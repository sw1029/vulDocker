#!/usr/bin/env bash

_CASE_CHAIN_SPECS_SURFACE_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_CASE_CHAIN_SPECS_SURFACE_LIB_DIR}/lib_case_specs_runner.sh"
source "${_CASE_CHAIN_SPECS_SURFACE_LIB_DIR}/lib_direct_case_runner.sh"
source "${_CASE_CHAIN_SPECS_SURFACE_LIB_DIR}/lib_repeatability_case_runner.sh"

case_chain_run_direct_specs_surface() {
  local log_prefix="$1"
  local python_bin="$2"
  local cases_root="$3"
  local output_root="$4"
  local mode="$5"
  local no_snapshot="$6"
  shift 6

  local case_specs=("$@")
  local runner_prefix=(
    "${log_prefix}"
    "${python_bin}"
    "${cases_root}"
  )
  local runner_suffix=(
    "${output_root}"
    "${mode}"
    "${no_snapshot}"
  )

  case_specs_run_with_contexts \
    direct_run_case_spec \
    case_specs \
    runner_prefix \
    runner_suffix \
    "${log_prefix}" \
    "" \
    ""
}

case_chain_run_repeatability_specs_surface() {
  local run_dirs_ref_name="$1"
  local log_prefix="$2"
  local cases_root="$3"
  local output_root="$4"
  local output_prefix="$5"
  local report_name="$6"
  local python_bin="$7"
  local repeat_attempts="$8"
  local repeat_mode="$9"
  local no_snapshot="${10}"
  local allow_failure_with_report="${11}"
  local docker_retry_count="${12}"
  local docker_retry_delay_sec="${13}"
  local permission_artifact_name="${14}"
  local run_dirs_file="${15}"
  shift 15

  local -n run_dirs_ref="${run_dirs_ref_name}"
  local case_specs=("$@")
  local runner_prefix=(
    "${run_dirs_ref_name}"
    "${log_prefix}"
    "${cases_root}"
  )
  local runner_suffix=(
    "${output_root}"
    "${output_prefix}"
    "${report_name}"
    "${python_bin}"
    "${repeat_attempts}"
    "${repeat_mode}"
    "${no_snapshot}"
    "${allow_failure_with_report}"
    "${docker_retry_count}"
    "${docker_retry_delay_sec}"
    "${permission_artifact_name}"
  )

  run_dirs_ref=()
  case_specs_run_with_contexts \
    repeatability_run_case_spec \
    case_specs \
    runner_prefix \
    runner_suffix \
    "${log_prefix}" \
    "${run_dirs_ref_name}" \
    "${run_dirs_file}"
}
