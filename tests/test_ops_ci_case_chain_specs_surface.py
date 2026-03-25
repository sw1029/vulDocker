from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_case_chain_specs_surface_supports_direct_specs(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    cases_root = tmp_path / "cases"
    alpha = cases_root / "alpha-case"
    alpha.mkdir(parents=True, exist_ok=True)
    (alpha / "expectations.json").write_text("{}", encoding="utf-8")
    fake_python = tmp_path / "fake_python.py"
    capture = tmp_path / "calls.json"

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
source {str(REPO_ROOT / "ops/ci/lib_case_chain_specs_surface.sh")!r}
case_chain_run_direct_specs_surface \
  TEST \
  {str(fake_python)!r} \
  {str(cases_root)!r} \
  {str(tmp_path / "outputs")!r} \
  deterministic \
  1 \
  alpha-case
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert (tmp_path / "outputs" / "run_alpha_case" / "summary.json").exists()
    calls = json.loads(capture.read_text(encoding="utf-8"))
    assert calls[0][0] == "tests/e2e/run_case.py"


def test_case_chain_specs_surface_supports_repeatability_specs(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    cases_root = tmp_path / "cases"
    alpha = cases_root / "alpha-case"
    alpha.mkdir(parents=True, exist_ok=True)
    (alpha / "expectations.json").write_text("{}", encoding="utf-8")
    fake_python = tmp_path / "fake_python.py"
    capture = tmp_path / "calls.json"
    run_dirs_file = tmp_path / "run_dirs.txt"

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
source {str(REPO_ROOT / "ops/ci/lib_case_chain_specs_surface.sh")!r}
RUN_DIRS=()
case_chain_run_repeatability_specs_surface \
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
  {str(run_dirs_file)!r} \
  alpha-case
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert (tmp_path / "outputs" / "repeat_alpha_case" / "repeatability_report.json").exists()
    assert run_dirs_file.read_text(encoding="utf-8").splitlines() == [
        str(tmp_path / "outputs" / "repeat_alpha_case")
    ]
    calls = json.loads(capture.read_text(encoding="utf-8"))
    assert calls[0][0] == "tests/e2e/repeat_case.py"
