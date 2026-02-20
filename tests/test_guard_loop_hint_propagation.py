from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import rag.memories as memories
from orchestrator.run_pipeline import _refresh_researcher_on_dsl_error


def test_latest_failure_context_includes_guard_dsl_details(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-test-loop"
    metadata_root = tmp_path / "metadata"
    sid_meta = metadata_root / sid
    sid_meta.mkdir(parents=True, exist_ok=True)
    failure_path = sid_meta / "generator_failures.jsonl"
    failure_entry = {
        "stage": "GENERATOR",
        "timestamp": "2026-02-20T14:22:04Z",
        "reason": "guard assertion failed: unsupported guard assertion op: regex_any_file",
        "fix_hint": "Regenerate guard spec",
        "guard_error_code": "guard_dsl_unsupported_op",
        "unsupported_ops": ["regex_any_file"],
        "missing_dependencies": [],
        "hint_payload": {
            "schema_version": "hint_payload@1",
            "sid": sid,
            "vuln_id": "CWE-89",
            "slug": "cwe-89",
            "loop": 1,
            "guard_error_code": "guard_dsl_unsupported_op",
            "must_fix": [],
            "semantic_gaps": [],
            "supported_ops": ["file_exists"],
            "normalization_suggestions": [],
            "next_action": {
                "retry_stage": "RESEARCH",
                "researcher_refresh": True,
                "rationale": "unsupported op requires researcher refresh",
            },
            "prompt_instructions": [],
        },
    }
    failure_path.write_text(json.dumps(failure_entry, ensure_ascii=False) + "\n", encoding="utf-8")

    monkeypatch.setattr(memories, "get_metadata_dir", lambda incoming_sid: metadata_root / incoming_sid)
    monkeypatch.setattr(memories, "_STORE_PATH", tmp_path / "rag" / "memories" / "reflexion_store.jsonl")

    context = memories.latest_failure_context(sid)
    assert "Error code: guard_dsl_unsupported_op" in context
    assert "Unsupported ops: regex_any_file" in context
    assert "researcher_refresh=true" in context


def test_refresh_researcher_on_guard_dsl_error_policy() -> None:
    plan = {"policy": {"guard": {"refresh_researcher_on_guard_dsl_error": True}}}
    failure = {"guard_error_code": "guard_dsl_unsupported_op"}
    assert _refresh_researcher_on_dsl_error(plan, failure) is True

    plan_disabled = {"policy": {"guard": {"refresh_researcher_on_guard_dsl_error": False}}}
    assert _refresh_researcher_on_dsl_error(plan_disabled, failure) is False

    other_failure = {"guard_error_code": "guard_semantic_mismatch"}
    assert _refresh_researcher_on_dsl_error(plan, other_failure) is False
