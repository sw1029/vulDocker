from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.generator.synthesis import SynthesisEngine, SynthesisLimits
from common.rules import load_rule, load_rulespec


class _DummyLLM:
    def generate(self, messages, *, tools=None) -> str:  # pragma: no cover - not used
        return "{}"


class _BadJsonManifestLLM:
    def __init__(self) -> None:
        self.fixture_used = False
        self.last_used_stub = True
        self.last_provider_attempted = False
        self.last_provider_succeeded = False
        self.last_error_class = "stub"
        self.last_error_message = "synthetic invalid manifest"

    def generate(self, messages, *, tools=None) -> str:
        return '{"files":[{"path":"app.py","content":"print(1)"}],"deps":[],"pattern_tags":[]}'


def _engine(tmp_path: Path, vuln_id: str) -> SynthesisEngine:
    engine = SynthesisEngine(
        sid="sid-test",
        llm=_DummyLLM(),
        limits=SynthesisLimits(),
        workspace=tmp_path / "workspace",
        metadata_dir=tmp_path / "metadata",
        mode="synthesis",
    )
    engine._requirement = {"vuln_id": vuln_id, "language": "python", "runtime": {"python_version": "3.11"}}  # type: ignore[attr-defined]
    engine._load_stdlib_spec()
    engine._rule = load_rule(vuln_id)  # type: ignore[attr-defined]
    engine._rulespec = load_rulespec(vuln_id)  # type: ignore[attr-defined]
    return engine


def test_semantic_guard_rejects_sqli_payload_for_cwe352(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "CWE-352")
    manifest = {
        "files": [
            {
                "path": "app.py",
                "role": "service_main",
                "content": (
                    "from flask import Flask, request\n"
                    "import sqlite3\n"
                    "app = Flask(__name__)\n"
                    "@app.route('/transfer', methods=['GET'])\n"
                    "def transfer():\n"
                    "    amount = request.args.get('amount', '0')\n"
                    "    query = f\"SELECT * FROM tx WHERE amount = {amount}\"\n"
                    "    conn = sqlite3.connect('/tmp/app.db')\n"
                    "    conn.execute(query)\n"
                    "    return 'ok'\n"
                ),
            },
            {
                "path": "poc.py",
                "role": "poc_entry",
                "content": "print('CSRF SUCCESS')\nprint('FLAG-csrf-demo-token')\n",
            },
        ],
        "deps": ["Flask==3.0.0"],
        "poc": {
            "cmd": "python poc.py --base-url {{base_url}}",
            "success_signature": "CSRF SUCCESS",
            "flag_token": "FLAG-csrf-demo-token",
        },
        "pattern_tags": ["guard-test"],
    }
    errors, report = engine._guard_manifest(manifest)
    assert any("semantic mismatch:" in item for item in errors)
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("supported") is True
    assert semantics.get("semantic_match") is False


def test_semantic_guard_rejects_cwe89_without_input_to_sql_path(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "CWE-89")
    manifest = {
        "files": [
            {
                "path": "app.py",
                "role": "service_main",
                "content": (
                    "from flask import Flask\n"
                    "import sqlite3\n"
                    "app = Flask(__name__)\n"
                    "@app.get('/users')\n"
                    "def users():\n"
                    "    query = 'SELECT id, name FROM users'\n"
                    "    conn = sqlite3.connect('/tmp/app.db')\n"
                    "    conn.execute(query)\n"
                    "    return 'ok'\n"
                ),
            },
            {
                "path": "poc.py",
                "role": "poc_entry",
                "content": "print('SQLi SUCCESS')\n",
            },
        ],
        "deps": ["Flask==3.0.0"],
        "poc": {"cmd": "python poc.py --base-url {{base_url}}", "success_signature": "SQLi SUCCESS"},
        "pattern_tags": ["guard-test"],
    }
    errors, report = engine._guard_manifest(manifest)
    assert any("semantic mismatch:" in item for item in errors)
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("supported") is True
    assert semantics.get("semantic_match") is False


def test_semantic_guard_accepts_cwe89_with_tainted_query_flow(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "CWE-89")
    manifest = {
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
                    "    query = 'SELECT id, username FROM users WHERE id = ' + user_id\n"
                    "    conn = sqlite3.connect('/tmp/app.db')\n"
                    "    rows = conn.execute(query).fetchall()\n"
                    "    return {'rows': rows}\n"
                ),
            },
            {
                "path": "poc.py",
                "role": "poc_entry",
                "content": "print('SQLi SUCCESS')\nprint('FLAG-sqli-demo-token')\n",
            },
        ],
        "deps": ["Flask==3.0.0"],
        "poc": {
            "cmd": "python poc.py --base-url {{base_url}}",
            "success_signature": "SQLi SUCCESS",
            "flag_token": "FLAG-sqli-demo-token",
        },
        "pattern_tags": ["guard-test"],
    }
    errors, report = engine._guard_manifest(manifest)
    assert not any("semantic mismatch:" in item for item in errors)
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("supported") is True
    assert semantics.get("semantic_match") is True


def test_semantic_guard_accepts_cwe89_multiline_tainted_query_flow(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "CWE-89")
    manifest = {
        "files": [
            {
                "path": "app.py",
                "role": "service_main",
                "content": (
                    "from flask import Flask, request\n"
                    "import sqlite3\n"
                    "app = Flask(__name__)\n"
                    "@app.get('/login')\n"
                    "def login():\n"
                    "    username = request.args.get('username', '')\n"
                    "    password = request.args.get('password', '')\n"
                    "    query = (\n"
                    "        \"SELECT id, username FROM users \"\n"
                    "        \"WHERE username = '\" + username + \"' AND password = '\" + password + \"'\"\n"
                    "    )\n"
                    "    conn = sqlite3.connect('/tmp/app.db')\n"
                    "    cur = conn.cursor()\n"
                    "    cur.execute(query)\n"
                    "    return 'ok'\n"
                ),
            },
            {
                "path": "poc.py",
                "role": "poc_entry",
                "content": "print('SQLi SUCCESS')\nprint('FLAG-sqli-demo-token')\n",
            },
        ],
        "deps": ["Flask==3.0.0"],
        "poc": {
            "cmd": "python poc.py --base-url {{base_url}}",
            "success_signature": "SQLi SUCCESS",
            "flag_token": "FLAG-sqli-demo-token",
        },
        "pattern_tags": ["guard-test"],
    }
    errors, report = engine._guard_manifest(manifest)
    assert not any("semantic mismatch:" in item for item in errors)
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("supported") is True
    assert semantics.get("semantic_match") is True


def test_semantic_guard_accepts_fastapi_cwe89_with_query_bound_flow(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "CWE-89")
    manifest = {
        "files": [
            {
                "path": "app.py",
                "role": "service_main",
                "content": (
                    "import sqlite3\n"
                    "from fastapi import FastAPI, Query\n"
                    "app = FastAPI()\n"
                    "@app.get('/login')\n"
                    "def login(username: str = Query(default=''), password: str = Query(default='')):\n"
                    "    query = \"SELECT id, username FROM users WHERE username = '\" + username + \"' AND password = '\" + password + \"'\"\n"
                    "    conn = sqlite3.connect('/tmp/app.db')\n"
                    "    conn.execute(query)\n"
                    "    return {'ok': True}\n"
                ),
            },
            {
                "path": "poc.py",
                "role": "poc_entry",
                "content": "print('SQLi SUCCESS')\nprint('FLAG-sqli-demo-token')\n",
            },
        ],
        "deps": ["fastapi==0.115.0", "uvicorn==0.30.6"],
        "poc": {
            "cmd": "python poc.py --base-url {{base_url}}",
            "success_signature": "SQLi SUCCESS",
            "flag_token": "FLAG-sqli-demo-token",
        },
        "pattern_tags": ["guard-test"],
    }
    errors, report = engine._guard_manifest(manifest)
    assert not any("semantic mismatch:" in item for item in errors)
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("supported") is True
    assert semantics.get("semantic_match") is True


def test_family_aware_fallback_manifest_for_cwe89_passes_guard(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "CWE-89")
    manifest = engine._fallback_manifest()

    errors, report = engine._guard_manifest(manifest)

    assert not any("semantic mismatch:" in item for item in errors)
    assert manifest["metadata"]["generation_origin"] == "deterministic_fallback"
    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    poc_entry = next(entry for entry in manifest["files"] if entry.get("role") == "poc_entry")
    assert "Asset-backed family-aware fallback template for SQLi." in service_main["content"]
    assert "Asset-backed family-aware fallback template for SQLi." in poc_entry["content"]
    assert "SELECT id, username FROM users" in service_main["content"]
    assert "cur.execute(query)" in service_main["content"]
    assert "SQLi SUCCESS" in poc_entry["content"]
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("supported") is True
    assert semantics.get("semantic_match") is True


def test_family_aware_fallback_manifest_for_cwe352_passes_guard(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "CWE-352")
    manifest = engine._fallback_manifest()

    errors, report = engine._guard_manifest(manifest)

    assert not any("semantic mismatch:" in item for item in errors)
    assert manifest["metadata"]["generation_origin"] == "deterministic_fallback"
    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    poc_entry = next(entry for entry in manifest["files"] if entry.get("role") == "poc_entry")
    assert "Asset-backed family-aware fallback template for CSRF." in service_main["content"]
    assert "Asset-backed family-aware fallback template for CSRF." in poc_entry["content"]
    assert "@app.post('/transfer')" in service_main["content"]
    assert "session['user'] = user" in service_main["content"]
    assert "CSRF SUCCESS" in poc_entry["content"]
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("supported") is True
    assert semantics.get("semantic_match") is True


