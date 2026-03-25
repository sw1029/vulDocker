#!/usr/bin/env bash

_CASE_CHAIN_ENTRYPOINT_COMPAT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_CASE_CHAIN_ENTRYPOINT_COMPAT_LIB_DIR}/lib_case_chain_named_profile_shortcuts.sh"
source "${_CASE_CHAIN_ENTRYPOINT_COMPAT_LIB_DIR}/lib_case_chain_profile_entrypoint.sh"

case_chain_run_named_entrypoint() {
  case_chain_run_named_profile_target \
    "case_chain_run_profile_entrypoint" \
    "$@"
}

case_chain_run_fixed_entrypoint() {
  case_chain_run_fixed_named_profile_target \
    "case_chain_run_named_entrypoint" \
    "$@"
}

case_chain_run_direct_entrypoint() {
  case_chain_run_direct_named_profile_target \
    "case_chain_run_named_entrypoint" \
    "$@"
}

case_chain_run_repeatability_entrypoint() {
  case_chain_run_repeatability_named_profile_target \
    "case_chain_run_named_entrypoint" \
    "$@"
}
