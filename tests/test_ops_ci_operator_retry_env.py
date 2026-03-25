from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_operator_retry_env_forwards_retry_pair_to_target_prefix(tmp_path: Path) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_operator_retry_env.sh")!r}
operator_retry_forward_pair 4 0 VULD_SAMPLE_TARGET
python - <<'PY' > {str(capture)!r}
import json, os
print(json.dumps({{
  "count": os.environ["VULD_SAMPLE_TARGET_DOCKER_RETRY_COUNT"],
  "delay": os.environ["VULD_SAMPLE_TARGET_DOCKER_RETRY_DELAY_SEC"],
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
        "count": "4",
        "delay": "0",
    }


def test_operator_retry_env_forwards_permission_surface_to_target_prefix(tmp_path: Path) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_operator_retry_env.sh")!r}
operator_forward_permission_surface sample_permission_marker.txt sample_permission_summary.json VULD_SAMPLE_TARGET
python - <<'PY' > {str(capture)!r}
import json, os
print(json.dumps({{
  "artifact": os.environ["VULD_SAMPLE_TARGET_PERMISSION_ARTIFACT_NAME"],
  "summary": os.environ["VULD_SAMPLE_TARGET_PERMISSION_SUMMARY_NAME"],
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
        "artifact": "sample_permission_marker.txt",
        "summary": "sample_permission_summary.json",
    }


def test_operator_retry_env_forwards_runtime_surface_to_target_prefix(tmp_path: Path) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_operator_retry_env.sh")!r}
operator_forward_runtime_surface 4 0 sample_permission_marker.txt sample_permission_summary.json VULD_SAMPLE_TARGET
python - <<'PY' > {str(capture)!r}
import json, os
print(json.dumps({{
  "count": os.environ["VULD_SAMPLE_TARGET_DOCKER_RETRY_COUNT"],
  "delay": os.environ["VULD_SAMPLE_TARGET_DOCKER_RETRY_DELAY_SEC"],
  "artifact": os.environ["VULD_SAMPLE_TARGET_PERMISSION_ARTIFACT_NAME"],
  "summary": os.environ["VULD_SAMPLE_TARGET_PERMISSION_SUMMARY_NAME"],
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
        "count": "4",
        "delay": "0",
        "artifact": "sample_permission_marker.txt",
        "summary": "sample_permission_summary.json",
    }


def test_operator_retry_env_forwards_retry_and_permission_surface_to_multiple_prefixes(tmp_path: Path) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_operator_retry_env.sh")!r}
operator_retry_forward_pair_many 4 0 VULD_ALPHA_TARGET VULD_BETA_TARGET
operator_forward_permission_surface_many sample_permission_marker.txt sample_permission_summary.json VULD_ALPHA_TARGET VULD_BETA_TARGET
python - <<'PY' > {str(capture)!r}
import json, os
print(json.dumps({{
  "alpha": {{
    "count": os.environ["VULD_ALPHA_TARGET_DOCKER_RETRY_COUNT"],
    "delay": os.environ["VULD_ALPHA_TARGET_DOCKER_RETRY_DELAY_SEC"],
    "artifact": os.environ["VULD_ALPHA_TARGET_PERMISSION_ARTIFACT_NAME"],
    "summary": os.environ["VULD_ALPHA_TARGET_PERMISSION_SUMMARY_NAME"],
  }},
  "beta": {{
    "count": os.environ["VULD_BETA_TARGET_DOCKER_RETRY_COUNT"],
    "delay": os.environ["VULD_BETA_TARGET_DOCKER_RETRY_DELAY_SEC"],
    "artifact": os.environ["VULD_BETA_TARGET_PERMISSION_ARTIFACT_NAME"],
    "summary": os.environ["VULD_BETA_TARGET_PERMISSION_SUMMARY_NAME"],
  }},
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
        "alpha": {
            "count": "4",
            "delay": "0",
            "artifact": "sample_permission_marker.txt",
            "summary": "sample_permission_summary.json",
        },
        "beta": {
            "count": "4",
            "delay": "0",
            "artifact": "sample_permission_marker.txt",
            "summary": "sample_permission_summary.json",
        },
    }
