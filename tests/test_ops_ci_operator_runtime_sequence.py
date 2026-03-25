from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_operator_runtime_sequence_forwards_runtime_surface_and_invokes_sequence_helper(
    tmp_path: Path,
) -> None:
    capture = tmp_path / "capture.json"
    sequence_helper = tmp_path / "sequence.py"

    _write_executable(
        sequence_helper,
        f"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
Path({str(capture)!r}).write_text(json.dumps({{
  "argv": sys.argv[1:],
  "retry_count": os.environ.get("VULD_SAMPLE_TARGET_DOCKER_RETRY_COUNT"),
  "retry_delay": os.environ.get("VULD_SAMPLE_TARGET_DOCKER_RETRY_DELAY_SEC"),
  "permission_artifact_name": os.environ.get("VULD_SAMPLE_TARGET_PERMISSION_ARTIFACT_NAME"),
  "permission_summary_name": os.environ.get("VULD_SAMPLE_TARGET_PERMISSION_SUMMARY_NAME"),
}}), encoding="utf-8")
raise SystemExit(0)
""",
    )

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_operator_runtime_sequence.sh')!r}\n"
                f"operator_run_baseline_sequence_with_runtime_surface 4 0 sample_permission_marker.txt sample_permission_summary.json VULD_SAMPLE_TARGET {str(sequence_helper)!r} TEST-BASELINE 'first step' /tmp/first_helper -- 'second step' /tmp/second_helper"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(capture.read_text(encoding="utf-8")) == {
        "argv": [
            "TEST-BASELINE",
            "first step",
            "/tmp/first_helper",
            "--",
            "second step",
            "/tmp/second_helper",
        ],
        "retry_count": "4",
        "retry_delay": "0",
        "permission_artifact_name": "sample_permission_marker.txt",
        "permission_summary_name": "sample_permission_summary.json",
    }


def test_operator_runtime_sequence_rejects_missing_sequence_helper() -> None:
    missing = Path("/tmp/vuld_missing_operator_runtime_sequence_helper.sh")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_operator_runtime_sequence.sh')!r}\n"
                f"operator_run_baseline_sequence_with_runtime_surface 4 0 sample_permission_marker.txt sample_permission_summary.json VULD_SAMPLE_TARGET {str(missing)!r} TEST-BASELINE 'first step' /tmp/first_helper"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr == (
        f"[TEST-BASELINE] sequence helper not found or not executable: {missing}\n"
    )
