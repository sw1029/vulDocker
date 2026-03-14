from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.contracts import (
    build_generator_contract,
    load_generator_contract,
    requires_semantic_support,
    requires_semantic_support_for_requirement,
    write_generator_contract,
)


def test_contract_uses_rule_defined_success_markers(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="CWE-89",
        metadata_dir=tmp_path,
        workspace_dir=tmp_path,
        generator_mode="synthesis",
        bundle_slug="cwe-89",
    )

    assert payload["success_signature"] == "SQLi SUCCESS"
    assert payload["flag_token"] == "FLAG-sqli-demo-token"
    assert payload["output_mode"] == "auto"
    assert payload["schema_version"] == "resolved_contract@1.0"
    assert payload["contract_stage"] == "synthesis"
    assert payload["semantic_contract"]["semantic_signature_source"] == ["baseline"]
    assert payload["semantic_contract"]["status"] == "aligned"
    assert payload["semantic_contract"]["contradictions"] == []
    assert payload["semantic_contract"]["semantic_signature"]["sink"] == ["SQL query execution"]
    assert payload["semantic_profile"]["compiler_supported"] is True
    assert payload["compiler_strategy"] == "sqli_string_concat"


def test_contract_preserves_family_hypothesis_summary_from_researcher_report(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="NAME-OPEN-REDIRECT",
        metadata_dir=tmp_path,
        workspace_dir=tmp_path,
        generator_mode="synthesis",
        bundle_slug="name-open-redirect",
        researcher_report={
            "researcher_report": {
                "quality": "sufficient",
                "family_hypothesis_summary": {
                    "top_family": "open_redirect",
                    "top_confidence": "high",
                    "contradiction_count": 0,
                    "contradictory_families": [],
                },
            }
        },
    )

    semantic_contract = payload["semantic_contract"]
    assert semantic_contract["family_hypothesis_summary"]["top_family"] == "open_redirect"
    assert semantic_contract["family_hypothesis_summary"]["top_confidence"] == "high"


def test_contract_surfaces_exploit_oracle_and_name_only_generation_spec(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="NAME-OPEN-REDIRECT",
        metadata_dir=tmp_path,
        workspace_dir=tmp_path,
        generator_mode="research_seed",
        bundle_slug="name-open-redirect",
        requirement={
            "vuln_id": "NAME-OPEN-REDIRECT",
            "vuln_name": "Open Redirect",
            "request_ir": {
                "request_label": "Open Redirect",
                "resolved_vuln_id": "NAME-OPEN-REDIRECT",
                "resolution_state": "catalog_alias",
                "pattern_seed_state": "preserved",
            },
            "request_identity": {
                "request_label": "Open Redirect",
                "resolved_vuln_id": "NAME-OPEN-REDIRECT",
                "input_mode": "free_form_name",
                "match_class": "catalog_alias",
                "confidence": "high",
                "name_driven": True,
            },
            "name_resolution": {
                "resolved_vuln_id": "NAME-OPEN-REDIRECT",
                "match_class": "catalog_alias",
                "confidence": "high",
            },
            "policy": {"name_only_mode": "dynamic"},
            "stack_hypotheses": [
                {"language": "python", "framework": "flask", "source": "profile_prior", "confidence": "low"},
                {"language": "python", "framework": "fastapi", "source": "available_skeleton", "confidence": "low"},
            ],
        },
        researcher_report={
            "quality": "sufficient",
            "family_hypothesis_summary": {
                "top_family": "open_redirect",
                "top_confidence": "high",
                "contradiction_count": 0,
                "contradictory_families": [],
            },
            "verification_spec": {
                "success_mode": "text",
                "success_text_markers": ["Exploit SUCCESS"],
                "flag_token": "FLAG{OPEN_REDIRECT_OK}",
                "assertion_program": [
                    {"op": "contains", "string": "Exploit SUCCESS"},
                    {"op": "not_contains", "string": "Exploit FAILED"},
                ],
                "negative_text_markers": ["Exploit FAILED"],
                "negative_controls": [{"name": "benign-next", "expect_success": False}],
                "metamorphic": {"total": 1, "passed": 1, "rationale": "same-origin redirect stays non-exploit"},
            },
        },
    )

    oracle = payload["exploit_oracle"]
    spec = payload["name_only_generation_spec"]

    assert oracle["success_signature"] == "Exploit SUCCESS"
    assert oracle["flag_token"] == "FLAG{OPEN_REDIRECT_OK}"
    assert oracle["source"] == "researcher_verification_spec"
    assert oracle["negative_text_markers"] == ["Exploit FAILED"]
    assert oracle["negative_controls"] == [{"name": "benign-next", "expect_success": False}]
    assert oracle["metamorphic"] == {"total": 1, "passed": 1, "rationale": "same-origin redirect stays non-exploit"}
    assert oracle["assertion_program"] == [
        {"op": "contains", "string": "Exploit SUCCESS"},
        {"op": "not_contains", "string": "Exploit FAILED"},
        {"op": "contains", "string": "FLAG{OPEN_REDIRECT_OK}"},
    ]
    assert spec["request_label"] == "Open Redirect"
    assert spec["request_ir"]["resolution_state"] == "catalog_alias"
    assert spec["family_working_hypothesis"] == "open_redirect"
    assert spec["family_hypothesis_source"] == "researcher_family_hypothesis"
    assert spec["request_identity_family"] == "open_redirect"
    assert spec["family_candidate_summary"]["top_family"] == "open_redirect"
    assert spec["family_candidate_summary"]["candidate_count"] == 1
    assert spec["stack_candidate_summary"]["working_stack_id"] == "python/flask"
    assert spec["stack_candidate_summary"]["candidate_count"] == 2
    assert spec["stack_candidate_summary"]["ambiguous"] is True
    assert spec["required_contract"]["require_research"] is True
    assert spec["required_contract"]["intent_success_rule"] == "open_world_positive_only"
    assert spec["planning_focus_summary"]["primary_focus"] == "stack_or_runtime_design"
    assert spec["planning_focus_summary"]["by_focus"]["stack_or_runtime_design"] == [
        "stack_defaulted",
        "stack_ambiguous",
    ]
    assert spec["planning_focus_summary"]["by_focus"]["evidence_authority"] == [
        "family_candidate_evidence_missing",
    ]
    assert spec["exploit_oracle_summary"]["success_signature"] == "Exploit SUCCESS"
    assert spec["exploit_oracle_summary"]["negative_text_markers"] == ["Exploit FAILED"]
    assert spec["exploit_oracle_summary"]["negative_controls"] == [{"name": "benign-next", "expect_success": False}]
    assert spec["exploit_oracle_summary"]["metamorphic"] == {
        "total": 1,
        "passed": 1,
        "rationale": "same-origin redirect stays non-exploit",
    }
    assert spec["exploit_oracle_summary"]["assertion_program"] == [
        {"op": "contains", "string": "Exploit SUCCESS"},
        {"op": "not_contains", "string": "Exploit FAILED"},
        {"op": "contains", "string": "FLAG{OPEN_REDIRECT_OK}"},
    ]


def test_contract_name_only_generation_spec_can_fall_back_to_request_identity_family(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="NAME-OPEN-REDIRECT",
        metadata_dir=tmp_path,
        workspace_dir=tmp_path,
        generator_mode="research_seed",
        bundle_slug="name-open-redirect",
        requirement={
            "vuln_id": "NAME-OPEN-REDIRECT",
            "vuln_name": "Open Redirect",
            "request_identity": {
                "request_label": "Open Redirect",
                "resolved_vuln_id": "NAME-OPEN-REDIRECT",
                "input_mode": "free_form_name",
                "match_class": "catalog_alias",
                "confidence": "high",
                "name_driven": True,
            },
            "name_resolution": {
                "resolved_vuln_id": "NAME-OPEN-REDIRECT",
                "match_class": "catalog_alias",
                "confidence": "high",
            },
            "policy": {"name_only_mode": "dynamic"},
        },
        researcher_report={
            "quality": "sufficient",
            "family_hypothesis_summary": {
                "top_family": "sqli",
                "top_confidence": "low",
                "contradiction_count": 0,
                "contradictory_families": [],
            },
        },
    )

    spec = payload["name_only_generation_spec"]

    assert spec["researcher_family_hypothesis"] == "sqli"
    assert spec["request_identity_family"] == "open_redirect"
    assert spec["family_working_hypothesis"] == "open_redirect"
    assert spec["family_hypothesis_source"] == "request_identity_fallback"


