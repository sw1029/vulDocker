"""Helpers for loading stdlib/alias metadata per language.

Prototype JSON files live under ``prototypes/stdlib`` and can be generated
via tools/bootstrap_stdlib.py. At runtime we fall back to built-in tables so
guard logic remains deterministic even when the prototype files are absent.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Set

from common.logging import get_logger
from common.paths import get_repo_root

LOGGER = get_logger(__name__)

STD_LIB_DIR = get_repo_root() / "prototypes" / "stdlib"


@dataclass(frozen=True)
class StdlibSpec:
    language: str
    version: str | None
    stdlib_modules: Set[str]
    aliases: Dict[str, str]
    default_versions: Dict[str, str]
    auto_patch_denylist: Set[str]


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("Failed to load stdlib spec %s: %s", path, exc)
        return {}


def load_stdlib_spec(language: str = "python", version: str | None = None) -> StdlibSpec:
    language = (language or "python").lower()
    version_token = (version or "").strip() or None
    candidates: Iterable[Path] = []
    paths: list[Path] = []
    if version_token:
        paths.append(STD_LIB_DIR / f"{language}-{version_token}.json")
    paths.append(STD_LIB_DIR / f"{language}.json")
    data: dict = {}
    for path in paths:
        if path.exists():
            data = _read_json(path)
            if data:
                break

    stdlib_modules = set(data.get("stdlib_modules", []))
    aliases = {entry.get("module", ""): entry.get("package", "") for entry in data.get("aliases", [])}
    aliases = {k: v for k, v in aliases.items() if k and v}
    default_versions = {k: v for k, v in (data.get("default_versions") or {}).items() if k and v}
    denylist = set(data.get("auto_patch_denylist", []))

    # hard-coded fallbacks ensure deterministic behaviour.
    if not stdlib_modules:
        stdlib_modules = {
            "abc",
            "argparse",
            "asyncio",
            "base64",
            "collections",
            "contextlib",
            "dataclasses",
            "datetime",
            "functools",
            "hashlib",
            "http",
            "json",
            "logging",
            "math",
            "os",
            "pathlib",
            "random",
            "re",
            "sqlite3",
            "ssl",
            "statistics",
            "subprocess",
            "sys",
            "threading",
            "typing",
            "unittest",
            "urllib",
            "uuid",
        }
    if not aliases:
        aliases = {"sqlite3": "pysqlite3-binary"}
    if not default_versions:
        default_versions = {
            "requests": "2.32.2",
            "pysqlite3-binary": "0.5.2",
        }
    if not denylist:
        denylist = {"logging", "sqlite3"}

    return StdlibSpec(
        language=language,
        version=version_token,
        stdlib_modules=stdlib_modules,
        aliases=aliases,
        default_versions=default_versions,
        auto_patch_denylist=denylist,
    )


__all__ = ["StdlibSpec", "load_stdlib_spec"]
