from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_repeatability_case_runner_executes_case_and_returns_context(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    case_dir = tmp_path / "cases" / "alpha-case"
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "expectations.json").write_text("{}", encoding="utf-8")
    fake_python = tmp_path / "fake_python.py"
    capture = tmp_path / "calls.json"
    runtime_txt = tmp_path / "runtime.txt"
    run_dirs_txt = tmp_path / "run_dirs.txt"

    _write_executable(
        fake_python,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path

capture_path = Path({str(capture)!r})
calls = json.loads(capture_path.read_text(encoding="utf-8")) if capture_path.exists() else []
calls.append(sys.argv[1:])
capture_path.write_text(json.dumps(calls), encoding="utf-8")

argv = sys.argv[1:]
if argv and argv[0] == "tests/e2e/repeat_case.py":
    out_dir = Path(argv[argv.index("--output-dir") + 1])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "repeatability_report.json").write_text('{{"passed": true}}', encoding="utf-8")
raise SystemExit(0)
""",
    )

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_repeatability_case_runner.sh")!r}
RUN_DIRS=()
CASE_RUNTIME=()
repeatability_run_case_spec \
  CASE_RUNTIME \
  RUN_DIRS \
  TEST \
  {str(tmp_path / "cases")!r} \
  "alpha-case=alias-out" \
  {str(tmp_path / "outputs")!r} \
  repeat \
  repeatability_report.json \
  {str(fake_python)!r} \
  3 \
  deterministic \
  1 \
  0 \
  2 \
  0 \
  docker_permission_artifact.txt
printf '%s\\n' "${{CASE_RUNTIME[@]}}" > {str(runtime_txt)!r}
printf '%s\\n' "${{RUN_DIRS[@]}}" > {str(run_dirs_txt)!r}
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "[TEST] repeat alpha-case -> " in completed.stdout
    assert runtime_txt.read_text(encoding="utf-8").splitlines() == [
        str(case_dir),
        "alpha-case",
        str(tmp_path / "outputs" / "repeat_alias_out"),
        str(tmp_path / "outputs" / "repeat_alias_out" / "repeatability_report.json"),
    ]
    assert run_dirs_txt.read_text(encoding="utf-8").splitlines() == [
        str(tmp_path / "outputs" / "repeat_alias_out")
    ]
    calls = json.loads(capture.read_text(encoding="utf-8"))
    assert calls[0][0] == "tests/e2e/repeat_case.py"
    assert "--attempts" in calls[0]
    assert "--expectations" in calls[0]
    assert "--no-snapshot" in calls[0]


def test_repeatability_case_runner_retries_transient_docker_failures(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    case_dir = tmp_path / "cases" / "beta-case"
    case_dir.mkdir(parents=True, exist_ok=True)
    fake_python = tmp_path / "fake_python.py"
    state = tmp_path / "state.json"
    capture = tmp_path / "calls.json"

    _write_executable(
        fake_python,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path

state_path = Path({str(state)!r})
capture_path = Path({str(capture)!r})
calls = json.loads(capture_path.read_text(encoding="utf-8")) if capture_path.exists() else []
calls.append(sys.argv[1:])
capture_path.write_text(json.dumps(calls), encoding="utf-8")

payload = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {{"count": 0}}
payload["count"] += 1
state_path.write_text(json.dumps(payload), encoding="utf-8")

argv = sys.argv[1:]
if argv and argv[0] == "tests/e2e/repeat_case.py":
    out_dir = Path(argv[argv.index("--output-dir") + 1])
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "repeatability_report.json"
    if payload["count"] == 1:
        report_path.write_text(
            json.dumps({{
                "passed": False,
                "attempts": [{{"error": "CaseError: docker daemon is not reachable"}}],
            }}),
            encoding="utf-8",
        )
        raise SystemExit(1)
    report_path.write_text('{{"passed": true}}', encoding="utf-8")
raise SystemExit(0)
""",
    )

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_repeatability_case_runner.sh")!r}
RUN_DIRS=()
CASE_RUNTIME=()
repeatability_run_case_spec \
  CASE_RUNTIME \
  RUN_DIRS \
  TEST \
  {str(tmp_path / "cases")!r} \
  "beta-case" \
  {str(tmp_path / "outputs")!r} \
  repeat \
  repeatability_report.json \
  {str(fake_python)!r} \
  2 \
  deterministic \
  0 \
  0 \
  2 \
  0 \
  docker_permission_artifact.txt
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "transient docker readiness failure, retrying (1/2)" in completed.stdout
    calls = json.loads(capture.read_text(encoding="utf-8"))
    assert len(calls) == 2


def test_repeatability_case_runner_continues_with_permission_denied_report(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    case_dir = tmp_path / "cases" / "gamma-case"
    case_dir.mkdir(parents=True, exist_ok=True)
    fake_python = tmp_path / "fake_python.py"
    runtime_txt = tmp_path / "runtime.txt"

    _write_executable(
        fake_python,
        """#!/usr/bin/env python3
import json
import sys
from pathlib import Path

argv = sys.argv[1:]
if argv and argv[0] == "tests/e2e/repeat_case.py":
    out_dir = Path(argv[argv.index("--output-dir") + 1])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "repeatability_report.json").write_text(
        json.dumps({
            "passed": False,
            "attempts": [{"error": "CaseError: docker daemon permission denied"}],
        }),
        encoding="utf-8",
    )
    raise SystemExit(1)
raise SystemExit(0)
""",
    )

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_repeatability_case_runner.sh")!r}
RUN_DIRS=()
CASE_RUNTIME=()
repeatability_run_case_spec \
  CASE_RUNTIME \
  RUN_DIRS \
  TEST \
  {str(tmp_path / "cases")!r} \
  "gamma-case" \
  {str(tmp_path / "outputs")!r} \
  repeat \
  repeatability_report.json \
  {str(fake_python)!r} \
  2 \
  deterministic \
  0 \
  1 \
  2 \
  0 \
  custom_permission_marker.txt
printf '%s\\n' "${{CASE_RUNTIME[@]}}" > {str(runtime_txt)!r}
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "reported docker daemon permission denied; continuing with recorded report" in completed.stdout
    assert runtime_txt.read_text(encoding="utf-8").splitlines() == [
        str(case_dir),
        "gamma-case",
        str(tmp_path / "outputs" / "repeat_gamma_case"),
        str(tmp_path / "outputs" / "repeat_gamma_case" / "repeatability_report.json"),
    ]
    marker = (tmp_path / "outputs" / "repeat_gamma_case" / "custom_permission_marker.txt").read_text(encoding="utf-8")
    assert "case_slug=gamma-case" in marker
    assert "reason=docker daemon permission denied" in marker
