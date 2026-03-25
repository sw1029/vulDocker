#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib_operator_baseline_matrix_env.sh"
source "${SCRIPT_DIR}/lib_operator_export_helper_contract.sh"
source "${SCRIPT_DIR}/lib_operator_runtime_sequence.sh"

operator_run_matrix_baseline_sequence() {
  local export_helper_fn="$1"
  local matrix_helper="$2"
  local named_matrix_helper="$3"
  local source_count="$4"
  local source_delay="$5"
  local source_artifact_name="$6"
  local source_summary_name="$7"
  local target_prefix="$8"
  local sequence_helper="$9"
  local baseline_label="${10}"
  shift 10

  operator_run_export_helper_function \
    "${export_helper_fn}" \
    "${baseline_label}" \
    "matrix export helper" \
    "${matrix_helper}" \
    "${named_matrix_helper}" || return 1

  operator_run_baseline_sequence_with_runtime_surface \
    "${source_count}" \
    "${source_delay}" \
    "${source_artifact_name}" \
    "${source_summary_name}" \
    "${target_prefix}" \
    "${sequence_helper}" \
    "${baseline_label}" \
    "$@"
}
