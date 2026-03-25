from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_case_chain_main_script_supports_direct_profile(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    capture = tmp_path / "capture.json"
    fake_script = tmp_path / "ops" / "ci" / "run_direct_validation_chain.sh"
    fake_script.parent.mkdir(parents=True, exist_ok=True)
    fake_script.write_text("", encoding="utf-8")

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_main_script.sh")!r}
case_chain_run_main() {{
  export PROFILE_NAME="$1"
  export SCRIPT_DIR_OUT="$2"
  python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "profile": os.environ["PROFILE_NAME"],
  "script_dir": os.environ["SCRIPT_DIR_OUT"],
}}))
PY
}}
case_chain_run_main_script direct {str(fake_script)!r} alpha-case
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
        "script_dir": str(fake_script.parent),
    }


def test_case_chain_main_script_supports_repeatability_profile(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    capture = tmp_path / "capture.json"
    fake_script = tmp_path / "ops" / "ci" / "run_repeatability_chain.sh"
    fake_script.parent.mkdir(parents=True, exist_ok=True)
    fake_script.write_text("", encoding="utf-8")

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_main_script.sh")!r}
case_chain_run_main() {{
  export PROFILE_NAME="$1"
  export SCRIPT_DIR_OUT="$2"
  python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "profile": os.environ["PROFILE_NAME"],
  "script_dir": os.environ["SCRIPT_DIR_OUT"],
}}))
PY
}}
case_chain_run_main_script repeatability {str(fake_script)!r} alpha-case
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
        "script_dir": str(fake_script.parent),
    }
