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
    service._last_evidence_relevance = None  # type: ignore[attr-defined]
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
    assert normalized["generator_assertions"][0]["severity"] == "warn"
    assert normalized["generator_assertions"][0]["intent"] == "syntax_hint"
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


def test_researcher_normalizes_file_regex_any_patterns_into_regex_and_globs() -> None:
    service = _service_stub()
    payload = {
        "generator_assertions": [
            {"op": "file_regex_any", "patterns": ["request\\.args", "cursor\\.execute"]},
        ],
        "verifier_assertions": [],
    }

    normalized = service._normalize_guard_payload_ops(  # type: ignore[attr-defined]
        payload,
        unsupported_policy="normalize_retry",
        bundle=None,
        report={},
    )

    assert normalized is not None
    assertion = normalized["generator_assertions"][0]
    assert assertion["globs"] == ["*.py", "*.js", "*.ts", "*.php", "*.rb", "*.java", "*.go", "*.sql"]
    assert assertion["regex"] == "(?:request\\.args)|(?:cursor\\.execute)"
    assert assertion["severity"] == "warn"
    assert assertion["intent"] == "syntax_hint"
    assert assertion["stability"] == "low"
    assert "patterns" not in assertion


def test_researcher_downgrades_contract_like_regex_generator_assertions() -> None:
    service = _service_stub()
    payload = {
        "generator_assertions": [
            {
                "op": "file_regex_any",
                "globs": ["**/*.py"],
                "regex": "@app\\.(get|route)\\s*\\(\\s*['\\\"]/health['\\\"]",
                "severity": "block",
                "intent": "contract",
                "stability": "high",
            }
        ],
        "verifier_assertions": [],
    }

    normalized = service._normalize_guard_payload_ops(  # type: ignore[attr-defined]
        payload,
        unsupported_policy="normalize_retry",
        bundle=None,
        report={},
    )

    assert normalized is not None
    assertion = normalized["generator_assertions"][0]
    assert assertion["severity"] == "warn"
    assert assertion["intent"] == "syntax_hint"
    assert assertion["stability"] == "low"


def test_researcher_downgrades_non_structural_blocking_generator_assertions() -> None:
    service = _service_stub()
    payload = {
        "generator_assertions": [
            {
                "op": "file_contains",
                "path": "app.py",
                "contains": "request.args",
                "severity": "block",
                "intent": "semantic_anchor",
                "stability": "high",
            }
        ],
        "verifier_assertions": [],
    }

    normalized = service._normalize_guard_payload_ops(  # type: ignore[attr-defined]
        payload,
        unsupported_policy="normalize_retry",
        bundle=None,
        report={},
    )

    assert normalized is not None
    assertion = normalized["generator_assertions"][0]
    assert assertion["op"] == "file_contains"
    assert assertion["severity"] == "warn"


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


def test_unknown_cwe_query_token_does_not_inflate_relevance() -> None:
    service = _service_stub("CWE-9999")
    service.requirement = {  # type: ignore[attr-defined]
        "vuln_id": "CWE-9999",
        "pattern_id": "sqli-string-concat",
        "language": "python",
        "framework": "flask",
        "runtime": {"db": "sqlite"},
    }
    hits = [
        SearchResult(
            title="generic devops note",
            url="https://example.com/post",
            snippet="Container hardening and deployment basics.",
            source="remote",
            query="CWE-9999 exploit writeup python flask",
        )
    ]

    score = service._estimate_evidence_relevance(None, hits)  # type: ignore[attr-defined]

    assert score < 0.30


def test_unknown_semantic_signature_is_derived_from_pattern_and_verification_spec() -> None:
    service = _service_stub("CWE-9999")
    service.requirement = {  # type: ignore[attr-defined]
        "vuln_id": "CWE-9999",
        "pattern_id": "sqli-string-concat",
        "intent": "unknown sql injection style demo",
    }
    report = {
        "intent": "Generate a Flask+SQLite endpoint with string concatenation SQL injection.",
        "preconditions": [
            "exploit_precondition: unauthenticated GET parameter",
            "input_vector: id query parameter",
            "sink: sqlite3 executes concatenated SQL query",
        ],
        "verification_spec": {
            "assertion_program": {
                "language": "python",
                "code": (
                    "user_id = request.args.get('id', '1')\n"
                    "q = 'SELECT id FROM users WHERE id=' + user_id\n"
                    "cur.execute(q)\n"
                ),
            }
        },
    }

    signature, sources = service._resolve_semantic_signature(report, None)  # type: ignore[attr-defined]

    assert "heuristic" in sources
    assert "request.args" in signature["input_vector"]
    assert any(token in signature["sink"] for token in ["cursor.execute", "execute("])
    assert any("string concatenation" in token or "input concatenated/interpolated into SQL sink" in token for token in signature["exploit_precondition"])


def test_extract_verification_spec_reads_wrapped_researcher_report() -> None:
    service = _service_stub("CWE-9999")
    service._load_latest_report = lambda: {  # type: ignore[attr-defined]
        "researcher_report": {
            "verification_spec": {
                "success_text_markers": ["SQLI_OK"],
                "flag_token": "FLAG_SQLI",
            }
        }
    }
    bundle = type("Bundle", (), {"vuln_id": "CWE-9999"})()

    spec = service._extract_verification_spec(bundle)  # type: ignore[attr-defined]

    assert spec is not None
    assert spec["success_text_markers"] == ["SQLI_OK"]
    assert spec["flag_token"] == "FLAG_SQLI"


def test_rule_from_verification_spec_ignores_opaque_code_string_and_uses_markers() -> None:
    service = _service_stub("CWE-9999")
    bundle = type("Bundle", (), {"vuln_id": "CWE-9999"})()

    rule = service._rule_from_verification_spec(  # type: ignore[attr-defined]
        bundle,
        {
            "success_text_markers": ["SQLI_OK"],
            "flag_token": "FLAG_SQLI",
            "assertion_program": "print('/tmp/app.db')\nprint('SQLI_OK')\n",
        },
    )

    runtime = rule["runtime"]
    assert runtime["success_text_markers"] == ["SQLI_OK"]
    assert runtime["assertion_program"] == [
        {"op": "contains", "string": "SQLI_OK"},
        {"op": "contains", "string": "FLAG_SQLI"},
    ]
