from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator.support_extract import (
    build_support_candidate,
    build_curated_support_registry,
    build_support_review_index,
    build_support_registry_update,
    write_support_candidate,
    write_curated_support_registry,
    write_support_review_index,
    write_support_registry_update,
)
from tests.e2e.support_review import _collect_support_candidate_paths


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _support_bundle(*, eligible: bool = True) -> dict:
    return {
        "slug": "cwe-89",
        "vuln_id": "CWE-89",
        "support_promotion": {"eligible": eligible, "reasons": [] if eligible else ["artifact_quality:medium"]},
        "request_ir": {
            "request_label": "SQL Injection",
            "provisional_family": "sqli",
            "primitive_hypotheses": [{"kind": "input_to_sink", "sink": "sql_query"}],
            "runtime_dependency_hypotheses": [{"kind": "database", "engine": "mysql"}],
            "topology_hypotheses": [{"topology": "service_plus_sidecar"}],
            "selection_decision": {
                "family": {"selected_family": "sqli"},
                "stack": {"selected_stack_id": "python/flask"},
                "scenario": {"selected_scenario_id": "scenario-1", "selected_topology": "service_plus_sidecar"},
            },
        },
        "name_only_outcome": {
            "request_kind": "name_only",
            "mode": "strict_dynamic",
            "selected_family": "sqli",
            "selected_stack_id": "python/flask",
        },
        "name_only_generation_spec": {"planning_focus_summary": {"primary_focus": "runtime_or_oracle_design"}},
        "runtime_recipe": {
            "framework": "flask",
            "topology": "service_plus_sidecar",
            "service_port": 5000,
            "service_env": {"DB_HOST": "db", "APP_PORT": "5000"},
            "sidecars": [{"name": "db", "image": "mysql:8", "aliases": ["db"], "env": {"MYSQL_DATABASE": "appdb"}}],
        },
        "runtime_graph": {"topology": "service_plus_sidecar"},
        "executor_plan": {
            "topology": "service_plus_sidecar",
            "base_url": "http://127.0.0.1:5000",
            "healthchecks": [{"transport": "http", "path": "/health"}],
            "service_env": {"DB_HOST": "db", "APP_PORT": "5000"},
            "sidecars": [
                {
                    "name": "db",
                    "image": "mysql:8",
                    "aliases": ["db"],
                    "env": {"MYSQL_DATABASE": "appdb"},
                    "ready_probe": {"transport": "tcp", "port": 3306},
                }
            ],
        },
        "exploit_oracle": {
            "success_signature": "SQLI_SUCCESS",
            "flag_token": "FLAG{SQLI}",
            "poc_cmd": "python poc.py",
            "negative_controls": [{"name": "benign", "payload": "user"}],
            "metamorphic": {"relation": "payload_strengthening", "cases": [{"name": "union", "payload": "' UNION SELECT 1--"}]},
        },
        "verification": {
            "rule_source": "declared_rule",
            "trust": "high",
            "independence": "independent",
            "oracle_execution_parity": "high",
            "oracle_execution_attempted": True,
            "oracle_negative_controls_pass": True,
            "oracle_metamorphic_pass": True,
        },
        "artifact_quality": {"oracle_execution_parity": "high"},
        "compiler_contract": {
            "compiler_strategy": "sqli_string_concat_mysql",
            "fragment_id": "mysql_query_concat",
            "compose_mode": "single_file",
        },
        "provenance": {
            "generation_origin": "compiler_generated",
            "fallback_class": "",
            "materializer": "compiler",
        },
        "dynamicness": {"verdict": "compiler-first"},
        "paths": {
            "workspace": "/tmp/workspace",
            "metadata": "/tmp/metadata",
            "build": "/tmp/build",
            "run": "/tmp/run",
        },
    }


def test_build_support_candidate_creates_reviewable_package_when_all_gates_pass(tmp_path: Path) -> None:
    manifest_path = _write_json(
        tmp_path / "manifest.json",
        {
            "sid": "sid-support",
            "bundles": [_support_bundle(eligible=True)],
        },
    )
    summary_path = _write_json(
        tmp_path / "summary.json",
        {
            "sid": "sid-support",
            "case_name": "cwe-89-basic",
            "manifest_path": str(manifest_path),
            "verdict_authority": {
                "mode": "single_bundle",
                "fields": {
                    "run_passed": {"projection_mode": "single_bundle_exact"},
                    "verify_pass": {"projection_mode": "single_bundle_exact"},
                    "oracle_execution_parity": {"projection_mode": "single_bundle_exact"},
                },
            },
        },
    )
    matrix_report = {
        "covered_cases": ["cwe-89-basic"],
        "failed_cases": [],
        "repeatability_failures": [],
        "authority_observations": {"by_verdict_authority_mode": {"single_bundle": 1}},
    }
    repeatability_report = {
        "case": "cwe-89-basic",
        "passed": True,
        "report_path": str(tmp_path / "repeatability_report.json"),
        "matrix_report_path": str(tmp_path / "matrix_report.json"),
        "observed_verdict_authority_modes": ["single_bundle"],
        "observed_verdict_projection_modes": {
            "run_passed": ["single_bundle_exact"],
            "verify_pass": ["single_bundle_exact"],
        },
        "verdict_authority_consistent": True,
        "measured_gate": {"ready": True, "blockers": []},
    }

    payload = build_support_candidate(
        summary_path,
        matrix_report=matrix_report,
        repeatability_report=repeatability_report,
    )

    assert payload["schema_version"] == "support_candidate@0.1"
    assert payload["support_ready_bundle_count"] == 1
    assert payload["mechanically_healthy_bundle_count"] == 1
    assert payload["promotion_policy_ready_bundle_count"] == 1
    assert payload["by_support_status"] == {"reviewable": 1}
    assert payload["reviewable_bundle_count"] == 1
    assert payload["all_reviewable"] is True
    assert payload["authority_gate"] == {
        "available": True,
        "summary_mode": "single_bundle",
        "repeatability_consistent": True,
        "blockers": [],
    }
    assert payload["measured_authority"]["summary_verdict_authority_mode"] == "single_bundle"
    assert payload["measured_authority"]["repeatability_verdict_authority_consistent"] is True
    assert payload["measured_authority"]["matrix_authority_observations"] == {
        "by_verdict_authority_mode": {"single_bundle": 1}
    }
    candidate = payload["candidates"][0]
    assert candidate["support_promotion_eligible"] is True
    assert candidate["reviewable"] is True
    assert candidate["support_status"] == "reviewable"
    assert candidate["mechanical_blockers"] == []
    assert candidate["promotion_policy_blockers"] == []
    assert candidate["gates"]["matrix_case_green"] is True
    assert candidate["gates"]["repeatability_passed"] is True
    assert candidate["gates"]["measured_gate_ready"] is True
    assert candidate["gates"]["verdict_authority_ready"] is True
    assert candidate["gates"]["mechanically_healthy"] is True
    assert candidate["gates"]["promotion_policy_ready"] is True
    assert candidate["primitive_signature"]["selected_family"] == "sqli"
    assert candidate["primitive_signature"]["selected_stack_id"] == "python/flask"
    assert candidate["runtime_contract"]["topology"] == "service_plus_sidecar"
    assert candidate["runtime_contract"]["service_env_keys"] == ["APP_PORT", "DB_HOST"]
    assert candidate["oracle_contract"]["oracle_execution_parity"] == "high"
    assert candidate["verdict_authority_mode"] == "single_bundle"
    assert candidate["verdict_authority_consistent"] is True
    assert candidate["oracle_contract"]["negative_controls_with_payload"] == 1
    assert candidate["unsafe_pattern"]["compiler_strategy"] == "sqli_string_concat_mysql"


def test_build_support_candidate_marks_external_gate_failures_without_losing_internal_signal(tmp_path: Path) -> None:
    manifest_path = _write_json(
        tmp_path / "manifest.json",
        {
            "sid": "sid-support-blocked",
            "bundles": [_support_bundle(eligible=True)],
        },
    )
    summary_path = _write_json(
        tmp_path / "summary.json",
        {
            "sid": "sid-support-blocked",
            "case_name": "cwe-89-basic",
            "manifest_path": str(manifest_path),
            "verdict_authority": {"mode": "multi_bundle", "fields": {}},
        },
    )

    payload = build_support_candidate(
        summary_path,
        matrix_report={
            "covered_cases": ["cwe-89-basic"],
            "failed_cases": ["cwe-89-basic"],
            "repeatability_failures": [],
            "authority_observations": {"by_verdict_authority_mode": {"multi_bundle": 1}},
        },
        repeatability_report={
            "case": "cwe-89-basic",
            "passed": False,
            "observed_verdict_authority_modes": ["multi_bundle"],
            "verdict_authority_consistent": False,
            "measured_gate": {"ready": False, "blockers": ["verdict_authority_inconsistent"]},
        },
    )

    assert payload["support_ready_bundle_count"] == 1
    assert payload["mechanically_healthy_bundle_count"] == 0
    assert payload["promotion_policy_ready_bundle_count"] == 1
    assert payload["by_support_status"] == {"mechanically_blocked": 1}
    assert payload["reviewable_bundle_count"] == 0
    assert payload["all_reviewable"] is False
    assert payload["authority_gate"] == {
        "available": True,
        "summary_mode": "multi_bundle",
        "repeatability_consistent": False,
        "blockers": ["verdict_authority:inconsistent"],
    }
    candidate = payload["candidates"][0]
    assert candidate["support_promotion_eligible"] is True
    assert candidate["reviewable"] is False
    assert candidate["support_status"] == "mechanically_blocked"
    assert candidate["verdict_authority_mode"] == "multi_bundle"
    assert candidate["verdict_authority_consistent"] is False
    assert candidate["mechanical_blockers"] == [
        "matrix_gate:not_green",
        "repeatability_gate:failed",
        "measured_gate:verdict_authority_inconsistent",
        "verdict_authority:inconsistent",
    ]
    assert candidate["promotion_policy_blockers"] == []
    assert candidate["gates"]["measured_gate_ready"] is False
    assert candidate["gates"]["verdict_authority_ready"] is False
    assert candidate["gates"]["mechanically_healthy"] is False
    assert candidate["gates"]["promotion_policy_ready"] is True
    assert "matrix_gate:not_green" in candidate["blockers"]
    assert "repeatability_gate:failed" in candidate["blockers"]
    assert "measured_gate:verdict_authority_inconsistent" in candidate["blockers"]
    assert "verdict_authority:inconsistent" in candidate["blockers"]


