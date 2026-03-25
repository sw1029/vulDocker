#!/usr/bin/env bash

operator_retry_forward_pair() {
  local source_count="$1"
  local source_delay="$2"
  local target_prefix="$3"

  export "${target_prefix}_DOCKER_RETRY_COUNT=${source_count}"
  export "${target_prefix}_DOCKER_RETRY_DELAY_SEC=${source_delay}"
}

operator_forward_optional_value() {
  local source_value="$1"
  local target_var="$2"
  if [[ -n "${source_value}" ]]; then
    export "${target_var}=${source_value}"
  fi
}

operator_forward_permission_surface() {
  local source_artifact_name="$1"
  local source_summary_name="$2"
  local target_prefix="$3"

  operator_forward_optional_value \
    "${source_artifact_name}" \
    "${target_prefix}_PERMISSION_ARTIFACT_NAME"
  operator_forward_optional_value \
    "${source_summary_name}" \
    "${target_prefix}_PERMISSION_SUMMARY_NAME"
}

operator_forward_runtime_surface() {
  local source_count="$1"
  local source_delay="$2"
  local source_artifact_name="$3"
  local source_summary_name="$4"
  local target_prefix="$5"

  operator_retry_forward_pair \
    "${source_count}" \
    "${source_delay}" \
    "${target_prefix}"
  operator_forward_permission_surface \
    "${source_artifact_name}" \
    "${source_summary_name}" \
    "${target_prefix}"
}

operator_retry_forward_pair_many() {
  local source_count="$1"
  local source_delay="$2"
  shift 2

  local target_prefix
  for target_prefix in "$@"; do
    operator_retry_forward_pair \
      "${source_count}" \
      "${source_delay}" \
      "${target_prefix}"
  done
}

operator_forward_permission_surface_many() {
  local source_artifact_name="$1"
  local source_summary_name="$2"
  shift 2

  local target_prefix
  for target_prefix in "$@"; do
    operator_forward_permission_surface \
      "${source_artifact_name}" \
      "${source_summary_name}" \
      "${target_prefix}"
  done
}
