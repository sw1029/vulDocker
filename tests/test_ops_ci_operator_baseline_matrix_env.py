from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_operator_baseline_matrix_env_exports_measured_and_no_docker_defaults_and_overrides(tmp_path: Path) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_operator_baseline_matrix_env.sh")!r}

export VULD_MEASURED_BASELINE_PYTHON_BIN=/tmp/measured_python
export VULD_MEASURED_BASELINE_CASES_ROOT=/tmp/measured_cases
export VULD_MEASURED_BASELINE_OUTPUT_ROOT=/tmp/measured_out
export VULD_MEASURED_BASELINE_MODE=diverse
export VULD_MEASURED_BASELINE_ATTEMPTS=5
export VULD_MEASURED_BASELINE_NO_SNAPSHOT=1
export VULD_MEASURED_BASELINE_ALLOW_REPEAT_FAILURE_WITH_REPORT=1
export VULD_MEASURED_BASELINE_PERMISSION_ARTIFACT_NAME=measured_permission_marker.txt
export VULD_MEASURED_BASELINE_PERMISSION_SUMMARY_NAME=measured_permission_summary.json
export VULD_MEASURED_BASELINE_DOCKER_RETRY_COUNT=4
export VULD_MEASURED_BASELINE_DOCKER_RETRY_DELAY_SEC=0
export VULD_MEASURED_BASELINE_REPEAT_HELPER=/tmp/measured_repeat
measured_baseline_matrix_export_env /tmp/matrix_helper /tmp/named_matrix_helper
export MEASURED_JSON=$(python - <<'PY'
import json, os
print(json.dumps({{
  "helper": os.environ["VULD_NAMED_MATRIX_HELPER"],
  "python_bin": os.environ["VULD_NAMED_MATRIX_PYTHON_BIN"],
  "cases_root": os.environ["VULD_NAMED_MATRIX_CASES_ROOT"],
  "output_root": os.environ["VULD_NAMED_MATRIX_OUTPUT_ROOT"],
  "mode": os.environ["VULD_NAMED_MATRIX_MODE"],
  "attempts": os.environ["VULD_NAMED_MATRIX_ATTEMPTS"],
  "no_snapshot": os.environ["VULD_NAMED_MATRIX_NO_SNAPSHOT"],
  "allow_repeat_failure_with_report": os.environ["VULD_NAMED_MATRIX_ALLOW_REPEAT_FAILURE_WITH_REPORT"],
  "permission_artifact_name": os.environ["VULD_NAMED_MATRIX_PERMISSION_ARTIFACT_NAME"],
  "permission_summary_name": os.environ["VULD_NAMED_MATRIX_PERMISSION_SUMMARY_NAME"],
  "docker_retry_count": os.environ["VULD_NAMED_MATRIX_DOCKER_RETRY_COUNT"],
  "docker_retry_delay_sec": os.environ["VULD_NAMED_MATRIX_DOCKER_RETRY_DELAY_SEC"],
  "repeat_helper": os.environ["VULD_NAMED_MATRIX_REPEAT_HELPER"],
  "preset_target_helper": os.environ["VULD_NAMED_PRESET_TARGET_HELPER"],
  "preset_log_prefix": os.environ["VULD_NAMED_PRESET_LOG_PREFIX"],
}}))
PY
)

