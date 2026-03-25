#!/usr/bin/env bash

operator_resolve_case_default() {
  local source_var_name="$1"
  local default_value="$2"
  local output_var_name="$3"

  printf -v "${output_var_name}" '%s' "${!source_var_name:-${default_value}}"
}

operator_resolve_case_defaults() {
  if (($# % 3 != 0)); then
    echo "case default triplets are required" >&2
    return 1
  fi

  while (($# >= 3)); do
    operator_resolve_case_default \
      "$1" \
      "$2" \
      "$3"
    shift 3
  done
}

operator_resolve_pair_case_defaults() {
  local first_var_name="$1"
  local first_default="$2"
  local first_output="$3"
  local second_var_name="$4"
  local second_default="$5"
  local second_output="$6"

  operator_resolve_case_defaults \
    "${first_var_name}" "${first_default}" "${first_output}" \
    "${second_var_name}" "${second_default}" "${second_output}"
}

operator_resolve_triple_case_defaults() {
  local first_var_name="$1"
  local first_default="$2"
  local first_output="$3"
  local second_var_name="$4"
  local second_default="$5"
  local second_output="$6"
  local third_var_name="$7"
  local third_default="$8"
  local third_output="$9"

  operator_resolve_case_defaults \
    "${first_var_name}" "${first_default}" "${first_output}" \
    "${second_var_name}" "${second_default}" "${second_output}" \
    "${third_var_name}" "${third_default}" "${third_output}"
}
