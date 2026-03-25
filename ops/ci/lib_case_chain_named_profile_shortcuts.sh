#!/usr/bin/env bash

_CASE_CHAIN_NAMED_PROFILE_SHORTCUTS_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_CASE_CHAIN_NAMED_PROFILE_SHORTCUTS_LIB_DIR}/lib_case_chain_fixed_profile.sh"
source "${_CASE_CHAIN_NAMED_PROFILE_SHORTCUTS_LIB_DIR}/lib_case_chain_fixed_profile_shortcuts.sh"
source "${_CASE_CHAIN_NAMED_PROFILE_SHORTCUTS_LIB_DIR}/lib_case_chain_profile_forward.sh"

case_chain_run_named_profile_target() {
  local target_fn="$1"
  local profile_name="$2"
  shift 2

  case_chain_run_profile_forward \
    "${target_fn}" \
    "${profile_name}" \
    "$@"
}

case_chain_run_fixed_named_profile_target() {
  local target_fn="$1"
  local fixed_profile_name="$2"
  shift 2

  case_chain_run_fixed_profile \
    "${target_fn}" \
    "${fixed_profile_name}" \
    "$@"
}

case_chain_run_direct_named_profile_target() {
  local target_fn="$1"
  shift 1

  case_chain_run_direct_fixed_profile_target \
    "${target_fn}" \
    "$@"
}

case_chain_run_repeatability_named_profile_target() {
  local target_fn="$1"
  shift 1

  case_chain_run_repeatability_fixed_profile_target \
    "${target_fn}" \
    "$@"
}
