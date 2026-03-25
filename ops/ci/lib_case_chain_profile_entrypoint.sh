#!/usr/bin/env bash

_CASE_CHAIN_PROFILE_ENTRYPOINT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_CASE_CHAIN_PROFILE_ENTRYPOINT_LIB_DIR}/lib_case_chain_profile_target_forward.sh"
source "${_CASE_CHAIN_PROFILE_ENTRYPOINT_LIB_DIR}/lib_case_chain_standard_entrypoint.sh"

case_chain_run_profile_entrypoint() {
  case_chain_run_profile_target_forward \
    "case_chain_run_standard_entrypoint" \
    "$@"
}
