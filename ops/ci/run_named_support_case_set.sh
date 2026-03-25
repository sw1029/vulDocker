#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib_named_case_env.sh"
CASESET_HELPER="${VULD_NAMED_SUPPORT_CASESET_HELPER:-${SCRIPT_DIR}/run_named_case_set.sh}"
SUPPORT_HELPER="${VULD_NAMED_SUPPORT_HELPER:-${SCRIPT_DIR}/run_support_workflow_chain.sh}"

named_support_export_env "" "/tmp/vuld_named_support_case_set"
named_caseset_dispatch "${CASESET_HELPER}" "NAMED-SUPPORT" "${SUPPORT_HELPER}" "$@"
