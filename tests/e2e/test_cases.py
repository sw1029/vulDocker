from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.config import get_tavily_api_key
from tests.e2e.repeat_case import execute_repeat_gate

CURATED_LOWER_BOUND_GENERALIZATION_CLASS = "real_free_form_curated_lower_bound"


@lru_cache(maxsize=1)
def _docker_ready_reason() -> str:
    docker_bin = shutil.which("docker")
    if docker_bin is None:
        return "Docker CLI is not available"
    proc = subprocess.run(
        [docker_bin, "info"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return "Docker daemon is not reachable"
    return ""


def _skip_reason() -> str:
    if not os.environ.get("VULD_RUN_E2E"):
        return "Set VULD_RUN_E2E=1 to enable slow E2E tests"
    return _docker_ready_reason()


def _case_requires_docker(case_name: str) -> bool:
    case_dir = REPO_ROOT / "tests/e2e/cases" / case_name
    expectations_path = case_dir / "expectations.json"
    if not expectations_path.exists():
        return True
    expectations = json.loads(expectations_path.read_text(encoding="utf-8"))
    manifest = expectations.get("manifest")
    if not isinstance(manifest, dict):
        return True
    failure = manifest.get("failure")
    if not isinstance(failure, dict):
        return True
    stage = str(failure.get("stage") or "").strip().upper()
    return stage not in {"CAPABILITY_CHECK", "RESEARCH"}


def _skip_reason_for_case(case_name: str) -> str:
    if not os.environ.get("VULD_RUN_E2E"):
        return "Set VULD_RUN_E2E=1 to enable slow E2E tests"
    if _case_requires_docker(case_name):
        return _docker_ready_reason()
    return ""


def _tavily_key_available() -> bool:
    return bool(os.environ.get("VUL_WEB_SEARCH_API_KEY") or get_tavily_api_key())


def _repeat_gate_enabled() -> bool:
    return bool(os.environ.get("VULD_RUN_E2E_REPEAT"))


def _skip_repeatability_pytest() -> bool:
    return bool(os.environ.get("VULD_SKIP_REPEATABILITY_PYTEST"))


def _live_gate_required() -> bool:
    return bool(os.environ.get("VULD_E2E_REQUIRE_TAVILY"))


def _run_case_dir(tmp_path: Path, case_name: str) -> dict:
    case_dir = REPO_ROOT / "tests/e2e/cases" / case_name
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
    return json.loads(summary_path.read_text(encoding="utf-8"))


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
def test_sqli_sidecar_template_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)
    case_dir = REPO_ROOT / "tests/e2e/cases/sqli-sidecar-template"
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
    assert summary["pipeline_result"] == "success"
    assert summary["generation_origin"] == "built_in_template"
    assert summary["dynamicness_verdict"] == "template-assisted"
    assert summary["executor_feasibility_status"] == "configured"
    bundle = next(bundle for bundle in summary["bundles"] if bundle["slug"] == "cwe-89")
    assert bundle["verify_pass"] is True
    assert bundle["generation_origin"] == "built_in_template"
    assert bundle["executor_feasibility_status"] == "configured"


@pytest.mark.e2e
def test_sqli_sidecar_compiler_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)
    case_dir = REPO_ROOT / "tests/e2e/cases/sqli-sidecar-compiler"
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
    assert summary["pipeline_result"] == "success"
    assert summary["generation_origin"] == "compiler_generated"
    assert summary["dynamicness_verdict"] == "compiler-first"
    assert summary["compiler_strategy"] == "sqli_string_concat_mysql"
    assert summary["executor_feasibility_status"] == "configured"
    bundle = next(bundle for bundle in summary["bundles"] if bundle["slug"] == "cwe-89")
    assert bundle["verify_pass"] is True
    assert bundle["generation_origin"] == "compiler_generated"
    assert bundle["compiler_strategy"] == "sqli_string_concat_mysql"
    assert bundle["executor_feasibility_status"] == "configured"


@pytest.mark.e2e
def test_sqli_sidecar_compiler_custom_env_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)
    case_dir = REPO_ROOT / "tests/e2e/cases/sqli-sidecar-compiler-custom-env"
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
    assert summary["pipeline_result"] == "success"
    assert summary["generation_origin"] == "compiler_generated"
    assert summary["dynamicness_verdict"] == "compiler-first"
    assert summary["compiler_strategy"] == "sqli_string_concat_mysql"
    assert summary["executor_feasibility_status"] == "configured"
    assert summary["service_env"] == {
        "APP_PORT": "5000",
        "DB_HOST": "db-internal",
        "DB_PORT": "3306",
        "DB_USER": "custom_user",
        "DB_PASSWORD": "custom_pw",
        "DB_NAME": "runtime_db_custom",
    }
    bundle = next(bundle for bundle in summary["bundles"] if bundle["slug"] == "cwe-89")
    assert bundle["verify_pass"] is True
    assert bundle["generation_origin"] == "compiler_generated"
    assert bundle["compiler_strategy"] == "sqli_string_concat_mysql"
    assert bundle["executor_feasibility_status"] == "configured"
    assert bundle["service_env"] == summary["service_env"]


