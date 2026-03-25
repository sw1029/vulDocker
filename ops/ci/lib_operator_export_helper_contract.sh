#!/usr/bin/env bash

operator_require_export_helper_function() {
  local export_helper_fn="${1:-}"
  local log_prefix="${2:-OPERATOR}"
  local helper_label="${3:-export helper function}"

  if ! declare -F "${export_helper_fn}" >/dev/null 2>&1; then
    echo "[${log_prefix}] ${helper_label} not found: ${export_helper_fn}" >&2
    return 1
  fi
}

operator_run_export_helper_function() {
  local export_helper_fn="$1"
  local log_prefix="$2"
  local helper_label="$3"
  shift 3

  operator_require_export_helper_function \
    "${export_helper_fn}" \
    "${log_prefix}" \
    "${helper_label}" || return 1

  "${export_helper_fn}" "$@"
}
