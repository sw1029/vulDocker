#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib_named_case_helper_contract.sh"

TARGET_HELPER="${VULD_NAMED_CASE_TARGET_HELPER:-}"
LOG_PREFIX="${VULD_NAMED_CASE_LOG_PREFIX:-NAMED-CASE}"

if [[ "$#" -lt 1 ]]; then
  echo "usage: ops/ci/run_named_case_set.sh <case-slug-or-dir[=alias]> [<case-slug-or-dir[=alias]> ...]" >&2
  exit 1
fi

if ! named_case_require_target_helper "${TARGET_HELPER}" "${LOG_PREFIX}" "target helper not configured"; then
  exit 1
fi

"${TARGET_HELPER}" "$@"
