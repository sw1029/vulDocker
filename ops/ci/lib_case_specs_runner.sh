#!/usr/bin/env bash

_CASE_SPECS_RUNNER_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_CASE_SPECS_RUNNER_LIB_DIR}/lib_case_chain_output_notes.sh"

case_specs_run_with_contexts() {
  local runner_fn="$1"
  local case_specs_ref_name="$2"
  local runner_prefix_ref_name="$3"
  local runner_suffix_ref_name="$4"
  local log_prefix="$5"
  local run_dirs_ref_name="$6"
  local run_dirs_file="$7"
  local -n case_specs_ref="${case_specs_ref_name}"
  local -n runner_prefix_ref="${runner_prefix_ref_name}"
  local -n runner_suffix_ref="${runner_suffix_ref_name}"
  local case_spec=""
  local case_runtime=()

  for case_spec in "${case_specs_ref[@]}"; do
    case_runtime=()
    "${runner_fn}" \
      case_runtime \
      "${runner_prefix_ref[@]}" \
      "${case_spec}" \
      "${runner_suffix_ref[@]}" || return $?
  done

  if [[ -n "${run_dirs_ref_name}" ]]; then
    local -n run_dirs_ref="${run_dirs_ref_name}"
    case_chain_write_run_dirs_file "${run_dirs_file}" "${run_dirs_ref[@]}"
  fi
  case_chain_emit_completed "${log_prefix}"
}
