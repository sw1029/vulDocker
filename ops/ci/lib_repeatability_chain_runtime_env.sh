#!/usr/bin/env bash

repeatability_chain_resolve_runtime_env() {
  local source_prefix="$1"
  local attempts_output_var_name="$2"
  local allow_failure_output_var_name="$3"
  local run_dirs_file_output_var_name="$4"
  local output_prefix_output_var_name="$5"
  local log_prefix_output_var_name="$6"
  local report_name_output_var_name="$7"
  local docker_retry_count_output_var_name="$8"
  local docker_retry_delay_output_var_name="$9"
  local permission_artifact_output_var_name="${10}"

  local attempts_var_name="${source_prefix}_ATTEMPTS"
  local allow_failure_var_name="${source_prefix}_ALLOW_FAILURE_WITH_REPORT"
  local run_dirs_file_var_name="${source_prefix}_RUN_DIRS_FILE"
  local output_prefix_var_name="${source_prefix}_OUTPUT_PREFIX"
  local log_prefix_var_name="${source_prefix}_LOG_PREFIX"
  local report_name_var_name="${source_prefix}_REPORT_NAME"
  local docker_retry_count_var_name="${source_prefix}_DOCKER_RETRY_COUNT"
  local docker_retry_delay_var_name="${source_prefix}_DOCKER_RETRY_DELAY_SEC"
  local permission_artifact_var_name="${source_prefix}_PERMISSION_ARTIFACT_NAME"

  printf -v "${attempts_output_var_name}" '%s' "${!attempts_var_name:-2}"
  printf -v "${allow_failure_output_var_name}" '%s' "${!allow_failure_var_name:-0}"
  printf -v "${run_dirs_file_output_var_name}" '%s' "${!run_dirs_file_var_name:-}"
  printf -v "${output_prefix_output_var_name}" '%s' "${!output_prefix_var_name:-repeat}"
  printf -v "${log_prefix_output_var_name}" '%s' "${!log_prefix_var_name:-REPEAT}"
  printf -v "${report_name_output_var_name}" '%s' "${!report_name_var_name:-repeatability_report.json}"
  printf -v "${docker_retry_count_output_var_name}" '%s' "${!docker_retry_count_var_name:-2}"
  printf -v "${docker_retry_delay_output_var_name}" '%s' "${!docker_retry_delay_var_name:-1}"
  printf -v "${permission_artifact_output_var_name}" '%s' "${!permission_artifact_var_name:-docker_permission_artifact.txt}"
}
