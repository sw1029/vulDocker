#!/usr/bin/env bash

support_review_require_helper() {
  local helper_path="$1"
  local log_prefix="$2"

  if [[ ! -x "${helper_path}" ]]; then
    echo "[${log_prefix}] review helper not found or not executable: ${helper_path}" >&2
    exit 1
  fi
}

support_review_materialize_decisions_file() {
  local decisions_file="$1"
  local decisions_out="$2"

  if [[ -n "${decisions_file}" ]]; then
    if [[ "${decisions_file}" != "${decisions_out}" ]]; then
      cp "${decisions_file}" "${decisions_out}"
    fi
    return 0
  fi

  printf '{"schema_version":"support_review_decisions@0.1","decisions":[]}\n' > "${decisions_out}"
}
