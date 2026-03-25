#!/usr/bin/env bash

_REPEATABILITY_CASE_FAILURE_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_REPEATABILITY_CASE_FAILURE_LIB_DIR}/lib_repeatability_report_failures.sh"

repeatability_resolve_case_failure_action() {
  local output_var_name="$1"
  local log_prefix="$2"
  local case_slug="$3"
  local report_root="$4"
  local report_path="$5"
  local repeat_rc="$6"
  local allow_failure_with_report="$7"
  local docker_retry_count="$8"
  local retry_index="$9"
  local permission_artifact_name="${10}"

  if [[ "${docker_retry_count}" =~ ^[0-9]+$ ]] \
    && (( retry_index < docker_retry_count )) \
    && repeatability_report_has_transient_docker_failure "${report_root}"; then
    printf -v "${output_var_name}" '%s' "retry"
    return 0
  fi

  if repeatability_report_has_permission_denied_docker_failure "${report_root}"; then
    repeatability_write_permission_artifact_marker \
      "${report_root}/${permission_artifact_name}" \
      "${case_slug}" \
      "${report_path}"
    if [[ "${allow_failure_with_report}" = "1" && -f "${report_path}" ]]; then
      echo "[${log_prefix}] repeat ${case_slug} reported docker daemon permission denied; continuing with recorded report ${report_path}"
      printf -v "${output_var_name}" '%s' "continue"
      return 0
    fi
  fi

  if [[ "${allow_failure_with_report}" = "1" && -f "${report_path}" ]]; then
    echo "[${log_prefix}] repeat ${case_slug} returned ${repeat_rc}, continuing with recorded report ${report_path}"
    printf -v "${output_var_name}" '%s' "continue"
    return 0
  fi

  printf -v "${output_var_name}" '%s' "fail"
}
