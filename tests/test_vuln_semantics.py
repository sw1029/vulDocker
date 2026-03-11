from __future__ import annotations

from pathlib import Path

from common.vuln_semantics import evaluate_manifest_semantics, normalize_vuln_id


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_normalize_vuln_id_preserves_name_identifier() -> None:
    assert normalize_vuln_id("NAME-OPEN-REDIRECT") == "name-open-redirect"
    assert normalize_vuln_id("NAME_TEMPLATE_INJECTION") == "name-template-injection"


def test_evaluate_manifest_semantics_supports_name_open_redirect() -> None:
    report = evaluate_manifest_semantics(
        "NAME-OPEN-REDIRECT",
        {
            "files": [
                {
                    "path": "app.py",
                    "role": "service_main",
                    "content": (
                        "from flask import Flask, redirect, request\n"
                        "app = Flask(__name__)\n"
                        "@app.get('/go')\n"
                        "def go():\n"
                        "    next_url = request.args.get('next', 'https://example.com')\n"
                        "    return redirect(next_url)\n"
                    ),
                }
            ]
        },
    )

    assert report["supported"] is True
    assert report["semantic_match"] is True
    assert report["vuln_id"] == "name-open-redirect"


def test_evaluate_manifest_semantics_supports_name_open_redirect_fastapi() -> None:
    report = evaluate_manifest_semantics(
        "NAME-OPEN-REDIRECT",
        {
            "files": [
                {
                    "path": "app.py",
                    "role": "service_main",
                    "content": (
                        "from fastapi import FastAPI, Query\n"
                        "from fastapi.responses import RedirectResponse\n"
                        "app = FastAPI()\n"
                        "@app.get('/go')\n"
                        "def go(next: str = Query('https://example.com')):\n"
                        "    return RedirectResponse(url=next, status_code=302)\n"
                    ),
                }
            ]
        },
    )

    assert report["supported"] is True
    assert report["semantic_match"] is True
    assert report["vuln_id"] == "name-open-redirect"


def test_evaluate_manifest_semantics_supports_cwe22_fastapi() -> None:
    report = evaluate_manifest_semantics(
        "CWE-22",
        {
            "files": [
                {
                    "path": "app.py",
                    "role": "service_main",
                    "content": (
                        "from pathlib import Path\n"
                        "from fastapi import FastAPI, Query\n"
                        "from fastapi.responses import PlainTextResponse\n"
                        "app = FastAPI()\n"
                        "BASE_DIR = Path('/app/files')\n"
                        "@app.get('/download')\n"
                        "def download(path: str = Query('note.txt')):\n"
                        "    target = BASE_DIR / path\n"
                        "    return PlainTextResponse(target.read_text())\n"
                    ),
                }
            ]
        },
    )

    assert report["supported"] is True
    assert report["semantic_match"] is True
    assert report["vuln_id"] == "cwe-22"


def test_evaluate_manifest_semantics_supports_name_template_injection() -> None:
    report = evaluate_manifest_semantics(
        "NAME-TEMPLATE-INJECTION",
        {
            "files": [
                {
                    "path": "app.py",
                    "role": "service_main",
                    "content": (
                        "from flask import Flask, render_template_string, request\n"
                        "app = Flask(__name__)\n"
                        "@app.get('/greet')\n"
                        "def greet():\n"
                        "    name = request.args.get('name', 'Guest')\n"
                        "    template = '<h1>Hello ' + name + '</h1>'\n"
                        "    return render_template_string(template)\n"
                    ),
                }
            ]
        },
    )

    assert report["supported"] is True
    assert report["semantic_match"] is True
    assert report["vuln_id"] == "name-template-injection"


def test_evaluate_manifest_semantics_supports_name_template_injection_fastapi() -> None:
    report = evaluate_manifest_semantics(
        "NAME-TEMPLATE-INJECTION",
        {
            "files": [
                {
                    "path": "app.py",
                    "role": "service_main",
                    "content": (
                        "from fastapi import FastAPI, Query\n"
                        "from fastapi.responses import HTMLResponse\n"
                        "from jinja2 import Template\n"
                        "app = FastAPI()\n"
                        "@app.get('/greet')\n"
                        "def greet(name: str = Query('Guest')):\n"
                        "    template = Template('<h1>Hello ' + name + '</h1>')\n"
                        "    return HTMLResponse(template.render())\n"
                    ),
                }
            ]
        },
    )

    assert report["supported"] is True
    assert report["semantic_match"] is True
    assert report["vuln_id"] == "name-template-injection"


