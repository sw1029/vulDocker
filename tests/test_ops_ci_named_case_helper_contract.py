from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_named_case_require_target_helper_accepts_executable(tmp_path: Path) -> None:
    helper = tmp_path / "helper.sh"
    _write_executable(helper, "#!/usr/bin/env bash\nexit 0\n")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_named_case_helper_contract.sh')!r}\n"
                f"named_case_require_target_helper {str(helper)!r} TEST"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0
    assert completed.stderr == ""


def test_named_case_require_target_helper_rejects_missing_helper_with_custom_message(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_named_case_helper_contract.sh')!r}\n"
                "named_case_require_target_helper '' TEST 'custom missing message'"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr == "[TEST] custom missing message\n"


def test_named_case_require_target_helper_rejects_non_executable_helper(tmp_path: Path) -> None:
    helper = tmp_path / "helper.sh"
    helper.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_named_case_helper_contract.sh')!r}\n"
                f"named_case_require_target_helper {str(helper)!r} TEST"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr == f"[TEST] target helper not found or not executable: {helper}\n"
