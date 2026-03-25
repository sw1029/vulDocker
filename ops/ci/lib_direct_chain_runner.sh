#!/usr/bin/env bash

_DIRECT_CHAIN_RUNNER_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_DIRECT_CHAIN_RUNNER_LIB_DIR}/lib_case_chain_specs_surface.sh"

direct_run_case_specs() {
  case_chain_run_direct_specs_surface "$@"
}
