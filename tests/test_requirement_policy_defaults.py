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
from common.run_matrix import VulnBundle, bundle_requirement


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
    assert verifier.get("min_promotion_independence") == "compiler_coupled"
    assert verifier.get("min_name_resolution_confidence") == "low"
    assert researcher.get("search_policy") == "remote_required"
    assert researcher.get("generate_candidate_templates") is False
    assert researcher.get("shadow_mode") is False
    assert normalized.requirement["pattern_id"] == "generic-web-vuln"
    assert policy.get("allow_unknown_pattern_seed") is False
    assert any("generic-web-vuln" in warning for warning in normalized.warnings)


def test_unknown_cwe_can_keep_pattern_seed_when_opted_in() -> None:
    requirement = _base_requirement("CWE-9999")
    requirement["policy"] = {"allow_unknown_pattern_seed": True}

    normalized = normalize_requirement(requirement)

    assert normalized.requirement["pattern_id"] == "test"
    assert (normalized.requirement.get("policy") or {}).get("allow_unknown_pattern_seed") is True


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
    assert researcher.get("shadow_mode") is False
    assert policy.get("open_world_strict") is False
    assert policy.get("dynamic_eval") is False
    assert policy.get("dynamic_eval_allow_lower_bound_fallback") is False


def test_open_world_strict_policy_is_normalized_to_bool() -> None:
    requirement = _base_requirement("CWE-89")
    requirement["policy"] = {"open_world_strict": "yes"}

    normalized = normalize_requirement(requirement)

    assert (normalized.requirement.get("policy") or {}).get("open_world_strict") is True


def test_dynamic_eval_policies_are_normalized_to_bool() -> None:
    requirement = _base_requirement("NAME-OPEN-REDIRECT")
    requirement["policy"] = {
        "dynamic_eval": "yes",
        "dynamic_eval_allow_lower_bound_fallback": "1",
    }

    normalized = normalize_requirement(requirement)
    policy = normalized.requirement.get("policy") or {}

    assert policy.get("dynamic_eval") is True
    assert policy.get("dynamic_eval_allow_lower_bound_fallback") is True


def test_name_only_mode_defaults_to_compatibility() -> None:
    requirement = _base_requirement("NAME-OPEN-REDIRECT")

    normalized = normalize_requirement(requirement)

    policy = normalized.requirement.get("policy") or {}

    assert policy.get("name_only_mode") == "compatibility"
    assert (policy.get("name_only_contract") or {}).get("effective_mode") == "compatibility"
    assert (policy.get("name_only_contract") or {}).get("allow_curated_lower_bound_closure") is True


def test_name_only_mode_is_normalized_and_preserved() -> None:
    requirement = _base_requirement("NAME-OPEN-REDIRECT")
    requirement["policy"] = {"name_only_mode": "STRICT_DYNAMIC"}

    normalized = normalize_requirement(requirement)
    policy = normalized.requirement.get("policy") or {}

    assert policy.get("name_only_mode") == "strict_dynamic"
    assert policy.get("require_researcher_evidence") is True
    assert (normalized.requirement.get("researcher") or {}).get("search_policy") == "remote_required"
    assert (policy.get("name_only_contract") or {}).get("require_strict_open_world") is True
    assert (policy.get("name_only_contract") or {}).get("require_live_llm") is True
    assert (policy.get("name_only_contract") or {}).get("allow_stub_llm") is False


def test_name_only_dynamic_mode_defers_hard_stack_defaults_into_stack_hypotheses() -> None:
    normalized = normalize_requirement(
        {
            "vuln_name": "Open Redirect",
            "policy": {"name_only_mode": "dynamic"},
        }
    )
    requirement = normalized.requirement
    runtime = requirement.get("runtime") or {}
    stack_hypotheses = requirement.get("stack_hypotheses") or []

    assert requirement["vuln_id"] == "NAME-OPEN-REDIRECT"
    assert "language" not in requirement
    assert "framework" not in requirement
    assert "base_image_digest" not in requirement
    assert "base_image" not in runtime
    assert "package_manager" not in runtime
    assert runtime["allow_external_db"] is False
    assert len(stack_hypotheses) >= 2
    assert stack_hypotheses[0]["stack_id"] == "python/flask"
    assert stack_hypotheses[0]["source"] == "profile_prior"
    assert any(item["stack_id"] == "python/fastapi" for item in stack_hypotheses)
    assert any("Deferred hard stack defaults" in warning for warning in normalized.warnings)


