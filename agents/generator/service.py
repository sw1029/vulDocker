"""Generator microservice for synthesis/hybrid modes.

Extends the template registry and enforces guard rails defined in
docs/handbook.md (아키텍처/스키마 섹션).
"""
from __future__ import annotations

import json
import os
import random
import re
import shutil
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from common.config import DecodingProfile
from common.guardrails import (
    SUPPORTED_GENERATOR_ASSERTION_OPS,
    enforce_generator_assertion_trust_boundary,
    load_guard_spec,
    write_guard_spec,
)
from common.hints import normalize_hint_payload
from common.llm import DEFAULT_LLM_MODEL, LLMClient, llm_execution_summary
from common.logging import get_logger
from common.name_only import is_name_driven_requirement, name_only_mode
from common.contracts import (
    build_generator_contract,
    executor_feasibility_summary,
    load_generator_contract,
    load_semantic_profile,
    write_generator_contract,
)
from common.paths import ensure_dir, get_metadata_dir, get_repo_root
from common.plan import load_plan
from common.prompts import build_generator_prompt, prompt_contract
from common.runtime_assets import record_generated_runtime_asset
from common.runtime_surface import derive_service_env, diagnose_runtime_surface
from common.rules import list_rules, load_rule, load_static_rule, rule_filename_for_vuln_id
from common.run_matrix import (
    VulnBundle,
    bundle_requirement,
    metadata_dir_for_bundle,
    workspace_dir_for_bundle,
)
from common.vuln_catalog import resolve_compiler_strategy
from common.variability import VariationManager
from rag import latest_failure_context, load_boilerplate, load_hints, load_static_context
from orchestrator.loop_controller import LoopController

from .synthesis import ManifestValidationError, SynthesisEngine, SynthesisLimits, SynthesisOutcome
from .compiler import CompilerResult, compile_manifest, compiler_fragment_spec
from .flask_fragment_registry import FLASK_FRAGMENT_REGISTRY
from .template_metadata import normalize_template_metadata

LOGGER = get_logger(__name__)

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


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


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
    def language(self) -> str:
        return str(self.metadata.get("language") or "").strip().lower()

    @property
    def framework(self) -> str:
        return str(self.metadata.get("framework") or "").strip().lower()

    @property
    def stack_id(self) -> str:
        value = str(self.metadata.get("stack_id") or "").strip().lower()
        if value:
            return value
        if self.language and self.framework:
            return f"{self.language}/{self.framework}"
        return ""

    @property
    def tags(self) -> List[str]:
        raw = self.metadata.get("tags") or []
        if not isinstance(raw, list):
            return []
        return [str(x).strip().lower() for x in raw if isinstance(x, str) and x.strip()]

    @property
    def scenario_type(self) -> str:
        return str(self.metadata.get("scenario_type") or "web-poc")

    @property
    def service_entry(self) -> str | None:
        value = self.metadata.get("service_entry")
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    @property
    def poc_entry(self) -> str | None:
        value = self.metadata.get("poc_entry")
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    @property
    def service_env(self) -> Dict[str, str]:
        raw = self.metadata.get("service_env")
        if not isinstance(raw, dict):
            return {}
        env: Dict[str, str] = {}
        for key, value in raw.items():
            if not isinstance(key, str):
                continue
            token = key.strip()
            if not token:
                continue
            env[token] = str(value)
        return env


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
    researcher_report: str
    guard_spec: str
    guard_spec_dict: Dict[str, Any]


