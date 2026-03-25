#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib_operator_named_preset_runner.sh"

operator_run_pair_named_preset() {
  local source_prefix="$1"
  local default_cases_root="$2"
  local default_output_root="$3"
  local named_helper="$4"
  local preset_helper="$5"
  local leaf_helper="$6"
  local preset_override="$7"
  local named_override="$8"
  local log_prefix="$9"
  local named_label="${10}"
  local leaf_label="${11}"
  local export_helper_fn="${12}"
  local preset_builder="${13}"
  shift 13

  operator_run_named_preset \
    "${source_prefix}" \
    "${default_cases_root}" \
    "${default_output_root}" \
    "${named_helper}" \
    "${preset_helper}" \
    "${leaf_helper}" \
    "${preset_override}" \
    "${named_override}" \
    "${log_prefix}" \
    "${named_label}" \
    "${leaf_label}" \
    "${export_helper_fn}" \
    "${preset_builder}" \
    "$@"
}
