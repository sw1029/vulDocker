"""Repeatability gate runner for E2E cases."""
from __future__ import annotations

import argparse
import inspect
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

try:  # pragma: no cover - optional dependency mirrors run_case.py
    import yaml
except Exception:  # pragma: no cover
    yaml = None

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.e2e.case_matrix import case_matrix_axes
from tests.e2e.matrix_report import write_matrix_report
from tests.e2e.run_case import (
    _case_requires_docker,
    _ensure_docker_ready,
    _execution_salt,
    _execute_pipeline,
    _load_case_spec,
    _load_manifest_summary,
    _materialize_runtime_assets,
    _snapshot_outputs,
    _validate_expectations,
    _write_plan,
)
from orchestrator.support_extract import write_support_candidate

PERFORMANCE_CACHE_FIELDS = (
    "search_cache_hit_count",
    "search_cache_miss_count",
    "search_cache_reuse_ratio",
    "search_planned_query_count",
    "search_executed_query_count",
    "search_early_stop_triggered",
)

VERDICT_AUTHORITY_FIELDS = (
    "run_passed",
    "verify_pass",
    "stage_ceiling",
    "terminal_failure_class",
    "oracle_execution_parity",
    "oracle_execution_attempted",
)


def _optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _generation_positive_bucket(attempt: Dict[str, Any]) -> str | None:
    path_class = str(attempt.get("generation_path_class") or "").strip().lower()
    generation_origin = str(attempt.get("generation_origin") or "").strip().lower()
    provider_health_state = str(attempt.get("provider_health_state") or "").strip().lower()
    provider_succeeded = _optional_bool(attempt.get("generation_provider_succeeded"))
    stub_fallback = _optional_bool(attempt.get("generation_stub_fallback"))
    fixture_used = _optional_bool(attempt.get("generation_fixture_used"))

    if fixture_used is True or path_class == "fixture":
        return "fixture_backed_positive"
    if provider_succeeded is True or path_class == "live":
        return "live_positive"
    if (
        path_class in {"degraded", "stub"}
        or stub_fallback is True
        or generation_origin == "deterministic_fallback"
        or provider_health_state == "llm_degraded"
    ):
        return "degraded_fallback_positive"
    if generation_origin:
        return "non_llm_positive"
    return None


def _generation_non_live_reason(attempt: Dict[str, Any]) -> str | None:
    return str(attempt.get("generation_non_live_reason") or "").strip().lower() or None


def _safe_read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _load_expectations(path: Optional[Path]) -> Dict[str, Any]:
    if path is None or not path.exists():
        return {}
    data = _safe_read_json(path)
    return data if isinstance(data, dict) else {}


def _load_latest_generator_failure(metadata_root: Path) -> Dict[str, Any]:
    candidate_paths = [metadata_root / "generator_failures.jsonl"]
    bundles_dir = metadata_root / "bundles"
    if bundles_dir.exists():
        candidate_paths.extend(sorted(bundles_dir.glob("*/generator_failures.jsonl")))
    latest: Dict[str, Any] = {}
    latest_ts = ""
    for path in candidate_paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            timestamp = str(payload.get("timestamp") or "")
            if timestamp >= latest_ts:
                latest = dict(payload)
                latest_ts = timestamp
                latest["_failure_path"] = str(path)
    return latest


def _load_loop_tail(metadata_root: Path) -> Dict[str, Any]:
    payload = _safe_read_json(metadata_root / "loop_state.json")
    history = payload.get("history")
    if not isinstance(history, list) or not history:
        return {}
    tail = history[-1]
    return tail if isinstance(tail, dict) else {}


