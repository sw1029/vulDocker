from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _run_cli(*args: str) -> dict:
    proc = subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(proc.stdout)


def test_support_cli_workflow_materializes_reviewable_accept_path(tmp_path: Path) -> None:
    candidate_dir = tmp_path / "reviewable-run"
    candidate_path = _write_json(
        candidate_dir / "support_candidate.json",
        {
            "schema_version": "support_candidate@0.1",
            "case_name": "cwe-89-basic",
            "sid": "sid-reviewable",
            "manifest_path": "/tmp/manifest-a.json",
            "support_ready_bundle_count": 1,
            "mechanically_healthy_bundle_count": 1,
            "promotion_policy_ready_bundle_count": 1,
            "reviewable_bundle_count": 1,
            "all_reviewable": True,
            "candidates": [
                {
                    "slug": "cwe-89",
                    "vuln_id": "CWE-89",
                    "reviewable": True,
                    "support_promotion_eligible": True,
                    "support_status": "reviewable",
                    "blockers": [],
                    "mechanical_blockers": [],
                    "promotion_policy_blockers": [],
                    "gates": {
                        "verdict_authority_ready": True,
                        "measured_gate_ready": True,
                        "mechanically_healthy": True,
                        "promotion_policy_ready": True,
                        "generation_path_live_positive_ready": True,
                    },
                        "primitive_signature": {"selected_family": "sqli", "selected_stack_id": "python/flask"},
                        "runtime_contract": {"topology": "single_service"},
                        "oracle_contract": {"oracle_execution_parity": "high"},
                        "generation_materialization": {"schema_version": "generation_materialization@0.1", "path_class": "live"},
                        "generation_path": {"path_class": "live", "positive_bucket": "live_positive"},
                        "verdict_authority_mode": "single_bundle",
                    "verdict_authority_consistent": True,
                    "source_artifacts": {"summary_path": "/tmp/summary-a.json", "workspace": "/tmp/workspace-a"},
                }
            ],
        },
    )
    review_index_path = tmp_path / "support_review_index.json"
    review_stdout = _run_cli("tests/e2e/support_review.py", str(candidate_dir), "--output", str(review_index_path))
    assert review_stdout["reviewable_bundle_count"] == 1
    assert review_stdout["all_reviewable_case_count"] == 1
    assert review_stdout["mixed_case_count"] == 0
    assert review_stdout["all_blocked_case_count"] == 0
    assert review_stdout["by_case_status"] == {"all_reviewable": 1}
    assert review_stdout["all_reviewable_cases"] == ["cwe-89-basic"]
    assert review_stdout["mixed_cases"] == []
    assert review_stdout["all_blocked_cases"] == []
    assert review_stdout["by_support_status"] == {"reviewable": 1}
    assert review_stdout["by_generation_path_class"] == {"live": 1}
    assert review_stdout["by_generation_positive_bucket"] == {"live_positive": 1}
    assert review_stdout["by_generation_non_live_reason"] == {}
    assert review_stdout["mechanically_healthy_bundle_count"] == 1
    assert review_stdout["promotion_policy_ready_bundle_count"] == 1
    assert review_stdout["live_positive_ready_bundle_count"] == 1

    decisions_path = _write_json(
        tmp_path / "support_review_decisions.json",
        {
            "schema_version": "support_review_decisions@0.1",
            "decisions": [
                {
                    "case_name": "cwe-89-basic",
                    "slug": "cwe-89",
                    "decision": "accept",
                    "reviewer": "alice",
                    "rationale": "synthetic reviewable lane",
                }
            ],
        },
    )
    registry_update_path = tmp_path / "support_registry_update.json"
    decide_stdout = _run_cli(
        "tests/e2e/support_decide.py",
        "--review-index",
        str(review_index_path),
        "--decisions",
        str(decisions_path),
        "--output",
        str(registry_update_path),
    )
    assert decide_stdout["accepted_count"] == 1
    assert decide_stdout["all_reviewable_case_count"] == 1
    assert decide_stdout["mixed_case_count"] == 0
    assert decide_stdout["all_blocked_case_count"] == 0
    assert decide_stdout["by_case_status"] == {"all_reviewable": 1}
    assert decide_stdout["all_reviewable_cases"] == ["cwe-89-basic"]
    assert decide_stdout["mixed_cases"] == []
    assert decide_stdout["all_blocked_cases"] == []
    assert decide_stdout["accepted_by_support_status"] == {"reviewable": 1}
    assert decide_stdout["rejected_by_support_status"] == {}
    assert decide_stdout["pending_by_support_status"] == {}
    assert decide_stdout["by_generation_non_live_reason"] == {}

    registry_path = tmp_path / "curated_support_registry.json"
    apply_stdout = _run_cli(
        "tests/e2e/support_apply.py",
        "--registry-update",
        str(registry_update_path),
        "--output",
        str(registry_path),
    )
    assert apply_stdout["registry_item_count"] == 1
    assert apply_stdout["all_accepted_case_count"] == 1
    assert apply_stdout["mixed_review_status_case_count"] == 0
    assert apply_stdout["all_rejected_case_count"] == 0
    assert apply_stdout["by_review_status"] == {"accepted": 1}
    assert apply_stdout["by_support_status"] == {"reviewable": 1}
    assert apply_stdout["by_case_review_status"] == {"all_accepted": 1}
    assert apply_stdout["all_accepted_cases"] == ["cwe-89-basic"]
    assert apply_stdout["mixed_review_status_cases"] == []
    assert apply_stdout["all_rejected_cases"] == []
    assert apply_stdout["by_generation_non_live_reason"] == {}
    assert apply_stdout["schema_status"] == "normalized"
    assert apply_stdout["schema_upgraded_item_count"] == 0
    assert apply_stdout["by_schema_upgrade_reason"] == {}
    assert apply_stdout["schema_upgraded_update_count"] == 0
    assert apply_stdout["by_update_schema_upgrade_reason"] == {}
    assert apply_stdout["schema_upgraded_decision_event_count"] == 0
    assert apply_stdout["by_decision_schema_upgrade_reason"] == {}

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assert registry["registry_item_count"] == 1
    assert registry["by_review_status"] == {"accepted": 1}
    assert registry["by_support_status"] == {"reviewable": 1}
    assert registry["by_case_review_status"] == {"all_accepted": 1}
    assert registry["by_generation_non_live_reason"] == {}
    assert registry["items"][0]["review_status"] == "accepted"
    assert registry["items"][0]["support_status"] == "reviewable"


