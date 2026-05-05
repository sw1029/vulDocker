from __future__ import annotations

import json
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


def test_web_search_tool_indexes_raw_cve_json_for_local_research(tmp_path: Path) -> None:
    corpus_root = tmp_path / "rag" / "corpus" / "raw" / "poc" / "20251108"
    corpus_root.mkdir(parents=True)
    (corpus_root / "cve-2099-0001.json").write_text(
        """
{
  "cve_id": "CVE-2099-0001",
  "title": "Demo product path traversal",
  "description": "Path traversal allows reading arbitrary files.",
  "link": "https://nvd.nist.gov/vuln/detail/CVE-2099-0001",
  "published": "2099-01-01",
  "source": "nvd",
  "tags": ["path traversal"]
}
""".strip(),
        encoding="utf-8",
    )

    tool = WebSearchTool()
    tool.local_root = tmp_path / "rag" / "corpus"

    hits = tool.search("CVE-2099-0001 exploit", policy="local_only")

    assert len(hits) == 1
    assert hits[0].title == "Demo product path traversal"
    assert hits[0].url == "https://nvd.nist.gov/vuln/detail/CVE-2099-0001"
    assert hits[0].published == "2099-01-01"
    assert "CVE: CVE-2099-0001" in hits[0].snippet
    assert "Path traversal allows reading arbitrary files." in hits[0].snippet


def test_web_search_tool_local_cve_query_requires_exact_identifier(tmp_path: Path) -> None:
    corpus_root = tmp_path / "rag" / "corpus" / "raw" / "poc" / "20251108"
    corpus_root.mkdir(parents=True)
    (corpus_root / "cve-2099-0001.json").write_text(
        """
{
  "cve_id": "CVE-2099-0001",
  "title": "Wrong NVD advisory",
  "description": "NVD advisory text for a different issue.",
  "link": "https://nvd.nist.gov/vuln/detail/CVE-2099-0001",
  "source": "nvd",
  "tags": ["advisory"]
}
""".strip(),
        encoding="utf-8",
    )
    (corpus_root / "cve-2099-0002.json").write_text(
        """
{
  "cve_id": "CVE-2099-0002",
  "title": "Target NVD advisory",
  "description": "NVD advisory text for the requested issue.",
  "link": "https://nvd.nist.gov/vuln/detail/CVE-2099-0002",
  "source": "nvd",
  "tags": ["advisory"]
}
""".strip(),
        encoding="utf-8",
    )

    tool = WebSearchTool()
    tool.local_root = tmp_path / "rag" / "corpus"

    hits = tool.search("CVE-2099-0002 NVD advisory affected versions weakness details", policy="local_only", limit=5)

    assert [hit.title for hit in hits] == ["Target NVD advisory"]


def test_web_search_tool_local_identifier_matches_filename_when_json_body_lacks_identifier(tmp_path: Path) -> None:
    corpus_root = tmp_path / "rag" / "corpus" / "raw" / "poc" / "20251108"
    corpus_root.mkdir(parents=True)
    (corpus_root / "cve-2099-0003.json").write_text(
        """
{
  "title": "Filename-only CVE advisory",
  "description": "The body omits the identifier but the cache filename carries it.",
  "source": "nvd"
}
""".strip(),
        encoding="utf-8",
    )

    tool = WebSearchTool()
    tool.local_root = tmp_path / "rag" / "corpus"

    hits = tool.search("CVE-2099-0003 NVD advisory", policy="local_only")

    assert len(hits) == 1
    assert hits[0].title == "Filename-only CVE advisory"


