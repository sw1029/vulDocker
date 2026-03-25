#!/usr/bin/env bash

case_chain_run_profile_forward() {
  local target_fn="$1"
  local profile_name="$2"
  shift 2

  "${target_fn}" \
    "${profile_name}" \
    "$@"
}
