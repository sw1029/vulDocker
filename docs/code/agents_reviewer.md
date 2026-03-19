# agents/reviewer 디렉토리

Status: support
Audience: implementation
Source of truth for: reviewer entrypoints, review surfaces, blocking interpretation before PACK
Not the source of truth for: support-promotion workflow, measured gate policy, project roadmap
Last validated against: current repo layout, reviewer/run-summary integration, and workflow boundary clarification on 2026-03-19

Relevant canonical docs:
- [현재 상태](../current_state_gap_analysis.md)
- [제약조건](../constraints.md)
- [로드맵](../final_solution.md)
- [작업 티켓](../work_tickets.md)
- success criteria 5축과 backlog owner 대응: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Completion Axis Map`
- completion companion set과 canonical reading order: [docs/work_tickets.md](../work_tickets.md)의 `Completion Companions`, `Open-World Completion Reading Order`
- success criteria 5축의 완료판정 질문과 최소 근거: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Completion Checklist`
- success criteria 5축의 canonical 완료 검토 순서: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Completion Review Flow`
- latest confirmed residual의 축별 ticket bundle 분해: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Residual Ticket Breakdown`
- [검증 하니스](../../tests/e2e/README.md)

## 핵심 파일

- `agents/reviewer/main.py`: reviewer CLI entry
- `agents/reviewer/service.py`: run log + static pattern + verifier/runtime signal을 읽어 blocking 여부 판단
- `orchestrator/plugins/react_loop.py`: reviewer loop / span trace 유틸

## 데이터 계약

- 입력:
  - `artifacts/<SID>/run/run.log`
  - `artifacts/<SID>/run/summary.json`
  - `artifacts/<SID>/reports/evals.json`
  - `metadata/<SID>/plan.json`
  - optional `guard_spec.json`
- 출력:
  - bundle review report JSON
  - `reviewer_reports.json`
  - `loop_state.json`

## 현재 구현상 포인트

- reviewer는 실행 결과와 정적 힌트를 결합해 수정 지시를 내리고, PACK 전에 blocking 여부를 결정한다.
- reviewer는 `run_passed`, `verify_pass`, `oracle_execution_parity`, guard mismatch 같은 downstream signal을 소비하지만, measured gate나 support-promotion policy의 primary owner는 아니다.
- 현재 workflow에서 `agents/reviewer/*`의 review와 `tests/e2e/support_review.py`의 measured/manual support review는 서로 다른 단계다.
- 전자는 bundle quality / blocking / repair guidance를 위한 pipeline reviewer이고, 후자는 measured repeatability artifact를 curated support candidate로 올릴지 말지 보는 operator-facing workflow다.

## Current Residual Owners

- broader browserful/stateful oracle realism residual은 `TKT-007-A/B` owner다.
- measured gate / support workflow policy residual은 `TKT-008-A*`, `TKT-009-A*` owner다.
- reviewer는 위 residual의 결과를 소비하는 downstream component이지 primary policy owner가 아니다.

## Residual Review Focus

- `TKT-007` residual은 reviewer가 어떤 oracle richness/result를 소비하는지 boundary 확인용으로만 보고, primary oracle policy owner와 혼동하지 않는지 본다.
- `TKT-008` / `TKT-009` residual은 pipeline reviewer와 measured/manual support review의 경계가 흐려지지 않는지부터 본다.

## Completion Review Focus

- `TKT-007` completion은 reviewer가 richer oracle realism을 소비하되, reviewer 자체를 primary oracle-policy owner로 과장하지 않는지부터 본다.
- `TKT-008`, `TKT-009` completion은 pipeline reviewer blocking surface와 measured/manual support review surface가 artifact와 vocabulary 상에서도 계속 분리되는지부터 본다.

## Review Mode Entry

이 문서를 열 때는 아래 mode entry를 먼저 고른다.

- 검증:
  - 이 문서의 `Representative Validation Surface`
- 완료판정:
  - 이 문서의 `Completion Review Focus`
  - [docs/code/README.md](README.md)의 `Completion Review Entry`
- 잔여 구현 검토:
  - 이 문서의 `Residual Review Focus`
  - [docs/code/README.md](README.md)의 `Residual Review Entry`

## Ticket-First Entry

- pipeline reviewer behavior를 볼 때:
  - `agents/reviewer/service.py`
  - `artifacts/<SID>/run/summary.json`
  - `artifacts/<SID>/reports/evals.json`
  - `metadata/<SID>/reviewer_reports.json`
- reviewer loop / span trace를 볼 때:
  - `orchestrator/plugins/react_loop.py`
  - `metadata/<SID>/loop_state.json`
- measured/manual support review와의 경계를 볼 때:
  - `agents/reviewer/service.py`
  - `tests/e2e/support_review.py`

## Representative Validation Surface

- reviewer blocking/boundary regression:
  - `tests/test_reviewer_blocking_policy.py`
  - `tests/test_run_pipeline_failure_resolution.py`
  - `tests/test_pack_promotion.py`
- representative workflow sanity:
  - pipeline direct rerun 후 `reviewer_reports.json`
  - measured/manual queue는 `tests/e2e/test_support_workflow.py`로 별도 확인

## How To Update This Document

- reviewer entrypoint, review surface, blocking interpretation boundary가 바뀔 때만 갱신한다.
- current rerun truth나 measured/support workflow 결과는 [docs/current_state_gap_analysis.md](../current_state_gap_analysis.md)에 남긴다.
- current non-claim과 workflow boundary는 [docs/constraints.md](../constraints.md)에 남긴다.
- owner와 sequencing은 [docs/final_solution.md](../final_solution.md), [docs/work_tickets.md](../work_tickets.md)로 보낸다.
- ticket-first entrypoint나 representative validation surface가 바뀌면 이 문서의 해당 섹션도 같이 갱신한다.
- completion review focus가 바뀌면 same workflow boundary 기준으로 이 문서도 같이 갱신한다.
- residual review focus가 바뀌면 same workflow boundary 기준으로 이 문서도 같이 갱신한다.
- review mode entry shortcut이 바뀌면 [docs/code/README.md](README.md)와 같이 갱신한다.
- reviewer와 measured/manual review의 harness boundary가 바뀌면 [tests/e2e/README.md](../../tests/e2e/README.md)와 같이 갱신한다.
