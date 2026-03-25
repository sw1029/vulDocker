#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib_operator_helper_defaults.sh"

operator_resolve_current_baseline_surface() {
  local source_prefix="$1"
  local script_dir="$2"

  local sequence_var="${source_prefix}_SEQUENCE_HELPER"
  local no_docker_var="${source_prefix}_NO_DOCKER_HELPER"
  local measured_var="${source_prefix}_MEASURED_HELPER"
  local support_var="${source_prefix}_SUPPORT_HELPER"
  local docker_positive_var="${source_prefix}_DOCKER_POSITIVE_HELPER"
  local helper_regression_var="${source_prefix}_HELPER_REGRESSION"

  operator_resolve_script_helper_defaults \
    "${script_dir}" \
    "${sequence_var}" "run_helper_sequence.sh" "OPERATOR_CURRENT_SEQUENCE_HELPER" \
    "${no_docker_var}" "run_no_docker_operator_baseline.sh" "OPERATOR_CURRENT_NO_DOCKER_HELPER" \
    "${measured_var}" "run_measured_gate_operator_baseline.sh" "OPERATOR_CURRENT_MEASURED_HELPER" \
    "${support_var}" "run_support_workflow_operator_baseline.sh" "OPERATOR_CURRENT_SUPPORT_HELPER" \
    "${docker_positive_var}" "run_docker_positive_operator_baseline.sh" "OPERATOR_CURRENT_DOCKER_POSITIVE_HELPER" \
    "${helper_regression_var}" "run_ops_helper_contract_regression.sh" "OPERATOR_CURRENT_HELPER_REGRESSION"
}
