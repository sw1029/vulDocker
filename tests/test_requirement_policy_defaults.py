from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.schema import normalize_requirement
from common.contracts import can_resolve_without_remote_research


def _base_requirement(vuln_id: str) -> dict:
    return {
        "requirement_id": "REQ-TEST-0001",
        "vuln_id": vuln_id,
        "language": "python",
        "framework": "flask",
        "seed": 1,
        "retriever_commit": "stub",
        "corpus_snapshot": "mvp-sample",
        "pattern_id": "test",
        "deps_digest": "sha256:test",
        "base_image_digest": "sha256:test",
        "runtime": {"base_image": "python:3.11-slim", "package_manager": "pip"},
    }


def test_unknown_cwe_defaults_to_remote_required_research_evidence() -> None:
    requirement = _base_requirement("CWE-9999")
    normalized = normalize_requirement(requirement)
    policy = normalized.requirement.get("policy") or {}
    guard = policy.get("guard") or {}
    researcher = normalized.requirement.get("researcher") or {}
    assert policy.get("require_researcher_evidence") is True
    assert policy.get("allow_runtime_rule_override_static") is False
    assert guard.get("enforcement") == "block_both"
    assert guard.get("failure_policy") == "closed_unknown"
    assert guard.get("dynamic_scope") == "assertions_semantics"
    assert guard.get("unsupported_op_policy") == "normalize_retry"
    assert guard.get("refresh_researcher_on_guard_dsl_error") is True
    assert guard.get("semantic_refresh_threshold") == 2
    assert guard.get("hint_payload_enabled") is True
    assert guard.get("failure_fingerprint_window") == 3
    assert (guard.get("call_budget") or {}).get("mode") == "bundle_once"
    assert (guard.get("autofix") or {}).get("level") == "code"
    assert researcher.get("search_policy") == "remote_required"
    assert researcher.get("generate_candidate_templates") is False


def test_known_cwe_defaults_to_remote_prefer_without_forced_evidence() -> None:
    requirement = _base_requirement("CWE-89")
    normalized = normalize_requirement(requirement)
    policy = normalized.requirement.get("policy") or {}
    guard = policy.get("guard") or {}
    researcher = normalized.requirement.get("researcher") or {}
    assert policy.get("require_researcher_evidence") is False
    assert policy.get("allow_runtime_rule_override_static") is False
    assert guard.get("enforcement") == "block_both"
    assert guard.get("failure_policy") == "closed_unknown"
    assert guard.get("unsupported_op_policy") == "normalize_retry"
    assert guard.get("refresh_researcher_on_guard_dsl_error") is True
    assert guard.get("semantic_refresh_threshold") == 2
    assert guard.get("hint_payload_enabled") is True
    assert guard.get("failure_fingerprint_window") == 3
    assert researcher.get("search_policy") == "remote_prefer"


def test_researcher_search_filters_are_normalized() -> None:
    requirement = _base_requirement("CWE-9999")
    requirement["researcher"] = {
        "search_policy": "remote_required",
        "search_filters": {
            "include_domains": [" mitre.org ", "owasp.org", "mitre.org"],
            "exclude_domains": "example.com",
            "time_range": " 30d ",
            "country": " us ",
            "search_lang": " en ",
            "unknown_key": "ignored",
        },
    }

    normalized = normalize_requirement(requirement)
    researcher = normalized.requirement.get("researcher") or {}
    filters = researcher.get("search_filters") or {}

    assert filters["include_domains"] == ["mitre.org", "owasp.org"]
    assert filters["exclude_domains"] == ["example.com"]
    assert filters["time_range"] == "30d"
    assert filters["country"] == "us"
    assert filters["search_lang"] == "en"
    assert "unknown_key" not in filters
    assert any("unknown keys" in warning for warning in normalized.warnings)


