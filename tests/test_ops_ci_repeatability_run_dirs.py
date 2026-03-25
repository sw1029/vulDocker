from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_repeatability_load_run_dirs_accepts_existing_dirs(tmp_path: Path) -> None:
    run_a = tmp_path / "run-a"
    run_b = tmp_path / "run-b"
    run_a.mkdir()
    run_b.mkdir()
    run_dirs_file = tmp_path / "run_dirs.txt"
    run_dirs_file.write_text(f"{run_a}\n{run_b}\n", encoding="utf-8")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_repeatability_run_dirs.sh')!r}\n"
                f"repeatability_load_run_dirs RUN_DIRS {str(run_dirs_file)!r} TEST\n"
                "printf '%s\\n' \"${#RUN_DIRS[@]}\"\n"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "2"


def test_repeatability_load_run_dirs_rejects_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing_run_dirs.txt"
    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_repeatability_run_dirs.sh')!r}\n"
                f"repeatability_load_run_dirs RUN_DIRS {str(missing)!r} TEST\n"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert f"[TEST] run dirs file not found: {missing}" in completed.stderr


def test_repeatability_load_run_dirs_rejects_empty_file(tmp_path: Path) -> None:
    run_dirs_file = tmp_path / "run_dirs.txt"
    run_dirs_file.write_text("", encoding="utf-8")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_repeatability_run_dirs.sh')!r}\n"
                f"repeatability_load_run_dirs RUN_DIRS {str(run_dirs_file)!r} TEST\n"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert f"[TEST] run dirs file is empty: {run_dirs_file}" in completed.stderr


def test_repeatability_load_run_dirs_rejects_missing_dir(tmp_path: Path) -> None:
    missing_dir = tmp_path / "missing-run"
    run_dirs_file = tmp_path / "run_dirs.txt"
    run_dirs_file.write_text(f"{missing_dir}\n", encoding="utf-8")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_repeatability_run_dirs.sh')!r}\n"
                f"repeatability_load_run_dirs RUN_DIRS {str(run_dirs_file)!r} TEST\n"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert f"[TEST] run directory not found: {missing_dir}" in completed.stderr
