from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_operator_run_direct_pair_check_resolves_cases_and_emits_output_notes(
    tmp_path: Path,
) -> None:
    preset_helper = tmp_path / "preset_helper.py"
    named_helper = tmp_path / "named_helper.sh"
    direct_helper = tmp_path / "direct_helper.sh"
    capture_path = tmp_path / "capture.json"

    _write_executable(named_helper, "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(direct_helper, "#!/usr/bin/env bash\nexit 0\n")
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
        "VULD_NAMED_DIRECT_HELPER": os.environ.get("VULD_NAMED_DIRECT_HELPER"),
        "VULD_NAMED_DIRECT_CASES_ROOT": os.environ.get("VULD_NAMED_DIRECT_CASES_ROOT"),
        "VULD_NAMED_DIRECT_OUTPUT_ROOT": os.environ.get("VULD_NAMED_DIRECT_OUTPUT_ROOT"),
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
                f"source {str(REPO_ROOT / 'ops/ci/lib_operator_direct_case_check.sh')!r}\n"
                f"export VULD_TEST_NAMED_DIRECT_HELPER={str(named_helper)!r}\n"
                f"export VULD_TEST_PRESET_HELPER={str(preset_helper)!r}\n"
                f"export VULD_TEST_DIRECT_HELPER={str(direct_helper)!r}\n"
                "export VULD_TEST_CASE_A=alpha-case\n"
                "export VULD_TEST_CASE_B=beta-case\n"
                "operator_run_direct_pair_check "
                f"VULD_TEST {str(REPO_ROOT / 'ops/ci')!r} "
                "/tmp/fake-cases "
                "/tmp/default-output "
                "VULD_TEST_NAMED_DIRECT_HELPER "
                "VULD_TEST_PRESET_HELPER "
                "VULD_TEST_DIRECT_HELPER "
                "VULD_TEST_CASE_A alpha-default "
                "VULD_TEST_CASE_B beta-default "
                "TEST build_positive_pair_case_specs "
                "first_out repeat_first "
                "second_out repeat_second\n"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines() == [
        "[TEST] completed",
        "[TEST] first_out=/tmp/default-output/repeat_first",
        "[TEST] second_out=/tmp/default-output/repeat_second",
    ]
    assert json.loads(capture_path.read_text(encoding="utf-8")) == {
        "argv": ["build_positive_pair_case_specs", "alpha-case", "beta-case"],
        "env": {
            "VULD_NAMED_DIRECT_HELPER": str(direct_helper),
            "VULD_NAMED_DIRECT_CASES_ROOT": "/tmp/fake-cases",
            "VULD_NAMED_DIRECT_OUTPUT_ROOT": "/tmp/default-output",
            "VULD_NAMED_PRESET_TARGET_HELPER": str(named_helper),
            "VULD_NAMED_PRESET_LOG_PREFIX": "TEST",
        },
    }


def test_operator_run_direct_triple_check_resolves_cases_and_emits_output_notes(
    tmp_path: Path,
) -> None:
    preset_helper = tmp_path / "preset_helper.py"
    named_helper = tmp_path / "named_helper.sh"
    direct_helper = tmp_path / "direct_helper.sh"
    capture_path = tmp_path / "capture.json"

    _write_executable(named_helper, "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(direct_helper, "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(
        preset_helper,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path
payload = {{
    "argv": sys.argv[1:],
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
                f"source {str(REPO_ROOT / 'ops/ci/lib_operator_direct_case_check.sh')!r}\n"
                f"export VULD_TEST_NAMED_DIRECT_HELPER={str(named_helper)!r}\n"
                f"export VULD_TEST_PRESET_HELPER={str(preset_helper)!r}\n"
                f"export VULD_TEST_DIRECT_HELPER={str(direct_helper)!r}\n"
                "export VULD_TEST_CASE_A=alpha-case\n"
                "export VULD_TEST_CASE_B=beta-case\n"
                "export VULD_TEST_CASE_C=gamma-case\n"
                "operator_run_direct_triple_check "
                f"VULD_TEST {str(REPO_ROOT / 'ops/ci')!r} "
                "/tmp/fake-cases "
                "/tmp/default-output "
                "VULD_TEST_NAMED_DIRECT_HELPER "
                "VULD_TEST_PRESET_HELPER "
                "VULD_TEST_DIRECT_HELPER "
                "VULD_TEST_CASE_A alpha-default "
                "VULD_TEST_CASE_B beta-default "
                "VULD_TEST_CASE_C gamma-default "
                "TEST build_low_cost_case_specs "
                "first_out repeat_first "
                "second_out repeat_second "
                "third_out repeat_third\n"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines() == [
        "[TEST] completed",
        "[TEST] first_out=/tmp/default-output/repeat_first",
        "[TEST] second_out=/tmp/default-output/repeat_second",
        "[TEST] third_out=/tmp/default-output/repeat_third",
    ]
    assert json.loads(capture_path.read_text(encoding="utf-8")) == {
        "argv": ["build_low_cost_case_specs", "alpha-case", "beta-case", "gamma-case"],
    }


def test_operator_run_direct_pair_check_rejects_missing_preset_helper(tmp_path: Path) -> None:
    missing = tmp_path / "missing.py"
    named_helper = tmp_path / "named_helper.sh"
    direct_helper = tmp_path / "direct_helper.sh"

    _write_executable(named_helper, "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(direct_helper, "#!/usr/bin/env bash\nexit 0\n")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_operator_direct_case_check.sh')!r}\n"
                "set -euo pipefail\n"
                f"export VULD_TEST_NAMED_DIRECT_HELPER={str(named_helper)!r}\n"
                f"export VULD_TEST_PRESET_HELPER={str(missing)!r}\n"
                f"export VULD_TEST_DIRECT_HELPER={str(direct_helper)!r}\n"
                "operator_run_direct_pair_check "
                f"VULD_TEST {str(REPO_ROOT / 'ops/ci')!r} "
                "/tmp/fake-cases "
                "/tmp/default-output "
                "VULD_TEST_NAMED_DIRECT_HELPER "
                "VULD_TEST_PRESET_HELPER "
                "VULD_TEST_DIRECT_HELPER "
                "VULD_TEST_CASE_A alpha-default "
                "VULD_TEST_CASE_B beta-default "
                "TEST build_positive_pair_case_specs "
                "first_out repeat_first\n"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr == f"[TEST] preset helper not found or not executable: {missing}\n"
