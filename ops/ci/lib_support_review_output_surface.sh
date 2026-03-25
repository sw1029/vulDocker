#!/usr/bin/env bash

_SUPPORT_REVIEW_OUTPUT_SURFACE_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_SUPPORT_REVIEW_OUTPUT_SURFACE_LIB_DIR}/lib_support_review_output_defaults.sh"
source "${_SUPPORT_REVIEW_OUTPUT_SURFACE_LIB_DIR}/lib_support_review_outputs.sh"

support_review_export_prefixed_resolved_output_paths() {
  local source_prefix="$1"

  export "${source_prefix}_RESOLVED_REVIEW_OUT=${VULD_SUPPORT_REVIEW_RESOLVED_REVIEW_OUT}"
  export "${source_prefix}_RESOLVED_DECISIONS_OUT=${VULD_SUPPORT_REVIEW_RESOLVED_DECISIONS_OUT}"
  export "${source_prefix}_RESOLVED_UPDATE_OUT=${VULD_SUPPORT_REVIEW_RESOLVED_UPDATE_OUT}"
  export "${source_prefix}_RESOLVED_REGISTRY_OUT=${VULD_SUPPORT_REVIEW_RESOLVED_REGISTRY_OUT}"
}

support_review_prepare_prefixed_output_surface() {
  local source_prefix="$1"
  local output_root="$2"
  local review_default="$3"
  local review_output_name_var="$4"
  local decisions_default="$5"
  local decisions_output_name_var="$6"
  local update_default="$7"
  local update_output_name_var="$8"
  local registry_default="$9"
  local registry_output_name_var="${10}"

  support_review_resolve_prefixed_output_name_defaults \
    "${source_prefix}" \
    "${review_default}" "${review_output_name_var}" \
    "${decisions_default}" "${decisions_output_name_var}" \
    "${update_default}" "${update_output_name_var}" \
    "${registry_default}" "${registry_output_name_var}"

  support_review_resolve_output_paths \
    "${output_root}" \
    "${!review_output_name_var}" \
    "${!decisions_output_name_var}" \
    "${!update_output_name_var}" \
    "${!registry_output_name_var}"

  support_review_export_prefixed_resolved_output_paths "${source_prefix}"
}
