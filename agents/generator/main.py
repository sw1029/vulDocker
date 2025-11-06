#!/usr/bin/env python3
"""Generator for MVP SQLi scenario (creates vulnerable app + PoC)."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP_CODE = '''"""Vulnerable Flask-like login workflow using raw SQL strings."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / 'data.db'


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS users (username TEXT, password TEXT)')
    cur.execute('DELETE FROM users')
    cur.execute('INSERT INTO users(username, password) VALUES ("admin", "secret"), ("guest", "guest")')
    conn.commit()
    conn.close()


def vulnerable_login(username: str, password: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    query = f"SELECT username FROM users WHERE username = '{username}' AND password = '{password}'"
    cur.execute(query)
    row = cur.fetchone()
    conn.close()
    return row is not None


def dump_users() -> list:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT username, password FROM users')
    rows = cur.fetchall()
    conn.close()
    return rows


if __name__ == '__main__':
    init_db()
    print('Users:', dump_users())
'''

POC_CODE = '''#!/usr/bin/env python3
"""Simple SQLi PoC to validate vulnerable_login."""
import argparse
import json
from datetime import datetime
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / 'app'))
from app import init_db, vulnerable_login, dump_users  # type: ignore


def run(log_path: Path) -> None:
    init_db()
    payload_user = "admin"
    payload_pass = "' OR '1'='1"
    result = vulnerable_login(payload_user, payload_pass)
    rows = dump_users()
    log = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'payload': {'username': payload_user, 'password': payload_pass},
        'result': bool(result),
        'rows': rows,
    }
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open('w', encoding='utf-8') as f:
        json.dump(log, f, indent=2, ensure_ascii=False)
    print(f"[POC] result={result} log={log_path}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--log', required=True)
    args = parser.parse_args()
    run(Path(args.log))
'''

README = '''# MVP Workspace

이 디렉터리는 자동 생성된 MVP SQLi 시나리오용 취약 앱과 PoC를 포함합니다.
'''


def generate(plan: dict) -> None:
    sid = plan['sid']
    workspace = ROOT / 'workspaces' / sid
    app_dir = workspace / 'app'
    poc_dir = workspace / 'poc'
    app_dir.mkdir(parents=True, exist_ok=True)
    poc_dir.mkdir(parents=True, exist_ok=True)

    (app_dir / '__init__.py').write_text('', encoding='utf-8')
    (app_dir / 'app.py').write_text(APP_CODE, encoding='utf-8')
    (app_dir / 'README.md').write_text(README, encoding='utf-8')
    (poc_dir / 'poc.py').write_text(POC_CODE, encoding='utf-8')
    (workspace / 'metadata.json').write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"[GENERATOR] Workspace ready at {workspace}")


def main() -> None:
    parser = argparse.ArgumentParser(description='Generate MVP workspace')
    parser.add_argument('--sid', required=True)
    args = parser.parse_args()
    plan_path = ROOT / 'metadata' / args.sid / 'plan.json'
    if not plan_path.exists():
        raise SystemExit(f'Plan not found: {plan_path}')
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    generate(plan)


if __name__ == '__main__':
    main()
