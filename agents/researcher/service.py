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
            or "gpt-4.1-mini"
        )
        self.llm = LLMClient(model, self.profile)
        self.react_loop = ReactLoop(sid)
        self.search_tool = WebSearchTool()
        self.search_limit = max(1, search_limit)
        self._last_report: Dict[str, Any] | None = None

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
            self._last_report = report
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

        spec = self._extract_verification_spec(bundle)
        if has_static and isinstance(spec, dict) and not bool(spec.get("override_static")):
            # Avoid overriding stable, repo-maintained rule contracts unless
            # the report explicitly opts into it.
            spec = None

        if spec:
            try:
                return self._rule_from_verification_spec(bundle, spec)
            except Exception as exc:  # pragma: no cover - defensive
                LOGGER.warning("Failed to build rule from verification_spec for %s: %s", bundle.vuln_id, exc)

        raw_rule = static_rule if has_static else (load_rule(bundle.vuln_id) or {})
        success_signature = str(raw_rule.get("success_signature") or "Exploit SUCCESS").strip() or "Exploit SUCCESS"
        flag_token = str(raw_rule.get("flag_token") or "").strip()
        strict_flag = bool(raw_rule.get("strict_flag", True)) if flag_token else False
        output_cfg = raw_rule.get("output") or {}
        json_cfg = output_cfg.get("json") if isinstance(output_cfg, dict) else None
        if not isinstance(json_cfg, dict):
            json_cfg = {}
        spec: Dict[str, Any] = {
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
        return self._rule_from_verification_spec(bundle, spec)

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
