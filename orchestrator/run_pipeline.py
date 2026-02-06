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
        run_log_path = first.get("run_log")
        if isinstance(run_log_path, str) and run_log_path:
            excerpt = _tail_text(Path(run_log_path), limit_chars=2200)
            if excerpt:
                metadata["log_excerpt"] = excerpt

    reason = f"Executor {stage} failed:\n" + "\n".join(failure_lines)
    hint = "Inspect executor logs and adjust the generated bundle to satisfy executor constraints."
    excerpt_text = str(metadata.get("log_excerpt") or "")
    joined = (reason + "\n" + excerpt_text).lower()
    if "no such file or directory" in joined and "sqlite3" in joined:
        hint = (
            "Avoid invoking sqlite3 CLI at runtime. Use Python sqlite3 module and store the DB under /tmp "
            "(container runs with --read-only)."
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

        rc = _run_step(_python_cmd("agents/generator/main.py", "--sid", sid, "--mode", args.mode))
        if rc != 0:
            controller.record_failure(
                stage="GENERATOR",
                reason=f"Generator failed with exit code {rc}",
                fix_hint="Inspect metadata/<SID>/*generator*.json(l) for guard violations and remediation hints.",
                blocking=True,
                metadata={"exit_code": rc},
            )
            if controller.should_continue():
                controller.start_loop()
                continue
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

