from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.schema import normalize_requirement
from common.contracts import (
    can_resolve_without_remote_research,
    can_resolve_without_remote_research_for_requirement,
)


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
    verifier = policy.get("verifier") or {}
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
    assert verifier.get("low_trust_unknown_policy") == "warn"
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
    assert (requirement.get("name_resolution") or {}).get("source") == "alias"
    assert (requirement.get("policy") or {}).get("require_researcher_evidence") is False
    assert (requirement.get("researcher") or {}).get("search_policy") == "remote_prefer"


def test_template_injection_with_compiler_disabled_requires_research_evidence() -> None:
    normalized = normalize_requirement({"vuln_name": "Template Injection", "compiler": {"enabled": False}})
    requirement = normalized.requirement

    assert requirement["vuln_id"] == "NAME-TEMPLATE-INJECTION"
    assert (requirement.get("policy") or {}).get("require_researcher_evidence") is True
    assert (requirement.get("researcher") or {}).get("search_policy") == "remote_required"
    assert can_resolve_without_remote_research(requirement["vuln_id"]) is True
    assert can_resolve_without_remote_research_for_requirement(requirement["vuln_id"], requirement) is False


def test_open_redirect_alias_is_canonicalized_to_supported_name_family() -> None:
    normalized = normalize_requirement({"vuln_name": "Unvalidated Redirect"})
    requirement = normalized.requirement

    assert requirement["vuln_id"] == "NAME-OPEN-REDIRECT"
    assert requirement["pattern_id"] == "open-redirect"
    assert (requirement.get("name_resolution") or {}).get("source") == "alias"
    assert (requirement.get("policy") or {}).get("require_researcher_evidence") is False
    assert (requirement.get("researcher") or {}).get("search_policy") == "remote_prefer"


def test_open_redirect_with_legacy_disable_compiler_requires_research_evidence() -> None:
    normalized = normalize_requirement({"vuln_name": "Open Redirect", "disable_compiler": True})
    requirement = normalized.requirement

    assert requirement["vuln_id"] == "NAME-OPEN-REDIRECT"
    assert (requirement.get("policy") or {}).get("require_researcher_evidence") is True
    assert (requirement.get("researcher") or {}).get("search_policy") == "remote_required"
    assert can_resolve_without_remote_research_for_requirement(requirement["vuln_id"], requirement) is False


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


def test_template_rendering_paraphrase_is_canonicalized_to_supported_name_family() -> None:
    normalized = normalize_requirement({"vuln_name": "Template rendering vulnerability"})
    requirement = normalized.requirement

    assert requirement["vuln_id"] == "NAME-TEMPLATE-INJECTION"
    assert requirement["pattern_id"] == "template-injection"
    assert (requirement.get("name_resolution") or {}).get("source") == "alias"


def test_external_redirect_paraphrase_is_canonicalized_to_supported_name_family() -> None:
    normalized = normalize_requirement({"vuln_name": "External redirect vulnerability"})
    requirement = normalized.requirement

    assert requirement["vuln_id"] == "NAME-OPEN-REDIRECT"
    assert requirement["pattern_id"] == "open-redirect"
    assert (requirement.get("name_resolution") or {}).get("source") == "alias"


def test_vuln_name_fragment_strategy_fallback_handles_reordered_shell_phrase() -> None:
    normalized = normalize_requirement({"vuln_name": "Injection in shell command"})
    requirement = normalized.requirement

    assert requirement["vuln_id"] == "CWE-78"
    assert requirement["pattern_id"] == "command-injection"
    assert (requirement.get("name_resolution") or {}).get("source") == "fragment_strategy_fallback"


def test_vuln_name_fragment_strategy_fallback_handles_reordered_template_phrase() -> None:
    normalized = normalize_requirement({"vuln_name": "Injection in Jinja template"})
    requirement = normalized.requirement

    assert requirement["vuln_id"] == "NAME-TEMPLATE-INJECTION"
    assert requirement["pattern_id"] == "template-injection"
    assert (requirement.get("name_resolution") or {}).get("source") == "fragment_strategy_fallback"


