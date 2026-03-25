from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_case_expectations_resolve_default_returns_expectations_path(tmp_path: Path) -> None:
    capture = tmp_path / "capture.txt"
    probe = tmp_path / "probe.sh"

    case_dir = tmp_path / "cases" / "alpha-case"
    case_dir.mkdir(parents=True, exist_ok=True)
    expectations_path = case_dir / "expectations.json"
    expectations_path.write_text("{}", encoding="utf-8")

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_expectations.sh")!r}
printf '%s' "$(case_expectations_resolve_default {str(case_dir)!r})" > {str(capture)!r}
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert capture.read_text(encoding="utf-8") == str(expectations_path)


def test_case_expectations_resolve_default_returns_empty_when_missing(tmp_path: Path) -> None:
    capture = tmp_path / "capture.txt"
    probe = tmp_path / "probe.sh"

    case_dir = tmp_path / "cases" / "beta-case"
    case_dir.mkdir(parents=True, exist_ok=True)

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_expectations.sh")!r}
printf '%s' "$(case_expectations_resolve_default {str(case_dir)!r})" > {str(capture)!r}
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert capture.read_text(encoding="utf-8") == ""


def test_case_expectations_append_if_present_mutates_command_array(tmp_path: Path) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    case_dir = tmp_path / "cases" / "gamma-case"
    case_dir.mkdir(parents=True, exist_ok=True)
    expectations_path = case_dir / "expectations.json"
    expectations_path.write_text("{}", encoding="utf-8")

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_expectations.sh")!r}
CMD=(python tests/e2e/run_case.py --case {str(case_dir)!r})
case_expectations_append_if_present CMD {str(case_dir)!r}
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
    assert capture.read_text(encoding="utf-8").splitlines() == [
        "python",
        "tests/e2e/run_case.py",
        "--case",
        str(case_dir),
        "--expectations",
        str(expectations_path),
    ]
