from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.guardrails import GuardEngine, build_guard_spec


def _manifest() -> dict:
    return {
        "files": [
            {
                "path": "app.py",
                "role": "service_main",
                "content": (
                    "from flask import Flask, request\n"
                    "import sqlite3\n"
                    "app = Flask(__name__)\n"
                    "@app.get('/users')\n"
                    "def users():\n"
                    "    user_id = request.args.get('id', '1')\n"
                    "    query = 'SELECT * FROM users WHERE id=' + user_id\n"
                    "    conn = sqlite3.connect('/tmp/app.db')\n"
                    "    conn.execute(query)\n"
                    "    return 'ok'\n"
                ),
            },
            {
                "path": "poc.py",
                "role": "poc_entry",
                "content": "print('Exploit SUCCESS')\n",
            },
        ],
        "deps": ["Flask==3.0.0"],
        "poc": {"cmd": "python poc.py --base-url {{base_url}}", "success_signature": "Exploit SUCCESS"},
        "pattern_tags": ["sqli"],
    }


def test_guard_engine_manifest_blocks_on_assertion_failure() -> None:
    spec = build_guard_spec(
        sid="sid-test",
        vuln_id="CWE-89",
        slug="cwe-89",
        generator_assertions=[{"op": "file_contains", "path": "app.py", "string": "nonexistent_token"}],
        verifier_assertions=[],
        semantic_signature={
            "input_vector": ["request.args"],
            "sink": ["execute("],
            "exploit_precondition": ["select"],
        },
    )
    engine = GuardEngine("CWE-89", spec.to_dict())
    result = engine.evaluate_manifest(_manifest())
    assert result.passed is False
    assert result.blocking is True
    assert any("guard assertion failed" in item for item in result.violations)


def test_guard_engine_verifier_assertions() -> None:
    spec = build_guard_spec(
        sid="sid-test",
        vuln_id="CWE-89",
        slug="cwe-89",
        generator_assertions=[],
        verifier_assertions=[{"op": "contains", "string": "Exploit SUCCESS"}],
    )
    engine = GuardEngine("CWE-89", spec.to_dict())
    ok = engine.evaluate_verifier_log("... Exploit SUCCESS ...")
    fail = engine.evaluate_verifier_log("no marker")
    assert ok.passed is True
    assert fail.passed is False


def test_unknown_cwe_missing_guard_is_closed_by_default() -> None:
    engine = GuardEngine("CWE-9999", None)
    assert engine.available is False
    assert engine.should_fail_when_missing_spec() is True


def test_compiler_supported_name_family_missing_guard_is_not_closed_by_default() -> None:
    engine = GuardEngine("NAME-OPEN-REDIRECT", None)
    assert engine.available is False
    assert engine.should_fail_when_missing_spec() is False


def test_guard_engine_regex_ops_supported() -> None:
    spec = build_guard_spec(
        sid="sid-test",
        vuln_id="CWE-89",
        slug="cwe-89",
        generator_assertions=[
            {"op": "file_regex_contains", "path": "app.py", "regex": r"request\.args"},
            {"op": "file_regex_not_contains", "path": "app.py", "regex": r"before_first_request"},
            {"op": "file_regex_any", "globs": ["*.py"], "regex": r"Exploit SUCCESS|request\.args"},
        ],
        verifier_assertions=[],
    )
    engine = GuardEngine("CWE-89", spec.to_dict())
    result = engine.evaluate_manifest(_manifest())
    assert result.passed is True
    assert result.blocking is False


def test_guard_engine_file_regex_any_matches_top_level_files_for_recursive_glob() -> None:
    spec = build_guard_spec(
        sid="sid-test",
        vuln_id="CWE-89",
        slug="cwe-89",
        generator_assertions=[
            {"op": "file_regex_any", "globs": ["**/*.py"], "regex": r"request\.args|Exploit SUCCESS"},
        ],
        verifier_assertions=[],
    )
    engine = GuardEngine("CWE-89", spec.to_dict())
    result = engine.evaluate_manifest(_manifest())
    assert result.passed is True
    assert result.blocking is False


def test_guard_engine_accepts_legacy_generator_op_aliases() -> None:
    spec = build_guard_spec(
        sid="sid-test",
        vuln_id="CWE-89",
        slug="cwe-89",
        generator_assertions=[
            {"op": "file_contains_regex", "path": "app.py", "regex": r"request\.args"},
            {"op": "not_file_contains_regex", "path": "app.py", "regex": r"before_first_request"},
            {"op": "regex_any_file", "globs": ["*.py"], "regex": r"request\.args"},
        ],
        verifier_assertions=[],
    )
    engine = GuardEngine("CWE-89", spec.to_dict())
    result = engine.evaluate_manifest(_manifest())
    assert result.passed is True


