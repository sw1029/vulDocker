"""Generator agent entry point using the TODO 14 service layer."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.generator.service import GeneratorService
from common.logging import get_logger
from common.paths import ensure_dir, get_metadata_dir
from common.plan import load_plan
from common.run_matrix import load_vuln_bundles

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
    plan = load_plan(args.sid)
    bundles = load_vuln_bundles(plan)
    runs = []
    for bundle in bundles:
        service = GeneratorService(
            args.sid,
            mode=args.mode,
            template_root=args.template_root,
            plan=plan,
            bundle=bundle,
        )
        service.run()
        runs.append({"vuln_id": bundle.vuln_id, "slug": bundle.slug, "workspace": str(service.workspace)})
        LOGGER.info("Generator completed for %s (%s)", args.sid, bundle.vuln_id)
    _write_index(args.sid, runs)


def _write_index(sid: str, runs: list[dict]) -> None:
    metadata_dir = ensure_dir(get_metadata_dir(sid))
    index_path = metadata_dir / "generator_runs.json"
    payload = {"sid": sid, "runs": runs}
    index_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    LOGGER.info("Generator run index updated at %s", index_path)


if __name__ == "__main__":
    main()
