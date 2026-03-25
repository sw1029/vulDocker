from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_named_support_case_set_supports_helper_override_and_forwards_env(tmp_path: Path) -> None:
    capture_path = tmp_path / "helper_capture.json"
    fake_helper = tmp_path / "support_helper.py"

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
        "VULD_SUPPORT_WORKFLOW_PYTHON_BIN": os.environ.get("VULD_SUPPORT_WORKFLOW_PYTHON_BIN"),
        "VULD_SUPPORT_WORKFLOW_CASES_ROOT": os.environ.get("VULD_SUPPORT_WORKFLOW_CASES_ROOT"),
        "VULD_SUPPORT_WORKFLOW_OUTPUT_ROOT": os.environ.get("VULD_SUPPORT_WORKFLOW_OUTPUT_ROOT"),
        "VULD_SUPPORT_WORKFLOW_MODE": os.environ.get("VULD_SUPPORT_WORKFLOW_MODE"),
        "VULD_SUPPORT_WORKFLOW_ATTEMPTS": os.environ.get("VULD_SUPPORT_WORKFLOW_ATTEMPTS"),
        "VULD_SUPPORT_WORKFLOW_REVIEW_ONLY": os.environ.get("VULD_SUPPORT_WORKFLOW_REVIEW_ONLY"),
        "VULD_SUPPORT_WORKFLOW_DECISIONS_FILE": os.environ.get("VULD_SUPPORT_WORKFLOW_DECISIONS_FILE"),
        "VULD_SUPPORT_WORKFLOW_NO_SNAPSHOT": os.environ.get("VULD_SUPPORT_WORKFLOW_NO_SNAPSHOT"),
        "VULD_SUPPORT_WORKFLOW_ALLOW_REPEAT_FAILURE_WITH_REPORT": os.environ.get("VULD_SUPPORT_WORKFLOW_ALLOW_REPEAT_FAILURE_WITH_REPORT"),
        "VULD_SUPPORT_WORKFLOW_PERMISSION_ARTIFACT_NAME": os.environ.get("VULD_SUPPORT_WORKFLOW_PERMISSION_ARTIFACT_NAME"),
        "VULD_SUPPORT_WORKFLOW_PERMISSION_SUMMARY_NAME": os.environ.get("VULD_SUPPORT_WORKFLOW_PERMISSION_SUMMARY_NAME"),
        "VULD_SUPPORT_WORKFLOW_DOCKER_RETRY_COUNT": os.environ.get("VULD_SUPPORT_WORKFLOW_DOCKER_RETRY_COUNT"),
        "VULD_SUPPORT_WORKFLOW_DOCKER_RETRY_DELAY_SEC": os.environ.get("VULD_SUPPORT_WORKFLOW_DOCKER_RETRY_DELAY_SEC"),
        "VULD_SUPPORT_WORKFLOW_REVIEW_OUTPUT_NAME": os.environ.get("VULD_SUPPORT_WORKFLOW_REVIEW_OUTPUT_NAME"),
        "VULD_SUPPORT_WORKFLOW_DECISIONS_OUTPUT_NAME": os.environ.get("VULD_SUPPORT_WORKFLOW_DECISIONS_OUTPUT_NAME"),
        "VULD_SUPPORT_WORKFLOW_UPDATE_OUTPUT_NAME": os.environ.get("VULD_SUPPORT_WORKFLOW_UPDATE_OUTPUT_NAME"),
        "VULD_SUPPORT_WORKFLOW_REGISTRY_OUTPUT_NAME": os.environ.get("VULD_SUPPORT_WORKFLOW_REGISTRY_OUTPUT_NAME"),
        "VULD_SUPPORT_WORKFLOW_REPEAT_HELPER": os.environ.get("VULD_SUPPORT_WORKFLOW_REPEAT_HELPER"),
        "VULD_SUPPORT_WORKFLOW_REVIEW_HELPER": os.environ.get("VULD_SUPPORT_WORKFLOW_REVIEW_HELPER"),
    }},
}}
Path({str(capture_path)!r}).write_text(json.dumps(payload), encoding="utf-8")
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_NAMED_SUPPORT_HELPER"] = str(fake_helper)
    env["VULD_NAMED_SUPPORT_PYTHON_BIN"] = "/tmp/fake-python"
    env["VULD_NAMED_SUPPORT_CASES_ROOT"] = "/tmp/fake-cases"
    env["VULD_NAMED_SUPPORT_OUTPUT_ROOT"] = "/tmp/fake-output"
    env["VULD_NAMED_SUPPORT_MODE"] = "diverse"
    env["VULD_NAMED_SUPPORT_ATTEMPTS"] = "5"
    env["VULD_NAMED_SUPPORT_REVIEW_ONLY"] = "1"
    env["VULD_NAMED_SUPPORT_DECISIONS_FILE"] = "/tmp/fake-decisions.json"
    env["VULD_NAMED_SUPPORT_NO_SNAPSHOT"] = "1"
    env["VULD_NAMED_SUPPORT_ALLOW_REPEAT_FAILURE_WITH_REPORT"] = "0"
    env["VULD_NAMED_SUPPORT_PERMISSION_ARTIFACT_NAME"] = "custom_permission_marker.txt"
    env["VULD_NAMED_SUPPORT_PERMISSION_SUMMARY_NAME"] = "custom_permission_summary.json"
    env["VULD_NAMED_SUPPORT_DOCKER_RETRY_COUNT"] = "4"
    env["VULD_NAMED_SUPPORT_DOCKER_RETRY_DELAY_SEC"] = "0"
    env["VULD_NAMED_SUPPORT_REVIEW_OUTPUT_NAME"] = "custom_review.json"
    env["VULD_NAMED_SUPPORT_DECISIONS_OUTPUT_NAME"] = "custom_decisions.json"
    env["VULD_NAMED_SUPPORT_UPDATE_OUTPUT_NAME"] = "custom_update.json"
    env["VULD_NAMED_SUPPORT_REGISTRY_OUTPUT_NAME"] = "custom_registry.json"
    env["VULD_NAMED_SUPPORT_REPEAT_HELPER"] = "/tmp/repeat_helper"
    env["VULD_NAMED_SUPPORT_REVIEW_HELPER"] = "/tmp/review_helper"

    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_named_support_case_set.sh"),
            "alpha-case=alpha",
            "beta-case=beta",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(capture_path.read_text(encoding="utf-8"))
    assert payload["argv"] == ["alpha-case=alpha", "beta-case=beta"]
    assert payload["env"] == {
        "VULD_SUPPORT_WORKFLOW_PYTHON_BIN": "/tmp/fake-python",
        "VULD_SUPPORT_WORKFLOW_CASES_ROOT": "/tmp/fake-cases",
        "VULD_SUPPORT_WORKFLOW_OUTPUT_ROOT": "/tmp/fake-output",
        "VULD_SUPPORT_WORKFLOW_MODE": "diverse",
        "VULD_SUPPORT_WORKFLOW_ATTEMPTS": "5",
        "VULD_SUPPORT_WORKFLOW_REVIEW_ONLY": "1",
        "VULD_SUPPORT_WORKFLOW_DECISIONS_FILE": "/tmp/fake-decisions.json",
        "VULD_SUPPORT_WORKFLOW_NO_SNAPSHOT": "1",
        "VULD_SUPPORT_WORKFLOW_ALLOW_REPEAT_FAILURE_WITH_REPORT": "0",
        "VULD_SUPPORT_WORKFLOW_PERMISSION_ARTIFACT_NAME": "custom_permission_marker.txt",
        "VULD_SUPPORT_WORKFLOW_PERMISSION_SUMMARY_NAME": "custom_permission_summary.json",
        "VULD_SUPPORT_WORKFLOW_DOCKER_RETRY_COUNT": "4",
        "VULD_SUPPORT_WORKFLOW_DOCKER_RETRY_DELAY_SEC": "0",
        "VULD_SUPPORT_WORKFLOW_REVIEW_OUTPUT_NAME": "custom_review.json",
        "VULD_SUPPORT_WORKFLOW_DECISIONS_OUTPUT_NAME": "custom_decisions.json",
        "VULD_SUPPORT_WORKFLOW_UPDATE_OUTPUT_NAME": "custom_update.json",
        "VULD_SUPPORT_WORKFLOW_REGISTRY_OUTPUT_NAME": "custom_registry.json",
        "VULD_SUPPORT_WORKFLOW_REPEAT_HELPER": "/tmp/repeat_helper",
        "VULD_SUPPORT_WORKFLOW_REVIEW_HELPER": "/tmp/review_helper",
    }


def test_named_support_case_set_supports_caseset_helper_override(tmp_path: Path) -> None:
    capture_path = tmp_path / "caseset_capture.json"
    caseset_helper = tmp_path / "caseset_helper.py"

    _write_executable(
        caseset_helper,
        f"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
payload = {{
    "argv": sys.argv[1:],
    "target_helper": os.environ.get("VULD_NAMED_CASE_TARGET_HELPER"),
    "log_prefix": os.environ.get("VULD_NAMED_CASE_LOG_PREFIX"),
}}
Path({str(capture_path)!r}).write_text(json.dumps(payload), encoding="utf-8")
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_NAMED_SUPPORT_CASESET_HELPER"] = str(caseset_helper)
    env["VULD_NAMED_SUPPORT_HELPER"] = "/tmp/support_helper"

    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_named_support_case_set.sh"),
            "alpha-case=alpha",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(capture_path.read_text(encoding="utf-8"))
    assert payload == {
        "argv": ["alpha-case=alpha"],
        "target_helper": "/tmp/support_helper",
        "log_prefix": "NAMED-SUPPORT",
    }
