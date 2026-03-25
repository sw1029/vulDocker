#!/usr/bin/env bash

_CASE_CHAIN_FIXED_PROFILE_SHORTCUTS_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_CASE_CHAIN_FIXED_PROFILE_SHORTCUTS_LIB_DIR}/lib_case_chain_fixed_profile.sh"

case_chain_run_direct_fixed_profile_target() {
  local target_fn="$1"
  shift 1

  case_chain_run_fixed_profile \
    "${target_fn}" \
    "direct" \
    "$@"
}

case_chain_run_repeatability_fixed_profile_target() {
  local target_fn="$1"
  shift 1

  case_chain_run_fixed_profile \
    "${target_fn}" \
    "repeatability" \
    "$@"
}
