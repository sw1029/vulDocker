"""Shared contract helpers for researcher/generator/executor/verifier stages.

This module centralizes how we resolve the *run contract* that downstream stages
need (success/flag markers, service entry, poc entry, service port, base URL,
PoC command). Researcher may write an early seed contract and the generator
later refreshes the canonical payload to
`resolved_contract.json` and mirrors it to `generator_contract.json` for
backward compatibility.
"""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

from common.roles import role_matches
from common.researcher_report import (
    extract_semantic_contract,
    extract_verification_spec,
    normalize_researcher_report_payload,
)
from common.rules import load_rule, load_rulespec, load_static_rule
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

_SEMANTIC_PROFILE_DEFAULTS: Dict[str, Dict[str, str]] = {
    "CWE-89": {
        "family": "sql_injection",
        "support_level": "builtin_supported",
        "compiler_strategy": "sqli_string_concat",
    },
    "CWE-352": {
        "family": "csrf",
        "support_level": "builtin_supported",
        "compiler_strategy": "csrf_missing_token",
    },
    "CWE-22": {
        "family": "path_traversal",
        "support_level": "builtin_supported",
        "compiler_strategy": "path_traversal_file_read",
    },
    "CWE-918": {
        "family": "ssrf",
        "support_level": "builtin_supported",
        "compiler_strategy": "ssrf_loopback_fetch",
    },
    "CWE-78": {
        "family": "command_injection",
        "support_level": "builtin_supported",
        "compiler_strategy": "command_injection_shell",
    },
    "CWE-94": {
        "family": "code_injection",
        "support_level": "builtin_supported",
        "compiler_strategy": "code_injection_eval",
    },
    "CWE-79": {
        "family": "xss",
        "support_level": "builtin_supported",
        "compiler_strategy": "xss_reflected",
    },
    "CWE-502": {
        "family": "deserialization",
        "support_level": "builtin_supported",
        "compiler_strategy": "deserialization_pickle_body",
    },
    "NAME-OPEN-REDIRECT": {
        "family": "open_redirect",
        "support_level": "compiler_supported",
        "compiler_strategy": "open_redirect_reflect",
    },
    "NAME-TEMPLATE-INJECTION": {
        "family": "template_injection",
        "support_level": "compiler_supported",
        "compiler_strategy": "template_injection_render",
    },
    "NAME-LDAP-INJECTION": {
        "family": "ldap_injection",
        "support_level": "unsupported",
        "compiler_strategy": "",
    },
}


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


def compiler_support_summary(vuln_id: str) -> Dict[str, Any]:
    """Return the default compiler support verdict for a vuln family.

    This is the pre-research/pre-generation lower-bound view derived from the
    canonical family mapping plus the currently implemented compiler registry.
    """

    defaults = _semantic_profile_defaults(vuln_id)
    support_level = str(defaults.get("support_level") or "unsupported").strip().lower()
    compiler_strategy = _string_or_none(defaults.get("compiler_strategy")) or ""
    compiler_available = _compiler_strategy_supported(compiler_strategy)
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
    proposal = _normalize_proposed_verification_contract(report)
    semantic_contract = _resolve_semantic_contract(vuln_id, report, guard_spec)

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

    payload: Dict[str, Any] = {
        "schema_version": RESOLVED_CONTRACT_SCHEMA_VERSION,
        "sid": sid,
        "slug": bundle_slug,
        "vuln_id": vuln_id,
        "generator_mode": generator_mode,
        "contract_stage": generator_mode or ("generator" if workspace_dir else "seed"),
        "resolved": {
            "success_signature": success_signature,
            "flag_token": flag_token,
            "service_entry": service_entry,
            "poc_entry": poc_entry,
            "service_port": service_port,
            "base_url": base_url,
            "poc_cmd": poc_cmd,
            "output_mode": output_mode,
        },
        "sources": sources,
    }
    if provenance:
        payload["provenance"] = provenance
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
    payload["compiler_supported"] = bool(semantic_profile.get("compiler_supported"))
    payload["compiler_strategy"] = _string_or_none(semantic_profile.get("compiler_strategy"))
    payload["compiler_reason"] = _string_or_none(semantic_profile.get("compiler_reason"))
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
    compiler_summary = compiler_support_summary(vuln_id)
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
            "semantic_gate_required": requires_semantic_support(vuln_id),
            "semantic_status": _string_or_none(semantic_contract.get("status")) or "unsupported",
            "rule_source": _string_or_none(rule_resolution.get("selected_source")) or "none",
            "service_entry": _string_or_none(resolved.get("service_entry")) or "app.py",
            "service_port": resolved.get("service_port") or DEFAULT_APP_PORT,
        },
        "evidence_relevance": deepcopy(semantic_contract.get("evidence_relevance"))
        if isinstance(semantic_contract.get("evidence_relevance"), dict)
        else {},
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


def _stack_profile(requirement: Dict[str, Any]) -> Dict[str, Any]:
    runtime = requirement.get("runtime") if isinstance(requirement, dict) else {}
    runtime = runtime if isinstance(runtime, dict) else {}
    return {
        "language": _string_or_none(requirement.get("language") if isinstance(requirement, dict) else None) or "python",
        "framework": _string_or_none(requirement.get("framework") if isinstance(requirement, dict) else None) or "flask",
        "base_image": _string_or_none(runtime.get("base_image"))
        or _string_or_none(requirement.get("base_image") if isinstance(requirement, dict) else None)
        or "python:3.11-slim",
        "package_manager": _string_or_none(runtime.get("package_manager"))
        or _string_or_none(requirement.get("package_manager") if isinstance(requirement, dict) else None)
        or "pip",
        "generator_mode": _string_or_none(requirement.get("generator_mode") if isinstance(requirement, dict) else None)
        or "synthesis",
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


def _compiler_strategy_supported(strategy: str) -> bool:
    token = str(strategy or "").strip()
    if not token:
        return False
    try:
        from agents.generator.compiler import supported_compiler_strategies

        return token in supported_compiler_strategies()
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

    llm_stub_used = _bool_or_none(manifest_payload.get("llm_stub_used")) if isinstance(manifest_payload, dict) else None
    if llm_stub_used is None and isinstance(template_summary, dict):
        llm_stub_used = _bool_or_none(template_summary.get("llm_stub_used"))
    if llm_stub_used is not None:
        provenance["llm_stub_used"] = llm_stub_used

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
        "source": "researcher_report.verification_spec",
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
    return normalized if len(normalized) > 2 else None


def _resolve_semantic_contract(vuln_id: str, report: Dict[str, Any], guard_spec: Dict[str, Any]) -> Dict[str, Any]:
    contract = extract_semantic_contract(report)
    is_free_form_name = str(vuln_id or "").strip().upper().startswith("NAME-")
    report_signature = contract.get("semantic_signature") if isinstance(contract, dict) else None
    guard_signature = guard_spec.get("semantic_signature") if isinstance(guard_spec, dict) else None
    baseline_signature = _normalize_semantic_buckets(baseline_semantic_signature(vuln_id))
    fragment_signature, _ = _default_profile_semantic_signature(vuln_id=vuln_id, requirement={"vuln_id": vuln_id})
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
    if contradictions:
        status = "contradicted"
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
    "can_resolve_without_remote_research",
    "compiler_support_summary",
    "DEFAULT_APP_PORT",
    "build_generator_contract",
    "load_generator_contract",
    "load_semantic_profile",
    "requires_semantic_support",
    "write_generator_contract",
]
