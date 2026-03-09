from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator.pack import (
    _bundle_dynamicness_verdict,
    _bundle_generalization_verdict,
    _generalization_summary,
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


def test_bundle_generalization_marks_real_free_form_compiler_first_bundle_as_positive() -> None:
    bundle = VulnBundle(vuln_id="NAME-OPEN-REDIRECT", slug="name-open-redirect", workspace_subdir="app")

    verdict = _bundle_generalization_verdict(
        bundle,
        pattern_id="open-redirect",
        promotion={"eligible": True},
        dynamicness={"verdict": "compiler-first"},
        compiler_contract={"support_level": "compiler_supported", "compiler_supported": True},
        provenance={"generation_origin": "compiler_generated"},
    )
    summary = _generalization_summary([{"generalization": verdict}])

    assert verdict["class"] == "real_free_form_positive"
    assert verdict["counts_as_generalization"] is True
    assert "compiler-first" in verdict["reason"]
    assert summary["positive_generalization_bundles"] == 1
    assert summary["by_class"]["real_free_form_positive"] == 1


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
    assert manifest["verification_summary"]["low_trust_bundles"] == 1
    assert manifest["bundles"][0]["provenance"]["generation_origin"] == "deterministic_fallback"
    assert manifest["bundles"][0]["provenance"]["fallback_used"] is True
    assert manifest["bundles"][0]["provenance"]["fallback_class"] == "generic_unsupported_family"
    assert manifest["bundles"][0]["verification"]["rule_source"] == "generator_manifest_fallback"
    assert manifest["bundles"][0]["verification"]["trust"] == "low"
    assert manifest["verification_rule_source"] == "generator_manifest_fallback"
    assert manifest["verification_trust"] == "low"
    assert manifest["bundles"][0]["compiler_contract"]["compiler_supported"] is False
    assert manifest["bundles"][0]["compiler_contract"]["compiler_strategy"] == "sqli_string_concat"
    assert manifest["bundles"][0]["compiler_contract"]["service_env"] == {
        "APP_PORT": "5000",
        "DB_HOST": "sqli-db",
    }
    assert manifest["service_env"] == {"APP_PORT": "5000", "DB_HOST": "sqli-db"}
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
    assert manifest["generation_summary"]["llm_fixture_bundles"] == 1
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
        "requirement": {"vuln_id": "NAME-OPEN-REDIRECT"},
        "run_matrix": {"vuln_bundles": [{"vuln_id": "NAME-OPEN-REDIRECT", "slug": "name-open-redirect", "workspace_subdir": "app"}]},
        "features": {"multi_vuln": False},
    }
    monkeypatch.setattr(pack_mod, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)
    monkeypatch.setattr(pack_mod, "get_artifacts_dir", lambda incoming_sid: tmp_path / "artifacts" / incoming_sid)

    manifest_path = pack_mod.write_manifest(sid, plan)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["compiler_supported"] is True
    assert manifest["compiler_strategy"] == "open_redirect_reflect"
    assert manifest["compiler_family"] == "open_redirect"
    assert manifest["stack_scaffold_id"] == "python/flask"
    assert manifest["stack_scaffold_version"] == "1.0"
    assert manifest["fragment_id"] == "redirect_next_route"
    assert manifest["compose_mode"] == "registry"
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
    assert manifest["verification_summary"]["by_rule_source"] == {"compiler_runtime_rule": 1}
    assert manifest["verification_summary"]["by_trust"] == {"medium": 1}
    assert manifest["verification_summary"]["low_trust_bundles"] == 0


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
                                    "slug": "name-ldap-injection",
                                    "vuln_id": "NAME-LDAP-INJECTION",
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
            "slug": "name-ldap-injection",
            "vuln_id": "NAME-LDAP-INJECTION",
            "semantic_profile": {
                "schema_version": "semantic_profile@1.0",
                "sid": sid,
                "slug": "name-ldap-injection",
                "normalized_vuln_id": "NAME-LDAP-INJECTION",
                "family": "ldap_injection",
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
        "requirement": {"vuln_id": "NAME-LDAP-INJECTION"},
        "run_matrix": {
            "vuln_bundles": [
                {
                    "vuln_id": "NAME-LDAP-INJECTION",
                    "slug": "name-ldap-injection",
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
    assert manifest["bundles"][0]["failure"]["terminal_failure_class"] == "semantic_support_missing"
    assert manifest["bundles"][0]["provenance"]["generation_origin"] == "research_short_circuit"
    assert manifest["bundles"][0]["provenance"]["source"] == "loop_state"
    assert manifest["bundles"][0]["dynamicness"]["verdict"] == "pre-generation fail-closed"


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
