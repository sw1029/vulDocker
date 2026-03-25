from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_case_chain_profile_target_forward_passes_profile_and_target(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "probe.sh"
    capture = tmp_path / "capture.json"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_profile_target_forward.sh")!r}
target_fn() {{
  export PROFILE_NAME="$1"
  export TARGET_ARG="$2"
  export ARG_ONE="$3"
  python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "profile": os.environ["PROFILE_NAME"],
  "target_arg": os.environ["TARGET_ARG"],
  "arg_one": os.environ["ARG_ONE"],
}}))
PY
}}
case_chain_run_profile_target_forward target_fn direct /tmp/demo alpha
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
        "target_arg": "/tmp/demo",
        "arg_one": "alpha",
    }


def test_case_chain_profile_script_target_forward_resolves_script_dir(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "probe.sh"
    capture = tmp_path / "capture.json"
    fake_script = tmp_path / "ops" / "ci" / "run_demo.sh"
    fake_script.parent.mkdir(parents=True, exist_ok=True)
    fake_script.write_text("", encoding="utf-8")

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_profile_target_forward.sh")!r}
target_fn() {{
  export PROFILE_NAME="$1"
  export TARGET_ARG="$2"
  python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "profile": os.environ["PROFILE_NAME"],
  "target_arg": os.environ["TARGET_ARG"],
}}))
PY
}}
case_chain_run_profile_script_target_forward target_fn repeatability {str(fake_script)!r} alpha
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
        "target_arg": str(fake_script.parent),
    }
