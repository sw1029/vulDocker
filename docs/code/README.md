# 코드 디렉토리별 상세 설명 인덱스

Status: support
Audience: implementation
Source of truth for: code navigation entrypoint
Not the source of truth for: project goals, constraints, roadmap
Last validated against: repository layout and measured/support workflow code paths on 2026-03-19

이 인덱스는 구현 엔지니어가 코드 구조를 빠르게 따라가기 위한 문서입니다. 프로젝트 목표는 [docs/problem.md](../problem.md), 현재 제약은 [docs/constraints.md](../constraints.md), 구현 로드맵은 [docs/final_solution.md](../final_solution.md), actionable ticket backlog는 [docs/work_tickets.md](../work_tickets.md)를 봅니다.

## Reader Routing

- operator라면 이 문서보다 [docs/handbook.md](../handbook.md)를 먼저 본다.
- current truth나 current limitation 확인은 [docs/current_state_gap_analysis.md](../current_state_gap_analysis.md), [docs/constraints.md](../constraints.md)를 먼저 본다.
- implementation owner와 priority 확인은 [docs/final_solution.md](../final_solution.md), [docs/work_tickets.md](../work_tickets.md)를 먼저 본다.
- direct rerun command와 measured/support harness 사용법은 [tests/e2e/README.md](../../tests/e2e/README.md)를 먼저 본다.
- 이 문서는 code path navigation과 subsystem entrypoint 탐색에만 쓴다.

특히 phase 설명을 바로 ticket owner로 번역하려면 [docs/final_solution.md](../final_solution.md)의 `Phase-To-Ticket Translation`과 [docs/work_tickets.md](../work_tickets.md)의 `Current Remaining Snapshot` / `Sequencing Rule`을 같이 본다.
실제 작업에 들어갈 때는 같은 [docs/work_tickets.md](../work_tickets.md)의 `Implementation Entry Points And Validation Surface`에서 ticket별 primary code path와 representative validation focus를 먼저 확인한다.
각 subsystem 문서에도 같은 관점의 `Ticket-First Entry`와 `Representative Validation Surface` 섹션을 유지한다.

## Index

- orchestrator: `docs/code/orchestrator.md`
- common: `docs/code/common.md`
- researcher: `docs/code/agents_researcher.md`
- generator: `docs/code/agents_generator.md`
- reviewer: `docs/code/agents_reviewer.md`
- executor: `docs/code/executor.md`
- evals: `docs/code/evals.md`
- rag: `docs/code/rag.md`
- ops: `docs/code/ops.md`
- workspace/metadata/artifacts: `docs/code/workspaces.md`

## Reading Order For Name-Only/Open-World Work

1. orchestrator
2. researcher
3. generator
4. executor
5. evals
6. common

이 순서를 기준으로 `request_ir`, `selection_decision`, `runtime_recipe`, `executor_plan`, `name_only_outcome`, `support_promotion`이 어디서 만들어지고 소비되는지 따라가면 됩니다.

## Reading Order For Measured / Support Workflow

1. orchestrator
2. evals
3. workspace/metadata/artifacts
4. common

이 순서를 기준으로 `repeatability_report.json`, `matrix_report.json`, `support_candidate.json`, `support_review_index.json`, `support_registry_update.json`, `curated_support_registry.json`이 어디서 생성되고 어떤 vocabulary(`measured_gate`, `by_case_status`, `by_case_review_status`, `last_update`)를 보존하는지 따라가면 됩니다.

## Validation Docs

- representative rerun command, case layout, repeatability/support CLI flow는 [tests/e2e/README.md](../../tests/e2e/README.md)를 본다.
- operator quickstart, artifact map, troubleshooting은 [docs/handbook.md](../handbook.md)를 본다.
- ticket별 first harness / regression surface는 [docs/work_tickets.md](../work_tickets.md)의 `Validation Routing`을 본다.

## Validation Companions

구현/검증 관점에서 이 문서와 같이 봐야 할 companion은 아래와 같다.

