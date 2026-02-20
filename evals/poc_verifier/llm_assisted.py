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
from common.rules import RuleSpec, load_rulespec
from evals.assertions import run_assertions

LOGGER = get_logger(__name__)
DEFAULT_LOG_EXCERPT = 6000


def _effective_llm_config(
    spec: Optional[RuleSpec],
    policy: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Combine caller policy with RuleSpec defaults into a single config."""
    cfg = dict(policy or {})
    if "llm_assist" not in cfg and isinstance(spec, RuleSpec):
        cfg["llm_assist"] = bool(getattr(spec, "llm_assist_default", False))
    if "assertion_budget" not in cfg and isinstance(spec, RuleSpec):
        cfg["assertion_budget"] = getattr(spec, "assertion_budget", 8)
    if "log_excerpt_chars" not in cfg:
        cfg["log_excerpt_chars"] = DEFAULT_LOG_EXCERPT
    return cfg


def llm_assisted_verify(
    vuln_id: str,
    log_path: Path,
    *,
    requirement: Optional[Dict[str, Any]] = None,
    run_summary: Optional[Dict[str, Any]] = None,
    policy: Optional[Dict[str, Any]] = None,
    evidence_rules: Optional[Dict[str, Any]] = None,
    base_result: Optional[Dict[str, Any]] = None,
    rule_spec: Optional[RuleSpec] = None,
) -> Optional[Dict[str, Any]]:
    try:
        log_text = log_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise
    except Exception as exc:  # pragma: no cover - IO guard
        LOGGER.warning("Failed to read log for LLM verifier %s: %s", vuln_id, exc)
        return None

    # If a runtime assertion program is available in RuleSpec, prefer it
    # before invoking the LLM, to keep verification as deterministic and
    # policy-driven as possible. 이 경로는 policy.llm_assist 여부와 무관하게
    # 항상 실행된다.
    spec: Optional[RuleSpec]
    if rule_spec is not None:
        spec = rule_spec
    else:
        try:
            spec = load_rulespec(vuln_id)
        except Exception:  # pragma: no cover - defensive
            spec = None
    if spec and isinstance(spec.runtime, dict):
        program = spec.runtime.get("assertion_program")
        if isinstance(program, list) and program:
            success, assertion_details = run_assertions(log_text, program)
            if success:
                evidence_lines = []
                for outcome in assertion_details:
                    prefix = "PASS" if outcome.success else "FAIL"
                    evidence_lines.append(f"[{prefix}::{outcome.op}] {outcome.details}")
                evidence = "\n".join(evidence_lines).strip() or "runtime assertion program satisfied"
                return {
                    "verify_pass": True,
                    "evidence": evidence,
                    "log_path": str(log_path),
                    "status": "evaluated-llm",
                    "metamorphic": None,
                    "llm": {
                        "model": "runtime-assertions",
                        "confidence": "high",
                        "raw_response_digest": _digest(evidence),
                        "assertions_checked": len(assertion_details),
                        "base_status": (base_result or {}).get("status"),
                    },
                }

    # Decide whether to call the LLM at all, combining explicit policy with
    # RuleSpec의 기본 설정(assist_default).
    cfg = _effective_llm_config(spec, policy)
    llm_assist_flag = cfg.get("llm_assist")
    if not llm_assist_flag:
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
        or "gpt-5.2"
    )
    decoding = get_decoding_profile(cfg.get("llm_decoding") or "deterministic")
    client = LLMClient(model_name, decoding)

    raw_response = client.generate(prompt)
    parsed = _parse_llm_json(raw_response)
    if not isinstance(parsed, dict):
        LOGGER.warning("LLM verifier returned non-JSON content for %s", vuln_id)
        return None

    assertions = parsed.get("proposed_assertions")
    assertion_list = assertions if isinstance(assertions, list) else []
    # Limit the number of LLM-proposed assertions according to policy/spec.
    budget = cfg.get("assertion_budget")
    max_assertions = int(budget) if isinstance(budget, (int, float)) else None
    if max_assertions is not None and max_assertions >= 0:
        assertion_list = assertion_list[: max_assertions or 0] if max_assertions else []
    success_assertions, assertion_details = run_assertions(log_text, assertion_list)
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
