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
