from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _skip_reason() -> str:
    if not os.environ.get("VULD_RUN_E2E"):
        return "Set VULD_RUN_E2E=1 to enable slow E2E tests"
    if shutil.which("docker") is None:
        return "Docker CLI is not available"
    return ""


@pytest.mark.e2e
def test_cwe89_basic_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)
    case_dir = REPO_ROOT / "tests/e2e/cases/cwe-89-basic"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "tests/e2e/run_case.py"),
        "--case",
        str(case_dir),
        "--mode",
        "deterministic",
        "--no-snapshot",
        "--output-dir",
        str(tmp_path),
    ]
    env = os.environ.copy()
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        pytest.fail(f"run_case failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    summary_path = tmp_path / "summary.json"
    assert summary_path.exists(), "summary.json was not created"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["sid"].startswith("sid-"), "SID was not recorded"
    assert any(bundle["slug"] == "cwe-89" and bundle.get("verify_pass") for bundle in summary["bundles"])
