from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator.plugins.react_loop import ReactLoop


def test_react_loop_queries_include_raw_vuln_name(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-react-name-only"
    monkeypatch.setattr("orchestrator.plugins.react_loop.get_metadata_dir", lambda incoming_sid: tmp_path / incoming_sid)
    monkeypatch.setattr("orchestrator.plugins.react_loop.latest_failure_context", lambda incoming_sid: "")
    loop = ReactLoop(sid)

    queries = loop.queries_from_requirement(
        {
            "vuln_id": "NAME-TEMPLATE-INJECTION",
            "vuln_name": "Template Injection",
            "language": "python",
            "framework": "flask",
        }
    )

    assert any("Template Injection vulnerability writeup exploit poc python flask" in query for query in queries)


def test_react_loop_query_plan_exposes_family_hypotheses_and_evidence_types(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-react-plan"
    monkeypatch.setattr("orchestrator.plugins.react_loop.get_metadata_dir", lambda incoming_sid: tmp_path / incoming_sid)
    monkeypatch.setattr("orchestrator.plugins.react_loop.latest_failure_context", lambda incoming_sid: "")
    loop = ReactLoop(sid)

    plan = loop.query_plan_from_requirement(
        {
            "vuln_id": "NAME-OPEN-REDIRECT",
            "vuln_name": "Open Redirect",
            "language": "python",
            "framework": "flask",
            "pattern_id": "open-redirect",
            "request_identity": {"request_label": "Open Redirect"},
        },
        limit=4,
    )

    family_hypotheses = plan["family_hypotheses"]
    assert any(item["family"] == "open_redirect" for item in family_hypotheses)
    assert any(item["basis"] in {"request_label", "pattern_id", "vuln_id"} for item in family_hypotheses)
    assert any(item["evidence_type"] == "writeup" for item in plan["queries"])
    assert any(item["evidence_type"] == "reference_impl" for item in plan["queries"])
    assert any("open redirect" in item["query"].lower() for item in plan["queries"])
    assert "user-controlled redirect target reaches redirect sink" in plan["exploit_hypotheses"]


def test_react_loop_family_hypothesis_ranking_surfaces_contradictions(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-react-ranking"
    monkeypatch.setattr("orchestrator.plugins.react_loop.get_metadata_dir", lambda incoming_sid: tmp_path / incoming_sid)
    monkeypatch.setattr("orchestrator.plugins.react_loop.latest_failure_context", lambda incoming_sid: "")
    loop = ReactLoop(sid)

    ranking = loop.rank_family_hypotheses(
        [
            {
                "title": "Flask open redirect writeup",
                "url": "https://example.com/open-redirect",
                "snippet": "open redirect with next parameter and redirect target in Flask",
            },
            {
                "title": "Flask SSRF writeup",
                "url": "https://example.com/ssrf",
                "snippet": "server-side request forgery using requests.get and user-controlled url",
            },
        ],
        base_hypotheses=[{"family": "open_redirect", "confidence": "high", "basis": "request_label"}],
    )

    assert ranking["top_family"] == "open_redirect"
    assert ranking["raw_top_confidence"] == "high"
    assert ranking["top_confidence"] == "medium"
    assert ranking["ambiguous"] is True
    assert ranking["top_margin"] < 0.2
    assert "ssrf" in ranking["contradictory_families"]
    assert ranking["contradiction_count"] >= 1


def test_react_loop_family_hypothesis_ranking_marks_single_family_as_non_ambiguous(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-react-single-ranking"
    monkeypatch.setattr("orchestrator.plugins.react_loop.get_metadata_dir", lambda incoming_sid: tmp_path / incoming_sid)
    monkeypatch.setattr("orchestrator.plugins.react_loop.latest_failure_context", lambda incoming_sid: "")
    loop = ReactLoop(sid)

    ranking = loop.rank_family_hypotheses(
        [
            {
                "title": "Open redirect in Flask",
                "url": "https://example.com/open-redirect",
                "snippet": "open redirect with next parameter and redirect target",
            }
        ],
        base_hypotheses=[{"family": "open_redirect", "confidence": "high", "basis": "request_label"}],
    )

    assert ranking["top_family"] == "open_redirect"
    assert ranking["ambiguous"] is False
    assert ranking["contradiction_count"] == 0


def test_react_loop_queries_ignore_noisy_regression_intent(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-react-clean-intent"
    monkeypatch.setattr("orchestrator.plugins.react_loop.get_metadata_dir", lambda incoming_sid: tmp_path / incoming_sid)
    monkeypatch.setattr("orchestrator.plugins.react_loop.latest_failure_context", lambda incoming_sid: "")
    loop = ReactLoop(sid)

    queries = loop.queries_from_requirement(
        {
            "vuln_id": "NAME-OPEN-REDIRECT",
            "vuln_name": "Open Redirect",
            "language": "python",
            "framework": "flask",
            "pattern_id": "open-redirect",
            "intent": "E2E 회귀: Open Redirect name-only 검증",
            "request_identity": {"request_label": "Open Redirect"},
        }
    )

    assert all("e2e" not in query.lower() for query in queries)
    assert any("Open Redirect vulnerability writeup exploit poc python flask" in query for query in queries)


def test_react_loop_query_plan_surfaces_stack_hypotheses_without_locking_stack(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-react-stack-hyp"
    monkeypatch.setattr("orchestrator.plugins.react_loop.get_metadata_dir", lambda incoming_sid: tmp_path / incoming_sid)
    monkeypatch.setattr("orchestrator.plugins.react_loop.latest_failure_context", lambda incoming_sid: "")
    loop = ReactLoop(sid)

    plan = loop.query_plan_from_requirement(
        {
            "vuln_id": "NAME-OPEN-REDIRECT",
            "vuln_name": "Open Redirect",
            "request_identity": {"request_label": "Open Redirect", "name_driven": True},
            "stack_hypotheses": [
                {"language": "python", "framework": "flask", "source": "profile_prior", "confidence": "low"},
                {"language": "python", "framework": "fastapi", "source": "available_skeleton", "confidence": "low"},
            ],
        },
        limit=8,
    )

    assert plan["stack_locked"] is False
    assert plan["tech_stack"] is None
    assert plan["stack_hypotheses"][0]["stack_id"] == "python/flask"
    assert any(item["evidence_type"] == "stack_anchor" for item in plan["queries"])
    assert any("python/flask" in item["query"] for item in plan["queries"])