def _infer_failure_stage(error: str, loop_tail: Dict[str, Any], latest_failure: Dict[str, Any]) -> str:
    stage = str(latest_failure.get("stage") or "").strip()
    if stage:
        return stage
    if isinstance(loop_tail, dict) and loop_tail.get("success") is False:
        stage = str(loop_tail.get("stage") or "").strip()
        if stage:
            return stage
    lowered = str(error or "").strip().lower()
    markers = [
        ("agents/researcher/main.py", "RESEARCH"),
        ("agents/generator/main.py", "GENERATOR"),
        ("executor/runtime/docker_local.py", "EXECUTOR"),
        ("evals/poc_verifier/main.py", "VERIFY"),
        ("agents/reviewer/main.py", "REVIEW"),
        ("orchestrator/pack.py", "PACK"),
    ]
    for marker, inferred in markers:
        if marker in lowered:
            return inferred
    return ""


def summarize_repeat_attempt(
    *,
    attempt: int,
    case_name: str = "",
    matrix_axes: Optional[Dict[str, str]] = None,
    sid: str,
    summary: Dict[str, Any],
    error: str,
    latest_failure: Dict[str, Any],
    loop_tail: Dict[str, Any],
    attempt_dir: Path,
) -> Dict[str, Any]:
    success = not error
    bundles = summary.get("bundles") if isinstance(summary.get("bundles"), list) else []
    reviewer = summary.get("reviewer") if isinstance(summary.get("reviewer"), dict) else {}
    guard_mismatches: List[Dict[str, Any]] = []
    for bundle in bundles:
        if not isinstance(bundle, dict):
            continue
        evidence = str(bundle.get("evidence") or "")
        if "guard mismatch:" not in evidence.lower():
            continue
        guard_mismatches.append(
            {
                "slug": bundle.get("slug"),
                "vuln_id": bundle.get("vuln_id"),
                "evidence": evidence,
            }
        )
    if not guard_mismatches:
        violations = latest_failure.get("guard_violations")
        if isinstance(violations, list) and violations:
            guard_mismatches.append(
                {
                    "slug": latest_failure.get("slug"),
                    "vuln_id": latest_failure.get("vuln_id"),
                    "evidence": "; ".join(str(item) for item in violations if item),
                }
            )

    has_failure_signal = bool(error) or bool(latest_failure)
    failure_stage = _infer_failure_stage(error, loop_tail, latest_failure) if has_failure_signal else ""
    failure_fingerprint = str(latest_failure.get("failure_fingerprint") or "").strip() if has_failure_signal else ""
    guard_error_code = str(latest_failure.get("guard_error_code") or "").strip() if has_failure_signal else ""
    summary_matrix_axes = summary.get("matrix_axes") if isinstance(summary.get("matrix_axes"), dict) else {}
    default_matrix_axes = matrix_axes if isinstance(matrix_axes, dict) else {}
    verdict_authority = summary.get("verdict_authority") if isinstance(summary.get("verdict_authority"), dict) else {}
    authority_fields = verdict_authority.get("fields") if isinstance(verdict_authority.get("fields"), dict) else {}
    attempt_report = {
        "case_name": str(summary.get("case_name") or "").strip() or case_name,
        "matrix_axes": {
            str(key): str(value)
            for key, value in (summary_matrix_axes or default_matrix_axes).items()
            if isinstance(key, str) and str(key).strip() and isinstance(value, str) and str(value).strip()
        },
        "execution_salt": str(summary.get("execution_salt") or "").strip() or None,
        "artifact_quality_band": str(
            ((summary.get("artifact_quality") or {}) if isinstance(summary.get("artifact_quality"), dict) else {}).get("band")
            or ""
        ).strip().lower()
        or None,
        "artifact_quality_qualitative_tier": str(
            ((summary.get("artifact_quality") or {}) if isinstance(summary.get("artifact_quality"), dict) else {}).get(
                "qualitative_tier"
            )
            or ""
        ).strip()
        or None,
        "oracle_execution_parity": str(
            ((summary.get("artifact_quality") or {}) if isinstance(summary.get("artifact_quality"), dict) else {}).get(
                "oracle_execution_parity"
            )
            or ""
        ).strip().lower()
        or None,
        "verdict_authority_mode": str(verdict_authority.get("mode") or "").strip() or None,
        "verdict_projection_modes": {
            field: str((authority_fields.get(field) or {}).get("projection_mode") or "").strip()
            for field in VERDICT_AUTHORITY_FIELDS
            if str((authority_fields.get(field) or {}).get("projection_mode") or "").strip()
        },
        "generation_origin": str(summary.get("generation_origin") or "").strip().lower() or None,
        "provider_health_state": str(summary.get("provider_health_state") or "").strip().lower() or None,
        "generation_path_class": str(summary.get("generation_path_class") or "").strip().lower() or None,
        "generation_provider_attempted": _optional_bool(summary.get("generation_provider_attempted")),
        "generation_provider_succeeded": _optional_bool(summary.get("generation_provider_succeeded")),
        "generation_stub_fallback": _optional_bool(summary.get("generation_stub_fallback")),
        "generation_fixture_used": _optional_bool(summary.get("generation_fixture_used")),
        "generation_non_live_reason": (
            str(summary.get("generation_non_live_reason") or "").strip().lower()
            or str(
                ((summary.get("generation_materialization") or {}) if isinstance(summary.get("generation_materialization"), dict) else {}).get(
                    "non_live_reason"
                )
                or ""
            ).strip().lower()
            or None
        ),
    }
    for field in PERFORMANCE_CACHE_FIELDS:
        value = summary.get(field)
        if field == "search_cache_reuse_ratio":
            attempt_report[field] = float(value or 0.0)
        elif field == "search_early_stop_triggered":
            attempt_report[field] = bool(value)
        else:
            attempt_report[field] = int(value or 0)
    return {
        "attempt": attempt,
        "sid": sid,
        "success": success,
        "overall_pass": summary.get("overall_pass"),
        "failure_stage": failure_stage or None,
        "failure_fingerprint": failure_fingerprint or None,
        "guard_error_code": guard_error_code or None,
        "blocking_bundles": reviewer.get("blocking_bundles") or [],
        "guard_mismatches": guard_mismatches,
        "bundles": bundles,
        "latest_failure": latest_failure or None,
        "loop_tail": loop_tail or None,
        "error": error or None,
        "output_dir": str(attempt_dir),
        "summary_path": str(attempt_dir / "summary.json") if (attempt_dir / "summary.json").exists() else None,
        **attempt_report,
    }


