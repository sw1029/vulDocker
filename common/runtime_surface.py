"""Helpers for deriving runtime surface requirements from asset-backed specs."""
from __future__ import annotations

from typing import Any, Dict, Optional

from common.vuln_catalog import resolve_runtime_surface_spec


def _requirement_dict(requirement: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return requirement if isinstance(requirement, dict) else {}


def _runtime_dict(requirement: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    req = _requirement_dict(requirement)
    runtime = req.get("runtime")
    return runtime if isinstance(runtime, dict) else {}


def _executor_dict(requirement: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    req = _requirement_dict(requirement)
    executor = req.get("executor")
    return executor if isinstance(executor, dict) else {}


def _sidecars(requirement: Optional[Dict[str, Any]]) -> list[Dict[str, Any]]:
    executor = _executor_dict(requirement)
    raw = executor.get("sidecars")
    if not isinstance(raw, list):
        return []
    return [entry for entry in raw if isinstance(entry, dict)]


def _matching_sidecar(spec: Dict[str, Any], requirement: Optional[Dict[str, Any]]) -> Dict[str, Any] | None:
    target_type = str(spec.get("sidecar_type") or "").strip().lower()
    target_name = str(spec.get("sidecar_name") or "").strip().lower()
    for entry in _sidecars(requirement):
        sidecar_type = str(entry.get("type") or "").strip().lower()
        name = str(entry.get("name") or "").strip().lower()
        if target_type and sidecar_type == target_type:
            return entry
        if target_name and name == target_name:
            return entry
    if target_type or target_name:
        return None
    entries = _sidecars(requirement)
    return entries[0] if entries else None


def _resolve_source_value(
    source: str,
    *,
    spec: Dict[str, Any],
    requirement: Optional[Dict[str, Any]],
    service_port: Optional[int],
) -> str | None:
    token = str(source or "").strip()
    if not token:
        return None
    if token == "service_port":
        if service_port:
            return str(service_port)
        return None
    if token.startswith("runtime."):
        key = token.split(".", 1)[1]
        value = _runtime_dict(requirement).get(key)
        if value in (None, ""):
            return None
        return str(value)
    if token.startswith("sidecar."):
        sidecar = _matching_sidecar(spec, requirement)
        if not isinstance(sidecar, dict):
            return None
        tail = token.split(".", 1)[1]
        if tail == "name":
            value = sidecar.get("name")
            return str(value) if value not in (None, "") else None
        if tail == "alias_or_name":
            aliases = sidecar.get("aliases")
            if isinstance(aliases, list):
                for item in aliases:
                    if item not in (None, ""):
                        return str(item)
            value = sidecar.get("name")
            return str(value) if value not in (None, "") else None
        if tail.startswith("env."):
            key = tail.split(".", 1)[1]
            env = sidecar.get("env")
            if not isinstance(env, dict):
                return None
            value = env.get(key)
            if value in (None, ""):
                return None
            return str(value)
    return None


def derive_service_env(
    *,
    compiler_strategy: str,
    requirement: Optional[Dict[str, Any]],
    service_port: Optional[int] = None,
) -> Dict[str, str]:
    spec = resolve_runtime_surface_spec(compiler_strategy, requirement)
    if not isinstance(spec, dict):
        return {}
    service_env = spec.get("service_env")
    if not isinstance(service_env, dict):
        return {}
    env: Dict[str, str] = {}
    for key, raw_rule in service_env.items():
        if not isinstance(key, str):
            continue
        name = key.strip()
        if not name:
            continue
        rule = raw_rule if isinstance(raw_rule, dict) else {}
        value = None
        if "value" in rule and rule.get("value") not in (None, ""):
            value = str(rule.get("value"))
        else:
            raw_sources = rule.get("sources")
            if isinstance(raw_sources, list):
                sources = [str(item).strip() for item in raw_sources if str(item).strip()]
            else:
                source = str(rule.get("source") or "").strip()
                sources = [source] if source else []
            for source in sources:
                value = _resolve_source_value(
                    source,
                    spec=rule,
                    requirement=requirement,
                    service_port=service_port,
                )
                if value not in (None, ""):
                    break
        if value in (None, ""):
            default = rule.get("default")
            if default not in (None, ""):
                value = str(default)
        if value not in (None, ""):
            env[name] = str(value)
    return env


__all__ = ["derive_service_env"]
