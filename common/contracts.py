"""Shared contract helpers for researcher/generator/executor/verifier stages.

This module centralizes how we resolve the *run contract* that downstream stages
need (success/flag markers, service entry, poc entry, service port, base URL,
PoC command). Researcher may write an early seed contract and the generator
later refreshes the canonical payload to
`resolved_contract.json` and mirrors it to `generator_contract.json` for
backward compatibility.
"""

from __future__ import annotations

import ast
import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from common.roles import role_matches
from common.researcher_report import (
    extract_semantic_contract,
    extract_verification_spec,
    normalize_researcher_report_payload,
)
from common.name_only import build_name_only_contract, is_name_driven_requirement, name_only_mode
from common.runtime_surface import derive_service_env
from common.rules import load_rule, load_rulespec, load_static_rule
from common.vuln_catalog import (
    catalog_semantic_support_defaults,
    resolve_compiler_strategy,
    resolve_vuln_catalog_entry,
    vuln_catalog_entries,
)
from common.vuln_semantics import (
    FAMILY_CANONICAL_TAGS,
    baseline_semantic_signature,
    family_canonical_tags,
    normalize_vuln_id,
    semantic_term_aliases,
)

DEFAULT_APP_PORT = 5000
RESOLVED_CONTRACT_SCHEMA_VERSION = "resolved_contract@1.0"
RESOLVED_CONTRACT_FILENAME = "resolved_contract.json"
LEGACY_CONTRACT_FILENAME = "generator_contract.json"
SEMANTIC_PROFILE_SCHEMA_VERSION = "semantic_profile@1.0"
SEMANTIC_PROFILE_FILENAME = "semantic_profile.json"
SEMANTIC_STATUS_VALUES = {"aligned", "contradicted", "unsupported", "empty"}

_SEMANTIC_PROFILE_DEFAULTS: Dict[str, Dict[str, str]] = catalog_semantic_support_defaults()


def _resolved_contract_path(metadata_dir: Path) -> Path:
    return metadata_dir / RESOLVED_CONTRACT_FILENAME


def _legacy_contract_path(metadata_dir: Path) -> Path:
    return metadata_dir / LEGACY_CONTRACT_FILENAME


def _semantic_profile_path(metadata_dir: Path) -> Path:
    return metadata_dir / SEMANTIC_PROFILE_FILENAME


def load_generator_contract(metadata_dir: Path) -> Optional[Dict[str, Any]]:
    for path in (_resolved_contract_path(metadata_dir), _legacy_contract_path(metadata_dir)):
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return None


def load_semantic_profile(metadata_dir: Path) -> Optional[Dict[str, Any]]:
    path = _semantic_profile_path(metadata_dir)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            return data
    contract = load_generator_contract(metadata_dir)
    if isinstance(contract, dict):
        profile = contract.get("semantic_profile")
        if isinstance(profile, dict):
            return profile
    return None


def requires_semantic_support(vuln_id: str) -> bool:
    token = str(vuln_id or "").strip().upper()
    if token.startswith("NAME-"):
        return True
    return not bool(load_static_rule(vuln_id))


def requires_semantic_support_for_requirement(vuln_id: str, requirement: Optional[Dict[str, Any]] = None) -> bool:
    if isinstance(requirement, dict) and is_name_driven_requirement(requirement):
        return True
    return requires_semantic_support(vuln_id)


