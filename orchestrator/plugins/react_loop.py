"""Helpers that wire Researcher ReAct loops into the orchestrator."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from common.logging import get_logger
from common.paths import ensure_dir, get_metadata_dir
from rag import latest_failure_context

LOGGER = get_logger(__name__)


@dataclass
class ReactSpan:
    """Context manager that records researcher.react span metadata."""

    loop: "ReactLoop"
    name: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    _events: List[Dict[str, Any]] = field(default_factory=list)
    _start: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def event(self, name: str, **attrs: Any) -> None:
        self._events.append(
            {
                "name": name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "attributes": attrs,
            }
        )

    def close(self) -> None:
        if self.loop is None:
            return
        payload = {
            "trace_id": self.loop.trace_id,
            "span_id": self.span_id,
            "span_name": self.name,
            "started_at": self._start.isoformat(),
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "attributes": self.attributes,
            "events": self._events,
        }
        self.loop._append_span(payload)
        self.loop = None

    def __enter__(self) -> "ReactSpan":
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        self.close()


class ReactLoop:
    """Light-weight plugin that captures Researcher queries and spans."""

    def __init__(self, sid: str) -> None:
        self.sid = sid
        self.metadata_dir = ensure_dir(get_metadata_dir(sid))
        self.trace_id = f"{sid}-react-{uuid.uuid4().hex[:8]}"
        self.failure_context = latest_failure_context(sid)
        self._span_path = self.metadata_dir / "react_trace.jsonl"
        self._history_path = self.metadata_dir / "researcher_history.jsonl"

    def span(self, name: str = "researcher.react", **attrs: Any) -> ReactSpan:
        """Return a context manager capturing a Researcher span."""

        return ReactSpan(loop=self, name=name, attributes=attrs)

    def queries_from_requirement(self, requirement: Dict[str, Any], *, limit: int = 3) -> List[str]:
        """Generate deterministic ReAct-style seed queries."""

        queries: List[str] = []
        vuln_ids = _vuln_ids_from_requirement(requirement)
        language = requirement.get("language")
        framework = requirement.get("framework")
        tech_stack = " ".join(filter(None, [language, framework]))
        intent = requirement.get("intent") or requirement.get("goal") or ""

        for vuln_id in vuln_ids:
            queries.append(f"{vuln_id} exploit writeup {tech_stack}".strip())
        if intent:
            queries.append(f"{intent} poc tutorial {tech_stack}".strip())
        runtime = requirement.get("runtime") or {}
        db = runtime.get("db") or runtime.get("database") or requirement.get("database")
        if db:
            anchor = vuln_ids[0] if vuln_ids else "vulnerability"
            queries.append(f"{anchor} {db} misconfiguration case study")

        if not queries:
            queries.append("autonomous vulnerability lab research report")

        augmented = self._augment_with_failures(queries)
        unique = []
        for query in augmented:
            normalized = query.strip()
            if not normalized or normalized in unique:
                continue
            unique.append(normalized)
            if len(unique) >= limit:
                break
        return unique

    def record_researcher_report(
        self,
        *,
        queries: Iterable[str],
        search_results: Iterable[Dict[str, Any]],
        report_path: Path,
    ) -> None:
        """Append a JSON line summarizing the Researcher output."""

        payload = {
            "trace_id": self.trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "queries": list(queries),
            "search_results": list(search_results),
            "report_path": str(report_path),
        }
        with self._history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    # Internal helpers -----------------------------------------------------

    def _augment_with_failures(self, queries: List[str]) -> List[str]:
        if not self.failure_context:
            return queries
        hints = []
        for line in self.failure_context.splitlines():
            tokens = [token.strip() for token in line.split(":") if token.strip()]
            if len(tokens) >= 2:
                hints.append(tokens[-1])
        if hints:
            queries.append(f"{' '.join(hints[:2])} mitigation guidance")
        return queries

    def _append_span(self, payload: Dict[str, Any]) -> None:
        with self._span_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _vuln_ids_from_requirement(requirement: Dict[str, Any]) -> List[str]:
    values = requirement.get("vuln_ids")
    if isinstance(values, list):
        normalized = [str(item).strip() for item in values if isinstance(item, str) and item.strip()]
        if normalized:
            return normalized
    fallback = requirement.get("vuln_id") or requirement.get("cwe_id") or requirement.get("cve_id")
    if isinstance(fallback, str) and fallback.strip():
        return [fallback.strip()]
    return []


__all__ = ["ReactLoop", "ReactSpan"]