def test_guard_engine_normalizes_assertion_parameter_aliases() -> None:
    spec = build_guard_spec(
        sid="sid-test",
        vuln_id="CWE-89",
        slug="cwe-89",
        generator_assertions=[
            {"op": "dep_declared", "name": "Flask"},
            {"op": "any_dep_declared", "names": ["foo", "Flask"]},
            {"op": "file_contains", "path": "app.py", "needle": "request.args"},
        ],
        verifier_assertions=[],
    )
    engine = GuardEngine("CWE-89", spec.to_dict())
    result = engine.evaluate_manifest(_manifest())
    assert result.passed is True
    assert result.blocking is False


def test_guard_engine_dep_declared_reads_requirements_file_when_deps_field_missing() -> None:
    manifest = _manifest()
    manifest.pop("deps", None)
    manifest["files"].append(
        {
            "path": "requirements.txt",
            "role": "deps_lock",
            "content": "Flask==3.0.0\nrequests==2.31.0\n",
        }
    )
    spec = build_guard_spec(
        sid="sid-test",
        vuln_id="CWE-89",
        slug="cwe-89",
        generator_assertions=[
            {"op": "dep_declared", "dep": "flask"},
            {"op": "any_dep_declared", "deps": ["foo", "requests"]},
        ],
        verifier_assertions=[],
    )
    engine = GuardEngine("CWE-89", spec.to_dict())
    result = engine.evaluate_manifest(manifest)
    assert result.passed is True
    assert result.blocking is False


def test_guard_engine_warn_severity_is_non_blocking() -> None:
    spec = build_guard_spec(
        sid="sid-test",
        vuln_id="CWE-89",
        slug="cwe-89",
        generator_assertions=[
            {
                "op": "file_contains",
                "path": "app.py",
                "string": "definitely_not_present",
                "severity": "warn",
                "intent": "syntax_hint",
                "stability": "low",
            }
        ],
        verifier_assertions=[],
    )
    engine = GuardEngine("CWE-89", spec.to_dict())
    result = engine.evaluate_manifest(_manifest())
    assert result.passed is True
    assert result.blocking is False
    assert any("guard assertion warning" in item for item in result.warnings)


def test_guard_engine_downgrades_low_stability_syntax_hint_when_builtin_semantics_pass() -> None:
    spec = build_guard_spec(
        sid="sid-test",
        vuln_id="CWE-89",
        slug="cwe-89",
        generator_assertions=[
            {
                "op": "file_regex_contains",
                "path": "app.py",
                "regex": r"never_matching_literal_12345",
                "severity": "block",
                "intent": "syntax_hint",
                "stability": "low",
            }
        ],
        verifier_assertions=[],
        semantic_signature={
            "input_vector": ["request.args"],
            "sink": ["execute("],
            "exploit_precondition": ["select"],
        },
        policy_snapshot={"dynamic_scope": "assertions_semantics"},
    )
    engine = GuardEngine("CWE-89", spec.to_dict())
    result = engine.evaluate_manifest(_manifest())
    assert result.passed is True
    assert result.blocking is False
    downgraded = result.details.get("downgraded_assertions") or []
    assert downgraded


def test_guard_engine_workspace_matches_abstract_sqli_semantics(tmp_path: Path) -> None:
    for entry in _manifest()["files"]:
        path = tmp_path / entry["path"]
        path.write_text(entry["content"], encoding="utf-8")

    spec = build_guard_spec(
        sid="sid-test",
        vuln_id="CWE-89",
        slug="cwe-89",
        generator_assertions=[],
        verifier_assertions=[],
        semantic_signature={
            "input_vector": ["user-controlled request parameter"],
            "sink": ["SQL query execution"],
            "exploit_precondition": ["input concatenated/interpolated into SQL sink"],
        },
    )
    engine = GuardEngine("CWE-89", spec.to_dict())
    result = engine.evaluate_workspace([tmp_path])
    assert result.passed is True
    assert result.blocking is False
    assert result.violations == []


def test_guard_engine_manifest_matches_template_injection_semantics() -> None:
    manifest = {
        "files": [
            {
                "path": "app.py",
                "role": "service_main",
                "content": (
                    "from flask import Flask, request, render_template_string\n"
                    "app = Flask(__name__)\n"
                    "@app.get('/greet')\n"
                    "def greet():\n"
                    "    name = request.args.get('name', '')\n"
                    "    template = f'<h1>Hello {name}</h1>'\n"
                    "    return render_template_string(template)\n"
                ),
            }
        ]
    }
    spec = build_guard_spec(
        sid="sid-test",
        vuln_id="NAME-TEMPLATE-INJECTION",
        slug="name-template-injection",
        generator_assertions=[],
        verifier_assertions=[],
        semantic_signature={
            "input_vector": [
                "request.args",
                "query parameter",
                "user-controlled request parameter",
            ],
            "sink": [
                "render_template_string",
                "jinja2 template rendering from string",
            ],
            "exploit_precondition": [
                "user input is embedded into template source string (concatenation/interpolation)",
                "template string is rendered server-side without escaping/sandboxing",
            ],
        },
    )
    engine = GuardEngine("NAME-TEMPLATE-INJECTION", spec.to_dict())
    result = engine.evaluate_manifest(manifest)
    assert result.passed is True
    assert result.blocking is False
    assert result.violations == []
