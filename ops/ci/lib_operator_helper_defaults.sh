#!/usr/bin/env bash

operator_resolve_script_helper_default() {
  local source_var_name="$1"
  local script_dir="$2"
  local default_file="$3"
  local output_var_name="$4"

  printf -v "${output_var_name}" '%s' "${!source_var_name:-${script_dir}/${default_file}}"
}

operator_resolve_script_helper_defaults() {
  local script_dir="$1"
  shift

  if (($# % 3 != 0)); then
    echo "script helper default triplets are required" >&2
    return 1
  fi

  while (($# >= 3)); do
    operator_resolve_script_helper_default \
      "$1" \
      "${script_dir}" \
      "$2" \
      "$3"
    shift 3
  done
}