def test_build_support_candidate_blocks_when_verdict_authority_missing(tmp_path: Path) -> None:
    manifest_path = _write_json(
        tmp_path / "manifest.json",
        {
            "sid": "sid-support-authority-missing",
            "bundles": [_support_bundle(eligible=True)],
        },
    )
    summary_path = _write_json(
        tmp_path / "summary.json",
        {
            "sid": "sid-support-authority-missing",
            "case_name": "cwe-89-basic",
            "manifest_path": str(manifest_path),
        },
    )

    payload = build_support_candidate(
        summary_path,
        matrix_report={"covered_cases": ["cwe-89-basic"], "failed_cases": [], "repeatability_failures": []},
        repeatability_report={"case": "cwe-89-basic", "passed": True},
    )

    assert payload["support_ready_bundle_count"] == 1
    assert payload["mechanically_healthy_bundle_count"] == 0
    assert payload["promotion_policy_ready_bundle_count"] == 1
    assert payload["by_support_status"] == {"mechanically_blocked": 1}
    assert payload["reviewable_bundle_count"] == 0
    assert payload["authority_gate"] == {
        "available": False,
        "summary_mode": None,
        "repeatability_consistent": None,
        "blockers": ["verdict_authority:missing"],
    }
    candidate = payload["candidates"][0]
    assert candidate["reviewable"] is False
    assert candidate["support_status"] == "mechanically_blocked"
    assert candidate["mechanical_blockers"] == ["verdict_authority:missing"]
    assert candidate["promotion_policy_blockers"] == []
    assert candidate["gates"]["mechanically_healthy"] is False
    assert candidate["gates"]["promotion_policy_ready"] is True
    assert candidate["gates"]["verdict_authority_ready"] is False
    assert "verdict_authority:missing" in candidate["blockers"]


def test_build_support_candidate_surfaces_matrix_unavailable_as_mechanical_blocker(tmp_path: Path) -> None:
    manifest_path = _write_json(
        tmp_path / "manifest.json",
        {
            "sid": "sid-support-matrix-unavailable",
            "bundles": [_support_bundle(eligible=True)],
        },
    )
    summary_path = _write_json(
        tmp_path / "summary.json",
        {
            "sid": "sid-support-matrix-unavailable",
            "case_name": "repeat-case",
            "manifest_path": str(manifest_path),
            "verdict_authority": {"mode": "single_bundle", "fields": {}},
        },
    )

    payload = build_support_candidate(
        summary_path,
        matrix_report={
            "schema_version": "matrix_report@0.1",
            "matrix_unavailable_reason": "case is not declared in case_matrix.json: repeat-case",
            "requested_case_name": "repeat-case",
            "covered_cases": [],
            "failed_cases": [],
            "repeatability_failures": [],
        },
        repeatability_report={
            "case": "repeat-case",
            "case_name": "repeat-case",
            "passed": True,
            "observed_verdict_authority_modes": ["single_bundle"],
            "verdict_authority_consistent": True,
            "measured_gate": {"ready": True, "blockers": []},
        },
    )

    assert payload["case_gates"]["matrix_available"] is False
    assert payload["case_gates"]["matrix_unavailable_reason"] == "case is not declared in case_matrix.json: repeat-case"
    candidate = payload["candidates"][0]
    assert candidate["support_status"] == "mechanically_blocked"
    assert candidate["mechanical_blockers"] == ["matrix_gate:unavailable"]
    assert candidate["promotion_policy_blockers"] == []
    assert candidate["gates"]["matrix_case_green"] is False
    assert candidate["gates"]["repeatability_passed"] is True
    assert candidate["gates"]["measured_gate_ready"] is True
    assert candidate["gates"]["mechanically_healthy"] is False
    assert candidate["gates"]["promotion_policy_ready"] is True


def test_write_support_candidate_persists_payload(tmp_path: Path) -> None:
    manifest_path = _write_json(tmp_path / "manifest.json", {"sid": "sid-write", "bundles": [_support_bundle(eligible=False)]})
    summary_path = _write_json(
        tmp_path / "summary.json",
        {
            "sid": "sid-write",
            "case_name": "cwe-89-basic",
            "manifest_path": str(manifest_path),
            "verdict_authority": {"mode": "single_bundle", "fields": {}},
        },
    )
    output_path = tmp_path / "support_candidate.json"

    payload = write_support_candidate(
        output_path,
        summary_path,
        matrix_report={"covered_cases": ["cwe-89-basic"], "failed_cases": [], "repeatability_failures": []},
        repeatability_report={"case": "cwe-89-basic", "passed": True},
    )

    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert persisted == payload
    assert payload["support_ready_bundle_count"] == 0
    assert payload["mechanically_healthy_bundle_count"] == 1
    assert payload["promotion_policy_ready_bundle_count"] == 0
    assert payload["by_support_status"] == {"mechanically_healthy_policy_blocked": 1}
    assert payload["reviewable_bundle_count"] == 0
    candidate = payload["candidates"][0]
    assert candidate["support_status"] == "mechanically_healthy_policy_blocked"
    assert candidate["mechanical_blockers"] == []
    assert candidate["promotion_policy_blockers"] == ["artifact_quality:medium"]
    assert candidate["gates"]["mechanically_healthy"] is True
    assert candidate["gates"]["promotion_policy_ready"] is False


def test_build_support_review_index_splits_reviewable_and_blocked_candidates(tmp_path: Path) -> None:
    reviewable_path = _write_json(
        tmp_path / "support_candidate.reviewable.json",
        {
            "schema_version": "support_candidate@0.1",
            "case_name": "cwe-89-basic",
            "sid": "sid-reviewable",
            "manifest_path": "/tmp/manifest-a.json",
            "support_ready_bundle_count": 1,
            "reviewable_bundle_count": 1,
            "measured_authority": {"summary_verdict_authority_mode": "single_bundle"},
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
                    "gates": {"verdict_authority_ready": True, "measured_gate_ready": True, "mechanically_healthy": True, "promotion_policy_ready": True},
                    "primitive_signature": {"selected_family": "sqli", "selected_stack_id": "python/flask"},
                    "runtime_contract": {"topology": "single_service"},
                    "oracle_contract": {"oracle_execution_parity": "high"},
                    "verdict_authority_mode": "single_bundle",
                    "verdict_authority_consistent": True,
                    "source_artifacts": {"summary_path": "/tmp/summary-a.json", "workspace": "/tmp/workspace-a"},
                }
            ],
        },
    )
    blocked_path = _write_json(
        tmp_path / "support_candidate.blocked.json",
        {
            "schema_version": "support_candidate@0.1",
            "case_name": "open-redirect-name-only",
            "sid": "sid-blocked",
            "manifest_path": "/tmp/manifest-b.json",
            "support_ready_bundle_count": 0,
            "reviewable_bundle_count": 0,
            "measured_authority": {"summary_verdict_authority_mode": "multi_bundle"},
            "candidates": [
                {
                    "slug": "name-open-redirect",
                    "vuln_id": "NAME-OPEN-REDIRECT",
                    "reviewable": False,
                    "support_promotion_eligible": False,
                    "support_status": "blocked_mixed",
                    "blockers": [
                        "artifact_quality:medium",
                        "oracle_execution_parity:missing",
                        "verdict_authority:inconsistent",
                        "measured_gate:oracle_execution_parity_not_high",
                    ],
                    "mechanical_blockers": [
                        "verdict_authority:inconsistent",
                        "measured_gate:oracle_execution_parity_not_high",
                    ],
                    "promotion_policy_blockers": [
                        "artifact_quality:medium",
                        "oracle_execution_parity:missing",
                    ],
                    "gates": {
                        "verdict_authority_ready": False,
                        "measured_gate_ready": False,
                        "mechanically_healthy": False,
                        "promotion_policy_ready": False,
                    },
                    "primitive_signature": {"selected_family": "open_redirect", "selected_stack_id": "python/flask"},
                    "runtime_contract": {"topology": "single_service"},
                    "oracle_contract": {"oracle_execution_parity": "missing"},
                    "verdict_authority_mode": "multi_bundle",
                    "verdict_authority_consistent": False,
                    "source_artifacts": {"summary_path": "/tmp/summary-b.json", "workspace": "/tmp/workspace-b"},
                }
            ],
        },
    )

    payload = build_support_review_index([reviewable_path, blocked_path])

    assert payload["schema_version"] == "support_review_index@0.1"
    assert payload["support_candidate_file_count"] == 2
    assert payload["case_count"] == 2
    assert payload["support_ready_bundle_count"] == 1
    assert payload["reviewable_bundle_count"] == 1
    assert payload["authority_ready_bundle_count"] == 1
    assert payload["authority_blocked_bundle_count"] == 1
    assert payload["measured_gate_ready_bundle_count"] == 1
    assert payload["measured_gate_blocked_bundle_count"] == 1
    assert payload["mechanically_healthy_bundle_count"] == 1
    assert payload["mechanically_blocked_bundle_count"] == 1
    assert payload["promotion_policy_ready_bundle_count"] == 1
    assert payload["promotion_policy_blocked_bundle_count"] == 1
    assert payload["by_case_status"] == {"all_blocked": 1, "all_reviewable": 1}
    assert payload["all_reviewable_cases"] == ["cwe-89-basic"]
    assert payload["mixed_cases"] == []
    assert payload["all_blocked_cases"] == ["open-redirect-name-only"]
    assert payload["by_support_status"] == {"blocked_mixed": 1, "reviewable": 1}
    assert payload["reviewable_cases"] == ["cwe-89-basic"]
    assert payload["blocked_cases"] == ["open-redirect-name-only"]
    assert payload["by_blocker"] == {
        "artifact_quality:medium": 1,
        "measured_gate:oracle_execution_parity_not_high": 1,
        "oracle_execution_parity:missing": 1,
        "verdict_authority:inconsistent": 1,
    }
    assert payload["by_authority_blocker"] == {"verdict_authority:inconsistent": 1}
    assert payload["by_measured_gate_blocker"] == {"measured_gate:oracle_execution_parity_not_high": 1}
    assert payload["by_mechanical_blocker"] == {
        "verdict_authority:inconsistent": 1,
        "measured_gate:oracle_execution_parity_not_high": 1,
    }
    assert payload["by_promotion_policy_blocker"] == {
        "artifact_quality:medium": 1,
        "oracle_execution_parity:missing": 1,
    }
    assert payload["by_family"] == {"open_redirect": 1, "sqli": 1}
    assert payload["by_topology"] == {"single_service": 2}
    assert payload["by_verdict_authority_mode"] == {"single_bundle": 1, "multi_bundle": 1}
    assert payload["review_queue"][0]["slug"] == "cwe-89"
    assert payload["review_queue"][0]["support_status"] == "reviewable"
    assert payload["review_queue"][0]["verdict_authority_mode"] == "single_bundle"
    assert payload["review_queue"][0]["verdict_authority_ready"] is True
    assert payload["review_queue"][0]["measured_gate_ready"] is True
    assert payload["review_queue"][0]["mechanically_healthy"] is True
    assert payload["review_queue"][0]["promotion_policy_ready"] is True
    assert payload["blocked_queue"][0]["slug"] == "name-open-redirect"
    assert payload["blocked_queue"][0]["support_status"] == "blocked_mixed"
    assert payload["blocked_queue"][0]["verdict_authority_mode"] == "multi_bundle"
    assert payload["blocked_queue"][0]["verdict_authority_ready"] is False
    assert payload["blocked_queue"][0]["measured_gate_ready"] is False
    assert payload["blocked_queue"][0]["mechanically_healthy"] is False
    assert payload["blocked_queue"][0]["promotion_policy_ready"] is False
    assert payload["case_statuses"] == [
        {
            "case_name": "cwe-89-basic",
            "case_status": "all_reviewable",
            "bundle_count": 1,
            "reviewable_bundle_count": 1,
            "blocked_bundle_count": 0,
            "mechanically_healthy_bundle_count": 1,
            "mechanically_blocked_bundle_count": 0,
            "promotion_policy_ready_bundle_count": 1,
            "promotion_policy_blocked_bundle_count": 0,
            "by_support_status": {"reviewable": 1},
            "by_mechanical_blocker": {},
            "by_promotion_policy_blocker": {},
        },
        {
            "case_name": "open-redirect-name-only",
            "case_status": "all_blocked",
            "bundle_count": 1,
            "reviewable_bundle_count": 0,
            "blocked_bundle_count": 1,
            "mechanically_healthy_bundle_count": 0,
            "mechanically_blocked_bundle_count": 1,
            "promotion_policy_ready_bundle_count": 0,
            "promotion_policy_blocked_bundle_count": 1,
            "by_support_status": {"blocked_mixed": 1},
            "by_mechanical_blocker": {
                "verdict_authority:inconsistent": 1,
                "measured_gate:oracle_execution_parity_not_high": 1,
            },
            "by_promotion_policy_blocker": {
                "artifact_quality:medium": 1,
                "oracle_execution_parity:missing": 1,
            },
        },
    ]


