from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rag.tools import SearchExecution, SearchResult, WebSearchTool


def test_web_search_tool_prefers_explicit_provider_over_endpoint_env(monkeypatch) -> None:
    monkeypatch.setenv("VUL_WEB_SEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("VUL_WEB_SEARCH_ENDPOINT", "https://custom.example/api")
    monkeypatch.setenv("VUL_WEB_SEARCH_API_KEY", "token")

    def _fake_remote(self, request):  # noqa: ANN001
        return [
            SearchResult(
                title="remote",
                url="https://example.com",
                snippet="snippet",
                source="remote",
                provider="tavily",
                query=request.query,
            )
        ], SearchExecution(
            provider="tavily",
            configured=True,
            result_count=1,
            request=request.to_payload(),
        )

    monkeypatch.setattr(WebSearchTool, "_remote_search", _fake_remote)

    tool = WebSearchTool()
    hits = tool.search("unknown cwe", policy="remote_required")

    assert len(hits) == 1
    execution = tool.last_execution()
    assert execution is not None
    assert execution.provider == "tavily"


def test_web_search_tool_remote_prefer_falls_back_to_local_when_remote_unavailable(monkeypatch, tmp_path: Path) -> None:
    corpus_root = tmp_path / "rag" / "corpus" / "processed"
    corpus_root.mkdir(parents=True)
    (corpus_root / "note.md").write_text("unknown cwe exploit note", encoding="utf-8")

    def _fake_remote(self, request):  # noqa: ANN001
        return [], SearchExecution(
            provider="tavily",
            configured=False,
            error="missing api key",
            degraded=False,
            request=request.to_payload(),
        )

    monkeypatch.setattr(WebSearchTool, "_remote_search", _fake_remote)

    tool = WebSearchTool()
    tool.local_root = tmp_path / "rag" / "corpus"
    hits = tool.search("unknown cwe", policy="remote_prefer")

    assert len(hits) == 1
    assert hits[0].source == "local"
    execution = tool.last_execution()
    assert execution is not None
    assert execution.provider == "tavily"
    assert execution.degraded is True
