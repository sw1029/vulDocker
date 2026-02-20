"""Simple plugin registry for PoC verifiers."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

from common.logging import get_logger
from common.rules import list_rules
from evals.poc_verifier.llm_assisted import llm_assisted_verify
from evals.poc_verifier.scenarios import EvaluationContext, build_evaluation_context, get_scenario, _scenario_for_type

LOGGER = get_logger(__name__)

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
    rule_known = _rule_known(vuln_id)
    verifier = get_verifier(vuln_id)
    verifier_policy = _resolve_verifier_policy(requirement, plan_policy)

    ctx: EvaluationContext = build_evaluation_context(
        vuln_id,
        log_path,
        requirement=requirement,
        run_summary=run_summary,
        policy=verifier_policy,
    )

    def _run_scenario() -> Dict[str, Any]:
        scenario_cls = get_scenario(vuln_id) or _scenario_for_type(ctx.rule_spec)
        scenario = scenario_cls(ctx)
        return scenario.verify()

    base_result: Dict[str, Any]
    prefer_rule = bool(verifier_policy.get("prefer_rule"))
    if verifier is None or prefer_rule:
        base_result = _run_scenario()
        base_result.setdefault("verifier_meta", {"type": "rule", "rule_available": rule_known})
        if not rule_known and base_result.get("status") == "unsupported":
            LOGGER.warning("No verifier or rule file available for %s", vuln_id)
        if base_result.get("status") == "unsupported" and verifier and not prefer_rule:
            plugin_result = verifier(log_path)
            plugin_result.setdefault("verifier_meta", {"type": "plugin", "rule_available": rule_known})
            base_result = plugin_result
    else:
        base_result = verifier(log_path)
        base_result.setdefault("verifier_meta", {"type": "plugin", "rule_available": rule_known})
        if not base_result.get("verify_pass"):
            scenario_result = _run_scenario()
            if scenario_result.get("status") != "unsupported":
                base_result = scenario_result
                base_result.setdefault("verifier_meta", {"type": "rule", "rule_available": rule_known})
                if base_result.get("verify_pass"):
                    return base_result

    if prefer_rule and base_result.get("status") == "unsupported" and verifier is not None:
        plugin_result = verifier(log_path)
        plugin_result.setdefault("verifier_meta", {"type": "plugin", "rule_available": rule_known})
        base_result = plugin_result

    if base_result.get("verify_pass"):
        return base_result

    # RuleSpec 요약 정보를 evidence_rules로 전달해 LLM verifier가
    # 정책/시그니처와 더 잘 정렬되도록 한다.
    rulespec = ctx.rule_spec
    evidence_rules: Dict[str, Any] | None = None
    if rulespec is not None:
        evidence_rules = {
            "cwe": rulespec.cwe,
            "scenario_type": rulespec.scenario_type,
            "template": {
                "service_entry": getattr(rulespec, "service_entry", None),
                "poc_entry": getattr(rulespec, "poc_entry", None),
                "flag_token": getattr(rulespec, "template_flag_token", None),
            },
            "verification": {
                "source": rulespec.verification_source,
                "require_flag": rulespec.require_flag,
                "flag_mode": rulespec.flag_required_mode,
                "exit_code_policy": rulespec.exit_code_policy,
            },
            "output": {
                "mode": rulespec.output_mode,
                "json_success_key": rulespec.json_success_key,
                "json_success_value": rulespec.json_success_value,
                "json_flag_key": rulespec.json_flag_key,
            },
            "runtime": rulespec.runtime,
            "llm": {
                "assist_default": rulespec.llm_assist_default,
                "assertion_budget": rulespec.assertion_budget,
            },
        }

    llm_result = llm_assisted_verify(
        vuln_id,
        log_path,
        requirement=requirement,
        run_summary=run_summary,
        policy=verifier_policy,
        evidence_rules=evidence_rules,
        base_result=base_result,
        rule_spec=rulespec,
    )
    return llm_result or base_result


def _rule_known(vuln_id: str) -> bool:
    key = _normalize(vuln_id)
    if not key:
        return False
    for entry in list_rules():
        if _normalize(entry.get("id", "")) == key:
            return True
    return False


def _resolve_verifier_policy(
    requirement: Optional[Dict[str, Any]], plan_policy: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    req_root_policy = (requirement or {}).get("policy") or {}
    req_policy = req_root_policy.get("verifier") or {}
    plan_verifier = (plan_policy or {}).get("verifier") or {}
    resolved = {**plan_verifier, **req_policy}
    plan_guard = (plan_policy or {}).get("guard")
    req_guard = req_root_policy.get("guard")
    if isinstance(plan_guard, dict) or isinstance(req_guard, dict):
        resolved["guard"] = {
            **(plan_guard if isinstance(plan_guard, dict) else {}),
            **(req_guard if isinstance(req_guard, dict) else {}),
        }
    return resolved
