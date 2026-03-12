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
    service._query_plan_index = {}  # type: ignore[attr-defined]
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


def test_researcher_warn_policy_records_dropped_unsupported_generator_op() -> None:
    service = _service_stub()
    payload = {
        "generator_assertions": [{"op": "totally_unknown_op", "path": "app.py"}],
        "verifier_assertions": [],
    }

    normalized = service._normalize_guard_payload_ops(  # type: ignore[attr-defined]
        payload,
        unsupported_policy="warn",
        bundle=None,
        report={},
    )

    assert normalized is not None
    assert normalized["generator_assertions"] == [{"op": "role_exists", "role": "service_main"}]
    dropped = normalized["normalization"]["dropped_ops"]
    warnings = normalized["normalization"]["warnings"]
    assert {"op": "totally_unknown_op", "scope": "generator", "reason": "unsupported_op"} in dropped
    assert any("dropped unsupported guard assertion op in generator" in item for item in warnings)


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


def test_researcher_normalizes_dep_declared_from_plural_dependency_keys() -> None:
    service = _service_stub()
    payload = {
        "generator_assertions": [
            {"op": "dep_declared", "deps": ["flask", "requests"]},
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
    assert assertion["op"] == "dep_declared"
    assert assertion["dep"] == "flask"
    assert "deps" not in assertion


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


def test_unknown_cwe_low_confidence_policy_can_fail_closed() -> None:
    service = _service_stub("CWE-9999")
    service._search_policy = lambda: "remote_prefer"  # type: ignore[attr-defined]
    service._require_researcher_evidence = lambda bundle: True  # type: ignore[attr-defined]
    service._bundle_is_unknown = lambda bundle: True  # type: ignore[attr-defined]
    service._low_confidence_unknown_policy = lambda: "fail_closed"  # type: ignore[attr-defined]
    service._score_evidence_relevance = lambda bundle, hits: {  # type: ignore[attr-defined]
        "score": 0.42,
        "threshold": 0.30,
        "confidence": "low",
    }
    hits = [
        SearchResult(
            title="vuln note",
            url="https://example.com/v",
            snippet="Potentially related write-up",
            source="remote",
            query="name only vuln",
        )
    ]

    quality, reason = service._evaluate_evidence_quality(None, hits)  # type: ignore[attr-defined]

    assert quality == "insufficient"
    assert "low-confidence unknown evidence" in reason.lower()


def test_unknown_cwe_low_confidence_policy_can_downgrade_to_guard_fallback() -> None:
    service = _service_stub("CWE-9999")
    service._search_policy = lambda: "remote_prefer"  # type: ignore[attr-defined]
    service._require_researcher_evidence = lambda bundle: True  # type: ignore[attr-defined]
    service._bundle_is_unknown = lambda bundle: True  # type: ignore[attr-defined]
    service._low_confidence_unknown_policy = lambda: "guard_fallback"  # type: ignore[attr-defined]
    service._score_evidence_relevance = lambda bundle, hits: {  # type: ignore[attr-defined]
        "score": 0.42,
        "threshold": 0.30,
        "confidence": "low",
    }
    hits = [
        SearchResult(
            title="vuln note",
            url="https://example.com/v",
            snippet="Potentially related write-up",
            source="remote",
            query="name only vuln",
        )
    ]

    quality, reason = service._evaluate_evidence_quality(None, hits)  # type: ignore[attr-defined]

    assert quality == "sufficient"
    assert "guard fallback mode" in reason.lower()


def test_open_world_strict_name_driven_lane_requires_non_degraded_remote_search() -> None:
    service = _service_stub("NAME-OPEN-REDIRECT")
    service.plan = {"policy": {"open_world_strict": True}, "requirement": service.requirement}  # type: ignore[attr-defined]
    service.requirement = {  # type: ignore[attr-defined]
        "vuln_id": "NAME-OPEN-REDIRECT",
        "request_identity": {"name_driven": True},
    }
    service._search_degraded = True  # type: ignore[attr-defined]
    service._bundle_is_unknown = lambda bundle: False  # type: ignore[attr-defined]
    service._require_researcher_evidence = lambda bundle: False  # type: ignore[attr-defined]
    hits = [
        SearchResult(
            title="local note",
            url="/tmp/local",
            snippet="Open redirect notes",
            source="local",
            query="Open Redirect",
        )
    ]

    quality, reason = service._evaluate_evidence_quality(None, hits)  # type: ignore[attr-defined]

    assert quality == "insufficient"
    assert "open_world_strict" in reason
    assert "degraded" in reason


def test_open_world_strict_name_driven_lane_requires_remote_hits() -> None:
    service = _service_stub("NAME-OPEN-REDIRECT")
    service.plan = {"policy": {"open_world_strict": True}, "requirement": service.requirement}  # type: ignore[attr-defined]
    service.requirement = {  # type: ignore[attr-defined]
        "vuln_id": "NAME-OPEN-REDIRECT",
        "request_identity": {"name_driven": True},
    }
    service._search_degraded = False  # type: ignore[attr-defined]
    service._bundle_is_unknown = lambda bundle: False  # type: ignore[attr-defined]
    service._require_researcher_evidence = lambda bundle: False  # type: ignore[attr-defined]
    hits = [
        SearchResult(
            title="local note",
            url="/tmp/local",
            snippet="Open redirect notes",
            source="local",
            query="Open Redirect",
        )
    ]

    quality, reason = service._evaluate_evidence_quality(None, hits)  # type: ignore[attr-defined]

    assert quality == "insufficient"
    assert "open_world_strict" in reason
    assert "at least one remote hit" in reason


def test_unknown_cwe_query_token_does_not_inflate_relevance() -> None:
    service = _service_stub("CWE-9999")
    service._bundle_is_unknown = lambda bundle: True  # type: ignore[attr-defined]
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

    profile = service._relevance_profile(None)  # type: ignore[attr-defined]
    assert "sql injection" not in profile["family_terms"]
    assert "sqli" not in profile["family_terms"]


def test_unknown_semantic_signature_does_not_infer_known_family_from_pattern_or_stack_hints() -> None:
    service = _service_stub("CWE-9999")
    service._bundle_is_unknown = lambda bundle: True  # type: ignore[attr-defined]
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

    assert sources == ["empty"]
    assert signature == {
        "input_vector": [],
        "sink": [],
        "exploit_precondition": [],
    }


def test_known_family_semantic_signature_merge_stays_family_scoped() -> None:
    service = _service_stub("CWE-22")
    service.requirement = {  # type: ignore[attr-defined]
        "vuln_id": "CWE-22",
        "pattern_id": "path-traversal",
        "vuln_name": "path traversal",
    }
    report = {
        "semantic_signature": {
            "input_vector": ["request.args", "user-controlled url"],
            "sink": ["open(", "requests.get"],
            "exploit_precondition": ["path traversal", "server-side request forgery", "string concatenation"],
        }
    }

    signature, sources = service._resolve_semantic_signature(report, None)  # type: ignore[attr-defined]

    assert "baseline" in sources
    assert "open(" in signature["sink"]
    assert "requests.get" not in signature["sink"]
    assert "user-controlled url" not in signature["input_vector"]
    assert "server-side request forgery" not in signature["exploit_precondition"]
    assert "string concatenation" not in signature["exploit_precondition"]


def test_freeform_template_injection_pattern_uses_pattern_semantics() -> None:
    service = _service_stub("NAME-TEMPLATE-INJECTION")
    service.requirement = {  # type: ignore[attr-defined]
        "vuln_id": "NAME-TEMPLATE-INJECTION",
        "pattern_id": "template-injection",
        "vuln_name": "Template Injection",
        "language": "python",
        "framework": "flask",
    }
    report = {
        "preconditions": [
            "render_template_string(template)",
            "incidental note mentioning cursor.execute should not flip the family",
        ],
        "verification_spec": {
            "success_text_markers": ["49"],
            "flag_token": "FLAG_SSTI_OK",
        },
    }

    signature, sources = service._resolve_semantic_signature(report, None)  # type: ignore[attr-defined]

    assert sources == ["pattern"]
    assert "render_template_string" in signature["sink"]
    assert any("template source string" in item for item in signature["exploit_precondition"])
    assert "cursor.execute" not in signature["sink"]
    assert "SQL query execution" not in signature["sink"]


def test_researcher_drops_stdlib_dependency_assertions_from_generator_guards() -> None:
    service = _service_stub("CWE-9999")
    service.requirement = {  # type: ignore[attr-defined]
        "vuln_id": "CWE-9999",
        "language": "python",
        "runtime": {"python_version": "3.11"},
    }
    payload = {
        "generator_assertions": [
            {"op": "dep_declared", "dep": "sqlite3"},
            {"op": "any_dep_declared", "deps": ["sqlite3", "pysqlite3", "flask"]},
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
    generator_assertions = normalized["generator_assertions"]
    assert len(generator_assertions) == 1
    assert generator_assertions[0]["op"] == "any_dep_declared"
    assert generator_assertions[0]["deps"] == ["flask"]
    warnings = normalized["normalization"]["warnings"]
    assert any("stdlib/runtime-provided module 'sqlite3'" in item for item in warnings)
    assert any("removed stdlib/runtime-provided dependency candidates" in item for item in warnings)


def test_unknown_relevance_penalizes_wrong_family_remote_hits() -> None:
    service = _service_stub("CWE-9999")
    service._bundle_is_unknown = lambda bundle: True  # type: ignore[attr-defined]
    service.requirement = {  # type: ignore[attr-defined]
        "vuln_id": "CWE-9999",
        "pattern_id": "sqli-string-concat",
        "language": "python",
        "framework": "flask",
        "runtime": {"db": "sqlite"},
    }
    report = service._score_evidence_relevance(  # type: ignore[attr-defined]
        None,
        [
            SearchResult(
                title="Flask SSRF via remote fetch",
                url="https://example.com/ssrf",
                snippet="Flask SSRF allows server-side request forgery to internal metadata services and remote code execution style impact.",
                source="remote",
                query="unknown cwe exploit python flask",
            )
        ],
    )

    assert report["negative_hit_count"] == 1
    assert report["negative_hit_ratio"] == 1.0
    assert report["confidence"] == "low"
    assert report["score"] < 0.30


def test_rule_from_verification_spec_derives_json_success_contract_from_marker() -> None:
    service = _service_stub("CWE-9999")
    bundle = type("Bundle", (), {"vuln_id": "CWE-9999"})()

    rule = service._rule_from_verification_spec(  # type: ignore[attr-defined]
        bundle,
        {
            "success_text_markers": ['"count": 2'],
        },
    )

    runtime = rule["runtime"]
    output = rule["output"]
    assert runtime["success_mode"] == "json"
    assert runtime["success_text_markers"][0] == '"count":2'
    assert runtime["json_success_key"] == "count"
    assert runtime["json_success_value"] == 2
    assert output["mode"] == "json"
    assert output["json"]["success_key"] == "count"
    assert output["json"]["success_value"] == 2


def test_guard_normalization_aligns_verifier_marker_with_canonical_json_marker() -> None:
    service = _service_stub("CWE-9999")
    payload = {
        "generator_assertions": [{"op": "role_exists", "role": "service_main"}],
        "verifier_assertions": [{"op": "contains", "string": '"count": 2'}],
    }
    report = {
        "verification_spec": {
            "success_text_markers": ['"count": 2'],
        }
    }

    normalized = service._normalize_guard_payload_ops(  # type: ignore[attr-defined]
        payload,
        unsupported_policy="normalize_retry",
        bundle=None,
        report=report,
    )

    assert normalized is not None
    verifier_assertions = normalized["verifier_assertions"]
    assert verifier_assertions[0]["string"] == '"count":2'
    assert any(
        "canonical structured success contract" in item
        for item in normalized["normalization"]["warnings"]
    )


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


def test_rule_from_verification_spec_prefers_printed_success_marker_over_weak_response_marker() -> None:
    service = _service_stub("NAME-TEMPLATE-INJECTION")
    bundle = type("Bundle", (), {"vuln_id": "NAME-TEMPLATE-INJECTION"})()

    rule = service._rule_from_verification_spec(  # type: ignore[attr-defined]
        bundle,
        {
            "success_text_markers": ["49"],
            "flag_token": "49",
            "assertion_program": "print('OK: SSTI confirmed')\nprint('FAIL: marker not found')\n",
        },
    )

    runtime = rule["runtime"]
    assert runtime["success_text_markers"] == ["OK: SSTI confirmed"]
    assert runtime["assertion_program"] == [
        {"op": "contains", "string": "OK: SSTI confirmed"},
        {"op": "not_contains", "string": "FAIL: marker not found"},
    ]
    assert runtime.get("flag_token") in {"", None}
    assert rule["success_signature"] == "OK: SSTI confirmed"
    assert "flag_token" not in rule
    assert rule["verification"]["require_flag"] is False


def test_rule_from_verification_spec_adds_service_side_pattern_for_open_redirect() -> None:
    service = _service_stub("NAME-OPEN-REDIRECT")
    service.requirement = {"vuln_id": "NAME-OPEN-REDIRECT", "vuln_name": "Open Redirect"}  # type: ignore[attr-defined]
    bundle = type("Bundle", (), {"vuln_id": "NAME-OPEN-REDIRECT"})()

    rule = service._rule_from_verification_spec(  # type: ignore[attr-defined]
        bundle,
        {
            "success_text_markers": ["Exploit SUCCESS"],
        },
    )

    patterns = rule["patterns"]
    assert any(
        pattern.get("type") == "file_contains"
        and pattern.get("path") == "{{service_entry}}"
        and pattern.get("contains") == "redirect("
        for pattern in patterns
    )


def test_rule_from_verification_spec_adds_service_side_pattern_for_template_injection() -> None:
    service = _service_stub("NAME-TEMPLATE-INJECTION")
    service.requirement = {"vuln_id": "NAME-TEMPLATE-INJECTION", "vuln_name": "Template Injection"}  # type: ignore[attr-defined]
    bundle = type("Bundle", (), {"vuln_id": "NAME-TEMPLATE-INJECTION"})()

    rule = service._rule_from_verification_spec(  # type: ignore[attr-defined]
        bundle,
        {
            "success_text_markers": ["Exploit SUCCESS"],
        },
    )

    patterns = rule["patterns"]
    assert any(
        pattern.get("type") == "file_contains"
        and pattern.get("path") == "{{service_entry}}"
        and pattern.get("contains") == "render_template_string"
        for pattern in patterns
    )


def test_align_verifier_assertions_drops_weak_response_marker_for_template_injection() -> None:
    service = _service_stub("NAME-TEMPLATE-INJECTION")
    payload = {
        "verifier_assertions": [
            {"op": "contains", "string": "OK: SSTI confirmed"},
            {"op": "contains", "string": "49"},
            {"op": "not_contains", "string": "FAIL: marker not found"},
        ]
    }
    report = {
        "verification_spec": {
            "success_text_markers": ["49"],
            "flag_token": "49",
            "assertion_program": "print('OK: SSTI confirmed')\nprint('FAIL: marker not found')\n",
        }
    }
    warnings: list[str] = []
    bundle = type("Bundle", (), {"vuln_id": "NAME-TEMPLATE-INJECTION"})()

    service._align_verifier_assertions_with_verification_spec(  # type: ignore[attr-defined]
        payload,
        report=report,
        bundle=bundle,
        warnings=warnings,
    )

    assertions = payload["verifier_assertions"]
    contains = [item["string"] for item in assertions if item.get("op") == "contains"]
    not_contains = [item["string"] for item in assertions if item.get("op") == "not_contains"]
    assert contains == ["OK: SSTI confirmed"]
    assert not_contains == ["FAIL: marker not found"]
    assert any("normalized runtime verification contract" in item for item in warnings)


def test_fallback_guard_spec_uses_normalized_runtime_verification_spec_for_path_traversal() -> None:
    service = _service_stub("CWE-22")
    service.sid = "sid-path"  # type: ignore[attr-defined]
    service.requirement = {"vuln_id": "CWE-22"}  # type: ignore[attr-defined]
    service._allow_runtime_rule_override_static = lambda: False  # type: ignore[attr-defined]
    service._report_confidence = lambda report: "high"  # type: ignore[attr-defined]
    service._fallback_generator_assertions = (  # type: ignore[attr-defined]
        lambda bundle: ResearcherService._fallback_generator_assertions(service, bundle)
    )
    bundle = type("Bundle", (), {"vuln_id": "CWE-22", "slug": "cwe-22"})()

    payload = service._fallback_guard_spec(  # type: ignore[attr-defined]
        report={
            "verification_spec": {
                "success_text_markers": ["49"],
                "flag_token": "49",
                "assertion_program": "print('OK: Path Traversal confirmed')\nprint('FAIL: marker not found')\n",
            },
            "semantic_signature": {},
        },
        evidence_refs=[],
        policy_snapshot={},
        bundle=bundle,
    )

    generator_assertions = payload["generator_assertions"]
    verifier_assertions = payload["verifier_assertions"]
    assert any(
        item.get("op") == "manifest_field_contains"
        and item.get("field") == "poc.success_signature"
        and item.get("string") == "Exploit SUCCESS"
        for item in generator_assertions
    )
    assert any(
        item.get("op") == "manifest_field_contains"
        and item.get("field") == "metadata.fragment_id"
        and item.get("string") == "file_read_download_route"
        for item in generator_assertions
    )
    assert any(
        item.get("op") == "manifest_field_contains"
        and item.get("field") == "metadata.compose_mode"
        and item.get("string") == "registry"
        for item in generator_assertions
    )
    assert any(
        item.get("op") == "contains" and item.get("string") == "Exploit SUCCESS"
        for item in verifier_assertions
    )
    assert not any(item.get("string") == "49" for item in verifier_assertions if item.get("op") == "contains")


def test_dynamic_eval_fallback_generator_assertions_drop_compiler_metadata_constraints() -> None:
    service = _service_stub("NAME-OPEN-REDIRECT")
    service.requirement = {  # type: ignore[attr-defined]
        "vuln_id": "NAME-OPEN-REDIRECT",
        "vuln_name": "Open Redirect",
        "pattern_id": "open-redirect",
        "policy": {"dynamic_eval": True},
    }
    service._fallback_generator_assertions = (  # type: ignore[attr-defined]
        lambda bundle: ResearcherService._fallback_generator_assertions(service, bundle)
    )
    bundle = type("Bundle", (), {"vuln_id": "NAME-OPEN-REDIRECT"})()

    assertions = service._fallback_generator_assertions(bundle)  # type: ignore[attr-defined]
    metadata_fields = {
        str(assertion.get("field") or "")
        for assertion in assertions
        if isinstance(assertion, dict)
    }

    assert "metadata.stack_scaffold_id" not in metadata_fields
    assert "metadata.fragment_id" not in metadata_fields
    assert "metadata.compose_mode" not in metadata_fields
    assert "metadata.compiler_strategy" not in metadata_fields
    assert any(assertion.get("op") == "role_exists" for assertion in assertions)


def test_name_only_dynamic_mode_fallback_generator_assertions_drop_compiler_metadata_constraints() -> None:
    service = _service_stub("NAME-OPEN-REDIRECT")
    service.requirement = {  # type: ignore[attr-defined]
        "vuln_id": "NAME-OPEN-REDIRECT",
        "vuln_name": "Open Redirect",
        "pattern_id": "open-redirect",
        "policy": {"name_only_mode": "dynamic"},
        "request_identity": {"name_driven": True},
    }
    service._fallback_generator_assertions = (  # type: ignore[attr-defined]
        lambda bundle: ResearcherService._fallback_generator_assertions(service, bundle)
    )
    bundle = type("Bundle", (), {"vuln_id": "NAME-OPEN-REDIRECT"})()

    assertions = service._fallback_generator_assertions(bundle)  # type: ignore[attr-defined]
    metadata_fields = {
        str(assertion.get("field") or "")
        for assertion in assertions
        if isinstance(assertion, dict)
    }

    assert "metadata.stack_scaffold_id" not in metadata_fields
    assert "metadata.fragment_id" not in metadata_fields
    assert "metadata.compose_mode" not in metadata_fields
    assert "metadata.compiler_strategy" not in metadata_fields


def test_name_only_dynamic_mode_candidate_guard_normalization_drops_compiler_metadata_constraints() -> None:
    service = _service_stub("NAME-OPEN-REDIRECT")
    service.requirement = {  # type: ignore[attr-defined]
        "vuln_id": "NAME-OPEN-REDIRECT",
        "policy": {"name_only_mode": "dynamic"},
        "request_identity": {"name_driven": True},
    }
    payload = {
        "generator_assertions": [
            {"op": "role_exists", "role": "service_main"},
            {"op": "manifest_field_contains", "field": "metadata.stack_scaffold_id", "string": "python/flask"},
            {"op": "manifest_field_contains", "field": "metadata.fragment_id", "string": "redirect_next_route"},
        ],
        "verifier_assertions": [{"op": "contains", "string": "Exploit SUCCESS"}],
    }

    normalized = service._normalize_guard_payload_ops(  # type: ignore[attr-defined]
        payload,
        unsupported_policy="normalize_retry",
        bundle=type("Bundle", (), {"vuln_id": "NAME-OPEN-REDIRECT"})(),
        report={},
    )

    generator_assertions = normalized["generator_assertions"]  # type: ignore[index]
    metadata_fields = {
        str(assertion.get("field") or "")
        for assertion in generator_assertions
        if isinstance(assertion, dict)
    }

    assert "metadata.stack_scaffold_id" not in metadata_fields
    assert "metadata.fragment_id" not in metadata_fields
    assert any(assertion.get("op") == "role_exists" for assertion in generator_assertions)


def test_default_semantic_signature_prefers_shared_registry_for_compiler_family() -> None:
    service = _service_stub("CWE-89")
    service.requirement = {"vuln_id": "CWE-89"}  # type: ignore[attr-defined]
    bundle = type("Bundle", (), {"vuln_id": "CWE-89", "slug": "cwe-89"})()

    signature = ResearcherService._default_semantic_signature(service, bundle)

    assert "request.args" in signature["input_vector"]
    assert "SQL query execution" in signature["sink"]
    assert "sql injection" in signature["exploit_precondition"]


def test_resolve_semantic_signature_for_open_redirect_uses_pattern_defaults() -> None:
    service = _service_stub("NAME-OPEN-REDIRECT")
    service.requirement = {  # type: ignore[attr-defined]
        "vuln_id": "NAME-OPEN-REDIRECT",
        "pattern_id": "open-redirect",
        "vuln_name": "Open Redirect",
    }
    bundle = type("Bundle", (), {"vuln_id": "NAME-OPEN-REDIRECT", "slug": "name-open-redirect"})()

    signature, sources = service._resolve_semantic_signature(  # type: ignore[attr-defined]
        {"semantic_signature": {}},
        bundle,
    )

    assert signature["input_vector"]
    assert signature["sink"]
    assert signature["exploit_precondition"]
    assert "redirect(" in signature["sink"]
    assert any(source in {"pattern", "heuristic", "default"} for source in sources)
