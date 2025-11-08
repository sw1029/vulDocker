"""Path helpers to keep directory layout consistent."""
from __future__ import annotations

from pathlib import Path


def get_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def get_metadata_dir(sid: str) -> Path:
    return get_repo_root() / "metadata" / sid


def get_workspace_dir(sid: str) -> Path:
    return get_repo_root() / "workspaces" / sid / "app"


def get_artifacts_dir(sid: str) -> Path:
    return get_repo_root() / "artifacts" / sid


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
