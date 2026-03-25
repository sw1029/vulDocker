from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_operator_run_export_helper_function_invokes_helper_with_args(
    tmp_path: Path,
) -> None:
    capture_path = tmp_path / "capture.json"

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_operator_export_helper_contract.sh')!r}\n"
                "test_export_helper() {\n"
                f"  python -c \"import json, pathlib, sys; pathlib.Path({str(capture_path)!r}).write_text(json.dumps(sys.argv[1:]), encoding='utf-8')\" \"$@\"\n"
                "}\n"
                "operator_run_export_helper_function test_export_helper TEST 'export helper function' alpha beta gamma"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(capture_path.read_text(encoding="utf-8")) == [
        "alpha",
        "beta",
        "gamma",
    ]


def test_operator_run_export_helper_function_rejects_missing_helper() -> None:
    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_operator_export_helper_contract.sh')!r}\n"
                "operator_run_export_helper_function missing_export_fn TEST 'export helper function' alpha beta"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr == "[TEST] export helper function not found: missing_export_fn\n"