@pytest.mark.e2e
def test_trusted_dynamic_sqli_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)
    case_dir = REPO_ROOT / "tests/e2e/cases/trusted-dynamic-sqli"
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
    assert summary["pipeline_result"] == "success"
    assert summary["generation_origin"] == "llm_manifest"
    assert summary["llm_fixture_used"] is True
    assert summary["dynamicness_verdict"] == "trusted dynamic"
    bundle = next(bundle for bundle in summary["bundles"] if bundle["slug"] == "cwe-89")
    assert bundle["verification_rule_source"] == "declared_rule"
    assert bundle["verification_trust"] == "high"
    assert bundle["verification_independence"] == "independent"
    assert bundle["llm_fixture_used"] is True


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
    assert summary["generalization_class"] == CURATED_LOWER_BOUND_GENERALIZATION_CLASS
    assert summary["counts_as_generalization"] is False
    assert any(
        bundle["slug"] == "name-template-injection"
        and bundle.get("verify_pass")
        and bundle.get("compiler_supported") is True
        and bundle.get("counts_as_generalization") is False
        for bundle in summary["bundles"]
    )
    bundle = next(bundle for bundle in summary["bundles"] if bundle["slug"] == "name-template-injection")
    assert "Using generator_manifest.json PoC contract as fallback rule" not in str(bundle.get("evidence") or "")
    assert bundle["verification_rule_source"] == "declared_rule"
    assert bundle["verification_trust"] == "high"
    assert bundle["verification_independence"] == "independent"
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
    assert summary["generalization_class"] == CURATED_LOWER_BOUND_GENERALIZATION_CLASS
    assert summary["counts_as_generalization"] is False
    assert any(
        bundle["slug"] == "name-template-injection"
        and bundle.get("verify_pass")
        and bundle.get("compiler_supported") is True
        and bundle.get("counts_as_generalization") is False
        for bundle in summary["bundles"]
    )
    bundle = next(bundle for bundle in summary["bundles"] if bundle["slug"] == "name-template-injection")
    assert "Using generator_manifest.json PoC contract as fallback rule" not in str(bundle.get("evidence") or "")
    assert summary["reviewer"]["blocking_bundles"] == []


@pytest.mark.e2e
def test_template_injection_paraphrase_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    case_dir = REPO_ROOT / "tests/e2e/cases/template-injection-paraphrase-name-only"
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
    assert summary["name_resolution"]["source"] == "alias"
    assert summary["name_resolution"]["resolved_vuln_id"] == "NAME-TEMPLATE-INJECTION"
    assert summary["name_resolution"]["confidence"] == "high"
    assert summary["name_resolution"]["match_class"] == "catalog_alias"
    assert summary["generalization_class"] == CURATED_LOWER_BOUND_GENERALIZATION_CLASS
    assert summary["counts_as_generalization"] is False
    assert any(
        bundle["slug"] == "name-template-injection"
        and bundle.get("verify_pass")
        and bundle.get("compiler_supported") is True
        and bundle.get("counts_as_generalization") is False
        for bundle in summary["bundles"]
    )
    bundle = next(bundle for bundle in summary["bundles"] if bundle["slug"] == "name-template-injection")
    assert "Using generator_manifest.json PoC contract as fallback rule" not in str(bundle.get("evidence") or "")
    assert summary["reviewer"]["blocking_bundles"] == []


@pytest.mark.e2e
def test_template_injection_reordered_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    case_dir = REPO_ROOT / "tests/e2e/cases/template-injection-reordered-name-only"
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
    assert summary["name_resolution"]["source"] == "fragment_strategy_fallback"
    assert summary["name_resolution"]["resolved_vuln_id"] == "NAME-TEMPLATE-INJECTION"
    assert summary["name_resolution"]["confidence"] == "medium"
    assert summary["name_resolution"]["match_class"] == "token_match"
    assert summary["generalization_class"] == "real_free_form_non_generalizing"
    assert summary["counts_as_generalization"] is False
    assert summary["generalization_confidence"] == "medium"
    assert summary["generalization_basis"] == "token_match"
    assert any(
        bundle["slug"] == "name-template-injection"
        and bundle.get("verify_pass")
        and bundle.get("compiler_supported") is True
        and bundle.get("counts_as_generalization") is False
        for bundle in summary["bundles"]
    )
    assert summary["reviewer"]["blocking_bundles"] == []


@pytest.mark.e2e
def test_template_injection_reordered_high_confidence_gate_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    case_dir = REPO_ROOT / "tests/e2e/cases/template-injection-reordered-high-confidence-gate"
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
    assert summary["promotion_eligible"] is False
    assert any("name_resolution_confidence:medium" in reason for reason in summary["promotion_reasons"])
    assert any("name_resolution_policy:min_high" in reason for reason in summary["promotion_reasons"])
    assert summary["compiler_supported"] is True
    assert summary["compiler_strategy"] == "template_injection_render"
    assert summary["name_resolution"]["source"] == "fragment_strategy_fallback"
    assert summary["name_resolution"]["resolved_vuln_id"] == "NAME-TEMPLATE-INJECTION"
    assert summary["name_resolution"]["confidence"] == "medium"
    assert summary["name_resolution"]["match_class"] == "token_match"
    assert summary["generalization_class"] == "real_free_form_non_generalizing"
    assert summary["counts_as_generalization"] is False
    assert summary["generalization_confidence"] == "medium"
    assert summary["generalization_basis"] == "token_match"
    bundle = next(bundle for bundle in summary["bundles"] if bundle["slug"] == "name-template-injection")
    assert bundle["promotion_eligible"] is False
    assert bundle["counts_as_generalization"] is False
    assert bundle["generalization_confidence"] == "medium"
    assert bundle["generalization_basis"] == "token_match"
    assert summary["reviewer"]["blocking_bundles"] == []


