#!/usr/bin/env bash

_DIRECT_CASE_RUNTIME_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_DIRECT_CASE_RUNTIME_LIB_DIR}/lib_case_command_surface.sh"
source "${_DIRECT_CASE_RUNTIME_LIB_DIR}/lib_case_runtime_context.sh"

direct_prepare_case_runtime() {
  local context_ref_name="$1"
  local cmd_ref_name="$2"
  local log_prefix="$3"
  local cases_root="$4"
  local case_spec="$5"
  local output_root="$6"
  local python_bin="$7"
  local mode="$8"
  local no_snapshot="$9"
  local -n context_ref="${context_ref_name}"
  case_runtime_prepare_direct_context \
    "${context_ref_name}" \
    "${log_prefix}" \
    "${cases_root}" \
    "${case_spec}" \
    "${output_root}" || return 1

  local case_dir="${context_ref[0]}"
  local case_out="${context_ref[2]}"

  case_command_build_run_case \
    "${cmd_ref_name}" \
    "${python_bin}" \
    "${case_dir}" \
    "${mode}" \
    "${case_out}" \
    "${no_snapshot}"
}
