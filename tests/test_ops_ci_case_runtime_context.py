from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_case_runtime_context_captures_context_from_direct_output_array(tmp_path: Path) -> None:
    capture = tmp_path / "capture.txt"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_runtime_context.sh")!r}
RESOLVED_OUTPUT=("/tmp/cases/alpha-case" "alpha-case" "alias-out" "alias-out" "/tmp/out/alias-out")
CASE_RUNTIME=()
case_runtime_capture_context CASE_RUNTIME RESOLVED_OUTPUT 4
printf '%s\\n' "${{CASE_RUNTIME[@]}}" > {str(capture)!r}
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert capture.read_text(encoding="utf-8").splitlines() == [
        "/tmp/cases/alpha-case",
        "alpha-case",
        "/tmp/out/alias-out",
    ]


def test_case_runtime_context_captures_repeat_output_and_appends_report_path(tmp_path: Path) -> None:
    capture = tmp_path / "capture.txt"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_runtime_context.sh")!r}
RESOLVED_OUTPUT=("/tmp/cases/beta-case" "beta-case" "alias-beta" "alias-beta" "alias_beta" "/tmp/out/repeat_alias_beta")
CASE_RUNTIME=()
case_runtime_capture_context CASE_RUNTIME RESOLVED_OUTPUT 5
case_runtime_append_report_path CASE_RUNTIME repeatability_report.json
printf '%s\\n' "${{CASE_RUNTIME[@]}}" > {str(capture)!r}
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert capture.read_text(encoding="utf-8").splitlines() == [
        "/tmp/cases/beta-case",
        "beta-case",
        "/tmp/out/repeat_alias_beta",
        "/tmp/out/repeat_alias_beta/repeatability_report.json",
    ]


def test_case_runtime_context_helpers_preserve_alias_agnostic_shape(tmp_path: Path) -> None:
    capture = tmp_path / "capture.txt"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_runtime_context.sh")!r}
RESOLVED_OUTPUT=("/tmp/cases/gamma-case" "gamma-case" "" "run_gamma_case" "/tmp/out/run_gamma_case")
CASE_RUNTIME=()
case_runtime_capture_context CASE_RUNTIME RESOLVED_OUTPUT 4
printf '%s\\n' "${{CASE_RUNTIME[@]}}" > {str(capture)!r}
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert capture.read_text(encoding="utf-8").splitlines() == [
        "/tmp/cases/gamma-case",
        "gamma-case",
        "/tmp/out/run_gamma_case",
    ]


def test_case_runtime_context_prepares_direct_context_from_case_spec(tmp_path: Path) -> None:
    capture = tmp_path / "capture.txt"
    probe = tmp_path / "probe.sh"
    case_dir = tmp_path / "cases" / "delta-case"
    case_dir.mkdir(parents=True, exist_ok=True)

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_runtime_context.sh")!r}
CASE_RUNTIME=()
case_runtime_prepare_direct_context \
  CASE_RUNTIME \
  TEST \
  {str(tmp_path / "cases")!r} \
  "delta-case=direct_alias" \
  {str(tmp_path / "outputs")!r}
printf '%s\\n' "${{CASE_RUNTIME[@]}}" > {str(capture)!r}
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert capture.read_text(encoding="utf-8").splitlines() == [
        str(case_dir),
        "delta-case",
        str(tmp_path / "outputs" / "direct_alias"),
    ]


def test_case_runtime_context_prepares_repeat_context_from_case_spec(tmp_path: Path) -> None:
    capture = tmp_path / "capture.txt"
    probe = tmp_path / "probe.sh"
    case_dir = tmp_path / "cases" / "epsilon-case"
    case_dir.mkdir(parents=True, exist_ok=True)

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_runtime_context.sh")!r}
CASE_RUNTIME=()
case_runtime_prepare_repeat_context \
  CASE_RUNTIME \
  TEST \
  {str(tmp_path / "cases")!r} \
  "epsilon-case=repeat_alias" \
  {str(tmp_path / "outputs")!r} \
  repeat \
  repeatability_report.json
printf '%s\\n' "${{CASE_RUNTIME[@]}}" > {str(capture)!r}
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert capture.read_text(encoding="utf-8").splitlines() == [
        str(case_dir),
        "epsilon-case",
        str(tmp_path / "outputs" / "repeat_repeat_alias"),
        str(tmp_path / "outputs" / "repeat_repeat_alias" / "repeatability_report.json"),
    ]
