#!/usr/bin/env bash

case_spec_split() {
  local spec="$1"
  local case_input="$spec"
  local alias=""
  if [[ "${spec}" == *=* ]]; then
    case_input="${spec%%=*}"
    alias="${spec#*=}"
  fi
  printf '%s\n%s\n' "${case_input}" "${alias}"
}

case_spec_resolve_case_dir() {
  local cases_root="$1"
  local input="$2"
  if [[ "${input}" = /* ]]; then
    printf '%s\n' "${input}"
  else
    printf '%s\n' "${cases_root}/${input}"
  fi
}

case_spec_require_existing_dir() {
  local log_prefix="$1"
  local case_dir="$2"
  if [[ ! -d "${case_dir}" ]]; then
    echo "[${log_prefix}] case directory not found: ${case_dir}" >&2
    return 1
  fi
}

case_spec_require_safe_alias() {
  local log_prefix="$1"
  local alias="$2"
  if [[ -n "${alias}" && "${alias}" == */* ]]; then
    echo "[${log_prefix}] alias must not contain '/': ${alias}" >&2
    return 1
  fi
}

case_spec_resolve_case_context() {
  local output_ref_name="$1"
  local log_prefix="$2"
  local cases_root="$3"
  local spec="$4"
  local -n output_ref="${output_ref_name}"
  local spec_parts=()
  local case_input=""
  local case_alias=""
  local case_dir=""
  local case_slug=""

  mapfile -t spec_parts < <(case_spec_split "${spec}")
  case_input="${spec_parts[0]}"
  case_alias="${spec_parts[1]}"
  case_dir="$(case_spec_resolve_case_dir "${cases_root}" "${case_input}")"
  case_spec_require_existing_dir "${log_prefix}" "${case_dir}" || return 1
  case_spec_require_safe_alias "${log_prefix}" "${case_alias}" || return 1
  case_slug="$(basename "${case_dir}")"

  output_ref=("${case_dir}" "${case_slug}" "${case_alias}")
}

case_spec_resolve_output_name() {
  local output_var_name="$1"
  local log_prefix="$2"
  local case_alias="$3"
  local default_value="$4"
  local resolved_value="${case_alias:-${default_value}}"

  case_spec_require_safe_alias "${log_prefix}" "${resolved_value}" || return 1
  printf -v "${output_var_name}" '%s' "${resolved_value}"
}

case_spec_safe_slug() {
  local output_var_name="$1"
  local raw_value="$2"
  printf -v "${output_var_name}" '%s' "${raw_value//-/_}"
}

case_spec_resolve_direct_output_context() {
  local output_ref_name="$1"
  local log_prefix="$2"
  local cases_root="$3"
  local spec="$4"
  local output_root="$5"
  local -n output_ref="${output_ref_name}"
  local case_context=()
  local case_dir=""
  local case_slug=""
  local case_alias=""
  local output_name=""

  case_spec_resolve_case_context case_context "${log_prefix}" "${cases_root}" "${spec}" || return 1
  case_dir="${case_context[0]}"
  case_slug="${case_context[1]}"
  case_alias="${case_context[2]}"
  case_spec_resolve_output_name output_name "${log_prefix}" "${case_alias}" "run_${case_slug//-/_}" || return 1

  output_ref=(
    "${case_dir}"
    "${case_slug}"
    "${case_alias}"
    "${output_name}"
    "${output_root}/${output_name}"
  )
}

case_spec_export_direct_output_context() {
  local output_prefix="$1"
  local log_prefix="$2"
  local cases_root="$3"
  local spec="$4"
  local output_root="$5"
  local context=()

  case_spec_resolve_direct_output_context \
    context \
    "${log_prefix}" \
    "${cases_root}" \
    "${spec}" \
    "${output_root}" || return 1

  printf -v "${output_prefix}_CASE_DIR" '%s' "${context[0]}"
  printf -v "${output_prefix}_CASE_SLUG" '%s' "${context[1]}"
  printf -v "${output_prefix}_CASE_ALIAS" '%s' "${context[2]}"
  printf -v "${output_prefix}_OUTPUT_NAME" '%s' "${context[3]}"
  printf -v "${output_prefix}_OUTPUT_DIR" '%s' "${context[4]}"
}

case_spec_resolve_repeat_output_context() {
  local output_ref_name="$1"
  local log_prefix="$2"
  local cases_root="$3"
  local spec="$4"
  local output_root="$5"
  local output_prefix="$6"
  local -n output_ref="${output_ref_name}"
  local case_context=()
  local case_dir=""
  local case_slug=""
  local case_alias=""
  local output_name=""
  local safe_slug=""

  case_spec_resolve_case_context case_context "${log_prefix}" "${cases_root}" "${spec}" || return 1
  case_dir="${case_context[0]}"
  case_slug="${case_context[1]}"
  case_alias="${case_context[2]}"
  case_spec_resolve_output_name output_name "${log_prefix}" "${case_alias}" "${case_slug}" || return 1
  case_spec_safe_slug safe_slug "${output_name}"

  output_ref=(
    "${case_dir}"
    "${case_slug}"
    "${case_alias}"
    "${output_name}"
    "${safe_slug}"
    "${output_root}/${output_prefix}_${safe_slug}"
  )
}

case_spec_export_repeat_output_context() {
  local output_prefix="$1"
  local log_prefix="$2"
  local cases_root="$3"
  local spec="$4"
  local output_root="$5"
  local repeat_output_prefix="$6"
  local context=()

  case_spec_resolve_repeat_output_context \
    context \
    "${log_prefix}" \
    "${cases_root}" \
    "${spec}" \
    "${output_root}" \
    "${repeat_output_prefix}" || return 1

  printf -v "${output_prefix}_CASE_DIR" '%s' "${context[0]}"
  printf -v "${output_prefix}_CASE_SLUG" '%s' "${context[1]}"
  printf -v "${output_prefix}_CASE_ALIAS" '%s' "${context[2]}"
  printf -v "${output_prefix}_OUTPUT_NAME" '%s' "${context[3]}"
  printf -v "${output_prefix}_SAFE_SLUG" '%s' "${context[4]}"
  printf -v "${output_prefix}_OUTPUT_DIR" '%s' "${context[5]}"
}
