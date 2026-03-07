"""Type/validation helpers for dynamic GuardSpec payloads."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

SUPPORTED_SCHEMA_VERSION = "guard_spec@1.0"
VALID_CONFIDENCE = {"high", "medium", "low"}
VALID_ENFORCEMENTS = {"block_both", "block_unknown", "warn_only"}
VALID_FAILURE_POLICY = {"closed_unknown", "open_all", "closed_all"}
VALID_DYNAMIC_SCOPE = {"assertions_semantics", "include_patterns", "full"}
VALID_CALL_BUDGET_MODES = {"bundle_once", "per_candidate", "verifier_only", "bundle_ensemble"}
VALID_AUTOFIX_LEVELS = {"none", "manifest", "code"}
VALID_UNSUPPORTED_OP_POLICIES = {"normalize_retry", "fail", "warn"}
VALID_LOW_CONFIDENCE_UNKNOWN_POLICIES = {"warn", "guard_fallback", "fail_closed"}
VALID_ASSERTION_SEVERITY = {"block", "warn"}
VALID_ASSERTION_INTENT = {"semantic_anchor", "syntax_hint", "contract", "dependency"}
VALID_ASSERTION_STABILITY = {"high", "medium", "low"}
DEFAULT_SEMANTIC_REFRESH_THRESHOLD = 2
DEFAULT_FAILURE_FINGERPRINT_WINDOW = 3
BLOCKING_GENERATOR_ASSERTION_OPS = {
    "role_exists",
    "file_exists",
    "dep_declared",
    "any_dep_declared",
    "manifest_field_equals",
    "manifest_field_contains",
}
GENERATOR_REGEX_ASSERTION_OPS = {
    "file_regex_contains",
    "file_regex_not_contains",
    "file_regex_any",
}

GENERATOR_OP_ALIASES = {
    "file_contains_regex": "file_regex_contains",
    "not_file_contains_regex": "file_regex_not_contains",
    "regex_any_file": "file_regex_any",
}
VERIFIER_OP_ALIASES = {
    "stdout_contains": "contains",
}
SUPPORTED_GENERATOR_ASSERTION_OPS = {
    "file_exists",
    "role_exists",
    "file_contains",
    "file_not_contains",
    "file_regex_contains",
    "file_regex_not_contains",
    "file_regex_any",
    "dep_declared",
    "any_dep_declared",
    "pattern_tag_present",
    "manifest_field_equals",
    "manifest_field_contains",
}
SUPPORTED_VERIFIER_ASSERTION_OPS = {
    "regex_contains",
    "contains",
    "not_contains",
    "number_delta",
}


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


@dataclass(frozen=True)
class GuardSpec:
    schema_version: str
    sid: str
    vuln_id: str
    slug: str
    source: str
    policy_snapshot: Dict[str, Any]
    evidence_refs: List[Dict[str, Any]]
    semantic_signature: Dict[str, List[str]]
    generator_assertions: List[Dict[str, Any]]
    verifier_assertions: List[Dict[str, Any]]
    verifier_assertions_deferred: List[Dict[str, Any]]
    autofix_hints: List[Dict[str, Any]]
    normalization: Dict[str, Any]
    confidence: str
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "sid": self.sid,
            "vuln_id": self.vuln_id,
            "slug": self.slug,
            "source": self.source,
            "policy_snapshot": self.policy_snapshot,
            "evidence_refs": self.evidence_refs,
            "semantic_signature": self.semantic_signature,
            "generator_assertions": self.generator_assertions,
            "verifier_assertions": self.verifier_assertions,
            "verifier_assertions_deferred": self.verifier_assertions_deferred,
            "autofix_hints": self.autofix_hints,
            "normalization": self.normalization,
            "confidence": self.confidence,
            "created_at": self.created_at,
        }


def default_guard_policy_snapshot(raw: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    call_budget = raw.get("call_budget") if isinstance(raw.get("call_budget"), dict) else {}
    autofix = raw.get("autofix") if isinstance(raw.get("autofix"), dict) else {}

    enforcement = str(raw.get("enforcement") or "block_both").strip().lower()
    if enforcement not in VALID_ENFORCEMENTS:
        enforcement = "block_both"
    failure_policy = str(raw.get("failure_policy") or "closed_unknown").strip().lower()
    if failure_policy not in VALID_FAILURE_POLICY:
        failure_policy = "closed_unknown"
    dynamic_scope = str(raw.get("dynamic_scope") or "assertions_semantics").strip().lower()
    if dynamic_scope not in VALID_DYNAMIC_SCOPE:
        dynamic_scope = "assertions_semantics"
    budget_mode = str(call_budget.get("mode") or "bundle_once").strip().lower()
    if budget_mode not in VALID_CALL_BUDGET_MODES:
        budget_mode = "bundle_once"
    try:
        ensemble_runs = int(call_budget.get("ensemble_runs", 3))
    except Exception:
        ensemble_runs = 3
    if ensemble_runs < 1:
        ensemble_runs = 1
    autofix_level = str(autofix.get("level") or "code").strip().lower()
    if autofix_level not in VALID_AUTOFIX_LEVELS:
        autofix_level = "code"
    try:
        autofix_attempts = int(autofix.get("max_attempts", 1))
    except Exception:
        autofix_attempts = 1
    if autofix_attempts < 0:
        autofix_attempts = 0

    unsupported_op_policy = str(raw.get("unsupported_op_policy") or "normalize_retry").strip().lower()
    if unsupported_op_policy not in VALID_UNSUPPORTED_OP_POLICIES:
        unsupported_op_policy = "normalize_retry"
    low_confidence_unknown_policy = str(raw.get("low_confidence_unknown_policy") or "warn").strip().lower()
    if low_confidence_unknown_policy not in VALID_LOW_CONFIDENCE_UNKNOWN_POLICIES:
        low_confidence_unknown_policy = "warn"
    refresh_researcher = raw.get("refresh_researcher_on_guard_dsl_error")
    if refresh_researcher is None:
        refresh_researcher_on_guard_dsl_error = True
    else:
        refresh_researcher_on_guard_dsl_error = _as_bool(refresh_researcher)
    hint_payload_enabled = _as_bool(raw.get("hint_payload_enabled", True))
    try:
        semantic_refresh_threshold = int(raw.get("semantic_refresh_threshold", DEFAULT_SEMANTIC_REFRESH_THRESHOLD))
    except Exception:
        semantic_refresh_threshold = DEFAULT_SEMANTIC_REFRESH_THRESHOLD
    if semantic_refresh_threshold < 1:
        semantic_refresh_threshold = DEFAULT_SEMANTIC_REFRESH_THRESHOLD
    try:
        failure_fingerprint_window = int(
            raw.get("failure_fingerprint_window", DEFAULT_FAILURE_FINGERPRINT_WINDOW)
        )
    except Exception:
        failure_fingerprint_window = DEFAULT_FAILURE_FINGERPRINT_WINDOW
    if failure_fingerprint_window < 1:
        failure_fingerprint_window = DEFAULT_FAILURE_FINGERPRINT_WINDOW

    return {
        "enforcement": enforcement,
        "failure_policy": failure_policy,
        "dynamic_scope": dynamic_scope,
        "call_budget": {
            "mode": budget_mode,
            "ensemble_runs": ensemble_runs,
        },
        "autofix": {
            "level": autofix_level,
            "max_attempts": autofix_attempts,
        },
        "unsupported_op_policy": unsupported_op_policy,
        "low_confidence_unknown_policy": low_confidence_unknown_policy,
        "refresh_researcher_on_guard_dsl_error": refresh_researcher_on_guard_dsl_error,
        "semantic_refresh_threshold": semantic_refresh_threshold,
        "hint_payload_enabled": hint_payload_enabled,
        "failure_fingerprint_window": failure_fingerprint_window,
    }


def normalize_semantic_signature(raw: Any) -> Dict[str, List[str]]:
    result = {
        "input_vector": [],
        "sink": [],
        "exploit_precondition": [],
    }
    if not isinstance(raw, dict):
        return result
    for key in result:
        values = raw.get(key)
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list):
            continue
        normalized: List[str] = []
        for value in values:
            if not isinstance(value, str):
                continue
            token = value.strip()
            if token and token not in normalized:
                normalized.append(token)
        result[key] = normalized
    return result


def build_guard_spec(
    *,
    sid: str,
    vuln_id: str,
    slug: str,
    policy_snapshot: Optional[Dict[str, Any]] = None,
    evidence_refs: Optional[List[Dict[str, Any]]] = None,
    semantic_signature: Optional[Dict[str, Any]] = None,
    generator_assertions: Optional[List[Dict[str, Any]]] = None,
    verifier_assertions: Optional[List[Dict[str, Any]]] = None,
    verifier_assertions_deferred: Optional[List[Dict[str, Any]]] = None,
    autofix_hints: Optional[List[Dict[str, Any]]] = None,
    normalization: Optional[Dict[str, Any]] = None,
    confidence: str = "medium",
    source: str = "llm",
    created_at: Optional[str] = None,
) -> GuardSpec:
    confidence_norm = str(confidence or "medium").strip().lower()
    if confidence_norm not in VALID_CONFIDENCE:
        confidence_norm = "medium"
    created = created_at or datetime.now(timezone.utc).isoformat()
    spec = GuardSpec(
        schema_version=SUPPORTED_SCHEMA_VERSION,
        sid=str(sid or "").strip(),
        vuln_id=str(vuln_id or "").strip(),
        slug=str(slug or "").strip(),
        source=str(source or "llm").strip().lower(),
        policy_snapshot=default_guard_policy_snapshot(policy_snapshot),
        evidence_refs=_normalize_evidence_refs(evidence_refs or []),
        semantic_signature=normalize_semantic_signature(semantic_signature or {}),
        generator_assertions=_normalize_assertions(generator_assertions or [], scope="generator"),
        verifier_assertions=_normalize_assertions(verifier_assertions or [], scope="verifier"),
        verifier_assertions_deferred=_normalize_assertions(verifier_assertions_deferred or [], scope="verifier"),
        autofix_hints=_normalize_autofix_hints(autofix_hints or []),
        normalization=_normalize_normalization_block(normalization or {}),
        confidence=confidence_norm,
        created_at=created,
    )
    _validate_assertions(spec.generator_assertions, scope="generator")
    _validate_assertions(spec.verifier_assertions, scope="verifier")
    return spec


def parse_guard_spec(payload: Dict[str, Any]) -> GuardSpec:
    if not isinstance(payload, dict):
        raise ValueError("guard spec payload must be a JSON object")
    schema_version = str(payload.get("schema_version") or "").strip()
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported guard spec schema_version: {schema_version!r} (expected {SUPPORTED_SCHEMA_VERSION})"
        )
    sid = str(payload.get("sid") or "").strip()
    vuln_id = str(payload.get("vuln_id") or "").strip()
    slug = str(payload.get("slug") or "").strip()
    if not sid or not vuln_id:
        raise ValueError("guard spec requires sid and vuln_id")
    return build_guard_spec(
        sid=sid,
        vuln_id=vuln_id,
        slug=slug,
        policy_snapshot=payload.get("policy_snapshot"),
        evidence_refs=payload.get("evidence_refs"),
        semantic_signature=payload.get("semantic_signature"),
        generator_assertions=payload.get("generator_assertions"),
        verifier_assertions=payload.get("verifier_assertions"),
        verifier_assertions_deferred=payload.get("verifier_assertions_deferred"),
        autofix_hints=payload.get("autofix_hints"),
        normalization=payload.get("normalization"),
        confidence=str(payload.get("confidence") or "medium"),
        source=str(payload.get("source") or "llm"),
        created_at=str(payload.get("created_at") or ""),
    )


def enforce_generator_assertion_trust_boundary(assertion: Dict[str, Any]) -> List[str]:
    """Downgrade risky LLM-authored generator assertions to advisory checks."""

    if not isinstance(assertion, dict):
        return []
    op = str(assertion.get("op") or "").strip().lower()
    if not op:
        return []

    warnings: List[str] = []
    severity = str(assertion.get("severity") or "block").strip().lower()
    if severity not in VALID_ASSERTION_SEVERITY:
        severity = "block"
    assertion["severity"] = severity

    if op in GENERATOR_REGEX_ASSERTION_OPS:
        changed = False
        if assertion.get("severity") != "warn":
            assertion["severity"] = "warn"
            changed = True
        if assertion.get("intent") != "syntax_hint":
            assertion["intent"] = "syntax_hint"
            changed = True
        if assertion.get("stability") != "low":
            assertion["stability"] = "low"
            changed = True
        if changed:
            warnings.append(
                f"generator regex assertion {op} downgraded to warn/syntax_hint because regex checks are advisory"
            )
        return warnings

    if op not in BLOCKING_GENERATOR_ASSERTION_OPS and assertion.get("severity") == "block":
        assertion["severity"] = "warn"
        warnings.append(
            f"generator assertion {op} downgraded to warn because only structural/dependency assertions may block"
        )
    return warnings


def _normalize_evidence_refs(raw_refs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    refs: List[Dict[str, Any]] = []
    for item in raw_refs:
        if not isinstance(item, dict):
            continue
        normalized: Dict[str, Any] = {}
        for key in ("index", "query", "source", "url", "published", "retrieved_at", "snippet"):
            value = item.get(key)
            if value in (None, "", []):
                continue
            normalized[key] = value
        if normalized:
            refs.append(normalized)
    return refs


def _normalize_assertions(assertions: List[Dict[str, Any]], *, scope: str) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for assertion in assertions:
        if not isinstance(assertion, dict):
            continue
        op = _normalize_assertion_op(str(assertion.get("op") or "").strip().lower(), scope=scope)
        if not op:
            continue
        entry = _canonicalize_assertion_params(dict(assertion), op=op, scope=scope)
        entry["op"] = op
        severity = str(entry.get("severity") or "block").strip().lower()
        if severity not in VALID_ASSERTION_SEVERITY:
            severity = "block"
        intent = str(entry.get("intent") or "semantic_anchor").strip().lower()
        if intent not in VALID_ASSERTION_INTENT:
            intent = "semantic_anchor"
        stability = str(entry.get("stability") or "medium").strip().lower()
        if stability not in VALID_ASSERTION_STABILITY:
            stability = "medium"
        evidence_ids_raw = entry.get("evidence_ids")
        evidence_ids: List[int] = []
        if isinstance(evidence_ids_raw, list):
            for item in evidence_ids_raw:
                try:
                    evidence_ids.append(int(item))
                except Exception:
                    continue
        entry["severity"] = severity
        entry["intent"] = intent
        entry["stability"] = stability
        entry["evidence_ids"] = evidence_ids
        for key in [item for item in entry if str(item).startswith("_")]:
            entry.pop(key, None)
        normalized.append(entry)
    return normalized


def _normalize_assertion_op(op: str, *, scope: str) -> str:
    if scope == "generator":
        return GENERATOR_OP_ALIASES.get(op, op)
    return VERIFIER_OP_ALIASES.get(op, op)


def _canonicalize_assertion_params(assertion: Dict[str, Any], *, op: str, scope: str) -> Dict[str, Any]:
    entry = dict(assertion)

    def _move_value(target: str, aliases: List[str]) -> Any:
        value = entry.get(target)
        if value is not None:
            return value
        for alias in aliases:
            alias_value = entry.get(alias)
            if alias_value is not None:
                entry[target] = alias_value
                return alias_value
        return None

    if op == "dep_declared":
        value = _move_value("dep", ["name", "package"])
        if isinstance(value, str):
            entry["dep"] = value.strip()
        for alias in ("name", "package"):
            entry.pop(alias, None)
    elif op == "any_dep_declared":
        value = _move_value("deps", ["names", "packages"])
        if isinstance(value, str):
            value = [value]
        if isinstance(value, list):
            entry["deps"] = [str(item).strip() for item in value if isinstance(item, str) and str(item).strip()]
        for alias in ("names", "packages"):
            entry.pop(alias, None)
    elif op in {"file_contains", "file_not_contains"}:
        value = _move_value("string", ["contains", "needle"])
        if isinstance(value, str):
            entry["string"] = value.strip()
        for alias in ("contains", "needle"):
            entry.pop(alias, None)
    elif op in {"file_regex_contains", "file_regex_not_contains", "file_regex_any", "regex_contains"}:
        value = _move_value("regex", ["pattern"])
        if isinstance(value, str):
            entry["regex"] = value.strip()
        entry.pop("pattern", None)
        if op == "file_regex_any":
            globs = _move_value("globs", ["paths", "glob"])
            if globs is None and entry.get("path") is not None:
                globs = [entry.get("path")]
            if globs is None and isinstance(entry.get("patterns"), list):
                globs = ["*"]
            if isinstance(globs, str):
                globs = [globs]
            if isinstance(globs, list):
                entry["globs"] = [
                    str(item).strip()
                    for item in globs
                    if isinstance(item, str) and str(item).strip()
                ]
            patterns = entry.get("patterns")
            if (not entry.get("regex")) and isinstance(patterns, list):
                merged = _merge_regex_patterns(patterns)
                if merged:
                    entry["regex"] = merged
            for alias in ("paths", "glob", "patterns", "path"):
                entry.pop(alias, None)
    elif scope == "verifier" and op in {"contains", "not_contains"}:
        value = _move_value("string", ["contains", "needle"])
        if isinstance(value, str):
            entry["string"] = value.strip()
        for alias in ("contains", "needle"):
            entry.pop(alias, None)

    return entry


def _merge_regex_patterns(patterns: List[Any]) -> str:
    normalized = [str(item).strip() for item in patterns if isinstance(item, str) and str(item).strip()]
    if not normalized:
        return ""
    if len(normalized) == 1:
        return normalized[0]
    return "(?:" + ")|(?:".join(normalized) + ")"


def _validate_assertions(assertions: List[Dict[str, Any]], *, scope: str) -> None:
    supported = SUPPORTED_GENERATOR_ASSERTION_OPS if scope == "generator" else SUPPORTED_VERIFIER_ASSERTION_OPS
    for assertion in assertions:
        op = str(assertion.get("op") or "").strip().lower()
        if not op:
            raise ValueError(f"{scope} assertion missing op")
        if op not in supported:
            raise ValueError(f"unsupported {scope} assertion op: {op}")
        if op == "file_exists" and not _non_empty_string(assertion.get("path")):
            raise ValueError("file_exists requires path")
        if op == "role_exists" and not _non_empty_string(assertion.get("role")):
            raise ValueError("role_exists requires role")
        if op in {"file_contains", "file_not_contains"}:
            if not _non_empty_string(assertion.get("path")) or not _non_empty_string(assertion.get("string")):
                raise ValueError(f"{op} requires path and string")
        if op in {"file_regex_contains", "file_regex_not_contains"}:
            if not _non_empty_string(assertion.get("path")) or not _non_empty_string(assertion.get("regex")):
                raise ValueError(f"{op} requires path and regex")
        if op == "file_regex_any":
            if not _non_empty_string(assertion.get("regex")):
                raise ValueError("file_regex_any requires regex")
            globs = assertion.get("globs")
            if not isinstance(globs, list) or not any(_non_empty_string(item) for item in globs):
                raise ValueError("file_regex_any requires globs[]")
        if op == "dep_declared" and not _non_empty_string(assertion.get("dep")):
            raise ValueError("dep_declared requires dep")
        if op == "any_dep_declared":
            deps = assertion.get("deps")
            if not isinstance(deps, list) or not any(_non_empty_string(item) for item in deps):
                raise ValueError("any_dep_declared requires deps[]")
        if op == "manifest_field_equals" and not _non_empty_string(assertion.get("field")):
            raise ValueError("manifest_field_equals requires field")
        if op == "manifest_field_contains":
            if not _non_empty_string(assertion.get("field")) or not _non_empty_string(assertion.get("string")):
                raise ValueError("manifest_field_contains requires field and string")
        if op == "pattern_tag_present":
            has_tag = _non_empty_string(assertion.get("tag"))
            tags = assertion.get("tags")
            has_tags = isinstance(tags, list) and any(_non_empty_string(item) for item in tags)
            if not has_tag and not has_tags:
                raise ValueError("pattern_tag_present requires tag or tags")
        if op in {"contains", "not_contains"} and not _non_empty_string(assertion.get("string")):
            raise ValueError(f"{op} requires string")
        if op == "regex_contains" and not _non_empty_string(assertion.get("regex")):
            raise ValueError("regex_contains requires regex")


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _normalize_autofix_hints(hints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for hint in hints:
        if not isinstance(hint, dict):
            continue
        instruction = str(hint.get("instruction") or "").strip()
        if not instruction:
            continue
        entry = dict(hint)
        entry["instruction"] = instruction
        priority = entry.get("priority")
        try:
            entry["priority"] = int(priority) if priority is not None else 100
        except Exception:
            entry["priority"] = 100
        normalized.append(entry)
    normalized.sort(key=lambda item: int(item.get("priority", 100)))
    return normalized


def _normalize_normalization_block(raw: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {}

    mapped_ops: List[Dict[str, Any]] = []
    dropped_ops: List[Dict[str, Any]] = []
    warnings: List[str] = []
    schema_mismatches: List[str] = []

    for item in raw.get("mapped_ops") or []:
        if not isinstance(item, dict):
            continue
        src = str(item.get("from") or "").strip()
        dst = str(item.get("to") or "").strip()
        scope = str(item.get("scope") or "").strip()
        if src and dst:
            mapped_ops.append({"from": src, "to": dst, "scope": scope or "generator"})

    for item in raw.get("dropped_ops") or []:
        if not isinstance(item, dict):
            continue
        op = str(item.get("op") or "").strip()
        scope = str(item.get("scope") or "").strip()
        reason = str(item.get("reason") or "").strip()
        if op:
            dropped_ops.append({"op": op, "scope": scope or "generator", "reason": reason or "unsupported op"})

    for item in raw.get("warnings") or []:
        if isinstance(item, str) and item.strip():
            warnings.append(item.strip())
    for item in raw.get("schema_mismatches") or []:
        if isinstance(item, str) and item.strip():
            schema_mismatches.append(item.strip())

    return {
        "mapped_ops": mapped_ops,
        "dropped_ops": dropped_ops,
        "warnings": warnings,
        "schema_mismatches": schema_mismatches,
    }


__all__ = [
    "BLOCKING_GENERATOR_ASSERTION_OPS",
    "GENERATOR_OP_ALIASES",
    "GENERATOR_REGEX_ASSERTION_OPS",
    "GuardSpec",
    "SUPPORTED_GENERATOR_ASSERTION_OPS",
    "SUPPORTED_VERIFIER_ASSERTION_OPS",
    "SUPPORTED_SCHEMA_VERSION",
    "VALID_UNSUPPORTED_OP_POLICIES",
    "VERIFIER_OP_ALIASES",
    "build_guard_spec",
    "default_guard_policy_snapshot",
    "enforce_generator_assertion_trust_boundary",
    "normalize_semantic_signature",
    "parse_guard_spec",
]
