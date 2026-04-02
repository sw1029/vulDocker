from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator.support_extract import write_support_registry_update


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply reviewer decisions to a measured support review index")
    parser.add_argument("--review-index", type=Path, required=True, help="Path to support_review_index.json")
    parser.add_argument("--decisions", type=Path, required=True, help="Path to reviewer decisions JSON")
    parser.add_argument("--output", type=Path, required=True, help="Path to write support_registry_update.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = write_support_registry_update(
        args.output.resolve(),
        args.review_index.resolve(),
        args.decisions.resolve(),
    )
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "accepted_count": payload.get("accepted_count"),
                "rejected_count": payload.get("rejected_count"),
                "pending_count": payload.get("pending_count"),
                "invalid_decision_count": payload.get("invalid_decision_count"),
                "all_reviewable_case_count": payload.get("all_reviewable_case_count"),
                "mixed_case_count": payload.get("mixed_case_count"),
                "all_blocked_case_count": payload.get("all_blocked_case_count"),
                "all_reviewable_cases": payload.get("all_reviewable_cases"),
                "mixed_cases": payload.get("mixed_cases"),
                "all_blocked_cases": payload.get("all_blocked_cases"),
                "by_case_status": payload.get("by_case_status"),
                "accepted_by_support_status": payload.get("accepted_by_support_status"),
                "rejected_by_support_status": payload.get("rejected_by_support_status"),
                "pending_by_support_status": payload.get("pending_by_support_status"),
                "by_generation_path_class": payload.get("by_generation_path_class"),
                "by_generation_positive_bucket": payload.get("by_generation_positive_bucket"),
                "by_generation_non_live_reason": payload.get("by_generation_non_live_reason"),
                "live_positive_ready_bundle_count": payload.get("live_positive_ready_bundle_count"),
                "live_positive_blocked_bundle_count": payload.get("live_positive_blocked_bundle_count"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
