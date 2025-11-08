"""Python dependency detection helpers."""
from __future__ import annotations

import ast
from typing import Any, Callable, Dict, Set

Manifest = Dict[str, Any]
ReadContent = Callable[[Dict[str, Any]], str]


def detect_required(manifest: Manifest, read_content: ReadContent) -> Set[str]:
    required: Set[str] = set()
    for entry in manifest.get("files", []):
        if not isinstance(entry, dict):
            continue
        path = (entry.get("path") or "").strip()
        if not path or not _is_python_path(path):
            continue
        content = read_content(entry)
        if not content:
            continue
        required.update(_detect_imports(content))
    return required


def _detect_imports(source: str) -> Set[str]:
    packages: Set[str] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return packages
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = (alias.name or "").split(".")[0]
                if root:
                    packages.add(root)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            module = node.module or ""
            root = module.split(".")[0]
            if root:
                packages.add(root)
    return packages


def _is_python_path(path: str) -> bool:
    lowered = path.lower()
    return lowered.endswith(".py") or lowered.endswith(".pyw")


__all__ = ["detect_required"]
