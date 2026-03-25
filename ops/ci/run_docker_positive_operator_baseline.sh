#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib_operator_pair_runtime_baseline.sh"
source "${SCRIPT_DIR}/lib_operator_pair_runtime_baseline_defaults.sh"
operator_resolve_pair_runtime_baseline_surface \
  "VULD_DOCKER_POSITIVE_BASELINE" \
  "${SCRIPT_DIR}" \
  "VULD_DOCKER_POSITIVE_BASELINE_DIRECT_HELPER" \
  "run_positive_direct_validation.sh" \
  "VULD_DOCKER_POSITIVE_BASELINE_PROMOTION_HELPER" \
  "run_positive_pair_promotion_check.sh"

operator_run_pair_runtime_baseline_sequence \
  "${VULD_DOCKER_POSITIVE_BASELINE_DOCKER_RETRY_COUNT:-}" \
  "${VULD_DOCKER_POSITIVE_BASELINE_DOCKER_RETRY_DELAY_SEC:-}" \
  "${VULD_DOCKER_POSITIVE_BASELINE_PERMISSION_ARTIFACT_NAME:-}" \
  "${VULD_DOCKER_POSITIVE_BASELINE_PERMISSION_SUMMARY_NAME:-}" \
  "VULD_POSITIVE_PAIR" \
  "${OPERATOR_PAIR_SEQUENCE_HELPER}" \
  "DOCKER-POSITIVE" \
  "direct rerun baseline" "${OPERATOR_PAIR_FIRST_HELPER}" \
  "promotion-check baseline" "${OPERATOR_PAIR_SECOND_HELPER}"
