"""Deterministic harness audit for pipeline governance artifacts."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.paths import get_metadata_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit harness governance artifacts for a SID")
    parser.add_argument("--sid", required=True)
    return parser.parse_args()


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _category_score(name: str, passed: bool, detail: str) -> Dict[str, Any]:
    return {
        "category": name,
        "passed": bool(passed),
        "score": 100 if passed else 0,
        "detail": detail,
    }


def _audit_manifest(manifest: Dict[str, Any], metadata_dir: Path) -> Tuple[Dict[str, Any], int]:
    action_summary = manifest.get("action_trace_summary") if isinstance(manifest.get("action_trace_summary"), dict) else {}
    gate_summary = manifest.get("stage_gate_summary") if isinstance(manifest.get("stage_gate_summary"), dict) else {}
    observation_summary = manifest.get("observation_summary") if isinstance(manifest.get("observation_summary"), dict) else {}
    snapshot_path = metadata_dir / "canonical_snapshot.json"
    categories = [
        _category_score(
            "selection_and_action_trace",
            int(action_summary.get("total_actions") or 0) > 0,
            f"total_actions={int(action_summary.get('total_actions') or 0)}",
        ),
        _category_score(
            "stage_gate_governance",
            int(gate_summary.get("total_gates") or 0) > 0,
            f"total_gates={int(gate_summary.get('total_gates') or 0)}",
        ),
        _category_score(
            "canonical_snapshot",
            snapshot_path.exists(),
            f"canonical_snapshot_exists={snapshot_path.exists()}",
        ),
        _category_score(
            "observation_ledger",
            int(observation_summary.get("total_observations") or 0) > 0,
            f"total_observations={int(observation_summary.get('total_observations') or 0)}",
        ),
        _category_score(
            "oracle_execution_parity",
            bool(str(manifest.get("oracle_execution_parity") or "").strip()),
            f"oracle_execution_parity={str(manifest.get('oracle_execution_parity') or '').strip() or 'missing'}",
        ),
        _category_score(
            "review_evidence_surface",
            bool(manifest.get("verification_summary")) and bool(manifest.get("reports")),
            "verification_summary and reports present",
        ),
    ]
    overall = round(sum(item["score"] for item in categories) / max(1, len(categories)))
    failing = [item["category"] for item in categories if not item["passed"]]
    top_actions = []
    first_failure = action_summary.get("first_failure_action")
    if isinstance(first_failure, dict) and first_failure:
        top_actions.append(first_failure)
    return (
        {
            "schema_version": "harness_audit@0.1",
            "audited_at": datetime.now(timezone.utc).isoformat(),
            "overall_score": overall,
            "categories": categories,
            "failing_checks": failing,
            "top_actions": top_actions,
            "recommended_rerun_lanes": ["focused-no-docker", "measured-gate"] if failing else [],
        },
        overall,
    )


def main() -> None:
    args = parse_args()
    metadata_dir = get_metadata_dir(args.sid)
    manifest = _load_json(metadata_dir / "manifest.json")
    if not manifest:
        manifest = _load_json(metadata_dir / "failure_manifest.json")
    audit, overall = _audit_manifest(manifest, metadata_dir)
    output_path = metadata_dir / "harness_audit.json"
    output_path.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"sid": args.sid, "overall_score": overall, "path": str(output_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
