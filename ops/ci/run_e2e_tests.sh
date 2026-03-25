#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CASES_DIR="${VULD_E2E_CASES_DIR:-${REPO_ROOT}/tests/e2e/cases}"
CONFIG_PATH="${VULD_E2E_CONFIG_PATH:-${REPO_ROOT}/config/api_keys.ini}"
PYTHON_BIN="${VULD_E2E_PYTHON_BIN:-python}"
PYTEST_BIN="${VULD_E2E_PYTEST_BIN:-pytest}"
REPEAT_HELPER="${VULD_E2E_REPEAT_HELPER:-${REPO_ROOT}/ops/ci/run_repeatability_gate.sh}"

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

if ! command -v "${PYTEST_BIN}" >/dev/null 2>&1; then
  echo "[E2E] pytest binary not found: ${PYTEST_BIN}" >&2
  exit 1
fi

if [[ -n "${VULD_E2E_REQUIRE_TAVILY:-}" ]]; then
  TAVILY_KEY="${VUL_WEB_SEARCH_API_KEY:-}"
  if [[ -z "${TAVILY_KEY}" && -f "${CONFIG_PATH}" ]]; then
    TAVILY_KEY="$("${PYTHON_BIN}" - <<'PY' "${CONFIG_PATH}"
import configparser
import sys
from pathlib import Path

path = Path(sys.argv[1])
parser = configparser.ConfigParser()
parser.read(path, encoding="utf-8")
print((parser.get("tavily", "api_key", fallback="") or "").strip(), end="")
PY
)"
  fi
  if [[ -z "${TAVILY_KEY}" ]]; then
    echo "[E2E] VULD_E2E_REQUIRE_TAVILY=1 but no Tavily API key is configured." >&2
    exit 1
  fi
fi

if [[ -n "${VULD_RUN_E2E_REPEAT:-}" ]]; then
  export VULD_SKIP_REPEATABILITY_PYTEST=1
fi

"${PYTEST_BIN}" -m e2e "$@"

if [[ -n "${VULD_RUN_E2E_REPEAT:-}" ]]; then
  REPEAT_ATTEMPTS="${VULD_E2E_REPEAT_ATTEMPTS:-3}"
  REPEAT_MODE="${VULD_E2E_REPEAT_MODE:-deterministic}"
  REPEAT_CASE_DIR="${VULD_E2E_REPEAT_CASE_DIR:-${CASES_DIR}/cwe-89-basic}"
  REPEAT_CASE_SLUG="$(basename "${REPEAT_CASE_DIR}")"
  REPEAT_OUTPUT_DIR="${VULD_E2E_REPEAT_OUTPUT_DIR:-${REPO_ROOT}/tests/e2e/outputs/${REPEAT_CASE_SLUG}-repeatability}"
  if [[ ! -x "${REPEAT_HELPER}" ]]; then
    echo "[E2E] repeatability helper not found: ${REPEAT_HELPER}" >&2
    exit 1
  fi
  echo "[E2E] Running repeatability gate: case=${REPEAT_CASE_SLUG} attempts=${REPEAT_ATTEMPTS} mode=${REPEAT_MODE}"
  "${REPEAT_HELPER}" "${REPEAT_CASE_DIR}" "${REPEAT_ATTEMPTS}" "${REPEAT_MODE}" "${REPEAT_OUTPUT_DIR}"
fi
