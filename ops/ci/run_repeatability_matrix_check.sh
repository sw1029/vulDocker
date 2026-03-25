#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
source "${SCRIPT_DIR}/lib_cases_output_roots.sh"
source "${SCRIPT_DIR}/lib_repeatability_chain_runner.sh"
REPEAT_HELPER="${VULD_REPEAT_MATRIX_REPEAT_HELPER:-${SCRIPT_DIR}/run_repeatability_chain.sh}"
PYTHON_BIN="${VULD_REPEAT_MATRIX_PYTHON_BIN:-python}"
resolve_cases_output_roots \
  "VULD_REPEAT_MATRIX" \
  "${REPO_ROOT}" \
  "/tmp/vuld_repeatability_matrix_check" \
  "CASES_ROOT" \
  "OUTPUT_ROOT"
REPEAT_MODE="${VULD_REPEAT_MATRIX_MODE:-deterministic}"
REPEAT_ATTEMPTS="${VULD_REPEAT_MATRIX_ATTEMPTS:-2}"
NO_SNAPSHOT="${VULD_REPEAT_MATRIX_NO_SNAPSHOT:-0}"
ALLOW_REPEAT_FAILURE_WITH_REPORT="${VULD_REPEAT_MATRIX_ALLOW_REPEAT_FAILURE_WITH_REPORT:-0}"
PERMISSION_ARTIFACT_NAME="${VULD_REPEAT_MATRIX_PERMISSION_ARTIFACT_NAME:-docker_permission_artifact.txt}"
PERMISSION_SUMMARY_NAME="${VULD_REPEAT_MATRIX_PERMISSION_SUMMARY_NAME:-permission_artifact_summary.json}"
DOCKER_RETRY_COUNT="${VULD_REPEAT_MATRIX_DOCKER_RETRY_COUNT:-}"
DOCKER_RETRY_DELAY_SEC="${VULD_REPEAT_MATRIX_DOCKER_RETRY_DELAY_SEC:-}"

if [[ "$#" -lt 1 ]]; then
  echo "usage: ops/ci/run_repeatability_matrix_check.sh <case-slug-or-dir> [<case-slug-or-dir> ...]" >&2
  exit 1
fi

repeatability_run_helper_and_postprocess \
  RUN_DIRS \
  PERMISSION_ARTIFACT_CASES \
  PERMISSION_SUMMARY_PATH \
  "${REPEAT_HELPER}" \
  "${PYTHON_BIN}" \
  "${CASES_ROOT}" \
  "${OUTPUT_ROOT}" \
  "${REPEAT_MODE}" \
  "${REPEAT_ATTEMPTS}" \
  "${NO_SNAPSHOT}" \
  "${ALLOW_REPEAT_FAILURE_WITH_REPORT}" \
  "${PERMISSION_ARTIFACT_NAME}" \
  "${PERMISSION_SUMMARY_NAME}" \
  "${DOCKER_RETRY_COUNT}" \
  "${DOCKER_RETRY_DELAY_SEC}" \
  "MATRIX" \
  "$@"

MATRIX_OUT="${OUTPUT_ROOT}/matrix_report.json"
echo "[MATRIX] build matrix report -> ${MATRIX_OUT}"
"${PYTHON_BIN}" tests/e2e/matrix_report.py "${RUN_DIRS[@]}" --output "${MATRIX_OUT}"

echo "[MATRIX] completed"
echo "[MATRIX] matrix_out=${MATRIX_OUT}"
echo "[MATRIX] permission_summary_out=${PERMISSION_SUMMARY_PATH}"