@pytest.mark.e2e
def test_template_injection_fastapi_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    case_dir = REPO_ROOT / "tests/e2e/cases/template-injection-fastapi-name-only"
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
    assert summary["compiler_strategy"] == "template_injection_render"
    assert summary["stack_scaffold_id"] == "python/fastapi"
    assert summary["fragment_id"] == "render_jinja_template_fastapi"
    assert summary["verification_rule_source"] == "declared_rule"
    assert summary["verification_trust"] == "high"
    assert summary["verification_independence"] == "independent"
    bundle = next(bundle for bundle in summary["bundles"] if bundle["slug"] == "name-template-injection")
    assert bundle["verify_pass"] is True
    assert bundle["stack_scaffold_id"] == "python/fastapi"
    assert bundle["fragment_id"] == "render_jinja_template_fastapi"
    assert bundle["verification_rule_source"] == "declared_rule"
    assert bundle["verification_trust"] == "high"
    assert bundle["verification_independence"] == "independent"


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
def test_xss_fastapi_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    case_dir = REPO_ROOT / "tests/e2e/cases/xss-fastapi-name-only"
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
    assert summary["compiler_strategy"] == "xss_reflected"
    assert summary["stack_scaffold_id"] == "python/fastapi"
    assert summary["fragment_id"] == "render_reflect_route_fastapi"
    assert summary["verification_rule_source"] == "declared_rule"
    assert summary["verification_trust"] == "high"
    assert summary["verification_independence"] == "independent"
    bundle = next(bundle for bundle in summary["bundles"] if bundle["slug"] == "cwe-79")
    assert bundle["verify_pass"] is True
    assert bundle["stack_scaffold_id"] == "python/fastapi"
    assert bundle["fragment_id"] == "render_reflect_route_fastapi"
    assert bundle["verification_rule_source"] == "declared_rule"
    assert bundle["verification_trust"] == "high"
    assert bundle["verification_independence"] == "independent"


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
def test_code_injection_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    case_dir = REPO_ROOT / "tests/e2e/cases/code-injection-name-only"
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
    assert summary["compiler_strategy"] == "code_injection_eval"
    assert any(
        bundle["slug"] == "cwe-94"
        and bundle.get("verify_pass")
        and bundle.get("compiler_supported") is True
        for bundle in summary["bundles"]
    )
    assert summary["reviewer"]["blocking_bundles"] == []


@pytest.mark.e2e
def test_code_injection_alias_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    case_dir = REPO_ROOT / "tests/e2e/cases/code-injection-alias-name-only"
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
    assert summary["compiler_strategy"] == "code_injection_eval"
    assert any(
        bundle["slug"] == "cwe-94"
        and bundle.get("verify_pass")
        and bundle.get("compiler_supported") is True
        for bundle in summary["bundles"]
    )
    assert summary["reviewer"]["blocking_bundles"] == []


@pytest.mark.e2e
def test_sqli_dynamic_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    summary = _run_case_dir(tmp_path, "sqli-dynamic-name-only")
    assert summary["sid"].startswith("sid-"), "SID was not recorded"
    assert summary["pipeline_result"] == "success"
    assert summary["generation_origin"] == "deterministic_fallback"
    assert summary["dynamicness_verdict"] == "deterministic fallback dependent"
    assert summary["open_world_class"] == "semantic_guided_minimal_dynamic"
    assert summary["generalization_class"] == "real_free_form_non_generalizing"


@pytest.mark.e2e
def test_open_redirect_dynamic_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    summary = _run_case_dir(tmp_path, "open-redirect-dynamic-name-only")
    assert summary["sid"].startswith("sid-"), "SID was not recorded"
    assert summary["pipeline_result"] == "success"
    assert summary["generation_origin"] == "deterministic_fallback"
    assert summary["dynamicness_verdict"] == "deterministic fallback dependent"
    assert summary["open_world_class"] == "semantic_guided_minimal_dynamic"
    assert summary["generalization_class"] == "real_free_form_non_generalizing"
    assert summary["verification_rule_source"] == "declared_rule"
    assert summary["verification_trust"] == "high"
    assert summary["verification_independence"] == "independent"
    assert summary["artifact_quality"]["metamorphic_present"] is True
    assert summary["name_only_primary_focus"] == "stack_or_runtime_design"
    assert "oracle_realism" not in (summary["name_only_planning_focus"] or {}).get("by_focus", {})


@pytest.mark.e2e
def test_open_redirect_strict_dynamic_stub_case(tmp_path: Path) -> None:
    reason = _skip_reason_for_case("open-redirect-strict-dynamic-stub")
    if reason:
        pytest.skip(reason)

    summary = _run_case_dir(tmp_path, "open-redirect-strict-dynamic-stub")
    assert summary["sid"].startswith("sid-"), "SID was not recorded"
    assert summary["pipeline_result"] == "failure"
    assert summary["manifest_file"] == "failure_manifest.json"
    assert summary["provider_health_state"] == "strict_dynamic_live_llm_unavailable"
    assert summary["failure"]["stage"] == "CAPABILITY_CHECK"
    assert summary["failure"]["terminal_failure_class"] == "strict_dynamic_live_llm_unavailable"
    assert summary["open_world_class"] == "name_driven_capability_gate_failed"
    assert summary["strict_open_world_class"] == "strict_dynamic_capability_unavailable"
    assert summary["intent_satisfaction"]["status"] == "strict_dynamic_failed"
    assert summary["name_only_decision"] == "fail_closed"
    assert summary["name_only_next_required_step"] == "capability_or_research"
    assert summary["name_only_outcome"]["decision"] == "fail_closed"
    assert summary["name_only_outcome"]["satisfies_intent_contract"] is False
    assert summary["request_ir"]["name_driven"] is True
    bundle = next(bundle for bundle in summary["bundles"] if bundle["slug"] == "name-open-redirect")
    assert bundle["terminal_failure_class"] == "strict_dynamic_live_llm_unavailable"
    assert bundle["name_only_outcome"]["decision"] == "fail_closed"
    assert "capability precheck" in str(bundle.get("failure_reason") or "")


