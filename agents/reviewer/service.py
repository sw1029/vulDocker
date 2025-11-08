"""Reviewer microservice for TODO 14 stabilization."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from common.config import get_decoding_profile
from common.llm import LLMClient
from common.logging import get_logger
from common.paths import ensure_dir, get_artifacts_dir, get_metadata_dir
from common.prompts import build_reviewer_prompt
from orchestrator.loop_controller import LoopController

LOGGER = get_logger(__name__)
SQLI_PATTERN = re.compile(r"SELECT.+\{.+\}", re.IGNORECASE | re.DOTALL)


def _load_plan(sid: str) -> Dict[str, Any]:
    plan_path = get_metadata_dir(sid) / "plan.json"
    if not plan_path.exists():
        raise FileNotFoundError(f"Plan not found for {sid}")
    return json.loads(plan_path.read_text(encoding="utf-8"))


@dataclass
class ReviewerContext:
    sid: str
    log_path: Path
    log_excerpt: str
    success: bool
    issues: List[Dict[str, Any]]
    blocking: bool
    reason: str
    fix_hint: str


class ReviewerService:
    """Analyzes executor logs + static patterns and records loop outcomes."""

    def __init__(self, sid: str, mode: str = "deterministic") -> None:
        self.sid = sid
        self.plan = _load_plan(sid)
        self.metadata_dir = ensure_dir(Path(self.plan["paths"]["metadata"]))
        self.workspace = Path(self.plan["paths"]["workspace"])
        loop_cfg = self.plan.get("loop", {"max_loops": 3})
        self.loop_controller = LoopController(sid, max_loops=int(loop_cfg.get("max_loops", 3)))
        profile = get_decoding_profile(mode)
        reviewer_model = self.plan["requirement"].get("reviewer_model") or self.plan["requirement"].get(
            "model_version", "gpt-4.1-mini"
        )
        self.llm = LLMClient(reviewer_model, profile)

    def run(self) -> None:
        if self.loop_controller.current_loop == 0:
            self.loop_controller.start_loop()

        context = self._evaluate()
        static_issues = self._scan_workspace()
        all_issues = context.issues + static_issues
        blocking = context.blocking or any(issue.get("severity") in {"high", "critical"} for issue in all_issues)
        run_summary = {
            "sid": self.sid,
            "requirement": self.plan["requirement"],
            "log_excerpt": context.log_excerpt,
            "issues": all_issues,
        }
        llm_feedback = self.llm.generate(build_reviewer_prompt(run_summary))
        report = {
            "sid": self.sid,
            "trace_id": f"{self.sid}-review-{self.loop_controller.current_loop}",
            "loop_count": self.loop_controller.current_loop,
            "issues": all_issues,
            "blocking": blocking,
            "log_path": str(context.log_path),
            "success": context.success,
            "llm_feedback": llm_feedback,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._write_report(report)
        if blocking:
            reason = context.reason or "Blocking static issue detected"
            fix_hint = context.fix_hint or "Follow reviewer suggestions in report"
            self.loop_controller.record_failure(
                stage="REVIEW",
                reason=reason,
                fix_hint=fix_hint,
                blocking=True,
                metadata={"issues": all_issues[:3]},
            )
        else:
            self.loop_controller.record_success(stage="REVIEW", note="All blocking checks passed")

    def _evaluate(self) -> ReviewerContext:
        log_path = get_artifacts_dir(self.sid) / "run" / "run.log"
        if not log_path.exists():
            return ReviewerContext(
                sid=self.sid,
                log_path=log_path,
                log_excerpt="run log missing",
                success=False,
                issues=[
                    self._issue_stub(
                        file="poc.py",
                        line=0,
                        issue="Run log missing",
                        fix_hint="Re-run executor to collect run.log",
                    )
                ],
                blocking=True,
                reason="run.log missing",
                fix_hint="Repeat EXECUTOR RUN step",
            )
        content = log_path.read_text(encoding="utf-8")
        success = "SQLi SUCCESS" in content
        issues: List[Dict[str, Any]] = []
        reason = ""
        fix_hint = ""
        blocking = not success
        if not success:
            reason = "SQLi SUCCESS marker missing"
            fix_hint = "Inspect application logs and PoC payload"
            issues.append(
                self._issue_stub(
                    file="poc.py",
                    line=0,
                    issue=reason,
                    fix_hint=fix_hint,
                    evidence=[str(log_path)],
                )
            )
        excerpt = content[-2000:] if content else ""
        return ReviewerContext(
            sid=self.sid,
            log_path=log_path,
            log_excerpt=excerpt,
            success=success,
            issues=issues,
            blocking=blocking,
            reason=reason,
            fix_hint=fix_hint,
        )

    def _scan_workspace(self) -> List[Dict[str, Any]]:
        issues: List[Dict[str, Any]] = []
        if not self.workspace.exists():
            return issues
        for path in self.workspace.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for match in SQLI_PATTERN.finditer(text):
                line = text[: match.start()].count("\n") + 1
                issues.append(
                    self._issue_stub(
                        file=str(path.relative_to(self.workspace)),
                        line=line,
                        issue="Raw SQL string interpolation detected",
                        fix_hint="Switch to parameterized queries or ORM bind parameters",
                    )
                )
        return issues

    def _issue_stub(
        self,
        *,
        file: str,
        line: int,
        issue: str,
        fix_hint: str,
        evidence: List[str] | None = None,
    ) -> Dict[str, Any]:
        return {
            "sid": self.sid,
            "file": file,
            "line": max(1, line),
            "issue": issue,
            "fix_hint": fix_hint,
            "severity": "high",
            "test_change": "Add PoC regression test",
            "evidence_log_ids": evidence or [],
            "blocking": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def _write_report(self, report: Dict[str, Any]) -> None:
        report_path = self.metadata_dir / "reviewer_report.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        LOGGER.info("Reviewer report written to %s", report_path)


__all__ = ["ReviewerService"]
