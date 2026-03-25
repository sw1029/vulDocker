#!/usr/bin/env bash

build_positive_pair_case_specs() {
  local trusted_case="${1:-trusted-dynamic-sqli}"
  local open_redirect_case="${2:-open-redirect-dynamic-name-only}"
  printf '%s\n' \
    "${trusted_case}=trusted_dynamic" \
    "${open_redirect_case}=open_redirect_dynamic"
}

build_blocked_noop_case_specs() {
  local foobar_case="${1:-foobar-name-only-negative}"
  local strict_case="${2:-open-redirect-strict-dynamic-no-remote}"
  printf '%s\n' \
    "${foobar_case}=foobar" \
    "${strict_case}=strict"
}

build_low_cost_case_specs() {
  local strict_no_remote_case="${1:-open-redirect-strict-dynamic-no-remote}"
  local strict_stub_case="${2:-open-redirect-strict-dynamic-stub}"
  local negative_case="${3:-foobar-name-only-negative}"
  printf '%s\n' \
    "${strict_no_remote_case}=strict_no_remote" \
    "${strict_stub_case}=strict_stub" \
    "${negative_case}=negative"
}

build_matrix_pair_case_specs() {
  local case_a="${1:-foobar-name-only-negative}"
  local case_b="${2:-open-redirect-strict-dynamic-no-remote}"
  printf '%s\n' "${case_a}" "${case_b}"
}