@pytest.mark.e2e
def test_open_redirect_strict_dynamic_no_remote_case(tmp_path: Path) -> None:
    reason = _skip_reason_for_case("open-redirect-strict-dynamic-no-remote")
    if reason:
        pytest.skip(reason)

    summary = _run_case_dir(tmp_path, "open-redirect-strict-dynamic-no-remote")
    assert summary["sid"].startswith("sid-"), "SID was not recorded"
    assert summary["pipeline_result"] == "failure"
    assert summary["manifest_file"] == "failure_manifest.json"
    assert summary["provider_health_state"] == "strict_dynamic_remote_research_unavailable"
    assert summary["failure"]["stage"] == "CAPABILITY_CHECK"
    assert summary["failure"]["terminal_failure_class"] == "strict_dynamic_remote_research_unavailable"
    assert summary["open_world_class"] == "name_driven_capability_gate_failed"
    assert summary["strict_open_world_class"] == "strict_dynamic_capability_unavailable"
    assert summary["intent_satisfaction"]["status"] == "strict_dynamic_failed"
    assert summary["name_only_decision"] == "fail_closed"
    assert summary["name_only_next_required_step"] == "capability_or_research"
    assert summary["name_only_outcome"]["decision"] == "fail_closed"
    assert summary["name_only_outcome"]["satisfies_intent_contract"] is False
    assert summary["request_ir"]["name_driven"] is True
    bundle = next(bundle for bundle in summary["bundles"] if bundle["slug"] == "name-open-redirect")
    assert bundle["terminal_failure_class"] == "strict_dynamic_remote_research_unavailable"
    assert bundle["name_only_outcome"]["decision"] == "fail_closed"
    assert "remote researcher evidence" in str(bundle.get("failure_reason") or "")


@pytest.mark.e2e
def test_xss_dynamic_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    summary = _run_case_dir(tmp_path, "xss-dynamic-name-only")
    assert summary["sid"].startswith("sid-"), "SID was not recorded"
    assert summary["pipeline_result"] == "success"
    assert summary["generation_origin"] == "deterministic_fallback"
    assert summary["dynamicness_verdict"] == "deterministic fallback dependent"
    assert summary["open_world_class"] == "semantic_guided_minimal_dynamic"
    assert summary["generalization_class"] == "real_free_form_non_generalizing"
    assert summary["verification_rule_source"] == "declared_rule"
    assert summary["verification_trust"] == "high"
    assert summary["verification_independence"] == "independent"


@pytest.mark.e2e
def test_path_traversal_dynamic_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    summary = _run_case_dir(tmp_path, "path-traversal-dynamic-name-only")
    assert summary["sid"].startswith("sid-"), "SID was not recorded"
    assert summary["pipeline_result"] == "success"
    assert summary["generation_origin"] == "deterministic_fallback"
    assert summary["dynamicness_verdict"] == "deterministic fallback dependent"
    assert summary["open_world_class"] == "semantic_guided_minimal_dynamic"
    assert summary["generalization_class"] == "real_free_form_non_generalizing"
    assert summary["verification_rule_source"] == "declared_rule"
    assert summary["verification_trust"] == "high"
    assert summary["verification_independence"] == "independent"


@pytest.mark.e2e
def test_ssrf_dynamic_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    summary = _run_case_dir(tmp_path, "ssrf-dynamic-name-only")
    assert summary["sid"].startswith("sid-"), "SID was not recorded"
    assert summary["pipeline_result"] == "success"
    assert summary["generation_origin"] == "deterministic_fallback"
    assert summary["dynamicness_verdict"] == "deterministic fallback dependent"
    assert summary["open_world_class"] == "semantic_guided_minimal_dynamic"
    assert summary["generalization_class"] == "real_free_form_non_generalizing"
    assert summary["verification_rule_source"] == "declared_rule"
    assert summary["verification_trust"] == "high"
    assert summary["verification_independence"] == "independent"


@pytest.mark.e2e
def test_csrf_dynamic_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    summary = _run_case_dir(tmp_path, "csrf-dynamic-name-only")
    assert summary["sid"].startswith("sid-"), "SID was not recorded"
    assert summary["pipeline_result"] == "success"
    assert summary["generation_origin"] == "deterministic_fallback"
    assert summary["dynamicness_verdict"] == "deterministic fallback dependent"
    assert summary["open_world_class"] == "semantic_guided_minimal_dynamic"
    assert summary["generalization_class"] == "real_free_form_non_generalizing"
    assert summary["verification_rule_source"] == "declared_rule"
    assert summary["verification_trust"] == "high"
    assert summary["verification_independence"] == "independent"


@pytest.mark.e2e
def test_deserialization_dynamic_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    summary = _run_case_dir(tmp_path, "deserialization-dynamic-name-only")
    assert summary["sid"].startswith("sid-"), "SID was not recorded"
    assert summary["pipeline_result"] == "success"
    assert summary["generation_origin"] == "deterministic_fallback"
    assert summary["dynamicness_verdict"] == "deterministic fallback dependent"
    assert summary["open_world_class"] == "semantic_guided_minimal_dynamic"
    assert summary["generalization_class"] == "real_free_form_non_generalizing"
    assert summary["verification_rule_source"] == "declared_rule"
    assert summary["verification_trust"] == "high"
    assert summary["verification_independence"] == "independent"


@pytest.mark.e2e
def test_command_injection_dynamic_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    summary = _run_case_dir(tmp_path, "command-injection-dynamic-name-only")
    assert summary["sid"].startswith("sid-"), "SID was not recorded"
    assert summary["pipeline_result"] == "success"
    assert summary["generation_origin"] == "deterministic_fallback"
    assert summary["dynamicness_verdict"] == "deterministic fallback dependent"
    assert summary["open_world_class"] == "semantic_guided_minimal_dynamic"
    assert summary["verification_rule_source"] == "declared_rule"
    assert summary["verification_trust"] == "high"
    assert summary["verification_independence"] == "independent"


