"""Requirement schema helpers for vuln_id/vuln_ids normalization."""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from common.contracts import can_resolve_without_remote_research_for_requirement
from common.name_only import VALID_NAME_ONLY_MODES, build_name_only_contract, is_name_driven_requirement
from common.vuln_catalog import (
    catalog_family_candidates_for_label,
    catalog_profile_defaults,
    mapped_vuln_id_with_source,
    normalize_vuln_label,
    resolve_vuln_catalog_entry,
)

RULES_ROOT = Path(__file__).resolve().parents[2] / "docs" / "evals" / "rules"
VALID_SEARCH_POLICIES = {"remote_required", "remote_prefer", "local_only"}
VALID_GUARD_ENFORCEMENTS = {"block_both", "block_unknown", "warn_only"}
VALID_GUARD_FAILURE_POLICIES = {"closed_unknown", "open_all", "closed_all"}
VALID_GUARD_DYNAMIC_SCOPES = {"assertions_semantics", "include_patterns", "full"}
VALID_GUARD_BUDGET_MODES = {"bundle_once", "per_candidate", "verifier_only", "bundle_ensemble"}
VALID_GUARD_AUTOFIX_LEVELS = {"none", "manifest", "code"}
VALID_GUARD_UNSUPPORTED_OP_POLICIES = {"normalize_retry", "fail", "warn"}
VALID_GUARD_LOW_CONFIDENCE_POLICIES = {"warn", "guard_fallback", "fail_closed"}
VALID_VERIFIER_LOW_TRUST_POLICIES = {"warn", "fail_closed"}
VALID_VERIFIER_PROMOTION_INDEPENDENCE = {"compiler_coupled", "independent"}
VALID_VERIFIER_NAME_RESOLUTION_CONFIDENCE = {"low", "medium", "high"}
AVAILABLE_STACK_HYPOTHESIS_POOL = (
    {
        "language": "python",
        "framework": "flask",
        "source": "available_skeleton",
        "confidence": "low",
    },
    {
        "language": "python",
        "framework": "fastapi",
        "source": "available_skeleton",
        "confidence": "low",
    },
)
DEFAULT_GUARD_SEMANTIC_REFRESH_THRESHOLD = 2
DEFAULT_GUARD_FAILURE_FINGERPRINT_WINDOW = 3
VALID_SEARCH_FILTER_KEYS = {"include_domains", "exclude_domains", "time_range", "country", "search_lang"}
DEFAULT_STACK_PROFILE = {
    "language": "python",
    "framework": "flask",
    "runtime": {
        "base_image": "python:3.11-slim",
        "package_manager": "pip",
        "allow_external_db": False,
    },
    "generator_mode": "synthesis",
    "seed": 1000,
    "retriever_commit": "stub",
    "corpus_snapshot": "rag-snap-mvp",
    "deps_digest": "sha256:auto",
    "base_image_digest": "sha256:python311",
    "dep_guard": {
        "llm_assist": True,
        "auto_patch": True,
    },
}
VULN_PROFILE_DEFAULTS = catalog_profile_defaults()


def _mapped_vuln_id_with_source(value: Any) -> tuple[str, str]:
    return mapped_vuln_id_with_source(value)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "on"}
    return bool(value)


def _coerce_identifier(value: Any) -> str:
    identifier, _source = _coerce_vuln_reference(value)
    return identifier


