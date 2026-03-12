"""Execution engine for dynamic GuardSpec assertions."""
from __future__ import annotations

import re
import fnmatch
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from common.roles import normalize_role, role_matches
from common.vuln_semantics import (
    evaluate_manifest_semantics,
    evaluate_workspace_semantics,
    is_service_side_workspace_path,
    normalize_vuln_id,
    semantic_error_summary,
)
from evals.assertions import run_assertions

from .types import GuardSpec, default_guard_policy_snapshot, parse_guard_spec


@dataclass
class GuardEvaluation:
    passed: bool
    blocking: bool
    violations: List[str]
    warnings: List[str]
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "blocking": self.blocking,
            "violations": self.violations,
            "warnings": self.warnings,
            "details": self.details,
        }


class GuardEngine:
    """Evaluate dynamic guard assertions across generator/verifier/reviewer."""

    def __init__(self, vuln_id: str, guard_spec: Optional[GuardSpec | Dict[str, Any]]) -> None:
        from common.contracts import can_resolve_without_remote_research

        self.vuln_id = str(vuln_id or "").strip()
        self.normalized_vuln_id = normalize_vuln_id(self.vuln_id)
        self.is_known = can_resolve_without_remote_research(self.vuln_id)
        self.spec = self._parse_spec(guard_spec)
        self.policy_snapshot = default_guard_policy_snapshot(
            self.spec.policy_snapshot if isinstance(self.spec, GuardSpec) else None
        )

    @property
    def available(self) -> bool:
        return self.spec is not None

    def should_block(self) -> bool:
        enforcement = str(self.policy_snapshot.get("enforcement") or "block_both").strip().lower()
        if enforcement == "warn_only":
            return False
        if enforcement == "block_unknown":
            return not self.is_known
        return True

    def should_fail_when_missing_spec(self) -> bool:
        failure_policy = str(self.policy_snapshot.get("failure_policy") or "closed_unknown").strip().lower()
        if failure_policy == "closed_all":
            return True
        if failure_policy == "closed_unknown":
            return not self.is_known
        return False

    def evaluate_manifest(self, manifest: Dict[str, Any]) -> GuardEvaluation:
        if not self.available:
            return GuardEvaluation(
                passed=True,
                blocking=False,
                violations=[],
                warnings=["guard spec unavailable; manifest guard skipped"],
                details={"available": False},
            )

        spec = self.spec
        assert spec is not None
        violations: List[str] = []
        warnings: List[str] = []
        assertion_details: List[Dict[str, Any]] = []
        downgraded_assertions: List[Dict[str, Any]] = []
        scope = str(self.policy_snapshot.get("dynamic_scope") or "assertions_semantics").strip().lower()
        semantic_detail = self._evaluate_manifest_semantics(manifest)
        builtin_semantics_passed = bool(
            scope == "assertions_semantics"
            and isinstance(semantic_detail, dict)
            and isinstance(semantic_detail.get("builtin"), dict)
            and semantic_detail.get("builtin", {}).get("supported")
            and semantic_detail.get("builtin", {}).get("semantic_match")
        )

        for assertion in spec.generator_assertions:
            ok, detail = _evaluate_generator_assertion(manifest, assertion)
            intent = str(assertion.get("intent") or "semantic_anchor").strip().lower()
            stability = str(assertion.get("stability") or "medium").strip().lower()
            severity = str(assertion.get("severity") or "block").strip().lower()
            if severity not in {"block", "warn"}:
                severity = "block"
            downgraded = False
            downgrade_reason = ""
            if not ok and severity == "warn":
                downgraded = True
                downgrade_reason = "assertion marked as warn"
            elif (
                not ok
                and builtin_semantics_passed
                and scope == "assertions_semantics"
                and (intent == "syntax_hint" or stability == "low")
            ):
                downgraded = True
                downgrade_reason = "syntax_hint/low-stability downgraded under semantics-first policy"
            assertion_details.append(
                {
                    "assertion": assertion,
                    "ok": ok,
                    "detail": detail,
                    "severity": severity,
                    "intent": intent,
                    "stability": stability,
                    "downgraded": downgraded,
                    "downgrade_reason": downgrade_reason,
                }
            )
            if not ok:
                if downgraded:
                    warnings.append(f"guard assertion warning: {detail}")
                    downgraded_assertions.append(
                        {
                            "op": str(assertion.get("op") or ""),
                            "detail": detail,
                            "reason": downgrade_reason,
                        }
                    )
                else:
                    violations.append(f"guard assertion failed: {detail}")

        if semantic_detail["errors"]:
            violations.extend(f"guard semantic mismatch: {item}" for item in semantic_detail["errors"])
        semantic_warnings = semantic_detail.get("warnings")
        if isinstance(semantic_warnings, list):
            for item in semantic_warnings:
                if isinstance(item, str) and item.strip():
                    warnings.append(f"guard semantic warning: {item.strip()}")

        blocking = self.should_block() and bool(violations)
        passed = not blocking
        if violations and not self.should_block():
            warnings.extend(violations)
            violations = []
            passed = True
            blocking = False

        return GuardEvaluation(
            passed=passed,
            blocking=blocking,
            violations=violations,
            warnings=warnings,
            details={
                "available": True,
                "policy_snapshot": self.policy_snapshot,
                "assertions": assertion_details,
                "downgraded_assertions": downgraded_assertions,
                "semantic": semantic_detail,
            },
        )

    def evaluate_verifier_log(self, log_text: str) -> GuardEvaluation:
        if not self.available:
            return GuardEvaluation(
                passed=True,
                blocking=False,
                violations=[],
                warnings=["guard spec unavailable; verifier guard skipped"],
                details={"available": False},
            )
        spec = self.spec
        assert spec is not None
        normalized_assertions = [_normalize_verifier_assertion(assertion) for assertion in spec.verifier_assertions]
        success, outcomes = run_assertions(log_text, normalized_assertions)
        violations: List[str] = []
        details: List[Dict[str, Any]] = []
        for outcome in outcomes:
            details.append({"op": outcome.op, "success": outcome.success, "details": outcome.details})
            if not outcome.success:
                violations.append(f"verifier assertion failed ({outcome.op}): {outcome.details}")
        if not success and not violations:
            violations.append("verifier assertion program failed")
        deferred = spec.verifier_assertions_deferred if isinstance(spec.verifier_assertions_deferred, list) else []

        blocking = self.should_block() and bool(violations)
        passed = not blocking
        warnings: List[str] = []
        if deferred:
            warnings.append(f"{len(deferred)} verifier assertions deferred (non-blocking)")
        if violations and not self.should_block():
            warnings.extend(violations)
            violations = []
            passed = True
            blocking = False
        return GuardEvaluation(
            passed=passed,
            blocking=blocking,
            violations=violations,
            warnings=warnings,
            details={
                "available": True,
                "policy_snapshot": self.policy_snapshot,
                "assertions": details,
                "deferred_assertions": deferred,
            },
        )

    def evaluate_workspace(self, workspace_dirs: Sequence[Path]) -> GuardEvaluation:
        if not self.available:
            return GuardEvaluation(
                passed=True,
                blocking=False,
                violations=[],
                warnings=["guard spec unavailable; workspace guard skipped"],
                details={"available": False},
            )
        spec = self.spec
        assert spec is not None
        text, scanned_files = _collect_workspace_text(workspace_dirs)
        signature_report = _evaluate_semantic_signature(spec.semantic_signature, text)
        builtin_report = _evaluate_builtin_workspace_semantics(self.vuln_id, workspace_dirs)

        violations: List[str] = []
        if signature_report["errors"]:
            violations.extend(f"semantic signature mismatch: {item}" for item in signature_report["errors"])
        if builtin_report.get("supported") and not builtin_report.get("semantic_match"):
            violations.append(f"semantic mismatch: {semantic_error_summary(builtin_report)}")

        blocking = self.should_block() and bool(violations)
        passed = not blocking
        warnings: List[str] = []
        if violations and not self.should_block():
            warnings.extend(violations)
            violations = []
            passed = True
            blocking = False

        return GuardEvaluation(
            passed=passed,
            blocking=blocking,
            violations=violations,
            warnings=warnings,
            details={
                "available": True,
                "policy_snapshot": self.policy_snapshot,
                "scanned_files": scanned_files,
                "semantic_signature": signature_report,
                "builtin_semantics": builtin_report,
            },
        )

    def _evaluate_manifest_semantics(self, manifest: Dict[str, Any]) -> Dict[str, Any]:
        spec = self.spec
        if spec is None:
            return {"errors": [], "warnings": [], "signature": {}, "builtin": {}}
        text = _collect_manifest_text(manifest)
        signature_report = _evaluate_semantic_signature(spec.semantic_signature, text)
        builtin_report = evaluate_manifest_semantics(self.vuln_id, manifest)
        errors: List[str] = []
        warnings: List[str] = []
        scope = str(self.policy_snapshot.get("dynamic_scope") or "assertions_semantics").strip().lower()

        signature_errors = list(signature_report.get("errors") or [])
        # When builtin semantic evaluator already confirms a semantic match, do not
        # hard-fail on token-level signature misses in assertions_semantics mode.
        if (
            signature_errors
            and scope == "assertions_semantics"
            and builtin_report.get("supported")
            and builtin_report.get("semantic_match")
        ):
            warnings.extend(signature_errors)
        elif signature_errors:
            errors.extend(signature_errors)

        if scope in {"assertions_semantics", "full"} and builtin_report.get("supported") and not builtin_report.get(
            "semantic_match"
        ):
            errors.append(semantic_error_summary(builtin_report))
        return {
            "errors": errors,
            "warnings": warnings,
            "signature": signature_report,
            "builtin": builtin_report,
        }

    @staticmethod
    def _parse_spec(guard_spec: Optional[GuardSpec | Dict[str, Any]]) -> Optional[GuardSpec]:
        if guard_spec is None:
            return None
        if isinstance(guard_spec, GuardSpec):
            return guard_spec
        if not isinstance(guard_spec, dict):
            return None
        try:
            return parse_guard_spec(guard_spec)
        except Exception:
            return None


