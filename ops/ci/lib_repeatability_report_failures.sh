#!/usr/bin/env bash

repeatability_report_contains_error() {
  local report_root="$1"
  local needle="$2"
  [[ -d "${report_root}" ]] || return 1
  grep -R -q -- "${needle}" "${report_root}"
}

repeatability_report_has_transient_docker_failure() {
  local report_root="$1"
  repeatability_report_contains_error \
    "${report_root}" \
    "docker daemon is not reachable"
}

repeatability_report_has_permission_denied_docker_failure() {
  local report_root="$1"
  repeatability_report_contains_error \
    "${report_root}" \
    "docker daemon permission denied"
}

repeatability_write_permission_artifact_marker() {
  local marker_path="$1"
  local case_slug="$2"
  local report_path="$3"
  printf 'case_slug=%s\nreport_path=%s\nreason=%s\n' \
    "${case_slug}" \
    "${report_path}" \
    "docker daemon permission denied" \
    > "${marker_path}"
}
