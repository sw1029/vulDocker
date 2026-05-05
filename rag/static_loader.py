"""Local RAG materializers used by the Generator agent."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List, Tuple

from common.paths import get_repo_root


def load_static_context(snapshot_name: str = "mvp-sample") -> str:
    """Return concatenated Markdown snippets for a processed/raw snapshot."""

    chunks = _processed_snapshot_chunks(snapshot_name)
    raw_chunks = _raw_cve_snapshot_chunks(snapshot_name)
    if chunks:
        chunks.extend(raw_chunks)
    elif snapshot_name != "mvp-sample":
        chunks = raw_chunks + _processed_snapshot_chunks("mvp-sample")
    return "\n\n".join(chunks)


def _processed_snapshot_chunks(snapshot_name: str) -> List[str]:
    base = get_repo_root() / "rag" / "corpus" / "processed" / snapshot_name
    if not base.exists():
        return []
    chunks: List[str] = []
    for path in sorted(base.rglob("*.md")):
        chunks.append(f"# File: {path.name}\n{path.read_text(encoding='utf-8')}")
    return chunks


def _raw_cve_snapshot_chunks(snapshot_name: str) -> List[str]:
    stamp = _snapshot_stamp(snapshot_name)
    if not stamp:
        return []
    raw_root = get_repo_root() / "rag" / "corpus" / "raw" / "poc"
    if not raw_root.exists():
        return []
    candidate_dirs: List[Path] = []
    direct = raw_root / stamp
    if direct.exists():
        candidate_dirs.append(direct)
    for path in sorted(raw_root.glob(f"*/{stamp}")):
        if path.is_dir() and path not in candidate_dirs:
            candidate_dirs.append(path)
    if not candidate_dirs:
        return []
    chunks: List[str] = []
    for base in candidate_dirs:
        for path in sorted(base.rglob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            records = _cve_record_payloads(payload)
            if records:
                for record in records:
                    chunk = _format_cve_record(record, source_path=path)
                    if chunk:
                        chunks.append(chunk)
                continue
            chunk = _format_cve_record(payload, source_path=path)
            if chunk:
                chunks.append(chunk)
    return chunks


def _snapshot_stamp(snapshot_name: str) -> str:
    token = str(snapshot_name or "").strip()
    if not token:
        return ""
    if token.startswith("rag-snap-"):
        token = token[len("rag-snap-") :]
    return token if token.isdigit() else ""


def _format_cve_record(payload: dict[str, Any], *, source_path: Path) -> str:
    cve_record = _cve_record_payload(payload)
    if not cve_record and any(key in payload for key in ("id", "CVE_data_meta", "descriptions", "weaknesses", "problemtype", "references")):
        cve_record = payload
    cve_id = _payload_text(payload, "cve_id", "cveID", "cveId") or _nested_payload_text(
        cve_record,
        ("id",),
        ("CVE_data_meta", "ID"),
        ("cveMetadata", "cveId"),
    )
    title = _payload_text(payload, "title", "vulnerabilityName") or cve_id
    description = (
        _payload_text(payload, "description", "shortDescription")
        or _localized_payload_text(cve_record.get("descriptions"))
        or _localized_payload_text(_nested_payload_value(cve_record, ("description", "description_data")))
    )
    link = _payload_text(payload, "link", "url") or _reference_url_from_payload(cve_record)
    published = (
        _payload_text(payload, "published", "dateAdded", "publicationDate")
        or _nested_payload_text(cve_record, ("published",), ("publishedDate",))
        or _payload_text(payload, "publishedDate")
    )
    source = _payload_text(payload, "source") or ("nvd" if cve_record else "")
    weakness_text = _weakness_text_from_payload(cve_record)
    tags = payload.get("tags")
    tag_values: List[str] = []
    if isinstance(tags, list):
        tag_values = [str(item).strip() for item in tags if str(item).strip()]
    elif isinstance(tags, str) and tags.strip():
        tag_values = [tags.strip()]
    if not any((cve_id, title, description, weakness_text, link, source, tag_values)):
        return ""
    lines = [f"# CVE Record: {cve_id or source_path.stem}"]
    for label, value in (
        ("CVE ID", cve_id),
        ("Title", title),
        ("Description", description),
        ("Weaknesses", weakness_text),
        ("Link", link),
        ("Published", published),
        ("Source", source),
        ("Tags", ", ".join(tag_values)),
        ("Local path", str(source_path)),
    ):
        if value:
            lines.append(f"- {label}: {value}")
    return "\n".join(lines)


def _payload_text(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _cve_record_payload(payload: dict[str, Any]) -> dict[str, Any]:
    records = _cve_record_payloads(payload)
    return records[0] if records else {}


def _cve_record_payloads(payload: dict[str, Any]) -> List[dict[str, Any]]:
    cve = payload.get("cve")
    if isinstance(cve, dict):
        record = dict(cve)
        if "cveMetadata" not in record and isinstance(payload.get("cveMetadata"), dict):
            record["cveMetadata"] = payload["cveMetadata"]
        return [record]
    vulnerabilities = payload.get("vulnerabilities")
    records: List[dict[str, Any]] = []
    if isinstance(vulnerabilities, list):
        for item in vulnerabilities:
            if not isinstance(item, dict):
                continue
            records.extend(_cve_record_payloads(item))
    return records


def _nested_payload_value(payload: dict[str, Any], path: Tuple[str, ...]) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _nested_payload_text(payload: dict[str, Any], *paths: Tuple[str, ...]) -> str:
    for path in paths:
        value = _nested_payload_value(payload, path)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _localized_payload_text(values: Any) -> str:
    if not isinstance(values, list):
        return ""
    fallback = ""
    for item in values:
        if not isinstance(item, dict):
            continue
        value = str(item.get("value") or "").strip()
        if not value:
            continue
        if not fallback:
            fallback = value
        if str(item.get("lang") or "").strip().lower() in {"en", "eng"}:
            return value
    return fallback


def _reference_url_from_payload(payload: dict[str, Any]) -> str:
    references = payload.get("references")
    if isinstance(references, dict):
        reference_data = references.get("referenceData")
    else:
        reference_data = references
    if not isinstance(reference_data, list):
        return ""
    for item in reference_data:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if url:
            return url
    return ""


def _weakness_text_from_payload(payload: dict[str, Any]) -> str:
    values: List[str] = []
    weaknesses = payload.get("weaknesses")
    if isinstance(weaknesses, list):
        for entry in weaknesses:
            if not isinstance(entry, dict):
                continue
            text = _localized_payload_text(entry.get("description"))
            if text and text not in values:
                values.append(text)
    problemtype_data = _nested_payload_value(payload, ("problemtype", "problemtype_data"))
    if isinstance(problemtype_data, list):
        for entry in problemtype_data:
            if not isinstance(entry, dict):
                continue
            text = _localized_payload_text(entry.get("description"))
            if text and text not in values:
                values.append(text)
    return ", ".join(values)


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
    default_hint = base / "default.md"
    if not hint_dir.exists():
        return default_hint.read_text(encoding="utf-8").strip() if default_hint.exists() else ""

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
    if snippets:
        return "\n\n".join(snippets)
    if default_hint.exists():
        text = default_hint.read_text(encoding="utf-8").strip()
        if text:
            return f"# Hint: default\n{text}"
    return ""

def load_boilerplate(stack: str | None = None, *, limit: int | None = None) -> str:
    """Return stack-level boilerplate hints (executor constraints, DB init patterns, etc.).

    Unlike ``load_hints`` (CWE-specific), boilerplate is *stack* oriented so it
    can be reused across vulnerabilities without adding per-CWE templates.
    """

    base = get_repo_root() / "rag" / "boilerplate"
    if not base.exists():
        return ""

    def _slug(value: str) -> str:
        cleaned = "".join(ch if ch.isalnum() else "-" for ch in value.lower())
        return "-".join(filter(None, cleaned.split("-")))

    prioritized: List[Path] = []
    if stack:
        stack_slug = _slug(stack)
        if stack_slug:
            prioritized.append(base / f"{stack_slug}.md")
            if "-" in stack_slug:
                for token in stack_slug.split("-"):
                    prioritized.append(base / f"{token}.md")
    prioritized.append(base / "default.md")

    for path in sorted(base.glob("*.md")):
        if path not in prioritized:
            prioritized.append(path)

    snippets: List[str] = []
    for path in prioritized:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8").strip()
        if text:
            snippets.append(f"# Boilerplate: {path.stem}\n{text}")
        if limit is not None and len(snippets) >= limit:
            break
    return "\n\n".join(snippets)


__all__ = ["load_static_context", "load_hints", "load_boilerplate"]
