from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_named_caseset_dispatch_forwards_target_helper_and_args(tmp_path: Path) -> None:
    helper = tmp_path / "caseset_helper.py"
    capture_path = tmp_path / "capture.json"
    _write_executable(
        helper,
        f"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
payload = {{
    "argv": sys.argv[1:],
    "target_helper": os.environ.get("VULD_NAMED_CASE_TARGET_HELPER"),
    "log_prefix": os.environ.get("VULD_NAMED_CASE_LOG_PREFIX"),
}}
Path({str(capture_path)!r}).write_text(json.dumps(payload), encoding="utf-8")
raise SystemExit(0)
""",
    )

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_named_case_env.sh')!r}\n"
                f"named_caseset_dispatch {str(helper)!r} TEST /tmp/leaf alpha=one beta=two"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(capture_path.read_text(encoding="utf-8")) == {
        "argv": ["alpha=one", "beta=two"],
        "target_helper": "/tmp/leaf",
        "log_prefix": "TEST",
    }


def test_named_caseset_dispatch_rejects_missing_caseset_helper(tmp_path: Path) -> None:
    missing = tmp_path / "missing.py"

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_named_case_env.sh')!r}\n"
                f"named_caseset_dispatch {str(missing)!r} TEST /tmp/leaf alpha=one"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr == f"[TEST] caseset helper not found or not executable: {missing}\n"
