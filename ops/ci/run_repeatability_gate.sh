#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PYTHON_BIN="${VULD_REPEAT_PYTHON_BIN:-python}"
DEFAULT_CASE_DIR_INPUT="${REPO_ROOT}/tests/e2e/cases/cwe-89-basic"
ARG1="${1:-}"
ARG2="${2:-}"
ARG3="${3:-}"
ARG4="${4:-}"

if [[ -z "${ARG1}" ]]; then
  CASE_DIR_INPUT="${DEFAULT_CASE_DIR_INPUT}"
  ATTEMPTS="3"
  MODE="deterministic"
  OUTPUT_DIR="${REPO_ROOT}/tests/e2e/outputs/$(basename "${CASE_DIR_INPUT}")-repeatability"
elif [[ "${ARG1}" =~ ^[0-9]+$ ]]; then
  # Backward-compatible shorthand: attempts [mode] [output_dir]
  CASE_DIR_INPUT="${DEFAULT_CASE_DIR_INPUT}"
  ATTEMPTS="${ARG1}"
  MODE="${ARG2:-deterministic}"
  OUTPUT_DIR="${ARG3:-${REPO_ROOT}/tests/e2e/outputs/$(basename "${CASE_DIR_INPUT}")-repeatability}"
else
  CASE_DIR_INPUT="${ARG1}"
  ATTEMPTS="${ARG2:-3}"
  MODE="${ARG3:-deterministic}"
  OUTPUT_DIR="${ARG4:-${REPO_ROOT}/tests/e2e/outputs/$(basename "${CASE_DIR_INPUT}")-repeatability}"
fi

if [[ "${CASE_DIR_INPUT}" = /* ]]; then
  CASE_DIR="${CASE_DIR_INPUT}"
elif [[ -d "${REPO_ROOT}/tests/e2e/cases/${CASE_DIR_INPUT}" ]]; then
  CASE_DIR="${REPO_ROOT}/tests/e2e/cases/${CASE_DIR_INPUT}"
else
  CASE_DIR="${REPO_ROOT}/${CASE_DIR_INPUT}"
fi

if [[ ! -d "${CASE_DIR}" ]]; then
  echo "[E2E] case directory not found: ${CASE_DIR}" >&2
  exit 1
fi

cd "${REPO_ROOT}"
REPORT_PATH="${OUTPUT_DIR}/repeatability_report.json"
repeat_rc=0
"${PYTHON_BIN}" -m tests.e2e.repeat_case \
  --case "${CASE_DIR}" \
  --attempts "${ATTEMPTS}" \
  --mode "${MODE}" \
  --output-dir "${OUTPUT_DIR}" \
  --no-snapshot || repeat_rc=$?

if [[ ! -f "${REPORT_PATH}" ]]; then
  echo "[E2E] repeatability report missing: ${REPORT_PATH}" >&2
  exit "${repeat_rc:-1}"
fi

report_rc=0
"${PYTHON_BIN}" - <<'PY' "${REPORT_PATH}" || report_rc=$?
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
print("[E2E] Repeatability summary:", json.dumps(
    {
        "case": payload.get("case"),
        "attempt_count": payload.get("attempt_count"),
        "success_count": payload.get("success_count"),
        "failure_count": payload.get("failure_count"),
        "passed": payload.get("passed"),
        "failure_fingerprints": payload.get("failure_fingerprints"),
        "failure_stages": payload.get("failure_stages"),
        "guard_error_codes": payload.get("guard_error_codes"),
        "report_path": str(path),
    },
    ensure_ascii=False,
))
if not payload.get("passed"):
    raise SystemExit(1)
PY

if [[ "${repeat_rc}" -ne 0 ]]; then
  exit "${repeat_rc}"
fi

exit "${report_rc}"
