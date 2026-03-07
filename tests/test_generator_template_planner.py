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
