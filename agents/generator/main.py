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
from common.bundle_state import bundle_research_blocker
from common.logging import get_logger
from common.paths import ensure_dir, get_metadata_dir
from common.plan import load_plan
from common.run_matrix import load_vuln_bundles

LOGGER = get_logger(__name__)


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generator agent")
    parser.add_argument("--sid", required=True, help="Scenario ID to generate")
    parser.add_argument("--mode", default="deterministic", help="Decoding profile name")
    parser.add_argument(
        "--template-root",
        type=Path,
        help="Override template root (defaults to workspaces/templates)",
    )
    parser.add_argument(
        "--single-attempt",
        action="store_true",
        help="Disable internal generator looping and run one synthesis attempt per invocation.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    plan = load_plan(args.sid)
    bundles = load_vuln_bundles(plan)
    policy = plan.get("policy") if isinstance(plan, dict) else {}
    stop_on_first_failure = _as_bool((policy or {}).get("stop_on_first_failure", False))
    runs = []
    had_failure = False
    for bundle in bundles:
        research_blocker = bundle_research_blocker(plan, bundle)
        if research_blocker:
            runs.append(
                {
                    "vuln_id": bundle.vuln_id,
                    "slug": bundle.slug,
                    "workspace": None,
                    "status": "skipped",
                    "error": str(research_blocker.get("reason") or "research blocked bundle"),
                    "failure_path": research_blocker.get("report_path"),
                    "skipped_stage": "RESEARCH",
                }
            )
            LOGGER.info(
                "Skipping GENERATOR for %s (%s): %s",
                args.sid,
                bundle.vuln_id,
                str(research_blocker.get("reason") or "research blocked bundle"),
            )
            continue
        service = GeneratorService(
            args.sid,
            mode=args.mode,
            template_root=args.template_root,
            plan=plan,
            bundle=bundle,
            single_attempt=args.single_attempt,
        )
        try:
            service.run()
            runs.append(
                {
                    "vuln_id": bundle.vuln_id,
                    "slug": bundle.slug,
                    "workspace": str(service.workspace),
                    "status": "success",
                    "error": None,
                    "failure_path": None,
                }
            )
            LOGGER.info("Generator completed for %s (%s)", args.sid, bundle.vuln_id)
        except Exception as exc:
            had_failure = True
            failure_path = service.metadata_dir / "generator_failures.jsonl"
            runs.append(
                {
                    "vuln_id": bundle.vuln_id,
                    "slug": bundle.slug,
                    "workspace": str(service.workspace),
                    "status": "failed",
                    "error": str(exc),
                    "failure_path": str(failure_path) if failure_path.exists() else None,
                }
            )
            LOGGER.exception("Generator failed for %s (%s): %s", args.sid, bundle.vuln_id, exc)
            if stop_on_first_failure:
                break
    _write_index(args.sid, runs)
    if had_failure:
        raise SystemExit(1)


def _write_index(sid: str, runs: list[dict]) -> None:
    metadata_dir = ensure_dir(get_metadata_dir(sid))
    index_path = metadata_dir / "generator_runs.json"
    payload = {"sid": sid, "runs": runs}
    index_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    LOGGER.info("Generator run index updated at %s", index_path)


if __name__ == "__main__":
    main()
