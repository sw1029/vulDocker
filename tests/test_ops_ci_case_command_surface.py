from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_case_command_surface_builds_run_case_args_with_expectations(tmp_path: Path) -> None:
    capture = tmp_path / "capture.txt"
    probe = tmp_path / "probe.sh"
    case_dir = tmp_path / "cases" / "alpha-case"
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "expectations.json").write_text("{}", encoding="utf-8")

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_command_surface.sh")!r}
CMD=()
case_command_build_run_case CMD python {str(case_dir)!r} deterministic {str(tmp_path / "out")!r} 1
printf '%s\\n' "${{CMD[@]}}" > {str(capture)!r}
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    argv = capture.read_text(encoding="utf-8").splitlines()
    assert argv == [
        "python",
        "tests/e2e/run_case.py",
        "--case",
        str(case_dir),
        "--mode",
        "deterministic",
        "--output-dir",
        str(tmp_path / "out"),
        "--expectations",
        str(case_dir / "expectations.json"),
        "--no-snapshot",
    ]


def test_case_command_surface_builds_repeat_case_args_without_snapshot_flag(tmp_path: Path) -> None:
    capture = tmp_path / "capture.txt"
    probe = tmp_path / "probe.sh"
    case_dir = tmp_path / "cases" / "beta-case"
    case_dir.mkdir(parents=True, exist_ok=True)

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_command_surface.sh")!r}
CMD=()
case_command_build_repeat_case CMD python {str(case_dir)!r} 3 deterministic {str(tmp_path / "repeat_out")!r} 0
printf '%s\\n' "${{CMD[@]}}" > {str(capture)!r}
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    argv = capture.read_text(encoding="utf-8").splitlines()
    assert argv == [
        "python",
        "tests/e2e/repeat_case.py",
        "--attempts",
        "3",
        "--case",
        str(case_dir),
        "--mode",
        "deterministic",
        "--output-dir",
        str(tmp_path / "repeat_out"),
    ]
