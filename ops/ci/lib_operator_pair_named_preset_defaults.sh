#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib_operator_helper_defaults.sh"

operator_resolve_pair_named_preset_surface() {
  local script_dir="$1"
  local named_var_name="$2"
  local named_default="$3"
  local preset_var_name="$4"
  local preset_default="$5"
  local leaf_var_name="$6"
  local leaf_default="$7"

  operator_resolve_script_helper_defaults \
    "${script_dir}" \
    "${named_var_name}" "${named_default}" "OPERATOR_PAIR_NAMED_HELPER" \
    "${preset_var_name}" "${preset_default}" "OPERATOR_PAIR_PRESET_HELPER" \
    "${leaf_var_name}" "${leaf_default}" "OPERATOR_PAIR_LEAF_HELPER"
}
