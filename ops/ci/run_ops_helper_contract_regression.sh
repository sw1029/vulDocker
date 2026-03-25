#!/usr/bin/env bash
set -euo pipefail

PYTEST_BIN="${VULD_OPS_HELPER_PYTEST_BIN:-pytest}"
TEST_GLOB="${VULD_OPS_HELPER_TEST_GLOB:-tests/test_ops_ci_*.py}"
PRINT_BUNDLE="${VULD_OPS_HELPER_PRINT_BUNDLE:-0}"

if ! command -v "${PYTEST_BIN}" >/dev/null 2>&1; then
  echo "[OPS-HELPERS] pytest binary not found: ${PYTEST_BIN}" >&2
  exit 1
fi

shopt -s nullglob
TEST_FILES=(${TEST_GLOB})
shopt -u nullglob

if [[ "${#TEST_FILES[@]}" -eq 0 ]]; then
  echo "[OPS-HELPERS] no helper regression tests found under ${TEST_GLOB}" >&2
  exit 1
fi

echo "[OPS-HELPERS] bundle_size=${#TEST_FILES[@]}"
if [[ "${PRINT_BUNDLE}" = "1" ]]; then
  printf '%s\n' "${TEST_FILES[@]}"
fi

"${PYTEST_BIN}" -q "${TEST_FILES[@]}" "$@"
