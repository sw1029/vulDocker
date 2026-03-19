# ops 디렉토리

Status: support
Audience: implementation
Source of truth for: CI/ops entrypoints and operational automation boundaries
Not the source of truth for: roadmap, support-promotion policy, current rerun baseline tables
Last validated against: current repo layout and operational script surface on 2026-03-19

Relevant canonical docs:
- [핸드북](../handbook.md)
- [제약조건](../constraints.md)
- [현재 상태](../current_state_gap_analysis.md)
- [작업 티켓](../work_tickets.md)
- success criteria 5축과 backlog owner 대응: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Completion Axis Map`
- completion companion set과 canonical reading order: [docs/work_tickets.md](../work_tickets.md)의 `Completion Companions`, `Open-World Completion Reading Order`
- success criteria 5축의 완료판정 질문과 최소 근거: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Completion Checklist`
- success criteria 5축의 canonical 완료 검토 순서: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Completion Review Flow`
- latest confirmed residual의 축별 ticket bundle 분해: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Residual Ticket Breakdown`
- [검증 하니스](../../tests/e2e/README.md)

## 구성 요소

- `ops/ci/run_case.sh`: PLAN -> optional RESEARCH -> GENERATE -> EXECUTE -> EVALS -> REVIEW -> PACK smoke pipeline
- `ops/ci/smoke_regression.sh`: 기본 회귀 실행 시나리오
- `ops/observability/dashboard_spec.md`: KPI/observability dashboard spec

## 현재 운영 경계

- `ops/ci/*`는 core pipeline의 표준 `metadata/<SID>` / `artifacts/<SID>` surface를 소비한다.
- `tests/e2e/repeat_case.py`, `support_review.py`, `support_decide.py`, `support_apply.py`는 현재 measured/manual workflow이며 `ops/ci/*`의 canonical auto-promotion path는 아니다.
- 따라서 local registry write/merge workflow가 존재해도 현재 운영 자동화는 `support_registry_update.json -> curated_support_registry.json` chain을 CI default path로 읽지 않는다.

## 데이터 계약 / 출력

- CI 스크립트는 각 단계의 표준 출력과 산출물(`metadata/`, `artifacts/`)을 그대로 이용하며, 실패 시 종료 코드를 전파한다.
- measured/support workflow는 operator-specified output directory에 `repeatability_report.json`, `matrix_report.json`, `support_candidate.json`, `support_review_index.json`, `support_registry_update.json`, `curated_support_registry.json`을 남길 수 있지만, 이것은 현재 수동 review/update rehearsal surface다.

## 프로젝트 내 역할

- 수동 실행을 자동화하고 회귀/KPI를 관측 가능한 형태로 유지한다.
- authoritative measured gate / CI policy closure는 roadmap상 `Phase 5B`, backlog상 `TKT-008-A2` owner다.
- curated registry closure는 backlog상 `TKT-009-A1/B*` owner이며, 현재 ops 문서는 그 workflow 존재와 경계만 설명한다.

## Residual Review Focus

- `TKT-008-A2` residual은 CI/automation boundary가 measured gate authoritative policy와 어디서 만나는지부터 본다.
- `TKT-009-*` residual은 ops가 local/manual workflow를 auto-promotion처럼 다루지 않는지 boundary를 먼저 본다.

## Completion Review Focus

- `TKT-008-A2` completion은 CI/automation path가 measured gate를 optional preview가 아니라 authoritative policy boundary로 실제 소비하는지부터 본다.
- `TKT-009-*` completion은 local/manual registry workflow와 auto-promotion boundary가 운영 문서와 스크립트 양쪽에서 계속 분리되는지부터 본다.

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

- core CI / smoke path를 볼 때:
  - `ops/ci/run_case.sh`
  - `ops/ci/smoke_regression.sh`
- measured gate / CI policy와 맞닿는 경계를 볼 때:
  - `ops/ci/*`
  - `tests/e2e/repeat_case.py`
  - `tests/e2e/matrix_report.py`
- support workflow automation boundary를 볼 때:
  - `tests/e2e/support_review.py`
  - `tests/e2e/support_decide.py`
  - `tests/e2e/support_apply.py`

## Representative Validation Surface

- ops/environment sanity:
  - `tests/test_e2e_env_checks.py`
  - `tests/test_plan_sid_isolation.py`
- CI boundary sanity:
  - `tests/e2e/test_cases.py`
  - `tests/e2e/test_case_matrix_rollup.py`
  - `tests/e2e/test_support_workflow.py`

## How To Update This Document

- CI/ops entrypoint, automation boundary, observability script surface가 바뀔 때만 갱신한다.
- current rerun truth나 local verification result는 [docs/current_state_gap_analysis.md](../current_state_gap_analysis.md)에 남긴다.
- current operational constraint와 auto-promotion non-claim은 [docs/constraints.md](../constraints.md)에 남긴다.
- owner와 sequencing은 [docs/final_solution.md](../final_solution.md), [docs/work_tickets.md](../work_tickets.md)로 보낸다.
- ticket-first entrypoint나 representative validation surface가 바뀌면 이 문서의 해당 섹션도 같이 갱신한다.
- completion review focus가 바뀌면 same owner/ticket mapping에 맞춰 이 문서도 같이 갱신한다.
- residual review focus가 바뀌면 same ops boundary 기준으로 이 문서도 같이 갱신한다.
- review mode entry shortcut이 바뀌면 [docs/code/README.md](README.md)와 같이 갱신한다.
- CI boundary에 연결된 harness path가 바뀌면 [tests/e2e/README.md](../../tests/e2e/README.md)와 같이 갱신한다.
