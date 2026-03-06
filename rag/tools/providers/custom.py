"""Generic backward-compatible custom search endpoint adapter."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from common.logging import get_logger

from .base import SearchExecution, SearchProvider, SearchRequest, SearchResult, _stable_digest

try:  # pragma: no cover - optional dependency
    import requests
except Exception:  # pragma: no cover
    requests = None

LOGGER = get_logger(__name__)


class CustomSearchProvider(SearchProvider):
    name = "custom"

    def __init__(self, *, endpoint: Optional[str], timeout: float = 8.0) -> None:
        self.endpoint = (endpoint or "").strip()
        self.timeout = timeout

    def search(self, request: SearchRequest) -> Tuple[List[SearchResult], SearchExecution]:
        params: Dict[str, Any] = {"q": request.query, "size": request.limit}
        if request.include_domains:
            params["include_domains"] = list(request.include_domains)
        if request.exclude_domains:
            params["exclude_domains"] = list(request.exclude_domains)
        if request.time_range:
            params["time_range"] = request.time_range
        if request.country:
            params["country"] = request.country
        if request.search_lang:
            params["search_lang"] = request.search_lang
        req_payload = {
            "method": "GET",
            "url": self.endpoint,
            "params": params,
        }
        if not self.endpoint:
            return [], SearchExecution(
                provider=self.name,
                configured=False,
                error="VUL_WEB_SEARCH_ENDPOINT is not configured",
                endpoint_or_base_url=None,
                auth_present=None,
                request=req_payload,
            )
        if requests is None:
            return [], SearchExecution(
                provider=self.name,
                configured=True,
                error="requests package unavailable",
                endpoint_or_base_url=self.endpoint,
                auth_present=None,
                request=req_payload,
            )

        started = time.monotonic()
        try:  # pragma: no cover - network calls are not exercised in tests
            response = requests.get(
                self.endpoint,
                params=req_payload["params"],
                timeout=self.timeout,
            )
            status_code = response.status_code
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # pragma: no cover - network code paths
            latency_ms = int((time.monotonic() - started) * 1000)
            LOGGER.warning("Custom remote search failed for '%s': %s", request.query, exc)
            return [], SearchExecution(
                provider=self.name,
                configured=True,
                status_code=status_code if "status_code" in locals() else None,
                latency_ms=latency_ms,
                error=str(exc),
                endpoint_or_base_url=self.endpoint,
                auth_present=None,
                request=req_payload,
            )

        latency_ms = int((time.monotonic() - started) * 1000)
        hits = self._parse_remote_payload(payload, request=request)
        execution = SearchExecution(
            provider=self.name,
            configured=True,
            status_code=status_code,
            latency_ms=latency_ms,
            result_count=len(hits),
            endpoint_or_base_url=self.endpoint,
            auth_present=None,
            request=req_payload,
            raw_payload_digest=_stable_digest(payload),
        )
        return hits, execution

    def _parse_remote_payload(self, payload: Any, *, request: SearchRequest) -> List[SearchResult]:
        candidates: List[Dict[str, Any]] = []
        if isinstance(payload, dict):
            for key in ("results", "items", "data", "list"):
                maybe = payload.get(key)
                if isinstance(maybe, list):
                    candidates = maybe
                    break
        elif isinstance(payload, list):
            candidates = payload

        hits: List[SearchResult] = []
        request_id = None
        if isinstance(payload, dict):
            raw_request_id = payload.get("request_id") or payload.get("id")
            if raw_request_id:
                request_id = str(raw_request_id)
        for entry in candidates:
            if not isinstance(entry, dict):
                continue
            title = entry.get("title") or entry.get("name") or "untitled"
            url = entry.get("url") or entry.get("link")
            snippet = (
                entry.get("snippet")
                or entry.get("summary")
                or entry.get("body")
                or entry.get("content")
            )
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
                    provider=self.name,
                    request_id=request_id,
                    query=request.query,
                )
            )
            if len(hits) >= request.limit:
                break
        return hits


__all__ = ["CustomSearchProvider"]
