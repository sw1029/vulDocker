"""Researcher agent entry point."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.researcher import ResearcherService
from common.logging import get_logger
from common.paths import ensure_dir, get_metadata_dir
from common.plan import load_plan
from common.run_matrix import load_vuln_bundles

LOGGER = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Researcher agent")
    parser.add_argument("--sid", required=True, help="Scenario ID to research")
    parser.add_argument("--mode", default="deterministic", help="Decoding profile override")
    parser.add_argument("--search-limit", type=int, default=3, help="Results per query")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    plan = load_plan(args.sid)
    bundles = load_vuln_bundles(plan)
    reports = []
    for bundle in bundles:
        service = ResearcherService(
            args.sid,
            mode=args.mode,
            search_limit=args.search_limit,
            plan=plan,
            bundle=bundle,
        )
        path = service.run()
        reports.append({"vuln_id": bundle.vuln_id, "slug": bundle.slug, "report_path": str(path)})
        LOGGER.info("Researcher finished for %s (%s)", args.sid, bundle.vuln_id)
    _write_index(args.sid, reports)


def _write_index(sid: str, reports: list[dict]) -> None:
    metadata_dir = ensure_dir(get_metadata_dir(sid))
    index_path = metadata_dir / "researcher_reports.json"
    payload = {"sid": sid, "reports": reports}
    index_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    LOGGER.info("Researcher index updated at %s", index_path)


if __name__ == "__main__":
    main()
