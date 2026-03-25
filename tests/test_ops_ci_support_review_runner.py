from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_support_review_run_helper_exports_env_and_invokes_helper(tmp_path: Path) -> None:
    run_a = tmp_path / "run-a"
    run_b = tmp_path / "run-b"
    run_a.mkdir()
    run_b.mkdir()
    review_helper = tmp_path / "review_helper.py"
    capture_path = tmp_path / "capture.json"

    _write_executable(
        review_helper,
        f"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

Path({str(capture_path)!r}).write_text(json.dumps({{
    "argv": sys.argv[1:],
    "env": {{
        "VULD_SUPPORT_REVIEW_PYTHON_BIN": os.environ.get("VULD_SUPPORT_REVIEW_PYTHON_BIN"),
        "VULD_SUPPORT_REVIEW_OUTPUT_ROOT": os.environ.get("VULD_SUPPORT_REVIEW_OUTPUT_ROOT"),
        "VULD_SUPPORT_REVIEW_REVIEW_ONLY": os.environ.get("VULD_SUPPORT_REVIEW_REVIEW_ONLY"),
        "VULD_SUPPORT_REVIEW_DECISIONS_FILE": os.environ.get("VULD_SUPPORT_REVIEW_DECISIONS_FILE"),
        "VULD_SUPPORT_REVIEW_REVIEW_OUTPUT_NAME": os.environ.get("VULD_SUPPORT_REVIEW_REVIEW_OUTPUT_NAME"),
        "VULD_SUPPORT_REVIEW_DECISIONS_OUTPUT_NAME": os.environ.get("VULD_SUPPORT_REVIEW_DECISIONS_OUTPUT_NAME"),
        "VULD_SUPPORT_REVIEW_UPDATE_OUTPUT_NAME": os.environ.get("VULD_SUPPORT_REVIEW_UPDATE_OUTPUT_NAME"),
        "VULD_SUPPORT_REVIEW_REGISTRY_OUTPUT_NAME": os.environ.get("VULD_SUPPORT_REVIEW_REGISTRY_OUTPUT_NAME"),
    }},
}}, ensure_ascii=False), encoding="utf-8")
raise SystemExit(0)
""",
    )

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_support_review_runner.sh')!r}\n"
                f"support_review_run_helper TEST {str(review_helper)!r} python /tmp/out 1 /tmp/decisions.json review.json decisions.json update.json registry.json {str(run_a)!r} {str(run_b)!r}"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(capture_path.read_text(encoding="utf-8")) == {
        "argv": [str(run_a), str(run_b)],
        "env": {
            "VULD_SUPPORT_REVIEW_PYTHON_BIN": "python",
            "VULD_SUPPORT_REVIEW_OUTPUT_ROOT": "/tmp/out",
            "VULD_SUPPORT_REVIEW_REVIEW_ONLY": "1",
            "VULD_SUPPORT_REVIEW_DECISIONS_FILE": "/tmp/decisions.json",
            "VULD_SUPPORT_REVIEW_REVIEW_OUTPUT_NAME": "review.json",
            "VULD_SUPPORT_REVIEW_DECISIONS_OUTPUT_NAME": "decisions.json",
            "VULD_SUPPORT_REVIEW_UPDATE_OUTPUT_NAME": "update.json",
            "VULD_SUPPORT_REVIEW_REGISTRY_OUTPUT_NAME": "registry.json",
        },
    }


def test_support_review_run_helper_rejects_missing_helper_before_invocation(tmp_path: Path) -> None:
    run_a = tmp_path / "run-a"
    run_a.mkdir()
    missing_helper = tmp_path / "missing_review_helper.sh"

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_support_review_runner.sh')!r}\n"
                f"support_review_run_helper TEST {str(missing_helper)!r} python /tmp/out 0 '' review.json decisions.json update.json registry.json {str(run_a)!r}"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr == f"[TEST] review helper not found or not executable: {missing_helper}\n"
