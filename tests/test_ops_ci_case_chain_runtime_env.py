from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_case_chain_runtime_env_supports_defaults(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    capture = tmp_path / "capture.json"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_runtime_env.sh")!r}
case_chain_resolve_runtime_env VULD_TEST deterministic 1 PYTHON_BIN MODE NO_SNAPSHOT
export PYTHON_BIN MODE NO_SNAPSHOT
python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
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
        "python_bin": "python",
        "mode": "deterministic",
        "no_snapshot": "1",
    }


def test_case_chain_runtime_env_supports_overrides(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    capture = tmp_path / "capture.json"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_runtime_env.sh")!r}
export VULD_TEST_PYTHON_BIN=/tmp/custom-python
export VULD_TEST_MODE=diverse
export VULD_TEST_NO_SNAPSHOT=0
case_chain_resolve_runtime_env VULD_TEST deterministic 1 PYTHON_BIN MODE NO_SNAPSHOT
export PYTHON_BIN MODE NO_SNAPSHOT
python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
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
        "python_bin": "/tmp/custom-python",
        "mode": "diverse",
        "no_snapshot": "0",
    }
