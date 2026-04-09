"""Reviewer microservice for TODO 14 stabilization."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from common.guardrails import GuardEngine, load_guard_spec
from common.llm import DEFAULT_LLM_MODEL, LLMClient, llm_execution_summary
from common.logging import get_logger
from common.name_only import is_name_driven_requirement
from common.bundle_state import bundle_research_blocker
from common.paths import ensure_dir
from common.plan import load_plan
from common.prompts import build_reviewer_prompt, prompt_contract
from common.roles import role_matches
from common.rules import load_rule, load_static_rule
from common.contracts import load_generator_contract
from common.vuln_semantics import evaluate_workspace_semantics, semantic_error_summary
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

    def __init__(self, sid: str, mode: str = "deterministic", *, record_loop_outcome: bool = True) -> None:
        self.sid = sid
        self.plan = load_plan(sid)
        self.record_loop_outcome = record_loop_outcome
        self.metadata_root = ensure_dir(Path(self.plan["paths"]["metadata"]))
        self._register_runtime_rules()
        loop_cfg = self.plan.get("loop", {"max_loops": 3})
        self.loop_controller = LoopController(sid, max_loops=int(loop_cfg.get("max_loops", 3)))
        self.variation_manager = VariationManager(self.plan.get("variation_key"), seed=self.plan["requirement"].get("seed"))
        profile = self.variation_manager.profile_for("reviewer", override_mode=mode)
        reviewer_model = self.plan["requirement"].get("reviewer_model") or self.plan["requirement"].get(
            "model_version", DEFAULT_LLM_MODEL
        )
        self.llm = LLMClient(reviewer_model, profile)
        self.bundles = load_vuln_bundles(self.plan)
        self._llm_prompt_invocations: Dict[str, int] = {}

    def _record_prompt_invocation(
        self,
        name: str,
        *,
        prompt_invocations: Optional[Dict[str, int]] = None,
    ) -> None:
        token = str(name or "").strip()
        if not token:
            return
        current = getattr(self, "_llm_prompt_invocations", None)
        if not isinstance(current, dict):
            current = {}
            self._llm_prompt_invocations = current
        current[token] = int(current.get(token) or 0) + 1
        if isinstance(prompt_invocations, dict):
            prompt_invocations[token] = int(prompt_invocations.get(token) or 0) + 1

    @staticmethod
    def _normalize_prompt_invocations(prompt_invocations: Optional[Dict[str, int]]) -> Dict[str, int]:
        if not isinstance(prompt_invocations, dict):
            return {}
        normalized: Dict[str, int] = {}
        for key, value in prompt_invocations.items():
            token = str(key or "").strip()
            if not token:
                continue
            try:
                count = int(value)
            except Exception:
                continue
            if count > 0:
                normalized[token] = count
        return normalized

    def _llm_execution_summary(
        self,
        *,
        prompt_invocations: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        llm = getattr(self, "llm", None)
        if llm is None:
            return {}
        prompt_counts = self._normalize_prompt_invocations(prompt_invocations)
        metadata: Dict[str, Any] = {"cache_mode": "none"}
        if prompt_counts:
            metadata["prompt_contracts"] = [prompt_contract(name) for name in prompt_counts]
            metadata["prompt_invocations"] = prompt_counts
            metadata["retry_budget"] = {
                **self._retry_budget_context(),
                "reviewer_feedback_runs": int(prompt_counts.get("reviewer", 0) or 0),
            }
        return llm_execution_summary(llm, observed=True, metadata=metadata)

    def _retry_budget_context(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        loop_controller = getattr(self, "loop_controller", None)
        if loop_controller is None:
            return payload
        try:
            current_loop = int(getattr(loop_controller, "current_loop", 0))
        except Exception:
            current_loop = 0
        try:
            max_loops = int(getattr(loop_controller, "max_loops", 0))
        except Exception:
            max_loops = 0
        if current_loop > 0:
            payload["controller_loop_current"] = current_loop
        if max_loops > 0:
            payload["controller_loop_max"] = max_loops
        return payload

    def run(self) -> None:
        record_loop_outcome = getattr(self, "record_loop_outcome", True)
        if record_loop_outcome and self.loop_controller.current_loop == 0:
            self.loop_controller.start_loop()

        bundle_reports: List[Dict[str, Any]] = []
        aggregated_issues: List[Dict[str, Any]] = []
        blocking_bundles: List[str] = []

        for bundle in self.bundles:
            research_blocker = bundle_research_blocker(self.plan, bundle)
            if research_blocker:
                report = self._write_research_blocked_bundle_report(bundle, research_blocker)
                bundle_reports.append(report)
                aggregated_issues.extend(report.get("issues_sample") or [])
                continue
            bundle_prompt_invocations: Dict[str, int] = {}
            context = self._evaluate_bundle(bundle)
            static_issues = self._scan_workspace(bundle, exploit_success=context.success)
            semantic_contract_issues = self._semantic_contract_issues(bundle)
            confidence_issues = self._confidence_issues(bundle)
            all_issues = context.issues + static_issues + semantic_contract_issues + confidence_issues
            blocking = context.blocking or any(bool(issue.get("blocking")) for issue in all_issues)
            run_summary = {
                "sid": self.sid,
                "bundle": {"vuln_id": bundle.vuln_id, "slug": bundle.slug},
                "requirement": self.plan["requirement"],
                "log_excerpt": context.log_excerpt,
                "issues": all_issues,
            }
            llm_feedback = self._llm_feedback(
                run_summary,
                all_issues=all_issues,
                blocking=blocking,
                prompt_invocations=bundle_prompt_invocations,
            )
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
            llm_execution = self._llm_execution_summary(prompt_invocations=bundle_prompt_invocations)
            if llm_execution:
                report["llm_execution"] = llm_execution
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
            "blocking": blocking_overall,
            "success": not blocking_overall,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "issues_sample": aggregated_issues[:5],
        }
        llm_execution = self._llm_execution_summary(prompt_invocations=getattr(self, "_llm_prompt_invocations", {}))
        if llm_execution:
            summary_report["llm_execution"] = llm_execution
        self._write_summary(summary_report)
        self._write_index(bundle_reports)

        if not record_loop_outcome:
            return

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

    def _write_research_blocked_bundle_report(self, bundle: VulnBundle, blocker: Dict[str, Any]) -> Dict[str, Any]:
        issue = self._issue_stub(
            bundle=bundle,
            file="researcher_report.json",
            line=1,
            issue=str(blocker.get("reason") or "Bundle was fail-closed before generation"),
            fix_hint=(
                "Add compiler-backed support or stronger researcher evidence for this bundle "
                "before expecting reviewable runtime artifacts."
            ),
            evidence=[str(blocker.get("report_path") or "")] if blocker.get("report_path") else [],
            severity="low",
            blocking=False,
        )
        report = {
            "sid": self.sid,
            "bundle": {"vuln_id": bundle.vuln_id, "slug": bundle.slug},
            "trace_id": f"{self.sid}-review-{bundle.slug}-{self.loop_controller.current_loop}",
            "loop_count": self.loop_controller.current_loop,
            "issues": [issue],
            "blocking": False,
            "success": False,
            "research_blocked": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        bundle_path = self._write_bundle_report(bundle, report)
        return {
            "vuln_id": bundle.vuln_id,
            "slug": bundle.slug,
            "report_path": str(bundle_path),
            "blocking": False,
            "issues": 1,
            "research_blocked": True,
            "issues_sample": [issue],
        }

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
        verifier_issues = self._verifier_result_issues(bundle, result)
        if verifier_issues:
            issues.extend(verifier_issues)
            if any(bool(issue.get("blocking")) for issue in verifier_issues):
                blocking = True
                if success:
                    success = False
                    reason = verifier_issues[0].get("issue") or "Verifier trust checks failed"
                    fix_hint = verifier_issues[0].get("fix_hint") or "Align verifier contract and guard checks"
        exit_issues, exit_reason = self._check_exit_code_policy(bundle, run_summary)
        if exit_issues:
            issues.extend(exit_issues)
            if success:
                success = False
                reason = exit_reason or "Non-zero exit code detected"
                fix_hint = "Inspect executor logs and container exit status"
            blocking = True
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

    def _verifier_result_issues(self, bundle: VulnBundle, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        issues: List[Dict[str, Any]] = []
        meta_dir = metadata_dir_for_bundle(self.plan, bundle)
        contract_path = meta_dir / "resolved_contract.json"
        contract_evidence = [str(contract_path)] if contract_path.exists() else []
        verification_trust = str(result.get("verification_trust") or "").strip().lower()
        verification_rule_source = str(result.get("verification_rule_source") or "").strip().lower()
        verification_trust_reason = str(result.get("verification_trust_reason") or "").strip()
        verification_independence = str(result.get("verification_independence") or "").strip().lower()
        if not verification_independence and verification_rule_source == "compiler_runtime_rule":
            verification_independence = "compiler_coupled"

        if verification_trust == "low":
            label = verification_rule_source or "self-derived verifier contract"
            detail = f"Verifier contract trust is low ({label})"
            if verification_trust_reason:
                detail += f": {verification_trust_reason}"
            issues.append(
                self._issue_stub(
                    bundle=bundle,
                    file="resolved_contract.json",
                    line=1,
                    issue=detail,
                    fix_hint=(
                        "Treat this bundle as inspection-only until a declared static/runtime rule or "
                        "independent verifier path is available."
                    ),
                    evidence=contract_evidence,
                    severity="medium",
                    blocking=False,
                )
            )

        if verification_independence == "compiler_coupled":
            detail = "Verifier evidence is compiler-coupled (compiler_runtime_rule)"
            if verification_trust_reason:
                detail += f": {verification_trust_reason}"
            issues.append(
                self._issue_stub(
                    bundle=bundle,
                    file="resolved_contract.json",
                    line=1,
                    issue=detail,
                    fix_hint=(
                        "Treat this as a medium-confidence compiler-backed verdict; add a declared independent "
                        "verification rule if this family needs high-confidence promotion."
                    ),
                    evidence=contract_evidence,
                    severity="medium",
                    blocking=False,
                )
            )

        semantic = result.get("semantic_consistency")
        if isinstance(semantic, dict) and semantic.get("supported") and not semantic.get("semantic_match"):
            issues.append(
                self._issue_stub(
                    bundle=bundle,
                    file="resolved_contract.json",
                    line=1,
                    issue=f"Verifier semantic mismatch: {semantic_error_summary(semantic)}",
                    fix_hint="Align generated service/PoC with the resolved semantic contract before promotion.",
                    evidence=contract_evidence,
                    severity="critical",
                    blocking=True,
                )
            )
        semantic_supported = result.get("semantic_supported")
        semantic_status = str(result.get("semantic_status") or "").strip().lower()
        if semantic_supported is False:
            issues.append(
                self._issue_stub(
                    bundle=bundle,
                    file="resolved_contract.json",
                    line=1,
                    issue=(
                        f"Verifier semantic support missing for {bundle.vuln_id}"
                        + (f" (status={semantic_status})" if semantic_status else "")
                    ),
                    fix_hint="Provide a non-empty aligned semantic contract or keep this bundle in failure/inspection-only state.",
                    evidence=contract_evidence,
                    severity="critical",
                    blocking=True,
                )
            )

        guard = result.get("guard_consistency")
        if not isinstance(guard, dict):
            return issues
        if guard.get("required_but_missing"):
            issues.append(
                self._issue_stub(
                    bundle=bundle,
                    file="resolved_contract.json",
                    line=1,
                    issue=str(guard.get("reason") or "Dynamic guard spec missing under failure policy"),
                    fix_hint="Ensure researcher emits guard_spec.json and verifier consumes it consistently.",
                    evidence=contract_evidence,
                    severity="critical",
                    blocking=True,
                )
            )
            return issues

        for scope in ("verifier", "workspace"):
            scope_report = guard.get(scope)
            if not isinstance(scope_report, dict) or scope_report.get("passed") is not False:
                continue
            violations = scope_report.get("violations") or []
            details = "; ".join(str(item).strip() for item in violations if str(item).strip()) or "guard evaluation failed"
            issues.append(
                self._issue_stub(
                    bundle=bundle,
                    file="run.log" if scope == "verifier" else "resolved_contract.json",
                    line=1,
                    issue=f"Verifier guard mismatch ({scope}): {details}",
                    fix_hint="Resolve guard assertion failures before treating this bundle as successful.",
                    evidence=[str(self._load_run_log_path(bundle))] if scope == "verifier" else contract_evidence,
                    severity="critical",
                    blocking=True,
                )
            )
        return issues

    def _bundle_requires_semantic_support(self, bundle: VulnBundle) -> bool:
        requirement = self.plan.get("requirement") if isinstance(self.plan, dict) else {}
        requirement_view = bundle_requirement(requirement, bundle) if isinstance(requirement, dict) else {}
        if is_name_driven_requirement(requirement_view):
            return True
        vuln_id = str(bundle.vuln_id or "").strip().upper()
        if vuln_id.startswith("NAME-"):
            return True
        return not bool(load_static_rule(vuln_id))

    def _llm_feedback(
        self,
        run_summary: Dict[str, Any],
        *,
        all_issues: List[Dict[str, Any]],
        blocking: bool,
        prompt_invocations: Optional[Dict[str, int]] = None,
    ) -> str:
        explicit = self.plan["requirement"].get("reviewer_always_llm_feedback")
        if explicit is not None:
            enabled = bool(explicit) if not isinstance(explicit, str) else explicit.strip().lower() in {
                "1",
                "true",
                "yes",
                "on",
            }
        else:
            enabled = bool(blocking or all_issues)
        if not enabled:
            return "skipped: clean run without blocking or quality issues"
        self._record_prompt_invocation("reviewer", prompt_invocations=prompt_invocations)
        return self.llm.generate(build_reviewer_prompt(run_summary))

    def _confidence_issues(self, bundle: VulnBundle) -> List[Dict[str, Any]]:
        if not self._bundle_requires_semantic_support(bundle):
            return []
        meta_dir = metadata_dir_for_bundle(self.plan, bundle)
        contract = load_generator_contract(meta_dir)
        if not isinstance(contract, dict):
            return []
        semantic_contract = contract.get("semantic_contract")
        if not isinstance(semantic_contract, dict):
            return []
        relevance = semantic_contract.get("evidence_relevance")
        if not isinstance(relevance, dict):
            return []
        confidence = str(relevance.get("confidence") or "").strip().lower()
        try:
            negative_ratio = float(relevance.get("negative_hit_ratio") or 0.0)
        except Exception:
            negative_ratio = 0.0
        guard_policy = ((self.plan.get("policy") or {}).get("guard") or {})
        policy = str(guard_policy.get("low_confidence_unknown_policy") or "warn").strip().lower()
        issues: List[Dict[str, Any]] = []
        if confidence == "low":
            blocking = policy == "fail_closed"
            issues.append(
                self._issue_stub(
                    bundle=bundle,
                    file="resolved_contract.json",
                    line=1,
                    issue=(
                        "Researcher evidence confidence is low for unknown vulnerability; "
                        "the generated bundle should be treated as low-trust."
                    ),
                    fix_hint="Strengthen evidence quality or set a stricter low_confidence_unknown_policy.",
                    evidence=[str(meta_dir / "resolved_contract.json")],
                    severity="high" if blocking else "medium",
                    blocking=blocking,
                )
            )
        elif confidence == "medium" and negative_ratio >= 0.30:
            issues.append(
                self._issue_stub(
                    bundle=bundle,
                    file="resolved_contract.json",
                    line=1,
                    issue=(
                        "Researcher evidence confidence is medium with high negative-hit ratio; "
                        "verification passed, but evidence remains noisy."
                    ),
                    fix_hint="Review search traces and tighten evidence selection before promoting this bundle.",
                    evidence=[str(meta_dir / "resolved_contract.json")],
                    severity="low",
                    blocking=False,
                )
            )
        return issues

    def _semantic_contract_issues(self, bundle: VulnBundle) -> List[Dict[str, Any]]:
        meta_dir = metadata_dir_for_bundle(self.plan, bundle)
        contract = load_generator_contract(meta_dir)
        if not isinstance(contract, dict):
            return []
        semantic_contract = contract.get("semantic_contract")
        if not isinstance(semantic_contract, dict):
            return []
        contradictions = semantic_contract.get("contradictions")
        if not isinstance(contradictions, list):
            return []
        issues: List[Dict[str, Any]] = []
        for item in contradictions:
            if not isinstance(item, str) or not item.strip():
                continue
            issues.append(
                self._issue_stub(
                    bundle=bundle,
                    file="resolved_contract.json",
                    line=1,
                    issue=f"Semantic contract contradiction: {item.strip()}",
                    fix_hint="Align researcher report, guard spec, and generated artifacts to the same semantic contract.",
                    evidence=[str(meta_dir / "resolved_contract.json")],
                    severity="high",
                    blocking=True,
                )
            )
        return issues

    def _load_run_summary(self, bundle: VulnBundle) -> Dict[str, Any]:
        summary_path = artifacts_dir_for_bundle(self.plan, bundle, "run") / "summary.json"
        if not summary_path.exists():
            return {}
        try:
            return json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _scan_workspace(self, bundle: VulnBundle, *, exploit_success: bool = False) -> List[Dict[str, Any]]:
        issues: List[Dict[str, Any]] = []
        workspace = workspace_dir_for_bundle(self.plan, bundle)
        if not workspace.exists():
            return issues
        rule = load_rule(bundle.vuln_id)
        patterns = rule.get("patterns") if isinstance(rule, dict) else None
        if not isinstance(patterns, list):
            patterns = []

        service_entry = "app.py"
        poc_entry = "poc.py"
        meta_dir = metadata_dir_for_bundle(self.plan, bundle)

        contract = load_generator_contract(meta_dir)
        if isinstance(contract, dict):
            candidate = contract.get("service_entry")
            if isinstance(candidate, str) and candidate.strip():
                service_entry = candidate.strip()
            candidate = contract.get("poc_entry")
            if isinstance(candidate, str) and candidate.strip():
                poc_entry = candidate.strip()

        manifest_path = meta_dir / "generator_manifest.json"
        if manifest_path.exists():
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                payload = {}
            manifest = payload.get("manifest") if isinstance(payload, dict) else None
            if isinstance(manifest, dict):
                for entry in manifest.get("files") or []:
                    if not isinstance(entry, dict):
                        continue
                    role = entry.get("role")
                    path = entry.get("path")
                    if not isinstance(path, str) or not path.strip():
                        continue
                    if role_matches(role, "service_main"):
                        service_entry = path.strip()
                    elif role_matches(role, "poc_entry"):
                        poc_entry = path.strip()

        template_path = meta_dir / "generator_template.json"
        if template_path.exists():
            try:
                template = json.loads(template_path.read_text(encoding="utf-8"))
            except Exception:
                template = {}
            if isinstance(template, dict):
                if service_entry == "app.py":
                    candidate = template.get("service_entry")
                    if isinstance(candidate, str) and candidate.strip():
                        service_entry = candidate.strip()
                if poc_entry == "poc.py":
                    candidate = template.get("poc_entry")
                    if isinstance(candidate, str) and candidate.strip():
                        poc_entry = candidate.strip()

        for pattern in patterns:
            if not isinstance(pattern, dict):
                continue
            ptype = str(pattern.get("type") or "").strip().lower()
            if ptype not in {"file_contains", "poc_contains", "file_regex_contains"}:
                continue
            path = pattern.get("path")
            if not isinstance(path, str) or not path.strip():
                continue
            resolved = (
                path.strip()
                .replace("{{service_entry}}", service_entry)
                .replace("{{poc_entry}}", poc_entry)
            )
            # Unknown placeholders: skip to avoid false positives.
            if "{{" in resolved and "}}" in resolved:
                continue
            target = workspace / resolved
            if not target.exists():
                issues.append(
                    self._issue_stub(
                        bundle=bundle,
                        file=resolved,
                        line=1,
                        issue=f"Rule pattern target missing: {resolved}",
                        fix_hint="Ensure generator writes the expected entry file or update docs/evals/rules patterns",
                        severity="high" if not exploit_success else "medium",
                        blocking=not exploit_success,
                    )
                )
                continue
            try:
                text = target.read_text(encoding="utf-8")
            except Exception:
                continue
            if ptype == "file_regex_contains":
                regex = pattern.get("pattern")
                if not isinstance(regex, str) or not regex:
                    continue
                matched = bool(re.search(regex, text, flags=re.IGNORECASE))
                issue_text = f"Rule pattern miss: expected /{regex}/ in {resolved}"
            else:
                needle = pattern.get("contains")
                if not isinstance(needle, str) or not needle:
                    continue
                matched = needle in text
                issue_text = f"Rule pattern miss: expected '{needle}' in {resolved}"
            if not matched:
                issues.append(
                    self._issue_stub(
                        bundle=bundle,
                        file=resolved,
                        line=1,
                        issue=issue_text,
                        fix_hint="Align generator output with rule patterns or update runtime_rules for this SID",
                        severity="high" if not exploit_success else "medium",
                        blocking=not exploit_success,
                    )
                )
        semantic_report = evaluate_workspace_semantics(bundle.vuln_id, workspace)
        if semantic_report.get("supported") and not semantic_report.get("semantic_match"):
            issues.append(
                self._issue_stub(
                    bundle=bundle,
                    file="app.py",
                    line=1,
                    issue=f"Semantic mismatch for {bundle.vuln_id}: {semantic_error_summary(semantic_report)}",
                    fix_hint=(
                        "Align generated code/PoC with the requested vuln_id semantics before passing REVIEW "
                        "(ex: CWE-352 requires state-changing endpoint and missing CSRF validation)."
                    ),
                    severity="critical" if not exploit_success else "medium",
                    blocking=not exploit_success,
                )
            )

        guard_spec = load_guard_spec(meta_dir)
        guard_engine = GuardEngine(bundle.vuln_id, guard_spec.to_dict() if guard_spec else None)
        guard_eval = guard_engine.evaluate_workspace([workspace])
        if (not guard_engine.available) and guard_engine.should_fail_when_missing_spec():
            issues.append(
                self._issue_stub(
                    bundle=bundle,
                    file=service_entry or "app.py",
                    line=1,
                    issue="Dynamic guard spec missing under failure_policy",
                    fix_hint="Ensure RESEARCH stage emits guard_spec.json for this bundle.",
                    severity="critical",
                    blocking=True,
                )
            )
        elif not guard_eval.passed:
            issues.append(
                self._issue_stub(
                    bundle=bundle,
                    file=service_entry or "app.py",
                    line=1,
                    issue="Dynamic guard mismatch: " + "; ".join(guard_eval.violations or ["unknown violation"]),
                    fix_hint="Apply guard autofix hints and regenerate bundle to satisfy semantic/assertion constraints.",
                    severity="critical" if not exploit_success else "medium",
                    blocking=not exploit_success,
                )
            )
        return issues

    def _check_exit_code_policy(
        self,
        bundle: VulnBundle,
        run_summary: Dict[str, Any],
    ) -> tuple[List[Dict[str, Any]], Optional[str]]:
        issues: List[Dict[str, Any]] = []
        verifier_policy = ((self.plan.get("policy") or {}).get("verifier") or {})
        require_zero = bool(verifier_policy.get("require_exit_code_zero"))
        if not require_zero:
            return issues, None
        if not run_summary or not run_summary.get("run_attempted"):
            return issues, None
        exit_code = run_summary.get("exit_code")
        summary_path = artifacts_dir_for_bundle(self.plan, bundle, "run") / "summary.json"
        if exit_code is None:
            issues.append(
                self._issue_stub(
                    bundle=bundle,
                    file="summary.json",
                    line=0,
                    issue="Exit code metadata missing (policy requires zero)",
                    fix_hint="Re-run executor >= v1.1 to capture exit_code in summary.json",
                    evidence=[str(summary_path)],
                )
            )
            return issues, "exit_code missing"
        if exit_code not in (0, None):
            issues.append(
                self._issue_stub(
                    bundle=bundle,
                    file="summary.json",
                    line=0,
                    issue=f"Executor exit_code={exit_code} (expected 0)",
                    fix_hint="Inspect application/container logs; resolve runtime crash", 
                    evidence=[str(summary_path)],
                )
            )
            return issues, f"exit_code={exit_code}"
        return issues, None

    def _load_run_log_path(self, bundle: VulnBundle) -> Path:
        return artifacts_dir_for_bundle(self.plan, bundle, "run") / "run.log"

    def _issue_stub(
        self,
        *,
        bundle: VulnBundle,
        file: str,
        line: int,
        issue: str,
        fix_hint: str,
        evidence: List[str] | None = None,
        severity: str = "high",
        blocking: bool = True,
    ) -> Dict[str, Any]:
        return {
            "sid": self.sid,
            "bundle_slug": bundle.slug,
            "file": file,
            "line": max(1, line),
            "issue": issue,
            "fix_hint": fix_hint,
            "severity": severity,
            "test_change": "Add PoC regression test",
            "evidence_log_ids": evidence or [],
            "blocking": bool(blocking),
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

    def _register_runtime_rules(self) -> None:
        import os

        allow_override = bool((self.plan.get("policy") or {}).get("allow_runtime_rule_override_static", False))
        os.environ["VULD_ALLOW_RUNTIME_RULE_OVERRIDE_STATIC"] = "true" if allow_override else "false"
        runtime_dir = self.metadata_root / "runtime_rules"
        if not runtime_dir.exists():
            return
        env_key = "VULD_RUNTIME_RULE_DIRS"
        existing = os.environ.get(env_key, "")
        parts = [p for p in existing.split(os.pathsep) if p]
        path_str = str(runtime_dir)
        if path_str not in parts:
            parts.append(path_str)
            os.environ[env_key] = os.pathsep.join(parts)


__all__ = ["ReviewerService"]
