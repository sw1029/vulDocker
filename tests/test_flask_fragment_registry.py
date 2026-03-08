from __future__ import annotations

from agents.generator.flask_fragment_registry import (
    FLASK_FRAGMENT_REGISTRY,
    fragment_guard_generator_assertions,
    fragment_semantic_signature,
    resolve_fragment_spec,
    resolve_fragment_strategy,
    service_side_file_contains_tokens,
)


def test_registry_contains_all_compiler_covered_families() -> None:
    assert set(FLASK_FRAGMENT_REGISTRY) == {
        "csrf_missing_token",
        "deserialization_pickle_body",
        "open_redirect_reflect",
        "path_traversal_file_read",
        "sqli_string_concat",
        "ssrf_loopback_fetch",
        "template_injection_render",
        "xss_reflected",
    }


def test_resolve_fragment_strategy_from_vuln_id_and_pattern() -> None:
    assert resolve_fragment_strategy("NAME-OPEN-REDIRECT") == "open_redirect_reflect"
    assert resolve_fragment_strategy("CWE-89") == "sqli_string_concat"
    assert resolve_fragment_strategy("", pattern_id="path-traversal") == "path_traversal_file_read"
    assert resolve_fragment_strategy("", raw_label="Template Injection") == "template_injection_render"
    assert resolve_fragment_strategy("", raw_label="Server Side Template Injection") == "template_injection_render"
    assert resolve_fragment_strategy("", raw_label="Unvalidated Redirect") == "open_redirect_reflect"
    assert resolve_fragment_spec("CWE-502").fragment_id == "unsafe_pickle_body_route"  # type: ignore[union-attr]


def test_service_side_tokens_are_derived_from_registry() -> None:
    assert service_side_file_contains_tokens("NAME-OPEN-REDIRECT") == ["redirect(", "request.args.get('next'"]
    assert service_side_file_contains_tokens("CWE-79") == ["render_template_string", "request.args"]
    assert service_side_file_contains_tokens("", pattern_id="ssrf-url-fetch") == ["requests.get", "/metadata"]


def test_fragment_semantic_signature_is_derived_from_registry() -> None:
    signature = fragment_semantic_signature("NAME-TEMPLATE-INJECTION")
    assert "render_template_string" in signature["sink"]
    assert "template injection" in signature["exploit_precondition"]
    assert fragment_semantic_signature("CWE-9999", pattern_id="sqli-string-concat") == {
        "input_vector": [],
        "sink": [],
        "exploit_precondition": [],
    }


def test_fragment_guard_generator_assertions_include_registry_provenance_and_tokens() -> None:
    assertions = fragment_guard_generator_assertions("CWE-89")
    assert any(
        item.get("op") == "manifest_field_contains"
        and item.get("field") == "metadata.fragment_id"
        and item.get("string") == "login_query_concat_route"
        for item in assertions
    )
    assert any(item.get("op") == "any_dep_declared" and "flask" in (item.get("deps") or []) for item in assertions)
    assert any(
        item.get("op") == "file_contains"
        and item.get("path") == "app.py"
        and item.get("string") == "cur.execute"
        and item.get("severity") == "warn"
        for item in assertions
    )
    assert fragment_guard_generator_assertions("CWE-9999", pattern_id="sqli-string-concat") == []
