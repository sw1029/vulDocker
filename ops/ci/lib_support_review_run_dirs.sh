#!/usr/bin/env bash

support_review_require_run_dirs() {
  local log_prefix="$1"
  shift || true

  if [[ "$#" -lt 1 ]]; then
    echo "[${log_prefix}] at least one run directory is required" >&2
    exit 1
  fi

  local run_dir
  for run_dir in "$@"; do
    if [[ ! -d "${run_dir}" ]]; then
      echo "[${log_prefix}] run directory not found: ${run_dir}" >&2
      exit 1
    fi
  done
}
