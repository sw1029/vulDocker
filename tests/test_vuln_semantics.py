from __future__ import annotations

from common.vuln_semantics import evaluate_manifest_semantics, normalize_vuln_id


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
