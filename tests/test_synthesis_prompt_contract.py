from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.prompts import build_synthesis_prompt


def _user_prompt(messages: list[dict[str, str]]) -> str:
    return messages[-1]["content"]


def test_name_only_synthesis_prompt_prefers_open_world_posture_and_runtime_recipe() -> None:
    messages = build_synthesis_prompt(
        {
            "vuln_id": "NAME-OPEN-REDIRECT",
            "language": "python",
            "framework": "fastapi",
            "runtime_recipe": {
                "language": "python",
                "framework": "fastapi",
                "topology": "service_plus_sidecar",
                "network_mode": "bridge",
                "sidecars": [{"name": "metadata", "type": "http-mock"}],
                "db": "none",
                "service_port": 8080,
            },
        },
        rag_context="",
        researcher_report='{"quality":"sufficient","minimal_repro_steps":["GET /?next=http://evil.test"]}',
    )

    prompt = _user_prompt(messages)

    assert "# Runtime Recipe (Prefer over guessing)" in prompt
    assert "Preferred stack: `python/fastapi`." in prompt
    assert "Preferred topology: `service_plus_sidecar`." in prompt
    assert "Sidecars: `metadata:http-mock`." in prompt
    assert "Treat this as name-driven/open-world synthesis" in prompt
    assert "Researcher Report overrides static priors" in prompt
    assert "avoid inventing extra family-specific semantics beyond the available evidence" in prompt
    assert "CWE-89: include a real SQL injection path." not in prompt


def test_name_only_synthesis_prompt_uses_request_ir_when_vuln_id_is_canonicalized() -> None:
    messages = build_synthesis_prompt(
        {
            "vuln_id": "CWE-79",
            "request_ir": {
                "request_label": "Reflected XSS",
                "resolved_vuln_id": "CWE-79",
                "name_driven": True,
                "resolution_state": "token_match",
            },
            "runtime_recipe": {
                "language": "python",
                "framework": "flask",
                "topology": "single_service",
                "network_mode": "none",
                "sidecars": [],
                "db": "none",
            },
        },
        rag_context="",
        researcher_report='{"quality":"sufficient"}',
    )

    prompt = _user_prompt(messages)

    assert "Treat this as name-driven/open-world synthesis" in prompt
    assert "Treat this as a known-family regression lane" not in prompt


def test_name_only_synthesis_prompt_surfaces_soft_stack_hypotheses_when_stack_is_not_locked() -> None:
    messages = build_synthesis_prompt(
        {
            "vuln_id": "NAME-OPEN-REDIRECT",
            "stack_hypotheses": [
                {"language": "python", "framework": "flask", "source": "profile_prior", "confidence": "low"},
                {"language": "python", "framework": "fastapi", "source": "available_skeleton", "confidence": "low"},
            ],
            "runtime_recipe": {
                "language": "python",
                "framework": "flask",
                "stack_source": "profile_prior",
                "stack_locked": False,
                "stack_defaulted": True,
                "stack_hypotheses": [
                    {"language": "python", "framework": "flask", "source": "profile_prior", "confidence": "low"},
                    {"language": "python", "framework": "fastapi", "source": "available_skeleton", "confidence": "low"},
                ],
                "topology": "single_service",
                "network_mode": "none",
                "sidecars": [],
                "db": "none",
            },
        },
        rag_context="",
        researcher_report='{"quality":"sufficient"}',
    )

    prompt = _user_prompt(messages)

    assert "Current top stack hypothesis: `python/flask` (not locked)." in prompt
    assert "Ordered stack hypotheses: `python/flask (profile_prior, low)`, `python/fastapi (available_skeleton, low)`." in prompt
    assert "Preferred stack:" not in prompt


def test_known_family_synthesis_prompt_keeps_family_contract() -> None:
    messages = build_synthesis_prompt(
        {
            "vuln_id": "CWE-89",
            "language": "python",
            "framework": "flask",
            "runtime": {"db": "sqlite"},
        },
        rag_context="",
    )

    prompt = _user_prompt(messages)

    assert "Treat this as a known-family regression lane" in prompt
    assert "CWE-89: include a real SQL injection path." in prompt
    assert "Preferred stack: `python/flask`." in prompt
    assert "Runtime DB expectation: `sqlite`." in prompt