def test_web_search_tool_formats_nested_nvd_json_for_local_research(tmp_path: Path) -> None:
    corpus_root = tmp_path / "rag" / "corpus" / "raw" / "poc" / "20251108"
    corpus_root.mkdir(parents=True)
    (corpus_root / "cve-2099-0042.json").write_text(
        json.dumps(
            {
                "cve": {
                    "id": "CVE-2099-0042",
                    "descriptions": [
                        {"lang": "en", "value": "Reflected cross-site scripting in the demo search page."}
                    ],
                    "weaknesses": [
                        {"description": [{"lang": "en", "value": "CWE-79"}]}
                    ],
                    "references": {
                        "referenceData": [{"url": "https://vendor.example/advisory/CVE-2099-0042"}]
                    },
                    "published": "2099-02-03T00:00:00.000",
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    tool = WebSearchTool()
    tool.local_root = tmp_path / "rag" / "corpus"

    hits = tool.search("CVE-2099-0042 NVD advisory weakness details", policy="local_only")

    assert len(hits) == 1
    assert hits[0].title == "CVE-2099-0042"
    assert hits[0].url == "https://vendor.example/advisory/CVE-2099-0042"
    assert hits[0].published == "2099-02-03T00:00:00.000"
    assert "Description: Reflected cross-site scripting" in hits[0].snippet
    assert "Weaknesses: CWE-79" in hits[0].snippet
    assert "Source: nvd" in hits[0].snippet


def test_web_search_tool_selects_matching_record_from_nvd_vulnerabilities_array(tmp_path: Path) -> None:
    corpus_root = tmp_path / "rag" / "corpus" / "raw" / "poc" / "20251108"
    corpus_root.mkdir(parents=True)
    (corpus_root / "nvd-response.json").write_text(
        json.dumps(
            {
                "vulnerabilities": [
                    {
                        "cve": {
                            "id": "CVE-2099-0001",
                            "descriptions": [{"lang": "en", "value": "Wrong issue."}],
                            "weaknesses": [{"description": [{"lang": "en", "value": "CWE-89"}]}],
                        }
                    },
                    {
                        "cve": {
                            "id": "CVE-2099-0042",
                            "descriptions": [{"lang": "en", "value": "Requested XSS issue."}],
                            "weaknesses": [{"description": [{"lang": "en", "value": "CWE-79"}]}],
                            "references": [{"url": "https://nvd.nist.gov/vuln/detail/CVE-2099-0042"}],
                        }
                    },
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    tool = WebSearchTool()
    tool.local_root = tmp_path / "rag" / "corpus"

    hits = tool.search("CVE-2099-0042 NVD advisory weakness details", policy="local_only")

    assert len(hits) == 1
    assert hits[0].title == "CVE-2099-0042"
    assert hits[0].url == "https://nvd.nist.gov/vuln/detail/CVE-2099-0042"
    assert "Description: Requested XSS issue." in hits[0].snippet
    assert "Weaknesses: CWE-79" in hits[0].snippet
    assert "CVE-2099-0001" not in hits[0].snippet


def test_web_search_tool_remote_prefer_uses_backoff_after_first_remote_failure(monkeypatch, tmp_path: Path) -> None:
    corpus_root = tmp_path / "rag" / "corpus" / "processed"
    corpus_root.mkdir(parents=True)
    (corpus_root / "note.md").write_text("unknown cwe exploit note", encoding="utf-8")
    calls = {"count": 0}

    def _fake_remote(self, request):  # noqa: ANN001
        calls["count"] += 1
        return [], SearchExecution(
            provider="tavily",
            configured=True,
            error="temporary remote failure",
            degraded=False,
            request=request.to_payload(),
        )

    monkeypatch.setattr(WebSearchTool, "_remote_search", _fake_remote)

    tool = WebSearchTool(provider="tavily", api_key="token")
    tool.local_root = tmp_path / "rag" / "corpus"

    first = tool.search("unknown cwe", policy="remote_prefer")
    second = tool.search("unknown cwe", policy="remote_prefer")

    assert len(first) == 1
    assert len(second) == 1
    assert calls["count"] == 1
    execution = tool.last_execution()
    assert execution is not None
    assert execution.degraded is True
    assert execution.error == "temporary remote failure"


def test_web_search_tool_loads_tavily_key_from_config_loader(monkeypatch) -> None:
    monkeypatch.delenv("VUL_WEB_SEARCH_API_KEY", raising=False)
    monkeypatch.setattr("rag.tools.web_search.get_tavily_api_key", lambda: "ini-token")

    tool = WebSearchTool(provider="tavily")

    assert tool.api_key == "ini-token"


def test_web_search_tool_auto_selects_tavily_when_key_exists(monkeypatch) -> None:
    monkeypatch.delenv("VUL_WEB_SEARCH_PROVIDER", raising=False)
    monkeypatch.delenv("VUL_WEB_SEARCH_ENDPOINT", raising=False)
    monkeypatch.delenv("VUL_WEB_SEARCH_BASE_URL", raising=False)
    monkeypatch.delenv("VUL_WEB_SEARCH_API_KEY", raising=False)
    monkeypatch.setattr("rag.tools.web_search.get_tavily_api_key", lambda: "ini-token")

    tool = WebSearchTool()

    assert tool.provider_name == "tavily"
    assert tool.api_key == "ini-token"
    assert tool._build_remote_provider().__class__.__name__ == "TavilySearchProvider"


def test_web_search_tool_reads_timeout_from_env(monkeypatch) -> None:
    monkeypatch.setenv("VUL_WEB_SEARCH_TIMEOUT_S", "15.5")

    tool = WebSearchTool()

    assert tool.timeout == 15.5


def test_web_search_tool_propagates_filter_surface_to_request(monkeypatch) -> None:
    captured = {}

    def _fake_remote(self, request):  # noqa: ANN001
        captured["request"] = request.to_payload()
        return [], SearchExecution(
            provider="tavily",
            configured=True,
            result_count=0,
            request=request.to_payload(),
        )

    monkeypatch.setattr(WebSearchTool, "_remote_search", _fake_remote)

    tool = WebSearchTool(provider="tavily", api_key="token")
    tool.search_with_filters(
        "unknown cwe",
        policy="remote_required",
        include_domains=["mitre.org"],
        exclude_domains=["example.com"],
        time_range="30d",
        country="us",
        search_lang="en",
    )

    assert captured["request"]["include_domains"] == ["mitre.org"]
    assert captured["request"]["exclude_domains"] == ["example.com"]
    assert captured["request"]["time_range"] == "30d"
    assert captured["request"]["country"] == "us"
    assert captured["request"]["search_lang"] == "en"
