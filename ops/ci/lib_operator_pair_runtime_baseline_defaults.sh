#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib_operator_helper_defaults.sh"

operator_resolve_pair_runtime_baseline_surface() {
  local source_prefix="$1"
  local script_dir="$2"
  local first_var_name="$3"
  local first_default="$4"
  local second_var_name="$5"
  local second_default="$6"

  local sequence_var="${source_prefix}_SEQUENCE_HELPER"

  operator_resolve_script_helper_defaults \
    "${script_dir}" \
    "${sequence_var}" "run_helper_sequence.sh" "OPERATOR_PAIR_SEQUENCE_HELPER" \
    "${first_var_name}" "${first_default}" "OPERATOR_PAIR_FIRST_HELPER" \
    "${second_var_name}" "${second_default}" "OPERATOR_PAIR_SECOND_HELPER"
}
