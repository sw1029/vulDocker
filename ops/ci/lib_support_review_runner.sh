#!/usr/bin/env bash

_SUPPORT_REVIEW_RUNNER_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_SUPPORT_REVIEW_RUNNER_LIB_DIR}/lib_support_review_env.sh"
source "${_SUPPORT_REVIEW_RUNNER_LIB_DIR}/lib_support_review_helper_contract.sh"
source "${_SUPPORT_REVIEW_RUNNER_LIB_DIR}/lib_support_review_run_dirs.sh"

support_review_run_helper() {
  local log_prefix="$1"
  local review_helper="$2"
  local python_bin="$3"
  local output_root="$4"
  local review_only="$5"
  local decisions_file="$6"
  local review_output_name="$7"
  local decisions_output_name="$8"
  local update_output_name="$9"
  local registry_output_name="${10}"
  shift 10

  support_review_require_helper "${review_helper}" "${log_prefix}" || return 1
  support_review_require_run_dirs "${log_prefix}" "$@" || return 1

  export_support_review_env \
    "${python_bin}" \
    "${output_root}" \
    "${review_only}" \
    "${decisions_file}" \
    "${review_output_name}" \
    "${decisions_output_name}" \
    "${update_output_name}" \
    "${registry_output_name}"

  "${review_helper}" "$@"
}