@pytest.mark.e2e
def test_xxe_dynamic_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    summary = _run_case_dir(tmp_path, "xxe-dynamic-name-only")
    assert summary["sid"].startswith("sid-"), "SID was not recorded"
    assert summary["pipeline_result"] == "success"
    assert summary["generation_origin"] == "deterministic_fallback"
    assert summary["dynamicness_verdict"] == "deterministic fallback dependent"
    assert summary["open_world_class"] == "semantic_guided_minimal_dynamic"
    assert summary["generalization_class"] == "real_free_form_non_generalizing"


@pytest.mark.e2e
def test_code_injection_dynamic_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    summary = _run_case_dir(tmp_path, "code-injection-dynamic-name-only")
    assert summary["sid"].startswith("sid-"), "SID was not recorded"
    assert summary["pipeline_result"] == "success"
    assert summary["generation_origin"] == "deterministic_fallback"
    assert summary["dynamicness_verdict"] == "deterministic fallback dependent"
    assert summary["open_world_class"] == "semantic_guided_minimal_dynamic"
    assert summary["generalization_class"] == "real_free_form_non_generalizing"
    assert summary["verification_rule_source"] == "declared_rule"
    assert summary["verification_trust"] == "high"
    assert summary["verification_independence"] == "independent"


@pytest.mark.e2e
def test_ldap_injection_dynamic_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    summary = _run_case_dir(tmp_path, "ldap-injection-dynamic-name-only")
    assert summary["sid"].startswith("sid-"), "SID was not recorded"
    assert summary["pipeline_result"] == "success"
    assert summary["generation_origin"] == "deterministic_fallback"
    assert summary["dynamicness_verdict"] == "deterministic fallback dependent"
    assert summary["open_world_class"] == "semantic_guided_minimal_dynamic"
    assert summary["generalization_class"] == "real_free_form_non_generalizing"
    assert summary["verification_rule_source"] == "declared_rule"
    assert summary["verification_trust"] == "high"
    assert summary["verification_independence"] == "independent"


@pytest.mark.e2e
def test_template_injection_dynamic_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    summary = _run_case_dir(tmp_path, "template-injection-dynamic-name-only")
    assert summary["sid"].startswith("sid-"), "SID was not recorded"
    assert summary["pipeline_result"] == "success"
    assert summary["generation_origin"] == "deterministic_fallback"
    assert summary["dynamicness_verdict"] == "deterministic fallback dependent"
    assert summary["open_world_class"] == "semantic_guided_minimal_dynamic"
    assert summary["generalization_class"] == "real_free_form_non_generalizing"
    assert summary["verification_rule_source"] == "declared_rule"
    assert summary["verification_trust"] == "high"
    assert summary["verification_independence"] == "independent"


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
    assert summary["verification_rule_source"] == "declared_rule"
    assert summary["verification_trust"] == "high"
    assert summary["verification_independence"] == "independent"
    assert summary["generalization_class"] == CURATED_LOWER_BOUND_GENERALIZATION_CLASS
    assert summary["counts_as_generalization"] is False
    assert any(
        bundle["slug"] == "name-open-redirect"
        and bundle.get("verify_pass")
        and bundle.get("promotion_eligible")
        and bundle.get("compiler_supported") is True
        and bundle.get("counts_as_generalization") is False
        for bundle in summary["bundles"]
    )
    bundle = next(bundle for bundle in summary["bundles"] if bundle["slug"] == "name-open-redirect")
    assert bundle["verification_rule_source"] == "declared_rule"
    assert bundle["verification_trust"] == "high"
    assert bundle["verification_independence"] == "independent"
    assert "Using generator_manifest.json PoC contract as fallback rule" not in str(bundle.get("evidence") or "")


@pytest.mark.e2e
def test_open_redirect_fastapi_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    case_dir = REPO_ROOT / "tests/e2e/cases/open-redirect-fastapi-name-only"
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
    assert summary["stack_scaffold_id"] == "python/fastapi"
    assert summary["fragment_id"] == "redirect_next_route_fastapi"
    bundle = next(bundle for bundle in summary["bundles"] if bundle["slug"] == "name-open-redirect")
    assert bundle["verify_pass"] is True
    assert bundle["stack_scaffold_id"] == "python/fastapi"
    assert bundle["fragment_id"] == "redirect_next_route_fastapi"


@pytest.mark.e2e
def test_ssrf_fastapi_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    case_dir = REPO_ROOT / "tests/e2e/cases/ssrf-fastapi-name-only"
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
    assert summary["compiler_strategy"] == "ssrf_loopback_fetch"
    assert summary["stack_scaffold_id"] == "python/fastapi"
    assert summary["fragment_id"] == "loopback_fetch_route_fastapi"
    assert summary["verification_rule_source"] == "declared_rule"
    assert summary["verification_trust"] == "high"
    assert summary["verification_independence"] == "independent"
    bundle = next(bundle for bundle in summary["bundles"] if bundle["slug"] == "cwe-918")
    assert bundle["verify_pass"] is True
    assert bundle["stack_scaffold_id"] == "python/fastapi"
    assert bundle["fragment_id"] == "loopback_fetch_route_fastapi"
    assert bundle["verification_rule_source"] == "declared_rule"
    assert bundle["verification_trust"] == "high"
    assert bundle["verification_independence"] == "independent"