- success criteria 5축과 backlog owner 대응: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Completion Axis Map`
- completion companion set: [docs/work_tickets.md](../work_tickets.md)의 `Completion Companions`
- success criteria 5축의 완료판정 질문과 최소 근거: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Completion Checklist`
- success criteria 5축의 canonical 완료 검토 순서: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Completion Review Flow`
- success criteria 5축의 canonical 완료판정 reading order: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Completion Reading Order`
- latest confirmed residual의 축별 ticket bundle 분해: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Residual Ticket Breakdown`
- latest confirmed residual의 canonical 구현 검토 순서: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Residual Review Flow`
- latest confirmed residual 검토 문서 순서: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Residual Reading Order`
- residual companion set: [docs/work_tickets.md](../work_tickets.md)의 `Residual Companions`
- review mode별 canonical 시작점: [docs/work_tickets.md](../work_tickets.md)의 `Review Mode Matrix`
- phase acceptance와 validation surface 대응: [docs/final_solution.md](../final_solution.md)
- ticket별 first harness와 reading order: [docs/work_tickets.md](../work_tickets.md)
- concrete rerun/support harness command: [tests/e2e/README.md](../../tests/e2e/README.md)
- operator artifact map / troubleshooting: [docs/handbook.md](../handbook.md)
- success criteria 5축별 artifact reading hints: [docs/handbook.md](../handbook.md)의 `Open-World Axis Reading Hints`, [docs/code/workspaces.md](workspaces.md)의 `Open-World Axis Artifact Hints`
- current truth와 observed rerun evidence: [docs/current_state_gap_analysis.md](../current_state_gap_analysis.md)
- 질문 기반 routing: [docs/work_tickets.md](../work_tickets.md)의 `Validation Question Routing`
- residual 질문 기반 routing: [docs/work_tickets.md](../work_tickets.md)의 `Residual Question Routing`

## Completion Companions

구현/완료판정 관점에서 이 문서와 같이 봐야 할 companion은 아래와 같다.

- completion companion set: [docs/work_tickets.md](../work_tickets.md)의 `Completion Companions`
- axis map / close criteria / canonical review order: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Completion Axis Map`, `Open-World Completion Checklist`, `Open-World Completion Review Flow`
- canonical completion reading order: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Completion Reading Order`
- phase acceptance map: [docs/final_solution.md](../final_solution.md)의 `Acceptance-To-Validation Translation`
- harness entry: [tests/e2e/README.md](../../tests/e2e/README.md)
- artifact reading / troubleshooting: [docs/handbook.md](../handbook.md)
- current truth / non-claim: [docs/current_state_gap_analysis.md](../current_state_gap_analysis.md), [docs/constraints.md](../constraints.md)

## Residual Companions

구현/잔여 구현 검토 관점에서 이 문서와 같이 봐야 할 companion은 아래와 같다.

- residual bucket / ticket bundle: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Residual Ticket Breakdown`
- residual close criteria: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Completion Checklist`
- residual review / reading order: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Residual Review Flow`, `Open-World Residual Reading Order`
- phase acceptance map: [docs/final_solution.md](../final_solution.md)의 `Acceptance-To-Validation Translation`
- harness entry: [tests/e2e/README.md](../../tests/e2e/README.md)
- artifact reading / troubleshooting: [docs/handbook.md](../handbook.md)
- current truth / non-claim: [docs/current_state_gap_analysis.md](../current_state_gap_analysis.md), [docs/constraints.md](../constraints.md)

## Review Mode Entry

구현 문서를 열 때는 아래 mode entry를 먼저 고른다.

- 검증:
  - [docs/work_tickets.md](../work_tickets.md)의 `Review Mode Matrix`
  - 이 문서의 `Validation Reading Order`
- 완료판정:
  - [docs/work_tickets.md](../work_tickets.md)의 `Review Mode Matrix`
  - 이 문서의 `Completion Companions`
- 잔여 구현 검토:
  - [docs/work_tickets.md](../work_tickets.md)의 `Review Mode Matrix`
  - 이 문서의 `Residual Review Entry`

## Validation Reading Order

이 순서는 [docs/work_tickets.md](../work_tickets.md)의 `Validation Reading Order`를 따른다.

1. [docs/work_tickets.md](../work_tickets.md)의 `Validation Routing`
2. [tests/e2e/README.md](../../tests/e2e/README.md)의 harness command / case layout
3. relevant subsystem docs의 `Ticket-First Entry` / `Representative Validation Surface`
4. [docs/handbook.md](../handbook.md)의 artifact map / troubleshooting

## Completion Review Entry

