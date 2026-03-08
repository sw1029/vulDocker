from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import orchestrator.pack as pack_mod
import orchestrator.run_pipeline as run_pipeline


def test_prepare_fresh_run_state_clears_generated_outputs_but_keeps_plan_and_runtime_assets(
    tmp_path: Path,
    monkeypatch,
) -> None:
    sid = "sid-fresh-run"
    metadata_root = tmp_path / "metadata" / sid
    artifacts_root = tmp_path / "artifacts" / sid
    workspace_root = tmp_path / "workspaces" / sid
    metadata_root.mkdir(parents=True, exist_ok=True)
    artifacts_root.mkdir(parents=True, exist_ok=True)
    workspace_root.mkdir(parents=True, exist_ok=True)
    (metadata_root / "plan.json").write_text("{}", encoding="utf-8")
    (metadata_root / "runtime_rules").mkdir(parents=True, exist_ok=True)
    (metadata_root / "runtime_templates").mkdir(parents=True, exist_ok=True)
    (metadata_root / "manifest.json").write_text("{}", encoding="utf-8")
    (metadata_root / "loop_state.json").write_text("{}", encoding="utf-8")
    (metadata_root / "resolved_contract.json").write_text("{}", encoding="utf-8")
    (artifacts_root / "reports").mkdir(parents=True, exist_ok=True)
    (artifacts_root / "reports" / "evals.json").write_text("{}", encoding="utf-8")
    (workspace_root / "app").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(run_pipeline, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)
    monkeypatch.setattr(run_pipeline, "get_artifacts_dir", lambda incoming_sid: tmp_path / "artifacts" / incoming_sid)
    monkeypatch.setattr(run_pipeline, "get_workspace_dir", lambda incoming_sid: tmp_path / "workspaces" / incoming_sid)

    run_pipeline._prepare_fresh_run_state(sid)

    assert (metadata_root / "plan.json").exists()
    assert (metadata_root / "runtime_rules").exists()
    assert (metadata_root / "runtime_templates").exists()
    assert not (metadata_root / "manifest.json").exists()
    assert not (metadata_root / "loop_state.json").exists()
    assert not (metadata_root / "resolved_contract.json").exists()
    assert not (artifacts_root / "reports" / "evals.json").exists()
    assert not (workspace_root / "app").exists()


