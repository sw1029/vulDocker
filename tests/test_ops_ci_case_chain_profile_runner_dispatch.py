from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_case_chain_profile_runner_dispatch_resolves_and_invokes_runner(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "probe.sh"
    capture = tmp_path / "capture.json"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_profile_runner_dispatch.sh")!r}
resolve_runner() {{
  local profile_name="$1"
  local output_var_name="$2"
  printf -v "${{output_var_name}}" '%s' "fake_runner_for_${{profile_name}}"
}}
invoke_runner() {{
  export RUNNER_FN="$1"
  export PROFILE_NAME="$2"
  export ARG_ONE="$3"
  export ARG_TWO="$4"
  python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "runner_fn": os.environ["RUNNER_FN"],
  "profile": os.environ["PROFILE_NAME"],
  "arg_one": os.environ["ARG_ONE"],
  "arg_two": os.environ["ARG_TWO"],
}}))
PY
}}
case_chain_run_profile_runner_dispatch resolve_runner invoke_runner direct alpha beta
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
        "runner_fn": "fake_runner_for_direct",
        "profile": "direct",
        "arg_one": "alpha",
        "arg_two": "beta",
    }


def test_case_chain_profile_runner_dispatch_propagates_resolver_failure(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_profile_runner_dispatch.sh")!r}
resolve_runner() {{
  echo "unknown profile: $1" >&2
  return 23
}}
invoke_runner() {{
  echo "should not run" >&2
  return 99
}}
case_chain_run_profile_runner_dispatch resolve_runner invoke_runner unknown alpha
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 23
    assert completed.stderr == "unknown profile: unknown\n"


def test_case_chain_profile_runner_dispatch_forwards_extra_arguments(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "probe.sh"
    capture = tmp_path / "capture.json"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_profile_runner_dispatch.sh")!r}
resolve_runner() {{
  local _profile_name="$1"
  local output_var_name="$2"
  printf -v "${{output_var_name}}" '%s' "selected_runner"
}}
invoke_runner() {{
  shift 2
  python - <<'PY' "$@" > {str(capture)!r}
import json
import sys
print(json.dumps(sys.argv[1:]))
PY
}}
case_chain_run_profile_runner_dispatch resolve_runner invoke_runner repeatability one two three
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(capture.read_text(encoding="utf-8")) == [
        "one",
        "two",
        "three",
    ]
