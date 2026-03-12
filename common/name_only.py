"""Shared helpers for name-only execution posture and evaluation."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


VALID_NAME_ONLY_MODES = {"compatibility", "dynamic", "strict_dynamic"}


def is_name_driven_requirement(requirement: Any) -> bool:
    if not isinstance(requirement, dict):
        return False
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
    dynamic_eval = bool(pol.get("dynamic_eval")) if isinstance(pol, dict) else False
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
            or bool(pol.get("require_researcher_evidence"))
            or researcher_policy == "remote_required"
        )
    )
    allow_degraded_fallback = bool(name_driven and effective_mode in {"dynamic", "dynamic_eval"})
    allow_lower_bound_recovery = bool(
        name_driven
        and effective_mode in {"dynamic", "dynamic_eval"}
        and bool(pol.get("dynamic_eval_allow_lower_bound_fallback"))
    )
    require_strict_open_world = bool(name_driven and effective_mode == "strict_dynamic")
    require_independent_verifier = require_strict_open_world
    require_live_llm = require_strict_open_world

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
