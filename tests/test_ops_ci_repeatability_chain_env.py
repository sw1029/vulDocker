from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_export_repeatability_chain_env_exports_values_and_optional_retries(tmp_path: Path) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_repeatability_chain_env.sh")!r}
export_repeatability_chain_env \
  /tmp/fake_python \
  /tmp/fake_cases \
  /tmp/fake_output \
  diverse \
  5 \
  1 \
  1 \
  custom_permission_marker.txt \
  3 \
  0 \
  /tmp/fake_run_dirs.txt \
  TESTLOG
python - <<'PY' > {str(capture)!r}
import json, os
print(json.dumps({{
  "python_bin": os.environ["VULD_REPEAT_CHAIN_PYTHON_BIN"],
  "cases_root": os.environ["VULD_REPEAT_CHAIN_CASES_ROOT"],
  "output_root": os.environ["VULD_REPEAT_CHAIN_OUTPUT_ROOT"],
  "mode": os.environ["VULD_REPEAT_CHAIN_MODE"],
  "attempts": os.environ["VULD_REPEAT_CHAIN_ATTEMPTS"],
  "no_snapshot": os.environ["VULD_REPEAT_CHAIN_NO_SNAPSHOT"],
  "allow_failure_with_report": os.environ["VULD_REPEAT_CHAIN_ALLOW_FAILURE_WITH_REPORT"],
  "permission_artifact_name": os.environ["VULD_REPEAT_CHAIN_PERMISSION_ARTIFACT_NAME"],
  "docker_retry_count": os.environ["VULD_REPEAT_CHAIN_DOCKER_RETRY_COUNT"],
  "docker_retry_delay_sec": os.environ["VULD_REPEAT_CHAIN_DOCKER_RETRY_DELAY_SEC"],
  "run_dirs_file": os.environ["VULD_REPEAT_CHAIN_RUN_DIRS_FILE"],
  "log_prefix": os.environ["VULD_REPEAT_CHAIN_LOG_PREFIX"],
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
        "python_bin": "/tmp/fake_python",
        "cases_root": "/tmp/fake_cases",
        "output_root": "/tmp/fake_output",
        "mode": "diverse",
        "attempts": "5",
        "no_snapshot": "1",
        "allow_failure_with_report": "1",
        "permission_artifact_name": "custom_permission_marker.txt",
        "docker_retry_count": "3",
        "docker_retry_delay_sec": "0",
        "run_dirs_file": "/tmp/fake_run_dirs.txt",
        "log_prefix": "TESTLOG",
    }
