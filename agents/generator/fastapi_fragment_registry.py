"""Registry of python/fastapi scaffold fragments for compiler-covered families."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List

from agents.generator.flask_fragment_registry import FlaskFragmentSpec


ASSETS_ROOT = Path(__file__).resolve().parent / "assets"
FRAGMENT_CATALOG_PATH = ASSETS_ROOT / "fastapi-fragments.json"
FRAGMENT_CODE_CATALOG_PATH = ASSETS_ROOT / "fastapi-fragment-code.json"
POC_TEMPLATES_ROOT = ASSETS_ROOT / "fastapi-pocs"


def _fragment_catalog() -> Dict[str, Dict[str, Any]]:
    payload = json.loads(FRAGMENT_CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}
    return {
        key: value
        for key, value in payload.items()
        if isinstance(key, str) and isinstance(value, dict)
    }


def _fragment_kwargs(strategy: str) -> Dict[str, Any]:
    payload = _fragment_catalog().get(strategy) or {}
    semantic_signature_raw = payload.get("semantic_signature") if isinstance(payload.get("semantic_signature"), dict) else {}
    semantic_signature = {
        bucket: tuple(
            str(item)
            for item in (semantic_signature_raw.get(bucket) or [])
            if isinstance(item, str) and item.strip()
        )
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
        "pattern_tags": tuple(
            str(item)
            for item in (payload.get("pattern_tags") or [])
            if isinstance(item, str) and item.strip()
        ),
        "notes": str(payload.get("notes") or ""),
        "service_description": str(payload.get("service_description") or ""),
        "poc_description": str(payload.get("poc_description") or ""),
        "service_side_tokens": tuple(
            str(item)
            for item in (payload.get("service_side_tokens") or [])
            if isinstance(item, str) and item.strip()
        ),
        "semantic_signature": semantic_signature,
        "requirements_content": str(payload.get("requirements_content") or ""),
        "extra_files": tuple(extra_files),
        "requires_external_db": bool(payload.get("requires_external_db", False)),
    }


def _fragment_code_catalog() -> Dict[str, Dict[str, Any]]:
    payload = json.loads(FRAGMENT_CODE_CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}
    return {
        key: value
        for key, value in payload.items()
        if isinstance(key, str) and isinstance(value, dict)
    }


def _fragment_code_text(strategy: str, field: str) -> str:
    payload = _fragment_code_catalog().get(strategy) or {}
    lines = payload.get(field)
    if not isinstance(lines, list):
        return ""
    text = "\n".join(str(item) for item in lines if isinstance(item, str))
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


FASTAPI_FRAGMENT_REGISTRY: Dict[str, FlaskFragmentSpec] = _build_fragment_registry()


__all__ = ["FASTAPI_FRAGMENT_REGISTRY"]
