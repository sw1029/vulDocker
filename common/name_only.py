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


def _normalized_closure_path_set(values: Any) -> set[str]:
    if not isinstance(values, list):
        return set()
    return {
        str(item).strip().lower()
        for item in values
        if isinstance(item, str) and str(item).strip()
    }


def closure_source_allowed_by_contract(contract: Any, closure_source: Any) -> bool:
    token = str(closure_source or "").strip().lower()
    if not token or not isinstance(contract, dict):
        return False
    return token in _normalized_closure_path_set(contract.get("allowed_execution_paths"))


def closure_source_satisfies_intent(contract: Any, closure_source: Any) -> bool:
    token = str(closure_source or "").strip().lower()
    if not token or not isinstance(contract, dict):
        return False
    return token in _normalized_closure_path_set(contract.get("intent_satisfying_paths"))


def resolve_name_only_closure_source(
    *,
    failure_stage: Any,
    generation_origin: Any,
    strict_counts_as_generalization: bool,
) -> str:
    failure_stage_token = str(failure_stage or "").strip().upper()
    generation_origin_token = str(generation_origin or "").strip().lower()
    if failure_stage_token in {"CAPABILITY_CHECK", "RESEARCH", "GENERATOR", "NAME_ONLY_GATE"}:
        return "failed"
    if generation_origin_token == "compiler_generated":
        return "curated_lower_bound"
    if generation_origin_token == "built_in_template":
        return "template_assisted"
    if generation_origin_token == "deterministic_fallback":
        return "degraded_deterministic_fallback"
    if generation_origin_token == "llm_manifest" and strict_counts_as_generalization:
        return "strict_open_world_positive"
    if generation_origin_token == "llm_manifest":
        return "trusted_dynamic"
    return generation_origin_token or "unknown"


def classify_name_only_intent(
    *,
    mode: Any,
    contract: Any,
    closure_source: Any,
    failure_stage: Any = "",
    dynamic_eval_status: Any = "",
    open_world_class: Any = "",
    strict_open_world_class: Any = "",
    strict_counts_as_generalization: bool = False,
) -> Dict[str, Any]:
    mode_token = str(mode or "").strip().lower() or "compatibility"
    closure_source_token = str(closure_source or "").strip().lower()
    failure_stage_token = str(failure_stage or "").strip().upper()
    dynamic_eval_status_token = str(dynamic_eval_status or "").strip().lower()
    open_world_class_token = str(open_world_class or "").strip().lower()
    strict_class_token = str(strict_open_world_class or "").strip().lower()
    allowed_by_execution_contract = closure_source_allowed_by_contract(contract, closure_source_token)
    satisfies_intent_contract = closure_source_satisfies_intent(contract, closure_source_token)

    status = "compatibility_lower_bound"
    meets_intent = False
    partial = False
    reason = ""

    if mode_token == "compatibility":
        if failure_stage_token:
            status = "compatibility_failed"
            reason = "compatibility lane failed before lower-bound completion"
        else:
            status = "compatibility_lower_bound"
            meets_intent = satisfies_intent_contract or closure_source_token == "curated_lower_bound"
            reason = "compatibility mode allows curated lower-bound/template-backed closure"
    elif mode_token in {"dynamic", "dynamic_eval"}:
        if strict_counts_as_generalization or open_world_class_token == "open_world_positive" or satisfies_intent_contract:
            status = "dynamic_success"
            meets_intent = True
            reason = "name-only dynamic lane closed without relying on degraded lower-bound recovery"
        elif dynamic_eval_status_token == "lower_bound_recovered" or closure_source_token == "curated_lower_bound":
            status = "lower_bound_recovered"
            reason = "dynamic lane fell back to an existing curated lower-bound path"
        elif allowed_by_execution_contract:
            status = "degraded_dynamic_success"
            partial = True
            reason = "dynamic lane remained runnable, but closure still relied on degraded deterministic fallback"
        else:
            status = "dynamic_failed"
            reason = "dynamic lane did not produce an acceptable runnable bundle"
    else:
        if strict_counts_as_generalization or satisfies_intent_contract:
            status = "strict_dynamic_success"
            meets_intent = True
            reason = "strict dynamic lane achieved strict open-world positive evidence"
        elif dynamic_eval_status_token == "degraded_success" or strict_class_token in {
            "strict_minimal_dynamic_fallback",
            "strict_semantic_guided_fallback",
        }:
            status = "strict_dynamic_rejected_degraded"
            reason = "strict dynamic lane produced only degraded deterministic fallback and does not meet intent"
        elif strict_class_token in {
            "strict_dynamic_generation_failed",
            "strict_dynamic_live_llm_required",
            "strict_dynamic_capability_unavailable",
        } or dynamic_eval_status_token == "dynamic_failed" or failure_stage_token:
            status = "strict_dynamic_failed"
            reason = "strict dynamic lane failed before acceptable materialization"
        else:
            status = "strict_dynamic_not_satisfied"
            reason = "strict dynamic lane did not reach strict open-world positive evidence"

    return {
        "status": status,
        "meets_intent": meets_intent,
        "partial": partial,
        "reason": reason,
        "allowed_by_execution_contract": allowed_by_execution_contract,
        "satisfies_intent_contract": satisfies_intent_contract,
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
    "classify_name_only_intent",
    "closure_source_allowed_by_contract",
    "closure_source_satisfies_intent",
    "is_name_driven_requirement",
    "name_only_mode",
    "resolve_name_only_closure_source",
    "with_name_only_contract",
]
