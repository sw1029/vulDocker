"""Plan loading utilities shared by agents and executors."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from .paths import get_metadata_dir


def load_plan(sid: str) -> Dict[str, Any]:
    plan_path = get_metadata_dir(sid) / "plan.json"
    if not plan_path.exists():
        raise FileNotFoundError(f"Plan not found for {sid}")
    return json.loads(plan_path.read_text(encoding="utf-8"))


__all__ = ["load_plan"]
