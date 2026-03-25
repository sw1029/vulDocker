from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_operator_current_baseline_sequence_forwards_child_surfaces_and_invokes_sequence(
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
  "measured_retry_count": os.environ.get("VULD_MEASURED_BASELINE_DOCKER_RETRY_COUNT"),
  "support_retry_count": os.environ.get("VULD_SUPPORT_BASELINE_DOCKER_RETRY_COUNT"),
  "docker_positive_retry_count": os.environ.get("VULD_DOCKER_POSITIVE_BASELINE_DOCKER_RETRY_COUNT"),
  "no_docker_permission_artifact_name": os.environ.get("VULD_NO_DOCKER_BASELINE_PERMISSION_ARTIFACT_NAME"),
  "measured_permission_artifact_name": os.environ.get("VULD_MEASURED_BASELINE_PERMISSION_ARTIFACT_NAME"),
  "support_permission_artifact_name": os.environ.get("VULD_SUPPORT_BASELINE_PERMISSION_ARTIFACT_NAME"),
  "docker_positive_permission_artifact_name": os.environ.get("VULD_DOCKER_POSITIVE_BASELINE_PERMISSION_ARTIFACT_NAME"),
}}), encoding="utf-8")
raise SystemExit(0)
""",
    )

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_operator_current_baseline_sequence.sh')!r}\n"
                f"operator_run_current_baseline_sequence 4 0 sample_permission_marker.txt sample_permission_summary.json {str(sequence_helper)!r} CURRENT-BASELINE /tmp/no_docker_helper /tmp/measured_helper /tmp/support_helper /tmp/docker_positive_helper /tmp/helper_regression_helper"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(capture.read_text(encoding="utf-8")) == {
        "argv": [
            "CURRENT-BASELINE",
            "no-docker operator baseline",
            "/tmp/no_docker_helper",
            "--",
            "measured gate operator baseline",
            "/tmp/measured_helper",
            "--",
            "support workflow baseline",
            "/tmp/support_helper",
            "--",
            "docker-positive operator baseline",
            "/tmp/docker_positive_helper",
            "--",
            "ops helper contract regression",
            "/tmp/helper_regression_helper",
        ],
        "measured_retry_count": "4",
        "support_retry_count": "4",
        "docker_positive_retry_count": "4",
        "no_docker_permission_artifact_name": "sample_permission_marker.txt",
        "measured_permission_artifact_name": "sample_permission_marker.txt",
        "support_permission_artifact_name": "sample_permission_marker.txt",
        "docker_positive_permission_artifact_name": "sample_permission_marker.txt",
    }


def test_operator_current_baseline_sequence_rejects_missing_sequence_helper() -> None:
    missing = Path("/tmp/vuld_missing_operator_current_baseline_sequence_helper.sh")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_operator_current_baseline_sequence.sh')!r}\n"
                f"operator_run_current_baseline_sequence 4 0 sample_permission_marker.txt sample_permission_summary.json {str(missing)!r} CURRENT-BASELINE /tmp/no_docker_helper /tmp/measured_helper /tmp/support_helper /tmp/docker_positive_helper /tmp/helper_regression_helper"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr == (
        "[CURRENT-BASELINE] sequence helper not found or not executable: "
        f"{missing}\n"
    )
