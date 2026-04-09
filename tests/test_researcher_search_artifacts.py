from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.researcher.service import ResearcherService
from common.config import DecodingProfile
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

    def query_plan_from_requirement(self, requirement, *, limit=3):  # noqa: ANN001
        return {
            "request_label": str(requirement.get("vuln_id") or ""),
            "family_hypotheses": [],
            "exploit_hypotheses": [],
            "queries": [
                {
                    "query": "unknown cwe exploit",
                    "evidence_type": "writeup",
                    "rationale": "stub",
                    "priority": 1,
                    "family": "",
                }
            ][:limit],
        }

    def span(self, **kwargs):  # noqa: ANN003, ANN001
        return _Span()

    def rank_family_hypotheses(self, search_results, *, base_hypotheses=None, limit=4):  # noqa: ANN001
        return {
            "ranked_families": [],
            "top_family": None,
            "top_confidence": None,
            "contradiction_count": 0,
            "contradictory_families": [],
        }

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
        self.call_count = 0

    def search_with_filters(self, query, limit=3, policy="remote_prefer", **kwargs):  # noqa: ANN001
        self.call_count += 1
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


class _LLMStub:
    def __init__(self) -> None:
        self.model_name = "gpt-5.4"
        self.decoding = DecodingProfile(mode="deterministic", temperature=0.0, top_p=1.0)
        self.observed_provider_attempted = False
        self.observed_provider_succeeded = False
        self.observed_stub_fallback = False
        self.observed_fixture_used = False
        self.last_error_class = None
        self.last_error_message = None
        self.last_error_retryable = None
        self.last_fixture_path = None
        self.use_stub = False
        self._fallback_on_error = True
        self.configured_cost_budget_usd = 0.25
        self._last_usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        self._observed_usage_totals = {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}


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
    assert report["query_plan"]["queries"][0]["query"] == "unknown cwe exploit"
    assert report["evidence_type_summary"]["hit_count"] == 0
    assert report["family_hypothesis_summary"]["top_family"] is None


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
    assert report["query_plan"]["queries"][0]["evidence_type"] == "writeup"
    assert report["evidence_type_summary"]["hit_count"] == 1
    assert report["family_hypothesis_summary"]["top_family"] is None
    assert health["degraded"] is True
    assert health["local_result_count"] == 1
    assert contract["contract_stage"] == "research_seed"


def test_name_only_dynamic_service_expands_query_plan_limit_for_stack_exploration(tmp_path: Path) -> None:
    service = _service_stub(
        tmp_path,
        vuln_id="NAME-OPEN-REDIRECT",
        search_policy="remote_prefer",
        require_evidence=False,
    )
    service.requirement.update(  # type: ignore[attr-defined]
        {
            "policy": {"name_only_mode": "dynamic"},
            "request_identity": {"name_driven": True},
            "stack_hypotheses": [
                {"language": "python", "framework": "flask"},
                {"language": "python", "framework": "fastapi"},
            ],
        }
    )
    service.plan["policy"]["name_only_mode"] = "dynamic"  # type: ignore[index]

    assert service._effective_query_plan_limit() == 4  # type: ignore[attr-defined]