def test_write_support_review_index_persists_payload(tmp_path: Path) -> None:
    candidate_path = _write_json(
        tmp_path / "support_candidate.json",
        {
            "schema_version": "support_candidate@0.1",
            "case_name": "cwe-89-basic",
            "sid": "sid-review-index",
            "manifest_path": "/tmp/manifest.json",
            "support_ready_bundle_count": 1,
            "reviewable_bundle_count": 0,
            "candidates": [
                {
                    "slug": "cwe-89",
                    "vuln_id": "CWE-89",
                    "reviewable": False,
                    "support_promotion_eligible": True,
                    "support_status": "mechanically_blocked",
                    "blockers": ["repeatability_gate:failed"],
                    "mechanical_blockers": ["repeatability_gate:failed"],
                    "promotion_policy_blockers": [],
                    "gates": {
                        "verdict_authority_ready": True,
                        "measured_gate_ready": False,
                        "mechanically_healthy": False,
                        "promotion_policy_ready": True,
                    },
                    "primitive_signature": {"selected_family": "sqli"},
                    "runtime_contract": {"topology": "single_service"},
                    "oracle_contract": {"oracle_execution_parity": "high"},
                    "source_artifacts": {"summary_path": "/tmp/summary.json", "workspace": "/tmp/workspace"},
                }
            ],
        },
    )
    output_path = tmp_path / "support_review_index.json"

    payload = write_support_review_index(output_path, [candidate_path])

    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert persisted == payload
    assert payload["reviewable_bundle_count"] == 0
    assert payload["authority_ready_bundle_count"] == 1
    assert payload["authority_blocked_bundle_count"] == 0
    assert payload["measured_gate_ready_bundle_count"] == 0
    assert payload["measured_gate_blocked_bundle_count"] == 1
    assert payload["mechanically_healthy_bundle_count"] == 0
    assert payload["mechanically_blocked_bundle_count"] == 1
    assert payload["promotion_policy_ready_bundle_count"] == 1
    assert payload["promotion_policy_blocked_bundle_count"] == 0
    assert payload["by_case_status"] == {"all_blocked": 1}
    assert payload["all_reviewable_cases"] == []
    assert payload["mixed_cases"] == []
    assert payload["all_blocked_cases"] == ["cwe-89-basic"]
    assert payload["by_support_status"] == {"mechanically_blocked": 1}
    assert payload["by_measured_gate_blocker"] == {}
    assert payload["by_mechanical_blocker"] == {"repeatability_gate:failed": 1}
    assert payload["by_promotion_policy_blocker"] == {}
    assert payload["blocked_cases"] == ["cwe-89-basic"]


def test_collect_support_candidate_paths_accepts_files_and_directories(tmp_path: Path) -> None:
    root = tmp_path / "repeat-runs"
    run_a = root / "run-a"
    run_b = root / "nested" / "run-b"
    run_a.mkdir(parents=True, exist_ok=True)
    run_b.mkdir(parents=True, exist_ok=True)
    candidate_a = _write_json(run_a / "support_candidate.json", {"schema_version": "support_candidate@0.1"})
    candidate_b = _write_json(run_b / "support_candidate.json", {"schema_version": "support_candidate@0.1"})

    collected = _collect_support_candidate_paths([candidate_a, root])

    assert collected == [candidate_a.resolve(), candidate_b.resolve()]


