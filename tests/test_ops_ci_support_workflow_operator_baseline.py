from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_support_workflow_operator_baseline_supports_helper_overrides(tmp_path: Path) -> None:
    capture_path = tmp_path / "calls.json"

    def _helper(name: str) -> Path:
        helper = tmp_path / f"{name}.py"
        _write_executable(
            helper,
            f"""#!/usr/bin/env python3
import json
from pathlib import Path
capture = Path({str(capture_path)!r})
rows = json.loads(capture.read_text(encoding="utf-8")) if capture.exists() else []
rows.append({name!r})
capture.write_text(json.dumps(rows), encoding="utf-8")
raise SystemExit(0)
""",
        )
        return helper

    env = os.environ.copy()
    env["VULD_SUPPORT_BASELINE_REVIEWABLE_HELPER"] = str(_helper("reviewable"))
    env["VULD_SUPPORT_BASELINE_BLOCKED_HELPER"] = str(_helper("blocked"))
    env["VULD_SUPPORT_BASELINE_DOCKER_RETRY_COUNT"] = "4"
    env["VULD_SUPPORT_BASELINE_DOCKER_RETRY_DELAY_SEC"] = "0"

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_support_workflow_operator_baseline.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "[SUPPORT-BASELINE] completed" in completed.stdout
    assert json.loads(capture_path.read_text(encoding="utf-8")) == ["reviewable", "blocked"]


def test_support_workflow_operator_baseline_supports_sequence_helper_override(tmp_path: Path) -> None:
    capture_path = tmp_path / "calls.json"
    sequence_helper = tmp_path / "sequence.py"
    _write_executable(
        sequence_helper,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path
capture = Path({str(capture_path)!r})
capture.write_text(json.dumps(sys.argv[1:]), encoding="utf-8")
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_SUPPORT_BASELINE_SEQUENCE_HELPER"] = str(sequence_helper)
    env["VULD_SUPPORT_BASELINE_REVIEWABLE_HELPER"] = "/tmp/reviewable_helper"
    env["VULD_SUPPORT_BASELINE_BLOCKED_HELPER"] = "/tmp/blocked_helper"
    env["VULD_SUPPORT_BASELINE_DOCKER_RETRY_COUNT"] = "4"
    env["VULD_SUPPORT_BASELINE_DOCKER_RETRY_DELAY_SEC"] = "0"

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_support_workflow_operator_baseline.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(capture_path.read_text(encoding="utf-8")) == [
        "SUPPORT-BASELINE",
        "reviewable accept-path",
        "/tmp/reviewable_helper",
        "--",
        "blocked/no-op path",
        "/tmp/blocked_helper",
    ]


def test_support_workflow_operator_baseline_forwards_retry_seams_to_blocked_helper(tmp_path: Path) -> None:
    capture_path = tmp_path / "blocked_capture.json"
    reviewable_helper = tmp_path / "reviewable.py"
    blocked_helper = tmp_path / "blocked.py"

    _write_executable(
        reviewable_helper,
        """#!/usr/bin/env python3
raise SystemExit(0)
""",
    )
    _write_executable(
        blocked_helper,
        f"""#!/usr/bin/env python3
import json, os
from pathlib import Path
Path({str(capture_path)!r}).write_text(json.dumps({{
    "retry_count": os.environ.get("VULD_BLOCKED_NOOP_DOCKER_RETRY_COUNT"),
    "retry_delay": os.environ.get("VULD_BLOCKED_NOOP_DOCKER_RETRY_DELAY_SEC"),
    "permission_artifact_name": os.environ.get("VULD_BLOCKED_NOOP_PERMISSION_ARTIFACT_NAME"),
    "permission_summary_name": os.environ.get("VULD_BLOCKED_NOOP_PERMISSION_SUMMARY_NAME"),
}}), encoding="utf-8")
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_SUPPORT_BASELINE_REVIEWABLE_HELPER"] = str(reviewable_helper)
    env["VULD_SUPPORT_BASELINE_BLOCKED_HELPER"] = str(blocked_helper)
    env["VULD_SUPPORT_BASELINE_PERMISSION_ARTIFACT_NAME"] = "support_baseline_permission_marker.txt"
    env["VULD_SUPPORT_BASELINE_PERMISSION_SUMMARY_NAME"] = "support_baseline_permission_summary.json"
    env["VULD_SUPPORT_BASELINE_DOCKER_RETRY_COUNT"] = "4"
    env["VULD_SUPPORT_BASELINE_DOCKER_RETRY_DELAY_SEC"] = "0"

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_support_workflow_operator_baseline.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(capture_path.read_text(encoding="utf-8")) == {
        "retry_count": "4",
        "retry_delay": "0",
        "permission_artifact_name": "support_baseline_permission_marker.txt",
        "permission_summary_name": "support_baseline_permission_summary.json",
    }
