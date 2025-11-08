"""PoC verifier for the MVP SQLi scenario."""
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
from common.run_matrix import artifacts_dir_for_bundle, load_vuln_bundles

LOGGER = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate SQLi PoC logs")
    parser.add_argument("--sid", required=True)
    parser.add_argument("--log", type=Path, help="Path to run log (optional)")
    return parser.parse_args()


def evaluate_log(log_path: Path) -> dict:
    if not log_path.exists():
        raise FileNotFoundError(f"Log file not found: {log_path}")
    content = log_path.read_text(encoding="utf-8")
    success = "SQLi SUCCESS" in content
    return {
        "verify_pass": success,
        "evidence": "SQLi SUCCESS" if success else "Signature missing",
        "log_path": str(log_path),
    }


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
    for entry in results:
        if entry.get("status") != "evaluated":
            return False
        if not entry.get("verify_pass"):
            return False
    return True


def main() -> None:
    args = parse_args()
    if args.log:
        result = evaluate_log(args.log)
        report = {
            "sid": args.sid,
            "overall_pass": result["verify_pass"],
            "results": [result],
        }
    else:
        plan = load_plan(args.sid)
        bundles = load_vuln_bundles(plan)
        run_index = _load_run_index(args.sid)
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
                    entry = evaluate_log(log_path)
                    entry["status"] = "evaluated"
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
        report = {"sid": args.sid, "overall_pass": overall, "results": results}
    reports_dir = ensure_dir(get_artifacts_dir(args.sid) / "reports")
    output_path = reports_dir / "evals.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    LOGGER.info("Evaluation result saved to %s", output_path)


if __name__ == "__main__":
    main()
