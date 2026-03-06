from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rag.tools import SearchRequest
from rag.tools.providers.custom import CustomSearchProvider


class _Response:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self._payload


def test_custom_provider_parses_legacy_payload(monkeypatch) -> None:
    def _fake_get(url, params, timeout):  # noqa: ANN001
        assert url == "https://search.example/api"
        assert params == {"q": "unknown cwe exploit", "size": 2}
        return _Response(
            {
                "items": [
                    {
                        "name": "Legacy result",
                        "link": "https://example.com/legacy",
                        "body": "legacy snippet",
                    }
                ]
            }
        )

    monkeypatch.setattr("rag.tools.providers.custom.requests.get", _fake_get)

    provider = CustomSearchProvider(endpoint="https://search.example/api")
    hits, execution = provider.search(SearchRequest(query="unknown cwe exploit", limit=2))

    assert len(hits) == 1
    assert hits[0].provider == "custom"
    assert hits[0].title == "Legacy result"
    assert hits[0].url == "https://example.com/legacy"
    assert hits[0].snippet == "legacy snippet"
    assert execution.provider == "custom"
    assert execution.configured is True
    assert execution.result_count == 1


def test_custom_provider_reports_missing_endpoint() -> None:
    provider = CustomSearchProvider(endpoint=None)
    hits, execution = provider.search(SearchRequest(query="unknown cwe"))

    assert hits == []
    assert execution.provider == "custom"
    assert execution.configured is False
    assert "VUL_WEB_SEARCH_ENDPOINT" in str(execution.error)
