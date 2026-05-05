"""Structured prompts shared by Researcher, Generator, and Reviewer agents."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from common.guardrails import SUPPORTED_GENERATOR_ASSERTION_OPS
from common.name_only import is_name_driven_requirement
from common.rules import load_rule


def _success_signature(requirement: Dict[str, object]) -> str:
    vuln = str((requirement or {}).get("vuln_id") or "").strip().lower()
    rule = load_rule(vuln)
    signature = rule.get("success_signature") if isinstance(rule, dict) else None
    if isinstance(signature, str) and signature.strip():
        return signature.strip()
    return "Exploit SUCCESS"


def _flag_token(requirement: Dict[str, object]) -> str:
    vuln = str((requirement or {}).get("vuln_id") or "").strip().lower()
    rule = load_rule(vuln)
    token = rule.get("flag_token") if isinstance(rule, dict) else None
    if isinstance(token, str) and token.strip():
        return token.strip()
    return ""


def _structured_success_contract(requirement: Dict[str, object]) -> str:
    vuln = str((requirement or {}).get("vuln_id") or "").strip().lower()
    rule = load_rule(vuln)
    if not isinstance(rule, dict):
        return ""
    runtime = rule.get("runtime") if isinstance(rule.get("runtime"), dict) else {}
    output = rule.get("output") if isinstance(rule.get("output"), dict) else {}
    json_cfg = output.get("json") if isinstance(output.get("json"), dict) else {}
    success_key = runtime.get("json_success_key") or json_cfg.get("success_key")
    success_value = (
        runtime.get("json_success_value")
        if "json_success_value" in runtime
        else json_cfg.get("success_value")
    )
    flag_key = runtime.get("json_flag_key") or json_cfg.get("flag_key")
    if not isinstance(success_key, str) or not success_key.strip():
        return ""
    lines = [
        "- Success is determined structurally from JSON, not raw whitespace-sensitive substring matching.",
        f"- Parse the HTTP response JSON and require `{success_key}` == `{success_value!r}`.",
    ]
    if isinstance(flag_key, str) and flag_key.strip():
        lines.append(f"- If the response embeds a flag, read it from JSON key `{flag_key}`.")
    return "\n".join(lines)


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
            "- MUST NOT use parameterized placeholders for the intentionally vulnerable query path.\n"
            "- Prefer a deterministic `/search?id=` or `/login` JSON response where a classic payload such as `1 OR 1=1` or `' OR 1=1 -- ` produces an obviously exploitable result.\n"
            "- Make PoC success deterministic: either return a result count >= 2 or emit `FLAG-sqli-demo-token` whenever the injected path yields multiple rows/admin data."
        )
    if vuln == "cwe-352":
        return (
            "- CWE-352: include a real CSRF path.\n"
            "- MUST have a state-changing endpoint (POST/PUT/DELETE/PATCH) behind session/cookie auth.\n"
            "- MUST omit CSRF token and Origin/Referer validation on the vulnerable endpoint."
        )
    if vuln == "cwe-22":
        return (
            "- CWE-22: include a real path traversal path.\n"
            "- MUST read a filename/path from request input and use it in a filesystem read sink such as open(), send_file(), or send_from_directory().\n"
            "- MUST omit canonicalization+confinement checks so payloads like ../ or /etc/passwd-style targets are reachable."
        )
    if vuln == "cwe-918":
        return (
            "- CWE-918: include a real SSRF path.\n"
            "- MUST accept a user-controlled URL from request input and make a server-side HTTP fetch with it.\n"
            "- MUST omit scheme/host allowlisting and internal address protection on the vulnerable path.\n"
            "- Prefer same-container loopback SSRF: expose an internal `/metadata`-style endpoint returning `FLAG{SSRF_OK}` and make `/fetch?url=` call `requests.get(user_url)` directly.\n"
            "- Do not use `before_first_request`; Flask 3 startup/init must run explicitly before `app.run()` or behind a one-time request guard."
        )
    if vuln == "cwe-78":
        return (
            "- CWE-78: include a real command injection path.\n"
            "- MUST read user input from the request and splice it into a shell/system command.\n"
            "- MUST keep a shell-enabled execution path such as shell=True or os.system on the vulnerable route."
        )
    if vuln == "cwe-94":
        return (
            "- CWE-94: include a real code injection path.\n"
            "- MUST read attacker-controlled input and feed it into eval()/exec() or an equivalent dynamic-code sink.\n"
            "- MUST NOT sanitize or sandbox the vulnerable execution path."
        )
    if vuln == "cwe-79":
        return (
            "- CWE-79: include a real reflected XSS path.\n"
            "- MUST reflect attacker-controlled input into the HTTP response or template output.\n"
            "- MUST omit output encoding/escaping on the vulnerable reflection path."
        )
    if vuln == "cwe-502":
        return (
            "- CWE-502: include a real insecure deserialization path.\n"
            "- MUST accept attacker-controlled serialized input from the request body.\n"
            "- MUST deserialize it with an unsafe sink such as pickle.loads(), yaml.load(), or jsonpickle.decode()."
        )
    return "- Keep generated code semantically aligned with vuln_id (input vector, sink, exploit precondition)."


def _is_name_only_requirement(requirement: Dict[str, object]) -> bool:
    return is_name_driven_requirement(requirement if isinstance(requirement, dict) else {})


def _is_cve_identifier(value: object) -> bool:
    text = str(value or "").strip().lower()
    if not text.startswith("cve-"):
        return False
    parts = text.split("-")
    return len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit()


def _is_evidence_driven_open_world_requirement(requirement: Dict[str, object]) -> bool:
    req = requirement if isinstance(requirement, dict) else {}
    if _is_name_only_requirement(req):
        return True
    if _is_cve_identifier(req.get("vuln_id") or req.get("cve_id")):
        return True
    policy = req.get("policy") if isinstance(req.get("policy"), dict) else {}
    if bool(policy.get("require_researcher_evidence")):
        return True
    researcher = req.get("researcher") if isinstance(req.get("researcher"), dict) else {}
    if str(researcher.get("search_policy") or "").strip().lower() == "remote_required":
        return True
    request_ir = req.get("request_ir") if isinstance(req.get("request_ir"), dict) else {}
    required_contract = (
        request_ir.get("required_contract")
        if isinstance(request_ir.get("required_contract"), dict)
        else {}
    )
    if required_contract.get("require_research") is True or required_contract.get("require_remote_research") is True:
        return True
    if str(request_ir.get("pattern_seed_state") or "").strip().lower() == "genericized_unknown":
        return True
    return False


def _has_researcher_report_payload(researcher_report: str) -> bool:
    text = str(researcher_report or "").strip()
    return bool(text and text != "(none provided)")


def _parse_researcher_report_payload(researcher_report: str) -> Dict[str, Any]:
    text = str(researcher_report or "").strip()
    if not text or text == "(none provided)":
        return {}
    try:
        payload = json.loads(text)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _runtime_recipe_contract(requirement: Dict[str, object]) -> str:
    req = requirement if isinstance(requirement, dict) else {}
    runtime_recipe = req.get("runtime_recipe") if isinstance(req.get("runtime_recipe"), dict) else {}
    runtime = req.get("runtime") if isinstance(req.get("runtime"), dict) else {}
    executor = req.get("executor") if isinstance(req.get("executor"), dict) else {}
    service_port = runtime_recipe.get("service_port")
    if not isinstance(service_port, int):
        runtime_port = runtime.get("service_port")
        service_port = runtime_port if isinstance(runtime_port, int) else None
    db = str(runtime_recipe.get("db") or runtime.get("db") or runtime.get("database") or "none").strip().lower() or "none"
    language = str(runtime_recipe.get("language") or req.get("language") or "").strip().lower()
    framework = str(runtime_recipe.get("framework") or req.get("framework") or "").strip().lower()
    stack_locked = bool(runtime_recipe.get("stack_locked")) or bool(req.get("language") and req.get("framework"))
    raw_hypotheses = runtime_recipe.get("stack_hypotheses") if isinstance(runtime_recipe.get("stack_hypotheses"), list) else req.get("stack_hypotheses")
    stack_hypotheses: List[str] = []
    if isinstance(raw_hypotheses, list):
        for entry in raw_hypotheses:
            if not isinstance(entry, dict):
                continue
            cand_language = str(entry.get("language") or "").strip().lower()
            cand_framework = str(entry.get("framework") or "").strip().lower()
            if not cand_language or not cand_framework:
                continue
            source = str(entry.get("source") or "").strip().lower() or "unknown"
            confidence = str(entry.get("confidence") or "").strip().lower() or "unknown"
            stack_hypotheses.append(f"{cand_language}/{cand_framework} ({source}, {confidence})")
    topology = str(runtime_recipe.get("topology") or "").strip().lower()
    if not topology:
        sidecars = executor.get("sidecars") if isinstance(executor.get("sidecars"), list) else []
        topology = "service_plus_sidecar" if sidecars else "single_service"
    network_mode = (
        str(runtime_recipe.get("network_mode") or executor.get("network_mode") or "none").strip().lower() or "none"
    )
    raw_sidecars = runtime_recipe.get("sidecars") if isinstance(runtime_recipe.get("sidecars"), list) else executor.get("sidecars")
    sidecar_labels: List[str] = []
    if isinstance(raw_sidecars, list):
        for entry in raw_sidecars:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name") or "").strip()
            sidecar_type = str(entry.get("type") or "").strip()
            if name and sidecar_type:
                sidecar_labels.append(f"{name}:{sidecar_type}")
            elif name:
                sidecar_labels.append(name)
            elif sidecar_type:
                sidecar_labels.append(sidecar_type)
    sidecar_text = ", ".join(sidecar_labels) if sidecar_labels else "none"
    stack_line = ""
    if language and framework and stack_locked:
        stack_line = f"- Preferred stack: `{language}/{framework}`."
    elif language and framework:
        stack_line = f"- Current top stack hypothesis: `{language}/{framework}` (not locked)."
    else:
        stack_line = "- Stack is not fixed yet; prefer the lightest viable stack only when evidence supports it."
    lines = [
        stack_line,
        f"- Preferred topology: `{topology}`.",
        f"- Runtime DB expectation: `{db}`.",
        f"- Network mode expectation: `{network_mode}`.",
        f"- Sidecars: `{sidecar_text}`.",
    ]
    if stack_hypotheses:
        lines.append("- Ordered stack hypotheses: `" + "`, `".join(stack_hypotheses) + "`.")
    if service_port:
        lines.append(f"- Service must bind the declared app port: `{service_port}`.")
    return "\n".join(lines)


def _generation_posture_contract(
    requirement: Dict[str, object],
    *,
    researcher_report: str,
    guard_spec: str,
) -> str:
    lines: List[str] = []
    if _is_name_only_requirement(requirement):
        lines.extend(
            [
                "- Treat this as name-driven/open-world synthesis, not as proof that a built-in family template exists.",
                "- Do not import repo-specific demo routes, parameter names, or sinks unless Guard Spec or Researcher evidence requires them.",
                "- If evidence is weak, prefer a minimal topology over family-specific flourish.",
            ]
        )
    elif _is_evidence_driven_open_world_requirement(requirement):
        lines.extend(
            [
                "- Treat this as evidence-driven/open-world synthesis for an explicit vulnerability identifier, not as proof that a built-in family template exists.",
                "- Do not assume CWE-family semantics from the identifier alone; use Researcher evidence, Guard Spec, and RAG snippets for input vector, sink, topology, and oracle details.",
                "- If evidence is weak or contradictory, prefer a minimal topology and surface the uncertainty in manifest notes.",
            ]
        )
    else:
        lines.append("- Treat this as a known-family regression lane unless Researcher/Guard data contradicts it.")
    if _has_researcher_report_payload(researcher_report):
        lines.append("- Researcher Report overrides static priors for route naming, topology, and exploit flow details.")
    if guard_spec:
        lines.append("- Guard Spec is the authority for semantic anchors and must override repo-internal heuristics on conflict.")
    return "\n".join(lines)


def _family_hypothesis_contract(researcher_report: str) -> str:
    payload = _parse_researcher_report_payload(researcher_report)
    summary = payload.get("family_hypothesis_summary") if isinstance(payload.get("family_hypothesis_summary"), dict) else {}
    if not isinstance(summary, dict) or not summary:
        return "- No researcher family hypothesis summary was provided."
    top_family = str(summary.get("top_family") or "").strip()
    top_confidence = str(summary.get("top_confidence") or "").strip().lower()
    contradiction_count = int(summary.get("contradiction_count") or 0) if isinstance(summary.get("contradiction_count"), (int, float)) else 0
    contradictory_families = [
        str(item).strip()
        for item in summary.get("contradictory_families") or []
        if isinstance(item, str) and str(item).strip()
    ] if isinstance(summary.get("contradictory_families"), list) else []
    top_margin = summary.get("top_margin")
    ambiguous = summary.get("ambiguous") is True

    lines: List[str] = []
    if top_family:
        lines.append(
            f"- Researcher top family hypothesis: `{top_family}` (confidence: `{top_confidence or 'unknown'}`)."
        )
    if top_margin is not None:
        lines.append(f"- Researcher top-family margin: `{top_margin}`.")
    if contradiction_count:
        lines.append(
            f"- Family hypothesis is ambiguous: `{contradiction_count}` contradictory family candidates"
            + (f" (`{', '.join(contradictory_families)}`)." if contradictory_families else ".")
        )
        lines.append("- When ambiguous, prefer minimal topology and avoid overcommitting to family-specific sinks unless Guard Spec or evidence is explicit.")
    elif top_family:
        lines.append("- Use the top family only as a working hypothesis; do not copy repo demo structure unless evidence requires it.")
    if ambiguous and not contradiction_count:
        lines.append("- Family hypothesis margin is weak; keep the implementation minimal and evidence-driven.")
    return "\n".join(lines) if lines else "- No researcher family hypothesis summary was provided."


def _researcher_evidence_contract(researcher_report: str) -> str:
    payload = _parse_researcher_report_payload(researcher_report)
    evidence = payload.get("evidence") if isinstance(payload.get("evidence"), list) else []
    summary = payload.get("evidence_type_summary") if isinstance(payload.get("evidence_type_summary"), dict) else {}
    lines: List[str] = []
    if isinstance(summary, dict) and summary:
        hit_count = summary.get("hit_count")
        matched_target_count = summary.get("matched_target_count")
        by_type = summary.get("by_type") if isinstance(summary.get("by_type"), dict) else {}
        by_authority = summary.get("by_source_authority") if isinstance(summary.get("by_source_authority"), dict) else {}
        detail: List[str] = []
        if isinstance(hit_count, int):
            detail.append(f"hit_count=`{hit_count}`")
        if isinstance(matched_target_count, int):
            detail.append(f"matched_target_count=`{matched_target_count}`")
        if by_type:
            compact = ",".join(
                f"{str(key).strip().lower()}:{int(value)}"
                for key, value in by_type.items()
                if str(key).strip() and isinstance(value, (int, float))
            )
            if compact:
                detail.append(f"by_type=`{compact}`")
        if by_authority:
            compact = ",".join(
                f"{str(key).strip().lower()}:{int(value)}"
                for key, value in by_authority.items()
                if str(key).strip() and isinstance(value, (int, float))
            )
            if compact:
                detail.append(f"by_authority=`{compact}`")
        if detail:
            lines.append("- Evidence summary: " + ", ".join(detail) + ".")
    for index, item in enumerate(evidence[:6], start=1):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        evidence_type = str(item.get("evidence_type") or item.get("query_target") or "").strip().lower()
        authority = str(item.get("source_authority") or "").strip().lower()
        source = str(item.get("source") or "").strip().lower()
        provider = str(item.get("provider") or "").strip().lower()
        url = str(item.get("url") or "").strip()
        snippet = " ".join(str(item.get("snippet") or "").split())[:280]
        detail = [f"#{index}"]
        if evidence_type:
            detail.append(f"type=`{evidence_type}`")
        if authority:
            detail.append(f"authority=`{authority}`")
        if source:
            source_detail = source
            if provider and provider != source:
                source_detail += f"/{provider}"
            detail.append(f"source=`{source_detail}`")
        if title:
            detail.append(f"title=`{title[:120]}`")
        if url:
            detail.append(f"url=`{url[:180]}`")
        if snippet:
            detail.append(f"snippet=`{snippet}`")
        lines.append("- Evidence " + ", ".join(detail) + ".")
    if lines:
        lines.append("- Use these evidence snippets as RAG context for endpoint shape, vulnerable version cues, exploit preconditions, and oracle details.")
        return "\n".join(lines)
    return "- No structured researcher evidence was provided."


def _exploit_oracle_contract(requirement: Dict[str, object]) -> str:
    req = requirement if isinstance(requirement, dict) else {}
    oracle = req.get("exploit_oracle") if isinstance(req.get("exploit_oracle"), dict) else {}
    if not isinstance(oracle, dict) or not oracle:
        return "- No structured exploit oracle was provided."
    lines: List[str] = []
    source = str(oracle.get("source") or "").strip()
    if source:
        lines.append(f"- Oracle source: `{source}`.")
    success_signature = str(oracle.get("success_signature") or "").strip()
    if success_signature:
        lines.append(f"- Success signature: `{success_signature}`.")
    flag_token = str(oracle.get("flag_token") or "").strip()
    if flag_token:
        lines.append(f"- Flag token: `{flag_token}`.")
    success_mode = str(oracle.get("success_mode") or "").strip()
    if success_mode:
        lines.append(f"- Success mode: `{success_mode}`.")
    json_success_key = str(oracle.get("json_success_key") or "").strip()
    if json_success_key:
        lines.append(f"- JSON success key: `{json_success_key}`.")
    json_flag_key = str(oracle.get("json_flag_key") or "").strip()
    if json_flag_key:
        lines.append(f"- JSON flag key: `{json_flag_key}`.")
    negative_markers = [
        str(item).strip()
        for item in (oracle.get("negative_text_markers") or [])
        if isinstance(item, str) and str(item).strip()
    ]
    if negative_markers:
        lines.append(f"- Negative markers (must stay absent on success): `{', '.join(negative_markers)}`.")
    forbidden_markers = [
        str(item).strip()
        for item in (oracle.get("forbidden_success_markers") or [])
        if isinstance(item, str) and str(item).strip()
    ]
    if forbidden_markers:
        lines.append(f"- Forbidden success markers: `{', '.join(forbidden_markers)}`.")
    negative_controls = oracle.get("negative_controls") if isinstance(oracle.get("negative_controls"), list) else []
    if negative_controls:
        lines.append(f"- Negative control cases: `{len(negative_controls)}`.")
        runnable_negative_controls = [
            item for item in negative_controls if isinstance(item, dict) and str(item.get("payload") or "").strip()
        ]
        if runnable_negative_controls:
            lines.append(f"- Runnable negative control payloads: `{len(runnable_negative_controls)}`.")
    metamorphic = oracle.get("metamorphic") if isinstance(oracle.get("metamorphic"), dict) else {}
    if metamorphic:
        total = metamorphic.get("total")
        passed = metamorphic.get("passed")
        rationale = str(metamorphic.get("rationale") or "").strip()
        detail: List[str] = []
        if isinstance(total, int):
            detail.append(f"total=`{total}`")
        if isinstance(passed, int):
            detail.append(f"passed=`{passed}`")
        if rationale:
            detail.append(f"rationale=`{rationale}`")
        cases = metamorphic.get("cases") if isinstance(metamorphic.get("cases"), list) else []
        runnable_cases = [
            item for item in cases if isinstance(item, dict) and str(item.get("payload") or "").strip()
        ]
        if runnable_cases:
            detail.append(f"runnable_cases=`{len(runnable_cases)}`")
        if detail:
            lines.append("- Metamorphic oracle context: " + ", ".join(detail) + ".")
    poc_cmd = str(oracle.get("poc_cmd") or "").strip()
    if poc_cmd:
        lines.append(f"- Preferred PoC command: `{poc_cmd}`.")
    return "\n".join(lines) if lines else "- No structured exploit oracle was provided."


def _name_only_generation_spec_contract(requirement: Dict[str, object]) -> str:
    req = requirement if isinstance(requirement, dict) else {}
    spec = req.get("name_only_generation_spec") if isinstance(req.get("name_only_generation_spec"), dict) else {}
    if not isinstance(spec, dict) or not spec:
        return "- No name-only generation spec was provided."
    lines: List[str] = []
    request_label = str(spec.get("request_label") or "").strip()
    if request_label:
        lines.append(f"- Original request label: `{request_label}`.")
    resolved_vuln_id = str(spec.get("resolved_vuln_id") or "").strip()
    if resolved_vuln_id:
        lines.append(f"- Resolved vuln id: `{resolved_vuln_id}`.")
    request_ir = spec.get("request_ir") if isinstance(spec.get("request_ir"), dict) else {}
    if isinstance(request_ir, dict) and request_ir:
        resolution_state = str(request_ir.get("resolution_state") or "").strip()
        if resolution_state:
            lines.append(f"- Request resolution state: `{resolution_state}`.")
        pattern_seed_state = str(request_ir.get("pattern_seed_state") or "").strip()
        if pattern_seed_state:
            lines.append(f"- Pattern seed state: `{pattern_seed_state}`.")
        selection_decision = request_ir.get("selection_decision") if isinstance(request_ir.get("selection_decision"), dict) else {}
        if isinstance(selection_decision, dict) and selection_decision:
            family_decision = selection_decision.get("family") if isinstance(selection_decision.get("family"), dict) else {}
            stack_decision = selection_decision.get("stack") if isinstance(selection_decision.get("stack"), dict) else {}
            scenario_decision = selection_decision.get("scenario") if isinstance(selection_decision.get("scenario"), dict) else {}
            if family_decision.get("selected") is True:
                selected_family = str(family_decision.get("selected_family") or family_decision.get("top_family") or "").strip()
                detail: List[str] = []
                if selected_family:
                    detail.append(f"family=`{selected_family}`")
                support_count = family_decision.get("support_count")
                if isinstance(support_count, int):
                    detail.append(f"support_count=`{support_count}`")
                support_by_authority = family_decision.get("support_by_source_authority")
                if isinstance(support_by_authority, dict) and support_by_authority:
                    compact = ",".join(
                        f"{str(key).strip().lower()}:{int(value)}"
                        for key, value in support_by_authority.items()
                        if str(key).strip()
                    )
                    if compact:
                        detail.append(f"support_authority=`{compact}`")
                if detail:
                    lines.append("- Request IR selected family: " + ", ".join(detail) + ".")
            if stack_decision.get("selected") is True:
                selected_stack = str(stack_decision.get("selected_stack_id") or "").strip()
                stack_basis = str(stack_decision.get("basis") or "").strip()
                stack_margin = stack_decision.get("margin")
                detail = [f"stack=`{selected_stack}`"] if selected_stack else []
                if stack_basis:
                    detail.append(f"basis=`{stack_basis}`")
                if isinstance(stack_margin, (int, float)):
                    detail.append(f"margin=`{stack_margin}`")
                support_count = stack_decision.get("support_count")
                if isinstance(support_count, int):
                    detail.append(f"support_count=`{support_count}`")
                support_by_authority = stack_decision.get("support_by_source_authority")
                if isinstance(support_by_authority, dict) and support_by_authority:
                    compact = ",".join(
                        f"{str(key).strip().lower()}:{int(value)}"
                        for key, value in support_by_authority.items()
                        if str(key).strip()
                    )
                    if compact:
                        detail.append(f"support_authority=`{compact}`")
                if detail:
                    lines.append("- Request IR selected stack: " + ", ".join(detail) + ".")
            if scenario_decision.get("selected") is True:
                detail = []
                selected_scenario = str(scenario_decision.get("selected_scenario_id") or scenario_decision.get("top_scenario_id") or "").strip()
                selected_topology = str(scenario_decision.get("selected_topology") or scenario_decision.get("topology") or "").strip()
                selected_oracle_mode = str(
                    scenario_decision.get("selected_oracle_mode") or scenario_decision.get("top_oracle_mode") or ""
                ).strip()
                selected_oracle_source = str(
                    scenario_decision.get("selected_oracle_source") or scenario_decision.get("top_oracle_source") or ""
                ).strip()
                if selected_scenario:
                    detail.append(f"scenario=`{selected_scenario}`")
                if selected_topology:
                    detail.append(f"topology=`{selected_topology}`")
                if selected_oracle_mode:
                    oracle_detail = f"oracle_mode=`{selected_oracle_mode}`"
                    if selected_oracle_source:
                        oracle_detail += f" ({selected_oracle_source})"
                    detail.append(oracle_detail)
                support_count = scenario_decision.get("support_count")
                if isinstance(support_count, int):
                    detail.append(f"support_count=`{support_count}`")
                support_by_authority = scenario_decision.get("support_by_source_authority")
                if isinstance(support_by_authority, dict) and support_by_authority:
                    compact = ",".join(
                        f"{str(key).strip().lower()}:{int(value)}"
                        for key, value in support_by_authority.items()
                        if str(key).strip()
                    )
                    if compact:
                        detail.append(f"support_authority=`{compact}`")
                if detail:
                    lines.append("- Request IR selected scenario: " + ", ".join(detail) + ".")
    identifier_candidate_summary = (
        spec.get("identifier_candidate_summary")
        if isinstance(spec.get("identifier_candidate_summary"), dict)
        else {}
    )
    if isinstance(identifier_candidate_summary, dict) and identifier_candidate_summary:
        candidate_count = identifier_candidate_summary.get("candidate_count")
        resolved_candidate = str(identifier_candidate_summary.get("resolved_vuln_id_candidate") or "").strip()
        abstain_reason = str(identifier_candidate_summary.get("abstain_reason") or "").strip()
        detail: List[str] = []
        if isinstance(candidate_count, int):
            detail.append(f"count=`{candidate_count}`")
        if resolved_candidate:
            detail.append(f"resolved_candidate=`{resolved_candidate}`")
        if abstain_reason:
            detail.append(f"abstain_reason=`{abstain_reason}`")
        if detail:
            lines.append("- Identifier candidate preview: " + ", ".join(detail) + ".")
    effective_mode = str(spec.get("effective_mode") or "").strip()
    if effective_mode:
        lines.append(f"- Name-only effective mode: `{effective_mode}`.")
    working_family = str(spec.get("family_working_hypothesis") or "").strip()
    working_family_source = str(spec.get("family_hypothesis_source") or "").strip()
    if working_family:
        source_text = f" ({working_family_source})" if working_family_source else ""
        lines.append(f"- Working family hypothesis: `{working_family}`{source_text}.")
    family_candidate_summary = (
        spec.get("family_candidate_summary")
        if isinstance(spec.get("family_candidate_summary"), dict)
        else {}
    )
    if isinstance(family_candidate_summary, dict) and family_candidate_summary:
        top_family = str(family_candidate_summary.get("top_family") or "").strip()
        top_source = str(family_candidate_summary.get("top_source") or "").strip()
        top_confidence = str(family_candidate_summary.get("top_confidence") or "").strip()
        candidate_count = family_candidate_summary.get("candidate_count")
        material_candidate_count = family_candidate_summary.get("material_candidate_count")
        deprioritized_candidate_count = family_candidate_summary.get("deprioritized_candidate_count")
        if top_family:
            detail = [f"top=`{top_family}`"]
            if top_source:
                detail.append(f"source=`{top_source}`")
            if top_confidence:
                detail.append(f"confidence=`{top_confidence}`")
            if isinstance(candidate_count, int):
                detail.append(f"count=`{candidate_count}`")
            if isinstance(material_candidate_count, int):
                detail.append(f"material_count=`{material_candidate_count}`")
            selection_support_count = family_candidate_summary.get("selection_support_count")
            if isinstance(selection_support_count, int):
                detail.append(f"selected_support_count=`{selection_support_count}`")
            lines.append("- Family candidate preview: " + ", ".join(detail) + ".")
        if isinstance(deprioritized_candidate_count, int) and deprioritized_candidate_count > 0:
            lines.append(
                f"- Low-confidence/background family candidates were deprioritized: `{deprioritized_candidate_count}`."
            )
        if family_candidate_summary.get("ambiguous") is True:
            lines.append("- Family candidate set is ambiguous; avoid overcommitting beyond supported family evidence.")
    negative_hypotheses = spec.get("negative_hypotheses") if isinstance(spec.get("negative_hypotheses"), list) else []
    if negative_hypotheses:
        normalized = [
            str(item.get("family") or "").strip()
            for item in negative_hypotheses
            if isinstance(item, dict) and str(item.get("family") or "").strip()
        ]
        if normalized:
            lines.append("- Negative family hypotheses: `" + "`, `".join(normalized) + "`.")
    provisional_family = str(spec.get("provisional_family") or "").strip()
    if provisional_family:
        lines.append(f"- Provisional family hypothesis remains open: `{provisional_family}`.")
    primitive_hypotheses = spec.get("primitive_hypotheses") if isinstance(spec.get("primitive_hypotheses"), list) else []
    if primitive_hypotheses:
        preview = []
        for item in primitive_hypotheses[:3]:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind") or "").strip()
            value = str(item.get("value") or "").strip()
            if kind and value:
                preview.append(f"{kind}:{value}")
        if preview:
            lines.append("- Primitive hypothesis preview: `" + "`, `".join(preview) + "`.")
    runtime_dependency_hypotheses = (
        spec.get("runtime_dependency_hypotheses")
        if isinstance(spec.get("runtime_dependency_hypotheses"), list)
        else {}
    )
    if isinstance(runtime_dependency_hypotheses, list) and runtime_dependency_hypotheses:
        preview = []
        for item in runtime_dependency_hypotheses[:3]:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind") or "").strip()
            value = str(item.get("value") or "").strip()
            if kind and value:
                preview.append(f"{kind}:{value}")
        if preview:
            lines.append("- Runtime dependency hypotheses: `" + "`, `".join(preview) + "`.")
    oracle_hypotheses = spec.get("oracle_hypotheses") if isinstance(spec.get("oracle_hypotheses"), list) else []
    if oracle_hypotheses:
        preview = []
        for item in oracle_hypotheses[:3]:
            if not isinstance(item, dict):
                continue
            mode = str(item.get("mode") or "").strip()
            source = str(item.get("source") or "").strip()
            confidence = str(item.get("confidence") or "").strip()
            if not mode:
                continue
            detail = mode
            if source or confidence:
                suffix = ", ".join(part for part in (source, confidence) if part)
                detail = f"{detail} ({suffix})"
            preview.append(detail)
        if preview:
            lines.append("- Oracle hypotheses: `" + "`, `".join(preview) + "`.")
    topology_hypotheses = spec.get("topology_hypotheses") if isinstance(spec.get("topology_hypotheses"), list) else []
    if topology_hypotheses:
        preview = []
        for item in topology_hypotheses[:3]:
            if not isinstance(item, dict):
                continue
            topology = str(item.get("topology") or "").strip()
            source = str(item.get("source") or "").strip()
            confidence = str(item.get("confidence") or "").strip()
            if not topology:
                continue
            detail = topology
            if source or confidence:
                suffix = ", ".join(part for part in (source, confidence) if part)
                detail = f"{detail} ({suffix})"
            preview.append(detail)
        if preview:
            lines.append("- Topology hypotheses: `" + "`, `".join(preview) + "`.")
    scenario_candidate_summary = (
        spec.get("scenario_candidate_summary")
        if isinstance(spec.get("scenario_candidate_summary"), dict)
        else {}
    )
    if isinstance(scenario_candidate_summary, dict) and scenario_candidate_summary:
        detail = []
        candidate_count = scenario_candidate_summary.get("candidate_count")
        selected_candidate_count = scenario_candidate_summary.get("selected_candidate_count")
        evidence_backed_candidate_count = scenario_candidate_summary.get("evidence_backed_candidate_count")
        if isinstance(candidate_count, int):
            detail.append(f"count=`{candidate_count}`")
        if isinstance(selected_candidate_count, int):
            detail.append(f"selected_count=`{selected_candidate_count}`")
        if isinstance(evidence_backed_candidate_count, int):
            detail.append(f"evidence_backed_count=`{evidence_backed_candidate_count}`")
        top_scenario_id = str(scenario_candidate_summary.get("top_scenario_id") or "").strip()
        if top_scenario_id:
            detail.append(f"top=`{top_scenario_id}`")
        top_oracle_mode = str(scenario_candidate_summary.get("top_oracle_mode") or "").strip()
        if top_oracle_mode:
            detail.append(f"top_oracle=`{top_oracle_mode}`")
        selected_scenario_id = str(scenario_candidate_summary.get("selected_scenario_id") or "").strip()
        if selected_scenario_id:
            detail.append(f"selected=`{selected_scenario_id}`")
        selected_oracle_mode = str(scenario_candidate_summary.get("selected_oracle_mode") or "").strip()
        if selected_oracle_mode:
            detail.append(f"selected_oracle=`{selected_oracle_mode}`")
        if detail:
            lines.append("- Scenario candidate preview: " + ", ".join(detail) + ".")
    runtime_recipe_summary = (
        spec.get("runtime_recipe_summary")
        if isinstance(spec.get("runtime_recipe_summary"), dict)
        else {}
    )
    if isinstance(runtime_recipe_summary, dict) and runtime_recipe_summary:
        language = str(runtime_recipe_summary.get("language") or "").strip()
        framework = str(runtime_recipe_summary.get("framework") or "").strip()
        topology = str(runtime_recipe_summary.get("topology") or "").strip()
        stack_defaulted = runtime_recipe_summary.get("stack_defaulted")
        if language and framework:
            lines.append(f"- Runtime working stack: `{language}/{framework}`.")
        if topology:
            lines.append(f"- Runtime working topology: `{topology}`.")
        if stack_defaulted is True:
            lines.append("- Runtime stack remains repo-prior/defaulted and is not evidence-backed yet.")
        stack_selection = runtime_recipe_summary.get("stack_selection") if isinstance(runtime_recipe_summary.get("stack_selection"), dict) else {}
        if isinstance(stack_selection, dict) and stack_selection.get("resolved") is True:
            detail: List[str] = []
            selected_stack_id = str(stack_selection.get("selected_stack_id") or "").strip()
            if selected_stack_id:
                detail.append(f"selected=`{selected_stack_id}`")
            confidence = str(stack_selection.get("confidence") or "").strip()
            if confidence:
                detail.append(f"confidence=`{confidence}`")
            margin = stack_selection.get("margin")
            if isinstance(margin, (int, float)):
                detail.append(f"margin=`{margin}`")
            basis = str(stack_selection.get("basis") or "").strip()
            if basis:
                detail.append(f"basis=`{basis}`")
            if detail:
                lines.append("- Runtime stack selection: " + ", ".join(detail) + ".")
    stack_candidate_summary = (
        spec.get("stack_candidate_summary")
        if isinstance(spec.get("stack_candidate_summary"), dict)
        else {}
    )
    if isinstance(stack_candidate_summary, dict) and stack_candidate_summary:
        working_stack_id = str(stack_candidate_summary.get("working_stack_id") or "").strip()
        working_stack_source = str(stack_candidate_summary.get("working_stack_source") or "").strip()
        working_stack_locked = stack_candidate_summary.get("working_stack_locked")
        working_stack_defaulted = stack_candidate_summary.get("working_stack_defaulted")
        candidate_count = stack_candidate_summary.get("candidate_count")
        top_stack_id = str(stack_candidate_summary.get("top_stack_id") or "").strip()
        top_source = str(stack_candidate_summary.get("top_source") or "").strip()
        top_confidence = str(stack_candidate_summary.get("top_confidence") or "").strip()
        detail: List[str] = []
        if working_stack_id:
            detail.append(f"working=`{working_stack_id}`")
        if working_stack_source:
            detail.append(f"source=`{working_stack_source}`")
        if isinstance(working_stack_locked, bool):
            detail.append(f"locked=`{working_stack_locked}`")
        if isinstance(working_stack_defaulted, bool):
            detail.append(f"defaulted=`{working_stack_defaulted}`")
        if isinstance(candidate_count, int):
            detail.append(f"count=`{candidate_count}`")
        if top_stack_id and top_stack_id != working_stack_id:
            detail.append(f"top_candidate=`{top_stack_id}`")
        if top_source and top_source != working_stack_source:
            detail.append(f"top_source=`{top_source}`")
        if top_confidence:
            detail.append(f"top_confidence=`{top_confidence}`")
        if detail:
            lines.append("- Stack candidate preview: " + ", ".join(detail) + ".")
        selection_support_count = stack_candidate_summary.get("selection_support_count")
        if isinstance(selection_support_count, int):
            lines.append(f"- Selected stack support count: `{selection_support_count}`.")
        if stack_candidate_summary.get("ambiguous") is True:
            lines.append("- Stack candidates remain ambiguous; stay within bounded repo-supported stacks unless stronger evidence is present.")
    runtime_graph_summary = (
        spec.get("runtime_graph_summary")
        if isinstance(spec.get("runtime_graph_summary"), dict)
        else {}
    )
    if isinstance(runtime_graph_summary, dict) and runtime_graph_summary:
        topology = str(runtime_graph_summary.get("topology") or "").strip()
        node_count = runtime_graph_summary.get("node_count")
        edge_count = runtime_graph_summary.get("edge_count")
        sidecars = runtime_graph_summary.get("sidecars") if isinstance(runtime_graph_summary.get("sidecars"), list) else []
        if topology:
            lines.append(f"- Runtime graph topology preview: `{topology}`.")
        if isinstance(node_count, int) and isinstance(edge_count, int):
            lines.append(f"- Runtime graph preview: `{node_count}` node(s), `{edge_count}` edge(s).")
        if sidecars:
            lines.append("- Runtime graph sidecars: `" + "`, `".join(str(item) for item in sidecars) + "`.")
    executor_plan = req.get("executor_plan") if isinstance(req.get("executor_plan"), dict) else {}
    if isinstance(executor_plan, dict) and executor_plan:
        detail: List[str] = []
        service_port = executor_plan.get("service_port")
        if isinstance(service_port, int):
            detail.append(f"service_port=`{service_port}`")
        health_path = str(executor_plan.get("health_path") or "").strip()
        if health_path:
            detail.append(f"health_path=`{health_path}`")
        topology = str(executor_plan.get("topology") or "").strip()
        if topology:
            detail.append(f"topology=`{topology}`")
        if detail:
            lines.append("- Executor plan preview: " + ", ".join(detail) + ".")
    evidence_graph_summary = (
        spec.get("evidence_graph_summary")
        if isinstance(spec.get("evidence_graph_summary"), dict)
        else {}
    )
    if isinstance(evidence_graph_summary, dict) and evidence_graph_summary:
        node_count = evidence_graph_summary.get("node_count")
        edge_count = evidence_graph_summary.get("edge_count")
        source = str(evidence_graph_summary.get("source") or "").strip()
        if isinstance(node_count, int) and isinstance(edge_count, int):
            prefix = f"- Evidence graph preview: `{node_count}` node(s), `{edge_count}` edge(s)"
            if source:
                prefix += f", source=`{source}`"
            lines.append(prefix + ".")
    required_contract = spec.get("required_contract") if isinstance(spec.get("required_contract"), dict) else {}
    if isinstance(required_contract, dict) and required_contract:
        required_bits: List[str] = []
        for key in (
            "require_research",
            "require_remote_research",
            "allow_degraded_fallback",
            "allow_lower_bound_recovery",
            "require_independent_verifier",
            "require_live_llm",
        ):
            if key in required_contract:
                required_bits.append(f"{key}={bool(required_contract.get(key))}")
        if required_bits:
            lines.append("- Name-only execution contract: `" + "`, `".join(required_bits) + "`.")
    planning_focus_summary = (
        spec.get("planning_focus_summary")
        if isinstance(spec.get("planning_focus_summary"), dict)
        else {}
    )
    if isinstance(planning_focus_summary, dict) and planning_focus_summary:
        primary_focus = str(planning_focus_summary.get("primary_focus") or "").strip()
        if primary_focus:
            lines.append(f"- Planning primary focus: `{primary_focus}`.")
        by_focus = planning_focus_summary.get("by_focus") if isinstance(planning_focus_summary.get("by_focus"), dict) else {}
        focus_lines: List[str] = []
        for focus in planning_focus_summary.get("focuses") or []:
            token = str(focus or "").strip()
            if not token:
                continue
            reasons = by_focus.get(token) if isinstance(by_focus, dict) else []
            normalized_reasons = [
                str(item).strip()
                for item in reasons
                if isinstance(item, str) and str(item).strip()
            ]
            if normalized_reasons:
                focus_lines.append(f"{token}=[{', '.join(normalized_reasons)}]")
            else:
                focus_lines.append(token)
        if focus_lines:
            lines.append("- Planning focus breakdown: `" + "`, `".join(focus_lines) + "`.")
        lines.append("- Use the planning focus order before claiming open-world success; resolve earlier focus items first.")
    return "\n".join(lines) if lines else "- No name-only generation spec was provided."


def _staged_synthesis_contract(requirement: Dict[str, object]) -> str:
    req = requirement if isinstance(requirement, dict) else {}
    staged = req.get("staged_synthesis") if isinstance(req.get("staged_synthesis"), dict) else {}
    if not isinstance(staged, dict) or not staged:
        return "- No staged synthesis control-plane was provided."
    lines: List[str] = []
    stage_order = staged.get("stage_order") if isinstance(staged.get("stage_order"), list) else []
    if stage_order:
        normalized = [str(item).strip() for item in stage_order if isinstance(item, str) and str(item).strip()]
        if normalized:
            lines.append("- Stage order: `" + "`, `".join(normalized) + "`.")
    candidate_resolution = staged.get("candidate_resolution") if isinstance(staged.get("candidate_resolution"), dict) else {}
    if candidate_resolution:
        detail: List[str] = []
        for key in (
            "request_label",
            "resolved_vuln_id",
            "effective_mode",
            "selected_family",
            "selected_stack_id",
            "selected_topology",
            "selected_oracle_mode",
            "selected_oracle_source",
        ):
            value = str(candidate_resolution.get(key) or "").strip()
            if value:
                detail.append(f"{key}=`{value}`")
        for key in ("ready_for_materialization", "open_world_evidence_ready"):
            if key in candidate_resolution:
                detail.append(f"{key}=`{bool(candidate_resolution.get(key))}`")
        if detail:
            lines.append("- Candidate resolution: " + ", ".join(detail) + ".")
    design_brief = staged.get("design_brief") if isinstance(staged.get("design_brief"), dict) else {}
    if design_brief:
        detail = []
        for key in (
            "working_family",
            "selected_scenario_id",
            "selected_topology",
            "selected_oracle_mode",
            "selected_oracle_source",
            "primary_focus",
        ):
            value = str(design_brief.get(key) or "").strip()
            if value:
                detail.append(f"{key}=`{value}`")
        focuses = design_brief.get("focuses") if isinstance(design_brief.get("focuses"), list) else []
        normalized_focuses = [str(item).strip() for item in focuses if isinstance(item, str) and str(item).strip()]
        if normalized_focuses:
            detail.append("focuses=`" + ",".join(normalized_focuses) + "`")
        dependency_set = design_brief.get("dependency_set") if isinstance(design_brief.get("dependency_set"), list) else []
        normalized_dependencies = [
            str(item).strip() for item in dependency_set if isinstance(item, str) and str(item).strip()
        ]
        if normalized_dependencies:
            detail.append("dependency_set=`" + ",".join(normalized_dependencies) + "`")
        required_roles = design_brief.get("required_roles") if isinstance(design_brief.get("required_roles"), list) else []
        normalized_roles = [str(item).strip() for item in required_roles if isinstance(item, str) and str(item).strip()]
        if normalized_roles:
            detail.append("required_roles=`" + ",".join(normalized_roles) + "`")
        if detail:
            lines.append("- Design brief: " + ", ".join(detail) + ".")
    runtime_plan = staged.get("runtime_plan") if isinstance(staged.get("runtime_plan"), dict) else {}
    if runtime_plan:
        detail = []
        for key in ("stack_id", "topology", "topology_source", "network_mode", "db", "db_source", "executor_health_path"):
            value = str(runtime_plan.get(key) or "").strip()
            if value:
                detail.append(f"{key}=`{value}`")
        service_port = runtime_plan.get("service_port")
        if isinstance(service_port, int):
            detail.append(f"service_port=`{service_port}`")
        sidecars = runtime_plan.get("sidecars") if isinstance(runtime_plan.get("sidecars"), list) else []
        compact_sidecars = []
        for item in sidecars:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("type") or "").strip()
            if name:
                compact_sidecars.append(name)
        if compact_sidecars:
            detail.append("sidecars=`" + ",".join(compact_sidecars) + "`")
        if detail:
            lines.append("- Runtime plan: " + ", ".join(detail) + ".")
    oracle_contract = staged.get("oracle_contract") if isinstance(staged.get("oracle_contract"), dict) else {}
    if oracle_contract:
        detail = []
        for key in ("success_signature", "flag_token", "output_mode", "source", "mode", "confidence"):
            value = str(oracle_contract.get(key) or "").strip()
            if value:
                detail.append(f"{key}=`{value}`")
        for key in ("negative_control_present", "metamorphic_present"):
            if key in oracle_contract:
                detail.append(f"{key}=`{bool(oracle_contract.get(key))}`")
        if detail:
            lines.append("- Oracle contract: " + ", ".join(detail) + ".")
    return "\n".join(lines) if lines else "- No staged synthesis control-plane was provided."


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
    flag_token = _flag_token(requirement)
    structured_success = _structured_success_contract(requirement)
    semantic_contract = _semantic_contract(requirement)
    runtime_recipe_contract = _runtime_recipe_contract(requirement)
    generation_posture = _generation_posture_contract(
        requirement,
        researcher_report=researcher_report,
        guard_spec=guard_spec,
    )
    family_hypothesis_contract = _family_hypothesis_contract(researcher_report)
    researcher_evidence_contract = _researcher_evidence_contract(researcher_report)
    exploit_oracle_contract = _exploit_oracle_contract(requirement)
    name_only_generation_spec_contract = _name_only_generation_spec_contract(requirement)
    staged_synthesis_contract = _staged_synthesis_contract(requirement)
    if guard_spec:
        semantic_contract = (
            "- Primary semantic contract is defined by Guard Spec semantic_signature.\n"
            "- Generated code and PoC must satisfy Guard Spec generator_assertions without contradiction."
        )
    elif _is_evidence_driven_open_world_requirement(requirement):
        semantic_contract = (
            "- Primary semantic contract should come from Researcher Report, structured evidence, and RAG snippets.\n"
            "- If the requirement only provides a name, CVE, or unsupported explicit identifier, avoid inventing extra family-specific semantics beyond the available evidence; this is especially important for CVE or unsupported explicit identifiers."
        )
    contract_block = (
        f"- Success signature: `{success_signature}`\n"
        + (f"- Flag token: `{flag_token}`\n" if flag_token else "- Flag token: none\n")
        + "- The PoC and runtime evidence must use these exact values."
    )
    if structured_success:
        contract_block += "\n" + structured_success
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
        "If a flag token is defined below, the PoC MUST also print that exact token on success. "
        "If a PoC Template is provided, you MUST copy its success_signature (and flag_token if present) verbatim into manifest.poc and the PoC code MUST print them on success. "
        "The PoC script SHOULD accept --base-url (default http://127.0.0.1:<port>) and optionally --payload so the executor can run it against "
        "the service inside the container."
        "If Failure Hint Payload JSON is provided, you MUST satisfy must_fix/prompt_instructions first and avoid repeating the same failure fingerprint."
        "\n\n# Execution Constraints (MUST)\n{constraints}\n\n# Requirement\n{req}\n\n# Synthesis Limits\n{limits}"
        "\n\n# Resolved Contract (MUST)\n{contract_block}"
        "\n\n# Runtime Recipe (Prefer over guessing)\n{runtime_recipe_contract}"
        "\n\n# Name-Only Generation Spec\n{name_only_generation_spec_contract}"
        "\n\n# Staged Synthesis Control-Plane\n{staged_synthesis_contract}"
        "\n\n# Exploit Oracle\n{exploit_oracle_contract}"
        "\n\n# Generation Posture\n{generation_posture}"
        "\n\n# Researcher Family Hypothesis\n{family_hypothesis_contract}"
        "\n\n# Researcher Evidence\n{researcher_evidence_contract}"
        "\n\n# Supported Guard Ops\n{supported_ops}"
        "\n\n# Vulnerability Semantics (MUST)\n{semantic_contract}"
        "\n\n# Internal Hints\n{hints}\n\n# Researcher Report (JSON)\n{researcher}"
        "\n\n# Guard Spec (JSON)\n{guard_spec}\n\n# RAG Context\n{rag}".format(
            idx=candidate_index,
            sig=success_signature,
            constraints=execution_constraints,
            req=requirement_payload,
            limits=limits_payload,
            contract_block=contract_block,
            runtime_recipe_contract=runtime_recipe_contract,
            name_only_generation_spec_contract=name_only_generation_spec_contract,
            staged_synthesis_contract=staged_synthesis_contract,
            exploit_oracle_contract=exploit_oracle_contract,
            generation_posture=generation_posture,
            family_hypothesis_contract=family_hypothesis_contract,
            researcher_evidence_contract=researcher_evidence_contract,
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
            "- For generator assertions, use severity=block ONLY for role_exists, file_exists, dep_declared, "
            "any_dep_declared, manifest_field_equals, manifest_field_contains.\n"
            "- All regex/content/pattern generator assertions are advisory and MUST use severity=warn.\n"
            "- `file_regex_any` MUST use `globs` (array of path globs) and `regex` (single regex string). "
            "Do NOT persist `patterns`, `path`, `glob`, or `paths` for that op.\n"
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
