from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def _write_case(case_dir: Path) -> None:
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "requirement.yml").write_text("requirement_id: TEST\n", encoding="utf-8")


def test_blocked_noop_support_check_supports_case_root_output_and_python_override(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    _write_case(cases_root / "foobar-name-only-negative")
    _write_case(cases_root / "open-redirect-strict-dynamic-no-remote")
    output_root = tmp_path / "outputs"
    capture_path = tmp_path / "python_calls.json"
    fake_python = tmp_path / "fake_python.py"

    _write_executable(
        fake_python,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path
import os

capture_path = Path({str(capture_path)!r})
calls = []
if capture_path.exists():
    calls = json.loads(capture_path.read_text(encoding="utf-8"))
calls.append(sys.argv[1:])
capture_path.write_text(json.dumps(calls, ensure_ascii=False), encoding="utf-8")

argv = sys.argv[1:]
if argv and argv[0] == "tests/e2e/repeat_case.py":
    out_dir = Path(argv[argv.index("--output-dir") + 1])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "support_candidate.json").write_text(
        json.dumps({{"schema_version": "support_candidate@0.1", "case_name": out_dir.name}}, ensure_ascii=False),
        encoding="utf-8",
    )
    raise SystemExit(0)
if argv and argv[0] == "tests/e2e/support_review.py":
    out_path = Path(argv[argv.index("--output") + 1])
    out_path.write_text(
        json.dumps({{"authority_ready_bundle_count": 2, "reviewable_bundle_count": 0}}, ensure_ascii=False),
        encoding="utf-8",
    )
    raise SystemExit(0)
if argv and argv[0] == "tests/e2e/support_decide.py":
    out_path = Path(argv[argv.index("--output") + 1])
    out_path.write_text(
        json.dumps({{"schema_version": "support_registry_update@0.1", "accepted_count": 0}}, ensure_ascii=False),
        encoding="utf-8",
    )
    raise SystemExit(0)
if argv and argv[0] == "tests/e2e/support_apply.py":
    out_path = Path(argv[argv.index("--output") + 1])
    out_path.write_text(
        json.dumps({{"registry_item_count": 0, "schema_status": "normalized"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    raise SystemExit(0)
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_BLOCKED_NOOP_PYTHON_BIN"] = str(fake_python)
    env["VULD_BLOCKED_NOOP_CASES_ROOT"] = str(cases_root)
    env["VULD_BLOCKED_NOOP_OUTPUT_ROOT"] = str(output_root)

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_blocked_noop_support_check.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "[BLOCKED] completed" in completed.stdout
    assert f"[BLOCKED] foobar_out={output_root / 'repeat_foobar'}" in completed.stdout
    assert f"[BLOCKED] strict_out={output_root / 'repeat_strict'}" in completed.stdout
    assert f"[BLOCKED] review_out={output_root / 'support_review.json'}" in completed.stdout
    assert f"[BLOCKED] update_out={output_root / 'support_update.json'}" in completed.stdout
    assert f"[BLOCKED] registry_out={output_root / 'support_registry.json'}" in completed.stdout
    assert (output_root / "repeat_foobar" / "support_candidate.json").exists()
    assert (output_root / "repeat_strict" / "support_candidate.json").exists()
    assert (output_root / "support_review.json").exists()
    assert (output_root / "support_update.json").exists()
    assert (output_root / "support_registry.json").exists()

    calls = json.loads(capture_path.read_text(encoding="utf-8"))
    assert calls[0][0] == "tests/e2e/repeat_case.py"
    assert calls[0][calls[0].index("--case") + 1] == str(cases_root / "foobar-name-only-negative")
    assert calls[1][0] == "tests/e2e/repeat_case.py"
    assert calls[1][calls[1].index("--case") + 1] == str(cases_root / "open-redirect-strict-dynamic-no-remote")
    assert calls[2][0] == "tests/e2e/support_review.py"
    assert calls[3][0] == "tests/e2e/support_decide.py"
    assert calls[4][0] == "tests/e2e/support_apply.py"


def test_blocked_noop_support_check_supports_support_helper_override(tmp_path: Path) -> None:
    capture_path = tmp_path / "helper_capture.json"
    fake_helper = tmp_path / "support_helper.py"

    _write_executable(
        fake_helper,
        f"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
capture = Path({str(capture_path)!r})
payload = {{
    "argv": sys.argv[1:],
    "env": {{
        "VULD_SUPPORT_WORKFLOW_PYTHON_BIN": os.environ.get("VULD_SUPPORT_WORKFLOW_PYTHON_BIN"),
        "VULD_SUPPORT_WORKFLOW_CASES_ROOT": os.environ.get("VULD_SUPPORT_WORKFLOW_CASES_ROOT"),
        "VULD_SUPPORT_WORKFLOW_OUTPUT_ROOT": os.environ.get("VULD_SUPPORT_WORKFLOW_OUTPUT_ROOT"),
        "VULD_SUPPORT_WORKFLOW_MODE": os.environ.get("VULD_SUPPORT_WORKFLOW_MODE"),
        "VULD_SUPPORT_WORKFLOW_ATTEMPTS": os.environ.get("VULD_SUPPORT_WORKFLOW_ATTEMPTS"),
        "VULD_SUPPORT_WORKFLOW_NO_SNAPSHOT": os.environ.get("VULD_SUPPORT_WORKFLOW_NO_SNAPSHOT"),
        "VULD_SUPPORT_WORKFLOW_PERMISSION_ARTIFACT_NAME": os.environ.get("VULD_SUPPORT_WORKFLOW_PERMISSION_ARTIFACT_NAME"),
        "VULD_SUPPORT_WORKFLOW_PERMISSION_SUMMARY_NAME": os.environ.get("VULD_SUPPORT_WORKFLOW_PERMISSION_SUMMARY_NAME"),
        "VULD_SUPPORT_WORKFLOW_DOCKER_RETRY_COUNT": os.environ.get("VULD_SUPPORT_WORKFLOW_DOCKER_RETRY_COUNT"),
        "VULD_SUPPORT_WORKFLOW_DOCKER_RETRY_DELAY_SEC": os.environ.get("VULD_SUPPORT_WORKFLOW_DOCKER_RETRY_DELAY_SEC"),
    }},
}}
capture.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_BLOCKED_NOOP_SUPPORT_HELPER"] = str(fake_helper)
    env["VULD_BLOCKED_NOOP_PYTHON_BIN"] = "/tmp/fake_python"
    env["VULD_BLOCKED_NOOP_CASES_ROOT"] = "/tmp/fake_cases"
    env["VULD_BLOCKED_NOOP_OUTPUT_ROOT"] = "/tmp/fake_output"
    env["VULD_BLOCKED_NOOP_MODE"] = "diverse"
    env["VULD_BLOCKED_NOOP_ATTEMPTS"] = "5"
    env["VULD_BLOCKED_NOOP_NO_SNAPSHOT"] = "1"
    env["VULD_BLOCKED_NOOP_PERMISSION_ARTIFACT_NAME"] = "blocked_permission_marker.txt"
    env["VULD_BLOCKED_NOOP_PERMISSION_SUMMARY_NAME"] = "blocked_permission_summary.json"
    env["VULD_BLOCKED_NOOP_DOCKER_RETRY_COUNT"] = "4"
    env["VULD_BLOCKED_NOOP_DOCKER_RETRY_DELAY_SEC"] = "0"
    env["VULD_BLOCKED_NOOP_FOOBAR_CASE"] = "foobar-case"
    env["VULD_BLOCKED_NOOP_STRICT_CASE"] = "strict-case"

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_blocked_noop_support_check.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(capture_path.read_text(encoding="utf-8"))
    assert payload["argv"] == [
        "foobar-case=foobar",
        "strict-case=strict",
    ]
    assert payload["env"] == {
        "VULD_SUPPORT_WORKFLOW_PYTHON_BIN": "/tmp/fake_python",
        "VULD_SUPPORT_WORKFLOW_CASES_ROOT": "/tmp/fake_cases",
        "VULD_SUPPORT_WORKFLOW_OUTPUT_ROOT": "/tmp/fake_output",
        "VULD_SUPPORT_WORKFLOW_MODE": "diverse",
        "VULD_SUPPORT_WORKFLOW_ATTEMPTS": "5",
        "VULD_SUPPORT_WORKFLOW_NO_SNAPSHOT": "1",
        "VULD_SUPPORT_WORKFLOW_PERMISSION_ARTIFACT_NAME": "blocked_permission_marker.txt",
        "VULD_SUPPORT_WORKFLOW_PERMISSION_SUMMARY_NAME": "blocked_permission_summary.json",
        "VULD_SUPPORT_WORKFLOW_DOCKER_RETRY_COUNT": "4",
        "VULD_SUPPORT_WORKFLOW_DOCKER_RETRY_DELAY_SEC": "0",
    }


def test_blocked_noop_support_check_supports_named_support_helper_override(tmp_path: Path) -> None:
    capture_path = tmp_path / "helper_capture.json"
    fake_helper = tmp_path / "named_support_helper.py"

    _write_executable(
        fake_helper,
        f"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
payload = {{
    "argv": sys.argv[1:],
    "env": {{
        "VULD_NAMED_SUPPORT_HELPER": os.environ.get("VULD_NAMED_SUPPORT_HELPER"),
        "VULD_NAMED_SUPPORT_PYTHON_BIN": os.environ.get("VULD_NAMED_SUPPORT_PYTHON_BIN"),
        "VULD_NAMED_SUPPORT_CASES_ROOT": os.environ.get("VULD_NAMED_SUPPORT_CASES_ROOT"),
        "VULD_NAMED_SUPPORT_OUTPUT_ROOT": os.environ.get("VULD_NAMED_SUPPORT_OUTPUT_ROOT"),
        "VULD_NAMED_SUPPORT_MODE": os.environ.get("VULD_NAMED_SUPPORT_MODE"),
        "VULD_NAMED_SUPPORT_ATTEMPTS": os.environ.get("VULD_NAMED_SUPPORT_ATTEMPTS"),
        "VULD_NAMED_SUPPORT_NO_SNAPSHOT": os.environ.get("VULD_NAMED_SUPPORT_NO_SNAPSHOT"),
        "VULD_NAMED_SUPPORT_PERMISSION_ARTIFACT_NAME": os.environ.get("VULD_NAMED_SUPPORT_PERMISSION_ARTIFACT_NAME"),
        "VULD_NAMED_SUPPORT_PERMISSION_SUMMARY_NAME": os.environ.get("VULD_NAMED_SUPPORT_PERMISSION_SUMMARY_NAME"),
        "VULD_NAMED_SUPPORT_DOCKER_RETRY_COUNT": os.environ.get("VULD_NAMED_SUPPORT_DOCKER_RETRY_COUNT"),
        "VULD_NAMED_SUPPORT_DOCKER_RETRY_DELAY_SEC": os.environ.get("VULD_NAMED_SUPPORT_DOCKER_RETRY_DELAY_SEC"),
    }},
}}
Path({str(capture_path)!r}).write_text(json.dumps(payload), encoding="utf-8")
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_BLOCKED_NOOP_NAMED_SUPPORT_HELPER"] = str(fake_helper)
    env["VULD_BLOCKED_NOOP_SUPPORT_HELPER"] = "/tmp/support_helper"
    env["VULD_BLOCKED_NOOP_PYTHON_BIN"] = "/tmp/fake-python"
    env["VULD_BLOCKED_NOOP_CASES_ROOT"] = "/tmp/fake-cases"
    env["VULD_BLOCKED_NOOP_OUTPUT_ROOT"] = "/tmp/fake-output"
    env["VULD_BLOCKED_NOOP_MODE"] = "diverse"
    env["VULD_BLOCKED_NOOP_ATTEMPTS"] = "5"
    env["VULD_BLOCKED_NOOP_NO_SNAPSHOT"] = "1"
    env["VULD_BLOCKED_NOOP_PERMISSION_ARTIFACT_NAME"] = "blocked_permission_marker.txt"
    env["VULD_BLOCKED_NOOP_PERMISSION_SUMMARY_NAME"] = "blocked_permission_summary.json"
    env["VULD_BLOCKED_NOOP_DOCKER_RETRY_COUNT"] = "4"
    env["VULD_BLOCKED_NOOP_DOCKER_RETRY_DELAY_SEC"] = "0"
    env["VULD_BLOCKED_NOOP_FOOBAR_CASE"] = "foobar-case"
    env["VULD_BLOCKED_NOOP_STRICT_CASE"] = "strict-case"

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_blocked_noop_support_check.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(capture_path.read_text(encoding="utf-8"))
    assert payload["argv"] == ["foobar-case=foobar", "strict-case=strict"]
    assert payload["env"] == {
        "VULD_NAMED_SUPPORT_HELPER": "/tmp/support_helper",
        "VULD_NAMED_SUPPORT_PYTHON_BIN": "/tmp/fake-python",
        "VULD_NAMED_SUPPORT_CASES_ROOT": "/tmp/fake-cases",
        "VULD_NAMED_SUPPORT_OUTPUT_ROOT": "/tmp/fake-output",
        "VULD_NAMED_SUPPORT_MODE": "diverse",
        "VULD_NAMED_SUPPORT_ATTEMPTS": "5",
        "VULD_NAMED_SUPPORT_NO_SNAPSHOT": "1",
        "VULD_NAMED_SUPPORT_PERMISSION_ARTIFACT_NAME": "blocked_permission_marker.txt",
        "VULD_NAMED_SUPPORT_PERMISSION_SUMMARY_NAME": "blocked_permission_summary.json",
        "VULD_NAMED_SUPPORT_DOCKER_RETRY_COUNT": "4",
        "VULD_NAMED_SUPPORT_DOCKER_RETRY_DELAY_SEC": "0",
    }


def test_blocked_noop_support_check_supports_preset_helper_override(tmp_path: Path) -> None:
    capture_path = tmp_path / "preset_capture.json"
    fake_helper = tmp_path / "preset_helper.py"

    _write_executable(
        fake_helper,
        f"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
payload = {{
    "argv": sys.argv[1:],
    "env": {{
        "VULD_NAMED_PRESET_TARGET_HELPER": os.environ.get("VULD_NAMED_PRESET_TARGET_HELPER"),
        "VULD_NAMED_PRESET_LOG_PREFIX": os.environ.get("VULD_NAMED_PRESET_LOG_PREFIX"),
    }},
}}
Path({str(capture_path)!r}).write_text(json.dumps(payload), encoding="utf-8")
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_BLOCKED_NOOP_PRESET_HELPER"] = str(fake_helper)
    env["VULD_BLOCKED_NOOP_NAMED_SUPPORT_HELPER"] = "/tmp/named-support"
    env["VULD_BLOCKED_NOOP_FOOBAR_CASE"] = "foobar-case"
    env["VULD_BLOCKED_NOOP_STRICT_CASE"] = "strict-case"

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_blocked_noop_support_check.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(capture_path.read_text(encoding="utf-8"))
    assert payload["argv"] == [
        "build_blocked_noop_case_specs",
        "foobar-case",
        "strict-case",
    ]
    assert payload["env"] == {
        "VULD_NAMED_PRESET_TARGET_HELPER": "/tmp/named-support",
        "VULD_NAMED_PRESET_LOG_PREFIX": "BLOCKED",
    }
