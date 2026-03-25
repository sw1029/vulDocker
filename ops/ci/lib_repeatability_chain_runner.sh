#!/usr/bin/env bash

_REPEATABILITY_CHAIN_RUNNER_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_REPEATABILITY_CHAIN_RUNNER_LIB_DIR}/lib_repeatability_chain_env.sh"
source "${_REPEATABILITY_CHAIN_RUNNER_LIB_DIR}/lib_repeatability_helper_contract.sh"
source "${_REPEATABILITY_CHAIN_RUNNER_LIB_DIR}/lib_repeatability_postprocess.sh"

repeatability_run_helper_and_postprocess() {
  local run_dirs_array_name="$1"
  local permission_cases_array_name="$2"
  local permission_summary_path_var_name="$3"
  local repeat_helper="$4"
  local python_bin="$5"
  local cases_root="$6"
  local output_root="$7"
  local repeat_mode="$8"
  local repeat_attempts="$9"
  local no_snapshot="${10}"
  local allow_failure_with_report="${11}"
  local permission_artifact_name="${12}"
  local permission_summary_name="${13}"
  local docker_retry_count="${14}"
  local docker_retry_delay_sec="${15}"
  local log_prefix="${16}"
  shift 16

  repeatability_require_helper "${repeat_helper}" "${log_prefix}" || return 1

  mkdir -p "${output_root}"

  local run_dirs_file="${output_root}/repeat_run_dirs.txt"
  export_repeatability_chain_env \
    "${python_bin}" \
    "${cases_root}" \
    "${output_root}" \
    "${repeat_mode}" \
    "${repeat_attempts}" \
    "${no_snapshot}" \
    "${allow_failure_with_report}" \
    "${permission_artifact_name}" \
    "${docker_retry_count}" \
    "${docker_retry_delay_sec}" \
    "${run_dirs_file}" \
    "${log_prefix}"

  "${repeat_helper}" "$@"

  local permission_summary_path="${output_root}/${permission_summary_name}"
  repeatability_postprocess_runs \
    "${run_dirs_array_name}" \
    "${permission_cases_array_name}" \
    "${run_dirs_file}" \
    "${permission_artifact_name}" \
    "${permission_summary_path}" \
    "${log_prefix}"

  printf -v "${permission_summary_path_var_name}" '%s' "${permission_summary_path}"
}