def test_evidence_graph_adds_family_and_stack_support_edges(tmp_path: Path) -> None:
    service = _service_stub(
        tmp_path,
        vuln_id="CWE-89",
        search_policy="remote_prefer",
        require_evidence=False,
    )
    service.requirement = {  # type: ignore[attr-defined]
        "vuln_id": "CWE-89",
        "vuln_name": "SQL Injection",
        "language": "python",
        "framework": "flask",
    }
    query_plan = {
        "request_label": "SQL Injection",
        "queries": [
            {
                "query": "SQL Injection exploit writeup poc python flask",
                "evidence_type": "writeup",
                "priority": 10,
                "family": "sqli",
            },
            {
                "query": "SQL Injection vulnerable example python/flask",
                "evidence_type": "stack_anchor",
                "priority": 9,
                "family": "",
            },
        ],
    }
    graph = service._build_evidence_graph(  # type: ignore[attr-defined]
        search_hits=[
            SearchResult(
                title="SQL injection writeup",
                url="https://example.test/sqli",
                snippet="Flask login vulnerable to SQL injection with OR 1=1",
                source="remote",
                query="SQL Injection exploit writeup poc python flask",
            ),
            SearchResult(
                title="Flask vulnerable example",
                url="https://example.test/flask",
                snippet="python/flask demo app",
                source="remote",
                query="SQL Injection vulnerable example python/flask",
            ),
        ],
        query_plan=query_plan,
        tech_stack_candidates=[
            {
                "language": "python",
                "framework": "flask",
                "stack_id": "python/flask",
                "confidence": "medium",
                "score": 0.5,
            }
        ],
        family_hypothesis_summary={
            "ranked_families": [
                {
                    "family": "sqli",
                    "confidence": "high",
                    "score": 0.83,
                    "matched_aliases": ["sql injection", "sqli"],
                    "matched_anchors": ["or 1=1"],
                }
            ]
        },
    )

    edges = graph["edges"]
    assert {"from": "evidence:1", "to": "family:sqli", "kind": "supports_family_hypothesis"} in edges
    assert {"from": "evidence:1", "to": "stack:python/flask", "kind": "supports_stack_hypothesis"} in edges
    assert {"from": "evidence:2", "to": "stack:python/flask", "kind": "supports_stack_hypothesis"} in edges


def test_evidence_graph_preserves_negative_family_hypotheses_from_query_plan(tmp_path: Path) -> None:
    service = _service_stub(
        tmp_path,
        vuln_id="CWE-79",
        search_policy="remote_prefer",
        require_evidence=False,
    )
    query_plan = {
        "request_label": "Reflected XSS",
        "queries": [
            {
                "query": "Reflected XSS server-side template injection contrast indicators render_template_string jinja2 python/flask",
                "evidence_type": "contradiction_check",
                "priority": 6,
                "family": "template_injection",
                "negative_family": True,
            }
        ],
        "negative_family_hypotheses": [
            {"family": "template_injection", "source": "researcher_contradiction"}
        ],
    }

    graph = service._build_evidence_graph(  # type: ignore[attr-defined]
        search_hits=[
            SearchResult(
                title="Template injection contrast note",
                url="https://example.test/ssti",
                snippet="render_template_string and jinja2 indicate server-side template injection, not reflected XSS",
                source="remote",
                query="Reflected XSS server-side template injection contrast indicators render_template_string jinja2 python/flask",
            )
        ],
        query_plan=query_plan,
        tech_stack_candidates=[],
        family_hypothesis_summary={"ranked_families": []},
    )

    edges = graph["edges"]
    nodes = graph["nodes"]
    assert {"from": "request", "to": "family:template_injection", "kind": "negative_family_hypothesis"} in edges
    assert {"from": "evidence:1", "to": "family:template_injection", "kind": "supports_negative_family_hypothesis"} in edges
    assert any(
        node.get("id") == "family:template_injection" and node.get("kind") == "family_hypothesis"
        for node in nodes
    )


def test_researcher_infers_tech_stack_candidates_from_stack_anchor_hits(tmp_path: Path) -> None:
    service = _service_stub(
        tmp_path,
        vuln_id="NAME-OPEN-REDIRECT",
        search_policy="remote_prefer",
        require_evidence=False,
    )
    query_plan = {
        "stack_hypotheses": [
            {"language": "python", "framework": "flask", "source": "profile_prior", "confidence": "low"},
            {"language": "python", "framework": "fastapi", "source": "available_skeleton", "confidence": "low"},
        ],
        "queries": [
            {
                "query": "Open Redirect vulnerable example python/fastapi",
                "evidence_type": "stack_anchor",
            }
        ],
    }
    service._query_plan_index = {  # type: ignore[attr-defined]
        "Open Redirect vulnerable example python/fastapi": {
            "query": "Open Redirect vulnerable example python/fastapi",
            "evidence_type": "stack_anchor",
        }
    }

    candidates = service._infer_tech_stack_candidates(  # type: ignore[attr-defined]
        [
            SearchResult(
                title="FastAPI open redirect vulnerable example",
                url="https://example.com/fastapi-open-redirect",
                snippet="FastAPI RedirectResponse vulnerable example with open redirect sink",
                source="remote",
                provider="tavily",
                query="Open Redirect vulnerable example python/fastapi",
            )
        ],
        query_plan,
    )

    assert candidates[0]["stack_id"] == "python/fastapi"
    assert candidates[0]["confidence"] in {"medium", "high"}
    assert "stack_anchor_query" in candidates[0]["sources"]