def test_build_support_registry_update_applies_accept_reject_and_pending(tmp_path: Path) -> None:
    review_index_path = _write_json(
        tmp_path / "support_review_index.json",
        {
            "schema_version": "support_review_index@0.1",
            "reviewable_bundle_count": 2,
            "authority_ready_bundle_count": 2,
            "authority_blocked_bundle_count": 0,
            "measured_gate_ready_bundle_count": 2,
            "measured_gate_blocked_bundle_count": 0,
            "mechanically_healthy_bundle_count": 2,
            "mechanically_blocked_bundle_count": 0,
            "promotion_policy_ready_bundle_count": 2,
            "promotion_policy_blocked_bundle_count": 0,
            "by_authority_blocker": {},
            "by_measured_gate_blocker": {},
            "by_mechanical_blocker": {},
            "by_promotion_policy_blocker": {},
            "by_support_status": {"reviewable": 2},
            "by_verdict_authority_mode": {"single_bundle": 1, "multi_bundle": 1},
            "review_queue": [
                {
                    "case_name": "cwe-89-basic",
                    "slug": "cwe-89",
                    "vuln_id": "CWE-89",
                    "selected_family": "sqli",
                    "selected_stack_id": "python/flask",
                    "topology": "single_service",
                    "oracle_execution_parity": "high",
                    "support_status": "reviewable",
                    "verdict_authority_mode": "single_bundle",
                    "verdict_authority_consistent": True,
                    "verdict_authority_ready": True,
                    "measured_gate_ready": True,
                    "mechanically_healthy": True,
                    "promotion_policy_ready": True,
                    "manifest_path": "/tmp/manifest-a.json",
                    "summary_path": "/tmp/summary-a.json",
                    "workspace": "/tmp/workspace-a",
                    "support_candidate_path": "/tmp/support-a.json",
                },
                {
                    "case_name": "template-injection-name-only",
                    "slug": "name-template-injection",
                    "vuln_id": "NAME-TEMPLATE-INJECTION",
                    "selected_family": "template_injection",
                    "selected_stack_id": "python/flask",
                    "topology": "single_service",
                    "oracle_execution_parity": "high",
                    "support_status": "reviewable",
                    "verdict_authority_mode": "multi_bundle",
                    "verdict_authority_consistent": True,
                    "verdict_authority_ready": True,
                    "measured_gate_ready": True,
                    "mechanically_healthy": True,
                    "promotion_policy_ready": True,
                    "manifest_path": "/tmp/manifest-b.json",
                    "summary_path": "/tmp/summary-b.json",
                    "workspace": "/tmp/workspace-b",
                    "support_candidate_path": "/tmp/support-b.json",
                },
            ],
        },
    )
    decisions_path = _write_json(
        tmp_path / "support_review_decisions.json",
        {
            "schema_version": "support_review_decisions@0.1",
            "decisions": [
                {
                    "case_name": "cwe-89-basic",
                    "slug": "cwe-89",
                    "decision": "accept",
                    "rationale": "measured lane is stable",
                    "reviewer": "alice",
                },
                {
                    "case_name": "template-injection-name-only",
                    "slug": "name-template-injection",
                    "decision": "reject",
                    "rationale": "needs richer oracle realism",
                    "reviewer": "bob",
                },
            ],
        },
    )

    payload = build_support_registry_update(review_index_path, decisions_path)

    assert payload["schema_version"] == "support_registry_update@0.1"
    assert payload["authority_ready_bundle_count"] == 2
    assert payload["authority_blocked_bundle_count"] == 0
    assert payload["measured_gate_ready_bundle_count"] == 2
    assert payload["measured_gate_blocked_bundle_count"] == 0
    assert payload["mechanically_healthy_bundle_count"] == 2
    assert payload["mechanically_blocked_bundle_count"] == 0
    assert payload["promotion_policy_ready_bundle_count"] == 2
    assert payload["promotion_policy_blocked_bundle_count"] == 0
    assert payload["reviewable_case_count"] == 2
    assert payload["blocked_case_count"] == 0
    assert payload["reviewable_cases"] == ["cwe-89-basic", "template-injection-name-only"]
    assert payload["blocked_cases"] == []
    assert payload["by_case_status"] == {"all_reviewable": 2}
    assert payload["all_reviewable_cases"] == ["cwe-89-basic", "template-injection-name-only"]
    assert payload["mixed_cases"] == []
    assert payload["all_blocked_cases"] == []
    assert payload["by_support_status"] == {"reviewable": 2}
    assert payload["by_authority_blocker"] == {}
    assert payload["by_measured_gate_blocker"] == {}
    assert payload["by_mechanical_blocker"] == {}
    assert payload["by_promotion_policy_blocker"] == {}
    assert payload["by_verdict_authority_mode"] == {"single_bundle": 1, "multi_bundle": 1}
    assert payload["accepted_count"] == 1
    assert payload["rejected_count"] == 1
    assert payload["pending_count"] == 0
    assert payload["accepted_by_verdict_authority_mode"] == {"single_bundle": 1}
    assert payload["rejected_by_verdict_authority_mode"] == {"multi_bundle": 1}
    assert payload["pending_by_verdict_authority_mode"] == {}
    assert payload["accepted_by_support_status"] == {"reviewable": 1}
    assert payload["rejected_by_support_status"] == {"reviewable": 1}
    assert payload["pending_by_support_status"] == {}
    assert payload["case_statuses"] == [
        {
            "case_name": "cwe-89-basic",
            "case_status": "all_reviewable",
            "bundle_count": 1,
            "reviewable_bundle_count": 1,
            "blocked_bundle_count": 0,
            "mechanically_healthy_bundle_count": 1,
            "mechanically_blocked_bundle_count": 0,
            "promotion_policy_ready_bundle_count": 1,
            "promotion_policy_blocked_bundle_count": 0,
            "by_support_status": {"reviewable": 1},
            "by_mechanical_blocker": {},
            "by_promotion_policy_blocker": {},
        },
        {
            "case_name": "template-injection-name-only",
            "case_status": "all_reviewable",
            "bundle_count": 1,
            "reviewable_bundle_count": 1,
            "blocked_bundle_count": 0,
            "mechanically_healthy_bundle_count": 1,
            "mechanically_blocked_bundle_count": 0,
            "promotion_policy_ready_bundle_count": 1,
            "promotion_policy_blocked_bundle_count": 0,
            "by_support_status": {"reviewable": 1},
            "by_mechanical_blocker": {},
            "by_promotion_policy_blocker": {},
        },
    ]
    assert payload["invalid_decision_count"] == 0
    assert payload["all_decisions_valid"] is True
    assert payload["accepted"][0]["case_name"] == "cwe-89-basic"
    assert payload["accepted"][0]["decision"] == "accept"
    assert payload["accepted"][0]["reviewer"] == "alice"
    assert payload["accepted"][0]["support_status"] == "reviewable"
    assert payload["accepted"][0]["verdict_authority_mode"] == "single_bundle"
    assert payload["accepted"][0]["verdict_authority_ready"] is True
    assert payload["accepted"][0]["measured_gate_ready"] is True
    assert payload["accepted"][0]["mechanically_healthy"] is True
    assert payload["accepted"][0]["promotion_policy_ready"] is True
    assert payload["rejected"][0]["slug"] == "name-template-injection"
    assert payload["rejected"][0]["decision"] == "reject"
    assert payload["rejected"][0]["support_status"] == "reviewable"
    assert payload["rejected"][0]["verdict_authority_mode"] == "multi_bundle"
    assert payload["rejected"][0]["verdict_authority_ready"] is True
    assert payload["rejected"][0]["measured_gate_ready"] is True
    assert payload["rejected"][0]["mechanically_healthy"] is True
    assert payload["rejected"][0]["promotion_policy_ready"] is True


def test_build_support_registry_update_flags_invalid_and_pending_entries(tmp_path: Path) -> None:
    review_index_path = _write_json(
        tmp_path / "support_review_index.json",
        {
            "schema_version": "support_review_index@0.1",
            "reviewable_bundle_count": 1,
            "authority_ready_bundle_count": 0,
            "authority_blocked_bundle_count": 1,
            "measured_gate_ready_bundle_count": 0,
            "measured_gate_blocked_bundle_count": 1,
            "mechanically_healthy_bundle_count": 0,
            "mechanically_blocked_bundle_count": 1,
            "promotion_policy_ready_bundle_count": 0,
            "promotion_policy_blocked_bundle_count": 1,
            "by_authority_blocker": {"verdict_authority:inconsistent": 1},
            "by_measured_gate_blocker": {"measured_gate:verdict_authority_inconsistent": 1},
            "by_mechanical_blocker": {
                "verdict_authority:inconsistent": 1,
                "measured_gate:verdict_authority_inconsistent": 1,
            },
            "by_promotion_policy_blocker": {"artifact_quality:medium": 1},
            "by_support_status": {"blocked_mixed": 1},
            "by_verdict_authority_mode": {"multi_bundle": 1},
            "review_queue": [
                {
                    "case_name": "cwe-89-basic",
                    "slug": "cwe-89",
                    "vuln_id": "CWE-89",
                    "selected_family": "sqli",
                    "selected_stack_id": "python/flask",
                    "topology": "single_service",
                    "oracle_execution_parity": "high",
                    "support_status": "blocked_mixed",
                    "verdict_authority_mode": "multi_bundle",
                    "verdict_authority_consistent": False,
                    "verdict_authority_ready": False,
                    "measured_gate_ready": False,
                    "mechanically_healthy": False,
                    "promotion_policy_ready": False,
                    "manifest_path": "/tmp/manifest-a.json",
                    "summary_path": "/tmp/summary-a.json",
                    "workspace": "/tmp/workspace-a",
                    "support_candidate_path": "/tmp/support-a.json",
                }
            ],
        },
    )
    decisions_path = _write_json(
        tmp_path / "support_review_decisions.json",
        {
            "schema_version": "support_review_decisions@0.1",
            "decisions": [
                {"case_name": "missing-case", "slug": "missing", "decision": "accept"},
                {"case_name": "cwe-89-basic", "slug": "cwe-89", "decision": "maybe"},
            ],
        },
    )

    payload = build_support_registry_update(review_index_path, decisions_path)

    assert payload["accepted_count"] == 0
    assert payload["rejected_count"] == 0
    assert payload["pending_count"] == 1
    assert payload["authority_ready_bundle_count"] == 0
    assert payload["authority_blocked_bundle_count"] == 1
    assert payload["measured_gate_ready_bundle_count"] == 0
    assert payload["measured_gate_blocked_bundle_count"] == 1
    assert payload["mechanically_healthy_bundle_count"] == 0
    assert payload["mechanically_blocked_bundle_count"] == 1
    assert payload["promotion_policy_ready_bundle_count"] == 0
    assert payload["promotion_policy_blocked_bundle_count"] == 1
    assert payload["reviewable_case_count"] == 0
    assert payload["blocked_case_count"] == 1
    assert payload["reviewable_cases"] == []
    assert payload["blocked_cases"] == ["cwe-89-basic"]
    assert payload["by_case_status"] == {"all_blocked": 1}
    assert payload["all_reviewable_cases"] == []
    assert payload["mixed_cases"] == []
    assert payload["all_blocked_cases"] == ["cwe-89-basic"]
    assert payload["by_support_status"] == {"blocked_mixed": 1}
    assert payload["by_authority_blocker"] == {"verdict_authority:inconsistent": 1}
    assert payload["by_measured_gate_blocker"] == {"measured_gate:verdict_authority_inconsistent": 1}
    assert payload["by_mechanical_blocker"] == {
        "verdict_authority:inconsistent": 1,
        "measured_gate:verdict_authority_inconsistent": 1,
    }
    assert payload["by_promotion_policy_blocker"] == {"artifact_quality:medium": 1}
    assert payload["by_verdict_authority_mode"] == {"multi_bundle": 1}
    assert payload["accepted_by_verdict_authority_mode"] == {}
    assert payload["rejected_by_verdict_authority_mode"] == {}
    assert payload["pending_by_verdict_authority_mode"] == {"multi_bundle": 1}
    assert payload["accepted_by_support_status"] == {}
    assert payload["rejected_by_support_status"] == {}
    assert payload["pending_by_support_status"] == {"blocked_mixed": 1}
    assert payload["case_statuses"] == [
        {
            "case_name": "cwe-89-basic",
            "case_status": "all_blocked",
            "bundle_count": 1,
            "reviewable_bundle_count": 0,
            "blocked_bundle_count": 1,
            "mechanically_healthy_bundle_count": 0,
            "mechanically_blocked_bundle_count": 1,
            "promotion_policy_ready_bundle_count": 0,
            "promotion_policy_blocked_bundle_count": 1,
            "by_support_status": {"blocked_mixed": 1},
            "by_mechanical_blocker": {},
            "by_promotion_policy_blocker": {},
        }
    ]
    assert payload["invalid_decision_count"] == 2
    assert payload["all_decisions_valid"] is False
    reasons = {entry["reason"] for entry in payload["invalid_decisions"]}
    assert reasons == {"not_in_review_queue", "unsupported_decision"}
    assert payload["pending_review"][0]["slug"] == "cwe-89"
    assert payload["pending_review"][0]["support_status"] == "blocked_mixed"
    assert payload["pending_review"][0]["verdict_authority_mode"] == "multi_bundle"
    assert payload["pending_review"][0]["verdict_authority_ready"] is False
    assert payload["pending_review"][0]["measured_gate_ready"] is False
    assert payload["pending_review"][0]["mechanically_healthy"] is False
    assert payload["pending_review"][0]["promotion_policy_ready"] is False


