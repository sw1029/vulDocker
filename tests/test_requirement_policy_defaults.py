from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.schema import normalize_requirement


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
