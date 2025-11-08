"""Researcher microservice orchestrating ReAct-style retrieval."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from common.llm import LLMClient
from common.logging import get_logger
from common.paths import ensure_dir
from common.plan import load_plan
from common.prompts import build_researcher_prompt
from common.run_matrix import VulnBundle, bundle_requirement, metadata_dir_for_bundle
from common.variability import VariationManager
from orchestrator.plugins import ReactLoop, ReactSpan
from rag.static_loader import load_static_context
from rag.tools import SearchResult, WebSearchTool

LOGGER = get_logger(__name__)


class ResearcherService:
    """Produces researcher_report.json aligned with docs/schemas/researcher_report.md."""

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
        base_requirement = self.plan["requirement"]
        self.requirement = bundle_requirement(base_requirement, bundle) if bundle else base_requirement
        self.variation_manager = VariationManager(self.plan.get("variation_key"), seed=self.requirement.get("seed"))
        self.profile = self.variation_manager.profile_for("researcher", override_mode=mode)
        model = (
            self.requirement.get("researcher_model")
            or self.requirement.get("model_version")
            or "gpt-4.1-mini"
        )
        self.llm = LLMClient(model, self.profile)
        self.react_loop = ReactLoop(sid)
        self.search_tool = WebSearchTool()
        self.search_limit = max(1, search_limit)

    def run(self) -> Path:
        snapshot = self._snapshot_id()
        rag_context = load_static_context(snapshot)
        queries = self.react_loop.queries_from_requirement(self.requirement)
        with self.react_loop.span(queries=queries) as span:
            search_hits = self._collect_search_results(queries, span=span)
            report = self._generate_report(rag_context, search_hits)
            report.setdefault("sid", self.sid)
            report.setdefault("trace_id", self.react_loop.trace_id)
            report.setdefault("retrieval_snapshot_id", snapshot)
            report.setdefault("failure_context", self.react_loop.failure_context)
            report["created_at"] = datetime.now(timezone.utc).isoformat()
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
        for query in queries:
            new_hits = self.search_tool.search(query, limit=self.search_limit)
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
                "Researcher output is not valid JSON. Ensure docs/schemas/researcher_report.md is followed.\n"
                f"Snippet: {snippet}"
            ) from exc
        if not isinstance(report, dict):
            raise RuntimeError("Researcher output must be a JSON object per schema.")
        return report

    def _write_report(self, report: Dict[str, Any]) -> Path:
        path = self.metadata_dir / "researcher_report.json"
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return path


__all__ = ["ResearcherService"]
