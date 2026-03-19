# workspaces/metadata/artifacts 구조

Status: support
Audience: implementation
Source of truth for: generated workspace paths, metadata/artifact layout, measured/support artifact locations
Not the source of truth for: roadmap, claim policy, operator quickstart
Last validated against: workspace layout and measured/support workflow artifacts on 2026-03-19

Relevant canonical docs:
- [현재 상태](../current_state_gap_analysis.md)
- [제약조건](../constraints.md)
- [로드맵](../final_solution.md)
- [핸드북](../handbook.md)
- success criteria 5축과 backlog owner 대응: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Completion Axis Map`
- completion companion set과 canonical reading order: [docs/work_tickets.md](../work_tickets.md)의 `Completion Companions`, `Open-World Completion Reading Order`
- success criteria 5축의 완료판정 질문과 최소 근거: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Completion Checklist`
- success criteria 5축의 canonical 완료 검토 순서: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Completion Review Flow`
- latest confirmed residual의 축별 ticket bundle 분해: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Residual Ticket Breakdown`
- [검증 하니스](../../tests/e2e/README.md)

## Core Layout

워크스페이스
- 경로: `workspaces/<SID>/app/` 또는 multi-bundle일 때 `workspaces/<SID>/<bundle_subdir>/`
- 대표 파일: `app.py`, `Dockerfile`, `requirements.txt`, `poc.py`, seed/schema/init script

메타데이터
- 경로: `metadata/<SID>/...`
- 대표 파일:
  - `plan.json`
  - `researcher_report.json`
  - `generator_manifest.json`
  - `generator_runs.json`
  - `resolved_contract.json`
  - `manifest.json` or `failure_manifest.json`
  - `reviewer_reports.json`
  - `loop_state.json`
  - `performance_summary.json`
  - `generator_failures.jsonl`

실행 아티팩트
- 경로: `artifacts/<SID>/build|run|reports/...`
- 대표 파일:
  - `build/build.log`
  - `build/sbom.spdx.json`
  - `run/run.log`
  - `run/summary.json`
  - `run/index.json`
  - `run/oracle_execution.json`
  - `reports/evals.json`

## Measured / Support Workflow Artifacts

`tests/e2e/run_case.py`, `repeat_case.py`, `support_review.py`, `support_decide.py`, `support_apply.py`는 보통 operator가 지정한 output directory 아래에 JSON artifact를 남긴다. 이 경로는 `metadata/<SID>`나 `artifacts/<SID>`에 고정되지 않는다.

대표 artifact:
- `summary.json`: case direct-run summary, `execution_salt`, top-level runtime/oracle verdict surface
- `repeatability_report.json`: attempt rollup, `observed_execution_salts`, `distinct_sid_count`, `measured_gate`
- `matrix_report.json`: matrix axes rollup, quality observations, measured-gate observations
- `support_candidate.json`: measured support candidate, blocker classes, `support_status`
- `support_review_index.json`: review queue aggregate, `by_case_status`, explicit case lists
- `support_registry_update.json`: reviewer decision preview, `accepted/rejected/pending_by_support_status`, case-level aggregate
- `curated_support_registry.json`: local registry current state, `by_case_review_status`, `last_update`, schema/history surface

## Open-World Axis Artifact Hints

[docs/work_tickets.md](../work_tickets.md)의 `Open-World Completion Axis Map`을 workspace artifact 관점으로 읽으면 아래와 같다.

- 선택
  - `metadata/<SID>/plan.json`
  - `metadata/<SID>/researcher_report.json`
  - representative E2E `summary.json`의 `request_ir`, `selection_decision`, `name_only_outcome`
- 생성
  - `metadata/<SID>/generator_manifest.json`
  - `metadata/<SID>/generator_runs.json`
  - `metadata/<SID>/generator_failures.jsonl`
  - `metadata/<SID>/loop_state.json`
  - `metadata/<SID>/manifest.json` 또는 `failure_manifest.json`
- 실행
  - `metadata/<SID>/manifest.json`의 `runtime_graph`, `executor_plan`
  - `artifacts/<SID>/run/summary.json`
  - representative E2E `summary.json`
- 검증
  - `artifacts/<SID>/run/oracle_execution.json`
  - `artifacts/<SID>/reports/evals.json`
  - `<OUT_DIR>/repeatability_report.json`
  - `<OUT_DIR>/matrix_report.json`
- 보고
  - representative E2E `summary.json`의 `name_only_outcome`
  - `<OUT_DIR>/support_candidate.json`
  - `support_review_index.json`
  - `support_registry_update.json`
  - `curated_support_registry.json`

## Reading Hints

- runtime/executor truth를 볼 때는 `metadata/<SID>/manifest.json` 또는 `failure_manifest.json`만 보지 말고 `metadata/<SID>/generator_manifest.json`, `artifacts/<SID>/run/summary.json`, E2E `summary.json`을 같이 본다.
- measured/support workflow를 볼 때는 `support_candidate.json -> support_review_index.json -> support_registry_update.json -> curated_support_registry.json` 순서로 읽는다.
- current workflow는 preview/current-state/apply-context에서 같은 vocabulary를 유지하려고 한다. 핵심 token은 `measured_gate`, `support_status`, `by_case_status`, `by_case_review_status`, `last_update`다.
- `measured_gate.ready=false`는 repeatability artifact 생성 실패가 아니라 promotion/measured policy 미통과를 뜻한다.
- `blocked_mixed` / `all_blocked` / `all_accepted` 같은 token은 bundle-level truth를 case-level current state로 압축한 해석 surface다.
- `blocked_unclassified`는 주로 legacy/default normalization에서 온 blocked state다.

## Residual Review Focus

- selection/생성 residual은 `generator_manifest.json`, `generator_failures.jsonl`, `loop_state.json`, representative E2E `summary.json`에서 stage/branch authority를 먼저 본다.
- 실행/검증 residual은 `run/summary.json`, `run/oracle_execution.json`, `reports/evals.json`이 graph/runtime/oracle truth를 얼마나 직접 보존하는지부터 본다.
- 보고 residual은 `support_candidate.json -> support_review_index.json -> support_registry_update.json -> curated_support_registry.json` chain이 actual accept/reject lifecycle까지 이어지는지부터 본다.

## Completion Review Focus

- 선택/생성 completion은 `plan.json`, `researcher_report.json`, `generator_manifest.json`, `generator_failures.jsonl`, representative `summary.json`이 같은 branch/stage authority를 남기는지부터 본다.
- 실행/검증/보고 completion은 `manifest.json`, `run/summary.json`, `oracle_execution.json`, `evals.json`, measured/support artifacts가 같은 runtime/oracle/report vocabulary를 끝까지 보존하는지부터 본다.

## Review Mode Entry

이 문서를 열 때는 아래 mode entry를 먼저 고른다.

- 검증:
  - 이 문서의 `Reading Hints`
- 완료판정:
  - 이 문서의 `Completion Review Focus`
  - [docs/code/README.md](README.md)의 `Completion Review Entry`
- 잔여 구현 검토:
  - 이 문서의 `Residual Review Focus`
  - [docs/code/README.md](README.md)의 `Residual Review Entry`

## Data Contract Summary

- 각 stage는 표준 경로나 E2E output directory에 자신의 산출물을 기록하고, 다음 stage는 이를 읽어 집계/판단한다.
- local registry workflow는 actual write/merge를 수행하지만 여전히 measured/manual workflow다. auto-promotion pipeline으로 읽으면 안 된다.

## Ticket-First Artifact Reading

- `TKT-001`, `TKT-006`을 볼 때:
  - `metadata/<SID>/generator_manifest.json`
  - `metadata/<SID>/generator_failures.jsonl`
  - `metadata/<SID>/loop_state.json`
  - `metadata/<SID>/manifest.json`
- `TKT-002` ~ `TKT-005`, `TKT-007`을 볼 때:
  - `artifacts/<SID>/run/summary.json`
  - `artifacts/<SID>/run/oracle_execution.json`
  - `artifacts/<SID>/reports/evals.json`
- `TKT-008`, `TKT-009`를 볼 때:
  - `<OUT_DIR>/repeatability_report.json`
  - `<OUT_DIR>/matrix_report.json`
  - `<OUT_DIR>/support_candidate.json`
  - `support_review_index.json`
  - `support_registry_update.json`
  - `curated_support_registry.json`

## How To Update This Document

- workspace/metadata/artifact path나 measured/support artifact layout이 바뀔 때만 갱신한다.
- current rerun truth나 current token meaning 자체는 [docs/current_state_gap_analysis.md](../current_state_gap_analysis.md), [docs/constraints.md](../constraints.md)에 남긴다.
- operator procedure는 [docs/handbook.md](../handbook.md)를 우선한다.
- completion review focus가 바뀌면 same artifact/vocabulary mapping에 맞춰 이 문서도 같이 갱신한다.
- ticket-first artifact reading 순서가 바뀌면 이 문서의 해당 섹션도 같이 갱신한다.
- success criteria 5축과 artifact 대응이 바뀌면 `Open-World Axis Artifact Hints`도 같이 갱신한다.
- residual review focus가 바뀌면 same artifact chain 기준으로 이 문서도 같이 갱신한다.
- review mode entry shortcut이 바뀌면 [docs/code/README.md](README.md), [docs/handbook.md](../handbook.md)와 같이 갱신한다.
- artifact를 생산하는 rerun/support harness 경로가 바뀌면 [tests/e2e/README.md](../../tests/e2e/README.md)와 같이 갱신한다.
