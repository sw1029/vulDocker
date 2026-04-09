"""Helpers for declarative stage gate artifacts."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

STAGE_GATE_REPORT_SCHEMA_VERSION = "stage_gate_report@0.1"
STAGE_GATE_REPORT_FILENAME = "stage_gate_report.json"


def _metadata_root(metadata_dir: Path) -> Path:
    if metadata_dir.parent.name == "bundles":
        return metadata_dir.parent.parent
    return metadata_dir


def _bundle_slug(metadata_dir: Path) -> str | None:
    if metadata_dir.parent.name == "bundles":
        token = metadata_dir.name.strip()
        return token or None
    return None


def stage_gate_paths(metadata_dir: Path) -> List[Path]:
    local = metadata_dir / STAGE_GATE_REPORT_FILENAME
    root = _metadata_root(metadata_dir) / STAGE_GATE_REPORT_FILENAME
    if local == root:
        return [local]
    return [local, root]


def record_stage_gate(
    metadata_dir: Path,
    *,
    sid: str,
    gate_id: str,
    stage: str,
    passed: bool,
    blocking: bool = True,
    enabled: bool = True,
    failure_class: str | None = None,
    detail: str | None = None,
    retry_policy: str | None = None,
    emits: List[str] | None = None,
    evidence: List[str] | None = None,
    metadata: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    bundle_slug = _bundle_slug(metadata_dir)
    gate_key = f"{bundle_slug or 'root'}:{gate_id}"
    record = {
        "gate_record_id": gate_key,
        "gate_id": str(gate_id or "").strip(),
        "stage": str(stage or "").strip(),
        "sid": sid,
        "bundle_slug": bundle_slug,
        "passed": bool(passed),
        "blocking": bool(blocking),
        "enabled": bool(enabled),
        "failure_class": str(failure_class or "").strip() or None,
        "detail": str(detail or "").strip() or None,
        "retry_policy": str(retry_policy or "").strip() or None,
        "emits": list(emits or []),
        "evidence": list(evidence or []),
        "metadata": metadata if isinstance(metadata, dict) and metadata else None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    for path in stage_gate_paths(metadata_dir):
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = _load_gate_payload(path)
        gates = payload.get("gates") or []
        replaced = False
        next_gates: List[Dict[str, Any]] = []
        for entry in gates:
            if isinstance(entry, dict) and entry.get("gate_record_id") == gate_key:
                next_gates.append(record)
                replaced = True
            elif isinstance(entry, dict):
                next_gates.append(entry)
        if not replaced:
            next_gates.append(record)
        payload.update(
            {
                "schema_version": STAGE_GATE_REPORT_SCHEMA_VERSION,
                "sid": sid,
                "updated_at": record["updated_at"],
                "gates": next_gates,
            }
        )
        if bundle_slug:
            payload["bundle_slug"] = bundle_slug
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return record


def load_stage_gate_report(metadata_dir: Path, *, include_root: bool = False) -> Dict[str, Any]:
    local = metadata_dir / STAGE_GATE_REPORT_FILENAME
    if not include_root:
        return _load_gate_payload(local)
    payload = _load_gate_payload(local)
    root = _metadata_root(metadata_dir) / STAGE_GATE_REPORT_FILENAME
    if root == local or not root.exists():
        return payload
    root_payload = _load_gate_payload(root)
    merged: Dict[str, Dict[str, Any]] = {}
    for source in (payload.get("gates") or [], root_payload.get("gates") or []):
        for entry in source:
            if not isinstance(entry, dict):
                continue
            key = str(entry.get("gate_record_id") or "").strip()
            if not key:
                continue
            merged[key] = entry
    payload["gates"] = list(merged.values())
    return payload


def _load_gate_payload(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"schema_version": STAGE_GATE_REPORT_SCHEMA_VERSION, "gates": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"schema_version": STAGE_GATE_REPORT_SCHEMA_VERSION, "gates": []}
    if not isinstance(payload, dict):
        return {"schema_version": STAGE_GATE_REPORT_SCHEMA_VERSION, "gates": []}
    gates = payload.get("gates")
    if not isinstance(gates, list):
        payload["gates"] = []
    return payload


def summarize_stage_gates(payload: Dict[str, Any] | Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    if isinstance(payload, dict):
        gates = payload.get("gates") or []
    else:
        gates = list(payload)
    total = 0
    passed = 0
    failed = 0
    first_blocking_failure: Dict[str, Any] | None = None
    gate_counts: Dict[str, int] = {}
    failed_gate_ids: List[str] = []
    for entry in gates:
        if not isinstance(entry, dict):
            continue
        total += 1
        gate_id = str(entry.get("gate_id") or "").strip() or "unknown"
        gate_counts[gate_id] = int(gate_counts.get(gate_id) or 0) + 1
        if entry.get("passed") is True:
            passed += 1
            continue
        failed += 1
        failed_gate_ids.append(gate_id)
        if first_blocking_failure is None and entry.get("blocking") is True:
            first_blocking_failure = {
                "gate_id": gate_id,
                "stage": entry.get("stage"),
                "bundle_slug": entry.get("bundle_slug"),
                "failure_class": entry.get("failure_class"),
                "detail": entry.get("detail"),
                "updated_at": entry.get("updated_at"),
            }
    return {
        "schema_version": STAGE_GATE_REPORT_SCHEMA_VERSION,
        "total_gates": total,
        "passed": passed,
        "failed": failed,
        "gate_counts": gate_counts,
        "failed_gate_ids": failed_gate_ids,
        "first_blocking_failure_gate": first_blocking_failure,
    }

