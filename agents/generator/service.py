"""Generator microservice for synthesis/hybrid modes.

Extends the template registry and enforces guard rails defined in
docs/handbook.md (아키텍처/스키마 섹션).
"""
from __future__ import annotations

import json
import random
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from common.config import DecodingProfile
from common.llm import LLMClient
from common.logging import get_logger
from common.paths import ensure_dir, get_metadata_dir, get_repo_root
from common.plan import load_plan
from common.prompts import build_generator_prompt
from common.rules import load_rule
from common.run_matrix import (
    VulnBundle,
    bundle_requirement,
    metadata_dir_for_bundle,
    workspace_dir_for_bundle,
)
from common.variability import VariationManager
from rag import latest_failure_context, load_hints, load_static_context
from orchestrator.loop_controller import LoopController

from .synthesis import ManifestValidationError, SynthesisEngine, SynthesisLimits, SynthesisOutcome

LOGGER = get_logger(__name__)

DEFAULT_TEMPLATE_ENDPOINTS = {
    "cwe-89": {"method": "GET", "path": "/profile"},
    "cwe-352": {"method": "POST", "path": "/transfer"},
}

MYSQL_DRIVERS = {
    "pymysql",
    "mysqlclient",
    "mysql-connector",
    "mysql-connector-python",
}
POSTGRES_DRIVERS = {
    "psycopg2",
    "psycopg2-binary",
    "pg8000",
    "asyncpg",
}


def _metadata_dir(plan: Dict[str, Any]) -> Path:
    return ensure_dir(Path(plan["paths"]["metadata"]))


def _workspace_dir(plan: Dict[str, Any]) -> Path:
    return ensure_dir(Path(plan["paths"]["workspace"]))


@dataclass
class TemplateSpec:
    """Metadata for a template rooted under workspaces/templates/sqli."""

    id: str
    path: Path
    metadata: Dict[str, Any]

    @property
    def stability(self) -> float:
        return float(self.metadata.get("stability_score", 0.5))

    @property
    def pattern_id(self) -> str:
        return self.metadata.get("pattern_id", self.id)

    @property
    def requires_external_db(self) -> bool:
        return bool(self.metadata.get("requires_external_db", False))

    @property
    def db(self) -> str:
        return str(self.metadata.get("db") or "").lower()

    @property
    def tags(self) -> List[str]:
        raw = self.metadata.get("tags") or []
        if not isinstance(raw, list):
            return []
        return [str(x).strip().lower() for x in raw if isinstance(x, str) and x.strip()]


@dataclass
class TemplateCandidate:
    """Single candidate sampled during self-consistency."""

    template: TemplateSpec
    trial: int
    score: float

    def to_payload(self) -> Dict[str, Any]:
        payload = {
            "trial": self.trial,
            "template_id": self.template.id,
            "score": round(self.score, 3),
            "metadata": self.template.metadata,
        }
        return payload


@dataclass
class GeneratorContext:
    """Context shared across generator modes."""

    rag: str
    failure: str
    hints: str


class TemplateRegistry:
    """Discovers template directories and handles workspace materialization."""

    def __init__(self, root: Path | None = None) -> None:
        default_root = get_repo_root() / "workspaces" / "templates"
        self.root = root or default_root
        self.templates = self._discover()
        if not self.templates:
            raise RuntimeError(f"No templates found under {self.root}")

    def _discover(self) -> List[TemplateSpec]:
        templates: List[TemplateSpec] = []
        if not self.root.exists():
            return templates
        for metadata_file in self.root.rglob("template.json"):
            meta = json.loads(metadata_file.read_text(encoding="utf-8"))
            template_id = meta.get("id") or metadata_file.parent.name
            templates.append(
                TemplateSpec(
                    id=template_id,
                    path=metadata_file.parent / "app",
                    metadata=meta,
                )
            )
        return templates

    def sample_candidates(self, *, seed: int, k: int) -> List[TemplateCandidate]:
        rng = random.Random(seed)
        candidates: List[TemplateCandidate] = []
        for trial in range(1, k + 1):
            template = rng.choice(self.templates)
            noise = rng.uniform(0, 0.15)
            score = template.stability + noise
            candidates.append(TemplateCandidate(template=template, trial=trial, score=score))
        return candidates

    def materialize(self, template: TemplateSpec, destination: Path) -> List[str]:
        if destination.exists():
            shutil.rmtree(destination)
        ensure_dir(destination)
        if not template.path.exists():
            raise FileNotFoundError(f"Template payload missing: {template.path}")
        shutil.copytree(template.path, destination, dirs_exist_ok=True)
        written = sorted(str(path.relative_to(destination)) for path in destination.rglob("*") if path.is_file())
        LOGGER.info("Materialized template %s into %s", template.id, destination)
        return written


