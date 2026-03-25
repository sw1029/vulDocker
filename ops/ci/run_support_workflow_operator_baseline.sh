#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib_operator_pair_runtime_baseline.sh"
source "${SCRIPT_DIR}/lib_operator_pair_runtime_baseline_defaults.sh"
operator_resolve_pair_runtime_baseline_surface \
  "VULD_SUPPORT_BASELINE" \
  "${SCRIPT_DIR}" \
  "VULD_SUPPORT_BASELINE_REVIEWABLE_HELPER" \
  "run_reviewable_support_accept_check.sh" \
  "VULD_SUPPORT_BASELINE_BLOCKED_HELPER" \
  "run_blocked_noop_support_check.sh"

operator_run_pair_runtime_baseline_sequence \
  "${VULD_SUPPORT_BASELINE_DOCKER_RETRY_COUNT:-}" \
  "${VULD_SUPPORT_BASELINE_DOCKER_RETRY_DELAY_SEC:-}" \
  "${VULD_SUPPORT_BASELINE_PERMISSION_ARTIFACT_NAME:-}" \
  "${VULD_SUPPORT_BASELINE_PERMISSION_SUMMARY_NAME:-}" \
  "VULD_BLOCKED_NOOP" \
  "${OPERATOR_PAIR_SEQUENCE_HELPER}" \
  "SUPPORT-BASELINE" \
  "reviewable accept-path" "${OPERATOR_PAIR_FIRST_HELPER}" \
  "blocked/no-op path" "${OPERATOR_PAIR_SECOND_HELPER}"