@pytest.mark.e2e
def test_path_traversal_fastapi_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    case_dir = REPO_ROOT / "tests/e2e/cases/path-traversal-fastapi-name-only"
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
    assert summary["compiler_strategy"] == "path_traversal_file_read"
    assert summary["stack_scaffold_id"] == "python/fastapi"
    assert summary["fragment_id"] == "file_read_download_route_fastapi"
    bundle = next(bundle for bundle in summary["bundles"] if bundle["slug"] == "cwe-22")
    assert bundle["verify_pass"] is True
    assert bundle["stack_scaffold_id"] == "python/fastapi"
    assert bundle["fragment_id"] == "file_read_download_route_fastapi"


@pytest.mark.e2e
def test_open_redirect_name_only_independent_gate_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    case_dir = REPO_ROOT / "tests/e2e/cases/open-redirect-name-only-independent-gate"
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
    assert summary["verification_rule_source"] == "declared_rule"
    assert summary["verification_trust"] == "high"
    assert summary["verification_independence"] == "independent"
    assert summary["generalization_class"] == CURATED_LOWER_BOUND_GENERALIZATION_CLASS
    assert summary["counts_as_generalization"] is False
    assert summary["generation_summary"]["by_compose_mode"] == {"registry": 1}
    assert summary["generation_summary"]["by_stack_scaffold_id"] == {"python/flask": 1}
    assert summary["generation_summary"]["registry_compose_bundles"] == 1
    assert summary["generation_summary"]["template_origin_bundles"] == 0
    assert summary["verification_summary"]["by_independence"] == {"independent": 1}
    bundle = next(bundle for bundle in summary["bundles"] if bundle["slug"] == "name-open-redirect")
    assert bundle["promotion_eligible"] is True
    assert bundle["verification_rule_source"] == "declared_rule"
    assert bundle["verification_trust"] == "high"
    assert bundle["verification_independence"] == "independent"
    assert bundle["counts_as_generalization"] is False
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
    assert summary["generalization_class"] == CURATED_LOWER_BOUND_GENERALIZATION_CLASS
    assert summary["counts_as_generalization"] is False
    assert any(
        bundle["slug"] == "name-open-redirect"
        and bundle.get("verify_pass")
        and bundle.get("promotion_eligible")
        and bundle.get("compiler_supported") is True
        and bundle.get("counts_as_generalization") is False
        for bundle in summary["bundles"]
    )
    bundle = next(bundle for bundle in summary["bundles"] if bundle["slug"] == "name-open-redirect")
    assert "Using generator_manifest.json PoC contract as fallback rule" not in str(bundle.get("evidence") or "")


@pytest.mark.e2e
def test_open_redirect_paraphrase_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    case_dir = REPO_ROOT / "tests/e2e/cases/open-redirect-paraphrase-name-only"
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
    assert summary["name_resolution"]["source"] == "alias"
    assert summary["name_resolution"]["resolved_vuln_id"] == "NAME-OPEN-REDIRECT"
    assert summary["name_resolution"]["confidence"] == "high"
    assert summary["name_resolution"]["match_class"] == "catalog_alias"
    assert summary["generalization_class"] == CURATED_LOWER_BOUND_GENERALIZATION_CLASS
    assert summary["counts_as_generalization"] is False
    assert any(
        bundle["slug"] == "name-open-redirect"
        and bundle.get("verify_pass")
        and bundle.get("promotion_eligible")
        and bundle.get("compiler_supported") is True
        and bundle.get("counts_as_generalization") is False
        for bundle in summary["bundles"]
    )
    bundle = next(bundle for bundle in summary["bundles"] if bundle["slug"] == "name-open-redirect")
    assert "Using generator_manifest.json PoC contract as fallback rule" not in str(bundle.get("evidence") or "")


@pytest.mark.e2e
def test_open_redirect_reordered_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    case_dir = REPO_ROOT / "tests/e2e/cases/open-redirect-reordered-name-only"
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
    assert summary["name_resolution"]["source"] == "fragment_strategy_fallback"
    assert summary["name_resolution"]["resolved_vuln_id"] == "NAME-OPEN-REDIRECT"
    assert summary["name_resolution"]["confidence"] == "medium"
    assert summary["name_resolution"]["match_class"] == "token_match"
    assert summary["generalization_class"] == "real_free_form_non_generalizing"
    assert summary["counts_as_generalization"] is False
    assert summary["generalization_confidence"] == "medium"
    assert summary["generalization_basis"] == "token_match"
    assert any(
        bundle["slug"] == "name-open-redirect"
        and bundle.get("verify_pass")
        and bundle.get("promotion_eligible")
        and bundle.get("compiler_supported") is True
        and bundle.get("counts_as_generalization") is False
        for bundle in summary["bundles"]
    )
    assert summary["reviewer"]["blocking_bundles"] == []


@pytest.mark.e2e
def test_xxe_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    case_dir = REPO_ROOT / "tests/e2e/cases/xxe-name-only"
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
    assert summary["compiler_strategy"] == "xxe_xml_entity_resolve"
    assert summary["verification_rule_source"] == "declared_rule"
    assert summary["verification_trust"] == "high"
    assert summary["verification_independence"] == "independent"
    assert summary["generalization_class"] == CURATED_LOWER_BOUND_GENERALIZATION_CLASS
    assert summary["counts_as_generalization"] is False
    assert any(
        bundle["slug"] == "name-xxe"
        and bundle.get("verify_pass")
        and bundle.get("promotion_eligible")
        and bundle.get("compiler_supported") is True
        and bundle.get("verification_rule_source") == "declared_rule"
        and bundle.get("verification_trust") == "high"
        and bundle.get("verification_independence") == "independent"
        and bundle.get("counts_as_generalization") is False
        for bundle in summary["bundles"]
    )
    bundle = next(bundle for bundle in summary["bundles"] if bundle["slug"] == "name-xxe")
    assert "Using generator_manifest.json PoC contract as fallback rule" not in str(bundle.get("evidence") or "")


