from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.contracts import (
    _build_executor_plan,
    _build_runtime_graph,
    _runtime_seed_files,
    build_generator_contract,
    load_generator_contract,
    requires_semantic_support,
    requires_semantic_support_for_requirement,
    write_generator_contract,
)
from agents.generator.compiler import compile_manifest


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
                "negative_controls": [{"name": "benign-next", "expect_success": False, "payload": "/local"}],
                "metamorphic": {
                    "total": 1,
                    "passed": 1,
                    "rationale": "same-origin redirect stays non-exploit",
                    "cases": [{"name": "same-origin", "payload": "/local", "expect_success": False}],
                },
            },
        },
    )

    oracle = payload["exploit_oracle"]
    spec = payload["name_only_generation_spec"]
    staged = payload["staged_synthesis"]

    assert oracle["success_signature"] == "Exploit SUCCESS"
    assert oracle["flag_token"] == "FLAG{OPEN_REDIRECT_OK}"
    assert oracle["source"] == "researcher_verification_spec"
    assert oracle["negative_text_markers"] == ["Exploit FAILED"]
    assert oracle["negative_controls"] == [{"name": "benign-next", "expect_success": False, "payload": "/local"}]
    assert oracle["metamorphic"] == {
        "total": 1,
        "passed": 1,
        "rationale": "same-origin redirect stays non-exploit",
        "cases": [{"name": "same-origin", "payload": "/local", "expect_success": False}],
    }
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
    assert spec["primitive_hypotheses"] == []
    assert spec["runtime_dependency_hypotheses"] == []
    assert spec["topology_hypotheses"][0]["topology"] == "single_service"
    assert spec["scenario_candidate_summary"]["candidate_count"] == 2
    assert spec["scenario_candidate_summary"]["selected_candidate_count"] == 1
    assert spec["scenario_candidate_summary"]["top_family"] == "open_redirect"
    assert spec["scenario_candidate_summary"]["top_oracle_mode"] == "stateful_text"
    assert spec["scenario_candidate_summary"]["selected_oracle_mode"] == "stateful_text"
    assert spec["scenario_candidate_summary"]["selection_state"] == "candidate_only"
    assert spec["scenario_candidate_summary"]["selected_candidate_present"] is True
    assert spec["scenario_candidate_summary"]["selected_by"] == "scenario_candidates.preview_candidate"
    assert spec["scenario_candidate_summary"]["selection_unresolved_reasons"] == ["stack_unselected"]
    assert spec["request_ir"]["selection_decision"]["scenario"]["selected"] is False
    assert spec["request_ir"]["selection_decision"]["scenario"]["selected_candidate_present"] is True
    assert spec["request_ir"]["selection_decision"]["scenario"]["selection_state"] == "candidate_only"
    assert spec["request_ir"]["selection_decision"]["scenario"]["selected_by"] == "scenario_candidates.preview_candidate"
    assert spec["request_ir"]["selection_decision"]["scenario"]["unresolved_reasons"] == ["stack_unselected"]
    assert spec["request_ir"]["selection_decision"]["scenario"]["selected_scenario_id"] == (
        "family=open_redirect|stack=python/flask|topology=single_service"
    )
    assert spec["request_ir"]["selection_decision"]["scenario"]["top_oracle_mode"] == "stateful_text"
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
        "selected_family_support_missing",
        "selected_family_authority_thin",
    ]
    assert spec["exploit_oracle_summary"]["success_signature"] == "Exploit SUCCESS"
    assert spec["exploit_oracle_summary"]["negative_text_markers"] == ["Exploit FAILED"]
    assert spec["exploit_oracle_summary"]["negative_controls"] == [{"name": "benign-next", "expect_success": False, "payload": "/local"}]
    assert spec["exploit_oracle_summary"]["metamorphic"] == {
        "total": 1,
        "passed": 1,
        "rationale": "same-origin redirect stays non-exploit",
        "cases": [{"name": "same-origin", "payload": "/local", "expect_success": False}],
    }
    assert spec["exploit_oracle_summary"]["assertion_program"] == [
        {"op": "contains", "string": "Exploit SUCCESS"},
        {"op": "not_contains", "string": "Exploit FAILED"},
        {"op": "contains", "string": "FLAG{OPEN_REDIRECT_OK}"},
    ]
    assert staged["schema_version"] == "staged_synthesis@0.1"
    assert staged["stage_order"] == [
        "candidate_resolution",
        "design_brief",
        "runtime_plan",
        "executor_plan",
        "oracle_contract",
        "file_manifest",
    ]
    assert staged["candidate_resolution"]["selected_family"] == "open_redirect"
    assert staged["candidate_resolution"]["selected_topology"] == "single_service"
    assert staged["design_brief"]["working_family"] == "open_redirect"
    assert staged["design_brief"]["selected_topology"] == "single_service"
    assert staged["design_brief"]["selected_oracle_mode"] == "stateful_text"
    assert staged["design_brief"]["selected_oracle_source"] == "researcher_report.verification_spec"
    assert staged["design_brief"]["dependency_set"] == ["service"]
    assert staged["design_brief"]["required_roles"] == [
        "service_main",
        "poc_entry",
        "oracle_state_checks",
        "negative_control_cases",
        "metamorphic_cases",
    ]
    assert staged["design_brief"]["primary_focus"] == "stack_or_runtime_design"
    assert staged["runtime_plan"]["topology"] == "single_service"
    assert staged["executor_plan"]["service_port"] == 5000
    assert staged["executor_plan"]["validator"] == "executor_plan_contract"
    assert staged["oracle_contract"]["success_signature"] == "Exploit SUCCESS"
    assert staged["file_manifest"]["build_context_root"] == "."
    assert staged["file_manifest"]["service_entry_path"] == "app.py"
    assert staged["file_manifest"]["poc_entry_path"] == "poc.py"
    assert staged["file_manifest"]["validator"] == "file_manifest_contract"


