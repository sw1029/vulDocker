#!/usr/bin/env bash

case_chain_run_entrypoint_surface() {
  local runner_fn="$1"
  local source_prefix="$2"
  local script_dir="$3"
  local default_output_root="$4"
  local usage_text="$5"
  local log_prefix="$6"
  shift 6

  local repo_root=""
  repo_root="$(cd "${script_dir}/../.." && pwd)"

  if [[ -n "${log_prefix}" ]]; then
    "${runner_fn}" \
      "${source_prefix}" \
      "${repo_root}" \
      "${default_output_root}" \
      "${usage_text}" \
      "${log_prefix}" \
      "$@"
    return $?
  fi

  "${runner_fn}" \
    "${source_prefix}" \
    "${repo_root}" \
    "${default_output_root}" \
    "${usage_text}" \
    "$@"
}
