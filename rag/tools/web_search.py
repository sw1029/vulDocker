"""Fallback-friendly search facade consumed by the Researcher agent."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple

from common.config import get_tavily_api_key
from common.logging import get_logger
from common.paths import get_repo_root

from .providers import (
    CustomSearchProvider,
    DEFAULT_TAVILY_BASE_URL,
    SearchExecution,
    SearchProvider,
    SearchRequest,
    SearchResult,
    TavilySearchProvider,
)

LOGGER = get_logger(__name__)


def _safe_timeout_seconds(value: object, default: float) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        return float(default)
    if timeout <= 0:
        return float(default)
    return timeout


class WebSearchTool:
    """Hybrid search helper that prefers remote APIs but falls back to local corpus."""

    def __init__(
        self,
        *,
        provider: Optional[str] = None,
        endpoint: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 8.0,
        max_local_files: int = 300,
    ) -> None:
        self.provider_name = (provider or os.environ.get("VUL_WEB_SEARCH_PROVIDER") or "").strip().lower()
        self.endpoint = (endpoint or os.environ.get("VUL_WEB_SEARCH_ENDPOINT") or "").strip()
        self.base_url = (base_url or os.environ.get("VUL_WEB_SEARCH_BASE_URL") or "").strip()
        explicit_api_key = (api_key or os.environ.get("VUL_WEB_SEARCH_API_KEY") or "").strip()
        config_tavily_key = get_tavily_api_key() or ""
        if not self.provider_name and not self.endpoint and (explicit_api_key or config_tavily_key):
            self.provider_name = "tavily"
        resolved_api_key = explicit_api_key
        if not resolved_api_key and self.provider_name == "tavily":
            resolved_api_key = config_tavily_key
        self.api_key = resolved_api_key
        env_timeout = os.environ.get("VUL_WEB_SEARCH_TIMEOUT_S")
        self.timeout = _safe_timeout_seconds(env_timeout, timeout) if env_timeout is not None else float(timeout)
        self.max_local_files = max_local_files
        self.local_root = get_repo_root() / "rag" / "corpus"
        self._last_execution: Optional[SearchExecution] = None
        self._remote_backoff_reason: str = ""
        self._remote_backoff_provider: str = ""

    def search(self, query: str, limit: int = 3, policy: str = "remote_prefer") -> List[SearchResult]:
        """Return up to ``limit`` results for a query."""
        return self.search_with_filters(query, limit=limit, policy=policy)

    def search_with_filters(
        self,
        query: str,
        *,
        limit: int = 3,
        policy: str = "remote_prefer",
        include_domains: Optional[Iterable[str]] = None,
        exclude_domains: Optional[Iterable[str]] = None,
        time_range: Optional[str] = None,
        country: Optional[str] = None,
        search_lang: Optional[str] = None,
    ) -> List[SearchResult]:
        """Return up to ``limit`` results for a query with optional filter surface."""

        query = (query or "").strip()
        if not query:
            self._last_execution = None
            return []
        policy = (policy or "remote_prefer").strip().lower()
        if policy not in {"remote_required", "remote_prefer", "local_only"}:
            policy = "remote_prefer"

        request = SearchRequest(
            query=query,
            limit=max(1, int(limit)),
            policy=policy,
            include_domains=self._normalize_string_list(include_domains),
            exclude_domains=self._normalize_string_list(exclude_domains),
            time_range=self._normalize_optional_string(time_range),
            country=self._normalize_optional_string(country),
            search_lang=self._normalize_optional_string(search_lang),
            include_raw_content=(policy == "remote_required"),
        )

        if policy == "local_only":
            local_hits = self._annotate_hits(self._local_search(query, limit), query)
            self._last_execution = SearchExecution(
                provider="local",
                configured=True,
                result_count=len(local_hits),
                degraded=False,
                request=request.to_payload(),
            )
            return local_hits

        if policy == "remote_prefer" and self._remote_backoff_reason:
            local_hits = self._annotate_hits(self._local_search(query, limit), query)
            provider_name = self._remote_backoff_provider or self.provider_name or ("custom" if self.endpoint else "none")
            self._last_execution = SearchExecution(
                provider=provider_name,
                configured=bool(self._build_remote_provider()),
                result_count=len(local_hits),
                degraded=True,
                error=self._remote_backoff_reason,
                endpoint_or_base_url=self.endpoint or self.base_url or None,
                auth_present=bool(self.api_key) if provider_name == "tavily" else None,
                request=request.to_payload(),
            )
            return local_hits

        remote_hits, execution = self._remote_search(request)
        remote_hits = self._annotate_hits(remote_hits, query)
        if policy == "remote_required":
            self._last_execution = execution
            return remote_hits

        if remote_hits:
            self._remote_backoff_reason = ""
            self._remote_backoff_provider = ""
            self._last_execution = execution
            return remote_hits

        local_hits = self._annotate_hits(self._local_search(query, limit), query)
        execution.result_count = len(local_hits)
        if execution.error or not execution.configured:
            execution.degraded = True
            if execution.error:
                self._remote_backoff_reason = str(execution.error)
                self._remote_backoff_provider = str(execution.provider or self.provider_name or "")
            elif not execution.configured:
                self._remote_backoff_reason = self._remote_provider_error(
                    self.provider_name or ("custom" if self.endpoint else "none")
                )
                self._remote_backoff_provider = str(execution.provider or self.provider_name or "")
        self._last_execution = execution
        return local_hits

    def last_execution(self) -> Optional[SearchExecution]:
        return self._last_execution

    def remote_capability(self) -> SearchExecution:
        """Return local remote-search capability status without issuing a network request."""

        provider_name = self.provider_name or ("custom" if self.endpoint else "none")
        endpoint_or_base_url = self.endpoint or self.base_url or None
        auth_present = bool(self.api_key) if provider_name == "tavily" else None

        if provider_name == "tavily":
            endpoint_or_base_url = self.base_url or DEFAULT_TAVILY_BASE_URL
            if not self.api_key:
                return SearchExecution(
                    provider=provider_name,
                    configured=False,
                    error=self._remote_provider_error(provider_name),
                    endpoint_or_base_url=endpoint_or_base_url,
                    auth_present=False,
                    request={},
                )
        elif provider_name == "custom" and not self.endpoint:
            return SearchExecution(
                provider=provider_name,
                configured=False,
                error=self._remote_provider_error(provider_name),
                endpoint_or_base_url=None,
                auth_present=None,
                request={},
            )

        provider = self._build_remote_provider()
        if provider is None:
            return SearchExecution(
                provider=provider_name,
                configured=False,
                error=self._remote_provider_error(provider_name),
                endpoint_or_base_url=endpoint_or_base_url,
                auth_present=auth_present,
                request={},
            )

        return SearchExecution(
            provider=getattr(provider, "name", "") or provider_name,
            configured=True,
            endpoint_or_base_url=endpoint_or_base_url,
            auth_present=auth_present,
            request={},
        )

    @staticmethod
    def _annotate_hits(hits: List[SearchResult], query: str) -> List[SearchResult]:
        retrieved_at = datetime.now(timezone.utc).isoformat()
        for hit in hits:
            if not hit.query:
                hit.query = query
            if not hit.retrieved_at:
                hit.retrieved_at = retrieved_at
        return hits

    @staticmethod
    def _normalize_string_list(values: Optional[Iterable[str]]) -> List[str]:
        if values is None:
            return []
        normalized: List[str] = []
        for value in values:
            if not isinstance(value, str):
                continue
            token = value.strip()
            if token and token not in normalized:
                normalized.append(token)
        return normalized

    @staticmethod
    def _normalize_optional_string(value: Optional[str]) -> Optional[str]:
        if not isinstance(value, str):
            return None
        token = value.strip()
        return token or None

    # Remote search helpers -------------------------------------------------

    def _remote_search(self, request: SearchRequest) -> Tuple[List[SearchResult], SearchExecution]:
        provider = self._build_remote_provider()
        if provider is None:
            provider_name = self.provider_name or ("custom" if self.endpoint else "none")
            execution = SearchExecution(
                provider=provider_name,
                configured=False,
                error=self._remote_provider_error(provider_name),
                endpoint_or_base_url=self.endpoint or self.base_url or None,
                auth_present=bool(self.api_key) if provider_name == "tavily" else None,
                request=request.to_payload(),
            )
            if request.policy == "remote_required":
                LOGGER.warning(execution.error)
            return [], execution
        return provider.search(request)

    def _build_remote_provider(self) -> Optional[SearchProvider]:
        provider_name = self.provider_name
        if provider_name:
            if provider_name == "custom":
                return CustomSearchProvider(endpoint=self.endpoint, timeout=self.timeout)
            if provider_name == "tavily":
                base_url = self.base_url or None
                return TavilySearchProvider(base_url=base_url, api_key=self.api_key or None, timeout=self.timeout)
            return None
        if self.endpoint:
            return CustomSearchProvider(endpoint=self.endpoint, timeout=self.timeout)
        return None

    def _remote_provider_error(self, provider_name: str) -> str:
        if provider_name == "tavily":
            if not self.api_key:
                return "search_policy requires Tavily remote search, but VUL_WEB_SEARCH_API_KEY is not configured"
            return "search_policy requires Tavily remote search, but provider setup is incomplete"
        if provider_name == "custom":
            return "search_policy requires remote search, but VUL_WEB_SEARCH_ENDPOINT is not configured"
        if provider_name in {"brave", "searxng"}:
            return f"search provider '{provider_name}' is not implemented in this release"
        return "search_policy requires remote search, but no remote provider is configured"

    # Local search helpers --------------------------------------------------

    def _local_search(self, query: str, limit: int) -> List[SearchResult]:
        tokens = [token for token in query.lower().split() if token]
        identifiers = _explicit_vuln_identifiers(query)
        candidates: List[Tuple[int, str, SearchResult]] = []
        for path in self._iter_local_files():
            try:
                text = path.read_text(encoding="utf-8")
            except Exception as exc:  # pragma: no cover - IO guard
                LOGGER.debug("Skipping %s due to read error: %s", path, exc)
                continue
            haystack = f"{path.name}\n{text}".lower()
            identifier_matches = sum(1 for identifier in identifiers if identifier in haystack)
            if identifiers and not identifier_matches:
                continue
            token_matches = sum(1 for token in tokens if token in haystack)
            if not identifiers and tokens and token_matches == 0:
                continue
            score = (identifier_matches * 100) + token_matches
            candidates.append((score, str(path), self._local_file_result(path, text, identifiers=identifiers)))
        candidates.sort(key=lambda item: (-item[0], item[1]))
        return [hit for _score, _path, hit in candidates[:limit]]

    def _iter_local_files(self) -> Iterable[Path]:
        if not self.local_root.exists():
            return []
        yielded = 0
        for section in ("processed", "raw"):
            base = self.local_root / section
            if not base.exists():
                continue
            for pattern in ("*.md", "*.txt", "*.json"):
                for path in sorted(base.rglob(pattern)):
                    yield path
                    yielded += 1
                    if yielded >= self.max_local_files:
                        return

    @staticmethod
    def _local_file_result(path: Path, text: str, *, identifiers: Optional[List[str]] = None) -> SearchResult:
        if path.suffix.lower() != ".json":
            snippet = " ".join(text.strip().split()) or "(empty content)"
            return SearchResult(
                title=path.name,
                url=str(path),
                snippet=snippet[:400],
                source="local",
                provider="local",
                raw_content=text,
            )

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        cve_record = _cve_record_payload(payload, identifiers=identifiers or [])
        if not cve_record and any(key in payload for key in ("id", "CVE_data_meta", "descriptions", "weaknesses", "problemtype", "references")):
            cve_record = payload
        cve_id = _json_text(payload, "cve_id", "cveID", "cveId") or _nested_json_text(
            cve_record,
            ("id",),
            ("CVE_data_meta", "ID"),
            ("cveMetadata", "cveId"),
        )
        title = _json_text(payload, "title", "vulnerabilityName") or cve_id or path.name
        description = (
            _json_text(payload, "description", "shortDescription")
            or _localized_json_text(cve_record.get("descriptions"))
            or _localized_json_text(_nested_json_value(cve_record, ("description", "description_data")))
        )
        link = (
            _json_text(payload, "link", "url", "references")
            or _reference_url_from_payload(cve_record)
            or str(path)
        )
        published = (
            _json_text(payload, "published", "dateAdded", "publicationDate")
            or _nested_json_text(cve_record, ("published",), ("publishedDate",))
            or _json_text(payload, "publishedDate")
        )
        source = _json_text(payload, "source") or ("nvd" if cve_record else "")
        weakness_text = _weakness_text_from_payload(cve_record)
        tags = payload.get("tags")
        tag_text = ""
        if isinstance(tags, list):
            tag_text = ", ".join(str(item).strip() for item in tags if str(item).strip())
        elif isinstance(tags, str):
            tag_text = tags.strip()
        parts = [
            f"CVE: {cve_id}" if cve_id else "",
            f"Title: {title}" if title else "",
            f"Description: {description}" if description else "",
            f"Weaknesses: {weakness_text}" if weakness_text else "",
            f"Source: {source}" if source else "",
            f"Tags: {tag_text}" if tag_text else "",
        ]
        snippet = " ".join(part for part in parts if part).strip()
        if not snippet:
            snippet = " ".join(text.strip().split()) or "(empty content)"
        raw_content = text
        if cve_record:
            try:
                raw_content = json.dumps(cve_record, indent=2, ensure_ascii=False)
            except TypeError:
                raw_content = text
        return SearchResult(
            title=title,
            url=link,
            snippet=snippet[:400],
            source="local",
            provider="local",
            published=published or None,
            raw_content=raw_content,
        )


def _json_text(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _cve_record_payload(payload: dict[str, Any], *, identifiers: List[str] | None = None) -> dict[str, Any]:
    identifiers = [str(item or "").strip().lower() for item in (identifiers or []) if str(item or "").strip()]
    cve_identifiers = [item for item in identifiers if item.startswith("cve-")]
    cwe_identifiers = [item for item in identifiers if item.startswith("cwe-")]
    records = _cve_record_payloads(payload)
    if records:
        for record in records:
            cve_id = _nested_json_text(record, ("id",), ("CVE_data_meta", "ID"), ("cveMetadata", "cveId")).lower()
            if cve_id and cve_id in cve_identifiers:
                return record
        for record in records:
            weakness_text = _weakness_text_from_payload(record).lower()
            if weakness_text and any(identifier in weakness_text for identifier in cwe_identifiers):
                return record
        return records[0]
    return {}


def _cve_record_payloads(payload: dict[str, Any]) -> List[dict[str, Any]]:
    cve = payload.get("cve")
    if isinstance(cve, dict):
        record = dict(cve)
        if "cveMetadata" not in record and isinstance(payload.get("cveMetadata"), dict):
            record["cveMetadata"] = payload["cveMetadata"]
        return [record]
    vulnerabilities = payload.get("vulnerabilities")
    records: List[dict[str, Any]] = []
    if isinstance(vulnerabilities, list):
        for item in vulnerabilities:
            if not isinstance(item, dict):
                continue
            records.extend(_cve_record_payloads(item))
    return records


def _nested_json_value(payload: dict[str, Any], path: Tuple[str, ...]) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _nested_json_text(payload: dict[str, Any], *paths: Tuple[str, ...]) -> str:
    for path in paths:
        value = _nested_json_value(payload, path)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _localized_json_text(values: Any) -> str:
    if not isinstance(values, list):
        return ""
    fallback = ""
    for item in values:
        if not isinstance(item, dict):
            continue
        value = str(item.get("value") or "").strip()
        if not value:
            continue
        if not fallback:
            fallback = value
        if str(item.get("lang") or "").strip().lower() in {"en", "eng"}:
            return value
    return fallback


def _reference_url_from_payload(payload: dict[str, Any]) -> str:
    references = payload.get("references")
    if isinstance(references, dict):
        reference_data = references.get("referenceData")
    else:
        reference_data = references
    if not isinstance(reference_data, list):
        return ""
    for item in reference_data:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if url:
            return url
    return ""


def _weakness_text_from_payload(payload: dict[str, Any]) -> str:
    values: List[str] = []
    weaknesses = payload.get("weaknesses")
    if isinstance(weaknesses, list):
        for entry in weaknesses:
            if not isinstance(entry, dict):
                continue
            text = _localized_json_text(entry.get("description"))
            if text and text not in values:
                values.append(text)
    problemtype_data = _nested_json_value(payload, ("problemtype", "problemtype_data"))
    if isinstance(problemtype_data, list):
        for entry in problemtype_data:
            if not isinstance(entry, dict):
                continue
            text = _localized_json_text(entry.get("description"))
            if text and text not in values:
                values.append(text)
    return ", ".join(values)


def _explicit_vuln_identifiers(value: str) -> List[str]:
    text = str(value or "").lower()
    identifiers: List[str] = []
    for pattern in (r"\bcve-\d{4}-\d+\b", r"\bcwe-\d+\b"):
        for match in re.finditer(pattern, text):
            token = match.group(0)
            if token not in identifiers:
                identifiers.append(token)
    return identifiers


__all__ = ["SearchExecution", "SearchRequest", "SearchResult", "WebSearchTool"]