def test_contract_enriched_request_ir_surfaces_provisional_and_joint_candidates(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="NAME-CUSTOM-THING",
        metadata_dir=tmp_path,
        workspace_dir=tmp_path,
        generator_mode="research_seed",
        bundle_slug="name-custom-thing",
        requirement={
            "vuln_id": "NAME-CUSTOM-THING",
            "vuln_name": "Custom Thing",
            "request_ir": {
                "request_label": "Custom Thing",
                "resolved_vuln_id": "NAME-CUSTOM-THING",
                "resolution_state": "synthetic_name",
                "pattern_seed_state": "preserved",
                "family_candidates": [
                    {"family": "template_injection", "source": "synthetic_name_preview", "confidence": "low"},
                    {"family": "xss", "source": "synthetic_name_preview", "confidence": "low"},
                ],
                "stack_candidates": [
                    {"stack_id": "python/flask", "source": "profile_prior", "confidence": "low"},
                ],
            },
            "policy": {"name_only_mode": "dynamic"},
        },
        researcher_report={
            "quality": "sufficient",
            "semantic_signature": {
                "input_vector": ["query parameter"],
                "sink": ["template rendering"],
                "exploit_precondition": ["server-side evaluation"],
            },
            "family_hypothesis_summary": {
                "top_family": "template_injection",
                "top_confidence": "low",
                "contradiction_count": 1,
                "contradictory_families": ["xss"],
                "ambiguous": True,
            },
        },
    )

    request_ir = payload["request_ir"]
    spec = payload["name_only_generation_spec"]

    assert request_ir["provisional_family"] == "template_injection"
    assert request_ir["primitive_hypotheses"] == [
        {"kind": "input_vector", "value": "query parameter", "source": "semantic_signature"},
        {"kind": "sink", "value": "template rendering", "source": "semantic_signature"},
        {"kind": "exploit_precondition", "value": "server-side evaluation", "source": "semantic_signature"},
    ]
    assert request_ir["topology_hypotheses"][0]["topology"] == "single_service"
    assert request_ir["scenario_candidates"][0]["scenario_id"].startswith("family=template_injection|stack=python/flask|")
    assert spec["provisional_family"] == "template_injection"
    assert spec["primitive_hypotheses"][0]["kind"] == "input_vector"
    assert spec["scenario_candidate_summary"]["candidate_count"] == 2
    assert spec["scenario_candidate_summary"]["top_family"] == "template_injection"
    assert spec["scenario_candidate_summary"]["top_stack_id"] == "python/flask"


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


def test_contract_name_only_generation_spec_derives_provisional_family_from_primitive_signature(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="NAME-CUSTOM-THING",
        metadata_dir=tmp_path,
        workspace_dir=tmp_path,
        generator_mode="research_seed",
        bundle_slug="name-custom-thing",
        requirement={
            "vuln_id": "NAME-CUSTOM-THING",
            "vuln_name": "Custom Thing",
            "language": "python",
            "framework": "flask",
            "request_ir": {
                "request_label": "Custom Thing",
                "resolved_vuln_id": "NAME-CUSTOM-THING",
                "resolution_state": "synthetic_name",
                "pattern_seed_state": "preserved",
                "stack_candidates": [
                    {"stack_id": "python/flask", "source": "explicit_requirement", "confidence": "high"},
                ],
            },
            "policy": {"name_only_mode": "dynamic"},
        },
        researcher_report={
            "quality": "sufficient",
            "semantic_signature": {
                "input_vector": ["next parameter"],
                "sink": ["redirect("],
                "exploit_precondition": ["external redirect"],
            },
        },
    )

    request_ir = payload["request_ir"]
    spec = payload["name_only_generation_spec"]

    assert request_ir["family_candidates"][0]["family"] == "open_redirect"
    assert request_ir["family_candidates"][0]["source"] == "primitive_signature"
    assert request_ir["family_candidates"][0]["confidence"] == "medium"
    assert request_ir["provisional_family"] == "open_redirect"
    assert request_ir["selection_decision"]["family"]["selected"] is False
    assert request_ir["selection_decision"]["family"]["source"] == "primitive_signature"
    assert request_ir["selection_decision"]["ready_for_materialization"] is False
    assert request_ir["scenario_candidates"][0]["family"] == "open_redirect"
    assert spec["provisional_family"] == "open_redirect"
    assert spec["family_candidate_summary"]["top_family"] == "open_redirect"
    assert spec["family_candidate_summary"]["top_source"] == "primitive_signature"