class GeneratorService:
    """High-level façade consumed by the CLI entry point."""

    def __init__(
        self,
        sid: str,
        mode: str = "deterministic",
        template_root: Path | None = None,
        *,
        plan: Dict[str, Any] | None = None,
        bundle: VulnBundle | None = None,
    ) -> None:
        self.sid = sid
        self.plan = plan or load_plan(sid)
        self.bundle = bundle
        self.metadata_dir = metadata_dir_for_bundle(self.plan, bundle) if bundle else _metadata_dir(self.plan)
        self.workspace = workspace_dir_for_bundle(self.plan, bundle) if bundle else _workspace_dir(self.plan)
        base_requirement = self.plan["requirement"]
        self.requirement = bundle_requirement(base_requirement, bundle) if bundle else base_requirement
        self.variation_manager = VariationManager(
            self.plan.get("variation_key"),
            seed=self.requirement.get("seed"),
        )
        self.variation = self.variation_manager.key
        self.user_deps = self._normalize_user_deps()
        self.loop_index = self._read_loop_index()
        self.profile: DecodingProfile = self.variation_manager.profile_for("generator", override_mode=mode)
        model = self.requirement.get("model_version", "gpt-4.1-mini")
        self.llm = LLMClient(model, self.profile)
        self.generator_mode = (self.requirement.get("generator_mode") or "hybrid").lower()
        self.synthesis_limits = SynthesisLimits.from_requirement(self.requirement)
        self._template_root = template_root
        self._registry: Optional[TemplateRegistry] = None
        loop_cfg = self.plan.get("loop", {"max_loops": 3})
        self.loop_controller = LoopController(self.sid, max_loops=int(loop_cfg.get("max_loops", 3)))

    def _read_loop_index(self) -> int:
        loop_path = self.metadata_dir / "loop_state.json"
        if not loop_path.exists():
            return 0
        data = json.loads(loop_path.read_text(encoding="utf-8"))
        return int(data.get("current_loop", 0))

    def _get_registry(self) -> TemplateRegistry:
        if self._registry is None:
            self._registry = TemplateRegistry(self._template_root)
        return self._registry

    def _stack_descriptor(self) -> str:
        parts: List[str] = []
        for key in ("language", "framework"):
            value = self.requirement.get(key)
            if value:
                parts.append(str(value))
        runtime = self.requirement.get("runtime") or {}
        if isinstance(runtime, dict):
            for key in ("db", "database", "data_store"):
                value = runtime.get(key)
                if value:
                    parts.append(str(value))
                    break
        for key in ("database", "db"):
            value = self.requirement.get(key)
            if value:
                parts.append(str(value))
                break
        return "-".join(part.replace(" ", "-").lower() for part in parts if part)

    def _allow_external_db(self) -> bool:
        runtime = self.requirement.get("runtime") or {}
        if isinstance(runtime, dict) and "allow_external_db" in runtime:
            return bool(runtime["allow_external_db"])
        if "allow_external_db" in self.requirement:
            return bool(self.requirement["allow_external_db"])
        # Default to False because executor runs with --network none.
        return False

    def _runtime_db(self) -> str:
        runtime = self.requirement.get("runtime") or {}
        for key in ("db", "database"):
            value = runtime.get(key)
            if value:
                return str(value).strip().lower()
        value = self.requirement.get("db") or self.requirement.get("database")
        if value:
            return str(value).strip().lower()
        return ""

    def _normalize_user_deps(self) -> List[str]:
        deps = self.requirement.get("user_deps") or []
        if not isinstance(deps, list):
            LOGGER.warning("user_deps must be a list of strings; ignoring %s", deps)
            return []
        normalized: List[str] = []
        for entry in deps:
            if isinstance(entry, str):
                value = entry.strip()
                if value:
                    normalized.append(value)
            else:
                LOGGER.warning("Ignoring non-string user_dep value: %s", entry)
        return normalized

    def _should_include_user_dep(self, dep: str) -> bool:
        dep_norm = dep.strip().lower()
        if not dep_norm:
            return False
        runtime_db = self._runtime_db()
        if dep_norm in MYSQL_DRIVERS:
            if runtime_db in {"mysql", "mariadb"}:
                return True
            if not runtime_db:
                return self._allow_external_db()
            LOGGER.info("Skipping MySQL driver dependency '%s' for runtime db=%s", dep, runtime_db or "unknown")
            return False
        if dep_norm in POSTGRES_DRIVERS:
            if runtime_db in {"postgres", "postgresql"}:
                return True
            if not runtime_db:
                return self._allow_external_db()
            LOGGER.info("Skipping PostgreSQL driver dependency '%s' for runtime db=%s", dep, runtime_db or "unknown")
            return False
        return True

    def _apply_user_deps_to_workspace(self) -> List[str]:
        if not self.user_deps:
            return []
        requirements_path = self.workspace / "requirements.txt"
        requirements_path.parent.mkdir(parents=True, exist_ok=True)
        existing: List[str] = []
        if requirements_path.exists():
            existing = [
                line.strip()
                for line in requirements_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        lower_seen = {line.lower() for line in existing}
        merged = list(existing)
        added: List[str] = []
        for dep in self.user_deps:
            if not self._should_include_user_dep(dep):
                continue
            key = dep.lower()
            if key in lower_seen:
                continue
            merged.append(dep)
            lower_seen.add(key)
            added.append(dep)
        if added:
            requirements_path.write_text("\n".join(merged) + "\n", encoding="utf-8")
            LOGGER.info("Applied user_deps to requirements.txt: %s", added)
        return added

    def _record_user_deps_metadata(self, added: List[str]) -> None:
        if not self.user_deps:
            return
        payload = {
            "user_deps_requested": self.user_deps,
            "user_deps_added": added,
        }
        path = self.metadata_dir / "user_deps.json"
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def _build_context(self) -> GeneratorContext:
        rag_snapshot = (
            self.requirement.get("rag_snapshot")
            or self.requirement.get("corpus_snapshot")
            or "mvp-sample"
        )
        rag_context = load_static_context(rag_snapshot)
        failure_context = latest_failure_context(self.sid)
        guard_hint = self._guard_prompt_hint()
        if guard_hint:
            failure_context = (failure_context + "\n" + guard_hint).strip()
        hints = ""
        if self.generator_mode in {"synthesis", "hybrid"}:
            cwe = self.requirement.get("vuln_id") or ""
            hints = load_hints(cwe, stack=self._stack_descriptor()) if cwe else ""
        return GeneratorContext(rag=rag_context, failure=failure_context, hints=hints)

    def _candidate_k(self) -> int:
        return self.variation_manager.self_consistency_k("generator")

    def run(self) -> None:
        context = self._build_context()
        self._ensure_loop_started()
        if self.generator_mode == "synthesis":
            self._run_synthesis_with_loops(context)
            return
        if self.generator_mode == "hybrid":
            try:
                self._run_synthesis_with_loops(context)
                return
            except ManifestValidationError as exc:
                LOGGER.warning(
                    "Synthesis guard rejected all candidates for %s; falling back to template. %s",
                    self.sid,
                    exc,
                )
            except Exception as exc:  # pragma: no cover - safety net
                LOGGER.warning("Hybrid synthesis failure (%s); using template path.", exc)
            self._run_template(context, mode_label="hybrid-template")
            return
        # In template mode, attempt a compatibility check first; if no viable
        # template exists for the requested vuln/runtime, fall back to LLM synthesis.
        if not self._has_viable_template():
            LOGGER.warning(
                "No viable template found for sid=%s (vuln=%s, db=%s). Falling back to synthesis.",
                self.sid,
                (self.requirement.get("vuln_id") or "").upper(),
                ((self.requirement.get("runtime") or {}).get("db") or "").lower(),
            )
            self._run_synthesis_with_loops(context)
            return
        self._run_template(context, mode_label="template")

    def _ensure_loop_started(self) -> None:
        if self.loop_controller.current_loop == 0:
            self.loop_controller.start_loop()

    def _run_synthesis_with_loops(self, context: GeneratorContext) -> None:
        while True:
            try:
                outcome = self._run_synthesis_once(context)
                added_user_deps = self._apply_user_deps_to_workspace()
                self._record_user_deps_metadata(added_user_deps)
                self.loop_controller.record_success(stage="GENERATOR", note="synthesis succeeded")
                LOGGER.info(
                    "Synthesis candidate #%s materialized %s files for %s",
                    outcome.selected.index,
                    len(outcome.written_files),
                    self.sid,
                )
                return
            except ManifestValidationError as exc:
                failure_meta = self._latest_generator_failure()
                reason = failure_meta.get("reason") or str(exc)
                fix_hint = failure_meta.get("fix_hint") or "Review generator_failures.jsonl and add missing deps."
                metadata = {
                    "missing_dependencies": failure_meta.get("missing_dependencies", []),
                    "suggested_dependencies": failure_meta.get("suggested_dependencies", []),
                }
                self.loop_controller.record_failure(
                    stage="GENERATOR",
                    reason=reason,
                    fix_hint=fix_hint,
                    blocking=True,
                    metadata=metadata,
                )
                if self.loop_controller.should_continue():
                    self.loop_controller.start_loop()
                    context = self._build_context()
                    continue
                raise

    def _run_synthesis_once(self, context: GeneratorContext) -> SynthesisOutcome:
        engine = SynthesisEngine(
            sid=self.sid,
            llm=self.llm,
            limits=self.synthesis_limits,
            workspace=self.workspace,
            metadata_dir=self.metadata_dir,
            mode=self.generator_mode,
            user_deps=self.user_deps,
        )
        return engine.run(
            requirement=self.requirement,
            rag_context=context.rag,
            hints=context.hints,
            failure_context=context.failure,
            candidate_k=self._candidate_k(),
            poc_template=self.requirement.get("poc_template"),
        )

    def _run_template(self, context: GeneratorContext, *, mode_label: str) -> None:
        prompt_messages = build_generator_prompt(
            self.requirement,
            context.rag,
            failure_context=context.failure,
        )
        llm_notes = self.llm.generate(prompt_messages)
        (self.metadata_dir / "generator_llm_plan.md").write_text(llm_notes, encoding="utf-8")
        selection, candidates = self._select_template()
        written_files = self._get_registry().materialize(selection, self.workspace)
        self._augment_workspace_if_needed(selection)
        added_user_deps = self._apply_user_deps_to_workspace()
        self._record_user_deps_metadata(added_user_deps)
        self._write_metadata(
            selection,
            candidates,
            written_files,
            context.failure,
            mode_label=mode_label,
            user_deps_added=added_user_deps,
        )
        self.loop_controller.record_success(stage="GENERATOR", note=f"template mode: {mode_label}")

    def _latest_generator_failure(self) -> Dict[str, Any]:
        path = self.metadata_dir / "generator_failures.jsonl"
        if not path.exists():
            return {}
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not lines:
            return {}
        try:
            return json.loads(lines[-1])
        except json.JSONDecodeError:
            return {}

    def _guard_prompt_hint(self) -> str:
        entry = self._latest_generator_failure()
        missing = entry.get("missing_dependencies") or []
        suggested = entry.get("suggested_dependencies") or []
        auto_patch = entry.get("auto_patch") or {}
        skipped = auto_patch.get("skipped") or []
        stdlib_skipped = [item.get("name") for item in skipped if item.get("reason") == "stdlib"]
        if not missing and not suggested:
            return ""
        unique_missing = sorted({dep for dep in missing if dep})
        unique_suggested = sorted({dep for dep in suggested if dep})
        parts: List[str] = []
        if unique_missing:
            parts.append(
                "Generator guard hint: declare and install the following dependencies in deps[] and requirements*.txt -> "
                + ", ".join(unique_missing)
            )
        if unique_suggested and unique_suggested != unique_missing:
            parts.append("LLM suggested dependencies: " + ", ".join(unique_suggested))
        if stdlib_skipped:
            parts.append(
                "Note: the following modules are stdlib and do not require pip installation -> "
                + ", ".join(sorted(set(stdlib_skipped)))
            )
        return "\n".join(parts)

    def _select_template(self) -> Tuple[TemplateSpec, List[TemplateCandidate]]:
        # Prefer templates matching vuln_id tags and runtime DB; respect external DB policy.
        allow_external = self._allow_external_db()
        req_vuln = str(self.requirement.get("vuln_id") or "").strip().lower()
        req_db = str(((self.requirement.get("runtime") or {}).get("db")) or "").strip().lower()
        req_pattern = str(self.requirement.get("pattern_id") or "").strip().lower()
        researcher_tags = self._researcher_hint_tags()

        all_templates = self._get_registry().templates
        scored: List[Tuple[float, TemplateSpec]] = []
        for t in all_templates:
            if not allow_external and t.requires_external_db:
                continue
            score = 0.0
            if req_vuln and req_vuln in t.tags:
                score += 3.0
            if req_db and req_db == t.db:
                score += 2.0
            if req_pattern and req_pattern == (t.pattern_id or "").lower():
                score += 1.0
            if researcher_tags:
                overlap = len(researcher_tags & set(t.tags))
                if overlap:
                    score += 0.5 * overlap
            # small tie-breaker on stability
            score += 0.1 * t.stability
            scored.append((score, t))

        # If nothing scored, fallback to sampling to keep legacy behavior
        if not scored:
            seed = self.variation_manager.pattern_seed_with_offset(self.loop_index)
            k = self._candidate_k()
            candidates = self._get_registry().sample_candidates(seed=seed, k=k)
            return candidates[0].template, candidates

        scored.sort(key=lambda x: x[0], reverse=True)
        best = scored[0][1]

        # For traceability, still emit candidate list using sampler
        seed = self.variation_manager.pattern_seed_with_offset(self.loop_index)
        k = self._candidate_k()
        candidates = self._get_registry().sample_candidates(seed=seed, k=k)
        return best, candidates

    def _has_viable_template(self) -> bool:
        allow_external = self._allow_external_db()
        req_vuln = str(self.requirement.get("vuln_id") or "").strip().lower()
        req_db = str(((self.requirement.get("runtime") or {}).get("db")) or "").strip().lower()
        if not req_vuln or not req_db:
            return False
        templates = self._get_registry().templates
        for t in templates:
            if not allow_external and t.requires_external_db:
                continue
            vuln_match = req_vuln in t.tags
            db_match = req_db == t.db
            if vuln_match and db_match:
                return True
        return False

    def _researcher_hint_tags(self) -> Set[str]:
        report_path = self.metadata_dir / "researcher_report.json"
        if not report_path.exists():
            return set()
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return set()
        tags: Set[str] = set()
        for key in ("preconditions", "tech_stack_candidates", "deps"):
            entries = report.get(key) or []
            if isinstance(entries, list):
                for entry in entries:
                    tags.update(self._normalize_hint_tokens(entry))
            elif isinstance(entries, str):
                tags.update(self._normalize_hint_tokens(entries))
        return tags

    @staticmethod
    def _normalize_hint_tokens(value: Any) -> Set[str]:
        if not isinstance(value, str):
            return set()
        tokens = {token.strip().lower() for token in re.split(r"[^a-zA-Z0-9]+", value) if token.strip()}
        return tokens

    def _write_metadata(
        self,
        selection: TemplateSpec,
        candidates: List[TemplateCandidate],
        written_files: List[str],
        failure_context: str,
        *,
        mode_label: str,
        user_deps_added: Optional[List[str]] = None,
    ) -> None:
        candidates_path = self.metadata_dir / "generator_candidates.json"
        candidates_payload = {
            "mode": mode_label,
            "candidates": [c.to_payload() for c in candidates],
        }
        candidates_path.write_text(json.dumps(candidates_payload, indent=2, ensure_ascii=False), encoding="utf-8")

        selection_payload = {
            "sid": self.sid,
            "template_id": selection.id,
            "pattern_id": selection.pattern_id,
            "requires_external_db": selection.requires_external_db,
            "variation_key": self.variation,
            "loop_index": self.loop_index,
            "failure_context": failure_context,
            "written_files": written_files,
            "user_deps_requested": self.user_deps,
            "user_deps_added": user_deps_added or [],
        }
        summary_path = self.metadata_dir / "generator_template.json"
        summary_path.write_text(json.dumps(selection_payload, indent=2, ensure_ascii=False), encoding="utf-8")
        LOGGER.info("Generator template summary written to %s", summary_path)

    def _augment_workspace_if_needed(self, selection: TemplateSpec) -> None:
        augmentation_cfg = self.requirement.get("augmentation") or {}
        enabled = augmentation_cfg.get("enabled")
        if enabled is False:
            LOGGER.info("Template augmentation disabled for %s", selection.id)
            return

        vuln_id = str(self.requirement.get("vuln_id") or "").strip().lower()
        rule = load_rule(vuln_id)
        if not rule:
            return
        success_signature = str(rule.get("success_signature") or "").strip()
        flag_token = str(rule.get("flag_token") or "").strip()
        if not success_signature and not flag_token:
            return

        markers_lines = ["# Verification markers", ""]
        if success_signature:
            markers_lines.append(f"- Success signature: `{success_signature}`")
        if flag_token:
            markers_lines.append(f"- Flag token: `{flag_token}`")
        markers_text = "\n".join(markers_lines) + "\n"
        markers_path = self.workspace / "MARKERS.md"
        if not markers_path.exists() or markers_path.read_text(encoding="utf-8") != markers_text:
            markers_path.write_text(markers_text, encoding="utf-8")
            LOGGER.info("Wrote marker hints to %s", markers_path)

        readme_path = self.workspace / "README.md"
        marker_block = ["## Verification markers", ""]
        if success_signature:
            marker_block.append(f"- PoC must print `{success_signature}` on success.")
        if flag_token:
            marker_block.append(
                "- Successful exploit should surface the flag token `{}`.".format(flag_token)
            )
        marker_block.append("")
        block_text = "\n".join(marker_block)

        if readme_path.exists():
            current = readme_path.read_text(encoding="utf-8")
        else:
            current = "# Template README\n\n"
        if block_text.strip() not in current:
            updated = current.rstrip() + "\n\n" + block_text + "\n"
            readme_path.write_text(updated, encoding="utf-8")
            LOGGER.info("Appended verification markers to %s", readme_path)

        self._ensure_poc_scaffold(vuln_id, success_signature, flag_token)

    def _ensure_poc_scaffold(
        self, vuln_id: str, success_signature: str, flag_token: str
    ) -> None:
        poc_path = self.workspace / "poc.py"
        if poc_path.exists():
            return

        endpoint = DEFAULT_TEMPLATE_ENDPOINTS.get(vuln_id, {"method": "GET", "path": "/"})
        method = endpoint.get("method", "GET").upper()
        path = endpoint.get("path", "/")

        content_lines = [
            "import argparse",
            "import sys",
            "from urllib.request import Request, urlopen",
            "from urllib.error import URLError, HTTPError",
            "",
            "SUCCESS_SIGNATURE = " + repr(success_signature or "Exploit SUCCESS"),
            "FLAG_TOKEN = " + repr(flag_token or ""),
            "PATH = " + repr(path),
            "METHOD = " + repr(method),
            "",
            "def exploit(base_url: str) -> bool:",
            "    url = base_url.rstrip('/') + PATH",
            "    data = None",
            "    status = 0",
            "    try:",
            "        req = Request(url, method=METHOD)",
            "        with urlopen(req, timeout=5) as resp:",
            "            data = resp.read()",
            "            status = resp.status",
            "    except (HTTPError, URLError) as exc:",
            "        print(f'[auto] request failed: {exc}', file=sys.stderr)",
            "        return False",
            "    if status < 400:",
            "        print(SUCCESS_SIGNATURE)",
            "        if FLAG_TOKEN:",
            "            print(FLAG_TOKEN)",
            "        if data:",
            "            print(data.decode('utf-8', errors='ignore'))",
            "        return True",
            "    return False",
            "",
            "def main() -> None:",
            "    parser = argparse.ArgumentParser(description='Auto-generated PoC scaffold')",
            "    parser.add_argument('--base-url', default='http://127.0.0.1:5000')",
            "    args = parser.parse_args()",
            "    if exploit(args.base_url):",
            "        sys.exit(0)",
            "    print('[auto] scaffold did not trigger exploit', file=sys.stderr)",
            "    sys.exit(1)",
            "",
            "if __name__ == '__main__':",
            "    main()",
        ]
        poc_path.write_text("\n".join(content_lines) + "\n", encoding="utf-8")
        LOGGER.info("Created scaffold poc.py for %s", self.sid)


__all__ = ["GeneratorService", "TemplateRegistry", "TemplateSpec"]
