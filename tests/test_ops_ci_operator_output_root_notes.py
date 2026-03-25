from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_operator_emit_output_root_children_formats_resolved_paths() -> None:
    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_operator_output_root_notes.sh')!r}\n"
                "operator_emit_output_root_children TEST /tmp/root first one second two/three"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines() == [
        "[TEST] completed",
        "[TEST] first=/tmp/root/one",
        "[TEST] second=/tmp/root/two/three",
    ]


def test_operator_emit_output_root_children_requires_even_label_suffix_pairs() -> None:
    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_operator_output_root_notes.sh')!r}\n"
                "operator_emit_output_root_children TEST /tmp/root orphan"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr.strip() == "[TEST] output-root child pairs are required"
