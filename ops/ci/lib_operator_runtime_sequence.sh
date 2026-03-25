#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib_operator_retry_env.sh"
source "${SCRIPT_DIR}/lib_operator_sequence_helper_contract.sh"

operator_run_baseline_sequence_with_runtime_surface() {
  local source_count="$1"
  local source_delay="$2"
  local source_artifact_name="$3"
  local source_summary_name="$4"
  local target_prefix="$5"
  local sequence_helper="$6"
  local baseline_label="$7"
  shift 7

  operator_forward_runtime_surface \
    "${source_count}" \
    "${source_delay}" \
    "${source_artifact_name}" \
    "${source_summary_name}" \
    "${target_prefix}"

  operator_run_sequence_helper "${sequence_helper}" "${baseline_label}" "$@"
}
