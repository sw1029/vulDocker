#!/usr/bin/env bash

case_chain_resolve_runtime_env() {
  local source_prefix="$1"
  local default_mode="$2"
  local default_no_snapshot="$3"
  local python_output_var_name="$4"
  local mode_output_var_name="$5"
  local no_snapshot_output_var_name="$6"

  local python_var_name="${source_prefix}_PYTHON_BIN"
  local mode_var_name="${source_prefix}_MODE"
  local no_snapshot_var_name="${source_prefix}_NO_SNAPSHOT"

  printf -v "${python_output_var_name}" '%s' "${!python_var_name:-python}"
  printf -v "${mode_output_var_name}" '%s' "${!mode_var_name:-${default_mode}}"
  printf -v "${no_snapshot_output_var_name}" '%s' "${!no_snapshot_var_name:-${default_no_snapshot}}"
}
