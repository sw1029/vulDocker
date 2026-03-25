from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_named_case_set_supports_target_helper_forwarding(tmp_path: Path) -> None:
    capture_path = tmp_path / "capture.json"
    target_helper = tmp_path / "target.py"
    _write_executable(
        target_helper,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path
Path({str(capture_path)!r}).write_text(json.dumps(sys.argv[1:]), encoding="utf-8")
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_NAMED_CASE_TARGET_HELPER"] = str(target_helper)
    env["VULD_NAMED_CASE_LOG_PREFIX"] = "CASESET"

    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_named_case_set.sh"),
            "alpha-case=alpha",
            "beta-case=beta",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(capture_path.read_text(encoding="utf-8")) == ["alpha-case=alpha", "beta-case=beta"]


def test_named_case_set_fails_without_target_helper(tmp_path: Path) -> None:
    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_named_case_set.sh"), "alpha-case"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "[NAMED-CASE] target helper not configured" in completed.stderr
