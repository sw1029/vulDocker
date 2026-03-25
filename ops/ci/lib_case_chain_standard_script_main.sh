#!/usr/bin/env bash

_CASE_CHAIN_STANDARD_SCRIPT_MAIN_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_CASE_CHAIN_STANDARD_SCRIPT_MAIN_LIB_DIR}/lib_case_chain_standard_script_entry.sh"

case_chain_run_standard_script_main() {
  local profile_name="$1"
  local script_path="$2"
  shift 2

  case_chain_run_standard_script_entry \
    "${profile_name}" \
    "${script_path}" \
    "$@"
}
