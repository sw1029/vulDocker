from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_operator_named_case_env_exports_direct_and_support_defaults_and_overrides(tmp_path: Path) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_operator_named_case_env.sh")!r}

export VULD_SAMPLE_DIRECT_PYTHON_BIN=/tmp/direct_python
export VULD_SAMPLE_DIRECT_CASES_ROOT=/tmp/direct_cases
export VULD_SAMPLE_DIRECT_OUTPUT_ROOT=/tmp/direct_out
export VULD_SAMPLE_DIRECT_MODE=diverse
export VULD_SAMPLE_DIRECT_NO_SNAPSHOT=0
operator_prefix_export_direct_named_env VULD_SAMPLE_DIRECT /unused/direct_cases /unused/direct_out /tmp/direct_helper /tmp/named_direct_helper DIRECT
export DIRECT_JSON=$(python - <<'PY'
import json, os
print(json.dumps({{
  "helper": os.environ["VULD_NAMED_DIRECT_HELPER"],
  "python_bin": os.environ["VULD_NAMED_DIRECT_PYTHON_BIN"],
  "cases_root": os.environ["VULD_NAMED_DIRECT_CASES_ROOT"],
  "output_root": os.environ["VULD_NAMED_DIRECT_OUTPUT_ROOT"],
  "mode": os.environ["VULD_NAMED_DIRECT_MODE"],
  "no_snapshot": os.environ["VULD_NAMED_DIRECT_NO_SNAPSHOT"],
  "preset_target_helper": os.environ["VULD_NAMED_PRESET_TARGET_HELPER"],
  "preset_log_prefix": os.environ["VULD_NAMED_PRESET_LOG_PREFIX"],
}}))
PY
)

export VULD_SAMPLE_SUPPORT_PYTHON_BIN=/tmp/support_python
export VULD_SAMPLE_SUPPORT_CASES_ROOT=/tmp/support_cases
export VULD_SAMPLE_SUPPORT_OUTPUT_ROOT=/tmp/support_out
export VULD_SAMPLE_SUPPORT_MODE=deterministic
export VULD_SAMPLE_SUPPORT_ATTEMPTS=5
export VULD_SAMPLE_SUPPORT_REVIEW_ONLY=1
export VULD_SAMPLE_SUPPORT_NO_SNAPSHOT=1
export VULD_SAMPLE_SUPPORT_DOCKER_RETRY_COUNT=4
export VULD_SAMPLE_SUPPORT_DOCKER_RETRY_DELAY_SEC=0
export VULD_SAMPLE_SUPPORT_PERMISSION_ARTIFACT_NAME=sample_permission_marker.txt
export VULD_SAMPLE_SUPPORT_PERMISSION_SUMMARY_NAME=sample_permission_summary.json
export VULD_SAMPLE_SUPPORT_REVIEW_OUTPUT_NAME=review.json
operator_prefix_export_support_named_env VULD_SAMPLE_SUPPORT /unused/support_cases /unused/support_out /tmp/support_helper /tmp/named_support_helper SUPPORT
export SUPPORT_JSON=$(python - <<'PY'
import json, os
print(json.dumps({{
  "helper": os.environ["VULD_NAMED_SUPPORT_HELPER"],
  "python_bin": os.environ["VULD_NAMED_SUPPORT_PYTHON_BIN"],
  "cases_root": os.environ["VULD_NAMED_SUPPORT_CASES_ROOT"],
  "output_root": os.environ["VULD_NAMED_SUPPORT_OUTPUT_ROOT"],
  "mode": os.environ["VULD_NAMED_SUPPORT_MODE"],
  "attempts": os.environ["VULD_NAMED_SUPPORT_ATTEMPTS"],
  "review_only": os.environ["VULD_NAMED_SUPPORT_REVIEW_ONLY"],
  "no_snapshot": os.environ["VULD_NAMED_SUPPORT_NO_SNAPSHOT"],
  "permission_artifact_name": os.environ["VULD_NAMED_SUPPORT_PERMISSION_ARTIFACT_NAME"],
  "permission_summary_name": os.environ["VULD_NAMED_SUPPORT_PERMISSION_SUMMARY_NAME"],
  "docker_retry_count": os.environ["VULD_NAMED_SUPPORT_DOCKER_RETRY_COUNT"],
  "docker_retry_delay_sec": os.environ["VULD_NAMED_SUPPORT_DOCKER_RETRY_DELAY_SEC"],
  "review_output_name": os.environ["VULD_NAMED_SUPPORT_REVIEW_OUTPUT_NAME"],
  "preset_target_helper": os.environ["VULD_NAMED_PRESET_TARGET_HELPER"],
  "preset_log_prefix": os.environ["VULD_NAMED_PRESET_LOG_PREFIX"],
}}))
PY
)

python - <<'PY' > {str(capture)!r}
import json, os
print(json.dumps({{
  "direct": json.loads(os.environ["DIRECT_JSON"]),
  "support": json.loads(os.environ["SUPPORT_JSON"]),
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
    assert payload["direct"] == {
        "helper": "/tmp/direct_helper",
        "python_bin": "/tmp/direct_python",
        "cases_root": "/tmp/direct_cases",
        "output_root": "/tmp/direct_out",
        "mode": "diverse",
        "no_snapshot": "0",
        "preset_target_helper": "/tmp/named_direct_helper",
        "preset_log_prefix": "DIRECT",
    }
    assert payload["support"] == {
        "helper": "/tmp/support_helper",
        "python_bin": "/tmp/support_python",
        "cases_root": "/tmp/support_cases",
        "output_root": "/tmp/support_out",
        "mode": "deterministic",
        "attempts": "5",
        "review_only": "1",
        "no_snapshot": "1",
        "permission_artifact_name": "sample_permission_marker.txt",
        "permission_summary_name": "sample_permission_summary.json",
        "docker_retry_count": "4",
        "docker_retry_delay_sec": "0",
        "review_output_name": "review.json",
        "preset_target_helper": "/tmp/named_support_helper",
        "preset_log_prefix": "SUPPORT",
    }