def test_evaluate_manifest_semantics_supports_name_xxe() -> None:
    report = evaluate_manifest_semantics(
        "NAME-XXE",
        {
            "files": [
                {
                    "path": "app.py",
                    "role": "service_main",
                    "content": (
                        "from lxml import etree\n"
                        "from flask import Flask, Response, request\n"
                        "app = Flask(__name__)\n"
                        "@app.post('/parse')\n"
                        "def parse_xml():\n"
                        "    xml_body = request.get_data()\n"
                        "    parser = etree.XMLParser(load_dtd=True, resolve_entities=True, no_network=False)\n"
                        "    root = etree.fromstring(xml_body, parser=parser)\n"
                        "    return Response(''.join(root.itertext()), mimetype='text/plain')\n"
                    ),
                }
            ]
        },
    )

    assert report["supported"] is True
    assert report["semantic_match"] is True
    assert report["vuln_id"] == "name-xxe"


def test_evaluate_manifest_semantics_supports_name_ldap_injection() -> None:
    report = evaluate_manifest_semantics(
        "NAME-LDAP-INJECTION",
        {
            "files": [
                {
                    "path": "app.py",
                    "role": "service_main",
                    "content": (
                        "import re\n"
                        "from flask import Flask, jsonify, request\n"
                        "app = Flask(__name__)\n"
                        "DIRECTORY = [\n"
                        "    {'uid': 'alice', 'status': 'active', 'role': 'user'},\n"
                        "    {'uid': 'admin', 'status': 'active', 'role': 'admin'},\n"
                        "]\n"
                        "def search_directory(ldap_filter: str):\n"
                        "    if '(|(uid=*))' in ldap_filter.lower() or '*)(|' in ldap_filter.lower():\n"
                        "        return DIRECTORY\n"
                        "    match = re.search(r'\\(uid=([^\\)]+)\\)', ldap_filter)\n"
                        "    if not match:\n"
                        "        return []\n"
                        "    uid = match.group(1)\n"
                        "    return [entry for entry in DIRECTORY if entry['uid'] == uid and entry['status'] == 'active']\n"
                        "@app.get('/search')\n"
                        "def search():\n"
                        "    user = request.args.get('user', 'alice')\n"
                        "    ldap_filter = '(&(uid=' + user + ')(status=active))'\n"
                        "    rows = search_directory(ldap_filter)\n"
                        "    return jsonify({'count': len(rows), 'rows': rows, 'filter': ldap_filter})\n"
                    ),
                }
            ]
        },
    )

    assert report["supported"] is True
    assert report["semantic_match"] is True
    assert report["vuln_id"] == "name-ldap-injection"


def test_evaluate_manifest_semantics_supports_xss_and_deserialization() -> None:
    xss_report = evaluate_manifest_semantics(
        "CWE-79",
        {
            "files": [
                {
                    "path": "app.py",
                    "role": "service_main",
                    "content": (
                        "from flask import Flask, render_template_string, request\n"
                        "app = Flask(__name__)\n"
                        "@app.get('/search')\n"
                        "def search():\n"
                        "    name = request.args.get('name', 'Guest')\n"
                        "    template = \"<div>\" + name + \"</div>\"\n"
                        "    return render_template_string(template)\n"
                    ),
                }
            ]
        },
    )
    deser_report = evaluate_manifest_semantics(
        "CWE-502",
        {
            "files": [
                {
                    "path": "app.py",
                    "role": "service_main",
                    "content": (
                        "import pickle\n"
                        "from flask import Flask, request\n"
                        "app = Flask(__name__)\n"
                        "@app.post('/deserialize')\n"
                        "def deserialize_payload():\n"
                        "    payload = request.get_data()\n"
                        "    return str(pickle.loads(payload))\n"
                    ),
                }
            ]
        },
    )

    assert xss_report["supported"] is True
    assert xss_report["semantic_match"] is True
    assert deser_report["supported"] is True
    assert deser_report["semantic_match"] is True


