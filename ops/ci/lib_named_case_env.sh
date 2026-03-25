#!/usr/bin/env bash

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib_support_review_output_defaults.sh"

named_caseset_require_helper() {
  local helper_path="$1"
  local log_prefix="$2"
  if [[ ! -x "${helper_path}" ]]; then
    echo "[${log_prefix}] caseset helper not found or not executable: ${helper_path}" >&2
    exit 1
  fi
}

named_caseset_dispatch() {
  local helper_path="$1"
  local log_prefix="$2"
  local target_helper="$3"
  shift 3

  named_caseset_require_helper "${helper_path}" "${log_prefix}"
  export VULD_NAMED_CASE_TARGET_HELPER="${target_helper}"
  export VULD_NAMED_CASE_LOG_PREFIX="${log_prefix}"

  "${helper_path}" "$@"
}

named_direct_export_env() {
  local default_cases_root="$1"
  local default_output_root="$2"
  export VULD_DIRECT_CHAIN_PYTHON_BIN="${VULD_NAMED_DIRECT_PYTHON_BIN:-python}"
  export VULD_DIRECT_CHAIN_CASES_ROOT="${VULD_NAMED_DIRECT_CASES_ROOT:-${default_cases_root}}"
  export VULD_DIRECT_CHAIN_OUTPUT_ROOT="${VULD_NAMED_DIRECT_OUTPUT_ROOT:-${default_output_root}}"
  export VULD_DIRECT_CHAIN_MODE="${VULD_NAMED_DIRECT_MODE:-deterministic}"
  export VULD_DIRECT_CHAIN_NO_SNAPSHOT="${VULD_NAMED_DIRECT_NO_SNAPSHOT:-1}"
}

named_support_export_env() {
  local default_cases_root="$1"
  local default_output_root="$2"
  local review_output_name
  local decisions_output_name
  local update_output_name
  local registry_output_name
  export VULD_SUPPORT_WORKFLOW_PYTHON_BIN="${VULD_NAMED_SUPPORT_PYTHON_BIN:-python}"
  export VULD_SUPPORT_WORKFLOW_CASES_ROOT="${VULD_NAMED_SUPPORT_CASES_ROOT:-${default_cases_root}}"
  export VULD_SUPPORT_WORKFLOW_OUTPUT_ROOT="${VULD_NAMED_SUPPORT_OUTPUT_ROOT:-${default_output_root}}"
  export VULD_SUPPORT_WORKFLOW_MODE="${VULD_NAMED_SUPPORT_MODE:-deterministic}"
  export VULD_SUPPORT_WORKFLOW_ATTEMPTS="${VULD_NAMED_SUPPORT_ATTEMPTS:-2}"
  export VULD_SUPPORT_WORKFLOW_REVIEW_ONLY="${VULD_NAMED_SUPPORT_REVIEW_ONLY:-0}"
  export VULD_SUPPORT_WORKFLOW_DECISIONS_FILE="${VULD_NAMED_SUPPORT_DECISIONS_FILE:-}"
  export VULD_SUPPORT_WORKFLOW_NO_SNAPSHOT="${VULD_NAMED_SUPPORT_NO_SNAPSHOT:-0}"
  export VULD_SUPPORT_WORKFLOW_ALLOW_REPEAT_FAILURE_WITH_REPORT="${VULD_NAMED_SUPPORT_ALLOW_REPEAT_FAILURE_WITH_REPORT:-1}"
  export VULD_SUPPORT_WORKFLOW_PERMISSION_ARTIFACT_NAME="${VULD_NAMED_SUPPORT_PERMISSION_ARTIFACT_NAME:-}"
  export VULD_SUPPORT_WORKFLOW_PERMISSION_SUMMARY_NAME="${VULD_NAMED_SUPPORT_PERMISSION_SUMMARY_NAME:-}"
  export VULD_SUPPORT_WORKFLOW_DOCKER_RETRY_COUNT="${VULD_NAMED_SUPPORT_DOCKER_RETRY_COUNT:-}"
  export VULD_SUPPORT_WORKFLOW_DOCKER_RETRY_DELAY_SEC="${VULD_NAMED_SUPPORT_DOCKER_RETRY_DELAY_SEC:-}"
  support_review_resolve_prefixed_output_name_defaults \
    "VULD_NAMED_SUPPORT" \
    "support_review.json" review_output_name \
    "support_decisions.json" decisions_output_name \
    "support_update.json" update_output_name \
    "support_registry.json" registry_output_name
  export VULD_SUPPORT_WORKFLOW_REVIEW_OUTPUT_NAME="${review_output_name}"
  export VULD_SUPPORT_WORKFLOW_DECISIONS_OUTPUT_NAME="${decisions_output_name}"
  export VULD_SUPPORT_WORKFLOW_UPDATE_OUTPUT_NAME="${update_output_name}"
  export VULD_SUPPORT_WORKFLOW_REGISTRY_OUTPUT_NAME="${registry_output_name}"

  if [[ -n "${VULD_NAMED_SUPPORT_REPEAT_HELPER:-}" ]]; then
    export VULD_SUPPORT_WORKFLOW_REPEAT_HELPER="${VULD_NAMED_SUPPORT_REPEAT_HELPER}"
  fi
  if [[ -n "${VULD_NAMED_SUPPORT_REVIEW_HELPER:-}" ]]; then
    export VULD_SUPPORT_WORKFLOW_REVIEW_HELPER="${VULD_NAMED_SUPPORT_REVIEW_HELPER}"
  fi
}

