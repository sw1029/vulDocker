#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib_operator_case_defaults.sh"
source "${SCRIPT_DIR}/lib_operator_output_root_notes.sh"
source "${SCRIPT_DIR}/lib_operator_pair_named_preset_defaults.sh"

operator_run_pair_case_check() {
  local source_prefix="$1"
  local script_dir="$2"
  local default_cases_root="$3"
  local output_root="$4"
  local named_var_name="$5"
  local named_default="$6"
  local preset_var_name="$7"
  local preset_default="$8"
  local leaf_var_name="$9"
  local leaf_default="${10}"
  local preset_override_var="${11}"
  local named_override_var="${12}"
  local runner_fn="${13}"
  local first_case_var_name="${14}"
  local first_default="${15}"
  local first_output_var_name="${16}"
  local second_case_var_name="${17}"
  local second_default="${18}"
  local second_output_var_name="${19}"
  local log_prefix="${20}"
  local preset_builder="${21}"
  shift 21

  operator_resolve_pair_named_preset_surface \
    "${script_dir}" \
    "${named_var_name}" \
    "${named_default}" \
    "${preset_var_name}" \
    "${preset_default}" \
    "${leaf_var_name}" \
    "${leaf_default}"

  operator_resolve_pair_case_defaults \
    "${first_case_var_name}" \
    "${first_default}" \
    "${first_output_var_name}" \
    "${second_case_var_name}" \
    "${second_default}" \
    "${second_output_var_name}"

  "${runner_fn}" \
    "${source_prefix}" \
    "${default_cases_root}" \
    "${output_root}" \
    "${OPERATOR_PAIR_NAMED_HELPER}" \
    "${OPERATOR_PAIR_PRESET_HELPER}" \
    "${OPERATOR_PAIR_LEAF_HELPER}" \
    "${!preset_override_var:-}" \
    "${!named_override_var:-}" \
    "${log_prefix}" \
    "${preset_builder}" \
    "${!first_output_var_name}" \
    "${!second_output_var_name}"

  operator_emit_output_root_children \
    "${log_prefix}" \
    "${output_root}" \
    "$@"
}
