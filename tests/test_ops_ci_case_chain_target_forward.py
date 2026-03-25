from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_case_chain_target_forward_passes_all_arguments(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    capture = tmp_path / "capture.json"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_target_forward.sh")!r}
target_fn() {{
  export ARG_ONE="$1"
  export ARG_TWO="$2"
  export ARG_THREE="$3"
  python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "arg_one": os.environ["ARG_ONE"],
  "arg_two": os.environ["ARG_TWO"],
  "arg_three": os.environ["ARG_THREE"],
}}))
PY
}}
case_chain_run_target_forward target_fn alpha beta gamma
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
        "arg_one": "alpha",
        "arg_two": "beta",
        "arg_three": "gamma",
    }


def test_case_chain_target_forward_supports_single_argument(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    capture = tmp_path / "capture.json"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_target_forward.sh")!r}
target_fn() {{
  export ARG_ONE="$1"
  python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "arg_one": os.environ["ARG_ONE"],
}}))
PY
}}
case_chain_run_target_forward target_fn alpha
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
        "arg_one": "alpha",
    }


def test_case_chain_target_forward_propagates_target_failure(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_target_forward.sh")!r}
target_fn() {{
  echo "target forward failed: $1" >&2
  return 31
}}
case_chain_run_target_forward target_fn alpha
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 31
    assert completed.stderr == "target forward failed: alpha\n"
