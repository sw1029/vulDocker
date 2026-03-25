from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_case_spec_require_builder_accepts_known_builder() -> None:
    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_case_spec_presets.sh')!r}\n"
                f"source {str(REPO_ROOT / 'ops/ci/lib_case_spec_preset_contract.sh')!r}\n"
                "case_spec_require_builder build_positive_pair_case_specs TEST"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0
    assert completed.stderr == ""


def test_case_spec_require_builder_rejects_missing_builder() -> None:
    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_case_spec_presets.sh')!r}\n"
                f"source {str(REPO_ROOT / 'ops/ci/lib_case_spec_preset_contract.sh')!r}\n"
                "case_spec_require_builder '' TEST"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr == "[TEST] preset builder is required\n"


def test_case_spec_require_builder_rejects_unknown_builder() -> None:
    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_case_spec_presets.sh')!r}\n"
                f"source {str(REPO_ROOT / 'ops/ci/lib_case_spec_preset_contract.sh')!r}\n"
                "case_spec_require_builder unknown_builder TEST"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr == "[TEST] unknown preset builder: unknown_builder\n"
