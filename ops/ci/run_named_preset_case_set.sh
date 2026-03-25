#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib_case_spec_presets.sh"
source "${SCRIPT_DIR}/lib_case_spec_preset_contract.sh"
source "${SCRIPT_DIR}/lib_named_case_helper_contract.sh"

TARGET_HELPER="${VULD_NAMED_PRESET_TARGET_HELPER:-}"
LOG_PREFIX="${VULD_NAMED_PRESET_LOG_PREFIX:-NAMED-PRESET}"
PRESET_BUILDER="${1:-}"

if ! case_spec_require_builder "${PRESET_BUILDER}" "${LOG_PREFIX}"; then
  exit 1
fi
shift

if ! named_case_require_target_helper \
  "${TARGET_HELPER}" \
  "${LOG_PREFIX}" \
  "target helper is required via VULD_NAMED_PRESET_TARGET_HELPER"; then
  exit 1
fi

mapfile -t CASE_SPECS < <("${PRESET_BUILDER}" "$@")
"${TARGET_HELPER}" "${CASE_SPECS[@]}"
