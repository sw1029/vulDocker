#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib_named_case_env.sh"
CASESET_HELPER="${VULD_NAMED_DIRECT_CASESET_HELPER:-${SCRIPT_DIR}/run_named_case_set.sh}"
DIRECT_HELPER="${VULD_NAMED_DIRECT_HELPER:-${SCRIPT_DIR}/run_direct_validation_chain.sh}"

named_direct_export_env "" "/tmp/vuld_named_direct_case_set"
named_caseset_dispatch "${CASESET_HELPER}" "NAMED-DIRECT" "${DIRECT_HELPER}" "$@"
