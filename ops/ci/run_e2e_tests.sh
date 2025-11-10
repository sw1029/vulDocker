#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CASES_DIR="${REPO_ROOT}/tests/e2e/cases"

if [[ ! -d "${CASES_DIR}" ]]; then
  echo "[E2E] case directory not found: ${CASES_DIR}" >&2
  exit 1
fi

missing=0
for case_dir in "${CASES_DIR}"/*; do
  [[ -d "${case_dir}" ]] || continue
  if [[ ! -f "${case_dir}/requirement.yml" ]]; then
    echo "[E2E] missing requirement.yml in ${case_dir}" >&2
    missing=1
  fi
  if [[ ! -f "${case_dir}/expectations.json" ]]; then
    echo "[E2E] missing expectations.json in ${case_dir}" >&2
    missing=1
  fi
done

if [[ ${missing} -ne 0 ]]; then
  echo "[E2E] case schema validation failed" >&2
  exit 1
fi

cd "${REPO_ROOT}"

if [[ -z "${VULD_RUN_E2E:-}" ]]; then
  echo "[E2E] VULD_RUN_E2E not set. Skipping heavy regression tests." >&2
  exit 0
fi

pytest -m e2e "$@"
