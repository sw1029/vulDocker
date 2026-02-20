"""CWE rule loader for generator/evaluator components."""
from __future__ import annotations

import functools
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml

RULES_ROOT = Path(__file__).resolve().parents[2] / "docs" / "evals" / "rules"
TEMPLATES_ROOT = Path(__file__).resolve().parents[2] / "workspaces" / "templates"


@dataclass
class RuleSpec:
    """Normalized rule configuration used by scenarios/verifiers.

    This is intentionally higher level than the raw YAML mapping:
    it captures policy-style switches and an optional runtime
    section carrying LLM- or pipeline-generated verification specs.
    """

    cwe: str
    version: int
    scenario_type: str
    verification_source: str
    require_flag: bool
    flag_required_mode: str
    exit_code_policy: str
    output_mode: str
    json_success_key: Optional[str]
    json_success_value: Any
    json_flag_key: Optional[str]
    llm_assist_default: bool
    assertion_budget: int
    runtime: Dict[str, Any]
    # Optional fields derived from template metadata or manifests.
    service_entry: Optional[str] = None
    poc_entry: Optional[str] = None
    template_flag_token: Optional[str] = None


def load_rule(vuln_id: str | None) -> Dict[str, Any]:
    """Load a rule mapping with runtime overrides applied (legacy API).

    Priority order:
    1) ``metadata/<SID>/runtime_rules`` entries (via ``VULD_RUNTIME_RULE_DIRS``)
    2) ``docs/evals/rules`` static entries

    This function returns the merged YAML mapping so callers that still depend
    on raw keys like ``success_signature``/``flag_token``/``patterns`` can stay
    compatible while supporting per-run overrides.
    """
    if not vuln_id:
        return {}
    signature = _runtime_signature()
    return _load_rule_cached(signature, str(vuln_id))


@functools.lru_cache(maxsize=32)
def _load_rule_cached(signature: str, vuln_id: str) -> Dict[str, Any]:
    # NOTE: signature is intentionally unused beyond cache keying.
    # It ensures runtime rule dir changes invalidate cached rule mappings.
    _ = signature
    if not vuln_id:
        return {}
    merged = _merged_rule_mapping(vuln_id)
    if not isinstance(merged, dict):
        return {}
    return merged


# Retain the public cache helpers for existing tests/tooling.
load_rule.cache_clear = _load_rule_cached.cache_clear  # type: ignore[attr-defined]
load_rule.cache_info = _load_rule_cached.cache_info  # type: ignore[attr-defined]


@functools.lru_cache(maxsize=32)
def load_static_rule(vuln_id: str | None) -> Dict[str, Any]:
    """Load a static rule mapping from ``docs/evals/rules`` only."""
    if not vuln_id:
        return {}
    filename = _normalized_filename(str(vuln_id))
    if not filename:
        return {}
    path = RULES_ROOT / f"{filename}.yaml"
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Rule file {path} must contain a mapping")
    return data


def list_rules() -> List[Dict[str, Any]]:
    """Return metadata for all available rule files (env-aware cache)."""

    signature = _runtime_signature()
    return _list_rules_cached(signature)


