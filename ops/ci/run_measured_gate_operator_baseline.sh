#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib_operator_matrix_baseline_sequence.sh"
source "${SCRIPT_DIR}/lib_operator_matrix_baseline_defaults.sh"
operator_resolve_matrix_baseline_surface "VULD_MEASURED_BASELINE" "${SCRIPT_DIR}"
PROMOTION_HELPER="${VULD_MEASURED_BASELINE_PROMOTION_HELPER:-${SCRIPT_DIR}/run_positive_pair_promotion_check.sh}"

operator_run_matrix_baseline_sequence \
  "measured_baseline_matrix_export_env" \
  "${OPERATOR_MATRIX_HELPER}" \
  "${OPERATOR_MATRIX_NAMED_MATRIX_HELPER}" \
  "${VULD_MEASURED_BASELINE_DOCKER_RETRY_COUNT:-}" \
  "${VULD_MEASURED_BASELINE_DOCKER_RETRY_DELAY_SEC:-}" \
  "${VULD_MEASURED_BASELINE_PERMISSION_ARTIFACT_NAME:-}" \
  "${VULD_MEASURED_BASELINE_PERMISSION_SUMMARY_NAME:-}" \
  "VULD_POSITIVE_PAIR" \
  "${OPERATOR_MATRIX_SEQUENCE_HELPER}" \
  "MEASURED-BASELINE" \
  "planning-only repeatability matrix preview" "${OPERATOR_MATRIX_PRESET_HELPER}" build_matrix_pair_case_specs "${OPERATOR_MATRIX_CASE_ARGS[@]}" -- \
  "positive pair promotion check" "${PROMOTION_HELPER}"
