"""Helpers for append-only observation ledger artifacts."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

OBSERVATION_LEDGER_SCHEMA_VERSION = "observation_ledger@0.1"
OBSERVATION_LEDGER_FILENAME = "observation_ledger.jsonl"


def _metadata_root(metadata_dir: Path) -> Path:
    if metadata_dir.parent.name == "bundles":
        return metadata_dir.parent.parent
    return metadata_dir


def _bundle_slug(metadata_dir: Path) -> str | None:
    if metadata_dir.parent.name == "bundles":
        token = metadata_dir.name.strip()
        return token or None
    return None


def observation_paths(metadata_dir: Path) -> List[Path]:
    local = metadata_dir / OBSERVATION_LEDGER_FILENAME
    root = _metadata_root(metadata_dir) / OBSERVATION_LEDGER_FILENAME
    if local == root:
        return [local]
    return [local, root]


def append_observation(
    metadata_dir: Path,
    *,
    sid: str,
    observation_type: str,
    failure_stage: str | None = None,
    failure_class: str | None = None,
    repair_strategy: str | None = None,
    result: str | None = None,
    selection_signature: Dict[str, Any] | None = None,
    oracle_execution_parity: str | None = None,
    measured_gate_ready: bool | None = None,
    artifact_quality_band: str | None = None,
    metadata: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    bundle_slug = _bundle_slug(metadata_dir)
    observed_at = datetime.now(timezone.utc).isoformat()
    entry = {
        "schema_version": OBSERVATION_LEDGER_SCHEMA_VERSION,
        "observation_id": f"{sid}:{bundle_slug or 'root'}:{observation_type}:{observed_at}",
        "sid": sid,
        "bundle_slug": bundle_slug,
        "observation_type": str(observation_type or "").strip(),
        "failure_stage": str(failure_stage or "").strip() or None,
        "failure_class": str(failure_class or "").strip() or None,
        "repair_strategy": str(repair_strategy or "").strip() or None,
        "result": str(result or "").strip() or None,
        "selection_signature": selection_signature if isinstance(selection_signature, dict) and selection_signature else None,
        "oracle_execution_parity": str(oracle_execution_parity or "").strip() or None,
        "measured_gate_ready": bool(measured_gate_ready) if isinstance(measured_gate_ready, bool) else None,
        "artifact_quality_band": str(artifact_quality_band or "").strip() or None,
        "metadata": metadata if isinstance(metadata, dict) and metadata else None,
        "created_at": observed_at,
    }
    for path in observation_paths(metadata_dir):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def load_observations(metadata_dir: Path, *, include_root: bool = False) -> List[Dict[str, Any]]:
    paths: List[Path] = [metadata_dir / OBSERVATION_LEDGER_FILENAME]
    root = _metadata_root(metadata_dir) / OBSERVATION_LEDGER_FILENAME
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
            key = str(payload.get("observation_id") or "").strip()
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            records.append(payload)
    records.sort(key=lambda item: str(item.get("created_at") or ""))
    return records


def summarize_observations(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    total = 0
    by_type: Dict[str, int] = {}
    by_failure_class: Dict[str, int] = {}
    for entry in records:
        if not isinstance(entry, dict):
            continue
        total += 1
        obs_type = str(entry.get("observation_type") or "").strip() or "unknown"
        by_type[obs_type] = int(by_type.get(obs_type) or 0) + 1
        failure_class = str(entry.get("failure_class") or "").strip()
        if failure_class:
            by_failure_class[failure_class] = int(by_failure_class.get(failure_class) or 0) + 1
    return {
        "schema_version": OBSERVATION_LEDGER_SCHEMA_VERSION,
        "total_observations": total,
        "observation_type_counts": by_type,
        "failure_class_counts": by_failure_class,
    }
