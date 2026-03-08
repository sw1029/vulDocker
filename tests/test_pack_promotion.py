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
    assert manifest["compiler_contract_summary"]["by_strategy"] == {"sqli_string_concat": 1}
    assert manifest["compiler_contract_summary"]["by_support_level"] == {"builtin_supported": 1}
    assert manifest["bundles"][0]["provenance"]["generation_origin"] == "deterministic_fallback"
    assert manifest["bundles"][0]["provenance"]["fallback_used"] is True
    assert manifest["bundles"][0]["provenance"]["fallback_class"] == "generic_unsupported_family"
    assert manifest["bundles"][0]["compiler_contract"]["compiler_supported"] is False
    assert manifest["bundles"][0]["compiler_contract"]["compiler_strategy"] == "sqli_string_concat"
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
            "provenance": {
                "generation_origin": "llm_manifest",
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
    assert manifest["bundles"][0]["dynamicness"]["verdict"] == "compiler-first"
    assert manifest["compiler_contract_summary"]["supported_bundles"] == 1


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
