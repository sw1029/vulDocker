"""Prompt contract metadata shared across LLM-facing stages."""
from __future__ import annotations

from copy import deepcopy
from typing import Dict


_PROMPT_VERSION_MAP = {
    "generator_plan": "build_generator_prompt@1",
    "synthesis_manifest": "build_synthesis_prompt@1",
    "dep_guard_inference": "build_dep_guard_messages@1",
    "researcher_report": "build_researcher_prompt@1",
    "guard_planner": "build_guard_planner_prompt@1",
    "guard_autofix": "build_guard_autofix_prompt@1",
    "reviewer": "build_reviewer_prompt@1",
    "llm_verifier": "build_llm_verifier_prompt@1",
}


def prompt_contract(name: str) -> Dict[str, str]:
    """Return the prompt name/version contract for a known prompt family."""

    token = str(name or "").strip()
    if not token:
        return {}
    version = _PROMPT_VERSION_MAP.get(token)
    if not version:
        return {"name": token, "version": f"{token}@unknown"}
    return deepcopy({"name": token, "version": version})