def _collect_manifest_text(manifest: Dict[str, Any]) -> str:
    body = manifest.get("manifest") if isinstance(manifest.get("manifest"), dict) else manifest
    files = body.get("files") if isinstance(body, dict) else []
    if not isinstance(files, list):
        return ""
    chunks: List[str] = []
    for entry in files:
        if not isinstance(entry, dict):
            continue
        content = entry.get("content")
        if isinstance(content, str) and content:
            chunks.append(content)
    notes = body.get("notes")
    if isinstance(notes, str) and notes.strip():
        chunks.append(notes)
    return "\n".join(chunks)


def _collect_workspace_text(workspace_dirs: Sequence[Path]) -> Tuple[str, int]:
    chunks: List[str] = []
    count = 0
    for root in workspace_dirs:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            try:
                rel = path.relative_to(root)
            except ValueError:
                rel = path
            if not is_service_side_workspace_path(rel):
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except Exception:
                continue
            count += 1
            chunks.append(content)
    return "\n".join(chunks), count


def _evaluate_builtin_workspace_semantics(vuln_id: str, workspace_dirs: Sequence[Path]) -> Dict[str, Any]:
    # Use the first existing workspace for the built-in semantic helper.
    for root in workspace_dirs:
        if root.exists() and root.is_dir():
            return evaluate_workspace_semantics(vuln_id, root)
    return {
        "supported": False,
        "semantic_match": True,
        "errors": [],
        "signals": {},
        "vuln_id": normalize_vuln_id(vuln_id),
        "scanned_files": 0,
    }


