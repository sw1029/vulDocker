#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
source "${SCRIPT_DIR}/lib_cases_output_roots.sh"
source "${SCRIPT_DIR}/lib_repeatability_chain_runner.sh"
source "${SCRIPT_DIR}/lib_support_review_output_surface.sh"
source "${SCRIPT_DIR}/lib_support_review_output_notes.sh"
source "${SCRIPT_DIR}/lib_support_review_runner.sh"
REPEAT_HELPER="${VULD_SUPPORT_WORKFLOW_REPEAT_HELPER:-${SCRIPT_DIR}/run_repeatability_chain.sh}"
REVIEW_HELPER="${VULD_SUPPORT_WORKFLOW_REVIEW_HELPER:-${SCRIPT_DIR}/run_support_review_chain.sh}"
PYTHON_BIN="${VULD_SUPPORT_WORKFLOW_PYTHON_BIN:-python}"
resolve_cases_output_roots \
  "VULD_SUPPORT_WORKFLOW" \
  "${REPO_ROOT}" \
  "/tmp/vuld_support_workflow_chain" \
  "CASES_ROOT" \
  "OUTPUT_ROOT"
REPEAT_MODE="${VULD_SUPPORT_WORKFLOW_MODE:-deterministic}"
REPEAT_ATTEMPTS="${VULD_SUPPORT_WORKFLOW_ATTEMPTS:-2}"
REVIEW_ONLY="${VULD_SUPPORT_WORKFLOW_REVIEW_ONLY:-0}"
DECISIONS_FILE="${VULD_SUPPORT_WORKFLOW_DECISIONS_FILE:-}"
NO_SNAPSHOT="${VULD_SUPPORT_WORKFLOW_NO_SNAPSHOT:-0}"
ALLOW_REPEAT_FAILURE_WITH_REPORT="${VULD_SUPPORT_WORKFLOW_ALLOW_REPEAT_FAILURE_WITH_REPORT:-1}"
DOCKER_RETRY_COUNT="${VULD_SUPPORT_WORKFLOW_DOCKER_RETRY_COUNT:-}"
DOCKER_RETRY_DELAY_SEC="${VULD_SUPPORT_WORKFLOW_DOCKER_RETRY_DELAY_SEC:-}"
support_review_prepare_prefixed_output_surface \
  "VULD_SUPPORT_WORKFLOW" \
  "${OUTPUT_ROOT}" \
  "support_review.json" REVIEW_OUTPUT_NAME \
  "support_decisions.json" DECISIONS_OUTPUT_NAME \
  "support_update.json" UPDATE_OUTPUT_NAME \
  "support_registry.json" REGISTRY_OUTPUT_NAME
PERMISSION_ARTIFACT_NAME="${VULD_SUPPORT_WORKFLOW_PERMISSION_ARTIFACT_NAME:-docker_permission_artifact.txt}"
PERMISSION_SUMMARY_NAME="${VULD_SUPPORT_WORKFLOW_PERMISSION_SUMMARY_NAME:-permission_artifact_summary.json}"

if [[ "$#" -lt 1 ]]; then
  echo "usage: ops/ci/run_support_workflow_chain.sh <case-slug-or-dir> [<case-slug-or-dir> ...]" >&2
  exit 1
fi

repeatability_run_helper_and_postprocess \
  REPEAT_OUTPUTS \
  PERMISSION_ARTIFACT_CASES \
  PERMISSION_SUMMARY_PATH \
  "${REPEAT_HELPER}" \
  "${PYTHON_BIN}" \
  "${CASES_ROOT}" \
  "${OUTPUT_ROOT}" \
  "${REPEAT_MODE}" \
  "${REPEAT_ATTEMPTS}" \
  "${NO_SNAPSHOT}" \
  "${ALLOW_REPEAT_FAILURE_WITH_REPORT}" \
  "${PERMISSION_ARTIFACT_NAME}" \
  "${PERMISSION_SUMMARY_NAME}" \
  "${DOCKER_RETRY_COUNT}" \
  "${DOCKER_RETRY_DELAY_SEC}" \
  "SUPPORT" \
  "$@"

support_review_run_helper \
  "SUPPORT" \
  "${REVIEW_HELPER}" \
  "${PYTHON_BIN}" \
  "${OUTPUT_ROOT}" \
  "${REVIEW_ONLY}" \
  "${DECISIONS_FILE}" \
  "${REVIEW_OUTPUT_NAME}" \
  "${DECISIONS_OUTPUT_NAME}" \
  "${UPDATE_OUTPUT_NAME}" \
  "${REGISTRY_OUTPUT_NAME}" \
  "${REPEAT_OUTPUTS[@]}"

if [[ "${REVIEW_ONLY}" = "1" ]]; then
  support_review_emit_prefixed_review_only_completion \
    "SUPPORT" \
    "VULD_SUPPORT_WORKFLOW" \
    "permission_summary_out" "${PERMISSION_SUMMARY_PATH}"
  exit 0
fi

support_review_emit_prefixed_standard_completion \
  "SUPPORT" \
  "VULD_SUPPORT_WORKFLOW" \
  "permission_summary_out" "${PERMISSION_SUMMARY_PATH}"
