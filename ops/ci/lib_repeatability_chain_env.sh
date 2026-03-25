#!/usr/bin/env bash

export_repeatability_chain_env() {
  local python_bin="$1"
  local cases_root="$2"
  local output_root="$3"
  local repeat_mode="$4"
  local repeat_attempts="$5"
  local no_snapshot="$6"
  local allow_failure_with_report="$7"
  local permission_artifact_name="$8"
  local docker_retry_count="$9"
  local docker_retry_delay_sec="${10}"
  local run_dirs_file="${11}"
  local log_prefix="${12}"

  export VULD_REPEAT_CHAIN_PYTHON_BIN="${python_bin}"
  export VULD_REPEAT_CHAIN_CASES_ROOT="${cases_root}"
  export VULD_REPEAT_CHAIN_OUTPUT_ROOT="${output_root}"
  export VULD_REPEAT_CHAIN_MODE="${repeat_mode}"
  export VULD_REPEAT_CHAIN_ATTEMPTS="${repeat_attempts}"
  export VULD_REPEAT_CHAIN_NO_SNAPSHOT="${no_snapshot}"
  export VULD_REPEAT_CHAIN_ALLOW_FAILURE_WITH_REPORT="${allow_failure_with_report}"
  export VULD_REPEAT_CHAIN_PERMISSION_ARTIFACT_NAME="${permission_artifact_name}"
  if [[ -n "${docker_retry_count}" ]]; then
    export VULD_REPEAT_CHAIN_DOCKER_RETRY_COUNT="${docker_retry_count}"
  fi
  if [[ -n "${docker_retry_delay_sec}" ]]; then
    export VULD_REPEAT_CHAIN_DOCKER_RETRY_DELAY_SEC="${docker_retry_delay_sec}"
  fi
  export VULD_REPEAT_CHAIN_RUN_DIRS_FILE="${run_dirs_file}"
  export VULD_REPEAT_CHAIN_LOG_PREFIX="${log_prefix}"
}
