from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rag.tools import SearchRequest
from rag.tools.providers.custom import CustomSearchProvider


class _Response:
    def __init__(self, payload: list[dict], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> list[dict]:
        return self._payload


def test_custom_provider_propagates_search_filters(monkeypatch) -> None:
    captured: dict = {}

    def _fake_get(url, params, timeout):  # noqa: ANN001
        captured["url"] = url
        captured["params"] = params
        captured["timeout"] = timeout
        return _Response(
            [
                {
                    "title": "note",
                    "url": "https://example.com/search",
                    "snippet": "remote result",
                }
            ]
        )

    monkeypatch.setattr("rag.tools.providers.custom.requests.get", _fake_get)

    provider = CustomSearchProvider(endpoint="https://search.example/api")
    request = SearchRequest(
        query="unknown cwe",
        policy="remote_required",
        include_domains=["mitre.org"],
        exclude_domains=["example.com"],
        time_range="30d",
        country="us",
        search_lang="en",
    )

    hits, execution = provider.search(request)

    assert len(hits) == 1
    assert execution.configured is True
    assert captured["url"] == "https://search.example/api"
    assert captured["params"]["include_domains"] == ["mitre.org"]
    assert captured["params"]["exclude_domains"] == ["example.com"]
    assert captured["params"]["time_range"] == "30d"
    assert captured["params"]["country"] == "us"
    assert captured["params"]["search_lang"] == "en"
