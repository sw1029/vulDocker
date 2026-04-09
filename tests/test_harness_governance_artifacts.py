from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import orchestrator.pack as pack_mod

from common.action_trace import emit_action_trace, load_action_trace, summarize_action_trace
from common.observations import append_observation, load_observations, summarize_observations
from common.stage_gates import load_stage_gate_report, record_stage_gate, summarize_stage_gates


def _load_harness_audit_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "ops" / "ci" / "harness_audit.py"
    spec = importlib.util.spec_from_file_location("test_harness_audit_module", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _base_plan(sid: str, metadata_dir: Path, artifacts_dir: Path, workspace_dir: Path) -> dict:
    return {
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


def test_harness_governance_helpers_fan_out_bundle_and_root(tmp_path: Path) -> None:
    metadata_root = tmp_path / "metadata" / "sid-governance"
    bundle_dir = metadata_root / "bundles" / "cwe-89"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    emit_action_trace(
        bundle_dir,
        sid="sid-governance",
        stage="GENERATOR",
        action_id="file_manifest_validate",
        status="failure",
        blocking=True,
        failure_class="manifest_validation_failed",
        detail="guard rejected all candidates",
    )
    record_stage_gate(
        bundle_dir,
        sid="sid-governance",
        gate_id="post_generator_live_path_gate",
        stage="GENERATOR",
        passed=False,
        blocking=True,
        failure_class="manifest_validation_failed",
        detail="guard rejected all candidates",
    )
    append_observation(
        bundle_dir,
        sid="sid-governance",
        observation_type="generator_failure",
        failure_stage="GENERATOR",
        failure_class="manifest_validation_failed",
        result="failure",
    )

    local_trace = summarize_action_trace(load_action_trace(bundle_dir))
    root_trace = summarize_action_trace(load_action_trace(metadata_root))
    local_gates = summarize_stage_gates(load_stage_gate_report(bundle_dir))
    root_gates = summarize_stage_gates(load_stage_gate_report(metadata_root))
    local_obs = summarize_observations(load_observations(bundle_dir))
    root_obs = summarize_observations(load_observations(metadata_root))

    assert local_trace["failure_count"] == 1
    assert root_trace["failure_count"] == 1
    assert local_trace["first_failure_action"]["action_id"] == "file_manifest_validate"
    assert local_gates["failed"] == 1
    assert root_gates["failed"] == 1
    assert local_obs["total_observations"] == 1
    assert root_obs["total_observations"] == 1


def test_write_manifest_surfaces_harness_governance_summaries(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-pack-governance"
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
        json.dumps({"sid": sid, "vuln_id": "CWE-89", "quality": "sufficient"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (metadata_dir / "reviewer_report.json").write_text(
        json.dumps({"blocking": False, "success": True, "blocking_bundles": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    (artifacts_dir / "run" / "summary.json").write_text(
        json.dumps({"run_passed": True, "oracle_execution_parity": "confirmed"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (artifacts_dir / "reports" / "evals.json").write_text(
        json.dumps(
            {"results": [{"slug": "cwe-89", "vuln_id": "CWE-89", "verify_pass": True, "oracle_execution_parity": "confirmed"}]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    emit_action_trace(
        metadata_dir,
        sid=sid,
        stage="RESEARCH",
        action_id="query_plan_emit",
        status="success",
    )
    record_stage_gate(
        metadata_dir,
        sid=sid,
        gate_id="post_research_authority_gate",
        stage="RESEARCH",
        passed=True,
        detail="sufficient evidence",
    )
    append_observation(
        metadata_dir,
        sid=sid,
        observation_type="review_blocker",
        failure_stage="REVIEW",
        failure_class="review_blocking",
        result="failure",
    )

    monkeypatch.setattr(pack_mod, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)
    monkeypatch.setattr(pack_mod, "get_artifacts_dir", lambda incoming_sid: tmp_path / "artifacts" / incoming_sid)

    manifest_path = pack_mod.write_manifest(sid, _base_plan(sid, metadata_dir, artifacts_dir, workspace_dir))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["action_trace_summary"]["total_actions"] >= 1
    assert manifest["stage_gate_summary"]["total_gates"] >= 1
    assert manifest["observation_summary"]["total_observations"] == 1
    assert Path(manifest["canonical_snapshot_path"]).exists()
    assert manifest["bundles"][0]["action_trace_summary"]["total_actions"] >= 1


def test_harness_audit_scores_new_governance_artifacts(tmp_path: Path) -> None:
    audit_mod = _load_harness_audit_module()
    metadata_dir = tmp_path / "metadata" / "sid-audit"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "canonical_snapshot.json").write_text("{}", encoding="utf-8")
    manifest = {
        "action_trace_summary": {"total_actions": 4, "first_failure_action": {"action_id": "executor_precheck"}},
        "stage_gate_summary": {"total_gates": 2},
        "observation_summary": {"total_observations": 1},
        "oracle_execution_parity": "confirmed",
        "verification_summary": {"verified_bundles": 1},
        "reports": {"evals": {"results": []}},
    }

    audit, overall = audit_mod._audit_manifest(manifest, metadata_dir)

    assert overall > 0
    assert audit["overall_score"] == overall
    assert audit["failing_checks"] == []
    assert audit["top_actions"][0]["action_id"] == "executor_precheck"