코드 관점에서 완료판정을 검토할 때는 [docs/work_tickets.md](../work_tickets.md)의 `Open-World Completion Review Flow`를 먼저 보고, 이후 relevant subsystem docs의 `Ticket-First Entry` / `Representative Validation Surface`를 따라 actual code path와 artifact surface를 대조한다.

## Completion Reading Order

코드 문서 기준 completion reading order는 아래와 같다.

이 순서는 [docs/work_tickets.md](../work_tickets.md)의 `Open-World Completion Reading Order`를 따른다.

1. [docs/work_tickets.md](../work_tickets.md)의 `Completion Companions`
2. 이 문서의 `Completion Review Entry`
3. relevant subsystem docs의 `Ticket-First Entry` / `Representative Validation Surface`
4. [docs/handbook.md](../handbook.md)의 `Completion Review Entry`

## Residual Review Entry

코드 관점에서 “현재 남은 open-world residual이 어느 ticket bundle에 걸려 있는가”를 먼저 보고 싶다면 [docs/work_tickets.md](../work_tickets.md)의 `Open-World Residual Ticket Breakdown`을 먼저 연 뒤, relevant subsystem docs의 canonical links와 `Ticket-First Entry`를 따라 실제 code path로 내려간다.
이 순서는 [docs/work_tickets.md](../work_tickets.md)의 `Open-World Residual Reading Order`를 따른다.

## Residual Reading Order

코드 문서 기준 residual reading order는 아래와 같다.

1. [docs/work_tickets.md](../work_tickets.md)의 `Open-World Residual Reading Order`
2. 이 문서의 `Residual Review Entry`
3. relevant subsystem docs의 `Residual Review Focus`
4. [docs/handbook.md](../handbook.md)의 `Residual Review Entry`

## How To Update This Document

- code navigation entrypoint로서 index, reading order, subsystem 문서 링크가 바뀔 때만 갱신한다.
- current truth나 current limit 자체는 [docs/current_state_gap_analysis.md](../current_state_gap_analysis.md), [docs/constraints.md](../constraints.md)에 남긴다.
- 새 subsystem 문서를 추가하면 이 index와 relevant reading order를 같이 갱신한다.
- subsystem ownership이나 ticket별 primary validation focus가 바뀌면 [docs/work_tickets.md](../work_tickets.md)의 entrypoint/validation 표와 이 인덱스를 같이 갱신한다.
- validation 문서 진입 순서가 바뀌면 [tests/e2e/README.md](../../tests/e2e/README.md), [docs/handbook.md](../handbook.md)와 같이 갱신한다.
- validation reading order 자체가 바뀌면 README의 검증 진입 순서 설명과도 같이 맞춘다.
- validation companion 관계가 바뀌면 README / handbook / e2e README와 같이 맞춘다.
- validation question routing이 바뀌면 [docs/work_tickets.md](../work_tickets.md)와 같이 맞춘다.
- completion companion 관계가 바뀌면 README / handbook / e2e README와 같이 맞춘다.
- residual companion 관계가 바뀌면 README / handbook / e2e README와 같이 맞춘다.
- residual question routing이 바뀌면 [docs/work_tickets.md](../work_tickets.md)와 같이 맞춘다.
- completion review entrypoint가 바뀌면 [docs/work_tickets.md](../work_tickets.md), [docs/handbook.md](../handbook.md), [tests/e2e/README.md](../../tests/e2e/README.md)와 같이 맞춘다.
- completion reading order가 바뀌면 [docs/work_tickets.md](../work_tickets.md), [README.md](../../README.md), [docs/handbook.md](../handbook.md), [tests/e2e/README.md](../../tests/e2e/README.md)와 같이 맞춘다.
- residual review entrypoint가 바뀌면 [docs/work_tickets.md](../work_tickets.md), [README.md](../../README.md), [docs/handbook.md](../handbook.md), [tests/e2e/README.md](../../tests/e2e/README.md)와 같이 맞춘다.
- residual reading order가 바뀌면 [docs/work_tickets.md](../work_tickets.md), [README.md](../../README.md), [docs/handbook.md](../handbook.md), [tests/e2e/README.md](../../tests/e2e/README.md)와 같이 맞춘다.
- review mode entry shortcuts가 바뀌면 [README.md](../../README.md), [docs/handbook.md](../handbook.md), [tests/e2e/README.md](../../tests/e2e/README.md)와 같이 맞춘다.
