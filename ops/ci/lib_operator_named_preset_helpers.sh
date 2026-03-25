#!/usr/bin/env bash

operator_validate_named_preset_chain() {
  local preset_helper="$1"
  local named_helper="$2"
  local leaf_helper="$3"
  local preset_override="${4:-}"
  local named_override="${5:-}"
  local log_prefix="$6"
  local named_label="$7"
  local leaf_label="$8"

  if [[ ! -x "${preset_helper}" ]]; then
    echo "[${log_prefix}] preset helper not found or not executable: ${preset_helper}" >&2
    return 1
  fi

  if [[ -z "${preset_override}" && ! -x "${named_helper}" ]]; then
    echo "[${log_prefix}] ${named_label} not found or not executable: ${named_helper}" >&2
    return 1
  fi

  if [[ -z "${named_override}" && -z "${preset_override}" && ! -x "${leaf_helper}" ]]; then
    echo "[${log_prefix}] ${leaf_label} not found or not executable: ${leaf_helper}" >&2
    return 1
  fi
}
