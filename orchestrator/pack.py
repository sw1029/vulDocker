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
    generation_summary = _generation_summary(bundles)
    generalization_summary = _generalization_summary(bundles)
    compiler_contract_summary = _compiler_contract_summary(bundles)
    verification_summary = _verification_summary(bundles)
    name_resolution_summary = _name_resolution_summary(bundles)
    lower_bound_rollup = _lower_bound_rollup(bundles)
    executor_feasibility_rollup = _executor_feasibility_rollup(bundles)
    partial_progress_summary = _partial_progress_summary(bundles)
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
        "generation_summary": generation_summary,
        "generalization_summary": generalization_summary,
        "compiler_contract_summary": compiler_contract_summary,
        "verification_summary": verification_summary,
        "name_resolution_summary": name_resolution_summary,
        "lower_bound_summary": lower_bound_rollup,
        "executor_feasibility_summary": executor_feasibility_rollup,
        "partial_progress_summary": partial_progress_summary,
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
        lower_bound = bundles[0].get("lower_bound") or {}
        if isinstance(lower_bound, dict) and lower_bound:
            manifest["lower_bound"] = lower_bound
            for key in ("family_non_remote_available", "effective_non_remote_available", "compiler_path_enabled"):
                value = lower_bound.get(key)
                if isinstance(value, bool):
                    manifest[key] = value
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

        bundle_entry = {
            "vuln_id": bundle.vuln_id,
            "slug": bundle.slug,
            "pattern_id": pattern_id,
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
            "compiler_contract": compiler_contract,
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


def _bundle_generation_provenance(
    sid: str,
    bundle,
    metadata_dir: Path,
    generator_template: Optional[Dict[str, Any]] = None,
    *,
    bundle_failure: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    contract = load_generator_contract(metadata_dir) or {}
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
        if generator_template:
            fallback = generator_template.get(key)
            if isinstance(fallback, str) and fallback.strip():
                return fallback.strip()
        return None

    def _read_bool(key: str) -> Optional[bool]:
        for source in (provenance, contract if isinstance(contract, dict) else {}, generator_template or {}):
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
    for key in ("generation_origin", "template_id", "source", "fallback_class"):
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
    promotion_eligible = bool((promotion or {}).get("eligible"))
    generation_origin = str((provenance or {}).get("generation_origin") or "").strip().lower()
    resolution = name_resolution if isinstance(name_resolution, dict) else {}
    resolution_confidence = str(resolution.get("confidence") or "").strip().lower()
    resolution_basis = str(resolution.get("match_class") or "").strip().lower()

    if vuln_id == "CWE-9999":
        reason = "explicit synthetic unknown identifier remains a regression lane"
        if pattern:
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
