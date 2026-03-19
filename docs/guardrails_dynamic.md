# Dynamic GuardSpec 운영 가이드

Status: support
Audience: implementation
Source of truth for: GuardSpec subsystem behavior and policy interpretation
Not the source of truth for: project-level constraints, roadmap, current baseline
Last validated against: `common/guardrails/*`, generator/verifier/reviewer integration, and current workflow boundaries on 2026-03-19

이 문서는 GuardSpec subsystem만 설명합니다. 프로젝트 전체의 제약은 [docs/constraints.md](constraints.md), 구현 우선순위는 [docs/final_solution.md](final_solution.md), 작업 티켓 분해는 [docs/work_tickets.md](work_tickets.md)를 봅니다.
success criteria 5축과 backlog owner 대응은 [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Axis Map`을 봅니다.
completion companion set과 canonical reading order는 [docs/work_tickets.md](work_tickets.md)의 `Completion Companions`, `Open-World Completion Reading Order`를 봅니다.
success criteria 5축의 완료판정 질문과 최소 근거는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Checklist`를 봅니다.
success criteria 5축의 canonical 완료 검토 순서는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Review Flow`를 봅니다.
latest confirmed residual의 축별 ticket bundle 분해는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Residual Ticket Breakdown`을 봅니다.
representative validation harness와 direct rerun command family는 [tests/e2e/README.md](../tests/e2e/README.md)를 봅니다.

## 개요

- 목적: Researcher evidence를 바탕으로 bundle 단위 `guard_spec.json`을 만들고 Generator/Verifier/Reviewer가 공통 소비합니다.
- 스키마 버전: `guard_spec@1.0`
- 위치: `metadata/<sid>/bundles/<slug>/guard_spec.json` 또는 단일 번들의 `metadata/<sid>/guard_spec.json`

## 정책 (`policy.guard`)

- `failure_policy`: `closed_unknown|open_all|closed_all`
- `dynamic_scope`: `assertions_semantics|include_patterns|full`
- `call_budget.mode`: `bundle_once|per_candidate|verifier_only|bundle_ensemble`
- `call_budget.ensemble_runs`: ensemble run count
- `autofix.level`: `none|manifest|code`
- `autofix.max_attempts`: 최대 자동 보정 시도 횟수

정책 제약과 claim 한계는 [docs/constraints.md](constraints.md)의 researcher/generator/verifier constraints를 따릅니다.

## GuardSpec 필드

- `schema_version`, `sid`, `vuln_id`, `slug`, `source`
- `policy_snapshot`
- `evidence_refs[]`
- `semantic_signature`
- `generator_assertions[]`
- `verifier_assertions[]`
- `autofix_hints[]`
- `confidence`, `created_at`

## 적용 지점

- Researcher: evidence와 verification spec을 바탕으로 GuardSpec 생성
- Generator: candidate manifest를 guard assertions와 semantic constraints로 검증
- Verifier: rule 기반 검증 이후 verifier assertions와 workspace semantics를 추가 교차검증
- Reviewer: guard mismatch를 blocking signal로 해석

## Current Role Boundary

- GuardSpec은 researcher/generator/verifier/reviewer 사이의 공통 assertion surface를 정리하는 subsystem이다.
- 하지만 이것이 `selection_decision`, `runtime_graph`, `executor_plan` 같은 control-plane을 authoritative하게 만드는 것은 아니다.
- measured support workflow(`support_candidate.json`, `support_review_index.json`, `support_registry_update.json`, `curated_support_registry.json`)의 primary owner도 GuardSpec이 아니다.

## What GuardSpec Does Not Solve Yet

- family/stack/topology selection 자체를 authoritative control-plane으로 만들지는 않습니다.
- negative/metamorphic oracle를 실제 실행하는 verifier parity를 대신하지 않습니다.
- generalized open-world capability의 근거가 되지 않습니다.

## Current Residual Owners

- selection/runtime control-plane residual은 `TKT-001` ~ `TKT-005` owner다.
- broader browserful/stateful oracle replay residual은 `TKT-007-A/B` owner다.
- measured gate / support workflow policy residual은 `TKT-008-A*`, `TKT-009-A*` owner다.

이 한계는 [docs/constraints.md](constraints.md)에 canonical하게 적고, 이 문서에서는 subsystem behavior만 유지합니다.

## Residual Review Focus

- GuardSpec residual review는 “GuardSpec이 primary owner가 아닌 residual을 어디까지 설명하고 어디서 멈춰야 하는가”를 먼저 보는 용도다.
- 특히 selection/runtime control-plane과 measured/support policy residual은 GuardSpec 소비 경계까지만 확인하고, primary owner ticket로 다시 올라가서 본다.

## Completion Review Focus

- GuardSpec completion review는 GuardSpec이 richer oracle/assertion surface와 연결되더라도 selection/runtime control-plane primary owner처럼 읽히지 않는지부터 본다.
- measured/support completion review에서도 GuardSpec은 policy owner가 아니라 companion assertion surface로만 남는지부터 본다.

## Review Mode Entry

이 문서를 열 때는 아래 mode entry를 먼저 고른다.

- 검증:
  - 이 문서의 `Representative Validation Surface`
- 완료판정:
  - 이 문서의 `Completion Review Focus`
  - [docs/code/README.md](code/README.md)의 `Completion Review Entry`
- 잔여 구현 검토:
  - 이 문서의 `Residual Review Focus`
  - [docs/code/README.md](code/README.md)의 `Residual Review Entry`

## Ticket-First Entry

- GuardSpec generation/consumption 경로를 볼 때:
  - `common/guardrails/*`
  - `agents/researcher/service.py`
  - `agents/generator/service.py`
  - `evals/poc_verifier/rule_based.py`
  - `agents/reviewer/service.py`
- bundle artifact를 볼 때:
  - `metadata/<SID>/guard_spec.json`
  - `metadata/<SID>/bundles/<slug>/guard_spec.json`

## Representative Validation Surface

- guard spec / engine regression:
  - `tests/test_guard_engine.py`
  - `tests/test_guard_spec_schema.py`
  - `tests/test_guard_error_classification.py`
  - `tests/test_guard_loop_hint_propagation.py`
- downstream semantic sanity:
  - `tests/test_synthesis_semantic_guard.py`
  - `tests/test_rule_based_semantic_contract.py`

## How To Update This Document

- GuardSpec schema, policy field, integration point가 바뀔 때만 갱신한다.
- current rerun truth나 representative workflow result는 [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)에 남긴다.
- current non-claim과 subsystem boundary는 [docs/constraints.md](constraints.md)에 남긴다.
- owner와 sequencing은 [docs/final_solution.md](final_solution.md), [docs/work_tickets.md](work_tickets.md)로 보낸다.
- ticket-first entrypoint나 representative validation surface가 바뀌면 이 문서의 해당 섹션도 같이 갱신한다.
- completion review focus가 바뀌면 same subsystem boundary 기준으로 이 문서도 같이 갱신한다.
- residual review focus가 바뀌면 same subsystem boundary 기준으로 이 문서도 같이 갱신한다.
- review mode entry shortcut이 바뀌면 [docs/code/README.md](code/README.md)와 같이 갱신한다.
- GuardSpec 관련 rerun/harness path가 바뀌면 [tests/e2e/README.md](../tests/e2e/README.md)와 같이 갱신한다.
