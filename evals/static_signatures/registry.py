"""Registry for vuln-specific static signal analyzers.

These analyzers are used during synthesis candidate scoring (pre-build) to
prefer manifests that contain stronger vulnerability signals for a given CWE.
"""

from __future__ import annotations

from typing import Callable, Dict, Iterable

Analyzer = Callable[[Dict[str, object]], Dict[str, object]]

_ANALYZERS: Dict[str, Analyzer] = {}


def _normalize(vuln_id: str) -> str:
    return (vuln_id or "").strip().lower()


def register_static_analyzer(vuln_ids: Iterable[str], func: Analyzer) -> None:
    for vuln_id in vuln_ids:
        key = _normalize(vuln_id)
        if not key:
            continue
        _ANALYZERS[key] = func


def analyze_static_signals(vuln_id: str, manifest: Dict[str, object]) -> Dict[str, object]:
    func = _ANALYZERS.get(_normalize(vuln_id))
    if func is None:
        return {"signals": {}, "hit_count": 0, "score": 0.0, "keywords_found": []}
    return func(manifest)


__all__ = ["analyze_static_signals", "register_static_analyzer"]

