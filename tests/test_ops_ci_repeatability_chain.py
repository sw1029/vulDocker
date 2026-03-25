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


def test_repeatability_chain_supports_case_root_output_and_python_override(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    _write_case(cases_root / "alpha-case", with_expectations=True)
    _write_case(cases_root / "beta-case")
    output_root = tmp_path / "outputs"
    capture_path = tmp_path / "python_calls.json"
    run_dirs_file = tmp_path / "run_dirs.txt"
    fake_python = tmp_path / "fake_python.py"

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

    env = os.environ.copy()
    env["VULD_REPEAT_CHAIN_PYTHON_BIN"] = str(fake_python)
    env["VULD_REPEAT_CHAIN_CASES_ROOT"] = str(cases_root)
    env["VULD_REPEAT_CHAIN_OUTPUT_ROOT"] = str(output_root)
    env["VULD_REPEAT_CHAIN_RUN_DIRS_FILE"] = str(run_dirs_file)
    env["VULD_REPEAT_CHAIN_NO_SNAPSHOT"] = "1"

    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_repeatability_chain.sh"),
            "alpha-case=alias_alpha",
            "beta-case",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "[REPEAT] completed" in completed.stdout
    calls = json.loads(capture_path.read_text(encoding="utf-8"))
    assert calls[0][0] == "tests/e2e/repeat_case.py"
    assert calls[0][calls[0].index("--case") + 1] == str(cases_root / "alpha-case")
    assert calls[0][calls[0].index("--output-dir") + 1] == str(output_root / "repeat_alias_alpha")
    assert "--expectations" in calls[0]
    assert "--no-snapshot" in calls[0]
    assert calls[1][calls[1].index("--case") + 1] == str(cases_root / "beta-case")
    assert calls[1][calls[1].index("--output-dir") + 1] == str(output_root / "repeat_beta_case")
    assert "--expectations" not in calls[1]

    run_dirs = run_dirs_file.read_text(encoding="utf-8").splitlines()
    assert run_dirs == [str(output_root / "repeat_alias_alpha"), str(output_root / "repeat_beta_case")]


def test_repeatability_chain_continues_when_report_exists_and_failure_is_allowed(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    _write_case(cases_root / "alpha-case", with_expectations=True)
    output_root = tmp_path / "outputs"
    fake_python = tmp_path / "fake_python.py"

    _write_executable(
        fake_python,
        """#!/usr/bin/env python3
import sys
from pathlib import Path

argv = sys.argv[1:]
if argv and argv[0] == "tests/e2e/repeat_case.py":
    out_dir = Path(argv[argv.index("--output-dir") + 1])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "repeatability_report.json").write_text('{"passed": false}', encoding="utf-8")
    raise SystemExit(1)
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_REPEAT_CHAIN_PYTHON_BIN"] = str(fake_python)
    env["VULD_REPEAT_CHAIN_CASES_ROOT"] = str(cases_root)
    env["VULD_REPEAT_CHAIN_OUTPUT_ROOT"] = str(output_root)
    env["VULD_REPEAT_CHAIN_ALLOW_FAILURE_WITH_REPORT"] = "1"
    env["VULD_REPEAT_CHAIN_LOG_PREFIX"] = "CHAIN"

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_repeatability_chain.sh"), "alpha-case"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "[CHAIN] repeat alpha-case returned 1, continuing with recorded report" in completed.stdout
    assert (output_root / "repeat_alpha_case" / "repeatability_report.json").exists()


def test_repeatability_chain_fails_without_report_when_repeat_case_returns_nonzero(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    _write_case(cases_root / "alpha-case")
    fake_python = tmp_path / "fake_python.py"

    _write_executable(
        fake_python,
        """#!/usr/bin/env python3
import sys
raise SystemExit(1)
""",
    )

    env = os.environ.copy()
    env["VULD_REPEAT_CHAIN_PYTHON_BIN"] = str(fake_python)
    env["VULD_REPEAT_CHAIN_CASES_ROOT"] = str(cases_root)
    env["VULD_REPEAT_CHAIN_OUTPUT_ROOT"] = str(tmp_path / "outputs")

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_repeatability_chain.sh"), "alpha-case"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1


def test_repeatability_chain_retries_transient_docker_readiness_failures(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    _write_case(cases_root / "alpha-case", with_expectations=True)
    output_root = tmp_path / "outputs"
    capture_path = tmp_path / "python_calls.json"
    state_path = tmp_path / "state.json"
    fake_python = tmp_path / "fake_python.py"

    _write_executable(
        fake_python,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path

capture_path = Path({str(capture_path)!r})
state_path = Path({str(state_path)!r})
calls = json.loads(capture_path.read_text(encoding="utf-8")) if capture_path.exists() else []
calls.append(sys.argv[1:])
capture_path.write_text(json.dumps(calls, ensure_ascii=False), encoding="utf-8")

state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {{"count": 0}}
state["count"] += 1
state_path.write_text(json.dumps(state), encoding="utf-8")

argv = sys.argv[1:]
if argv and argv[0] == "tests/e2e/repeat_case.py":
    out_dir = Path(argv[argv.index("--output-dir") + 1])
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "repeatability_report.json"
    if state["count"] == 1:
        report_path.write_text(
            json.dumps({{
                "passed": False,
                "attempts": [{{"error": "CaseError: docker daemon is not reachable"}}],
            }}, ensure_ascii=False),
            encoding="utf-8",
        )
        raise SystemExit(1)
    report_path.write_text('{{"passed": true}}', encoding="utf-8")
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_REPEAT_CHAIN_PYTHON_BIN"] = str(fake_python)
    env["VULD_REPEAT_CHAIN_CASES_ROOT"] = str(cases_root)
    env["VULD_REPEAT_CHAIN_OUTPUT_ROOT"] = str(output_root)
    env["VULD_REPEAT_CHAIN_DOCKER_RETRY_COUNT"] = "2"
    env["VULD_REPEAT_CHAIN_DOCKER_RETRY_DELAY_SEC"] = "0"

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_repeatability_chain.sh"), "alpha-case"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "transient docker readiness failure, retrying (1/2)" in completed.stdout
    calls = json.loads(capture_path.read_text(encoding="utf-8"))
    assert len(calls) == 2
    assert all(call[0] == "tests/e2e/repeat_case.py" for call in calls)
    report = json.loads((output_root / "repeat_alpha_case" / "repeatability_report.json").read_text(encoding="utf-8"))
    assert report["passed"] is True


def test_repeatability_chain_does_not_retry_permission_denied_reports(tmp_path: Path) -> None:
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
calls = json.loads(capture_path.read_text(encoding="utf-8")) if capture_path.exists() else []
calls.append(sys.argv[1:])
capture_path.write_text(json.dumps(calls, ensure_ascii=False), encoding="utf-8")

argv = sys.argv[1:]
if argv and argv[0] == "tests/e2e/repeat_case.py":
    out_dir = Path(argv[argv.index("--output-dir") + 1])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "repeatability_report.json").write_text(
        json.dumps({{
            "passed": False,
            "attempts": [{{"error": "CaseError: docker daemon permission denied"}}],
        }}, ensure_ascii=False),
        encoding="utf-8",
    )
    raise SystemExit(1)
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_REPEAT_CHAIN_PYTHON_BIN"] = str(fake_python)
    env["VULD_REPEAT_CHAIN_CASES_ROOT"] = str(cases_root)
    env["VULD_REPEAT_CHAIN_OUTPUT_ROOT"] = str(output_root)
    env["VULD_REPEAT_CHAIN_ALLOW_FAILURE_WITH_REPORT"] = "1"
    env["VULD_REPEAT_CHAIN_DOCKER_RETRY_COUNT"] = "2"
    env["VULD_REPEAT_CHAIN_DOCKER_RETRY_DELAY_SEC"] = "0"
    env["VULD_REPEAT_CHAIN_LOG_PREFIX"] = "CHAIN"

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_repeatability_chain.sh"), "alpha-case"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "transient docker readiness failure, retrying" not in completed.stdout
    assert "reported docker daemon permission denied; continuing with recorded report" in completed.stdout
    calls = json.loads(capture_path.read_text(encoding="utf-8"))
    assert len(calls) == 1
    marker_path = output_root / "repeat_alpha_case" / "docker_permission_artifact.txt"
    assert marker_path.exists()
    marker = marker_path.read_text(encoding="utf-8")
    assert "case_slug=alpha-case" in marker
    assert "reason=docker daemon permission denied" in marker
