#!/usr/bin/env bash

support_review_resolve_output_path() {
  local output_root="$1"
  local output_name="$2"
  local output_var_name="$3"

  export "${output_var_name}=${output_root}/${output_name}"
}

support_review_resolve_output_path_pairs() {
  local output_root="$1"
  shift

  if (($# % 2 != 0)); then
    echo "support review output path pairs are required" >&2
    return 1
  fi

  while (($# >= 2)); do
    support_review_resolve_output_path "${output_root}" "$1" "$2"
    shift 2
  done
}

support_review_resolve_output_paths() {
  local output_root="$1"
  local review_output_name="$2"
  local decisions_output_name="$3"
  local update_output_name="$4"
  local registry_output_name="$5"

  support_review_resolve_output_path_pairs \
    "${output_root}" \
    "${review_output_name}" "VULD_SUPPORT_REVIEW_RESOLVED_REVIEW_OUT" \
    "${decisions_output_name}" "VULD_SUPPORT_REVIEW_RESOLVED_DECISIONS_OUT" \
    "${update_output_name}" "VULD_SUPPORT_REVIEW_RESOLVED_UPDATE_OUT" \
    "${registry_output_name}" "VULD_SUPPORT_REVIEW_RESOLVED_REGISTRY_OUT"
}