def _write_plan_supports_sid_salt(writer: Callable[..., Dict[str, Any]]) -> bool:
    try:
        signature = inspect.signature(writer)
    except (TypeError, ValueError):
        return False
    parameter = signature.parameters.get("sid_salt")
    if parameter is None:
        return False
    return parameter.kind in (
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.KEYWORD_ONLY,
    )


def _write_plan_compat(
    requirement: Dict[str, Any],
    *,
    multi_vuln_opt_in: bool,
    sid_salt: str,
) -> Dict[str, Any]:
    if _write_plan_supports_sid_salt(_write_plan):
        return _write_plan(
            requirement,
            multi_vuln_opt_in=multi_vuln_opt_in,
            sid_salt=sid_salt,
        )
    return _write_plan(
        requirement,
        multi_vuln_opt_in=multi_vuln_opt_in,
    )


def _fallback_matrix_report(
    output_path: Path,
    *,
    case_name: str,
    reason: str,
) -> Dict[str, Any]:
    report = {
        "schema_version": "matrix_report@0.1",
        "case_count": 0,
        "covered_cases": [],
        "failed_cases": [],
        "repeatability_failures": [],
        "fully_green": False,
        "matrix_unavailable_reason": reason,
        "requested_case_name": case_name,
        "by_axis": {},
        "quality_observations": {
            "by_band": {},
            "by_qualitative_tier": {},
            "oracle_high_nonhigh_band_cases": [],
        },
        "authority_observations": {
            "by_verdict_authority_mode": {},
            "by_run_passed_projection_mode": {},
            "by_verify_pass_projection_mode": {},
            "by_stage_ceiling_projection_mode": {},
            "by_terminal_failure_class_projection_mode": {},
            "by_oracle_execution_parity_projection_mode": {},
        },
        "measured_gate_observations": {
            "ready_cases": [],
            "not_ready_cases": [],
            "by_blocker": {},
        },
        "generation_path_observations": {
            "by_primary_path_class": {},
            "by_primary_positive_bucket": {},
            "path_class_consistent_cases": [],
            "path_class_inconsistent_cases": [],
            "positive_bucket_consistent_cases": [],
            "positive_bucket_inconsistent_cases": [],
            "live_positive_ready_cases": [],
            "live_positive_blocked_cases": [],
            "by_generation_gate_blocker": {},
        },
        "cache_observations": {
            "cache_reuse_observed_cases": [],
            "cache_reuse_consistent_cases": [],
            "executed_query_reduction_observed_cases": [],
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def aggregate_repeat_results(case_name: str, attempts: List[Dict[str, Any]]) -> Dict[str, Any]:
    fingerprint_counts = Counter(
        str(item.get("failure_fingerprint") or "").strip()
        for item in attempts
        if str(item.get("failure_fingerprint") or "").strip()
    )
    stage_counts = Counter(
        str(item.get("failure_stage") or "").strip()
        for item in attempts
        if str(item.get("failure_stage") or "").strip()
    )
    guard_error_counts = Counter(
        str(item.get("guard_error_code") or "").strip()
        for item in attempts
        if str(item.get("guard_error_code") or "").strip()
    )
    first_success_attempt = next((item for item in attempts if item.get("success")), None)
    later_success_attempts = [
        item
        for item in attempts
        if item.get("success")
        and first_success_attempt is not None
        and int(item.get("attempt") or 0) > int(first_success_attempt.get("attempt") or 0)
    ]
    baseline_executed_query_count = (
        int(first_success_attempt.get("search_executed_query_count") or 0)
        if isinstance(first_success_attempt, dict)
        else 0
    )
    cache_reuse_observed = any(int(item.get("search_cache_hit_count") or 0) > 0 for item in later_success_attempts)
    cache_reuse_consistent = bool(later_success_attempts) and all(
        int(item.get("search_cache_hit_count") or 0) > 0 for item in later_success_attempts
    )
    executed_query_reduction_observed = bool(later_success_attempts) and any(
        int(item.get("search_executed_query_count") or 0) < baseline_executed_query_count
        for item in later_success_attempts
    )
    successful_attempts = [item for item in attempts if item.get("success")]
    observed_artifact_quality_bands = sorted(
        {
            str(item.get("artifact_quality_band") or "").strip().lower()
            for item in successful_attempts
            if str(item.get("artifact_quality_band") or "").strip()
        }
    )
    observed_qualitative_tiers = sorted(
        {
            str(item.get("artifact_quality_qualitative_tier") or "").strip()
            for item in successful_attempts
            if str(item.get("artifact_quality_qualitative_tier") or "").strip()
        }
    )
    observed_oracle_execution_parities = sorted(
        {
            str(item.get("oracle_execution_parity") or "").strip().lower()
            for item in successful_attempts
            if str(item.get("oracle_execution_parity") or "").strip()
        }
    )
    observed_verdict_authority_modes = sorted(
        {
            str(item.get("verdict_authority_mode") or "").strip()
            for item in successful_attempts
            if str(item.get("verdict_authority_mode") or "").strip()
        }
    )
    observed_verdict_projection_modes: Dict[str, List[str]] = {}
    for field in VERDICT_AUTHORITY_FIELDS:
        modes = sorted(
            {
                str(((item.get("verdict_projection_modes") or {}) if isinstance(item.get("verdict_projection_modes"), dict) else {}).get(field) or "").strip()
                for item in successful_attempts
                if str(((item.get("verdict_projection_modes") or {}) if isinstance(item.get("verdict_projection_modes"), dict) else {}).get(field) or "").strip()
            }
        )
        if modes:
            observed_verdict_projection_modes[field] = modes
    quality_tier_consistent = bool(observed_qualitative_tiers) and len(observed_qualitative_tiers) == 1
    verdict_authority_consistent = bool(observed_verdict_authority_modes) and len(observed_verdict_authority_modes) == 1 and all(
        len(modes) == 1 for modes in observed_verdict_projection_modes.values()
    )
    matrix_axes = case_matrix_axes(case_name)
    observed_execution_salts = sorted(
        {
            str(item.get("execution_salt") or "").strip()
            for item in attempts
            if str(item.get("execution_salt") or "").strip()
        }
    )
    observed_generation_path_classes = sorted(
        {
            str(item.get("generation_path_class") or "").strip().lower()
            for item in successful_attempts
            if str(item.get("generation_path_class") or "").strip()
        }
    )
    observed_generation_positive_buckets = sorted(
        {
            bucket
            for item in successful_attempts
            if (bucket := _generation_positive_bucket(item))
        }
    )
    observed_generation_non_live_reasons = sorted(
        {
            reason
            for item in successful_attempts
            if (reason := _generation_non_live_reason(item))
        }
    )
    generation_path_class_consistent = bool(observed_generation_path_classes) and len(observed_generation_path_classes) == 1
    generation_positive_bucket_consistent = (
        bool(observed_generation_positive_buckets) and len(observed_generation_positive_buckets) == 1
    )
    generation_non_live_reason_consistent = (
        len(observed_generation_non_live_reasons) == 1
        if observed_generation_non_live_reasons
        else None
    )
    primary_generation_path_class = (
        observed_generation_path_classes[0] if generation_path_class_consistent else None
    )
    primary_generation_positive_bucket = (
        observed_generation_positive_buckets[0] if generation_positive_bucket_consistent else None
    )
    primary_generation_non_live_reason = (
        observed_generation_non_live_reasons[0] if generation_non_live_reason_consistent is True else None
    )
    by_generation_path_class = dict(
        sorted(
            Counter(
                str(item.get("generation_path_class") or "").strip().lower()
                for item in successful_attempts
                if str(item.get("generation_path_class") or "").strip()
            ).items()
        )
    )
    by_generation_positive_bucket = dict(
        sorted(
            Counter(
                bucket
                for item in successful_attempts
                if (bucket := _generation_positive_bucket(item))
            ).items()
        )
    )
    by_generation_non_live_reason = dict(
        sorted(
            Counter(
                reason
                for item in successful_attempts
                if (reason := _generation_non_live_reason(item))
            ).items()
        )
    )
    generation_path_observed = bool(
        observed_generation_path_classes
        or observed_generation_positive_buckets
        or observed_generation_non_live_reasons
        or any(
            item.get("generation_provider_attempted") is not None
            or item.get("generation_provider_succeeded") is not None
            or item.get("generation_stub_fallback") is not None
            or item.get("generation_fixture_used") is not None
            or str(item.get("generation_non_live_reason") or "").strip()
            or str(item.get("generation_origin") or "").strip()
            or str(item.get("provider_health_state") or "").strip()
            for item in successful_attempts
        )
    )
    generation_gate_blockers: List[str] = []
    if generation_path_observed and observed_generation_path_classes and not generation_path_class_consistent:
        generation_gate_blockers.append("generation_path_class_inconsistent")
    if generation_path_observed and observed_generation_positive_buckets and not generation_positive_bucket_consistent:
        generation_gate_blockers.append("generation_path_bucket_inconsistent")
    if generation_path_observed and generation_non_live_reason_consistent is False:
        generation_gate_blockers.append("generation_non_live_reason_inconsistent")
    if any(
        bucket in {"fixture_backed_positive", "degraded_fallback_positive"}
        for bucket in observed_generation_positive_buckets
    ) and "live_positive" not in observed_generation_positive_buckets:
        generation_gate_blockers.append("generation_path_not_live_positive")
    generation_path_live_positive_ready = (
        bool(successful_attempts)
        and generation_positive_bucket_consistent
        and primary_generation_positive_bucket == "live_positive"
    )
    measured_gate_blockers: List[str] = []
    if not attempts or not all(bool(item.get("success")) for item in attempts):
        measured_gate_blockers.append("case_failed")
    if not cache_reuse_consistent:
        measured_gate_blockers.append("cache_reuse_inconsistent")
    if not observed_artifact_quality_bands or observed_artifact_quality_bands != ["high"]:
        measured_gate_blockers.append("artifact_quality_band_not_high")
    if not quality_tier_consistent:
        measured_gate_blockers.append("quality_tier_inconsistent")
    if observed_oracle_execution_parities != ["high"]:
        measured_gate_blockers.append("oracle_execution_parity_not_high")
    if not verdict_authority_consistent:
        measured_gate_blockers.append("verdict_authority_inconsistent")
    measured_gate_blockers.extend(generation_gate_blockers)
    report = {
        "case": case_name,
        "case_name": case_name,
        "matrix_axes": matrix_axes,
        "attempt_count": len(attempts),
        "success_count": sum(1 for item in attempts if item.get("success")),
        "failure_count": sum(1 for item in attempts if not item.get("success")),
        "passed": all(bool(item.get("success")) for item in attempts) if attempts else False,
        "cache_reuse_observed": cache_reuse_observed,
        "cache_reuse_consistent": cache_reuse_consistent,
        "executed_query_reduction_observed": executed_query_reduction_observed,
        "observed_artifact_quality_bands": observed_artifact_quality_bands,
        "observed_qualitative_tiers": observed_qualitative_tiers,
        "observed_oracle_execution_parities": observed_oracle_execution_parities,
        "observed_execution_salts": observed_execution_salts,
        "distinct_sid_count": len({str(item.get("sid") or "").strip() for item in attempts if str(item.get("sid") or "").strip()}),
        "observed_verdict_authority_modes": observed_verdict_authority_modes,
        "observed_verdict_projection_modes": observed_verdict_projection_modes,
        "quality_tier_consistent": quality_tier_consistent,
        "verdict_authority_consistent": verdict_authority_consistent,
        "observed_generation_path_classes": observed_generation_path_classes,
        "observed_generation_positive_buckets": observed_generation_positive_buckets,
        "observed_generation_non_live_reasons": observed_generation_non_live_reasons,
        "generation_path_class_consistent": generation_path_class_consistent,
        "generation_positive_bucket_consistent": generation_positive_bucket_consistent,
        "generation_non_live_reason_consistent": generation_non_live_reason_consistent,
        "generation_path_observations": {
            "path_observed": generation_path_observed,
            "observed_path_classes": observed_generation_path_classes,
            "observed_positive_buckets": observed_generation_positive_buckets,
            "observed_non_live_reasons": observed_generation_non_live_reasons,
            "primary_path_class": primary_generation_path_class,
            "primary_positive_bucket": primary_generation_positive_bucket,
            "primary_non_live_reason": primary_generation_non_live_reason,
            "path_class_consistent": generation_path_class_consistent,
            "positive_bucket_consistent": generation_positive_bucket_consistent,
            "non_live_reason_consistent": generation_non_live_reason_consistent,
            "by_path_class": by_generation_path_class,
            "by_positive_bucket": by_generation_positive_bucket,
            "by_non_live_reason": by_generation_non_live_reason,
        },
        "generation_path_gate": {
            "live_positive_ready": generation_path_live_positive_ready,
            "blockers": generation_gate_blockers,
        },
        "measured_gate": {
            "ready": not measured_gate_blockers,
            "blockers": measured_gate_blockers,
        },
        "failure_fingerprints": [
            {"fingerprint": fingerprint, "count": count}
            for fingerprint, count in sorted(fingerprint_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "failure_stages": [
            {"stage": stage, "count": count}
            for stage, count in sorted(stage_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "guard_error_codes": [
            {"guard_error_code": code, "count": count}
            for code, count in sorted(guard_error_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "attempts": attempts,
    }
    return report


def _write_attempt_summary(attempt_dir: Path, summary: Dict[str, Any], resolved_requirement: Dict[str, Any]) -> None:
    if not summary:
        return
    attempt_dir.mkdir(parents=True, exist_ok=True)
    (attempt_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    if yaml is not None:
        (attempt_dir / "requirement.resolved.yml").write_text(
            yaml.safe_dump(resolved_requirement, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )


def _build_attempt_env(sid: str, custom_env: Dict[str, Any]) -> Dict[str, str]:
    env = os.environ.copy()
    env["SID"] = sid
    for key, value in custom_env.items():
        env[str(key)] = str(value)
    return env


def execute_repeat_gate(
    case_dir: Path,
    *,
    attempts: int,
    mode: str,
    snapshot: bool,
    output_dir: Path,
    requirement_path: Optional[Path] = None,
    expectations_path: Optional[Path] = None,
) -> Dict[str, Any]:
    case_spec = _load_case_spec(case_dir, requirement_path)
    expectations = _load_expectations(expectations_path or (case_dir / "expectations.json"))
    output_dir.mkdir(parents=True, exist_ok=True)
    attempt_reports: List[Dict[str, Any]] = []
    matrix_axes = case_matrix_axes(case_spec.name)

    for attempt_index in range(1, max(1, attempts) + 1):
        plan = _write_plan_compat(
            case_spec.requirement,
            multi_vuln_opt_in=bool(case_spec.options.get("multi_vuln_opt_in", False)),
            sid_salt=_execution_salt(output_dir=output_dir, case_name=case_spec.name, attempt=attempt_index),
        )
        sid = plan["sid"]
        env = _build_attempt_env(sid, case_spec.options.get("env") or {})
        metadata_root = REPO_ROOT / "metadata" / sid
        summary: Dict[str, Any] = {}
        error = ""
        pipeline_returncode: Optional[int] = None
        attempt_dir = output_dir / f"attempt-{attempt_index:02d}"
        attempt_dir.mkdir(parents=True, exist_ok=True)

        try:
            _materialize_runtime_assets(sid, case_spec.runtime_assets)
            if _case_requires_docker(expectations):
                _ensure_docker_ready(env)
            proc = _execute_pipeline(sid, mode, env)
            pipeline_returncode = int(proc.returncode)
            summary = _load_manifest_summary(sid, pipeline_returncode=pipeline_returncode)
            summary["case_name"] = case_spec.name
            summary["matrix_axes"] = matrix_axes
            if expectations:
                _validate_expectations(summary, expectations)
        except Exception as exc:  # pragma: no cover - exercised in live E2E only
            error = f"{type(exc).__name__}: {exc}"
            try:
                summary = _load_manifest_summary(sid, pipeline_returncode=pipeline_returncode)
                summary["case_name"] = case_spec.name
                summary["matrix_axes"] = matrix_axes
            except Exception:
                summary = {}
        finally:
            _write_attempt_summary(attempt_dir, summary, plan.get("requirement", case_spec.requirement))
            if snapshot:
                _snapshot_outputs(sid, attempt_dir)

        latest_failure = _load_latest_generator_failure(metadata_root)
        loop_tail = _load_loop_tail(metadata_root)
        attempt_report = summarize_repeat_attempt(
            attempt=attempt_index,
            case_name=case_spec.name,
            matrix_axes=matrix_axes,
            sid=sid,
            summary=summary,
            error=error,
            latest_failure=latest_failure,
            loop_tail=loop_tail,
            attempt_dir=attempt_dir,
        )
        (attempt_dir / "attempt.json").write_text(
            json.dumps(attempt_report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        attempt_reports.append(attempt_report)

    report = aggregate_repeat_results(case_spec.name, attempt_reports)
    report_path = output_dir / "repeatability_report.json"
    matrix_report_path = output_dir / "matrix_report.json"
    support_candidate_path = output_dir / "support_candidate.json"
    report["report_path"] = str(report_path)
    report["matrix_report_path"] = str(matrix_report_path)
    try:
        matrix_report = write_matrix_report(
            matrix_report_path,
            [attempt["summary_path"] for attempt in attempt_reports if attempt.get("summary_path")],
            repeatability_reports=[report],
        )
    except ValueError as exc:
        if "case is not declared in case_matrix.json" not in str(exc):
            raise
        matrix_report = _fallback_matrix_report(
            matrix_report_path,
            case_name=case_spec.name,
            reason=str(exc),
        )
    source_summary_path = next(
        (Path(attempt["summary_path"]) for attempt in attempt_reports if attempt.get("success") and attempt.get("summary_path")),
        None,
    )
    if source_summary_path is None:
        source_summary_path = next(
            (Path(attempt["summary_path"]) for attempt in attempt_reports if attempt.get("summary_path")),
            None,
        )
    support_candidate = None
    if source_summary_path is not None:
        try:
            source_summary_payload = json.loads(source_summary_path.read_text(encoding="utf-8"))
        except Exception:
            source_summary_payload = {}
    else:
        source_summary_payload = {}
    if source_summary_path is not None and str(source_summary_payload.get("manifest_path") or "").strip():
        support_candidate = write_support_candidate(
            support_candidate_path,
            source_summary_path,
            matrix_report=matrix_report,
            repeatability_report=report,
        )
        report["support_candidate_path"] = str(support_candidate_path)
        report["support_ready_bundle_count"] = int(support_candidate.get("support_ready_bundle_count") or 0)
        report["reviewable_bundle_count"] = int(support_candidate.get("reviewable_bundle_count") or 0)
    else:
        report["support_candidate_path"] = str(support_candidate_path)
        report["support_ready_bundle_count"] = 0
        report["reviewable_bundle_count"] = 0
        support_candidate_path.write_text(
            json.dumps(
                {
                    "schema_version": "support_candidate@0.1",
                    "case_name": case_spec.name,
                    "sid": None,
                    "manifest_path": None,
                    "matrix_report_path": str(matrix_report_path),
                    "repeatability_report_path": str(report_path),
                    "case_gates": {
                        "matrix_available": True,
                        "matrix_case_covered": True,
                        "matrix_case_green": False,
                        "repeatability_available": True,
                        "repeatability_passed": bool(report.get("passed")),
                        "external_blockers": ["summary_missing"],
                    },
                    "support_ready_bundle_count": 0,
                    "reviewable_bundle_count": 0,
                    "all_reviewable": False,
                    "candidates": [],
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an E2E case repeatedly and aggregate failures")
    parser.add_argument("--case", type=Path, required=True, help="Path to the case directory")
    parser.add_argument("--attempts", type=int, default=3, help="Number of repeated attempts")
    parser.add_argument("--mode", default="deterministic", help="LLM decoding mode")
    parser.add_argument("--requirement", type=Path, help="Override requirement YAML path")
    parser.add_argument("--expectations", type=Path, help="Override expectations JSON path")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory to store repeatability outputs")
    parser.add_argument("--no-snapshot", action="store_true", help="Skip copying metadata/artifacts snapshots")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    case_dir = args.case.resolve()
    if not case_dir.exists():
        raise SystemExit(f"case directory not found: {case_dir}")
    report = execute_repeat_gate(
        case_dir,
        attempts=max(1, int(args.attempts)),
        mode=args.mode,
        snapshot=not args.no_snapshot,
        output_dir=args.output_dir.resolve(),
        requirement_path=args.requirement.resolve() if args.requirement else None,
        expectations_path=args.expectations.resolve() if args.expectations else None,
    )
    print(f"[E2E] Repeatability report written to {report['report_path']}")
    if not report.get("passed"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
