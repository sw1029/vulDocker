from __future__ import annotations

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
    engine = _engine(tmp_path, "NAME-LDAP-INJECTION")
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
    assert "redirect(next_url, code=302)" in service_main["content"]
    assert "allow_redirects=False" in poc_entry["content"]
    semantics = (report or {}).get("semantics") or {}
    assert semantics.get("supported") is True
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
