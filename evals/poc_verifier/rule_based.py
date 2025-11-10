"""Rule-driven PoC verifier fallback/utility."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from common.rules import load_rule

DEFAULT_FLAG_MARKER = "FLAG"


def verify_with_rule(
    vuln_id: str,
    log_path: Path,
    *,
    requirement: Optional[Dict[str, Any]] = None,
    run_summary: Optional[Dict[str, Any]] = None,
    policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    rule = load_rule(vuln_id)
    if not rule:
        return {
            "verify_pass": False,
            "evidence": f"No rule file registered for {vuln_id}",
            "log_path": str(log_path),
            "status": "unsupported",
        }

    try:
        log_text = log_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise
    except Exception as exc:  # pragma: no cover - IO guard
        return {
            "verify_pass": False,
            "evidence": f"Failed to read log: {exc}",
            "log_path": str(log_path),
            "status": "log_error",
        }

    summary_data = _load_summary_data(log_path, run_summary)

    evidence: List[str] = []
    success = False

    # Structured sources first (run_summary/summary.json), then inline JSON snippets.
    struct_sources: List[Dict[str, Any]] = []
    if summary_data:
        struct_sources.append(summary_data)
    json_success = False
    if struct_sources:
        json_success, json_evidence = _evaluate_json_structs(rule, struct_sources)
        if json_success:
            success = True
            evidence.extend(json_evidence)

    if not json_success:
        text_json_success, json_evidence = _evaluate_json_text(rule, log_text)
        if text_json_success:
            success = True
            evidence.extend(json_evidence)

    if not success:
        text_success, text_evidence = _evaluate_text_markers(rule, log_text, policy)
        success = text_success
        evidence.extend(text_evidence)

    success, exit_evidence = _apply_exit_policy(success, summary_data, policy)
    evidence.extend(exit_evidence)

    if not evidence:
        evidence.append("Signature missing")

    return {
        "verify_pass": success,
        "evidence": ", ".join(evidence),
        "log_path": str(log_path),
        "status": "evaluated",
        "rule": rule.get("cwe") or vuln_id,
    }


def _evaluate_text_markers(
    rule: Dict[str, Any],
    log_text: str,
    policy: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, List[str]]:
    evidence: List[str] = []
    signature = str(rule.get("success_signature") or "").strip()
    flag_token = str(rule.get("flag_token") or "").strip()
    policy_strict = None
    if policy:
        policy_strict = policy.get("strict_flag")
    strict_flag = bool(policy_strict if policy_strict is not None else rule.get("strict_flag", False))

    signature_hit = bool(signature and signature in log_text)
    if signature_hit:
        evidence.append(f"Found signature: {signature}")

    flag_hit = _match_flag_token(flag_token, log_text, strict_flag)
    if flag_hit:
        evidence.append(f"Found flag token: {flag_token or DEFAULT_FLAG_MARKER}")

    if signature and flag_token:
        success = bool(signature_hit and flag_hit)
    elif signature:
        success = signature_hit
    elif flag_token:
        success = flag_hit
    else:
        success = False
    return success, evidence


def _match_flag_token(token: str, log_text: str, strict: bool) -> bool:
    if token:
        if strict:
            return token in log_text
        return token in log_text or DEFAULT_FLAG_MARKER in log_text
    if strict:
        return False
    return DEFAULT_FLAG_MARKER in log_text


def _evaluate_json_text(rule: Dict[str, Any], log_text: str) -> Tuple[bool, List[str]]:
    output_cfg = rule.get("output") or {}
    fmt = str(output_cfg.get("format") or "auto").strip().lower()
    if fmt not in {"json", "auto"}:
        return False, []
    objects = list(_extract_json_objects(log_text))
    return _evaluate_json_structs(rule, reversed(objects))


def _evaluate_json_structs(
    rule: Dict[str, Any], objects: Iterable[Dict[str, Any]]
) -> Tuple[bool, List[str]]:
    json_cfg = (rule.get("output") or {}).get("json") or {}
    success_key = json_cfg.get("success_key")
    success_value = json_cfg.get("success_value")
    flag_key = json_cfg.get("flag_key")
    flag_token = str(rule.get("flag_token") or "").strip()

    if not success_key and not flag_key:
        return False, []

    for obj in objects:
        success_hit, evidence = _evaluate_json_object(obj, success_key, success_value, flag_key, flag_token)
        if success_hit:
            return True, evidence
    return False, []


def _evaluate_json_object(
    obj: Dict[str, Any],
    success_key: Optional[str],
    success_value: Any,
    flag_key: Optional[str],
    flag_token: str,
) -> Tuple[bool, List[str]]:
    evidence: List[str] = []
    success_hit = _json_success_match(obj, success_key, success_value)
    if success_key and not success_hit:
        return False, []
    if success_hit and success_key:
        evidence.append(f"JSON {success_key}={obj.get(success_key)!r}")

    flag_hit = _json_flag_match(obj, flag_key, flag_token)
    if flag_key and not flag_hit:
        return False, []
    if flag_key and flag_hit:
        evidence.append(f"JSON {flag_key} matched")

    if evidence:
        return True, evidence
    return False, []


def _json_success_match(obj: Dict[str, Any], key: Optional[str], expected: Any) -> bool:
    if not key:
        return False
    if key not in obj:
        return False
    if expected is None:
        return bool(obj.get(key))
    return obj.get(key) == expected


def _json_flag_match(obj: Dict[str, Any], key: Optional[str], token: str) -> bool:
    if not key:
        return False
    if key not in obj:
        return False
    if token:
        return obj.get(key) == token
    value = obj.get(key)
    if isinstance(value, str):
        return DEFAULT_FLAG_MARKER in value
    return bool(value)


def _extract_json_objects(text: str) -> Iterable[Dict[str, Any]]:
    objects: List[Dict[str, Any]] = []
    depth = 0
    start: Optional[int] = None
    for index, char in enumerate(text):
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            if depth == 0:
                continue
            depth -= 1
            if depth == 0 and start is not None:
                snippet = text[start : index + 1]
                try:
                    obj = json.loads(snippet)
                except json.JSONDecodeError:
                    start = None
                    continue
                objects.append(obj)
                start = None
    return objects


def _load_summary_data(
    log_path: Path, run_summary: Optional[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    if isinstance(run_summary, dict) and run_summary:
        return run_summary
    summary_path = log_path.with_name("summary.json")
    if summary_path.exists():
        try:
            data = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        if isinstance(data, dict):
            return data
    return None


def _apply_exit_policy(
    success: bool,
    summary: Optional[Dict[str, Any]],
    policy: Optional[Dict[str, Any]],
) -> Tuple[bool, List[str]]:
    evidence: List[str] = []
    if not summary or not policy:
        return success, evidence
    require_zero = policy.get("require_exit_code_zero")
    if require_zero and "exit_code" in summary:
        exit_code = summary.get("exit_code")
        if exit_code not in (None, 0):
            evidence.append(f"exit_code={exit_code} (expected 0)")
            return False, evidence
    return success, evidence
