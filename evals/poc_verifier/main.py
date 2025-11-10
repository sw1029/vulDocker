"""Generic PoC verifier entry point using plugin registry."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.logging import get_logger
from common.paths import ensure_dir, get_artifacts_dir
from common.plan import load_plan
from common.run_matrix import (
    artifacts_dir_for_bundle,
    bundle_requirement,
    load_vuln_bundles,
)

from evals.poc_verifier.registry import evaluate_with_vuln
from rag.memories import ReflexionRecord, append_memory

# Ensure built-in verifiers are registered
from evals.poc_verifier import csrf  # noqa: F401
from evals.poc_verifier import mvp_sqli  # noqa: F401

LOGGER = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate PoC logs via registry")
    parser.add_argument("--sid", required=True)
    parser.add_argument("--log", type=Path, help="Optional path to a single run log")
    parser.add_argument("--vuln-id", help="Vuln ID for --log evaluation")
    return parser.parse_args()


def _load_run_index(sid: str) -> Dict[str, Dict[str, Any]]:
    path = get_artifacts_dir(sid) / "run" / "index.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    runs = data.get("runs") or []
    return {entry.get("slug"): entry for entry in runs if entry.get("slug")}


def _overall_pass(results: List[Dict[str, Any]]) -> bool:
    if not results:
        return False
    allowed_status = {"evaluated", "evaluated-llm"}
    for entry in results:
        if entry.get("status") not in allowed_status:
            return False
        if not entry.get("verify_pass"):
            return False
    return True


def _evaluate_single(log_path: Path, vuln_id: str) -> Dict[str, Any]:
    if not vuln_id:
        raise ValueError("--vuln-id is required when using --log")
    result = evaluate_with_vuln(vuln_id, log_path)
    result.setdefault("status", "evaluated")
    result.setdefault("log_path", str(log_path))
    return result


def _evaluate_all(sid: str) -> Dict[str, Any]:
    plan = load_plan(sid)
    _register_runtime_rules(plan)
    bundles = load_vuln_bundles(plan)
    run_index = _load_run_index(sid)
    results: List[Dict[str, Any]] = []
    for bundle in bundles:
        run_record = run_index.get(bundle.slug) or {}
        default_log = artifacts_dir_for_bundle(plan, bundle, "run") / "run.log"
        log_path = Path(run_record.get("run_log") or default_log)
        executed = run_record.get("executed")
        if not executed:
            entry = {
                "verify_pass": False,
                "evidence": run_record.get("error") or "Run not executed",
                "log_path": str(log_path),
                "status": "skipped",
            }
        else:
            try:
                requirement = bundle_requirement(plan["requirement"], bundle)
                entry = evaluate_with_vuln(
                    bundle.vuln_id,
                    log_path,
                    requirement=requirement,
                    run_summary=run_record,
                    plan_policy=plan.get("policy"),
                )
                entry.setdefault("status", "evaluated")
            except FileNotFoundError:
                entry = {
                    "verify_pass": False,
                    "evidence": "Run log missing",
                    "log_path": str(log_path),
                    "status": "log_missing",
                }
        entry["vuln_id"] = bundle.vuln_id
        entry["slug"] = bundle.slug
        entry["run_summary"] = run_record
        results.append(entry)
    _record_verifier_feedback(plan, results)
    overall = _overall_pass(results)
    return {"sid": sid, "overall_pass": overall, "results": results}


def main() -> None:
    args = parse_args()
    if args.log:
        result = _evaluate_single(args.log, args.vuln_id)
        report = {
            "sid": args.sid,
            "overall_pass": result.get("verify_pass"),
            "results": [result],
        }
    else:
        report = _evaluate_all(args.sid)
    reports_dir = ensure_dir(get_artifacts_dir(args.sid) / "reports")
    output_path = reports_dir / "evals.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    LOGGER.info("Evaluation result saved to %s", output_path)


def _register_runtime_rules(plan: Dict[str, Any]) -> None:
    metadata_root = Path(plan["paths"]["metadata"])
    runtime_dir = metadata_root / "runtime_rules"
    if not runtime_dir.exists():
        return
    env_key = "VULD_RUNTIME_RULE_DIRS"
    existing = os.environ.get(env_key, "")
    parts = [p for p in existing.split(os.pathsep) if p]
    path_str = str(runtime_dir)
    if path_str not in parts:
        parts.append(path_str)
        os.environ[env_key] = os.pathsep.join(parts)


def _record_verifier_feedback(plan: Dict[str, Any], results: List[Dict[str, Any]]) -> None:
    metadata_dir = Path(plan["paths"]["metadata"])
    loop_state = metadata_dir / "loop_state.json"
    loop_count = 0
    if loop_state.exists():
        try:
            state = json.loads(loop_state.read_text(encoding="utf-8"))
            loop_count = int(state.get("current_loop", 0))
        except json.JSONDecodeError:
            loop_count = 0
    timestamp = datetime.now(timezone.utc).isoformat()
    for entry in results:
        if entry.get("verify_pass"):
            continue
        reason = entry.get("evidence") or "PoC verification failed"
        fix_hint = _derive_fix_hint(reason)
        append_memory(
            ReflexionRecord(
                sid=plan["sid"],
                loop_count=loop_count,
                stage="VERIFIER",
                reason=reason,
                remediation_hint=fix_hint,
                blocking=True,
                metadata={
                    "bundle": entry.get("slug", ""),
                    "log_path": entry.get("log_path", ""),
                },
                timestamp=timestamp,
            )
        )


def _derive_fix_hint(reason: str) -> str:
    text = reason.lower()
    if "signature missing" in text:
        return "Ensure app/PoC prints the success signature and flag token into run.log"
    if "flag" in text and "missing" in text:
        return "Expose the expected flag token during successful exploitation"
    return "Inspect run.log and adjust PoC/app to satisfy the rule-defined success signature"


if __name__ == "__main__":
    main()
