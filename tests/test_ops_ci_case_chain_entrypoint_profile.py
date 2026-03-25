from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_case_chain_entrypoint_profile_supports_direct_defaults(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    capture = tmp_path / "capture.json"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_entrypoint_profile.sh")!r}
case_chain_resolve_entrypoint_profile \
  direct \
  {str(REPO_ROOT / "ops/ci")!r} \
  SOURCE_PREFIX \
  REPO_ROOT_OUT \
  DEFAULT_OUTPUT_ROOT \
  USAGE_TEXT \
  LOG_PREFIX
export SOURCE_PREFIX REPO_ROOT_OUT DEFAULT_OUTPUT_ROOT USAGE_TEXT LOG_PREFIX
python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "source_prefix": os.environ["SOURCE_PREFIX"],
  "repo_root": os.environ["REPO_ROOT_OUT"],
  "default_output_root": os.environ["DEFAULT_OUTPUT_ROOT"],
  "usage_text": os.environ["USAGE_TEXT"],
  "log_prefix": os.environ["LOG_PREFIX"],
}}))
PY
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
        "source_prefix": "VULD_DIRECT_CHAIN",
        "repo_root": str(REPO_ROOT),
        "default_output_root": "/tmp/vuld_direct_validation_chain",
        "usage_text": "usage: ops/ci/run_direct_validation_chain.sh <case-slug-or-dir> [<case-slug-or-dir> ...]",
        "log_prefix": "DIRECT-CHAIN",
    }


def test_case_chain_entrypoint_profile_supports_repeatability_defaults(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    capture = tmp_path / "capture.json"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_entrypoint_profile.sh")!r}
case_chain_resolve_entrypoint_profile \
  repeatability \
  {str(REPO_ROOT / "ops/ci")!r} \
  SOURCE_PREFIX \
  REPO_ROOT_OUT \
  DEFAULT_OUTPUT_ROOT \
  USAGE_TEXT \
  LOG_PREFIX
export SOURCE_PREFIX REPO_ROOT_OUT DEFAULT_OUTPUT_ROOT USAGE_TEXT LOG_PREFIX
python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "source_prefix": os.environ["SOURCE_PREFIX"],
  "repo_root": os.environ["REPO_ROOT_OUT"],
  "default_output_root": os.environ["DEFAULT_OUTPUT_ROOT"],
  "usage_text": os.environ["USAGE_TEXT"],
  "log_prefix": os.environ["LOG_PREFIX"],
}}))
PY
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
        "source_prefix": "VULD_REPEAT_CHAIN",
        "repo_root": str(REPO_ROOT),
        "default_output_root": "/tmp/vuld_repeatability_chain",
        "usage_text": "usage: ops/ci/run_repeatability_chain.sh <case-slug-or-dir> [<case-slug-or-dir> ...]",
        "log_prefix": "",
    }


def test_case_chain_entrypoint_profile_rejects_unknown_profile(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_entrypoint_profile.sh")!r}
case_chain_resolve_entrypoint_profile \
  unknown \
  {str(REPO_ROOT / "ops/ci")!r} \
  SOURCE_PREFIX \
  REPO_ROOT_OUT \
  DEFAULT_OUTPUT_ROOT \
  USAGE_TEXT \
  LOG_PREFIX
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr == "unknown case-chain entrypoint profile: unknown\n"
