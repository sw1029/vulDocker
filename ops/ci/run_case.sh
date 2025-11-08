#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <requirement_yaml> [mode]" >&2
  exit 1
fi

REQ_PATH="$1"
MODE="${2:-deterministic}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
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
import orchestrator.plan as plan_module
from pathlib import Path
import sys
req = plan_module._load_requirement(Path(sys.argv[1]))
plan = plan_module.build_plan(req)
print(plan["sid"])
PY
)

echo "[CASE] SID=${SID}"
export SID

python agents/researcher/main.py --sid "${SID}" --mode "${MODE}"
python agents/generator/main.py --sid "${SID}" --mode "${MODE}"
python executor/runtime/docker_local.py --sid "${SID}" --build
python executor/runtime/docker_local.py --sid "${SID}" --run
python evals/poc_verifier/mvp_sqli.py --sid "${SID}"
python evals/diversity_metrics.py --sid "${SID}"
python orchestrator/pack.py --sid "${SID}"

python - <<'PY'
import json, os, pathlib
sid = os.environ["SID"]
root = pathlib.Path(".")
plan = json.loads((root / f"metadata/{sid}/plan.json").read_text(encoding="utf-8"))
evals = json.loads((root / f"artifacts/{sid}/reports/evals.json").read_text(encoding="utf-8"))
div = json.loads((root / f"artifacts/{sid}/reports/diversity.json").read_text(encoding="utf-8"))
summary = {
    "sid": sid,
    "variation_key": plan.get("variation_key"),
    "verify_pass": evals.get("verify_pass"),
    "evidence": evals.get("evidence"),
    "diversity": div.get("metrics"),
}
print("[CASE] Summary:", json.dumps(summary, indent=2))
PY

echo "[CASE] Artifacts -> artifacts/${SID}"
echo "[CASE] Metadata  -> metadata/${SID}"