def test_family_aware_fallback_manifest_for_cwe79_passes_guard(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "CWE-79")
    manifest = engine._fallback_manifest()

    errors, report = engine._guard_manifest(manifest)

    assert not any("semantic mismatch:" in item for item in errors)
    assert manifest["metadata"]["generation_origin"] == "deterministic_fallback"
    assert manifest["metadata"]["fallback_class"] == "family_aware"
    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    poc_entry = next(entry for entry in manifest["files"] if entry.get("role") == "poc_entry")
    assert "Asset-backed family-aware fallback template for XSS." in service_main["content"]
    assert "Asset-backed family-aware fallback template for XSS." in poc_entry["content"]
    assert "render_template_string" in service_main["content"]
    assert "cross-site scripting" in service_main["content"].lower()
    assert "<script>alert(1)</script>" in poc_entry["content"]
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("supported") is True
    assert semantics.get("semantic_match") is True


def test_dynamic_eval_semantic_guided_fallback_prefers_minimal_dynamic_materializer_for_xss(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "CWE-79")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "xss",
            "top_confidence": "high",
            "contradiction_count": 0,
            "ambiguous": False,
        }
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.args", "query parameter", "user input"],
            "sink": ["render_template_string", "template response"],
            "exploit_precondition": ["<script>", "unescaped reflection", "cross-site scripting"],
        }
    }

    manifest = engine._fallback_manifest()
    errors, report = engine._guard_manifest(manifest)

    assert manifest["metadata"]["fallback_class"] == "semantic_guided"
    assert manifest["metadata"]["semantic_guided_family"] == "xss"
    assert manifest["metadata"]["materializer"] == "minimal_dynamic"
    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    poc_entry = next(entry for entry in manifest["files"] if entry.get("role") == "poc_entry")
    assert "render_template_string" in service_main["content"]
    assert "template = f'<html><body>{name}</body></html>'" in service_main["content"]
    assert "request.args.get('name'" in service_main["content"]
    assert "/echo?name=" in poc_entry["content"]
    assert not any("semantic mismatch:" in item for item in errors)
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("semantic_match") is True


def test_family_aware_fallback_manifest_for_template_injection_uses_asset_templates(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "NAME-TEMPLATE-INJECTION")
    engine._requirement["policy"] = {"allow_name_family_fallback": True}  # type: ignore[index]
    manifest = engine._fallback_manifest()

    errors, report = engine._guard_manifest(manifest)

    assert not any("semantic mismatch:" in item for item in errors)
    assert manifest["metadata"]["fallback_class"] == "family_aware"
    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    poc_entry = next(entry for entry in manifest["files"] if entry.get("role") == "poc_entry")
    assert "Asset-backed family-aware fallback template for Template Injection." in service_main["content"]
    assert "Asset-backed family-aware fallback template for Template Injection." in poc_entry["content"]
    assert "render_template_string" in service_main["content"]
    assert "{{7*7}}" in poc_entry["content"]
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("supported") is True
    assert semantics.get("semantic_match") is True


def test_generic_unsupported_fallback_manifest_uses_asset_templates(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "NAME-CUSTOM-WEIRD-VULN")
    engine._requirement["staged_synthesis"] = {  # type: ignore[index]
        "schema_version": "staged_synthesis@0.1",
        "stage_order": ["candidate_resolution", "design_brief", "runtime_plan", "oracle_contract"],
        "design_brief": {
            "selected_topology": "service_plus_sidecar",
            "selected_oracle_mode": "stateful_text",
            "selected_oracle_source": "researcher_verification_spec",
            "dependency_set": ["service", "db:mysql"],
            "required_roles": [
                "service_main",
                "poc_entry",
                "dependency_db",
                "dependency_sidecar",
                "oracle_state_checks",
            ],
        },
    }
    manifest = engine._fallback_manifest()

    assert manifest["metadata"]["fallback_class"] == "generic_unsupported_family"
    assert manifest["metadata"]["design_brief_topology"] == "service_plus_sidecar"
    assert manifest["metadata"]["design_brief_oracle_mode"] == "stateful_text"
    assert manifest["metadata"]["design_brief_oracle_source"] == "researcher_verification_spec"
    assert manifest["metadata"]["design_brief_required_roles"] == [
        "service_main",
        "poc_entry",
        "dependency_db",
        "dependency_sidecar",
        "oracle_state_checks",
    ]
    assert manifest["metadata"]["design_brief_dependency_set"] == ["service", "db:mysql"]
    assert manifest["metadata"]["target_topology"] == "service_plus_sidecar"
    assert manifest["metadata"]["target_db"] == "mysql"
    assert manifest["metadata"]["target_sidecars"] == ["mysql"]
    dockerfile = next(entry for entry in manifest["files"] if entry.get("path") == "Dockerfile")
    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    poc_entry = next(entry for entry in manifest["files"] if entry.get("role") == "poc_entry")
    readme = next(entry for entry in manifest["files"] if entry.get("path") == "README.md")
    assert "Asset-backed fallback bundle Dockerfile template." in dockerfile["content"]
    assert "Asset-backed generic unsupported fallback service template." in service_main["content"]
    assert "Asset-backed generic unsupported fallback PoC template." in poc_entry["content"]
    assert "Asset-backed fallback bundle README template." in readme["content"]


def test_explicit_unknown_cwe_with_known_pattern_id_uses_generic_fallback(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "CWE-9999")
    engine._requirement["pattern_id"] = "sqli-string-concat"  # type: ignore[index]
    engine._requirement["vuln_name"] = "CWE-9999"  # type: ignore[index]

    manifest = engine._fallback_manifest()

    assert manifest["metadata"]["fallback_class"] == "generic_unsupported_family"
    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    assert "Asset-backed generic unsupported fallback service template." in service_main["content"]


def test_family_aware_fallback_manifest_for_cwe918_passes_guard(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "CWE-918")
    manifest = engine._fallback_manifest()

    errors, report = engine._guard_manifest(manifest)

    assert not any("semantic mismatch:" in item for item in errors)
    assert manifest["metadata"]["fallback_class"] == "family_aware"
    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    poc_entry = next(entry for entry in manifest["files"] if entry.get("role") == "poc_entry")
    assert "Asset-backed family-aware fallback template for SSRF." in service_main["content"]
    assert "Asset-backed family-aware fallback template for SSRF." in poc_entry["content"]
    assert "requests.get" in service_main["content"]
    assert "/metadata" in service_main["content"]
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("supported") is True
    assert semantics.get("semantic_match") is True


def test_family_aware_fallback_manifest_for_open_redirect_uses_asset_templates(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "NAME-OPEN-REDIRECT")
    engine._requirement["policy"] = {"allow_name_family_fallback": True}  # type: ignore[index]
    manifest = engine._fallback_manifest()

    errors, report = engine._guard_manifest(manifest)

    assert not any("semantic mismatch:" in item for item in errors)
    assert manifest["metadata"]["fallback_class"] == "family_aware"
    dockerfile = next(entry for entry in manifest["files"] if entry.get("path") == "Dockerfile")
    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    poc_entry = next(entry for entry in manifest["files"] if entry.get("role") == "poc_entry")
    readme = next(entry for entry in manifest["files"] if entry.get("path") == "README.md")
    assert "Asset-backed fallback bundle Dockerfile template." in dockerfile["content"]
    assert "Asset-backed family-aware fallback template for Open Redirect." in service_main["content"]
    assert "Asset-backed family-aware fallback template for Open Redirect." in poc_entry["content"]
    assert "Asset-backed fallback bundle README template." in readme["content"]
    assert "Verification markers" in readme["content"]
    assert "Success signature: `Exploit SUCCESS`" in readme["content"]
    assert "Flag token: `FLAG{OPEN_REDIRECT_OK}`" in readme["content"]
    assert "Runtime expects a single-service HTTP container on port `8000`." in readme["content"]
    assert "redirect(next_url, code=302)" in service_main["content"]
    assert "allow_redirects=False" in poc_entry["content"]
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("supported") is True
    assert semantics.get("semantic_match") is True


def test_name_only_family_fallback_is_disabled_by_default(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "NAME-OPEN-REDIRECT")

    manifest = engine._fallback_manifest()

    assert manifest["metadata"]["fallback_class"] == "generic_unsupported_family"
    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    assert "Asset-backed generic unsupported fallback service template." in service_main["content"]


def test_canonicalized_name_driven_family_fallback_is_disabled_by_default(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "CWE-79")
    engine._requirement["request_ir"] = {  # type: ignore[index]
        "request_label": "Reflected XSS",
        "resolved_vuln_id": "CWE-79",
        "resolution_state": "catalog_alias",
        "resolution_confidence": "high",
        "name_driven": True,
    }

    manifest = engine._fallback_manifest()

    assert manifest["metadata"]["fallback_class"] == "generic_unsupported_family"
    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    assert "Asset-backed generic unsupported fallback service template." in service_main["content"]
    assert "Asset-backed family-aware fallback template for XSS." not in service_main["content"]


def test_canonicalized_name_driven_family_fallback_can_be_enabled_explicitly(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "CWE-79")
    engine._requirement["request_ir"] = {  # type: ignore[index]
        "request_label": "Reflected XSS",
        "resolved_vuln_id": "CWE-79",
        "resolution_state": "catalog_alias",
        "resolution_confidence": "high",
        "name_driven": True,
    }
    engine._requirement["policy"] = {"allow_name_family_fallback": True}  # type: ignore[index]

    manifest = engine._fallback_manifest()

    assert manifest["metadata"]["fallback_class"] == "family_aware"
    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    assert "Asset-backed family-aware fallback template for XSS." in service_main["content"]


