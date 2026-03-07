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
from common.rules import load_rule, load_rulespec
from common.vuln_semantics import (
    baseline_semantic_signature,
    family_canonical_tags,
    normalize_vuln_id,
    semantic_term_aliases,
)

DEFAULT_APP_PORT = 5000
RESOLVED_CONTRACT_SCHEMA_VERSION = "resolved_contract@1.0"
RESOLVED_CONTRACT_FILENAME = "resolved_contract.json"
LEGACY_CONTRACT_FILENAME = "generator_contract.json"


def _resolved_contract_path(metadata_dir: Path) -> Path:
    return metadata_dir / RESOLVED_CONTRACT_FILENAME


def _legacy_contract_path(metadata_dir: Path) -> Path:
    return metadata_dir / LEGACY_CONTRACT_FILENAME


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


def write_generator_contract(metadata_dir: Path, payload: Dict[str, Any]) -> Path:
    resolved_path = _resolved_contract_path(metadata_dir)
    legacy_path = _legacy_contract_path(metadata_dir)
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    resolved_path.write_text(text, encoding="utf-8")
    legacy_path.write_text(text, encoding="utf-8")
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
    if poc_cmd:
        payload["poc_cmd"] = poc_cmd
    if semantic_contract.get("semantic_signature"):
        payload["semantic_signature"] = semantic_contract["semantic_signature"]
    if semantic_contract.get("semantic_signature_source"):
        payload["semantic_signature_source"] = semantic_contract["semantic_signature_source"]
    return payload


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
    report_signature = contract.get("semantic_signature") if isinstance(contract, dict) else None
    guard_signature = guard_spec.get("semantic_signature") if isinstance(guard_spec, dict) else None
    baseline_signature = _normalize_semantic_buckets(baseline_semantic_signature(vuln_id))
    has_baseline = any(baseline_signature.get(bucket) for bucket in baseline_signature)
    resolved_signature = _normalize_semantic_buckets(contract.get("semantic_signature") if isinstance(contract, dict) else {})
    if isinstance(guard_signature, dict) and guard_signature and "semantic_signature" not in contract:
        contract["semantic_signature"] = guard_signature
        contract.setdefault("semantic_signature_source", ["guard_spec"])
        resolved_signature = _normalize_semantic_buckets(guard_signature)
    elif has_baseline and not any(resolved_signature.get(bucket) for bucket in resolved_signature):
        contract["semantic_signature"] = baseline_signature
        contract["semantic_signature_source"] = ["baseline"]
        resolved_signature = baseline_signature
    guard_confidence = guard_spec.get("confidence") if isinstance(guard_spec, dict) else None
    if isinstance(guard_confidence, str) and guard_confidence.strip():
        contract["guard_confidence"] = guard_confidence.strip().lower()
    contradictions = _semantic_contract_contradictions(
        vuln_id,
        signature=resolved_signature,
        report_signature=report_signature if isinstance(report_signature, dict) else {},
        guard_signature=guard_signature if isinstance(guard_signature, dict) else {},
    )
    contract["authority"] = "resolved_contract.semantic_contract"
    contract["contradictions"] = contradictions
    contract["status"] = "contradicted" if contradictions else "aligned"
    return contract


def _semantic_contract_contradictions(
    vuln_id: str,
    *,
    signature: Any,
    report_signature: Dict[str, Any],
    guard_signature: Dict[str, Any],
) -> list[str]:
    resolved = _normalize_semantic_buckets(signature)
    report_norm = _normalize_semantic_buckets(report_signature)
    guard_norm = _normalize_semantic_buckets(guard_signature)
    baseline = _normalize_semantic_buckets(baseline_semantic_signature(vuln_id))
    contradictions: list[str] = []

    for bucket in ("input_vector", "sink", "exploit_precondition"):
        expected = baseline.get(bucket) or []
        observed = resolved.get(bucket) or []
        if expected and not observed:
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
    for candidate in (
        "cwe-89",
        "cwe-352",
        "cwe-22",
        "cwe-918",
        "cwe-78",
        "cwe-94",
        "cwe-79",
        "cwe-502",
    ):
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
    "DEFAULT_APP_PORT",
    "build_generator_contract",
    "load_generator_contract",
    "write_generator_contract",
]
