from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_operator_run_support_named_preset_exports_env_and_invokes_preset(tmp_path: Path) -> None:
    preset_helper = tmp_path / "preset_helper.py"
    named_helper = tmp_path / "named_helper.sh"
    support_helper = tmp_path / "support_helper.sh"
    capture_path = tmp_path / "capture.json"

    _write_executable(named_helper, "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(support_helper, "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(
        preset_helper,
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
        "VULD_NAMED_SUPPORT_REVIEW_ONLY": os.environ.get("VULD_NAMED_SUPPORT_REVIEW_ONLY"),
        "VULD_NAMED_SUPPORT_NO_SNAPSHOT": os.environ.get("VULD_NAMED_SUPPORT_NO_SNAPSHOT"),
        "VULD_NAMED_PRESET_TARGET_HELPER": os.environ.get("VULD_NAMED_PRESET_TARGET_HELPER"),
        "VULD_NAMED_PRESET_LOG_PREFIX": os.environ.get("VULD_NAMED_PRESET_LOG_PREFIX"),
    }},
}}
Path({str(capture_path)!r}).write_text(json.dumps(payload), encoding="utf-8")
raise SystemExit(0)
""",
    )

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_operator_support_named_preset.sh')!r}\n"
                "export VULD_TEST_PYTHON_BIN=/tmp/fake-python\n"
                "export VULD_TEST_CASES_ROOT=/tmp/fake-cases\n"
                "export VULD_TEST_OUTPUT_ROOT=/tmp/fake-output\n"
                "export VULD_TEST_MODE=diverse\n"
                "export VULD_TEST_ATTEMPTS=5\n"
                "export VULD_TEST_REVIEW_ONLY=1\n"
                "export VULD_TEST_NO_SNAPSHOT=0\n"
                f"operator_run_support_named_preset VULD_TEST {str(REPO_ROOT / 'tests/e2e/cases')!r} /tmp/default-out {str(named_helper)!r} {str(preset_helper)!r} {str(support_helper)!r} '' '' TEST build_positive_pair_case_specs trusted-case open-redirect-case"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(capture_path.read_text(encoding="utf-8")) == {
        "argv": ["build_positive_pair_case_specs", "trusted-case", "open-redirect-case"],
        "env": {
            "VULD_NAMED_SUPPORT_HELPER": str(support_helper),
            "VULD_NAMED_SUPPORT_PYTHON_BIN": "/tmp/fake-python",
            "VULD_NAMED_SUPPORT_CASES_ROOT": "/tmp/fake-cases",
            "VULD_NAMED_SUPPORT_OUTPUT_ROOT": "/tmp/fake-output",
            "VULD_NAMED_SUPPORT_MODE": "diverse",
            "VULD_NAMED_SUPPORT_ATTEMPTS": "5",
            "VULD_NAMED_SUPPORT_REVIEW_ONLY": "1",
            "VULD_NAMED_SUPPORT_NO_SNAPSHOT": "0",
            "VULD_NAMED_PRESET_TARGET_HELPER": str(named_helper),
            "VULD_NAMED_PRESET_LOG_PREFIX": "TEST",
        },
    }


def test_operator_run_support_named_preset_rejects_missing_preset_helper(tmp_path: Path) -> None:
    missing = tmp_path / "missing.py"
    named_helper = tmp_path / "named_helper.sh"
    support_helper = tmp_path / "support_helper.sh"

    _write_executable(named_helper, "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(support_helper, "#!/usr/bin/env bash\nexit 0\n")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_operator_support_named_preset.sh')!r}\n"
                f"operator_run_support_named_preset VULD_TEST {str(REPO_ROOT / 'tests/e2e/cases')!r} /tmp/default-out {str(named_helper)!r} {str(missing)!r} {str(support_helper)!r} '' '' TEST build_positive_pair_case_specs trusted-case open-redirect-case"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr == f"[TEST] preset helper not found or not executable: {missing}\n"
