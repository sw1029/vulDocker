#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <requirement_yaml> [mode]" >&2
  exit 1
fi

REQ_PATH="$1"
MODE="${2:-deterministic}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

if ! command -v docker >/dev/null 2>&1; then
  echo "[CASE] ERROR: docker binary not found" >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "[CASE] ERROR: cannot reach Docker daemon. Grant permissions before running." >&2
  exit 1
fi

if [[ ! -f "${REQ_PATH}" ]]; then
  echo "[CASE] ERROR: requirement file not found: ${REQ_PATH}" >&2
  exit 1
fi

echo "[CASE] Planning ${REQ_PATH}"
python orchestrator/plan.py --input "${REQ_PATH}"

SID=$(python - "$REQ_PATH" <<'PY'
from pathlib import Path
import sys
import orchestrator.plan as plan_module
from common.schema import normalize_requirement
req = plan_module._load_requirement(Path(sys.argv[1]))
norm = normalize_requirement(req)
plan = plan_module.build_plan(norm)
print(plan["sid"])
PY
)

echo "[CASE] SID=${SID}"
export SID

PIPE_RC=0
python orchestrator/run_pipeline.py --sid "${SID}" --mode "${MODE}" || PIPE_RC=$?

python - <<'PY'
import json, os, pathlib, sys
sid = os.environ["SID"]
root = pathlib.Path(".")
manifest_path = root / f"metadata/{sid}/manifest.json"
if not manifest_path.exists():
    print("[CASE] Summary: manifest missing at", manifest_path, file=sys.stderr)
    raise SystemExit(0)
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
bundles = []
for entry in manifest.get("bundles", []):
    eval_result = entry.get("artifacts", {}).get("eval_result") or {}
    run_summary = entry.get("artifacts", {}).get("run_summary") or {}
    bundles.append(
        {
            "vuln_id": entry.get("vuln_id"),
            "slug": entry.get("slug"),
            "eval_pass": eval_result.get("verify_pass"),
            "run_passed": run_summary.get("run_passed"),
            "error": run_summary.get("error"),
            "network_mode": run_summary.get("network_mode"),
            "sidecars": run_summary.get("sidecars"),
        }
    )
summary = {
    "sid": sid,
    "overall_pass": (manifest.get("reports", {}) or {}).get("evals", {}).get("overall_pass"),
    "policy": manifest.get("policy"),
    "bundles": bundles,
}
print("[CASE] Summary:", json.dumps(summary, indent=2, ensure_ascii=False))
PY

echo "[CASE] Artifacts -> artifacts/${SID}"
echo "[CASE] Metadata  -> metadata/${SID}"
exit "${PIPE_RC}"