def test_evidence_payload_and_summary_surface_source_authority(tmp_path: Path) -> None:
    service = _service_stub(
        tmp_path,
        vuln_id="CWE-89",
        search_policy="remote_prefer",
        require_evidence=False,
    )
    service._query_plan_index = {  # type: ignore[attr-defined]
        "OWASP SQL injection advisory": {"query": "OWASP SQL injection advisory", "evidence_type": "advisory"},
        "GitHub SQLi vulnerable example": {"query": "GitHub SQLi vulnerable example", "evidence_type": "reference_impl"},
    }
    hits = [
        SearchResult(
            title="OWASP SQL injection advisory",
            url="https://owasp.org/www-community/attacks/SQL_Injection",
            snippet="official SQL injection advisory guidance",
            source="remote",
            provider="tavily",
            query="OWASP SQL injection advisory",
        ),
        SearchResult(
            title="GitHub SQLi vulnerable example",
            url="https://github.com/example/sqli-demo",
            snippet="example vulnerable code",
            source="remote",
            provider="tavily",
            query="GitHub SQLi vulnerable example",
        ),
    ]

    payload = service._build_evidence_payload(hits)  # type: ignore[attr-defined]
    summary = service._summarize_evidence_types(hits)  # type: ignore[attr-defined]

    assert payload[0]["source_authority"] == "high"
    assert payload[1]["source_authority"] == "medium"
    assert summary["by_source_authority"] == {"high": 1, "medium": 1}


def test_evidence_graph_surfaces_source_authority_on_evidence_nodes(tmp_path: Path) -> None:
    service = _service_stub(
        tmp_path,
        vuln_id="CWE-89",
        search_policy="remote_prefer",
        require_evidence=False,
    )
    service.requirement = {  # type: ignore[attr-defined]
        "vuln_id": "CWE-89",
        "vuln_name": "SQL Injection",
    }
    query_plan = {
        "request_label": "SQL Injection",
        "queries": [
            {
                "query": "OWASP SQL injection advisory",
                "evidence_type": "advisory",
                "priority": 10,
                "family": "sqli",
            }
        ],
    }
    graph = service._build_evidence_graph(  # type: ignore[attr-defined]
        search_hits=[
            SearchResult(
                title="OWASP SQL injection advisory",
                url="https://owasp.org/www-community/attacks/SQL_Injection",
                snippet="sql injection advisory with OR 1=1 and unsafe query composition",
                source="remote",
                provider="tavily",
                query="OWASP SQL injection advisory",
            )
        ],
        query_plan=query_plan,
        tech_stack_candidates=[],
        family_hypothesis_summary={
            "ranked_families": [
                {
                    "family": "sqli",
                    "confidence": "high",
                    "score": 0.9,
                    "matched_aliases": ["sql injection"],
                    "matched_anchors": ["or 1=1"],
                }
            ]
        },
    )

    evidence_nodes = [node for node in graph["nodes"] if node.get("kind") == "evidence"]
    assert evidence_nodes[0]["source_authority"] == "high"


