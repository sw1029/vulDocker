"""Shared helpers for name-only execution posture and evaluation."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


VALID_NAME_ONLY_MODES = {"compatibility", "dynamic", "strict_dynamic"}
_COMPATIBILITY_ALLOWED_CLOSURE_SOURCES = [
    "curated_lower_bound",
    "template_assisted",
    "trusted_dynamic",
    "strict_open_world_positive",
    "degraded_deterministic_fallback",
]
_DYNAMIC_ALLOWED_CLOSURE_SOURCES = [
    "trusted_dynamic",
    "strict_open_world_positive",
]
_STRICT_DYNAMIC_ALLOWED_CLOSURE_SOURCES = ["strict_open_world_positive"]
_COMPATIBILITY_ALLOWED_EXECUTION_PATHS = list(_COMPATIBILITY_ALLOWED_CLOSURE_SOURCES)
_DYNAMIC_ALLOWED_EXECUTION_PATHS = [
    "trusted_dynamic",
    "strict_open_world_positive",
    "degraded_deterministic_fallback",
]
_STRICT_DYNAMIC_ALLOWED_EXECUTION_PATHS = ["strict_open_world_positive"]


def is_name_driven_requirement(requirement: Any) -> bool:
    if not isinstance(requirement, dict):
        return False
    request_ir = requirement.get("request_ir")
    if isinstance(request_ir, dict) and request_ir.get("name_driven") is True:
        return True
    request_identity = requirement.get("request_identity")
    if isinstance(request_identity, dict) and request_identity.get("name_driven") is True:
        return True
    vuln_id = str(requirement.get("vuln_id") or "").strip().upper()
    return vuln_id.startswith("NAME-")


def name_only_mode(requirement_or_policy: Any) -> str:
    if not isinstance(requirement_or_policy, dict):
        return "compatibility"
    if isinstance(requirement_or_policy.get("policy"), dict):
        policy = requirement_or_policy.get("policy")
    else:
        policy = requirement_or_policy
    token = str((policy or {}).get("name_only_mode") or "").strip().lower()
    if token in VALID_NAME_ONLY_MODES:
        return token
    return "compatibility"


def _bool_setting(policy: Dict[str, Any], key: str) -> bool:
    value = policy.get(key)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def build_name_only_contract(
    *,
    requirement: Any,
    policy: Any = None,
) -> Dict[str, Any]:
    req = requirement if isinstance(requirement, dict) else {}
    pol = policy if isinstance(policy, dict) else (
        req.get("policy") if isinstance(req.get("policy"), dict) else {}
    )
    researcher = req.get("researcher") if isinstance(req.get("researcher"), dict) else {}
    name_driven = is_name_driven_requirement(req)
    mode = name_only_mode(pol)
    dynamic_eval = _bool_setting(pol, "dynamic_eval") if isinstance(pol, dict) else False
    effective_mode = mode
    if effective_mode == "compatibility" and dynamic_eval:
        effective_mode = "dynamic_eval"
    elif effective_mode not in {"dynamic", "strict_dynamic"}:
        effective_mode = "compatibility"

    require_research = bool(name_driven and effective_mode in {"dynamic", "dynamic_eval", "strict_dynamic"})
    researcher_policy = str(researcher.get("search_policy") or "").strip().lower()
    require_remote_research = bool(
        name_driven
        and (
            effective_mode == "strict_dynamic"
            or _bool_setting(pol, "require_researcher_evidence")
            or researcher_policy == "remote_required"
        )
    )
    allow_degraded_fallback = bool(name_driven and effective_mode in {"dynamic", "dynamic_eval"})
    allow_lower_bound_recovery = bool(
        name_driven
        and effective_mode in {"dynamic", "dynamic_eval"}
        and _bool_setting(pol, "dynamic_eval_allow_lower_bound_fallback")
    )
    require_strict_open_world = bool(name_driven and effective_mode == "strict_dynamic")
    require_independent_verifier = require_strict_open_world
    require_live_llm = require_strict_open_world
    if effective_mode == "compatibility":
        allowed_closure_sources = list(_COMPATIBILITY_ALLOWED_CLOSURE_SOURCES)
        allowed_execution_paths = list(_COMPATIBILITY_ALLOWED_EXECUTION_PATHS)
        intent_satisfying_paths = list(_COMPATIBILITY_ALLOWED_EXECUTION_PATHS)
        intent_success_rule = "any_non_failed_runnable_closure"
    elif effective_mode in {"dynamic", "dynamic_eval"}:
        allowed_closure_sources = list(_DYNAMIC_ALLOWED_CLOSURE_SOURCES)
        allowed_execution_paths = list(_DYNAMIC_ALLOWED_EXECUTION_PATHS)
        intent_satisfying_paths = list(_DYNAMIC_ALLOWED_CLOSURE_SOURCES)
        intent_success_rule = "open_world_positive_only"
    else:
        allowed_closure_sources = list(_STRICT_DYNAMIC_ALLOWED_CLOSURE_SOURCES)
        allowed_execution_paths = list(_STRICT_DYNAMIC_ALLOWED_EXECUTION_PATHS)
        intent_satisfying_paths = list(_STRICT_DYNAMIC_ALLOWED_EXECUTION_PATHS)
        intent_success_rule = "strict_open_world_positive_only"

    return {
        "enabled": bool(name_driven),
        "mode": mode,
        "effective_mode": effective_mode,
        "require_research": require_research,
        "require_remote_research": require_remote_research,
        "allow_degraded_fallback": allow_degraded_fallback,
        "allow_lower_bound_recovery": allow_lower_bound_recovery,
        "allow_curated_lower_bound_closure": bool(name_driven and effective_mode == "compatibility"),
        "allow_template_closure": bool(name_driven and effective_mode == "compatibility"),
        "require_strict_open_world": require_strict_open_world,
        "require_independent_verifier": require_independent_verifier,
        "require_live_llm": require_live_llm,
        "allow_stub_llm": not require_live_llm,
        "allow_fixture_llm": not require_live_llm,
        "allowed_closure_sources": allowed_closure_sources,
        "allowed_execution_paths": allowed_execution_paths,
        "intent_satisfying_paths": intent_satisfying_paths,
        "allowed_llm_paths": (
            ["live", "fixture", "stub"]
            if effective_mode == "compatibility"
            else ["live", "fixture", "stub"]
            if effective_mode in {"dynamic", "dynamic_eval"}
            else ["live"]
        ),
        "intent_success_rule": intent_success_rule,
    }


def with_name_only_contract(requirement: Any) -> Dict[str, Any]:
    req = deepcopy(requirement) if isinstance(requirement, dict) else {}
    policy = req.get("policy")
    if not isinstance(policy, dict):
        policy = {}
        req["policy"] = policy
    policy["name_only_contract"] = build_name_only_contract(requirement=req, policy=policy)
    return req


__all__ = [
    "VALID_NAME_ONLY_MODES",
    "build_name_only_contract",
    "is_name_driven_requirement",
    "name_only_mode",
    "with_name_only_contract",
]
