from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator.pack import _bundle_promotion_status, _promotion_summary
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
