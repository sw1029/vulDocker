#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
source "${SCRIPT_DIR}/lib_operator_cases_output_roots.sh"
source "${SCRIPT_DIR}/lib_operator_direct_case_check.sh"
operator_resolve_cases_output_roots \
  "VULD_LOW_COST" \
  "${REPO_ROOT}" \
  "/tmp/vuld_low_cost_no_docker" \
  "CASES_ROOT" \
  "OUTPUT_ROOT"

operator_run_direct_triple_check \
  "VULD_LOW_COST" \
  "${SCRIPT_DIR}" \
  "${CASES_ROOT}" \
  "${OUTPUT_ROOT}" \
  "VULD_LOW_COST_NAMED_DIRECT_HELPER" \
  "VULD_LOW_COST_PRESET_HELPER" \
  "VULD_LOW_COST_DIRECT_HELPER" \
  "VULD_LOW_COST_STRICT_NO_REMOTE_CASE" \
  "open-redirect-strict-dynamic-no-remote" \
  "VULD_LOW_COST_STRICT_STUB_CASE" \
  "open-redirect-strict-dynamic-stub" \
  "VULD_LOW_COST_NEGATIVE_CASE" \
  "foobar-name-only-negative" \
  "LOW-COST" \
  "build_low_cost_case_specs" \
  "strict_no_remote_out" "strict_no_remote" \
  "strict_stub_out" "strict_stub" \
  "negative_out" "negative"
