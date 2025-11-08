"""Reflexion memory helpers.

The storage format is a JSON Lines file that captures reviewer findings or
executor failures so that follow-up generator passes can inject the
``failure_context`` described in docs/rag/design.md and
docs/milestones/todo_13-15_code_plan.md.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from common.logging import get_logger
from common.paths import get_repo_root

LOGGER = get_logger(__name__)
_STORE_PATH = get_repo_root() / "rag" / "memories" / "reflexion_store.jsonl"


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


def latest_failure_context(sid: str, limit: int = 3) -> str:
    """Return a human-readable summary for prompt injection."""

    records = load_memories(sid=sid, limit=limit)
    if not records:
        return ""
    summary_lines = []
    for record in records:
        summary_lines.append(
            f"- Loop {record.get('loop_count')}: {record.get('reason')}. "
            f"Hint: {record.get('remediation_hint')}"
        )
    return "\n".join(summary_lines)


__all__ = ["ReflexionRecord", "append_memory", "load_memories", "latest_failure_context"]
