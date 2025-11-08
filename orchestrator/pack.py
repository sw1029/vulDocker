"""PACK stage consolidating artifacts."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.logging import get_logger
from common.paths import ensure_dir, get_artifacts_dir, get_metadata_dir, get_workspace_dir

LOGGER = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pack artifacts for a SID")
    parser.add_argument("--sid", required=True, help="Scenario ID")
    return parser.parse_args()


def load_plan(sid: str) -> dict:
    plan_path = get_metadata_dir(sid) / "plan.json"
    if not plan_path.exists():
        raise FileNotFoundError(f"Plan file missing for {sid}: {plan_path}")
    return json.loads(plan_path.read_text(encoding="utf-8"))


def snapshot_workspace(sid: str) -> Path:
    workspace = get_workspace_dir(sid)
    destination = ensure_dir(get_artifacts_dir(sid) / "build" / "source_snapshot")
    target = destination / "app"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(workspace, target)
    LOGGER.info("Workspace snapshot copied to %s", target)
    return target


def write_manifest(sid: str, plan: dict) -> Path:
    metadata_dir = get_metadata_dir(sid)
    manifest = {
        "sid": sid,
        "packed_at": datetime.now(timezone.utc).isoformat(),
        "variation_key": plan.get("variation_key"),
        "paths": plan.get("paths"),
        "status": "success",
    }
    manifest_path = metadata_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    LOGGER.info("Manifest written to %s", manifest_path)
    return manifest_path


def main() -> None:
    args = parse_args()
    plan = load_plan(args.sid)
    snapshot_workspace(args.sid)
    write_manifest(args.sid, plan)


if __name__ == "__main__":
    main()
