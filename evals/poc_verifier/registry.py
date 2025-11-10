"""Simple plugin registry for PoC verifiers."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

from common.logging import get_logger
from common.rules import list_rules
from evals.poc_verifier.llm_assisted import llm_assisted_verify
from evals.poc_verifier.rule_based import verify_with_rule

LOGGER = get_logger(__name__)

VerifierFunc = Callable[[Path], Dict[str, Any]]

_REGISTRY: Dict[str, VerifierFunc] = {}


def _normalize(vuln_id: str) -> str:
    return (vuln_id or "").strip().lower()


_RULE_IDS = {_normalize(entry.get("id", "")) for entry in list_rules()}


def register_verifier(vuln_ids: Iterable[str], func: VerifierFunc) -> None:
    for vuln_id in vuln_ids:
        key = _normalize(vuln_id)
        if key:
            _REGISTRY[key] = func


def get_verifier(vuln_id: str) -> VerifierFunc | None:
    return _REGISTRY.get(_normalize(vuln_id))


def evaluate_with_vuln(
    vuln_id: str,
    log_path: Path,
    *,
    requirement: Optional[Dict[str, Any]] = None,
    run_summary: Optional[Dict[str, Any]] = None,
    plan_policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    rule_known = _rule_known(vuln_id)
    verifier = get_verifier(vuln_id)
    verifier_policy = _resolve_verifier_policy(requirement, plan_policy)

    base_result: Dict[str, Any]
    prefer_rule = bool(verifier_policy.get("prefer_rule"))
    if verifier is None or prefer_rule:
        base_result = verify_with_rule(
            vuln_id,
            log_path,
            requirement=requirement,
            run_summary=run_summary,
            policy=verifier_policy,
        )
        base_result.setdefault("verifier_meta", {"type": "rule", "rule_available": rule_known})
        if not rule_known:
            LOGGER.warning("No verifier or rule file available for %s", vuln_id)
        if base_result.get("status") == "unsupported" and verifier and not prefer_rule:
            plugin_result = verifier(log_path)
            plugin_result.setdefault("verifier_meta", {"type": "plugin", "rule_available": rule_known})
            base_result = plugin_result
    else:
        base_result = verifier(log_path)
        base_result.setdefault("verifier_meta", {"type": "plugin", "rule_available": rule_known})
        if not base_result.get("verify_pass"):
            rule_result = verify_with_rule(
                vuln_id,
                log_path,
                requirement=requirement,
                run_summary=run_summary,
                policy=verifier_policy,
            )
            if rule_result.get("status") != "unsupported":
                base_result = rule_result
                base_result.setdefault(
                    "verifier_meta", {"type": "rule", "rule_available": rule_known}
                )
                if base_result.get("verify_pass"):
                    return base_result

    if prefer_rule and base_result.get("status") == "unsupported" and verifier is not None:
        plugin_result = verifier(log_path)
        plugin_result.setdefault("verifier_meta", {"type": "plugin", "rule_available": rule_known})
        base_result = plugin_result

    if base_result.get("verify_pass"):
        return base_result

    llm_result = llm_assisted_verify(
        vuln_id,
        log_path,
        requirement=requirement,
        run_summary=run_summary,
        policy=verifier_policy,
        base_result=base_result,
    )
    return llm_result or base_result


def _rule_known(vuln_id: str) -> bool:
    return _normalize(vuln_id) in _RULE_IDS


def _resolve_verifier_policy(
    requirement: Optional[Dict[str, Any]], plan_policy: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    req_policy = ((requirement or {}).get("policy") or {}).get("verifier") or {}
    plan_verifier = (plan_policy or {}).get("verifier") or {}
    return {**plan_verifier, **req_policy}
