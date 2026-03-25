#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  cat >&2 <<'USAGE'
Usage:
  ./ops/ci/run_custom_vuln_example.sh <VULN_ID[,VULN_ID2,...]> [mode]
  ./ops/ci/run_custom_vuln_example.sh <VULN_ID1> <VULN_ID2> ... [--mode MODE]

Examples:
  ./ops/ci/run_custom_vuln_example.sh CWE-22
  ./ops/ci/run_custom_vuln_example.sh CWE-22,CWE-94 deterministic
  ./ops/ci/run_custom_vuln_example.sh CWE-22 CWE-94 --mode deterministic
USAGE
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BASE_REQ="${VULD_CUSTOM_BASE_REQUIREMENT_FILE:-${REPO_ROOT}/inputs/base_requirement.yml}"
RUN_CASE_SCRIPT="${VULD_CUSTOM_RUN_CASE_SCRIPT:-${SCRIPT_DIR}/run_case.sh}"

if [[ ! -f "${BASE_REQ}" ]]; then
  echo "[CUSTOM] base requirement not found: ${BASE_REQ}" >&2
  exit 1
fi

if [[ ! -f "${RUN_CASE_SCRIPT}" ]]; then
  echo "[CUSTOM] run_case helper not found: ${RUN_CASE_SCRIPT}" >&2
  exit 1
fi

MODE="deterministic"
declare -a TOKENS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      if [[ $# -lt 2 ]]; then
        echo "[CUSTOM] --mode requires value" >&2
        exit 1
      fi
      MODE="$2"
      shift 2
      ;;
    *)
      TOKENS+=("$1")
      shift
      ;;
  esac
done

if [[ ${#TOKENS[@]} -eq 0 ]]; then
  echo "[CUSTOM] at least one vuln id is required" >&2
  exit 1
fi

if [[ ${#TOKENS[@]} -eq 2 && "${TOKENS[1]}" != CWE-* && "${TOKENS[1]}" != cwe-* ]]; then
  # Backward compatible shorthand: "<vuln_csv> <mode>"
  MODE="${TOKENS[1]}"
  TOKENS=("${TOKENS[0]}")
fi

declare -a VULN_IDS=()
for token in "${TOKENS[@]}"; do
  IFS=',' read -r -a split_ids <<< "${token}"
  for raw in "${split_ids[@]}"; do
    trimmed="$(echo "${raw}" | xargs)"
    if [[ -n "${trimmed}" ]]; then
      VULN_IDS+=("${trimmed}")
    fi
  done
done

if [[ ${#VULN_IDS[@]} -eq 0 ]]; then
  echo "[CUSTOM] parsed vuln ids are empty" >&2
  exit 1
fi

TMP_REQ="$(mktemp "${REPO_ROOT}/inputs/custom_requirement_XXXXXX.yml")"
trap 'rm -f "${TMP_REQ}"' EXIT

python - "$BASE_REQ" "$TMP_REQ" "${VULN_IDS[@]}" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

base_path = Path(sys.argv[1])
out_path = Path(sys.argv[2])
vuln_ids = [item.strip() for item in sys.argv[3:] if item.strip()]

payload = yaml.safe_load(base_path.read_text(encoding="utf-8")) or {}
if not isinstance(payload, dict):
    raise SystemExit("base requirement must be a YAML object")

ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
if len(vuln_ids) == 1:
    payload["vuln_id"] = vuln_ids[0]
    payload.pop("vuln_ids", None)
    payload.pop("multi_vuln", None)
    payload["requirement_id"] = f"CUSTOM-{vuln_ids[0].upper()}-{ts}"
    payload["intent"] = f"Custom single vulnerability run for {vuln_ids[0]}"
else:
    payload["vuln_ids"] = vuln_ids
    payload["multi_vuln"] = True
    payload.pop("vuln_id", None)
    joined = "-".join(item.upper() for item in vuln_ids)
    payload["requirement_id"] = f"CUSTOM-MULTI-{joined}-{ts}"
    payload["intent"] = f"Custom multi vulnerability run for {', '.join(vuln_ids)}"

out_path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
print(json.dumps({"out_path": str(out_path), "vuln_ids": vuln_ids}, ensure_ascii=False))
PY

echo "[CUSTOM] Generated requirement: ${TMP_REQ}"
echo "[CUSTOM] VULN_IDS: ${VULN_IDS[*]}"
echo "[CUSTOM] MODE: ${MODE}"

"${RUN_CASE_SCRIPT}" "${TMP_REQ}" "${MODE}"
