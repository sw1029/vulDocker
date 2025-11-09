"""Structured prompts shared by Researcher, Generator, and Reviewer agents."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


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


def build_researcher_prompt(
    requirement: Dict[str, object],
    *,
    search_results: List[Dict[str, Any]],
    rag_context: str,
    failure_context: str = "",
    variation_key: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """Return messages instructing the Researcher to emit schema-compliant JSON."""

    system = (
        "You are the Researcher agent. Produce ONLY compact JSON per docs/schemas/researcher_report.md. "
        "Use ReAct-style reasoning internally but return the final JSON object without commentary."
    )
    requirement_payload = json.dumps(requirement, indent=2, ensure_ascii=False)
    search_payload = json.dumps(search_results or [], indent=2, ensure_ascii=False)
    sections = [
        "Create a researcher report JSON covering vuln_id, intent, preconditions, "
        "tech_stack_candidates, minimal_repro_steps, references, pocs, deps, risks, "
        "retrieval_snapshot_id, and optionally failure_context. "
        "Cite relevant references and align with docs/architecture/agents_contracts.md."
        "\n\n# Requirement\n{req}"
        "\n\n# Search Findings\n{search}"
        "\n\n# RAG Context\n{rag}".format(
            req=requirement_payload,
            search=search_payload,
            rag=rag_context or "(snapshot empty)",
        )
    ]
    if failure_context:
        sections.append(f"\n# Failure Context\n{failure_context}")
    if variation_key:
        sections.append(f"\n# Variation Key\n{json.dumps(variation_key, indent=2, ensure_ascii=False)}")
    user = "".join(sections)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def build_llm_verifier_prompt(
    requirement: Dict[str, Any],
    run_summary: Dict[str, Any],
    log_excerpt: str,
    *,
    evidence_rules: Optional[Dict[str, Any]] = None,
    metamorphic: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """Prompt instructing the LLM verifier helper to emit structured JSON."""

    schema_hint = {
        "verify_pass": "boolean",
        "confidence": "high|medium|low",
        "rationale": "short string",
        "proposed_assertions": [
            {
                "op": "regex_contains|contains|not_contains|number_delta",
                "pattern": "regex or literal",
                "flags": ["i"],
                "pattern_before": "...",
                "pattern_after": "...",
                "comparator": "lt|gt|eq",
                "delta": 0,
            }
        ],
        "extracted_evidence": ["string"],
        "metamorphic": {"total": 0, "passed": 0, "rationale": "..."},
    }
    system = (
        "You are a verification analyst. Determine if the exploit succeeded using ONLY the provided context. "
        "Reply with STRICT JSON matching the described schema. "
        "Do not invent data, do not cite external knowledge, and keep responses concise."
    )
    sections = [
        "Analyze the following requirement, executor run summary, rules, and log excerpt. "
        "Return strictly-formatted JSON per the schema below. If unsure, set confidence=low."
        f"\n\n# Schema\n{json.dumps(schema_hint, indent=2, ensure_ascii=False)}",
        f"\n\n# Requirement\n{json.dumps(requirement or {}, indent=2, ensure_ascii=False)}",
        f"\n\n# Run Summary\n{json.dumps(run_summary or {}, indent=2, ensure_ascii=False)}",
    ]
    if evidence_rules:
        sections.append(
            f"\n\n# Evidence Rules\n{json.dumps(evidence_rules, indent=2, ensure_ascii=False)}"
        )
    if metamorphic:
        sections.append(
            f"\n\n# Metamorphic Context\n{json.dumps(metamorphic, indent=2, ensure_ascii=False)}"
        )
    sections.append(f"\n\n# Log Excerpt (tail)\n```text\n{log_excerpt}\n```")
    user = "".join(sections)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
