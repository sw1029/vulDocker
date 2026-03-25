#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
source "${SCRIPT_DIR}/lib_support_review_output_surface.sh"
source "${SCRIPT_DIR}/lib_support_review_output_notes.sh"
source "${SCRIPT_DIR}/lib_support_review_runner.sh"
REVIEW_HELPER="${VULD_REVIEWABLE_ACCEPT_REVIEW_HELPER:-${SCRIPT_DIR}/run_support_review_chain.sh}"
PYTHON_BIN="${VULD_REVIEWABLE_ACCEPT_PYTHON_BIN:-python}"
OUTPUT_ROOT="${VULD_REVIEWABLE_ACCEPT_OUTPUT_ROOT:-/tmp/vuld_reviewable_accept_check}"
CASE_NAME="${VULD_REVIEWABLE_ACCEPT_CASE_NAME:-cwe-89-basic}"
SLUG="${VULD_REVIEWABLE_ACCEPT_SLUG:-cwe-89}"
VULN_ID="${VULD_REVIEWABLE_ACCEPT_VULN_ID:-CWE-89}"
REVIEWER="${VULD_REVIEWABLE_ACCEPT_REVIEWER:-alice}"
RATIONALE="${VULD_REVIEWABLE_ACCEPT_RATIONALE:-synthetic reviewable lane}"
support_review_prepare_prefixed_output_surface \
  "VULD_REVIEWABLE_ACCEPT" \
  "${OUTPUT_ROOT}" \
  "support_review_index.json" REVIEW_OUTPUT_NAME \
  "support_review_decisions.json" DECISIONS_OUTPUT_NAME \
  "support_registry_update.json" UPDATE_OUTPUT_NAME \
  "curated_support_registry.json" REGISTRY_OUTPUT_NAME

mkdir -p "${OUTPUT_ROOT}/reviewable-run"

CANDIDATE_PATH="${OUTPUT_ROOT}/reviewable-run/support_candidate.json"
REVIEW_INDEX_PATH="${VULD_SUPPORT_REVIEW_RESOLVED_REVIEW_OUT}"
DECISIONS_PATH="${VULD_SUPPORT_REVIEW_RESOLVED_DECISIONS_OUT}"
REGISTRY_UPDATE_PATH="${VULD_SUPPORT_REVIEW_RESOLVED_UPDATE_OUT}"
REGISTRY_PATH="${VULD_SUPPORT_REVIEW_RESOLVED_REGISTRY_OUT}"

cat > "${CANDIDATE_PATH}" <<EOF
{
  "schema_version": "support_candidate@0.1",
  "case_name": "${CASE_NAME}",
  "sid": "sid-reviewable",
  "manifest_path": "/tmp/manifest-a.json",
  "support_ready_bundle_count": 1,
  "mechanically_healthy_bundle_count": 1,
  "promotion_policy_ready_bundle_count": 1,
  "reviewable_bundle_count": 1,
  "all_reviewable": true,
  "candidates": [
    {
      "slug": "${SLUG}",
      "vuln_id": "${VULN_ID}",
      "reviewable": true,
      "support_promotion_eligible": true,
      "support_status": "reviewable",
      "blockers": [],
      "mechanical_blockers": [],
      "promotion_policy_blockers": [],
      "gates": {
        "verdict_authority_ready": true,
        "measured_gate_ready": true,
        "mechanically_healthy": true,
        "promotion_policy_ready": true
      },
      "primitive_signature": {
        "selected_family": "sqli",
        "selected_stack_id": "python/flask"
      },
      "runtime_contract": {
        "topology": "single_service"
      },
      "oracle_contract": {
        "oracle_execution_parity": "high"
      },
      "verdict_authority_mode": "single_bundle",
      "verdict_authority_consistent": true,
      "source_artifacts": {
        "summary_path": "/tmp/summary-a.json",
        "workspace": "/tmp/workspace-a"
      }
    }
  ]
}
EOF

cat > "${DECISIONS_PATH}" <<EOF
{
  "schema_version": "support_review_decisions@0.1",
  "decisions": [
    {
      "case_name": "${CASE_NAME}",
      "slug": "${SLUG}",
      "decision": "accept",
      "reviewer": "${REVIEWER}",
      "rationale": "${RATIONALE}"
    }
  ]
}
EOF

support_review_run_helper \
  "REVIEWABLE" \
  "${REVIEW_HELPER}" \
  "${PYTHON_BIN}" \
  "${OUTPUT_ROOT}" \
  "" \
  "${DECISIONS_PATH}" \
  "${REVIEW_OUTPUT_NAME}" \
  "${DECISIONS_OUTPUT_NAME}" \
  "${UPDATE_OUTPUT_NAME}" \
  "${REGISTRY_OUTPUT_NAME}" \
  "${OUTPUT_ROOT}/reviewable-run"

support_review_emit_prefixed_reviewable_accept_completion "REVIEWABLE" "VULD_REVIEWABLE_ACCEPT"
