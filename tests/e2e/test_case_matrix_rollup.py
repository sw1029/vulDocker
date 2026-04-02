from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.e2e.matrix_report import build_matrix_report, write_matrix_report
from tests.e2e import repeat_case
from tests.e2e.repeat_case import aggregate_repeat_results, summarize_repeat_attempt
from tests.e2e.run_case import CaseSpec


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def test_build_matrix_report_rolls_up_axis_counts(tmp_path: Path) -> None:
    summary_success = _write_json(
        tmp_path / "summary-success.json",
        {
            "case_name": "cwe-89-basic",
            "overall_pass": True,
            "pipeline_result": "success",
            "artifact_quality": {
                "band": "high",
                "qualitative_tier": "bounded_sidecar_parity_success",
                "oracle_execution_parity": "high",
            },
            "verdict_authority": {
                "mode": "single_bundle",
                "fields": {
                    "run_passed": {"projection_mode": "single_bundle_exact"},
                    "verify_pass": {"projection_mode": "single_bundle_exact"},
                    "stage_ceiling": {"projection_mode": "single_bundle_exact"},
                    "terminal_failure_class": {"projection_mode": "bundle_truth_only"},
                    "oracle_execution_parity": {"projection_mode": "single_bundle_exact"},
                },
            },
            "search_cache_hit_count": 0,
            "search_cache_miss_count": 2,
            "search_cache_reuse_ratio": 0.0,
            "search_planned_query_count": 2,
            "search_executed_query_count": 2,
            "search_early_stop_triggered": False,
        },
    )
    summary_failure = _write_json(
        tmp_path / "summary-failure.json",
        {
            "case_name": "open-redirect-strict-dynamic-no-remote",
            "overall_pass": False,
            "pipeline_result": "failure",
            "artifact_quality": {
                "band": "medium",
                "qualitative_tier": "thin_fallback_demo",
                "oracle_execution_parity": "high",
            },
            "verdict_authority": {
                "mode": "multi_bundle",
                "fields": {
                    "run_passed": {"projection_mode": "multibundle_rollup"},
                    "verify_pass": {"projection_mode": "multibundle_rollup"},
                    "stage_ceiling": {"projection_mode": "multibundle_rollup"},
                    "terminal_failure_class": {"projection_mode": "multibundle_rollup"},
                    "oracle_execution_parity": {"projection_mode": "multibundle_rollup"},
                },
            },
            "search_cache_hit_count": 1,
            "search_cache_miss_count": 1,
            "search_cache_reuse_ratio": 0.5,
            "search_planned_query_count": 3,
            "search_executed_query_count": 2,
            "search_early_stop_triggered": True,
        },
    )
    repeatability_failure = _write_json(
        tmp_path / "repeatability-report.json",
        {
            "case": "open-redirect-strict-dynamic-no-remote",
            "passed": False,
            "cache_reuse_observed": True,
            "cache_reuse_consistent": True,
            "executed_query_reduction_observed": True,
            "generation_path_observations": {
                "primary_path_class": "fixture",
                "primary_positive_bucket": "fixture_backed_positive",
                "primary_non_live_reason": "fixture_backed",
                "path_class_consistent": True,
                "positive_bucket_consistent": True,
                "non_live_reason_consistent": True,
            },
            "generation_path_gate": {
                "live_positive_ready": False,
                "blockers": ["generation_path_not_live_positive"],
            },
            "measured_gate": {"ready": False, "blockers": ["case_failed", "artifact_quality_band_not_high"]},
        },
    )

    report = build_matrix_report(
        [summary_success, summary_failure],
        repeatability_reports=[repeatability_failure],
    )

    assert report["schema_version"] == "matrix_report@0.1"
    assert report["case_count"] == 2
    assert report["fully_green"] is False
    assert report["covered_cases"] == ["cwe-89-basic", "open-redirect-strict-dynamic-no-remote"]
    assert report["failed_cases"] == ["open-redirect-strict-dynamic-no-remote"]
    assert report["repeatability_failures"] == ["open-redirect-strict-dynamic-no-remote"]
    assert report["by_axis"]["remote_mode"]["remote_ok"] == {
        "case_count": 1,
        "pass_count": 1,
        "fail_count": 0,
        "repeatability_fail_count": 0,
    }
    assert report["by_axis"]["remote_mode"]["strict_no_remote"] == {
        "case_count": 1,
        "pass_count": 0,
        "fail_count": 1,
        "repeatability_fail_count": 1,
    }
    assert report["quality_observations"]["by_band"] == {"high": 1, "medium": 1}
    assert report["quality_observations"]["by_qualitative_tier"] == {
        "bounded_sidecar_parity_success": 1,
        "thin_fallback_demo": 1,
    }
    assert report["quality_observations"]["oracle_high_nonhigh_band_cases"] == [
        "open-redirect-strict-dynamic-no-remote"
    ]
    assert report["authority_observations"]["by_verdict_authority_mode"] == {
        "single_bundle": 1,
        "multi_bundle": 1,
    }
    assert report["authority_observations"]["by_run_passed_projection_mode"] == {
        "single_bundle_exact": 1,
        "multibundle_rollup": 1,
    }
    assert report["measured_gate_observations"] == {
        "ready_cases": [],
        "not_ready_cases": ["open-redirect-strict-dynamic-no-remote"],
        "by_blocker": {
            "case_failed": 1,
            "artifact_quality_band_not_high": 1,
        },
    }
    assert report["generation_path_observations"] == {
        "by_primary_path_class": {"fixture": 1},
        "by_primary_positive_bucket": {"fixture_backed_positive": 1},
        "by_primary_non_live_reason": {"fixture_backed": 1},
        "path_class_consistent_cases": ["open-redirect-strict-dynamic-no-remote"],
        "path_class_inconsistent_cases": [],
        "positive_bucket_consistent_cases": ["open-redirect-strict-dynamic-no-remote"],
        "positive_bucket_inconsistent_cases": [],
        "non_live_reason_consistent_cases": ["open-redirect-strict-dynamic-no-remote"],
        "non_live_reason_inconsistent_cases": [],
        "live_positive_ready_cases": [],
        "live_positive_blocked_cases": ["open-redirect-strict-dynamic-no-remote"],
        "by_generation_gate_blocker": {"generation_path_not_live_positive": 1},
    }


