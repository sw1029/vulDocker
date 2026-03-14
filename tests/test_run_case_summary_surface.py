from __future__ import annotations

import json
import sys
from pathlib import Path

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
                "artifact_quality_summary": {"bundle_count": 1, "average_score": 8.0},
                "support_promotion": {
                    "eligible_bundles": 0,
                    "all_eligible": False,
                    "reasons": [
                        "name-open-redirect: strict_open_world:strict_minimal_dynamic_fallback",
                        "name-open-redirect: selection_evidence:open_world_not_ready",
                    ],
                },
                "open_world_readiness_summary": {
                    "bundle_count": 1,
                    "ready_bundles": 0,
                    "not_ready_bundles": 1,
                    "all_ready": False,
                    "by_blocker": {
                        "strict_open_world_gate": 1,
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
                    "by_stage": {
                        "RESEARCH": {"count": 1, "duration_s": 3.2, "skipped": 0},
                        "GENERATOR": {"count": 1, "duration_s": 1.4, "skipped": 0},
                    },
                },
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
                "runtime_recipe": {"language": "python", "framework": "flask", "hypothetical": False},
                "runtime_graph": {"topology": "single_service", "nodes": [{"id": "service"}], "hypothetical": False},
                "executor_plan": {"service_port": 5000, "health_path": "/health", "topology": "single_service"},
                "evidence_graph": {
                    "schema_version": "evidence_graph@0.1",
                    "node_count": 3,
                    "edge_count": 2,
                    "nodes": [{"id": "evidence:1", "kind": "evidence", "source_authority": "high"}],
                },
                "artifact_quality": {"band": "medium"},
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
                        "artifact_quality": {"band": "medium"},
                        "stack_dependence": {
                            "class": "repo_prior_bounded",
                            "stack_source": "profile_prior",
                            "stack_defaulted": True,
                            "working_stack_evidence_backed": True,
                        },
                        "support_promotion": {
                            "eligible": False,
                            "reasons": ["strict_open_world:strict_minimal_dynamic_fallback"],
                        },
                        "open_world_readiness": {
                            "ready": False,
                            "blockers": ["strict_open_world_gate", "stack_defaulted"],
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
                            "run_summary": {"run_passed": True, "exit_code": 0},
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
    assert summary["dynamic_eval_summary"]["attempted_bundles"] == 1
    assert summary["completion_summary"]["by_stage_ceiling"] == {"generated": 1}
    assert summary["semantic_guided_selection_source"] == "request_resolution"
    assert summary["semantic_guided_ambiguous"] is True
    assert summary["performance_retry_count"] == 1
    assert summary["performance_by_stage"]["RESEARCH"]["duration_s"] == 3.2
    assert summary["runtime_recipe"]["framework"] == "flask"
    assert summary["runtime_recipe_hypothetical"] is False
    assert summary["runtime_graph"]["topology"] == "single_service"
    assert summary["runtime_graph_hypothetical"] is False
    assert summary["executor_plan"]["health_path"] == "/health"
    assert summary["evidence_graph"]["schema_version"] == "evidence_graph@0.1"
    assert summary["artifact_quality"]["band"] == "medium"
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
    assert summary["completion_state"]["stage_ceiling"] == "generated"
    assert summary["stage_ceiling"] == "generated"
    assert summary["fully_validated"] is False
    assert summary["bundles"][0]["request_ir"]["request_label"] == "Open Redirect"
    assert summary["bundles"][0]["request_ir"]["selection_decision"]["ready_for_materialization"] is True
    assert summary["bundles"][0]["semantic_guided_selection_source"] == "request_resolution"
    assert summary["bundles"][0]["semantic_guided_ambiguous"] is True
    assert summary["bundles"][0]["runtime_graph"]["topology"] == "single_service"
    assert summary["bundles"][0]["executor_plan"]["health_path"] == "/health"
    assert summary["bundles"][0]["evidence_graph"]["node_count"] == 3
    assert summary["bundles"][0]["stack_dependence"]["stack_source"] == "profile_prior"
    assert summary["bundles"][0]["stack_dependence"]["stack_defaulted"] is True
    assert summary["bundles"][0]["support_promotion_eligible"] is False
    assert summary["bundles"][0]["open_world_ready"] is False
    assert summary["bundles"][0]["open_world_selection_source"] == "request_resolution"
    assert summary["bundles"][0]["open_world_selection_evidence_ready"] is True
    assert summary["bundles"][0]["name_only_primary_focus"] == "stack_or_runtime_design"
    assert summary["bundles"][0]["name_only_outcome"]["selected_family"] == "open_redirect"
    assert summary["bundles"][0]["name_only_planning_focus"]["by_focus"]["stack_or_runtime_design"] == [
        "stack_defaulted",
        "stack_ambiguous",
    ]
    assert summary["bundles"][0]["family_dependence"]["selection_source"] == "semantic_signature"
    assert summary["bundles"][0]["name_only_outcome"]["next_required_step"] == "execution"
    assert summary["bundles"][0]["completion_state"]["stage_ceiling"] == "generated"
