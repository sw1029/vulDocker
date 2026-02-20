from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.researcher.service import ResearcherService
from rag.tools import SearchResult


def _service_stub(vuln_id: str = "CWE-89") -> ResearcherService:
    service = ResearcherService.__new__(ResearcherService)
    service.requirement = {"vuln_id": vuln_id}  # type: ignore[attr-defined]
    service.plan = {"policy": {"guard": {"failure_policy": "closed_unknown"}}}  # type: ignore[attr-defined]
    service._bundle_is_unknown = lambda bundle: False  # type: ignore[attr-defined]
    service._guard_missing_is_blocking = lambda bundle: False  # type: ignore[attr-defined]
    service._fallback_generator_assertions = lambda bundle: [  # type: ignore[attr-defined]
        {"op": "role_exists", "role": "service_main"}
    ]
    return service


def test_researcher_normalizes_legacy_ops_and_defers_verifier_unknown() -> None:
    service = _service_stub()
    payload = {
        "generator_assertions": [
            {"op": "regex_any_file", "globs": ["*.py"], "regex": "request\\.args"},
            {"op": "file_contains_regex", "path": "app.py", "regex": "SELECT"},
        ],
        "verifier_assertions": [
            {"op": "stdout_contains", "string": "Exploit SUCCESS"},
            {"op": "http_status", "url": "http://127.0.0.1:5000", "status": 200},
        ],
    }

    normalized = service._normalize_guard_payload_ops(  # type: ignore[attr-defined]
        payload,
        unsupported_policy="normalize_retry",
        bundle=None,
        report={},
    )

    assert normalized is not None
    assert normalized["generator_assertions"][0]["op"] == "file_regex_any"
    assert normalized["generator_assertions"][1]["op"] == "file_regex_contains"
    assert normalized["verifier_assertions"][0]["op"] == "contains"
    deferred = normalized["verifier_assertions_deferred"]
    assert any(item.get("op") == "http_status" for item in deferred)
    mapped = normalized["normalization"]["mapped_ops"]
    assert any(item.get("from") == "regex_any_file" and item.get("to") == "file_regex_any" for item in mapped)


def test_researcher_fail_policy_rejects_unsupported_generator_op() -> None:
    service = _service_stub()
    payload = {
        "generator_assertions": [{"op": "totally_unknown_op", "path": "app.py"}],
        "verifier_assertions": [],
    }

    normalized = service._normalize_guard_payload_ops(  # type: ignore[attr-defined]
        payload,
        unsupported_policy="fail",
        bundle=None,
        report={},
    )

    assert normalized is None


def test_known_cwe_low_relevance_uses_guard_fallback_mode() -> None:
    service = _service_stub("CWE-352")
    service._search_policy = lambda: "remote_prefer"  # type: ignore[attr-defined]
    service._require_researcher_evidence = lambda bundle: False  # type: ignore[attr-defined]
    service._bundle_is_unknown = lambda bundle: False  # type: ignore[attr-defined]
    hits = [
        SearchResult(
            title="sqli note",
            url="file:///tmp/sqli.md",
            snippet="SQL injection via UNION SELECT on request.args id",
            source="local",
            query="flask form bug",
        )
    ]
    quality, reason = service._evaluate_evidence_quality(None, hits)  # type: ignore[attr-defined]
    assert quality == "sufficient"
    assert "guard fallback mode" in reason.lower()


def test_unknown_cwe_low_relevance_is_insufficient_when_evidence_required() -> None:
    service = _service_stub("CWE-9999")
    service._search_policy = lambda: "remote_prefer"  # type: ignore[attr-defined]
    service._require_researcher_evidence = lambda bundle: True  # type: ignore[attr-defined]
    service._bundle_is_unknown = lambda bundle: True  # type: ignore[attr-defined]
    hits = [
        SearchResult(
            title="generic article",
            url="https://example.com/a",
            snippet="Unrelated application security note",
            source="remote",
            query="generic application issue",
        )
    ]
    quality, reason = service._evaluate_evidence_quality(None, hits)  # type: ignore[attr-defined]
    assert quality == "insufficient"
    assert "low relevance score" in reason.lower()
