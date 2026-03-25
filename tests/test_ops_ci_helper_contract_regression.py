from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_ops_helper_contract_regression_supports_pytest_override_and_forwards_args(tmp_path: Path) -> None:
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
    env["VULD_OPS_HELPER_PYTEST_BIN"] = str(fake_pytest)
    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_ops_helper_contract_regression.sh"),
            "-k",
            "repeatability_scripts",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    captured = json.loads(capture_path.read_text(encoding="utf-8"))
    assert captured[0] == "-q"
    assert captured[-2:] == ["-k", "repeatability_scripts"]
    expected = sorted(str(path.relative_to(REPO_ROOT)) for path in REPO_ROOT.glob("tests/test_ops_ci_*.py"))
    actual = sorted(item for item in captured if item.startswith("tests/test_ops_ci_"))
    assert actual == expected


def test_ops_helper_contract_regression_supports_custom_glob(tmp_path: Path) -> None:
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

    custom_dir = tmp_path / "custom"
    custom_dir.mkdir(parents=True, exist_ok=True)
    for name in ("alpha_test.py", "beta_test.py"):
        (custom_dir / name).write_text("# test placeholder\n", encoding="utf-8")

    env = os.environ.copy()
    env["VULD_OPS_HELPER_PYTEST_BIN"] = str(fake_pytest)
    env["VULD_OPS_HELPER_TEST_GLOB"] = str(custom_dir / "*_test.py")
    env["VULD_OPS_HELPER_PRINT_BUNDLE"] = "1"
    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_ops_helper_contract_regression.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "[OPS-HELPERS] bundle_size=2" in completed.stdout
    assert str(custom_dir / "alpha_test.py") in completed.stdout
    assert str(custom_dir / "beta_test.py") in completed.stdout

    captured = json.loads(capture_path.read_text(encoding="utf-8"))
    actual = sorted(item for item in captured if item.startswith(str(custom_dir)))
    assert actual == sorted([str(custom_dir / "alpha_test.py"), str(custom_dir / "beta_test.py")])


def test_ops_helper_contract_regression_fails_when_glob_is_empty(tmp_path: Path) -> None:
    fake_pytest = tmp_path / "fake_pytest.py"
    _write_executable(
        fake_pytest,
        """#!/usr/bin/env python3
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_OPS_HELPER_PYTEST_BIN"] = str(fake_pytest)
    env["VULD_OPS_HELPER_TEST_GLOB"] = str(tmp_path / "missing_*.py")
    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_ops_helper_contract_regression.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert f"[OPS-HELPERS] no helper regression tests found under {tmp_path / 'missing_*.py'}" in completed.stderr