def test_contract_name_only_generation_spec_prefers_request_ir_source_label(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="CWE-79",
        metadata_dir=tmp_path,
        workspace_dir=tmp_path,
        generator_mode="research_seed",
        bundle_slug="cwe-79",
        requirement={
            "vuln_id": "CWE-79",
            "vuln_name": "CWE-79",
            "request_ir": {
                "request_label": "Reflected XSS",
                "resolved_vuln_id": "CWE-79",
                "resolution_state": "token_match",
                "resolution_match_class": "token_match",
                "resolution_confidence": "medium",
                "name_driven": True,
                "pattern_seed_state": "preserved",
            },
            "policy": {"name_only_mode": "dynamic"},
        },
        researcher_report={
            "quality": "sufficient",
            "family_hypothesis_summary": {
                "top_family": "xss",
                "top_confidence": "high",
                "contradiction_count": 0,
                "contradictory_families": [],
            },
        },
    )

    spec = payload["name_only_generation_spec"]
    profile = payload["semantic_profile"]

    assert spec["request_label"] == "Reflected XSS"
    assert spec["request_ir"]["name_driven"] is True
    assert profile["requested_name"] == "Reflected XSS"


def test_contract_name_only_generation_spec_deprioritizes_low_confidence_background_families_when_resolution_is_strong(
    tmp_path: Path,
) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="NAME-OPEN-REDIRECT",
        metadata_dir=tmp_path,
        workspace_dir=tmp_path,
        generator_mode="research_seed",
        bundle_slug="name-open-redirect",
        requirement={
            "vuln_id": "NAME-OPEN-REDIRECT",
            "vuln_name": "Open Redirect",
            "request_ir": {
                "request_label": "Open Redirect",
                "resolved_vuln_id": "NAME-OPEN-REDIRECT",
                "resolution_state": "catalog_alias",
                "resolution_match_class": "catalog_alias",
                "resolution_confidence": "high",
                "name_driven": True,
                "family_candidates": [
                    {"family": "open_redirect", "source": "catalog_resolution", "confidence": "high"},
                ],
            },
            "policy": {"name_only_mode": "dynamic"},
        },
        researcher_report={
            "quality": "sufficient",
            "family_hypothesis_summary": {
                "top_family": "open_redirect",
                "top_confidence": "high",
                "ranked_families": [
                    {"family": "open_redirect", "confidence": "high", "score": 0.93, "signal_hits": 8},
                    {"family": "xss", "confidence": "medium", "score": 0.72, "signal_hits": 3},
                    {"family": "ssrf", "confidence": "low", "score": 0.18, "signal_hits": 1},
                ],
                "contradiction_count": 0,
                "contradictory_families": [],
                "ambiguous": False,
            },
        },
    )

    spec = payload["name_only_generation_spec"]

    assert spec["family_candidate_summary"]["candidate_count"] == 3
    assert spec["family_candidate_summary"]["material_candidate_count"] == 1
    assert spec["family_candidate_summary"]["deprioritized_candidate_count"] == 2
    assert spec["family_candidate_summary"]["material_ambiguous"] is False
    assert spec["planning_focus_summary"]["primary_focus"] != "family_disambiguation"


def test_contract_name_only_generation_spec_uses_generation_execution_focus_for_compatibility_lane(
    tmp_path: Path,
) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="NAME-OPEN-REDIRECT",
        metadata_dir=tmp_path,
        workspace_dir=tmp_path,
        generator_mode="research_seed",
        bundle_slug="name-open-redirect",
        requirement={
            "vuln_id": "NAME-OPEN-REDIRECT",
            "vuln_name": "Open Redirect",
            "language": "python",
            "framework": "flask",
            "request_ir": {
                "request_label": "Open Redirect",
                "resolved_vuln_id": "NAME-OPEN-REDIRECT",
                "resolution_state": "catalog_alias",
                "resolution_match_class": "catalog_alias",
                "resolution_confidence": "high",
                "name_driven": True,
                "family_candidates": [
                    {"family": "open_redirect", "source": "catalog_resolution", "confidence": "high"},
                ],
            },
            "policy": {"name_only_mode": "compatibility"},
        },
        researcher_report={
            "quality": "sufficient",
            "family_hypothesis_summary": {
                "top_family": "open_redirect",
                "top_confidence": "high",
                "contradiction_count": 0,
                "contradictory_families": [],
            },
        },
    )

    spec = payload["name_only_generation_spec"]

    assert spec["required_contract"]["effective_mode"] == "compatibility"
    assert spec["planning_focus_summary"]["primary_focus"] == "generation_execution"
    assert spec["planning_focus_summary"]["by_focus"]["generation_execution"] == ["generation_ready"]


def test_enriched_request_ir_filters_background_researcher_families_under_strong_request_resolution(
    tmp_path: Path,
) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="NAME-OPEN-REDIRECT",
        metadata_dir=tmp_path,
        workspace_dir=tmp_path,
        generator_mode="research_seed",
        bundle_slug="name-open-redirect",
        requirement={
            "vuln_id": "NAME-OPEN-REDIRECT",
            "vuln_name": "Open Redirect",
            "request_ir": {
                "request_label": "Open Redirect",
                "resolved_vuln_id": "NAME-OPEN-REDIRECT",
                "resolution_state": "catalog_alias",
                "resolution_match_class": "catalog_alias",
                "resolution_confidence": "high",
                "name_driven": True,
                "family_candidates": [
                    {"family": "open_redirect", "source": "catalog_resolution", "confidence": "high"},
                ],
            },
            "policy": {"name_only_mode": "dynamic"},
        },
        researcher_report={
            "quality": "sufficient",
            "family_hypothesis_summary": {
                "top_family": "open_redirect",
                "top_confidence": "high",
                "ranked_families": [
                    {"family": "open_redirect", "confidence": "high", "score": 0.93, "signal_hits": 8},
                    {"family": "xss", "confidence": "medium", "score": 0.72, "signal_hits": 3},
                    {"family": "ssrf", "confidence": "low", "score": 0.18, "signal_hits": 1},
                ],
                "contradiction_count": 0,
                "contradictory_families": [],
                "ambiguous": False,
            },
        },
    )

    families = [item["family"] for item in payload["request_ir"]["family_candidates"]]

    assert families == ["open_redirect"]


