"""Lightweight semantic checks that align generated artifacts with vuln_id intent."""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Dict, List

from common.roles import role_matches

SUPPORTED_VULN_IDS = {"cwe-22", "cwe-89", "cwe-352", "cwe-918"}
FAMILY_CANONICAL_TAGS = {
    "cwe-89": {"request_input", "sql_sink", "sql_injection"},
    "cwe-352": {"csrf_flow", "state_change", "csrf_protection"},
    "cwe-22": {"request_input", "path_input", "file_sink", "path_traversal"},
    "cwe-918": {"request_input", "url_input", "http_client_sink", "ssrf"},
    "cwe-78": {"request_input", "command_input", "command_sink", "command_injection"},
    "cwe-94": {"request_input", "code_input", "code_sink", "code_injection"},
    "cwe-79": {"request_input", "template_sink", "xss"},
    "cwe-502": {"serialized_input", "deserialization_sink", "deserialization"},
}
BASELINE_SEMANTIC_SIGNATURES = {
    "cwe-89": {
        "input_vector": ["user-controlled request parameter"],
        "sink": ["SQL query execution"],
        "exploit_precondition": ["input concatenated/interpolated into SQL sink"],
    },
    "cwe-352": {
        "input_vector": ["cross-site request", "cookie-authenticated session"],
        "sink": ["state-changing endpoint (POST/PUT/DELETE/PATCH)"],
        "exploit_precondition": ["missing CSRF token validation"],
    },
    "cwe-22": {
        "input_vector": ["request.args", "path parameter"],
        "sink": ["open(", "send_file", "send_from_directory"],
        "exploit_precondition": ["../", "os.path.join", "path traversal"],
    },
    "cwe-918": {
        "input_vector": ["request.args", "url parameter", "user-controlled url"],
        "sink": ["requests.get", "urllib.request", "http client request"],
        "exploit_precondition": ["server-side request forgery", "169.254.169.254"],
    },
    "cwe-78": {
        "input_vector": ["request.args", "command parameter"],
        "sink": ["subprocess", "os.system", "shell=True"],
        "exploit_precondition": ["command injection", "user input in command"],
    },
    "cwe-94": {
        "input_vector": ["request.args", "code parameter"],
        "sink": ["eval(", "exec("],
        "exploit_precondition": ["code injection", "user input reaches eval"],
    },
    "cwe-79": {
        "input_vector": ["request.args", "query parameter", "user input"],
        "sink": ["render_template_string", "template response"],
        "exploit_precondition": ["<script>", "unescaped reflection", "cross-site scripting"],
    },
    "cwe-502": {
        "input_vector": ["request.data", "serialized payload"],
        "sink": ["pickle.loads", "yaml.load", "jsonpickle.decode"],
        "exploit_precondition": ["untrusted deserialization", "attacker-controlled serialized input"],
    },
}

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
_FILE_READ_RE = re.compile(r"\b(?:open|send_file|send_from_directory|read_text|read_bytes)\s*\(", re.IGNORECASE)
_PATH_INPUT_RE = re.compile(
    r"\brequest\.(?:args|form|values|get_json|json)\b|(?:path|file|filename)\s*=",
    re.IGNORECASE,
)
_PATH_TRAVERSAL_RE = re.compile(r"\.\./|\.\.\\\\|/etc/passwd|os\.path\.join|path traversal", re.IGNORECASE)
_HTTP_CLIENT_RE = re.compile(
    r"\b(?:requests\.(?:get|post|put|delete|request)|urllib\.request|urlopen)\b",
    re.IGNORECASE,
)
_URL_INPUT_RE = re.compile(r"\brequest\.(?:args|form|values|get_json|json)\b|url\s*=", re.IGNORECASE)
_SSRF_INDICATOR_RE = re.compile(
    r"169\.254\.169\.254|internal service|metadata|127\.0\.0\.1|localhost|/metadata|flag\{ssrf_ok\}",
    re.IGNORECASE,
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


def baseline_semantic_signature(vuln_id: str) -> Dict[str, List[str]]:
    normalized = normalize_vuln_id(vuln_id)
    baseline = BASELINE_SEMANTIC_SIGNATURES.get(normalized) or {}
    return {
        "input_vector": list(baseline.get("input_vector") or []),
        "sink": list(baseline.get("sink") or []),
        "exploit_precondition": list(baseline.get("exploit_precondition") or []),
    }


def semantic_term_aliases(term: str) -> set[str]:
    token = str(term or "").strip().lower()
    aliases = {token}
    if not token:
        return aliases
    if any(
        key in token
        for key in {
            "request.args",
            "request.form",
            "request.json",
            "request parameter",
            "query parameter",
            "user-controlled request parameter",
        }
    ):
        aliases.add("request_input")
    if any(key in token for key in {"path parameter", "filename", "filepath"}):
        aliases.add("path_input")
    if any(key in token for key in {"url parameter", "user-controlled url", "target url"}):
        aliases.add("url_input")
    if any(key in token for key in {"command parameter", "shell argument"}):
        aliases.add("command_input")
    if any(key in token for key in {"code parameter", "script parameter"}):
        aliases.add("code_input")
    if any(key in token for key in {"request.data", "request.get_data", "serialized payload"}):
        aliases.add("serialized_input")
    if any(key in token for key in {"cross-site request", "cookie-authenticated session"}):
        aliases.add("csrf_flow")
    if any(key in token for key in {"state-changing endpoint", "post", "put", "delete", "patch"}):
        aliases.add("state_change")
    if any(key in token for key in {"csrf token", "origin validation", "referer validation"}):
        aliases.add("csrf_protection")
    if any(key in token for key in {"sql query execution", "cursor.execute", "execute("}):
        aliases.add("sql_sink")
    if any(key in token for key in {"open(", "send_file", "send_from_directory"}):
        aliases.add("file_sink")
    if any(key in token for key in {"requests.get", "urllib.request", "http client request", "urlopen("}):
        aliases.add("http_client_sink")
    if any(key in token for key in {"subprocess", "os.system", "shell=true"}):
        aliases.add("command_sink")
    if any(key in token for key in {"eval(", "exec("}):
        aliases.add("code_sink")
    if any(key in token for key in {"pickle.loads", "yaml.load", "jsonpickle.decode"}):
        aliases.add("deserialization_sink")
    if any(key in token for key in {"render_template_string", "template response", "innerhtml"}):
        aliases.add("template_sink")
    if any(key in token for key in {"string concatenation", "or 1=1", "union select"}):
        aliases.add("sql_injection")
    if any(key in token for key in {"../", "os.path.join", "path traversal"}):
        aliases.add("path_traversal")
    if any(key in token for key in {"server-side request forgery", "169.254.169.254"}):
        aliases.add("ssrf")
    if any(key in token for key in {"command injection", "user input in command"}):
        aliases.add("command_injection")
    if any(key in token for key in {"code injection", "user input reaches eval"}):
        aliases.add("code_injection")
    if any(key in token for key in {"cross-site scripting", "<script>", "unescaped reflection"}):
        aliases.add("xss")
    if any(key in token for key in {"untrusted deserialization", "attacker-controlled serialized input"}):
        aliases.add("deserialization")
    return aliases


def family_canonical_tags(vuln_id: str) -> set[str]:
    normalized = normalize_vuln_id(vuln_id)
    tags = set(FAMILY_CANONICAL_TAGS.get(normalized) or set())
    baseline = baseline_semantic_signature(normalized)
    for bucket in ("input_vector", "sink", "exploit_precondition"):
        for value in baseline.get(bucket) or []:
            tags.update(semantic_term_aliases(value))
    return tags


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
    elif normalized == "cwe-89":
        report = _evaluate_cwe_89(combined_text)
    elif normalized == "cwe-22":
        report = _evaluate_cwe_22(combined_text)
    else:
        report = _evaluate_cwe_918(combined_text)
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
        role = entry.get("role")
        all_chunks.append(content)
        if role_matches(role, "service_main"):
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


def _evaluate_cwe_22(combined_text: str) -> Dict[str, Any]:
    has_file_sink = bool(_FILE_READ_RE.search(combined_text))
    has_path_input = bool(_PATH_INPUT_RE.search(combined_text))
    has_traversal_indicator = bool(_PATH_TRAVERSAL_RE.search(combined_text))
    errors: List[str] = []
    if not has_file_sink:
        errors.append("missing filesystem read sink for CWE-22")
    if has_file_sink and not has_path_input:
        errors.append("missing request-controlled path/filename input for CWE-22")
    if has_file_sink and has_path_input and not has_traversal_indicator:
        errors.append("missing traversal indicator (../, /etc/passwd, os.path.join) for CWE-22")
    return {
        "semantic_match": not errors,
        "errors": errors,
        "signals": {
            "file_sink_present": has_file_sink,
            "path_input_present": has_path_input,
            "traversal_indicator_present": has_traversal_indicator,
        },
    }


def _evaluate_cwe_918(combined_text: str) -> Dict[str, Any]:
    has_http_sink = bool(_HTTP_CLIENT_RE.search(combined_text))
    has_url_input = bool(_URL_INPUT_RE.search(combined_text))
    has_ssrf_indicator = bool(_SSRF_INDICATOR_RE.search(combined_text))
    errors: List[str] = []
    if not has_http_sink:
        errors.append("missing server-side HTTP client sink for CWE-918")
    if has_http_sink and not has_url_input:
        errors.append("missing request-controlled URL input for CWE-918")
    if has_http_sink and has_url_input and not has_ssrf_indicator:
        errors.append("missing SSRF indicator (metadata/internal target) for CWE-918")
    return {
        "semantic_match": not errors,
        "errors": errors,
        "signals": {
            "http_sink_present": has_http_sink,
            "url_input_present": has_url_input,
            "ssrf_indicator_present": has_ssrf_indicator,
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

    try:
        tree = ast.parse(text)
    except SyntaxError:
        tree = None
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
                if not targets:
                    continue
                expr = ast.unparse(node.value)
                references_tainted = bool(
                    tainted_vars and any(_references_var(expr, item) for item in tainted_vars)
                )
                if _INPUT_SOURCE_RE.search(expr) or references_tainted:
                    tainted_vars.update(targets)
                if _looks_unsafe_query_expr(expr, tainted_vars):
                    query_vars.update(targets)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
                expr = ast.unparse(node.value)
                references_tainted = bool(
                    tainted_vars and any(_references_var(expr, item) for item in tainted_vars)
                )
                if _INPUT_SOURCE_RE.search(expr) or references_tainted:
                    tainted_vars.add(node.target.id)
                if _looks_unsafe_query_expr(expr, tainted_vars):
                    query_vars.add(node.target.id)
            elif isinstance(node, ast.Call):
                func = node.func
                func_name = ""
                if isinstance(func, ast.Attribute):
                    func_name = func.attr
                elif isinstance(func, ast.Name):
                    func_name = func.id
                if func_name.lower() not in {"execute", "executemany"}:
                    continue
                if not node.args:
                    continue
                first_arg = node.args[0]
                if isinstance(first_arg, ast.Name) and first_arg.id in (tainted_vars | query_vars):
                    return True
                if _looks_unsafe_query_expr(ast.unparse(first_arg), tainted_vars):
                    return True

    for match in assignment_re.finditer(text):
        lhs = match.group(1)
        rhs = match.group(2)
        if _INPUT_SOURCE_RE.search(rhs):
            tainted_vars.add(lhs)
        elif tainted_vars and any(_references_var(rhs, item) for item in tainted_vars):
            tainted_vars.add(lhs)
        if _looks_unsafe_query_expr(rhs, tainted_vars):
            query_vars.add(lhs)

    for variable in tainted_vars:
        multiline_sql_assign = re.compile(
            rf"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*\(?[\s\S]{{0,320}}?"
            rf"\b(select|insert|update|delete|union)\b[\s\S]{{0,320}}?\+\s*{re.escape(variable)}\b",
            re.IGNORECASE,
        )
        for match in multiline_sql_assign.finditer(text):
            query_vars.add(match.group(1))

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
    "baseline_semantic_signature",
    "evaluate_manifest_semantics",
    "evaluate_workspace_semantics",
    "family_canonical_tags",
    "normalize_vuln_id",
    "semantic_term_aliases",
    "semantic_error_summary",
]