def test_contract_name_only_generation_spec_derives_runtime_dependency_from_primitive_family(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="NAME-CUSTOM-THING",
        metadata_dir=tmp_path,
        workspace_dir=tmp_path,
        generator_mode="research_seed",
        bundle_slug="name-custom-thing",
        requirement={
            "vuln_id": "NAME-CUSTOM-THING",
            "vuln_name": "Custom Thing",
            "language": "python",
            "framework": "flask",
            "request_ir": {
                "request_label": "Custom Thing",
                "resolved_vuln_id": "NAME-CUSTOM-THING",
                "resolution_state": "synthetic_name",
                "pattern_seed_state": "preserved",
                "stack_candidates": [
                    {"stack_id": "python/flask", "source": "explicit_requirement", "confidence": "high"},
                ],
            },
            "policy": {"name_only_mode": "dynamic"},
        },
        researcher_report={
            "quality": "sufficient",
            "semantic_signature": {
                "input_vector": ["query parameter"],
                "sink": ["SQL query execution"],
                "exploit_precondition": ["input concatenated into SQL sink"],
            },
        },
    )

    request_ir = payload["request_ir"]
    spec = payload["name_only_generation_spec"]

    assert request_ir["family_candidates"][0]["family"] == "sql_injection"
    assert request_ir["provisional_family"] == "sql_injection"
    assert request_ir["runtime_dependency_hypotheses"] == [
        {
            "kind": "db",
            "value": "sqlite",
            "source": "primitive_family_inference",
            "confidence": "low",
        }
    ]
    assert request_ir["oracle_hypotheses"] == [
        {
            "mode": "text_markers",
            "output_mode": "auto",
            "negative_control_present": True,
            "metamorphic_present": False,
            "source": "primitive_family_inference",
            "confidence": "low",
        }
    ]
    assert "db:sqlite" in request_ir["scenario_candidates"][0]["dependency_set"]
    assert request_ir["scenario_candidates"][0]["oracle_profile"]["source"] == "primitive_family_inference"
    assert request_ir["scenario_candidates"][0]["oracle_profile"]["mode"] == "text_markers"
    assert spec["runtime_dependency_hypotheses"] == [
        {
            "kind": "db",
            "value": "sqlite",
            "source": "primitive_family_inference",
            "confidence": "low",
        }
    ]
    assert spec["oracle_hypotheses"] == [
        {
            "mode": "text_markers",
            "output_mode": "auto",
            "negative_control_present": True,
            "metamorphic_present": False,
            "source": "primitive_family_inference",
            "confidence": "low",
        }
    ]
    assert payload["staged_synthesis"]["candidate_resolution"]["selected_topology"] == "single_service"
    assert payload["runtime_recipe"]["db"] == "sqlite"
    assert payload["runtime_recipe"]["db_source"] == "primitive_family_inference"
    assert payload["runtime_recipe"]["topology"] == "single_service"
    assert payload["runtime_recipe"]["topology_source"] == "primitive_family_inference"
    assert payload["executor_plan"]["db"] == "sqlite"
    assert payload["executor_plan"]["db_source"] == "primitive_family_inference"
    assert payload["executor_plan"]["topology"] == "single_service"
    assert payload["executor_plan"]["topology_source"] == "primitive_family_inference"
    assert payload["staged_synthesis"]["runtime_plan"]["db"] == "sqlite"
    assert payload["staged_synthesis"]["runtime_plan"]["db_source"] == "primitive_family_inference"
    assert payload["staged_synthesis"]["runtime_plan"]["topology"] == "single_service"
    assert payload["staged_synthesis"]["runtime_plan"]["topology_source"] == "primitive_family_inference"
    assert payload["staged_synthesis"]["design_brief"]["selected_topology"] == "single_service"
    assert payload["staged_synthesis"]["design_brief"]["selected_oracle_mode"] == "text_markers"
    assert payload["staged_synthesis"]["design_brief"]["selected_oracle_source"] == "primitive_family_inference"
    assert payload["staged_synthesis"]["design_brief"]["dependency_set"] == ["service", "db:sqlite"]
    assert payload["staged_synthesis"]["design_brief"]["required_roles"] == [
        "service_main",
        "poc_entry",
        "dependency_db",
        "negative_control_cases",
    ]
    assert payload["staged_synthesis"]["oracle_contract"]["source"] == "primitive_family_inference"
    assert payload["staged_synthesis"]["oracle_contract"]["mode"] == "text_markers"
    assert payload["staged_synthesis"]["oracle_contract"]["confidence"] == "low"
    assert payload["staged_synthesis"]["oracle_contract"]["negative_control_present"] is True
    assert payload["staged_synthesis"]["oracle_contract"]["metamorphic_present"] is False


def test_executor_plan_preserves_seed_files_from_runtime_graph() -> None:
    plan = _build_executor_plan(
        runtime_recipe={
            "topology": "single_service",
            "service_port": 8000,
            "network_mode": "none",
            "network_enabled": False,
            "requires_external_db": False,
            "service_entry": "app.py",
            "poc_entry": "poc.py",
            "seed_strategy": "sqlite_service_init",
            "seed_strategy_source": "runtime_recipe.seed_files+db",
        },
        runtime_graph={
            "healthchecks": [],
            "seed_files": ["schema.sql", "seed_data.sql"],
            "seed_strategy": "sqlite_service_init",
            "seed_strategy_source": "runtime_recipe.seed_files+db",
        },
        resolved={},
    )

    assert plan["seed_files"] == ["schema.sql", "seed_data.sql"]
    assert plan["seed_strategy"] == "sqlite_service_init"
    assert plan["seed_strategy_source"] == "runtime_recipe.seed_files+db"


