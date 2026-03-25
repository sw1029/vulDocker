#!/usr/bin/env bash

_CASE_RUNTIME_CONTEXT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_CASE_RUNTIME_CONTEXT_LIB_DIR}/lib_case_spec_resolution.sh"

case_runtime_capture_context() {
  local context_ref_name="$1"
  local resolved_output_ref_name="$2"
  local output_dir_index="$3"
  local -n context_ref="${context_ref_name}"
  local -n resolved_output_ref="${resolved_output_ref_name}"

  context_ref=(
    "${resolved_output_ref[0]}"
    "${resolved_output_ref[1]}"
    "${resolved_output_ref[${output_dir_index}]}"
  )
}

case_runtime_append_report_path() {
  local context_ref_name="$1"
  local report_name="$2"
  local -n context_ref="${context_ref_name}"

  context_ref+=("${context_ref[2]}/${report_name}")
}

case_runtime_prepare_direct_context() {
  local context_ref_name="$1"
  local log_prefix="$2"
  local cases_root="$3"
  local case_spec="$4"
  local output_root="$5"
  local resolved_output=()

  case_spec_resolve_direct_output_context \
    resolved_output \
    "${log_prefix}" \
    "${cases_root}" \
    "${case_spec}" \
    "${output_root}" || return 1

  case_runtime_capture_context \
    "${context_ref_name}" \
    resolved_output \
    4
}

case_runtime_prepare_repeat_context() {
  local context_ref_name="$1"
  local log_prefix="$2"
  local cases_root="$3"
  local case_spec="$4"
  local output_root="$5"
  local output_prefix="$6"
  local report_name="$7"
  local resolved_output=()

  case_spec_resolve_repeat_output_context \
    resolved_output \
    "${log_prefix}" \
    "${cases_root}" \
    "${case_spec}" \
    "${output_root}" \
    "${output_prefix}" || return 1

  case_runtime_capture_context \
    "${context_ref_name}" \
    resolved_output \
    5
  case_runtime_append_report_path \
    "${context_ref_name}" \
    "${report_name}"
}
