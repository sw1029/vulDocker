from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_docker_positive_operator_baseline_supports_helper_overrides(tmp_path: Path) -> None:
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
    env["VULD_DOCKER_POSITIVE_BASELINE_DIRECT_HELPER"] = str(_helper("direct"))
    env["VULD_DOCKER_POSITIVE_BASELINE_PROMOTION_HELPER"] = str(_helper("promotion"))
    env["VULD_DOCKER_POSITIVE_BASELINE_DOCKER_RETRY_COUNT"] = "4"
    env["VULD_DOCKER_POSITIVE_BASELINE_DOCKER_RETRY_DELAY_SEC"] = "0"

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_docker_positive_operator_baseline.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "[DOCKER-POSITIVE] completed" in completed.stdout
    assert json.loads(capture_path.read_text(encoding="utf-8")) == ["direct", "promotion"]


def test_docker_positive_operator_baseline_supports_sequence_helper_override(tmp_path: Path) -> None:
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
    env["VULD_DOCKER_POSITIVE_BASELINE_SEQUENCE_HELPER"] = str(sequence_helper)
    env["VULD_DOCKER_POSITIVE_BASELINE_DIRECT_HELPER"] = "/tmp/direct_helper"
    env["VULD_DOCKER_POSITIVE_BASELINE_PROMOTION_HELPER"] = "/tmp/promotion_helper"
    env["VULD_DOCKER_POSITIVE_BASELINE_DOCKER_RETRY_COUNT"] = "4"
    env["VULD_DOCKER_POSITIVE_BASELINE_DOCKER_RETRY_DELAY_SEC"] = "0"

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_docker_positive_operator_baseline.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(capture_path.read_text(encoding="utf-8")) == [
        "DOCKER-POSITIVE",
        "direct rerun baseline",
        "/tmp/direct_helper",
        "--",
        "promotion-check baseline",
        "/tmp/promotion_helper",
    ]


def test_docker_positive_operator_baseline_forwards_retry_seams_to_promotion_helper(tmp_path: Path) -> None:
    capture_path = tmp_path / "promotion_capture.json"
    direct_helper = tmp_path / "direct.py"
    promotion_helper = tmp_path / "promotion.py"

    _write_executable(
        direct_helper,
        """#!/usr/bin/env python3
raise SystemExit(0)
""",
    )
    _write_executable(
        promotion_helper,
        f"""#!/usr/bin/env python3
import json, os
from pathlib import Path
Path({str(capture_path)!r}).write_text(json.dumps({{
    "retry_count": os.environ.get("VULD_POSITIVE_PAIR_DOCKER_RETRY_COUNT"),
    "retry_delay": os.environ.get("VULD_POSITIVE_PAIR_DOCKER_RETRY_DELAY_SEC"),
    "permission_artifact_name": os.environ.get("VULD_POSITIVE_PAIR_PERMISSION_ARTIFACT_NAME"),
    "permission_summary_name": os.environ.get("VULD_POSITIVE_PAIR_PERMISSION_SUMMARY_NAME"),
}}), encoding="utf-8")
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_DOCKER_POSITIVE_BASELINE_DIRECT_HELPER"] = str(direct_helper)
    env["VULD_DOCKER_POSITIVE_BASELINE_PROMOTION_HELPER"] = str(promotion_helper)
    env["VULD_DOCKER_POSITIVE_BASELINE_PERMISSION_ARTIFACT_NAME"] = "docker_positive_permission_marker.txt"
    env["VULD_DOCKER_POSITIVE_BASELINE_PERMISSION_SUMMARY_NAME"] = "docker_positive_permission_summary.json"
    env["VULD_DOCKER_POSITIVE_BASELINE_DOCKER_RETRY_COUNT"] = "4"
    env["VULD_DOCKER_POSITIVE_BASELINE_DOCKER_RETRY_DELAY_SEC"] = "0"

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_docker_positive_operator_baseline.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(capture_path.read_text(encoding="utf-8")) == {
        "retry_count": "4",
        "retry_delay": "0",
        "permission_artifact_name": "docker_positive_permission_marker.txt",
        "permission_summary_name": "docker_positive_permission_summary.json",
    }
