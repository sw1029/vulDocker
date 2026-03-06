from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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
