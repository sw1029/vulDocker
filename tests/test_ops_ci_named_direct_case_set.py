from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_named_direct_case_set_supports_helper_override_and_forwards_env(tmp_path: Path) -> None:
    capture_path = tmp_path / "helper_capture.json"
    fake_helper = tmp_path / "direct_helper.py"

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
        "VULD_DIRECT_CHAIN_PYTHON_BIN": os.environ.get("VULD_DIRECT_CHAIN_PYTHON_BIN"),
        "VULD_DIRECT_CHAIN_CASES_ROOT": os.environ.get("VULD_DIRECT_CHAIN_CASES_ROOT"),
        "VULD_DIRECT_CHAIN_OUTPUT_ROOT": os.environ.get("VULD_DIRECT_CHAIN_OUTPUT_ROOT"),
        "VULD_DIRECT_CHAIN_MODE": os.environ.get("VULD_DIRECT_CHAIN_MODE"),
        "VULD_DIRECT_CHAIN_NO_SNAPSHOT": os.environ.get("VULD_DIRECT_CHAIN_NO_SNAPSHOT"),
    }},
}}
Path({str(capture_path)!r}).write_text(json.dumps(payload), encoding="utf-8")
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_NAMED_DIRECT_HELPER"] = str(fake_helper)
    env["VULD_NAMED_DIRECT_PYTHON_BIN"] = "/tmp/fake-python"
    env["VULD_NAMED_DIRECT_CASES_ROOT"] = "/tmp/fake-cases"
    env["VULD_NAMED_DIRECT_OUTPUT_ROOT"] = "/tmp/fake-output"
    env["VULD_NAMED_DIRECT_MODE"] = "diverse"
    env["VULD_NAMED_DIRECT_NO_SNAPSHOT"] = "0"

    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_named_direct_case_set.sh"),
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
        "VULD_DIRECT_CHAIN_PYTHON_BIN": "/tmp/fake-python",
        "VULD_DIRECT_CHAIN_CASES_ROOT": "/tmp/fake-cases",
        "VULD_DIRECT_CHAIN_OUTPUT_ROOT": "/tmp/fake-output",
        "VULD_DIRECT_CHAIN_MODE": "diverse",
        "VULD_DIRECT_CHAIN_NO_SNAPSHOT": "0",
    }


def test_named_direct_case_set_supports_caseset_helper_override(tmp_path: Path) -> None:
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
    env["VULD_NAMED_DIRECT_CASESET_HELPER"] = str(caseset_helper)
    env["VULD_NAMED_DIRECT_HELPER"] = "/tmp/direct_helper"

    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_named_direct_case_set.sh"),
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
        "target_helper": "/tmp/direct_helper",
        "log_prefix": "NAMED-DIRECT",
    }