def test_contract_surfaces_identifier_candidate_summary_and_evidence_graph(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="CWE-79",
        metadata_dir=tmp_path,
        workspace_dir=tmp_path,
        generator_mode="research_seed",
        bundle_slug="cwe-79",
        requirement={
            "vuln_id": "CWE-79",
            "request_ir": {
                "request_label": "Reflected XSS",
                "resolved_vuln_id": "CWE-79",
                "resolved_vuln_id_candidate": "CWE-79",
                "resolution_state": "token_match",
                "resolution_match_class": "token_match",
                "resolution_confidence": "medium",
                "name_driven": True,
                "identifier_candidates": [
                    {"vuln_id": "CWE-79", "source": "fragment_strategy_fallback", "confidence": "medium"},
                    {"vuln_id": "NAME-REFLECTED-XSS", "source": "synthetic_name_preview", "confidence": "low"},
                ],
            },
            "policy": {"name_only_mode": "dynamic"},
        },
        researcher_report={
            "quality": "sufficient",
            "family_hypothesis_summary": {
                "top_family": "xss",
                "top_confidence": "medium",
                "ranked_families": [
                    {"family": "xss", "confidence": "medium", "score": 0.62, "signal_hits": 2},
                    {"family": "template_injection", "confidence": "low", "score": 0.17, "signal_hits": 1},
                ],
                "contradiction_count": 1,
                "contradictory_families": ["template_injection"],
                "ambiguous": True,
            },
            "tech_stack_candidates": [
                {
                    "language": "python",
                    "framework": "flask",
                    "stack_id": "python/flask",
                    "confidence": "medium",
                    "score": 0.51,
                    "sources": ["search_hit_text"],
                }
            ],
            "evidence_graph": {
                "schema_version": "evidence_graph@0.1",
                "source": "researcher_derived",
                "node_count": 6,
                "edge_count": 6,
                "nodes": [
                    {"id": "request", "kind": "request"},
                    {"id": "query:1", "kind": "query"},
                    {"id": "evidence:1", "kind": "evidence"},
                    {"id": "family:xss", "kind": "family_hypothesis"},
                    {"id": "family:template_injection", "kind": "family_hypothesis"},
                    {"id": "stack:python/flask", "kind": "stack_hypothesis"},
                ],
                "edges": [
                    {"from": "request", "to": "query:1", "kind": "planned_query"},
                    {"from": "query:1", "to": "evidence:1", "kind": "retrieved_evidence"},
                    {"from": "request", "to": "family:xss", "kind": "family_hypothesis"},
                    {"from": "request", "to": "family:template_injection", "kind": "family_hypothesis"},
                    {"from": "evidence:1", "to": "family:xss", "kind": "supports_family_hypothesis"},
                    {"from": "evidence:1", "to": "stack:python/flask", "kind": "supports_stack_hypothesis"},
                ],
            },
        },
    )

    spec = payload["name_only_generation_spec"]
    enriched_request_ir = payload["request_ir"]

    assert payload["evidence_graph"]["schema_version"] == "evidence_graph@0.1"
    assert enriched_request_ir["abstain_reason"] == "ambiguous_family_hypothesis"
    assert enriched_request_ir["evidence_ids"] == ["evidence:1"]
    assert enriched_request_ir["family_candidates"][0]["family"] == "xss"
    assert enriched_request_ir["family_candidates"][0]["evidence_ids"] == ["evidence:1"]
    assert enriched_request_ir["family_candidates"][1]["family"] == "template_injection"
    assert "evidence_ids" not in enriched_request_ir["family_candidates"][1]
    assert enriched_request_ir["stack_candidates"][0]["stack_id"] == "python/flask"
    assert enriched_request_ir["stack_candidates"][0]["evidence_ids"] == ["evidence:1"]
    assert enriched_request_ir["negative_hypotheses"] == [
        {"family": "template_injection", "source": "researcher_contradiction"}
    ]
    assert spec["identifier_candidate_summary"]["candidate_count"] == 2
    assert spec["identifier_candidate_summary"]["resolved_vuln_id_candidate"] == "CWE-79"
    assert spec["identifier_candidate_summary"]["abstain_reason"] == "ambiguous_family_hypothesis"
    assert spec["request_ir"]["evidence_ids"] == ["evidence:1"]
    assert spec["request_ir"]["negative_hypotheses"] == [
        {"family": "template_injection", "source": "researcher_contradiction"}
    ]
    assert spec["evidence_graph_summary"]["node_count"] == 6
    assert spec["evidence_graph_summary"]["edge_count"] == 6
    assert spec["evidence_graph_summary"]["by_kind"]["evidence"] == 1
    assert spec["evidence_graph_summary"]["by_edge_kind"]["supports_family_hypothesis"] == 1
    assert spec["evidence_graph_summary"]["by_edge_kind"]["supports_stack_hypothesis"] == 1


def test_contract_name_only_generation_spec_uses_request_ir_fallback_source(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="CWE-79",
        metadata_dir=tmp_path,
        workspace_dir=tmp_path,
        generator_mode="research_seed",
        bundle_slug="cwe-79",
        requirement={
            "vuln_id": "CWE-79",
            "request_ir": {
                "request_label": "Reflected XSS",
                "resolved_vuln_id": "CWE-79",
                "resolution_state": "catalog_alias",
                "resolution_match_class": "catalog_alias",
                "resolution_confidence": "high",
                "name_driven": True,
                "family_candidates": [{"family": "xss", "confidence": "high"}],
            },
            "policy": {"name_only_mode": "dynamic"},
        },
        researcher_report={
            "quality": "sufficient",
            "family_hypothesis_summary": {
                "top_family": "sqli",
                "top_confidence": "low",
                "contradiction_count": 0,
                "contradictory_families": [],
            },
        },
    )

    spec = payload["name_only_generation_spec"]

    assert spec["request_identity_family"] == "xss"
    assert spec["family_working_hypothesis"] == "xss"
    assert spec["family_hypothesis_source"] == "request_ir_fallback"


def test_contract_uses_mysql_compiler_strategy_for_external_db_runtime(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="CWE-89",
        metadata_dir=tmp_path,
        workspace_dir=tmp_path,
        generator_mode="synthesis",
        bundle_slug="cwe-89",
        requirement={
            "vuln_name": "SQL Injection",
            "vuln_id": "CWE-89",
            "pattern_id": "sqli-union-mysql",
            "language": "python",
            "framework": "flask",
            "runtime": {"db": "mysql", "allow_external_db": True},
        },
    )

    assert payload["success_signature"] == "SQLi SUCCESS"
    assert payload["flag_token"] == "FLAG-sqli-demo-token"
    assert payload["compiler_strategy"] == "sqli_string_concat_mysql"
    assert payload["semantic_profile"]["compiler_strategy"] == "sqli_string_concat_mysql"
    assert payload["semantic_profile"]["compiler_supported"] is True
    assert payload["service_env"]["DB_HOST"] == "sqli-db"
    assert payload["resolved"]["service_env"]["DB_NAME"] == "sqliapp"


def test_contract_uses_catalog_driven_mysql_service_env_with_custom_sidecar_values(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="CWE-89",
        metadata_dir=tmp_path,
        workspace_dir=tmp_path,
        generator_mode="synthesis",
        bundle_slug="cwe-89",
        requirement={
            "vuln_name": "SQL Injection",
            "vuln_id": "CWE-89",
            "pattern_id": "sqli-union-mysql",
            "language": "python",
            "framework": "flask",
            "runtime": {"db": "mysql", "allow_external_db": True, "db_name": "runtime_db"},
            "executor": {
                "allow_network": True,
                "network_mode": "bridge",
                "sidecars": [
                    {
                        "name": "mysql-main",
                        "type": "mysql",
                        "aliases": ["db-internal"],
                        "env": {
                            "MYSQL_USER": "custom_user",
                            "MYSQL_PASSWORD": "custom_pw",
                            "MYSQL_DATABASE": "custom_db",
                        },
                    }
                ],
            },
        },
    )

    assert payload["compiler_strategy"] == "sqli_string_concat_mysql"
    assert payload["service_env"] == {
        "APP_PORT": "5000",
        "DB_HOST": "db-internal",
        "DB_PORT": "3306",
        "DB_USER": "custom_user",
        "DB_PASSWORD": "custom_pw",
        "DB_NAME": "custom_db",
    }
    assert payload["resolved"]["service_env"]["DB_HOST"] == "db-internal"


def test_contract_surfaces_runtime_recipe_for_sidecar_backed_lane(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="CWE-89",
        metadata_dir=tmp_path,
        workspace_dir=tmp_path,
        generator_mode="synthesis",
        bundle_slug="cwe-89",
        requirement={
            "vuln_name": "SQL Injection",
            "vuln_id": "CWE-89",
            "pattern_id": "sqli-union-mysql",
            "language": "python",
            "framework": "flask",
            "runtime": {"db": "mysql", "allow_external_db": True},
            "executor": {
                "allow_network": True,
                "network_mode": "bridge",
                "sidecars": [
                    {
                        "name": "mysql-main",
                        "type": "mysql",
                        "image": "mysql:8.0",
                        "aliases": ["db-internal"],
                    }
                ],
            },
        },
    )

    recipe = payload["runtime_recipe"]
    assert recipe["language"] == "python"
    assert recipe["framework"] == "flask"
    assert recipe["transport"] == "http"
    assert recipe["db"] == "mysql"
    assert recipe["allow_external_db"] is True
    assert recipe["requires_external_db"] is True
    assert recipe["network_mode"] == "bridge"
    assert recipe["network_enabled"] is True
    assert recipe["topology"] == "service_plus_sidecar"
    assert recipe["sidecars"] == [
        {
            "name": "mysql-main",
            "type": "mysql",
            "image": "mysql:8.0",
            "aliases": ["db-internal"],
        }
    ]
    assert recipe["service_env"]["DB_HOST"] == "db-internal"
    graph = payload["runtime_graph"]
    assert graph["topology"] == "service_plus_sidecar"
    assert graph["network"]["mode"] == "bridge"
    assert any(node["id"] == "service" and node["kind"] == "service" for node in graph["nodes"])
    assert any(node["id"] == "sidecar:mysql-main" and node["kind"] == "sidecar" for node in graph["nodes"])
    assert any(edge["from"] == "service" and edge["to"] == "sidecar:mysql-main" for edge in graph["edges"])
    assert graph["env_contract"][0]["scope"] == "service"
    assert graph["exploit_path"]["target_node"] == "service"