def test_researcher_stack_anchor_query_without_text_support_stays_low_confidence(tmp_path: Path) -> None:
    service = _service_stub(
        tmp_path,
        vuln_id="NAME-OPEN-REDIRECT",
        search_policy="remote_prefer",
        require_evidence=False,
    )
    query_plan = {
        "queries": [
            {
                "query": "Open Redirect vulnerable example python/fastapi",
                "evidence_type": "stack_anchor",
            }
        ],
    }
    service._query_plan_index = {  # type: ignore[attr-defined]
        "Open Redirect vulnerable example python/fastapi": {
            "query": "Open Redirect vulnerable example python/fastapi",
            "evidence_type": "stack_anchor",
        }
    }

    candidates = service._infer_tech_stack_candidates(  # type: ignore[attr-defined]
        [
            SearchResult(
                title="Open redirect note",
                url="https://example.com/open-redirect",
                snippet="generic redirect vulnerability example",
                source="remote",
                provider="tavily",
                query="Open Redirect vulnerable example python/fastapi",
            )
        ],
        query_plan,
    )

    assert candidates[0]["stack_id"] == "python/fastapi"
    assert candidates[0]["confidence"] == "low"
    assert candidates[0]["score"] == 0.05
    assert candidates[0]["sources"] == ["stack_anchor_query"]


def test_evidence_graph_does_not_add_support_edges_from_query_seed_alone(tmp_path: Path) -> None:
    service = _service_stub(
        tmp_path,
        vuln_id="NAME-OPEN-REDIRECT",
        search_policy="remote_prefer",
        require_evidence=False,
    )
    service.requirement = {  # type: ignore[attr-defined]
        "vuln_id": "NAME-OPEN-REDIRECT",
        "vuln_name": "Open Redirect",
    }
    query_plan = {
        "request_label": "Open Redirect",
        "queries": [
            {
                "query": "Open Redirect vulnerable example python/fastapi",
                "evidence_type": "stack_anchor",
                "priority": 9,
                "family": "open_redirect",
                "negative_family": False,
            }
        ],
    }
    graph = service._build_evidence_graph(  # type: ignore[attr-defined]
        search_hits=[
            SearchResult(
                title="generic reference",
                url="https://example.test/reference",
                snippet="generic web security example without concrete framework or family markers",
                source="remote",
                query="Open Redirect vulnerable example python/fastapi",
            )
        ],
        query_plan=query_plan,
        tech_stack_candidates=[
            {
                "language": "python",
                "framework": "fastapi",
                "stack_id": "python/fastapi",
                "confidence": "medium",
                "score": 0.5,
            }
        ],
        family_hypothesis_summary={
            "ranked_families": [
                {
                    "family": "open_redirect",
                    "confidence": "high",
                    "score": 0.9,
                    "matched_aliases": ["open redirect"],
                    "matched_anchors": ["redirect target"],
                }
            ]
        },
    )

    edges = graph["edges"]
    assert {"from": "evidence:1", "to": "family:open_redirect", "kind": "supports_family_hypothesis"} not in edges
    assert {"from": "evidence:1", "to": "stack:python/fastapi", "kind": "supports_stack_hypothesis"} not in edges


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


def test_unknown_cwe_researcher_run_fail_closes_when_only_wrong_family_tavily_hit_exists(monkeypatch, tmp_path: Path) -> None:
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

    try:
        service.run()
    except RuntimeError as exc:
        assert "low relevance score" in str(exc).lower()
    else:  # pragma: no cover - fail closed is the contract under test
        raise AssertionError("expected researcher to fail closed for unsupported unknown family")

    report = json.loads((tmp_path / "researcher_report.json").read_text(encoding="utf-8"))
    health = json.loads((tmp_path / "search_health.json").read_text(encoding="utf-8"))
    contract = json.loads((tmp_path / "resolved_contract.json").read_text(encoding="utf-8"))
    assert report["quality"] == "insufficient"
    assert report["search_degraded"] is False
    assert report["evidence"][0]["source"] == "remote"
    assert report["resolved_contract_path"] == str(tmp_path / "resolved_contract.json")
    assert report["semantic_signature"] == {
        "input_vector": [],
        "sink": [],
        "exploit_precondition": [],
    }
    assert health["configured"] is True
    assert health["remote_result_count"] == 1
    assert contract["contract_stage"] == "research_seed"


