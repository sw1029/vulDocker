#!/usr/bin/env bash

_operator_baseline_matrix_export_env() {
  local python_bin="$1"
  local cases_root="$2"
  local output_root="$3"
  local mode="$4"
  local attempts="$5"
  local no_snapshot="$6"
  local allow_repeat_failure_with_report="$7"
  local permission_artifact_name="$8"
  local permission_summary_name="$9"
  local docker_retry_count="${10}"
  local docker_retry_delay_sec="${11}"
  local repeat_helper="${12}"
  local matrix_helper="${13}"
  local named_matrix_helper="${14}"
  local log_prefix="${15}"

  export VULD_NAMED_MATRIX_HELPER="${matrix_helper}"
  export VULD_NAMED_MATRIX_PYTHON_BIN="${python_bin}"
  export VULD_NAMED_MATRIX_CASES_ROOT="${cases_root}"
  export VULD_NAMED_MATRIX_OUTPUT_ROOT="${output_root}"
  export VULD_NAMED_MATRIX_MODE="${mode}"
  export VULD_NAMED_MATRIX_ATTEMPTS="${attempts}"
  export VULD_NAMED_MATRIX_NO_SNAPSHOT="${no_snapshot}"
  export VULD_NAMED_MATRIX_ALLOW_REPEAT_FAILURE_WITH_REPORT="${allow_repeat_failure_with_report}"
  export VULD_NAMED_MATRIX_PERMISSION_ARTIFACT_NAME="${permission_artifact_name}"
  export VULD_NAMED_MATRIX_PERMISSION_SUMMARY_NAME="${permission_summary_name}"
  export VULD_NAMED_MATRIX_DOCKER_RETRY_COUNT="${docker_retry_count}"
  export VULD_NAMED_MATRIX_DOCKER_RETRY_DELAY_SEC="${docker_retry_delay_sec}"

  if [[ -n "${repeat_helper}" ]]; then
    export VULD_NAMED_MATRIX_REPEAT_HELPER="${repeat_helper}"
  fi

  export VULD_NAMED_PRESET_TARGET_HELPER="${named_matrix_helper}"
  export VULD_NAMED_PRESET_LOG_PREFIX="${log_prefix}"
}

measured_baseline_matrix_export_env() {
  _operator_baseline_matrix_export_env \
    "${VULD_MEASURED_BASELINE_PYTHON_BIN:-python}" \
    "${VULD_MEASURED_BASELINE_CASES_ROOT:-}" \
    "${VULD_MEASURED_BASELINE_OUTPUT_ROOT:-}" \
    "${VULD_MEASURED_BASELINE_MODE:-deterministic}" \
    "${VULD_MEASURED_BASELINE_ATTEMPTS:-2}" \
    "${VULD_MEASURED_BASELINE_NO_SNAPSHOT:-0}" \
    "${VULD_MEASURED_BASELINE_ALLOW_REPEAT_FAILURE_WITH_REPORT:-0}" \
    "${VULD_MEASURED_BASELINE_PERMISSION_ARTIFACT_NAME:-}" \
    "${VULD_MEASURED_BASELINE_PERMISSION_SUMMARY_NAME:-}" \
    "${VULD_MEASURED_BASELINE_DOCKER_RETRY_COUNT:-}" \
    "${VULD_MEASURED_BASELINE_DOCKER_RETRY_DELAY_SEC:-}" \
    "${VULD_MEASURED_BASELINE_REPEAT_HELPER:-}" \
    "${1}" \
    "${2}" \
    "MEASURED-MATRIX"
}

no_docker_baseline_matrix_export_env() {
  _operator_baseline_matrix_export_env \
    "${VULD_NO_DOCKER_BASELINE_PYTHON_BIN:-python}" \
    "${VULD_NO_DOCKER_BASELINE_CASES_ROOT:-}" \
    "${VULD_NO_DOCKER_BASELINE_MATRIX_OUTPUT_ROOT:-}" \
    "${VULD_NO_DOCKER_BASELINE_MATRIX_MODE:-deterministic}" \
    "${VULD_NO_DOCKER_BASELINE_MATRIX_ATTEMPTS:-2}" \
    "${VULD_NO_DOCKER_BASELINE_MATRIX_NO_SNAPSHOT:-0}" \
    "${VULD_NO_DOCKER_BASELINE_MATRIX_ALLOW_REPEAT_FAILURE_WITH_REPORT:-0}" \
    "${VULD_NO_DOCKER_BASELINE_PERMISSION_ARTIFACT_NAME:-}" \
    "${VULD_NO_DOCKER_BASELINE_PERMISSION_SUMMARY_NAME:-}" \
    "${VULD_NO_DOCKER_BASELINE_MATRIX_DOCKER_RETRY_COUNT:-}" \
    "${VULD_NO_DOCKER_BASELINE_MATRIX_DOCKER_RETRY_DELAY_SEC:-}" \
    "${VULD_NO_DOCKER_BASELINE_REPEAT_HELPER:-}" \
    "${1}" \
    "${2}" \
    "NO-DOCKER-MATRIX"
}
