"""CWE rule loader for generator/evaluator components."""
from __future__ import annotations

import functools
from pathlib import Path
from typing import Any, Dict, List

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
    path = RULES_ROOT / f"{filename}.yaml"
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Rule file {path} must contain a mapping")
    return data

@functools.lru_cache(maxsize=1)
def list_rules() -> List[Dict[str, Any]]:
    """Return metadata for all available rule files."""

    entries: List[Dict[str, Any]] = []
    if not RULES_ROOT.exists():
        return entries
    for rule_path in sorted(RULES_ROOT.glob("*.yaml")):
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


__all__ = ["load_rule", "list_rules"]
