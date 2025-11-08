"""Generator microservice implementation for TODO 14.

This module introduces a template registry + self-consistency voting based on
``workspaces/templates/sqli/*`` as defined in
docs/milestones/todo_13-15_code_plan.md.
"""
from __future__ import annotations

import json
import random
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

from common.config import DecodingProfile, get_decoding_profile
from common.llm import LLMClient
from common.logging import get_logger
from common.paths import ensure_dir, get_metadata_dir, get_repo_root
from common.prompts import build_generator_prompt
from rag import latest_failure_context, load_static_context

LOGGER = get_logger(__name__)


def _load_plan(sid: str) -> Dict[str, Any]:
    plan_path = get_metadata_dir(sid) / "plan.json"
    if not plan_path.exists():
        raise FileNotFoundError(f"Plan not found for {sid}")
    return json.loads(plan_path.read_text(encoding="utf-8"))


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


class TemplateRegistry:
    """Discovers template directories and handles workspace materialization."""

    def __init__(self, root: Path | None = None) -> None:
        default_root = get_repo_root() / "workspaces" / "templates" / "sqli"
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
    ) -> None:
        self.sid = sid
        self.plan = _load_plan(sid)
        self.metadata_dir = _metadata_dir(self.plan)
        self.workspace = _workspace_dir(self.plan)
        self.requirement = self.plan["requirement"]
        self.variation = self.plan.get("variation_key", {})
        self.loop_index = self._read_loop_index()
        self.profile: DecodingProfile = get_decoding_profile(mode)
        model = self.requirement.get("model_version", "gpt-4.1-mini")
        self.llm = LLMClient(model, self.profile)
        self.registry = TemplateRegistry(template_root)

    def _read_loop_index(self) -> int:
        loop_path = self.metadata_dir / "loop_state.json"
        if not loop_path.exists():
            return 0
        data = json.loads(loop_path.read_text(encoding="utf-8"))
        return int(data.get("current_loop", 0))

    def run(self) -> None:
        rag_snapshot = self.requirement.get("rag_snapshot") or self.requirement.get("corpus_snapshot", "mvp-sample")
        rag_context = load_static_context(rag_snapshot)
        failure_context = latest_failure_context(self.sid)
        prompt_messages = build_generator_prompt(
            self.requirement,
            rag_context,
            failure_context=failure_context,
        )
        llm_notes = self.llm.generate(prompt_messages)
        (self.metadata_dir / "generator_llm_plan.md").write_text(llm_notes, encoding="utf-8")
        selection, candidates = self._select_template()
        written_files = self.registry.materialize(selection, self.workspace)
        self._write_metadata(selection, candidates, written_files, failure_context)

    def _select_template(self) -> Tuple[TemplateSpec, List[TemplateCandidate]]:
        seed = int(self.variation.get("pattern_pool_seed", 0)) + self.loop_index
        k = max(1, int(self.variation.get("self_consistency_k", 1)))
        candidates = self.registry.sample_candidates(seed=seed, k=k)
        votes: Dict[str, List[TemplateCandidate]] = {}
        for candidate in candidates:
            votes.setdefault(candidate.template.id, []).append(candidate)
        # Majority vote followed by best score tiebreaker.
        sorted_votes = sorted(
            votes.items(),
            key=lambda item: (
                len(item[1]),
                item[1][0].template.stability,
            ),
            reverse=True,
        )
        winning_id, _ = sorted_votes[0]
        tied = votes[winning_id]
        winner = max(tied, key=lambda candidate: candidate.score)
        return winner.template, candidates

    def _write_metadata(
        self,
        selection: TemplateSpec,
        candidates: List[TemplateCandidate],
        written_files: List[str],
        failure_context: str,
    ) -> None:
        candidates_path = self.metadata_dir / "generator_candidates.json"
        candidates_payload = [c.to_payload() for c in candidates]
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
        }
        summary_path = self.metadata_dir / "generator_template.json"
        summary_path.write_text(json.dumps(selection_payload, indent=2, ensure_ascii=False), encoding="utf-8")
        LOGGER.info("Generator template summary written to %s", summary_path)


__all__ = ["GeneratorService", "TemplateRegistry", "TemplateSpec"]
