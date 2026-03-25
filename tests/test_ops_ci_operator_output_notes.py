from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_operator_emit_completion_and_outputs_formats_lines() -> None:
    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_operator_output_notes.sh')!r}\n"
                "operator_emit_completion_and_outputs TEST first /tmp/one second /tmp/two third /tmp/three"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines() == [
        "[TEST] completed",
        "[TEST] first=/tmp/one",
        "[TEST] second=/tmp/two",
        "[TEST] third=/tmp/three",
    ]
