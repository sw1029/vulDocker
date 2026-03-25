#!/usr/bin/env bash

case_chain_run_target_forward() {
  local target_fn="$1"
  shift 1

  "${target_fn}" "$@"
}
