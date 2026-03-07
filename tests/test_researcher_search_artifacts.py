from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.researcher.service import ResearcherService
from rag.tools import SearchExecution, SearchResult, WebSearchTool


class _Span:
    def __enter__(self):  # noqa: ANN204
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
        return False

    def event(self, *args, **kwargs) -> None:  # noqa: ANN001
        return None


class _ReactLoopStub:
    trace_id = "trace-test"
    failure_context = ""

    def queries_from_requirement(self, requirement):  # noqa: ANN001
        return ["unknown cwe exploit"]

    def span(self, **kwargs):  # noqa: ANN003, ANN001
        return _Span()

    def record_researcher_report(self, **kwargs) -> None:  # noqa: ANN003
        return None


class _SearchToolStub:
    provider_name = "tavily"
    endpoint = ""
    base_url = "https://api.tavily.com/search"

    def __init__(self, hits, execution):  # noqa: ANN001
        self._hits = hits
        self._execution = execution
        self.last_kwargs = {}

    def search_with_filters(self, query, limit=3, policy="remote_prefer", **kwargs):  # noqa: ANN001
        self.last_kwargs = {"query": query, "limit": limit, "policy": policy, **kwargs}
        for hit in self._hits:
            if not hit.query:
                hit.query = query
        return list(self._hits)

    def search(self, query, limit=3, policy="remote_prefer"):  # noqa: ANN001
        return self.search_with_filters(query, limit=limit, policy=policy)

    def last_execution(self):  # noqa: ANN204
        return self._execution


def _service_stub(
    tmp_path: Path,
    *,
    vuln_id: str,
    search_policy: str,
    require_evidence: bool,
    search_filters: dict | None = None,
) -> ResearcherService:
    researcher_cfg = {"search_policy": search_policy}
    if search_filters:
        researcher_cfg["search_filters"] = search_filters
    service = ResearcherService.__new__(ResearcherService)
    service.sid = "sid-search"
    service.bundle = None  # type: ignore[attr-defined]
    service.plan = {
        "requirement": {"vuln_id": vuln_id, "researcher": researcher_cfg},
        "policy": {"require_researcher_evidence": require_evidence},
        "paths": {"metadata": str(tmp_path)},
    }
    service.metadata_dir = tmp_path  # type: ignore[attr-defined]
    service.metadata_root = tmp_path  # type: ignore[attr-defined]
    service.runtime_rules_dir = tmp_path / "runtime_rules"  # type: ignore[attr-defined]
    service.runtime_templates_dir = tmp_path / "runtime_templates"  # type: ignore[attr-defined]
    service.requirement = {"vuln_id": vuln_id, "researcher": researcher_cfg}  # type: ignore[attr-defined]
    service.react_loop = _ReactLoopStub()  # type: ignore[attr-defined]
    service.search_limit = 3  # type: ignore[attr-defined]
    service._last_report = None  # type: ignore[attr-defined]
    service._last_guard_spec = None  # type: ignore[attr-defined]
    service._search_records = []  # type: ignore[attr-defined]
    service._search_health_path = None  # type: ignore[attr-defined]
    service._search_degraded = False  # type: ignore[attr-defined]
    service._last_evidence_relevance = None  # type: ignore[attr-defined]
    service.variation_manager = type("Variation", (), {"key": {"mode": "deterministic"}})()  # type: ignore[attr-defined]
    service._generate_report = lambda rag_context, search_hits: {"intent": "demo", "vuln_id": vuln_id}  # type: ignore[attr-defined]
    service._build_and_write_guard_spec = lambda report, evidence, bundle: (None, None)  # type: ignore[attr-defined]
    service._synthesize_candidates = lambda: {"rules": [], "templates": []}  # type: ignore[attr-defined]
    return service


