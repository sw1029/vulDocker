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


def test_cve_synthesis_prompt_uses_evidence_driven_open_world_posture() -> None:
    messages = build_synthesis_prompt(
        {
            "vuln_id": "CVE-2099-0001",
            "language": "python",
            "framework": "flask",
            "policy": {"require_researcher_evidence": True},
            "researcher": {"search_policy": "remote_required"},
        },
        rag_context="",
        researcher_report='{"quality":"sufficient"}',
    )

    prompt = _user_prompt(messages)

    assert "Treat this as evidence-driven/open-world synthesis for an explicit vulnerability identifier" in prompt
    assert "Do not assume CWE-family semantics from the identifier alone" in prompt
    assert "Primary semantic contract should come from Researcher Report, structured evidence, and RAG snippets." in prompt
    assert "especially important for CVE or unsupported explicit identifiers" in prompt
    assert "Treat this as a known-family regression lane" not in prompt


def test_unknown_identifier_remote_required_prompt_uses_open_world_posture() -> None:
    messages = build_synthesis_prompt(
        {
            "vuln_id": "CWE-9999",
            "language": "python",
            "framework": "flask",
            "policy": {"require_researcher_evidence": True},
            "researcher": {"search_policy": "remote_required"},
            "request_ir": {"pattern_seed_state": "genericized_unknown"},
        },
        rag_context="",
        researcher_report='{"quality":"sufficient"}',
    )

    prompt = _user_prompt(messages)

    assert "Treat this as evidence-driven/open-world synthesis for an explicit vulnerability identifier" in prompt
    assert "Treat this as a known-family regression lane" not in prompt


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


