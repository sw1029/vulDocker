"""Helpers for tracking seeded/generated runtime assets under metadata/<SID>.

Runtime rules/templates can come from two sources:
- seeded assets copied in by a caller (for example the E2E harness)
- generated assets emitted by the pipeline itself during a run

We track both so reruns can clean generated state without deleting caller-
managed inputs, and so seeded inputs can be restored if a previous run
overwrote them.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List

GENERATED_RUNTIME_ASSETS_FILENAME = "generated_runtime_assets.json"
RUNTIME_ASSET_SEEDS_FILENAME = "runtime_asset_seeds.json"
_RUNTIME_DIRS = ("runtime_rules", "runtime_templates")


def _manifest_path(metadata_root: Path, filename: str) -> Path:
    return Path(metadata_root) / filename


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _normalize_kind(kind: str) -> str:
    token = str(kind or "").strip().lower()
    if token in {"rule", "rules", "runtime_rule", "runtime_rules"}:
        return "runtime_rules"
    if token in {"template", "templates", "runtime_template", "runtime_templates"}:
        return "runtime_templates"
    raise ValueError(f"unsupported runtime asset kind: {kind!r}")


def _relative_to_metadata(metadata_root: Path, target: Path) -> str:
    root = Path(metadata_root).resolve()
    resolved = Path(target).resolve()
    try:
        return str(resolved.relative_to(root))
    except ValueError:
        return str(resolved)


def _target_from_entry(metadata_root: Path, entry: Dict[str, Any]) -> Path | None:
    raw = entry.get("path")
    if not isinstance(raw, str) or not raw.strip():
        return None
    target = Path(raw)
    if target.is_absolute():
        return target
    return Path(metadata_root) / raw


def _dedupe_entries(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        key = json.dumps(
            {
                "kind": entry.get("kind"),
                "path": entry.get("path"),
                "source": entry.get("source"),
                "is_dir": bool(entry.get("is_dir")),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped


def has_runtime_asset_seed_manifest(metadata_root: Path) -> bool:
    return _manifest_path(metadata_root, RUNTIME_ASSET_SEEDS_FILENAME).exists()


def ensure_runtime_asset_seed_manifest(metadata_root: Path) -> Path:
    manifest_path = _manifest_path(metadata_root, RUNTIME_ASSET_SEEDS_FILENAME)
    payload = _load_json(manifest_path)
    assets = payload.get("assets")
    if not isinstance(assets, list):
        assets = []
    payload = {
        "schema_version": "runtime_asset_seeds@1.0",
        "assets": _dedupe_entries(assets),
    }
    _write_json(manifest_path, payload)
    return manifest_path


def record_generated_runtime_asset(metadata_root: Path, *, kind: str, path: Path) -> Path:
    manifest_path = _manifest_path(metadata_root, GENERATED_RUNTIME_ASSETS_FILENAME)
    payload = _load_json(manifest_path)
    entries = payload.get("assets")
    if not isinstance(entries, list):
        entries = []
    entries.append(
        {
            "kind": _normalize_kind(kind),
            "path": _relative_to_metadata(metadata_root, path),
            "is_dir": Path(path).is_dir(),
        }
    )
    payload = {
        "schema_version": "runtime_generated_assets@1.0",
        "assets": _dedupe_entries(entries),
    }
    _write_json(manifest_path, payload)
    return manifest_path


def record_runtime_asset_seed(
    metadata_root: Path,
    *,
    kind: str,
    source: Path,
    destination: Path,
) -> Path:
    manifest_path = _manifest_path(metadata_root, RUNTIME_ASSET_SEEDS_FILENAME)
    payload = _load_json(manifest_path)
    entries = payload.get("assets")
    if not isinstance(entries, list):
        entries = []
    source_path = Path(source)
    destination_path = Path(destination)
    entries.append(
        {
            "kind": _normalize_kind(kind),
            "source": str(source_path.resolve()),
            "path": _relative_to_metadata(metadata_root, destination_path),
            "is_dir": source_path.is_dir() or destination_path.is_dir(),
        }
    )
    payload = {
        "schema_version": "runtime_asset_seeds@1.0",
        "assets": _dedupe_entries(entries),
    }
    _write_json(manifest_path, payload)
    return manifest_path


def purge_runtime_asset_dirs(metadata_root: Path) -> List[str]:
    removed: List[str] = []
    for dirname in _RUNTIME_DIRS:
        root = Path(metadata_root) / dirname
        if root.exists():
            shutil.rmtree(root)
            removed.append(str(root))
        root.mkdir(parents=True, exist_ok=True)
    generated_manifest = _manifest_path(metadata_root, GENERATED_RUNTIME_ASSETS_FILENAME)
    if generated_manifest.exists():
        generated_manifest.unlink()
    return removed


def remove_generated_runtime_assets(metadata_root: Path) -> List[str]:
    manifest_path = _manifest_path(metadata_root, GENERATED_RUNTIME_ASSETS_FILENAME)
    payload = _load_json(manifest_path)
    entries = payload.get("assets")
    if not isinstance(entries, list):
        return []
    removed: List[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        target = _target_from_entry(metadata_root, entry)
        if target is None:
            continue
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
            removed.append(str(target))
        else:
            if target.exists():
                target.unlink(missing_ok=True)
                removed.append(str(target))
        for dirname in _RUNTIME_DIRS:
            runtime_root = Path(metadata_root) / dirname
            if runtime_root in target.parents and runtime_root.exists():
                runtime_root.mkdir(parents=True, exist_ok=True)
    manifest_path.unlink(missing_ok=True)
    return removed


def restore_seeded_runtime_assets(metadata_root: Path) -> List[str]:
    manifest_path = _manifest_path(metadata_root, RUNTIME_ASSET_SEEDS_FILENAME)
    payload = _load_json(manifest_path)
    entries = payload.get("assets")
    if not isinstance(entries, list):
        return []
    restored: List[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        source_raw = entry.get("source")
        if not isinstance(source_raw, str) or not source_raw.strip():
            continue
        source = Path(source_raw)
        if not source.exists():
            continue
        target = _target_from_entry(metadata_root, entry)
        if target is None:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        is_dir = bool(entry.get("is_dir")) or source.is_dir()
        if is_dir:
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
        restored.append(str(target))
    return restored


__all__ = [
    "GENERATED_RUNTIME_ASSETS_FILENAME",
    "RUNTIME_ASSET_SEEDS_FILENAME",
    "ensure_runtime_asset_seed_manifest",
    "has_runtime_asset_seed_manifest",
    "purge_runtime_asset_dirs",
    "record_generated_runtime_asset",
    "record_runtime_asset_seed",
    "remove_generated_runtime_assets",
    "restore_seeded_runtime_assets",
]
