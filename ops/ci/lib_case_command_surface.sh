#!/usr/bin/env bash

_CASE_COMMAND_SURFACE_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_CASE_COMMAND_SURFACE_LIB_DIR}/lib_case_expectations.sh"

case_command_append_common_args() {
  local cmd_ref_name="$1"
  local case_dir="$2"
  local mode="$3"
  local output_dir="$4"
  local no_snapshot="$5"
  local -n output_cmd="${cmd_ref_name}"

  output_cmd+=(
    --case "${case_dir}"
    --mode "${mode}"
    --output-dir "${output_dir}"
  )
  case_expectations_append_if_present output_cmd "${case_dir}"
  if [[ "${no_snapshot}" = "1" ]]; then
    output_cmd+=(--no-snapshot)
  fi
}

case_command_build_run_case() {
  local cmd_ref_name="$1"
  local python_bin="$2"
  local case_dir="$3"
  local mode="$4"
  local output_dir="$5"
  local no_snapshot="$6"
  local -n output_cmd="${cmd_ref_name}"

  output_cmd=(
    "${python_bin}" tests/e2e/run_case.py
  )
  case_command_append_common_args \
    "${cmd_ref_name}" \
    "${case_dir}" \
    "${mode}" \
    "${output_dir}" \
    "${no_snapshot}"
}

case_command_build_repeat_case() {
  local cmd_ref_name="$1"
  local python_bin="$2"
  local case_dir="$3"
  local attempts="$4"
  local mode="$5"
  local output_dir="$6"
  local no_snapshot="$7"
  local -n output_cmd="${cmd_ref_name}"

  output_cmd=(
    "${python_bin}" tests/e2e/repeat_case.py
    --attempts "${attempts}"
  )
  case_command_append_common_args \
    "${cmd_ref_name}" \
    "${case_dir}" \
    "${mode}" \
    "${output_dir}" \
    "${no_snapshot}"
}
