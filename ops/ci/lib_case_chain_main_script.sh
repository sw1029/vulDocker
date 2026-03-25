#!/usr/bin/env bash

_CASE_CHAIN_MAIN_SCRIPT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_CASE_CHAIN_MAIN_SCRIPT_LIB_DIR}/lib_case_chain_profile_target_forward.sh"
source "${_CASE_CHAIN_MAIN_SCRIPT_LIB_DIR}/lib_case_chain_main.sh"

case_chain_run_main_script() {
  case_chain_run_profile_script_target_forward \
    "case_chain_run_main" \
    "$@"
}
