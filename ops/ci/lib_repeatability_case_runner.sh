#!/usr/bin/env bash

_REPEATABILITY_CASE_RUNNER_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_REPEATABILITY_CASE_RUNNER_LIB_DIR}/lib_case_chain_output_notes.sh"
source "${_REPEATABILITY_CASE_RUNNER_LIB_DIR}/lib_repeatability_case_runtime.sh"
source "${_REPEATABILITY_CASE_RUNNER_LIB_DIR}/lib_repeatability_case_failure.sh"

repeatability_run_case_spec() {
  local context_ref_name="$1"
  local run_dirs_ref_name="$2"
  local log_prefix="$3"
  local cases_root="$4"
  local case_spec="$5"
  local output_root="$6"
  local output_prefix="$7"
  local report_name="$8"
  local python_bin="$9"
  local repeat_attempts="${10}"
  local repeat_mode="${11}"
  local no_snapshot="${12}"
  local allow_failure_with_report="${13}"
  local docker_retry_count="${14}"
  local docker_retry_delay_sec="${15}"
  local permission_artifact_name="${16}"
  local -n context_ref="${context_ref_name}"
  local runtime=()
  local cmd=()
  local case_slug=""
  local case_out=""
  local report_path=""
  local repeat_rc=0
  local retry_index=0
  local failure_action=""

  repeatability_prepare_case_runtime \
    runtime \
    cmd \
    "${run_dirs_ref_name}" \
    "${log_prefix}" \
    "${cases_root}" \
    "${case_spec}" \
    "${output_root}" \
    "${output_prefix}" \
    "${report_name}" \
    "${python_bin}" \
    "${repeat_attempts}" \
    "${repeat_mode}" \
    "${no_snapshot}" || return 1

  case_slug="${runtime[1]}"
  case_out="${runtime[2]}"
  report_path="${runtime[3]}"

  while true; do
    case_chain_emit_case_output "${log_prefix}" "${case_slug}" "${case_out}" "repeat "
    rm -rf "${case_out}"
    mkdir -p "${case_out}"
    set +e
    "${cmd[@]}"
    repeat_rc=$?
    set -e
    if [[ ${repeat_rc} -eq 0 ]]; then
      break
    fi
    failure_action=""
    repeatability_resolve_case_failure_action \
      failure_action \
      "${log_prefix}" \
      "${case_slug}" \
      "${case_out}" \
      "${report_path}" \
      "${repeat_rc}" \
      "${allow_failure_with_report}" \
      "${docker_retry_count}" \
      "${retry_index}" \
      "${permission_artifact_name}"
    if [[ "${failure_action}" = "retry" ]]; then
      retry_index=$((retry_index + 1))
      echo "[${log_prefix}] repeat ${case_slug} returned ${repeat_rc} with transient docker readiness failure, retrying (${retry_index}/${docker_retry_count})"
      sleep "${docker_retry_delay_sec}"
      continue
    fi
    if [[ "${failure_action}" = "continue" ]]; then
      break
    fi
    return "${repeat_rc}"
  done

  context_ref=("${runtime[@]}")
}
