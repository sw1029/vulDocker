#!/usr/bin/env bash

case_chain_require_case_specs() {
  local usage_text="$1"
  shift

  if [[ "$#" -lt 1 ]]; then
    echo "${usage_text}" >&2
    return 1
  fi
}

case_chain_prepare_output_root() {
  local output_root="$1"
  mkdir -p "${output_root}"
}

case_chain_require_specs_and_prepare_root() {
  local usage_text="$1"
  local output_root="$2"
  shift 2

  case_chain_require_case_specs "${usage_text}" "$@" || return 1
  case_chain_prepare_output_root "${output_root}"
}