unset VULD_NAMED_MATRIX_REPEAT_HELPER || true
export VULD_NO_DOCKER_BASELINE_PYTHON_BIN=/tmp/no_docker_python
export VULD_NO_DOCKER_BASELINE_CASES_ROOT=/tmp/no_docker_cases
export VULD_NO_DOCKER_BASELINE_MATRIX_OUTPUT_ROOT=/tmp/no_docker_out
export VULD_NO_DOCKER_BASELINE_MATRIX_MODE=deterministic
export VULD_NO_DOCKER_BASELINE_MATRIX_ATTEMPTS=3
export VULD_NO_DOCKER_BASELINE_MATRIX_NO_SNAPSHOT=0
export VULD_NO_DOCKER_BASELINE_MATRIX_ALLOW_REPEAT_FAILURE_WITH_REPORT=0
export VULD_NO_DOCKER_BASELINE_PERMISSION_ARTIFACT_NAME=no_docker_permission_marker.txt
export VULD_NO_DOCKER_BASELINE_PERMISSION_SUMMARY_NAME=no_docker_permission_summary.json
export VULD_NO_DOCKER_BASELINE_MATRIX_DOCKER_RETRY_COUNT=2
export VULD_NO_DOCKER_BASELINE_MATRIX_DOCKER_RETRY_DELAY_SEC=1
export VULD_NO_DOCKER_BASELINE_REPEAT_HELPER=/tmp/no_docker_repeat
no_docker_baseline_matrix_export_env /tmp/no_docker_matrix_helper /tmp/no_docker_named_matrix_helper
export NO_DOCKER_JSON=$(python - <<'PY'
import json, os
print(json.dumps({{
  "helper": os.environ["VULD_NAMED_MATRIX_HELPER"],
  "python_bin": os.environ["VULD_NAMED_MATRIX_PYTHON_BIN"],
  "cases_root": os.environ["VULD_NAMED_MATRIX_CASES_ROOT"],
  "output_root": os.environ["VULD_NAMED_MATRIX_OUTPUT_ROOT"],
  "mode": os.environ["VULD_NAMED_MATRIX_MODE"],
  "attempts": os.environ["VULD_NAMED_MATRIX_ATTEMPTS"],
  "no_snapshot": os.environ["VULD_NAMED_MATRIX_NO_SNAPSHOT"],
  "allow_repeat_failure_with_report": os.environ["VULD_NAMED_MATRIX_ALLOW_REPEAT_FAILURE_WITH_REPORT"],
  "permission_artifact_name": os.environ["VULD_NAMED_MATRIX_PERMISSION_ARTIFACT_NAME"],
  "permission_summary_name": os.environ["VULD_NAMED_MATRIX_PERMISSION_SUMMARY_NAME"],
  "docker_retry_count": os.environ["VULD_NAMED_MATRIX_DOCKER_RETRY_COUNT"],
  "docker_retry_delay_sec": os.environ["VULD_NAMED_MATRIX_DOCKER_RETRY_DELAY_SEC"],
  "repeat_helper": os.environ["VULD_NAMED_MATRIX_REPEAT_HELPER"],
  "preset_target_helper": os.environ["VULD_NAMED_PRESET_TARGET_HELPER"],
  "preset_log_prefix": os.environ["VULD_NAMED_PRESET_LOG_PREFIX"],
}}))
PY
)

python - <<'PY' > {str(capture)!r}
import json, os
print(json.dumps({{
  "measured": json.loads(os.environ["MEASURED_JSON"]),
  "no_docker": json.loads(os.environ["NO_DOCKER_JSON"]),
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
    payload = json.loads(capture.read_text(encoding="utf-8"))
    assert payload["measured"] == {
        "helper": "/tmp/matrix_helper",
        "python_bin": "/tmp/measured_python",
        "cases_root": "/tmp/measured_cases",
        "output_root": "/tmp/measured_out",
        "mode": "diverse",
        "attempts": "5",
        "no_snapshot": "1",
        "allow_repeat_failure_with_report": "1",
        "permission_artifact_name": "measured_permission_marker.txt",
        "permission_summary_name": "measured_permission_summary.json",
        "docker_retry_count": "4",
        "docker_retry_delay_sec": "0",
        "repeat_helper": "/tmp/measured_repeat",
        "preset_target_helper": "/tmp/named_matrix_helper",
        "preset_log_prefix": "MEASURED-MATRIX",
    }
    assert payload["no_docker"] == {
        "helper": "/tmp/no_docker_matrix_helper",
        "python_bin": "/tmp/no_docker_python",
        "cases_root": "/tmp/no_docker_cases",
        "output_root": "/tmp/no_docker_out",
        "mode": "deterministic",
        "attempts": "3",
        "no_snapshot": "0",
        "allow_repeat_failure_with_report": "0",
        "permission_artifact_name": "no_docker_permission_marker.txt",
        "permission_summary_name": "no_docker_permission_summary.json",
        "docker_retry_count": "2",
        "docker_retry_delay_sec": "1",
        "repeat_helper": "/tmp/no_docker_repeat",
        "preset_target_helper": "/tmp/no_docker_named_matrix_helper",
        "preset_log_prefix": "NO-DOCKER-MATRIX",
    }
