"""Lightweight semantic checks that align generated artifacts with vuln_id intent."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

SUPPORTED_VULN_IDS = {"cwe-89", "cwe-352"}

_STATE_CHANGE_DECORATOR_RE = re.compile(r"@app\.(post|put|delete|patch)\s*\(", re.IGNORECASE)
_STATE_CHANGE_ROUTE_RE = re.compile(
    r"methods\s*=\s*\[[^\]]*(?:'POST'|\"POST\"|'PUT'|\"PUT\"|'DELETE'|\"DELETE\"|'PATCH'|\"PATCH\")",
    re.IGNORECASE,
)
_CSRF_GUARD_HINTS = (
    "csrf_token",
    "x-csrf-token",
    "x_csrf_token",
    "csrfmiddlewaretoken",
    "validate_csrf",
    "csrfprotect",
    "csrf_protect",
    "flask_wtf.csrf",
    "wtforms.csrf",
)
_SQL_EXEC_RE = re.compile(r"\b(?:execute|executemany)\s*\(", re.IGNORECASE)
_SQL_KEYWORD_RE = re.compile(r"\b(select|insert|update|delete|union)\b", re.IGNORECASE)
_INPUT_SOURCE_RE = re.compile(
    r"\brequest\.(?:args|form|values|get_json|json)\b|\binput\s*\(",
    re.IGNORECASE,
)
_UNSAFE_SQL_BUILD_PATTERNS = (
    re.compile(r"f[\"'][^\"']*(select|insert|update|delete|union)[^\"']*\{", re.IGNORECASE),
    re.compile(r"(select|insert|update|delete|union)[^\n]*\+\s*request\.", re.IGNORECASE),
    re.compile(r"request\.(?:args|form|values|get_json|json)[^\n]*\+\s*(?:\"|'|f\")", re.IGNORECASE),
    re.compile(r"\.format\s*\([^)]*request\.", re.IGNORECASE),
    re.compile(r"(select|insert|update|delete|union)[^\n]*(?:\+|%|\.format\()", re.IGNORECASE),
)


def normalize_vuln_id(vuln_id: str) -> str:
    token = (vuln_id or "").strip().lower()
    if not token:
        return ""
    if token.startswith("cwe-"):
        return token
    if token.startswith("cwe_"):
        return token.replace("_", "-", 1)
    if token.startswith("cwe"):
        return token.replace("cwe", "cwe-", 1)
    return f"cwe-{token}"


def evaluate_manifest_semantics(vuln_id: str, manifest: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_vuln_id(vuln_id)
    if normalized not in SUPPORTED_VULN_IDS:
        return {
            "supported": False,
            "semantic_match": True,
            "errors": [],
            "signals": {},
            "vuln_id": normalized or vuln_id,
        }

    service_text, combined_text, file_count = _collect_manifest_text(manifest)
    if normalized == "cwe-352":
        report = _evaluate_cwe_352(service_text, combined_text)
    else:
        report = _evaluate_cwe_89(combined_text)
    report["supported"] = True
    report["vuln_id"] = normalized
    report["scanned_files"] = file_count
    return report


def evaluate_workspace_semantics(
    vuln_id: str,
    workspace: Path,
    *,
    max_files: int = 64,
    max_file_bytes: int = 128_000,
) -> Dict[str, Any]:
    if not workspace or not workspace.exists() or not workspace.is_dir():
        return {
            "supported": False,
            "semantic_match": True,
            "errors": [],
            "signals": {},
            "vuln_id": normalize_vuln_id(vuln_id),
            "scanned_files": 0,
        }
    files: List[Dict[str, Any]] = []
    exts = {".py", ".js", ".ts", ".php", ".rb", ".java", ".go", ".sql", ".txt", ".md"}
    for path in sorted(workspace.rglob("*")):
        if len(files) >= max_files:
            break
        if not path.is_file():
            continue
        if path.suffix.lower() not in exts:
            continue
        try:
            if path.stat().st_size > max_file_bytes:
                continue
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        files.append({"path": str(path.relative_to(workspace)), "content": text})
    return evaluate_manifest_semantics(vuln_id, {"files": files})


def _collect_manifest_text(manifest: Dict[str, Any]) -> tuple[str, str, int]:
    body = manifest.get("manifest") if isinstance(manifest.get("manifest"), dict) else manifest
    files = body.get("files") if isinstance(body, dict) else []
    if not isinstance(files, list):
        return "", "", 0
    all_chunks: List[str] = []
    service_chunks: List[str] = []
    python_chunks: List[str] = []
    for entry in files:
        if not isinstance(entry, dict):
            continue
        content = entry.get("content")
        if not isinstance(content, str) or not content:
            continue
        path = str(entry.get("path") or "").strip().lower()
        role = str(entry.get("role") or "").strip().lower()
        all_chunks.append(content)
        if role == "service_main":
            service_chunks.append(content)
        elif path.endswith(".py"):
            python_chunks.append(content)
    if service_chunks:
        service_text = "\n".join(service_chunks)
    elif python_chunks:
        service_text = "\n".join(python_chunks)
    else:
        service_text = "\n".join(all_chunks)
    return service_text, "\n".join(all_chunks), len(all_chunks)


def _evaluate_cwe_352(service_text: str, combined_text: str) -> Dict[str, Any]:
    has_state_change_endpoint = bool(
        _STATE_CHANGE_DECORATOR_RE.search(service_text) or _STATE_CHANGE_ROUTE_RE.search(service_text)
    )
    lowered_service = service_text.lower()
    has_csrf_validation = any(token in lowered_service for token in _CSRF_GUARD_HINTS)
    sqli_semantics = _evaluate_cwe_89(combined_text)
    sqli_like = bool(sqli_semantics.get("semantic_match"))
    errors: List[str] = []
    if not has_state_change_endpoint:
        errors.append("missing state-changing endpoint (POST/PUT/DELETE/PATCH) required for CSRF scenario")
    if has_csrf_validation:
        errors.append("CSRF token validation detected; CWE-352 scenario must omit CSRF validation")
    if sqli_like and not has_state_change_endpoint:
        errors.append("SQLi-like sink/input pattern detected without CSRF workflow (likely CWE-89 mismatch)")
    return {
        "semantic_match": not errors,
        "errors": errors,
        "signals": {
            "state_changing_endpoint": has_state_change_endpoint,
            "csrf_validation_present": has_csrf_validation,
            "sqli_like_payload": sqli_like,
        },
    }


def _evaluate_cwe_89(combined_text: str) -> Dict[str, Any]:
    has_sql_sink = bool(_SQL_EXEC_RE.search(combined_text) and _SQL_KEYWORD_RE.search(combined_text))
    has_input_source = bool(_INPUT_SOURCE_RE.search(combined_text))
    has_unsafe_query_build = any(pattern.search(combined_text) for pattern in _UNSAFE_SQL_BUILD_PATTERNS)
    has_variable_flow = _has_input_variable_to_execute_flow(combined_text)
    has_input_to_sql_path = has_sql_sink and has_input_source and (has_unsafe_query_build or has_variable_flow)
    errors: List[str] = []
    if not has_sql_sink:
        errors.append("missing SQL sink pattern (execute + SQL keyword)")
    if has_sql_sink and not has_input_to_sql_path:
        errors.append("missing input-to-SQL composition path for CWE-89")
    return {
        "semantic_match": not errors,
        "errors": errors,
        "signals": {
            "sql_sink_present": has_sql_sink,
            "input_source_present": has_input_source,
            "unsafe_query_build_present": has_unsafe_query_build,
            "input_variable_to_execute_flow": has_variable_flow,
        },
    }


def _has_input_variable_to_execute_flow(text: str) -> bool:
    assignment_re = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*([^\n]+)", re.IGNORECASE)
    tainted_vars: set[str] = set()
    query_vars: set[str] = set()

    def _references_var(expr: str, var: str) -> bool:
        return bool(re.search(rf"\b{re.escape(var)}\b", expr))

    def _looks_unsafe_query_expr(expr: str, current_tainted: set[str]) -> bool:
        lowered = expr.lower()
        if not _SQL_KEYWORD_RE.search(expr):
            return False
        has_input_reference = bool(_INPUT_SOURCE_RE.search(expr))
        if not has_input_reference and current_tainted:
            has_input_reference = any(_references_var(expr, item) for item in current_tainted)
        if not has_input_reference:
            return False
        has_unsafe_builder = (
            "+" in expr
            or ".format(" in lowered
            or "%" in expr
            or expr.lstrip().startswith(("f\"", "f'"))
            or any(("{" + item + "}") in expr for item in current_tainted)
        )
        return has_unsafe_builder

    for match in assignment_re.finditer(text):
        lhs = match.group(1)
        rhs = match.group(2)
        if _INPUT_SOURCE_RE.search(rhs):
            tainted_vars.add(lhs)
        elif tainted_vars and any(_references_var(rhs, item) for item in tainted_vars):
            tainted_vars.add(lhs)
        if _looks_unsafe_query_expr(rhs, tainted_vars):
            query_vars.add(lhs)

    sink_vars = tainted_vars | query_vars
    for variable in sink_vars:
        sink_re = re.compile(
            rf"\b(?:execute|executemany)\s*\(\s*(?:query\s*=\s*)?{re.escape(variable)}\b",
            re.IGNORECASE,
        )
        if sink_re.search(text):
            return True
    return False


def semantic_error_summary(report: Dict[str, Any]) -> str:
    errors = report.get("errors")
    if isinstance(errors, str) and errors.strip():
        return errors.strip()
    if isinstance(errors, list):
        tokens = [str(item) for item in errors if item]
        if tokens:
            return "; ".join(tokens)
    return "semantic mismatch"


__all__ = [
    "evaluate_manifest_semantics",
    "evaluate_workspace_semantics",
    "normalize_vuln_id",
    "semantic_error_summary",
]