def _evaluate_semantic_signature(signature: Dict[str, List[str]], text: str) -> Dict[str, Any]:
    lowered_text = (text or "").lower()
    errors: List[str] = []
    bucket_signals: Dict[str, Dict[str, Any]] = {}
    for bucket in ("input_vector", "sink", "exploit_precondition"):
        terms = signature.get(bucket) if isinstance(signature, dict) else []
        if not isinstance(terms, list):
            terms = []
        normalized_terms = [str(term).strip() for term in terms if isinstance(term, str) and term.strip()]
        if not normalized_terms:
            bucket_signals[bucket] = {"required": [], "matched": []}
            continue
        matched = [term for term in normalized_terms if _semantic_token_present(lowered_text, term.lower())]
        bucket_signals[bucket] = {"required": normalized_terms, "matched": matched}
        if not matched:
            errors.append(f"{bucket} terms were not observed in generated artifacts")
    return {
        "semantic_match": not errors,
        "errors": errors,
        "signals": bucket_signals,
    }


def _semantic_token_present(text: str, token: str) -> bool:
    token = (token or "").strip().lower()
    if not token:
        return False
    if _semantic_token_alias_present(text, token):
        return True
    if token in text:
        return True
    words = [part for part in re.split(r"[^a-z0-9]+", token) if part]
    if not words:
        return False
    return all(word in text for word in words)


