#!/usr/bin/env bash

case_chain_resolve_standard_profile_runner() {
  local profile_name="$1"
  local direct_runner_name="$2"
  local repeatability_runner_name="$3"
  local profile_kind_label="$4"
  local runner_output_var_name="$5"

  case "${profile_name}" in
    direct)
      printf -v "${runner_output_var_name}" '%s' "${direct_runner_name}"
      ;;
    repeatability)
      printf -v "${runner_output_var_name}" '%s' "${repeatability_runner_name}"
      ;;
    *)
      echo "unknown case-chain ${profile_kind_label} profile: ${profile_name}" >&2
      return 1
      ;;
  esac
}
