#!/usr/bin/env bash

repeatability_require_helper() {
  local helper_path="$1"
  local log_prefix="$2"
  if [[ ! -x "${helper_path}" ]]; then
    echo "[${log_prefix}] repeat helper not found or not executable: ${helper_path}" >&2
    return 1
  fi
}
