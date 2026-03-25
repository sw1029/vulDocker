#!/usr/bin/env bash

_REPEATABILITY_CASE_RUNTIME_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_REPEATABILITY_CASE_RUNTIME_LIB_DIR}/lib_case_command_surface.sh"
source "${_REPEATABILITY_CASE_RUNTIME_LIB_DIR}/lib_case_runtime_context.sh"

repeatability_prepare_case_runtime() {
  local context_ref_name="$1"
  local cmd_ref_name="$2"
  local run_dirs_ref_name="$3"
  local log_prefix="$4"
  local cases_root="$5"
  local case_spec="$6"
  local output_root="$7"
  local output_prefix="$8"
  local report_name="$9"
  local python_bin="${10}"
  local repeat_attempts="${11}"
  local repeat_mode="${12}"
  local no_snapshot="${13}"
  local -n context_ref="${context_ref_name}"
  local -n cmd_ref="${cmd_ref_name}"
  local -n run_dirs_ref="${run_dirs_ref_name}"
  case_runtime_prepare_repeat_context \
    "${context_ref_name}" \
    "${log_prefix}" \
    "${cases_root}" \
    "${case_spec}" \
    "${output_root}" \
    "${output_prefix}" \
    "${report_name}" || return 1

  local case_dir="${context_ref[0]}"
  local case_out="${context_ref[2]}"
  run_dirs_ref+=("${case_out}")

  case_command_build_repeat_case \
    "${cmd_ref_name}" \
    "${python_bin}" \
    "${case_dir}" \
    "${repeat_attempts}" \
    "${repeat_mode}" \
    "${case_out}" \
    "${no_snapshot}"
}
