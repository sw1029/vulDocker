from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

MECHANICAL_BLOCKER_PREFIXES = (
    "matrix_gate:",
    "repeatability_gate:",
    "measured_gate:",
    "verdict_authority:",
)

PROMOTION_POLICY_BLOCKER_PREFIXES = (
    "strict_open_world:",
    "open_world:",
    "oracle_clarity:",
    "family_evidence:",
    "artifact_quality:",
    "oracle_execution_parity:",
)


def _load_json_like(payload_or_path: Mapping[str, Any] | Path | str | None) -> Dict[str, Any]:
    if payload_or_path is None:
        return {}
    if isinstance(payload_or_path, Mapping):
        return dict(payload_or_path)
    path = Path(payload_or_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _case_gate_status(
    *,
    case_name: str,
    matrix_report: Mapping[str, Any],
    repeatability_report: Mapping[str, Any],
) -> Dict[str, Any]:
    matrix_unavailable_reason = (
        str(matrix_report.get("matrix_unavailable_reason") or "").strip()
        if isinstance(matrix_report, Mapping)
        else ""
    )
    covered_cases = set(matrix_report.get("covered_cases") or []) if isinstance(matrix_report.get("covered_cases"), list) else set()
    failed_cases = set(matrix_report.get("failed_cases") or []) if isinstance(matrix_report.get("failed_cases"), list) else set()
    repeatability_failures = (
        set(matrix_report.get("repeatability_failures") or [])
        if isinstance(matrix_report.get("repeatability_failures"), list)
        else set()
    )
    matrix_payload_present = bool(matrix_report)
    matrix_available = matrix_payload_present and not matrix_unavailable_reason
    matrix_case_covered = case_name in covered_cases if matrix_available else False
    matrix_case_green = matrix_case_covered and case_name not in failed_cases and case_name not in repeatability_failures
    repeatability_available = bool(repeatability_report)
    repeatability_passed = bool(repeatability_report.get("passed")) if repeatability_available else False
    measured_gate = (
        repeatability_report.get("measured_gate")
        if isinstance(repeatability_report.get("measured_gate"), dict)
        else {}
    )
    measured_gate_ready = measured_gate.get("ready") is True if measured_gate else None
    blockers = []
    if not matrix_payload_present:
        blockers.append("matrix_gate:missing")
    elif matrix_unavailable_reason:
        blockers.append("matrix_gate:unavailable")
    elif not matrix_case_covered:
        blockers.append("matrix_gate:not_covered")
    elif not matrix_case_green:
        blockers.append("matrix_gate:not_green")
    if not repeatability_available:
        blockers.append("repeatability_gate:missing")
    elif not repeatability_passed:
        blockers.append("repeatability_gate:failed")
    if repeatability_available and measured_gate:
        if measured_gate_ready is False:
            for blocker in measured_gate.get("blockers") or []:
                token = str(blocker).strip()
                if token:
                    blockers.append(f"measured_gate:{token}")
    return {
        "matrix_available": matrix_available,
        "matrix_unavailable_reason": matrix_unavailable_reason or None,
        "matrix_case_covered": matrix_case_covered,
        "matrix_case_green": matrix_case_green,
        "repeatability_available": repeatability_available,
        "repeatability_passed": repeatability_passed,
        "measured_gate_ready": measured_gate_ready,
        "external_blockers": blockers,
    }


def _classify_support_blockers(blockers: Sequence[str]) -> Dict[str, List[str]]:
    mechanical: List[str] = []
    promotion_policy: List[str] = []
    other: List[str] = []
    for item in blockers:
        token = str(item).strip()
        if not token:
            continue
        if token.startswith(MECHANICAL_BLOCKER_PREFIXES):
            mechanical.append(token)
        elif token.startswith(PROMOTION_POLICY_BLOCKER_PREFIXES):
            promotion_policy.append(token)
        else:
            other.append(token)
    return {
        "mechanical": mechanical,
        "promotion_policy": promotion_policy,
        "other": other,
    }


def _support_status(
    *,
    reviewable: bool,
    mechanical_blockers: Sequence[str],
    promotion_policy_blockers: Sequence[str],
    other_blockers: Sequence[str],
) -> str:
    if reviewable:
        return "reviewable"
    mechanical = bool(mechanical_blockers)
    policy = bool(promotion_policy_blockers or other_blockers)
    if mechanical and policy:
        return "blocked_mixed"
    if mechanical:
        return "mechanically_blocked"
    if policy:
        return "mechanically_healthy_policy_blocked"
    return "blocked_unclassified"


def _measured_authority(
    *,
    summary: Mapping[str, Any],
    matrix_report: Mapping[str, Any],
    repeatability_report: Mapping[str, Any],
) -> Dict[str, Any]:
    summary_verdict_authority = (
        summary.get("verdict_authority") if isinstance(summary.get("verdict_authority"), dict) else {}
    )
    matrix_authority_observations = (
        matrix_report.get("authority_observations")
        if isinstance(matrix_report.get("authority_observations"), dict)
        else {}
    )
    repeatability_projection_modes = (
        repeatability_report.get("observed_verdict_projection_modes")
        if isinstance(repeatability_report.get("observed_verdict_projection_modes"), dict)
        else {}
    )
    return {
        "summary_verdict_authority": summary_verdict_authority,
        "summary_verdict_authority_mode": str(summary_verdict_authority.get("mode") or "").strip() or None,
        "repeatability_verdict_authority_modes": (
            repeatability_report.get("observed_verdict_authority_modes")
            if isinstance(repeatability_report.get("observed_verdict_authority_modes"), list)
            else []
        ),
        "repeatability_verdict_projection_modes": repeatability_projection_modes,
        "repeatability_verdict_authority_consistent": (
            repeatability_report.get("verdict_authority_consistent")
            if isinstance(repeatability_report.get("verdict_authority_consistent"), bool)
            else None
        ),
        "matrix_authority_observations": matrix_authority_observations,
    }


def _authority_gate_status(measured_authority: Mapping[str, Any]) -> Dict[str, Any]:
    summary_mode = str(measured_authority.get("summary_verdict_authority_mode") or "").strip()
    repeatability_modes = (
        measured_authority.get("repeatability_verdict_authority_modes")
        if isinstance(measured_authority.get("repeatability_verdict_authority_modes"), list)
        else []
    )
    repeatability_consistent = measured_authority.get("repeatability_verdict_authority_consistent")
    matrix_authority = (
        measured_authority.get("matrix_authority_observations")
        if isinstance(measured_authority.get("matrix_authority_observations"), dict)
        else {}
    )
    matrix_modes = (
        matrix_authority.get("by_verdict_authority_mode")
        if isinstance(matrix_authority.get("by_verdict_authority_mode"), dict)
        else {}
    )

    blockers: List[str] = []
    if not summary_mode:
        blockers.append("verdict_authority:missing")
    if isinstance(repeatability_consistent, bool) and repeatability_consistent is False:
        blockers.append("verdict_authority:inconsistent")
    if summary_mode and repeatability_modes and summary_mode not in {str(item).strip() for item in repeatability_modes if str(item).strip()}:
        blockers.append("verdict_authority:repeatability_mode_mismatch")
    if summary_mode and matrix_modes and summary_mode not in {
        str(key).strip() for key, value in matrix_modes.items() if str(key).strip() and int(value or 0) > 0
    }:
        blockers.append("verdict_authority:matrix_mode_mismatch")

    return {
        "available": bool(summary_mode),
        "summary_mode": summary_mode or None,
        "repeatability_consistent": repeatability_consistent if isinstance(repeatability_consistent, bool) else None,
        "blockers": blockers,
    }


def _primitive_signature(bundle: Mapping[str, Any]) -> Dict[str, Any]:
    request_ir = bundle.get("request_ir") if isinstance(bundle.get("request_ir"), dict) else {}
    name_only_outcome = bundle.get("name_only_outcome") if isinstance(bundle.get("name_only_outcome"), dict) else {}
    name_only_generation_spec = (
        bundle.get("name_only_generation_spec") if isinstance(bundle.get("name_only_generation_spec"), dict) else {}
    )
    selection_decision = request_ir.get("selection_decision") if isinstance(request_ir.get("selection_decision"), dict) else {}
    family_selection = selection_decision.get("family") if isinstance(selection_decision.get("family"), dict) else {}
    stack_selection = selection_decision.get("stack") if isinstance(selection_decision.get("stack"), dict) else {}
    scenario_selection = selection_decision.get("scenario") if isinstance(selection_decision.get("scenario"), dict) else {}
    planning_focus = (
        name_only_generation_spec.get("planning_focus_summary")
        if isinstance(name_only_generation_spec.get("planning_focus_summary"), dict)
        else {}
    )
    return {
        "request_kind": str(name_only_outcome.get("request_kind") or "").strip().lower() or None,
        "mode": str(name_only_outcome.get("mode") or "").strip().lower() or None,
        "request_label": str(request_ir.get("request_label") or "").strip() or None,
        "selected_family": (
            str(name_only_outcome.get("selected_family") or "").strip()
            or str(family_selection.get("selected_family") or "").strip()
            or None
        ),
        "selected_stack_id": (
            str(name_only_outcome.get("selected_stack_id") or "").strip()
            or str(stack_selection.get("selected_stack_id") or "").strip()
            or None
        ),
        "selected_topology": str(scenario_selection.get("selected_topology") or "").strip() or None,
        "selected_scenario_id": str(scenario_selection.get("selected_scenario_id") or "").strip() or None,
        "provisional_family": str(request_ir.get("provisional_family") or "").strip() or None,
        "primitive_hypotheses": request_ir.get("primitive_hypotheses") or [],
        "runtime_dependency_hypotheses": request_ir.get("runtime_dependency_hypotheses") or [],
        "topology_hypotheses": request_ir.get("topology_hypotheses") or [],
        "primary_focus": str(planning_focus.get("primary_focus") or "").strip() or None,
    }


def _runtime_contract(bundle: Mapping[str, Any]) -> Dict[str, Any]:
    runtime_recipe = bundle.get("runtime_recipe") if isinstance(bundle.get("runtime_recipe"), dict) else {}
    executor_plan = bundle.get("executor_plan") if isinstance(bundle.get("executor_plan"), dict) else {}
    runtime_graph = bundle.get("runtime_graph") if isinstance(bundle.get("runtime_graph"), dict) else {}
    sidecars = executor_plan.get("sidecars") if isinstance(executor_plan.get("sidecars"), list) else runtime_recipe.get("sidecars")
    sidecars = sidecars if isinstance(sidecars, list) else []
    normalized_sidecars = []
    for entry in sidecars:
        if not isinstance(entry, dict):
            continue
        normalized_sidecars.append(
            {
                "name": str(entry.get("name") or "").strip() or None,
                "image": str(entry.get("image") or "").strip() or None,
                "aliases": [str(item).strip() for item in (entry.get("aliases") or []) if str(item).strip()],
                "env_keys": sorted(str(key).strip() for key in (entry.get("env") or {}).keys() if str(key).strip())
                if isinstance(entry.get("env"), dict)
                else [],
                "ready_probe": entry.get("ready_probe") if isinstance(entry.get("ready_probe"), dict) else None,
            }
        )
    return {
        "framework": str(runtime_recipe.get("framework") or "").strip() or None,
        "topology": (
            str(executor_plan.get("topology") or "").strip()
            or str(runtime_recipe.get("topology") or "").strip()
            or str(runtime_graph.get("topology") or "").strip()
            or None
        ),
        "service_port": executor_plan.get("service_port") or runtime_recipe.get("service_port"),
        "base_url": str(executor_plan.get("base_url") or "").strip() or None,
        "health_path": (
            str(executor_plan.get("health_path") or "").strip()
            or str(runtime_recipe.get("health_path") or "").strip()
            or None
        ),
        "healthchecks": executor_plan.get("healthchecks") if isinstance(executor_plan.get("healthchecks"), list) else [],
        "service_env_keys": sorted(
            str(key).strip()
            for key in (
                (executor_plan.get("service_env") if isinstance(executor_plan.get("service_env"), dict) else {})
                or (runtime_recipe.get("service_env") if isinstance(runtime_recipe.get("service_env"), dict) else {})
            ).keys()
            if str(key).strip()
        ),
        "sidecars": normalized_sidecars,
    }


def _oracle_contract(bundle: Mapping[str, Any]) -> Dict[str, Any]:
    exploit_oracle = bundle.get("exploit_oracle") if isinstance(bundle.get("exploit_oracle"), dict) else {}
    verification = bundle.get("verification") if isinstance(bundle.get("verification"), dict) else {}
    negative_controls = exploit_oracle.get("negative_controls") if isinstance(exploit_oracle.get("negative_controls"), list) else []
    metamorphic = exploit_oracle.get("metamorphic") if isinstance(exploit_oracle.get("metamorphic"), dict) else {}
    metamorphic_cases = metamorphic.get("cases") if isinstance(metamorphic.get("cases"), list) else []
    return {
        "success_signature": str(exploit_oracle.get("success_signature") or "").strip() or None,
        "flag_token": str(exploit_oracle.get("flag_token") or "").strip() or None,
        "poc_cmd": str(exploit_oracle.get("poc_cmd") or "").strip() or None,
        "negative_control_count": len(negative_controls),
        "negative_controls_with_payload": sum(
            1 for item in negative_controls if isinstance(item, dict) and str(item.get("payload") or "").strip()
        ),
        "metamorphic_case_count": len([item for item in metamorphic_cases if isinstance(item, dict)]),
        "metamorphic_relation": str(metamorphic.get("relation") or "").strip() or None,
        "verification_rule_source": str(verification.get("rule_source") or "").strip().lower() or None,
        "verification_trust": str(verification.get("trust") or "").strip().lower() or None,
        "verification_independence": str(verification.get("independence") or "").strip().lower() or None,
        "oracle_execution_parity": str(verification.get("oracle_execution_parity") or "").strip().lower() or "missing",
        "oracle_execution_attempted": verification.get("oracle_execution_attempted") is True,
        "oracle_negative_controls_pass": verification.get("oracle_negative_controls_pass"),
        "oracle_metamorphic_pass": verification.get("oracle_metamorphic_pass"),
    }


def _unsafe_pattern(bundle: Mapping[str, Any]) -> Dict[str, Any]:
    compiler_contract = bundle.get("compiler_contract") if isinstance(bundle.get("compiler_contract"), dict) else {}
    provenance = bundle.get("provenance") if isinstance(bundle.get("provenance"), dict) else {}
    dynamicness = bundle.get("dynamicness") if isinstance(bundle.get("dynamicness"), dict) else {}
    return {
        "compiler_strategy": str(compiler_contract.get("compiler_strategy") or "").strip() or None,
        "fragment_id": str(compiler_contract.get("fragment_id") or "").strip() or None,
        "compose_mode": str(compiler_contract.get("compose_mode") or "").strip() or None,
        "generation_origin": str(provenance.get("generation_origin") or "").strip() or None,
        "fallback_class": str(provenance.get("fallback_class") or "").strip() or None,
        "materializer": str(provenance.get("materializer") or "").strip() or None,
        "dynamicness_verdict": str(dynamicness.get("verdict") or "").strip() or None,
    }


def _source_artifacts(bundle: Mapping[str, Any], *, manifest_path: Path, summary_path: Optional[Path]) -> Dict[str, Any]:
    paths = bundle.get("paths") if isinstance(bundle.get("paths"), dict) else {}
    source = {
        "manifest_path": str(manifest_path),
        "summary_path": str(summary_path) if summary_path else None,
        "workspace": str(paths.get("workspace") or "").strip() or None,
        "metadata": str(paths.get("metadata") or "").strip() or None,
        "build": str(paths.get("build") or "").strip() or None,
        "run": str(paths.get("run") or "").strip() or None,
    }
    return source


def build_support_candidate(
    summary_or_path: Mapping[str, Any] | Path | str,
    *,
    matrix_report: Mapping[str, Any] | Path | str | None = None,
    repeatability_report: Mapping[str, Any] | Path | str | None = None,
) -> Dict[str, Any]:
    summary = _load_json_like(summary_or_path)
    matrix_payload = _load_json_like(matrix_report)
    repeatability_payload = _load_json_like(repeatability_report)
    manifest_path_raw = str(summary.get("manifest_path") or "").strip()
    if not manifest_path_raw:
        raise ValueError("summary is missing manifest_path")
    manifest_path = Path(manifest_path_raw)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError(f"invalid manifest JSON: {manifest_path}")
    case_name = str(summary.get("case_name") or repeatability_payload.get("case") or "").strip() or None
    gate_status = _case_gate_status(case_name=case_name or "", matrix_report=matrix_payload, repeatability_report=repeatability_payload)
    measured_authority = _measured_authority(
        summary=summary,
        matrix_report=matrix_payload,
        repeatability_report=repeatability_payload,
    )
    authority_gate = _authority_gate_status(measured_authority)
    summary_path = None if isinstance(summary_or_path, Mapping) else Path(summary_or_path)
    candidates = []
    reviewable_bundle_count = 0
    support_ready_bundle_count = 0
    mechanically_healthy_bundle_count = 0
    promotion_policy_ready_bundle_count = 0
    by_support_status: Dict[str, int] = {}
    for bundle in manifest.get("bundles") or []:
        if not isinstance(bundle, dict):
            continue
        support_promotion = bundle.get("support_promotion") if isinstance(bundle.get("support_promotion"), dict) else {}
        internal_eligible = support_promotion.get("eligible") is True
        if internal_eligible:
            support_ready_bundle_count += 1
        blockers = [
            str(item).strip()
            for item in (support_promotion.get("reasons") or [])
            if isinstance(item, str) and str(item).strip()
        ]
        blockers.extend(gate_status.get("external_blockers") or [])
        blockers.extend(authority_gate.get("blockers") or [])
        blocker_classes = _classify_support_blockers(blockers)
        mechanically_healthy = not blocker_classes["mechanical"]
        promotion_policy_ready = internal_eligible and not blocker_classes["promotion_policy"] and not blocker_classes["other"]
        reviewable = internal_eligible and mechanically_healthy and not blocker_classes["promotion_policy"] and not blocker_classes["other"]
        if reviewable:
            reviewable_bundle_count += 1
        if mechanically_healthy:
            mechanically_healthy_bundle_count += 1
        if promotion_policy_ready:
            promotion_policy_ready_bundle_count += 1
        support_status = _support_status(
            reviewable=reviewable,
            mechanical_blockers=blocker_classes["mechanical"],
            promotion_policy_blockers=blocker_classes["promotion_policy"],
            other_blockers=blocker_classes["other"],
        )
        by_support_status[support_status] = by_support_status.get(support_status, 0) + 1
        candidates.append(
            {
                "slug": str(bundle.get("slug") or "").strip() or None,
                "vuln_id": str(bundle.get("vuln_id") or "").strip() or None,
                "support_promotion_eligible": internal_eligible,
                "reviewable": reviewable,
                "support_status": support_status,
                "mechanical_blockers": blocker_classes["mechanical"],
                "promotion_policy_blockers": blocker_classes["promotion_policy"],
                "other_blockers": blocker_classes["other"],
                "gates": {
                    "support_promotion_eligible": internal_eligible,
                    "matrix_case_green": gate_status.get("matrix_case_green"),
                    "repeatability_passed": gate_status.get("repeatability_passed"),
                    "measured_gate_ready": gate_status.get("measured_gate_ready"),
                    "verdict_authority_ready": not bool(authority_gate.get("blockers")),
                    "mechanically_healthy": mechanically_healthy,
                    "promotion_policy_ready": promotion_policy_ready,
                    "oracle_execution_parity": str(
                        ((bundle.get("artifact_quality") or {}) if isinstance(bundle.get("artifact_quality"), dict) else {}).get(
                            "oracle_execution_parity"
                        )
                        or ""
                    ).strip().lower()
                    or "missing",
                },
                "verdict_authority_mode": measured_authority.get("summary_verdict_authority_mode"),
                "verdict_authority_consistent": measured_authority.get("repeatability_verdict_authority_consistent"),
                "blockers": blockers,
                "primitive_signature": _primitive_signature(bundle),
                "runtime_contract": _runtime_contract(bundle),
                "oracle_contract": _oracle_contract(bundle),
                "unsafe_pattern": _unsafe_pattern(bundle),
                "source_artifacts": _source_artifacts(bundle, manifest_path=manifest_path, summary_path=summary_path),
            }
        )
    return {
        "schema_version": "support_candidate@0.1",
        "sid": str(summary.get("sid") or manifest.get("sid") or "").strip() or None,
        "case_name": case_name,
        "manifest_path": str(manifest_path),
        "matrix_report_path": (
            str(repeatability_payload.get("matrix_report_path") or "")
            if repeatability_payload.get("matrix_report_path")
            else None
        ),
        "repeatability_report_path": (
            str(repeatability_payload.get("report_path") or "")
            if repeatability_payload.get("report_path")
            else None
        ),
        "case_gates": gate_status,
        "measured_authority": measured_authority,
        "authority_gate": authority_gate,
        "support_ready_bundle_count": support_ready_bundle_count,
        "mechanically_healthy_bundle_count": mechanically_healthy_bundle_count,
        "promotion_policy_ready_bundle_count": promotion_policy_ready_bundle_count,
        "by_support_status": by_support_status,
        "reviewable_bundle_count": reviewable_bundle_count,
        "all_reviewable": reviewable_bundle_count == len(candidates) if candidates else False,
        "candidates": candidates,
    }


def write_support_candidate(
    output_path: Path,
    summary_or_path: Mapping[str, Any] | Path | str,
    *,
    matrix_report: Mapping[str, Any] | Path | str | None = None,
    repeatability_report: Mapping[str, Any] | Path | str | None = None,
) -> Dict[str, Any]:
    payload = build_support_candidate(
        summary_or_path,
        matrix_report=matrix_report,
        repeatability_report=repeatability_report,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def _support_review_entry(candidate_payload: Mapping[str, Any], bundle: Mapping[str, Any]) -> Dict[str, Any]:
    primitive_signature = bundle.get("primitive_signature") if isinstance(bundle.get("primitive_signature"), dict) else {}
    runtime_contract = bundle.get("runtime_contract") if isinstance(bundle.get("runtime_contract"), dict) else {}
    oracle_contract = bundle.get("oracle_contract") if isinstance(bundle.get("oracle_contract"), dict) else {}
    source_artifacts = bundle.get("source_artifacts") if isinstance(bundle.get("source_artifacts"), dict) else {}
    return {
        "case_name": str(candidate_payload.get("case_name") or "").strip() or None,
        "sid": str(candidate_payload.get("sid") or "").strip() or None,
        "slug": str(bundle.get("slug") or "").strip() or None,
        "vuln_id": str(bundle.get("vuln_id") or "").strip() or None,
        "reviewable": bundle.get("reviewable") is True,
        "support_promotion_eligible": bundle.get("support_promotion_eligible") is True,
        "support_status": str(bundle.get("support_status") or "").strip() or None,
        "blockers": [
            str(item).strip()
            for item in (bundle.get("blockers") or [])
            if isinstance(item, str) and str(item).strip()
        ],
        "mechanical_blockers": [
            str(item).strip()
            for item in (bundle.get("mechanical_blockers") or [])
            if isinstance(item, str) and str(item).strip()
        ],
        "promotion_policy_blockers": [
            str(item).strip()
            for item in (bundle.get("promotion_policy_blockers") or [])
            if isinstance(item, str) and str(item).strip()
        ],
        "other_blockers": [
            str(item).strip()
            for item in (bundle.get("other_blockers") or [])
            if isinstance(item, str) and str(item).strip()
        ],
        "selected_family": str(primitive_signature.get("selected_family") or "").strip() or None,
        "selected_stack_id": str(primitive_signature.get("selected_stack_id") or "").strip() or None,
        "topology": str(runtime_contract.get("topology") or "").strip() or None,
        "oracle_execution_parity": str(oracle_contract.get("oracle_execution_parity") or "").strip().lower() or "missing",
        "verdict_authority_mode": str(bundle.get("verdict_authority_mode") or "").strip() or None,
        "verdict_authority_consistent": bundle.get("verdict_authority_consistent"),
        "verdict_authority_ready": (
            ((bundle.get("gates") or {}) if isinstance(bundle.get("gates"), dict) else {}).get("verdict_authority_ready")
            if isinstance(((bundle.get("gates") or {}) if isinstance(bundle.get("gates"), dict) else {}).get("verdict_authority_ready"), bool)
            else None
        ),
        "measured_gate_ready": (
            ((bundle.get("gates") or {}) if isinstance(bundle.get("gates"), dict) else {}).get("measured_gate_ready")
            if isinstance(((bundle.get("gates") or {}) if isinstance(bundle.get("gates"), dict) else {}).get("measured_gate_ready"), bool)
            else None
        ),
        "mechanically_healthy": (
            ((bundle.get("gates") or {}) if isinstance(bundle.get("gates"), dict) else {}).get("mechanically_healthy")
            if isinstance(((bundle.get("gates") or {}) if isinstance(bundle.get("gates"), dict) else {}).get("mechanically_healthy"), bool)
            else None
        ),
        "promotion_policy_ready": (
            ((bundle.get("gates") or {}) if isinstance(bundle.get("gates"), dict) else {}).get("promotion_policy_ready")
            if isinstance(((bundle.get("gates") or {}) if isinstance(bundle.get("gates"), dict) else {}).get("promotion_policy_ready"), bool)
            else None
        ),
        "manifest_path": str(candidate_payload.get("manifest_path") or "").strip() or None,
        "summary_path": str(source_artifacts.get("summary_path") or "").strip() or None,
        "workspace": str(source_artifacts.get("workspace") or "").strip() or None,
        "support_candidate_path": str(candidate_payload.get("_support_candidate_path") or "").strip() or None,
    }


def build_support_review_index(
    support_candidates: Sequence[Mapping[str, Any] | Path | str],
) -> Dict[str, Any]:
    payloads: List[Dict[str, Any]] = []
    review_queue: List[Dict[str, Any]] = []
    blocked_queue: List[Dict[str, Any]] = []
    by_blocker: Dict[str, int] = {}
    by_authority_blocker: Dict[str, int] = {}
    by_measured_gate_blocker: Dict[str, int] = {}
    by_mechanical_blocker: Dict[str, int] = {}
    by_promotion_policy_blocker: Dict[str, int] = {}
    by_family: Dict[str, int] = {}
    by_topology: Dict[str, int] = {}
    by_verdict_authority_mode: Dict[str, int] = {}
    by_support_status: Dict[str, int] = {}
    authority_ready_bundle_count = 0
    authority_blocked_bundle_count = 0
    measured_gate_ready_bundle_count = 0
    measured_gate_blocked_bundle_count = 0
    mechanically_healthy_bundle_count = 0
    mechanically_blocked_bundle_count = 0
    promotion_policy_ready_bundle_count = 0
    promotion_policy_blocked_bundle_count = 0
    reviewable_cases: List[str] = []
    blocked_cases: List[str] = []
    case_statuses: List[Dict[str, Any]] = []
    by_case_status: Dict[str, int] = {}

    for item in support_candidates:
        payload = _load_json_like(item)
        if not payload:
            continue
        if not isinstance(item, Mapping):
            payload["_support_candidate_path"] = str(Path(item))
        payloads.append(payload)

        case_name = str(payload.get("case_name") or "").strip()
        candidates = payload.get("candidates") if isinstance(payload.get("candidates"), list) else []
        case_has_reviewable = False
        case_has_candidate = False
        case_bundle_count = 0
        case_reviewable_bundle_count = 0
        case_blocked_bundle_count = 0
        case_mechanically_healthy_bundle_count = 0
        case_mechanically_blocked_bundle_count = 0
        case_promotion_policy_ready_bundle_count = 0
        case_promotion_policy_blocked_bundle_count = 0
        case_by_support_status: Dict[str, int] = {}
        case_by_mechanical_blocker: Dict[str, int] = {}
        case_by_promotion_policy_blocker: Dict[str, int] = {}
        for bundle in candidates:
            if not isinstance(bundle, dict):
                continue
            case_has_candidate = True
            case_bundle_count += 1
            entry = _support_review_entry(payload, bundle)
            family = str(entry.get("selected_family") or "").strip()
            topology = str(entry.get("topology") or "").strip()
            verdict_authority_mode = str(entry.get("verdict_authority_mode") or "").strip()
            support_status = str(entry.get("support_status") or "").strip()
            if family:
                by_family[family] = by_family.get(family, 0) + 1
            if topology:
                by_topology[topology] = by_topology.get(topology, 0) + 1
            if verdict_authority_mode:
                by_verdict_authority_mode[verdict_authority_mode] = (
                    by_verdict_authority_mode.get(verdict_authority_mode, 0) + 1
                )
            if support_status:
                by_support_status[support_status] = by_support_status.get(support_status, 0) + 1
                case_by_support_status[support_status] = case_by_support_status.get(support_status, 0) + 1
            if entry.get("verdict_authority_ready") is True:
                authority_ready_bundle_count += 1
            elif entry.get("verdict_authority_ready") is False:
                authority_blocked_bundle_count += 1
            if entry.get("measured_gate_ready") is True:
                measured_gate_ready_bundle_count += 1
            elif entry.get("measured_gate_ready") is False:
                measured_gate_blocked_bundle_count += 1
            if entry.get("mechanically_healthy") is True:
                mechanically_healthy_bundle_count += 1
                case_mechanically_healthy_bundle_count += 1
            elif entry.get("mechanically_healthy") is False:
                mechanically_blocked_bundle_count += 1
                case_mechanically_blocked_bundle_count += 1
            if entry.get("promotion_policy_ready") is True:
                promotion_policy_ready_bundle_count += 1
                case_promotion_policy_ready_bundle_count += 1
            elif entry.get("promotion_policy_ready") is False:
                promotion_policy_blocked_bundle_count += 1
                case_promotion_policy_blocked_bundle_count += 1
            blockers = entry.get("blockers") or []
            for blocker in entry.get("mechanical_blockers") or []:
                token = str(blocker).strip()
                if token:
                    by_mechanical_blocker[token] = by_mechanical_blocker.get(token, 0) + 1
                    case_by_mechanical_blocker[token] = case_by_mechanical_blocker.get(token, 0) + 1
            for blocker in entry.get("promotion_policy_blockers") or []:
                token = str(blocker).strip()
                if token:
                    by_promotion_policy_blocker[token] = by_promotion_policy_blocker.get(token, 0) + 1
                    case_by_promotion_policy_blocker[token] = case_by_promotion_policy_blocker.get(token, 0) + 1
            if entry["reviewable"] is True:
                case_has_reviewable = True
                case_reviewable_bundle_count += 1
                review_queue.append(entry)
            else:
                case_blocked_bundle_count += 1
                blocked_queue.append(entry)
                for blocker in blockers:
                    token = str(blocker).strip()
                    if token:
                        by_blocker[token] = by_blocker.get(token, 0) + 1
                        if token.startswith("verdict_authority:"):
                            by_authority_blocker[token] = by_authority_blocker.get(token, 0) + 1
                        if token.startswith("measured_gate:"):
                            by_measured_gate_blocker[token] = by_measured_gate_blocker.get(token, 0) + 1
        if case_name and case_has_reviewable:
            reviewable_cases.append(case_name)
        elif case_name and case_has_candidate:
            blocked_cases.append(case_name)
        if case_name and case_has_candidate:
            if case_reviewable_bundle_count == case_bundle_count:
                case_status = "all_reviewable"
            elif case_reviewable_bundle_count > 0:
                case_status = "mixed_reviewability"
            else:
                case_status = "all_blocked"
            by_case_status[case_status] = by_case_status.get(case_status, 0) + 1
            case_statuses.append(
                {
                    "case_name": case_name,
                    "case_status": case_status,
                    "bundle_count": case_bundle_count,
                    "reviewable_bundle_count": case_reviewable_bundle_count,
                    "blocked_bundle_count": case_blocked_bundle_count,
                    "mechanically_healthy_bundle_count": case_mechanically_healthy_bundle_count,
                    "mechanically_blocked_bundle_count": case_mechanically_blocked_bundle_count,
                    "promotion_policy_ready_bundle_count": case_promotion_policy_ready_bundle_count,
                    "promotion_policy_blocked_bundle_count": case_promotion_policy_blocked_bundle_count,
                    "by_support_status": case_by_support_status,
                    "by_mechanical_blocker": case_by_mechanical_blocker,
                    "by_promotion_policy_blocker": case_by_promotion_policy_blocker,
                }
            )

    review_queue.sort(key=lambda item: (str(item.get("case_name") or ""), str(item.get("slug") or "")))
    blocked_queue.sort(key=lambda item: (str(item.get("case_name") or ""), str(item.get("slug") or "")))
    reviewable_cases = sorted(set(reviewable_cases))
    blocked_cases = sorted(set(blocked_cases))
    case_statuses.sort(key=lambda item: str(item.get("case_name") or ""))
    all_reviewable_cases = _case_names_for_status(
        case_statuses,
        status_key="case_status",
        target_statuses=("all_reviewable",),
    )
    mixed_cases = _case_names_for_status(
        case_statuses,
        status_key="case_status",
        target_statuses=("mixed_reviewability",),
    )
    all_blocked_cases = _case_names_for_status(
        case_statuses,
        status_key="case_status",
        target_statuses=("all_blocked",),
    )
    return {
        "schema_version": "support_review_index@0.1",
        "support_candidate_file_count": len(payloads),
        "case_count": len(
            {
                str(payload.get("case_name") or "").strip()
                for payload in payloads
                if str(payload.get("case_name") or "").strip()
            }
        ),
        "support_ready_bundle_count": sum(int(payload.get("support_ready_bundle_count") or 0) for payload in payloads),
        "reviewable_bundle_count": len(review_queue),
        "authority_ready_bundle_count": authority_ready_bundle_count,
        "authority_blocked_bundle_count": authority_blocked_bundle_count,
        "measured_gate_ready_bundle_count": measured_gate_ready_bundle_count,
        "measured_gate_blocked_bundle_count": measured_gate_blocked_bundle_count,
        "mechanically_healthy_bundle_count": mechanically_healthy_bundle_count,
        "mechanically_blocked_bundle_count": mechanically_blocked_bundle_count,
        "promotion_policy_ready_bundle_count": promotion_policy_ready_bundle_count,
        "promotion_policy_blocked_bundle_count": promotion_policy_blocked_bundle_count,
        "reviewable_cases": reviewable_cases,
        "blocked_cases": blocked_cases,
        "all_reviewable_case_count": len(all_reviewable_cases),
        "mixed_case_count": len(mixed_cases),
        "all_blocked_case_count": len(all_blocked_cases),
        "all_reviewable_cases": all_reviewable_cases,
        "mixed_cases": mixed_cases,
        "all_blocked_cases": all_blocked_cases,
        "by_case_status": by_case_status,
        "case_statuses": case_statuses,
        "by_blocker": by_blocker,
        "by_authority_blocker": by_authority_blocker,
        "by_measured_gate_blocker": by_measured_gate_blocker,
        "by_mechanical_blocker": by_mechanical_blocker,
        "by_promotion_policy_blocker": by_promotion_policy_blocker,
        "by_family": by_family,
        "by_topology": by_topology,
        "by_verdict_authority_mode": by_verdict_authority_mode,
        "by_support_status": by_support_status,
        "review_queue": review_queue,
        "blocked_queue": blocked_queue,
    }


def write_support_review_index(
    output_path: Path,
    support_candidates: Sequence[Mapping[str, Any] | Path | str],
) -> Dict[str, Any]:
    payload = build_support_review_index(support_candidates)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def _review_queue_index(review_index: Mapping[str, Any]) -> Dict[tuple[str, str], Dict[str, Any]]:
    queue = review_index.get("review_queue") if isinstance(review_index.get("review_queue"), list) else []
    indexed: Dict[tuple[str, str], Dict[str, Any]] = {}
    for entry in queue:
        if not isinstance(entry, dict):
            continue
        case_name = str(entry.get("case_name") or "").strip()
        slug = str(entry.get("slug") or "").strip()
        if not case_name or not slug:
            continue
        indexed[(case_name, slug)] = entry
    return indexed


def _decision_entries(decisions_payload: Mapping[str, Any]) -> List[Dict[str, Any]]:
    entries = decisions_payload.get("decisions") if isinstance(decisions_payload.get("decisions"), list) else []
    return [entry for entry in entries if isinstance(entry, dict)]


def _case_status_from_counts(*, reviewable_bundle_count: int, bundle_count: int) -> str:
    if reviewable_bundle_count >= bundle_count and bundle_count > 0:
        return "all_reviewable"
    if reviewable_bundle_count > 0:
        return "mixed_reviewability"
    return "all_blocked"


def _derive_case_statuses_from_review_index(review_index: Mapping[str, Any]) -> tuple[Dict[str, int], List[Dict[str, Any]]]:
    queues: List[Dict[str, Any]] = []
    for key in ("review_queue", "blocked_queue"):
        entries = review_index.get(key)
        if isinstance(entries, list):
            queues.extend(entry for entry in entries if isinstance(entry, dict))

    per_case: Dict[str, Dict[str, Any]] = {}
    for entry in queues:
        case_name = str(entry.get("case_name") or "").strip()
        if not case_name:
            continue
        support_status = str(entry.get("support_status") or "").strip()
        reviewable = entry.get("reviewable") is True or support_status == "reviewable"
        bucket = per_case.setdefault(
            case_name,
            {
                "case_name": case_name,
                "bundle_count": 0,
                "reviewable_bundle_count": 0,
                "blocked_bundle_count": 0,
                "mechanically_healthy_bundle_count": 0,
                "mechanically_blocked_bundle_count": 0,
                "promotion_policy_ready_bundle_count": 0,
                "promotion_policy_blocked_bundle_count": 0,
                "by_support_status": {},
                "by_mechanical_blocker": {},
                "by_promotion_policy_blocker": {},
            },
        )
        bucket["bundle_count"] += 1
        if reviewable:
            bucket["reviewable_bundle_count"] += 1
        else:
            bucket["blocked_bundle_count"] += 1
        if entry.get("mechanically_healthy") is True:
            bucket["mechanically_healthy_bundle_count"] += 1
        elif entry.get("mechanically_healthy") is False:
            bucket["mechanically_blocked_bundle_count"] += 1
        if entry.get("promotion_policy_ready") is True:
            bucket["promotion_policy_ready_bundle_count"] += 1
        elif entry.get("promotion_policy_ready") is False:
            bucket["promotion_policy_blocked_bundle_count"] += 1
        if support_status:
            by_support_status = bucket["by_support_status"]
            by_support_status[support_status] = by_support_status.get(support_status, 0) + 1
        for blocker in entry.get("mechanical_blockers") or []:
            token = str(blocker).strip()
            if token:
                by_mechanical_blocker = bucket["by_mechanical_blocker"]
                by_mechanical_blocker[token] = by_mechanical_blocker.get(token, 0) + 1
        for blocker in entry.get("promotion_policy_blockers") or []:
            token = str(blocker).strip()
            if token:
                by_promotion_policy_blocker = bucket["by_promotion_policy_blocker"]
                by_promotion_policy_blocker[token] = by_promotion_policy_blocker.get(token, 0) + 1

    case_statuses: List[Dict[str, Any]] = []
    by_case_status: Dict[str, int] = {}
    for case_name in sorted(per_case):
        bucket = per_case[case_name]
        case_status = _case_status_from_counts(
            reviewable_bundle_count=int(bucket["reviewable_bundle_count"] or 0),
            bundle_count=int(bucket["bundle_count"] or 0),
        )
        bucket["case_status"] = case_status
        by_case_status[case_status] = by_case_status.get(case_status, 0) + 1
        case_statuses.append(bucket)
    return by_case_status, case_statuses


def _case_names_for_status(
    entries: Sequence[Mapping[str, Any]],
    *,
    status_key: str,
    target_statuses: Sequence[str],
) -> List[str]:
    allowed = {str(status).strip() for status in target_statuses if str(status).strip()}
    names = {
        str(entry.get("case_name") or "").strip()
        for entry in entries
        if str(entry.get(status_key) or "").strip() in allowed and str(entry.get("case_name") or "").strip()
    }
    return sorted(names)


def build_support_registry_update(
    review_index_or_path: Mapping[str, Any] | Path | str,
    decisions_or_path: Mapping[str, Any] | Path | str,
) -> Dict[str, Any]:
    review_index = _load_json_like(review_index_or_path)
    decisions_payload = _load_json_like(decisions_or_path)
    queue_index = _review_queue_index(review_index)
    decision_entries = _decision_entries(decisions_payload)
    derived_by_case_status, derived_case_statuses = _derive_case_statuses_from_review_index(review_index)
    raw_by_case_status = review_index.get("by_case_status") if isinstance(review_index.get("by_case_status"), dict) else None
    raw_case_statuses = review_index.get("case_statuses") if isinstance(review_index.get("case_statuses"), list) else None
    by_case_status = dict(raw_by_case_status) if raw_by_case_status is not None else derived_by_case_status
    case_statuses = [dict(entry) for entry in raw_case_statuses if isinstance(entry, dict)] if raw_case_statuses is not None else derived_case_statuses
    reviewable_cases = [
        str(case).strip()
        for case in (review_index.get("reviewable_cases") or [])
        if isinstance(case, str) and str(case).strip()
    ]
    blocked_cases = [
        str(case).strip()
        for case in (review_index.get("blocked_cases") or [])
        if isinstance(case, str) and str(case).strip()
    ]
    if not reviewable_cases and case_statuses:
        reviewable_cases = sorted(
            str(entry.get("case_name") or "").strip()
            for entry in case_statuses
            if str(entry.get("case_status") or "").strip() in {"all_reviewable", "mixed_reviewability"}
            and str(entry.get("case_name") or "").strip()
        )
    if not blocked_cases and case_statuses:
        blocked_cases = sorted(
            str(entry.get("case_name") or "").strip()
            for entry in case_statuses
            if str(entry.get("case_status") or "").strip() == "all_blocked"
            and str(entry.get("case_name") or "").strip()
        )
    all_reviewable_cases = _case_names_for_status(
        case_statuses,
        status_key="case_status",
        target_statuses=("all_reviewable",),
    )
    mixed_cases = _case_names_for_status(
        case_statuses,
        status_key="case_status",
        target_statuses=("mixed_reviewability",),
    )
    all_blocked_cases = _case_names_for_status(
        case_statuses,
        status_key="case_status",
        target_statuses=("all_blocked",),
    )

    accepted: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    invalid_decisions: List[Dict[str, Any]] = []
    consumed_targets = set()
    seen_targets = set()
    accepted_by_verdict_authority_mode: Dict[str, int] = {}
    rejected_by_verdict_authority_mode: Dict[str, int] = {}
    accepted_by_support_status: Dict[str, int] = {}
    rejected_by_support_status: Dict[str, int] = {}

    for decision in decision_entries:
        case_name = str(decision.get("case_name") or "").strip()
        slug = str(decision.get("slug") or "").strip()
        action = str(decision.get("decision") or "").strip().lower()
        rationale = str(decision.get("rationale") or "").strip()
        reviewer = str(decision.get("reviewer") or "").strip()
        target = (case_name, slug)

        if not case_name or not slug:
            invalid_decisions.append(
                {
                    "case_name": case_name or None,
                    "slug": slug or None,
                    "decision": action or None,
                    "reason": "target_missing",
                }
            )
            continue
        if target in seen_targets:
            invalid_decisions.append(
                {
                    "case_name": case_name,
                    "slug": slug,
                    "decision": action or None,
                    "reason": "duplicate_decision",
                }
            )
            continue
        seen_targets.add(target)

        queue_entry = queue_index.get(target)
        if queue_entry is None:
            invalid_decisions.append(
                {
                    "case_name": case_name,
                    "slug": slug,
                    "decision": action or None,
                    "reason": "not_in_review_queue",
                }
            )
            continue
        if action not in {"accept", "reject"}:
            invalid_decisions.append(
                {
                    "case_name": case_name,
                    "slug": slug,
                    "decision": action or None,
                    "reason": "unsupported_decision",
                }
            )
            continue

        decision_record = {
            "case_name": case_name,
            "slug": slug,
            "vuln_id": queue_entry.get("vuln_id"),
            "decision": action,
            "rationale": rationale or None,
            "reviewer": reviewer or None,
            "support_candidate_path": queue_entry.get("support_candidate_path"),
            "manifest_path": queue_entry.get("manifest_path"),
            "summary_path": queue_entry.get("summary_path"),
            "workspace": queue_entry.get("workspace"),
            "selected_family": queue_entry.get("selected_family"),
            "selected_stack_id": queue_entry.get("selected_stack_id"),
            "topology": queue_entry.get("topology"),
            "oracle_execution_parity": queue_entry.get("oracle_execution_parity"),
            "support_status": queue_entry.get("support_status"),
            "verdict_authority_mode": queue_entry.get("verdict_authority_mode"),
            "verdict_authority_consistent": queue_entry.get("verdict_authority_consistent"),
            "verdict_authority_ready": queue_entry.get("verdict_authority_ready"),
            "measured_gate_ready": queue_entry.get("measured_gate_ready"),
            "mechanically_healthy": queue_entry.get("mechanically_healthy"),
            "promotion_policy_ready": queue_entry.get("promotion_policy_ready"),
            "source": queue_entry,
        }
        verdict_authority_mode = str(queue_entry.get("verdict_authority_mode") or "").strip()
        support_status = str(queue_entry.get("support_status") or "").strip()
        if action == "accept":
            accepted.append(decision_record)
            if verdict_authority_mode:
                accepted_by_verdict_authority_mode[verdict_authority_mode] = (
                    accepted_by_verdict_authority_mode.get(verdict_authority_mode, 0) + 1
                )
            if support_status:
                accepted_by_support_status[support_status] = (
                    accepted_by_support_status.get(support_status, 0) + 1
                )
        else:
            rejected.append(decision_record)
            if verdict_authority_mode:
                rejected_by_verdict_authority_mode[verdict_authority_mode] = (
                    rejected_by_verdict_authority_mode.get(verdict_authority_mode, 0) + 1
                )
            if support_status:
                rejected_by_support_status[support_status] = (
                    rejected_by_support_status.get(support_status, 0) + 1
                )
        consumed_targets.add(target)

    pending_review = [
        entry
        for key, entry in sorted(queue_index.items(), key=lambda item: item[0])
        if key not in consumed_targets
    ]
    pending_by_verdict_authority_mode: Dict[str, int] = {}
    pending_by_support_status: Dict[str, int] = {}
    for entry in pending_review:
        verdict_authority_mode = str(entry.get("verdict_authority_mode") or "").strip()
        support_status = str(entry.get("support_status") or "").strip()
        if verdict_authority_mode:
            pending_by_verdict_authority_mode[verdict_authority_mode] = (
                pending_by_verdict_authority_mode.get(verdict_authority_mode, 0) + 1
            )
        if support_status:
            pending_by_support_status[support_status] = (
                pending_by_support_status.get(support_status, 0) + 1
            )

    return {
        "schema_version": "support_registry_update@0.1",
        "review_index_path": (
            str(Path(review_index_or_path).resolve())
            if not isinstance(review_index_or_path, Mapping)
            else None
        ),
        "decision_source_path": (
            str(Path(decisions_or_path).resolve())
            if not isinstance(decisions_or_path, Mapping)
            else None
        ),
        "reviewable_bundle_count": int(review_index.get("reviewable_bundle_count") or 0),
        "authority_ready_bundle_count": int(review_index.get("authority_ready_bundle_count") or 0),
        "authority_blocked_bundle_count": int(review_index.get("authority_blocked_bundle_count") or 0),
        "measured_gate_ready_bundle_count": int(review_index.get("measured_gate_ready_bundle_count") or 0),
        "measured_gate_blocked_bundle_count": int(review_index.get("measured_gate_blocked_bundle_count") or 0),
        "mechanically_healthy_bundle_count": int(review_index.get("mechanically_healthy_bundle_count") or 0),
        "mechanically_blocked_bundle_count": int(review_index.get("mechanically_blocked_bundle_count") or 0),
        "promotion_policy_ready_bundle_count": int(review_index.get("promotion_policy_ready_bundle_count") or 0),
        "promotion_policy_blocked_bundle_count": int(review_index.get("promotion_policy_blocked_bundle_count") or 0),
        "reviewable_case_count": len(reviewable_cases),
        "blocked_case_count": len(blocked_cases),
        "reviewable_cases": reviewable_cases,
        "blocked_cases": blocked_cases,
        "all_reviewable_case_count": len(all_reviewable_cases),
        "mixed_case_count": len(mixed_cases),
        "all_blocked_case_count": len(all_blocked_cases),
        "all_reviewable_cases": all_reviewable_cases,
        "mixed_cases": mixed_cases,
        "all_blocked_cases": all_blocked_cases,
        "by_case_status": by_case_status,
        "case_statuses": case_statuses,
        "by_authority_blocker": (
            dict(review_index.get("by_authority_blocker"))
            if isinstance(review_index.get("by_authority_blocker"), dict)
            else {}
        ),
        "by_measured_gate_blocker": (
            dict(review_index.get("by_measured_gate_blocker"))
            if isinstance(review_index.get("by_measured_gate_blocker"), dict)
            else {}
        ),
        "by_mechanical_blocker": (
            dict(review_index.get("by_mechanical_blocker"))
            if isinstance(review_index.get("by_mechanical_blocker"), dict)
            else {}
        ),
        "by_promotion_policy_blocker": (
            dict(review_index.get("by_promotion_policy_blocker"))
            if isinstance(review_index.get("by_promotion_policy_blocker"), dict)
            else {}
        ),
        "by_support_status": (
            dict(review_index.get("by_support_status"))
            if isinstance(review_index.get("by_support_status"), dict)
            else {}
        ),
        "by_verdict_authority_mode": (
            dict(review_index.get("by_verdict_authority_mode"))
            if isinstance(review_index.get("by_verdict_authority_mode"), dict)
            else {}
        ),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "pending_count": len(pending_review),
        "accepted_by_verdict_authority_mode": accepted_by_verdict_authority_mode,
        "rejected_by_verdict_authority_mode": rejected_by_verdict_authority_mode,
        "pending_by_verdict_authority_mode": pending_by_verdict_authority_mode,
        "accepted_by_support_status": accepted_by_support_status,
        "rejected_by_support_status": rejected_by_support_status,
        "pending_by_support_status": pending_by_support_status,
        "invalid_decision_count": len(invalid_decisions),
        "all_decisions_valid": not invalid_decisions,
        "accepted": accepted,
        "rejected": rejected,
        "pending_review": pending_review,
        "invalid_decisions": invalid_decisions,
    }


def write_support_registry_update(
    output_path: Path,
    review_index_or_path: Mapping[str, Any] | Path | str,
    decisions_or_path: Mapping[str, Any] | Path | str,
) -> Dict[str, Any]:
    payload = build_support_registry_update(review_index_or_path, decisions_or_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def _registry_items(payload: Mapping[str, Any]) -> List[Dict[str, Any]]:
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    return [_normalize_registry_item(item) for item in items if isinstance(item, dict)]


def _registry_decision_history(payload: Mapping[str, Any]) -> List[Dict[str, Any]]:
    history = payload.get("decision_history") if isinstance(payload.get("decision_history"), list) else []
    return [_normalize_registry_decision_history_entry(item) for item in history if isinstance(item, dict)]


def _normalize_registry_decision_history_entry(entry: Mapping[str, Any]) -> Dict[str, Any]:
    normalized = dict(entry)
    schema_upgrade_applied = normalized.get("schema_upgrade_applied") is True
    schema_upgrade_reasons = [
        str(reason).strip()
        for reason in (normalized.get("schema_upgrade_reasons") or [])
        if isinstance(reason, str) and str(reason).strip()
    ]

    def _note_upgrade(reason: str) -> None:
        nonlocal schema_upgrade_applied
        token = str(reason).strip()
        if not token:
            return
        schema_upgrade_applied = True
        if token not in schema_upgrade_reasons:
            schema_upgrade_reasons.append(token)

    decision = str(normalized.get("decision") or "").strip().lower() or None
    if decision is not None and normalized.get("decision") != decision:
        normalized["decision"] = decision
    else:
        normalized["decision"] = decision

    if normalized.get("oracle_execution_parity") is None:
        normalized["oracle_execution_parity"] = "missing"
        _note_upgrade("oracle_execution_parity_defaulted")
    else:
        normalized["oracle_execution_parity"] = (
            str(normalized.get("oracle_execution_parity") or "").strip().lower() or "missing"
        )

    support_status = str(normalized.get("support_status") or "").strip() or None
    if support_status is None:
        if decision == "accept":
            support_status = "reviewable"
            _note_upgrade("support_status_from_decision_default")
        elif decision == "reject":
            support_status = "blocked_unclassified"
            _note_upgrade("support_status_from_decision_default")
    normalized["support_status"] = support_status

    if not isinstance(normalized.get("mechanically_healthy"), bool) and decision == "accept":
        normalized["mechanically_healthy"] = True
        _note_upgrade("mechanically_healthy_from_decision_default")
    elif not isinstance(normalized.get("mechanically_healthy"), bool):
        normalized["mechanically_healthy"] = None

    if not isinstance(normalized.get("promotion_policy_ready"), bool) and decision == "accept":
        normalized["promotion_policy_ready"] = True
        _note_upgrade("promotion_policy_ready_from_decision_default")
    elif not isinstance(normalized.get("promotion_policy_ready"), bool):
        normalized["promotion_policy_ready"] = None

    for field in (
        "case_name",
        "slug",
        "vuln_id",
        "rationale",
        "reviewer",
        "selected_family",
        "selected_stack_id",
        "topology",
        "verdict_authority_mode",
        "support_candidate_path",
        "manifest_path",
        "summary_path",
        "workspace",
        "review_index_path",
        "decision_source_path",
    ):
        normalized[field] = str(normalized.get(field) or "").strip() or None

    for field in ("verdict_authority_consistent", "verdict_authority_ready", "measured_gate_ready"):
        normalized[field] = normalized.get(field) if isinstance(normalized.get(field), bool) else None

    normalized["schema_status"] = _schema_record_status(schema_upgrade_applied)
    normalized["schema_upgrade_applied"] = schema_upgrade_applied
    normalized["schema_upgrade_reasons"] = schema_upgrade_reasons
    return normalized


def _normalize_registry_update_entry(entry: Mapping[str, Any]) -> Dict[str, Any]:
    normalized = dict(entry)
    schema_upgrade_applied = normalized.get("schema_upgrade_applied") is True
    schema_upgrade_reasons = [
        str(reason).strip()
        for reason in (normalized.get("schema_upgrade_reasons") or [])
        if isinstance(reason, str) and str(reason).strip()
    ]

    def _note_upgrade(reason: str) -> None:
        nonlocal schema_upgrade_applied
        token = str(reason).strip()
        if not token:
            return
        schema_upgrade_applied = True
        if token not in schema_upgrade_reasons:
            schema_upgrade_reasons.append(token)

    scalar_zero_fields = (
        "accepted_count",
        "rejected_count",
        "pending_count",
        "invalid_decision_count",
        "authority_ready_bundle_count",
        "authority_blocked_bundle_count",
        "measured_gate_ready_bundle_count",
        "measured_gate_blocked_bundle_count",
        "mechanically_healthy_bundle_count",
        "mechanically_blocked_bundle_count",
        "promotion_policy_ready_bundle_count",
        "promotion_policy_blocked_bundle_count",
        "schema_upgraded_item_count",
    )
    for field in scalar_zero_fields:
        if normalized.get(field) is None:
            normalized[field] = 0
            _note_upgrade(f"{field}_defaulted")

    dict_zero_fields = (
        "by_authority_blocker",
        "by_measured_gate_blocker",
        "by_mechanical_blocker",
        "by_promotion_policy_blocker",
        "by_support_status",
        "accepted_by_verdict_authority_mode",
        "rejected_by_verdict_authority_mode",
        "pending_by_verdict_authority_mode",
        "accepted_by_support_status",
        "rejected_by_support_status",
        "pending_by_support_status",
        "by_schema_upgrade_reason",
    )
    for field in dict_zero_fields:
        value = normalized.get(field)
        if not isinstance(value, dict):
            normalized[field] = {}
            _note_upgrade(f"{field}_defaulted")
        else:
            normalized[field] = dict(value)

    explicit_status = str(normalized.get("schema_status") or "").strip()
    explicit_registry_status = str(normalized.get("registry_schema_status") or "").strip()
    registry_scope_statuses = {
        "normalized",
        "legacy_items_present",
        "legacy_updates_present",
        "legacy_decisions_present",
        "legacy_mixed_present",
    }
    registry_status = ""
    if explicit_registry_status in registry_scope_statuses:
        registry_status = explicit_registry_status
    elif explicit_status in registry_scope_statuses and not schema_upgrade_applied:
        registry_status = explicit_status

    normalized["schema_status"] = registry_status or _schema_record_status(schema_upgrade_applied)
    normalized["schema_upgrade_applied"] = schema_upgrade_applied
    normalized["schema_upgrade_reasons"] = schema_upgrade_reasons
    normalized["registry_schema_status"] = registry_status or None
    return normalized


def _registry_schema_status(
    *,
    schema_upgraded_item_count: int,
    schema_upgraded_update_count: int,
    schema_upgraded_decision_event_count: int,
) -> str:
    scopes = 0
    if int(schema_upgraded_item_count or 0) > 0:
        scopes += 1
    if int(schema_upgraded_update_count or 0) > 0:
        scopes += 1
    if int(schema_upgraded_decision_event_count or 0) > 0:
        scopes += 1
    if scopes == 0:
        return "normalized"
    if scopes > 1:
        return "legacy_mixed_present"
    if int(schema_upgraded_item_count or 0) > 0:
        return "legacy_items_present"
    if int(schema_upgraded_update_count or 0) > 0:
        return "legacy_updates_present"
    return "legacy_decisions_present"


def _schema_record_status(schema_upgrade_applied: bool) -> str:
    return "legacy_upgraded" if schema_upgrade_applied else "normalized"


def _registry_update_history(payload: Mapping[str, Any]) -> List[Dict[str, Any]]:
    history = payload.get("update_history") if isinstance(payload.get("update_history"), list) else []
    return [_normalize_registry_update_entry(item) for item in history if isinstance(item, dict)]


def _registry_item_index(items: Sequence[Mapping[str, Any]]) -> Dict[tuple[str, str], Dict[str, Any]]:
    indexed: Dict[tuple[str, str], Dict[str, Any]] = {}
    for item in items:
        case_name = str(item.get("case_name") or "").strip()
        slug = str(item.get("slug") or "").strip()
        if not case_name or not slug:
            continue
        indexed[(case_name, slug)] = dict(item)
    return indexed


def _registry_decision_event(
    registry_update: Mapping[str, Any],
    entry: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "case_name": str(entry.get("case_name") or "").strip() or None,
        "slug": str(entry.get("slug") or "").strip() or None,
        "vuln_id": str(entry.get("vuln_id") or "").strip() or None,
        "decision": str(entry.get("decision") or "").strip().lower() or None,
        "rationale": str(entry.get("rationale") or "").strip() or None,
        "reviewer": str(entry.get("reviewer") or "").strip() or None,
        "selected_family": str(entry.get("selected_family") or "").strip() or None,
        "selected_stack_id": str(entry.get("selected_stack_id") or "").strip() or None,
        "topology": str(entry.get("topology") or "").strip() or None,
        "oracle_execution_parity": str(entry.get("oracle_execution_parity") or "").strip().lower() or "missing",
        "support_status": str(entry.get("support_status") or "").strip() or None,
        "verdict_authority_mode": str(entry.get("verdict_authority_mode") or "").strip() or None,
        "verdict_authority_consistent": entry.get("verdict_authority_consistent"),
        "verdict_authority_ready": entry.get("verdict_authority_ready"),
        "measured_gate_ready": entry.get("measured_gate_ready"),
        "mechanically_healthy": entry.get("mechanically_healthy"),
        "promotion_policy_ready": entry.get("promotion_policy_ready"),
        "support_candidate_path": str(entry.get("support_candidate_path") or "").strip() or None,
        "manifest_path": str(entry.get("manifest_path") or "").strip() or None,
        "summary_path": str(entry.get("summary_path") or "").strip() or None,
        "workspace": str(entry.get("workspace") or "").strip() or None,
        "review_index_path": str(registry_update.get("review_index_path") or "").strip() or None,
        "decision_source_path": str(registry_update.get("decision_source_path") or "").strip() or None,
    }


def _registry_merge_conflicts(prior_item: Mapping[str, Any], entry: Mapping[str, Any]) -> List[str]:
    conflicts: List[str] = []
    for field in ("vuln_id", "selected_family", "selected_stack_id", "topology"):
        prior_value = str(prior_item.get(field) or "").strip()
        next_value = str(entry.get(field) or "").strip()
        if prior_value and next_value and prior_value != next_value:
            conflicts.append(field)
    return conflicts


def _registry_item_source_artifacts(event: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "support_candidate_path": str(event.get("support_candidate_path") or "").strip() or None,
        "manifest_path": str(event.get("manifest_path") or "").strip() or None,
        "summary_path": str(event.get("summary_path") or "").strip() or None,
        "workspace": str(event.get("workspace") or "").strip() or None,
        "review_index_path": str(event.get("review_index_path") or "").strip() or None,
        "decision_source_path": str(event.get("decision_source_path") or "").strip() or None,
    }


def _count_registry_decisions(history: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    accepted = 0
    rejected = 0
    for entry in history:
        decision = str(entry.get("decision") or "").strip().lower()
        if decision == "accept":
            accepted += 1
        elif decision == "reject":
            rejected += 1
    return {
        "accepted_count": accepted,
        "rejected_count": rejected,
    }


def _normalize_registry_item(item: Mapping[str, Any]) -> Dict[str, Any]:
    normalized = dict(item)
    history = [dict(entry) for entry in normalized.get("history", []) if isinstance(entry, dict)]
    explicit_last_decision = (
        dict(normalized.get("last_decision"))
        if isinstance(normalized.get("last_decision"), dict)
        else None
    )
    last_event = explicit_last_decision or (dict(history[-1]) if history else None)
    counts = _count_registry_decisions(history)
    schema_upgrade_applied = normalized.get("schema_upgrade_applied") is True
    schema_upgrade_reasons = [
        str(reason).strip()
        for reason in (normalized.get("schema_upgrade_reasons") or [])
        if isinstance(reason, str) and str(reason).strip()
    ]

    def _note_upgrade(reason: str) -> None:
        nonlocal schema_upgrade_applied
        token = str(reason).strip()
        if not token:
            return
        schema_upgrade_applied = True
        if token not in schema_upgrade_reasons:
            schema_upgrade_reasons.append(token)

    accepted_count = normalized.get("accepted_count")
    if accepted_count is None and counts["accepted_count"] > 0:
        accepted_count = counts["accepted_count"]
        _note_upgrade("accepted_count_from_history")
    rejected_count = normalized.get("rejected_count")
    if rejected_count is None and counts["rejected_count"] > 0:
        rejected_count = counts["rejected_count"]
        _note_upgrade("rejected_count_from_history")

    review_status = str(normalized.get("review_status") or "").strip().lower() or None
    if review_status is None and isinstance(last_event, dict):
        decision = str(last_event.get("decision") or "").strip().lower()
        if decision == "accept":
            review_status = "accepted"
            _note_upgrade("review_status_from_last_decision")
        elif decision == "reject":
            review_status = "rejected"
            _note_upgrade("review_status_from_last_decision")

    support_status = str(normalized.get("support_status") or "").strip() or None
    if support_status is None and isinstance(last_event, dict):
        support_status = str(last_event.get("support_status") or "").strip() or None
        if support_status:
            _note_upgrade("support_status_from_last_event")
    if support_status is None and review_status == "accepted":
        support_status = "reviewable"
        _note_upgrade("support_status_from_review_status_default")
    elif support_status is None and review_status == "rejected":
        support_status = "blocked_unclassified"
        _note_upgrade("support_status_from_review_status_default")

    mechanically_healthy = normalized.get("mechanically_healthy")
    if not isinstance(mechanically_healthy, bool) and isinstance(last_event, dict) and isinstance(last_event.get("mechanically_healthy"), bool):
        mechanically_healthy = last_event.get("mechanically_healthy")
        _note_upgrade("mechanically_healthy_from_last_event")
    elif not isinstance(mechanically_healthy, bool) and review_status == "accepted":
        mechanically_healthy = True
        _note_upgrade("mechanically_healthy_from_review_status_default")

    promotion_policy_ready = normalized.get("promotion_policy_ready")
    if not isinstance(promotion_policy_ready, bool) and isinstance(last_event, dict) and isinstance(last_event.get("promotion_policy_ready"), bool):
        promotion_policy_ready = last_event.get("promotion_policy_ready")
        _note_upgrade("promotion_policy_ready_from_last_event")
    elif not isinstance(promotion_policy_ready, bool) and review_status == "accepted":
        promotion_policy_ready = True
        _note_upgrade("promotion_policy_ready_from_review_status_default")

    decision_history_count = normalized.get("decision_history_count")
    if decision_history_count is None and history:
        decision_history_count = len(history)
        _note_upgrade("decision_history_count_from_history")

    source_artifacts = (
        dict(normalized.get("source_artifacts"))
        if isinstance(normalized.get("source_artifacts"), dict)
        else {}
    )
    merged_source_artifacts = {
        key: _prefer_registry_str(
            source_artifacts.get(key),
            normalized.get(key),
        )
        for key in (
            "support_candidate_path",
            "manifest_path",
            "summary_path",
            "workspace",
            "review_index_path",
            "decision_source_path",
        )
    }
    if isinstance(last_event, dict):
        merged_source_artifacts = {
            key: _prefer_registry_str(
                merged_source_artifacts.get(key),
                last_event.get(key),
            )
            for key in merged_source_artifacts.keys()
        }
    if merged_source_artifacts != source_artifacts:
        _note_upgrade("source_artifacts_backfilled")

    normalized["history"] = history
    normalized["last_decision"] = last_event
    normalized["accepted_count"] = int(accepted_count or 0)
    normalized["rejected_count"] = int(rejected_count or 0)
    normalized["review_status"] = review_status
    normalized["support_status"] = support_status
    normalized["mechanically_healthy"] = mechanically_healthy if isinstance(mechanically_healthy, bool) else None
    normalized["promotion_policy_ready"] = (
        promotion_policy_ready if isinstance(promotion_policy_ready, bool) else None
    )
    normalized["decision_history_count"] = int(decision_history_count or 0)
    normalized["source_artifacts"] = merged_source_artifacts
    normalized["schema_status"] = _schema_record_status(schema_upgrade_applied)
    normalized["schema_upgrade_applied"] = schema_upgrade_applied
    normalized["schema_upgrade_reasons"] = schema_upgrade_reasons
    return normalized


def _prefer_registry_str(new_value: Any, prior_value: Any) -> str | None:
    new_token = str(new_value or "").strip()
    if new_token:
        return new_token
    prior_token = str(prior_value or "").strip()
    return prior_token or None


def _prefer_registry_bool(new_value: Any, prior_value: Any) -> bool | None:
    if isinstance(new_value, bool):
        return new_value
    if isinstance(prior_value, bool):
        return prior_value
    return None


def _merged_registry_source_artifacts(
    prior_item: Mapping[str, Any],
    event: Mapping[str, Any],
) -> Dict[str, Any]:
    prior_source = (
        prior_item.get("source_artifacts")
        if isinstance(prior_item.get("source_artifacts"), dict)
        else {}
    )
    current_source = _registry_item_source_artifacts(event)
    return {
        key: _prefer_registry_str(current_source.get(key), prior_source.get(key))
        for key in (
            "support_candidate_path",
            "manifest_path",
            "summary_path",
            "workspace",
            "review_index_path",
            "decision_source_path",
        )
    }


def _case_review_status_from_counts(*, accepted_count: int, rejected_count: int, item_count: int) -> str:
    if accepted_count >= item_count and item_count > 0:
        return "all_accepted"
    if rejected_count >= item_count and item_count > 0:
        return "all_rejected"
    return "mixed_review_status"


def _derive_registry_case_review_statuses(items: Sequence[Mapping[str, Any]]) -> tuple[Dict[str, int], List[Dict[str, Any]]]:
    per_case: Dict[str, Dict[str, Any]] = {}
    for item in items:
        case_name = str(item.get("case_name") or "").strip()
        if not case_name:
            continue
        bucket = per_case.setdefault(
            case_name,
            {
                "case_name": case_name,
                "item_count": 0,
                "accepted_item_count": 0,
                "rejected_item_count": 0,
                "mechanically_healthy_item_count": 0,
                "mechanically_blocked_item_count": 0,
                "promotion_policy_ready_item_count": 0,
                "promotion_policy_blocked_item_count": 0,
                "by_review_status": {},
                "by_support_status": {},
            },
        )
        bucket["item_count"] += 1
        review_status = str(item.get("review_status") or "").strip().lower()
        if review_status:
            by_review_status = bucket["by_review_status"]
            by_review_status[review_status] = by_review_status.get(review_status, 0) + 1
        if review_status == "accepted":
            bucket["accepted_item_count"] += 1
        elif review_status == "rejected":
            bucket["rejected_item_count"] += 1
        support_status = str(item.get("support_status") or "").strip()
        if support_status:
            by_support_status = bucket["by_support_status"]
            by_support_status[support_status] = by_support_status.get(support_status, 0) + 1
        if item.get("mechanically_healthy") is True:
            bucket["mechanically_healthy_item_count"] += 1
        elif item.get("mechanically_healthy") is False:
            bucket["mechanically_blocked_item_count"] += 1
        if item.get("promotion_policy_ready") is True:
            bucket["promotion_policy_ready_item_count"] += 1
        elif item.get("promotion_policy_ready") is False:
            bucket["promotion_policy_blocked_item_count"] += 1

    by_case_review_status: Dict[str, int] = {}
    case_review_statuses: List[Dict[str, Any]] = []
    for case_name in sorted(per_case):
        bucket = per_case[case_name]
        case_review_status = _case_review_status_from_counts(
            accepted_count=int(bucket["accepted_item_count"] or 0),
            rejected_count=int(bucket["rejected_item_count"] or 0),
            item_count=int(bucket["item_count"] or 0),
        )
        bucket["case_review_status"] = case_review_status
        by_case_review_status[case_review_status] = by_case_review_status.get(case_review_status, 0) + 1
        case_review_statuses.append(bucket)
    return by_case_review_status, case_review_statuses


def build_curated_support_registry(
    registry_update_or_path: Mapping[str, Any] | Path | str,
    *,
    existing_registry: Mapping[str, Any] | Path | str | None = None,
) -> Dict[str, Any]:
    registry_update = _load_json_like(registry_update_or_path)
    if int(registry_update.get("invalid_decision_count") or 0) > 0:
        raise ValueError("support registry update has invalid decisions")

    existing_payload = _load_json_like(existing_registry)
    items = _registry_items(existing_payload)
    decision_history = _registry_decision_history(existing_payload)
    update_history = _registry_update_history(existing_payload)
    indexed_items = _registry_item_index(items)

    accepted = registry_update.get("accepted") if isinstance(registry_update.get("accepted"), list) else []
    rejected = registry_update.get("rejected") if isinstance(registry_update.get("rejected"), list) else []
    pending_review = (
        registry_update.get("pending_review")
        if isinstance(registry_update.get("pending_review"), list)
        else []
    )

    accepted_applied_count = 0
    rejected_logged_count = 0

    for entry in accepted:
        if not isinstance(entry, dict):
            continue
        if entry.get("verdict_authority_ready") is not True:
            raise ValueError("accepted registry entry is not verdict-authority ready")
        if entry.get("measured_gate_ready") is not True:
            raise ValueError("accepted registry entry is not measured-gate ready")

        event = _normalize_registry_decision_history_entry(_registry_decision_event(registry_update, entry))
        decision_history.append(event)

        case_name = str(entry.get("case_name") or "").strip()
        slug = str(entry.get("slug") or "").strip()
        key = (case_name, slug)
        prior_item = indexed_items.get(key, {})
        conflict_fields = _registry_merge_conflicts(prior_item, entry)
        if conflict_fields:
            raise ValueError(
                "registry merge conflict for "
                f"{case_name}/{slug}: {', '.join(conflict_fields)}"
            )
        prior_history = (
            [dict(item) for item in prior_item.get("history", []) if isinstance(item, dict)]
            if isinstance(prior_item.get("history"), list)
            else []
        )
        prior_history.append(event)
        indexed_items[key] = {
            "case_name": case_name or None,
            "slug": slug or None,
            "vuln_id": _prefer_registry_str(entry.get("vuln_id"), prior_item.get("vuln_id")),
            "selected_family": _prefer_registry_str(entry.get("selected_family"), prior_item.get("selected_family")),
            "selected_stack_id": _prefer_registry_str(entry.get("selected_stack_id"), prior_item.get("selected_stack_id")),
            "topology": _prefer_registry_str(entry.get("topology"), prior_item.get("topology")),
            "oracle_execution_parity": _prefer_registry_str(
                str(entry.get("oracle_execution_parity") or "").strip().lower() or None,
                prior_item.get("oracle_execution_parity"),
            )
            or "missing",
            "support_status": _prefer_registry_str(entry.get("support_status"), "reviewable"),
            "verdict_authority_mode": _prefer_registry_str(
                entry.get("verdict_authority_mode"),
                prior_item.get("verdict_authority_mode"),
            ),
            "verdict_authority_consistent": entry.get("verdict_authority_consistent"),
            "verdict_authority_ready": _prefer_registry_bool(
                entry.get("verdict_authority_ready"),
                prior_item.get("verdict_authority_ready"),
            ),
            "measured_gate_ready": _prefer_registry_bool(
                entry.get("measured_gate_ready"),
                prior_item.get("measured_gate_ready"),
            ),
            "mechanically_healthy": _prefer_registry_bool(
                entry.get("mechanically_healthy"),
                True,
            ),
            "promotion_policy_ready": _prefer_registry_bool(
                entry.get("promotion_policy_ready"),
                True,
            ),
            "support_candidate_path": _prefer_registry_str(
                entry.get("support_candidate_path"),
                prior_item.get("support_candidate_path"),
            ),
            "manifest_path": _prefer_registry_str(entry.get("manifest_path"), prior_item.get("manifest_path")),
            "summary_path": _prefer_registry_str(entry.get("summary_path"), prior_item.get("summary_path")),
            "workspace": _prefer_registry_str(entry.get("workspace"), prior_item.get("workspace")),
            "accepted_count": int(prior_item.get("accepted_count") or 0) + 1,
            "rejected_count": int(prior_item.get("rejected_count") or 0),
            "review_status": "accepted",
            "decision_history_count": len(prior_history),
            "last_decision": event,
            "source_artifacts": _merged_registry_source_artifacts(prior_item, event),
            "schema_status": _schema_record_status(prior_item.get("schema_upgrade_applied") is True),
            "schema_upgrade_applied": prior_item.get("schema_upgrade_applied") is True,
            "schema_upgrade_reasons": [
                str(reason).strip()
                for reason in (prior_item.get("schema_upgrade_reasons") or [])
                if isinstance(reason, str) and str(reason).strip()
            ],
            "history": prior_history,
        }
        accepted_applied_count += 1

    for entry in rejected:
        if not isinstance(entry, dict):
            continue
        event = _normalize_registry_decision_history_entry(_registry_decision_event(registry_update, entry))
        decision_history.append(event)
        case_name = str(entry.get("case_name") or "").strip()
        slug = str(entry.get("slug") or "").strip()
        key = (case_name, slug)
        prior_item = indexed_items.get(key)
        if isinstance(prior_item, dict):
            conflict_fields = _registry_merge_conflicts(prior_item, entry)
            if conflict_fields:
                raise ValueError(
                    "registry merge conflict for "
                    f"{case_name}/{slug}: {', '.join(conflict_fields)}"
                )
            prior_history = (
                [dict(item) for item in prior_item.get("history", []) if isinstance(item, dict)]
                if isinstance(prior_item.get("history"), list)
                else []
            )
            prior_history.append(event)
            updated_item = dict(prior_item)
            updated_item["decision_history_count"] = len(prior_history)
            updated_item["rejected_count"] = int(prior_item.get("rejected_count") or 0) + 1
            updated_item["review_status"] = "rejected"
            updated_item["support_status"] = _prefer_registry_str(
                entry.get("support_status"),
                "reviewable",
            )
            updated_item["mechanically_healthy"] = _prefer_registry_bool(
                entry.get("mechanically_healthy"),
                True,
            )
            updated_item["promotion_policy_ready"] = _prefer_registry_bool(
                entry.get("promotion_policy_ready"),
                True,
            )
            updated_item["last_decision"] = event
            updated_item["source_artifacts"] = _merged_registry_source_artifacts(updated_item, event)
            updated_item["history"] = prior_history
            updated_item["schema_status"] = _schema_record_status(updated_item.get("schema_upgrade_applied") is True)
            indexed_items[key] = updated_item
        rejected_logged_count += 1

    merged_items = sorted(
        indexed_items.values(),
        key=lambda item: (str(item.get("case_name") or ""), str(item.get("slug") or "")),
    )
    by_selected_family: Dict[str, int] = {}
    by_topology: Dict[str, int] = {}
    by_verdict_authority_mode: Dict[str, int] = {}
    by_review_status: Dict[str, int] = {}
    by_support_status: Dict[str, int] = {}
    by_item_schema_status: Dict[str, int] = {}
    by_schema_upgrade_reason: Dict[str, int] = {}
    by_decision_schema_upgrade_reason: Dict[str, int] = {}
    mechanically_healthy_item_count = 0
    mechanically_blocked_item_count = 0
    promotion_policy_ready_item_count = 0
    promotion_policy_blocked_item_count = 0
    items_with_source_artifacts_count = 0
    schema_upgraded_item_count = 0
    schema_upgraded_update_count = 0
    schema_upgraded_decision_event_count = 0
    by_update_schema_status: Dict[str, int] = {}
    by_decision_schema_status: Dict[str, int] = {}
    by_update_schema_upgrade_reason: Dict[str, int] = {}
    for item in merged_items:
        selected_family = str(item.get("selected_family") or "").strip()
        topology = str(item.get("topology") or "").strip()
        verdict_authority_mode = str(item.get("verdict_authority_mode") or "").strip()
        review_status = str(item.get("review_status") or "").strip().lower()
        support_status = str(item.get("support_status") or "").strip()
        source_artifacts = item.get("source_artifacts") if isinstance(item.get("source_artifacts"), dict) else {}
        item_schema_status = str(item.get("schema_status") or "").strip() or "normalized"
        if selected_family:
            by_selected_family[selected_family] = by_selected_family.get(selected_family, 0) + 1
        if topology:
            by_topology[topology] = by_topology.get(topology, 0) + 1
        if verdict_authority_mode:
            by_verdict_authority_mode[verdict_authority_mode] = (
                by_verdict_authority_mode.get(verdict_authority_mode, 0) + 1
            )
        if review_status:
            by_review_status[review_status] = by_review_status.get(review_status, 0) + 1
        if support_status:
            by_support_status[support_status] = by_support_status.get(support_status, 0) + 1
        by_item_schema_status[item_schema_status] = by_item_schema_status.get(item_schema_status, 0) + 1
        if item.get("mechanically_healthy") is True:
            mechanically_healthy_item_count += 1
        elif item.get("mechanically_healthy") is False:
            mechanically_blocked_item_count += 1
        if item.get("promotion_policy_ready") is True:
            promotion_policy_ready_item_count += 1
        elif item.get("promotion_policy_ready") is False:
            promotion_policy_blocked_item_count += 1
        if any(str(value).strip() for value in source_artifacts.values()):
            items_with_source_artifacts_count += 1
        if item.get("schema_upgrade_applied") is True:
            schema_upgraded_item_count += 1
        for reason in item.get("schema_upgrade_reasons") or []:
            token = str(reason).strip()
            if token:
                by_schema_upgrade_reason[token] = by_schema_upgrade_reason.get(token, 0) + 1
    for entry in update_history:
        update_schema_status = str(entry.get("schema_status") or "").strip() or "normalized"
        by_update_schema_status[update_schema_status] = by_update_schema_status.get(update_schema_status, 0) + 1
        if entry.get("schema_upgrade_applied") is True:
            schema_upgraded_update_count += 1
        for reason in entry.get("schema_upgrade_reasons") or []:
            token = str(reason).strip()
            if token:
                by_update_schema_upgrade_reason[token] = by_update_schema_upgrade_reason.get(token, 0) + 1
    for event in decision_history:
        decision_schema_status = str(event.get("schema_status") or "").strip() or "normalized"
        by_decision_schema_status[decision_schema_status] = (
            by_decision_schema_status.get(decision_schema_status, 0) + 1
        )
        if event.get("schema_upgrade_applied") is True:
            schema_upgraded_decision_event_count += 1
        for reason in event.get("schema_upgrade_reasons") or []:
            token = str(reason).strip()
            if token:
                by_decision_schema_upgrade_reason[token] = by_decision_schema_upgrade_reason.get(token, 0) + 1
    by_decision: Dict[str, int] = {}
    by_reviewer: Dict[str, int] = {}
    for event in decision_history:
        decision = str(event.get("decision") or "").strip().lower()
        reviewer = str(event.get("reviewer") or "").strip()
        if decision:
            by_decision[decision] = by_decision.get(decision, 0) + 1
        if reviewer:
            by_reviewer[reviewer] = by_reviewer.get(reviewer, 0) + 1
    by_case_review_status, case_review_statuses = _derive_registry_case_review_statuses(merged_items)
    all_accepted_cases = _case_names_for_status(
        case_review_statuses,
        status_key="case_review_status",
        target_statuses=("all_accepted",),
    )
    mixed_review_status_cases = _case_names_for_status(
        case_review_statuses,
        status_key="case_review_status",
        target_statuses=("mixed_review_status",),
    )
    all_rejected_cases = _case_names_for_status(
        case_review_statuses,
        status_key="case_review_status",
        target_statuses=("all_rejected",),
    )

    overall_schema_status = _registry_schema_status(
        schema_upgraded_item_count=schema_upgraded_item_count,
        schema_upgraded_update_count=schema_upgraded_update_count,
        schema_upgraded_decision_event_count=schema_upgraded_decision_event_count,
    )

    last_update = {
        "review_index_path": str(registry_update.get("review_index_path") or "").strip() or None,
        "decision_source_path": str(registry_update.get("decision_source_path") or "").strip() or None,
        "accepted_count": int(registry_update.get("accepted_count") or 0),
        "rejected_count": int(registry_update.get("rejected_count") or 0),
        "pending_count": int(registry_update.get("pending_count") or 0),
        "invalid_decision_count": int(registry_update.get("invalid_decision_count") or 0),
        "authority_ready_bundle_count": int(registry_update.get("authority_ready_bundle_count") or 0),
        "authority_blocked_bundle_count": int(registry_update.get("authority_blocked_bundle_count") or 0),
        "measured_gate_ready_bundle_count": int(registry_update.get("measured_gate_ready_bundle_count") or 0),
        "measured_gate_blocked_bundle_count": int(registry_update.get("measured_gate_blocked_bundle_count") or 0),
        "mechanically_healthy_bundle_count": int(registry_update.get("mechanically_healthy_bundle_count") or 0),
        "mechanically_blocked_bundle_count": int(registry_update.get("mechanically_blocked_bundle_count") or 0),
        "promotion_policy_ready_bundle_count": int(registry_update.get("promotion_policy_ready_bundle_count") or 0),
        "promotion_policy_blocked_bundle_count": int(registry_update.get("promotion_policy_blocked_bundle_count") or 0),
        "reviewable_case_count": int(registry_update.get("reviewable_case_count") or 0),
        "blocked_case_count": int(registry_update.get("blocked_case_count") or 0),
        "all_reviewable_case_count": int(registry_update.get("all_reviewable_case_count") or 0),
        "mixed_case_count": int(registry_update.get("mixed_case_count") or 0),
        "all_blocked_case_count": int(registry_update.get("all_blocked_case_count") or 0),
        "reviewable_cases": [
            str(case).strip()
            for case in (registry_update.get("reviewable_cases") or [])
            if isinstance(case, str) and str(case).strip()
        ],
        "blocked_cases": [
            str(case).strip()
            for case in (registry_update.get("blocked_cases") or [])
            if isinstance(case, str) and str(case).strip()
        ],
        "all_reviewable_cases": [
            str(case).strip()
            for case in (registry_update.get("all_reviewable_cases") or [])
            if isinstance(case, str) and str(case).strip()
        ],
        "mixed_cases": [
            str(case).strip()
            for case in (registry_update.get("mixed_cases") or [])
            if isinstance(case, str) and str(case).strip()
        ],
        "all_blocked_cases": [
            str(case).strip()
            for case in (registry_update.get("all_blocked_cases") or [])
            if isinstance(case, str) and str(case).strip()
        ],
        "by_case_status": (
            dict(registry_update.get("by_case_status"))
            if isinstance(registry_update.get("by_case_status"), dict)
            else {}
        ),
        "case_statuses": [
            dict(entry)
            for entry in (registry_update.get("case_statuses") or [])
            if isinstance(entry, dict)
        ],
        "by_authority_blocker": (
            dict(registry_update.get("by_authority_blocker"))
            if isinstance(registry_update.get("by_authority_blocker"), dict)
            else {}
        ),
        "by_measured_gate_blocker": (
            dict(registry_update.get("by_measured_gate_blocker"))
            if isinstance(registry_update.get("by_measured_gate_blocker"), dict)
            else {}
        ),
        "by_mechanical_blocker": (
            dict(registry_update.get("by_mechanical_blocker"))
            if isinstance(registry_update.get("by_mechanical_blocker"), dict)
            else {}
        ),
        "by_promotion_policy_blocker": (
            dict(registry_update.get("by_promotion_policy_blocker"))
            if isinstance(registry_update.get("by_promotion_policy_blocker"), dict)
            else {}
        ),
        "by_support_status": (
            dict(registry_update.get("by_support_status"))
            if isinstance(registry_update.get("by_support_status"), dict)
            else {}
        ),
        "accepted_by_verdict_authority_mode": (
            dict(registry_update.get("accepted_by_verdict_authority_mode"))
            if isinstance(registry_update.get("accepted_by_verdict_authority_mode"), dict)
            else {}
        ),
        "rejected_by_verdict_authority_mode": (
            dict(registry_update.get("rejected_by_verdict_authority_mode"))
            if isinstance(registry_update.get("rejected_by_verdict_authority_mode"), dict)
            else {}
        ),
        "pending_by_verdict_authority_mode": (
            dict(registry_update.get("pending_by_verdict_authority_mode"))
            if isinstance(registry_update.get("pending_by_verdict_authority_mode"), dict)
            else {}
        ),
        "accepted_by_support_status": (
            dict(registry_update.get("accepted_by_support_status"))
            if isinstance(registry_update.get("accepted_by_support_status"), dict)
            else {}
        ),
        "rejected_by_support_status": (
            dict(registry_update.get("rejected_by_support_status"))
            if isinstance(registry_update.get("rejected_by_support_status"), dict)
            else {}
        ),
        "pending_by_support_status": (
            dict(registry_update.get("pending_by_support_status"))
            if isinstance(registry_update.get("pending_by_support_status"), dict)
            else {}
        ),
        "schema_upgraded_item_count": schema_upgraded_item_count,
        "by_schema_upgrade_reason": by_schema_upgrade_reason,
        "schema_upgraded_decision_event_count": schema_upgraded_decision_event_count,
        "by_decision_schema_upgrade_reason": by_decision_schema_upgrade_reason,
        "schema_status": overall_schema_status,
        "registry_schema_status": overall_schema_status,
    }
    last_update["schema_upgrade_applied"] = False
    last_update["schema_upgrade_reasons"] = []
    update_history.append(dict(last_update))

    by_update_schema_status = {}
    for entry in update_history:
        update_schema_status = str(entry.get("schema_status") or "").strip() or "normalized"
        by_update_schema_status[update_schema_status] = by_update_schema_status.get(update_schema_status, 0) + 1

    return {
        "schema_version": "curated_support_registry@0.1",
        "registry_item_count": len(merged_items),
        "accepted_applied_count": accepted_applied_count,
        "rejected_logged_count": rejected_logged_count,
        "pending_count": len([item for item in pending_review if isinstance(item, dict)]),
        "decision_history_count": len(decision_history),
        "update_count": len(update_history),
        "by_selected_family": by_selected_family,
        "by_topology": by_topology,
        "by_verdict_authority_mode": by_verdict_authority_mode,
        "by_review_status": by_review_status,
        "by_support_status": by_support_status,
        "by_case_review_status": by_case_review_status,
        "all_accepted_case_count": len(all_accepted_cases),
        "mixed_review_status_case_count": len(mixed_review_status_cases),
        "all_rejected_case_count": len(all_rejected_cases),
        "all_accepted_cases": all_accepted_cases,
        "mixed_review_status_cases": mixed_review_status_cases,
        "all_rejected_cases": all_rejected_cases,
        "by_item_schema_status": by_item_schema_status,
        "by_schema_upgrade_reason": by_schema_upgrade_reason,
        "mechanically_healthy_item_count": mechanically_healthy_item_count,
        "mechanically_blocked_item_count": mechanically_blocked_item_count,
        "promotion_policy_ready_item_count": promotion_policy_ready_item_count,
        "promotion_policy_blocked_item_count": promotion_policy_blocked_item_count,
        "items_with_source_artifacts_count": items_with_source_artifacts_count,
        "schema_upgraded_item_count": schema_upgraded_item_count,
        "schema_upgraded_update_count": schema_upgraded_update_count,
        "schema_upgraded_decision_event_count": schema_upgraded_decision_event_count,
        "schema_status": overall_schema_status,
        "by_update_schema_status": by_update_schema_status,
        "by_decision_schema_status": by_decision_schema_status,
        "by_update_schema_upgrade_reason": by_update_schema_upgrade_reason,
        "by_decision_schema_upgrade_reason": by_decision_schema_upgrade_reason,
        "by_decision": by_decision,
        "by_reviewer": by_reviewer,
        "case_review_statuses": case_review_statuses,
        "last_update": last_update,
        "items": merged_items,
        "decision_history": decision_history,
        "update_history": update_history,
    }


def write_curated_support_registry(
    output_path: Path,
    registry_update_or_path: Mapping[str, Any] | Path | str,
    *,
    existing_registry: Mapping[str, Any] | Path | str | None = None,
) -> Dict[str, Any]:
    base_registry = existing_registry
    if base_registry is None and output_path.exists():
        base_registry = output_path
    payload = build_curated_support_registry(
        registry_update_or_path,
        existing_registry=base_registry,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload
