#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib_support_review_output_surface.sh"
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib_support_review_output_notes.sh"
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib_support_review_helper_contract.sh"
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib_support_review_run_dirs.sh"
PYTHON_BIN="${VULD_SUPPORT_REVIEW_PYTHON_BIN:-python}"
OUTPUT_ROOT="${VULD_SUPPORT_REVIEW_OUTPUT_ROOT:-/tmp/vuld_support_review_chain}"
REVIEW_ONLY="${VULD_SUPPORT_REVIEW_REVIEW_ONLY:-0}"
DECISIONS_FILE="${VULD_SUPPORT_REVIEW_DECISIONS_FILE:-}"
support_review_prepare_prefixed_output_surface \
  "VULD_SUPPORT_REVIEW" \
  "${OUTPUT_ROOT}" \
  "support_review.json" REVIEW_OUTPUT_NAME \
  "support_decisions.json" DECISIONS_OUTPUT_NAME \
  "support_update.json" UPDATE_OUTPUT_NAME \
  "support_registry.json" REGISTRY_OUTPUT_NAME

if [[ "$#" -lt 1 ]]; then
  echo "usage: ops/ci/run_support_review_chain.sh <run-dir> [<run-dir> ...]" >&2
  exit 1
fi

support_review_require_run_dirs "SUPPORT-REVIEW" "$@"

mkdir -p "${OUTPUT_ROOT}"

REVIEW_OUT="${VULD_SUPPORT_REVIEW_RESOLVED_REVIEW_OUT}"
echo "[SUPPORT-REVIEW] support review aggregate -> ${REVIEW_OUT}"
"${PYTHON_BIN}" tests/e2e/support_review.py \
  "$@" \
  --output "${REVIEW_OUT}"

if [[ "${REVIEW_ONLY}" = "1" ]]; then
  support_review_emit_prefixed_review_only_completion "SUPPORT-REVIEW" "VULD_SUPPORT_REVIEW"
  exit 0
fi

DECISIONS_OUT="${VULD_SUPPORT_REVIEW_RESOLVED_DECISIONS_OUT}"
support_review_materialize_decisions_file "${DECISIONS_FILE}" "${DECISIONS_OUT}"

UPDATE_OUT="${VULD_SUPPORT_REVIEW_RESOLVED_UPDATE_OUT}"
echo "[SUPPORT-REVIEW] support decide preview -> ${UPDATE_OUT}"
"${PYTHON_BIN}" tests/e2e/support_decide.py \
  --review-index "${REVIEW_OUT}" \
  --decisions "${DECISIONS_OUT}" \
  --output "${UPDATE_OUT}"

REGISTRY_OUT="${VULD_SUPPORT_REVIEW_RESOLVED_REGISTRY_OUT}"
echo "[SUPPORT-REVIEW] support apply local registry -> ${REGISTRY_OUT}"
"${PYTHON_BIN}" tests/e2e/support_apply.py \
  --registry-update "${UPDATE_OUT}" \
  --output "${REGISTRY_OUT}"

support_review_emit_prefixed_standard_completion "SUPPORT-REVIEW" "VULD_SUPPORT_REVIEW"
