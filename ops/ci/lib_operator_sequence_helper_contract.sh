#!/usr/bin/env bash

operator_require_sequence_helper() {
  local sequence_helper="$1"
  local baseline_label="$2"

  if [[ ! -x "${sequence_helper}" ]]; then
    echo "[${baseline_label}] sequence helper not found or not executable: ${sequence_helper}" >&2
    return 1
  fi
}

operator_run_sequence_helper() {
  local sequence_helper="$1"
  local baseline_label="$2"
  shift 2

  operator_require_sequence_helper "${sequence_helper}" "${baseline_label}" || return 1
  "${sequence_helper}" "${baseline_label}" "$@"
}
