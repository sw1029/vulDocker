"""End-to-end pipeline runner with iterative loops.

This runner closes the gap between GENERATE-only loops and real-world failures
that happen in EXECUTE/VERIFY. It uses LoopController + Reflexion memories so
that later synthesis attempts can incorporate concrete failure context.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.logging import get_logger
from common.paths import get_artifacts_dir, get_metadata_dir
from common.plan import load_plan
from orchestrator.loop_controller import LoopController

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


def _run_step(cmd: List[str]) -> int:
    LOGGER.info("Running command: %s", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), check=False)
    return int(proc.returncode or 0)


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
    loop_cfg = plan.get("loop", {"max_loops": 3})
    controller = LoopController(sid, max_loops=int(loop_cfg.get("max_loops", 3)))
    if controller.current_loop == 0:
        controller.start_loop()

    researcher_ran = False
    while True:
        if not args.skip_researcher and (args.researcher_every_loop or not researcher_ran):
            rc = _run_step(_python_cmd("agents/researcher/main.py", "--sid", sid, "--mode", args.mode))
            if rc != 0:
                controller.record_failure(
                    stage="RESEARCH",
                    reason=f"Researcher failed with exit code {rc}",
                    fix_hint="Check LLM provider configuration / API key / network connectivity.",
                    blocking=True,
                    metadata={"exit_code": rc},
                )
                if controller.should_continue():
                    controller.start_loop()
                    continue
                break
            controller.record_success(stage="RESEARCH", note="researcher succeeded")
            researcher_ran = True

        rc = _run_step(
            _python_cmd("agents/generator/main.py", "--sid", sid, "--mode", args.mode, "--single-attempt")
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

        rc = _run_step(_python_cmd("executor/runtime/docker_local.py", "--sid", sid, "--build"))
        if rc != 0:
            reason, hint, meta = _summarize_executor_error(sid, stage="build")
            controller.record_failure(stage="EXECUTOR", reason=reason, fix_hint=hint, blocking=True, metadata=meta)
            if controller.should_continue():
                controller.start_loop()
                continue
            break

        rc = _run_step(_python_cmd("executor/runtime/docker_local.py", "--sid", sid, "--run"))
        if rc != 0:
            reason, hint, meta = _summarize_executor_error(sid, stage="run")
            controller.record_failure(stage="EXECUTOR", reason=reason, fix_hint=hint, blocking=True, metadata=meta)
            if controller.should_continue():
                controller.start_loop()
                continue
            break

        controller.record_success(stage="EXECUTOR", note="executor build+run succeeded")

        _run_step(_python_cmd("evals/poc_verifier/main.py", "--sid", sid))
        if not _overall_verify_pass(sid):
            reason, hint, meta = _summarize_verify_failure(sid)
            controller.record_failure(stage="VERIFY", reason=reason, fix_hint=hint, blocking=True, metadata=meta)
            if controller.should_continue():
                controller.start_loop()
                continue
            break

        controller.record_success(stage="VERIFY", note="verifier passed")

        if not args.skip_reviewer:
            _run_step(_python_cmd("agents/reviewer/main.py", "--sid", sid, "--mode", args.mode))
            if _review_blocking(sid):
                if controller.should_continue():
                    controller.start_loop()
                    continue
                break

        _run_step(_python_cmd("evals/diversity_metrics.py", "--sid", sid))

        if not args.skip_pack:
            allow_intentional = bool((plan.get("policy") or {}).get("allow_intentional_vuln"))
            pack_cmd = _python_cmd("orchestrator/pack.py", "--sid", sid)
            if allow_intentional:
                pack_cmd.append("--allow-intentional-vuln")
            _run_step(pack_cmd)

        return

    # Out of loops or fatal failure: still pack for debugging.
    if not args.skip_pack:
        allow_intentional = bool((plan.get("policy") or {}).get("allow_intentional_vuln"))
        pack_cmd = _python_cmd("orchestrator/pack.py", "--sid", sid)
        if allow_intentional:
            pack_cmd.append("--allow-intentional-vuln")
        _run_step(pack_cmd)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
