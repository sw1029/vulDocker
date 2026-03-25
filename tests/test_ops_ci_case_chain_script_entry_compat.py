from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_case_chain_script_entry_compat_supports_named_script_entry(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "probe.sh"
    capture = tmp_path / "capture.json"
    fake_script = tmp_path / "ops" / "ci" / "run_custom.sh"
    fake_script.parent.mkdir(parents=True, exist_ok=True)
    fake_script.write_text("", encoding="utf-8")

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_script_entry_compat.sh")!r}
case_chain_run_main_script() {{
  export PROFILE_NAME="$1"
  export SCRIPT_PATH="$2"
  python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "profile": os.environ["PROFILE_NAME"],
  "script_path": os.environ["SCRIPT_PATH"],
}}))
PY
}}
case_chain_run_named_script_entry custom {str(fake_script)!r} alpha-case
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(capture.read_text(encoding="utf-8")) == {
        "profile": "custom",
        "script_path": str(fake_script),
    }


def test_case_chain_script_entry_compat_supports_direct_script_entry(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "probe.sh"
    capture = tmp_path / "capture.json"
    fake_script = tmp_path / "ops" / "ci" / "run_direct_validation_chain.sh"
    fake_script.parent.mkdir(parents=True, exist_ok=True)
    fake_script.write_text("", encoding="utf-8")

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_script_entry_compat.sh")!r}
case_chain_run_main_script() {{
  export PROFILE_NAME="$1"
  export SCRIPT_PATH="$2"
  python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "profile": os.environ["PROFILE_NAME"],
  "script_path": os.environ["SCRIPT_PATH"],
}}))
PY
}}
case_chain_run_direct_script_entry {str(fake_script)!r} alpha-case
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(capture.read_text(encoding="utf-8")) == {
        "profile": "direct",
        "script_path": str(fake_script),
    }


def test_case_chain_script_entry_compat_supports_repeatability_script_entry(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "probe.sh"
    capture = tmp_path / "capture.json"
    fake_script = tmp_path / "ops" / "ci" / "run_repeatability_chain.sh"
    fake_script.parent.mkdir(parents=True, exist_ok=True)
    fake_script.write_text("", encoding="utf-8")

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_script_entry_compat.sh")!r}
case_chain_run_main_script() {{
  export PROFILE_NAME="$1"
  export SCRIPT_PATH="$2"
  python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "profile": os.environ["PROFILE_NAME"],
  "script_path": os.environ["SCRIPT_PATH"],
}}))
PY
}}
case_chain_run_repeatability_script_entry {str(fake_script)!r} alpha-case
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(capture.read_text(encoding="utf-8")) == {
        "profile": "repeatability",
        "script_path": str(fake_script),
    }
