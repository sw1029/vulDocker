#!/usr/bin/env bash

operator_emit_matrix_case_pair_args() {
  local case_a="${1:-}"
  local case_b="${2:-}"

  printf '%s\n' \
    "${case_a:-foobar-name-only-negative}" \
    "${case_b:-open-redirect-strict-dynamic-no-remote}"
}