def test_contract_runtime_recipe_surfaces_soft_stack_hypotheses_for_name_only_lane(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="NAME-OPEN-REDIRECT",
        metadata_dir=tmp_path,
        workspace_dir=tmp_path,
        generator_mode="research_seed",
        bundle_slug="name-open-redirect",
        requirement={
            "vuln_name": "Open Redirect",
            "vuln_id": "NAME-OPEN-REDIRECT",
            "stack_hypotheses": [
                {"language": "python", "framework": "flask", "source": "profile_prior", "confidence": "low"},
                {"language": "python", "framework": "fastapi", "source": "available_skeleton", "confidence": "low"},
            ],
        },
    )

    recipe = payload["runtime_recipe"]
    assert recipe["language"] == "python"
    assert recipe["framework"] == "flask"
    assert recipe["stack_locked"] is False
    assert recipe["stack_source"] == "profile_prior"
    assert recipe["stack_hypotheses"][0]["stack_id"] == "python/flask"
    assert recipe["stack_hypotheses"][1]["stack_id"] == "python/fastapi"
    graph = payload["runtime_graph"]
    assert graph["topology"] == "single_service"
    assert graph["network"]["mode"] == "none"
    assert graph["exploit_path"]["entrypoint"] == "poc.py"


def test_contract_runtime_recipe_prefers_unambiguous_researcher_stack_candidate_when_unlocked(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="NAME-OPEN-REDIRECT",
        metadata_dir=tmp_path,
        workspace_dir=tmp_path,
        generator_mode="research_seed",
        bundle_slug="name-open-redirect",
        researcher_report={
            "tech_stack_candidates": [
                {
                    "language": "python",
                    "framework": "fastapi",
                    "stack_id": "python/fastapi",
                    "confidence": "medium",
                    "score": 0.55,
                    "sources": ["search_hit_text"],
                },
            ]
        },
        requirement={
            "vuln_name": "Open Redirect",
            "vuln_id": "NAME-OPEN-REDIRECT",
            "stack_hypotheses": [
                {"language": "python", "framework": "flask", "source": "profile_prior", "confidence": "low"},
                {"language": "python", "framework": "fastapi", "source": "available_skeleton", "confidence": "low"},
            ],
        },
    )

    recipe = payload["runtime_recipe"]
    assert recipe["framework"] == "fastapi"
    assert recipe["stack_source"] == "researcher_candidate"
    assert recipe["stack_locked"] is False


def test_contract_runtime_recipe_prefers_researcher_top_stack_with_clear_margin(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="NAME-OPEN-REDIRECT",
        metadata_dir=tmp_path,
        workspace_dir=tmp_path,
        generator_mode="research_seed",
        bundle_slug="name-open-redirect",
        researcher_report={
            "tech_stack_candidates": [
                {
                    "language": "python",
                    "framework": "flask",
                    "stack_id": "python/flask",
                    "confidence": "medium",
                    "score": 0.6,
                    "sources": ["search_hit_text", "stack_anchor_query"],
                },
                {
                    "language": "python",
                    "framework": "fastapi",
                    "stack_id": "python/fastapi",
                    "confidence": "low",
                    "score": 0.2,
                    "sources": ["stack_anchor_query"],
                },
            ]
        },
        requirement={
            "vuln_name": "Open Redirect",
            "vuln_id": "NAME-OPEN-REDIRECT",
            "stack_hypotheses": [
                {"language": "python", "framework": "flask", "source": "profile_prior", "confidence": "low"},
                {"language": "python", "framework": "fastapi", "source": "available_skeleton", "confidence": "low"},
            ],
        },
    )

    recipe = payload["runtime_recipe"]
    assert recipe["framework"] == "flask"
    assert recipe["stack_source"] == "researcher_candidate"
    assert recipe["stack_locked"] is False
    assert recipe["stack_selection"]["resolved"] is True
    assert recipe["stack_selection"]["basis"] == "researcher_top_candidate"
    assert recipe["stack_selection"]["selected_stack_id"] == "python/flask"
    assert recipe["stack_selection"]["confidence"] == "medium"
    assert recipe["stack_selection"]["margin"] == pytest.approx(0.4)


def test_contract_runtime_recipe_ignores_ambiguous_researcher_stack_candidates(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="NAME-OPEN-REDIRECT",
        metadata_dir=tmp_path,
        workspace_dir=tmp_path,
        generator_mode="research_seed",
        bundle_slug="name-open-redirect",
        researcher_report={
            "tech_stack_candidates": [
                {
                    "language": "python",
                    "framework": "fastapi",
                    "stack_id": "python/fastapi",
                    "confidence": "medium",
                    "score": 0.45,
                    "sources": ["search_hit_text"],
                },
                {
                    "language": "python",
                    "framework": "flask",
                    "stack_id": "python/flask",
                    "confidence": "medium",
                    "score": 0.4,
                    "sources": ["search_hit_text"],
                },
            ]
        },
        requirement={
            "vuln_name": "Open Redirect",
            "vuln_id": "NAME-OPEN-REDIRECT",
            "stack_hypotheses": [
                {"language": "python", "framework": "flask", "source": "profile_prior", "confidence": "low"},
                {"language": "python", "framework": "fastapi", "source": "available_skeleton", "confidence": "low"},
            ],
        },
    )

    recipe = payload["runtime_recipe"]
    assert recipe["framework"] == "flask"
    assert recipe["stack_source"] == "profile_prior"
    assert recipe["stack_locked"] is False
    assert recipe["stack_selection"]["resolved"] is False


