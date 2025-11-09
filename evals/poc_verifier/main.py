"""Generic PoC verifier entry point using plugin registry."""
from __future__ import annotations

import argparse
import json
import sys
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


if __name__ == "__main__":
    main()
