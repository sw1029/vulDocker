#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib_operator_runtime_sequence.sh"

operator_run_pair_runtime_baseline_sequence() {
  local source_count="$1"
  local source_delay="$2"
  local source_artifact_name="$3"
  local source_summary_name="$4"
  local target_prefix="$5"
  local sequence_helper="$6"
  local baseline_label="$7"
  local first_label="$8"
  local first_helper="$9"
  local second_label="${10}"
  local second_helper="${11}"

  operator_run_baseline_sequence_with_runtime_surface \
    "${source_count}" \
    "${source_delay}" \
    "${source_artifact_name}" \
    "${source_summary_name}" \
    "${target_prefix}" \
    "${sequence_helper}" \
    "${baseline_label}" \
    "${first_label}" "${first_helper}" -- \
    "${second_label}" "${second_helper}"
}
