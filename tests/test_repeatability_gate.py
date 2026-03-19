from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import tests.e2e.repeat_case as repeat_case
from tests.e2e.repeat_case import aggregate_repeat_results, summarize_repeat_attempt


def test_summarize_repeat_attempt_extracts_guard_mismatch(tmp_path: Path) -> None:
    attempt_dir = tmp_path / "attempt-01"
    attempt_dir.mkdir(parents=True)
    (attempt_dir / "summary.json").write_text("{}", encoding="utf-8")
    summary = {
        "overall_pass": False,
        "reviewer": {"blocking_bundles": ["cwe-89"]},
        "bundles": [
            {
                "slug": "cwe-89",
                "vuln_id": "CWE-89",
                "evidence": "guard mismatch: semantic mismatch: missing input-to-SQL composition path for CWE-89",
            }
        ],
    }

    record = summarize_repeat_attempt(
        attempt=1,
        sid="sid-repeat",
        summary=summary,
        error="",
        latest_failure={"stage": "GENERATOR", "failure_fingerprint": "fp-1", "guard_error_code": "guard_semantic_mismatch"},
        loop_tail={"stage": "GENERATOR"},
        attempt_dir=attempt_dir,
    )

    assert record["success"] is True
    assert record["failure_stage"] == "GENERATOR"
    assert record["failure_fingerprint"] == "fp-1"
    assert record["guard_error_code"] == "guard_semantic_mismatch"
    assert record["guard_mismatches"][0]["slug"] == "cwe-89"


def test_aggregate_repeat_results_counts_failures() -> None:
    report = aggregate_repeat_results(
        "cwe-89-basic",
        [
            {
                "attempt": 1,
                "success": True,
                "failure_stage": None,
                "failure_fingerprint": None,
                "guard_error_code": None,
            },
            {
                "attempt": 2,
                "success": False,
                "failure_stage": "GENERATOR",
                "failure_fingerprint": "fp-1",
                "guard_error_code": "guard_semantic_mismatch",
            },
            {
                "attempt": 3,
                "success": False,
                "failure_stage": "GENERATOR",
                "failure_fingerprint": "fp-1",
                "guard_error_code": "guard_semantic_mismatch",
            },
        ],
    )

    assert report["case"] == "cwe-89-basic"
    assert report["case_name"] == "cwe-89-basic"
    assert report["attempt_count"] == 3
    assert report["success_count"] == 1
    assert report["failure_count"] == 2
    assert report["passed"] is False
    assert report["failure_fingerprints"] == [{"fingerprint": "fp-1", "count": 2}]
    assert report["failure_stages"] == [{"stage": "GENERATOR", "count": 2}]
    assert report["guard_error_codes"] == [{"guard_error_code": "guard_semantic_mismatch", "count": 2}]


def test_summarize_repeat_attempt_clears_failure_stage_for_success_without_failure_signal(tmp_path: Path) -> None:
    attempt_dir = tmp_path / "attempt-01"
    attempt_dir.mkdir(parents=True)
    (attempt_dir / "summary.json").write_text("{}", encoding="utf-8")

    record = summarize_repeat_attempt(
        attempt=1,
        sid="sid-repeat",
        summary={"overall_pass": True, "reviewer": {"blocking_bundles": []}, "bundles": []},
        error="",
        latest_failure={},
        loop_tail={"stage": "REVIEW", "success": True},
        attempt_dir=attempt_dir,
    )

    assert record["success"] is True
    assert record["failure_stage"] is None
    assert record["failure_fingerprint"] is None
    assert record["guard_error_code"] is None


def test_summarize_repeat_attempt_infers_executor_stage_from_subprocess_error(tmp_path: Path) -> None:
    attempt_dir = tmp_path / "attempt-01"
    attempt_dir.mkdir(parents=True)
    (attempt_dir / "summary.json").write_text("{}", encoding="utf-8")

    record = summarize_repeat_attempt(
        attempt=1,
        sid="sid-repeat",
        summary={"overall_pass": None, "reviewer": {"blocking_bundles": []}, "bundles": []},
        error=(
            "CalledProcessError: Command '['python', 'executor/runtime/docker_local.py', '--sid', "
            "'sid-repeat', '--run']' returned non-zero exit status 1."
        ),
        latest_failure={},
        loop_tail={"stage": "GENERATOR", "success": True},
        attempt_dir=attempt_dir,
    )

    assert record["success"] is False
    assert record["failure_stage"] == "EXECUTOR"


def test_execute_repeat_gate_forwards_pipeline_returncode_into_summary_expectations(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case_dir = tmp_path / "case"
    case_dir.mkdir(parents=True)
    metadata_root = tmp_path / "metadata"
    captured: list[int | None] = []

    monkeypatch.setattr(
        repeat_case,
        "_load_case_spec",
        lambda _case_dir, _requirement_path=None: type(
            "CaseSpec",
            (),
            {
                "name": "repeat-case",
                "requirement": {"vuln_id": "NAME-TEMPLATE-INJECTION"},
                "runtime_assets": {},
                "options": {},
            },
        )(),
    )
    monkeypatch.setattr(
        repeat_case,
        "_write_plan",
        lambda requirement, multi_vuln_opt_in=False: {
            "sid": "sid-repeat-forward",
            "requirement": requirement,
        },
    )
    monkeypatch.setattr(repeat_case, "_materialize_runtime_assets", lambda sid, assets: None)
    monkeypatch.setattr(repeat_case, "_ensure_docker_ready", lambda env: None)
    monkeypatch.setattr(
        repeat_case,
        "_execute_pipeline",
        lambda sid, mode, env: type("Proc", (), {"returncode": 0})(),
    )

    def _fake_load_manifest_summary(sid: str, *, pipeline_returncode=None):
        captured.append(pipeline_returncode)
        return {
            "sid": sid,
            "overall_pass": True,
            "pipeline_result": "success",
            "pipeline_returncode": pipeline_returncode,
            "bundles": [],
            "reviewer": {"blocking_bundles": []},
        }

    monkeypatch.setattr(repeat_case, "_load_manifest_summary", _fake_load_manifest_summary)
    monkeypatch.setattr(repeat_case, "_write_attempt_summary", lambda attempt_dir, summary, resolved_requirement: None)
    monkeypatch.setattr(repeat_case, "_snapshot_outputs", lambda sid, attempt_dir: None)
    monkeypatch.setattr(repeat_case, "_load_latest_generator_failure", lambda metadata_root: {})
    monkeypatch.setattr(repeat_case, "_load_loop_tail", lambda metadata_root: {})
    monkeypatch.setattr(repeat_case, "REPO_ROOT", tmp_path)

    report = repeat_case.execute_repeat_gate(
        case_dir,
        attempts=1,
        mode="deterministic",
        snapshot=False,
        output_dir=tmp_path / "out",
        expectations_path=None,
    )

    assert report["passed"] is True
    assert report["case_name"] == "repeat-case"
    assert captured == [0]
    matrix_report = json.loads(Path(report["matrix_report_path"]).read_text(encoding="utf-8"))
    assert matrix_report["requested_case_name"] == "repeat-case"
    assert "case is not declared in case_matrix.json" in matrix_report["matrix_unavailable_reason"]
