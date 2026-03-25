#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib_operator_case_defaults.sh"
source "${SCRIPT_DIR}/lib_operator_pair_case_check.sh"
source "${SCRIPT_DIR}/lib_operator_direct_named_preset.sh"
source "${SCRIPT_DIR}/lib_operator_output_root_notes.sh"
source "${SCRIPT_DIR}/lib_operator_pair_named_preset_defaults.sh"

operator_run_direct_case_check() {
  local source_prefix="$1"
  local script_dir="$2"
  local default_cases_root="$3"
  local output_root="$4"
  local named_var_name="$5"
  local preset_var_name="$6"
  local leaf_var_name="$7"
  local log_prefix="$8"
  local preset_builder="$9"
  local case_triplet_count="${10}"
  shift 10

  if (($# < case_triplet_count)); then
    echo "[${log_prefix}] case default triplets are required" >&2
    return 1
  fi

  operator_resolve_pair_named_preset_surface \
    "${script_dir}" \
    "${named_var_name}" \
    "run_named_direct_case_set.sh" \
    "${preset_var_name}" \
    "run_named_preset_case_set.sh" \
    "${leaf_var_name}" \
    "run_direct_validation_chain.sh"

  local case_triplets=("${@:1:${case_triplet_count}}")
  shift "${case_triplet_count}"
  operator_resolve_case_defaults "${case_triplets[@]}"

  local case_args=()
  local output_var_name=""
  local index=2
  while ((index < case_triplet_count)); do
    output_var_name="${case_triplets[index]}"
    case_args+=("${!output_var_name}")
    index=$((index + 3))
  done

  operator_run_direct_named_preset \
    "${source_prefix}" \
    "${default_cases_root}" \
    "${output_root}" \
    "${OPERATOR_PAIR_NAMED_HELPER}" \
    "${OPERATOR_PAIR_PRESET_HELPER}" \
    "${OPERATOR_PAIR_LEAF_HELPER}" \
    "${!preset_var_name:-}" \
    "${!named_var_name:-}" \
    "${log_prefix}" \
    "${preset_builder}" \
    "${case_args[@]}"

  operator_emit_output_root_children \
    "${log_prefix}" \
    "${output_root}" \
    "$@"
}

operator_run_direct_pair_check() {
  local source_prefix="$1"
  local script_dir="$2"
  local default_cases_root="$3"
  local output_root="$4"
  local named_var_name="$5"
  local preset_var_name="$6"
  local leaf_var_name="$7"
  local first_case_var_name="$8"
  local first_default="$9"
  local second_case_var_name="${10}"
  local second_default="${11}"
  local log_prefix="${12}"
  local preset_builder="${13}"
  shift 13

  operator_run_pair_case_check \
    "${source_prefix}" \
    "${script_dir}" \
    "${default_cases_root}" \
    "${output_root}" \
    "${named_var_name}" \
    "run_named_direct_case_set.sh" \
    "${preset_var_name}" \
    "run_named_preset_case_set.sh" \
    "${leaf_var_name}" \
    "run_direct_validation_chain.sh" \
    "${preset_var_name}" \
    "${named_var_name}" \
    "operator_run_direct_named_preset" \
    "${first_case_var_name}" "${first_default}" "OPERATOR_DIRECT_CASE_A" \
    "${second_case_var_name}" "${second_default}" "OPERATOR_DIRECT_CASE_B" \
    "${log_prefix}" \
    "${preset_builder}" \
    "$@"
}

operator_run_direct_triple_check() {
  local source_prefix="$1"
  local script_dir="$2"
  local default_cases_root="$3"
  local output_root="$4"
  local named_var_name="$5"
  local preset_var_name="$6"
  local leaf_var_name="$7"
  local first_case_var_name="$8"
  local first_default="$9"
  local second_case_var_name="${10}"
  local second_default="${11}"
  local third_case_var_name="${12}"
  local third_default="${13}"
  local log_prefix="${14}"
  local preset_builder="${15}"
  shift 15

  operator_run_direct_case_check \
    "${source_prefix}" \
    "${script_dir}" \
    "${default_cases_root}" \
    "${output_root}" \
    "${named_var_name}" \
    "${preset_var_name}" \
    "${leaf_var_name}" \
    "${log_prefix}" \
    "${preset_builder}" \
    9 \
    "${first_case_var_name}" "${first_default}" "OPERATOR_DIRECT_CASE_A" \
    "${second_case_var_name}" "${second_default}" "OPERATOR_DIRECT_CASE_B" \
    "${third_case_var_name}" "${third_default}" "OPERATOR_DIRECT_CASE_C" \
    "$@"
}
