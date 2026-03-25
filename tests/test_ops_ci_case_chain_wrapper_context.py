from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_case_chain_wrapper_context_supports_defaults(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    capture = tmp_path / "capture.json"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_wrapper_context.sh")!r}
case_chain_prepare_wrapper_context \
  VULD_TEST \
  /tmp/repo \
  {str(tmp_path / "default-out")!r} \
  "usage: demo <case>" \
  deterministic \
  1 \
  CASES_ROOT \
  OUTPUT_ROOT \
  PYTHON_BIN \
  MODE \
  NO_SNAPSHOT \
  alpha-case
export CASES_ROOT OUTPUT_ROOT PYTHON_BIN MODE NO_SNAPSHOT
python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "cases_root": os.environ["CASES_ROOT"],
  "output_root": os.environ["OUTPUT_ROOT"],
  "python_bin": os.environ["PYTHON_BIN"],
  "mode": os.environ["MODE"],
  "no_snapshot": os.environ["NO_SNAPSHOT"],
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
        "cases_root": "/tmp/repo/tests/e2e/cases",
        "output_root": str(tmp_path / "default-out"),
        "python_bin": "python",
        "mode": "deterministic",
        "no_snapshot": "1",
    }


def test_case_chain_wrapper_context_supports_env_overrides(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    capture = tmp_path / "capture.json"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_wrapper_context.sh")!r}
export VULD_TEST_CASES_ROOT=/tmp/custom-cases
export VULD_TEST_OUTPUT_ROOT=/tmp/custom-output
export VULD_TEST_PYTHON_BIN=/tmp/custom-python
export VULD_TEST_MODE=diverse
export VULD_TEST_NO_SNAPSHOT=0
case_chain_prepare_wrapper_context \
  VULD_TEST \
  /tmp/repo \
  {str(tmp_path / "default-out")!r} \
  "usage: demo <case>" \
  deterministic \
  1 \
  CASES_ROOT \
  OUTPUT_ROOT \
  PYTHON_BIN \
  MODE \
  NO_SNAPSHOT \
  alpha-case
export CASES_ROOT OUTPUT_ROOT PYTHON_BIN MODE NO_SNAPSHOT
python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "cases_root": os.environ["CASES_ROOT"],
  "output_root": os.environ["OUTPUT_ROOT"],
  "python_bin": os.environ["PYTHON_BIN"],
  "mode": os.environ["MODE"],
  "no_snapshot": os.environ["NO_SNAPSHOT"],
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
        "cases_root": "/tmp/custom-cases",
        "output_root": "/tmp/custom-output",
        "python_bin": "/tmp/custom-python",
        "mode": "diverse",
        "no_snapshot": "0",
    }
