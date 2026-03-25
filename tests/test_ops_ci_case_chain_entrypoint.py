from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def _write_case(case_dir: Path, *, with_expectations: bool = False) -> None:
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "requirement.yml").write_text("requirement_id: TEST\n", encoding="utf-8")
    if with_expectations:
        (case_dir / "expectations.json").write_text("{}", encoding="utf-8")


def test_case_chain_entrypoint_supports_direct_entrypoint(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    _write_case(cases_root / "alpha-case", with_expectations=True)
    output_root = tmp_path / "outputs"
    capture_path = tmp_path / "python_calls.json"
    fake_python = tmp_path / "fake_python.py"
    probe = tmp_path / "probe.sh"

    _write_executable(
        fake_python,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path

capture_path = Path({str(capture_path)!r})
calls = json.loads(capture_path.read_text(encoding="utf-8")) if capture_path.exists() else []
calls.append(sys.argv[1:])
capture_path.write_text(json.dumps(calls, ensure_ascii=False), encoding="utf-8")

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
source {str(REPO_ROOT / "ops/ci/lib_case_chain_entrypoint.sh")!r}
case_chain_run_direct_entrypoint {str(REPO_ROOT / "ops/ci")!r} alpha-case
""",
    )

    env = os.environ.copy()
    env["VULD_DIRECT_CHAIN_PYTHON_BIN"] = str(fake_python)
    env["VULD_DIRECT_CHAIN_CASES_ROOT"] = str(cases_root)
    env["VULD_DIRECT_CHAIN_OUTPUT_ROOT"] = str(output_root)

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert (output_root / "run_alpha_case" / "summary.json").exists()
    calls = json.loads(capture_path.read_text(encoding="utf-8"))
    assert calls[0][0] == "tests/e2e/run_case.py"


def test_case_chain_entrypoint_supports_repeatability_entrypoint(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    _write_case(cases_root / "alpha-case", with_expectations=True)
    output_root = tmp_path / "outputs"
    capture_path = tmp_path / "python_calls.json"
    run_dirs_file = tmp_path / "run_dirs.txt"
    fake_python = tmp_path / "fake_python.py"
    probe = tmp_path / "probe.sh"

    _write_executable(
        fake_python,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path

capture_path = Path({str(capture_path)!r})
calls = json.loads(capture_path.read_text(encoding="utf-8")) if capture_path.exists() else []
calls.append(sys.argv[1:])
capture_path.write_text(json.dumps(calls, ensure_ascii=False), encoding="utf-8")

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
source {str(REPO_ROOT / "ops/ci/lib_case_chain_entrypoint.sh")!r}
case_chain_run_repeatability_entrypoint {str(REPO_ROOT / "ops/ci")!r} alpha-case
""",
    )

    env = os.environ.copy()
    env["VULD_REPEAT_CHAIN_PYTHON_BIN"] = str(fake_python)
    env["VULD_REPEAT_CHAIN_CASES_ROOT"] = str(cases_root)
    env["VULD_REPEAT_CHAIN_OUTPUT_ROOT"] = str(output_root)
    env["VULD_REPEAT_CHAIN_RUN_DIRS_FILE"] = str(run_dirs_file)

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert (output_root / "repeat_alpha_case" / "repeatability_report.json").exists()
    assert run_dirs_file.read_text(encoding="utf-8").splitlines() == [
        str(output_root / "repeat_alpha_case")
    ]
    calls = json.loads(capture_path.read_text(encoding="utf-8"))
    assert calls[0][0] == "tests/e2e/repeat_case.py"
