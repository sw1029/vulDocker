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


def test_direct_validation_chain_supports_case_root_output_and_python_override(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    _write_case(cases_root / "alpha-case", with_expectations=True)
    _write_case(cases_root / "beta-case")
    output_root = tmp_path / "outputs"
    capture_path = tmp_path / "python_calls.json"
    fake_python = tmp_path / "fake_python.py"

    _write_executable(
        fake_python,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path

capture_path = Path({str(capture_path)!r})
calls = []
if capture_path.exists():
    calls = json.loads(capture_path.read_text(encoding="utf-8"))
calls.append(sys.argv[1:])
capture_path.write_text(json.dumps(calls, ensure_ascii=False), encoding="utf-8")

argv = sys.argv[1:]
if argv and argv[0] == "tests/e2e/run_case.py":
    out_dir = Path(argv[argv.index("--output-dir") + 1])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps({{"ok": True}}, ensure_ascii=False), encoding="utf-8")
    raise SystemExit(0)
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_DIRECT_CHAIN_PYTHON_BIN"] = str(fake_python)
    env["VULD_DIRECT_CHAIN_CASES_ROOT"] = str(cases_root)
    env["VULD_DIRECT_CHAIN_OUTPUT_ROOT"] = str(output_root)

    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_direct_validation_chain.sh"),
            "alpha-case",
            "beta-case",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "[DIRECT-CHAIN] completed" in completed.stdout
    assert (output_root / "run_alpha_case" / "summary.json").exists()
    assert (output_root / "run_beta_case" / "summary.json").exists()

    calls = json.loads(capture_path.read_text(encoding="utf-8"))
    assert calls[0][0] == "tests/e2e/run_case.py"
    assert calls[0][calls[0].index("--case") + 1] == str(cases_root / "alpha-case")
    assert "--expectations" in calls[0]
    assert "--no-snapshot" in calls[0]
    assert calls[1][0] == "tests/e2e/run_case.py"
    assert calls[1][calls[1].index("--case") + 1] == str(cases_root / "beta-case")
    assert "--expectations" not in calls[1]
    assert "--no-snapshot" in calls[1]


def test_direct_validation_chain_supports_alias_output_names(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    _write_case(cases_root / "alpha-case", with_expectations=True)
    output_root = tmp_path / "outputs"
    capture_path = tmp_path / "python_calls.json"
    fake_python = tmp_path / "fake_python.py"

    _write_executable(
        fake_python,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path
capture_path = Path({str(capture_path)!r})
calls = []
if capture_path.exists():
    calls = json.loads(capture_path.read_text(encoding="utf-8"))
calls.append(sys.argv[1:])
capture_path.write_text(json.dumps(calls, ensure_ascii=False), encoding="utf-8")
argv = sys.argv[1:]
if argv and argv[0] == "tests/e2e/run_case.py":
    out_dir = Path(argv[argv.index("--output-dir") + 1])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps({{"ok": True}}, ensure_ascii=False), encoding="utf-8")
    raise SystemExit(0)
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_DIRECT_CHAIN_PYTHON_BIN"] = str(fake_python)
    env["VULD_DIRECT_CHAIN_CASES_ROOT"] = str(cases_root)
    env["VULD_DIRECT_CHAIN_OUTPUT_ROOT"] = str(output_root)

    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_direct_validation_chain.sh"),
            "alpha-case=custom_output",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert (output_root / "custom_output" / "summary.json").exists()
    calls = json.loads(capture_path.read_text(encoding="utf-8"))
    assert calls[0][calls[0].index("--output-dir") + 1] == str(output_root / "custom_output")


def test_direct_validation_chain_can_keep_snapshots(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    _write_case(cases_root / "gamma-case", with_expectations=True)
    output_root = tmp_path / "outputs"
    capture_path = tmp_path / "python_calls.json"
    fake_python = tmp_path / "fake_python.py"

    _write_executable(
        fake_python,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path
capture_path = Path({str(capture_path)!r})
calls = []
if capture_path.exists():
    calls = json.loads(capture_path.read_text(encoding="utf-8"))
calls.append(sys.argv[1:])
capture_path.write_text(json.dumps(calls, ensure_ascii=False), encoding="utf-8")
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_DIRECT_CHAIN_PYTHON_BIN"] = str(fake_python)
    env["VULD_DIRECT_CHAIN_CASES_ROOT"] = str(cases_root)
    env["VULD_DIRECT_CHAIN_OUTPUT_ROOT"] = str(output_root)
    env["VULD_DIRECT_CHAIN_NO_SNAPSHOT"] = "0"

    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_direct_validation_chain.sh"),
            "gamma-case",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    calls = json.loads(capture_path.read_text(encoding="utf-8"))
    assert "--no-snapshot" not in calls[0]