def test_vuln_name_fragment_strategy_fallback_handles_reordered_redirect_phrase() -> None:
    normalized = normalize_requirement({"vuln_name": "Redirect open vulnerability"})
    requirement = normalized.requirement

    assert requirement["vuln_id"] == "NAME-OPEN-REDIRECT"
    assert requirement["pattern_id"] == "open-redirect"
    assert (requirement.get("name_resolution") or {}).get("source") == "fragment_strategy_fallback"


def test_multi_vuln_name_only_supported_families_are_normalized_when_opted_in() -> None:
    normalized = normalize_requirement(
        {
            "vuln_ids": ["Template Injection", "Open Redirect"],
            "multi_vuln": True,
        },
        multi_vuln_opt_in=True,
    )
    requirement = normalized.requirement

    assert normalized.multi_vuln is True
    assert normalized.requested_vuln_ids == ["NAME-TEMPLATE-INJECTION", "NAME-OPEN-REDIRECT"]
    assert normalized.effective_vuln_ids == ["NAME-TEMPLATE-INJECTION", "NAME-OPEN-REDIRECT"]
    assert requirement["vuln_id"] == "NAME-TEMPLATE-INJECTION"
    assert requirement["vuln_ids"] == ["NAME-TEMPLATE-INJECTION", "NAME-OPEN-REDIRECT"]
    assert (requirement.get("policy") or {}).get("require_researcher_evidence") is False
    assert (requirement.get("researcher") or {}).get("search_policy") == "remote_prefer"
    assert [bundle["slug"] for bundle in normalized.bundles] == [
        "name-template-injection",
        "name-open-redirect",
    ]
    assert all(can_resolve_without_remote_research(vuln_id) for vuln_id in normalized.effective_vuln_ids)


def test_multi_vuln_mixed_freeform_entries_preserve_unknown_synthetic_bundle() -> None:
    normalized = normalize_requirement(
        {
            "vuln_ids": ["Custom Weird Vuln", "Open Redirect"],
            "multi_vuln": True,
        },
        multi_vuln_opt_in=True,
    )
    requirement = normalized.requirement

    assert normalized.multi_vuln is True
    assert normalized.requested_vuln_ids == ["NAME-CUSTOM-WEIRD-VULN", "NAME-OPEN-REDIRECT"]
    assert normalized.effective_vuln_ids == ["NAME-CUSTOM-WEIRD-VULN", "NAME-OPEN-REDIRECT"]
    assert requirement["vuln_id"] == "NAME-CUSTOM-WEIRD-VULN"
    assert requirement["vuln_ids"] == ["NAME-CUSTOM-WEIRD-VULN", "NAME-OPEN-REDIRECT"]
    assert (requirement.get("policy") or {}).get("require_researcher_evidence") is True
    assert (requirement.get("researcher") or {}).get("search_policy") == "remote_required"
    assert [bundle["slug"] for bundle in normalized.bundles] == [
        "name-custom-weird-vuln",
        "name-open-redirect",
    ]
    resolutions = requirement.get("vuln_id_resolutions") or []
    assert resolutions[0]["resolved_vuln_id"] == "NAME-CUSTOM-WEIRD-VULN"
    assert resolutions[0]["source"] == "synthetic_name"
    assert resolutions[1]["resolved_vuln_id"] == "NAME-OPEN-REDIRECT"


def test_explicit_plaintext_vuln_id_is_promoted_to_synthetic_name() -> None:
    normalized = normalize_requirement({"vuln_id": "Custom Weird Vuln"})
    requirement = normalized.requirement

    assert requirement["vuln_id"] == "NAME-CUSTOM-WEIRD-VULN"
    assert (requirement.get("name_resolution") or {}).get("source") == "synthetic_name"
    assert (requirement.get("policy") or {}).get("require_researcher_evidence") is True
    assert (requirement.get("researcher") or {}).get("search_policy") == "remote_required"


