from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.e2e.case_matrix import ALLOWED_AXIS_VALUES, case_matrix_axes, case_matrix_entry


def _read_payload(payload_or_path: Mapping[str, Any] | Path | str) -> Dict[str, Any]:
    if isinstance(payload_or_path, Mapping):
        return dict(payload_or_path)
    path = Path(payload_or_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload
def _summary_passed(summary: Mapping[str, Any]) -> bool:
    overall_pass = summary.get("overall_pass")
    if overall_pass is not None:
        return bool(overall_pass)
    return str(summary.get("pipeline_result") or "").strip().lower() == "success"


def _ensure_case_metadata(case_name: str) -> Dict[str, str]:
    entry = case_matrix_entry(case_name)
    if not entry:
        raise ValueError(f"case is not declared in case_matrix.json: {case_name}")
    return case_matrix_axes(case_name)


def build_matrix_report(
    case_summaries: Sequence[Mapping[str, Any] | Path | str],
    *,
    repeatability_reports: Sequence[Mapping[str, Any] | Path | str] = (),
) -> Dict[str, Any]:
    records: Dict[str, Dict[str, Any]] = {}

    for payload_or_path in case_summaries:
        summary = _read_payload(payload_or_path)
        case_name = str(summary.get("case_name") or "").strip()
        if not case_name:
            raise ValueError("case summary is missing case_name")
        axes = _ensure_case_metadata(case_name)
        record = records.setdefault(case_name, {"axes": axes})
        record["summary"] = summary

    for payload_or_path in repeatability_reports:
        report = _read_payload(payload_or_path)
        case_name = str(report.get("case") or report.get("case_name") or "").strip()
        if not case_name:
            raise ValueError("repeatability report is missing case name")
        axes = _ensure_case_metadata(case_name)
        record = records.setdefault(case_name, {"axes": axes})
        record["repeatability"] = report

    by_axis: Dict[str, Dict[str, Dict[str, int]]] = {
        axis_name: {
            axis_value: {
                "case_count": 0,
                "pass_count": 0,
                "fail_count": 0,
                "repeatability_fail_count": 0,
            }
            for axis_value in sorted(axis_values)
        }
        for axis_name, axis_values in ALLOWED_AXIS_VALUES.items()
    }
    failed_cases = []
    repeatability_failures = []
    cache_reuse_observed_cases = []
    cache_reuse_consistent_cases = []
    executed_query_reduction_observed_cases = []
    measured_gate_ready_cases = []
    measured_gate_not_ready_cases = []
    by_measured_gate_blocker: Dict[str, int] = {}
    by_quality_band: Dict[str, int] = {}
    by_qualitative_tier: Dict[str, int] = {}
    oracle_high_nonhigh_band_cases = []
    by_verdict_authority_mode: Dict[str, int] = {}
    by_run_passed_projection_mode: Dict[str, int] = {}
    by_verify_pass_projection_mode: Dict[str, int] = {}
    by_stage_ceiling_projection_mode: Dict[str, int] = {}
    by_terminal_failure_class_projection_mode: Dict[str, int] = {}
    by_oracle_execution_parity_projection_mode: Dict[str, int] = {}

    for case_name in sorted(records):
        record = records[case_name]
        axes = record["axes"]
        summary = record.get("summary") or {}
        repeatability = record.get("repeatability") or {}
        passed = _summary_passed(summary) if summary else bool(repeatability.get("passed"))
        repeatability_passed = True
        if repeatability:
            repeatability_passed = bool(repeatability.get("passed"))

        if not passed:
            failed_cases.append(case_name)
        if repeatability and not repeatability_passed:
            repeatability_failures.append(case_name)
        if repeatability and bool(repeatability.get("cache_reuse_observed")):
            cache_reuse_observed_cases.append(case_name)
        elif not repeatability and int(summary.get("search_cache_hit_count") or 0) > 0:
            cache_reuse_observed_cases.append(case_name)
        if repeatability and bool(repeatability.get("cache_reuse_consistent")):
            cache_reuse_consistent_cases.append(case_name)
        if repeatability and bool(repeatability.get("executed_query_reduction_observed")):
            executed_query_reduction_observed_cases.append(case_name)
        measured_gate = repeatability.get("measured_gate") if isinstance(repeatability.get("measured_gate"), dict) else {}
        if measured_gate:
            if measured_gate.get("ready") is True:
                measured_gate_ready_cases.append(case_name)
            else:
                measured_gate_not_ready_cases.append(case_name)
                for blocker in measured_gate.get("blockers") or []:
                    token = str(blocker).strip()
                    if token:
                        by_measured_gate_blocker[token] = by_measured_gate_blocker.get(token, 0) + 1
        artifact_quality = summary.get("artifact_quality") if isinstance(summary.get("artifact_quality"), dict) else {}
        quality_band = str((artifact_quality or {}).get("band") or "").strip().lower()
        qualitative_tier = str((artifact_quality or {}).get("qualitative_tier") or "").strip()
        oracle_execution_parity = str((artifact_quality or {}).get("oracle_execution_parity") or "").strip().lower()
        if quality_band:
            by_quality_band[quality_band] = by_quality_band.get(quality_band, 0) + 1
        if qualitative_tier:
            by_qualitative_tier[qualitative_tier] = by_qualitative_tier.get(qualitative_tier, 0) + 1
        if oracle_execution_parity == "high" and quality_band and quality_band != "high":
            oracle_high_nonhigh_band_cases.append(case_name)
        verdict_authority = summary.get("verdict_authority") if isinstance(summary.get("verdict_authority"), dict) else {}
        authority_fields = verdict_authority.get("fields") if isinstance(verdict_authority.get("fields"), dict) else {}
        authority_mode = str(verdict_authority.get("mode") or "").strip()
        if authority_mode:
            by_verdict_authority_mode[authority_mode] = by_verdict_authority_mode.get(authority_mode, 0) + 1
        for field_name, bucket in (
            ("run_passed", by_run_passed_projection_mode),
            ("verify_pass", by_verify_pass_projection_mode),
            ("stage_ceiling", by_stage_ceiling_projection_mode),
            ("terminal_failure_class", by_terminal_failure_class_projection_mode),
            ("oracle_execution_parity", by_oracle_execution_parity_projection_mode),
        ):
            projection_mode = str(((authority_fields.get(field_name) or {}) if isinstance(authority_fields.get(field_name), dict) else {}).get("projection_mode") or "").strip()
            if projection_mode:
                bucket[projection_mode] = bucket.get(projection_mode, 0) + 1

        for axis_name, axis_value in axes.items():
            bucket = by_axis[axis_name][axis_value]
            bucket["case_count"] += 1
            if passed:
                bucket["pass_count"] += 1
            else:
                bucket["fail_count"] += 1
            if repeatability and not repeatability_passed:
                bucket["repeatability_fail_count"] += 1

    return {
        "schema_version": "matrix_report@0.1",
        "case_count": len(records),
        "covered_cases": sorted(records),
        "failed_cases": failed_cases,
        "repeatability_failures": repeatability_failures,
        "fully_green": bool(records) and not failed_cases and not repeatability_failures,
        "by_axis": by_axis,
        "quality_observations": {
            "by_band": by_quality_band,
            "by_qualitative_tier": by_qualitative_tier,
            "oracle_high_nonhigh_band_cases": oracle_high_nonhigh_band_cases,
        },
        "authority_observations": {
            "by_verdict_authority_mode": by_verdict_authority_mode,
            "by_run_passed_projection_mode": by_run_passed_projection_mode,
            "by_verify_pass_projection_mode": by_verify_pass_projection_mode,
            "by_stage_ceiling_projection_mode": by_stage_ceiling_projection_mode,
            "by_terminal_failure_class_projection_mode": by_terminal_failure_class_projection_mode,
            "by_oracle_execution_parity_projection_mode": by_oracle_execution_parity_projection_mode,
        },
        "measured_gate_observations": {
            "ready_cases": measured_gate_ready_cases,
            "not_ready_cases": measured_gate_not_ready_cases,
            "by_blocker": by_measured_gate_blocker,
        },
        "cache_observations": {
            "cache_reuse_observed_cases": cache_reuse_observed_cases,
            "cache_reuse_consistent_cases": cache_reuse_consistent_cases,
            "executed_query_reduction_observed_cases": executed_query_reduction_observed_cases,
        },
    }


def write_matrix_report(
    output_path: Path,
    case_summaries: Sequence[Mapping[str, Any] | Path | str],
    *,
    repeatability_reports: Sequence[Mapping[str, Any] | Path | str] = (),
) -> Dict[str, Any]:
    report = build_matrix_report(case_summaries, repeatability_reports=repeatability_reports)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build matrix_report.json from repeat_case output directories")
    parser.add_argument(
        "run_dirs",
        nargs="+",
        help="repeat_case output directories containing summary.json and optional repeatability_report.json",
    )
    parser.add_argument("--output", type=Path, required=True, help="Path to matrix_report.json")
    args = parser.parse_args(argv)

    summaries: list[Path] = []
    repeatability_reports: list[Path] = []

    for run_dir_input in args.run_dirs:
        run_dir = Path(run_dir_input).resolve()
        if not run_dir.is_dir():
            raise SystemExit(f"run directory not found: {run_dir}")

        summary_path = run_dir / "summary.json"
        if summary_path.exists():
            summaries.append(summary_path)

        repeatability_path = run_dir / "repeatability_report.json"
        if repeatability_path.exists():
            repeatability_reports.append(repeatability_path)
        elif not summary_path.exists():
            raise SystemExit(
                f"neither summary.json nor repeatability_report.json found: {run_dir}"
            )

    report = write_matrix_report(
        args.output.resolve(),
        summaries,
        repeatability_reports=repeatability_reports,
    )
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "case_count": report.get("case_count"),
                "fully_green": report.get("fully_green"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
