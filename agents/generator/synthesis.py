"""Synthesis engine for TODO 14.5.

This module turns LLM JSON manifests into on-disk workspaces while enforcing
the guard rails described in docs/milestones/todo_13-15_code_plan.md."""
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
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from common.logging import get_logger
from common.prompts import build_synthesis_prompt
from common.paths import ensure_dir
from evals.static_signatures import analyze_sql_injection_signals

try:  # Python >=3.11
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - fallback for older interpreters
    tomllib = None

LOGGER = get_logger(__name__)
DEFAULT_POC_TEMPLATE = {
    "cmd": "python poc.py",
    "success_signature": "SQLi SUCCESS",
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


FALLBACK_STDLIB_MODULES = {
    "abc",
    "argparse",
    "asyncio",
    "base64",
    "collections",
    "contextlib",
    "dataclasses",
    "datetime",
    "functools",
    "hashlib",
    "http",
    "json",
    "logging",
    "math",
    "os",
    "pathlib",
    "random",
    "re",
    "sqlite3",
    "ssl",
    "statistics",
    "subprocess",
    "sys",
    "threading",
    "typing",
    "unittest",
    "urllib",
    "uuid",
}


PIP_INSTALL_PATTERN = re.compile(r"pip(?:3)?\s+install(?P<body>[^&;|\n]*)", re.IGNORECASE)


@dataclass
class DeclaredDependencies:
    combined: set[str]
    from_deps_field: set[str]
    from_requirements: set[str]
    requirements_by_path: Dict[str, set[str]]


@dataclass(frozen=True)
class SynthesisLimits:
    """Constraints mirrored in docs/schemas/generator_manifest.md."""

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
    ) -> None:
        self.sid = sid
        self.llm = llm
        self.limits = limits
        self.workspace = workspace
        self.metadata_dir = ensure_dir(metadata_dir)
        self.mode = mode
        ensure_dir(self.workspace.parent)
        stdlib_names = getattr(sys, "stdlib_module_names", None)
        stdlib_pool = set(stdlib_names) if stdlib_names else set()
        stdlib_pool.update(FALLBACK_STDLIB_MODULES)
        self._stdlib_modules = {
            self._canonicalize_package_name(name)
            for name in stdlib_pool
            if self._canonicalize_package_name(name)
        }

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
            violations, guard_report = self._guard_manifest(manifest)
            static_report = analyze_sql_injection_signals(manifest)
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
        written = self._materialize(selected.manifest)
        self._write_records(selected, reports, hints, rag_context, failure_context)
        return SynthesisOutcome(selected=selected, written_files=written, reports=reports)

    # --- internal helpers -------------------------------------------------
    @staticmethod
    def _score_candidate(violation_count: int, signal_score: float) -> float:
        base = max(0.0, 1.0 - 0.2 * violation_count)
        bonus = max(0.0, min(1.0, signal_score)) * 0.3
        return min(1.0, round(base + bonus, 3))

    def _normalize_poc_template(self, template: Dict[str, Any] | None) -> Dict[str, Any]:
        normalized = dict(DEFAULT_POC_TEMPLATE)
        if isinstance(template, dict):
            for key, value in template.items():
                if value:
                    normalized[key] = value
        signature = normalized.get("success_signature", "")
        if "SQLi SUCCESS" not in signature:
            normalized["success_signature"] = f"{signature} SQLi SUCCESS".strip()
        return normalized

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

    def _guard_manifest(self, manifest: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
        errors: List[str] = []
        dep_error_messages: List[str] = []

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
            if "SQLi SUCCESS" not in signature:
                errors.append("success_signature must include 'SQLi SUCCESS'")

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
        }
        manifest_path.write_text(json.dumps(manifest_payload, indent=2, ensure_ascii=False), encoding="utf-8")
        self._write_candidate_log(reports)

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
        required: set[str] = set()
        for entry in manifest.get("files", []):
            if not isinstance(entry, dict):
                continue
            path = (entry.get("path") or "").strip()
            if not path or not self._is_python_path(path):
                continue
            content = self._read_text_content(entry)
            if not content:
                continue
            required.update(self._detect_python_imports(content))
        return required

    def _detect_python_imports(self, source: str) -> set[str]:
        packages: set[str] = set()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return packages
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = (alias.name or "").split(".")[0]
                    package = self._canonicalize_package_name(root)
                    if package and package not in self._stdlib_modules:
                        packages.add(package)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    continue  # relative import
                module = node.module or ""
                root = module.split(".")[0]
                package = self._canonicalize_package_name(root)
                if package and package not in self._stdlib_modules:
                    packages.add(package)
        return packages

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
        return PYTHON_MODULE_PACKAGE_MAP.get(normalized, normalized)

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


__all__ = ["SynthesisEngine", "SynthesisLimits", "ManifestValidationError"]
