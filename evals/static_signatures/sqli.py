"""Static SQLi signature scorer for TODO 14.5 synthesis candidates.

The heuristics intentionally stay lightweight so that they can run before the
Docker workspace is built. They operate purely on the manifest JSON produced by
`agents/generator/synthesis.py`.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List

SQLI_PATTERNS = {
    "union_select": r"UNION\s+SELECT",
    "tautology_or": r"'\s*OR\s*'1'='1",
    "comment_truncation": r"--\s*[\r\n]",
    "concat_request": r"request\.(args|get_json).*\+",
    "sql_success_marker": r"SQLi\s+SUCCESS",
}

KEYWORDS = [
    "UNION SELECT",
    "SQLi SUCCESS",
    "' OR '1'='1",
    "OR 1=1",
]


def _collect_text(manifest: Dict[str, object]) -> List[str]:
    files = manifest.get("files") or []
    blobs: List[str] = []
    for entry in files:
        if isinstance(entry, dict):
            content = entry.get("content")
            if isinstance(content, str):
                blobs.append(content)
    poc = manifest.get("poc")
    if isinstance(poc, dict):
        for key in ("cmd", "notes"):
            value = poc.get(key)
            if isinstance(value, str):
                blobs.append(value)
    return blobs


def analyze_sql_injection_signals(manifest: Dict[str, object]) -> Dict[str, object]:
    """Return heuristics describing SQL injection signals.

    The return payload intentionally mirrors what reviewers need: individual
    signal booleans, a normalized score (0~1), and the literal keywords found.
    """

    blobs = _collect_text(manifest)
    combined = "\n".join(blobs)
    signals: Dict[str, bool] = {}
    for name, pattern in SQLI_PATTERNS.items():
        signals[name] = bool(re.search(pattern, combined, flags=re.IGNORECASE))
    keywords_found: List[str] = []
    for keyword in KEYWORDS:
        if keyword.lower() in combined.lower():
            keywords_found.append(keyword)
    hit_count = sum(1 for hit in signals.values() if hit)
    score = hit_count / max(1, len(SQLI_PATTERNS))
    return {
        "signals": signals,
        "hit_count": hit_count,
        "score": round(score, 3),
        "keywords_found": keywords_found,
    }


__all__ = ["analyze_sql_injection_signals"]
