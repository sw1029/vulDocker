#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
source "${SCRIPT_DIR}/lib_operator_cases_output_roots.sh"
source "${SCRIPT_DIR}/lib_operator_direct_case_check.sh"
operator_resolve_cases_output_roots \
  "VULD_POSITIVE_DIRECT" \
  "${REPO_ROOT}" \
  "/tmp/vuld_positive_direct_validation" \
  "CASES_ROOT" \
  "OUTPUT_ROOT"

operator_run_direct_pair_check \
  "VULD_POSITIVE_DIRECT" \
  "${SCRIPT_DIR}" \
  "${CASES_ROOT}" \
  "${OUTPUT_ROOT}" \
  "VULD_POSITIVE_DIRECT_NAMED_HELPER" \
  "VULD_POSITIVE_DIRECT_PRESET_HELPER" \
  "VULD_POSITIVE_DIRECT_HELPER" \
  "VULD_POSITIVE_DIRECT_TRUSTED_CASE" \
  "trusted-dynamic-sqli" \
  "VULD_POSITIVE_DIRECT_OPEN_REDIRECT_CASE" \
  "open-redirect-dynamic-name-only" \
  "POSITIVE-DIRECT" \
  "build_positive_pair_case_specs" \
  "trusted_out" "trusted_dynamic" \
  "open_redirect_out" "open_redirect_dynamic"
