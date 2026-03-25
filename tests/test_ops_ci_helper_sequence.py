from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_helper_sequence_runs_helpers_in_order_and_forwards_args(tmp_path: Path) -> None:
    capture_path = tmp_path / "calls.json"

    def _helper(name: str) -> Path:
        helper = tmp_path / f"{name}.py"
        _write_executable(
            helper,
            f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path
capture = Path({str(capture_path)!r})
rows = json.loads(capture.read_text(encoding="utf-8")) if capture.exists() else []
rows.append([{name!r}, sys.argv[1:]])
capture.write_text(json.dumps(rows), encoding="utf-8")
raise SystemExit(0)
""",
        )
        return helper

    first = _helper("first")
    second = _helper("second")

    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_helper_sequence.sh"),
            "HELPER-SEQUENCE",
            "first step",
            str(first),
            "--flag",
            "one",
            "--",
            "second step",
            str(second),
            "alpha",
            "beta",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "[HELPER-SEQUENCE] first step" in completed.stdout
    assert "[HELPER-SEQUENCE] second step" in completed.stdout
    assert "[HELPER-SEQUENCE] completed" in completed.stdout
    assert json.loads(capture_path.read_text(encoding="utf-8")) == [
        ["first", ["--flag", "one"]],
        ["second", ["alpha", "beta"]],
    ]


def test_helper_sequence_fails_for_missing_helper(tmp_path: Path) -> None:
    missing = tmp_path / "missing.sh"

    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_helper_sequence.sh"),
            "HELPER-SEQUENCE",
            "missing step",
            str(missing),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert f"[HELPER-SEQUENCE] helper not found or not executable: {missing}" in completed.stderr


def test_helper_sequence_fails_for_incomplete_entry() -> None:
    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_helper_sequence.sh"),
            "HELPER-SEQUENCE",
            "broken step",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "usage:" in completed.stderr
