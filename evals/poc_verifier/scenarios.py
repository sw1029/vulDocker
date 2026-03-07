"""Scenario abstraction layer for PoC verification.

This module introduces EvaluationContext and BaseScenarioVerifier
to decouple vuln-specific logic from raw log-path based functions.
Existing call sites remain compatible; plugins can opt into this
layer by constructing a scenario from the context.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Type

from common.contracts import load_generator_contract
from common.rules import RuleSpec, load_rulespec
from evals.poc_verifier import rule_based as _rule_based


@dataclass
class EvaluationContext:
    """Normalized context for evaluating a single vuln bundle."""

    vuln_id: str
    sid: str
    slug: str
    log_path: Path
    workspace_dirs: List[Path]
    requirement: Optional[Dict[str, Any]] = None
    run_summary: Optional[Dict[str, Any]] = None
    policy: Optional[Dict[str, Any]] = None
    rule_spec: Optional[RuleSpec] = None


class BaseScenarioVerifier(ABC):
    """Abstract base for scenario-specific verifiers.

    Subclasses may optionally override expected_signature/verify_log/
    verify_patterns to share common behaviour across scenario types.
    """

    def __init__(self, context: EvaluationContext) -> None:
        self.context = context

    def expected_signature(self) -> Optional[Dict[str, Any]]:
        """Return a normalized signature spec derived from RuleSpec.runtime.

        This is a convenience helper for scenarios that want to surface
        success markers/flag tokens without re-parsing RuleSpec.
        """
        spec = self.context.rule_spec
        if not isinstance(spec, RuleSpec):
            return None
        runtime = spec.runtime or {}
        if not isinstance(runtime, dict):
            runtime = {}
        markers = runtime.get("success_text_markers") or []
        if isinstance(markers, str):
            markers = [markers]
        if not isinstance(markers, list):
            markers = []
        markers = [m for m in markers if isinstance(m, str) and m]
        return {
            "mode": runtime.get("success_mode") or spec.output_mode,
            "markers": markers,
            "flag_token": runtime.get("flag_token"),
        }

    def verify_log(self) -> Dict[str, Any]:
        """Verify using log-only signals.

        The default implementation delegates to the full verify() method,
        allowing existing subclasses that only implement verify() to
        remain valid. Scenario types that need finer-grained control
        can override this method.
        """
        return self.verify()

    def verify_patterns(self) -> Dict[str, Any]:
        """Optional additional verification based on workspace patterns."""
        return {}

    @abstractmethod
    def verify(self) -> Dict[str, Any]:
        raise NotImplementedError


class RuleBasedScenario(BaseScenarioVerifier):
    """Scenario that delegates to the generic rule-based verifier."""

    def verify(self) -> Dict[str, Any]:
        # Delegate exploit/semantic/guard composition to the shared verifier.
        policy = self.context.policy or {}
        result = _rule_based.verify_with_rule(
            self.context.vuln_id,
            self.context.log_path,
            requirement=self.context.requirement,
            run_summary=self.context.run_summary,
            policy=policy,
        )
        return result


class SignatureOnlyScenario(RuleBasedScenario):
    """Scenario type for simple signature/flag based PoC checks."""


class HttpEffectScenario(RuleBasedScenario):
    """Scenario type for HTTP/request effect based checks.

    For now this reuses the generic rule-based flow; dedicated
    implementations can refine verify_log/verify_patterns later.
    """


class FileMutationScenario(RuleBasedScenario):
    """Scenario type for workspace/file-mutation oriented checks.

    Currently identical to RuleBasedScenario; specialized behaviour
    can be introduced without changing the registry wiring.
    """


_SCENARIOS: Dict[str, Type[BaseScenarioVerifier]] = {}


def _normalize(vuln_id: str) -> str:
    return (vuln_id or "").strip().lower()


def register_scenario(vuln_ids: Iterable[str], cls: Type[BaseScenarioVerifier]) -> None:
    for vuln_id in vuln_ids:
        key = _normalize(vuln_id)
        if not key:
            continue
        _SCENARIOS[key] = cls


def get_scenario(vuln_id: str) -> Optional[Type[BaseScenarioVerifier]]:
    return _SCENARIOS.get(_normalize(vuln_id))


def _scenario_for_type(rule_spec: Optional[RuleSpec]) -> Type[BaseScenarioVerifier]:
    """Select a default scenario class based on RuleSpec.scenario_type.

    This keeps behaviour backwards compatible while making scenario_type
    actually influence which implementation is used. For now all known
    web PoC scenarios share the same RuleBasedScenario, but dedicated
    scenario types are wired for future use.
    """
    if rule_spec is None:
        return RuleBasedScenario
    scenario_type = (rule_spec.scenario_type or "web-poc").strip().lower()
    if scenario_type in {"web-poc", "web_poc"}:
        return RuleBasedScenario
    if scenario_type in {"signature_only", "signature-only"}:
        return SignatureOnlyScenario
    if scenario_type in {"http_effect", "http-effect"}:
        return HttpEffectScenario
    if scenario_type in {"file_mutation", "file-mutation"}:
        return FileMutationScenario
    # Unknown types currently fall back to the generic rule-based flow.
    return RuleBasedScenario


def _load_runtime_generator_metadata(sid: str, slug: str) -> Optional[Dict[str, Any]]:
    """Load generator contract metadata for this run, if present.

    Supports both single-vuln and multi-vuln layouts by checking:
    - metadata/<sid>/bundles/<slug>/resolved_contract.json
    - metadata/<sid>/bundles/<slug>/generator_contract.json
    - metadata/<sid>/resolved_contract.json
    - metadata/<sid>/generator_contract.json
    - (fallback) generator_template.json in the same locations
    """
    sid = (sid or "").strip()
    slug = (slug or "").strip()
    if not sid:
        return None
    candidate_dirs: List[Path] = []
    if slug:
        candidate_dirs.append(_rule_based.REPO_ROOT / "metadata" / sid / "bundles" / slug)
    candidate_dirs.append(_rule_based.REPO_ROOT / "metadata" / sid)
    for meta_dir in candidate_dirs:
        contract = load_generator_contract(meta_dir)
        if isinstance(contract, dict):
            return contract
        path = meta_dir / "generator_template.json"
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return None


def _apply_template_metadata_override(spec: RuleSpec, meta: Dict[str, Any]) -> RuleSpec:
    """Refine a RuleSpec instance using runtime template metadata."""
    scenario_type = meta.get("scenario_type")
    if isinstance(scenario_type, str) and scenario_type.strip():
        spec.scenario_type = scenario_type.strip()

    service_entry = meta.get("service_entry")
    if isinstance(service_entry, str) and service_entry.strip():
        spec.service_entry = service_entry.strip()

    poc_entry = meta.get("poc_entry")
    if isinstance(poc_entry, str) and poc_entry.strip():
        spec.poc_entry = poc_entry.strip()

    flag_token = meta.get("flag_token")
    if isinstance(flag_token, str) and flag_token.strip():
        token = flag_token.strip()
        spec.template_flag_token = token
        runtime = spec.runtime if isinstance(spec.runtime, dict) else {}
        if not runtime.get("flag_token"):
            runtime = dict(runtime)
            runtime["flag_token"] = token
            spec.runtime = runtime
    return spec


def build_evaluation_context(
    vuln_id: str,
    log_path: Path,
    *,
    requirement: Optional[Dict[str, Any]] = None,
    run_summary: Optional[Dict[str, Any]] = None,
    policy: Optional[Dict[str, Any]] = None,
) -> EvaluationContext:
    summary_obj: Dict[str, Any] = {}
    if isinstance(run_summary, dict):
        summary_obj = run_summary
    sid = str(summary_obj.get("sid") or "").strip()
    if not sid:
        sid = _rule_based._extract_sid_from_log(log_path)
    slug = str(summary_obj.get("slug") or "").strip()
    if not slug:
        slug = _rule_based._extract_slug_from_log(log_path)
    workspace_dirs = _rule_based._workspace_candidates(log_path, summary_obj or None)
    rule_spec = load_rulespec(vuln_id)

    # If a generator_template.json exists for this run (per-bundle in multi-vuln
    # mode), use it to refine the RuleSpec with the actual scenario/template
    # metadata instead of relying solely on global template indices.
    template_meta = _load_runtime_generator_metadata(sid, slug)
    if isinstance(rule_spec, RuleSpec) and template_meta:
        rule_spec = _apply_template_metadata_override(rule_spec, template_meta)
    return EvaluationContext(
        vuln_id=vuln_id,
        sid=sid,
        slug=slug,
        log_path=log_path,
        workspace_dirs=workspace_dirs,
        requirement=requirement,
        run_summary=run_summary,
        policy=policy,
        rule_spec=rule_spec,
    )


__all__ = [
    "EvaluationContext",
    "RuleSpec",
    "BaseScenarioVerifier",
    "RuleBasedScenario",
    "SignatureOnlyScenario",
    "HttpEffectScenario",
    "FileMutationScenario",
    "register_scenario",
    "get_scenario",
    "build_evaluation_context",
]
