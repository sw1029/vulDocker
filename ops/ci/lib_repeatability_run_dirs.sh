#!/usr/bin/env bash

repeatability_load_run_dirs() {
  local -n output_ref="$1"
  local run_dirs_file="$2"
  local log_prefix="$3"

  if [[ ! -f "${run_dirs_file}" ]]; then
    echo "[${log_prefix}] run dirs file not found: ${run_dirs_file}" >&2
    exit 1
  fi

  mapfile -t output_ref < "${run_dirs_file}"

  if [[ "${#output_ref[@]}" -lt 1 ]]; then
    echo "[${log_prefix}] run dirs file is empty: ${run_dirs_file}" >&2
    exit 1
  fi

  local run_dir
  for run_dir in "${output_ref[@]}"; do
    if [[ ! -d "${run_dir}" ]]; then
      echo "[${log_prefix}] run directory not found: ${run_dir}" >&2
      exit 1
    fi
  done
}
