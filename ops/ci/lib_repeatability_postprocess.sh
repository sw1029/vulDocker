#!/usr/bin/env bash

_REPEATABILITY_POSTPROCESS_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_REPEATABILITY_POSTPROCESS_LIB_DIR}/lib_permission_artifact_summary.sh"
source "${_REPEATABILITY_POSTPROCESS_LIB_DIR}/lib_repeatability_permission_artifacts.sh"
source "${_REPEATABILITY_POSTPROCESS_LIB_DIR}/lib_repeatability_run_dirs.sh"

repeatability_postprocess_runs() {
  local run_dirs_array_name="$1"
  local permission_cases_array_name="$2"
  local run_dirs_file="$3"
  local permission_artifact_name="$4"
  local permission_summary_path="$5"
  local log_prefix="$6"

  repeatability_load_run_dirs "${run_dirs_array_name}" "${run_dirs_file}" "${log_prefix}"

  local -n run_dirs_ref="${run_dirs_array_name}"
  local -a permission_cases=()
  mapfile -t permission_cases < <(
    collect_permission_artifact_cases "${permission_artifact_name}" "${run_dirs_ref[@]}"
  )

  emit_permission_artifact_note "${log_prefix}" "${permission_cases[@]}"
  write_permission_artifact_summary "${permission_summary_path}" "${permission_artifact_name}" "${permission_cases[@]}"

  local -n permission_cases_ref="${permission_cases_array_name}"
  permission_cases_ref=("${permission_cases[@]}")
}
