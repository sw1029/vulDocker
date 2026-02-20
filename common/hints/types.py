"""Schema helpers for structured generator hint payloads."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from common.guardrails import SUPPORTED_GENERATOR_ASSERTION_OPS

HINT_PAYLOAD_SCHEMA_VERSION = "hint_payload@1"


def normalize_hint_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    raw = payload if isinstance(payload, dict) else {}
    must_fix: List[Dict[str, Any]] = []
    semantic_gaps: List[Dict[str, Any]] = []
    normalization_suggestions: List[str] = []
    prompt_instructions: List[str] = []

    for item in raw.get("must_fix") or []:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip()
        target = str(item.get("target") or "").strip()
        expected = str(item.get("expected") or "").strip()
        observed = str(item.get("observed") or "").strip()
        evidence = str(item.get("evidence") or "").strip()
        if not kind or not target:
            continue
        must_fix.append(
            {
                "kind": kind,
                "target": target,
                "expected": expected,
                "observed": observed,
                "evidence": evidence,
            }
        )

    for item in raw.get("semantic_gaps") or []:
        if not isinstance(item, dict):
            continue
        bucket = str(item.get("bucket") or "").strip()
        required_terms = item.get("required_terms")
        observed_signals = item.get("observed_signals")
        if isinstance(required_terms, str):
            required_terms = [required_terms]
        if isinstance(observed_signals, str):
            observed_signals = [observed_signals]
        if not isinstance(required_terms, list):
            required_terms = []
        if not isinstance(observed_signals, list):
            observed_signals = []
        semantic_gaps.append(
            {
                "bucket": bucket,
                "required_terms": [str(item).strip() for item in required_terms if str(item).strip()],
                "observed_signals": [str(item).strip() for item in observed_signals if str(item).strip()],
            }
        )

    for item in raw.get("normalization_suggestions") or []:
        if isinstance(item, str) and item.strip():
            normalization_suggestions.append(item.strip())

    for item in raw.get("prompt_instructions") or []:
        if isinstance(item, str) and item.strip():
            prompt_instructions.append(item.strip())

    next_action = raw.get("next_action")
    if not isinstance(next_action, dict):
        next_action = {}
    retry_stage = str(next_action.get("retry_stage") or "GENERATOR").strip().upper()
    researcher_refresh = bool(next_action.get("researcher_refresh", False))
    rationale = str(next_action.get("rationale") or "").strip()

    supported_ops = raw.get("supported_ops")
    if isinstance(supported_ops, str):
        supported_ops = [supported_ops]
    if not isinstance(supported_ops, list):
        supported_ops = []
    normalized_supported_ops = [
        str(item).strip() for item in supported_ops if isinstance(item, str) and str(item).strip()
    ]
    if not normalized_supported_ops:
        normalized_supported_ops = sorted(SUPPORTED_GENERATOR_ASSERTION_OPS)

    return {
        "schema_version": HINT_PAYLOAD_SCHEMA_VERSION,
        "sid": str(raw.get("sid") or "").strip(),
        "vuln_id": str(raw.get("vuln_id") or "").strip(),
        "slug": str(raw.get("slug") or "").strip(),
        "loop": int(raw.get("loop", 0) or 0),
        "guard_error_code": str(raw.get("guard_error_code") or "").strip().lower(),
        "must_fix": must_fix,
        "semantic_gaps": semantic_gaps,
        "supported_ops": normalized_supported_ops,
        "normalization_suggestions": normalization_suggestions,
        "next_action": {
            "retry_stage": retry_stage,
            "researcher_refresh": researcher_refresh,
            "rationale": rationale,
        },
        "prompt_instructions": prompt_instructions,
    }


def build_hint_payload(
    *,
    sid: str,
    vuln_id: str,
    slug: str,
    loop: int,
    guard_error_code: str,
    must_fix: Optional[List[Dict[str, Any]]] = None,
    semantic_gaps: Optional[List[Dict[str, Any]]] = None,
    supported_ops: Optional[List[str]] = None,
    normalization_suggestions: Optional[List[str]] = None,
    next_action: Optional[Dict[str, Any]] = None,
    prompt_instructions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "schema_version": HINT_PAYLOAD_SCHEMA_VERSION,
        "sid": sid,
        "vuln_id": vuln_id,
        "slug": slug,
        "loop": loop,
        "guard_error_code": guard_error_code,
        "must_fix": must_fix or [],
        "semantic_gaps": semantic_gaps or [],
        "supported_ops": supported_ops or sorted(SUPPORTED_GENERATOR_ASSERTION_OPS),
        "normalization_suggestions": normalization_suggestions or [],
        "next_action": next_action or {},
        "prompt_instructions": prompt_instructions or [],
    }
    return normalize_hint_payload(payload)


__all__ = ["HINT_PAYLOAD_SCHEMA_VERSION", "build_hint_payload", "normalize_hint_payload"]
