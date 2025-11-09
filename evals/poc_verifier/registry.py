"""Simple plugin registry for PoC verifiers."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

from evals.poc_verifier.llm_assisted import llm_assisted_verify

VerifierFunc = Callable[[Path], Dict[str, Any]]

_REGISTRY: Dict[str, VerifierFunc] = {}


def _normalize(vuln_id: str) -> str:
    return (vuln_id or "").strip().lower()


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
    verifier = get_verifier(vuln_id)
    base_result: Dict[str, Any]
    if verifier is None:
        base_result = {
            "verify_pass": False,
            "evidence": f"No verifier registered for {vuln_id}",
            "log_path": str(log_path),
            "status": "unsupported",
        }
    else:
        base_result = verifier(log_path)

    if base_result.get("verify_pass"):
        return base_result

    verifier_policy = _resolve_verifier_policy(requirement, plan_policy)
    llm_result = llm_assisted_verify(
        vuln_id,
        log_path,
        requirement=requirement,
        run_summary=run_summary,
        policy=verifier_policy,
        base_result=base_result,
    )
    return llm_result or base_result


def _resolve_verifier_policy(
    requirement: Optional[Dict[str, Any]], plan_policy: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    req_policy = ((requirement or {}).get("policy") or {}).get("verifier") or {}
    plan_verifier = (plan_policy or {}).get("verifier") or {}
    return {**plan_verifier, **req_policy}
