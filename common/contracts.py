"""Shared contract helpers for generator/executor/verifier stages.

This module centralizes how we resolve the *run contract* that downstream stages
need (service_entry, poc_entry, service_port, base_url, poc.cmd). The generator
should write the resolved contract into `metadata/<SID>/[bundles/<slug>/]generator_contract.json`
so that executor/verifier/reviewer can consume a single source of truth.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_APP_PORT = 5000


def load_generator_contract(metadata_dir: Path) -> Optional[Dict[str, Any]]:
    path = metadata_dir / "generator_contract.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def write_generator_contract(metadata_dir: Path, payload: Dict[str, Any]) -> Path:
    path = metadata_dir / "generator_contract.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def build_generator_contract(
    *,
    sid: str,
    vuln_id: str,
    metadata_dir: Path,
    workspace_dir: Optional[Path] = None,
    generator_mode: str = "",
    bundle_slug: str = "",
) -> Dict[str, Any]:
    """Build a normalized generator contract for a single bundle.

    Priority (when multiple sources exist):
    - generator_manifest.json (synthesis path / most specific for this run)
    - generator_template.json (template path)
    - Dockerfile EXPOSE
    - DEFAULT_APP_PORT
    """

    template = _load_json(metadata_dir / "generator_template.json") or {}
    manifest_payload = _load_json(metadata_dir / "generator_manifest.json") or {}
    manifest = _unwrap_manifest(manifest_payload)
    has_manifest = isinstance(manifest.get("files"), list) and bool(manifest.get("files"))

    sources: Dict[str, str] = {}

    service_entry = _manifest_role_path(manifest, "service_main")
    if service_entry:
        sources["service_entry"] = "generator_manifest.manifest.files(role=service_main)"
    else:
        service_entry = _string_or_none(template.get("service_entry"))
        if service_entry:
            sources["service_entry"] = "generator_template.service_entry"
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

    payload: Dict[str, Any] = {
        "sid": sid,
        "slug": bundle_slug,
        "vuln_id": vuln_id,
        "generator_mode": generator_mode,
        "resolved": {
            "service_entry": service_entry,
            "poc_entry": poc_entry,
            "service_port": service_port,
            "base_url": base_url,
            "poc_cmd": poc_cmd,
        },
        "sources": sources,
    }

    poc_success_signature = _string_or_none(_dig(manifest, "poc", "success_signature"))
    if poc_success_signature:
        payload["poc_success_signature"] = poc_success_signature
        sources.setdefault("poc_success_signature", "generator_manifest.manifest.poc.success_signature")
    poc_flag_token = _string_or_none(_dig(manifest, "poc", "flag_token"))
    if poc_flag_token:
        payload["poc_flag_token"] = poc_flag_token
        sources.setdefault("poc_flag_token", "generator_manifest.manifest.poc.flag_token")

    if not has_manifest:
        scenario_type = _string_or_none(template.get("scenario_type"))
        if scenario_type:
            payload["scenario_type"] = scenario_type
            sources.setdefault("scenario_type", "generator_template.scenario_type")
        template_id = _string_or_none(template.get("template_id"))
        if template_id:
            payload["template_id"] = template_id
            sources.setdefault("template_id", "generator_template.template_id")
        pattern_id = _string_or_none(template.get("pattern_id"))
        if pattern_id:
            payload["pattern_id"] = pattern_id
            sources.setdefault("pattern_id", "generator_template.pattern_id")
        flag_token = _string_or_none(template.get("flag_token"))
        if flag_token:
            payload["flag_token"] = flag_token
            sources.setdefault("flag_token", "generator_template.flag_token")

    payload["rule_resolution"] = _resolve_rule_sources(vuln_id)

    # Keep backward-compatible fields at the top-level for convenience.
    payload["service_entry"] = service_entry
    payload["poc_entry"] = poc_entry
    payload["service_port"] = service_port
    payload["base_url"] = base_url
    if poc_cmd:
        payload["poc_cmd"] = poc_cmd
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


def _manifest_role_path(manifest: Dict[str, Any], role: str) -> Optional[str]:
    files = manifest.get("files") or []
    if not isinstance(files, list):
        return None
    role_norm = (role or "").strip().lower()
    for entry in files:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("role") or "").strip().lower() != role_norm:
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
