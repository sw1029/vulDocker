"""Local RAG materializers used by the Generator agent."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from common.paths import get_repo_root


def load_static_context(snapshot_name: str = "mvp-sample") -> str:
    """Return concatenated Markdown snippets for a processed snapshot."""

    base = get_repo_root() / "rag" / "corpus" / "processed" / snapshot_name
    if not base.exists():
        return ""
    chunks: List[str] = []
    for path in sorted(base.rglob("*.md")):
        chunks.append(f"# File: {path.name}\n{path.read_text(encoding='utf-8')}")
    return "\n\n".join(chunks)


def load_hints(cwe_id: str, stack: str | None = None, *, limit: int | None = None) -> str:
    """Return curated CWE-specific hints for synthesis prompts.

    Parameters
    ----------
    cwe_id: str
        CWE identifier such as ``"CWE-89"``.
    stack: str, optional
        Optional stack descriptor (ex: ``"python-flask"``). When provided the
        loader attempts to read ``<stack>.md`` first, then falls back to
        ``default.md`` inside ``rag/hints/<cwe>/``.
    limit: int, optional
        Maximum number of hint files to concatenate. ``None`` keeps all files.
    """

    base = get_repo_root() / "rag" / "hints"
    normalized = (cwe_id or "").strip().lower().replace("_", "-")
    if not normalized.startswith("cwe-"):
        normalized = f"cwe-{normalized.split('-')[-1] if normalized else 'unknown'}"
    hint_dir = base / normalized
    if not hint_dir.exists():
        return ""

    def _slug(value: str) -> str:
        cleaned = "".join(ch if ch.isalnum() else "-" for ch in value.lower())
        return "-".join(filter(None, cleaned.split("-")))

    prioritized: List[Path] = []
    if stack:
        stack_slug = _slug(stack)
        if stack_slug:
            prioritized.append(hint_dir / f"{stack_slug}.md")
            if "-" in stack_slug:
                for token in stack_slug.split("-"):
                    prioritized.append(hint_dir / f"{token}.md")
    prioritized.append(hint_dir / "default.md")

    # Add remaining markdown hints deterministically.
    for path in sorted(hint_dir.glob("*.md")):
        if path not in prioritized:
            prioritized.append(path)

    snippets: List[str] = []
    for path in prioritized:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8").strip()
        if text:
            snippets.append(f"# Hint: {path.stem}\n{text}")
        if limit is not None and len(snippets) >= limit:
            break
    return "\n\n".join(snippets)


__all__ = ["load_static_context", "load_hints"]
