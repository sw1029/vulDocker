#!/usr/bin/env bash

_CASE_CHAIN_SCRIPT_RUNNER_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_CASE_CHAIN_SCRIPT_RUNNER_LIB_DIR}/lib_case_chain_wrapper_context.sh"
source "${_CASE_CHAIN_SCRIPT_RUNNER_LIB_DIR}/lib_direct_chain_runner.sh"
source "${_CASE_CHAIN_SCRIPT_RUNNER_LIB_DIR}/lib_repeatability_chain_runtime_env.sh"
source "${_CASE_CHAIN_SCRIPT_RUNNER_LIB_DIR}/lib_repeatability_specs_runner.sh"

case_chain_run_direct_wrapper() {
  local source_prefix="$1"
  local repo_root="$2"
  local default_output_root="$3"
  local usage_text="$4"
  local log_prefix="$5"
  shift 5

  local cases_root=""
  local output_root=""
  local python_bin=""
  local mode=""
  local no_snapshot=""

  case_chain_prepare_wrapper_context \
    "${source_prefix}" \
    "${repo_root}" \
    "${default_output_root}" \
    "${usage_text}" \
    "deterministic" \
    "1" \
    "cases_root" \
    "output_root" \
    "python_bin" \
    "mode" \
    "no_snapshot" \
    "$@" || return 1

  direct_run_case_specs \
    "${log_prefix}" \
    "${python_bin}" \
    "${cases_root}" \
    "${output_root}" \
    "${mode}" \
    "${no_snapshot}" \
    "$@"
}

case_chain_run_repeatability_wrapper() {
  local source_prefix="$1"
  local repo_root="$2"
  local default_output_root="$3"
  local usage_text="$4"
  shift 4

  local cases_root=""
  local output_root=""
  local python_bin=""
  local repeat_mode=""
  local no_snapshot=""
  local repeat_attempts=""
  local allow_failure_with_report=""
  local run_dirs_file=""
  local output_prefix=""
  local log_prefix=""
  local report_name=""
  local docker_retry_count=""
  local docker_retry_delay_sec=""
  local permission_artifact_name=""
  local run_dirs=()

  case_chain_prepare_wrapper_context \
    "${source_prefix}" \
    "${repo_root}" \
    "${default_output_root}" \
    "${usage_text}" \
    "deterministic" \
    "0" \
    "cases_root" \
    "output_root" \
    "python_bin" \
    "repeat_mode" \
    "no_snapshot" \
    "$@" || return 1

  repeatability_chain_resolve_runtime_env \
    "${source_prefix}" \
    "repeat_attempts" \
    "allow_failure_with_report" \
    "run_dirs_file" \
    "output_prefix" \
    "log_prefix" \
    "report_name" \
    "docker_retry_count" \
    "docker_retry_delay_sec" \
    "permission_artifact_name"

  repeatability_run_case_specs \
    run_dirs \
    "${log_prefix}" \
    "${cases_root}" \
    "${output_root}" \
    "${output_prefix}" \
    "${report_name}" \
    "${python_bin}" \
    "${repeat_attempts}" \
    "${repeat_mode}" \
    "${no_snapshot}" \
    "${allow_failure_with_report}" \
    "${docker_retry_count}" \
    "${docker_retry_delay_sec}" \
    "${permission_artifact_name}" \
    "${run_dirs_file}" \
    "$@"
}