def test_support_cli_workflow_preserves_blocked_noop_path(tmp_path: Path) -> None:
    candidate_dir = tmp_path / "blocked-run"
    _write_json(
        candidate_dir / "support_candidate.json",
        {
            "schema_version": "support_candidate@0.1",
            "case_name": "sqli-sidecar-compiler-custom-env",
            "sid": "sid-blocked",
            "manifest_path": "/tmp/manifest-b.json",
            "support_ready_bundle_count": 0,
            "mechanically_healthy_bundle_count": 0,
            "promotion_policy_ready_bundle_count": 0,
            "reviewable_bundle_count": 0,
            "all_reviewable": False,
            "candidates": [
                {
                    "slug": "cwe-89",
                    "vuln_id": "CWE-89",
                    "reviewable": False,
                    "support_promotion_eligible": False,
                    "support_status": "blocked_mixed",
                    "blockers": [
                        "strict_open_world:strict_curated_lower_bound",
                        "open_world:catalog_resolved_lower_bound",
                        "oracle_clarity:medium",
                        "family_evidence:candidate_unbacked",
                        "measured_gate:cache_reuse_inconsistent",
                    ],
                    "mechanical_blockers": ["measured_gate:cache_reuse_inconsistent"],
                    "promotion_policy_blockers": [
                        "strict_open_world:strict_curated_lower_bound",
                        "open_world:catalog_resolved_lower_bound",
                        "oracle_clarity:medium",
                        "family_evidence:candidate_unbacked",
                    ],
                    "gates": {
                        "verdict_authority_ready": True,
                        "measured_gate_ready": False,
                        "mechanically_healthy": False,
                        "promotion_policy_ready": False,
                        "generation_path_live_positive_ready": False,
                    },
                        "primitive_signature": {"selected_family": "sqli", "selected_stack_id": "python/flask"},
                        "runtime_contract": {"topology": "service_plus_sidecar"},
                        "oracle_contract": {"oracle_execution_parity": "high"},
                        "generation_materialization": {
                            "schema_version": "generation_materialization@0.1",
                            "path_class": "fixture",
                            "non_live_reason": "fixture_backed",
                        },
                        "generation_path": {"path_class": "fixture", "positive_bucket": "fixture_backed_positive"},
                        "verdict_authority_mode": "single_bundle",
                    "verdict_authority_consistent": True,
                    "source_artifacts": {"summary_path": "/tmp/summary-b.json", "workspace": "/tmp/workspace-b"},
                }
            ],
        },
    )
    review_index_path = tmp_path / "support_review_index.json"
    review_stdout = _run_cli("tests/e2e/support_review.py", str(candidate_dir), "--output", str(review_index_path))
    assert review_stdout["reviewable_bundle_count"] == 0
    assert review_stdout["all_reviewable_case_count"] == 0
    assert review_stdout["mixed_case_count"] == 0
    assert review_stdout["all_blocked_case_count"] == 1
    assert review_stdout["by_case_status"] == {"all_blocked": 1}
    assert review_stdout["all_reviewable_cases"] == []
    assert review_stdout["mixed_cases"] == []
    assert review_stdout["all_blocked_cases"] == ["sqli-sidecar-compiler-custom-env"]
    assert review_stdout["by_support_status"] == {"blocked_mixed": 1}
    assert review_stdout["by_generation_path_class"] == {"fixture": 1}
    assert review_stdout["by_generation_positive_bucket"] == {"fixture_backed_positive": 1}
    assert review_stdout["by_generation_non_live_reason"] == {"fixture_backed": 1}
    assert review_stdout["mechanically_healthy_bundle_count"] == 0
    assert review_stdout["promotion_policy_ready_bundle_count"] == 0
    assert review_stdout["live_positive_blocked_bundle_count"] == 1

    decisions_path = _write_json(
        tmp_path / "support_review_decisions.json",
        {
            "schema_version": "support_review_decisions@0.1",
            "decisions": [],
        },
    )
    registry_update_path = tmp_path / "support_registry_update.json"
    decide_stdout = _run_cli(
        "tests/e2e/support_decide.py",
        "--review-index",
        str(review_index_path),
        "--decisions",
        str(decisions_path),
        "--output",
        str(registry_update_path),
    )
    assert decide_stdout["accepted_count"] == 0
    assert decide_stdout["rejected_count"] == 0
    assert decide_stdout["pending_count"] == 0
    assert decide_stdout["all_reviewable_case_count"] == 0
    assert decide_stdout["mixed_case_count"] == 0
    assert decide_stdout["all_blocked_case_count"] == 1
    assert decide_stdout["by_case_status"] == {"all_blocked": 1}
    assert decide_stdout["all_reviewable_cases"] == []
    assert decide_stdout["mixed_cases"] == []
    assert decide_stdout["all_blocked_cases"] == ["sqli-sidecar-compiler-custom-env"]
    assert decide_stdout["accepted_by_support_status"] == {}
    assert decide_stdout["rejected_by_support_status"] == {}
    assert decide_stdout["pending_by_support_status"] == {}
    assert decide_stdout["by_generation_non_live_reason"] == {"fixture_backed": 1}

    registry_path = tmp_path / "curated_support_registry.json"
    apply_stdout = _run_cli(
        "tests/e2e/support_apply.py",
        "--registry-update",
        str(registry_update_path),
        "--output",
        str(registry_path),
    )
    assert apply_stdout["registry_item_count"] == 0
    assert apply_stdout["all_accepted_case_count"] == 0
    assert apply_stdout["mixed_review_status_case_count"] == 0
    assert apply_stdout["all_rejected_case_count"] == 0
    assert apply_stdout["by_review_status"] == {}
    assert apply_stdout["by_support_status"] == {}
    assert apply_stdout["by_case_review_status"] == {}
    assert apply_stdout["all_accepted_cases"] == []
    assert apply_stdout["mixed_review_status_cases"] == []
    assert apply_stdout["all_rejected_cases"] == []
    assert apply_stdout["by_generation_non_live_reason"] == {}
    assert apply_stdout["schema_status"] == "normalized"
    assert apply_stdout["schema_upgraded_item_count"] == 0
    assert apply_stdout["by_schema_upgrade_reason"] == {}
    assert apply_stdout["schema_upgraded_update_count"] == 0
    assert apply_stdout["by_update_schema_upgrade_reason"] == {}
    assert apply_stdout["schema_upgraded_decision_event_count"] == 0
    assert apply_stdout["by_decision_schema_upgrade_reason"] == {}

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assert registry["registry_item_count"] == 0
    assert registry["by_review_status"] == {}
    assert registry["by_support_status"] == {}
    assert registry["by_case_review_status"] == {}
    assert registry["by_generation_non_live_reason"] == {}
    assert registry["last_update"]["by_generation_non_live_reason"] == {"fixture_backed": 1}
