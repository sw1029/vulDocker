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


def test_repeatability_matrix_check_supports_case_root_output_and_python_override(tmp_path: Path) -> None:
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
if argv and argv[0] == "tests/e2e/repeat_case.py":
    out_dir = Path(argv[argv.index("--output-dir") + 1])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps({{"case_name": out_dir.name.replace("repeat_", "").replace("_", "-"), "overall_pass": True}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (out_dir / "repeatability_report.json").write_text(
        json.dumps({{"case": out_dir.name.replace("repeat_", "").replace("_", "-"), "passed": True}}, ensure_ascii=False),
        encoding="utf-8",
    )
    raise SystemExit(0)
if argv and argv[0] == "tests/e2e/matrix_report.py":
    out_path = Path(argv[argv.index("--output") + 1])
    out_path.write_text(
        json.dumps({{"schema_version": "matrix_report@0.1", "case_count": 2, "fully_green": True}}, ensure_ascii=False),
        encoding="utf-8",
    )
    raise SystemExit(0)
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_REPEAT_MATRIX_PYTHON_BIN"] = str(fake_python)
    env["VULD_REPEAT_MATRIX_CASES_ROOT"] = str(cases_root)
    env["VULD_REPEAT_MATRIX_OUTPUT_ROOT"] = str(output_root)

    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_repeatability_matrix_check.sh"),
            "alpha-case",
            "beta-case",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "[MATRIX] completed" in completed.stdout
    assert (output_root / "repeat_alpha_case" / "summary.json").exists()
    assert (output_root / "repeat_beta_case" / "summary.json").exists()
    assert (output_root / "matrix_report.json").exists()

    calls = json.loads(capture_path.read_text(encoding="utf-8"))
    assert calls[0][0] == "tests/e2e/repeat_case.py"
    assert calls[0][calls[0].index("--case") + 1] == str(cases_root / "alpha-case")
    assert "--expectations" in calls[0]
    assert calls[1][0] == "tests/e2e/repeat_case.py"
    assert calls[1][calls[1].index("--case") + 1] == str(cases_root / "beta-case")
    assert "--expectations" not in calls[1]
    assert calls[2][0] == "tests/e2e/matrix_report.py"
    assert calls[2][-2:] == ["--output", str(output_root / "matrix_report.json")]


def test_repeatability_matrix_check_writes_permission_summary_and_supports_custom_name(tmp_path: Path) -> None:
    output_root = tmp_path / "outputs"
    repeat_capture_path = tmp_path / "repeat_helper_capture.json"
    matrix_capture_path = tmp_path / "python_calls.json"
    fake_repeat_helper = tmp_path / "repeat_helper.py"
    fake_python = tmp_path / "fake_python.py"

    _write_executable(
        fake_repeat_helper,
        f"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
capture = Path({str(repeat_capture_path)!r})
output_root = Path(os.environ["VULD_REPEAT_CHAIN_OUTPUT_ROOT"])
artifact_name = os.environ["VULD_REPEAT_CHAIN_PERMISSION_ARTIFACT_NAME"]
run_dirs = [output_root / "repeat_alpha", output_root / "repeat_beta"]
for run_dir in run_dirs:
    run_dir.mkdir(parents=True, exist_ok=True)
(run_dirs[0] / artifact_name).write_text("case_slug=alpha-case\\n", encoding="utf-8")
run_dirs_file = Path(os.environ["VULD_REPEAT_CHAIN_RUN_DIRS_FILE"])
run_dirs_file.write_text("\\n".join(str(path) for path in run_dirs) + "\\n", encoding="utf-8")
capture.write_text(json.dumps({{
    "argv": sys.argv[1:],
    "env": {{
        "VULD_REPEAT_CHAIN_PERMISSION_ARTIFACT_NAME": os.environ.get("VULD_REPEAT_CHAIN_PERMISSION_ARTIFACT_NAME"),
    }},
}}, ensure_ascii=False), encoding="utf-8")
raise SystemExit(0)
""",
    )
    _write_executable(
        fake_python,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path
capture = Path({str(matrix_capture_path)!r})
capture.write_text(json.dumps(sys.argv[1:], ensure_ascii=False), encoding="utf-8")
argv = sys.argv[1:]
if argv and argv[0] == "tests/e2e/matrix_report.py":
    out_path = Path(argv[argv.index("--output") + 1])
    out_path.write_text('{{"schema_version":"matrix_report@0.1","case_count":2}}', encoding="utf-8")
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_REPEAT_MATRIX_REPEAT_HELPER"] = str(fake_repeat_helper)
    env["VULD_REPEAT_MATRIX_PYTHON_BIN"] = str(fake_python)
    env["VULD_REPEAT_MATRIX_OUTPUT_ROOT"] = str(output_root)
    env["VULD_REPEAT_MATRIX_PERMISSION_SUMMARY_NAME"] = "custom_matrix_permission_summary.json"

    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_repeatability_matrix_check.sh"),
            "alpha-case=alpha",
            "beta-case=beta",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "permission_summary_out=" in completed.stdout
    summary = json.loads((output_root / "custom_matrix_permission_summary.json").read_text(encoding="utf-8"))
    assert summary == {
        "schema_version": "permission_artifact_summary@0.1",
        "permission_artifact_name": "docker_permission_artifact.txt",
        "permission_artifact_count": 1,
        "runtime_equivalent_helper_truth_available": False,
        "recommended_action": "unrestricted_docker_rerun",
        "permission_artifact_cases": ["alpha-case"],
    }
    repeat_payload = json.loads(repeat_capture_path.read_text(encoding="utf-8"))
    assert repeat_payload["env"] == {
        "VULD_REPEAT_CHAIN_PERMISSION_ARTIFACT_NAME": "docker_permission_artifact.txt",
    }
    matrix_argv = json.loads(matrix_capture_path.read_text(encoding="utf-8"))
    assert matrix_argv == [
        "tests/e2e/matrix_report.py",
        str(output_root / "repeat_alpha"),
        str(output_root / "repeat_beta"),
        "--output",
        str(output_root / "matrix_report.json"),
    ]


def test_repeatability_matrix_check_supports_repeat_helper_override(tmp_path: Path) -> None:
    output_root = tmp_path / "outputs"
    repeat_capture_path = tmp_path / "repeat_helper_capture.json"
    matrix_capture_path = tmp_path / "python_calls.json"
    fake_repeat_helper = tmp_path / "repeat_helper.py"
    fake_python = tmp_path / "fake_python.py"

    _write_executable(
        fake_repeat_helper,
        f"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
capture = Path({str(repeat_capture_path)!r})
output_root = Path(os.environ["VULD_REPEAT_CHAIN_OUTPUT_ROOT"])
run_dirs = [output_root / "repeat_alpha", output_root / "repeat_beta"]
for run_dir in run_dirs:
    run_dir.mkdir(parents=True, exist_ok=True)
run_dirs_file = Path(os.environ["VULD_REPEAT_CHAIN_RUN_DIRS_FILE"])
run_dirs_file.write_text("\\n".join(str(path) for path in run_dirs) + "\\n", encoding="utf-8")
capture.write_text(json.dumps({{
    "argv": sys.argv[1:],
    "env": {{
        "VULD_REPEAT_CHAIN_PYTHON_BIN": os.environ.get("VULD_REPEAT_CHAIN_PYTHON_BIN"),
        "VULD_REPEAT_CHAIN_CASES_ROOT": os.environ.get("VULD_REPEAT_CHAIN_CASES_ROOT"),
        "VULD_REPEAT_CHAIN_OUTPUT_ROOT": os.environ.get("VULD_REPEAT_CHAIN_OUTPUT_ROOT"),
        "VULD_REPEAT_CHAIN_MODE": os.environ.get("VULD_REPEAT_CHAIN_MODE"),
        "VULD_REPEAT_CHAIN_ATTEMPTS": os.environ.get("VULD_REPEAT_CHAIN_ATTEMPTS"),
        "VULD_REPEAT_CHAIN_NO_SNAPSHOT": os.environ.get("VULD_REPEAT_CHAIN_NO_SNAPSHOT"),
        "VULD_REPEAT_CHAIN_ALLOW_FAILURE_WITH_REPORT": os.environ.get("VULD_REPEAT_CHAIN_ALLOW_FAILURE_WITH_REPORT"),
        "VULD_REPEAT_CHAIN_PERMISSION_ARTIFACT_NAME": os.environ.get("VULD_REPEAT_CHAIN_PERMISSION_ARTIFACT_NAME"),
        "VULD_REPEAT_CHAIN_DOCKER_RETRY_COUNT": os.environ.get("VULD_REPEAT_CHAIN_DOCKER_RETRY_COUNT"),
        "VULD_REPEAT_CHAIN_DOCKER_RETRY_DELAY_SEC": os.environ.get("VULD_REPEAT_CHAIN_DOCKER_RETRY_DELAY_SEC"),
        "VULD_REPEAT_CHAIN_LOG_PREFIX": os.environ.get("VULD_REPEAT_CHAIN_LOG_PREFIX"),
    }},
}}, ensure_ascii=False), encoding="utf-8")
raise SystemExit(0)
""",
    )
    _write_executable(
        fake_python,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path
capture = Path({str(matrix_capture_path)!r})
capture.write_text(json.dumps(sys.argv[1:], ensure_ascii=False), encoding="utf-8")
argv = sys.argv[1:]
if argv and argv[0] == "tests/e2e/matrix_report.py":
    out_path = Path(argv[argv.index("--output") + 1])
    out_path.write_text('{{"schema_version":"matrix_report@0.1","case_count":2}}', encoding="utf-8")
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_REPEAT_MATRIX_REPEAT_HELPER"] = str(fake_repeat_helper)
    env["VULD_REPEAT_MATRIX_PYTHON_BIN"] = str(fake_python)
    env["VULD_REPEAT_MATRIX_CASES_ROOT"] = "/tmp/fake_cases"
    env["VULD_REPEAT_MATRIX_OUTPUT_ROOT"] = str(output_root)
    env["VULD_REPEAT_MATRIX_MODE"] = "diverse"
    env["VULD_REPEAT_MATRIX_ATTEMPTS"] = "4"
    env["VULD_REPEAT_MATRIX_NO_SNAPSHOT"] = "1"
    env["VULD_REPEAT_MATRIX_ALLOW_REPEAT_FAILURE_WITH_REPORT"] = "1"
    env["VULD_REPEAT_MATRIX_PERMISSION_ARTIFACT_NAME"] = "custom_repeatability_permission_marker.txt"
    env["VULD_REPEAT_MATRIX_DOCKER_RETRY_COUNT"] = "3"
    env["VULD_REPEAT_MATRIX_DOCKER_RETRY_DELAY_SEC"] = "0"

    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_repeatability_matrix_check.sh"),
            "alpha-case=alpha",
            "beta-case=beta",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    repeat_payload = json.loads(repeat_capture_path.read_text(encoding="utf-8"))
    assert repeat_payload["argv"] == ["alpha-case=alpha", "beta-case=beta"]
    assert repeat_payload["env"] == {
        "VULD_REPEAT_CHAIN_PYTHON_BIN": str(fake_python),
        "VULD_REPEAT_CHAIN_CASES_ROOT": "/tmp/fake_cases",
        "VULD_REPEAT_CHAIN_OUTPUT_ROOT": str(output_root),
        "VULD_REPEAT_CHAIN_MODE": "diverse",
        "VULD_REPEAT_CHAIN_ATTEMPTS": "4",
        "VULD_REPEAT_CHAIN_NO_SNAPSHOT": "1",
        "VULD_REPEAT_CHAIN_ALLOW_FAILURE_WITH_REPORT": "1",
        "VULD_REPEAT_CHAIN_PERMISSION_ARTIFACT_NAME": "custom_repeatability_permission_marker.txt",
        "VULD_REPEAT_CHAIN_DOCKER_RETRY_COUNT": "3",
        "VULD_REPEAT_CHAIN_DOCKER_RETRY_DELAY_SEC": "0",
        "VULD_REPEAT_CHAIN_LOG_PREFIX": "MATRIX",
    }
    matrix_argv = json.loads(matrix_capture_path.read_text(encoding="utf-8"))
    assert matrix_argv == [
        "tests/e2e/matrix_report.py",
        str(output_root / "repeat_alpha"),
        str(output_root / "repeat_beta"),
        "--output",
        str(output_root / "matrix_report.json"),
    ]


def test_matrix_report_cli_builds_report_from_run_dirs(tmp_path: Path) -> None:
    run_dir = tmp_path / "repeat_cwe_89_basic"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "summary.json").write_text(
        json.dumps({"case_name": "cwe-89-basic", "overall_pass": True}, ensure_ascii=False),
        encoding="utf-8",
    )
    (run_dir / "repeatability_report.json").write_text(
        json.dumps({"case": "cwe-89-basic", "passed": True}, ensure_ascii=False),
        encoding="utf-8",
    )
    output_path = tmp_path / "matrix_report.json"

    completed = subprocess.run(
        [
            "python",
            "tests/e2e/matrix_report.py",
            str(run_dir),
            "--output",
            str(output_path),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "matrix_report@0.1"
    assert payload["case_count"] == 1
    assert payload["covered_cases"] == ["cwe-89-basic"]


def test_matrix_report_cli_supports_repeatability_only_run_dirs(tmp_path: Path) -> None:
    run_dir = tmp_path / "repeat_foobar_name_only_negative"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "repeatability_report.json").write_text(
        json.dumps({"case": "foobar-name-only-negative", "passed": False}, ensure_ascii=False),
        encoding="utf-8",
    )
    output_path = tmp_path / "matrix_report.json"

    completed = subprocess.run(
        [
            "python",
            "tests/e2e/matrix_report.py",
            str(run_dir),
            "--output",
            str(output_path),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "matrix_report@0.1"
    assert payload["case_count"] == 1
    assert payload["covered_cases"] == ["foobar-name-only-negative"]
    assert payload["failed_cases"] == ["foobar-name-only-negative"]
    assert payload["repeatability_failures"] == ["foobar-name-only-negative"]
    assert payload["fully_green"] is False


def test_repeatability_matrix_check_succeeds_with_repeatability_only_run_dirs(tmp_path: Path) -> None:
    output_root = tmp_path / "outputs"
    fake_repeat_helper = tmp_path / "repeat_helper.py"

    _write_executable(
        fake_repeat_helper,
        f"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
output_root = Path(os.environ["VULD_REPEAT_CHAIN_OUTPUT_ROOT"])
run_dirs = [
    output_root / "repeat_foobar_name_only_negative",
    output_root / "repeat_open_redirect_strict_dynamic_no_remote",
]
cases = [
    "foobar-name-only-negative",
    "open-redirect-strict-dynamic-no-remote",
]
for run_dir, case_name in zip(run_dirs, cases):
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "repeatability_report.json").write_text(
        json.dumps({{"case": case_name, "passed": False}}, ensure_ascii=False),
        encoding="utf-8",
    )
run_dirs_file = Path(os.environ["VULD_REPEAT_CHAIN_RUN_DIRS_FILE"])
run_dirs_file.write_text("\\n".join(str(path) for path in run_dirs) + "\\n", encoding="utf-8")
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_REPEAT_MATRIX_REPEAT_HELPER"] = str(fake_repeat_helper)
    env["VULD_REPEAT_MATRIX_OUTPUT_ROOT"] = str(output_root)

    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_repeatability_matrix_check.sh"),
            "foobar-name-only-negative",
            "open-redirect-strict-dynamic-no-remote",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads((output_root / "matrix_report.json").read_text(encoding="utf-8"))
    assert payload["covered_cases"] == [
        "foobar-name-only-negative",
        "open-redirect-strict-dynamic-no-remote",
    ]
    assert payload["repeatability_failures"] == [
        "foobar-name-only-negative",
        "open-redirect-strict-dynamic-no-remote",
    ]
    assert "permission_summary_out=" in completed.stdout


def test_repeatability_matrix_check_rejects_missing_run_dirs_file(tmp_path: Path) -> None:
    output_root = tmp_path / "outputs"
    repeat_helper = tmp_path / "repeat_helper.py"

    _write_executable(
        repeat_helper,
        """#!/usr/bin/env python3
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_REPEAT_MATRIX_REPEAT_HELPER"] = str(repeat_helper)
    env["VULD_REPEAT_MATRIX_OUTPUT_ROOT"] = str(output_root)

    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_repeatability_matrix_check.sh"),
            "alpha-case",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert f"[MATRIX] run dirs file not found: {output_root / 'repeat_run_dirs.txt'}" in completed.stderr


def test_repeatability_matrix_check_rejects_missing_repeat_helper(tmp_path: Path) -> None:
    output_root = tmp_path / "outputs"
    missing_helper = tmp_path / "missing_repeat_helper.sh"

    env = os.environ.copy()
    env["VULD_REPEAT_MATRIX_OUTPUT_ROOT"] = str(output_root)
    env["VULD_REPEAT_MATRIX_REPEAT_HELPER"] = str(missing_helper)

    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_repeatability_matrix_check.sh"),
            "alpha-case",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr == f"[MATRIX] repeat helper not found or not executable: {missing_helper}\n"
