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
from common.contracts import load_generator_contract, load_semantic_profile
from common.rules import load_static_rule
from common.run_matrix import (
    artifacts_dir_for_bundle,
    load_vuln_bundles,
    metadata_dir_for_bundle,
    workspace_dir_for_bundle,
)

LOGGER = get_logger(__name__)


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
        "performance": performance,
        "indices": _collect_indices(metadata_dir, artifacts_dir),
        "reports": {
            "evals": _load_json(reports_dir / "evals.json"),
            "diversity": _load_json(reports_dir / "diversity.json"),
        },
    }
    failure = _failure_summary(sid)
    if failure:
        manifest["failure"] = failure
    if len(bundles) == 1:
        compiler_contract = bundles[0].get("compiler_contract") or {}
        if isinstance(compiler_contract.get("compiler_supported"), bool):
            manifest["compiler_supported"] = compiler_contract["compiler_supported"]
        for key in ("compiler_strategy", "compiler_reason"):
            value = compiler_contract.get(key)
            if isinstance(value, str) and value.strip():
                manifest[key] = value.strip()
        generalization = bundles[0].get("generalization") or {}
        class_name = generalization.get("class")
        if isinstance(class_name, str) and class_name.strip():
            manifest["generalization_class"] = class_name.strip()
        if isinstance(generalization.get("counts_as_generalization"), bool):
            manifest["counts_as_generalization"] = generalization["counts_as_generalization"]
        reason = generalization.get("reason")
        if isinstance(reason, str) and reason.strip():
            manifest["generalization_reason"] = reason.strip()
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
        researcher_report = metadata_dir / "researcher_report.json"
        generator_template = metadata_dir / "generator_template.json"
        reviewer_report = metadata_dir / "reviewer_report.json"
        generator_payload = _load_json(generator_template)
        pattern_id = (generator_payload or {}).get("pattern_id") or requirement.get("pattern_id")
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
        generalization = _bundle_generalization_verdict(
            bundle,
            pattern_id=pattern_id,
            promotion=promotion,
            dynamicness=dynamicness,
            compiler_contract=compiler_contract,
            provenance=provenance,
        )

        bundle_entry = {
            "vuln_id": bundle.vuln_id,
            "slug": bundle.slug,
            "pattern_id": pattern_id,
            "promotion": promotion,
            "failure": failure,
            "provenance": provenance,
            "dynamicness": dynamicness,
            "generalization": generalization,
            "compiler_contract": compiler_contract,
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
        if _bundle_requires_semantic_support(bundle):
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
    for key in ("fallback_used", "family_override_applied", "llm_stub_used"):
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
    llm_stub_bundles = 0
    fallback_bundles = 0
    family_override_bundles = 0
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
        if provenance.get("fallback_used") is True:
            fallback_bundles += 1
        if provenance.get("family_override_applied") is True:
            family_override_bundles += 1
    return {
        "bundle_count": len(bundles),
        "by_origin": by_origin,
        "by_dynamicness_verdict": by_dynamicness_verdict,
        "llm_stub_bundles": llm_stub_bundles,
        "fallback_bundles": fallback_bundles,
        "family_override_bundles": family_override_bundles,
    }


def _bundle_generalization_verdict(
    bundle,
    *,
    pattern_id: Optional[str],
    promotion: Dict[str, Any],
    dynamicness: Dict[str, Any],
    compiler_contract: Dict[str, Any],
    provenance: Dict[str, Any],
) -> Dict[str, Any]:
    vuln_id = str(getattr(bundle, "vuln_id", "") or "").strip().upper()
    pattern = str(pattern_id or "").strip()
    dynamicness_verdict = str((dynamicness or {}).get("verdict") or "").strip().lower()
    support_level = str((compiler_contract or {}).get("support_level") or "").strip().lower()
    fallback_class = str((provenance or {}).get("fallback_class") or "").strip().lower()
    promotion_eligible = bool((promotion or {}).get("eligible"))
    generation_origin = str((provenance or {}).get("generation_origin") or "").strip().lower()

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
            }
        if (
            promotion_eligible
            and dynamicness_verdict in {"compiler-first", "trusted dynamic"}
            and fallback_class != "generic_unsupported_family"
        ):
            return {
                "class": "real_free_form_positive",
                "counts_as_generalization": True,
                "reason": f"free-form vuln_name lane closed via {dynamicness_verdict} without generic fallback",
            }
        return {
            "class": "real_free_form_non_generalizing",
            "counts_as_generalization": False,
            "reason": "free-form NAME-* lane exists but is not yet strong enough to count as generalization evidence",
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


def _generalization_summary(bundles: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_class: Dict[str, int] = {}
    positive_generalization_bundles = 0
    for entry in bundles:
        generalization = entry.get("generalization") or {}
        if not isinstance(generalization, dict):
            continue
        class_name = str(generalization.get("class") or "").strip()
        if class_name:
            by_class[class_name] = by_class.get(class_name, 0) + 1
        if generalization.get("counts_as_generalization") is True:
            positive_generalization_bundles += 1
    return {
        "bundle_count": len(bundles),
        "positive_generalization_bundles": positive_generalization_bundles,
        "by_class": by_class,
    }


def _bundle_compiler_contract(metadata_dir: Path) -> Dict[str, Any]:
    profile = load_semantic_profile(metadata_dir) or {}
    contract = load_generator_contract(metadata_dir) or {}
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
    if not payload:
        return {}
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
