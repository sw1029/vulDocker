#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib_operator_export_helper_contract.sh"
source "${SCRIPT_DIR}/lib_operator_named_case_env.sh"
source "${SCRIPT_DIR}/lib_operator_named_preset_helpers.sh"

operator_run_named_preset() {
  local source_prefix="$1"
  local default_cases_root="$2"
  local default_output_root="$3"
  local named_helper="$4"
  local preset_helper="$5"
  local leaf_helper="$6"
  local preset_override="$7"
  local named_override="$8"
  local log_prefix="$9"
  local named_label="${10}"
  local leaf_label="${11}"
  local export_helper_fn="${12}"
  local preset_builder="${13}"
  shift 13

  operator_validate_named_preset_chain \
    "${preset_helper}" \
    "${named_helper}" \
    "${leaf_helper}" \
    "${preset_override}" \
    "${named_override}" \
    "${log_prefix}" \
    "${named_label}" \
    "${leaf_label}" || return 1

  operator_run_export_helper_function \
    "${export_helper_fn}" \
    "${log_prefix}" \
    "export helper function" \
    "${source_prefix}" \
    "${default_cases_root}" \
    "${default_output_root}" \
    "${leaf_helper}" \
    "${named_helper}" \
    "${log_prefix}" || return 1

  "${preset_helper}" "${preset_builder}" "$@"
}