def test_dynamic_eval_semantic_guided_fallback_prefers_minimal_dynamic_materializer_for_open_redirect(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "NAME-CUSTOM-OPEN-REDIRECT")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "open_redirect",
            "top_confidence": "high",
            "contradiction_count": 0,
            "ambiguous": False,
        }
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.args", "next parameter"],
            "sink": ["redirect(", "location header"],
            "exploit_precondition": ["open redirect", "external redirect"],
        }
    }

    manifest = engine._fallback_manifest()

    assert manifest["metadata"]["fallback_class"] == "semantic_guided"
    assert manifest["metadata"]["semantic_guided_family"] == "open_redirect"
    assert manifest["metadata"]["materializer"] == "minimal_dynamic"
    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    readme = next(entry for entry in manifest["files"] if entry.get("path") == "README.md")
    assert "def bounce():" in service_main["content"]
    assert "return redirect(next_url, code=302)" in service_main["content"]
    assert "Asset-backed family-aware fallback template for Open Redirect." not in service_main["content"]
    assert "Verification markers" in readme["content"]
    assert "Success signature: `Exploit SUCCESS`" in readme["content"]


def test_dynamic_eval_semantic_guided_fallback_can_emit_fastapi_minimal_dynamic(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "NAME-CUSTOM-OPEN-REDIRECT")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._requirement["runtime_recipe"] = {  # type: ignore[index]
        "language": "python",
        "framework": "fastapi",
    }
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "open_redirect",
            "top_confidence": "high",
            "contradiction_count": 0,
            "ambiguous": False,
        },
        "tech_stack_candidates": [
            {"language": "python", "framework": "fastapi", "stack_id": "python/fastapi", "confidence": "medium"}
        ],
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.args", "next parameter"],
            "sink": ["redirect(", "location header"],
            "exploit_precondition": ["open redirect", "external redirect"],
        }
    }

    manifest = engine._fallback_manifest()

    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    requirements = next(entry for entry in manifest["files"] if entry.get("path") == "requirements.txt")
    assert "from fastapi import FastAPI" in service_main["content"]
    assert "RedirectResponse" in service_main["content"]
    assert "uvicorn.run(app" in service_main["content"]
    assert "fastapi==" in requirements["content"].lower()
    assert "uvicorn==" in requirements["content"].lower()


def test_dynamic_eval_semantic_guided_fallback_can_use_unambiguous_researcher_stack_candidate(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "NAME-CUSTOM-OPEN-REDIRECT")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "open_redirect",
            "top_confidence": "high",
            "contradiction_count": 0,
            "ambiguous": False,
        },
        "tech_stack_candidates": [
            {"language": "python", "framework": "fastapi", "stack_id": "python/fastapi", "confidence": "medium"}
        ],
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.args", "next parameter"],
            "sink": ["redirect(", "location header"],
            "exploit_precondition": ["open redirect", "external redirect"],
        }
    }

    manifest = engine._fallback_manifest()

    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    assert "from fastapi import FastAPI" in service_main["content"]
    assert manifest["metadata"]["materializer"] == "minimal_dynamic"


def test_request_identity_guided_family_accepts_single_medium_family_candidate_for_synthetic_name(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "NAME-UNSAFE-REDIRECT")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._requirement["request_ir"] = {  # type: ignore[index]
        "request_label": "Unsafe Redirect",
        "resolved_vuln_id": "NAME-UNSAFE-REDIRECT",
        "name_driven": True,
        "resolution_state": "synthetic_name",
        "resolution_confidence": "low",
        "family_candidates": [
            {"family": "open_redirect", "confidence": "medium", "source": "label_overlap"}
        ],
    }

    assert engine._request_identity_guided_family() == "open_redirect"


def test_request_identity_guided_family_keeps_ambiguous_synthetic_name_unresolved(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "NAME-CROSS-SITE-INJECTION")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._requirement["request_ir"] = {  # type: ignore[index]
        "request_label": "Cross Site Injection",
        "resolved_vuln_id": "NAME-CROSS-SITE-INJECTION",
        "name_driven": True,
        "resolution_state": "synthetic_name",
        "resolution_confidence": "low",
        "family_candidates": [
            {"family": "xss", "confidence": "low", "source": "label_overlap"},
            {"family": "csrf", "confidence": "low", "source": "label_overlap"},
        ],
    }

    assert engine._request_identity_guided_family() == ""


def test_dynamic_eval_semantic_guided_fallback_ignores_ambiguous_researcher_stack_candidates(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "NAME-CUSTOM-OPEN-REDIRECT")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._requirement["stack_hypotheses"] = [  # type: ignore[index]
        {"language": "python", "framework": "flask", "stack_id": "python/flask", "source": "profile_prior", "confidence": "low"},
        {"language": "python", "framework": "fastapi", "stack_id": "python/fastapi", "source": "available_skeleton", "confidence": "low"},
    ]
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "open_redirect",
            "top_confidence": "high",
            "contradiction_count": 0,
            "ambiguous": False,
        },
        "tech_stack_candidates": [
            {"language": "python", "framework": "fastapi", "stack_id": "python/fastapi", "confidence": "medium"},
            {"language": "python", "framework": "flask", "stack_id": "python/flask", "confidence": "medium"},
        ],
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.args", "next parameter"],
            "sink": ["redirect(", "location header"],
            "exploit_precondition": ["open redirect", "external redirect"],
        }
    }

    manifest = engine._fallback_manifest()

    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    assert "from flask import Flask" in service_main["content"]
    assert "from fastapi import FastAPI" not in service_main["content"]
    assert manifest["metadata"]["materializer"] == "minimal_dynamic"


def test_dynamic_eval_semantic_guided_fallback_is_blocked_by_ambiguous_family_hypothesis(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "NAME-CUSTOM-OPEN-REDIRECT")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "template_injection",
            "top_confidence": "low",
            "contradiction_count": 3,
            "ambiguous": True,
        }
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.args", "next parameter"],
            "sink": ["redirect(", "location header"],
            "exploit_precondition": ["open redirect", "external redirect"],
        }
    }

    manifest = engine._fallback_manifest()

    assert manifest["metadata"]["fallback_class"] == "generic_unsupported_family"


def test_dynamic_eval_semantic_guided_fallback_abstains_on_overlapping_family_matches_without_disambiguator(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "NAME-CUSTOM-AMBIGUOUS")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "xss",
            "top_confidence": "low",
            "top_margin": 0.02,
            "contradiction_count": 2,
            "ambiguous": True,
        }
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.args", "template payload"],
            "sink": ["render_template_string"],
            "exploit_precondition": ["cross-site scripting", "server-side template injection"],
        }
    }

    manifest = engine._fallback_manifest()

    assert manifest["metadata"]["fallback_class"] == "generic_unsupported_family"
    assert manifest["metadata"]["semantic_guided_abstain_reason"] == "ambiguous_semantic_family_match"
    assert manifest["metadata"]["semantic_guided_candidate_families"] == ["template_injection", "xss"]
    assert manifest["metadata"]["semantic_guided_ambiguous"] is True


def test_dynamic_eval_semantic_guided_fallback_can_use_design_brief_dependency_db_when_semantics_missing(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "NAME-CUSTOM-DB-THING")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._requirement["staged_synthesis"] = {  # type: ignore[index]
        "schema_version": "staged_synthesis@0.1",
        "stage_order": ["candidate_resolution", "design_brief", "runtime_plan", "oracle_contract"],
        "design_brief": {
            "selected_topology": "single_service",
            "dependency_set": ["service", "db:sqlite"],
            "required_roles": ["service_main", "poc_entry", "dependency_db"],
        },
    }
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "sqli",
            "top_confidence": "medium",
            "contradiction_count": 0,
            "ambiguous": False,
        }
    }
    engine._guard_spec_payload = {}  # type: ignore[attr-defined]

    manifest = engine._fallback_manifest()
    errors, report = engine._guard_manifest(manifest)

    assert manifest["metadata"]["fallback_class"] == "semantic_guided"
    assert manifest["metadata"]["semantic_guided_family"] == "sqli"
    assert manifest["metadata"]["semantic_guided_selection_source"] == "design_brief_dependency_db"
    assert manifest["metadata"]["semantic_guided_candidate_families"] == ["sqli"]
    assert manifest["metadata"]["materializer"] == "minimal_dynamic"
    assert manifest["metadata"]["design_brief_topology"] == "single_service"
    assert manifest["metadata"]["design_brief_dependency_set"] == ["service", "db:sqlite"]
    assert manifest["metadata"]["design_brief_required_roles"] == ["service_main", "poc_entry", "dependency_db"]
    assert manifest["metadata"]["target_topology"] == "single_service"
    assert manifest["metadata"]["target_db"] == "sqlite"
    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    assert "sqlite3.connect(DB_PATH)" in service_main["content"]
    assert not any("semantic mismatch:" in item for item in errors)
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("semantic_match") is True


def test_dynamic_eval_semantic_guided_fallback_can_use_researcher_top_family_when_semantic_signature_missing(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "NAME-CUSTOM-CSRF")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "csrf",
            "top_confidence": "high",
            "contradiction_count": 0,
            "ambiguous": False,
        }
    }
    engine._guard_spec_payload = {}  # type: ignore[attr-defined]

    manifest = engine._fallback_manifest()
    errors, report = engine._guard_manifest(manifest)

    assert manifest["metadata"]["fallback_class"] == "semantic_guided"
    assert manifest["metadata"]["semantic_guided_family"] == "csrf"
    assert manifest["metadata"]["semantic_guided_selection_source"] == "researcher_top_family_no_semantic_signature"
    assert manifest["metadata"]["semantic_guided_candidate_families"] == ["csrf"]
    assert manifest["metadata"]["materializer"] == "minimal_dynamic"
    assert not any("semantic mismatch:" in item for item in errors)
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("semantic_match") is True


def test_dynamic_eval_semantic_guided_fallback_abstains_when_semantic_signature_missing_and_top_family_is_ambiguous(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "NAME-CUSTOM-CSRF")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "csrf",
            "top_confidence": "high",
            "contradiction_count": 0,
            "ambiguous": True,
        }
    }
    engine._guard_spec_payload = {}  # type: ignore[attr-defined]

    manifest = engine._fallback_manifest()

    assert manifest["metadata"]["fallback_class"] == "generic_unsupported_family"
    assert manifest["metadata"]["semantic_guided_abstain_reason"] == "no_semantic_family_match"


