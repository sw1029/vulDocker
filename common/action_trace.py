"""Helpers for machine-readable action trace artifacts."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

ACTION_TRACE_SCHEMA_VERSION = "action_trace@0.1"
ACTION_TRACE_FILENAME = "action_trace.jsonl"


def _metadata_root(metadata_dir: Path) -> Path:
    if metadata_dir.parent.name == "bundles":
        return metadata_dir.parent.parent
    return metadata_dir


def _bundle_slug(metadata_dir: Path) -> str | None:
    if metadata_dir.parent.name == "bundles":
        token = metadata_dir.name.strip()
        return token or None
    return None


def action_trace_paths(metadata_dir: Path) -> List[Path]:
    local = metadata_dir / ACTION_TRACE_FILENAME
    root = _metadata_root(metadata_dir) / ACTION_TRACE_FILENAME
    if local == root:
        return [local]
    return [local, root]


def emit_action_trace(
    metadata_dir: Path,
    *,
    sid: str,
    stage: str,
    action_id: str,
    status: str,
    trace_id: str | None = None,
    attempt: int | None = None,
    blocking: bool | None = None,
    failure_class: str | None = None,
    detail: str | None = None,
    duration_ms: int | None = None,
    input_contract: Dict[str, Any] | None = None,
    output_contract: Dict[str, Any] | None = None,
    source_authority: str | None = None,
    concurrency_safe: bool | None = None,
    cacheable: bool | None = None,
    retryable: bool | None = None,
    emitted_artifacts: List[str] | None = None,
    selected_family: str | None = None,
    selected_stack_id: str | None = None,
    selected_scenario_id: str | None = None,
    materialized_family: str | None = None,
    materialized_topology: str | None = None,
    metadata: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    bundle_slug = _bundle_slug(metadata_dir)
    emitted_at = datetime.now(timezone.utc).isoformat()
    record = {
        "schema_version": ACTION_TRACE_SCHEMA_VERSION,
        "trace_id": str(trace_id or f"{sid}:{bundle_slug or 'root'}:{stage}:{action_id}"),
        "sid": sid,
        "bundle_slug": bundle_slug,
        "stage": str(stage or "").strip(),
        "action_id": str(action_id or "").strip(),
        "status": str(status or "").strip().lower() or "unknown",
        "attempt": int(attempt) if isinstance(attempt, int) else None,
        "blocking": bool(blocking) if isinstance(blocking, bool) else None,
        "failure_class": str(failure_class or "").strip() or None,
        "detail": str(detail or "").strip() or None,
        "duration_ms": int(duration_ms) if isinstance(duration_ms, int) else None,
        "input_contract": input_contract if isinstance(input_contract, dict) and input_contract else None,
        "output_contract": output_contract if isinstance(output_contract, dict) and output_contract else None,
        "source_authority": str(source_authority or "").strip() or None,
        "concurrency_safe": bool(concurrency_safe) if isinstance(concurrency_safe, bool) else None,
        "cacheable": bool(cacheable) if isinstance(cacheable, bool) else None,
        "retryable": bool(retryable) if isinstance(retryable, bool) else None,
        "emitted_artifacts": list(emitted_artifacts or []),
        "selected_family": str(selected_family or "").strip() or None,
        "selected_stack_id": str(selected_stack_id or "").strip() or None,
        "selected_scenario_id": str(selected_scenario_id or "").strip() or None,
        "materialized_family": str(materialized_family or "").strip() or None,
        "materialized_topology": str(materialized_topology or "").strip() or None,
        "metadata": metadata if isinstance(metadata, dict) and metadata else None,
        "emitted_at": emitted_at,
    }
    for path in action_trace_paths(metadata_dir):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def load_action_trace(metadata_dir: Path, *, include_root: bool = False) -> List[Dict[str, Any]]:
    paths: List[Path] = [metadata_dir / ACTION_TRACE_FILENAME]
    root = _metadata_root(metadata_dir) / ACTION_TRACE_FILENAME
    if include_root and root not in paths:
        paths.append(root)
    return _read_records(paths)


def _read_records(paths: Iterable[Path]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            trace_key = json.dumps(
                {
                    "trace_id": payload.get("trace_id"),
                    "bundle_slug": payload.get("bundle_slug"),
                    "action_id": payload.get("action_id"),
                    "status": payload.get("status"),
                    "emitted_at": payload.get("emitted_at"),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            if trace_key in seen:
                continue
            seen.add(trace_key)
            records.append(payload)
    records.sort(key=lambda item: str(item.get("emitted_at") or ""))
    return records


def summarize_action_trace(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    total = 0
    status_counts: Dict[str, int] = {}
    stage_counts: Dict[str, int] = {}
    action_counts: Dict[str, int] = {}
    first_failure: Dict[str, Any] | None = None

    for record in records:
        if not isinstance(record, dict):
            continue
        total += 1
        status = str(record.get("status") or "unknown").strip().lower() or "unknown"
        stage = str(record.get("stage") or "").strip() or "UNKNOWN"
        action_id = str(record.get("action_id") or "").strip() or "unknown"
        status_counts[status] = int(status_counts.get(status) or 0) + 1
        stage_counts[stage] = int(stage_counts.get(stage) or 0) + 1
        action_counts[action_id] = int(action_counts.get(action_id) or 0) + 1
        is_failure = status in {"failure", "failed", "error"}
        if is_failure and first_failure is None:
            first_failure = {
                "trace_id": record.get("trace_id"),
                "bundle_slug": record.get("bundle_slug"),
                "stage": record.get("stage"),
                "action_id": record.get("action_id"),
                "failure_class": record.get("failure_class"),
                "detail": record.get("detail"),
                "blocking": record.get("blocking"),
                "emitted_at": record.get("emitted_at"),
            }

    return {
        "schema_version": ACTION_TRACE_SCHEMA_VERSION,
        "total_actions": total,
        "status_counts": status_counts,
        "stage_counts": stage_counts,
        "action_counts": action_counts,
        "failure_count": sum(count for key, count in status_counts.items() if key in {"failure", "failed", "error"}),
        "first_failure_action": first_failure,
    }

