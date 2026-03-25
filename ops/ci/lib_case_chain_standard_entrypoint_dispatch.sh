#!/usr/bin/env bash

_CASE_CHAIN_STANDARD_ENTRYPOINT_DISPATCH_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_CASE_CHAIN_STANDARD_ENTRYPOINT_DISPATCH_LIB_DIR}/lib_case_chain_standard_profile_dispatch.sh"

case_chain_resolve_standard_entrypoint_runner() {
  local profile_name="$1"
  local runner_output_var_name="$2"

  case_chain_resolve_standard_profile_runner \
    "${profile_name}" \
    "case_chain_run_direct_wrapper" \
    "case_chain_run_repeatability_wrapper" \
    "standard entrypoint" \
    "${runner_output_var_name}"
}
