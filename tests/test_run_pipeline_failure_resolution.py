from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import orchestrator.run_pipeline as run_pipeline


def test_latest_generator_failure_falls_back_to_bundle_paths(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-failure-path"
    metadata_root = tmp_path / "metadata" / sid
    bundle_dir = metadata_root / "bundles" / "cwe-89"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": "2026-02-20T14:49:17Z",
        "guard_error_code": "guard_semantic_mismatch",
        "reason": "semantic mismatch",
        "failure_fingerprint": "fp-1",
    }
    (bundle_dir / "generator_failures.jsonl").write_text(
        json.dumps(entry, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(run_pipeline, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)

    latest = run_pipeline._latest_generator_failure(sid)
    assert latest is not None
    assert latest.get("guard_error_code") == "guard_semantic_mismatch"
    assert "bundles/cwe-89" in str(latest.get("_failure_path"))


def test_semantic_mismatch_refreshes_after_threshold(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-semantic-threshold"
    metadata_root = tmp_path / "metadata" / sid
    metadata_root.mkdir(parents=True, exist_ok=True)
    failure_path = metadata_root / "generator_failures.jsonl"
    lines = [
        {
            "timestamp": "2026-02-20T14:48:23Z",
            "guard_error_code": "guard_semantic_mismatch",
            "failure_fingerprint": "same-fp",
            "reason": "semantic mismatch A",
        },
        {
            "timestamp": "2026-02-20T14:49:17Z",
            "guard_error_code": "guard_semantic_mismatch",
            "failure_fingerprint": "same-fp",
            "reason": "semantic mismatch B",
        },
    ]
    failure_path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in lines) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(run_pipeline, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)
    plan = {"policy": {"guard": {"semantic_refresh_threshold": 2, "failure_fingerprint_window": 3}}}
    current_failure = dict(lines[-1])
    refresh, reason = run_pipeline._refresh_researcher_for_guard_failure(plan, sid, current_failure)
    assert refresh is True
    assert "semantic mismatch repeated" in reason


def test_schema_error_requires_repeat_before_researcher_refresh(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-schema-refresh"
    metadata_root = tmp_path / "metadata" / sid
    metadata_root.mkdir(parents=True, exist_ok=True)
    failure_path = metadata_root / "generator_failures.jsonl"
    first = {
        "timestamp": "2026-02-20T14:47:36Z",
        "guard_error_code": "guard_assertion_schema_error",
        "failure_fingerprint": "schema-fp",
        "reason": "dep_declared requires dep",
    }
    failure_path.write_text(json.dumps(first, ensure_ascii=False) + "\n", encoding="utf-8")
    monkeypatch.setattr(run_pipeline, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)
    plan = {"policy": {"guard": {"failure_fingerprint_window": 3}}}

    refresh_once, _ = run_pipeline._refresh_researcher_for_guard_failure(plan, sid, first)
    assert refresh_once is False

    second = {
        "timestamp": "2026-02-20T14:48:23Z",
        "guard_error_code": "guard_assertion_schema_error",
        "failure_fingerprint": "schema-fp",
        "reason": "any_dep_declared requires deps[]",
    }
    with failure_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(second, ensure_ascii=False) + "\n")
    refresh_twice, reason = run_pipeline._refresh_researcher_for_guard_failure(plan, sid, second)
    assert refresh_twice is True
    assert "schema mismatch repeated" in reason


def test_record_deferred_refresh_marks_loop_state(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-deferred-refresh"
    metadata_root = tmp_path / "metadata" / sid
    metadata_root.mkdir(parents=True, exist_ok=True)
    loop_state_path = metadata_root / "loop_state.json"
    loop_state = {
        "sid": sid,
        "max_loops": 3,
        "current_loop": 3,
        "history": [
            {
                "loop": 3,
                "stage": "GENERATOR",
                "success": False,
                "blocking": True,
                "reason": "guard semantic mismatch",
                "fix_hint": "retry",
                "timestamp": "2026-02-20T15:55:43Z",
                "metadata": {},
            }
        ],
        "last_result": "failure",
    }
    loop_state_path.write_text(json.dumps(loop_state, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(run_pipeline, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)

    run_pipeline._record_deferred_refresh(
        sid,
        reason="refresh intended but loop limit reached",
        planned_next_action={"retry_stage": "RESEARCH", "researcher_refresh": True, "rationale": "repeated mismatch"},
    )
    updated = json.loads(loop_state_path.read_text(encoding="utf-8"))
    metadata = updated["history"][-1]["metadata"]
    assert metadata["refresh_deferred_due_to_loop_limit"] is True
    assert metadata["planned_next_action"]["retry_stage"] == "RESEARCH"


def test_can_skip_researcher_for_known_static_without_required_evidence(monkeypatch) -> None:
    plan = {
        "requirement": {"researcher": {}},
        "policy": {"require_researcher_evidence": False},
        "run_matrix": {
            "vuln_bundles": [
                {"vuln_id": "CWE-89", "slug": "cwe-89", "workspace_subdir": "app"},
                {"vuln_id": "CWE-352", "slug": "cwe-352", "workspace_subdir": "app"},
            ]
        },
    }
    monkeypatch.setattr(run_pipeline, "load_static_rule", lambda vuln_id: {"cwe": vuln_id})

    assert run_pipeline._can_skip_researcher(plan, refresh_requested=False) is True


def test_cannot_skip_researcher_when_required_or_refresh_requested(monkeypatch) -> None:
    plan = {
        "requirement": {"researcher": {}},
        "policy": {"require_researcher_evidence": True},
        "run_matrix": {"vuln_bundles": [{"vuln_id": "CWE-9999", "slug": "cwe-9999", "workspace_subdir": "app"}]},
    }
    monkeypatch.setattr(run_pipeline, "load_static_rule", lambda vuln_id: {})

    assert run_pipeline._can_skip_researcher(plan, refresh_requested=False) is False
    assert run_pipeline._can_skip_researcher(
        {"requirement": {"researcher": {}}, "policy": {"require_researcher_evidence": False}, "run_matrix": plan["run_matrix"]},
        refresh_requested=True,
    ) is False


def test_write_perf_summary_records_retry_and_provider_health(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-perf"
    metadata_root = tmp_path / "metadata" / sid
    metadata_root.mkdir(parents=True, exist_ok=True)
    (metadata_root / "search_health.json").write_text(
        json.dumps(
            {
                "provider": "tavily",
                "configured": True,
                "degraded": False,
                "remote_result_count": 3,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (metadata_root / "resolved_contract.json").write_text(
        json.dumps(
            {
                "schema_version": "resolved_contract@1.0",
                "llm_stub_used": True,
                "provenance": {"llm_stub_used": True},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(run_pipeline, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)
    events = [
        {"loop": 1, "stage": "GENERATOR", "duration_s": 3.0, "returncode": 1, "skipped": False, "note": ""},
        {"loop": 2, "stage": "GENERATOR", "duration_s": 2.0, "returncode": 0, "skipped": False, "note": ""},
        {"loop": 2, "stage": "PACK", "duration_s": 0.1, "returncode": 0, "skipped": False, "note": ""},
    ]

    run_pipeline._write_perf_summary(sid, events)

    payload = json.loads((metadata_root / "performance_summary.json").read_text(encoding="utf-8"))
    assert payload["retry_count"] == 1
    assert payload["provider_health_state"] == "llm_degraded"
    assert payload["llm_stub_used"] is True


def test_write_perf_summary_uses_failure_records_for_llm_health(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-perf-failure-record"
    metadata_root = tmp_path / "metadata" / sid
    metadata_root.mkdir(parents=True, exist_ok=True)
    (metadata_root / "search_health.json").write_text(
        json.dumps(
            {
                "provider": "tavily",
                "configured": True,
                "degraded": False,
                "remote_result_count": 9,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (metadata_root / "generator_failures.jsonl").write_text(
        json.dumps(
            {
                "timestamp": "2026-03-07T10:38:57Z",
                "guard_error_code": "guard_semantic_mismatch",
                "reason": "semantic mismatch",
                "failure_fingerprint": "fp-1",
                "llm_stub_used": True,
                "fallback_used": True,
                "family_override_applied": False,
                "llm_failure_class": "quota_exhausted",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(run_pipeline, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)
    events = [
        {"loop": 1, "stage": "GENERATOR", "duration_s": 3.0, "returncode": 1, "skipped": False, "note": ""},
        {"loop": 1, "stage": "PACK", "duration_s": 0.1, "returncode": 1, "skipped": False, "note": ""},
    ]

    run_pipeline._write_perf_summary(sid, events)

    payload = json.loads((metadata_root / "performance_summary.json").read_text(encoding="utf-8"))
    assert payload["provider_health_state"] == "llm_degraded"
    assert payload["llm_stub_used"] is True
    assert payload["llm_failure_class"] == "quota_exhausted"
