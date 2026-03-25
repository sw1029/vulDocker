#!/usr/bin/env bash

_CASE_CHAIN_WRAPPER_CONTEXT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_CASE_CHAIN_WRAPPER_CONTEXT_LIB_DIR}/lib_case_chain_paths.sh"
source "${_CASE_CHAIN_WRAPPER_CONTEXT_LIB_DIR}/lib_case_chain_runtime_env.sh"

case_chain_prepare_wrapper_context() {
  local source_prefix="$1"
  local repo_root="$2"
  local default_output_root="$3"
  local usage_text="$4"
  local default_mode="$5"
  local default_no_snapshot="$6"
  local cases_output_var_name="$7"
  local output_output_var_name="$8"
  local python_output_var_name="$9"
  local mode_output_var_name="${10}"
  local no_snapshot_output_var_name="${11}"
  shift 11

  case_chain_prepare_cases_output_root \
    "${source_prefix}" \
    "${repo_root}" \
    "${default_output_root}" \
    "${usage_text}" \
    "${cases_output_var_name}" \
    "${output_output_var_name}" \
    "$@" || return 1

  case_chain_resolve_runtime_env \
    "${source_prefix}" \
    "${default_mode}" \
    "${default_no_snapshot}" \
    "${python_output_var_name}" \
    "${mode_output_var_name}" \
    "${no_snapshot_output_var_name}"
}