def test_write_support_registry_update_persists_payload(tmp_path: Path) -> None:
    review_index_path = _write_json(
        tmp_path / "support_review_index.json",
        {"schema_version": "support_review_index@0.1", "reviewable_bundle_count": 0, "review_queue": []},
    )
    decisions_path = _write_json(
        tmp_path / "support_review_decisions.json",
        {"schema_version": "support_review_decisions@0.1", "decisions": []},
    )
    output_path = tmp_path / "support_registry_update.json"

    payload = write_support_registry_update(output_path, review_index_path, decisions_path)

    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert persisted == payload
    assert payload["accepted_count"] == 0
    assert payload["pending_count"] == 0


def test_build_curated_support_registry_applies_accepts_and_logs_history(tmp_path: Path) -> None:
    registry_update_path = _write_json(
        tmp_path / "support_registry_update.json",
        {
            "schema_version": "support_registry_update@0.1",
            "review_index_path": "/tmp/support_review_index.json",
            "decision_source_path": "/tmp/support_review_decisions.json",
            "accepted_count": 1,
            "rejected_count": 1,
            "pending_count": 1,
            "invalid_decision_count": 0,
            "authority_ready_bundle_count": 1,
            "authority_blocked_bundle_count": 0,
            "measured_gate_ready_bundle_count": 1,
            "measured_gate_blocked_bundle_count": 0,
            "mechanically_healthy_bundle_count": 1,
            "mechanically_blocked_bundle_count": 0,
            "promotion_policy_ready_bundle_count": 1,
            "promotion_policy_blocked_bundle_count": 0,
            "by_authority_blocker": {},
            "by_measured_gate_blocker": {},
            "by_mechanical_blocker": {},
            "by_promotion_policy_blocker": {},
            "by_support_status": {"reviewable": 1},
            "accepted_by_verdict_authority_mode": {"single_bundle": 1},
            "rejected_by_verdict_authority_mode": {"multi_bundle": 1},
            "pending_by_verdict_authority_mode": {"single_bundle": 1},
            "accepted_by_support_status": {"reviewable": 1},
            "rejected_by_support_status": {"reviewable": 1},
            "pending_by_support_status": {"reviewable": 1},
            "accepted": [
                {
                    "case_name": "cwe-89-basic",
                    "slug": "cwe-89",
                    "vuln_id": "CWE-89",
                    "decision": "accept",
                    "rationale": "stable measured lane",
                    "reviewer": "alice",
                    "selected_family": "sqli",
                    "selected_stack_id": "python/flask",
                    "topology": "single_service",
                    "oracle_execution_parity": "high",
                    "support_status": "reviewable",
                    "verdict_authority_mode": "single_bundle",
                    "verdict_authority_consistent": True,
                    "verdict_authority_ready": True,
                    "measured_gate_ready": True,
                    "mechanically_healthy": True,
                    "promotion_policy_ready": True,
                    "support_candidate_path": "/tmp/support-a.json",
                    "manifest_path": "/tmp/manifest-a.json",
                    "summary_path": "/tmp/summary-a.json",
                    "workspace": "/tmp/workspace-a",
                }
            ],
            "rejected": [
                {
                    "case_name": "template-injection-name-only",
                    "slug": "name-template-injection",
                    "vuln_id": "NAME-TEMPLATE-INJECTION",
                    "decision": "reject",
                    "rationale": "still thin demo",
                    "reviewer": "bob",
                    "selected_family": "template_injection",
                    "selected_stack_id": "python/flask",
                    "topology": "single_service",
                    "oracle_execution_parity": "high",
                    "support_status": "reviewable",
                    "verdict_authority_mode": "multi_bundle",
                    "verdict_authority_consistent": True,
                    "verdict_authority_ready": True,
                    "measured_gate_ready": True,
                    "mechanically_healthy": True,
                    "promotion_policy_ready": True,
                    "support_candidate_path": "/tmp/support-b.json",
                    "manifest_path": "/tmp/manifest-b.json",
                    "summary_path": "/tmp/summary-b.json",
                    "workspace": "/tmp/workspace-b",
                }
            ],
            "pending_review": [
                {
                    "case_name": "csrf-name-only",
                    "slug": "name-csrf",
                }
            ],
        },
    )

    payload = build_curated_support_registry(registry_update_path)

    assert payload["schema_version"] == "curated_support_registry@0.1"
    assert payload["registry_item_count"] == 1
    assert payload["accepted_applied_count"] == 1
    assert payload["rejected_logged_count"] == 1
    assert payload["pending_count"] == 1
    assert payload["decision_history_count"] == 2
    assert payload["update_count"] == 1
    assert payload["by_selected_family"] == {"sqli": 1}
    assert payload["by_topology"] == {"single_service": 1}
    assert payload["by_verdict_authority_mode"] == {"single_bundle": 1}
    assert payload["by_review_status"] == {"accepted": 1}
    assert payload["by_support_status"] == {"reviewable": 1}
    assert payload["by_case_review_status"] == {"all_accepted": 1}
    assert payload["all_accepted_cases"] == ["cwe-89-basic"]
    assert payload["mixed_review_status_cases"] == []
    assert payload["all_rejected_cases"] == []
    assert payload["mechanically_healthy_item_count"] == 1
    assert payload["mechanically_blocked_item_count"] == 0
    assert payload["promotion_policy_ready_item_count"] == 1
    assert payload["promotion_policy_blocked_item_count"] == 0
    assert payload["items_with_source_artifacts_count"] == 1
    assert payload["by_decision"] == {"accept": 1, "reject": 1}
    assert payload["by_reviewer"] == {"alice": 1, "bob": 1}
    assert payload["last_update"]["review_index_path"] == "/tmp/support_review_index.json"
    assert payload["last_update"]["decision_source_path"] == "/tmp/support_review_decisions.json"
    assert payload["last_update"]["measured_gate_ready_bundle_count"] == 1
    assert payload["last_update"]["mechanically_healthy_bundle_count"] == 1
    assert payload["last_update"]["mechanically_blocked_bundle_count"] == 0
    assert payload["last_update"]["promotion_policy_ready_bundle_count"] == 1
    assert payload["last_update"]["promotion_policy_blocked_bundle_count"] == 0
    assert payload["last_update"]["all_reviewable_case_count"] == 0
    assert payload["last_update"]["mixed_case_count"] == 0
    assert payload["last_update"]["all_blocked_case_count"] == 0
    assert payload["last_update"]["by_mechanical_blocker"] == {}
    assert payload["last_update"]["by_promotion_policy_blocker"] == {}
    assert payload["last_update"]["by_support_status"] == {"reviewable": 1}
    assert payload["last_update"]["all_reviewable_cases"] == []
    assert payload["last_update"]["mixed_cases"] == []
    assert payload["last_update"]["all_blocked_cases"] == []
    assert payload["last_update"]["accepted_by_verdict_authority_mode"] == {"single_bundle": 1}
    assert payload["last_update"]["accepted_by_support_status"] == {"reviewable": 1}
    assert payload["last_update"]["rejected_by_support_status"] == {"reviewable": 1}
    assert payload["last_update"]["pending_by_support_status"] == {"reviewable": 1}
    assert payload["case_review_statuses"] == [
        {
            "case_name": "cwe-89-basic",
            "item_count": 1,
            "accepted_item_count": 1,
            "rejected_item_count": 0,
            "mechanically_healthy_item_count": 1,
            "mechanically_blocked_item_count": 0,
            "promotion_policy_ready_item_count": 1,
            "promotion_policy_blocked_item_count": 0,
            "by_review_status": {"accepted": 1},
            "by_support_status": {"reviewable": 1},
            "case_review_status": "all_accepted",
        }
    ]
    item = payload["items"][0]
    assert item["case_name"] == "cwe-89-basic"
    assert item["slug"] == "cwe-89"
    assert item["accepted_count"] == 1
    assert item["review_status"] == "accepted"
    assert item["support_status"] == "reviewable"
    assert item["mechanically_healthy"] is True
    assert item["promotion_policy_ready"] is True
    assert item["decision_history_count"] == 1
    assert item["verdict_authority_ready"] is True
    assert item["measured_gate_ready"] is True
    assert item["source_artifacts"] == {
        "support_candidate_path": "/tmp/support-a.json",
        "manifest_path": "/tmp/manifest-a.json",
        "summary_path": "/tmp/summary-a.json",
        "workspace": "/tmp/workspace-a",
        "review_index_path": "/tmp/support_review_index.json",
        "decision_source_path": "/tmp/support_review_decisions.json",
    }
    assert item["history"][0]["decision"] == "accept"
    assert item["last_decision"]["reviewer"] == "alice"
    assert payload["decision_history"][1]["decision"] == "reject"
    assert payload["update_history"][0]["accepted_count"] == 1


