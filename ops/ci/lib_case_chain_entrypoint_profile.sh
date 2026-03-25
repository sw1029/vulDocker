#!/usr/bin/env bash

case_chain_resolve_entrypoint_profile() {
  local profile_name="$1"
  local script_dir="$2"
  local source_prefix_output_var_name="$3"
  local repo_root_output_var_name="$4"
  local default_output_root_output_var_name="$5"
  local usage_text_output_var_name="$6"
  local log_prefix_output_var_name="$7"

  local repo_root=""
  repo_root="$(cd "${script_dir}/../.." && pwd)"

  case "${profile_name}" in
    direct)
      printf -v "${source_prefix_output_var_name}" '%s' "VULD_DIRECT_CHAIN"
      printf -v "${repo_root_output_var_name}" '%s' "${repo_root}"
      printf -v "${default_output_root_output_var_name}" '%s' "/tmp/vuld_direct_validation_chain"
      printf -v "${usage_text_output_var_name}" '%s' "usage: ops/ci/run_direct_validation_chain.sh <case-slug-or-dir> [<case-slug-or-dir> ...]"
      printf -v "${log_prefix_output_var_name}" '%s' "DIRECT-CHAIN"
      ;;
    repeatability)
      printf -v "${source_prefix_output_var_name}" '%s' "VULD_REPEAT_CHAIN"
      printf -v "${repo_root_output_var_name}" '%s' "${repo_root}"
      printf -v "${default_output_root_output_var_name}" '%s' "/tmp/vuld_repeatability_chain"
      printf -v "${usage_text_output_var_name}" '%s' "usage: ops/ci/run_repeatability_chain.sh <case-slug-or-dir> [<case-slug-or-dir> ...]"
      printf -v "${log_prefix_output_var_name}" '%s' ""
      ;;
    *)
      echo "unknown case-chain entrypoint profile: ${profile_name}" >&2
      return 1
      ;;
  esac
}