def test_runtime_seed_files_detects_schema_role_entries() -> None:
    manifest = {
        "files": [
            {"path": "app.py", "role": "service_main", "content": "print('app')\n"},
            {"path": "schema.sql", "role": "schema", "content": "create table demo(id integer);\n"},
            {"path": "seed_data.sql", "role": "seed_data", "content": "insert into demo values (1);\n"},
        ]
    }

    assert _runtime_seed_files(manifest) == ["schema.sql", "seed_data.sql"]


def test_executor_plan_preserves_env_contract_from_runtime_graph() -> None:
    plan = _build_executor_plan(
        runtime_recipe={
            "topology": "single_service",
            "service_port": 8000,
            "network_mode": "none",
            "network_enabled": False,
            "requires_external_db": False,
            "service_entry": "app.py",
            "poc_entry": "poc.py",
        },
        runtime_graph={
            "healthchecks": [],
            "env_contract": [
                {"scope": "service", "name": "APP_PORT", "value": "8000"},
                {"scope": "service", "name": "DB_HOST", "value": "db-internal"},
            ],
        },
        resolved={},
    )

    assert plan["env_contract"] == [
        {"scope": "service", "name": "APP_PORT", "value": "8000"},
        {"scope": "service", "name": "DB_HOST", "value": "db-internal"},
    ]


def test_executor_plan_preserves_volume_contract_from_runtime_graph() -> None:
    plan = _build_executor_plan(
        runtime_recipe={
            "topology": "service_plus_sidecar",
            "service_port": 8000,
            "network_mode": "bridge",
            "network_enabled": True,
            "requires_external_db": True,
            "service_entry": "app.py",
            "poc_entry": "poc.py",
        },
        runtime_graph={
            "healthchecks": [],
            "volume_contract": [
                {
                    "scope": "sidecar:mysql-main",
                    "source": "workspace",
                    "target": "/seed-input",
                    "mode": "ro",
                }
            ],
            "volume_contract_source": "runtime_recipe.seed_files+seed_strategy",
        },
        resolved={},
    )

    assert plan["volume_contract"] == [
        {
            "scope": "sidecar:mysql-main",
            "source": "workspace",
            "target": "/seed-input",
            "mode": "ro",
        }
    ]
    assert plan["volume_contract_source"] == "runtime_recipe.seed_files+seed_strategy"


def test_executor_plan_preserves_network_contract_from_runtime_graph() -> None:
    plan = _build_executor_plan(
        runtime_recipe={
            "topology": "service_plus_sidecar",
            "service_port": 8000,
            "network_mode": "bridge",
            "network_enabled": True,
            "requires_external_db": True,
            "service_entry": "app.py",
            "poc_entry": "poc.py",
        },
        runtime_graph={
            "healthchecks": [],
            "network_contract": [
                {"scope": "service", "name": "DB_HOST", "alias": "db-internal"},
                {"scope": "sidecar:mysql-main", "alias": "db-internal"},
            ],
            "network_contract_source": "runtime_recipe.service_env+sidecars",
        },
        resolved={},
    )

    assert plan["network_contract"] == [
        {"scope": "service", "name": "DB_HOST", "alias": "db-internal"},
        {"scope": "sidecar:mysql-main", "alias": "db-internal"},
    ]
    assert plan["network_contract_source"] == "runtime_recipe.service_env+sidecars"


def test_runtime_graph_includes_sidecar_env_contract_entries() -> None:
    graph = _build_runtime_graph(
        runtime_recipe={
            "topology": "service_plus_sidecar",
            "service_port": 8000,
            "network_mode": "bridge",
            "network_enabled": True,
            "requires_external_db": True,
            "service_entry": "app.py",
            "poc_entry": "poc.py",
            "service_env": {"APP_PORT": "8000"},
            "sidecars": [
                {
                    "name": "mysql-main",
                    "type": "mysql",
                    "image": "mysql:8.0",
                    "env": {"MYSQL_DATABASE": "appdb", "MYSQL_USER": "appuser"},
                }
            ],
        },
        resolved={},
    )

    assert {"scope": "sidecar:mysql-main", "name": "MYSQL_DATABASE", "value": "appdb"} in graph["env_contract"]
    assert {"scope": "sidecar:mysql-main", "name": "MYSQL_USER", "value": "appuser"} in graph["env_contract"]


