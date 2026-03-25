#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_EXAMPLE_SCRIPT="${VULD_BASE_EXAMPLE_SCRIPT:-${SCRIPT_DIR}/run_base_example.sh}"

if [[ ! -f "${BASE_EXAMPLE_SCRIPT}" ]]; then
  echo "[BASE] base example helper not found: ${BASE_EXAMPLE_SCRIPT}" >&2
  exit 1
fi

exec "${BASE_EXAMPLE_SCRIPT}" "$@"
