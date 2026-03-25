#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
source "${SCRIPT_DIR}/lib_operator_cases_output_roots.sh"
source "${SCRIPT_DIR}/lib_operator_support_pair_check.sh"
operator_resolve_cases_output_roots \
  "VULD_POSITIVE_PAIR" \
  "${REPO_ROOT}" \
  "/tmp/vuld_positive_pair_check" \
  "CASES_ROOT" \
  "OUTPUT_ROOT"

export VULD_POSITIVE_PAIR_REVIEW_ONLY=1
export VULD_POSITIVE_PAIR_REVIEW_OUTPUT_NAME="support_review_positive_pair.json"
operator_run_support_pair_check \
  "VULD_POSITIVE_PAIR" \
  "${SCRIPT_DIR}" \
  "${CASES_ROOT}" \
  "${OUTPUT_ROOT}" \
  "VULD_POSITIVE_PAIR_TRUSTED_CASE" \
  "trusted-dynamic-sqli" \
  "VULD_POSITIVE_PAIR_OPEN_REDIRECT_CASE" \
  "open-redirect-dynamic-name-only" \
  "PROMOTION" \
  "build_positive_pair_case_specs" \
  "trusted_out" "repeat_trusted_dynamic" \
  "open_redirect_out" "repeat_open_redirect_dynamic" \
  "review_out" "support_review_positive_pair.json"
