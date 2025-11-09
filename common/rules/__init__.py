"""CWE rule loader for generator/evaluator components."""
from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Any, Dict

import yaml

RULES_ROOT = Path(__file__).resolve().parents[1] / "docs" / "evals" / "rules"


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


__all__ = ["load_rule"]