def test_build_curated_support_registry_upserts_existing_item_history(tmp_path: Path) -> None:
    existing_registry_path = _write_json(
        tmp_path / "curated_support_registry.json",
        {
            "schema_version": "curated_support_registry@0.1",
            "items": [
                {
                    "case_name": "cwe-89-basic",
                    "slug": "cwe-89",
                    "selected_family": "sqli",
                    "topology": "single_service",
                    "verdict_authority_mode": "single_bundle",
                    "accepted_count": 1,
                    "history": [{"decision": "accept", "reviewer": "alice"}],
                }
            ],
            "decision_history": [{"decision": "accept", "reviewer": "alice"}],
            "update_history": [{"accepted_count": 1, "rejected_count": 0}],
        },
    )
    registry_update_path = _write_json(
        tmp_path / "support_registry_update.json",
        {
            "schema_version": "support_registry_update@0.1",
            "accepted_count": 1,
            "rejected_count": 0,
            "pending_count": 0,
            "invalid_decision_count": 0,
            "accepted": [
                {
                    "case_name": "cwe-89-basic",
                    "slug": "cwe-89",
                    "vuln_id": "CWE-89",
                    "decision": "accept",
                    "reviewer": "bob",
                    "selected_family": "sqli",
                    "selected_stack_id": "python/flask",
                    "topology": "single_service",
                    "oracle_execution_parity": "high",
                    "support_status": "reviewable",
                    "verdict_authority_mode": "single_bundle",
                    "verdict_authority_consistent": True,
                    "verdict_authority_ready": True,
                    "measured_gate_ready": True,
                    "mechanically_healthy": True,
                    "promotion_policy_ready": True,
                }
            ],
            "rejected": [],
            "pending_review": [],
        },
    )

    payload = build_curated_support_registry(
        registry_update_path,
        existing_registry=existing_registry_path,
    )

    assert payload["registry_item_count"] == 1
    assert payload["accepted_applied_count"] == 1
    assert payload["items"][0]["accepted_count"] == 2
    assert payload["items"][0]["review_status"] == "accepted"
    assert payload["items"][0]["support_status"] == "reviewable"
    assert payload["items"][0]["mechanically_healthy"] is True
    assert payload["items"][0]["promotion_policy_ready"] is True
    assert payload["items"][0]["decision_history_count"] == 2
    assert len(payload["items"][0]["history"]) == 2
    assert payload["items"][0]["last_decision"]["reviewer"] == "bob"
    assert payload["decision_history_count"] == 2
    assert payload["update_count"] == 2
    assert payload["by_review_status"] == {"accepted": 1}
    assert payload["by_support_status"] == {"reviewable": 1}
    assert payload["by_case_review_status"] == {"all_accepted": 1}
    assert payload["all_accepted_cases"] == ["cwe-89-basic"]
    assert payload["mixed_review_status_cases"] == []
    assert payload["all_rejected_cases"] == []
    assert payload["mechanically_healthy_item_count"] == 1
    assert payload["mechanically_blocked_item_count"] == 0
    assert payload["promotion_policy_ready_item_count"] == 1
    assert payload["promotion_policy_blocked_item_count"] == 0
    assert payload["items_with_source_artifacts_count"] == 1
    assert payload["schema_upgraded_item_count"] == 1
    assert payload["schema_status"] == "legacy_mixed_present"
    assert payload["by_schema_upgrade_reason"] == {
        "decision_history_count_from_history": 1,
        "mechanically_healthy_from_review_status_default": 1,
        "promotion_policy_ready_from_review_status_default": 1,
        "review_status_from_last_decision": 1,
        "source_artifacts_backfilled": 1,
        "support_status_from_review_status_default": 1,
    }
    assert payload["by_decision"] == {"accept": 2}
    assert payload["by_reviewer"] == {"alice": 1, "bob": 1}


def test_build_curated_support_registry_rejects_merge_conflict(tmp_path: Path) -> None:
    existing_registry_path = _write_json(
        tmp_path / "curated_support_registry.json",
        {
            "schema_version": "curated_support_registry@0.1",
            "items": [
                {
                    "case_name": "cwe-89-basic",
                    "slug": "cwe-89",
                    "selected_family": "sqli",
                    "selected_stack_id": "python/flask",
                    "topology": "single_service",
                }
            ],
        },
    )
    registry_update_path = _write_json(
        tmp_path / "support_registry_update.conflict.json",
        {
            "schema_version": "support_registry_update@0.1",
            "invalid_decision_count": 0,
            "accepted": [
                {
                    "case_name": "cwe-89-basic",
                    "slug": "cwe-89",
                    "decision": "accept",
                    "selected_family": "template_injection",
                    "selected_stack_id": "python/flask",
                    "topology": "single_service",
                    "verdict_authority_ready": True,
                    "measured_gate_ready": True,
                }
            ],
            "rejected": [],
            "pending_review": [],
        },
    )

    try:
        build_curated_support_registry(
            registry_update_path,
            existing_registry=existing_registry_path,
        )
    except ValueError as exc:
        assert "merge conflict" in str(exc)
        assert "selected_family" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected merge conflict to fail")


def test_build_curated_support_registry_accept_preserves_prior_reject_count(tmp_path: Path) -> None:
    existing_registry_path = _write_json(
        tmp_path / "curated_support_registry.prior-reject.json",
        {
            "schema_version": "curated_support_registry@0.1",
            "items": [
                {
                    "case_name": "cwe-89-basic",
                    "slug": "cwe-89",
                    "selected_family": "sqli",
                    "selected_stack_id": "python/flask",
                    "topology": "single_service",
                    "accepted_count": 1,
                    "rejected_count": 1,
                    "support_status": "blocked_mixed",
                    "mechanically_healthy": False,
                    "promotion_policy_ready": False,
                    "source_artifacts": {
                        "support_candidate_path": "/tmp/support-old.json",
                        "manifest_path": "/tmp/manifest-old.json",
                        "summary_path": "/tmp/summary-old.json",
                        "workspace": "/tmp/workspace-old",
                        "review_index_path": "/tmp/review-index-old.json",
                        "decision_source_path": "/tmp/decisions-old.json",
                    },
                    "history": [
                        {"decision": "accept", "reviewer": "alice"},
                        {"decision": "reject", "reviewer": "bob"},
                    ],
                }
            ],
            "decision_history": [
                {"decision": "accept", "reviewer": "alice"},
                {"decision": "reject", "reviewer": "bob"},
            ],
            "update_history": [{"accepted_count": 1, "rejected_count": 1}],
        },
    )
    registry_update_path = _write_json(
        tmp_path / "support_registry_update.accept-after-reject.json",
        {
            "schema_version": "support_registry_update@0.1",
            "accepted_count": 1,
            "rejected_count": 0,
            "pending_count": 0,
            "invalid_decision_count": 0,
            "accepted": [
                {
                    "case_name": "cwe-89-basic",
                    "slug": "cwe-89",
                    "vuln_id": "CWE-89",
                    "decision": "accept",
                    "reviewer": "carol",
                    "selected_family": "sqli",
                    "selected_stack_id": "python/flask",
                    "topology": "single_service",
                    "oracle_execution_parity": "high",
                    "verdict_authority_mode": "single_bundle",
                    "verdict_authority_consistent": True,
                    "verdict_authority_ready": True,
                    "measured_gate_ready": True,
                }
            ],
            "rejected": [],
            "pending_review": [],
        },
    )

    payload = build_curated_support_registry(
        registry_update_path,
        existing_registry=existing_registry_path,
    )

    item = payload["items"][0]
    assert item["accepted_count"] == 2
    assert item["rejected_count"] == 1
    assert item["review_status"] == "accepted"
    assert item["support_status"] == "reviewable"
    assert item["mechanically_healthy"] is True
    assert item["promotion_policy_ready"] is True
    assert item["decision_history_count"] == 3
    assert len(item["history"]) == 3
    assert item["last_decision"]["reviewer"] == "carol"
    assert item["source_artifacts"] == {
        "support_candidate_path": "/tmp/support-old.json",
        "manifest_path": "/tmp/manifest-old.json",
        "summary_path": "/tmp/summary-old.json",
        "workspace": "/tmp/workspace-old",
        "review_index_path": "/tmp/review-index-old.json",
        "decision_source_path": "/tmp/decisions-old.json",
    }
    assert payload["by_decision"] == {"accept": 2, "reject": 1}


def test_build_curated_support_registry_normalizes_sparse_existing_item_from_history(tmp_path: Path) -> None:
    existing_registry_path = _write_json(
        tmp_path / "curated_support_registry.legacy-accept.json",
        {
            "schema_version": "curated_support_registry@0.1",
            "items": [
                {
                    "case_name": "cwe-89-basic",
                    "slug": "cwe-89",
                    "selected_family": "sqli",
                    "selected_stack_id": "python/flask",
                    "topology": "single_service",
                    "history": [
                        {
                            "decision": "accept",
                            "reviewer": "alice",
                            "support_candidate_path": "/tmp/support-legacy.json",
                            "manifest_path": "/tmp/manifest-legacy.json",
                            "summary_path": "/tmp/summary-legacy.json",
                            "workspace": "/tmp/workspace-legacy",
                        }
                    ],
                }
            ],
        },
    )
    registry_update_path = _write_json(
        tmp_path / "support_registry_update.legacy-noop.json",
        {
            "schema_version": "support_registry_update@0.1",
            "invalid_decision_count": 0,
            "accepted_count": 0,
            "rejected_count": 0,
            "pending_count": 0,
            "accepted": [],
            "rejected": [],
            "pending_review": [],
        },
    )

    payload = build_curated_support_registry(
        registry_update_path,
        existing_registry=existing_registry_path,
    )

    assert payload["registry_item_count"] == 1
    assert payload["schema_upgraded_item_count"] == 1
    assert payload["schema_status"] == "legacy_items_present"
    assert payload["by_review_status"] == {"accepted": 1}
    assert payload["by_support_status"] == {"reviewable": 1}
    assert payload["by_case_review_status"] == {"all_accepted": 1}
    assert payload["all_accepted_cases"] == ["cwe-89-basic"]
    assert payload["mixed_review_status_cases"] == []
    assert payload["all_rejected_cases"] == []
    assert payload["mechanically_healthy_item_count"] == 1
    assert payload["promotion_policy_ready_item_count"] == 1
    assert payload["items_with_source_artifacts_count"] == 1
    assert payload["by_schema_upgrade_reason"] == {
        "accepted_count_from_history": 1,
        "decision_history_count_from_history": 1,
        "mechanically_healthy_from_review_status_default": 1,
        "promotion_policy_ready_from_review_status_default": 1,
        "review_status_from_last_decision": 1,
        "source_artifacts_backfilled": 1,
        "support_status_from_review_status_default": 1,
    }
    assert payload["last_update"]["schema_upgraded_item_count"] == 1
    assert payload["last_update"]["by_schema_upgrade_reason"] == {
        "accepted_count_from_history": 1,
        "decision_history_count_from_history": 1,
        "mechanically_healthy_from_review_status_default": 1,
        "promotion_policy_ready_from_review_status_default": 1,
        "review_status_from_last_decision": 1,
        "source_artifacts_backfilled": 1,
        "support_status_from_review_status_default": 1,
    }
    item = payload["items"][0]
    assert item["accepted_count"] == 1
    assert item["rejected_count"] == 0
    assert item["review_status"] == "accepted"
    assert item["support_status"] == "reviewable"
    assert item["mechanically_healthy"] is True
    assert item["promotion_policy_ready"] is True
    assert item["decision_history_count"] == 1
    assert item["schema_status"] == "legacy_upgraded"
    assert item["schema_upgrade_applied"] is True
    assert item["schema_upgrade_reasons"] == [
        "accepted_count_from_history",
        "review_status_from_last_decision",
        "support_status_from_review_status_default",
        "mechanically_healthy_from_review_status_default",
        "promotion_policy_ready_from_review_status_default",
        "decision_history_count_from_history",
        "source_artifacts_backfilled",
    ]
    assert item["last_decision"]["decision"] == "accept"
    assert item["last_decision"]["reviewer"] == "alice"
    assert item["source_artifacts"] == {
        "support_candidate_path": "/tmp/support-legacy.json",
        "manifest_path": "/tmp/manifest-legacy.json",
        "summary_path": "/tmp/summary-legacy.json",
        "workspace": "/tmp/workspace-legacy",
        "review_index_path": None,
        "decision_source_path": None,
    }


