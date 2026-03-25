#!/usr/bin/env bash

resolve_cases_output_roots() {
  local source_prefix="$1"
  local repo_root="$2"
  local default_output_root="$3"
  local cases_output_var_name="$4"
  local output_output_var_name="$5"

  local cases_var_name="${source_prefix}_CASES_ROOT"
  local output_var_name="${source_prefix}_OUTPUT_ROOT"

  printf -v "${cases_output_var_name}" '%s' "${!cases_var_name:-${repo_root}/tests/e2e/cases}"
  printf -v "${output_output_var_name}" '%s' "${!output_var_name:-${default_output_root}}"
}
