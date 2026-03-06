"""Tavily search provider adapter."""
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

DEFAULT_TAVILY_BASE_URL = "https://api.tavily.com/search"


class TavilySearchProvider(SearchProvider):
    name = "tavily"

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 8.0,
    ) -> None:
        self.base_url = (base_url or DEFAULT_TAVILY_BASE_URL).strip() or DEFAULT_TAVILY_BASE_URL
        self.api_key = (api_key or "").strip()
        self.timeout = timeout

    def search(self, request: SearchRequest) -> Tuple[List[SearchResult], SearchExecution]:
        auth_present = bool(self.api_key)
        body: Dict[str, Any] = {
            "query": request.query,
            "max_results": request.limit,
            "search_depth": "advanced" if request.policy == "remote_required" else "basic",
            "include_raw_content": bool(request.include_raw_content),
        }
        if request.include_domains:
            body["include_domains"] = list(request.include_domains)
        if request.exclude_domains:
            body["exclude_domains"] = list(request.exclude_domains)
        if request.time_range:
            body["time_range"] = request.time_range
        req_payload = {
            "method": "POST",
            "url": self.base_url,
            "json": body,
        }

        if not auth_present:
            return [], SearchExecution(
                provider=self.name,
                configured=False,
                error="VUL_WEB_SEARCH_API_KEY is not configured for Tavily",
                endpoint_or_base_url=self.base_url,
                auth_present=False,
                request=req_payload,
            )
        if requests is None:
            return [], SearchExecution(
                provider=self.name,
                configured=True,
                error="requests package unavailable",
                endpoint_or_base_url=self.base_url,
                auth_present=True,
                request=req_payload,
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        started = time.monotonic()
        try:  # pragma: no cover - network calls are not exercised in tests
            response = requests.post(
                self.base_url,
                json=body,
                headers=headers,
                timeout=self.timeout,
            )
            status_code = response.status_code
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # pragma: no cover - network code paths
            latency_ms = int((time.monotonic() - started) * 1000)
            LOGGER.warning("Tavily search failed for '%s': %s", request.query, exc)
            return [], SearchExecution(
                provider=self.name,
                configured=True,
                status_code=status_code if "status_code" in locals() else None,
                latency_ms=latency_ms,
                error=str(exc),
                endpoint_or_base_url=self.base_url,
                auth_present=True,
                request=req_payload,
            )

        latency_ms = int((time.monotonic() - started) * 1000)
        request_id = str(payload.get("request_id") or "") if isinstance(payload, dict) else ""
        hits = self._parse_payload(payload, request=request, request_id=request_id or None)
        execution = SearchExecution(
            provider=self.name,
            configured=True,
            status_code=status_code,
            latency_ms=latency_ms,
            result_count=len(hits),
            request_id=request_id or None,
            endpoint_or_base_url=self.base_url,
            auth_present=True,
            request=req_payload,
            raw_payload_digest=_stable_digest(payload),
        )
        return hits, execution

    def _parse_payload(
        self,
        payload: Any,
        *,
        request: SearchRequest,
        request_id: Optional[str],
    ) -> List[SearchResult]:
        if not isinstance(payload, dict):
            return []
        raw_results = payload.get("results")
        if not isinstance(raw_results, list):
            return []
        hits: List[SearchResult] = []
        for entry in raw_results:
            if not isinstance(entry, dict):
                continue
            title = str(entry.get("title") or "untitled")
            url = str(entry.get("url") or "").strip()
            raw_content = entry.get("raw_content")
            content = entry.get("content")
            snippet = str(content or "").strip()
            if not snippet and isinstance(raw_content, str) and raw_content.strip():
                snippet = raw_content.strip()[:400]
            if not url or not snippet:
                continue
            score = entry.get("score")
            published = entry.get("published_date") or entry.get("published")
            hits.append(
                SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source="remote",
                    published=str(published) if published else None,
                    query=request.query,
                    provider=self.name,
                    score=float(score) if isinstance(score, (int, float)) else None,
                    raw_content=str(raw_content) if isinstance(raw_content, str) and raw_content else None,
                    request_id=request_id,
                )
            )
            if len(hits) >= request.limit:
                break
        return hits


__all__ = ["DEFAULT_TAVILY_BASE_URL", "TavilySearchProvider"]
