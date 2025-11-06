#!/usr/bin/env python3
"""Simple planner for MVP SQLi scenario."""
import argparse
import hashlib
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[0].parent


def load_requirement(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def compute_sid(payload: dict) -> str:
    base = payload.get("scenario_id") or "sid-" + hashlib.sha256(
        json.dumps(
            {
                "requirement": payload.get("requirement"),
                "language": payload.get("language"),
                "framework": payload.get("framework"),
                "database": payload.get("database"),
                "pattern_id": payload.get("pattern_id"),
                "seed": payload.get("seed"),
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:12]
    return base


def write_plan(sid: str, plan: dict) -> Path:
    meta_dir = ROOT / "metadata" / sid
    meta_dir.mkdir(parents=True, exist_ok=True)
    plan_path = meta_dir / "plan.json"
    with plan_path.open("w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)
    return plan_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan MVP scenario execution")
    parser.add_argument("--input", required=True, help="Path to requirement YAML (JSON)")
    args = parser.parse_args()

    requirement_path = Path(args.input)
    payload = load_requirement(requirement_path)
    sid = compute_sid(payload)

    plan = {
        "sid": sid,
        "requirement": payload.get("requirement"),
        "language": payload.get("language"),
        "framework": payload.get("framework"),
        "database": payload.get("database"),
        "pattern_id": payload.get("pattern_id"),
        "seed": payload.get("seed", 42),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "workspace": str((ROOT / "workspaces" / sid).resolve()),
    }

    path = write_plan(sid, plan)
    print(f"[PLAN] Scenario {sid} planned. Metadata: {path}")


if __name__ == "__main__":
    main()