def test_write_matrix_report_collects_cache_observations(tmp_path: Path) -> None:
    summary = _write_json(
        tmp_path / "summary.json",
        {
            "case_name": "template-injection-name-only",
            "overall_pass": True,
            "pipeline_result": "success",
            "artifact_quality": {
                "band": "medium",
                "qualitative_tier": "thin_fallback_demo",
                "oracle_execution_parity": "high",
            },
            "search_cache_hit_count": 2,
            "search_cache_miss_count": 1,
            "search_cache_reuse_ratio": 0.667,
            "search_planned_query_count": 4,
            "search_executed_query_count": 3,
            "search_early_stop_triggered": True,
        },
    )
    repeatability = _write_json(
        tmp_path / "repeatability.json",
        {
            "case": "template-injection-name-only",
            "passed": True,
            "cache_reuse_observed": True,
            "cache_reuse_consistent": True,
            "executed_query_reduction_observed": False,
            "generation_path_observations": {
                "primary_path_class": "live",
                "primary_positive_bucket": "live_positive",
                "path_class_consistent": True,
                "positive_bucket_consistent": True,
            },
            "generation_path_gate": {"live_positive_ready": True, "blockers": []},
            "measured_gate": {"ready": True, "blockers": []},
        },
    )

    output_path = tmp_path / "matrix_report.json"
    report = write_matrix_report(output_path, [summary], repeatability_reports=[repeatability])

    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert persisted == report
    assert report["fully_green"] is True
    assert report["cache_observations"]["cache_reuse_observed_cases"] == ["template-injection-name-only"]
    assert report["cache_observations"]["cache_reuse_consistent_cases"] == ["template-injection-name-only"]
    assert report["cache_observations"]["executed_query_reduction_observed_cases"] == []
    assert report["quality_observations"]["by_qualitative_tier"] == {"thin_fallback_demo": 1}
    assert report["measured_gate_observations"] == {
        "ready_cases": ["template-injection-name-only"],
        "not_ready_cases": [],
        "by_blocker": {},
    }
    assert report["generation_path_observations"] == {
        "by_primary_path_class": {"live": 1},
        "by_primary_positive_bucket": {"live_positive": 1},
        "by_primary_non_live_reason": {},
        "path_class_consistent_cases": ["template-injection-name-only"],
        "path_class_inconsistent_cases": [],
        "positive_bucket_consistent_cases": ["template-injection-name-only"],
        "positive_bucket_inconsistent_cases": [],
        "non_live_reason_consistent_cases": [],
        "non_live_reason_inconsistent_cases": [],
        "live_positive_ready_cases": ["template-injection-name-only"],
        "live_positive_blocked_cases": [],
        "by_generation_gate_blocker": {},
    }


