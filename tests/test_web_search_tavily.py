from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rag.tools.providers.tavily import TavilySearchProvider
from rag.tools import SearchRequest


class _Response:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self._payload


def test_tavily_provider_normalizes_results(monkeypatch) -> None:
    captured: dict = {}

    def _fake_post(url, json, headers, timeout):  # noqa: ANN001
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _Response(
            {
                "request_id": "req-1",
                "results": [
                    {
                        "title": "CWE note",
                        "url": "https://example.com/cwe",
                        "content": "remote snippet",
                        "raw_content": "full remote content",
                        "score": 0.91,
                    }
                ],
            }
        )

    monkeypatch.setattr("rag.tools.providers.tavily.requests.post", _fake_post)

    provider = TavilySearchProvider(api_key="secret-key")
    request = SearchRequest(
        query="unknown cwe exploit",
        limit=2,
        policy="remote_required",
        include_domains=["mitre.org"],
        include_raw_content=True,
    )

    hits, execution = provider.search(request)

    assert len(hits) == 1
    assert hits[0].provider == "tavily"
    assert hits[0].source == "remote"
    assert hits[0].title == "CWE note"
    assert hits[0].snippet == "remote snippet"
    assert hits[0].raw_content == "full remote content"
    assert hits[0].request_id == "req-1"
    assert execution.provider == "tavily"
    assert execution.configured is True
    assert execution.request_id == "req-1"
    assert execution.result_count == 1
    assert execution.raw_payload_digest
    assert captured["url"] == "https://api.tavily.com/search"
    assert captured["json"]["query"] == "unknown cwe exploit"
    assert captured["json"]["max_results"] == 2
    assert captured["json"]["search_depth"] == "advanced"
    assert captured["json"]["include_domains"] == ["mitre.org"]
    assert captured["json"]["include_raw_content"] is True
    assert captured["headers"]["Authorization"] == "Bearer secret-key"


def test_tavily_provider_reports_missing_api_key() -> None:
    provider = TavilySearchProvider(api_key=None)
    hits, execution = provider.search(SearchRequest(query="unknown cwe", policy="remote_required"))

    assert hits == []
    assert execution.provider == "tavily"
    assert execution.configured is False
    assert execution.auth_present is False
    assert "VUL_WEB_SEARCH_API_KEY" in str(execution.error)
