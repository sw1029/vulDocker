#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib_operator_pair_case_check.sh"
source "${SCRIPT_DIR}/lib_operator_support_named_preset.sh"

operator_run_support_pair_check() {
  local source_prefix="$1"
  local script_dir="$2"
  local default_cases_root="$3"
  local output_root="$4"
  local first_case_var_name="$5"
  local first_default="$6"
  local second_case_var_name="$7"
  local second_default="$8"
  local log_prefix="$9"
  local preset_builder="${10}"
  shift 10

  operator_run_pair_case_check \
    "${source_prefix}" \
    "${script_dir}" \
    "${default_cases_root}" \
    "${output_root}" \
    "${source_prefix}_NAMED_SUPPORT_HELPER" \
    "run_named_support_case_set.sh" \
    "${source_prefix}_PRESET_HELPER" \
    "run_named_preset_case_set.sh" \
    "${source_prefix}_SUPPORT_HELPER" \
    "run_support_workflow_chain.sh" \
    "${source_prefix}_PRESET_HELPER" \
    "${source_prefix}_NAMED_SUPPORT_HELPER" \
    "operator_run_support_named_preset" \
    "${first_case_var_name}" \
    "${first_default}" \
    "OPERATOR_SUPPORT_PAIR_CASE_A" \
    "${second_case_var_name}" \
    "${second_default}" \
    "OPERATOR_SUPPORT_PAIR_CASE_B" \
    "${log_prefix}" \
    "${preset_builder}" \
    "$@"
}