def _synthetic_name_vuln_id(value: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        return ""
    return f"NAME-{slugify_vuln_id(cleaned).upper()}"


def _looks_like_explicit_identifier(value: str) -> bool:
    cleaned = str(value or "").strip()
    if not cleaned:
        return False
    lowered = cleaned.lower()
    if lowered.startswith(("cwe", "cve", "name-")):
        return True
    if cleaned.isdigit():
        return True
    return False


def _coerce_vuln_reference(
    value: Any,
    *,
    allow_synthetic_name: bool = False,
) -> tuple[str, str]:
    if not isinstance(value, str):
        return "", ""
    cleaned = value.strip()
    if not cleaned:
        return "", ""
    mapped = _mapped_vuln_id(cleaned)
    if mapped:
        mapped_value, source = _mapped_vuln_id_with_source(cleaned)
        return mapped_value, source or "alias"
    if _looks_like_explicit_identifier(cleaned):
        return cleaned.replace(" ", "").replace("_", "-").upper(), "explicit_identifier"
    if allow_synthetic_name:
        synthetic = _synthetic_name_vuln_id(cleaned)
        if synthetic:
            return synthetic, "synthetic_name"
    if re.fullmatch(r"[A-Za-z0-9.-]+", cleaned):
        return cleaned.replace(" ", "").upper(), "explicit_identifier"
    return "", ""


def _mapped_vuln_id(value: Any) -> str:
    mapped, _source = _mapped_vuln_id_with_source(value)
    return mapped


def _named_vuln_label(requirement: Dict[str, Any]) -> str:
    for key in ("vuln_name", "vulnerability_name", "weakness_name", "cwe_name"):
        value = requirement.get(key)
        if not isinstance(value, str):
            continue
        cleaned = value.strip()
        if cleaned:
            return cleaned
    return ""


def _named_vuln_id(requirement: Dict[str, Any]) -> str:
    for key in ("vuln_name", "vulnerability_name", "weakness_name", "cwe_name"):
        identifier, _source = _coerce_vuln_reference(
            requirement.get(key),
            allow_synthetic_name=True,
        )
        if identifier:
            return identifier
    raw_name = _named_vuln_label(requirement)
    if raw_name:
        return _synthetic_name_vuln_id(raw_name)
    return ""


def slugify_vuln_id(value: str) -> str:
    """Return workspace-safe slug for a vuln identifier."""

    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "vuln"


def _name_resolution_match_class(source: str) -> str:
    token = str(source or "").strip().lower()
    if token in {"alias", "explicit_alias"}:
        return "catalog_alias"
    if token == "fragment_strategy_fallback":
        return "token_match"
    if token == "synthetic_name":
        return "synthetic_name"
    if token in {"explicit_identifier", "resolved_only"}:
        return "exact_identifier"
    return "unknown"


def _name_resolution_confidence(source: str) -> str:
    token = str(source or "").strip().lower()
    if token in {"alias", "explicit_alias", "explicit_identifier", "resolved_only"}:
        return "high"
    if token == "fragment_strategy_fallback":
        return "medium"
    if token == "synthetic_name":
        return "low"
    return "unknown"


def _decorate_name_resolution(payload: Dict[str, Any]) -> Dict[str, str]:
    source = str(payload.get("source") or "").strip()
    payload["match_class"] = _name_resolution_match_class(source)
    payload["confidence"] = _name_resolution_confidence(source)
    return {
        str(key): str(value)
        for key, value in payload.items()
        if isinstance(key, str) and key and value not in (None, "")
    }


def _request_identity_from_resolution(
    requirement: Dict[str, Any],
    resolution: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(resolution, dict):
        return {}
    raw_input = str(resolution.get("input") or "").strip()
    resolved_vuln_id = str(resolution.get("resolved_vuln_id") or "").strip()
    source = str(resolution.get("source") or "").strip().lower()
    match_class = str(resolution.get("match_class") or "").strip().lower()
    confidence = str(resolution.get("confidence") or "").strip().lower()
    field = str(resolution.get("field") or "").strip()
    if not raw_input or not resolved_vuln_id:
        return {}

    input_mode = "explicit_identifier"
    if field in {"vuln_name", "vulnerability_name", "weakness_name", "cwe_name"}:
        input_mode = "free_form_name"
    elif source == "synthetic_name":
        input_mode = "free_form_name"

    normalized_label = normalize_vuln_label(raw_input)
    return {
        "request_label": raw_input,
        "normalized_request_label": normalized_label,
        "resolved_vuln_id": resolved_vuln_id,
        "input_mode": input_mode,
        "source": source or "unknown",
        "match_class": match_class or "unknown",
        "confidence": confidence or "unknown",
        "field": field or None,
        "synthetic_resolution": source == "synthetic_name",
        "catalog_backed_resolution": match_class == "catalog_alias",
        "token_match_resolution": match_class == "token_match",
        "exact_identifier_resolution": match_class == "exact_identifier",
        "name_driven": input_mode == "free_form_name",
    }


def _resolution_state_from_request_identity(payload: Dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        return "unknown"
    source = str(payload.get("source") or "").strip().lower()
    match_class = str(payload.get("match_class") or "").strip().lower()
    if source == "synthetic_name":
        return "synthetic_name"
    if match_class == "catalog_alias":
        return "catalog_alias"
    if match_class == "token_match":
        return "token_match"
    if match_class == "exact_identifier":
        return "explicit_identifier"
    if source == "resolved_only":
        return "resolved_only"
    return "unknown"


def _stack_candidates_for_request_ir(requirement: Dict[str, Any]) -> List[Dict[str, str]]:
    candidates = _normalized_stack_hypotheses(requirement.get("stack_hypotheses"))
    if candidates:
        return candidates
    language = str(requirement.get("language") or "").strip().lower()
    framework = str(requirement.get("framework") or "").strip().lower()
    if not language or not framework:
        return []
    return [
        {
            "language": language,
            "framework": framework,
            "stack_id": f"{language}/{framework}",
            "source": "explicit_requirement",
            "confidence": "high",
        }
    ]


def _runtime_dependency_hypotheses_for_request_ir(requirement: Dict[str, Any]) -> List[Dict[str, str]]:
    runtime = requirement.get("runtime") if isinstance(requirement.get("runtime"), dict) else {}
    runtime = runtime if isinstance(runtime, dict) else {}
    db = str(
        runtime.get("db")
        or runtime.get("database")
        or requirement.get("db")
        or requirement.get("database")
        or ""
    ).strip().lower()
    if not db:
        return []
    confidence = "high" if db == "sqlite" else "medium"
    return [
        {
            "kind": "db",
            "value": db,
            "source": "request_runtime_db",
            "confidence": confidence,
        }
    ]


def _topology_hypotheses_for_request_ir(requirement: Dict[str, Any]) -> List[Dict[str, str]]:
    runtime = requirement.get("runtime") if isinstance(requirement.get("runtime"), dict) else {}
    runtime = runtime if isinstance(runtime, dict) else {}
    policy = requirement.get("policy") if isinstance(requirement.get("policy"), dict) else {}
    executor = policy.get("executor") if isinstance(policy.get("executor"), dict) else {}
    sidecars = executor.get("sidecars") if isinstance(executor.get("sidecars"), list) else []
    db = str(
        runtime.get("db")
        or runtime.get("database")
        or requirement.get("db")
        or requirement.get("database")
        or ""
    ).strip().lower()
    requires_sidecar = bool(sidecars) or db in {"mysql", "mariadb", "postgres", "postgresql"}
    topology = "service_plus_sidecar" if requires_sidecar else "single_service"
    confidence = "medium" if requires_sidecar else "high"
    return [{"topology": topology, "source": "request_runtime_hint", "confidence": confidence}]


def _scenario_candidates_for_request_ir(
    requirement: Dict[str, Any],
    *,
    family_candidates: List[Dict[str, str]],
    stack_candidates: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    if not isinstance(family_candidates, list) or not isinstance(stack_candidates, list):
        return []
    topologies = _topology_hypotheses_for_request_ir(requirement)
    dependency_set = [
        "service",
        *[
            f"{str(item.get('kind') or '').strip().lower()}:{str(item.get('value') or '').strip().lower()}"
            for item in _runtime_dependency_hypotheses_for_request_ir(requirement)
            if str(item.get("kind") or "").strip() and str(item.get("value") or "").strip()
        ],
    ]
    candidates: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for family in family_candidates[:3]:
        if not isinstance(family, dict):
            continue
        family_name = str(family.get("family") or "").strip().lower()
        if not family_name:
            continue
        for stack in stack_candidates[:3]:
            if not isinstance(stack, dict):
                continue
            stack_id = str(stack.get("stack_id") or "").strip().lower()
            if not stack_id:
                continue
            for topology in topologies[:2]:
                if not isinstance(topology, dict):
                    continue
                topology_name = str(topology.get("topology") or "").strip().lower()
                if not topology_name:
                    continue
                scenario_id = f"family={family_name}|stack={stack_id}|topology={topology_name}"
                if scenario_id in seen:
                    continue
                seen.add(scenario_id)
                candidates.append(
                    {
                        "scenario_id": scenario_id,
                        "family": family_name,
                        "stack_id": stack_id,
                        "topology": topology_name,
                        "dependency_set": list(dependency_set),
                        "oracle_profile": {
                            "mode": "contract_or_auto",
                            "negative_control_present": False,
                            "metamorphic_present": False,
                        },
                        "family_source": str(family.get("source") or "").strip().lower() or "unknown",
                        "stack_source": str(stack.get("source") or "").strip().lower() or "unknown",
                        "family_confidence": str(family.get("confidence") or "").strip().lower() or "unknown",
                        "stack_confidence": str(stack.get("confidence") or "").strip().lower() or "unknown",
                        "topology_source": str(topology.get("source") or "").strip().lower() or "unknown",
                        "topology_confidence": str(topology.get("confidence") or "").strip().lower() or "unknown",
                        "selected": False,
                    }
                )
    return candidates


def _family_candidates_for_request_ir(
    requirement: Dict[str, Any],
    *,
    resolved_vuln_id: str,
    request_label: str,
    resolution_state: str,
    resolution_confidence: str,
) -> List[Dict[str, str]]:
    candidates: List[Dict[str, str]] = []
    seen: set[str] = set()

    def add_candidate(family: Any, *, source: str, confidence: str, matched_vuln_id: str = "") -> None:
        token = str(family or "").strip().lower()
        if not token or token in seen:
            return
        seen.add(token)
        payload = {
            "family": token,
            "source": source,
            "confidence": confidence or "unknown",
        }
        if matched_vuln_id:
            payload["matched_vuln_id"] = matched_vuln_id
        candidates.append(payload)

    for candidate in catalog_family_candidates_for_label(
        request_label,
        resolved_vuln_id=resolved_vuln_id,
    ):
        if not isinstance(candidate, dict):
            continue
        add_candidate(
            candidate.get("family"),
            source=str(candidate.get("source") or "").strip().lower() or "catalog_resolution",
            confidence=str(candidate.get("confidence") or "").strip().lower()
            or resolution_confidence
            or ("high" if resolution_state in {"catalog_alias", "explicit_identifier"} else "medium"),
            matched_vuln_id=str(candidate.get("matched_vuln_id") or "").strip(),
        )
    return candidates


def _identifier_candidates_for_request_ir(
    requirement: Dict[str, Any],
    *,
    request_label: str,
    resolved_vuln_id: str,
    resolution_source: str,
    resolution_confidence: str,
) -> List[Dict[str, str]]:
    candidates: List[Dict[str, str]] = []
    seen: set[str] = set()

    def add_candidate(identifier: Any, *, source: str, confidence: str) -> None:
        token = str(identifier or "").strip().upper()
        if not token or token in seen:
            return
        seen.add(token)
        candidates.append(
            {
                "vuln_id": token,
                "source": source or "unknown",
                "confidence": confidence or "unknown",
            }
        )

    if resolved_vuln_id:
        add_candidate(
            resolved_vuln_id,
            source=resolution_source or "resolved_only",
            confidence=resolution_confidence or "unknown",
        )

    for key in ("vuln_id", "cwe_id", "cve_id", "vuln_name", "vulnerability_name", "weakness_name", "cwe_name"):
        raw = requirement.get(key)
        identifier, source = _coerce_vuln_reference(
            raw,
            allow_synthetic_name=key in {"vuln_id", "vuln_name", "vulnerability_name", "weakness_name", "cwe_name"},
        )
        if not identifier:
            continue
        add_candidate(
            identifier,
            source=source or f"input:{key}",
            confidence=_name_resolution_confidence(source or ""),
        )

    synthetic = _synthetic_name_vuln_id(request_label)
    if synthetic and synthetic != str(resolved_vuln_id or "").strip().upper():
        add_candidate(synthetic, source="synthetic_name_preview", confidence="low")

    return candidates


def _pattern_seed_state(requirement: Dict[str, Any], primary_vuln: str, resolution_source: str) -> str:
    pattern_id = str(requirement.get("pattern_id") or "").strip()
    if not pattern_id:
        return "absent"
    if pattern_id != "generic-web-vuln":
        return "preserved"
    if (
        not can_resolve_without_remote_research_for_requirement(primary_vuln, requirement)
        and str(resolution_source or "").strip().lower() in {"explicit_identifier", "synthetic_name", "resolved_only"}
    ):
        return "genericized_unknown"
    return "generic"


def _build_request_ir(
    requirement: Dict[str, Any],
    *,
    primary_vuln: str,
    request_identity: Dict[str, Any],
    name_resolution: Dict[str, Any],
) -> Dict[str, Any]:
    request_label = (
        str((request_identity or {}).get("request_label") or "").strip()
        or str((name_resolution or {}).get("input") or "").strip()
        or _named_vuln_label(requirement)
        or str(primary_vuln or "").strip()
    )
    normalized_request_label = normalize_vuln_label(request_label)
    resolved_vuln_id = str(
        (request_identity or {}).get("resolved_vuln_id")
        or (name_resolution or {}).get("resolved_vuln_id")
        or primary_vuln
        or ""
    ).strip()
    resolution_source = str(
        (request_identity or {}).get("source")
        or (name_resolution or {}).get("source")
        or ""
    ).strip().lower()
    resolution_match_class = str(
        (request_identity or {}).get("match_class")
        or (name_resolution or {}).get("match_class")
        or ""
    ).strip().lower()
    resolution_confidence = str(
        (request_identity or {}).get("confidence")
        or (name_resolution or {}).get("confidence")
        or ""
    ).strip().lower()
    name_driven = is_name_driven_requirement(
        {
            "vuln_id": resolved_vuln_id,
            "request_identity": request_identity if isinstance(request_identity, dict) else {},
        }
    )
    policy = requirement.get("policy") if isinstance(requirement.get("policy"), dict) else {}
    name_only_contract = (
        dict(policy.get("name_only_contract"))
        if isinstance(policy.get("name_only_contract"), dict)
        else build_name_only_contract(requirement=requirement, policy=policy)
    )
    resolution_state = _resolution_state_from_request_identity(
        {
            "source": resolution_source,
            "match_class": resolution_match_class,
        }
    )
    payload: Dict[str, Any] = {
        "raw_label": request_label,
        "request_label": request_label,
        "normalized_request_label": normalized_request_label,
        "resolved_vuln_id": resolved_vuln_id or None,
        "resolved_vuln_id_candidate": resolved_vuln_id or None,
        "input_mode": str((request_identity or {}).get("input_mode") or "").strip().lower() or "explicit_identifier",
        "name_driven": name_driven,
        "resolution_state": resolution_state,
        "resolution_source": resolution_source or "unknown",
        "resolution_match_class": resolution_match_class or "unknown",
        "resolution_confidence": resolution_confidence or "unknown",
        "identifier_candidates": _identifier_candidates_for_request_ir(
            requirement,
            request_label=request_label,
            resolved_vuln_id=resolved_vuln_id,
            resolution_source=resolution_source,
            resolution_confidence=resolution_confidence,
        ),
        "catalog_backed": bool((request_identity or {}).get("catalog_backed_resolution")),
        "token_match_backed": bool((request_identity or {}).get("token_match_resolution")),
        "synthetic_resolution": bool((request_identity or {}).get("synthetic_resolution")),
        "exact_identifier_resolution": bool((request_identity or {}).get("exact_identifier_resolution")),
        "pattern_id": str(requirement.get("pattern_id") or "").strip() or None,
        "pattern_seed_state": _pattern_seed_state(requirement, primary_vuln, resolution_source),
        "stack_candidates": _stack_candidates_for_request_ir(requirement),
        "family_candidates": _family_candidates_for_request_ir(
            requirement,
            resolved_vuln_id=resolved_vuln_id,
            request_label=request_label,
            resolution_state=resolution_state,
            resolution_confidence=resolution_confidence,
        ),
        "abstain_reason": None,
        "evidence_ids": [],
        "name_only_mode": str(name_only_contract.get("mode") or "compatibility"),
        "required_contract": {
            key: deepcopy(name_only_contract.get(key))
            for key in (
                "effective_mode",
                "require_research",
                "require_remote_research",
                "allow_degraded_fallback",
                "allow_lower_bound_recovery",
                "allow_curated_lower_bound_closure",
                "allow_template_closure",
                "require_strict_open_world",
                "require_independent_verifier",
                "require_live_llm",
                "allow_stub_llm",
                "allow_fixture_llm",
                "allowed_closure_sources",
                "allowed_execution_paths",
                "intent_satisfying_paths",
                "allowed_llm_paths",
                "intent_success_rule",
            )
            if key in name_only_contract
        },
    }
    payload["runtime_dependency_hypotheses"] = _runtime_dependency_hypotheses_for_request_ir(requirement)
    payload["topology_hypotheses"] = _topology_hypotheses_for_request_ir(requirement)
    payload["scenario_candidates"] = _scenario_candidates_for_request_ir(
        requirement,
        family_candidates=payload["family_candidates"],
        stack_candidates=payload["stack_candidates"],
    )
    return payload


def _name_resolution(requirement: Dict[str, Any], primary_vuln: str) -> Dict[str, Any]:
    for key in ("vuln_name", "vulnerability_name", "weakness_name", "cwe_name"):
        raw = requirement.get(key)
        if not isinstance(raw, str) or not raw.strip():
            continue
        mapped, source = _mapped_vuln_id_with_source(raw)
        if mapped:
            return _decorate_name_resolution({
                "field": key,
                "input": raw.strip(),
                "resolved_vuln_id": mapped,
                "source": source or "unknown",
            })
        synthetic = f"NAME-{slugify_vuln_id(raw).upper()}"
        return _decorate_name_resolution({
            "field": key,
            "input": raw.strip(),
            "resolved_vuln_id": synthetic,
            "source": "synthetic_name",
        })

    for key in ("vuln_id", "cwe_id", "cve_id"):
        raw = requirement.get(key)
        if not isinstance(raw, str) or not raw.strip():
            continue
        resolved, source = _coerce_vuln_reference(
            raw,
            allow_synthetic_name=(key == "vuln_id"),
        )
        resolved = resolved or str(primary_vuln or "").strip()
        resolution_source = source or "explicit_identifier"
        if source == "alias" and resolved != raw.strip():
            resolution_source = "explicit_alias"
        return _decorate_name_resolution({
            "field": key,
            "input": raw.strip(),
            "resolved_vuln_id": resolved,
            "source": resolution_source,
        })

    if primary_vuln:
        return _decorate_name_resolution({
            "field": "resolved_only",
            "input": primary_vuln,
            "resolved_vuln_id": primary_vuln,
            "source": "resolved_only",
        })
    return {}


def _name_resolution_from_target(target: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(target, dict):
        return {}
    raw_input = str(target.get("input") or "").strip()
    resolved = str(target.get("vuln_id") or "").strip()
    source = str(target.get("source") or "").strip() or "unknown"
    field = str(target.get("field") or "").strip()
    if not raw_input or not resolved:
        return {}
    if field in {"vuln_id", "cwe_id", "cve_id"} and source == "alias":
        source = "explicit_alias"
    return _decorate_name_resolution({
        "field": field,
        "input": raw_input,
        "resolved_vuln_id": resolved,
        "source": source,
    })


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
    vuln_id_resolutions: List[Dict[str, str]]
    executor_policy: Dict[str, Any]


def normalize_requirement(
    requirement: Dict[str, Any],
    *,
    multi_vuln_opt_in: bool = False,
) -> RequirementNormalization:
    """Normalize vuln_id/vuln_ids fields and derive helper metadata."""

    normalized_req = deepcopy(requirement)
    targets = _extract_vuln_targets(normalized_req)
    requested = [entry["vuln_id"] for entry in targets]
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
    if targets:
        normalized_req["vuln_id_resolutions"] = [
            _decorate_name_resolution({
                "field": str(entry.get("field") or ""),
                "input": str(entry.get("input") or ""),
                "resolved_vuln_id": str(entry.get("vuln_id") or ""),
                "source": str(entry.get("source") or ""),
            })
            for entry in targets
        ]
        normalized_req["vuln_request_identities"] = [
            _request_identity_from_resolution(
                normalized_req,
                _decorate_name_resolution({
                    "field": str(entry.get("field") or ""),
                    "input": str(entry.get("input") or ""),
                    "resolved_vuln_id": str(entry.get("vuln_id") or ""),
                    "source": str(entry.get("source") or ""),
                }),
            )
            for entry in targets
        ]
        normalized_req["vuln_request_identities"] = [
            entry for entry in normalized_req["vuln_request_identities"] if isinstance(entry, dict) and entry
        ]
    name_resolution = _name_resolution_from_target(targets[0]) if targets else {}
    if not name_resolution:
        name_resolution = _name_resolution(normalized_req, effective[0])
    if name_resolution:
        normalized_req["name_resolution"] = name_resolution
        request_identity = _request_identity_from_resolution(normalized_req, name_resolution)
        if request_identity:
            normalized_req["request_identity"] = request_identity
    _apply_minimal_input_defaults(normalized_req, effective, warnings)
    _normalize_unknown_pattern_seed(normalized_req, effective, warnings)
    _normalize_research_policy(normalized_req, effective, warnings)
    _normalize_pipeline_policy(normalized_req, effective, warnings)
    request_identity = normalized_req.get("request_identity") if isinstance(normalized_req.get("request_identity"), dict) else {}
    name_resolution = normalized_req.get("name_resolution") if isinstance(normalized_req.get("name_resolution"), dict) else {}
    normalized_req["request_ir"] = _build_request_ir(
        normalized_req,
        primary_vuln=effective[0],
        request_identity=request_identity,
        name_resolution=name_resolution,
    )
    raw_resolutions = normalized_req.get("vuln_id_resolutions")
    raw_request_identities = normalized_req.get("vuln_request_identities")
    if isinstance(raw_resolutions, list) and isinstance(raw_request_identities, list):
        request_irs: List[Dict[str, Any]] = []
        for resolution in raw_resolutions:
            if not isinstance(resolution, dict):
                continue
            resolved_vuln_id = str(resolution.get("resolved_vuln_id") or "").strip()
            if not resolved_vuln_id:
                continue
            request_identity_match = next(
                (
                    dict(entry)
                    for entry in raw_request_identities
                    if isinstance(entry, dict) and str(entry.get("resolved_vuln_id") or "").strip() == resolved_vuln_id
                ),
                {},
            )
            request_irs.append(
                _build_request_ir(
                    normalized_req,
                    primary_vuln=resolved_vuln_id,
                    request_identity=request_identity_match,
                    name_resolution=dict(resolution),
                )
            )
        if request_irs:
            normalized_req["vuln_request_irs"] = request_irs

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
        vuln_id_resolutions=normalized_req.get("vuln_id_resolutions") or [],
        executor_policy=_normalize_executor_policy(normalized_req),
    )


def _extract_vuln_targets(requirement: Dict[str, Any]) -> List[Dict[str, str]]:
    declared: List[Dict[str, str]] = []

    def _append_target(raw_value: Any, *, field: str, allow_synthetic_name: bool) -> None:
        identifier, source = _coerce_vuln_reference(
            raw_value,
            allow_synthetic_name=allow_synthetic_name,
        )
        if not identifier:
            return
        for existing in declared:
            if existing.get("vuln_id") == identifier:
                return
        declared.append(
            {
                "field": field,
                "input": str(raw_value).strip(),
                "vuln_id": identifier,
                "source": source or "unknown",
            }
        )

    seq = requirement.get("vuln_ids")
    if isinstance(seq, list):
        for index, entry in enumerate(seq):
            _append_target(
                entry,
                field=f"vuln_ids[{index}]",
                allow_synthetic_name=True,
            )

    primary: Dict[str, str] = {}
    for key in ("vuln_id", "cwe_id", "cve_id"):
        raw = requirement.get(key)
        identifier, source = _coerce_vuln_reference(
            raw,
            allow_synthetic_name=(key == "vuln_id"),
        )
        if not identifier:
            continue
        primary = {
            "field": key,
            "input": str(raw).strip(),
            "vuln_id": identifier,
            "source": source or "unknown",
        }
        break
    if not primary:
        raw_name = _named_vuln_label(requirement)
        primary_id = _named_vuln_id(requirement)
        if primary_id:
            mapped, source = _mapped_vuln_id_with_source(raw_name)
            primary = {
                "field": "vuln_name",
                "input": raw_name,
                "vuln_id": primary_id,
                "source": source or ("synthetic_name" if not mapped else "alias"),
            }
    if primary:
        declared = [entry for entry in declared if entry.get("vuln_id") != primary.get("vuln_id")]
        declared.insert(0, primary)
    if not declared:
        return []
    return declared


def _pattern_default_for_name(raw_name: str) -> str:
    entry = resolve_vuln_catalog_entry(raw_label=raw_name, pattern_id=raw_name)
    if isinstance(entry, dict):
        mapped = str(entry.get("pattern_id") or "").strip()
        if mapped:
            return mapped
    return "generic-web-vuln"


def _profile_defaults_for_vuln(vuln_id: str, *, raw_name: str = "") -> Dict[str, Any]:
    normalized = _coerce_identifier(vuln_id) or str(vuln_id or "").strip().upper()
    profile = deepcopy(DEFAULT_STACK_PROFILE)
    profile.update(deepcopy(VULN_PROFILE_DEFAULTS.get(normalized, {})))
    runtime = deepcopy(DEFAULT_STACK_PROFILE.get("runtime") or {})
    runtime.update(deepcopy((VULN_PROFILE_DEFAULTS.get(normalized, {}) or {}).get("runtime") or {}))
    profile["runtime"] = runtime
    profile.setdefault("display_name", str(raw_name or "").strip() or normalized or "Unknown Vulnerability")
    profile.setdefault("pattern_id", _pattern_default_for_name(raw_name))
    profile.setdefault("user_deps", ["requests==2.31.0"])
    return profile


def _name_only_open_world_posture(requirement: Dict[str, Any]) -> bool:
    contract = build_name_only_contract(requirement=requirement)
    return bool(
        contract.get("enabled")
        and str(contract.get("effective_mode") or "").strip().lower() in {"dynamic", "dynamic_eval", "strict_dynamic"}
    )


def _normalized_stack_hypotheses(raw: Any) -> List[Dict[str, str]]:
    if not isinstance(raw, list):
        return []
    hypotheses: List[Dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        language = str(entry.get("language") or "").strip().lower()
        framework = str(entry.get("framework") or "").strip().lower()
        if not language or not framework:
            continue
        key = (language, framework)
        if key in seen:
            continue
        seen.add(key)
        payload = {
            "language": language,
            "framework": framework,
            "stack_id": f"{language}/{framework}",
            "source": str(entry.get("source") or "unknown").strip().lower() or "unknown",
            "confidence": str(entry.get("confidence") or "unknown").strip().lower() or "unknown",
        }
        hypotheses.append(payload)
    return hypotheses


def _ensure_stack_hypotheses(
    requirement: Dict[str, Any],
    *,
    profile: Dict[str, Any],
    warnings: List[str],
    defer_stack_defaults: bool,
    applied: List[str],
) -> None:
    normalized = _normalized_stack_hypotheses(requirement.get("stack_hypotheses"))
    if normalized:
        requirement["stack_hypotheses"] = normalized
        return
    if not defer_stack_defaults:
        return

    hypotheses: List[Dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add_candidate(language: Any, framework: Any, *, source: str, confidence: str) -> None:
        lang = str(language or "").strip().lower()
        fw = str(framework or "").strip().lower()
        if not lang or not fw:
            return
        key = (lang, fw)
        if key in seen:
            return
        seen.add(key)
        hypotheses.append(
            {
                "language": lang,
                "framework": fw,
                "stack_id": f"{lang}/{fw}",
                "source": source,
                "confidence": confidence,
            }
        )

    explicit_language = requirement.get("language")
    explicit_framework = requirement.get("framework")
    add_candidate(explicit_language, explicit_framework, source="explicit_requirement", confidence="high")
    add_candidate(profile.get("language"), profile.get("framework"), source="profile_prior", confidence="low")
    for candidate in AVAILABLE_STACK_HYPOTHESIS_POOL:
        add_candidate(
            candidate.get("language"),
            candidate.get("framework"),
            source=str(candidate.get("source") or "available_skeleton"),
            confidence=str(candidate.get("confidence") or "low"),
        )
    if not hypotheses:
        return
    requirement["stack_hypotheses"] = hypotheses
    applied.append("stack_hypotheses")
    warnings.append(
        "Deferred hard stack defaults for name-only dynamic posture; using stack_hypotheses as soft candidates instead."
    )


def _apply_minimal_input_defaults(
    requirement: Dict[str, Any],
    effective_vuln_ids: List[str],
    warnings: List[str],
) -> None:
    primary_vuln = effective_vuln_ids[0] if effective_vuln_ids else str(requirement.get("vuln_id") or "")
    raw_name = _named_vuln_label(requirement)
    profile = _profile_defaults_for_vuln(primary_vuln, raw_name=raw_name)
    defer_stack_defaults = _name_only_open_world_posture(requirement)
    applied: List[str] = []

    def _apply(key: str, value: Any) -> None:
        if requirement.get(key) not in (None, "", [], {}):
            return
        requirement[key] = deepcopy(value)
        applied.append(key)

    _apply("requirement_id", f"AUTO-{slugify_vuln_id(primary_vuln or 'unknown').upper()}")
    _apply("intent", f"Auto-normalized minimal-input run for {profile.get('display_name') or primary_vuln}")
    _apply("vuln_label", profile.get("display_name"))
    if not defer_stack_defaults:
        _apply("language", profile.get("language"))
        _apply("framework", profile.get("framework"))
    _apply("seed", profile.get("seed"))
    _apply("retriever_commit", profile.get("retriever_commit"))
    _apply("corpus_snapshot", profile.get("corpus_snapshot"))
    _apply("pattern_id", profile.get("pattern_id"))
    _apply("deps_digest", profile.get("deps_digest"))
    if not defer_stack_defaults:
        _apply("base_image_digest", profile.get("base_image_digest"))
    _apply("generator_mode", profile.get("generator_mode"))

    runtime = requirement.get("runtime")
    if not isinstance(runtime, dict):
        runtime = {}
        requirement["runtime"] = runtime
    runtime_defaults = profile.get("runtime") if isinstance(profile.get("runtime"), dict) else {}
    for key, value in runtime_defaults.items():
        if defer_stack_defaults and key in {"base_image", "package_manager"}:
            continue
        if runtime.get(key) in (None, "", [], {}):
            runtime[key] = deepcopy(value)
            applied.append(f"runtime.{key}")

    dep_guard = requirement.get("dep_guard")
    if not isinstance(dep_guard, dict):
        dep_guard = {}
        requirement["dep_guard"] = dep_guard
    for key, value in (profile.get("dep_guard") or {}).items():
        if dep_guard.get(key) in (None, "", [], {}):
            dep_guard[key] = deepcopy(value)
            applied.append(f"dep_guard.{key}")

    if requirement.get("user_deps") in (None, "", []):
        default_user_deps = profile.get("user_deps")
        if isinstance(default_user_deps, list) and default_user_deps:
            requirement["user_deps"] = deepcopy(default_user_deps)
            applied.append("user_deps")

    _ensure_stack_hypotheses(
        requirement,
        profile=profile,
        warnings=warnings,
        defer_stack_defaults=defer_stack_defaults,
        applied=applied,
    )

    if applied:
        requirement["_normalization_defaults"] = {
            "profile": str(profile.get("display_name") or primary_vuln or "unknown"),
            "applied_fields": applied,
        }
        warnings.append(
            "Applied minimal-input defaults for "
            f"{primary_vuln or 'unknown'}: {', '.join(applied)}"
        )


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
    remote_required = any(
        not can_resolve_without_remote_research_for_requirement(vuln_id, requirement)
        for vuln_id in effective_vuln_ids
    )
    policy = requirement.get("policy") if isinstance(requirement.get("policy"), dict) else {}
    name_only_mode = str(policy.get("name_only_mode") or "").strip().lower() if isinstance(policy, dict) else ""
    name_driven = is_name_driven_requirement(requirement)
    if name_driven and name_only_mode == "strict_dynamic":
        remote_required = True
    default_policy = "remote_required" if remote_required else "remote_prefer"
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
    if "shadow_mode" in researcher:
        researcher["shadow_mode"] = _as_bool(researcher.get("shadow_mode"))
    else:
        researcher["shadow_mode"] = False
    researcher["search_filters"] = _normalize_search_filters(researcher.get("search_filters"), warnings)
    requirement["researcher"] = researcher


def _normalize_search_filters(raw: Any, warnings: List[str]) -> Dict[str, Any]:
    if raw in (None, ""):
        return {}
    if not isinstance(raw, dict):
        warnings.append("researcher.search_filters must be a mapping; ignoring invalid value")
        return {}

    normalized: Dict[str, Any] = {}
    unknown_keys = sorted(set(str(key) for key in raw.keys()) - VALID_SEARCH_FILTER_KEYS)
    if unknown_keys:
        warnings.append(
            "researcher.search_filters contains unknown keys: " + ", ".join(unknown_keys)
        )

    for key in ("include_domains", "exclude_domains"):
        value = raw.get(key)
        if value in (None, "", []):
            continue
        items = value if isinstance(value, list) else [value]
        cleaned: List[str] = []
        for item in items:
            if not isinstance(item, str):
                continue
            token = item.strip()
            if token and token not in cleaned:
                cleaned.append(token)
        if cleaned:
            normalized[key] = cleaned

    for key in ("time_range", "country", "search_lang"):
        value = raw.get(key)
        if not isinstance(value, str):
            continue
        token = value.strip()
        if token:
            normalized[key] = token

    return normalized


def _normalize_pipeline_policy(
    requirement: Dict[str, Any],
    effective_vuln_ids: List[str],
    warnings: List[str],
) -> None:
    policy = requirement.get("policy") or {}
    if not isinstance(policy, dict):
        policy = {}
    has_unknown = any(not _has_static_rule(vuln_id) for vuln_id in effective_vuln_ids)
    remote_required = any(
        not can_resolve_without_remote_research_for_requirement(vuln_id, requirement)
        for vuln_id in effective_vuln_ids
    )
    name_driven = is_name_driven_requirement(requirement)
    policy["allow_runtime_rule_override_static"] = _as_bool(
        policy.get("allow_runtime_rule_override_static", False)
    )
    policy["allow_name_family_fallback"] = _as_bool(
        policy.get("allow_name_family_fallback", False)
    )
    policy["open_world_strict"] = _as_bool(policy.get("open_world_strict", False))
    policy["dynamic_eval"] = _as_bool(policy.get("dynamic_eval", False))
    policy["dynamic_eval_allow_lower_bound_fallback"] = _as_bool(
        policy.get("dynamic_eval_allow_lower_bound_fallback", False)
    )
    raw_name_only_mode = str(policy.get("name_only_mode") or "").strip().lower()
    if raw_name_only_mode and raw_name_only_mode not in VALID_NAME_ONLY_MODES:
        warnings.append(
            "policy.name_only_mode must be one of compatibility, dynamic, strict_dynamic; "
            f"got '{raw_name_only_mode}', defaulting to compatibility"
        )
        raw_name_only_mode = ""
    policy["name_only_mode"] = raw_name_only_mode or "compatibility"
    if "require_researcher_evidence" in policy:
        policy["require_researcher_evidence"] = _as_bool(policy.get("require_researcher_evidence"))
    else:
        policy["require_researcher_evidence"] = remote_required
    if name_driven and policy["name_only_mode"] == "strict_dynamic":
        policy["require_researcher_evidence"] = True
    policy["allow_unknown_pattern_seed"] = _as_bool(policy.get("allow_unknown_pattern_seed", False))
    _normalize_guard_policy(policy, has_unknown=has_unknown, warnings=warnings)
    _normalize_verifier_policy(policy, has_unknown=has_unknown, warnings=warnings)
    policy["name_only_contract"] = build_name_only_contract(requirement=requirement, policy=policy)
    requirement["policy"] = policy


def _normalize_unknown_pattern_seed(
    requirement: Dict[str, Any],
    effective_vuln_ids: List[str],
    warnings: List[str],
) -> None:
    if not effective_vuln_ids:
        return
    primary_vuln = str(effective_vuln_ids[0] or "").strip()
    if not primary_vuln:
        return
    policy = requirement.get("policy") if isinstance(requirement.get("policy"), dict) else {}
    if _as_bool(policy.get("allow_unknown_pattern_seed", False)):
        return
    if can_resolve_without_remote_research_for_requirement(primary_vuln, requirement):
        return
    name_resolution = requirement.get("name_resolution") if isinstance(requirement.get("name_resolution"), dict) else {}
    resolution_source = str(name_resolution.get("source") or "").strip().lower()
    if resolution_source not in {"explicit_identifier", "synthetic_name", "resolved_only"}:
        return
    current_pattern = str(requirement.get("pattern_id") or "").strip()
    if not current_pattern or current_pattern == "generic-web-vuln":
        return
    requirement["pattern_id"] = "generic-web-vuln"
    warnings.append(
        "Normalized pattern_id to generic-web-vuln for unsupported unknown family; "
        f"inherited pattern seed '{current_pattern}' is ignored by default."
    )


def _normalize_verifier_policy(
    policy: Dict[str, Any],
    *,
    has_unknown: bool,
    warnings: List[str],
) -> None:
    verifier = policy.get("verifier") or {}
    if not isinstance(verifier, dict):
        verifier = {}
    low_trust_policy = str(verifier.get("low_trust_unknown_policy") or "warn").strip().lower()
    if low_trust_policy not in VALID_VERIFIER_LOW_TRUST_POLICIES:
        warnings.append(
            "policy.verifier.low_trust_unknown_policy must be one of "
            f"{sorted(VALID_VERIFIER_LOW_TRUST_POLICIES)}; falling back to warn"
        )
        low_trust_policy = "warn"
    if has_unknown and low_trust_policy == "warn":
        verifier["low_trust_unknown_policy"] = "warn"
    else:
        verifier["low_trust_unknown_policy"] = low_trust_policy
    promotion_independence = str(verifier.get("min_promotion_independence") or "compiler_coupled").strip().lower()
    if promotion_independence not in VALID_VERIFIER_PROMOTION_INDEPENDENCE:
        warnings.append(
            "policy.verifier.min_promotion_independence must be one of "
            f"{sorted(VALID_VERIFIER_PROMOTION_INDEPENDENCE)}; falling back to compiler_coupled"
        )
        promotion_independence = "compiler_coupled"
    verifier["min_promotion_independence"] = promotion_independence
    min_name_resolution_confidence = str(
        verifier.get("min_name_resolution_confidence") or "low"
    ).strip().lower()
    if min_name_resolution_confidence not in VALID_VERIFIER_NAME_RESOLUTION_CONFIDENCE:
        warnings.append(
            "policy.verifier.min_name_resolution_confidence must be one of "
            f"{sorted(VALID_VERIFIER_NAME_RESOLUTION_CONFIDENCE)}; falling back to low"
        )
        min_name_resolution_confidence = "low"
    verifier["min_name_resolution_confidence"] = min_name_resolution_confidence
    policy["verifier"] = verifier


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

    low_confidence_policy = str(guard.get("low_confidence_unknown_policy") or "warn").strip().lower()
    if low_confidence_policy not in VALID_GUARD_LOW_CONFIDENCE_POLICIES:
        warnings.append(
            "policy.guard.low_confidence_unknown_policy must be one of "
            f"{sorted(VALID_GUARD_LOW_CONFIDENCE_POLICIES)}; falling back to warn"
        )
        low_confidence_policy = "warn"

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
    guard["low_confidence_unknown_policy"] = low_confidence_policy
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
