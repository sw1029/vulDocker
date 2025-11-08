"""Compute diversity and reproducibility metrics for a Scenario ID."""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.logging import get_logger
from common.paths import ensure_dir, get_artifacts_dir, get_metadata_dir

LOGGER = get_logger(__name__)


class DiversityEvaluator:
    """Aggregates generator candidates and loop state statistics."""

    def __init__(self, sid: str, output: Path | None = None) -> None:
        self.sid = sid
        self.metadata_dir = ensure_dir(get_metadata_dir(sid))
        reports_dir = ensure_dir(get_artifacts_dir(sid) / "reports")
        self.output = output or (reports_dir / "diversity.json")

    def run(self) -> Path:
        plan = self._load_json(self.metadata_dir / "plan.json")
        candidates = self._load_candidates()
        entropy = self._shannon_entropy(candidates)
        scenario_distance = self._scenario_distance(candidates)
        reproducibility = self._reproducibility_rate()
        payload = {
            "sid": self.sid,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "variation_key": plan.get("variation_key"),
            "metrics": {
                "shannon_entropy": entropy,
                "scenario_distance": scenario_distance,
                "reproducibility_rate": reproducibility,
                "candidate_count": len(candidates),
            },
            "dimensions": {
                "language": plan["requirement"].get("language"),
                "framework": plan["requirement"].get("framework"),
                "pattern_id": plan["requirement"].get("pattern_id"),
            },
        }
        self.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        LOGGER.info("Diversity metrics written to %s", self.output)
        return self.output

    # Helpers --------------------------------------------------------------

    def _load_json(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"Required metadata missing: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _load_candidates(self) -> List[Dict[str, Any]]:
        path = self.metadata_dir / "generator_candidates.json"
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("candidates", [])

    def _shannon_entropy(self, candidates: List[Dict[str, Any]]) -> float:
        if not candidates:
            return 0.0
        counts: Dict[str, int] = {}
        for candidate in candidates:
            template_id = candidate.get("template_id") or candidate.get("metadata", {}).get("pattern_id") or "unknown"
            counts[template_id] = counts.get(template_id, 0) + 1
        total = sum(counts.values())
        entropy = 0.0
        for count in counts.values():
            probability = count / total
            entropy -= probability * math.log(probability, 2)
        return round(entropy, 4)

    def _scenario_distance(self, candidates: List[Dict[str, Any]]) -> float:
        if not candidates:
            return 0.0
        patterns = {
            candidate.get("metadata", {}).get("pattern_id") or candidate.get("template_id")
            for candidate in candidates
        }
        return round(len(patterns) / len(candidates), 4)

    def _reproducibility_rate(self) -> float:
        path = self.metadata_dir / "loop_state.json"
        if not path.exists():
            return 1.0
        data = json.loads(path.read_text(encoding="utf-8"))
        history = data.get("history", [])
        if not history:
            return 1.0
        success = sum(1 for entry in history if entry.get("success"))
        return round(success / max(1, len(history)), 4)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute diversity metrics for a scenario")
    parser.add_argument("--sid", required=True)
    parser.add_argument("--output", type=Path, help="Optional output path (defaults to artifacts/<sid>/reports/diversity.json)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    evaluator = DiversityEvaluator(args.sid, output=args.output)
    evaluator.run()


if __name__ == "__main__":
    main()
