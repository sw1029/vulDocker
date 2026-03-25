#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib_operator_current_baseline_sequence.sh"
source "${SCRIPT_DIR}/lib_operator_current_baseline_defaults.sh"
operator_resolve_current_baseline_surface "VULD_CURRENT_BASELINE" "${SCRIPT_DIR}"

operator_run_current_baseline_sequence \
  "${VULD_CURRENT_BASELINE_DOCKER_RETRY_COUNT:-}" \
  "${VULD_CURRENT_BASELINE_DOCKER_RETRY_DELAY_SEC:-}" \
  "${VULD_CURRENT_BASELINE_PERMISSION_ARTIFACT_NAME:-}" \
  "${VULD_CURRENT_BASELINE_PERMISSION_SUMMARY_NAME:-}" \
  "${OPERATOR_CURRENT_SEQUENCE_HELPER}" \
  "CURRENT-BASELINE" \
  "${OPERATOR_CURRENT_NO_DOCKER_HELPER}" \
  "${OPERATOR_CURRENT_MEASURED_HELPER}" \
  "${OPERATOR_CURRENT_SUPPORT_HELPER}" \
  "${OPERATOR_CURRENT_DOCKER_POSITIVE_HELPER}" \
  "${OPERATOR_CURRENT_HELPER_REGRESSION}"
