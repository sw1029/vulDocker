#!/usr/bin/env bash

support_review_emit_output_pairs() {
  local log_prefix="$1"
  shift

  if (($# % 2 != 0)); then
    echo "support review output note pairs are required" >&2
    return 1
  fi

  while (($# >= 2)); do
    echo "[${log_prefix}] $1=$2"
    shift 2
  done
}

support_review_emit_completion_and_outputs() {
  local log_prefix="$1"
  local completion_note="$2"
  shift 2

  echo "[${log_prefix}] ${completion_note}"
  support_review_emit_output_pairs "${log_prefix}" "$@"
}

support_review_emit_review_only_completion() {
  local log_prefix="$1"
  local review_out="$2"
  shift 2

  support_review_emit_completion_and_outputs \
    "${log_prefix}" \
    "review-only completed" \
    "review_out" "${review_out}" \
    "$@"
}

support_review_emit_standard_completion() {
  local log_prefix="$1"
  local review_out="$2"
  local update_out="$3"
  local registry_out="$4"
  shift 4

  support_review_emit_completion_and_outputs \
    "${log_prefix}" \
    "completed" \
    "review_out" "${review_out}" \
    "update_out" "${update_out}" \
    "registry_out" "${registry_out}" \
    "$@"
}

support_review_emit_reviewable_accept_completion() {
  local log_prefix="$1"
  local review_index="$2"
  local registry_update="$3"
  local registry="$4"
  shift 4

  support_review_emit_completion_and_outputs \
    "${log_prefix}" \
    "completed" \
    "review_index" "${review_index}" \
    "registry_update" "${registry_update}" \
    "registry" "${registry}" \
    "$@"
}

support_review_emit_prefixed_review_only_completion() {
  local log_prefix="$1"
  local source_prefix="$2"
  local review_out_var="${source_prefix}_RESOLVED_REVIEW_OUT"
  shift 2

  support_review_emit_review_only_completion \
    "${log_prefix}" \
    "${!review_out_var}" \
    "$@"
}

support_review_emit_prefixed_standard_completion() {
  local log_prefix="$1"
  local source_prefix="$2"
  local review_out_var="${source_prefix}_RESOLVED_REVIEW_OUT"
  local update_out_var="${source_prefix}_RESOLVED_UPDATE_OUT"
  local registry_out_var="${source_prefix}_RESOLVED_REGISTRY_OUT"
  shift 2

  support_review_emit_standard_completion \
    "${log_prefix}" \
    "${!review_out_var}" \
    "${!update_out_var}" \
    "${!registry_out_var}" \
    "$@"
}

support_review_emit_prefixed_reviewable_accept_completion() {
  local log_prefix="$1"
  local source_prefix="$2"
  local review_index_var="${source_prefix}_RESOLVED_REVIEW_OUT"
  local registry_update_var="${source_prefix}_RESOLVED_UPDATE_OUT"
  local registry_var="${source_prefix}_RESOLVED_REGISTRY_OUT"
  shift 2

  support_review_emit_reviewable_accept_completion \
    "${log_prefix}" \
    "${!review_index_var}" \
    "${!registry_update_var}" \
    "${!registry_var}" \
    "$@"
}

support_review_emit_resolved_review_only_completion() {
  local log_prefix="$1"
  shift

  support_review_emit_prefixed_review_only_completion \
    "${log_prefix}" \
    "VULD_SUPPORT_REVIEW" \
    "$@"
}

support_review_emit_resolved_standard_completion() {
  local log_prefix="$1"
  shift

  support_review_emit_prefixed_standard_completion \
    "${log_prefix}" \
    "VULD_SUPPORT_REVIEW" \
    "$@"
}

support_review_emit_resolved_reviewable_accept_completion() {
  local log_prefix="$1"
  shift

  support_review_emit_prefixed_reviewable_accept_completion \
    "${log_prefix}" \
    "VULD_SUPPORT_REVIEW" \
    "$@"
}
