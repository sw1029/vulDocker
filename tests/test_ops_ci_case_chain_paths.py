from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_case_chain_paths_resolves_defaults_and_prepares_output_root(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    capture = tmp_path / "capture.json"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_paths.sh")!r}
case_chain_prepare_cases_output_root \
  VULD_TEST \
  /tmp/repo \
  {str(tmp_path / "default-out")!r} \
  "usage: demo <case>" \
  CASES_ROOT \
  OUTPUT_ROOT \
  alpha-case
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
        "output_root": str(tmp_path / "default-out"),
    }
    assert (tmp_path / "default-out").is_dir()


def test_case_chain_paths_supports_env_overrides(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    capture = tmp_path / "capture.json"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_paths.sh")!r}
export VULD_TEST_CASES_ROOT=/tmp/custom-cases
export VULD_TEST_OUTPUT_ROOT=/tmp/custom-output
case_chain_prepare_cases_output_root \
  VULD_TEST \
  /tmp/repo \
  {str(tmp_path / "default-out")!r} \
  "usage: demo <case>" \
  CASES_ROOT \
  OUTPUT_ROOT \
  alpha-case
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


def test_case_chain_paths_rejects_missing_case_specs(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_paths.sh")!r}
case_chain_prepare_cases_output_root \
  VULD_TEST \
  /tmp/repo \
  {str(tmp_path / "default-out")!r} \
  "usage: demo <case>" \
  CASES_ROOT \
  OUTPUT_ROOT
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr == "usage: demo <case>\n"
