"""CSRF verifier plugin."""
from __future__ import annotations

from pathlib import Path

from .registry import register_verifier
from .scenarios import BaseScenarioVerifier, RuleBasedScenario, build_evaluation_context, register_scenario


class CsrfScenario(BaseScenarioVerifier):
    """CSRF-specific scenario that reuses the generic RuleBasedScenario.

    기존 하드코딩된 \"CSRF SUCCESS\"/\"FLAG\" 문자열 대신 RuleSpec/runtime rule에
    정의된 success_text_markers, flag_token, assertion_program 등에 기반해
    검증을 수행한다.
    """

    def verify(self) -> dict:
        delegate = RuleBasedScenario(self.context)
        return delegate.verify()


def _evaluate_csrf_log(log_path: Path) -> dict:
    context = build_evaluation_context("CWE-352", log_path)
    scenario = CsrfScenario(context)
    return scenario.verify()


register_verifier(["CWE-352", "csrf"], _evaluate_csrf_log)
register_scenario(["CWE-352", "csrf"], CsrfScenario)
