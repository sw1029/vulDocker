#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib_operator_pair_named_preset.sh"

operator_run_support_named_preset() {
  local source_prefix="$1"
  local default_cases_root="$2"
  local default_output_root="$3"
  local named_helper="$4"
  local preset_helper="$5"
  local support_helper="$6"
  local preset_override="$7"
  local named_override="$8"
  local log_prefix="$9"
  local preset_builder="${10}"
  shift 10

  operator_run_pair_named_preset \
    "${source_prefix}" \
    "${default_cases_root}" \
    "${default_output_root}" \
    "${named_helper}" \
    "${preset_helper}" \
    "${support_helper}" \
    "${preset_override}" \
    "${named_override}" \
    "${log_prefix}" \
    "named support helper" \
    "support helper" \
    "operator_prefix_export_support_named_env" \
    "${preset_builder}" \
    "$@"
}