def test_llm_execution_summary_includes_prompt_contract_and_search_cache_mode(tmp_path: Path) -> None:
    service = _service_stub(
        tmp_path,
        vuln_id="NAME-OPEN-REDIRECT",
        search_policy="remote_prefer",
        require_evidence=True,
    )
    service.plan["loop"] = {"max_loops": 4}  # type: ignore[index]
    (tmp_path / "loop_state.json").write_text(json.dumps({"current_loop": 2}), encoding="utf-8")
    service.llm = _LLMStub()  # type: ignore[attr-defined]
    service.search_tool = type("SearchTool", (), {"timeout": 8.0})()  # type: ignore[attr-defined]
    service._search_cache_hit_count = 2  # type: ignore[attr-defined]
    service._search_cache_miss_count = 1  # type: ignore[attr-defined]
    service._record_prompt_invocation("researcher_report")  # type: ignore[attr-defined]
    service._record_prompt_invocation("guard_planner")  # type: ignore[attr-defined]
    service._guard_planner_budget_mode = "bundle_ensemble"  # type: ignore[attr-defined]
    service._guard_planner_planned_runs = 2  # type: ignore[attr-defined]

    payload = service._llm_execution_summary()  # type: ignore[attr-defined]

    assert payload["prompt_contracts"][0]["name"] == "researcher_report"
    assert payload["prompt_contracts"][0]["version"] == "build_researcher_prompt@1"
    assert payload["prompt_contracts"][1]["name"] == "guard_planner"
    assert payload["prompt_invocations"]["researcher_report"] == 1
    assert payload["prompt_invocations"]["guard_planner"] == 1
    assert payload["timeout_budget"]["search_timeout_s"] == 8.0
    assert payload["cost_budget"]["configured_cost_budget_usd"] == 0.25
    assert payload["cost_budget"]["usage_tokens"]["total_tokens"] == 30
    assert payload["cost_budget"]["usage_scope"] == "observed"
    assert payload["cost_budget"]["pricing_model"] == "gpt-5"
    assert payload["cost_budget"]["pricing_basis"] == "alias"
    assert payload["retry_budget"]["controller_loop_current"] == 2
    assert payload["retry_budget"]["controller_loop_max"] == 4
    assert payload["retry_budget"]["guard_planner_planned_runs"] == 2
    assert payload["retry_budget"]["guard_planner_actual_runs"] == 1
    assert payload["retry_budget"]["guard_budget_mode"] == "bundle_ensemble"
    assert payload["cache_mode"] == "search_cache_read_write"
    assert payload["path_class"] == "not_executed"


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


