#!/usr/bin/env bash

collect_permission_artifact_cases() {
  local permission_artifact_name="$1"
  shift || true

  local run_dir
  for run_dir in "$@"; do
    local marker_path="${run_dir}/${permission_artifact_name}"
    [[ -f "${marker_path}" ]] || continue

    local case_name
    case_name="$(basename "${run_dir}")"
    if grep -q '^case_slug=' "${marker_path}"; then
      case_name="$(grep '^case_slug=' "${marker_path}" | head -n1 | cut -d= -f2-)"
    fi
    printf '%s\n' "${case_name}"
  done
}

emit_permission_artifact_note() {
  local log_prefix="$1"
  shift || true
  local cases=("$@")
  if [[ "${#cases[@]}" -gt 0 ]]; then
    echo "[${log_prefix}] note: docker permission artifact detected for ${cases[*]}; unrestricted Docker-enabled rerun is recommended for runtime-equivalent helper truth"
  fi
}