def test_guard_spec_overrides_name_only_semantic_contract() -> None:
    messages = build_synthesis_prompt(
        {
            "vuln_id": "NAME-CUSTOM-THING",
            "language": "python",
            "framework": "flask",
        },
        rag_context="",
        guard_spec='{"semantic_signature":{"sink":["render_template_string"]}}',
    )

    prompt = _user_prompt(messages)

    assert "Primary semantic contract is defined by Guard Spec semantic_signature." in prompt
    assert "Guard Spec is the authority for semantic anchors" in prompt
    assert "Primary semantic contract should come from Researcher Report" not in prompt


def test_name_only_prompt_surfaces_researcher_family_hypothesis() -> None:
    messages = build_synthesis_prompt(
        {
            "vuln_id": "NAME-OPEN-REDIRECT",
            "language": "python",
            "framework": "flask",
        },
        rag_context="",
        researcher_report=(
            '{"family_hypothesis_summary":{"top_family":"open_redirect","top_confidence":"high",'
            '"contradiction_count":0,"contradictory_families":[],"top_margin":0.42,"ambiguous":false}}'
        ),
    )

    prompt = _user_prompt(messages)

    assert "# Researcher Family Hypothesis" in prompt
    assert "Researcher top family hypothesis: `open_redirect`" in prompt
    assert "Use the top family only as a working hypothesis" in prompt


def test_name_only_prompt_warns_when_family_hypothesis_is_ambiguous() -> None:
    messages = build_synthesis_prompt(
        {
            "vuln_id": "NAME-CUSTOM-THING",
            "language": "python",
            "framework": "flask",
        },
        rag_context="",
        researcher_report=(
            '{"family_hypothesis_summary":{"top_family":"template_injection","top_confidence":"low",'
            '"contradiction_count":3,"contradictory_families":["sqli","xss","ssrf"],'
            '"top_margin":0.0,"ambiguous":true}}'
        ),
    )

    prompt = _user_prompt(messages)

    assert "Family hypothesis is ambiguous" in prompt
    assert "prefer minimal topology and avoid overcommitting" in prompt


