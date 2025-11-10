"""Researcher microservice orchestrating ReAct-style retrieval."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from common.llm import LLMClient
from common.logging import get_logger
from common.paths import ensure_dir, get_repo_root
from common.plan import load_plan
from common.prompts import build_researcher_prompt
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

    def _synthesize_candidates(self) -> Dict[str, List[Dict[str, Any]]]:
        targets = [self.bundle] if self.bundle else load_vuln_bundles(self.plan)
        output = {"rules": [], "templates": []}
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

    def _generate_candidate_rule(self, bundle: VulnBundle) -> Dict[str, Any] | None:
        vuln = (bundle.vuln_id or "").upper()
        if vuln == "CWE-89":
            return {
                "cwe": "CWE-89",
                "success_signature": "SQLi SUCCESS",
                "flag_token": "FLAG-sqli-demo-token",
                "strict_flag": True,
                "output": {"format": "auto"},
                "patterns": [
                    {"type": "file_contains", "path": "app.py", "contains": "SELECT"},
                    {"type": "poc_contains", "contains": "SQLi SUCCESS"},
                ],
            }
        if vuln == "CWE-352":
            return {
                "cwe": "CWE-352",
                "success_signature": "CSRF SUCCESS",
                "flag_token": "FLAG-csrf-demo-token",
                "strict_flag": True,
                "output": {"format": "auto"},
                "patterns": [
                    {"type": "file_contains", "path": "app.py", "contains": "@app.route('/transfer"},
                    {"type": "poc_contains", "contains": "CSRF SUCCESS"},
                ],
            }
        return {
            "cwe": bundle.vuln_id or "UNKNOWN",
            "success_signature": "Exploit SUCCESS",
            "flag_token": "FLAG-auto-token",
            "strict_flag": True,
            "output": {"format": "text"},
        }

    def _generate_candidate_template(self, bundle: VulnBundle) -> Path | None:
        vuln = (bundle.vuln_id or "").upper()
        mapping = {
            "CWE-89": Path("workspaces/templates/sqli/flask_sqlite_raw"),
            "CWE-352": Path("workspaces/templates/csrf/flask_sqlite_csrf"),
        }
        base = mapping.get(vuln)
        if not base:
            return None
        return self._write_candidate_template(bundle, base)


__all__ = ["ResearcherService"]