def test_name_only_dynamic_eval_defers_hard_stack_defaults_into_stack_hypotheses() -> None:
    normalized = normalize_requirement(
        {
            "vuln_name": "Open Redirect",
            "policy": {"dynamic_eval": True},
        }
    )
    requirement = normalized.requirement
    runtime = requirement.get("runtime") or {}
    stack_hypotheses = requirement.get("stack_hypotheses") or []

    assert requirement["vuln_id"] == "NAME-OPEN-REDIRECT"
    assert "language" not in requirement
    assert "framework" not in requirement
    assert "base_image_digest" not in requirement
    assert "base_image" not in runtime
    assert "package_manager" not in runtime
    assert runtime["allow_external_db"] is False
    assert len(stack_hypotheses) >= 2
    assert stack_hypotheses[0]["stack_id"] == "python/flask"
    assert any(item["stack_id"] == "python/fastapi" for item in stack_hypotheses)
    assert any("Deferred hard stack defaults" in warning for warning in normalized.warnings)
    assert ((requirement.get("policy") or {}).get("name_only_contract") or {}).get("effective_mode") == "dynamic_eval"


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


def test_researcher_shadow_mode_is_normalized_to_bool() -> None:
    requirement = _base_requirement("CWE-89")
    requirement["researcher"] = {"shadow_mode": "yes"}

    normalized = normalize_requirement(requirement)

    assert (normalized.requirement.get("researcher") or {}).get("shadow_mode") is True


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
    assert (requirement.get("name_resolution") or {}).get("confidence") == "high"
    assert (requirement.get("name_resolution") or {}).get("match_class") == "catalog_alias"
    assert (requirement.get("policy") or {}).get("require_researcher_evidence") is False
    assert (requirement.get("researcher") or {}).get("search_policy") == "remote_prefer"
    request_identity = requirement.get("request_identity") or {}
    assert request_identity.get("request_label") == "Server Side Template Injection"
    assert request_identity.get("input_mode") == "free_form_name"
    assert request_identity.get("catalog_backed_resolution") is True
    assert request_identity.get("synthetic_resolution") is False


def test_path_traversal_with_compiler_disabled_keeps_static_rule_lower_bound() -> None:
    normalized = normalize_requirement({"vuln_name": "Path Traversal", "compiler": {"enabled": False}})
    requirement = normalized.requirement

    assert requirement["vuln_id"] == "CWE-22"
    assert (requirement.get("policy") or {}).get("require_researcher_evidence") is False
    assert (requirement.get("researcher") or {}).get("search_policy") == "remote_prefer"
    assert can_resolve_without_remote_research(requirement["vuln_id"]) is True
    assert can_resolve_without_remote_research_for_requirement(requirement["vuln_id"], requirement) is True


def test_open_redirect_alias_is_canonicalized_to_supported_name_family() -> None:
    normalized = normalize_requirement({"vuln_name": "Unvalidated Redirect"})
    requirement = normalized.requirement

    assert requirement["vuln_id"] == "NAME-OPEN-REDIRECT"
    assert requirement["pattern_id"] == "open-redirect"
    assert (requirement.get("name_resolution") or {}).get("source") == "alias"
    assert (requirement.get("name_resolution") or {}).get("confidence") == "high"
    assert (requirement.get("name_resolution") or {}).get("match_class") == "catalog_alias"
    assert (requirement.get("policy") or {}).get("require_researcher_evidence") is False
    assert (requirement.get("researcher") or {}).get("search_policy") == "remote_prefer"


def test_path_traversal_with_legacy_disable_compiler_keeps_static_rule_lower_bound() -> None:
    normalized = normalize_requirement({"vuln_name": "Path Traversal", "disable_compiler": True})
    requirement = normalized.requirement

    assert requirement["vuln_id"] == "CWE-22"
    assert (requirement.get("policy") or {}).get("require_researcher_evidence") is False
    assert (requirement.get("researcher") or {}).get("search_policy") == "remote_prefer"
    assert can_resolve_without_remote_research_for_requirement(requirement["vuln_id"], requirement) is True


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
    assert (requirement.get("name_resolution") or {}).get("confidence") == "high"


