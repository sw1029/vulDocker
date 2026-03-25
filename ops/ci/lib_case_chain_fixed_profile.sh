#!/usr/bin/env bash

case_chain_run_fixed_profile() {
  local target_fn="$1"
  local fixed_profile_name="$2"
  shift 2

  "${target_fn}" \
    "${fixed_profile_name}" \
    "$@"
}
