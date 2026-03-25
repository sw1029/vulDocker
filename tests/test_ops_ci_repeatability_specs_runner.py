from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_repeatability_specs_runner_executes_multiple_case_specs_writes_run_dirs_and_emits_completed(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "probe.sh"
    cases_root = tmp_path / "cases"
    alpha = cases_root / "alpha-case"
    beta = cases_root / "beta-case"
    alpha.mkdir(parents=True, exist_ok=True)
    beta.mkdir(parents=True, exist_ok=True)
    (alpha / "expectations.json").write_text("{}", encoding="utf-8")
    fake_python = tmp_path / "fake_python.py"
    capture = tmp_path / "calls.json"
    run_dirs_file = tmp_path / "run_dirs.txt"
    run_dirs_capture = tmp_path / "run_dirs_capture.txt"

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
source {str(REPO_ROOT / "ops/ci/lib_repeatability_specs_runner.sh")!r}
RUN_DIRS=()
repeatability_run_case_specs \
  RUN_DIRS \
  TEST \
  {str(cases_root)!r} \
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
  docker_permission_artifact.txt \
  {str(run_dirs_file)!r} \
  alpha-case \
  beta-case=custom_beta
printf '%s\\n' "${{RUN_DIRS[@]}}" > {str(run_dirs_capture)!r}
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
    assert "[TEST] repeat beta-case -> " in completed.stdout
    assert "[TEST] completed" in completed.stdout
    assert run_dirs_file.read_text(encoding="utf-8").splitlines() == [
        str(tmp_path / "outputs" / "repeat_alpha_case"),
        str(tmp_path / "outputs" / "repeat_custom_beta"),
    ]
    assert run_dirs_capture.read_text(encoding="utf-8").splitlines() == [
        str(tmp_path / "outputs" / "repeat_alpha_case"),
        str(tmp_path / "outputs" / "repeat_custom_beta"),
    ]
    calls = json.loads(capture.read_text(encoding="utf-8"))
    assert len(calls) == 2
    assert "--expectations" in calls[0]
    assert "--expectations" not in calls[1]
    assert "--no-snapshot" in calls[0]


def test_repeatability_specs_runner_propagates_invalid_alias_failure(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    cases_root = tmp_path / "cases"
    (cases_root / "gamma-case").mkdir(parents=True, exist_ok=True)
    fake_python = tmp_path / "fake_python.py"

    _write_executable(fake_python, "#!/usr/bin/env python3\nraise SystemExit(0)\n")
    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_repeatability_specs_runner.sh")!r}
RUN_DIRS=()
repeatability_run_case_specs \
  RUN_DIRS \
  TEST \
  {str(cases_root)!r} \
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
  docker_permission_artifact.txt \
  {str(tmp_path / "run_dirs.txt")!r} \
  gamma-case=bad/alias
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
