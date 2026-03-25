#!/usr/bin/env bash

case_expectations_resolve_default() {
  local case_dir="$1"
  local expectations_path="${case_dir}/expectations.json"
  if [[ -f "${expectations_path}" ]]; then
    printf '%s\n' "${expectations_path}"
  fi
}

case_expectations_append_if_present() {
  local cmd_var_name="$1"
  local case_dir="$2"
  local expectations_path
  local -n cmd_ref="${cmd_var_name}"

  expectations_path="$(case_expectations_resolve_default "${case_dir}")"
  if [[ -n "${expectations_path}" ]]; then
    cmd_ref+=(--expectations "${expectations_path}")
  fi
}
