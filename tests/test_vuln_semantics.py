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