@pytest.mark.e2e
def test_multi_name_only_supported_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    case_dir = REPO_ROOT / "tests/e2e/cases/multi-name-only-supported"
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
    assert summary["pipeline_result"] == "success"
    assert summary["promotion_eligible"] is True
    assert summary["generation_origin"] == "compiler_generated"
    assert summary["dynamicness_verdict"] == "compiler-first"
    assert summary["verification_rule_source"] == "declared_rule"
    assert summary["verification_trust"] == "high"
    assert summary["verification_independence"] == "independent"
    assert summary["generalization_class"] == CURATED_LOWER_BOUND_GENERALIZATION_CLASS
    assert summary["counts_as_generalization"] is False
    assert summary["generalization_confidence"] == "high"
    assert summary["generalization_basis"] == "catalog_alias"
    assert len(summary["bundles"]) == 2
    assert summary["compiler_contract_summary"]["supported_bundles"] == 2
    assert summary["generalization_summary"]["positive_generalization_bundles"] == 0
    assert summary["name_resolution_summary"]["by_source"] == {"alias": 2}
    assert summary["name_resolution_summary"]["by_confidence"] == {"high": 2}

    bundle_index = {bundle["slug"]: bundle for bundle in summary["bundles"]}
    assert sorted(bundle_index) == ["name-open-redirect", "name-template-injection"]
    assert bundle_index["name-template-injection"]["compiler_strategy"] == "template_injection_render"
    assert bundle_index["name-open-redirect"]["compiler_strategy"] == "open_redirect_reflect"
    assert bundle_index["name-template-injection"]["name_resolution"]["confidence"] == "high"
    assert bundle_index["name-open-redirect"]["name_resolution"]["confidence"] == "high"
    assert bundle_index["name-template-injection"]["verification_rule_source"] == "declared_rule"
    assert bundle_index["name-open-redirect"]["verification_rule_source"] == "declared_rule"
    assert all(bundle.get("generation_origin") == "compiler_generated" for bundle in bundle_index.values())
    assert all(bundle.get("dynamicness_verdict") == "compiler-first" for bundle in bundle_index.values())
    assert all(bundle.get("counts_as_generalization") is False for bundle in bundle_index.values())
    assert summary["reviewer"]["blocking_bundles"] == []


@pytest.mark.e2e
def test_multi_name_mixed_partial_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    case_dir = REPO_ROOT / "tests/e2e/cases/multi-name-mixed-partial"
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
    assert summary["pipeline_result"] == "failure"
    assert summary["manifest_file"] == "failure_manifest.json"
    assert summary["generation_origin"] == "mixed"
    assert summary["dynamicness_verdict"] == "mixed"
    assert summary["provider_health_state"] == "not_probed"
    assert summary["failure"]["stage"] == "RESEARCH"
    assert summary["partial_progress_summary"]["partial_success"] is True
    assert summary["partial_progress_summary"]["successful_bundles"] == 1
    assert summary["partial_progress_summary"]["research_blocked_bundles"] == 1
    assert summary["name_only_outcome_summary"]["by_decision"] == {"abstain": 1, "intent_met": 1}
    assert summary["name_only_decision"] == "mixed"
    assert summary["name_only_next_required_step"] == "mixed"
    bundle_index = {bundle["slug"]: bundle for bundle in summary["bundles"]}
    assert bundle_index["name-custom-weird-vuln"]["generation_origin"] == "research_short_circuit"
    assert bundle_index["name-custom-weird-vuln"]["terminal_failure_class"] == "semantic_support_missing"
    assert bundle_index["name-custom-weird-vuln"]["name_only_outcome"]["decision"] == "abstain"
    assert bundle_index["name-open-redirect"]["run_passed"] is True
    assert bundle_index["name-open-redirect"]["verify_pass"] is True
    assert bundle_index["name-open-redirect"]["generation_origin"] == "compiler_generated"
    assert bundle_index["name-open-redirect"]["name_only_outcome"]["decision"] == "intent_met"


@pytest.mark.e2e
def test_ldap_injection_name_only_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    case_dir = REPO_ROOT / "tests/e2e/cases/ldap-injection-name-only"
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
    assert summary["manifest_file"] == "manifest.json"
    assert summary["compiler_supported"] is True
    assert summary["compiler_strategy"] == "ldap_injection_filter"
    assert summary["verification_rule_source"] == "declared_rule"
    assert summary["verification_trust"] == "high"
    assert summary["verification_independence"] == "independent"
    assert summary["generalization_class"] == CURATED_LOWER_BOUND_GENERALIZATION_CLASS
    assert summary["counts_as_generalization"] is False
    assert any(
        bundle["slug"] == "name-ldap-injection"
        and bundle.get("verify_pass") is True
        and bundle.get("compiler_supported") is True
        and bundle.get("compiler_strategy") == "ldap_injection_filter"
        and bundle.get("verification_rule_source") == "declared_rule"
        and bundle.get("verification_trust") == "high"
        and bundle.get("verification_independence") == "independent"
        and bundle.get("generalization_class") == CURATED_LOWER_BOUND_GENERALIZATION_CLASS
        and bundle.get("counts_as_generalization") is False
        for bundle in summary["bundles"]
    )