def test_build_curated_support_registry_normalizes_sparse_existing_rejected_item_from_history(tmp_path: Path) -> None:
    existing_registry_path = _write_json(
        tmp_path / "curated_support_registry.legacy-reject.json",
        {
            "schema_version": "curated_support_registry@0.1",
            "items": [
                {
                    "case_name": "template-injection-name-only",
                    "slug": "name-template-injection",
                    "selected_family": "template_injection",
                    "selected_stack_id": "python/flask",
                    "topology": "single_service",
                    "history": [
                        {
                            "decision": "accept",
                            "reviewer": "alice",
                        },
                        {
                            "decision": "reject",
                            "reviewer": "bob",
                            "support_status": "blocked_mixed",
                            "mechanically_healthy": False,
                            "promotion_policy_ready": False,
                        },
                    ],
                }
            ],
        },
    )
    registry_update_path = _write_json(
        tmp_path / "support_registry_update.legacy-reject-noop.json",
        {
            "schema_version": "support_registry_update@0.1",
            "invalid_decision_count": 0,
            "accepted_count": 0,
            "rejected_count": 0,
            "pending_count": 0,
            "accepted": [],
            "rejected": [],
            "pending_review": [],
        },
    )

    payload = build_curated_support_registry(
        registry_update_path,
        existing_registry=existing_registry_path,
    )

    assert payload["registry_item_count"] == 1
    assert payload["schema_upgraded_item_count"] == 1
    assert payload["schema_status"] == "legacy_items_present"
    assert payload["by_schema_upgrade_reason"] == {
        "accepted_count_from_history": 1,
        "decision_history_count_from_history": 1,
        "mechanically_healthy_from_last_event": 1,
        "promotion_policy_ready_from_last_event": 1,
        "rejected_count_from_history": 1,
        "review_status_from_last_decision": 1,
        "source_artifacts_backfilled": 1,
        "support_status_from_last_event": 1,
    }
    assert payload["last_update"]["schema_upgraded_item_count"] == 1
    assert payload["last_update"]["by_schema_upgrade_reason"] == {
        "accepted_count_from_history": 1,
        "decision_history_count_from_history": 1,
        "mechanically_healthy_from_last_event": 1,
        "promotion_policy_ready_from_last_event": 1,
        "rejected_count_from_history": 1,
        "review_status_from_last_decision": 1,
        "source_artifacts_backfilled": 1,
        "support_status_from_last_event": 1,
    }
    assert payload["by_review_status"] == {"rejected": 1}
    assert payload["by_support_status"] == {"blocked_mixed": 1}
    assert payload["by_case_review_status"] == {"all_rejected": 1}
    assert payload["all_accepted_cases"] == []
    assert payload["mixed_review_status_cases"] == []
    assert payload["all_rejected_cases"] == ["template-injection-name-only"]
    assert payload["mechanically_blocked_item_count"] == 1
    assert payload["promotion_policy_blocked_item_count"] == 1
    item = payload["items"][0]
    assert item["accepted_count"] == 1
    assert item["rejected_count"] == 1
    assert item["review_status"] == "rejected"
    assert item["support_status"] == "blocked_mixed"
    assert item["mechanically_healthy"] is False
    assert item["promotion_policy_ready"] is False
    assert item["decision_history_count"] == 2
    assert item["schema_status"] == "legacy_upgraded"
    assert item["schema_upgrade_applied"] is True
    assert item["schema_upgrade_reasons"] == [
        "accepted_count_from_history",
        "rejected_count_from_history",
        "review_status_from_last_decision",
        "support_status_from_last_event",
        "mechanically_healthy_from_last_event",
        "promotion_policy_ready_from_last_event",
        "decision_history_count_from_history",
        "source_artifacts_backfilled",
    ]
    assert item["last_decision"]["decision"] == "reject"
    assert item["last_decision"]["reviewer"] == "bob"


def test_build_curated_support_registry_normalizes_sparse_existing_update_history(tmp_path: Path) -> None:
    existing_registry_path = _write_json(
        tmp_path / "curated_support_registry.legacy-update-history.json",
        {
            "schema_version": "curated_support_registry@0.1",
            "items": [],
            "update_history": [
                {
                    "accepted_count": 1,
                }
            ],
        },
    )
    registry_update_path = _write_json(
        tmp_path / "support_registry_update.noop-current.json",
        {
            "schema_version": "support_registry_update@0.1",
            "invalid_decision_count": 0,
            "accepted_count": 0,
            "rejected_count": 0,
            "pending_count": 0,
            "accepted": [],
            "rejected": [],
            "pending_review": [],
        },
    )

    payload = build_curated_support_registry(
        registry_update_path,
        existing_registry=existing_registry_path,
    )

    assert payload["registry_item_count"] == 0
    assert payload["schema_upgraded_item_count"] == 0
    assert payload["schema_upgraded_update_count"] == 1
    assert payload["schema_status"] == "legacy_updates_present"
    assert payload["by_update_schema_upgrade_reason"]["rejected_count_defaulted"] == 1
    assert payload["by_update_schema_upgrade_reason"]["by_support_status_defaulted"] == 1
    assert payload["by_update_schema_upgrade_reason"]["schema_upgraded_item_count_defaulted"] == 1
    assert len(payload["update_history"]) == 2
    normalized_entry = payload["update_history"][0]
    assert normalized_entry["schema_status"] == "legacy_upgraded"
    assert normalized_entry["schema_upgrade_applied"] is True
    assert "rejected_count_defaulted" in normalized_entry["schema_upgrade_reasons"]
    assert "by_support_status_defaulted" in normalized_entry["schema_upgrade_reasons"]
    assert normalized_entry["accepted_count"] == 1
    assert normalized_entry["rejected_count"] == 0
    assert normalized_entry["by_support_status"] == {}
    assert normalized_entry["schema_upgraded_item_count"] == 0
    assert normalized_entry["by_schema_upgrade_reason"] == {}
    assert payload["last_update"]["schema_upgraded_item_count"] == 0
    assert payload["last_update"]["by_schema_upgrade_reason"] == {}


def test_build_curated_support_registry_normalizes_sparse_existing_decision_history(tmp_path: Path) -> None:
    existing_registry_path = _write_json(
        tmp_path / "curated_support_registry.legacy-decision-history.json",
        {
            "schema_version": "curated_support_registry@0.1",
            "items": [],
            "decision_history": [
                {
                    "decision": "accept",
                    "reviewer": "alice",
                }
            ],
        },
    )
    registry_update_path = _write_json(
        tmp_path / "support_registry_update.decision-history-noop.json",
        {
            "schema_version": "support_registry_update@0.1",
            "invalid_decision_count": 0,
            "accepted_count": 0,
            "rejected_count": 0,
            "pending_count": 0,
            "accepted": [],
            "rejected": [],
            "pending_review": [],
        },
    )

    payload = build_curated_support_registry(
        registry_update_path,
        existing_registry=existing_registry_path,
    )

    assert payload["registry_item_count"] == 0
    assert payload["decision_history_count"] == 1
    assert payload["schema_upgraded_decision_event_count"] == 1
    assert payload["schema_status"] == "legacy_decisions_present"
    assert payload["by_decision_schema_upgrade_reason"] == {
        "oracle_execution_parity_defaulted": 1,
        "support_status_from_decision_default": 1,
        "mechanically_healthy_from_decision_default": 1,
        "promotion_policy_ready_from_decision_default": 1,
    }
    event = payload["decision_history"][0]
    assert event["decision"] == "accept"
    assert event["reviewer"] == "alice"
    assert event["oracle_execution_parity"] == "missing"
    assert event["support_status"] == "reviewable"
    assert event["mechanically_healthy"] is True
    assert event["promotion_policy_ready"] is True
    assert event["schema_status"] == "legacy_upgraded"
    assert event["schema_upgrade_applied"] is True
    assert event["schema_upgrade_reasons"] == [
        "oracle_execution_parity_defaulted",
        "support_status_from_decision_default",
        "mechanically_healthy_from_decision_default",
        "promotion_policy_ready_from_decision_default",
    ]
    assert payload["last_update"]["schema_upgraded_decision_event_count"] == 1
    assert payload["last_update"]["schema_status"] == "legacy_decisions_present"
    assert payload["last_update"]["registry_schema_status"] == "legacy_decisions_present"
    assert payload["last_update"]["by_decision_schema_upgrade_reason"] == {
        "oracle_execution_parity_defaulted": 1,
        "support_status_from_decision_default": 1,
        "mechanically_healthy_from_decision_default": 1,
        "promotion_policy_ready_from_decision_default": 1,
    }


