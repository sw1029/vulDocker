#!/usr/bin/env bash

_CASE_CHAIN_PROFILED_ENTRYPOINT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_CASE_CHAIN_PROFILED_ENTRYPOINT_LIB_DIR}/lib_case_chain_entrypoint_profile.sh"
source "${_CASE_CHAIN_PROFILED_ENTRYPOINT_LIB_DIR}/lib_case_chain_entrypoint_surface.sh"

case_chain_run_profiled_entrypoint() {
  local runner_fn="$1"
  local profile_name="$2"
  local script_dir="$3"
  shift 3

  local source_prefix=""
  local repo_root=""
  local default_output_root=""
  local usage_text=""
  local log_prefix=""
  case_chain_resolve_entrypoint_profile \
    "${profile_name}" \
    "${script_dir}" \
    "source_prefix" \
    "repo_root" \
    "default_output_root" \
    "usage_text" \
    "log_prefix" || return 1

  case_chain_run_entrypoint_surface \
    "${runner_fn}" \
    "${source_prefix}" \
    "${script_dir}" \
    "${default_output_root}" \
    "${usage_text}" \
    "${log_prefix}" \
    "$@"
}
