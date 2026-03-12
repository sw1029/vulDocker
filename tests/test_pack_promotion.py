from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator.pack import (
    _bundle_generation_provenance,
    _bundle_dynamicness_verdict,
    _bundle_dynamic_eval_summary,
    _bundle_generalization_verdict,
    _bundle_intent_satisfaction,
    _bundle_open_world_verdict,
    _bundle_researcher_summary,
    _bundle_strict_open_world_verdict,
    _dynamic_eval_summary,
    _bundle_memory_promotion_status,
    _generation_summary,
    _generalization_summary,
    _intent_satisfaction_summary,
    _memory_promotion_summary,
    _open_world_summary,
    _request_identity_summary,
    _strict_open_world_summary,
    _bundle_promotion_status,
    _promotion_summary,
)
import orchestrator.pack as pack_mod
from common.run_matrix import VulnBundle
from common.contracts import write_generator_contract


def test_bundle_promotion_is_blocked_by_semantic_contradiction(tmp_path: Path) -> None:
    plan = {"paths": {"metadata": str(tmp_path)}, "features": {"multi_vuln": False}}
    bundle = VulnBundle(vuln_id="CWE-89", slug="cwe-89", workspace_subdir="app")
    write_generator_contract(
        tmp_path,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": "sid-pack",
            "slug": "cwe-89",
            "vuln_id": "CWE-89",
            "semantic_contract": {
                "contradictions": ["semantic_contract sink conflicts with baseline CWE-89 semantics"]
            },
        },
    )

    promotion = _bundle_promotion_status(plan, bundle)

    assert promotion["eligible"] is False
    assert any("semantic_contract" in reason for reason in promotion["reasons"])


