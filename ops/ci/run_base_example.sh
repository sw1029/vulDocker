#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
REQ_FILE="${REPO_ROOT}/inputs/base_requirement.yml"

if [[ ! -f "${REQ_FILE}" ]]; then
  echo "[BASE] requirement file not found: ${REQ_FILE}" >&2
  exit 1
fi

bash "${SCRIPT_DIR}/run_case.sh" "${REQ_FILE}" deterministic
