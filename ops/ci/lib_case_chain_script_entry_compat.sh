#!/usr/bin/env bash

_CASE_CHAIN_SCRIPT_ENTRY_COMPAT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_CASE_CHAIN_SCRIPT_ENTRY_COMPAT_LIB_DIR}/lib_case_chain_named_profile_shortcuts.sh"
source "${_CASE_CHAIN_SCRIPT_ENTRY_COMPAT_LIB_DIR}/lib_case_chain_main_script.sh"

case_chain_run_named_script_entry() {
  case_chain_run_named_profile_target \
    "case_chain_run_main_script" \
    "$@"
}

case_chain_run_fixed_script_entry() {
  case_chain_run_fixed_named_profile_target \
    "case_chain_run_named_script_entry" \
    "$@"
}

case_chain_run_direct_script_entry() {
  case_chain_run_direct_named_profile_target \
    "case_chain_run_named_script_entry" \
    "$@"
}

case_chain_run_repeatability_script_entry() {
  case_chain_run_repeatability_named_profile_target \
    "case_chain_run_named_script_entry" \
    "$@"
}