@functools.lru_cache(maxsize=8)
def _list_rules_cached(signature: str) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for rule_path in _iter_rule_paths():
        try:
            data = yaml.safe_load(rule_path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        rule_id = str(data.get("cwe") or rule_path.stem).strip()
        if not rule_id:
            continue
        entries.append({"id": rule_id, "path": str(rule_path), "data": data})
    return entries


# Retain the public cache helpers for existing tests/tooling.
list_rules.cache_clear = _list_rules_cached.cache_clear  # type: ignore[attr-defined]
list_rules.cache_info = _list_rules_cached.cache_info  # type: ignore[attr-defined]


def _candidate_rule_paths(filename: str) -> Iterable[Path]:
    yield RULES_ROOT / f"{filename}.yaml"
    for extra_root in _runtime_rule_dirs():
        yield extra_root / f"{filename}.yaml"


def _runtime_rule_dirs() -> List[Path]:
    env = os.environ.get("VULD_RUNTIME_RULE_DIRS") or ""
    dirs: List[Path] = []
    for raw in env.split(os.pathsep):
        raw = raw.strip()
        if not raw:
            continue
        dirs.append(Path(raw))
    return dirs


def _runtime_signature() -> str:
    roots = [str(RULES_ROOT)] + [str(path) for path in _runtime_rule_dirs()]
    allow_override = os.environ.get("VULD_ALLOW_RUNTIME_RULE_OVERRIDE_STATIC", "").strip().lower()
    return os.pathsep.join(sorted(set(roots))) + f"|allow_override={allow_override}"


def _iter_rule_paths() -> Iterable[Path]:
    seen: set[Path] = set()
    for root in [RULES_ROOT, *_runtime_rule_dirs()]:
        if not root.exists():
            continue
        for rule_path in sorted(root.glob("*.yaml")):
            if rule_path in seen:
                continue
            seen.add(rule_path)
            yield rule_path


def _normalized_filename(vuln_id: str) -> str:
    normalized = str(vuln_id).strip().lower()
    if not normalized:
        return ""
    return normalized if normalized.startswith("cwe-") else f"cwe-{normalized}"


@functools.lru_cache(maxsize=1)
def _template_index() -> Dict[str, Dict[str, Any]]:
    """Index template metadata keyed by CWE-like tags."""
    index: Dict[str, Dict[str, Any]] = {}
    root = TEMPLATES_ROOT
    if not root.exists():
        return index
    for meta_path in root.rglob("template.json"):
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        tags = data.get("tags") or []
        if not isinstance(tags, list):
            continue
        vuln_tags: List[str] = []
        for raw in tags:
            if not isinstance(raw, str):
                continue
            token = raw.strip().lower()
            if token.startswith("cwe-"):
                vuln_tags.append(token)
        if not vuln_tags:
            continue
        for key in vuln_tags:
            existing = index.get(key)
            if existing is None:
                index[key] = data
            else:
                try:
                    current_score = float(existing.get("stability_score", 0.0))
                    candidate_score = float(data.get("stability_score", 0.0))
                except Exception:
                    continue
                if candidate_score > current_score:
                    index[key] = data
    return index


def _template_metadata_for_vuln(vuln_id: str) -> Dict[str, Any]:
    filename = _normalized_filename(vuln_id)
    if not filename:
        return {}
    return _template_index().get(filename, {})


def _merged_rule_mapping(vuln_id: str) -> Dict[str, Any]:
    """Merge static/runtime rule mappings while protecting static contracts.

    Policy:
    - Unknown CWE (no static rule): runtime rule is used as-is.
    - Known CWE (static exists):
      - default: keep static contract lock.
      - runtime override_scope=assertions_only: only assertion-related fields are merged.
      - runtime override_scope=full: allowed only when
        VULD_ALLOW_RUNTIME_RULE_OVERRIDE_STATIC=true.
    """
    filename = _normalized_filename(vuln_id)
    if not filename:
        return {}
    static_rule = _load_rule_yaml(RULES_ROOT / f"{filename}.yaml")
    runtime_rule = _load_runtime_rule_yaml(filename)
    if not static_rule:
        if runtime_rule:
            runtime_rule.setdefault("origin", "runtime")
            runtime_rule.setdefault("override_scope", "none")
        return runtime_rule
    if not runtime_rule:
        static_rule.setdefault("origin", "static")
        static_rule.setdefault("override_scope", "none")
        return static_rule
    return _merge_static_and_runtime(static_rule, runtime_rule)


def _load_rule_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _load_runtime_rule_yaml(filename: str) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for root in _runtime_rule_dirs():
        payload = _load_rule_yaml(root / f"{filename}.yaml")
        if payload:
            merged.update(payload)
    return merged


def _merge_static_and_runtime(static_rule: Dict[str, Any], runtime_rule: Dict[str, Any]) -> Dict[str, Any]:
    scope = str(runtime_rule.get("override_scope") or "none").strip().lower()
    if scope not in {"none", "assertions_only", "full"}:
        scope = "none"
    allow_full_override = _env_bool("VULD_ALLOW_RUNTIME_RULE_OVERRIDE_STATIC", False)
    if scope == "full" and allow_full_override:
        merged = dict(static_rule)
        merged.update(runtime_rule)
        merged["origin"] = "runtime"
        merged["override_scope"] = "full"
        return merged
    if scope in {"assertions_only", "full"}:
        merged = dict(static_rule)
        merged = _apply_assertion_only_overrides(merged, runtime_rule)
        merged["origin"] = "runtime"
        merged["override_scope"] = "assertions_only"
        return merged
    merged = dict(static_rule)
    merged["origin"] = "static"
    merged["override_scope"] = "none"
    return merged


def _apply_assertion_only_overrides(
    static_rule: Dict[str, Any],
    runtime_rule: Dict[str, Any],
) -> Dict[str, Any]:
    merged = dict(static_rule)
    runtime_section = runtime_rule.get("runtime")
    if isinstance(runtime_section, dict):
        base_runtime = merged.get("runtime") if isinstance(merged.get("runtime"), dict) else {}
        next_runtime = dict(base_runtime)
        assertion_program = runtime_section.get("assertion_program")
        if isinstance(assertion_program, list):
            next_runtime["assertion_program"] = assertion_program
        extra_assertions = runtime_section.get("extra_assertions")
        if isinstance(extra_assertions, list):
            next_runtime["extra_assertions"] = extra_assertions
        if next_runtime:
            merged["runtime"] = next_runtime
    runtime_llm = runtime_rule.get("llm")
    if isinstance(runtime_llm, dict) and "assertion_budget" in runtime_llm:
        base_llm = merged.get("llm") if isinstance(merged.get("llm"), dict) else {}
        next_llm = dict(base_llm)
        next_llm["assertion_budget"] = runtime_llm.get("assertion_budget")
        merged["llm"] = next_llm
    return merged


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _default_rulespec(vuln_id: str) -> RuleSpec:
    return RuleSpec(
        cwe=vuln_id or "UNKNOWN",
        version=1,
        scenario_type="web-poc",
        verification_source="static",
        require_flag=False,
        flag_required_mode="none",
        exit_code_policy="zero",
        output_mode="auto",
        json_success_key=None,
        json_success_value=None,
        json_flag_key=None,
        llm_assist_default=False,
        assertion_budget=8,
        runtime={},
    )


def _adapt_legacy_rule(vuln_id: str, raw: Dict[str, Any]) -> RuleSpec:
    cwe = str(raw.get("cwe") or vuln_id or "UNKNOWN")
    output_cfg = raw.get("output") or {}
    json_cfg = output_cfg.get("json") or {}
    flag_token = str(raw.get("flag_token") or "").strip()
    strict_flag = bool(raw.get("strict_flag", False))
    require_flag = bool(flag_token)
    flag_mode = "strict" if strict_flag else "loose"
    return RuleSpec(
        cwe=cwe,
        version=int(raw.get("version", 1)),
        scenario_type=str(raw.get("scenario_type") or "web-poc"),
        verification_source=str(raw.get("verification", {}).get("source") or "static"),
        require_flag=require_flag,
        flag_required_mode=flag_mode,
        exit_code_policy=str(raw.get("verification", {}).get("exit_code") or "zero"),
        output_mode=str(output_cfg.get("format") or output_cfg.get("mode") or "auto"),
        json_success_key=json_cfg.get("success_key"),
        json_success_value=json_cfg.get("success_value"),
        json_flag_key=json_cfg.get("flag_key"),
        llm_assist_default=bool((raw.get("llm") or {}).get("assist_default", False)),
        assertion_budget=int((raw.get("llm") or {}).get("assertion_budget", 8)),
        runtime={},
    )


def _parse_v2_rulespec(vuln_id: str, raw: Dict[str, Any]) -> RuleSpec:
    cwe = str(raw.get("cwe") or vuln_id or "UNKNOWN")
    verification = raw.get("verification") or {}
    output_cfg = raw.get("output") or {}
    # v2 스키마는 docs/evals/eval_refactor_plan.md 9.2절의 예시처럼
    # output 블록에 json_* 키를 직접 두는 형태와, Researcher가 생성하는
    # runtime rule처럼 output.json 서브맵을 사용하는 형태를 모두 허용한다.
    json_cfg = output_cfg.get("json") or {}
    if not json_cfg:
        inferred: Dict[str, Any] = {}
        if "json_success_key" in output_cfg:
            inferred["success_key"] = output_cfg.get("json_success_key")
        if "json_success_value" in output_cfg:
            inferred["success_value"] = output_cfg.get("json_success_value")
        if "json_flag_key" in output_cfg:
            inferred["flag_key"] = output_cfg.get("json_flag_key")
        json_cfg = inferred
    llm_cfg = raw.get("llm") or {}
    runtime = raw.get("runtime") or {}
    return RuleSpec(
        cwe=cwe,
        version=int(raw.get("version", 2)),
        scenario_type=str(raw.get("scenario_type") or "web-poc"),
        verification_source=str(verification.get("source") or "runtime"),
        require_flag=bool(verification.get("require_flag", True)),
        flag_required_mode=str(verification.get("flag_mode") or "strict"),
        exit_code_policy=str(verification.get("exit_code") or "zero"),
        output_mode=str(output_cfg.get("mode") or output_cfg.get("format") or "auto"),
        json_success_key=json_cfg.get("success_key"),
        json_success_value=json_cfg.get("success_value"),
        json_flag_key=json_cfg.get("flag_key"),
        llm_assist_default=bool(llm_cfg.get("assist_default", True)),
        assertion_budget=int(llm_cfg.get("assertion_budget", 8)),
        runtime=runtime if isinstance(runtime, dict) else {},
    )


def _enrich_with_template_metadata(vuln_id: str, spec: RuleSpec) -> RuleSpec:
    """Populate RuleSpec with template metadata when available."""
    meta = _template_metadata_for_vuln(vuln_id)
    if not meta:
        return spec

    scenario_type = str(meta.get("scenario_type") or "").strip()
    if scenario_type:
        spec.scenario_type = scenario_type

    service_entry = meta.get("service_entry")
    if isinstance(service_entry, str) and service_entry.strip():
        if not spec.service_entry:
            spec.service_entry = service_entry.strip()

    poc_entry = meta.get("poc_entry")
    if isinstance(poc_entry, str) and poc_entry.strip():
        if not spec.poc_entry:
            spec.poc_entry = poc_entry.strip()

    flag_token = meta.get("flag_token")
    if isinstance(flag_token, str) and flag_token.strip():
        token = flag_token.strip()
        if not spec.template_flag_token:
            spec.template_flag_token = token
        runtime = spec.runtime if isinstance(spec.runtime, dict) else {}
        if not runtime.get("flag_token"):
            runtime = dict(runtime)
            runtime["flag_token"] = token
            spec.runtime = runtime
    return spec


def load_rulespec(vuln_id: str | None) -> RuleSpec:
    """Return a normalized RuleSpec for the given vuln_id.

    - merges static docs/evals/rules and runtime rule dirs
    - supports both legacy(v1) and v2 YAML schemas
    """
    if not vuln_id:
        spec = _default_rulespec("UNKNOWN")
        return _enrich_with_template_metadata("UNKNOWN", spec)
    raw = _merged_rule_mapping(vuln_id)
    if not raw:
        spec = _default_rulespec(vuln_id)
        return _enrich_with_template_metadata(vuln_id, spec)
    version = int(raw.get("version", 1))
    if version >= 2:
        spec = _parse_v2_rulespec(vuln_id, raw)
    else:
        spec = _adapt_legacy_rule(vuln_id, raw)
    return _enrich_with_template_metadata(vuln_id, spec)


__all__ = ["load_rule", "load_static_rule", "list_rules", "RuleSpec", "load_rulespec"]
