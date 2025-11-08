#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

if ! command -v docker >/dev/null 2>&1; then
  echo "[SMOKE] ERROR: docker binary not found" >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "[SMOKE] ERROR: unable to talk to Docker daemon (check permissions)" >&2
  exit 1
fi

SNAPSHOT=$(ls -td rag/index/rag-snap-* 2>/dev/null | head -1 | xargs -n1 basename || true)
SNAPSHOT=${SNAPSHOT:-mvp-sample}
echo "[SMOKE] Using snapshot: ${SNAPSHOT}"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

cat >"${TMP_DIR}/smoke_det.yml" <<EOF
requirement_id: SMOKE-DET-$(date +%s)
vuln_id: CWE-89
intent: Regression smoke (deterministic)
language: python
framework: flask
seed: 12001
retriever_commit: "stub"
corpus_snapshot: ${SNAPSHOT}
pattern_id: sqli-string-concat
deps_digest: sha256:placeholder
base_image_digest: sha256:python311
allow_intentional_vuln: true
runtime:
  base_image: python:3.11-slim
  package_manager: pip
  allow_external_db: false
variation_key:
  mode: deterministic
  self_consistency_k: 1
  pattern_pool_seed: 12001
EOF

cat >"${TMP_DIR}/smoke_diverse.yml" <<EOF
requirement_id: SMOKE-DIV-$(date +%s)
vuln_id: CWE-89
intent: Regression smoke (diverse + self-consistency)
language: python
framework: flask
seed: 12002
retriever_commit: "stub"
corpus_snapshot: ${SNAPSHOT}
pattern_id: sqli-string-concat
deps_digest: sha256:placeholder
base_image_digest: sha256:python311
allow_intentional_vuln: true
runtime:
  base_image: python:3.11-slim
  package_manager: pip
  allow_external_db: false
variation_key:
  mode: diverse
  self_consistency_k: 4
  pattern_pool_seed: 12002
EOF

SID_RESULT=""

run_flow() {
  local input_file="$1"
  local mode="$2"

  echo "[SMOKE] PLAN -> ${input_file}"
  python orchestrator/plan.py --input "${input_file}"
  local sid
  sid=$(python - <<'PY' "${input_file}"
import sys
from pathlib import Path
import orchestrator.plan as plan
req = plan._load_requirement(Path(sys.argv[1]))
plan_dict = plan.build_plan(req)
print(plan_dict["sid"])
PY
)
  echo "[SMOKE] SID=${sid}"

  python agents/researcher/main.py --sid "${sid}" --mode "${mode}"
  python agents/generator/main.py --sid "${sid}" --mode "${mode}"
  python executor/runtime/docker_local.py --sid "${sid}" --build
  python executor/runtime/docker_local.py --sid "${sid}" --run
  python evals/poc_verifier/mvp_sqli.py --sid "${sid}"
  python evals/diversity_metrics.py --sid "${sid}"
  python orchestrator/pack.py --sid "${sid}"

  SID_CURRENT="${sid}" python - <<'PY'
import json, os, pathlib
sid = os.environ["SID_CURRENT"]
root = pathlib.Path(".")
plan = json.loads((root / f"metadata/{sid}/plan.json").read_text(encoding="utf-8"))
evals = json.loads((root / f"artifacts/{sid}/reports/evals.json").read_text(encoding="utf-8"))
div = json.loads((root / f"artifacts/{sid}/reports/diversity.json").read_text(encoding="utf-8"))
gen = json.loads((root / f"metadata/{sid}/generator_candidates.json").read_text(encoding="utf-8"))
candidate_count = len(gen.get("candidates", []))
print(f"[SMOKE] variation_key={plan.get('variation_key')}")
print(f"[SMOKE] verify_pass={evals.get('verify_pass')} evidence={evals.get('evidence')}")
print(f"[SMOKE] diversity_metrics={div.get('metrics')}")
print(f"[SMOKE] template_candidates={candidate_count}")
assert evals.get("verify_pass"), "PoC verification failed"
PY

  echo "[SMOKE] Artifacts: artifacts/${sid}"
  echo "[SMOKE] Metadata : metadata/${sid}"
  SID_RESULT="${sid}"
}

run_flow "${TMP_DIR}/smoke_det.yml" "deterministic"
SID_DET="${SID_RESULT}"
run_flow "${TMP_DIR}/smoke_diverse.yml" "diverse"
SID_DIV="${SID_RESULT}"

SID_DET="${SID_DET}" SID_DIV="${SID_DIV}" python - <<'PY'
import json, os, pathlib
root = pathlib.Path(".")
sid_det = os.environ["SID_DET"]
sid_div = os.environ["SID_DIV"]
div = json.loads((root / f"artifacts/{sid_div}/reports/diversity.json").read_text(encoding="utf-8"))
det = json.loads((root / f"artifacts/{sid_det}/reports/diversity.json").read_text(encoding="utf-8"))
det_count = det["metrics"]["candidate_count"]
div_count = div["metrics"]["candidate_count"]
print(f"[SMOKE] deterministic candidate_count={det_count}")
print(f"[SMOKE] diverse candidate_count={div_count}")
assert det_count == 1, "Deterministic run should sample exactly one template"
assert div_count >= 2, "Diverse run should keep >=2 template candidates"
print("[SMOKE] Regression suite passed")
PY