def _semantic_token_alias_present(text: str, token: str) -> bool:
    if "user-controlled request parameter" in token or token in {"request parameter", "query parameter"}:
        aliases = [
            "request.args",
            "request.form",
            "request.values",
            "request.json",
            "get_json(",
            "query parameter",
            "get parameter",
            "params={",
            "params =",
        ]
        return any(alias in text for alias in aliases)
    if token in {"path parameter", "filename"} or "filename/path" in token:
        aliases = [
            "request.args",
            "request.form",
            "filename",
            "filepath",
            "path =",
            "file =",
        ]
        return any(alias in text for alias in aliases)
    if "sql query execution" in token or token in {"sql sink", "cursor.execute"}:
        aliases = [
            "cursor.execute",
            "execute(",
            "executescript(",
            "sqlite3.connect",
            "select ",
        ]
        return any(alias in text for alias in aliases)
    if ("concatenated" in token or "string concatenation" in token or "interpolated" in token) and "sql" in token:
        return _looks_like_sql_string_composition(text)
    if "cross-site request" in token:
        return any(alias in text for alias in ["csrf", "@app.post", "methods=['post", 'methods=["post', "fetch(", "xmlhttprequest"])
    if "state-changing endpoint" in token:
        return any(alias in text for alias in ["@app.post", "@app.put", "@app.delete", "@app.patch", "methods=['post", 'methods=["post'])
    if "cookie-authenticated session" in token:
        return any(alias in text for alias in ["session", "cookie", "login_required", "set-cookie"])
    if token in {"open(", "send_file", "send_from_directory"} or "filesystem read" in token:
        aliases = [
            "open(",
            "send_file",
            "send_from_directory",
            "read_text(",
            "read_bytes(",
        ]
        return any(alias in text for alias in aliases)
    if token in {"../", "os.path.join", "path traversal"} or "confinement" in token:
        aliases = [
            "../",
            "..\\",
            "/etc/passwd",
            "os.path.join",
            "pathlib.path",
            "path traversal",
        ]
        return any(alias in text for alias in aliases)
    if token in {"url parameter", "user-controlled url"}:
        aliases = [
            "request.args",
            "request.form",
            "url =",
            "target_url",
            "target =",
        ]
        return any(alias in text for alias in aliases)
    if token in {"redirect target", "next parameter", "return_to parameter", "redirect url"}:
        aliases = [
            "request.args.get('next'",
            'request.args.get("next"',
            "request.args.get('url'",
            'request.args.get("url"',
            "request.args.get('target'",
            'request.args.get("target"',
            "next_url",
            "redirect_url",
            "target_url",
        ]
        return any(alias in text for alias in aliases)
    if token in {"redirect(", "location header", "http redirect sink", "redirect response"}:
        aliases = [
            "redirect(",
            "flask.redirect",
            "response.headers['location']",
            'response.headers["location"]',
            "location header",
            "302",
            "303",
        ]
        return any(alias in text for alias in aliases)
    if token in {"requests.get", "urllib.request", "http client request"} or "server-side request forgery" in token:
        aliases = [
            "requests.get",
            "requests.post",
            "urllib.request",
            "urlopen(",
            "server-side request forgery",
        ]
        return any(alias in text for alias in aliases)
    if "open redirect" in token or "unvalidated redirect" in token or "external redirect" in token:
        aliases = [
            "open redirect",
            "unvalidated redirect",
            "external redirect",
            "redirect(",
            "next_url",
            "redirect_url",
            "target_url",
            "location header",
        ]
        return any(alias in text for alias in aliases)
    if token in {"subprocess", "os.system", "shell=true"} or "command injection" in token:
        aliases = [
            "subprocess",
            "os.system",
            "shell=true",
            "shell = true",
            "popen(",
        ]
        return any(alias in text for alias in aliases)
    if token in {"code parameter"}:
        aliases = [
            "request.args.get('code'",
            'request.args.get("code"',
            "code = request.args.get(",
            "code: str = query(",
            "code:str=query(",
        ]
        return any(alias in text for alias in aliases)
    if token in {"eval(", "exec("} or "code injection" in token:
        return any(alias in text for alias in ["eval(", "exec(", "compile("])
    if "user input reaches eval" in token:
        return _looks_like_code_exec_flow(text)
    if token in {"render_template_string", "template response", "innerhtml"} or "cross-site scripting" in token:
        aliases = [
            "render_template_string",
            "<script>",
            "innerhtml",
            "markup(",
            "template response",
        ]
        return any(alias in text for alias in aliases)
    if "template source string" in token or ("concatenation" in token and "template" in token):
        template_source_aliases = [
            "render_template_string(",
            "template = f",
            "template=f",
            "template_source = f",
            "template_source=f",
            ".format(",
            "{name}",
            "{payload}",
            "+ name",
            "+ payload",
            "+ user_input",
            "+ request.args",
        ]
        return "render_template_string" in text and any(alias in text for alias in template_source_aliases)
    if "without escaping/sandboxing" in token or ("sandbox" in token and "template" in token):
        aliases = [
            "render_template_string",
            "jinja2.from_string",
            "template.render(",
        ]
        return any(alias in text for alias in aliases)
    if token in {"request.data", "request.get_data", "serialized payload"}:
        aliases = [
            "request.data",
            "request.get_data",
            "request.json",
            "payload =",
            "serialized",
        ]
        return any(alias in text for alias in aliases)
    if token in {"pickle.loads", "yaml.load", "jsonpickle.decode"} or "deserialization" in token:
        aliases = [
            "pickle.loads",
            "yaml.load",
            "jsonpickle.decode",
            "deserialize",
        ]
        return any(alias in text for alias in aliases)
    if token in {"ldap user parameter", "user-controlled directory lookup input"}:
        aliases = [
            "request.args.get('user'",
            'request.args.get("user"',
            "user = request.args.get(",
            "user: str = query(",
            "user:str=query(",
        ]
        return any(alias in text for alias in aliases)
    if token in {"ldap filter construction"}:
        return "ldap_filter" in text or _looks_like_ldap_filter_composition(text)
    if token in {"directory search"}:
        return any(alias in text for alias in ["search_directory(", "ldap_search(", "conn.search("])
    if "user input concatenated into ldap filter" in token:
        return _looks_like_ldap_filter_composition(text)
    if "ldap injection" in token:
        return _looks_like_ldap_filter_composition(text) and any(
            alias in text for alias in ["search_directory(", "ldap_search(", "conn.search("]
        )
    if "filter bypass via wildcard or or clause" in token:
        aliases = [
            "'*' in ldap_filter",
            "\"*\" in ldap_filter",
            "'|' in ldap_filter",
            "\"|\" in ldap_filter",
            "uid=*)",
            ")(|",
        ]
        return any(alias in text for alias in aliases)
    return False


