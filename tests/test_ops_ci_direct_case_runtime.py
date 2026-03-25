from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_direct_case_runtime_prepares_context_and_command(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    case_dir = tmp_path / "cases" / "alpha-case"
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "expectations.json").write_text("{}", encoding="utf-8")
    cmd_out = tmp_path / "cmd.txt"
    ctx_out = tmp_path / "ctx.txt"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_direct_case_runtime.sh")!r}
CASE_RUNTIME=()
CMD=()
direct_prepare_case_runtime \
  CASE_RUNTIME \
  CMD \
  TEST \
  {str(tmp_path / "cases")!r} \
  "alpha-case=custom_output" \
  {str(tmp_path / "outputs")!r} \
  python \
  deterministic \
  1
printf '%s\\n' "${{CASE_RUNTIME[@]}}" > {str(ctx_out)!r}
printf '%s\\n' "${{CMD[@]}}" > {str(cmd_out)!r}
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert ctx_out.read_text(encoding="utf-8").splitlines() == [
        str(case_dir),
        "alpha-case",
        str(tmp_path / "outputs" / "custom_output"),
    ]
    cmd_lines = cmd_out.read_text(encoding="utf-8").splitlines()
    assert cmd_lines[:2] == ["python", "tests/e2e/run_case.py"]
    assert "--case" in cmd_lines
    assert "--expectations" in cmd_lines
    assert "--no-snapshot" in cmd_lines
    assert cmd_lines[cmd_lines.index("--output-dir") + 1] == str(tmp_path / "outputs" / "custom_output")


def test_direct_case_runtime_supports_default_output_name(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    case_dir = tmp_path / "cases" / "beta-case"
    case_dir.mkdir(parents=True, exist_ok=True)
    capture = tmp_path / "capture.txt"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_direct_case_runtime.sh")!r}
CASE_RUNTIME=()
CMD=()
direct_prepare_case_runtime \
  CASE_RUNTIME \
  CMD \
  TEST \
  {str(tmp_path / "cases")!r} \
  "beta-case" \
  {str(tmp_path / "outputs")!r} \
  python \
  deterministic \
  0
printf '%s' "${{CASE_RUNTIME[2]}}" > {str(capture)!r}
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert capture.read_text(encoding="utf-8") == str(tmp_path / "outputs" / "run_beta_case")


def test_direct_case_runtime_propagates_invalid_alias_failure(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    case_dir = tmp_path / "cases" / "gamma-case"
    case_dir.mkdir(parents=True, exist_ok=True)

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_direct_case_runtime.sh")!r}
CASE_RUNTIME=()
CMD=()
direct_prepare_case_runtime \
  CASE_RUNTIME \
  CMD \
  TEST \
  {str(tmp_path / "cases")!r} \
  "gamma-case=bad/alias" \
  {str(tmp_path / "outputs")!r} \
  python \
  deterministic \
  0
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr == "[TEST] alias must not contain '/': bad/alias\n"
