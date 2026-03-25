from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_support_review_chain_supports_output_and_python_override(tmp_path: Path) -> None:
    run_a = tmp_path / "run-a"
    run_b = tmp_path / "run-b"
    run_a.mkdir()
    run_b.mkdir()
    output_root = tmp_path / "outputs"
    capture_path = tmp_path / "python_calls.json"
    fake_python = tmp_path / "fake_python.py"

    _write_executable(
        fake_python,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path

capture_path = Path({str(capture_path)!r})
calls = json.loads(capture_path.read_text(encoding="utf-8")) if capture_path.exists() else []
calls.append(sys.argv[1:])
capture_path.write_text(json.dumps(calls, ensure_ascii=False), encoding="utf-8")

argv = sys.argv[1:]
if argv and argv[0] == "tests/e2e/support_review.py":
    Path(argv[argv.index("--output") + 1]).write_text("{{}}", encoding="utf-8")
    raise SystemExit(0)
if argv and argv[0] == "tests/e2e/support_decide.py":
    Path(argv[argv.index("--output") + 1]).write_text("{{}}", encoding="utf-8")
    raise SystemExit(0)
if argv and argv[0] == "tests/e2e/support_apply.py":
    Path(argv[argv.index("--output") + 1]).write_text("{{}}", encoding="utf-8")
    raise SystemExit(0)
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_SUPPORT_REVIEW_PYTHON_BIN"] = str(fake_python)
    env["VULD_SUPPORT_REVIEW_OUTPUT_ROOT"] = str(output_root)
    env["VULD_SUPPORT_REVIEW_REVIEW_OUTPUT_NAME"] = "custom_review.json"
    env["VULD_SUPPORT_REVIEW_DECISIONS_OUTPUT_NAME"] = "custom_decisions.json"
    env["VULD_SUPPORT_REVIEW_UPDATE_OUTPUT_NAME"] = "custom_update.json"
    env["VULD_SUPPORT_REVIEW_REGISTRY_OUTPUT_NAME"] = "custom_registry.json"

    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_support_review_chain.sh"),
            str(run_a),
            str(run_b),
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert (output_root / "custom_review.json").exists()
    assert (output_root / "custom_decisions.json").exists()
    assert (output_root / "custom_update.json").exists()
    assert (output_root / "custom_registry.json").exists()

    calls = json.loads(capture_path.read_text(encoding="utf-8"))
    assert calls[0] == [
        "tests/e2e/support_review.py",
        str(run_a),
        str(run_b),
        "--output",
        str(output_root / "custom_review.json"),
    ]
    assert calls[1][0] == "tests/e2e/support_decide.py"
    assert calls[2][0] == "tests/e2e/support_apply.py"


def test_support_review_chain_supports_review_only(tmp_path: Path) -> None:
    run_a = tmp_path / "run-a"
    run_a.mkdir()
    output_root = tmp_path / "outputs"
    capture_path = tmp_path / "python_calls.json"
    fake_python = tmp_path / "fake_python.py"

    _write_executable(
        fake_python,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path

capture_path = Path({str(capture_path)!r})
calls = json.loads(capture_path.read_text(encoding="utf-8")) if capture_path.exists() else []
calls.append(sys.argv[1:])
capture_path.write_text(json.dumps(calls, ensure_ascii=False), encoding="utf-8")

argv = sys.argv[1:]
if argv and argv[0] == "tests/e2e/support_review.py":
    Path(argv[argv.index("--output") + 1]).write_text("{{}}", encoding="utf-8")
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_SUPPORT_REVIEW_PYTHON_BIN"] = str(fake_python)
    env["VULD_SUPPORT_REVIEW_OUTPUT_ROOT"] = str(output_root)
    env["VULD_SUPPORT_REVIEW_REVIEW_ONLY"] = "1"

    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_support_review_chain.sh"),
            str(run_a),
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "[SUPPORT-REVIEW] review-only completed" in completed.stdout
    assert (output_root / "support_review.json").exists()
    assert not (output_root / "support_decisions.json").exists()
    assert not (output_root / "support_update.json").exists()
    assert not (output_root / "support_registry.json").exists()

    calls = json.loads(capture_path.read_text(encoding="utf-8"))
    assert len(calls) == 1
    assert calls[0][0] == "tests/e2e/support_review.py"