def compiler_support_summary(vuln_id: str, requirement: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return the default compiler support verdict for a vuln family.

    This is the pre-research/pre-generation lower-bound view derived from the
    canonical family mapping plus the currently implemented compiler registry.
    """

    defaults = _semantic_profile_defaults(vuln_id)
    support_level = str(defaults.get("support_level") or "unsupported").strip().lower()
    compiler_strategy = resolve_compiler_strategy(vuln_id, requirement) or _string_or_none(defaults.get("compiler_strategy")) or ""
    compiler_available = _compiler_strategy_supported(compiler_strategy, requirement)
    if support_level == "unsupported":
        compiler_supported = False
        compiler_reason = "semantic family unsupported for compiler-backed generation"
    elif support_level == "deferred":
        compiler_supported = False
        compiler_reason = "family has deterministic fallback coverage but no compiler-backed path yet"
    elif not compiler_strategy:
        compiler_supported = False
        compiler_reason = "no compiler strategy mapped for this family"
    elif not compiler_available:
        compiler_supported = False
        compiler_reason = "compiler scaffold registry not implemented"
    else:
        compiler_supported = True
        compiler_reason = "compiler strategy and scaffold are available"
    return {
        "family": defaults.get("family") or _fallback_family_label(vuln_id),
        "support_level": support_level,
        "compiler_strategy": compiler_strategy or None,
        "compiler_supported": compiler_supported,
        "compiler_reason": compiler_reason,
        "static_rule": bool(load_static_rule(vuln_id)),
    }


def can_resolve_without_remote_research(vuln_id: str) -> bool:
    """Whether the current release has a non-remote lower-bound path for a vuln."""

    summary = compiler_support_summary(vuln_id)
    return bool(summary.get("static_rule") or summary.get("compiler_supported"))


def compiler_path_enabled(requirement: Optional[Dict[str, Any]]) -> bool:
    """Whether compiler-backed lower bounds are enabled for this requirement."""

    if not isinstance(requirement, dict):
        return True
    compiler_cfg = requirement.get("compiler")
    if isinstance(compiler_cfg, dict) and "enabled" in compiler_cfg:
        enabled = _bool_or_none(compiler_cfg.get("enabled"))
        if enabled is not None:
            return enabled
    legacy_disabled = _bool_or_none(requirement.get("disable_compiler"))
    if legacy_disabled is True:
        return False
    return True


def can_resolve_without_remote_research_for_requirement(
    vuln_id: str,
    requirement: Optional[Dict[str, Any]],
) -> bool:
    """Requirement-aware lower-bound view used by planning/skip policies.

    Static rules remain available regardless of compiler flags. Compiler-only
    lower bounds are disabled when the requirement explicitly disables the
    compiler path.
    """

    summary = compiler_support_summary(vuln_id, requirement)
    if summary.get("static_rule"):
        return True
    if not compiler_path_enabled(requirement):
        return False
    return bool(summary.get("compiler_supported"))


def lower_bound_summary(
    vuln_id: str,
    requirement: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Describe both family-level and effective lower bounds for a request."""

    compiler_summary = compiler_support_summary(vuln_id, requirement)
    static_rule_available = bool(compiler_summary.get("static_rule"))
    compiler_supported = bool(compiler_summary.get("compiler_supported"))
    compiler_enabled = compiler_path_enabled(requirement)
    family_non_remote_available = bool(static_rule_available or compiler_supported)
    effective_non_remote_available = can_resolve_without_remote_research_for_requirement(vuln_id, requirement)

    effective_reason = ""
    if static_rule_available:
        effective_reason = "static rule available"
    elif compiler_supported and compiler_enabled:
        effective_reason = "compiler lower bound available and enabled"
    elif compiler_supported and not compiler_enabled:
        effective_reason = "compiler lower bound exists but is disabled by requirement"
    else:
        effective_reason = str(compiler_summary.get("compiler_reason") or "no non-remote lower bound")

    return {
        "family": compiler_summary.get("family"),
        "support_level": compiler_summary.get("support_level"),
        "compiler_strategy": compiler_summary.get("compiler_strategy"),
        "compiler_reason": compiler_summary.get("compiler_reason"),
        "static_rule_available": static_rule_available,
        "compiler_supported": compiler_supported,
        "compiler_path_enabled": compiler_enabled,
        "family_non_remote_available": family_non_remote_available,
        "effective_non_remote_available": effective_non_remote_available,
        "effective_reason": effective_reason,
    }


def executor_feasibility_summary(
    requirement: Optional[Dict[str, Any]],
    executor_policy: Optional[Dict[str, Any]],
    *,
    requires_external_db: Optional[bool] = None,
) -> Dict[str, Any]:
    """Summarize whether current executor policy can satisfy bundle runtime deps."""

    req = requirement if isinstance(requirement, dict) else {}
    runtime = req.get("runtime") if isinstance(req.get("runtime"), dict) else {}
    db = str(runtime.get("db") or "").strip().lower()
    if requires_external_db is None:
        requires_external_db = db in {"mysql", "postgres", "postgresql", "mariadb"}
    runtime_allow_external_db = _bool_or_none(runtime.get("allow_external_db"))
    if runtime_allow_external_db is None:
        runtime_allow_external_db = False

    policy = executor_policy if isinstance(executor_policy, dict) else {}
    sidecars = policy.get("sidecars") or []
    sidecars_declared = isinstance(sidecars, list) and bool(sidecars)
    compatible_sidecar_types: Dict[str, set[str]] = {
        "mysql": {"mysql", "mariadb"},
        "mariadb": {"mysql", "mariadb"},
        "postgres": {"postgres", "postgresql"},
        "postgresql": {"postgres", "postgresql"},
    }
    required_types = sorted(compatible_sidecar_types.get(db, set()))
    matching_sidecars = []
    if isinstance(sidecars, list) and required_types:
        for entry in sidecars:
            if not isinstance(entry, dict):
                continue
            sidecar_type = str(entry.get("type") or "").strip().lower()
            if sidecar_type in compatible_sidecar_types.get(db, set()):
                matching_sidecars.append(
                    {
                        "name": str(entry.get("name") or "").strip() or None,
                        "type": sidecar_type,
                    }
                )
    allow_network = _bool_or_none(policy.get("allow_network"))
    if allow_network is None:
        allow_network = False
    network_mode = str(policy.get("network_mode") or ("bridge" if allow_network else "none")).strip() or "none"
    network_enabled = bool(allow_network and network_mode.lower() != "none")

    issues: List[str] = []
    status = "not_required"
    reason = "bundle does not require external DB/service sidecars"
    if requires_external_db:
        status = "configured"
        reason = "executor policy satisfies external DB/service requirements"
        if not runtime_allow_external_db:
            issues.append("runtime.allow_external_db=false")
        if not sidecars_declared:
            issues.append("policy.executor.sidecars missing")
        elif required_types and not matching_sidecars:
            issues.append(f"policy.executor.sidecars missing compatible db sidecar ({'/'.join(required_types)})")
        if not network_enabled:
            issues.append("policy.executor.allow_network/network_mode disables sidecars")
        if issues:
            status = "misconfigured"
            reason = ", ".join(issues)

    return {
        "requires_external_db": bool(requires_external_db),
        "runtime_allow_external_db": runtime_allow_external_db,
        "db": db or None,
        "sidecars_declared": sidecars_declared,
        "required_sidecar_types": required_types,
        "matching_sidecars": matching_sidecars,
        "network_enabled": network_enabled,
        "network_mode": network_mode,
        "status": status,
        "reason": reason,
        "issues": issues,
    }


def write_generator_contract(metadata_dir: Path, payload: Dict[str, Any]) -> Path:
    resolved_path = _resolved_contract_path(metadata_dir)
    legacy_path = _legacy_contract_path(metadata_dir)
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    resolved_path.write_text(text, encoding="utf-8")
    legacy_path.write_text(text, encoding="utf-8")
    profile = payload.get("semantic_profile")
    if isinstance(profile, dict):
        _semantic_profile_path(metadata_dir).write_text(
            json.dumps(profile, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    return resolved_path


def build_generator_contract(
    *,
    sid: str,
    vuln_id: str,
    metadata_dir: Path,
    workspace_dir: Optional[Path] = None,
    generator_mode: str = "",
    bundle_slug: str = "",
    researcher_report: Optional[Dict[str, Any]] = None,
    requirement: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a normalized generator contract for a single bundle.

    Contract priority:
    - resolved rule contract (static/runtime merge via ``load_rule``)
    - generator manifest PoC contract
    - template metadata contract
    - defaults
    """

    template = _load_json(metadata_dir / "generator_template.json") or {}
    manifest_payload = _load_json(metadata_dir / "generator_manifest.json") or {}
    manifest = _unwrap_manifest(manifest_payload)
    has_manifest = isinstance(manifest.get("files"), list) and bool(manifest.get("files"))
    provenance = _resolve_generation_provenance(
        generator_mode=generator_mode,
        manifest_payload=manifest_payload,
        template_summary=template,
        has_manifest=has_manifest,
    )
    rule = load_rule(vuln_id) or {}
    rulespec = load_rulespec(vuln_id)
    report = normalize_researcher_report_payload(
        researcher_report if isinstance(researcher_report, dict) else (_load_json(metadata_dir / "researcher_report.json") or {})
    )
    guard_spec = _load_json(metadata_dir / "guard_spec.json") or {}
    proposal = _merge_proposed_verification_contracts(
        _normalize_proposed_verification_contract(report),
        _manifest_proposed_verification_contract(manifest),
    )
    semantic_contract = _resolve_semantic_contract(
        vuln_id,
        report,
        guard_spec,
        requirement if isinstance(requirement, dict) else {},
    )

    sources: Dict[str, str] = {}

    service_entry = _manifest_role_path(manifest, "service_main")
    if service_entry:
        sources["service_entry"] = "generator_manifest.manifest.files(role=service_main)"
    else:
        service_entry = _string_or_none(template.get("service_entry"))
        if service_entry:
            sources["service_entry"] = "generator_template.service_entry"
        else:
            service_entry = _string_or_none(getattr(rulespec, "service_entry", None))
            if service_entry:
                sources["service_entry"] = "rulespec.service_entry"
            else:
                service_entry = "app.py"
                sources["service_entry"] = "default(app.py)"

    poc_entry = _manifest_role_path(manifest, "poc_entry") or _first_poc_like_path(manifest)
    if poc_entry:
        sources["poc_entry"] = "generator_manifest.manifest.files(role=poc_entry|name=poc.*)"
    else:
        poc_entry = _string_or_none(template.get("poc_entry"))
        if poc_entry:
            sources["poc_entry"] = "generator_template.poc_entry"
        else:
            poc_entry = _string_or_none(getattr(rulespec, "poc_entry", None))
            if poc_entry:
                sources["poc_entry"] = "rulespec.poc_entry"
            else:
                poc_entry = "poc.py"
                sources["poc_entry"] = "default(poc.py)"

    service_port = _port_from_generator_manifest(manifest)
    if service_port:
        sources["service_port"] = "generator_manifest.manifest.run.port|command"
    else:
        service_port = _port_from_generator_template(template)
        if service_port:
            sources["service_port"] = "generator_template.ports|service_port|port"
        else:
            service_port = _port_from_dockerfile(workspace_dir) if workspace_dir else None
            if service_port:
                sources["service_port"] = "Dockerfile(EXPOSE)"
            else:
                service_port = DEFAULT_APP_PORT
                sources["service_port"] = f"default({DEFAULT_APP_PORT})"

    base_url = f"http://127.0.0.1:{service_port}"
    sources["base_url"] = "service_port"

    service_env = _service_env_from_generator_manifest(manifest)
    if service_env:
        sources["service_env"] = "generator_manifest.manifest.run.env"
    else:
        service_env = _service_env_from_generator_template(template)
        if service_env:
            sources["service_env"] = "generator_template.service_env"
        else:
            compiler_strategy_hint = resolve_compiler_strategy(vuln_id, requirement or {})
            service_env = derive_service_env(
                compiler_strategy=compiler_strategy_hint,
                requirement=requirement or {},
                service_port=service_port,
            )
            if service_env:
                sources["service_env"] = "requirement+compiler_strategy"

    poc_cmd = _string_or_none(_dig(manifest, "poc", "cmd"))
    if poc_cmd:
        sources["poc_cmd"] = "generator_manifest.manifest.poc.cmd"

    success_signature = _string_or_none(rule.get("success_signature"))
    if success_signature:
        sources["success_signature"] = "rule.success_signature"
    else:
        success_signature = _string_or_none(_dig(manifest, "poc", "success_signature"))
        if success_signature:
            sources["success_signature"] = "generator_manifest.manifest.poc.success_signature"
        else:
            success_signature = _string_or_none(template.get("success_signature"))
            if success_signature:
                sources["success_signature"] = "generator_template.success_signature"
            else:
                success_signature = _string_or_none((proposal or {}).get("success_signature"))
                if success_signature:
                    sources["success_signature"] = "researcher_report.verification_spec.success_text_markers[0]"

    flag_token = _string_or_none(rule.get("flag_token"))
    if flag_token:
        sources["flag_token"] = "rule.flag_token"
    else:
        flag_token = _string_or_none(_dig(manifest, "poc", "flag_token"))
        if flag_token:
            sources["flag_token"] = "generator_manifest.manifest.poc.flag_token"
        else:
            flag_token = _string_or_none(template.get("flag_token"))
            if flag_token:
                sources["flag_token"] = "generator_template.flag_token"
            else:
                flag_token = _string_or_none(getattr(rulespec, "template_flag_token", None))
                if flag_token:
                    sources["flag_token"] = "rulespec.template_flag_token"
                else:
                    flag_token = _string_or_none((proposal or {}).get("flag_token"))
                    if flag_token:
                        sources["flag_token"] = "researcher_report.verification_spec.flag_token"

    output_mode = _contract_output_mode(rule)
    if output_mode:
        sources["output_mode"] = "rule.output"
    else:
        output_mode = "auto"
        sources["output_mode"] = "default(auto)"

    runtime_recipe = _build_runtime_recipe(
        requirement=requirement or {},
        manifest=manifest,
        template=template,
        resolved={
            "service_entry": service_entry,
            "poc_entry": poc_entry,
            "service_port": service_port,
            "service_env": service_env,
            "output_mode": output_mode,
        },
        researcher_report=report,
    )
    recipe_service_env = runtime_recipe.get("service_env") if isinstance(runtime_recipe.get("service_env"), dict) else {}
    if recipe_service_env:
        service_env = deepcopy(recipe_service_env)
        sources["service_env"] = str(runtime_recipe.get("service_env_source") or sources.get("service_env") or "runtime_recipe")

    resolved_payload = {
        "service_entry": service_entry,
        "poc_entry": poc_entry,
        "service_port": service_port,
        "base_url": base_url,
        "service_env": deepcopy(service_env),
        "poc_cmd": poc_cmd,
        "output_mode": output_mode,
        "success_signature": success_signature,
        "flag_token": flag_token,
    }
    runtime_graph = _build_runtime_graph(
        runtime_recipe=runtime_recipe,
        resolved=resolved_payload,
    )
    executor_plan = _build_executor_plan(
        runtime_recipe=runtime_recipe,
        runtime_graph=runtime_graph,
        resolved=resolved_payload,
    )

    payload: Dict[str, Any] = {
        "schema_version": RESOLVED_CONTRACT_SCHEMA_VERSION,
        "sid": sid,
        "slug": bundle_slug,
        "vuln_id": vuln_id,
        "generator_mode": generator_mode,
        "contract_stage": generator_mode or ("generator" if workspace_dir else "seed"),
        "resolved": resolved_payload,
        "sources": sources,
    }
    if runtime_recipe:
        payload["runtime_recipe"] = runtime_recipe
    if runtime_graph:
        payload["runtime_graph"] = runtime_graph
    if executor_plan:
        payload["executor_plan"] = executor_plan
    exploit_oracle = _build_exploit_oracle(
        resolved=payload["resolved"],
        proposal=proposal or {},
        sources=sources,
    )
    if exploit_oracle:
        payload["exploit_oracle"] = exploit_oracle
    evidence_graph = deepcopy(report.get("evidence_graph")) if isinstance(report.get("evidence_graph"), dict) else {}
    if evidence_graph:
        payload["evidence_graph"] = evidence_graph
    enriched_request_ir = _enriched_request_ir(
        requirement=requirement or {},
        report=report,
        runtime_recipe=runtime_recipe,
        evidence_graph=evidence_graph,
    )
    runtime_recipe, runtime_graph, executor_plan = _enrich_runtime_contract_surfaces(
        request_ir=enriched_request_ir,
        runtime_recipe=runtime_recipe,
        runtime_graph=runtime_graph,
        executor_plan=executor_plan,
    )
    if runtime_recipe:
        payload["runtime_recipe"] = deepcopy(runtime_recipe)
    if runtime_graph:
        payload["runtime_graph"] = deepcopy(runtime_graph)
    if executor_plan:
        payload["executor_plan"] = deepcopy(executor_plan)
    if enriched_request_ir:
        payload["request_ir"] = deepcopy(enriched_request_ir)
    name_only_generation_spec = _build_name_only_generation_spec(
        requirement=requirement or {},
        report=report,
        runtime_recipe=runtime_recipe,
        runtime_graph=runtime_graph,
        evidence_graph=evidence_graph,
        exploit_oracle=exploit_oracle,
        request_ir=enriched_request_ir,
    )
    if name_only_generation_spec:
        payload["name_only_generation_spec"] = name_only_generation_spec
    staged_synthesis = _build_staged_synthesis(
        requirement=requirement or {},
        request_ir=enriched_request_ir,
        runtime_recipe=runtime_recipe,
        executor_plan=executor_plan,
        exploit_oracle=exploit_oracle,
        name_only_generation_spec=name_only_generation_spec,
        manifest=manifest,
        workspace_dir=workspace_dir,
        resolved=resolved_payload,
    )
    if staged_synthesis:
        payload["staged_synthesis"] = staged_synthesis
    if provenance:
        payload["provenance"] = provenance
    selection_branch_trace = _build_selection_branch_trace(
        request_ir=enriched_request_ir,
        staged_synthesis=staged_synthesis,
        provenance=provenance or {},
    )
    if selection_branch_trace:
        payload["selection_branch_trace"] = selection_branch_trace
    if proposal:
        payload["proposed_verification_contract"] = proposal
    if semantic_contract:
        payload["semantic_contract"] = semantic_contract

    if not has_manifest:
        scenario_type = _string_or_none(template.get("scenario_type"))
        if scenario_type:
            payload["scenario_type"] = scenario_type
            sources.setdefault("scenario_type", "generator_template.scenario_type")
        else:
            scenario_type = _string_or_none(getattr(rulespec, "scenario_type", None))
            if scenario_type:
                payload["scenario_type"] = scenario_type
                sources.setdefault("scenario_type", "rulespec.scenario_type")
        template_id = _string_or_none(template.get("template_id"))
        if template_id:
            payload["template_id"] = template_id
            sources.setdefault("template_id", "generator_template.template_id")
        pattern_id = _string_or_none(template.get("pattern_id"))
        if pattern_id:
            payload["pattern_id"] = pattern_id
            sources.setdefault("pattern_id", "generator_template.pattern_id")
        for key in (
            "template_stack_id",
            "template_language",
            "template_framework",
            "requested_stack_id",
            "template_runtime_surface_status",
            "template_runtime_surface_reason",
        ):
            value = _string_or_none(template.get(key))
            if value:
                payload[key] = value
                sources.setdefault(key, f"generator_template.{key}")
        stack_match = _bool_or_none(template.get("template_stack_match"))
        if stack_match is not None:
            payload["template_stack_match"] = stack_match
            sources.setdefault("template_stack_match", "generator_template.template_stack_match")
        runtime_diagnostics = template.get("template_runtime_diagnostics")
        if isinstance(runtime_diagnostics, dict) and runtime_diagnostics:
            payload["template_runtime_diagnostics"] = deepcopy(runtime_diagnostics)
            sources.setdefault("template_runtime_diagnostics", "generator_template.template_runtime_diagnostics")

    payload["rule_resolution"] = _resolve_rule_sources(vuln_id)

    # Keep backward-compatible fields at the top-level for convenience.
    if success_signature:
        payload["success_signature"] = success_signature
        payload["poc_success_signature"] = success_signature
    if flag_token:
        payload["flag_token"] = flag_token
        payload["poc_flag_token"] = flag_token
    payload["output_mode"] = output_mode
    payload["service_entry"] = service_entry
    payload["poc_entry"] = poc_entry
    payload["service_port"] = service_port
    payload["base_url"] = base_url
    if service_env:
        payload["service_env"] = deepcopy(service_env)
    if runtime_recipe:
        payload["runtime_recipe"] = deepcopy(runtime_recipe)
    if runtime_graph:
        payload["runtime_graph"] = deepcopy(runtime_graph)
    if executor_plan:
        payload["executor_plan"] = deepcopy(executor_plan)
    if evidence_graph:
        payload["evidence_graph"] = deepcopy(evidence_graph)
    if enriched_request_ir:
        payload["request_ir"] = deepcopy(enriched_request_ir)
    if exploit_oracle:
        payload["exploit_oracle"] = deepcopy(exploit_oracle)
    if name_only_generation_spec:
        payload["name_only_generation_spec"] = deepcopy(name_only_generation_spec)
    if staged_synthesis:
        payload["staged_synthesis"] = deepcopy(staged_synthesis)
    if selection_branch_trace:
        payload["selection_branch_trace"] = deepcopy(selection_branch_trace)
    generation_origin = _string_or_none(provenance.get("generation_origin")) if provenance else None
    if generation_origin:
        payload["generation_origin"] = generation_origin
    fallback_used = _bool_or_none(provenance.get("fallback_used")) if provenance else None
    if fallback_used is not None:
        payload["fallback_used"] = fallback_used
    fallback_class = _string_or_none(provenance.get("fallback_class")) if provenance else None
    if fallback_class:
        payload["fallback_class"] = fallback_class
    family_override_applied = _bool_or_none(provenance.get("family_override_applied")) if provenance else None
    if family_override_applied is not None:
        payload["family_override_applied"] = family_override_applied
    llm_stub_used = _bool_or_none(provenance.get("llm_stub_used")) if provenance else None
    if llm_stub_used is not None:
        payload["llm_stub_used"] = llm_stub_used
    llm_fixture_used = _bool_or_none(provenance.get("llm_fixture_used")) if provenance else None
    if llm_fixture_used is not None:
        payload["llm_fixture_used"] = llm_fixture_used
    llm_provider_attempted = _bool_or_none(provenance.get("llm_provider_attempted")) if provenance else None
    if llm_provider_attempted is not None:
        payload["llm_provider_attempted"] = llm_provider_attempted
    llm_provider_succeeded = _bool_or_none(provenance.get("llm_provider_succeeded")) if provenance else None
    if llm_provider_succeeded is not None:
        payload["llm_provider_succeeded"] = llm_provider_succeeded
    llm_failure_class = _string_or_none(provenance.get("llm_failure_class")) if provenance else None
    if llm_failure_class:
        payload["llm_failure_class"] = llm_failure_class
    llm_execution = provenance.get("llm_execution") if isinstance(provenance, dict) else None
    if isinstance(llm_execution, dict) and llm_execution:
        payload["llm_execution"] = deepcopy(llm_execution)
    if poc_cmd:
        payload["poc_cmd"] = poc_cmd
    if semantic_contract.get("semantic_signature"):
        payload["semantic_signature"] = semantic_contract["semantic_signature"]
    if semantic_contract.get("semantic_signature_source"):
        payload["semantic_signature_source"] = semantic_contract["semantic_signature_source"]
    semantic_profile = _build_semantic_profile(
        sid=sid,
        bundle_slug=bundle_slug,
        vuln_id=vuln_id,
        requirement=requirement or {},
        semantic_contract=semantic_contract,
        proposed_verification_contract=proposal or {},
        resolved=payload["resolved"],
        rule_resolution=payload["rule_resolution"],
    )
    payload["semantic_profile"] = semantic_profile
    payload["lower_bound"] = deepcopy(semantic_profile.get("lower_bound") or {})
    payload["compiler_supported"] = bool(semantic_profile.get("compiler_supported"))
    payload["compiler_strategy"] = _string_or_none(semantic_profile.get("compiler_strategy"))
    payload["compiler_reason"] = _string_or_none(semantic_profile.get("compiler_reason"))
    lower_bound = payload.get("lower_bound") if isinstance(payload.get("lower_bound"), dict) else {}
    for key in ("family_non_remote_available", "effective_non_remote_available", "compiler_path_enabled"):
        value = lower_bound.get(key)
        if isinstance(value, bool):
            payload[key] = value
    manifest_metadata = manifest.get("metadata") if isinstance(manifest, dict) else {}
    if isinstance(manifest_metadata, dict):
        for key in ("compiler_family", "stack_scaffold_id", "stack_scaffold_version", "fragment_id", "compose_mode"):
            value = _string_or_none(manifest_metadata.get(key))
            if value:
                payload[key] = value
    return payload


def _build_semantic_profile(
    *,
    sid: str,
    bundle_slug: str,
    vuln_id: str,
    requirement: Dict[str, Any],
    semantic_contract: Dict[str, Any],
    proposed_verification_contract: Dict[str, Any],
    resolved: Dict[str, Any],
    rule_resolution: Dict[str, Any],
) -> Dict[str, Any]:
    defaults = _semantic_profile_defaults(vuln_id)
    compiler_summary = compiler_support_summary(vuln_id, requirement)
    lower_bound = lower_bound_summary(vuln_id, requirement)
    support_level = str(compiler_summary.get("support_level") or "unsupported").strip().lower()
    compiler_strategy = _string_or_none(compiler_summary.get("compiler_strategy")) or ""
    compiler_supported = bool(compiler_summary.get("compiler_supported"))
    compiler_reason = _string_or_none(compiler_summary.get("compiler_reason")) or ""

    verification_contract = {
        "success_signature": _string_or_none(resolved.get("success_signature")),
        "flag_token": _string_or_none(resolved.get("flag_token")),
        "output_mode": _string_or_none(resolved.get("output_mode")) or "auto",
    }
    if isinstance(proposed_verification_contract.get("assertion_program"), list):
        verification_contract["assertion_program"] = deepcopy(
            proposed_verification_contract.get("assertion_program") or []
        )
    for key in ("success_mode", "json_success_key", "json_success_value", "json_flag_key", "override_static"):
        if key in proposed_verification_contract:
            verification_contract[key] = deepcopy(proposed_verification_contract.get(key))

    semantic_signature = _normalize_semantic_buckets(semantic_contract.get("semantic_signature"))
    signature_source = semantic_contract.get("semantic_signature_source")
    if isinstance(signature_source, str):
        signature_source = [signature_source]
    if not isinstance(signature_source, list):
        signature_source = []
    if not _semantic_signature_present(semantic_signature):
        semantic_signature, default_signature_source = _default_profile_semantic_signature(
            vuln_id=vuln_id,
            requirement=requirement,
        )
        if default_signature_source and not signature_source:
            signature_source = list(default_signature_source)
    profile: Dict[str, Any] = {
        "schema_version": SEMANTIC_PROFILE_SCHEMA_VERSION,
        "sid": sid,
        "slug": bundle_slug,
        "requested_name": _requested_name(requirement, vuln_id),
        "normalized_vuln_id": str(vuln_id or "").strip(),
        "family": defaults.get("family") or _fallback_family_label(vuln_id),
        "support_level": support_level,
        "compiler_strategy": compiler_strategy,
        "compiler_supported": compiler_supported,
        "compiler_reason": compiler_reason,
        "stack_profile": _stack_profile(requirement),
        "scenario_shape": {
            "service_entry": _string_or_none(resolved.get("service_entry")) or "app.py",
            "poc_entry": _string_or_none(resolved.get("poc_entry")) or "poc.py",
            "service_port": resolved.get("service_port") or DEFAULT_APP_PORT,
            "base_url": _string_or_none(resolved.get("base_url")),
        },
        "semantic_signature": semantic_signature,
        "verification_contract": verification_contract,
        "derived_assertions": {
            "semantic_gate_required": requires_semantic_support_for_requirement(vuln_id, requirement),
            "semantic_status": _string_or_none(semantic_contract.get("status")) or "unsupported",
            "rule_source": _string_or_none(rule_resolution.get("selected_source")) or "none",
            "service_entry": _string_or_none(resolved.get("service_entry")) or "app.py",
            "service_port": resolved.get("service_port") or DEFAULT_APP_PORT,
        },
        "evidence_relevance": deepcopy(semantic_contract.get("evidence_relevance"))
        if isinstance(semantic_contract.get("evidence_relevance"), dict)
        else {},
        "lower_bound": lower_bound,
    }
    if signature_source:
        profile["semantic_signature_source"] = list(signature_source)
    return profile


def _default_profile_semantic_signature(
    *,
    vuln_id: str,
    requirement: Dict[str, Any],
) -> tuple[Dict[str, list[str]], list[str]]:
    requested_name = _requested_name(requirement, vuln_id)
    pattern_id = _string_or_none(requirement.get("pattern_id")) if isinstance(requirement, dict) else None
    try:
        from agents.generator.flask_fragment_registry import fragment_semantic_signature

        fragment_signature = _normalize_semantic_buckets(
            fragment_semantic_signature(
                vuln_id,
                pattern_id=pattern_id or "",
                raw_label=requested_name,
            )
        )
    except Exception:
        fragment_signature = _normalize_semantic_buckets({})
    if _semantic_signature_present(fragment_signature):
        return fragment_signature, ["fragment_registry"]

    baseline_signature = _normalize_semantic_buckets(baseline_semantic_signature(vuln_id))
    if _semantic_signature_present(baseline_signature):
        return baseline_signature, ["baseline"]
    return _normalize_semantic_buckets({}), []


def _requested_name(requirement: Dict[str, Any], vuln_id: str) -> str:
    if isinstance(requirement, dict):
        request_ir = requirement.get("request_ir")
        if isinstance(request_ir, dict):
            value = _string_or_none(request_ir.get("request_label"))
            if value:
                return value
        for key in ("vuln_name", "requested_name", "name"):
            value = _string_or_none(requirement.get(key))
            if value:
                return value
        value = _string_or_none(requirement.get("vuln_id"))
        if value:
            return value
    token = str(vuln_id or "").strip()
    if token.upper().startswith("NAME-"):
        return token[5:].replace("-", " ")
    return token


def _stack_hypotheses(requirement: Dict[str, Any]) -> list[Dict[str, str]]:
    raw = requirement.get("stack_hypotheses") if isinstance(requirement, dict) else None
    if not isinstance(raw, list):
        return []
    hypotheses: list[Dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        language = _string_or_none(entry.get("language"))
        framework = _string_or_none(entry.get("framework"))
        if not language or not framework:
            continue
        key = (language.lower(), framework.lower())
        if key in seen:
            continue
        seen.add(key)
        hypotheses.append(
            {
                "language": language.lower(),
                "framework": framework.lower(),
                "stack_id": _string_or_none(entry.get("stack_id")) or f"{language.lower()}/{framework.lower()}",
                "source": _string_or_none(entry.get("source")) or "unknown",
                "confidence": _string_or_none(entry.get("confidence")) or "unknown",
            }
        )
    return hypotheses


def _researcher_stack_candidates(report: Dict[str, Any]) -> list[Dict[str, Any]]:
    if not isinstance(report, dict):
        return []
    raw = report.get("tech_stack_candidates")
    if not isinstance(raw, list):
        return []
    candidates: list[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        language = _string_or_none(entry.get("language"))
        framework = _string_or_none(entry.get("framework"))
        if not language or not framework:
            continue
        key = (language.lower(), framework.lower())
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            {
                "language": language.lower(),
                "framework": framework.lower(),
                "stack_id": _string_or_none(entry.get("stack_id")) or f"{language.lower()}/{framework.lower()}",
                "source": "researcher_candidate",
                "confidence": _string_or_none(entry.get("confidence")) or "unknown",
                "score": entry.get("score"),
                "sources": (
                    [
                        str(item).strip().lower()
                        for item in (entry.get("sources") or [])
                        if isinstance(item, str) and str(item).strip()
                    ]
                    if isinstance(entry.get("sources"), list)
                    else []
                ),
            }
        )
    return candidates


def _stack_confidence_rank(value: str) -> int:
    token = str(value or "").strip().lower()
    if token == "high":
        return 3
    if token == "medium":
        return 2
    if token == "low":
        return 1
    return 0


def _stack_candidate_score(entry: Dict[str, Any]) -> float:
    try:
        return float(entry.get("score") or 0.0)
    except Exception:
        return 0.0


def _stack_candidate_sources(entry: Dict[str, Any]) -> list[str]:
    if not isinstance(entry, dict):
        return []
    raw = entry.get("sources")
    if not isinstance(raw, list):
        return []
    return [
        str(item).strip().lower()
        for item in raw
        if isinstance(item, str) and str(item).strip()
    ]


def _stack_candidate_has_text_evidence(entry: Dict[str, Any]) -> bool:
    sources = set(_stack_candidate_sources(entry))
    return "search_hit_text" in sources or "explicit_requirement" in sources


def _preferred_researcher_stack_candidate(candidates: list[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(candidates, list) or not candidates:
        return {}
    normalized = [entry for entry in candidates if isinstance(entry, dict)]
    if not normalized:
        return {}
    top = normalized[0]
    confidence = str(top.get("confidence") or "").strip().lower()
    confidence_rank = _stack_confidence_rank(confidence)
    if confidence_rank < _stack_confidence_rank("medium"):
        return {}
    has_text_evidence = _stack_candidate_has_text_evidence(top)
    if not has_text_evidence:
        return {}
    if len(normalized) == 1:
        return top
    second_score = _stack_candidate_score(normalized[1])
    top_margin = _stack_candidate_score(top) - second_score
    required_margin = 0.15 if confidence_rank >= _stack_confidence_rank("high") else 0.25
    if top_margin < required_margin:
        return {}
    return top


def _family_confidence_rank(value: Any) -> int:
    token = str(value or "").strip().lower()
    if token == "high":
        return 3
    if token == "medium":
        return 2
    if token == "low":
        return 1
    return 0


def _is_request_resolution_family_source(value: Any) -> bool:
    token = str(value or "").strip().lower()
    return token in {
        "catalog_resolution",
        "request_resolution",
        "request_ir",
        "request_ir_fallback",
        "request_identity",
        "request_identity_fallback",
        "label_overlap",
    }


def _material_family_candidates(candidates: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    if not isinstance(candidates, list) or not candidates:
        return []
    normalized = [entry for entry in candidates if isinstance(entry, dict)]
    if not normalized:
        return []
    top = normalized[0]
    top_source = str(top.get("source") or "").strip().lower()
    top_confidence = _family_confidence_rank(top.get("confidence"))
    strong_request_resolution = _is_request_resolution_family_source(top_source) and top_confidence >= _family_confidence_rank("high")

    material: list[Dict[str, Any]] = []
    seen: set[str] = set()
    for index, entry in enumerate(normalized):
        family = _string_or_none(entry.get("family"))
        if not family:
            continue
        family = family.lower()
        if family in seen:
            continue
        include = False
        source = str(entry.get("source") or "").strip().lower()
        confidence_rank = _family_confidence_rank(entry.get("confidence"))
        if index == 0:
            include = True
        elif strong_request_resolution:
            include = _is_request_resolution_family_source(source) or confidence_rank >= _family_confidence_rank("high")
        else:
            include = _is_request_resolution_family_source(source) or confidence_rank >= _family_confidence_rank("medium")
        if not include:
            continue
        seen.add(family)
        material.append(entry)
    return material


def _merge_stack_candidates(*groups: list[Dict[str, str]]) -> list[Dict[str, str]]:
    merged: list[Dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for group in groups:
        for entry in group or []:
            if not isinstance(entry, dict):
                continue
            language = _string_or_none(entry.get("language"))
            framework = _string_or_none(entry.get("framework"))
            if not language or not framework:
                continue
            key = (language.lower(), framework.lower())
            if key in seen:
                continue
            seen.add(key)
            merged.append(
                {
                    "language": language.lower(),
                    "framework": framework.lower(),
                    "stack_id": _string_or_none(entry.get("stack_id")) or f"{language.lower()}/{framework.lower()}",
                    "source": _string_or_none(entry.get("source")) or "unknown",
                    "confidence": _string_or_none(entry.get("confidence")) or "unknown",
                }
            )
    return merged


def _stack_profile(requirement: Dict[str, Any], report: Dict[str, Any] | None = None) -> Dict[str, Any]:
    runtime = requirement.get("runtime") if isinstance(requirement, dict) else {}
    runtime = runtime if isinstance(runtime, dict) else {}
    explicit_language = _string_or_none(requirement.get("language") if isinstance(requirement, dict) else None)
    explicit_framework = _string_or_none(requirement.get("framework") if isinstance(requirement, dict) else None)
    requirement_hypotheses = _stack_hypotheses(requirement if isinstance(requirement, dict) else {})
    researcher_hypotheses = _researcher_stack_candidates(report or {})
    confident_researcher_hypothesis = _preferred_researcher_stack_candidate(researcher_hypotheses)
    hypotheses = _merge_stack_candidates(researcher_hypotheses, requirement_hypotheses)
    if explicit_language and explicit_framework:
        language = explicit_language.lower()
        framework = explicit_framework.lower()
        stack_source = "explicit_requirement"
        stack_locked = True
    elif confident_researcher_hypothesis:
        top = confident_researcher_hypothesis
        language = _string_or_none(top.get("language")) or "python"
        framework = _string_or_none(top.get("framework")) or "flask"
        stack_source = "researcher_candidate"
        stack_locked = False
    elif requirement_hypotheses:
        top = requirement_hypotheses[0]
        language = _string_or_none(top.get("language")) or "python"
        framework = _string_or_none(top.get("framework")) or "flask"
        stack_source = _string_or_none(top.get("source")) or "stack_hypothesis"
        stack_locked = False
    elif hypotheses:
        top = hypotheses[0]
        language = _string_or_none(top.get("language")) or "python"
        framework = _string_or_none(top.get("framework")) or "flask"
        stack_source = _string_or_none(top.get("source")) or "stack_hypothesis"
        stack_locked = False
    else:
        language = "python"
        framework = "flask"
        stack_source = "default_stack_profile"
        stack_locked = False
    selected_stack_id = f"{language}/{framework}"
    stack_defaulted = bool(
        not stack_locked
        and stack_source in {"default_stack_profile", "profile_prior", "available_skeleton"}
    )
    stack_selection: Dict[str, Any] = {
        "selected_stack_id": selected_stack_id,
        "source": stack_source,
        "resolved": False,
    }
    if stack_locked and stack_source == "explicit_requirement":
        stack_selection.update(
            {
                "resolved": True,
                "confidence": "high",
                "basis": "explicit_requirement",
            }
        )
    elif stack_source == "researcher_candidate" and confident_researcher_hypothesis:
        second_score = _stack_candidate_score(researcher_hypotheses[1]) if len(researcher_hypotheses) > 1 else 0.0
        top_score = _stack_candidate_score(confident_researcher_hypothesis)
        stack_selection.update(
            {
                "resolved": True,
                "confidence": _string_or_none(confident_researcher_hypothesis.get("confidence")) or "unknown",
                "score": round(top_score, 3),
                "margin": round(max(0.0, top_score - second_score), 3),
                "basis": "researcher_top_candidate",
                "evidence_backed": _stack_candidate_has_text_evidence(confident_researcher_hypothesis),
                "sources": _stack_candidate_sources(confident_researcher_hypothesis),
            }
        )
    elif stack_source in {"profile_prior", "available_skeleton", "default_stack_profile"}:
        stack_selection.update(
            {
                "basis": "repo_prior_default",
                "confidence": "low",
            }
        )
    elif stack_source == "stack_hypothesis":
        stack_selection.update(
            {
                "basis": "soft_stack_hypothesis",
                "confidence": "low",
            }
        )
    return {
        "language": language,
        "framework": framework,
        "base_image": _string_or_none(runtime.get("base_image"))
        or _string_or_none(requirement.get("base_image") if isinstance(requirement, dict) else None)
        or "python:3.11-slim",
        "package_manager": _string_or_none(runtime.get("package_manager"))
        or _string_or_none(requirement.get("package_manager") if isinstance(requirement, dict) else None)
        or "pip",
        "generator_mode": _string_or_none(requirement.get("generator_mode") if isinstance(requirement, dict) else None)
        or "synthesis",
        "stack_source": stack_source,
        "stack_locked": stack_locked,
        "stack_defaulted": stack_defaulted,
        "stack_hypotheses": hypotheses,
        "stack_selection": stack_selection,
    }


def _semantic_profile_defaults(vuln_id: str) -> Dict[str, str]:
    token = normalize_vuln_id(vuln_id).upper().replace("_", "-")
    if not token:
        token = str(vuln_id or "").strip().upper().replace("_", "-")
    defaults = _SEMANTIC_PROFILE_DEFAULTS.get(token)
    if defaults:
        return dict(defaults)
    if token.startswith("NAME-"):
        return {
            "family": token[5:].lower().replace("-", "_"),
            "support_level": "unsupported",
            "compiler_strategy": "",
        }
    if load_static_rule(vuln_id):
        normalized = normalize_vuln_id(vuln_id).replace("-", "_")
        return {
            "family": normalized or "builtin_family",
            "support_level": "builtin_supported",
            "compiler_strategy": "",
        }
    return {
        "family": _fallback_family_label(vuln_id),
        "support_level": "unsupported",
        "compiler_strategy": "",
    }


def _fallback_family_label(vuln_id: str) -> str:
    token = str(vuln_id or "").strip().lower().replace("-", "_")
    if token.startswith("name_"):
        return token[5:] or "unsupported_family"
    if token.startswith("cwe_"):
        return token
    if token:
        return token
    return "unsupported_family"


def _compiler_strategy_supported(strategy: str, requirement: Optional[Dict[str, Any]] = None) -> bool:
    token = str(strategy or "").strip()
    if not token:
        return False
    try:
        from agents.generator.compiler import supported_compiler_strategies
        stack_name = None
        if isinstance(requirement, dict):
            language = str(requirement.get("language") or "python").strip().lower()
            framework = str(requirement.get("framework") or "flask").strip().lower()
            stack_name = f"{language}/{framework}"
        return token in supported_compiler_strategies(stack_name)
    except Exception:
        return False


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _unwrap_manifest(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    inner = payload.get("manifest")
    return inner if isinstance(inner, dict) else payload


def _resolve_generation_provenance(
    *,
    generator_mode: str,
    manifest_payload: Dict[str, Any],
    template_summary: Dict[str, Any],
    has_manifest: bool,
) -> Dict[str, Any]:
    provenance: Dict[str, Any] = {}

    manifest_origin = _string_or_none(manifest_payload.get("generation_origin")) if isinstance(manifest_payload, dict) else None
    template_origin = _string_or_none(template_summary.get("generation_origin")) if isinstance(template_summary, dict) else None

    if manifest_origin:
        provenance["generation_origin"] = manifest_origin
        provenance["source"] = "generator_manifest"
    elif template_origin:
        provenance["generation_origin"] = template_origin
        provenance["source"] = "generator_template"
    elif generator_mode in {"template", "hybrid-template"}:
        provenance["generation_origin"] = "built_in_template"
        provenance["source"] = "generator_mode"
    elif has_manifest:
        provenance["generation_origin"] = "llm_manifest"
        provenance["source"] = "generator_manifest"

    fallback_used = _bool_or_none(manifest_payload.get("fallback_used")) if isinstance(manifest_payload, dict) else None
    if fallback_used is None and isinstance(template_summary, dict):
        fallback_used = _bool_or_none(template_summary.get("fallback_used"))
    if fallback_used is not None:
        provenance["fallback_used"] = fallback_used

    family_override_applied = _bool_or_none(manifest_payload.get("family_override_applied")) if isinstance(manifest_payload, dict) else None
    if family_override_applied is None and isinstance(template_summary, dict):
        family_override_applied = _bool_or_none(template_summary.get("family_override_applied"))
    if family_override_applied is not None:
        provenance["family_override_applied"] = family_override_applied

    llm_execution = manifest_payload.get("llm_execution") if isinstance(manifest_payload, dict) else None
    if not isinstance(llm_execution, dict) and isinstance(template_summary, dict):
        llm_execution = template_summary.get("llm_execution")
    if isinstance(llm_execution, dict) and llm_execution:
        provenance["llm_execution"] = deepcopy(llm_execution)

    llm_stub_used = _bool_or_none(manifest_payload.get("llm_stub_used")) if isinstance(manifest_payload, dict) else None
    if llm_stub_used is None and isinstance(llm_execution, dict):
        llm_stub_used = _bool_or_none(llm_execution.get("stub_fallback"))
    if llm_stub_used is None and isinstance(template_summary, dict):
        llm_stub_used = _bool_or_none(template_summary.get("llm_stub_used"))
    if llm_stub_used is not None:
        provenance["llm_stub_used"] = llm_stub_used

    llm_fixture_used = _bool_or_none(manifest_payload.get("llm_fixture_used")) if isinstance(manifest_payload, dict) else None
    if llm_fixture_used is None and isinstance(llm_execution, dict):
        llm_fixture_used = _bool_or_none(llm_execution.get("fixture_used"))
    if llm_fixture_used is None and isinstance(template_summary, dict):
        llm_fixture_used = _bool_or_none(template_summary.get("llm_fixture_used"))
    if llm_fixture_used is not None:
        provenance["llm_fixture_used"] = llm_fixture_used

    llm_provider_attempted = _bool_or_none(manifest_payload.get("llm_provider_attempted")) if isinstance(manifest_payload, dict) else None
    if llm_provider_attempted is None and isinstance(llm_execution, dict):
        llm_provider_attempted = _bool_or_none(llm_execution.get("provider_attempted"))
    if llm_provider_attempted is None and isinstance(template_summary, dict):
        llm_provider_attempted = _bool_or_none(template_summary.get("llm_provider_attempted"))
    if llm_provider_attempted is not None:
        provenance["llm_provider_attempted"] = llm_provider_attempted

    llm_provider_succeeded = _bool_or_none(manifest_payload.get("llm_provider_succeeded")) if isinstance(manifest_payload, dict) else None
    if llm_provider_succeeded is None and isinstance(llm_execution, dict):
        llm_provider_succeeded = _bool_or_none(llm_execution.get("provider_succeeded"))
    if llm_provider_succeeded is None and isinstance(template_summary, dict):
        llm_provider_succeeded = _bool_or_none(template_summary.get("llm_provider_succeeded"))
    if llm_provider_succeeded is not None:
        provenance["llm_provider_succeeded"] = llm_provider_succeeded

    llm_failure_class = _string_or_none(manifest_payload.get("llm_failure_class")) if isinstance(manifest_payload, dict) else None
    if llm_failure_class is None and isinstance(llm_execution, dict):
        llm_failure_class = _string_or_none(llm_execution.get("last_error_class"))
    if llm_failure_class is None and isinstance(template_summary, dict):
        llm_failure_class = _string_or_none(template_summary.get("llm_failure_class"))
    if llm_failure_class:
        provenance["llm_failure_class"] = llm_failure_class

    fallback_class = _fallback_class_from_payload(manifest_payload)
    if fallback_class is None and isinstance(template_summary, dict):
        fallback_class = _string_or_none(template_summary.get("fallback_class"))
    if fallback_class:
        provenance["fallback_class"] = fallback_class

    template_id = _string_or_none(template_summary.get("template_id")) if isinstance(template_summary, dict) else None
    if template_id:
        provenance["template_id"] = template_id

    return provenance


def _fallback_class_from_payload(payload: Dict[str, Any]) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    direct = _string_or_none(payload.get("fallback_class"))
    if direct:
        return direct
    manifest = _unwrap_manifest(payload)
    metadata = manifest.get("metadata") if isinstance(manifest, dict) else None
    if isinstance(metadata, dict):
        return _string_or_none(metadata.get("fallback_class"))
    return None


def _dig(mapping: Dict[str, Any], *keys: str) -> Any:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _string_or_none(value: Any) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _bool_or_none(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        token = value.strip().lower()
        if token in {"true", "1", "yes", "on"}:
            return True
        if token in {"false", "0", "no", "off"}:
            return False
    return None


def _contract_output_mode(rule: Dict[str, Any]) -> Optional[str]:
    if not isinstance(rule, dict):
        return None
    output = rule.get("output")
    if isinstance(output, dict):
        value = output.get("format") or output.get("mode")
        normalized = _string_or_none(value)
        if normalized:
            return normalized.lower()
    return None


def _normalize_proposed_verification_contract(report: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(report, dict):
        return None
    raw = extract_verification_spec(report)
    return _normalize_verification_spec_raw(raw, source_label="researcher_report.verification_spec")


def _normalize_verification_spec_raw(
    raw: Any,
    *,
    source_label: str,
) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None

    markers = raw.get("success_text_markers")
    success_signature = ""
    if isinstance(markers, str) and markers.strip():
        success_signature = markers.strip()
    elif isinstance(markers, list):
        for item in markers:
            if isinstance(item, str) and item.strip():
                success_signature = item.strip()
                break

    flag_token = _string_or_none(raw.get("flag_token"))
    assertion_program = raw.get("assertion_program")
    normalized: Dict[str, Any] = {
        "source": source_label,
        "override_static": bool(raw.get("override_static")),
    }
    success_mode = _string_or_none(raw.get("success_mode"))
    json_success_key = _string_or_none(raw.get("json_success_key"))
    json_flag_key = _string_or_none(raw.get("json_flag_key"))
    if success_signature:
        normalized["success_signature"] = success_signature
    if flag_token:
        normalized["flag_token"] = flag_token
    if success_mode:
        normalized["success_mode"] = success_mode
    if json_success_key:
        normalized["json_success_key"] = json_success_key
        if "json_success_value" in raw:
            normalized["json_success_value"] = deepcopy(raw.get("json_success_value"))
    if json_flag_key:
        normalized["json_flag_key"] = json_flag_key
    if isinstance(assertion_program, list) and assertion_program:
        normalized["assertion_program"] = assertion_program
    negative_markers = _normalize_string_list(raw.get("negative_text_markers"))
    if not negative_markers:
        negative_markers = _negative_markers_from_assertion_program(assertion_program)
    if negative_markers:
        normalized["negative_text_markers"] = negative_markers
    forbidden_markers = _normalize_string_list(raw.get("forbidden_success_markers"))
    if not forbidden_markers:
        forbidden_markers = list(negative_markers)
    if forbidden_markers:
        normalized["forbidden_success_markers"] = forbidden_markers
    negative_controls = raw.get("negative_controls")
    if isinstance(negative_controls, list) and negative_controls:
        normalized["negative_controls"] = deepcopy(negative_controls)
    metamorphic = raw.get("metamorphic")
    if isinstance(metamorphic, dict) and metamorphic:
        normalized["metamorphic"] = deepcopy(metamorphic)
    return normalized if len(normalized) > 2 else None


def _manifest_role_content(manifest: Dict[str, Any], role: str) -> Optional[str]:
    files = manifest.get("files") or []
    if not isinstance(files, list):
        return None
    role_norm = (role or "").strip().lower()
    for entry in files:
        if not isinstance(entry, dict):
            continue
        if not role_matches(entry.get("role"), role_norm):
            continue
        content = entry.get("content")
        if isinstance(content, str):
            return content
    return None


def _poc_content_from_manifest(manifest: Dict[str, Any]) -> str:
    direct = _manifest_role_content(manifest, "poc_entry")
    if isinstance(direct, str) and direct.strip():
        return direct
    files = manifest.get("files") or []
    if not isinstance(files, list):
        return ""
    poc_path = _first_poc_like_path(manifest)
    for entry in files:
        if not isinstance(entry, dict):
            continue
        path = _string_or_none(entry.get("path"))
        content = entry.get("content")
        if not isinstance(content, str):
            continue
        if poc_path and path == poc_path:
            return content
    return ""


def _negative_markers_from_poc_content(
    content: str,
    *,
    success_signature: str,
    flag_token: str,
) -> List[str]:
    if not isinstance(content, str) or not content.strip():
        return []
    markers: List[str] = []

    def add_marker(value: Any) -> None:
        token = str(value or "").strip()
        if not token:
            return
        if token == success_signature or token == flag_token:
            return
        if success_signature and success_signature in token:
            return
        if flag_token and flag_token in token:
            return
        if token not in markers:
            markers.append(token)

    try:
        tree = ast.parse(content)
    except SyntaxError:
        tree = None
    if tree is not None:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Name) or func.id != "print":
                continue
            if not node.args:
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                add_marker(first.value)

    if markers:
        return markers

    for match in re.finditer(r"print\(\s*(?:f)?(['\"])(.*?)\1", content, flags=re.DOTALL):
        add_marker(match.group(2))
    return markers


def _manifest_proposed_verification_contract(manifest: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(manifest, dict):
        return None
    explicit = manifest.get("verification_spec")
    normalized = _normalize_verification_spec_raw(
        explicit,
        source_label="generator_manifest.verification_spec",
    )
    if normalized:
        return normalized

    poc = manifest.get("poc") if isinstance(manifest.get("poc"), dict) else {}
    success_signature = _string_or_none(poc.get("success_signature"))
    flag_token = _string_or_none(poc.get("flag_token"))
    poc_content = _poc_content_from_manifest(manifest)
    negative_markers = _negative_markers_from_poc_content(
        poc_content,
        success_signature=success_signature or "",
        flag_token=flag_token or "",
    )
    if not success_signature and not flag_token and not negative_markers:
        return None
    raw: Dict[str, Any] = {}
    if success_signature:
        raw["success_text_markers"] = [success_signature]
    if flag_token:
        raw["flag_token"] = flag_token
    if negative_markers:
        raw["negative_text_markers"] = negative_markers
    return _normalize_verification_spec_raw(
        raw,
        source_label="generator_manifest.poc_derived_verification_spec",
    )


def _merge_proposed_verification_contracts(
    primary: Optional[Dict[str, Any]],
    secondary: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not isinstance(primary, dict) or not primary:
        return deepcopy(secondary) if isinstance(secondary, dict) and secondary else None
    if not isinstance(secondary, dict) or not secondary:
        return deepcopy(primary)
    merged = deepcopy(primary)

    for key in (
        "success_signature",
        "flag_token",
        "success_mode",
        "json_success_key",
        "json_success_value",
        "json_flag_key",
        "metamorphic",
    ):
        if key not in merged and key in secondary:
            merged[key] = deepcopy(secondary.get(key))

    for key in ("negative_text_markers", "forbidden_success_markers", "negative_controls"):
        primary_values = merged.get(key)
        secondary_values = secondary.get(key)
        if isinstance(primary_values, list) and isinstance(secondary_values, list):
            seen = {
                json.dumps(item, ensure_ascii=False, sort_keys=True)
                for item in primary_values
            }
            for item in secondary_values:
                digest = json.dumps(item, ensure_ascii=False, sort_keys=True)
                if digest in seen:
                    continue
                primary_values.append(deepcopy(item))
                seen.add(digest)
        elif key not in merged and isinstance(secondary_values, list) and secondary_values:
            merged[key] = deepcopy(secondary_values)

    primary_assertions = merged.get("assertion_program")
    secondary_assertions = secondary.get("assertion_program")
    if isinstance(primary_assertions, list) and isinstance(secondary_assertions, list):
        seen = {
            json.dumps(item, ensure_ascii=False, sort_keys=True)
            for item in primary_assertions
            if isinstance(item, dict)
        }
        for item in secondary_assertions:
            if not isinstance(item, dict):
                continue
            digest = json.dumps(item, ensure_ascii=False, sort_keys=True)
            if digest in seen:
                continue
            primary_assertions.append(deepcopy(item))
            seen.add(digest)
    elif "assertion_program" not in merged and isinstance(secondary_assertions, list) and secondary_assertions:
        merged["assertion_program"] = deepcopy(secondary_assertions)

    if merged.get("negative_text_markers") or merged.get("forbidden_success_markers") or merged.get("negative_controls"):
        merged["negative_control_present"] = True
    if isinstance(merged.get("metamorphic"), dict) and merged.get("metamorphic"):
        merged["metamorphic_present"] = True
    return merged


def _normalize_string_list(value: Any) -> List[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if isinstance(item, str) and str(item).strip()]


def _negative_markers_from_assertion_program(program: Any) -> List[str]:
    if not isinstance(program, list):
        return []
    markers: List[str] = []
    for item in program:
        if not isinstance(item, dict):
            continue
        op = str(item.get("op") or "").strip().lower()
        if op not in {"not_contains", "stdout_not_contains"}:
            continue
        marker = _string_or_none(item.get("string") or item.get("contains") or item.get("needle"))
        if marker and marker not in markers:
            markers.append(marker)
    return markers


def _resolve_semantic_contract(
    vuln_id: str,
    report: Dict[str, Any],
    guard_spec: Dict[str, Any],
    requirement: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    contract = extract_semantic_contract(report)
    requirement_view = requirement if isinstance(requirement, dict) else {}
    synthetic_requirement = dict(requirement_view) if isinstance(requirement_view, dict) else {}
    synthetic_requirement.setdefault("vuln_id", vuln_id)
    is_free_form_name = is_name_driven_requirement(synthetic_requirement)
    report_signature = contract.get("semantic_signature") if isinstance(contract, dict) else None
    guard_signature = guard_spec.get("semantic_signature") if isinstance(guard_spec, dict) else None
    baseline_signature = _normalize_semantic_buckets(baseline_semantic_signature(vuln_id))
    fragment_signature, _ = _default_profile_semantic_signature(
        vuln_id=vuln_id,
        requirement=requirement_view or {"vuln_id": vuln_id},
    )
    fragment_signature_present = _semantic_signature_present(fragment_signature)
    has_baseline = any(baseline_signature.get(bucket) for bucket in baseline_signature)
    resolved_signature = _normalize_semantic_buckets(contract.get("semantic_signature") if isinstance(contract, dict) else {})
    if isinstance(guard_signature, dict) and guard_signature and "semantic_signature" not in contract:
        contract["semantic_signature"] = guard_signature
        contract.setdefault("semantic_signature_source", ["guard_spec"])
        resolved_signature = _normalize_semantic_buckets(guard_signature)
    elif has_baseline and not is_free_form_name and not any(resolved_signature.get(bucket) for bucket in resolved_signature):
        contract["semantic_signature"] = baseline_signature
        contract["semantic_signature_source"] = ["baseline"]
        resolved_signature = baseline_signature
    elif fragment_signature_present and is_free_form_name and not any(
        resolved_signature.get(bucket) for bucket in resolved_signature
    ):
        contract["semantic_signature"] = fragment_signature
        contract["semantic_signature_source"] = ["fragment_registry"]
        resolved_signature = fragment_signature
    guard_confidence = guard_spec.get("confidence") if isinstance(guard_spec, dict) else None
    if isinstance(guard_confidence, str) and guard_confidence.strip():
        contract["guard_confidence"] = guard_confidence.strip().lower()
    contradictions = _semantic_contract_contradictions(
        vuln_id,
        signature=resolved_signature,
        report_signature=report_signature if isinstance(report_signature, dict) else {},
        guard_signature=guard_signature if isinstance(guard_signature, dict) else {},
        require_expected_terms=not is_free_form_name,
    )
    contract["authority"] = "resolved_contract.semantic_contract"
    contract["contradictions"] = contradictions
    report_has_terms = _semantic_signature_present(report_signature)
    guard_has_terms = _semantic_signature_present(guard_signature)
    resolved_has_terms = _semantic_signature_present(resolved_signature)
    baseline_counts_as_present = has_baseline and not is_free_form_name
    quality = str(contract.get("quality") or "").strip().lower()
    quality_insufficient = quality == "insufficient"
    if contradictions:
        status = "contradicted"
    elif quality_insufficient:
        status = "empty" if (resolved_has_terms or report_has_terms or guard_has_terms) else "unsupported"
    elif resolved_has_terms:
        status = "aligned"
    elif baseline_counts_as_present or report_has_terms or guard_has_terms:
        status = "empty"
    else:
        status = "unsupported"
    contract["status"] = status
    return contract


def _semantic_contract_contradictions(
    vuln_id: str,
    *,
    signature: Any,
    report_signature: Dict[str, Any],
    guard_signature: Dict[str, Any],
    require_expected_terms: bool = True,
) -> list[str]:
    resolved = _normalize_semantic_buckets(signature)
    report_norm = _normalize_semantic_buckets(report_signature)
    guard_norm = _normalize_semantic_buckets(guard_signature)
    baseline = _normalize_semantic_buckets(baseline_semantic_signature(vuln_id))
    contradictions: list[str] = []

    for bucket in ("input_vector", "sink", "exploit_precondition"):
        expected = baseline.get(bucket) or []
        observed = resolved.get(bucket) or []
        if require_expected_terms and expected and not observed:
            contradictions.append(f"semantic_contract missing expected {bucket} for {vuln_id}")
        elif expected and observed and not _semantic_bucket_overlap(expected, observed):
            contradictions.append(f"semantic_contract {bucket} conflicts with baseline {vuln_id} semantics")

        report_values = report_norm.get(bucket) or []
        guard_values = guard_norm.get(bucket) or []
        if report_values and guard_values and not _semantic_bucket_overlap(report_values, guard_values):
            contradictions.append(f"report vs guard semantic_signature mismatch on {bucket}")
        contradictions.extend(_foreign_family_semantic_terms(vuln_id, bucket=bucket, values=observed))

    return contradictions


def _normalize_semantic_buckets(signature: Any) -> Dict[str, list[str]]:
    if not isinstance(signature, dict):
        return {
            "input_vector": [],
            "sink": [],
            "exploit_precondition": [],
        }
    normalized: Dict[str, list[str]] = {}
    for bucket in ("input_vector", "sink", "exploit_precondition"):
        values = signature.get(bucket)
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list):
            values = []
        normalized[bucket] = [
            str(value).strip()
            for value in values
            if isinstance(value, str) and str(value).strip()
        ]
    return normalized


def _semantic_signature_present(signature: Any) -> bool:
    normalized = _normalize_semantic_buckets(signature)
    return any(normalized.get(bucket) for bucket in ("input_vector", "sink", "exploit_precondition"))


def _semantic_bucket_overlap(lhs: list[str], rhs: list[str]) -> bool:
    for left in lhs:
        left_aliases = semantic_term_aliases(left)
        for right in rhs:
            right_aliases = semantic_term_aliases(right)
            if left_aliases & right_aliases:
                return True
            if left.lower() in right.lower() or right.lower() in left.lower():
                return True
    return False


def _foreign_family_semantic_terms(vuln_id: str, *, bucket: str, values: list[str]) -> list[str]:
    normalized = normalize_vuln_id(vuln_id)
    allowed = family_canonical_tags(normalized)
    if not allowed:
        return []
    foreign_tags: dict[str, str] = {}
    for candidate in sorted(FAMILY_CANONICAL_TAGS):
        if candidate == normalized:
            continue
        for tag in family_canonical_tags(candidate):
            foreign_tags.setdefault(tag, candidate.upper())
    contradictions: list[str] = []
    for value in values:
        aliases = semantic_term_aliases(value)
        if aliases & allowed:
            continue
        foreign_hits = [foreign_tags[tag] for tag in aliases if tag in foreign_tags]
        if not foreign_hits:
            continue
        families = ", ".join(sorted(set(foreign_hits)))
        contradictions.append(
            f"semantic_contract {bucket} includes foreign-family term '{value}' for {vuln_id} (matches {families})"
        )
    return contradictions


def _manifest_role_path(manifest: Dict[str, Any], role: str) -> Optional[str]:
    files = manifest.get("files") or []
    if not isinstance(files, list):
        return None
    role_norm = (role or "").strip().lower()
    for entry in files:
        if not isinstance(entry, dict):
            continue
        if not role_matches(entry.get("role"), role_norm):
            continue
        path = _string_or_none(entry.get("path"))
        if path:
            return path
    return None


def _first_poc_like_path(manifest: Dict[str, Any]) -> Optional[str]:
    files = manifest.get("files") or []
    if not isinstance(files, list):
        return None
    for entry in files:
        if not isinstance(entry, dict):
            continue
        path = _string_or_none(entry.get("path"))
        if not path:
            continue
        if Path(path).name.lower().startswith("poc."):
            return path
    return None


def _manifest_file_paths(manifest: Dict[str, Any]) -> list[str]:
    files = manifest.get("files") or []
    if not isinstance(files, list):
        return []
    paths: list[str] = []
    for entry in files:
        if not isinstance(entry, dict):
            continue
        path = _string_or_none(entry.get("path"))
        if path:
            paths.append(path)
    return paths


def _workspace_file_paths(workspace_dir: Optional[Path]) -> list[str]:
    if not isinstance(workspace_dir, Path) or not workspace_dir.exists():
        return []
    paths: list[str] = []
    for path in workspace_dir.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(workspace_dir).as_posix()
        except ValueError:
            continue
        if rel:
            paths.append(rel)
    return sorted(paths)


def _path_present_in_sources(path: Optional[str], candidates: Sequence[str], workspace_dir: Optional[Path]) -> bool:
    token = _string_or_none(path)
    if not token:
        return False
    if token in candidates:
        return True
    if isinstance(workspace_dir, Path):
        return (workspace_dir / token).exists()
    return False


def _dependency_manifest_paths(paths: Sequence[str]) -> list[str]:
    dependency_names = {
        "requirements.txt",
        "requirements-dev.txt",
        "requirements.lock",
        "pyproject.toml",
        "poetry.lock",
        "pipfile",
        "pipfile.lock",
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "setup.py",
    }
    return [path for path in paths if Path(path).name.lower() in dependency_names]


def _seed_asset_paths(paths: Sequence[str]) -> list[str]:
    seed_names = {"schema.sql", "seed.sql", "seed_data.sql", "init.sql"}
    results: list[str] = []
    for path in paths:
        name = Path(path).name.lower()
        suffix = Path(path).suffix.lower()
        if name in seed_names or suffix in {".sql", ".sqlite", ".sqlite3", ".db"}:
            results.append(path)
    return results


def _manifest_file_content(manifest: Dict[str, Any], path_token: Optional[str]) -> Optional[str]:
    token = _string_or_none(path_token)
    if not token:
        return None
    files = manifest.get("files") or []
    if not isinstance(files, list):
        return None
    for entry in files:
        if not isinstance(entry, dict):
            continue
        if _string_or_none(entry.get("path")) != token:
            continue
        content = entry.get("content")
        if isinstance(content, str):
            return content
    return None


def _workspace_file_content(workspace_dir: Optional[Path], path_token: Optional[str]) -> Optional[str]:
    token = _string_or_none(path_token)
    if not token or not isinstance(workspace_dir, Path):
        return None
    candidate = workspace_dir / token
    if not candidate.exists() or not candidate.is_file():
        return None
    try:
        return candidate.read_text(encoding="utf-8")
    except Exception:
        return None


def _read_manifest_or_workspace_text(
    *,
    path_token: Optional[str],
    manifest: Dict[str, Any],
    workspace_dir: Optional[Path],
) -> str:
    content = _workspace_file_content(workspace_dir, path_token)
    if isinstance(content, str):
        return content
    content = _manifest_file_content(manifest, path_token)
    return content if isinstance(content, str) else ""


def _dockerfile_instruction_blocks(dockerfile_text: str) -> list[tuple[str, str]]:
    if not dockerfile_text:
        return []
    blocks: list[tuple[str, str]] = []
    current_token: Optional[str] = None
    current_body: List[str] = []
    continuation = False
    for raw_line in dockerfile_text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if continuation and current_token:
            current_body.append(stripped.rstrip("\\").strip())
            continuation = stripped.endswith("\\")
            if not continuation:
                blocks.append((current_token, " ".join(part for part in current_body if part).strip()))
                current_token = None
                current_body = []
            continue
        token, _, remainder = stripped.partition(" ")
        current_token = token.upper()
        current_body = [remainder.rstrip("\\").strip()]
        continuation = stripped.endswith("\\")
        if not continuation:
            blocks.append((current_token, " ".join(part for part in current_body if part).strip()))
            current_token = None
            current_body = []
    if current_token:
        blocks.append((current_token, " ".join(part for part in current_body if part).strip()))
    return blocks


def _dockerfile_base_images(dockerfile_text: str) -> list[str]:
    images: list[str] = []
    for token, body in _dockerfile_instruction_blocks(dockerfile_text):
        if token != "FROM":
            continue
        for candidate in body.split():
            if candidate.startswith("--"):
                continue
            images.append(candidate)
            break
    return images


def _dockerfile_is_unpinned_base_image(image: str) -> bool:
    token = str(image or "").strip()
    if not token:
        return False
    if "@sha256:" in token:
        return False
    leaf = token.rsplit("/", 1)[-1]
    if ":" not in leaf:
        return True
    _, _, tag = leaf.rpartition(":")
    return tag.strip().lower() == "latest"


def _dockerfile_package_installers(dockerfile_text: str) -> list[str]:
    detected: list[str] = []
    patterns = {
        "apt_get_install": re.compile(r"\bapt-get\s+install\b", re.IGNORECASE),
        "apk_add": re.compile(r"\bapk\s+add\b", re.IGNORECASE),
        "pip_install": re.compile(r"\b(?:python\s+-m\s+pip|pip)\s+install\b", re.IGNORECASE),
        "npm_install": re.compile(r"\bnpm\s+install\b", re.IGNORECASE),
        "poetry_install": re.compile(r"\bpoetry\s+install\b", re.IGNORECASE),
        "cargo_install": re.compile(r"\bcargo\s+install\b", re.IGNORECASE),
        "go_install": re.compile(r"\bgo\s+install\b", re.IGNORECASE),
    }
    for token, body in _dockerfile_instruction_blocks(dockerfile_text):
        if token != "RUN":
            continue
        for name, pattern in patterns.items():
            if pattern.search(body) and name not in detected:
                detected.append(name)
    return detected


def _dockerfile_remote_fetch_commands(dockerfile_text: str) -> list[str]:
    commands: list[str] = []
    remote_url = re.compile(r"https?://", re.IGNORECASE)
    remote_fetch = re.compile(r"\b(?:curl|wget)\b", re.IGNORECASE)
    for token, body in _dockerfile_instruction_blocks(dockerfile_text):
        if token == "ADD" and remote_url.search(body):
            commands.append(f"ADD {body}".strip())
        elif token == "RUN" and remote_fetch.search(body) and remote_url.search(body):
            commands.append(f"RUN {body}".strip())
    return commands


def _dockerfile_tmp_db_artifacts(dockerfile_text: str) -> list[str]:
    pattern = re.compile(r"/tmp/[^\s'\"\\]+?\.(?:db|sqlite|sqlite3)", re.IGNORECASE)
    matches: list[str] = []
    for token, body in _dockerfile_instruction_blocks(dockerfile_text):
        if token not in {"RUN", "COPY", "ADD"}:
            continue
        matches.extend(pattern.findall(body))
    return sorted(set(matches))


def _dockerfile_final_user(dockerfile_text: str) -> Optional[str]:
    final_user: Optional[str] = None
    for token, body in _dockerfile_instruction_blocks(dockerfile_text):
        if token != "USER":
            continue
        candidate = body.split()[0].strip() if body.split() else ""
        final_user = candidate or None
    return final_user


def _dockerfile_instruction_counts(dockerfile_text: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for token, _ in _dockerfile_instruction_blocks(dockerfile_text):
        key = token.lower()
        counts[key] = counts.get(key, 0) + 1
    return counts


def _build_file_manifest_safety_policy(
    *,
    dockerfile_path: Optional[str],
    manifest: Dict[str, Any],
    workspace_dir: Optional[Path],
) -> Dict[str, Any]:
    dockerfile_text = _read_manifest_or_workspace_text(
        path_token=dockerfile_path,
        manifest=manifest,
        workspace_dir=workspace_dir,
    )
    base_images = _dockerfile_base_images(dockerfile_text)
    package_installers = _dockerfile_package_installers(dockerfile_text)
    remote_fetch_commands = _dockerfile_remote_fetch_commands(dockerfile_text)
    tmp_db_artifacts = _dockerfile_tmp_db_artifacts(dockerfile_text)
    final_user = _dockerfile_final_user(dockerfile_text)
    instruction_counts = _dockerfile_instruction_counts(dockerfile_text)

    blockers: list[str] = []
    warnings: list[str] = []
    if not dockerfile_text:
        blockers.append("dockerfile_missing")
    if dockerfile_text and not base_images:
        blockers.append("base_image_missing")
    if remote_fetch_commands:
        blockers.append("remote_fetch_in_build")
    if tmp_db_artifacts:
        blockers.append("tmp_db_artifact_in_build")
    unpinned_images = [image for image in base_images if _dockerfile_is_unpinned_base_image(image)]
    if unpinned_images:
        warnings.extend(f"base_image_unpinned:{image}" for image in unpinned_images)
    if final_user in {None, "", "root", "0"}:
        warnings.append("final_user_root")

    return {
        "policy_version": "docker_build_safety@0.1",
        "assessed": bool(dockerfile_text),
        "safe": bool(dockerfile_text) and not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "base_images": base_images,
        "package_installers_detected": package_installers,
        "remote_fetch_commands": remote_fetch_commands,
        "tmp_db_artifact_paths": tmp_db_artifacts,
        "final_user": final_user or "root",
        "instruction_counts": instruction_counts,
    }


def _port_from_generator_template(template: Dict[str, Any]) -> Optional[int]:
    ports = template.get("ports")
    if isinstance(ports, dict):
        candidate = ports.get("app") or ports.get("service") or ports.get("web")
        value = _int_or_none(candidate)
        if value:
            return value
    for key in ("service_port", "port"):
        value = _int_or_none(template.get(key))
        if value:
            return value
    return None


def _service_env_from_generator_template(template: Dict[str, Any]) -> Dict[str, str]:
    raw = template.get("service_env")
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


def _port_from_generator_manifest(manifest: Dict[str, Any]) -> Optional[int]:
    run_section = manifest.get("run")
    if isinstance(run_section, dict):
        value = _int_or_none(run_section.get("port"))
        if value:
            return value
        command = _string_or_none(run_section.get("command"))
        if command:
            return _parse_port_from_run_command(command)
    if isinstance(run_section, str):
        return _parse_port_from_run_command(run_section)
    return None


def _service_env_from_generator_manifest(manifest: Dict[str, Any]) -> Dict[str, str]:
    run_section = manifest.get("run")
    if not isinstance(run_section, dict):
        return {}
    raw = run_section.get("env")
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


def _build_runtime_recipe(
    *,
    requirement: Dict[str, Any],
    manifest: Dict[str, Any],
    template: Dict[str, Any],
    resolved: Dict[str, Any],
    researcher_report: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    req = requirement if isinstance(requirement, dict) else {}
    runtime = req.get("runtime") if isinstance(req.get("runtime"), dict) else {}
    executor = req.get("executor") if isinstance(req.get("executor"), dict) else {}
    stack = _stack_profile(req, researcher_report)
    service_env = resolved.get("service_env") if isinstance(resolved.get("service_env"), dict) else {}
    service_env = {
        str(key): str(value)
        for key, value in service_env.items()
        if isinstance(key, str) and key.strip() and value not in (None, "")
    }
    db = (
        _string_or_none(runtime.get("db"))
        or _string_or_none(runtime.get("database"))
        or _string_or_none(req.get("db"))
        or _string_or_none(req.get("database"))
    )
    allow_external_db = bool(runtime.get("allow_external_db", False))
    service_port = resolved.get("service_port")
    sidecars = _runtime_sidecars(executor)
    sidecars_source = "requirement.executor.sidecars" if sidecars else None
    target_db_hint, target_sidecars_hint, target_topology_hint = _manifest_target_runtime_hints(manifest)
    if not sidecars:
        synthesized_sidecars = _synthesized_runtime_sidecars(
            target_db=target_db_hint,
            target_sidecars=target_sidecars_hint,
            service_env=service_env,
        )
        if synthesized_sidecars:
            sidecars = synthesized_sidecars
            sidecars_source = "generator_manifest.metadata.target_sidecars"
    service_env, service_env_source = _synthesized_runtime_service_env(
        service_env=service_env,
        service_port=service_port if isinstance(service_port, int) else DEFAULT_APP_PORT,
        sidecars=sidecars,
        target_db=target_db_hint,
        target_sidecars=target_sidecars_hint,
    )
    if not db and target_db_hint:
        db = target_db_hint
    template_requires_external_db = _bool_or_none(template.get("requires_external_db")) is True
    manifest_requires_external_db = _bool_or_none(manifest.get("requires_external_db")) is True
    requires_external_db = template_requires_external_db or manifest_requires_external_db or (db or "").lower() in {
        "mysql",
        "mariadb",
        "postgres",
        "postgresql",
    } or bool(sidecars)
    policy_allow_network = _bool_or_none(executor.get("allow_network"))
    policy_network_mode = _string_or_none(executor.get("network_mode"))
    feasibility = executor_feasibility_summary(
        req,
        executor,
        requires_external_db=requires_external_db,
    )
    topology = "service_plus_sidecar" if sidecars or feasibility.get("requires_external_db") else "single_service"
    if not sidecars and target_topology_hint == "service_plus_sidecar":
        topology = "service_plus_sidecar"
    requires_runtime_network = bool(sidecars or topology == "service_plus_sidecar" or requires_external_db)
    network_enabled = bool(feasibility.get("network_enabled"))
    network_enabled_source = "executor_feasibility"
    if policy_allow_network is None and requires_runtime_network:
        network_enabled = True
        network_enabled_source = "runtime_topology_requires_network"
    elif policy_allow_network is False:
        network_enabled = False
        network_enabled_source = "requirement.executor.allow_network"
    network_mode = _string_or_none(feasibility.get("network_mode")) or "none"
    network_mode_source = "executor_feasibility"
    if policy_network_mode:
        network_mode = policy_network_mode
        network_mode_source = "requirement.executor.network_mode"
    elif network_enabled and requires_runtime_network:
        network_mode = "bridge"
        network_mode_source = "runtime_topology_requires_network"
    seed_files = _runtime_seed_files(manifest)
    seed_strategy, seed_strategy_source = _runtime_seed_strategy(
        seed_files=seed_files,
        db=db,
        requires_external_db=bool(feasibility.get("requires_external_db")),
        topology=topology,
    )
    volume_contract, volume_contract_source = _runtime_volume_contract(
        seed_files=seed_files,
        seed_strategy=seed_strategy,
        sidecars=sidecars,
    )
    network_contract, network_contract_source = _runtime_network_contract(
        service_env=service_env,
        sidecars=sidecars,
    )
    stack_hypotheses = stack.get("stack_hypotheses") if isinstance(stack.get("stack_hypotheses"), list) else []
    recipe: Dict[str, Any] = {
        "language": _string_or_none(stack.get("language")) or "python",
        "framework": _string_or_none(stack.get("framework")) or "flask",
        "stack_source": _string_or_none(stack.get("stack_source")) or "default_stack_profile",
        "stack_locked": bool(stack.get("stack_locked")),
        "stack_defaulted": bool(stack.get("stack_defaulted")),
        "transport": "http",
        "service_entry": _string_or_none(resolved.get("service_entry")) or "app.py",
        "poc_entry": _string_or_none(resolved.get("poc_entry")) or "poc.py",
        "service_port": service_port if isinstance(service_port, int) else DEFAULT_APP_PORT,
        "db": db,
        "allow_external_db": allow_external_db,
        "requires_external_db": bool(feasibility.get("requires_external_db")),
        "network_mode": network_mode,
        "network_enabled": network_enabled,
        "sidecars": sidecars,
        "service_env": service_env,
        "seed_files": seed_files,
        "topology": topology,
        "output_mode": _string_or_none(resolved.get("output_mode")) or "auto",
    }
    if sidecars_source:
        recipe["sidecars_source"] = sidecars_source
    sidecar_start_order = [
        str(item.get("name") or "").strip()
        for item in sidecars
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]
    if sidecar_start_order:
        recipe["sidecar_start_order"] = sidecar_start_order
        recipe["sidecar_start_order_source"] = sidecars_source or "runtime_recipe.sidecars"
    if service_env_source:
        recipe["service_env_source"] = service_env_source
    if seed_strategy:
        recipe["seed_strategy"] = seed_strategy
    if seed_strategy_source:
        recipe["seed_strategy_source"] = seed_strategy_source
    if volume_contract:
        recipe["volume_contract"] = volume_contract
    if volume_contract_source:
        recipe["volume_contract_source"] = volume_contract_source
    if network_contract:
        recipe["network_contract"] = network_contract
    if network_contract_source:
        recipe["network_contract_source"] = network_contract_source
    recipe["network_mode_source"] = network_mode_source
    recipe["network_enabled_source"] = network_enabled_source
    if stack_hypotheses:
        recipe["stack_hypotheses"] = deepcopy(stack_hypotheses)
    if isinstance(stack.get("stack_selection"), dict) and stack.get("stack_selection"):
        recipe["stack_selection"] = deepcopy(stack.get("stack_selection"))
    health_path = _runtime_health_path(manifest)
    if health_path:
        recipe["health_path"] = health_path
    return recipe


def _build_runtime_graph(
    *,
    runtime_recipe: Dict[str, Any],
    resolved: Dict[str, Any],
) -> Dict[str, Any]:
    recipe = runtime_recipe if isinstance(runtime_recipe, dict) else {}
    if not recipe:
        return {}
    service_port = resolved.get("service_port")
    if not isinstance(service_port, int):
        service_port = recipe.get("service_port")
    if not isinstance(service_port, int):
        service_port = DEFAULT_APP_PORT
    nodes: list[Dict[str, Any]] = [
        {
            "id": "service",
            "kind": "service",
            "role": "primary",
            "language": _string_or_none(recipe.get("language")) or "python",
            "framework": _string_or_none(recipe.get("framework")) or "flask",
            "entry": _string_or_none(recipe.get("service_entry")) or "app.py",
            "transport": _string_or_none(recipe.get("transport")) or "http",
            "port": service_port,
        }
    ]
    edges: list[Dict[str, Any]] = [
        {
            "from": "poc",
            "to": "service",
            "kind": "exploit_http",
            "transport": _string_or_none(recipe.get("transport")) or "http",
            "target_port": service_port,
        }
    ]
    raw_sidecars = recipe.get("sidecars") if isinstance(recipe.get("sidecars"), list) else []
    sidecar_start_order = (
        deepcopy(recipe.get("sidecar_start_order"))
        if isinstance(recipe.get("sidecar_start_order"), list)
        else []
    )
    sidecar_order_index = {
        str(name).strip(): idx + 1
        for idx, name in enumerate(sidecar_start_order)
        if isinstance(name, str) and str(name).strip()
    }
    for sidecar in raw_sidecars:
        if not isinstance(sidecar, dict):
            continue
        name = _string_or_none(sidecar.get("name"))
        if not name:
            continue
        node_id = f"sidecar:{name}"
        startup_order_index = sidecar_order_index.get(name)
        nodes.append(
            {
                "id": node_id,
                "kind": "sidecar",
                "role": "dependency",
                "sidecar_type": _string_or_none(sidecar.get("type")) or "unknown",
                "image": _string_or_none(sidecar.get("image")),
                "aliases": deepcopy(sidecar.get("aliases")) if isinstance(sidecar.get("aliases"), list) else [],
                "env": deepcopy(sidecar.get("env")) if isinstance(sidecar.get("env"), dict) else {},
                "ready_probe": deepcopy(sidecar.get("ready_probe")) if isinstance(sidecar.get("ready_probe"), dict) else {},
                "startup_order_index": startup_order_index,
            }
        )
        startup_after = None
        if isinstance(startup_order_index, int) and startup_order_index > 1:
            previous_name = sidecar_start_order[startup_order_index - 2]
            previous_name = str(previous_name).strip() if isinstance(previous_name, str) else ""
            if previous_name:
                startup_after = f"sidecar:{previous_name}"
        edges.append(
            {
                "from": "service",
                "to": node_id,
                "kind": "runtime_dependency",
                "dependency_type": _string_or_none(sidecar.get("type")) or "unknown",
                "network_mode": _string_or_none(recipe.get("network_mode")) or "none",
                "startup_order_index": startup_order_index,
                "startup_after": startup_after,
            }
        )
    env_contract = [
        {"scope": "service", "name": str(key), "value": str(value)}
        for key, value in (recipe.get("service_env") or {}).items()
        if isinstance(key, str) and key.strip() and value not in (None, "")
    ]
    for sidecar in raw_sidecars:
        if not isinstance(sidecar, dict):
            continue
        sidecar_name = _string_or_none(sidecar.get("name"))
        sidecar_env = sidecar.get("env") if isinstance(sidecar.get("env"), dict) else {}
        if not sidecar_name or not sidecar_env:
            continue
        for key, value in sidecar_env.items():
            if not isinstance(key, str) or not key.strip() or value in (None, ""):
                continue
            env_contract.append(
                {
                    "scope": f"sidecar:{sidecar_name.strip().lower()}",
                    "name": str(key),
                    "value": str(value),
                }
            )
    healthchecks: list[Dict[str, Any]] = []
    health_path = _string_or_none(recipe.get("health_path"))
    if health_path:
        healthchecks.append(
            {
                "node": "service",
                "path": health_path,
                "port": service_port,
                "transport": _string_or_none(recipe.get("transport")) or "http",
            }
        )
    graph: Dict[str, Any] = {
        "schema_version": "runtime_graph@0.1",
        "source": "derived_from_runtime_recipe",
        "topology": _string_or_none(recipe.get("topology")) or "single_service",
        "network": {
            "mode": _string_or_none(recipe.get("network_mode")) or "none",
            "enabled": bool(recipe.get("network_enabled")),
        },
        "nodes": nodes,
        "edges": edges,
        "healthchecks": healthchecks,
        "env_contract": env_contract,
        "exploit_path": {
            "entrypoint": _string_or_none(recipe.get("poc_entry")) or "poc.py",
            "target_node": "service",
            "service_entry": _string_or_none(recipe.get("service_entry")) or "app.py",
            "transport": _string_or_none(recipe.get("transport")) or "http",
            "port": service_port,
            "base_url": _string_or_none(resolved.get("base_url")),
            "success_signal": _string_or_none(resolved.get("success_signature")),
            "flag_token": _string_or_none(resolved.get("flag_token")),
        },
    }
    seed_files = deepcopy(recipe.get("seed_files")) if isinstance(recipe.get("seed_files"), list) else []
    if seed_files:
        graph["seed_files"] = seed_files
    seed_strategy = _string_or_none(recipe.get("seed_strategy"))
    if seed_strategy:
        graph["seed_strategy"] = seed_strategy
    seed_strategy_source = _string_or_none(recipe.get("seed_strategy_source"))
    if seed_strategy_source:
        graph["seed_strategy_source"] = seed_strategy_source
    volume_contract = deepcopy(recipe.get("volume_contract")) if isinstance(recipe.get("volume_contract"), list) else []
    if volume_contract:
        graph["volume_contract"] = volume_contract
    volume_contract_source = _string_or_none(recipe.get("volume_contract_source"))
    if volume_contract_source:
        graph["volume_contract_source"] = volume_contract_source
    network_contract = deepcopy(recipe.get("network_contract")) if isinstance(recipe.get("network_contract"), list) else []
    if not network_contract:
        derived_network_contract, derived_network_contract_source = _runtime_network_contract(
            service_env=recipe.get("service_env") if isinstance(recipe.get("service_env"), dict) else {},
            sidecars=raw_sidecars,
        )
        network_contract = derived_network_contract
        if derived_network_contract_source and not _string_or_none(recipe.get("network_contract_source")):
            recipe["network_contract_source"] = derived_network_contract_source
    if network_contract:
        graph["network_contract"] = network_contract
    network_contract_source = _string_or_none(recipe.get("network_contract_source"))
    if network_contract_source:
        graph["network_contract_source"] = network_contract_source
    db = _string_or_none(recipe.get("db"))
    if db:
        graph["db"] = db
    if sidecar_start_order:
        graph["sidecar_start_order"] = sidecar_start_order
    sidecar_start_order_source = _string_or_none(recipe.get("sidecar_start_order_source"))
    if sidecar_start_order_source:
        graph["sidecar_start_order_source"] = sidecar_start_order_source
    sidecars_source = _string_or_none(recipe.get("sidecars_source"))
    if sidecars_source:
        graph["sidecars_source"] = sidecars_source
    service_env_source = _string_or_none(recipe.get("service_env_source"))
    if service_env_source:
        graph["service_env_source"] = service_env_source
    network_mode_source = _string_or_none(recipe.get("network_mode_source"))
    if network_mode_source:
        graph["network_mode_source"] = network_mode_source
    network_enabled_source = _string_or_none(recipe.get("network_enabled_source"))
    if network_enabled_source:
        graph["network_enabled_source"] = network_enabled_source
    return graph


def _build_executor_plan(
    *,
    runtime_recipe: Dict[str, Any],
    runtime_graph: Dict[str, Any],
    resolved: Dict[str, Any],
) -> Dict[str, Any]:
    recipe = runtime_recipe if isinstance(runtime_recipe, dict) else {}
    graph = runtime_graph if isinstance(runtime_graph, dict) else {}
    if not recipe:
        return {}
    plan: Dict[str, Any] = {
        "schema_version": "executor_plan@0.1",
        "source": "resolved_contract.runtime_recipe",
        "topology": _string_or_none(recipe.get("topology")) or "single_service",
        "service_port": recipe.get("service_port") if isinstance(recipe.get("service_port"), int) else DEFAULT_APP_PORT,
        "base_url": _string_or_none(resolved.get("base_url")) or None,
        "service_entry": _string_or_none(recipe.get("service_entry")) or "app.py",
        "poc_entry": _string_or_none(recipe.get("poc_entry")) or "poc.py",
        "network_mode": _string_or_none(recipe.get("network_mode")) or "none",
        "network_enabled": bool(recipe.get("network_enabled")),
        "requires_external_db": bool(recipe.get("requires_external_db")),
        "target_node": "service",
    }
    network_mode_source = _string_or_none(recipe.get("network_mode_source")) or _string_or_none(graph.get("network_mode_source"))
    if network_mode_source:
        plan["network_mode_source"] = network_mode_source
    network_enabled_source = _string_or_none(recipe.get("network_enabled_source")) or _string_or_none(graph.get("network_enabled_source"))
    if network_enabled_source:
        plan["network_enabled_source"] = network_enabled_source
    health_path = _string_or_none(recipe.get("health_path"))
    if health_path:
        plan["health_path"] = health_path
    sidecars = recipe.get("sidecars") if isinstance(recipe.get("sidecars"), list) else []
    if sidecars:
        plan["sidecars"] = deepcopy(sidecars)
    sidecar_start_order = (
        deepcopy(recipe.get("sidecar_start_order"))
        if isinstance(recipe.get("sidecar_start_order"), list)
        else deepcopy(graph.get("sidecar_start_order"))
        if isinstance(graph.get("sidecar_start_order"), list)
        else []
    )
    if sidecar_start_order:
        plan["sidecar_start_order"] = sidecar_start_order
    sidecar_start_order_source = (
        _string_or_none(recipe.get("sidecar_start_order_source"))
        or _string_or_none(graph.get("sidecar_start_order_source"))
    )
    if sidecar_start_order_source:
        plan["sidecar_start_order_source"] = sidecar_start_order_source
    sidecars_source = _string_or_none(recipe.get("sidecars_source")) or _string_or_none(graph.get("sidecars_source"))
    if sidecars_source:
        plan["sidecars_source"] = sidecars_source
    service_env = recipe.get("service_env") if isinstance(recipe.get("service_env"), dict) else {}
    if service_env:
        plan["service_env"] = deepcopy(service_env)
    service_env_source = _string_or_none(recipe.get("service_env_source")) or _string_or_none(graph.get("service_env_source"))
    if service_env_source:
        plan["service_env_source"] = service_env_source
    stack_selection = recipe.get("stack_selection") if isinstance(recipe.get("stack_selection"), dict) else {}
    if stack_selection:
        plan["stack_selection"] = deepcopy(stack_selection)
    healthchecks = graph.get("healthchecks") if isinstance(graph.get("healthchecks"), list) else []
    if healthchecks:
        plan["healthchecks"] = deepcopy(healthchecks)
    env_contract = graph.get("env_contract") if isinstance(graph.get("env_contract"), list) else []
    if env_contract:
        plan["env_contract"] = deepcopy(env_contract)
    seed_files = graph.get("seed_files") if isinstance(graph.get("seed_files"), list) else []
    if not seed_files:
        seed_files = recipe.get("seed_files") if isinstance(recipe.get("seed_files"), list) else []
    if seed_files:
        plan["seed_files"] = deepcopy(seed_files)
    seed_strategy = _string_or_none(recipe.get("seed_strategy")) or _string_or_none(graph.get("seed_strategy"))
    if seed_strategy:
        plan["seed_strategy"] = seed_strategy
    seed_strategy_source = _string_or_none(recipe.get("seed_strategy_source")) or _string_or_none(graph.get("seed_strategy_source"))
    if seed_strategy_source:
        plan["seed_strategy_source"] = seed_strategy_source
    volume_contract = (
        deepcopy(graph.get("volume_contract"))
        if isinstance(graph.get("volume_contract"), list)
        else deepcopy(recipe.get("volume_contract"))
        if isinstance(recipe.get("volume_contract"), list)
        else []
    )
    if volume_contract:
        plan["volume_contract"] = volume_contract
    volume_contract_source = _string_or_none(graph.get("volume_contract_source")) or _string_or_none(recipe.get("volume_contract_source"))
    if volume_contract_source:
        plan["volume_contract_source"] = volume_contract_source
    network_contract = (
        deepcopy(graph.get("network_contract"))
        if isinstance(graph.get("network_contract"), list)
        else deepcopy(recipe.get("network_contract"))
        if isinstance(recipe.get("network_contract"), list)
        else []
    )
    if network_contract:
        plan["network_contract"] = network_contract
    network_contract_source = _string_or_none(graph.get("network_contract_source")) or _string_or_none(recipe.get("network_contract_source"))
    if network_contract_source:
        plan["network_contract_source"] = network_contract_source
    exploit_path = graph.get("exploit_path") if isinstance(graph.get("exploit_path"), dict) else {}
    if exploit_path:
        plan["exploit_path"] = deepcopy(exploit_path)
    return plan


def _enrich_runtime_contract_surfaces(
    *,
    request_ir: Dict[str, Any],
    runtime_recipe: Dict[str, Any],
    runtime_graph: Dict[str, Any],
    executor_plan: Dict[str, Any],
) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    request_ir = request_ir if isinstance(request_ir, dict) else {}
    recipe = deepcopy(runtime_recipe) if isinstance(runtime_recipe, dict) else {}
    graph = deepcopy(runtime_graph) if isinstance(runtime_graph, dict) else {}
    plan = deepcopy(executor_plan) if isinstance(executor_plan, dict) else {}
    if not recipe:
        return recipe, graph, plan

    runtime_dependency_hypotheses = (
        deepcopy(request_ir.get("runtime_dependency_hypotheses"))
        if isinstance(request_ir.get("runtime_dependency_hypotheses"), list)
        else []
    )
    oracle_hypotheses = (
        deepcopy(request_ir.get("oracle_hypotheses"))
        if isinstance(request_ir.get("oracle_hypotheses"), list)
        else []
    )
    topology_hypotheses = (
        deepcopy(request_ir.get("topology_hypotheses"))
        if isinstance(request_ir.get("topology_hypotheses"), list)
        else []
    )
    lead_db_hint = next(
        (
            entry
            for entry in runtime_dependency_hypotheses
            if isinstance(entry, dict)
            and str(entry.get("kind") or "").strip().lower() == "db"
            and _string_or_none(entry.get("value"))
        ),
        None,
    )
    lead_topology_hint = next(
        (
            entry
            for entry in topology_hypotheses
            if isinstance(entry, dict) and _string_or_none(entry.get("topology"))
        ),
        None,
    )
    lead_oracle_hint = next(
        (
            entry
            for entry in oracle_hypotheses
            if isinstance(entry, dict)
            and (
                _string_or_none(entry.get("mode"))
                or _string_or_none(entry.get("output_mode"))
                or entry.get("negative_control_present") is True
                or entry.get("metamorphic_present") is True
            )
        ),
        None,
    )

    recipe_db = _string_or_none(recipe.get("db"))
    if not recipe_db and lead_db_hint:
        recipe["db"] = _string_or_none(lead_db_hint.get("value"))
        recipe["db_source"] = _string_or_none(lead_db_hint.get("source")) or "primitive_hint"
    elif recipe_db and _string_or_none(recipe.get("db_source")) is None:
        recipe["db_source"] = "runtime_recipe"

    recipe_topology = _string_or_none(recipe.get("topology")) or "single_service"
    if _string_or_none(recipe.get("topology_source")) is None:
        if (
            lead_topology_hint
            and recipe_topology == _string_or_none(lead_topology_hint.get("topology"))
            and recipe_topology == "single_service"
            and not recipe.get("sidecars")
            and not recipe.get("requires_external_db")
        ):
            recipe["topology_source"] = _string_or_none(lead_topology_hint.get("source")) or "primitive_hint"
        else:
            recipe["topology_source"] = "runtime_recipe"

    if runtime_dependency_hypotheses:
        recipe["runtime_dependency_hypotheses"] = runtime_dependency_hypotheses
    if topology_hypotheses:
        recipe["topology_hypotheses"] = topology_hypotheses

    if graph:
        if _string_or_none(graph.get("db")) is None and _string_or_none(recipe.get("db")):
            graph["db"] = _string_or_none(recipe.get("db"))
        if _string_or_none(graph.get("db_source")) is None and _string_or_none(recipe.get("db_source")):
            graph["db_source"] = _string_or_none(recipe.get("db_source"))
        if _string_or_none(graph.get("topology_source")) is None and _string_or_none(recipe.get("topology_source")):
            graph["topology_source"] = _string_or_none(recipe.get("topology_source"))

    if plan:
        if _string_or_none(plan.get("db")) is None and _string_or_none(recipe.get("db")):
            plan["db"] = _string_or_none(recipe.get("db"))
        if _string_or_none(plan.get("db_source")) is None and _string_or_none(recipe.get("db_source")):
            plan["db_source"] = _string_or_none(recipe.get("db_source"))
        if _string_or_none(plan.get("topology_source")) is None and _string_or_none(recipe.get("topology_source")):
            plan["topology_source"] = _string_or_none(recipe.get("topology_source"))
        if runtime_dependency_hypotheses:
            plan["runtime_dependency_hypotheses"] = runtime_dependency_hypotheses
        if topology_hypotheses:
            plan["topology_hypotheses"] = topology_hypotheses
    return recipe, graph, plan


def _runtime_graph_summary(runtime_graph: Dict[str, Any]) -> Dict[str, Any]:
    graph = runtime_graph if isinstance(runtime_graph, dict) else {}
    if not graph:
        return {}
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    edges = graph.get("edges") if isinstance(graph.get("edges"), list) else []
    network = graph.get("network") if isinstance(graph.get("network"), dict) else {}
    exploit = graph.get("exploit_path") if isinstance(graph.get("exploit_path"), dict) else {}
    sidecars = []
    for item in nodes:
        if not isinstance(item, dict) or str(item.get("kind") or "").strip() != "sidecar":
            continue
        name = str(item.get("id") or "").replace("sidecar:", "").strip()
        sidecar_type = str(item.get("sidecar_type") or "").strip()
        sidecars.append(f"{name}:{sidecar_type}" if sidecar_type else name)
    return {
        "topology": _string_or_none(graph.get("topology")) or "single_service",
        "node_count": len(nodes),
        "edge_count": len(edges),
        "sidecars": sidecars,
        "network_mode": _string_or_none(network.get("mode")) or "none",
        "target_node": _string_or_none(exploit.get("target_node")) or "service",
    }


def _evidence_graph_summary(evidence_graph: Dict[str, Any]) -> Dict[str, Any]:
    graph = evidence_graph if isinstance(evidence_graph, dict) else {}
    if not graph:
        return {}
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    edges = graph.get("edges") if isinstance(graph.get("edges"), list) else []
    by_kind: Dict[str, int] = {}
    by_edge_kind: Dict[str, int] = {}
    by_source_authority: Dict[str, int] = {}
    for entry in nodes:
        if not isinstance(entry, dict):
            continue
        kind = _string_or_none(entry.get("kind")) or "unknown"
        by_kind[kind] = by_kind.get(kind, 0) + 1
        if kind == "evidence":
            authority = _string_or_none(entry.get("source_authority"))
            if authority:
                by_source_authority[authority] = by_source_authority.get(authority, 0) + 1
    for entry in edges:
        if not isinstance(entry, dict):
            continue
        kind = _string_or_none(entry.get("kind")) or "unknown"
        by_edge_kind[kind] = by_edge_kind.get(kind, 0) + 1
    return {
        "node_count": int(graph.get("node_count") or len(nodes)),
        "edge_count": int(graph.get("edge_count") or len(edges)),
        "by_kind": by_kind,
        "by_edge_kind": by_edge_kind,
        "by_source_authority": by_source_authority,
        "source": _string_or_none(graph.get("source")) or "unknown",
    }


def _evidence_graph_ids(evidence_graph: Dict[str, Any], *, kind: str) -> list[str]:
    graph = evidence_graph if isinstance(evidence_graph, dict) else {}
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    values: list[str] = []
    for entry in nodes:
        if not isinstance(entry, dict):
            continue
        if _string_or_none(entry.get("kind")) != kind:
            continue
        node_id = _string_or_none(entry.get("id"))
        if node_id and node_id not in values:
            values.append(node_id)
    return values


_FAMILY_EQUIVALENCE: Dict[str, set[str]] = {
    "sqli": {"sqli", "sql_injection", "sqlinjection"},
    "sql_injection": {"sqli", "sql_injection", "sqlinjection"},
    "open_redirect": {"open_redirect", "openredirect"},
    "template_injection": {"template_injection", "templateinjection", "ssti"},
    "ldap_injection": {"ldap_injection", "ldapinjection"},
    "path_traversal": {"path_traversal", "pathtraversal", "directory_traversal"},
    "xss": {"xss", "crosssitescripting"},
    "csrf": {"csrf", "crosssiterequestforgery"},
    "ssrf": {"ssrf", "serversiderequestforgery"},
    "xxe": {"xxe", "xmlexternalentity"},
    "deserialization": {"deserialization", "insecuredeserialization"},
    "code_injection": {"code_injection", "codeinjection"},
    "command_injection": {"command_injection", "commandinjection"},
}


def _normalized_family_key(value: Any) -> str:
    token = _string_or_none(value)
    if not token:
        return ""
    return re.sub(r"[^a-z0-9]+", "", token.lower())


def _family_match_keys(value: Any) -> set[str]:
    normalized = _normalized_family_key(value)
    if not normalized:
        return set()
    aliases = set(_FAMILY_EQUIVALENCE.get(normalized) or [])
    if not aliases:
        return {normalized}
    expanded = {re.sub(r"[^a-z0-9]+", "", item.lower()) for item in aliases}
    expanded.add(normalized)
    return expanded


def _support_maps_from_evidence_graph(
    evidence_graph: Dict[str, Any],
) -> tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    graph = evidence_graph if isinstance(evidence_graph, dict) else {}
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    edges = graph.get("edges") if isinstance(graph.get("edges"), list) else []
    family_node_to_name: Dict[str, str] = {}
    stack_node_to_id: Dict[str, str] = {}
    for entry in nodes:
        if not isinstance(entry, dict):
            continue
        node_id = _string_or_none(entry.get("id"))
        kind = _string_or_none(entry.get("kind"))
        if not node_id or not kind:
            continue
        if kind == "family_hypothesis":
            family = _string_or_none(entry.get("family"))
            if not family and node_id.startswith("family:"):
                family = node_id.split(":", 1)[1]
            if family:
                family_node_to_name[node_id] = family
        elif kind == "stack_hypothesis":
            stack_id = _string_or_none(entry.get("stack_id"))
            if not stack_id and node_id.startswith("stack:"):
                stack_id = node_id.split(":", 1)[1]
            if stack_id:
                stack_node_to_id[node_id] = stack_id.lower()

    family_support: Dict[str, List[str]] = {}
    stack_support: Dict[str, List[str]] = {}
    for entry in edges:
        if not isinstance(entry, dict):
            continue
        edge_kind = _string_or_none(entry.get("kind"))
        edge_from = _string_or_none(entry.get("from"))
        edge_to = _string_or_none(entry.get("to"))
        if not edge_kind or not edge_from or not edge_to or not edge_from.startswith("evidence:"):
            continue
        if edge_kind == "supports_family_hypothesis" and edge_to in family_node_to_name:
            family = family_node_to_name[edge_to]
            values = family_support.setdefault(family, [])
            if edge_from not in values:
                values.append(edge_from)
        if edge_kind == "supports_stack_hypothesis" and edge_to in stack_node_to_id:
            stack_id = stack_node_to_id[edge_to]
            values = stack_support.setdefault(stack_id, [])
            if edge_from not in values:
                values.append(edge_from)
    return family_support, stack_support


def _evidence_authority_map(evidence_graph: Dict[str, Any]) -> Dict[str, str]:
    graph = evidence_graph if isinstance(evidence_graph, dict) else {}
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    authority_map: Dict[str, str] = {}
    for entry in nodes:
        if not isinstance(entry, dict):
            continue
        if _string_or_none(entry.get("kind")) != "evidence":
            continue
        node_id = _string_or_none(entry.get("id"))
        authority = _string_or_none(entry.get("source_authority"))
        if node_id and authority:
            authority_map[node_id] = authority.lower()
    return authority_map


def _support_summary(evidence_ids: List[str], authority_map: Dict[str, str]) -> Dict[str, Any]:
    normalized_ids: List[str] = []
    seen: set[str] = set()
    by_source_authority: Dict[str, int] = {}
    for raw in evidence_ids:
        token = _string_or_none(raw)
        if not token or token in seen:
            continue
        seen.add(token)
        normalized_ids.append(token)
        authority = _string_or_none(authority_map.get(token))
        if authority:
            by_source_authority[authority] = by_source_authority.get(authority, 0) + 1
    return {
        "evidence_ids": normalized_ids,
        "support_count": len(normalized_ids),
        "support_by_source_authority": by_source_authority,
        "evidence_backed": bool(normalized_ids),
        "high_or_medium_authority_support": any(by_source_authority.get(level, 0) > 0 for level in ("high", "medium")),
    }


def _family_support_summary(
    family: Any,
    family_support: Dict[str, List[str]],
    authority_map: Dict[str, str],
) -> Dict[str, Any]:
    candidate_keys = _family_match_keys(family)
    evidence_ids: List[str] = []
    for family_name, support_ids in family_support.items():
        if not (_family_match_keys(family_name) & candidate_keys):
            continue
        for evidence_id in support_ids:
            token = _string_or_none(evidence_id)
            if token and token not in evidence_ids:
                evidence_ids.append(token)
    return _support_summary(evidence_ids, authority_map)


def _stack_support_summary(
    stack_id: Any,
    stack_support: Dict[str, List[str]],
    authority_map: Dict[str, str],
) -> Dict[str, Any]:
    normalized_stack_id = _string_or_none(stack_id)
    if not normalized_stack_id:
        return _support_summary([], authority_map)
    return _support_summary(stack_support.get(normalized_stack_id.lower(), []), authority_map)


def _attach_family_candidate_evidence(
    candidates: list[Dict[str, Any]],
    family_support: Dict[str, List[str]],
) -> list[Dict[str, Any]]:
    output: list[Dict[str, Any]] = []
    for entry in candidates:
        if not isinstance(entry, dict):
            continue
        candidate = deepcopy(entry)
        support: List[str] = []
        candidate_keys = _family_match_keys(candidate.get("family"))
        for family_name, evidence_ids in family_support.items():
            if _family_match_keys(family_name) & candidate_keys:
                for evidence_id in evidence_ids:
                    if evidence_id not in support:
                        support.append(evidence_id)
        existing = candidate.get("evidence_ids")
        if isinstance(existing, list):
            for evidence_id in existing:
                token = _string_or_none(evidence_id)
                if token and token not in support:
                    support.append(token)
        if support:
            candidate["evidence_ids"] = support
        output.append(candidate)
    return output


def _attach_stack_candidate_evidence(
    candidates: list[Dict[str, Any]],
    stack_support: Dict[str, List[str]],
) -> list[Dict[str, Any]]:
    output: list[Dict[str, Any]] = []
    for entry in candidates:
        if not isinstance(entry, dict):
            continue
        candidate = deepcopy(entry)
        stack_id = _string_or_none(candidate.get("stack_id"))
        support: List[str] = []
        if stack_id:
            for evidence_id in stack_support.get(stack_id.lower(), []):
                if evidence_id not in support:
                    support.append(evidence_id)
        existing = candidate.get("evidence_ids")
        if isinstance(existing, list):
            for evidence_id in existing:
                token = _string_or_none(evidence_id)
                if token and token not in support:
                    support.append(token)
        if support:
            candidate["evidence_ids"] = support
        output.append(candidate)
    return output


def _negative_hypotheses_from_report(
    report: Dict[str, Any],
    family_support: Dict[str, List[str]],
) -> list[Dict[str, Any]]:
    family_summary = (
        report.get("family_hypothesis_summary")
        if isinstance(report.get("family_hypothesis_summary"), dict)
        else {}
    )
    contradictory = family_summary.get("contradictory_families") if isinstance(family_summary, dict) else []
    if not isinstance(contradictory, list):
        return []
    hypotheses: list[Dict[str, Any]] = []
    for item in contradictory:
        family = _string_or_none(item)
        if not family:
            continue
        hypothesis: Dict[str, Any] = {
            "family": family.lower(),
            "source": "researcher_contradiction",
        }
        support: List[str] = []
        for family_name, evidence_ids in family_support.items():
            if _family_match_keys(family_name) & _family_match_keys(family):
                for evidence_id in evidence_ids:
                    if evidence_id not in support:
                        support.append(evidence_id)
        if support:
            hypothesis["evidence_ids"] = support
        hypotheses.append(hypothesis)
    return hypotheses


def _family_candidates_from_report(report: Dict[str, Any]) -> list[Dict[str, Any]]:
    family_summary = (
        report.get("family_hypothesis_summary")
        if isinstance(report.get("family_hypothesis_summary"), dict)
        else {}
    )
    ranked = family_summary.get("ranked_families") if isinstance(family_summary, dict) else []
    candidates: list[Dict[str, Any]] = []
    if not isinstance(ranked, list) or not ranked:
        top_family = _string_or_none(family_summary.get("top_family"))
        if not top_family:
            return candidates
        candidate: Dict[str, Any] = {
            "family": top_family.lower(),
            "source": "researcher_hypothesis_summary",
        }
        confidence = _string_or_none(family_summary.get("top_confidence"))
        if confidence:
            candidate["confidence"] = confidence.lower()
        top_margin = family_summary.get("top_margin")
        if isinstance(top_margin, (int, float)):
            candidate["score"] = round(float(top_margin), 3)
        candidates.append(candidate)
        return candidates
    for entry in ranked:
        if not isinstance(entry, dict):
            continue
        family = _string_or_none(entry.get("family"))
        if not family:
            continue
        candidate: Dict[str, Any] = {
            "family": family.lower(),
            "source": "researcher_hypothesis",
        }
        confidence = _string_or_none(entry.get("confidence"))
        if confidence:
            candidate["confidence"] = confidence.lower()
        score = entry.get("score")
        if isinstance(score, (int, float)):
            candidate["score"] = round(float(score), 3)
        signal_hits = entry.get("signal_hits")
        if isinstance(signal_hits, int):
            candidate["signal_hits"] = signal_hits
        candidates.append(candidate)
    return candidates


def _primitive_family_profiles() -> Dict[str, Dict[str, Any]]:
    profiles: Dict[str, Dict[str, Any]] = {}
    for entry in vuln_catalog_entries():
        if not isinstance(entry, dict):
            continue
        family = _string_or_none(entry.get("family"))
        vuln_id = _string_or_none(entry.get("vuln_id"))
        if not family or not vuln_id:
            continue
        family = family.lower()
        profile = profiles.setdefault(
            family,
            {
                "bucket_terms": {
                    "input_vector": [],
                    "sink": [],
                    "exploit_precondition": [],
                },
            },
        )
        baseline = _normalize_semantic_buckets(baseline_semantic_signature(vuln_id))
        for bucket in ("input_vector", "sink", "exploit_precondition"):
            for value in baseline.get(bucket) or []:
                if value not in profile["bucket_terms"][bucket]:
                    profile["bucket_terms"][bucket].append(value)
    return profiles


_PRIMITIVE_FAMILY_RUNTIME_HINTS: Dict[str, Dict[str, Any]] = {
    "open_redirect": {
        "oracle_hypotheses": [
            {
                "mode": "stateful_text",
                "output_mode": "auto",
                "negative_control_present": True,
                "metamorphic_present": True,
                "source": "primitive_family_inference",
                "confidence": "low",
            }
        ],
    },
    "sqli": {
        "dependencies": [
            {
                "kind": "db",
                "value": "sqlite",
                "source": "primitive_family_inference",
                "confidence": "low",
            }
        ],
        "topologies": [
            {
                "topology": "single_service",
                "source": "primitive_family_inference",
                "confidence": "low",
            }
        ],
        "oracle_hypotheses": [
            {
                "mode": "text_markers",
                "output_mode": "auto",
                "negative_control_present": True,
                "metamorphic_present": False,
                "source": "primitive_family_inference",
                "confidence": "low",
            }
        ],
    },
    "sql_injection": {
        "dependencies": [
            {
                "kind": "db",
                "value": "sqlite",
                "source": "primitive_family_inference",
                "confidence": "low",
            }
        ],
        "topologies": [
            {
                "topology": "single_service",
                "source": "primitive_family_inference",
                "confidence": "low",
            }
        ],
        "oracle_hypotheses": [
            {
                "mode": "text_markers",
                "output_mode": "auto",
                "negative_control_present": True,
                "metamorphic_present": False,
                "source": "primitive_family_inference",
                "confidence": "low",
            }
        ],
    },
}


def _primitive_family_candidates_from_hypotheses(
    primitive_hypotheses: list[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    if not isinstance(primitive_hypotheses, list) or not primitive_hypotheses:
        return []
    bucket_values: Dict[str, list[str]] = {
        "input_vector": [],
        "sink": [],
        "exploit_precondition": [],
    }
    for entry in primitive_hypotheses:
        if not isinstance(entry, dict):
            continue
        kind = _string_or_none(entry.get("kind"))
        value = _string_or_none(entry.get("value"))
        if not kind or not value or kind not in bucket_values:
            continue
        if value not in bucket_values[kind]:
            bucket_values[kind].append(value)

    candidates: list[Dict[str, Any]] = []
    for family, profile in _primitive_family_profiles().items():
        matched_buckets: list[str] = []
        matched_values: list[str] = []
        signal_hits = 0
        bucket_terms = profile.get("bucket_terms") if isinstance(profile.get("bucket_terms"), dict) else {}
        for bucket in ("input_vector", "sink", "exploit_precondition"):
            family_terms = bucket_terms.get(bucket) if isinstance(bucket_terms.get(bucket), list) else []
            if not family_terms:
                continue
            for value in bucket_values.get(bucket) or []:
                if not _semantic_bucket_overlap([value], family_terms):
                    continue
                matched_buckets.append(bucket)
                signal_hits += 1
                if value not in matched_values:
                    matched_values.append(value)
                break
        if len(matched_buckets) < 2:
            continue
        if not any(bucket in {"sink", "exploit_precondition"} for bucket in matched_buckets):
            continue
        confidence = "medium" if len(matched_buckets) >= 3 else "low"
        score = round(len(matched_buckets) + (signal_hits / 10.0), 3)
        candidate: Dict[str, Any] = {
            "family": family,
            "source": "primitive_signature",
            "confidence": confidence,
            "score": score,
            "matched_buckets": matched_buckets,
            "signal_hits": signal_hits,
        }
        if matched_values:
            candidate["matched_primitive_values"] = matched_values[:3]
        candidates.append(candidate)
    return sorted(
        candidates,
        key=lambda item: (
            -len(item.get("matched_buckets") or []),
            -float(item.get("score") or 0.0),
            str(item.get("family") or ""),
        ),
    )


def _primitive_runtime_hints_for_request_ir(request_ir: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(request_ir, dict):
        return {}
    primitive_hypotheses = request_ir.get("primitive_hypotheses") if isinstance(request_ir.get("primitive_hypotheses"), list) else []
    provisional_family = _string_or_none(request_ir.get("provisional_family"))
    if not primitive_hypotheses or not provisional_family:
        return {}
    normalized_family = _normalized_family_key(provisional_family)
    if not normalized_family:
        return {}
    for family_key, payload in _PRIMITIVE_FAMILY_RUNTIME_HINTS.items():
        if normalized_family in _family_match_keys(family_key):
            return deepcopy(payload)
    return {}


def _stack_candidates_from_runtime_and_report(
    *,
    runtime_recipe: Dict[str, Any],
    report: Dict[str, Any],
) -> list[Dict[str, Any]]:
    candidates: list[Dict[str, Any]] = []
    selected_stack = runtime_recipe.get("stack_selection") if isinstance(runtime_recipe.get("stack_selection"), dict) else {}
    selected_stack_id = _string_or_none(selected_stack.get("selected_stack_id"))
    if selected_stack_id:
        selected_language, _, selected_framework = selected_stack_id.partition("/")
        candidate: Dict[str, Any] = {
            "stack_id": selected_stack_id.lower(),
            "source": _string_or_none(selected_stack.get("source")) or "runtime_selection",
        }
        if selected_language and selected_framework:
            candidate["language"] = selected_language.lower()
            candidate["framework"] = selected_framework.lower()
        confidence = _string_or_none(selected_stack.get("confidence"))
        if confidence:
            candidate["confidence"] = confidence.lower()
        score = selected_stack.get("score")
        if isinstance(score, (int, float)):
            candidate["score"] = round(float(score), 3)
        sources = selected_stack.get("sources")
        if isinstance(sources, list):
            candidate["sources"] = [
                str(item).strip().lower()
                for item in sources
                if isinstance(item, str) and str(item).strip()
            ]
        candidate["selected"] = bool(selected_stack.get("resolved"))
        candidates.append(candidate)

    raw_candidates = []
    if isinstance(runtime_recipe.get("stack_hypotheses"), list):
        raw_candidates.extend(runtime_recipe.get("stack_hypotheses") or [])
    elif isinstance(report.get("tech_stack_candidates"), list):
        raw_candidates.extend(report.get("tech_stack_candidates") or [])
    if not isinstance(raw_candidates, list):
        return candidates
    for entry in raw_candidates:
        if not isinstance(entry, dict):
            continue
        language = _string_or_none(entry.get("language"))
        framework = _string_or_none(entry.get("framework"))
        stack_id = _string_or_none(entry.get("stack_id"))
        if not stack_id and language and framework:
            stack_id = f"{language.lower()}/{framework.lower()}"
        if not stack_id:
            continue
        candidate: Dict[str, Any] = {
            "stack_id": stack_id.lower(),
            "source": _string_or_none(entry.get("source"))
            or (
                entry.get("sources")[0]
                if isinstance(entry.get("sources"), list)
                and entry.get("sources")
                and isinstance(entry.get("sources")[0], str)
                else None
            )
            or "researcher_candidate",
        }
        if language:
            candidate["language"] = language.lower()
        if framework:
            candidate["framework"] = framework.lower()
        confidence = _string_or_none(entry.get("confidence"))
        if confidence:
            candidate["confidence"] = confidence.lower()
        score = entry.get("score")
        if isinstance(score, (int, float)):
            candidate["score"] = round(float(score), 3)
        sources = entry.get("sources")
        if isinstance(sources, list):
            candidate["sources"] = [
                str(item).strip().lower()
                for item in sources
                if isinstance(item, str) and str(item).strip()
            ]
        candidates.append(candidate)
    return candidates


def _merge_family_candidates(
    existing: list[Dict[str, Any]],
    researcher: list[Dict[str, Any]],
    *,
    resolution_confidence: str,
) -> list[Dict[str, Any]]:
    filtered_researcher = list(researcher)
    if resolution_confidence in {"high"} and isinstance(existing, list) and existing:
        authoritative_existing = _material_family_candidates(existing)
        top_existing = authoritative_existing[0] if authoritative_existing else {}
        top_source = str(top_existing.get("source") or "").strip().lower()
        top_confidence = _family_confidence_rank(top_existing.get("confidence"))
        if _is_request_resolution_family_source(top_source) and top_confidence >= _family_confidence_rank("high"):
            filtered_researcher = []
            seen_background: set[str] = set()
            for entry in researcher:
                if not isinstance(entry, dict):
                    continue
                family = _string_or_none(entry.get("family"))
                if not family:
                    continue
                family = family.lower()
                if family in seen_background:
                    continue
                source = str(entry.get("source") or "").strip().lower()
                confidence_rank = _family_confidence_rank(entry.get("confidence"))
                if not (_is_request_resolution_family_source(source) or confidence_rank >= _family_confidence_rank("high")):
                    continue
                seen_background.add(family)
                filtered_researcher.append(entry)
    prioritize_researcher = not existing or resolution_confidence not in {"high"}
    ordered = (filtered_researcher, existing) if prioritize_researcher else (existing, filtered_researcher)
    merged: list[Dict[str, Any]] = []
    seen: set[str] = set()
    for source_list in ordered:
        for entry in source_list:
            if not isinstance(entry, dict):
                continue
            family = _string_or_none(entry.get("family"))
            if not family:
                continue
            family = family.lower()
            if family in seen:
                continue
            seen.add(family)
            candidate = deepcopy(entry)
            candidate["family"] = family
            merged.append(candidate)
    return merged


def _merge_stack_candidates(
    existing: list[Dict[str, Any]],
    inferred: list[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    merged: list[Dict[str, Any]] = []
    seen: set[str] = set()
    for source_list in (inferred, existing):
        for entry in source_list:
            if not isinstance(entry, dict):
                continue
            stack_id = _string_or_none(entry.get("stack_id"))
            if not stack_id:
                language = _string_or_none(entry.get("language"))
                framework = _string_or_none(entry.get("framework"))
                if language and framework:
                    stack_id = f"{language.lower()}/{framework.lower()}"
            if not stack_id:
                continue
            stack_id = stack_id.lower()
            if stack_id in seen:
                continue
            seen.add(stack_id)
            candidate = deepcopy(entry)
            candidate["stack_id"] = stack_id
            if _string_or_none(candidate.get("language")):
                candidate["language"] = str(candidate["language"]).strip().lower()
            if _string_or_none(candidate.get("framework")):
                candidate["framework"] = str(candidate["framework"]).strip().lower()
            source = _string_or_none(candidate.get("source"))
            if source:
                candidate["source"] = source.lower()
            confidence = _string_or_none(candidate.get("confidence"))
            if confidence:
                candidate["confidence"] = confidence.lower()
            merged.append(candidate)
    return merged


def _primitive_hypotheses_from_report(report: Dict[str, Any]) -> list[Dict[str, Any]]:
    signature = report.get("semantic_signature") if isinstance(report.get("semantic_signature"), dict) else {}
    if not isinstance(signature, dict) or not signature:
        return []
    hypotheses: list[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for kind in ("input_vector", "sink", "exploit_precondition"):
        values = signature.get(kind) if isinstance(signature.get(kind), list) else []
        for item in values[:3]:
            value = _string_or_none(item)
            if not value:
                continue
            key = (kind, value.lower())
            if key in seen:
                continue
            seen.add(key)
            hypotheses.append(
                {
                    "kind": kind,
                    "value": value.lower(),
                    "source": "semantic_signature",
                }
            )
    return hypotheses


def _runtime_dependency_hypotheses_from_runtime_recipe(runtime_recipe: Dict[str, Any]) -> list[Dict[str, Any]]:
    recipe = runtime_recipe if isinstance(runtime_recipe, dict) else {}
    hypotheses: list[Dict[str, Any]] = []
    db = _string_or_none(recipe.get("db"))
    if db:
        hypotheses.append(
            {
                "kind": "db",
                "value": db.lower(),
                "source": "runtime_recipe",
                "confidence": "high" if db.lower() == "sqlite" else "medium",
            }
        )
    for sidecar in recipe.get("sidecars") or [] if isinstance(recipe.get("sidecars"), list) else []:
        if not isinstance(sidecar, dict):
            continue
        sidecar_type = _string_or_none(sidecar.get("type")) or _string_or_none(sidecar.get("name"))
        if not sidecar_type:
            continue
        hypotheses.append(
            {
                "kind": "sidecar",
                "value": sidecar_type.lower(),
                "source": "runtime_recipe",
                "confidence": "medium",
            }
        )
    return hypotheses


def _runtime_dependency_hypotheses_from_request_ir(request_ir: Dict[str, Any]) -> list[Dict[str, Any]]:
    hints = _primitive_runtime_hints_for_request_ir(request_ir)
    dependencies = hints.get("dependencies") if isinstance(hints.get("dependencies"), list) else []
    return [deepcopy(entry) for entry in dependencies if isinstance(entry, dict)]


def _topology_hypotheses_from_runtime_recipe(runtime_recipe: Dict[str, Any]) -> list[Dict[str, Any]]:
    recipe = runtime_recipe if isinstance(runtime_recipe, dict) else {}
    topology = _string_or_none(recipe.get("topology")) or "single_service"
    hypotheses = [
        {
            "topology": topology.lower(),
            "source": "runtime_recipe",
            "confidence": "high",
        }
    ]
    if recipe.get("requires_external_db") is True and topology.lower() != "service_plus_sidecar":
        hypotheses.append(
            {
                "topology": "service_plus_sidecar",
                "source": "runtime_feasibility",
                "confidence": "medium",
            }
        )
    return hypotheses


def _topology_hypotheses_from_request_ir(request_ir: Dict[str, Any]) -> list[Dict[str, Any]]:
    hints = _primitive_runtime_hints_for_request_ir(request_ir)
    topologies = hints.get("topologies") if isinstance(hints.get("topologies"), list) else []
    return [deepcopy(entry) for entry in topologies if isinstance(entry, dict)]


def _oracle_hypotheses_from_request_ir(request_ir: Dict[str, Any]) -> list[Dict[str, Any]]:
    hints = _primitive_runtime_hints_for_request_ir(request_ir)
    oracle_hypotheses = hints.get("oracle_hypotheses") if isinstance(hints.get("oracle_hypotheses"), list) else []
    return [deepcopy(entry) for entry in oracle_hypotheses if isinstance(entry, dict)]


def _merge_unique_mapping_entries(
    *groups: list[Dict[str, Any]],
    key_fields: tuple[str, ...],
) -> list[Dict[str, Any]]:
    merged: list[Dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for group in groups:
        if not isinstance(group, list):
            continue
        for entry in group:
            if not isinstance(entry, dict):
                continue
            key = tuple(str(entry.get(field) or "").strip().lower() for field in key_fields)
            if not key or any(not token for token in key):
                continue
            if key in seen:
                continue
            seen.add(key)
            merged.append(deepcopy(entry))
    return merged


def _scenario_oracle_profile_from_context(
    report: Dict[str, Any],
    request_ir: Dict[str, Any],
) -> Dict[str, Any]:
    proposal = _normalize_proposed_verification_contract(report) or {}
    oracle_hypotheses = _merge_unique_mapping_entries(
        _oracle_hypotheses_from_request_ir(request_ir),
        key_fields=("mode", "source"),
    )
    lead_hint = next((entry for entry in oracle_hypotheses if isinstance(entry, dict)), None)
    if _string_or_none(proposal.get("json_success_key")) or _string_or_none(proposal.get("success_mode")) == "json":
        mode = "json_contract"
    elif (
        proposal.get("negative_control_present") is True
        or proposal.get("metamorphic_present") is True
        or proposal.get("negative_controls")
        or proposal.get("metamorphic")
    ):
        mode = "stateful_text"
    elif proposal:
        mode = "text_markers"
    else:
        mode = _string_or_none((lead_hint or {}).get("mode")) or "contract_or_auto"
    return {
        "mode": mode,
        "negative_control_present": bool(
            proposal.get("negative_control_present")
            or proposal.get("negative_controls")
            or proposal.get("negative_text_markers")
            or ((lead_hint or {}).get("negative_control_present") is True)
        ),
        "metamorphic_present": bool(
            proposal.get("metamorphic_present")
            or proposal.get("metamorphic")
            or ((lead_hint or {}).get("metamorphic_present") is True)
        ),
        "source": _string_or_none(proposal.get("source"))
        or _string_or_none((lead_hint or {}).get("source"))
        or "unknown",
        "confidence": _string_or_none((lead_hint or {}).get("confidence")) or "unknown",
    }


def _provisional_family_from_request_ir(request_ir: Dict[str, Any]) -> Optional[str]:
    selection = request_ir.get("selection_decision") if isinstance(request_ir.get("selection_decision"), dict) else {}
    family_selection = selection.get("family") if isinstance(selection.get("family"), dict) else {}
    if family_selection.get("selected") is True:
        return None
    family_candidates = request_ir.get("family_candidates") if isinstance(request_ir.get("family_candidates"), list) else []
    if not family_candidates:
        return None
    top = family_candidates[0] if isinstance(family_candidates[0], dict) else {}
    family = _string_or_none(top.get("family"))
    source = _string_or_none(top.get("source")) or ""
    confidence = _string_or_none(top.get("confidence")) or ""
    if not family:
        return None
    if source == "primitive_signature":
        second = family_candidates[1] if len(family_candidates) > 1 and isinstance(family_candidates[1], dict) else {}
        second_source = _string_or_none(second.get("source")) or ""
        second_score = second.get("score")
        top_score = top.get("score")
        second_confidence = _string_or_none(second.get("confidence")) or ""
        if second_source == "primitive_signature":
            if second_confidence == confidence and second_score == top_score:
                return None
    if _is_request_resolution_family_source(source) and _family_confidence_rank(confidence) >= _family_confidence_rank("high"):
        return None
    return family.lower()


def _scenario_candidates_from_context(
    *,
    request_ir: Dict[str, Any],
    runtime_recipe: Dict[str, Any],
    report: Dict[str, Any],
) -> list[Dict[str, Any]]:
    family_candidates = request_ir.get("family_candidates") if isinstance(request_ir.get("family_candidates"), list) else []
    stack_candidates = request_ir.get("stack_candidates") if isinstance(request_ir.get("stack_candidates"), list) else []
    if not family_candidates or not stack_candidates:
        return []
    topology_hypotheses = _merge_unique_mapping_entries(
        _topology_hypotheses_from_runtime_recipe(runtime_recipe),
        _topology_hypotheses_from_request_ir(request_ir),
        key_fields=("topology",),
    )
    dependency_hypotheses = _merge_unique_mapping_entries(
        _runtime_dependency_hypotheses_from_runtime_recipe(runtime_recipe),
        _runtime_dependency_hypotheses_from_request_ir(request_ir),
        key_fields=("kind", "value"),
    )
    oracle_hypotheses = _merge_unique_mapping_entries(
        _oracle_hypotheses_from_request_ir(request_ir),
        key_fields=("mode", "source"),
    )
    oracle_profile = _scenario_oracle_profile_from_context(report, request_ir)
    selection = request_ir.get("selection_decision") if isinstance(request_ir.get("selection_decision"), dict) else {}
    selected_family = _string_or_none(((selection.get("family") or {}) if isinstance(selection.get("family"), dict) else {}).get("selected_family"))
    selected_stack = _string_or_none(((selection.get("stack") or {}) if isinstance(selection.get("stack"), dict) else {}).get("selected_stack_id"))
    selected_topology = _string_or_none(runtime_recipe.get("topology")) or "single_service"
    candidates: list[Dict[str, Any]] = []
    seen: set[str] = set()
    for family_entry in family_candidates[:3]:
        if not isinstance(family_entry, dict):
            continue
        family = _string_or_none(family_entry.get("family"))
        if not family:
            continue
        for stack_entry in stack_candidates[:3]:
            if not isinstance(stack_entry, dict):
                continue
            stack_id = _string_or_none(stack_entry.get("stack_id"))
            if not stack_id:
                continue
            for topology_entry in topology_hypotheses[:2]:
                if not isinstance(topology_entry, dict):
                    continue
                topology = _string_or_none(topology_entry.get("topology"))
                if not topology:
                    continue
                scenario_id = f"family={family.lower()}|stack={stack_id.lower()}|topology={topology.lower()}"
                if scenario_id in seen:
                    continue
                seen.add(scenario_id)
                evidence_ids: list[str] = []
                for group in (family_entry.get("evidence_ids"), stack_entry.get("evidence_ids")):
                    if not isinstance(group, list):
                        continue
                    for item in group:
                        token = _string_or_none(item)
                        if token and token not in evidence_ids:
                            evidence_ids.append(token)
                candidate: Dict[str, Any] = {
                    "scenario_id": scenario_id,
                    "family": family.lower(),
                    "stack_id": stack_id.lower(),
                    "topology": topology.lower(),
                    "dependency_set": [
                        "service",
                        *[
                            f"{str(item.get('kind') or '').strip().lower()}:{str(item.get('value') or '').strip().lower()}"
                            for item in dependency_hypotheses
                            if str(item.get("kind") or "").strip() and str(item.get("value") or "").strip()
                        ],
                    ],
                    "oracle_profile": deepcopy(oracle_profile),
                    "family_source": _string_or_none(family_entry.get("source")) or "unknown",
                    "stack_source": _string_or_none(stack_entry.get("source")) or "unknown",
                    "family_confidence": _string_or_none(family_entry.get("confidence")) or "unknown",
                    "stack_confidence": _string_or_none(stack_entry.get("confidence")) or "unknown",
                    "topology_source": _string_or_none(topology_entry.get("source")) or "unknown",
                    "topology_confidence": _string_or_none(topology_entry.get("confidence")) or "unknown",
                    "selected": bool(
                        selected_family
                        and selected_stack
                        and family.lower() == selected_family.lower()
                        and stack_id.lower() == selected_stack.lower()
                        and topology.lower() == selected_topology.lower()
                    ),
                }
                if oracle_hypotheses:
                    candidate["oracle_hypotheses"] = deepcopy(oracle_hypotheses)
                if evidence_ids:
                    candidate["evidence_ids"] = evidence_ids
                candidates.append(candidate)
    return candidates


def _derived_request_ir_abstain_reason(
    request_ir: Dict[str, Any],
    *,
    report: Dict[str, Any],
    evidence_graph: Dict[str, Any],
) -> Optional[str]:
    explicit = _string_or_none(request_ir.get("abstain_reason"))
    if explicit:
        return explicit
    quality = _string_or_none(report.get("quality"))
    quality_reason = _string_or_none(report.get("quality_reason"))
    family_summary = (
        report.get("family_hypothesis_summary")
        if isinstance(report.get("family_hypothesis_summary"), dict)
        else {}
    )
    top_family = _string_or_none(family_summary.get("top_family"))
    top_confidence = _string_or_none(family_summary.get("top_confidence"))
    ambiguous = bool(family_summary.get("ambiguous"))
    evidence_ids = _evidence_graph_ids(evidence_graph, kind="evidence")
    if quality == "insufficient":
        return quality_reason or "insufficient_research_evidence"
    if ambiguous and top_family and top_confidence not in {"high"}:
        return "ambiguous_family_hypothesis"
    if not top_family and evidence_ids:
        return "no_family_hypothesis"
    return None


def _enriched_request_ir(
    *,
    requirement: Dict[str, Any],
    report: Dict[str, Any],
    runtime_recipe: Dict[str, Any],
    evidence_graph: Dict[str, Any],
) -> Dict[str, Any]:
    request_ir = (
        deepcopy(requirement.get("request_ir"))
        if isinstance(requirement.get("request_ir"), dict)
        else {}
    )
    if not request_ir:
        return {}
    family_support, stack_support = _support_maps_from_evidence_graph(evidence_graph)
    resolution_confidence = _string_or_none(request_ir.get("resolution_confidence")) or "unknown"
    existing_family_candidates = (
        deepcopy(request_ir.get("family_candidates"))
        if isinstance(request_ir.get("family_candidates"), list)
        else []
    )
    existing_stack_candidates = (
        deepcopy(request_ir.get("stack_candidates"))
        if isinstance(request_ir.get("stack_candidates"), list)
        else []
    )
    merged_family_candidates = _merge_family_candidates(
        existing_family_candidates,
        _family_candidates_from_report(report),
        resolution_confidence=resolution_confidence.lower(),
    )
    merged_family_candidates = _attach_family_candidate_evidence(merged_family_candidates, family_support)
    if merged_family_candidates:
        request_ir["family_candidates"] = merged_family_candidates
    merged_stack_candidates = _merge_stack_candidates(
        existing_stack_candidates,
        _stack_candidates_from_runtime_and_report(runtime_recipe=runtime_recipe, report=report),
    )
    merged_stack_candidates = _attach_stack_candidate_evidence(merged_stack_candidates, stack_support)
    if merged_stack_candidates:
        request_ir["stack_candidates"] = merged_stack_candidates
    existing_evidence_ids = [
        str(item).strip()
        for item in (request_ir.get("evidence_ids") or [])
        if isinstance(item, str) and str(item).strip()
    ]
    evidence_ids = list(existing_evidence_ids)
    for node_id in _evidence_graph_ids(evidence_graph, kind="evidence"):
        if node_id not in evidence_ids:
            evidence_ids.append(node_id)
    request_ir["evidence_ids"] = evidence_ids
    negative_hypotheses = _negative_hypotheses_from_report(report, family_support)
    if negative_hypotheses:
        request_ir["negative_hypotheses"] = negative_hypotheses
    primitive_hypotheses = _merge_unique_mapping_entries(
        request_ir.get("primitive_hypotheses") if isinstance(request_ir.get("primitive_hypotheses"), list) else [],
        _primitive_hypotheses_from_report(report),
        key_fields=("kind", "value"),
    )
    if primitive_hypotheses:
        request_ir["primitive_hypotheses"] = primitive_hypotheses
        primitive_family_candidates = _primitive_family_candidates_from_hypotheses(primitive_hypotheses)
        if primitive_family_candidates:
            merged_family_candidates = _merge_family_candidates(
                request_ir.get("family_candidates") if isinstance(request_ir.get("family_candidates"), list) else [],
                primitive_family_candidates,
                resolution_confidence=resolution_confidence.lower(),
            )
            merged_family_candidates = _attach_family_candidate_evidence(merged_family_candidates, family_support)
            if merged_family_candidates:
                request_ir["family_candidates"] = merged_family_candidates
    request_ir["provisional_family"] = _provisional_family_from_request_ir(request_ir)
    runtime_dependency_hypotheses = _merge_unique_mapping_entries(
        request_ir.get("runtime_dependency_hypotheses")
        if isinstance(request_ir.get("runtime_dependency_hypotheses"), list)
        else [],
        _runtime_dependency_hypotheses_from_runtime_recipe(runtime_recipe),
        _runtime_dependency_hypotheses_from_request_ir(request_ir),
        key_fields=("kind", "value"),
    )
    if runtime_dependency_hypotheses:
        request_ir["runtime_dependency_hypotheses"] = runtime_dependency_hypotheses
    oracle_hypotheses = _merge_unique_mapping_entries(
        request_ir.get("oracle_hypotheses") if isinstance(request_ir.get("oracle_hypotheses"), list) else [],
        _oracle_hypotheses_from_request_ir(request_ir),
        key_fields=("mode", "source"),
    )
    if oracle_hypotheses:
        request_ir["oracle_hypotheses"] = oracle_hypotheses
    topology_hypotheses = _merge_unique_mapping_entries(
        _topology_hypotheses_from_request_ir(request_ir),
        request_ir.get("topology_hypotheses") if isinstance(request_ir.get("topology_hypotheses"), list) else [],
        _topology_hypotheses_from_runtime_recipe(runtime_recipe),
        key_fields=("topology",),
    )
    if topology_hypotheses:
        request_ir["topology_hypotheses"] = topology_hypotheses
    selection_decision = _request_ir_selection_decision(
        request_ir,
        runtime_recipe=runtime_recipe,
        evidence_graph=evidence_graph,
    )
    if selection_decision:
        request_ir["selection_decision"] = selection_decision
    scenario_candidates = _merge_unique_mapping_entries(
        _scenario_candidates_from_context(
            request_ir=request_ir,
            runtime_recipe=runtime_recipe,
            report=report,
        ),
        request_ir.get("scenario_candidates") if isinstance(request_ir.get("scenario_candidates"), list) else [],
        key_fields=("scenario_id",),
    )
    if scenario_candidates:
        request_ir["scenario_candidates"] = scenario_candidates
        selection_decision = _request_ir_selection_decision(
            request_ir,
            runtime_recipe=runtime_recipe,
            evidence_graph=evidence_graph,
        )
        if selection_decision:
            request_ir["selection_decision"] = selection_decision
    request_ir["provisional_family"] = _provisional_family_from_request_ir(request_ir)
    abstain_reason = _derived_request_ir_abstain_reason(
        request_ir,
        report=report,
        evidence_graph=evidence_graph,
    )
    request_ir["abstain_reason"] = abstain_reason
    return request_ir


def _build_exploit_oracle(
    *,
    resolved: Dict[str, Any],
    proposal: Dict[str, Any],
    sources: Dict[str, str],
) -> Dict[str, Any]:
    success_signature = _string_or_none(resolved.get("success_signature"))
    flag_token = _string_or_none(resolved.get("flag_token"))
    if not success_signature:
        return {}
    output_mode = _string_or_none(resolved.get("output_mode")) or "auto"
    payload: Dict[str, Any] = {
        "schema_version": "exploit_oracle@0.1",
        "success_signature": success_signature,
        "flag_token": flag_token,
        "output_mode": output_mode,
        "base_url": _string_or_none(resolved.get("base_url")),
        "service_port": resolved.get("service_port"),
        "poc_cmd": _string_or_none(resolved.get("poc_cmd")),
    }
    assertions = deepcopy(proposal.get("assertion_program")) if isinstance(proposal.get("assertion_program"), list) else []
    for key in ("success_mode", "json_success_key", "json_success_value", "json_flag_key"):
        if key in proposal:
            payload[key] = deepcopy(proposal.get(key))
    negative_text_markers = _normalize_string_list(proposal.get("negative_text_markers"))
    if not negative_text_markers:
        negative_text_markers = _negative_markers_from_assertion_program(assertions)
    forbidden_success_markers = _normalize_string_list(proposal.get("forbidden_success_markers"))
    if not forbidden_success_markers:
        forbidden_success_markers = list(negative_text_markers)
    negative_controls = proposal.get("negative_controls")
    metamorphic = proposal.get("metamorphic")
    if success_signature and not _oracle_assertion_contains(assertions, success_signature):
        assertions.append({"op": "contains", "string": success_signature})
    if flag_token and not _oracle_assertion_contains(assertions, flag_token):
        assertions.append({"op": "contains", "string": flag_token})
    for marker in list(negative_text_markers) + [item for item in forbidden_success_markers if item not in negative_text_markers]:
        if marker and not _oracle_assertion_not_contains(assertions, marker):
            assertions.append({"op": "not_contains", "string": marker})
    if assertions:
        payload["assertion_program"] = assertions
    if negative_text_markers:
        payload["negative_text_markers"] = negative_text_markers
    if forbidden_success_markers:
        payload["forbidden_success_markers"] = forbidden_success_markers
    if isinstance(negative_controls, list) and negative_controls:
        payload["negative_controls"] = deepcopy(negative_controls)
    if isinstance(metamorphic, dict) and metamorphic:
        payload["metamorphic"] = deepcopy(metamorphic)
    if negative_text_markers or forbidden_success_markers or (isinstance(negative_controls, list) and negative_controls):
        payload["negative_control_present"] = True
    if isinstance(metamorphic, dict) and metamorphic:
        payload["metamorphic_present"] = True
    if proposal:
        proposal_source = _string_or_none(proposal.get("source")) or "proposed_verification_spec"
        if proposal_source == "researcher_report.verification_spec":
            payload["source"] = "researcher_verification_spec"
        else:
            payload["source"] = proposal_source
    else:
        payload["source"] = "resolved_contract"
    payload["source_fields"] = {
        key: value
        for key, value in {
            "success_signature": sources.get("success_signature"),
            "flag_token": sources.get("flag_token"),
            "output_mode": sources.get("output_mode"),
            "poc_cmd": sources.get("poc_cmd"),
        }.items()
        if isinstance(value, str) and value.strip()
    }
    return payload


def _oracle_assertion_contains(assertions: list[Any], needle: str) -> bool:
    target = str(needle or "").strip()
    if not target:
        return False
    for item in assertions:
        if not isinstance(item, dict):
            continue
        op = str(item.get("op") or "").strip().lower()
        if op not in {"contains", "stdout_contains"}:
            continue
        candidate = str(item.get("string") or item.get("contains") or item.get("needle") or "").strip()
        if candidate == target:
            return True
    return False


def _oracle_assertion_not_contains(assertions: list[Any], needle: str) -> bool:
    target = str(needle or "").strip()
    if not target:
        return False
    for item in assertions:
        if not isinstance(item, dict):
            continue
        op = str(item.get("op") or "").strip().lower()
        if op not in {"not_contains", "stdout_not_contains"}:
            continue
        candidate = str(item.get("string") or item.get("contains") or item.get("needle") or "").strip()
        if candidate == target:
            return True
    return False


def _request_ir_candidate_evidence_ids(request_ir: Dict[str, Any]) -> list[str]:
    evidence_ids: list[str] = []
    seen: set[str] = set()

    def _push(raw: Any) -> None:
        token = str(raw or "").strip()
        if not token or token in seen:
            return
        seen.add(token)
        evidence_ids.append(token)

    for item in (request_ir.get("evidence_ids") or []) if isinstance(request_ir, dict) else []:
        _push(item)
    for key in ("family_candidates", "stack_candidates", "identifier_candidates", "scenario_candidates"):
        group = request_ir.get(key) if isinstance(request_ir.get(key), list) else []
        for entry in group:
            if not isinstance(entry, dict):
                continue
            for item in entry.get("evidence_ids") or []:
                _push(item)
    return evidence_ids


def _scenario_selection_payload(
    request_ir: Dict[str, Any],
    *,
    runtime_recipe: Dict[str, Any],
    authority_map: Dict[str, str],
    family_payload: Dict[str, Any],
    stack_payload: Dict[str, Any],
) -> Dict[str, Any]:
    scenario_candidates = request_ir.get("scenario_candidates") if isinstance(request_ir.get("scenario_candidates"), list) else []
    normalized_candidates = [entry for entry in scenario_candidates if isinstance(entry, dict)]
    if not normalized_candidates:
        return {}

    selected_family = _string_or_none(family_payload.get("selected_family")) if family_payload.get("selected") is True else None
    selected_stack = _string_or_none(stack_payload.get("selected_stack_id")) if stack_payload.get("selected") is True else None
    runtime_topology = _string_or_none(runtime_recipe.get("topology")) or "single_service"
    selected_candidate: Optional[Dict[str, Any]] = None
    for entry in normalized_candidates:
        if entry.get("selected") is True:
            selected_candidate = entry
            break
    if selected_candidate is None and selected_family and selected_stack:
        for entry in normalized_candidates:
            family = _string_or_none(entry.get("family"))
            stack_id = _string_or_none(entry.get("stack_id"))
            topology = _string_or_none(entry.get("topology"))
            if (
                family
                and stack_id
                and topology
                and family.lower() == selected_family.lower()
                and stack_id.lower() == selected_stack.lower()
                and topology.lower() == runtime_topology.lower()
            ):
                selected_candidate = entry
                break

    family_selected = family_payload.get("selected") is True
    stack_selected = stack_payload.get("selected") is True
    selected_candidate_present = bool(selected_candidate)
    scenario_selected = bool(selected_candidate_present and family_selected and stack_selected)
    preview_candidate = selected_candidate or normalized_candidates[0]
    payload: Dict[str, Any] = {
        "candidate_count": len(normalized_candidates),
        "selected": scenario_selected,
        "source": "scenario_candidates",
        "top_scenario_id": _string_or_none(preview_candidate.get("scenario_id")),
        "top_family": _string_or_none(preview_candidate.get("family")),
        "top_stack_id": _string_or_none(preview_candidate.get("stack_id")),
        "topology": _string_or_none(preview_candidate.get("topology")) or runtime_topology.lower(),
        "dependency_count": len(
            [
                item
                for item in (preview_candidate.get("dependency_set") or [])
                if isinstance(item, str) and str(item).strip()
            ]
        ),
    }
    payload["selected_candidate_present"] = selected_candidate_present
    if scenario_selected:
        payload["selection_state"] = "selected"
        payload["selected_by"] = (
            "scenario_candidates.explicit_selected"
            if isinstance(selected_candidate, dict) and selected_candidate.get("selected") is True
            else "family_stack_runtime_topology_alignment"
        )
    elif selected_candidate_present:
        payload["selection_state"] = "candidate_only"
        payload["selected_by"] = "scenario_candidates.preview_candidate"
        unresolved_reasons: list[str] = []
        if not family_selected:
            unresolved_reasons.append("family_unselected")
        if not stack_selected:
            unresolved_reasons.append("stack_unselected")
        if unresolved_reasons:
            payload["unresolved_reasons"] = unresolved_reasons
    else:
        payload["selection_state"] = "unresolved"
        payload["selected_by"] = "unresolved"
        payload["unresolved_reasons"] = ["scenario_candidate_unresolved"]
    preview_oracle_profile = (
        preview_candidate.get("oracle_profile") if isinstance(preview_candidate.get("oracle_profile"), dict) else {}
    )
    if preview_oracle_profile:
        payload["top_oracle_mode"] = _string_or_none(preview_oracle_profile.get("mode"))
        payload["top_oracle_source"] = _string_or_none(preview_oracle_profile.get("source"))
        payload["top_oracle_confidence"] = _string_or_none(preview_oracle_profile.get("confidence"))
        payload["top_oracle_negative_control_present"] = preview_oracle_profile.get("negative_control_present") is True
        payload["top_oracle_metamorphic_present"] = preview_oracle_profile.get("metamorphic_present") is True
    if selected_candidate:
        payload["selected_scenario_id"] = _string_or_none(selected_candidate.get("scenario_id"))
        payload["selected_family"] = _string_or_none(selected_candidate.get("family"))
        payload["selected_stack_id"] = _string_or_none(selected_candidate.get("stack_id"))
        payload["selected_topology"] = _string_or_none(selected_candidate.get("topology")) or runtime_topology.lower()
        selected_oracle_profile = (
            selected_candidate.get("oracle_profile")
            if isinstance(selected_candidate.get("oracle_profile"), dict)
            else {}
        )
        if selected_oracle_profile:
            payload["selected_oracle_mode"] = _string_or_none(selected_oracle_profile.get("mode"))
            payload["selected_oracle_source"] = _string_or_none(selected_oracle_profile.get("source"))
            payload["selected_oracle_confidence"] = _string_or_none(selected_oracle_profile.get("confidence"))
            payload["selected_oracle_negative_control_present"] = (
                selected_oracle_profile.get("negative_control_present") is True
            )
            payload["selected_oracle_metamorphic_present"] = (
                selected_oracle_profile.get("metamorphic_present") is True
            )
        payload.update(
            _support_summary(
                [
                    item
                    for item in (selected_candidate.get("evidence_ids") or [])
                    if isinstance(item, str) and str(item).strip()
                ],
                authority_map,
            )
        )
    return payload


def _request_ir_selection_decision(
    request_ir: Dict[str, Any],
    *,
    runtime_recipe: Dict[str, Any],
    evidence_graph: Dict[str, Any],
) -> Dict[str, Any]:
    decision: Dict[str, Any] = {}
    family_support, stack_support = _support_maps_from_evidence_graph(evidence_graph)
    authority_map = _evidence_authority_map(evidence_graph)

    family_candidates = request_ir.get("family_candidates") if isinstance(request_ir.get("family_candidates"), list) else []
    normalized_family_candidates = [entry for entry in family_candidates if isinstance(entry, dict)]
    if normalized_family_candidates:
        top_family = normalized_family_candidates[0]
        family = _string_or_none(top_family.get("family"))
        source = _string_or_none(top_family.get("source")) or "unknown"
        confidence = _string_or_none(top_family.get("confidence")) or "unknown"
        unique_families = {
            str(entry.get("family") or "").strip().lower()
            for entry in normalized_family_candidates
            if str(entry.get("family") or "").strip()
        }
        family_payload: Dict[str, Any] = {
            "candidate_count": len(normalized_family_candidates),
            "top_family": family.lower() if family else None,
            "source": source.lower(),
            "confidence": confidence.lower(),
            "selected": False,
        }
        if family:
            family_payload.update(_family_support_summary(family, family_support, authority_map))
        if family and (
            (len(unique_families) == 1 and source.lower() != "primitive_signature")
            or (_is_request_resolution_family_source(source) and _family_confidence_rank(confidence) >= _family_confidence_rank("high"))
        ):
            family_payload["selected"] = True
            family_payload["selected_family"] = family.lower()
        decision["family"] = family_payload

    stack_selection = runtime_recipe.get("stack_selection") if isinstance(runtime_recipe.get("stack_selection"), dict) else {}
    if stack_selection:
        selected_stack_id = _string_or_none(stack_selection.get("selected_stack_id"))
        stack_payload: Dict[str, Any] = {
            "selected_stack_id": selected_stack_id,
            "source": _string_or_none(stack_selection.get("source")) or "unknown",
            "confidence": _string_or_none(stack_selection.get("confidence")) or "unknown",
            "margin": stack_selection.get("margin"),
            "basis": _string_or_none(stack_selection.get("basis")) or None,
            "selected": bool(stack_selection.get("resolved")),
        }
        if selected_stack_id:
            stack_payload.update(_stack_support_summary(selected_stack_id, stack_support, authority_map))
        sources = stack_selection.get("sources")
        if isinstance(sources, list):
            stack_payload["sources"] = [
                str(item).strip().lower()
                for item in sources
                if isinstance(item, str) and str(item).strip()
            ]
        decision["stack"] = stack_payload

    family_payload = decision.get("family") if isinstance(decision.get("family"), dict) else {}
    stack_payload = decision.get("stack") if isinstance(decision.get("stack"), dict) else {}
    scenario_payload = _scenario_selection_payload(
        request_ir,
        runtime_recipe=runtime_recipe,
        authority_map=authority_map,
        family_payload=family_payload,
        stack_payload=stack_payload,
    )
    if scenario_payload:
        decision["scenario"] = scenario_payload

    if decision:
        decision["ready_for_materialization"] = bool(family_payload.get("selected")) and bool(stack_payload.get("selected"))
        stack_basis = str(stack_payload.get("basis") or "").strip().lower()
        stack_is_explicit = stack_basis == "explicit_requirement"
        scenario_selected = scenario_payload.get("selected") is True if scenario_payload else False
        scenario_evidence_backed = scenario_payload.get("evidence_backed") is True if scenario_payload else False
        decision["open_world_evidence_ready"] = (
            decision["ready_for_materialization"]
            and family_payload.get("evidence_backed") is True
            and (stack_payload.get("evidence_backed") is True or stack_is_explicit)
            and (not scenario_payload or (scenario_selected and scenario_evidence_backed))
        )
    return decision


def _name_only_planning_focus_summary(
    *,
    name_only_contract: Dict[str, Any],
    request_ir: Dict[str, Any],
    family_candidate_summary: Dict[str, Any],
    stack_candidate_summary: Dict[str, Any],
    exploit_oracle: Dict[str, Any],
) -> Dict[str, Any]:
    ordered_focuses: list[str] = []
    by_focus: Dict[str, list[str]] = {}

    def _add_focus(focus: str, reason: str) -> None:
        token = str(focus or "").strip().lower()
        reason_token = str(reason or "").strip().lower()
        if not token or not reason_token:
            return
        reasons = by_focus.setdefault(token, [])
        if token not in ordered_focuses:
            ordered_focuses.append(token)
        if reason_token not in reasons:
            reasons.append(reason_token)

    candidate_count = family_candidate_summary.get("candidate_count")
    material_candidate_count = family_candidate_summary.get("material_candidate_count")
    family_ambiguous = family_candidate_summary.get("material_ambiguous")
    working_family = str(family_candidate_summary.get("working_family") or "").strip().lower()
    if not working_family and not isinstance(candidate_count, int):
        candidate_count = 0
    if not isinstance(material_candidate_count, int):
        material_candidate_count = candidate_count if isinstance(candidate_count, int) else 0
    if not isinstance(family_ambiguous, bool):
        family_ambiguous = bool(family_candidate_summary.get("ambiguous")) or (
            isinstance(material_candidate_count, int) and material_candidate_count > 1
        )
    if not working_family:
        _add_focus("family_disambiguation", "family_unresolved")
    if family_ambiguous:
        _add_focus("family_disambiguation", "family_ambiguous")

    working_stack_id = str(stack_candidate_summary.get("working_stack_id") or "").strip().lower()
    stack_selection_resolved = stack_candidate_summary.get("selection_resolved") is True
    if not working_stack_id:
        _add_focus("stack_or_runtime_design", "stack_unresolved")
    if stack_candidate_summary.get("working_stack_defaulted") is True:
        _add_focus("stack_or_runtime_design", "stack_defaulted")
    if stack_candidate_summary.get("ambiguous") is True and not stack_selection_resolved:
        _add_focus("stack_or_runtime_design", "stack_ambiguous")

    effective_mode = str(name_only_contract.get("effective_mode") or "").strip().lower()
    require_open_world_oracle = effective_mode in {"dynamic", "dynamic_eval", "strict_dynamic"}
    require_remote_research = name_only_contract.get("require_remote_research") is True
    require_evidence_authority = require_open_world_oracle or require_remote_research
    request_ir_evidence_ids = _request_ir_candidate_evidence_ids(request_ir)
    if require_evidence_authority and not request_ir_evidence_ids:
        _add_focus("evidence_authority", "family_candidate_evidence_missing")
    selection_decision = request_ir.get("selection_decision") if isinstance(request_ir.get("selection_decision"), dict) else {}
    family_decision = selection_decision.get("family") if isinstance(selection_decision.get("family"), dict) else {}
    stack_decision = selection_decision.get("stack") if isinstance(selection_decision.get("stack"), dict) else {}
    scenario_decision = selection_decision.get("scenario") if isinstance(selection_decision.get("scenario"), dict) else {}
    family_selected = family_decision.get("selected") is True
    stack_selected = stack_decision.get("selected") is True
    scenario_selected = scenario_decision.get("selected") is True
    family_evidence_backed = family_decision.get("evidence_backed") is True
    stack_evidence_backed = stack_decision.get("evidence_backed") is True
    stack_basis = str(stack_decision.get("basis") or "").strip().lower()
    stack_is_explicit_or_locked = stack_basis == "explicit_requirement" or stack_candidate_summary.get("working_stack_locked") is True
    if require_open_world_oracle:
        if family_selected and not family_evidence_backed:
            _add_focus("evidence_authority", "selected_family_support_missing")
        if stack_selected and not stack_evidence_backed and not stack_is_explicit_or_locked:
            _add_focus("evidence_authority", "selected_stack_support_missing")
        if family_selected and family_decision.get("high_or_medium_authority_support") is not True:
            _add_focus("evidence_authority", "selected_family_authority_thin")
        if stack_selected and not stack_is_explicit_or_locked and stack_decision.get("high_or_medium_authority_support") is not True:
            _add_focus("evidence_authority", "selected_stack_authority_thin")
        if family_selected and stack_selected and scenario_decision.get("candidate_count"):
            if not scenario_selected:
                _add_focus("topology_or_scenario_design", "scenario_unresolved")
            elif scenario_decision.get("evidence_backed") is not True:
                _add_focus("evidence_authority", "selected_scenario_support_missing")
            if scenario_selected and scenario_decision.get("high_or_medium_authority_support") is not True:
                _add_focus("evidence_authority", "selected_scenario_authority_thin")
    if require_open_world_oracle:
        if exploit_oracle.get("negative_control_present") is not True:
            _add_focus("oracle_realism", "negative_control_missing")
        if exploit_oracle.get("metamorphic_present") is not True:
            _add_focus("oracle_realism", "metamorphic_missing")
    if name_only_contract.get("require_independent_verifier") is True:
        _add_focus("independent_verification", "independent_verifier_required")
    if require_remote_research and not request_ir_evidence_ids:
        _add_focus("evidence_authority", "remote_research_evidence_missing")
    if (
        require_open_world_oracle
        and working_family
        and working_stack_id
        and stack_selection_resolved
        and stack_candidate_summary.get("working_stack_defaulted") is not True
        and request_ir_evidence_ids
        and (not family_selected or family_evidence_backed)
        and (not stack_selected or stack_evidence_backed or stack_is_explicit_or_locked)
        and (not scenario_decision or scenario_decision.get("evidence_backed") is True)
        and exploit_oracle.get("negative_control_present") is True
        and exploit_oracle.get("metamorphic_present") is True
    ):
        _add_focus("open_world_generation", "bounded_dynamic_generation")

    if not ordered_focuses:
        ordered_focuses.append("generation_execution")
        by_focus["generation_execution"] = ["generation_ready"]

    reason_tokens: list[str] = []
    for focus in ordered_focuses:
        for reason in by_focus.get(focus, []):
            if reason not in reason_tokens:
                reason_tokens.append(reason)

    return {
        "primary_focus": ordered_focuses[0],
        "focuses": ordered_focuses,
        "by_focus": by_focus,
        "reason_tokens": reason_tokens,
    }


def _build_name_only_generation_spec(
    *,
    requirement: Dict[str, Any],
    report: Dict[str, Any],
    runtime_recipe: Dict[str, Any],
    runtime_graph: Dict[str, Any],
    evidence_graph: Dict[str, Any],
    exploit_oracle: Dict[str, Any],
    request_ir: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    name_only_contract = build_name_only_contract(requirement=requirement)
    if name_only_contract.get("enabled") is not True:
        return {}
    request_ir = (
        deepcopy(request_ir)
        if isinstance(request_ir, dict)
        else deepcopy(requirement.get("request_ir"))
        if isinstance(requirement.get("request_ir"), dict)
        else {}
    )
    request_identity = (
        deepcopy(requirement.get("request_identity"))
        if isinstance(requirement.get("request_identity"), dict)
        else {}
    )
    name_resolution = (
        deepcopy(requirement.get("name_resolution"))
        if isinstance(requirement.get("name_resolution"), dict)
        else {}
    )
    request_label = str(
        (request_ir or {}).get("request_label")
        or (request_identity or {}).get("request_label")
        or requirement.get("vuln_name")
        or ""
    ).strip()
    resolved_vuln_id = str(
        (request_ir or {}).get("resolved_vuln_id")
        or (request_identity or {}).get("resolved_vuln_id")
        or (name_resolution or {}).get("resolved_vuln_id")
        or requirement.get("vuln_id")
        or ""
    ).strip()
    family_summary = (
        deepcopy(report.get("family_hypothesis_summary"))
        if isinstance(report.get("family_hypothesis_summary"), dict)
        else {}
    )
    researcher_family = str((family_summary or {}).get("top_family") or "").strip().lower()
    researcher_confidence = str((family_summary or {}).get("top_confidence") or "").strip().lower()
    resolution_basis = str(
        (request_ir or {}).get("resolution_match_class")
        or (request_identity or {}).get("match_class")
        or (name_resolution or {}).get("match_class")
        or ""
    ).strip().lower()
    resolution_confidence = str(
        (request_ir or {}).get("resolution_confidence")
        or (request_identity or {}).get("confidence")
        or (name_resolution or {}).get("confidence")
        or ""
    ).strip().lower()
    request_identity_family = ""
    if resolution_basis in {"catalog_alias", "exact_identifier"} and resolution_confidence == "high":
        entry = resolve_vuln_catalog_entry(vuln_id=resolved_vuln_id, raw_label=request_label)
        if isinstance(entry, dict):
            request_identity_family = str(entry.get("family") or "").strip().lower()
    working_family = researcher_family
    working_family_source = "researcher_family_hypothesis" if working_family else ""
    if not working_family and request_identity_family:
        working_family = request_identity_family
        working_family_source = "request_ir" if request_ir else "request_identity"
    elif (
        request_identity_family
        and working_family
        and working_family != request_identity_family
        and researcher_confidence in {"", "low"}
    ):
        working_family = request_identity_family
        working_family_source = "request_ir_fallback" if request_ir else "request_identity_fallback"
    stack_hypotheses = runtime_recipe.get("stack_hypotheses") if isinstance(runtime_recipe.get("stack_hypotheses"), list) else []
    family_candidates = request_ir.get("family_candidates") if isinstance(request_ir.get("family_candidates"), list) else []
    family_candidate_summary: Dict[str, Any] = {
        "candidate_count": 0,
        "working_family": working_family or None,
        "working_family_source": working_family_source or None,
        "ambiguous": bool((family_summary or {}).get("ambiguous")),
        "material_candidate_count": 0,
        "material_ambiguous": bool((family_summary or {}).get("ambiguous")),
    }
    if isinstance(family_candidates, list) and family_candidates:
        unique_families = []
        seen_families: set[str] = set()
        for entry in family_candidates:
            if not isinstance(entry, dict):
                continue
            family = str(entry.get("family") or "").strip().lower()
            if not family or family in seen_families:
                continue
            seen_families.add(family)
            unique_families.append(entry)
        if unique_families:
            background_family_candidates: list[Dict[str, Any]] = []
            background_seen: set[str] = set(seen_families)
            for entry in _family_candidates_from_report(report):
                if not isinstance(entry, dict):
                    continue
                family = str(entry.get("family") or "").strip().lower()
                if not family or family in background_seen:
                    continue
                background_seen.add(family)
                background_family_candidates.append(entry)
            top_family = unique_families[0]
            material_families = _material_family_candidates(unique_families)
            material_top_family = material_families[0] if material_families else top_family
            family_candidate_summary.update(
                {
                    "candidate_count": len(unique_families) + len(background_family_candidates),
                    "top_family": str(top_family.get("family") or "").strip().lower() or None,
                    "top_source": str(top_family.get("source") or "").strip().lower() or None,
                    "top_confidence": str(top_family.get("confidence") or "").strip().lower() or None,
                    "material_candidate_count": len(material_families),
                    "material_top_family": str(material_top_family.get("family") or "").strip().lower() or None,
                    "material_top_source": str(material_top_family.get("source") or "").strip().lower() or None,
                    "material_top_confidence": str(material_top_family.get("confidence") or "").strip().lower() or None,
                    "deprioritized_candidate_count": max(
                        len(background_family_candidates) + len(unique_families) - len(material_families),
                        0,
                    ),
                    "ambiguous": family_candidate_summary["ambiguous"] or len(material_families) > 1,
                    "material_ambiguous": family_candidate_summary["material_ambiguous"] or len(material_families) > 1,
                }
            )
    elif request_identity_family:
        family_candidate_summary.update(
            {
                "candidate_count": 1,
                "top_family": request_identity_family,
                "top_source": "request_resolution",
                "top_confidence": resolution_confidence or None,
                "material_candidate_count": 1,
                "material_top_family": request_identity_family,
                "material_top_source": "request_resolution",
                "material_top_confidence": resolution_confidence or None,
            }
        )
    raw_negative_hypotheses = request_ir.get("negative_hypotheses") if isinstance(request_ir.get("negative_hypotheses"), list) else []
    negative_hypotheses = [
        deepcopy(item)
        for item in raw_negative_hypotheses
        if isinstance(item, dict)
    ]
    if not negative_hypotheses:
        contradictory_families = []
        raw_contradictory = family_summary.get("contradictory_families") if isinstance(family_summary, dict) else []
        if isinstance(raw_contradictory, list):
            contradictory_families = [
                str(item).strip().lower()
                for item in raw_contradictory
                if isinstance(item, str) and str(item).strip()
            ]
        negative_hypotheses = [
            {
                "family": family,
                "source": "researcher_contradiction",
            }
            for family in contradictory_families
        ]
    working_stack_id = None
    language = str(runtime_recipe.get("language") or "").strip().lower()
    framework = str(runtime_recipe.get("framework") or "").strip().lower()
    if language and framework:
        working_stack_id = f"{language}/{framework}"
    raw_stack_selection = runtime_recipe.get("stack_selection") if isinstance(runtime_recipe.get("stack_selection"), dict) else {}
    stack_candidate_summary: Dict[str, Any] = {
        "candidate_count": 0,
        "working_stack_id": working_stack_id or None,
        "working_stack_source": str(runtime_recipe.get("stack_source") or "").strip().lower() or None,
        "working_stack_locked": bool(runtime_recipe.get("stack_locked")),
        "working_stack_defaulted": bool(runtime_recipe.get("stack_defaulted")),
        "ambiguous": False,
        "selection_resolved": bool((raw_stack_selection or {}).get("resolved")),
        "selection_confidence": str((raw_stack_selection or {}).get("confidence") or "").strip().lower() or None,
        "selection_margin": raw_stack_selection.get("margin"),
        "selection_score": raw_stack_selection.get("score"),
        "selection_basis": str((raw_stack_selection or {}).get("basis") or "").strip().lower() or None,
        "selection_sources": deepcopy(raw_stack_selection.get("sources")) if isinstance(raw_stack_selection.get("sources"), list) else [],
    }
    if isinstance(stack_hypotheses, list) and stack_hypotheses:
        unique_stacks = []
        seen_stacks: set[str] = set()
        for entry in stack_hypotheses:
            if not isinstance(entry, dict):
                continue
            stack_id = str(entry.get("stack_id") or "").strip().lower()
            if not stack_id:
                cand_language = str(entry.get("language") or "").strip().lower()
                cand_framework = str(entry.get("framework") or "").strip().lower()
                if cand_language and cand_framework:
                    stack_id = f"{cand_language}/{cand_framework}"
            if not stack_id or stack_id in seen_stacks:
                continue
            seen_stacks.add(stack_id)
            unique_stacks.append((stack_id, entry))
        if unique_stacks:
            top_stack_id, top_stack = unique_stacks[0]
            stack_candidate_summary.update(
                {
                    "candidate_count": len(unique_stacks),
                    "top_stack_id": top_stack_id or None,
                    "top_source": str(top_stack.get("source") or "").strip().lower() or None,
                    "top_confidence": str(top_stack.get("confidence") or "").strip().lower() or None,
                    "ambiguous": len(unique_stacks) > 1,
                }
            )
    if stack_candidate_summary.get("selection_resolved") is True and working_stack_id:
        stack_candidate_summary["selected_stack_id"] = working_stack_id
    selection_decision = request_ir.get("selection_decision") if isinstance(request_ir.get("selection_decision"), dict) else {}
    family_selection = selection_decision.get("family") if isinstance(selection_decision.get("family"), dict) else {}
    stack_selection = selection_decision.get("stack") if isinstance(selection_decision.get("stack"), dict) else {}
    scenario_selection = selection_decision.get("scenario") if isinstance(selection_decision.get("scenario"), dict) else {}
    if family_selection:
        family_candidate_summary["selection_evidence_backed"] = family_selection.get("evidence_backed") is True
        family_candidate_summary["selection_support_count"] = int(family_selection.get("support_count") or 0)
        family_candidate_summary["selection_support_by_source_authority"] = deepcopy(
            family_selection.get("support_by_source_authority")
        ) if isinstance(family_selection.get("support_by_source_authority"), dict) else {}
    if stack_selection:
        stack_candidate_summary["selection_evidence_backed"] = stack_selection.get("evidence_backed") is True
        stack_candidate_summary["selection_support_count"] = int(stack_selection.get("support_count") or 0)
        stack_candidate_summary["selection_support_by_source_authority"] = deepcopy(
            stack_selection.get("support_by_source_authority")
        ) if isinstance(stack_selection.get("support_by_source_authority"), dict) else {}
    provisional_family = _string_or_none(request_ir.get("provisional_family"))
    primitive_hypotheses = deepcopy(request_ir.get("primitive_hypotheses")) if isinstance(request_ir.get("primitive_hypotheses"), list) else []
    runtime_dependency_hypotheses = (
        deepcopy(request_ir.get("runtime_dependency_hypotheses"))
        if isinstance(request_ir.get("runtime_dependency_hypotheses"), list)
        else []
    )
    oracle_hypotheses = (
        deepcopy(request_ir.get("oracle_hypotheses"))
        if isinstance(request_ir.get("oracle_hypotheses"), list)
        else []
    )
    topology_hypotheses = (
        deepcopy(request_ir.get("topology_hypotheses"))
        if isinstance(request_ir.get("topology_hypotheses"), list)
        else []
    )
    scenario_candidates = deepcopy(request_ir.get("scenario_candidates")) if isinstance(request_ir.get("scenario_candidates"), list) else []
    selected_scenarios = [
        entry
        for entry in scenario_candidates
        if isinstance(entry, dict) and entry.get("selected") is True
    ]
    lead_scenario = None
    if selected_scenarios:
        lead_scenario = selected_scenarios[0]
    else:
        lead_scenario = next((entry for entry in scenario_candidates if isinstance(entry, dict)), None)
    evidence_backed_scenario_count = 0
    for entry in scenario_candidates:
        if not isinstance(entry, dict):
            continue
        evidence_ids = entry.get("evidence_ids") if isinstance(entry.get("evidence_ids"), list) else []
        if any(isinstance(item, str) and str(item).strip() for item in evidence_ids):
            evidence_backed_scenario_count += 1
    scenario_candidate_summary: Dict[str, Any] = {
        "candidate_count": len([entry for entry in scenario_candidates if isinstance(entry, dict)]),
        "selected_candidate_count": len(selected_scenarios),
        "evidence_backed_candidate_count": evidence_backed_scenario_count,
    }
    if isinstance(lead_scenario, dict):
        scenario_candidate_summary.update(
            {
                "top_scenario_id": _string_or_none(lead_scenario.get("scenario_id")),
                "top_family": _string_or_none(lead_scenario.get("family")),
                "top_stack_id": _string_or_none(lead_scenario.get("stack_id")),
                "topology": _string_or_none(lead_scenario.get("topology")),
            }
        )
        top_oracle_profile = (
            lead_scenario.get("oracle_profile") if isinstance(lead_scenario.get("oracle_profile"), dict) else {}
        )
        if top_oracle_profile:
            scenario_candidate_summary["top_oracle_mode"] = _string_or_none(top_oracle_profile.get("mode"))
            scenario_candidate_summary["top_oracle_source"] = _string_or_none(top_oracle_profile.get("source"))
    if selected_scenarios:
        scenario_candidate_summary["selected_scenario_id"] = _string_or_none(selected_scenarios[0].get("scenario_id"))
        selected_oracle_profile = (
            selected_scenarios[0].get("oracle_profile")
            if isinstance(selected_scenarios[0].get("oracle_profile"), dict)
            else {}
        )
        if selected_oracle_profile:
            scenario_candidate_summary["selected_oracle_mode"] = _string_or_none(selected_oracle_profile.get("mode"))
            scenario_candidate_summary["selected_oracle_source"] = _string_or_none(selected_oracle_profile.get("source"))
    if scenario_selection:
        scenario_candidate_summary["selection_evidence_backed"] = scenario_selection.get("evidence_backed") is True
        scenario_candidate_summary["selection_support_count"] = int(scenario_selection.get("support_count") or 0)
        scenario_candidate_summary["selection_support_by_source_authority"] = deepcopy(
            scenario_selection.get("support_by_source_authority")
        ) if isinstance(scenario_selection.get("support_by_source_authority"), dict) else {}
        scenario_candidate_summary["selection_state"] = _string_or_none(scenario_selection.get("selection_state")) or None
        scenario_candidate_summary["selected_candidate_present"] = (
            scenario_selection.get("selected_candidate_present") is True
        )
        scenario_candidate_summary["selected_by"] = _string_or_none(scenario_selection.get("selected_by")) or None
        unresolved_reasons = scenario_selection.get("unresolved_reasons")
        if isinstance(unresolved_reasons, list):
            scenario_candidate_summary["selection_unresolved_reasons"] = [
                str(item).strip().lower()
                for item in unresolved_reasons
                if isinstance(item, str) and str(item).strip()
            ]
    payload: Dict[str, Any] = {
        "schema_version": "name_only_generation_spec@0.1",
        "request_label": request_label or None,
        "resolved_vuln_id": resolved_vuln_id or None,
        "request_ir": request_ir,
        "request_identity": request_identity,
        "name_resolution": name_resolution,
        "effective_mode": str(name_only_contract.get("effective_mode") or "compatibility"),
        "required_contract": deepcopy(name_only_contract),
        "family_working_hypothesis": working_family or None,
        "family_hypothesis_source": working_family_source or None,
        "researcher_family_hypothesis": researcher_family or None,
        "request_identity_family": request_identity_family or None,
        "family_hypothesis_summary": family_summary,
        "family_candidate_summary": family_candidate_summary,
        "provisional_family": provisional_family or None,
        "primitive_hypotheses": primitive_hypotheses,
        "negative_hypotheses": negative_hypotheses,
        "identifier_candidate_summary": {
            "candidate_count": len(
                request_ir.get("identifier_candidates")
                if isinstance(request_ir.get("identifier_candidates"), list)
                else []
            ),
            "resolved_vuln_id_candidate": _string_or_none(request_ir.get("resolved_vuln_id_candidate"))
            if isinstance(request_ir, dict)
            else None,
            "abstain_reason": _string_or_none(request_ir.get("abstain_reason")) if isinstance(request_ir, dict) else None,
        },
        "runtime_dependency_hypotheses": runtime_dependency_hypotheses,
        "oracle_hypotheses": oracle_hypotheses,
        "topology_hypotheses": topology_hypotheses,
        "scenario_candidate_summary": scenario_candidate_summary,
        "runtime_recipe_summary": {
            key: deepcopy(runtime_recipe.get(key))
            for key in (
                "language",
                "framework",
                "stack_locked",
                "stack_defaulted",
                "stack_source",
                "topology",
                "service_port",
                "db",
                "network_mode",
            )
            if key in runtime_recipe
        },
        "runtime_graph_summary": _runtime_graph_summary(runtime_graph),
        "evidence_graph_summary": _evidence_graph_summary(evidence_graph),
        "stack_hypotheses": deepcopy(stack_hypotheses),
        "stack_candidate_summary": stack_candidate_summary,
        "exploit_oracle_summary": {
            key: deepcopy(exploit_oracle.get(key))
            for key in (
                "success_signature",
                "flag_token",
                "negative_text_markers",
                "forbidden_success_markers",
                "negative_controls",
                "negative_control_present",
                "metamorphic",
                "metamorphic_present",
                "poc_cmd",
                "output_mode",
                "source",
                "success_mode",
                "json_success_key",
                "json_flag_key",
                "assertion_program",
            )
            if key in exploit_oracle
        },
    }
    if raw_stack_selection:
        payload["runtime_recipe_summary"]["stack_selection"] = deepcopy(raw_stack_selection)
    payload["planning_focus_summary"] = _name_only_planning_focus_summary(
        name_only_contract=name_only_contract,
        request_ir=request_ir,
        family_candidate_summary=family_candidate_summary,
        stack_candidate_summary=stack_candidate_summary,
        exploit_oracle=exploit_oracle,
    )
    return payload


def _build_staged_synthesis(
    *,
    requirement: Dict[str, Any],
    request_ir: Dict[str, Any],
    runtime_recipe: Dict[str, Any],
    executor_plan: Dict[str, Any],
    exploit_oracle: Dict[str, Any],
    name_only_generation_spec: Dict[str, Any],
    manifest: Dict[str, Any],
    workspace_dir: Optional[Path],
    resolved: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(requirement, dict):
        return {}
    request_ir = request_ir if isinstance(request_ir, dict) else {}
    runtime_recipe = runtime_recipe if isinstance(runtime_recipe, dict) else {}
    executor_plan = executor_plan if isinstance(executor_plan, dict) else {}
    exploit_oracle = exploit_oracle if isinstance(exploit_oracle, dict) else {}
    manifest = manifest if isinstance(manifest, dict) else {}
    workspace_dir = workspace_dir if isinstance(workspace_dir, Path) else None
    resolved = resolved if isinstance(resolved, dict) else {}
    name_only_generation_spec = (
        name_only_generation_spec if isinstance(name_only_generation_spec, dict) else {}
    )

    request_label = _string_or_none(request_ir.get("request_label")) or _string_or_none(requirement.get("vuln_name"))
    selection_decision = request_ir.get("selection_decision") if isinstance(request_ir.get("selection_decision"), dict) else {}
    family_selection = selection_decision.get("family") if isinstance(selection_decision.get("family"), dict) else {}
    stack_selection = selection_decision.get("stack") if isinstance(selection_decision.get("stack"), dict) else {}
    scenario_selection = selection_decision.get("scenario") if isinstance(selection_decision.get("scenario"), dict) else {}
    planning_focus_summary = (
        name_only_generation_spec.get("planning_focus_summary")
        if isinstance(name_only_generation_spec.get("planning_focus_summary"), dict)
        else {}
    )
    runtime_dependency_hypotheses = (
        deepcopy(request_ir.get("runtime_dependency_hypotheses"))
        if isinstance(request_ir.get("runtime_dependency_hypotheses"), list)
        else []
    )
    oracle_hypotheses = (
        deepcopy(request_ir.get("oracle_hypotheses"))
        if isinstance(request_ir.get("oracle_hypotheses"), list)
        else []
    )
    topology_hypotheses = (
        deepcopy(request_ir.get("topology_hypotheses"))
        if isinstance(request_ir.get("topology_hypotheses"), list)
        else []
    )
    lead_db_hint = next(
        (
            entry
            for entry in runtime_dependency_hypotheses
            if isinstance(entry, dict)
            and str(entry.get("kind") or "").strip().lower() == "db"
            and _string_or_none(entry.get("value"))
        ),
        None,
    )
    lead_topology_hint = next(
        (
            entry
            for entry in topology_hypotheses
            if isinstance(entry, dict) and _string_or_none(entry.get("topology"))
        ),
        None,
    )
    lead_oracle_hint = next(
        (
            entry
            for entry in oracle_hypotheses
            if isinstance(entry, dict)
            and (
                _string_or_none(entry.get("mode"))
                or _string_or_none(entry.get("output_mode"))
                or entry.get("negative_control_present") is True
                or entry.get("metamorphic_present") is True
            )
        ),
        None,
    )
    language = _string_or_none(runtime_recipe.get("language"))
    framework = _string_or_none(runtime_recipe.get("framework"))
    runtime_stack_id = f"{language.lower()}/{framework.lower()}" if language and framework else ""
    scenario_candidates = (
        deepcopy(request_ir.get("scenario_candidates"))
        if isinstance(request_ir.get("scenario_candidates"), list)
        else []
    )
    selected_scenario_id = _string_or_none(scenario_selection.get("selected_scenario_id"))
    selected_scenario_entry = next(
        (
            entry
            for entry in scenario_candidates
            if isinstance(entry, dict)
            and selected_scenario_id
            and _string_or_none(entry.get("scenario_id")) == selected_scenario_id
        ),
        None,
    )
    if selected_scenario_entry is None:
        selected_scenario_entry = next(
            (
                entry
                for entry in scenario_candidates
                if isinstance(entry, dict) and entry.get("selected") is True
            ),
            None,
        )
    if selected_scenario_entry is None:
        selected_scenario_entry = next((entry for entry in scenario_candidates if isinstance(entry, dict)), None)
    selected_dependency_set = [
        str(item).strip().lower()
        for item in ((selected_scenario_entry or {}).get("dependency_set") or [])
        if isinstance(item, str) and str(item).strip()
    ]
    design_brief_required_roles: list[str] = ["service_main", "poc_entry"]
    selected_topology_for_roles = (
        _string_or_none(scenario_selection.get("selected_topology"))
        or _string_or_none((selected_scenario_entry or {}).get("topology"))
        or _string_or_none(runtime_recipe.get("topology"))
        or _string_or_none((lead_topology_hint or {}).get("topology"))
        or "single_service"
    )
    selected_oracle_mode_for_roles = (
        _string_or_none(scenario_selection.get("selected_oracle_mode"))
        or _string_or_none((((selected_scenario_entry or {}).get("oracle_profile") or {}) if isinstance((selected_scenario_entry or {}).get("oracle_profile"), dict) else {}).get("mode"))
        or _string_or_none((lead_oracle_hint or {}).get("mode"))
    )
    if selected_topology_for_roles == "service_plus_sidecar":
        design_brief_required_roles.append("dependency_sidecar")
    if any(item.startswith("db:") for item in selected_dependency_set):
        design_brief_required_roles.append("dependency_db")
    if any(item.startswith("sidecar:") for item in selected_dependency_set):
        design_brief_required_roles.append("dependency_sidecar")
    if selected_oracle_mode_for_roles == "stateful_text":
        design_brief_required_roles.append("oracle_state_checks")
    elif selected_oracle_mode_for_roles == "json_contract":
        design_brief_required_roles.append("oracle_json_contract")
    negative_control_present = bool(
        scenario_selection.get("selected_oracle_negative_control_present") is True
        or ((((selected_scenario_entry or {}).get("oracle_profile") or {}) if isinstance((selected_scenario_entry or {}).get("oracle_profile"), dict) else {}).get("negative_control_present") is True)
        or exploit_oracle.get("negative_control_present") is True
    )
    metamorphic_present = bool(
        scenario_selection.get("selected_oracle_metamorphic_present") is True
        or ((((selected_scenario_entry or {}).get("oracle_profile") or {}) if isinstance((selected_scenario_entry or {}).get("oracle_profile"), dict) else {}).get("metamorphic_present") is True)
        or exploit_oracle.get("metamorphic_present") is True
    )
    if negative_control_present:
        design_brief_required_roles.append("negative_control_cases")
    if metamorphic_present:
        design_brief_required_roles.append("metamorphic_cases")
    deduped_required_roles: list[str] = []
    for role in design_brief_required_roles:
        if role not in deduped_required_roles:
            deduped_required_roles.append(role)

    candidate_resolution = {
        "request_label": request_label,
        "resolved_vuln_id": _string_or_none(request_ir.get("resolved_vuln_id")) or _string_or_none(requirement.get("vuln_id")),
        "effective_mode": _string_or_none(name_only_generation_spec.get("effective_mode")) or name_only_mode(requirement),
        "selected_family": _string_or_none(family_selection.get("selected_family")),
        "provisional_family": _string_or_none(request_ir.get("provisional_family")),
        "selected_stack_id": _string_or_none(stack_selection.get("selected_stack_id")) or runtime_stack_id or None,
        "selected_scenario_id": _string_or_none(scenario_selection.get("selected_scenario_id")),
        "selected_topology": _string_or_none(scenario_selection.get("selected_topology"))
        or _string_or_none(scenario_selection.get("topology"))
        or _string_or_none((selected_scenario_entry or {}).get("topology"))
        or _string_or_none(runtime_recipe.get("topology"))
        or _string_or_none((lead_topology_hint or {}).get("topology"))
        or "single_service",
        "selected_oracle_mode": _string_or_none(scenario_selection.get("selected_oracle_mode"))
        or _string_or_none(scenario_selection.get("top_oracle_mode"))
        or _string_or_none((((selected_scenario_entry or {}).get("oracle_profile") or {}) if isinstance((selected_scenario_entry or {}).get("oracle_profile"), dict) else {}).get("mode"))
        or _string_or_none((lead_oracle_hint or {}).get("mode")),
        "selected_oracle_source": _string_or_none(scenario_selection.get("selected_oracle_source"))
        or _string_or_none(scenario_selection.get("top_oracle_source"))
        or _string_or_none((((selected_scenario_entry or {}).get("oracle_profile") or {}) if isinstance((selected_scenario_entry or {}).get("oracle_profile"), dict) else {}).get("source"))
        or _string_or_none((lead_oracle_hint or {}).get("source")),
        "ready_for_materialization": selection_decision.get("ready_for_materialization") is True,
        "open_world_evidence_ready": selection_decision.get("open_world_evidence_ready") is True,
        "validator": "request_ir_selection_contract",
        "repair_policy": "refresh_from_request_ir_and_runtime_recipe",
        "abort_policy": "degrade_to_prompt_guidance",
    }
    design_brief = {
        "working_family": _string_or_none(name_only_generation_spec.get("family_working_hypothesis")),
        "selected_scenario_id": candidate_resolution.get("selected_scenario_id"),
        "selected_topology": candidate_resolution.get("selected_topology"),
        "selected_oracle_mode": candidate_resolution.get("selected_oracle_mode"),
        "selected_oracle_source": candidate_resolution.get("selected_oracle_source"),
        "primary_focus": _string_or_none(planning_focus_summary.get("primary_focus")),
        "focuses": deepcopy(planning_focus_summary.get("focuses"))
        if isinstance(planning_focus_summary.get("focuses"), list)
        else [],
        "dependency_set": selected_dependency_set,
        "primitive_hypotheses": deepcopy(request_ir.get("primitive_hypotheses"))
        if isinstance(request_ir.get("primitive_hypotheses"), list)
        else [],
        "negative_hypotheses": deepcopy(request_ir.get("negative_hypotheses"))
        if isinstance(request_ir.get("negative_hypotheses"), list)
        else [],
        "required_roles": deduped_required_roles,
        "validator": "design_brief_contract",
        "repair_policy": "narrow_to_selected_family_stack_topology",
        "abort_policy": "fail_open_to_manifest_validation",
    }
    runtime_plan = {
        "stack_id": runtime_stack_id or _string_or_none(stack_selection.get("selected_stack_id")),
        "topology": _string_or_none(runtime_recipe.get("topology"))
        or candidate_resolution.get("selected_topology")
        or _string_or_none((lead_topology_hint or {}).get("topology")),
        "topology_source": (
            _string_or_none(runtime_recipe.get("topology_source"))
            if _string_or_none(runtime_recipe.get("topology_source"))
            else "runtime_recipe"
            if _string_or_none(runtime_recipe.get("topology"))
            else _string_or_none((lead_topology_hint or {}).get("source"))
            or "candidate_resolution"
        ),
        "service_port": runtime_recipe.get("service_port"),
        "network_mode": _string_or_none(runtime_recipe.get("network_mode")) or "none",
        "db": _string_or_none(runtime_recipe.get("db"))
        or _string_or_none((lead_db_hint or {}).get("value"))
        or "none",
        "db_source": (
            _string_or_none(runtime_recipe.get("db_source"))
            if _string_or_none(runtime_recipe.get("db_source"))
            else "runtime_recipe"
            if _string_or_none(runtime_recipe.get("db"))
            else _string_or_none((lead_db_hint or {}).get("source"))
            or "none"
        ),
        "sidecars": deepcopy(runtime_recipe.get("sidecars")) if isinstance(runtime_recipe.get("sidecars"), list) else [],
        "runtime_dependency_hypotheses": runtime_dependency_hypotheses,
        "topology_hypotheses": topology_hypotheses,
        "executor_health_path": _string_or_none(executor_plan.get("health_path")),
        "validator": "runtime_recipe_executor_alignment",
        "repair_policy": "prefer_executor_plan_over_guessing",
        "abort_policy": "fail_manifest_if_runtime_surface_conflicts",
    }
    executor_plan_stage = {
        "topology": _string_or_none(executor_plan.get("topology")) or _string_or_none(runtime_plan.get("topology")),
        "service_port": executor_plan.get("service_port"),
        "service_entry": _string_or_none(executor_plan.get("service_entry")) or _string_or_none(resolved.get("service_entry")),
        "poc_entry": _string_or_none(executor_plan.get("poc_entry")) or _string_or_none(resolved.get("poc_entry")),
        "health_path": _string_or_none(executor_plan.get("health_path")),
        "network_mode": _string_or_none(executor_plan.get("network_mode")) or _string_or_none(runtime_plan.get("network_mode")) or "none",
        "requires_external_db": executor_plan.get("requires_external_db") is True,
        "sidecar_count": len(executor_plan.get("sidecars")) if isinstance(executor_plan.get("sidecars"), list) else 0,
        "seed_strategy": _string_or_none(executor_plan.get("seed_strategy")),
        "validator": "executor_plan_contract",
        "repair_policy": "reuse_runtime_plan_and_runtime_graph",
        "abort_policy": "fail_manifest_if_executor_surface_conflicts",
    }
    observed_paths = sorted(set(_manifest_file_paths(manifest) + _workspace_file_paths(workspace_dir)))
    dockerfile_path = next((path for path in observed_paths if Path(path).name.lower() == "dockerfile"), None)
    dependency_paths = _dependency_manifest_paths(observed_paths)
    service_entry_path = _string_or_none(resolved.get("service_entry")) or _string_or_none(executor_plan.get("service_entry"))
    poc_entry_path = _string_or_none(resolved.get("poc_entry")) or _string_or_none(executor_plan.get("poc_entry"))
    build_safety_policy = _build_file_manifest_safety_policy(
        dockerfile_path=dockerfile_path,
        manifest=manifest,
        workspace_dir=workspace_dir,
    )
    build_ready_blockers: list[str] = []
    if not dockerfile_path:
        build_ready_blockers.append("dockerfile_missing")
    if not _path_present_in_sources(service_entry_path, observed_paths, workspace_dir):
        build_ready_blockers.append("service_entry_missing")
    if not _path_present_in_sources(poc_entry_path, observed_paths, workspace_dir):
        build_ready_blockers.append("poc_entry_missing")
    if build_safety_policy.get("package_installers_detected") and not dependency_paths:
        build_ready_blockers.append("dependency_manifest_missing_for_install")
    file_manifest = {
        "workspace_root_present": bool(isinstance(workspace_dir, Path) and workspace_dir.exists()),
        "build_context_root": ".",
        "file_count": len(observed_paths),
        "listed_paths": observed_paths,
        "dockerfile_path": dockerfile_path,
        "dockerfile_present": bool(dockerfile_path),
        "dependency_manifest_paths": dependency_paths,
        "dependency_manifest_present": bool(dependency_paths),
        "service_entry_path": service_entry_path,
        "service_entry_present": _path_present_in_sources(service_entry_path, observed_paths, workspace_dir),
        "poc_entry_path": poc_entry_path,
        "poc_entry_present": _path_present_in_sources(poc_entry_path, observed_paths, workspace_dir),
        "seed_asset_paths": _seed_asset_paths(observed_paths),
        "build_ready": not build_ready_blockers,
        "build_ready_blockers": build_ready_blockers,
        "dockerfile_base_images": build_safety_policy.get("base_images") or [],
        "package_installers_detected": build_safety_policy.get("package_installers_detected") or [],
        "build_safety_policy": build_safety_policy,
        "validator": "file_manifest_contract",
        "repair_policy": "prefer_manifest_file_index_then_workspace_scan",
        "abort_policy": "build_required_before_promotion",
    }
    if (
        _string_or_none(runtime_plan.get("topology")) == _string_or_none((lead_topology_hint or {}).get("topology"))
        and _string_or_none((lead_topology_hint or {}).get("source"))
        and runtime_plan.get("topology") == "single_service"
        and not runtime_recipe.get("db")
        and not runtime_recipe.get("sidecars")
    ):
        runtime_plan["topology_source"] = _string_or_none((lead_topology_hint or {}).get("source"))
    oracle_contract = {
        "success_signature": _string_or_none(exploit_oracle.get("success_signature")),
        "flag_token": _string_or_none(exploit_oracle.get("flag_token")),
        "output_mode": _string_or_none(exploit_oracle.get("output_mode"))
        or _string_or_none((lead_oracle_hint or {}).get("output_mode"))
        or "auto",
        "negative_control_present": bool(
            exploit_oracle.get("negative_control_present") is True
            or ((lead_oracle_hint or {}).get("negative_control_present") is True)
        ),
        "metamorphic_present": bool(
            exploit_oracle.get("metamorphic_present") is True
            or ((lead_oracle_hint or {}).get("metamorphic_present") is True)
        ),
        "source": _string_or_none(exploit_oracle.get("source"))
        or _string_or_none((lead_oracle_hint or {}).get("source"))
        or "resolved_contract",
        "mode": _string_or_none((lead_oracle_hint or {}).get("mode")) or "contract_or_auto",
        "confidence": _string_or_none((lead_oracle_hint or {}).get("confidence")) or "unknown",
        "oracle_hypotheses": oracle_hypotheses,
        "validator": "exploit_oracle_contract",
        "repair_policy": "reuse_existing_oracle_contract",
        "abort_policy": "verification_required_before_promotion",
    }
    return {
        "schema_version": "staged_synthesis@0.1",
        "stage_order": [
            "candidate_resolution",
            "design_brief",
            "runtime_plan",
            "executor_plan",
            "oracle_contract",
            "file_manifest",
        ],
        "candidate_resolution": candidate_resolution,
        "design_brief": design_brief,
        "runtime_plan": runtime_plan,
        "executor_plan": executor_plan_stage,
        "oracle_contract": oracle_contract,
        "file_manifest": file_manifest,
    }


def _build_selection_branch_trace(
    *,
    request_ir: Dict[str, Any],
    staged_synthesis: Dict[str, Any],
    provenance: Dict[str, Any],
) -> Dict[str, Any]:
    request_ir = request_ir if isinstance(request_ir, dict) else {}
    staged_synthesis = staged_synthesis if isinstance(staged_synthesis, dict) else {}
    provenance = provenance if isinstance(provenance, dict) else {}
    if not staged_synthesis:
        return {}

    selection_decision = request_ir.get("selection_decision") if isinstance(request_ir.get("selection_decision"), dict) else {}
    family_selection = selection_decision.get("family") if isinstance(selection_decision.get("family"), dict) else {}
    stack_selection = selection_decision.get("stack") if isinstance(selection_decision.get("stack"), dict) else {}
    scenario_selection = selection_decision.get("scenario") if isinstance(selection_decision.get("scenario"), dict) else {}
    scenario_candidates = (
        deepcopy(request_ir.get("scenario_candidates"))
        if isinstance(request_ir.get("scenario_candidates"), list)
        else []
    )

    candidate_resolution = (
        staged_synthesis.get("candidate_resolution")
        if isinstance(staged_synthesis.get("candidate_resolution"), dict)
        else {}
    )
    design_brief = (
        staged_synthesis.get("design_brief")
        if isinstance(staged_synthesis.get("design_brief"), dict)
        else {}
    )
    runtime_plan = (
        staged_synthesis.get("runtime_plan")
        if isinstance(staged_synthesis.get("runtime_plan"), dict)
        else {}
    )
    executor_plan = (
        staged_synthesis.get("executor_plan")
        if isinstance(staged_synthesis.get("executor_plan"), dict)
        else {}
    )
    oracle_contract = (
        staged_synthesis.get("oracle_contract")
        if isinstance(staged_synthesis.get("oracle_contract"), dict)
        else {}
    )
    file_manifest = (
        staged_synthesis.get("file_manifest")
        if isinstance(staged_synthesis.get("file_manifest"), dict)
        else {}
    )

    selected_family = _string_or_none(family_selection.get("selected_family"))
    selected_stack_id = _string_or_none(stack_selection.get("selected_stack_id"))
    selected_scenario_id = _string_or_none(scenario_selection.get("selected_scenario_id"))
    selected_topology = (
        _string_or_none(scenario_selection.get("selected_topology"))
        or _string_or_none(scenario_selection.get("topology"))
    )
    selected_oracle_mode = (
        _string_or_none(scenario_selection.get("selected_oracle_mode"))
        or _string_or_none(scenario_selection.get("top_oracle_mode"))
    )

    family_materialized = (
        _string_or_none(candidate_resolution.get("selected_family"))
        or _string_or_none(design_brief.get("working_family"))
    )
    stack_materialized = (
        _string_or_none(candidate_resolution.get("selected_stack_id"))
        or _string_or_none(runtime_plan.get("stack_id"))
    )
    scenario_materialized = (
        _string_or_none(candidate_resolution.get("selected_scenario_id"))
        or _string_or_none(design_brief.get("selected_scenario_id"))
    )
    topology_materialized = (
        _string_or_none(executor_plan.get("topology"))
        or _string_or_none(runtime_plan.get("topology"))
        or _string_or_none(candidate_resolution.get("selected_topology"))
    )
    oracle_mode_materialized = (
        _string_or_none(design_brief.get("selected_oracle_mode"))
        or _string_or_none(candidate_resolution.get("selected_oracle_mode"))
        or _string_or_none(oracle_contract.get("mode"))
    )

    rejected_scenario_ids = [
        scenario_id
        for scenario_id in (
            _string_or_none(entry.get("scenario_id")) for entry in scenario_candidates if isinstance(entry, dict)
        )
        if scenario_id and scenario_id != selected_scenario_id
    ]

    branch_chain = [
        {
            "branch": "family",
            "selected_value": selected_family,
            "materialized_value": family_materialized,
            "selected_source": _string_or_none(family_selection.get("source")),
            "materialized_field": "staged_synthesis.candidate_resolution.selected_family",
            "aligned": bool(selected_family and family_materialized and selected_family == family_materialized),
        },
        {
            "branch": "stack",
            "selected_value": selected_stack_id,
            "materialized_value": stack_materialized,
            "selected_source": _string_or_none(stack_selection.get("source")) or _string_or_none(stack_selection.get("basis")),
            "materialized_field": "staged_synthesis.candidate_resolution.selected_stack_id",
            "aligned": bool(selected_stack_id and stack_materialized and selected_stack_id == stack_materialized),
        },
        {
            "branch": "scenario",
            "selected_value": selected_scenario_id,
            "materialized_value": scenario_materialized,
            "selected_source": _string_or_none(scenario_selection.get("selected_by")) or _string_or_none(scenario_selection.get("source")),
            "materialized_field": "staged_synthesis.candidate_resolution.selected_scenario_id",
            "aligned": bool(selected_scenario_id and scenario_materialized and selected_scenario_id == scenario_materialized),
        },
        {
            "branch": "topology",
            "selected_value": selected_topology,
            "materialized_value": topology_materialized,
            "selected_source": _string_or_none(scenario_selection.get("selected_by")) or _string_or_none(scenario_selection.get("source")),
            "materialized_field": "staged_synthesis.executor_plan.topology",
            "aligned": bool(selected_topology and topology_materialized and selected_topology == topology_materialized),
        },
        {
            "branch": "oracle_mode",
            "selected_value": selected_oracle_mode,
            "materialized_value": oracle_mode_materialized,
            "selected_source": _string_or_none(scenario_selection.get("selected_oracle_source")) or _string_or_none(scenario_selection.get("top_oracle_source")),
            "materialized_field": "staged_synthesis.oracle_contract.mode",
            "aligned": bool(
                selected_oracle_mode and oracle_mode_materialized and selected_oracle_mode == oracle_mode_materialized
            ),
        },
    ]

    branch_alignment = {
        str(entry.get("branch") or ""): bool(entry.get("aligned"))
        for entry in branch_chain
        if str(entry.get("branch") or "").strip()
    }

    return {
        "schema_version": "selection_branch_trace@0.1",
        "controller_ready": selection_decision.get("ready_for_materialization") is True,
        "open_world_evidence_ready": selection_decision.get("open_world_evidence_ready") is True,
        "branch_aligned": all(branch_alignment.values()) if branch_alignment else False,
        "generation_origin": _string_or_none(provenance.get("generation_origin")),
        "materializer": _string_or_none(provenance.get("materializer")),
        "candidate_context": {
            "scenario_candidate_count": len([entry for entry in scenario_candidates if isinstance(entry, dict)]),
            "selected_candidate_present": scenario_selection.get("selected_candidate_present") is True,
            "selection_state": _string_or_none(scenario_selection.get("selection_state")),
            "selected_by": _string_or_none(scenario_selection.get("selected_by")),
            "unresolved_reasons": deepcopy(scenario_selection.get("unresolved_reasons"))
            if isinstance(scenario_selection.get("unresolved_reasons"), list)
            else [],
            "rejected_scenario_ids_sample": rejected_scenario_ids[:3],
            "rejected_candidate_count": len(rejected_scenario_ids),
        },
        "selected_branch": {
            "family": {
                "selected": family_selection.get("selected") is True,
                "selected_value": selected_family,
                "materialized_value": family_materialized,
                "source": _string_or_none(family_selection.get("source")),
                "aligned": branch_alignment.get("family") is True,
            },
            "stack": {
                "selected": stack_selection.get("selected") is True,
                "selected_value": selected_stack_id,
                "materialized_value": stack_materialized,
                "source": _string_or_none(stack_selection.get("source")) or _string_or_none(stack_selection.get("basis")),
                "aligned": branch_alignment.get("stack") is True,
            },
            "scenario": {
                "selected": scenario_selection.get("selected") is True,
                "selected_value": selected_scenario_id,
                "materialized_value": scenario_materialized,
                "source": _string_or_none(scenario_selection.get("selected_by")) or _string_or_none(scenario_selection.get("source")),
                "aligned": branch_alignment.get("scenario") is True,
            },
            "topology": {
                "selected_value": selected_topology,
                "materialized_value": topology_materialized,
                "source": _string_or_none(scenario_selection.get("selected_by")) or _string_or_none(scenario_selection.get("source")),
                "aligned": branch_alignment.get("topology") is True,
            },
            "oracle_mode": {
                "selected_value": selected_oracle_mode,
                "materialized_value": oracle_mode_materialized,
                "source": _string_or_none(scenario_selection.get("selected_oracle_source")) or _string_or_none(scenario_selection.get("top_oracle_source")),
                "aligned": branch_alignment.get("oracle_mode") is True,
            },
        },
        "materialization_bundle": {
            "runtime_topology": _string_or_none(runtime_plan.get("topology")),
            "runtime_topology_source": _string_or_none(runtime_plan.get("topology_source")),
            "executor_topology": _string_or_none(executor_plan.get("topology")),
            "service_entry_path": _string_or_none(file_manifest.get("service_entry_path")),
            "poc_entry_path": _string_or_none(file_manifest.get("poc_entry_path")),
            "dockerfile_path": _string_or_none(file_manifest.get("dockerfile_path")),
            "build_context_root": _string_or_none(file_manifest.get("build_context_root")) or ".",
            "dependency_manifest_paths": deepcopy(file_manifest.get("dependency_manifest_paths"))
            if isinstance(file_manifest.get("dependency_manifest_paths"), list)
            else [],
            "seed_asset_paths": deepcopy(file_manifest.get("seed_asset_paths"))
            if isinstance(file_manifest.get("seed_asset_paths"), list)
            else [],
            "required_roles": deepcopy(design_brief.get("required_roles"))
            if isinstance(design_brief.get("required_roles"), list)
            else [],
        },
        "branch_chain": branch_chain,
    }


def _runtime_sidecars(executor: Dict[str, Any]) -> list[Dict[str, Any]]:
    raw = executor.get("sidecars") if isinstance(executor, dict) else None
    if not isinstance(raw, list):
        return []
    sidecars: list[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        entry: Dict[str, Any] = {}
        for key in ("name", "type", "image"):
            value = _string_or_none(item.get(key))
            if value:
                entry[key] = value
        aliases = item.get("aliases")
        if isinstance(aliases, list):
            normalized_aliases = [
                str(alias).strip()
                for alias in aliases
                if isinstance(alias, str) and str(alias).strip()
            ]
            if normalized_aliases:
                entry["aliases"] = normalized_aliases
        env = item.get("env")
        if isinstance(env, dict):
            normalized_env = {
                str(key).strip(): str(value)
                for key, value in env.items()
                if isinstance(key, str) and str(key).strip() and value not in (None, "")
            }
            if normalized_env:
                entry["env"] = normalized_env
        ready_probe = item.get("ready_probe")
        if isinstance(ready_probe, dict) and ready_probe:
            entry["ready_probe"] = deepcopy(ready_probe)
        network_mode = _string_or_none(item.get("network_mode"))
        if network_mode:
            entry["network_mode"] = network_mode
        if entry:
            sidecars.append(entry)
    return sidecars


def _manifest_target_runtime_hints(manifest: Dict[str, Any]) -> tuple[str | None, list[str], str | None]:
    metadata = manifest.get("metadata") if isinstance(manifest.get("metadata"), dict) else {}
    if not isinstance(metadata, dict):
        return None, [], None
    target_db = _string_or_none(metadata.get("target_db"))
    target_db = target_db.lower() if isinstance(target_db, str) and target_db.strip() else None
    target_sidecars_raw = metadata.get("target_sidecars") if isinstance(metadata.get("target_sidecars"), list) else []
    target_sidecars = [
        str(item).strip().lower()
        for item in target_sidecars_raw
        if isinstance(item, str) and str(item).strip()
    ]
    target_topology = _string_or_none(metadata.get("target_topology"))
    target_topology = target_topology.lower() if isinstance(target_topology, str) and target_topology.strip() else None
    return target_db, target_sidecars, target_topology


def _synthesized_runtime_sidecars(
    *,
    target_db: str | None,
    target_sidecars: list[str],
    service_env: Dict[str, str],
) -> list[Dict[str, Any]]:
    hints = [
        str(item).strip().lower()
        for item in target_sidecars
        if isinstance(item, str) and str(item).strip()
    ]
    if target_db and target_db not in hints:
        hints.append(target_db)
    if not hints:
        return []
    db_host = str(service_env.get("DB_HOST") or "").strip() or "db-internal"
    db_name = str(service_env.get("DB_NAME") or "").strip() or "sqliapp"
    db_user = str(service_env.get("DB_USER") or "").strip() or "sqli"
    db_password = str(service_env.get("DB_PASSWORD") or "").strip() or "sqli_pw"
    for hint in hints:
        if hint in {"mysql", "mariadb"}:
            image = "mysql:8.0" if hint == "mysql" else "mariadb:11"
            return [
                {
                    "name": f"{hint}-main",
                    "type": hint,
                    "image": image,
                    "aliases": [db_host],
                    "env": {
                        "MYSQL_ROOT_PASSWORD": "sqli_root_pw",
                        "MYSQL_DATABASE": db_name,
                        "MYSQL_USER": db_user,
                        "MYSQL_PASSWORD": db_password,
                    },
                    "ready_probe": {"type": "mysql", "retries": 10},
                }
            ]
        if hint in {"postgres", "postgresql"}:
            return [
                {
                    "name": "postgres-main",
                    "type": "postgres",
                    "image": "postgres:16",
                    "aliases": [db_host],
                    "env": {
                        "POSTGRES_DB": db_name,
                        "POSTGRES_USER": db_user,
                        "POSTGRES_PASSWORD": db_password,
                    },
                    "ready_probe": {"type": "postgres", "retries": 10},
                }
            ]
    return []


def _synthesized_runtime_service_env(
    *,
    service_env: Dict[str, str],
    service_port: int,
    sidecars: list[Dict[str, Any]],
    target_db: str | None,
    target_sidecars: list[str],
) -> tuple[Dict[str, str], str | None]:
    env = {
        str(key): str(value)
        for key, value in (service_env or {}).items()
        if isinstance(key, str) and key.strip() and value not in (None, "")
    }
    sidecar_type = ""
    for entry in sidecars:
        if not isinstance(entry, dict):
            continue
        candidate = str(entry.get("type") or entry.get("name") or "").strip().lower()
        if candidate in {"mysql", "mariadb", "postgres", "postgresql"}:
            sidecar_type = candidate
            break
    if not sidecar_type:
        hints = [
            str(item).strip().lower()
            for item in target_sidecars
            if isinstance(item, str) and str(item).strip()
        ]
        if target_db:
            hints.append(str(target_db).strip().lower())
        for candidate in hints:
            if candidate in {"mysql", "mariadb", "postgres", "postgresql"}:
                sidecar_type = candidate
                break
    if not sidecar_type:
        return env, None

    primary_sidecar = next((entry for entry in sidecars if isinstance(entry, dict)), {})
    aliases = primary_sidecar.get("aliases") if isinstance(primary_sidecar.get("aliases"), list) else []
    host = env.get("DB_HOST") or (
        str(aliases[0]).strip() if aliases and isinstance(aliases[0], str) and str(aliases[0]).strip() else ""
    ) or str(primary_sidecar.get("name") or "").strip() or "db-internal"
    primary_env = primary_sidecar.get("env") if isinstance(primary_sidecar.get("env"), dict) else {}
    if sidecar_type in {"mysql", "mariadb"}:
        defaults = {
            "APP_PORT": str(service_port),
            "DB_HOST": host,
            "DB_PORT": "3306",
            "DB_USER": env.get("DB_USER") or str(primary_env.get("MYSQL_USER") or "").strip() or "sqli",
            "DB_PASSWORD": env.get("DB_PASSWORD") or str(primary_env.get("MYSQL_PASSWORD") or "").strip() or "sqli_pw",
            "DB_NAME": env.get("DB_NAME") or str(primary_env.get("MYSQL_DATABASE") or "").strip() or "sqliapp",
        }
    else:
        defaults = {
            "APP_PORT": str(service_port),
            "DB_HOST": host,
            "DB_PORT": "5432",
            "DB_USER": env.get("DB_USER") or str(primary_env.get("POSTGRES_USER") or "").strip() or "sqli",
            "DB_PASSWORD": env.get("DB_PASSWORD") or str(primary_env.get("POSTGRES_PASSWORD") or "").strip() or "sqli_pw",
            "DB_NAME": env.get("DB_NAME") or str(primary_env.get("POSTGRES_DB") or "").strip() or "sqliapp",
        }
    changed = False
    for key, value in defaults.items():
        if not str(env.get(key) or "").strip() and str(value or "").strip():
            env[key] = str(value)
            changed = True
    return env, ("runtime_hint_sidecar_defaults" if changed else None)


def _runtime_seed_files(manifest: Dict[str, Any]) -> list[str]:
    files = manifest.get("files") if isinstance(manifest, dict) else []
    if not isinstance(files, list):
        return []
    seeds: list[str] = []
    for entry in files:
        if not isinstance(entry, dict):
            continue
        path = _string_or_none(entry.get("path"))
        if not path:
            continue
        role = str(entry.get("role") or "").strip().lower()
        name = Path(path).name.lower()
        if role in {"schema", "seed_data"} or name in {"schema.sql", "seed_data.sql"}:
            seeds.append(path)
    return seeds


def _runtime_seed_strategy(
    *,
    seed_files: list[str],
    db: Optional[str],
    requires_external_db: bool,
    topology: str,
) -> tuple[str | None, str | None]:
    normalized_seed_files = [
        str(item).strip()
        for item in seed_files
        if isinstance(item, str) and str(item).strip()
    ]
    if not normalized_seed_files:
        return None, None
    normalized_db = str(db or "").strip().lower()
    normalized_topology = str(topology or "").strip().lower()
    if normalized_db == "sqlite":
        return "sqlite_service_init", "runtime_recipe.seed_files+db"
    if requires_external_db or normalized_topology == "service_plus_sidecar" or normalized_db in {"mysql", "mariadb", "postgres", "postgresql"}:
        return "sidecar_sql_apply", "runtime_recipe.seed_files+topology"
    return None, None


def _runtime_volume_contract(
    *,
    seed_files: list[str],
    seed_strategy: Optional[str],
    sidecars: list[Dict[str, Any]],
) -> tuple[list[Dict[str, str]], str | None]:
    strategy = str(seed_strategy or "").strip().lower()
    if strategy != "sidecar_sql_apply":
        return [], None
    sql_seed_files = [
        str(item).strip()
        for item in seed_files
        if isinstance(item, str) and str(item).strip().lower().endswith(".sql")
    ]
    if not sql_seed_files:
        return [], None
    volume_contract: list[Dict[str, str]] = []
    for sidecar in sidecars:
        if not isinstance(sidecar, dict):
            continue
        name = _string_or_none(sidecar.get("name"))
        sidecar_type = _string_or_none(sidecar.get("type")) or _string_or_none(sidecar.get("image")) or ""
        normalized_type = str(sidecar_type).strip().lower().split("/")[-1].split(":")[0]
        if not name or normalized_type not in {"mysql", "mariadb", "postgres", "postgresql"}:
            continue
        volume_contract.append(
            {
                "scope": f"sidecar:{name.strip().lower()}",
                "source": "workspace",
                "target": "/seed-input",
                "mode": "ro",
            }
        )
    if not volume_contract:
        return [], None
    return volume_contract, "runtime_recipe.seed_files+seed_strategy"


def _runtime_network_contract(
    *,
    service_env: Dict[str, str],
    sidecars: list[Dict[str, Any]],
) -> tuple[list[Dict[str, str]], str | None]:
    if not sidecars:
        return [], None
    network_contract: list[Dict[str, str]] = []
    db_host = str(service_env.get("DB_HOST") or "").strip()
    if db_host:
        network_contract.append(
            {
                "scope": "service",
                "name": "DB_HOST",
                "alias": db_host,
            }
        )
    for sidecar in sidecars:
        if not isinstance(sidecar, dict):
            continue
        sidecar_name = _string_or_none(sidecar.get("name"))
        aliases = sidecar.get("aliases") if isinstance(sidecar.get("aliases"), list) else []
        if not sidecar_name:
            continue
        for alias in aliases:
            if not isinstance(alias, str) or not alias.strip():
                continue
            network_contract.append(
                {
                    "scope": f"sidecar:{sidecar_name.strip().lower()}",
                    "alias": alias.strip(),
                }
            )
    if not network_contract:
        return [], None
    return network_contract, "runtime_recipe.service_env+sidecars"


def _runtime_health_path(manifest: Dict[str, Any]) -> Optional[str]:
    files = manifest.get("files") if isinstance(manifest, dict) else []
    if not isinstance(files, list):
        return None
    for entry in files:
        if not isinstance(entry, dict):
            continue
        if not role_matches(entry.get("role"), "service_main"):
            continue
        content = entry.get("content")
        if not isinstance(content, str) or not content:
            continue
        if '"/health"' in content or "'/health'" in content:
            return "/health"
    return None


def _parse_port_from_run_command(command: str) -> Optional[int]:
    text = (command or "").strip()
    if not text:
        return None
    pattern = re.compile(r"(?:-p|--publish)\\s*(\\d+)\\s*:\\s*(\\d+)")
    match = pattern.search(text)
    if not match:
        return None
    return _int_or_none(match.group(2))


def _port_from_dockerfile(workspace: Optional[Path]) -> Optional[int]:
    if workspace is None:
        return None
    dockerfile = workspace / "Dockerfile"
    if not dockerfile.exists():
        return None
    try:
        lines = dockerfile.read_text(encoding="utf-8").splitlines()
    except Exception:
        return None
    for line in lines:
        stripped = line.strip()
        if not stripped.upper().startswith("EXPOSE"):
            continue
        parts = stripped.split()
        for token in parts[1:]:
            raw = token.split("/")[0].strip()
            value = _int_or_none(raw)
            if value:
                return value
    return None


def _int_or_none(value: Any) -> Optional[int]:
    try:
        ivalue = int(value)
    except Exception:
        return None
    return ivalue if ivalue > 0 else None


def _resolve_rule_sources(vuln_id: str) -> Dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    normalized = _normalized_rule_id(vuln_id)
    static_path = repo_root / "docs" / "evals" / "rules" / f"{normalized}.yaml"
    runtime_dirs = _runtime_rule_dirs()
    runtime_paths = [path / f"{normalized}.yaml" for path in runtime_dirs]
    existing_runtime = [str(path) for path in runtime_paths if path.exists()]
    source = "none"
    if existing_runtime:
        source = "runtime"
    elif static_path.exists():
        source = "static"
    return {
        "normalized_id": normalized,
        "selected_source": source,
        "static_rule_path": str(static_path) if static_path.exists() else None,
        "runtime_rule_dirs": [str(path) for path in runtime_dirs],
        "runtime_rule_paths": existing_runtime,
    }


def _normalized_rule_id(vuln_id: str) -> str:
    token = (vuln_id or "").strip().lower()
    if not token:
        return "cwe-unknown"
    if token.startswith("name_"):
        token = token.replace("_", "-", 1)
    if token.startswith("name-"):
        return token
    if token.startswith("cwe_"):
        token = token.replace("_", "-", 1)
    if token.startswith("cwe-"):
        return token
    if token.startswith("cwe"):
        token = token.replace("cwe", "cwe-", 1)
        return token
    return f"cwe-{token}"


def _runtime_rule_dirs() -> list[Path]:
    env = os.environ.get("VULD_RUNTIME_RULE_DIRS") or ""
    dirs: list[Path] = []
    for raw in env.split(os.pathsep):
        raw = raw.strip()
        if not raw:
            continue
        dirs.append(Path(raw))
    return dirs


__all__ = [
    "can_resolve_without_remote_research_for_requirement",
    "can_resolve_without_remote_research",
    "compiler_path_enabled",
    "compiler_support_summary",
    "DEFAULT_APP_PORT",
    "executor_feasibility_summary",
    "build_generator_contract",
    "lower_bound_summary",
    "load_generator_contract",
    "load_semantic_profile",
    "requires_semantic_support",
    "write_generator_contract",
]
