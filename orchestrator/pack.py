"""PACK stage consolidating artifacts."""
from __future__ import annotations

import argparse
import json
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
from common.contracts import (
    executor_feasibility_summary,
    load_generator_contract,
    load_semantic_profile,
    lower_bound_summary,
)
from common.rules import load_static_rule
from common.run_matrix import (
    artifacts_dir_for_bundle,
    bundle_requirement,
    load_vuln_bundles,
    metadata_dir_for_bundle,
    workspace_dir_for_bundle,
)

LOGGER = get_logger(__name__)


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


def write_manifest(sid: str, plan: dict, *, filename: str = "manifest.json") -> Path:
    metadata_dir = get_metadata_dir(sid)
    artifacts_dir = get_artifacts_dir(sid)
    bundles = _collect_bundle_records(plan, sid)
    reports_dir = artifacts_dir / "reports"
    performance = _load_json(metadata_dir / "performance_summary.json")
    promotion = _promotion_summary(bundles)
    memory_promotion = _memory_promotion_summary(bundles)
    generation_summary = _generation_summary(bundles)
    dynamic_eval_summary = _dynamic_eval_summary(bundles)
    generalization_summary = _generalization_summary(bundles)
    open_world_summary = _open_world_summary(bundles)
    strict_open_world_summary = _strict_open_world_summary(bundles)
    compiler_contract_summary = _compiler_contract_summary(bundles)
    verification_summary = _verification_summary(bundles)
    researcher_summary = _researcher_summary(bundles)
    request_identity_summary = _request_identity_summary(bundles)
    name_resolution_summary = _name_resolution_summary(bundles)
    lower_bound_rollup = _lower_bound_rollup(bundles)
    executor_feasibility_rollup = _executor_feasibility_rollup(bundles)
    artifact_quality_summary = _artifact_quality_summary(bundles)
    template_dependence_summary = _template_dependence_summary(bundles)
    partial_progress_summary = _partial_progress_summary(bundles)
    intent_satisfaction_summary = _intent_satisfaction_summary(bundles)
    pipeline_result = _pipeline_result(sid)
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
        "generation_summary": generation_summary,
        "dynamic_eval_summary": dynamic_eval_summary,
        "generalization_summary": generalization_summary,
        "open_world_summary": open_world_summary,
        "strict_open_world_summary": strict_open_world_summary,
        "compiler_contract_summary": compiler_contract_summary,
        "verification_summary": verification_summary,
        "researcher_summary": researcher_summary,
        "request_identity_summary": request_identity_summary,
        "name_resolution_summary": name_resolution_summary,
        "lower_bound_summary": lower_bound_rollup,
        "executor_feasibility_summary": executor_feasibility_rollup,
        "artifact_quality_summary": artifact_quality_summary,
        "template_dependence_summary": template_dependence_summary,
        "partial_progress_summary": partial_progress_summary,
        "intent_satisfaction_summary": intent_satisfaction_summary,
        "performance": performance,
        "indices": _collect_indices(metadata_dir, artifacts_dir),
        "reports": {
            "evals": _load_json(reports_dir / "evals.json"),
            "diversity": _load_json(reports_dir / "diversity.json"),
        },
    }
    requirement = plan.get("requirement") if isinstance(plan, dict) else {}
    if isinstance(requirement, dict):
        name_resolution = requirement.get("name_resolution")
        if isinstance(name_resolution, dict) and name_resolution:
            manifest["name_resolution"] = name_resolution
    failure = _failure_summary(sid)
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
        exploit_oracle = bundles[0].get("exploit_oracle") or {}
        if isinstance(exploit_oracle, dict) and exploit_oracle:
            manifest["exploit_oracle"] = exploit_oracle
        name_only_generation_spec = bundles[0].get("name_only_generation_spec") or {}
        if isinstance(name_only_generation_spec, dict) and name_only_generation_spec:
            manifest["name_only_generation_spec"] = name_only_generation_spec
        dynamic_eval = bundles[0].get("dynamic_eval") or {}
        if isinstance(dynamic_eval, dict) and dynamic_eval:
            manifest["dynamic_eval"] = dynamic_eval
        artifact_quality = bundles[0].get("artifact_quality") or {}
        if isinstance(artifact_quality, dict) and artifact_quality:
            manifest["artifact_quality"] = artifact_quality
        intent_satisfaction = bundles[0].get("intent_satisfaction") or {}
        if isinstance(intent_satisfaction, dict) and intent_satisfaction:
            manifest["intent_satisfaction"] = intent_satisfaction
            status = intent_satisfaction.get("status")
            if isinstance(status, str) and status.strip():
                manifest["intent_satisfaction_status"] = status.strip()
            meets_intent = intent_satisfaction.get("meets_intent")
            if isinstance(meets_intent, bool):
                manifest["meets_name_only_intent"] = meets_intent
        researcher = bundles[0].get("researcher") or {}
        if isinstance(researcher, dict) and researcher:
            manifest["researcher"] = researcher
        request_identity = bundles[0].get("request_identity") or {}
        if isinstance(request_identity, dict) and request_identity:
            manifest["request_identity"] = request_identity
        memory_promotion_payload = bundles[0].get("memory_promotion") or {}
        if isinstance(memory_promotion_payload, dict) and memory_promotion_payload:
            manifest["memory_promotion"] = memory_promotion_payload
            if isinstance(memory_promotion_payload.get("eligible"), bool):
                manifest["memory_promotion_eligible"] = memory_promotion_payload["eligible"]
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