def test_runtime_graph_includes_network_contract_entries_for_sidecar_aliases() -> None:
    graph = _build_runtime_graph(
        runtime_recipe={
            "topology": "service_plus_sidecar",
            "service_port": 8000,
            "network_mode": "bridge",
            "network_enabled": True,
            "requires_external_db": True,
            "service_entry": "app.py",
            "poc_entry": "poc.py",
            "service_env": {"APP_PORT": "8000", "DB_HOST": "db-internal"},
            "sidecars": [
                {
                    "name": "mysql-main",
                    "type": "mysql",
                    "image": "mysql:8.0",
                    "aliases": ["db-internal"],
                }
            ],
        },
        resolved={},
    )

    assert {"scope": "service", "name": "DB_HOST", "alias": "db-internal"} in graph["network_contract"]
    assert {"scope": "sidecar:mysql-main", "alias": "db-internal"} in graph["network_contract"]
    assert graph["network_contract_source"] == "runtime_recipe.service_env+sidecars"


def test_runtime_graph_includes_volume_contract_entries_for_sidecar_sql_apply() -> None:
    graph = _build_runtime_graph(
        runtime_recipe={
            "topology": "service_plus_sidecar",
            "service_port": 8000,
            "network_mode": "bridge",
            "network_enabled": True,
            "requires_external_db": True,
            "service_entry": "app.py",
            "poc_entry": "poc.py",
            "seed_strategy": "sidecar_sql_apply",
            "seed_strategy_source": "runtime_recipe.seed_files+topology",
            "volume_contract": [
                {
                    "scope": "sidecar:mysql-main",
                    "source": "workspace",
                    "target": "/seed-input",
                    "mode": "ro",
                }
            ],
            "volume_contract_source": "runtime_recipe.seed_files+seed_strategy",
        },
        resolved={},
    )

    assert graph["volume_contract"] == [
        {
            "scope": "sidecar:mysql-main",
            "source": "workspace",
            "target": "/seed-input",
            "mode": "ro",
        }
    ]
    assert graph["volume_contract_source"] == "runtime_recipe.seed_files+seed_strategy"


def test_contract_name_only_generation_spec_keeps_primitive_family_background_when_request_resolution_is_authoritative(
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
                "pattern_seed_state": "preserved",
                "family_candidates": [
                    {"family": "open_redirect", "source": "request_resolution", "confidence": "high"},
                ],
                "stack_candidates": [
                    {"stack_id": "python/flask", "source": "profile_prior", "confidence": "low"},
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
        },
        researcher_report={
            "quality": "sufficient",
            "semantic_signature": {
                "input_vector": ["query parameter"],
                "sink": ["render_template_string"],
                "exploit_precondition": ["unescaped reflection"],
            },
        },
    )

    request_ir = payload["request_ir"]

    assert request_ir["family_candidates"][0]["family"] == "open_redirect"
    assert request_ir["family_candidates"][0]["source"] == "request_resolution"
    assert all(
        str(entry.get("source") or "").strip().lower() != "primitive_signature"
        for entry in request_ir["family_candidates"]
        if isinstance(entry, dict)
    )
    assert request_ir["selection_decision"]["family"]["selected"] is True
    assert request_ir["provisional_family"] is None


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


def test_contract_reads_seed_surface_from_mysql_compiler_manifest(tmp_path: Path) -> None:
    result = compile_manifest(
        sid="sid-registry-sqli-mysql-seed",
        requirement={
            "vuln_id": "CWE-89",
            "vuln_name": "SQL Injection",
            "pattern_id": "sqli-union-mysql",
            "runtime": {"db": "mysql", "allow_external_db": True},
            "executor": {
                "allow_network": True,
                "network_mode": "bridge",
                "sidecars": [
                    {
                        "name": "mysql-main",
                        "type": "mysql",
                        "aliases": ["db-internal"],
                        "env": {
                            "MYSQL_ROOT_PASSWORD": "rootpw",
                            "MYSQL_DATABASE": "sqliapp",
                            "MYSQL_USER": "sqli",
                            "MYSQL_PASSWORD": "sqli_pw",
                        },
                    }
                ],
            },
        },
        semantic_profile={
            "requested_name": "SQL Injection",
            "normalized_vuln_id": "CWE-89",
            "compiler_strategy": "sqli_string_concat_mysql",
            "compiler_supported": True,
            "scenario_shape": {"service_port": 5000},
            "stack_profile": {"language": "python", "framework": "flask"},
        },
    )
    assert result is not None
    (tmp_path / "generator_manifest.json").write_text(
        json.dumps({"manifest": result.manifest}, ensure_ascii=False),
        encoding="utf-8",
    )

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
                        "aliases": ["db-internal"],
                        "env": {
                            "MYSQL_ROOT_PASSWORD": "rootpw",
                            "MYSQL_DATABASE": "sqliapp",
                            "MYSQL_USER": "sqli",
                            "MYSQL_PASSWORD": "sqli_pw",
                        },
                    }
                ],
            },
        },
    )

    assert payload["runtime_recipe"]["seed_files"] == ["schema.sql"]
    assert payload["runtime_recipe"]["seed_strategy"] == "sidecar_sql_apply"
    assert payload["executor_plan"]["seed_files"] == ["schema.sql"]
    assert payload["executor_plan"]["seed_strategy"] == "sidecar_sql_apply"
    assert payload["exploit_oracle"]["negative_controls"] == [
        {"name": "literal-admin", "expect_success": False, "payload": "admin"}
    ]
    assert payload["exploit_oracle"]["metamorphic"]["cases"] == [
        {"name": "guest-user", "expect_success": False, "payload": "guest"}
    ]


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