@pytest.mark.e2e
def test_foobar_name_only_negative_case(tmp_path: Path) -> None:
    reason = _skip_reason_for_case("foobar-name-only-negative")
    if reason:
        pytest.skip(reason)

    case_dir = REPO_ROOT / "tests/e2e/cases/foobar-name-only-negative"
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
    assert summary["provider_health_state"] == "not_probed"
    assert summary["failure"]["stage"] == "RESEARCH"
    assert summary["failure"]["terminal_failure_class"] == "semantic_support_missing"
    assert summary["name_only_decision"] == "abstain"
    assert summary["name_only_next_required_step"] == "research"
    assert summary["name_only_outcome"]["decision"] == "abstain"
    assert summary["name_only_outcome"]["abstain_reason"] == "semantic_support_missing"
    assert summary["name_resolution"]["input"] == "Foobar"
    assert summary["name_resolution"]["resolved_vuln_id"] == "NAME-FOOBAR"
    assert summary["name_resolution"]["source"] == "synthetic_name"
    assert summary["name_resolution"]["confidence"] == "low"
    assert summary["name_resolution"]["match_class"] == "synthetic_name"
    assert summary["generalization_class"] == "unsupported_free_form_negative"
    assert summary["counts_as_generalization"] is False
    assert any(
        bundle["slug"] == "name-foobar"
        and bundle.get("compiler_supported") is False
        and bundle.get("generation_origin") == "research_short_circuit"
        and (bundle.get("name_only_outcome") or {}).get("decision") == "abstain"
        and bundle.get("terminal_failure_class") == "semantic_support_missing"
        and bundle.get("generalization_class") == "unsupported_free_form_negative"
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
    assert report["matrix_axes"]["family_known"] == "known"
    assert isinstance(report["cache_reuse_observed"], bool)
    assert isinstance(report["cache_reuse_consistent"], bool)
    assert isinstance(report["executed_query_reduction_observed"], bool)
    assert Path(report["matrix_report_path"]).exists()
    assert Path(report["support_candidate_path"]).exists()
    first_attempt = report["attempts"][0]
    assert first_attempt["case_name"] == "cwe-89-basic"
    assert first_attempt["matrix_axes"]["topology_class"] == "single_service"
    assert "search_cache_hit_count" in first_attempt
    assert "search_executed_query_count" in first_attempt


@pytest.mark.e2e
def test_template_injection_name_only_repeatability_gate(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)
    if _skip_repeatability_pytest():
        pytest.skip("Repeatability gate is executed via ops/ci/run_repeatability_gate.sh in this run")
    if not _repeat_gate_enabled():
        pytest.skip("Set VULD_RUN_E2E_REPEAT=1 to enable repeatability gate")

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
    assert report["matrix_axes"]["phrase_shape"] == "canonical"
    assert isinstance(report["cache_reuse_observed"], bool)
    assert isinstance(report["cache_reuse_consistent"], bool)
    assert isinstance(report["executed_query_reduction_observed"], bool)
    assert Path(report["matrix_report_path"]).exists()
    assert Path(report["support_candidate_path"]).exists()
    first_attempt = report["attempts"][0]
    assert first_attempt["case_name"] == "template-injection-name-only"
    assert first_attempt["matrix_axes"]["oracle_difficulty"] == "payload_replay"
    assert "search_cache_hit_count" in first_attempt
    assert "search_early_stop_triggered" in first_attempt


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
            pytest.fail("A Tavily API key is required for the current canonical live unknown-CWE gate")
        pytest.skip("Tavily API key is not configured for the current canonical live unknown-CWE gate")

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
    assert summary["pipeline_result"] == "failure"
    assert summary["manifest_file"] == "failure_manifest.json"
    assert summary["failure"]["stage"] == "RESEARCH"
    assert summary["failure"]["terminal_failure_class"] == "evidence_low_relevance"
    assert summary["promotion_eligible"] is False
    assert summary["generalization_class"] == "synthetic_regression"
    assert summary["counts_as_generalization"] is False
    assert summary["generalization_summary"]["positive_generalization_bundles"] == 0
    assert any(
        bundle["slug"] == "cwe-9999"
        and bundle.get("verify_pass") is None
        and bundle.get("run_passed") is None
        and bundle.get("promotion_eligible") is False
        and bundle.get("generalization_class") == "synthetic_regression"
        and bundle.get("counts_as_generalization") is False
        and bundle.get("generation_origin") == "research_short_circuit"
        and bundle.get("terminal_failure_class") == "evidence_low_relevance"
        and "low relevance score" in str(bundle.get("failure_reason") or "")
        for bundle in summary["bundles"]
    )
    assert summary["reviewer"]["blocking_bundles"] == []


@pytest.mark.e2e
def test_unknown_cwe_live_low_trust_fail_closed_case(tmp_path: Path) -> None:
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)
    if not _tavily_key_available():
        if _live_gate_required():
            pytest.fail("A Tavily API key is required for the current canonical live unknown-CWE gate")
        pytest.skip("Tavily API key is not configured for the current canonical live unknown-CWE gate")

    case_dir = REPO_ROOT / "tests/e2e/cases/cwe-unknown-low-trust-fail-closed"
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
    assert summary["pipeline_result"] == "failure"
    assert summary["manifest_file"] == "failure_manifest.json"
    assert summary["failure"]["stage"] == "RESEARCH"
    assert summary["failure"]["terminal_failure_class"] == "evidence_low_relevance"
    assert summary["promotion_eligible"] is False
    assert any(
        bundle["slug"] == "cwe-9999"
        and bundle.get("verify_pass") is None
        and bundle.get("run_passed") is None
        and bundle.get("generation_origin") == "research_short_circuit"
        and bundle.get("terminal_failure_class") == "evidence_low_relevance"
        and "low relevance score" in str(bundle.get("failure_reason") or "")
        for bundle in summary["bundles"]
    )
