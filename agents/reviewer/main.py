"""Reviewer agent placeholder for MVP."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.config import get_decoding_profile
from common.llm import LLMClient
from common.logging import get_logger
from common.paths import get_artifacts_dir, get_metadata_dir
from common.prompts import build_reviewer_prompt

LOGGER = get_logger(__name__)


def load_plan(sid: str) -> Dict[str, object]:
    plan_path = get_metadata_dir(sid) / "plan.json"
    if not plan_path.exists():
        raise FileNotFoundError(f"Plan not found for {sid}")
    return json.loads(plan_path.read_text(encoding="utf-8"))


def read_run_log(sid: str) -> str:
    run_log_path = get_artifacts_dir(sid) / "run" / "run.log"
    if not run_log_path.exists():
        return "run log missing"
    return run_log_path.read_text(encoding="utf-8")


class ReviewerAgent:
    def __init__(self, sid: str, mode: str) -> None:
        self.sid = sid
        self.plan = load_plan(sid)
        self.metadata_dir = Path(self.plan["paths"]["metadata"])  # already ensured
        self.run_log = read_run_log(sid)
        profile = get_decoding_profile(mode)
        model = self.plan["requirement"].get("model_version", "gpt-4.1-mini")
        self.llm = LLMClient(model, profile)

    def run(self) -> None:
        summary = {
            "sid": self.sid,
            "requirement": self.plan["requirement"],
            "log_excerpt": self.run_log[-2000:],
        }
        messages = build_reviewer_prompt(summary)
        llm_feedback = self.llm.generate(messages)
        report = {
            "sid": self.sid,
            "issues": self._auto_detect_issues(),
            "llm_feedback": llm_feedback,
        }
        report_path = self.metadata_dir / "reviewer_report.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        LOGGER.info("Reviewer report saved to %s", report_path)

    def _auto_detect_issues(self) -> List[Dict[str, str]]:
        issues: List[Dict[str, str]] = []
        if "SQLi SUCCESS" not in self.run_log:
            issues.append(
                {
                    "file": "poc.py",
                    "line": 0,
                    "issue": "Expected SQLi SUCCESS marker missing",
                    "fix_hint": "Check PoC execution or run logs",
                    "severity": "high",
                }
            )
        return issues


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reviewer agent")
    parser.add_argument("--sid", required=True)
    parser.add_argument("--mode", default="deterministic")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    agent = ReviewerAgent(args.sid, args.mode)
    agent.run()


if __name__ == "__main__":
    main()