def test_aggregate_repeat_results_surfaces_cache_observations() -> None:
    report = aggregate_repeat_results(
        "cwe-89-basic",
        [
            {
                "attempt": 1,
                "sid": "sid-a",
                "success": True,
                "execution_salt": "salt-a",
                "search_cache_hit_count": 0,
                "search_executed_query_count": 4,
                "artifact_quality_band": "high",
                "artifact_quality_qualitative_tier": "bounded_sidecar_parity_success",
                "oracle_execution_parity": "high",
                "generation_origin": "llm_manifest",
                "provider_health_state": "live",
                "generation_path_class": "live",
                "generation_provider_attempted": True,
                "generation_provider_succeeded": True,
                "generation_stub_fallback": False,
                "generation_fixture_used": False,
                "verdict_authority_mode": "single_bundle",
                "verdict_projection_modes": {
                    "run_passed": "single_bundle_exact",
                    "verify_pass": "single_bundle_exact",
                    "oracle_execution_parity": "single_bundle_exact",
                },
            },
            {
                "attempt": 2,
                "sid": "sid-b",
                "success": True,
                "execution_salt": "salt-b",
                "search_cache_hit_count": 2,
                "search_executed_query_count": 2,
                "artifact_quality_band": "high",
                "artifact_quality_qualitative_tier": "bounded_sidecar_parity_success",
                "oracle_execution_parity": "high",
                "generation_origin": "llm_manifest",
                "provider_health_state": "live",
                "generation_path_class": "live",
                "generation_provider_attempted": True,
                "generation_provider_succeeded": True,
                "generation_stub_fallback": False,
                "generation_fixture_used": False,
                "verdict_authority_mode": "single_bundle",
                "verdict_projection_modes": {
                    "run_passed": "single_bundle_exact",
                    "verify_pass": "single_bundle_exact",
                    "oracle_execution_parity": "single_bundle_exact",
                },
            },
            {
                "attempt": 3,
                "sid": "sid-c",
                "success": True,
                "execution_salt": "salt-c",
                "search_cache_hit_count": 1,
                "search_executed_query_count": 3,
                "artifact_quality_band": "high",
                "artifact_quality_qualitative_tier": "bounded_sidecar_parity_success",
                "oracle_execution_parity": "high",
                "generation_origin": "llm_manifest",
                "provider_health_state": "live",
                "generation_path_class": "live",
                "generation_provider_attempted": True,
                "generation_provider_succeeded": True,
                "generation_stub_fallback": False,
                "generation_fixture_used": False,
                "verdict_authority_mode": "single_bundle",
                "verdict_projection_modes": {
                    "run_passed": "single_bundle_exact",
                    "verify_pass": "single_bundle_exact",
                    "oracle_execution_parity": "single_bundle_exact",
                },
            },
        ],
    )

    assert report["matrix_axes"]["family_known"] == "known"
    assert report["cache_reuse_observed"] is True
    assert report["cache_reuse_consistent"] is True
    assert report["executed_query_reduction_observed"] is True
    assert report["observed_artifact_quality_bands"] == ["high"]
    assert report["observed_qualitative_tiers"] == ["bounded_sidecar_parity_success"]
    assert report["observed_oracle_execution_parities"] == ["high"]
    assert report["observed_execution_salts"] == ["salt-a", "salt-b", "salt-c"]
    assert report["distinct_sid_count"] == 3
    assert report["quality_tier_consistent"] is True
    assert report["observed_verdict_authority_modes"] == ["single_bundle"]
    assert report["observed_verdict_projection_modes"] == {
        "run_passed": ["single_bundle_exact"],
        "verify_pass": ["single_bundle_exact"],
        "oracle_execution_parity": ["single_bundle_exact"],
    }
    assert report["verdict_authority_consistent"] is True
    assert report["observed_generation_path_classes"] == ["live"]
    assert report["observed_generation_positive_buckets"] == ["live_positive"]
    assert report["observed_generation_non_live_reasons"] == []
    assert report["generation_non_live_reason_consistent"] is None
    assert report["generation_path_observations"] == {
        "path_observed": True,
        "observed_path_classes": ["live"],
        "observed_positive_buckets": ["live_positive"],
        "observed_non_live_reasons": [],
        "primary_path_class": "live",
        "primary_positive_bucket": "live_positive",
        "primary_non_live_reason": None,
        "path_class_consistent": True,
        "positive_bucket_consistent": True,
        "non_live_reason_consistent": None,
        "by_path_class": {"live": 3},
        "by_positive_bucket": {"live_positive": 3},
        "by_non_live_reason": {},
    }
    assert report["generation_path_gate"] == {
        "live_positive_ready": True,
        "blockers": [],
    }
    assert report["measured_gate"] == {
        "ready": True,
        "blockers": [],
    }


