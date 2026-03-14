"""Normalization helpers for researcher report payloads."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

from common.guardrails import normalize_semantic_signature


_PASSTHROUGH_KEYS = (
    "type",
    "version",
    "requirement_id",
    "sid",
    "vuln_id",
    "trace_id",
    "retrieval_snapshot_id",
    "intent",
    "preconditions",
    "minimal_repro_steps",
    "references",
    "pocs",
    "deps",
    "risks",
    "failure_context",
    "verification_spec",
    "verification_specs",
    "search_policy",
    "search_health_path",
    "search_degraded",
    "evidence",
    "semantic_signature",
    "semantic_signature_source",
    "quality",
    "quality_reason",
    "guard_fallback",
    "created_at",
    "guard_spec_path",
    "guard_spec_ensemble_path",
    "candidate_rules",
    "candidate_templates",
    "resolved_contract_path",
    "evidence_relevance",
    "query_plan",
    "evidence_type_summary",
    "family_hypothesis_summary",
    "evidence_graph",
    "llm_execution",
)


def normalize_researcher_report_payload(payload: Any) -> Dict[str, Any]:
    """Flatten wrapped researcher outputs into the canonical top-level shape."""

    if not isinstance(payload, dict):
        return {}
    normalized = deepcopy(payload)
    wrapped = payload.get("researcher_report")
    if not isinstance(wrapped, dict):
        return normalized

    merged = deepcopy(wrapped)
    for key in _PASSTHROUGH_KEYS:
        if key in merged or key not in payload:
            continue
        merged[key] = deepcopy(payload[key])

    schema_normalization = merged.get("schema_normalization")
    if not isinstance(schema_normalization, dict):
        schema_normalization = {}
    schema_normalization.setdefault("wrapped", True)
    schema_normalization.setdefault("source_key", "researcher_report")
    merged["schema_normalization"] = schema_normalization
    return merged


def extract_verification_spec(
    report: Any,
    *,
    vuln_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Read a verification_spec block from canonical or wrapped report payloads."""

    normalized = normalize_researcher_report_payload(report)
    spec = normalized.get("verification_spec")
    if isinstance(spec, dict):
        return deepcopy(spec)

    mapping = normalized.get("verification_specs")
    if not isinstance(mapping, dict):
        return None

    key_candidates = []
    if isinstance(vuln_id, str) and vuln_id.strip():
        raw = vuln_id.strip()
        key_candidates.extend([raw, raw.upper(), raw.lower()])
    for key in key_candidates:
        value = mapping.get(key)
        if isinstance(value, dict):
            return deepcopy(value)
    return None


def extract_semantic_contract(report: Any) -> Dict[str, Any]:
    """Return the semantic contract subset that downstream stages can share."""

    normalized = normalize_researcher_report_payload(report)
    semantic_signature = normalize_semantic_signature(normalized.get("semantic_signature") or {})
    semantic_signature_source = normalized.get("semantic_signature_source")
    if isinstance(semantic_signature_source, str):
        semantic_signature_source = [semantic_signature_source]
    if not isinstance(semantic_signature_source, list):
        semantic_signature_source = []
    semantic_signature_source = [
        str(item).strip()
        for item in semantic_signature_source
        if isinstance(item, str) and str(item).strip()
    ]

    contract: Dict[str, Any] = {}
    if any(semantic_signature.get(bucket) for bucket in semantic_signature):
        contract["semantic_signature"] = semantic_signature
    if semantic_signature_source:
        contract["semantic_signature_source"] = semantic_signature_source

    for key in ("quality", "quality_reason"):
        value = normalized.get(key)
        if isinstance(value, str) and value.strip():
            contract[key] = value.strip()

    relevance = normalized.get("evidence_relevance")
    if isinstance(relevance, dict) and relevance:
        contract["evidence_relevance"] = deepcopy(relevance)
    family_hypothesis_summary = normalized.get("family_hypothesis_summary")
    if isinstance(family_hypothesis_summary, dict) and family_hypothesis_summary:
        contract["family_hypothesis_summary"] = deepcopy(family_hypothesis_summary)
    return contract


__all__ = [
    "extract_semantic_contract",
    "extract_verification_spec",
    "normalize_researcher_report_payload",
]
