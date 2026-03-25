from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_focused_no_docker_regression_supports_pytest_override_and_forwards_args(tmp_path: Path) -> None:
    capture_path = tmp_path / "pytest_capture.json"
    fake_pytest = tmp_path / "fake_pytest.py"
    _write_executable(
        fake_pytest,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path
Path({str(capture_path)!r}).write_text(json.dumps(sys.argv[1:]), encoding="utf-8")
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_FOCUSED_NO_DOCKER_PYTEST_BIN"] = str(fake_pytest)
    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_focused_no_docker_regression.sh"),
            "-k",
            "support_workflow",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    captured = json.loads(capture_path.read_text(encoding="utf-8"))
    assert captured[:7] == [
        "-q",
        "tests/test_name_only_helpers.py",
        "tests/test_pack_promotion.py",
        "tests/test_repeatability_gate.py",
        "tests/test_support_extract.py",
        "tests/e2e/test_support_workflow.py",
        "tests/e2e/test_case_matrix_rollup.py",
    ]
    assert captured[7:] == ["-k", "support_workflow"]
