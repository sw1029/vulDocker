#!/usr/bin/env bash

case_chain_emit_case_output() {
  local log_prefix="$1"
  local case_slug="$2"
  local output_dir="$3"
  local action_prefix="${4:-}"

  echo "[${log_prefix}] ${action_prefix}${case_slug} -> ${output_dir}"
}

case_chain_write_run_dirs_file() {
  local run_dirs_file="$1"
  shift

  if [[ -n "${run_dirs_file}" ]]; then
    printf '%s\n' "$@" > "${run_dirs_file}"
  fi
}

case_chain_emit_completed() {
  local log_prefix="$1"
  echo "[${log_prefix}] completed"
}
