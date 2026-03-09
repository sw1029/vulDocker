"""Helpers for bundle-scoped researcher/generator runtime state."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from common.run_matrix import load_vuln_bundles, metadata_dir_for_bundle


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def load_bundle_research_report(plan: Dict[str, Any], bundle) -> Dict[str, Any]:
    metadata_dir = metadata_dir_for_bundle(plan, bundle)
    return _load_json(metadata_dir / "researcher_report.json")


def _infer_research_terminal_failure_class(report: Dict[str, Any]) -> str:
    if not isinstance(report, dict):
        return ""
    direct = str(report.get("terminal_failure_class") or "").strip().lower()
    if direct:
        return direct

    quality = str(report.get("quality") or "").strip().lower()
    quality_reason = str(report.get("quality_reason") or "").strip().lower()
    if quality != "insufficient":
        return ""

    health = _load_json(Path(str(report.get("search_health_path") or "").strip()))
    if isinstance(health, dict):
        if bool(health.get("degraded")):
            return "provider_degraded"
        if health.get("configured") is False:
            return "remote_provider_unavailable"
    if "low relevance score" in quality_reason:
        return "evidence_low_relevance"
    if "remote_required" in quality_reason or "remote provenance is required" in quality_reason:
        return "remote_evidence_missing"
    return "research_insufficient"


def bundle_research_blocker(plan: Dict[str, Any], bundle) -> Dict[str, Any]:
    report = load_bundle_research_report(plan, bundle)
    if not isinstance(report, dict):
        return {}
    quality = str(report.get("quality") or "").strip().lower()
    if quality != "insufficient":
        return {}
    quality_reason = str(report.get("quality_reason") or "").strip()
    blocker = {
        "bundle_slug": bundle.slug,
        "vuln_id": bundle.vuln_id,
        "stage": "RESEARCH",
        "generation_origin": "research_short_circuit",
        "reason": quality_reason or "Insufficient researcher evidence",
        "quality": quality,
        "quality_reason": quality_reason,
        "terminal_failure_class": _infer_research_terminal_failure_class(report),
        "retry_recommended": False,
        "report_path": str(metadata_dir_for_bundle(plan, bundle) / "researcher_report.json"),
    }
    search_health_path = str(report.get("search_health_path") or "").strip()
    if search_health_path:
        blocker["search_health_path"] = search_health_path
    return blocker


def collect_bundle_research_blockers(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    blockers: List[Dict[str, Any]] = []
    for bundle in load_vuln_bundles(plan):
        blocker = bundle_research_blocker(plan, bundle)
        if blocker:
            blockers.append(blocker)
    return blockers


__all__ = [
    "bundle_research_blocker",
    "collect_bundle_research_blockers",
    "load_bundle_research_report",
]
