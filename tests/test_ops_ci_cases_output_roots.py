from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_cases_output_roots_support_defaults(tmp_path: Path) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_cases_output_roots.sh")!r}
resolve_cases_output_roots VULD_TEST /tmp/repo /tmp/default-output CASES_ROOT OUTPUT_ROOT
export CASES_ROOT OUTPUT_ROOT
python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "cases_root": os.environ["CASES_ROOT"],
  "output_root": os.environ["OUTPUT_ROOT"],
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
        "output_root": "/tmp/default-output",
    }


def test_cases_output_roots_support_overrides(tmp_path: Path) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_cases_output_roots.sh")!r}
export VULD_TEST_CASES_ROOT=/tmp/custom-cases
export VULD_TEST_OUTPUT_ROOT=/tmp/custom-output
resolve_cases_output_roots VULD_TEST /tmp/repo /tmp/default-output CASES_ROOT OUTPUT_ROOT
export CASES_ROOT OUTPUT_ROOT
python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "cases_root": os.environ["CASES_ROOT"],
  "output_root": os.environ["OUTPUT_ROOT"],
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
    }