def test_contract_runtime_recipe_preserves_sidecar_env_and_ready_probe(tmp_path: Path) -> None:
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
                        "env": {
                            "MYSQL_USER": "app_user",
                            "MYSQL_PASSWORD": "app_pw",
                        },
                        "ready_probe": {"type": "mysql", "retries": 5},
                    }
                ],
            },
        },
    )

    assert payload["runtime_recipe"]["sidecars"] == [
        {
            "name": "mysql-main",
            "type": "mysql",
            "image": "mysql:8.0",
            "aliases": ["db-internal"],
            "env": {
                "MYSQL_USER": "app_user",
                "MYSQL_PASSWORD": "app_pw",
            },
            "ready_probe": {"type": "mysql", "retries": 5},
        }
    ]
    assert payload["executor_plan"]["sidecars"] == payload["runtime_recipe"]["sidecars"]


def test_contract_runtime_recipe_can_synthesize_sidecars_from_manifest_target_hints(tmp_path: Path) -> None:
    (tmp_path / "generator_manifest.json").write_text(
        json.dumps(
            {
                "manifest": {
                    "files": [
                        {"path": "app.py", "role": "service_main", "content": "print('app')\n"},
                        {"path": "poc.py", "role": "poc_entry", "content": "print('poc')\n"},
                        {"path": "schema.sql", "role": "schema", "content": "create table demo(id integer);\n"},
                    ],
                    "run": {
                        "command": "python app.py",
                        "port": 5000,
                        "env": {
                            "DB_HOST": "db-internal",
                        },
                    },
                    "metadata": {
                        "target_db": "mysql",
                        "target_sidecars": ["mysql"],
                        "target_topology": "service_plus_sidecar",
                    },
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="NAME-CUSTOM-SQLI",
        metadata_dir=tmp_path,
        workspace_dir=tmp_path,
        generator_mode="synthesis",
        bundle_slug="name-custom-sqli",
        requirement={
            "vuln_id": "NAME-CUSTOM-SQLI",
            "vuln_name": "Custom SQLi",
            "policy": {"name_only_mode": "dynamic"},
        },
    )

    recipe = payload["runtime_recipe"]
    assert recipe["db"] == "mysql"
    assert recipe["requires_external_db"] is True
    assert recipe["topology"] == "service_plus_sidecar"
    assert recipe["network_enabled"] is True
    assert recipe["network_mode"] == "bridge"
    assert recipe["network_enabled_source"] == "runtime_topology_requires_network"
    assert recipe["network_mode_source"] == "runtime_topology_requires_network"
    assert recipe["sidecars_source"] == "generator_manifest.metadata.target_sidecars"
    assert recipe["sidecar_start_order"] == ["mysql-main"]
    assert recipe["sidecar_start_order_source"] == "generator_manifest.metadata.target_sidecars"
    assert recipe["service_env_source"] == "runtime_hint_sidecar_defaults"
    assert recipe["service_env"] == {
        "DB_HOST": "db-internal",
        "DB_PORT": "3306",
        "DB_USER": "sqli",
        "DB_PASSWORD": "sqli_pw",
        "DB_NAME": "sqliapp",
        "APP_PORT": "5000",
    }
    assert recipe["seed_files"] == ["schema.sql"]
    assert recipe["seed_strategy"] == "sidecar_sql_apply"
    assert recipe["seed_strategy_source"] == "runtime_recipe.seed_files+topology"
    assert recipe["sidecars"] == [
        {
            "name": "mysql-main",
            "type": "mysql",
            "image": "mysql:8.0",
            "aliases": ["db-internal"],
            "env": {
                "MYSQL_ROOT_PASSWORD": "sqli_root_pw",
                "MYSQL_DATABASE": "sqliapp",
                "MYSQL_USER": "sqli",
                "MYSQL_PASSWORD": "sqli_pw",
            },
            "ready_probe": {"type": "mysql", "retries": 10},
        }
    ]
    graph = payload["runtime_graph"]
    assert graph["topology"] == "service_plus_sidecar"
    assert graph["network"]["enabled"] is True
    assert graph["network"]["mode"] == "bridge"
    assert graph["seed_strategy"] == "sidecar_sql_apply"
    assert graph["seed_strategy_source"] == "runtime_recipe.seed_files+topology"
    assert any(node["id"] == "sidecar:mysql-main" for node in graph["nodes"])
    sidecar_node = next(node for node in graph["nodes"] if node["id"] == "sidecar:mysql-main")
    assert sidecar_node["startup_order_index"] == 1
    assert sidecar_node["env"] == {
        "MYSQL_ROOT_PASSWORD": "sqli_root_pw",
        "MYSQL_DATABASE": "sqliapp",
        "MYSQL_USER": "sqli",
        "MYSQL_PASSWORD": "sqli_pw",
    }
    assert sidecar_node["ready_probe"] == {"type": "mysql", "retries": 10}
    sidecar_edge = next(edge for edge in graph["edges"] if edge["to"] == "sidecar:mysql-main")
    assert sidecar_edge["startup_order_index"] == 1
    assert sidecar_edge["startup_after"] is None
    assert graph["sidecars_source"] == "generator_manifest.metadata.target_sidecars"
    assert graph["sidecar_start_order"] == ["mysql-main"]
    assert graph["sidecar_start_order_source"] == "generator_manifest.metadata.target_sidecars"
    assert graph["service_env_source"] == "runtime_hint_sidecar_defaults"
    assert graph["network_enabled_source"] == "runtime_topology_requires_network"
    assert graph["network_mode_source"] == "runtime_topology_requires_network"
    plan = payload["executor_plan"]
    assert plan["requires_external_db"] is True
    assert plan["sidecars"] == recipe["sidecars"]
    assert plan["seed_files"] == ["schema.sql"]
    assert plan["seed_strategy"] == "sidecar_sql_apply"
    assert plan["seed_strategy_source"] == "runtime_recipe.seed_files+topology"
    assert plan["network_enabled"] is True
    assert plan["network_mode"] == "bridge"
    assert plan["sidecars_source"] == "generator_manifest.metadata.target_sidecars"
    assert plan["sidecar_start_order"] == ["mysql-main"]
    assert plan["sidecar_start_order_source"] == "generator_manifest.metadata.target_sidecars"
    assert plan["service_env_source"] == "runtime_hint_sidecar_defaults"
    assert plan["network_enabled_source"] == "runtime_topology_requires_network"
    assert plan["network_mode_source"] == "runtime_topology_requires_network"
    assert payload["service_env"] == recipe["service_env"]
    assert payload["resolved"]["service_env"] == recipe["service_env"]


def test_contract_runtime_recipe_keeps_explicit_network_cap_when_executor_disables_network(tmp_path: Path) -> None:
    (tmp_path / "generator_manifest.json").write_text(
        json.dumps(
            {
                "manifest": {
                    "files": [
                        {"path": "app.py", "role": "service_main", "content": "print('app')\n"},
                        {"path": "poc.py", "role": "poc_entry", "content": "print('poc')\n"},
                    ],
                    "run": {"command": "python app.py", "port": 5000, "env": {"DB_HOST": "db-internal"}},
                    "metadata": {
                        "target_db": "postgres",
                        "target_sidecars": ["postgres"],
                        "target_topology": "service_plus_sidecar",
                    },
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="NAME-CUSTOM-SQLI",
        metadata_dir=tmp_path,
        workspace_dir=tmp_path,
        generator_mode="synthesis",
        bundle_slug="name-custom-sqli",
        requirement={
            "vuln_id": "NAME-CUSTOM-SQLI",
            "vuln_name": "Custom SQLi",
            "executor": {"allow_network": False, "network_mode": "none"},
        },
    )

    recipe = payload["runtime_recipe"]
    assert recipe["network_enabled"] is False
    assert recipe["network_mode"] == "none"
    assert recipe["network_enabled_source"] == "requirement.executor.allow_network"
    assert recipe["network_mode_source"] == "requirement.executor.network_mode"


def test_contract_runtime_recipe_marks_sqlite_seed_strategy(tmp_path: Path) -> None:
    (tmp_path / "generator_manifest.json").write_text(
        json.dumps(
            {
                "manifest": {
                    "files": [
                        {
                            "path": "app.py",
                            "role": "service_main",
                            "content": "import sqlite3\nconn = sqlite3.connect('/tmp/app.db')\n",
                        },
                        {"path": "poc.py", "role": "poc_entry", "content": "print('poc')\n"},
                        {"path": "schema.sql", "role": "schema", "content": "create table demo(id integer);\n"},
                    ],
                    "run": {"command": "python app.py", "port": 5000},
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="CWE-89",
        metadata_dir=tmp_path,
        workspace_dir=tmp_path,
        generator_mode="synthesis",
        bundle_slug="cwe-89",
        requirement={"runtime": {"db": "sqlite"}},
    )

    assert payload["runtime_recipe"]["seed_strategy"] == "sqlite_service_init"
    assert payload["runtime_graph"]["seed_strategy"] == "sqlite_service_init"
    assert payload["executor_plan"]["seed_strategy"] == "sqlite_service_init"


def test_runtime_graph_surfaces_startup_after_for_multiple_sidecars() -> None:
    graph = _build_runtime_graph(
        runtime_recipe={
            "language": "python",
            "framework": "flask",
            "transport": "http",
            "service_entry": "app.py",
            "poc_entry": "poc.py",
            "service_port": 8000,
            "topology": "service_plus_sidecar",
            "network_mode": "bridge",
            "network_enabled": True,
            "sidecars": [
                {"name": "mysql-main", "type": "mysql", "image": "mysql:8.0"},
                {"name": "redis-main", "type": "redis", "image": "redis:7"},
            ],
            "sidecar_start_order": ["mysql-main", "redis-main"],
        },
        resolved={"service_port": 8000},
    )

    mysql_node = next(node for node in graph["nodes"] if node["id"] == "sidecar:mysql-main")
    redis_node = next(node for node in graph["nodes"] if node["id"] == "sidecar:redis-main")
    assert mysql_node["startup_order_index"] == 1
    assert redis_node["startup_order_index"] == 2
    mysql_edge = next(edge for edge in graph["edges"] if edge["to"] == "sidecar:mysql-main")
    redis_edge = next(edge for edge in graph["edges"] if edge["to"] == "sidecar:redis-main")
    assert mysql_edge["startup_order_index"] == 1
    assert mysql_edge["startup_after"] is None
    assert redis_edge["startup_order_index"] == 2
    assert redis_edge["startup_after"] == "sidecar:mysql-main"


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
    assert request_ir["selection_decision"]["scenario"]["selected"] is True
    assert request_ir["selection_decision"]["scenario"]["selected_candidate_present"] is True
    assert request_ir["selection_decision"]["scenario"]["selection_state"] == "selected"
    assert request_ir["selection_decision"]["scenario"]["selected_by"] == "scenario_candidates.explicit_selected"
    assert request_ir["selection_decision"]["scenario"]["selected_topology"] == "single_service"
    assert request_ir["selection_decision"]["scenario"]["selected_oracle_mode"] == "stateful_text"
    assert request_ir["selection_decision"]["ready_for_materialization"] is True
    assert request_ir["selection_decision"]["open_world_evidence_ready"] is False
    assert executor_plan["service_port"] == 5000
    assert executor_plan.get("health_path") in {None, "/health"}
    assert executor_plan["stack_selection"]["selected_stack_id"] == "python/flask"
    trace = payload["selection_branch_trace"]
    assert trace["schema_version"] == "selection_branch_trace@0.1"
    assert trace["controller_ready"] is True
    assert trace["open_world_evidence_ready"] is False
    assert trace["selected_branch"]["family"]["selected_value"] == "open_redirect"
    assert trace["selected_branch"]["family"]["materialized_value"] == "open_redirect"
    assert trace["selected_branch"]["family"]["aligned"] is True
    assert trace["selected_branch"]["stack"]["selected_value"] == "python/flask"
    assert trace["selected_branch"]["stack"]["materialized_value"] == "python/flask"
    assert trace["selected_branch"]["stack"]["aligned"] is True
    assert trace["selected_branch"]["scenario"]["selected_value"] == "family=open_redirect|stack=python/flask|topology=single_service"
    assert trace["selected_branch"]["scenario"]["aligned"] is True
    assert trace["selected_branch"]["topology"]["selected_value"] == "single_service"
    assert trace["selected_branch"]["topology"]["materialized_value"] == "single_service"
    assert trace["selected_branch"]["oracle_mode"]["selected_value"] == "stateful_text"
    assert trace["selected_branch"]["oracle_mode"]["materialized_value"] == "stateful_text"
    assert trace["branch_aligned"] is True
    assert trace["candidate_context"]["selection_state"] == "selected"
    assert trace["candidate_context"]["selected_by"] == "scenario_candidates.explicit_selected"
    assert trace["materialization_bundle"]["service_entry_path"] == "app.py"
    assert trace["materialization_bundle"]["poc_entry_path"] == "poc.py"
    assert trace["materialization_bundle"]["build_context_root"] == "."
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
        "selected_scenario_support_missing",
        "selected_scenario_authority_thin",
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
                "llm_provider_attempted": True,
                "llm_provider_succeeded": False,
                "llm_failure_class": "provider_disabled",
                "llm_execution": {
                    "attempt_scope": "observed",
                    "provider_attempted": True,
                    "provider_succeeded": False,
                    "stub_fallback": True,
                    "fixture_used": False,
                    "path_class": "degraded",
                    "cache_mode": "none",
                    "prompt_contracts": [{"name": "synthesis_manifest", "version": "build_synthesis_prompt@1"}],
                    "retry_budget": {"candidate_budget": 3, "guard_autofix_max_attempts": 2},
                    "last_error_class": "provider_disabled",
                },
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
    assert payload["llm_provider_attempted"] is True
    assert payload["llm_provider_succeeded"] is False
    assert payload["llm_failure_class"] == "provider_disabled"
    assert payload["llm_execution"]["path_class"] == "degraded"
    assert payload["llm_execution"]["prompt_contracts"][0]["name"] == "synthesis_manifest"
    assert payload["llm_execution"]["retry_budget"]["candidate_budget"] == 3
    assert payload["provenance"]["source"] == "generator_manifest"
    assert payload["provenance"]["fallback_class"] == "generic_unsupported_family"
    assert payload["provenance"]["llm_execution"]["path_class"] == "degraded"


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
                "llm_provider_attempted": False,
                "llm_provider_succeeded": False,
                "llm_failure_class": "",
                "llm_execution": {
                    "attempt_scope": "observed",
                    "provider_attempted": False,
                    "provider_succeeded": False,
                    "stub_fallback": False,
                    "fixture_used": False,
                    "path_class": "not_executed",
                    "cache_mode": "none",
                    "prompt_contracts": [{"name": "generator_plan", "version": "build_generator_prompt@1"}],
                },
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
    assert payload["llm_provider_attempted"] is False
    assert payload["llm_provider_succeeded"] is False
    assert payload["llm_execution"]["path_class"] == "not_executed"
    assert payload["llm_execution"]["prompt_contracts"][0]["name"] == "generator_plan"
    assert payload["provenance"]["template_id"] == "flask_sqlite_raw"
    assert payload["provenance"]["source"] == "generator_template"
    assert payload["provenance"]["llm_execution"]["path_class"] == "not_executed"
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
