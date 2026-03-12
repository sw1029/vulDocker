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
    manifest = engine._fallback_manifest()

    assert manifest["metadata"]["fallback_class"] == "generic_unsupported_family"
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
