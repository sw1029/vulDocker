"""Generator agent entry point using the TODO 14 service layer."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.logging import get_logger
from agents.generator.service import GeneratorService

LOGGER = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generator agent")
    parser.add_argument("--sid", required=True, help="Scenario ID to generate")
    parser.add_argument("--mode", default="deterministic", help="Decoding profile name")
    parser.add_argument(
        "--template-root",
        type=Path,
        help="Override template root (defaults to workspaces/templates/sqli)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    service = GeneratorService(args.sid, mode=args.mode, template_root=args.template_root)
    service.run()
    LOGGER.info("Generator completed for %s", args.sid)


if __name__ == "__main__":
    main()
