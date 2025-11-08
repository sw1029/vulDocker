"""Utility to load deterministic RAG context from local snapshots."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from common.paths import get_repo_root


def load_static_context(snapshot_name: str = "mvp-sample") -> str:
    base = get_repo_root() / "rag" / "corpus" / "processed" / snapshot_name
    if not base.exists():
        return ""
    chunks = []
    for path in sorted(base.rglob("*.md")):
        chunks.append(f"# File: {path.name}\n{path.read_text(encoding='utf-8')}")
    return "\n\n".join(chunks)
