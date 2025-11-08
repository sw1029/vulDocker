"""Structured prompts shared by Generator and Reviewer agents."""
from __future__ import annotations

import json
from typing import Dict, List, Optional


def build_generator_prompt(
    requirement: Dict[str, object],
    rag_context: str,
    *,
    failure_context: str = "",
) -> List[Dict[str, str]]:
    """Return chat-style messages for the Generator agent."""

    system = (
        "You are the Generator agent inside an autonomous vulnerability testbed. "
        "Follow the contracts described in docs/architecture/agents_contracts.md. "
        "Emit concise plans and highlight assumptions."
    )
    user_payload = json.dumps(requirement, indent=2, ensure_ascii=False)
    sections = [
        "Create a build plan for a vulnerable environment using the following "
        "requirement JSON and RAG snippets. Do not write code; focus on plan, "
        "key files, and PoC outline.\n\n"
        f"# Requirement\n{user_payload}\n\n# RAG Context\n{rag_context}"
    ]
    if failure_context:
        sections.append(f"\n# Failure Context\n{failure_context}")
    user = "".join(sections)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def build_synthesis_prompt(
    requirement: Dict[str, object],
    rag_context: str,
    *,
    hints: str = "",
    failure_context: str = "",
    limits: Optional[Dict[str, object]] = None,
    candidate_index: int = 1,
    poc_template: Optional[Dict[str, object]] = None,
) -> List[Dict[str, str]]:
    """Prompt that asks the LLM to emit a manifest for synthesis mode."""

    system = (
        "You synthesize intentionally vulnerable Docker bundles for education. "
        "Follow docs/architecture/agents_contracts.md and produce ONLY compact JSON "
        "matching docs/schemas/generator_manifest.md."
    )
    requirement_payload = json.dumps(requirement, indent=2, ensure_ascii=False)
    limits_payload = json.dumps(limits or {}, indent=2, ensure_ascii=False)
    sections = [
        "Synthesize candidate #{idx} for the request below. The manifest must be JSON "
        "and contain files[], deps[], build, run, poc, notes, pattern_tags[]. "
        "Respect the file/path limits verbatim, include the SQLi success signature, and do not add standard library modules (e.g., logging, sqlite3) to deps[]."
        "\n\n# Requirement\n{req}\n\n# Synthesis Limits\n{limits}"
        "\n\n# Internal Hints\n{hints}\n\n# RAG Context\n{rag}".format(
            idx=candidate_index,
            req=requirement_payload,
            limits=limits_payload,
            hints=hints or "(none provided)",
            rag=rag_context or "(snapshot empty)",
        )
    ]
    if poc_template:
        poc_payload = json.dumps(poc_template, indent=2, ensure_ascii=False)
        sections.append(f"\n# PoC Template\n{poc_payload}")
    if failure_context:
        sections.append(f"\n# Failure Context\n{failure_context}")
    user = "".join(sections)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def build_reviewer_prompt(run_summary: Dict[str, object]) -> List[Dict[str, str]]:
    """Return chat-style messages for the Reviewer agent."""

    system = (
        "You are the Reviewer agent. Inspect logs and code summaries. "
        "Return JSON with any blocking issues per docs/architecture/agents_contracts.md."
    )
    user_payload = json.dumps(run_summary, indent=2, ensure_ascii=False)
    user = "Analyze the following run summary and spot regressions.\n" + user_payload
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
