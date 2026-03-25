from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_current_operator_baseline_supports_helper_overrides(tmp_path: Path) -> None:
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
    env["VULD_CURRENT_BASELINE_NO_DOCKER_HELPER"] = str(_helper("no_docker"))
    env["VULD_CURRENT_BASELINE_MEASURED_HELPER"] = str(_helper("measured"))
    env["VULD_CURRENT_BASELINE_SUPPORT_HELPER"] = str(_helper("support"))
    env["VULD_CURRENT_BASELINE_DOCKER_POSITIVE_HELPER"] = str(_helper("docker_positive"))
    env["VULD_CURRENT_BASELINE_HELPER_REGRESSION"] = str(_helper("helper_regression"))
    env["VULD_CURRENT_BASELINE_DOCKER_RETRY_COUNT"] = "4"
    env["VULD_CURRENT_BASELINE_DOCKER_RETRY_DELAY_SEC"] = "0"

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_current_operator_baseline.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "[CURRENT-BASELINE] completed" in completed.stdout
    assert json.loads(capture_path.read_text(encoding="utf-8")) == [
        "no_docker",
        "measured",
        "support",
        "docker_positive",
        "helper_regression",
    ]


def test_current_operator_baseline_supports_sequence_helper_override(tmp_path: Path) -> None:
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
    env["VULD_CURRENT_BASELINE_SEQUENCE_HELPER"] = str(sequence_helper)
    env["VULD_CURRENT_BASELINE_NO_DOCKER_HELPER"] = "/tmp/no_docker_helper"
    env["VULD_CURRENT_BASELINE_MEASURED_HELPER"] = "/tmp/measured_helper"
    env["VULD_CURRENT_BASELINE_SUPPORT_HELPER"] = "/tmp/support_helper"
    env["VULD_CURRENT_BASELINE_DOCKER_POSITIVE_HELPER"] = "/tmp/docker_positive_helper"
    env["VULD_CURRENT_BASELINE_HELPER_REGRESSION"] = "/tmp/helper_regression_helper"
    env["VULD_CURRENT_BASELINE_DOCKER_RETRY_COUNT"] = "4"
    env["VULD_CURRENT_BASELINE_DOCKER_RETRY_DELAY_SEC"] = "0"

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_current_operator_baseline.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(capture_path.read_text(encoding="utf-8")) == [
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
    ]


def test_current_operator_baseline_forwards_retry_seams_to_child_baselines(tmp_path: Path) -> None:
    capture_path = tmp_path / "baseline_capture.json"

    def _helper(name: str, retry_var_prefix: str) -> Path:
        helper = tmp_path / f"{name}.py"
        _write_executable(
            helper,
            f"""#!/usr/bin/env python3
import json, os
from pathlib import Path
capture = Path({str(capture_path)!r})
rows = json.loads(capture.read_text(encoding="utf-8")) if capture.exists() else []
rows.append({{
    "name": {name!r},
    "retry_count": os.environ.get("{retry_var_prefix}_DOCKER_RETRY_COUNT"),
    "retry_delay": os.environ.get("{retry_var_prefix}_DOCKER_RETRY_DELAY_SEC"),
    "permission_artifact_name": os.environ.get("{retry_var_prefix}_PERMISSION_ARTIFACT_NAME"),
    "permission_summary_name": os.environ.get("{retry_var_prefix}_PERMISSION_SUMMARY_NAME"),
}})
capture.write_text(json.dumps(rows), encoding="utf-8")
raise SystemExit(0)
""",
        )
        return helper

    env = os.environ.copy()
    env["VULD_CURRENT_BASELINE_NO_DOCKER_HELPER"] = str(_helper("no_docker", "VULD_NO_DOCKER_BASELINE"))
    env["VULD_CURRENT_BASELINE_MEASURED_HELPER"] = str(_helper("measured", "VULD_MEASURED_BASELINE"))
    env["VULD_CURRENT_BASELINE_SUPPORT_HELPER"] = str(_helper("support", "VULD_SUPPORT_BASELINE"))
    env["VULD_CURRENT_BASELINE_DOCKER_POSITIVE_HELPER"] = str(_helper("docker_positive", "VULD_DOCKER_POSITIVE_BASELINE"))
    env["VULD_CURRENT_BASELINE_HELPER_REGRESSION"] = str(_helper("helper_regression", "VULD_HELPER_REGRESSION_UNUSED"))
    env["VULD_CURRENT_BASELINE_PERMISSION_ARTIFACT_NAME"] = "current_baseline_permission_marker.txt"
    env["VULD_CURRENT_BASELINE_PERMISSION_SUMMARY_NAME"] = "current_baseline_permission_summary.json"
    env["VULD_CURRENT_BASELINE_DOCKER_RETRY_COUNT"] = "4"
    env["VULD_CURRENT_BASELINE_DOCKER_RETRY_DELAY_SEC"] = "0"

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_current_operator_baseline.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    rows = json.loads(capture_path.read_text(encoding="utf-8"))
    assert rows[:4] == [
        {"name": "no_docker", "retry_count": None, "retry_delay": None, "permission_artifact_name": "current_baseline_permission_marker.txt", "permission_summary_name": "current_baseline_permission_summary.json"},
        {"name": "measured", "retry_count": "4", "retry_delay": "0", "permission_artifact_name": "current_baseline_permission_marker.txt", "permission_summary_name": "current_baseline_permission_summary.json"},
        {"name": "support", "retry_count": "4", "retry_delay": "0", "permission_artifact_name": "current_baseline_permission_marker.txt", "permission_summary_name": "current_baseline_permission_summary.json"},
        {"name": "docker_positive", "retry_count": "4", "retry_delay": "0", "permission_artifact_name": "current_baseline_permission_marker.txt", "permission_summary_name": "current_baseline_permission_summary.json"},
    ]
