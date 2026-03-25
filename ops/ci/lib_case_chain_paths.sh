#!/usr/bin/env bash

_CASE_CHAIN_PATHS_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_CASE_CHAIN_PATHS_LIB_DIR}/lib_cases_output_roots.sh"
source "${_CASE_CHAIN_PATHS_LIB_DIR}/lib_case_chain_entry.sh"

case_chain_prepare_cases_output_root() {
  local source_prefix="$1"
  local repo_root="$2"
  local default_output_root="$3"
  local usage_text="$4"
  local cases_output_var_name="$5"
  local output_output_var_name="$6"
  shift 6

  resolve_cases_output_roots \
    "${source_prefix}" \
    "${repo_root}" \
    "${default_output_root}" \
    "${cases_output_var_name}" \
    "${output_output_var_name}"

  local output_root="${!output_output_var_name}"
  case_chain_require_specs_and_prepare_root \
    "${usage_text}" \
    "${output_root}" \
    "$@" || return 1
}