def test_search_cache_reuses_previous_query_results(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("agents.researcher.service.load_static_context", lambda _snapshot: "")
    monkeypatch.setattr("agents.researcher.service.get_repo_root", lambda: tmp_path)
    search_tool = _SearchToolStub(
        [
            SearchResult(
                title="remote note",
                url="https://owasp.org/demo",
                snippet="remote snippet",
                source="remote",
                provider="tavily",
            )
        ],
        SearchExecution(
            provider="tavily",
            configured=True,
            result_count=1,
            request={"query": "unknown cwe exploit", "limit": 3, "policy": "remote_required"},
        ),
    )
    service = _service_stub(
        tmp_path,
        vuln_id="CWE-9999",
        search_policy="remote_required",
        require_evidence=False,
    )
    service._evaluate_evidence_quality = lambda bundle, hits: ("sufficient", "sufficient evidence")  # type: ignore[attr-defined]
    service.search_tool = search_tool  # type: ignore[attr-defined]

    service.run()
    second = _service_stub(
        tmp_path,
        vuln_id="CWE-9999",
        search_policy="remote_required",
        require_evidence=False,
    )
    second._evaluate_evidence_quality = lambda bundle, hits: ("sufficient", "sufficient evidence")  # type: ignore[attr-defined]
    second.search_tool = search_tool  # type: ignore[attr-defined]
    second.run()

    health = json.loads((tmp_path / "search_health.json").read_text(encoding="utf-8"))
    assert search_tool.call_count == 1
    assert health["cache_hit_count"] == 1
    assert health["cache_miss_count"] == 0
    assert health["executed_query_count"] == 1


def test_collect_search_results_triggers_early_stop_on_diminishing_returns(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("agents.researcher.service.get_repo_root", lambda: tmp_path)
    service = _service_stub(
        tmp_path,
        vuln_id="NAME-OPEN-REDIRECT",
        search_policy="remote_required",
        require_evidence=False,
    )
    service.search_limit = 2  # type: ignore[attr-defined]
    service._query_plan_index = {  # type: ignore[attr-defined]
        "q1": {"priority": 3},
        "q2": {"priority": 2},
        "q3": {"priority": 1},
    }

    class _LoopStub(_ReactLoopStub):
        def query_plan_from_requirement(self, requirement, *, limit=3):  # noqa: ANN001
            return {
                "request_label": "Open Redirect",
                "family_hypotheses": [],
                "exploit_hypotheses": [],
                "queries": [
                    {"query": "q1", "priority": 3},
                    {"query": "q2", "priority": 2},
                    {"query": "q3", "priority": 1},
                ],
            }

    class _PerQuerySearchTool(_SearchToolStub):
        def search_with_filters(self, query, limit=3, policy="remote_prefer", **kwargs):  # noqa: ANN001
            self.call_count += 1
            if query == "q1":
                return [
                    SearchResult(
                        title="high authority",
                        url="https://owasp.org/demo",
                        snippet="open redirect writeup",
                        source="remote",
                        provider="tavily",
                        query=query,
                    )
                ]
            if query == "q2":
                return [
                    SearchResult(
                        title="duplicate authority",
                        url="https://owasp.org/demo",
                        snippet="same writeup",
                        source="remote",
                        provider="tavily",
                        query=query,
                    ),
                    SearchResult(
                        title="second authority",
                        url="https://mitre.org/demo",
                        snippet="second writeup",
                        source="remote",
                        provider="tavily",
                        query=query,
                    ),
                ]
            return [
                SearchResult(
                    title="duplicate authority again",
                    url="https://mitre.org/demo",
                    snippet="same writeup",
                    source="remote",
                    provider="tavily",
                    query=query,
                )
            ]

    search_tool = _PerQuerySearchTool(
        [],
        SearchExecution(
            provider="tavily",
            configured=True,
            result_count=1,
            request={"query": "q1", "limit": 3, "policy": "remote_required"},
        ),
    )
    service.react_loop = _LoopStub()  # type: ignore[attr-defined]
    service.search_tool = search_tool  # type: ignore[attr-defined]
    hits = service._collect_search_results(["q1", "q2", "q3"], _Span())  # type: ignore[attr-defined]

    assert len(hits) == 2
    assert service._search_early_stop_triggered is True  # type: ignore[attr-defined]
    assert service._search_executed_query_count == 3  # type: ignore[attr-defined]
    assert service._search_records[-1]["early_stop_triggered"] is True  # type: ignore[attr-defined]


def _write_template_fixture(template_dir: Path, metadata: dict) -> None:
    (template_dir / "app").mkdir(parents=True, exist_ok=True)
    (template_dir / "app" / "app.py").write_text("print('template')\n", encoding="utf-8")
    (template_dir / "template.json").write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")


def test_candidate_template_prefers_runtime_compatible_template(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    sqlite_template = repo_root / "workspaces" / "templates" / "sqli" / "flask_sqlite_raw"
    mysql_template = repo_root / "workspaces" / "templates" / "sqli" / "flask_mysql_union"
    _write_template_fixture(
        sqlite_template,
        {
            "id": "flask_sqlite_raw",
            "tags": ["cwe-89"],
            "db": "sqlite",
            "pattern_id": "sqli-string-concat",
            "stability_score": 0.40,
            "requires_external_db": False,
        },
    )
    _write_template_fixture(
        mysql_template,
        {
            "id": "flask_mysql_union",
            "tags": ["cwe-89"],
            "db": "mysql",
            "pattern_id": "sqli-union-mysql",
            "stability_score": 0.95,
            "requires_external_db": True,
        },
    )
    service = _service_stub(
        tmp_path,
        vuln_id="CWE-89",
        search_policy="remote_prefer",
        require_evidence=False,
    )
    service.runtime_templates_dir.mkdir(parents=True, exist_ok=True)  # type: ignore[attr-defined]
    service.requirement = {  # type: ignore[attr-defined]
        "vuln_id": "CWE-89",
        "pattern_id": "sqli-string-concat",
        "runtime": {"db": "sqlite", "allow_external_db": False},
        "researcher": {"generate_candidate_templates": True},
    }
    monkeypatch.setattr("agents.researcher.service.get_repo_root", lambda: repo_root)

    bundle = type("Bundle", (), {"vuln_id": "CWE-89"})()
    template_path = service._generate_candidate_template(bundle)  # type: ignore[attr-defined]

    assert template_path is not None
    assert template_path.name == "cwe-89-flask_sqlite_raw"
    metadata = json.loads((template_path / "template.json").read_text(encoding="utf-8"))
    assert metadata["id"] == "cwe-89-candidate"
    assert metadata["name"] == "CWE-89 candidate template"
    assert metadata["stack_id"] == "python/flask"
    assert metadata["language"] == "python"
    assert metadata["framework"] == "flask"


def test_candidate_template_skips_external_db_only_template_when_runtime_disallows_it(
    monkeypatch,
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    mysql_template = repo_root / "workspaces" / "templates" / "sqli" / "flask_mysql_union"
    _write_template_fixture(
        mysql_template,
        {
            "id": "flask_mysql_union",
            "tags": ["cwe-89"],
            "db": "mysql",
            "pattern_id": "sqli-union-mysql",
            "stability_score": 0.95,
            "requires_external_db": True,
        },
    )
    service = _service_stub(
        tmp_path,
        vuln_id="CWE-89",
        search_policy="remote_prefer",
        require_evidence=False,
    )
    service.runtime_templates_dir.mkdir(parents=True, exist_ok=True)  # type: ignore[attr-defined]
    service.requirement = {  # type: ignore[attr-defined]
        "vuln_id": "CWE-89",
        "pattern_id": "sqli-string-concat",
        "runtime": {"db": "sqlite", "allow_external_db": False},
        "researcher": {"generate_candidate_templates": True},
    }
    monkeypatch.setattr("agents.researcher.service.get_repo_root", lambda: repo_root)

    bundle = type("Bundle", (), {"vuln_id": "CWE-89"})()
    template_path = service._generate_candidate_template(bundle)  # type: ignore[attr-defined]

    assert template_path is None


def test_researcher_service_uses_request_ir_for_name_only_detection_and_dynamic_eval(
    tmp_path: Path,
) -> None:
    service = _service_stub(
        tmp_path,
        vuln_id="CWE-89",
        search_policy="remote_prefer",
        require_evidence=False,
    )
    service.requirement = {  # type: ignore[attr-defined]
        "vuln_id": "CWE-89",
        "request_ir": {
            "request_label": "SQL Injection",
            "resolved_vuln_id": "CWE-89",
            "name_driven": True,
            "resolution_state": "catalog_alias",
        },
        "policy": {"name_only_mode": "dynamic"},
        "researcher": {"search_policy": "remote_prefer"},
    }
    service.plan = {  # type: ignore[attr-defined]
        "requirement": dict(service.requirement),  # type: ignore[attr-defined]
        "policy": {"name_only_mode": "dynamic"},
        "paths": {"metadata": str(tmp_path)},
    }

    assert service._bundle_is_name_driven(None) is True  # type: ignore[attr-defined]
    assert service._dynamic_eval_enabled() is True  # type: ignore[attr-defined]