def test_single_token_plaintext_vuln_id_is_promoted_to_synthetic_name() -> None:
    normalized = normalize_requirement({"vuln_id": "Foobar"})
    requirement = normalized.requirement

    assert requirement["vuln_id"] == "NAME-FOOBAR"
    assert (requirement.get("name_resolution") or {}).get("resolved_vuln_id") == "NAME-FOOBAR"
    assert (requirement.get("name_resolution") or {}).get("source") == "synthetic_name"
    assert (requirement.get("policy") or {}).get("require_researcher_evidence") is True
    assert (requirement.get("researcher") or {}).get("search_policy") == "remote_required"


def test_single_token_vuln_name_is_promoted_to_synthetic_name() -> None:
    normalized = normalize_requirement({"vuln_name": "Foobar"})
    requirement = normalized.requirement

    assert requirement["vuln_id"] == "NAME-FOOBAR"
    assert requirement["vuln_ids"] == ["NAME-FOOBAR"]
    assert (requirement.get("name_resolution") or {}).get("resolved_vuln_id") == "NAME-FOOBAR"
    assert (requirement.get("name_resolution") or {}).get("source") == "synthetic_name"
    assert (requirement.get("policy") or {}).get("require_researcher_evidence") is True
    assert (requirement.get("researcher") or {}).get("search_policy") == "remote_required"


def test_single_token_vuln_ids_entry_is_promoted_to_synthetic_name() -> None:
    normalized = normalize_requirement({"vuln_ids": ["Foobar"]})
    requirement = normalized.requirement

    assert normalized.requested_vuln_ids == ["NAME-FOOBAR"]
    assert requirement["vuln_id"] == "NAME-FOOBAR"
    assert requirement["vuln_ids"] == ["NAME-FOOBAR"]
    assert (requirement.get("name_resolution") or {}).get("resolved_vuln_id") == "NAME-FOOBAR"
    assert (requirement.get("name_resolution") or {}).get("source") == "synthetic_name"
    assert (requirement.get("policy") or {}).get("require_researcher_evidence") is True
    assert (requirement.get("researcher") or {}).get("search_policy") == "remote_required"


def test_explicit_cwe_identifier_alias_is_canonicalized() -> None:
    normalized = normalize_requirement({"vuln_id": "CWE89"})
    requirement = normalized.requirement

    assert requirement["vuln_id"] == "CWE-89"
    assert requirement["pattern_id"] == "sqli-string-concat"
    assert (requirement.get("policy") or {}).get("require_researcher_evidence") is False


def test_xxe_name_only_is_canonicalized_to_compiler_supported_family_defaults() -> None:
    normalized = normalize_requirement({"vuln_name": "XML External Entity"})
    requirement = normalized.requirement

    assert requirement["vuln_id"] == "NAME-XXE"
    assert requirement["pattern_id"] == "xxe"
    assert requirement["vuln_label"] == "XXE"
    assert (requirement.get("policy") or {}).get("require_researcher_evidence") is False
    assert (requirement.get("researcher") or {}).get("search_policy") == "remote_prefer"


def test_ambiguous_token_match_phrase_does_not_canonicalize_to_supported_family() -> None:
    normalized = normalize_requirement({"vuln_name": "unsafe template deserialization"})
    requirement = normalized.requirement

    assert requirement["vuln_id"] == "NAME-UNSAFE-TEMPLATE-DESERIALIZATION"
    assert (requirement.get("name_resolution") or {}).get("source") == "synthetic_name"
    assert requirement["pattern_id"] == "generic-web-vuln"
    assert (requirement.get("policy") or {}).get("require_researcher_evidence") is True
    assert (requirement.get("researcher") or {}).get("search_policy") == "remote_required"


def test_invalid_low_trust_unknown_policy_falls_back_to_warn() -> None:
    requirement = _base_requirement("CWE-9999")
    requirement["policy"] = {"verifier": {"low_trust_unknown_policy": "strict"}}

    normalized = normalize_requirement(requirement)

    assert (normalized.requirement.get("policy") or {}).get("verifier", {}).get("low_trust_unknown_policy") == "warn"
    assert any("low_trust_unknown_policy" in warning for warning in normalized.warnings)