def _pipeline_result(sid: str) -> str:
    loop_state_path = get_metadata_dir(sid) / "loop_state.json"
    if not loop_state_path.exists():
        return "success"
    try:
        state = json.loads(loop_state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "success"
    last_result = str(state.get("last_result") or "").strip().lower()
    if last_result in {"success", "failure"}:
        return last_result
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
        runtime_recipe = _bundle_runtime_recipe(
            contract=contract,
            requirement=requirement_view,
            compiler_contract=compiler_contract,
            executor_feasibility=executor_feasibility,
        )
        exploit_oracle = (
            dict(contract.get("exploit_oracle"))
            if isinstance(contract.get("exploit_oracle"), dict)
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
            "exploit_oracle": exploit_oracle,
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
        bundle_entry["artifact_quality"] = _bundle_artifact_quality(bundle_entry)
        bundle_entry["intent_satisfaction"] = _bundle_intent_satisfaction(bundle_entry, requirement_view)
        bundle_entry["memory_promotion"] = _bundle_memory_promotion_status(bundle_entry)
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
    for key in ("generation_origin", "template_id", "source", "fallback_class", "materializer"):
        value = _read_str(key)
        if value:
            payload[key] = value
    for key in ("fallback_used", "family_override_applied", "llm_stub_used", "llm_fixture_used"):
        value = _read_bool(key)
        if value is not None:
            payload[key] = value
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


def _bundle_generalization_verdict(
    bundle,
    *,
    pattern_id: Optional[str],
    promotion: Dict[str, Any],
    dynamicness: Dict[str, Any],
    compiler_contract: Dict[str, Any],
    provenance: Dict[str, Any],
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
    resolution = name_resolution if isinstance(name_resolution, dict) else {}
    resolution_confidence = str(resolution.get("confidence") or "").strip().lower()
    resolution_basis = str(resolution.get("match_class") or "").strip().lower()

    if vuln_id == "CWE-9999":
        reason = "explicit synthetic unknown identifier remains a regression lane"
        if pattern and pattern != "generic-web-vuln":
            reason = f"{reason}; inherited pattern_id={pattern}"
        return {
            "class": "synthetic_regression",
            "counts_as_generalization": False,
            "reason": reason,
        }

    if vuln_id.startswith("NAME-"):
        if support_level == "unsupported" or generation_origin == "research_short_circuit":
            return {
                "class": "unsupported_free_form_negative",
                "counts_as_generalization": False,
                "reason": "free-form NAME-* family is unsupported and intentionally fail-closed",
                "confidence": resolution_confidence or "low",
                "basis": resolution_basis or "synthetic_name",
            }
        if (
            promotion_eligible
            and dynamicness_verdict in {"compiler-first", "trusted dynamic"}
            and fallback_class != "generic_unsupported_family"
            and resolution_confidence == "high"
            and resolution_basis in {"catalog_alias", "exact_identifier"}
        ):
            return {
                "class": "real_free_form_positive",
                "counts_as_generalization": True,
                "reason": f"free-form vuln_name lane closed via {dynamicness_verdict} without generic fallback",
                "confidence": resolution_confidence or "unknown",
                "basis": resolution_basis or "unknown",
            }
        return {
            "class": "real_free_form_non_generalizing",
            "counts_as_generalization": False,
            "reason": (
                "free-form NAME-* lane exists but is not yet strong enough to count as generalization evidence"
                if not resolution_confidence
                else f"free-form NAME-* lane closed but name resolution confidence/basis is {resolution_confidence}/{resolution_basis or 'unknown'}"
            ),
            "confidence": resolution_confidence or "unknown",
            "basis": resolution_basis or "unknown",
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


def _bundle_open_world_verdict(
    bundle,
    *,
    pattern_id: Optional[str],
    promotion: Dict[str, Any],
    dynamicness: Dict[str, Any],
    compiler_contract: Dict[str, Any],
    provenance: Dict[str, Any],
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
    resolution = name_resolution if isinstance(name_resolution, dict) else {}
    resolution_confidence = str(resolution.get("confidence") or "").strip().lower()
    resolution_basis = str(resolution.get("match_class") or "").strip().lower()
    dynamic_eval_payload = dynamic_eval if isinstance(dynamic_eval, dict) else {}
    dynamic_eval_status = str(dynamic_eval_payload.get("status") or "").strip().lower()
    failure_payload = failure if isinstance(failure, dict) else {}
    failure_stage = str(failure_payload.get("stage") or "").strip().upper()
    failure_terminal_class = str(failure_payload.get("terminal_failure_class") or "").strip().lower()
    lower_bound_available = (
        support_level in {"builtin_supported", "compiler_supported"}
        or bool((compiler_contract or {}).get("compiler_supported"))
        or bool(load_static_rule(vuln_id))
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

    if vuln_id.startswith("NAME-"):
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
    requires_research_contract = vuln_id.startswith("NAME-") or not bool(load_static_rule(vuln_id))

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
) -> Dict[str, Any]:
    direct = contract.get("runtime_recipe") if isinstance(contract.get("runtime_recipe"), dict) else None
    if isinstance(direct, dict) and direct:
        return direct

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
    recipe: Dict[str, Any] = {
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
    return recipe


def _bundle_dynamic_eval_summary(
    *,
    requirement: Dict[str, Any],
    metadata_dir: Path,
) -> Dict[str, Any]:
    policy = requirement.get("policy") if isinstance(requirement.get("policy"), dict) else {}
    request_identity = requirement.get("request_identity") if isinstance(requirement.get("request_identity"), dict) else {}
    name_driven = bool((request_identity or {}).get("name_driven")) or str(requirement.get("vuln_id") or "").strip().upper().startswith("NAME-")
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
    report = _load_json(metadata_dir / "researcher_report.json") or {}
    report_present = bool(report)
    ambiguous = None
    summary: Dict[str, Any] = {
        "shadow_mode_enabled": bool((researcher_cfg or {}).get("shadow_mode")),
        "force_run": bool((researcher_cfg or {}).get("force_run")) if isinstance(researcher_cfg, dict) else False,
        "dynamic_eval_enabled": (
            bool((policy or {}).get("dynamic_eval"))
            or (
                (
                    bool(((requirement.get("request_identity") or {}).get("name_driven")))
                    or str(requirement.get("vuln_id") or "").strip().upper().startswith("NAME-")
                )
                and str((policy or {}).get("name_only_mode") or "").strip().lower() in {"dynamic", "strict_dynamic"}
            )
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
    has_rule_source = isinstance(rule_source, str) and rule_source.strip()
    has_trust = isinstance(trust, str) and trust.strip()
    has_oracle_contract = False
    if isinstance(exploit_oracle, dict) and exploit_oracle:
        if any(
            key in exploit_oracle and exploit_oracle.get(key)
            for key in ("success_signature", "flag_token", "assertion_program", "poc_cmd")
        ):
            has_oracle_contract = True
    if has_rule_source and has_trust:
        oracle_clarity = "high" if readme_verification else "medium"
    elif has_rule_source:
        oracle_clarity = "low"
    elif has_oracle_contract:
        oracle_clarity = "high" if readme_verification else "medium"

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
    for entry in bundles:
        generalization = entry.get("generalization") or {}
        if not isinstance(generalization, dict):
            continue
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
    return {
        "bundle_count": len(bundles),
        "positive_generalization_bundles": positive_generalization_bundles,
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
    average_score = round(total_score / bundle_count, 2) if bundle_count else 0.0
    return {
        "bundle_count": bundle_count,
        "average_score": average_score,
        "by_band": by_band,
        "readme_present_bundles": readme_present_bundles,
        "runtime_recipe_bundles": runtime_recipe_bundles,
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
        if not isinstance(request_identity, dict):
            continue
        input_mode = str(request_identity.get("input_mode") or "").strip()
        if input_mode:
            by_input_mode[input_mode] = by_input_mode.get(input_mode, 0) + 1
        match_class = str(request_identity.get("match_class") or "").strip()
        if match_class:
            by_match_class[match_class] = by_match_class.get(match_class, 0) + 1
        confidence = str(request_identity.get("confidence") or "").strip()
        if confidence:
            by_confidence[confidence] = by_confidence.get(confidence, 0) + 1
        if request_identity.get("name_driven") is True:
            name_driven_bundles += 1
        if request_identity.get("synthetic_resolution") is True:
            synthetic_resolution_bundles += 1
    return {
        "bundle_count": len(bundles),
        "name_driven_bundles": name_driven_bundles,
        "synthetic_resolution_bundles": synthetic_resolution_bundles,
        "by_input_mode": by_input_mode,
        "by_match_class": by_match_class,
        "by_confidence": by_confidence,
    }


def _template_dependence_summary(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    template_assisted_bundles = 0
    template_dependent_bundles = 0
    lower_bound_dependent_bundles = 0
    name_only_lower_bound_bundles = 0
    open_world_positive_bundles = 0
    minimal_dynamic_bundles = 0
    by_open_world_class: Dict[str, int] = {}
    for entry in bundles:
        dynamicness = entry.get("dynamicness") or {}
        open_world = entry.get("open_world") or {}
        provenance = entry.get("provenance") or {}
        if str((dynamicness or {}).get("verdict") or "").strip().lower() == "template-assisted":
            template_assisted_bundles += 1
        if str((provenance or {}).get("materializer") or "").strip().lower() == "minimal_dynamic":
            minimal_dynamic_bundles += 1
        if isinstance(open_world, dict):
            if open_world.get("template_dependent") is True:
                template_dependent_bundles += 1
            if open_world.get("lower_bound_dependent") is True:
                lower_bound_dependent_bundles += 1
            if open_world.get("counts_as_generalization") is True:
                open_world_positive_bundles += 1
            class_name = str(open_world.get("class") or "").strip()
            if class_name:
                by_open_world_class[class_name] = by_open_world_class.get(class_name, 0) + 1
            vuln_id = str(entry.get("vuln_id") or "").strip().upper()
            if vuln_id.startswith("NAME-") and open_world.get("lower_bound_dependent") is True:
                name_only_lower_bound_bundles += 1
    return {
        "bundle_count": len(bundles),
        "template_assisted_bundles": template_assisted_bundles,
        "template_dependent_bundles": template_dependent_bundles,
        "lower_bound_dependent_bundles": lower_bound_dependent_bundles,
        "name_only_lower_bound_bundles": name_only_lower_bound_bundles,
        "open_world_positive_bundles": open_world_positive_bundles,
        "minimal_dynamic_bundles": minimal_dynamic_bundles,
        "by_open_world_class": by_open_world_class,
    }


def _open_world_summary(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_class: Dict[str, int] = {}
    by_confidence: Dict[str, int] = {}
    by_basis: Dict[str, int] = {}
    positive_open_world_bundles = 0
    lower_bound_dependent_bundles = 0
    template_dependent_bundles = 0
    for entry in bundles:
        open_world = entry.get("open_world") or {}
        if not isinstance(open_world, dict):
            continue
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
        if open_world.get("lower_bound_dependent") is True:
            lower_bound_dependent_bundles += 1
        if open_world.get("template_dependent") is True:
            template_dependent_bundles += 1
    return {
        "bundle_count": len(bundles),
        "positive_open_world_bundles": positive_open_world_bundles,
        "lower_bound_dependent_bundles": lower_bound_dependent_bundles,
        "template_dependent_bundles": template_dependent_bundles,
        "by_class": by_class,
        "by_confidence": by_confidence,
        "by_basis": by_basis,
    }


def _strict_open_world_summary(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_class: Dict[str, int] = {}
    positive_strict_open_world_bundles = 0
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
        class_name = str(strict_open_world.get("class") or "").strip()
        if class_name:
            by_class[class_name] = by_class.get(class_name, 0) + 1
        if strict_open_world.get("counts_as_generalization") is True:
            positive_strict_open_world_bundles += 1
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


def _bundle_intent_satisfaction(bundle_entry: Dict[str, Any], requirement_view: Dict[str, Any]) -> Dict[str, Any]:
    request_identity = bundle_entry.get("request_identity") if isinstance(bundle_entry.get("request_identity"), dict) else {}
    vuln_id = str(bundle_entry.get("vuln_id") or "").strip().upper()
    name_driven = bool((request_identity or {}).get("name_driven")) or vuln_id.startswith("NAME-")
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
    if failure_stage in {"RESEARCH", "GENERATOR", "NAME_ONLY_GATE"}:
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
        elif strict_class == "strict_dynamic_generation_failed" or dynamic_eval_status == "dynamic_failed":
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
    if origin == "research_short_circuit":
        failure_class = str(provenance.get("failure_class") or "").strip().lower()
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
    filename = "manifest.json" if _pipeline_result(args.sid) == "success" else "failure_manifest.json"
    write_manifest(args.sid, plan, filename=filename)


if __name__ == "__main__":
    main()
