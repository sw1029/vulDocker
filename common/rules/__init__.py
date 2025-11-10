"""CWE rule loader for generator/evaluator components."""
from __future__ import annotations

import functools
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List

import yaml

RULES_ROOT = Path(__file__).resolve().parents[2] / "docs" / "evals" / "rules"


@functools.lru_cache(maxsize=32)
def load_rule(vuln_id: str | None) -> Dict[str, Any]:
    if not vuln_id:
        return {}
    normalized = str(vuln_id).strip().lower()
    if not normalized:
        return {}
    filename = normalized if normalized.startswith("cwe-") else f"cwe-{normalized}"
    for path in _candidate_rule_paths(filename):
        if not path.exists():
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Rule file {path} must contain a mapping")
        return data
    return {}

def list_rules() -> List[Dict[str, Any]]:
    """Return metadata for all available rule files (env-aware cache)."""

    signature = _runtime_signature()
    return _list_rules_cached(signature)


@functools.lru_cache(maxsize=8)
def _list_rules_cached(signature: str) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for rule_path in _iter_rule_paths():
        try:
            data = yaml.safe_load(rule_path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        rule_id = str(data.get("cwe") or rule_path.stem).strip()
        if not rule_id:
            continue
        entries.append({"id": rule_id, "path": str(rule_path), "data": data})
    return entries


def _candidate_rule_paths(filename: str) -> Iterable[Path]:
    yield RULES_ROOT / f"{filename}.yaml"
    for extra_root in _runtime_rule_dirs():
        yield extra_root / f"{filename}.yaml"


def _runtime_rule_dirs() -> List[Path]:
    env = os.environ.get("VULD_RUNTIME_RULE_DIRS") or ""
    dirs: List[Path] = []
    for raw in env.split(os.pathsep):
        raw = raw.strip()
        if not raw:
            continue
        dirs.append(Path(raw))
    return dirs


def _runtime_signature() -> str:
    roots = [str(RULES_ROOT)] + [str(path) for path in _runtime_rule_dirs()]
    return os.pathsep.join(sorted(set(roots)))


def _iter_rule_paths() -> Iterable[Path]:
    seen: set[Path] = set()
    for root in [RULES_ROOT, *_runtime_rule_dirs()]:
        if not root.exists():
            continue
        for rule_path in sorted(root.glob("*.yaml")):
            if rule_path in seen:
                continue
            seen.add(rule_path)
            yield rule_path


__all__ = ["load_rule", "list_rules"]
