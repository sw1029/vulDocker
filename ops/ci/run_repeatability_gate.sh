#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CASE_DIR="${REPO_ROOT}/tests/e2e/cases/cwe-89-basic"
ATTEMPTS="${1:-3}"
MODE="${2:-deterministic}"
OUTPUT_DIR="${3:-${REPO_ROOT}/tests/e2e/outputs/cwe-89-repeatability}"

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
