#!/usr/bin/env bash

_REPEATABILITY_SPECS_RUNNER_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_REPEATABILITY_SPECS_RUNNER_LIB_DIR}/lib_case_chain_specs_surface.sh"

repeatability_run_case_specs() {
  case_chain_run_repeatability_specs_surface "$@"
}
