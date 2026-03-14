"""선언형 E2E 회귀 케이스를 실행하는 도우미.

각 케이스 디렉터리는 요구 블루프린트, 선택적 런타임 자산(규칙/템플릿),
검증·리뷰 기대치를 정의한다. 이 실행기는 해당 요구를 실체화한 뒤
전체 파이프라인(`plan -> researcher -> generator -> executor -> verifier -> reviewer -> pack`)
을 수행하고, 생성된 manifest를 기대치와 비교한다.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

try:  # pragma: no cover - YAML 모듈 부재 시 JSON으로 대체
    import yaml
except Exception:  # pragma: no cover
    yaml = None

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.schema import normalize_requirement
from common.runtime_assets import ensure_runtime_asset_seed_manifest, record_runtime_asset_seed
from orchestrator import plan as plan_module


class CaseError(RuntimeError):
    """케이스 정의나 실행이 실패했을 때 사용하는 예외."""


@dataclass
class CaseSpec:
    name: str
    requirement: Dict[str, Any]
    runtime_assets: Dict[str, List[Path]]
    options: Dict[str, Any]


def _read_yaml(path: Path) -> Dict[str, Any]:
    if yaml is None:
        raise CaseError("PyYAML is required to load requirement blueprints")
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # pragma: no cover - YAML 파서 상세 예외
        raise CaseError(f"failed to parse YAML: {path}") from exc


def _deep_merge(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_case_spec(case_dir: Path, requirement_path: Optional[Path] = None) -> CaseSpec:
    spec_path = requirement_path or (case_dir / "requirement.yml")
    if not spec_path.exists():
        raise CaseError(f"case requirement not found: {spec_path}")
    raw = _read_yaml(spec_path)
    runtime_assets = raw.pop("runtime_assets", {}) or {}
    options = raw.pop("options", {}) or {}
    requirement: Dict[str, Any]
    if "base_requirement" in raw or "overrides" in raw:
        base_path_value = raw.get("base_requirement")
        if not base_path_value:
            raise CaseError("'base_requirement' must be provided when overrides are present")
        base_path = (REPO_ROOT / str(base_path_value)).resolve()
        if not base_path.exists():
            raise CaseError(f"base requirement does not exist: {base_path}")
        base_payload = _read_yaml(base_path)
        overrides = raw.get("overrides", {}) or {}
        requirement = _deep_merge(base_payload, overrides)
    else:
        requirement = raw
    normalized_assets: Dict[str, List[Path]] = {}
    for key in ("rules", "templates"):
        entries = runtime_assets.get(key) or []
        resolved: List[Path] = []
        for entry in entries:
            candidate = (REPO_ROOT / str(entry)).resolve()
            if not candidate.exists():
                raise CaseError(f"runtime asset missing: {candidate}")
            resolved.append(candidate)
        if resolved:
            normalized_assets[key] = resolved
    return CaseSpec(name=case_dir.name, requirement=requirement, runtime_assets=normalized_assets, options=options)


def _cleanup_sid_dirs(sid: str) -> None:
    for root_name in ("metadata", "artifacts", "workspaces"):
        target = REPO_ROOT / root_name / sid
        if target.exists():
            shutil.rmtree(target)


def _write_plan(requirement: Dict[str, Any], *, multi_vuln_opt_in: bool) -> Dict[str, Any]:
    normalization = normalize_requirement(requirement, multi_vuln_opt_in=multi_vuln_opt_in)
    plan = plan_module.build_plan(normalization)
    sid = plan["sid"]
    _cleanup_sid_dirs(sid)
    plan_module.write_plan(plan)
    return plan


def _copy_asset(source: Path, destination_dir: Path) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / source.name
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)
    else:
        shutil.copy2(source, destination)
    return destination


def _materialize_runtime_assets(sid: str, runtime_assets: Dict[str, List[Path]]) -> None:
    metadata_root = REPO_ROOT / "metadata" / sid
    ensure_runtime_asset_seed_manifest(metadata_root)
    kind_map = {
        "rules": "runtime_rules",
        "templates": "runtime_templates",
    }
    for kind, entries in runtime_assets.items():
        if kind == "rules":
            dest_root = metadata_root / "runtime_rules"
        elif kind == "templates":
            dest_root = metadata_root / "runtime_templates"
        else:
            continue
        for entry in entries:
            destination = _copy_asset(entry, dest_root)
            record_runtime_asset_seed(metadata_root, kind=kind_map[kind], source=entry, destination=destination)

    for dirname in ("runtime_rules", "runtime_templates"):
        (metadata_root / dirname).mkdir(parents=True, exist_ok=True)


def _ensure_docker_ready(env: Dict[str, str]) -> None:
    if os.environ.get("VULD_E2E_SKIP_DOCKER_CHECK"):
        return
    if shutil.which("docker") is None:
        raise CaseError("docker binary not found in PATH")
    try:
        subprocess.run(["docker", "info"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    except subprocess.CalledProcessError as exc:
        raise CaseError("docker daemon is not reachable") from exc


def _case_requires_docker(expectations: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(expectations, dict):
        return True
    manifest_expect = expectations.get("manifest")
    if not isinstance(manifest_expect, dict):
        return True
    failure_expect = manifest_expect.get("failure")
    if not isinstance(failure_expect, dict):
        return True
    stage = str(failure_expect.get("stage") or "").strip().upper()
    return stage not in {"CAPABILITY_CHECK", "RESEARCH"}


def _run_command(command: Sequence[str], env: Dict[str, str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=REPO_ROOT, env=env, check=check, text=True, capture_output=True)


def _execute_pipeline(sid: str, mode: str, env: Dict[str, str]) -> subprocess.CompletedProcess[str]:
    # E2E cases should exercise the same loop-aware runner used by CI/ops.
    return _run_command(
        [sys.executable, "orchestrator/run_pipeline.py", "--sid", sid, "--mode", mode],
        env,
        check=False,
    )


def _manifest_path_for_sid(sid: str) -> Path:
    metadata_dir = REPO_ROOT / "metadata" / sid
    manifest_path = metadata_dir / "manifest.json"
    failure_manifest_path = metadata_dir / "failure_manifest.json"
    if manifest_path.exists():
        return manifest_path
    if failure_manifest_path.exists():
        return failure_manifest_path
    raise CaseError(f"manifest not found for SID {sid}")


def _load_manifest_summary(sid: str, *, pipeline_returncode: int | None = None) -> Dict[str, Any]:
    manifest_path = _manifest_path_for_sid(sid)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    reports = (manifest.get("reports") or {}).get("evals") or {}
    reviewer_path = REPO_ROOT / "metadata" / sid / "reviewer_report.json"
    reviewer = json.loads(reviewer_path.read_text(encoding="utf-8")) if reviewer_path.exists() else {}
    bundles: List[Dict[str, Any]] = []
    for bundle in manifest.get("bundles", []):
        artifacts = bundle.get("artifacts") or {}
        eval_result = artifacts.get("eval_result") or {}
        run_summary = artifacts.get("run_summary") or {}
        compiler_contract = bundle.get("compiler_contract") or {}
        bundles.append(
            {
                "slug": bundle.get("slug"),
                "vuln_id": bundle.get("vuln_id"),
                "verify_pass": eval_result.get("verify_pass"),
                "evidence": eval_result.get("evidence") or "",
                "run_passed": run_summary.get("run_passed"),
                "exit_code": run_summary.get("exit_code"),
                "run_log": run_summary.get("run_log"),
                "rule": eval_result.get("rule"),
                "promotion_eligible": (bundle.get("promotion") or {}).get("eligible"),
                "promotion_reasons": (bundle.get("promotion") or {}).get("reasons") or [],
                "memory_promotion_eligible": (bundle.get("memory_promotion") or {}).get("eligible"),
                "memory_promotion_reasons": (bundle.get("memory_promotion") or {}).get("reasons") or [],
                "support_promotion_eligible": (bundle.get("support_promotion") or {}).get("eligible"),
                "support_promotion_reasons": (bundle.get("support_promotion") or {}).get("reasons") or [],
                "open_world_readiness": bundle.get("open_world_readiness") or {},
                "open_world_ready": (bundle.get("open_world_readiness") or {}).get("ready"),
                "name_only_planning_focus": (
                    ((bundle.get("name_only_generation_spec") or {}).get("planning_focus_summary"))
                    if isinstance(bundle.get("name_only_generation_spec"), dict)
                    else {}
                ),
                "name_only_primary_focus": (
                    (((bundle.get("name_only_generation_spec") or {}).get("planning_focus_summary")) or {}).get("primary_focus")
                    if isinstance(bundle.get("name_only_generation_spec"), dict)
                    else None
                ),
                "semantic_supported": (
                    eval_result.get("semantic_supported")
                    if isinstance(eval_result, dict) and eval_result.get("semantic_supported") is not None
                    else bundle.get("semantic_supported")
                ),
                "semantic_status": (
                    eval_result.get("semantic_status")
                    if isinstance(eval_result, dict) and eval_result.get("semantic_status")
                    else bundle.get("semantic_status")
                ),
                "semantic_source": (
                    eval_result.get("semantic_source")
                    if isinstance(eval_result, dict) and eval_result.get("semantic_source")
                    else bundle.get("semantic_source")
                ),
                "verification_rule_source": eval_result.get("verification_rule_source"),
                "verification_trust": eval_result.get("verification_trust"),
                "verification_independence": eval_result.get("verification_independence"),
                "verification_trust_reason": eval_result.get("verification_trust_reason"),
                "compiler_supported": compiler_contract.get("compiler_supported"),
                "compiler_strategy": compiler_contract.get("compiler_strategy"),
                "compiler_reason": compiler_contract.get("compiler_reason"),
                "compiler_family": compiler_contract.get("compiler_family"),
                "stack_scaffold_id": compiler_contract.get("stack_scaffold_id"),
                "stack_scaffold_version": compiler_contract.get("stack_scaffold_version"),
                "fragment_id": compiler_contract.get("fragment_id"),
                "compose_mode": compiler_contract.get("compose_mode"),
                "service_env": compiler_contract.get("service_env"),
                "request_identity": bundle.get("request_identity") or {},
                "request_ir": bundle.get("request_ir") or {},
                "name_resolution": bundle.get("name_resolution") or {},
                "generation_origin": (bundle.get("provenance") or {}).get("generation_origin"),
                "semantic_guided_selection_source": (bundle.get("provenance") or {}).get("semantic_guided_selection_source"),
                "semantic_guided_abstain_reason": (bundle.get("provenance") or {}).get("semantic_guided_abstain_reason"),
                "semantic_guided_ambiguous": (bundle.get("provenance") or {}).get("semantic_guided_ambiguous"),
                "llm_fixture_used": (bundle.get("provenance") or {}).get("llm_fixture_used"),
                "dynamicness_verdict": (bundle.get("dynamicness") or {}).get("verdict"),
                "dynamicness_reason": (bundle.get("dynamicness") or {}).get("reason"),
                "family_non_remote_available": (bundle.get("lower_bound") or {}).get("family_non_remote_available"),
                "effective_non_remote_available": (bundle.get("lower_bound") or {}).get("effective_non_remote_available"),
                "compiler_path_enabled": (bundle.get("lower_bound") or {}).get("compiler_path_enabled"),
                "executor_feasibility_status": (bundle.get("executor_feasibility") or {}).get("status"),
                "generalization_class": (bundle.get("generalization") or {}).get("class"),
                "counts_as_generalization": (bundle.get("generalization") or {}).get("counts_as_generalization"),
                "generalization_reason": (bundle.get("generalization") or {}).get("reason"),
                "generalization_confidence": (bundle.get("generalization") or {}).get("confidence"),
                "generalization_basis": (bundle.get("generalization") or {}).get("basis"),
                "open_world_class": (bundle.get("open_world") or {}).get("class"),
                "counts_as_open_world_generalization": (bundle.get("open_world") or {}).get("counts_as_generalization"),
                "open_world_reason": (bundle.get("open_world") or {}).get("reason"),
                "open_world_confidence": (bundle.get("open_world") or {}).get("confidence"),
                "open_world_basis": (bundle.get("open_world") or {}).get("basis"),
                "strict_open_world_class": (bundle.get("strict_open_world") or {}).get("class"),
                "counts_as_strict_open_world_generalization": (
                    (bundle.get("strict_open_world") or {}).get("counts_as_generalization")
                ),
                "strict_open_world_reason": (bundle.get("strict_open_world") or {}).get("reason"),
                "researcher_quality": (bundle.get("researcher") or {}).get("quality"),
                "researcher_shadow_mode": (bundle.get("researcher") or {}).get("shadow_mode_enabled"),
                "researcher_report_present": (bundle.get("researcher") or {}).get("report_present"),
                "runtime_recipe": bundle.get("runtime_recipe") or {},
                "runtime_graph": bundle.get("runtime_graph") or {},
                "evidence_graph": bundle.get("evidence_graph") or {},
                "dynamic_eval": bundle.get("dynamic_eval") or {},
                "artifact_quality": bundle.get("artifact_quality") or {},
                "stack_dependence": bundle.get("stack_dependence") or {},
                "family_dependence": bundle.get("family_dependence") or {},
                "intent_satisfaction": bundle.get("intent_satisfaction") or {},
                "name_only_outcome": bundle.get("name_only_outcome") or {},
                "completion_state": bundle.get("completion_state") or {},
                "failure_reason": (bundle.get("failure") or {}).get("reason"),
                "terminal_failure_class": (bundle.get("failure") or {}).get("terminal_failure_class"),
            }
        )
    return {
        "sid": sid,
        "overall_pass": reports.get("overall_pass"),
        "pipeline_result": manifest.get("pipeline_result"),
        "promotion_eligible": (manifest.get("promotion") or {}).get("eligible"),
        "promotion_reasons": (manifest.get("promotion") or {}).get("reasons") or [],
        "memory_promotion": manifest.get("memory_promotion") or {},
        "memory_promotion_eligible": manifest.get("memory_promotion_eligible"),
        "support_promotion": manifest.get("support_promotion") or {},
        "support_promotion_eligible": manifest.get("support_promotion_eligible"),
        "open_world_readiness_summary": manifest.get("open_world_readiness_summary") or {},
        "boundedness_summary": manifest.get("boundedness_summary") or {},
        "open_world_readiness": manifest.get("open_world_readiness") or {},
        "open_world_ready": manifest.get("open_world_ready"),
        "generation_summary": manifest.get("generation_summary") or {},
        "compiler_contract_summary": manifest.get("compiler_contract_summary") or {},
        "verification_summary": manifest.get("verification_summary") or {},
        "researcher_summary": manifest.get("researcher_summary") or {},
        "request_identity_summary": manifest.get("request_identity_summary") or {},
        "request_ir_summary": manifest.get("request_ir_summary") or {},
        "name_resolution_summary": manifest.get("name_resolution_summary") or {},
        "generalization_summary": manifest.get("generalization_summary") or {},
        "open_world_summary": manifest.get("open_world_summary") or {},
        "strict_open_world_summary": manifest.get("strict_open_world_summary") or {},
        "dynamic_eval_summary": manifest.get("dynamic_eval_summary") or {},
        "artifact_quality_summary": manifest.get("artifact_quality_summary") or {},
        "evidence_graph_summary": manifest.get("evidence_graph_summary") or {},
        "template_dependence_summary": manifest.get("template_dependence_summary") or {},
        "runtime_surface_summary": manifest.get("runtime_surface_summary") or {},
        "stack_dependence_summary": manifest.get("stack_dependence_summary") or {},
        "family_dependence_summary": manifest.get("family_dependence_summary") or {},
        "intent_satisfaction_summary": manifest.get("intent_satisfaction_summary") or {},
        "name_only_outcome_summary": manifest.get("name_only_outcome_summary") or {},
        "name_only_planning_summary": manifest.get("name_only_planning_summary") or {},
        "partial_progress_summary": manifest.get("partial_progress_summary") or {},
        "completion_summary": manifest.get("completion_summary") or {},
        "compiler_supported": manifest.get("compiler_supported"),
        "compiler_strategy": manifest.get("compiler_strategy"),
        "compiler_reason": manifest.get("compiler_reason"),
        "compiler_family": manifest.get("compiler_family"),
        "stack_scaffold_id": manifest.get("stack_scaffold_id"),
        "stack_scaffold_version": manifest.get("stack_scaffold_version"),
        "fragment_id": manifest.get("fragment_id"),
        "compose_mode": manifest.get("compose_mode"),
        "service_env": manifest.get("service_env"),
        "request_identity": manifest.get("request_identity") or {},
        "request_ir": manifest.get("request_ir") or {},
        "name_resolution": manifest.get("name_resolution") or {},
        "generation_origin": manifest.get("generation_origin"),
        "semantic_guided_selection_source": manifest.get("semantic_guided_selection_source"),
        "semantic_guided_abstain_reason": manifest.get("semantic_guided_abstain_reason"),
        "semantic_guided_ambiguous": manifest.get("semantic_guided_ambiguous"),
        "verification_rule_source": manifest.get("verification_rule_source"),
        "verification_trust": manifest.get("verification_trust"),
        "verification_independence": manifest.get("verification_independence"),
        "semantic_supported": manifest.get("semantic_supported"),
        "semantic_status": manifest.get("semantic_status"),
        "semantic_source": manifest.get("semantic_source"),
        "llm_fixture_used": (
            manifest.get("llm_fixture_used")
            if isinstance(manifest.get("llm_fixture_used"), bool)
            else (manifest.get("performance") or {}).get("llm_fixture_used")
        ),
        "provider_health_state": (manifest.get("performance") or {}).get("provider_health_state"),
        "total_duration_s": (manifest.get("performance") or {}).get("total_duration_s"),
        "performance_retry_count": (manifest.get("performance") or {}).get("retry_count"),
        "performance_by_stage": (manifest.get("performance") or {}).get("by_stage") or {},
        "dynamicness_verdict": manifest.get("dynamicness_verdict"),
        "dynamicness_reason": manifest.get("dynamicness_reason"),
        "family_non_remote_available": manifest.get("family_non_remote_available"),
        "effective_non_remote_available": manifest.get("effective_non_remote_available"),
        "compiler_path_enabled": manifest.get("compiler_path_enabled"),
        "executor_feasibility_status": manifest.get("executor_feasibility_status"),
        "generalization_class": manifest.get("generalization_class"),
        "counts_as_generalization": manifest.get("counts_as_generalization"),
        "generalization_reason": manifest.get("generalization_reason"),
        "generalization_confidence": manifest.get("generalization_confidence"),
        "generalization_basis": manifest.get("generalization_basis"),
        "open_world_class": manifest.get("open_world_class"),
        "counts_as_open_world_generalization": manifest.get("counts_as_open_world_generalization"),
        "open_world_reason": manifest.get("open_world_reason"),
        "open_world_confidence": manifest.get("open_world_confidence"),
        "open_world_basis": manifest.get("open_world_basis"),
        "strict_open_world_class": manifest.get("strict_open_world_class"),
        "counts_as_strict_open_world_generalization": manifest.get("counts_as_strict_open_world_generalization"),
        "strict_open_world_reason": manifest.get("strict_open_world_reason"),
        "runtime_recipe": manifest.get("runtime_recipe") or {},
        "runtime_recipe_hypothetical": ((manifest.get("runtime_recipe") or {}).get("hypothetical")),
        "runtime_graph": manifest.get("runtime_graph") or {},
        "runtime_graph_hypothetical": ((manifest.get("runtime_graph") or {}).get("hypothetical")),
        "evidence_graph": manifest.get("evidence_graph") or {},
        "dynamic_eval": manifest.get("dynamic_eval") or {},
        "artifact_quality": manifest.get("artifact_quality") or {},
        "stack_dependence": manifest.get("stack_dependence") or {},
        "family_dependence": manifest.get("family_dependence") or {},
        "intent_satisfaction": manifest.get("intent_satisfaction") or {},
        "name_only_outcome": manifest.get("name_only_outcome") or {},
        "name_only_decision": manifest.get("name_only_decision"),
        "name_only_next_required_step": manifest.get("name_only_next_required_step"),
        "name_only_planning_focus": manifest.get("name_only_planning_focus") or {},
        "name_only_primary_focus": manifest.get("name_only_primary_focus"),
        "completion_state": manifest.get("completion_state") or {},
        "stage_ceiling": manifest.get("stage_ceiling"),
        "fully_validated": manifest.get("fully_validated"),
        "researcher": manifest.get("researcher") or {},
        "pipeline_returncode": pipeline_returncode,
        "failure": manifest.get("failure") or {},
        "bundles": bundles,
        "reviewer": {
            "blocking_bundles": reviewer.get("blocking_bundles") or [],
            "issues_sample": reviewer.get("issues_sample") or [],
        },
        "manifest_path": str(manifest_path),
        "manifest_file": manifest_path.name,
        "reviewer_path": str(reviewer_path) if reviewer_path.exists() else None,
    }


def _bundle_index(summary: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}
    for bundle in summary.get("bundles", []):
        slug = (bundle.get("slug") or "").lower()
        if slug:
            index[slug] = bundle
        vuln = (bundle.get("vuln_id") or "").lower()
        if vuln and vuln not in index:
            index[vuln] = bundle
    return index


def _validate_partial_mapping(
    actual: Dict[str, Any],
    expected: Dict[str, Any],
    *,
    prefix: str,
    errors: List[str],
) -> None:
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        path = f"{prefix}.{key}"
        if isinstance(expected_value, dict):
            if not isinstance(actual_value, dict):
                errors.append(f"{path} expected {expected_value!r} but observed {actual_value!r}")
                continue
            _validate_partial_mapping(actual_value, expected_value, prefix=path, errors=errors)
            continue
        if actual_value != expected_value:
            errors.append(f"{path} expected {expected_value!r} but observed {actual_value!r}")


def _validate_expectations(summary: Dict[str, Any], expectations: Dict[str, Any]) -> None:
    errors: List[str] = []
    manifest_expect = expectations.get("manifest") or {}
    if "overall_pass" in manifest_expect:
        actual = bool(summary.get("overall_pass"))
        if actual != bool(manifest_expect["overall_pass"]):
            errors.append(
                f"overall_pass expected {manifest_expect['overall_pass']!r} but observed {summary.get('overall_pass')!r}"
            )
    if "pipeline_result" in manifest_expect:
        actual = str(summary.get("pipeline_result") or "")
        if actual != str(manifest_expect["pipeline_result"]):
            errors.append(
                f"pipeline_result expected {manifest_expect['pipeline_result']!r} but observed {summary.get('pipeline_result')!r}"
            )
    if "promotion_eligible" in manifest_expect:
        actual = bool(summary.get("promotion_eligible"))
        if actual != bool(manifest_expect["promotion_eligible"]):
            errors.append(
                f"promotion_eligible expected {manifest_expect['promotion_eligible']!r} but observed {summary.get('promotion_eligible')!r}"
            )
    if "manifest_file" in manifest_expect:
        actual = str(summary.get("manifest_file") or "")
        if actual != str(manifest_expect["manifest_file"]):
            errors.append(
                f"manifest_file expected {manifest_expect['manifest_file']!r} but observed {summary.get('manifest_file')!r}"
            )
    if "pipeline_returncode" in manifest_expect:
        actual = summary.get("pipeline_returncode")
        if actual != manifest_expect["pipeline_returncode"]:
            errors.append(
                f"pipeline_returncode expected {manifest_expect['pipeline_returncode']!r} but observed {summary.get('pipeline_returncode')!r}"
            )
    if "generation_origin" in manifest_expect:
        actual = str(summary.get("generation_origin") or "")
        if actual != str(manifest_expect["generation_origin"]):
            errors.append(
                f"generation_origin expected {manifest_expect['generation_origin']!r} but observed {summary.get('generation_origin')!r}"
            )
    if "llm_fixture_used" in manifest_expect:
        actual = bool(summary.get("llm_fixture_used"))
        if actual != bool(manifest_expect["llm_fixture_used"]):
            errors.append(
                f"llm_fixture_used expected {manifest_expect['llm_fixture_used']!r} but observed {summary.get('llm_fixture_used')!r}"
            )
    if "dynamicness_verdict" in manifest_expect:
        actual = str(summary.get("dynamicness_verdict") or "")
        if actual != str(manifest_expect["dynamicness_verdict"]):
            errors.append(
                f"dynamicness_verdict expected {manifest_expect['dynamicness_verdict']!r} but observed {summary.get('dynamicness_verdict')!r}"
            )
    if "verification_rule_source" in manifest_expect:
        actual = str(summary.get("verification_rule_source") or "")
        if actual != str(manifest_expect["verification_rule_source"]):
            errors.append(
                f"verification_rule_source expected {manifest_expect['verification_rule_source']!r} but observed {summary.get('verification_rule_source')!r}"
            )
    if "verification_trust" in manifest_expect:
        actual = str(summary.get("verification_trust") or "")
        if actual != str(manifest_expect["verification_trust"]):
            errors.append(
                f"verification_trust expected {manifest_expect['verification_trust']!r} but observed {summary.get('verification_trust')!r}"
            )
    if "verification_independence" in manifest_expect:
        actual = str(summary.get("verification_independence") or "")
        if actual != str(manifest_expect["verification_independence"]):
            errors.append(
                "verification_independence expected "
                f"{manifest_expect['verification_independence']!r} but observed {summary.get('verification_independence')!r}"
            )
    if "semantic_supported" in manifest_expect:
        actual = summary.get("semantic_supported")
        if actual != manifest_expect["semantic_supported"]:
            errors.append(
                f"semantic_supported expected {manifest_expect['semantic_supported']!r} but observed {summary.get('semantic_supported')!r}"
            )
    for key in ("semantic_status", "semantic_source"):
        if key in manifest_expect:
            actual = str(summary.get(key) or "")
            if actual != str(manifest_expect[key]):
                errors.append(f"{key} expected {manifest_expect[key]!r} but observed {summary.get(key)!r}")
    if "provider_health_state" in manifest_expect:
        actual = str(summary.get("provider_health_state") or "")
        if actual != str(manifest_expect["provider_health_state"]):
            errors.append(
                f"provider_health_state expected {manifest_expect['provider_health_state']!r} but observed {summary.get('provider_health_state')!r}"
            )
    for key in ("family_non_remote_available", "effective_non_remote_available", "compiler_path_enabled"):
        if key in manifest_expect and bool(summary.get(key)) != bool(manifest_expect[key]):
            errors.append(f"{key} expected {manifest_expect[key]!r} but observed {summary.get(key)!r}")
    if "fully_validated" in manifest_expect and bool(summary.get("fully_validated")) != bool(manifest_expect["fully_validated"]):
        errors.append(
            f"fully_validated expected {manifest_expect['fully_validated']!r} but observed {summary.get('fully_validated')!r}"
        )
    if "executor_feasibility_status" in manifest_expect:
        actual = str(summary.get("executor_feasibility_status") or "")
        if actual != str(manifest_expect["executor_feasibility_status"]):
            errors.append(
                f"executor_feasibility_status expected {manifest_expect['executor_feasibility_status']!r} but observed {summary.get('executor_feasibility_status')!r}"
            )
    if "stage_ceiling" in manifest_expect:
        actual = str(summary.get("stage_ceiling") or "")
        if actual != str(manifest_expect["stage_ceiling"]):
            errors.append(
                f"stage_ceiling expected {manifest_expect['stage_ceiling']!r} but observed {summary.get('stage_ceiling')!r}"
            )
    for key in ("name_only_decision", "name_only_next_required_step"):
        if key in manifest_expect:
            actual = str(summary.get(key) or "")
            if actual != str(manifest_expect[key]):
                errors.append(f"{key} expected {manifest_expect[key]!r} but observed {summary.get(key)!r}")
    if "service_env" in manifest_expect:
        actual = summary.get("service_env") or {}
        if actual != manifest_expect["service_env"]:
            errors.append(
                f"service_env expected {manifest_expect['service_env']!r} but observed {summary.get('service_env')!r}"
            )
    name_resolution_expect = manifest_expect.get("name_resolution")
    if isinstance(name_resolution_expect, dict):
        actual = summary.get("name_resolution") or {}
        for key, expected in name_resolution_expect.items():
            if actual.get(key) != expected:
                errors.append(
                    f"name_resolution.{key} expected {expected!r} but observed {actual.get(key)!r}"
                )
    for key in (
        "request_ir",
        "runtime_recipe",
        "runtime_graph",
        "evidence_graph",
        "dynamic_eval",
        "artifact_quality",
        "stack_dependence",
        "family_dependence",
        "intent_satisfaction",
        "name_only_outcome",
        "completion_state",
    ):
        expected_payload = manifest_expect.get(key)
        if isinstance(expected_payload, dict):
            _validate_partial_mapping(
                summary.get(key) or {},
                expected_payload,
                prefix=key,
                errors=errors,
            )
    for key in ("compiler_family", "stack_scaffold_id", "stack_scaffold_version", "fragment_id", "compose_mode"):
        if key not in manifest_expect:
            continue
        actual = str(summary.get(key) or "")
        if actual != str(manifest_expect[key]):
            errors.append(f"{key} expected {manifest_expect[key]!r} but observed {summary.get(key)!r}")
    if "generalization_class" in manifest_expect:
        actual = str(summary.get("generalization_class") or "")
        if actual != str(manifest_expect["generalization_class"]):
            errors.append(
                f"generalization_class expected {manifest_expect['generalization_class']!r} but observed {summary.get('generalization_class')!r}"
            )
    if "counts_as_generalization" in manifest_expect:
        actual = summary.get("counts_as_generalization")
        if actual is not manifest_expect["counts_as_generalization"]:
            errors.append(
                "counts_as_generalization expected "
                f"{manifest_expect['counts_as_generalization']!r} but observed {summary.get('counts_as_generalization')!r}"
            )
    for key in ("generalization_confidence", "generalization_basis"):
        if key in manifest_expect:
            actual = str(summary.get(key) or "")
            if actual != str(manifest_expect[key]):
                errors.append(f"{key} expected {manifest_expect[key]!r} but observed {summary.get(key)!r}")
    generation_summary_expect = manifest_expect.get("generation_summary")
    if isinstance(generation_summary_expect, dict):
        _validate_partial_mapping(
            summary.get("generation_summary") or {},
            generation_summary_expect,
            prefix="generation_summary",
            errors=errors,
        )
    verification_summary_expect = manifest_expect.get("verification_summary")
    if isinstance(verification_summary_expect, dict):
        _validate_partial_mapping(
            summary.get("verification_summary") or {},
            verification_summary_expect,
            prefix="verification_summary",
            errors=errors,
        )
    for key in (
        "dynamic_eval_summary",
        "artifact_quality_summary",
        "evidence_graph_summary",
        "template_dependence_summary",
        "intent_satisfaction_summary",
        "name_only_outcome_summary",
        "completion_summary",
    ):
        expected_payload = manifest_expect.get(key)
        if isinstance(expected_payload, dict):
            _validate_partial_mapping(
                summary.get(key) or {},
                expected_payload,
                prefix=key,
                errors=errors,
            )
    partial_progress_expect = manifest_expect.get("partial_progress_summary")
    if isinstance(partial_progress_expect, dict):
        _validate_partial_mapping(
            summary.get("partial_progress_summary") or {},
            partial_progress_expect,
            prefix="partial_progress_summary",
            errors=errors,
        )
    failure_expect = manifest_expect.get("failure")
    if isinstance(failure_expect, dict):
        _validate_partial_mapping(
            summary.get("failure") or {},
            failure_expect,
            prefix="failure",
            errors=errors,
        )
    bundle_index = _bundle_index(summary)
    for entry in expectations.get("evals", []):
        key = (entry.get("slug") or entry.get("vuln_id") or "").lower()
        if not key or key not in bundle_index:
            errors.append(f"missing bundle entry for expectation: {entry}")
            continue
        bundle = bundle_index[key]
        if "verify_pass" in entry and bool(bundle.get("verify_pass")) != bool(entry["verify_pass"]):
            errors.append(
                f"bundle {bundle['slug']}: verify_pass expected {entry['verify_pass']} but was {bundle.get('verify_pass')}"
            )
        if "run_passed" in entry and bool(bundle.get("run_passed")) != bool(entry["run_passed"]):
            errors.append(
                f"bundle {bundle['slug']}: run_passed expected {entry['run_passed']} but was {bundle.get('run_passed')}"
            )
        if "exit_code" in entry and bundle.get("exit_code") != entry["exit_code"]:
            errors.append(
                f"bundle {bundle['slug']}: exit_code expected {entry['exit_code']} but was {bundle.get('exit_code')}"
            )
        if "promotion_eligible" in entry and bool(bundle.get("promotion_eligible")) != bool(entry["promotion_eligible"]):
            errors.append(
                f"bundle {bundle['slug']}: promotion_eligible expected {entry['promotion_eligible']} but was {bundle.get('promotion_eligible')}"
            )
        if "compiler_supported" in entry and bundle.get("compiler_supported") != entry["compiler_supported"]:
            errors.append(
                f"bundle {bundle['slug']}: compiler_supported expected {entry['compiler_supported']!r} but was {bundle.get('compiler_supported')!r}"
            )
        if "compiler_strategy" in entry and str(bundle.get("compiler_strategy") or "") != str(entry["compiler_strategy"]):
            errors.append(
                f"bundle {bundle['slug']}: compiler_strategy expected {entry['compiler_strategy']!r} but was {bundle.get('compiler_strategy')!r}"
            )
        if "generation_origin" in entry and str(bundle.get("generation_origin") or "") != str(entry["generation_origin"]):
            errors.append(
                f"bundle {bundle['slug']}: generation_origin expected {entry['generation_origin']!r} but was {bundle.get('generation_origin')!r}"
            )
        if "llm_fixture_used" in entry and bool(bundle.get("llm_fixture_used")) != bool(entry["llm_fixture_used"]):
            errors.append(
                f"bundle {bundle['slug']}: llm_fixture_used expected {entry['llm_fixture_used']!r} but was {bundle.get('llm_fixture_used')!r}"
            )
        if "dynamicness_verdict" in entry and str(bundle.get("dynamicness_verdict") or "") != str(entry["dynamicness_verdict"]):
            errors.append(
                f"bundle {bundle['slug']}: dynamicness_verdict expected {entry['dynamicness_verdict']!r} but was {bundle.get('dynamicness_verdict')!r}"
            )
        for key in ("family_non_remote_available", "effective_non_remote_available", "compiler_path_enabled"):
            if key in entry and bool(bundle.get(key)) != bool(entry[key]):
                errors.append(
                    f"bundle {bundle['slug']}: {key} expected {entry[key]!r} but was {bundle.get(key)!r}"
                )
        if "fully_validated" in entry and bool(bundle.get("completion_state", {}).get("fully_validated")) != bool(entry["fully_validated"]):
            errors.append(
                f"bundle {bundle['slug']}: fully_validated expected {entry['fully_validated']!r} but was {bundle.get('completion_state', {}).get('fully_validated')!r}"
            )
        if "executor_feasibility_status" in entry and str(bundle.get("executor_feasibility_status") or "") != str(entry["executor_feasibility_status"]):
            errors.append(
                f"bundle {bundle['slug']}: executor_feasibility_status expected {entry['executor_feasibility_status']!r} but was {bundle.get('executor_feasibility_status')!r}"
            )
        if "stage_ceiling" in entry and str(bundle.get("completion_state", {}).get("stage_ceiling") or "") != str(entry["stage_ceiling"]):
            errors.append(
                f"bundle {bundle['slug']}: stage_ceiling expected {entry['stage_ceiling']!r} but was {bundle.get('completion_state', {}).get('stage_ceiling')!r}"
            )
        if "name_only_decision" in entry and str(bundle.get("name_only_outcome", {}).get("decision") or "") != str(entry["name_only_decision"]):
            errors.append(
                f"bundle {bundle['slug']}: name_only_decision expected {entry['name_only_decision']!r} but was {bundle.get('name_only_outcome', {}).get('decision')!r}"
            )
        if "name_only_next_required_step" in entry and str(bundle.get("name_only_outcome", {}).get("next_required_step") or "") != str(entry["name_only_next_required_step"]):
            errors.append(
                f"bundle {bundle['slug']}: name_only_next_required_step expected {entry['name_only_next_required_step']!r} but was {bundle.get('name_only_outcome', {}).get('next_required_step')!r}"
            )
        if "service_env" in entry and (bundle.get("service_env") or {}) != entry["service_env"]:
            errors.append(
                f"bundle {bundle['slug']}: service_env expected {entry['service_env']!r} but was {bundle.get('service_env')!r}"
            )
        for key in ("compiler_family", "stack_scaffold_id", "stack_scaffold_version", "fragment_id", "compose_mode"):
            if key not in entry:
                continue
            if str(bundle.get(key) or "") != str(entry[key]):
                errors.append(
                    f"bundle {bundle['slug']}: {key} expected {entry[key]!r} but was {bundle.get(key)!r}"
                )
        if "semantic_supported" in entry and bundle.get("semantic_supported") != entry["semantic_supported"]:
            errors.append(
                f"bundle {bundle['slug']}: semantic_supported expected {entry['semantic_supported']!r} but was {bundle.get('semantic_supported')!r}"
            )
        if "semantic_status" in entry and str(bundle.get("semantic_status")) != str(entry["semantic_status"]):
            errors.append(
                f"bundle {bundle['slug']}: semantic_status expected {entry['semantic_status']!r} but was {bundle.get('semantic_status')!r}"
            )
        if "semantic_source" in entry and str(bundle.get("semantic_source") or "") != str(entry["semantic_source"]):
            errors.append(
                f"bundle {bundle['slug']}: semantic_source expected {entry['semantic_source']!r} but was {bundle.get('semantic_source')!r}"
            )
        for key in (
            "request_ir",
            "runtime_recipe",
            "runtime_graph",
            "evidence_graph",
            "dynamic_eval",
            "artifact_quality",
            "stack_dependence",
            "family_dependence",
            "intent_satisfaction",
            "name_only_outcome",
            "completion_state",
        ):
            expected_payload = entry.get(key)
            if isinstance(expected_payload, dict):
                _validate_partial_mapping(
                    bundle.get(key) or {},
                    expected_payload,
                    prefix=f"bundle[{bundle['slug']}].{key}",
                    errors=errors,
                )
        if "verification_rule_source" in entry and str(bundle.get("verification_rule_source") or "") != str(entry["verification_rule_source"]):
            errors.append(
                f"bundle {bundle['slug']}: verification_rule_source expected {entry['verification_rule_source']!r} but was {bundle.get('verification_rule_source')!r}"
            )
        if "verification_trust" in entry and str(bundle.get("verification_trust") or "") != str(entry["verification_trust"]):
            errors.append(
                f"bundle {bundle['slug']}: verification_trust expected {entry['verification_trust']!r} but was {bundle.get('verification_trust')!r}"
            )
        if "verification_independence" in entry and str(bundle.get("verification_independence") or "") != str(entry["verification_independence"]):
            errors.append(
                f"bundle {bundle['slug']}: verification_independence expected {entry['verification_independence']!r} but was {bundle.get('verification_independence')!r}"
            )
        if "generalization_class" in entry and str(bundle.get("generalization_class") or "") != str(entry["generalization_class"]):
            errors.append(
                f"bundle {bundle['slug']}: generalization_class expected {entry['generalization_class']!r} but was {bundle.get('generalization_class')!r}"
            )
        if "counts_as_generalization" in entry and bundle.get("counts_as_generalization") is not entry["counts_as_generalization"]:
            errors.append(
                f"bundle {bundle['slug']}: counts_as_generalization expected {entry['counts_as_generalization']!r} but was {bundle.get('counts_as_generalization')!r}"
            )
        for key in ("generalization_confidence", "generalization_basis"):
            if key in entry and str(bundle.get(key) or "") != str(entry[key]):
                errors.append(
                    f"bundle {bundle['slug']}: {key} expected {entry[key]!r} but was {bundle.get(key)!r}"
                )
        if "terminal_failure_class" in entry and str(bundle.get("terminal_failure_class") or "") != str(entry["terminal_failure_class"]):
            errors.append(
                f"bundle {bundle['slug']}: terminal_failure_class expected {entry['terminal_failure_class']!r} but was {bundle.get('terminal_failure_class')!r}"
            )
        failure_reason = str(bundle.get("failure_reason") or "")
        for token in entry.get("failure_reason_contains", []):
            if token not in failure_reason:
                errors.append(f"bundle {bundle['slug']}: failure_reason missing substring '{token}'")
        evidence = bundle.get("evidence") or ""
        for token in entry.get("evidence_contains", []):
            if token not in evidence:
                errors.append(f"bundle {bundle['slug']}: evidence missing substring '{token}'")
        compiler_reason = str(bundle.get("compiler_reason") or "")
        for token in entry.get("compiler_reason_contains", []):
            if token not in compiler_reason:
                errors.append(f"bundle {bundle['slug']}: compiler_reason missing substring '{token}'")
    reviewer_expect = expectations.get("reviewer") or {}
    reviewer = summary.get("reviewer") or {}
    if "blocking_bundles" in reviewer_expect:
        expected = sorted(reviewer_expect.get("blocking_bundles") or [])
        actual = sorted(reviewer.get("blocking_bundles") or [])
        if actual != expected:
            errors.append(f"blocking bundles mismatch. expected={expected}, actual={actual}")
    snippets = reviewer_expect.get("issue_snippets") or []
    if snippets:
        issues = reviewer.get("issues_sample") or []
        texts = [issue.get("issue", "") for issue in issues]
        for snippet in snippets:
            if not any(snippet in text for text in texts):
                errors.append(f"reviewer issues missing snippet '{snippet}'")
    if errors:
        raise CaseError("; ".join(errors))


def _write_summary(summary: Dict[str, Any], requirement: Dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    if yaml is not None:
        (output_dir / "requirement.resolved.yml").write_text(
            yaml.safe_dump(requirement, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
    return summary_path


def _snapshot_outputs(sid: str, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for root_name in ("metadata", "artifacts"):
        source = REPO_ROOT / root_name / sid
        if not source.exists():
            continue
        target = destination / root_name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target, dirs_exist_ok=True)


def execute_case(case_dir: Path, *, requirement_path: Optional[Path], expectations_path: Optional[Path], mode: str, snapshot: bool, output_dir: Optional[Path]) -> Dict[str, Any]:
    case_spec = _load_case_spec(case_dir, requirement_path)
    plan = _write_plan(case_spec.requirement, multi_vuln_opt_in=bool(case_spec.options.get("multi_vuln_opt_in", False)))
    sid = plan["sid"]
    env = os.environ.copy()
    env["SID"] = sid
    custom_env = case_spec.options.get("env") or {}
    for key, value in custom_env.items():
        env[str(key)] = str(value)
    _materialize_runtime_assets(sid, case_spec.runtime_assets)
    expectations_data: Optional[Dict[str, Any]] = None
    resolved_expectations_path = expectations_path or (case_dir / "expectations.json")
    if resolved_expectations_path and resolved_expectations_path.exists():
        expectations_data = json.loads(resolved_expectations_path.read_text(encoding="utf-8"))
    if _case_requires_docker(expectations_data):
        _ensure_docker_ready(env)
    proc = _execute_pipeline(sid, mode, env)
    summary = _load_manifest_summary(sid, pipeline_returncode=proc.returncode)
    destination = output_dir or (case_dir / "outputs" / sid)
    summary_path = _write_summary(summary, plan.get("requirement", case_spec.requirement), destination)
    if snapshot:
        _snapshot_outputs(sid, destination)
    if expectations_data is not None:
        _validate_expectations(summary, expectations_data)
    elif proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        raise CaseError(
            f"pipeline exited with non-zero status {proc.returncode} without expectations to validate it"
            + (f"\nSTDERR:\n{stderr}" if stderr else "")
        )
    if expectations_data and proc.returncode != 0 and summary.get("manifest_file") not in {"failure_manifest.json", "manifest.json"}:
        stderr = (proc.stderr or "").strip()
        raise CaseError(
            f"pipeline exited with non-zero status {proc.returncode} and no usable manifest was written"
            + (f"\nSTDERR:\n{stderr}" if stderr else "")
        )
    print(f"[E2E] Summary written to {summary_path}")
    if expectations_data:
        print(f"[E2E] Expectations satisfied for {case_spec.name}")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a single E2E case")
    parser.add_argument("--case", type=Path, required=True, help="Path to the case directory")
    parser.add_argument("--mode", default="deterministic", help="LLM decoding mode (deterministic|diverse)")
    parser.add_argument("--requirement", type=Path, help="Override requirement YAML path")
    parser.add_argument("--expectations", type=Path, help="Override expectations JSON path")
    parser.add_argument("--output-dir", type=Path, help="Directory to store summary/snapshots")
    parser.add_argument("--no-snapshot", action="store_true", help="Skip copying metadata/artifacts to the outputs directory")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    case_dir = args.case.resolve()
    if not case_dir.exists():
        raise SystemExit(f"case directory not found: {case_dir}")
    snapshot = not args.no_snapshot
    try:
        execute_case(
            case_dir,
            requirement_path=args.requirement.resolve() if args.requirement else None,
            expectations_path=args.expectations.resolve() if args.expectations else None,
            mode=args.mode,
            snapshot=snapshot,
            output_dir=args.output_dir.resolve() if args.output_dir else None,
        )
    except CaseError as exc:
        print(f"[E2E] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
