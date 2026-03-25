#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib_operator_retry_env.sh"
source "${SCRIPT_DIR}/lib_operator_sequence_helper_contract.sh"

operator_run_current_baseline_sequence() {
  local source_count="$1"
  local source_delay="$2"
  local source_artifact_name="$3"
  local source_summary_name="$4"
  local sequence_helper="$5"
  local baseline_label="$6"
  local no_docker_helper="$7"
  local measured_helper="$8"
  local support_helper="$9"
  local docker_positive_helper="${10}"
  local helper_regression="${11}"

  operator_retry_forward_pair_many \
    "${source_count}" \
    "${source_delay}" \
    "VULD_MEASURED_BASELINE" \
    "VULD_SUPPORT_BASELINE" \
    "VULD_DOCKER_POSITIVE_BASELINE"
  operator_forward_permission_surface_many \
    "${source_artifact_name}" \
    "${source_summary_name}" \
    "VULD_MEASURED_BASELINE" \
    "VULD_NO_DOCKER_BASELINE" \
    "VULD_SUPPORT_BASELINE" \
    "VULD_DOCKER_POSITIVE_BASELINE"

  operator_run_sequence_helper "${sequence_helper}" "${baseline_label}" \
    "no-docker operator baseline" "${no_docker_helper}" -- \
    "measured gate operator baseline" "${measured_helper}" -- \
    "support workflow baseline" "${support_helper}" -- \
    "docker-positive operator baseline" "${docker_positive_helper}" -- \
    "ops helper contract regression" "${helper_regression}"
}
