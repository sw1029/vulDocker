#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
source "${SCRIPT_DIR}/lib_operator_cases_output_roots.sh"
source "${SCRIPT_DIR}/lib_operator_support_pair_check.sh"
operator_resolve_cases_output_roots \
  "VULD_BLOCKED_NOOP" \
  "${REPO_ROOT}" \
  "/tmp/vuld_blocked_noop_check" \
  "CASES_ROOT" \
  "OUTPUT_ROOT"

operator_run_support_pair_check \
  "VULD_BLOCKED_NOOP" \
  "${SCRIPT_DIR}" \
  "${CASES_ROOT}" \
  "${OUTPUT_ROOT}" \
  "VULD_BLOCKED_NOOP_FOOBAR_CASE" \
  "foobar-name-only-negative" \
  "VULD_BLOCKED_NOOP_STRICT_CASE" \
  "open-redirect-strict-dynamic-no-remote" \
  "BLOCKED" \
  "build_blocked_noop_case_specs" \
  "foobar_out" "repeat_foobar" \
  "strict_out" "repeat_strict" \
  "review_out" "support_review.json" \
  "update_out" "support_update.json" \
  "registry_out" "support_registry.json"
