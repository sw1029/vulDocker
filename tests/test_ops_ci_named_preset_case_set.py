from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_named_preset_case_set_forwards_generated_specs_to_target_helper(tmp_path: Path) -> None:
    capture_path = tmp_path / "capture.json"
    fake_helper = tmp_path / "helper.py"
    _write_executable(
        fake_helper,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path
Path({str(capture_path)!r}).write_text(json.dumps(sys.argv[1:]), encoding="utf-8")
raise SystemExit(0)
""",
    )

    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_named_preset_case_set.sh"),
            "build_positive_pair_case_specs",
            "trusted-case",
            "open-redirect-case",
        ],
        cwd=REPO_ROOT,
        env={
            "PATH": str(Path("/usr/bin")) + ":" + str(Path("/bin")),
            "VULD_NAMED_PRESET_TARGET_HELPER": str(fake_helper),
            "VULD_NAMED_PRESET_LOG_PREFIX": "TEST-PRESET",
        },
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(capture_path.read_text(encoding="utf-8")) == [
        "trusted-case=trusted_dynamic",
        "open-redirect-case=open_redirect_dynamic",
    ]


def test_named_preset_case_set_fails_for_unknown_builder(tmp_path: Path) -> None:
    fake_helper = tmp_path / "helper.py"
    _write_executable(
        fake_helper,
        "#!/usr/bin/env bash\nexit 0\n",
    )

    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_named_preset_case_set.sh"),
            "unknown_builder",
        ],
        cwd=REPO_ROOT,
        env={
            "PATH": str(Path("/usr/bin")) + ":" + str(Path("/bin")),
            "VULD_NAMED_PRESET_TARGET_HELPER": str(fake_helper),
            "VULD_NAMED_PRESET_LOG_PREFIX": "TEST-PRESET",
        },
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "unknown preset builder" in completed.stderr


def test_named_preset_case_set_fails_without_target_helper() -> None:
    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_named_preset_case_set.sh"),
            "build_positive_pair_case_specs",
        ],
        cwd=REPO_ROOT,
        env={
            "PATH": str(Path("/usr/bin")) + ":" + str(Path("/bin")),
            "VULD_NAMED_PRESET_LOG_PREFIX": "TEST-PRESET",
        },
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr == "[TEST-PRESET] target helper is required via VULD_NAMED_PRESET_TARGET_HELPER\n"
