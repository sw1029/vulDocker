#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
REQ_FILE="${VULD_BASE_REQUIREMENT_FILE:-${REPO_ROOT}/inputs/base_requirement.yml}"
RUN_CASE_SCRIPT="${VULD_BASE_RUN_CASE_SCRIPT:-${SCRIPT_DIR}/run_case.sh}"
MODE="${1:-deterministic}"

if [[ $# -gt 1 ]]; then
  echo "Usage: ./ops/ci/run_base_example.sh [mode]" >&2
  exit 1
fi

if [[ ! -f "${REQ_FILE}" ]]; then
  echo "[BASE] requirement file not found: ${REQ_FILE}" >&2
  exit 1
fi

if [[ ! -f "${RUN_CASE_SCRIPT}" ]]; then
  echo "[BASE] run_case helper not found: ${RUN_CASE_SCRIPT}" >&2
  exit 1
fi

"${RUN_CASE_SCRIPT}" "${REQ_FILE}" "${MODE}"
