"""Researcher microservice orchestrating ReAct-style retrieval."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from common.contracts import (
    build_generator_contract,
    can_resolve_without_remote_research_for_requirement,
    write_generator_contract,
)
from common.deps.stdlib import load_stdlib_spec
from common.guardrails import (
    GENERATOR_OP_ALIASES,
    SUPPORTED_GENERATOR_ASSERTION_OPS,
    SUPPORTED_VERIFIER_ASSERTION_OPS,
    VERIFIER_OP_ALIASES,
    VALID_UNSUPPORTED_OP_POLICIES,
    build_guard_spec,
    default_guard_policy_snapshot,
    enforce_generator_assertion_trust_boundary,
    normalize_semantic_signature,
    parse_guard_spec,
    write_guard_spec,
    write_guard_spec_ensemble,
)
from common.llm import LLMClient, llm_execution_summary
from common.logging import get_logger
from common.name_only import build_name_only_contract, is_name_driven_requirement
from common.paths import ensure_dir, get_repo_root
from common.plan import load_plan
from common.prompts import build_guard_planner_prompt, build_researcher_prompt, prompt_contract
from common.researcher_report import extract_verification_spec, normalize_researcher_report_payload
from common.roles import normalize_role
from common.runtime_assets import record_generated_runtime_asset
from common.rules import load_rule, load_static_rule, rule_filename_for_vuln_id
from common.run_matrix import (
    VulnBundle,
    bundle_requirement,
    load_vuln_bundles,
    metadata_dir_for_bundle,
)
from common.variability import VariationManager
from common.vuln_semantics import (
    baseline_semantic_signature,
    family_canonical_tags,
    normalize_vuln_id,
    semantic_term_aliases,
)
from agents.generator.flask_fragment_registry import (
    fragment_guard_generator_assertions,
    fragment_semantic_signature,
    service_side_file_contains_tokens,
)
from agents.generator.template_metadata import normalize_template_metadata
from orchestrator.plugins import ReactLoop, ReactSpan
from rag.static_loader import load_static_context
from rag.tools import SearchExecution, SearchResult, SearchRequest, WebSearchTool

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
        self._search_records: List[Dict[str, Any]] = []
        self._search_cache_hit_count = 0
        self._search_cache_miss_count = 0
        self._search_planned_query_count = 0
        self._search_executed_query_count = 0
        self._search_early_stop_triggered = False
        self._search_health_path: Path | None = None
        self._search_degraded = False
        self._last_evidence_relevance: Dict[str, Any] | None = None
        self._query_plan: Dict[str, Any] = {}
        self._query_plan_index: Dict[str, Dict[str, Any]] = {}
        self._family_hypothesis_summary: Dict[str, Any] = {}
        self._llm_prompt_invocations: Dict[str, int] = {}
        self._guard_planner_budget_mode: str = "bundle_once"
        self._guard_planner_planned_runs: int = 0

    def run(self) -> Path:
        snapshot = self._snapshot_id()
        rag_context = load_static_context(snapshot)
        query_plan = self.react_loop.query_plan_from_requirement(
            self.requirement,
            limit=self._effective_query_plan_limit(),
        )
        queries = [str(entry.get("query") or "").strip() for entry in query_plan.get("queries") or [] if str(entry.get("query") or "").strip()]
        self._query_plan = query_plan
        self._query_plan_index = {
            str(entry.get("query") or "").strip(): entry
            for entry in query_plan.get("queries") or []
            if isinstance(entry, dict) and str(entry.get("query") or "").strip()
        }
        active_bundle = self.bundle
        with self.react_loop.span(queries=queries, query_plan=query_plan) as span:
            search_hits = self._collect_search_results(queries, span=span)
            search_meta = self._write_search_artifacts(search_hits, policy=self._search_policy())
            evidence = self._build_evidence_payload(search_hits)
            evidence_type_summary = self._summarize_evidence_types(search_hits)
            tech_stack_candidates = self._infer_tech_stack_candidates(search_hits, query_plan)
            family_hypothesis_summary = self.react_loop.rank_family_hypotheses(
                search_hits,
                base_hypotheses=list(query_plan.get("family_hypotheses") or []),
            )
            self._family_hypothesis_summary = family_hypothesis_summary
            evidence_graph = self._build_evidence_graph(
                search_hits=search_hits,
                query_plan=query_plan,
                tech_stack_candidates=tech_stack_candidates,
                family_hypothesis_summary=family_hypothesis_summary,
            )
            quality, quality_reason = self._evaluate_evidence_quality(active_bundle, search_hits)
            relevance_report = self._last_evidence_relevance or {
                "score": 0.0,
                "threshold": self._relevance_threshold(active_bundle),
                "profile": {},
                "hits": [],
            }
            guard_fallback = "guard fallback mode" in (quality_reason or "").lower()
            if quality == "insufficient":
                failure_reason = self._format_search_failure_reason(quality_reason)
                report = {
                    "sid": self.sid,
                    "vuln_id": active_bundle.vuln_id if active_bundle else self.requirement.get("vuln_id"),
                    "trace_id": self.react_loop.trace_id,
                    "retrieval_snapshot_id": snapshot,
                    "failure_context": self.react_loop.failure_context,
                    "search_policy": self._search_policy(),
                    "search_health_path": str(search_meta["health_path"]) if search_meta.get("health_path") else None,
                    "search_degraded": bool(search_meta.get("degraded")),
                    "evidence": evidence,
                    "query_plan": query_plan,
                    "evidence_type_summary": evidence_type_summary,
                    "tech_stack_candidates": tech_stack_candidates,
                    "family_hypothesis_summary": family_hypothesis_summary,
                    "evidence_graph": evidence_graph,
                    "semantic_signature": {},
                    "evidence_relevance": relevance_report,
                    "quality": "insufficient",
                    "quality_reason": quality_reason,
                    "guard_fallback": False,
                    "guard_spec_path": None,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "llm_execution": self._llm_execution_summary(),
                }
                report["semantic_signature"], report["semantic_signature_source"] = self._resolve_semantic_signature(
                    report,
                    active_bundle,
                )
                report = self._canonicalize_report_identity(report, active_bundle)
                contract_path = self._write_resolved_contract_seed(report, active_bundle)
                report["resolved_contract_path"] = str(contract_path)
                self._last_report = report
                path = self._write_report(report)
                span.event("research_insufficient", reason=failure_reason, path=str(path))
                raise RuntimeError(failure_reason)
            report = normalize_researcher_report_payload(self._generate_report(rag_context, search_hits))
            report = self._canonicalize_report_identity(report, active_bundle)
            report.setdefault("trace_id", self.react_loop.trace_id)
            report.setdefault("retrieval_snapshot_id", snapshot)
            report.setdefault("failure_context", self.react_loop.failure_context)
            report["search_policy"] = self._search_policy()
            report["search_health_path"] = (
                str(search_meta["health_path"]) if search_meta.get("health_path") else None
            )
            report["search_degraded"] = bool(search_meta.get("degraded"))
            report["evidence"] = evidence
            report["query_plan"] = query_plan
            report["evidence_type_summary"] = evidence_type_summary
            report["tech_stack_candidates"] = tech_stack_candidates
            report["family_hypothesis_summary"] = family_hypothesis_summary
            report["evidence_graph"] = evidence_graph
            report["evidence_relevance"] = relevance_report
            report["semantic_signature"], report["semantic_signature_source"] = self._resolve_semantic_signature(
                report,
                active_bundle,
            )
            report["quality"] = quality
            report["quality_reason"] = quality_reason or "sufficient evidence"
            report["guard_fallback"] = guard_fallback
            report["created_at"] = datetime.now(timezone.utc).isoformat()
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
            llm_execution = self._llm_execution_summary()
            if llm_execution:
                report["llm_execution"] = llm_execution
            self._last_report = report
            contract_path = self._write_resolved_contract_seed(report, active_bundle)
            report["resolved_contract_path"] = str(contract_path)
            path = self._write_report(report)
            span.event("report_written", path=str(path))
        self.react_loop.record_researcher_report(
            queries=queries,
            search_results=[hit.to_payload() for hit in search_hits],
            report_path=path,
            query_plan=query_plan,
        )
        LOGGER.info("Researcher report saved to %s", path)
        return path

    # Internal helpers -----------------------------------------------------

    def _canonical_report_vuln_id(self, bundle: VulnBundle | None) -> str:
        if bundle and isinstance(bundle.vuln_id, str) and bundle.vuln_id.strip():
            return bundle.vuln_id.strip()
        value = self.requirement.get("vuln_id")
        if isinstance(value, str) and value.strip():
            return value.strip()
        return "UNKNOWN"

    def _canonicalize_report_identity(
        self,
        report: Dict[str, Any],
        bundle: VulnBundle | None,
    ) -> Dict[str, Any]:
        if not isinstance(report, dict):
            return report
        report.setdefault("sid", self.sid)
        canonical_vuln_id = self._canonical_report_vuln_id(bundle)
        current_vuln_id = str(report.get("vuln_id") or "").strip()
        if canonical_vuln_id and (not current_vuln_id or current_vuln_id.upper() == "UNKNOWN"):
            report["vuln_id"] = canonical_vuln_id
        return report

    def _snapshot_id(self) -> str:
        requirement = self.plan["requirement"]
        return (
            requirement.get("rag_snapshot")
            or requirement.get("corpus_snapshot")
            or "mvp-sample"
        )

    def _search_cache_path(self) -> Path:
        repo_root = get_repo_root().resolve()
        metadata_root = Path(self.metadata_root).resolve()
        try:
            metadata_root.relative_to(repo_root)
        except ValueError:
            return ensure_dir(Path(self.metadata_root) / "_search_cache") / "search_cache.json"
        return ensure_dir(repo_root / "artifacts" / "_search_cache") / "search_cache.json"

    def _load_search_cache(self) -> Dict[str, Any]:
        path = self._search_cache_path()
        if not path.exists():
            return {"schema_version": "search_cache@0.1", "entries": {}}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"schema_version": "search_cache@0.1", "entries": {}}
        if not isinstance(payload, dict):
            return {"schema_version": "search_cache@0.1", "entries": {}}
        entries = payload.get("entries")
        if not isinstance(entries, dict):
            payload["entries"] = {}
        return payload

    def _write_search_cache(self, payload: Dict[str, Any]) -> None:
        self._search_cache_path().write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @staticmethod
    def _search_cache_key(request_payload: Dict[str, Any]) -> str:
        normalized = json.dumps(request_payload or {}, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def _search_results_from_payload(results_payload: Any) -> List[SearchResult]:
        if not isinstance(results_payload, list):
            return []
        results: List[SearchResult] = []
        for entry in results_payload:
            if not isinstance(entry, dict):
                continue
            title = str(entry.get("title") or "").strip()
            url = str(entry.get("url") or "").strip()
            snippet = str(entry.get("snippet") or "").strip()
            if not (title and url):
                continue
            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source=str(entry.get("source") or "local").strip() or "local",
                    published=str(entry.get("published") or "").strip() or None,
                    query=str(entry.get("query") or "").strip() or None,
                    retrieved_at=str(entry.get("retrieved_at") or "").strip() or None,
                    provider=str(entry.get("provider") or "").strip() or None,
                    score=float(entry.get("score")) if isinstance(entry.get("score"), (int, float)) else None,
                    raw_content=str(entry.get("raw_content") or "").strip() or None,
                    request_id=str(entry.get("request_id") or "").strip() or None,
                )
            )
        return results

    def _should_early_stop_search(
        self,
        *,
        retained_hits: List[SearchResult],
        new_url_count: int,
    ) -> bool:
        if self._search_executed_query_count < 2:
            return False
        if new_url_count != 0:
            return False
        if len(retained_hits) < self.search_limit:
            return False
        return any(
            self._source_authority_for_hit(hit, evidence_type=self._classify_evidence_type(hit)) == "high"
            for hit in retained_hits
        )

    def _collect_search_results(self, queries: Iterable[str], span: ReactSpan) -> List[SearchResult]:
        hits: List[SearchResult] = []
        seen_urls: set[str] = set()
        self._search_records = []
        self._search_cache_hit_count = 0
        self._search_cache_miss_count = 0
        self._search_executed_query_count = 0
        self._search_early_stop_triggered = False
        query_list = [str(query).strip() for query in queries if str(query).strip()]
        self._search_planned_query_count = len(query_list)
        search_policy = self._search_policy()
        cache_payload = self._load_search_cache()
        cache_entries = cache_payload.get("entries") if isinstance(cache_payload.get("entries"), dict) else {}
        if not isinstance(cache_entries, dict):
            cache_entries = {}
            cache_payload["entries"] = cache_entries
        cache_dirty = False
        for query in query_list:
            filters = self._search_filters()
            request = SearchRequest(
                query=query,
                limit=self.search_limit,
                policy=search_policy,
                include_domains=list(filters.get("include_domains") or []),
                exclude_domains=list(filters.get("exclude_domains") or []),
                time_range=str(filters.get("time_range") or "") or None,
                country=str(filters.get("country") or "") or None,
                search_lang=str(filters.get("search_lang") or "") or None,
            )
            request_payload = request.to_payload()
            cache_key = self._search_cache_key(request_payload)
            cache_entry = cache_entries.get(cache_key) if isinstance(cache_entries, dict) else None
            cache_hit = False
            if isinstance(cache_entry, dict):
                new_hits = self._search_results_from_payload(cache_entry.get("results"))
                execution_payload = cache_entry.get("execution") if isinstance(cache_entry.get("execution"), dict) else {}
                execution = SearchExecution.from_payload(execution_payload) if execution_payload else SearchExecution(
                    provider="cache",
                    configured=True,
                    result_count=len(new_hits),
                    request=request_payload,
                )
                cache_hit = True
                self._search_cache_hit_count += 1
            else:
                new_hits = self.search_tool.search_with_filters(
                    query,
                    limit=self.search_limit,
                    policy=search_policy,
                    include_domains=filters.get("include_domains"),
                    exclude_domains=filters.get("exclude_domains"),
                    time_range=filters.get("time_range"),
                    country=filters.get("country"),
                    search_lang=filters.get("search_lang"),
                )
                execution = self.search_tool.last_execution()
                self._search_cache_miss_count += 1
                if isinstance(execution, SearchExecution):
                    cache_entries[cache_key] = {
                        "request": request_payload,
                        "execution": execution.to_payload(),
                        "results": [hit.to_payload(include_raw_content=True) for hit in new_hits],
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                    cache_dirty = True
            self._search_executed_query_count += 1
            execution_payload = (
                execution.to_payload()
                if isinstance(execution, SearchExecution)
                else {
                    "provider": "cache" if cache_hit else None,
                    "configured": cache_hit,
                    "request": request_payload,
                    "result_count": len(new_hits),
                }
            )
            execution_payload["cache_hit"] = cache_hit
            new_url_count = 0
            deduped_hits_for_record: List[Dict[str, Any]] = []
            for hit in new_hits:
                deduped_hits_for_record.append(hit.to_payload(include_raw_content=True))
                if hit.url in seen_urls:
                    continue
                seen_urls.add(hit.url)
                hits.append(hit)
                new_url_count += 1
            self._search_records.append(
                {
                    "query": query,
                    "query_plan_entry": self._query_plan_index.get(query) or {},
                    "provider": execution.provider if isinstance(execution, SearchExecution) else None,
                    "policy": search_policy,
                    "request": request_payload,
                    "execution": execution_payload,
                    "results": deduped_hits_for_record,
                    "raw_payload_digest": (
                        execution.raw_payload_digest if isinstance(execution, SearchExecution) else None
                    ),
                    "cache_hit": cache_hit,
                    "new_url_count": new_url_count,
                    "early_stop_triggered": False,
                }
            )
            span.event("search", query=query, hits=len(new_hits), cache_hit=cache_hit, new_url_count=new_url_count)
            if self._should_early_stop_search(retained_hits=hits, new_url_count=new_url_count):
                self._search_early_stop_triggered = True
                self._search_records[-1]["early_stop_triggered"] = True
                span.event(
                    "search_early_stop",
                    query=query,
                    executed_queries=self._search_executed_query_count,
                    retained_hits=len(hits),
                )
                break
        if cache_dirty:
            self._write_search_cache(cache_payload)
        return hits

    def _build_evidence_graph(
        self,
        *,
        search_hits: List[SearchResult],
        query_plan: Dict[str, Any],
        tech_stack_candidates: List[Dict[str, Any]],
        family_hypothesis_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        def add_edge(
            edges: List[Dict[str, Any]],
            *,
            edge_from: str,
            edge_to: str,
            kind: str,
            seen: set[tuple[str, str, str]],
        ) -> None:
            key = (edge_from, edge_to, kind)
            if key in seen:
                return
            seen.add(key)
            edges.append({"from": edge_from, "to": edge_to, "kind": kind})

        request_label = str(
            query_plan.get("request_label")
            or self.requirement.get("vuln_name")
            or self.requirement.get("vuln_id")
            or ""
        ).strip()
        nodes: List[Dict[str, Any]] = [
            {
                "id": "request",
                "kind": "request",
                "label": request_label or None,
                "vuln_id": str(self.requirement.get("vuln_id") or "").strip() or None,
            }
        ]
        edges: List[Dict[str, Any]] = []
        edge_seen: set[tuple[str, str, str]] = set()
        queries = query_plan.get("queries") if isinstance(query_plan.get("queries"), list) else []
        query_lookup: Dict[str, tuple[int, Dict[str, Any]]] = {}
        for index, entry in enumerate(queries, start=1):
            if not isinstance(entry, dict):
                continue
            query_lookup[str(entry.get("query") or "").strip()] = (index, entry)
            node_id = f"query:{index}"
            nodes.append(
                {
                    "id": node_id,
                    "kind": "query",
                    "query": str(entry.get("query") or "").strip() or None,
                    "evidence_type": str(entry.get("evidence_type") or "").strip().lower() or None,
                }
            )
            add_edge(edges, edge_from="request", edge_to=node_id, kind="planned_query", seen=edge_seen)
        evidence_entries: List[Dict[str, Any]] = []
        for index, hit in enumerate(search_hits, start=1):
            node_id = f"evidence:{index}"
            query_value = str(hit.query or "").strip()
            query_meta = query_lookup.get(query_value) or (None, {})
            query_index = query_meta[0]
            query_entry = query_meta[1] if isinstance(query_meta[1], dict) else {}
            evidence_type = self._classify_evidence_type(hit)
            source_authority = self._source_authority_for_hit(hit, evidence_type=evidence_type)
            text = self._search_hit_text(hit)
            nodes.append(
                {
                    "id": node_id,
                    "kind": "evidence",
                    "source": str(hit.source or "").strip().lower() or None,
                    "provider": str(hit.provider or "").strip().lower() or None,
                    "url": str(hit.url or "").strip() or None,
                    "query": str(hit.query or "").strip() or None,
                    "evidence_type": evidence_type or None,
                    "source_authority": source_authority,
                }
            )
            if query_index is not None:
                add_edge(
                    edges,
                    edge_from=f"query:{query_index}",
                    edge_to=node_id,
                    kind="retrieved_evidence",
                    seen=edge_seen,
                )
            evidence_entries.append(
                {
                    "id": node_id,
                    "text": text,
                    "query": query_value,
                    "query_entry": query_entry,
                    "evidence_type": evidence_type,
                    "source_authority": source_authority,
                }
            )
        ranked_families = (
            family_hypothesis_summary.get("ranked_families")
            if isinstance(family_hypothesis_summary, dict)
            else []
        )
        family_entries: Dict[str, Dict[str, Any]] = {}

        def ensure_family_entry(
            family: str,
            *,
            confidence: str = "",
            score: Any = None,
            matched_aliases: Optional[List[str]] = None,
            matched_anchors: Optional[List[str]] = None,
        ) -> Dict[str, Any]:
            token = str(family or "").strip().lower()
            if not token:
                return {}
            existing = family_entries.get(token)
            if isinstance(existing, dict):
                if matched_aliases:
                    existing_aliases = existing.setdefault("matched_aliases", [])
                    if isinstance(existing_aliases, list):
                        for item in matched_aliases:
                            alias = str(item).strip().lower()
                            if alias and alias not in existing_aliases:
                                existing_aliases.append(alias)
                if matched_anchors:
                    existing_anchors = existing.setdefault("matched_anchors", [])
                    if isinstance(existing_anchors, list):
                        for item in matched_anchors:
                            anchor = str(item).strip().lower()
                            if anchor and anchor not in existing_anchors:
                                existing_anchors.append(anchor)
                return existing
            node_id = f"family:{token}"
            entry = {
                "node_id": node_id,
                "matched_aliases": [
                    str(item).strip().lower()
                    for item in (matched_aliases or [])
                    if isinstance(item, str) and str(item).strip()
                ],
                "matched_anchors": [
                    str(item).strip().lower()
                    for item in (matched_anchors or [])
                    if isinstance(item, str) and str(item).strip()
                ],
            }
            family_entries[token] = entry
            nodes.append(
                {
                    "id": node_id,
                    "kind": "family_hypothesis",
                    "family": token,
                    "confidence": confidence or None,
                    "score": score,
                    "matched_aliases": entry["matched_aliases"],
                    "matched_anchors": entry["matched_anchors"],
                }
            )
            return entry

        for entry in ranked_families if isinstance(ranked_families, list) else []:
            if not isinstance(entry, dict):
                continue
            family = str(entry.get("family") or "").strip().lower()
            if not family:
                continue
            family_meta = ensure_family_entry(
                family,
                confidence=str(entry.get("confidence") or "").strip().lower(),
                score=entry.get("score"),
                matched_aliases=[
                    str(item).strip().lower()
                    for item in (entry.get("matched_aliases") or [])
                    if isinstance(item, str) and str(item).strip()
                ],
                matched_anchors=[
                    str(item).strip().lower()
                    for item in (entry.get("matched_anchors") or [])
                    if isinstance(item, str) and str(item).strip()
                ],
            )
            add_edge(
                edges,
                edge_from="request",
                edge_to=str(family_meta.get("node_id") or ""),
                kind="family_hypothesis",
                seen=edge_seen,
            )
        negative_family_hypotheses = (
            query_plan.get("negative_family_hypotheses")
            if isinstance(query_plan.get("negative_family_hypotheses"), list)
            else []
        )
        negative_family_entries: Dict[str, Dict[str, Any]] = {}
        for entry in negative_family_hypotheses if isinstance(negative_family_hypotheses, list) else []:
            if not isinstance(entry, dict):
                continue
            family = str(entry.get("family") or "").strip().lower()
            if not family:
                continue
            family_meta = ensure_family_entry(
                family,
                confidence=str(entry.get("confidence") or "").strip().lower(),
            )
            negative_family_entries[family] = family_meta
            add_edge(
                edges,
                edge_from="request",
                edge_to=str(family_meta.get("node_id") or ""),
                kind="negative_family_hypothesis",
                seen=edge_seen,
            )
        stack_entries: Dict[str, Dict[str, Any]] = {}
        for entry in tech_stack_candidates or []:
            if not isinstance(entry, dict):
                continue
            stack_id = str(entry.get("stack_id") or "").strip().lower()
            if not stack_id:
                continue
            node_id = f"stack:{stack_id}"
            stack_entries[stack_id] = {
                "node_id": node_id,
                "framework": str(entry.get("framework") or "").strip().lower() or None,
                "language": str(entry.get("language") or "").strip().lower() or None,
            }
            nodes.append(
                {
                    "id": node_id,
                    "kind": "stack_hypothesis",
                    "stack_id": stack_id,
                    "confidence": str(entry.get("confidence") or "").strip().lower() or None,
                    "score": entry.get("score"),
                }
            )
            add_edge(edges, edge_from="request", edge_to=node_id, kind="stack_hypothesis", seen=edge_seen)

        known_framework_markers = {
            "python/flask": ["flask"],
            "python/fastapi": ["fastapi", "uvicorn"],
        }
        for evidence in evidence_entries:
            evidence_text = str(evidence.get("text") or "")
            evidence_id = str(evidence.get("id") or "")
            if not evidence_id:
                continue
            for family, family_meta in family_entries.items():
                supports_family = False
                family_label = family.replace("_", " ")
                if any(token in evidence_text for token in family_meta.get("matched_aliases") or []):
                    supports_family = True
                elif any(token in evidence_text for token in family_meta.get("matched_anchors") or []):
                    supports_family = True
                elif family_label and family_label in evidence_text:
                    supports_family = True
                if supports_family:
                    add_edge(
                        edges,
                        edge_from=evidence_id,
                        edge_to=str(family_meta.get("node_id") or ""),
                        kind="supports_family_hypothesis",
                        seen=edge_seen,
                    )
            for family, family_meta in negative_family_entries.items():
                supports_negative_family = False
                family_label = family.replace("_", " ")
                if any(token in evidence_text for token in family_meta.get("matched_aliases") or []):
                    supports_negative_family = True
                elif any(token in evidence_text for token in family_meta.get("matched_anchors") or []):
                    supports_negative_family = True
                elif family_label and family_label in evidence_text:
                    supports_negative_family = True
                if supports_negative_family:
                    add_edge(
                        edges,
                        edge_from=evidence_id,
                        edge_to=str(family_meta.get("node_id") or ""),
                        kind="supports_negative_family_hypothesis",
                        seen=edge_seen,
                    )
            for stack_id, stack_meta in stack_entries.items():
                supports_stack = False
                framework = str(stack_meta.get("framework") or "").strip().lower()
                markers = list(known_framework_markers.get(stack_id, []))
                if framework and framework not in markers:
                    markers.append(framework)
                if any(marker in evidence_text for marker in markers if marker):
                    supports_stack = True
                if supports_stack:
                    add_edge(
                        edges,
                        edge_from=evidence_id,
                        edge_to=str(stack_meta.get("node_id") or ""),
                        kind="supports_stack_hypothesis",
                        seen=edge_seen,
                    )
        return {
            "schema_version": "evidence_graph@0.1",
            "source": "researcher_derived",
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": nodes,
            "edges": edges,
        }

    def _write_search_artifacts(self, search_hits: List[SearchResult], *, policy: str) -> Dict[str, Any]:
        traces_dir = ensure_dir(self.metadata_dir / "search_traces")
        for index, record in enumerate(self._search_records, start=1):
            query = str(record.get("query") or "")
            digest = hashlib.sha256(query.encode("utf-8")).hexdigest()[:12] if query else f"{index:012d}"
            trace_path = traces_dir / f"{index:02d}-{digest}.json"
            payload = {
                "query": query,
                "query_plan_entry": record.get("query_plan_entry") or {},
                "provider": record.get("provider"),
                "policy": policy,
                "request": record.get("request") or {},
                "execution": record.get("execution") or {},
                "results": record.get("results") or [],
                "raw_payload_digest": record.get("raw_payload_digest"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            trace_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

        last_execution_payload = (
            self._search_records[-1].get("execution") if self._search_records else None
        )
        last_execution = (
            SearchExecution.from_payload(last_execution_payload)
            if isinstance(last_execution_payload, dict)
            else None
        )
        degraded = any(
            bool((record.get("execution") or {}).get("degraded"))
            for record in self._search_records
            if isinstance(record.get("execution"), dict)
        )
        remote_result_count = 0
        local_result_count = 0
        for record in self._search_records:
            results = record.get("results") or []
            if not isinstance(results, list):
                continue
            for item in results:
                if not isinstance(item, dict):
                    continue
                source = str(item.get("source") or "").strip().lower()
                if source == "remote":
                    remote_result_count += 1
                elif source == "local":
                    local_result_count += 1
        health_path = self.metadata_dir / "search_health.json"
        health_payload = {
            "provider": (
                last_execution.provider
                if isinstance(last_execution, SearchExecution) and last_execution.provider
                else self.search_tool.provider_name or ("custom" if self.search_tool.endpoint else "none")
            ),
            "configured": bool(last_execution.configured) if isinstance(last_execution, SearchExecution) else False,
            "policy": policy,
            "endpoint_or_base_url": (
                last_execution.endpoint_or_base_url
                if isinstance(last_execution, SearchExecution)
                else (self.search_tool.endpoint or self.search_tool.base_url or None)
            ),
            "auth_present": last_execution.auth_present if isinstance(last_execution, SearchExecution) else None,
            "request_count": len(self._search_records),
            "remote_result_count": remote_result_count,
            "local_result_count": local_result_count,
            "cache_hit_count": self._search_cache_hit_count,
            "cache_miss_count": self._search_cache_miss_count,
            "cache_reuse_ratio": round(
                self._search_cache_hit_count / max(1, self._search_cache_hit_count + self._search_cache_miss_count),
                3,
            ),
            "planned_query_count": self._search_planned_query_count,
            "executed_query_count": self._search_executed_query_count,
            "early_stop_triggered": self._search_early_stop_triggered,
            "degraded": degraded,
            "last_error": last_execution.error if isinstance(last_execution, SearchExecution) else None,
            "last_status_code": last_execution.status_code if isinstance(last_execution, SearchExecution) else None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        health_path.write_text(json.dumps(health_payload, indent=2, ensure_ascii=False), encoding="utf-8")
        self._search_health_path = health_path
        self._search_degraded = degraded
        return {"health_path": health_path, "degraded": degraded}

    def _format_search_failure_reason(self, reason: str) -> str:
        text = str(reason or "").strip()
        if self._search_health_path:
            return f"{text} See {self._search_health_path}."
        return text

    def _generate_report(self, rag_context: str, search_hits: List[SearchResult]) -> Dict[str, Any]:
        prompt = build_researcher_prompt(
            self.requirement,
            search_results=[hit.to_payload() for hit in search_hits],
            rag_context=rag_context,
            failure_context=self.react_loop.failure_context,
            variation_key=self.variation_manager.key,
        )
        self._record_prompt_invocation("researcher_report")
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
        return normalize_researcher_report_payload(report)

    def _write_report(self, report: Dict[str, Any]) -> Path:
        path = self.metadata_dir / "researcher_report.json"
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def _llm_execution_summary(self) -> Dict[str, Any]:
        llm = getattr(self, "llm", None)
        if llm is None:
            return {}
        cache_active = (self._search_cache_hit_count + self._search_cache_miss_count) > 0
        prompt_invocations = self._prompt_invocation_counts()
        search_timeout_s = getattr(getattr(self, "search_tool", None), "timeout", None)
        metadata = {
            "cache_mode": "search_cache_read_write" if cache_active else None,
            "timeout_budget": {"search_timeout_s": float(search_timeout_s)} if isinstance(search_timeout_s, (int, float)) else None,
        }
        if prompt_invocations:
            metadata["prompt_contracts"] = [prompt_contract(name) for name in prompt_invocations]
            metadata["prompt_invocations"] = prompt_invocations
        retry_budget = self._llm_retry_budget_metadata(prompt_invocations)
        if retry_budget:
            metadata["retry_budget"] = retry_budget
        return llm_execution_summary(llm, observed=True, metadata=metadata)

    def _record_prompt_invocation(self, name: str) -> None:
        token = str(name or "").strip()
        if not token:
            return
        current = getattr(self, "_llm_prompt_invocations", None)
        if not isinstance(current, dict):
            current = {}
            self._llm_prompt_invocations = current
        current[token] = int(current.get(token) or 0) + 1

    def _prompt_invocation_counts(self) -> Dict[str, int]:
        current = getattr(self, "_llm_prompt_invocations", None)
        if not isinstance(current, dict):
            return {}
        normalized: Dict[str, int] = {}
        for key, value in current.items():
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

    def _retry_budget_context(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        plan = self.plan if isinstance(getattr(self, "plan", None), dict) else {}
        loop_cfg = plan.get("loop") if isinstance(plan.get("loop"), dict) else {}
        try:
            max_loops = int(loop_cfg.get("max_loops"))
        except Exception:
            max_loops = 0
        if max_loops > 0:
            payload["controller_loop_max"] = max_loops
        loop_state_path = self.metadata_dir / "loop_state.json"
        if loop_state_path.exists():
            try:
                state = json.loads(loop_state_path.read_text(encoding="utf-8"))
            except Exception:
                state = {}
            try:
                current_loop = int((state or {}).get("current_loop", 0))
            except Exception:
                current_loop = 0
            if current_loop > 0:
                payload["controller_loop_current"] = current_loop
        return payload

    def _llm_retry_budget_metadata(self, prompt_invocations: Dict[str, int]) -> Dict[str, Any]:
        payload: Dict[str, Any] = self._retry_budget_context()
        if "researcher_report" in prompt_invocations:
            payload["researcher_report_runs"] = int(prompt_invocations.get("researcher_report") or 0)
        planned_runs = int(getattr(self, "_guard_planner_planned_runs", 0) or 0)
        actual_runs = int(prompt_invocations.get("guard_planner") or 0)
        budget_mode = str(getattr(self, "_guard_planner_budget_mode", "") or "").strip()
        if planned_runs > 0 or actual_runs > 0:
            payload["guard_planner_planned_runs"] = planned_runs
            payload["guard_planner_actual_runs"] = actual_runs
            if budget_mode:
                payload["guard_budget_mode"] = budget_mode
        return payload

    def write_skip_report(self, reason: str) -> Path:
        active_bundle = self.bundle
        query_plan = self.react_loop.query_plan_from_requirement(
            self.requirement,
            limit=self._effective_query_plan_limit(),
        )
        report = {
            "sid": self.sid,
            "vuln_id": active_bundle.vuln_id if active_bundle else self.requirement.get("vuln_id"),
            "trace_id": self.react_loop.trace_id,
            "retrieval_snapshot_id": self._snapshot_id(),
            "failure_context": self.react_loop.failure_context,
            "search_policy": self._search_policy(),
            "search_health_path": None,
            "search_degraded": False,
            "evidence": [],
            "query_plan": query_plan,
            "evidence_type_summary": {},
            "family_hypothesis_summary": {},
            "semantic_signature": {},
            "evidence_relevance": {},
            "quality": "skipped",
            "quality_reason": reason,
            "guard_fallback": False,
            "guard_spec_path": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "skipped_reason": reason,
            "llm_execution": self._llm_execution_summary(),
        }
        report["semantic_signature"], report["semantic_signature_source"] = self._resolve_semantic_signature(
            report,
            active_bundle,
        )
        report = self._canonicalize_report_identity(report, active_bundle)
        contract_path = self._write_resolved_contract_seed(report, active_bundle)
        report["resolved_contract_path"] = str(contract_path)
        self._last_report = report
        return self._write_report(report)

    def write_fail_closed_report(
        self,
        *,
        reason: str,
        terminal_failure_class: str,
        fix_hint: str = "",
    ) -> Path:
        active_bundle = self.bundle
        query_plan = self.react_loop.query_plan_from_requirement(
            self.requirement,
            limit=self._effective_query_plan_limit(),
        )
        report = {
            "sid": self.sid,
            "vuln_id": active_bundle.vuln_id if active_bundle else self.requirement.get("vuln_id"),
            "trace_id": self.react_loop.trace_id,
            "retrieval_snapshot_id": self._snapshot_id(),
            "failure_context": self.react_loop.failure_context,
            "search_policy": self._search_policy(),
            "search_health_path": None,
            "search_degraded": False,
            "evidence": [],
            "query_plan": query_plan,
            "evidence_type_summary": {},
            "family_hypothesis_summary": {},
            "semantic_signature": {},
            "evidence_relevance": {},
            "quality": "insufficient",
            "quality_reason": reason,
            "guard_fallback": False,
            "guard_spec_path": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "terminal_failure_class": str(terminal_failure_class or "").strip(),
            "retry_recommended": False,
            "fix_hint": fix_hint,
            "skipped_reason": reason,
            "llm_execution": self._llm_execution_summary(),
        }
        report["semantic_signature"], report["semantic_signature_source"] = self._resolve_semantic_signature(
            report,
            active_bundle,
        )
        report = self._canonicalize_report_identity(report, active_bundle)
        contract_path = self._write_resolved_contract_seed(report, active_bundle)
        report["resolved_contract_path"] = str(contract_path)
        self._last_report = report
        return self._write_report(report)

    def _write_resolved_contract_seed(self, report: Dict[str, Any], bundle: VulnBundle | None) -> Path:
        vuln_id = str(bundle.vuln_id if bundle else self.requirement.get("vuln_id") or "UNKNOWN")
        slug = bundle.slug if bundle else ""
        payload = build_generator_contract(
            sid=self.sid,
            vuln_id=vuln_id,
            metadata_dir=self.metadata_dir,
            workspace_dir=None,
            generator_mode="research_seed",
            bundle_slug=slug,
            researcher_report=report,
            requirement=self.requirement,
        )
        return write_generator_contract(self.metadata_dir, payload)

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
            self._last_report = normalize_researcher_report_payload(data)
            return self._last_report
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

    def _search_filters(self) -> Dict[str, Any]:
        researcher_cfg = self.requirement.get("researcher") or {}
        if not isinstance(researcher_cfg, dict):
            return {}
        raw = researcher_cfg.get("search_filters")
        if not isinstance(raw, dict):
            return {}
        filters: Dict[str, Any] = {}
        for key in ("include_domains", "exclude_domains"):
            values = raw.get(key)
            if isinstance(values, str):
                values = [values]
            if not isinstance(values, list):
                continue
            cleaned = [str(value).strip() for value in values if isinstance(value, str) and str(value).strip()]
            if cleaned:
                filters[key] = list(dict.fromkeys(cleaned))
        for key in ("time_range", "country", "search_lang"):
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                filters[key] = value.strip()
        return filters

    def _allow_candidate_templates(self) -> bool:
        researcher_cfg = self.requirement.get("researcher") or {}
        if not isinstance(researcher_cfg, dict):
            return False
        return bool(researcher_cfg.get("generate_candidate_templates", False))

    def _effective_query_plan_limit(self) -> int:
        limit = max(1, int(self.search_limit or 1))
        if not self._dynamic_eval_enabled():
            return limit
        if not self._bundle_is_name_driven(self.bundle):
            return limit
        if self.requirement.get("language") and self.requirement.get("framework"):
            return limit
        stack_hypotheses = (
            self.requirement.get("stack_hypotheses")
            if isinstance(self.requirement.get("stack_hypotheses"), list)
            else []
        )
        if len(stack_hypotheses) < 2:
            return limit
        return max(limit, 4)

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
            return not can_resolve_without_remote_research_for_requirement(vuln_id, self.requirement)
        requirement_view = bundle_requirement(self.plan["requirement"], bundle)
        return not can_resolve_without_remote_research_for_requirement(bundle.vuln_id, requirement_view)

    def _require_researcher_evidence(self, bundle: VulnBundle | None) -> bool:
        plan_policy = self.plan.get("policy") or {}
        if isinstance(plan_policy, dict) and "require_researcher_evidence" in plan_policy:
            return bool(plan_policy.get("require_researcher_evidence"))
        return self._bundle_is_unknown(bundle)

    def _open_world_strict_mode(self) -> bool:
        plan_policy = self.plan.get("policy") or {}
        if not isinstance(plan_policy, dict):
            return False
        return bool(plan_policy.get("open_world_strict"))

    def _bundle_requirement_view(self, bundle: VulnBundle | None) -> Dict[str, Any]:
        if bundle is None:
            requirement_view = dict(self.requirement) if isinstance(self.requirement, dict) else {}
        else:
            plan = self.plan if isinstance(getattr(self, "plan", None), dict) else {}
            base_requirement = plan.get("requirement") if isinstance(plan, dict) else {}
            raw_view = bundle_requirement(base_requirement, bundle)
            requirement_view = dict(raw_view) if isinstance(raw_view, dict) else {}
        vuln_id = str(
            requirement_view.get("vuln_id")
            or (bundle.vuln_id if bundle is not None else (self.requirement.get("vuln_id") if isinstance(self.requirement, dict) else ""))
            or ""
        ).strip()
        if vuln_id:
            requirement_view.setdefault("vuln_id", vuln_id)
        if "policy" not in requirement_view:
            plan = self.plan if isinstance(getattr(self, "plan", None), dict) else {}
            plan_policy = plan.get("policy") if isinstance(plan, dict) else {}
            if isinstance(plan_policy, dict) and plan_policy:
                requirement_view["policy"] = dict(plan_policy)
        return requirement_view

    def _bundle_is_name_driven(self, bundle: VulnBundle | None) -> bool:
        return is_name_driven_requirement(self._bundle_requirement_view(bundle))

    def _guard_policy(self) -> Dict[str, Any]:
        plan_policy = self.plan.get("policy") or {}
        guard_raw = {}
        if isinstance(plan_policy, dict):
            maybe_guard = plan_policy.get("guard")
            if isinstance(maybe_guard, dict):
                guard_raw = maybe_guard
        return default_guard_policy_snapshot(guard_raw)

    def _low_confidence_unknown_policy(self) -> str:
        policy = str(self._guard_policy().get("low_confidence_unknown_policy") or "warn").strip().lower()
        if policy in {"warn", "guard_fallback", "fail_closed"}:
            return policy
        return "warn"

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
        if self._dynamic_eval_enabled():
            compiler_metadata_fields = {
                "metadata.stack_scaffold_id",
                "metadata.fragment_id",
                "metadata.compose_mode",
                "metadata.compiler_strategy",
            }
            filtered_generators = [
                assertion
                for assertion in norm_generators
                if not (
                    isinstance(assertion, dict)
                    and str(assertion.get("op") or "").strip().lower() == "manifest_field_contains"
                    and str(assertion.get("field") or "").strip() in compiler_metadata_fields
                )
            ]
            if len(filtered_generators) != len(norm_generators):
                warnings.append(
                    "removed compiler-lower-bound metadata assertions from generator_assertions for dynamic name-only posture"
                )
            norm_generators = filtered_generators
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
        self._align_verifier_assertions_with_verification_spec(
            normalized,
            report=report,
            bundle=bundle,
            warnings=warnings,
        )
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
            if self._filter_stdlib_dependency_assertion(
                assertion,
                scope=scope,
                dropped_ops=dropped_ops,
                warnings=warnings,
            ):
                continue

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
            warnings.append(f"dropped unsupported guard assertion op in {scope}: {mapped_op}")
        return normalized

    def _filter_stdlib_dependency_assertion(
        self,
        assertion: Dict[str, Any],
        *,
        scope: str,
        dropped_ops: List[Dict[str, Any]],
        warnings: List[str],
    ) -> bool:
        if scope != "generator" or not isinstance(assertion, dict):
            return False
        op = str(assertion.get("op") or "").strip().lower()
        if op not in {"dep_declared", "any_dep_declared"}:
            return False

        blocked = self._stdlib_dependency_names()
        if not blocked:
            return False

        if op == "dep_declared":
            dep = self._normalize_dependency_name(assertion.get("dep"))
            if dep and dep in blocked:
                dropped_ops.append({"op": op, "scope": scope, "reason": "stdlib_dependency", "dep": dep})
                warnings.append(
                    f"dropped generator dependency assertion for stdlib/runtime-provided module '{dep}'"
                )
                return True
            return False

        raw_deps = assertion.get("deps")
        deps = raw_deps if isinstance(raw_deps, list) else [raw_deps]
        kept: List[str] = []
        removed: List[str] = []
        for item in deps:
            token = str(item).strip() if isinstance(item, str) else ""
            if not token:
                continue
            normalized = self._normalize_dependency_name(token)
            if normalized in blocked:
                removed.append(token)
                continue
            kept.append(token)

        if removed:
            warnings.append(
                "removed stdlib/runtime-provided dependency candidates from guard assertion: "
                + ", ".join(removed)
            )
        if not kept:
            dropped_ops.append({"op": op, "scope": scope, "reason": "stdlib_dependency", "deps": removed})
            return True
        assertion["deps"] = kept
        return False

    def _stdlib_dependency_names(self) -> set[str]:
        requirement = self.requirement if isinstance(self.requirement, dict) else {}
        language = str(requirement.get("language") or "python").strip().lower() or "python"
        runtime = requirement.get("runtime") or {}
        version = None
        if isinstance(runtime, dict):
            version = runtime.get("language_version") or runtime.get("python_version")
        spec = load_stdlib_spec(language=language, version=str(version or "3.11"))
        blocked: set[str] = set()
        for token in spec.stdlib_modules | spec.auto_patch_denylist:
            normalized = self._normalize_dependency_name(token)
            if normalized:
                blocked.add(normalized)
        for module_name, package_name in spec.aliases.items():
            module_norm = self._normalize_dependency_name(module_name)
            package_norm = self._normalize_dependency_name(package_name)
            if module_norm and module_norm in blocked and package_norm:
                blocked.add(package_norm)
                if package_norm.endswith("-binary"):
                    blocked.add(package_norm[: -len("-binary")])
        return blocked

    @staticmethod
    def _normalize_dependency_name(value: Any) -> str:
        if not isinstance(value, str):
            return ""
        cleaned = value.strip().lower().replace("_", "-")
        if not cleaned:
            return ""
        return re.split(r"[<>=!~\[\]\s]+", cleaned, maxsplit=1)[0]

    def _align_verifier_assertions_with_verification_spec(
        self,
        payload: Dict[str, Any],
        *,
        report: Dict[str, Any],
        bundle: VulnBundle | None,
        warnings: List[str],
    ) -> None:
        if not isinstance(payload, dict):
            return
        assertions = payload.get("verifier_assertions")
        if not isinstance(assertions, list):
            return
        vuln_id = bundle.vuln_id if bundle else str(self.requirement.get("vuln_id") or "")
        spec = extract_verification_spec(report, vuln_id=vuln_id)
        if not isinstance(spec, dict):
            return
        spec, normalization = self._normalize_runtime_verification_spec(spec)
        raw_markers = spec.get("success_text_markers") or []
        markers: List[str] = []
        if isinstance(raw_markers, list):
            markers.extend(str(item).strip() for item in raw_markers if isinstance(item, str) and str(item).strip())
        elif isinstance(raw_markers, str) and raw_markers.strip():
            markers.append(raw_markers.strip())
        dropped_markers = set(normalization.get("dropped_markers") or [])
        negative_markers = [
            str(item).strip()
            for item in (normalization.get("negative_markers") or [])
            if isinstance(item, str) and str(item).strip()
        ]
        structured_success = self._derive_structured_success_contract(markers)
        canonical_marker = str(structured_success.get("canonical_marker") or "").strip()
        changed = False
        normalized_assertions: List[Dict[str, Any]] = []
        has_positive = {marker: False for marker in markers}
        has_negative = {marker: False for marker in negative_markers}
        variants = {marker for marker in markers if marker}
        if canonical_marker:
            variants.add(canonical_marker)

        for assertion in assertions:
            if not isinstance(assertion, dict):
                continue
            op = str(assertion.get("op") or "").strip().lower()
            token = str(assertion.get("string") or "").strip()
            if op == "contains":
                if token and token in dropped_markers and token not in markers:
                    changed = True
                    continue
                if canonical_marker and token and token in variants and token != canonical_marker:
                    assertion["string"] = canonical_marker
                    token = canonical_marker
                    changed = True
                if token in has_positive:
                    has_positive[token] = True
            elif op == "not_contains" and token in has_negative:
                has_negative[token] = True
            normalized_assertions.append(assertion)

        for marker, present in has_positive.items():
            if present:
                continue
            normalized_assertions.insert(
                0,
                {
                    "op": "contains",
                    "string": canonical_marker if canonical_marker and marker in variants else marker,
                    "severity": "block",
                    "intent": "semantic_anchor",
                    "stability": "medium",
                    "evidence_ids": [],
                },
            )
            changed = True
        for marker, present in has_negative.items():
            if present:
                continue
            normalized_assertions.append(
                {
                    "op": "not_contains",
                    "string": marker,
                    "severity": "block",
                    "intent": "semantic_anchor",
                    "stability": "medium",
                    "evidence_ids": [],
                }
            )
            changed = True
        if changed:
            payload["verifier_assertions"] = normalized_assertions
            if canonical_marker:
                warnings.append("aligned verifier success marker with canonical structured success contract")
            else:
                warnings.append("aligned verifier assertions with normalized runtime verification contract")

    @staticmethod
    def _extract_print_markers_from_assertion_program(program: str) -> Dict[str, List[str]]:
        positive: List[str] = []
        negative: List[str] = []
        if not isinstance(program, str) or not program.strip():
            return {"positive": positive, "negative": negative}
        for match in re.finditer(r"print\(\s*(['\"])(?P<text>.*?)(?<!\\)\1\s*\)", program, flags=re.DOTALL):
            token = str(match.group("text") or "").strip()
            if not token:
                continue
            lowered = token.lower()
            if lowered.startswith(("fail", "error", "unexpected")):
                if token not in negative:
                    negative.append(token)
                continue
            if token not in positive:
                positive.append(token)
        return {"positive": positive, "negative": negative}

    @staticmethod
    def _looks_like_flag_token(token: str) -> bool:
        candidate = str(token or "").strip()
        lowered = candidate.lower()
        if not candidate:
            return False
        return (
            "flag" in lowered
            or "token" in lowered
            or ("{" in candidate and "}" in candidate)
        )

    @staticmethod
    def _is_weak_runtime_marker(token: str) -> bool:
        candidate = str(token or "").strip()
        if not candidate:
            return True
        if re.fullmatch(r"-?\d+(?:\.\d+)?", candidate):
            return True
        if candidate.lower() in {"true", "false", "null", "none"}:
            return True
        return False

    def _normalize_runtime_verification_spec(
        self,
        spec: Dict[str, Any],
    ) -> tuple[Dict[str, Any], Dict[str, List[str]]]:
        normalized = dict(spec)
        info: Dict[str, List[str]] = {
            "dropped_markers": [],
            "negative_markers": [],
        }
        raw_markers = normalized.get("success_text_markers") or []
        markers: List[str] = []
        if isinstance(raw_markers, list):
            markers = [str(item).strip() for item in raw_markers if isinstance(item, str) and str(item).strip()]
        elif isinstance(raw_markers, str) and raw_markers.strip():
            markers = [raw_markers.strip()]

        program = normalized.get("assertion_program")
        extracted = self._extract_print_markers_from_assertion_program(program) if isinstance(program, str) else {"positive": [], "negative": []}
        positive_markers = extracted.get("positive") or []
        negative_markers = extracted.get("negative") or []

        use_program_print_markers = False
        if positive_markers and markers and all(self._is_weak_runtime_marker(marker) for marker in markers):
            info["dropped_markers"] = list(markers)
            normalized["success_text_markers"] = positive_markers
            markers = list(positive_markers)
            use_program_print_markers = True
        elif positive_markers and not markers:
            normalized["success_text_markers"] = positive_markers
            markers = list(positive_markers)
            use_program_print_markers = True

        flag_token = str(normalized.get("flag_token") or "").strip()
        if (
            positive_markers
            and flag_token
            and (flag_token in info["dropped_markers"] or self._is_weak_runtime_marker(flag_token))
            and not self._looks_like_flag_token(flag_token)
        ):
            normalized.pop("flag_token", None)
            normalized["flag_mode"] = "none"

        if isinstance(program, str) and positive_markers and use_program_print_markers:
            assertion_program: List[Dict[str, Any]] = [
                {"op": "contains", "string": marker}
                for marker in positive_markers
                if isinstance(marker, str) and marker
            ]
            assertion_program.extend(
                {"op": "not_contains", "string": marker}
                for marker in negative_markers
                if isinstance(marker, str) and marker
            )
            normalized["assertion_program"] = assertion_program

        info["negative_markers"] = list(negative_markers)
        return normalized, info

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
            if assertion.get("dep") is None:
                for key in ("deps", "names", "packages"):
                    value = assertion.get(key)
                    values = value if isinstance(value, list) else [value]
                    normalized = [
                        str(item).strip()
                        for item in values
                        if isinstance(item, str) and str(item).strip()
                    ]
                    if normalized:
                        assertion["dep"] = normalized[0]
                        mismatches.append(f"{op}.dep missing, found {key}[0]")
                        break
            assertion.pop("name", None)
            assertion.pop("package", None)
            assertion.pop("deps", None)
            assertion.pop("names", None)
            assertion.pop("packages", None)
        elif op == "any_dep_declared":
            _map_key("deps", ["names", "packages"])
            value = assertion.get("deps")
            if isinstance(value, str):
                assertion["deps"] = [value]
            assertion.pop("names", None)
            assertion.pop("packages", None)
        elif op in {"file_contains", "file_not_contains"}:
            _map_key("string", ["contains", "needle"])
            assertion.pop("contains", None)
            assertion.pop("needle", None)
        elif op == "role_exists":
            role = normalize_role(assertion.get("role"))
            if role:
                assertion["role"] = role
        elif op in {"file_regex_contains", "file_regex_not_contains", "file_regex_any"}:
            _map_key("regex", ["pattern"])
            if op == "file_regex_any":
                _map_key("globs", ["paths", "glob"])
                patterns = assertion.get("patterns")
                if not assertion.get("regex") and isinstance(patterns, list):
                    merged = [
                        str(item).strip()
                        for item in patterns
                        if isinstance(item, str) and str(item).strip()
                    ]
                    if merged:
                        assertion["regex"] = merged[0] if len(merged) == 1 else "(?:" + ")|(?:".join(merged) + ")"
                        assertion["_normalized_from_patterns"] = True
                        mismatches.append("file_regex_any.regex missing, found patterns[]")
                globs = assertion.get("globs")
                if globs is None and assertion.get("path") is not None:
                    globs = [assertion.get("path")]
                    assertion["globs"] = globs
                    assertion["_defaulted_globs"] = True
                    mismatches.append("file_regex_any.globs missing, found path")
                if globs is None:
                    assertion["globs"] = ResearcherService._default_guard_globs()
                    assertion["_defaulted_globs"] = True
                    mismatches.append("file_regex_any.globs missing, defaulted to stack-aware globs")
                elif isinstance(globs, str):
                    assertion["globs"] = [globs]
            assertion.pop("pattern", None)
            assertion.pop("paths", None)
            assertion.pop("glob", None)
            assertion.pop("patterns", None)
            if op == "file_regex_any":
                assertion.pop("path", None)
        return mismatches

    @staticmethod
    def _default_guard_globs() -> List[str]:
        return ["*.py", "*.js", "*.ts", "*.php", "*.rb", "*.java", "*.go", "*.sql"]

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

        if scope == "generator":
            warnings.extend(enforce_generator_assertion_trust_boundary(assertion))

        if scope == "generator" and op in {"file_regex_contains", "file_regex_not_contains", "file_regex_any"}:
            pattern = str(assertion.get("regex") or assertion.get("pattern") or "")
            alternations = pattern.count("|")
            normalized_from_patterns = bool(assertion.pop("_normalized_from_patterns", False))
            defaulted_globs = bool(assertion.pop("_defaulted_globs", False))
            if len(pattern) > 220 or alternations >= 8:
                assertion["intent"] = "syntax_hint"
                assertion["stability"] = "low"
                if assertion.get("severity") != "warn":
                    assertion["severity"] = "warn"
                warnings.append(
                    f"brittle regex assertion downgraded ({op}) due to complexity/length; treated as syntax_hint warn"
                )
            elif op == "file_regex_any" and (normalized_from_patterns or defaulted_globs):
                assertion["intent"] = "syntax_hint"
                assertion["stability"] = "low"
                assertion["severity"] = "warn"
                warnings.append(
                    "file_regex_any synthesized from non-canonical inputs; downgraded to syntax_hint warn"
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
        pattern_id = str(self.requirement.get("pattern_id") or "").strip().lower()
        raw_label = self._raw_vuln_label()
        assertions = fragment_guard_generator_assertions(vuln_id, pattern_id=pattern_id, raw_label=raw_label)
        if self._dynamic_eval_enabled():
            compiler_metadata_fields = {
                "metadata.stack_scaffold_id",
                "metadata.fragment_id",
                "metadata.compose_mode",
                "metadata.compiler_strategy",
            }
            assertions = [
                assertion
                for assertion in assertions
                if not (
                    isinstance(assertion, dict)
                    and str(assertion.get("op") or "").strip().lower() == "manifest_field_contains"
                    and str(assertion.get("field") or "").strip() in compiler_metadata_fields
                )
            ]
        if not assertions:
            assertions = [
                {"op": "role_exists", "role": "service_main"},
                {"op": "role_exists", "role": "poc_entry"},
            ]
        assertions.append(
            {
                "op": "manifest_field_contains",
                "field": "poc.success_signature",
                "string": success_signature,
                "intent": "contract",
                "stability": "high",
            }
        )
        return assertions

    def _dynamic_eval_enabled(self) -> bool:
        requirement_view = self._bundle_requirement_view(getattr(self, "bundle", None))
        requirement_policy = (
            requirement_view.get("policy") if isinstance(requirement_view.get("policy"), dict) else {}
        )
        if isinstance(requirement_policy, dict) and bool(requirement_policy.get("dynamic_eval")):
            return True
        contract = build_name_only_contract(
            requirement=requirement_view,
            policy=requirement_policy if isinstance(requirement_policy, dict) else {},
        )
        return bool(
            contract.get("enabled")
            and str(contract.get("effective_mode") or "").strip().lower() in {"dynamic", "dynamic_eval", "strict_dynamic"}
        )

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
        self._guard_planner_budget_mode = budget_mode
        self._guard_planner_planned_runs = run_count

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
            self._record_prompt_invocation("guard_planner")
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
        payload.setdefault("confidence", self._report_confidence(report))
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
        verification_spec = extract_verification_spec(
            report,
            vuln_id=bundle.vuln_id if bundle else str(self.requirement.get("vuln_id") or ""),
        )
        if not isinstance(verification_spec, dict):
            verification_spec = {}
        verification_spec, _ = self._normalize_runtime_verification_spec(verification_spec)
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
        generator_assertions = self._fallback_generator_assertions(bundle)
        generator_assertions = [
            item
            for item in generator_assertions
            if not (
                isinstance(item, dict)
                and str(item.get("op") or "").strip().lower() == "manifest_field_contains"
                and str(item.get("field") or "").strip() == "poc.success_signature"
            )
        ]
        generator_assertions.append(
            {
                "op": "manifest_field_contains",
                "field": "poc.success_signature",
                "string": success_marker,
                "intent": "contract",
                "stability": "high",
            }
        )
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
            confidence=self._report_confidence(report),
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
    def _report_confidence(report: Dict[str, Any]) -> str:
        relevance = report.get("evidence_relevance") if isinstance(report, dict) else {}
        if isinstance(relevance, dict):
            confidence = str(relevance.get("confidence") or "").strip().lower()
            if confidence in {"high", "medium", "low"}:
                return confidence
        return "medium"

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
        name_driven = self._bundle_is_name_driven(bundle)
        open_world_strict = self._open_world_strict_mode()
        remote_hits = [hit for hit in search_hits if str(hit.source).strip().lower() == "remote"]
        if open_world_strict and name_driven and self._search_degraded:
            vuln = bundle.vuln_id if bundle else str(self.requirement.get("vuln_id") or "UNKNOWN")
            return (
                "insufficient",
                (
                    f"Insufficient researcher evidence for {vuln}: open_world_strict requires non-degraded remote research, "
                    "but the search provider degraded to local/fallback results."
                ),
            )
        if open_world_strict and name_driven and not remote_hits:
            vuln = bundle.vuln_id if bundle else str(self.requirement.get("vuln_id") or "UNKNOWN")
            return (
                "insufficient",
                (
                    f"Insufficient researcher evidence for {vuln}: open_world_strict requires at least one remote hit "
                    "for name-driven lanes, but none were found."
                ),
            )
        if search_policy == "remote_required" and not remote_hits:
            vuln = bundle.vuln_id if bundle else str(self.requirement.get("vuln_id") or "UNKNOWN")
            return (
                "insufficient",
                (
                    f"Insufficient researcher evidence for {vuln}: search_policy=remote_required requires at least "
                    "one remote hit, but none were found. Configure the remote search provider "
                    "(for example VUL_WEB_SEARCH_PROVIDER/VUL_WEB_SEARCH_API_KEY or VUL_WEB_SEARCH_ENDPOINT) or relax "
                    "researcher.search_policy."
                ),
            )
        if require_evidence and unknown and not remote_hits:
            vuln = bundle.vuln_id if bundle else str(self.requirement.get("vuln_id") or "UNKNOWN")
            return (
                "insufficient",
                (
                    f"Insufficient researcher evidence for unknown CWE {vuln}: remote provenance is required, "
                    "but only local/no evidence was collected. Configure the remote search provider or set "
                    "policy.require_researcher_evidence=false explicitly."
                ),
            )
        if require_evidence and not search_hits:
            vuln = bundle.vuln_id if bundle else str(self.requirement.get("vuln_id") or "UNKNOWN")
            return (
                "insufficient",
                f"Insufficient researcher evidence for {vuln}: no search evidence was collected.",
            )
        relevance_report = self._score_evidence_relevance(bundle, search_hits)
        self._last_evidence_relevance = relevance_report
        relevance_score = float(relevance_report.get("score") or 0.0)
        threshold = float(relevance_report.get("threshold") or self._relevance_threshold(bundle))
        confidence = str(relevance_report.get("confidence") or "medium").strip().lower()
        if relevance_score < threshold:
            vuln = bundle.vuln_id if bundle else str(self.requirement.get("vuln_id") or "UNKNOWN")
            if unknown and require_evidence:
                return (
                    "insufficient",
                    (
                        f"Insufficient researcher evidence for {vuln}: low relevance score ({relevance_score:.2f} < {threshold:.2f}). "
                        "Evidence does not align with requested vulnerability semantics."
                    ),
                )
            if not unknown:
                return (
                    "sufficient",
                    (
                        f"Low evidence relevance for {vuln} ({relevance_score:.2f} < {threshold:.2f}); using guard fallback mode "
                        "with static/minimal assertions."
                    ),
                )
        if unknown and require_evidence and confidence == "low":
            vuln = bundle.vuln_id if bundle else str(self.requirement.get("vuln_id") or "UNKNOWN")
            policy = self._low_confidence_unknown_policy()
            if policy == "fail_closed":
                return (
                    "insufficient",
                    (
                        f"Insufficient researcher evidence for {vuln}: low-confidence unknown evidence "
                        f"(score={relevance_score:.2f}, threshold={threshold:.2f}). "
                        "policy.guard.low_confidence_unknown_policy=fail_closed."
                    ),
                )
            if policy == "guard_fallback":
                return (
                    "sufficient",
                    (
                        f"Low-confidence unknown evidence for {vuln} (score={relevance_score:.2f}, threshold={threshold:.2f}); "
                        "using guard fallback mode due to policy.guard.low_confidence_unknown_policy=guard_fallback."
                    ),
                )
            return (
                "sufficient",
                (
                    f"Low-confidence unknown evidence for {vuln} (score={relevance_score:.2f}, threshold={threshold:.2f}); "
                    "reviewer should surface this as a confidence warning."
                ),
            )
        return "sufficient", ""

    def _score_evidence_relevance(
        self,
        bundle: VulnBundle | None,
        search_hits: List[SearchResult],
    ) -> Dict[str, Any]:
        if not search_hits:
            return {
                "score": 0.0,
                "threshold": self._relevance_threshold(bundle),
                "profile": {},
                "coverage": 0.0,
                "remote_hit_count": 0,
                "hits": [],
            }

        profile = self._relevance_profile(bundle)
        overall_matches = {
            "family": False,
            "stack": False,
            "exploit": False,
            "input_vector": False,
            "sink": False,
            "exploit_precondition": False,
        }
        per_hit: List[Dict[str, Any]] = []
        remote_hits = 0
        negative_hits = 0
        for hit in search_hits:
            text = self._search_hit_text(hit)
            query_plan_entry = self._query_plan_index.get(str(hit.query or "").strip()) or {}
            expected_evidence_type = str(query_plan_entry.get("evidence_type") or "").strip().lower()
            evidence_type = self._classify_evidence_type(hit)
            matched = {
                "family_terms": self._matched_terms(text, profile.get("family_terms") or []),
                "stack_terms": self._matched_terms(text, profile.get("stack_terms") or []),
                "exploit_terms": self._matched_terms(text, profile.get("exploit_terms") or []),
                "negative_terms": self._matched_terms(text, profile.get("negative_terms") or []),
                "input_vector": self._matched_terms(
                    text,
                    profile.get("semantic_terms", {}).get("input_vector") or [],
                ),
                "sink": self._matched_terms(
                    text,
                    profile.get("semantic_terms", {}).get("sink") or [],
                ),
                "exploit_precondition": self._matched_terms(
                    text,
                    profile.get("semantic_terms", {}).get("exploit_precondition") or [],
                ),
            }
            score = 0.0
            if matched["family_terms"]:
                score += 0.35
                overall_matches["family"] = True
            if matched["stack_terms"]:
                score += 0.15
                overall_matches["stack"] = True
            if matched["exploit_terms"]:
                score += 0.10
                overall_matches["exploit"] = True
            for bucket in ("input_vector", "sink", "exploit_precondition"):
                if matched[bucket]:
                    score += 0.10
                    overall_matches[bucket] = True
            if evidence_type in {"advisory", "writeup", "reference_impl"}:
                score += 0.03
            if expected_evidence_type and evidence_type == expected_evidence_type:
                score += 0.05
            if str(hit.source or "").strip().lower() == "remote":
                remote_hits += 1
                score += 0.05
            negative_penalty = 0.0
            semantic_match = any(
                matched[bucket]
                for bucket in ("family_terms", "exploit_terms", "input_vector", "sink", "exploit_precondition")
            )
            if matched["negative_terms"] and not semantic_match:
                negative_penalty += min(0.20, 0.05 * len(matched["negative_terms"]))
            if matched["stack_terms"] and not semantic_match:
                negative_penalty += 0.05
            if negative_penalty > 0:
                negative_hits += 1
            score = max(0.0, score - negative_penalty)
            per_hit.append(
                {
                    "title": str(hit.title or ""),
                    "url": str(hit.url or ""),
                    "source": str(hit.source or ""),
                    "evidence_type": evidence_type,
                    "query_target": expected_evidence_type or None,
                    "score": round(min(1.0, score), 3),
                    "negative_penalty": round(negative_penalty, 3),
                    "matched": matched,
                }
            )

        ranked_scores = sorted((float(item["score"]) for item in per_hit), reverse=True)
        strongest = ranked_scores[0] if ranked_scores else 0.0
        support = sum(ranked_scores[:2]) / min(2, len(ranked_scores)) if ranked_scores else 0.0
        active_categories = [
            key
            for key, enabled in (
                ("family", bool(profile.get("family_terms"))),
                ("stack", bool(profile.get("stack_terms"))),
                ("exploit", bool(profile.get("exploit_terms"))),
                ("input_vector", bool(profile.get("semantic_terms", {}).get("input_vector"))),
                ("sink", bool(profile.get("semantic_terms", {}).get("sink"))),
                (
                    "exploit_precondition",
                    bool(profile.get("semantic_terms", {}).get("exploit_precondition")),
                ),
            )
            if enabled
        ]
        coverage = (
            sum(1 for key in active_categories if overall_matches.get(key)) / len(active_categories)
            if active_categories
            else 0.0
        )
        remote_bonus = 0.05 if remote_hits else 0.0
        negative_ratio = (negative_hits / len(per_hit)) if per_hit else 0.0
        overall = min(
            1.0,
            max(0.0, (0.55 * strongest) + (0.20 * support) + (0.20 * coverage) + remote_bonus - (0.10 * negative_ratio)),
        )
        semantic_alignment = any(
            overall_matches.get(key)
            for key in ("family", "exploit", "input_vector", "sink", "exploit_precondition")
        )
        if self._bundle_is_unknown(bundle) and not semantic_alignment:
            overall = min(overall, max(0.0, self._relevance_threshold(bundle) - 0.05))
        return {
            "score": round(overall, 3),
            "threshold": self._relevance_threshold(bundle),
            "profile": profile,
            "coverage": round(coverage, 3),
            "remote_hit_count": remote_hits,
            "negative_hit_count": negative_hits,
            "negative_hit_ratio": round(negative_ratio, 3),
            "confidence": self._relevance_confidence(overall, coverage, negative_ratio),
            "hits": per_hit,
        }

    def _estimate_evidence_relevance(
        self,
        bundle: VulnBundle | None,
        search_hits: List[SearchResult],
    ) -> float:
        return float(self._score_evidence_relevance(bundle, search_hits).get("score") or 0.0)

    def _allow_pattern_guidance(self, bundle: VulnBundle | None) -> bool:
        return not self._bundle_is_unknown(bundle)

    def _relevance_terms(self, bundle: VulnBundle | None) -> List[str]:
        return list(self._relevance_profile(bundle).get("family_terms") or [])

    def _relevance_profile(self, bundle: VulnBundle | None) -> Dict[str, Any]:
        vuln_id = str(bundle.vuln_id if bundle else self.requirement.get("vuln_id") or "").strip().lower()
        family_terms: List[str] = []
        exploit_terms: List[str] = []
        allow_pattern_guidance = self._allow_pattern_guidance(bundle)
        if vuln_id in {"cwe-89", "cwe_89"}:
            family_terms.extend(["sql injection", "sqli", "union select", "where id =", "or 1=1"])
            exploit_terms.extend(["or 1=1", "union select", "boolean-based"])
        elif vuln_id in {"cwe-352", "cwe_352"}:
            family_terms.extend(["csrf", "cross-site request forgery", "anti-csrf", "csrf token"])
            exploit_terms.extend(["same-site", "cross-site", "forgery"])
        elif vuln_id in {"cwe-22", "cwe_22"}:
            family_terms.extend(["path traversal", "directory traversal", "../", "/etc/passwd"])
            exploit_terms.extend(["../", "..\\", "/etc/passwd", "send_file", "open("])
        elif vuln_id in {"cwe-78", "cwe_78"}:
            family_terms.extend(["command injection", "shell injection", "os command"])
            exploit_terms.extend(["subprocess", "os.system", "shell=true", "command injection"])
        elif vuln_id in {"cwe-94", "cwe_94"}:
            family_terms.extend(["code injection", "eval injection", "exec injection"])
            exploit_terms.extend(["eval(", "exec(", "code injection"])
        elif vuln_id in {"cwe-79", "cwe_79"}:
            family_terms.extend(["cross-site scripting", "xss", "<script>"])
            exploit_terms.extend(["reflected xss", "<script>", "render_template_string"])
        elif vuln_id in {"cwe-918", "cwe_918"}:
            family_terms.extend(["ssrf", "server-side request forgery", "url fetch"])
            exploit_terms.extend(["requests.get", "169.254.169.254", "user-controlled url"])
        elif vuln_id in {"cwe-502", "cwe_502"}:
            family_terms.extend(["insecure deserialization", "deserialization", "pickle", "yaml.load"])
            exploit_terms.extend(["pickle.loads", "yaml.load", "untrusted deserialization"])
        elif allow_pattern_guidance:
            pattern_id = str(self.requirement.get("pattern_id") or "").strip().lower()
            if "sqli" in pattern_id or "sql" in pattern_id:
                family_terms.extend(["sql injection", "sqli", "sql", "sqlite"])
                exploit_terms.extend(["or 1=1", "union select", "string concat", "concatenation"])
            if "csrf" in pattern_id:
                family_terms.extend(["csrf", "cross-site request forgery"])
                exploit_terms.extend(["same-site", "csrf token"])
            if "path-traversal" in pattern_id:
                family_terms.extend(["path traversal", "directory traversal", "../"])
                exploit_terms.extend(["../", "/etc/passwd", "send_file", "open("])
            if "command-injection" in pattern_id:
                family_terms.extend(["command injection", "shell injection"])
                exploit_terms.extend(["subprocess", "os.system", "shell=true"])
            if "code-injection" in pattern_id:
                family_terms.extend(["code injection", "eval injection"])
                exploit_terms.extend(["eval(", "exec("])
            if "ssrf" in pattern_id:
                family_terms.extend(["ssrf", "server-side request forgery"])
                exploit_terms.extend(["requests.get", "169.254.169.254", "user-controlled url"])
            if "xss" in pattern_id:
                family_terms.extend(["cross-site scripting", "xss", "<script>"])
                exploit_terms.extend(["render_template_string", "<script>", "unescaped reflection"])
            if "deserialization" in pattern_id:
                family_terms.extend(["insecure deserialization", "deserialization"])
                exploit_terms.extend(["pickle.loads", "yaml.load", "jsonpickle.decode"])
            if "open-redirect" in pattern_id:
                family_terms.extend(["open redirect", "redirect target", "next parameter"])
                exploit_terms.extend(["redirect(", "location header", "external redirect"])
            if "template-injection" in pattern_id or "ssti" in pattern_id:
                family_terms.extend(["template injection", "server-side template injection", "ssti"])
                exploit_terms.extend(["render_template_string", "jinja2", "{{7*7}}", "template rendering"])

        raw_name = self._raw_vuln_label()
        if raw_name:
            family_terms.append(raw_name)
            normalized_label = re.sub(r"[^a-z0-9]+", " ", raw_name.lower()).strip()
            if normalized_label and normalized_label not in family_terms:
                family_terms.append(normalized_label)

        stack_terms: List[str] = []
        runtime = self.requirement.get("runtime") or {}
        runtime_db = runtime.get("db") if isinstance(runtime, dict) else None
        for value in (self.requirement.get("language"), self.requirement.get("framework"), runtime_db):
            if isinstance(value, str) and value.strip():
                stack_terms.append(value.strip())

        semantic_signature, _ = self._resolve_semantic_signature({"semantic_signature": {}}, bundle)
        return {
            "family_terms": self._dedupe_strings(family_terms),
            "stack_terms": self._dedupe_strings(stack_terms),
            "exploit_terms": self._dedupe_strings(exploit_terms),
            "negative_terms": self._negative_relevance_terms(
                vuln_id=vuln_id,
                pattern_id=str(self.requirement.get("pattern_id") or "") if allow_pattern_guidance else "",
            ),
            "semantic_terms": semantic_signature,
        }

    @staticmethod
    def _negative_relevance_terms(*, vuln_id: str, pattern_id: str) -> List[str]:
        normalized_vuln = str(vuln_id or "").strip().lower()
        normalized_pattern = str(pattern_id or "").strip().lower()
        if normalized_vuln in {"cwe-89", "cwe_89"} or "sql" in normalized_pattern:
            return [
                "csrf",
                "cross-site request forgery",
                "ssrf",
                "server-side request forgery",
                "remote code execution",
                "rce",
                "path traversal",
                "directory traversal",
                "yaml deserialization",
                "pickle deserialization",
                "command injection",
            ]
        if normalized_vuln in {"cwe-352", "cwe_352"} or "csrf" in normalized_pattern:
            return [
                "sql injection",
                "sqli",
                "path traversal",
                "remote code execution",
                "ssrf",
                "command injection",
            ]
        if normalized_vuln in {"cwe-22", "cwe_22"} or "path-traversal" in normalized_pattern:
            return [
                "sql injection",
                "sqli",
                "csrf",
                "cross-site request forgery",
                "ssrf",
                "server-side request forgery",
                "remote code execution",
                "yaml deserialization",
                "pickle deserialization",
            ]
        if normalized_vuln in {"cwe-918", "cwe_918"} or "ssrf" in normalized_pattern:
            return [
                "sql injection",
                "sqli",
                "csrf",
                "path traversal",
                "directory traversal",
                "command injection",
                "pickle deserialization",
            ]
        if "template-injection" in normalized_pattern or "ssti" in normalized_pattern:
            return [
                "sql injection",
                "sqli",
                "csrf",
                "cross-site request forgery",
                "ssrf",
                "server-side request forgery",
                "path traversal",
                "directory traversal",
                "yaml deserialization",
                "pickle deserialization",
            ]
        if "open-redirect" in normalized_pattern:
            return [
                "sql injection",
                "sqli",
                "csrf",
                "cross-site request forgery",
                "ssrf",
                "server-side request forgery",
                "path traversal",
                "directory traversal",
                "yaml deserialization",
                "pickle deserialization",
            ]
        return []

    @staticmethod
    def _relevance_confidence(score: float, coverage: float, negative_ratio: float) -> str:
        if score >= 0.70 and coverage >= 0.60 and negative_ratio <= 0.20:
            return "high"
        if score >= 0.45 and negative_ratio <= 0.50:
            return "medium"
        return "low"

    @staticmethod
    def _search_hit_text(hit: SearchResult) -> str:
        parts = [str(hit.title or ""), str(hit.snippet or ""), str(hit.url or "")]
        raw_content = getattr(hit, "raw_content", None)
        if isinstance(raw_content, str) and raw_content.strip():
            parts.append(raw_content[:1200])
        return " ".join(parts).lower()

    @staticmethod
    def _matched_terms(text: str, terms: List[str]) -> List[str]:
        lowered = str(text or "").lower()
        matched: List[str] = []
        for term in terms:
            token = str(term or "").strip().lower()
            if token and token in lowered and token not in matched:
                matched.append(token)
        return matched

    @staticmethod
    def _dedupe_strings(values: List[str]) -> List[str]:
        output: List[str] = []
        for value in values:
            token = str(value or "").strip().lower()
            if token and token not in output:
                output.append(token)
        return output

    def _raw_vuln_label(self) -> str:
        for key in ("vuln_name", "vulnerability_name", "weakness_name", "cwe_name", "vuln_label"):
            value = self.requirement.get(key)
            if not isinstance(value, str):
                continue
            cleaned = value.strip()
            if cleaned:
                return cleaned
        return ""

    def _relevance_threshold(self, bundle: VulnBundle | None) -> float:
        return 0.30 if self._bundle_is_unknown(bundle) else 0.35

    def _build_evidence_payload(self, search_hits: List[SearchResult]) -> List[Dict[str, Any]]:
        payload: List[Dict[str, Any]] = []
        for hit in search_hits:
            query_plan_entry = self._query_plan_index.get(str(hit.query or "").strip()) or {}
            evidence_type = self._classify_evidence_type(hit)
            source_authority = self._source_authority_for_hit(hit, evidence_type=evidence_type)
            item: Dict[str, Any] = {
                "query": hit.query or "",
                "query_target": str(query_plan_entry.get("evidence_type") or "").strip() or None,
                "evidence_type": evidence_type,
                "source_authority": source_authority,
                "source": hit.source,
                "title": hit.title,
                "provider": hit.provider,
                "url": hit.url,
                "snippet": hit.snippet,
                "retrieved_at": hit.retrieved_at or datetime.now(timezone.utc).isoformat(),
            }
            if hit.published:
                item["published"] = hit.published
            payload.append(item)
        return payload

    def _summarize_evidence_types(self, search_hits: List[SearchResult]) -> Dict[str, Any]:
        by_type: Dict[str, int] = {}
        by_query_target: Dict[str, int] = {}
        by_source_authority: Dict[str, int] = {}
        matched_target_count = 0
        for hit in search_hits:
            actual = self._classify_evidence_type(hit)
            if actual:
                by_type[actual] = by_type.get(actual, 0) + 1
            authority = self._source_authority_for_hit(hit, evidence_type=actual)
            by_source_authority[authority] = by_source_authority.get(authority, 0) + 1
            query_plan_entry = self._query_plan_index.get(str(hit.query or "").strip()) or {}
            expected = str(query_plan_entry.get("evidence_type") or "").strip()
            if expected:
                by_query_target[expected] = by_query_target.get(expected, 0) + 1
                if actual == expected:
                    matched_target_count += 1
        return {
            "by_type": by_type,
            "by_query_target": by_query_target,
            "by_source_authority": by_source_authority,
            "matched_target_count": matched_target_count,
            "query_count": len(self._query_plan_index),
            "hit_count": len(search_hits),
        }

    def _infer_tech_stack_candidates(
        self,
        search_hits: List[SearchResult],
        query_plan: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        candidates: Dict[str, Dict[str, Any]] = {}

        def add_candidate(
            language: str,
            framework: str,
            *,
            score: float,
            source: str,
        ) -> None:
            lang = str(language or "").strip().lower()
            fw = str(framework or "").strip().lower()
            if not lang or not fw:
                return
            stack_id = f"{lang}/{fw}"
            entry = candidates.get(stack_id)
            if entry is None:
                entry = {
                    "language": lang,
                    "framework": fw,
                    "stack_id": stack_id,
                    "score": 0.0,
                    "sources": [],
                }
                candidates[stack_id] = entry
            entry["score"] = round(float(entry.get("score") or 0.0) + max(0.0, float(score or 0.0)), 3)
            sources = entry.get("sources")
            if not isinstance(sources, list):
                sources = []
                entry["sources"] = sources
            if source and source not in sources:
                sources.append(source)

        explicit_language = str(self.requirement.get("language") or "").strip().lower()
        explicit_framework = str(self.requirement.get("framework") or "").strip().lower()
        if explicit_language and explicit_framework:
            add_candidate(explicit_language, explicit_framework, score=1.0, source="explicit_requirement")

        stack_hypotheses = query_plan.get("stack_hypotheses") if isinstance(query_plan.get("stack_hypotheses"), list) else []
        for index, entry in enumerate(stack_hypotheses):
            if not isinstance(entry, dict):
                continue
            add_candidate(
                str(entry.get("language") or ""),
                str(entry.get("framework") or ""),
                score=0.25 if index == 0 else 0.15,
                source=str(entry.get("source") or "stack_hypothesis"),
            )

        known_framework_markers = {
            "python/flask": ["flask"],
            "python/fastapi": ["fastapi", "uvicorn"],
        }
        stack_anchor_hints: set[str] = set()

        for hit in search_hits:
            query_text = str(hit.query or "").strip()
            query_plan_entry = self._query_plan_index.get(query_text) or {}
            expected_type = str(query_plan_entry.get("evidence_type") or "").strip().lower()
            text = " ".join(
                str(part or "").strip().lower()
                for part in (hit.title, hit.url, hit.snippet, hit.raw_content)
                if str(part or "").strip()
            )
            for stack_id, markers in known_framework_markers.items():
                language, framework = stack_id.split("/", 1)
                if expected_type == "stack_anchor" and any(marker in query_text.lower() for marker in (stack_id, framework)):
                    stack_anchor_hints.add(stack_id)
                marker_hits = sum(1 for marker in markers if marker in text)
                if marker_hits:
                    add_candidate(language, framework, score=0.25 + (0.1 * max(0, marker_hits - 1)), source="search_hit_text")
        for stack_id in sorted(stack_anchor_hints):
            language, framework = stack_id.split("/", 1)
            add_candidate(language, framework, score=0.05, source="stack_anchor_query")

        ranked = sorted(candidates.values(), key=lambda item: float(item.get("score") or 0.0), reverse=True)
        payload: List[Dict[str, Any]] = []
        for item in ranked:
            score = round(float(item.get("score") or 0.0), 3)
            confidence = "low"
            if score >= 0.9:
                confidence = "high"
            elif score >= 0.45:
                confidence = "medium"
            payload.append(
                {
                    "language": str(item.get("language") or "").strip().lower(),
                    "framework": str(item.get("framework") or "").strip().lower(),
                    "stack_id": str(item.get("stack_id") or "").strip().lower(),
                    "score": score,
                    "confidence": confidence,
                    "sources": list(item.get("sources") or []),
                }
            )
        return payload

    @staticmethod
    def _classify_evidence_type(hit: SearchResult) -> str:
        text = " ".join(
            str(part or "").strip().lower()
            for part in (hit.title, hit.url, hit.snippet)
            if str(part or "").strip()
        )
        if not text:
            return "reference"
        if (
            "github.com" in text
            or "gitlab" in text
            or "docker-compose" in text
            or "dockerfile" in text
            or ("vulnerable example" in text and "poc" in text)
        ):
            return "reference_impl"
        if any(token in text for token in ("writeup", "walkthrough", "medium.com", "blog", "exploit tutorial")):
            return "writeup"
        if any(token in text for token in ("cve-", "cwe-", "nvd", "owasp", "advisory", "vulnerability.circl", "security advisory")):
            return "advisory"
        if any(
            token in text
            for token in (
                "success signature",
                "flag token",
                "verification",
                "allow_redirects=false",
                "location header",
                "docker run",
                "python poc.py",
            )
        ):
            return "oracle_hint"
        return "reference"

    @staticmethod
    def _source_authority_for_hit(hit: SearchResult, *, evidence_type: str | None = None) -> str:
        text = " ".join(
            str(part or "").strip().lower()
            for part in (hit.title, hit.url, hit.snippet)
            if str(part or "").strip()
        )
        evidence_kind = str(evidence_type or "").strip().lower() or ResearcherService._classify_evidence_type(hit)
        if evidence_kind == "advisory":
            return "high"
        if any(
            token in text
            for token in (
                "nvd",
                "mitre",
                "owasp",
                "cwe.mitre",
                "security advisory",
                "docs.python.org",
                "fastapi.tiangolo.com",
                "flask.palletsprojects.com",
            )
        ):
            return "high"
        if evidence_kind in {"reference_impl", "oracle_hint", "writeup"}:
            return "medium"
        return "low"

    def _resolve_semantic_signature(
        self,
        report: Dict[str, Any],
        bundle: VulnBundle | None,
    ) -> Tuple[Dict[str, List[str]], List[str]]:
        report_signature = normalize_semantic_signature(
            report.get("semantic_signature") if isinstance(report, dict) else {}
        )
        inferred_signature = self._infer_semantic_signature(report, bundle)
        default_signature = normalize_semantic_signature(self._default_semantic_signature(bundle))
        normalized_vuln = self._normalized_vuln_id(bundle)
        pattern_signature = normalize_semantic_signature(
            self._pattern_semantic_signature(
                str(self.requirement.get("pattern_id") or ""),
                self._raw_vuln_label(),
            )
        )
        baseline_signature = normalize_semantic_signature(baseline_semantic_signature(normalized_vuln))
        if normalized_vuln.startswith("name-") and self._signature_has_terms(pattern_signature):
            return pattern_signature, ["pattern"]
        if self._signature_has_terms(baseline_signature):
            merged: Dict[str, List[str]] = {
                "input_vector": list(baseline_signature.get("input_vector") or []),
                "sink": list(baseline_signature.get("sink") or []),
                "exploit_precondition": list(baseline_signature.get("exploit_precondition") or []),
            }
            sources: List[str] = ["baseline"]
            if self._merge_known_family_signature(merged, report_signature, normalized_vuln):
                sources.append("report")
            if self._merge_known_family_signature(merged, inferred_signature, normalized_vuln):
                sources.append("heuristic")
            return merged, sources
        if self._signature_has_terms(pattern_signature):
            return pattern_signature, ["pattern"]
        sources: List[str] = []
        if self._signature_has_terms(report_signature):
            sources.append("report")
        if self._signature_has_terms(inferred_signature):
            sources.append("heuristic")
        if self._signature_has_terms(default_signature):
            sources.append("default")

        merged: Dict[str, List[str]] = {
            "input_vector": [],
            "sink": [],
            "exploit_precondition": [],
        }
        for bucket in merged:
            merged[bucket] = self._merge_semantic_bucket_values(
                report_signature.get(bucket) or [],
                inferred_signature.get(bucket) or [],
                default_signature.get(bucket) or [],
            )
        return merged, (sources or ["empty"])

    @staticmethod
    def _signature_has_terms(signature: Dict[str, List[str]]) -> bool:
        if not isinstance(signature, dict):
            return False
        return any(bool(signature.get(bucket)) for bucket in ("input_vector", "sink", "exploit_precondition"))

    @staticmethod
    def _merge_semantic_bucket_values(*groups: List[str]) -> List[str]:
        merged: List[str] = []
        for group in groups:
            if not isinstance(group, list):
                continue
            for value in group:
                if not isinstance(value, str):
                    continue
                token = value.strip()
                if token and token not in merged:
                    merged.append(token)
        return merged

    def _merge_known_family_signature(
        self,
        merged: Dict[str, List[str]],
        candidate: Dict[str, List[str]],
        vuln_id: str,
    ) -> bool:
        changed = False
        allowed_tags = family_canonical_tags(vuln_id)
        for bucket in ("input_vector", "sink", "exploit_precondition"):
            baseline_bucket = merged.get(bucket) or []
            values = candidate.get(bucket) if isinstance(candidate, dict) else []
            if not isinstance(values, list):
                continue
            for value in values:
                if not isinstance(value, str):
                    continue
                token = value.strip()
                if not token or token in baseline_bucket:
                    continue
                aliases = semantic_term_aliases(token)
                if aliases & allowed_tags:
                    baseline_bucket.append(token)
                    changed = True
                    continue
                lowered = token.lower()
                if any(lowered in item.lower() or item.lower() in lowered for item in baseline_bucket):
                    baseline_bucket.append(token)
                    changed = True
            merged[bucket] = baseline_bucket
        return changed

    def _normalized_vuln_id(self, bundle: VulnBundle | None) -> str:
        vuln_id = bundle.vuln_id if bundle else self.requirement.get("vuln_id")
        return normalize_vuln_id(str(vuln_id or ""))

    def _infer_semantic_signature(
        self,
        report: Dict[str, Any],
        bundle: VulnBundle | None,
    ) -> Dict[str, List[str]]:
        result: Dict[str, List[str]] = {
            "input_vector": [],
            "sink": [],
            "exploit_precondition": [],
        }
        if self._bundle_is_unknown(bundle):
            # Unsupported/open-world lanes must not inherit a known-family
            # semantic contract from incidental stack terms (for example
            # "sqlite3" or "cursor.execute") found in noisy evidence.
            return normalize_semantic_signature(result)
        corpus = self._semantic_inference_corpus(report, bundle)
        lowered = corpus.lower()
        allow_pattern_guidance = self._allow_pattern_guidance(bundle)
        pattern_id = str(self.requirement.get("pattern_id") or "").strip().lower() if allow_pattern_guidance else ""
        vuln_id = str(bundle.vuln_id if bundle else self.requirement.get("vuln_id") or "").strip().lower()
        raw_vuln_label = self._raw_vuln_label().strip().lower()
        pattern_signature = normalize_semantic_signature(
            self._pattern_semantic_signature(pattern_id, raw_vuln_label)
        )
        explicit_pattern_family = self._signature_has_terms(pattern_signature)

        def add(bucket: str, *values: str) -> None:
            bucket_values = result[bucket]
            for value in values:
                token = str(value or "").strip()
                if token and token not in bucket_values:
                    bucket_values.append(token)

        def contains_any(tokens: List[str]) -> bool:
            return any(token in lowered for token in tokens)

        for bucket in ("input_vector", "sink", "exploit_precondition"):
            add(bucket, *(pattern_signature.get(bucket) or []))

        is_sqli = (
            vuln_id in {"cwe-89", "cwe_89"}
            or "sqli" in pattern_id
            or "sql" in pattern_id
            or contains_any(
                [
                    "sql injection",
                    "sqli",
                    "union select",
                    "sqlite3",
                    "cursor.execute",
                    "sql query",
                    "or 1=1",
                ]
            )
        )
        if is_sqli:
            add("input_vector", "request.args", "query parameter", "user-controlled request parameter")
            add("sink", "cursor.execute", "execute(", "SQL query execution")
            add(
                "exploit_precondition",
                "string concatenation",
                "input concatenated/interpolated into SQL sink",
                "or 1=1",
            )

        is_csrf = (
            vuln_id in {"cwe-352", "cwe_352"}
            or "csrf" in pattern_id
            or contains_any(
                [
                    "csrf",
                    "cross-site request forgery",
                    "cookie-authenticated session",
                    "same-site",
                ]
            )
        )
        if is_csrf:
            add("input_vector", "cross-site request", "cookie-authenticated session")
            add("sink", "state-changing endpoint", "POST")
            add("exploit_precondition", "missing CSRF token validation", "csrf token")

        is_path_traversal = (
            vuln_id in {"cwe-22", "cwe_22"}
            or "path-traversal" in pattern_id
            or any(token in raw_vuln_label for token in ["path traversal", "directory traversal"])
        )
        if is_path_traversal:
            add("input_vector", "request.args", "path parameter", "filename")
            add("sink", "open(", "send_file", "send_from_directory")
            add("exploit_precondition", "../", "os.path.join", "path traversal")

        is_ssrf = (
            vuln_id in {"cwe-918", "cwe_918"}
            or "ssrf" in pattern_id
            or any(token in raw_vuln_label for token in ["ssrf", "server-side request forgery"])
        )
        if is_ssrf:
            add("input_vector", "request.args", "url parameter", "user-controlled url")
            add("sink", "requests.get", "urllib.request", "http client request")
            add("exploit_precondition", "server-side request forgery", "169.254.169.254")

        is_command_injection = (
            vuln_id in {"cwe-78", "cwe_78"}
            or "command-injection" in pattern_id
            or "command injection" in raw_vuln_label
        )
        if is_command_injection:
            add("input_vector", "request.args", "command parameter")
            add("sink", "subprocess", "os.system", "shell=True")
            add("exploit_precondition", "command injection", "user input in command")

        is_code_injection = (
            vuln_id in {"cwe-94", "cwe_94"}
            or "code-injection" in pattern_id
            or "code injection" in raw_vuln_label
        )
        if is_code_injection:
            add("input_vector", "request.args", "code parameter")
            add("sink", "eval(", "exec(")
            add("exploit_precondition", "code injection", "user input reaches eval")

        is_xss = (
            vuln_id in {"cwe-79", "cwe_79"}
            or "xss" in pattern_id
            or any(token in raw_vuln_label for token in ["xss", "cross-site scripting"])
        )
        if is_xss:
            add("input_vector", "request.args", "query parameter", "user input")
            add("sink", "render_template_string", "template response", "innerHTML")
            add("exploit_precondition", "<script>", "unescaped reflection", "cross-site scripting")

        is_open_redirect = (
            "open-redirect" in pattern_id
            or any(token in raw_vuln_label for token in ["open redirect", "unvalidated redirect"])
        )
        if is_open_redirect:
            add("input_vector", "request.args", "next parameter", "redirect target", "url parameter")
            add("sink", "redirect(", "location header", "http redirect sink")
            add("exploit_precondition", "open redirect", "unvalidated redirect target", "external redirect")

        is_deserialization = (
            vuln_id in {"cwe-502", "cwe_502"}
            or "deserialization" in pattern_id
            or "deserialization" in raw_vuln_label
        )
        if is_deserialization:
            add("input_vector", "request.data", "request.get_data", "serialized payload")
            add("sink", "pickle.loads", "yaml.load", "jsonpickle.decode")
            add("exploit_precondition", "untrusted deserialization", "attacker-controlled serialized input")

        if contains_any(["request.args", "query parameter", "get parameter", "id query param"]):
            add("input_vector", "request.args", "query parameter")
        if contains_any(["request.form", "form parameter"]):
            add("input_vector", "request.form", "form parameter")
        if contains_any(["request.json", "json body", "request body", "body parameter"]):
            add("input_vector", "request.json", "body parameter")
        if (not explicit_pattern_family) and contains_any(["cursor.execute", "execute(", "executescript(", "sql query", "sqlite3"]):
            add("sink", "cursor.execute", "execute(")
        if (not explicit_pattern_family) and contains_any(["string concatenation", "concat", "interpolat", "f-string", ".format(", "or 1=1"]):
            add("exploit_precondition", "string concatenation", "input concatenated/interpolated into SQL sink")

        return normalize_semantic_signature(result)

    def _semantic_inference_corpus(self, report: Dict[str, Any], bundle: VulnBundle | None) -> str:
        fragments: List[str] = []

        def collect(value: Any) -> None:
            if isinstance(value, str):
                token = value.strip()
                if token:
                    fragments.append(token)
                return
            if isinstance(value, list):
                for item in value:
                    collect(item)
                return
            if isinstance(value, dict):
                for key, item in value.items():
                    if str(key).strip().lower() in {"evidence", "references"}:
                        continue
                    collect(item)

        collect(
            {
                "intent": report.get("intent") if isinstance(report, dict) else None,
                "preconditions": report.get("preconditions") if isinstance(report, dict) else None,
                "minimal_repro_steps": report.get("minimal_repro_steps") if isinstance(report, dict) else None,
                "verification_spec": report.get("verification_spec") if isinstance(report, dict) else None,
                "failure_context": report.get("failure_context") if isinstance(report, dict) else None,
                "pocs": report.get("pocs") if isinstance(report, dict) else None,
                "tech_stack_candidates": report.get("tech_stack_candidates") if isinstance(report, dict) else None,
                "risks": report.get("risks") if isinstance(report, dict) else None,
                "semantic_signature": report.get("semantic_signature") if isinstance(report, dict) else None,
                "requirement_intent": self.requirement.get("intent"),
                "pattern_id": self.requirement.get("pattern_id") if self._allow_pattern_guidance(bundle) else None,
                "framework": self.requirement.get("framework"),
                "language": self.requirement.get("language"),
                "runtime": self.requirement.get("runtime"),
            }
        )
        return "\n".join(fragments)

    def _default_semantic_signature(self, bundle: VulnBundle | None) -> Dict[str, Any]:
        normalized = self._normalized_vuln_id(bundle) or "cwe-unknown"
        allow_pattern_guidance = self._allow_pattern_guidance(bundle)
        pattern_id = str(self.requirement.get("pattern_id") or "") if allow_pattern_guidance else ""
        registry_signature = fragment_semantic_signature(
            bundle.vuln_id if bundle else str(self.requirement.get("vuln_id") or normalized),
            pattern_id=pattern_id,
            raw_label=self._raw_vuln_label(),
        )
        if any(registry_signature.get(bucket) for bucket in ("input_vector", "sink", "exploit_precondition")):
            return registry_signature
        baseline = baseline_semantic_signature(normalized)
        if any(baseline.get(bucket) for bucket in ("input_vector", "sink", "exploit_precondition")):
            return baseline
        pattern_signature = self._pattern_semantic_signature(pattern_id, self._raw_vuln_label())
        if any(pattern_signature.get(bucket) for bucket in ("input_vector", "sink", "exploit_precondition")):
            return pattern_signature
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
        if normalized == "cwe-22":
            return {
                "input_vector": ["request.args", "path parameter"],
                "sink": ["open(", "send_file", "send_from_directory"],
                "exploit_precondition": ["../", "os.path.join", "path traversal"],
            }
        if normalized == "cwe-918":
            return {
                "input_vector": ["request.args", "url parameter", "user-controlled url"],
                "sink": ["requests.get", "urllib.request", "http client request"],
                "exploit_precondition": ["server-side request forgery", "169.254.169.254"],
            }
        if normalized == "cwe-78":
            return {
                "input_vector": ["request.args", "command parameter"],
                "sink": ["subprocess", "os.system", "shell=True"],
                "exploit_precondition": ["command injection", "user input in command"],
            }
        if normalized == "cwe-94":
            return {
                "input_vector": ["request.args", "code parameter"],
                "sink": ["eval(", "exec("],
                "exploit_precondition": ["code injection", "user input reaches eval"],
            }
        if normalized == "cwe-79":
            return {
                "input_vector": ["request.args", "query parameter", "user input"],
                "sink": ["render_template_string", "template response"],
                "exploit_precondition": ["<script>", "unescaped reflection", "cross-site scripting"],
            }
        if normalized == "cwe-502":
            return {
                "input_vector": ["request.data", "serialized payload"],
                "sink": ["pickle.loads", "yaml.load", "jsonpickle.decode"],
                "exploit_precondition": ["untrusted deserialization", "attacker-controlled serialized input"],
            }
        return {
            "input_vector": [],
            "sink": [],
            "exploit_precondition": [],
        }

    @staticmethod
    def _pattern_semantic_signature(pattern_id: str, raw_vuln_label: str) -> Dict[str, List[str]]:
        normalized_pattern = str(pattern_id or "").strip().lower()
        normalized_label = str(raw_vuln_label or "").strip().lower()
        if (
            "template-injection" in normalized_pattern
            or "ssti" in normalized_pattern
            or any(
                token in normalized_label
                for token in ("template injection", "ssti", "server side template injection", "server-side template injection")
            )
        ):
            return {
                "input_vector": [
                    "request.args",
                    "request.form",
                    "query parameter",
                    "user-controlled request parameter",
                ],
                "sink": [
                    "render_template_string",
                    "jinja2 template rendering from string",
                ],
                "exploit_precondition": [
                    "user input is embedded into template source string (concatenation/interpolation)",
                    "template string is rendered server-side without escaping/sandboxing",
                ],
            }
        if "open-redirect" in normalized_pattern or "open redirect" in normalized_label:
            return {
                "input_vector": [
                    "request.args",
                    "next parameter",
                    "redirect target",
                    "url parameter",
                ],
                "sink": [
                    "redirect(",
                    "location header",
                    "http redirect sink",
                ],
                "exploit_precondition": [
                    "open redirect",
                    "unvalidated redirect target",
                    "external redirect",
                ],
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

        filename = f"{rule_filename_for_vuln_id(bundle.vuln_id)}.yaml"
        path = self.runtime_rules_dir / filename
        path.write_text(yaml.safe_dump(rule, sort_keys=False, allow_unicode=True), encoding="utf-8")
        metadata_root = getattr(self, "metadata_root", None)
        if isinstance(metadata_root, Path):
            record_generated_runtime_asset(metadata_root, kind="runtime_rules", path=path)
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
        data = normalize_template_metadata(data)
        data["id"] = f"{bundle.vuln_id.lower()}-candidate"
        data["name"] = f"{bundle.vuln_id} candidate template"
        data = normalize_template_metadata(data)
        template_json.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        metadata_root = getattr(self, "metadata_root", None)
        if isinstance(metadata_root, Path):
            record_generated_runtime_asset(metadata_root, kind="runtime_templates", path=dest)
        return dest

    def _load_template_metadata(self, template_root: Path) -> Dict[str, Any]:
        template_json = template_root / "template.json"
        if not template_json.exists():
            return {}
        try:
            return normalize_template_metadata(json.loads(template_json.read_text(encoding="utf-8")))
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
        spec = extract_verification_spec(report, vuln_id=bundle.vuln_id)
        if not isinstance(spec, dict):
            return None
        normalized, _ = self._normalize_runtime_verification_spec(spec)
        return normalized

    @staticmethod
    def _derive_structured_success_contract(markers: List[str]) -> Dict[str, Any]:
        for marker in markers:
            if not isinstance(marker, str):
                continue
            candidate = marker.strip()
            if not candidate:
                continue
            match = re.fullmatch(
                r'"(?P<key>[^"]+)"\s*:\s*(?P<value>true|false|null|-?\d+(?:\.\d+)?|"(?:[^"\\]|\\.)*")',
                candidate,
                flags=re.IGNORECASE,
            )
            if not match:
                continue
            key = str(match.group("key") or "").strip()
            raw_value = str(match.group("value") or "").strip()
            if not key or not raw_value:
                continue
            try:
                if raw_value.lower() in {"true", "false", "null"}:
                    parsed_value = json.loads(raw_value.lower())
                else:
                    parsed_value = json.loads(raw_value)
            except Exception:
                continue
            canonical_marker = json.dumps({key: parsed_value}, ensure_ascii=False, separators=(",", ":"))[1:-1]
            return {
                "success_mode": "json",
                "json_success_key": key,
                "json_success_value": parsed_value,
                "canonical_marker": canonical_marker,
            }
        return {}

    def _rule_from_verification_spec(self, bundle: VulnBundle, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Construct a v2 rule mapping from a compact verification_spec."""

        vuln_id = bundle.vuln_id or "UNKNOWN"
        cwe = vuln_id.upper()
        spec, _ = self._normalize_runtime_verification_spec(spec)

        raw_markers = spec.get("success_text_markers") or []
        markers: List[str] = []
        if isinstance(raw_markers, list):
            for entry in raw_markers:
                if isinstance(entry, str) and entry:
                    markers.append(entry)
        elif isinstance(raw_markers, str) and raw_markers:
            markers.append(raw_markers)
        structured_success = self._derive_structured_success_contract(markers)
        canonical_marker = str(structured_success.get("canonical_marker") or "").strip()
        if canonical_marker and canonical_marker not in markers:
            markers = [canonical_marker, *markers]

        success_mode = str(spec.get("success_mode") or structured_success.get("success_mode") or "text")

        flag_token = spec.get("flag_token")
        flag_mode = str(spec.get("flag_mode") or "strict").lower()

        json_success_key = spec.get("json_success_key") or structured_success.get("json_success_key")
        json_success_value = (
            spec.get("json_success_value")
            if "json_success_value" in spec
            else structured_success.get("json_success_value")
        )
        json_flag_key = spec.get("json_flag_key")

        assertion_program = spec.get("assertion_program") or []
        if isinstance(assertion_program, str):
            # Treat free-form verifier code as an opaque hint. Pulling the first
            # quoted literal out of a Python program produces weak assertions such
            # as file paths, which harms runtime rule quality.
            assertion_program = []
        elif not isinstance(assertion_program, list):
            assertion_program = []
        if not assertion_program:
            assertion_program = [{"op": "contains", "string": marker} for marker in markers if marker]
            if isinstance(flag_token, str) and flag_token:
                assertion_program.append({"op": "contains", "string": flag_token})

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
            if ("json_success_value" in spec) or ("json_success_value" in structured_success):
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
            rule["patterns"].extend(self._service_side_rule_patterns(bundle))
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

    def _service_side_rule_patterns(self, bundle: VulnBundle) -> List[Dict[str, str]]:
        vuln_id = str(getattr(bundle, "vuln_id", "") or "").strip().upper()
        pattern_id = str(self.requirement.get("pattern_id") or "").strip().lower()
        raw_label = self._raw_vuln_label().strip().lower()

        def file_contains(token: str) -> Dict[str, str]:
            return {
                "type": "file_contains",
                "path": "{{service_entry}}",
                "contains": token,
            }

        tokens = service_side_file_contains_tokens(vuln_id, pattern_id=pattern_id, raw_label=raw_label)
        return [file_contains(token) for token in tokens]

    def _generate_candidate_template(self, bundle: VulnBundle) -> Path | None:
        def _coerce_bool(value: Any) -> bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.strip().lower() in {"1", "true", "yes", "on"}
            return bool(value)

        vuln_id = (bundle.vuln_id or "").strip().lower()
        if not vuln_id:
            return None
        if vuln_id.startswith("cwe_"):
            vuln_id = vuln_id.replace("_", "-", 1)
        if not vuln_id.startswith("cwe-") and "cwe" in vuln_id:
            vuln_id = vuln_id.replace("cwe", "cwe-", 1)
        runtime = self.requirement.get("runtime") if isinstance(self.requirement, dict) else {}
        runtime = runtime if isinstance(runtime, dict) else {}
        requested_db = str(runtime.get("db") or runtime.get("database") or "").strip().lower()
        allow_external_db = _coerce_bool(runtime.get("allow_external_db") or self.requirement.get("allow_external_db"))
        requested_pattern = str(self.requirement.get("pattern_id") or "").strip().lower()

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
            template_db = str(meta.get("db") or "").strip().lower()
            if requested_db and template_db and requested_db != template_db:
                continue
            requires_external_db = _coerce_bool(meta.get("requires_external_db"))
            if requires_external_db and not allow_external_db:
                continue
            try:
                score = float(meta.get("stability_score", 0.0))
            except Exception:
                score = 0.0
            pattern_id = str(meta.get("pattern_id") or "").strip().lower()
            if requested_pattern and pattern_id and requested_pattern == pattern_id:
                score += 1.0
            if best is None or score > best[0]:
                best = (score, meta_path.parent)

        if not best:
            return None
        return self._write_candidate_template(bundle, best[1])


__all__ = ["ResearcherService"]
