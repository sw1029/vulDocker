from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.e2e import run_case


def test_case_requires_docker_skips_capability_check_fail_closed_cases() -> None:
    assert run_case._case_requires_docker({"manifest": {"failure": {"stage": "CAPABILITY_CHECK"}}}) is False
    assert run_case._case_requires_docker({"manifest": {"failure": {"stage": "RESEARCH"}}}) is False
    assert run_case._case_requires_docker({"manifest": {"failure": {"stage": "EXECUTOR"}}}) is True


def test_load_manifest_summary_surfaces_name_only_and_quality_fields(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-summary-surface"
    metadata_dir = tmp_path / "metadata" / sid
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "reviewer_report.json").write_text(
        json.dumps({"blocking_bundles": [], "issues_sample": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    (metadata_dir / "manifest.json").write_text(
        json.dumps(
            {
                "sid": sid,
                "pipeline_result": "success",
                "sid_inputs": {"components": {"execution_salt": "salt-summary-surface"}},
                "request_ir": {
                    "request_label": "Open Redirect",
                    "resolution_state": "catalog_alias",
                    "pattern_seed_state": "preserved",
                    "name_driven": True,
                    "resolution_confidence": "high",
                    "resolution_match_class": "catalog_alias",
                    "abstain_reason": "ambiguous_family_hypothesis",
                    "identifier_candidates": [
                        {"vuln_id": "NAME-OPEN-REDIRECT", "confidence": "high"},
                        {"vuln_id": "CWE-601", "confidence": "low"},
                    ],
                    "family_candidates": [
                        {"family": "open_redirect", "confidence": "high", "evidence_ids": ["evidence:1"]},
                        {"family": "xss", "confidence": "low"},
                    ],
                    "stack_candidates": [{"stack_id": "python/flask", "confidence": "low"}],
                    "negative_hypotheses": [{"family": "xss", "source": "researcher_contradiction"}],
                    "evidence_ids": ["evidence:1"],
                    "selection_decision": {
                        "family": {
                            "selected": True,
                            "selected_family": "open_redirect",
                            "evidence_backed": True,
                            "support_count": 1,
                            "support_by_source_authority": {"high": 1},
                            "high_or_medium_authority_support": True,
                        },
                        "stack": {
                            "selected": True,
                            "selected_stack_id": "python/flask",
                            "evidence_backed": True,
                            "support_count": 1,
                            "support_by_source_authority": {"high": 1},
                            "high_or_medium_authority_support": True,
                        },
                        "ready_for_materialization": True,
                        "open_world_evidence_ready": True,
                    },
                },
                "artifact_quality_summary": {
                    "bundle_count": 1,
                    "average_score": 8.0,
                    "by_qualitative_tier": {"thin_or_incomplete": 1},
                    "oracle_high_nonhigh_band_bundles": 0,
                    "thin_fallback_demo_bundles": 0,
                    "native_operator_ready_bundles": 0,
                },
                "support_promotion": {
                    "eligible_bundles": 0,
                    "all_eligible": False,
                    "reasons": [
                        "name-open-redirect: strict_open_world:strict_minimal_dynamic_fallback",
                        "name-open-redirect: selection_evidence:open_world_not_ready",
                        "name-open-redirect: generation_path:not_live_positive",
                        "name-open-redirect: generation_path:provider_disabled",
                    ],
                },
                "open_world_readiness_summary": {
                    "bundle_count": 1,
                    "ready_bundles": 0,
                    "not_ready_bundles": 1,
                    "all_ready": False,
                    "by_blocker": {
                        "strict_open_world_gate": 1,
                        "generation_path_not_live_positive": 1,
                        "generation_path_provider_disabled": 1,
                        "stack_defaulted": 1,
                        "selection_open_world_evidence_not_ready": 1,
                    },
                },
                "boundedness_summary": {
                    "catalog_entries": 12,
                    "family_hint_families": 12,
                    "scaffold_stack_pool": 2,
                    "compiler_strategy_count": 13,
                    "closed_vocabulary_family_discovery": True,
                    "executor_multi_primary_supported": False,
                },
                "request_ir_summary": {
                    "bundle_count": 1,
                    "name_driven_bundles": 1,
                    "evidence_backed_bundles": 1,
                    "selection_ready_bundles": 1,
                    "selected_family_bundles": 1,
                    "selected_stack_bundles": 1,
                    "abstain_signaled_bundles": 1,
                    "multi_identifier_candidate_bundles": 1,
                    "ambiguous_family_candidate_bundles": 1,
                    "ambiguous_stack_candidate_bundles": 0,
                    "resolved_ambiguous_family_candidate_bundles": 1,
                    "resolved_ambiguous_stack_candidate_bundles": 0,
                    "unresolved_ambiguous_family_candidate_bundles": 0,
                    "unresolved_ambiguous_stack_candidate_bundles": 0,
                    "negative_hypothesis_bundles": 1,
                    "avg_identifier_candidate_count": 2.0,
                    "avg_family_candidate_count": 2.0,
                    "avg_stack_candidate_count": 1.0,
                    "avg_negative_hypothesis_count": 1.0,
                    "by_resolution_state": {"catalog_alias": 1},
                    "by_resolution_match_class": {"catalog_alias": 1},
                    "by_resolution_confidence": {"high": 1},
                },
                "selection_readiness_summary": {
                    "bundle_count": 1,
                    "family_selected_bundles": 1,
                    "stack_selected_bundles": 1,
                    "ready_for_materialization_bundles": 1,
                    "open_world_evidence_ready_bundles": 1,
                    "family_evidence_backed_bundles": 1,
                    "stack_evidence_backed_bundles": 1,
                    "family_high_or_medium_authority_support_bundles": 1,
                    "stack_high_or_medium_authority_support_bundles": 1,
                    "resolved_ambiguous_family_bundles": 1,
                    "resolved_ambiguous_stack_bundles": 0,
                    "unresolved_ambiguous_family_bundles": 0,
                    "unresolved_ambiguous_stack_bundles": 0,
                    "by_family_source": {},
                    "by_stack_source": {},
                    "by_family_confidence": {},
                    "by_stack_confidence": {},
                    "by_stack_basis": {},
                    "by_family_support_authority": {"high": 1},
                    "by_stack_support_authority": {"high": 1},
                },
                "performance": {
                    "total_duration_s": 7.3,
                    "retry_count": 1,
                    "search_cache_hit_count": 2,
                    "search_cache_miss_count": 1,
                    "search_cache_reuse_ratio": 0.667,
                    "search_planned_query_count": 4,
                    "search_executed_query_count": 3,
                    "search_early_stop_triggered": True,
                    "by_stage": {
                        "RESEARCH": {"count": 1, "duration_s": 3.2, "skipped": 0},
                        "GENERATOR": {"count": 1, "duration_s": 1.4, "skipped": 0},
                    },
                },
                "research_retry_budget": {
                    "controller_loop_current": 1,
                    "controller_loop_max": 3,
                    "researcher_report_runs": 1,
                },
                "research_timeout_budget": {"llm_request_timeout_s": 9.5, "search_timeout_s": 8.0},
                "research_cost_budget": {"configured_cost_budget_usd": 0.25},
                "generation_retry_budget": {
                    "controller_loop_current": 1,
                    "controller_loop_max": 3,
                    "planned_candidate_budget": 1,
                },
                "generation_timeout_budget": {"llm_request_timeout_s": 9.5},
                "generation_cost_budget": {"configured_cost_budget_usd": 0.25},
                "reviewer_retry_budget": {},
                "reviewer_timeout_budget": {},
                "reviewer_cost_budget": {},
                "evidence_graph_summary": {
                    "bundle_count": 1,
                    "graph_present_bundles": 1,
                    "average_node_count": 3.0,
                    "average_edge_count": 2.0,
                    "by_node_kind": {"request": 1, "query": 1, "evidence": 1},
                    "by_source_authority": {"high": 1},
                },
                "generalization_summary": {
                    "bundle_count": 1,
                    "positive_generalization_bundles": 0,
                    "realized_bundles": 1,
                    "hypothetical_bundles": 0,
                    "fully_validated_bundles": 0,
                    "realized_positive_generalization_bundles": 0,
                    "fully_validated_positive_generalization_bundles": 0,
                    "lower_bound_dependent_bundles": 1,
                    "by_class": {"real_free_form_curated_lower_bound": 1},
                },
                "open_world_selection_source": "request_resolution",
                "open_world_selection_evidence_ready": True,
                "template_dependence_summary": {"bundle_count": 1, "minimal_dynamic_bundles": 1},
                "open_world_summary": {
                    "bundle_count": 1,
                    "positive_open_world_bundles": 0,
                    "realized_bundles": 1,
                    "hypothetical_bundles": 0,
                    "fully_validated_bundles": 0,
                    "realized_positive_open_world_bundles": 0,
                    "fully_validated_positive_open_world_bundles": 0,
                },
                "runtime_surface_summary": {
                    "bundle_count": 1,
                    "realized_bundles": 1,
                    "hypothetical_bundles": 0,
                    "network_enabled_bundles": 0,
                    "sidecar_bundles": 0,
                    "by_topology": {"single_service": 1},
                },
                "stack_dependence_summary": {
                    "bundle_count": 1,
                    "repo_prior_bounded_bundles": 1,
                    "stack_defaulted_bundles": 1,
                    "evidence_backed_bundles": 1,
                },
                "open_world_readiness": {
                    "ready": False,
                    "blockers": [
                        "strict_open_world_gate",
                        "open_world_non_positive",
                        "artifact_quality_below_high",
                        "stack_defaulted",
                        "selection_open_world_evidence_not_ready",
                        "name_only_intent_not_met",
                    ],
                },
                "family_dependence_summary": {
                    "bundle_count": 1,
                    "by_class": {"semantic_signature_bounded": 1},
                    "evidence_backed_bundles": 1,
                    "candidate_evidence_backed_bundles": 1,
                    "negative_hypothesis_bundles": 1,
                    "by_resolution_confidence": {"high": 1},
                    "by_resolution_basis": {"catalog_alias": 1},
                },
                "intent_satisfaction_summary": {"bundle_count": 1, "by_status": {"degraded_dynamic_success": 1}},
                "name_only_outcome_summary": {
                    "bundle_count": 1,
                    "name_only_bundles": 1,
                    "intent_met_bundles": 0,
                    "partial_bundles": 1,
                    "abstained_bundles": 0,
                    "fail_closed_bundles": 0,
                    "failed_bundles": 0,
                    "by_decision": {"partial": 1},
                    "by_next_required_step": {"execution": 1},
                    "by_abstain_reason": {},
                    "by_terminal_failure_class": {},
                    "by_stage_ceiling": {"generated": 1},
                },
                "name_only_planning_summary": {
                    "bundle_count": 1,
                    "name_only_bundles": 1,
                    "with_planning_focus_bundles": 1,
                    "by_primary_focus": {"stack_or_runtime_design": 1},
                    "by_focus": {"stack_or_runtime_design": 1, "evidence_authority": 1},
                    "by_reason_token": {
                        "stack_defaulted": 1,
                        "stack_ambiguous": 1,
                        "family_candidate_evidence_missing": 1,
                    },
                },
                "staged_synthesis_summary": {
                    "bundle_count": 1,
                    "staged_bundles": 1,
                    "with_failure_stage_bundles": 1,
                    "stage_aware_recovery_bundles": 1,
                    "by_failure_stage": {"runtime_plan": 1},
                    "by_failure_stage_reason": {"runtime_plan_mismatch": 1},
                    "by_recovery_strategy": {"runtime_plan": 1},
                    "by_selected_topology": {"single_service": 1},
                },
                "dynamic_eval_summary": {"bundle_count": 1, "attempted_bundles": 1},
                "completion_summary": {
                    "bundle_count": 1,
                    "generated_bundles": 1,
                    "executed_bundles": 0,
                    "verified_bundles": 0,
                    "reviewed_bundles": 0,
                    "fully_validated_bundles": 0,
                    "by_stage_ceiling": {"generated": 1},
                },
                "semantic_guided_selection_source": "request_resolution",
                "semantic_guided_ambiguous": True,
                "service_port": 9000,
                "service_base_url": "http://127.0.0.1:9000",
                "service_port_source": "executor_plan.service_port",
                "service_entry_source": "executor_plan.service_entry",
                "poc_entry": "poc.py",
                "poc_entry_source": "executor_plan.poc_entry",
                "poc_cmd": "python poc.py --base-url {{base_url}}",
                "poc_cmd_source": "resolved_contract.poc_cmd",
                "base_url_source": "executor_plan.base_url",
                "health_path_source": "runtime_graph.healthchecks[service]",
                "healthchecks": [{"node": "service", "path": "/ready", "port": 9000, "transport": "http"}],
                "healthchecks_source": "runtime_graph.healthchecks",
                "service_env_runtime": {
                    "APP_PORT": "9000",
                    "DB_HOST": "db-internal",
                    "DB_NAME": "sqliapp",
                    "DB_USER": "sqli",
                    "DB_PASSWORD": "sqli_pw",
                    "DB_PORT": "3306",
                },
                "allow_network": True,
                "service_env_source": "runtime_hint_sidecar_defaults",
                "sidecars_source": "generator_manifest.metadata.target_sidecars",
                "network_mode": "bridge",
                "allow_network_source": "runtime_topology_requires_network",
                "network_mode_source": "runtime_topology_requires_network",
                "executed_sidecars": [
                    {
                        "name": "mysql-main",
                        "type": "mysql",
                        "container": "sid-summary-surface-name-open-redirect-mysql-main",
                        "image": "mysql:8.0",
                        "aliases": ["db-internal"],
                        "start_order_index": 1,
                        "seed_mount_target": "/seed-input",
                        "seed_files_applied": ["schema.sql"],
                    }
                ],
                "sidecar_start_order": ["mysql-main"],
                "sidecar_start_order_source": "generator_manifest.metadata.target_sidecars",
                "network_contract": [
                    {"scope": "service", "name": "DB_HOST", "alias": "db-internal"},
                    {"scope": "sidecar:mysql-main", "alias": "db-internal"},
                ],
                "network_contract_source": "runtime_recipe.service_env+sidecars",
                "seed_strategy": "sidecar_sql_apply",
                "seed_strategy_source": "runtime_recipe.seed_files+topology",
                "seed_files": ["schema.sql"],
                "seed_files_source": "executor_plan.seed_files",
                "volume_contract": [
                    {
                        "scope": "sidecar:mysql-main",
                        "source": "workspace",
                        "target": "/seed-input",
                        "mode": "ro",
                    }
                ],
                "volume_contract_source": "runtime_recipe.seed_files+seed_strategy",
                "seed_apply_attempted": True,
                "seed_apply_completed": True,
                "seed_files_applied_total": 1,
                "seed_mount_targets": ["/seed-input"],
                "runtime_recipe": {"language": "python", "framework": "flask", "hypothetical": False},
                "runtime_graph": {"topology": "single_service", "nodes": [{"id": "service"}], "hypothetical": False},
                "executor_plan": {"service_port": 5000, "health_path": "/health", "topology": "single_service"},
                "evidence_graph": {
                    "schema_version": "evidence_graph@0.1",
                    "node_count": 3,
                    "edge_count": 2,
                    "nodes": [{"id": "evidence:1", "kind": "evidence", "source_authority": "high"}],
                },
                "artifact_quality": {
                    "band": "medium",
                    "oracle_execution_parity": "partial",
                    "oracle_execution_attempted": True,
                    "qualitative_tier": "thin_or_incomplete",
                    "qualitative_review": "artifact remains thin or incomplete for operator-facing use",
                },
                "stack_dependence": {
                    "class": "repo_prior_bounded",
                    "stack_source": "profile_prior",
                    "stack_defaulted": True,
                    "working_stack_evidence_backed": True,
                },
                "family_dependence": {
                    "class": "semantic_signature_bounded",
                    "selection_source": "semantic_signature",
                    "working_family_evidence_backed": True,
                    "candidate_evidence_backed": True,
                    "candidate_evidence_ids": ["evidence:1"],
                    "resolution_confidence": "high",
                    "resolution_basis": "catalog_alias",
                    "negative_hypothesis_count": 1,
                },
                "dynamic_eval": {"enabled": True, "status": "degraded_success"},
                "intent_satisfaction": {"mode": "dynamic", "status": "degraded_dynamic_success"},
                "name_only_outcome": {
                    "request_kind": "name_only",
                    "mode": "dynamic",
                    "decision": "partial",
                    "decision_reason": "degraded_dynamic_success",
                    "abstain_reason": None,
                    "terminal_failure_class": None,
                    "closure_source": "degraded_deterministic_fallback",
                    "allowed_by_execution_contract": True,
                    "satisfies_intent_contract": False,
                    "stage_ceiling": "generated",
                    "fully_validated": False,
                    "next_required_step": "execution",
                    "selection_ready_for_materialization": True,
                    "selection_open_world_evidence_ready": True,
                    "family_selected": True,
                    "selected_family": "open_redirect",
                    "family_evidence_backed": True,
                    "family_support_count": 1,
                    "stack_selected": True,
                    "selected_stack_id": "python/flask",
                    "stack_evidence_backed": True,
                    "stack_support_count": 1,
                    "open_world_class": "semantic_guided_minimal_dynamic",
                    "strict_open_world_class": "strict_minimal_dynamic_fallback",
                    "stack_dependence_class": "repo_prior_bounded",
                    "family_dependence_class": "semantic_signature_bounded",
                },
                "completion_state": {
                    "generated": True,
                    "executed": False,
                    "run_passed": False,
                    "verified": False,
                    "verify_pass": None,
                    "reviewed": False,
                    "review_ready": False,
                    "fully_validated": False,
                    "stage_ceiling": "generated",
                    "generation_origin": "deterministic_fallback",
                },
                "stage_ceiling": "generated",
                "fully_validated": False,
                "name_only_decision": "partial",
                "name_only_next_required_step": "execution",
                "name_only_primary_focus": "stack_or_runtime_design",
                "name_only_planning_focus": {
                    "primary_focus": "stack_or_runtime_design",
                    "focuses": ["stack_or_runtime_design", "evidence_authority"],
                    "by_focus": {
                        "stack_or_runtime_design": ["stack_defaulted", "stack_ambiguous"],
                        "evidence_authority": ["family_candidate_evidence_missing"],
                    },
                    "reason_tokens": [
                        "stack_defaulted",
                        "stack_ambiguous",
                        "family_candidate_evidence_missing",
                    ],
                },
                "staged_synthesis": {
                    "schema_version": "staged_synthesis@0.1",
                    "stage_order": ["candidate_resolution", "design_brief", "runtime_plan", "oracle_contract"],
                    "candidate_resolution": {"selected_topology": "single_service"},
                },
                "selection_branch_trace": {
                    "schema_version": "selection_branch_trace@0.1",
                    "controller_ready": True,
                    "open_world_evidence_ready": True,
                    "branch_aligned": True,
                    "selected_branch": {
                        "family": {"selected_value": "open_redirect", "materialized_value": "open_redirect", "aligned": True},
                        "stack": {"selected_value": "python/flask", "materialized_value": "python/flask", "aligned": True},
                        "scenario": {
                            "selected_value": "family=open_redirect|stack=python/flask|topology=single_service",
                            "materialized_value": "family=open_redirect|stack=python/flask|topology=single_service",
                            "aligned": True,
                        },
                        "topology": {"selected_value": "single_service", "materialized_value": "single_service", "aligned": True},
                        "oracle_mode": {"selected_value": "stateful_text", "materialized_value": "stateful_text", "aligned": True},
                    },
                    "materialization_bundle": {
                        "runtime_topology": "single_service",
                        "executor_topology": "single_service",
                        "service_entry_path": "app.py",
                        "poc_entry_path": "poc.py",
                        "dockerfile_path": "Dockerfile",
                        "build_context_root": ".",
                        "dependency_manifest_paths": ["requirements.txt"],
                        "seed_asset_paths": ["schema.sql"],
                        "required_roles": ["service_main", "poc_entry"],
                    },
                    "candidate_context": {
                        "scenario_candidate_count": 2,
                        "selected_candidate_present": True,
                        "selection_state": "selected",
                        "selected_by": "scenario_candidates.explicit_selected",
                        "unresolved_reasons": [],
                        "rejected_scenario_ids_sample": ["family=open_redirect|stack=python/django|topology=single_service"],
                        "rejected_candidate_count": 1,
                    },
                    "branch_chain": [
                        {
                            "branch": "family",
                            "selected_value": "open_redirect",
                            "materialized_value": "open_redirect",
                            "selected_source": "semantic_signature",
                            "materialized_field": "staged_synthesis.candidate_resolution.selected_family",
                            "aligned": True,
                        }
                    ],
                },
                "generation_materialization": {
                    "schema_version": "generation_materialization@0.1",
                    "generation_origin": "deterministic_fallback",
                    "materializer": "llm_fallback",
                    "path_class": "stub",
                    "provider_attempted": False,
                    "provider_succeeded": False,
                    "stub_fallback": True,
                    "fixture_used": False,
                    "failure_class": "provider_disabled",
                    "provider_backend": "litellm",
                    "model": "gpt-5.2",
                    "cache_mode": "none",
                    "live_positive_ready": False,
                    "non_live_reason": "provider_disabled",
                    "prompt_contracts": [{"name": "synthesis_manifest", "version": "build_synthesis_prompt@1"}],
                    "prompt_invocations": {"synthesis_manifest": 1},
                },
                "staged_recovery": {
                    "recovery_strategy": "runtime_plan",
                    "failure_stage": "runtime_plan",
                    "failure_stage_reason": "runtime_plan_mismatch",
                    "stage_aware_recovery_used": True,
                },
                "staged_recovery_strategy": "runtime_plan",
                "staged_failure_stage": "runtime_plan",
                "staged_failure_stage_reason": "runtime_plan_mismatch",
                "bundles": [
                    {
                        "slug": "name-open-redirect",
                        "vuln_id": "NAME-OPEN-REDIRECT",
                        "request_ir": {
                            "request_label": "Open Redirect",
                            "resolution_state": "catalog_alias",
                            "name_driven": True,
                            "selection_decision": {
                                "family": {
                                    "selected": True,
                                    "selected_family": "open_redirect",
                                    "evidence_backed": True,
                                    "support_count": 1,
                                    "support_by_source_authority": {"high": 1},
                                    "high_or_medium_authority_support": True,
                                },
                                "stack": {
                                    "selected": True,
                                    "selected_stack_id": "python/flask",
                                    "evidence_backed": True,
                                    "support_count": 1,
                                    "support_by_source_authority": {"high": 1},
                                    "high_or_medium_authority_support": True,
                                },
                                "ready_for_materialization": True,
                                "open_world_evidence_ready": True,
                            },
                        },
                        "provenance": {
                            "generation_origin": "deterministic_fallback",
                            "llm_provider_attempted": False,
                            "llm_provider_succeeded": False,
                            "llm_fixture_used": False,
                            "llm_stub_used": True,
                            "llm_execution": {
                                "provider_attempted": False,
                                "provider_succeeded": False,
                                "stub_fallback": True,
                                "fixture_used": False,
                                "path_class": "stub",
                            },
                            "semantic_guided_selection_source": "request_resolution",
                            "semantic_guided_ambiguous": True,
                        },
                        "open_world": {
                            "class": "semantic_guided_minimal_dynamic",
                            "counts_as_generalization": False,
                            "selection_source": "request_resolution",
                            "selection_open_world_evidence_ready": True,
                        },
                        "runtime_recipe": {"language": "python", "framework": "flask", "hypothetical": False},
                        "runtime_graph": {"topology": "single_service", "nodes": [{"id": "service"}], "hypothetical": False},
                        "executor_plan": {"service_port": 5000, "health_path": "/health", "topology": "single_service"},
                        "evidence_graph": {
                            "schema_version": "evidence_graph@0.1",
                            "node_count": 3,
                            "edge_count": 2,
                            "nodes": [{"id": "evidence:1", "kind": "evidence", "source_authority": "high"}],
                        },
                        "dynamic_eval": {"enabled": True, "status": "degraded_success"},
                        "artifact_quality": {
                            "band": "medium",
                            "oracle_execution_parity": "partial",
                            "oracle_execution_attempted": True,
                            "qualitative_tier": "thin_or_incomplete",
                            "qualitative_review": "artifact remains thin or incomplete for operator-facing use",
                        },
                        "stack_dependence": {
                            "class": "repo_prior_bounded",
                            "stack_source": "profile_prior",
                            "stack_defaulted": True,
                            "working_stack_evidence_backed": True,
                        },
                        "support_promotion": {
                        "eligible": False,
                        "reasons": [
                            "strict_open_world:strict_minimal_dynamic_fallback",
                            "generation_path:not_live_positive",
                            "generation_path:provider_disabled",
                        ],
                    },
                    "open_world_readiness": {
                        "ready": False,
                        "blockers": [
                            "strict_open_world_gate",
                            "generation_path_not_live_positive",
                            "generation_path_provider_disabled",
                            "stack_defaulted",
                        ],
                    },
                        "family_dependence": {
                            "class": "semantic_signature_bounded",
                            "selection_source": "semantic_signature",
                            "working_family_evidence_backed": True,
                            "candidate_evidence_backed": True,
                            "candidate_evidence_ids": ["evidence:1"],
                            "resolution_confidence": "high",
                            "resolution_basis": "catalog_alias",
                            "negative_hypothesis_count": 1,
                        },
                        "intent_satisfaction": {"mode": "dynamic", "status": "degraded_dynamic_success"},
                        "name_only_outcome": {
                            "request_kind": "name_only",
                            "mode": "dynamic",
                            "decision": "partial",
                            "decision_reason": "degraded_dynamic_success",
                            "abstain_reason": None,
                            "terminal_failure_class": None,
                            "closure_source": "degraded_deterministic_fallback",
                            "allowed_by_execution_contract": True,
                            "satisfies_intent_contract": False,
                            "stage_ceiling": "generated",
                            "fully_validated": False,
                            "next_required_step": "execution",
                            "selection_ready_for_materialization": True,
                            "selection_open_world_evidence_ready": True,
                            "family_selected": True,
                            "selected_family": "open_redirect",
                            "family_evidence_backed": True,
                            "family_support_count": 1,
                            "stack_selected": True,
                            "selected_stack_id": "python/flask",
                            "stack_evidence_backed": True,
                            "stack_support_count": 1,
                            "open_world_class": "semantic_guided_minimal_dynamic",
                            "strict_open_world_class": "strict_minimal_dynamic_fallback",
                            "stack_dependence_class": "repo_prior_bounded",
                            "family_dependence_class": "semantic_signature_bounded",
                        },
                        "name_only_generation_spec": {
                            "planning_focus_summary": {
                                "primary_focus": "stack_or_runtime_design",
                                "focuses": ["stack_or_runtime_design", "evidence_authority"],
                                "by_focus": {
                                    "stack_or_runtime_design": ["stack_defaulted", "stack_ambiguous"],
                                    "evidence_authority": ["family_candidate_evidence_missing"],
                                },
                                "reason_tokens": [
                                    "stack_defaulted",
                                    "stack_ambiguous",
                                    "family_candidate_evidence_missing",
                                ],
                            }
                        },
                        "staged_synthesis": {
                            "schema_version": "staged_synthesis@0.1",
                            "stage_order": ["candidate_resolution", "design_brief", "runtime_plan", "oracle_contract"],
                            "candidate_resolution": {"selected_topology": "single_service"},
                        },
                        "selection_branch_trace": {
                            "schema_version": "selection_branch_trace@0.1",
                            "controller_ready": True,
                            "open_world_evidence_ready": True,
                            "branch_aligned": True,
                            "selected_branch": {
                                "family": {"selected_value": "open_redirect", "materialized_value": "open_redirect", "aligned": True}
                            },
                            "materialization_bundle": {
                                "runtime_topology": "single_service",
                                "executor_topology": "single_service",
                                "service_entry_path": "app.py",
                                "poc_entry_path": "poc.py",
                                "dockerfile_path": "Dockerfile",
                                "build_context_root": ".",
                                "dependency_manifest_paths": ["requirements.txt"],
                                "seed_asset_paths": ["schema.sql"],
                                "required_roles": ["service_main", "poc_entry"],
                            },
                            "candidate_context": {
                                "scenario_candidate_count": 2,
                                "selected_candidate_present": True,
                                "selection_state": "selected",
                                "selected_by": "scenario_candidates.explicit_selected",
                                "unresolved_reasons": [],
                                "rejected_scenario_ids_sample": ["family=open_redirect|stack=python/django|topology=single_service"],
                                "rejected_candidate_count": 1,
                            },
                            "branch_chain": [
                                {
                                    "branch": "family",
                                    "selected_value": "open_redirect",
                                    "materialized_value": "open_redirect",
                                    "selected_source": "semantic_signature",
                                    "materialized_field": "staged_synthesis.candidate_resolution.selected_family",
                                    "aligned": True,
                                }
                            ],
                        },
                        "generation_materialization": {
                            "schema_version": "generation_materialization@0.1",
                            "generation_origin": "deterministic_fallback",
                            "materializer": "llm_fallback",
                            "path_class": "stub",
                            "provider_attempted": False,
                            "provider_succeeded": False,
                            "stub_fallback": True,
                            "fixture_used": False,
                            "failure_class": "provider_disabled",
                            "provider_backend": "litellm",
                            "model": "gpt-5.2",
                            "cache_mode": "none",
                            "live_positive_ready": False,
                            "non_live_reason": "provider_disabled",
                            "prompt_contracts": [{"name": "synthesis_manifest", "version": "build_synthesis_prompt@1"}],
                            "prompt_invocations": {"synthesis_manifest": 1},
                        },
                        "staged_recovery": {
                            "recovery_strategy": "runtime_plan",
                            "failure_stage": "runtime_plan",
                            "failure_stage_reason": "runtime_plan_mismatch",
                            "stage_aware_recovery_used": True,
                        },
                        "completion_state": {
                            "generated": True,
                            "executed": False,
                            "run_passed": False,
                            "verified": False,
                            "verify_pass": None,
                            "reviewed": False,
                            "review_ready": False,
                            "fully_validated": False,
                            "stage_ceiling": "generated",
                            "generation_origin": "deterministic_fallback",
                        },
                        "artifacts": {
                            "build_log": "/tmp/build/build.log",
                            "sbom": "/tmp/build/sbom.spdx.json",
                            "run_log": "/tmp/run/run.log",
                            "run_summary": {
                                "image_tag": "sid-summary-surface",
                                "build_log": "/tmp/build/build.log",
                                "run_log": "/tmp/run/run.log",
                                "sbom_path": "/tmp/build/sbom.spdx.json",
                                "build_passed": True,
                                "run_passed": True,
                                "exit_code": 0,
                                "service_port_source": "executor_plan.service_port",
                                "service_entry_source": "executor_plan.service_entry",
                                "poc_entry": "poc.py",
                                "poc_entry_source": "executor_plan.poc_entry",
                                "poc_cmd": "python poc.py --base-url {{base_url}}",
                                "poc_cmd_source": "resolved_contract.poc_cmd",
                                "base_url_source": "executor_plan.base_url",
                                "health_path_source": "runtime_graph.healthchecks[service]",
                                "healthchecks": [{"node": "service", "path": "/ready", "port": 9000, "transport": "http"}],
                                "healthchecks_source": "runtime_graph.healthchecks",
                                "service_env_runtime": {
                                    "APP_PORT": "9000",
                                    "DB_HOST": "db-internal",
                                    "DB_NAME": "sqliapp",
                                    "DB_USER": "sqli",
                                    "DB_PASSWORD": "sqli_pw",
                                    "DB_PORT": "3306",
                                },
                                "service_env_source": "runtime_hint_sidecar_defaults",
                                "sidecars_source": "generator_manifest.metadata.target_sidecars",
                                "sidecars": [
                                    {
                                        "name": "mysql-main",
                                        "type": "mysql",
                                        "container": "sid-summary-surface-name-open-redirect-mysql-main",
                                        "image": "mysql:8.0",
                                        "aliases": ["db-internal"],
                                        "start_order_index": 1,
                                        "seed_mount_target": "/seed-input",
                                        "seed_files_applied": ["schema.sql"],
                                    }
                                ],
                                "sidecar_start_order": ["mysql-main"],
                                "sidecar_start_order_source": "generator_manifest.metadata.target_sidecars",
                                "allow_network": True,
                                "allow_network_source": "runtime_topology_requires_network",
                                "network_mode_source": "runtime_topology_requires_network",
                                "network_contract": [
                                    {"scope": "service", "name": "DB_HOST", "alias": "db-internal"},
                                    {"scope": "sidecar:mysql-main", "alias": "db-internal"},
                                ],
                                "network_contract_source": "runtime_recipe.service_env+sidecars",
                                "seed_strategy": "sidecar_sql_apply",
                                "seed_strategy_source": "runtime_recipe.seed_files+topology",
                                "seed_files": ["schema.sql"],
                                "seed_files_source": "executor_plan.seed_files",
                                "volume_contract": [
                                    {
                                        "scope": "sidecar:mysql-main",
                                        "source": "workspace",
                                        "target": "/seed-input",
                                        "mode": "ro",
                                    }
                                ],
                                "volume_contract_source": "runtime_recipe.seed_files+seed_strategy",
                                "seed_apply_attempted": True,
                                "seed_apply_completed": True,
                                "seed_files_applied_total": 1,
                                "seed_mount_targets": ["/seed-input"],
                            },
                            "eval_result": {"verify_pass": True},
                        },
                    }
                ],
                "reports": {"evals": {"overall_pass": True}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(run_case, "REPO_ROOT", tmp_path)

    summary = run_case._load_manifest_summary(sid, pipeline_returncode=0)

    assert summary["request_ir"]["resolution_state"] == "catalog_alias"
    assert summary["execution_salt"] == "salt-summary-surface"
    assert summary["request_ir_summary"]["ambiguous_family_candidate_bundles"] == 1
    assert summary["request_ir_summary"]["negative_hypothesis_bundles"] == 1
    assert summary["request_ir_summary"]["selection_ready_bundles"] == 1
    assert summary["request_ir_summary"]["selected_family_bundles"] == 1
    assert summary["request_ir_summary"]["selected_stack_bundles"] == 1
    assert summary["request_ir_summary"]["resolved_ambiguous_family_candidate_bundles"] == 1
    assert summary["request_ir_summary"]["unresolved_ambiguous_stack_candidate_bundles"] == 0
    assert summary["selection_readiness_summary"]["ready_for_materialization_bundles"] == 1
    assert summary["selection_readiness_summary"]["open_world_evidence_ready_bundles"] == 1
    assert summary["selection_readiness_summary"]["family_evidence_backed_bundles"] == 1
    assert summary["selection_readiness_summary"]["stack_evidence_backed_bundles"] == 1
    assert summary["selection_readiness_summary"]["resolved_ambiguous_family_bundles"] == 1
    assert summary["artifact_quality_summary"]["average_score"] == 8.0
    assert summary["artifact_quality_summary"]["by_qualitative_tier"] == {"thin_or_incomplete": 1}
    assert summary["support_promotion"]["eligible_bundles"] == 0
    assert summary["open_world_readiness_summary"]["ready_bundles"] == 0
    assert summary["open_world_readiness_summary"]["by_blocker"]["stack_defaulted"] == 1
    assert summary["open_world_readiness_summary"]["by_blocker"]["selection_open_world_evidence_not_ready"] == 1
    assert summary["boundedness_summary"]["catalog_entries"] == 12
    assert summary["evidence_graph_summary"]["graph_present_bundles"] == 1
    assert summary["evidence_graph_summary"]["by_source_authority"] == {"high": 1}
    assert summary["generalization_summary"]["lower_bound_dependent_bundles"] == 1
    assert summary["generalization_summary"]["positive_generalization_bundles"] == 0
    assert summary["open_world_selection_source"] == "request_resolution"
    assert summary["open_world_selection_evidence_ready"] is True
    assert summary["template_dependence_summary"]["minimal_dynamic_bundles"] == 1
    assert summary["open_world_summary"]["realized_bundles"] == 1
    assert summary["runtime_surface_summary"]["realized_bundles"] == 1
    assert summary["stack_dependence_summary"]["repo_prior_bounded_bundles"] == 1
    assert summary["stack_dependence_summary"]["stack_defaulted_bundles"] == 1
    assert summary["stack_dependence_summary"]["evidence_backed_bundles"] == 1
    assert summary["open_world_readiness"]["ready"] is False
    assert "stack_defaulted" in summary["open_world_readiness"]["blockers"]
    assert "selection_open_world_evidence_not_ready" in summary["open_world_readiness"]["blockers"]
    assert summary["family_dependence_summary"]["by_class"] == {"semantic_signature_bounded": 1}
    assert summary["family_dependence_summary"]["evidence_backed_bundles"] == 1
    assert summary["family_dependence_summary"]["candidate_evidence_backed_bundles"] == 1
    assert summary["family_dependence_summary"]["negative_hypothesis_bundles"] == 1
    assert summary["intent_satisfaction_summary"]["by_status"] == {"degraded_dynamic_success": 1}
    assert summary["name_only_outcome_summary"]["by_decision"] == {"partial": 1}
    assert summary["name_only_planning_summary"]["by_primary_focus"] == {"stack_or_runtime_design": 1}
    assert summary["name_only_planning_summary"]["by_reason_token"]["stack_defaulted"] == 1
    assert summary["staged_synthesis_summary"]["stage_aware_recovery_bundles"] == 1
    assert summary["staged_synthesis_summary"]["by_recovery_strategy"] == {"runtime_plan": 1}
    assert summary["dynamic_eval_summary"]["attempted_bundles"] == 1
    assert summary["completion_summary"]["by_stage_ceiling"] == {"generated": 1}
    assert summary["semantic_guided_selection_source"] == "request_resolution"
    assert summary["semantic_guided_ambiguous"] is True
    assert summary["image_tag"] == "sid-summary-surface"
    assert summary["build_log"] == "/tmp/build/build.log"
    assert summary["run_log"] == "/tmp/run/run.log"
    assert summary["sbom_path"] == "/tmp/build/sbom.spdx.json"
    assert summary["service_port"] == 9000
    assert summary["service_base_url"] == "http://127.0.0.1:9000"
    assert summary["run_passed"] is True
    assert summary["verify_pass"] is True
    assert summary["service_port_source"] == "executor_plan.service_port"
    assert summary["service_entry_source"] == "executor_plan.service_entry"
    assert summary["poc_entry"] == "poc.py"
    assert summary["poc_entry_source"] == "executor_plan.poc_entry"
    assert summary["poc_cmd"] == "python poc.py --base-url {{base_url}}"
    assert summary["poc_cmd_source"] == "resolved_contract.poc_cmd"
    assert summary["base_url_source"] == "executor_plan.base_url"
    assert summary["health_path_source"] == "runtime_graph.healthchecks[service]"
    assert summary["healthchecks"] == [{"node": "service", "path": "/ready", "port": 9000, "transport": "http"}]
    assert summary["healthchecks_source"] == "runtime_graph.healthchecks"
    assert summary["runtime_service_env"] == {
        "APP_PORT": "9000",
        "DB_HOST": "db-internal",
        "DB_NAME": "sqliapp",
        "DB_USER": "sqli",
        "DB_PASSWORD": "sqli_pw",
        "DB_PORT": "3306",
    }
    assert summary["allow_network"] is True
    assert summary["service_env_source"] == "runtime_hint_sidecar_defaults"
    assert summary["sidecars_source"] == "generator_manifest.metadata.target_sidecars"
    assert summary["network_mode"] == "bridge"
    assert summary["oracle_execution_parity"] == "partial"
    assert summary["oracle_execution_attempted"] is True
    assert summary["allow_network_source"] == "runtime_topology_requires_network"
    assert summary["network_mode_source"] == "runtime_topology_requires_network"
    assert summary["executed_sidecars"] == [
        {
            "name": "mysql-main",
            "type": "mysql",
            "container": "sid-summary-surface-name-open-redirect-mysql-main",
            "image": "mysql:8.0",
            "aliases": ["db-internal"],
            "start_order_index": 1,
            "seed_mount_target": "/seed-input",
            "seed_files_applied": ["schema.sql"],
        }
    ]
    assert summary["sidecar_start_order"] == ["mysql-main"]
    assert summary["sidecar_start_order_source"] == "generator_manifest.metadata.target_sidecars"
    assert summary["network_contract"] == [
        {"scope": "service", "name": "DB_HOST", "alias": "db-internal"},
        {"scope": "sidecar:mysql-main", "alias": "db-internal"},
    ]
    assert summary["network_contract_source"] == "runtime_recipe.service_env+sidecars"
    assert summary["seed_strategy"] == "sidecar_sql_apply"
    assert summary["seed_strategy_source"] == "runtime_recipe.seed_files+topology"
    assert summary["seed_files"] == ["schema.sql"]
    assert summary["seed_files_source"] == "executor_plan.seed_files"
    assert summary["volume_contract"] == [
        {
            "scope": "sidecar:mysql-main",
            "source": "workspace",
            "target": "/seed-input",
            "mode": "ro",
        }
    ]
    assert summary["volume_contract_source"] == "runtime_recipe.seed_files+seed_strategy"
    assert summary["seed_apply_attempted"] is True
    assert summary["seed_apply_completed"] is True
    assert summary["seed_files_applied_total"] == 1
    assert summary["seed_mount_targets"] == ["/seed-input"]
    assert summary["performance_retry_count"] == 1
    assert summary["performance_by_stage"]["RESEARCH"]["duration_s"] == 3.2
    assert summary["search_cache_hit_count"] == 2
    assert summary["search_cache_miss_count"] == 1
    assert summary["search_cache_reuse_ratio"] == 0.667
    assert summary["research_retry_budget"]["researcher_report_runs"] == 1
    assert summary["generation_retry_budget"]["planned_candidate_budget"] == 1
    assert summary["research_timeout_budget"]["search_timeout_s"] == 8.0
    assert summary["generation_timeout_budget"]["llm_request_timeout_s"] == 9.5
    assert summary["research_cost_budget"]["configured_cost_budget_usd"] == 0.25
    assert summary["generation_cost_budget"]["configured_cost_budget_usd"] == 0.25
    assert summary["generation_origin"] == "deterministic_fallback"
    assert summary["generation_path_class"] == "stub"
    assert summary["generation_provider_attempted"] is False
    assert summary["generation_provider_succeeded"] is False
    assert summary["generation_stub_fallback"] is True
    assert summary["generation_fixture_used"] is False
    assert summary["generation_non_live_reason"] == "provider_disabled"
    assert summary["generation_materialization"]["path_class"] == "stub"
    assert summary["generation_materialization"]["provider_backend"] == "litellm"
    assert summary["generation_materialization"]["prompt_contracts"][0]["name"] == "synthesis_manifest"
    assert summary["generation_materialization"]["non_live_reason"] == "provider_disabled"
    assert summary["selection_branch_trace"]["schema_version"] == "selection_branch_trace@0.1"
    assert summary["selection_branch_trace"]["branch_aligned"] is True
    assert summary["selection_branch_trace"]["materialization_bundle"]["service_entry_path"] == "app.py"
    assert summary["selection_branch_trace"]["candidate_context"]["selected_by"] == "scenario_candidates.explicit_selected"
    assert summary["search_planned_query_count"] == 4
    assert summary["search_executed_query_count"] == 3
    assert summary["search_early_stop_triggered"] is True
    assert summary["runtime_recipe"]["framework"] == "flask"
    assert summary["runtime_recipe_hypothetical"] is False
    assert summary["runtime_graph"]["topology"] == "single_service"
    assert summary["runtime_graph_hypothetical"] is False
    assert summary["executor_plan"]["health_path"] == "/health"
    assert summary["evidence_graph"]["schema_version"] == "evidence_graph@0.1"
    assert summary["artifact_quality"]["band"] == "medium"
    assert summary["artifact_quality"]["qualitative_tier"] == "thin_or_incomplete"
    assert summary["stack_dependence"]["class"] == "repo_prior_bounded"
    assert summary["stack_dependence"]["stack_defaulted"] is True
    assert summary["stack_dependence"]["working_stack_evidence_backed"] is True
    assert summary["family_dependence"]["class"] == "semantic_signature_bounded"
    assert summary["family_dependence"]["working_family_evidence_backed"] is True
    assert summary["family_dependence"]["candidate_evidence_backed"] is True
    assert summary["family_dependence"]["resolution_confidence"] == "high"
    assert summary["dynamic_eval"]["status"] == "degraded_success"
    assert summary["intent_satisfaction"]["status"] == "degraded_dynamic_success"
    assert summary["name_only_outcome"]["decision"] == "partial"
    assert summary["name_only_outcome"]["selection_ready_for_materialization"] is True
    assert summary["name_only_outcome"]["selection_open_world_evidence_ready"] is True
    assert summary["name_only_outcome"]["family_evidence_backed"] is True
    assert summary["name_only_outcome"]["family_support_count"] == 1
    assert summary["name_only_outcome"]["selected_stack_id"] == "python/flask"
    assert summary["name_only_outcome"]["stack_evidence_backed"] is True
    assert summary["name_only_outcome"]["stack_support_count"] == 1
    assert summary["name_only_decision"] == "partial"
    assert summary["name_only_next_required_step"] == "execution"
    assert summary["name_only_primary_focus"] == "stack_or_runtime_design"
    assert summary["name_only_planning_focus"]["by_focus"]["evidence_authority"] == [
        "family_candidate_evidence_missing"
    ]
    assert summary["staged_recovery_strategy"] == "runtime_plan"
    assert summary["staged_failure_stage"] == "runtime_plan"
    assert summary["staged_failure_stage_reason"] == "runtime_plan_mismatch"
    assert summary["completion_state"]["stage_ceiling"] == "generated"
    assert summary["stage_ceiling"] == "generated"
    assert summary["fully_validated"] is False
    assert summary["bundles"][0]["request_ir"]["request_label"] == "Open Redirect"
    assert summary["bundles"][0]["request_ir"]["selection_decision"]["ready_for_materialization"] is True
    assert summary["bundles"][0]["semantic_guided_selection_source"] == "request_resolution"
    assert summary["bundles"][0]["semantic_guided_ambiguous"] is True
    assert summary["bundles"][0]["generation_origin"] == "deterministic_fallback"
    assert summary["bundles"][0]["generation_path_class"] == "stub"
    assert summary["bundles"][0]["generation_stub_fallback"] is True
    assert summary["bundles"][0]["generation_fixture_used"] is False
    assert summary["bundles"][0]["generation_non_live_reason"] == "provider_disabled"
    assert summary["bundles"][0]["generation_materialization"]["failure_class"] == "provider_disabled"
    assert summary["bundles"][0]["generation_materialization"]["non_live_reason"] == "provider_disabled"
    assert summary["bundles"][0]["selection_branch_trace"]["branch_aligned"] is True
    assert summary["bundles"][0]["selection_branch_trace"]["selected_branch"]["family"]["materialized_value"] == "open_redirect"
    assert summary["bundles"][0]["runtime_graph"]["topology"] == "single_service"
    assert summary["bundles"][0]["executor_plan"]["health_path"] == "/health"
    assert summary["bundles"][0]["evidence_graph"]["node_count"] == 3
    assert summary["bundles"][0]["service_port_source"] == "executor_plan.service_port"
    assert summary["bundles"][0]["service_entry_source"] == "executor_plan.service_entry"
    assert summary["bundles"][0]["poc_entry"] == "poc.py"
    assert summary["bundles"][0]["poc_entry_source"] == "executor_plan.poc_entry"
    assert summary["bundles"][0]["poc_cmd"] == "python poc.py --base-url {{base_url}}"
    assert summary["bundles"][0]["poc_cmd_source"] == "resolved_contract.poc_cmd"
    assert summary["bundles"][0]["base_url_source"] == "executor_plan.base_url"
    assert summary["bundles"][0]["health_path_source"] == "runtime_graph.healthchecks[service]"
    assert summary["bundles"][0]["healthchecks"] == [
        {"node": "service", "path": "/ready", "port": 9000, "transport": "http"}
    ]
    assert summary["bundles"][0]["healthchecks_source"] == "runtime_graph.healthchecks"
    assert summary["bundles"][0]["runtime_service_env"] == {
        "APP_PORT": "9000",
        "DB_HOST": "db-internal",
        "DB_NAME": "sqliapp",
        "DB_USER": "sqli",
        "DB_PASSWORD": "sqli_pw",
        "DB_PORT": "3306",
    }
    assert summary["bundles"][0]["stack_dependence"]["stack_source"] == "profile_prior"
    assert summary["bundles"][0]["stack_dependence"]["stack_defaulted"] is True
    assert summary["bundles"][0]["support_promotion_eligible"] is False
    assert summary["bundles"][0]["open_world_ready"] is False
    assert summary["bundles"][0]["open_world_selection_source"] == "request_resolution"
    assert summary["bundles"][0]["open_world_selection_evidence_ready"] is True
    assert summary["bundles"][0]["name_only_primary_focus"] == "stack_or_runtime_design"
    assert summary["bundles"][0]["name_only_outcome"]["selected_family"] == "open_redirect"
    assert summary["bundles"][0]["staged_recovery_strategy"] == "runtime_plan"
    assert summary["bundles"][0]["staged_failure_stage"] == "runtime_plan"
    assert summary["bundles"][0]["service_env_source"] == "runtime_hint_sidecar_defaults"
    assert summary["bundles"][0]["sidecars_source"] == "generator_manifest.metadata.target_sidecars"
    assert summary["bundles"][0]["executed_sidecars"] == [
        {
            "name": "mysql-main",
            "type": "mysql",
            "container": "sid-summary-surface-name-open-redirect-mysql-main",
            "image": "mysql:8.0",
            "aliases": ["db-internal"],
            "start_order_index": 1,
            "seed_mount_target": "/seed-input",
            "seed_files_applied": ["schema.sql"],
        }
    ]
    assert summary["bundles"][0]["sidecar_start_order"] == ["mysql-main"]
    assert summary["bundles"][0]["sidecar_start_order_source"] == "generator_manifest.metadata.target_sidecars"
    assert summary["bundles"][0]["allow_network"] is True
    assert summary["bundles"][0]["allow_network_source"] == "runtime_topology_requires_network"
    assert summary["bundles"][0]["network_mode_source"] == "runtime_topology_requires_network"
    assert summary["bundles"][0]["network_contract"] == [
        {"scope": "service", "name": "DB_HOST", "alias": "db-internal"},
        {"scope": "sidecar:mysql-main", "alias": "db-internal"},
    ]
    assert summary["bundles"][0]["network_contract_source"] == "runtime_recipe.service_env+sidecars"
    assert summary["bundles"][0]["seed_strategy"] == "sidecar_sql_apply"
    assert summary["bundles"][0]["seed_strategy_source"] == "runtime_recipe.seed_files+topology"
    assert summary["bundles"][0]["seed_files"] == ["schema.sql"]
    assert summary["bundles"][0]["seed_files_source"] == "executor_plan.seed_files"
    assert summary["bundles"][0]["oracle_execution_parity"] == "partial"
    assert summary["bundles"][0]["oracle_execution_attempted"] is True
    assert summary["bundles"][0]["artifact_quality"]["qualitative_tier"] == "thin_or_incomplete"
    assert summary["bundles"][0]["volume_contract"] == [
        {
            "scope": "sidecar:mysql-main",
            "source": "workspace",
            "target": "/seed-input",
            "mode": "ro",
        }
    ]
    assert summary["bundles"][0]["volume_contract_source"] == "runtime_recipe.seed_files+seed_strategy"
    assert summary["bundles"][0]["seed_apply_attempted"] is True
    assert summary["bundles"][0]["seed_apply_completed"] is True
    assert summary["bundles"][0]["seed_files_applied_total"] == 1
    assert summary["bundles"][0]["seed_mount_targets"] == ["/seed-input"]
    assert summary["bundles"][0]["staged_recovery"]["stage_aware_recovery_used"] is True
    assert summary["bundles"][0]["name_only_planning_focus"]["by_focus"]["stack_or_runtime_design"] == [
        "stack_defaulted",
        "stack_ambiguous",
    ]
    assert summary["bundles"][0]["family_dependence"]["selection_source"] == "semantic_signature"
    assert summary["bundles"][0]["name_only_outcome"]["next_required_step"] == "execution"
    assert summary["bundles"][0]["completion_state"]["stage_ceiling"] == "generated"


def test_load_manifest_summary_surfaces_top_level_terminal_failure_class_from_nested_name_only_outcome(
    tmp_path: Path, monkeypatch
) -> None:
    sid = "sid-summary-failure-class"
    metadata_dir = tmp_path / "metadata" / sid
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "reviewer_report.json").write_text(
        json.dumps({"blocking_bundles": [], "issues_sample": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    (metadata_dir / "manifest.json").write_text(
        json.dumps(
            {
                "sid": sid,
                "pipeline_result": "failure",
                "name_only_outcome": {
                    "request_kind": "name_only",
                    "mode": "strict_dynamic",
                    "decision": "fail_closed",
                    "terminal_failure_class": "strict_dynamic_remote_research_unavailable",
                    "stage_ceiling": "pre_generation",
                },
                "bundles": [
                    {
                        "slug": "name-open-redirect",
                        "vuln_id": "NAME-OPEN-REDIRECT",
                        "name_only_outcome": {
                            "request_kind": "name_only",
                            "mode": "strict_dynamic",
                            "decision": "fail_closed",
                            "terminal_failure_class": "strict_dynamic_remote_research_unavailable",
                            "stage_ceiling": "pre_generation",
                        },
                        "failure": {
                            "stage": "CAPABILITY_CHECK",
                            "reason": "remote research unavailable",
                            "terminal_failure_class": "strict_dynamic_remote_research_unavailable",
                        },
                    }
                ],
                "reports": {"evals": {"overall_pass": False}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(run_case, "REPO_ROOT", tmp_path)

    summary = run_case._load_manifest_summary(sid, pipeline_returncode=1)

    assert summary["terminal_failure_class"] == "strict_dynamic_remote_research_unavailable"
    assert summary["bundles"][0]["terminal_failure_class"] == "strict_dynamic_remote_research_unavailable"


def test_load_manifest_summary_surfaces_multibundle_bundle_verdict_rollup(
    tmp_path: Path, monkeypatch
) -> None:
    sid = "sid-summary-multibundle-verdict-rollup"
    metadata_dir = tmp_path / "metadata" / sid
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "reviewer_report.json").write_text(
        json.dumps({"blocking_bundles": [], "issues_sample": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    (metadata_dir / "manifest.json").write_text(
        json.dumps(
            {
                "sid": sid,
                "pipeline_result": "failure",
                "run_passed_rollup": "mixed",
                "verify_pass_rollup": "mixed",
                "oracle_execution_parity_rollup": "mixed",
                "oracle_execution_attempted_rollup": "mixed",
                "qualitative_tier_rollup": "mixed",
                "stage_ceiling_rollup": "mixed",
                "terminal_failure_class_rollup": "mixed",
                "verdict_authority": {
                    "canonical_surface": "bundles",
                    "top_level_role": "convenience_projection",
                    "mode": "multi_bundle",
                    "fields": {
                        "run_passed": {
                            "canonical_source": "bundles[].completion_state.run_passed",
                            "canonical_precedence": "bundle_truth",
                            "projection_mode": "multibundle_rollup",
                            "rollup_key": "run_passed_rollup",
                        },
                        "verify_pass": {
                            "canonical_source": "bundles[].completion_state.verify_pass",
                            "canonical_precedence": "bundle_truth",
                            "projection_mode": "multibundle_rollup",
                            "rollup_key": "verify_pass_rollup",
                        },
                        "stage_ceiling": {
                            "canonical_source": "bundles[].completion_state.stage_ceiling",
                            "canonical_precedence": "bundle_truth",
                            "projection_mode": "multibundle_rollup",
                            "rollup_key": "stage_ceiling_rollup",
                        },
                        "terminal_failure_class": {
                            "canonical_source": "bundles[].failure.terminal_failure_class|bundles[].name_only_outcome.terminal_failure_class",
                            "canonical_precedence": "bundle_truth",
                            "projection_mode": "multibundle_rollup",
                            "rollup_key": "terminal_failure_class_rollup",
                        },
                        "oracle_execution_parity": {
                            "canonical_source": "bundles[].artifact_quality.oracle_execution_parity",
                            "canonical_precedence": "bundle_truth",
                            "projection_mode": "multibundle_rollup",
                            "rollup_key": "oracle_execution_parity_rollup",
                        },
                        "oracle_execution_attempted": {
                            "canonical_source": "bundles[].artifact_quality.oracle_execution_attempted",
                            "canonical_precedence": "bundle_truth",
                            "projection_mode": "multibundle_rollup",
                            "rollup_key": "oracle_execution_attempted_rollup",
                        },
                    },
                },
                "bundle_verdict_rollup": {
                    "bundle_count": 2,
                    "run_passed_bundles": 1,
                    "run_failed_bundles": 0,
                    "run_unknown_bundles": 1,
                    "run_passed_consensus": "mixed",
                    "verify_pass_bundles": 1,
                    "verify_failed_bundles": 0,
                    "verify_unknown_bundles": 1,
                    "verify_pass_consensus": "mixed",
                    "oracle_execution_attempted_bundles": 1,
                    "oracle_execution_attempted_consensus": "mixed",
                    "by_oracle_execution_parity": {"high": 1, "missing": 1},
                    "oracle_execution_parity_consensus": "mixed",
                    "by_qualitative_tier": {"thin_fallback_demo": 1, "planning_only": 1},
                    "qualitative_tier_consensus": "mixed",
                    "by_stage_ceiling": {"generated": 1, "pre_generation": 1},
                    "stage_ceiling_consensus": "mixed",
                    "by_terminal_failure_class": {"strict_dynamic_remote_research_unavailable": 1},
                    "terminal_failure_class_consensus": "mixed",
                },
                "bundles": [
                    {
                        "slug": "name-template-injection",
                        "vuln_id": "NAME-TEMPLATE-INJECTION",
                        "artifacts": {
                            "run_summary": {"run_passed": True},
                            "eval_result": {"verify_pass": True},
                        },
                        "artifact_quality": {
                            "oracle_execution_parity": "high",
                            "oracle_execution_attempted": True,
                            "qualitative_tier": "thin_fallback_demo",
                        },
                        "completion_state": {"stage_ceiling": "generated"},
                    },
                    {
                        "slug": "name-custom-weird-vuln",
                        "vuln_id": "NAME-CUSTOM-WEIRD-VULN",
                        "name_only_outcome": {
                            "terminal_failure_class": "strict_dynamic_remote_research_unavailable",
                        },
                        "artifact_quality": {
                            "oracle_execution_parity": "missing",
                            "oracle_execution_attempted": False,
                            "qualitative_tier": "planning_only",
                        },
                        "completion_state": {"stage_ceiling": "pre_generation"},
                    },
                ],
                "reports": {"evals": {"overall_pass": False}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(run_case, "REPO_ROOT", tmp_path)

    summary = run_case._load_manifest_summary(sid, pipeline_returncode=1)

    assert summary["bundle_verdict_rollup"] == {
        "bundle_count": 2,
        "run_passed_bundles": 1,
        "run_failed_bundles": 0,
        "run_unknown_bundles": 1,
        "run_passed_consensus": "mixed",
        "verify_pass_bundles": 1,
        "verify_failed_bundles": 0,
        "verify_unknown_bundles": 1,
        "verify_pass_consensus": "mixed",
        "oracle_execution_attempted_bundles": 1,
        "oracle_execution_attempted_consensus": "mixed",
        "by_oracle_execution_parity": {"high": 1, "missing": 1},
        "oracle_execution_parity_consensus": "mixed",
        "by_qualitative_tier": {"thin_fallback_demo": 1, "planning_only": 1},
        "qualitative_tier_consensus": "mixed",
        "by_stage_ceiling": {"generated": 1, "pre_generation": 1},
        "stage_ceiling_consensus": "mixed",
        "by_terminal_failure_class": {"strict_dynamic_remote_research_unavailable": 1},
        "terminal_failure_class_consensus": "mixed",
    }
    assert summary["run_passed_rollup"] == "mixed"
    assert summary["verify_pass_rollup"] == "mixed"
    assert summary["oracle_execution_parity_rollup"] == "mixed"
    assert summary["oracle_execution_attempted_rollup"] == "mixed"
    assert summary["qualitative_tier_rollup"] == "mixed"
    assert summary["stage_ceiling_rollup"] == "mixed"
    assert summary["terminal_failure_class_rollup"] == "mixed"
    assert summary["verdict_authority"] == {
        "canonical_surface": "bundles",
        "top_level_role": "convenience_projection",
        "mode": "multi_bundle",
        "fields": {
            "run_passed": {
                "canonical_source": "bundles[].completion_state.run_passed",
                "canonical_precedence": "bundle_truth",
                "projection_mode": "multibundle_rollup",
                "rollup_key": "run_passed_rollup",
            },
            "verify_pass": {
                "canonical_source": "bundles[].completion_state.verify_pass",
                "canonical_precedence": "bundle_truth",
                "projection_mode": "multibundle_rollup",
                "rollup_key": "verify_pass_rollup",
            },
            "stage_ceiling": {
                "canonical_source": "bundles[].completion_state.stage_ceiling",
                "canonical_precedence": "bundle_truth",
                "projection_mode": "multibundle_rollup",
                "rollup_key": "stage_ceiling_rollup",
            },
            "terminal_failure_class": {
                "canonical_source": "bundles[].failure.terminal_failure_class|bundles[].name_only_outcome.terminal_failure_class",
                "canonical_precedence": "bundle_truth",
                "projection_mode": "multibundle_rollup",
                "rollup_key": "terminal_failure_class_rollup",
            },
            "oracle_execution_parity": {
                "canonical_source": "bundles[].artifact_quality.oracle_execution_parity",
                "canonical_precedence": "bundle_truth",
                "projection_mode": "multibundle_rollup",
                "rollup_key": "oracle_execution_parity_rollup",
            },
            "oracle_execution_attempted": {
                "canonical_source": "bundles[].artifact_quality.oracle_execution_attempted",
                "canonical_precedence": "bundle_truth",
                "projection_mode": "multibundle_rollup",
                "rollup_key": "oracle_execution_attempted_rollup",
            },
        },
    }


def test_load_manifest_summary_surfaces_uniform_multibundle_top_level_verdict_fields(
    tmp_path: Path, monkeypatch
) -> None:
    sid = "sid-summary-uniform-multibundle-top-level-verdicts"
    metadata_dir = tmp_path / "metadata" / sid
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "reviewer_report.json").write_text(
        json.dumps({"blocking_bundles": [], "issues_sample": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    (metadata_dir / "manifest.json").write_text(
        json.dumps(
            {
                "sid": sid,
                "pipeline_result": "failure",
                "run_passed": False,
                "run_passed_rollup": "all_false",
                "verify_pass": None,
                "verify_pass_rollup": "unknown",
                "stage_ceiling": "pre_generation",
                "stage_ceiling_rollup": "pre_generation",
                "terminal_failure_class": "strict_dynamic_remote_research_unavailable",
                "terminal_failure_class_rollup": "strict_dynamic_remote_research_unavailable",
                "oracle_execution_parity": "missing",
                "oracle_execution_parity_rollup": "missing",
                "oracle_execution_attempted": False,
                "oracle_execution_attempted_rollup": "all_false",
                "verdict_authority": {
                    "canonical_surface": "bundles",
                    "top_level_role": "convenience_projection",
                    "mode": "multi_bundle",
                    "fields": {
                        "run_passed": {
                            "canonical_source": "bundles[].completion_state.run_passed",
                            "canonical_precedence": "bundle_truth",
                            "projection_mode": "uniform_multibundle_exact",
                            "rollup_key": "run_passed_rollup",
                            "exact_key": "run_passed",
                        },
                        "verify_pass": {
                            "canonical_source": "bundles[].completion_state.verify_pass",
                            "canonical_precedence": "bundle_truth",
                            "projection_mode": "uniform_multibundle_exact",
                            "rollup_key": "verify_pass_rollup",
                            "exact_key": "verify_pass",
                        },
                        "stage_ceiling": {
                            "canonical_source": "bundles[].completion_state.stage_ceiling",
                            "canonical_precedence": "bundle_truth",
                            "projection_mode": "uniform_multibundle_exact",
                            "rollup_key": "stage_ceiling_rollup",
                            "exact_key": "stage_ceiling",
                        },
                        "terminal_failure_class": {
                            "canonical_source": "bundles[].failure.terminal_failure_class|bundles[].name_only_outcome.terminal_failure_class",
                            "canonical_precedence": "bundle_truth",
                            "projection_mode": "uniform_multibundle_exact",
                            "rollup_key": "terminal_failure_class_rollup",
                            "exact_key": "terminal_failure_class",
                        },
                        "oracle_execution_parity": {
                            "canonical_source": "bundles[].artifact_quality.oracle_execution_parity",
                            "canonical_precedence": "bundle_truth",
                            "projection_mode": "uniform_multibundle_exact",
                            "rollup_key": "oracle_execution_parity_rollup",
                            "exact_key": "oracle_execution_parity",
                        },
                        "oracle_execution_attempted": {
                            "canonical_source": "bundles[].artifact_quality.oracle_execution_attempted",
                            "canonical_precedence": "bundle_truth",
                            "projection_mode": "uniform_multibundle_exact",
                            "rollup_key": "oracle_execution_attempted_rollup",
                            "exact_key": "oracle_execution_attempted",
                        },
                    },
                },
                "bundles": [
                    {
                        "slug": "name-a",
                        "vuln_id": "NAME-A",
                        "completion_state": {"stage_ceiling": "pre_generation"},
                        "failure": {"terminal_failure_class": "strict_dynamic_remote_research_unavailable"},
                    },
                    {
                        "slug": "name-b",
                        "vuln_id": "NAME-B",
                        "completion_state": {"stage_ceiling": "pre_generation"},
                        "failure": {"terminal_failure_class": "strict_dynamic_remote_research_unavailable"},
                    },
                ],
                "reports": {"evals": {"overall_pass": False}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(run_case, "REPO_ROOT", tmp_path)

    summary = run_case._load_manifest_summary(sid, pipeline_returncode=1)

    assert summary["run_passed"] is False
    assert summary["run_passed_rollup"] == "all_false"
    assert summary["verify_pass"] is None
    assert summary["verify_pass_rollup"] == "unknown"
    assert summary["stage_ceiling"] == "pre_generation"
    assert summary["stage_ceiling_rollup"] == "pre_generation"
    assert summary["terminal_failure_class"] == "strict_dynamic_remote_research_unavailable"
    assert summary["terminal_failure_class_rollup"] == "strict_dynamic_remote_research_unavailable"
    assert summary["oracle_execution_parity"] == "missing"
    assert summary["oracle_execution_parity_rollup"] == "missing"
    assert summary["oracle_execution_attempted"] is False
    assert summary["oracle_execution_attempted_rollup"] == "all_false"
    assert summary["verdict_authority"] == {
        "canonical_surface": "bundles",
        "top_level_role": "convenience_projection",
        "mode": "multi_bundle",
        "fields": {
            "run_passed": {
                "canonical_source": "bundles[].completion_state.run_passed",
                "canonical_precedence": "bundle_truth",
                "projection_mode": "uniform_multibundle_exact",
                "rollup_key": "run_passed_rollup",
                "exact_key": "run_passed",
            },
            "verify_pass": {
                "canonical_source": "bundles[].completion_state.verify_pass",
                "canonical_precedence": "bundle_truth",
                "projection_mode": "uniform_multibundle_exact",
                "rollup_key": "verify_pass_rollup",
                "exact_key": "verify_pass",
            },
            "stage_ceiling": {
                "canonical_source": "bundles[].completion_state.stage_ceiling",
                "canonical_precedence": "bundle_truth",
                "projection_mode": "uniform_multibundle_exact",
                "rollup_key": "stage_ceiling_rollup",
                "exact_key": "stage_ceiling",
            },
            "terminal_failure_class": {
                "canonical_source": "bundles[].failure.terminal_failure_class|bundles[].name_only_outcome.terminal_failure_class",
                "canonical_precedence": "bundle_truth",
                "projection_mode": "uniform_multibundle_exact",
                "rollup_key": "terminal_failure_class_rollup",
                "exact_key": "terminal_failure_class",
            },
            "oracle_execution_parity": {
                "canonical_source": "bundles[].artifact_quality.oracle_execution_parity",
                "canonical_precedence": "bundle_truth",
                "projection_mode": "uniform_multibundle_exact",
                "rollup_key": "oracle_execution_parity_rollup",
                "exact_key": "oracle_execution_parity",
            },
            "oracle_execution_attempted": {
                "canonical_source": "bundles[].artifact_quality.oracle_execution_attempted",
                "canonical_precedence": "bundle_truth",
                "projection_mode": "uniform_multibundle_exact",
                "rollup_key": "oracle_execution_attempted_rollup",
                "exact_key": "oracle_execution_attempted",
            },
        },
    }


def test_execute_case_annotates_case_matrix_and_writes_summary(tmp_path: Path, monkeypatch) -> None:
    case_dir = tmp_path / "case"
    case_dir.mkdir(parents=True, exist_ok=True)
    output_dir = tmp_path / "output"
    written: dict[str, object] = {}

    monkeypatch.setattr(
        run_case,
        "_load_case_spec",
        lambda _case_dir, _requirement_path=None: run_case.CaseSpec(
            name="cwe-89-basic",
            requirement={"target": {}},
            runtime_assets={},
            options={},
        ),
    )
    monkeypatch.setattr(
        run_case,
        "_write_plan",
        lambda requirement, *, multi_vuln_opt_in=False, sid_salt="": {
            "sid": "sid-case-matrix",
            "requirement": requirement,
            "sid_salt": sid_salt,
        },
    )
    monkeypatch.setattr(run_case, "_materialize_runtime_assets", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(run_case, "_case_requires_docker", lambda _expectations: False)
    monkeypatch.setattr(
        run_case,
        "_execute_pipeline",
        lambda _sid, _mode, _env: SimpleNamespace(returncode=0, stderr=""),
    )
    monkeypatch.setattr(
        run_case,
        "_load_manifest_summary",
        lambda _sid, *, pipeline_returncode=None: {
            "overall_pass": True,
            "pipeline_result": "success",
            "search_cache_hit_count": 2,
            "search_cache_miss_count": 1,
            "search_cache_reuse_ratio": 0.667,
            "search_planned_query_count": 4,
            "search_executed_query_count": 3,
            "search_early_stop_triggered": True,
        },
    )

    def _fake_write_summary(summary: dict, requirement: dict, destination: Path) -> Path:
        written["summary"] = dict(summary)
        written["requirement"] = dict(requirement)
        destination.mkdir(parents=True, exist_ok=True)
        path = destination / "summary.json"
        path.write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
        return path

    monkeypatch.setattr(run_case, "_write_summary", _fake_write_summary)

    summary = run_case.execute_case(
        case_dir,
        requirement_path=None,
        expectations_path=None,
        mode="deterministic",
        snapshot=False,
        output_dir=output_dir,
    )

    assert summary["case_name"] == "cwe-89-basic"
    assert summary["matrix_axes"]["family_known"] == "known"
    assert summary["case_matrix_exempt"] is False
    assert summary["search_cache_hit_count"] == 2
    assert summary["search_executed_query_count"] == 3
    assert written["summary"] == summary


def test_apply_execution_salt_rewrites_sid_and_paths(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(run_case, "REPO_ROOT", tmp_path)

    salted = run_case._apply_execution_salt(
        {
            "sid": "sid-original",
            "sid_inputs": {"components": {"seed": "0"}},
            "paths": {
                "metadata": "/tmp/metadata/sid-original",
                "workspace": "/tmp/workspaces/sid-original/app",
                "artifacts": "/tmp/artifacts/sid-original",
            },
        },
        "salt-123",
    )

    assert salted["sid"] != "sid-original"
    assert salted["sid"].startswith("sid-")
    assert salted["sid_inputs"]["components"]["execution_salt"] == "salt-123"
    assert salted["paths"]["metadata"] == str(tmp_path / "metadata" / salted["sid"])
    assert salted["paths"]["workspace"] == str(tmp_path / "workspaces" / salted["sid"] / "app")
    assert salted["paths"]["artifacts"] == str(tmp_path / "artifacts" / salted["sid"])
