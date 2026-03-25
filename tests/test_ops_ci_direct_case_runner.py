from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_direct_case_runner_executes_case_and_returns_context(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    case_dir = tmp_path / "cases" / "alpha-case"
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "expectations.json").write_text("{}", encoding="utf-8")
    fake_python = tmp_path / "fake_python.py"
    capture = tmp_path / "calls.json"
    runtime_txt = tmp_path / "runtime.txt"

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
if argv and argv[0] == "tests/e2e/run_case.py":
    out_dir = Path(argv[argv.index("--output-dir") + 1])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text('{{"ok": true}}', encoding="utf-8")
raise SystemExit(0)
""",
    )

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_direct_case_runner.sh")!r}
CASE_RUNTIME=()
direct_run_case_spec \
  CASE_RUNTIME \
  TEST \
  {str(fake_python)!r} \
  {str(tmp_path / "cases")!r} \
  "alpha-case" \
  {str(tmp_path / "outputs")!r} \
  deterministic \
  1
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
    assert "[TEST] alpha-case -> " in completed.stdout
    assert (tmp_path / "outputs" / "run_alpha_case" / "summary.json").exists()
    assert runtime_txt.read_text(encoding="utf-8").splitlines() == [
        str(case_dir),
        "alpha-case",
        str(tmp_path / "outputs" / "run_alpha_case"),
    ]
    calls = json.loads(capture.read_text(encoding="utf-8"))
    assert calls[0][0] == "tests/e2e/run_case.py"
    assert "--expectations" in calls[0]
    assert "--no-snapshot" in calls[0]


def test_direct_case_runner_supports_alias_output_name(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    case_dir = tmp_path / "cases" / "beta-case"
    case_dir.mkdir(parents=True, exist_ok=True)
    fake_python = tmp_path / "fake_python.py"
    output_capture = tmp_path / "output.txt"

    _write_executable(
        fake_python,
        """#!/usr/bin/env python3
import sys
from pathlib import Path
argv = sys.argv[1:]
if argv and argv[0] == "tests/e2e/run_case.py":
    out_dir = Path(argv[argv.index("--output-dir") + 1])
    out_dir.mkdir(parents=True, exist_ok=True)
raise SystemExit(0)
""",
    )

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_direct_case_runner.sh")!r}
CASE_RUNTIME=()
direct_run_case_spec \
  CASE_RUNTIME \
  TEST \
  {str(fake_python)!r} \
  {str(tmp_path / "cases")!r} \
  "beta-case=custom_out" \
  {str(tmp_path / "outputs")!r} \
  deterministic \
  0
printf '%s' "${{CASE_RUNTIME[2]}}" > {str(output_capture)!r}
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert output_capture.read_text(encoding="utf-8") == str(tmp_path / "outputs" / "custom_out")


def test_direct_case_runner_propagates_invalid_alias_failure(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    case_dir = tmp_path / "cases" / "gamma-case"
    case_dir.mkdir(parents=True, exist_ok=True)
    fake_python = tmp_path / "fake_python.py"

    _write_executable(fake_python, "#!/usr/bin/env python3\nraise SystemExit(0)\n")
    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_direct_case_runner.sh")!r}
CASE_RUNTIME=()
direct_run_case_spec \
  CASE_RUNTIME \
  TEST \
  {str(fake_python)!r} \
  {str(tmp_path / "cases")!r} \
  "gamma-case=bad/alias" \
  {str(tmp_path / "outputs")!r} \
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
