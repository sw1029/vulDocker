#!/usr/bin/env bash

_CASE_CHAIN_PROFILE_TARGET_FORWARD_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_CASE_CHAIN_PROFILE_TARGET_FORWARD_LIB_DIR}/lib_case_chain_target_forward.sh"

case_chain_run_profile_target_forward() {
  local target_fn="$1"
  local profile_name="$2"
  local target_arg="$3"
  shift 3

  case_chain_run_target_forward \
    "${target_fn}" \
    "${profile_name}" \
    "${target_arg}" \
    "$@"
}

case_chain_run_profile_script_target_forward() {
  local target_fn="$1"
  local profile_name="$2"
  local script_path="$3"
  shift 3

  local script_dir=""
  script_dir="$(cd "$(dirname "${script_path}")" && pwd)"

  case_chain_run_profile_target_forward \
    "${target_fn}" \
    "${profile_name}" \
    "${script_dir}" \
    "$@"
}
