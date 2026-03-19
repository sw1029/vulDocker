from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, List

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator.support_extract import write_support_review_index


def _collect_support_candidate_paths(inputs: Iterable[Path]) -> List[Path]:
    collected: List[Path] = []
    seen = set()
    for raw in inputs:
        path = raw.resolve()
        if path.is_file():
            candidates = [path]
        elif path.is_dir():
            direct = path / "support_candidate.json"
            if direct.exists():
                candidates = [direct]
            else:
                candidates = sorted(path.rglob("support_candidate.json"))
        else:
            continue
        for candidate in candidates:
            if candidate.name != "support_candidate.json":
                continue
            token = str(candidate)
            if token in seen:
                continue
            seen.add(token)
            collected.append(candidate)
    return collected


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate measured support candidates into a review index")
    parser.add_argument("inputs", nargs="+", type=Path, help="support_candidate.json file or directory containing support candidates")
    parser.add_argument("--output", type=Path, required=True, help="Path to write support_review_index.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    candidate_paths = _collect_support_candidate_paths(args.inputs)
    if not candidate_paths:
        raise SystemExit("no support_candidate.json files found")
    payload = write_support_review_index(args.output.resolve(), candidate_paths)
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "support_candidate_file_count": payload.get("support_candidate_file_count"),
                "reviewable_bundle_count": payload.get("reviewable_bundle_count"),
                "all_reviewable_case_count": payload.get("all_reviewable_case_count"),
                "mixed_case_count": payload.get("mixed_case_count"),
                "all_blocked_case_count": payload.get("all_blocked_case_count"),
                "reviewable_cases": payload.get("reviewable_cases"),
                "all_reviewable_cases": payload.get("all_reviewable_cases"),
                "mixed_cases": payload.get("mixed_cases"),
                "all_blocked_cases": payload.get("all_blocked_cases"),
                "by_case_status": payload.get("by_case_status"),
                "by_support_status": payload.get("by_support_status"),
                "mechanically_healthy_bundle_count": payload.get("mechanically_healthy_bundle_count"),
                "promotion_policy_ready_bundle_count": payload.get("promotion_policy_ready_bundle_count"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