def test_bundle_generation_provenance_reads_materializer_from_generator_manifest(tmp_path: Path) -> None:
    (tmp_path / "generator_manifest.json").write_text(
        json.dumps(
            {
                "manifest": {
                    "metadata": {
                        "generation_origin": "deterministic_fallback",
                        "fallback_class": "semantic_guided",
                        "materializer": "minimal_dynamic",
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    provenance = _bundle_generation_provenance(
        "sid-pack",
        VulnBundle(vuln_id="NAME-OPEN-REDIRECT", slug="name-open-redirect", workspace_subdir="app"),
        tmp_path,
    )

    assert provenance["materializer"] == "minimal_dynamic"


def test_bundle_generation_provenance_surfaces_semantic_guided_selection_metadata(tmp_path: Path) -> None:
    (tmp_path / "generator_manifest.json").write_text(
        json.dumps(
            {
                "manifest": {
                    "metadata": {
                        "generation_origin": "deterministic_fallback",
                        "fallback_class": "semantic_guided",
                        "semantic_guided_selection_source": "request_resolution",
                        "semantic_guided_abstain_reason": "ambiguous_semantic_family_match",
                        "semantic_guided_ambiguous": True,
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    provenance = _bundle_generation_provenance(
        "sid-pack",
        VulnBundle(vuln_id="NAME-TEMPLATE-INJECTION", slug="name-template-injection", workspace_subdir="app"),
        tmp_path,
    )

    assert provenance["semantic_guided_selection_source"] == "request_resolution"
    assert provenance["semantic_guided_abstain_reason"] == "ambiguous_semantic_family_match"
    assert provenance["semantic_guided_ambiguous"] is True


def test_bundle_promotion_is_blocked_by_medium_confidence_unknown_noise(tmp_path: Path) -> None:
    plan = {"paths": {"metadata": str(tmp_path)}, "features": {"multi_vuln": False}}
    bundle = VulnBundle(vuln_id="CWE-9999", slug="cwe-9999", workspace_subdir="app")
    write_generator_contract(
        tmp_path,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": "sid-pack",
            "slug": "cwe-9999",
            "vuln_id": "CWE-9999",
            "semantic_contract": {
                "evidence_relevance": {
                    "confidence": "medium",
                    "negative_hit_ratio": 0.33,
                }
            },
        },
    )

    promotion = _bundle_promotion_status(plan, bundle)
    summary = _promotion_summary([{"slug": "cwe-9999", "promotion": promotion}])

    assert promotion["eligible"] is False
    assert any("unknown_evidence" in reason for reason in promotion["reasons"])
    assert summary["eligible"] is False


def test_bundle_promotion_is_blocked_by_low_verification_trust(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    artifacts_dir = tmp_path / "artifacts"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "run").mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "reports").mkdir(parents=True, exist_ok=True)

    plan = {
        "paths": {
            "metadata": str(metadata_dir),
            "artifacts": str(artifacts_dir),
        },
        "features": {"multi_vuln": False},
    }
    bundle = VulnBundle(vuln_id="CWE-89", slug="cwe-89", workspace_subdir="app")
    (metadata_dir / "reviewer_report.json").write_text(
        json.dumps({"blocking": False, "success": True, "blocking_bundles": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    (metadata_dir / "generator_manifest.json").write_text(
        json.dumps(
            {
                "manifest": {
                    "metadata": {
                        "compiler_family": "open_redirect",
                        "stack_scaffold_id": "python/flask",
                        "stack_scaffold_version": "1.0",
                        "fragment_id": "redirect_next_route",
                        "compose_mode": "registry",
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (metadata_dir / "generator_manifest.json").write_text(
        json.dumps(
            {
                "manifest": {
                    "metadata": {
                        "compiler_family": "open_redirect",
                        "stack_scaffold_id": "python/flask",
                        "stack_scaffold_version": "1.0",
                        "fragment_id": "redirect_next_route",
                        "compose_mode": "registry",
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (artifacts_dir / "run" / "summary.json").write_text(
        json.dumps({"run_passed": True}, ensure_ascii=False),
        encoding="utf-8",
    )
    (artifacts_dir / "reports" / "evals.json").write_text(
        json.dumps(
            {
                "results": [
                    {
                        "slug": "cwe-89",
                        "vuln_id": "CWE-89",
                        "verify_pass": True,
                        "semantic_supported": True,
                        "semantic_status": "aligned",
                        "verification_rule_source": "generator_manifest_fallback",
                        "verification_trust": "low",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    promotion = _bundle_promotion_status(plan, bundle)

    assert promotion["eligible"] is False
    assert "verify_contract:generator_manifest_fallback" in promotion["reasons"]


def test_bundle_promotion_tracks_contract_oracle_fallback_as_low_trust_contract_coupled(
    tmp_path: Path,
) -> None:
    metadata_dir = tmp_path / "metadata"
    artifacts_dir = tmp_path / "artifacts"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "run").mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "reports").mkdir(parents=True, exist_ok=True)

    plan = {
        "paths": {
            "metadata": str(metadata_dir),
            "artifacts": str(artifacts_dir),
        },
        "features": {"multi_vuln": False},
    }
    bundle = VulnBundle(vuln_id="CWE-89", slug="cwe-89", workspace_subdir="app")
    (metadata_dir / "reviewer_report.json").write_text(
        json.dumps({"blocking": False, "success": True, "blocking_bundles": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    (metadata_dir / "generator_manifest.json").write_text(
        json.dumps(
            {
                "manifest": {
                    "metadata": {
                        "generation_origin": "deterministic_fallback",
                        "fallback_class": "semantic_guided",
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (artifacts_dir / "run" / "summary.json").write_text(
        json.dumps({"run_passed": True}, ensure_ascii=False),
        encoding="utf-8",
    )
    (artifacts_dir / "reports" / "evals.json").write_text(
        json.dumps(
            {
                "results": [
                    {
                        "slug": "cwe-89",
                        "vuln_id": "CWE-89",
                        "verify_pass": True,
                        "semantic_supported": True,
                        "semantic_status": "aligned",
                        "verification_rule_source": "contract_oracle_fallback",
                        "verification_trust": "low",
                        "verification_independence": "contract_coupled",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    promotion = _bundle_promotion_status(plan, bundle)

    assert promotion["eligible"] is False
    assert "verify_contract:contract_oracle_fallback" in promotion["reasons"]
    assert "verify_independence:contract_coupled" in promotion["reasons"]


def test_bundle_promotion_is_blocked_by_name_resolution_confidence_policy(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    artifacts_dir = tmp_path / "artifacts"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "run").mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "reports").mkdir(parents=True, exist_ok=True)

    plan = {
        "paths": {
            "metadata": str(metadata_dir),
            "artifacts": str(artifacts_dir),
        },
        "features": {"multi_vuln": False},
        "requirement": {
            "vuln_id": "NAME-TEMPLATE-INJECTION",
            "name_resolution": {
                "input": "Injection in Jinja template",
                "resolved_vuln_id": "NAME-TEMPLATE-INJECTION",
                "source": "fragment_strategy_fallback",
                "match_class": "token_match",
                "confidence": "medium",
            },
            "policy": {"verifier": {"min_name_resolution_confidence": "high"}},
        },
    }
    bundle = VulnBundle(vuln_id="NAME-TEMPLATE-INJECTION", slug="name-template-injection", workspace_subdir="app")
    (metadata_dir / "reviewer_report.json").write_text(
        json.dumps({"blocking": False, "success": True, "blocking_bundles": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    (artifacts_dir / "run" / "summary.json").write_text(
        json.dumps({"run_passed": True}, ensure_ascii=False),
        encoding="utf-8",
    )
    (artifacts_dir / "reports" / "evals.json").write_text(
        json.dumps(
            {
                "results": [
                    {
                        "slug": "name-template-injection",
                        "vuln_id": "NAME-TEMPLATE-INJECTION",
                        "verify_pass": True,
                        "semantic_supported": True,
                        "semantic_status": "aligned",
                        "verification_rule_source": "compiler_runtime_rule",
                        "verification_trust": "medium",
                        "verification_independence": "compiler_coupled",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    write_generator_contract(
        metadata_dir,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": "sid-pack",
            "slug": "name-template-injection",
            "vuln_id": "NAME-TEMPLATE-INJECTION",
            "semantic_profile": {
                "normalized_vuln_id": "NAME-TEMPLATE-INJECTION",
                "support_level": "compiler_supported",
                "compiler_supported": True,
                "compiler_strategy": "template_injection_render",
                "compiler_reason": "compiler strategy and scaffold are available",
            },
        },
    )

    promotion = _bundle_promotion_status(plan, bundle)

    assert promotion["eligible"] is False
    assert "name_resolution_confidence:medium" in promotion["reasons"]
    assert "name_resolution_policy:min_high" in promotion["reasons"]


def test_bundle_promotion_is_blocked_when_known_family_verifier_reports_semantic_failure(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    artifacts_dir = tmp_path / "artifacts"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "run").mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "reports").mkdir(parents=True, exist_ok=True)
    bundle = VulnBundle(vuln_id="CWE-79", slug="cwe-79", workspace_subdir="app")
    plan = {
        "paths": {
            "metadata": str(metadata_dir),
            "artifacts": str(artifacts_dir),
        },
        "features": {"multi_vuln": False},
    }
    write_generator_contract(
        metadata_dir,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": "sid-pack",
            "slug": "cwe-79",
            "vuln_id": "CWE-79",
            "semantic_profile": {
                "schema_version": "semantic_profile@1.0",
                "sid": "sid-pack",
                "slug": "cwe-79",
                "requested_name": "XSS",
                "normalized_vuln_id": "CWE-79",
                "family": "xss",
                "support_level": "builtin_supported",
                "compiler_strategy": "xss_reflected",
                "compiler_supported": True,
                "compiler_reason": "compiler strategy and scaffold are available",
                "stack_profile": {"language": "python", "framework": "flask"},
                "scenario_shape": {"service_entry": "app.py", "poc_entry": "poc.py", "service_port": 5000},
                "semantic_signature": {
                    "input_vector": ["request.args"],
                    "sink": ["render_template_string"],
                    "exploit_precondition": ["unescaped reflection"],
                },
                "verification_contract": {"success_signature": "Exploit SUCCESS", "output_mode": "auto"},
                "derived_assertions": {"semantic_gate_required": True},
                "evidence_relevance": {},
            },
        },
    )
    (metadata_dir / "generator_manifest.json").write_text(
        json.dumps(
            {
                "manifest": {
                    "metadata": {
                        "compiler_family": "open_redirect",
                        "stack_scaffold_id": "python/flask",
                        "stack_scaffold_version": "1.0",
                        "fragment_id": "redirect_next_route",
                        "compose_mode": "registry",
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (artifacts_dir / "run" / "summary.json").write_text(json.dumps({"run_passed": True}), encoding="utf-8")
    (artifacts_dir / "reports" / "evals.json").write_text(
        json.dumps(
            {
                "results": [
                    {
                        "slug": "cwe-79",
                        "vuln_id": "CWE-79",
                        "verify_pass": True,
                        "semantic_supported": False,
                        "semantic_status": "unsupported",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (metadata_dir / "reviewer_report.json").write_text(
        json.dumps({"blocking": False, "success": True, "blocking_bundles": []}),
        encoding="utf-8",
    )

    promotion = _bundle_promotion_status(plan, bundle)

    assert promotion["eligible"] is False
    assert "verify_semantic:unsupported" in promotion["reasons"]
    assert "verify_semantic_status:unsupported" in promotion["reasons"]


def test_bundle_generalization_marks_synthetic_unknown_as_non_generalizing() -> None:
    bundle = VulnBundle(vuln_id="CWE-9999", slug="cwe-9999", workspace_subdir="app")

    verdict = _bundle_generalization_verdict(
        bundle,
        pattern_id="sqli-string-concat",
        promotion={"eligible": True},
        dynamicness={"verdict": "deterministic fallback dependent"},
        compiler_contract={},
        provenance={"generation_origin": "deterministic_fallback"},
    )
    summary = _generalization_summary([{"generalization": verdict}])

    assert verdict["class"] == "synthetic_regression"
    assert verdict["counts_as_generalization"] is False
    assert "pattern_id=sqli-string-concat" in verdict["reason"]
    assert summary["positive_generalization_bundles"] == 0
    assert summary["by_class"]["synthetic_regression"] == 1


def test_generation_summary_surfaces_template_and_registry_dependency_mix() -> None:
    summary = _generation_summary(
        [
            {
                "provenance": {"generation_origin": "built_in_template"},
                "dynamicness": {"verdict": "template-assisted"},
                "compiler_contract": {},
            },
            {
                "provenance": {"generation_origin": "compiler_generated"},
                "dynamicness": {"verdict": "compiler-first"},
                "compiler_contract": {
                    "compose_mode": "registry",
                    "stack_scaffold_id": "python/flask",
                },
            },
        ]
    )

    assert summary["by_origin"] == {"built_in_template": 1, "compiler_generated": 1}
    assert summary["by_dynamicness_verdict"] == {"template-assisted": 1, "compiler-first": 1}
    assert summary["by_compose_mode"] == {"registry": 1}
    assert summary["by_stack_scaffold_id"] == {"python/flask": 1}
    assert summary["template_origin_bundles"] == 1
    assert summary["template_assisted_bundles"] == 1
    assert summary["registry_compose_bundles"] == 1
    assert summary["scaffolded_bundles"] == 1


def test_bundle_generalization_marks_real_free_form_compiler_first_bundle_as_positive() -> None:
    bundle = VulnBundle(vuln_id="NAME-OPEN-REDIRECT", slug="name-open-redirect", workspace_subdir="app")

    verdict = _bundle_generalization_verdict(
        bundle,
        pattern_id="open-redirect",
        promotion={"eligible": True},
        dynamicness={"verdict": "compiler-first"},
        compiler_contract={"support_level": "compiler_supported", "compiler_supported": True},
        provenance={"generation_origin": "compiler_generated"},
        name_resolution={"confidence": "high", "match_class": "catalog_alias"},
    )
    summary = _generalization_summary([{"generalization": verdict}])

    assert verdict["class"] == "real_free_form_positive"
    assert verdict["counts_as_generalization"] is True
    assert verdict["confidence"] == "high"
    assert verdict["basis"] == "catalog_alias"
    assert "compiler-first" in verdict["reason"]
    assert summary["positive_generalization_bundles"] == 1
    assert summary["by_class"]["real_free_form_positive"] == 1
    assert summary["by_confidence"]["high"] == 1
    assert summary["by_basis"]["catalog_alias"] == 1


def test_bundle_generalization_surfaces_medium_confidence_token_match_for_free_form_lane() -> None:
    bundle = VulnBundle(vuln_id="NAME-TEMPLATE-INJECTION", slug="name-template-injection", workspace_subdir="app")

    verdict = _bundle_generalization_verdict(
        bundle,
        pattern_id="template-injection",
        promotion={"eligible": True},
        dynamicness={"verdict": "compiler-first"},
        compiler_contract={"support_level": "compiler_supported", "compiler_supported": True},
        provenance={"generation_origin": "compiler_generated"},
        name_resolution={"confidence": "medium", "match_class": "token_match"},
    )

    assert verdict["class"] == "real_free_form_non_generalizing"
    assert verdict["counts_as_generalization"] is False
    assert verdict["confidence"] == "medium"


def test_bundle_generalization_uses_request_ir_for_alias_resolved_dynamic_name_only_lane() -> None:
    bundle = VulnBundle(vuln_id="CWE-89", slug="cwe-89", workspace_subdir="app")

    verdict = _bundle_generalization_verdict(
        bundle,
        pattern_id="sqli-string-concat",
        promotion={"eligible": True},
        dynamicness={"verdict": "deterministic fallback dependent"},
        compiler_contract={"support_level": "builtin_supported", "compiler_supported": True},
        provenance={
            "generation_origin": "deterministic_fallback",
            "fallback_class": "semantic_guided",
            "materializer": "minimal_dynamic",
        },
        policy={"name_only_mode": "dynamic"},
        request_ir={
            "name_driven": True,
            "resolved_vuln_id": "CWE-89",
            "resolution_confidence": "high",
            "resolution_match_class": "catalog_alias",
        },
        name_resolution={"confidence": "high", "match_class": "catalog_alias"},
    )

    assert verdict["class"] == "real_free_form_non_generalizing"
    assert verdict["counts_as_generalization"] is False
    assert verdict["confidence"] == "high"
    assert verdict["basis"] == "catalog_alias"
    assert "high/catalog_alias" in verdict["reason"]


def test_bundle_open_world_marks_catalog_resolved_name_only_lane_as_lower_bound_dependent() -> None:
    bundle = VulnBundle(vuln_id="NAME-OPEN-REDIRECT", slug="name-open-redirect", workspace_subdir="app")

    verdict = _bundle_open_world_verdict(
        bundle,
        pattern_id="open-redirect",
        promotion={"eligible": True},
        dynamicness={"verdict": "compiler-first"},
        compiler_contract={"support_level": "compiler_supported", "compiler_supported": True},
        provenance={"generation_origin": "compiler_generated"},
        name_resolution={"confidence": "high", "match_class": "catalog_alias"},
    )
    summary = _open_world_summary(
        [
            {
                "open_world": verdict,
            }
        ]
    )

    assert verdict["class"] == "catalog_resolved_lower_bound"
    assert verdict["counts_as_generalization"] is False
    assert verdict["lower_bound_dependent"] is True
    assert verdict["template_dependent"] is False
    assert verdict["confidence"] == "high"
    assert verdict["basis"] == "catalog_alias"
    assert "curated lower-bound evidence" in verdict["reason"]
    assert summary["positive_open_world_bundles"] == 0
    assert summary["lower_bound_dependent_bundles"] == 1
    assert summary["by_class"]["catalog_resolved_lower_bound"] == 1


def test_bundle_open_world_separates_semantic_guided_degraded_name_only_lane() -> None:
    bundle = VulnBundle(vuln_id="NAME-OPEN-REDIRECT", slug="name-open-redirect", workspace_subdir="app")

    verdict = _bundle_open_world_verdict(
        bundle,
        pattern_id="open-redirect",
        promotion={"eligible": True},
        dynamicness={"verdict": "deterministic fallback dependent"},
        compiler_contract={"support_level": "compiler_supported", "compiler_supported": True},
        provenance={"generation_origin": "deterministic_fallback", "fallback_class": "semantic_guided"},
        name_resolution={"confidence": "high", "match_class": "catalog_alias"},
    )
    summary = _open_world_summary([{"open_world": verdict}])

    assert verdict["class"] == "semantic_guided_degraded"
    assert verdict["counts_as_generalization"] is False
    assert verdict["lower_bound_dependent"] is True
    assert verdict["confidence"] == "high"
    assert verdict["basis"] == "catalog_alias"
    assert "semantic-guided deterministic fallback" in verdict["reason"]
    assert summary["lower_bound_dependent_bundles"] == 1
    assert summary["by_class"]["semantic_guided_degraded"] == 1


def test_bundle_open_world_separates_minimal_dynamic_name_only_lane() -> None:
    bundle = VulnBundle(vuln_id="NAME-OPEN-REDIRECT", slug="name-open-redirect", workspace_subdir="app")

    verdict = _bundle_open_world_verdict(
        bundle,
        pattern_id="open-redirect",
        promotion={"eligible": True},
        dynamicness={"verdict": "deterministic fallback dependent"},
        compiler_contract={"support_level": "compiler_supported", "compiler_supported": True},
        provenance={
            "generation_origin": "deterministic_fallback",
            "fallback_class": "semantic_guided",
            "materializer": "minimal_dynamic",
        },
        name_resolution={"confidence": "high", "match_class": "catalog_alias"},
    )
    summary = _open_world_summary([{"open_world": verdict}])

    assert verdict["class"] == "semantic_guided_minimal_dynamic"
    assert verdict["counts_as_generalization"] is False
    assert verdict["lower_bound_dependent"] is True
    assert summary["by_class"]["semantic_guided_minimal_dynamic"] == 1


def test_bundle_open_world_uses_request_ir_for_alias_resolved_name_only_minimal_dynamic() -> None:
    bundle = VulnBundle(vuln_id="CWE-89", slug="cwe-89", workspace_subdir="app")

    verdict = _bundle_open_world_verdict(
        bundle,
        pattern_id="sqli-string-concat",
        promotion={"eligible": True},
        dynamicness={"verdict": "deterministic fallback dependent"},
        compiler_contract={"support_level": "builtin_supported", "compiler_supported": True},
        provenance={
            "generation_origin": "deterministic_fallback",
            "fallback_class": "semantic_guided",
            "materializer": "minimal_dynamic",
        },
        request_ir={
            "name_driven": True,
            "resolved_vuln_id": "CWE-89",
            "resolution_confidence": "high",
            "resolution_match_class": "catalog_alias",
        },
        name_resolution={"confidence": "high", "match_class": "catalog_alias"},
    )

    assert verdict["class"] == "semantic_guided_minimal_dynamic"
    assert verdict["counts_as_generalization"] is False
    assert verdict["lower_bound_dependent"] is True
    assert verdict["basis"] == "catalog_alias"


def test_bundle_open_world_marks_dynamic_name_only_generator_failure_as_attempt_failure() -> None:
    bundle = VulnBundle(vuln_id="NAME-OPEN-REDIRECT", slug="name-open-redirect", workspace_subdir="app")

    verdict = _bundle_open_world_verdict(
        bundle,
        pattern_id="open-redirect",
        promotion={"eligible": False},
        dynamicness={"verdict": "deterministic fallback dependent"},
        compiler_contract={"support_level": "compiler_supported", "compiler_supported": True},
        provenance={"generation_origin": "deterministic_fallback", "fallback_class": "generic_unsupported_family"},
        dynamic_eval={"enabled": True, "attempted": True, "status": "dynamic_failed"},
        failure={"stage": "GENERATOR", "terminal_failure_class": "guard_semantic_mismatch"},
        name_resolution={"confidence": "high", "match_class": "catalog_alias"},
    )

    assert verdict["class"] == "name_driven_dynamic_failed"
    assert verdict["lower_bound_dependent"] is False
    assert "attempted dynamic generation first" in verdict["reason"]


def test_bundle_open_world_marks_template_lane_as_template_dependent() -> None:
    bundle = VulnBundle(vuln_id="CWE-89", slug="cwe-89", workspace_subdir="app")

    verdict = _bundle_open_world_verdict(
        bundle,
        pattern_id="sqli-union-mysql",
        promotion={"eligible": True},
        dynamicness={"verdict": "template-assisted"},
        compiler_contract={"support_level": "builtin_supported", "compiler_supported": True},
        provenance={"generation_origin": "built_in_template"},
    )
    summary = _open_world_summary(
        [
            {
                "open_world": verdict,
            }
        ]
    )

    assert verdict["class"] == "known_family_regression"
    assert verdict["template_dependent"] is True
    assert verdict["lower_bound_dependent"] is True
    assert summary["template_dependent_bundles"] == 1
    assert summary["lower_bound_dependent_bundles"] == 1


def test_bundle_strict_open_world_excludes_curated_lower_bound_lane() -> None:
    bundle = VulnBundle(vuln_id="NAME-OPEN-REDIRECT", slug="name-open-redirect", workspace_subdir="app")

    verdict = _bundle_strict_open_world_verdict(
        bundle,
        open_world={
            "class": "catalog_resolved_lower_bound",
            "counts_as_generalization": False,
            "lower_bound_dependent": True,
            "template_dependent": False,
        },
        dynamicness={"verdict": "compiler-first"},
        provenance={"generation_origin": "compiler_generated"},
        lower_bound={"effective_non_remote_available": True},
        verification={"rule_source": "declared_rule", "trust": "high", "independence": "independent"},
        researcher={"report_present": True, "quality": "skipped", "search_degraded": False},
        semantic={"supported": True, "status": "aligned"},
    )
    summary = _strict_open_world_summary([{"strict_open_world": verdict}])

    assert verdict["class"] == "strict_curated_lower_bound"
    assert verdict["counts_as_generalization"] is False
    assert verdict["lower_bound_dependent"] is True
    assert summary["positive_strict_open_world_bundles"] == 0
    assert summary["lower_bound_dependent_bundles"] == 1
    assert summary["by_class"]["strict_curated_lower_bound"] == 1


def test_bundle_strict_open_world_separates_semantic_guided_fallback_lane() -> None:
    bundle = VulnBundle(vuln_id="NAME-OPEN-REDIRECT", slug="name-open-redirect", workspace_subdir="app")

    verdict = _bundle_strict_open_world_verdict(
        bundle,
        open_world={
            "class": "semantic_guided_degraded",
            "counts_as_generalization": False,
            "lower_bound_dependent": True,
            "template_dependent": False,
        },
        dynamicness={"verdict": "deterministic fallback dependent"},
        provenance={"generation_origin": "deterministic_fallback", "fallback_class": "semantic_guided"},
        lower_bound={"effective_non_remote_available": True},
        verification={"rule_source": "declared_rule", "trust": "high", "independence": "independent"},
        researcher={"report_present": True, "quality": "sufficient", "search_degraded": False},
        semantic={"supported": True, "status": "aligned"},
    )
    summary = _strict_open_world_summary([{"strict_open_world": verdict}])

    assert verdict["class"] == "strict_semantic_guided_fallback"
    assert verdict["counts_as_generalization"] is False
    assert verdict["lower_bound_dependent"] is True
    assert summary["lower_bound_dependent_bundles"] == 1
    assert summary["by_class"]["strict_semantic_guided_fallback"] == 1


def test_bundle_strict_open_world_separates_minimal_dynamic_fallback_lane() -> None:
    bundle = VulnBundle(vuln_id="NAME-OPEN-REDIRECT", slug="name-open-redirect", workspace_subdir="app")

    verdict = _bundle_strict_open_world_verdict(
        bundle,
        open_world={
            "class": "semantic_guided_minimal_dynamic",
            "counts_as_generalization": False,
            "lower_bound_dependent": True,
            "template_dependent": False,
        },
        dynamicness={"verdict": "deterministic fallback dependent"},
        provenance={
            "generation_origin": "deterministic_fallback",
            "fallback_class": "semantic_guided",
            "materializer": "minimal_dynamic",
        },
        lower_bound={"effective_non_remote_available": True},
        verification={"rule_source": "declared_rule", "trust": "high", "independence": "independent"},
        researcher={"report_present": True, "quality": "sufficient", "search_degraded": False},
        semantic={"supported": True, "status": "aligned"},
    )
    summary = _strict_open_world_summary([{"strict_open_world": verdict}])

    assert verdict["class"] == "strict_minimal_dynamic_fallback"
    assert summary["by_class"]["strict_minimal_dynamic_fallback"] == 1


def test_bundle_strict_open_world_marks_dynamic_name_only_generator_failure() -> None:
    bundle = VulnBundle(vuln_id="NAME-OPEN-REDIRECT", slug="name-open-redirect", workspace_subdir="app")

    verdict = _bundle_strict_open_world_verdict(
        bundle,
        open_world={
            "class": "name_driven_dynamic_failed",
            "counts_as_generalization": False,
            "lower_bound_dependent": False,
            "template_dependent": False,
        },
        dynamicness={"verdict": "deterministic fallback dependent"},
        provenance={"generation_origin": "deterministic_fallback", "fallback_class": "generic_unsupported_family"},
        lower_bound={"effective_non_remote_available": True},
        verification={"rule_source": "declared_rule", "trust": "high", "independence": "independent"},
        researcher={"report_present": True, "quality": "sufficient", "search_degraded": False},
        semantic={"supported": True, "status": "aligned"},
        dynamic_eval={"enabled": True, "attempted": True, "status": "dynamic_failed"},
        failure={"stage": "GENERATOR", "terminal_failure_class": "guard_semantic_mismatch"},
    )

    assert verdict["class"] == "strict_dynamic_generation_failed"
    assert verdict["lower_bound_dependent"] is False


def test_bundle_strict_open_world_excludes_fixture_backed_dynamic_lane() -> None:
    bundle = VulnBundle(vuln_id="CWE-89", slug="cwe-89", workspace_subdir="app")

    verdict = _bundle_strict_open_world_verdict(
        bundle,
        open_world={
            "class": "open_world_positive",
            "counts_as_generalization": True,
            "lower_bound_dependent": False,
            "template_dependent": False,
        },
        dynamicness={"verdict": "trusted dynamic"},
        provenance={"generation_origin": "llm_manifest", "llm_fixture_used": True},
        lower_bound={"effective_non_remote_available": False},
        verification={"rule_source": "declared_rule", "trust": "high", "independence": "independent"},
        researcher={"report_present": True, "quality": "sufficient", "search_degraded": False},
        semantic={"supported": True, "status": "aligned"},
    )
    summary = _strict_open_world_summary([{"strict_open_world": verdict}])

    assert verdict["class"] == "strict_fixture_backed_dynamic"
    assert verdict["fixture_backed"] is True
    assert verdict["counts_as_generalization"] is False
    assert summary["fixture_backed_bundles"] == 1
    assert summary["positive_strict_open_world_bundles"] == 0


def test_bundle_strict_open_world_prefers_template_specific_exclusion() -> None:
    bundle = VulnBundle(vuln_id="CWE-89", slug="cwe-89", workspace_subdir="app")

    verdict = _bundle_strict_open_world_verdict(
        bundle,
        open_world={
            "class": "known_family_regression",
            "counts_as_generalization": False,
            "lower_bound_dependent": True,
            "template_dependent": True,
        },
        dynamicness={"verdict": "template-assisted"},
        provenance={"generation_origin": "built_in_template"},
        lower_bound={"effective_non_remote_available": True},
        verification={"rule_source": "declared_rule", "trust": "high", "independence": "independent"},
        researcher={"report_present": True, "quality": "skipped", "search_degraded": False},
        semantic={"supported": True, "status": "aligned"},
    )

    assert verdict["class"] == "strict_template_dependent"
    assert verdict["template_dependent"] is True


def test_bundle_strict_open_world_prefers_fixture_specific_exclusion_over_lower_bound() -> None:
    bundle = VulnBundle(vuln_id="CWE-89", slug="cwe-89", workspace_subdir="app")

    verdict = _bundle_strict_open_world_verdict(
        bundle,
        open_world={
            "class": "known_family_regression",
            "counts_as_generalization": False,
            "lower_bound_dependent": True,
            "template_dependent": False,
        },
        dynamicness={"verdict": "trusted dynamic"},
        provenance={"generation_origin": "llm_manifest", "llm_fixture_used": True},
        lower_bound={"effective_non_remote_available": True},
        verification={"rule_source": "declared_rule", "trust": "high", "independence": "independent"},
        researcher={"report_present": True, "quality": "sufficient", "search_degraded": False},
        semantic={"supported": True, "status": "aligned"},
    )

    assert verdict["class"] == "strict_fixture_backed_dynamic"
    assert verdict["fixture_backed"] is True


def test_write_manifest_surfaces_researcher_summary_and_bundle_researcher_state(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-pack-researcher-summary"
    metadata_dir = tmp_path / "metadata" / sid
    artifacts_dir = tmp_path / "artifacts" / sid
    workspace_dir = tmp_path / "workspaces" / sid / "app"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "run").mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "reports").mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "loop_state.json").write_text(
        json.dumps({"sid": sid, "last_result": "success"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (metadata_dir / "researcher_report.json").write_text(
        json.dumps(
            {
                "sid": sid,
                "vuln_id": "CWE-89",
                "quality": "skipped",
                "quality_reason": "researcher skipped: compiler/static supported bundle",
                "search_policy": "remote_prefer",
                "search_degraded": False,
                "semantic_signature_source": ["baseline"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (artifacts_dir / "run" / "summary.json").write_text(json.dumps({"run_passed": True}), encoding="utf-8")
    (artifacts_dir / "reports" / "evals.json").write_text(
        json.dumps({"results": [{"slug": "cwe-89", "vuln_id": "CWE-89", "verify_pass": True}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (metadata_dir / "reviewer_report.json").write_text(
        json.dumps({"blocking": False, "success": True, "blocking_bundles": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    plan = {
        "sid": sid,
        "paths": {
            "metadata": str(metadata_dir),
            "artifacts": str(artifacts_dir),
            "workspace": str(workspace_dir),
        },
        "requirement": {"vuln_id": "CWE-89", "researcher": {"shadow_mode": True, "search_policy": "remote_prefer"}},
        "run_matrix": {"vuln_bundles": [{"vuln_id": "CWE-89", "slug": "cwe-89", "workspace_subdir": "app"}]},
        "features": {"multi_vuln": False},
    }
    monkeypatch.setattr(pack_mod, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)
    monkeypatch.setattr(pack_mod, "get_artifacts_dir", lambda incoming_sid: tmp_path / "artifacts" / incoming_sid)

    manifest_path = pack_mod.write_manifest(sid, plan)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["researcher_summary"]["shadow_mode_bundles"] == 1
    assert manifest["researcher_summary"]["report_present_bundles"] == 1
    assert manifest["researcher_summary"]["by_quality"] == {"skipped": 1}
    assert manifest["researcher"]["quality"] == "skipped"
    assert manifest["researcher"]["shadow_mode_enabled"] is True


def test_write_manifest_surfaces_strict_open_world_summary(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-pack-strict-open-world"
    metadata_dir = tmp_path / "metadata" / sid
    artifacts_dir = tmp_path / "artifacts" / sid
    workspace_dir = tmp_path / "workspaces" / sid / "app"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "run").mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "reports").mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    (workspace_dir / "README.md").write_text("# bundle\n", encoding="utf-8")
    (metadata_dir / "loop_state.json").write_text(
        json.dumps({"sid": sid, "last_result": "success"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (metadata_dir / "researcher_report.json").write_text(
        json.dumps(
            {
                "sid": sid,
                "vuln_id": "NAME-OPEN-REDIRECT",
                "quality": "skipped",
                "quality_reason": "researcher skipped: compiler/static supported path",
                "search_policy": "remote_prefer",
                "search_degraded": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (artifacts_dir / "run" / "summary.json").write_text(
        json.dumps({"run_passed": True, "executed": True, "service_port": 5000}, ensure_ascii=False),
        encoding="utf-8",
    )
    (artifacts_dir / "reports" / "evals.json").write_text(
        json.dumps(
            {
                "results": [
                    {
                        "slug": "name-open-redirect",
                        "vuln_id": "NAME-OPEN-REDIRECT",
                        "verify_pass": True,
                        "semantic_supported": True,
                        "semantic_status": "aligned",
                        "verification_rule_source": "declared_rule",
                        "verification_trust": "high",
                        "verification_independence": "independent",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (metadata_dir / "reviewer_report.json").write_text(
        json.dumps({"blocking": False, "success": True, "blocking_bundles": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    write_generator_contract(
        metadata_dir,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": sid,
            "slug": "name-open-redirect",
            "vuln_id": "NAME-OPEN-REDIRECT",
            "service_entry": "app.py",
            "poc_entry": "poc.py",
            "service_port": 5000,
            "output_mode": "auto",
            "provenance": {"generation_origin": "compiler_generated"},
            "semantic_profile": {
                "normalized_vuln_id": "NAME-OPEN-REDIRECT",
                "support_level": "compiler_supported",
                "compiler_supported": True,
                "compiler_strategy": "open_redirect_reflect",
                "compiler_reason": "compiler strategy and scaffold are available",
            },
        },
    )
    plan = {
        "sid": sid,
        "paths": {
            "metadata": str(metadata_dir),
            "artifacts": str(artifacts_dir),
            "workspace": str(workspace_dir),
        },
        "requirement": {"vuln_id": "NAME-OPEN-REDIRECT", "policy": {}, "name_resolution": {
            "input": "Open Redirect",
            "resolved_vuln_id": "NAME-OPEN-REDIRECT",
            "source": "alias",
            "match_class": "catalog_alias",
            "confidence": "high",
        }},
        "run_matrix": {"vuln_bundles": [{"vuln_id": "NAME-OPEN-REDIRECT", "slug": "name-open-redirect", "workspace_subdir": "app"}]},
        "features": {"multi_vuln": False},
    }
    monkeypatch.setattr(pack_mod, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)
    monkeypatch.setattr(pack_mod, "get_artifacts_dir", lambda incoming_sid: tmp_path / "artifacts" / incoming_sid)
    monkeypatch.setattr(pack_mod, "get_workspace_dir", lambda incoming_sid: tmp_path / "workspaces" / incoming_sid)

    manifest_path = pack_mod.write_manifest(sid, plan)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["strict_open_world_summary"]["positive_strict_open_world_bundles"] == 0
    assert manifest["strict_open_world_summary"]["by_class"]["strict_curated_lower_bound"] == 1
    assert manifest["strict_open_world_class"] == "strict_curated_lower_bound"
    assert manifest["counts_as_strict_open_world_generalization"] is False


def test_bundle_memory_promotion_rejects_curated_lower_bound_lane() -> None:
    status = _bundle_memory_promotion_status(
        {
            "promotion": {"eligible": True, "reasons": []},
            "strict_open_world": {"class": "strict_curated_lower_bound", "counts_as_generalization": False},
            "artifact_quality": {"band": "high", "oracle_clarity": "high", "topology_clarity": "high"},
        }
    )
    summary = _memory_promotion_summary(
        [{"slug": "name-open-redirect", "memory_promotion": status}]
    )

    assert status["eligible"] is False
    assert "strict_open_world:strict_curated_lower_bound" in status["reasons"]
    assert summary["eligible_bundles"] == 0


def test_bundle_memory_promotion_accepts_high_quality_strict_open_world_bundle() -> None:
    status = _bundle_memory_promotion_status(
        {
            "promotion": {"eligible": True, "reasons": []},
            "strict_open_world": {"class": "strict_open_world_positive", "counts_as_generalization": True},
            "artifact_quality": {"band": "high", "oracle_clarity": "high", "topology_clarity": "high"},
        }
    )
    summary = _memory_promotion_summary([{"slug": "cwe-unknown", "memory_promotion": status}])

    assert status["eligible"] is True
    assert status["reasons"] == []
    assert summary["eligible_bundles"] == 1
    assert summary["all_eligible"] is True


def test_request_identity_summary_tracks_input_modes_and_resolution_classes() -> None:
    summary = _request_identity_summary(
        [
            {
                "request_identity": {
                    "input_mode": "free_form_name",
                    "match_class": "catalog_alias",
                    "confidence": "high",
                    "name_driven": True,
                    "synthetic_resolution": False,
                }
            },
            {
                "request_identity": {
                    "input_mode": "free_form_name",
                    "match_class": "token_match",
                    "confidence": "medium",
                    "name_driven": True,
                    "synthetic_resolution": False,
                }
            },
            {
                "request_identity": {
                    "input_mode": "free_form_name",
                    "match_class": "synthetic_name",
                    "confidence": "low",
                    "name_driven": True,
                    "synthetic_resolution": True,
                }
            },
        ]
    )

    assert summary["bundle_count"] == 3
    assert summary["name_driven_bundles"] == 3
    assert summary["synthetic_resolution_bundles"] == 1
    assert summary["by_input_mode"] == {"free_form_name": 3}
    assert summary["by_match_class"] == {"catalog_alias": 1, "token_match": 1, "synthetic_name": 1}
    assert summary["by_confidence"] == {"high": 1, "medium": 1, "low": 1}


def test_bundle_intent_satisfaction_surfaces_extended_name_only_contract() -> None:
    payload = _bundle_intent_satisfaction(
        {
            "vuln_id": "NAME-OPEN-REDIRECT",
            "request_identity": {"name_driven": True},
            "request_ir": {"name_driven": True},
            "dynamic_eval": {"enabled": True, "status": "degraded_success"},
            "open_world": {"class": "semantic_guided_minimal_dynamic"},
            "strict_open_world": {"class": "strict_minimal_dynamic_fallback"},
            "provenance": {
                "generation_origin": "deterministic_fallback",
                "fallback_class": "semantic_guided",
                "llm_stub_used": True,
            },
            "verification": {"independence": "independent", "trust": "high"},
            "researcher": {"quality": "sufficient"},
        },
        {"policy": {"name_only_mode": "dynamic"}, "request_identity": {"name_driven": True}},
    )

    assert payload["mode"] == "dynamic"
    assert payload["status"] == "degraded_dynamic_success"
    assert payload["required_contract"]["allowed_closure_sources"] == ["trusted_dynamic", "strict_open_world_positive"]
    assert payload["required_contract"]["allowed_llm_paths"] == ["live", "fixture", "stub"]
    assert payload["required_contract"]["intent_success_rule"] == "open_world_positive_only"


def test_bundle_researcher_summary_does_not_count_skip_report_as_ran(tmp_path: Path) -> None:
    (tmp_path / "researcher_report.json").write_text(
        json.dumps(
            {
                "quality": "skipped",
                "quality_reason": "researcher skipped: compiler/static supported path",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary = _bundle_researcher_summary(
        requirement={"researcher": {"shadow_mode": False}, "policy": {"dynamic_eval": True}},
        metadata_dir=tmp_path,
    )

    assert summary["report_present"] is True
    assert summary["ran"] is False
    assert summary["dynamic_eval_enabled"] is True
    assert summary["quality"] == "skipped"


def test_bundle_researcher_summary_uses_request_ir_for_alias_resolved_name_only_mode(tmp_path: Path) -> None:
    (tmp_path / "researcher_report.json").write_text(
        json.dumps(
            {
                "quality": "skipped",
                "quality_reason": "researcher skipped: compiler/static supported path",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary = _bundle_researcher_summary(
        requirement={
            "vuln_id": "CWE-89",
            "request_ir": {"name_driven": True},
            "policy": {"name_only_mode": "dynamic"},
            "researcher": {"shadow_mode": False},
        },
        metadata_dir=tmp_path,
    )

    assert summary["report_present"] is True
    assert summary["dynamic_eval_enabled"] is True
    assert summary["ran"] is False


def test_bundle_researcher_summary_surfaces_family_hypothesis_and_query_target_stats(tmp_path: Path) -> None:
    (tmp_path / "researcher_report.json").write_text(
        json.dumps(
            {
                "quality": "sufficient",
                "query_plan": {
                    "family_hypotheses": [{"family": "open_redirect", "confidence": "high", "basis": "request_label"}]
                },
                "evidence_type_summary": {
                    "by_type": {"advisory": 2, "reference_impl": 1},
                    "matched_target_count": 2,
                    "hit_count": 4,
                },
                "family_hypothesis_summary": {
                    "top_family": "open_redirect",
                    "top_confidence": "high",
                    "raw_top_confidence": "high",
                    "contradiction_count": 1,
                    "top_margin": 0.18,
                    "ambiguous": True,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary = _bundle_researcher_summary(
        requirement={"researcher": {"shadow_mode": False}, "policy": {"dynamic_eval": True}},
        metadata_dir=tmp_path,
    )

    assert summary["query_plan_present"] is True
    assert summary["query_plan_family_hypothesis_count"] == 1
    assert summary["top_family_hypothesis"] == "open_redirect"
    assert summary["top_family_hypothesis_confidence"] == "high"
    assert summary["top_family_hypothesis_raw_confidence"] == "high"
    assert summary["family_hypothesis_contradictions"] == 1
    assert summary["top_family_hypothesis_margin"] == 0.18
    assert summary["family_hypothesis_ambiguous"] is True
    assert summary["evidence_types"] == {"advisory": 2, "reference_impl": 1}
    assert summary["query_target_match_rate"] == 0.5


def test_researcher_summary_rolls_up_top_family_and_contradictions() -> None:
    summary = pack_mod._researcher_summary(
        [
            {
                "researcher": {
                    "report_present": True,
                    "ran": True,
                    "quality": "sufficient",
                    "query_plan_present": True,
                    "top_family_hypothesis": "open_redirect",
                    "top_family_hypothesis_confidence": "high",
                    "family_hypothesis_contradictions": 0,
                    "family_hypothesis_ambiguous": False,
                    "query_target_match_rate": 0.25,
                }
            },
            {
                "researcher": {
                    "report_present": True,
                    "ran": True,
                    "quality": "insufficient",
                    "query_plan_present": True,
                    "top_family_hypothesis": "template_injection",
                    "top_family_hypothesis_confidence": "low",
                    "family_hypothesis_contradictions": 2,
                    "family_hypothesis_ambiguous": True,
                    "query_target_match_rate": 0.75,
                }
            },
        ]
    )

    assert summary["query_plan_bundles"] == 2
    assert summary["contradiction_bundles"] == 1
    assert summary["ambiguous_family_hypothesis_bundles"] == 1
    assert summary["by_top_family_hypothesis"] == {
        "open_redirect": 1,
        "template_injection": 1,
    }
    assert summary["by_top_family_confidence"] == {"high": 1, "low": 1}
    assert summary["avg_query_target_match_rate"] == 0.5


def test_template_dependence_summary_tracks_minimal_dynamic_materializers() -> None:
    summary = pack_mod._template_dependence_summary(
        [
            {
                "dynamicness": {"verdict": "deterministic fallback dependent"},
                "provenance": {"materializer": "minimal_dynamic"},
                "open_world": {"class": "semantic_guided_minimal_dynamic", "lower_bound_dependent": True},
                "vuln_id": "NAME-OPEN-REDIRECT",
            }
        ]
    )

    assert summary["minimal_dynamic_bundles"] == 1
    assert summary["by_open_world_class"]["semantic_guided_minimal_dynamic"] == 1


def test_template_dependence_summary_counts_request_ir_name_only_lower_bound_bundles() -> None:
    summary = pack_mod._template_dependence_summary(
        [
            {
                "dynamicness": {"verdict": "deterministic fallback dependent"},
                "provenance": {"materializer": "minimal_dynamic"},
                "open_world": {"class": "semantic_guided_minimal_dynamic", "lower_bound_dependent": True},
                "vuln_id": "CWE-89",
                "request_ir": {"name_driven": True},
            }
        ]
    )

    assert summary["name_only_lower_bound_bundles"] == 1
    assert summary["minimal_dynamic_bundles"] == 1


def test_stack_dependence_summary_tracks_repo_prior_and_researcher_sources() -> None:
    summary = pack_mod._stack_dependence_summary(
        [
            {
                "stack_dependence": {
                    "class": "repo_prior_bounded",
                    "stack_source": "profile_prior",
                    "repo_prior_bounded": True,
                    "researcher_inferred": False,
                    "ambiguous": True,
                    "stack_locked": False,
                }
            },
            {
                "stack_dependence": {
                    "class": "researcher_inferred",
                    "stack_source": "researcher_candidate",
                    "repo_prior_bounded": False,
                    "researcher_inferred": True,
                    "ambiguous": False,
                    "stack_locked": False,
                }
            },
        ]
    )

    assert summary["repo_prior_bounded_bundles"] == 1
    assert summary["researcher_inferred_bundles"] == 1
    assert summary["ambiguous_bundles"] == 1
    assert summary["by_class"] == {"repo_prior_bounded": 1, "researcher_inferred": 1}
    assert summary["by_stack_source"] == {"profile_prior": 1, "researcher_candidate": 1}


def test_family_dependence_summary_tracks_semantic_signature_and_unresolved_fallbacks() -> None:
    summary = pack_mod._family_dependence_summary(
        [
            {
                "family_dependence": {
                    "class": "semantic_signature_bounded",
                    "name_only": True,
                    "family_bounded": True,
                    "ambiguous": False,
                    "selection_source": "semantic_signature",
                    "abstain_reason": None,
                }
            },
            {
                "family_dependence": {
                    "class": "family_unresolved_generic_fallback",
                    "name_only": True,
                    "family_bounded": False,
                    "ambiguous": True,
                    "selection_source": None,
                    "abstain_reason": "ambiguous_semantic_family_match",
                }
            },
        ]
    )

    assert summary["name_only_bundles"] == 2
    assert summary["family_bounded_bundles"] == 1
    assert summary["ambiguous_bundles"] == 1
    assert summary["by_class"] == {
        "semantic_signature_bounded": 1,
        "family_unresolved_generic_fallback": 1,
    }
    assert summary["by_selection_source"] == {"semantic_signature": 1}
    assert summary["by_abstain_reason"] == {"ambiguous_semantic_family_match": 1}


def test_bundle_artifact_quality_uses_exploit_oracle_when_verification_is_missing(tmp_path: Path) -> None:
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    (workspace_dir / "README.md").write_text(
        "\n".join(
            [
                "# dynamic bundle",
                "",
                "docker build -t demo .",
                "docker run -p 8000:8000 demo",
                "python poc.py --base-url http://127.0.0.1:8000",
                "",
                "Verification markers",
                "Success signature: `Exploit SUCCESS`",
                "Flag token: `FLAG{PATH_TRAVERSAL_OK}`",
                "Runtime expects a single-service HTTP container on port `8000`.",
            ]
        ),
        encoding="utf-8",
    )

    quality = pack_mod._bundle_artifact_quality(
        {
            "paths": {"workspace": str(workspace_dir)},
            "runtime_recipe": {"topology": "single_service", "service_port": 8000},
            "provenance": {"generation_origin": "deterministic_fallback", "fallback_used": True},
            "exploit_oracle": {
                "success_signature": "Exploit SUCCESS",
                "flag_token": "FLAG{PATH_TRAVERSAL_OK}",
                "poc_cmd": "python poc.py --base-url {{base_url}}",
            },
        }
    )

    assert quality["oracle_clarity"] == "high"
    assert any("deterministic fallback bundle" in note for note in quality["notes"])


def test_bundle_dynamic_eval_summary_reads_status_file(tmp_path: Path) -> None:
    (tmp_path / "dynamic_eval.json").write_text(
        json.dumps(
            {
                "enabled": True,
                "attempted": True,
                "status": "lower_bound_recovered",
                "lower_bound_fallback_used": True,
                "fallback_path": "compiler",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary = _bundle_dynamic_eval_summary(
        requirement={"policy": {"dynamic_eval": True}},
        metadata_dir=tmp_path,
    )

    assert summary["enabled"] is True
    assert summary["attempted"] is True
    assert summary["status"] == "lower_bound_recovered"
    assert summary["lower_bound_fallback_used"] is True
    assert summary["fallback_path"] == "compiler"


def test_bundle_dynamic_eval_summary_uses_request_ir_for_alias_resolved_name_only_mode(tmp_path: Path) -> None:
    summary = _bundle_dynamic_eval_summary(
        requirement={
            "vuln_id": "CWE-89",
            "policy": {"name_only_mode": "dynamic"},
            "request_ir": {"name_driven": True},
        },
        metadata_dir=tmp_path,
    )

    assert summary["enabled"] is True
    assert summary["attempted"] is True


def test_dynamic_eval_rollup_tracks_attempted_and_recovered_bundles() -> None:
    summary = _dynamic_eval_summary(
        [
            {"dynamic_eval": {"enabled": True, "attempted": True, "status": "dynamic_failed"}},
            {
                "dynamic_eval": {
                    "enabled": True,
                    "attempted": True,
                    "status": "lower_bound_recovered",
                    "lower_bound_fallback_used": True,
                    "fallback_path": "compiler",
                }
            },
        ]
    )

    assert summary["enabled_bundles"] == 2
    assert summary["attempted_bundles"] == 2
    assert summary["lower_bound_recovered_bundles"] == 1
    assert summary["by_status"] == {"dynamic_failed": 1, "lower_bound_recovered": 1}
    assert summary["by_fallback_path"] == {"compiler": 1}


def test_bundle_intent_satisfaction_marks_dynamic_degraded_success_as_partial() -> None:
    payload = _bundle_intent_satisfaction(
        {
            "vuln_id": "NAME-OPEN-REDIRECT",
            "request_identity": {"name_driven": True},
            "dynamic_eval": {"enabled": True, "status": "degraded_success"},
            "provenance": {
                "generation_origin": "deterministic_fallback",
                "fallback_class": "semantic_guided",
                "llm_stub_used": True,
            },
            "researcher": {"quality": "sufficient"},
            "verification": {"independence": "independent", "trust": "high"},
            "open_world": {"class": "semantic_guided_minimal_dynamic"},
            "strict_open_world": {"class": "strict_minimal_dynamic_fallback"},
        },
        {"policy": {"name_only_mode": "dynamic"}},
    )

    assert payload["mode"] == "dynamic"
    assert payload["status"] == "degraded_dynamic_success"
    assert payload["meets_intent"] is False
    assert payload["partial"] is True
    assert payload["closure_source"] == "degraded_deterministic_fallback"
    assert payload["llm_path"] == "stub"
    assert payload["research_quality"] == "sufficient"


def test_bundle_intent_satisfaction_preserves_generation_closure_source_when_executor_fails() -> None:
    payload = _bundle_intent_satisfaction(
        {
            "vuln_id": "NAME-OPEN-REDIRECT",
            "request_identity": {"name_driven": True},
            "dynamic_eval": {"enabled": True, "status": "degraded_success"},
            "provenance": {
                "generation_origin": "deterministic_fallback",
                "fallback_class": "semantic_guided",
                "llm_stub_used": True,
            },
            "open_world": {"class": "semantic_guided_minimal_dynamic"},
            "strict_open_world": {"class": "strict_minimal_dynamic_fallback"},
            "failure": {"stage": "EXECUTOR"},
        },
        {"policy": {"name_only_mode": "dynamic"}},
    )

    assert payload["status"] == "degraded_dynamic_success"
    assert payload["closure_source"] == "degraded_deterministic_fallback"


def test_bundle_intent_satisfaction_uses_dynamic_eval_mode_when_enabled_under_compatibility_default() -> None:
    payload = _bundle_intent_satisfaction(
        {
            "vuln_id": "NAME-OPEN-REDIRECT",
            "request_identity": {"name_driven": True},
            "dynamic_eval": {"enabled": True, "status": "degraded_success"},
            "provenance": {"generation_origin": "deterministic_fallback"},
            "open_world": {"class": "semantic_guided_minimal_dynamic"},
            "strict_open_world": {"class": "strict_minimal_dynamic_fallback"},
        },
        {"policy": {"name_only_mode": "compatibility"}},
    )

    assert payload["mode"] == "dynamic_eval"
    assert payload["status"] == "degraded_dynamic_success"
    assert payload["required_contract"]["require_research"] is True
    assert payload["required_contract"]["allow_degraded_fallback"] is True


def test_bundle_intent_satisfaction_marks_strict_dynamic_failure() -> None:
    payload = _bundle_intent_satisfaction(
        {
            "vuln_id": "NAME-OPEN-REDIRECT",
            "request_identity": {"name_driven": True},
            "dynamic_eval": {"enabled": True, "status": "dynamic_failed"},
            "open_world": {"class": "name_driven_dynamic_failed"},
            "strict_open_world": {"class": "strict_dynamic_generation_failed"},
            "failure": {"stage": "GENERATOR", "terminal_failure_class": "guard_semantic_mismatch"},
        },
        {"policy": {"name_only_mode": "strict_dynamic"}},
    )

    assert payload["mode"] == "strict_dynamic"
    assert payload["status"] == "strict_dynamic_failed"
    assert payload["meets_intent"] is False
    assert payload["partial"] is False


def test_bundle_intent_satisfaction_uses_request_ir_for_canonicalized_name_driven_lane() -> None:
    payload = _bundle_intent_satisfaction(
        {
            "vuln_id": "CWE-79",
            "request_ir": {
                "name_driven": True,
                "request_label": "Reflected XSS",
                "resolved_vuln_id": "CWE-79",
                "resolution_state": "token_match",
            },
            "dynamic_eval": {"enabled": True, "status": "degraded_success"},
            "open_world": {"class": "semantic_guided_minimal_dynamic"},
            "strict_open_world": {"class": "strict_minimal_dynamic_fallback"},
            "provenance": {
                "generation_origin": "deterministic_fallback",
                "fallback_class": "semantic_guided",
                "llm_stub_used": True,
            },
            "verification": {"independence": "independent", "trust": "high"},
            "researcher": {"quality": "sufficient"},
        },
        {
            "vuln_id": "CWE-79",
            "request_ir": {
                "name_driven": True,
                "request_label": "Reflected XSS",
                "resolved_vuln_id": "CWE-79",
                "resolution_state": "token_match",
            },
            "policy": {"name_only_mode": "dynamic"},
        },
    )

    assert payload["request_kind"] == "name_only"
    assert payload["mode"] == "dynamic"
    assert payload["status"] == "degraded_dynamic_success"
    assert payload["meets_intent"] is False


def test_intent_satisfaction_summary_counts_partial_and_failed_name_only_lanes() -> None:
    summary = _intent_satisfaction_summary(
        [
            {
                "intent_satisfaction": {
                    "request_kind": "name_only",
                    "mode": "dynamic",
                    "status": "degraded_dynamic_success",
                    "meets_intent": False,
                    "partial": True,
                }
            },
            {
                "intent_satisfaction": {
                    "request_kind": "name_only",
                    "mode": "strict_dynamic",
                    "status": "strict_dynamic_failed",
                    "meets_intent": False,
                    "partial": False,
                }
            },
        ]
    )

    assert summary["name_only_bundles"] == 2
    assert summary["meets_intent_bundles"] == 0
    assert summary["partial_bundles"] == 1
    assert summary["by_status"] == {
        "degraded_dynamic_success": 1,
        "strict_dynamic_failed": 1,
    }



def test_bundle_promotion_is_blocked_when_pipeline_artifacts_are_missing(tmp_path: Path) -> None:
    plan = {
        "paths": {
            "metadata": str(tmp_path / "metadata"),
            "artifacts": str(tmp_path / "artifacts"),
        },
        "features": {"multi_vuln": False},
    }
    (tmp_path / "metadata").mkdir(parents=True, exist_ok=True)
    (tmp_path / "artifacts").mkdir(parents=True, exist_ok=True)
    bundle = VulnBundle(vuln_id="CWE-22", slug="cwe-22", workspace_subdir="app")

    promotion = _bundle_promotion_status(plan, bundle)

    assert promotion["eligible"] is False
    assert any(reason.startswith("pipeline:") for reason in promotion["reasons"])


def test_bundle_promotion_is_blocked_by_nested_eval_guard_failure(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    artifacts_dir = tmp_path / "artifacts"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "run").mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "reports").mkdir(parents=True, exist_ok=True)

    plan = {
        "paths": {
            "metadata": str(metadata_dir),
            "artifacts": str(artifacts_dir),
        },
        "features": {"multi_vuln": False},
    }
    bundle = VulnBundle(vuln_id="NAME-TEMPLATE-INJECTION", slug="name-template-injection", workspace_subdir="app")
    (metadata_dir / "reviewer_report.json").write_text(
        json.dumps({"blocking": False, "success": True, "blocking_bundles": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    (artifacts_dir / "run" / "summary.json").write_text(
        json.dumps({"run_passed": True}, ensure_ascii=False),
        encoding="utf-8",
    )
    (artifacts_dir / "reports" / "evals.json").write_text(
        json.dumps(
            {
                "results": [
                    {
                        "slug": "name-template-injection",
                        "vuln_id": "NAME-TEMPLATE-INJECTION",
                        "verify_pass": True,
                        "guard_consistency": {
                            "available": True,
                            "required_but_missing": False,
                            "verifier": {
                                "passed": False,
                                "blocking": True,
                                "violations": [
                                    "verifier assertion failed (contains): substring=missing: 49"
                                ],
                            },
                            "workspace": {"passed": True, "blocking": False, "violations": []},
                        },
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    promotion = _bundle_promotion_status(plan, bundle)

    assert promotion["eligible"] is False
    assert any(reason.startswith("verify_guard:verifier:") for reason in promotion["reasons"])


def test_bundle_promotion_is_blocked_by_nested_eval_semantic_failure(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    artifacts_dir = tmp_path / "artifacts"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "run").mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "reports").mkdir(parents=True, exist_ok=True)

    plan = {
        "paths": {
            "metadata": str(metadata_dir),
            "artifacts": str(artifacts_dir),
        },
        "features": {"multi_vuln": False},
    }
    bundle = VulnBundle(vuln_id="CWE-79", slug="cwe-79", workspace_subdir="app")
    (metadata_dir / "reviewer_report.json").write_text(
        json.dumps({"blocking": False, "success": True, "blocking_bundles": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    (artifacts_dir / "run" / "summary.json").write_text(
        json.dumps({"run_passed": True}, ensure_ascii=False),
        encoding="utf-8",
    )
    (artifacts_dir / "reports" / "evals.json").write_text(
        json.dumps(
            {
                "results": [
                    {
                        "slug": "cwe-79",
                        "vuln_id": "CWE-79",
                        "verify_pass": True,
                        "semantic_consistency": {
                            "supported": True,
                            "semantic_match": False,
                            "errors": ["missing reflected XSS sink"],
                        },
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    promotion = _bundle_promotion_status(plan, bundle)

    assert promotion["eligible"] is False
    assert any(reason.startswith("verify_semantic:") for reason in promotion["reasons"])


def test_bundle_promotion_is_blocked_when_semantic_support_is_missing_for_freeform_name(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    artifacts_dir = tmp_path / "artifacts"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "run").mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "reports").mkdir(parents=True, exist_ok=True)

    plan = {
        "paths": {
            "metadata": str(metadata_dir),
            "artifacts": str(artifacts_dir),
        },
        "features": {"multi_vuln": False},
    }
    bundle = VulnBundle(vuln_id="NAME-OPEN-REDIRECT", slug="name-open-redirect", workspace_subdir="app")
    (metadata_dir / "reviewer_report.json").write_text(
        json.dumps({"blocking": False, "success": True, "blocking_bundles": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    write_generator_contract(
        metadata_dir,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": "sid-pack-open-redirect",
            "slug": "name-open-redirect",
            "vuln_id": "NAME-OPEN-REDIRECT",
            "fallback_used": True,
            "fallback_class": "generic_unsupported_family",
            "provenance": {
                "generation_origin": "deterministic_fallback",
                "fallback_used": True,
                "fallback_class": "generic_unsupported_family",
                "source": "generator_manifest",
            },
            "semantic_contract": {
                "status": "unsupported",
                "semantic_signature": {
                    "input_vector": [],
                    "sink": [],
                    "exploit_precondition": [],
                },
            },
            "semantic_profile": {
                "schema_version": "semantic_profile@1.0",
                "sid": "sid-pack-open-redirect",
                "slug": "name-open-redirect",
                "requested_name": "Open Redirect",
                "normalized_vuln_id": "NAME-OPEN-REDIRECT",
                "family": "open_redirect",
                "support_level": "unsupported",
                "compiler_supported": False,
                "compiler_reason": "semantic family unsupported for compiler-backed generation",
                "stack_profile": {"language": "python", "framework": "flask"},
                "scenario_shape": {"service_entry": "app.py", "poc_entry": "poc.py", "service_port": 5000},
                "semantic_signature": {"input_vector": [], "sink": [], "exploit_precondition": []},
                "verification_contract": {"success_signature": "Exploit SUCCESS", "output_mode": "auto"},
                "derived_assertions": {"semantic_gate_required": True},
                "evidence_relevance": {},
            },
        },
    )
    (metadata_dir / "generator_manifest.json").write_text(
        json.dumps(
            {
                "manifest": {
                    "metadata": {
                        "compiler_family": "open_redirect",
                        "stack_scaffold_id": "python/flask",
                        "stack_scaffold_version": "1.0",
                        "fragment_id": "redirect_next_route",
                        "compose_mode": "registry",
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (artifacts_dir / "run" / "summary.json").write_text(
        json.dumps({"run_passed": True}, ensure_ascii=False),
        encoding="utf-8",
    )
    (artifacts_dir / "reports" / "evals.json").write_text(
        json.dumps(
            {
                "results": [
                    {
                        "slug": "name-open-redirect",
                        "vuln_id": "NAME-OPEN-REDIRECT",
                        "verify_pass": False,
                        "semantic_supported": False,
                        "semantic_status": "unsupported",
                        "semantic_consistency": {
                            "supported": False,
                            "semantic_match": False,
                            "status": "unsupported",
                            "source": "resolved_contract.semantic_contract",
                        },
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    promotion = _bundle_promotion_status(plan, bundle)

    assert promotion["eligible"] is False
    assert "verify_semantic:unsupported" in promotion["reasons"]
    assert "verify_semantic_status:unsupported" in promotion["reasons"]
    assert "fallback:generic_unsupported_family" in promotion["reasons"]
    assert "compiler:unsupported" in promotion["reasons"]


def test_write_manifest_records_failure_pipeline_result(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-pack-status"
    metadata_dir = tmp_path / "metadata" / sid
    artifacts_dir = tmp_path / "artifacts" / sid
    workspace_dir = tmp_path / "workspaces" / sid / "app"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "loop_state.json").write_text(
        json.dumps({"sid": sid, "last_result": "failure"}, ensure_ascii=False),
        encoding="utf-8",
    )
    plan = {
        "sid": sid,
        "paths": {
            "metadata": str(metadata_dir),
            "artifacts": str(artifacts_dir),
            "workspace": str(workspace_dir),
        },
        "requirement": {"vuln_id": "CWE-89"},
        "run_matrix": {"vuln_bundles": [{"vuln_id": "CWE-89", "slug": "cwe-89", "workspace_subdir": "app"}]},
        "features": {"multi_vuln": False},
    }
    monkeypatch.setattr(pack_mod, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)
    monkeypatch.setattr(pack_mod, "get_artifacts_dir", lambda incoming_sid: tmp_path / "artifacts" / incoming_sid)

    manifest_path = pack_mod.write_manifest(sid, plan)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["status"] == "failure"
    assert manifest["pipeline_result"] == "failure"


def test_write_manifest_flattens_top_level_failure_fields(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-pack-failure-flatten"
    metadata_dir = tmp_path / "metadata" / sid
    artifacts_dir = tmp_path / "artifacts" / sid
    workspace_dir = tmp_path / "workspaces" / sid / "app"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "loop_state.json").write_text(
        json.dumps(
            {
                "sid": sid,
                "last_result": "failure",
                "history": [
                    {
                        "stage": "PACK",
                        "success": False,
                        "reason": "strict open-world gate not satisfied",
                        "fix_hint": "improve dynamic lane",
                        "timestamp": "2026-03-11T00:00:00+00:00",
                        "metadata": {
                            "terminal_failure_class": "strict_open_world_not_satisfied",
                            "retry_recommended": False,
                        },
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    plan = {
        "sid": sid,
        "paths": {
            "metadata": str(metadata_dir),
            "artifacts": str(artifacts_dir),
            "workspace": str(workspace_dir),
        },
        "requirement": {"vuln_id": "NAME-OPEN-REDIRECT"},
        "run_matrix": {"vuln_bundles": [{"vuln_id": "NAME-OPEN-REDIRECT", "slug": "name-open-redirect", "workspace_subdir": "app"}]},
        "features": {"multi_vuln": False},
    }
    monkeypatch.setattr(pack_mod, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)
    monkeypatch.setattr(pack_mod, "get_artifacts_dir", lambda incoming_sid: tmp_path / "artifacts" / incoming_sid)

    manifest_path = pack_mod.write_manifest(sid, plan)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["failure_stage"] == "PACK"
    assert manifest["failure_reason"] == "strict open-world gate not satisfied"
    assert manifest["terminal_failure_class"] == "strict_open_world_not_satisfied"
    assert manifest["retry_recommended"] is False


def test_write_manifest_surfaces_bundle_provenance_and_performance(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-pack-provenance"
    metadata_dir = tmp_path / "metadata" / sid
    artifacts_dir = tmp_path / "artifacts" / sid
    workspace_dir = tmp_path / "workspaces" / sid / "app"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "run").mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "reports").mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "loop_state.json").write_text(
        json.dumps({"sid": sid, "last_result": "success"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (metadata_dir / "performance_summary.json").write_text(
        json.dumps(
            {
                "sid": sid,
                "retry_count": 2,
                "provider_health_state": "llm_degraded",
                "llm_stub_used": True,
                "events": [],
                "by_stage": {},
                "total_duration_s": 12.3,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    write_generator_contract(
        metadata_dir,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": sid,
            "slug": "cwe-89",
            "vuln_id": "CWE-89",
            "compiler_supported": False,
            "compiler_strategy": "sqli_string_concat",
            "compiler_reason": "compiler scaffold registry not implemented",
            "generation_origin": "deterministic_fallback",
            "fallback_used": True,
            "fallback_class": "generic_unsupported_family",
            "family_override_applied": False,
            "llm_stub_used": True,
            "llm_fixture_used": False,
            "service_env": {"APP_PORT": "5000", "DB_HOST": "sqli-db"},
            "semantic_profile": {
                "schema_version": "semantic_profile@1.0",
                "sid": sid,
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
            "provenance": {
                "generation_origin": "deterministic_fallback",
                "fallback_used": True,
                "fallback_class": "generic_unsupported_family",
                "family_override_applied": False,
                "llm_stub_used": True,
                "llm_fixture_used": False,
                "source": "generator_manifest",
            },
        },
    )
    (metadata_dir / "generator_manifest.json").write_text(
        json.dumps(
            {
                "manifest": {
                    "metadata": {
                        "compiler_family": "open_redirect",
                        "stack_scaffold_id": "python/flask",
                        "stack_scaffold_version": "1.0",
                        "fragment_id": "redirect_next_route",
                        "compose_mode": "registry",
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (artifacts_dir / "run" / "summary.json").write_text(
        json.dumps({"run_passed": True}, ensure_ascii=False),
        encoding="utf-8",
    )
    (artifacts_dir / "reports" / "evals.json").write_text(
        json.dumps(
            {
                "results": [
                    {
                        "slug": "cwe-89",
                        "vuln_id": "CWE-89",
                        "verify_pass": True,
                        "verification_rule_source": "generator_manifest_fallback",
                        "verification_trust": "low",
                        "verification_trust_reason": "self-certifying fallback rule",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (metadata_dir / "reviewer_report.json").write_text(
        json.dumps({"blocking": False, "success": True, "blocking_bundles": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    plan = {
        "sid": sid,
        "paths": {
            "metadata": str(metadata_dir),
            "artifacts": str(artifacts_dir),
            "workspace": str(workspace_dir),
        },
        "requirement": {"vuln_id": "CWE-89"},
        "run_matrix": {"vuln_bundles": [{"vuln_id": "CWE-89", "slug": "cwe-89", "workspace_subdir": "app"}]},
        "features": {"multi_vuln": False},
    }
    monkeypatch.setattr(pack_mod, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)
    monkeypatch.setattr(pack_mod, "get_artifacts_dir", lambda incoming_sid: tmp_path / "artifacts" / incoming_sid)

    manifest_path = pack_mod.write_manifest(sid, plan)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["performance"]["retry_count"] == 2
    assert manifest["performance"]["provider_health_state"] == "llm_degraded"
    assert manifest["compiler_supported"] is False
    assert manifest["compiler_strategy"] == "sqli_string_concat"
    assert manifest["compiler_reason"] == "compiler scaffold registry not implemented"
    assert manifest["generation_summary"]["by_origin"] == {"deterministic_fallback": 1}
    assert manifest["generation_summary"]["by_dynamicness_verdict"] == {"deterministic fallback dependent": 1}
    assert manifest["generation_summary"]["llm_stub_bundles"] == 1
    assert manifest["fallback_used"] is True
    assert manifest["family_override_applied"] is False
    assert manifest["llm_stub_used"] is True
    assert manifest["llm_fixture_used"] is False
    assert manifest["compiler_contract_summary"]["by_strategy"] == {"sqli_string_concat": 1}
    assert manifest["compiler_contract_summary"]["by_support_level"] == {"builtin_supported": 1}
    assert manifest["lower_bound_summary"]["family_non_remote_bundles"] == 1
    assert manifest["lower_bound_summary"]["effective_non_remote_bundles"] == 1
    assert manifest["lower_bound"]["family_non_remote_available"] is True
    assert manifest["lower_bound"]["effective_non_remote_available"] is True
    assert manifest["executor_feasibility_summary"]["by_status"] == {"not_required": 1}
    assert manifest["executor_feasibility_status"] == "not_required"
    assert manifest["verification_summary"]["by_rule_source"] == {"generator_manifest_fallback": 1}
    assert manifest["verification_summary"]["by_trust"] == {"low": 1}
    assert manifest["verification_summary"]["by_independence"] == {"self_derived": 1}
    assert manifest["verification_summary"]["low_trust_bundles"] == 1
    assert manifest["bundles"][0]["provenance"]["generation_origin"] == "deterministic_fallback"
    assert manifest["bundles"][0]["provenance"]["fallback_used"] is True
    assert manifest["bundles"][0]["provenance"]["fallback_class"] == "generic_unsupported_family"
    assert manifest["bundles"][0]["verification"]["rule_source"] == "generator_manifest_fallback"
    assert manifest["bundles"][0]["verification"]["trust"] == "low"
    assert manifest["bundles"][0]["verification"]["independence"] == "self_derived"
    assert manifest["verification_rule_source"] == "generator_manifest_fallback"
    assert manifest["verification_trust"] == "low"
    assert manifest["verification_independence"] == "self_derived"
    assert manifest["bundles"][0]["compiler_contract"]["compiler_supported"] is False
    assert manifest["bundles"][0]["compiler_contract"]["compiler_strategy"] == "sqli_string_concat"
    assert manifest["bundles"][0]["compiler_contract"]["service_env"] == {
        "APP_PORT": "5000",
        "DB_HOST": "sqli-db",
    }
    assert manifest["service_env"] == {"APP_PORT": "5000", "DB_HOST": "sqli-db"}
    assert manifest["runtime_recipe"]["service_env"] == {"APP_PORT": "5000", "DB_HOST": "sqli-db"}
    assert manifest["runtime_recipe"]["topology"] == "single_service"
    assert manifest["runtime_graph"]["topology"] == "single_service"
    assert manifest["bundles"][0]["runtime_graph"]["exploit_path"]["target_node"] == "service"
    assert manifest["bundles"][0]["runtime_recipe"]["service_port"] == 5000
    assert manifest["artifact_quality_summary"]["bundle_count"] == 1
    assert manifest["artifact_quality"]["runtime_recipe_present"] is True
    assert manifest["artifact_quality"]["generation_authenticity"] == "degraded_fallback"
    assert manifest["artifact_quality"]["band"] == "low"
    assert any("deterministic fallback bundle" in note for note in manifest["artifact_quality"]["notes"])
    assert manifest["template_dependence_summary"]["lower_bound_dependent_bundles"] == 1
    assert manifest["bundles"][0]["lower_bound"]["effective_non_remote_available"] is True
    assert manifest["bundles"][0]["executor_feasibility"]["status"] == "not_required"
    assert manifest["bundles"][0]["dynamicness"]["verdict"] == "deterministic fallback dependent"
    assert manifest["bundles"][0]["dynamicness"]["trusted"] is False


def test_write_manifest_classifies_llm_manifest_as_trusted_dynamic(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-pack-dynamic"
    metadata_dir = tmp_path / "metadata" / sid
    artifacts_dir = tmp_path / "artifacts" / sid
    workspace_dir = tmp_path / "workspaces" / sid / "app"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "run").mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "reports").mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "loop_state.json").write_text(
        json.dumps({"sid": sid, "last_result": "success"}, ensure_ascii=False),
        encoding="utf-8",
    )
    write_generator_contract(
        metadata_dir,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": sid,
            "slug": "cwe-22",
            "vuln_id": "CWE-22",
            "generation_origin": "llm_manifest",
            "fallback_used": False,
            "family_override_applied": False,
            "llm_stub_used": False,
            "llm_fixture_used": True,
            "provenance": {
                "generation_origin": "llm_manifest",
                "fallback_used": False,
                "family_override_applied": False,
                "llm_stub_used": False,
                "llm_fixture_used": True,
                "source": "generator_manifest",
            },
        },
    )
    (artifacts_dir / "run" / "summary.json").write_text(
        json.dumps({"run_passed": True}, ensure_ascii=False),
        encoding="utf-8",
    )
    (artifacts_dir / "reports" / "evals.json").write_text(
        json.dumps({"results": [{"slug": "cwe-22", "vuln_id": "CWE-22", "verify_pass": True}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (metadata_dir / "reviewer_report.json").write_text(
        json.dumps({"blocking": False, "success": True, "blocking_bundles": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    plan = {
        "sid": sid,
        "paths": {
            "metadata": str(metadata_dir),
            "artifacts": str(artifacts_dir),
            "workspace": str(workspace_dir),
        },
        "requirement": {"vuln_id": "CWE-22"},
        "run_matrix": {"vuln_bundles": [{"vuln_id": "CWE-22", "slug": "cwe-22", "workspace_subdir": "app"}]},
        "features": {"multi_vuln": False},
    }
    monkeypatch.setattr(pack_mod, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)
    monkeypatch.setattr(pack_mod, "get_artifacts_dir", lambda incoming_sid: tmp_path / "artifacts" / incoming_sid)

    manifest_path = pack_mod.write_manifest(sid, plan)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["generation_summary"]["by_dynamicness_verdict"] == {"trusted dynamic": 1}
    assert manifest["generation_summary"]["by_compose_mode"] == {}
    assert manifest["generation_summary"]["by_stack_scaffold_id"] == {}
    assert manifest["generation_summary"]["llm_fixture_bundles"] == 1
    assert manifest["generation_summary"]["template_origin_bundles"] == 0
    assert manifest["generation_summary"]["template_assisted_bundles"] == 0
    assert manifest["generation_summary"]["registry_compose_bundles"] == 0
    assert manifest["generation_summary"]["scaffolded_bundles"] == 0
    assert manifest["fallback_used"] is False
    assert manifest["family_override_applied"] is False
    assert manifest["llm_stub_used"] is False
    assert manifest["llm_fixture_used"] is True
    assert manifest["bundles"][0]["dynamicness"]["verdict"] == "trusted dynamic"
    assert manifest["bundles"][0]["dynamicness"]["trusted"] is True


def test_write_manifest_classifies_compiler_generated_as_compiler_first(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-pack-compiler"
    metadata_dir = tmp_path / "metadata" / sid
    artifacts_dir = tmp_path / "artifacts" / sid
    workspace_dir = tmp_path / "workspaces" / sid / "app"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "run").mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "reports").mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "loop_state.json").write_text(
        json.dumps({"sid": sid, "last_result": "success"}, ensure_ascii=False),
        encoding="utf-8",
    )
    write_generator_contract(
        metadata_dir,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": sid,
            "slug": "name-open-redirect",
            "vuln_id": "NAME-OPEN-REDIRECT",
            "compiler_supported": True,
            "compiler_strategy": "open_redirect_reflect",
            "compiler_reason": "compiler strategy and scaffold are available",
            "compiler_family": "open_redirect",
            "stack_scaffold_id": "python/flask",
            "stack_scaffold_version": "1.0",
            "fragment_id": "redirect_next_route",
            "compose_mode": "registry",
            "generation_origin": "compiler_generated",
            "fallback_used": False,
            "family_override_applied": False,
            "llm_stub_used": False,
            "semantic_profile": {
                "schema_version": "semantic_profile@1.0",
                "sid": sid,
                "slug": "name-open-redirect",
                "requested_name": "Open Redirect",
                "normalized_vuln_id": "NAME-OPEN-REDIRECT",
                "family": "open_redirect",
                "support_level": "compiler_supported",
                "compiler_strategy": "open_redirect_reflect",
                "compiler_supported": True,
                "compiler_reason": "compiler strategy and scaffold are available",
                "stack_profile": {"language": "python", "framework": "flask"},
                "scenario_shape": {"service_entry": "app.py", "poc_entry": "poc.py", "service_port": 5000},
                "semantic_signature": {"input_vector": ["next parameter"], "sink": ["redirect("], "exploit_precondition": ["open redirect"]},
                "verification_contract": {"success_signature": "Exploit SUCCESS", "output_mode": "auto"},
                "derived_assertions": {"semantic_gate_required": True},
                "evidence_relevance": {},
            },
            "provenance": {
                "generation_origin": "compiler_generated",
                "fallback_used": False,
                "family_override_applied": False,
                "llm_stub_used": False,
                "source": "generator_manifest",
            },
        },
    )
    (artifacts_dir / "run" / "summary.json").write_text(
        json.dumps({"run_passed": True}, ensure_ascii=False),
        encoding="utf-8",
    )
    (artifacts_dir / "reports" / "evals.json").write_text(
        json.dumps(
            {"results": [{"slug": "name-open-redirect", "vuln_id": "NAME-OPEN-REDIRECT", "verify_pass": True, "semantic_supported": True, "semantic_status": "aligned"}]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (metadata_dir / "reviewer_report.json").write_text(
        json.dumps({"blocking": False, "success": True, "blocking_bundles": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    plan = {
        "sid": sid,
        "paths": {
            "metadata": str(metadata_dir),
            "artifacts": str(artifacts_dir),
            "workspace": str(workspace_dir),
        },
        "requirement": {
            "vuln_id": "NAME-OPEN-REDIRECT",
            "request_identity": {
                "request_label": "Open Redirect",
                "resolved_vuln_id": "NAME-OPEN-REDIRECT",
                "input_mode": "free_form_name",
                "source": "alias",
                "match_class": "catalog_alias",
                "confidence": "high",
                "name_driven": True,
            },
            "request_ir": {
                "request_label": "Open Redirect",
                "resolved_vuln_id": "NAME-OPEN-REDIRECT",
                "input_mode": "free_form_name",
                "name_driven": True,
                "resolution_state": "catalog_alias",
                "pattern_seed_state": "preserved",
            },
        },
        "run_matrix": {"vuln_bundles": [{"vuln_id": "NAME-OPEN-REDIRECT", "slug": "name-open-redirect", "workspace_subdir": "app"}]},
        "features": {"multi_vuln": False},
    }
    monkeypatch.setattr(pack_mod, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)
    monkeypatch.setattr(pack_mod, "get_artifacts_dir", lambda incoming_sid: tmp_path / "artifacts" / incoming_sid)

    manifest_path = pack_mod.write_manifest(sid, plan)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["request_ir"]["resolution_state"] == "catalog_alias"
    assert manifest["request_ir"]["pattern_seed_state"] == "preserved"
    assert manifest["bundles"][0]["request_ir"]["request_label"] == "Open Redirect"

    assert manifest["compiler_supported"] is True
    assert manifest["compiler_strategy"] == "open_redirect_reflect"
    assert manifest["compiler_family"] == "open_redirect"
    assert manifest["stack_scaffold_id"] == "python/flask"
    assert manifest["stack_scaffold_version"] == "1.0"
    assert manifest["fragment_id"] == "redirect_next_route"
    assert manifest["compose_mode"] == "registry"
    assert manifest["generation_summary"]["by_compose_mode"] == {"registry": 1}
    assert manifest["generation_summary"]["by_stack_scaffold_id"] == {"python/flask": 1}
    assert manifest["generation_summary"]["template_origin_bundles"] == 0
    assert manifest["generation_summary"]["template_assisted_bundles"] == 0
    assert manifest["generation_summary"]["registry_compose_bundles"] == 1
    assert manifest["generation_summary"]["scaffolded_bundles"] == 1
    assert manifest["verification_summary"]["by_rule_source"] == {}
    assert manifest["verification_summary"]["by_trust"] == {}
    assert manifest["bundles"][0]["dynamicness"]["verdict"] == "compiler-first"
    assert manifest["compiler_contract_summary"]["supported_bundles"] == 1
    assert manifest["bundles"][0]["compiler_contract"]["stack_scaffold_id"] == "python/flask"
    assert manifest["bundles"][0]["compiler_contract"]["fragment_id"] == "redirect_next_route"


def test_write_manifest_surfaces_executor_feasibility_misconfiguration(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-pack-executor-feasibility"
    metadata_dir = tmp_path / "metadata" / sid
    artifacts_dir = tmp_path / "artifacts" / sid
    workspace_dir = tmp_path / "workspaces" / sid / "app"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "run").mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "reports").mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "loop_state.json").write_text(
        json.dumps({"sid": sid, "last_result": "success"}, ensure_ascii=False),
        encoding="utf-8",
    )
    write_generator_contract(
        metadata_dir,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": sid,
            "slug": "cwe-89",
            "vuln_id": "CWE-89",
            "compiler_supported": True,
            "compiler_strategy": "sqli_string_concat",
            "compiler_reason": "compiler strategy and scaffold are available",
            "generation_origin": "compiler_generated",
            "semantic_profile": {
                "schema_version": "semantic_profile@1.0",
                "sid": sid,
                "slug": "cwe-89",
                "requested_name": "SQL Injection",
                "normalized_vuln_id": "CWE-89",
                "family": "sql_injection",
                "support_level": "builtin_supported",
                "compiler_strategy": "sqli_string_concat",
                "compiler_supported": True,
                "compiler_reason": "compiler strategy and scaffold are available",
                "stack_profile": {"language": "python", "framework": "flask"},
                "scenario_shape": {"service_entry": "app.py", "poc_entry": "poc.py", "service_port": 5000},
                "semantic_signature": {
                    "input_vector": ["request.args"],
                    "sink": ["execute("],
                    "exploit_precondition": ["string concatenation"],
                },
                "verification_contract": {"success_signature": "SQLi SUCCESS", "output_mode": "auto"},
                "derived_assertions": {"semantic_gate_required": False},
                "evidence_relevance": {},
            },
            "provenance": {
                "generation_origin": "compiler_generated",
                "fallback_used": False,
                "family_override_applied": False,
                "llm_stub_used": False,
                "source": "generator_manifest",
            },
        },
    )
    (artifacts_dir / "run" / "summary.json").write_text(
        json.dumps({"run_passed": True}, ensure_ascii=False),
        encoding="utf-8",
    )
    (artifacts_dir / "reports" / "evals.json").write_text(
        json.dumps({"results": [{"slug": "cwe-89", "vuln_id": "CWE-89", "verify_pass": True}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (metadata_dir / "reviewer_report.json").write_text(
        json.dumps({"blocking": False, "success": True, "blocking_bundles": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    plan = {
        "sid": sid,
        "paths": {
            "metadata": str(metadata_dir),
            "artifacts": str(artifacts_dir),
            "workspace": str(workspace_dir),
        },
        "requirement": {"vuln_id": "CWE-89", "runtime": {"db": "mysql", "allow_external_db": True}},
        "policy": {"executor": {"allow_network": False, "network_mode": "none", "sidecars": []}},
        "run_matrix": {"vuln_bundles": [{"vuln_id": "CWE-89", "slug": "cwe-89", "workspace_subdir": "app"}]},
        "features": {"multi_vuln": False},
    }
    monkeypatch.setattr(pack_mod, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)
    monkeypatch.setattr(pack_mod, "get_artifacts_dir", lambda incoming_sid: tmp_path / "artifacts" / incoming_sid)

    manifest_path = pack_mod.write_manifest(sid, plan)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["promotion"]["eligible"] is False
    assert any(reason.endswith("executor:misconfigured") for reason in manifest["promotion"]["reasons"])
    assert manifest["executor_feasibility_status"] == "misconfigured"
    assert manifest["executor_feasibility"]["requires_external_db"] is True
    assert manifest["executor_feasibility_summary"]["misconfigured_bundles"] == 1
    assert manifest["executor_feasibility_summary"]["by_status"] == {"misconfigured": 1}


def test_bundle_promotion_allows_medium_verification_trust_for_compiler_runtime_rule(
    tmp_path: Path,
    monkeypatch,
) -> None:
    sid = "sid-pack-medium-trust"
    metadata_dir = tmp_path / "metadata" / sid
    artifacts_dir = tmp_path / "artifacts" / sid
    workspace_dir = tmp_path / "workspaces" / sid / "app"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "run").mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "reports").mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "loop_state.json").write_text(
        json.dumps({"sid": sid, "last_result": "success"}, ensure_ascii=False),
        encoding="utf-8",
    )
    write_generator_contract(
        metadata_dir,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": sid,
            "slug": "name-open-redirect",
            "vuln_id": "NAME-OPEN-REDIRECT",
            "compiler_supported": True,
            "compiler_strategy": "open_redirect_reflect",
            "compiler_reason": "compiler strategy and scaffold are available",
            "generation_origin": "compiler_generated",
            "semantic_profile": {
                "schema_version": "semantic_profile@1.0",
                "sid": sid,
                "slug": "name-open-redirect",
                "requested_name": "Open Redirect",
                "normalized_vuln_id": "NAME-OPEN-REDIRECT",
                "family": "open_redirect",
                "support_level": "compiler_supported",
                "compiler_strategy": "open_redirect_reflect",
                "compiler_supported": True,
                "compiler_reason": "compiler strategy and scaffold are available",
                "stack_profile": {"language": "python", "framework": "flask"},
                "scenario_shape": {"service_entry": "app.py", "poc_entry": "poc.py", "service_port": 5000},
                "semantic_signature": {
                    "input_vector": ["next parameter"],
                    "sink": ["redirect("],
                    "exploit_precondition": ["open redirect"],
                },
                "verification_contract": {"success_signature": "Exploit SUCCESS", "output_mode": "auto"},
                "derived_assertions": {"semantic_gate_required": True},
                "evidence_relevance": {},
            },
            "provenance": {
                "generation_origin": "compiler_generated",
                "fallback_used": False,
                "family_override_applied": False,
                "llm_stub_used": False,
                "source": "generator_manifest",
            },
        },
    )
    (artifacts_dir / "run" / "summary.json").write_text(
        json.dumps({"run_passed": True}, ensure_ascii=False),
        encoding="utf-8",
    )
    (artifacts_dir / "reports" / "evals.json").write_text(
        json.dumps(
            {
                "results": [
                    {
                        "slug": "name-open-redirect",
                        "vuln_id": "NAME-OPEN-REDIRECT",
                        "verify_pass": True,
                        "semantic_supported": True,
                        "semantic_status": "aligned",
                        "verification_rule_source": "compiler_runtime_rule",
                        "verification_trust": "medium",
                        "verification_trust_reason": "compiler-derived runtime rule",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (metadata_dir / "reviewer_report.json").write_text(
        json.dumps({"blocking": False, "success": True, "blocking_bundles": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    plan = {
        "sid": sid,
        "paths": {
            "metadata": str(metadata_dir),
            "artifacts": str(artifacts_dir),
            "workspace": str(workspace_dir),
        },
        "requirement": {"vuln_id": "NAME-OPEN-REDIRECT"},
        "run_matrix": {"vuln_bundles": [{"vuln_id": "NAME-OPEN-REDIRECT", "slug": "name-open-redirect", "workspace_subdir": "app"}]},
        "features": {"multi_vuln": False},
    }
    monkeypatch.setattr(pack_mod, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)
    monkeypatch.setattr(pack_mod, "get_artifacts_dir", lambda incoming_sid: tmp_path / "artifacts" / incoming_sid)

    manifest_path = pack_mod.write_manifest(sid, plan)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["promotion"]["eligible"] is True
    assert manifest["verification_rule_source"] == "compiler_runtime_rule"
    assert manifest["verification_trust"] == "medium"
    assert manifest["verification_independence"] == "compiler_coupled"
    assert manifest["verification_summary"]["by_rule_source"] == {"compiler_runtime_rule": 1}
    assert manifest["verification_summary"]["by_trust"] == {"medium": 1}
    assert manifest["verification_summary"]["by_independence"] == {"compiler_coupled": 1}
    assert manifest["verification_summary"]["low_trust_bundles"] == 0


def test_bundle_promotion_can_require_independent_verification_for_compiler_runtime_rule(
    tmp_path: Path,
    monkeypatch,
) -> None:
    sid = "sid-pack-independent-required"
    metadata_dir = tmp_path / "metadata" / sid
    artifacts_dir = tmp_path / "artifacts" / sid
    workspace_dir = tmp_path / "workspaces" / sid / "app"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "run").mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "reports").mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "loop_state.json").write_text(
        json.dumps({"sid": sid, "last_result": "success"}, ensure_ascii=False),
        encoding="utf-8",
    )
    write_generator_contract(
        metadata_dir,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": sid,
            "slug": "name-open-redirect",
            "vuln_id": "NAME-OPEN-REDIRECT",
            "compiler_supported": True,
            "compiler_strategy": "open_redirect_reflect",
            "compiler_reason": "compiler strategy and scaffold are available",
            "generation_origin": "compiler_generated",
            "semantic_profile": {
                "schema_version": "semantic_profile@1.0",
                "sid": sid,
                "slug": "name-open-redirect",
                "requested_name": "Open Redirect",
                "normalized_vuln_id": "NAME-OPEN-REDIRECT",
                "family": "open_redirect",
                "support_level": "compiler_supported",
                "compiler_strategy": "open_redirect_reflect",
                "compiler_supported": True,
                "compiler_reason": "compiler strategy and scaffold are available",
                "stack_profile": {"language": "python", "framework": "flask"},
                "scenario_shape": {"service_entry": "app.py", "poc_entry": "poc.py", "service_port": 5000},
                "semantic_signature": {
                    "input_vector": ["next parameter"],
                    "sink": ["redirect("],
                    "exploit_precondition": ["open redirect"],
                },
                "verification_contract": {"success_signature": "Exploit SUCCESS", "output_mode": "auto"},
                "derived_assertions": {"semantic_gate_required": True},
                "evidence_relevance": {},
            },
            "provenance": {
                "generation_origin": "compiler_generated",
                "fallback_used": False,
                "family_override_applied": False,
                "llm_stub_used": False,
                "source": "generator_manifest",
            },
        },
    )
    (artifacts_dir / "run" / "summary.json").write_text(
        json.dumps({"run_passed": True}, ensure_ascii=False),
        encoding="utf-8",
    )
    (artifacts_dir / "reports" / "evals.json").write_text(
        json.dumps(
            {
                "results": [
                    {
                        "slug": "name-open-redirect",
                        "vuln_id": "NAME-OPEN-REDIRECT",
                        "verify_pass": True,
                        "semantic_supported": True,
                        "semantic_status": "aligned",
                        "verification_rule_source": "compiler_runtime_rule",
                        "verification_trust": "medium",
                        "verification_trust_reason": "compiler-derived runtime rule",
                        "verification_independence": "compiler_coupled",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (metadata_dir / "reviewer_report.json").write_text(
        json.dumps({"blocking": False, "success": True, "blocking_bundles": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    plan = {
        "sid": sid,
        "paths": {
            "metadata": str(metadata_dir),
            "artifacts": str(artifacts_dir),
            "workspace": str(workspace_dir),
        },
        "requirement": {
            "vuln_id": "NAME-OPEN-REDIRECT",
            "policy": {"verifier": {"min_promotion_independence": "independent"}},
        },
        "run_matrix": {"vuln_bundles": [{"vuln_id": "NAME-OPEN-REDIRECT", "slug": "name-open-redirect", "workspace_subdir": "app"}]},
        "features": {"multi_vuln": False},
    }
    monkeypatch.setattr(pack_mod, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)
    monkeypatch.setattr(pack_mod, "get_artifacts_dir", lambda incoming_sid: tmp_path / "artifacts" / incoming_sid)

    manifest_path = pack_mod.write_manifest(sid, plan)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["promotion"]["eligible"] is False
    assert any("verify_independence:compiler_coupled" in reason for reason in manifest["promotion"]["reasons"])
    assert any("verify_independence_policy:min_independent" in reason for reason in manifest["promotion"]["reasons"])


def test_write_manifest_classifies_compiler_supported_known_family_without_static_rule_as_known_regression(
    tmp_path: Path,
    monkeypatch,
) -> None:
    sid = "sid-pack-xss"
    metadata_dir = tmp_path / "metadata" / sid
    artifacts_dir = tmp_path / "artifacts" / sid
    workspace_dir = tmp_path / "workspaces" / sid / "app"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "run").mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "reports").mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "loop_state.json").write_text(
        json.dumps({"sid": sid, "last_result": "success"}, ensure_ascii=False),
        encoding="utf-8",
    )
    write_generator_contract(
        metadata_dir,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": sid,
            "slug": "cwe-79",
            "vuln_id": "CWE-79",
            "compiler_supported": True,
            "compiler_strategy": "xss_reflected",
            "compiler_reason": "compiler strategy and scaffold are available",
            "generation_origin": "compiler_generated",
            "semantic_profile": {
                "schema_version": "semantic_profile@1.0",
                "sid": sid,
                "slug": "cwe-79",
                "requested_name": "XSS",
                "normalized_vuln_id": "CWE-79",
                "family": "xss",
                "support_level": "builtin_supported",
                "compiler_strategy": "xss_reflected",
                "compiler_supported": True,
                "compiler_reason": "compiler strategy and scaffold are available",
                "stack_profile": {"language": "python", "framework": "flask"},
                "scenario_shape": {"service_entry": "app.py", "poc_entry": "poc.py", "service_port": 5000},
                "semantic_signature": {
                    "input_vector": ["request.args"],
                    "sink": ["render_template_string"],
                    "exploit_precondition": ["unescaped reflection"],
                },
                "verification_contract": {"success_signature": "Exploit SUCCESS", "output_mode": "auto"},
                "derived_assertions": {"semantic_gate_required": True},
                "evidence_relevance": {},
            },
            "provenance": {
                "generation_origin": "compiler_generated",
                "fallback_used": False,
                "family_override_applied": False,
                "llm_stub_used": False,
                "source": "generator_manifest",
            },
        },
    )
    (artifacts_dir / "run" / "summary.json").write_text(
        json.dumps({"run_passed": True}, ensure_ascii=False),
        encoding="utf-8",
    )
    (artifacts_dir / "reports" / "evals.json").write_text(
        json.dumps(
            {"results": [{"slug": "cwe-79", "vuln_id": "CWE-79", "verify_pass": True}]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (metadata_dir / "reviewer_report.json").write_text(
        json.dumps({"blocking": False, "success": True, "blocking_bundles": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    plan = {
        "sid": sid,
        "paths": {
            "metadata": str(metadata_dir),
            "artifacts": str(artifacts_dir),
            "workspace": str(workspace_dir),
        },
        "requirement": {"vuln_id": "CWE-79"},
        "run_matrix": {"vuln_bundles": [{"vuln_id": "CWE-79", "slug": "cwe-79", "workspace_subdir": "app"}]},
        "features": {"multi_vuln": False},
    }
    monkeypatch.setattr(pack_mod, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)
    monkeypatch.setattr(pack_mod, "get_artifacts_dir", lambda incoming_sid: tmp_path / "artifacts" / incoming_sid)

    manifest_path = pack_mod.write_manifest(sid, plan)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["bundles"][0]["generalization"]["class"] == "known_family_regression"
    assert manifest["generalization_class"] == "known_family_regression"


def test_family_override_is_not_classified_as_trusted_dynamic() -> None:
    verdict = _bundle_dynamicness_verdict(
        {
            "generation_origin": "family_override",
            "fallback_used": False,
            "family_override_applied": True,
            "llm_stub_used": False,
        }
    )

    assert verdict["verdict"] == "template-assisted"
    assert verdict["trusted"] is False


def test_write_manifest_uses_generator_failure_record_for_failed_bundle_provenance(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-pack-failure-provenance"
    metadata_dir = tmp_path / "metadata" / sid
    artifacts_dir = tmp_path / "artifacts" / sid
    workspace_dir = tmp_path / "workspaces" / sid / "app"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "loop_state.json").write_text(
        json.dumps({"sid": sid, "last_result": "failure"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (metadata_dir / "generator_failures.jsonl").write_text(
        json.dumps(
            {
                "timestamp": "2026-03-07T10:38:57Z",
                "guard_error_code": "guard_semantic_mismatch",
                "failure_fingerprint": "fp-1",
                "reason": "semantic mismatch",
                "llm_stub_used": True,
                "fallback_used": True,
                "fallback_class": "generic_unsupported_family",
                "family_override_applied": False,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    plan = {
        "sid": sid,
        "paths": {
            "metadata": str(metadata_dir),
            "artifacts": str(artifacts_dir),
            "workspace": str(workspace_dir),
        },
        "requirement": {"vuln_id": "CWE-89"},
        "run_matrix": {"vuln_bundles": [{"vuln_id": "CWE-89", "slug": "cwe-89", "workspace_subdir": "app"}]},
        "features": {"multi_vuln": False},
    }
    monkeypatch.setattr(pack_mod, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)
    monkeypatch.setattr(pack_mod, "get_artifacts_dir", lambda incoming_sid: tmp_path / "artifacts" / incoming_sid)

    manifest_path = pack_mod.write_manifest(sid, plan, filename="failure_manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest_path.name == "failure_manifest.json"
    assert manifest["bundles"][0]["provenance"]["source"] == "generator_failure_record"
    assert manifest["bundles"][0]["provenance"]["generation_origin"] == "deterministic_fallback"
    assert manifest["bundles"][0]["provenance"]["llm_stub_used"] is True
    assert manifest["bundles"][0]["provenance"]["fallback_class"] == "generic_unsupported_family"
    assert manifest["bundles"][0]["dynamicness"]["verdict"] == "deterministic fallback dependent"


def test_write_manifest_removes_stale_counterpart_file(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-pack-stale-counterpart"
    metadata_dir = tmp_path / "metadata" / sid
    artifacts_dir = tmp_path / "artifacts" / sid
    workspace_dir = tmp_path / "workspaces" / sid / "app"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "run").mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "reports").mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "loop_state.json").write_text(
        json.dumps({"sid": sid, "last_result": "failure"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (metadata_dir / "manifest.json").write_text("{}", encoding="utf-8")
    (artifacts_dir / "run" / "summary.json").write_text(json.dumps({"run_passed": False}), encoding="utf-8")
    (artifacts_dir / "reports" / "evals.json").write_text(json.dumps({"results": []}), encoding="utf-8")
    plan = {
        "sid": sid,
        "paths": {
            "metadata": str(metadata_dir),
            "artifacts": str(artifacts_dir),
            "workspace": str(workspace_dir),
        },
        "requirement": {"vuln_id": "CWE-89"},
        "run_matrix": {"vuln_bundles": [{"vuln_id": "CWE-89", "slug": "cwe-89", "workspace_subdir": "app"}]},
        "features": {"multi_vuln": False},
    }
    monkeypatch.setattr(pack_mod, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)
    monkeypatch.setattr(pack_mod, "get_artifacts_dir", lambda incoming_sid: tmp_path / "artifacts" / incoming_sid)

    manifest_path = pack_mod.write_manifest(sid, plan, filename="failure_manifest.json")

    assert manifest_path.name == "failure_manifest.json"
    assert manifest_path.exists()
    assert not (metadata_dir / "manifest.json").exists()


def test_write_failure_manifest_surfaces_research_short_circuit_provenance(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-pack-research-short-circuit"
    metadata_dir = tmp_path / "metadata" / sid
    artifacts_dir = tmp_path / "artifacts" / sid
    workspace_dir = tmp_path / "workspaces" / sid / "app"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "loop_state.json").write_text(
        json.dumps(
            {
                "sid": sid,
                "last_result": "failure",
                "history": [
                    {
                        "loop": 1,
                        "stage": "RESEARCH",
                        "success": False,
                        "blocking": True,
                        "reason": "semantic profile unsupported",
                        "fix_hint": "keep inspection-only",
                        "timestamp": "2026-03-08T02:10:32Z",
                        "metadata": {
                            "terminal_failure_class": "semantic_support_missing",
                            "retry_recommended": False,
                            "unsupported_bundles": [
                                {
                                    "slug": "name-custom-weird-vuln",
                                    "vuln_id": "NAME-CUSTOM-WEIRD-VULN",
                                    "support_level": "unsupported",
                                }
                            ],
                        },
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    write_generator_contract(
        metadata_dir,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": sid,
            "slug": "name-custom-weird-vuln",
            "vuln_id": "NAME-CUSTOM-WEIRD-VULN",
            "semantic_profile": {
                "schema_version": "semantic_profile@1.0",
                "sid": sid,
                "slug": "name-custom-weird-vuln",
                "normalized_vuln_id": "NAME-CUSTOM-WEIRD-VULN",
                "family": "custom_weird_vuln",
                "support_level": "unsupported",
                "compiler_supported": False,
                "compiler_reason": "semantic family unsupported for compiler-backed generation",
            },
        },
    )
    plan = {
        "sid": sid,
        "paths": {
            "metadata": str(metadata_dir),
            "artifacts": str(artifacts_dir),
            "workspace": str(workspace_dir),
        },
        "requirement": {"vuln_id": "NAME-CUSTOM-WEIRD-VULN"},
        "run_matrix": {
            "vuln_bundles": [
                {
                    "vuln_id": "NAME-CUSTOM-WEIRD-VULN",
                    "slug": "name-custom-weird-vuln",
                    "workspace_subdir": "app",
                }
            ]
        },
        "features": {"multi_vuln": False},
    }
    monkeypatch.setattr(pack_mod, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)
    monkeypatch.setattr(pack_mod, "get_artifacts_dir", lambda incoming_sid: tmp_path / "artifacts" / incoming_sid)

    manifest_path = pack_mod.write_manifest(sid, plan, filename="failure_manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["failure"]["terminal_failure_class"] == "semantic_support_missing"
    assert manifest["semantic_supported"] is False
    assert manifest["semantic_status"] == "unsupported"
    assert manifest["semantic_source"] == "semantic_profile"
    assert manifest["bundles"][0]["failure"]["terminal_failure_class"] == "semantic_support_missing"
    assert manifest["bundles"][0]["provenance"]["generation_origin"] == "research_short_circuit"
    assert manifest["bundles"][0]["provenance"]["source"] == "loop_state"
    assert manifest["bundles"][0]["dynamicness"]["verdict"] == "pre-generation fail-closed"
    assert manifest["bundles"][0]["semantic_supported"] is False
    assert manifest["bundles"][0]["semantic_status"] == "unsupported"
    assert manifest["bundles"][0]["semantic_source"] == "semantic_profile"


def test_bundle_scoped_research_failure_does_not_poison_other_multi_vuln_bundle(
    tmp_path: Path, monkeypatch
) -> None:
    sid = "sid-pack-multi-bundle-research-failure"
    metadata_dir = tmp_path / "metadata" / sid
    artifacts_dir = tmp_path / "artifacts" / sid
    workspace_dir = tmp_path / "workspaces" / sid / "app"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "loop_state.json").write_text(
        json.dumps(
            {
                "sid": sid,
                "last_result": "failure",
                "history": [
                    {
                        "loop": 1,
                        "stage": "RESEARCH",
                        "success": False,
                        "blocking": True,
                        "reason": "Insufficient researcher evidence for NAME-CUSTOM-WEIRD-VULN",
                        "fix_hint": "improve evidence",
                        "timestamp": "2026-03-09T12:50:01Z",
                        "metadata": {
                            "terminal_failure_class": "evidence_low_relevance",
                            "retry_recommended": False,
                            "bundle_slug": "name-custom-weird-vuln",
                            "vuln_id": "NAME-CUSTOM-WEIRD-VULN",
                        },
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    unsupported_bundle_dir = metadata_dir / "bundles" / "name-custom-weird-vuln"
    supported_bundle_dir = metadata_dir / "bundles" / "name-open-redirect"
    unsupported_bundle_dir.mkdir(parents=True, exist_ok=True)
    supported_bundle_dir.mkdir(parents=True, exist_ok=True)
    (unsupported_bundle_dir / "semantic_profile.json").write_text(
        json.dumps(
            {
                "support_level": "unsupported",
                "compiler_supported": False,
                "compiler_reason": "semantic family unsupported for compiler-backed generation",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (supported_bundle_dir / "semantic_profile.json").write_text(
        json.dumps(
            {
                "support_level": "compiler_supported",
                "compiler_supported": True,
                "compiler_strategy": "open_redirect_reflect",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    plan = {
        "sid": sid,
        "paths": {
            "metadata": str(metadata_dir),
            "artifacts": str(artifacts_dir),
            "workspace": str(workspace_dir),
        },
        "requirement": {"vuln_ids": ["NAME-CUSTOM-WEIRD-VULN", "NAME-OPEN-REDIRECT"], "multi_vuln": True},
        "run_matrix": {
            "vuln_bundles": [
                {
                    "vuln_id": "NAME-CUSTOM-WEIRD-VULN",
                    "slug": "name-custom-weird-vuln",
                    "workspace_subdir": "app/name-custom-weird-vuln",
                },
                {
                    "vuln_id": "NAME-OPEN-REDIRECT",
                    "slug": "name-open-redirect",
                    "workspace_subdir": "app/name-open-redirect",
                },
            ]
        },
        "features": {"multi_vuln": True},
    }
    monkeypatch.setattr(pack_mod, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)
    monkeypatch.setattr(pack_mod, "get_artifacts_dir", lambda incoming_sid: tmp_path / "artifacts" / incoming_sid)

    manifest_path = pack_mod.write_manifest(sid, plan, filename="failure_manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    bundles = {entry["slug"]: entry for entry in manifest["bundles"]}

    assert bundles["name-custom-weird-vuln"]["failure"]["bundle_slug"] == "name-custom-weird-vuln"
    assert bundles["name-custom-weird-vuln"]["generalization"]["class"] == "unsupported_free_form_negative"
    assert bundles["name-open-redirect"].get("failure") == {}
    assert bundles["name-open-redirect"]["generalization"]["class"] != "unsupported_free_form_negative"
    assert manifest["partial_progress_summary"]["partial_success"] is False
    assert manifest["generation_origin"] == "mixed"
    assert manifest["dynamicness_verdict"] == "mixed"


def test_failed_bundles_metadata_maps_partial_research_failure_to_matching_bundle(
    tmp_path: Path, monkeypatch
) -> None:
    sid = "sid-pack-failed-bundles"
    metadata_dir = tmp_path / "metadata" / sid
    artifacts_dir = tmp_path / "artifacts" / sid
    workspace_dir = tmp_path / "workspaces" / sid / "app"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "loop_state.json").write_text(
        json.dumps(
            {
                "sid": sid,
                "last_result": "failure",
                "history": [
                    {
                        "loop": 1,
                        "stage": "RESEARCH",
                        "success": False,
                        "blocking": True,
                        "reason": "Bundle-scoped RESEARCH failures prevented full multi-bundle completion: name-custom-weird-vuln",
                        "fix_hint": "split the request",
                        "timestamp": "2026-03-09T12:52:06Z",
                        "metadata": {
                            "terminal_failure_class": "bundle_scoped_research_failure",
                            "retry_recommended": False,
                            "failed_bundles": [
                                {
                                    "bundle_slug": "name-custom-weird-vuln",
                                    "vuln_id": "NAME-CUSTOM-WEIRD-VULN",
                                    "quality_reason": "Insufficient researcher evidence for NAME-CUSTOM-WEIRD-VULN",
                                    "terminal_failure_class": "evidence_low_relevance",
                                }
                            ],
                            "runnable_bundles": ["name-open-redirect"],
                        },
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    failed_bundle_dir = metadata_dir / "bundles" / "name-custom-weird-vuln"
    ok_bundle_dir = metadata_dir / "bundles" / "name-open-redirect"
    failed_bundle_dir.mkdir(parents=True, exist_ok=True)
    ok_bundle_dir.mkdir(parents=True, exist_ok=True)
    (failed_bundle_dir / "semantic_profile.json").write_text(
        json.dumps({"support_level": "unsupported", "compiler_supported": False}, ensure_ascii=False),
        encoding="utf-8",
    )
    (ok_bundle_dir / "semantic_profile.json").write_text(
        json.dumps(
            {
                "support_level": "compiler_supported",
                "compiler_supported": True,
                "compiler_strategy": "open_redirect_reflect",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    plan = {
        "sid": sid,
        "paths": {
            "metadata": str(metadata_dir),
            "artifacts": str(artifacts_dir),
            "workspace": str(workspace_dir),
        },
        "requirement": {"vuln_ids": ["NAME-CUSTOM-WEIRD-VULN", "NAME-OPEN-REDIRECT"], "multi_vuln": True},
        "run_matrix": {
            "vuln_bundles": [
                {"vuln_id": "NAME-CUSTOM-WEIRD-VULN", "slug": "name-custom-weird-vuln", "workspace_subdir": "app/name-custom-weird-vuln"},
                {"vuln_id": "NAME-OPEN-REDIRECT", "slug": "name-open-redirect", "workspace_subdir": "app/name-open-redirect"},
            ]
        },
        "features": {"multi_vuln": True},
    }
    monkeypatch.setattr(pack_mod, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)
    monkeypatch.setattr(pack_mod, "get_artifacts_dir", lambda incoming_sid: tmp_path / "artifacts" / incoming_sid)

    manifest_path = pack_mod.write_manifest(sid, plan, filename="failure_manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    bundles = {entry["slug"]: entry for entry in manifest["bundles"]}

    assert bundles["name-custom-weird-vuln"]["failure"]["terminal_failure_class"] == "evidence_low_relevance"
    assert bundles["name-custom-weird-vuln"]["provenance"]["generation_origin"] == "research_short_circuit"
    assert bundles["name-open-redirect"]["failure"] == {}
    assert manifest["partial_progress_summary"]["research_blocked_bundles"] == 1


def test_write_manifest_rolls_up_multibundle_top_level_provenance_when_uniform(
    tmp_path: Path,
    monkeypatch,
) -> None:
    sid = "sid-pack-multi-supported-rollup"
    metadata_dir = tmp_path / "metadata" / sid
    artifacts_dir = tmp_path / "artifacts" / sid
    workspace_dir = tmp_path / "workspaces" / sid / "app"
    (artifacts_dir / "reports").mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "run").mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    for slug, vuln_id, strategy, family, fragment_id in (
        ("name-template-injection", "NAME-TEMPLATE-INJECTION", "template_injection_render", "template_injection", "render_template_string_concat"),
        ("name-open-redirect", "NAME-OPEN-REDIRECT", "open_redirect_reflect", "open_redirect", "redirect_next_route"),
    ):
        bundle_dir = metadata_dir / "bundles" / slug
        bundle_dir.mkdir(parents=True, exist_ok=True)
        (bundle_dir / "resolved_contract.json").write_text(
            json.dumps(
                {
                    "schema_version": "resolved_contract@1.0",
                    "slug": slug,
                    "vuln_id": vuln_id,
                    "compiler_supported": True,
                    "compiler_strategy": strategy,
                    "compiler_reason": "compiler strategy and scaffold are available",
                    "stack_scaffold_id": "python/flask",
                    "stack_scaffold_version": "1.0",
                    "compose_mode": "registry",
                    "provenance": {"generation_origin": "compiler_generated"},
                    "semantic_profile": {
                        "support_level": "compiler_supported",
                        "compiler_supported": True,
                        "compiler_strategy": strategy,
                        "compiler_reason": "compiler strategy and scaffold are available",
                        "family": family,
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (bundle_dir / "generator_manifest.json").write_text(
            json.dumps(
                {
                    "manifest": {
                        "metadata": {
                            "compiler_family": family,
                            "stack_scaffold_id": "python/flask",
                            "stack_scaffold_version": "1.0",
                            "fragment_id": fragment_id,
                            "compose_mode": "registry",
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    (metadata_dir / "loop_state.json").write_text(
        json.dumps({"sid": sid, "last_result": "success"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (artifacts_dir / "run" / "index.json").write_text(
        json.dumps(
            {
                "sid": sid,
                "runs": [
                    {"slug": "name-template-injection", "vuln_id": "NAME-TEMPLATE-INJECTION", "run_passed": True, "executed": True},
                    {"slug": "name-open-redirect", "vuln_id": "NAME-OPEN-REDIRECT", "run_passed": True, "executed": True},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (artifacts_dir / "reports" / "evals.json").write_text(
        json.dumps(
            {
                "overall_pass": True,
                "results": [
                    {
                        "slug": "name-template-injection",
                        "vuln_id": "NAME-TEMPLATE-INJECTION",
                        "verify_pass": True,
                        "status": "evaluated",
                        "verification_rule_source": "compiler_runtime_rule",
                        "verification_trust": "medium",
                    },
                    {
                        "slug": "name-open-redirect",
                        "vuln_id": "NAME-OPEN-REDIRECT",
                        "verify_pass": True,
                        "status": "evaluated",
                        "verification_rule_source": "compiler_runtime_rule",
                        "verification_trust": "medium",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    plan = {
        "sid": sid,
        "paths": {
            "metadata": str(metadata_dir),
            "artifacts": str(artifacts_dir),
            "workspace": str(workspace_dir),
        },
        "requirement": {"vuln_ids": ["NAME-TEMPLATE-INJECTION", "NAME-OPEN-REDIRECT"], "multi_vuln": True},
        "run_matrix": {
            "vuln_bundles": [
                {"vuln_id": "NAME-TEMPLATE-INJECTION", "slug": "name-template-injection", "workspace_subdir": "app/name-template-injection"},
                {"vuln_id": "NAME-OPEN-REDIRECT", "slug": "name-open-redirect", "workspace_subdir": "app/name-open-redirect"},
            ]
        },
        "features": {"multi_vuln": True},
    }
    monkeypatch.setattr(pack_mod, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)
    monkeypatch.setattr(pack_mod, "get_artifacts_dir", lambda incoming_sid: tmp_path / "artifacts" / incoming_sid)

    manifest_path = pack_mod.write_manifest(sid, plan)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["generation_origin"] == "compiler_generated"
    assert manifest["dynamicness_verdict"] == "compiler-first"
    assert manifest["verification_rule_source"] == "compiler_runtime_rule"
    assert manifest["verification_trust"] == "medium"
    assert manifest["stack_scaffold_id"] == "python/flask"
    assert manifest["stack_scaffold_version"] == "1.0"
    assert manifest["compose_mode"] == "registry"


def test_write_failure_manifest_surfaces_remote_evidence_missing_as_research_short_circuit(
    tmp_path: Path, monkeypatch
) -> None:
    sid = "sid-pack-remote-evidence-missing"
    metadata_dir = tmp_path / "metadata" / sid
    artifacts_dir = tmp_path / "artifacts" / sid
    workspace_dir = tmp_path / "workspaces" / sid / "app"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "loop_state.json").write_text(
        json.dumps(
            {
                "sid": sid,
                "last_result": "failure",
                "history": [
                    {
                        "loop": 1,
                        "stage": "RESEARCH",
                        "success": False,
                        "blocking": True,
                        "reason": "Insufficient researcher evidence for CWE-9999",
                        "fix_hint": "configure remote provider",
                        "timestamp": "2026-03-08T02:10:32Z",
                        "metadata": {
                            "terminal_failure_class": "remote_provider_unavailable",
                            "retry_recommended": False,
                            "search_provider": "none",
                            "search_configured": False,
                        },
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    write_generator_contract(
        metadata_dir,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": sid,
            "slug": "cwe-9999",
            "vuln_id": "CWE-9999",
            "semantic_profile": {
                "schema_version": "semantic_profile@1.0",
                "sid": sid,
                "slug": "cwe-9999",
                "normalized_vuln_id": "CWE-9999",
                "family": "cwe_9999",
                "support_level": "unsupported",
                "compiler_supported": False,
                "compiler_reason": "semantic family unsupported for compiler-backed generation",
            },
        },
    )
    plan = {
        "sid": sid,
        "paths": {
            "metadata": str(metadata_dir),
            "artifacts": str(artifacts_dir),
            "workspace": str(workspace_dir),
        },
        "requirement": {"vuln_id": "CWE-9999"},
        "run_matrix": {"vuln_bundles": [{"vuln_id": "CWE-9999", "slug": "cwe-9999", "workspace_subdir": "app"}]},
        "features": {"multi_vuln": False},
    }
    monkeypatch.setattr(pack_mod, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)
    monkeypatch.setattr(pack_mod, "get_artifacts_dir", lambda incoming_sid: tmp_path / "artifacts" / incoming_sid)

    manifest_path = pack_mod.write_manifest(sid, plan, filename="failure_manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["failure"]["terminal_failure_class"] == "remote_provider_unavailable"
    assert manifest["bundles"][0]["failure"]["terminal_failure_class"] == "remote_provider_unavailable"
    assert manifest["bundles"][0]["provenance"]["generation_origin"] == "research_short_circuit"
    assert manifest["bundles"][0]["provenance"]["failure_class"] == "remote_provider_unavailable"
    assert manifest["bundles"][0]["dynamicness"]["verdict"] == "pre-generation fail-closed"
    assert manifest["bundles"][0]["dynamicness"]["reason"] == "generation was skipped after remote evidence precheck"
