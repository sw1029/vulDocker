"""Structured prompts shared by Researcher, Generator, and Reviewer agents."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from common.guardrails import SUPPORTED_GENERATOR_ASSERTION_OPS
from common.rules import load_rule


def _success_signature(requirement: Dict[str, object]) -> str:
    vuln = str((requirement or {}).get("vuln_id") or "").strip().lower()
    rule = load_rule(vuln)
    signature = rule.get("success_signature") if isinstance(rule, dict) else None
    if isinstance(signature, str) and signature.strip():
        return signature.strip()
    return "Exploit SUCCESS"


def _semantic_contract(requirement: Dict[str, object]) -> str:
    vuln = str((requirement or {}).get("vuln_id") or "").strip().lower().replace("_", "-")
    if vuln == "89":
        vuln = "cwe-89"
    if vuln == "352":
        vuln = "cwe-352"
    if vuln == "cwe89":
        vuln = "cwe-89"
    if vuln == "cwe352":
        vuln = "cwe-352"
    if vuln == "cwe-89":
        return (
            "- CWE-89: include a real SQL injection path.\n"
            "- MUST read user input from request args/form/json, compose SQL by string concat/interpolation, and execute that composed query.\n"
            "- MUST NOT use parameterized placeholders for the intentionally vulnerable query path."
        )
    if vuln == "cwe-352":
        return (
            "- CWE-352: include a real CSRF path.\n"
            "- MUST have a state-changing endpoint (POST/PUT/DELETE/PATCH) behind session/cookie auth.\n"
            "- MUST omit CSRF token and Origin/Referer validation on the vulnerable endpoint."
        )
    return "- Keep generated code semantically aligned with vuln_id (input vector, sink, exploit precondition)."


def build_generator_prompt(
    requirement: Dict[str, object],
    rag_context: str,
    *,
    failure_context: str = "",
) -> List[Dict[str, str]]:
    """Return chat-style messages for the Generator agent."""

    system = (
        "You are the Generator agent inside an autonomous vulnerability testbed. "
        "Follow the contracts described in docs/handbook.md (아키텍처). "
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
    researcher_report: str = "",
    failure_context: str = "",
    limits: Optional[Dict[str, object]] = None,
    candidate_index: int = 1,
    poc_template: Optional[Dict[str, object]] = None,
    guard_spec: str = "",
) -> List[Dict[str, str]]:
    """Prompt that asks the LLM to emit a manifest for synthesis mode."""

    system = (
        "You synthesize intentionally vulnerable Docker bundles for education. "
        "Follow docs/handbook.md (아키텍처/스키마) and produce ONLY compact JSON "
        "matching the generator_manifest section."
    )
    requirement_payload = json.dumps(requirement, indent=2, ensure_ascii=False)
    limits_payload = json.dumps(limits or {}, indent=2, ensure_ascii=False)
    success_signature = _success_signature(requirement)
    semantic_contract = _semantic_contract(requirement)
    if guard_spec:
        semantic_contract = (
            "- Primary semantic contract is defined by Guard Spec semantic_signature.\n"
            "- Generated code and PoC must satisfy Guard Spec generator_assertions without contradiction."
        )
    execution_constraints = (
        "- Container is executed with `--read-only` and `/tmp` is mounted as tmpfs (writable). "
        "`/tmp` starts EMPTY on every container run and masks anything written to `/tmp` at image build time. "
        "Do NOT create stateful artifacts under `/tmp` during Docker build expecting them at runtime. "
        "Instead, keep schema/seed files under `/app` and initialize runtime state under `/tmp` when the service starts.\n"
        "- Do NOT rely on external OS binaries at runtime (ex: `sqlite3`, `psql`, `mysql`, `curl`). "
        "Prefer pure language libraries. If an OS binary is truly required, install it in the Dockerfile "
        "at build time and keep it (do not purge it if used at runtime).\n"
        "- If your service uses SQLite and performs writes (INSERT/UPDATE/DELETE), the DB file path MUST be under `/tmp` "
        "(ex: `APP_DB_PATH=os.environ.get('APP_DB_PATH', '/tmp/app.db')`). "
        "If the DB is under `/tmp`, you MUST initialize tables/seed data at service startup (schema.sql -> creates tables).\n"
        "- The service MUST bind to `0.0.0.0` and listen on the declared port (default 5000)."
    )
    supported_ops = ", ".join(sorted(SUPPORTED_GENERATOR_ASSERTION_OPS))
    sections = [
        "Synthesize candidate #{idx} for the request below. The manifest must be JSON "
        "and contain files[], deps[], build, run, poc, notes, pattern_tags[]. "
        "Respect the file/path limits verbatim and do not add standard library modules (e.g., logging, sqlite3) to deps[]. "
        "When a Researcher Report is provided, prefer it over guessing (endpoints, exploit steps, success markers). "
        "Each files[] entry SHOULD also include a role field (for example: 'service_main', 'poc_entry', 'helper', 'schema', 'seed_data'), "
        "and the PoC MUST print the exact manifest.poc.success_signature string on success and exit with code 0. "
        "If a PoC Template is provided, you MUST copy its success_signature (and flag_token if present) verbatim into manifest.poc and the PoC code MUST print them on success. "
        "The PoC script SHOULD accept --base-url (default http://127.0.0.1:<port>) and optionally --payload so the executor can run it against "
        "the service inside the container."
        "If Failure Hint Payload JSON is provided, you MUST satisfy must_fix/prompt_instructions first and avoid repeating the same failure fingerprint."
        "\n\n# Execution Constraints (MUST)\n{constraints}\n\n# Requirement\n{req}\n\n# Synthesis Limits\n{limits}"
        "\n\n# Supported Guard Ops\n{supported_ops}"
        "\n\n# Vulnerability Semantics (MUST)\n{semantic_contract}"
        "\n\n# Internal Hints\n{hints}\n\n# Researcher Report (JSON)\n{researcher}"
        "\n\n# Guard Spec (JSON)\n{guard_spec}\n\n# RAG Context\n{rag}".format(
            idx=candidate_index,
            sig=success_signature,
            constraints=execution_constraints,
            req=requirement_payload,
            limits=limits_payload,
            supported_ops=supported_ops,
            semantic_contract=semantic_contract,
            hints=hints or "(none provided)",
            researcher=researcher_report or "(none provided)",
            guard_spec=guard_spec or "(none provided)",
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
        "Return JSON with any blocking issues per docs/handbook.md (아키텍처)."
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
        "You are the Researcher agent. Produce ONLY compact JSON per docs/handbook.md (researcher_report). "
        "Use ReAct-style reasoning internally but return the final JSON object without commentary."
    )
    requirement_payload = json.dumps(requirement, indent=2, ensure_ascii=False)
    search_payload = json.dumps(search_results or [], indent=2, ensure_ascii=False)
    sections = [
        "Create a researcher report JSON covering vuln_id, intent, preconditions, "
        "tech_stack_candidates, minimal_repro_steps, references, pocs, deps, risks, "
        "retrieval_snapshot_id, and optionally failure_context. "
        "Cite relevant references and align with docs/handbook.md (아키텍처). "
        "Execution constraint: the generated bundle will be executed in a container with `--read-only` and only `/tmp` writable, "
        "so prefer designs that keep runtime state under `/tmp` and avoid runtime OS binaries.\n"
        "If relevant, you MAY also include an optional verification_spec field describing success_text_markers, flag_token, and a short assertion_program. "
        "Only override repo-maintained rule contracts when necessary; if you must, set verification_spec.override_static=true."
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


def build_guard_planner_prompt(
    requirement: Dict[str, object],
    *,
    researcher_report: Dict[str, Any],
    evidence: List[Dict[str, Any]],
    policy_guard: Dict[str, Any],
    sid: str,
    slug: str,
) -> List[Dict[str, str]]:
    """Prompt for generating a bundle-level GuardSpec JSON."""

    schema_hint = {
        "schema_version": "guard_spec@1.0",
        "sid": sid,
        "vuln_id": requirement.get("vuln_id"),
        "slug": slug,
        "source": "llm",
        "policy_snapshot": policy_guard,
        "evidence_refs": [
            {
                "index": 0,
                "query": "...",
                "source": "remote|local",
                "url": "...",
                "published": "...",
                "retrieved_at": "...",
            }
        ],
        "semantic_signature": {
            "input_vector": ["..."],
            "sink": ["..."],
            "exploit_precondition": ["..."],
        },
        "generator_assertions": [
            {
                "op": "file_exists",
                "path": "app.py",
                "severity": "block|warn",
                "intent": "semantic_anchor|syntax_hint|contract|dependency",
                "stability": "high|medium|low",
                "evidence_ids": [0],
            }
        ],
        "verifier_assertions": [{"op": "contains", "string": "Exploit SUCCESS"}],
        "verifier_assertions_deferred": [],
        "autofix_hints": [{"priority": 10, "instruction": "..."}],
        "normalization": {"mapped_ops": [], "dropped_ops": [], "warnings": []},
        "confidence": "high|medium|low",
        "created_at": "ISO-8601",
    }
    system = (
        "You are a Guard Planner. Return ONLY valid JSON for guard_spec@1.0. "
        "Do not return markdown. Guard assertions must be satisfiable and non-contradictory."
    )
    payload = [
        "# Requirement",
        json.dumps(requirement, indent=2, ensure_ascii=False),
        "\n# Policy Guard",
        json.dumps(policy_guard, indent=2, ensure_ascii=False),
        "\n# Researcher Report",
        json.dumps(researcher_report, indent=2, ensure_ascii=False),
        "\n# Evidence",
        json.dumps(evidence, indent=2, ensure_ascii=False),
        "\n# Output Schema",
        json.dumps(schema_hint, indent=2, ensure_ascii=False),
        (
            "\n# Constraints\n"
            "- Keep success/flag contracts consistent with static rules when known CWE.\n"
            "- Use ONLY supported generator ops: file_exists, role_exists, file_contains, file_not_contains, "
            "file_regex_contains, file_regex_not_contains, file_regex_any, dep_declared, any_dep_declared, "
            "pattern_tag_present, manifest_field_equals, manifest_field_contains.\n"
            "- Use ONLY supported verifier ops: regex_contains, contains, not_contains, number_delta.\n"
            "- Semantics-first: assert semantic anchors first, syntax hints only as supporting checks.\n"
            "- Avoid brittle regex tied to exact payload literals or single line formatting; prefer resilient patterns.\n"
            "- For syntax-like checks use severity=warn unless the check is contract/dependency critical.\n"
            "- If confidence is low, still emit best-effort spec with explicit autofix_hints.\n"
            "- Prefer generic conditions over template-specific paths unless unavoidable."
        ),
    ]
    user = "\n".join(payload)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def build_guard_autofix_prompt(
    *,
    requirement: Dict[str, Any],
    manifest: Dict[str, Any],
    violations: List[str],
    guard_spec: Dict[str, Any],
) -> List[Dict[str, str]]:
    """Prompt that asks LLM to patch a manifest after guard violations."""

    system = (
        "You repair generator_manifest JSON. Return ONLY JSON object that keeps the vulnerability intentional "
        "while satisfying guard violations. Do not remove PoC success markers."
    )
    user = (
        "# Requirement\n"
        + json.dumps(requirement, indent=2, ensure_ascii=False)
        + "\n\n# Current Manifest\n"
        + json.dumps(manifest, indent=2, ensure_ascii=False)
        + "\n\n# Guard Violations\n"
        + json.dumps(violations, indent=2, ensure_ascii=False)
        + "\n\n# Guard Spec\n"
        + json.dumps(guard_spec, indent=2, ensure_ascii=False)
        + "\n\nReturn the patched manifest JSON only."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


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
