#!/usr/bin/env bash

named_case_require_target_helper() {
  local helper_path="${1:-}"
  local log_prefix="${2:-NAMED-CASE}"
  local missing_message="${3:-target helper not configured}"

  if [[ -z "${helper_path}" ]]; then
    echo "[${log_prefix}] ${missing_message}" >&2
    return 1
  fi

  if [[ ! -x "${helper_path}" ]]; then
    echo "[${log_prefix}] target helper not found or not executable: ${helper_path}" >&2
    return 1
  fi
}
