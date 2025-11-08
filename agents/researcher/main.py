"""Researcher agent entry point."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.researcher import ResearcherService
from common.logging import get_logger

LOGGER = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Researcher agent")
    parser.add_argument("--sid", required=True, help="Scenario ID to research")
    parser.add_argument("--mode", default="deterministic", help="Decoding profile override")
    parser.add_argument("--search-limit", type=int, default=3, help="Results per query")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    service = ResearcherService(args.sid, mode=args.mode, search_limit=args.search_limit)
    path = service.run()
    LOGGER.info("Researcher finished for %s (report=%s)", args.sid, path)


if __name__ == "__main__":
    main()