def test_dynamic_eval_semantic_guided_fallback_tolerates_minor_contradiction_with_clear_margin(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "NAME-CUSTOM-OPEN-REDIRECT")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "open_redirect",
            "top_confidence": "high",
            "top_margin": 0.34,
            "contradiction_count": 1,
            "ambiguous": False,
        }
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.args", "next parameter"],
            "sink": ["redirect(", "location header"],
            "exploit_precondition": ["open redirect", "external redirect"],
        }
    }

    manifest = engine._fallback_manifest()

    assert manifest["metadata"]["fallback_class"] == "semantic_guided"
    assert manifest["metadata"]["semantic_guided_family"] == "open_redirect"
    assert manifest["metadata"]["materializer"] == "minimal_dynamic"


def test_dynamic_eval_semantic_guided_open_redirect_manifest_includes_verification_spec(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "NAME-CUSTOM-OPEN-REDIRECT")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "open_redirect",
            "top_confidence": "high",
            "top_margin": 0.34,
            "contradiction_count": 0,
            "ambiguous": False,
        }
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.args", "next parameter"],
            "sink": ["redirect(", "location header"],
            "exploit_precondition": ["open redirect", "external redirect"],
        }
    }

    manifest = engine._fallback_manifest()
    verification_spec = manifest.get("verification_spec") or {}

    assert manifest["metadata"]["fallback_class"] == "semantic_guided"
    assert verification_spec["negative_controls"][0]["name"] == "missing-next"
    assert verification_spec["negative_controls"][0]["payload"] == "/local"
    assert verification_spec["metamorphic"]["passed"] == 1
    assert verification_spec["metamorphic"]["cases"] == [
        {"name": "same-origin-relative", "expect_success": False, "payload": "/profile"}
    ]
    assert "open redirect exploit success" in verification_spec["metamorphic"]["rationale"]
    assert manifest["poc"]["cmd"] == "python poc.py --base-url {{base_url}} --payload {{payload}}"


def test_stateless_minimal_dynamic_manifests_include_payload_replay_verification_specs(tmp_path: Path) -> None:
    cases = [
        {
            "family": "xss",
            "vuln_id": "CWE-79",
            "negative_payload": "hello",
            "metamorphic_payload": "<img src=x onerror=alert(1)>",
            "guard_signature": {
                "input_vector": ["request.args", "query parameter", "user input"],
                "sink": ["render_template_string", "template response"],
                "exploit_precondition": ["<script>", "unescaped reflection", "cross-site scripting"],
            },
        },
        {
            "family": "path_traversal",
            "vuln_id": "NAME-CUSTOM-PATH-TRAVERSAL",
            "negative_payload": "note.txt",
            "metamorphic_payload": ".././secret.txt",
            "guard_signature": {
                "input_vector": ["request.args", "path parameter"],
                "sink": ["open(", "os.path.join"],
                "exploit_precondition": ["path traversal", "../"],
            },
        },
        {
            "family": "ssrf",
            "vuln_id": "NAME-CUSTOM-SSRF",
            "negative_payload": "/health",
            "metamorphic_payload": "/metadata?from=probe",
            "guard_signature": {
                "input_vector": ["request.args", "url parameter"],
                "sink": ["requests.get", "http client request"],
                "exploit_precondition": ["server-side request forgery"],
            },
        },
        {
            "family": "command_injection",
            "vuln_id": "CWE-78",
            "negative_payload": "echo safe",
            "metamorphic_payload": "printf FLAG-command-injection-demo-token",
            "guard_signature": {
                "input_vector": ["request.args", "command parameter"],
                "sink": ["subprocess", "shell=True"],
                "exploit_precondition": ["command injection", "user input in command"],
            },
        },
        {
            "family": "code_injection",
            "vuln_id": "CWE-94",
            "negative_payload": "0",
            "metamorphic_payload": "str(FLAG_TOKEN)",
            "guard_signature": {
                "input_vector": ["request.args", "code parameter"],
                "sink": ["eval(", "exec("],
                "exploit_precondition": ["code injection", "user input reaches eval"],
            },
        },
        {
            "family": "ldap_injection",
            "vuln_id": "NAME-LDAP-INJECTION",
            "negative_payload": "guest",
            "metamorphic_payload": "*",
            "guard_signature": {
                "input_vector": ["request.args", "ldap user parameter"],
                "sink": ["LDAP filter construction", "directory search", "search_directory("],
                "exploit_precondition": ["ldap injection", "filter bypass via wildcard or OR clause"],
            },
        },
        {
            "family": "template_injection",
            "vuln_id": "NAME-CUSTOM-TEMPLATE-INJECTION",
            "negative_payload": "friend",
            "metamorphic_payload": "{{6*7}}",
            "guard_signature": {
                "input_vector": ["request.args", "template variable", "name parameter"],
                "sink": ["render_template_string", "Template("],
                "exploit_precondition": ["template injection", "server-side expression evaluation", "{{7*7}}"],
            },
        },
        {
            "family": "csrf",
            "vuln_id": "NAME-CUSTOM-CSRF",
            "negative_payload": "0",
            "metamorphic_payload": "250",
            "guard_signature": {
                "input_vector": ["cross-site request", "cookie-authenticated session"],
                "sink": ["state-changing endpoint (POST/PUT/DELETE/PATCH)"],
                "exploit_precondition": ["missing csrf token validation"],
            },
        },
        {
            "family": "deserialization",
            "vuln_id": "NAME-CUSTOM-DESERIALIZATION",
            "negative_payload": "echo safe",
            "metamorphic_payload": "printf FLAG{DESER_OK}",
            "guard_signature": {
                "input_vector": ["request.body", "serialized payload"],
                "sink": ["pickle.loads", "unsafe deserialization"],
                "exploit_precondition": ["deserialization", "attacker-controlled pickle payload"],
            },
        },
        {
            "family": "xxe",
            "vuln_id": "NAME-XXE",
            "negative_payload": "file:///etc/hostname",
            "metamorphic_payload": "file:///tmp/./xxe-secret.txt",
            "guard_signature": {
                "input_vector": ["request.body", "xml payload"],
                "sink": ["etree.fromstring", "resolve_entities=True"],
                "exploit_precondition": ["xxe", "external entity resolution"],
            },
        },
    ]

    for case in cases:
        engine = _engine(tmp_path / case["family"], case["vuln_id"])
        engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
        engine._researcher_report_payload = {  # type: ignore[attr-defined]
            "family_hypothesis_summary": {
                "top_family": case["family"],
                "top_confidence": "high",
                "contradiction_count": 0,
                "ambiguous": False,
            }
        }
        engine._guard_spec_payload = {  # type: ignore[attr-defined]
            "semantic_signature": case["guard_signature"]
        }

        manifest = engine._fallback_manifest()
        verification_spec = manifest.get("verification_spec") or {}
        poc_entry = next(entry for entry in manifest["files"] if entry.get("role") == "poc_entry")

        assert manifest["metadata"]["fallback_class"] == "semantic_guided"
        assert manifest["metadata"]["semantic_guided_family"] == case["family"]
        assert manifest["poc"]["cmd"] == "python poc.py --base-url {{base_url}} --payload {{payload}}"
        assert verification_spec["negative_controls"][0]["payload"] == case["negative_payload"]
        assert verification_spec["metamorphic"]["cases"][0]["payload"] == case["metamorphic_payload"]
        assert "parser.add_argument('--payload'" in poc_entry["content"]


def test_dynamic_eval_semantic_guided_fallback_can_emit_fastapi_xss_minimal_dynamic(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "CWE-79")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._requirement["runtime_recipe"] = {  # type: ignore[index]
        "language": "python",
        "framework": "fastapi",
    }
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "xss",
            "top_confidence": "high",
            "contradiction_count": 0,
            "ambiguous": False,
        },
        "tech_stack_candidates": [
            {"language": "python", "framework": "fastapi", "stack_id": "python/fastapi", "confidence": "medium"}
        ],
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.args", "query parameter", "user input"],
            "sink": ["render_template_string", "template response"],
            "exploit_precondition": ["<script>", "unescaped reflection", "cross-site scripting"],
        }
    }

    manifest = engine._fallback_manifest()

    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    poc_entry = next(entry for entry in manifest["files"] if entry.get("role") == "poc_entry")
    assert "def echo(name: str = '')" in service_main["content"]
    assert "/echo?name=" in poc_entry["content"]
    assert "parser.add_argument('--payload'" in poc_entry["content"]


def test_dynamic_eval_semantic_guided_fallback_can_use_request_identity_when_research_is_degraded(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "NAME-OPEN-REDIRECT")
    engine._requirement["policy"] = {"name_only_mode": "dynamic"}  # type: ignore[index]
    engine._requirement["request_identity"] = {  # type: ignore[index]
        "request_label": "Open Redirect",
        "resolved_vuln_id": "NAME-OPEN-REDIRECT",
        "match_class": "catalog_alias",
        "confidence": "high",
        "name_driven": True,
    }
    engine._requirement["name_resolution"] = {  # type: ignore[index]
        "resolved_vuln_id": "NAME-OPEN-REDIRECT",
        "match_class": "catalog_alias",
        "confidence": "high",
    }
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "search_degraded": True,
        "quality_reason": "Low evidence relevance for NAME-OPEN-REDIRECT; using guard fallback mode with static/minimal assertions.",
        "evidence_relevance": {"confidence": "low"},
        "family_hypothesis_summary": {
            "top_family": "sqli",
            "top_confidence": "low",
            "contradiction_count": 0,
            "ambiguous": False,
        },
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.args", "next parameter"],
            "sink": ["redirect(", "location header"],
            "exploit_precondition": ["open redirect", "external redirect"],
        }
    }

    manifest = engine._fallback_manifest()

    assert manifest["metadata"]["fallback_class"] == "semantic_guided"
    assert manifest["metadata"]["semantic_guided_family"] == "open_redirect"
    assert manifest["metadata"]["materializer"] == "minimal_dynamic"


