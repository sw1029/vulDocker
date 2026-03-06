"""Rule-driven PoC verifier fallback/utility."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from common.contracts import load_generator_contract as load_resolved_contract
from common.guardrails import GuardEngine, load_guard_spec_for_sid
from common.rules import RuleSpec, load_rule, load_rulespec
from common.vuln_semantics import evaluate_manifest_semantics, evaluate_workspace_semantics, semantic_error_summary

DEFAULT_FLAG_MARKER = "FLAG"
REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSPACES_ROOT = REPO_ROOT / "workspaces"


def verify_with_rule(
    vuln_id: str,
    log_path: Path,
    *,
    requirement: Optional[Dict[str, Any]] = None,
    run_summary: Optional[Dict[str, Any]] = None,
    policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    rule = load_rule(vuln_id)
    rulespec: RuleSpec = load_rulespec(vuln_id)

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
    contract_meta = _load_generator_contract(log_path, run_summary or summary_data)
    if contract_meta:
        _apply_generator_metadata_override(rulespec, contract_meta)
    workspace_dirs = _workspace_candidates(log_path, run_summary or summary_data)
    generator_manifest = _load_generator_manifest(log_path, run_summary or summary_data)
    used_fallback_rule = False
    if not rule:
        synthetic = _rule_from_generator_manifest(vuln_id, generator_manifest)
        if synthetic:
            rule = synthetic
            used_fallback_rule = True
        else:
            return {
                "verify_pass": False,
                "evidence": f"No rule file registered for {vuln_id}",
                "log_path": str(log_path),
                "status": "unsupported",
            }

    evidence: List[str] = []
    success = False
    if used_fallback_rule:
        evidence.append("Using generator_manifest.json PoC contract as fallback rule")

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

    success, exit_evidence = _apply_exit_policy(success, summary_data, policy, rulespec)
    evidence.extend(exit_evidence)

    pattern_evidence = _evaluate_patterns(rule, workspace_dirs, generator_manifest, rulespec)
    evidence.extend(pattern_evidence)

    semantic_report = _evaluate_semantic_consistency(vuln_id, workspace_dirs, generator_manifest)
    if semantic_report.get("supported"):
        if semantic_report.get("semantic_match"):
            evidence.append("Semantic consistency check passed")
        else:
            evidence.append(f"semantic mismatch: {semantic_error_summary(semantic_report)}")

    guard_consistency = _evaluate_guard_consistency(
        vuln_id=vuln_id,
        log_text=log_text,
        workspace_dirs=workspace_dirs,
        run_summary=run_summary or summary_data,
        policy=policy,
    )
    if guard_consistency.get("required_but_missing"):
        evidence.append(str(guard_consistency.get("reason") or "dynamic guard spec missing"))
    else:
        verifier_guard = guard_consistency.get("verifier") or {}
        workspace_guard = guard_consistency.get("workspace") or {}
        violations = []
        if isinstance(verifier_guard, dict):
            violations.extend(verifier_guard.get("violations") or [])
        if isinstance(workspace_guard, dict):
            violations.extend(workspace_guard.get("violations") or [])
        if violations:
            evidence.append("guard mismatch: " + "; ".join(str(item) for item in violations))

    if not evidence:
        evidence.append("Signature missing")

    return {
        "verify_pass": success,
        "evidence": ", ".join(evidence),
        "log_path": str(log_path),
        "status": "evaluated",
        "rule": rule.get("cwe") or vuln_id,
        "semantic_consistency": semantic_report,
        "guard_consistency": guard_consistency,
    }


def _evaluate_guard_consistency(
    *,
    vuln_id: str,
    log_text: str,
    workspace_dirs: List[Path],
    run_summary: Optional[Dict[str, Any]],
    policy: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    sid = ""
    slug = ""
    if isinstance(run_summary, dict):
        sid = str(run_summary.get("sid") or "").strip()
        slug = str(run_summary.get("slug") or "").strip()
    guard_spec = load_guard_spec_for_sid(sid, slug=slug) if sid else None
    engine = GuardEngine(vuln_id, guard_spec.to_dict() if guard_spec else None)

    # Requirement/plan policy may override missing-spec behavior in edge cases.
    guard_policy = (policy or {}).get("guard") if isinstance(policy, dict) else {}
    guard_policy_explicit = isinstance(guard_policy, dict) and bool(guard_policy)
    if isinstance(guard_policy, dict) and guard_policy:
        engine.policy_snapshot.update(guard_policy)

    if not engine.available and engine.should_fail_when_missing_spec() and guard_policy_explicit:
        return {
            "available": False,
            "required_but_missing": True,
            "reason": "dynamic guard spec missing under failure_policy",
            "policy_snapshot": engine.policy_snapshot,
        }

    verifier_eval = engine.evaluate_verifier_log(log_text)
    workspace_eval = engine.evaluate_workspace(workspace_dirs)
    return {
        "available": engine.available,
        "required_but_missing": False,
        "policy_snapshot": engine.policy_snapshot,
        "verifier": verifier_eval.to_dict(),
        "workspace": workspace_eval.to_dict(),
    }


def _rule_from_generator_manifest(
    vuln_id: str,
    manifest: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Build a minimal legacy rule mapping from generator_manifest.json.

    This keeps VERIFY from ending in `unsupported` when users request new
    vulnerabilities that don't have a static rule file yet, as long as
    synthesis produced a PoC contract (success_signature/flag_token).
    """
    if not isinstance(manifest, dict):
        return None
    body = manifest.get("manifest") if isinstance(manifest.get("manifest"), dict) else manifest
    if not isinstance(body, dict):
        return None
    poc = body.get("poc")
    if not isinstance(poc, dict):
        return None
    success_signature = str(poc.get("success_signature") or "").strip()
    flag_token = str(poc.get("flag_token") or "").strip()
    if not success_signature and not flag_token:
        return None
    cwe = str(body.get("metadata", {}).get("cwe") or vuln_id or "UNKNOWN")
    strict = bool(flag_token)
    return {
        "cwe": cwe,
        "success_signature": success_signature,
        "flag_token": flag_token,
        "strict_flag": strict,
        "output": {"format": "auto"},
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
    if not strict_flag and policy and policy.get("strict_flag_default"):
        strict_flag = True

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


def _evaluate_patterns(
    rule: Dict[str, Any],
    workspace_dirs: List[Path],
    generator_manifest: Optional[Dict[str, Any]] = None,
    rulespec: Optional[RuleSpec] = None,
) -> List[str]:
    patterns = rule.get("patterns") or []
    if not patterns:
        return []

    evidence: List[str] = []
    manifest_service_entry = _manifest_role_path(generator_manifest, "service_main")
    manifest_poc_entry = _manifest_role_path(generator_manifest, "poc_entry")
    spec_service_entry = getattr(rulespec, "service_entry", None) if isinstance(rulespec, RuleSpec) else None
    spec_poc_entry = getattr(rulespec, "poc_entry", None) if isinstance(rulespec, RuleSpec) else None
    service_entry_fallback = manifest_service_entry or spec_service_entry or "app.py"
    poc_entry_fallback = manifest_poc_entry or spec_poc_entry or "poc.py"
    use_manifest_only = not workspace_dirs and generator_manifest is not None
    for entry in patterns:
        if not isinstance(entry, dict):
            continue
        ptype = str(entry.get("type") or "").strip().lower()
        needle = entry.get("contains")
        if not needle:
            continue
        needle_str = str(needle)

        if ptype == "file_contains":
            rel_path = entry.get("path")
            if not rel_path:
                continue
            if isinstance(rel_path, str) and rel_path.strip().startswith("{{") and "service_entry" in rel_path:
                # Placeholder → manifest/template 기반 service_entry 경로 또는 app.py 폴백.
                rel_path = service_entry_fallback
            if use_manifest_only:
                hit = _manifest_file_contains(generator_manifest, str(rel_path), needle_str)
            else:
                hit = _workspace_contains(workspace_dirs, str(rel_path), needle_str)
            if hit:
                evidence.append(f"{rel_path} contains '{needle_str}'")
        elif ptype == "poc_contains":
            rel_path = entry.get("path") or "poc.py"
            if isinstance(rel_path, str) and rel_path.strip().startswith("{{") and "poc_entry" in rel_path:
                # Placeholder → manifest/template 기반 poc_entry 경로 또는 poc.py 폴백.
                rel_path = poc_entry_fallback
            if use_manifest_only:
                hit = _manifest_file_contains(generator_manifest, str(rel_path), needle_str)
            else:
                hit = _workspace_contains(workspace_dirs, str(rel_path), needle_str)
            if hit:
                evidence.append(f"{rel_path} contains '{needle_str}'")
    return evidence


def _workspace_candidates(
    log_path: Path,
    run_summary: Optional[Dict[str, Any]],
) -> List[Path]:
    """Locate candidate workspace directories for a given run.log.

    Preference order:
    1) workspace_root recorded in generator_manifest.json (per-bundle when available)
    2) Conventional workspaces/<SID>/app[/<slug>] patterns (legacy behaviour)
    """
    sid = ""
    if isinstance(run_summary, dict):
        sid = str(run_summary.get("sid") or "").strip()
    if not sid:
        sid = _extract_sid_from_log(log_path)
    if not sid:
        return []

    slug = ""
    if isinstance(run_summary, dict):
        slug = str(run_summary.get("slug") or "").strip()
    if not slug:
        slug = _extract_slug_from_log(log_path)

    # Prefer an explicit workspace_root recorded by the generator, if available.
    manifest = _load_generator_manifest(log_path, run_summary)
    if isinstance(manifest, dict):
        workspace_root = manifest.get("workspace_root")
        if isinstance(workspace_root, str) and workspace_root.strip():
            root_path = Path(workspace_root).resolve()
            if root_path.is_dir():
                return [root_path]

    base = WORKSPACES_ROOT / sid
    candidates: List[Path] = []
    seen: set[Path] = set()

    def _append(path: Path) -> None:
        if path in seen:
            return
        if path.is_dir():
            seen.add(path)
            candidates.append(path)

    if slug:
        slug_variants = [
            Path(slug),
            Path("app") / slug,
            Path(slug) / "app",
            Path("app") / slug / "app",
        ]
        for variant in slug_variants:
            _append(base / variant)

    _append(base / "app")
    _append(base)
    return candidates


def _extract_sid_from_log(log_path: Path) -> str:
    parts = log_path.resolve().parts
    for idx, part in enumerate(parts):
        if part == "artifacts" and idx + 1 < len(parts):
            return parts[idx + 1]
    return ""


def _extract_slug_from_log(log_path: Path) -> str:
    parent = log_path.parent
    if parent.name != "run" and parent.parent.name == "run":
        return parent.name
    return ""


def _load_generator_manifest(
    log_path: Path,
    run_summary: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Best-effort loader for generator_manifest.json based on sid.

    This enables role/manifest-aware path resolution (예: poc_entry) during
    pattern evaluation without changing the external verify_with_rule API.
    """
    sid = ""
    if isinstance(run_summary, dict):
        sid = str(run_summary.get("sid") or "").strip()
    if not sid:
        sid = _extract_sid_from_log(log_path)
    if not sid:
        return None
    slug = ""
    if isinstance(run_summary, dict):
        slug = str(run_summary.get("slug") or "").strip()
    if not slug:
        slug = _extract_slug_from_log(log_path)

    # Prefer per-bundle metadata when running in multi-vuln mode.
    candidate_dirs: List[Path] = []
    if slug:
        candidate_dirs.append(REPO_ROOT / "metadata" / sid / "bundles" / slug)
    candidate_dirs.append(REPO_ROOT / "metadata" / sid)

    for meta_dir in candidate_dirs:
        manifest_path = meta_dir / "generator_manifest.json"
        if not manifest_path.exists():
            continue
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return None


def _load_generator_contract(
    log_path: Path,
    run_summary: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Best-effort loader for resolved/generator contract based on sid/slug."""
    sid = ""
    if isinstance(run_summary, dict):
        sid = str(run_summary.get("sid") or "").strip()
    if not sid:
        sid = _extract_sid_from_log(log_path)
    if not sid:
        return None
    slug = ""
    if isinstance(run_summary, dict):
        slug = str(run_summary.get("slug") or "").strip()
    if not slug:
        slug = _extract_slug_from_log(log_path)

    candidate_dirs: List[Path] = []
    if slug:
        candidate_dirs.append(REPO_ROOT / "metadata" / sid / "bundles" / slug)
    candidate_dirs.append(REPO_ROOT / "metadata" / sid)

    for meta_dir in candidate_dirs:
        data = load_resolved_contract(meta_dir)
        if isinstance(data, dict):
            return data
    return None


def _apply_generator_metadata_override(spec: RuleSpec, meta: Dict[str, Any]) -> None:
    """Refine RuleSpec using generator metadata (contract/template summary)."""
    scenario_type = meta.get("scenario_type")
    if isinstance(scenario_type, str) and scenario_type.strip():
        spec.scenario_type = scenario_type.strip()

    service_entry = meta.get("service_entry")
    if isinstance(service_entry, str) and service_entry.strip():
        spec.service_entry = service_entry.strip()

    poc_entry = meta.get("poc_entry")
    if isinstance(poc_entry, str) and poc_entry.strip():
        spec.poc_entry = poc_entry.strip()

    flag_token = meta.get("flag_token")
    if isinstance(flag_token, str) and flag_token.strip():
        token = flag_token.strip()
        spec.template_flag_token = token
        runtime = spec.runtime if isinstance(spec.runtime, dict) else {}
        if not runtime.get("flag_token"):
            runtime = dict(runtime)
            runtime["flag_token"] = token
            spec.runtime = runtime


def _workspace_contains(
    workspace_dirs: Iterable[Path],
    relative_path: str,
    needle: str,
) -> Optional[str]:
    rel = Path(relative_path)
    for workspace in workspace_dirs:
        candidate = workspace / rel
        if not candidate.is_file():
            continue
        text = _read_file(candidate)
        if needle in text:
            return str(candidate)
    return None


def _manifest_file_contains(
    manifest: Optional[Dict[str, Any]],
    relative_path: str,
    needle: str,
) -> bool:
    """Best-effort pattern check against generator_manifest contents."""
    if not isinstance(manifest, dict) or not relative_path or not needle:
        return False
    manifest_body = manifest.get("manifest") or manifest
    files = manifest_body.get("files") if isinstance(manifest_body, dict) else None
    if not isinstance(files, list):
        return False
    target = str(relative_path)
    for entry in files:
        if not isinstance(entry, dict):
            continue
        path = entry.get("path")
        if not isinstance(path, str):
            continue
        if path != target:
            continue
        content = entry.get("content")
        if isinstance(content, str) and needle in content:
            return True
    return False


def _manifest_role_path(manifest: Optional[Dict[str, Any]], role: str) -> Optional[str]:
    """Extract the first file path for a given role from generator_manifest."""
    if not isinstance(manifest, dict):
        return None
    manifest_body = manifest.get("manifest") or manifest
    files = manifest_body.get("files") if isinstance(manifest_body, dict) else None
    if not isinstance(files, list):
        return None
    for entry in files:
        if not isinstance(entry, dict):
            continue
        entry_role = str(entry.get("role") or "").strip().lower()
        path = entry.get("path")
        if entry_role == role and isinstance(path, str) and path:
            return path
    return None


def _read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def _apply_exit_policy(
    success: bool,
    summary: Optional[Dict[str, Any]],
    policy: Optional[Dict[str, Any]],
    rulespec: Optional[RuleSpec] = None,
) -> Tuple[bool, List[str]]:
    evidence: List[str] = []
    if not summary:
        return success, evidence
    # 정책 우선순위:
    # 1) 호출자가 명시한 policy.require_exit_code_zero
    # 2) RuleSpec.exit_code_policy == "zero" 인 경우
    # 3) 그 외에는 exit code를 무시
    require_zero = False
    if policy is not None and "require_exit_code_zero" in policy:
        require_zero = bool(policy.get("require_exit_code_zero"))
    elif isinstance(rulespec, RuleSpec):
        # RuleSpec을 사용해 기본 exit code 정책을 적용한다.
        require_zero = str(getattr(rulespec, "exit_code_policy", "") or "").lower() == "zero"
    if not require_zero:
        return success, evidence
    if require_zero and "exit_code" in summary:
        exit_code = summary.get("exit_code")
        if exit_code not in (None, 0):
            evidence.append(f"exit_code={exit_code} (expected 0)")
            return False, evidence
    return success, evidence


def _evaluate_semantic_consistency(
    vuln_id: str,
    workspace_dirs: Iterable[Path],
    generator_manifest: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if isinstance(generator_manifest, dict):
        report = evaluate_manifest_semantics(vuln_id, generator_manifest)
        if report.get("supported"):
            report["source"] = "generator_manifest"
            return report
    for workspace in workspace_dirs:
        report = evaluate_workspace_semantics(vuln_id, workspace)
        if report.get("supported"):
            report["source"] = str(workspace)
            return report
    return {
        "supported": False,
        "semantic_match": True,
        "errors": [],
        "signals": {},
        "source": None,
    }
