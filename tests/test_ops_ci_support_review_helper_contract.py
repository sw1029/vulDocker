from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_support_review_require_helper_accepts_executable() -> None:
    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_support_review_helper_contract.sh')!r}\n"
                "support_review_require_helper /bin/echo TEST\n"
                "printf 'ok\\n'\n"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "ok"


def test_support_review_require_helper_rejects_missing_helper() -> None:
    missing = "/tmp/definitely-missing-support-review-helper"
    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_support_review_helper_contract.sh')!r}\n"
                f"support_review_require_helper {missing!r} TEST\n"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert f"[TEST] review helper not found or not executable: {missing}" in completed.stderr


def test_support_review_materialize_decisions_file_writes_empty_default(tmp_path: Path) -> None:
    decisions_out = tmp_path / "support_decisions.json"
    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_support_review_helper_contract.sh')!r}\n"
                f"support_review_materialize_decisions_file '' {str(decisions_out)!r}\n"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(decisions_out.read_text(encoding="utf-8")) == {
        "schema_version": "support_review_decisions@0.1",
        "decisions": [],
    }


def test_support_review_materialize_decisions_file_copies_existing_payload(tmp_path: Path) -> None:
    decisions_file = tmp_path / "source_decisions.json"
    decisions_out = tmp_path / "support_decisions.json"
    expected = {
        "schema_version": "support_review_decisions@0.1",
        "decisions": [{"case_name": "demo", "decision": "accept"}],
    }
    decisions_file.write_text(json.dumps(expected, ensure_ascii=False), encoding="utf-8")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_support_review_helper_contract.sh')!r}\n"
                f"support_review_materialize_decisions_file {str(decisions_file)!r} {str(decisions_out)!r}\n"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(decisions_out.read_text(encoding="utf-8")) == expected