named_matrix_export_env() {
  local default_cases_root="$1"
  local default_output_root="$2"
  export VULD_REPEAT_MATRIX_PYTHON_BIN="${VULD_NAMED_MATRIX_PYTHON_BIN:-python}"
  export VULD_REPEAT_MATRIX_CASES_ROOT="${VULD_NAMED_MATRIX_CASES_ROOT:-${default_cases_root}}"
  export VULD_REPEAT_MATRIX_OUTPUT_ROOT="${VULD_NAMED_MATRIX_OUTPUT_ROOT:-${default_output_root}}"
  export VULD_REPEAT_MATRIX_MODE="${VULD_NAMED_MATRIX_MODE:-deterministic}"
  export VULD_REPEAT_MATRIX_ATTEMPTS="${VULD_NAMED_MATRIX_ATTEMPTS:-2}"
  export VULD_REPEAT_MATRIX_NO_SNAPSHOT="${VULD_NAMED_MATRIX_NO_SNAPSHOT:-0}"
  export VULD_REPEAT_MATRIX_ALLOW_REPEAT_FAILURE_WITH_REPORT="${VULD_NAMED_MATRIX_ALLOW_REPEAT_FAILURE_WITH_REPORT:-0}"
  export VULD_REPEAT_MATRIX_PERMISSION_ARTIFACT_NAME="${VULD_NAMED_MATRIX_PERMISSION_ARTIFACT_NAME:-}"
  export VULD_REPEAT_MATRIX_PERMISSION_SUMMARY_NAME="${VULD_NAMED_MATRIX_PERMISSION_SUMMARY_NAME:-}"
  export VULD_REPEAT_MATRIX_DOCKER_RETRY_COUNT="${VULD_NAMED_MATRIX_DOCKER_RETRY_COUNT:-}"
  export VULD_REPEAT_MATRIX_DOCKER_RETRY_DELAY_SEC="${VULD_NAMED_MATRIX_DOCKER_RETRY_DELAY_SEC:-}"

  if [[ -n "${VULD_NAMED_MATRIX_REPEAT_HELPER:-}" ]]; then
    export VULD_REPEAT_MATRIX_REPEAT_HELPER="${VULD_NAMED_MATRIX_REPEAT_HELPER}"
  fi
}