def test_contract_name_only_generation_spec_keeps_evidence_authority_focus_without_selection_support(
    tmp_path: Path,
) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="NAME-OPEN-REDIRECT",
        metadata_dir=tmp_path,
        workspace_dir=tmp_path,
        generator_mode="research_seed",
        bundle_slug="name-open-redirect",
        requirement={
            "vuln_id": "NAME-OPEN-REDIRECT",
            "vuln_name": "Open Redirect",
            "request_ir": {
                "request_label": "Open Redirect",
                "resolved_vuln_id": "NAME-OPEN-REDIRECT",
                "resolution_state": "catalog_alias",
                "pattern_seed_state": "preserved",
                "evidence_ids": ["evidence:1"],
                "family_candidates": [
                    {"family": "open_redirect", "source": "catalog_resolution", "confidence": "high"}
                ],
            },
            "request_identity": {
                "request_label": "Open Redirect",
                "resolved_vuln_id": "NAME-OPEN-REDIRECT",
                "input_mode": "free_form_name",
                "match_class": "catalog_alias",
                "confidence": "high",
                "name_driven": True,
            },
            "name_resolution": {
                "resolved_vuln_id": "NAME-OPEN-REDIRECT",
                "match_class": "catalog_alias",
                "confidence": "high",
            },
            "policy": {"name_only_mode": "dynamic"},
            "stack_hypotheses": [
                {"language": "python", "framework": "flask", "source": "profile_prior", "confidence": "low"},
                {"language": "python", "framework": "fastapi", "source": "available_skeleton", "confidence": "low"},
            ],
        },
        researcher_report={
            "quality": "sufficient",
            "tech_stack_candidates": [
                {
                    "language": "python",
                    "framework": "flask",
                    "stack_id": "python/flask",
                    "confidence": "medium",
                    "score": 0.6,
                    "sources": ["search_hit_text", "stack_anchor_query"],
                },
                {
                    "language": "python",
                    "framework": "fastapi",
                    "stack_id": "python/fastapi",
                    "confidence": "low",
                    "score": 0.2,
                    "sources": ["stack_anchor_query"],
                },
            ],
            "family_hypothesis_summary": {
                "top_family": "open_redirect",
                "top_confidence": "high",
                "contradiction_count": 0,
                "contradictory_families": [],
            },
            "verification_spec": {
                "success_mode": "text",
                "success_text_markers": ["Exploit SUCCESS"],
                "flag_token": "FLAG{OPEN_REDIRECT_OK}",
                "assertion_program": [{"op": "contains", "string": "Exploit SUCCESS"}],
                "negative_text_markers": ["Exploit FAILED"],
                "negative_controls": [{"name": "benign-next", "expect_success": False}],
                "metamorphic": {"total": 1, "passed": 1, "rationale": "same-origin redirect stays non-exploit"},
            },
        },
    )

    spec = payload["name_only_generation_spec"]
    request_ir = payload["request_ir"]
    executor_plan = payload["executor_plan"]
    assert request_ir["selection_decision"]["stack"]["selected"] is True
    assert request_ir["selection_decision"]["stack"]["selected_stack_id"] == "python/flask"
    assert request_ir["selection_decision"]["stack"]["basis"] == "researcher_top_candidate"
    assert "support_count" in request_ir["selection_decision"]["stack"]
    assert isinstance(request_ir["selection_decision"]["stack"]["support_by_source_authority"], dict)
    assert request_ir["selection_decision"]["family"]["selected"] is True
    assert request_ir["selection_decision"]["family"]["selected_family"] == "open_redirect"
    assert "support_count" in request_ir["selection_decision"]["family"]
    assert isinstance(request_ir["selection_decision"]["family"]["support_by_source_authority"], dict)
    assert request_ir["selection_decision"]["ready_for_materialization"] is True
    assert request_ir["selection_decision"]["open_world_evidence_ready"] is False
    assert executor_plan["service_port"] == 5000
    assert executor_plan.get("health_path") in {None, "/health"}
    assert executor_plan["stack_selection"]["selected_stack_id"] == "python/flask"
    assert spec["stack_candidate_summary"]["working_stack_source"] == "researcher_candidate"
    assert spec["stack_candidate_summary"]["working_stack_defaulted"] is False
    assert spec["stack_candidate_summary"]["selection_resolved"] is True
    assert spec["stack_candidate_summary"]["selection_basis"] == "researcher_top_candidate"
    assert "selection_support_count" in spec["stack_candidate_summary"]
    assert "selection_support_by_source_authority" in spec["stack_candidate_summary"]
    assert "selection_support_count" in spec["family_candidate_summary"]
    assert "selection_support_by_source_authority" in spec["family_candidate_summary"]
    assert spec["planning_focus_summary"]["primary_focus"] == "evidence_authority"
    assert spec["planning_focus_summary"]["by_focus"]["evidence_authority"] == [
        "selected_family_support_missing",
        "selected_stack_support_missing",
        "selected_family_authority_thin",
        "selected_stack_authority_thin",
    ]


def test_contract_marks_cwe352_as_compiler_supported_when_strategy_exists(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="CWE-352",
        metadata_dir=tmp_path,
        workspace_dir=None,
        generator_mode="research_seed",
        bundle_slug="cwe-352",
        requirement={"vuln_name": "CSRF", "vuln_id": "CWE-352", "language": "python", "framework": "flask"},
    )

    profile = payload["semantic_profile"]
    assert profile["family"] == "csrf"
    assert profile["compiler_strategy"] == "csrf_missing_token"
    assert profile["compiler_supported"] is True
    assert payload["compiler_supported"] is True


def test_contract_keeps_static_rule_lower_bound_when_compiler_disabled_for_cwe22(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="CWE-22",
        metadata_dir=tmp_path,
        workspace_dir=None,
        generator_mode="research_seed",
        bundle_slug="cwe-22",
        requirement={
            "vuln_name": "Path Traversal",
            "vuln_id": "CWE-22",
            "compiler": {"enabled": False},
            "language": "python",
            "framework": "flask",
        },
    )

    lower_bound = payload["lower_bound"]
    assert lower_bound["family_non_remote_available"] is True
    assert lower_bound["effective_non_remote_available"] is True
    assert lower_bound["compiler_path_enabled"] is False
    assert lower_bound["effective_reason"] == "static rule available"
    assert payload["effective_non_remote_available"] is True
    assert payload["semantic_profile"]["lower_bound"]["effective_non_remote_available"] is True


def test_contract_keeps_static_rule_lower_bound_when_compiler_disabled(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="CWE-89",
        metadata_dir=tmp_path,
        workspace_dir=None,
        generator_mode="research_seed",
        bundle_slug="cwe-89",
        requirement={
            "vuln_name": "SQL Injection",
            "vuln_id": "CWE-89",
            "compiler": {"enabled": False},
            "language": "python",
            "framework": "flask",
        },
    )

    lower_bound = payload["lower_bound"]
    assert lower_bound["static_rule_available"] is True
    assert lower_bound["family_non_remote_available"] is True
    assert lower_bound["effective_non_remote_available"] is True


def test_contract_uses_researcher_proposal_when_rule_is_missing(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="CWE-9999",
        metadata_dir=tmp_path,
        workspace_dir=None,
        generator_mode="research_seed",
        bundle_slug="cwe-9999",
        researcher_report={
            "researcher_report": {
                "verification_spec": {
                    "success_mode": "json",
                    "success_text_markers": ["UNKNOWN SUCCESS"],
                    "flag_token": "FLAG-unknown",
                    "json_success_key": "count",
                    "json_success_value": 2,
                    "assertion_program": [{"op": "contains", "string": "UNKNOWN SUCCESS"}],
                },
                "semantic_signature": {
                    "input_vector": ["request.args"],
                    "sink": ["execute("],
                    "exploit_precondition": ["string concatenation"],
                },
                "semantic_signature_source": ["heuristic"],
                "quality": "sufficient",
                "quality_reason": "semantic anchors matched",
            }
        },
    )

    assert payload["success_signature"] == "UNKNOWN SUCCESS"
    assert payload["flag_token"] == "FLAG-unknown"
    assert payload["sources"]["success_signature"] == "researcher_report.verification_spec.success_text_markers[0]"
    assert payload["sources"]["flag_token"] == "researcher_report.verification_spec.flag_token"
    assert payload["proposed_verification_contract"]["success_signature"] == "UNKNOWN SUCCESS"
    assert payload["proposed_verification_contract"]["flag_token"] == "FLAG-unknown"
    assert payload["proposed_verification_contract"]["success_mode"] == "json"
    assert payload["proposed_verification_contract"]["json_success_key"] == "count"
    assert payload["proposed_verification_contract"]["json_success_value"] == 2
    assert payload["semantic_contract"]["semantic_signature"]["sink"] == ["execute("]
    assert payload["semantic_contract"]["semantic_signature_source"] == ["heuristic"]
    assert payload["semantic_contract"]["quality"] == "sufficient"
    assert payload["contract_stage"] == "research_seed"
    assert payload["exploit_oracle"]["assertion_program"] == [
        {"op": "contains", "string": "UNKNOWN SUCCESS"},
        {"op": "contains", "string": "FLAG-unknown"},
    ]


