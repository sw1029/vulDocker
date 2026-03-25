from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_operator_run_pair_named_preset_invokes_named_runner(tmp_path: Path) -> None:
    named_helper = tmp_path / "named_helper.sh"
    preset_helper = tmp_path / "preset_helper.py"
    leaf_helper = tmp_path / "leaf_helper.sh"
    capture_path = tmp_path / "capture.json"

    _write_executable(named_helper, "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(leaf_helper, "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(
        preset_helper,
        f"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
payload = {{
    "argv": sys.argv[1:],
    "export_marker": os.environ.get("TEST_EXPORT_MARKER"),
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
                f"source {str(REPO_ROOT / 'ops/ci/lib_operator_pair_named_preset.sh')!r}\n"
                "test_export_helper() {\n"
                "  export TEST_EXPORT_MARKER=\"$1|$2|$3|$4|$5|$6\"\n"
                "}\n"
                f"operator_run_pair_named_preset SRC /tmp/cases /tmp/out {str(named_helper)!r} {str(preset_helper)!r} {str(leaf_helper)!r} '' '' TEST 'named helper' 'leaf helper' test_export_helper build_positive_pair_case_specs alpha beta"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(capture_path.read_text(encoding="utf-8")) == {
        "argv": ["build_positive_pair_case_specs", "alpha", "beta"],
        "export_marker": f"SRC|/tmp/cases|/tmp/out|{leaf_helper}|{named_helper}|TEST",
    }


def test_operator_run_pair_named_preset_rejects_missing_export_helper(
    tmp_path: Path,
) -> None:
    named_helper = tmp_path / "named_helper.sh"
    preset_helper = tmp_path / "preset_helper.sh"
    leaf_helper = tmp_path / "leaf_helper.sh"

    _write_executable(named_helper, "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(preset_helper, "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(leaf_helper, "#!/usr/bin/env bash\nexit 0\n")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_operator_pair_named_preset.sh')!r}\n"
                f"operator_run_pair_named_preset SRC /tmp/cases /tmp/out {str(named_helper)!r} {str(preset_helper)!r} {str(leaf_helper)!r} '' '' TEST 'named helper' 'leaf helper' missing_export_fn build_positive_pair_case_specs alpha beta"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr == "[TEST] export helper function not found: missing_export_fn\n"
