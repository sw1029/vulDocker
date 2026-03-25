#!/usr/bin/env bash

_CASE_CHAIN_STANDARD_PROFILE_SURFACE_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_CASE_CHAIN_STANDARD_PROFILE_SURFACE_LIB_DIR}/lib_case_chain_profile_runner_dispatch.sh"

case_chain_run_standard_profile_surface() {
  local resolver_fn="$1"
  local invoke_fn="$2"
  local profile_name="$3"
  shift 3

  case_chain_run_profile_runner_dispatch \
    "${resolver_fn}" \
    "${invoke_fn}" \
    "${profile_name}" \
    "$@"
}
