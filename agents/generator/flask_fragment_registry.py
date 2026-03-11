"""Registry of python/flask scaffold fragments for compiler-covered families."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from common.vuln_catalog import resolve_compiler_strategy, resolve_vuln_catalog_entry


ASSETS_ROOT = Path(__file__).resolve().parent / "assets"
FRAGMENT_CATALOG_PATH = ASSETS_ROOT / "flask-fragments.json"
FRAGMENT_CODE_CATALOG_PATH = ASSETS_ROOT / "flask-fragment-code.json"
POC_TEMPLATES_ROOT = ASSETS_ROOT / "flask-pocs"


@dataclass(frozen=True)
class FlaskFragmentSpec:
    strategy: str
    family: str
    fragment_id: str
    import_block: str
    route_block: str
    poc_builder: Callable[[int], Dict[str, str]]
    pattern_tags: Tuple[str, ...]
    notes: str
    service_description: str
    poc_description: str
    service_side_tokens: Tuple[str, ...]
    semantic_signature: Dict[str, Tuple[str, ...]]
    requirements_content: str = "Flask==3.0.0\nrequests==2.31.0\n"
    app_setup_block: str = ""
    startup_block: str = ""
    extra_files: Tuple[Dict[str, Any], ...] = ()
    requires_external_db: bool = False


def _fragment_catalog() -> Dict[str, Dict[str, Any]]:
    payload = json.loads(FRAGMENT_CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}
    catalog: Dict[str, Dict[str, Any]] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        catalog[key] = value
    return catalog


def _fragment_kwargs(strategy: str) -> Dict[str, Any]:
    payload = _fragment_catalog().get(strategy) or {}
    semantic_signature_raw = payload.get("semantic_signature") if isinstance(payload.get("semantic_signature"), dict) else {}
    semantic_signature = {
        bucket: tuple(str(item) for item in (semantic_signature_raw.get(bucket) or []) if isinstance(item, str) and item.strip())
        for bucket in ("input_vector", "sink", "exploit_precondition")
    }
    extra_files_raw = payload.get("extra_files") if isinstance(payload.get("extra_files"), list) else []
    extra_files: List[Dict[str, Any]] = []
    for item in extra_files_raw:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip()
        if not path:
            continue
        extra_files.append(
            {
                "path": path,
                "role": str(item.get("role") or "helper").strip() or "helper",
                "description": str(item.get("description") or "").strip(),
                "content": str(item.get("content") or ""),
            }
        )
    return {
        "family": str(payload.get("family") or strategy),
        "fragment_id": str(payload.get("fragment_id") or strategy),
        "pattern_tags": tuple(str(item) for item in (payload.get("pattern_tags") or []) if isinstance(item, str) and item.strip()),
        "notes": str(payload.get("notes") or ""),
        "service_description": str(payload.get("service_description") or ""),
        "poc_description": str(payload.get("poc_description") or ""),
        "service_side_tokens": tuple(
            str(item) for item in (payload.get("service_side_tokens") or []) if isinstance(item, str) and item.strip()
        ),
        "semantic_signature": semantic_signature,
        "requirements_content": str(payload.get("requirements_content") or "Flask==3.0.0\nrequests==2.31.0\n"),
        "extra_files": tuple(extra_files),
        "requires_external_db": bool(payload.get("requires_external_db", False)),
    }


def _fragment_code_catalog() -> Dict[str, Dict[str, Any]]:
    payload = json.loads(FRAGMENT_CODE_CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}
    catalog: Dict[str, Dict[str, Any]] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        catalog[key] = value
    return catalog


def _fragment_code_lines(strategy: str, field: str) -> Tuple[str, ...]:
    payload = _fragment_code_catalog().get(strategy) or {}
    lines = payload.get(field)
    if not isinstance(lines, list):
        return ()
    return tuple(str(item) for item in lines if isinstance(item, str))


def _fragment_code_text(strategy: str, field: str) -> str:
    lines = _fragment_code_lines(strategy, field)
    if not lines:
        return ""
    text = "\n".join(lines)
    if field == "startup_block" and text and not text.endswith("\n"):
        text += "\n"
    return text


def _fragment_success_signature(strategy: str) -> str:
    payload = _fragment_catalog().get(strategy) or {}
    return str(payload.get("success_signature") or "Exploit SUCCESS")


def _fragment_flag_token(strategy: str) -> str:
    payload = _fragment_catalog().get(strategy) or {}
    return str(payload.get("flag_token") or "")


def _poc_asset_payload(strategy: str, port: int) -> Dict[str, str]:
    template_path = POC_TEMPLATES_ROOT / f"{strategy}.py.tmpl"
    text = template_path.read_text(encoding="utf-8")
    success_signature = _fragment_success_signature(strategy)
    flag_token = _fragment_flag_token(strategy)
    poc_content = (
        text.replace("__PORT__", str(port))
        .replace("__SUCCESS_SIGNATURE__", success_signature)
        .replace("__FLAG_TOKEN__", flag_token)
    )
    return {
        "success_signature": success_signature,
        "flag_token": flag_token,
        "poc_content": poc_content,
    }

def _poc_builder(strategy: str) -> Callable[[int], Dict[str, str]]:
    return lambda port, _strategy=strategy: _poc_asset_payload(_strategy, port)


def _build_fragment_registry() -> Dict[str, FlaskFragmentSpec]:
    registry: Dict[str, FlaskFragmentSpec] = {}
    for strategy in sorted(_fragment_catalog()):
        registry[strategy] = FlaskFragmentSpec(
            strategy=strategy,
            import_block=_fragment_code_text(strategy, "import_block"),
            route_block=_fragment_code_text(strategy, "route_block"),
            poc_builder=_poc_builder(strategy),
            app_setup_block=_fragment_code_text(strategy, "app_setup_block"),
            startup_block=_fragment_code_text(strategy, "startup_block"),
            **_fragment_kwargs(strategy),
        )
    return registry


FLASK_FRAGMENT_REGISTRY: Dict[str, FlaskFragmentSpec] = _build_fragment_registry()


def _resolve_exact_fragment_strategy(vuln_id: str) -> str | None:
    entry = resolve_vuln_catalog_entry(vuln_id=vuln_id)
    if not isinstance(entry, dict):
        return None
    strategy = str(entry.get("fragment_strategy") or "").strip()
    return strategy or None


def resolve_fragment_strategy(vuln_id: str, pattern_id: str = "", raw_label: str = "") -> str | None:
    exact = _resolve_exact_fragment_strategy(vuln_id)
    if exact:
        return exact
    entry = resolve_vuln_catalog_entry(pattern_id=pattern_id, raw_label=raw_label)
    if not isinstance(entry, dict):
        return None
    strategy = resolve_compiler_strategy(
        str(entry.get("vuln_id") or ""),
        {"pattern_id": pattern_id} if str(pattern_id or "").strip() else None,
    ) or str(entry.get("fragment_strategy") or "").strip()
    return strategy or None


def resolve_fragment_spec(vuln_id: str, pattern_id: str = "", raw_label: str = "") -> FlaskFragmentSpec | None:
    strategy = resolve_fragment_strategy(vuln_id, pattern_id=pattern_id, raw_label=raw_label)
    if not strategy:
        return None
    return FLASK_FRAGMENT_REGISTRY.get(strategy)


def fragment_semantic_signature(vuln_id: str, pattern_id: str = "", raw_label: str = "") -> Dict[str, List[str]]:
    spec = None
    exact = _resolve_exact_fragment_strategy(vuln_id)
    if exact:
        spec = FLASK_FRAGMENT_REGISTRY.get(exact)
    elif not str(vuln_id or "").strip():
        spec = resolve_fragment_spec(vuln_id, pattern_id=pattern_id, raw_label=raw_label)
    if spec is None:
        return {
            "input_vector": [],
            "sink": [],
            "exploit_precondition": [],
        }
    return {
        bucket: [str(item) for item in (spec.semantic_signature.get(bucket) or ()) if str(item).strip()]
        for bucket in ("input_vector", "sink", "exploit_precondition")
    }


def fragment_guard_generator_assertions(vuln_id: str, pattern_id: str = "", raw_label: str = "") -> List[Dict[str, Any]]:
    spec = None
    exact = _resolve_exact_fragment_strategy(vuln_id)
    if exact:
        spec = FLASK_FRAGMENT_REGISTRY.get(exact)
    elif not str(vuln_id or "").strip():
        spec = resolve_fragment_spec(vuln_id, pattern_id=pattern_id, raw_label=raw_label)
    if spec is None:
        return []
    assertions: List[Dict[str, Any]] = [
        {"op": "role_exists", "role": "service_main"},
        {"op": "role_exists", "role": "poc_entry"},
        {"op": "manifest_field_contains", "field": "metadata.stack_scaffold_id", "string": "python/flask"},
        {"op": "manifest_field_contains", "field": "metadata.fragment_id", "string": spec.fragment_id},
        {"op": "manifest_field_contains", "field": "metadata.compose_mode", "string": "registry"},
        {"op": "manifest_field_contains", "field": "metadata.compiler_strategy", "string": spec.strategy},
    ]
    deps = _requirements_dep_candidates(spec.requirements_content)
    if deps:
        assertions.append(
            {
                "op": "any_dep_declared",
                "deps": deps,
                "intent": "dependency",
                "stability": "high",
            }
        )
    for token in spec.service_side_tokens:
        if not token:
            continue
        assertions.append(
            {
                "op": "file_contains",
                "path": "app.py",
                "string": token,
                "severity": "warn",
                "intent": "syntax_hint",
                "stability": "high",
            }
        )
    return assertions


def service_side_file_contains_tokens(vuln_id: str, pattern_id: str = "", raw_label: str = "") -> List[str]:
    spec = resolve_fragment_spec(vuln_id, pattern_id=pattern_id, raw_label=raw_label)
    if spec is None:
        return []
    return [token for token in spec.service_side_tokens if token]


def _requirements_dep_candidates(requirements_content: str) -> List[str]:
    deps: List[str] = []
    seen: set[str] = set()
    for line in str(requirements_content or "").splitlines():
        token = line.split("#", 1)[0].strip().lower()
        if not token:
            continue
        normalized = re.split(r"[<>=!~\[\]\s]+", token, maxsplit=1)[0]
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deps.append(normalized)
    return deps


__all__ = [
    "FLASK_FRAGMENT_REGISTRY",
    "FlaskFragmentSpec",
    "fragment_guard_generator_assertions",
    "fragment_semantic_signature",
    "resolve_fragment_strategy",
    "resolve_fragment_spec",
    "service_side_file_contains_tokens",
]
