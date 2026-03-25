from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_repeatability_case_runtime_prepares_context_command_and_run_dirs(tmp_path: Path) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"
    case_dir = tmp_path / "cases" / "alpha-case"
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "expectations.json").write_text("{}", encoding="utf-8")

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_repeatability_case_runtime.sh")!r}
RUN_DIRS=()
CASE_RUNTIME=()
CMD=()
repeatability_prepare_case_runtime \
  CASE_RUNTIME \
  CMD \
  RUN_DIRS \
  TEST \
  {str(tmp_path / "cases")!r} \
  "alpha-case=alias-output" \
  {str(tmp_path / "outputs")!r} \
  repeat \
  repeatability_report.json \
  python \
  3 \
  deterministic \
  1
export CASE_DIR="${{CASE_RUNTIME[0]}}"
export CASE_SLUG="${{CASE_RUNTIME[1]}}"
export CASE_OUT="${{CASE_RUNTIME[2]}}"
export REPORT_PATH="${{CASE_RUNTIME[3]}}"
python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "case_dir": os.environ["CASE_DIR"],
  "case_slug": os.environ["CASE_SLUG"],
  "case_out": os.environ["CASE_OUT"],
  "report_path": os.environ["REPORT_PATH"],
  "run_dirs": os.environ.get("RUN_DIRS_CAPTURE", "").splitlines(),
}}))
PY
printf '%s\\n' "${{RUN_DIRS[@]}}" > {str(tmp_path / "run_dirs.txt")!r}
printf '%s\\n' "${{CMD[@]}}" > {str(tmp_path / "cmd.txt")!r}
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(capture.read_text(encoding="utf-8"))
    assert payload["case_dir"] == str(case_dir)
    assert payload["case_slug"] == "alpha-case"
    assert payload["case_out"] == str(tmp_path / "outputs" / "repeat_alias_output")
    assert payload["report_path"] == str(tmp_path / "outputs" / "repeat_alias_output" / "repeatability_report.json")
    assert (tmp_path / "run_dirs.txt").read_text(encoding="utf-8").splitlines() == [
        str(tmp_path / "outputs" / "repeat_alias_output")
    ]
    cmd_lines = (tmp_path / "cmd.txt").read_text(encoding="utf-8").splitlines()
    assert cmd_lines[:4] == ["python", "tests/e2e/repeat_case.py", "--attempts", "3"]
    assert "--expectations" in cmd_lines
    assert "--no-snapshot" in cmd_lines


def test_repeatability_case_runtime_supports_default_output_name(tmp_path: Path) -> None:
    capture = tmp_path / "capture.txt"
    probe = tmp_path / "probe.sh"
    case_dir = tmp_path / "cases" / "beta-case"
    case_dir.mkdir(parents=True, exist_ok=True)

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_repeatability_case_runtime.sh")!r}
RUN_DIRS=()
CASE_RUNTIME=()
CMD=()
repeatability_prepare_case_runtime \
  CASE_RUNTIME \
  CMD \
  RUN_DIRS \
  TEST \
  {str(tmp_path / "cases")!r} \
  "beta-case" \
  {str(tmp_path / "outputs")!r} \
  repeat \
  repeatability_report.json \
  python \
  2 \
  deterministic \
  0
printf '%s' "${{CASE_RUNTIME[2]}}" > {str(capture)!r}
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert capture.read_text(encoding="utf-8") == str(tmp_path / "outputs" / "repeat_beta_case")


def test_repeatability_case_runtime_propagates_invalid_alias_failure(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    case_dir = tmp_path / "cases" / "gamma-case"
    case_dir.mkdir(parents=True, exist_ok=True)

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_repeatability_case_runtime.sh")!r}
RUN_DIRS=()
CASE_RUNTIME=()
CMD=()
repeatability_prepare_case_runtime \
  CASE_RUNTIME \
  CMD \
  RUN_DIRS \
  TEST \
  {str(tmp_path / "cases")!r} \
  "gamma-case=bad/alias" \
  {str(tmp_path / "outputs")!r} \
  repeat \
  repeatability_report.json \
  python \
  2 \
  deterministic \
  0
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr == "[TEST] alias must not contain '/': bad/alias\n"
