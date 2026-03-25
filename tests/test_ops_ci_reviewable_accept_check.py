from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_reviewable_accept_check_supports_python_and_output_override(tmp_path: Path) -> None:
    capture_path = tmp_path / "python_calls.json"
    fake_python = tmp_path / "fake_python.py"

    _write_executable(
        fake_python,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path

capture_path = Path({str(capture_path)!r})
calls = []
if capture_path.exists():
    calls = json.loads(capture_path.read_text(encoding="utf-8"))
calls.append(sys.argv[1:])
capture_path.write_text(json.dumps(calls, ensure_ascii=False), encoding="utf-8")

argv = sys.argv[1:]
if argv and argv[0] == "tests/e2e/support_review.py":
    out_path = Path(argv[argv.index("--output") + 1])
    out_path.write_text(json.dumps({{"reviewable_bundle_count": 1}}, ensure_ascii=False), encoding="utf-8")
    raise SystemExit(0)
if argv and argv[0] == "tests/e2e/support_decide.py":
    out_path = Path(argv[argv.index("--output") + 1])
    out_path.write_text(json.dumps({{"accepted_count": 1}}, ensure_ascii=False), encoding="utf-8")
    raise SystemExit(0)
if argv and argv[0] == "tests/e2e/support_apply.py":
    out_path = Path(argv[argv.index("--output") + 1])
    out_path.write_text(json.dumps({{"registry_item_count": 1, "schema_status": "normalized"}}, ensure_ascii=False), encoding="utf-8")
    raise SystemExit(0)
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_REVIEWABLE_ACCEPT_PYTHON_BIN"] = str(fake_python)
    env["VULD_REVIEWABLE_ACCEPT_OUTPUT_ROOT"] = str(tmp_path / "outputs")

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_reviewable_support_accept_check.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "[REVIEWABLE] completed" in completed.stdout

    outputs = tmp_path / "outputs"
    assert (outputs / "reviewable-run" / "support_candidate.json").exists()
    assert (outputs / "support_review_decisions.json").exists()
    assert (outputs / "support_review_index.json").exists()
    assert (outputs / "support_registry_update.json").exists()
    assert (outputs / "curated_support_registry.json").exists()

    calls = json.loads(capture_path.read_text(encoding="utf-8"))
    assert calls[0][0] == "tests/e2e/support_review.py"
    assert calls[1][0] == "tests/e2e/support_decide.py"
    assert calls[2][0] == "tests/e2e/support_apply.py"


def test_reviewable_accept_check_supports_review_helper_override(tmp_path: Path) -> None:
    capture_path = tmp_path / "review_helper_capture.json"
    review_helper = tmp_path / "review_helper.py"

    _write_executable(
        review_helper,
        f"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
capture = Path({str(capture_path)!r})
capture.write_text(json.dumps({{
    "argv": sys.argv[1:],
    "env": {{
        "VULD_SUPPORT_REVIEW_PYTHON_BIN": os.environ.get("VULD_SUPPORT_REVIEW_PYTHON_BIN"),
        "VULD_SUPPORT_REVIEW_OUTPUT_ROOT": os.environ.get("VULD_SUPPORT_REVIEW_OUTPUT_ROOT"),
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

    env = os.environ.copy()
    env["VULD_REVIEWABLE_ACCEPT_REVIEW_HELPER"] = str(review_helper)
    env["VULD_REVIEWABLE_ACCEPT_PYTHON_BIN"] = "/tmp/fake_python"
    env["VULD_REVIEWABLE_ACCEPT_OUTPUT_ROOT"] = str(tmp_path / "outputs")
    env["VULD_REVIEWABLE_ACCEPT_REVIEW_OUTPUT_NAME"] = "custom_review_index.json"
    env["VULD_REVIEWABLE_ACCEPT_DECISIONS_OUTPUT_NAME"] = "custom_review_decisions.json"
    env["VULD_REVIEWABLE_ACCEPT_UPDATE_OUTPUT_NAME"] = "custom_registry_update.json"
    env["VULD_REVIEWABLE_ACCEPT_REGISTRY_OUTPUT_NAME"] = "custom_curated_support_registry.json"

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_reviewable_support_accept_check.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(capture_path.read_text(encoding="utf-8"))
    outputs = tmp_path / "outputs"
    assert payload["argv"] == [str(outputs / "reviewable-run")]
    assert payload["env"] == {
        "VULD_SUPPORT_REVIEW_PYTHON_BIN": "/tmp/fake_python",
        "VULD_SUPPORT_REVIEW_OUTPUT_ROOT": str(outputs),
        "VULD_SUPPORT_REVIEW_DECISIONS_FILE": str(outputs / "custom_review_decisions.json"),
        "VULD_SUPPORT_REVIEW_REVIEW_OUTPUT_NAME": "custom_review_index.json",
        "VULD_SUPPORT_REVIEW_DECISIONS_OUTPUT_NAME": "custom_review_decisions.json",
        "VULD_SUPPORT_REVIEW_UPDATE_OUTPUT_NAME": "custom_registry_update.json",
        "VULD_SUPPORT_REVIEW_REGISTRY_OUTPUT_NAME": "custom_curated_support_registry.json",
    }
