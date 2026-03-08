from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.config import get_tavily_api_key
from tests.e2e.repeat_case import execute_repeat_gate


def _skip_reason() -> str:
    if not os.environ.get("VULD_RUN_E2E"):
        return "Set VULD_RUN_E2E=1 to enable slow E2E tests"
    if shutil.which("docker") is None:
        return "Docker CLI is not available"
    return ""


def _tavily_key_available() -> bool:
    return bool(os.environ.get("VUL_WEB_SEARCH_API_KEY") or get_tavily_api_key())


def _repeat_gate_enabled() -> bool:
    return bool(os.environ.get("VULD_RUN_E2E_REPEAT"))


def _skip_repeatability_pytest() -> bool:
    return bool(os.environ.get("VULD_SKIP_REPEATABILITY_PYTEST"))


def _live_gate_required() -> bool:
    return bool(os.environ.get("VULD_E2E_REQUIRE_TAVILY"))


@pytest.mark.e2e
def test_cwe89_basic_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)
    case_dir = REPO_ROOT / "tests/e2e/cases/cwe-89-basic"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "tests/e2e/run_case.py"),
        "--case",
        str(case_dir),
        "--expectations",
        str(case_dir / "expectations.no-remote.json"),
        "--mode",
        "deterministic",
        "--no-snapshot",
        "--output-dir",
        str(tmp_path),
    ]
    env = os.environ.copy()
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        pytest.fail(f"run_case failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    summary_path = tmp_path / "summary.json"
    assert summary_path.exists(), "summary.json was not created"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["sid"].startswith("sid-"), "SID was not recorded"
    assert any(bundle["slug"] == "cwe-89" and bundle.get("verify_pass") for bundle in summary["bundles"])


@pytest.mark.e2e
def test_sqli_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)
    case_dir = REPO_ROOT / "tests/e2e/cases/sqli-name-only"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "tests/e2e/run_case.py"),
        "--case",
        str(case_dir),
        "--expectations",
        str(case_dir / "expectations.no-remote.json"),
        "--mode",
        "deterministic",
        "--no-snapshot",
        "--output-dir",
        str(tmp_path),
    ]
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        pytest.fail(f"run_case failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    summary_path = tmp_path / "summary.json"
    assert summary_path.exists(), "summary.json was not created"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["sid"].startswith("sid-"), "SID was not recorded"
    assert summary["compiler_supported"] is True
    assert summary["compiler_strategy"] == "sqli_string_concat"
    assert any(
        bundle["slug"] == "cwe-89"
        and bundle.get("verify_pass")
        and bundle.get("compiler_supported") is True
        for bundle in summary["bundles"]
    )


@pytest.mark.e2e
def test_csrf_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)
    case_dir = REPO_ROOT / "tests/e2e/cases/csrf-name-only"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "tests/e2e/run_case.py"),
        "--case",
        str(case_dir),
        "--mode",
        "deterministic",
        "--no-snapshot",
        "--output-dir",
        str(tmp_path),
    ]
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        pytest.fail(f"run_case failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    summary_path = tmp_path / "summary.json"
    assert summary_path.exists(), "summary.json was not created"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["sid"].startswith("sid-"), "SID was not recorded"
    assert summary["compiler_supported"] is True
    assert summary["compiler_strategy"] == "csrf_missing_token"
    assert any(
        bundle["slug"] == "cwe-352"
        and bundle.get("verify_pass")
        and bundle.get("compiler_supported") is True
        for bundle in summary["bundles"]
    )


@pytest.mark.e2e
def test_ssrf_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)
    case_dir = REPO_ROOT / "tests/e2e/cases/ssrf-name-only"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "tests/e2e/run_case.py"),
        "--case",
        str(case_dir),
        "--mode",
        "deterministic",
        "--no-snapshot",
        "--output-dir",
        str(tmp_path),
    ]
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        pytest.fail(f"run_case failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    summary_path = tmp_path / "summary.json"
    assert summary_path.exists(), "summary.json was not created"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["sid"].startswith("sid-"), "SID was not recorded"
    assert summary["compiler_supported"] is True
    assert summary["compiler_strategy"] == "ssrf_loopback_fetch"
    assert any(
        bundle["slug"] == "cwe-918"
        and bundle.get("verify_pass")
        and bundle.get("compiler_supported") is True
        for bundle in summary["bundles"]
    )


@pytest.mark.e2e
def test_template_injection_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    case_dir = REPO_ROOT / "tests/e2e/cases/template-injection-name-only"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "tests/e2e/run_case.py"),
        "--case",
        str(case_dir),
        "--mode",
        "deterministic",
        "--no-snapshot",
        "--output-dir",
        str(tmp_path),
    ]
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        pytest.fail(f"run_case failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    summary_path = tmp_path / "summary.json"
    assert summary_path.exists(), "summary.json was not created"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["sid"].startswith("sid-"), "SID was not recorded"
    assert summary["compiler_supported"] is True
    assert summary["compiler_strategy"] == "template_injection_render"
    assert summary["generalization_class"] == "real_free_form_positive"
    assert summary["counts_as_generalization"] is True
    assert any(
        bundle["slug"] == "name-template-injection"
        and bundle.get("verify_pass")
        and bundle.get("compiler_supported") is True
        and bundle.get("counts_as_generalization") is True
        for bundle in summary["bundles"]
    )
    bundle = next(bundle for bundle in summary["bundles"] if bundle["slug"] == "name-template-injection")
    assert "Using generator_manifest.json PoC contract as fallback rule" not in str(bundle.get("evidence") or "")
    assert summary["reviewer"]["blocking_bundles"] == []


@pytest.mark.e2e
def test_path_traversal_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    case_dir = REPO_ROOT / "tests/e2e/cases/path-traversal-name-only"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "tests/e2e/run_case.py"),
        "--case",
        str(case_dir),
        "--mode",
        "deterministic",
        "--no-snapshot",
        "--output-dir",
        str(tmp_path),
    ]
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        pytest.fail(f"run_case failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    summary_path = tmp_path / "summary.json"
    assert summary_path.exists(), "summary.json was not created"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["sid"].startswith("sid-"), "SID was not recorded"
    assert summary["compiler_supported"] is True
    assert summary["compiler_strategy"] == "path_traversal_file_read"
    assert any(
        bundle["slug"] == "cwe-22"
        and bundle.get("verify_pass")
        and bundle.get("compiler_supported") is True
        for bundle in summary["bundles"]
    )
    assert summary["reviewer"]["blocking_bundles"] == []


@pytest.mark.e2e
def test_template_injection_alias_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    case_dir = REPO_ROOT / "tests/e2e/cases/template-injection-alias-name-only"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "tests/e2e/run_case.py"),
        "--case",
        str(case_dir),
        "--mode",
        "deterministic",
        "--no-snapshot",
        "--output-dir",
        str(tmp_path),
    ]
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        pytest.fail(f"run_case failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    summary_path = tmp_path / "summary.json"
    assert summary_path.exists(), "summary.json was not created"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["sid"].startswith("sid-"), "SID was not recorded"
    assert summary["compiler_supported"] is True
    assert summary["compiler_strategy"] == "template_injection_render"
    assert summary["generalization_class"] == "real_free_form_positive"
    assert summary["counts_as_generalization"] is True
    assert any(
        bundle["slug"] == "name-template-injection"
        and bundle.get("verify_pass")
        and bundle.get("compiler_supported") is True
        and bundle.get("counts_as_generalization") is True
        for bundle in summary["bundles"]
    )
    bundle = next(bundle for bundle in summary["bundles"] if bundle["slug"] == "name-template-injection")
    assert "Using generator_manifest.json PoC contract as fallback rule" not in str(bundle.get("evidence") or "")
    assert summary["reviewer"]["blocking_bundles"] == []


@pytest.mark.e2e
def test_xss_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    case_dir = REPO_ROOT / "tests/e2e/cases/xss-name-only"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "tests/e2e/run_case.py"),
        "--case",
        str(case_dir),
        "--mode",
        "deterministic",
        "--no-snapshot",
        "--output-dir",
        str(tmp_path),
    ]
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        pytest.fail(f"run_case failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    summary_path = tmp_path / "summary.json"
    assert summary_path.exists(), "summary.json was not created"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["sid"].startswith("sid-"), "SID was not recorded"
    assert summary["compiler_supported"] is True
    assert summary["compiler_strategy"] == "xss_reflected"
    assert any(
        bundle["slug"] == "cwe-79"
        and bundle.get("verify_pass")
        and bundle.get("compiler_supported") is True
        for bundle in summary["bundles"]
    )
    assert summary["reviewer"]["blocking_bundles"] == []


@pytest.mark.e2e
def test_deserialization_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    case_dir = REPO_ROOT / "tests/e2e/cases/deserialization-name-only"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "tests/e2e/run_case.py"),
        "--case",
        str(case_dir),
        "--mode",
        "deterministic",
        "--no-snapshot",
        "--output-dir",
        str(tmp_path),
    ]
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        pytest.fail(f"run_case failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    summary_path = tmp_path / "summary.json"
    assert summary_path.exists(), "summary.json was not created"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["sid"].startswith("sid-"), "SID was not recorded"
    assert summary["compiler_supported"] is True
    assert summary["compiler_strategy"] == "deserialization_pickle_body"
    assert any(
        bundle["slug"] == "cwe-502"
        and bundle.get("verify_pass")
        and bundle.get("compiler_supported") is True
        for bundle in summary["bundles"]
    )
    assert summary["reviewer"]["blocking_bundles"] == []


@pytest.mark.e2e
def test_command_injection_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    case_dir = REPO_ROOT / "tests/e2e/cases/command-injection-name-only"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "tests/e2e/run_case.py"),
        "--case",
        str(case_dir),
        "--mode",
        "deterministic",
        "--no-snapshot",
        "--output-dir",
        str(tmp_path),
    ]
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        pytest.fail(f"run_case failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    summary_path = tmp_path / "summary.json"
    assert summary_path.exists(), "summary.json was not created"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["sid"].startswith("sid-"), "SID was not recorded"
    assert summary["compiler_supported"] is True
    assert summary["compiler_strategy"] == "command_injection_shell"
    assert any(
        bundle["slug"] == "cwe-78"
        and bundle.get("verify_pass")
        and bundle.get("compiler_supported") is True
        for bundle in summary["bundles"]
    )
    assert summary["reviewer"]["blocking_bundles"] == []


@pytest.mark.e2e
def test_open_redirect_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    case_dir = REPO_ROOT / "tests/e2e/cases/open-redirect-name-only"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "tests/e2e/run_case.py"),
        "--case",
        str(case_dir),
        "--mode",
        "deterministic",
        "--no-snapshot",
        "--output-dir",
        str(tmp_path),
    ]
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        pytest.fail(f"run_case failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    summary_path = tmp_path / "summary.json"
    assert summary_path.exists(), "summary.json was not created"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["sid"].startswith("sid-"), "SID was not recorded"
    assert summary["pipeline_result"] == "success"
    assert summary["promotion_eligible"] is True
    assert summary["compiler_supported"] is True
    assert summary["compiler_strategy"] == "open_redirect_reflect"
    assert summary["generalization_class"] == "real_free_form_positive"
    assert summary["counts_as_generalization"] is True
    assert any(
        bundle["slug"] == "name-open-redirect"
        and bundle.get("verify_pass")
        and bundle.get("promotion_eligible")
        and bundle.get("compiler_supported") is True
        and bundle.get("counts_as_generalization") is True
        for bundle in summary["bundles"]
    )
    bundle = next(bundle for bundle in summary["bundles"] if bundle["slug"] == "name-open-redirect")
    assert "Using generator_manifest.json PoC contract as fallback rule" not in str(bundle.get("evidence") or "")


@pytest.mark.e2e
def test_open_redirect_alias_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    case_dir = REPO_ROOT / "tests/e2e/cases/open-redirect-alias-name-only"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "tests/e2e/run_case.py"),
        "--case",
        str(case_dir),
        "--mode",
        "deterministic",
        "--no-snapshot",
        "--output-dir",
        str(tmp_path),
    ]
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        pytest.fail(f"run_case failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    summary_path = tmp_path / "summary.json"
    assert summary_path.exists(), "summary.json was not created"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["sid"].startswith("sid-"), "SID was not recorded"
    assert summary["pipeline_result"] == "success"
    assert summary["promotion_eligible"] is True
    assert summary["compiler_supported"] is True
    assert summary["compiler_strategy"] == "open_redirect_reflect"
    assert summary["generalization_class"] == "real_free_form_positive"
    assert summary["counts_as_generalization"] is True
    assert any(
        bundle["slug"] == "name-open-redirect"
        and bundle.get("verify_pass")
        and bundle.get("promotion_eligible")
        and bundle.get("compiler_supported") is True
        and bundle.get("counts_as_generalization") is True
        for bundle in summary["bundles"]
    )
    bundle = next(bundle for bundle in summary["bundles"] if bundle["slug"] == "name-open-redirect")
    assert "Using generator_manifest.json PoC contract as fallback rule" not in str(bundle.get("evidence") or "")


@pytest.mark.e2e
def test_ldap_injection_negative_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    case_dir = REPO_ROOT / "tests/e2e/cases/ldap-injection-negative"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "tests/e2e/run_case.py"),
        "--case",
        str(case_dir),
        "--mode",
        "deterministic",
        "--no-snapshot",
        "--output-dir",
        str(tmp_path),
    ]
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        pytest.fail(f"run_case failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    summary_path = tmp_path / "summary.json"
    assert summary_path.exists(), "summary.json was not created"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["sid"].startswith("sid-"), "SID was not recorded"
    assert summary["pipeline_result"] == "failure"
    assert summary["promotion_eligible"] is False
    assert summary["manifest_file"] == "failure_manifest.json"
    assert summary["generalization_class"] == "unsupported_free_form_negative"
    assert summary["counts_as_generalization"] is False
    assert any(
        bundle["slug"] == "name-ldap-injection"
        and bundle.get("compiler_supported") is False
        and bundle.get("generalization_class") == "unsupported_free_form_negative"
        and "unsupported" in str(bundle.get("compiler_reason") or "").lower()
        for bundle in summary["bundles"]
    )


@pytest.mark.e2e
def test_cwe89_basic_repeatability_gate(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)
    if _skip_repeatability_pytest():
        pytest.skip("Repeatability gate is executed via ops/ci/run_repeatability_gate.sh in this run")
    if not _repeat_gate_enabled():
        pytest.skip("Set VULD_RUN_E2E_REPEAT=1 to enable repeatability gate")

    case_dir = REPO_ROOT / "tests/e2e/cases/cwe-89-basic"
    report = execute_repeat_gate(
        case_dir,
        attempts=3,
        mode="deterministic",
        snapshot=False,
        output_dir=tmp_path,
    )

    assert report["passed"] is True
    assert report["attempt_count"] == 3
    assert report["failure_count"] == 0


@pytest.mark.e2e
def test_template_injection_name_only_repeatability_gate(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)
    if _skip_repeatability_pytest():
        pytest.skip("Repeatability gate is executed via ops/ci/run_repeatability_gate.sh in this run")
    if not _repeat_gate_enabled():
        pytest.skip("Set VULD_RUN_E2E_REPEAT=1 to enable repeatability gate")
    if not _tavily_key_available():
        if _live_gate_required():
            pytest.fail("Tavily API key is required for mandatory Template Injection repeatability gate")
        pytest.skip("Tavily API key is not configured in env or config/api_keys.ini")

    case_dir = REPO_ROOT / "tests/e2e/cases/template-injection-name-only"
    report = execute_repeat_gate(
        case_dir,
        attempts=3,
        mode="deterministic",
        snapshot=False,
        output_dir=tmp_path,
    )

    assert report["passed"] is True
    assert report["attempt_count"] == 3
    assert report["failure_count"] == 0


@pytest.mark.e2e
def test_unknown_cwe_synthesis_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)
    case_dir = REPO_ROOT / "tests/e2e/cases/cwe-unknown-basic"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "tests/e2e/run_case.py"),
        "--case",
        str(case_dir),
        "--expectations",
        str(case_dir / "expectations.no-remote.json"),
        "--mode",
        "deterministic",
        "--no-snapshot",
        "--output-dir",
        str(tmp_path),
    ]
    env = os.environ.copy()
    env["VUL_WEB_SEARCH_PROVIDER"] = "none"
    env.pop("VUL_WEB_SEARCH_ENDPOINT", None)
    env.pop("VUL_WEB_SEARCH_API_KEY", None)
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        pytest.fail(f"run_case failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    summary_path = tmp_path / "summary.json"
    assert summary_path.exists(), "summary.json was not created"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["pipeline_result"] == "failure"
    assert summary["manifest_file"] == "failure_manifest.json"
    assert any(
        bundle["slug"] == "cwe-9999"
        and bundle.get("promotion_eligible") is False
        and "Insufficient researcher evidence" in str(bundle.get("failure_reason") or "")
        for bundle in summary["bundles"]
    )


@pytest.mark.e2e
def test_unknown_cwe_live_tavily_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)
    if not _tavily_key_available():
        if _live_gate_required():
            pytest.fail("Tavily API key is required for mandatory live unknown gate")
        pytest.skip("Tavily API key is not configured in env or config/api_keys.ini")

    case_dir = REPO_ROOT / "tests/e2e/cases/cwe-unknown-basic"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "tests/e2e/run_case.py"),
        "--case",
        str(case_dir),
        "--mode",
        "deterministic",
        "--no-snapshot",
        "--output-dir",
        str(tmp_path),
    ]
    env = os.environ.copy()
    env["VUL_WEB_SEARCH_PROVIDER"] = "tavily"
    env.pop("VUL_WEB_SEARCH_ENDPOINT", None)
    if get_tavily_api_key():
        env.pop("VUL_WEB_SEARCH_API_KEY", None)
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        pytest.fail(f"run_case failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")

    summary_path = tmp_path / "summary.json"
    assert summary_path.exists(), "summary.json was not created"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["sid"].startswith("sid-"), "SID was not recorded"
    assert summary["promotion_eligible"] is False
    assert summary["generalization_class"] == "synthetic_regression"
    assert summary["counts_as_generalization"] is False
    assert summary["generalization_summary"]["positive_generalization_bundles"] == 0
    assert any(
        bundle["slug"] == "cwe-9999"
        and bundle.get("verify_pass")
        and bundle.get("run_passed")
        and bundle.get("promotion_eligible") is False
        and bundle.get("generalization_class") == "synthetic_regression"
        and bundle.get("counts_as_generalization") is False
        for bundle in summary["bundles"]
    )
    assert summary["reviewer"]["blocking_bundles"] == []
