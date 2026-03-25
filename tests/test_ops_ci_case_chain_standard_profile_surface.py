from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_case_chain_standard_profile_surface_dispatches_runner_and_profile(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "probe.sh"
    capture = tmp_path / "capture.json"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_standard_profile_surface.sh")!r}
resolver_fn() {{
  local profile_name="$1"
  local output_var="$2"
  case "${{profile_name}}" in
    direct) printf -v "${{output_var}}" '%s' direct-runner ;;
    repeatability) printf -v "${{output_var}}" '%s' repeat-runner ;;
    *) echo "unknown profile: ${{profile_name}}" >&2; return 1 ;;
  esac
}}
invoke_fn() {{
  export RUNNER_FN="$1"
  export PROFILE_NAME="$2"
  export ARG_ONE="$3"
  python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "runner_fn": os.environ["RUNNER_FN"],
  "profile_name": os.environ["PROFILE_NAME"],
  "arg_one": os.environ["ARG_ONE"],
}}))
PY
}}
case_chain_run_standard_profile_surface resolver_fn invoke_fn direct alpha
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
        "runner_fn": "direct-runner",
        "profile_name": "direct",
        "arg_one": "alpha",
    }


def test_case_chain_standard_profile_surface_propagates_resolver_failure(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_standard_profile_surface.sh")!r}
resolver_fn() {{
  echo "resolver failed: $1" >&2
  return 23
}}
invoke_fn() {{
  echo "unexpected invoke" >&2
  return 99
}}
case_chain_run_standard_profile_surface resolver_fn invoke_fn repeatability alpha
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 23
    assert completed.stderr == "resolver failed: repeatability\n"
