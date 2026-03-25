from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_support_review_require_run_dirs_accepts_existing_dirs(tmp_path: Path) -> None:
    run_a = tmp_path / "run-a"
    run_b = tmp_path / "run-b"
    run_a.mkdir()
    run_b.mkdir()

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_support_review_run_dirs.sh')!r}\n"
                f"support_review_require_run_dirs TEST {str(run_a)!r} {str(run_b)!r}\n"
                "printf 'ok\\n'\n"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "ok"


def test_support_review_require_run_dirs_rejects_empty_input() -> None:
    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_support_review_run_dirs.sh')!r}\n"
                "support_review_require_run_dirs TEST\n"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "[TEST] at least one run directory is required" in completed.stderr


def test_support_review_require_run_dirs_rejects_missing_dir(tmp_path: Path) -> None:
    missing = tmp_path / "missing-run"
    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_support_review_run_dirs.sh')!r}\n"
                f"support_review_require_run_dirs TEST {str(missing)!r}\n"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert f"[TEST] run directory not found: {missing}" in completed.stderr
