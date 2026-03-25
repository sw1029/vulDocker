from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_case_chain_entrypoint_surface_supports_runner_with_log_prefix(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    capture = tmp_path / "capture.json"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_entrypoint_surface.sh")!r}
fake_runner() {{
  export SOURCE_PREFIX="$1"
  export REPO_ROOT="$2"
  export DEFAULT_OUTPUT_ROOT="$3"
  export USAGE_TEXT="$4"
  export LOG_PREFIX="$5"
  shift 5
  python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "source_prefix": os.environ["SOURCE_PREFIX"],
  "repo_root": os.environ["REPO_ROOT"],
  "default_output_root": os.environ["DEFAULT_OUTPUT_ROOT"],
  "usage_text": os.environ["USAGE_TEXT"],
  "log_prefix": os.environ["LOG_PREFIX"],
}}))
PY
}}
case_chain_run_entrypoint_surface fake_runner VULD_TEST {str(REPO_ROOT / "ops/ci")!r} /tmp/default-out "usage: demo <case>" TESTLOG alpha-case
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
        "source_prefix": "VULD_TEST",
        "repo_root": str(REPO_ROOT),
        "default_output_root": "/tmp/default-out",
        "usage_text": "usage: demo <case>",
        "log_prefix": "TESTLOG",
    }


def test_case_chain_entrypoint_surface_supports_runner_without_log_prefix(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    capture = tmp_path / "capture.json"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_entrypoint_surface.sh")!r}
fake_runner() {{
  export SOURCE_PREFIX="$1"
  export REPO_ROOT="$2"
  export DEFAULT_OUTPUT_ROOT="$3"
  export USAGE_TEXT="$4"
  python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "source_prefix": os.environ["SOURCE_PREFIX"],
  "repo_root": os.environ["REPO_ROOT"],
  "default_output_root": os.environ["DEFAULT_OUTPUT_ROOT"],
  "usage_text": os.environ["USAGE_TEXT"],
}}))
PY
}}
case_chain_run_entrypoint_surface fake_runner VULD_TEST {str(REPO_ROOT / "ops/ci")!r} /tmp/default-out "usage: demo <case>" "" alpha-case
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
        "source_prefix": "VULD_TEST",
        "repo_root": str(REPO_ROOT),
        "default_output_root": "/tmp/default-out",
        "usage_text": "usage: demo <case>",
    }