def test_refresh_manifest_after_pack_rewrites_existing_success_manifest(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-pack-refresh-success"
    metadata_root = tmp_path / "metadata" / sid
    metadata_root.mkdir(parents=True, exist_ok=True)
    (metadata_root / "manifest.json").write_text("{}", encoding="utf-8")
    calls: list[tuple[str, str]] = []

    def _fake_write_manifest(incoming_sid: str, plan: dict, *, filename: str = "manifest.json") -> Path:
        calls.append((incoming_sid, filename))
        return metadata_root / filename

    monkeypatch.setattr(run_pipeline, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)
    monkeypatch.setattr(pack_mod, "write_manifest", _fake_write_manifest)

    run_pipeline._refresh_manifest_after_pack(sid, {"sid": sid})

    assert calls == [(sid, "manifest.json")]


def test_refresh_manifest_after_pack_rewrites_existing_failure_manifest(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-pack-refresh-failure"
    metadata_root = tmp_path / "metadata" / sid
    metadata_root.mkdir(parents=True, exist_ok=True)
    (metadata_root / "failure_manifest.json").write_text("{}", encoding="utf-8")
    calls: list[tuple[str, str]] = []

    def _fake_write_manifest(incoming_sid: str, plan: dict, *, filename: str = "manifest.json") -> Path:
        calls.append((incoming_sid, filename))
        return metadata_root / filename

    monkeypatch.setattr(run_pipeline, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)
    monkeypatch.setattr(pack_mod, "write_manifest", _fake_write_manifest)

    run_pipeline._refresh_manifest_after_pack(sid, {"sid": sid})

    assert calls == [(sid, "failure_manifest.json")]


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


def test_terminal_research_failure_from_semantic_profile_marks_unsupported_name_bundle(tmp_path: Path) -> None:
    sid = "sid-terminal-profile"
    metadata_root = tmp_path / "metadata" / sid
    metadata_root.mkdir(parents=True, exist_ok=True)
    (metadata_root / "semantic_profile.json").write_text(
        json.dumps(
            {
                "schema_version": "semantic_profile@1.0",
                "sid": sid,
                "slug": "name-ldap-injection",
                "normalized_vuln_id": "NAME-LDAP-INJECTION",
                "family": "ldap_injection",
                "support_level": "unsupported",
                "compiler_supported": False,
                "compiler_reason": "semantic family unsupported for compiler-backed generation",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    plan = {
        "sid": sid,
        "paths": {
            "metadata": str(metadata_root),
            "artifacts": str(tmp_path / "artifacts" / sid),
            "workspace": str(tmp_path / "workspaces" / sid / "app"),
        },
        "requirement": {"vuln_id": "NAME-LDAP-INJECTION"},
        "run_matrix": {"vuln_bundles": [{"vuln_id": "NAME-LDAP-INJECTION", "slug": "name-ldap-injection", "workspace_subdir": "app"}]},
        "features": {"multi_vuln": False},
    }

    outcome = run_pipeline._terminal_research_failure_from_semantic_profile(plan)

    assert outcome["terminal"] is True
    assert outcome["terminal_failure_class"] == "semantic_support_missing"
    assert "name-ldap-injection" in outcome["reason"]


def test_terminal_research_failure_from_semantic_profile_allows_compiler_supported_name_bundle(tmp_path: Path) -> None:
    sid = "sid-compiler-profile"
    metadata_root = tmp_path / "metadata" / sid
    metadata_root.mkdir(parents=True, exist_ok=True)
    (metadata_root / "semantic_profile.json").write_text(
        json.dumps(
            {
                "schema_version": "semantic_profile@1.0",
                "sid": sid,
                "slug": "name-open-redirect",
                "normalized_vuln_id": "NAME-OPEN-REDIRECT",
                "family": "open_redirect",
                "support_level": "compiler_supported",
                "compiler_supported": True,
                "compiler_strategy": "open_redirect_reflect",
                "compiler_reason": "compiler strategy and scaffold are available",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    plan = {
        "sid": sid,
        "paths": {
            "metadata": str(metadata_root),
            "artifacts": str(tmp_path / "artifacts" / sid),
            "workspace": str(tmp_path / "workspaces" / sid / "app"),
        },
        "requirement": {"vuln_id": "NAME-OPEN-REDIRECT"},
        "run_matrix": {"vuln_bundles": [{"vuln_id": "NAME-OPEN-REDIRECT", "slug": "name-open-redirect", "workspace_subdir": "app"}]},
        "features": {"multi_vuln": False},
    }

    outcome = run_pipeline._terminal_research_failure_from_semantic_profile(plan)

    assert outcome["terminal"] is False


def test_can_skip_researcher_for_known_static_without_required_evidence() -> None:
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
    assert run_pipeline._can_skip_researcher(plan, refresh_requested=False) is True


def test_can_skip_researcher_for_compiler_supported_without_required_evidence() -> None:
    plan = {
        "requirement": {"researcher": {}},
        "policy": {"require_researcher_evidence": False},
        "run_matrix": {
            "vuln_bundles": [
                {"vuln_id": "CWE-22", "slug": "cwe-22", "workspace_subdir": "app"},
                {"vuln_id": "NAME-OPEN-REDIRECT", "slug": "name-open-redirect", "workspace_subdir": "app"},
            ]
        },
    }

    assert run_pipeline._can_skip_researcher(plan, refresh_requested=False) is True


def test_cannot_skip_researcher_when_required_or_refresh_requested() -> None:
    plan = {
        "requirement": {"researcher": {}},
        "policy": {"require_researcher_evidence": True},
        "run_matrix": {"vuln_bundles": [{"vuln_id": "CWE-9999", "slug": "cwe-9999", "workspace_subdir": "app"}]},
    }
    assert run_pipeline._can_skip_researcher(plan, refresh_requested=False) is False
    assert run_pipeline._can_skip_researcher(
        {"requirement": {"researcher": {}}, "policy": {"require_researcher_evidence": False}, "run_matrix": plan["run_matrix"]},
        refresh_requested=True,
    ) is False


def test_research_failure_details_uses_insufficient_evidence_reason(tmp_path: Path) -> None:
    sid = "sid-research-failure"
    metadata_root = tmp_path / "metadata" / sid
    metadata_root.mkdir(parents=True, exist_ok=True)
    report_path = metadata_root / "researcher_report.json"
    health_path = metadata_root / "search_health.json"
    health_path.write_text(
        json.dumps(
            {
                "provider": "custom",
                "configured": False,
                "last_error": "VUL_WEB_SEARCH_ENDPOINT is not configured",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    report_path.write_text(
        json.dumps(
            {
                "quality": "insufficient",
                "quality_reason": "Insufficient researcher evidence for CWE-9999: search_policy=remote_required requires at least one remote hit, but none were found.",
                "search_health_path": str(health_path),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    plan = {
        "sid": sid,
        "paths": {
            "metadata": str(metadata_root),
            "artifacts": str(tmp_path / "artifacts" / sid),
            "workspace": str(tmp_path / "workspaces" / sid / "app"),
        },
        "requirement": {"vuln_id": "CWE-9999"},
        "run_matrix": {"vuln_bundles": [{"vuln_id": "CWE-9999", "slug": "cwe-9999", "workspace_subdir": "app"}]},
        "features": {"multi_vuln": False},
    }

    reason, fix_hint, metadata = run_pipeline._research_failure_details(plan, 1)

    assert "Insufficient researcher evidence" in reason
    assert "Configure the remote search provider" in fix_hint
    assert metadata["search_provider"] == "custom"
    assert metadata["terminal_failure_class"] == "remote_provider_unavailable"
    assert metadata["retry_recommended"] is False


def test_should_retry_research_failure_false_for_terminal_class() -> None:
    metadata = {"terminal_failure_class": "remote_evidence_missing", "retry_recommended": False}

    assert run_pipeline._should_retry_research_failure(metadata) is False


def test_should_retry_research_failure_true_for_unclassified_failure() -> None:
    metadata = {"exit_code": 1}

    assert run_pipeline._should_retry_research_failure(metadata) is True


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
                "slug": "cwe-89",
                "vuln_id": "CWE-89",
                "llm_stub_used": True,
                "compiler_supported": False,
                "compiler_strategy": "sqli_string_concat",
                "compiler_reason": "compiler scaffold registry not implemented",
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
    assert payload["compiler_supported"] is False
    assert payload["compiler_strategy"] == "sqli_string_concat"
    assert payload["compiler_reason"] == "compiler scaffold registry not implemented"
    assert payload["compiler_contracts"][0]["compiler_supported"] is False


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


def test_write_perf_summary_marks_compiler_only_lane_as_not_probed(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-perf-compiler-only"
    metadata_root = tmp_path / "metadata" / sid
    metadata_root.mkdir(parents=True, exist_ok=True)
    (metadata_root / "resolved_contract.json").write_text(
        json.dumps(
            {
                "schema_version": "resolved_contract@1.0",
                "slug": "cwe-918",
                "vuln_id": "CWE-918",
                "compiler_supported": True,
                "compiler_strategy": "ssrf_loopback_fetch",
                "compiler_reason": "compiler strategy and scaffold are available",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(run_pipeline, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)
    events = [
        {"loop": 1, "stage": "GENERATOR", "duration_s": 1.5, "returncode": 0, "skipped": False, "note": ""},
        {"loop": 1, "stage": "PACK", "duration_s": 0.1, "returncode": 0, "skipped": False, "note": ""},
    ]

    run_pipeline._write_perf_summary(sid, events)

    payload = json.loads((metadata_root / "performance_summary.json").read_text(encoding="utf-8"))
    assert payload["provider_health_state"] == "not_probed"
    assert payload["compiler_supported"] is True
    assert payload["compiler_strategy"] == "ssrf_loopback_fetch"


def test_write_perf_summary_surfaces_remote_provider_unavailable_failure_class(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-perf-remote-unavailable"
    metadata_root = tmp_path / "metadata" / sid
    metadata_root.mkdir(parents=True, exist_ok=True)
    (metadata_root / "search_health.json").write_text(
        json.dumps(
            {
                "provider": "none",
                "configured": False,
                "degraded": False,
                "remote_result_count": 0,
                "last_error": "search_policy requires remote search, but no remote provider is configured",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (metadata_root / "loop_state.json").write_text(
        json.dumps(
            {
                "history": [
                    {
                        "stage": "RESEARCH",
                        "reason": "remote provider unavailable",
                        "success": False,
                        "timestamp": "2026-03-08T06:38:26.539948+00:00",
                        "metadata": {
                            "terminal_failure_class": "remote_provider_unavailable",
                            "retry_recommended": False,
                        },
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(run_pipeline, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)
    events = [
        {"loop": 1, "stage": "RESEARCH", "duration_s": 1.5, "returncode": 1, "skipped": False, "note": ""},
        {"loop": 1, "stage": "PACK", "duration_s": 0.1, "returncode": 0, "skipped": False, "note": ""},
    ]

    run_pipeline._write_perf_summary(sid, events)

    payload = json.loads((metadata_root / "performance_summary.json").read_text(encoding="utf-8"))
    assert payload["provider_health_state"] == "remote_provider_unavailable"


def test_analyze_verify_failures_marks_terminal_semantic_unsupported(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-terminal-verify"
    artifacts_root = tmp_path / "artifacts" / sid / "reports"
    artifacts_root.mkdir(parents=True, exist_ok=True)
    (artifacts_root / "evals.json").write_text(
        json.dumps(
            {
                "overall_pass": False,
                "results": [
                    {
                        "slug": "name-ldap-injection",
                        "vuln_id": "NAME-LDAP-INJECTION",
                        "verify_pass": False,
                        "semantic_supported": False,
                        "semantic_status": "unsupported",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(run_pipeline, "get_artifacts_dir", lambda incoming_sid: tmp_path / "artifacts" / incoming_sid)

    analysis = run_pipeline._analyze_verify_failures(sid)

    assert analysis["terminal_semantic_unsupported"] is True
    assert analysis["failure_count"] == 1
    assert analysis["slugs"] == ["name-ldap-injection"]


def test_analyze_verify_failures_keeps_retryable_verify_mismatch_non_terminal(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-retryable-verify"
    artifacts_root = tmp_path / "artifacts" / sid / "reports"
    artifacts_root.mkdir(parents=True, exist_ok=True)
    (artifacts_root / "evals.json").write_text(
        json.dumps(
            {
                "overall_pass": False,
                "results": [
                    {
                        "slug": "cwe-89",
                        "vuln_id": "CWE-89",
                        "verify_pass": False,
                        "semantic_supported": True,
                        "semantic_status": "contradicted",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(run_pipeline, "get_artifacts_dir", lambda incoming_sid: tmp_path / "artifacts" / incoming_sid)

    analysis = run_pipeline._analyze_verify_failures(sid)

    assert analysis["terminal_semantic_unsupported"] is False
    assert analysis["failure_count"] == 1


def test_compiler_contract_snapshot_deduplicates_resolved_and_legacy_contracts(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-compiler-contracts"
    metadata_root = tmp_path / "metadata" / sid
    metadata_root.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "resolved_contract@1.0",
        "sid": sid,
        "slug": "name-open-redirect",
        "vuln_id": "NAME-OPEN-REDIRECT",
        "compiler_supported": False,
        "compiler_strategy": "open_redirect_reflect",
        "compiler_reason": "family has deterministic fallback coverage but no compiler-backed path yet",
        "semantic_profile": {
            "family": "open_redirect",
            "support_level": "deferred",
        },
    }
    for name in ("resolved_contract.json", "generator_contract.json"):
        (metadata_root / name).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(run_pipeline, "get_metadata_dir", lambda incoming_sid: tmp_path / "metadata" / incoming_sid)

    snapshot = run_pipeline._compiler_contract_snapshot(sid)

    assert len(snapshot) == 1
    assert snapshot[0]["compiler_strategy"] == "open_redirect_reflect"
    assert snapshot[0]["support_level"] == "deferred"
