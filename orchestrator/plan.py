"""Plan stage CLI.

Creates Scenario ID, metadata records, and workspace scaffolding using the
inputs defined in docs/milestones/mvp_runbook.md."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.logging import get_logger
from common.paths import ensure_dir, get_artifacts_dir, get_metadata_dir, get_workspace_dir
from common.sid import SID_FIELDS, compute_sid

LOGGER = get_logger(__name__)

try:  # pragma: no cover - optional dep
    import yaml
except Exception:  # pragma: no cover
    yaml = None


def _load_requirement(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text)
    LOGGER.warning("PyYAML not available; attempting JSON parsing")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Requirement file is YAML. Install PyYAML (pip install pyyaml) or "
            "provide JSON input."
        ) from exc


def _prompt_hash() -> str:
    return hashlib.sha256(b"generator-prompt-v1").hexdigest()


def _default_components(requirement: Dict[str, Any]) -> Dict[str, str]:
    components = {
        "model_version": requirement.get("model_version", "gpt-4.1-mini"),
        "prompt_hash": _prompt_hash(),
        "seed": str(requirement.get("seed", 0)),
        "retriever_commit": requirement.get("retriever_commit", "unknown"),
        "corpus_snapshot": requirement.get("corpus_snapshot", "mvp-sample"),
        "pattern_id": requirement.get("pattern_id", "unknown"),
        "deps_digest": requirement.get("deps_digest", "unknown"),
        "base_image_digest": requirement.get("base_image_digest", "unknown"),
    }
    return components


def build_plan(requirement: Dict[str, Any]) -> Dict[str, Any]:
    sid = compute_sid(_default_components(requirement))
    timestamp = datetime.now(timezone.utc).isoformat()
    plan = {
        "sid": sid,
        "created_at": timestamp,
        "requirement": requirement,
        "variation_key": requirement.get("variation_key", {"mode": "deterministic"}),
        "state": "PLAN",
        "paths": {
            "metadata": str(get_metadata_dir(sid)),
            "workspace": str(get_workspace_dir(sid)),
            "artifacts": str(get_artifacts_dir(sid)),
        },
    }
    return plan


def write_plan(plan: Dict[str, Any]) -> Path:
    metadata_dir = ensure_dir(Path(plan["paths"]["metadata"]))
    ensure_dir(Path(plan["paths"]["workspace"]))
    ensure_dir(Path(plan["paths"]["artifacts"]))
    plan_path = metadata_dir / "plan.json"
    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    return plan_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan stage for MVP")
    parser.add_argument("--input", required=True, type=Path, help="Requirement YAML/JSON file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    requirement = _load_requirement(args.input)
    missing_fields = [field for field in SID_FIELDS if field not in requirement]
    if missing_fields:
        LOGGER.info("Missing optional SID components will use defaults: %s", missing_fields)
    plan = build_plan(requirement)
    plan_path = write_plan(plan)
    LOGGER.info("Scenario %s planned. Metadata written to %s", plan["sid"], plan_path)


if __name__ == "__main__":
    main()