def test_remote_required_failure_records_search_health_path(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("agents.researcher.service.load_static_context", lambda _snapshot: "")
    service = _service_stub(
        tmp_path,
        vuln_id="CWE-9999",
        search_policy="remote_required",
        require_evidence=True,
    )
    service.search_tool = _SearchToolStub(  # type: ignore[attr-defined]
        [],
        SearchExecution(
            provider="tavily",
            configured=False,
            error="missing api key",
            auth_present=False,
            endpoint_or_base_url="https://api.tavily.com/search",
            request={"query": "unknown cwe exploit"},
        ),
    )

    try:
        service.run()
    except RuntimeError as exc:
        message = str(exc)
    else:  # pragma: no cover - test expects failure
        raise AssertionError("service.run() unexpectedly succeeded")

    health_path = tmp_path / "search_health.json"
    report_path = tmp_path / "researcher_report.json"
    contract_path = tmp_path / "resolved_contract.json"
    assert health_path.exists()
    assert report_path.exists()
    assert contract_path.exists()
    assert "search_health.json" in message
    health = json.loads(health_path.read_text(encoding="utf-8"))
    assert health["provider"] == "tavily"
    assert health["configured"] is False
    assert "missing api key" in health["last_error"]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["search_health_path"] == str(health_path)
    assert report["resolved_contract_path"] == str(contract_path)


def test_remote_prefer_degraded_search_is_recorded_in_report(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("agents.researcher.service.load_static_context", lambda _snapshot: "")
    service = _service_stub(
        tmp_path,
        vuln_id="CWE-89",
        search_policy="remote_prefer",
        require_evidence=False,
    )
    service.search_tool = _SearchToolStub(  # type: ignore[attr-defined]
        [
            SearchResult(
                title="local note",
                url=str(tmp_path / "note.md"),
                snippet="sql injection note",
                source="local",
                provider="local",
            )
        ],
        SearchExecution(
            provider="tavily",
            configured=False,
            error="missing api key",
            degraded=True,
            auth_present=False,
            endpoint_or_base_url="https://api.tavily.com/search",
            request={"query": "unknown cwe exploit"},
        ),
    )

    path = service.run()

    report = json.loads(path.read_text(encoding="utf-8"))
    health = json.loads((tmp_path / "search_health.json").read_text(encoding="utf-8"))
    contract = json.loads((tmp_path / "resolved_contract.json").read_text(encoding="utf-8"))
    assert report["search_degraded"] is True
    assert report["search_health_path"] == str(tmp_path / "search_health.json")
    assert report["resolved_contract_path"] == str(tmp_path / "resolved_contract.json")
    assert health["degraded"] is True
    assert health["local_result_count"] == 1
    assert contract["contract_stage"] == "research_seed"


def test_success_report_canonicalizes_unknown_vuln_id(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("agents.researcher.service.load_static_context", lambda _snapshot: "")
    service = _service_stub(
        tmp_path,
        vuln_id="NAME-TEMPLATE-INJECTION",
        search_policy="remote_required",
        require_evidence=False,
    )
    service._evaluate_evidence_quality = lambda bundle, hits: ("sufficient", "sufficient evidence")  # type: ignore[attr-defined]
    service._generate_report = lambda rag_context, search_hits: {"intent": "demo", "vuln_id": "UNKNOWN"}  # type: ignore[attr-defined]
    service.search_tool = _SearchToolStub(  # type: ignore[attr-defined]
        [
            SearchResult(
                title="remote note",
                url="https://example.com/ssti",
                snippet="template injection note",
                source="remote",
                provider="tavily",
            )
        ],
        SearchExecution(
            provider="tavily",
            configured=True,
            result_count=1,
            request={"query": "unknown cwe exploit"},
        ),
    )

    path = service.run()

    report = json.loads(path.read_text(encoding="utf-8"))
    contract = json.loads((tmp_path / "resolved_contract.json").read_text(encoding="utf-8"))
    assert report["vuln_id"] == "NAME-TEMPLATE-INJECTION"
    assert contract["vuln_id"] == "NAME-TEMPLATE-INJECTION"


class _Response:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self._payload


def test_unknown_cwe_researcher_run_succeeds_with_mock_tavily(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("agents.researcher.service.load_static_context", lambda _snapshot: "")

    def _fake_post(url, json, headers, timeout):  # noqa: ANN001
        assert url == "https://api.tavily.com/search"
        assert json["search_depth"] == "advanced"
        return _Response(
            {
                "request_id": "req-search",
                "results": [
                    {
                        "title": "Flask SQLite SQL injection walkthrough",
                        "url": "https://example.com/cwe-9999",
                        "content": "SQL injection in a Flask app using sqlite request.args and cursor.execute with string concatenation",
                        "raw_content": "full writeup showing request.args, sqlite, cursor.execute, and OR 1=1 boolean-based SQL injection",
                        "score": 0.88,
                    }
                ],
            }
        )

    monkeypatch.setattr("rag.tools.providers.tavily.requests.post", _fake_post)

    service = _service_stub(
        tmp_path,
        vuln_id="CWE-9999",
        search_policy="remote_required",
        require_evidence=True,
    )
    service.requirement.update(  # type: ignore[attr-defined]
        {
            "pattern_id": "sqli-string-concat",
            "language": "python",
            "framework": "flask",
            "runtime": {"db": "sqlite"},
        }
    )
    service.search_tool = WebSearchTool(provider="tavily", api_key="token")  # type: ignore[attr-defined]

    path = service.run()

    report = json.loads(path.read_text(encoding="utf-8"))
    health = json.loads((tmp_path / "search_health.json").read_text(encoding="utf-8"))
    contract = json.loads((tmp_path / "resolved_contract.json").read_text(encoding="utf-8"))
    assert report["quality"] == "sufficient"
    assert report["search_degraded"] is False
    assert report["evidence"][0]["source"] == "remote"
    assert report["resolved_contract_path"] == str(tmp_path / "resolved_contract.json")
    assert health["configured"] is True
    assert health["remote_result_count"] == 1
    assert contract["contract_stage"] == "research_seed"


def test_search_filters_are_propagated_to_request_payload(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("agents.researcher.service.load_static_context", lambda _snapshot: "")
    filters = {
        "include_domains": ["mitre.org", "owasp.org"],
        "exclude_domains": ["example.com"],
        "time_range": "30d",
        "country": "us",
        "search_lang": "en",
    }
    service = _service_stub(
        tmp_path,
        vuln_id="CWE-9999",
        search_policy="remote_required",
        require_evidence=True,
        search_filters=filters,
    )
    service._evaluate_evidence_quality = lambda bundle, hits: ("sufficient", "sufficient evidence")  # type: ignore[attr-defined]
    search_tool = _SearchToolStub(
        [
            SearchResult(
                title="remote note",
                url="https://mitre.org/demo",
                snippet="remote snippet",
                source="remote",
                provider="tavily",
            )
        ],
        SearchExecution(
            provider="tavily",
            configured=True,
            result_count=1,
            request={
                "query": "unknown cwe exploit",
                "limit": 3,
                "policy": "remote_required",
                "include_domains": ["mitre.org", "owasp.org"],
                "exclude_domains": ["example.com"],
                "time_range": "30d",
                "country": "us",
                "search_lang": "en",
            },
        ),
    )
    service.search_tool = search_tool  # type: ignore[attr-defined]

    path = service.run()

    report = json.loads(path.read_text(encoding="utf-8"))
    health = json.loads((tmp_path / "search_health.json").read_text(encoding="utf-8"))
    trace_files = sorted((tmp_path / "search_traces").glob("*.json"))
    assert search_tool.last_kwargs["include_domains"] == ["mitre.org", "owasp.org"]
    assert search_tool.last_kwargs["exclude_domains"] == ["example.com"]
    assert search_tool.last_kwargs["time_range"] == "30d"
    assert search_tool.last_kwargs["country"] == "us"
    assert search_tool.last_kwargs["search_lang"] == "en"
    assert report["search_policy"] == "remote_required"
    assert health["policy"] == "remote_required"
    assert trace_files, "search trace was not written"
    trace = json.loads(trace_files[0].read_text(encoding="utf-8"))
    assert trace["request"]["include_domains"] == ["mitre.org", "owasp.org"]
    assert trace["request"]["exclude_domains"] == ["example.com"]
    assert trace["request"]["time_range"] == "30d"