def test_build_curated_support_registry_updates_existing_item_with_reject_history(tmp_path: Path) -> None:
    existing_registry_path = _write_json(
        tmp_path / "curated_support_registry.reject-history.json",
        {
            "schema_version": "curated_support_registry@0.1",
            "items": [
                {
                    "case_name": "template-injection-name-only",
                    "slug": "name-template-injection",
                    "selected_family": "template_injection",
                    "selected_stack_id": "python/flask",
                    "topology": "single_service",
                    "accepted_count": 1,
                    "history": [{"decision": "accept", "reviewer": "alice"}],
                }
            ],
            "decision_history": [{"decision": "accept", "reviewer": "alice"}],
        },
    )
    registry_update_path = _write_json(
        tmp_path / "support_registry_update.reject-existing.json",
        {
            "schema_version": "support_registry_update@0.1",
            "accepted_count": 0,
            "rejected_count": 1,
            "pending_count": 0,
            "invalid_decision_count": 0,
            "mechanically_healthy_bundle_count": 0,
            "mechanically_blocked_bundle_count": 1,
            "promotion_policy_ready_bundle_count": 0,
            "promotion_policy_blocked_bundle_count": 1,
            "by_mechanical_blocker": {
                "verdict_authority:inconsistent": 1,
                "measured_gate:verdict_authority_inconsistent": 1,
            },
            "by_promotion_policy_blocker": {"artifact_quality:medium": 1},
            "by_support_status": {"blocked_mixed": 1},
            "accepted_by_support_status": {},
            "rejected_by_support_status": {"blocked_mixed": 1},
            "pending_by_support_status": {},
            "accepted": [],
            "rejected": [
                {
                    "case_name": "template-injection-name-only",
                    "slug": "name-template-injection",
                    "vuln_id": "NAME-TEMPLATE-INJECTION",
                    "decision": "reject",
                    "reviewer": "bob",
                    "selected_family": "template_injection",
                    "selected_stack_id": "python/flask",
                    "topology": "single_service",
                    "oracle_execution_parity": "high",
                    "support_status": "blocked_mixed",
                    "verdict_authority_mode": "multi_bundle",
                    "verdict_authority_consistent": True,
                    "verdict_authority_ready": True,
                    "measured_gate_ready": True,
                    "mechanically_healthy": False,
                    "promotion_policy_ready": False,
                }
            ],
            "pending_review": [],
        },
    )

    payload = build_curated_support_registry(
        registry_update_path,
        existing_registry=existing_registry_path,
    )

    assert payload["registry_item_count"] == 1
    assert payload["accepted_applied_count"] == 0
    assert payload["rejected_logged_count"] == 1
    assert payload["decision_history_count"] == 2
    assert payload["by_review_status"] == {"rejected": 1}
    assert payload["by_support_status"] == {"blocked_mixed": 1}
    assert payload["by_case_review_status"] == {"all_rejected": 1}
    assert payload["all_accepted_cases"] == []
    assert payload["mixed_review_status_cases"] == []
    assert payload["all_rejected_cases"] == ["template-injection-name-only"]
    assert payload["mechanically_healthy_item_count"] == 0
    assert payload["mechanically_blocked_item_count"] == 1
    assert payload["promotion_policy_ready_item_count"] == 0
    assert payload["promotion_policy_blocked_item_count"] == 1
    assert payload["items_with_source_artifacts_count"] == 1
    assert payload["by_decision"] == {"accept": 1, "reject": 1}
    assert payload["by_reviewer"] == {"alice": 1, "bob": 1}
    assert payload["last_update"]["mechanically_healthy_bundle_count"] == 0
    assert payload["last_update"]["mechanically_blocked_bundle_count"] == 1
    assert payload["last_update"]["promotion_policy_ready_bundle_count"] == 0
    assert payload["last_update"]["promotion_policy_blocked_bundle_count"] == 1
    assert payload["last_update"]["all_reviewable_case_count"] == 0
    assert payload["last_update"]["mixed_case_count"] == 0
    assert payload["last_update"]["all_blocked_case_count"] == 0
    assert payload["last_update"]["by_mechanical_blocker"] == {
        "verdict_authority:inconsistent": 1,
        "measured_gate:verdict_authority_inconsistent": 1,
    }
    assert payload["last_update"]["by_promotion_policy_blocker"] == {"artifact_quality:medium": 1}
    assert payload["last_update"]["by_support_status"] == {"blocked_mixed": 1}
    assert payload["last_update"]["all_reviewable_cases"] == []
    assert payload["last_update"]["mixed_cases"] == []
    assert payload["last_update"]["all_blocked_cases"] == []
    assert payload["last_update"]["accepted_by_support_status"] == {}
    assert payload["last_update"]["rejected_by_support_status"] == {"blocked_mixed": 1}
    assert payload["last_update"]["pending_by_support_status"] == {}
    item = payload["items"][0]
    assert item["case_name"] == "template-injection-name-only"
    assert item["slug"] == "name-template-injection"
    assert item["accepted_count"] == 1
    assert item["rejected_count"] == 1
    assert item["review_status"] == "rejected"
    assert item["support_status"] == "blocked_mixed"
    assert item["mechanically_healthy"] is False
    assert item["promotion_policy_ready"] is False
    assert item["decision_history_count"] == 2
    assert item["source_artifacts"] == {
        "support_candidate_path": None,
        "manifest_path": None,
        "summary_path": None,
        "workspace": None,
        "review_index_path": None,
        "decision_source_path": None,
    }
    assert len(item["history"]) == 2
    assert item["last_decision"]["decision"] == "reject"
    assert item["last_decision"]["reviewer"] == "bob"


def test_build_curated_support_registry_rejects_invalid_or_gate_unready_update(tmp_path: Path) -> None:
    invalid_update_path = _write_json(
        tmp_path / "support_registry_update.invalid.json",
        {
            "schema_version": "support_registry_update@0.1",
            "invalid_decision_count": 1,
            "accepted": [],
            "rejected": [],
            "pending_review": [],
        },
    )
    gate_unready_update_path = _write_json(
        tmp_path / "support_registry_update.unready.json",
        {
            "schema_version": "support_registry_update@0.1",
            "invalid_decision_count": 0,
            "accepted": [
                {
                    "case_name": "cwe-89-basic",
                    "slug": "cwe-89",
                    "decision": "accept",
                    "verdict_authority_ready": True,
                    "measured_gate_ready": False,
                }
            ],
            "rejected": [],
            "pending_review": [],
        },
    )

    try:
        build_curated_support_registry(invalid_update_path)
    except ValueError as exc:
        assert "invalid decisions" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected invalid update to fail")

    try:
        build_curated_support_registry(gate_unready_update_path)
    except ValueError as exc:
        assert "measured-gate ready" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected gate-unready accept to fail")


def test_write_curated_support_registry_persists_payload(tmp_path: Path) -> None:
    registry_update_path = _write_json(
        tmp_path / "support_registry_update.json",
        {
            "schema_version": "support_registry_update@0.1",
            "invalid_decision_count": 0,
            "accepted_count": 0,
            "rejected_count": 0,
            "pending_count": 0,
            "accepted": [],
            "rejected": [],
            "pending_review": [],
        },
    )
    output_path = tmp_path / "curated_support_registry.json"

    payload = write_curated_support_registry(output_path, registry_update_path)

    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert persisted == payload
    assert payload["registry_item_count"] == 0
    assert payload["decision_history_count"] == 0
    assert payload["update_count"] == 1
    assert payload["schema_status"] == "normalized"
    assert payload["last_update"]["schema_status"] == "normalized"
    assert payload["by_review_status"] == {}
    assert payload["by_support_status"] == {}
    assert payload["by_case_review_status"] == {}
    assert payload["all_accepted_cases"] == []
    assert payload["mixed_review_status_cases"] == []
    assert payload["all_rejected_cases"] == []
    assert payload["mechanically_healthy_item_count"] == 0
    assert payload["mechanically_blocked_item_count"] == 0
    assert payload["promotion_policy_ready_item_count"] == 0
    assert payload["promotion_policy_blocked_item_count"] == 0
    assert payload["items_with_source_artifacts_count"] == 0


def test_write_curated_support_registry_preserves_legacy_decision_schema_status_in_output(tmp_path: Path) -> None:
    existing_registry_path = _write_json(
        tmp_path / "curated_support_registry.legacy-decision-history.json",
        {
            "schema_version": "curated_support_registry@0.1",
            "items": [],
            "decision_history": [
                {
                    "decision": "accept",
                    "reviewer": "alice",
                }
            ],
        },
    )
    registry_update_path = _write_json(
        tmp_path / "support_registry_update.decision-history-noop.json",
        {
            "schema_version": "support_registry_update@0.1",
            "invalid_decision_count": 0,
            "accepted_count": 0,
            "rejected_count": 0,
            "pending_count": 0,
            "accepted": [],
            "rejected": [],
            "pending_review": [],
        },
    )
    output_path = tmp_path / "curated_support_registry.out.json"

    payload = write_curated_support_registry(
        output_path,
        registry_update_path,
        existing_registry=existing_registry_path,
    )

    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert persisted == payload
    assert payload["schema_status"] == "legacy_decisions_present"
    assert payload["last_update"]["schema_status"] == "legacy_decisions_present"
    assert payload["last_update"]["registry_schema_status"] == "legacy_decisions_present"