def _looks_like_code_exec_flow(text: str) -> bool:
    has_code_input = any(
        alias in text
        for alias in [
            "request.args.get('code'",
            'request.args.get("code"',
            "code = request.args.get(",
            "code: str = query(",
            "code:str=query(",
        ]
    )
    has_exec_sink = bool(re.search(r"(eval|exec)\s*\(\s*code\b", text, flags=re.IGNORECASE))
    return has_code_input and has_exec_sink


def _looks_like_ldap_filter_composition(text: str) -> bool:
    return bool(
        re.search(
            r"ldap_filter\s*=\s*[^\n]*(?:\+\s*user\b|\buser\b\s*\+)",
            text,
            flags=re.IGNORECASE,
        )
    )


def _looks_like_sql_string_composition(text: str) -> bool:
    patterns = [
        r"select[\s\S]{0,160}\+\s*[a-z_][a-z0-9_]*",
        r"(select|insert|update|delete)[\s\S]{0,160}\.format\s*\(",
        r"f[\"'][^\"']*(select|insert|update|delete)[^\"']*[\"']",
    ]
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _evaluate_generator_assertion(manifest: Dict[str, Any], assertion: Dict[str, Any]) -> Tuple[bool, str]:
    op = _normalize_generator_assertion_op(str(assertion.get("op") or "").strip().lower())
    files = _manifest_files(manifest)
    deps = _manifest_deps(manifest)
    if op == "file_exists":
        path = str(assertion.get("path") or "").strip()
        if not path:
            return False, "file_exists requires path"
        for entry in files:
            if entry["path"] == path:
                return True, f"file exists: {path}"
        return False, f"missing file: {path}"
    if op == "role_exists":
        role = normalize_role(assertion.get("role"))
        if not role:
            return False, "role_exists requires role"
        if any(role_matches(entry["role"], role) for entry in files):
            return True, f"role exists: {role}"
        return False, f"missing role: {role}"
    if op in {"file_contains", "file_not_contains"}:
        path = str(assertion.get("path") or "").strip()
        needle = str(assertion.get("string") or assertion.get("contains") or assertion.get("needle") or "").strip()
        if not path or not needle:
            return False, f"{op} requires path and string"
        target = next((entry for entry in files if entry["path"] == path), None)
        if target is None:
            return False, f"{op}: missing file {path}"
        hit = needle in (target["content"] or "")
        if op == "file_contains":
            return hit, f"{path} contains '{needle}'" if hit else f"{path} missing '{needle}'"
        return (not hit), f"{path} does not contain '{needle}'" if not hit else f"{path} unexpectedly contains '{needle}'"
    if op in {"file_regex_contains", "file_regex_not_contains"}:
        path = str(assertion.get("path") or "").strip()
        pattern = str(assertion.get("regex") or assertion.get("pattern") or "").strip()
        if not path or not pattern:
            return False, f"{op} requires path and regex"
        target = next((entry for entry in files if entry["path"] == path), None)
        if target is None:
            return False, f"{op}: missing file {path}"
        regex, err = _compile_regex(pattern, assertion.get("flags"))
        if regex is None:
            return False, err
        hit = bool(regex.search(target["content"] or ""))
        if op == "file_regex_contains":
            return hit, f"{path} matches /{pattern}/" if hit else f"{path} missing regex /{pattern}/"
        return (not hit), f"{path} does not match /{pattern}/" if not hit else f"{path} unexpectedly matches /{pattern}/"
    if op == "file_regex_any":
        globs = assertion.get("globs") or assertion.get("paths") or assertion.get("glob")
        pattern = str(assertion.get("regex") or assertion.get("pattern") or "").strip()
        if isinstance(globs, str):
            globs = [globs]
        if not isinstance(globs, list) or not pattern:
            return False, "file_regex_any requires globs[] and regex"
        normalized_globs = [str(item).strip() for item in globs if isinstance(item, str) and str(item).strip()]
        if not normalized_globs:
            return False, "file_regex_any requires non-empty globs[]"
        regex, err = _compile_regex(pattern, assertion.get("flags"))
        if regex is None:
            return False, err
        matched_paths: List[str] = []
        for entry in files:
            rel = entry["path"]
            if any(_glob_matches(rel, glob) for glob in normalized_globs):
                if regex.search(entry["content"] or ""):
                    matched_paths.append(rel)
        if matched_paths:
            return True, f"regex /{pattern}/ matched file(s): {', '.join(sorted(matched_paths)[:3])}"
        return False, f"regex /{pattern}/ not found under globs: {', '.join(normalized_globs)}"
    if op == "dep_declared":
        dep = str(assertion.get("dep") or assertion.get("name") or assertion.get("package") or "").strip().lower()
        if not dep:
            return False, "dep_declared requires dep"
        if dep in deps:
            return True, f"dep declared: {dep}"
        return False, f"missing dep declaration: {dep}"
    if op == "any_dep_declared":
        candidates = assertion.get("deps")
        if candidates is None:
            candidates = assertion.get("names")
        if candidates is None:
            candidates = assertion.get("packages")
        if isinstance(candidates, str):
            candidates = [candidates]
        if not isinstance(candidates, list):
            return False, "any_dep_declared requires deps[]"
        normalized = [str(item).strip().lower() for item in candidates if isinstance(item, str) and item.strip()]
        if not normalized:
            return False, "any_dep_declared requires non-empty deps[]"
        hit = next((dep for dep in normalized if dep in deps), None)
        if hit:
            return True, f"one of deps declared: {hit}"
        return False, f"none of deps declared: {', '.join(normalized)}"
    if op == "pattern_tag_present":
        tag = str(assertion.get("tag") or "").strip().lower()
        tags = assertion.get("tags")
        manifest_tags = _manifest_pattern_tags(manifest)
        if tag:
            hit = tag in manifest_tags
            return hit, f"pattern tag '{tag}' present" if hit else f"missing pattern tag '{tag}'"
        if isinstance(tags, list):
            normalized = [str(item).strip().lower() for item in tags if isinstance(item, str) and item.strip()]
            for candidate in normalized:
                if candidate in manifest_tags:
                    return True, f"pattern tag '{candidate}' present"
            return False, f"none of pattern tags present: {', '.join(normalized)}"
        return False, "pattern_tag_present requires tag or tags"
    if op in {"manifest_field_equals", "manifest_field_contains"}:
        pointer = str(assertion.get("field") or "").strip()
        if not pointer:
            return False, f"{op} requires field"
        value = _resolve_field(manifest, pointer)
        if op == "manifest_field_equals":
            expected = assertion.get("value")
            ok = value == expected
            return ok, f"{pointer} == {expected!r}" if ok else f"{pointer} expected {expected!r}, got {value!r}"
        needle = str(assertion.get("string") or "").strip()
        if not needle:
            return False, "manifest_field_contains requires string"
        haystack = str(value or "")
        ok = needle in haystack
        return ok, f"{pointer} contains '{needle}'" if ok else f"{pointer} missing '{needle}'"
    return False, f"unsupported guard assertion op: {op or 'unknown'}"


