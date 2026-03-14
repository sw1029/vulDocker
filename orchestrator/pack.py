"""PACK stage consolidating artifacts."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.logging import get_logger
from common.name_only import build_name_only_contract
from common.paths import ensure_dir, get_artifacts_dir, get_metadata_dir, get_workspace_dir
from common.plan import load_plan
from common.vuln_catalog import vuln_catalog_entries
from common.contracts import (
    executor_feasibility_summary,
    load_generator_contract,
    load_semantic_profile,
    lower_bound_summary,
)
from common.rules import load_static_rule
from agents.generator.compiler import supported_compiler_strategies
from orchestrator.plugins.react_loop import _FAMILY_HINTS
from common.run_matrix import (
    artifacts_dir_for_bundle,
    bundle_requirement,
    load_vuln_bundles,
    metadata_dir_for_bundle,
    workspace_dir_for_bundle,
)

LOGGER = get_logger(__name__)


def _normalized_family_key(value: Any) -> str:
    token = str(value or "").strip().lower()
    if not token:
        return ""
    return re.sub(r"[^a-z0-9]+", "", token)


def _family_keys_match(left: Any, right: Any) -> bool:
    left_key = _normalized_family_key(left)
    right_key = _normalized_family_key(right)
    if not left_key or not right_key:
        return False
    if left_key == right_key:
        return True
    aliases = {
        "sqli": {"sqli", "sqlinjection"},
        "sqlinjection": {"sqli", "sqlinjection"},
        "openredirect": {"openredirect"},
        "templateinjection": {"templateinjection", "ssti"},
        "ssti": {"templateinjection", "ssti"},
    }
    left_aliases = aliases.get(left_key, {left_key})
    right_aliases = aliases.get(right_key, {right_key})
    return bool(left_aliases & right_aliases)


def _verification_independence(rule_source: Any, trust: Any, explicit: Any = None) -> str:
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    source = str(rule_source or "").strip().lower()
    trust_level = str(trust or "").strip().lower()
    if source == "declared_rule":
        return "independent"
    if source == "compiler_runtime_rule":
        return "compiler_coupled"
    if source == "contract_oracle_fallback":
        return "contract_coupled"
    if source in {"runtime_rule_candidate", "generator_manifest_fallback", "verifier_runtime_rule_fallback"}:
        return "self_derived"
    if trust_level == "low":
        return "self_derived"
    return ""


def _minimum_promotion_independence(requirement: Any) -> str:
    if not isinstance(requirement, dict):
        return "compiler_coupled"
    policy = requirement.get("policy")
    if not isinstance(policy, dict):
        return "compiler_coupled"
    verifier = policy.get("verifier")
    if not isinstance(verifier, dict):
        return "compiler_coupled"
    token = str(verifier.get("min_promotion_independence") or "compiler_coupled").strip().lower()
    if token not in {"compiler_coupled", "independent"}:
        return "compiler_coupled"
    return token


def _minimum_name_resolution_confidence(requirement: Any) -> str:
    if not isinstance(requirement, dict):
        return "low"
    policy = requirement.get("policy")
    if not isinstance(policy, dict):
        return "low"
    verifier = policy.get("verifier")
    if not isinstance(verifier, dict):
        return "low"
    token = str(verifier.get("min_name_resolution_confidence") or "low").strip().lower()
    if token not in {"low", "medium", "high"}:
        return "low"
    return token


def _independence_rank(value: Any) -> int:
    token = str(value or "").strip().lower()
    if token == "independent":
        return 2
    if token == "compiler_coupled":
        return 1
    if token == "contract_coupled":
        return 0
    if token == "self_derived":
        return 0
    return -1


def _confidence_rank(value: Any) -> int:
    token = str(value or "").strip().lower()
    if token == "high":
        return 2
    if token == "medium":
        return 1
    if token == "low":
        return 0
    return -1


def _stable_reason_token(value: Any) -> str:
    token = str(value or "").strip().lower()
    if not token:
        return ""
    if re.fullmatch(r"[a-z0-9_-]+", token):
        return token
    return ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pack artifacts for a SID")
    parser.add_argument("--sid", required=True, help="Scenario ID")
    parser.add_argument(
        "--allow-intentional-vuln",
        action="store_true",
        help="Bypass REVIEW blocking gate when plan.policy.allow_intentional_vuln is true.",
    )
    return parser.parse_args()


def snapshot_workspace(sid: str) -> Path:
    workspace = get_workspace_dir(sid)
    destination = ensure_dir(get_artifacts_dir(sid) / "build" / "source_snapshot")
    target = destination / "app"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(workspace, target)
    LOGGER.info("Workspace snapshot copied to %s", target)
    return target


def assert_review_passed(sid: str, plan: dict, allow_intentional: bool) -> None:
    loop_state_path = get_metadata_dir(sid) / "loop_state.json"
    if not loop_state_path.exists():
        return
    state = json.loads(loop_state_path.read_text(encoding="utf-8"))
    last_result = state.get("last_result")
    if last_result and last_result != "success":
        policy_allows = plan.get("policy", {}).get("allow_intentional_vuln")
        if allow_intentional and policy_allows:
            LOGGER.warning(
                "Bypassing REVIEW gate for %s (intentional vulnerability flag enabled).",
                sid,
            )
            return
        raise RuntimeError(
            f"Cannot pack {sid}: loop controller last_result={last_result}. "
            "Complete the REVIEW loop (fix + re-run) before PACK or rerun with "
            "--allow-intentional-vuln when plan.policy.allow_intentional_vuln is true."
        )


def write_manifest(sid: str, plan: dict, *, filename: str | None = None) -> Path:
    metadata_dir = get_metadata_dir(sid)
    artifacts_dir = get_artifacts_dir(sid)
    bundles = _collect_bundle_records(plan, sid)
    reports_dir = artifacts_dir / "reports"
    performance = _load_json(metadata_dir / "performance_summary.json")
    promotion = _promotion_summary(bundles)
    memory_promotion = _memory_promotion_summary(bundles)
    support_promotion = _support_promotion_summary(bundles)
    open_world_readiness_summary = _open_world_readiness_summary(bundles)
    boundedness_summary = _boundedness_summary()
    generation_summary = _generation_summary(bundles)
    dynamic_eval_summary = _dynamic_eval_summary(bundles)
    generalization_summary = _generalization_summary(bundles)
    open_world_summary = _open_world_summary(bundles)
    strict_open_world_summary = _strict_open_world_summary(bundles)
    compiler_contract_summary = _compiler_contract_summary(bundles)
    verification_summary = _verification_summary(bundles)
    researcher_summary = _researcher_summary(bundles)
    request_identity_summary = _request_identity_summary(bundles)
    request_ir_summary = _request_ir_summary(bundles)
    name_resolution_summary = _name_resolution_summary(bundles)
    lower_bound_rollup = _lower_bound_rollup(bundles)
    executor_feasibility_rollup = _executor_feasibility_rollup(bundles)
    artifact_quality_summary = _artifact_quality_summary(bundles)
    evidence_graph_summary = _evidence_graph_summary(bundles)
    template_dependence_summary = _template_dependence_summary(bundles)
    stack_dependence_summary = _stack_dependence_summary(bundles)
    family_dependence_summary = _family_dependence_summary(bundles)
    runtime_surface_summary = _runtime_surface_summary(bundles)
    partial_progress_summary = _partial_progress_summary(bundles)
    completion_summary = _completion_summary(bundles)
    intent_satisfaction_summary = _intent_satisfaction_summary(bundles)
    name_only_outcome_summary = _name_only_outcome_summary(bundles)
    name_only_planning_summary = _name_only_planning_summary(bundles)
    failure = _failure_summary(sid)
    pipeline_result = _pipeline_result(sid, bundles=bundles, failure=failure)
    if not filename:
        filename = "manifest.json" if pipeline_result == "success" else "failure_manifest.json"
    manifest = {
        "sid": sid,
        "packed_at": datetime.now(timezone.utc).isoformat(),
        "variation_key": plan.get("variation_key"),
        "paths": plan.get("paths"),
        "status": pipeline_result,
        "pipeline_result": pipeline_result,
        "features": plan.get("features", {}),
        "policy": plan.get("policy", {}),
        "vuln_ids": plan.get("vuln_ids") or [plan.get("requirement", {}).get("vuln_id")],
        "effective_vuln_ids_digest": plan.get("effective_vuln_ids_digest"),
        "vuln_ids_digest": plan.get("vuln_ids_digest"),
        "sid_inputs": plan.get("sid_inputs", {}),
        "bundles": bundles,
        "promotion": promotion,
        "memory_promotion": memory_promotion,
        "support_promotion": support_promotion,
        "open_world_readiness_summary": open_world_readiness_summary,
        "boundedness_summary": boundedness_summary,
        "generation_summary": generation_summary,
        "dynamic_eval_summary": dynamic_eval_summary,
        "generalization_summary": generalization_summary,
        "open_world_summary": open_world_summary,
        "strict_open_world_summary": strict_open_world_summary,
        "compiler_contract_summary": compiler_contract_summary,
        "verification_summary": verification_summary,
        "researcher_summary": researcher_summary,
        "request_identity_summary": request_identity_summary,
        "request_ir_summary": request_ir_summary,
        "name_resolution_summary": name_resolution_summary,
        "lower_bound_summary": lower_bound_rollup,
        "executor_feasibility_summary": executor_feasibility_rollup,
        "artifact_quality_summary": artifact_quality_summary,
        "evidence_graph_summary": evidence_graph_summary,
        "template_dependence_summary": template_dependence_summary,
        "stack_dependence_summary": stack_dependence_summary,
        "family_dependence_summary": family_dependence_summary,
        "runtime_surface_summary": runtime_surface_summary,
        "partial_progress_summary": partial_progress_summary,
        "completion_summary": completion_summary,
        "intent_satisfaction_summary": intent_satisfaction_summary,
        "name_only_outcome_summary": name_only_outcome_summary,
        "name_only_planning_summary": name_only_planning_summary,
        "performance": performance,
        "indices": _collect_indices(metadata_dir, artifacts_dir),
        "reports": {
            "evals": _load_json(reports_dir / "evals.json"),
            "diversity": _load_json(reports_dir / "diversity.json"),
        },
    }
    requirement = plan.get("requirement") if isinstance(plan, dict) else {}
    if isinstance(requirement, dict):
        request_ir = requirement.get("request_ir")
        if isinstance(request_ir, dict) and request_ir:
            manifest["request_ir"] = request_ir
        name_resolution = requirement.get("name_resolution")
        if isinstance(name_resolution, dict) and name_resolution:
            manifest["name_resolution"] = name_resolution
    if failure:
        manifest["failure"] = failure
        for key, target in (
            ("stage", "failure_stage"),
            ("reason", "failure_reason"),
            ("fix_hint", "failure_fix_hint"),
            ("terminal_failure_class", "terminal_failure_class"),
        ):
            value = failure.get(key)
            if isinstance(value, str) and value.strip():
                manifest[target] = value.strip()
        retry_recommended = failure.get("retry_recommended")
        if isinstance(retry_recommended, bool):
            manifest["retry_recommended"] = retry_recommended
    if len(bundles) == 1:
        provenance = bundles[0].get("provenance") or {}
        if isinstance(provenance.get("generation_origin"), str) and provenance.get("generation_origin", "").strip():
            manifest["generation_origin"] = provenance["generation_origin"].strip()
        for key in ("fallback_used", "family_override_applied", "llm_stub_used", "llm_fixture_used"):
            value = provenance.get(key)
            if isinstance(value, bool):
                manifest[key] = value
        for key in ("semantic_guided_selection_source", "semantic_guided_abstain_reason"):
            value = provenance.get(key)
            if isinstance(value, str) and value.strip():
                manifest[key] = value.strip()
        semantic_guided_ambiguous = provenance.get("semantic_guided_ambiguous")
        if isinstance(semantic_guided_ambiguous, bool):
            manifest["semantic_guided_ambiguous"] = semantic_guided_ambiguous
        dynamicness = bundles[0].get("dynamicness") or {}
        if isinstance(dynamicness.get("verdict"), str) and dynamicness.get("verdict", "").strip():
            manifest["dynamicness_verdict"] = dynamicness["verdict"].strip()
        if isinstance(dynamicness.get("reason"), str) and dynamicness.get("reason", "").strip():
            manifest["dynamicness_reason"] = dynamicness["reason"].strip()
        compiler_contract = bundles[0].get("compiler_contract") or {}
        if isinstance(compiler_contract.get("compiler_supported"), bool):
            manifest["compiler_supported"] = compiler_contract["compiler_supported"]
        for key in (
            "compiler_strategy",
            "compiler_reason",
            "compiler_family",
            "stack_scaffold_id",
            "stack_scaffold_version",
            "fragment_id",
            "compose_mode",
        ):
            value = compiler_contract.get(key)
            if isinstance(value, str) and value.strip():
                manifest[key] = value.strip()
        verification = bundles[0].get("verification") or {}
        if isinstance(verification.get("rule_source"), str) and verification.get("rule_source", "").strip():
            manifest["verification_rule_source"] = verification["rule_source"].strip()
        if isinstance(verification.get("trust"), str) and verification.get("trust", "").strip():
            manifest["verification_trust"] = verification["trust"].strip()
        if isinstance(verification.get("independence"), str) and verification.get("independence", "").strip():
            manifest["verification_independence"] = verification["independence"].strip()
        if isinstance(verification.get("trust_reason"), str) and verification.get("trust_reason", "").strip():
            manifest["verification_trust_reason"] = verification["trust_reason"].strip()
        semantic = bundles[0].get("semantic") or {}
        if isinstance(semantic, dict):
            if isinstance(semantic.get("supported"), bool):
                manifest["semantic_supported"] = semantic["supported"]
            if isinstance(semantic.get("status"), str) and semantic.get("status", "").strip():
                manifest["semantic_status"] = semantic["status"].strip()
            if isinstance(semantic.get("source"), str) and semantic.get("source", "").strip():
                manifest["semantic_source"] = semantic["source"].strip()
        generalization = bundles[0].get("generalization") or {}
        class_name = generalization.get("class")
        if isinstance(class_name, str) and class_name.strip():
            manifest["generalization_class"] = class_name.strip()
        if isinstance(generalization.get("counts_as_generalization"), bool):
            manifest["counts_as_generalization"] = generalization["counts_as_generalization"]
        reason = generalization.get("reason")
        if isinstance(reason, str) and reason.strip():
            manifest["generalization_reason"] = reason.strip()
        confidence = generalization.get("confidence")
        if isinstance(confidence, str) and confidence.strip():
            manifest["generalization_confidence"] = confidence.strip()
        basis = generalization.get("basis")
        if isinstance(basis, str) and basis.strip():
            manifest["generalization_basis"] = basis.strip()
        open_world = bundles[0].get("open_world") or {}
        class_name = open_world.get("class")
        if isinstance(class_name, str) and class_name.strip():
            manifest["open_world_class"] = class_name.strip()
        if isinstance(open_world.get("counts_as_generalization"), bool):
            manifest["counts_as_open_world_generalization"] = open_world["counts_as_generalization"]
        reason = open_world.get("reason")
        if isinstance(reason, str) and reason.strip():
            manifest["open_world_reason"] = reason.strip()
        confidence = open_world.get("confidence")
        if isinstance(confidence, str) and confidence.strip():
            manifest["open_world_confidence"] = confidence.strip()
        basis = open_world.get("basis")
        if isinstance(basis, str) and basis.strip():
            manifest["open_world_basis"] = basis.strip()
        strict_open_world = bundles[0].get("strict_open_world") or {}
        class_name = strict_open_world.get("class")
        if isinstance(class_name, str) and class_name.strip():
            manifest["strict_open_world_class"] = class_name.strip()
        if isinstance(strict_open_world.get("counts_as_generalization"), bool):
            manifest["counts_as_strict_open_world_generalization"] = strict_open_world["counts_as_generalization"]
        reason = strict_open_world.get("reason")
        if isinstance(reason, str) and reason.strip():
            manifest["strict_open_world_reason"] = reason.strip()
        lower_bound = bundles[0].get("lower_bound") or {}
        if isinstance(lower_bound, dict) and lower_bound:
            manifest["lower_bound"] = lower_bound
            for key in ("family_non_remote_available", "effective_non_remote_available", "compiler_path_enabled"):
                value = lower_bound.get(key)
                if isinstance(value, bool):
                    manifest[key] = value
        runtime_recipe = bundles[0].get("runtime_recipe") or {}
        if isinstance(runtime_recipe, dict) and runtime_recipe:
            manifest["runtime_recipe"] = runtime_recipe
        runtime_graph = bundles[0].get("runtime_graph") or {}
        if isinstance(runtime_graph, dict) and runtime_graph:
            manifest["runtime_graph"] = runtime_graph
        exploit_oracle = bundles[0].get("exploit_oracle") or {}
        if isinstance(exploit_oracle, dict) and exploit_oracle:
            manifest["exploit_oracle"] = exploit_oracle
        evidence_graph = bundles[0].get("evidence_graph") or {}
        if isinstance(evidence_graph, dict) and evidence_graph:
            manifest["evidence_graph"] = evidence_graph
            manifest["evidence_graph_summary"] = _evidence_graph_summary(bundles)
        name_only_generation_spec = bundles[0].get("name_only_generation_spec") or {}
        if isinstance(name_only_generation_spec, dict) and name_only_generation_spec:
            manifest["name_only_generation_spec"] = name_only_generation_spec
            planning_focus_summary = (
                name_only_generation_spec.get("planning_focus_summary")
                if isinstance(name_only_generation_spec.get("planning_focus_summary"), dict)
                else {}
            )
            if planning_focus_summary:
                manifest["name_only_planning_focus"] = planning_focus_summary
                primary_focus = planning_focus_summary.get("primary_focus")
                if isinstance(primary_focus, str) and primary_focus.strip():
                    manifest["name_only_primary_focus"] = primary_focus.strip()
        dynamic_eval = bundles[0].get("dynamic_eval") or {}
        if isinstance(dynamic_eval, dict) and dynamic_eval:
            manifest["dynamic_eval"] = dynamic_eval
        artifact_quality = bundles[0].get("artifact_quality") or {}
        if isinstance(artifact_quality, dict) and artifact_quality:
            manifest["artifact_quality"] = artifact_quality
        stack_dependence = bundles[0].get("stack_dependence") or {}
        if isinstance(stack_dependence, dict) and stack_dependence:
            manifest["stack_dependence"] = stack_dependence
        family_dependence = bundles[0].get("family_dependence") or {}
        if isinstance(family_dependence, dict) and family_dependence:
            manifest["family_dependence"] = family_dependence
        intent_satisfaction = bundles[0].get("intent_satisfaction") or {}
        if isinstance(intent_satisfaction, dict) and intent_satisfaction:
            manifest["intent_satisfaction"] = intent_satisfaction
            status = intent_satisfaction.get("status")
            if isinstance(status, str) and status.strip():
                manifest["intent_satisfaction_status"] = status.strip()
        name_only_outcome = bundles[0].get("name_only_outcome") or {}
        if isinstance(name_only_outcome, dict) and name_only_outcome:
            manifest["name_only_outcome"] = name_only_outcome
            decision = name_only_outcome.get("decision")
            if isinstance(decision, str) and decision.strip():
                manifest["name_only_decision"] = decision.strip()
                manifest["meets_name_only_intent"] = decision.strip() == "intent_met"
            next_required_step = name_only_outcome.get("next_required_step")
            if isinstance(next_required_step, str) and next_required_step.strip():
                manifest["name_only_next_required_step"] = next_required_step.strip()
        researcher = bundles[0].get("researcher") or {}
        if isinstance(researcher, dict) and researcher:
            manifest["researcher"] = researcher
        request_identity = bundles[0].get("request_identity") or {}
        if isinstance(request_identity, dict) and request_identity:
            manifest["request_identity"] = request_identity
        request_ir = bundles[0].get("request_ir") or {}
        if isinstance(request_ir, dict) and request_ir:
            manifest["request_ir"] = request_ir
        memory_promotion_payload = bundles[0].get("memory_promotion") or {}
        if isinstance(memory_promotion_payload, dict) and memory_promotion_payload:
            manifest["memory_promotion"] = memory_promotion_payload
            if isinstance(memory_promotion_payload.get("eligible"), bool):
                manifest["memory_promotion_eligible"] = memory_promotion_payload["eligible"]
        support_promotion_payload = bundles[0].get("support_promotion") or {}
        if isinstance(support_promotion_payload, dict) and support_promotion_payload:
            manifest["support_promotion"] = support_promotion_payload
            if isinstance(support_promotion_payload.get("eligible"), bool):
                manifest["support_promotion_eligible"] = support_promotion_payload["eligible"]
        open_world_readiness_payload = bundles[0].get("open_world_readiness") or {}
        if isinstance(open_world_readiness_payload, dict) and open_world_readiness_payload:
            manifest["open_world_readiness"] = open_world_readiness_payload
            if isinstance(open_world_readiness_payload.get("ready"), bool):
                manifest["open_world_ready"] = open_world_readiness_payload["ready"]
        completion_state = bundles[0].get("completion_state") or {}
        if isinstance(completion_state, dict) and completion_state:
            manifest["completion_state"] = completion_state
            stage_ceiling = completion_state.get("stage_ceiling")
            if isinstance(stage_ceiling, str) and stage_ceiling.strip():
                manifest["stage_ceiling"] = stage_ceiling.strip()
            fully_validated = completion_state.get("fully_validated")
            if isinstance(fully_validated, bool):
                manifest["fully_validated"] = fully_validated
        executor_feasibility = bundles[0].get("executor_feasibility") or {}
        if isinstance(executor_feasibility, dict) and executor_feasibility:
            manifest["executor_feasibility"] = executor_feasibility
            status = executor_feasibility.get("status")
            if isinstance(status, str) and status.strip():
                manifest["executor_feasibility_status"] = status.strip()
        service_env = compiler_contract.get("service_env")
        if isinstance(service_env, dict) and service_env:
            manifest["service_env"] = {
                str(key): str(value)
                for key, value in service_env.items()
                if isinstance(key, str) and key.strip() and value not in (None, "")
            }
    else:
        _apply_multibundle_top_level_rollups(manifest, bundles)
    manifest_path = metadata_dir / filename
    stale_name = "failure_manifest.json" if filename == "manifest.json" else "manifest.json"
    stale_path = metadata_dir / stale_name
    if stale_path.exists():
        stale_path.unlink()
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    LOGGER.info("Manifest written to %s", manifest_path)
    return manifest_path


def _pipeline_result(
    sid: str,
    *,
    bundles: Optional[List[Dict[str, Any]]] = None,
    failure: Optional[Dict[str, Any]] = None,
) -> str:
    loop_state_path = get_metadata_dir(sid) / "loop_state.json"
    if not loop_state_path.exists():
        if isinstance(failure, dict) and failure:
            return "failure"
        if isinstance(bundles, list) and bundles:
            for entry in bundles:
                completion = entry.get("completion_state") if isinstance(entry, dict) and isinstance(entry.get("completion_state"), dict) else {}
                if completion and completion.get("fully_validated") is not True:
                    return "failure"
            return "success"
        return "success"
    try:
        state = json.loads(loop_state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        if isinstance(failure, dict) and failure:
            return "failure"
        if isinstance(bundles, list) and bundles:
            for entry in bundles:
                completion = entry.get("completion_state") if isinstance(entry, dict) and isinstance(entry.get("completion_state"), dict) else {}
                if completion and completion.get("fully_validated") is not True:
                    return "failure"
            return "success"
        return "success"
    last_result = str(state.get("last_result") or "").strip().lower()
    if last_result in {"success", "failure"}:
        return last_result
    if isinstance(failure, dict) and failure:
        return "failure"
    if isinstance(bundles, list) and bundles:
        for entry in bundles:
            completion = entry.get("completion_state") if isinstance(entry, dict) and isinstance(entry.get("completion_state"), dict) else {}
            if completion and completion.get("fully_validated") is not True:
                return "failure"
    return "success"


def _collect_bundle_records(plan: Dict[str, Any], sid: str) -> List[Dict[str, Any]]:
    bundles: List[Dict[str, Any]] = []
    eval_data = _load_json(get_artifacts_dir(sid) / "reports" / "evals.json") or {}
    eval_results = eval_data.get("results") or []
    eval_map = {entry.get("slug") or entry.get("vuln_id"): entry for entry in eval_results}
    run_index = _load_json(get_artifacts_dir(sid) / "run" / "index.json") or {"runs": []}
    run_map = {entry.get("slug"): entry for entry in run_index.get("runs", [])}
    requirement = plan.get("requirement", {})
    dep_digest = requirement.get("deps_digest")

    for bundle in load_vuln_bundles(plan):
        metadata_dir = metadata_dir_for_bundle(plan, bundle)
        workspace_dir = workspace_dir_for_bundle(plan, bundle)
        build_dir = artifacts_dir_for_bundle(plan, bundle, "build")
        run_dir = artifacts_dir_for_bundle(plan, bundle, "run")
        requirement_view = bundle_requirement(requirement, bundle)
        researcher_report = metadata_dir / "researcher_report.json"
        generator_template = metadata_dir / "generator_template.json"
        reviewer_report = metadata_dir / "reviewer_report.json"
        generator_payload = _load_json(generator_template)
        pattern_id = (generator_payload or {}).get("pattern_id") or requirement_view.get("pattern_id")
        run_record = run_map.get(bundle.slug, {})
        eval_record = eval_map.get(bundle.slug) or eval_map.get(bundle.vuln_id)
        promotion = _bundle_promotion_status(plan, bundle)
        failure = _bundle_failure_summary(sid, bundle)
        provenance = _bundle_generation_provenance(
            sid,
            bundle,
            metadata_dir,
            generator_payload,
            bundle_failure=failure,
        )
        dynamicness = _bundle_dynamicness_verdict(provenance)
        compiler_contract = _bundle_compiler_contract(metadata_dir)
        semantic_surface = _bundle_semantic_surface(
            metadata_dir,
            bundle.vuln_id,
            eval_record,
        )
        lower_bound = _bundle_lower_bound(metadata_dir, bundle.vuln_id, requirement_view)
        executor_feasibility = _bundle_executor_feasibility(plan, bundle, requirement_view, metadata_dir)
        contract = load_generator_contract(metadata_dir) or {}
        contract_request_ir = (
            dict(contract.get("request_ir"))
            if isinstance(contract.get("request_ir"), dict)
            else {}
        )
        runtime_recipe = _bundle_runtime_recipe(
            contract=contract,
            requirement=requirement_view,
            compiler_contract=compiler_contract,
            executor_feasibility=executor_feasibility,
            provenance=provenance,
        )
        runtime_graph = _bundle_runtime_graph(
            contract=contract,
            runtime_recipe=runtime_recipe,
        )
        exploit_oracle = (
            dict(contract.get("exploit_oracle"))
            if isinstance(contract.get("exploit_oracle"), dict)
            else {}
        )
        evidence_graph = (
            dict(contract.get("evidence_graph"))
            if isinstance(contract.get("evidence_graph"), dict)
            else {}
        )
        name_only_generation_spec = (
            dict(contract.get("name_only_generation_spec"))
            if isinstance(contract.get("name_only_generation_spec"), dict)
            else {}
        )
        dynamic_eval = _bundle_dynamic_eval_summary(
            requirement=requirement_view,
            metadata_dir=metadata_dir,
        )
        researcher = _bundle_researcher_summary(
            requirement=requirement_view,
            metadata_dir=metadata_dir,
        )
        generalization = _bundle_generalization_verdict(
            bundle,
            pattern_id=pattern_id,
            promotion=promotion,
            dynamicness=dynamicness,
            compiler_contract=compiler_contract,
            provenance=provenance,
            policy=(
                requirement_view.get("policy")
                if isinstance(requirement_view.get("policy"), dict)
                else {}
            ),
            request_identity=(
                requirement_view.get("request_identity")
                if isinstance(requirement_view.get("request_identity"), dict)
                else {}
            ),
            request_ir=(
                requirement_view.get("request_ir")
                if isinstance(requirement_view.get("request_ir"), dict)
                else {}
            ),
            name_resolution=(
                requirement_view.get("name_resolution")
                if isinstance(requirement_view.get("name_resolution"), dict)
                else {}
            ),
        )
        open_world = _bundle_open_world_verdict(
            bundle,
            pattern_id=pattern_id,
            promotion=promotion,
            dynamicness=dynamicness,
            compiler_contract=compiler_contract,
            provenance=provenance,
            request_identity=(
                requirement_view.get("request_identity")
                if isinstance(requirement_view.get("request_identity"), dict)
                else {}
            ),
            request_ir=(
                requirement_view.get("request_ir")
                if isinstance(requirement_view.get("request_ir"), dict)
                else {}
            ),
            dynamic_eval=dynamic_eval,
            failure=failure,
            name_resolution=(
                requirement_view.get("name_resolution")
                if isinstance(requirement_view.get("name_resolution"), dict)
                else {}
            ),
        )
        strict_open_world = _bundle_strict_open_world_verdict(
            bundle,
            open_world=open_world,
            dynamicness=dynamicness,
            provenance=provenance,
            lower_bound=lower_bound,
            verification={
                "rule_source": (eval_record or {}).get("verification_rule_source")
                if isinstance(eval_record, dict)
                else None,
                "trust": (eval_record or {}).get("verification_trust") if isinstance(eval_record, dict) else None,
                "independence": _verification_independence(
                    (eval_record or {}).get("verification_rule_source") if isinstance(eval_record, dict) else None,
                    (eval_record or {}).get("verification_trust") if isinstance(eval_record, dict) else None,
                    (eval_record or {}).get("verification_independence") if isinstance(eval_record, dict) else None,
                ),
            },
            researcher=researcher,
            semantic=semantic_surface,
            request_identity=(
                requirement_view.get("request_identity")
                if isinstance(requirement_view.get("request_identity"), dict)
                else {}
            ),
            request_ir=(
                requirement_view.get("request_ir")
                if isinstance(requirement_view.get("request_ir"), dict)
                else {}
            ),
            dynamic_eval=dynamic_eval,
            failure=failure,
        )

        bundle_entry = {
            "vuln_id": bundle.vuln_id,
            "slug": bundle.slug,
            "pattern_id": pattern_id,
            "request_identity": (
                dict(requirement_view.get("request_identity"))
                if isinstance(requirement_view.get("request_identity"), dict)
                else {}
            ),
            "request_ir": (
                contract_request_ir
                if contract_request_ir
                else dict(requirement_view.get("request_ir"))
                if isinstance(requirement_view.get("request_ir"), dict)
                else {}
            ),
            "name_resolution": (
                dict(requirement_view.get("name_resolution"))
                if isinstance(requirement_view.get("name_resolution"), dict)
                else {}
            ),
            "promotion": promotion,
            "failure": failure,
            "provenance": provenance,
            "dynamicness": dynamicness,
            "generalization": generalization,
            "open_world": open_world,
            "strict_open_world": strict_open_world,
            "compiler_contract": compiler_contract,
            "runtime_recipe": runtime_recipe,
            "runtime_graph": runtime_graph,
            "exploit_oracle": exploit_oracle,
            "evidence_graph": evidence_graph,
            "name_only_generation_spec": name_only_generation_spec,
            "dynamic_eval": dynamic_eval,
            "researcher": researcher,
            "semantic": semantic_surface,
            "lower_bound": lower_bound,
            "executor_feasibility": executor_feasibility,
            "deps_digest": dep_digest,
            "paths": {
                "workspace": str(workspace_dir),
                "metadata": str(metadata_dir),
                "build": str(build_dir),
                "run": str(run_dir),
            },
            "artifacts": {
                "build_log": _existing(build_dir / "build.log"),
                "sbom": _existing(build_dir / "sbom.spdx.json"),
                "run_log": _existing(run_dir / "run.log"),
                "run_summary": run_record,
                "eval_result": eval_record,
            },
            "verification": {
                "rule_source": (eval_record or {}).get("verification_rule_source")
                if isinstance(eval_record, dict)
                else None,
                "trust": (eval_record or {}).get("verification_trust") if isinstance(eval_record, dict) else None,
                "independence": _verification_independence(
                    (eval_record or {}).get("verification_rule_source") if isinstance(eval_record, dict) else None,
                    (eval_record or {}).get("verification_trust") if isinstance(eval_record, dict) else None,
                    (eval_record or {}).get("verification_independence") if isinstance(eval_record, dict) else None,
                ),
                "trust_reason": (eval_record or {}).get("verification_trust_reason")
                if isinstance(eval_record, dict)
                else None,
            },
            "semantic_supported": semantic_surface.get("supported"),
            "semantic_status": semantic_surface.get("status"),
            "semantic_source": semantic_surface.get("source"),
            "researcher_report": _existing(researcher_report),
            "generator_template": _existing(generator_template),
            "reviewer_report": _existing(reviewer_report),
        }
        bundle_entry["stack_dependence"] = _bundle_stack_dependence(bundle_entry)
        bundle_entry["family_dependence"] = _bundle_family_dependence(bundle_entry)
        bundle_entry["artifact_quality"] = _bundle_artifact_quality(bundle_entry)
        bundle_entry["intent_satisfaction"] = _bundle_intent_satisfaction(bundle_entry, requirement_view)
        bundle_entry["completion_state"] = _bundle_completion_state(bundle_entry)
        bundle_entry["name_only_outcome"] = _bundle_name_only_outcome(bundle_entry)
        bundle_entry["memory_promotion"] = _bundle_memory_promotion_status(bundle_entry)
        bundle_entry["support_promotion"] = _bundle_support_promotion_status(bundle_entry)
        bundle_entry["open_world_readiness"] = _bundle_open_world_readiness(bundle_entry)
        bundles.append(bundle_entry)
    return bundles


def _bundle_promotion_status(plan: Dict[str, Any], bundle) -> Dict[str, Any]:
    metadata_dir = metadata_dir_for_bundle(plan, bundle)
    reviewer_report = _load_json(metadata_dir / "reviewer_report.json")
    run_summary = _bundle_run_summary(plan, bundle)
    eval_result = _bundle_eval_result(plan, bundle)
    contract = load_generator_contract(metadata_dir)
    requirement = plan.get("requirement") or {}
    requirement_view = bundle_requirement(requirement, bundle) if isinstance(requirement, dict) else {}
    reasons: List[str] = []
    if not isinstance(run_summary, dict):
        reasons.append("pipeline:run_missing")
    elif not bool(run_summary.get("run_passed")):
        reasons.append("pipeline:run_failed")
    if not isinstance(eval_result, dict):
        reasons.append("pipeline:verify_missing")
    elif not bool(eval_result.get("verify_pass")):
        reasons.append("pipeline:verify_failed")
    if not isinstance(reviewer_report, dict):
        reasons.append("pipeline:review_missing")
    elif bool(reviewer_report.get("blocking")) or reviewer_report.get("success") is False:
        reasons.append("pipeline:review_failed")
    elif bundle.slug in (reviewer_report.get("blocking_bundles") or []):
        reasons.append("pipeline:review_failed")
    if isinstance(eval_result, dict):
        reasons.extend(_eval_result_failure_reasons(eval_result))
        verification_trust = str(eval_result.get("verification_trust") or "").strip().lower()
        verification_rule_source = str(eval_result.get("verification_rule_source") or "").strip().lower()
        verification_independence = _verification_independence(
            verification_rule_source,
            verification_trust,
            eval_result.get("verification_independence"),
        )
        if verification_trust == "low":
            if verification_rule_source:
                reasons.append(f"verify_contract:{verification_rule_source}")
            else:
                reasons.append("verify_contract:low_trust")
        min_independence = _minimum_promotion_independence(requirement_view)
        if _independence_rank(verification_independence) < _independence_rank(min_independence):
            reasons.append(f"verify_independence:{verification_independence or 'unknown'}")
            reasons.append(f"verify_independence_policy:min_{min_independence}")
        semantic_supported = eval_result.get("semantic_supported")
        if semantic_supported is None:
            semantic = eval_result.get("semantic_consistency") or {}
            if isinstance(semantic, dict):
                semantic_supported = semantic.get("supported")
        if semantic_supported is False:
            reasons.append("verify_semantic:unsupported")
        semantic_status = str(eval_result.get("semantic_status") or "").strip().lower()
        if not semantic_status:
            semantic = eval_result.get("semantic_consistency") or {}
            if isinstance(semantic, dict):
                semantic_status = str(semantic.get("status") or "").strip().lower()
        if semantic_status in {"empty", "unsupported", "contradicted"}:
            reasons.append(f"verify_semantic_status:{semantic_status}")
    if str(getattr(bundle, "vuln_id", "") or "").strip().upper().startswith("NAME-"):
        resolution = requirement_view.get("name_resolution") if isinstance(requirement_view, dict) else {}
        resolution_confidence = str((resolution or {}).get("confidence") or "").strip().lower()
        min_confidence = _minimum_name_resolution_confidence(requirement_view)
        if (resolution_confidence or min_confidence != "low") and _confidence_rank(
            resolution_confidence
        ) < _confidence_rank(min_confidence):
            reasons.append(f"name_resolution_confidence:{resolution_confidence or 'unknown'}")
            reasons.append(f"name_resolution_policy:min_{min_confidence}")
    if isinstance(contract, dict):
        semantic_contract = contract.get("semantic_contract")
        if isinstance(semantic_contract, dict):
            contradictions = semantic_contract.get("contradictions")
            if isinstance(contradictions, list):
                reasons.extend(
                    f"semantic_contract:{str(item).strip()}"
                    for item in contradictions
                    if isinstance(item, str) and str(item).strip()
                )
            relevance = semantic_contract.get("evidence_relevance")
            if isinstance(relevance, dict) and not load_static_rule(bundle.vuln_id):
                confidence = str(relevance.get("confidence") or "").strip().lower()
                try:
                    negative_ratio = float(relevance.get("negative_hit_ratio") or 0.0)
                except Exception:
                    negative_ratio = 0.0
                if confidence == "low":
                    reasons.append("unknown_evidence:low_confidence")
                elif confidence == "medium" and negative_ratio >= 0.30:
                    reasons.append("unknown_evidence:medium_confidence_high_negative_ratio")
        provenance = contract.get("provenance")
        if isinstance(provenance, dict):
            fallback_class = str(provenance.get("fallback_class") or "").strip().lower()
            if fallback_class == "generic_unsupported_family":
                reasons.append("fallback:generic_unsupported_family")
    profile = load_semantic_profile(metadata_dir)
    if isinstance(profile, dict):
        support_level = str(profile.get("support_level") or "").strip().lower()
        compiler_supported = profile.get("compiler_supported")
        compiler_reason = str(profile.get("compiler_reason") or "").strip()
        if support_level == "unsupported" and compiler_supported is False:
            reasons.append("compiler:unsupported")
            if compiler_reason:
                reasons.append(f"compiler_reason:{compiler_reason}")
    requirement_view = bundle_requirement(requirement, bundle) if isinstance(requirement, dict) else {}
    feasibility = _bundle_executor_feasibility(plan, bundle, requirement_view, metadata_dir)
    if feasibility.get("status") == "misconfigured":
        reasons.append("executor:misconfigured")
    return {
        "eligible": not reasons,
        "reasons": reasons,
    }


def _bundle_memory_promotion_status(bundle_entry: Dict[str, Any]) -> Dict[str, Any]:
    promotion = bundle_entry.get("promotion") or {}
    strict_open_world = bundle_entry.get("strict_open_world") or {}
    artifact_quality = bundle_entry.get("artifact_quality") or {}
    reasons: List[str] = []

    if not bool((promotion or {}).get("eligible")):
        reasons.append("base_promotion:ineligible")

    strict_class = str((strict_open_world or {}).get("class") or "").strip() or "unknown"
    if strict_open_world.get("counts_as_generalization") is not True:
        reasons.append(f"strict_open_world:{strict_class}")

    quality_band = str((artifact_quality or {}).get("band") or "").strip().lower() or "unknown"
    if quality_band != "high":
        reasons.append(f"artifact_quality:{quality_band}")

    oracle_clarity = str((artifact_quality or {}).get("oracle_clarity") or "").strip().lower() or "missing"
    if oracle_clarity != "high":
        reasons.append(f"oracle_clarity:{oracle_clarity}")

    topology_clarity = str((artifact_quality or {}).get("topology_clarity") or "").strip().lower() or "missing"
    if topology_clarity not in {"high", "medium"}:
        reasons.append(f"topology_clarity:{topology_clarity}")

    return {
        "eligible": not reasons,
        "reasons": reasons,
    }


def _bundle_support_promotion_status(bundle_entry: Dict[str, Any]) -> Dict[str, Any]:
    promotion = bundle_entry.get("promotion") or {}
    open_world = bundle_entry.get("open_world") or {}
    strict_open_world = bundle_entry.get("strict_open_world") or {}
    artifact_quality = bundle_entry.get("artifact_quality") or {}
    stack_dependence = bundle_entry.get("stack_dependence") or {}
    family_dependence = bundle_entry.get("family_dependence") or {}
    name_only_outcome = bundle_entry.get("name_only_outcome") or {}
    reasons: List[str] = []

    if not bool((promotion or {}).get("eligible")):
        reasons.append("base_promotion:ineligible")

    strict_class = str((strict_open_world or {}).get("class") or "").strip() or "unknown"
    if strict_open_world.get("counts_as_generalization") is not True:
        reasons.append(f"strict_open_world:{strict_class}")

    open_world_class = str((open_world or {}).get("class") or "").strip() or "unknown"
    if open_world.get("counts_as_generalization") is not True:
        reasons.append(f"open_world:{open_world_class}")

    quality_band = str((artifact_quality or {}).get("band") or "").strip().lower() or "unknown"
    if quality_band != "high":
        reasons.append(f"artifact_quality:{quality_band}")

    oracle_clarity = str((artifact_quality or {}).get("oracle_clarity") or "").strip().lower() or "missing"
    if oracle_clarity != "high":
        reasons.append(f"oracle_clarity:{oracle_clarity}")

    topology_clarity = str((artifact_quality or {}).get("topology_clarity") or "").strip().lower() or "missing"
    if topology_clarity not in {"high", "medium"}:
        reasons.append(f"topology_clarity:{topology_clarity}")

    if (stack_dependence or {}).get("stack_defaulted") is True:
        reasons.append("stack_selection:defaulted")
    elif (stack_dependence or {}).get("repo_prior_bounded") is True:
        reasons.append("stack_selection:repo_prior_bounded")

    if (family_dependence or {}).get("candidate_evidence_backed") is not True:
        reasons.append("family_evidence:candidate_unbacked")

    if str((name_only_outcome or {}).get("decision") or "").strip().lower() != "intent_met":
        reasons.append(
            f"name_only_outcome:{str((name_only_outcome or {}).get('decision') or '').strip().lower() or 'unknown'}"
        )

    return {
        "eligible": not reasons,
        "reasons": reasons,
    }


def _eval_result_failure_reasons(eval_result: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    semantic = eval_result.get("semantic_consistency")
    if isinstance(semantic, dict) and semantic.get("supported") and not semantic.get("semantic_match"):
        errors = semantic.get("errors") or []
        if isinstance(errors, list):
            reasons.extend(
                f"verify_semantic:{str(item).strip()}"
                for item in errors
                if isinstance(item, str) and str(item).strip()
            )
        if not reasons or not any(reason.startswith("verify_semantic:") for reason in reasons):
            reasons.append("verify_semantic:mismatch")

    guard = eval_result.get("guard_consistency")
    if not isinstance(guard, dict):
        return reasons
    if guard.get("required_but_missing"):
        reasons.append("verify_guard:required_but_missing")
        return reasons

    for scope in ("verifier", "workspace"):
        scope_report = guard.get(scope)
        if not isinstance(scope_report, dict) or scope_report.get("passed") is not False:
            continue
        violations = scope_report.get("violations") or []
        if isinstance(violations, list):
            reasons.extend(
                f"verify_guard:{scope}:{str(item).strip()}"
                for item in violations
                if isinstance(item, str) and str(item).strip()
            )
        if not any(reason.startswith(f"verify_guard:{scope}:") for reason in reasons):
            reasons.append(f"verify_guard:{scope}:failed")
    return reasons


def _bundle_eval_result(plan: Dict[str, Any], bundle) -> Optional[Dict[str, Any]]:
    artifacts_root = _artifacts_root(plan)
    if artifacts_root is None:
        return None
    reports_dir = artifacts_root / "reports"
    payload = _load_json(reports_dir / "evals.json") or {}
    results = payload.get("results") if isinstance(payload, dict) else []
    if not isinstance(results, list):
        return None
    for entry in results:
        if not isinstance(entry, dict):
            continue
        if entry.get("slug") == bundle.slug or entry.get("vuln_id") == bundle.vuln_id:
            return entry
    return None


def _bundle_run_summary(plan: Dict[str, Any], bundle) -> Optional[Dict[str, Any]]:
    artifacts_root = _artifacts_root(plan)
    if artifacts_root is None:
        return None
    return _load_json(artifacts_dir_for_bundle(plan, bundle, "run") / "summary.json")


def _artifacts_root(plan: Dict[str, Any]) -> Optional[Path]:
    paths = plan.get("paths")
    if not isinstance(paths, dict):
        return None
    raw = paths.get("artifacts")
    if not isinstance(raw, str) or not raw.strip():
        return None
    return Path(raw)


def _promotion_summary(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    reasons: List[str] = []
    for entry in bundles:
        promotion = entry.get("promotion") or {}
        bundle_reasons = promotion.get("reasons") or []
        for item in bundle_reasons:
            if isinstance(item, str) and item.strip():
                reasons.append(f"{entry.get('slug')}: {item.strip()}")
    return {
        "eligible": not reasons,
        "reasons": reasons,
    }


def _memory_promotion_summary(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    reasons: List[str] = []
    eligible_bundles = 0
    for entry in bundles:
        memory_promotion = entry.get("memory_promotion") or {}
        if not isinstance(memory_promotion, dict):
            continue
        if memory_promotion.get("eligible") is True:
            eligible_bundles += 1
        bundle_reasons = memory_promotion.get("reasons") or []
        for item in bundle_reasons:
            if isinstance(item, str) and item.strip():
                reasons.append(f"{entry.get('slug')}: {item.strip()}")
    return {
        "eligible_bundles": eligible_bundles,
        "all_eligible": eligible_bundles == len(bundles) if bundles else False,
        "reasons": reasons,
    }


def _support_promotion_summary(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    reasons: List[str] = []
    eligible_bundles = 0
    for entry in bundles:
        support_promotion = entry.get("support_promotion") or {}
        if not isinstance(support_promotion, dict):
            continue
        if support_promotion.get("eligible") is True:
            eligible_bundles += 1
        bundle_reasons = support_promotion.get("reasons") or []
        for item in bundle_reasons:
            if isinstance(item, str) and item.strip():
                reasons.append(f"{entry.get('slug')}: {item.strip()}")
    return {
        "eligible_bundles": eligible_bundles,
        "all_eligible": eligible_bundles == len(bundles) if bundles else False,
        "reasons": reasons,
    }


def _boundedness_summary() -> Dict[str, Any]:
    catalog_payload = vuln_catalog_entries()
    catalog_entries = len(catalog_payload)
    catalog_families = len(
        {
            str(entry.get("family") or "").strip().lower()
            for entry in catalog_payload
            if isinstance(entry, dict) and str(entry.get("family") or "").strip()
        }
    )
    scaffold_stack_pool = len(list((REPO_ROOT / "agents" / "generator" / "assets").glob("python-*-scaffold.json")))
    template_count = len(list((REPO_ROOT / "workspaces" / "templates").rglob("template.json")))
    compiler_strategy_count = len(supported_compiler_strategies())
    family_hint_families = len(_FAMILY_HINTS)
    semantic_guided_family_builders = 12
    return {
        "catalog_entries": catalog_entries,
        "catalog_families": catalog_families,
        "family_hint_families": family_hint_families,
        "template_count": template_count,
        "scaffold_stack_pool": scaffold_stack_pool,
        "compiler_strategy_count": compiler_strategy_count,
        "semantic_guided_family_builders": semantic_guided_family_builders,
        "executor_topology_classes": ["single_service", "service_plus_sidecar"],
        "executor_multi_primary_supported": False,
        "closed_vocabulary_family_discovery": True,
        "stack_pool_bounded": True,
        "compiler_registry_bounded": True,
        "executor_topology_bounded": True,
    }


def _open_world_readiness_blockers(bundle_entry: Dict[str, Any]) -> List[str]:
    support_promotion = bundle_entry.get("support_promotion") or {}
    blockers: List[str] = []
    for item in (support_promotion.get("reasons") or []) if isinstance(support_promotion, dict) else []:
        token = str(item or "").strip()
        if not token:
            continue
        if token.startswith("strict_open_world:"):
            blockers.append("strict_open_world_gate")
        elif token.startswith("open_world:"):
            blockers.append("open_world_non_positive")
        elif token.startswith("artifact_quality:"):
            blockers.append("artifact_quality_below_high")
        elif token.startswith("oracle_clarity:"):
            blockers.append("oracle_clarity_below_high")
        elif token.startswith("topology_clarity:"):
            blockers.append("topology_clarity_below_medium")
        elif token == "stack_selection:defaulted":
            blockers.append("stack_defaulted")
        elif token == "stack_selection:repo_prior_bounded":
            blockers.append("stack_repo_prior_bounded")
        elif token.startswith("family_evidence:"):
            blockers.append("family_candidate_evidence_missing")
        elif token.startswith("name_only_outcome:"):
            blockers.append("name_only_intent_not_met")
        elif token.startswith("base_promotion:"):
            blockers.append("base_promotion_ineligible")
        else:
            blockers.append(token)
    deduped: List[str] = []
    for token in blockers:
        if token not in deduped:
            deduped.append(token)
    return deduped


def _bundle_open_world_readiness(bundle_entry: Dict[str, Any]) -> Dict[str, Any]:
    support_promotion = bundle_entry.get("support_promotion") or {}
    stack_dependence = bundle_entry.get("stack_dependence") or {}
    family_dependence = bundle_entry.get("family_dependence") or {}
    name_only_outcome = bundle_entry.get("name_only_outcome") or {}
    open_world = bundle_entry.get("open_world") or {}
    strict_open_world = bundle_entry.get("strict_open_world") or {}
    readiness = {
        "ready": bool((support_promotion or {}).get("eligible")),
        "blockers": _open_world_readiness_blockers(bundle_entry),
        "open_world_class": str((open_world or {}).get("class") or "").strip() or None,
        "strict_open_world_class": str((strict_open_world or {}).get("class") or "").strip() or None,
        "name_only_decision": str((name_only_outcome or {}).get("decision") or "").strip() or None,
        "stack_defaulted": bool((stack_dependence or {}).get("stack_defaulted")),
        "family_evidence_backed": bool((family_dependence or {}).get("candidate_evidence_backed")),
    }
    return readiness


def _open_world_readiness_summary(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    ready_bundles = 0
    by_blocker: Dict[str, int] = {}
    for entry in bundles:
        readiness = entry.get("open_world_readiness") if isinstance(entry.get("open_world_readiness"), dict) else {}
        if not readiness:
            readiness = _bundle_open_world_readiness(entry)
        if readiness.get("ready") is True:
            ready_bundles += 1
        for blocker in readiness.get("blockers") or []:
            token = str(blocker or "").strip()
            if not token:
                continue
            by_blocker[token] = by_blocker.get(token, 0) + 1
    return {
        "bundle_count": len(bundles),
        "ready_bundles": ready_bundles,
        "not_ready_bundles": len(bundles) - ready_bundles,
        "all_ready": ready_bundles == len(bundles) if bundles else False,
        "by_blocker": by_blocker,
    }


def _bundle_generation_provenance(
    sid: str,
    bundle,
    metadata_dir: Path,
    generator_template: Optional[Dict[str, Any]] = None,
    *,
    bundle_failure: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    contract = load_generator_contract(metadata_dir) or {}
    generator_manifest = _load_json(metadata_dir / "generator_manifest.json") or {}
    generator_manifest_meta = (
        (generator_manifest.get("manifest") or {}).get("metadata")
        if isinstance((generator_manifest.get("manifest") or {}), dict)
        else {}
    )
    if not isinstance(generator_manifest_meta, dict):
        generator_manifest_meta = {}
    provenance = contract.get("provenance") if isinstance(contract, dict) else {}
    if not isinstance(provenance, dict):
        provenance = {}

    def _read_str(key: str) -> Optional[str]:
        value = provenance.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(contract, dict):
            fallback = contract.get(key)
            if isinstance(fallback, str) and fallback.strip():
                return fallback.strip()
        fallback = generator_manifest_meta.get(key)
        if isinstance(fallback, str) and fallback.strip():
            return fallback.strip()
        if generator_template:
            fallback = generator_template.get(key)
            if isinstance(fallback, str) and fallback.strip():
                return fallback.strip()
        return None

    def _read_bool(key: str) -> Optional[bool]:
        for source in (
            provenance,
            contract if isinstance(contract, dict) else {},
            generator_manifest_meta,
            generator_template or {},
        ):
            value = source.get(key)
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                token = value.strip().lower()
                if token in {"true", "1", "yes", "on"}:
                    return True
                if token in {"false", "0", "no", "off"}:
                    return False
        return None

    payload: Dict[str, Any] = {}
    for key in (
        "generation_origin",
        "template_id",
        "source",
        "fallback_class",
        "materializer",
        "semantic_guided_selection_source",
        "semantic_guided_abstain_reason",
    ):
        value = _read_str(key)
        if value:
            payload[key] = value
    for key in ("fallback_used", "family_override_applied", "llm_stub_used", "llm_fixture_used"):
        value = _read_bool(key)
        if value is not None:
            payload[key] = value
    semantic_guided_ambiguous = _read_bool("semantic_guided_ambiguous")
    if semantic_guided_ambiguous is not None:
        payload["semantic_guided_ambiguous"] = semantic_guided_ambiguous
    if not payload:
        failure_payload = _latest_failure_provenance(metadata_dir)
        if failure_payload:
            payload.update(failure_payload)
    if not payload:
        loop_payload = _loop_failure_provenance(sid, bundle, bundle_failure=bundle_failure)
        if loop_payload:
            payload.update(loop_payload)
    return payload


def _latest_failure_provenance(metadata_dir: Path) -> Dict[str, Any]:
    failure_path = metadata_dir / "generator_failures.jsonl"
    if not failure_path.exists():
        return {}
    latest: Dict[str, Any] = {}
    lines = [line for line in failure_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for line in reversed(lines):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            latest = payload
            break
    if not latest:
        return {}
    provenance: Dict[str, Any] = {"source": "generator_failure_record"}
    if latest.get("fallback_used") is True:
        provenance["generation_origin"] = "deterministic_fallback"
        provenance["fallback_used"] = True
    fallback_class = str(latest.get("fallback_class") or "").strip()
    if fallback_class:
        provenance["fallback_class"] = fallback_class
    if latest.get("family_override_applied") is True:
        provenance["family_override_applied"] = True
        provenance.setdefault("generation_origin", "family_override")
    if latest.get("llm_stub_used") is True:
        provenance["llm_stub_used"] = True
    if latest.get("llm_fixture_used") is True:
        provenance["llm_fixture_used"] = True
    return provenance


def _load_loop_state(sid: str) -> Dict[str, Any]:
    return _load_json(get_metadata_dir(sid) / "loop_state.json") or {}


def _last_failure_entry(sid: str) -> Dict[str, Any]:
    state = _load_loop_state(sid)
    history = state.get("history") if isinstance(state, dict) else []
    if not isinstance(history, list):
        return {}
    for entry in reversed(history):
        if isinstance(entry, dict) and entry.get("success") is False:
            return entry
    return {}


def _failure_summary(sid: str) -> Dict[str, Any]:
    entry = _last_failure_entry(sid)
    if not entry:
        return {}
    summary: Dict[str, Any] = {}
    for key in ("stage", "reason", "fix_hint", "timestamp"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            summary[key] = value.strip()
    metadata = entry.get("metadata")
    if isinstance(metadata, dict):
        for key in ("terminal_failure_class", "retry_recommended"):
            if key in metadata:
                summary[key] = metadata.get(key)
        if metadata:
            summary["metadata"] = metadata
    return summary


def _bundle_failure_summary(sid: str, bundle) -> Dict[str, Any]:
    entry = _last_failure_entry(sid)
    if not entry:
        return {}
    metadata = entry.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    failure_bundle_slug = str(metadata.get("bundle_slug") or "").strip()
    failure_vuln_id = str(metadata.get("vuln_id") or "").strip()
    if failure_bundle_slug or failure_vuln_id:
        if failure_bundle_slug and failure_bundle_slug != bundle.slug:
            return {}
        if failure_vuln_id and failure_vuln_id != bundle.vuln_id:
            return {}
    failed_bundles = metadata.get("failed_bundles")
    failed_bundle_detail: Dict[str, Any] | None = None
    if isinstance(failed_bundles, list) and failed_bundles:
        for item in failed_bundles:
            if not isinstance(item, dict):
                continue
            if item.get("bundle_slug") == bundle.slug or item.get("vuln_id") == bundle.vuln_id:
                failed_bundle_detail = item
                break
        if failed_bundle_detail is None:
            return {}
    unsupported = metadata.get("unsupported_bundles")
    if isinstance(unsupported, list) and unsupported:
        matched = False
        for item in unsupported:
            if not isinstance(item, dict):
                continue
            if item.get("slug") == bundle.slug or item.get("vuln_id") == bundle.vuln_id:
                matched = True
                break
        if not matched:
            return {}
    summary = _failure_summary(sid)
    if not summary:
        return {}
    if failed_bundle_detail:
        for key in ("stage", "reason", "quality_reason", "terminal_failure_class", "retry_recommended"):
            value = failed_bundle_detail.get(key)
            if isinstance(value, str) and value.strip():
                if key == "quality_reason":
                    summary["reason"] = value.strip()
                else:
                    summary[key] = value.strip()
            elif isinstance(value, bool):
                summary[key] = value
        detail_metadata = dict(summary.get("metadata") or {})
        detail_metadata.update(
            {
                key: value
                for key, value in failed_bundle_detail.items()
                if key
                not in {
                    "reason",
                    "quality_reason",
                    "terminal_failure_class",
                    "retry_recommended",
                }
            }
        )
        if detail_metadata:
            summary["metadata"] = detail_metadata
    summary["bundle_slug"] = bundle.slug
    summary["vuln_id"] = bundle.vuln_id
    return summary


def _loop_failure_provenance(
    sid: str,
    bundle,
    *,
    bundle_failure: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    failure = bundle_failure or _bundle_failure_summary(sid, bundle)
    if not isinstance(failure, dict) or not failure:
        return {}
    stage = str(failure.get("stage") or "").strip().upper()
    terminal_failure_class = str(failure.get("terminal_failure_class") or "").strip().lower()
    if stage == "RESEARCH" and terminal_failure_class in {
        "semantic_support_missing",
        "remote_provider_unavailable",
        "remote_evidence_missing",
        "evidence_low_relevance",
        "provider_degraded",
        "research_insufficient",
    }:
        return {
            "generation_origin": "research_short_circuit",
            "source": "loop_state",
            "failure_class": terminal_failure_class,
            "fallback_used": False,
        }
    if stage == "CAPABILITY_CHECK" and terminal_failure_class in {
        "strict_dynamic_live_llm_unavailable",
        "strict_dynamic_remote_research_unavailable",
    }:
        metadata = failure.get("metadata") if isinstance(failure.get("metadata"), dict) else {}
        return {
            "generation_origin": "capability_gate_rejected",
            "source": "loop_state",
            "failure_class": terminal_failure_class,
            "fallback_used": False,
            "llm_stub_used": metadata.get("llm_stub_used") is True,
            "llm_fixture_used": metadata.get("llm_fixture_used") is True,
        }
    if stage == "NAME_ONLY_GATE" and terminal_failure_class == "strict_dynamic_disallowed_llm_path":
        metadata = failure.get("metadata") if isinstance(failure.get("metadata"), dict) else {}
        return {
            "generation_origin": "name_only_gate_rejected",
            "source": "loop_state",
            "failure_class": terminal_failure_class,
            "fallback_used": False,
            "llm_stub_used": metadata.get("llm_stub_used") is True,
            "llm_fixture_used": metadata.get("llm_fixture_used") is True,
        }
    return {}


def _generation_summary(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_origin: Dict[str, int] = {}
    by_dynamicness_verdict: Dict[str, int] = {}
    by_compose_mode: Dict[str, int] = {}
    by_stack_scaffold_id: Dict[str, int] = {}
    llm_stub_bundles = 0
    llm_fixture_bundles = 0
    fallback_bundles = 0
    family_override_bundles = 0
    template_origin_bundles = 0
    template_assisted_bundles = 0
    registry_compose_bundles = 0
    scaffolded_bundles = 0
    dynamic_eval_attempted_bundles = 0
    dynamic_eval_recovered_bundles = 0
    for entry in bundles:
        provenance = entry.get("provenance") or {}
        if not isinstance(provenance, dict):
            continue
        origin = str(provenance.get("generation_origin") or "").strip()
        if origin:
            by_origin[origin] = by_origin.get(origin, 0) + 1
        dynamicness = entry.get("dynamicness") or {}
        if isinstance(dynamicness, dict):
            verdict = str(dynamicness.get("verdict") or "").strip()
            if verdict:
                by_dynamicness_verdict[verdict] = by_dynamicness_verdict.get(verdict, 0) + 1
        if provenance.get("llm_stub_used") is True:
            llm_stub_bundles += 1
        if provenance.get("llm_fixture_used") is True:
            llm_fixture_bundles += 1
        if provenance.get("fallback_used") is True:
            fallback_bundles += 1
        if provenance.get("family_override_applied") is True:
            family_override_bundles += 1
        dynamic_eval = entry.get("dynamic_eval") or {}
        if isinstance(dynamic_eval, dict):
            if dynamic_eval.get("attempted") is True:
                dynamic_eval_attempted_bundles += 1
            if dynamic_eval.get("lower_bound_fallback_used") is True:
                dynamic_eval_recovered_bundles += 1
        if origin in {"built_in_template", "runtime_template_clone"}:
            template_origin_bundles += 1
            template_assisted_bundles += 1
        elif provenance.get("family_override_applied") is True or origin == "family_override":
            template_assisted_bundles += 1
        compiler_contract = entry.get("compiler_contract") or {}
        if isinstance(compiler_contract, dict):
            compose_mode = str(compiler_contract.get("compose_mode") or "").strip()
            if compose_mode:
                by_compose_mode[compose_mode] = by_compose_mode.get(compose_mode, 0) + 1
                if compose_mode == "registry":
                    registry_compose_bundles += 1
            scaffold_id = str(compiler_contract.get("stack_scaffold_id") or "").strip()
            if scaffold_id:
                by_stack_scaffold_id[scaffold_id] = by_stack_scaffold_id.get(scaffold_id, 0) + 1
                scaffolded_bundles += 1
    return {
        "bundle_count": len(bundles),
        "by_origin": by_origin,
        "by_dynamicness_verdict": by_dynamicness_verdict,
        "by_compose_mode": by_compose_mode,
        "by_stack_scaffold_id": by_stack_scaffold_id,
        "llm_stub_bundles": llm_stub_bundles,
        "llm_fixture_bundles": llm_fixture_bundles,
        "fallback_bundles": fallback_bundles,
        "family_override_bundles": family_override_bundles,
        "template_origin_bundles": template_origin_bundles,
        "template_assisted_bundles": template_assisted_bundles,
        "registry_compose_bundles": registry_compose_bundles,
        "scaffolded_bundles": scaffolded_bundles,
        "dynamic_eval_attempted_bundles": dynamic_eval_attempted_bundles,
        "dynamic_eval_recovered_bundles": dynamic_eval_recovered_bundles,
    }


def _dynamic_eval_summary(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    enabled_bundles = 0
    attempted_bundles = 0
    lower_bound_recovered_bundles = 0
    by_status: Dict[str, int] = {}
    by_fallback_path: Dict[str, int] = {}
    for entry in bundles:
        dynamic_eval = entry.get("dynamic_eval") or {}
        if not isinstance(dynamic_eval, dict):
            continue
        if dynamic_eval.get("enabled") is True:
            enabled_bundles += 1
        if dynamic_eval.get("attempted") is True:
            attempted_bundles += 1
        if dynamic_eval.get("lower_bound_fallback_used") is True:
            lower_bound_recovered_bundles += 1
        status = str(dynamic_eval.get("status") or "").strip()
        if status:
            by_status[status] = by_status.get(status, 0) + 1
        fallback_path = str(dynamic_eval.get("fallback_path") or "").strip()
        if fallback_path:
            by_fallback_path[fallback_path] = by_fallback_path.get(fallback_path, 0) + 1
    return {
        "bundle_count": len(bundles),
        "enabled_bundles": enabled_bundles,
        "attempted_bundles": attempted_bundles,
        "lower_bound_recovered_bundles": lower_bound_recovered_bundles,
        "by_status": by_status,
        "by_fallback_path": by_fallback_path,
    }


def _apply_multibundle_top_level_rollups(manifest: Dict[str, Any], bundles: List[Dict[str, Any]]) -> None:
    if not isinstance(manifest, dict) or not isinstance(bundles, list) or not bundles:
        return
    name_only_decision = _rollup_multibundle_name_only_outcome_field(bundles, key="decision")
    if name_only_decision:
        manifest["name_only_decision"] = name_only_decision
        manifest["meets_name_only_intent"] = name_only_decision == "intent_met"
    name_only_next_required_step = _rollup_multibundle_name_only_outcome_field(
        bundles,
        key="next_required_step",
    )
    if name_only_next_required_step:
        manifest["name_only_next_required_step"] = name_only_next_required_step
    generation_origin = _rollup_multibundle_string_field(bundles, section="provenance", key="generation_origin")
    if generation_origin:
        manifest["generation_origin"] = generation_origin
    dynamicness_verdict = _rollup_multibundle_string_field(bundles, section="dynamicness", key="verdict")
    if dynamicness_verdict:
        manifest["dynamicness_verdict"] = dynamicness_verdict
    verification_rule_source = _rollup_multibundle_string_field(bundles, section="verification", key="rule_source")
    if verification_rule_source:
        manifest["verification_rule_source"] = verification_rule_source
    verification_trust = _rollup_multibundle_string_field(bundles, section="verification", key="trust")
    if verification_trust:
        manifest["verification_trust"] = verification_trust
    verification_independence = _rollup_multibundle_string_field(bundles, section="verification", key="independence")
    if verification_independence:
        manifest["verification_independence"] = verification_independence
    semantic_status = _rollup_multibundle_string_field(bundles, section="semantic", key="status")
    if semantic_status:
        manifest["semantic_status"] = semantic_status
    semantic_source = _rollup_multibundle_string_field(bundles, section="semantic", key="source")
    if semantic_source:
        manifest["semantic_source"] = semantic_source
    semantic_supported = _rollup_multibundle_bool_field(bundles, section="semantic", key="supported")
    if semantic_supported is not None:
        manifest["semantic_supported"] = semantic_supported
    generalization_class = _rollup_multibundle_string_field(bundles, section="generalization", key="class")
    if generalization_class:
        manifest["generalization_class"] = generalization_class
    for key, manifest_key in (
        ("confidence", "generalization_confidence"),
        ("basis", "generalization_basis"),
    ):
        value = _rollup_multibundle_string_field(bundles, section="generalization", key=key)
        if value:
            manifest[manifest_key] = value
    counts_as_generalization = _rollup_multibundle_bool_field(
        bundles,
        section="generalization",
        key="counts_as_generalization",
    )
    if counts_as_generalization is not None:
        manifest["counts_as_generalization"] = counts_as_generalization
    open_world_class = _rollup_multibundle_string_field(bundles, section="open_world", key="class")
    if open_world_class:
        manifest["open_world_class"] = open_world_class
    for key, manifest_key in (
        ("confidence", "open_world_confidence"),
        ("basis", "open_world_basis"),
    ):
        value = _rollup_multibundle_string_field(bundles, section="open_world", key=key)
        if value:
            manifest[manifest_key] = value
    counts_as_open_world_generalization = _rollup_multibundle_bool_field(
        bundles,
        section="open_world",
        key="counts_as_generalization",
    )
    if counts_as_open_world_generalization is not None:
        manifest["counts_as_open_world_generalization"] = counts_as_open_world_generalization
    strict_open_world_class = _rollup_multibundle_string_field(bundles, section="strict_open_world", key="class")
    if strict_open_world_class:
        manifest["strict_open_world_class"] = strict_open_world_class
    counts_as_strict_open_world_generalization = _rollup_multibundle_bool_field(
        bundles,
        section="strict_open_world",
        key="counts_as_generalization",
    )
    if counts_as_strict_open_world_generalization is not None:
        manifest["counts_as_strict_open_world_generalization"] = counts_as_strict_open_world_generalization
    for key in ("stack_scaffold_id", "stack_scaffold_version", "compose_mode"):
        value = _rollup_multibundle_string_field(bundles, section="compiler_contract", key=key)
        if value:
            manifest[key] = value


def _rollup_multibundle_string_field(
    bundles: List[Dict[str, Any]],
    *,
    section: str,
    key: str,
) -> str:
    values: List[str] = []
    saw_missing = False
    for entry in bundles:
        scoped = entry.get(section) or {}
        if not isinstance(scoped, dict):
            scoped = {}
        raw = scoped.get(key)
        if isinstance(raw, str) and raw.strip():
            values.append(raw.strip())
        else:
            saw_missing = True
    if not values:
        return ""
    unique = sorted(set(values))
    if len(unique) == 1 and not saw_missing:
        return unique[0]
    return "mixed"


def _rollup_multibundle_bool_field(
    bundles: List[Dict[str, Any]],
    *,
    section: str,
    key: str,
) -> bool | None:
    values: List[bool] = []
    saw_missing = False
    for entry in bundles:
        scoped = entry.get(section) or {}
        if not isinstance(scoped, dict):
            scoped = {}
        raw = scoped.get(key)
        if isinstance(raw, bool):
            values.append(raw)
        else:
            saw_missing = True
    if not values:
        return None
    unique = set(values)
    if len(unique) == 1 and not saw_missing:
        return values[0]
    return None


def _rollup_multibundle_name_only_outcome_field(
    bundles: List[Dict[str, Any]],
    *,
    key: str,
) -> str:
    values: List[str] = []
    saw_name_only = False
    saw_missing = False
    for entry in bundles:
        outcome = entry.get("name_only_outcome") if isinstance(entry.get("name_only_outcome"), dict) else {}
        if not outcome or outcome.get("request_kind") != "name_only":
            continue
        saw_name_only = True
        raw = outcome.get(key)
        if isinstance(raw, str) and raw.strip():
            values.append(raw.strip())
        else:
            saw_missing = True
    if not saw_name_only:
        return ""
    if not values:
        return ""
    unique = sorted(set(values))
    if len(unique) == 1 and not saw_missing:
        return unique[0]
    return "mixed"


def _bundle_generalization_verdict(
    bundle,
    *,
    pattern_id: Optional[str],
    promotion: Dict[str, Any],
    dynamicness: Dict[str, Any],
    compiler_contract: Dict[str, Any],
    provenance: Dict[str, Any],
    policy: Optional[Dict[str, Any]] = None,
    request_identity: Optional[Dict[str, Any]] = None,
    request_ir: Optional[Dict[str, Any]] = None,
    name_resolution: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    vuln_id = str(getattr(bundle, "vuln_id", "") or "").strip().upper()
    pattern = str(pattern_id or "").strip()
    dynamicness_verdict = str((dynamicness or {}).get("verdict") or "").strip().lower()
    support_level = str((compiler_contract or {}).get("support_level") or "").strip().lower()
    fallback_class = str((provenance or {}).get("fallback_class") or "").strip().lower()
    materializer = str((provenance or {}).get("materializer") or "").strip().lower()
    promotion_eligible = bool((promotion or {}).get("eligible"))
    generation_origin = str((provenance or {}).get("generation_origin") or "").strip().lower()
    name_driven = _is_name_driven_request(vuln_id=vuln_id, request_identity=request_identity, request_ir=request_ir)
    resolution_context = _name_resolution_context(
        vuln_id=vuln_id,
        request_identity=request_identity,
        request_ir=request_ir,
        name_resolution=name_resolution,
    )
    resolution_confidence = resolution_context["confidence"]
    resolution_basis = resolution_context["basis"]
    effective_mode = _effective_name_only_mode(
        vuln_id=vuln_id,
        policy=policy,
        request_identity=request_identity,
        request_ir=request_ir,
    )

    if vuln_id == "CWE-9999":
        reason = "explicit synthetic unknown identifier remains a regression lane"
        if pattern and pattern != "generic-web-vuln":
            reason = f"{reason}; inherited pattern_id={pattern}"
        return {
            "class": "synthetic_regression",
            "counts_as_generalization": False,
            "reason": reason,
        }

    if vuln_id.startswith("NAME-") or (name_driven and effective_mode in {"dynamic", "dynamic_eval", "strict_dynamic"}):
        if generation_origin == "capability_gate_rejected":
            return {
                "class": "real_free_form_precondition_failed",
                "counts_as_generalization": False,
                "reason": "name-only lane failed before generation because strict open-world preconditions were unavailable",
                "confidence": resolution_confidence or "unknown",
                "basis": resolution_basis or "unknown",
            }
        if generation_origin == "name_only_gate_rejected":
            return {
                "class": "real_free_form_precondition_failed",
                "counts_as_generalization": False,
                "reason": "name-only lane failed before generation because strict live-LLM conditions were not satisfied",
                "confidence": resolution_confidence or "unknown",
                "basis": resolution_basis or "unknown",
            }
        if support_level == "unsupported" or generation_origin == "research_short_circuit":
            return {
                "class": "unsupported_free_form_negative",
                "counts_as_generalization": False,
                "reason": "name-only dynamic family is unsupported and intentionally fail-closed",
                "confidence": resolution_confidence or "low",
                "basis": resolution_basis or "synthetic_name",
            }
        if (
            promotion_eligible
            and dynamicness_verdict == "trusted dynamic"
            and fallback_class != "generic_unsupported_family"
            and resolution_confidence == "high"
            and resolution_basis in {"catalog_alias", "exact_identifier"}
        ):
            return {
                "class": "real_free_form_positive",
                "counts_as_generalization": True,
                "reason": f"name-only dynamic lane closed via {dynamicness_verdict} without generic fallback",
                "confidence": resolution_confidence or "unknown",
                "basis": resolution_basis or "unknown",
            }
        if (
            promotion_eligible
            and dynamicness_verdict == "compiler-first"
            and fallback_class != "generic_unsupported_family"
            and resolution_confidence == "high"
            and resolution_basis in {"catalog_alias", "exact_identifier"}
        ):
            return {
                "class": "real_free_form_curated_lower_bound",
                "counts_as_generalization": False,
                "reason": (
                    "name-only dynamic lane closed via compiler-first curated lower-bound support; "
                    "this is a free-form compatibility success, not open-world generalization evidence"
                ),
                "confidence": resolution_confidence or "unknown",
                "basis": resolution_basis or "unknown",
                "lower_bound_dependent": True,
                "template_dependent": False,
            }
        return {
            "class": "real_free_form_non_generalizing",
            "counts_as_generalization": False,
            "reason": (
                "name-only dynamic lane exists but is not yet strong enough to count as generalization evidence"
                if not resolution_confidence
                else (
                    "name-only dynamic lane closed but remained curated lower-bound dependent despite "
                    f"{resolution_confidence}/{resolution_basis or 'unknown'} resolution"
                    if dynamicness_verdict == "compiler-first"
                    else f"name-only dynamic lane closed but resolution confidence/basis is {resolution_confidence}/{resolution_basis or 'unknown'}"
                )
            ),
            "confidence": resolution_confidence or "unknown",
            "basis": resolution_basis or "unknown",
            "lower_bound_dependent": dynamicness_verdict == "compiler-first",
            "template_dependent": dynamicness_verdict == "template-assisted",
        }

    if support_level in {"builtin_supported", "compiler_supported"} or compiler_contract.get("compiler_supported") is True:
        return {
            "class": "known_family_regression",
            "counts_as_generalization": False,
            "reason": "compiler-supported or builtin-supported known family regression lane",
        }

    if not load_static_rule(vuln_id):
        return {
            "class": "unknown_regression",
            "counts_as_generalization": False,
            "reason": "unknown identifier without a static rule is treated as a regression lane",
        }

    return {
        "class": "known_family_regression",
        "counts_as_generalization": False,
        "reason": "known/static-rule family regression lane",
    }


def _is_name_driven_request(
    *,
    vuln_id: str,
    request_identity: Optional[Dict[str, Any]] = None,
    request_ir: Optional[Dict[str, Any]] = None,
) -> bool:
    identity = request_identity if isinstance(request_identity, dict) else {}
    ir = request_ir if isinstance(request_ir, dict) else {}
    return bool((ir or {}).get("name_driven")) or bool((identity or {}).get("name_driven")) or vuln_id.startswith("NAME-")


def _name_resolution_context(
    *,
    vuln_id: str,
    request_identity: Optional[Dict[str, Any]] = None,
    request_ir: Optional[Dict[str, Any]] = None,
    name_resolution: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    identity = request_identity if isinstance(request_identity, dict) else {}
    ir = request_ir if isinstance(request_ir, dict) else {}
    resolution = name_resolution if isinstance(name_resolution, dict) else {}
    return {
        "confidence": str(
            (ir or {}).get("resolution_confidence")
            or (identity or {}).get("confidence")
            or (resolution or {}).get("confidence")
            or ""
        ).strip().lower(),
        "basis": str(
            (ir or {}).get("resolution_match_class")
            or (identity or {}).get("match_class")
            or (resolution or {}).get("match_class")
            or ""
        ).strip().lower(),
        "resolved_vuln_id": str(
            (ir or {}).get("resolved_vuln_id")
            or (identity or {}).get("resolved_vuln_id")
            or (resolution or {}).get("resolved_vuln_id")
            or vuln_id
            or ""
        ).strip().upper(),
    }


def _effective_name_only_mode(
    *,
    vuln_id: str,
    policy: Optional[Dict[str, Any]] = None,
    request_identity: Optional[Dict[str, Any]] = None,
    request_ir: Optional[Dict[str, Any]] = None,
) -> str:
    synthetic_requirement: Dict[str, Any] = {}
    if vuln_id:
        synthetic_requirement["vuln_id"] = vuln_id
    if isinstance(policy, dict):
        synthetic_requirement["policy"] = dict(policy)
    if isinstance(request_identity, dict) and request_identity:
        synthetic_requirement["request_identity"] = dict(request_identity)
    if isinstance(request_ir, dict) and request_ir:
        synthetic_requirement["request_ir"] = dict(request_ir)
    contract = build_name_only_contract(
        requirement=synthetic_requirement,
        policy=policy if isinstance(policy, dict) else {},
    )
    return str(contract.get("effective_mode") or "").strip().lower()


def _bundle_open_world_verdict(
    bundle,
    *,
    pattern_id: Optional[str],
    promotion: Dict[str, Any],
    dynamicness: Dict[str, Any],
    compiler_contract: Dict[str, Any],
    provenance: Dict[str, Any],
    request_identity: Optional[Dict[str, Any]] = None,
    request_ir: Optional[Dict[str, Any]] = None,
    name_resolution: Optional[Dict[str, Any]] = None,
    dynamic_eval: Optional[Dict[str, Any]] = None,
    failure: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    vuln_id = str(getattr(bundle, "vuln_id", "") or "").strip().upper()
    pattern = str(pattern_id or "").strip()
    dynamicness_verdict = str((dynamicness or {}).get("verdict") or "").strip().lower()
    support_level = str((compiler_contract or {}).get("support_level") or "").strip().lower()
    fallback_class = str((provenance or {}).get("fallback_class") or "").strip().lower()
    materializer = str((provenance or {}).get("materializer") or "").strip().lower()
    promotion_eligible = bool((promotion or {}).get("eligible"))
    generation_origin = str((provenance or {}).get("generation_origin") or "").strip().lower()
    name_driven = _is_name_driven_request(vuln_id=vuln_id, request_identity=request_identity, request_ir=request_ir)
    resolution_context = _name_resolution_context(
        vuln_id=vuln_id,
        request_identity=request_identity,
        request_ir=request_ir,
        name_resolution=name_resolution,
    )
    resolution_confidence = resolution_context["confidence"]
    resolution_basis = resolution_context["basis"]
    resolved_vuln_id = resolution_context["resolved_vuln_id"]
    dynamic_eval_payload = dynamic_eval if isinstance(dynamic_eval, dict) else {}
    dynamic_eval_status = str(dynamic_eval_payload.get("status") or "").strip().lower()
    failure_payload = failure if isinstance(failure, dict) else {}
    failure_stage = str(failure_payload.get("stage") or "").strip().upper()
    failure_terminal_class = str(failure_payload.get("terminal_failure_class") or "").strip().lower()
    lower_bound_available = (
        support_level in {"builtin_supported", "compiler_supported"}
        or bool((compiler_contract or {}).get("compiler_supported"))
        or bool(load_static_rule(resolved_vuln_id or vuln_id))
    )
    template_dependent = dynamicness_verdict == "template-assisted"

    if vuln_id == "CWE-9999":
        reason = "explicit synthetic unknown identifier remains a regression lane"
        if pattern and pattern != "generic-web-vuln":
            reason = f"{reason}; inherited pattern_id={pattern}"
        return {
            "class": "synthetic_regression",
            "counts_as_generalization": False,
            "reason": reason,
            "lower_bound_dependent": False,
            "template_dependent": template_dependent,
        }

    if name_driven:
        if failure_stage == "CAPABILITY_CHECK" and failure_terminal_class in {
            "strict_dynamic_live_llm_unavailable",
            "strict_dynamic_remote_research_unavailable",
        }:
            return {
                "class": "name_driven_capability_gate_failed",
                "counts_as_generalization": False,
                "reason": (
                    "strict_dynamic rejected the name-only lane before RESEARCH because required live-LLM or "
                    "remote-research capability was unavailable"
                ),
                "confidence": resolution_confidence or "unknown",
                "basis": resolution_basis or "unknown",
                "lower_bound_dependent": False,
                "template_dependent": False,
            }
        if failure_stage == "NAME_ONLY_GATE" and failure_terminal_class == "strict_dynamic_disallowed_llm_path":
            return {
                "class": "name_driven_live_llm_gate_failed",
                "counts_as_generalization": False,
                "reason": "strict_dynamic rejected the name-only lane before generation because a live LLM path was unavailable or disallowed",
                "confidence": resolution_confidence or "unknown",
                "basis": resolution_basis or "unknown",
                "lower_bound_dependent": False,
                "template_dependent": False,
            }
        if support_level == "unsupported" or generation_origin == "research_short_circuit":
            return {
                "class": "unsupported_free_form_negative",
                "counts_as_generalization": False,
                "reason": "free-form NAME-* family is unsupported and intentionally fail-closed",
                "confidence": resolution_confidence or "low",
                "basis": resolution_basis or "synthetic_name",
                "lower_bound_dependent": False,
                "template_dependent": template_dependent,
            }
        if failure_stage == "GENERATOR" and dynamic_eval_status == "dynamic_failed":
            return {
                "class": "name_driven_dynamic_failed",
                "counts_as_generalization": False,
                "reason": (
                    "name-only lane attempted dynamic generation first, but generation failed before acceptable materialization"
                    + (f" ({failure_terminal_class})" if failure_terminal_class else "")
                ),
                "confidence": resolution_confidence or "unknown",
                "basis": resolution_basis or "unknown",
                "lower_bound_dependent": False,
                "template_dependent": False,
            }
        if (
            promotion_eligible
            and dynamicness_verdict == "trusted dynamic"
            and not lower_bound_available
            and fallback_class != "generic_unsupported_family"
            and resolution_confidence == "high"
            and resolution_basis in {"catalog_alias", "exact_identifier"}
        ):
            return {
                "class": "open_world_positive",
                "counts_as_generalization": True,
                "reason": "name-only lane closed via trusted dynamic generation without an existing curated lower bound",
                "confidence": resolution_confidence,
                "basis": resolution_basis,
                "lower_bound_dependent": False,
                "template_dependent": template_dependent,
            }
        if generation_origin == "deterministic_fallback" and fallback_class == "semantic_guided":
            return {
                "class": "semantic_guided_minimal_dynamic"
                if materializer == "minimal_dynamic"
                else "semantic_guided_degraded",
                "counts_as_generalization": False,
                "reason": (
                    "name-only lane closed by semantic-guided deterministic fallback using a minimal dynamic materializer; "
                    "this reduces direct template dependence, but remains below open-world generation"
                    if materializer == "minimal_dynamic"
                    else "name-only lane closed by semantic-guided deterministic fallback using repo family assets; "
                    "this is a useful degraded recovery path, but not open-world generation"
                ),
                "confidence": resolution_confidence or "unknown",
                "basis": resolution_basis or "unknown",
                "lower_bound_dependent": True,
                "template_dependent": template_dependent,
            }
        if resolution_basis in {"catalog_alias", "exact_identifier", "token_match"}:
            dependency = dynamicness_verdict or generation_origin or "lower-bound path"
            class_name = (
                "catalog_token_match_lower_bound"
                if resolution_basis == "token_match"
                else "catalog_resolved_lower_bound"
            )
            return {
                "class": class_name,
                "counts_as_generalization": False,
                "reason": (
                    f"name-only lane resolved via {resolution_basis} and closed by {dependency}; "
                    "this remains curated lower-bound evidence, not open-world generation"
                ),
                "confidence": resolution_confidence or "unknown",
                "basis": resolution_basis or "unknown",
                "lower_bound_dependent": True,
                "template_dependent": template_dependent,
            }
        return {
            "class": "free_form_non_generalizing",
            "counts_as_generalization": False,
            "reason": "free-form NAME-* lane exists but resolution basis is not strong enough to count as open-world evidence",
            "confidence": resolution_confidence or "unknown",
            "basis": resolution_basis or "unknown",
            "lower_bound_dependent": lower_bound_available,
            "template_dependent": template_dependent,
        }

    if (
        promotion_eligible
        and dynamicness_verdict == "trusted dynamic"
        and not lower_bound_available
        and fallback_class != "generic_unsupported_family"
    ):
        return {
            "class": "open_world_positive",
            "counts_as_generalization": True,
            "reason": "bundle succeeded through trusted dynamic generation without an existing curated lower bound",
            "lower_bound_dependent": False,
            "template_dependent": template_dependent,
        }

    if lower_bound_available:
        return {
            "class": "known_family_regression",
            "counts_as_generalization": False,
            "reason": "known family or curated lower-bound regression lane",
            "lower_bound_dependent": True,
            "template_dependent": template_dependent,
        }

    if not load_static_rule(vuln_id):
        return {
            "class": "unknown_regression",
            "counts_as_generalization": False,
            "reason": "unknown identifier without a static rule is treated as a regression lane",
            "lower_bound_dependent": False,
            "template_dependent": template_dependent,
        }

    return {
        "class": "known_family_regression",
        "counts_as_generalization": False,
        "reason": "known/static-rule family regression lane",
        "lower_bound_dependent": True,
        "template_dependent": template_dependent,
    }


def _bundle_strict_open_world_verdict(
    bundle,
    *,
    open_world: Dict[str, Any],
    dynamicness: Dict[str, Any],
    provenance: Dict[str, Any],
    lower_bound: Dict[str, Any],
    verification: Dict[str, Any],
    researcher: Dict[str, Any],
    semantic: Dict[str, Any],
    request_identity: Optional[Dict[str, Any]] = None,
    request_ir: Optional[Dict[str, Any]] = None,
    dynamic_eval: Optional[Dict[str, Any]] = None,
    failure: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    vuln_id = str(getattr(bundle, "vuln_id", "") or "").strip().upper()
    generation_origin = str((provenance or {}).get("generation_origin") or "").strip().lower()
    dynamicness_verdict = str((dynamicness or {}).get("verdict") or "").strip().lower()
    fallback_class = str((provenance or {}).get("fallback_class") or "").strip().lower()
    materializer = str((provenance or {}).get("materializer") or "").strip().lower()
    if isinstance(open_world, dict) and "lower_bound_dependent" in open_world:
        lower_bound_dependent = bool((open_world or {}).get("lower_bound_dependent"))
    else:
        lower_bound_dependent = bool((lower_bound or {}).get("effective_non_remote_available"))
    template_dependent = bool((open_world or {}).get("template_dependent")) or dynamicness_verdict == "template-assisted"
    fixture_backed = (provenance or {}).get("llm_fixture_used") is True
    stub_backed = (provenance or {}).get("llm_stub_used") is True
    fallback_used = (provenance or {}).get("fallback_used") is True or generation_origin == "deterministic_fallback"
    research_degraded = (researcher or {}).get("search_degraded") is True
    researcher_quality = str((researcher or {}).get("quality") or "").strip().lower()
    researcher_report_present = (researcher or {}).get("report_present") is True
    dynamic_eval_payload = dynamic_eval if isinstance(dynamic_eval, dict) else {}
    dynamic_eval_status = str(dynamic_eval_payload.get("status") or "").strip().lower()
    failure_payload = failure if isinstance(failure, dict) else {}
    failure_stage = str(failure_payload.get("stage") or "").strip().upper()
    failure_terminal_class = str(failure_payload.get("terminal_failure_class") or "").strip().lower()
    verification_trust = str((verification or {}).get("trust") or "").strip().lower()
    verification_independence = str((verification or {}).get("independence") or "").strip().lower()
    semantic_supported = (semantic or {}).get("supported")
    semantic_status = str((semantic or {}).get("status") or "").strip().lower()
    name_driven = _is_name_driven_request(vuln_id=vuln_id, request_identity=request_identity, request_ir=request_ir)
    resolution_context = _name_resolution_context(
        vuln_id=vuln_id,
        request_identity=request_identity,
        request_ir=request_ir,
    )
    requires_research_contract = name_driven or not bool(load_static_rule(resolution_context["resolved_vuln_id"] or vuln_id))

    base_payload = {
        "counts_as_generalization": False,
        "lower_bound_dependent": lower_bound_dependent,
        "template_dependent": template_dependent,
        "fixture_backed": fixture_backed,
        "stub_backed": stub_backed,
        "research_degraded": research_degraded,
        "verification_independence": verification_independence or "unknown",
        "verification_trust": verification_trust or "unknown",
    }

    if failure_stage == "CAPABILITY_CHECK" and failure_terminal_class in {
        "strict_dynamic_live_llm_unavailable",
        "strict_dynamic_remote_research_unavailable",
    }:
        return {
            **base_payload,
            "class": "strict_dynamic_capability_unavailable",
            "reason": (
                "strict_dynamic requires live LLM and remote-research preconditions, but capability precheck "
                "failed before RESEARCH"
            ),
        }
    if failure_stage == "NAME_ONLY_GATE" and failure_terminal_class == "strict_dynamic_disallowed_llm_path":
        return {
            **base_payload,
            "class": "strict_dynamic_live_llm_required",
            "reason": "strict_dynamic requires a live LLM path, but RESEARCH already closed via a disallowed stub/fixture/degraded provider path",
        }
    if generation_origin == "research_short_circuit" or dynamicness_verdict == "pre-generation fail-closed":
        return {
            **base_payload,
            "class": "strict_fail_closed_negative",
            "reason": "bundle stopped before generation, so it cannot count as strict open-world evidence",
        }
    if failure_stage == "GENERATOR" and dynamic_eval_status == "dynamic_failed":
        return {
            **base_payload,
            "class": "strict_dynamic_generation_failed",
            "reason": (
                "name-only dynamic lane attempted generation first, but it failed before acceptable materialization"
                + (f" ({failure_terminal_class})" if failure_terminal_class else "")
            ),
        }
    if generation_origin == "deterministic_fallback" and fallback_class == "semantic_guided":
        return {
            **base_payload,
            "class": "strict_minimal_dynamic_fallback"
            if materializer == "minimal_dynamic"
            else "strict_semantic_guided_fallback",
            "reason": (
                "bundle closed through a semantic-guided minimal dynamic materializer and remains below strict open-world acceptance"
                if materializer == "minimal_dynamic"
                else "bundle closed through semantic-guided deterministic fallback and remains below strict open-world acceptance"
            ),
        }
    if template_dependent:
        return {
            **base_payload,
            "class": "strict_template_dependent",
            "reason": "bundle used a template-backed path and is excluded from strict open-world evidence",
        }
    if dynamicness_verdict != "trusted dynamic" or generation_origin != "llm_manifest":
        if lower_bound_dependent:
            return {
                **base_payload,
                "class": "strict_curated_lower_bound",
                "reason": "bundle closed through an existing curated lower bound and is excluded from strict open-world evidence",
            }
        return {
            **base_payload,
            "class": "strict_non_dynamic_path",
            "reason": "bundle did not close through a trusted-dynamic llm_manifest path",
        }
    if fallback_used:
        return {
            **base_payload,
            "class": "strict_deterministic_fallback",
            "reason": "bundle relied on deterministic fallback and is excluded from strict open-world evidence",
        }
    if fixture_backed:
        return {
            **base_payload,
            "class": "strict_fixture_backed_dynamic",
            "reason": "bundle used an LLM fixture and does not count as live strict open-world evidence",
        }
    if stub_backed:
        return {
            **base_payload,
            "class": "strict_stub_backed_dynamic",
            "reason": "bundle used the deterministic LLM stub and does not count as strict open-world evidence",
        }
    if lower_bound_dependent:
        return {
            **base_payload,
            "class": "strict_curated_lower_bound",
            "reason": "bundle closed through an existing curated lower bound and is excluded from strict open-world evidence",
        }
    if verification_trust != "high":
        return {
            **base_payload,
            "class": "strict_low_trust_verification",
            "reason": "verification trust is below high, so the bundle remains below strict open-world acceptance",
        }
    if verification_independence != "independent":
        return {
            **base_payload,
            "class": "strict_verifier_coupled",
            "reason": "verification is not independent from generation and is excluded from strict open-world evidence",
        }
    if semantic_supported is not True or semantic_status != "aligned":
        return {
            **base_payload,
            "class": "strict_semantic_unresolved",
            "reason": "semantic contract is not fully aligned, so the bundle cannot count as strict open-world evidence",
        }
    if research_degraded:
        return {
            **base_payload,
            "class": "strict_research_degraded",
            "reason": "research evidence degraded to fallback mode, so the bundle is excluded from strict open-world evidence",
        }
    if requires_research_contract and (not researcher_report_present or researcher_quality in {"skipped", "insufficient"}):
        return {
            **base_payload,
            "class": "strict_research_contract_missing",
            "reason": "strict open-world acceptance requires a non-skipped researcher contract for this lane",
        }
    return {
        **base_payload,
        "class": "strict_open_world_positive",
        "counts_as_generalization": True,
        "reason": "bundle closed through live trusted-dynamic generation without lower-bound/template dependence and with independent high-trust verification",
    }


def _bundle_lower_bound(
    metadata_dir: Path,
    vuln_id: str,
    requirement: Dict[str, Any],
) -> Dict[str, Any]:
    contract = load_generator_contract(metadata_dir) or {}
    direct = contract.get("lower_bound")
    if isinstance(direct, dict) and direct:
        return direct
    profile = load_semantic_profile(metadata_dir) or {}
    nested = profile.get("lower_bound") if isinstance(profile, dict) else None
    if isinstance(nested, dict) and nested:
        return nested
    return lower_bound_summary(vuln_id, requirement)


def _bundle_executor_feasibility(
    plan: Dict[str, Any],
    bundle,
    requirement: Dict[str, Any],
    metadata_dir: Path,
) -> Dict[str, Any]:
    requires_external_db = False
    for path in (metadata_dir / "generator_manifest.json", metadata_dir / "generator_template.json"):
        payload = _load_json(path) or {}
        if not isinstance(payload, dict):
            continue
        candidates = [payload]
        manifest = payload.get("manifest")
        if isinstance(manifest, dict):
            candidates.append(manifest)
        found = False
        for candidate in candidates:
            value = candidate.get("requires_external_db")
            if value is not None:
                requires_external_db = bool(value)
                found = True
                break
        if found:
            break
    else:
        runtime = requirement.get("runtime") if isinstance(requirement.get("runtime"), dict) else {}
        db = str(runtime.get("db") or "").strip().lower()
        requires_external_db = db in {"mysql", "postgres", "postgresql", "mariadb"}
    policy = plan.get("policy") or {}
    executor_policy = policy.get("executor") if isinstance(policy, dict) else {}
    return executor_feasibility_summary(
        requirement,
        executor_policy if isinstance(executor_policy, dict) else {},
        requires_external_db=requires_external_db,
    )


def _bundle_runtime_recipe(
    *,
    contract: Dict[str, Any],
    requirement: Dict[str, Any],
    compiler_contract: Dict[str, Any],
    executor_feasibility: Dict[str, Any],
    provenance: Dict[str, Any],
) -> Dict[str, Any]:
    generation_origin = str((provenance or {}).get("generation_origin") or "").strip().lower()
    pre_generation_only = generation_origin in {
        "capability_gate_rejected",
        "name_only_gate_rejected",
        "research_short_circuit",
    }
    direct = contract.get("runtime_recipe") if isinstance(contract.get("runtime_recipe"), dict) else None
    if isinstance(direct, dict) and direct:
        recipe = dict(direct)
    else:
        runtime = requirement.get("runtime") if isinstance(requirement.get("runtime"), dict) else {}
        executor = requirement.get("executor") if isinstance(requirement.get("executor"), dict) else {}
        sidecars = executor.get("sidecars") if isinstance(executor.get("sidecars"), list) else []
        normalized_sidecars: List[Dict[str, Any]] = []
        for item in sidecars:
            if not isinstance(item, dict):
                continue
            entry: Dict[str, Any] = {}
            for key in ("name", "type", "image"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    entry[key] = value.strip()
            aliases = item.get("aliases")
            if isinstance(aliases, list):
                alias_values = [str(alias).strip() for alias in aliases if isinstance(alias, str) and str(alias).strip()]
                if alias_values:
                    entry["aliases"] = alias_values
            if entry:
                normalized_sidecars.append(entry)

        service_env = contract.get("service_env") if isinstance(contract.get("service_env"), dict) else {}
        if not service_env and isinstance(compiler_contract.get("service_env"), dict):
            service_env = compiler_contract.get("service_env") or {}
        normalized_env = {
            str(key): str(value)
            for key, value in service_env.items()
            if isinstance(key, str) and key.strip() and value not in (None, "")
        }
        db = str(runtime.get("db") or runtime.get("database") or requirement.get("db") or "").strip().lower() or None
        service_port = contract.get("service_port")
        recipe = {
            "language": str(requirement.get("language") or "python").strip().lower() or "python",
            "framework": str(requirement.get("framework") or "flask").strip().lower() or "flask",
            "transport": "http",
            "service_entry": str(contract.get("service_entry") or "app.py").strip() or "app.py",
            "poc_entry": str(contract.get("poc_entry") or "poc.py").strip() or "poc.py",
            "service_port": int(service_port or 5000),
            "db": db,
            "allow_external_db": bool(runtime.get("allow_external_db", False)),
            "requires_external_db": bool(executor_feasibility.get("requires_external_db")),
            "network_mode": str(executor_feasibility.get("network_mode") or "none").strip().lower() or "none",
            "network_enabled": bool(executor_feasibility.get("network_enabled")),
            "sidecars": normalized_sidecars,
            "service_env": normalized_env,
            "seed_files": [],
            "topology": "service_plus_sidecar"
            if normalized_sidecars or bool(executor_feasibility.get("requires_external_db"))
            else "single_service",
            "output_mode": str(contract.get("output_mode") or "auto").strip().lower() or "auto",
        }

    recipe.setdefault("source", "resolved_contract" if isinstance(direct, dict) and direct else "derived_from_requirement")
    recipe["hypothetical"] = pre_generation_only
    recipe["realized"] = not pre_generation_only
    return recipe


def _bundle_runtime_graph(
    *,
    contract: Dict[str, Any],
    runtime_recipe: Dict[str, Any],
) -> Dict[str, Any]:
    direct = contract.get("runtime_graph") if isinstance(contract.get("runtime_graph"), dict) else None
    if isinstance(direct, dict) and direct:
        graph = dict(direct)
        graph["hypothetical"] = bool(runtime_recipe.get("hypothetical"))
        graph["realized"] = not bool(runtime_recipe.get("hypothetical"))
        graph.setdefault("source", "resolved_contract")
        return graph
    recipe = runtime_recipe if isinstance(runtime_recipe, dict) else {}
    if not recipe:
        return {}
    service_port = recipe.get("service_port")
    if not isinstance(service_port, int):
        service_port = 5000
    nodes: List[Dict[str, Any]] = [
        {
            "id": "service",
            "kind": "service",
            "role": "primary",
            "language": str(recipe.get("language") or "python").strip().lower() or "python",
            "framework": str(recipe.get("framework") or "flask").strip().lower() or "flask",
            "entry": str(recipe.get("service_entry") or "app.py").strip() or "app.py",
            "transport": str(recipe.get("transport") or "http").strip().lower() or "http",
            "port": service_port,
        }
    ]
    edges: List[Dict[str, Any]] = [
        {
            "from": "poc",
            "to": "service",
            "kind": "exploit_http",
            "transport": str(recipe.get("transport") or "http").strip().lower() or "http",
            "target_port": service_port,
        }
    ]
    raw_sidecars = recipe.get("sidecars") if isinstance(recipe.get("sidecars"), list) else []
    for sidecar in raw_sidecars:
        if not isinstance(sidecar, dict):
            continue
        name = str(sidecar.get("name") or "").strip()
        if not name:
            continue
        node_id = f"sidecar:{name}"
        nodes.append(
            {
                "id": node_id,
                "kind": "sidecar",
                "role": "dependency",
                "sidecar_type": str(sidecar.get("type") or "").strip() or "unknown",
                "image": str(sidecar.get("image") or "").strip() or None,
                "aliases": [str(alias).strip() for alias in sidecar.get("aliases") or [] if str(alias).strip()],
            }
        )
        edges.append(
            {
                "from": "service",
                "to": node_id,
                "kind": "runtime_dependency",
                "dependency_type": str(sidecar.get("type") or "").strip() or "unknown",
                "network_mode": str(recipe.get("network_mode") or "none").strip().lower() or "none",
            }
        )
    graph: Dict[str, Any] = {
        "schema_version": "runtime_graph@0.1",
        "source": "derived_from_runtime_recipe",
        "hypothetical": bool(recipe.get("hypothetical")),
        "realized": bool(recipe.get("realized", True)),
        "topology": str(recipe.get("topology") or "single_service").strip() or "single_service",
        "network": {
            "mode": str(recipe.get("network_mode") or "none").strip().lower() or "none",
            "enabled": bool(recipe.get("network_enabled")),
        },
        "nodes": nodes,
        "edges": edges,
        "healthchecks": [],
        "env_contract": [
            {"scope": "service", "name": str(key), "value": str(value)}
            for key, value in (recipe.get("service_env") or {}).items()
            if isinstance(key, str) and key.strip() and value not in (None, "")
        ],
        "exploit_path": {
            "entrypoint": str(recipe.get("poc_entry") or "poc.py").strip() or "poc.py",
            "target_node": "service",
            "service_entry": str(recipe.get("service_entry") or "app.py").strip() or "app.py",
            "transport": str(recipe.get("transport") or "http").strip().lower() or "http",
            "port": service_port,
        },
    }
    health_path = str(recipe.get("health_path") or "").strip()
    if health_path:
        graph["healthchecks"] = [
            {
                "node": "service",
                "path": health_path,
                "port": service_port,
                "transport": str(recipe.get("transport") or "http").strip().lower() or "http",
            }
        ]
    if isinstance(recipe.get("seed_files"), list) and recipe.get("seed_files"):
        graph["seed_files"] = list(recipe.get("seed_files") or [])
    db = str(recipe.get("db") or "").strip().lower()
    if db:
        graph["db"] = db
    return graph


def _bundle_dynamic_eval_summary(
    *,
    requirement: Dict[str, Any],
    metadata_dir: Path,
) -> Dict[str, Any]:
    policy = requirement.get("policy") if isinstance(requirement.get("policy"), dict) else {}
    request_identity = requirement.get("request_identity") if isinstance(requirement.get("request_identity"), dict) else {}
    request_ir = requirement.get("request_ir") if isinstance(requirement.get("request_ir"), dict) else {}
    name_driven = _is_name_driven_request(
        vuln_id=str(requirement.get("vuln_id") or "").strip().upper(),
        request_identity=request_identity,
        request_ir=request_ir,
    )
    name_only_mode = str((policy or {}).get("name_only_mode") or "").strip().lower() if isinstance(policy, dict) else ""
    enabled = bool(policy.get("dynamic_eval")) if isinstance(policy, dict) else False
    if name_driven and name_only_mode in {"dynamic", "strict_dynamic"}:
        enabled = True
    payload = _load_json(metadata_dir / "dynamic_eval.json") or {}
    summary: Dict[str, Any] = {"enabled": enabled}
    if not isinstance(payload, dict):
        summary["attempted"] = enabled
        return summary
    for key in ("status", "fallback_path"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            summary[key] = value.strip()
    for key in ("attempted", "lower_bound_fallback_used"):
        value = payload.get(key)
        if isinstance(value, bool):
            summary[key] = value
    if "attempted" not in summary:
        summary["attempted"] = enabled
    return summary


def _bundle_researcher_summary(
    *,
    requirement: Dict[str, Any],
    metadata_dir: Path,
) -> Dict[str, Any]:
    researcher_cfg = requirement.get("researcher") if isinstance(requirement.get("researcher"), dict) else {}
    policy = requirement.get("policy") if isinstance(requirement.get("policy"), dict) else {}
    request_identity = requirement.get("request_identity") if isinstance(requirement.get("request_identity"), dict) else {}
    request_ir = requirement.get("request_ir") if isinstance(requirement.get("request_ir"), dict) else {}
    name_driven = _is_name_driven_request(
        vuln_id=str(requirement.get("vuln_id") or "").strip().upper(),
        request_identity=request_identity,
        request_ir=request_ir,
    )
    report = _load_json(metadata_dir / "researcher_report.json") or {}
    report_present = bool(report)
    ambiguous = None
    summary: Dict[str, Any] = {
        "shadow_mode_enabled": bool((researcher_cfg or {}).get("shadow_mode")),
        "force_run": bool((researcher_cfg or {}).get("force_run")) if isinstance(researcher_cfg, dict) else False,
        "dynamic_eval_enabled": (
            bool((policy or {}).get("dynamic_eval"))
            or (name_driven and str((policy or {}).get("name_only_mode") or "").strip().lower() in {"dynamic", "strict_dynamic"})
        )
        if isinstance(policy, dict)
        else False,
        "search_policy": (
            str((researcher_cfg or {}).get("search_policy") or "").strip().lower()
            if isinstance(researcher_cfg, dict)
            else ""
        )
        or None,
        "report_present": report_present,
        "ran": False,
    }
    if not report_present:
        return summary

    quality = str(report.get("quality") or "").strip().lower()
    summary["ran"] = quality not in {"", "skipped"}
    for key in ("quality", "quality_reason", "search_health_path"):
        value = report.get(key)
        if isinstance(value, str) and value.strip():
            summary[key] = value.strip()
    for key in ("search_degraded", "guard_fallback", "retry_recommended"):
        value = report.get(key)
        if isinstance(value, bool):
            summary[key] = value
    semantic_signature_source = report.get("semantic_signature_source")
    if isinstance(semantic_signature_source, str):
        semantic_signature_source = [semantic_signature_source]
    if isinstance(semantic_signature_source, list):
        normalized_sources = [
            str(item).strip()
            for item in semantic_signature_source
            if isinstance(item, str) and str(item).strip()
        ]
        if normalized_sources:
            summary["semantic_signature_source"] = normalized_sources
    evidence_relevance = report.get("evidence_relevance")
    if isinstance(evidence_relevance, dict) and evidence_relevance:
        score = evidence_relevance.get("score")
        threshold = evidence_relevance.get("threshold")
        confidence = evidence_relevance.get("confidence")
        if score is not None:
            summary["evidence_relevance_score"] = score
        if threshold is not None:
            summary["evidence_relevance_threshold"] = threshold
        if isinstance(confidence, str) and confidence.strip():
            summary["evidence_relevance_confidence"] = confidence.strip().lower()
    candidate_rules = report.get("candidate_rules")
    if isinstance(candidate_rules, list):
        summary["candidate_rule_count"] = len(candidate_rules)
    candidate_templates = report.get("candidate_templates")
    if isinstance(candidate_templates, list):
        summary["candidate_template_count"] = len(candidate_templates)
    query_plan = report.get("query_plan")
    if isinstance(query_plan, dict) and query_plan:
        summary["query_plan_present"] = True
        family_hypotheses = query_plan.get("family_hypotheses")
        if isinstance(family_hypotheses, list):
            summary["query_plan_family_hypothesis_count"] = len(family_hypotheses)
    evidence_type_summary = report.get("evidence_type_summary")
    if isinstance(evidence_type_summary, dict) and evidence_type_summary:
        by_type = evidence_type_summary.get("by_type")
        if isinstance(by_type, dict) and by_type:
            summary["evidence_types"] = {
                str(key): int(value)
                for key, value in by_type.items()
                if isinstance(key, str) and key.strip() and isinstance(value, (int, float))
            }
        matched_target_count = evidence_type_summary.get("matched_target_count")
        hit_count = evidence_type_summary.get("hit_count")
        if isinstance(matched_target_count, (int, float)) and isinstance(hit_count, (int, float)) and hit_count:
            summary["query_target_match_rate"] = round(float(matched_target_count) / float(hit_count), 3)
    family_hypothesis_summary = report.get("family_hypothesis_summary")
    if isinstance(family_hypothesis_summary, dict) and family_hypothesis_summary:
        top_family = family_hypothesis_summary.get("top_family")
        top_confidence = family_hypothesis_summary.get("top_confidence")
        raw_top_confidence = family_hypothesis_summary.get("raw_top_confidence")
        contradiction_count = family_hypothesis_summary.get("contradiction_count")
        top_margin = family_hypothesis_summary.get("top_margin")
        ambiguous = family_hypothesis_summary.get("ambiguous")
        if isinstance(top_family, str) and top_family.strip():
            summary["top_family_hypothesis"] = top_family.strip()
        if isinstance(top_confidence, str) and top_confidence.strip():
            summary["top_family_hypothesis_confidence"] = top_confidence.strip().lower()
        if isinstance(raw_top_confidence, str) and raw_top_confidence.strip():
            summary["top_family_hypothesis_raw_confidence"] = raw_top_confidence.strip().lower()
        if isinstance(contradiction_count, (int, float)):
            summary["family_hypothesis_contradictions"] = int(contradiction_count)
        if isinstance(top_margin, (int, float)):
            summary["top_family_hypothesis_margin"] = round(float(top_margin), 3)
    if isinstance(ambiguous, bool):
        summary["family_hypothesis_ambiguous"] = ambiguous
    llm_execution = report.get("llm_execution")
    if isinstance(llm_execution, dict) and llm_execution:
        for src_key, dst_key in (
            ("provider_attempted", "llm_provider_attempted"),
            ("provider_succeeded", "llm_provider_succeeded"),
            ("stub_fallback", "llm_stub_used"),
            ("fixture_used", "llm_fixture_used"),
        ):
            value = llm_execution.get(src_key)
            if isinstance(value, bool):
                summary[dst_key] = value
        last_error_class = llm_execution.get("last_error_class")
        if isinstance(last_error_class, str) and last_error_class.strip():
            summary["llm_failure_class"] = last_error_class.strip()
    return summary


def _bundle_artifact_quality(bundle_entry: Dict[str, Any]) -> Dict[str, Any]:
    paths = bundle_entry.get("paths") if isinstance(bundle_entry.get("paths"), dict) else {}
    workspace_value = paths.get("workspace") if isinstance(paths, dict) else None
    workspace_path = str(workspace_value).strip() if isinstance(workspace_value, str) and str(workspace_value).strip() else ""
    readme_present = False
    readme_substantive = False
    readme_quickstart = False
    readme_verification = False
    readme_runtime = False
    if workspace_path:
        readme_path = Path(workspace_path) / "README.md"
        if readme_path.exists():
            readme_present = True
            try:
                text = readme_path.read_text(encoding="utf-8")
            except Exception:
                text = ""
            lowered = text.lower()
            nonempty_lines = [line for line in text.splitlines() if line.strip()]
            readme_substantive = len(nonempty_lines) >= 6 and len(text) >= 180
            readme_quickstart = any(token in lowered for token in ("docker build", "docker run", "python poc.py"))
            readme_verification = any(
                token in lowered for token in ("verification markers", "success signature", "flag token", "poc must print")
            )
            readme_runtime = any(
                token in lowered for token in ("runtime expects", "sidecar", "db_host", "mysql", "postgres", "/health")
            )

    provenance = bundle_entry.get("provenance") if isinstance(bundle_entry.get("provenance"), dict) else {}
    dynamicness = bundle_entry.get("dynamicness") if isinstance(bundle_entry.get("dynamicness"), dict) else {}
    generation_origin = str((provenance or {}).get("generation_origin") or "").strip().lower()
    dynamicness_verdict = str((dynamicness or {}).get("verdict") or "").strip().lower()
    pre_generation_fail_closed = generation_origin == "research_short_circuit" or dynamicness_verdict == "pre-generation fail-closed"
    degraded_fallback = bool((provenance or {}).get("fallback_used")) or generation_origin == "deterministic_fallback"

    runtime_recipe = bundle_entry.get("runtime_recipe") if isinstance(bundle_entry.get("runtime_recipe"), dict) else {}
    stack_dependence = bundle_entry.get("stack_dependence") if isinstance(bundle_entry.get("stack_dependence"), dict) else {}
    runtime_recipe_present = bool(runtime_recipe) and not pre_generation_fail_closed
    topology = str(runtime_recipe.get("topology") or "").strip()
    service_port = runtime_recipe.get("service_port")
    sidecars = runtime_recipe.get("sidecars") if isinstance(runtime_recipe.get("sidecars"), list) else []
    service_env = runtime_recipe.get("service_env") if isinstance(runtime_recipe.get("service_env"), dict) else {}
    if pre_generation_fail_closed:
        topology_clarity = "missing"
    elif runtime_recipe_present and topology == "service_plus_sidecar" and sidecars and service_env:
        topology_clarity = "high"
    elif runtime_recipe_present and topology and service_port:
        topology_clarity = "medium"
    elif runtime_recipe_present:
        topology_clarity = "low"
    else:
        topology_clarity = "missing"

    verification = bundle_entry.get("verification") if isinstance(bundle_entry.get("verification"), dict) else {}
    exploit_oracle = bundle_entry.get("exploit_oracle") if isinstance(bundle_entry.get("exploit_oracle"), dict) else {}
    oracle_clarity = "missing"
    rule_source = verification.get("rule_source")
    trust = verification.get("trust")
    independence = str(verification.get("independence") or "").strip().lower()
    has_rule_source = isinstance(rule_source, str) and rule_source.strip()
    has_trust = isinstance(trust, str) and trust.strip()
    has_oracle_contract = False
    negative_control_present = False
    metamorphic_present = False
    if isinstance(exploit_oracle, dict) and exploit_oracle:
        if any(
            key in exploit_oracle and exploit_oracle.get(key)
            for key in ("success_signature", "flag_token", "assertion_program", "poc_cmd")
        ):
            has_oracle_contract = True
        negative_control_present = bool(
            exploit_oracle.get("negative_control_present")
            or exploit_oracle.get("negative_text_markers")
            or exploit_oracle.get("forbidden_success_markers")
            or exploit_oracle.get("negative_controls")
        )
        metamorphic_present = isinstance(exploit_oracle.get("metamorphic"), dict) and bool(exploit_oracle.get("metamorphic"))
    if has_rule_source and has_trust:
        trust_token = str(trust or "").strip().lower()
        if trust_token == "high" and independence == "independent":
            oracle_clarity = "high" if readme_verification else "medium"
        elif trust_token == "high":
            oracle_clarity = "medium" if readme_verification else "low"
        else:
            oracle_clarity = "low"
    elif has_rule_source:
        oracle_clarity = "low"
    elif has_oracle_contract:
        oracle_clarity = "medium" if readme_verification else "low"
    oracle_rigor = "missing"
    if has_oracle_contract:
        if negative_control_present and metamorphic_present:
            oracle_rigor = "high"
        elif negative_control_present or metamorphic_present or exploit_oracle.get("assertion_program"):
            oracle_rigor = "medium"
        else:
            oracle_rigor = "low"

    readme_score = sum(
        1 for flag in (readme_present, readme_substantive, readme_quickstart, readme_verification, readme_runtime) if flag
    )
    topology_score = {"missing": 0, "low": 1, "medium": 2, "high": 3}.get(topology_clarity, 0)
    oracle_score = {"missing": 0, "low": 1, "medium": 2, "high": 3}.get(oracle_clarity, 0)
    total_score = readme_score + topology_score + oracle_score
    generation_authenticity = "degraded_fallback" if degraded_fallback else "native"
    if degraded_fallback:
        # Keep deterministic recovery bundles runnable, but avoid scoring them
        # as if they were native dynamic or template-quality artifacts.
        total_score = min(total_score, 8)
        trust_token = str(trust or "").strip().lower()
        if trust_token != "high" or independence != "independent":
            total_score = min(total_score, 5)
    if total_score >= 9:
        band = "high"
    elif total_score >= 6:
        band = "medium"
    else:
        band = "low"

    notes: List[str] = []
    if not readme_present:
        notes.append("README missing")
    elif not readme_substantive:
        notes.append("README is too thin for operator-facing use")
    elif not readme_verification:
        notes.append("README does not clearly surface verification/oracle contract")
    if topology_clarity in {"missing", "low"}:
        notes.append("runtime topology clarity is incomplete")
    if oracle_clarity in {"missing", "low"}:
        notes.append("exploit oracle clarity is limited")
    if pre_generation_fail_closed:
        notes.append("bundle stopped before code generation; runtime recipe remains planning-only")
    elif degraded_fallback:
        notes.append("deterministic fallback bundle: operator-facing quality is capped below native dynamic/template artifacts")
        trust_token = str(trust or "").strip().lower()
        if trust_token != "high" or independence != "independent":
            notes.append("deterministic fallback bundle lacks independent high-trust verification, so operator-facing realism stays low")
    if has_oracle_contract and not negative_control_present:
        notes.append("oracle contract lacks explicit negative-control or forbidden-success markers")
    if has_oracle_contract and not metamorphic_present:
        notes.append("oracle contract lacks metamorphic checks")
    if (stack_dependence or {}).get("stack_defaulted") is True:
        notes.append("stack selection remained repo-prior/defaulted rather than evidence-led")

    return {
        "band": band,
        "score": total_score,
        "generation_authenticity": generation_authenticity,
        "readme_present": readme_present,
        "readme_substantive": readme_substantive,
        "readme_quickstart": readme_quickstart,
        "readme_verification": readme_verification,
        "readme_runtime": readme_runtime,
        "runtime_recipe_present": runtime_recipe_present,
        "topology_clarity": topology_clarity,
        "oracle_clarity": oracle_clarity,
        "oracle_rigor": oracle_rigor,
        "negative_control_present": negative_control_present,
        "metamorphic_present": metamorphic_present,
        "verification_independence": independence or "missing",
        "verification_trust": str(trust or "").strip().lower() or "missing",
        "notes": notes,
    }


def _lower_bound_rollup(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    family_non_remote_bundles = 0
    effective_non_remote_bundles = 0
    compiler_disabled_bundles = 0
    by_effective_status: Dict[str, int] = {}
    for entry in bundles:
        lower_bound = entry.get("lower_bound") or {}
        if not isinstance(lower_bound, dict):
            continue
        if lower_bound.get("family_non_remote_available") is True:
            family_non_remote_bundles += 1
        if lower_bound.get("effective_non_remote_available") is True:
            effective_non_remote_bundles += 1
        if lower_bound.get("compiler_path_enabled") is False:
            compiler_disabled_bundles += 1
        if lower_bound.get("effective_non_remote_available") is True:
            token = "effective_non_remote"
        elif lower_bound.get("family_non_remote_available") is True:
            token = "family_only"
        else:
            token = "none"
        by_effective_status[token] = by_effective_status.get(token, 0) + 1
    return {
        "bundle_count": len(bundles),
        "family_non_remote_bundles": family_non_remote_bundles,
        "effective_non_remote_bundles": effective_non_remote_bundles,
        "compiler_disabled_bundles": compiler_disabled_bundles,
        "by_effective_status": by_effective_status,
    }


def _executor_feasibility_rollup(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    requires_external_db_bundles = 0
    misconfigured_bundles = 0
    by_status: Dict[str, int] = {}
    for entry in bundles:
        feasibility = entry.get("executor_feasibility") or {}
        if not isinstance(feasibility, dict):
            continue
        if feasibility.get("requires_external_db") is True:
            requires_external_db_bundles += 1
        status = str(feasibility.get("status") or "").strip() or "unknown"
        by_status[status] = by_status.get(status, 0) + 1
        if status == "misconfigured":
            misconfigured_bundles += 1
    return {
        "bundle_count": len(bundles),
        "requires_external_db_bundles": requires_external_db_bundles,
        "misconfigured_bundles": misconfigured_bundles,
        "by_status": by_status,
    }


def _generalization_summary(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_class: Dict[str, int] = {}
    by_confidence: Dict[str, int] = {}
    by_basis: Dict[str, int] = {}
    positive_generalization_bundles = 0
    realized_bundles = 0
    hypothetical_bundles = 0
    fully_validated_bundles = 0
    realized_positive_generalization_bundles = 0
    fully_validated_positive_generalization_bundles = 0
    lower_bound_dependent_bundles = 0
    for entry in bundles:
        generalization = entry.get("generalization") or {}
        if not isinstance(generalization, dict):
            continue
        runtime_recipe = entry.get("runtime_recipe") if isinstance(entry.get("runtime_recipe"), dict) else {}
        completion = entry.get("completion_state") if isinstance(entry.get("completion_state"), dict) else {}
        hypothetical = bool(runtime_recipe.get("hypothetical"))
        fully_validated = completion.get("fully_validated") is True
        if hypothetical:
            hypothetical_bundles += 1
        else:
            realized_bundles += 1
        if fully_validated:
            fully_validated_bundles += 1
        class_name = str(generalization.get("class") or "").strip()
        if class_name:
            by_class[class_name] = by_class.get(class_name, 0) + 1
        confidence = str(generalization.get("confidence") or "").strip()
        if confidence:
            by_confidence[confidence] = by_confidence.get(confidence, 0) + 1
        basis = str(generalization.get("basis") or "").strip()
        if basis:
            by_basis[basis] = by_basis.get(basis, 0) + 1
        if generalization.get("counts_as_generalization") is True:
            positive_generalization_bundles += 1
            if not hypothetical:
                realized_positive_generalization_bundles += 1
            if fully_validated:
                fully_validated_positive_generalization_bundles += 1
        if generalization.get("lower_bound_dependent") is True:
            lower_bound_dependent_bundles += 1
    return {
        "bundle_count": len(bundles),
        "positive_generalization_bundles": positive_generalization_bundles,
        "realized_bundles": realized_bundles,
        "hypothetical_bundles": hypothetical_bundles,
        "fully_validated_bundles": fully_validated_bundles,
        "realized_positive_generalization_bundles": realized_positive_generalization_bundles,
        "fully_validated_positive_generalization_bundles": fully_validated_positive_generalization_bundles,
        "lower_bound_dependent_bundles": lower_bound_dependent_bundles,
        "by_class": by_class,
        "by_confidence": by_confidence,
        "by_basis": by_basis,
    }


def _artifact_quality_summary(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_band: Dict[str, int] = {}
    total_score = 0
    bundle_count = 0
    readme_present_bundles = 0
    runtime_recipe_bundles = 0
    stack_defaulted_bundles = 0
    for entry in bundles:
        quality = entry.get("artifact_quality") or {}
        if not isinstance(quality, dict):
            continue
        bundle_count += 1
        band = str(quality.get("band") or "").strip()
        if band:
            by_band[band] = by_band.get(band, 0) + 1
        total_score += int(quality.get("score") or 0)
        if quality.get("readme_present") is True:
            readme_present_bundles += 1
        if quality.get("runtime_recipe_present") is True:
            runtime_recipe_bundles += 1
        stack_dependence = entry.get("stack_dependence") or {}
        if isinstance(stack_dependence, dict) and stack_dependence.get("stack_defaulted") is True:
            stack_defaulted_bundles += 1
    average_score = round(total_score / bundle_count, 2) if bundle_count else 0.0
    return {
        "bundle_count": bundle_count,
        "average_score": average_score,
        "by_band": by_band,
        "readme_present_bundles": readme_present_bundles,
        "runtime_recipe_bundles": runtime_recipe_bundles,
        "stack_defaulted_bundles": stack_defaulted_bundles,
    }


def _evidence_graph_summary(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    graph_present_bundles = 0
    total_nodes = 0
    total_edges = 0
    by_node_kind: Dict[str, int] = {}
    by_edge_kind: Dict[str, int] = {}
    for entry in bundles:
        graph = entry.get("evidence_graph") or {}
        if not isinstance(graph, dict) or not graph:
            continue
        graph_present_bundles += 1
        nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
        edges = graph.get("edges") if isinstance(graph.get("edges"), list) else []
        total_nodes += int(graph.get("node_count") or len(nodes))
        total_edges += int(graph.get("edge_count") or len(edges))
        for node in nodes:
            if not isinstance(node, dict):
                continue
            kind = str(node.get("kind") or "").strip().lower() or "unknown"
            by_node_kind[kind] = by_node_kind.get(kind, 0) + 1
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            kind = str(edge.get("kind") or "").strip().lower() or "unknown"
            by_edge_kind[kind] = by_edge_kind.get(kind, 0) + 1
    return {
        "bundle_count": len(bundles),
        "graph_present_bundles": graph_present_bundles,
        "average_node_count": round(total_nodes / graph_present_bundles, 2) if graph_present_bundles else 0.0,
        "average_edge_count": round(total_edges / graph_present_bundles, 2) if graph_present_bundles else 0.0,
        "by_node_kind": by_node_kind,
        "by_edge_kind": by_edge_kind,
    }


def _researcher_summary(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_quality: Dict[str, int] = {}
    by_top_family_hypothesis: Dict[str, int] = {}
    by_top_family_confidence: Dict[str, int] = {}
    shadow_mode_bundles = 0
    report_present_bundles = 0
    ran_bundles = 0
    skipped_bundles = 0
    degraded_bundles = 0
    query_plan_bundles = 0
    contradiction_bundles = 0
    ambiguous_family_hypothesis_bundles = 0
    query_target_match_rates: List[float] = []
    for entry in bundles:
        researcher = entry.get("researcher") or {}
        if not isinstance(researcher, dict):
            continue
        if researcher.get("shadow_mode_enabled") is True:
            shadow_mode_bundles += 1
        if researcher.get("report_present") is True:
            report_present_bundles += 1
        if researcher.get("ran") is True:
            ran_bundles += 1
        quality = str(researcher.get("quality") or "").strip()
        if quality:
            by_quality[quality] = by_quality.get(quality, 0) + 1
            if quality == "skipped":
                skipped_bundles += 1
        if researcher.get("search_degraded") is True:
            degraded_bundles += 1
        if researcher.get("query_plan_present") is True:
            query_plan_bundles += 1
        top_family = str(researcher.get("top_family_hypothesis") or "").strip()
        if top_family:
            by_top_family_hypothesis[top_family] = by_top_family_hypothesis.get(top_family, 0) + 1
        top_confidence = str(researcher.get("top_family_hypothesis_confidence") or "").strip().lower()
        if top_confidence:
            by_top_family_confidence[top_confidence] = by_top_family_confidence.get(top_confidence, 0) + 1
        contradictions = researcher.get("family_hypothesis_contradictions")
        if isinstance(contradictions, (int, float)) and contradictions > 0:
            contradiction_bundles += 1
        if researcher.get("family_hypothesis_ambiguous") is True:
            ambiguous_family_hypothesis_bundles += 1
        match_rate = researcher.get("query_target_match_rate")
        if isinstance(match_rate, (int, float)):
            query_target_match_rates.append(float(match_rate))
    return {
        "bundle_count": len(bundles),
        "shadow_mode_bundles": shadow_mode_bundles,
        "report_present_bundles": report_present_bundles,
        "ran_bundles": ran_bundles,
        "skipped_bundles": skipped_bundles,
        "degraded_bundles": degraded_bundles,
        "query_plan_bundles": query_plan_bundles,
        "contradiction_bundles": contradiction_bundles,
        "ambiguous_family_hypothesis_bundles": ambiguous_family_hypothesis_bundles,
        "by_quality": by_quality,
        "by_top_family_hypothesis": by_top_family_hypothesis,
        "by_top_family_confidence": by_top_family_confidence,
        "avg_query_target_match_rate": round(sum(query_target_match_rates) / len(query_target_match_rates), 3)
        if query_target_match_rates
        else 0.0,
    }


def _request_identity_summary(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_input_mode: Dict[str, int] = {}
    by_match_class: Dict[str, int] = {}
    by_confidence: Dict[str, int] = {}
    name_driven_bundles = 0
    synthetic_resolution_bundles = 0
    for entry in bundles:
        request_identity = entry.get("request_identity") or {}
        request_ir = entry.get("request_ir") or {}
        identity = request_identity if isinstance(request_identity, dict) and request_identity else {}
        ir = request_ir if isinstance(request_ir, dict) and request_ir else {}
        if not identity and not ir:
            continue
        input_mode = str((identity or {}).get("input_mode") or (ir or {}).get("input_mode") or "").strip()
        if input_mode:
            by_input_mode[input_mode] = by_input_mode.get(input_mode, 0) + 1
        match_class = str(
            (identity or {}).get("match_class")
            or (ir or {}).get("resolution_match_class")
            or ""
        ).strip()
        if match_class:
            by_match_class[match_class] = by_match_class.get(match_class, 0) + 1
        confidence = str(
            (identity or {}).get("confidence")
            or (ir or {}).get("resolution_confidence")
            or ""
        ).strip()
        if confidence:
            by_confidence[confidence] = by_confidence.get(confidence, 0) + 1
        if _is_name_driven_request(
            vuln_id=str(entry.get("vuln_id") or "").strip().upper(),
            request_identity=identity,
            request_ir=ir,
        ):
            name_driven_bundles += 1
        if (identity or {}).get("synthetic_resolution") is True or (ir or {}).get("synthetic_resolution") is True:
            synthetic_resolution_bundles += 1
    return {
        "bundle_count": len(bundles),
        "name_driven_bundles": name_driven_bundles,
        "synthetic_resolution_bundles": synthetic_resolution_bundles,
        "by_input_mode": by_input_mode,
        "by_match_class": by_match_class,
        "by_confidence": by_confidence,
    }


def _request_ir_summary(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_resolution_state: Dict[str, int] = {}
    by_resolution_match_class: Dict[str, int] = {}
    by_resolution_confidence: Dict[str, int] = {}
    name_driven_bundles = 0
    evidence_backed_bundles = 0
    abstain_signaled_bundles = 0
    multi_identifier_candidate_bundles = 0
    ambiguous_family_candidate_bundles = 0
    ambiguous_stack_candidate_bundles = 0
    negative_hypothesis_bundles = 0
    identifier_candidate_counts: List[int] = []
    family_candidate_counts: List[int] = []
    stack_candidate_counts: List[int] = []
    negative_hypothesis_counts: List[int] = []
    for entry in bundles:
        request_ir = entry.get("request_ir")
        if not isinstance(request_ir, dict) or not request_ir:
            continue
        vuln_id = str(entry.get("vuln_id") or "").strip().upper()
        if _is_name_driven_request(vuln_id=vuln_id, request_ir=request_ir):
            name_driven_bundles += 1
        resolution_state = str(request_ir.get("resolution_state") or "").strip()
        if resolution_state:
            by_resolution_state[resolution_state] = by_resolution_state.get(resolution_state, 0) + 1
        resolution_match_class = str(request_ir.get("resolution_match_class") or "").strip()
        if resolution_match_class:
            by_resolution_match_class[resolution_match_class] = by_resolution_match_class.get(resolution_match_class, 0) + 1
        resolution_confidence = str(request_ir.get("resolution_confidence") or "").strip()
        if resolution_confidence:
            by_resolution_confidence[resolution_confidence] = by_resolution_confidence.get(resolution_confidence, 0) + 1

        identifier_candidates = request_ir.get("identifier_candidates") if isinstance(request_ir.get("identifier_candidates"), list) else []
        family_candidates = request_ir.get("family_candidates") if isinstance(request_ir.get("family_candidates"), list) else []
        stack_candidates = request_ir.get("stack_candidates") if isinstance(request_ir.get("stack_candidates"), list) else []
        negative_hypotheses = request_ir.get("negative_hypotheses") if isinstance(request_ir.get("negative_hypotheses"), list) else []

        identifier_candidate_counts.append(len(identifier_candidates))
        family_candidate_counts.append(len(family_candidates))
        stack_candidate_counts.append(len(stack_candidates))
        negative_hypothesis_counts.append(len(negative_hypotheses))

        if len(identifier_candidates) > 1:
            multi_identifier_candidate_bundles += 1
        if len(family_candidates) > 1:
            ambiguous_family_candidate_bundles += 1
        if len(stack_candidates) > 1:
            ambiguous_stack_candidate_bundles += 1
        if negative_hypotheses:
            negative_hypothesis_bundles += 1
        if _stable_reason_token(request_ir.get("abstain_reason")):
            abstain_signaled_bundles += 1

        request_evidence_ids = [
            str(item).strip()
            for item in (request_ir.get("evidence_ids") or [])
            if isinstance(item, str) and str(item).strip()
        ]
        candidate_evidence_backed = bool(request_evidence_ids)
        if not candidate_evidence_backed:
            for candidate_group in (family_candidates, stack_candidates, identifier_candidates):
                for candidate in candidate_group:
                    if not isinstance(candidate, dict):
                        continue
                    evidence_ids = [
                        str(item).strip()
                        for item in (candidate.get("evidence_ids") or [])
                        if isinstance(item, str) and str(item).strip()
                    ]
                    if evidence_ids:
                        candidate_evidence_backed = True
                        break
                if candidate_evidence_backed:
                    break
        if candidate_evidence_backed:
            evidence_backed_bundles += 1

    def _avg(values: List[int]) -> float:
        if not values:
            return 0.0
        return round(sum(values) / len(values), 3)

    return {
        "bundle_count": len(bundles),
        "name_driven_bundles": name_driven_bundles,
        "evidence_backed_bundles": evidence_backed_bundles,
        "abstain_signaled_bundles": abstain_signaled_bundles,
        "multi_identifier_candidate_bundles": multi_identifier_candidate_bundles,
        "ambiguous_family_candidate_bundles": ambiguous_family_candidate_bundles,
        "ambiguous_stack_candidate_bundles": ambiguous_stack_candidate_bundles,
        "negative_hypothesis_bundles": negative_hypothesis_bundles,
        "avg_identifier_candidate_count": _avg(identifier_candidate_counts),
        "avg_family_candidate_count": _avg(family_candidate_counts),
        "avg_stack_candidate_count": _avg(stack_candidate_counts),
        "avg_negative_hypothesis_count": _avg(negative_hypothesis_counts),
        "by_resolution_state": by_resolution_state,
        "by_resolution_match_class": by_resolution_match_class,
        "by_resolution_confidence": by_resolution_confidence,
    }


def _template_dependence_summary(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    template_assisted_bundles = 0
    template_dependent_bundles = 0
    lower_bound_dependent_bundles = 0
    name_only_lower_bound_bundles = 0
    open_world_positive_bundles = 0
    minimal_dynamic_bundles = 0
    realized_minimal_dynamic_bundles = 0
    fully_validated_minimal_dynamic_bundles = 0
    hypothetical_lower_bound_bundles = 0
    by_open_world_class: Dict[str, int] = {}
    for entry in bundles:
        dynamicness = entry.get("dynamicness") or {}
        open_world = entry.get("open_world") or {}
        provenance = entry.get("provenance") or {}
        runtime_recipe = entry.get("runtime_recipe") if isinstance(entry.get("runtime_recipe"), dict) else {}
        completion = entry.get("completion_state") if isinstance(entry.get("completion_state"), dict) else {}
        hypothetical = bool(runtime_recipe.get("hypothetical"))
        fully_validated = completion.get("fully_validated") is True
        if str((dynamicness or {}).get("verdict") or "").strip().lower() == "template-assisted":
            template_assisted_bundles += 1
        if str((provenance or {}).get("materializer") or "").strip().lower() == "minimal_dynamic":
            minimal_dynamic_bundles += 1
            if not hypothetical:
                realized_minimal_dynamic_bundles += 1
            if fully_validated:
                fully_validated_minimal_dynamic_bundles += 1
        if isinstance(open_world, dict):
            if open_world.get("template_dependent") is True:
                template_dependent_bundles += 1
            if open_world.get("lower_bound_dependent") is True:
                lower_bound_dependent_bundles += 1
                if hypothetical:
                    hypothetical_lower_bound_bundles += 1
            if open_world.get("counts_as_generalization") is True:
                open_world_positive_bundles += 1
            class_name = str(open_world.get("class") or "").strip()
            if class_name:
                by_open_world_class[class_name] = by_open_world_class.get(class_name, 0) + 1
            if _is_name_driven_request(
                vuln_id=str(entry.get("vuln_id") or "").strip().upper(),
                request_identity=entry.get("request_identity") if isinstance(entry.get("request_identity"), dict) else {},
                request_ir=entry.get("request_ir") if isinstance(entry.get("request_ir"), dict) else {},
            ) and open_world.get("lower_bound_dependent") is True:
                name_only_lower_bound_bundles += 1
    return {
        "bundle_count": len(bundles),
        "template_assisted_bundles": template_assisted_bundles,
        "template_dependent_bundles": template_dependent_bundles,
        "lower_bound_dependent_bundles": lower_bound_dependent_bundles,
        "name_only_lower_bound_bundles": name_only_lower_bound_bundles,
        "open_world_positive_bundles": open_world_positive_bundles,
        "minimal_dynamic_bundles": minimal_dynamic_bundles,
        "realized_minimal_dynamic_bundles": realized_minimal_dynamic_bundles,
        "fully_validated_minimal_dynamic_bundles": fully_validated_minimal_dynamic_bundles,
        "hypothetical_lower_bound_bundles": hypothetical_lower_bound_bundles,
        "by_open_world_class": by_open_world_class,
    }


def _bundle_stack_dependence(bundle_entry: Dict[str, Any]) -> Dict[str, Any]:
    runtime_recipe = bundle_entry.get("runtime_recipe") if isinstance(bundle_entry.get("runtime_recipe"), dict) else {}
    request_ir = bundle_entry.get("request_ir") if isinstance(bundle_entry.get("request_ir"), dict) else {}
    request_ir_stack_candidates = request_ir.get("stack_candidates") if isinstance(request_ir.get("stack_candidates"), list) else []
    raw_hypotheses = (
        runtime_recipe.get("stack_hypotheses")
        if isinstance(runtime_recipe.get("stack_hypotheses"), list)
        else request_ir.get("stack_candidates")
        if isinstance(request_ir.get("stack_candidates"), list)
        else []
    )
    unique_stack_ids: List[str] = []
    top_source = ""
    top_confidence = ""
    for entry in raw_hypotheses if isinstance(raw_hypotheses, list) else []:
        if not isinstance(entry, dict):
            continue
        stack_id = str(entry.get("stack_id") or "").strip().lower()
        if not stack_id:
            language = str(entry.get("language") or "").strip().lower()
            framework = str(entry.get("framework") or "").strip().lower()
            if language and framework:
                stack_id = f"{language}/{framework}"
        if not stack_id:
            continue
        if not unique_stack_ids:
            top_source = str(entry.get("source") or "").strip().lower()
            top_confidence = str(entry.get("confidence") or "").strip().lower()
        if stack_id not in unique_stack_ids:
            unique_stack_ids.append(stack_id)

    language = str(runtime_recipe.get("language") or "").strip().lower()
    framework = str(runtime_recipe.get("framework") or "").strip().lower()
    working_stack_id = f"{language}/{framework}" if language and framework else (unique_stack_ids[0] if unique_stack_ids else "")
    working_stack_entry = None
    for entry in raw_hypotheses if isinstance(raw_hypotheses, list) else []:
        if not isinstance(entry, dict):
            continue
        stack_id = str(entry.get("stack_id") or "").strip().lower()
        if not stack_id:
            cand_language = str(entry.get("language") or "").strip().lower()
            cand_framework = str(entry.get("framework") or "").strip().lower()
            if cand_language and cand_framework:
                stack_id = f"{cand_language}/{cand_framework}"
        if stack_id and stack_id == working_stack_id:
            working_stack_entry = entry
            break
    working_stack_evidence_ids = [
        str(item).strip()
        for item in ((working_stack_entry or {}).get("evidence_ids") or [])
        if isinstance(item, str) and str(item).strip()
    ]
    if not working_stack_evidence_ids and isinstance(request_ir_stack_candidates, list):
        for entry in request_ir_stack_candidates:
            if not isinstance(entry, dict):
                continue
            stack_id = str(entry.get("stack_id") or "").strip().lower()
            if not stack_id:
                cand_language = str(entry.get("language") or "").strip().lower()
                cand_framework = str(entry.get("framework") or "").strip().lower()
                if cand_language and cand_framework:
                    stack_id = f"{cand_language}/{cand_framework}"
            if stack_id != working_stack_id:
                continue
            working_stack_evidence_ids = [
                str(item).strip()
                for item in (entry.get("evidence_ids") or [])
                if isinstance(item, str) and str(item).strip()
            ]
            if working_stack_evidence_ids:
                break
    stack_source = str(runtime_recipe.get("stack_source") or "").strip().lower() or top_source or "unknown"
    stack_locked = bool(runtime_recipe.get("stack_locked"))
    stack_defaulted = bool(runtime_recipe.get("stack_defaulted"))
    ambiguous = len(unique_stack_ids) > 1
    repo_bounded_sources = {"profile_prior", "available_skeleton", "default_stack_profile", "stack_hypothesis"}
    repo_prior_bounded = stack_source in repo_bounded_sources
    researcher_inferred = stack_source == "researcher_candidate"
    if stack_locked and stack_source == "explicit_requirement":
        class_name = "explicit_requirement_locked"
    elif researcher_inferred:
        class_name = "researcher_inferred"
    elif repo_prior_bounded:
        class_name = "repo_prior_bounded"
    elif stack_source == "explicit_requirement":
        class_name = "explicit_requirement"
    else:
        class_name = "other"
    return {
        "class": class_name,
        "working_stack_id": working_stack_id or None,
        "stack_source": stack_source,
        "stack_locked": stack_locked,
        "stack_defaulted": stack_defaulted,
        "candidate_count": len(unique_stack_ids),
        "ambiguous": ambiguous,
        "repo_prior_bounded": repo_prior_bounded,
        "researcher_inferred": researcher_inferred,
        "top_confidence": top_confidence or None,
        "working_stack_evidence_ids": working_stack_evidence_ids,
        "working_stack_evidence_count": len(working_stack_evidence_ids),
        "working_stack_evidence_backed": bool(working_stack_evidence_ids),
    }


def _stack_dependence_summary(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_class: Dict[str, int] = {}
    by_stack_source: Dict[str, int] = {}
    repo_prior_bounded_bundles = 0
    stack_defaulted_bundles = 0
    researcher_inferred_bundles = 0
    ambiguous_bundles = 0
    locked_bundles = 0
    evidence_backed_bundles = 0
    for entry in bundles:
        dependence = entry.get("stack_dependence") if isinstance(entry.get("stack_dependence"), dict) else {}
        if not dependence:
            continue
        class_name = str(dependence.get("class") or "").strip()
        if class_name:
            by_class[class_name] = by_class.get(class_name, 0) + 1
        stack_source = str(dependence.get("stack_source") or "").strip()
        if stack_source:
            by_stack_source[stack_source] = by_stack_source.get(stack_source, 0) + 1
        if dependence.get("repo_prior_bounded") is True:
            repo_prior_bounded_bundles += 1
        if dependence.get("stack_defaulted") is True:
            stack_defaulted_bundles += 1
        if dependence.get("researcher_inferred") is True:
            researcher_inferred_bundles += 1
        if dependence.get("ambiguous") is True:
            ambiguous_bundles += 1
        if dependence.get("stack_locked") is True:
            locked_bundles += 1
        if dependence.get("working_stack_evidence_backed") is True:
            evidence_backed_bundles += 1
    return {
        "bundle_count": len(bundles),
        "repo_prior_bounded_bundles": repo_prior_bounded_bundles,
        "stack_defaulted_bundles": stack_defaulted_bundles,
        "researcher_inferred_bundles": researcher_inferred_bundles,
        "ambiguous_bundles": ambiguous_bundles,
        "locked_bundles": locked_bundles,
        "evidence_backed_bundles": evidence_backed_bundles,
        "by_class": by_class,
        "by_stack_source": by_stack_source,
    }


def _bundle_family_dependence(bundle_entry: Dict[str, Any]) -> Dict[str, Any]:
    request_identity = bundle_entry.get("request_identity") if isinstance(bundle_entry.get("request_identity"), dict) else {}
    request_ir = bundle_entry.get("request_ir") if isinstance(bundle_entry.get("request_ir"), dict) else {}
    provenance = bundle_entry.get("provenance") if isinstance(bundle_entry.get("provenance"), dict) else {}
    generation_origin = str((provenance or {}).get("generation_origin") or "").strip().lower()
    fallback_class = str((provenance or {}).get("fallback_class") or "").strip().lower()
    semantic_guided_selection_source = str((provenance or {}).get("semantic_guided_selection_source") or "").strip().lower()
    semantic_guided_abstain_reason = str((provenance or {}).get("semantic_guided_abstain_reason") or "").strip().lower()
    semantic_guided_ambiguous = (provenance or {}).get("semantic_guided_ambiguous") is True
    name_only_spec = (
        bundle_entry.get("name_only_generation_spec")
        if isinstance(bundle_entry.get("name_only_generation_spec"), dict)
        else {}
    )
    required_contract = (
        name_only_spec.get("required_contract")
        if isinstance(name_only_spec, dict) and isinstance(name_only_spec.get("required_contract"), dict)
        else {}
    )
    family_candidate_summary = (
        name_only_spec.get("family_candidate_summary")
        if isinstance(name_only_spec, dict) and isinstance(name_only_spec.get("family_candidate_summary"), dict)
        else {}
    )
    family_hypothesis_source = str((name_only_spec or {}).get("family_hypothesis_source") or "").strip().lower()
    working_family = str((name_only_spec or {}).get("family_working_hypothesis") or "").strip().lower()
    name_driven = _is_name_driven_request(
        vuln_id=str(bundle_entry.get("vuln_id") or "").strip().upper(),
        request_identity=request_identity,
        request_ir=request_ir,
    )

    candidate_count = 0
    material_candidate_count = 0
    material_ambiguous = False
    if isinstance(family_candidate_summary, dict):
        raw_candidate_count = family_candidate_summary.get("candidate_count")
        if isinstance(raw_candidate_count, int):
            candidate_count = raw_candidate_count
        raw_material_candidate_count = family_candidate_summary.get("material_candidate_count")
        if isinstance(raw_material_candidate_count, int):
            material_candidate_count = raw_material_candidate_count
        raw_material_ambiguous = family_candidate_summary.get("material_ambiguous")
        if isinstance(raw_material_ambiguous, bool):
            material_ambiguous = raw_material_ambiguous
    if material_candidate_count <= 0:
        material_candidate_count = candidate_count

    if not name_driven:
        return {
            "class": "not_name_only",
            "name_only": False,
            "family_bounded": False,
            "ambiguous": False,
            "candidate_count": candidate_count,
            "material_candidate_count": material_candidate_count,
            "selection_source": None,
            "abstain_reason": None,
        }

    class_name = "other"
    family_bounded = False
    selection_source = None
    abstain_reason = None
    working_family_entry = None
    resolution_context = _name_resolution_context(
        vuln_id=str(bundle_entry.get("vuln_id") or "").strip().upper(),
        request_identity=request_identity,
        request_ir=request_ir,
    )
    raw_family_candidates = request_ir.get("family_candidates") if isinstance(request_ir.get("family_candidates"), list) else []
    unique_family_candidates: List[str] = []
    top_request_ir_family_source = ""
    family_candidate_evidence_ids: List[str] = []
    if candidate_count <= 0:
        candidate_count = len([entry for entry in raw_family_candidates if isinstance(entry, dict)])
    if material_candidate_count <= 0:
        material_candidate_count = candidate_count
    for entry in raw_family_candidates if isinstance(raw_family_candidates, list) else []:
        if not isinstance(entry, dict):
            continue
        family = str(entry.get("family") or "").strip().lower()
        if family and family not in unique_family_candidates:
            unique_family_candidates.append(family)
        if not top_request_ir_family_source:
            top_request_ir_family_source = str(entry.get("source") or "").strip().lower()
        family_candidate_evidence_ids.extend(
            [
                str(item).strip()
                for item in (entry.get("evidence_ids") or [])
                if isinstance(item, str) and str(item).strip()
            ]
        )
        if working_family and _family_keys_match(family, working_family):
            working_family_entry = entry
            break
    if not working_family and len(unique_family_candidates) == 1:
        working_family = unique_family_candidates[0]
        for entry in raw_family_candidates if isinstance(raw_family_candidates, list) else []:
            if not isinstance(entry, dict):
                continue
            if _family_keys_match(str(entry.get("family") or "").strip().lower(), working_family):
                working_family_entry = entry
                break
    working_family_evidence_ids = [
        str(item).strip()
        for item in ((working_family_entry or {}).get("evidence_ids") or [])
        if isinstance(item, str) and str(item).strip()
    ]
    if not working_family_evidence_ids:
        deduped_candidate_evidence_ids: List[str] = []
        seen_candidate_evidence_ids = set()
        for item in family_candidate_evidence_ids:
            if item in seen_candidate_evidence_ids:
                continue
            seen_candidate_evidence_ids.add(item)
            deduped_candidate_evidence_ids.append(item)
        family_candidate_evidence_ids = deduped_candidate_evidence_ids
    else:
        family_candidate_evidence_ids = working_family_evidence_ids

    if generation_origin in {"capability_gate_rejected", "name_only_gate_rejected", "research_short_circuit"}:
        class_name = "precondition_failed"
        selection_source = top_request_ir_family_source or None
        abstain_reason = _stable_reason_token((request_ir or {}).get("abstain_reason")) or abstain_reason
    elif generation_origin == "deterministic_fallback" and fallback_class == "semantic_guided":
        family_bounded = True
        selection_source = semantic_guided_selection_source or top_request_ir_family_source or None
        if semantic_guided_selection_source == "request_resolution":
            class_name = "request_resolution_bounded"
        elif semantic_guided_selection_source in {"researcher_top_family", "researcher_ranked_family", "family_hypothesis_gate"}:
            class_name = "researcher_family_bounded"
        elif semantic_guided_selection_source == "semantic_signature":
            class_name = "semantic_signature_bounded"
        else:
            class_name = "semantic_guided_bounded"
    elif generation_origin == "deterministic_fallback" and fallback_class == "family_aware":
        class_name = "curated_family_asset"
        family_bounded = True
        selection_source = top_request_ir_family_source or None
    elif generation_origin == "deterministic_fallback" and fallback_class == "generic_unsupported_family":
        class_name = "family_unresolved_generic_fallback"
        selection_source = top_request_ir_family_source or None
        abstain_reason = semantic_guided_abstain_reason or _stable_reason_token((request_ir or {}).get("abstain_reason")) or None
    elif generation_origin in {"compiler_generated", "built_in_template", "runtime_template_clone"}:
        class_name = "curated_family_asset"
        family_bounded = True
        selection_source = top_request_ir_family_source or None
    elif generation_origin == "llm_manifest":
        family_bounded = True
        selection_source = family_hypothesis_source or top_request_ir_family_source or None
        if family_hypothesis_source in {"request_ir", "request_ir_fallback", "request_identity", "request_identity_fallback"}:
            class_name = "request_resolution_prompt_bounded"
        elif family_hypothesis_source == "researcher_family_hypothesis":
            class_name = "researcher_family_prompt_bounded"
        else:
            class_name = "llm_manifest_family_bounded"
    elif required_contract:
        class_name = "name_only_unresolved"
        selection_source = top_request_ir_family_source or None
        abstain_reason = _stable_reason_token((request_ir or {}).get("abstain_reason")) or abstain_reason

    return {
        "class": class_name,
        "name_only": True,
        "family_bounded": family_bounded,
        "ambiguous": semantic_guided_ambiguous or material_ambiguous or (material_candidate_count > 1),
        "candidate_count": candidate_count,
        "material_candidate_count": material_candidate_count,
        "selection_source": selection_source,
        "abstain_reason": abstain_reason,
        "working_family": working_family or None,
        "working_family_evidence_ids": working_family_evidence_ids,
        "working_family_evidence_count": len(working_family_evidence_ids),
        "working_family_evidence_backed": bool(working_family_evidence_ids),
        "candidate_evidence_ids": family_candidate_evidence_ids,
        "candidate_evidence_count": len(family_candidate_evidence_ids),
        "candidate_evidence_backed": bool(family_candidate_evidence_ids),
        "resolution_confidence": resolution_context["confidence"] or None,
        "resolution_basis": resolution_context["basis"] or None,
        "negative_hypothesis_count": len(
            request_ir.get("negative_hypotheses") if isinstance(request_ir.get("negative_hypotheses"), list) else []
        ),
    }


def _family_dependence_summary(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_class: Dict[str, int] = {}
    by_selection_source: Dict[str, int] = {}
    by_abstain_reason: Dict[str, int] = {}
    by_resolution_confidence: Dict[str, int] = {}
    by_resolution_basis: Dict[str, int] = {}
    family_bounded_bundles = 0
    ambiguous_bundles = 0
    name_only_bundles = 0
    evidence_backed_bundles = 0
    candidate_evidence_backed_bundles = 0
    negative_hypothesis_bundles = 0
    for entry in bundles:
        dependence = entry.get("family_dependence") if isinstance(entry.get("family_dependence"), dict) else {}
        if not dependence:
            continue
        if dependence.get("name_only") is True:
            name_only_bundles += 1
        if dependence.get("family_bounded") is True:
            family_bounded_bundles += 1
        if dependence.get("ambiguous") is True:
            ambiguous_bundles += 1
        if dependence.get("working_family_evidence_backed") is True:
            evidence_backed_bundles += 1
        if dependence.get("candidate_evidence_backed") is True:
            candidate_evidence_backed_bundles += 1
        if int(dependence.get("negative_hypothesis_count") or 0) > 0:
            negative_hypothesis_bundles += 1
        class_name = str(dependence.get("class") or "").strip()
        if class_name:
            by_class[class_name] = by_class.get(class_name, 0) + 1
        selection_source = str(dependence.get("selection_source") or "").strip()
        if selection_source:
            by_selection_source[selection_source] = by_selection_source.get(selection_source, 0) + 1
        abstain_reason = str(dependence.get("abstain_reason") or "").strip()
        if abstain_reason:
            by_abstain_reason[abstain_reason] = by_abstain_reason.get(abstain_reason, 0) + 1
        resolution_confidence = str(dependence.get("resolution_confidence") or "").strip()
        if resolution_confidence:
            by_resolution_confidence[resolution_confidence] = by_resolution_confidence.get(resolution_confidence, 0) + 1
        resolution_basis = str(dependence.get("resolution_basis") or "").strip()
        if resolution_basis:
            by_resolution_basis[resolution_basis] = by_resolution_basis.get(resolution_basis, 0) + 1
    return {
        "bundle_count": len(bundles),
        "name_only_bundles": name_only_bundles,
        "family_bounded_bundles": family_bounded_bundles,
        "ambiguous_bundles": ambiguous_bundles,
        "evidence_backed_bundles": evidence_backed_bundles,
        "candidate_evidence_backed_bundles": candidate_evidence_backed_bundles,
        "negative_hypothesis_bundles": negative_hypothesis_bundles,
        "by_class": by_class,
        "by_selection_source": by_selection_source,
        "by_abstain_reason": by_abstain_reason,
        "by_resolution_confidence": by_resolution_confidence,
        "by_resolution_basis": by_resolution_basis,
    }


def _runtime_surface_summary(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    realized_bundles = 0
    hypothetical_bundles = 0
    network_enabled_bundles = 0
    sidecar_bundles = 0
    by_topology: Dict[str, int] = {}
    for entry in bundles:
        recipe = entry.get("runtime_recipe") if isinstance(entry.get("runtime_recipe"), dict) else {}
        if not recipe:
            continue
        if recipe.get("hypothetical") is True:
            hypothetical_bundles += 1
        else:
            realized_bundles += 1
        if recipe.get("network_enabled") is True:
            network_enabled_bundles += 1
        if isinstance(recipe.get("sidecars"), list) and recipe.get("sidecars"):
            sidecar_bundles += 1
        topology = str(recipe.get("topology") or "").strip() or "unknown"
        by_topology[topology] = by_topology.get(topology, 0) + 1
    return {
        "bundle_count": len(bundles),
        "realized_bundles": realized_bundles,
        "hypothetical_bundles": hypothetical_bundles,
        "network_enabled_bundles": network_enabled_bundles,
        "sidecar_bundles": sidecar_bundles,
        "by_topology": by_topology,
    }


def _open_world_summary(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_class: Dict[str, int] = {}
    by_confidence: Dict[str, int] = {}
    by_basis: Dict[str, int] = {}
    positive_open_world_bundles = 0
    realized_bundles = 0
    hypothetical_bundles = 0
    fully_validated_bundles = 0
    realized_positive_open_world_bundles = 0
    fully_validated_positive_open_world_bundles = 0
    lower_bound_dependent_bundles = 0
    template_dependent_bundles = 0
    for entry in bundles:
        open_world = entry.get("open_world") or {}
        if not isinstance(open_world, dict):
            continue
        runtime_recipe = entry.get("runtime_recipe") if isinstance(entry.get("runtime_recipe"), dict) else {}
        completion = entry.get("completion_state") if isinstance(entry.get("completion_state"), dict) else {}
        hypothetical = bool(runtime_recipe.get("hypothetical"))
        fully_validated = completion.get("fully_validated") is True
        if hypothetical:
            hypothetical_bundles += 1
        else:
            realized_bundles += 1
        if fully_validated:
            fully_validated_bundles += 1
        class_name = str(open_world.get("class") or "").strip()
        if class_name:
            by_class[class_name] = by_class.get(class_name, 0) + 1
        confidence = str(open_world.get("confidence") or "").strip()
        if confidence:
            by_confidence[confidence] = by_confidence.get(confidence, 0) + 1
        basis = str(open_world.get("basis") or "").strip()
        if basis:
            by_basis[basis] = by_basis.get(basis, 0) + 1
        if open_world.get("counts_as_generalization") is True:
            positive_open_world_bundles += 1
            if not hypothetical:
                realized_positive_open_world_bundles += 1
            if fully_validated:
                fully_validated_positive_open_world_bundles += 1
        if open_world.get("lower_bound_dependent") is True:
            lower_bound_dependent_bundles += 1
        if open_world.get("template_dependent") is True:
            template_dependent_bundles += 1
    return {
        "bundle_count": len(bundles),
        "positive_open_world_bundles": positive_open_world_bundles,
        "realized_bundles": realized_bundles,
        "hypothetical_bundles": hypothetical_bundles,
        "fully_validated_bundles": fully_validated_bundles,
        "realized_positive_open_world_bundles": realized_positive_open_world_bundles,
        "fully_validated_positive_open_world_bundles": fully_validated_positive_open_world_bundles,
        "lower_bound_dependent_bundles": lower_bound_dependent_bundles,
        "template_dependent_bundles": template_dependent_bundles,
        "by_class": by_class,
        "by_confidence": by_confidence,
        "by_basis": by_basis,
    }


def _strict_open_world_summary(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_class: Dict[str, int] = {}
    positive_strict_open_world_bundles = 0
    realized_bundles = 0
    hypothetical_bundles = 0
    fully_validated_bundles = 0
    realized_positive_strict_open_world_bundles = 0
    fully_validated_positive_strict_open_world_bundles = 0
    lower_bound_dependent_bundles = 0
    template_dependent_bundles = 0
    fixture_backed_bundles = 0
    stub_backed_bundles = 0
    research_degraded_bundles = 0
    verifier_coupled_bundles = 0
    for entry in bundles:
        strict_open_world = entry.get("strict_open_world") or {}
        if not isinstance(strict_open_world, dict):
            continue
        runtime_recipe = entry.get("runtime_recipe") if isinstance(entry.get("runtime_recipe"), dict) else {}
        completion = entry.get("completion_state") if isinstance(entry.get("completion_state"), dict) else {}
        hypothetical = bool(runtime_recipe.get("hypothetical"))
        fully_validated = completion.get("fully_validated") is True
        if hypothetical:
            hypothetical_bundles += 1
        else:
            realized_bundles += 1
        if fully_validated:
            fully_validated_bundles += 1
        class_name = str(strict_open_world.get("class") or "").strip()
        if class_name:
            by_class[class_name] = by_class.get(class_name, 0) + 1
        if strict_open_world.get("counts_as_generalization") is True:
            positive_strict_open_world_bundles += 1
            if not hypothetical:
                realized_positive_strict_open_world_bundles += 1
            if fully_validated:
                fully_validated_positive_strict_open_world_bundles += 1
        if strict_open_world.get("lower_bound_dependent") is True:
            lower_bound_dependent_bundles += 1
        if strict_open_world.get("template_dependent") is True:
            template_dependent_bundles += 1
        if strict_open_world.get("fixture_backed") is True:
            fixture_backed_bundles += 1
        if strict_open_world.get("stub_backed") is True:
            stub_backed_bundles += 1
        if strict_open_world.get("research_degraded") is True:
            research_degraded_bundles += 1
        class_name_lower = class_name.lower()
        if class_name_lower in {"strict_verifier_coupled", "strict_low_trust_verification"}:
            verifier_coupled_bundles += 1
    return {
        "bundle_count": len(bundles),
        "positive_strict_open_world_bundles": positive_strict_open_world_bundles,
        "realized_bundles": realized_bundles,
        "hypothetical_bundles": hypothetical_bundles,
        "fully_validated_bundles": fully_validated_bundles,
        "realized_positive_strict_open_world_bundles": realized_positive_strict_open_world_bundles,
        "fully_validated_positive_strict_open_world_bundles": fully_validated_positive_strict_open_world_bundles,
        "lower_bound_dependent_bundles": lower_bound_dependent_bundles,
        "template_dependent_bundles": template_dependent_bundles,
        "fixture_backed_bundles": fixture_backed_bundles,
        "stub_backed_bundles": stub_backed_bundles,
        "research_degraded_bundles": research_degraded_bundles,
        "verifier_coupled_bundles": verifier_coupled_bundles,
        "by_class": by_class,
    }


def _partial_progress_summary(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    successful_bundles = 0
    executed_bundles = 0
    verified_bundles = 0
    research_blocked_bundles = 0
    failed_bundles = 0
    for entry in bundles:
        artifacts = entry.get("artifacts") or {}
        run_summary = artifacts.get("run_summary") if isinstance(artifacts, dict) else {}
        eval_result = artifacts.get("eval_result") if isinstance(artifacts, dict) else {}
        provenance = entry.get("provenance") or {}
        run_passed = bool((run_summary or {}).get("run_passed")) if isinstance(run_summary, dict) else False
        executed = bool((run_summary or {}).get("executed")) if isinstance(run_summary, dict) else False
        verify_pass = bool((eval_result or {}).get("verify_pass")) if isinstance(eval_result, dict) else False
        if executed:
            executed_bundles += 1
        if verify_pass:
            verified_bundles += 1
        if run_passed and verify_pass:
            successful_bundles += 1
        if str((provenance or {}).get("generation_origin") or "").strip().lower() == "research_short_circuit":
            research_blocked_bundles += 1
        if not (run_passed and verify_pass):
            failed_bundles += 1
    return {
        "bundle_count": len(bundles),
        "successful_bundles": successful_bundles,
        "failed_bundles": failed_bundles,
        "executed_bundles": executed_bundles,
        "verified_bundles": verified_bundles,
        "research_blocked_bundles": research_blocked_bundles,
        "partial_success": successful_bundles > 0 and failed_bundles > 0,
    }


def _bundle_completion_state(bundle_entry: Dict[str, Any]) -> Dict[str, Any]:
    artifacts = bundle_entry.get("artifacts") if isinstance(bundle_entry.get("artifacts"), dict) else {}
    run_summary = artifacts.get("run_summary") if isinstance(artifacts, dict) and isinstance(artifacts.get("run_summary"), dict) else {}
    eval_result = artifacts.get("eval_result") if isinstance(artifacts, dict) and isinstance(artifacts.get("eval_result"), dict) else {}
    provenance = bundle_entry.get("provenance") if isinstance(bundle_entry.get("provenance"), dict) else {}

    generation_origin = str((provenance or {}).get("generation_origin") or "").strip().lower()
    generated = generation_origin not in {"", "research_short_circuit", "capability_gate_rejected", "name_only_gate_rejected"}
    if not generated:
        return {
            "generated": False,
            "executed": False,
            "run_passed": False,
            "verified": False,
            "verify_pass": None,
            "reviewed": False,
            "review_ready": False,
            "fully_validated": False,
            "stage_ceiling": "pre_generation",
            "generation_origin": generation_origin or "unknown",
        }

    executed = bool((run_summary or {}).get("executed")) if isinstance(run_summary, dict) else False
    run_passed = bool((run_summary or {}).get("run_passed")) if isinstance(run_summary, dict) else False
    verified = isinstance(eval_result, dict) and isinstance(eval_result.get("verify_pass"), bool)
    verify_pass = bool((eval_result or {}).get("verify_pass")) if verified else False
    reviewer_report_present = bool(bundle_entry.get("reviewer_report"))

    promotion = bundle_entry.get("promotion") if isinstance(bundle_entry.get("promotion"), dict) else {}
    review_ready = reviewer_report_present and "pipeline:review_failed" not in {str(item) for item in (promotion.get("reasons") or [])}
    fully_validated = bool(generated and executed and run_passed and verified and verify_pass and review_ready)

    if fully_validated:
        stage_ceiling = "fully_validated"
    elif reviewer_report_present:
        stage_ceiling = "reviewed"
    elif verified:
        stage_ceiling = "verified"
    elif executed:
        stage_ceiling = "executed"
    elif generated:
        stage_ceiling = "generated"
    else:
        stage_ceiling = "pre_generation"

    return {
        "generated": generated,
        "executed": executed,
        "run_passed": run_passed,
        "verified": verified,
        "verify_pass": verify_pass if verified else None,
        "reviewed": reviewer_report_present,
        "review_ready": review_ready,
        "fully_validated": fully_validated,
        "stage_ceiling": stage_ceiling,
        "generation_origin": generation_origin or "unknown",
    }


def _completion_summary(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    generated_bundles = 0
    executed_bundles = 0
    verified_bundles = 0
    reviewed_bundles = 0
    fully_validated_bundles = 0
    by_stage_ceiling: Dict[str, int] = {}
    for entry in bundles:
        completion = entry.get("completion_state") if isinstance(entry.get("completion_state"), dict) else {}
        if not completion:
            continue
        if completion.get("generated") is True:
            generated_bundles += 1
        if completion.get("executed") is True:
            executed_bundles += 1
        if completion.get("verified") is True:
            verified_bundles += 1
        if completion.get("reviewed") is True:
            reviewed_bundles += 1
        if completion.get("fully_validated") is True:
            fully_validated_bundles += 1
        stage_ceiling = str(completion.get("stage_ceiling") or "").strip() or "unknown"
        by_stage_ceiling[stage_ceiling] = by_stage_ceiling.get(stage_ceiling, 0) + 1
    return {
        "bundle_count": len(bundles),
        "generated_bundles": generated_bundles,
        "executed_bundles": executed_bundles,
        "verified_bundles": verified_bundles,
        "reviewed_bundles": reviewed_bundles,
        "fully_validated_bundles": fully_validated_bundles,
        "by_stage_ceiling": by_stage_ceiling,
    }


def _bundle_intent_satisfaction(bundle_entry: Dict[str, Any], requirement_view: Dict[str, Any]) -> Dict[str, Any]:
    request_identity = bundle_entry.get("request_identity") if isinstance(bundle_entry.get("request_identity"), dict) else {}
    request_ir = bundle_entry.get("request_ir") if isinstance(bundle_entry.get("request_ir"), dict) else {}
    vuln_id = str(bundle_entry.get("vuln_id") or "").strip().upper()
    name_driven = _is_name_driven_request(
        vuln_id=vuln_id,
        request_identity=request_identity,
        request_ir=request_ir,
    )
    if not name_driven:
        return {
            "request_kind": "other",
            "mode": "not_applicable",
            "status": "not_applicable",
            "meets_intent": True,
            "partial": False,
            "reason": "bundle is not a name-only lane",
        }

    effective_requirement = dict(requirement_view) if isinstance(requirement_view, dict) else {}
    if "request_identity" not in effective_requirement and isinstance(request_identity, dict):
        effective_requirement["request_identity"] = request_identity
    if "request_ir" not in effective_requirement and isinstance(request_ir, dict):
        effective_requirement["request_ir"] = request_ir
    if "vuln_id" not in effective_requirement and vuln_id:
        effective_requirement["vuln_id"] = vuln_id
    policy = effective_requirement.get("policy") if isinstance(effective_requirement.get("policy"), dict) else {}
    name_only_contract = build_name_only_contract(requirement=effective_requirement, policy=policy)
    mode = str(name_only_contract.get("effective_mode") or "").strip().lower() or "compatibility"
    dynamic_eval = bundle_entry.get("dynamic_eval") if isinstance(bundle_entry.get("dynamic_eval"), dict) else {}
    dynamic_eval_enabled = bool((dynamic_eval or {}).get("enabled"))
    if mode == "compatibility" and dynamic_eval_enabled:
        mode = "dynamic_eval"
        synthetic_policy = dict(policy) if isinstance(policy, dict) else {}
        synthetic_policy["dynamic_eval"] = True
        name_only_contract = build_name_only_contract(requirement=effective_requirement, policy=synthetic_policy)
    open_world = bundle_entry.get("open_world") if isinstance(bundle_entry.get("open_world"), dict) else {}
    strict_open_world = (
        bundle_entry.get("strict_open_world") if isinstance(bundle_entry.get("strict_open_world"), dict) else {}
    )
    failure = bundle_entry.get("failure") if isinstance(bundle_entry.get("failure"), dict) else {}
    provenance = bundle_entry.get("provenance") if isinstance(bundle_entry.get("provenance"), dict) else {}
    verification = bundle_entry.get("verification") if isinstance(bundle_entry.get("verification"), dict) else {}
    researcher = bundle_entry.get("researcher") if isinstance(bundle_entry.get("researcher"), dict) else {}
    failure_stage = str((failure or {}).get("stage") or "").strip().upper()
    dynamic_eval_status = str((dynamic_eval or {}).get("status") or "").strip().lower()
    open_world_class = str((open_world or {}).get("class") or "").strip().lower()
    strict_class = str((strict_open_world or {}).get("class") or "").strip().lower()
    generation_origin = str((provenance or {}).get("generation_origin") or "").strip().lower()
    fallback_class = str((provenance or {}).get("fallback_class") or "").strip().lower()
    if (provenance or {}).get("llm_fixture_used") is True:
        llm_path = "fixture"
    elif (provenance or {}).get("llm_stub_used") is True:
        llm_path = "stub"
    elif generation_origin == "llm_manifest":
        llm_path = "live"
    else:
        llm_path = "not_used"
    if failure_stage in {"CAPABILITY_CHECK", "RESEARCH", "GENERATOR", "NAME_ONLY_GATE"}:
        closure_source = "failed"
    elif generation_origin == "compiler_generated":
        closure_source = "curated_lower_bound"
    elif generation_origin == "built_in_template":
        closure_source = "template_assisted"
    elif generation_origin == "deterministic_fallback":
        closure_source = "degraded_deterministic_fallback"
    elif generation_origin == "llm_manifest" and strict_open_world.get("counts_as_generalization") is True:
        closure_source = "strict_open_world_positive"
    elif generation_origin == "llm_manifest":
        closure_source = "trusted_dynamic"
    else:
        closure_source = generation_origin or "unknown"

    status = "compatibility_lower_bound"
    meets_intent = False
    partial = False
    reason = ""

    if mode == "compatibility":
        if failure_stage:
            status = "compatibility_failed"
            reason = "compatibility lane failed before lower-bound completion"
        else:
            status = "compatibility_lower_bound"
            meets_intent = True
            reason = "compatibility mode allows curated lower-bound/template-backed closure"
    elif mode in {"dynamic", "dynamic_eval"}:
        if strict_open_world.get("counts_as_generalization") is True or open_world_class == "open_world_positive":
            status = "dynamic_success"
            meets_intent = True
            reason = "name-only dynamic lane closed without relying on degraded lower-bound recovery"
        elif dynamic_eval_status == "degraded_success" or open_world_class in {
            "semantic_guided_minimal_dynamic",
            "semantic_guided_degraded",
        }:
            status = "degraded_dynamic_success"
            partial = True
            reason = "dynamic lane remained runnable, but closure still relied on degraded deterministic fallback"
        elif dynamic_eval_status == "lower_bound_recovered":
            status = "lower_bound_recovered"
            reason = "dynamic lane fell back to an existing curated lower-bound path"
        else:
            status = "dynamic_failed"
            reason = "dynamic lane did not produce an acceptable runnable bundle"
    else:  # strict_dynamic
        if strict_open_world.get("counts_as_generalization") is True:
            status = "strict_dynamic_success"
            meets_intent = True
            reason = "strict dynamic lane achieved strict open-world positive evidence"
        elif strict_class in {
            "strict_dynamic_generation_failed",
            "strict_dynamic_live_llm_required",
            "strict_dynamic_capability_unavailable",
        } or dynamic_eval_status == "dynamic_failed":
            status = "strict_dynamic_failed"
            reason = "strict dynamic lane failed before acceptable materialization"
        elif dynamic_eval_status == "degraded_success" or strict_class in {
            "strict_minimal_dynamic_fallback",
            "strict_semantic_guided_fallback",
        }:
            status = "strict_dynamic_rejected_degraded"
            reason = "strict dynamic lane produced only degraded deterministic fallback and does not meet intent"
        else:
            status = "strict_dynamic_not_satisfied"
            reason = "strict dynamic lane did not reach strict open-world positive evidence"

    return {
        "request_kind": "name_only",
        "mode": mode,
        "status": status,
        "meets_intent": meets_intent,
        "partial": partial,
        "reason": reason,
        "closure_source": closure_source,
        "generation_origin": generation_origin or "unknown",
        "fallback_class": fallback_class or None,
        "llm_path": llm_path,
        "research_quality": str((researcher or {}).get("quality") or "").strip().lower() or "unknown",
        "verification_independence": str((verification or {}).get("independence") or "").strip().lower() or "unknown",
        "verification_trust": str((verification or {}).get("trust") or "").strip().lower() or "unknown",
        "required_contract": {
            "require_research": bool(name_only_contract.get("require_research")),
            "require_remote_research": bool(name_only_contract.get("require_remote_research")),
            "allow_degraded_fallback": bool(name_only_contract.get("allow_degraded_fallback")),
            "allow_lower_bound_recovery": bool(name_only_contract.get("allow_lower_bound_recovery")),
            "require_strict_open_world": bool(name_only_contract.get("require_strict_open_world")),
            "require_independent_verifier": bool(name_only_contract.get("require_independent_verifier")),
            "require_live_llm": bool(name_only_contract.get("require_live_llm")),
            "allowed_closure_sources": list(name_only_contract.get("allowed_closure_sources") or []),
            "allowed_execution_paths": list(name_only_contract.get("allowed_execution_paths") or []),
            "intent_satisfying_paths": list(name_only_contract.get("intent_satisfying_paths") or []),
            "allowed_llm_paths": list(name_only_contract.get("allowed_llm_paths") or []),
            "intent_success_rule": str(name_only_contract.get("intent_success_rule") or "").strip() or None,
        },
    }


def _intent_satisfaction_summary(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    name_only_bundles = 0
    meets_intent_bundles = 0
    partial_bundles = 0
    by_status: Dict[str, int] = {}
    by_closure_source: Dict[str, int] = {}
    by_llm_path: Dict[str, int] = {}
    by_research_quality: Dict[str, int] = {}
    for entry in bundles:
        payload = entry.get("intent_satisfaction") or {}
        if not isinstance(payload, dict):
            continue
        if payload.get("request_kind") != "name_only":
            continue
        name_only_bundles += 1
        if payload.get("meets_intent") is True:
            meets_intent_bundles += 1
        if payload.get("partial") is True:
            partial_bundles += 1
        status = str(payload.get("status") or "").strip()
        if status:
            by_status[status] = by_status.get(status, 0) + 1
        closure_source = str(payload.get("closure_source") or "").strip()
        if closure_source:
            by_closure_source[closure_source] = by_closure_source.get(closure_source, 0) + 1
        llm_path = str(payload.get("llm_path") or "").strip()
        if llm_path:
            by_llm_path[llm_path] = by_llm_path.get(llm_path, 0) + 1
        research_quality = str(payload.get("research_quality") or "").strip()
        if research_quality:
            by_research_quality[research_quality] = by_research_quality.get(research_quality, 0) + 1
    return {
        "bundle_count": len(bundles),
        "name_only_bundles": name_only_bundles,
        "meets_intent_bundles": meets_intent_bundles,
        "partial_bundles": partial_bundles,
        "all_name_only_meet_intent": meets_intent_bundles == name_only_bundles if name_only_bundles else False,
        "by_status": by_status,
        "by_closure_source": by_closure_source,
        "by_llm_path": by_llm_path,
        "by_research_quality": by_research_quality,
    }


def _name_only_next_required_step(
    completion_state: Dict[str, Any],
    *,
    failure_stage: str,
) -> str | None:
    if completion_state.get("fully_validated") is True:
        return None
    failure_stage_token = str(failure_stage or "").strip().upper()
    if failure_stage_token in {"CAPABILITY_CHECK", "NAME_ONLY_GATE"}:
        return "capability_or_research"
    if failure_stage_token == "RESEARCH":
        return "research"
    stage_ceiling = str(completion_state.get("stage_ceiling") or "").strip().lower()
    if stage_ceiling == "pre_generation":
        return "generation"
    if stage_ceiling == "generated":
        return "execution"
    if stage_ceiling == "executed":
        return "verification"
    if stage_ceiling == "verified":
        return "review"
    if stage_ceiling == "reviewed":
        return "validation"
    return "unknown"


def _name_only_partial_next_required_step(bundle_entry: Dict[str, Any]) -> str:
    stack_dependence = (
        bundle_entry.get("stack_dependence") if isinstance(bundle_entry.get("stack_dependence"), dict) else {}
    )
    family_dependence = (
        bundle_entry.get("family_dependence") if isinstance(bundle_entry.get("family_dependence"), dict) else {}
    )
    open_world = bundle_entry.get("open_world") if isinstance(bundle_entry.get("open_world"), dict) else {}
    strict_open_world = (
        bundle_entry.get("strict_open_world") if isinstance(bundle_entry.get("strict_open_world"), dict) else {}
    )
    dynamic_eval = bundle_entry.get("dynamic_eval") if isinstance(bundle_entry.get("dynamic_eval"), dict) else {}

    if (stack_dependence or {}).get("stack_defaulted") is True:
        return "stack_or_runtime_design"
    if str((stack_dependence or {}).get("class") or "").strip().lower() == "repo_prior_bounded":
        return "stack_or_runtime_design"
    if (family_dependence or {}).get("ambiguous") is True:
        return "research"
    if (family_dependence or {}).get("candidate_evidence_backed") is not True:
        return "research"

    dynamic_eval_status = str((dynamic_eval or {}).get("status") or "").strip().lower()
    open_world_class = str((open_world or {}).get("class") or "").strip().lower()
    strict_class = str((strict_open_world or {}).get("class") or "").strip().lower()
    if dynamic_eval_status in {"degraded_success", "lower_bound_recovered"}:
        return "open_world_generation"
    if open_world_class in {"semantic_guided_minimal_dynamic", "semantic_guided_degraded"}:
        return "open_world_generation"
    if strict_class in {
        "strict_minimal_dynamic_fallback",
        "strict_semantic_guided_fallback",
        "strict_curated_lower_bound",
    }:
        return "open_world_generation"
    if (open_world or {}).get("lower_bound_dependent") is True:
        return "open_world_generation"
    return "generalization"


def _bundle_name_only_outcome(bundle_entry: Dict[str, Any]) -> Dict[str, Any]:
    intent = bundle_entry.get("intent_satisfaction") if isinstance(bundle_entry.get("intent_satisfaction"), dict) else {}
    if not isinstance(intent, dict) or intent.get("request_kind") != "name_only":
        return {
            "request_kind": "other",
            "decision": "not_applicable",
            "decision_reason": "bundle is not a name-only lane",
        }

    request_ir = bundle_entry.get("request_ir") if isinstance(bundle_entry.get("request_ir"), dict) else {}
    family_dependence = (
        bundle_entry.get("family_dependence") if isinstance(bundle_entry.get("family_dependence"), dict) else {}
    )
    completion_state = (
        bundle_entry.get("completion_state") if isinstance(bundle_entry.get("completion_state"), dict) else {}
    )
    failure = bundle_entry.get("failure") if isinstance(bundle_entry.get("failure"), dict) else {}
    provenance = bundle_entry.get("provenance") if isinstance(bundle_entry.get("provenance"), dict) else {}
    open_world = bundle_entry.get("open_world") if isinstance(bundle_entry.get("open_world"), dict) else {}
    strict_open_world = (
        bundle_entry.get("strict_open_world") if isinstance(bundle_entry.get("strict_open_world"), dict) else {}
    )

    failure_stage = str((failure or {}).get("stage") or "").strip().upper()
    terminal_failure_class = str((failure or {}).get("terminal_failure_class") or "").strip() or None
    candidate_abstain_reason = (
        _stable_reason_token((request_ir or {}).get("abstain_reason"))
        or _stable_reason_token((family_dependence or {}).get("abstain_reason"))
        or _stable_reason_token((provenance or {}).get("semantic_guided_abstain_reason"))
        or _stable_reason_token(terminal_failure_class)
        or None
    )
    closure_source = str(intent.get("closure_source") or "").strip().lower() or None
    required_contract = intent.get("required_contract") if isinstance(intent.get("required_contract"), dict) else {}
    allowed_execution_paths = {
        str(item).strip().lower()
        for item in (required_contract.get("allowed_execution_paths") or [])
        if isinstance(item, str) and str(item).strip()
    }
    intent_satisfying_paths = {
        str(item).strip().lower()
        for item in (required_contract.get("intent_satisfying_paths") or [])
        if isinstance(item, str) and str(item).strip()
    }
    allowed_by_execution_contract = closure_source in allowed_execution_paths if closure_source else False
    satisfies_intent_contract = closure_source in intent_satisfying_paths if closure_source else False
    next_required_step = _name_only_next_required_step(completion_state, failure_stage=failure_stage)

    decision = "failed"
    abstain_reason = None
    decision_reason = (
        terminal_failure_class
        or str(intent.get("status") or "").strip()
        or failure_stage.lower()
        or "name_only_outcome_unknown"
    )
    if intent.get("meets_intent") is True and completion_state.get("fully_validated") is True:
        decision = "intent_met"
        decision_reason = str(intent.get("status") or "").strip() or "name_only_intent_met"
    elif intent.get("meets_intent") is True:
        decision = "partial"
        decision_reason = "intent_not_fully_validated"
    elif failure_stage in {"CAPABILITY_CHECK", "NAME_ONLY_GATE"}:
        decision = "fail_closed"
        decision_reason = terminal_failure_class or failure_stage.lower()
    elif completion_state.get("stage_ceiling") == "pre_generation" and (
        candidate_abstain_reason
        or failure_stage == "RESEARCH"
        or str((provenance or {}).get("generation_origin") or "").strip().lower() == "research_short_circuit"
    ):
        decision = "abstain"
        decision_reason = candidate_abstain_reason or terminal_failure_class or "research_abstain"
        abstain_reason = candidate_abstain_reason or terminal_failure_class or "research_abstain"
    elif intent.get("partial") is True:
        decision = "partial"
        decision_reason = str(intent.get("status") or "").strip() or "name_only_partial"
    else:
        abstain_reason = None

    if decision == "partial" and not next_required_step:
        next_required_step = _name_only_partial_next_required_step(bundle_entry)

    return {
        "request_kind": "name_only",
        "mode": str(intent.get("mode") or "").strip() or "unknown",
        "decision": decision,
        "decision_reason": decision_reason,
        "abstain_reason": abstain_reason,
        "terminal_failure_class": terminal_failure_class,
        "closure_source": closure_source,
        "allowed_by_execution_contract": allowed_by_execution_contract,
        "satisfies_intent_contract": satisfies_intent_contract,
        "stage_ceiling": str((completion_state or {}).get("stage_ceiling") or "").strip() or "unknown",
        "fully_validated": bool((completion_state or {}).get("fully_validated")),
        "next_required_step": next_required_step,
        "open_world_class": str((open_world or {}).get("class") or "").strip() or None,
        "strict_open_world_class": str((strict_open_world or {}).get("class") or "").strip() or None,
        "stack_dependence_class": str((bundle_entry.get("stack_dependence") or {}).get("class") or "").strip() or None,
        "family_dependence_class": str((family_dependence or {}).get("class") or "").strip() or None,
    }


def _name_only_outcome_summary(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    name_only_bundles = 0
    by_decision: Dict[str, int] = {}
    by_next_required_step: Dict[str, int] = {}
    by_abstain_reason: Dict[str, int] = {}
    by_terminal_failure_class: Dict[str, int] = {}
    by_stage_ceiling: Dict[str, int] = {}
    for entry in bundles:
        payload = entry.get("name_only_outcome") if isinstance(entry.get("name_only_outcome"), dict) else {}
        if not payload or payload.get("request_kind") != "name_only":
            continue
        name_only_bundles += 1
        decision = str(payload.get("decision") or "").strip() or "unknown"
        by_decision[decision] = by_decision.get(decision, 0) + 1
        next_required_step = str(payload.get("next_required_step") or "").strip()
        if next_required_step:
            by_next_required_step[next_required_step] = by_next_required_step.get(next_required_step, 0) + 1
        abstain_reason = str(payload.get("abstain_reason") or "").strip()
        if abstain_reason:
            by_abstain_reason[abstain_reason] = by_abstain_reason.get(abstain_reason, 0) + 1
        terminal_failure_class = str(payload.get("terminal_failure_class") or "").strip()
        if terminal_failure_class:
            by_terminal_failure_class[terminal_failure_class] = (
                by_terminal_failure_class.get(terminal_failure_class, 0) + 1
            )
        stage_ceiling = str(payload.get("stage_ceiling") or "").strip() or "unknown"
        by_stage_ceiling[stage_ceiling] = by_stage_ceiling.get(stage_ceiling, 0) + 1

    return {
        "bundle_count": len(bundles),
        "name_only_bundles": name_only_bundles,
        "intent_met_bundles": by_decision.get("intent_met", 0),
        "partial_bundles": by_decision.get("partial", 0),
        "abstained_bundles": by_decision.get("abstain", 0),
        "fail_closed_bundles": by_decision.get("fail_closed", 0),
        "failed_bundles": by_decision.get("failed", 0),
        "by_decision": by_decision,
        "by_next_required_step": by_next_required_step,
        "by_abstain_reason": by_abstain_reason,
        "by_terminal_failure_class": by_terminal_failure_class,
        "by_stage_ceiling": by_stage_ceiling,
    }


def _name_only_planning_summary(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    name_only_bundles = 0
    with_planning_focus_bundles = 0
    by_primary_focus: Dict[str, int] = {}
    by_focus: Dict[str, int] = {}
    by_reason_token: Dict[str, int] = {}
    for entry in bundles:
        spec = (
            entry.get("name_only_generation_spec")
            if isinstance(entry.get("name_only_generation_spec"), dict)
            else {}
        )
        required_contract = spec.get("required_contract") if isinstance(spec.get("required_contract"), dict) else {}
        if not required_contract:
            continue
        name_only_bundles += 1
        planning_focus_summary = (
            spec.get("planning_focus_summary")
            if isinstance(spec.get("planning_focus_summary"), dict)
            else {}
        )
        if not planning_focus_summary:
            continue
        with_planning_focus_bundles += 1
        primary_focus = str(planning_focus_summary.get("primary_focus") or "").strip() or "unknown"
        by_primary_focus[primary_focus] = by_primary_focus.get(primary_focus, 0) + 1
        for focus in planning_focus_summary.get("focuses") or []:
            token = str(focus or "").strip()
            if not token:
                continue
            by_focus[token] = by_focus.get(token, 0) + 1
        for reason in planning_focus_summary.get("reason_tokens") or []:
            token = str(reason or "").strip()
            if not token:
                continue
            by_reason_token[token] = by_reason_token.get(token, 0) + 1
    return {
        "bundle_count": len(bundles),
        "name_only_bundles": name_only_bundles,
        "with_planning_focus_bundles": with_planning_focus_bundles,
        "by_primary_focus": by_primary_focus,
        "by_focus": by_focus,
        "by_reason_token": by_reason_token,
    }


def _bundle_compiler_contract(metadata_dir: Path) -> Dict[str, Any]:
    profile = load_semantic_profile(metadata_dir) or {}
    contract = load_generator_contract(metadata_dir) or {}
    generator_manifest_payload = _load_json(metadata_dir / "generator_manifest.json") or {}
    generator_manifest = (
        generator_manifest_payload.get("manifest")
        if isinstance(generator_manifest_payload.get("manifest"), dict)
        else generator_manifest_payload
    )
    generator_meta = generator_manifest.get("metadata") if isinstance(generator_manifest, dict) else {}
    payload: Dict[str, Any] = {}
    compiler_supported = contract.get("compiler_supported")
    if isinstance(compiler_supported, bool):
        payload["compiler_supported"] = compiler_supported
    elif isinstance(profile.get("compiler_supported"), bool):
        payload["compiler_supported"] = profile.get("compiler_supported")
    for key in ("compiler_strategy", "compiler_reason"):
        value = contract.get(key)
        if not isinstance(value, str) or not value.strip():
            value = profile.get(key)
        if isinstance(value, str) and value.strip():
            payload[key] = value.strip()
    support_level = profile.get("support_level")
    if isinstance(support_level, str) and support_level.strip():
        payload["support_level"] = support_level.strip()
    family = profile.get("family")
    if isinstance(family, str) and family.strip():
        payload["family"] = family.strip()
    if isinstance(generator_meta, dict):
        for key in ("compiler_family", "stack_scaffold_id", "stack_scaffold_version", "fragment_id", "compose_mode"):
            value = generator_meta.get(key)
            if isinstance(value, str) and value.strip():
                payload[key] = value.strip()
        run = generator_manifest.get("run") if isinstance(generator_manifest.get("run"), dict) else {}
        env = run.get("env") if isinstance(run, dict) else {}
        if isinstance(env, dict) and env:
            payload["service_env"] = {
                str(key): str(value)
                for key, value in env.items()
                if isinstance(key, str) and key.strip() and value not in (None, "")
            }
    for key in ("compiler_family", "stack_scaffold_id", "stack_scaffold_version", "fragment_id", "compose_mode"):
        if key in payload:
            continue
        value = contract.get(key) if isinstance(contract, dict) else None
        if not isinstance(value, str) or not value.strip():
            value = profile.get(key) if isinstance(profile, dict) else None
        if isinstance(value, str) and value.strip():
            payload[key] = value.strip()
    if "service_env" not in payload:
        service_env = contract.get("service_env") if isinstance(contract, dict) else None
        if isinstance(service_env, dict) and service_env:
            payload["service_env"] = {
                str(key): str(value)
                for key, value in service_env.items()
                if isinstance(key, str) and key.strip() and value not in (None, "")
            }
    if not payload:
        return {}
    return payload


def _bundle_semantic_surface(
    metadata_dir: Path,
    vuln_id: str,
    eval_record: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    contract = load_generator_contract(metadata_dir) or {}
    profile = load_semantic_profile(metadata_dir) or {}
    semantic_contract = contract.get("semantic_contract") if isinstance(contract, dict) else {}
    semantic_consistency = (
        eval_record.get("semantic_consistency")
        if isinstance(eval_record, dict) and isinstance(eval_record.get("semantic_consistency"), dict)
        else {}
    )

    supported: Optional[bool] = None
    status = ""
    source = ""

    if isinstance(eval_record, dict):
        if isinstance(eval_record.get("semantic_supported"), bool):
            supported = bool(eval_record.get("semantic_supported"))
        status = str(eval_record.get("semantic_status") or "").strip().lower()
        source = str(eval_record.get("semantic_source") or "").strip()

    if isinstance(semantic_consistency, dict):
        if supported is None and isinstance(semantic_consistency.get("supported"), bool):
            supported = bool(semantic_consistency.get("supported"))
        if not status:
            status = str(semantic_consistency.get("status") or "").strip().lower()
        if not source:
            source = str(semantic_consistency.get("source") or "").strip()

    if isinstance(semantic_contract, dict):
        contract_status = str(semantic_contract.get("status") or "").strip().lower()
        if not status and contract_status:
            status = contract_status
        if not source:
            source = "resolved_contract.semantic_contract"
        if supported is None:
            if contract_status == "aligned":
                supported = True
            elif contract_status in {"unsupported", "empty"}:
                supported = False

    support_level = str(profile.get("support_level") or "").strip().lower()
    compiler_supported = profile.get("compiler_supported")
    if supported is None and support_level == "unsupported" and compiler_supported is False:
        supported = False
        if not status:
            status = "unsupported"
        if not source:
            source = "semantic_profile"

    if supported is None:
        if status == "aligned":
            supported = True
        elif status in {"unsupported", "empty"}:
            supported = False

    payload: Dict[str, Any] = {}
    if supported is not None:
        payload["supported"] = supported
    if status:
        payload["status"] = status
    if source:
        payload["source"] = source
    return payload


def _compiler_contract_summary(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    strategies: Dict[str, int] = {}
    support_levels: Dict[str, int] = {}
    supported_bundles = 0
    for entry in bundles:
        compiler_contract = entry.get("compiler_contract") or {}
        if not isinstance(compiler_contract, dict):
            continue
        if compiler_contract.get("compiler_supported") is True:
            supported_bundles += 1
        strategy = str(compiler_contract.get("compiler_strategy") or "").strip()
        if strategy:
            strategies[strategy] = strategies.get(strategy, 0) + 1
        support_level = str(compiler_contract.get("support_level") or "").strip()
        if support_level:
            support_levels[support_level] = support_levels.get(support_level, 0) + 1
    return {
        "bundle_count": len(bundles),
        "supported_bundles": supported_bundles,
        "unsupported_bundles": max(0, len(bundles) - supported_bundles),
        "by_strategy": strategies,
        "by_support_level": support_levels,
    }


def _verification_summary(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_rule_source: Dict[str, int] = {}
    by_trust: Dict[str, int] = {}
    by_independence: Dict[str, int] = {}
    low_trust_bundles = 0
    for entry in bundles:
        verification = entry.get("verification") or {}
        if not isinstance(verification, dict):
            continue
        rule_source = str(verification.get("rule_source") or "").strip()
        trust = str(verification.get("trust") or "").strip()
        independence = str(verification.get("independence") or "").strip()
        if rule_source:
            by_rule_source[rule_source] = by_rule_source.get(rule_source, 0) + 1
        if trust:
            by_trust[trust] = by_trust.get(trust, 0) + 1
            if trust.lower() == "low":
                low_trust_bundles += 1
        if independence:
            by_independence[independence] = by_independence.get(independence, 0) + 1
    return {
        "bundle_count": len(bundles),
        "by_rule_source": by_rule_source,
        "by_trust": by_trust,
        "by_independence": by_independence,
        "low_trust_bundles": low_trust_bundles,
    }


def _name_resolution_summary(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_source: Dict[str, int] = {}
    by_confidence: Dict[str, int] = {}
    by_match_class: Dict[str, int] = {}
    resolved_bundles = 0
    for entry in bundles:
        resolution = entry.get("name_resolution")
        if not isinstance(resolution, dict) or not resolution:
            continue
        resolved_bundles += 1
        source = str(resolution.get("source") or "").strip()
        confidence = str(resolution.get("confidence") or "").strip()
        match_class = str(resolution.get("match_class") or "").strip()
        if source:
            by_source[source] = by_source.get(source, 0) + 1
        if confidence:
            by_confidence[confidence] = by_confidence.get(confidence, 0) + 1
        if match_class:
            by_match_class[match_class] = by_match_class.get(match_class, 0) + 1
    return {
        "bundle_count": len(bundles),
        "resolved_bundles": resolved_bundles,
        "by_source": by_source,
        "by_confidence": by_confidence,
        "by_match_class": by_match_class,
    }


def _bundle_requires_semantic_support(bundle) -> bool:
    vuln_id = str(getattr(bundle, "vuln_id", "") or "").strip().upper()
    if vuln_id.startswith("NAME-"):
        return True
    return not bool(load_static_rule(vuln_id))


def _bundle_dynamicness_verdict(provenance: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(provenance, dict) or not provenance:
        return {
            "verdict": "unclassified",
            "trusted": False,
            "reason": "generation provenance missing",
        }

    origin = str(provenance.get("generation_origin") or "").strip()
    fallback_used = provenance.get("fallback_used") is True
    family_override_applied = provenance.get("family_override_applied") is True

    if fallback_used or origin == "deterministic_fallback":
        return {
            "verdict": "deterministic fallback dependent",
            "trusted": False,
            "reason": "deterministic fallback generation path was used",
        }
    if origin in {"research_short_circuit", "capability_gate_rejected", "name_only_gate_rejected"}:
        failure_class = str(provenance.get("failure_class") or "").strip().lower()
        if origin == "capability_gate_rejected":
            reason = "generation was skipped after strict capability precheck"
            if failure_class == "strict_dynamic_live_llm_unavailable":
                reason = "generation was skipped after strict live-LLM capability precheck"
            elif failure_class == "strict_dynamic_remote_research_unavailable":
                reason = "generation was skipped after strict remote-research capability precheck"
        elif origin == "name_only_gate_rejected":
            reason = "generation was skipped after strict live-LLM gate"
        else:
            reason = "generation was skipped after research precheck"
            if failure_class == "semantic_support_missing":
                reason = "generation was skipped after semantic support precheck"
            elif failure_class in {"remote_provider_unavailable", "remote_evidence_missing"}:
                reason = "generation was skipped after remote evidence precheck"
            elif failure_class == "evidence_low_relevance":
                reason = "generation was skipped after evidence relevance precheck"
            elif failure_class == "provider_degraded":
                reason = "generation was skipped after provider health precheck"
        return {
            "verdict": "pre-generation fail-closed",
            "trusted": False,
            "reason": reason,
        }
    if origin == "compiler_generated":
        return {
            "verdict": "compiler-first",
            "trusted": False,
            "reason": "compiler-generated scaffold/fragment path was used",
        }
    if origin in {"built_in_template", "runtime_template_clone"}:
        return {
            "verdict": "template-assisted",
            "trusted": False,
            "reason": f"template-backed generation path was used ({origin})",
        }
    if family_override_applied or origin == "family_override":
        return {
            "verdict": "template-assisted",
            "trusted": False,
            "reason": "family-specific deterministic override was applied",
        }
    if origin == "llm_manifest":
        return {
            "verdict": "trusted dynamic",
            "trusted": True,
            "reason": "llm_manifest provenance recorded without fallback/template override",
        }
    return {
        "verdict": "unclassified",
        "trusted": False,
        "reason": f"unsupported or incomplete provenance origin: {origin or 'missing'}",
    }


def _collect_indices(metadata_dir: Path, artifacts_dir: Path) -> Dict[str, Optional[str]]:
    indices = {
        "researcher_reports": _existing(metadata_dir / "researcher_reports.json"),
        "generator_runs": _existing(metadata_dir / "generator_runs.json"),
        "reviewer_report": _existing(metadata_dir / "reviewer_report.json"),
        "reviewer_reports_index": _existing(metadata_dir / "reviewer_reports.json"),
        "semantic_profile": _existing(metadata_dir / "semantic_profile.json"),
        "run_index": _existing(artifacts_dir / "run" / "index.json"),
        "evals": _existing(artifacts_dir / "reports" / "evals.json"),
        "diversity": _existing(artifacts_dir / "reports" / "diversity.json"),
        "performance": _existing(metadata_dir / "performance_summary.json"),
    }
    return indices


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        LOGGER.warning("Failed to parse JSON at %s: %s", path, exc)
        return None


def _existing(path: Path) -> Optional[str]:
    if path.exists():
        return str(path)
    return None


def main() -> None:
    args = parse_args()
    plan = load_plan(args.sid)
    assert_review_passed(args.sid, plan, args.allow_intentional_vuln)
    snapshot_workspace(args.sid)
    write_manifest(args.sid, plan)


if __name__ == "__main__":
    main()
