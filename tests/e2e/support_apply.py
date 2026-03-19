from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator.support_extract import write_curated_support_registry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply a support registry update preview to a curated registry JSON")
    parser.add_argument("--registry-update", type=Path, required=True, help="Path to support_registry_update.json")
    parser.add_argument(
        "--registry",
        type=Path,
        default=None,
        help="Optional existing curated_support_registry.json to merge into",
    )
    parser.add_argument("--output", type=Path, required=True, help="Path to write curated_support_registry.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = write_curated_support_registry(
        args.output.resolve(),
        args.registry_update.resolve(),
        existing_registry=args.registry.resolve() if args.registry else None,
    )
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "registry_item_count": payload.get("registry_item_count"),
                "accepted_applied_count": payload.get("accepted_applied_count"),
                "rejected_logged_count": payload.get("rejected_logged_count"),
                "pending_count": payload.get("pending_count"),
                "by_review_status": payload.get("by_review_status"),
                "by_support_status": payload.get("by_support_status"),
                "by_case_review_status": payload.get("by_case_review_status"),
                "all_accepted_case_count": payload.get("all_accepted_case_count"),
                "mixed_review_status_case_count": payload.get("mixed_review_status_case_count"),
                "all_rejected_case_count": payload.get("all_rejected_case_count"),
                "all_accepted_cases": payload.get("all_accepted_cases"),
                "mixed_review_status_cases": payload.get("mixed_review_status_cases"),
                "all_rejected_cases": payload.get("all_rejected_cases"),
                "schema_status": payload.get("schema_status"),
                "schema_upgraded_item_count": payload.get("schema_upgraded_item_count"),
                "by_schema_upgrade_reason": payload.get("by_schema_upgrade_reason"),
                "schema_upgraded_update_count": payload.get("schema_upgraded_update_count"),
                "by_update_schema_upgrade_reason": payload.get("by_update_schema_upgrade_reason"),
                "schema_upgraded_decision_event_count": payload.get("schema_upgraded_decision_event_count"),
                "by_decision_schema_upgrade_reason": payload.get("by_decision_schema_upgrade_reason"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
