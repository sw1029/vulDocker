"""Requirement schema helpers for vuln_id/vuln_ids normalization."""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

RULES_ROOT = Path(__file__).resolve().parents[2] / "docs" / "evals" / "rules"
VALID_SEARCH_POLICIES = {"remote_required", "remote_prefer", "local_only"}
VALID_GUARD_ENFORCEMENTS = {"block_both", "block_unknown", "warn_only"}
VALID_GUARD_FAILURE_POLICIES = {"closed_unknown", "open_all", "closed_all"}
VALID_GUARD_DYNAMIC_SCOPES = {"assertions_semantics", "include_patterns", "full"}
VALID_GUARD_BUDGET_MODES = {"bundle_once", "per_candidate", "verifier_only", "bundle_ensemble"}
VALID_GUARD_AUTOFIX_LEVELS = {"none", "manifest", "code"}
VALID_GUARD_UNSUPPORTED_OP_POLICIES = {"normalize_retry", "fail", "warn"}
DEFAULT_GUARD_SEMANTIC_REFRESH_THRESHOLD = 2
DEFAULT_GUARD_FAILURE_FINGERPRINT_WINDOW = 3


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "on"}
    return bool(value)


def _coerce_identifier(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = value.strip()
    if not cleaned:
        return ""
    normalized = cleaned.replace(" ", "").upper()
    return normalized


def slugify_vuln_id(value: str) -> str:
    """Return workspace-safe slug for a vuln identifier."""

    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "vuln"


class RequirementValidationError(ValueError):
    """Raised when the requirement payload is missing mandatory fields."""


@dataclass
class RequirementNormalization:
    """Result of requirement normalization."""

    requirement: Dict[str, Any]
    requested_vuln_ids: List[str]
    effective_vuln_ids: List[str]
    multi_vuln: bool
    effective_vuln_ids_digest: str
    vuln_ids_digest: Optional[str]
    warnings: List[str]
    ignored_vuln_ids: List[str]
    bundles: List[Dict[str, str]]
    executor_policy: Dict[str, Any]


def normalize_requirement(
    requirement: Dict[str, Any],
    *,
    multi_vuln_opt_in: bool = False,
) -> RequirementNormalization:
    """Normalize vuln_id/vuln_ids fields and derive helper metadata."""

    normalized_req = deepcopy(requirement)
    requested = _extract_vuln_ids(normalized_req)
    if not requested:
        raise RequirementValidationError("At least one vuln_id or vuln_ids entry is required.")

    raw_multi = _as_bool(normalized_req.get("multi_vuln"))
    multi_vuln = bool((raw_multi or multi_vuln_opt_in) and len(requested) > 1)
    warnings: List[str] = []
    ignored: List[str] = []
    if not multi_vuln and len(requested) > 1:
        ignored = requested[1:]
        warnings.append(
            "multi_vuln disabled; ignoring additional vuln_ids: " + ", ".join(ignored)
        )
    effective = requested if multi_vuln else [requested[0]]
    normalized_req["vuln_id"] = effective[0]
    normalized_req["vuln_ids"] = effective
    normalized_req["multi_vuln"] = multi_vuln
    _normalize_research_policy(normalized_req, effective, warnings)
    _normalize_pipeline_policy(normalized_req, effective, warnings)

    serialized = "\n".join(sorted(effective))
    effective_vuln_ids_digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    vuln_ids_digest: Optional[str] = effective_vuln_ids_digest if multi_vuln else None

    bundles: List[Dict[str, str]] = []
    single_bundle = len(effective) == 1
    for vid in effective:
        slug = slugify_vuln_id(vid)
        workspace_subdir = "app" if single_bundle else f"app/{slug}"
        bundles.append(
            {
                "vuln_id": vid,
                "slug": slug,
                "workspace_subdir": workspace_subdir,
            }
        )

    return RequirementNormalization(
        requirement=normalized_req,
        requested_vuln_ids=requested,
        effective_vuln_ids=effective,
        multi_vuln=multi_vuln,
        effective_vuln_ids_digest=effective_vuln_ids_digest,
        vuln_ids_digest=vuln_ids_digest,
        warnings=warnings,
        ignored_vuln_ids=ignored,
        bundles=bundles,
        executor_policy=_normalize_executor_policy(normalized_req),
    )


def _extract_vuln_ids(requirement: Dict[str, Any]) -> List[str]:
    declared: List[str] = []
    seq = requirement.get("vuln_ids")
    if isinstance(seq, list):
        for entry in seq:
            identifier = _coerce_identifier(entry)
            if identifier and identifier not in declared:
                declared.append(identifier)
    primary = _coerce_identifier(
        requirement.get("vuln_id")
        or requirement.get("cwe_id")
        or requirement.get("cve_id")
    )
    if primary:
        if primary in declared:
            declared.remove(primary)
        declared.insert(0, primary)
    if not declared:
        return []
    return declared


def _normalize_executor_policy(requirement: Dict[str, Any]) -> Dict[str, Any]:
    policy = requirement.get("executor") or {}
    if not isinstance(policy, dict):
        policy = {}
    result = {
        "allow_network": bool(policy.get("allow_network", False)),
        "network_mode": str(policy.get("network_mode") or ("bridge" if policy.get("allow_network") else "none")),
        "network_name": str(policy.get("network_name") or "").strip() or None,
        "sidecars": [],
    }
    sidecars = policy.get("sidecars") or []
    if isinstance(sidecars, list):
        for entry in sidecars:
            if not isinstance(entry, dict):
                continue
            aliases: List[str] = []
            raw_aliases = entry.get("aliases") or []
            if isinstance(raw_aliases, list):
                for alias in raw_aliases:
                    if isinstance(alias, str) and alias.strip():
                        aliases.append(alias.strip())
            result["sidecars"].append(
                {
                    "name": entry.get("name", "sidecar"),
                    "type": entry.get("type"),
                    "image": entry.get("image"),
                    "env": entry.get("env") or {},
                    "ready_probe": entry.get("ready_probe") or {},
                    "network_mode": entry.get("network_mode") or result["network_mode"],
                    "aliases": aliases,
                }
            )
    if not result["sidecars"]:
        result["sidecars"] = []
    return result


def _normalized_rule_filename(vuln_id: str) -> str:
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


def _has_static_rule(vuln_id: str) -> bool:
    filename = _normalized_rule_filename(vuln_id)
    if not filename:
        return False
    return (RULES_ROOT / f"{filename}.yaml").exists()


def _normalize_research_policy(
    requirement: Dict[str, Any],
    effective_vuln_ids: List[str],
    warnings: List[str],
) -> None:
    researcher = requirement.get("researcher") or {}
    if not isinstance(researcher, dict):
        researcher = {}
    has_unknown = any(not _has_static_rule(vuln_id) for vuln_id in effective_vuln_ids)
    default_policy = "remote_required" if has_unknown else "remote_prefer"
    raw_policy = str(researcher.get("search_policy") or default_policy).strip().lower()
    if raw_policy not in VALID_SEARCH_POLICIES:
        warnings.append(
            "researcher.search_policy must be one of "
            f"{sorted(VALID_SEARCH_POLICIES)}; falling back to {default_policy}"
        )
        raw_policy = default_policy
    researcher["search_policy"] = raw_policy
    if "generate_candidate_templates" in researcher:
        researcher["generate_candidate_templates"] = _as_bool(researcher.get("generate_candidate_templates"))
    else:
        researcher["generate_candidate_templates"] = False
    requirement["researcher"] = researcher


def _normalize_pipeline_policy(
    requirement: Dict[str, Any],
    effective_vuln_ids: List[str],
    warnings: List[str],
) -> None:
    policy = requirement.get("policy") or {}
    if not isinstance(policy, dict):
        policy = {}
    has_unknown = any(not _has_static_rule(vuln_id) for vuln_id in effective_vuln_ids)
    policy["allow_runtime_rule_override_static"] = _as_bool(
        policy.get("allow_runtime_rule_override_static", False)
    )
    if "require_researcher_evidence" in policy:
        policy["require_researcher_evidence"] = _as_bool(policy.get("require_researcher_evidence"))
    else:
        policy["require_researcher_evidence"] = has_unknown
    _normalize_guard_policy(policy, has_unknown=has_unknown, warnings=warnings)
    requirement["policy"] = policy


def _normalize_guard_policy(
    policy: Dict[str, Any],
    *,
    has_unknown: bool,
    warnings: List[str],
) -> None:
    guard = policy.get("guard") or {}
    if not isinstance(guard, dict):
        guard = {}

    enforcement = str(guard.get("enforcement") or "block_both").strip().lower()
    if enforcement not in VALID_GUARD_ENFORCEMENTS:
        warnings.append(
            "policy.guard.enforcement must be one of "
            f"{sorted(VALID_GUARD_ENFORCEMENTS)}; falling back to block_both"
        )
        enforcement = "block_both"

    failure_policy = str(guard.get("failure_policy") or "closed_unknown").strip().lower()
    if failure_policy not in VALID_GUARD_FAILURE_POLICIES:
        warnings.append(
            "policy.guard.failure_policy must be one of "
            f"{sorted(VALID_GUARD_FAILURE_POLICIES)}; falling back to closed_unknown"
        )
        failure_policy = "closed_unknown"

    dynamic_scope = str(guard.get("dynamic_scope") or "assertions_semantics").strip().lower()
    if dynamic_scope not in VALID_GUARD_DYNAMIC_SCOPES:
        warnings.append(
            "policy.guard.dynamic_scope must be one of "
            f"{sorted(VALID_GUARD_DYNAMIC_SCOPES)}; falling back to assertions_semantics"
        )
        dynamic_scope = "assertions_semantics"

    call_budget = guard.get("call_budget") or {}
    if not isinstance(call_budget, dict):
        call_budget = {}
    budget_mode = str(call_budget.get("mode") or "bundle_once").strip().lower()
    if budget_mode not in VALID_GUARD_BUDGET_MODES:
        warnings.append(
            "policy.guard.call_budget.mode must be one of "
            f"{sorted(VALID_GUARD_BUDGET_MODES)}; falling back to bundle_once"
        )
        budget_mode = "bundle_once"
    try:
        ensemble_runs = int(call_budget.get("ensemble_runs", 3))
    except Exception:
        ensemble_runs = 3
    if ensemble_runs < 1:
        ensemble_runs = 1

    autofix = guard.get("autofix") or {}
    if not isinstance(autofix, dict):
        autofix = {}
    autofix_level = str(autofix.get("level") or "code").strip().lower()
    if autofix_level not in VALID_GUARD_AUTOFIX_LEVELS:
        warnings.append(
            "policy.guard.autofix.level must be one of "
            f"{sorted(VALID_GUARD_AUTOFIX_LEVELS)}; falling back to code"
        )
        autofix_level = "code"
    try:
        autofix_attempts = int(autofix.get("max_attempts", 1))
    except Exception:
        autofix_attempts = 1
    if autofix_attempts < 0:
        autofix_attempts = 0

    unsupported_op_policy = str(guard.get("unsupported_op_policy") or "normalize_retry").strip().lower()
    if unsupported_op_policy not in VALID_GUARD_UNSUPPORTED_OP_POLICIES:
        warnings.append(
            "policy.guard.unsupported_op_policy must be one of "
            f"{sorted(VALID_GUARD_UNSUPPORTED_OP_POLICIES)}; falling back to normalize_retry"
        )
        unsupported_op_policy = "normalize_retry"

    refresh_researcher = guard.get("refresh_researcher_on_guard_dsl_error")
    if refresh_researcher is None:
        refresh_researcher_on_guard_dsl_error = True
    else:
        refresh_researcher_on_guard_dsl_error = _as_bool(refresh_researcher)
    hint_payload_enabled = _as_bool(guard.get("hint_payload_enabled", True))
    try:
        semantic_refresh_threshold = int(
            guard.get("semantic_refresh_threshold", DEFAULT_GUARD_SEMANTIC_REFRESH_THRESHOLD)
        )
    except Exception:
        semantic_refresh_threshold = DEFAULT_GUARD_SEMANTIC_REFRESH_THRESHOLD
    if semantic_refresh_threshold < 1:
        warnings.append(
            "policy.guard.semantic_refresh_threshold must be >= 1; "
            f"falling back to {DEFAULT_GUARD_SEMANTIC_REFRESH_THRESHOLD}"
        )
        semantic_refresh_threshold = DEFAULT_GUARD_SEMANTIC_REFRESH_THRESHOLD
    try:
        failure_fingerprint_window = int(
            guard.get("failure_fingerprint_window", DEFAULT_GUARD_FAILURE_FINGERPRINT_WINDOW)
        )
    except Exception:
        failure_fingerprint_window = DEFAULT_GUARD_FAILURE_FINGERPRINT_WINDOW
    if failure_fingerprint_window < 1:
        warnings.append(
            "policy.guard.failure_fingerprint_window must be >= 1; "
            f"falling back to {DEFAULT_GUARD_FAILURE_FINGERPRINT_WINDOW}"
        )
        failure_fingerprint_window = DEFAULT_GUARD_FAILURE_FINGERPRINT_WINDOW

    # Unknown CWE runs default to closed validation and evidence-first behaviour.
    if has_unknown and failure_policy == "open_all":
        warnings.append(
            "policy.guard.failure_policy=open_all weakens unknown CWE safety; prefer closed_unknown or closed_all."
        )

    guard["enforcement"] = enforcement
    guard["failure_policy"] = failure_policy
    guard["dynamic_scope"] = dynamic_scope
    guard["call_budget"] = {
        "mode": budget_mode,
        "ensemble_runs": ensemble_runs,
    }
    guard["autofix"] = {
        "level": autofix_level,
        "max_attempts": autofix_attempts,
    }
    guard["unsupported_op_policy"] = unsupported_op_policy
    guard["refresh_researcher_on_guard_dsl_error"] = refresh_researcher_on_guard_dsl_error
    guard["semantic_refresh_threshold"] = semantic_refresh_threshold
    guard["hint_payload_enabled"] = hint_payload_enabled
    guard["failure_fingerprint_window"] = failure_fingerprint_window
    policy["guard"] = guard


__all__ = [
    "RequirementNormalization",
    "RequirementValidationError",
    "normalize_requirement",
    "slugify_vuln_id",
]
