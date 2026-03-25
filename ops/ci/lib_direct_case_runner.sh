#!/usr/bin/env bash

_DIRECT_CASE_RUNNER_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_DIRECT_CASE_RUNNER_LIB_DIR}/lib_case_chain_output_notes.sh"
source "${_DIRECT_CASE_RUNNER_LIB_DIR}/lib_direct_case_runtime.sh"

direct_run_case_spec() {
  local context_ref_name="$1"
  local log_prefix="$2"
  local python_bin="$3"
  local cases_root="$4"
  local case_spec="$5"
  local output_root="$6"
  local mode="$7"
  local no_snapshot="$8"
  local -n context_ref="${context_ref_name}"
  local cmd=()
  local runtime=()

  direct_prepare_case_runtime \
    runtime \
    cmd \
    "${log_prefix}" \
    "${cases_root}" \
    "${case_spec}" \
    "${output_root}" \
    "${python_bin}" \
    "${mode}" \
    "${no_snapshot}" || return 1

  case_chain_emit_case_output "${log_prefix}" "${runtime[1]}" "${runtime[2]}"
  "${cmd[@]}"
  context_ref=("${runtime[@]}")
}
