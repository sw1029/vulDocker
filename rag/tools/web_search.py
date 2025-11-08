"""Fallback-friendly web search helper for the Researcher agent."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from common.logging import get_logger
from common.paths import get_repo_root

try:  # pragma: no cover - optional dependency
    import requests
except Exception:  # pragma: no cover - optional dependency
    requests = None

LOGGER = get_logger(__name__)


@dataclass
class SearchResult:
    """Normalized container for search hits."""

    title: str
    url: str
    snippet: str
    source: str = "local"
    published: Optional[str] = None

    def to_payload(self) -> Dict[str, str]:
        payload: Dict[str, str] = {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source,
        }
        if self.published:
            payload["published"] = self.published
        return payload


class WebSearchTool:
    """Hybrid search helper that prefers remote APIs but falls back to local corpus."""

    def __init__(
        self,
        *,
        endpoint: Optional[str] = None,
        timeout: float = 8.0,
        max_local_files: int = 300,
    ) -> None:
        self.endpoint = endpoint or os.environ.get("VUL_WEB_SEARCH_ENDPOINT")
        self.timeout = timeout
        self.max_local_files = max_local_files
        self.local_root = get_repo_root() / "rag" / "corpus"

    def search(self, query: str, limit: int = 3) -> List[SearchResult]:
        """Return up to ``limit`` results for a query."""

        query = (query or "").strip()
        if not query:
            return []

        if self.endpoint:
            remote_hits = self._remote_search(query, limit)
            if remote_hits:
                return remote_hits

        return self._local_search(query, limit)

    # Remote search helpers -------------------------------------------------

    def _remote_search(self, query: str, limit: int) -> List[SearchResult]:
        if requests is None:
            LOGGER.warning("requests package unavailable; skipping remote search endpoint %s", self.endpoint)
            return []
        try:  # pragma: no cover - network calls are not exercised in tests
            response = requests.get(
                self.endpoint,
                params={"q": query, "size": limit},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # pragma: no cover - network code paths
            LOGGER.warning("Remote search failed for '%s': %s", query, exc)
            return []
        return self._parse_remote_payload(payload, limit)

    def _parse_remote_payload(self, payload: Any, limit: int) -> List[SearchResult]:
        candidates: List[Dict[str, Any]] = []
        if isinstance(payload, dict):
            for key in ("results", "items", "data"):
                maybe = payload.get(key)
                if isinstance(maybe, list):
                    candidates = maybe
                    break
        elif isinstance(payload, list):
            candidates = payload

        hits: List[SearchResult] = []
        for entry in candidates:
            if not isinstance(entry, dict):
                continue
            title = entry.get("title") or entry.get("name") or "untitled"
            url = entry.get("url") or entry.get("link")
            snippet = entry.get("snippet") or entry.get("summary") or entry.get("body")
            if not url or not snippet:
                continue
            published = entry.get("published") or entry.get("date")
            hits.append(
                SearchResult(
                    title=str(title),
                    url=str(url),
                    snippet=str(snippet),
                    source="remote",
                    published=str(published) if published else None,
                )
            )
            if len(hits) >= limit:
                break
        return hits

    # Local search helpers --------------------------------------------------

    def _local_search(self, query: str, limit: int) -> List[SearchResult]:
        tokens = [token for token in query.lower().split() if token]
        hits: List[SearchResult] = []
        for path in self._iter_local_files():
            try:
                text = path.read_text(encoding="utf-8")
            except Exception as exc:  # pragma: no cover - IO guard
                LOGGER.debug("Skipping %s due to read error: %s", path, exc)
                continue
            haystack = text.lower()
            if tokens and not any(token in haystack for token in tokens):
                continue
            snippet = " ".join(text.strip().split())
            if not snippet:
                snippet = "(empty content)"
            hits.append(
                SearchResult(
                    title=path.name,
                    url=str(path),
                    snippet=snippet[:400],
                    source="local",
                )
            )
            if len(hits) >= limit:
                break
        return hits

    def _iter_local_files(self) -> Iterable[Path]:
        if not self.local_root.exists():
            return []
        yielded = 0
        for section in ("processed", "raw"):
            base = self.local_root / section
            if not base.exists():
                continue
            for pattern in ("*.md", "*.txt"):
                for path in sorted(base.rglob(pattern)):
                    yield path
                    yielded += 1
                    if yielded >= self.max_local_files:
                        return


__all__ = ["SearchResult", "WebSearchTool"]
