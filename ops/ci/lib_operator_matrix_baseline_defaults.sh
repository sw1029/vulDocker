#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib_operator_helper_defaults.sh"
source "${SCRIPT_DIR}/lib_operator_matrix_case_pair.sh"

operator_resolve_matrix_baseline_surface() {
  local source_prefix="$1"
  local script_dir="$2"

  local sequence_var="${source_prefix}_SEQUENCE_HELPER"
  local preset_var="${source_prefix}_PRESET_HELPER"
  local named_matrix_var="${source_prefix}_NAMED_MATRIX_HELPER"
  local matrix_var="${source_prefix}_MATRIX_HELPER"
  local case_a_var="${source_prefix}_MATRIX_CASE_A"
  local case_b_var="${source_prefix}_MATRIX_CASE_B"

  operator_resolve_script_helper_defaults \
    "${script_dir}" \
    "${sequence_var}" "run_helper_sequence.sh" "OPERATOR_MATRIX_SEQUENCE_HELPER" \
    "${preset_var}" "run_named_preset_case_set.sh" "OPERATOR_MATRIX_PRESET_HELPER" \
    "${named_matrix_var}" "run_named_matrix_case_set.sh" "OPERATOR_MATRIX_NAMED_MATRIX_HELPER" \
    "${matrix_var}" "run_repeatability_matrix_check.sh" "OPERATOR_MATRIX_HELPER"

  mapfile -t OPERATOR_MATRIX_CASE_ARGS < <(
    operator_emit_matrix_case_pair_args \
      "${!case_a_var:-}" \
      "${!case_b_var:-}"
  )
}
