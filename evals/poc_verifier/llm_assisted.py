"""LLM-assisted PoC verification fallback."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional

from common.config import get_decoding_profile
from common.logging import get_logger
from common.llm import LLMClient
from common.prompts import build_llm_verifier_prompt
from evals.assertions import run_assertions

LOGGER = get_logger(__name__)
DEFAULT_LOG_EXCERPT = 6000


def llm_assisted_verify(
    vuln_id: str,
    log_path: Path,
    *,
    requirement: Optional[Dict[str, Any]] = None,
    run_summary: Optional[Dict[str, Any]] = None,
    policy: Optional[Dict[str, Any]] = None,
    evidence_rules: Optional[Dict[str, Any]] = None,
    base_result: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    cfg = dict(policy or {})
    if not cfg.get("llm_assist"):
        return None
    try:
        log_text = log_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise
    except Exception as exc:  # pragma: no cover - IO guard
        LOGGER.warning("Failed to read log for LLM verifier %s: %s", vuln_id, exc)
        return None

    excerpt_chars = int(cfg.get("log_excerpt_chars", DEFAULT_LOG_EXCERPT))
    log_excerpt = log_text[-excerpt_chars:]
    prompt = build_llm_verifier_prompt(
        requirement or {},
        run_summary or {},
        log_excerpt,
        evidence_rules=evidence_rules,
        metamorphic=cfg.get("metamorphic"),
    )
    model_name = (
        cfg.get("llm_model")
        or (requirement or {}).get("reviewer_model")
        or (requirement or {}).get("model_version")
        or "gpt-4.1-mini"
    )
    decoding = get_decoding_profile(cfg.get("llm_decoding") or "deterministic")
    client = LLMClient(model_name, decoding)

    raw_response = client.generate(prompt)
    parsed = _parse_llm_json(raw_response)
    if not isinstance(parsed, dict):
        LOGGER.warning("LLM verifier returned non-JSON content for %s", vuln_id)
        return None

    assertions = parsed.get("proposed_assertions")
    success_assertions, assertion_details = run_assertions(
        log_text, assertions if isinstance(assertions, list) else []
    )
    verify_pass = bool(parsed.get("verify_pass")) and success_assertions
    evidence_lines = []
    rationale = parsed.get("rationale")
    if isinstance(rationale, str) and rationale.strip():
        evidence_lines.append(rationale.strip())
    for outcome in assertion_details:
        prefix = "PASS" if outcome.success else "FAIL"
        evidence_lines.append(f"[{prefix}::{outcome.op}] {outcome.details}")
    extracted = parsed.get("extracted_evidence")
    if not evidence_lines and isinstance(extracted, list):
        evidence_lines.extend(str(item) for item in extracted)
    evidence = "\n".join(evidence_lines).strip() or "LLM-assisted verification"

    return {
        "verify_pass": verify_pass,
        "evidence": evidence,
        "log_path": str(log_path),
        "status": "evaluated-llm",
        "metamorphic": parsed.get("metamorphic"),
        "llm": {
            "model": model_name,
            "confidence": parsed.get("confidence", "unknown"),
            "raw_response_digest": _digest(raw_response),
            "assertions_checked": len(assertion_details),
            "base_status": (base_result or {}).get("status"),
        },
    }


def _parse_llm_json(raw: str) -> Optional[Dict[str, Any]]:
    text = (raw or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        segments = [segment.strip() for segment in text.split("```") if segment.strip()]
        if segments:
            candidate = segments[0]
            if candidate.lower().startswith("json"):
                candidate = candidate[4:].strip()
            text = candidate
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        return data
    return None


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

