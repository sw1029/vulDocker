from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator.pack import _bundle_dynamicness_verdict, _bundle_promotion_status, _promotion_summary
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
            "generation_origin": "deterministic_fallback",
            "fallback_used": True,
            "family_override_applied": False,
            "llm_stub_used": True,
            "provenance": {
                "generation_origin": "deterministic_fallback",
                "fallback_used": True,
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
    assert manifest["generation_summary"]["by_origin"] == {"deterministic_fallback": 1}
    assert manifest["generation_summary"]["by_dynamicness_verdict"] == {"deterministic fallback dependent": 1}
    assert manifest["generation_summary"]["llm_stub_bundles"] == 1
    assert manifest["bundles"][0]["provenance"]["generation_origin"] == "deterministic_fallback"
    assert manifest["bundles"][0]["provenance"]["fallback_used"] is True
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
    assert manifest["bundles"][0]["dynamicness"]["verdict"] == "deterministic fallback dependent"
