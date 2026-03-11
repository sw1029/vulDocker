"""Helpers for normalizing template metadata across built-in/runtime templates."""
from __future__ import annotations

from typing import Any, Dict


def normalize_template_metadata(metadata: Dict[str, Any] | None) -> Dict[str, Any]:
    payload = dict(metadata) if isinstance(metadata, dict) else {}
    stack_id = str(payload.get("stack_id") or "").strip().lower()
    language = str(payload.get("language") or "").strip().lower()
    framework = str(payload.get("framework") or "").strip().lower()

    if stack_id and "/" in stack_id:
        parts = stack_id.split("/", 1)
        if not language:
            language = parts[0].strip().lower()
        if not framework:
            framework = parts[1].strip().lower()

    if not stack_id and language and framework:
        stack_id = f"{language}/{framework}"

    if not stack_id:
        inferred = _infer_stack_id(payload)
        if inferred:
            stack_id = inferred
            if "/" in stack_id:
                language, framework = stack_id.split("/", 1)

    if stack_id:
        payload["stack_id"] = stack_id
    if language:
        payload["language"] = language
    if framework:
        payload["framework"] = framework
    return payload


def _infer_stack_id(metadata: Dict[str, Any]) -> str:
    haystacks = []
    for key in ("id", "name", "pattern_id", "description"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            haystacks.append(value.strip().lower())
    tags = metadata.get("tags")
    if isinstance(tags, list):
        for item in tags:
            if isinstance(item, str) and item.strip():
                haystacks.append(item.strip().lower())
    joined = " ".join(haystacks)
    if "fastapi" in joined:
        return "python/fastapi"
    if "flask" in joined:
        return "python/flask"
    return ""


__all__ = ["normalize_template_metadata"]
