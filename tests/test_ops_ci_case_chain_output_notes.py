from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_case_chain_output_notes_emit_case_and_completed(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_output_notes.sh")!r}
case_chain_emit_case_output "CHAIN" "alpha-case" "/tmp/out" "repeat "
case_chain_emit_completed "CHAIN"
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines() == [
        "[CHAIN] repeat alpha-case -> /tmp/out",
        "[CHAIN] completed",
    ]


def test_case_chain_output_notes_write_run_dirs_file(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    run_dirs_file = tmp_path / "run_dirs.txt"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_output_notes.sh")!r}
case_chain_write_run_dirs_file {str(run_dirs_file)!r} /tmp/out-a /tmp/out-b
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert run_dirs_file.read_text(encoding="utf-8").splitlines() == [
        "/tmp/out-a",
        "/tmp/out-b",
    ]