def test_dynamic_eval_semantic_guided_fallback_can_use_request_ir_when_ranked_family_support_is_high(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "CWE-94")
    engine._requirement["policy"] = {"name_only_mode": "dynamic"}  # type: ignore[index]
    engine._requirement["request_ir"] = {  # type: ignore[index]
        "request_label": "Code Injection",
        "resolved_vuln_id": "CWE-94",
        "resolution_state": "catalog_alias",
        "resolution_confidence": "high",
        "name_driven": True,
        "family_candidates": [
            {
                "family": "code_injection",
                "source": "catalog_resolution",
                "confidence": "high",
            }
        ],
    }
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "search_degraded": False,
        "quality_reason": "sufficient evidence",
        "evidence_relevance": {"confidence": "high"},
        "family_hypothesis_summary": {
            "top_family": "sqli",
            "top_confidence": "low",
            "top_margin": 0.07,
            "ambiguous": True,
            "contradiction_count": 2,
            "ranked_families": [
                {
                    "family": "sqli",
                    "confidence": "low",
                },
                {
                    "family": "code_injection",
                    "confidence": "high",
                    "bases": [{"basis": "vuln_id", "confidence": "high"}],
                },
            ],
        },
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.args", "code parameter"],
            "sink": ["eval(", "exec("],
            "exploit_precondition": ["code injection", "user input reaches eval"],
        }
    }

    manifest = engine._fallback_manifest()

    assert manifest["metadata"]["fallback_class"] == "semantic_guided"
    assert manifest["metadata"]["semantic_guided_family"] == "code_injection"
    assert manifest["metadata"]["materializer"] == "minimal_dynamic"


def test_dynamic_eval_semantic_guided_fallback_can_use_request_resolution_to_disambiguate_overlapping_matches(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "NAME-TEMPLATE-INJECTION")
    engine._requirement["policy"] = {"name_only_mode": "dynamic"}  # type: ignore[index]
    engine._requirement["request_ir"] = {  # type: ignore[index]
        "request_label": "Template Injection",
        "resolved_vuln_id": "NAME-TEMPLATE-INJECTION",
        "resolution_state": "catalog_alias",
        "resolution_match_class": "catalog_alias",
        "resolution_confidence": "high",
        "name_driven": True,
        "family_candidates": [
            {"family": "template_injection", "source": "catalog_resolution", "confidence": "high"}
        ],
    }
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "search_degraded": True,
        "quality_reason": "guard fallback mode due to degraded retrieval",
        "evidence_relevance": {"confidence": "low"},
        "family_hypothesis_summary": {
            "top_family": "xss",
            "top_confidence": "low",
            "top_margin": 0.01,
            "ambiguous": True,
            "contradiction_count": 2,
        },
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.args", "template payload"],
            "sink": ["render_template_string"],
            "exploit_precondition": ["cross-site scripting", "server-side template injection"],
        }
    }

    manifest = engine._fallback_manifest()

    assert manifest["metadata"]["fallback_class"] == "semantic_guided"
    assert manifest["metadata"]["semantic_guided_family"] == "template_injection"
    assert manifest["metadata"]["semantic_guided_selection_source"] == "request_resolution"
    assert manifest["metadata"]["semantic_guided_candidate_families"] == ["template_injection", "xss"]
    assert manifest["metadata"]["semantic_guided_ambiguous"] is True


def test_dynamic_eval_semantic_guided_fallback_prefers_request_ir_selection_when_evidence_ready(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "NAME-TEMPLATE-INJECTION")
    engine._requirement["policy"] = {"name_only_mode": "dynamic"}  # type: ignore[index]
    engine._requirement["request_ir"] = {  # type: ignore[index]
        "request_label": "Template Injection",
        "resolved_vuln_id": "NAME-TEMPLATE-INJECTION",
        "resolution_state": "catalog_alias",
        "resolution_match_class": "catalog_alias",
        "resolution_confidence": "high",
        "name_driven": True,
        "family_candidates": [
            {"family": "template_injection", "source": "catalog_resolution", "confidence": "high"}
        ],
        "selection_decision": {
            "family": {
                "selected": True,
                "selected_family": "template_injection",
                "support_count": 4,
                "support_by_source_authority": {"medium": 3, "high": 1},
                "evidence_backed": True,
                "high_or_medium_authority_support": True,
            },
            "stack": {
                "selected": True,
                "selected_stack_id": "python/flask",
                "basis": "researcher_top_candidate",
                "support_count": 2,
                "support_by_source_authority": {"medium": 2},
                "evidence_backed": True,
                "high_or_medium_authority_support": True,
            },
            "ready_for_materialization": True,
            "open_world_evidence_ready": True,
        },
    }
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "search_degraded": True,
        "quality_reason": "guard fallback mode due to degraded retrieval",
        "evidence_relevance": {"confidence": "low"},
        "family_hypothesis_summary": {
            "top_family": "xss",
            "top_confidence": "low",
            "top_margin": 0.01,
            "ambiguous": True,
            "contradiction_count": 2,
        },
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.args", "template payload"],
            "sink": ["render_template_string"],
            "exploit_precondition": ["cross-site scripting", "server-side template injection"],
        }
    }

    manifest = engine._fallback_manifest()

    assert manifest["metadata"]["fallback_class"] == "semantic_guided"
    assert manifest["metadata"]["semantic_guided_family"] == "template_injection"
    assert manifest["metadata"]["semantic_guided_selection_source"] == "request_ir_selection"


def test_fallback_stack_id_prefers_request_ir_selected_stack_when_runtime_recipe_missing(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "NAME-OPEN-REDIRECT")
    engine._requirement["request_ir"] = {  # type: ignore[index]
        "name_driven": True,
        "selection_decision": {
            "family": {
                "selected": True,
                "selected_family": "open_redirect",
                "support_count": 4,
                "support_by_source_authority": {"medium": 4},
                "evidence_backed": True,
                "high_or_medium_authority_support": True,
            },
            "stack": {
                "selected": True,
                "selected_stack_id": "python/fastapi",
                "basis": "researcher_top_candidate",
                "support_count": 2,
                "support_by_source_authority": {"medium": 2},
                "evidence_backed": True,
                "high_or_medium_authority_support": True,
            },
            "ready_for_materialization": True,
            "open_world_evidence_ready": True,
        },
        "stack_candidates": [
            {"stack_id": "python/flask", "confidence": "high"},
            {"stack_id": "python/fastapi", "confidence": "high"},
        ],
    }

    assert engine._fallback_stack_id() == "python/fastapi"


def test_dynamic_eval_semantic_guided_fallback_prefers_minimal_dynamic_materializer_for_path_traversal(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "NAME-CUSTOM-PATH-TRAVERSAL")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "path_traversal",
            "top_confidence": "high",
            "contradiction_count": 0,
            "ambiguous": False,
        }
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.args", "path parameter"],
            "sink": ["open(", "os.path.join"],
            "exploit_precondition": ["path traversal", "../"],
        }
    }

    manifest = engine._fallback_manifest()
    errors, report = engine._guard_manifest(manifest)

    assert manifest["metadata"]["fallback_class"] == "semantic_guided"
    assert manifest["metadata"]["semantic_guided_family"] == "path_traversal"
    assert manifest["metadata"]["materializer"] == "minimal_dynamic"
    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    poc_entry = next(entry for entry in manifest["files"] if entry.get("role") == "poc_entry")
    assert "Asset-backed family-aware fallback template for Path Traversal." not in service_main["content"]
    assert "os.path.join" in service_main["content"]
    assert "../secret.txt" in poc_entry["content"]
    assert not any("semantic mismatch:" in item for item in errors)
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("semantic_match") is True


def test_dynamic_eval_semantic_guided_fallback_can_emit_fastapi_path_traversal_minimal_dynamic(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "NAME-CUSTOM-PATH-TRAVERSAL")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._requirement["runtime_recipe"] = {  # type: ignore[index]
        "language": "python",
        "framework": "fastapi",
    }
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "path_traversal",
            "top_confidence": "high",
            "contradiction_count": 0,
            "ambiguous": False,
        },
        "tech_stack_candidates": [
            {"language": "python", "framework": "fastapi", "stack_id": "python/fastapi", "confidence": "medium"}
        ],
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.args", "path parameter"],
            "sink": ["open(", "os.path.join"],
            "exploit_precondition": ["path traversal", "../"],
        }
    }

    manifest = engine._fallback_manifest()

    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    requirements = next(entry for entry in manifest["files"] if entry.get("path") == "requirements.txt")
    assert manifest["metadata"]["materializer"] == "minimal_dynamic"
    assert "from fastapi import FastAPI" in service_main["content"]
    assert "PlainTextResponse" in service_main["content"]
    assert "uvicorn.run(app" in service_main["content"]
    assert "fastapi==" in requirements["content"].lower()
    assert "uvicorn==" in requirements["content"].lower()


def test_dynamic_eval_semantic_guided_fallback_prefers_minimal_dynamic_materializer_for_ssrf(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "NAME-CUSTOM-SSRF")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "ssrf",
            "top_confidence": "high",
            "contradiction_count": 0,
            "ambiguous": False,
        }
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.args", "url parameter"],
            "sink": ["requests.get", "http client request"],
            "exploit_precondition": ["server-side request forgery"],
        }
    }

    manifest = engine._fallback_manifest()
    errors, report = engine._guard_manifest(manifest)

    assert manifest["metadata"]["fallback_class"] == "semantic_guided"
    assert manifest["metadata"]["semantic_guided_family"] == "ssrf"
    assert manifest["metadata"]["materializer"] == "minimal_dynamic"
    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    poc_entry = next(entry for entry in manifest["files"] if entry.get("role") == "poc_entry")
    assert "Asset-backed family-aware fallback template for SSRF." not in service_main["content"]
    assert "requests.get(target_url, timeout=2)" in service_main["content"]
    assert "/fetch?url=" in poc_entry["content"]
    assert not any("semantic mismatch:" in item for item in errors)
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("semantic_match") is True


