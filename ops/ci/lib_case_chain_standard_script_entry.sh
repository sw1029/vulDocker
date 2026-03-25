#!/usr/bin/env bash

_CASE_CHAIN_STANDARD_SCRIPT_ENTRY_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_CASE_CHAIN_STANDARD_SCRIPT_ENTRY_LIB_DIR}/lib_case_chain_script_entry_compat.sh"
source "${_CASE_CHAIN_STANDARD_SCRIPT_ENTRY_LIB_DIR}/lib_case_chain_standard_profile_surface.sh"
source "${_CASE_CHAIN_STANDARD_SCRIPT_ENTRY_LIB_DIR}/lib_case_chain_standard_script_entry_dispatch.sh"

case_chain_invoke_standard_script_entry_runner() {
  local runner_fn="$1"
  local profile_name="$2"
  local script_path="$3"
  shift 3

  # The runner itself already encodes the selected profile; only the script path is forwarded.
  : "${profile_name}"
  "${runner_fn}" \
    "${script_path}" \
    "$@"
}

case_chain_run_standard_script_entry() {
  local profile_name="$1"
  local script_path="$2"
  shift 2

  case_chain_run_standard_profile_surface \
    "case_chain_resolve_standard_script_entry_runner" \
    "case_chain_invoke_standard_script_entry_runner" \
    "${profile_name}" \
    "${script_path}" \
    "$@"
}
