from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_operator_require_sequence_helper_accepts_executable(tmp_path: Path) -> None:
    helper = tmp_path / "sequence.sh"
    _write_executable(helper, "#!/usr/bin/env bash\nexit 0\n")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_operator_sequence_helper_contract.sh')!r}\n"
                f"operator_require_sequence_helper {str(helper)!r} TEST-SEQUENCE"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""


def test_operator_require_sequence_helper_rejects_missing_helper() -> None:
    missing = Path("/tmp/vuld_missing_operator_sequence_helper.sh")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_operator_sequence_helper_contract.sh')!r}\n"
                f"operator_require_sequence_helper {str(missing)!r} TEST-SEQUENCE"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr == (
        f"[TEST-SEQUENCE] sequence helper not found or not executable: {missing}\n"
    )


def test_operator_run_sequence_helper_invokes_helper_with_baseline_label(
    tmp_path: Path,
) -> None:
    helper = tmp_path / "sequence.py"
    capture = tmp_path / "capture.json"
    _write_executable(
        helper,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path
Path({str(capture)!r}).write_text(json.dumps(sys.argv[1:]), encoding='utf-8')
raise SystemExit(0)
""",
    )

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_operator_sequence_helper_contract.sh')!r}\n"
                f"operator_run_sequence_helper {str(helper)!r} TEST-SEQUENCE 'first step' /tmp/first -- 'second step' /tmp/second"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(capture.read_text(encoding='utf-8')) == [
        "TEST-SEQUENCE",
        "first step",
        "/tmp/first",
        "--",
        "second step",
        "/tmp/second",
    ]
