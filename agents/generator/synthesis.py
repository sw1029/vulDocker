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
from typing import Any, Dict, List, Sequence, Tuple

from common.deps.stdlib import load_stdlib_spec
from common.logging import get_logger
from common.prompts import build_synthesis_prompt
from common.paths import ensure_dir
from evals.static_signatures import analyze_sql_injection_signals
from common.rules import load_rule

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
    "cmd": "python poc.py",
    "success_signature": "Exploit SUCCESS",
    "notes": "Auto-injected fallback PoC block",
}

DEFAULT_SUCCESS_SIGNATURES = {
    "cwe-89": "SQLi SUCCESS",
    "cwe-352": "CSRF SUCCESS",
}

DEFAULT_FLAG_TOKENS = {
    "cwe-89": "FLAG-sqli-demo-token",
    "cwe-352": "FLAG-csrf-demo-token",
}

FALLBACK_POC_ENDPOINTS = {
    "cwe-89": {
        "method": "get",
        "path": "/login",
        "payload": {
            "username": "' OR '1'='1",
            "password": "' OR '1'='1",
        },
    },
    "cwe-352": {
        "method": "post",
        "path": "/transfer",
        "payload": {
            "amount": "250",
        },
    },
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

    def run(
        self,
        *,
        requirement: Dict[str, Any],
        rag_context: str,
        hints: str,
        failure_context: str,
        candidate_k: int,
        poc_template: Dict[str, Any] | None = None,
    ) -> SynthesisOutcome:
        """Generate k candidates, select the best, and materialize it."""

        candidate_k = max(1, int(candidate_k or 1))
        reports: List[CandidateReport] = []
        self._requirement = requirement
        self._load_stdlib_spec()
        self._dep_guard_config = requirement.get("dep_guard") or {}
        self._auto_patch_enabled = bool(self._dep_guard_config.get("auto_patch"))
        self._rule = load_rule(requirement.get("vuln_id"))
        poc_template = self._normalize_poc_template(poc_template)

        for idx in range(1, candidate_k + 1):
            messages = build_synthesis_prompt(
                requirement,
                rag_context,
                hints=hints,
                failure_context=failure_context,
                limits=self.limits.to_dict(),
                candidate_index=idx,
                poc_template=poc_template,
            )
            raw = self.llm.generate(messages)
            manifest = self._parse_manifest(raw, idx)
            manifest = self._apply_poc_template(manifest, poc_template)
            manifest = self._ensure_fallback_poc(manifest, poc_template)
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
            violations, guard_report = self._guard_manifest(
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
        if vuln in {"cwe-89", "sqli"}:
            return analyze_sql_injection_signals(manifest)
        return {"signals": {}, "hit_count": 0, "score": 0.0, "keywords_found": []}

    def _normalize_poc_template(self, template: Dict[str, Any] | None) -> Dict[str, Any]:
        normalized = dict(DEFAULT_POC_TEMPLATE)
        if isinstance(template, dict):
            for key, value in template.items():
                if value:
                    normalized[key] = value
        vuln = str(self._requirement.get("vuln_id") or "").strip().lower()
        rule_sig = (self._rule or {}).get("success_signature") if hasattr(self, "_rule") else None
        success_signature = rule_sig or DEFAULT_SUCCESS_SIGNATURES.get(vuln, normalized.get("success_signature") or "Exploit SUCCESS")
        normalized["success_signature"] = success_signature
        rule_flag = (self._rule or {}).get("flag_token") if hasattr(self, "_rule") else None
        flag_token = rule_flag or DEFAULT_FLAG_TOKENS.get(vuln, "FLAG-demo-token")
        normalized["flag_token"] = flag_token
        flag_note = f"On exploit success, print '{success_signature}' and '{flag_token}'."
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
        self._stdlib_modules = {self._canonicalize_package_name(name) for name in spec.stdlib_modules}
        # Merge aliases/defaults with fallbacks to preserve canonical names.
        self._module_alias_map = dict(PYTHON_MODULE_PACKAGE_MAP)
        self._module_alias_map.update({k.lower(): v for k, v in spec.aliases.items()})
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

    def _ensure_fallback_poc(self, manifest: Dict[str, Any], template: Dict[str, Any]) -> Dict[str, Any]:
        files = manifest.get("files")
        if not isinstance(files, list):
            manifest["files"] = files = []
        has_poc_file = any(isinstance(entry, dict) and (entry.get("path") or "").lower() == "poc.py" for entry in files)
        if has_poc_file:
            return manifest
        vuln = str(self._requirement.get("vuln_id") or "").strip().lower()
        success_signature = template.get("success_signature") or DEFAULT_SUCCESS_SIGNATURES.get(vuln, "Exploit SUCCESS")
        flag_token = template.get("flag_token") or DEFAULT_FLAG_TOKENS.get(vuln, "FLAG-demo-token")
        content = self._build_fallback_poc_content(vuln, success_signature, flag_token)
        files.append(
            {
                "path": "poc.py",
                "description": "Fallback PoC used when the LLM omits poc.py",
                "content": content,
            }
        )
        return manifest

    def _parse_manifest(self, raw: str, idx: int) -> Dict[str, Any]:
        try:
            manifest = json.loads(raw)
            if isinstance(manifest, dict):
                return manifest
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                snippet = raw[start : end + 1]
                try:
                    manifest = json.loads(snippet)
                    if isinstance(manifest, dict):
                        return manifest
                except json.JSONDecodeError:
                    pass
        LOGGER.warning("Candidate %s emitted non-JSON manifest; using fallback.", idx)
        return self._fallback_manifest()

    def _fallback_manifest(self) -> Dict[str, Any]:
        """Deterministic manifest used when the LLM stub is active."""

        stack = self._requirement.get("framework") or self._requirement.get("language", "python")
        notes = (
            "Fallback manifest auto-generated because the LLM response was not valid JSON. "
            "The layout still passes guard rails for deterministic testing."
        )
        return {
            "intent": f"{self._requirement.get('vuln_id', 'CWE-89')} fallback synthesis",
            "pattern_tags": ["sqli", "string-concat"],
            "files": [
                {
                    "path": "Dockerfile",
                    "description": "Build Python image and seed SQLite DB.",
                    "content": (
                        "FROM python:3.11-slim\n"
                        "WORKDIR /app\n"
                        "COPY . /app\n"
                        "RUN pip install -r requirements.txt && sqlite3 app.db < schema.sql && sqlite3 app.db < seed_data.sql\n"
                        "CMD [\"python\", \"app.py\"]\n"
                    ),
                },
                {
                    "path": "requirements.txt",
                    "description": "Pinned deps for SBOM.",
                    "content": "Flask==2.3.3\nJinja2==3.1.4\n",
                },
                {
                    "path": "app.py",
                    "description": f"{stack} vulnerable endpoint.",
                    "content": (
                        "from flask import Flask, request\n"
                        "import sqlite3\n"
                        "app = Flask(__name__)\n\n"
                        "@app.route('/login')\n"
                        "def login():\n"
                        "    username = request.args.get('username', '')\n"
                        "    password = request.args.get('password', '')\n"
                        "    query = f\"SELECT username FROM users WHERE username = '{username}' AND password = '{password}'\"\n"
                        "    conn = sqlite3.connect('app.db')\n"
                        "    cursor = conn.cursor()\n"
                        "    rows = cursor.execute(query).fetchall()\n"
                        "    conn.close()\n"
                        "    if rows:\n"
                        "        return 'SQLi SUCCESS'\n"
                        "    return 'Invalid credentials'\n"
                        "\n"
                        "if __name__ == '__main__':\n"
                        "    app.run(host='0.0.0.0', port=8000)\n"
                    ),
                },
                {
                    "path": "schema.sql",
                    "description": "User table schema.",
                    "content": "CREATE TABLE IF NOT EXISTS users (username TEXT, password TEXT);\n",
                },
                {
                    "path": "seed_data.sql",
                    "description": "Baseline records.",
                    "content": "INSERT INTO users VALUES ('admin', 'admin');\n",
                },
                {
                    "path": "poc.py",
                    "description": "Simple UNION-based exploit.",
                    "content": (
                        "import requests\n"
                        "payload = \"admin' OR '1'='1\"\n"
                        "resp = requests.get('http://127.0.0.1:8000/login', params={'username': payload, 'password': 'x'})\n"
                        "print(resp.text)\n"
                    ),
                },
                {
                    "path": "README.md",
                    "description": "Usage instructions.",
                    "content": (
                        "# CWE-89 fallback bundle\n"
                        "```bash\n"
                        "docker build -t cwe-89 .\n"
                        "docker run -p 8000:8000 cwe-89\n"
                        "python poc.py\n"
                        "```\n"
                    ),
                },
            ],
            "deps": ["Flask==2.3.3", "requests==2.32.2"],
            "build": {"command": "pip install -r requirements.txt"},
            "run": {"command": "python app.py", "port": 8000},
            "poc": {"cmd": "python poc.py", "success_signature": "SQLi SUCCESS"},
            "notes": notes,
            "metadata": {
                "sid": self.sid,
                "stack": stack,
                "cwe": self._requirement.get("vuln_id", "CWE-89"),
            },
        }

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

        poc = manifest.get("poc", {})
        if not isinstance(poc, dict) or "cmd" not in poc or "success_signature" not in poc:
            errors.append("poc section incomplete")
        else:
            signature = poc.get("success_signature", "")
            vuln = str((self._requirement or {}).get("vuln_id") or "").strip().lower()
            rule_sig = (self._rule or {}).get("success_signature") if hasattr(self, "_rule") else None
            expected_signature = rule_sig or DEFAULT_SUCCESS_SIGNATURES.get(vuln, "Exploit SUCCESS")
            if expected_signature and expected_signature not in signature:
                errors.append(f"success_signature must include '{expected_signature}'")
            expected_flag = None
            if hasattr(self, "_rule"):
                expected_flag = (self._rule or {}).get("flag_token")
            expected_flag = expected_flag or DEFAULT_FLAG_TOKENS.get(vuln)
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
                if path and needle and not self._file_contains(manifest, path, needle):
                    errors.append(f"rule violation: file {path} missing '{needle}'")
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
        }

        return errors, dep_guard

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
        manifest_payload = {
            "sid": self.sid,
            "mode": self.mode,
            "limits": self.limits.to_dict(),
            "selected_candidate": selected.to_summary(),
            "manifest": selected.manifest,
            "failure_context": failure_context,
            "hints_digest": hashlib.sha256(hints.encode("utf-8")).hexdigest() if hints else "",
            "rag_snapshot_digest": hashlib.sha256(rag_context.encode("utf-8")).hexdigest()
            if rag_context
            else "",
            "user_deps": self._user_deps,
            "requires_external_db": requires_external_db,
        }
        manifest_path.write_text(json.dumps(manifest_payload, indent=2, ensure_ascii=False), encoding="utf-8")
        self._write_candidate_log(reports)

    def _record_guard_failure(self, reports: List[CandidateReport]) -> None:
        failure_path = self.metadata_dir / "generator_failures.jsonl"
        ensure_dir(failure_path.parent)
        missing_static: set[str] = set()
        missing_from_requirements: set[str] = set()
        missing_from_build: set[str] = set()
        llm_high_conf: set[str] = set()
        guard_notes: List[str] = []
        auto_patched: set[str] = set()
        auto_patch_entries: List[Dict[str, Any]] = []
        for report in reports:
            guard = report.guard_report or {}
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
        suggested = sorted(llm_high_conf or missing_static)
        if auto_patched:
            suggested = sorted(set(suggested) | auto_patched)
        missing_all = sorted(missing_static | missing_from_requirements | missing_from_build | llm_high_conf)
        timestamp = datetime.now(timezone.utc).isoformat()
        reason = "; ".join(sorted(set(guard_notes))) or "guard violations"
        fix_hint = "Add the missing dependencies to manifest.deps and requirements*.txt, then re-run synthesis."
        entry = {
            "stage": "GENERATOR",
            "timestamp": timestamp,
            "reason": reason,
            "fix_hint": fix_hint,
            "missing_dependencies": missing_all,
            "suggested_dependencies": suggested,
            "notes": guard_notes,
            "auto_patch": auto_patch_entries[-1] if auto_patch_entries else {},
        }
        with failure_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

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
        requirements_packages = self._extract_packages_from_requirements(requirements_entry.get("content", ""))
        missing_requirements = declared_deps - requirements_packages
        for canonical in sorted(missing_requirements):
            if canonical in self._auto_patch_denylist:
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
        return self._canonicalize_package_name(name) in self._stdlib_modules
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
        return {
            self._canonicalize_package_name(name)
            for name in detect_python_required(manifest, self._read_text_content)
        }

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
    def _poc_contains(manifest: Dict[str, Any], needle: str) -> bool:
        if not needle:
            return False
        poc = manifest.get("poc")
        if isinstance(poc, dict):
            for key in ("cmd", "notes", "success_signature"):
                value = poc.get(key)
                if isinstance(value, str) and needle in value:
                    return True
        for entry in manifest.get("files", []):
            if not isinstance(entry, dict):
                continue
            path = str(entry.get("path") or "").strip().lower()
            if path.endswith("poc.py"):
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

    def _build_fallback_poc_content(self, vuln: str, success_signature: str, flag_token: str) -> str:
        endpoint = FALLBACK_POC_ENDPOINTS.get(vuln) or FALLBACK_POC_ENDPOINTS.get("cwe-89")
        method = (endpoint.get("method") or "get").lower()
        path = endpoint.get("path", "/")
        payload = endpoint.get("payload") or {}
        payload_literal = json.dumps(payload)
        lines = [
            "import argparse",
            "import sys",
            "import requests",
            "",
            "DEFAULT_BASE = 'http://127.0.0.1:5000'",
            "PAYLOAD = " + payload_literal,
            "SUCCESS_SIGNATURE = " + repr(success_signature),
            "FLAG_TOKEN = " + repr(flag_token),
            "",
            "def exploit(base_url: str) -> bool:",
            "    url = base_url.rstrip('/') + '" + path + "'",
        ]
        if method == "post":
            lines.append("    response = requests.post(url, data=PAYLOAD, timeout=5)")
        else:
            lines.append("    response = requests.get(url, params=PAYLOAD, timeout=5)")
        lines.extend(
            [
                "    if response.status_code < 400:",
                "        print(SUCCESS_SIGNATURE)",
                "        print(FLAG_TOKEN)",
                "        return True",
                "    return False",
                "",
                "def main():",
                "    parser = argparse.ArgumentParser(description='Fallback PoC executor')",
                "    parser.add_argument('--base-url', default=DEFAULT_BASE)",
                "    args = parser.parse_args()",
                "    if not exploit(args.base_url):",
                "        print('Exploit failed; signature not emitted')",
                "        sys.exit(1)",
                "",
                "if __name__ == '__main__':",
                "    main()",
            ]
        )
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


    def _inject_user_deps(self, manifest: Dict[str, Any]) -> Dict[str, Any]:
        if not self._user_deps:
            return manifest
        deps = [dep for dep in (manifest.get("deps") or []) if isinstance(dep, str) and dep.strip()]
        lower_seen = {dep.lower() for dep in deps}
        for dep in self._user_deps:
            key = dep.lower()
            if key in lower_seen:
                continue
            deps.append(dep)
            lower_seen.add(key)
        manifest["deps"] = deps
        return manifest


__all__ = ["SynthesisEngine", "SynthesisLimits", "ManifestValidationError"]
