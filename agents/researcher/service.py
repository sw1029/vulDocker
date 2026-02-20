"""Researcher microservice orchestrating ReAct-style retrieval."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from common.guardrails import (
    GENERATOR_OP_ALIASES,
    SUPPORTED_GENERATOR_ASSERTION_OPS,
    SUPPORTED_VERIFIER_ASSERTION_OPS,
    VERIFIER_OP_ALIASES,
    VALID_UNSUPPORTED_OP_POLICIES,
    build_guard_spec,
    default_guard_policy_snapshot,
    parse_guard_spec,
    write_guard_spec,
    write_guard_spec_ensemble,
)
from common.llm import LLMClient
from common.logging import get_logger
from common.paths import ensure_dir, get_repo_root
from common.plan import load_plan
from common.prompts import build_guard_planner_prompt, build_researcher_prompt
from common.rules import load_rule, load_static_rule
from common.run_matrix import (
    VulnBundle,
    bundle_requirement,
    load_vuln_bundles,
    metadata_dir_for_bundle,
)
from common.variability import VariationManager
from orchestrator.plugins import ReactLoop, ReactSpan
from rag.static_loader import load_static_context
from rag.tools import SearchResult, WebSearchTool

LOGGER = get_logger(__name__)


class ResearcherService:
    """Produces researcher_report.json aligned with docs/handbook.md (researcher_report)."""

    def __init__(
        self,
        sid: str,
        mode: str = "deterministic",
        search_limit: int = 3,
        *,
        plan: Optional[Dict[str, Any]] = None,
        bundle: Optional[VulnBundle] = None,
    ) -> None:
        self.sid = sid
        self.plan = plan or load_plan(sid)
        self.bundle = bundle
        base_metadata_dir = ensure_dir(Path(self.plan["paths"]["metadata"]))
        self.metadata_dir = metadata_dir_for_bundle(self.plan, bundle) if bundle else base_metadata_dir
        self.metadata_root = base_metadata_dir
        self.runtime_rules_dir = ensure_dir(self.metadata_root / "runtime_rules")
        self.runtime_templates_dir = ensure_dir(self.metadata_root / "runtime_templates")
        base_requirement = self.plan["requirement"]
        self.requirement = bundle_requirement(base_requirement, bundle) if bundle else base_requirement
        self.variation_manager = VariationManager(self.plan.get("variation_key"), seed=self.requirement.get("seed"))
        self.profile = self.variation_manager.profile_for("researcher", override_mode=mode)
        model = (
            self.requirement.get("researcher_model")
            or self.requirement.get("model_version")
            or "gpt-5.2"
        )
        self.llm = LLMClient(model, self.profile)
        self.react_loop = ReactLoop(sid)
        self.search_tool = WebSearchTool()
        self.search_limit = max(1, search_limit)
        self._last_report: Dict[str, Any] | None = None
        self._last_guard_spec: Dict[str, Any] | None = None

    def run(self) -> Path:
        snapshot = self._snapshot_id()
        rag_context = load_static_context(snapshot)
        queries = self.react_loop.queries_from_requirement(self.requirement)
        active_bundle = self.bundle
        with self.react_loop.span(queries=queries) as span:
            search_hits = self._collect_search_results(queries, span=span)
            evidence = self._build_evidence_payload(search_hits)
            quality, quality_reason = self._evaluate_evidence_quality(active_bundle, search_hits)
            guard_fallback = "guard fallback mode" in (quality_reason or "").lower()
            if quality == "insufficient":
                report = {
                    "sid": self.sid,
                    "vuln_id": active_bundle.vuln_id if active_bundle else self.requirement.get("vuln_id"),
                    "trace_id": self.react_loop.trace_id,
                    "retrieval_snapshot_id": snapshot,
                    "failure_context": self.react_loop.failure_context,
                    "search_policy": self._search_policy(),
                    "evidence": evidence,
                    "semantic_signature": self._default_semantic_signature(active_bundle),
                    "quality": "insufficient",
                    "quality_reason": quality_reason,
                    "guard_fallback": False,
                    "guard_spec_path": None,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                self._last_report = report
                path = self._write_report(report)
                span.event("research_insufficient", reason=quality_reason, path=str(path))
                raise RuntimeError(quality_reason)
            report = self._generate_report(rag_context, search_hits)
            report.setdefault("sid", self.sid)
            if active_bundle:
                report.setdefault("vuln_id", active_bundle.vuln_id)
            report.setdefault("trace_id", self.react_loop.trace_id)
            report.setdefault("retrieval_snapshot_id", snapshot)
            report.setdefault("failure_context", self.react_loop.failure_context)
            report["search_policy"] = self._search_policy()
            report["evidence"] = evidence
            report.setdefault("semantic_signature", self._default_semantic_signature(active_bundle))
            report["quality"] = quality
            report["quality_reason"] = quality_reason or "sufficient evidence"
            report["guard_fallback"] = guard_fallback
            report["created_at"] = datetime.now(timezone.utc).isoformat()
            self._last_report = report
            guard_spec_path, guard_ensemble_path = self._build_and_write_guard_spec(
                report=report,
                evidence=evidence,
                bundle=active_bundle,
            )
            if guard_spec_path:
                report["guard_spec_path"] = str(guard_spec_path)
            if guard_ensemble_path:
                report["guard_spec_ensemble_path"] = str(guard_ensemble_path)
            candidates = self._synthesize_candidates()
            if candidates["rules"]:
                report["candidate_rules"] = candidates["rules"]
            if candidates["templates"]:
                report["candidate_templates"] = candidates["templates"]
            path = self._write_report(report)
            span.event("report_written", path=str(path))
        self.react_loop.record_researcher_report(
            queries=queries,
            search_results=[hit.to_payload() for hit in search_hits],
            report_path=path,
        )
        LOGGER.info("Researcher report saved to %s", path)
        return path

    # Internal helpers -----------------------------------------------------

    def _snapshot_id(self) -> str:
        requirement = self.plan["requirement"]
        return (
            requirement.get("rag_snapshot")
            or requirement.get("corpus_snapshot")
            or "mvp-sample"
        )

    def _collect_search_results(self, queries: Iterable[str], span: ReactSpan) -> List[SearchResult]:
        hits: List[SearchResult] = []
        seen_urls: set[str] = set()
        search_policy = self._search_policy()
        for query in queries:
            new_hits = self.search_tool.search(query, limit=self.search_limit, policy=search_policy)
            span.event("search", query=query, hits=len(new_hits))
            for hit in new_hits:
                if hit.url in seen_urls:
                    continue
                seen_urls.add(hit.url)
                hits.append(hit)
        return hits

    def _generate_report(self, rag_context: str, search_hits: List[SearchResult]) -> Dict[str, Any]:
        prompt = build_researcher_prompt(
            self.requirement,
            search_results=[hit.to_payload() for hit in search_hits],
            rag_context=rag_context,
            failure_context=self.react_loop.failure_context,
            variation_key=self.variation_manager.key,
        )
        raw = self.llm.generate(prompt)
        return self._parse_report(raw)

    def _parse_report(self, raw: str) -> Dict[str, Any]:
        text = (raw or "").strip()
        if text.startswith("```"):
            segments = [segment.strip() for segment in text.split("```") if segment.strip()]
            if segments:
                candidate = segments[0]
                if candidate.lower().startswith("json"):
                    candidate = candidate[4:].strip()
                text = candidate
        try:
            report = json.loads(text)
        except json.JSONDecodeError as exc:
            snippet = text[:400]
            raise RuntimeError(
                "Researcher output is not valid JSON. Ensure docs/handbook.md (researcher_report) is followed.\n"
                f"Snippet: {snippet}"
            ) from exc
        if not isinstance(report, dict):
            raise RuntimeError("Researcher output must be a JSON object per schema.")
        return report

    def _write_report(self, report: Dict[str, Any]) -> Path:
        path = self.metadata_dir / "researcher_report.json"
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def _load_latest_report(self) -> Dict[str, Any]:
        if isinstance(self._last_report, dict):
            return self._last_report
        path = self.metadata_dir / "researcher_report.json"
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        if isinstance(data, dict):
            self._last_report = data
            return data
        return {}

    def _search_policy(self) -> str:
        researcher_cfg = self.requirement.get("researcher") or {}
        if isinstance(researcher_cfg, dict):
            policy = str(researcher_cfg.get("search_policy") or "").strip().lower()
            if policy in {"remote_required", "remote_prefer", "local_only"}:
                return policy
        plan_policy = (self.plan.get("policy") or {}).get("researcher") or {}
        if isinstance(plan_policy, dict):
            policy = str(plan_policy.get("search_policy") or "").strip().lower()
            if policy in {"remote_required", "remote_prefer", "local_only"}:
                return policy
        return "remote_prefer"

    def _allow_candidate_templates(self) -> bool:
        researcher_cfg = self.requirement.get("researcher") or {}
        if not isinstance(researcher_cfg, dict):
            return False
        return bool(researcher_cfg.get("generate_candidate_templates", False))

    def _allow_runtime_rule_override_static(self) -> bool:
        plan_policy = self.plan.get("policy") or {}
        if not isinstance(plan_policy, dict):
            return False
        return bool(plan_policy.get("allow_runtime_rule_override_static", False))

    def _bundle_is_unknown(self, bundle: VulnBundle | None) -> bool:
        if bundle is None:
            vuln_id = str(self.requirement.get("vuln_id") or "").strip()
            if not vuln_id:
                return False
            return not bool(load_static_rule(vuln_id))
        return not bool(load_static_rule(bundle.vuln_id))

    def _require_researcher_evidence(self, bundle: VulnBundle | None) -> bool:
        plan_policy = self.plan.get("policy") or {}
        if isinstance(plan_policy, dict) and "require_researcher_evidence" in plan_policy:
            return bool(plan_policy.get("require_researcher_evidence"))
        return self._bundle_is_unknown(bundle)

    def _guard_policy(self) -> Dict[str, Any]:
        plan_policy = self.plan.get("policy") or {}
        guard_raw = {}
        if isinstance(plan_policy, dict):
            maybe_guard = plan_policy.get("guard")
            if isinstance(maybe_guard, dict):
                guard_raw = maybe_guard
        return default_guard_policy_snapshot(guard_raw)

    def _guard_missing_is_blocking(self, bundle: VulnBundle | None) -> bool:
        failure_policy = str(self._guard_policy().get("failure_policy") or "closed_unknown").strip().lower()
        if failure_policy == "closed_all":
            return True
        if failure_policy == "closed_unknown":
            return self._bundle_is_unknown(bundle)
        return False

    def _guard_budget_mode(self) -> str:
        call_budget = self._guard_policy().get("call_budget") or {}
        if isinstance(call_budget, dict):
            mode = str(call_budget.get("mode") or "").strip().lower()
            if mode:
                return mode
        return "bundle_once"

    def _guard_ensemble_runs(self) -> int:
        call_budget = self._guard_policy().get("call_budget") or {}
        if isinstance(call_budget, dict):
            try:
                value = int(call_budget.get("ensemble_runs", 3))
            except Exception:
                value = 3
            return max(1, value)
        return 3

    def _unsupported_op_policy(self, policy_snapshot: Dict[str, Any]) -> str:
        if not isinstance(policy_snapshot, dict):
            return "normalize_retry"
        value = str(policy_snapshot.get("unsupported_op_policy") or "normalize_retry").strip().lower()
        if value not in VALID_UNSUPPORTED_OP_POLICIES:
            return "normalize_retry"
        return value

    def _normalize_guard_payload_ops(
        self,
        payload: Dict[str, Any],
        *,
        unsupported_policy: str,
        bundle: VulnBundle | None,
        report: Dict[str, Any],
    ) -> Dict[str, Any] | None:
        normalized = dict(payload)
        generator_assertions = normalized.get("generator_assertions")
        verifier_assertions = normalized.get("verifier_assertions")
        if not isinstance(generator_assertions, list):
            generator_assertions = []
        if not isinstance(verifier_assertions, list):
            verifier_assertions = []

        mapped_ops: List[Dict[str, Any]] = []
        dropped_ops: List[Dict[str, Any]] = []
        warnings: List[str] = []
        deferred: List[Dict[str, Any]] = []
        schema_mismatches: List[str] = []

        norm_generators = self._normalize_assertions_for_scope(
            assertions=generator_assertions,
            scope="generator",
            unsupported_policy=unsupported_policy,
            mapped_ops=mapped_ops,
            dropped_ops=dropped_ops,
            warnings=warnings,
            deferred=deferred,
            schema_mismatches=schema_mismatches,
        )
        if norm_generators is None:
            return None
        norm_generators = self._trim_generator_assertions(norm_generators, warnings=warnings)
        norm_verifiers = self._normalize_assertions_for_scope(
            assertions=verifier_assertions,
            scope="verifier",
            unsupported_policy=unsupported_policy,
            mapped_ops=mapped_ops,
            dropped_ops=dropped_ops,
            warnings=warnings,
            deferred=deferred,
            schema_mismatches=schema_mismatches,
        )
        if norm_verifiers is None:
            return None

        normalized["generator_assertions"] = norm_generators
        normalized["verifier_assertions"] = norm_verifiers
        existing_deferred = normalized.get("verifier_assertions_deferred")
        if isinstance(existing_deferred, list):
            for item in existing_deferred:
                if isinstance(item, dict):
                    deferred.append(item)
        normalized["verifier_assertions_deferred"] = deferred

        fallback_assertions = []
        if not normalized["generator_assertions"]:
            fallback_assertions = self._fallback_generator_assertions(bundle)
            if fallback_assertions:
                normalized["generator_assertions"] = fallback_assertions
                warnings.append("generator_assertions empty after normalization; fallback assertions applied")

        if not normalized["generator_assertions"] and self._bundle_is_unknown(bundle) and self._guard_missing_is_blocking(bundle):
            warnings.append("guard spec generator_assertions empty for unknown CWE under closed policy")
            return None

        prior_norm = normalized.get("normalization")
        if not isinstance(prior_norm, dict):
            prior_norm = {}
        prior_mapped = prior_norm.get("mapped_ops")
        prior_dropped = prior_norm.get("dropped_ops")
        prior_warnings = prior_norm.get("warnings")
        prior_schema_mismatches = prior_norm.get("schema_mismatches")
        all_mapped = list(prior_mapped) if isinstance(prior_mapped, list) else []
        all_dropped = list(prior_dropped) if isinstance(prior_dropped, list) else []
        all_warnings = list(prior_warnings) if isinstance(prior_warnings, list) else []
        all_schema_mismatches = (
            list(prior_schema_mismatches) if isinstance(prior_schema_mismatches, list) else []
        )
        all_mapped.extend(mapped_ops)
        all_dropped.extend(dropped_ops)
        all_warnings.extend(warnings)
        all_schema_mismatches.extend(schema_mismatches)
        normalized["normalization"] = {
            "mapped_ops": all_mapped,
            "dropped_ops": all_dropped,
            "warnings": [item for item in all_warnings if isinstance(item, str) and item.strip()],
            "schema_mismatches": [
                item for item in all_schema_mismatches if isinstance(item, str) and item.strip()
            ],
        }
        return normalized

    def _normalize_assertions_for_scope(
        self,
        *,
        assertions: List[Dict[str, Any]],
        scope: str,
        unsupported_policy: str,
        mapped_ops: List[Dict[str, Any]],
        dropped_ops: List[Dict[str, Any]],
        warnings: List[str],
        deferred: List[Dict[str, Any]],
        schema_mismatches: List[str],
    ) -> List[Dict[str, Any]] | None:
        normalized: List[Dict[str, Any]] = []
        for raw_assertion in assertions:
            if not isinstance(raw_assertion, dict):
                continue
            assertion = dict(raw_assertion)
            original_op = str(assertion.get("op") or "").strip().lower()
            if not original_op:
                continue
            mapped_op = self._normalize_op(original_op, scope=scope)
            if mapped_op != original_op:
                mapped_ops.append({"from": original_op, "to": mapped_op, "scope": scope})
            assertion["op"] = mapped_op
            param_mismatches = self._normalize_assertion_params(assertion, mapped_op)
            schema_mismatches.extend(param_mismatches)
            warnings.extend(self._normalize_assertion_metadata(assertion, op=mapped_op, scope=scope))

            if scope == "generator":
                supported = mapped_op in SUPPORTED_GENERATOR_ASSERTION_OPS
            else:
                supported = mapped_op in SUPPORTED_VERIFIER_ASSERTION_OPS

            if supported:
                normalized.append(assertion)
                continue

            if scope == "verifier" and self._is_deferable_verifier_assertion(assertion):
                deferred.append(assertion)
                dropped_ops.append({"op": mapped_op, "scope": scope, "reason": "deferred_for_verifier_executor"})
                continue

            if unsupported_policy == "fail":
                warnings.append(f"unsupported guard assertion op in {scope}: {mapped_op}")
                return None

            dropped_ops.append({"op": mapped_op, "scope": scope, "reason": "unsupported_op"})
        return normalized

    @staticmethod
    def _normalize_op(op: str, *, scope: str) -> str:
        if scope == "generator":
            return GENERATOR_OP_ALIASES.get(op, op)
        return VERIFIER_OP_ALIASES.get(op, op)

    @staticmethod
    def _normalize_assertion_params(assertion: Dict[str, Any], op: str) -> List[str]:
        mismatches: List[str] = []
        if not isinstance(assertion, dict):
            return mismatches

        def _map_key(target: str, aliases: List[str]) -> None:
            if assertion.get(target) is not None:
                return
            for key in aliases:
                value = assertion.get(key)
                if value is None:
                    continue
                assertion[target] = value
                mismatches.append(f"{op}.{target} missing, found {key}")
                return

        if op == "dep_declared":
            _map_key("dep", ["name", "package"])
        elif op == "any_dep_declared":
            _map_key("deps", ["names", "packages"])
        elif op in {"file_contains", "file_not_contains"}:
            _map_key("string", ["contains", "needle"])
        elif op in {"file_regex_contains", "file_regex_not_contains", "file_regex_any"}:
            _map_key("regex", ["pattern"])
            if op == "file_regex_any":
                _map_key("globs", ["paths", "glob"])
        return mismatches

    @staticmethod
    def _normalize_assertion_metadata(assertion: Dict[str, Any], *, op: str, scope: str) -> List[str]:
        warnings: List[str] = []
        if not isinstance(assertion, dict):
            return warnings
        severity = str(assertion.get("severity") or "block").strip().lower()
        if severity not in {"block", "warn"}:
            severity = "block"
        intent = str(assertion.get("intent") or "").strip().lower()
        if not intent:
            if op in {"dep_declared", "any_dep_declared"}:
                intent = "dependency"
            elif op in {"manifest_field_equals", "manifest_field_contains"}:
                intent = "contract"
            elif "regex" in op:
                intent = "syntax_hint"
            else:
                intent = "semantic_anchor"
        if intent not in {"semantic_anchor", "syntax_hint", "contract", "dependency"}:
            intent = "semantic_anchor"
        stability = str(assertion.get("stability") or "medium").strip().lower()
        if stability not in {"high", "medium", "low"}:
            stability = "medium"
        evidence_ids_raw = assertion.get("evidence_ids")
        evidence_ids: List[int] = []
        if isinstance(evidence_ids_raw, list):
            for item in evidence_ids_raw:
                try:
                    evidence_ids.append(int(item))
                except Exception:
                    continue
        assertion["severity"] = severity
        assertion["intent"] = intent
        assertion["stability"] = stability
        assertion["evidence_ids"] = evidence_ids

        if scope == "generator" and op in {"file_regex_contains", "file_regex_not_contains", "file_regex_any"}:
            pattern = str(assertion.get("regex") or assertion.get("pattern") or "")
            alternations = pattern.count("|")
            if len(pattern) > 220 or alternations >= 8:
                assertion["intent"] = "syntax_hint"
                assertion["stability"] = "low"
                if assertion.get("severity") != "warn":
                    assertion["severity"] = "warn"
                warnings.append(
                    f"brittle regex assertion downgraded ({op}) due to complexity/length; treated as syntax_hint warn"
                )
        return warnings

    @staticmethod
    def _trim_generator_assertions(assertions: List[Dict[str, Any]], *, warnings: List[str]) -> List[Dict[str, Any]]:
        if not isinstance(assertions, list):
            return []
        max_assertions = 10
        if len(assertions) <= max_assertions:
            return assertions

        def _priority(item: Dict[str, Any]) -> tuple[int, int]:
            severity = str(item.get("severity") or "block").strip().lower()
            intent = str(item.get("intent") or "semantic_anchor").strip().lower()
            severity_rank = 0 if severity == "block" else 1
            intent_rank = {
                "contract": 0,
                "dependency": 1,
                "semantic_anchor": 2,
                "syntax_hint": 3,
            }.get(intent, 4)
            return (severity_rank, intent_rank)

        sorted_assertions = sorted(assertions, key=_priority)
        trimmed = sorted_assertions[:max_assertions]
        dropped = len(assertions) - len(trimmed)
        if dropped > 0:
            warnings.append(f"trimmed {dropped} low-priority guard assertions to reduce over-constrained specs")
        return trimmed

    @staticmethod
    def _is_deferable_verifier_assertion(assertion: Dict[str, Any]) -> bool:
        op = str(assertion.get("op") or "").strip().lower()
        if op.startswith("http_") or op.startswith("python_"):
            return True
        for key in ("url", "method", "script", "command", "python"):
            if key in assertion:
                return True
        return False

    def _fallback_generator_assertions(self, bundle: VulnBundle | None) -> List[Dict[str, Any]]:
        vuln_id = bundle.vuln_id if bundle else str(self.requirement.get("vuln_id") or "UNKNOWN")
        rule = load_rule(vuln_id)
        success_signature = str(rule.get("success_signature") or "Exploit SUCCESS").strip() or "Exploit SUCCESS"
        assertions: List[Dict[str, Any]] = [
            {"op": "role_exists", "role": "service_main"},
            {"op": "role_exists", "role": "poc_entry"},
            {"op": "manifest_field_contains", "field": "poc.success_signature", "string": success_signature},
        ]
        return assertions

    def _build_and_write_guard_spec(
        self,
        *,
        report: Dict[str, Any],
        evidence: List[Dict[str, Any]],
        bundle: VulnBundle | None,
    ) -> tuple[Path | None, Path | None]:
        guard_payload, ensemble_payload = self._generate_guard_spec_payload(report, evidence, bundle)
        if not guard_payload:
            if self._guard_missing_is_blocking(bundle):
                vuln = bundle.vuln_id if bundle else str(self.requirement.get("vuln_id") or "UNKNOWN")
                raise RuntimeError(
                    f"GuardSpec generation failed for {vuln} and policy.guard.failure_policy requires closed failure."
                )
            return None, None

        spec_path = write_guard_spec(self.metadata_dir, guard_payload)
        ensemble_path: Path | None = None
        if ensemble_payload:
            ensemble_path = write_guard_spec_ensemble(self.metadata_dir, ensemble_payload)
        self._last_guard_spec = guard_payload
        LOGGER.info("Guard spec saved to %s", spec_path)
        return spec_path, ensemble_path

    def _generate_guard_spec_payload(
        self,
        report: Dict[str, Any],
        evidence: List[Dict[str, Any]],
        bundle: VulnBundle | None,
    ) -> tuple[Dict[str, Any] | None, Dict[str, Any] | None]:
        policy_snapshot = self._guard_policy()
        evidence_refs = self._evidence_refs(evidence)
        if bool(report.get("guard_fallback")):
            fallback = self._fallback_guard_spec(
                report=report,
                evidence_refs=evidence_refs,
                policy_snapshot=policy_snapshot,
                bundle=bundle,
            )
            return fallback, None
        budget_mode = self._guard_budget_mode()
        run_count = 1
        if budget_mode == "bundle_ensemble":
            run_count = self._guard_ensemble_runs()

        raw_candidates: List[Dict[str, Any]] = []
        for _ in range(run_count):
            prompt = build_guard_planner_prompt(
                self.requirement,
                researcher_report=report,
                evidence=evidence,
                policy_guard=policy_snapshot,
                sid=self.sid,
                slug=bundle.slug if bundle else "",
            )
            raw = self.llm.generate(prompt)
            candidate = self._parse_guard_spec_candidate(
                raw=raw,
                report=report,
                evidence_refs=evidence_refs,
                policy_snapshot=policy_snapshot,
                bundle=bundle,
            )
            if candidate:
                raw_candidates.append(candidate)

        if not raw_candidates:
            fallback = self._fallback_guard_spec(
                report=report,
                evidence_refs=evidence_refs,
                policy_snapshot=policy_snapshot,
                bundle=bundle,
            )
            if fallback:
                raw_candidates.append(fallback)

        if not raw_candidates:
            return None, None

        if budget_mode == "bundle_ensemble" and len(raw_candidates) > 1:
            merged = self._merge_guard_specs(
                raw_candidates,
                report=report,
                evidence_refs=evidence_refs,
                policy_snapshot=policy_snapshot,
                bundle=bundle,
            )
            ensemble_payload = {
                "sid": self.sid,
                "vuln_id": bundle.vuln_id if bundle else self.requirement.get("vuln_id"),
                "slug": bundle.slug if bundle else "",
                "mode": "bundle_ensemble",
                "runs": len(raw_candidates),
                "candidates": raw_candidates,
            }
            return merged, ensemble_payload
        return raw_candidates[0], None

    def _parse_guard_spec_candidate(
        self,
        *,
        raw: str,
        report: Dict[str, Any],
        evidence_refs: List[Dict[str, Any]],
        policy_snapshot: Dict[str, Any],
        bundle: VulnBundle | None,
    ) -> Dict[str, Any] | None:
        payload = self._parse_json_object(raw)
        if not isinstance(payload, dict):
            return None
        payload.setdefault("schema_version", "guard_spec@1.0")
        payload["sid"] = self.sid
        payload["vuln_id"] = bundle.vuln_id if bundle else self.requirement.get("vuln_id")
        payload["slug"] = bundle.slug if bundle else payload.get("slug") or ""
        payload["source"] = payload.get("source") or "llm"
        payload["policy_snapshot"] = policy_snapshot
        payload["evidence_refs"] = evidence_refs
        payload["semantic_signature"] = payload.get("semantic_signature") or report.get("semantic_signature") or {}
        if not isinstance(payload.get("generator_assertions"), list):
            payload["generator_assertions"] = []
        if not isinstance(payload.get("verifier_assertions"), list):
            payload["verifier_assertions"] = []
        if not isinstance(payload.get("autofix_hints"), list):
            payload["autofix_hints"] = []
        payload.setdefault("confidence", "medium")
        unsupported_policy = self._unsupported_op_policy(policy_snapshot)
        normalized_payload = self._normalize_guard_payload_ops(
            payload,
            unsupported_policy=unsupported_policy,
            bundle=bundle,
            report=report,
        )
        if normalized_payload is None:
            LOGGER.warning(
                "Discarding guard spec candidate for %s due to unsupported op policy=%s",
                payload.get("vuln_id"),
                unsupported_policy,
            )
            return None
        try:
            spec = parse_guard_spec(normalized_payload)
            return spec.to_dict()
        except Exception as exc:
            LOGGER.warning("Discarding invalid guard spec candidate for %s: %s", payload.get("vuln_id"), exc)
            return None

    def _fallback_guard_spec(
        self,
        *,
        report: Dict[str, Any],
        evidence_refs: List[Dict[str, Any]],
        policy_snapshot: Dict[str, Any],
        bundle: VulnBundle | None,
    ) -> Dict[str, Any]:
        verification_spec = report.get("verification_spec") if isinstance(report, dict) else {}
        if not isinstance(verification_spec, dict):
            verification_spec = {}
        vuln_id = bundle.vuln_id if bundle else self.requirement.get("vuln_id")
        rule = load_rule(vuln_id)
        has_static = bool(load_static_rule(vuln_id))
        allow_override = self._allow_runtime_rule_override_static()
        wants_override = bool(verification_spec.get("override_static"))
        can_override_static = has_static and allow_override and wants_override
        markers = verification_spec.get("success_text_markers") or []
        if isinstance(markers, str):
            markers = [markers]
        success_marker = str(rule.get("success_signature") or "Exploit SUCCESS").strip() or "Exploit SUCCESS"
        if isinstance(markers, list) and (not has_static or can_override_static):
            for marker in markers:
                if isinstance(marker, str) and marker.strip():
                    success_marker = marker.strip()
                    break
        flag_token = verification_spec.get("flag_token")
        if not isinstance(flag_token, str) or (has_static and not can_override_static):
            flag_token = str(rule.get("flag_token") or "")
        generator_assertions: List[Dict[str, Any]] = [
            {"op": "role_exists", "role": "service_main"},
            {"op": "role_exists", "role": "poc_entry"},
            {"op": "manifest_field_contains", "field": "poc.success_signature", "string": success_marker},
        ]
        verifier_assertions: List[Dict[str, Any]] = [{"op": "contains", "string": success_marker}]
        if flag_token:
            verifier_assertions.append({"op": "contains", "string": flag_token})
        autofix_hints = [
            {
                "priority": 10,
                "instruction": "Ensure PoC prints success_signature exactly and exits with code 0.",
                "kind": "poc_contract",
            },
            {
                "priority": 20,
                "instruction": "Align service flow with semantic_signature input/sink/preconditions.",
                "kind": "semantics",
            },
        ]
        spec = build_guard_spec(
            sid=self.sid,
            vuln_id=bundle.vuln_id if bundle else str(self.requirement.get("vuln_id") or "UNKNOWN"),
            slug=bundle.slug if bundle else "",
            policy_snapshot=policy_snapshot,
            evidence_refs=evidence_refs,
            semantic_signature=report.get("semantic_signature") or self._default_semantic_signature(bundle),
            generator_assertions=generator_assertions,
            verifier_assertions=verifier_assertions,
            autofix_hints=autofix_hints,
            confidence="medium",
            source="llm",
        )
        return spec.to_dict()

    def _merge_guard_specs(
        self,
        candidates: List[Dict[str, Any]],
        *,
        report: Dict[str, Any],
        evidence_refs: List[Dict[str, Any]],
        policy_snapshot: Dict[str, Any],
        bundle: VulnBundle | None,
    ) -> Dict[str, Any]:
        best = sorted(candidates, key=self._guard_candidate_rank, reverse=True)[0]
        generator_assertions = self._intersect_object_lists(candidates, "generator_assertions")
        verifier_assertions = self._intersect_object_lists(candidates, "verifier_assertions")
        merged_signature = self._merge_semantic_signatures(candidates, report.get("semantic_signature") or {})
        hints = self._merge_autofix_hints(candidates)
        if not generator_assertions:
            generator_assertions = list(best.get("generator_assertions") or [])
        if not verifier_assertions:
            verifier_assertions = list(best.get("verifier_assertions") or [])
        spec = build_guard_spec(
            sid=self.sid,
            vuln_id=bundle.vuln_id if bundle else str(self.requirement.get("vuln_id") or "UNKNOWN"),
            slug=bundle.slug if bundle else "",
            policy_snapshot=policy_snapshot,
            evidence_refs=evidence_refs,
            semantic_signature=merged_signature,
            generator_assertions=generator_assertions,
            verifier_assertions=verifier_assertions,
            autofix_hints=hints,
            confidence=str(best.get("confidence") or "medium"),
            source="llm",
        )
        return spec.to_dict()

    @staticmethod
    def _guard_candidate_rank(candidate: Dict[str, Any]) -> tuple[int, int]:
        confidence = str(candidate.get("confidence") or "medium").strip().lower()
        rank_map = {"high": 3, "medium": 2, "low": 1}
        assertions = candidate.get("generator_assertions") or []
        return rank_map.get(confidence, 0), len(assertions) if isinstance(assertions, list) else 0

    @staticmethod
    def _intersect_object_lists(candidates: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
        normalized_sets: List[set[str]] = []
        value_map: Dict[str, Dict[str, Any]] = {}
        for candidate in candidates:
            entries = candidate.get(key) or []
            local: set[str] = set()
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                encoded = json.dumps(entry, sort_keys=True, ensure_ascii=False)
                local.add(encoded)
                value_map[encoded] = entry
            if local:
                normalized_sets.append(local)
        if not normalized_sets:
            return []
        shared = set.intersection(*normalized_sets)
        return [value_map[item] for item in sorted(shared)]

    @staticmethod
    def _merge_semantic_signatures(
        candidates: List[Dict[str, Any]],
        fallback: Dict[str, Any],
    ) -> Dict[str, List[str]]:
        buckets = ("input_vector", "sink", "exploit_precondition")
        merged: Dict[str, List[str]] = {bucket: [] for bucket in buckets}
        for bucket in buckets:
            candidate_sets: List[set[str]] = []
            for candidate in candidates:
                signature = candidate.get("semantic_signature") or {}
                values = signature.get(bucket) if isinstance(signature, dict) else []
                if isinstance(values, str):
                    values = [values]
                if not isinstance(values, list):
                    continue
                normalized = {str(value).strip() for value in values if isinstance(value, str) and str(value).strip()}
                if normalized:
                    candidate_sets.append(normalized)
            if candidate_sets:
                intersection = set.intersection(*candidate_sets)
                if intersection:
                    merged[bucket] = sorted(intersection)
                    continue
                merged[bucket] = sorted(candidate_sets[0])
                continue
            fb_values = fallback.get(bucket) if isinstance(fallback, dict) else []
            if isinstance(fb_values, str):
                fb_values = [fb_values]
            if isinstance(fb_values, list):
                merged[bucket] = [
                    str(value).strip()
                    for value in fb_values
                    if isinstance(value, str) and str(value).strip()
                ]
        return merged

    @staticmethod
    def _merge_autofix_hints(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        merged: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for candidate in candidates:
            hints = candidate.get("autofix_hints") or []
            if not isinstance(hints, list):
                continue
            for hint in hints:
                if not isinstance(hint, dict):
                    continue
                instruction = str(hint.get("instruction") or "").strip()
                if not instruction or instruction in seen:
                    continue
                seen.add(instruction)
                merged.append(hint)
        return merged

    @staticmethod
    def _parse_json_object(raw: str) -> Dict[str, Any] | None:
        text = (raw or "").strip()
        if not text:
            return None
        if text.startswith("```"):
            segments = [segment.strip() for segment in text.split("```") if segment.strip()]
            if segments:
                candidate = segments[0]
                if candidate.lower().startswith("json"):
                    candidate = candidate[4:].strip()
                text = candidate
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _evidence_refs(evidence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        refs: List[Dict[str, Any]] = []
        for index, item in enumerate(evidence):
            if not isinstance(item, dict):
                continue
            ref: Dict[str, Any] = {"index": index}
            for key in ("query", "source", "url", "published", "retrieved_at", "snippet"):
                value = item.get(key)
                if value in (None, "", []):
                    continue
                ref[key] = value
            refs.append(ref)
        return refs

    def _evaluate_evidence_quality(
        self,
        bundle: VulnBundle | None,
        search_hits: List[SearchResult],
    ) -> Tuple[str, str]:
        search_policy = self._search_policy()
        require_evidence = self._require_researcher_evidence(bundle)
        unknown = self._bundle_is_unknown(bundle)
        remote_hits = [hit for hit in search_hits if str(hit.source).strip().lower() == "remote"]
        if search_policy == "remote_required" and not remote_hits:
            vuln = bundle.vuln_id if bundle else str(self.requirement.get("vuln_id") or "UNKNOWN")
            return (
                "insufficient",
                (
                    f"Insufficient researcher evidence for {vuln}: search_policy=remote_required requires at least "
                    "one remote hit, but none were found. Configure VUL_WEB_SEARCH_ENDPOINT or relax "
                    "researcher.search_policy."
                ),
            )
        if require_evidence and unknown and not remote_hits:
            vuln = bundle.vuln_id if bundle else str(self.requirement.get("vuln_id") or "UNKNOWN")
            return (
                "insufficient",
                (
                    f"Insufficient researcher evidence for unknown CWE {vuln}: remote provenance is required, "
                    "but only local/no evidence was collected. Configure VUL_WEB_SEARCH_ENDPOINT or set "
                    "policy.require_researcher_evidence=false explicitly."
                ),
            )
        if require_evidence and not search_hits:
            vuln = bundle.vuln_id if bundle else str(self.requirement.get("vuln_id") or "UNKNOWN")
            return (
                "insufficient",
                f"Insufficient researcher evidence for {vuln}: no search evidence was collected.",
            )
        relevance_score = self._estimate_evidence_relevance(bundle, search_hits)
        if relevance_score < 0.35:
            vuln = bundle.vuln_id if bundle else str(self.requirement.get("vuln_id") or "UNKNOWN")
            if unknown and require_evidence:
                return (
                    "insufficient",
                    (
                        f"Insufficient researcher evidence for {vuln}: low relevance score ({relevance_score:.2f}). "
                        "Evidence does not align with requested vulnerability semantics."
                    ),
                )
            if not unknown:
                return (
                    "sufficient",
                    (
                        f"Low evidence relevance for {vuln} ({relevance_score:.2f}); using guard fallback mode "
                        "with static/minimal assertions."
                    ),
                )
        return "sufficient", ""

    def _estimate_evidence_relevance(
        self,
        bundle: VulnBundle | None,
        search_hits: List[SearchResult],
    ) -> float:
        if not search_hits:
            return 0.0
        terms = self._relevance_terms(bundle)
        if not terms:
            return 1.0
        matches = 0
        remote_hits = 0
        for hit in search_hits:
            text = " ".join(
                [
                    str(hit.query or ""),
                    str(hit.snippet or ""),
                    str(hit.url or ""),
                ]
            ).lower()
            if any(term in text for term in terms):
                matches += 1
            if str(hit.source or "").strip().lower() == "remote":
                remote_hits += 1
        base = matches / max(1, len(search_hits))
        diversity_bonus = 0.1 if remote_hits and (len(search_hits) - remote_hits) > 0 else 0.0
        remote_bonus = 0.1 if remote_hits else 0.0
        return min(1.0, base + diversity_bonus + remote_bonus)

    def _relevance_terms(self, bundle: VulnBundle | None) -> List[str]:
        vuln_id = str(bundle.vuln_id if bundle else self.requirement.get("vuln_id") or "").strip().lower()
        if vuln_id in {"cwe-89", "cwe_89"}:
            return [
                "sql injection",
                "sqli",
                "sql query",
                "union select",
                "cursor.execute",
            ]
        if vuln_id in {"cwe-352", "cwe_352"}:
            return [
                "csrf",
                "cross-site request forgery",
                "anti-csrf",
                "csrf token",
                "same-site",
            ]
        tokens = [token for token in vuln_id.replace("_", "-").split("-") if token]
        if len(tokens) >= 2 and tokens[0] == "cwe":
            return [f"cwe-{tokens[1]}", f"cwe {tokens[1]}"]
        return tokens

    def _build_evidence_payload(self, search_hits: List[SearchResult]) -> List[Dict[str, Any]]:
        payload: List[Dict[str, Any]] = []
        for hit in search_hits:
            item: Dict[str, Any] = {
                "query": hit.query or "",
                "source": hit.source,
                "url": hit.url,
                "snippet": hit.snippet,
                "retrieved_at": hit.retrieved_at or datetime.now(timezone.utc).isoformat(),
            }
            if hit.published:
                item["published"] = hit.published
            payload.append(item)
        return payload

    def _default_semantic_signature(self, bundle: VulnBundle | None) -> Dict[str, Any]:
        vuln_id = (bundle.vuln_id if bundle else self.requirement.get("vuln_id")) or "UNKNOWN"
        normalized = str(vuln_id).strip().lower().replace("_", "-")
        if not normalized.startswith("cwe-"):
            normalized = f"cwe-{normalized.split('-')[-1]}" if normalized else "cwe-unknown"
        if normalized == "cwe-352":
            return {
                "input_vector": ["cross-site request", "cookie-authenticated session"],
                "sink": ["state-changing endpoint (POST/PUT/DELETE/PATCH)"],
                "exploit_precondition": ["missing CSRF token validation"],
            }
        if normalized == "cwe-89":
            return {
                "input_vector": ["user-controlled request parameter"],
                "sink": ["SQL query execution"],
                "exploit_precondition": ["input concatenated/interpolated into SQL sink"],
            }
        return {
            "input_vector": [],
            "sink": [],
            "exploit_precondition": [],
        }

    def _synthesize_candidates(self) -> Dict[str, List[Dict[str, Any]]]:
        targets = [self.bundle] if self.bundle else load_vuln_bundles(self.plan)
        output = {"rules": [], "templates": []}
        allow_templates = self._allow_candidate_templates()
        for target in targets:
            if target is None:
                continue
            rule = self._generate_candidate_rule(target)
            if rule:
                rule_path = self._write_candidate_rule(target, rule)
                output["rules"].append(
                    {
                        "vuln_id": target.vuln_id,
                        "path": str(rule_path),
                        "success_signature": rule.get("success_signature"),
                        "flag_token": rule.get("flag_token"),
                    }
                )
            if allow_templates:
                template_path = self._generate_candidate_template(target)
                if template_path:
                    template_meta = self._load_template_metadata(template_path)
                    output["templates"].append(
                        {
                            "vuln_id": target.vuln_id,
                            "path": str(template_path),
                            "template_id": template_meta.get("id"),
                            "name": template_meta.get("name"),
                        }
                    )
                    LOGGER.info("Candidate template generated at %s", template_path)
        return output

    def _write_candidate_rule(self, bundle: VulnBundle, rule: Dict[str, Any]) -> Path:
        import yaml

        filename = f"{bundle.vuln_id.lower()}.yaml"
        path = self.runtime_rules_dir / filename
        path.write_text(yaml.safe_dump(rule, sort_keys=False, allow_unicode=True), encoding="utf-8")
        LOGGER.info("Candidate rule written to %s", path)
        return path

    def _write_candidate_template(self, bundle: VulnBundle, base_template_dir: Path) -> Path | None:
        import shutil

        repo_root = get_repo_root()
        source = repo_root / base_template_dir
        if not source.exists():
            return None
        dest = self.runtime_templates_dir / f"{bundle.vuln_id.lower()}-{source.name}"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(source, dest)
        template_json = dest / "template.json"
        if template_json.exists():
            data = json.loads(template_json.read_text(encoding="utf-8"))
        else:
            data = {"id": dest.name}
        data["id"] = f"{bundle.vuln_id.lower()}-candidate"
        data["name"] = f"{bundle.vuln_id} candidate template"
        template_json.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return dest

    def _load_template_metadata(self, template_root: Path) -> Dict[str, Any]:
        template_json = template_root / "template.json"
        if not template_json.exists():
            return {}
        try:
            return json.loads(template_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _extract_verification_spec(self, bundle: VulnBundle) -> Dict[str, Any] | None:
        """Extract a verification_spec block for the given bundle, if present.

        The primary location is a top-level `verification_spec` field inside
        the most recent researcher_report.json. This keeps the schema simple
        while still allowing per-vuln overrides in future by switching to a
        mapping structure.
        """
        report = self._load_latest_report()
        if not isinstance(report, dict):
            return None
        spec = report.get("verification_spec")
        if isinstance(spec, dict):
            return spec
        # Optional extension: support per-vuln mapping under verification_specs.
        mapping = report.get("verification_specs")
        if isinstance(mapping, dict):
            key_candidates = [
                (bundle.vuln_id or "").upper(),
                (bundle.vuln_id or "").lower(),
            ]
            for key in key_candidates:
                value = mapping.get(key)
                if isinstance(value, dict):
                    return value
        return None

    def _rule_from_verification_spec(self, bundle: VulnBundle, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Construct a v2 rule mapping from a compact verification_spec."""

        vuln_id = bundle.vuln_id or "UNKNOWN"
        cwe = vuln_id.upper()

        success_mode = str(spec.get("success_mode") or "text")
        raw_markers = spec.get("success_text_markers") or []
        markers: List[str] = []
        if isinstance(raw_markers, list):
            for entry in raw_markers:
                if isinstance(entry, str) and entry:
                    markers.append(entry)
        elif isinstance(raw_markers, str) and raw_markers:
            markers.append(raw_markers)

        flag_token = spec.get("flag_token")
        flag_mode = str(spec.get("flag_mode") or "strict").lower()

        json_success_key = spec.get("json_success_key")
        json_success_value = spec.get("json_success_value")
        json_flag_key = spec.get("json_flag_key")

        assertion_program = spec.get("assertion_program") or []
        if isinstance(assertion_program, str):
            # Lightweight compatibility: accept a single "assert ..." string and
            # try to turn it into a contains() operation so runtime verifiers
            # can leverage it.
            import re

            matches = re.findall(r"['\"]([^'\"]+)['\"]", assertion_program)
            assertion_program = [{"op": "contains", "string": matches[0]}] if matches else []
        elif not isinstance(assertion_program, list):
            assertion_program = []

        runtime: Dict[str, Any] = {
            "success_mode": success_mode,
            "success_text_markers": markers,
            "flag_token": flag_token,
            "assertion_program": assertion_program,
        }
        if json_success_key:
            runtime["json_success_key"] = json_success_key
            runtime["json_success_value"] = json_success_value
        if json_flag_key:
            runtime["json_flag_key"] = json_flag_key

        output: Dict[str, Any] = {
            "mode": "json" if success_mode == "json" else "auto",
        }
        json_cfg: Dict[str, Any] = {}
        if json_success_key:
            json_cfg["success_key"] = json_success_key
            if "json_success_value" in spec:
                json_cfg["success_value"] = json_success_value
        if json_flag_key:
            json_cfg["flag_key"] = json_flag_key
        if json_cfg:
            output["json"] = json_cfg

        rule: Dict[str, Any] = {
            "cwe": cwe,
            "version": 2,
            "scenario_type": "web-poc",
            "verification": {
                "source": "runtime",
                "require_flag": bool(flag_token) and flag_mode != "none",
                "flag_mode": flag_mode,
                "exit_code": "zero",
            },
            "output": output,
            "llm": {
                "assist_default": True,
                "assertion_budget": 8,
            },
            "runtime": runtime,
        }
        # Guard rails should not hardcode template-specific endpoints. Instead,
        # enforce that the PoC carries the success marker so synthesis-mode
        # bundles remain template-agnostic.
        if markers:
            rule["patterns"] = [
                {
                    "type": "poc_contains",
                    "path": "{{poc_entry}}",
                    "contains": markers[0],
                }
            ]
        # Legacy compatibility fields: used by generator augmentation and
        # rule_based fallback logic when runtime assertions are absent/disabled.
        if markers:
            rule["success_signature"] = markers[0]
        if isinstance(flag_token, str) and flag_token:
            rule["flag_token"] = flag_token
        rule["strict_flag"] = flag_mode == "strict"
        return rule

    def _generate_candidate_rule(self, bundle: VulnBundle) -> Dict[str, Any] | None:
        static_rule = load_static_rule(bundle.vuln_id) or {}
        has_static = bool(static_rule)
        allow_full_override = self._allow_runtime_rule_override_static()

        spec = self._extract_verification_spec(bundle)
        wants_override = bool(isinstance(spec, dict) and spec.get("override_static"))
        if has_static and isinstance(spec, dict):
            if not wants_override:
                # Keep static contracts stable unless the report explicitly requests override.
                spec = None
            elif not allow_full_override:
                LOGGER.warning(
                    "Ignoring verification_spec.override_static for %s because policy "
                    "allow_runtime_rule_override_static is disabled.",
                    bundle.vuln_id,
                )
                spec = None

        candidate_rule: Dict[str, Any] | None = None
        if spec:
            try:
                candidate_rule = self._rule_from_verification_spec(bundle, spec)
            except Exception as exc:  # pragma: no cover - defensive
                LOGGER.warning("Failed to build rule from verification_spec for %s: %s", bundle.vuln_id, exc)

        if candidate_rule is None:
            raw_rule = static_rule if has_static else (load_rule(bundle.vuln_id) or {})
            success_signature = str(raw_rule.get("success_signature") or "Exploit SUCCESS").strip() or "Exploit SUCCESS"
            flag_token = str(raw_rule.get("flag_token") or "").strip()
            strict_flag = bool(raw_rule.get("strict_flag", True)) if flag_token else False
            output_cfg = raw_rule.get("output") or {}
            json_cfg = output_cfg.get("json") if isinstance(output_cfg, dict) else None
            if not isinstance(json_cfg, dict):
                json_cfg = {}
            spec = {
                "success_mode": "text",
                "success_text_markers": [success_signature],
                "flag_mode": "strict" if strict_flag else ("loose" if flag_token else "none"),
                "json_success_key": output_cfg.get("json_success_key") if isinstance(output_cfg, dict) else None,
                "json_success_value": output_cfg.get("json_success_value") if isinstance(output_cfg, dict) else None,
                "json_flag_key": output_cfg.get("json_flag_key") if isinstance(output_cfg, dict) else None,
                "assertion_program": [
                    {"op": "contains", "string": success_signature},
                ],
            }
            if flag_token:
                spec["flag_token"] = flag_token
                spec["assertion_program"].append({"op": "contains", "string": flag_token})
            if json_cfg:
                spec.setdefault("json_success_key", json_cfg.get("success_key"))
                spec.setdefault("json_success_value", json_cfg.get("success_value"))
                spec.setdefault("json_flag_key", json_cfg.get("flag_key"))
            candidate_rule = self._rule_from_verification_spec(bundle, spec)

        if candidate_rule is None:
            return None
        candidate_rule["origin"] = "runtime"
        if has_static and wants_override and allow_full_override:
            candidate_rule["override_scope"] = "full"
        elif has_static:
            candidate_rule["override_scope"] = "assertions_only"
        else:
            candidate_rule["override_scope"] = "none"
        return candidate_rule

    def _generate_candidate_template(self, bundle: VulnBundle) -> Path | None:
        vuln_id = (bundle.vuln_id or "").strip().lower()
        if not vuln_id:
            return None
        if vuln_id.startswith("cwe_"):
            vuln_id = vuln_id.replace("_", "-", 1)
        if not vuln_id.startswith("cwe-") and "cwe" in vuln_id:
            vuln_id = vuln_id.replace("cwe", "cwe-", 1)

        repo_root = get_repo_root()
        template_root = repo_root / "workspaces" / "templates"
        if not template_root.exists():
            return None

        best: tuple[float, Path] | None = None
        for meta_path in template_root.rglob("template.json"):
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if not isinstance(meta, dict):
                continue
            tags = meta.get("tags") or []
            if not isinstance(tags, list):
                continue
            normalized_tags = [str(tag).strip().lower() for tag in tags if isinstance(tag, str) and tag.strip()]
            if vuln_id not in normalized_tags:
                continue
            try:
                score = float(meta.get("stability_score", 0.0))
            except Exception:
                score = 0.0
            if best is None or score > best[0]:
                best = (score, meta_path.parent)

        if not best:
            return None
        return self._write_candidate_template(bundle, best[1])


__all__ = ["ResearcherService"]