def test_summarize_repeat_attempt_preserves_case_metadata_without_manifest_summary(tmp_path: Path) -> None:
    attempt_dir = tmp_path / "attempt-01"
    attempt_dir.mkdir(parents=True, exist_ok=True)

    attempt = summarize_repeat_attempt(
        attempt=1,
        case_name="open-redirect-name-only",
        matrix_axes={"family_known": "known", "remote_mode": "remote_ok"},
        sid="sid-no-manifest",
        summary={},
        error="CaseError: docker daemon is not reachable",
        latest_failure={},
        loop_tail={},
        attempt_dir=attempt_dir,
    )

    assert attempt["case_name"] == "open-redirect-name-only"
    assert attempt["matrix_axes"] == {"family_known": "known", "remote_mode": "remote_ok"}
    assert attempt["summary_path"] is None
    assert attempt["search_cache_hit_count"] == 0
    assert attempt["artifact_quality_band"] is None
    assert attempt["artifact_quality_qualitative_tier"] is None


def test_execute_repeat_gate_skips_docker_check_for_non_docker_failure_case(tmp_path: Path, monkeypatch) -> None:
    case_dir = tmp_path / "case"
    case_dir.mkdir(parents=True, exist_ok=True)
    expectations_path = tmp_path / "expectations.no-remote.json"
    expectations_path.write_text(
        json.dumps({"manifest": {"failure": {"stage": "RESEARCH"}}}, ensure_ascii=False),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        repeat_case,
        "_load_case_spec",
        lambda _case_dir, _requirement_path=None: CaseSpec(
            name="cwe-unknown-basic",
            requirement={"target": {}},
            runtime_assets={},
            options={},
        ),
    )
    monkeypatch.setattr(
        repeat_case,
        "_write_plan",
        lambda requirement, *, multi_vuln_opt_in=False, sid_salt="": {
            "sid": "sid-repeat-no-docker",
            "requirement": requirement,
            "sid_salt": sid_salt,
        },
    )
    monkeypatch.setattr(repeat_case, "_materialize_runtime_assets", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        repeat_case,
        "_ensure_docker_ready",
        lambda _env: (_ for _ in ()).throw(AssertionError("docker check should not run")),
    )
    monkeypatch.setattr(
        repeat_case,
        "_execute_pipeline",
        lambda _sid, _mode, _env: SimpleNamespace(returncode=0),
    )
    monkeypatch.setattr(
        repeat_case,
        "_load_manifest_summary",
        lambda _sid, *, pipeline_returncode=None: {"overall_pass": False, "pipeline_result": "failure"},
    )
    monkeypatch.setattr(repeat_case, "_validate_expectations", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(repeat_case, "_snapshot_outputs", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(repeat_case, "_load_latest_generator_failure", lambda _metadata_root: {})
    monkeypatch.setattr(repeat_case, "_load_loop_tail", lambda _metadata_root: {})

    report = repeat_case.execute_repeat_gate(
        case_dir,
        attempts=1,
        mode="deterministic",
        snapshot=False,
        output_dir=tmp_path / "output",
        expectations_path=expectations_path,
    )

    assert report["case"] == "cwe-unknown-basic"
    assert report["case_name"] == "cwe-unknown-basic"
    assert report["attempt_count"] == 1
    assert Path(report["support_candidate_path"]).exists()