def test_dynamic_eval_semantic_guided_fallback_can_emit_fastapi_ssrf_minimal_dynamic(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "NAME-CUSTOM-SSRF")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._requirement["runtime_recipe"] = {  # type: ignore[index]
        "language": "python",
        "framework": "fastapi",
    }
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "ssrf",
            "top_confidence": "high",
            "contradiction_count": 0,
            "ambiguous": False,
        },
        "tech_stack_candidates": [
            {"language": "python", "framework": "fastapi", "stack_id": "python/fastapi", "confidence": "medium"}
        ],
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.args", "url parameter"],
            "sink": ["requests.get", "http client request"],
            "exploit_precondition": ["server-side request forgery"],
        }
    }

    manifest = engine._fallback_manifest()

    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    requirements = next(entry for entry in manifest["files"] if entry.get("path") == "requirements.txt")
    assert manifest["metadata"]["materializer"] == "minimal_dynamic"
    assert "from fastapi import FastAPI" in service_main["content"]
    assert "PlainTextResponse" in service_main["content"]
    assert "requests==" in requirements["content"].lower()


def test_dynamic_eval_semantic_guided_fallback_prefers_minimal_dynamic_materializer_for_sqli(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "NAME-CUSTOM-SQLI")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "sqli",
            "top_confidence": "high",
            "contradiction_count": 0,
            "ambiguous": False,
        }
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.args", "user-controlled request parameter"],
            "sink": ["sqlite3.execute", "sql query execution"],
            "exploit_precondition": ["sql injection", "input concatenated into sql sink"],
        }
    }

    manifest = engine._fallback_manifest()
    errors, report = engine._guard_manifest(manifest)

    assert manifest["metadata"]["fallback_class"] == "semantic_guided"
    assert manifest["metadata"]["semantic_guided_family"] == "sqli"
    assert manifest["metadata"]["materializer"] == "minimal_dynamic"
    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    poc_entry = next(entry for entry in manifest["files"] if entry.get("role") == "poc_entry")
    assert "Asset-backed family-aware fallback template for SQLi." not in service_main["content"]
    assert "sqlite3.connect(DB_PATH)" in service_main["content"]
    assert "FLAG_TOKEN if compromised else None" in service_main["content"]
    assert "admin' OR '1'='1" in poc_entry["content"]
    assert not any("semantic mismatch:" in item for item in errors)
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("semantic_match") is True


def test_dynamic_eval_semantic_guided_fallback_can_emit_fastapi_sqli_minimal_dynamic(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "NAME-CUSTOM-SQLI")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._requirement["runtime_recipe"] = {  # type: ignore[index]
        "language": "python",
        "framework": "fastapi",
    }
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "sqli",
            "top_confidence": "high",
            "contradiction_count": 0,
            "ambiguous": False,
        },
        "tech_stack_candidates": [
            {"language": "python", "framework": "fastapi", "stack_id": "python/fastapi", "confidence": "medium"}
        ],
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.args", "user-controlled request parameter"],
            "sink": ["sqlite3.execute", "sql query execution"],
            "exploit_precondition": ["sql injection", "input concatenated into sql sink"],
        }
    }

    manifest = engine._fallback_manifest()
    errors, report = engine._guard_manifest(manifest)

    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    requirements = next(entry for entry in manifest["files"] if entry.get("path") == "requirements.txt")
    assert manifest["metadata"]["materializer"] == "minimal_dynamic"
    assert "from fastapi import FastAPI, Query" in service_main["content"]
    assert "uvicorn.run(app" in service_main["content"]
    assert "fastapi==" in requirements["content"].lower()
    assert "uvicorn==" in requirements["content"].lower()
    assert not any("semantic mismatch:" in item for item in errors)
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("semantic_match") is True


def test_dynamic_eval_semantic_guided_fallback_can_emit_mysql_sqli_minimal_dynamic_from_design_brief(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "NAME-CUSTOM-SQLI")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._requirement["staged_synthesis"] = {  # type: ignore[index]
        "schema_version": "staged_synthesis@0.1",
        "stage_order": ["candidate_resolution", "design_brief", "runtime_plan", "oracle_contract"],
        "design_brief": {
            "selected_topology": "service_plus_sidecar",
            "dependency_set": ["service", "db:mysql"],
            "required_roles": ["service_main", "poc_entry", "dependency_db", "dependency_sidecar"],
        },
    }
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "sqli",
            "top_confidence": "high",
            "contradiction_count": 0,
            "ambiguous": False,
        }
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.args", "user-controlled request parameter"],
            "sink": ["cur.execute", "sql query execution"],
            "exploit_precondition": ["sql injection", "input concatenated into sql sink"],
        }
    }

    manifest = engine._fallback_manifest()
    errors, report = engine._guard_manifest(manifest)

    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    requirements = next(entry for entry in manifest["files"] if entry.get("path") == "requirements.txt")
    schema_entry = next(entry for entry in manifest["files"] if entry.get("path") == "schema.sql")
    assert manifest["metadata"]["materializer"] == "minimal_dynamic"
    assert manifest["metadata"]["target_db"] == "mysql"
    assert manifest["metadata"]["target_sidecars"] == ["mysql"]
    assert manifest["metadata"]["target_topology"] == "service_plus_sidecar"
    assert manifest["run"]["env"] == {
        "DB_HOST": "db-internal",
        "DB_PORT": "3306",
        "DB_USER": "sqli",
        "DB_PASSWORD": "sqli_pw",
        "DB_NAME": "sqliapp",
    }
    assert "import pymysql" in service_main["content"]
    assert "pymysql.connect(" in service_main["content"]
    assert "Path(__file__).with_name('schema.sql')" in service_main["content"]
    assert "SCHEMA_PATH.read_text" in service_main["content"]
    assert "cur.execute(query)" in service_main["content"]
    assert "sqlite3.connect" not in service_main["content"]
    assert "pymysql==" in requirements["content"].lower()
    assert schema_entry["role"] == "schema"
    assert "CREATE TABLE IF NOT EXISTS users" in schema_entry["content"]
    assert "INSERT INTO users" in schema_entry["content"]
    assert not any("semantic mismatch:" in item for item in errors)
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("semantic_match") is True


def test_dynamic_eval_semantic_guided_fallback_can_emit_postgres_sqli_minimal_dynamic_from_design_brief(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "NAME-CUSTOM-SQLI")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._requirement["staged_synthesis"] = {  # type: ignore[index]
        "schema_version": "staged_synthesis@0.1",
        "stage_order": ["candidate_resolution", "design_brief", "runtime_plan", "oracle_contract"],
        "design_brief": {
            "selected_topology": "service_plus_sidecar",
            "dependency_set": ["service", "db:postgres"],
            "required_roles": ["service_main", "poc_entry", "dependency_db", "dependency_sidecar"],
        },
    }
    engine._requirement["runtime_recipe"] = {  # type: ignore[index]
        "language": "python",
        "framework": "fastapi",
    }
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "sqli",
            "top_confidence": "high",
            "contradiction_count": 0,
            "ambiguous": False,
        }
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.args", "user-controlled request parameter"],
            "sink": ["cursor.execute", "sql query execution"],
            "exploit_precondition": ["sql injection", "input concatenated into sql sink"],
        }
    }

    manifest = engine._fallback_manifest()
    errors, report = engine._guard_manifest(manifest)

    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    requirements = next(entry for entry in manifest["files"] if entry.get("path") == "requirements.txt")
    schema_entry = next(entry for entry in manifest["files"] if entry.get("path") == "schema.sql")
    assert manifest["metadata"]["materializer"] == "minimal_dynamic"
    assert manifest["metadata"]["target_db"] == "postgres"
    assert manifest["metadata"]["target_sidecars"] == ["postgres"]
    assert manifest["metadata"]["target_topology"] == "service_plus_sidecar"
    assert manifest["run"]["env"] == {
        "DB_HOST": "db-internal",
        "DB_PORT": "5432",
        "DB_USER": "sqli",
        "DB_PASSWORD": "sqli_pw",
        "DB_NAME": "sqliapp",
    }
    assert "from fastapi import FastAPI, Query" in service_main["content"]
    assert "import psycopg2" in service_main["content"]
    assert "Path(__file__).with_name('schema.sql')" in service_main["content"]
    assert "SCHEMA_PATH.read_text" in service_main["content"]
    assert "cursor_factory=RealDictCursor" in service_main["content"]
    assert "sqlite3.connect" not in service_main["content"]
    assert "psycopg2-binary==" in requirements["content"].lower()
    assert schema_entry["role"] == "schema"
    assert "CREATE TABLE IF NOT EXISTS users" in schema_entry["content"]
    assert "SERIAL PRIMARY KEY" in schema_entry["content"]
    assert not any("semantic mismatch:" in item for item in errors)
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("semantic_match") is True


