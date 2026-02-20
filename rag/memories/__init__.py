"""Reflexion memory helpers.

The storage format is a JSON Lines file that captures reviewer findings or
executor failures so that follow-up generator passes can inject the
``failure_context`` described in docs/handbook.md (RAG/실패 맥락).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from common.logging import get_logger
from common.paths import get_metadata_dir, get_repo_root

LOGGER = get_logger(__name__)
_STORE_PATH = get_repo_root() / "rag" / "memories" / "reflexion_store.jsonl"
GENERATOR_FAILURE_FILENAME = "generator_failures.jsonl"


@dataclass
class ReflexionRecord:
    """Single Reflexion memory entry."""

    sid: str
    loop_count: int
    stage: str
    reason: str
    remediation_hint: str = ""
    blocking: bool = True
    metadata: Dict[str, str] = field(default_factory=dict)
    timestamp: str | None = None

    def to_dict(self) -> Dict[str, object]:
        payload = asdict(self)
        payload["timestamp"] = payload["timestamp"] or datetime.now(timezone.utc).isoformat()
        return payload


def _ensure_store() -> Path:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not _STORE_PATH.exists():
        _STORE_PATH.write_text("", encoding="utf-8")
    return _STORE_PATH


def append_memory(record: ReflexionRecord) -> None:
    """Persist a Reflexion record to the JSONL store."""

    path = _ensure_store()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
    LOGGER.debug("Reflexion memory appended for %s (loop %s)", record.sid, record.loop_count)


def _iter_store() -> Iterable[dict]:
    path = _ensure_store()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError as exc:  # pragma: no cover - corruption guard
            LOGGER.warning("Skipping malformed memory line: %s", exc)
            continue


def load_memories(sid: Optional[str] = None, limit: Optional[int] = None) -> List[dict]:
    """Return Reflexion records optionally filtered by SID."""

    records: List[dict] = []
    for entry in _iter_store():
        if sid and entry.get("sid") != sid:
            continue
        records.append(entry)
    records.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
    if limit is not None:
        return records[:limit]
    return records


def _load_generator_failures(sid: str) -> List[dict]:
    metadata_root = get_metadata_dir(sid)
    paths = [metadata_root / GENERATOR_FAILURE_FILENAME]
    bundles_dir = metadata_root / "bundles"
    if bundles_dir.exists():
        paths.extend(sorted(bundles_dir.glob(f"*/{GENERATOR_FAILURE_FILENAME}")))
    records: List[dict] = []
    seen: set[str] = set()
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                entry.setdefault("stage", "GENERATOR")
                entry.setdefault("timestamp", "")
                dedupe_key = json.dumps(
                    {
                        "timestamp": entry.get("timestamp"),
                        "reason": entry.get("reason"),
                        "guard_error_code": entry.get("guard_error_code"),
                        "failure_fingerprint": entry.get("failure_fingerprint"),
                        "vuln_id": entry.get("vuln_id"),
                        "slug": entry.get("slug"),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                records.append(entry)
            except json.JSONDecodeError as exc:  # pragma: no cover - corruption guard
                LOGGER.warning("Skipping malformed generator failure line: %s", exc)
                continue
    records.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
    return records


def latest_failure_context(sid: str, limit: int = 3) -> str:
    """Return a human-readable summary for prompt injection."""

    def _format_log_excerpt(metadata: Dict[str, object], *, limit_chars: int = 900) -> str:
        excerpt = metadata.get("log_excerpt")
        if not isinstance(excerpt, str) or not excerpt.strip():
            return ""
        text = excerpt.strip()
        if limit_chars > 0 and len(text) > limit_chars:
            # Keep the tail (it is usually the most actionable part of build/run logs).
            text = text[-limit_chars:]
        path = metadata.get("log_excerpt_path")
        label = ""
        if isinstance(path, str) and path.strip():
            label = Path(path.strip()).name
        header = f"Log excerpt ({label} tail):" if label else "Log excerpt (tail):"
        return f"\n  {header}\n```text\n{text}\n```"

    generator_records = _load_generator_failures(sid)
    reflexion_limit = limit * 2 if limit is not None else None
    reflexion_records = load_memories(sid=sid, limit=reflexion_limit)
    combined: List[dict] = []
    for record in generator_records:
        combined.append(
            {
                "stage": record.get("stage", "GENERATOR"),
                "timestamp": record.get("timestamp", ""),
                "loop_count": record.get("loop_count"),
                "reason": record.get("reason", "guard failure"),
                "hint": record.get("fix_hint", ""),
                "missing": record.get("missing_dependencies", []),
                "guard_error_code": record.get("guard_error_code", ""),
                "guard_error_subcode": record.get("guard_error_subcode", ""),
                "unsupported_ops": record.get("unsupported_ops", []),
                "schema_errors": record.get("schema_errors", []),
                "hint_payload": record.get("hint_payload"),
            }
        )
    for record in reflexion_records:
        meta = record.get("metadata")
        meta = meta if isinstance(meta, dict) else {}
        stage = record.get("stage", "REVIEW")
        if stage == "EXECUTOR":
            substage = meta.get("stage")
            if isinstance(substage, str) and substage.strip():
                stage = f"EXECUTOR/{substage.strip()}"
        combined.append(
            {
                "stage": stage,
                "timestamp": record.get("timestamp", ""),
                "loop_count": record.get("loop_count"),
                "reason": record.get("reason", ""),
                "hint": record.get("remediation_hint", ""),
                "missing": meta.get("missing_dependencies", []),
                "log_excerpt": _format_log_excerpt(meta),
            }
        )
    if not combined:
        return ""
    combined.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
    summary_lines = []
    for record in combined[:limit]:
        stage = record.get("stage")
        if stage == "GENERATOR":
            missing = record.get("missing") or []
            missing_part = f" Missing deps: {', '.join(missing)}." if missing else ""
            error_code = str(record.get("guard_error_code") or "").strip()
            unsupported = record.get("unsupported_ops") or []
            schema_errors = record.get("schema_errors") or []
            unsupported_part = ""
            if isinstance(unsupported, list) and unsupported:
                unsupported_part = f" Unsupported ops: {', '.join(str(op) for op in unsupported if op)}."
            schema_part = ""
            if isinstance(schema_errors, list) and schema_errors:
                schema_part = f" Schema errors: {', '.join(str(item) for item in schema_errors if item)}."
            code_part = f" Error code: {error_code}." if error_code else ""
            subcode = str(record.get("guard_error_subcode") or "").strip()
            subcode_part = f" Subcode: {subcode}." if subcode else ""
            hint_payload = record.get("hint_payload")
            payload_part = ""
            if isinstance(hint_payload, dict):
                next_action = hint_payload.get("next_action")
                if isinstance(next_action, dict):
                    retry_stage = str(next_action.get("retry_stage") or "").strip()
                    researcher_refresh = bool(next_action.get("researcher_refresh"))
                    if retry_stage or researcher_refresh:
                        payload_part = (
                            f" Next action: stage={retry_stage or 'GENERATOR'}, "
                            f"researcher_refresh={str(researcher_refresh).lower()}."
                        )
            summary_lines.append(
                f"- Generator guard: {record.get('reason')}.{missing_part}{unsupported_part}{schema_part}{code_part}{subcode_part}{payload_part} "
                f"Hint: {record.get('hint')}"
            )
        else:
            log_excerpt = record.get("log_excerpt") or ""
            summary_lines.append(
                f"- Loop {record.get('loop_count')} ({record.get('stage')}): {record.get('reason')}. Hint: {record.get('hint')}{log_excerpt}"
            )
    return "\n".join(summary_lines)


__all__ = ["ReflexionRecord", "append_memory", "load_memories", "latest_failure_context"]
