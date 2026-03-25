#!/usr/bin/env bash

support_review_resolve_output_name_default() {
  local source_var_name="$1"
  local default_value="$2"
  local output_var_name="$3"

  printf -v "${output_var_name}" '%s' "${!source_var_name:-${default_value}}"
}

support_review_resolve_output_name_defaults() {
  if (($# % 3 != 0)); then
    echo "support review output default triplets are required" >&2
    return 1
  fi

  while (($# >= 3)); do
    support_review_resolve_output_name_default \
      "$1" \
      "$2" \
      "$3"
    shift 3
  done
}

support_review_resolve_prefixed_output_name_defaults() {
  local source_prefix="$1"
  local review_default="$2"
  local review_output_var="$3"
  local decisions_default="$4"
  local decisions_output_var="$5"
  local update_default="$6"
  local update_output_var="$7"
  local registry_default="$8"
  local registry_output_var="$9"

  support_review_resolve_output_name_defaults \
    "${source_prefix}_REVIEW_OUTPUT_NAME" "${review_default}" "${review_output_var}" \
    "${source_prefix}_DECISIONS_OUTPUT_NAME" "${decisions_default}" "${decisions_output_var}" \
    "${source_prefix}_UPDATE_OUTPUT_NAME" "${update_default}" "${update_output_var}" \
    "${source_prefix}_REGISTRY_OUTPUT_NAME" "${registry_default}" "${registry_output_var}"
}