class TemplateRegistry:
    """Discovers template directories and handles workspace materialization."""

    def __init__(self, root: Path | None = None, extra_roots: Optional[List[Path]] = None) -> None:
        default_root = get_repo_root() / "workspaces" / "templates"
        roots: List[Path] = [root or default_root]
        for extra in extra_roots or []:
            if extra and extra not in roots:
                roots.append(extra)
        self.roots = roots
        self.templates = self._discover()
        if not self.templates:
            raise RuntimeError(f"No templates found under {[str(r) for r in self.roots]}")

    def _discover(self) -> List[TemplateSpec]:
        templates: List[TemplateSpec] = []
        for base in self.roots:
            if not base.exists():
                continue
            for metadata_file in base.rglob("template.json"):
                meta = normalize_template_metadata(json.loads(metadata_file.read_text(encoding="utf-8")))
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
        single_attempt: bool = False,
    ) -> None:
        self.sid = sid
        self.plan = plan or load_plan(sid)
        self.bundle = bundle
        self.metadata_dir = metadata_dir_for_bundle(self.plan, bundle) if bundle else _metadata_dir(self.plan)
        self.metadata_root = ensure_dir(Path(self.plan["paths"]["metadata"]))
        self.runtime_rules_dir = ensure_dir(self.metadata_root / "runtime_rules")
        self.runtime_templates_dir = ensure_dir(self.metadata_root / "runtime_templates")
        self._register_runtime_rule_env(self.runtime_rules_dir)
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
        model = self.requirement.get("model_version", DEFAULT_LLM_MODEL)
        self.llm = LLMClient(model, self.profile)
        self.generator_mode = (self.requirement.get("generator_mode") or "synthesis").lower()
        self.synthesis_limits = SynthesisLimits.from_requirement(self.requirement)
        internal_loops_env = os.environ.get("VULD_GENERATOR_INTERNAL_LOOPS", "true").strip().lower()
        internal_loops_enabled = internal_loops_env not in {"0", "false", "no", "off"}
        self.single_attempt = bool(single_attempt) or not internal_loops_enabled
        self._template_root = template_root
        self._registry: Optional[TemplateRegistry] = None
        self._llm_prompt_invocations: Dict[str, int] = {}
        loop_cfg = self.plan.get("loop", {"max_loops": 3})
        self.loop_controller = LoopController(self.sid, max_loops=int(loop_cfg.get("max_loops", 3)))

    def _record_prompt_invocation(self, name: str) -> None:
        token = str(name or "").strip()
        if not token:
            return
        self._llm_prompt_invocations[token] = int(self._llm_prompt_invocations.get(token) or 0) + 1

    def _prompt_invocation_metadata(self) -> Dict[str, Any]:
        prompt_invocations = {
            str(key).strip(): int(value)
            for key, value in (self._llm_prompt_invocations or {}).items()
            if str(key).strip() and int(value) > 0
        }
        if not prompt_invocations:
            return {}
        return {
            "prompt_contracts": [prompt_contract(name) for name in prompt_invocations],
            "prompt_invocations": prompt_invocations,
        }

    def _retry_budget_context(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        loop_controller = getattr(self, "loop_controller", None)
        if loop_controller is not None:
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
        payload["single_attempt_mode"] = bool(getattr(self, "single_attempt", False))
        return payload

    def _read_loop_index(self) -> int:
        loop_path = self.metadata_dir / "loop_state.json"
        if not loop_path.exists():
            return 0
        data = json.loads(loop_path.read_text(encoding="utf-8"))
        return int(data.get("current_loop", 0))

    def _register_runtime_rule_env(self, path: Path) -> None:
        import os

        if not path.exists():
            return
        env_key = "VULD_RUNTIME_RULE_DIRS"
        existing = os.environ.get(env_key, "")
        parts = [p for p in existing.split(os.pathsep) if p]
        path_str = str(path)
        if path_str not in parts:
            parts.append(path_str)
            os.environ[env_key] = os.pathsep.join(parts)
        override_key = "VULD_ALLOW_RUNTIME_RULE_OVERRIDE_STATIC"
        allow_override = bool((self.plan.get("policy") or {}).get("allow_runtime_rule_override_static", False))
        os.environ[override_key] = "true" if allow_override else "false"

    def _get_registry(self) -> TemplateRegistry:
        if self._registry is None:
            extras: List[Path] = []
            if self.generator_mode in {"template", "hybrid"} and self.runtime_templates_dir.exists():
                extras = [self.runtime_templates_dir]
            self._registry = TemplateRegistry(self._template_root, extra_roots=extras)
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

    def _name_only_mode(self) -> str:
        return name_only_mode(self.requirement if isinstance(self.requirement, dict) else {})

    def _is_name_driven_request(self) -> bool:
        return is_name_driven_requirement(self.requirement if isinstance(self.requirement, dict) else {})

    def _dynamic_eval_enabled(self) -> bool:
        policy = self.requirement.get("policy") if isinstance(self.requirement, dict) else {}
        if not isinstance(policy, dict):
            return False
        if _as_bool(policy.get("dynamic_eval", False)):
            return True
        return self._is_name_driven_request() and self._name_only_mode() in {"dynamic", "strict_dynamic"}

    def _dynamic_eval_allow_lower_bound_fallback(self) -> bool:
        policy = self.requirement.get("policy") if isinstance(self.requirement, dict) else {}
        if not isinstance(policy, dict):
            return False
        if self._is_name_driven_request() and self._name_only_mode() == "strict_dynamic":
            return False
        return _as_bool(policy.get("dynamic_eval_allow_lower_bound_fallback", False))

    def _resolved_contract_for_synthesis(self) -> Dict[str, Any]:
        contract = load_generator_contract(self.metadata_dir) or {}
        if not self._is_name_driven_request():
            return contract if isinstance(contract, dict) else {}
        vuln_id = str(self.requirement.get("vuln_id") or "").strip() or "UNKNOWN"
        bundle_slug = self.bundle.slug if getattr(self, "bundle", None) else ""
        sid = str(getattr(self, "sid", "") or vuln_id or "sid-preflight")
        generator_mode = str(getattr(self, "generator_mode", "") or "synthesis_preflight")
        preflight = build_generator_contract(
            sid=sid,
            vuln_id=vuln_id,
            metadata_dir=self.metadata_dir,
            workspace_dir=self.workspace if isinstance(getattr(self, "workspace", None), Path) else None,
            generator_mode=generator_mode,
            bundle_slug=bundle_slug,
            requirement=self.requirement,
        )
        if not isinstance(contract, dict) or not contract:
            return preflight if isinstance(preflight, dict) else {}
        merged = deepcopy(contract)
        for key in ("request_ir", "runtime_recipe", "exploit_oracle", "name_only_generation_spec", "executor_plan", "staged_synthesis"):
            existing = merged.get(key)
            candidate = preflight.get(key) if isinstance(preflight, dict) else None
            if isinstance(existing, dict) and existing:
                if key == "request_ir" and isinstance(candidate, dict):
                    combined = deepcopy(existing)
                    for nested_key, nested_value in candidate.items():
                        if nested_key not in combined:
                            combined[nested_key] = deepcopy(nested_value)
                    merged[key] = combined
                continue
            if isinstance(candidate, dict) and candidate:
                merged[key] = deepcopy(candidate)
        return merged

    def _requirement_for_synthesis(self) -> Dict[str, Any]:
        requirement = deepcopy(self.requirement) if isinstance(self.requirement, dict) else {}
        contract = self._resolved_contract_for_synthesis()
        for key in ("request_ir", "runtime_recipe", "exploit_oracle", "name_only_generation_spec", "executor_plan", "staged_synthesis"):
            payload = contract.get(key) if isinstance(contract.get(key), dict) else {}
            if payload:
                requirement[key] = deepcopy(payload)
        return requirement

    def _dynamic_eval_status_path(self) -> Path:
        return self.metadata_dir / "dynamic_eval.json"

    def _write_dynamic_eval_status(
        self,
        status: str,
        *,
        lower_bound_fallback_used: bool = False,
        fallback_path: str = "",
    ) -> None:
        payload = {
            "enabled": self._dynamic_eval_enabled(),
            "attempted": self._dynamic_eval_enabled(),
            "status": str(status or "").strip() or "unknown",
            "lower_bound_fallback_used": bool(lower_bound_fallback_used),
            "fallback_path": str(fallback_path or "").strip() or None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._dynamic_eval_status_path().write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _try_lower_bound_fallback_after_dynamic_eval(self, context: GeneratorContext) -> bool:
        if not self._dynamic_eval_allow_lower_bound_fallback():
            return False
        compiled = self._run_compiler_if_supported()
        if compiled:
            self._write_dynamic_eval_status(
                "lower_bound_recovered",
                lower_bound_fallback_used=True,
                fallback_path="compiler",
            )
            self.loop_controller.record_success(
                stage="GENERATOR",
                note=f"dynamic_eval lower-bound compiler fallback: {compiled.strategy}",
            )
            return True
        if self._has_viable_template():
            self._write_dynamic_eval_status(
                "lower_bound_recovered",
                lower_bound_fallback_used=True,
                fallback_path="template",
            )
            self._run_template(context, mode_label="dynamic-eval-template-fallback")
            return True
        return False

    def _researcher_report_for_prompt(self) -> str:
        path = self.metadata_dir / "researcher_report.json"
        if not path.exists():
            return ""
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return ""
        if not isinstance(report, dict):
            return ""
        static_rule = load_static_rule(self.requirement.get("vuln_id") or "") or {}
        has_static = bool(static_rule)
        keep_keys = [
            "vuln_id",
            "intent",
            "preconditions",
            "tech_stack_candidates",
            "family_hypothesis_summary",
            "evidence_relevance",
            "minimal_repro_steps",
            "pocs",
            "deps",
            "risks",
            "verification_spec",
        ]
        trimmed: Dict[str, Any] = {}
        for key in keep_keys:
            value = report.get(key)
            if value in (None, "", [], {}):
                continue
            if key == "verification_spec" and has_static and isinstance(value, dict):
                allow_full_override = bool(
                    (self.plan.get("policy") or {}).get("allow_runtime_rule_override_static", False)
                )
                if (not allow_full_override) or (not bool(value.get("override_static"))):
                    # Prevent static contract drift in synthesis prompts unless policy explicitly allows full override.
                    continue
            trimmed[key] = value
        if not trimmed:
            return ""
        return json.dumps(trimmed, indent=2, ensure_ascii=False)

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
            boilerplate = load_boilerplate(stack=self._stack_descriptor())
            if boilerplate:
                hints = (hints + "\n\n" + boilerplate).strip() if hints else boilerplate
        researcher_report = self._researcher_report_for_prompt()
        guard_spec_dict = self._load_guard_spec_dict()
        guard_spec_text = json.dumps(guard_spec_dict, indent=2, ensure_ascii=False) if guard_spec_dict else ""
        return GeneratorContext(
            rag=rag_context,
            failure=failure_context,
            hints=hints,
            researcher_report=researcher_report,
            guard_spec=guard_spec_text,
            guard_spec_dict=guard_spec_dict,
        )

    def _candidate_k(self) -> int:
        return self.variation_manager.self_consistency_k("generator")

    def run(self) -> None:
        context = self._build_context()
        self._ensure_loop_started()
        dynamic_eval = self._dynamic_eval_enabled()
        if dynamic_eval:
            self._write_dynamic_eval_status("started")
        if self.generator_mode == "synthesis":
            if not dynamic_eval:
                compiled = self._run_compiler_if_supported()
                if compiled:
                    self.loop_controller.record_success(stage="GENERATOR", note=f"compiler path: {compiled.strategy}")
                    return
            try:
                outcome = self._run_synthesis_with_loops(context)
                if dynamic_eval:
                    self._write_dynamic_eval_status(self._dynamic_eval_status_for_outcome(outcome))
            except Exception:
                if dynamic_eval and self._try_lower_bound_fallback_after_dynamic_eval(context):
                    return
                if dynamic_eval:
                    self._write_dynamic_eval_status("dynamic_failed")
                raise
            return
        if self.generator_mode == "hybrid":
            if not dynamic_eval:
                compiled = self._run_compiler_if_supported()
                if compiled:
                    self.loop_controller.record_success(stage="GENERATOR", note=f"compiler path: {compiled.strategy}")
                    return
            try:
                outcome = self._run_synthesis_with_loops(context)
                if dynamic_eval:
                    self._write_dynamic_eval_status(self._dynamic_eval_status_for_outcome(outcome))
                return
            except ManifestValidationError as exc:
                if dynamic_eval and not self._dynamic_eval_allow_lower_bound_fallback():
                    self._write_dynamic_eval_status("dynamic_failed")
                    raise
                if not self._has_compatible_template():
                    LOGGER.warning(
                        "Synthesis guard rejected all candidates for %s and no compatible template exists; preserving failure. %s",
                        self.sid,
                        exc,
                    )
                    if dynamic_eval and self._try_lower_bound_fallback_after_dynamic_eval(context):
                        return
                    if dynamic_eval:
                        self._write_dynamic_eval_status("dynamic_failed")
                    raise
                LOGGER.warning(
                    "Synthesis guard rejected all candidates for %s; falling back to compatible template. %s",
                    self.sid,
                    exc,
                )
            except Exception as exc:  # pragma: no cover - safety net
                if dynamic_eval and not self._dynamic_eval_allow_lower_bound_fallback():
                    self._write_dynamic_eval_status("dynamic_failed")
                    raise
                if not self._has_compatible_template():
                    LOGGER.warning(
                        "Hybrid synthesis failure (%s) and no compatible template exists for %s; preserving failure.",
                        exc,
                        self.sid,
                    )
                    if dynamic_eval and self._try_lower_bound_fallback_after_dynamic_eval(context):
                        return
                    if dynamic_eval:
                        self._write_dynamic_eval_status("dynamic_failed")
                    raise
                LOGGER.warning("Hybrid synthesis failure (%s); using compatible template path.", exc)
            if dynamic_eval:
                if self._try_lower_bound_fallback_after_dynamic_eval(context):
                    return
                self._write_dynamic_eval_status("dynamic_failed")
                raise RuntimeError(
                    "dynamic_eval lower-bound fallback was allowed, but no viable compiler/template path remained"
                )
            self._run_template(context, mode_label="hybrid-template")
            return
        if dynamic_eval:
            try:
                outcome = self._run_synthesis_with_loops(context)
                self._write_dynamic_eval_status(self._dynamic_eval_status_for_outcome(outcome))
                return
            except Exception:
                if self._try_lower_bound_fallback_after_dynamic_eval(context):
                    return
                self._write_dynamic_eval_status("dynamic_failed")
                raise
        # In template mode, attempt a compatibility check first; if no viable
        # template exists for the requested vuln/runtime, fall back to LLM synthesis.
        if not self._has_viable_template():
            LOGGER.warning(
                "No viable template found for sid=%s (vuln=%s, db=%s). Falling back to synthesis.",
                self.sid,
                (self.requirement.get("vuln_id") or "").upper(),
                ((self.requirement.get("runtime") or {}).get("db") or "").lower(),
            )
            compiled = self._run_compiler_if_supported()
            if compiled:
                self.loop_controller.record_success(stage="GENERATOR", note=f"compiler path: {compiled.strategy}")
                return
            self._run_synthesis_with_loops(context)
            return
        self._run_template(context, mode_label="template")

    def _run_compiler_if_supported(self) -> Optional[CompilerResult]:
        compiler_cfg = self.requirement.get("compiler") if isinstance(self.requirement, dict) else {}
        if isinstance(compiler_cfg, dict) and "enabled" in compiler_cfg and not _as_bool(compiler_cfg.get("enabled")):
            LOGGER.info("Compiler path disabled by requirement for %s", self.sid)
            return None
        if _as_bool(self.requirement.get("disable_compiler", False)):
            LOGGER.info("Compiler path disabled by legacy requirement flag for %s", self.sid)
            return None
        semantic_profile = load_semantic_profile(self.metadata_dir) or {}
        if not isinstance(semantic_profile, dict) or not semantic_profile:
            semantic_profile = self._seed_semantic_profile_for_compiler()
        if not isinstance(semantic_profile, dict):
            return None
        if semantic_profile.get("compiler_supported") is not True:
            return None
        result = compile_manifest(
            sid=self.sid,
            requirement=self.requirement,
            semantic_profile=semantic_profile,
        )
        if result is None:
            return None
        written_files = self._materialize_compiler_manifest(result.manifest)
        added_user_deps = self._apply_user_deps_to_workspace()
        self._record_user_deps_metadata(added_user_deps)
        self._write_compiler_records(result, written_files)
        self._write_compiler_runtime_rule(result)
        self._write_generator_contract(mode_label="compiler")
        LOGGER.info(
            "Compiler strategy %s materialized %s files for %s",
            result.strategy,
            len(written_files),
            self.sid,
        )
        return result

    def _seed_semantic_profile_for_compiler(self) -> Dict[str, Any]:
        vuln_id = str(self.requirement.get("vuln_id") or "").strip() or "UNKNOWN"
        slug = self.bundle.slug if self.bundle else ""
        payload = build_generator_contract(
            sid=self.sid,
            vuln_id=vuln_id,
            metadata_dir=self.metadata_dir,
            workspace_dir=None,
            generator_mode="compiler_seed",
            bundle_slug=slug,
            requirement=self.requirement,
        )
        write_generator_contract(self.metadata_dir, payload)
        profile = payload.get("semantic_profile")
        return profile if isinstance(profile, dict) else {}

    def _materialize_compiler_manifest(self, manifest: Dict[str, Any]) -> List[str]:
        if self.workspace.exists():
            shutil.rmtree(self.workspace)
        ensure_dir(self.workspace)
        written: List[str] = []
        for entry in manifest.get("files", []):
            if not isinstance(entry, dict):
                continue
            rel_path = Path(str(entry.get("path") or "").strip())
            if not rel_path or rel_path.is_absolute():
                continue
            destination = self.workspace / rel_path
            ensure_dir(destination.parent)
            destination.write_text(str(entry.get("content") or ""), encoding="utf-8")
            written.append(str(rel_path))
        return written

    def _write_compiler_records(self, result: CompilerResult, written_files: List[str]) -> None:
        files = result.manifest.get("files") or []
        llm_execution = llm_execution_summary(
            getattr(self, "llm", None),
            observed=True,
            metadata={"cache_mode": "none"},
        )
        llm_stub_used = bool(llm_execution.get("stub_fallback"))
        llm_fixture_used = bool(llm_execution.get("fixture_used"))
        llm_provider_attempted = bool(llm_execution.get("provider_attempted"))
        llm_provider_succeeded = bool(llm_execution.get("provider_succeeded"))
        llm_failure_class = str(llm_execution.get("last_error_class") or "").strip()
        llm_failure_message = str(llm_execution.get("last_error_message") or "").strip()
        summary = {
            "index": 1,
            "score": 1.0,
            "violations": [],
            "accepted": True,
            "manifest_digest": "",
            "file_paths": [entry.get("path") for entry in files if isinstance(entry, dict)],
            "pattern_tags": result.manifest.get("pattern_tags", []),
            "raw_excerpt": f"compiler:{result.strategy}",
            "static_report": {"score": 1.0, "source": "compiler"},
            "dep_guard": {},
            "fallback_used": False,
            "fallback_class": "",
            "family_override_applied": False,
            "llm_stub_used": llm_stub_used,
            "llm_fixture_used": llm_fixture_used,
            "llm_provider_attempted": llm_provider_attempted,
            "llm_provider_succeeded": llm_provider_succeeded,
            "llm_failure_class": llm_failure_class,
            "llm_failure_message": llm_failure_message,
            "llm_execution": llm_execution,
        }
        candidates_payload = {"mode": "compiler", "candidates": [summary]}
        (self.metadata_dir / "generator_candidates.json").write_text(
            json.dumps(candidates_payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        manifest_payload = {
            "sid": self.sid,
            "slug": self.bundle.slug if self.bundle else "",
            "vuln_id": str(self.requirement.get("vuln_id") or "").strip() or "UNKNOWN",
            "mode": "compiler",
            "limits": self.synthesis_limits.to_dict(),
            "workspace_root": str(self.workspace),
            "selected_candidate": summary,
            "manifest": result.manifest,
            "failure_context": "",
            "hints_digest": "",
            "rag_snapshot_digest": "",
            "user_deps": self.user_deps,
            "requires_external_db": bool(result.manifest.get("requires_external_db")),
            "guard_spec_available": bool(self._load_guard_spec_dict()),
            "guard_policy": {},
            "generation_origin": "compiler_generated",
            "fallback_used": False,
            "fallback_class": None,
            "family_override_applied": False,
            "llm_stub_used": llm_stub_used,
            "llm_fixture_used": llm_fixture_used,
            "llm_provider_attempted": llm_provider_attempted,
            "llm_provider_succeeded": llm_provider_succeeded,
            "llm_failure_class": llm_failure_class,
            "llm_failure_message": llm_failure_message,
            "llm_execution": llm_execution,
            "compiler_strategy": result.strategy,
            "provenance": {
                "generation_origin": "compiler_generated",
                "fallback_used": False,
                "fallback_class": None,
                "family_override_applied": False,
                "llm_stub_used": llm_stub_used,
                "llm_fixture_used": llm_fixture_used,
                "llm_provider_attempted": llm_provider_attempted,
                "llm_provider_succeeded": llm_provider_succeeded,
                "llm_failure_class": llm_failure_class or None,
                "llm_execution": llm_execution,
            },
            "written_files": written_files,
        }
        (self.metadata_dir / "generator_manifest.json").write_text(
            json.dumps(manifest_payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _write_compiler_runtime_rule(self, result: CompilerResult) -> None:
        manifest = result.manifest if isinstance(result.manifest, dict) else {}
        metadata = manifest.get("metadata") if isinstance(manifest.get("metadata"), dict) else {}
        stack_name = str(metadata.get("stack_scaffold_id") or metadata.get("stack") or "").strip().lower()
        spec = compiler_fragment_spec(stack_name, result.strategy) or FLASK_FRAGMENT_REGISTRY.get(result.strategy)
        if spec is None:
            return
        poc = manifest.get("poc") if isinstance(manifest.get("poc"), dict) else {}
        success_signature = str(poc.get("success_signature") or "").strip()
        if not success_signature:
            return
        flag_token = str(poc.get("flag_token") or "").strip()
        service_entry = "app.py"
        poc_entry = "poc.py"
        for entry in manifest.get("files", []):
            if not isinstance(entry, dict):
                continue
            role = str(entry.get("role") or "").strip().lower()
            path = str(entry.get("path") or "").strip()
            if role == "service_main" and path:
                service_entry = path
            elif role == "poc_entry" and path:
                poc_entry = path

        assertion_program: List[Dict[str, Any]] = [{"op": "contains", "string": success_signature}]
        if flag_token:
            assertion_program.append({"op": "contains", "string": flag_token})

        patterns: List[Dict[str, Any]] = []
        for token in spec.service_side_tokens:
            if not token:
                continue
            patterns.append({"type": "file_contains", "path": service_entry, "contains": token})
        patterns.append({"type": "poc_contains", "path": poc_entry, "contains": success_signature})
        if flag_token:
            patterns.append({"type": "poc_contains", "path": poc_entry, "contains": flag_token})

        rule = {
            "cwe": str(self.requirement.get("vuln_id") or manifest.get("metadata", {}).get("cwe") or "UNKNOWN"),
            "version": 2,
            "scenario_type": "web-poc",
            "origin": "runtime",
            "override_scope": "none",
            "verification": {
                "source": "runtime",
                "require_flag": bool(flag_token),
                "flag_mode": "strict" if flag_token else "none",
                "exit_code": "zero",
            },
            "output": {"mode": "auto", "format": "auto"},
            "llm": {"assist_default": False, "assertion_budget": 8},
            "runtime": {
                "success_mode": "text",
                "success_text_markers": [success_signature],
                "flag_token": flag_token or None,
                "assertion_program": assertion_program,
            },
            "patterns": patterns,
            "success_signature": success_signature,
            "strict_flag": bool(flag_token),
            "service_entry": service_entry,
            "poc_entry": poc_entry,
        }
        if flag_token:
            rule["flag_token"] = flag_token

        import yaml

        self.runtime_rules_dir.mkdir(parents=True, exist_ok=True)
        path = self.runtime_rules_dir / f"{rule_filename_for_vuln_id(rule['cwe'])}.yaml"
        path.write_text(yaml.safe_dump(rule, sort_keys=False, allow_unicode=True), encoding="utf-8")
        metadata_root = getattr(self, "metadata_root", None)
        if isinstance(metadata_root, Path):
            record_generated_runtime_asset(metadata_root, kind="runtime_rules", path=path)
        try:
            load_rule.cache_clear()  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            list_rules.cache_clear()  # type: ignore[attr-defined]
        except Exception:
            pass
        LOGGER.info("Compiler-derived runtime rule written to %s", path)

    def _ensure_loop_started(self) -> None:
        if self.loop_controller.current_loop == 0:
            self.loop_controller.start_loop()

    def _run_synthesis_with_loops(self, context: GeneratorContext) -> SynthesisOutcome:
        if self.single_attempt:
            try:
                outcome = self._run_synthesis_once(context)
                added_user_deps = self._apply_user_deps_to_workspace()
                self._record_user_deps_metadata(added_user_deps)
                self._write_generator_contract(mode_label="synthesis")
                self.loop_controller.record_success(stage="GENERATOR", note="synthesis succeeded")
                LOGGER.info(
                    "Synthesis candidate #%s materialized %s files for %s",
                    outcome.selected.index,
                    len(outcome.written_files),
                    self.sid,
                )
                return outcome
            except ManifestValidationError as exc:
                failure_meta = self._latest_generator_failure()
                reason = failure_meta.get("reason") or str(exc)
                fix_hint = failure_meta.get("fix_hint") or "Review generator_failures.jsonl and add missing deps."
                metadata = {
                    "missing_dependencies": failure_meta.get("missing_dependencies", []),
                    "suggested_dependencies": failure_meta.get("suggested_dependencies", []),
                    "guard_error_code": failure_meta.get("guard_error_code"),
                    "guard_error_subcode": failure_meta.get("guard_error_subcode"),
                    "failure_stage": failure_meta.get("failure_stage"),
                    "failure_stage_reason": failure_meta.get("failure_stage_reason"),
                    "unsupported_ops": failure_meta.get("unsupported_ops", []),
                    "schema_errors": failure_meta.get("schema_errors", []),
                    "schema_normalizations": failure_meta.get("schema_normalizations", []),
                    "failure_fingerprint": failure_meta.get("failure_fingerprint", ""),
                    "hint_payload": failure_meta.get("hint_payload", {}),
                }
                self.loop_controller.record_failure(
                    stage="GENERATOR",
                    reason=reason,
                    fix_hint=fix_hint,
                    blocking=True,
                    metadata=metadata,
                )
                raise

        while True:
            try:
                outcome = self._run_synthesis_once(context)
                added_user_deps = self._apply_user_deps_to_workspace()
                self._record_user_deps_metadata(added_user_deps)
                self._write_generator_contract(mode_label="synthesis")
                self.loop_controller.record_success(stage="GENERATOR", note="synthesis succeeded")
                LOGGER.info(
                    "Synthesis candidate #%s materialized %s files for %s",
                    outcome.selected.index,
                    len(outcome.written_files),
                    self.sid,
                )
                return outcome
            except ManifestValidationError as exc:
                failure_meta = self._latest_generator_failure()
                reason = failure_meta.get("reason") or str(exc)
                fix_hint = failure_meta.get("fix_hint") or "Review generator_failures.jsonl and add missing deps."
                metadata = {
                    "missing_dependencies": failure_meta.get("missing_dependencies", []),
                    "suggested_dependencies": failure_meta.get("suggested_dependencies", []),
                    "guard_error_code": failure_meta.get("guard_error_code"),
                    "failure_stage": failure_meta.get("failure_stage"),
                    "failure_stage_reason": failure_meta.get("failure_stage_reason"),
                    "unsupported_ops": failure_meta.get("unsupported_ops", []),
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

    @staticmethod
    def _dynamic_eval_status_for_outcome(outcome: SynthesisOutcome) -> str:
        selected = getattr(outcome, "selected", None)
        if selected is None:
            return "dynamic_success"
        if bool(getattr(selected, "fallback_used", False)):
            return "degraded_success"
        return "dynamic_success"

    def _run_synthesis_once(self, context: GeneratorContext) -> SynthesisOutcome:
        engine = SynthesisEngine(
            sid=self.sid,
            llm=self.llm,
            limits=self.synthesis_limits,
            workspace=self.workspace,
            metadata_dir=self.metadata_dir,
            mode=self.generator_mode,
            user_deps=self.user_deps,
            retry_budget_context={
                **self._retry_budget_context(),
                "planned_candidate_budget": self._candidate_k(),
            },
        )
        return engine.run(
            requirement=self._requirement_for_synthesis(),
            rag_context=context.rag,
            hints=context.hints,
            researcher_report=context.researcher_report,
            guard_spec=context.guard_spec,
            guard_spec_payload=context.guard_spec_dict,
            failure_context=context.failure,
            candidate_k=self._candidate_k(),
            poc_template=self.requirement.get("poc_template"),
        )

    @staticmethod
    def _sanitize_guard_spec_for_generation(payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return {}
        assertions = payload.get("generator_assertions")
        if not isinstance(assertions, list):
            return payload

        warnings: List[str] = []
        changed = False
        for assertion in assertions:
            if not isinstance(assertion, dict):
                continue
            before = json.dumps(assertion, sort_keys=True, ensure_ascii=False)
            warnings.extend(enforce_generator_assertion_trust_boundary(assertion))
            after = json.dumps(assertion, sort_keys=True, ensure_ascii=False)
            if before != after:
                changed = True

        if not changed:
            return payload

        normalization = payload.get("normalization")
        if not isinstance(normalization, dict):
            normalization = {}
        existing = normalization.get("warnings")
        merged = list(existing) if isinstance(existing, list) else []
        merged.extend(
            item for item in warnings if isinstance(item, str) and item.strip()
        )
        normalization["warnings"] = list(dict.fromkeys(merged))
        payload["normalization"] = normalization
        return payload

    def _load_guard_spec_dict(self) -> Dict[str, Any]:
        spec = load_guard_spec(self.metadata_dir)
        payload = spec.to_dict() if spec else {}
        if not payload:
            return {}
        before = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        sanitized = self._sanitize_guard_spec_for_generation(payload)
        after = json.dumps(sanitized, sort_keys=True, ensure_ascii=False)
        if after != before:
            write_guard_spec(self.metadata_dir, sanitized)
            LOGGER.info("Sanitized guard spec for generation at %s", self.metadata_dir / "guard_spec.json")
        return sanitized

    def _should_generate_template_plan(self, context: GeneratorContext) -> bool:
        explicit = self.requirement.get("template_plan_enabled")
        if explicit is not None:
            if isinstance(explicit, str):
                return explicit.strip().lower() in {"1", "true", "yes", "on"}
            return bool(explicit)
        return bool((context.failure or "").strip())

    def _run_template(self, context: GeneratorContext, *, mode_label: str) -> None:
        if self._should_generate_template_plan(context):
            prompt_messages = build_generator_prompt(
                self.requirement,
                context.rag,
                failure_context=context.failure,
            )
            self._record_prompt_invocation("generator_plan")
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
        self._write_generator_contract(mode_label=mode_label)
        self.loop_controller.record_success(stage="GENERATOR", note=f"template mode: {mode_label}")

    def _write_generator_contract(self, *, mode_label: str) -> None:
        vuln_id = str(self.requirement.get("vuln_id") or "").strip() or "UNKNOWN"
        slug = self.bundle.slug if self.bundle else ""
        payload = build_generator_contract(
            sid=self.sid,
            vuln_id=vuln_id,
            metadata_dir=self.metadata_dir,
            workspace_dir=self.workspace,
            generator_mode=mode_label,
            bundle_slug=slug,
            requirement=self.requirement,
        )
        path = write_generator_contract(self.metadata_dir, payload)
        LOGGER.info("Generator contract written to %s", path)

    def _latest_generator_failure(self) -> Dict[str, Any]:
        candidate_paths = [self.metadata_dir / "generator_failures.jsonl"]
        if self.metadata_dir != self.metadata_root:
            candidate_paths.append(self.metadata_root / "generator_failures.jsonl")
        latest_entry: Dict[str, Any] = {}
        latest_ts = ""
        for path in candidate_paths:
            if not path.exists():
                continue
            lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            if not lines:
                continue
            try:
                entry = json.loads(lines[-1])
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict):
                continue
            timestamp = str(entry.get("timestamp") or "")
            if timestamp >= latest_ts:
                latest_entry = entry
                latest_ts = timestamp
        return latest_entry

    def _guard_prompt_hint(self) -> str:
        entry = self._latest_generator_failure()
        if not entry:
            return ""
        hint_payload_raw = ((self.plan.get("policy") or {}).get("guard") or {}).get("hint_payload_enabled", True)
        if isinstance(hint_payload_raw, str):
            hint_payload_enabled = hint_payload_raw.strip().lower() in {"1", "true", "yes", "on"}
        else:
            hint_payload_enabled = bool(hint_payload_raw)
        if hint_payload_enabled and isinstance(entry.get("hint_payload"), dict):
            payload = normalize_hint_payload(entry.get("hint_payload"))
            payload_text = json.dumps(payload, indent=2, ensure_ascii=False)
            supported_ops = ", ".join(sorted(SUPPORTED_GENERATOR_ASSERTION_OPS))
            failure_stage = str(entry.get("failure_stage") or "").strip()
            stage_line = f"- Latest staged synthesis failure_stage: `{failure_stage}`.\n" if failure_stage else ""
            return (
                "# Failure Hint Payload (JSON)\n"
                f"{stage_line}"
                "```json\n"
                f"{payload_text}\n"
                "```\n"
                "# Supported Guard Ops\n"
                f"{supported_ops}"
            )

        missing = entry.get("missing_dependencies") or []
        suggested = entry.get("suggested_dependencies") or []
        unsupported_ops = entry.get("unsupported_ops") or []
        guard_error_code = str(entry.get("guard_error_code") or "").strip().lower()
        auto_patch = entry.get("auto_patch") or {}
        skipped = auto_patch.get("skipped") or []
        stdlib_skipped = [item.get("name") for item in skipped if item.get("reason") == "stdlib"]
        notes = entry.get("notes") or []
        semantic_notes = []
        if isinstance(notes, list):
            semantic_notes = [
                str(item).strip()
                for item in notes
                if isinstance(item, str) and "semantic mismatch:" in item.lower()
            ]
        reason = str(entry.get("reason") or "").strip()
        if reason and "semantic mismatch:" in reason.lower():
            semantic_notes.append(reason)
        semantic_notes = sorted(set(note for note in semantic_notes if note))
        if not missing and not suggested and not semantic_notes and not unsupported_ops and not guard_error_code:
            return ""
        unique_missing = sorted({dep for dep in missing if dep})
        unique_suggested = sorted({dep for dep in suggested if dep})
        parts: List[str] = []
        if guard_error_code:
            parts.append(f"Latest guard failure code: {guard_error_code}")
        failure_stage = str(entry.get("failure_stage") or "").strip()
        if failure_stage:
            parts.append(f"Latest staged synthesis failure_stage: {failure_stage}")
        if unsupported_ops:
            parts.append("Unsupported guard ops from last run: " + ", ".join(sorted({str(op) for op in unsupported_ops if op})))
            parts.append(
                "Regenerate GuardSpec with supported generator ops only: "
                "file_exists, role_exists, file_contains, file_not_contains, file_regex_contains, "
                "file_regex_not_contains, file_regex_any, dep_declared, any_dep_declared, "
                "pattern_tag_present, manifest_field_equals, manifest_field_contains."
            )
        if semantic_notes:
            parts.append("Semantic guard failures to fix: " + " | ".join(semantic_notes))
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
        req_vuln = str(self.requirement.get("vuln_id") or "").strip().lower()
        req_db = str(((self.requirement.get("runtime") or {}).get("db")) or "").strip().lower()
        req_pattern = str(self.requirement.get("pattern_id") or "").strip().lower()
        researcher_tags = self._researcher_hint_tags()

        all_templates = [
            template
            for template in self._get_registry().templates
            if self._template_runtime_surface_matches(template)
        ]
        scored: List[Tuple[float, TemplateSpec]] = []
        for t in all_templates:
            score = 0.0
            if req_vuln and req_vuln in t.tags:
                score += 3.0
            if req_db and req_db == t.db:
                score += 2.0
            if not req_db and not t.requires_external_db:
                score += 1.0
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
            candidates = [
                candidate
                for candidate in self._get_registry().sample_candidates(seed=seed, k=k)
                if self._template_runtime_surface_matches(candidate.template)
            ]
            if candidates:
                return candidates[0].template, candidates
            fallback_candidates = self._get_registry().sample_candidates(seed=seed, k=k)
            return fallback_candidates[0].template, fallback_candidates

        scored.sort(key=lambda x: x[0], reverse=True)
        best = scored[0][1]

        # For traceability, still emit candidate list using sampler
        seed = self.variation_manager.pattern_seed_with_offset(self.loop_index)
        k = self._candidate_k()
        candidates = self._get_registry().sample_candidates(seed=seed, k=k)
        return best, candidates

    def _has_viable_template(self) -> bool:
        req_vuln = str(self.requirement.get("vuln_id") or "").strip().lower()
        req_db = self._runtime_db()
        if not req_vuln:
            return False
        templates = self._get_registry().templates
        for t in templates:
            if not self._template_runtime_surface_matches(t):
                continue
            vuln_match = req_vuln in t.tags
            db_match = not req_db or req_db == t.db
            if vuln_match and db_match:
                return True
        return False

    def _has_compatible_template(self) -> bool:
        req_vuln = str(self.requirement.get("vuln_id") or "").strip().lower()
        req_pattern = str(self.requirement.get("pattern_id") or "").strip().lower()
        if not req_vuln and not req_pattern:
            return False
        templates = self._get_registry().templates
        for template in templates:
            if not self._template_runtime_surface_matches(template):
                continue
            tags = set(template.tags)
            if req_vuln and req_vuln in tags:
                return True
            if req_pattern and req_pattern == (template.pattern_id or "").lower():
                return True
        return False

    def _template_runtime_surface_matches(self, template: TemplateSpec) -> bool:
        diagnostics = self._template_runtime_diagnostics(template)
        return bool(diagnostics.get("matches"))

    def _template_runtime_diagnostics(self, template: TemplateSpec) -> Dict[str, Any]:
        requested_stack_id = self._requested_stack_id()
        template_stack_id = str(getattr(template, "stack_id", "") or "").strip().lower()
        requested_db = self._runtime_db()
        template_db = str(getattr(template, "db", "") or "").strip().lower()
        requires_external_db = bool(getattr(template, "requires_external_db", False))
        template_env_keys = sorted(
            {
                str(key).strip()
                for key in getattr(template, "service_env", {}).keys()
                if isinstance(key, str) and str(key).strip()
            }
        )
        expected_env = self._template_expected_service_env(template)
        expected_env_keys = sorted(expected_env)
        stack_match = self._template_stack_matches(template)

        diagnostics: Dict[str, Any] = {
            "matches": True,
            "requested_stack_id": requested_stack_id or None,
            "template_stack_id": template_stack_id or None,
            "stack_match": stack_match,
            "requested_db": requested_db or None,
            "template_db": template_db or None,
            "requires_external_db": requires_external_db,
            "template_service_env_keys": template_env_keys,
            "expected_service_env_keys": expected_env_keys,
            "status": "not_required",
            "reason": "template runtime requirements are satisfied",
        }

        if not stack_match:
            diagnostics["matches"] = False
            diagnostics["status"] = "stack_mismatch"
            diagnostics["reason"] = "template stack metadata does not match requested stack"
            return diagnostics

        allow_external = self._allow_external_db()
        if not allow_external and requires_external_db:
            diagnostics["matches"] = False
            diagnostics["status"] = "external_db_disallowed"
            diagnostics["reason"] = "template requires external DB but runtime disallows it"
            return diagnostics

        if requested_db and not (bool(template_db) and template_db == requested_db):
            diagnostics["matches"] = False
            diagnostics["status"] = "db_mismatch"
            diagnostics["reason"] = "template DB surface does not match requested runtime DB"
            return diagnostics

        if requires_external_db:
            strategy = resolve_compiler_strategy(
                str(self.requirement.get("vuln_id") or "").strip(),
                self.requirement,
            )
            feasibility = executor_feasibility_summary(
                self.requirement,
                self._executor_policy_for_template_runtime_surface(),
                requires_external_db=True,
            )
            diagnostics["executor_feasibility_status"] = str(feasibility.get("status") or "").strip().lower() or None
            diagnostics["executor_feasibility_reason"] = str(feasibility.get("reason") or "").strip() or None
            if diagnostics["executor_feasibility_status"] != "configured":
                diagnostics["matches"] = False
                diagnostics["status"] = "executor_misconfigured"
                diagnostics["reason"] = (
                    diagnostics["executor_feasibility_reason"]
                    or "executor surface does not satisfy external DB contract"
                )
                return diagnostics
            diagnostics["status"] = "configured"
            runtime_surface = diagnose_runtime_surface(
                compiler_strategy=strategy,
                requirement=self.requirement,
                service_port=self._template_service_port(template),
            )
            missing_targets = runtime_surface.get("missing_sidecar_targets") or []
            defaulted_sidecar_keys = runtime_surface.get("defaulted_sidecar_keys") or []
            if missing_targets:
                diagnostics["matches"] = False
                diagnostics["status"] = "sidecar_contract_mismatch"
                diagnostics["reason"] = "template runtime surface could not resolve a compatible sidecar target"
                diagnostics["missing_sidecar_targets"] = missing_targets
                return diagnostics
            if defaulted_sidecar_keys:
                diagnostics["matches"] = False
                diagnostics["status"] = "sidecar_env_mismatch"
                diagnostics["reason"] = "template runtime surface fell back to defaults for sidecar-backed env keys"
                diagnostics["defaulted_sidecar_keys"] = defaulted_sidecar_keys
                return diagnostics

        if template_env_keys and expected_env:
            expected_keys = set(expected_env)
            if not set(template_env_keys).issubset(expected_keys):
                diagnostics["matches"] = False
                diagnostics["status"] = "env_contract_mismatch"
                diagnostics["reason"] = "template env contract is not satisfied by derived runtime surface"
                return diagnostics
            value_mismatches = {}
            for key, template_value in getattr(template, "service_env", {}).items():
                expected_value = expected_env.get(key)
                if expected_value is None:
                    continue
                if str(template_value) != str(expected_value):
                    value_mismatches[key] = {
                        "template": str(template_value),
                        "expected": str(expected_value),
                    }
            if value_mismatches:
                diagnostics["matches"] = False
                diagnostics["status"] = "env_value_mismatch"
                diagnostics["reason"] = "template env values do not match the derived runtime surface"
                diagnostics["env_value_mismatches"] = value_mismatches
                return diagnostics

        return diagnostics

    def _template_service_port(self, template: TemplateSpec) -> int:
        metadata = getattr(template, "metadata", {})
        ports = metadata.get("ports") if isinstance(metadata, dict) else {}
        if isinstance(ports, dict):
            for key in ("app", "service", "http"):
                try:
                    candidate = int(ports.get(key))
                except Exception:
                    candidate = None
                if candidate and candidate > 0:
                    return candidate
        return 5000

    def _template_stack_matches(self, template: TemplateSpec) -> bool:
        requested = self._requested_stack_id()
        if not requested:
            return True
        template_stack = str(getattr(template, "stack_id", "") or "").strip().lower()
        if template_stack:
            return template_stack == requested
        template_language = str(getattr(template, "language", "") or "").strip().lower()
        template_framework = str(getattr(template, "framework", "") or "").strip().lower()
        if template_language and template_framework:
            return f"{template_language}/{template_framework}" == requested
        return True

    def _requested_stack_id(self) -> str:
        requirement = self.requirement if isinstance(self.requirement, dict) else {}
        language = str(requirement.get("language") or "").strip().lower()
        framework = str(requirement.get("framework") or "").strip().lower()
        if language and framework:
            return f"{language}/{framework}"
        return ""

    def _executor_policy_for_template_runtime_surface(self) -> Dict[str, Any]:
        executor = self.requirement.get("executor") if isinstance(self.requirement, dict) else None
        if isinstance(executor, dict):
            return executor
        plan = self.plan if isinstance(getattr(self, "plan", None), dict) else {}
        policy = plan.get("policy") if isinstance(plan, dict) else {}
        executor = policy.get("executor") if isinstance(policy, dict) else None
        return executor if isinstance(executor, dict) else {}

    def _template_expected_service_env(self, template: TemplateSpec) -> Dict[str, str]:
        vuln_id = str(self.requirement.get("vuln_id") or "").strip()
        if not vuln_id:
            return {}
        strategy = resolve_compiler_strategy(vuln_id, self.requirement)
        if not strategy:
            return {}
        return derive_service_env(
            compiler_strategy=strategy,
            requirement=self.requirement,
            service_port=self._template_service_port(template),
        )

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

        template_root = selection.path.parent
        runtime_template_selected = bool(
            template_root == self.runtime_templates_dir or self.runtime_templates_dir in template_root.parents
        )
        generation_origin = "runtime_template_clone" if runtime_template_selected else "built_in_template"
        diagnostics = self._template_runtime_diagnostics(selection)
        llm_metadata = {"cache_mode": "none", **self._prompt_invocation_metadata()}
        prompt_invocations = llm_metadata.get("prompt_invocations") if isinstance(llm_metadata.get("prompt_invocations"), dict) else {}
        if prompt_invocations:
            retry_budget = self._retry_budget_context()
            retry_budget["template_plan_actual_runs"] = int(prompt_invocations.get("generator_plan") or 0)
            retry_budget["template_selection_candidate_budget"] = self._candidate_k()
            llm_metadata["retry_budget"] = retry_budget
        llm_execution = llm_execution_summary(getattr(self, "llm", None), observed=True, metadata=llm_metadata)
        selection_payload = {
            "sid": self.sid,
            "template_id": selection.id,
            "pattern_id": selection.pattern_id,
            "template_stack_id": selection.stack_id or None,
            "template_language": selection.language or None,
            "template_framework": selection.framework or None,
            "requested_stack_id": diagnostics.get("requested_stack_id"),
            "template_stack_match": diagnostics.get("stack_match"),
            "template_runtime_surface_status": diagnostics.get("status"),
            "template_runtime_surface_reason": diagnostics.get("reason"),
            "scenario_type": selection.scenario_type,
            "requires_external_db": selection.requires_external_db,
            "ports": selection.metadata.get("ports") if isinstance(selection.metadata, dict) else {},
            "service_entry": selection.service_entry,
            "poc_entry": selection.poc_entry,
            "service_env": selection.service_env,
            "flag_token": (
                selection.metadata.get("flag_token")
                if isinstance(selection.metadata, dict) and isinstance(selection.metadata.get("flag_token"), str)
                else None
            ),
            "variation_key": self.variation,
            "loop_index": self.loop_index,
            "failure_context": failure_context,
            "written_files": written_files,
            "user_deps_requested": self.user_deps,
            "user_deps_added": user_deps_added or [],
            "generation_origin": generation_origin,
            "fallback_used": False,
            "family_override_applied": False,
            "llm_stub_used": bool(llm_execution.get("stub_fallback")),
            "llm_fixture_used": bool(llm_execution.get("fixture_used")),
            "llm_provider_attempted": bool(llm_execution.get("provider_attempted")),
            "llm_provider_succeeded": bool(llm_execution.get("provider_succeeded")),
            "llm_failure_class": str(llm_execution.get("last_error_class") or "").strip(),
            "llm_failure_message": str(llm_execution.get("last_error_message") or "").strip(),
            "llm_execution": llm_execution,
            "template_root": str(template_root),
            "template_runtime_diagnostics": diagnostics,
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

        self._ensure_poc_scaffold(selection, success_signature, flag_token)

    def _ensure_poc_scaffold(
        self, selection: TemplateSpec, success_signature: str, flag_token: str
    ) -> None:
        poc_entry = selection.poc_entry or "poc.py"
        poc_path = self.workspace / poc_entry
        if poc_path.exists():
            return

        method, path = self._infer_poc_endpoint(selection)
        default_base_url = self._infer_default_base_url(selection)

        content_lines = [
            "import argparse",
            "import sys",
            "from urllib.request import Request, urlopen",
            "from urllib.error import URLError, HTTPError",
            "from urllib.parse import urlencode",
            "",
            "SUCCESS_SIGNATURE = " + repr(success_signature or "Exploit SUCCESS"),
            "FLAG_TOKEN = " + repr(flag_token or ""),
            "PATH = " + repr(path),
            "METHOD = " + repr(method),
            "",
            "def exploit(base_url: str, payload: str | None = None) -> bool:",
            "    url = base_url.rstrip('/') + PATH",
            "    data = None",
            "    status = 0",
            "    try:",
            "        if payload:",
            "            if METHOD in ('GET', 'HEAD'):",
            "                sep = '&' if '?' in url else '?'",
            "                url = url + sep + urlencode({'payload': payload})",
            "            else:",
            "                data = urlencode({'payload': payload}).encode('utf-8')",
            "        req = Request(url, data=data, method=METHOD)",
            "        if data is not None:",
            "            req.add_header('Content-Type', 'application/x-www-form-urlencoded')",
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
            f"    parser.add_argument('--base-url', default={default_base_url!r})",
            "    parser.add_argument('--payload', default='', help='Optional payload string')",
            "    args = parser.parse_args()",
            "    payload = args.payload or None",
            "    if exploit(args.base_url, payload):",
            "        sys.exit(0)",
            "    print('[auto] scaffold did not trigger exploit', file=sys.stderr)",
            "    sys.exit(1)",
            "",
            "if __name__ == '__main__':",
            "    main()",
        ]
        ensure_dir(poc_path.parent)
        poc_path.write_text("\n".join(content_lines) + "\n", encoding="utf-8")
        LOGGER.info("Created scaffold %s for %s", poc_entry, self.sid)

    def _infer_default_base_url(self, selection: TemplateSpec) -> str:
        ports = selection.metadata.get("ports") if isinstance(selection.metadata, dict) else {}
        port = None
        if isinstance(ports, dict):
            for key in ("app", "service", "http"):
                candidate = ports.get(key)
                try:
                    value = int(candidate)
                except Exception:
                    value = None
                if value and value > 0:
                    port = value
                    break
        if not port:
            port = 5000
        return f"http://127.0.0.1:{port}"

    def _infer_poc_endpoint(self, selection: TemplateSpec) -> tuple[str, str]:
        """Infer a (method, path) pair from the service entrypoint source.

        This intentionally avoids CWE-specific endpoint tables; it scans the
        template's service_entry file for common Flask routing decorators.
        """
        service_entry = selection.service_entry or "app.py"
        rel = Path(service_entry)
        if rel.is_absolute() or ".." in rel.parts:
            return "GET", "/"
        service_path = self.workspace / rel
        if not service_path.exists():
            return "GET", "/"
        try:
            text = service_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return "GET", "/"

        candidates: List[tuple[int, str, str]] = []
        route_pattern = re.compile(
            r"@(?P<obj>[A-Za-z0-9_\\.]+)\\.route\\(\\s*(?P<q>['\\\"])(?P<path>[^'\\\"]+)(?P=q)"
            r"(?:\\s*,\\s*methods\\s*=\\s*(?P<methods>\\[[^\\]]*\\]|\\([^\\)]*\\)))?",
            re.MULTILINE,
        )
        verb_pattern = re.compile(
            r"@(?P<obj>[A-Za-z0-9_\\.]+)\\.(?P<verb>get|post|put|delete|patch)\\(\\s*(?P<q>['\\\"])(?P<path>[^'\\\"]+)(?P=q)",
            re.MULTILINE | re.IGNORECASE,
        )

        for match in route_pattern.finditer(text):
            raw_path = match.group("path")
            methods_blob = match.group("methods") or ""
            method = "GET"
            if methods_blob:
                method_tokens = re.findall(r"['\\\"]([A-Za-z]+)['\\\"]", methods_blob)
                allowed = [m.upper() for m in method_tokens if m and m.upper() in {"GET", "POST", "PUT", "DELETE", "PATCH"}]
                if allowed:
                    method = allowed[0]
            candidates.append((match.start(), method, raw_path))

        for match in verb_pattern.finditer(text):
            raw_path = match.group("path")
            method = str(match.group("verb") or "GET").upper()
            candidates.append((match.start(), method, raw_path))

        if not candidates:
            return "GET", "/"
        candidates.sort(key=lambda item: item[0])
        for _, method, raw_path in candidates:
            if raw_path and raw_path != "/" and not raw_path.startswith("/static"):
                return method, raw_path
        _, method, raw_path = candidates[0]
        return method, raw_path or "/"


__all__ = ["GeneratorService", "TemplateRegistry", "TemplateSpec"]
