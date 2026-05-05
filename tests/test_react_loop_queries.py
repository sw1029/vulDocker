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


def test_react_loop_query_plan_prioritizes_cve_advisory_queries(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-react-cve-plan"
    monkeypatch.setattr("orchestrator.plugins.react_loop.get_metadata_dir", lambda incoming_sid: tmp_path / incoming_sid)
    monkeypatch.setattr("orchestrator.plugins.react_loop.latest_failure_context", lambda incoming_sid: "")
    loop = ReactLoop(sid)

    plan = loop.query_plan_from_requirement(
        {
            "cve_id": "CVE-2099-0001",
            "language": "python",
            "framework": "flask",
        },
        limit=3,
    )

    assert plan["request_label"] == "CVE-2099-0001"
    assert plan["queries"][0]["evidence_type"] == "advisory"
    assert plan["queries"][0]["rationale"] == "cve-first official advisory seed"
    assert "CVE-2099-0001 NVD advisory" in plan["queries"][0]["query"]
    assert any(item["evidence_type"] == "writeup" for item in plan["queries"])


def test_react_loop_query_plan_expands_multiple_cve_ids(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-react-multi-cve-plan"
    monkeypatch.setattr("orchestrator.plugins.react_loop.get_metadata_dir", lambda incoming_sid: tmp_path / incoming_sid)
    monkeypatch.setattr("orchestrator.plugins.react_loop.latest_failure_context", lambda incoming_sid: "")
    loop = ReactLoop(sid)

    plan = loop.query_plan_from_requirement(
        {
            "vuln_ids": ["CVE-2099-0001", "CVE-2099-0002"],
            "language": "python",
            "framework": "flask",
        },
        limit=6,
    )
    queries = [item["query"] for item in plan["queries"]]

    assert any("CVE-2099-0001 NVD advisory" in query for query in queries)
    assert any("CVE-2099-0002 NVD advisory" in query for query in queries)
    assert sum(1 for item in plan["queries"] if item["rationale"] == "cve-first official advisory seed") == 2


def test_react_loop_query_plan_accepts_raw_cve_ids_list(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-react-raw-cve-ids-plan"
    monkeypatch.setattr("orchestrator.plugins.react_loop.get_metadata_dir", lambda incoming_sid: tmp_path / incoming_sid)
    monkeypatch.setattr("orchestrator.plugins.react_loop.latest_failure_context", lambda incoming_sid: "")
    loop = ReactLoop(sid)

    plan = loop.query_plan_from_requirement(
        {
            "cve_ids": ["CVE-2099-0001", "CVE-2099-0002"],
            "language": "python",
            "framework": "flask",
        },
        limit=6,
    )
    queries = [item["query"] for item in plan["queries"]]

    assert any("CVE-2099-0001 NVD advisory" in query for query in queries)
    assert any("CVE-2099-0002 NVD advisory" in query for query in queries)
    assert sum(1 for item in plan["queries"] if item["rationale"] == "cve-first official advisory seed") == 2


def test_react_loop_query_plan_prefers_effective_vuln_ids_over_raw_cve_ids(
    tmp_path: Path,
    monkeypatch,
) -> None:
    sid = "sid-react-effective-cve-plan"
    monkeypatch.setattr("orchestrator.plugins.react_loop.get_metadata_dir", lambda incoming_sid: tmp_path / incoming_sid)
    monkeypatch.setattr("orchestrator.plugins.react_loop.latest_failure_context", lambda incoming_sid: "")
    loop = ReactLoop(sid)

    plan = loop.query_plan_from_requirement(
        {
            "vuln_ids": ["CVE-2099-0001"],
            "cve_ids": ["CVE-2099-0001", "CVE-2099-0002"],
            "language": "python",
            "framework": "flask",
        },
        limit=8,
    )
    queries = [item["query"] for item in plan["queries"]]

    assert any("CVE-2099-0001 NVD advisory" in query for query in queries)
    assert all("CVE-2099-0002" not in query for query in queries)


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


def test_react_loop_family_hypothesis_ranking_uses_cwe_references_from_cve_advisory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    sid = "sid-react-cve-cwe-ranking"
    monkeypatch.setattr("orchestrator.plugins.react_loop.get_metadata_dir", lambda incoming_sid: tmp_path / incoming_sid)
    monkeypatch.setattr("orchestrator.plugins.react_loop.latest_failure_context", lambda incoming_sid: "")
    loop = ReactLoop(sid)

    ranking = loop.rank_family_hypotheses(
        [
            {
                "title": "CVE-2099-0001 NVD advisory",
                "url": "https://nvd.nist.gov/vuln/detail/CVE-2099-0001",
                "snippet": "Official advisory with affected versions and weakness metadata.",
                "raw_content": '{"weaknesses":[{"description":[{"lang":"en","value":"CWE-79"}]}]}',
            }
        ],
        base_hypotheses=[],
    )

    assert ranking["top_family"] == "xss"
    assert ranking["top_confidence"] in {"medium", "high"}
    top = ranking["ranked_families"][0]
    assert top["matched_cwes"] == ["cwe-79"]
    assert {
        "basis": "cwe_reference",
        "confidence": "high",
        "cwe_id": "cwe-79",
    } in top["bases"]


def test_react_loop_family_hypothesis_ranking_ignores_cwe_references_from_query_only(
    tmp_path: Path,
    monkeypatch,
) -> None:
    sid = "sid-react-cwe-query-only"
    monkeypatch.setattr("orchestrator.plugins.react_loop.get_metadata_dir", lambda incoming_sid: tmp_path / incoming_sid)
    monkeypatch.setattr("orchestrator.plugins.react_loop.latest_failure_context", lambda incoming_sid: "")
    loop = ReactLoop(sid)

    ranking = loop.rank_family_hypotheses(
        [
            {
                "title": "Database login bypass writeup",
                "url": "https://example.com/login-bypass",
                "snippet": "SQL injection with UNION SELECT in a vulnerable login query.",
                "query": "CWE-79 NVD advisory affected versions weakness details",
            }
        ],
        base_hypotheses=[],
    )

    assert ranking["top_family"] == "sqli"
    assert not any(item["family"] == "xss" for item in ranking["ranked_families"])


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


def test_react_loop_query_plan_uses_request_ir_family_candidates_for_broad_phrase(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-react-family-candidates"
    monkeypatch.setattr("orchestrator.plugins.react_loop.get_metadata_dir", lambda incoming_sid: tmp_path / incoming_sid)
    monkeypatch.setattr("orchestrator.plugins.react_loop.latest_failure_context", lambda incoming_sid: "")
    loop = ReactLoop(sid)

    plan = loop.query_plan_from_requirement(
        {
            "vuln_id": "NAME-CROSS-SITE-INJECTION",
            "vuln_name": "Cross Site Injection",
            "request_identity": {"request_label": "Cross Site Injection", "name_driven": True},
            "request_ir": {
                "request_label": "Cross Site Injection",
                "resolved_vuln_id": "NAME-CROSS-SITE-INJECTION",
                "name_driven": True,
                "resolution_state": "synthetic_name",
                "family_candidates": [
                    {"family": "xss", "confidence": "medium", "source": "label_overlap"},
                    {"family": "csrf", "confidence": "low", "source": "label_overlap"},
                ],
            },
        },
        limit=8,
    )

    families = [str(item.get("family") or "").strip().lower() for item in plan["family_hypotheses"]]

    assert "xss" in families
    assert "csrf" in families
    assert any(
        ("cross-site scripting" in item["query"].lower()) or ("csrf" in item["query"].lower())
        for item in plan["queries"]
    )


def test_react_loop_query_plan_does_not_reinject_raw_vuln_id_family_for_canonicalized_name_driven_lane(
    tmp_path: Path,
    monkeypatch,
) -> None:
    sid = "sid-react-request-ir-authority"
    monkeypatch.setattr("orchestrator.plugins.react_loop.get_metadata_dir", lambda incoming_sid: tmp_path / incoming_sid)
    monkeypatch.setattr("orchestrator.plugins.react_loop.latest_failure_context", lambda incoming_sid: "")
    loop = ReactLoop(sid)

    plan = loop.query_plan_from_requirement(
        {
            "vuln_id": "CWE-79",
            "vuln_name": "Reflected XSS",
            "request_identity": {"request_label": "Reflected XSS", "name_driven": True},
            "request_ir": {
                "request_label": "Reflected XSS",
                "resolved_vuln_id": "CWE-79",
                "resolution_state": "catalog_alias",
                "resolution_confidence": "high",
                "name_driven": True,
                "family_candidates": [
                    {"family": "xss", "confidence": "high", "source": "catalog_resolution"},
                ],
            },
        },
        limit=4,
    )

    xss_entries = [item for item in plan["family_hypotheses"] if item.get("family") == "xss"]
    assert xss_entries
    assert all(item.get("basis") != "vuln_id" for item in xss_entries)
    assert any(item.get("basis") == "catalog_resolution" for item in xss_entries)
    assert all("cwe-79" not in str(item.get("query") or "").lower() for item in plan["queries"])


def test_react_loop_query_plan_surfaces_negative_family_hypotheses_and_contradiction_query(
    tmp_path: Path,
    monkeypatch,
) -> None:
    sid = "sid-react-negative-families"
    monkeypatch.setattr("orchestrator.plugins.react_loop.get_metadata_dir", lambda incoming_sid: tmp_path / incoming_sid)
    monkeypatch.setattr("orchestrator.plugins.react_loop.latest_failure_context", lambda incoming_sid: "")
    loop = ReactLoop(sid)

    plan = loop.query_plan_from_requirement(
        {
            "vuln_id": "CWE-79",
            "vuln_name": "Reflected XSS",
            "request_identity": {"request_label": "Reflected XSS", "name_driven": True},
            "request_ir": {
                "request_label": "Reflected XSS",
                "resolved_vuln_id": "CWE-79",
                "name_driven": True,
                "family_candidates": [
                    {"family": "xss", "confidence": "high", "source": "catalog_resolution"},
                ],
                "negative_hypotheses": [
                    {"family": "template_injection", "source": "researcher_contradiction"},
                ],
            },
        },
        limit=6,
    )

    assert plan["negative_family_hypotheses"] == [
        {"family": "template_injection", "source": "researcher_contradiction"}
    ]
    assert any(
        item["evidence_type"] == "contradiction_check"
        and item.get("family") == "template_injection"
        and item.get("negative_family") is True
        for item in plan["queries"]
    )
