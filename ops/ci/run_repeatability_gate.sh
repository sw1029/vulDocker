#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CASE_DIR_INPUT="${1:-${REPO_ROOT}/tests/e2e/cases/cwe-89-basic}"
ATTEMPTS="${2:-3}"
MODE="${3:-deterministic}"
OUTPUT_DIR="${4:-${REPO_ROOT}/tests/e2e/outputs/$(basename "${CASE_DIR_INPUT}")-repeatability}"

if [[ "${CASE_DIR_INPUT}" = /* ]]; then
  CASE_DIR="${CASE_DIR_INPUT}"
else
  CASE_DIR="${REPO_ROOT}/${CASE_DIR_INPUT}"
fi

if [[ ! -d "${CASE_DIR}" ]]; then
  echo "[E2E] case directory not found: ${CASE_DIR}" >&2
  exit 1
fi

cd "${REPO_ROOT}"
python -m tests.e2e.repeat_case \
  --case "${CASE_DIR}" \
  --attempts "${ATTEMPTS}" \
  --mode "${MODE}" \
  --output-dir "${OUTPUT_DIR}" \
  --no-snapshot
