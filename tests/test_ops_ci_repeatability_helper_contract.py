from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_repeatability_require_helper_accepts_executable(tmp_path: Path) -> None:
    helper = tmp_path / "repeat_helper.sh"
    _write_executable(helper, "#!/usr/bin/env bash\nexit 0\n")
    probe = tmp_path / "probe.sh"
    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_repeatability_helper_contract.sh")!r}
repeatability_require_helper {str(helper)!r} TEST
echo ok
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "ok\n"


def test_repeatability_require_helper_rejects_missing_helper(tmp_path: Path) -> None:
    helper = tmp_path / "missing_repeat_helper.sh"
    probe = tmp_path / "probe.sh"
    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_repeatability_helper_contract.sh")!r}
repeatability_require_helper {str(helper)!r} TEST
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr == f"[TEST] repeat helper not found or not executable: {helper}\n"
