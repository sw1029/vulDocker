#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib_named_case_env.sh"
CASESET_HELPER="${VULD_NAMED_MATRIX_CASESET_HELPER:-${SCRIPT_DIR}/run_named_case_set.sh}"
MATRIX_HELPER="${VULD_NAMED_MATRIX_HELPER:-${SCRIPT_DIR}/run_repeatability_matrix_check.sh}"

named_matrix_export_env "" "/tmp/vuld_named_matrix_case_set"
named_caseset_dispatch "${CASESET_HELPER}" "NAMED-MATRIX" "${MATRIX_HELPER}" "$@"
