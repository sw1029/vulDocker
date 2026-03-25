#!/usr/bin/env bash

_CASE_CHAIN_STANDARD_ENTRYPOINT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_CASE_CHAIN_STANDARD_ENTRYPOINT_LIB_DIR}/lib_case_chain_standard_profile_surface.sh"
source "${_CASE_CHAIN_STANDARD_ENTRYPOINT_LIB_DIR}/lib_case_chain_standard_entrypoint_dispatch.sh"
source "${_CASE_CHAIN_STANDARD_ENTRYPOINT_LIB_DIR}/lib_case_chain_profiled_entrypoint.sh"
source "${_CASE_CHAIN_STANDARD_ENTRYPOINT_LIB_DIR}/lib_case_chain_script_runner.sh"

case_chain_invoke_standard_entrypoint_runner() {
  local runner_fn="$1"
  local profile_name="$2"
  local script_dir="$3"
  shift 3

  case_chain_run_profiled_entrypoint \
    "${runner_fn}" \
    "${profile_name}" \
    "${script_dir}" \
    "$@"
}

case_chain_run_standard_entrypoint() {
  local profile_name="$1"
  local script_dir="$2"
  shift 2

  case_chain_run_standard_profile_surface \
    "case_chain_resolve_standard_entrypoint_runner" \
    "case_chain_invoke_standard_entrypoint_runner" \
    "${profile_name}" \
    "${script_dir}" \
    "$@"
}
