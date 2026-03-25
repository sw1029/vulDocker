#!/usr/bin/env bash
set -euo pipefail

PYTEST_BIN="${VULD_FOCUSED_NO_DOCKER_PYTEST_BIN:-pytest}"

if ! command -v "${PYTEST_BIN}" >/dev/null 2>&1; then
  echo "[FOCUSED] pytest binary not found: ${PYTEST_BIN}" >&2
  exit 1
fi

"${PYTEST_BIN}" -q \
  tests/test_name_only_helpers.py \
  tests/test_pack_promotion.py \
  tests/test_repeatability_gate.py \
  tests/test_support_extract.py \
  tests/e2e/test_support_workflow.py \
  tests/e2e/test_case_matrix_rollup.py \
  "$@"