def test_external_redirect_paraphrase_is_canonicalized_to_supported_name_family() -> None:
    normalized = normalize_requirement({"vuln_name": "External redirect vulnerability"})
    requirement = normalized.requirement

    assert requirement["vuln_id"] == "NAME-OPEN-REDIRECT"
    assert requirement["pattern_id"] == "open-redirect"
    assert (requirement.get("name_resolution") or {}).get("source") == "alias"
    assert (requirement.get("name_resolution") or {}).get("confidence") == "high"


def test_vuln_name_fragment_strategy_fallback_handles_reordered_shell_phrase() -> None:
    normalized = normalize_requirement({"vuln_name": "Injection in shell command"})
    requirement = normalized.requirement

    assert requirement["vuln_id"] == "CWE-78"
    assert requirement["pattern_id"] == "command-injection"
    assert (requirement.get("name_resolution") or {}).get("source") == "fragment_strategy_fallback"
    assert (requirement.get("name_resolution") or {}).get("confidence") == "medium"
    assert (requirement.get("name_resolution") or {}).get("match_class") == "token_match"


def test_vuln_name_fragment_strategy_fallback_handles_reordered_template_phrase() -> None:
    normalized = normalize_requirement({"vuln_name": "Injection in Jinja template"})
    requirement = normalized.requirement

    assert requirement["vuln_id"] == "NAME-TEMPLATE-INJECTION"
    assert requirement["pattern_id"] == "template-injection"
    assert (requirement.get("name_resolution") or {}).get("source") == "fragment_strategy_fallback"
    assert (requirement.get("name_resolution") or {}).get("confidence") == "medium"
    assert (requirement.get("name_resolution") or {}).get("match_class") == "token_match"


def test_vuln_name_fragment_strategy_fallback_handles_reordered_redirect_phrase() -> None:
    normalized = normalize_requirement({"vuln_name": "Redirect open vulnerability"})
    requirement = normalized.requirement

    assert requirement["vuln_id"] == "NAME-OPEN-REDIRECT"
    assert requirement["pattern_id"] == "open-redirect"
    assert (requirement.get("name_resolution") or {}).get("source") == "fragment_strategy_fallback"
    assert (requirement.get("name_resolution") or {}).get("confidence") == "medium"
    assert (requirement.get("name_resolution") or {}).get("match_class") == "token_match"


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
    assert resolutions[0]["confidence"] == "low"
    assert resolutions[1]["resolved_vuln_id"] == "NAME-OPEN-REDIRECT"


def test_policy_disables_name_family_fallback_by_default() -> None:
    normalized = normalize_requirement({"vuln_id": "Open Redirect"})

    assert (normalized.requirement.get("policy") or {}).get("allow_name_family_fallback") is False


def test_policy_normalizes_name_family_fallback_to_bool() -> None:
    normalized = normalize_requirement(
        {
            "vuln_id": "Open Redirect",
            "policy": {"allow_name_family_fallback": "true"},
        }
    )

    assert (normalized.requirement.get("policy") or {}).get("allow_name_family_fallback") is True


def test_bundle_requirement_uses_bundle_specific_name_resolution_for_multi_vuln_inputs() -> None:
    normalized = normalize_requirement(
        {
            "vuln_ids": ["Injection in Jinja template", "Open Redirect"],
            "multi_vuln": True,
        },
        multi_vuln_opt_in=True,
    )
    requirement = normalized.requirement

    template_req = bundle_requirement(
        requirement,
        VulnBundle(
            vuln_id="NAME-TEMPLATE-INJECTION",
            slug="name-template-injection",
            workspace_subdir="app/name-template-injection",
        ),
    )
    redirect_req = bundle_requirement(
        requirement,
        VulnBundle(
            vuln_id="NAME-OPEN-REDIRECT",
            slug="name-open-redirect",
            workspace_subdir="app/name-open-redirect",
        ),
    )

    assert (template_req.get("name_resolution") or {}).get("resolved_vuln_id") == "NAME-TEMPLATE-INJECTION"
    assert (template_req.get("name_resolution") or {}).get("confidence") == "medium"
    assert template_req.get("vuln_label") == "Injection in Jinja template"
    assert template_req.get("vuln_name") == "Injection in Jinja template"
    assert (template_req.get("request_identity") or {}).get("request_label") == "Injection in Jinja template"
    assert (template_req.get("request_identity") or {}).get("match_class") == "token_match"
    assert (redirect_req.get("name_resolution") or {}).get("resolved_vuln_id") == "NAME-OPEN-REDIRECT"
    assert (redirect_req.get("name_resolution") or {}).get("confidence") == "high"
    assert redirect_req.get("vuln_label") == "Open Redirect"
    assert redirect_req.get("vuln_name") == "Open Redirect"
    assert (redirect_req.get("request_identity") or {}).get("request_label") == "Open Redirect"
    assert (redirect_req.get("request_identity") or {}).get("match_class") == "catalog_alias"


