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
- priority companion set과 canonical priority routing: [docs/work_tickets.md](../work_tickets.md)의 `Priority Companions`, `Priority Reading Order`
- success criteria 5축의 완료판정 질문과 최소 근거: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Completion Checklist`
- success criteria 5축의 canonical 완료 검토 순서: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Completion Review Flow`
- latest confirmed residual의 축별 ticket bundle 분해: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Residual Ticket Breakdown`
- latest direct verification까지 반영한 current completion priority order와 잔여 작업량/turn envelope: [docs/work_tickets.md](../work_tickets.md)의 `Confirmed Completion Priority Order`, `Estimated Turn Envelope`
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
- planning-only pair(`foobar-name-only-negative`, `open-redirect-strict-dynamic-no-remote`) blocked/no-op chain은 reviewer boundary를 확인하는 cheapest no-Docker workflow다. pipeline reviewer와 measured/manual support review가 서로 다른 surface로 남는지 보는 current `TKT-008-A1`, `TKT-009-A2` reading에 포함된다.
- positive LLM-shaped lane(`trusted-dynamic-sqli`)는 reviewer가 downstream quality/blocking surface를 읽는 representative positive lane 후보고, latest Docker-enabled rerun에서는 실제 review surface까지 다시 열렸다. 다만 current truth는 `authority_ready_bundle_count=1`이어도 `reviewable_bundle_count=0`인 blocked lane이므로, reviewer 문서에서도 strict live-LLM fail-closed honesty와 positive LLM-shaped review surface를 분리해서 읽는다.
- same positive pair의 ticket-form 해석은 [docs/work_tickets.md](../work_tickets.md)의 `Assessment-To-Ticket Interpretation`을 따른다. reviewer 관점에서는 `trusted-dynamic-sqli`가 `TKT-009-A1` accept-path blocker를, `open-redirect-dynamic-name-only`가 `TKT-008-A*` blocked promotion signal을 더 직접 보여 준다.
- latest positive pair support review aggregate도 `authority_ready_bundle_count=2`, `reviewable_bundle_count=0`이므로, reviewer 관점의 current closure는 still `runnable but not promotable`이다.
- same positive pair의 canonical rerun/support command chain은 [tests/e2e/README.md](../../tests/e2e/README.md)의 `Positive Pair Promotion Check`를 따른다.
- reviewer/support 경계 wording만 바뀐 경우 fastest pytest preflight는 `Focused No-Docker Regression Slice`다. reviewer 관점에서는 `tests/test_pack_promotion.py`, `tests/test_support_extract.py`, `tests/e2e/test_support_workflow.py`가 먼저 흔들린다.
- reviewer는 위 residual의 결과를 소비하는 downstream component이지 primary policy owner가 아니다.

## Residual Review Focus

- `TKT-007` residual은 reviewer가 어떤 oracle richness/result를 소비하는지 boundary 확인용으로만 보고, primary oracle policy owner와 혼동하지 않는지 본다.
- `TKT-008` / `TKT-009` residual은 pipeline reviewer와 measured/manual support review의 경계가 흐려지지 않는지부터 본다.
- cheapest boundary rehearsal은 planning-only pair의 `support_review -> support_decide -> support_apply`가 empty local registry로 끝나는지와, same pair의 pipeline `summary.json`은 여전히 `abstain/fail_closed`를 따로 유지하는지 같이 보는 것이다.

## Completion Review Focus

- `TKT-007` completion은 reviewer가 richer oracle realism을 소비하되, reviewer 자체를 primary oracle-policy owner로 과장하지 않는지부터 본다.
- `TKT-008`, `TKT-009` completion은 pipeline reviewer blocking surface와 measured/manual support review surface가 artifact와 vocabulary 상에서도 계속 분리되는지부터 본다.

## Priority Companions

이 문서를 우선순위 판단 관점으로 읽을 때는 아래 문서를 같이 본다.

- current completion priority order: [docs/work_tickets.md](../work_tickets.md)의 `Confirmed Completion Priority Order`
- 잔여 작업량과 practical turn envelope: [docs/work_tickets.md](../work_tickets.md)의 `Estimated Turn Envelope`
- representative evidence와 함께 보는 turn estimate shortcut: [docs/work_tickets.md](../work_tickets.md)의 `Turn Estimate Entry`
- priority companion set / reading order: [docs/work_tickets.md](../work_tickets.md)의 `Priority Companions`, `Priority Reading Order`
- latest positive representative pair의 ticket-form reading: [docs/work_tickets.md](../work_tickets.md)의 `Assessment-To-Ticket Interpretation`
- LLM-response 기준 residual/priority 해석: [docs/work_tickets.md](../work_tickets.md)의 `LLM-Response Capability Overlay`
- current truth / non-claim: [docs/current_state_gap_analysis.md](../current_state_gap_analysis.md), [docs/constraints.md](../constraints.md)
- code/harness entry: [docs/code/README.md](README.md), [tests/e2e/README.md](../../tests/e2e/README.md)

## Priority Review Focus

- current completion priority order에서 reviewer는 후행 `TKT-008`, `TKT-009` 경계 정합성을 보는 downstream companion이다.
- 즉 reviewer 문서는 무엇을 먼저 구현할지보다, later bucket이 pipeline review와 measured/manual review로 어디서 갈라지는지 확인하는 용도로 읽는다.
- LLM-response stricter reading에서도 strict stub pass가 곧 positive reviewable surface를 뜻하지 않는다는 점을 확인하는 downstream companion으로 남는다.
- latest positive representative pair의 ticket-form 해석도 [docs/work_tickets.md](../work_tickets.md)의 `Assessment-To-Ticket Interpretation`을 같이 따른다.
- 잔여 작업량/turn envelope 해석도 [docs/work_tickets.md](../work_tickets.md)의 `Estimated Turn Envelope`를 같이 따른다.
- turn estimate shortcut도 [docs/work_tickets.md](../work_tickets.md)의 `Turn Estimate Entry`를 같이 따른다.
- LLM-response 기준 상세 해석은 [docs/work_tickets.md](../work_tickets.md)의 `LLM-Response Capability Overlay`를 따른다.

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
- 우선순위 판단:
  - 이 문서의 `Priority Review Focus`
  - [docs/work_tickets.md](../work_tickets.md)의 `Priority Companions`
  - [docs/work_tickets.md](../work_tickets.md)의 `Assessment-To-Ticket Interpretation`

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
  - fastest no-Docker pytest preflight:
    - `tests/test_pack_promotion.py`
    - `tests/test_support_extract.py`
    - `tests/e2e/test_support_workflow.py`
  - latest blocked/no-op rehearsal pair:
    - `foobar-name-only-negative`
    - `open-redirect-strict-dynamic-no-remote`

## Representative Validation Surface

- reviewer blocking/boundary regression:
  - `tests/test_reviewer_blocking_policy.py`
  - `tests/test_run_pipeline_failure_resolution.py`
  - `tests/test_pack_promotion.py`
- representative workflow sanity:
  - pipeline direct rerun 후 `reviewer_reports.json`
  - measured/manual queue는 `tests/e2e/test_support_workflow.py`로 별도 확인
  - fastest project-level no-Docker preflight slice:
    - `tests/test_name_only_helpers.py`
    - `tests/test_pack_promotion.py`
    - `tests/test_repeatability_gate.py`
    - `tests/test_support_extract.py`
    - `tests/e2e/test_support_workflow.py`
    - `tests/e2e/test_case_matrix_rollup.py`
  - cheapest no-Docker boundary rehearsal:
    - `foobar-name-only-negative`
    - `open-redirect-strict-dynamic-no-remote`

## How To Update This Document

- reviewer entrypoint, review surface, blocking interpretation boundary가 바뀔 때만 갱신한다.
- current rerun truth나 measured/support workflow 결과는 [docs/current_state_gap_analysis.md](../current_state_gap_analysis.md)에 남긴다.
- current non-claim과 workflow boundary는 [docs/constraints.md](../constraints.md)에 남긴다.
- owner와 sequencing은 [docs/final_solution.md](../final_solution.md), [docs/work_tickets.md](../work_tickets.md)로 보낸다.
- ticket-first entrypoint나 representative validation surface가 바뀌면 이 문서의 해당 섹션도 같이 갱신한다.
- completion review focus가 바뀌면 same workflow boundary 기준으로 이 문서도 같이 갱신한다.
- residual review focus가 바뀌면 same workflow boundary 기준으로 이 문서도 같이 갱신한다.
- priority review focus나 priority companion 해석이 바뀌면 [docs/code/README.md](README.md), [docs/work_tickets.md](../work_tickets.md)와 같이 갱신한다.
- LLM-response stricter reading의 reviewer-side 해석이 바뀌면 [docs/work_tickets.md](../work_tickets.md)의 `LLM-Response Capability Overlay`와 같이 갱신한다.
- latest positive representative pair의 ticket-form 해석이 바뀌면 [docs/work_tickets.md](../work_tickets.md)의 `Assessment-To-Ticket Interpretation`와 같이 갱신한다.
- 잔여 작업량/turn envelope 해석이 바뀌면 [docs/work_tickets.md](../work_tickets.md)의 `Estimated Turn Envelope`와 같이 갱신한다.
- [docs/work_tickets.md](../work_tickets.md)의 `Turn Estimate Entry`가 바뀌면 same shortcut도 같이 갱신한다.
- review mode entry shortcut이 바뀌면 [docs/code/README.md](README.md)와 같이 갱신한다.
- reviewer와 measured/manual review의 harness boundary가 바뀌면 [tests/e2e/README.md](../../tests/e2e/README.md)와 같이 갱신한다.
