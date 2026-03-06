"""Provider interfaces and normalized request/response types for search."""
from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple


def _stable_digest(payload: Any) -> Optional[str]:
    try:
        serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    except Exception:
        return None
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass
class SearchRequest:
    query: str
    limit: int = 3
    policy: str = "remote_prefer"
    include_domains: List[str] = field(default_factory=list)
    exclude_domains: List[str] = field(default_factory=list)
    time_range: Optional[str] = None
    country: Optional[str] = None
    search_lang: Optional[str] = None
    include_raw_content: bool = False

    def to_payload(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["include_domains"] = list(self.include_domains)
        payload["exclude_domains"] = list(self.exclude_domains)
        return payload


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str = "local"
    published: Optional[str] = None
    query: Optional[str] = None
    retrieved_at: Optional[str] = None
    provider: Optional[str] = None
    score: Optional[float] = None
    raw_content: Optional[str] = None
    request_id: Optional[str] = None

    def to_payload(self, *, include_raw_content: bool = False) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source,
        }
        if self.published:
            payload["published"] = self.published
        if self.query:
            payload["query"] = self.query
        if self.retrieved_at:
            payload["retrieved_at"] = self.retrieved_at
        if self.provider:
            payload["provider"] = self.provider
        if self.score is not None:
            payload["score"] = self.score
        if self.request_id:
            payload["request_id"] = self.request_id
        if include_raw_content and self.raw_content:
            payload["raw_content"] = self.raw_content
        return payload


@dataclass
class SearchExecution:
    provider: str
    configured: bool
    status_code: Optional[int] = None
    latency_ms: Optional[int] = None
    result_count: int = 0
    error: Optional[str] = None
    request_id: Optional[str] = None
    degraded: bool = False
    endpoint_or_base_url: Optional[str] = None
    auth_present: Optional[bool] = None
    request: Dict[str, Any] = field(default_factory=dict)
    raw_payload_digest: Optional[str] = None

    def to_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "provider": self.provider,
            "configured": self.configured,
            "status_code": self.status_code,
            "latency_ms": self.latency_ms,
            "result_count": self.result_count,
            "error": self.error,
            "request_id": self.request_id,
            "degraded": self.degraded,
            "endpoint_or_base_url": self.endpoint_or_base_url,
            "auth_present": self.auth_present,
            "request": dict(self.request),
            "raw_payload_digest": self.raw_payload_digest,
        }
        return payload

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "SearchExecution":
        return cls(
            provider=str(payload.get("provider") or ""),
            configured=bool(payload.get("configured", False)),
            status_code=payload.get("status_code"),
            latency_ms=payload.get("latency_ms"),
            result_count=int(payload.get("result_count", 0) or 0),
            error=payload.get("error"),
            request_id=payload.get("request_id"),
            degraded=bool(payload.get("degraded", False)),
            endpoint_or_base_url=payload.get("endpoint_or_base_url"),
            auth_present=payload.get("auth_present"),
            request=payload.get("request") if isinstance(payload.get("request"), dict) else {},
            raw_payload_digest=payload.get("raw_payload_digest"),
        )


class SearchProvider(ABC):
    name: str

    @abstractmethod
    def search(self, request: SearchRequest) -> Tuple[List[SearchResult], SearchExecution]:
        raise NotImplementedError


__all__ = [
    "SearchExecution",
    "SearchProvider",
    "SearchRequest",
    "SearchResult",
    "_stable_digest",
]
