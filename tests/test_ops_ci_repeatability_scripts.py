from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _prepare_fake_bin(tmp_path: Path) -> tuple[Path, Path, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    capture_path = tmp_path / "python_calls.jsonl"
    python_path = bin_dir / "python"
    pytest_path = bin_dir / "pytest"

    _write_executable(
        python_path,
        f"""#!/usr/bin/env python3
import json
import os
import sys

capture_path = {str(capture_path)!r}
with open(capture_path, "a", encoding="utf-8") as fh:
    fh.write(json.dumps(sys.argv[1:], ensure_ascii=False) + "\\n")

if len(sys.argv) > 2 and sys.argv[1] == "-m" and sys.argv[2] == "tests.e2e.repeat_case":
    output_dir = None
    for index, arg in enumerate(sys.argv):
        if arg == "--output-dir" and index + 1 < len(sys.argv):
            output_dir = sys.argv[index + 1]
            break
    passed = os.environ.get("FAKE_REPEATABILITY_PASSED", "true").strip().lower() not in {"0", "false", "no"}
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        with open(os.path.join(output_dir, "repeatability_report.json"), "w", encoding="utf-8") as fh:
            json.dump(
                {{
                    "case": "synthetic-repeat-case",
                    "attempt_count": 1,
                    "success_count": 1 if passed else 0,
                    "failure_count": 0 if passed else 1,
                    "passed": passed,
                    "failure_fingerprints": [] if passed else [{{"fingerprint": "fp-simulated", "count": 1}}],
                    "failure_stages": [] if passed else [{{"stage": "GENERATOR", "count": 1}}],
                    "guard_error_codes": [] if passed else [{{"guard_error_code": "guard_simulated", "count": 1}}],
                }},
                fh,
            )
    raise SystemExit(0)

if len(sys.argv) > 1 and sys.argv[1] == "-":
    _ = sys.stdin.read()
    if len(sys.argv) > 2 and os.path.exists(sys.argv[2]):
        with open(sys.argv[2], "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        print(" [E2E] Repeatability summary:", json.dumps(
            {{
                "case": payload.get("case"),
                "attempt_count": payload.get("attempt_count"),
                "success_count": payload.get("success_count"),
                "failure_count": payload.get("failure_count"),
                "passed": payload.get("passed"),
                "failure_fingerprints": payload.get("failure_fingerprints"),
                "failure_stages": payload.get("failure_stages"),
                "guard_error_codes": payload.get("guard_error_codes"),
                "report_path": sys.argv[2],
            }},
            ensure_ascii=False,
        ))
        raise SystemExit(0 if payload.get("passed") else 1)
    raise SystemExit(0)

raise SystemExit(0)
""",
    )
    _write_executable(pytest_path, "#!/usr/bin/env bash\nexit 0\n")
    return bin_dir, capture_path, python_path


def _load_python_calls(capture_path: Path) -> list[list[str]]:
    if not capture_path.exists():
        return []
    return [
        json.loads(line)
        for line in capture_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _find_repeat_case_call(calls: list[list[str]]) -> list[str]:
    for call in calls:
        if len(call) >= 2 and call[0] == "-m" and call[1] == "tests.e2e.repeat_case":
            return call
    raise AssertionError("repeat_case invocation was not captured")


def _option_value(argv: list[str], flag: str) -> str:
    index = argv.index(flag)
    return argv[index + 1]


def test_run_repeatability_gate_accepts_legacy_shorthand_args(tmp_path: Path) -> None:
    fake_bin, capture_path, python_path = _prepare_fake_bin(tmp_path)
    output_dir = tmp_path / "repeat-out"
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["VULD_REPEAT_PYTHON_BIN"] = str(python_path)

    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_repeatability_gate.sh"),
            "4",
            "deterministic",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    repeat_call = _find_repeat_case_call(_load_python_calls(capture_path))
    assert _option_value(repeat_call, "--case") == str(REPO_ROOT / "tests/e2e/cases/cwe-89-basic")
    assert _option_value(repeat_call, "--attempts") == "4"
    assert _option_value(repeat_call, "--mode") == "deterministic"
    assert _option_value(repeat_call, "--output-dir") == str(output_dir)


def test_run_repeatability_gate_accepts_case_slug(tmp_path: Path) -> None:
    fake_bin, capture_path, python_path = _prepare_fake_bin(tmp_path)
    output_dir = tmp_path / "repeat-out"
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["VULD_REPEAT_PYTHON_BIN"] = str(python_path)

    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_repeatability_gate.sh"),
            "open-redirect-strict-dynamic-no-remote",
            "2",
            "deterministic",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    repeat_call = _find_repeat_case_call(_load_python_calls(capture_path))
    assert _option_value(repeat_call, "--case") == str(
        REPO_ROOT / "tests/e2e/cases/open-redirect-strict-dynamic-no-remote"
    )
    assert _option_value(repeat_call, "--attempts") == "2"
    assert _option_value(repeat_call, "--mode") == "deterministic"
    assert _option_value(repeat_call, "--output-dir") == str(output_dir)


def test_run_e2e_tests_forwards_repeat_case_slug(tmp_path: Path) -> None:
    fake_bin, capture_path, python_path = _prepare_fake_bin(tmp_path)
    output_dir = tmp_path / "repeat-out"
    case_slug = "open-redirect-strict-dynamic-no-remote"
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["VULD_RUN_E2E"] = "1"
    env["VULD_RUN_E2E_REPEAT"] = "1"
    env["VULD_E2E_REPEAT_ATTEMPTS"] = "2"
    env["VULD_E2E_REPEAT_MODE"] = "deterministic"
    env["VULD_E2E_REPEAT_CASE_DIR"] = case_slug
    env["VULD_E2E_REPEAT_OUTPUT_DIR"] = str(output_dir)
    env["VULD_REPEAT_PYTHON_BIN"] = str(python_path)

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_e2e_tests.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    repeat_call = _find_repeat_case_call(_load_python_calls(capture_path))
    assert _option_value(repeat_call, "--case") == str(REPO_ROOT / "tests/e2e/cases" / case_slug)
    assert _option_value(repeat_call, "--attempts") == "2"
    assert _option_value(repeat_call, "--mode") == "deterministic"
    assert _option_value(repeat_call, "--output-dir") == str(output_dir)


def test_run_repeatability_gate_fails_when_report_failed(tmp_path: Path) -> None:
    fake_bin, _capture_path, python_path = _prepare_fake_bin(tmp_path)
    output_dir = tmp_path / "repeat-out"
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["FAKE_REPEATABILITY_PASSED"] = "false"
    env["VULD_REPEAT_PYTHON_BIN"] = str(python_path)

    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_repeatability_gate.sh"),
            "cwe-89-basic",
            "3",
            "deterministic",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert "Repeatability summary:" in completed.stdout


def test_run_e2e_tests_fails_when_repeatability_report_failed(tmp_path: Path) -> None:
    fake_bin, _capture_path, python_path = _prepare_fake_bin(tmp_path)
    output_dir = tmp_path / "repeat-out"
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["FAKE_REPEATABILITY_PASSED"] = "false"
    env["VULD_RUN_E2E"] = "1"
    env["VULD_RUN_E2E_REPEAT"] = "1"
    env["VULD_E2E_REPEAT_CASE_DIR"] = "cwe-89-basic"
    env["VULD_E2E_REPEAT_OUTPUT_DIR"] = str(output_dir)
    env["VULD_REPEAT_PYTHON_BIN"] = str(python_path)

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_e2e_tests.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert "[E2E] Running repeatability gate: case=cwe-89-basic" in completed.stdout