def test_explicit_plaintext_vuln_id_is_promoted_to_synthetic_name() -> None:
    normalized = normalize_requirement({"vuln_id": "Custom Weird Vuln"})
    requirement = normalized.requirement

    assert requirement["vuln_id"] == "NAME-CUSTOM-WEIRD-VULN"
    assert (requirement.get("name_resolution") or {}).get("source") == "synthetic_name"
    assert (requirement.get("name_resolution") or {}).get("confidence") == "low"
    assert (requirement.get("policy") or {}).get("require_researcher_evidence") is True
    assert (requirement.get("researcher") or {}).get("search_policy") == "remote_required"


def test_single_token_plaintext_vuln_id_is_promoted_to_synthetic_name() -> None:
    normalized = normalize_requirement({"vuln_id": "Foobar"})
    requirement = normalized.requirement

    assert requirement["vuln_id"] == "NAME-FOOBAR"
    assert (requirement.get("name_resolution") or {}).get("resolved_vuln_id") == "NAME-FOOBAR"
    assert (requirement.get("name_resolution") or {}).get("source") == "synthetic_name"
    assert (requirement.get("name_resolution") or {}).get("confidence") == "low"
    assert (requirement.get("policy") or {}).get("require_researcher_evidence") is True
    assert (requirement.get("researcher") or {}).get("search_policy") == "remote_required"
    request_identity = requirement.get("request_identity") or {}
    assert request_identity.get("request_label") == "Foobar"
    assert request_identity.get("input_mode") == "free_form_name"
    assert request_identity.get("synthetic_resolution") is True
    assert request_identity.get("catalog_backed_resolution") is False


def test_single_token_vuln_name_is_promoted_to_synthetic_name() -> None:
    normalized = normalize_requirement({"vuln_name": "Foobar"})
    requirement = normalized.requirement

    assert requirement["vuln_id"] == "NAME-FOOBAR"
    assert requirement["vuln_ids"] == ["NAME-FOOBAR"]
    assert (requirement.get("name_resolution") or {}).get("resolved_vuln_id") == "NAME-FOOBAR"
    assert (requirement.get("name_resolution") or {}).get("source") == "synthetic_name"
    assert (requirement.get("name_resolution") or {}).get("confidence") == "low"
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
    assert (requirement.get("name_resolution") or {}).get("confidence") == "low"
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
    assert (requirement.get("name_resolution") or {}).get("confidence") == "low"
    assert requirement["pattern_id"] == "generic-web-vuln"
    assert (requirement.get("policy") or {}).get("require_researcher_evidence") is True
    assert (requirement.get("researcher") or {}).get("search_policy") == "remote_required"


def test_invalid_low_trust_unknown_policy_falls_back_to_warn() -> None:
    requirement = _base_requirement("CWE-9999")
    requirement["policy"] = {"verifier": {"low_trust_unknown_policy": "strict"}}

    normalized = normalize_requirement(requirement)

    assert (normalized.requirement.get("policy") or {}).get("verifier", {}).get("low_trust_unknown_policy") == "warn"
    assert any("low_trust_unknown_policy" in warning for warning in normalized.warnings)


def test_invalid_min_promotion_independence_falls_back_to_compiler_coupled() -> None:
    requirement = _base_requirement("CWE-89")
    requirement["policy"] = {"verifier": {"min_promotion_independence": "self_derived"}}

    normalized = normalize_requirement(requirement)

    assert (
        (normalized.requirement.get("policy") or {}).get("verifier", {}).get("min_promotion_independence")
        == "compiler_coupled"
    )
    assert any("min_promotion_independence" in warning for warning in normalized.warnings)


def test_invalid_min_name_resolution_confidence_falls_back_to_low() -> None:
    requirement = _base_requirement("NAME-OPEN-REDIRECT")
    requirement["policy"] = {"verifier": {"min_name_resolution_confidence": "strict"}}

    normalized = normalize_requirement(requirement)

    assert (
        (normalized.requirement.get("policy") or {}).get("verifier", {}).get("min_name_resolution_confidence")
        == "low"
    )
    assert any("min_name_resolution_confidence" in warning for warning in normalized.warnings)