def test_dynamic_eval_semantic_guided_fallback_prefers_minimal_dynamic_materializer_for_csrf(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "NAME-CUSTOM-CSRF")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "csrf",
            "top_confidence": "high",
            "contradiction_count": 0,
            "ambiguous": False,
        }
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["cross-site request", "cookie-authenticated session"],
            "sink": ["state-changing endpoint (POST/PUT/DELETE/PATCH)"],
            "exploit_precondition": ["missing csrf token validation"],
        }
    }

    manifest = engine._fallback_manifest()
    errors, report = engine._guard_manifest(manifest)

    assert manifest["metadata"]["fallback_class"] == "semantic_guided"
    assert manifest["metadata"]["semantic_guided_family"] == "csrf"
    assert manifest["metadata"]["materializer"] == "minimal_dynamic"
    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    poc_entry = next(entry for entry in manifest["files"] if entry.get("role") == "poc_entry")
    assert "Asset-backed family-aware fallback template for CSRF." not in service_main["content"]
    assert "@app.get('/login')" in service_main["content"]
    assert "request.cookies.get('session')" in service_main["content"]
    assert "@app.post('/transfer')" in service_main["content"]
    assert "HTTPCookieProcessor" in poc_entry["content"]
    assert "method='POST'" in poc_entry["content"]
    assert not any("semantic mismatch:" in item for item in errors)
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("semantic_match") is True


def test_dynamic_eval_semantic_guided_fallback_can_emit_fastapi_csrf_minimal_dynamic(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "NAME-CUSTOM-CSRF")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._requirement["runtime_recipe"] = {  # type: ignore[index]
        "language": "python",
        "framework": "fastapi",
    }
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "csrf",
            "top_confidence": "high",
            "contradiction_count": 0,
            "ambiguous": False,
        },
        "tech_stack_candidates": [
            {"language": "python", "framework": "fastapi", "stack_id": "python/fastapi", "confidence": "medium"}
        ],
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["cross-site request", "cookie-authenticated session"],
            "sink": ["state-changing endpoint (POST/PUT/DELETE/PATCH)"],
            "exploit_precondition": ["missing csrf token validation"],
        }
    }

    manifest = engine._fallback_manifest()
    errors, report = engine._guard_manifest(manifest)

    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    requirements = next(entry for entry in manifest["files"] if entry.get("path") == "requirements.txt")
    assert manifest["metadata"]["materializer"] == "minimal_dynamic"
    assert "from fastapi import FastAPI" in service_main["content"]
    assert "response.set_cookie('session', SESSION_COOKIE)" in service_main["content"]
    assert "request.cookies.get('session')" in service_main["content"]
    assert "@app.post('/transfer')" in service_main["content"]
    assert "fastapi==" in requirements["content"].lower()
    assert "uvicorn==" in requirements["content"].lower()
    assert not any("semantic mismatch:" in item for item in errors)
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("semantic_match") is True


def test_family_aware_fallback_manifest_for_cwe502_passes_guard(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "CWE-502")
    manifest = engine._fallback_manifest()

    errors, report = engine._guard_manifest(manifest)

    assert not any("guard semantic mismatch:" in item for item in errors)
    assert manifest["metadata"]["fallback_class"] == "family_aware"
    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    poc_entry = next(entry for entry in manifest["files"] if entry.get("role") == "poc_entry")
    assert "Asset-backed family-aware fallback template for Insecure Deserialization." in service_main["content"]
    assert "Asset-backed family-aware fallback template for Insecure Deserialization." in poc_entry["content"]
    assert "pickle.loads" in service_main["content"]
    assert "request.get_data" in service_main["content"]
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("supported") is True
    assert semantics.get("semantic_match") is True


def test_dynamic_eval_semantic_guided_fallback_prefers_minimal_dynamic_materializer_for_deserialization(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "NAME-CUSTOM-DESERIALIZATION")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "deserialization",
            "top_confidence": "high",
            "contradiction_count": 0,
            "ambiguous": False,
        }
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.get_data", "serialized payload"],
            "sink": ["pickle.loads"],
            "exploit_precondition": ["untrusted deserialization", "attacker-controlled serialized input"],
        }
    }

    manifest = engine._fallback_manifest()
    errors, report = engine._guard_manifest(manifest)

    assert manifest["metadata"]["fallback_class"] == "semantic_guided"
    assert manifest["metadata"]["semantic_guided_family"] == "deserialization"
    assert manifest["metadata"]["materializer"] == "minimal_dynamic"
    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    poc_entry = next(entry for entry in manifest["files"] if entry.get("role") == "poc_entry")
    assert "Asset-backed family-aware fallback template for Insecure Deserialization." not in service_main["content"]
    assert "pickle.loads" in service_main["content"]
    assert "__reduce__" in poc_entry["content"]
    assert not any("semantic mismatch:" in item for item in errors)
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("semantic_match") is True


def test_dynamic_eval_semantic_guided_fallback_can_emit_fastapi_deserialization_minimal_dynamic(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "NAME-CUSTOM-DESERIALIZATION")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._requirement["runtime_recipe"] = {  # type: ignore[index]
        "language": "python",
        "framework": "fastapi",
    }
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "deserialization",
            "top_confidence": "high",
            "contradiction_count": 0,
            "ambiguous": False,
        },
        "tech_stack_candidates": [
            {"language": "python", "framework": "fastapi", "stack_id": "python/fastapi", "confidence": "medium"}
        ],
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.get_data", "serialized payload"],
            "sink": ["pickle.loads"],
            "exploit_precondition": ["untrusted deserialization", "attacker-controlled serialized input"],
        }
    }

    manifest = engine._fallback_manifest()

    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    requirements = next(entry for entry in manifest["files"] if entry.get("path") == "requirements.txt")
    assert manifest["metadata"]["materializer"] == "minimal_dynamic"
    assert "from fastapi import FastAPI, Request" in service_main["content"]
    assert "uvicorn.run(app" in service_main["content"]
    assert "fastapi==" in requirements["content"].lower()
    assert "uvicorn==" in requirements["content"].lower()


def test_dynamic_eval_semantic_guided_fallback_prefers_minimal_dynamic_materializer_for_template_injection(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "NAME-CUSTOM-TEMPLATE-INJECTION")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "template_injection",
            "top_confidence": "high",
            "contradiction_count": 0,
            "ambiguous": False,
        }
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.args", "query parameter", "user input"],
            "sink": ["render_template_string"],
            "exploit_precondition": ["server-side template injection", "template injection"],
        }
    }

    manifest = engine._fallback_manifest()
    errors, report = engine._guard_manifest(manifest)

    assert manifest["metadata"]["fallback_class"] == "semantic_guided"
    assert manifest["metadata"]["semantic_guided_family"] == "template_injection"
    assert manifest["metadata"]["materializer"] == "minimal_dynamic"
    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    poc_entry = next(entry for entry in manifest["files"] if entry.get("role") == "poc_entry")
    assert "Asset-backed family-aware fallback template for Template Injection." not in service_main["content"]
    assert "render_template_string(template)" in service_main["content"]
    assert "{{7*7}}" in poc_entry["content"]
    assert not any("semantic mismatch:" in item for item in errors)
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("semantic_match") is True


def test_dynamic_eval_semantic_guided_fallback_accepts_descriptive_template_injection_guard_spec(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "NAME-CUSTOM-TEMPLATE-INJECTION")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "template_injection",
            "top_confidence": "high",
            "contradiction_count": 0,
            "ambiguous": False,
        }
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.args", "user-controlled request parameter"],
            "sink": ["render_template_string", "jinja2 template rendering from string"],
            "exploit_precondition": [
                "user input is embedded into template source string (concatenation/interpolation)",
                "template string is rendered server-side without escaping/sandboxing",
            ],
        }
    }

    manifest = engine._fallback_manifest()
    errors, report = engine._guard_manifest(manifest)

    assert manifest["metadata"]["fallback_class"] == "semantic_guided"
    assert manifest["metadata"]["semantic_guided_family"] == "template_injection"
    assert manifest["metadata"]["materializer"] == "minimal_dynamic"
    assert not any("semantic mismatch:" in item for item in errors)
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("semantic_match") is True


def test_dynamic_eval_semantic_guided_fallback_can_emit_fastapi_template_injection_minimal_dynamic(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "NAME-CUSTOM-TEMPLATE-INJECTION")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._requirement["runtime_recipe"] = {  # type: ignore[index]
        "language": "python",
        "framework": "fastapi",
    }
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "template_injection",
            "top_confidence": "high",
            "contradiction_count": 0,
            "ambiguous": False,
        },
        "tech_stack_candidates": [
            {"language": "python", "framework": "fastapi", "stack_id": "python/fastapi", "confidence": "medium"}
        ],
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.args", "query parameter", "user input"],
            "sink": ["render_template_string"],
            "exploit_precondition": ["server-side template injection", "template injection"],
        }
    }

    manifest = engine._fallback_manifest()
    errors, report = engine._guard_manifest(manifest)

    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    requirements = next(entry for entry in manifest["files"] if entry.get("path") == "requirements.txt")
    assert manifest["metadata"]["materializer"] == "minimal_dynamic"
    assert "from fastapi import FastAPI, Query" in service_main["content"]
    assert "Template(template)" in service_main["content"]
    assert "Jinja2==" in requirements["content"]
    assert not any("semantic mismatch:" in item for item in errors)
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("semantic_match") is True


def test_dynamic_eval_semantic_guided_fallback_prefers_minimal_dynamic_materializer_for_command_injection(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "CWE-78")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "command_injection",
            "top_confidence": "high",
            "contradiction_count": 0,
            "ambiguous": False,
        }
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.args", "command parameter"],
            "sink": ["subprocess", "shell=True"],
            "exploit_precondition": ["command injection", "user input in command"],
        }
    }

    manifest = engine._fallback_manifest()
    errors, report = engine._guard_manifest(manifest)

    assert manifest["metadata"]["fallback_class"] == "semantic_guided"
    assert manifest["metadata"]["semantic_guided_family"] == "command_injection"
    assert manifest["metadata"]["materializer"] == "minimal_dynamic"
    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    assert "subprocess.check_output" in service_main["content"]
    assert "shell=True" in service_main["content"]
    assert not any("semantic mismatch:" in item for item in errors)
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("semantic_match") is True


