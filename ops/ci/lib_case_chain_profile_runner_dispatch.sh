#!/usr/bin/env bash

case_chain_run_profile_runner_dispatch() {
  local resolver_fn="$1"
  local invoke_fn="$2"
  local profile_name="$3"
  shift 3

  local runner_fn=""
  local resolver_rc=0
  "${resolver_fn}" "${profile_name}" "runner_fn" || resolver_rc=$?
  if [ "${resolver_rc}" -ne 0 ]; then
    return "${resolver_rc}"
  fi

  "${invoke_fn}" \
    "${runner_fn}" \
    "${profile_name}" \
    "$@"
}
