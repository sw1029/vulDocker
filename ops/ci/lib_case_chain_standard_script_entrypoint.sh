#!/usr/bin/env bash

_CASE_CHAIN_STANDARD_SCRIPT_ENTRYPOINT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_CASE_CHAIN_STANDARD_SCRIPT_ENTRYPOINT_LIB_DIR}/lib_case_chain_named_profile_shortcuts.sh"
source "${_CASE_CHAIN_STANDARD_SCRIPT_ENTRYPOINT_LIB_DIR}/lib_case_chain_standard_script_main.sh"

case_chain_run_named_standard_script_entrypoint() {
  case_chain_run_named_profile_target \
    "case_chain_run_standard_script_main" \
    "$@"
}

case_chain_run_fixed_standard_script_entrypoint() {
  case_chain_run_fixed_named_profile_target \
    "case_chain_run_named_standard_script_entrypoint" \
    "$@"
}

case_chain_run_direct_standard_script_entrypoint() {
  case_chain_run_direct_named_profile_target \
    "case_chain_run_named_standard_script_entrypoint" \
    "$@"
}

case_chain_run_repeatability_standard_script_entrypoint() {
  case_chain_run_repeatability_named_profile_target \
    "case_chain_run_named_standard_script_entrypoint" \
    "$@"
}