def test_dynamic_eval_semantic_guided_fallback_can_emit_fastapi_command_injection_minimal_dynamic(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "CWE-78")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._requirement["runtime_recipe"] = {  # type: ignore[index]
        "language": "python",
        "framework": "fastapi",
    }
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "command_injection",
            "top_confidence": "high",
            "contradiction_count": 0,
            "ambiguous": False,
        },
        "tech_stack_candidates": [
            {"language": "python", "framework": "fastapi", "stack_id": "python/fastapi", "confidence": "medium"}
        ],
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.args", "command parameter"],
            "sink": ["subprocess", "shell=True"],
            "exploit_precondition": ["command injection", "user input in command"],
        }
    }

    manifest = engine._fallback_manifest()
    errors, report = engine._guard_manifest(manifest)

    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    requirements = next(entry for entry in manifest["files"] if entry.get("path") == "requirements.txt")
    assert manifest["metadata"]["materializer"] == "minimal_dynamic"
    assert "from fastapi import FastAPI, Query" in service_main["content"]
    assert "subprocess.check_output" in service_main["content"]
    assert "fastapi==" in requirements["content"].lower()
    assert "uvicorn==" in requirements["content"].lower()
    assert not any("semantic mismatch:" in item for item in errors)
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("semantic_match") is True


def test_dynamic_eval_semantic_guided_fallback_prefers_minimal_dynamic_materializer_for_code_injection(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "CWE-94")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "code_injection",
            "top_confidence": "high",
            "contradiction_count": 0,
            "ambiguous": False,
        }
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.args", "code parameter"],
            "sink": ["eval(", "exec("],
            "exploit_precondition": ["code injection", "user input reaches eval"],
        }
    }

    manifest = engine._fallback_manifest()
    errors, report = engine._guard_manifest(manifest)

    assert manifest["metadata"]["fallback_class"] == "semantic_guided"
    assert manifest["metadata"]["semantic_guided_family"] == "code_injection"
    assert manifest["metadata"]["materializer"] == "minimal_dynamic"
    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    assert "result = eval(code" in service_main["content"]
    assert not any("semantic mismatch:" in item for item in errors)
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("semantic_match") is True


def test_dynamic_eval_semantic_guided_fallback_can_emit_fastapi_code_injection_minimal_dynamic(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "CWE-94")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._requirement["runtime_recipe"] = {  # type: ignore[index]
        "language": "python",
        "framework": "fastapi",
    }
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "code_injection",
            "top_confidence": "high",
            "contradiction_count": 0,
            "ambiguous": False,
        },
        "tech_stack_candidates": [
            {"language": "python", "framework": "fastapi", "stack_id": "python/fastapi", "confidence": "medium"}
        ],
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.args", "code parameter"],
            "sink": ["eval(", "exec("],
            "exploit_precondition": ["code injection", "user input reaches eval"],
        }
    }

    manifest = engine._fallback_manifest()
    errors, report = engine._guard_manifest(manifest)

    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    requirements = next(entry for entry in manifest["files"] if entry.get("path") == "requirements.txt")
    assert manifest["metadata"]["materializer"] == "minimal_dynamic"
    assert "from fastapi import FastAPI, Query" in service_main["content"]
    assert "result = eval(code" in service_main["content"]
    assert "fastapi==" in requirements["content"].lower()
    assert "uvicorn==" in requirements["content"].lower()
    assert not any("semantic mismatch:" in item for item in errors)
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("semantic_match") is True


def test_dynamic_eval_semantic_guided_fallback_prefers_minimal_dynamic_materializer_for_ldap_injection(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "NAME-LDAP-INJECTION")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "ldap_injection",
            "top_confidence": "high",
            "contradiction_count": 0,
            "ambiguous": False,
        }
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.args", "ldap user parameter"],
            "sink": ["LDAP filter construction", "directory search", "search_directory("],
            "exploit_precondition": ["ldap injection", "filter bypass via wildcard or OR clause"],
        }
    }

    manifest = engine._fallback_manifest()
    errors, report = engine._guard_manifest(manifest)

    assert manifest["metadata"]["fallback_class"] == "semantic_guided"
    assert manifest["metadata"]["semantic_guided_family"] == "ldap_injection"
    assert manifest["metadata"]["materializer"] == "minimal_dynamic"
    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    assert "search_directory(ldap_filter)" in service_main["content"]
    assert "ldap_filter = '(uid=' + user + ')'" in service_main["content"]
    assert not any("semantic mismatch:" in item for item in errors)
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("semantic_match") is True


def test_dynamic_eval_semantic_guided_fallback_prefers_minimal_dynamic_materializer_for_xxe(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path, "NAME-XXE")
    engine._requirement["policy"] = {"dynamic_eval": True}  # type: ignore[index]
    engine._researcher_report_payload = {  # type: ignore[attr-defined]
        "family_hypothesis_summary": {
            "top_family": "xxe",
            "top_confidence": "high",
            "contradiction_count": 0,
            "ambiguous": False,
        }
    }
    engine._guard_spec_payload = {  # type: ignore[attr-defined]
        "semantic_signature": {
            "input_vector": ["request.data", "xml body", "attacker-controlled xml payload"],
            "sink": ["etree.XMLParser(load_dtd=True, resolve_entities=True)", "etree.fromstring"],
            "exploit_precondition": ["xml external entity", "xxe", "external entity resolution enabled"],
        }
    }

    manifest = engine._fallback_manifest()
    errors, report = engine._guard_manifest(manifest)

    assert manifest["metadata"]["fallback_class"] == "semantic_guided"
    assert manifest["metadata"]["semantic_guided_family"] == "xxe"
    assert manifest["metadata"]["materializer"] == "minimal_dynamic"
    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    requirements = next(entry for entry in manifest["files"] if entry.get("path") == "requirements.txt")
    assert "etree.XMLParser(load_dtd=True, resolve_entities=True)" in service_main["content"]
    assert "lxml==" in requirements["content"].lower()
    assert not any("semantic mismatch:" in item for item in errors)
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("semantic_match") is True


def test_run_can_recover_with_semantic_guided_minimal_dynamic_after_invalid_json_manifest(
    tmp_path: Path,
) -> None:
    engine = SynthesisEngine(
        sid="sid-test-recovery",
        llm=_BadJsonManifestLLM(),
        limits=SynthesisLimits(),
        workspace=tmp_path / "workspace",
        metadata_dir=tmp_path / "metadata",
        mode="synthesis",
    )
    requirement = {
        "vuln_id": "CWE-502",
        "language": "python",
        "runtime": {"python_version": "3.11"},
        "pattern_id": "insecure-deserialization",
        "dep_guard": {"llm_assist": False, "auto_patch": False},
        "policy": {"dynamic_eval": True},
    }
    researcher_payload = {
        "family_hypothesis_summary": {
            "top_family": "deserialization",
            "top_confidence": "high",
            "contradiction_count": 0,
            "ambiguous": False,
        }
    }
    guard_spec_payload = {
        "semantic_signature": {
            "input_vector": ["request.get_data", "serialized payload"],
            "sink": ["pickle.loads"],
            "exploit_precondition": ["untrusted deserialization", "attacker-controlled serialized input"],
        }
    }

    outcome = engine.run(
        requirement=requirement,
        rag_context="",
        hints="",
        failure_context="",
        candidate_k=1,
        researcher_report=json.dumps(researcher_payload),
        guard_spec=json.dumps(guard_spec_payload),
        guard_spec_payload=guard_spec_payload,
    )

    selected = outcome.selected.manifest
    assert selected["metadata"]["fallback_class"] == "semantic_guided"
    assert selected["metadata"]["semantic_guided_family"] == "deserialization"
    assert selected["metadata"]["materializer"] == "minimal_dynamic"


def test_family_aware_fallback_manifest_for_path_traversal_uses_asset_templates(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "CWE-22")
    manifest = engine._fallback_manifest()

    errors, report = engine._guard_manifest(manifest)

    assert not any("semantic mismatch:" in item for item in errors)
    assert manifest["metadata"]["fallback_class"] == "family_aware"
    service_main = next(entry for entry in manifest["files"] if entry.get("role") == "service_main")
    poc_entry = next(entry for entry in manifest["files"] if entry.get("role") == "poc_entry")
    assert "Asset-backed family-aware fallback template for Path Traversal." in service_main["content"]
    assert "Asset-backed family-aware fallback template for Path Traversal." in poc_entry["content"]
    assert "os.path.join" in service_main["content"]
    assert "../../../../etc/passwd" in poc_entry["content"]
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("supported") is True
    assert semantics.get("semantic_match") is True


def test_semantic_guard_accepts_cwe918_same_container_loopback_indicator(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "CWE-918")
    manifest = {
        "files": [
            {
                "path": "app.py",
                "role": "service_main",
                "content": (
                    "import requests\n"
                    "from flask import Flask, request, jsonify\n"
                    "app = Flask(__name__)\n"
                    "@app.get('/metadata')\n"
                    "def metadata():\n"
                    "    return jsonify({'marker': 'FLAG{SSRF_OK}', 'service': 'metadata'})\n"
                    "@app.get('/fetch')\n"
                    "def fetch():\n"
                    "    target_url = request.args.get('url', 'http://127.0.0.1:5000/metadata')\n"
                    "    resp = requests.get(target_url, timeout=2)\n"
                    "    return resp.text\n"
                ),
            },
            {
                "path": "poc.py",
                "role": "poc_entry",
                "content": "print('FLAG{SSRF_OK}')\n",
            },
        ],
        "deps": ["Flask==3.0.0", "requests==2.31.0"],
        "poc": {
            "cmd": "python poc.py --base-url {{base_url}}",
            "success_signature": "FLAG{SSRF_OK}",
            "flag_token": "FLAG{SSRF_OK}",
        },
        "pattern_tags": ["guard-test"],
    }
    errors, report = engine._guard_manifest(manifest)
    assert not any("semantic mismatch:" in item for item in errors)
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("supported") is True
    assert semantics.get("semantic_match") is True
