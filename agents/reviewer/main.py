"""Reviewer agent entry point using the stabilization service."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.logging import get_logger
from agents.reviewer.service import ReviewerService

LOGGER = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reviewer agent")
    parser.add_argument("--sid", required=True, help="Scenario ID")
    parser.add_argument("--mode", default="deterministic", help="Decoding profile name")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    service = ReviewerService(args.sid, mode=args.mode)
    service.run()
    LOGGER.info("Reviewer completed for %s", args.sid)


if __name__ == "__main__":
    main()
