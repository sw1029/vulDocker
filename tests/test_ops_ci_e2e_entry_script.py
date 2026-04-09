from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _write_case(case_dir: Path, *, include_expectations: bool = True) -> None:
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "requirement.yml").write_text("requirement_id: TEST\n", encoding="utf-8")
    if include_expectations:
        (case_dir / "expectations.json").write_text("{}", encoding="utf-8")


def test_run_e2e_tests_skips_without_opt_in_with_override_cases_dir(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    _write_case(cases_dir / "sample-case")

    env = os.environ.copy()
    env["VULD_E2E_CASES_DIR"] = str(cases_dir)
    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_e2e_tests.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0
    assert "VULD_RUN_E2E not set" in completed.stderr


def test_run_e2e_tests_uses_override_pytest_and_tavily_config(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    _write_case(cases_dir / "sample-case")
    capture_path = tmp_path / "pytest_capture.json"
    pytest_path = tmp_path / "fake_pytest"
    config_path = tmp_path / "api_keys.ini"
    config_path.write_text("[tavily]\napi_key = test-key\n", encoding="utf-8")
    _write_executable(
        pytest_path,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path
Path({str(capture_path)!r}).write_text(json.dumps(sys.argv[1:]), encoding="utf-8")
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_RUN_E2E"] = "1"
    env["VULD_E2E_REQUIRE_TAVILY"] = "1"
    env["VULD_E2E_CASES_DIR"] = str(cases_dir)
    env["VULD_E2E_CONFIG_PATH"] = str(config_path)
    env["VULD_E2E_PYTEST_BIN"] = str(pytest_path)
    env["VULD_E2E_PYTHON_BIN"] = sys.executable

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_e2e_tests.sh"), "-k", "sample"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(capture_path.read_text(encoding="utf-8")) == ["-m", "e2e", "-k", "sample"]


def test_run_e2e_tests_accepts_custom_remote_provider_for_generic_live_gate(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    _write_case(cases_dir / "sample-case")
    capture_path = tmp_path / "pytest_capture.json"
    pytest_path = tmp_path / "fake_pytest"
    _write_executable(
        pytest_path,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path
Path({str(capture_path)!r}).write_text(json.dumps(sys.argv[1:]), encoding="utf-8")
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_RUN_E2E"] = "1"
    env["VULD_E2E_REQUIRE_REMOTE_PROVIDER"] = "1"
    env["VUL_WEB_SEARCH_PROVIDER"] = "custom"
    env["VUL_WEB_SEARCH_ENDPOINT"] = "https://search.example/api"
    env["VULD_E2E_CASES_DIR"] = str(cases_dir)
    env["VULD_E2E_PYTEST_BIN"] = str(pytest_path)

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_e2e_tests.sh"), "-k", "sample"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(capture_path.read_text(encoding="utf-8")) == ["-m", "e2e", "-k", "sample"]


def test_run_e2e_tests_fails_generic_live_gate_without_remote_provider(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    _write_case(cases_dir / "sample-case")
    pytest_path = tmp_path / "fake_pytest"
    config_path = tmp_path / "missing_api_keys.ini"
    _write_executable(pytest_path, "#!/usr/bin/env python3\nraise SystemExit(0)\n")

    env = os.environ.copy()
    env["VULD_RUN_E2E"] = "1"
    env["VULD_E2E_REQUIRE_REMOTE_PROVIDER"] = "1"
    env["VULD_E2E_CASES_DIR"] = str(cases_dir)
    env["VULD_E2E_CONFIG_PATH"] = str(config_path)
    env["VULD_E2E_PYTEST_BIN"] = str(pytest_path)
    env.pop("VUL_WEB_SEARCH_PROVIDER", None)
    env.pop("VUL_WEB_SEARCH_ENDPOINT", None)
    env.pop("VUL_WEB_SEARCH_API_KEY", None)

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_e2e_tests.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert "VULD_E2E_REQUIRE_REMOTE_PROVIDER=1" in completed.stderr


def test_run_e2e_tests_fails_schema_validation_with_override_cases_dir(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    _write_case(cases_dir / "broken-case", include_expectations=False)

    env = os.environ.copy()
    env["VULD_E2E_CASES_DIR"] = str(cases_dir)
    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_e2e_tests.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert "case schema validation failed" in completed.stderr


def test_run_e2e_tests_supports_repeat_helper_override(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    case_slug = "sample-case"
    _write_case(cases_dir / case_slug)
    pytest_path = tmp_path / "fake_pytest"
    repeat_helper = tmp_path / "fake_repeat_helper.sh"
    capture_path = tmp_path / "repeat_capture.json"

    _write_executable(pytest_path, "#!/usr/bin/env python3\nraise SystemExit(0)\n")
    _write_executable(
        repeat_helper,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path
Path({str(capture_path)!r}).write_text(json.dumps(sys.argv[1:]), encoding="utf-8")
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_RUN_E2E"] = "1"
    env["VULD_RUN_E2E_REPEAT"] = "1"
    env["VULD_E2E_CASES_DIR"] = str(cases_dir)
    env["VULD_E2E_PYTEST_BIN"] = str(pytest_path)
    env["VULD_E2E_REPEAT_HELPER"] = str(repeat_helper)
    env["VULD_E2E_REPEAT_CASE_DIR"] = case_slug
    env["VULD_E2E_REPEAT_ATTEMPTS"] = "2"
    env["VULD_E2E_REPEAT_MODE"] = "deterministic"
    env["VULD_E2E_REPEAT_OUTPUT_DIR"] = str(tmp_path / "repeat-out")

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_e2e_tests.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    captured = json.loads(capture_path.read_text(encoding="utf-8"))
    assert captured[0] == case_slug
    assert captured[1:] == ["2", "deterministic", str(tmp_path / "repeat-out")]
