"""Reviewer microservice for TODO 14 stabilization."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from common.llm import LLMClient
from common.logging import get_logger
from common.paths import ensure_dir
from common.plan import load_plan
from common.prompts import build_reviewer_prompt
from common.run_matrix import (
    VulnBundle,
    artifacts_dir_for_bundle,
    bundle_requirement,
    load_vuln_bundles,
    metadata_dir_for_bundle,
    workspace_dir_for_bundle,
)
from common.variability import VariationManager
from orchestrator.loop_controller import LoopController
from evals.poc_verifier import evaluate_with_vuln
from evals.poc_verifier import csrf as _verifier_csrf  # noqa: F401
from evals.poc_verifier import mvp_sqli as _verifier_sqli  # noqa: F401

LOGGER = get_logger(__name__)
SQLI_PATTERN = re.compile(r"SELECT.+\{.+\}", re.IGNORECASE | re.DOTALL)


@dataclass
class ReviewerContext:
    sid: str
    bundle: VulnBundle
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
        self.plan = load_plan(sid)
        self.metadata_root = ensure_dir(Path(self.plan["paths"]["metadata"]))
        loop_cfg = self.plan.get("loop", {"max_loops": 3})
        self.loop_controller = LoopController(sid, max_loops=int(loop_cfg.get("max_loops", 3)))
        self.variation_manager = VariationManager(self.plan.get("variation_key"), seed=self.plan["requirement"].get("seed"))
        profile = self.variation_manager.profile_for("reviewer", override_mode=mode)
        reviewer_model = self.plan["requirement"].get("reviewer_model") or self.plan["requirement"].get(
            "model_version", "gpt-4.1-mini"
        )
        self.llm = LLMClient(reviewer_model, profile)
        self.bundles = load_vuln_bundles(self.plan)

    def run(self) -> None:
        if self.loop_controller.current_loop == 0:
            self.loop_controller.start_loop()

        bundle_reports: List[Dict[str, Any]] = []
        aggregated_issues: List[Dict[str, Any]] = []
        blocking_bundles: List[str] = []

        for bundle in self.bundles:
            context = self._evaluate_bundle(bundle)
            static_issues = self._scan_workspace(bundle)
            all_issues = context.issues + static_issues
            blocking = context.blocking or any(issue.get("severity") in {"high", "critical"} for issue in all_issues)
            run_summary = {
                "sid": self.sid,
                "bundle": {"vuln_id": bundle.vuln_id, "slug": bundle.slug},
                "requirement": self.plan["requirement"],
                "log_excerpt": context.log_excerpt,
                "issues": all_issues,
            }
            llm_feedback = self.llm.generate(build_reviewer_prompt(run_summary))
            report = {
                "sid": self.sid,
                "bundle": {"vuln_id": bundle.vuln_id, "slug": bundle.slug},
                "trace_id": f"{self.sid}-review-{bundle.slug}-{self.loop_controller.current_loop}",
                "loop_count": self.loop_controller.current_loop,
                "issues": all_issues,
                "blocking": blocking,
                "log_path": str(context.log_path),
                "success": context.success,
                "llm_feedback": llm_feedback,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            bundle_path = self._write_bundle_report(bundle, report)
            bundle_reports.append(
                {
                    "vuln_id": bundle.vuln_id,
                    "slug": bundle.slug,
                    "report_path": str(bundle_path),
                    "blocking": blocking,
                    "issues": len(all_issues),
                }
            )
            if blocking:
                blocking_bundles.append(bundle.slug)
            aggregated_issues.extend(all_issues[:3])  # cap per bundle for summary

        blocking_overall = bool(blocking_bundles)
        summary_report = {
            "sid": self.sid,
            "loop_count": self.loop_controller.current_loop,
            "bundles": bundle_reports,
            "blocking_bundles": blocking_bundles,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "issues_sample": aggregated_issues[:5],
        }
        self._write_summary(summary_report)
        self._write_index(bundle_reports)

        if blocking_overall:
            reason = f"Blocking issues detected in bundles: {', '.join(blocking_bundles)}"
            self.loop_controller.record_failure(
                stage="REVIEW",
                reason=reason,
                fix_hint="Inspect reviewer bundle reports for remediation guidance.",
                blocking=True,
                metadata={"bundles": blocking_bundles},
            )
        else:
            self.loop_controller.record_success(stage="REVIEW", note="All bundles cleared reviewer checks")

    def _evaluate_bundle(self, bundle: VulnBundle) -> ReviewerContext:
        log_path = artifacts_dir_for_bundle(self.plan, bundle, "run") / "run.log"
        if not log_path.exists():
            return ReviewerContext(
                sid=self.sid,
                bundle=bundle,
                log_path=log_path,
                log_excerpt="run log missing",
                success=False,
                issues=[
                    self._issue_stub(
                        bundle=bundle,
                        file="poc.py",
                        line=0,
                        issue="Run log missing",
                        fix_hint="Re-run executor to collect bundle-specific run.log",
                    )
                ],
                blocking=True,
                reason="run.log missing",
                fix_hint="Repeat EXECUTOR RUN step for this bundle",
            )
        bundle_requirement_view = bundle_requirement(self.plan["requirement"], bundle)
        run_summary = self._load_run_summary(bundle)
        try:
            result = evaluate_with_vuln(
                bundle.vuln_id,
                log_path,
                requirement=bundle_requirement_view,
                run_summary=run_summary,
                plan_policy=self.plan.get("policy"),
            )
        except FileNotFoundError:
            return ReviewerContext(
                sid=self.sid,
                bundle=bundle,
                log_path=log_path,
                log_excerpt="run log missing",
                success=False,
                issues=[
                    self._issue_stub(
                        bundle=bundle,
                        file="poc.py",
                        line=0,
                        issue="Run log missing",
                        fix_hint="Re-run executor to collect bundle-specific run.log",
                        evidence=[str(log_path)],
                    )
                ],
                blocking=True,
                reason="run.log missing",
                fix_hint="Repeat EXECUTOR RUN step for this bundle",
            )
        success = bool(result.get("verify_pass"))
        issues: List[Dict[str, Any]] = []
        reason = ""
        fix_hint = ""
        blocking_status = {"evaluated", "evaluated-llm", None}
        blocking = (not success) or (result.get("status") not in blocking_status)
        if not success:
            reason = result.get("evidence") or "PoC verification failed"
            fix_hint = "Inspect application logs and PoC payload"
            issues.append(
                self._issue_stub(
                    bundle=bundle,
                    file="poc.py",
                    line=0,
                    issue=reason,
                    fix_hint=fix_hint,
                    evidence=[str(log_path)],
                )
            )
        content = log_path.read_text(encoding="utf-8")
        excerpt = content[-2000:] if content else ""
        return ReviewerContext(
            sid=self.sid,
            bundle=bundle,
            log_path=log_path,
            log_excerpt=excerpt,
            success=success,
            issues=issues,
            blocking=blocking,
            reason=reason,
            fix_hint=fix_hint,
        )

    def _load_run_summary(self, bundle: VulnBundle) -> Dict[str, Any]:
        summary_path = artifacts_dir_for_bundle(self.plan, bundle, "run") / "summary.json"
        if not summary_path.exists():
            return {}
        try:
            return json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _scan_workspace(self, bundle: VulnBundle) -> List[Dict[str, Any]]:
        issues: List[Dict[str, Any]] = []
        workspace = workspace_dir_for_bundle(self.plan, bundle)
        if not workspace.exists():
            return issues
        for path in workspace.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for match in SQLI_PATTERN.finditer(text):
                line = text[: match.start()].count("\n") + 1
                issues.append(
                    self._issue_stub(
                        bundle=bundle,
                        file=str(path.relative_to(workspace)),
                        line=line,
                        issue="Raw SQL string interpolation detected",
                        fix_hint="Switch to parameterized queries or ORM bind parameters",
                    )
                )
        return issues

    def _issue_stub(
        self,
        *,
        bundle: VulnBundle,
        file: str,
        line: int,
        issue: str,
        fix_hint: str,
        evidence: List[str] | None = None,
    ) -> Dict[str, Any]:
        return {
            "sid": self.sid,
            "bundle_slug": bundle.slug,
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

    def _write_bundle_report(self, bundle: VulnBundle, report: Dict[str, Any]) -> Path:
        bundle_dir = metadata_dir_for_bundle(self.plan, bundle)
        report_path = bundle_dir / "reviewer_report.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        LOGGER.info("Reviewer bundle report written to %s", report_path)
        return report_path

    def _write_summary(self, report: Dict[str, Any]) -> None:
        path = self.metadata_root / "reviewer_report.json"
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        LOGGER.info("Reviewer summary report written to %s", path)

    def _write_index(self, bundle_reports: List[Dict[str, Any]]) -> None:
        index_path = self.metadata_root / "reviewer_reports.json"
        payload = {"sid": self.sid, "bundles": bundle_reports}
        index_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        LOGGER.info("Reviewer bundle index written to %s", index_path)


__all__ = ["ReviewerService"]
