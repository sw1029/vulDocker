#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib_operator_matrix_baseline_sequence.sh"
source "${SCRIPT_DIR}/lib_operator_matrix_baseline_defaults.sh"
operator_resolve_matrix_baseline_surface "VULD_NO_DOCKER_BASELINE" "${SCRIPT_DIR}"
FOCUSED_HELPER="${VULD_NO_DOCKER_BASELINE_FOCUSED_HELPER:-${SCRIPT_DIR}/run_focused_no_docker_regression.sh}"
LOW_COST_HELPER="${VULD_NO_DOCKER_BASELINE_LOW_COST_HELPER:-${SCRIPT_DIR}/run_low_cost_no_docker_validation.sh}"
BLOCKED_HELPER="${VULD_NO_DOCKER_BASELINE_BLOCKED_HELPER:-${SCRIPT_DIR}/run_blocked_noop_support_check.sh}"

operator_run_matrix_baseline_sequence \
  "no_docker_baseline_matrix_export_env" \
  "${OPERATOR_MATRIX_HELPER}" \
  "${OPERATOR_MATRIX_NAMED_MATRIX_HELPER}" \
  "${VULD_NO_DOCKER_BASELINE_BLOCKED_DOCKER_RETRY_COUNT:-}" \
  "${VULD_NO_DOCKER_BASELINE_BLOCKED_DOCKER_RETRY_DELAY_SEC:-}" \
  "${VULD_NO_DOCKER_BASELINE_PERMISSION_ARTIFACT_NAME:-}" \
  "${VULD_NO_DOCKER_BASELINE_PERMISSION_SUMMARY_NAME:-}" \
  "VULD_BLOCKED_NOOP" \
  "${OPERATOR_MATRIX_SEQUENCE_HELPER}" \
  "NO-DOCKER" \
  "focused regression slice" "${FOCUSED_HELPER}" -- \
  "low-cost validation lanes" "${LOW_COST_HELPER}" -- \
  "repeatability + matrix preview" "${OPERATOR_MATRIX_PRESET_HELPER}" build_matrix_pair_case_specs "${OPERATOR_MATRIX_CASE_ARGS[@]}" -- \
  "blocked/no-op support rehearsal" "${BLOCKED_HELPER}"
