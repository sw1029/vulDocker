from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_case_specs_runner_invokes_runner_for_each_case_writes_run_dirs_and_emits_completed(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "probe.sh"
    capture = tmp_path / "capture.txt"
    run_dirs_file = tmp_path / "run_dirs.txt"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_specs_runner.sh")!r}
RUN_DIRS=()
fake_runner() {{
  local context_ref_name="$1"
  local prefix_a="$2"
  local prefix_b="$3"
  local case_spec="$4"
  local suffix_a="$5"
  local suffix_b="$6"
  local -n context_ref="${{context_ref_name}}"
  context_ref=("dir:${{case_spec}}" "slug:${{case_spec}}" "out:${{case_spec}}")
  RUN_DIRS+=("out:${{case_spec}}")
  printf '%s|%s|%s|%s|%s\\n' "${{prefix_a}}" "${{prefix_b}}" "${{case_spec}}" "${{suffix_a}}" "${{suffix_b}}" >> {str(capture)!r}
}}
CASE_SPECS=("alpha-case" "beta-case=alias_beta")
RUNNER_PREFIX=("PRE_A" "PRE_B")
RUNNER_SUFFIX=("SUF_A" "SUF_B")
case_specs_run_with_contexts fake_runner CASE_SPECS RUNNER_PREFIX RUNNER_SUFFIX TEST RUN_DIRS {str(run_dirs_file)!r}
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "[TEST] completed\n"
    assert capture.read_text(encoding="utf-8").splitlines() == [
        "PRE_A|PRE_B|alpha-case|SUF_A|SUF_B",
        "PRE_A|PRE_B|beta-case=alias_beta|SUF_A|SUF_B",
    ]
    assert run_dirs_file.read_text(encoding="utf-8").splitlines() == [
        "out:alpha-case",
        "out:beta-case=alias_beta",
    ]


def test_case_specs_runner_propagates_runner_failure(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_specs_runner.sh")!r}
fake_runner() {{
  local context_ref_name="$1"
  local case_spec="$4"
  if [[ "${{case_spec}}" = "beta-case" ]]; then
    echo "runner failed for ${{case_spec}}" >&2
    return 7
  fi
}}
CASE_SPECS=("alpha-case" "beta-case")
RUNNER_PREFIX=("PRE_A" "PRE_B")
RUNNER_SUFFIX=("SUF_A" "SUF_B")
case_specs_run_with_contexts fake_runner CASE_SPECS RUNNER_PREFIX RUNNER_SUFFIX TEST "" ""
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 7
    assert completed.stderr == "runner failed for beta-case\n"
