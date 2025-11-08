"""Node/JavaScript dependency detection helpers."""
from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, Set

Manifest = Dict[str, Any]
ReadContent = Callable[[Dict[str, Any]], str]

IMPORT_RE = re.compile(r"import\s+[^;]*?from\s+['\"]([^'\"]+)['\"]", re.MULTILINE)
REQUIRE_RE = re.compile(r"require\(\s*['\"]([^'\"]+)['\"]\s*\)")
PKG_JSON_PATHS = {"package.json"}


def detect_required(manifest: Manifest, read_content: ReadContent) -> Set[str]:
    modules: Set[str] = set()
    for entry in manifest.get("files", []):
        if not isinstance(entry, dict):
            continue
        path = (entry.get("path") or "").lower()
        if not _is_js_path(path):
            continue
        content = read_content(entry)
        if not content:
            continue
        modules.update(_extract_modules(content))
    modules = {module for module in modules if not module.startswith((".", "/"))}
    return modules


def extract_declared(manifest: Manifest, read_content: ReadContent) -> Set[str]:
    declared: Set[str] = set()
    for entry in manifest.get("files", []):
        if not isinstance(entry, dict):
            continue
        path = (entry.get("path") or "").lower()
        if path not in PKG_JSON_PATHS:
            continue
        content = read_content(entry)
        if not content:
            continue
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            continue
        for section in ("dependencies", "devDependencies", "optionalDependencies"):
            deps = data.get(section) or {}
            if isinstance(deps, dict):
                for name in deps.keys():
                    declared.add((name or "").strip())
    return {name for name in declared if name}


def detect_installs(dockerfile: str | None, build_command: str | None) -> Set[str]:
    installs: Set[str] = set()
    for text in (dockerfile or "", build_command or ""):
        if not text:
            continue
        installs.update(_parse_npm_commands(text))
    return installs


def _extract_modules(content: str) -> Set[str]:
    modules: Set[str] = set()
    modules.update(IMPORT_RE.findall(content))
    modules.update(REQUIRE_RE.findall(content))
    return modules


def _parse_npm_commands(text: str) -> Set[str]:
    packages: Set[str] = set()
    lines = text.replace("\\n", "\n").splitlines()
    for line in lines:
        stripped = line.strip()
        if "npm install" in stripped or "yarn add" in stripped or "pnpm add" in stripped:
            packages.update(_tokens_from_command(stripped))
    return {pkg for pkg in packages if pkg and not pkg.startswith("-")}


def _tokens_from_command(command: str) -> Set[str]:
    packages: Set[str] = set()
    tokens = command.replace("&&", " ").replace(";", " ").split()
    capture = False
    for token in tokens:
        lower = token.lower()
        if lower in {"npm", "yarn", "pnpm"}:
            capture = False
            continue
        if lower in {"install", "add"}:
            capture = True
            continue
        if capture:
            if token.startswith("-"):
                continue
            packages.add(token.strip())
    return packages


def _is_js_path(path: str) -> bool:
    return path.endswith((".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"))


__all__ = ["detect_required", "extract_declared", "detect_installs"]
