#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib_cases_output_roots.sh"

operator_resolve_cases_output_roots() {
  resolve_cases_output_roots "$@"
}