def test_vuln_name_only_requirement_is_mapped_and_defaulted() -> None:
    normalized = normalize_requirement({"vuln_name": "SQL injection"})
    requirement = normalized.requirement
    runtime = requirement.get("runtime") or {}
    dep_guard = requirement.get("dep_guard") or {}

    assert requirement["vuln_id"] == "CWE-89"
    assert requirement["requirement_id"].startswith("AUTO-CWE-89")
    assert requirement["language"] == "python"
    assert requirement["framework"] == "flask"
    assert requirement["pattern_id"] == "sqli-string-concat"
    assert requirement["generator_mode"] == "synthesis"
    assert runtime["base_image"] == "python:3.11-slim"
    assert runtime["package_manager"] == "pip"
    assert runtime["db"] == "sqlite"
    assert runtime["allow_external_db"] is False
    assert dep_guard["llm_assist"] is True
    assert dep_guard["auto_patch"] is True
    assert requirement["user_deps"] == ["requests==2.31.0"]
    defaults_meta = requirement.get("_normalization_defaults") or {}
    assert defaults_meta.get("profile") == "SQL Injection"
    assert "pattern_id" in (defaults_meta.get("applied_fields") or [])


def test_vuln_name_ssrf_maps_to_cwe918_defaults() -> None:
    normalized = normalize_requirement({"vuln_name": "SSRF"})
    requirement = normalized.requirement

    assert requirement["vuln_id"] == "CWE-918"
    assert requirement["pattern_id"] == "ssrf-url-fetch"
    assert requirement["vuln_label"] == "Server-Side Request Forgery"
    assert (requirement.get("policy") or {}).get("guard", {}).get("low_confidence_unknown_policy") == "warn"


def test_freeform_vuln_name_gets_synthetic_identifier_and_generic_defaults() -> None:
    normalized = normalize_requirement({"vuln_name": "Template Injection"})
    requirement = normalized.requirement

    assert requirement["vuln_id"] == "NAME-TEMPLATE-INJECTION"
    assert requirement["pattern_id"] == "template-injection"
    assert requirement["vuln_label"] == "Template Injection"
    assert requirement["language"] == "python"
    assert requirement["framework"] == "flask"
    assert (requirement.get("policy") or {}).get("require_researcher_evidence") is False
    assert (requirement.get("researcher") or {}).get("search_policy") == "remote_prefer"


def test_template_injection_alias_is_canonicalized_to_supported_name_family() -> None:
    normalized = normalize_requirement({"vuln_name": "Server Side Template Injection"})
    requirement = normalized.requirement

    assert requirement["vuln_id"] == "NAME-TEMPLATE-INJECTION"
    assert requirement["pattern_id"] == "template-injection"
    assert (requirement.get("policy") or {}).get("require_researcher_evidence") is False
    assert (requirement.get("researcher") or {}).get("search_policy") == "remote_prefer"


def test_open_redirect_alias_is_canonicalized_to_supported_name_family() -> None:
    normalized = normalize_requirement({"vuln_name": "Unvalidated Redirect"})
    requirement = normalized.requirement

    assert requirement["vuln_id"] == "NAME-OPEN-REDIRECT"
    assert requirement["pattern_id"] == "open-redirect"
    assert (requirement.get("policy") or {}).get("require_researcher_evidence") is False
    assert (requirement.get("researcher") or {}).get("search_policy") == "remote_prefer"


def test_explicit_name_alias_vuln_id_is_treated_as_supported_family() -> None:
    normalized = normalize_requirement({"vuln_id": "NAME-SERVER-SIDE-TEMPLATE-INJECTION"})
    requirement = normalized.requirement

    assert requirement["vuln_id"] == "NAME-TEMPLATE-INJECTION"
    assert can_resolve_without_remote_research(requirement["vuln_id"]) is True
    assert (requirement.get("policy") or {}).get("require_researcher_evidence") is False
    assert (requirement.get("researcher") or {}).get("search_policy") == "remote_prefer"


def test_compiler_supported_known_family_without_static_rule_defaults_to_remote_prefer() -> None:
    normalized = normalize_requirement({"vuln_name": "Path Traversal"})
    requirement = normalized.requirement

    assert requirement["vuln_id"] == "CWE-22"
    assert (requirement.get("policy") or {}).get("require_researcher_evidence") is False
    assert (requirement.get("researcher") or {}).get("search_policy") == "remote_prefer"


def test_vuln_name_heuristics_match_non_exact_family_phrase() -> None:
    normalized = normalize_requirement({"vuln_name": "Reflected XSS vulnerability"})
    requirement = normalized.requirement

    assert requirement["vuln_id"] == "CWE-79"
    assert requirement["pattern_id"] == "xss-reflected"
