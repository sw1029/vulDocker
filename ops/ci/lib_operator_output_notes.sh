#!/usr/bin/env bash

operator_emit_completion_and_outputs() {
  local log_prefix="$1"
  shift

  echo "[${log_prefix}] completed"

  while (($# >= 2)); do
    local label="$1"
    local value="$2"
    echo "[${log_prefix}] ${label}=${value}"
    shift 2
  done
}
