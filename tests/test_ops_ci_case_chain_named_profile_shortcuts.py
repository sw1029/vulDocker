from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_case_chain_named_profile_shortcuts_forward_named_profile(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "probe.sh"
    capture = tmp_path / "capture.json"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_named_profile_shortcuts.sh")!r}
target_fn() {{
  export PROFILE_NAME="$1"
  export ARG_ONE="$2"
  python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "profile": os.environ["PROFILE_NAME"],
  "arg_one": os.environ["ARG_ONE"],
}}))
PY
}}
case_chain_run_named_profile_target target_fn custom alpha
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
        "arg_one": "alpha",
    }


def test_case_chain_named_profile_shortcuts_support_fixed_profile(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "probe.sh"
    capture = tmp_path / "capture.json"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_named_profile_shortcuts.sh")!r}
target_fn() {{
  export PROFILE_NAME="$1"
  export ARG_ONE="$2"
  python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "profile": os.environ["PROFILE_NAME"],
  "arg_one": os.environ["ARG_ONE"],
}}))
PY
}}
case_chain_run_fixed_named_profile_target target_fn fixed alpha
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
        "profile": "fixed",
        "arg_one": "alpha",
    }


def test_case_chain_named_profile_shortcuts_support_direct_profile(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "probe.sh"
    capture = tmp_path / "capture.json"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_named_profile_shortcuts.sh")!r}
target_fn() {{
  export PROFILE_NAME="$1"
  export ARG_ONE="$2"
  python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "profile": os.environ["PROFILE_NAME"],
  "arg_one": os.environ["ARG_ONE"],
}}))
PY
}}
case_chain_run_direct_named_profile_target target_fn alpha
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
        "arg_one": "alpha",
    }


def test_case_chain_named_profile_shortcuts_support_repeatability_profile(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "probe.sh"
    capture = tmp_path / "capture.json"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_named_profile_shortcuts.sh")!r}
target_fn() {{
  export PROFILE_NAME="$1"
  export ARG_ONE="$2"
  python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "profile": os.environ["PROFILE_NAME"],
  "arg_one": os.environ["ARG_ONE"],
}}))
PY
}}
case_chain_run_repeatability_named_profile_target target_fn beta
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
        "arg_one": "beta",
    }
