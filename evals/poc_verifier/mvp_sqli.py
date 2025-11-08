"""PoC verifier for the MVP SQLi scenario."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.logging import get_logger
from common.paths import ensure_dir, get_artifacts_dir

LOGGER = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate SQLi PoC logs")
    parser.add_argument("--sid", required=True)
    parser.add_argument("--log", type=Path, help="Path to run log (optional)")
    return parser.parse_args()


def evaluate_log(log_path: Path) -> dict:
    if not log_path.exists():
        raise FileNotFoundError(f"Log file not found: {log_path}")
    content = log_path.read_text(encoding="utf-8")
    success = "SQLi SUCCESS" in content
    return {
        "verify_pass": success,
        "evidence": "SQLi SUCCESS" if success else "Signature missing",
        "log_path": str(log_path),
    }


def main() -> None:
    args = parse_args()
    log_path = args.log or (get_artifacts_dir(args.sid) / "run" / "run.log")
    result = evaluate_log(log_path)
    reports_dir = ensure_dir(get_artifacts_dir(args.sid) / "reports")
    output_path = reports_dir / "evals.json"
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    LOGGER.info("Evaluation result saved to %s", output_path)


if __name__ == "__main__":
    main()
