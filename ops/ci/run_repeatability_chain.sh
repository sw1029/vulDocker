#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib_case_chain_standard_script_entrypoint.sh"
case_chain_run_repeatability_standard_script_entrypoint "${BASH_SOURCE[0]}" "$@"
