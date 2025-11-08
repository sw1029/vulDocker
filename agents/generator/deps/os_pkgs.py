"""OS package detection from Dockerfile/build commands."""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, Set

Manifest = Dict[str, Any]
ReadContent = Callable[[Dict[str, Any]], str]

APT_RE = re.compile(r"apt-get\s+install([^;&]+)")
APK_RE = re.compile(r"apk\s+add([^;&]+)")
YUM_RE = re.compile(r"yum\s+install([^;&]+)")


def detect_os_packages(manifest: Manifest, read_content: ReadContent) -> Dict[str, Set[str]]:
    dockerfile_entry = _find_file(manifest, "Dockerfile")
    dockerfile_text = read_content(dockerfile_entry) if dockerfile_entry else ""
    build = manifest.get("build") or {}
    build_command = build.get("command") if isinstance(build, dict) else ""
    texts = [dockerfile_text, build_command or ""]
    return {
        "apt": _parse_packages(texts, APT_RE),
        "apk": _parse_packages(texts, APK_RE),
        "yum": _parse_packages(texts, YUM_RE),
    }


def _parse_packages(texts: list[str], pattern: re.Pattern[str]) -> Set[str]:
    packages: Set[str] = set()
    for text in texts:
        if not text:
            continue
        for match in pattern.finditer(text):
            body = match.group(1)
            tokens = [token.strip() for token in body.replace("\\n", " ").split()]
            for token in tokens:
                if not token or token.startswith("-"):
                    continue
                packages.add(token)
    return packages


def _find_file(manifest: Manifest, filename: str) -> Dict[str, Any] | None:
    target = filename.lower()
    for entry in manifest.get("files", []):
        if not isinstance(entry, dict):
            continue
        if (entry.get("path") or "").lower() == target:
            return entry
    return None


__all__ = ["detect_os_packages"]