def test_contract_derives_verification_contract_from_generator_manifest_poc(tmp_path: Path) -> None:
    (tmp_path / "generator_manifest.json").write_text(
        json.dumps(
            {
                "manifest": {
                    "files": [
                        {
                            "path": "app.py",
                            "role": "service_main",
                            "content": "print('service')\n",
                        },
                        {
                            "path": "poc.py",
                            "role": "poc_entry",
                            "content": (
                                "print('UNKNOWN SUCCESS')\n"
                                "print('FLAG-unknown')\n"
                                "print('Exploit FAILED')\n"
                            ),
                        },
                    ],
                    "run": {"command": "python app.py", "port": 5000},
                    "poc": {
                        "cmd": "python poc.py --base-url {{base_url}}",
                        "success_signature": "UNKNOWN SUCCESS",
                        "flag_token": "FLAG-unknown",
                    },
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="CWE-9999",
        metadata_dir=tmp_path,
        workspace_dir=tmp_path,
        generator_mode="synthesis",
        bundle_slug="cwe-9999",
    )

    proposal = payload["proposed_verification_contract"]
    oracle = payload["exploit_oracle"]
    assert proposal["source"] == "generator_manifest.poc_derived_verification_spec"
    assert proposal["success_signature"] == "UNKNOWN SUCCESS"
    assert proposal["flag_token"] == "FLAG-unknown"
    assert proposal["negative_text_markers"] == ["Exploit FAILED"]
    assert oracle["source"] == "generator_manifest.poc_derived_verification_spec"
    assert {"op": "not_contains", "string": "Exploit FAILED"} in oracle["assertion_program"]


def test_contract_merges_manifest_negative_markers_into_researcher_proposal(tmp_path: Path) -> None:
    (tmp_path / "generator_manifest.json").write_text(
        json.dumps(
            {
                "manifest": {
                    "files": [
                        {
                            "path": "app.py",
                            "role": "service_main",
                            "content": "print('service')\n",
                        },
                        {
                            "path": "poc.py",
                            "role": "poc_entry",
                            "content": (
                                "print('UNKNOWN SUCCESS')\n"
                                "print('FLAG-unknown')\n"
                                "print('Exploit FAILED')\n"
                            ),
                        },
                    ],
                    "run": {"command": "python app.py", "port": 5000},
                    "poc": {
                        "cmd": "python poc.py --base-url {{base_url}}",
                        "success_signature": "UNKNOWN SUCCESS",
                        "flag_token": "FLAG-unknown",
                    },
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="CWE-9999",
        metadata_dir=tmp_path,
        workspace_dir=tmp_path,
        generator_mode="synthesis",
        bundle_slug="cwe-9999",
        researcher_report={
            "verification_spec": {
                "success_text_markers": ["UNKNOWN SUCCESS"],
                "flag_token": "FLAG-unknown",
            }
        },
    )

    proposal = payload["proposed_verification_contract"]
    oracle = payload["exploit_oracle"]
    assert proposal["source"] == "researcher_report.verification_spec"
    assert proposal["negative_text_markers"] == ["Exploit FAILED"]
    assert oracle["source"] == "researcher_verification_spec"
    assert {"op": "not_contains", "string": "Exploit FAILED"} in oracle["assertion_program"]


def test_contract_marks_insufficient_unknown_semantics_as_empty(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="CWE-9999",
        metadata_dir=tmp_path,
        workspace_dir=None,
        generator_mode="research_seed",
        bundle_slug="cwe-9999",
        researcher_report={
            "researcher_report": {
                "semantic_signature": {
                    "input_vector": ["request.args"],
                    "sink": ["execute("],
                    "exploit_precondition": ["string concatenation"],
                },
                "semantic_signature_source": ["heuristic"],
                "quality": "insufficient",
                "quality_reason": "remote evidence missing",
            }
        },
    )

    semantic_contract = payload["semantic_contract"]
    assert semantic_contract["semantic_signature_source"] == ["heuristic"]
    assert semantic_contract["quality"] == "insufficient"
    assert semantic_contract["status"] == "empty"
    assert payload["semantic_profile"]["derived_assertions"]["semantic_status"] == "empty"


def test_contract_uses_cwe918_rule_defined_markers(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="CWE-918",
        metadata_dir=tmp_path,
        workspace_dir=tmp_path,
        generator_mode="synthesis",
        bundle_slug="cwe-918",
    )

    assert payload["success_signature"] == "FLAG{SSRF_OK}"
    assert payload["flag_token"] == "FLAG{SSRF_OK}"
    assert payload["semantic_contract"]["semantic_signature_source"] == ["baseline"]
    assert payload["semantic_contract"]["status"] == "aligned"
    assert payload["semantic_profile"]["compiler_supported"] is True
    assert payload["compiler_strategy"] == "ssrf_loopback_fetch"


def test_contract_marks_cwe79_as_compiler_supported_when_strategy_exists(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="CWE-79",
        metadata_dir=tmp_path,
        workspace_dir=None,
        generator_mode="research_seed",
        bundle_slug="cwe-79",
        requirement={"vuln_name": "Reflected XSS", "vuln_id": "CWE-79", "language": "python", "framework": "flask"},
    )

    profile = payload["semantic_profile"]
    assert profile["family"] == "xss"
    assert profile["support_level"] == "builtin_supported"
    assert profile["compiler_strategy"] == "xss_reflected"
    assert profile["compiler_supported"] is True
    assert payload["compiler_supported"] is True
    assert payload["compiler_strategy"] == "xss_reflected"


def test_contract_marks_cwe502_as_compiler_supported_when_strategy_exists(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="CWE-502",
        metadata_dir=tmp_path,
        workspace_dir=None,
        generator_mode="research_seed",
        bundle_slug="cwe-502",
        requirement={"vuln_name": "Insecure Deserialization", "vuln_id": "CWE-502", "language": "python", "framework": "flask"},
    )

    profile = payload["semantic_profile"]
    assert profile["family"] == "deserialization"
    assert profile["compiler_strategy"] == "deserialization_pickle_body"
    assert profile["compiler_supported"] is True
    assert payload["compiler_supported"] is True


def test_contract_marks_cwe22_as_compiler_supported_when_strategy_exists(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="CWE-22",
        metadata_dir=tmp_path,
        workspace_dir=None,
        generator_mode="research_seed",
        bundle_slug="cwe-22",
        requirement={"vuln_name": "Path Traversal", "vuln_id": "CWE-22", "language": "python", "framework": "flask"},
    )

    profile = payload["semantic_profile"]
    assert profile["family"] == "path_traversal"
    assert profile["compiler_strategy"] == "path_traversal_file_read"
    assert profile["compiler_supported"] is True
    assert payload["compiler_supported"] is True


def test_contract_marks_cwe94_as_compiler_supported_when_strategy_exists(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="CWE-94",
        metadata_dir=tmp_path,
        workspace_dir=None,
        generator_mode="research_seed",
        bundle_slug="cwe-94",
        requirement={"vuln_name": "Code Injection", "vuln_id": "CWE-94", "language": "python", "framework": "flask"},
    )

    profile = payload["semantic_profile"]
    assert profile["family"] == "code_injection"
    assert profile["support_level"] == "builtin_supported"
    assert profile["compiler_strategy"] == "code_injection_eval"
    assert profile["compiler_supported"] is True
    assert payload["compiler_supported"] is True
    assert payload["compiler_strategy"] == "code_injection_eval"


def test_contract_records_semantic_contradiction_against_known_baseline(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="CWE-89",
        metadata_dir=tmp_path,
        workspace_dir=None,
        generator_mode="research_seed",
        bundle_slug="cwe-89",
        researcher_report={
            "researcher_report": {
                "verification_spec": {
                    "success_text_markers": ["SQLi SUCCESS"],
                    "flag_token": "FLAG-sqli-demo-token",
                },
                "semantic_signature": {
                    "input_vector": ["cross-site request"],
                    "sink": ["state-changing endpoint (POST/PUT/DELETE/PATCH)"],
                    "exploit_precondition": ["missing CSRF token validation"],
                },
                "semantic_signature_source": ["heuristic"],
                "quality": "sufficient",
                "quality_reason": "semantic anchors matched",
            }
        },
    )

    semantic_contract = payload["semantic_contract"]
    assert semantic_contract["status"] == "contradicted"
    assert semantic_contract["authority"] == "resolved_contract.semantic_contract"
    assert any("baseline" in item for item in semantic_contract["contradictions"])


def test_contract_records_foreign_family_terms_for_known_baseline(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="CWE-22",
        metadata_dir=tmp_path,
        workspace_dir=None,
        generator_mode="research_seed",
        bundle_slug="cwe-22",
        researcher_report={
            "researcher_report": {
                "semantic_signature": {
                    "input_vector": ["request.args"],
                    "sink": ["open(", "requests.get"],
                    "exploit_precondition": ["path traversal", "server-side request forgery"],
                },
                "semantic_signature_source": ["heuristic"],
            }
        },
    )

    semantic_contract = payload["semantic_contract"]
    assert semantic_contract["status"] == "contradicted"
    assert any("foreign-family term 'requests.get'" in item for item in semantic_contract["contradictions"])
    assert any("foreign-family term 'server-side request forgery'" in item for item in semantic_contract["contradictions"])


def test_contract_backfills_fragment_signature_for_supported_freeform_family(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="NAME-OPEN-REDIRECT",
        metadata_dir=tmp_path,
        workspace_dir=None,
        generator_mode="research_seed",
        bundle_slug="name-open-redirect",
        researcher_report={"researcher_report": {"verification_spec": {"success_text_markers": ["Exploit SUCCESS"]}}},
    )

    assert requires_semantic_support("NAME-OPEN-REDIRECT") is True
    assert payload["semantic_contract"]["status"] == "aligned"
    assert payload["semantic_contract"]["contradictions"] == []
    assert payload["semantic_contract"]["semantic_signature_source"] == ["fragment_registry"]
    assert payload["semantic_contract"]["semantic_signature"]["sink"] == [
        "redirect(",
        "location header",
        "http redirect sink",
    ]


def test_contract_uses_fragment_signature_for_canonicalized_name_driven_family(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="CWE-79",
        metadata_dir=tmp_path,
        workspace_dir=None,
        generator_mode="research_seed",
        bundle_slug="cwe-79",
        requirement={
            "vuln_id": "CWE-79",
            "request_ir": {
                "request_label": "Reflected XSS",
                "resolved_vuln_id": "CWE-79",
                "name_driven": True,
                "resolution_state": "token_match",
            },
        },
    )

    assert payload["semantic_contract"]["status"] == "aligned"
    assert payload["semantic_contract"]["contradictions"] == []
    assert payload["semantic_contract"]["semantic_signature_source"] == ["fragment_registry"]
    assert payload["semantic_contract"]["semantic_signature"]["sink"] == [
        "render_template_string",
        "template response",
    ]


def test_requires_semantic_support_for_requirement_uses_request_ir_name_driven_signal() -> None:
    assert requires_semantic_support("CWE-79") is False
    assert requires_semantic_support_for_requirement(
        "CWE-79",
        {
            "vuln_id": "CWE-79",
            "request_ir": {
                "request_label": "Reflected XSS",
                "resolved_vuln_id": "CWE-79",
                "name_driven": True,
                "resolution_state": "token_match",
            },
        },
    ) is True


def test_contract_surfaces_semantic_profile_and_compiler_verdict(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="NAME-OPEN-REDIRECT",
        metadata_dir=tmp_path,
        workspace_dir=None,
        generator_mode="research_seed",
        bundle_slug="name-open-redirect",
        requirement={
            "vuln_name": "Open Redirect",
            "vuln_id": "NAME-OPEN-REDIRECT",
            "language": "python",
            "framework": "flask",
        },
        researcher_report={
            "researcher_report": {
                "semantic_signature": {
                    "input_vector": ["next parameter"],
                    "sink": ["redirect(", "Location header"],
                    "exploit_precondition": ["open redirect", "unvalidated redirect target"],
                },
                "verification_spec": {"success_text_markers": ["Exploit SUCCESS"]},
            }
        },
    )

    profile = payload["semantic_profile"]
    assert profile["schema_version"] == "semantic_profile@1.0"
    assert profile["requested_name"] == "Open Redirect"
    assert profile["family"] == "open_redirect"
    assert profile["support_level"] == "compiler_supported"
    assert profile["compiler_strategy"] == "open_redirect_reflect"
    assert profile["compiler_supported"] is True
    assert "available" in profile["compiler_reason"]
    assert payload["compiler_supported"] is True
    assert payload["compiler_strategy"] == "open_redirect_reflect"


def test_contract_keeps_name_open_redirect_fail_closed_but_populates_profile_signature(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="NAME-OPEN-REDIRECT",
        metadata_dir=tmp_path,
        workspace_dir=None,
        generator_mode="research_seed",
        bundle_slug="name-open-redirect",
        requirement={
            "vuln_name": "Open Redirect",
            "vuln_id": "NAME-OPEN-REDIRECT",
            "language": "python",
            "framework": "flask",
            "pattern_id": "open-redirect",
        },
        researcher_report={"researcher_report": {"verification_spec": {"success_text_markers": ["Exploit SUCCESS"]}}},
    )

    assert payload["semantic_contract"]["status"] == "aligned"
    profile = payload["semantic_profile"]
    assert profile["compiler_supported"] is True
    assert profile["semantic_signature"]["input_vector"] == [
        "request.args",
        "next parameter",
        "redirect target",
        "url parameter",
    ]
    assert profile["semantic_signature"]["sink"] == [
        "redirect(",
        "location header",
        "http redirect sink",
    ]
    assert profile["semantic_signature_source"] == ["fragment_registry"]


def test_contract_marks_name_template_injection_as_compiler_supported(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="NAME-TEMPLATE-INJECTION",
        metadata_dir=tmp_path,
        workspace_dir=None,
        generator_mode="research_seed",
        bundle_slug="name-template-injection",
        requirement={
            "vuln_name": "Template Injection",
            "vuln_id": "NAME-TEMPLATE-INJECTION",
            "language": "python",
            "framework": "flask",
        },
        researcher_report={
            "researcher_report": {
                "semantic_signature": {
                    "input_vector": ["request.args", "query parameter"],
                    "sink": ["render_template_string", "jinja2 template rendering from string"],
                    "exploit_precondition": [
                        "user input is embedded into template source string (concatenation/interpolation)",
                        "template string is rendered server-side without escaping/sandboxing",
                    ],
                },
                "verification_spec": {"success_text_markers": ["Exploit SUCCESS"]},
            }
        },
    )

    profile = payload["semantic_profile"]
    assert profile["family"] == "template_injection"
    assert profile["support_level"] == "compiler_supported"
    assert profile["compiler_strategy"] == "template_injection_render"
    assert profile["compiler_supported"] is True
    assert payload["compiler_supported"] is True
    assert payload["compiler_strategy"] == "template_injection_render"


def test_contract_marks_name_ldap_injection_as_compiler_supported(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="NAME-LDAP-INJECTION",
        metadata_dir=tmp_path,
        workspace_dir=None,
        generator_mode="research_seed",
        bundle_slug="name-ldap-injection",
        requirement={
            "vuln_name": "LDAP Injection",
            "vuln_id": "NAME-LDAP-INJECTION",
            "language": "python",
            "framework": "flask",
        },
        researcher_report={
            "researcher_report": {
                "verification_spec": {"success_text_markers": ["Exploit SUCCESS"]},
            }
        },
    )

    profile = payload["semantic_profile"]
    assert profile["family"] == "ldap_injection"
    assert profile["support_level"] == "compiler_supported"
    assert profile["compiler_strategy"] == "ldap_injection_filter"
    assert profile["compiler_supported"] is True
    assert payload["compiler_supported"] is True
    assert payload["compiler_strategy"] == "ldap_injection_filter"


@pytest.mark.parametrize(
    ("vuln_id", "vuln_name"),
    [
        ("NAME-OPEN-REDIRECT", "Open Redirect"),
        ("NAME-TEMPLATE-INJECTION", "Template Injection"),
        ("NAME-XXE", "XML External Entity"),
        ("NAME-LDAP-INJECTION", "LDAP Injection"),
    ],
)
def test_contract_surfaces_static_rule_for_supported_freeform_name_family(
    tmp_path: Path,
    vuln_id: str,
    vuln_name: str,
) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id=vuln_id,
        metadata_dir=tmp_path,
        workspace_dir=None,
        generator_mode="research_seed",
        bundle_slug=vuln_id.lower(),
        requirement={
            "vuln_name": vuln_name,
            "vuln_id": vuln_id,
            "language": "python",
            "framework": "flask",
        },
    )

    lower_bound = payload["lower_bound"]
    assert lower_bound["static_rule_available"] is True
    assert lower_bound["family_non_remote_available"] is True
    assert payload["semantic_profile"]["lower_bound"]["static_rule_available"] is True


def test_contract_populates_profile_signature_for_name_template_injection_without_research_semantics(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="NAME-TEMPLATE-INJECTION",
        metadata_dir=tmp_path,
        workspace_dir=None,
        generator_mode="research_seed",
        bundle_slug="name-template-injection",
        requirement={
            "vuln_name": "Template Injection",
            "vuln_id": "NAME-TEMPLATE-INJECTION",
            "language": "python",
            "framework": "flask",
            "pattern_id": "template-injection",
        },
        researcher_report={"researcher_report": {"verification_spec": {"success_text_markers": ["Exploit SUCCESS"]}}},
    )

    assert payload["semantic_contract"]["status"] == "aligned"
    profile = payload["semantic_profile"]
    assert profile["compiler_supported"] is True
    assert profile["semantic_signature"]["sink"] == [
        "render_template_string",
        "jinja2 template rendering",
        "template source construction",
    ]
    assert profile["semantic_signature_source"] == ["fragment_registry"]


def test_contract_detects_foreign_family_terms_for_name_open_redirect(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="NAME-OPEN-REDIRECT",
        metadata_dir=tmp_path,
        workspace_dir=None,
        generator_mode="research_seed",
        bundle_slug="name-open-redirect",
        requirement={
            "vuln_name": "Open Redirect",
            "vuln_id": "NAME-OPEN-REDIRECT",
            "language": "python",
            "framework": "flask",
        },
        researcher_report={
            "researcher_report": {
                "semantic_signature": {
                    "input_vector": ["next parameter"],
                    "sink": ["render_template_string"],
                    "exploit_precondition": ["server-side template injection"],
                },
                "verification_spec": {"success_text_markers": ["Exploit SUCCESS"]},
            }
        },
    )

    semantic_contract = payload["semantic_contract"]
    assert semantic_contract["status"] == "contradicted"
    assert any("foreign-family term 'render_template_string'" in item for item in semantic_contract["contradictions"])
    assert any("foreign-family term 'server-side template injection'" in item for item in semantic_contract["contradictions"])


def test_write_generator_contract_mirrors_resolved_and_legacy_files(tmp_path: Path) -> None:
    payload = {
        "schema_version": "resolved_contract@1.0",
        "sid": "sid-contract",
        "slug": "cwe-89",
        "vuln_id": "CWE-89",
        "success_signature": "SQLi SUCCESS",
        "flag_token": "FLAG-sqli-demo-token",
        "service_entry": "app.py",
        "poc_entry": "poc.py",
        "service_port": 5000,
        "base_url": "http://127.0.0.1:5000",
        "output_mode": "auto",
        "compiler_supported": False,
        "compiler_strategy": "sqli_string_concat",
        "compiler_reason": "compiler scaffold registry not implemented",
        "semantic_profile": {
            "schema_version": "semantic_profile@1.0",
            "sid": "sid-contract",
            "slug": "cwe-89",
            "requested_name": "CWE-89",
            "normalized_vuln_id": "CWE-89",
            "family": "sql_injection",
            "support_level": "builtin_supported",
            "compiler_strategy": "sqli_string_concat",
            "compiler_supported": False,
            "compiler_reason": "compiler scaffold registry not implemented",
            "stack_profile": {"language": "python", "framework": "flask"},
            "scenario_shape": {"service_entry": "app.py", "poc_entry": "poc.py", "service_port": 5000},
            "semantic_signature": {"input_vector": [], "sink": [], "exploit_precondition": []},
            "verification_contract": {"success_signature": "SQLi SUCCESS", "output_mode": "auto"},
            "derived_assertions": {"semantic_gate_required": False},
            "evidence_relevance": {},
        },
    }

    written = write_generator_contract(tmp_path, payload)

    assert written.name == "resolved_contract.json"
    assert (tmp_path / "resolved_contract.json").exists()
    assert (tmp_path / "generator_contract.json").exists()
    assert (tmp_path / "semantic_profile.json").exists()
    loaded = load_generator_contract(tmp_path)
    assert loaded is not None
    assert loaded["success_signature"] == "SQLi SUCCESS"
    assert json.loads((tmp_path / "generator_contract.json").read_text(encoding="utf-8"))["slug"] == "cwe-89"


def test_contract_provenance_prefers_generator_manifest_metadata(tmp_path: Path) -> None:
    (tmp_path / "generator_manifest.json").write_text(
        json.dumps(
            {
                "generation_origin": "deterministic_fallback",
                "fallback_used": True,
                "fallback_class": "generic_unsupported_family",
                "family_override_applied": False,
                "llm_stub_used": True,
                "manifest": {
                    "files": [
                        {"path": "app.py", "role": "service_main", "content": "print('app')\n"},
                        {"path": "poc.py", "role": "poc_entry", "content": "print('poc')\n"},
                    ],
                    "poc": {"success_signature": "Exploit SUCCESS"},
                    "run": {"port": 8080},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="CWE-9999",
        metadata_dir=tmp_path,
        workspace_dir=tmp_path,
        generator_mode="synthesis",
        bundle_slug="cwe-9999",
    )

    assert payload["generation_origin"] == "deterministic_fallback"
    assert payload["fallback_used"] is True
    assert payload["fallback_class"] == "generic_unsupported_family"
    assert payload["family_override_applied"] is False
    assert payload["llm_stub_used"] is True
    assert payload["provenance"]["source"] == "generator_manifest"
    assert payload["provenance"]["fallback_class"] == "generic_unsupported_family"


def test_contract_provenance_uses_template_summary_when_manifest_is_missing(tmp_path: Path) -> None:
    (tmp_path / "generator_template.json").write_text(
        json.dumps(
            {
                "template_id": "flask_sqlite_raw",
                "template_stack_id": "python/flask",
                "template_language": "python",
                "template_framework": "flask",
                "requested_stack_id": "python/flask",
                "template_stack_match": True,
                "template_runtime_surface_status": "not_required",
                "template_runtime_surface_reason": "template runtime requirements are satisfied",
                "template_runtime_diagnostics": {
                    "matches": True,
                    "status": "not_required",
                    "reason": "template runtime requirements are satisfied",
                    "requested_stack_id": "python/flask",
                    "template_stack_id": "python/flask",
                },
                "service_entry": "app.py",
                "poc_entry": "poc.py",
                "ports": {"app": 5000},
                "service_env": {"DB_HOST": "sqli-db", "DB_NAME": "sqliapp"},
                "generation_origin": "built_in_template",
                "fallback_used": False,
                "family_override_applied": False,
                "llm_stub_used": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="CWE-89",
        metadata_dir=tmp_path,
        workspace_dir=None,
        generator_mode="template",
        bundle_slug="cwe-89",
    )

    assert payload["generation_origin"] == "built_in_template"
    assert payload["fallback_used"] is False
    assert payload["family_override_applied"] is False
    assert payload["llm_stub_used"] is False
    assert payload["provenance"]["template_id"] == "flask_sqlite_raw"
    assert payload["provenance"]["source"] == "generator_template"
    assert payload["service_env"] == {"DB_HOST": "sqli-db", "DB_NAME": "sqliapp"}
    assert payload["template_stack_id"] == "python/flask"
    assert payload["requested_stack_id"] == "python/flask"
    assert payload["template_stack_match"] is True
    assert payload["template_runtime_surface_status"] == "not_required"
    assert payload["template_runtime_diagnostics"]["matches"] is True


def test_contract_rule_resolution_supports_name_prefixed_runtime_rules(tmp_path: Path, monkeypatch) -> None:
    runtime_rules = tmp_path / "runtime_rules"
    runtime_rules.mkdir(parents=True)
    (runtime_rules / "name-open-redirect.yaml").write_text("cwe: NAME-OPEN-REDIRECT\nversion: 2\n", encoding="utf-8")
    monkeypatch.setenv("VULD_RUNTIME_RULE_DIRS", str(runtime_rules))

    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="NAME-OPEN-REDIRECT",
        metadata_dir=tmp_path,
        workspace_dir=None,
        generator_mode="research_seed",
        bundle_slug="name-open-redirect",
        researcher_report={
            "researcher_report": {
                "semantic_signature": {
                    "input_vector": ["request.args", "next parameter"],
                    "sink": ["redirect(", "location header"],
                    "exploit_precondition": ["open redirect", "unvalidated redirect target"],
                }
            }
        },
    )

    assert payload["rule_resolution"]["normalized_id"] == "name-open-redirect"
    assert payload["rule_resolution"]["selected_source"] == "runtime"
