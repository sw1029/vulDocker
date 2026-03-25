#!/usr/bin/env bash

case_spec_require_builder() {
  local builder_name="${1:-}"
  local log_prefix="${2:-NAMED-PRESET}"

  if [[ -z "${builder_name}" ]]; then
    echo "[${log_prefix}] preset builder is required" >&2
    return 1
  fi

  if ! declare -F "${builder_name}" >/dev/null 2>&1; then
    echo "[${log_prefix}] unknown preset builder: ${builder_name}" >&2
    return 1
  fi
}
