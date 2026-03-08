from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.generator.service import GeneratorContext, GeneratorService


def _context(*, failure: str = "") -> GeneratorContext:
    return GeneratorContext(
        rag="",
        failure=failure,
        hints="",
        researcher_report="",
        guard_spec="",
        guard_spec_dict={},
    )


def test_template_planner_is_skipped_for_clean_template_runs() -> None:
    service = GeneratorService.__new__(GeneratorService)
    service.requirement = {}  # type: ignore[attr-defined]

    assert service._should_generate_template_plan(_context()) is False  # type: ignore[attr-defined]


def test_template_planner_runs_when_failure_context_exists() -> None:
    service = GeneratorService.__new__(GeneratorService)
    service.requirement = {}  # type: ignore[attr-defined]

    assert service._should_generate_template_plan(_context(failure="retry with fixes")) is True  # type: ignore[attr-defined]


def test_template_planner_can_be_force_enabled_from_requirement() -> None:
    service = GeneratorService.__new__(GeneratorService)
    service.requirement = {"template_plan_enabled": True}  # type: ignore[attr-defined]

    assert service._should_generate_template_plan(_context()) is True  # type: ignore[attr-defined]


def test_hybrid_template_fallback_requires_compatible_template() -> None:
    service = GeneratorService.__new__(GeneratorService)
    service.requirement = {"vuln_id": "NAME-LDAP-INJECTION", "pattern_id": "generic-web-vuln"}  # type: ignore[attr-defined]
    service._allow_external_db = lambda: False  # type: ignore[attr-defined]

    class _Template:
        def __init__(self, tags: list[str], pattern_id: str, requires_external_db: bool = False) -> None:
            self.tags = tags
            self.pattern_id = pattern_id
            self.requires_external_db = requires_external_db

    class _Registry:
        templates = [
            _Template(["cwe-89", "sqlite"], "sqli-sqlite-raw"),
            _Template(["cwe-352", "csrf"], "csrf-missing-token"),
        ]

    service._get_registry = lambda: _Registry()  # type: ignore[attr-defined]
    assert service._has_compatible_template() is False  # type: ignore[attr-defined]

    service.requirement = {"vuln_id": "NAME-TEMPLATE-INJECTION", "pattern_id": "template-injection"}  # type: ignore[attr-defined]

    class _CompatibleRegistry:
        templates = [
            _Template(["name-template-injection", "flask"], "template-injection"),
        ]

    service._get_registry = lambda: _CompatibleRegistry()  # type: ignore[attr-defined]
    assert service._has_compatible_template() is True  # type: ignore[attr-defined]