def test_name_only_prompt_surfaces_generation_spec_and_exploit_oracle() -> None:
    messages = build_synthesis_prompt(
        {
            "vuln_id": "NAME-OPEN-REDIRECT",
            "exploit_oracle": {
                "source": "researcher_verification_spec",
                "success_signature": "Exploit SUCCESS",
                "flag_token": "FLAG{OPEN_REDIRECT_OK}",
                "negative_text_markers": ["Exploit FAILED"],
                "forbidden_success_markers": ["false positive"],
                "negative_controls": [{"name": "benign-next", "expect_success": False}],
                "metamorphic": {"total": 1, "passed": 1, "rationale": "same-origin redirect stays non-exploit"},
                "poc_cmd": "python poc.py --base-url {{base_url}}",
            },
            "name_only_generation_spec": {
                "request_label": "Open Redirect",
                "resolved_vuln_id": "NAME-OPEN-REDIRECT",
                "request_ir": {
                    "resolution_state": "catalog_alias",
                    "pattern_seed_state": "preserved",
                },
                "effective_mode": "dynamic",
                "family_working_hypothesis": "open_redirect",
                "family_hypothesis_source": "request_identity",
                "family_candidate_summary": {
                    "top_family": "open_redirect",
                    "top_source": "catalog_resolution",
                    "top_confidence": "high",
                    "candidate_count": 3,
                    "material_candidate_count": 1,
                    "deprioritized_candidate_count": 2,
                    "ambiguous": False,
                },
                "negative_hypotheses": [
                    {"family": "xss", "source": "researcher_contradiction"},
                ],
                "runtime_recipe_summary": {
                    "language": "python",
                    "framework": "flask",
                    "topology": "single_service",
                    "stack_defaulted": True,
                },
                "stack_candidate_summary": {
                    "working_stack_id": "python/flask",
                    "working_stack_source": "profile_prior",
                    "working_stack_locked": False,
                    "working_stack_defaulted": True,
                    "candidate_count": 2,
                    "top_stack_id": "python/flask",
                    "top_source": "profile_prior",
                    "top_confidence": "low",
                    "ambiguous": True,
                },
                "evidence_graph_summary": {
                    "node_count": 5,
                    "edge_count": 4,
                    "by_kind": {"request": 1, "query": 2, "evidence": 1, "family_hypothesis": 1},
                    "source": "researcher_derived",
                },
                "required_contract": {
                    "require_research": True,
                    "allow_degraded_fallback": True,
                    "require_live_llm": False,
                },
                "planning_focus_summary": {
                    "primary_focus": "stack_or_runtime_design",
                    "focuses": ["stack_or_runtime_design", "evidence_authority"],
                    "by_focus": {
                        "stack_or_runtime_design": ["stack_defaulted", "stack_ambiguous"],
                        "evidence_authority": ["family_candidate_evidence_missing"],
                    },
                    "reason_tokens": [
                        "stack_defaulted",
                        "stack_ambiguous",
                        "family_candidate_evidence_missing",
                    ],
                },
            },
        },
        rag_context="",
        researcher_report='{"quality":"sufficient"}',
    )

    prompt = _user_prompt(messages)

    assert "# Name-Only Generation Spec" in prompt
    assert "Original request label: `Open Redirect`." in prompt
    assert "Request resolution state: `catalog_alias`." in prompt
    assert "Pattern seed state: `preserved`." in prompt
    assert "Working family hypothesis: `open_redirect` (request_identity)." in prompt
    assert (
        "Family candidate preview: top=`open_redirect`, source=`catalog_resolution`, confidence=`high`, "
        "count=`3`, material_count=`1`."
    ) in prompt
    assert "Low-confidence/background family candidates were deprioritized: `2`." in prompt
    assert "Negative markers (must stay absent on success): `Exploit FAILED`." in prompt
    assert "Forbidden success markers: `false positive`." in prompt
    assert "Negative control cases: `1`." in prompt
    assert "Metamorphic oracle context: total=`1`, passed=`1`, rationale=`same-origin redirect stays non-exploit`." in prompt
    assert "Negative family hypotheses: `xss`." in prompt
    assert "Runtime stack remains repo-prior/defaulted and is not evidence-backed yet." in prompt
    assert "Stack candidate preview: working=`python/flask`, source=`profile_prior`, locked=`False`, defaulted=`True`, count=`2`, top_confidence=`low`." in prompt
    assert "Stack candidates remain ambiguous; stay within bounded repo-supported stacks unless stronger evidence is present." in prompt
    assert "Evidence graph preview: `5` node(s), `4` edge(s), source=`researcher_derived`." in prompt
    assert "Planning primary focus: `stack_or_runtime_design`." in prompt
    assert (
        "Planning focus breakdown: `stack_or_runtime_design=[stack_defaulted, stack_ambiguous]`, "
        "`evidence_authority=[family_candidate_evidence_missing]`."
    ) in prompt


def test_name_only_prompt_surfaces_runtime_graph_preview() -> None:
    messages = build_synthesis_prompt(
        {
            "vuln_id": "CWE-79",
            "request_ir": {
                "request_label": "Reflected XSS",
                "resolved_vuln_id": "CWE-79",
                "name_driven": True,
                "resolution_state": "token_match",
            },
            "name_only_generation_spec": {
                "effective_mode": "dynamic",
                "family_working_hypothesis": "xss",
                "family_hypothesis_source": "researcher_family_hypothesis",
                "runtime_graph_summary": {
                    "topology": "single_service",
                    "node_count": 1,
                    "edge_count": 1,
                    "sidecars": [],
                    "network_mode": "none",
                    "target_node": "service",
                },
            },
            "runtime_recipe": {
                "language": "python",
                "framework": "flask",
                "topology": "single_service",
                "network_mode": "none",
                "sidecars": [],
                "db": "none",
            },
        },
        rag_context="",
        researcher_report='{"quality":"sufficient"}',
    )

    prompt = _user_prompt(messages)

    assert "Runtime graph topology preview: `single_service`." in prompt
    assert "Runtime graph preview: `1` node(s), `1` edge(s)." in prompt