def _manifest_files(manifest: Dict[str, Any]) -> List[Dict[str, str]]:
    body = manifest.get("manifest") if isinstance(manifest.get("manifest"), dict) else manifest
    files = body.get("files") if isinstance(body, dict) else []
    output: List[Dict[str, str]] = []
    if not isinstance(files, list):
        return output
    for entry in files:
        if not isinstance(entry, dict):
            continue
        path = str(entry.get("path") or "").strip()
        if not path:
            continue
        output.append(
            {
                "path": path,
                "role": normalize_role(entry.get("role")),
                "content": str(entry.get("content") or ""),
            }
        )
    return output


def _normalize_generator_assertion_op(op: str) -> str:
    if op == "file_contains_regex":
        return "file_regex_contains"
    if op == "not_file_contains_regex":
        return "file_regex_not_contains"
    if op == "regex_any_file":
        return "file_regex_any"
    return op


def _normalize_verifier_assertion(assertion: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(assertion)
    op = str(normalized.get("op") or "").strip().lower()
    if op == "stdout_contains":
        normalized["op"] = "contains"
    else:
        normalized["op"] = op
    return normalized


def _compile_regex(pattern: str, flags_value: Any) -> Tuple[Optional[re.Pattern[str]], str]:
    flags = _regex_flags_from_value(flags_value)
    try:
        return re.compile(pattern, flags), ""
    except re.error as exc:
        return None, f"invalid regex '{pattern}': {exc}"


def _regex_flags_from_value(value: Any) -> int:
    if value is None:
        return 0
    tokens: List[str]
    if isinstance(value, str):
        tokens = [value]
    elif isinstance(value, list):
        tokens = [str(item) for item in value]
    else:
        return 0
    merged = "".join(token.strip().lower() for token in tokens if token)
    flags = 0
    if "i" in merged:
        flags |= re.IGNORECASE
    if "m" in merged:
        flags |= re.MULTILINE
    if "s" in merged:
        flags |= re.DOTALL
    if "x" in merged:
        flags |= re.VERBOSE
    return flags


def _glob_matches(path: str, pattern: str) -> bool:
    normalized_path = str(path or "").strip()
    normalized_pattern = str(pattern or "").strip()
    if not normalized_path or not normalized_pattern:
        return False
    candidates = [normalized_pattern]
    if normalized_pattern.startswith("**/"):
        trimmed = normalized_pattern[3:]
        if trimmed:
            candidates.append(trimmed)
    return any(fnmatch.fnmatch(normalized_path, candidate) for candidate in candidates)


def _manifest_deps(manifest: Dict[str, Any]) -> set[str]:
    body = manifest.get("manifest") if isinstance(manifest.get("manifest"), dict) else manifest
    deps = body.get("deps") if isinstance(body, dict) else []
    result: set[str] = set()
    if isinstance(deps, list):
        for dep in deps:
            if not isinstance(dep, str):
                continue
            token = dep.strip().lower()
            if not token:
                continue
            result.add(token.split("==")[0].strip())
            result.add(token)

    files = body.get("files") if isinstance(body, dict) else []
    if isinstance(files, list):
        for entry in files:
            if not isinstance(entry, dict):
                continue
            path = str(entry.get("path") or "").strip().lower()
            if not path or not path.startswith("requirements") or not path.endswith(".txt"):
                continue
            content = str(entry.get("content") or "")
            for line in content.splitlines():
                token = line.split("#", 1)[0].strip().lower()
                if not token:
                    continue
                result.add(re.split(r"[<>=!~\[\]\s]+", token, maxsplit=1)[0])
                result.add(token)
    return result


def _manifest_pattern_tags(manifest: Dict[str, Any]) -> set[str]:
    body = manifest.get("manifest") if isinstance(manifest.get("manifest"), dict) else manifest
    tags = body.get("pattern_tags") if isinstance(body, dict) else []
    result: set[str] = set()
    if not isinstance(tags, list):
        return result
    for tag in tags:
        if isinstance(tag, str) and tag.strip():
            result.add(tag.strip().lower())
    return result


def _resolve_field(payload: Dict[str, Any], field: str) -> Any:
    current: Any = payload.get("manifest") if isinstance(payload.get("manifest"), dict) else payload
    for token in field.split("."):
        token = token.strip()
        if not token:
            continue
        if isinstance(current, dict):
            current = current.get(token)
            continue
        if isinstance(current, list):
            try:
                index = int(token)
            except Exception:
                return None
            if index < 0 or index >= len(current):
                return None
            current = current[index]
            continue
        return None
    return current


__all__ = ["GuardEngine", "GuardEvaluation"]