def test_synthesis_prompt_surfaces_researcher_evidence_snippets_for_cve() -> None:
    messages = build_synthesis_prompt(
        {
            "vuln_id": "CVE-2099-0001",
            "language": "python",
            "framework": "flask",
        },
        rag_context="",
        researcher_report=(
            '{"quality":"sufficient",'
            '"evidence_type_summary":{"hit_count":1,"matched_target_count":1,'
            '"by_type":{"advisory":1},"by_source_authority":{"high":1}},'
            '"evidence":[{"query":"CVE-2099-0001 NVD advisory affected versions weakness details",'
            '"query_target":"advisory","evidence_type":"advisory","source_authority":"high",'
            '"source":"local","provider":"local","title":"NVD - CVE-2099-0001",'
            '"url":"file:///tmp/rag/corpus/raw/poc/20250101/CVE-2099-0001.json",'
            '"snippet":"CVE-2099-0001 NVD advisory affected Flask endpoint uses user controlled redirect target."}]}'
        ),
    )

    prompt = _user_prompt(messages)

    assert "# Researcher Evidence" in prompt
    assert "Evidence summary: hit_count=`1`, matched_target_count=`1`, by_type=`advisory:1`, by_authority=`high:1`." in prompt
    assert "Evidence #1, type=`advisory`, authority=`high`, source=`local`" in prompt
    assert "NVD - CVE-2099-0001" in prompt
    assert "affected Flask endpoint uses user controlled redirect target" in prompt
    assert "Use these evidence snippets as RAG context" in prompt


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
                "negative_controls": [{"name": "benign-next", "expect_success": False, "payload": "/local"}],
                "metamorphic": {
                    "total": 1,
                    "passed": 1,
                    "rationale": "same-origin redirect stays non-exploit",
                    "cases": [{"name": "same-origin", "payload": "/local", "expect_success": False}],
                },
                "poc_cmd": "python poc.py --base-url {{base_url}}",
            },
            "name_only_generation_spec": {
                "request_label": "Open Redirect",
                "resolved_vuln_id": "NAME-OPEN-REDIRECT",
                "request_ir": {
                    "resolution_state": "catalog_alias",
                    "pattern_seed_state": "preserved",
                    "selection_decision": {
                        "family": {
                            "selected": True,
                            "selected_family": "open_redirect",
                            "support_count": 2,
                            "support_by_source_authority": {"high": 1, "medium": 1},
                        },
                        "stack": {
                            "selected": True,
                            "selected_stack_id": "python/flask",
                            "basis": "researcher_top_candidate",
                            "margin": 0.35,
                            "support_count": 1,
                            "support_by_source_authority": {"medium": 1},
                        },
                        "scenario": {
                            "selected": True,
                            "selected_scenario_id": "family=open_redirect|stack=python/flask|topology=single_service",
                            "selected_topology": "single_service",
                            "selected_oracle_mode": "stateful_text",
                            "selected_oracle_source": "primitive_family_inference",
                            "support_count": 1,
                            "support_by_source_authority": {"high": 1},
                        },
                        "ready_for_materialization": True,
                    },
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
                    "selection_support_count": 2,
                },
                "negative_hypotheses": [
                    {"family": "xss", "source": "researcher_contradiction"},
                ],
                "provisional_family": "open_redirect",
                "primitive_hypotheses": [
                    {"kind": "input_vector", "value": "redirect parameter", "source": "semantic_signature"},
                    {"kind": "sink", "value": "location header", "source": "semantic_signature"},
                ],
                "runtime_dependency_hypotheses": [
                    {"kind": "sidecar", "value": "http-mock", "source": "runtime_recipe", "confidence": "medium"},
                ],
                "oracle_hypotheses": [
                    {
                        "mode": "stateful_text",
                        "source": "primitive_family_inference",
                        "confidence": "low",
                        "negative_control_present": True,
                        "metamorphic_present": True,
                        "output_mode": "auto",
                    },
                ],
                "topology_hypotheses": [
                    {"topology": "single_service", "source": "runtime_recipe", "confidence": "high"},
                    {"topology": "service_plus_sidecar", "source": "runtime_feasibility", "confidence": "medium"},
                ],
                "scenario_candidate_summary": {
                    "candidate_count": 2,
                    "selected_candidate_count": 1,
                    "evidence_backed_candidate_count": 1,
                    "top_scenario_id": "family=open_redirect|stack=python/flask|topology=single_service",
                    "top_oracle_mode": "stateful_text",
                    "selected_scenario_id": "family=open_redirect|stack=python/flask|topology=single_service",
                    "selected_oracle_mode": "stateful_text",
                },
                "runtime_recipe_summary": {
                    "language": "python",
                    "framework": "flask",
                    "topology": "single_service",
                    "stack_defaulted": False,
                    "stack_selection": {
                        "resolved": True,
                        "selected_stack_id": "python/flask",
                        "confidence": "medium",
                        "margin": 0.35,
                        "basis": "researcher_top_candidate",
                    },
                },
                "stack_candidate_summary": {
                    "working_stack_id": "python/flask",
                    "working_stack_source": "researcher_candidate",
                    "working_stack_locked": False,
                    "working_stack_defaulted": False,
                    "candidate_count": 2,
                    "top_stack_id": "python/flask",
                    "top_source": "researcher_candidate",
                    "top_confidence": "medium",
                    "ambiguous": True,
                    "selection_resolved": True,
                    "selection_basis": "researcher_top_candidate",
                    "selection_margin": 0.35,
                    "selection_support_count": 1,
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
                    "primary_focus": "open_world_generation",
                    "focuses": ["open_world_generation"],
                    "by_focus": {
                        "open_world_generation": ["bounded_dynamic_generation"],
                    },
                    "reason_tokens": [
                        "bounded_dynamic_generation",
                    ],
                },
            },
            "staged_synthesis": {
                "schema_version": "staged_synthesis@0.1",
                "stage_order": [
                    "candidate_resolution",
                    "design_brief",
                    "runtime_plan",
                    "oracle_contract",
                ],
                "candidate_resolution": {
                    "request_label": "Open Redirect",
                    "resolved_vuln_id": "NAME-OPEN-REDIRECT",
                    "effective_mode": "dynamic",
                    "selected_family": "open_redirect",
                    "selected_stack_id": "python/flask",
                    "selected_topology": "single_service",
                    "selected_oracle_mode": "stateful_text",
                    "selected_oracle_source": "primitive_family_inference",
                    "ready_for_materialization": True,
                    "open_world_evidence_ready": True,
                },
                "design_brief": {
                    "working_family": "open_redirect",
                    "selected_scenario_id": "family=open_redirect|stack=python/flask|topology=single_service",
                    "selected_topology": "single_service",
                    "selected_oracle_mode": "stateful_text",
                    "selected_oracle_source": "primitive_family_inference",
                    "primary_focus": "open_world_generation",
                    "focuses": ["open_world_generation"],
                    "dependency_set": ["service", "sidecar:http-mock"],
                    "required_roles": [
                        "service_main",
                        "poc_entry",
                        "oracle_state_checks",
                        "negative_control_cases",
                        "metamorphic_cases",
                    ],
                },
                "runtime_plan": {
                    "stack_id": "python/flask",
                    "topology": "single_service",
                    "topology_source": "primitive_family_inference",
                    "network_mode": "none",
                    "db": "sqlite",
                    "db_source": "primitive_family_inference",
                    "service_port": 8000,
                    "executor_health_path": "/health",
                },
                "oracle_contract": {
                    "success_signature": "Exploit SUCCESS",
                    "flag_token": "FLAG{OPEN_REDIRECT_OK}",
                    "output_mode": "auto",
                    "source": "researcher_verification_spec",
                    "mode": "stateful_text",
                    "confidence": "low",
                    "negative_control_present": True,
                    "metamorphic_present": True,
                },
            },
            "executor_plan": {
                "service_port": 8000,
                "health_path": "/health",
                "topology": "single_service",
            },
        },
        rag_context="",
        researcher_report='{"quality":"sufficient"}',
    )

    prompt = _user_prompt(messages)

    assert "# Name-Only Generation Spec" in prompt
    assert "Original request label: `Open Redirect`." in prompt
    assert "# Staged Synthesis Control-Plane" in prompt
    assert "Request resolution state: `catalog_alias`." in prompt
    assert "Pattern seed state: `preserved`." in prompt
    assert (
        "Request IR selected family: family=`open_redirect`, support_count=`2`, support_authority=`high:1,medium:1`."
        in prompt
    )
    assert (
        "Request IR selected stack: stack=`python/flask`, basis=`researcher_top_candidate`, margin=`0.35`, "
        "support_count=`1`, support_authority=`medium:1`."
    ) in prompt
    assert (
        "Request IR selected scenario: scenario=`family=open_redirect|stack=python/flask|topology=single_service`, "
        "topology=`single_service`, oracle_mode=`stateful_text` (primitive_family_inference), support_count=`1`, support_authority=`high:1`."
    ) in prompt
    assert "Working family hypothesis: `open_redirect` (request_identity)." in prompt
    assert (
        "Family candidate preview: top=`open_redirect`, source=`catalog_resolution`, confidence=`high`, "
        "count=`3`, material_count=`1`, selected_support_count=`2`."
    ) in prompt
    assert "Low-confidence/background family candidates were deprioritized: `2`." in prompt
    assert "Negative markers (must stay absent on success): `Exploit FAILED`." in prompt
    assert "Forbidden success markers: `false positive`." in prompt
    assert "Negative control cases: `1`." in prompt
    assert "Metamorphic oracle context:" in prompt
    assert "total=`1`" in prompt
    assert "passed=`1`" in prompt
    assert "rationale=`same-origin redirect stays non-exploit`" in prompt
    assert "Runnable negative control payloads: `1`." in prompt
    assert "runnable_cases=`1`" in prompt
    assert "Negative family hypotheses: `xss`." in prompt
    assert "Provisional family hypothesis remains open: `open_redirect`." in prompt
    assert "Primitive hypothesis preview: `input_vector:redirect parameter`, `sink:location header`." in prompt
    assert "Runtime dependency hypotheses: `sidecar:http-mock`." in prompt
    assert "Oracle hypotheses: `stateful_text (primitive_family_inference, low)`." in prompt
    assert "Topology hypotheses: `single_service (runtime_recipe, high)`, `service_plus_sidecar (runtime_feasibility, medium)`." in prompt
    assert (
        "Scenario candidate preview: count=`2`, selected_count=`1`, evidence_backed_count=`1`, "
        "top=`family=open_redirect|stack=python/flask|topology=single_service`, top_oracle=`stateful_text`, "
        "selected=`family=open_redirect|stack=python/flask|topology=single_service`, selected_oracle=`stateful_text`."
    ) in prompt
    assert "Stage order: `candidate_resolution`, `design_brief`, `runtime_plan`, `oracle_contract`." in prompt
    assert (
        "Candidate resolution: request_label=`Open Redirect`, resolved_vuln_id=`NAME-OPEN-REDIRECT`, "
        "effective_mode=`dynamic`, selected_family=`open_redirect`, selected_stack_id=`python/flask`, "
        "selected_topology=`single_service`, selected_oracle_mode=`stateful_text`, selected_oracle_source=`primitive_family_inference`, "
        "ready_for_materialization=`True`, open_world_evidence_ready=`True`."
    ) in prompt
    assert (
        "Design brief: working_family=`open_redirect`, selected_scenario_id=`family=open_redirect|stack=python/flask|topology=single_service`, "
        "selected_topology=`single_service`, selected_oracle_mode=`stateful_text`, selected_oracle_source=`primitive_family_inference`, "
        "primary_focus=`open_world_generation`, focuses=`open_world_generation`, dependency_set=`service,sidecar:http-mock`, "
        "required_roles=`service_main,poc_entry,oracle_state_checks,negative_control_cases,metamorphic_cases`."
    ) in prompt
    assert (
        "Runtime plan: stack_id=`python/flask`, topology=`single_service`, topology_source=`primitive_family_inference`, "
        "network_mode=`none`, db=`sqlite`, db_source=`primitive_family_inference`, executor_health_path=`/health`, "
        "service_port=`8000`."
    ) in prompt
    assert (
        "Oracle contract: success_signature=`Exploit SUCCESS`, flag_token=`FLAG{OPEN_REDIRECT_OK}`, "
        "output_mode=`auto`, source=`researcher_verification_spec`, mode=`stateful_text`, confidence=`low`, "
        "negative_control_present=`True`, metamorphic_present=`True`."
    ) in prompt
    assert "Runtime stack remains repo-prior/defaulted and is not evidence-backed yet." not in prompt
    assert "Runtime stack selection: selected=`python/flask`, confidence=`medium`, margin=`0.35`, basis=`researcher_top_candidate`." in prompt
    assert "Stack candidate preview: working=`python/flask`, source=`researcher_candidate`, locked=`False`, defaulted=`False`, count=`2`, top_confidence=`medium`." in prompt
    assert "Selected stack support count: `1`." in prompt
    assert "Stack candidates remain ambiguous; stay within bounded repo-supported stacks unless stronger evidence is present." in prompt
    assert "Executor plan preview: service_port=`8000`, health_path=`/health`, topology=`single_service`." in prompt
    assert "Evidence graph preview: `5` node(s), `4` edge(s), source=`researcher_derived`." in prompt
    assert "Planning primary focus: `open_world_generation`." in prompt
    assert (
        "Planning focus breakdown: `open_world_generation=[bounded_dynamic_generation]`."
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
