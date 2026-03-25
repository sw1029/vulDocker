from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_repeatability_chain_runtime_env_supports_defaults(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    capture = tmp_path / "capture.json"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_repeatability_chain_runtime_env.sh")!r}
repeatability_chain_resolve_runtime_env \
  VULD_TEST \
  REPEAT_ATTEMPTS \
  ALLOW_FAILURE_WITH_REPORT \
  RUN_DIRS_FILE \
  OUTPUT_PREFIX \
  LOG_PREFIX \
  REPORT_NAME \
  DOCKER_RETRY_COUNT \
  DOCKER_RETRY_DELAY_SEC \
  PERMISSION_ARTIFACT_NAME
export REPEAT_ATTEMPTS ALLOW_FAILURE_WITH_REPORT RUN_DIRS_FILE OUTPUT_PREFIX LOG_PREFIX REPORT_NAME DOCKER_RETRY_COUNT DOCKER_RETRY_DELAY_SEC PERMISSION_ARTIFACT_NAME
python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "repeat_attempts": os.environ["REPEAT_ATTEMPTS"],
  "allow_failure_with_report": os.environ["ALLOW_FAILURE_WITH_REPORT"],
  "run_dirs_file": os.environ["RUN_DIRS_FILE"],
  "output_prefix": os.environ["OUTPUT_PREFIX"],
  "log_prefix": os.environ["LOG_PREFIX"],
  "report_name": os.environ["REPORT_NAME"],
  "docker_retry_count": os.environ["DOCKER_RETRY_COUNT"],
  "docker_retry_delay_sec": os.environ["DOCKER_RETRY_DELAY_SEC"],
  "permission_artifact_name": os.environ["PERMISSION_ARTIFACT_NAME"],
}}))
PY
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(capture.read_text(encoding="utf-8")) == {
        "repeat_attempts": "2",
        "allow_failure_with_report": "0",
        "run_dirs_file": "",
        "output_prefix": "repeat",
        "log_prefix": "REPEAT",
        "report_name": "repeatability_report.json",
        "docker_retry_count": "2",
        "docker_retry_delay_sec": "1",
        "permission_artifact_name": "docker_permission_artifact.txt",
    }


def test_repeatability_chain_runtime_env_supports_overrides(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    capture = tmp_path / "capture.json"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_repeatability_chain_runtime_env.sh")!r}
export VULD_TEST_ATTEMPTS=5
export VULD_TEST_ALLOW_FAILURE_WITH_REPORT=1
export VULD_TEST_RUN_DIRS_FILE=/tmp/custom_run_dirs.txt
export VULD_TEST_OUTPUT_PREFIX=custom_repeat
export VULD_TEST_LOG_PREFIX=CUSTOM
export VULD_TEST_REPORT_NAME=custom_repeatability_report.json
export VULD_TEST_DOCKER_RETRY_COUNT=4
export VULD_TEST_DOCKER_RETRY_DELAY_SEC=0
export VULD_TEST_PERMISSION_ARTIFACT_NAME=custom_permission_marker.txt
repeatability_chain_resolve_runtime_env \
  VULD_TEST \
  REPEAT_ATTEMPTS \
  ALLOW_FAILURE_WITH_REPORT \
  RUN_DIRS_FILE \
  OUTPUT_PREFIX \
  LOG_PREFIX \
  REPORT_NAME \
  DOCKER_RETRY_COUNT \
  DOCKER_RETRY_DELAY_SEC \
  PERMISSION_ARTIFACT_NAME
export REPEAT_ATTEMPTS ALLOW_FAILURE_WITH_REPORT RUN_DIRS_FILE OUTPUT_PREFIX LOG_PREFIX REPORT_NAME DOCKER_RETRY_COUNT DOCKER_RETRY_DELAY_SEC PERMISSION_ARTIFACT_NAME
python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "repeat_attempts": os.environ["REPEAT_ATTEMPTS"],
  "allow_failure_with_report": os.environ["ALLOW_FAILURE_WITH_REPORT"],
  "run_dirs_file": os.environ["RUN_DIRS_FILE"],
  "output_prefix": os.environ["OUTPUT_PREFIX"],
  "log_prefix": os.environ["LOG_PREFIX"],
  "report_name": os.environ["REPORT_NAME"],
  "docker_retry_count": os.environ["DOCKER_RETRY_COUNT"],
  "docker_retry_delay_sec": os.environ["DOCKER_RETRY_DELAY_SEC"],
  "permission_artifact_name": os.environ["PERMISSION_ARTIFACT_NAME"],
}}))
PY
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(capture.read_text(encoding="utf-8")) == {
        "repeat_attempts": "5",
        "allow_failure_with_report": "1",
        "run_dirs_file": "/tmp/custom_run_dirs.txt",
        "output_prefix": "custom_repeat",
        "log_prefix": "CUSTOM",
        "report_name": "custom_repeatability_report.json",
        "docker_retry_count": "4",
        "docker_retry_delay_sec": "0",
        "permission_artifact_name": "custom_permission_marker.txt",
    }
