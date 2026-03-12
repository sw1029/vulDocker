"""End-to-end pipeline runner with iterative loops.

This runner closes the gap between GENERATE-only loops and real-world failures
that happen in EXECUTE/VERIFY. It uses LoopController + Reflexion memories so
that later synthesis attempts can incorporate concrete failure context.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.contracts import (
    build_generator_contract,
    can_resolve_without_remote_research_for_requirement,
    executor_feasibility_summary,
    load_semantic_profile,
    lower_bound_summary,
    requires_semantic_support,
    requires_semantic_support_for_requirement,
    write_generator_contract,
)
from common.bundle_state import collect_bundle_research_blockers
from common.config import get_openai_api_key
from common.llm.provider import litellm_completion
from common.logging import get_logger
from common.name_only import build_name_only_contract, is_name_driven_requirement, name_only_mode
from common.paths import ensure_dir, get_artifacts_dir, get_metadata_dir, get_workspace_dir
from common.plan import load_plan
from common.runtime_assets import (
    GENERATED_RUNTIME_ASSETS_FILENAME,
    RUNTIME_ASSET_SEEDS_FILENAME,
    has_runtime_asset_seed_manifest,
    purge_runtime_asset_dirs,
    remove_generated_runtime_assets,
    restore_seeded_runtime_assets,
)
from common.run_matrix import bundle_requirement, load_vuln_bundles, metadata_dir_for_bundle
from orchestrator.loop_controller import LoopController
from agents.researcher.service import ResearcherService
from rag.tools import WebSearchTool

LOGGER = get_logger(__name__)


def _python_cmd(*args: str) -> List[str]:
    return [sys.executable, *args]


def _load_json(path: Path) -> Dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _tail_text(path: Path, limit_chars: int = 2200) -> str:
    if limit_chars <= 0 or not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return ""
    if not text:
        return ""
    return text[-limit_chars:]


def _research_failure_details(plan: Dict[str, Any], rc: int) -> Tuple[str, str, Dict[str, Any]]:
    default_reason = f"Researcher failed with exit code {rc}"
    default_fix_hint = "Check LLM provider configuration / API key / network connectivity."
    bundles = load_vuln_bundles(plan)
    for bundle in bundles:
        metadata_dir = metadata_dir_for_bundle(plan, bundle)
        report = _load_json(metadata_dir / "researcher_report.json") or {}
        if not isinstance(report, dict):
            continue
        quality = str(report.get("quality") or "").strip().lower()
        quality_reason = str(report.get("quality_reason") or "").strip()
        search_health_path = report.get("search_health_path")
        metadata: Dict[str, Any] = {
            "exit_code": rc,
            "bundle_slug": bundle.slug,
            "vuln_id": bundle.vuln_id,
        }
        if isinstance(search_health_path, str) and search_health_path.strip():
            metadata["search_health_path"] = search_health_path.strip()
            health = _load_json(Path(search_health_path.strip()))
            if isinstance(health, dict):
                provider = str(health.get("provider") or "").strip()
                last_error = str(health.get("last_error") or "").strip()
                configured = bool(health.get("configured"))
                degraded = bool(health.get("degraded"))
                remote_result_count = int(health.get("remote_result_count") or 0)
                metadata["search_configured"] = configured
                if degraded:
                    metadata["search_degraded"] = degraded
                metadata["remote_result_count"] = remote_result_count
                if provider:
                    metadata["search_provider"] = provider
                if last_error:
                    metadata["search_error"] = last_error
        if quality == "insufficient" and quality_reason:
            terminal_failure_class = "research_insufficient"
            retry_recommended = False
            if metadata.get("search_degraded") is True:
                terminal_failure_class = "provider_degraded"
            elif metadata.get("search_configured") is False:
                terminal_failure_class = "remote_provider_unavailable"
            elif "low relevance score" in quality_reason.lower():
                terminal_failure_class = "evidence_low_relevance"
            elif "remote_required" in quality_reason or "remote provenance is required" in quality_reason:
                terminal_failure_class = "remote_evidence_missing"
            metadata["terminal_failure_class"] = terminal_failure_class
            metadata["retry_recommended"] = retry_recommended
            if "remote_required" in quality_reason or "remote provenance is required" in quality_reason:
                fix_hint = "Configure the remote search provider or relax researcher.search_policy / policy.require_researcher_evidence."
            elif "low relevance score" in quality_reason.lower():
                fix_hint = "Improve evidence quality or lower the researcher evidence threshold for this lane."
            else:
                fix_hint = "Review researcher evidence policy and provider configuration for this lane."
            return quality_reason, fix_hint, metadata
    return default_reason, default_fix_hint, {"exit_code": rc}


def _should_retry_research_failure(metadata: Dict[str, Any]) -> bool:
    if not isinstance(metadata, dict):
        return True
    if metadata.get("retry_recommended") is False:
        return False
    terminal_failure_class = str(metadata.get("terminal_failure_class") or "").strip().lower()
    if terminal_failure_class in {
        "semantic_support_missing",
        "remote_provider_unavailable",
        "remote_evidence_missing",
        "evidence_low_relevance",
        "provider_degraded",
        "research_insufficient",
    }:
        return False
    return True


def _bundle_scoped_research_failure_metadata(plan: Dict[str, Any]) -> Dict[str, Any]:
    blockers = collect_bundle_research_blockers(plan)
    if not blockers:
        return {}
    bundles = load_vuln_bundles(plan)
    failed = {
        str(item.get("bundle_slug") or "").strip()
        for item in blockers
        if str(item.get("bundle_slug") or "").strip()
    }
    runnable_bundles = [bundle for bundle in bundles if bundle.slug not in failed]
    return {
        "failed_bundles": blockers,
        "runnable_bundles": [bundle.slug for bundle in runnable_bundles],
        "continue_pipeline": bool(runnable_bundles),
    }


def _latest_generator_failure(sid: str) -> Dict[str, Any] | None:
    records = _load_generator_failure_records(sid, limit=1)
    if not records:
        return None
    return records[0]


def _guard_policy(plan: Dict[str, Any]) -> Dict[str, Any]:
    policy = plan.get("policy") if isinstance(plan, dict) else {}
    if not isinstance(policy, dict):
        return {}
    guard = policy.get("guard")
    if isinstance(guard, dict):
        return guard
    return {}


def _int_guard_policy(guard: Dict[str, Any], key: str, default: int) -> int:
    try:
        value = int(guard.get(key, default))
    except Exception:
        value = default
    if value < 1:
        return default
    return value


def _generator_failure_paths(sid: str) -> List[Path]:
    root = get_metadata_dir(sid)
    paths: List[Path] = [root / "generator_failures.jsonl"]
    bundles_dir = root / "bundles"
    if bundles_dir.exists():
        paths.extend(sorted(bundles_dir.glob("*/generator_failures.jsonl")))
    return paths


def _load_generator_failure_records(sid: str, limit: int | None = None) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for path in _generator_failure_paths(sid):
        if not path.exists():
            continue
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        for line in lines:
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            key = json.dumps(
                {
                    "timestamp": payload.get("timestamp", ""),
                    "reason": payload.get("reason", ""),
                    "guard_error_code": payload.get("guard_error_code", ""),
                    "guard_error_subcode": payload.get("guard_error_subcode", ""),
                    "failure_fingerprint": payload.get("failure_fingerprint", ""),
                    "vuln_id": payload.get("vuln_id", ""),
                    "slug": payload.get("slug", ""),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            if key in seen:
                continue
            seen.add(key)
            payload["_failure_path"] = str(path)
            records.append(payload)
    records.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
    if limit is not None:
        return records[: max(0, limit)]
    return records


def _failure_fingerprint_repeats(
    sid: str,
    fingerprint: str,
    *,
    window: int,
    vuln_id: str = "",
    slug: str = "",
) -> int:
    token = str(fingerprint or "").strip()
    if not token:
        return 0
    records = _load_generator_failure_records(sid, limit=window)
    count = 0
    target_vuln_id = str(vuln_id or "").strip().upper()
    target_slug = str(slug or "").strip().lower()
    for record in records:
        if str(record.get("failure_fingerprint") or "").strip() != token:
            continue
        if target_vuln_id:
            record_vuln_id = str(record.get("vuln_id") or "").strip().upper()
            if record_vuln_id and record_vuln_id != target_vuln_id:
                continue
        if target_slug:
            record_slug = str(record.get("slug") or "").strip().lower()
            if record_slug and record_slug != target_slug:
                continue
        count += 1
    return count


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _refresh_researcher_on_dsl_error(plan: Dict[str, Any], failure: Dict[str, Any] | None) -> bool:
    if not isinstance(failure, dict):
        return False
    code = str(failure.get("guard_error_code") or "").strip().lower()
    if code != "guard_dsl_unsupported_op":
        return False
    guard = _guard_policy(plan)
    refresh_value = guard.get("refresh_researcher_on_guard_dsl_error") if isinstance(guard, dict) else None
    if refresh_value is None:
        return True
    return _as_bool(refresh_value)


def _refresh_researcher_for_guard_failure(
    plan: Dict[str, Any],
    sid: str,
    failure: Dict[str, Any] | None,
) -> Tuple[bool, str]:
    if not isinstance(failure, dict):
        return False, ""
    guard = _guard_policy(plan)
    code = str(failure.get("guard_error_code") or "").strip().lower()
    fingerprint = str(failure.get("failure_fingerprint") or "").strip()
    failure_vuln_id = str(failure.get("vuln_id") or "").strip()
    failure_slug = str(failure.get("slug") or "").strip()
    window = _int_guard_policy(guard, "failure_fingerprint_window", 3)
    repeat_count = (
        _failure_fingerprint_repeats(
            sid,
            fingerprint,
            window=window,
            vuln_id=failure_vuln_id,
            slug=failure_slug,
        )
        if fingerprint
        else 1
    )

    hint_payload_enabled = _as_bool(guard.get("hint_payload_enabled", True))
    if hint_payload_enabled:
        hint_payload = failure.get("hint_payload")
        if isinstance(hint_payload, dict):
            next_action = hint_payload.get("next_action")
            if isinstance(next_action, dict) and _as_bool(next_action.get("researcher_refresh")):
                rationale = str(next_action.get("rationale") or "hint payload requested researcher refresh").strip()
                return True, rationale

    if code == "guard_dsl_unsupported_op":
        should_refresh = _refresh_researcher_on_dsl_error(plan, failure)
        reason = "guard DSL unsupported op" if should_refresh else ""
        return should_refresh, reason
    if code == "guard_assertion_schema_error":
        if repeat_count >= 2:
            return True, f"guard assertion schema mismatch repeated ({repeat_count})"
        return False, ""
    if code == "guard_semantic_mismatch":
        threshold = _int_guard_policy(guard, "semantic_refresh_threshold", 2)
        if repeat_count >= threshold:
            return True, f"guard semantic mismatch repeated ({repeat_count}/{threshold})"
        return False, ""
    if code == "guard_dependency_missing":
        if repeat_count >= 2:
            return True, f"guard dependency mismatch repeated ({repeat_count})"
        return False, ""
    return False, ""


def _generator_terminal_failure_class(failure: Dict[str, Any] | None) -> str:
    if not isinstance(failure, dict):
        return ""
    code = str(failure.get("guard_error_code") or "").strip().lower()
    mapping = {
        "guard_semantic_mismatch": "guard_semantic_mismatch",
        "guard_assertion_schema_error": "guard_assertion_schema_error",
        "guard_dsl_unsupported_op": "guard_dsl_unsupported_op",
        "guard_dependency_missing": "guard_dependency_missing",
    }
    return mapping.get(code, "")


def _record_deferred_refresh(
    sid: str,
    *,
    reason: str,
    planned_next_action: Dict[str, Any] | None = None,
) -> None:
    loop_state_path = get_metadata_dir(sid) / "loop_state.json"
    state = _load_json(loop_state_path)
    if not isinstance(state, dict):
        return
    history = state.get("history")
    if not isinstance(history, list) or not history:
        return
    last = history[-1]
    if not isinstance(last, dict):
        return
    metadata = last.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    metadata["refresh_deferred_due_to_loop_limit"] = True
    metadata["planned_next_action"] = planned_next_action or {
        "retry_stage": "RESEARCH",
        "researcher_refresh": True,
        "rationale": reason,
    }
    if reason:
        metadata["deferred_reason"] = reason
    last["metadata"] = metadata
    history[-1] = last
    state["history"] = history
    _write_json(loop_state_path, state)


def _subprocess_env_for_sid(sid: str = "") -> Dict[str, str] | None:
    if not sid:
        return None
    failure_class = _pipeline_llm_failure_class(sid)
    if failure_class not in {"quota_exhausted", "auth_failure"}:
        return None
    try:
        plan = load_plan(sid)
    except Exception:
        plan = {}
    if _strict_name_only_live_llm_required(plan if isinstance(plan, dict) else {}):
        return None
    env = dict(os.environ)
    env["VUL_FORCE_LLM_STUB"] = "1"
    env["VUL_FORCE_LLM_STUB_REASON"] = failure_class
    return env


def _run_step(cmd: List[str], *, sid: str = "") -> int:
    LOGGER.info("Running command: %s", " ".join(cmd))
    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        check=False,
        env=_subprocess_env_for_sid(sid),
    )
    return int(proc.returncode or 0)


def _run_step_timed(cmd: List[str], *, sid: str = "") -> Tuple[int, float]:
    started = time.perf_counter()
    rc = _run_step(cmd, sid=sid)
    return rc, max(0.0, time.perf_counter() - started)


def _researcher_force_run(plan: Dict[str, Any]) -> bool:
    requirement = plan.get("requirement") or {}
    if not isinstance(requirement, dict):
        return False
    researcher_cfg = requirement.get("researcher") or {}
    if not isinstance(researcher_cfg, dict):
        return False
    value = researcher_cfg.get("force_run")
    if value is None:
        return False
    return _as_bool(value)


def _researcher_shadow_mode(plan: Dict[str, Any]) -> bool:
    requirement = plan.get("requirement") or {}
    if not isinstance(requirement, dict):
        return False
    researcher_cfg = requirement.get("researcher") or {}
    if not isinstance(researcher_cfg, dict):
        return False
    value = researcher_cfg.get("shadow_mode")
    if value is None:
        return False
    return _as_bool(value)


def _name_only_contract(plan: Dict[str, Any]) -> Dict[str, Any]:
    policy = plan.get("policy") if isinstance(plan, dict) else {}
    if isinstance(policy, dict):
        contract = policy.get("name_only_contract")
        if isinstance(contract, dict):
            return contract
    requirement = plan.get("requirement") if isinstance(plan, dict) else {}
    return build_name_only_contract(requirement=requirement, policy=policy)


def _name_only_mode(plan: Dict[str, Any]) -> str:
    return name_only_mode(plan if isinstance(plan, dict) else {})


def _open_world_strict_mode(plan: Dict[str, Any]) -> bool:
    policy = plan.get("policy") or {}
    if not isinstance(policy, dict):
        return False
    value = policy.get("open_world_strict")
    if value is None:
        return False
    return _as_bool(value)


def _dynamic_eval_mode(plan: Dict[str, Any]) -> bool:
    policy = plan.get("policy") or {}
    if not isinstance(policy, dict):
        return False
    value = policy.get("dynamic_eval")
    if value is None:
        return False
    return _as_bool(value)


def _bundle_is_name_driven(plan: Dict[str, Any], bundle) -> bool:
    requirement = plan.get("requirement") or {}
    requirement_view = bundle_requirement(requirement, bundle) if isinstance(requirement, dict) else {}
    synthesized = dict(requirement_view) if isinstance(requirement_view, dict) else {}
    synthesized.setdefault("vuln_id", str(getattr(bundle, "vuln_id", "") or "").strip())
    return is_name_driven_requirement(synthesized)


def _strict_name_only_gate_required(plan: Dict[str, Any]) -> bool:
    if _name_only_mode(plan) != "strict_dynamic":
        return False
    bundles = load_vuln_bundles(plan)
    if not bundles:
        return False
    return any(_bundle_is_name_driven(plan, bundle) for bundle in bundles)


def _strict_name_only_live_llm_required(plan: Dict[str, Any]) -> bool:
    if not _strict_name_only_gate_required(plan):
        return False
    contract = _name_only_contract(plan)
    return bool(contract.get("require_live_llm"))


def _strict_name_only_remote_research_required(plan: Dict[str, Any]) -> bool:
    if not _strict_name_only_gate_required(plan):
        return False
    contract = _name_only_contract(plan)
    return bool(contract.get("require_remote_research"))


def _strict_name_only_capability_gate_failure(plan: Dict[str, Any]) -> Dict[str, Any]:
    if not _strict_name_only_gate_required(plan):
        return {}
    if _strict_name_only_live_llm_required(plan):
        reasons: List[str] = []
        metadata: Dict[str, Any] = {
            "terminal_failure_class": "strict_dynamic_live_llm_unavailable",
            "retry_recommended": False,
            "required_gate": "strict_dynamic",
        }
        if os.environ.get("VUL_FORCE_LLM_STUB"):
            reasons.append("forced_stub_env")
        fixture_keys = [
            key
            for key in ("VUL_LLM_FIXTURE_GENERATOR_MANIFEST",)
            if str(os.environ.get(key) or "").strip()
        ]
        if fixture_keys:
            reasons.append("fixture_env")
            metadata["fixture_env_keys"] = fixture_keys
        api_key = (
            get_openai_api_key()
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("VUL_LLM_API_KEY")
        )
        if not str(api_key or "").strip():
            reasons.append("missing_api_key")
        if litellm_completion is None:
            reasons.append("litellm_unavailable")
        if reasons:
            metadata["capability_reasons"] = reasons
            reason = (
                "strict_dynamic requires a live LLM path, but capability precheck failed before RESEARCH: "
                + ", ".join(reasons)
            )
            fix_hint = (
                "Provide a live OpenAI-compatible LLM path (remove forced stub/fixture, ensure API key is configured, "
                "and ensure litellm is available) or relax policy.name_only_mode to dynamic/compatibility."
            )
            return {
                "reason": reason,
                "fix_hint": fix_hint,
                "metadata": metadata,
            }

    if not _strict_name_only_remote_research_required(plan):
        return {}
    remote_capability = WebSearchTool().remote_capability()
    if remote_capability.configured:
        return {}
    provider = str(remote_capability.provider or "none").strip() or "none"
    reason_parts = [f"provider={provider}"]
    if remote_capability.error:
        reason_parts.append(str(remote_capability.error))
    reason = (
        "strict_dynamic requires remote researcher evidence, but capability precheck failed before RESEARCH: "
        + "; ".join(reason_parts)
    )
    fix_hint = (
        "Configure a remote search provider (for example Tavily via VUL_WEB_SEARCH_PROVIDER/VUL_WEB_SEARCH_API_KEY "
        "or a custom endpoint via VUL_WEB_SEARCH_ENDPOINT) or relax policy.name_only_mode / researcher.search_policy."
    )
    metadata = {
        "terminal_failure_class": "strict_dynamic_remote_research_unavailable",
        "retry_recommended": False,
        "required_gate": "strict_dynamic",
        "search_provider": provider,
        "search_configured": False,
        "search_error": str(remote_capability.error or "").strip() or None,
        "search_endpoint_or_base_url": remote_capability.endpoint_or_base_url,
        "search_auth_present": remote_capability.auth_present,
        "require_remote_research": True,
    }
    return {
        "reason": reason,
        "fix_hint": fix_hint,
        "metadata": metadata,
    }


def _strict_name_only_live_llm_gate_failure(plan: Dict[str, Any], sid: str) -> Dict[str, Any]:
    if not _strict_name_only_live_llm_required(plan):
        return {}
    llm_stub_used = _pipeline_llm_stub_used(sid)
    llm_fixture_used = _pipeline_llm_fixture_used(sid)
    llm_failure_class = str(_pipeline_llm_failure_class(sid) or "").strip().lower()
    if not llm_stub_used and not llm_fixture_used and llm_failure_class not in {
        "quota_exhausted",
        "auth_failure",
        "llm_unavailable",
        "provider_disabled",
    }:
        return {}
    reasons: List[str] = []
    if llm_stub_used:
        reasons.append("llm_stub_used")
    if llm_fixture_used:
        reasons.append("llm_fixture_used")
    if llm_failure_class:
        reasons.append(f"llm_failure_class={llm_failure_class}")
    reason = (
        "strict_dynamic requires a live LLM path before GENERATOR, but RESEARCH already established "
        "a disallowed LLM path: "
        + ", ".join(reasons)
    )
    fix_hint = (
        "Restore live LLM availability (disable stub/fixture, resolve quota/auth/provider issues) "
        "or relax policy.name_only_mode to dynamic/compatibility."
    )
    return {
        "reason": reason,
        "fix_hint": fix_hint,
        "metadata": {
            "terminal_failure_class": "strict_dynamic_disallowed_llm_path",
            "retry_recommended": False,
            "required_gate": "strict_dynamic",
            "llm_stub_used": llm_stub_used,
            "llm_fixture_used": llm_fixture_used,
            "llm_failure_class": llm_failure_class or None,
        },
    }


def _bundle_generator_posture(plan: Dict[str, Any], bundle) -> Dict[str, Any]:
    metadata_dir = metadata_dir_for_bundle(plan, bundle)
    manifest_payload = _load_json(metadata_dir / "generator_manifest.json") or {}
    manifest = (
        manifest_payload.get("manifest")
        if isinstance(manifest_payload.get("manifest"), dict)
        else manifest_payload
    )
    provenance = manifest_payload.get("provenance") if isinstance(manifest_payload.get("provenance"), dict) else {}
    metadata = manifest.get("metadata") if isinstance(manifest, dict) and isinstance(manifest.get("metadata"), dict) else {}
    dynamic_eval = _load_json(metadata_dir / "dynamic_eval.json") or {}

    def _bool(value: Any) -> bool | None:
        if value is None:
            return None
        return _as_bool(value)

    posture = {
        "generation_origin": str(
            manifest_payload.get("generation_origin")
            or provenance.get("generation_origin")
            or metadata.get("generation_origin")
            or ""
        ).strip().lower(),
        "fallback_used": _bool(
            manifest_payload.get("fallback_used")
            if "fallback_used" in manifest_payload
            else provenance.get("fallback_used")
        ),
        "fallback_class": str(
            manifest_payload.get("fallback_class")
            or provenance.get("fallback_class")
            or metadata.get("fallback_class")
            or ""
        ).strip().lower(),
        "materializer": str(
            provenance.get("materializer")
            or metadata.get("materializer")
            or ""
        ).strip().lower(),
        "llm_stub_used": _bool(
            manifest_payload.get("llm_stub_used")
            if "llm_stub_used" in manifest_payload
            else provenance.get("llm_stub_used")
        ),
        "llm_fixture_used": _bool(
            manifest_payload.get("llm_fixture_used")
            if "llm_fixture_used" in manifest_payload
            else provenance.get("llm_fixture_used")
        ),
        "dynamic_eval_status": str((dynamic_eval or {}).get("status") or "").strip().lower(),
    }
    return posture


def _strict_name_only_generator_gate_failure(plan: Dict[str, Any]) -> Dict[str, Any]:
    if not _strict_name_only_gate_required(plan):
        return {}
    bundles = load_vuln_bundles(plan)
    if not bundles:
        return {}

    failed_bundles: List[Dict[str, Any]] = []
    for bundle in bundles:
        if not _bundle_is_name_driven(plan, bundle):
            continue
        posture = _bundle_generator_posture(plan, bundle)
        reasons: List[str] = []
        generation_origin = str(posture.get("generation_origin") or "").strip().lower()
        if generation_origin != "llm_manifest":
            reasons.append(f"generation_origin={generation_origin or 'unknown'}")
        if posture.get("fallback_used") is True or generation_origin == "deterministic_fallback":
            reasons.append("deterministic_fallback")
        if posture.get("llm_stub_used") is True:
            reasons.append("llm_stub_used")
        if posture.get("llm_fixture_used") is True:
            reasons.append("llm_fixture_used")
        dynamic_eval_status = str(posture.get("dynamic_eval_status") or "").strip().lower()
        if dynamic_eval_status in {"degraded_success", "lower_bound_recovered"}:
            reasons.append(f"dynamic_eval_status={dynamic_eval_status}")
        if not reasons:
            continue
        failed_bundles.append(
            {
                "slug": bundle.slug,
                "vuln_id": bundle.vuln_id,
                "generation_origin": generation_origin or "unknown",
                "fallback_class": str(posture.get("fallback_class") or "").strip(),
                "materializer": str(posture.get("materializer") or "").strip(),
                "dynamic_eval_status": dynamic_eval_status or "unknown",
                "llm_stub_used": posture.get("llm_stub_used") is True,
                "llm_fixture_used": posture.get("llm_fixture_used") is True,
                "reasons": reasons,
            }
        )

    if not failed_bundles:
        return {}

    lines = []
    for item in failed_bundles:
        detail = (
            f"{item['slug']} ({item['vuln_id']}): "
            + ", ".join(item["reasons"])
        )
        if item["fallback_class"]:
            detail += f", fallback_class={item['fallback_class']}"
        if item["materializer"]:
            detail += f", materializer={item['materializer']}"
        lines.append(f"- {detail}")
    reason = (
        "strict_dynamic policy rejects the generated name-only bundle before EXECUTOR because the generation path "
        "already closed below the required open-world bar:\n"
        + "\n".join(lines)
    )
    fix_hint = (
        "Provide live researcher-backed LLM generation that closes via llm_manifest without stub/fixture or deterministic fallback, "
        "or relax policy.name_only_mode to dynamic/compatibility."
    )
    return {
        "reason": reason,
        "fix_hint": fix_hint,
        "metadata": {
            "terminal_failure_class": "strict_dynamic_disallowed_generation_path",
            "retry_recommended": False,
            "required_gate": "strict_dynamic",
            "failed_bundles": failed_bundles,
        },
    }


def _manifest_bundle_is_name_driven(bundle_payload: Dict[str, Any]) -> bool:
    if not isinstance(bundle_payload, dict):
        return False
    return is_name_driven_requirement(bundle_payload)


def _strict_name_only_gate_failure(plan: Dict[str, Any], sid: str) -> Dict[str, Any]:
    if not _strict_name_only_gate_required(plan):
        return {}
    manifest = _load_json(get_metadata_dir(sid) / "manifest.json") or {}
    bundles = manifest.get("bundles") or []
    if not isinstance(bundles, list):
        return {}

    failing_bundles: List[Dict[str, Any]] = []
    for entry in bundles:
        if not _manifest_bundle_is_name_driven(entry):
            continue
        strict_open_world = entry.get("strict_open_world")
        if isinstance(strict_open_world, dict) and strict_open_world.get("counts_as_generalization") is True:
            continue
        dynamic_eval = entry.get("dynamic_eval") if isinstance(entry.get("dynamic_eval"), dict) else {}
        provenance = entry.get("provenance") if isinstance(entry.get("provenance"), dict) else {}
        strict_open_world = strict_open_world if isinstance(strict_open_world, dict) else {}
        failing_bundles.append(
            {
                "slug": str(entry.get("slug") or "").strip() or str(entry.get("vuln_id") or "").strip() or "unknown",
                "vuln_id": str(entry.get("vuln_id") or "").strip() or "UNKNOWN",
                "strict_open_world_class": str(strict_open_world.get("class") or "").strip() or "unknown",
                "strict_open_world_reason": str(strict_open_world.get("reason") or "").strip() or "",
                "dynamic_eval_status": str(dynamic_eval.get("status") or "").strip() or "unknown",
                "generation_origin": str(provenance.get("generation_origin") or "").strip() or "unknown",
                "fallback_class": str(provenance.get("fallback_class") or "").strip() or "",
                "materializer": str(provenance.get("materializer") or "").strip() or "",
            }
        )
    if not failing_bundles:
        return {}

    lines = []
    for item in failing_bundles:
        detail = (
            f"{item['slug']} ({item['vuln_id']}): strict_open_world={item['strict_open_world_class']}, "
            f"dynamic_eval={item['dynamic_eval_status']}, generation_origin={item['generation_origin']}"
        )
        if item["fallback_class"]:
            detail += f", fallback_class={item['fallback_class']}"
        if item["materializer"]:
            detail += f", materializer={item['materializer']}"
        lines.append(f"- {detail}")
    reason = (
        "strict_dynamic policy requires strict open-world positive evidence, but the run closed below that bar:\n"
        + "\n".join(lines)
    )
    fix_hint = (
        "Either relax policy.name_only_mode to dynamic/compatibility, or improve the lane so it closes via "
        "trusted staged synthesis plus independent verification instead of degraded deterministic fallback."
    )
    return {
        "reason": reason,
        "fix_hint": fix_hint,
        "metadata": {
            "terminal_failure_class": "strict_open_world_not_satisfied",
            "retry_recommended": False,
            "required_gate": "strict_dynamic",
            "failed_bundles": failing_bundles,
        },
    }


def _seed_generator_contracts(plan: Dict[str, Any]) -> None:
    sid = str(plan.get("sid") or "").strip()
    requirement = plan.get("requirement") or {}
    if not sid or not isinstance(requirement, dict):
        return
    for bundle in load_vuln_bundles(plan):
        metadata_dir = metadata_dir_for_bundle(plan, bundle)
        if load_semantic_profile(metadata_dir):
            continue
        vuln_id = str(bundle.vuln_id or "").strip()
        if not vuln_id:
            continue
        payload = build_generator_contract(
            sid=sid,
            vuln_id=vuln_id,
            metadata_dir=metadata_dir,
            workspace_dir=None,
            generator_mode="pipeline_seed",
            bundle_slug=bundle.slug,
            requirement=bundle_requirement(requirement, bundle),
        )
        write_generator_contract(metadata_dir, payload)


def _write_researcher_skip_reports(plan: Dict[str, Any], sid: str, reason: str) -> None:
    for bundle in load_vuln_bundles(plan):
        metadata_dir = metadata_dir_for_bundle(plan, bundle)
        report_path = metadata_dir / "researcher_report.json"
        if report_path.exists():
            continue
        service = ResearcherService(
            sid,
            mode="deterministic",
            search_limit=1,
            plan=plan,
            bundle=bundle,
        )
        service.write_skip_report(reason)


def _can_skip_researcher(plan: Dict[str, Any], *, refresh_requested: bool) -> bool:
    if refresh_requested:
        return False
    if _researcher_force_run(plan):
        return False
    if _dynamic_eval_mode(plan):
        return False
    policy = plan.get("policy") or {}
    if isinstance(policy, dict) and _as_bool(policy.get("require_researcher_evidence")):
        return False
    bundles = load_vuln_bundles(plan)
    if not bundles:
        return False
    name_only_mode = _name_only_mode(plan)
    name_driven_requested = any(_bundle_is_name_driven(plan, bundle) for bundle in bundles)
    if name_driven_requested and name_only_mode in {"dynamic", "strict_dynamic"}:
        return False
    if (_open_world_strict_mode(plan) or (name_driven_requested and name_only_mode == "strict_dynamic")):
        return False
    requirement = plan.get("requirement") or {}
    if not isinstance(requirement, dict):
        requirement = {}
    return all(
        can_resolve_without_remote_research_for_requirement(
            bundle.vuln_id,
            bundle_requirement(requirement, bundle),
        )
        for bundle in bundles
    )


def _can_tolerate_shadow_research_failure(plan: Dict[str, Any], failure_meta: Dict[str, Any]) -> bool:
    if not _researcher_shadow_mode(plan):
        return False
    if _open_world_strict_mode(plan) or _name_only_mode(plan) == "strict_dynamic":
        return False
    if not _can_skip_researcher(plan, refresh_requested=False):
        return False
    if not isinstance(failure_meta, dict):
        return False
    terminal_failure_class = str(failure_meta.get("terminal_failure_class") or "").strip().lower()
    # Shadow mode is for non-blocking spec accumulation on lower-bound lanes.
    # Tolerate evidence/provider failures, but not unsupported-family hard stops.
    if terminal_failure_class == "semantic_support_missing":
        return False
    return True


def _bundle_requires_external_db(plan: Dict[str, Any], bundle) -> bool:
    paths = plan.get("paths") if isinstance(plan, dict) else {}
    if isinstance(paths, dict) and paths.get("metadata"):
        metadata_dir = metadata_dir_for_bundle(plan, bundle)
        for path in (metadata_dir / "generator_manifest.json", metadata_dir / "generator_template.json"):
            payload = _load_json(path)
            if not isinstance(payload, dict):
                continue
            candidates = [payload]
            manifest = payload.get("manifest")
            if isinstance(manifest, dict):
                candidates.append(manifest)
            for candidate in candidates:
                value = candidate.get("requires_external_db")
                if value is not None:
                    return _as_bool(value)
    requirement = plan.get("requirement") or {}
    bundle_req = bundle_requirement(requirement, bundle) if isinstance(requirement, dict) else {}
    runtime = bundle_req.get("runtime") if isinstance(bundle_req, dict) else {}
    if not isinstance(runtime, dict):
        runtime = {}
    db = str(runtime.get("db") or "").strip().lower()
    return db in {"mysql", "postgres", "postgresql", "mariadb"}


def _terminal_executor_precheck(plan: Dict[str, Any]) -> Dict[str, Any]:
    policy = plan.get("policy") or {}
    executor_policy = policy.get("executor") if isinstance(policy, dict) else {}
    if not isinstance(executor_policy, dict):
        executor_policy = {}
    sidecars = executor_policy.get("sidecars") or []
    allow_network = _as_bool(executor_policy.get("allow_network"))
    network_mode = str(
        executor_policy.get("network_mode") or ("bridge" if allow_network else "none")
    ).strip().lower()
    requirement = plan.get("requirement") or {}
    findings: List[Dict[str, Any]] = []
    for bundle in load_vuln_bundles(plan):
        if not _bundle_requires_external_db(plan, bundle):
            continue
        bundle_req = bundle_requirement(requirement, bundle) if isinstance(requirement, dict) else {}
        runtime = bundle_req.get("runtime") if isinstance(bundle_req, dict) else {}
        if not isinstance(runtime, dict):
            runtime = {}
        issues: List[str] = []
        db = str(runtime.get("db") or "").strip().lower()
        if not _as_bool(runtime.get("allow_external_db", False)):
            issues.append("runtime.allow_external_db=false")
        if not isinstance(sidecars, list) or not sidecars:
            issues.append("policy.executor.sidecars missing")
        if not allow_network or network_mode == "none":
            issues.append("policy.executor.allow_network/network_mode disables sidecars")
        if issues:
            findings.append(
                {
                    "slug": bundle.slug,
                    "vuln_id": bundle.vuln_id,
                    "db": db,
                    "issues": issues,
                }
            )
    if not findings:
        return {"terminal": False}
    lines = []
    for finding in findings:
        issue_text = ", ".join(str(item) for item in finding.get("issues") or [])
        db = str(finding.get("db") or "").strip()
        suffix = f", db={db}" if db else ""
        lines.append(f"- {finding['slug']} ({finding['vuln_id']}{suffix}): {issue_text}")
    reason = "Executor dependency precheck failed before Docker build:\n" + "\n".join(lines)
    fix_hint = (
        "If this bundle requires an external DB, set runtime.allow_external_db=true and configure "
        "policy.executor.allow_network=true with matching policy.executor.sidecars entries. "
        "Otherwise keep the family on embedded/no-sidecar runtime paths."
    )
    return {
        "terminal": True,
        "reason": reason,
        "fix_hint": fix_hint,
        "metadata": {
            "terminal_failure_class": "executor_dependency_misconfigured",
            "retry_recommended": False,
            "dependency_findings": findings,
        },
    }


def _terminal_research_failure_from_semantic_profile(plan: Dict[str, Any]) -> Dict[str, Any]:
    relevant_bundles = []
    unsupported_findings = []
    requirement = plan.get("requirement") or {}
    for bundle in load_vuln_bundles(plan):
        vuln_id = str(bundle.vuln_id or "").strip()
        requirement_view = bundle_requirement(requirement, bundle) if isinstance(requirement, dict) else {}
        if not _bundle_is_name_driven(plan, bundle):
            continue
        if not requires_semantic_support_for_requirement(vuln_id, requirement_view):
            continue
        relevant_bundles.append(bundle)
        profile = load_semantic_profile(metadata_dir_for_bundle(plan, bundle)) or {}
        support_level = str(profile.get("support_level") or "").strip().lower()
        compiler_supported = profile.get("compiler_supported")
        if support_level == "unsupported" and compiler_supported is False:
            unsupported_findings.append(
                {
                    "slug": bundle.slug,
                    "vuln_id": vuln_id,
                    "support_level": support_level,
                    "compiler_reason": str(profile.get("compiler_reason") or "").strip(),
                }
            )
    terminal = bool(relevant_bundles) and len(unsupported_findings) == len(relevant_bundles)
    reason_lines = []
    for finding in unsupported_findings:
        line = f"- {finding['slug']} ({finding['vuln_id']}): support_level={finding['support_level']}"
        compiler_reason = str(finding.get("compiler_reason") or "").strip()
        if compiler_reason:
            line += f", compiler_reason={compiler_reason}"
        reason_lines.append(line)
    reason = ""
    if terminal and reason_lines:
        reason = "Semantic profile marks unsupported free-form family before generation:\n" + "\n".join(reason_lines)
    return {
        "terminal": terminal,
        "bundles": unsupported_findings,
        "reason": reason,
        "retry_recommended": False,
        "terminal_failure_class": "semantic_support_missing",
    }


def _record_perf_event(
    sid: str,
    events: List[Dict[str, Any]],
    *,
    loop: int,
    stage: str,
    duration_s: float,
    returncode: int | None = None,
    skipped: bool = False,
    note: str = "",
) -> None:
    events.append(
        {
            "loop": loop,
            "stage": stage,
            "duration_s": round(max(0.0, duration_s), 3),
            "returncode": returncode,
            "skipped": bool(skipped),
            "note": note,
        }
    )
    _write_perf_summary(sid, events)


def _write_perf_summary(sid: str, events: List[Dict[str, Any]]) -> None:
    by_stage: Dict[str, Dict[str, Any]] = {}
    total = 0.0
    for item in events:
        if not isinstance(item, dict):
            continue
        duration = float(item.get("duration_s") or 0.0)
        total += duration
        stage = str(item.get("stage") or "UNKNOWN")
        stage_bucket = by_stage.setdefault(stage, {"count": 0, "duration_s": 0.0, "skipped": 0})
        stage_bucket["count"] += 1
        stage_bucket["duration_s"] = round(float(stage_bucket["duration_s"]) + duration, 3)
        if item.get("skipped"):
            stage_bucket["skipped"] += 1
    retry_count = _count_retries(events)
    provider_health_state = _provider_health_state(sid)
    llm_stub_used = _pipeline_llm_stub_used(sid)
    llm_fixture_used = _pipeline_llm_fixture_used(sid)
    llm_failure_class = _pipeline_llm_failure_class(sid)
    compiler_contracts = _compiler_contract_snapshot(sid)
    lower_bounds = _lower_bound_snapshot(sid)
    executor_feasibility = _executor_feasibility_snapshot(sid)
    payload = {
        "sid": sid,
        "events": events,
        "by_stage": by_stage,
        "retry_count": retry_count,
        "provider_health_state": provider_health_state,
        "llm_stub_used": llm_stub_used,
        "llm_fixture_used": llm_fixture_used,
        "llm_failure_class": llm_failure_class,
        "compiler_contracts": compiler_contracts,
        "lower_bounds": lower_bounds,
        "executor_feasibility": executor_feasibility,
        "total_duration_s": round(total, 3),
    }
    if len(compiler_contracts) == 1:
        contract = compiler_contracts[0]
        if isinstance(contract.get("compiler_supported"), bool):
            payload["compiler_supported"] = contract["compiler_supported"]
        for key in ("compiler_strategy", "compiler_reason"):
            value = contract.get(key)
            if isinstance(value, str) and value.strip():
                payload[key] = value.strip()
    if len(lower_bounds) == 1:
        lower_bound = lower_bounds[0]
        for key in ("family_non_remote_available", "effective_non_remote_available", "compiler_path_enabled"):
            value = lower_bound.get(key)
            if isinstance(value, bool):
                payload[key] = value
    if len(executor_feasibility) == 1:
        feasibility = executor_feasibility[0]
        status = feasibility.get("status")
        if isinstance(status, str) and status.strip():
            payload["executor_feasibility_status"] = status.strip()
    _write_json(get_metadata_dir(sid) / "performance_summary.json", payload)


def _count_retries(events: List[Dict[str, Any]]) -> int:
    stage_counts: Dict[str, int] = {}
    for item in events:
        if not isinstance(item, dict) or item.get("skipped"):
            continue
        stage = str(item.get("stage") or "").strip().upper()
        if not stage or stage == "PACK":
            continue
        stage_counts[stage] = stage_counts.get(stage, 0) + 1
    return sum(max(0, count - 1) for count in stage_counts.values())


def _provider_health_state(sid: str) -> str:
    search_health_payloads = _search_health_payloads(sid)
    search_degraded = any(
        bool(payload.get("degraded"))
        for payload in search_health_payloads
        if isinstance(payload, dict)
    )
    llm_stub_used = _pipeline_llm_stub_used(sid)
    llm_fixture_used = _pipeline_llm_fixture_used(sid)
    compiler_contracts = _compiler_contract_snapshot(sid)
    terminal_failure_class = _provider_failure_state_from_loop_state(sid)
    if terminal_failure_class == "strict_dynamic_disallowed_llm_path":
        return terminal_failure_class
    if search_degraded and llm_stub_used:
        return "search_and_llm_degraded"
    if llm_stub_used:
        return "llm_degraded"
    if llm_fixture_used:
        return "llm_fixture"
    if terminal_failure_class:
        return terminal_failure_class
    if search_degraded:
        return "search_degraded"
    if search_health_payloads:
        if any(
            bool(payload.get("configured")) or int(payload.get("remote_result_count") or 0) > 0
            for payload in search_health_payloads
            if isinstance(payload, dict)
        ):
            return "healthy"
        return "remote_provider_unavailable"
    if compiler_contracts:
        return "not_probed"
    return "unknown"


def _search_health_payloads(sid: str) -> List[Dict[str, Any]]:
    metadata_dir = get_metadata_dir(sid)
    paths = [metadata_dir / "search_health.json"]
    bundles_dir = metadata_dir / "bundles"
    if bundles_dir.exists():
        paths.extend(sorted(bundles_dir.glob("*/search_health.json")))
    payloads: List[Dict[str, Any]] = []
    for path in paths:
        payload = _load_json(path)
        if isinstance(payload, dict) and payload:
            payloads.append(payload)
    return payloads


def _researcher_report_paths(sid: str) -> List[Path]:
    metadata_root = get_metadata_dir(sid)
    paths = [metadata_root / "researcher_report.json"]
    bundles_dir = metadata_root / "bundles"
    if bundles_dir.exists():
        paths.extend(sorted(bundles_dir.glob("*/researcher_report.json")))
    return paths


def _provider_failure_state_from_loop_state(sid: str) -> str:
    metadata_dir = get_metadata_dir(sid)
    loop_state = _load_json(metadata_dir / "loop_state.json") or {}
    history = loop_state.get("history") if isinstance(loop_state, dict) else []
    if not isinstance(history, list):
        return ""
    priorities = (
        "strict_dynamic_live_llm_unavailable",
        "strict_dynamic_remote_research_unavailable",
        "strict_dynamic_disallowed_llm_path",
        "provider_degraded",
        "remote_provider_unavailable",
        "remote_evidence_missing",
        "evidence_low_relevance",
    )
    for entry in reversed(history):
        if not isinstance(entry, dict) or entry.get("success") is not False:
            continue
        metadata = entry.get("metadata")
        if not isinstance(metadata, dict):
            continue
        observed: set[str] = set()
        direct = str(metadata.get("terminal_failure_class") or "").strip().lower()
        if direct:
            observed.add(direct)
        for key in ("failed_bundles", "unsupported_bundles"):
            items = metadata.get(key)
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                token = str(item.get("terminal_failure_class") or "").strip().lower()
                if token:
                    observed.add(token)
        for candidate in priorities:
            if candidate in observed:
                return candidate
    return ""


def _pipeline_llm_stub_used(sid: str) -> bool:
    for path in _contract_candidate_paths(sid):
        payload = _load_json(path)
        if not isinstance(payload, dict):
            continue
        if _payload_llm_stub_used(payload):
            return True
    for path in _researcher_report_paths(sid):
        payload = _load_json(path)
        if not isinstance(payload, dict):
            continue
        if _researcher_report_llm_stub_used(payload):
            return True
    for record in _load_generator_failure_records(sid):
        if _failure_record_llm_stub_used(record):
            return True
    return False


def _pipeline_llm_fixture_used(sid: str) -> bool:
    for path in _contract_candidate_paths(sid):
        payload = _load_json(path)
        if not isinstance(payload, dict):
            continue
        if _payload_llm_fixture_used(payload):
            return True
    for path in _researcher_report_paths(sid):
        payload = _load_json(path)
        if not isinstance(payload, dict):
            continue
        if _researcher_report_llm_fixture_used(payload):
            return True
    for record in _load_generator_failure_records(sid):
        if _failure_record_llm_fixture_used(record):
            return True
    return False


def _payload_llm_stub_used(payload: Dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    direct = payload.get("llm_stub_used")
    if isinstance(direct, bool):
        return direct
    provenance = payload.get("provenance")
    if isinstance(provenance, dict):
        nested = provenance.get("llm_stub_used")
        if isinstance(nested, bool):
            return nested
    return False


def _payload_llm_fixture_used(payload: Dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    direct = payload.get("llm_fixture_used")
    if isinstance(direct, bool):
        return direct
    provenance = payload.get("provenance")
    if isinstance(provenance, dict):
        nested = provenance.get("llm_fixture_used")
        if isinstance(nested, bool):
            return nested
    return False


def _pipeline_llm_failure_class(sid: str) -> str:
    for path in _contract_candidate_paths(sid):
        payload = _load_json(path)
        if not isinstance(payload, dict):
            continue
        token = _payload_llm_failure_class(payload)
        if token:
            return token
    for path in _researcher_report_paths(sid):
        payload = _load_json(path)
        if not isinstance(payload, dict):
            continue
        token = _researcher_report_llm_failure_class(payload)
        if token:
            return token
    for record in _load_generator_failure_records(sid):
        token = _failure_record_llm_failure_class(record)
        if token:
            return token
    return ""


def _payload_llm_failure_class(payload: Dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        return ""
    direct = payload.get("llm_failure_class")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    provenance = payload.get("provenance")
    if isinstance(provenance, dict):
        nested = provenance.get("llm_failure_class")
        if isinstance(nested, str) and nested.strip():
            return nested.strip()
    return ""


def _failure_record_llm_stub_used(record: Dict[str, Any]) -> bool:
    if not isinstance(record, dict):
        return False
    direct = record.get("llm_stub_used")
    if isinstance(direct, bool):
        return direct
    return False


def _failure_record_llm_fixture_used(record: Dict[str, Any]) -> bool:
    if not isinstance(record, dict):
        return False
    direct = record.get("llm_fixture_used")
    if isinstance(direct, bool):
        return direct
    return False


def _failure_record_llm_failure_class(record: Dict[str, Any]) -> str:
    if not isinstance(record, dict):
        return ""
    direct = record.get("llm_failure_class")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    return ""


def _researcher_report_llm_stub_used(payload: Dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    llm_execution = payload.get("llm_execution")
    if not isinstance(llm_execution, dict):
        return False
    return llm_execution.get("stub_fallback") is True


def _researcher_report_llm_fixture_used(payload: Dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    llm_execution = payload.get("llm_execution")
    if not isinstance(llm_execution, dict):
        return False
    return llm_execution.get("fixture_used") is True


def _researcher_report_llm_failure_class(payload: Dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        return ""
    llm_execution = payload.get("llm_execution")
    if not isinstance(llm_execution, dict):
        return ""
    token = llm_execution.get("last_error_class")
    if isinstance(token, str) and token.strip():
        return token.strip()
    return ""


def _contract_candidate_paths(sid: str) -> List[Path]:
    metadata_root = get_metadata_dir(sid)
    candidate_paths = [
        metadata_root / "resolved_contract.json",
        metadata_root / "generator_contract.json",
        metadata_root / "generator_manifest.json",
        metadata_root / "generator_template.json",
    ]
    bundles_dir = metadata_root / "bundles"
    if bundles_dir.exists():
        for bundle_dir in sorted(path for path in bundles_dir.iterdir() if path.is_dir()):
            candidate_paths.extend(
                [
                    bundle_dir / "resolved_contract.json",
                    bundle_dir / "generator_contract.json",
                    bundle_dir / "generator_manifest.json",
                    bundle_dir / "generator_template.json",
                ]
            )
    return candidate_paths


def _compiler_contract_snapshot(sid: str) -> List[Dict[str, Any]]:
    snapshots: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for path in _contract_candidate_paths(sid):
        payload = _load_json(path)
        if not isinstance(payload, dict):
            continue
        slug = payload.get("slug")
        vuln_id = payload.get("vuln_id")
        compiler_supported = payload.get("compiler_supported")
        compiler_strategy = payload.get("compiler_strategy")
        compiler_reason = payload.get("compiler_reason")
        profile = payload.get("semantic_profile")
        if isinstance(profile, dict):
            if not isinstance(compiler_supported, bool):
                compiler_supported = profile.get("compiler_supported")
            if not isinstance(compiler_strategy, str) or not compiler_strategy.strip():
                compiler_strategy = profile.get("compiler_strategy")
            if not isinstance(compiler_reason, str) or not compiler_reason.strip():
                compiler_reason = profile.get("compiler_reason")
        if not isinstance(compiler_supported, bool) and not (
            isinstance(compiler_strategy, str) and compiler_strategy.strip()
        ):
            continue
        if not (isinstance(slug, str) and slug.strip()) and not (isinstance(vuln_id, str) and vuln_id.strip()):
            continue
        key = json.dumps({"slug": slug, "vuln_id": vuln_id}, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        entry: Dict[str, Any] = {
            "slug": slug,
            "vuln_id": vuln_id,
            "path": str(path),
        }
        if isinstance(compiler_supported, bool):
            entry["compiler_supported"] = compiler_supported
        if isinstance(compiler_strategy, str) and compiler_strategy.strip():
            entry["compiler_strategy"] = compiler_strategy.strip()
        if isinstance(compiler_reason, str) and compiler_reason.strip():
            entry["compiler_reason"] = compiler_reason.strip()
        if isinstance(profile, dict):
            for key_name in ("support_level", "family"):
                value = profile.get(key_name)
                if isinstance(value, str) and value.strip():
                    entry[key_name] = value.strip()
        snapshots.append(entry)
    return snapshots


def _lower_bound_snapshot(sid: str) -> List[Dict[str, Any]]:
    try:
        plan = load_plan(sid)
    except Exception:
        return []
    requirement = plan.get("requirement") or {}
    snapshots: List[Dict[str, Any]] = []
    for bundle in load_vuln_bundles(plan):
        bundle_req = bundle_requirement(requirement, bundle) if isinstance(requirement, dict) else {}
        lower_bound = lower_bound_summary(bundle.vuln_id, bundle_req)
        if not isinstance(lower_bound, dict):
            continue
        entry = {
            "slug": bundle.slug,
            "vuln_id": bundle.vuln_id,
            **lower_bound,
        }
        snapshots.append(entry)
    return snapshots


def _executor_feasibility_snapshot(sid: str) -> List[Dict[str, Any]]:
    try:
        plan = load_plan(sid)
    except Exception:
        return []
    requirement = plan.get("requirement") or {}
    policy = plan.get("policy") or {}
    executor_policy = policy.get("executor") if isinstance(policy, dict) else {}
    if not isinstance(executor_policy, dict):
        executor_policy = {}
    snapshots: List[Dict[str, Any]] = []
    for bundle in load_vuln_bundles(plan):
        bundle_req = bundle_requirement(requirement, bundle) if isinstance(requirement, dict) else {}
        summary = executor_feasibility_summary(
            bundle_req,
            executor_policy,
            requires_external_db=_bundle_requires_external_db(plan, bundle),
        )
        entry = {
            "slug": bundle.slug,
            "vuln_id": bundle.vuln_id,
            **summary,
        }
        snapshots.append(entry)
    return snapshots


def _write_failure_summary_manifest(sid: str, plan: Dict[str, Any]) -> None:
    try:
        from orchestrator import pack as pack_mod

        pack_mod.write_manifest(sid, plan, filename="failure_manifest.json")
    except Exception as exc:  # pragma: no cover - defensive logging only
        LOGGER.warning("Failed to write failure summary manifest for %s: %s", sid, exc)


def _refresh_manifest_after_pack(sid: str, plan: Dict[str, Any]) -> None:
    metadata_dir = get_metadata_dir(sid)
    manifest_path = metadata_dir / "manifest.json"
    failure_manifest_path = metadata_dir / "failure_manifest.json"
    if manifest_path.exists():
        filename = "manifest.json"
    elif failure_manifest_path.exists():
        filename = "failure_manifest.json"
    else:
        return

    try:
        from orchestrator import pack as pack_mod

        pack_mod.write_manifest(sid, plan, filename=filename)
    except Exception as exc:  # pragma: no cover - defensive logging only
        LOGGER.warning("Failed to refresh manifest after PACK for %s: %s", sid, exc)


def _prepare_fresh_run_state(sid: str) -> None:
    metadata_dir = ensure_dir(get_metadata_dir(sid))
    if has_runtime_asset_seed_manifest(metadata_dir):
        purge_runtime_asset_dirs(metadata_dir)
    else:
        remove_generated_runtime_assets(metadata_dir)
    keep_names = {
        "plan.json",
        "runtime_rules",
        "runtime_templates",
        RUNTIME_ASSET_SEEDS_FILENAME,
        GENERATED_RUNTIME_ASSETS_FILENAME,
    }
    for child in list(metadata_dir.iterdir()):
        if child.name in keep_names:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink(missing_ok=True)
    ensure_dir(metadata_dir / "runtime_rules")
    ensure_dir(metadata_dir / "runtime_templates")
    if has_runtime_asset_seed_manifest(metadata_dir):
        restore_seeded_runtime_assets(metadata_dir)

    for target in (get_artifacts_dir(sid), get_workspace_dir(sid)):
        if target.exists():
            shutil.rmtree(target)
        ensure_dir(target)


def _summarize_executor_error(sid: str, *, stage: str) -> Tuple[str, str, Dict[str, Any]]:
    artifacts_root = get_artifacts_dir(sid)
    index_path = artifacts_root / "run" / "index.json"
    index_payload = _load_json(index_path) or {}
    runs = index_payload.get("runs") or []
    failures: List[Dict[str, Any]] = []
    for entry in runs:
        if not isinstance(entry, dict):
            continue
        if entry.get("error"):
            failures.append(entry)
            continue
        # Conservative fallback: treat explicit stage failures as failures even without error string.
        if stage == "build" and entry.get("build_attempted") and not entry.get("build_passed"):
            failures.append(entry)
        if stage == "run" and entry.get("run_attempted") and not entry.get("run_passed"):
            failures.append(entry)

    failure_lines: List[str] = []
    metadata: Dict[str, Any] = {
        "sid": sid,
        "stage": stage,
        "index_path": str(index_path),
        "failures": [],
    }

    for entry in failures[:3]:
        slug = entry.get("slug") or entry.get("vuln_id") or "unknown"
        error = entry.get("error") or "executor failure"
        failure_lines.append(f"- {slug}: {error}")
        metadata["failures"].append(
            {
                "slug": slug,
                "vuln_id": entry.get("vuln_id"),
                "failed_stage": entry.get("failed_stage"),
                "error": error,
                "run_log": entry.get("run_log"),
                "build_log": entry.get("build_log"),
            }
        )
    if not failure_lines:
        failure_lines.append("- unknown: executor reported failure (index.json missing details)")

    # Add a small log tail excerpt for the first failing bundle when available.
    if metadata["failures"]:
        first = metadata["failures"][0]
        preferred_key = "build_log" if stage == "build" else "run_log"
        fallback_key = "run_log" if preferred_key == "build_log" else "build_log"
        chosen_path = first.get(preferred_key) or first.get(fallback_key)
        if isinstance(chosen_path, str) and chosen_path:
            excerpt = _tail_text(Path(chosen_path), limit_chars=2200)
            if excerpt:
                metadata["log_excerpt"] = excerpt
                metadata["log_excerpt_path"] = chosen_path

    reason = f"Executor {stage} failed:\n" + "\n".join(failure_lines)
    hint = "Inspect executor logs and adjust the generated bundle to satisfy executor constraints."
    excerpt_text = str(metadata.get("log_excerpt") or "")
    joined = (reason + "\n" + excerpt_text).lower()
    if "no such file or directory" in joined and "sqlite3" in joined:
        hint = (
            "Avoid invoking sqlite3 CLI at runtime. Use Python sqlite3 module and store the DB under /tmp "
            "(container runs with --read-only)."
        )
    elif "no such table" in joined and "sqlite" in joined:
        hint = (
            "SQLite table missing at runtime. Remember /tmp is mounted as tmpfs and starts empty each run; "
            "initialize the SQLite DB under /tmp at service startup (e.g., read schema.sql/seed_data.sql from /app, "
            "create tables, then handle requests)."
        )
    elif "dockerfile parse error" in joined or "unknown instruction" in joined:
        hint = (
            "Dockerfile parse error detected. Ensure every Dockerfile line starts with a valid instruction "
            "(FROM/RUN/COPY/...) or is a continuation line ending with '\\'. Avoid multi-line `RUN python -c \"...` "
            "blocks that spill Python code onto new Dockerfile lines."
        )
    elif "before_first_request" in joined and "attributeerror" in joined:
        hint = (
            "Flask compatibility error detected: `before_first_request` is removed in Flask 3. "
            "Remove that decorator and run initialization explicitly at startup (call init_db() before app.run) "
            "or use before_request with a one-time guard."
        )
    elif "modulenotfounderror" in joined or "no module named" in joined:
        hint = (
            "Missing runtime dependency detected (ModuleNotFoundError). Add the required package to manifest.deps "
            "and requirements*.txt (or enable dep_guard.auto_patch) so `pip install -r requirements.txt` installs it."
        )
    elif "read-only file system" in joined:
        hint = "Container runs with --read-only; write runtime state only under /tmp (or use in-memory)."
    elif "did not become ready" in joined or "readiness probe" in joined:
        hint = "Ensure the service binds 0.0.0.0 and listens on the declared port; add startup init delays if needed."

    return reason, hint, metadata


def _summarize_verify_failure(sid: str) -> Tuple[str, str, Dict[str, Any]]:
    artifacts_root = get_artifacts_dir(sid)
    evals_path = artifacts_root / "reports" / "evals.json"
    payload = _load_json(evals_path) or {}
    results = payload.get("results") or []
    failures: List[Dict[str, Any]] = []
    for entry in results:
        if not isinstance(entry, dict):
            continue
        if entry.get("verify_pass") is False:
            failures.append(entry)

    failure_lines: List[str] = []
    metadata: Dict[str, Any] = {"sid": sid, "evals_path": str(evals_path), "failures": []}
    for entry in failures[:3]:
        slug = entry.get("slug") or entry.get("vuln_id") or "unknown"
        evidence = entry.get("evidence") or entry.get("status") or "verification failed"
        failure_lines.append(f"- {slug}: {evidence}")
        metadata["failures"].append(
            {
                "slug": slug,
                "vuln_id": entry.get("vuln_id"),
                "status": entry.get("status"),
                "evidence": evidence,
                "log_path": entry.get("log_path"),
            }
        )
    if not failure_lines:
        failure_lines.append("- unknown: evals.json missing failure details")

    reason = "Verifier failed:\n" + "\n".join(failure_lines)
    hint = (
        "Align the PoC output with the rule/contract (success_signature + optional flag_token), "
        "ensure exit_code=0 on success, and ensure the exploit path matches the generated service."
    )
    return reason, hint, metadata


def _overall_verify_pass(sid: str) -> bool:
    evals_path = get_artifacts_dir(sid) / "reports" / "evals.json"
    payload = _load_json(evals_path) or {}
    return bool(payload.get("overall_pass"))


def _has_successful_verified_bundles(sid: str) -> bool:
    evals_path = get_artifacts_dir(sid) / "reports" / "evals.json"
    payload = _load_json(evals_path) or {}
    results = payload.get("results") or []
    for entry in results:
        if isinstance(entry, dict) and entry.get("verify_pass") is True:
            return True
    return False


def _analyze_verify_failures(sid: str) -> Dict[str, Any]:
    evals_path = get_artifacts_dir(sid) / "reports" / "evals.json"
    payload = _load_json(evals_path) or {}
    results = payload.get("results") or []
    failures: List[Dict[str, Any]] = []
    terminal_semantic_unsupported = bool(results)
    terminal_low_trust_verification = bool(results)
    for entry in results:
        if not isinstance(entry, dict) or entry.get("verify_pass") is not False:
            continue
        failures.append(entry)
        if entry.get("verification_policy_blocked") is not True:
            terminal_low_trust_verification = False
        vuln_id = str(entry.get("vuln_id") or "").strip()
        semantic_supported = entry.get("semantic_supported")
        semantic_status = str(entry.get("semantic_status") or "").strip().lower()
        if not requires_semantic_support(vuln_id):
            terminal_semantic_unsupported = False
            continue
        if semantic_supported is False and semantic_status in {"unsupported", "empty"}:
            continue
        terminal_semantic_unsupported = False

    if not failures:
        terminal_semantic_unsupported = False
        terminal_low_trust_verification = False
    return {
        "terminal_semantic_unsupported": terminal_semantic_unsupported,
        "terminal_low_trust_verification": terminal_low_trust_verification,
        "failure_count": len(failures),
        "failures": failures,
        "slugs": [
            str(entry.get("slug") or entry.get("vuln_id") or "unknown")
            for entry in failures
            if isinstance(entry, dict)
        ],
    }


def _verify_failures_match_partial_research_failure(
    verify_analysis: Dict[str, Any],
    partial_research_failure: Dict[str, Any],
) -> bool:
    failures = verify_analysis.get("failures") or []
    failed_bundles = partial_research_failure.get("failed_bundles") or []
    if not isinstance(failures, list) or not failures:
        return False
    blocked = {
        str(item.get("bundle_slug") or item.get("vuln_id") or "").strip()
        for item in failed_bundles
        if isinstance(item, dict) and str(item.get("bundle_slug") or item.get("vuln_id") or "").strip()
    }
    if not blocked:
        return False
    seen_failure = False
    for entry in failures:
        if not isinstance(entry, dict):
            return False
        token = str(entry.get("slug") or entry.get("vuln_id") or "").strip()
        if token not in blocked:
            return False
        seen_failure = True
    return seen_failure


def _review_blocking(sid: str) -> bool:
    report_path = get_metadata_dir(sid) / "reviewer_report.json"
    payload = _load_json(report_path) or {}
    blocking = payload.get("blocking_bundles") or []
    return bool(blocking)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run pipeline with E2E loops")
    parser.add_argument("--sid", required=True)
    parser.add_argument("--mode", default="deterministic", help="Decoding profile name")
    parser.add_argument("--skip-researcher", action="store_true")
    parser.add_argument("--researcher-every-loop", action="store_true")
    parser.add_argument("--skip-reviewer", action="store_true")
    parser.add_argument("--skip-pack", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sid = args.sid
    plan = load_plan(sid)
    _prepare_fresh_run_state(sid)
    loop_cfg = plan.get("loop", {"max_loops": 3})
    controller = LoopController(sid, max_loops=int(loop_cfg.get("max_loops", 3)))
    perf_events: List[Dict[str, Any]] = []
    if controller.current_loop == 0:
        controller.start_loop()
    _seed_generator_contracts(plan)
    capability_gate = _strict_name_only_capability_gate_failure(plan)
    if capability_gate:
        _record_perf_event(
            sid,
            perf_events,
            loop=controller.current_loop,
            stage="CAPABILITY_CHECK",
            duration_s=0.0,
            returncode=1,
            note="strict_dynamic capability precheck rejected before research",
        )
        controller.record_failure(
            stage="CAPABILITY_CHECK",
            reason=str(capability_gate.get("reason") or "strict_dynamic capability precheck failed"),
            fix_hint=str(
                capability_gate.get("fix_hint")
                or "Provide a live LLM path or relax policy.name_only_mode."
            ),
            blocking=True,
            metadata=capability_gate.get("metadata") or {},
        )
        LOGGER.info(
            "Stopping before RESEARCH for %s: strict_dynamic capability precheck rejected the run",
            sid,
        )
        if not args.skip_pack:
            allow_intentional = bool((plan.get("policy") or {}).get("allow_intentional_vuln"))
            pack_cmd = _python_cmd("orchestrator/pack.py", "--sid", sid)
            if allow_intentional:
                pack_cmd.append("--allow-intentional-vuln")
            rc, duration = _run_step_timed(pack_cmd, sid=sid)
            _record_perf_event(
                sid,
                perf_events,
                loop=controller.current_loop,
                stage="PACK",
                duration_s=duration,
                returncode=rc,
            )
            if rc != 0:
                _write_failure_summary_manifest(sid, plan)
            else:
                _refresh_manifest_after_pack(sid, plan)
        raise SystemExit(1)

    researcher_ran = False
    researcher_refresh_requested = False
    partial_research_failure: Dict[str, Any] = {}
    while True:
        if not args.skip_researcher and (args.researcher_every_loop or researcher_refresh_requested or not researcher_ran):
            terminal_profile = _terminal_research_failure_from_semantic_profile(plan)
            if terminal_profile.get("terminal"):
                _record_perf_event(
                    sid,
                    perf_events,
                    loop=controller.current_loop,
                    stage="RESEARCH",
                    duration_s=0.0,
                    returncode=1,
                    note="preseeded semantic profile unsupported",
                )
                controller.record_failure(
                    stage="RESEARCH",
                    reason=str(terminal_profile.get("reason") or "semantic profile unsupported"),
                    fix_hint=(
                        "Add compiler-backed support for this family or keep the request in "
                        "inspection-only / negative regression mode."
                    ),
                    blocking=True,
                    metadata={
                        "terminal_failure_class": terminal_profile.get("terminal_failure_class"),
                        "retry_recommended": False,
                        "unsupported_bundles": terminal_profile.get("bundles") or [],
                    },
                )
                LOGGER.info(
                    "Stopping before RESEARCH for %s: preseeded semantic_profile marked all relevant free-form bundles unsupported",
                    sid,
                )
                break
            can_skip_researcher = (
                not args.researcher_every_loop
                and _can_skip_researcher(plan, refresh_requested=researcher_refresh_requested)
            )
            shadow_mode = can_skip_researcher and _researcher_shadow_mode(plan)
            if can_skip_researcher and not shadow_mode:
                note = "researcher skipped: compiler/static supported path"
                _write_researcher_skip_reports(plan, sid, note)
                controller.record_success(stage="RESEARCH", note=note)
                _record_perf_event(
                    sid,
                    perf_events,
                    loop=controller.current_loop,
                    stage="RESEARCH",
                    duration_s=0.0,
                    skipped=True,
                    note=note,
                )
                researcher_ran = True
                researcher_refresh_requested = False
            else:
                research_note = "researcher shadow run"
                rc, duration = _run_step_timed(
                    _python_cmd("agents/researcher/main.py", "--sid", sid, "--mode", args.mode),
                    sid=sid,
                )
                _record_perf_event(
                    sid,
                    perf_events,
                    loop=controller.current_loop,
                    stage="RESEARCH",
                    duration_s=duration,
                    returncode=rc,
                    note=research_note if shadow_mode else "",
                )
                if rc != 0:
                    failure_reason, fix_hint, failure_meta = _research_failure_details(plan, rc)
                    bundle_scoped = _bundle_scoped_research_failure_metadata(plan)
                    if bundle_scoped.get("continue_pipeline"):
                        partial_research_failure = bundle_scoped
                        researcher_ran = True
                        researcher_refresh_requested = False
                        LOGGER.info(
                            "Continuing pipeline for %s after bundle-scoped RESEARCH failures: failed=%s runnable=%s",
                            sid,
                            [item.get("bundle_slug") for item in bundle_scoped.get("failed_bundles") or []],
                            bundle_scoped.get("runnable_bundles") or [],
                        )
                        research_note = "researcher partial failure tolerated"
                    elif _can_tolerate_shadow_research_failure(plan, failure_meta):
                        partial_research_failure = {}
                        researcher_ran = True
                        researcher_refresh_requested = False
                        research_note = (
                            "researcher shadow failure tolerated: "
                            + str(failure_meta.get("terminal_failure_class") or "research_failure")
                        )
                        LOGGER.info(
                            "Continuing pipeline for %s after non-blocking RESEARCH shadow failure (%s)",
                            sid,
                            str(failure_meta.get("terminal_failure_class") or "research_failure"),
                        )
                    else:
                        controller.record_failure(
                            stage="RESEARCH",
                            reason=failure_reason,
                            fix_hint=fix_hint,
                            blocking=True,
                            metadata=failure_meta,
                        )
                        if not _should_retry_research_failure(failure_meta):
                            LOGGER.info(
                                "Stopping retries for %s after RESEARCH: terminal research failure (%s)",
                                sid,
                                str(failure_meta.get("terminal_failure_class") or "research_failure"),
                            )
                            break
                        if controller.should_continue():
                            controller.start_loop()
                            continue
                        break
                else:
                    partial_research_failure = {}
                    research_note = "researcher succeeded"
                _seed_generator_contracts(plan)
                terminal_profile = _terminal_research_failure_from_semantic_profile(plan)
                if terminal_profile.get("terminal"):
                    controller.record_failure(
                        stage="RESEARCH",
                        reason=str(terminal_profile.get("reason") or "semantic profile unsupported"),
                        fix_hint=(
                            "Add compiler-backed support for this family or keep the request in "
                            "inspection-only / negative regression mode."
                        ),
                        blocking=True,
                        metadata={
                            "terminal_failure_class": terminal_profile.get("terminal_failure_class"),
                            "retry_recommended": False,
                            "unsupported_bundles": terminal_profile.get("bundles") or [],
                        },
                        )
                    LOGGER.info(
                        "Stopping before GENERATOR for %s: semantic_profile marked all relevant free-form bundles unsupported",
                        sid,
                    )
                    break
                controller.record_success(stage="RESEARCH", note=research_note)
                researcher_ran = True
                researcher_refresh_requested = False
                strict_live_llm_gate = _strict_name_only_live_llm_gate_failure(plan, sid)
                if strict_live_llm_gate:
                    _record_perf_event(
                        sid,
                        perf_events,
                        loop=controller.current_loop,
                        stage="NAME_ONLY_GATE",
                        duration_s=0.0,
                        returncode=1,
                        note="strict_dynamic live LLM gate rejected before generator",
                    )
                    controller.record_failure(
                        stage="NAME_ONLY_GATE",
                        reason=str(
                            strict_live_llm_gate.get("reason")
                            or "strict_dynamic requires a live LLM path before generation"
                        ),
                        fix_hint=str(
                            strict_live_llm_gate.get("fix_hint")
                            or "Restore live LLM availability or relax policy.name_only_mode."
                        ),
                        blocking=True,
                        metadata=strict_live_llm_gate.get("metadata") or {},
                    )
                    LOGGER.info(
                        "Stopping before GENERATOR for %s: strict_dynamic live LLM gate rejected the run",
                        sid,
                    )
                    break

        rc, duration = _run_step_timed(
            _python_cmd("agents/generator/main.py", "--sid", sid, "--mode", args.mode, "--single-attempt"),
            sid=sid,
        )
        _record_perf_event(
            sid,
            perf_events,
            loop=controller.current_loop,
            stage="GENERATOR",
            duration_s=duration,
            returncode=rc,
        )
        if rc != 0:
            latest_failure = _latest_generator_failure(sid)
            reason = (
                str((latest_failure or {}).get("reason") or "").strip()
                or f"Generator failed with exit code {rc}"
            )
            fix_hint = (
                str((latest_failure or {}).get("fix_hint") or "").strip()
                or "Inspect metadata/<SID>/*generator*.json(l) for guard violations and remediation hints."
            )
            metadata: Dict[str, Any] = {"exit_code": rc}
            planned_next_action: Dict[str, Any] | None = None
            if isinstance(latest_failure, dict):
                for key in (
                    "guard_error_code",
                    "guard_error_subcode",
                    "unsupported_ops",
                    "schema_errors",
                    "schema_normalizations",
                    "schema_mismatches",
                    "missing_dependencies",
                    "suggested_dependencies",
                    "failure_fingerprint",
                    "autofix_effective",
                    "hint_payload",
                ):
                    if key in latest_failure:
                        metadata[key] = latest_failure.get(key)
                hint_payload = latest_failure.get("hint_payload")
                if isinstance(hint_payload, dict):
                    next_action = hint_payload.get("next_action")
                    if isinstance(next_action, dict):
                        planned_next_action = next_action
                        metadata["planned_next_action"] = next_action
                terminal_failure_class = _generator_terminal_failure_class(latest_failure)
                if terminal_failure_class:
                    metadata["terminal_failure_class"] = terminal_failure_class
            controller.record_failure(
                stage="GENERATOR",
                reason=reason,
                fix_hint=fix_hint,
                blocking=True,
                metadata=metadata,
            )
            refresh_researcher, refresh_reason = _refresh_researcher_for_guard_failure(plan, sid, latest_failure)
            if refresh_researcher:
                if refresh_reason:
                    LOGGER.info("Refreshing researcher on next loop: %s", refresh_reason)
                else:
                    LOGGER.info("Refreshing researcher on next loop due to guard failure policy.")
                researcher_ran = False
                researcher_refresh_requested = True
            can_continue = controller.should_continue()
            if can_continue:
                controller.start_loop()
                continue
            if refresh_researcher:
                deferred_next_action = dict(planned_next_action or {})
                deferred_next_action["researcher_refresh"] = True
                deferred_next_action["retry_stage"] = "RESEARCH"
                deferred_next_action["rationale"] = refresh_reason or str(
                    deferred_next_action.get("rationale") or "refresh intended but loop limit reached"
                )
                _record_deferred_refresh(
                    sid,
                    reason=refresh_reason or "refresh intended but loop limit reached",
                    planned_next_action=deferred_next_action,
                )
                LOGGER.info("Researcher refresh deferred: loop limit reached for %s", sid)
            break

        strict_generator_gate = _strict_name_only_generator_gate_failure(plan)
        if strict_generator_gate:
            _record_perf_event(
                sid,
                perf_events,
                loop=controller.current_loop,
                stage="NAME_ONLY_GATE",
                duration_s=0.0,
                returncode=1,
                note="strict_dynamic generator posture rejected before executor",
            )
            controller.record_failure(
                stage="GENERATOR",
                reason=str(strict_generator_gate.get("reason") or "strict_dynamic generator posture rejected"),
                fix_hint=str(
                    strict_generator_gate.get("fix_hint")
                    or "Name-only strict dynamic requires a non-degraded live dynamic generation path."
                ),
                blocking=True,
                metadata=strict_generator_gate.get("metadata") or {},
            )
            LOGGER.info("Stopping before EXECUTOR for %s: strict_dynamic generator posture rejected", sid)
            break

        executor_precheck = _terminal_executor_precheck(plan)
        if executor_precheck.get("terminal"):
            _record_perf_event(
                sid,
                perf_events,
                loop=controller.current_loop,
                stage="EXECUTOR_PRECHECK",
                duration_s=0.0,
                returncode=1,
                note="executor dependency precheck failed",
            )
            controller.record_failure(
                stage="EXECUTOR",
                reason=str(executor_precheck.get("reason") or "executor dependency precheck failed"),
                fix_hint=str(
                    executor_precheck.get("fix_hint")
                    or "Align runtime external dependency requirements with executor sidecar/network policy."
                ),
                blocking=True,
                metadata=executor_precheck.get("metadata") or {},
            )
            LOGGER.info("Stopping before EXECUTOR for %s: executor dependency precheck failed", sid)
            break

        rc, duration = _run_step_timed(
            _python_cmd("executor/runtime/docker_local.py", "--sid", sid, "--build"),
            sid=sid,
        )
        _record_perf_event(
            sid,
            perf_events,
            loop=controller.current_loop,
            stage="EXECUTOR_BUILD",
            duration_s=duration,
            returncode=rc,
        )
        if rc != 0:
            reason, hint, meta = _summarize_executor_error(sid, stage="build")
            controller.record_failure(stage="EXECUTOR", reason=reason, fix_hint=hint, blocking=True, metadata=meta)
            if controller.should_continue():
                controller.start_loop()
                continue
            break

        rc, duration = _run_step_timed(
            _python_cmd("executor/runtime/docker_local.py", "--sid", sid, "--run"),
            sid=sid,
        )
        _record_perf_event(
            sid,
            perf_events,
            loop=controller.current_loop,
            stage="EXECUTOR_RUN",
            duration_s=duration,
            returncode=rc,
        )
        if rc != 0:
            reason, hint, meta = _summarize_executor_error(sid, stage="run")
            controller.record_failure(stage="EXECUTOR", reason=reason, fix_hint=hint, blocking=True, metadata=meta)
            if controller.should_continue():
                controller.start_loop()
                continue
            break

        controller.record_success(stage="EXECUTOR", note="executor build+run succeeded")

        rc, duration = _run_step_timed(_python_cmd("evals/poc_verifier/main.py", "--sid", sid), sid=sid)
        _record_perf_event(
            sid,
            perf_events,
            loop=controller.current_loop,
            stage="VERIFY",
            duration_s=duration,
            returncode=rc,
        )
        if not _overall_verify_pass(sid):
            reason, hint, meta = _summarize_verify_failure(sid)
            verify_analysis = _analyze_verify_failures(sid)
            failure_stage = "VERIFY"
            run_reviewer_for_partial_progress = False
            if partial_research_failure and _verify_failures_match_partial_research_failure(
                verify_analysis,
                partial_research_failure,
            ):
                failure_stage = "RESEARCH"
                meta["terminal_failure_class"] = "bundle_scoped_research_failure"
                meta["retry_recommended"] = False
                meta["failed_bundles"] = partial_research_failure.get("failed_bundles") or []
                meta["runnable_bundles"] = partial_research_failure.get("runnable_bundles") or []
                hint = (
                    "Some bundles were intentionally fail-closed after RESEARCH. "
                    "Add stronger evidence/compiler support for those bundles or split the request."
                )
                run_reviewer_for_partial_progress = _has_successful_verified_bundles(sid)
            elif verify_analysis.get("terminal_semantic_unsupported"):
                meta["terminal_failure_class"] = "semantic_support_missing"
                meta["retry_recommended"] = False
            elif verify_analysis.get("terminal_low_trust_verification"):
                meta["terminal_failure_class"] = "low_trust_verification"
                meta["retry_recommended"] = False
                hint = (
                    "Unknown/open-world lane was blocked by verifier low-trust policy. "
                    "Provide a declared/compiler-backed rule contract or relax "
                    "policy.verifier.low_trust_unknown_policy to warn for synthetic regression lanes."
                )
            controller.record_failure(stage=failure_stage, reason=reason, fix_hint=hint, blocking=True, metadata=meta)
            if run_reviewer_for_partial_progress and not args.skip_reviewer:
                rc, duration = _run_step_timed(
                    _python_cmd(
                        "agents/reviewer/main.py",
                        "--sid",
                        sid,
                        "--mode",
                        args.mode,
                        "--artifact-only",
                    ),
                    sid=sid,
                )
                _record_perf_event(
                    sid,
                    perf_events,
                    loop=controller.current_loop,
                    stage="REVIEW",
                    duration_s=duration,
                    returncode=rc,
                    note="partial-progress reviewer run",
                )
            if meta.get("terminal_failure_class") == "bundle_scoped_research_failure":
                LOGGER.info(
                    "Stopping retries for %s after VERIFY: bundle-scoped RESEARCH failures already explain the skipped bundles (%s)",
                    sid,
                    ", ".join(verify_analysis.get("slugs") or []) or "unknown bundle",
                )
                break
            if verify_analysis.get("terminal_semantic_unsupported"):
                LOGGER.info(
                    "Stopping retries for %s after VERIFY: terminal semantic support failure (%s)",
                    sid,
                    ", ".join(verify_analysis.get("slugs") or []) or "unknown bundle",
                )
                break
            if verify_analysis.get("terminal_low_trust_verification"):
                LOGGER.info(
                    "Stopping retries for %s after VERIFY: terminal low-trust verification policy block (%s)",
                    sid,
                    ", ".join(verify_analysis.get("slugs") or []) or "unknown bundle",
                )
                break
            if controller.should_continue():
                controller.start_loop()
                continue
            break

        controller.record_success(stage="VERIFY", note="verifier passed")

        if not args.skip_reviewer:
            rc, duration = _run_step_timed(
                _python_cmd("agents/reviewer/main.py", "--sid", sid, "--mode", args.mode),
                sid=sid,
            )
            _record_perf_event(
                sid,
                perf_events,
                loop=controller.current_loop,
                stage="REVIEW",
                duration_s=duration,
                returncode=rc,
            )
            if _review_blocking(sid):
                if controller.should_continue():
                    controller.start_loop()
                    continue
                break

        rc, duration = _run_step_timed(_python_cmd("evals/diversity_metrics.py", "--sid", sid), sid=sid)
        _record_perf_event(
            sid,
            perf_events,
            loop=controller.current_loop,
            stage="DIVERSITY",
            duration_s=duration,
            returncode=rc,
        )

        if partial_research_failure:
            failed_bundles = partial_research_failure.get("failed_bundles") or []
            failed_labels = [
                str(item.get("bundle_slug") or item.get("vuln_id") or "").strip()
                for item in failed_bundles
                if str(item.get("bundle_slug") or item.get("vuln_id") or "").strip()
            ]
            controller.record_failure(
                stage="RESEARCH",
                reason=(
                    "Bundle-scoped RESEARCH failures prevented full multi-bundle completion: "
                    + ", ".join(failed_labels)
                ),
                fix_hint=(
                    "Add stronger evidence/compiler support for the failed bundles or split the request "
                    "so supported bundles can be promoted independently."
                ),
                blocking=True,
                metadata={
                    "terminal_failure_class": "bundle_scoped_research_failure",
                    "retry_recommended": False,
                    "failed_bundles": failed_bundles,
                    "runnable_bundles": partial_research_failure.get("runnable_bundles") or [],
                },
            )

        if not args.skip_pack:
            allow_intentional = bool((plan.get("policy") or {}).get("allow_intentional_vuln"))
            pack_cmd = _python_cmd("orchestrator/pack.py", "--sid", sid)
            if allow_intentional:
                pack_cmd.append("--allow-intentional-vuln")
            rc, duration = _run_step_timed(pack_cmd, sid=sid)
            _record_perf_event(
                sid,
                perf_events,
                loop=controller.current_loop,
                stage="PACK",
                duration_s=duration,
                returncode=rc,
            )
            if rc != 0:
                _write_failure_summary_manifest(sid, plan)
            else:
                _refresh_manifest_after_pack(sid, plan)
                strict_gate_failure = _strict_name_only_gate_failure(plan, sid)
                if strict_gate_failure:
                    controller.record_failure(
                        stage="PACK",
                        reason=str(strict_gate_failure.get("reason") or "strict open-world gate not satisfied"),
                        fix_hint=str(
                            strict_gate_failure.get("fix_hint")
                            or "strict_dynamic requires strict open-world positive evidence"
                        ),
                        blocking=True,
                        metadata=strict_gate_failure.get("metadata") or {},
                    )
                    _refresh_manifest_after_pack(sid, plan)
                    raise SystemExit(1)

        return

    # Out of loops or fatal failure: still pack for debugging.
    if not args.skip_pack:
        allow_intentional = bool((plan.get("policy") or {}).get("allow_intentional_vuln"))
        pack_cmd = _python_cmd("orchestrator/pack.py", "--sid", sid)
        if allow_intentional:
            pack_cmd.append("--allow-intentional-vuln")
        rc, duration = _run_step_timed(pack_cmd, sid=sid)
        _record_perf_event(
            sid,
            perf_events,
            loop=controller.current_loop,
            stage="PACK",
            duration_s=duration,
            returncode=rc,
        )
        if rc != 0:
            _write_failure_summary_manifest(sid, plan)
        else:
            _refresh_manifest_after_pack(sid, plan)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
