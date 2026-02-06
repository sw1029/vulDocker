"""SQLi verifier plugin registration."""
from __future__ import annotations

from pathlib import Path

from .registry import register_verifier
from .scenarios import BaseScenarioVerifier, RuleBasedScenario, build_evaluation_context, register_scenario


class SqlInjectionScenario(BaseScenarioVerifier):
    """SQLi-specific scenario that delegates to the generic RuleBasedScenario.

    This removes hardcoded \"SQLi SUCCESS\"/\"FLAG\" checks from the plugin and
    instead relies on RuleSpec/runtime rule configuration (success markers,
    flag token, assertion_program 등)과 rule_based verifier를 사용한다.
    """

    def verify(self) -> dict:
        # Reuse the RuleBasedScenario implementation so that SQLi behaves
        # consistently with other rule-driven scenarios (runtime assertions,
        # JSON output rules, exit code policy 등).
        delegate = RuleBasedScenario(self.context)
        return delegate.verify()


def _evaluate_sqli_log(log_path: Path) -> dict:
    context = build_evaluation_context("CWE-89", log_path)
    scenario = SqlInjectionScenario(context)
    return scenario.verify()


register_verifier(["CWE-89", "sqli"], _evaluate_sqli_log)
register_scenario(["CWE-89", "sqli"], SqlInjectionScenario)
