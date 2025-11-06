#!/usr/bin/env python3
"""Verifier for MVP SQLi PoC log."""
import argparse
import json
from pathlib import Path


def verify(log_path: Path) -> bool:
    data = json.loads(log_path.read_text(encoding='utf-8'))
    return bool(data.get('result')) and data.get('payload', {}).get('password', '').strip() == "' OR '1'='1"


def main() -> None:
    parser = argparse.ArgumentParser(description='Verify MVP SQLi PoC log')
    parser.add_argument('--log', required=True)
    args = parser.parse_args()
    log_path = Path(args.log)
    if not log_path.exists():
        raise SystemExit(f'Log not found: {log_path}')
    ok = verify(log_path)
    print(json.dumps({'log': str(log_path), 'verify_pass': ok}, ensure_ascii=False))
    if not ok:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
