from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_no_docker_operator_baseline_supports_helper_overrides(tmp_path: Path) -> None:
    capture_path = tmp_path / "calls.json"

    def _helper(name: str) -> Path:
        helper = tmp_path / f"{name}.sh"
        _write_executable(
            helper,
            f"""#!/usr/bin/env python3
import json
import os
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
    env["VULD_NO_DOCKER_BASELINE_FOCUSED_HELPER"] = str(_helper("focused"))
    env["VULD_NO_DOCKER_BASELINE_LOW_COST_HELPER"] = str(_helper("low_cost"))
    env["VULD_NO_DOCKER_BASELINE_MATRIX_HELPER"] = str(_helper("matrix"))
    env["VULD_NO_DOCKER_BASELINE_BLOCKED_HELPER"] = str(_helper("blocked"))

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_no_docker_operator_baseline.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "[NO-DOCKER] completed" in completed.stdout
    assert json.loads(capture_path.read_text(encoding="utf-8")) == ["focused", "low_cost", "matrix", "blocked"]


def test_no_docker_operator_baseline_supports_sequence_helper_override(tmp_path: Path) -> None:
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
    env["VULD_NO_DOCKER_BASELINE_SEQUENCE_HELPER"] = str(sequence_helper)
    env["VULD_NO_DOCKER_BASELINE_FOCUSED_HELPER"] = "/tmp/focused_helper"
    env["VULD_NO_DOCKER_BASELINE_LOW_COST_HELPER"] = "/tmp/low_cost_helper"
    env["VULD_NO_DOCKER_BASELINE_PRESET_HELPER"] = "/tmp/preset_helper"
    env["VULD_NO_DOCKER_BASELINE_NAMED_MATRIX_HELPER"] = "/tmp/named_matrix_helper"
    env["VULD_NO_DOCKER_BASELINE_MATRIX_HELPER"] = "/tmp/matrix_helper"
    env["VULD_NO_DOCKER_BASELINE_BLOCKED_HELPER"] = "/tmp/blocked_helper"
    env["VULD_NO_DOCKER_BASELINE_MATRIX_CASE_A"] = "alpha-case"
    env["VULD_NO_DOCKER_BASELINE_MATRIX_CASE_B"] = "beta-case"

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_no_docker_operator_baseline.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(capture_path.read_text(encoding="utf-8")) == [
        "NO-DOCKER",
        "focused regression slice",
        "/tmp/focused_helper",
        "--",
        "low-cost validation lanes",
        "/tmp/low_cost_helper",
        "--",
        "repeatability + matrix preview",
        "/tmp/preset_helper",
        "build_matrix_pair_case_specs",
        "alpha-case",
        "beta-case",
        "--",
        "blocked/no-op support rehearsal",
        "/tmp/blocked_helper",
    ]


def test_no_docker_operator_baseline_supports_preset_helper_override(tmp_path: Path) -> None:
    capture_path = tmp_path / "calls.json"
    preset_helper = tmp_path / "preset.py"
    focused_helper = tmp_path / "focused.py"
    low_cost_helper = tmp_path / "low_cost.py"
    blocked_helper = tmp_path / "blocked.py"

    for helper in (focused_helper, low_cost_helper, blocked_helper):
        _write_executable(
            helper,
            """#!/usr/bin/env python3
raise SystemExit(0)
""",
        )

    _write_executable(
        preset_helper,
        f"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
payload = {{
    "argv": sys.argv[1:],
    "env": {{
        "VULD_NAMED_PRESET_TARGET_HELPER": os.environ.get("VULD_NAMED_PRESET_TARGET_HELPER"),
        "VULD_NAMED_PRESET_LOG_PREFIX": os.environ.get("VULD_NAMED_PRESET_LOG_PREFIX"),
    }},
}}
Path({str(capture_path)!r}).write_text(json.dumps(payload), encoding='utf-8')
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_NO_DOCKER_BASELINE_PRESET_HELPER"] = str(preset_helper)
    env["VULD_NO_DOCKER_BASELINE_NAMED_MATRIX_HELPER"] = "/tmp/named_matrix_helper"
    env["VULD_NO_DOCKER_BASELINE_MATRIX_CASE_A"] = "alpha-case"
    env["VULD_NO_DOCKER_BASELINE_MATRIX_CASE_B"] = "beta-case"
    env["VULD_NO_DOCKER_BASELINE_FOCUSED_HELPER"] = str(focused_helper)
    env["VULD_NO_DOCKER_BASELINE_LOW_COST_HELPER"] = str(low_cost_helper)
    env["VULD_NO_DOCKER_BASELINE_BLOCKED_HELPER"] = str(blocked_helper)

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_no_docker_operator_baseline.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(capture_path.read_text(encoding="utf-8"))
    assert payload["argv"] == ["build_matrix_pair_case_specs", "alpha-case", "beta-case"]
    assert payload["env"] == {
        "VULD_NAMED_PRESET_TARGET_HELPER": "/tmp/named_matrix_helper",
        "VULD_NAMED_PRESET_LOG_PREFIX": "NO-DOCKER-MATRIX",
    }


def test_no_docker_operator_baseline_supports_named_matrix_helper_override(tmp_path: Path) -> None:
    capture_path = tmp_path / "calls.json"
    named_matrix_helper = tmp_path / "named_matrix.py"
    focused_helper = tmp_path / "focused.py"
    low_cost_helper = tmp_path / "low_cost.py"
    blocked_helper = tmp_path / "blocked.py"

    for helper in (focused_helper, low_cost_helper, blocked_helper):
        _write_executable(
            helper,
            """#!/usr/bin/env python3
raise SystemExit(0)
""",
        )

    _write_executable(
        named_matrix_helper,
        f"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
payload = {{
    "argv": sys.argv[1:],
    "env": {{
        "VULD_NAMED_MATRIX_HELPER": os.environ.get("VULD_NAMED_MATRIX_HELPER"),
        "VULD_NAMED_MATRIX_PYTHON_BIN": os.environ.get("VULD_NAMED_MATRIX_PYTHON_BIN"),
        "VULD_NAMED_MATRIX_CASES_ROOT": os.environ.get("VULD_NAMED_MATRIX_CASES_ROOT"),
        "VULD_NAMED_MATRIX_OUTPUT_ROOT": os.environ.get("VULD_NAMED_MATRIX_OUTPUT_ROOT"),
        "VULD_NAMED_MATRIX_MODE": os.environ.get("VULD_NAMED_MATRIX_MODE"),
        "VULD_NAMED_MATRIX_ATTEMPTS": os.environ.get("VULD_NAMED_MATRIX_ATTEMPTS"),
        "VULD_NAMED_MATRIX_NO_SNAPSHOT": os.environ.get("VULD_NAMED_MATRIX_NO_SNAPSHOT"),
        "VULD_NAMED_MATRIX_ALLOW_REPEAT_FAILURE_WITH_REPORT": os.environ.get("VULD_NAMED_MATRIX_ALLOW_REPEAT_FAILURE_WITH_REPORT"),
        "VULD_NAMED_MATRIX_PERMISSION_ARTIFACT_NAME": os.environ.get("VULD_NAMED_MATRIX_PERMISSION_ARTIFACT_NAME"),
        "VULD_NAMED_MATRIX_PERMISSION_SUMMARY_NAME": os.environ.get("VULD_NAMED_MATRIX_PERMISSION_SUMMARY_NAME"),
        "VULD_NAMED_MATRIX_DOCKER_RETRY_COUNT": os.environ.get("VULD_NAMED_MATRIX_DOCKER_RETRY_COUNT"),
        "VULD_NAMED_MATRIX_DOCKER_RETRY_DELAY_SEC": os.environ.get("VULD_NAMED_MATRIX_DOCKER_RETRY_DELAY_SEC"),
        "VULD_NAMED_MATRIX_REPEAT_HELPER": os.environ.get("VULD_NAMED_MATRIX_REPEAT_HELPER"),
    }},
}}
Path({str(capture_path)!r}).write_text(json.dumps(payload), encoding="utf-8")
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_NO_DOCKER_BASELINE_NAMED_MATRIX_HELPER"] = str(named_matrix_helper)
    env["VULD_NO_DOCKER_BASELINE_MATRIX_HELPER"] = "/tmp/matrix_helper"
    env["VULD_NO_DOCKER_BASELINE_PYTHON_BIN"] = "/tmp/fake-python"
    env["VULD_NO_DOCKER_BASELINE_CASES_ROOT"] = "/tmp/fake-cases"
    env["VULD_NO_DOCKER_BASELINE_MATRIX_OUTPUT_ROOT"] = "/tmp/fake-output"
    env["VULD_NO_DOCKER_BASELINE_MATRIX_MODE"] = "diverse"
    env["VULD_NO_DOCKER_BASELINE_MATRIX_ATTEMPTS"] = "5"
    env["VULD_NO_DOCKER_BASELINE_MATRIX_NO_SNAPSHOT"] = "1"
    env["VULD_NO_DOCKER_BASELINE_MATRIX_ALLOW_REPEAT_FAILURE_WITH_REPORT"] = "1"
    env["VULD_NO_DOCKER_BASELINE_PERMISSION_ARTIFACT_NAME"] = "no_docker_permission_marker.txt"
    env["VULD_NO_DOCKER_BASELINE_PERMISSION_SUMMARY_NAME"] = "no_docker_permission_summary.json"
    env["VULD_NO_DOCKER_BASELINE_MATRIX_DOCKER_RETRY_COUNT"] = "3"
    env["VULD_NO_DOCKER_BASELINE_MATRIX_DOCKER_RETRY_DELAY_SEC"] = "0"
    env["VULD_NO_DOCKER_BASELINE_REPEAT_HELPER"] = "/tmp/repeat_helper"
    env["VULD_NO_DOCKER_BASELINE_MATRIX_CASE_A"] = "alpha-case"
    env["VULD_NO_DOCKER_BASELINE_MATRIX_CASE_B"] = "beta-case"
    env["VULD_NO_DOCKER_BASELINE_FOCUSED_HELPER"] = str(focused_helper)
    env["VULD_NO_DOCKER_BASELINE_LOW_COST_HELPER"] = str(low_cost_helper)
    env["VULD_NO_DOCKER_BASELINE_BLOCKED_HELPER"] = str(blocked_helper)

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_no_docker_operator_baseline.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(capture_path.read_text(encoding="utf-8"))
    assert payload["argv"] == ["alpha-case", "beta-case"]
    assert payload["env"] == {
        "VULD_NAMED_MATRIX_HELPER": "/tmp/matrix_helper",
        "VULD_NAMED_MATRIX_PYTHON_BIN": "/tmp/fake-python",
        "VULD_NAMED_MATRIX_CASES_ROOT": "/tmp/fake-cases",
        "VULD_NAMED_MATRIX_OUTPUT_ROOT": "/tmp/fake-output",
        "VULD_NAMED_MATRIX_MODE": "diverse",
        "VULD_NAMED_MATRIX_ATTEMPTS": "5",
        "VULD_NAMED_MATRIX_NO_SNAPSHOT": "1",
        "VULD_NAMED_MATRIX_ALLOW_REPEAT_FAILURE_WITH_REPORT": "1",
        "VULD_NAMED_MATRIX_PERMISSION_ARTIFACT_NAME": "no_docker_permission_marker.txt",
        "VULD_NAMED_MATRIX_PERMISSION_SUMMARY_NAME": "no_docker_permission_summary.json",
        "VULD_NAMED_MATRIX_DOCKER_RETRY_COUNT": "3",
        "VULD_NAMED_MATRIX_DOCKER_RETRY_DELAY_SEC": "0",
        "VULD_NAMED_MATRIX_REPEAT_HELPER": "/tmp/repeat_helper",
    }


def test_no_docker_operator_baseline_forwards_permission_artifact_to_blocked_helper(tmp_path: Path) -> None:
    capture_path = tmp_path / "blocked_capture.json"

    def _helper(name: str) -> Path:
        helper = tmp_path / f"{name}.py"
        _write_executable(
            helper,
            """#!/usr/bin/env python3
raise SystemExit(0)
""",
        )
        return helper

    blocked_helper = tmp_path / "blocked.py"
    _write_executable(
        blocked_helper,
        f"""#!/usr/bin/env python3
import json, os
from pathlib import Path
Path({str(capture_path)!r}).write_text(json.dumps({{
    "permission_artifact_name": os.environ.get("VULD_BLOCKED_NOOP_PERMISSION_ARTIFACT_NAME"),
    "permission_summary_name": os.environ.get("VULD_BLOCKED_NOOP_PERMISSION_SUMMARY_NAME"),
    "retry_count": os.environ.get("VULD_BLOCKED_NOOP_DOCKER_RETRY_COUNT"),
    "retry_delay": os.environ.get("VULD_BLOCKED_NOOP_DOCKER_RETRY_DELAY_SEC"),
}}), encoding="utf-8")
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_NO_DOCKER_BASELINE_FOCUSED_HELPER"] = str(_helper("focused"))
    env["VULD_NO_DOCKER_BASELINE_LOW_COST_HELPER"] = str(_helper("low_cost"))
    env["VULD_NO_DOCKER_BASELINE_MATRIX_HELPER"] = str(_helper("matrix"))
    env["VULD_NO_DOCKER_BASELINE_BLOCKED_HELPER"] = str(blocked_helper)
    env["VULD_NO_DOCKER_BASELINE_PERMISSION_ARTIFACT_NAME"] = "no_docker_permission_marker.txt"
    env["VULD_NO_DOCKER_BASELINE_PERMISSION_SUMMARY_NAME"] = "no_docker_permission_summary.json"
    env["VULD_NO_DOCKER_BASELINE_BLOCKED_DOCKER_RETRY_COUNT"] = "4"
    env["VULD_NO_DOCKER_BASELINE_BLOCKED_DOCKER_RETRY_DELAY_SEC"] = "0"

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_no_docker_operator_baseline.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(capture_path.read_text(encoding="utf-8")) == {
        "permission_artifact_name": "no_docker_permission_marker.txt",
        "permission_summary_name": "no_docker_permission_summary.json",
        "retry_count": "4",
        "retry_delay": "0",
    }
