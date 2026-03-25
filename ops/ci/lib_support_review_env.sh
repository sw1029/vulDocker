#!/usr/bin/env bash

export_support_review_env() {
  local python_bin="$1"
  local output_root="$2"
  local review_only="$3"
  local decisions_file="$4"
  local review_output_name="$5"
  local decisions_output_name="$6"
  local update_output_name="$7"
  local registry_output_name="$8"

  export VULD_SUPPORT_REVIEW_PYTHON_BIN="${python_bin}"
  export VULD_SUPPORT_REVIEW_OUTPUT_ROOT="${output_root}"
  export VULD_SUPPORT_REVIEW_REVIEW_ONLY="${review_only}"
  export VULD_SUPPORT_REVIEW_DECISIONS_FILE="${decisions_file}"
  export VULD_SUPPORT_REVIEW_REVIEW_OUTPUT_NAME="${review_output_name}"
  export VULD_SUPPORT_REVIEW_DECISIONS_OUTPUT_NAME="${decisions_output_name}"
  export VULD_SUPPORT_REVIEW_UPDATE_OUTPUT_NAME="${update_output_name}"
  export VULD_SUPPORT_REVIEW_REGISTRY_OUTPUT_NAME="${registry_output_name}"
}