def test_evaluate_manifest_semantics_supports_code_injection() -> None:
    report = evaluate_manifest_semantics(
        "CWE-94",
        {
            "files": [
                {
                    "path": "app.py",
                    "role": "service_main",
                    "content": (
                        "from flask import Flask, jsonify, request\n"
                        "app = Flask(__name__)\n"
                        "@app.get('/eval')\n"
                        "def evaluate_code():\n"
                        "    code = request.args.get('code', '21 + 21')\n"
                        "    result = eval(code)\n"
                        "    return jsonify({'ok': True, 'result': str(result)})\n"
                    ),
                }
            ]
        },
    )

    assert report["supported"] is True
    assert report["semantic_match"] is True
    assert report["vuln_id"] == "cwe-94"


def test_evaluate_manifest_semantics_supports_path_traversal_via_path_flow_without_comment_marker() -> None:
    report = evaluate_manifest_semantics(
        "CWE-22",
        {
            "files": [
                {
                    "path": "app.py",
                    "role": "service_main",
                    "content": (
                        "from pathlib import Path\n"
                        "from flask import Flask, Response, request\n"
                        "app = Flask(__name__)\n"
                        "BASE_DIR = Path('/app/files')\n"
                        "@app.get('/download')\n"
                        "def download():\n"
                        "    path = request.args.get('path', 'note.txt')\n"
                        "    target = BASE_DIR / path\n"
                        "    try:\n"
                        "        body = target.read_text(encoding='utf-8', errors='ignore')\n"
                        "    except OSError as exc:\n"
                        "        return Response(f'error: {exc}', status=404, mimetype='text/plain')\n"
                        "    return Response(body, mimetype='text/plain')\n"
                    ),
                }
            ]
        },
    )

    assert report["supported"] is True
    assert report["semantic_match"] is True
    assert report["signals"]["input_to_file_sink_flow_present"] is True


def test_evaluate_manifest_semantics_ignores_python_comments_for_path_traversal_signal() -> None:
    report = evaluate_manifest_semantics(
        "CWE-22",
        {
            "files": [
                {
                    "path": "app.py",
                    "role": "service_main",
                    "content": (
                        "from pathlib import Path\n"
                        "from flask import Flask, Response, request\n"
                        "app = Flask(__name__)\n"
                        "SAFE_FILE = Path('/app/files/note.txt')\n"
                        "@app.get('/download')\n"
                        "def download():\n"
                        "    path = request.args.get('path', 'note.txt')\n"
                        "    # attacker can request ../secret.txt for path traversal here\n"
                        "    body = SAFE_FILE.read_text(encoding='utf-8', errors='ignore')\n"
                        "    return Response(body, mimetype='text/plain')\n"
                    ),
                }
            ]
        },
    )

    assert report["supported"] is True
    assert report["semantic_match"] is False
    assert report["signals"]["path_input_present"] is True
    assert report["signals"]["input_to_file_sink_flow_present"] is False


def test_mysql_union_template_sqli_semantics_align() -> None:
    app_path = REPO_ROOT / "workspaces" / "templates" / "sqli" / "flask_mysql_union" / "app" / "app.py"
    report = evaluate_manifest_semantics(
        "CWE-89",
        {
            "files": [
                {
                    "path": "app.py",
                    "role": "service_main",
                    "content": app_path.read_text(encoding="utf-8"),
                }
            ]
        },
    )

    assert report["supported"] is True
    assert report["semantic_match"] is True


def test_manifest_semantics_prefers_service_entry_over_helper_code() -> None:
    report = evaluate_manifest_semantics(
        "CWE-89",
        {
            "files": [
                {
                    "path": "app.py",
                    "role": "service_main",
                    "content": (
                        "from flask import Flask\n"
                        "app = Flask(__name__)\n"
                        "@app.get('/health')\n"
                        "def health():\n"
                        "    return {'ok': True}\n"
                    ),
                },
                {
                    "path": "db_helper.py",
                    "role": "helper",
                    "content": (
                        "from flask import request\n"
                        "def unsafe_query(cur):\n"
                        "    user_id = request.args.get('id', '1')\n"
                        "    query = f\"SELECT * FROM users WHERE id = {user_id}\"\n"
                        "    return cur.execute(query)\n"
                    ),
                },
            ]
        },
    )

    assert report["supported"] is True
    assert report["semantic_match"] is False
