"""Persistence helpers for dynamic guard specs."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from common.paths import ensure_dir, get_metadata_dir

from .types import GuardSpec, parse_guard_spec


def guard_spec_path(metadata_dir: Path) -> Path:
    return metadata_dir / "guard_spec.json"


def guard_spec_ensemble_path(metadata_dir: Path) -> Path:
    return metadata_dir / "guard_spec_ensemble.json"


def write_guard_spec(metadata_dir: Path, payload: Dict[str, Any]) -> Path:
    ensure_dir(metadata_dir)
    path = guard_spec_path(metadata_dir)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_guard_spec_ensemble(metadata_dir: Path, payload: Dict[str, Any]) -> Path:
    ensure_dir(metadata_dir)
    path = guard_spec_ensemble_path(metadata_dir)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_guard_spec(metadata_dir: Path) -> Optional[GuardSpec]:
    path = guard_spec_path(metadata_dir)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    try:
        return parse_guard_spec(payload)
    except Exception:
        return None


def load_guard_spec_with_error(metadata_dir: Path) -> Tuple[Optional[GuardSpec], Optional[str]]:
    path = guard_spec_path(metadata_dir)
    if not path.exists():
        return None, "guard_spec.json missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"guard_spec.json parse error: {exc}"
    try:
        return parse_guard_spec(payload), None
    except Exception as exc:
        return None, f"guard_spec.json validation error: {exc}"


def load_guard_spec_for_sid(
    sid: str,
    *,
    slug: Optional[str] = None,
) -> Optional[GuardSpec]:
    sid = str(sid or "").strip()
    if not sid:
        return None
    base = get_metadata_dir(sid)
    candidate_dirs: list[Path] = []
    if slug:
        candidate_dirs.append(base / "bundles" / slug)
    candidate_dirs.append(base)
    for meta_dir in candidate_dirs:
        spec = load_guard_spec(meta_dir)
        if spec is not None:
            return spec
    return None


__all__ = [
    "guard_spec_path",
    "guard_spec_ensemble_path",
    "load_guard_spec",
    "load_guard_spec_for_sid",
    "load_guard_spec_with_error",
    "write_guard_spec",
    "write_guard_spec_ensemble",
]
