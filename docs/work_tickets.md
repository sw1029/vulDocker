# vulDocker 작업 티켓

Status: canonical
Audience: implementation
Source of truth for: actionable ticket decomposition, current backlog slicing, phase-to-ticket mapping
Not the source of truth for: rerun evidence, active constraints, operator quickstart
Last validated against: roadmap/current-state/constraints, workspace-local direct execution, and current regression baselines on 2026-04-02, with 2026-03-15 representative reruns retained as residual grounding

이 문서는 [docs/final_solution.md](final_solution.md)의 phase roadmap과
[docs/current_state_gap_analysis.md](current_state_gap_analysis.md)의 confirmed gap을
실행 가능한 작업 티켓으로 분해한 canonical backlog다.

관련 문서:
- 문제 정의와 success criteria: [docs/problem.md](problem.md)
- phase ordering과 acceptance gate: [docs/final_solution.md](final_solution.md)
- current rerun-backed truth: [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)
- current technical constraints: [docs/constraints.md](constraints.md)
- 운영/실행 절차: [docs/handbook.md](handbook.md)
- 코드 탐색 인덱스: [docs/code/README.md](code/README.md)
- representative validation harness: [tests/e2e/README.md](../tests/e2e/README.md)

## Reader Routing

- implementation owner, subtask decomposition, backlog priority, 잔여 작업량/turn envelope를 보려면 이 문서를 본다.
- current rerun truth나 latest direct verification 결과는 [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)를 본다.
- phase ordering과 acceptance gate는 [docs/final_solution.md](final_solution.md)를 본다.
- current non-claim과 operational constraint는 [docs/constraints.md](constraints.md)를 본다.
- operator quickstart와 artifact reading은 [docs/handbook.md](handbook.md)를 본다.
- subsystem code entrypoint는 [docs/code/README.md](code/README.md)를 본다.
- direct rerun command와 measured/support harness detail은 [tests/e2e/README.md](../tests/e2e/README.md)를 본다.

## Validation Companions

backlog/검증 관점에서 이 문서와 같이 봐야 할 companion은 아래와 같다.

- success criteria 5축과 backlog owner 대응: 이 문서의 `Open-World Completion Axis Map`
- phase acceptance와 validation surface 대응: [docs/final_solution.md](final_solution.md)
- concrete rerun/support harness command: [tests/e2e/README.md](../tests/e2e/README.md)
- code entrypoint와 subsystem owner: [docs/code/README.md](code/README.md)
- operator artifact map / troubleshooting: [docs/handbook.md](handbook.md)
- current truth와 observed rerun evidence: [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)

## Completion Companions

backlog/완료판정 관점에서 이 문서와 같이 봐야 할 companion은 아래와 같다.

- success criteria 5축과 completion bucket 대응: 이 문서의 `Open-World Completion Axis Map`
- completion close criteria와 minimum evidence: 이 문서의 `Open-World Completion Checklist`
- completion review / reading order: 이 문서의 `Open-World Completion Review Flow`, `Open-World Completion Reading Order`
- phase acceptance와 validation surface 대응: [docs/final_solution.md](final_solution.md)의 `Acceptance-To-Validation Translation`
- concrete rerun / support harness command: [tests/e2e/README.md](../tests/e2e/README.md)
- code entrypoint와 subsystem owner: [docs/code/README.md](code/README.md)
- operator artifact map / troubleshooting: [docs/handbook.md](handbook.md)
- current truth와 observed rerun evidence: [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)
- forbidden claim과 current limit: [docs/constraints.md](constraints.md)

## Residual Companions

backlog/residual 관점에서 이 문서와 같이 봐야 할 companion은 아래와 같다.

- success criteria 5축과 residual bucket 대응: 이 문서의 `Open-World Completion Axis Map`, `Open-World Residual Ticket Breakdown`
- residual close 기준과 최소 evidence: 이 문서의 `Open-World Completion Checklist`
- residual 구현 검토 순서와 문서 reading order: 이 문서의 `Open-World Residual Review Flow`, `Open-World Residual Reading Order`
- phase acceptance와 phase ordering 대응: [docs/final_solution.md](final_solution.md)
- concrete rerun/support harness command: [tests/e2e/README.md](../tests/e2e/README.md)
- code entrypoint와 subsystem residual focus: [docs/code/README.md](code/README.md)
- operator artifact map / troubleshooting: [docs/handbook.md](handbook.md)
- current truth와 observed rerun evidence: [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)
- forbidden claim과 current limit: [docs/constraints.md](constraints.md)

## Priority Companions

backlog/우선순위 판단 관점에서 이 문서와 같이 봐야 할 companion은 아래와 같다.

- current completion priority order와 해석 규칙: 이 문서의 `Confirmed Completion Priority Order`
- 잔여 작업량과 practical turn envelope: 이 문서의 `Estimated Turn Envelope`
- current remaining leverage bucket: 이 문서의 `Current Remaining Snapshot`
- queue-facing 정성/정량 shorthand: 이 문서의 `Current Capability Scorecard`
- 계획 구체성 보강이 필요한 residual: 이 문서의 `Planning Specificity Residual Overlay`
- phase ordering과 fixed sequencing guardrail: [docs/final_solution.md](final_solution.md), 이 문서의 `Sequencing Rule`
- current truth와 latest direct verification 근거: [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)
- forbidden claim과 operational/non-claim boundary: [docs/constraints.md](constraints.md)
- latest positive representative pair의 ticket-form reading: 이 문서의 `Assessment-To-Ticket Interpretation`
- LLM-response 기준 stricter capability 해석: 이 문서의 `LLM-Response Capability Overlay`
- concrete rerun/support harness command: [tests/e2e/README.md](../tests/e2e/README.md)
- code entrypoint와 subsystem owner: [docs/code/README.md](code/README.md)
- operator artifact map / troubleshooting: [docs/handbook.md](handbook.md)

## Turn Estimate Companions

backlog/작업량 추산 관점에서 이 문서와 같이 봐야 할 companion은 아래와 같다.

- turn estimate source와 practical envelope: 이 문서의 `Estimated Turn Envelope`
- visible blocker / structural root-cause 해석: 이 문서의 `Assessment-To-Ticket Interpretation`, `LLM-Response Capability Overlay`
- current remaining leverage bucket: 이 문서의 `Current Remaining Snapshot`, `Confirmed Completion Priority Order`
- queue-facing 정성/정량 shorthand: 이 문서의 `Current Capability Scorecard`
- 계획 구체성 보강이 필요한 residual: 이 문서의 `Planning Specificity Residual Overlay`
- current truth와 operational/non-claim boundary: [docs/current_state_gap_analysis.md](current_state_gap_analysis.md), [docs/constraints.md](constraints.md)
- representative rerun/support evidence: [tests/e2e/README.md](../tests/e2e/README.md)의 `Positive Pair Promotion Check`
- code/artifact/operator companion: [docs/code/README.md](code/README.md), [docs/handbook.md](handbook.md)

## Review Mode Matrix

문서를 어떤 목적에서 열고 있는지에 따라 canonical 시작점은 아래처럼 고른다.

| Review mode | Start here | First routing surface | Canonical reading order | Primary outcome |
| --- | --- | --- | --- | --- |
| 검증 | `Validation Companions` | `Validation Question Routing` | `Validation Reading Order` | representative rerun / measured-support harness와 code/artifact를 연결한다 |
| 완료판정 | `Completion Companions`, `Open-World Completion Axis Map` | `Validation Question Routing` | `Open-World Completion Reading Order` | success criteria 5축이 실제로 닫혔는지 판단한다 |
| 잔여 검토 | `Residual Companions`, `Open-World Residual Ticket Breakdown` | `Residual Question Routing` | `Open-World Residual Reading Order` | latest confirmed residual이 어느 ticket bundle에 남았는지와 다음 확인 경로를 정한다 |
| 작업량 추산 | `Turn Estimate Companions`, `Estimated Turn Envelope`, `Assessment-To-Ticket Interpretation` | `Priority Question Routing` | `Turn Estimate Reading Order` | representative evidence와 residual bucket을 기준으로 practical turn envelope를 읽는다 |
| 우선순위 판단 | `Priority Companions`, `Confirmed Completion Priority Order`, `Estimated Turn Envelope`, `Assessment-To-Ticket Interpretation` | `Priority Question Routing` | `Priority Reading Order` | current completion 기준으로 무엇을 먼저 구현할지와 왜 그런지를 판단하고, latest positive representative pair를 visible blocker vs structural root-cause로 나눠 읽으며 practical turn envelope까지 같이 본다 |

## Validation Question Routing

검증 관점에서 자주 묻는 질문은 아래처럼 문서를 나눠 본다.

- “성공 기준 5축 기준으로 지금 어떤 축이 비어 있나?”
  - 이 문서의 `Open-World Completion Axis Map`
- “이 축이 완료됐다고 무엇으로 판정하나?”
  - 이 문서의 `Open-World Completion Checklist`
- “완료판정을 어떤 순서로 검토하나?”
  - 이 문서의 `Open-World Completion Review Flow`
- “완료판정 문서를 어떤 순서로 열어야 하나?”
  - 이 문서의 `Open-World Completion Reading Order`
- “지금 확인된 open-world residual을 티켓 단위로 어떻게 쪼개나?”
  - 이 문서의 `Open-World Residual Ticket Breakdown`
- “잔여 구현을 어떤 순서로 검토하나?”
  - 이 문서의 `Open-World Residual Review Flow`
- “residual 문서를 어떤 순서로 열어야 하나?”
  - 이 문서의 `Open-World Residual Reading Order`
- “이 phase acceptance를 무엇으로 확인하나?”
  - [docs/final_solution.md](final_solution.md)의 `Acceptance-To-Validation Translation`
- “이 ticket를 먼저 어떤 하니스로 검증하나?”
  - 이 문서의 `Validation Routing`
- “검증 문서를 어떤 순서로 열어야 하나?”
  - 이 문서의 `Validation Reading Order`
- “실제 rerun / repeatability / support 명령은 무엇인가?”
  - [tests/e2e/README.md](../tests/e2e/README.md)
- “Docker 없이 가장 싸게 strict fail-closed / abstain 경계를 확인하려면 무엇을 먼저 보나?”
  - [tests/e2e/README.md](../tests/e2e/README.md)의 `Low-Cost No-Docker Validation Lanes`
  - `open-redirect-strict-dynamic-no-remote`
  - `open-redirect-strict-dynamic-stub`
  - `foobar-name-only-negative`
- “authority handoff와 measured/support gate split을 Docker 없이 가장 싸게 확인하려면 무엇을 먼저 보나?”
  - [tests/e2e/README.md](../tests/e2e/README.md)의 planning-only measured/support no-op pair
  - `foobar-name-only-negative`
  - `open-redirect-strict-dynamic-no-remote`
- “문서/정책/measured-support regression을 Docker 없이 가장 싸게 preflight하려면 무엇을 먼저 보나?”
  - [tests/e2e/README.md](../tests/e2e/README.md)의 `Focused No-Docker Regression Slice`
  - `tests/test_name_only_helpers.py`
  - `tests/test_pack_promotion.py`
  - `tests/test_repeatability_gate.py`
  - `tests/test_support_extract.py`
  - `tests/e2e/test_support_workflow.py`
  - `tests/e2e/test_case_matrix_rollup.py`
- “positive representative pair가 왜 runnable but not promotable인지 가장 직접적으로 확인하려면?”
  - [tests/e2e/README.md](../tests/e2e/README.md)의 `Positive Pair Promotion Check`
  - `trusted-dynamic-sqli`
  - `open-redirect-dynamic-name-only`
- “코드는 어디부터 읽어야 하나?”
  - [docs/code/README.md](code/README.md)
- “artifact는 어디서 읽고 어떻게 해석하나?”
  - [docs/handbook.md](handbook.md)
- “success criteria 5축별로 실제 artifact는 무엇을 먼저 보나?”
  - [docs/handbook.md](handbook.md)의 `Open-World Axis Reading Hints`
  - [docs/code/workspaces.md](code/workspaces.md)의 `Open-World Axis Artifact Hints`
- “왜 아직 success/support-ready/open-world claim이 아니라고 보나?”
  - [docs/constraints.md](constraints.md), [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)

## Residual Question Routing

residual 검토 관점에서 자주 묻는 질문은 아래처럼 문서를 나눠 본다.

- “이 residual이 어느 축에 속하나?”
  - 이 문서의 `Open-World Completion Axis Map`
  - 이 문서의 `Open-World Residual Ticket Breakdown`
- “이 residual이 닫혔다고 무엇으로 판정하나?”
  - 이 문서의 `Open-World Completion Checklist`
- “이 residual을 어떤 순서로 검토하나?”
  - 이 문서의 `Open-World Residual Review Flow`
- “이 residual이 어떤 phase acceptance와 연결되나?”
  - [docs/final_solution.md](final_solution.md)의 `Acceptance-To-Validation Translation`
- “이 residual을 먼저 어떤 하니스로 확인하나?”
  - 이 문서의 `Validation Routing`
  - [tests/e2e/README.md](../tests/e2e/README.md)
- “이 residual이 strict capability gate boundary인지, semantic abstain인지 빠르게 가르려면?”
  - [tests/e2e/README.md](../tests/e2e/README.md)의 `Low-Cost No-Docker Validation Lanes`
  - `open-redirect-strict-dynamic-no-remote`
  - `open-redirect-strict-dynamic-stub`
  - `foobar-name-only-negative`
- “이 residual이 blocked/no-op support policy인지 accept-path closure인지 빠르게 가르려면?”
  - [tests/e2e/README.md](../tests/e2e/README.md)의 planning-only measured/support no-op pair
  - `foobar-name-only-negative`
  - `open-redirect-strict-dynamic-no-remote`
- “이 residual이 wording/support-policy regression인지, 실제 direct rerun residual인지 먼저 가르려면?”
  - [tests/e2e/README.md](../tests/e2e/README.md)의 `Focused No-Docker Regression Slice`
  - `tests/test_name_only_helpers.py`
  - `tests/test_pack_promotion.py`
  - `tests/test_repeatability_gate.py`
  - `tests/test_support_extract.py`
  - `tests/e2e/test_support_workflow.py`
  - `tests/e2e/test_case_matrix_rollup.py`
- “이 residual의 코드는 어디부터 읽어야 하나?”
  - [docs/code/README.md](code/README.md)
  - subsystem docs의 `Ticket-First Entry` / `Residual Review Focus`
- “이 residual의 artifact는 어디서 읽나?”
  - [docs/handbook.md](handbook.md)의 `Open-World Axis Reading Hints`
  - [docs/code/workspaces.md](code/workspaces.md)의 `Open-World Axis Artifact Hints`
- “왜 아직 residual이 닫혔다고 말하면 안 되나?”
  - [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)
  - [docs/constraints.md](constraints.md)

## Priority Question Routing

우선순위 판단 관점에서 자주 묻는 질문은 아래처럼 문서를 나눠 본다.

- “지금 무엇을 먼저 구현해야 하나?”
  - 이 문서의 `Confirmed Completion Priority Order`
- “왜 이 ticket가 다음 bucket보다 앞서는가?”
  - 이 문서의 `Confirmed Completion Priority Order`
  - 이 문서의 `Current Remaining Snapshot`
- “지금 남은 작업량과 practical turn envelope를 어떻게 읽나?”
  - 이 문서의 `Estimated Turn Envelope`
  - 이 문서의 `Confirmed Completion Priority Order`
- “turn envelope를 latest representative evidence와 같이 어디서 읽나?”
  - 이 문서의 `Turn Estimate Entry`
  - [tests/e2e/README.md](../tests/e2e/README.md)의 `Positive Pair Promotion Check`
- “phase 순서와 현재 ticket 우선순위가 어떻게 대응되나?”
  - [docs/final_solution.md](final_solution.md)의 `Phase-To-Ticket Translation`
  - 이 문서의 `Sequencing Rule`
- “latest direct verification이 우선순위 해석을 어떻게 바꿨나?”
  - [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)
  - 이 문서의 `Direct Verification Slice`
- “latest positive Docker-enabled representative pair를 ticket 관점에서 어떻게 읽나?”
  - 이 문서의 `Assessment-To-Ticket Interpretation`
  - 이 문서의 `LLM-Response Capability Overlay`
- “latest positive representative pair가 왜 현재 priority를 바꾸지 않는가?”
  - 이 문서의 `Assessment-To-Ticket Interpretation`
  - [tests/e2e/README.md](../tests/e2e/README.md)의 `Positive Pair Promotion Check`
- “지금 priority가 높아 보여도 사실 stabilization lane인 ticket는 무엇인가?”
  - 이 문서의 `Confirmed Completion Priority Order`
  - 이 문서의 `Direct Verification Slice`
- “우선순위 판단 전에 가장 싼 no-Docker preflight는 무엇인가?”
  - [tests/e2e/README.md](../tests/e2e/README.md)의 `Focused No-Docker Regression Slice`
  - [tests/e2e/README.md](../tests/e2e/README.md)의 `Low-Cost No-Docker Validation Lanes`
- “이 우선순위를 코드 관점에서 어디부터 따라가나?”
  - [docs/code/README.md](code/README.md)
  - 이 문서의 `Implementation Entry Points And Validation Surface`
- “이 우선순위를 artifact/operator 관점에서 어떻게 읽나?”
  - [docs/handbook.md](handbook.md)
  - [docs/code/workspaces.md](code/workspaces.md)
- “LLM response로 실제 vulnerable Docker를 만든다는 기준에서 남은 본체는 무엇인가?”
  - 이 문서의 `LLM-Response Capability Overlay`
  - 이 문서의 `Confirmed Completion Priority Order`
  - [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)
  - [docs/constraints.md](constraints.md)

## Usage Rules

- 이 문서는 priority와 implementation slicing을 담당한다.
- representative rerun truth나 current non-claim은 여기서 다시 장황하게 반복하지 않고 관련 canonical 문서로 링크한다.
- priority는 effort가 아니라 completeness leverage 기준이다.
- ticket status는 `ready`, `blocked`, `deferred`만 쓴다.
- close 조건은 반드시 code change, regression, representative validation까지 같이 적는다.
- latest workspace-local regression stabilization은 phase ordering을 바꾸지 않는 한 기존 parent ticket의 subtask로 흡수한다.
- current truth와 backlog priority가 충돌해 보이면, truth는 `docs/current_state_gap_analysis.md`, priority/order는 `docs/final_solution.md`와 이 문서를 따른다.

## Priority Board

| ID | Priority | Phase | Status | Title |
| --- | --- | --- | --- | --- |
| TKT-001 | P0 | 2.5 -> 3 | ready | Primitive-First Branch Controller |
| TKT-002 | P1 | 3C | ready | Runtime Graph / Executor Plan Control-Plane Promotion |
| TKT-003 | P1 | 3C | ready | Generalized Dependency Ordering And Lifecycle |
| TKT-004 | P1 | 3C | ready | Generalized Seed / Init DSL |
| TKT-005 | P1 | 3C | ready | Generalized Env / Volume / Network Contract Semantics |
| TKT-006 | P2 | 2 / 2.5 | ready | Stage-Resumable Synthesis And One-Shot Reduction |
| TKT-007 | P3 | 4 | ready | Browserful / Multi-Step Stateful Oracle Replay |
| TKT-008 | P4 | 5B | ready | Authoritative Measurement Gate Closure |
| TKT-009 | P5 | 6B | ready | Curated Registry Write / Merge Closure |
| TKT-010 | P6 | 7 | deferred | Expansion After Runtime / Oracle Closure |

## Subtask Decomposition

아래 subtask는 active backlog를 더 잘게 쪼갠 것이다. 이미 닫힌 bounded hardening을 다시 여는 용도가 아니라,
현재 residual을 implementation-sized unit으로 정리하는 용도다.

| Subtask | Parent | Status | Focus |
| --- | --- | --- | --- |
| `TKT-001-A` | `TKT-001` | ready | primitive/dependency/topology/oracle IR를 actual builder input으로 승격 |
| `TKT-001-B` | `TKT-001` | ready | scenario-specific materializer branch split |
| `TKT-001-C` | `TKT-001` | ready | family를 selector가 아니라 projection label로 축소 |
| `TKT-001-D` | `TKT-001` | ready | selection_decision authoritative branch controller |
| `TKT-001-E` | `TKT-001` | ready | partial-lane decision state machine unification |
| `TKT-001-F` | `TKT-001` | ready | unresolved-to-abstain transition modeling |
| `TKT-001-G` | `TKT-001` | ready | evidence authority thresholding for scenario selection |
| `TKT-001-H` | `TKT-001` | ready | scenario selection algebra and abstain contract |
| `TKT-001-I` | `TKT-001` | ready | selection-to-materialization causal trace |
| `TKT-002-A` | `TKT-002` | ready | graph-first service/sidecar/env/network execution |
| `TKT-002-B` | `TKT-002` | ready | graph-first health/poc/runtime surface consumption |
| `TKT-002-C` | `TKT-002` | ready | runtime_graph authoritative executor consumption |
| `TKT-002-D` | `TKT-002` | ready | representative topology class ladder |
| `TKT-003-A` | `TKT-003` | ready | generalized startup ordering |
| `TKT-003-B` | `TKT-003` | ready | shutdown/cleanup ordering |
| `TKT-004-A` | `TKT-004` | ready | declarative seed/init step schema |
| `TKT-004-B` | `TKT-004` | ready | seed/init execution result surface |
| `TKT-005-A` | `TKT-005` | ready | env contract class generalization |
| `TKT-005-B` | `TKT-005` | ready | volume contract class generalization |
| `TKT-005-C` | `TKT-005` | ready | network lifecycle class generalization |
| `TKT-006-A` | `TKT-006` | ready | stage artifact persistence and resumable retry |
| `TKT-006-B` | `TKT-006` | ready | generation path control beyond repair-only use |
| `TKT-006-C` | `TKT-006` | ready | stage failure journaling and downgrade policy |
| `TKT-006-D` | `TKT-006` | ready | live LLM materialization contract and provenance |
| `TKT-006-E` | `TKT-006` | ready | build-ready file manifest contract and build taxonomy |
| `TKT-006-F` | `TKT-006` | ready | build-time Docker safety policy |
| `TKT-007-A` | `TKT-007` | ready | browserful/sessionful multi-step replay |
| `TKT-007-B` | `TKT-007` | ready | realism rubric integration |
| `TKT-007-C` | `TKT-007` | ready | realism rubric operationalization |
| `TKT-008-A` | `TKT-008` | ready | authoritative measured gate and CI comparison |
| `TKT-008-A1` | `TKT-008-A` | ready | measured-gate blocker policy split for mechanically healthy lanes |
| `TKT-008-A2` | `TKT-008-A` | ready | authoritative CI/measured gate consumption policy |
| `TKT-008-A3` | `TKT-008-A` | ready | generation-path axis and live-positive measurement |
| `TKT-008-B` | `TKT-008` | ready | planning-only and multi-bundle summary consistency residual |
| `TKT-008-B1` | `TKT-008-B` | ready | mixed multi-bundle top-level verdict/failure projection consistency |
| `TKT-008-B2` | `TKT-008-B` | ready | authoritative measured-gate handoff and top-level/nested precedence |
| `TKT-008-B3` | `TKT-008-B` | ready | repeatability surface contract stabilization |
| `TKT-008-B3-A` | `TKT-008-B3` | ready | repeat helper backward-compat arguments |
| `TKT-008-B3-B` | `TKT-008-B3` | ready | plan writer sid-salt compatibility seam |
| `TKT-008-B3-C` | `TKT-008-B3` | ready | repeatability report top-level case key parity |
| `TKT-009-A` | `TKT-009` | ready | registry write/merge workflow |
| `TKT-009-B` | `TKT-009` | ready | provenance/history persistence |
| `TKT-009-A1` | `TKT-009-A` | ready | representative reviewable accept-path direct workflow verification |
| `TKT-009-A1-A` | `TKT-009-A1` | ready | first reviewable LLM-shaped positive lane |
| `TKT-009-A1-B` | `TKT-009-A1` | ready | first reviewable dynamic name-only positive lane |
| `TKT-009-A1-C` | `TKT-009-A1` | ready | first reviewable live-LLM name-only positive lane |
| `TKT-009-A2` | `TKT-009-A` | ready | blocked/no-op path regression preservation |
| `TKT-009-B1` | `TKT-009-B` | ready | registry item provenance/status surface hardening |
| `TKT-009-B2` | `TKT-009-B` | ready | merge policy, history compaction, schema evolution |
| `TKT-009-B3` | `TKT-009-B` | ready | registry API / artifact schema-status parity |
| `TKT-009-B3-A` | `TKT-009-B3` | ready | legacy decision-only schema-status parity |
| `TKT-009-B3-B` | `TKT-009-B3` | ready | direct API vs written artifact parity |
| `TKT-010-A` | `TKT-010` | deferred | open-vocabulary family induction after runtime/oracle closure |
| `TKT-010-B` | `TKT-010` | deferred | stack/runtime-class expansion beyond Python narrow pool |
| `TKT-010-C` | `TKT-010` | deferred | expansion unlock contract |

## Direct Verification Slice

`2026-03-19` ~ `2026-04-02` workspace-local direct execution에서 확인한 latest residual을 work ticket으로 매핑하면 아래와 같다.

| Observed issue | Ticket | Why this ticket |
| --- | --- | --- |
| `summarize_repeat_attempt(...)` helper call shape drift | `TKT-008-B3-A` | repeat helper backward-compat와 report contract 안정화 |
| `_write_plan(..., sid_salt=...)` 도입 이후 older stub/test double breakage | `TKT-008-B3-B` | SID isolation은 유지하되 unit/mock seam 복구 |
| `repeatability_report.json` top-level `case` vs `case_name` drift | `TKT-008-B3-C` | operator-facing measured artifact key parity 복구 |
| legacy decision-only registry에서 nested `last_update.schema_status` drift | `TKT-009-B3-A` | legacy decision normalization truth를 top-level/nested에서 동일하게 유지 |
| `build_curated_support_registry(...)` direct return vs final written artifact drift | `TKT-009-B3-B` | API path와 CLI/file path가 같은 support-registry truth를 보이게 정렬 |
| focused no-Docker regression slice(`tests/test_name_only_helpers.py`, `tests/test_pack_promotion.py`, `tests/test_repeatability_gate.py`, `tests/test_support_extract.py`, `tests/e2e/test_support_workflow.py`, `tests/e2e/test_case_matrix_rollup.py`)가 `160 passed`로 green | `TKT-001-E`, `TKT-008-A1`, `TKT-009-A2` | latest low-cost policy/honesty/measured-support regression net가 여전히 살아 있다는 뜻이며 새 product backlog보다는 existing residual regression protection에 가깝다 |
| planning-only repeatability lanes가 둘 다 `measured_gate.ready=false`와 `cache_reuse_inconsistent`, `artifact_quality_band_not_high`, `oracle_execution_parity_not_high` blocker를 남김 | `TKT-008-A1`, `TKT-008-A2` | repeatability CLI는 정상인데 measured promotion gate가 의도대로 닫혀 있는 상태를 authoritative policy 관점에서 계속 정리해야 함 |
| planning-only pair review index가 `authority_ready_bundle_count=2`이지만 same run은 `measured_gate_blocked_bundle_count=2`, `reviewable_bundle_count=0`, `by_support_status={blocked_mixed:2}`로 끝남 | `TKT-008-A1`, `TKT-009-A2` | authority handoff와 measured/promotion gate split을 계속 분리해서 읽어야 하며, current blocked/no-op path는 여전히 정상이지만 accept-path closure는 아님 |
| blocked support workflow recheck가 `by_support_status={blocked_mixed:2}`, `by_case_status={all_blocked:2}`, final `registry_item_count=0` no-op로 끝남 | `TKT-009-A2` | blocked/no-op path가 false promotion 없이 유지되는 current safety behavior를 regression으로 계속 고정해야 함 |
| fixture-backed positive LLM-shaped lane(`trusted-dynamic-sqli`)가 Docker-enabled rerun에서 expectation을 통과했지만 `provider_health_state=llm_fixture`, `generation_origin=llm_manifest`, `artifact_quality.qualitative_tier=thin_or_incomplete`, `measured_gate.ready=false`로 남음 | `TKT-006-A/B/C`, `TKT-008-A1/A2`, `TKT-009-A1` | positive materialization은 다시 열렸지만 fixture-backed synthesis quality와 measured/support accept-path closure는 여전히 residual이다 |
| representative dynamic lane(`open-redirect-dynamic-name-only`)가 Docker-enabled rerun에서 expectation을 통과했지만 `provider_health_state=llm_degraded`, `generation_origin=deterministic_fallback`, `name_only_outcome.decision=partial`, `artifact_quality.qualitative_tier=thin_fallback_demo`, `measured_gate.ready=false`로 남음 | `TKT-001`, `TKT-006-A/B/C`, `TKT-008-A1/A2` | runtime/oracle path는 다시 열렸지만 selection authority와 quality/promotion closure는 아직 current residual이다 |
| fresh positive pair support review가 `support_candidate_file_count=2`, `authority_ready_bundle_count=2`여도 `measured_gate_blocked_bundle_count=2`, `reviewable_bundle_count=0`, `by_support_status={blocked_mixed:2}`로 남음 | `TKT-008-A1/A2`, `TKT-009-A1` | representative positive lane도 current support workflow에서는 still “runnable but not promotable”이며, measured gate와 accept-path closure가 계속 본체 residual이다 |
| latest slice에서는 support workflow/docker-positive baseline wrapper의 helper/default resolution contract도 `lib_operator_pair_runtime_baseline_defaults.sh`와 [tests/test_ops_ci_operator_pair_runtime_baseline_defaults.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_pair_runtime_baseline_defaults.py) 로 direct regression까지 닫혔다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | pair baseline helper/default resolution도 wrapper별 inline bash가 아니라 bounded helper/operator contract로 읽는다 |
| latest slice에서는 same pair/matrix/current defaults library가 공유하는 helper-default single/batch resolution primitive도 `lib_operator_helper_defaults.sh`와 [tests/test_ops_ci_operator_helper_defaults.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_helper_defaults.py) 로 direct regression까지 닫혔다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | defaults library 내부 `${!VAR:-${script_dir}/...}` 패턴도 ad-hoc inline bash가 아니라 bounded helper/operator primitive로 읽는다 |
| latest slice에서는 measured/no-docker baseline wrapper의 matrix helper/default resolution contract도 `lib_operator_matrix_baseline_defaults.sh`와 [tests/test_ops_ci_operator_matrix_baseline_defaults.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_matrix_baseline_defaults.py) 로 direct regression까지 닫혔다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | matrix baseline helper/default resolution도 wrapper별 inline bash가 아니라 bounded helper/operator contract로 읽는다 |
| latest slice에서는 current baseline의 helper/default resolution contract도 `lib_operator_current_baseline_defaults.sh`와 [tests/test_ops_ci_operator_current_baseline_defaults.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_current_baseline_defaults.py) 로 direct regression까지 닫혔다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | current baseline helper/default resolution도 wrapper별 inline bash가 아니라 bounded helper/operator contract로 읽는다 |
| latest slice에서는 runtime/current/matrix baseline family가 공유하는 sequence-helper executable gate와 invoke primitive도 `lib_operator_sequence_helper_contract.sh`와 [tests/test_ops_ci_operator_sequence_helper_contract.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_sequence_helper_contract.py) 로 direct regression까지 닫혔다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | sequence helper validation과 helper invocation도 wrapper별 inline bash가 아니라 bounded helper/operator contract로 읽는다 |
| latest slice에서는 named-preset runner와 matrix baseline sequence family가 공유하는 export-helper function gate와 invoke primitive도 `lib_operator_export_helper_contract.sh`와 [tests/test_ops_ci_operator_export_helper_contract.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_export_helper_contract.py) 로 direct regression까지 닫혔다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | export helper function validation과 helper invocation도 wrapper별 inline bash가 아니라 bounded helper/operator contract로 읽는다 |
| latest slice에서는 direct/support named-preset thin wrapper가 공유하는 pair-runner primitive도 `lib_operator_pair_named_preset.sh`와 [tests/test_ops_ci_operator_pair_named_preset.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_pair_named_preset.py) 로 direct regression까지 닫혔다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | direct/support thin wrapper도 wrapper별 inline bash가 아니라 bounded helper/operator pair-runner contract로 읽는다 |
| latest slice에서는 direct/support named-preset wrapper가 공유하는 helper/default resolution도 `lib_operator_pair_named_preset_defaults.sh`와 [tests/test_ops_ci_operator_pair_named_preset_defaults.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_pair_named_preset_defaults.py) 로 direct regression까지 닫혔다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | direct/support wrapper entry의 named/preset/leaf helper default resolution도 wrapper별 inline bash가 아니라 bounded helper/operator defaults contract로 읽는다 |
| latest slice에서는 direct/support wrapper family가 공유하는 pair case-check skeleton도 `lib_operator_pair_case_check.sh`와 [tests/test_ops_ci_operator_pair_case_check.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_pair_case_check.py) 로 direct regression까지 닫혔다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | direct/support pair wrapper entry도 repeated inline bash가 아니라 bounded helper/operator pair skeleton으로 읽는다 |
| latest slice에서는 positive direct / low-cost direct wrapper가 공유하는 direct case-check skeleton도 `lib_operator_direct_case_check.sh`와 [tests/test_ops_ci_operator_direct_case_check.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_direct_case_check.py) 로 direct regression까지 닫혔다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | direct wrapper entry도 repeated inline bash가 아니라 bounded helper/operator direct case skeleton으로 읽는다 |
| latest slice에서는 positive pair / blocked-noop support wrapper가 공유하는 named-preset pair-check skeleton도 `lib_operator_support_pair_check.sh`와 [tests/test_ops_ci_operator_support_pair_check.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_support_pair_check.py) 로 direct regression까지 닫혔다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | support pair wrapper entry도 repeated inline bash가 아니라 bounded helper/operator pair skeleton으로 읽는다 |
| latest slice에서는 direct/repeatability/support workflow helper family가 공유하는 cases/output-root default resolution도 `lib_cases_output_roots.sh`와 [tests/test_ops_ci_cases_output_roots.py](/home/ysw/vulDocker/tests/test_ops_ci_cases_output_roots.py) 로 direct regression까지 닫혔다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | helper chain entry의 cases/output-root default resolution도 ad-hoc inline bash가 아니라 bounded helper/operator defaults contract로 읽는다 |
| latest slice에서는 direct/repeatability helper family가 공유하는 default `expectations.json` auto-discovery와 `--expectations` argv append도 `lib_case_expectations.sh`와 [tests/test_ops_ci_case_expectations.py](/home/ysw/vulDocker/tests/test_ops_ci_case_expectations.py) 로 direct regression까지 닫혔다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | helper chain entry의 expectations auto-discovery도 per-script inline file check가 아니라 bounded helper/operator contract로 읽는다 |
| same helper family에서는 direct/repeatability helper가 공유하는 `run_case.py` / `repeat_case.py` argv assembly, expectations append, `--no-snapshot` surface도 `lib_case_command_surface.sh`와 [tests/test_ops_ci_case_command_surface.py](/home/ysw/vulDocker/tests/test_ops_ci_case_command_surface.py) 로 direct regression까지 닫혔다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | helper chain entry의 case command assembly도 per-script inline argv construction이 아니라 bounded helper/operator contract로 읽는다 |
| same helper family에서는 direct/repeatability helper가 공유하는 usage check, output-root prep, entry preflight surface도 `lib_case_chain_entry.sh`와 [tests/test_ops_ci_case_chain_entry.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_entry.py) 로 direct regression까지 닫혔다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | helper chain entry의 usage/output-root prep도 per-script inline bash가 아니라 bounded helper/operator primitive로 읽는다 |
| same helper family에서는 direct/repeatability helper가 공유하는 case-output log, run-dirs file write, completion note surface도 `lib_case_chain_output_notes.sh`와 [tests/test_ops_ci_case_chain_output_notes.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_output_notes.py) 로 direct regression까지 닫혔다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | helper chain entry의 output-note/run-dirs surface도 per-script inline echo/printf가 아니라 bounded helper/operator primitive로 읽는다 |
| same helper family에서는 direct/repeatability helper가 공유하는 `case=alias` split, case-dir path resolution, alias/path safety validation뿐 아니라 case-context capture, resolved output-name/safe-slug helper, named output-context export surface도 `lib_case_spec_resolution.sh`와 [tests/test_ops_ci_case_spec_resolution.py](/home/ysw/vulDocker/tests/test_ops_ci_case_spec_resolution.py) 로 direct regression까지 닫혔다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | helper chain entry의 case-spec parsing도 inline bash split/path check가 아니라 bounded helper/operator context/output contract로 읽는다 |
| same helper family에서는 direct/repeatability helper가 공유하는 repeatability report Docker failure classification, retry gate input, permission-marker writer surface도 `lib_repeatability_report_failures.sh`와 [tests/test_ops_ci_repeatability_report_failures.py](/home/ysw/vulDocker/tests/test_ops_ci_repeatability_report_failures.py) 로 direct regression까지 닫혔다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | repeatability chain의 Docker failure parsing/retry-marker surface도 inline grep/printf block이 아니라 bounded helper/operator contract로 읽는다 |
| same helper family에서는 direct/repeatability helper가 공유하는 repeatability case-failure action resolution, retry/continue/fail routing, permission-marker-aware continue surface도 `lib_repeatability_case_failure.sh`와 [tests/test_ops_ci_repeatability_case_failure.py](/home/ysw/vulDocker/tests/test_ops_ci_repeatability_case_failure.py) 로 direct regression까지 닫혔다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | repeatability chain의 nonzero result branching도 inline bash branch block이 아니라 bounded helper/operator contract로 읽는다 |
| same helper family에서는 direct/repeatability helper가 공유하는 repeatability case context hydration, report-path resolution, run-dir append, `repeat_case.py` argv assembly surface도 `lib_repeatability_case_runtime.sh`와 [tests/test_ops_ci_repeatability_case_runtime.py](/home/ysw/vulDocker/tests/test_ops_ci_repeatability_case_runtime.py) 로 direct regression까지 닫혔다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | repeatability chain의 per-case setup도 inline bash context/argv block이 아니라 bounded helper/operator contract로 읽는다 |
| same helper family에서는 direct/repeatability helper가 공유하는 direct case context hydration, output-dir resolution, `run_case.py` argv assembly surface도 `lib_direct_case_runtime.sh`와 [tests/test_ops_ci_direct_case_runtime.py](/home/ysw/vulDocker/tests/test_ops_ci_direct_case_runtime.py) 로 direct regression까지 닫혔다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | direct chain의 per-case setup도 inline bash context/argv block이 아니라 bounded helper/operator contract로 읽는다 |
| same helper family에서는 direct/repeatability helper가 공유하는 direct case runtime reuse, output note emission, `run_case.py` command invoke surface도 `lib_direct_case_runner.sh`와 [tests/test_ops_ci_direct_case_runner.py](/home/ysw/vulDocker/tests/test_ops_ci_direct_case_runner.py) 로 direct regression까지 닫혔다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | direct chain의 emit/invoke block도 inline bash가 아니라 bounded helper/operator contract로 읽는다 |
| same helper family에서는 direct/repeatability chain wrapper family가 공유하는 `cases/output-root resolve + usage/output-root prep` surface도 `lib_case_chain_paths.sh`와 [tests/test_ops_ci_case_chain_paths.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_paths.py) 로 direct regression까지 닫혔다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | direct/repeatability top-level chain wrapper도 duplicated resolve/preflight block이 아니라 bounded helper/operator primitive로 읽는다 |
| latest slice에서는 same direct/repeatability profile wrapper family의 shared `profile target forward` surface도 `lib_case_chain_profile_target_forward.sh`, [tests/test_ops_ci_case_chain_profile_target_forward.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_profile_target_forward.py), `lib_case_chain_profile_entrypoint.sh`, [tests/test_ops_ci_case_chain_profile_entrypoint.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_profile_entrypoint.py), `lib_case_chain_main.sh`, [tests/test_ops_ci_case_chain_main.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_main.py), `lib_case_chain_main_script.sh`, [tests/test_ops_ci_case_chain_main_script.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_main_script.py), `run_direct_validation_chain.sh`, [tests/test_ops_ci_direct_validation_chain.py](/home/ysw/vulDocker/tests/test_ops_ci_direct_validation_chain.py), `run_repeatability_chain.sh`, [tests/test_ops_ci_repeatability_chain.py](/home/ysw/vulDocker/tests/test_ops_ci_repeatability_chain.py) 로 direct regression까지 닫혔다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | direct/repeatability profile wrapper도 duplicated profile/script-dir target-forward block이 아니라 bounded helper/operator primitive로 읽는다 |
| same support/matrix helper family에서는 repeat-helper invoke, env export, run-dir postprocess skeleton도 `lib_repeatability_chain_runner.sh`와 [tests/test_ops_ci_repeatability_chain_runner.py](/home/ysw/vulDocker/tests/test_ops_ci_repeatability_chain_runner.py) 로 direct regression까지 닫혔다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | support/matrix helper entry도 preflight/export/postprocess inline bash가 아니라 bounded repeatability runner contract로 읽는다 |
| same support review helper family에서는 prefix-aware output-name default resolution과 resolved output-path materialization도 `lib_support_review_output_surface.sh`, [tests/test_ops_ci_support_review_output_surface.py](/home/ysw/vulDocker/tests/test_ops_ci_support_review_output_surface.py), [tests/test_ops_ci_support_workflow_chain.py](/home/ysw/vulDocker/tests/test_ops_ci_support_workflow_chain.py) 로 direct regression까지 닫혔다. `run_support_review_chain.sh`, `run_reviewable_support_accept_check.sh`, `run_support_workflow_chain.sh`가 same resolved output-surface contract를 재사용하고, generic `VULD_SUPPORT_REVIEW_RESOLVED_*`뿐 아니라 `${PREFIX}_RESOLVED_*` output surface도 같이 export한다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | support review caller/output entry도 default/output-path inline bash가 아니라 bounded output-surface contract로 읽는다 |
| latest slice에서는 direct/support pair wrapper family가 공유하는 cases/output-root default resolution도 `lib_operator_cases_output_roots.sh`와 [tests/test_ops_ci_operator_cases_output_roots.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_cases_output_roots.py) 로 direct regression까지 닫혔다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | pair wrapper entry의 cases/output-root default resolution도 wrapper별 inline bash가 아니라 bounded helper/operator defaults contract로 읽는다 |
| latest slice에서는 direct/support wrapper family가 공유하는 single/pair/triple/batch case-slug default resolution도 `lib_operator_case_defaults.sh`와 [tests/test_ops_ci_operator_case_defaults.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_case_defaults.py) 로 direct regression까지 닫혔다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | direct/support wrapper entry의 case-slug default resolution도 wrapper별 inline bash가 아니라 bounded helper/operator defaults contract로 읽는다 |
| latest slice에서는 same direct/support wrapper family가 공유하는 completion/output note primitive도 `lib_operator_output_notes.sh`와 [tests/test_ops_ci_operator_output_notes.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_output_notes.py) 로 direct regression까지 닫혔다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | wrapper completion logging과 output-path note surface도 repeated inline echo block이 아니라 bounded helper/operator primitive로 읽는다 |
| latest slice에서는 same direct/support wrapper family가 공유하는 `output_root + child suffix -> completion note` primitive도 `lib_operator_output_root_notes.sh`와 [tests/test_ops_ci_operator_output_root_notes.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_output_root_notes.py) 로 direct regression까지 닫혔다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | wrapper output-root child path note surface도 wrapper별 inline path concatenation이 아니라 bounded helper/operator primitive로 읽는다 |
| latest slice에서는 support review helper family가 공유하는 prefix-aware single/batch output-name default resolution도 `lib_support_review_output_defaults.sh`와 [tests/test_ops_ci_support_review_output_defaults.py](/home/ysw/vulDocker/tests/test_ops_ci_support_review_output_defaults.py) 로 direct regression까지 닫혔다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | support review output-name defaults도 wrapper별 inline string default가 아니라 bounded helper/operator defaults primitive로 읽는다 |
| latest slice에서는 support review helper family가 공유하는 single/batch output-path resolution도 `lib_support_review_outputs.sh`와 [tests/test_ops_ci_support_review_outputs.py](/home/ysw/vulDocker/tests/test_ops_ci_support_review_outputs.py) 로 direct regression까지 닫혔다. workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | support review output path resolution도 fixed four-output inline export가 아니라 bounded helper/operator primitive로 읽는다 |
| latest slice에서는 support review helper family가 공유하는 resolved completion/output note contract도 `lib_support_review_output_notes.sh`와 [tests/test_ops_ci_support_review_output_notes.py](/home/ysw/vulDocker/tests/test_ops_ci_support_review_output_notes.py) 로 direct regression까지 닫혔다. `support_review_emit_prefixed_review_only_completion(...)`, `support_review_emit_prefixed_standard_completion(...)`, `support_review_emit_prefixed_reviewable_accept_completion(...)`와 backward-compatible `support_review_emit_resolved_*` wrappers를 통해 same family가 same resolved completion surface를 재사용하고, workspace-local `tests/test_ops_ci_*.py` bundle은 `343 passed`로 다시 확인됐다 | `TKT-008-B3`, companion-only | support review completion/output surface도 wrapper별 inline echo block이 아니라 bounded helper/operator primitive로 읽는다 |
| current workspace-local sandbox helper output이 `support_candidate_file_count=2`, `authority_ready_bundle_count=0`, `measured_gate_blocked_bundle_count=0`, `reviewable_bundle_count=0`, `by_support_status={}` empty aggregate로 끝날 수도 다시 확인됨. same helper의 per-case `repeatability_report.json`도 `passed=false`, blocker `case_failed`를 남겼고, `permission_artifact_summary.json`는 `runtime_equivalent_helper_truth_available=false`, `recommended_action=unrestricted_docker_rerun`를 남겼다. same latest direct reverify에서는 `docker ps` / `docker ps -a`가 empty list로 정상 응답하고 representative direct rerun도 다시 성공했으므로, same split은 host Docker precondition 부재가 아니라 permission-artifact environment output distinction으로 읽는 편이 맞다. same positive pair의 manual `repeat_case.py -> support_review.py` chain은 여전히 `blocked_mixed` aggregate를 재현함 | `TKT-008-B3`, companion-only | helper contract green이나 sandbox helper output을 runtime-equivalent truth로 읽지 않게 하는 bounded environment distinction이며, 새 core residual이 아니라 companion/operator stabilization residual이다 |
| latest slice에서 `run_support_workflow_chain.sh` / `run_positive_pair_promotion_check.sh`가 blocked lane의 `repeat_case.py` nonzero-with-report를 허용하고 `run_repeatability_chain.sh`에 transient docker readiness retry seam(`VULD_REPEAT_CHAIN_DOCKER_RETRY_COUNT`, `VULD_REPEAT_CHAIN_DOCKER_RETRY_DELAY_SEC`)까지 추가됐다. same helper는 `docker daemon permission denied`를 retry 대상이 아닌 permission artifact marker/note로 분리해 surface하고, unrestricted Docker-enabled direct rerun에서는 helper projection도 다시 `blocked_mixed` aggregate current truth와 정렬된다 | `TKT-008-B3`, companion-only | helper/operator stabilization은 많이 진전됐지만 sandbox helper artifact와 runtime-equivalent helper truth는 계속 분리해서 읽어야 한다. same bounded environment distinction만 companion residual로 유지한다 |

latest rerun slice는 위 항목을 재확인했을 뿐, 새 product backlog ticket을 추가로 만들지는 않았다. current residual owner는 그대로 `TKT-001`, `TKT-006`, `TKT-008-A*`, `TKT-009-A*`를 유지한다.

같은 날짜 direct recheck에서도 `strict no-remote`, `strict stub`, `unsupported negative`, planning-only repeatability/support blocked-no-op chain의 결과는 변하지 않았다. later same-day Docker-enabled rerun과 그 뒤의 fresh positive pair support review에서도 positive dynamic/LLM-shaped lane는 여전히 measured/support gate 기준으로 blocked였다. `2026-03-20` fresh rerun에서도 strict stub / positive pair / positive-pair support review verdict는 다시 바뀌지 않았고 host Docker precondition은 충족됐다. 따라서 current action item은 새 ticket 추가보다 existing `TKT-001-E`, `TKT-006`, `TKT-008-A1/A2`, `TKT-009-A1/A2` residual을 더 정확히 읽고 representative positive lane을 recurring regression set에 포함시키는 쪽이 맞다.

## Residual Coverage Map

`docs/current_state_gap_analysis.md`의 confirmed residual section을 active ticket과 연결하면 아래와 같다.

| Current-state section | Primary ticket(s) | Notes |
| --- | --- | --- |
| `6.1 request_ir is still too resolved` | `TKT-001-D`, `TKT-001-A` | resolved request surface를 authoritative branch input으로 낮추고 primitive IR를 actual builder input으로 승격 |
| `6.2 planning focus와 outcome step이 아직 이중화돼 있다` | `TKT-001-E`, `TKT-001-F` | partial-lane state machine과 unresolved-to-abstain transition을 하나의 규칙으로 정리 |
| `6.3 family discovery is still closed-vocabulary` | `TKT-010-A`, `TKT-001-C` | near-term에는 family selector를 projection label로 축소하고, open-vocabulary induction은 expansion phase에서 추적 |
| `6.4 evidence graph는 아직 causal authority graph는 아니다` | `TKT-001-G` | scenario selection용 evidence authority threshold와 contradiction policy를 명시 |
| `6.5 stack selection은 개선됐지만 아직 narrow하다` | `TKT-010-B` | stack/runtime-class 확장은 runtime/oracle closure 이후 deferred |
| `6.6 executor plan은 생겼지만 parity는 아직 얕다` | `TKT-002-C`, `TKT-004-A`, `TKT-004-B`, `TKT-005-A`, `TKT-005-B`, `TKT-005-C` | executor plan, seed/init, env-volume-network semantics를 control-plane으로 승격 |
| `6.7 one-shot synthesis is still the main bottleneck` | `TKT-006-A`, `TKT-006-B`, `TKT-006-C` | stage persistence, repair-first flow, downgrade journaling로 분해 |
| `6.8 runtime_graph is not yet the executor control plane` | `TKT-002-A`, `TKT-002-B`, `TKT-002-C`, `TKT-003-A`, `TKT-003-B` | graph-first execution과 lifecycle ordering parity를 함께 추적 |
| `6.9 verifier independence / artifact realism is still limited` | `TKT-007-A`, `TKT-007-B` | browserful/stateful replay와 realism rubric integration |
| `6.10 performance reuse는 생겼지만 measurement closure는 아직 partial이다` | `TKT-008-A1`, `TKT-008-A2` | perf reuse를 authoritative measured gate/CI policy로 승격 |
| `6.11 support promotion loop is still missing` | `TKT-009-A1`, `TKT-009-B1`, `TKT-009-B2` | actual reviewable accept-path verification과 long-lived registry merge policy로 분해 |
| `6.12 open-world eval matrix는 harness-scoped measurement에 머문다` | `TKT-008-A1`, `TKT-008-A2` | measured gate preview를 authoritative regression gate로 닫는 축 |
| `6.12b summary surface consistency still has residual scope` | `TKT-008-B1`, `TKT-008-B2` | mixed multi-bundle projection consistency와 authoritative handoff residual |
| `6.12c latest workspace-local repeatability / support stabilization closure` | `TKT-008-B3-A`, `TKT-008-B3-B`, `TKT-008-B3-C`, `TKT-009-B3-A`, `TKT-009-B3-B` | latest verified drift는 close됐고 same parent ticket의 bounded closure로 흡수 |
| `6.13 primitive-level runtime design control plane이 아직 없다` | `TKT-001-A`, `TKT-001-D`, `TKT-002-C`, `TKT-003-A`, `TKT-004-A`, `TKT-005-A` | primitive-first controller 부재가 runtime/runtime-graph/env/seed residual과 직접 연결 |

## Current Remaining Snapshot

latest direct verification까지 반영한 현재 잔여 구현의 묶음은 아래와 같다.

| Bucket | Primary ticket(s) | Why this is the next real leverage |
| --- | --- | --- |
| control-plane closure | `TKT-001` | family-first/bounded builder 의존을 줄이고 primitive-first branch controller로 넘어가야 나머지 phase가 실제로 열린다 |
| generalized runtime closure | `TKT-002`, `TKT-003`, `TKT-004`, `TKT-005` | `runtime_graph` / `executor_plan` / dependency / seed / env-volume-network semantics를 authoritative runtime input으로 만들어야 한다 |
| synthesis resilience | `TKT-006` | one-shot manifest 의존을 줄이고 stage-aware recovery를 실제 generation path에 올려야 한다 |
| stateful oracle realism | `TKT-007` | browserful/multi-step oracle가 아직 대표 residual로 남아 있다 |
| authoritative measured gate | `TKT-008-A1`, `TKT-008-A2` | current preview/measured gate를 CI/policy gate로 닫아야 support workflow가 capability truth와 분리된다 |
| actual reviewable accept path | `TKT-009-A1` | synthetic reviewable path를 넘는 representative measured accept-path direct verification이 아직 없다 |
| long-lived registry hardening | `TKT-009-B1`, `TKT-009-B2` | provenance/history/merge lifecycle은 local workflow가 생긴 뒤의 다음 잔여다 |
| expansion | `TKT-010` | 지금은 defer 유지가 맞다. above closure 이전에 올리면 안 된다 |

latest direct verification에서 green으로 다시 확인된 low-cost regression net(`TKT-001-E`, `TKT-008-A1`, `TKT-009-A2`)은 중요하지만, 현재 completion 기준 본체는 아니다. 이 slice는 현재 honesty / blocked-no-op / measured-support wording drift를 막는 stabilization lane으로 읽고, open-world capability 본체 우선순위는 아래 순서를 따른다.

## Current Capability Scorecard

latest direct verification을 current queue 판단용 shorthand로 다시 압축하면 아래처럼 읽는 편이 맞다.

| Capability slice | Queue-facing score | Primary evidence shorthand | Primary ticket(s) | Queue interpretation |
| --- | --- | --- | --- | --- |
| bounded regression / honesty floor | `80 / 100` | `python -m pytest -q tests -> 1175 passed, 53 skipped`, `python -m pytest -q tests/test_ops_ci_*.py -> 343 passed`, focused no-Docker slice `160 passed`, strict/negative direct rerun이 `fail_closed/fail_closed/abstain`으로 유지 | `TKT-001-E`, `TKT-008-A1`, `TKT-009-A2`, companion `TKT-008-B3` | current floor는 강하다. 그러나 이는 main completion blocker라기보다 regression floor / honesty floor다 |
| open-world `name-only -> runnable vulnerable Docker` | `50 / 100` | E2E case `50`, `name-only` case `39`, name-only family slug `14`, positive representative direct rerun 2종은 expectation을 통과했지만 `open-redirect-dynamic-name-only`는 still `deterministic_fallback`, `partial`, `thin_fallback_demo` | `TKT-001`, `TKT-002~005`, `TKT-006` | runnable closure는 일부 열렸지만 controller/runtime generalization이 아직 부족하다 |
| LLM-response shaped artifact -> promotable / reviewable candidate | `30 / 100` | `trusted-dynamic-sqli`가 `llm_fixture` / `llm_manifest` / `thin_or_incomplete`, positive pair repeatability는 둘 다 `measured_gate.ready=false`, support review는 `reviewable_bundle_count=0`, `by_support_status={blocked_mixed:2}` | `TKT-006`, `TKT-008-A1/A2`, `TKT-009-A1` | current main product gap이다. “실행 가능”과 “promotable/reviewable” 사이가 비어 있다 |

coverage shorthand는 아래처럼 읽는다.

- name-only coverage breadth:
  - total E2E cases `50`
  - `name-only` cases `39`
  - `name-only` family slug `14`
  - dynamic/strict 관련 `name-only` cases `14` (`dynamic` lane `12` + strict capability-gate lane `2`)
- boundedness summary shorthand:
  - catalog family `12`
  - scaffold stack pool `2`
  - executor topology class `2` (`single_service`, `service_plus_sidecar`)
  - `executor_multi_primary_supported=false`
  - `closed_vocabulary_family_discovery=true`

reading rule은 아래와 같다.

- `80 / 100` slice는 current floor를 보여 주지만, main completion priority를 다시 정렬시키는 근거로 읽지 않는다.
- `50 / 100` slice는 open-world runnable closure가 partial하게 열렸다는 뜻이지 generalized controller/runtime closure가 닫혔다는 뜻이 아니다.
- `30 / 100` slice가 current queue에서 가장 중요한 product gap이고, visible blocker cluster는 그대로 `TKT-006`, `TKT-008-A1/A2`, `TKT-009-A1`로 읽는다.

## Current Remaining Ticket Form

latest direct verification까지 반영한 current residual을 ticket-form으로 다시 묶으면 아래처럼 읽는 편이 맞다.

| Current residual cluster | Primary ticket(s) | Current interpretation |
| --- | --- | --- |
| selection/controller residual | `TKT-001` | representative dynamic lane가 still `deterministic_fallback`, `partial`로 남아 actual materialization branch authority가 아직 부족하다 |
| runtime/executor residual | `TKT-002`, `TKT-003`, `TKT-004`, `TKT-005` | actual Docker materialization은 열려도 generalized topology/dependency/env/seed control-plane은 아직 아니다 |
| visible synthesis blocker | `TKT-006` | fixture-backed positive lane가 `llm_manifest`, `thin_or_incomplete`로 남아 one-shot/stage-aware synthesis residual이 계속 보인다 |
| oracle realism residual | `TKT-007` | runnable lane 일부가 있어도 browserful/stateful oracle realism은 아직 대표 residual이다 |
| measured gate residual | `TKT-008-A1`, `TKT-008-A2` | positive pair manual repeatability truth가 still `measured_gate.ready=false`라 authoritative measured closure가 없다 |
| accept-path / registry residual | `TKT-009-A1`, `TKT-009-B1`, `TKT-009-B2` | positive pair manual support review truth가 `authority_ready_bundle_count=2`, `reviewable_bundle_count=0`로 남아 still `runnable but not promotable`이다 |
| summary/handoff polishing residual | `TKT-008-B1`, `TKT-008-B2` | main capability blocker는 아니지만 operator-facing summary/authority handoff polishing은 아직 남아 있다 |
| helper/operator companion residual | `TKT-008-B3` | helper bundle은 green이어도 sandbox helper output은 permission-artifact environment output으로 갈라질 수 있어 core truth와 분리해서 읽어야 한다 |
| deferred expansion | `TKT-010` | current control-plane/runtime/oracle/measured gate closure 이전에는 올리면 안 된다 |

reading rule은 아래와 같다.

- 눈앞의 visible core blocker는 `TKT-006`, `TKT-008-A1/A2`, `TKT-009-A1`이다.
- 그 blocker를 반복해서 만드는 상위 원인은 `TKT-001`, `TKT-002~005`다.
- helper/operator residual은 `TKT-008-B3` 안에서만 읽고, canonical completion priority order를 바꾸는 근거로 쓰지 않는다.

## Evaluation-To-Ticket Breakdown

latest 정성/정량평가를 current queue에 직접 내려쓰면 아래처럼 ticket-form으로 분해하는 편이 맞다.

| Evaluation statement | Primary ticket(s) | Direct evidence shorthand | Detailed implementation reading |
| --- | --- | --- | --- |
| honesty / fail-closed floor는 강하고 already green이다 | `TKT-001-E`, `TKT-008-A1`, `TKT-009-A2`, companion `TKT-008-B3` | strict lane 2종은 `fail_closed`, unsupported negative lane은 `abstain`, low-cost/ops/helper regression이 green | 이 bucket은 유지/회귀 보호가 본체다. priority를 올리는 근거가 아니라 “current floor를 잃지 말라”는 ticket로 읽는다 |
| representative dynamic lane는 runnable이지만 still fallback/partial이다 | `TKT-001-A/B/C/D/G`, `TKT-002-A/B/C`, `TKT-003-A/B`, `TKT-004-A/B`, `TKT-005-A/B/C`, `TKT-006-A/B/C` | `open-redirect-dynamic-name-only -> deterministic_fallback`, `partial`, `thin_fallback_demo` | selection/controller authority와 runtime control-plane이 아직 실제 생성 branch를 완전히 지배하지 못한다. controller/runtime/synthesis를 같이 읽어야 한다 |
| fixture-backed positive LLM-shaped lane도 thin quality에 머문다 | `TKT-006-A/B/C`, supporting `TKT-007-A/B` | `trusted-dynamic-sqli -> llm_fixture`, `llm_manifest`, `thin_or_incomplete`, `oracle_execution_parity=missing` | positive LLM-shaped artifact가 돌아가는 것과 stage-aware synthesis / oracle closure가 충분한 것은 다르다. 이 residual은 synthesis-first로 읽는다 |
| current measurable blocker는 quality/measured gate다 | `TKT-008-A1`, `TKT-008-A2` | positive pair repeatability 둘 다 `passed=true`지만 `measured_gate.ready=false` | current capability truth와 promotion policy truth를 authoritative gate로 더 선명하게 분리하고, high-quality representative lane가 왜 blocked인지 CI/policy surface로 승격해야 한다 |
| current accept-path blocker는 reviewable candidate 부재다 | `TKT-009-A1` | positive pair support review `reviewable_bundle_count=0`, `all_blocked_case_count=2`, `by_support_status={blocked_mixed:2}` | synthetic accept-path rehearsal을 넘어서 representative measured positive lane에서 실제 accepted local registry item이 생기는 workflow를 확보해야 한다 |
| broader browserful/stateful oracle realism은 아직 next quality gate다 | `TKT-007-A/B` | current positive lane 일부는 runtime까지 열렸지만 broader stateful oracle closure는 직접 닫히지 않았다 | current runnable closure를 higher-quality open-world claim으로 올리려면 browserful/sessionful replay와 realism rubric integration이 뒤따라야 한다 |
| expansion은 지금 점수를 올리는 leverage가 아니다 | `TKT-010` | boundedness summary가 여전히 stack pool `2`, topology class `2`, closed-vocabulary family discovery로 남아 있음 | family/stack 수를 늘리기 전에 controller/runtime/synthesis/measured gate를 닫아야 한다 |

queue reading rule은 아래와 같다.

- “현재 가장 먼저 손대면 점수가 실제로 오르는 slice”는 `TKT-006 -> TKT-008-A -> TKT-009-A1`이다.
- “그 score uplift를 구조적으로 지속시키는 root-cause slice”는 `TKT-001 -> TKT-002~005`다.
- “현재 green인데 계속 유지해야 하는 floor”는 `TKT-001-E`, `TKT-008-A1`, `TKT-009-A2`이며, 이를 new product backlog처럼 읽지 않는다.

## Planning Specificity Residual Overlay

latest 계획 검토에서 “방향은 맞지만 구현 계획으로는 아직 덜 구체적이다”라고 판단된 축을 current ticket 체계에 내려쓰면 아래처럼 읽는 편이 맞다.

| Planning-specificity question | Additional planning owner | Why current wording is still thin | Required plan upgrade |
| --- | --- | --- | --- |
| live LLM positive path를 무엇으로 판정하는가 | `TKT-006-D`, supporting `TKT-001-D` | current 문서는 strict live-LLM fail-closed honesty는 강하지만, live/fixture/stub/degraded positive path의 separate acceptance contract는 약하다. latest direct run의 `trusted-dynamic-sqli`도 `llm_fixture` / `llm_manifest`로 닫혀 live-positive proving ground가 아니다 | provider/model/prompt/decoding/retry/cost/cache/provenance를 묶는 live-positive materialization contract와 named proving-ground lane가 필요하다 |
| `live LLM + name-only + dynamic Docker` 교집합 proving ground를 무엇으로 판정하는가 | `TKT-009-A1-C`, supporting `TKT-006-D`, `TKT-008-A3` | current 문서는 `trusted-dynamic-sqli`와 `open-redirect-dynamic-name-only`를 separate proving ground로 읽지만, 둘의 교집합인 live-LLM name-only positive lane는 없다. 그래서 current pair를 다 통과해도 stricter target을 직접 입증하지는 못한다 | live-name-only positive lane, same lane의 measured/support acceptance contract, comparator lane와의 분리 기준을 explicit하게 고정해야 한다 |
| scenario selection을 실제로 어떻게 고르는가 | `TKT-001-H`, supporting `TKT-001-F/G` | `scenario_candidates` field shape는 있으나 contradiction, tie-break, abstain threshold, negative hypothesis consumption rule이 explicit하지 않다. latest direct run의 `csrf-dynamic-name-only`는 `selected_scenario_id`가 채워져도 `scenario.selected=false`로 남아 selection consistency drift를 보여 준다 | candidate score / contradiction score / abstain reason / evidence sufficiency / selected_by surface를 가진 selection algebra가 필요하다 |
| selection이 실제 Docker/materialization branch를 만들었다는 인과를 어떻게 남기는가 | `TKT-001-I`, supporting `TKT-001-D/H` | current 문서는 selection algebra와 authoritative controller를 말하지만, selected scenario가 어떤 file/runtime/oracle branch를 만들었는지 one-shot trace가 없다. provenance는 늘었지만 branch causality는 여전히 summary-friendly wording에 머문다 | `selection_branch_trace`, branch-controller provenance, selected-vs-rejected branch reason surface가 필요하다 |
| `file_manifest/build closure`를 무엇으로 판정하는가 | `TKT-006-E`, supporting `TKT-006-B/C`, `TKT-002-B/C` | Phase 2는 `file_manifest` stage를 선언하지만 current subtask/acceptance는 Dockerfile/build context/dependency manifest/build log 분류까지 내려와 있지 않다. latest direct rerun에서도 representative lane의 `generator_manifest.staged_synthesis.stage_order`는 아직 `oracle_contract`에서 멈추고, actual `artifacts/<sid>/build/build.log`가 존재해도 top-level manifest/summary의 `build_log/image_tag`는 null일 수 있었다. 그래서 actual Docker materialization claim이 stage wording보다 느슨하다 | typed `file_manifest` schema, build-ready validator, build failure taxonomy, workspace/build artifact validation surface와 build pointer roundtrip이 필요하다 |
| topology/runtime closure를 어떤 representative ladder로 닫는가 | `TKT-002-D`, supporting `TKT-003-A/B`, `TKT-004-A/B`, `TKT-005-A/B/C` | current plan은 generalized runtime closure를 말하지만 proving-ground topology class ladder가 없다. latest direct run은 사실상 `single_service`와 `service_plus_sidecar`만 직접 재현됐다 | `service_only -> service+db -> service+supporting sidecar -> multi_primary_web_pair -> browserful_lab_topology`처럼 explicit topology ladder가 필요하다 |
| realism rubric이 실제 gate에 어떻게 들어가는가 | `TKT-007-C`, supporting `TKT-008-A1` | rubric integration은 말하지만 axis와 threshold가 문장 수준에 머문다. latest direct run의 `csrf-dynamic-name-only`도 sessionful single-flow replay까지는 보였지만 browserful/stateful realism closure를 뜻하지는 않았다 | exploit-path diversity / statefulness / victim realism / environment fidelity / verifier independence / cleanup reproducibility 같은 explicit rubric axis가 필요하다 |
| generation path를 measured gate에서 어떻게 분리 측정하는가 | `TKT-008-A3`, supporting `TKT-006-D` | current matrix는 family/stack/topology/oracle 난이도는 보지만 `live/fixture/stub/degraded` generation path를 explicit 축으로 보지 않는다. 그래서 LLM-response quality uplift와 fallback reshaping이 같은 measured bucket에 섞일 수 있다 | `generation_path` axis와 lane별 blocker/acceptance policy가 필요하다 |
| Tavily API가 실제로 필수인가 | companion operational prerequisite, not a new core ticket | current repository는 Tavily와 custom remote endpoint를 모두 지원하고 ops/E2E entry도 now `VULD_E2E_REQUIRE_REMOTE_PROVIDER=1` generic gate와 `VULD_E2E_REQUIRE_TAVILY=1` canonical Tavily gate를 분리한다. live unknown-CWE E2E gate는 여전히 Tavily key를 canonical prerequisite로 쓴다. 이걸 product-wide mandatory dependency로 읽으면 capability/ops truth가 섞인다 | Tavily는 “current canonical live remote-research provider”로만 문서화하고, researcher remote capability 자체는 custom provider alternative도 같이 남긴다 |
| LLM-generated Docker build safety policy를 어디서 fail-closed 하는가 | `TKT-006-F`, supporting `TKT-006-E` | current constraints는 runtime isolation은 강하지만, open-world에서 LLM이 만든 Dockerfile/build step 자체를 어떤 instruction/dependency/network policy로 통제할지는 backlog wording이 없다 | build-time instruction/dependency/base-image/network policy와 explicit build-stage rejection failure class가 필요하다 |
| first promotable lane를 무엇으로 삼을 것인가 | `TKT-009-A1-A`, `TKT-009-A1-B` | current accept-path는 “representative measured lane”이라는 추상 표현에 가깝다. latest direct/support run에서도 `trusted-dynamic-sqli`와 `open-redirect-dynamic-name-only`는 둘 다 `blocked_mixed`였고, comparator lane `sqli-sidecar-compiler-custom-env`는 high-quality bounded artifact지만 promotion target이 아니었다 | `trusted-dynamic-sqli`와 `open-redirect-dynamic-name-only`를 분리된 proving-ground accept-path로 고정하고, `sqli-sidecar-compiler-custom-env`는 comparator lane로 명시할 필요가 있다 |
| expansion을 언제 열 것인가 | `TKT-010-C` | current defer rule은 맞지만 unlock contract가 없다 | expansion before/after boundary를 measurable prerequisite bundle로 명시해야 한다 |

reading rule은 아래와 같다.

- 이 overlay는 새 top-level ticket를 만드는 게 아니라 existing ticket의 구현 명세를 더 구체화하는 용도다.
- current main order는 바뀌지 않는다. 다만 `TKT-001`, `TKT-006`, `TKT-009-A1`, `TKT-010` 내부의 subtask priority는 더 또렷하게 읽을 수 있어야 한다.
- implementation review에서는 이 overlay의 각 row가 실제 subtask/acceptance wording에 반영되어 있는지 먼저 확인하는 편이 맞다.

## Current Remaining Ticket Routing

latest 확인 내용을 “무엇이 남았는가 / 무엇을 먼저 닫는가 / 무엇이 companion-only인가” 기준으로 다시 줄이면 아래 routing으로 읽는 편이 맞다.

| Question | Ticket-form answer | Reading rule |
| --- | --- | --- |
| 지금 가장 먼저 눈에 보이는 blocker가 무엇인가 | `TKT-006`, `TKT-008-A1/A2`, `TKT-009-A1` | current positive representative lane에서 바로 관찰되는 visible blocker cluster다 |
| 그 blocker를 반복해서 만드는 상위 원인은 무엇인가 | `TKT-001`, `TKT-002~005` | selection/controller authority와 generalized runtime/control-plane residual이 structural root-cause cluster다 |
| 현재 “실행은 되지만 promotable은 아님”을 만드는 직접 근거는 무엇인가 | `TKT-006` + `TKT-008-A1/A2` + `TKT-009-A1` | `thin_or_incomplete` / `deterministic_fallback` / `measured_gate.ready=false` / `reviewable_bundle_count=0`를 같이 읽는다 |
| helper/operator green bundle을 core progress로 읽어도 되는가 | `no`, `TKT-008-B3` only | workspace-local helper bundle `343 passed`는 companion stability evidence이지 core reprioritization 근거는 아니다 |
| sandbox helper empty aggregate나 `case_failed` / `quality_tier_inconsistent` / `verdict_authority_inconsistent` drift는 어디에 귀속되는가 | `TKT-008-B3` | runtime-equivalent truth가 아니라 permission-artifact environment output distinction으로 읽는다 |
| latest audit3 summary-level classification은 어떤 ticket에 귀속되는가 | `TKT-001-E`, `TKT-001`, `TKT-006`, `TKT-008-A1/A2`, `TKT-009-A1`, `TKT-008-B3` | strict stub `fail_closed`는 capability honesty, trusted positive lane `llm_manifest`/measured blocked는 synthesis+measured residual, representative dynamic lane `deterministic_fallback`/`partial`는 selection+synthesis residual, manual `blocked_mixed` aggregate는 measured+accept-path residual, helper split은 companion-only로 읽는다 |
| summary/handoff polishing은 어디에 속하는가 | `TKT-008-B1/B2` | 본체 blocker보다 뒤에 두는 operator-facing polishing residual이다 |
| expansion은 지금 어디에 두는가 | `TKT-010` | current control-plane/runtime/oracle/measured-support closure 이후의 defer bucket이다 |

practical shorthand는 아래와 같다.

- visible blocker cluster: `TKT-006`, `TKT-008-A1/A2`, `TKT-009-A1`
- structural root-cause cluster: `TKT-001`, `TKT-002~005`
- polishing cluster: `TKT-008-B1/B2`
- companion-only cluster: `TKT-008-B3`
- deferred expansion cluster: `TKT-010`

## LLM-Response Capability Overlay

LLM response로 open-world `name-only -> vulnerable Docker`를 만든다는 더 엄격한 기준으로 읽을 때도, 새 product backlog를 추가하기보다 기존 bucket에 아래처럼 귀속시켜 읽는 편이 맞다.

| LLM-response perspective question | Primary ticket(s) | Current reading |
| --- | --- | --- |
| live LLM path 부재를 정직하게 fail-closed 하는가 | `TKT-001-E` | `open-redirect-strict-dynamic-stub` no-Docker lane에서 `strict_dynamic_live_llm_unavailable` honesty를 계속 회귀시킨다 |
| LLM/research response가 actual materialization branch를 지배하는가 | `TKT-001-A/B/C/D/G/H` | current selection/evidence surface는 풍부하지만 still bounded builder/fallback 편향이 남아 있고, scenario selection algebra도 아직 약하다 |
| LLM/research selection이 어떤 materializer/file/runtime/oracle branch를 열었는지 causal trace가 남는가 | `TKT-001-I`, supporting `TKT-001-D/H` | current summary/provenance는 richer해졌지만 selected scenario가 actual Docker branch를 만들었다는 one-shot causal trace는 아직 약하다 |
| positive LLM-shaped artifact를 stage-aware하게 synthesis 하는가 | `TKT-006-A/B/C/D` | one-shot manifest bottleneck과 repair-first 한계가 남아 있고, live/fixture/stub/degraded positive path provenance contract도 아직 얕다 |
| LLM response가 build-ready file manifest와 Docker build contract까지 닫히는가 | `TKT-006-E/F`, supporting `TKT-002-B/C` | current roadmap는 `file_manifest` stage를 선언하지만 Dockerfile/build context/build failure taxonomy/safety policy는 아직 implementation-sized contract로 충분히 내려오지 않았다 |
| LLM-shaped result가 실제 Docker runtime/topology/dependency로 닫히는가 | `TKT-002-A/B/C/D`, `TKT-003-A/B`, `TKT-004-A/B`, `TKT-005-A/B/C` | current session later rerun에서는 `trusted-dynamic-sqli`, `open-redirect-dynamic-name-only`가 둘 다 actual Docker materialization/runtime까지 갔지만, 하나는 fixture-backed `llm_manifest`, 다른 하나는 `deterministic_fallback` partial이어서 generalized runtime closure는 여전히 본체 residual이다 |
| LLM-shaped result가 browserful/stateful oracle까지 검증되는가 | `TKT-007-A/B/C` | payload replay 일부를 넘는 richer realism/oracle closure가 아직 남아 있고 rubric axis도 아직 operationalized되지 않았다 |
| true `live LLM + name-only + dynamic Docker` positive lane가 measured/support accept-path까지 존재하는가 | `TKT-006-D`, `TKT-008-A3`, `TKT-009-A1-C` | current proving ground는 fixture-backed positive lane와 degraded dynamic name-only lane로 분리돼 있고, stricter 교집합 lane는 아직 없다 |
| LLM-shaped positive lane가 measured gate와 support promotion까지 닫히는가 | `TKT-008-A1/A2`, `TKT-009-A1-A/B`, `TKT-009-B1/B2` | current measured/support honesty는 강하지만 representative positive accept-path는 아직 direct verification이 없다 |
| strict live-LLM fail-closed lane와 positive LLM-response Docker materialization을 혼동하지 않는가 | `none (interpretation rule)`, supporting `TKT-001-E` | current canonical reading rule은 “strict stub pass = positive capability verified”가 아니라, 둘을 분리해 읽는 것이다 |

현재 direct verification 기준으로는 strict live-LLM fail-closed honesty는 no-Docker lane에서 확인됐고, later same-day Docker-enabled rerun에서는 fixture-backed positive LLM-shaped lane(`trusted-dynamic-sqli`)와 representative dynamic lane(`open-redirect-dynamic-name-only`)도 actual runtime/oracle path를 다시 열었다. 다만 전자는 `llm_fixture`/`llm_manifest`와 `thin_or_incomplete`, 후자는 `llm_degraded`/`deterministic_fallback`와 `thin_fallback_demo`/`partial`로 남았고 둘 다 measured/support gate에서는 blocked였다. 따라서 current completion priority order는 그대로 유지하되, LLM-response 기준 해석은 `TKT-001 -> TKT-002~005 -> TKT-006 -> TKT-007 -> TKT-008-A -> TKT-009-*` 본체를 더 정확히 읽는 쪽이 맞다.

## Confirmed Completion Priority Order

latest direct verification과 current completeness assessment를 함께 읽었을 때, 현재 open-world/name-only 목표 기준의 canonical completion priority order는 아래와 같다.

| Order | Ticket bucket | Primary subtasks | Why it is ahead of the next bucket |
| --- | --- | --- | --- |
| `1` | `TKT-001` | `TKT-001-A/B/C/D/E/F/G/H/I` | selection/controller residual이 아직 actual materialization을 충분히 지배하지 못한다. scenario selection algebra와 selection-to-materialization causal trace까지 닫혀야 이후 runtime/oracle hardening이 bounded branch 위 보강이 아니라 real open-world closure가 된다 |
| `2` | `TKT-002` ~ `TKT-005` | `TKT-002-A/B/C/D`, `TKT-003-A/B`, `TKT-004-A/B`, `TKT-005-A/B/C` | 무엇을 만들지보다 어떻게 실제로 실행되는지가 여전히 generalized control-plane이 아니다. topology class ladder를 포함한 runtime/executor contract가 닫혀야 representative Docker generation claim이 가능하다 |
| `3` | `TKT-006` | `TKT-006-A/B/C/D/E/F` | branch controller와 runtime contract가 있어도 one-shot synthesis bottleneck이 남으면 actual generation success가 불안정하다. live-positive provenance contract와 build-ready/safe file-manifest contract까지 포함한 stage-aware recovery는 그 다음 leverage다 |
| `4` | `TKT-007` | `TKT-007-A/B/C` | runtime이 닫혀도 oracle realism이 약하면 open-world success claim을 못 올린다. browserful/stateful replay와 explicit realism rubric이 next quality gate다 |
| `5` | `TKT-008-A` | `TKT-008-A1/A2/A3` | measured preview는 이미 있지만 authoritative CI/policy gate는 아직 아니다. capability truth와 support-ready truth를 분리하고 generation-path claim까지 같이 측정하려면 이 bucket이 필요하다 |
| `6` | `TKT-009-A1`, `TKT-009-B1/B2` | `TKT-009-A1-A/B/C`, `TKT-009-B1`, `TKT-009-B2` | blocked/no-op path는 정직하지만 representative accept-path proving ground와 long-lived registry lifecycle은 아직 없다. promotion surface closure는 measured gate 이후가 맞고, stricter reading에서는 live-LLM name-only accept-path까지 별도로 닫혀야 한다 |
| `7` | `TKT-008-B` | `TKT-008-B1/B2` | summary/handoff consistency residual은 중요하지만 main capability blocker라기보다 authoritative handoff polishing 성격이 더 강하다 |
| `8` | `TKT-010` | `TKT-010-A/B/C` | expansion은 current control-plane/runtime/oracle/measured gate closure와 explicit unlock contract 이전에 올리면 안 된다 |

priority 해석 규칙은 아래와 같다.

- `TKT-001-E`, `TKT-008-A1`, `TKT-009-A2`는 current low-cost regression net의 핵심이지만, 이미 blocked/no-op honesty를 보호하는 stabilization lane이기도 하다.
- `TKT-009-A2`는 current safety behavior preservation ticket이지, representative positive accept-path를 먼저 여는 ticket은 아니다.
- `TKT-008-B3`, `TKT-009-B3`는 latest workspace-local contract drift stabilization으로서 이미 bounded closure에 더 가깝고, main completion order를 바꾸지 않는다.

## Estimated Turn Envelope

아래 추산은 `1턴 = 하나의 subtask 구현 + representative rerun + 문서 반영`으로 잡은 practical envelope다. backlog slicing과 sequencing 판단을 돕는 운영 추산치이지, 일정 commitment는 아니다.

| Goal slice | Estimated turns | Primary ticket focus | Why this is the current envelope |
| --- | --- | --- | --- |
| representative positive pair를 `runnable -> promotable`로 끌어올리는 최소 범위 | `8 ~ 12턴` | `TKT-006`, `TKT-008-A1/A2`, `TKT-009-A1`, partial `TKT-001` | current visible blocker가 synthesis quality, measured gate, reviewable accept-path에 몰려 있고, positive pair가 이미 runnable이라 바로 보이는 bottleneck부터 줄이는 범위다 |
| `live LLM response -> open-world positive`를 더 강하게 주장할 수 있는 수준 | `16 ~ 24턴` | `TKT-001`, `TKT-002~005`, `TKT-006`, `TKT-007`, `TKT-008-A` | visible blocker뿐 아니라 structural root-cause인 selection authority와 generalized runtime/oracle closure까지 같이 닫아야 stronger claim이 가능하다 |
| promotable + generalized + polishing까지 포함한 보수적 범위 | `20 ~ 30턴` | `TKT-001` ~ `TKT-009-B`, excluding `TKT-010` | representative accept-path, registry lifecycle, summary/handoff polishing까지 포함한 end-to-end hardening 범위다 |

turn envelope 해석 규칙은 아래와 같다.

- `TKT-010` expansion은 현재 envelope에서 제외한다. runtime/oracle/measured gate closure 이전에는 implementation turn 추산에 넣지 않는다.
- `8 ~ 12턴`은 current positive representative pair(`trusted-dynamic-sqli`, `open-redirect-dynamic-name-only`)를 기준으로 한 practical promotion slice다.
- `16 ~ 24턴` 이후부터는 `live LLM response` purity와 generalized runtime/oracle claim을 함께 읽는다.
- latest representative pair truth가 바뀌더라도 visible blocker와 structural root-cause bucket이 유지되면, turn envelope는 priority order보다 느리게 변한다.

## Assessment-To-Ticket Interpretation

latest Docker-enabled direct verification까지 포함해 현재 평가를 ticket 형태로 다시 쪼개면 아래처럼 읽는 편이 맞다.

- visible blocker cluster: `TKT-006`, `TKT-008-A1/A2`, `TKT-009-A1`
  - `trusted-dynamic-sqli`는 actual Docker materialization까지 갔지만 `llm_fixture` / `llm_manifest`, `thin_or_incomplete`, `measured_gate.ready=false`, `reviewable_bundle_count=0`로 남았다.
  - 즉 current positive representative lane에서 가장 먼저 보이는 미비점은 synthesis quality, measured gate, reviewable accept-path closure다.
- structural root-cause cluster: `TKT-001`, `TKT-002~005`
  - `open-redirect-dynamic-name-only`는 actual runtime/oracle path를 다시 열었지만 `llm_degraded` / `deterministic_fallback`, `partial`, `thin_fallback_demo`로 남았다.
  - 즉 visible blocker 뒤의 상위 원인은 여전히 selection authority와 generalized runtime control-plane closure 부족이다.
- interpretation rule:
  - latest positive rerun truth는 새 ticket를 추가하는 근거가 아니라 existing `TKT-001`, `TKT-006`, `TKT-008-A*`, `TKT-009-A1` 해석을 더 촘촘하게 만드는 근거다.
  - 그래서 canonical priority order는 유지하되, next recurring representative regression set에는 `trusted-dynamic-sqli`, `open-redirect-dynamic-name-only`를 같이 포함해 읽는다.

## Fresh Rerun Ticket Overlay

`2026-03-20` fresh direct execution을 ticket 관점으로 다시 묶으면 아래처럼 읽는 편이 맞다.

- `TKT-001-E`
  - `open-redirect-strict-dynamic-stub`는 이번 fresh rerun에서도 `strict_dynamic_live_llm_unavailable`, `generation_origin=capability_gate_rejected`, `stage_ceiling=pre_generation`으로 끝났다.
  - 즉 strict live-LLM fail-closed honesty는 계속 정상이고, 이 bucket은 여전히 regression protection 성격이 강하다.
- `TKT-006`
  - `trusted-dynamic-sqli`는 이번 fresh rerun에서도 `llm_fixture`, `llm_manifest`, `thin_or_incomplete`로 남았다.
  - 즉 positive lane가 actual Docker materialization까지 가도 synthesis quality/resilience 본체 residual은 그대로다.
- `TKT-008-A1/A2`
  - positive pair repeatability는 둘 다 `passed=true`지만 `measured_gate.ready=false`였다.
  - 즉 measured gate preview는 정상이고, authoritative promotion gate closure가 아직 잔여라는 해석이 다시 확인됐다.
- `TKT-009-A1`
  - positive pair support review는 이번 fresh rerun에서도 `support_candidate_file_count=2`, `authority_ready_bundle_count=2`, `reviewable_bundle_count=0`, `by_support_status={blocked_mixed:2}`로 남았다.
  - 즉 current claim은 여전히 `runnable but not promotable`이고 representative accept-path closure는 아직 없다.
- `TKT-008-B3`
  - helper contract bundle은 latest workspace-local head에서 `343 passed`로 green이고, sandbox helper run에서는 `docker daemon permission denied`가 permission artifact marker/note로 분리돼 surface된다.
  - current workspace-local direct verification에서는 same sandbox helper output이 `support_candidate_file_count=2`, `authority_ready_bundle_count=0`, `measured_gate_blocked_bundle_count=0`, `reviewable_bundle_count=0`, `by_support_status={}` empty aggregate로 끝날 수도 다시 확인됐다. same output은 runtime-equivalent truth가 아니라 permission-artifact environment output으로 읽는다.
  - same-day latest liveaudit rerun에서도 `docker ps` / `docker ps -a`와 representative direct rerun 3종, manual `repeat_case.py -> support_review.py` chain은 다시 정상인데 sandbox helper wrapper만 same permission-artifact split을 반복했다. therefore latest evidence도 계속 `TKT-008-B3` companion residual로만 귀속한다.
  - same-day latest audit2 rerun에서도 `docker ps` / `docker ps -a`와 representative direct rerun 3종, manual `tests/e2e/support_review.py` aggregate는 다시 정상인데 sandbox helper wrapper만 same permission-artifact split을 반복했다. helper per-case `repeatability_report.json`도 둘 다 `passed=false`였고 blocker에 `case_failed`, `quality_tier_inconsistent`, `verdict_authority_inconsistent`가 같이 남았다.
  - latest `2026-03-21` direct rerun에서도 `docker ps` / `docker ps -a`는 again empty list로 정상이고 `docker images`에는 fresh `sid-*` image가 남은 상태에서 representative direct rerun 3종과 manual `repeat_case.py -> support_review.py` chain은 다시 성공했지만, sandbox helper wrapper는 again empty aggregate와 `permission_artifact_summary.json(runtime_equivalent_helper_truth_available=false, recommended_action=unrestricted_docker_rerun)`로 갈라졌다.
  - same `2026-03-21` latest audit3 rerun에서는 summary-level classification도 다시 유지됐다. strict stub은 `fail_closed`, `pre_generation`, `pre-generation fail-closed`; `trusted-dynamic-sqli`는 `llm_fixture`, `llm_manifest`, `trusted dynamic`; `open-redirect-dynamic-name-only`는 `llm_degraded`, `deterministic_fallback`, `partial`, `deterministic fallback dependent`로 다시 닫혔다.
  - same `2026-03-21` helper per-case `repeatability_report.json`는 둘 다 `passed=false`였고 blocker에 `case_failed`, `cache_reuse_inconsistent`, `artifact_quality_band_not_high`, `quality_tier_inconsistent`, `oracle_execution_parity_not_high`, `verdict_authority_inconsistent`가 같이 남았다. therefore same latest rerun도 current core truth 변화가 아니라 bounded helper projection drift evidence로만 읽는다.
  - unrestricted Docker-enabled rerun에서는 `run_positive_pair_promotion_check.sh` helper path도 다시 `blocked_mixed` aggregate current truth와 정렬된다. same bounded environment distinction만 companion/operator stabilization residual로 읽는다.
- reprioritization rule:
  - 이번 fresh rerun은 새 product backlog를 만들지 않는다.
  - visible blocker는 계속 `TKT-006`, `TKT-008-A*`, `TKT-009-A1`이고, structural root-cause는 그대로 `TKT-001`, `TKT-002~005`다.
  - helper/operator drift는 `TKT-008-B3` 안에서만 읽고, canonical completion priority order는 여전히 core bucket 기준으로 유지한다.
  - 따라서 canonical completion priority order는 바뀌지 않는다.

## Open-World Completion Axis Map

[docs/problem.md](problem.md)의 success criteria 5축을 active backlog에 매핑하면 아래와 같다.

| Axis | Meaning | Primary ticket(s) | Current ceiling | Next leverage |
| --- | --- | --- | --- | --- |
| 선택 | family/stack/topology/oracle이 evidence-backed 또는 requirement-backed로 결정되는가 | `TKT-001-A/B/C/D/E/F/G`, long-term `TKT-010-A/B` | enriched candidate surface와 bounded selection truth는 생겼지만 joint primitive-first scenario controller는 아직 아님 | `TKT-001`로 primitive/dependency/topology/oracle branch controller를 actual materialization input으로 승격 |
| 생성 | 산출물이 silent default 없이 intent-faithful하게 materialize되는가 | `TKT-001`, `TKT-006` | bounded family-first/degraded fallback generation은 가능하지만 one-shot manifest 의존과 bounded builder 편향이 큼 | `TKT-001` + `TKT-006`으로 branch split과 stage-resumable synthesis를 같이 닫기 |
| 실행 | runtime plan과 actual executor behavior가 일치하는가 | `TKT-002`, `TKT-003`, `TKT-004`, `TKT-005` | single-service와 bounded sidecar parity는 많이 올라왔지만 generalized runtime control-plane은 아님 | `TKT-002` ~ `TKT-005`로 `runtime_graph/executor_plan` authoritative화, dependency/seed/env-volume-network semantics generalization |
| 검증 | verifier가 negative/forbidden/metamorphic contract를 실제로 반영하는가 | `TKT-007`, `TKT-008-A1/A2` | stateless/body-structured/sessionful 일부 closure와 measured preview는 있으나 broader browserful/stateful oracle과 authoritative gate는 미완 | `TKT-007`으로 richer oracle replay, `TKT-008-A*`로 measured gate authoritative화 |
| 보고 | `intent_met/partial/abstain/fail_closed`와 support/promotion state를 혼동 없이 surface하는가 | `TKT-008-B*`, `TKT-009-A*`, `TKT-009-B*` | honesty surface와 blocked no-op workflow는 강하지만 actual accept-path와 long-lived provenance/merge policy는 잔여 | `TKT-009-A1` reviewable accept-path direct verification, 이후 `TKT-009-B1/B2` provenance/history hardening |

## Open-World Completion Checklist

success criteria 5축을 “무엇이 닫혀야 완료로 볼 수 있는가” 관점에서 다시 읽으면 아래와 같다.

| Axis | Completion question | Minimum evidence to inspect | Current not-yet-done signal | Primary blocking ticket(s) |
| --- | --- | --- | --- | --- |
| 선택 | family/stack/topology/oracle 선택이 primitive-first joint decision으로 materialization에 실제 영향을 주는가 | `summary.json`의 `request_ir` / `selection_decision` / `name_only_outcome`, `metadata/<SID>/researcher_report.json`, selection-to-materialization branch trace, representative name-only rerun | evidence-enriched top choice는 보이지만 family-first bounded builder가 still primary path이고 selection-to-materialization causal trace도 약하다 | `TKT-001-A/B/C/D/E/F/G/H/I` |
| 생성 | staged synthesis가 one-shot default가 아니라 intent-faithful branch/recovery로 산출물을 만들고 build-ready file manifest까지 남기는가 | `metadata/<SID>/generator_manifest.json`, `generator_runs.json`, `generator_failures.jsonl`, `loop_state.json`, staged `file_manifest`, workspace `Dockerfile`/dependency manifest/PoC files, `artifacts/<SID>/build/build.log`, `manifest.json` or `failure_manifest.json` | bounded/degraded generation은 가능하지만 stage-resumable repair와 branch split이 authoritative하지 않고 `file_manifest/build` contract도 아직 약하다 | `TKT-001`, `TKT-006` |
| 실행 | `runtime_graph` / `executor_plan`이 설명 surface가 아니라 actual executor truth를 지배하는가 | `manifest.json`의 `runtime_graph` / `executor_plan`, `artifacts/<SID>/run/summary.json`, representative E2E `summary.json` | single-service 및 bounded sidecar parity는 있으나 generalized lifecycle/seed/env-volume-network closure는 부족 | `TKT-002`, `TKT-003`, `TKT-004`, `TKT-005` |
| 검증 | oracle replay와 measured gate가 richer stateful truth를 반영하며 promotion gate로 authoritative하게 연결되고 generation path까지 분리 측정하는가 | `artifacts/<SID>/run/oracle_execution.json`, `reports/evals.json`, `repeatability_report.json`, `matrix_report.json`, generation-path observations | stateless/sessionful 일부 closure와 preview gate만 있고 browserful/stateful replay, generation-path axis, CI/policy gate는 미완 | `TKT-007`, `TKT-008-A1`, `TKT-008-A2`, `TKT-008-A3` |
| 보고 | `name_only_outcome`와 support/review/promotion current state가 실제 accept/reject lifecycle까지 혼동 없이 이어지는가 | representative E2E `summary.json`, `support_candidate.json`, `support_review_index.json`, `support_registry_update.json`, `curated_support_registry.json` | blocked no-op / schema parity는 닫혔지만 representative reviewable accept-path와 long-lived provenance/merge lifecycle은 미완 | `TKT-009-A1`, `TKT-009-B1`, `TKT-009-B2` |

## Open-World Completion Review Flow

success criteria 5축을 실제 완료판정으로 검토할 때는 아래 순서를 canonical review flow로 쓴다.

1. `Open-World Completion Axis Map`
   - 지금 어떤 축이 비어 있고, 어떤 ticket bucket이 primary owner인지 먼저 확인한다.
2. `Open-World Completion Checklist`
   - 각 축을 완료로 보려면 어떤 최소 evidence가 필요한지 확인한다.
3. [docs/final_solution.md](final_solution.md)의 `Acceptance-To-Validation Translation`
   - 현재 검토 대상 축이 어떤 phase acceptance와 연결되는지 확인한다.
4. 이 문서의 `Validation Routing` / `Validation Reading Order`
   - 어떤 harness와 어떤 code entrypoint부터 열어야 하는지 정한다.
5. [docs/handbook.md](handbook.md)의 `Open-World Axis Reading Hints`, [docs/code/workspaces.md](code/workspaces.md)의 `Open-World Axis Artifact Hints`
   - 실제 artifact를 어디서 읽고 어떤 vocabulary로 해석할지 확인한다.
6. [docs/current_state_gap_analysis.md](current_state_gap_analysis.md), [docs/constraints.md](constraints.md)
   - observed truth와 forbidden claim을 대조해 premature success claim을 막는다.

## Open-World Completion Reading Order

완료판정부터 시작할 때의 canonical reading order는 아래와 같다.

1. [docs/work_tickets.md](work_tickets.md)의 `Completion Companions`
2. [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Axis Map`, `Open-World Completion Checklist`
3. [docs/final_solution.md](final_solution.md)의 `Acceptance-To-Validation Translation`
4. [tests/e2e/README.md](../tests/e2e/README.md)의 harness command / case layout / ticket mapping
5. [docs/code/README.md](code/README.md)와 subsystem docs의 `Completion Review Entry` / `Representative Validation Surface`
6. [docs/handbook.md](handbook.md)의 `Open-World Axis Reading Hints`, troubleshooting
7. [docs/current_state_gap_analysis.md](current_state_gap_analysis.md), [docs/constraints.md](constraints.md)

## Open-World Residual Ticket Breakdown

latest open-world/name-only 직접 검증과 completeness assessment를 티켓 묶음으로 다시 쪼개면 아래와 같다.

| Axis | Confirmed residual | Ticket decomposition | Immediate completion gate |
| --- | --- | --- | --- |
| 선택 | primitive-first joint decision이 아직 authoritative controller가 아니고 family-first bounded builder가 여전히 primary path다 | `TKT-001-A`, `TKT-001-B`, `TKT-001-C`, `TKT-001-D`, `TKT-001-E`, `TKT-001-F`, `TKT-001-G`, `TKT-001-H`, `TKT-001-I` | representative non-SQLi name-only lane가 primitive/dependency/topology/oracle decision에서 실제로 materialize되고, summary가 branch authority와 causal trace를 직접 남긴다 |
| 생성 | one-shot manifest 의존이 여전히 크고 staged repair/resume가 deterministic fallback보다 앞서지 못하며 build-ready file-manifest contract도 약하다 | `TKT-001-B`, `TKT-001-C`, `TKT-006-A`, `TKT-006-B`, `TKT-006-C`, `TKT-006-D`, `TKT-006-E`, `TKT-006-F` | stage artifact persistence와 repair-first retry가 representative dynamic lane에서 measurable하게 남고 generic fallback 진입이 줄며 build-ready/safe file manifest가 explicit contract로 남는다 |
| 실행 | `runtime_graph` / `executor_plan`이 아직 설명/provenance surface에 더 가깝고 generalized lifecycle/seed/env-volume/network semantics가 미완이다 | `TKT-002-A`, `TKT-002-B`, `TKT-002-C`, `TKT-003-A`, `TKT-003-B`, `TKT-004-A`, `TKT-004-B`, `TKT-005-A`, `TKT-005-B`, `TKT-005-C` | representative single-service / sidecar lane가 graph-first execution으로 돌고 lifecycle/seed/network provenance가 same contract surface로 남는다 |
| 검증 | browserful/stateful oracle replay가 부족하고 measured gate는 아직 preview/policy split 수준이며 generation-path axis도 약하다 | `TKT-007-A`, `TKT-007-B`, `TKT-007-C`, `TKT-008-A1`, `TKT-008-A2`, `TKT-008-A3` | representative stateful lane에서 richer oracle replay가 quality tier에 반영되고 measured gate가 CI/policy authoritative surface로 승격되며 generation path까지 separate bucket으로 읽힌다 |
| 보고 | honesty surface와 blocked no-op path는 닫혔지만 actual reviewable accept-path, `live LLM + name-only` proving ground, long-lived registry provenance/merge lifecycle은 미완이다 | `TKT-009-A1`, `TKT-009-A2`, `TKT-009-B1`, `TKT-009-B2` | representative measured accept-path가 non-empty accepted registry item을 materialize하고, same registry가 provenance/history/merge policy를 일관되게 유지하며, stricter reading용 live-name-only accept path도 explicit하게 남는다 |

bounded stabilization으로 이미 닫힌 slice는 현재 우선순위 본체가 아니다.

- `TKT-008-B3`: repeatability helper/report contract stabilization
- `TKT-009-B3`: registry API / artifact schema-status parity
- latest rerun도 위 close state를 재확인했을 뿐 새 product backlog ticket을 추가하지 않았다.

## Open-World Residual Review Flow

latest confirmed residual을 실제 구현 검토 순서로 내릴 때는 아래를 canonical residual review flow로 쓴다.

1. `Open-World Residual Ticket Breakdown`
   - 지금 residual이 어느 축과 어느 ticket bundle에 걸려 있는지 먼저 확인한다.
2. `Open-World Completion Checklist`
   - 그 residual이 닫혔다고 보려면 어떤 최소 evidence가 필요한지 확인한다.
3. [docs/final_solution.md](final_solution.md)의 `Acceptance-To-Validation Translation`
   - 해당 residual이 어떤 phase acceptance와 연결되는지 확인한다.
4. 이 문서의 `Validation Routing` / `Validation Reading Order`
   - representative harness와 reading order를 정한다.
5. [docs/code/README.md](code/README.md), subsystem docs의 `Ticket-First Entry` / `Representative Validation Surface`
   - 실제 code entrypoint와 regression focus를 정한다.
6. [docs/handbook.md](handbook.md)의 `Open-World Axis Reading Hints`, [docs/code/workspaces.md](code/workspaces.md)의 `Open-World Axis Artifact Hints`
   - artifact truth를 어디서 읽을지 정한다.
7. [docs/current_state_gap_analysis.md](current_state_gap_analysis.md), [docs/constraints.md](constraints.md)
   - observed truth와 forbidden claim을 대조해 residual이 실제로 닫혔는지 판단한다.

## Open-World Residual Reading Order

residual 검토부터 시작할 때의 canonical reading order는 아래와 같다.

1. [docs/work_tickets.md](work_tickets.md)의 `Open-World Residual Ticket Breakdown`
2. [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Checklist`
3. [docs/final_solution.md](final_solution.md)의 `Acceptance-To-Validation Translation`
4. [tests/e2e/README.md](../tests/e2e/README.md)의 harness command / case layout / ticket mapping
5. [docs/code/README.md](code/README.md)와 subsystem docs의 `Residual Review Entry` / `Residual Review Focus`
6. [docs/handbook.md](handbook.md)의 artifact reading hints / troubleshooting
7. [docs/current_state_gap_analysis.md](current_state_gap_analysis.md), [docs/constraints.md](constraints.md)

## Implementation Entry Points And Validation Surface

phase와 subtask owner를 실제 코드/검증 표면으로 옮길 때는 아래 표를 기준으로 시작한다.

| Ticket bucket | Start here | Primary artifact / surface | Representative validation focus |
| --- | --- | --- | --- |
| `TKT-001` | [docs/code/orchestrator.md](code/orchestrator.md), [docs/code/agents_researcher.md](code/agents_researcher.md), [docs/code/agents_generator.md](code/agents_generator.md), [docs/code/common.md](code/common.md) | `request_ir`, `selection_decision`, `design_brief`, `runtime_plan`, `name_only_outcome` | generator-focused regression과 representative non-SQLi name-only direct rerun에서 primitive/dependency/topology/oracle branch controller가 실제 materialization path를 바꾸는지 확인 |
| `TKT-002` | [docs/code/executor.md](code/executor.md), [docs/code/orchestrator.md](code/orchestrator.md), [docs/code/workspaces.md](code/workspaces.md) | `runtime_graph`, `executor_plan`, `manifest.json`, `artifacts/<SID>/run/summary.json` | single-service와 service-plus-sidecar representative lane에서 graph-first runtime node materialization과 graph/plan precedence가 유지되는지 확인 |
| `TKT-003` | [docs/code/executor.md](code/executor.md), [docs/code/common.md](code/common.md), [docs/code/workspaces.md](code/workspaces.md) | dependency edge, `startup_after`, lifecycle ordering, run/cleanup summary | valid/invalid dependency graph regression과 ordered dependency lane rerun에서 startup/shutdown ordering이 같은 lifecycle rule을 따르는지 확인 |
| `TKT-004` | [docs/code/executor.md](code/executor.md), [docs/code/orchestrator.md](code/orchestrator.md), [docs/code/workspaces.md](code/workspaces.md) | seed/init contract, step result surface, `generator_manifest.json`, run summary | sqlite lane과 sidecar SQL lane representative rerun에서 declarative seed step schema와 step-level result provenance가 남는지 확인 |
| `TKT-005` | [docs/code/executor.md](code/executor.md), [docs/code/common.md](code/common.md), [docs/code/workspaces.md](code/workspaces.md) | `env_contract`, `volume_contract`, `network_contract`, runtime materialization summary | executor/pack/run_case regression과 networked/non-networked lane rerun에서 env-volume-network semantics가 bounded DB lane 밖으로 재사용되는지 확인 |
| `TKT-006` | [docs/code/agents_generator.md](code/agents_generator.md), [docs/code/orchestrator.md](code/orchestrator.md), [docs/code/workspaces.md](code/workspaces.md) | `generator_manifest.json`, `generator_failures.jsonl`, `loop_state.json`, staged intermediate artifacts | semantic-guided dynamic rerun과 generator regression에서 last-good stage persistence, repair-first retry, downgrade journal이 살아 있는지 확인 |
| `TKT-007` | [docs/code/evals.md](code/evals.md), [docs/code/executor.md](code/executor.md), [docs/guardrails_dynamic.md](guardrails_dynamic.md), [docs/code/workspaces.md](code/workspaces.md) | `oracle_execution.json`, `evals.json`, `artifact_quality`, `oracle_execution_parity` | verifier/executor regression과 representative stateful lane rerun에서 single-step과 multi-step replay가 분리되고 realism rubric이 quality tier에 반영되는지 확인 |
| `TKT-008` | [docs/code/evals.md](code/evals.md), [docs/code/workspaces.md](code/workspaces.md), [docs/handbook.md](handbook.md) | `repeatability_report.json`, `matrix_report.json`, `support_candidate.json`, `measured_gate` | `tests/test_repeatability_gate.py`, `tests/e2e/test_case_matrix_rollup.py`, repeatability/matrix/support preview workflow에서 measured gate preview와 authoritative policy split이 일관되게 유지되는지 확인 |
| `TKT-009` | [docs/code/orchestrator.md](code/orchestrator.md), [docs/code/workspaces.md](code/workspaces.md), [docs/handbook.md](handbook.md) | `support_review_index.json`, `support_registry_update.json`, `curated_support_registry.json`, `last_update` | `tests/test_support_extract.py`, `tests/e2e/test_support_workflow.py`, support review/decide/apply chain에서 blocked no-op과 reviewable accept-path가 같은 vocabulary로 materialize되는지 확인 |
| `TKT-010` | [docs/final_solution.md](final_solution.md), [docs/current_state_gap_analysis.md](current_state_gap_analysis.md), [docs/constraints.md](constraints.md) | expansion gate, measurement rubric, runtime/oracle closure precondition | runtime/oracle/eval closure review가 먼저 끝났는지 확인한 뒤 backlog review로만 올린다. direct capability expansion 구현은 선행하지 않는다 |

## Validation Routing

ticket를 실제 검증 하니스와 연결할 때는 아래 순서를 따른다.

| Ticket bucket | Canonical validation doc | First harness / regression surface | Environment note |
| --- | --- | --- | --- |
| `TKT-001` ~ `TKT-007` | [tests/e2e/README.md](../tests/e2e/README.md), [docs/code/README.md](code/README.md) | `tests/e2e/run_case.py`, `tests/e2e/test_cases.py`, subsystem regression listed in code docs | representative executed lane는 Docker가 필요할 수 있다 |
| `TKT-008` | [tests/e2e/README.md](../tests/e2e/README.md), [docs/handbook.md](handbook.md) | `tests/e2e/repeat_case.py`, `tests/e2e/matrix_report.py`, `tests/test_repeatability_gate.py`, `tests/e2e/test_case_matrix_rollup.py` | planning-only lane만으로도 preview/measured gate sanity 일부 확인 가능. latest low-cost pair는 `foobar-name-only-negative` + `open-redirect-strict-dynamic-no-remote`다 |
| `TKT-009` | [tests/e2e/README.md](../tests/e2e/README.md), [docs/handbook.md](handbook.md) | `tests/e2e/support_review.py`, `tests/e2e/support_decide.py`, `tests/e2e/support_apply.py`, `tests/test_support_extract.py`, `tests/e2e/test_support_workflow.py` | current local registry flow는 measured/manual workflow이지 auto-promotion path가 아니다. latest blocked/no-op rehearsal pair는 `foobar-name-only-negative` + `open-redirect-strict-dynamic-no-remote`다 |
| `TKT-010` | [docs/final_solution.md](final_solution.md), [docs/current_state_gap_analysis.md](current_state_gap_analysis.md) | roadmap review, residual review, gate review only | implementation harness보다 readiness review가 먼저다 |

## Validation Reading Order

검증부터 시작할 때의 canonical reading order는 아래와 같다.

1. [docs/work_tickets.md](work_tickets.md)의 `Validation Routing`
2. [tests/e2e/README.md](../tests/e2e/README.md)의 harness command / case layout / ticket mapping
3. [docs/code/README.md](code/README.md)와 subsystem docs의 code entrypoint
4. [docs/handbook.md](handbook.md)의 artifact map / troubleshooting

phase acceptance gate와 validation surface의 대응은 [docs/final_solution.md](final_solution.md)의 `Acceptance-To-Validation Translation`을 같이 본다.

## Priority Reading Order

우선순위 판단부터 시작할 때의 canonical reading order는 아래와 같다.

1. [docs/work_tickets.md](work_tickets.md)의 `Priority Companions`
2. [docs/work_tickets.md](work_tickets.md)의 `Current Remaining Snapshot`, `Confirmed Completion Priority Order`, `Estimated Turn Envelope`
3. [docs/work_tickets.md](work_tickets.md)의 `Current Capability Scorecard`, `Planning Specificity Residual Overlay`, `Evaluation-To-Ticket Breakdown`, `Assessment-To-Ticket Interpretation`, `LLM-Response Capability Overlay`
4. [docs/final_solution.md](final_solution.md)의 `Phase-To-Ticket Translation`, `Acceptance Gates`
5. [docs/current_state_gap_analysis.md](current_state_gap_analysis.md), [docs/constraints.md](constraints.md)
6. [tests/e2e/README.md](../tests/e2e/README.md)의 low-cost preflight / no-Docker rehearsal pair
7. [docs/code/README.md](code/README.md)와 subsystem docs의 code entrypoint
8. [docs/handbook.md](handbook.md)의 troubleshooting / artifact reading hints

## Priority Review Entry

priority 판단은 아래 순서로 시작한다.

1. `Priority Companions`
2. `Priority Question Routing`
3. `Confirmed Completion Priority Order`, `Estimated Turn Envelope`
4. `Current Capability Scorecard`, `Planning Specificity Residual Overlay`, `Evaluation-To-Ticket Breakdown`, `Assessment-To-Ticket Interpretation`, `LLM-Response Capability Overlay`
5. `Priority Reading Order`

## Turn Estimate Entry

잔여 작업량/turn envelope를 representative evidence와 함께 읽고 싶다면 아래 순서를 쓴다.

1. `Estimated Turn Envelope`
2. `Current Capability Scorecard`, `Planning Specificity Residual Overlay`, `Evaluation-To-Ticket Breakdown`, `Assessment-To-Ticket Interpretation`, `LLM-Response Capability Overlay`
3. `Current Remaining Snapshot`, `Confirmed Completion Priority Order`
4. [docs/current_state_gap_analysis.md](current_state_gap_analysis.md), [docs/constraints.md](constraints.md)
5. [tests/e2e/README.md](../tests/e2e/README.md)의 `Positive Pair Promotion Check`

## Turn Estimate Reading Order

작업량 추산부터 시작할 때의 canonical reading order는 아래와 같다.

1. [docs/work_tickets.md](work_tickets.md)의 `Turn Estimate Companions`
2. [docs/work_tickets.md](work_tickets.md)의 `Estimated Turn Envelope`
3. [docs/work_tickets.md](work_tickets.md)의 `Current Capability Scorecard`, `Planning Specificity Residual Overlay`, `Evaluation-To-Ticket Breakdown`, `Assessment-To-Ticket Interpretation`, `LLM-Response Capability Overlay`
4. [docs/work_tickets.md](work_tickets.md)의 `Current Remaining Snapshot`, `Confirmed Completion Priority Order`
5. [docs/current_state_gap_analysis.md](current_state_gap_analysis.md), [docs/constraints.md](constraints.md)
6. [tests/e2e/README.md](../tests/e2e/README.md)의 `Positive Pair Promotion Check`

## Tickets

### TKT-001. Primitive-First Branch Controller

- Priority: `P0`
- Phase mapping: `Phase 2.5 -> Phase 3`
- Status: `ready`
- Problem:
  - current generator는 `design_brief.required_roles`, `dependency_set`, bounded salvage signal을 읽지만 materialization 본체는 아직 `selected family + bounded builder` 중심이다.
- Scope:
  - `primitive -> dependency -> topology -> oracle`를 actual generation branch controller로 승격한다.
  - `family`는 primary builder selector가 아니라 projection/label에 더 가깝게 밀어낸다.
  - `design_brief`, `runtime_plan`, `selection_decision`이 prompt/recovery/guard를 넘어서 candidate generation path를 직접 바꾸게 한다.
  - same selection truth가 어떤 materializer/file/runtime/oracle branch를 열었는지 causal trace로 남겨, selection summary와 actual Docker branch truth를 연결한다.
- Out of scope:
  - arbitrary unknown family discovery
  - non-Python/general multi-runtime expansion
- Exit criteria:
  - representative bounded lane가 family-first builder가 아니라 primitive/dependency/topology decision에서 materialize된다.
  - summary/contract surface가 어떤 controller signal이 선택을 지배했는지 직접 남긴다.
  - selected scenario와 actual materializer/file/runtime/oracle branch의 인과가 machine-readable trace로 남는다.
  - `dependency_db -> sqli` 같은 narrow salvage를 넘는 second family/class example이 생긴다.
- Minimum validation:
  - generator-focused regression
  - representative direct rerun at least one non-SQLi bounded lane
- Active subtask decomposition:
  - `TKT-001-A. Primitive / Dependency / Topology / Oracle IR Promotion`
    - `primitive_hypotheses`, `dependency_set`, `selected_topology`, `selected_oracle_mode`를 prompt summary가 아니라 actual builder input으로 승격한다
    - materialization branch가 family label보다 primitive/dependency/topology/oracle IR를 먼저 읽게 정리한다
  - `TKT-001-B. Scenario-Specific Materializer Branch Split`
    - selected scenario마다 runtime/oracle generation path가 다르게 열리도록 branch split을 정리한다
    - same family 안에서도 topology/dependency/oracle profile에 따라 materially different builder path가 선택되게 만든다
  - `TKT-001-C. Family As Projection Label`
    - family를 builder selector가 아니라 selected scenario를 설명하는 projection label로 축소한다
    - open-vocabulary induction 이전 단계에서도 family-first closure가 아닌 scenario/primitive-first closure에 더 가깝게 이동시킨다
  - `TKT-001-D. Selection Decision As Authoritative Branch Controller`
    - `selection_decision`, `ready_for_materialization`, `open_world_evidence_ready`를 generator가 실제 branching input으로 소비하게 만든다
    - selected scenario/family/stack/oracle truth가 summary가 아니라 materialization path를 직접 바꾸게 정리
  - `TKT-001-E. Partial-Lane Decision State Machine Unification`
    - `planning_focus_summary`, `next_required_step`, `name_only_outcome`를 하나의 partial-lane state machine으로 정리한다
    - compatibility/dynamic/strict_dynamic 사이의 같은 residual wording drift를 줄인다
    - low-cost capability-gate regression pair(`open-redirect-strict-dynamic-no-remote`, `open-redirect-strict-dynamic-stub`)가 둘 다 `fail_closed`를 유지하되 `strict_dynamic_remote_research_unavailable` vs `strict_dynamic_live_llm_unavailable` subclass를 계속 분리해 남기게 고정한다
  - `TKT-001-F. Unresolved-To-Abstain Transition Modeling`
    - ambiguity/evidence-thin/unresolved 상태가 언제 `partial`, `abstain`, `fail_closed`로 넘어가는지 explicit transition rule로 고정한다
    - same transition이 researcher/generator/executor handoff에서 달라지지 않게 한다
  - `TKT-001-G. Evidence Authority Thresholding`
    - lexical support count를 넘어서 scenario selection에 필요한 minimum authority / contradiction threshold를 explicit rule로 정리한다
    - evidence graph를 causal proof로 과장하지 않으면서도 branch controller가 쓸 수 있는 threshold surface를 마련한다
  - `TKT-001-H. Scenario Selection Algebra And Abstain Contract`
    - `scenario_candidates[]`가 단순 field collection이 아니라 `candidate_score`, `contradiction_score`, `evidence_sufficiency`, `selected_by`, `abstain_reason`를 가진 explicit selection algebra를 쓰게 정리한다
    - family/stack/topology/oracle, negative hypothesis, contradiction signal, ambiguous evidence가 같은 selection rule 안에서 tie-break / abstain / fail-closed로 내려가게 고정한다
    - `selected_scenario_id` / `selected_family` / `selected_stack_id`가 populated되어도 `scenario.selected=false`로 남는 current drift를 없애고, same selected payload가 single consistency rule을 따르게 정리한다
    - current bounded closure로는 scenario payload가 `selected_candidate_present`, `selection_state`, `selected_by`, `unresolved_reasons`를 직접 surface하기 시작했고, latest direct rerun 기준 `strict_stub` / `csrf_dynamic`는 `candidate_only + stack_unselected`, `open_redirect_dynamic`는 `selected`로 다시 확인됐다. remaining work는 same state를 scoring/tie-break/abstain algebra까지 끌어올리는 것이다
  - `TKT-001-I. Selection-To-Materialization Causal Trace`
    - `selection_decision`이 어떤 materializer branch, file set, runtime/oracle branch를 실제로 열었는지 machine-readable trace를 남긴다
    - selected candidate와 rejected candidate가 final Docker/materialization path에서 어떤 차이를 만들었는지 summary / generator artifact / measured artifact가 같은 vocabulary로 설명하게 정리한다
    - selection enrichment와 actual branch causality가 operator-facing provenance에서 섞이지 않게 한다
    - latest bounded closure로 `selection_branch_trace@0.1`가 generator contract, single-bundle manifest/direct summary, support candidate/review artifact에 들어가기 시작했고 branch별 `selected_value/materialized_value/aligned`, rejected scenario sample, materialized file/runtime bundle이 now one-shot payload로 읽힌다
    - current residual은 trace 부재가 아니라 same trace가 live-positive proving ground와 실제 branch-controller authority를 얼마나 정직하게 반영하는지다. latest direct rerun 기준 comparator lane에서도 trace는 `branch_aligned=true`로 남지만 generation path는 still `fixture`/`stub`라 stricter claim을 대신하지 않는다

### TKT-002. Runtime Graph / Executor Plan Control-Plane Promotion

- Priority: `P1`
- Phase mapping: `Phase 3C`
- Status: `ready`
- Problem:
  - `runtime_graph`와 `executor_plan`은 bounded fallback input과 provenance surface로는 많이 올라왔지만 아직 authoritative executable control-plane은 아니다.
- Scope:
  - service, sidecar, port, env, healthcheck, seed, volume, network를 graph/plan에서 first-class runtime input으로 정의한다.
  - executor가 manifest metadata와 ad-hoc fallback보다 graph/plan을 우선 소비하게 만든다.
  - current bounded fallback reconstruction을 graph-first execution으로 치환한다.
- Out of scope:
  - arbitrary orchestrator backend 지원
  - cluster-scale scheduling
- Exit criteria:
  - representative single-service lane과 sidecar lane이 graph-first execution으로 돌아간다.
  - graph/plan inconsistency는 runtime 전 early failure로 정리된다.
  - executor summary는 graph/plan provenance를 덜 재합성하고 그대로 보존한다.
- Minimum validation:
  - contract/executor regression
  - representative rerun on single-service and service-plus-sidecar lanes
- Active subtask decomposition:
  - `TKT-002-A. Graph-First Runtime Node Materialization`
    - service/sidecar/env/network/healthcheck/seed surface를 `runtime_graph` / `executor_plan` 기준으로 first-class node/edge input으로 정리
    - actual container materialization이 recipe/metadata fallback보다 graph-defined runtime node를 먼저 읽게 만든다
  - `TKT-002-B. Graph-First Health / PoC Surface Consumption`
    - `service_port`, `base_url`, `healthchecks`, `poc_entry`, `poc_cmd`를 graph/plan canonical surface에서 직접 소비하게 정리
    - readiness / PoC execution / oracle replay가 bundle-scoped execution surface와 같은 canonical input을 재사용하게 만든다
  - `TKT-002-C. Runtime Graph Authoritative Consumption`
    - `runtime_graph`가 summary surface를 넘어서 executor의 primary canonical input이 되게 만든다
    - recipe/metadata hint fallback보다 graph/plan precedence를 먼저 읽게 정리한다
  - `TKT-002-D. Representative Topology Class Ladder`
    - generalized runtime closure를 추상 문구가 아니라 `service_only`, `service_plus_db`, `service_plus_supporting_sidecar`, `multi_primary_web_pair`, `browserful_lab_topology` 같은 proving-ground topology class ladder로 정리한다
    - 각 topology class마다 required runtime contract, first validation lane, remaining blocker를 같이 남겨 Phase 3C closure를 단계적으로 읽을 수 있게 만든다
    - current directly verified comparator는 `open-redirect-dynamic-name-only` / `csrf-dynamic-name-only`의 `service_only`와 `sqli-sidecar-compiler-custom-env`의 `service_plus_sidecar`로 고정하고, unsupported class는 explicit future proving ground로 남긴다
    - same ladder는 generation path claim과도 분리해, `fixture-backed`, `degraded fallback`, future `live name-only positive`가 같은 topology rung에 있더라도 같은 capability claim으로 섞이지 않게 한다

### TKT-003. Generalized Dependency Ordering And Lifecycle

- Priority: `P1`
- Phase mapping: `Phase 3C`
- Status: `ready`
- Problem:
  - current dependency ordering은 bounded sidecar lane에서 `startup_order_index`/`startup_after`를 일부 읽고 cycle/error를 early-fail시키는 정도다.
- Scope:
  - generalized topological ordering을 service/sidecar/runtime dependency graph에 적용한다.
  - startup order와 shutdown order를 같은 contract surface로 설명한다.
  - dependency graph malformed reference, cycle, missing dependency를 runtime 전 consistently fail-fast 한다.
  - bounded sidecar order를 넘어서 lifecycle sequencing을 executor semantics로 올린다.
- Out of scope:
  - distributed systems orchestration
  - async repair/retry policy
- Exit criteria:
  - order derivation이 bounded DB sidecar lane 밖의 representative lane에도 적용된다.
  - shutdown/cleanup order까지 contract로 설명된다.
  - executor가 ad-hoc start order fallback보다 declared dependency graph를 우선 읽는다.
- Minimum validation:
  - executor regression for valid/invalid graph shapes
  - representative rerun with ordered dependency lane
- Active subtask decomposition:
  - `TKT-003-A. Startup Order Derivation And Validation`
    - `startup_order_index`, `startup_after`, declared dependency edge를 하나의 startup ordering rule로 정리한다
    - malformed reference, unknown dependency, cyclic graph를 runtime 전 fail-fast 하도록 고정한다
  - `TKT-003-B. Shutdown / Cleanup Lifecycle Semantics`
    - reverse teardown, cleanup ordering, sidecar/network/resource release semantics를 same lifecycle contract로 정리한다
    - startup과 shutdown이 서로 다른 ad-hoc rule이 아니라 single dependency/lifecycle model로 읽히게 만든다

### TKT-004. Generalized Seed / Init DSL

- Priority: `P1`
- Phase mapping: `Phase 3C`
- Status: `ready`
- Problem:
  - current seed/init은 `sqlite_service_init`, `sidecar_sql_apply`, seed file existence, minimal init signal validation 같은 bounded pattern에 머문다.
- Scope:
  - service init, sidecar SQL apply, ordered seed steps를 설명하는 declarative DSL을 정의한다.
  - seed file, mount target, apply target, ordering, required runtime dependency를 하나의 contract로 정리한다.
  - executor가 declared step을 실행하고 결과를 summary에 남기게 한다.
- Out of scope:
  - arbitrary shell script execution
  - generalized migration framework support
- Exit criteria:
  - sqlite lane과 external DB lane이 같은 DSL family로 설명된다.
  - seed/init success/failure가 contract step 단위로 summary에 남는다.
  - current bounded `seed_strategy` split이 generalized step model로 대체된다.
- Minimum validation:
  - contract/executor regression
  - representative rerun on sqlite lane and sidecar SQL lane
- Current bounded closure already achieved:
  - `sqlite_service_init` vs non-sqlite/sidecar runtime mismatch detection
  - `sidecar_sql_apply` requires `.sql` seed files
  - `sidecar_sql_apply` requires actual SQL-capable sidecar entry and no longer accepts DB family hint alone as sufficient target evidence
  - `sidecar_sql_apply` rejects multiple SQL family ambiguity across sidecar targets
  - sqlite minimal init signal validation and bounded external DB SQL seed apply result surface
- Active subtask decomposition:
  - `TKT-004-A. Declarative Seed Step Schema`
    - `sqlite_service_init` and `sidecar_sql_apply`를 single step family가 아니라 reusable step graph로 재설계
    - step ordering, runtime dependency, input artifact, target node를 explicit schema로 올림
  - `TKT-004-B. Seed Result Surface And Replay`
    - step 단위 success/failure/result provenance를 summary와 measured artifact에 남김
    - bounded SQL apply/SQLite init signal을 넘어 reusable seed replay semantics를 정의

### TKT-005. Generalized Env / Volume / Network Contract Semantics

- Priority: `P1`
- Phase mapping: `Phase 3C`
- Status: `ready`
- Problem:
  - current env/volume/network contract는 bounded external-DB lane self-consistency hardening은 강하지만 generalized semantics는 아니다.
- Scope:
  - service/sidecar env binding, mount contract, alias binding, network enable/mode/lifecycle를 generalized contract surface로 정리한다.
  - executor가 contract semantics를 actual runtime materialization에 직접 반영하게 한다.
  - bounded mysql/postgres lane에서만 strong했던 env/volume/network validation을 reusable class로 끌어올린다.
- Out of scope:
  - arbitrary external network topologies
  - non-local volume provider support
- Exit criteria:
  - current DB lane-specific env/host/port credential drift gate가 broader representative runtime class에 재사용된다.
  - custom mount target과 alias binding이 bounded exception이 아니라 general contract feature로 설명된다.
  - network lifecycle가 enable/mode flag를 넘는 runtime behavior surface로 남는다.
- Minimum validation:
  - executor/pack/run_case regression
  - representative rerun covering networked and non-networked lanes
- Current bounded closure already achieved:
  - `env_contract` conflicting value duplicate, unsupported scope, service/sidecar drift detection
  - `volume_contract` unsupported scope, unsupported source, conflicting mount definition, ambiguous seed mount target detection
  - `network_contract` conflicting service alias, unresolved service alias, unsupported scope, alias-vs-target drift detection
  - sidecar identity/runtime/probe, service endpoint, `service_entry`, `poc_entry`, `poc_cmd`, workspace-path self-consistency gates
- Active subtask decomposition:
  - `TKT-005-A. Env Contract Class Generalization`
    - DB lane-specific env drift gate를 broader runtime classes로 일반화
    - `service`/`sidecar:*` 외의 future scope schema를 explicit contract로 정의
    - env provenance와 runtime override precedence를 reusable class semantics로 정리
  - `TKT-005-B. Volume Contract Class Generalization`
    - seed mount 중심 volume semantics를 broader mount lifecycle로 확장
    - mount intent, mount source class, cleanup semantics를 runtime class 전반으로 일반화
    - actual mount result surface를 representative non-seed lane까지 확장
  - `TKT-005-C. Network Lifecycle Class Generalization`
    - alias binding을 넘는 connect/disconnect/lifecycle semantics를 정의
    - named network allocation/cleanup을 contract-driven behavior로 승격
    - service binding과 sidecar identity를 broader topology class에 재사용

### TKT-006. Stage-Resumable Synthesis And One-Shot Reduction

- Priority: `P2`
- Phase mapping: `Phase 2 / Phase 2.5`
- Status: `ready`
- Problem:
  - typed staged surface는 생겼지만 synthesis 본체는 아직 final manifest one-shot 의존이 크고 malformed intermediate를 오래 살리지 못한다.
- Scope:
  - `candidate_resolution -> design_brief -> runtime_plan -> executor_plan -> oracle_contract -> file_manifest`를 resumable하게 만든다.
  - stage별 repair/retry를 generic deterministic fallback보다 먼저 쓰게 만든다.
  - intermediate persistence와 stage-specific recovery provenance를 강화한다.
  - `file_manifest`를 typed build-ready contract로 다뤄 workspace file set과 Docker build context를 explicit하게 검증한다.
  - live/dynamic Docker materialization에 적용할 build-time safety policy를 explicit하게 fail-closed 한다.
- Out of scope:
  - fully autonomous open-world self-repair
  - arbitrary external tool orchestration
- Exit criteria:
  - malformed intermediate가 곧장 final fallback으로 무너지지 않는다.
  - recovery path가 어떤 stage artifact를 어떻게 보정했는지 summary에 남는다.
  - representative dynamic lane에서 deterministic fallback 진입 전 typed repair가 measurable하게 늘어난다.
  - `file_manifest`가 workspace artifact와 build-stage provenance를 같이 남겨 "manifest exists"와 "build-ready Docker bundle"이 다시 섞이지 않는다.
- Minimum validation:
  - generator regression
  - representative rerun on semantic-guided dynamic lane
- Active subtask decomposition:
  - `TKT-006-A. Stage Artifact Persistence And Resumable Retry`
    - `candidate_resolution`, `design_brief`, `runtime_plan`, `executor_plan`, `oracle_contract`의 last-good artifact를 persist하고 retry가 그 지점부터 재개되게 만든다
    - malformed intermediate가 있어도 validated stage output은 보존돼 subsequent repair input으로 재사용되게 정리한다
  - `TKT-006-B. Repair-First Generation Path Control`
    - stage-specific repair / retry / abort policy를 deterministic fallback보다 앞세우는 generation path control을 정리한다
    - `runtime_plan` failure와 `oracle_contract` failure가 generic fallback으로 바로 합쳐지지 않게 좁힌다
  - `TKT-006-C. Stage Failure Journaling And Downgrade Policy`
    - 어떤 stage/validator/abort policy 때문에 downgrade/fallback이 일어났는지 explicit journal을 남긴다
    - malformed intermediate가 즉시 one-shot fallback으로 붕괴하지 않도록 stage-aware downgrade policy를 더 좁힌다
  - `TKT-006-D. Live LLM Materialization Contract And Provenance`
    - `live`, `fixture`, `stub`, `degraded` generation path를 별도 provider/materialization contract로 나누고 `provider_kind`, `model`, `prompt_version`, `decoding_profile`, `retry_budget`, `timeout_budget`, `cost_budget`, `cache_mode`를 machine-readable provenance로 남긴다
    - strict stub honesty lane와 live-positive materialization lane가 서로 다른 acceptance surface를 쓰도록 고정하고, representative positive lane에서 “LLM-shaped”와 “live LLM-positive”를 구분해 읽게 만든다
    - latest direct run의 `trusted-dynamic-sqli -> llm_fixture/llm_manifest`를 proving-ground baseline으로 삼아, fixture-backed positive와 true live-positive의 acceptance boundary를 explicit하게 남긴다
    - current bounded closure already achieved:
      - `LLMClient.execution_summary(...)`가 landed되어 researcher/generator/template/contract가 공통 `llm_execution` vocabulary를 쓰기 시작했다
      - same additive surface는 `provider_backend`, `model`, `decoding_profile`, `path_class`, `fixture_path`, `last_error_retryable`, `prompt_contracts`, `prompt_invocations`, `retry_budget`, `timeout_budget`, `cost_budget`, `cache_mode`를 machine-readable provenance로 남긴다
      - latest direct rerun 기준 `open-redirect-dynamic-name-only`는 `generator_manifest.json` / `resolved_contract.json`에서 `path_class=stub`, actual `prompt_contracts=[synthesis_manifest, dep_guard_inference, guard_autofix]`, `prompt_invocations={synthesis_manifest:1, dep_guard_inference:3, guard_autofix:2}`, `retry_budget={candidate_budget=1, guard_autofix_max_attempts=1, actual_candidate_runs=1}`, `last_error_class=provider_disabled`로 읽힌다
      - same rerun 기준 `researcher_report.json`도 `cache_mode=search_cache_read_write`, actual `prompt_contracts=[researcher_report, guard_planner]`, `retry_budget={controller_loop_current=1, controller_loop_max=3, guard_planner_planned_runs=1, guard_planner_actual_runs=1}`로 읽힌다
      - same rerun 기준 `generator_manifest.json`도 same `retry_budget` 안에 `controller_loop_current/max`, `single_attempt_mode`, `planned_candidate_budget`를 같이 남겨 stage-local budget과 controller budget이 분리되지 않게 읽힌다
      - latest bounded closure로 single-bundle `manifest.json`, direct `summary.json`, `support_candidate.json`, `support_review_index.json`도 `generation_materialization@0.1`을 surface하기 시작했다. same payload는 `generation_origin`, `materializer`, `path_class`, provider attempt/success, fixture/stub flag, provider/model/cache/prompt/retry/timeout/cost surface를 one-shot contract로 남긴다
      - latest direct rerun 기준 `open-redirect-dynamic-name-only`의 direct `summary.json`도 now `support_promotion.reasons += generation_path:not_live_positive`, `open_world_readiness.blockers += generation_path_not_live_positive`를 남긴다. 따라서 measured/support chain을 열지 않아도 non-live materialization mismatch를 top-level policy wording에서 바로 읽을 수 있다
      - latest direct rerun 기준 same lane은 same direct policy surface에서 `generation_path:provider_disabled` / `generation_path_provider_disabled`까지 같이 남기므로, non-live mismatch가 generic wording에 머물지 않고 actionable provider-disabled subclass로 읽힌다
      - latest support-flow closure로 `support_review_index.json`, `support_registry_update.json`, `curated_support_registry.json:last_update`도 `by_generation_non_live_reason` aggregate를 같이 보존한다. 따라서 `trusted-dynamic-sqli -> fixture_backed`, `open-redirect-dynamic-name-only -> provider_disabled` 같은 why-not-live subtype이 blocked no-op apply에서도 사라지지 않는다
      - latest direct rerun with `VUL_LLM_TIMEOUT_S=9.5` 기준 `open-redirect-dynamic-name-only`는 `researcher_report.json`에서 `timeout_budget={llm_request_timeout_s=9.5, search_timeout_s=8.0}`, `generator_manifest.json`에서 `timeout_budget={llm_request_timeout_s=9.5}`로 읽힌다
      - latest direct rerun with `VUL_LLM_COST_BUDGET_USD=0.25` 기준 same lane은 `researcher_report.json` / `generator_manifest.json` 모두 `cost_budget={configured_cost_budget_usd=0.25}`를 남긴다. unit closure 기준 provider success path에서는 same `cost_budget`에 `usage_tokens={prompt_tokens, completion_tokens, total_tokens}`, `usage_scope={last_call|observed}`, `estimated_cost_usd`, `pricing_model`, `pricing_basis`, `pricing_source=litellm_cost_map`도 포함된다
      - same direct rerun 기준 top-level `manifest.json` / direct `summary.json`도 `research_retry_budget`, `research_timeout_budget`, `research_cost_budget`, `generation_retry_budget`, `generation_timeout_budget`, `generation_cost_budget`, `reviewer_retry_budget`, `reviewer_timeout_budget`, `reviewer_cost_budget` convenience field를 같이 노출해 nested metadata를 열지 않고도 operator가 stage budget surface를 읽을 수 있다
      - same rerun 기준 `sqli-sidecar-template`는 `generator_template.json` / `resolved_contract.json`에서 `path_class=not_executed`, `cache_mode=none`이며 no-op lane이라 `prompt_contracts` / `retry_budget`를 강제로 남기지 않는다. 다만 unit closure 기준 `generator_plan`이 실제로 호출된 template lane에서는 `retry_budget={controller_loop_current/max, single_attempt_mode, template_plan_actual_runs, template_selection_candidate_budget}`가 surfaced된다
      - reviewer도 same `llm_execution` / actual prompt tracking surface를 공유한다. unit closure 기준 feedback-enabled lane에서는 `retry_budget={controller_loop_current/max, reviewer_feedback_runs}`가 surfaced되고, latest direct rerun의 `open-redirect-dynamic-name-only` reviewer lane은 clean/no-op path라 `path_class=not_executed`, `cache_mode=none`만 남는다
    - remaining residual after current closure:
      - `timeout_budget`은 search timeout과 configured LLM timeout 기준으로 partial closure가 생겼지만, stage-wide default/provider policy timeout contract로 fully unify되지는 않았다
      - `cost_budget`은 configured USD budget, observed usage token, and litellm cost-map-based conservative dollar estimate 기준으로 partial closure가 생겼지만, promotion-quality cost policy나 provider/version drift-aware pricing governance까지는 닫히지 않았다
      - `retry_budget`는 now controller-loop/generator/researcher/reviewer/template-plan까지 partial closure가 생겼지만, true live-positive path와 cost/timeout-aware provider budget까지 fully unify되지는 않았다
      - first true live-positive proving-ground lane는 아직 없고, current positive control은 여전히 fixture-backed 또는 degraded/stub lane에 가깝다
  - `TKT-006-E. Build-Ready File Manifest Contract And Build Taxonomy`
    - `file_manifest` stage를 workspace artifact set(`Dockerfile`, dependency manifest, service entry, PoC entry, seed/init assets)과 build context contract로 typed schema/validator에 올린다
    - build failure를 syntax/build-context/dependency/image/runtime-contract mismatch 같은 explicit taxonomy로 나누고 `build.log` / SBOM / manifest provenance와 연결한다
    - `trusted-dynamic-sqli`, representative dynamic lane, comparator sidecar lane가 같은 build-ready vocabulary를 쓰게 만들어 actual Docker materialization claim을 더 직접 읽게 한다
    - current direct rerun 기준 representative lane의 `staged_synthesis.stage_order`가 아직 `oracle_contract`에서 멈추고, actual `artifacts/<sid>/build/build.log` / `image_id.txt`가 있어도 manifest/summary `build_log` / `image_tag`가 null일 수 있었으므로, same roundtrip gap을 direct burn-down target으로 유지한다
    - current bounded closure already achieved:
      - `staged_synthesis.stage_order`가 `executor_plan`, `file_manifest`까지 surface되고, same stage가 executor-facing surface와 build-ready file set(`Dockerfile`, dependency manifest, service/PoC entry) 요약을 같이 남긴다
      - same `file_manifest`는 now `build_ready`, `build_ready_blockers`, `dockerfile_base_images`, `package_installers_detected`, `build_safety_policy(policy_version=docker_build_safety@0.1)`도 같이 남긴다. current policy는 remote fetch in build와 `/tmp/*.db|sqlite*` artifact 생성을 blocker로, unpinned/latest base image와 final `USER root`를 warning으로 먼저 surface한다
      - same build-ready/build-safety surface는 now `support_promotion.reasons += build_ready:*|build_safety:*`, `open_world_readiness.blockers += build_*`, `support_candidate.build_contract`까지 직접 연결된다. therefore measured/support lane에서도 “Docker bundle이 buildable한가”와 “still promotable/reviewable한가”를 같은 vocabulary family 안에서 분리해 읽을 수 있다
      - same support extraction은 now stale/thin `support_promotion.reasons`에만 의존하지 않고 `support_candidate.build_contract`에서 build blocker를 재구성하며, `selection_evidence` / `stack_selection` / `name_only_outcome` 같은 open-world policy token도 `promotion_policy_blockers` aggregate로 바로 남긴다
      - same `support_review_index.json` / `support_registry_update.json` preview도 now `build_ready_bundle_count`, `build_not_ready_bundle_count`, `build_safety_safe_bundle_count`, `build_safety_blocked_bundle_count`, `by_build_ready_blocker`, `by_build_safety_blocker`를 같이 보존한다. therefore queue-level aggregate에서도 “buildable but not promotable”와 “not build-ready”를 직접 분리해 읽을 수 있다
      - same local registry apply guard도 now explicit `generation_path_live_positive_ready=false` 또는 `generation_path_class!=live`, `mechanically_healthy=false`, `promotion_policy_ready=false`, `build_ready=false`, `build_safety_safe=false` accepted entry를 fail-closed 한다. therefore stale/manual accept path가 non-live/build/policy-unready candidate를 local curated registry에 올리는 drift도 줄었다
      - representative direct rerun 기준 single-bundle `manifest.json` / `summary.json`도 actual `image_tag`, `build_log`, `run_log`, optional `sbom_path` pointer를 다시 surface한다
      - remaining residual은 build failure taxonomy를 broader lane에 일반화하는 것과, optional SBOM/image metadata path를 authoritative measured/support surface까지 더 일관되게 handoff하는 것이다
  - `TKT-006-F. Build-Time Docker Safety Policy`
    - live/dynamic `file_manifest`에 적용할 Dockerfile instruction, base image, package/dependency install, build-stage network usage policy를 explicit하게 정리한다
    - policy 위반이 runtime isolation과 섞이지 않도록 build-stage rejection surface와 failure class를 따로 남긴다
    - same policy가 fixture/stub/degraded/live path 모두에 어떤 수준으로 적용되는지 measured/support interpretation과도 맞춘다

### TKT-007. Browserful / Multi-Step Stateful Oracle Replay

- Priority: `P3`
- Phase mapping: `Phase 4`
- Status: `ready`
- Problem:
  - representative stateless/body-structured/sessionful single-flow lane은 많이 닫혔지만 broader browserful multi-step state transition oracle은 아직 아니다.
- Scope:
  - cookie/session/token/redirect chain을 포함하는 multi-step replay contract를 정의한다.
  - browserful or client-stateful oracle execution path를 최소 representative lane에 도입한다.
  - richer realism rubric을 `artifact_quality`에 연결한다.
- Out of scope:
  - full browser automation across arbitrary apps
  - generalized human-like interaction modeling
- Exit criteria:
  - representative broader stateful lane가 `oracle_execution_parity=high`에 도달한다.
  - single-step payload replay와 multi-step stateful replay가 summary에서 구분된다.
  - stateful oracle richness가 quality band에 실제 반영된다.
- Minimum validation:
  - verifier/executor regression
  - representative direct rerun on stateful lane
- Active subtask decomposition:
  - `TKT-007-A. Browserful / Sessionful Multi-Step Replay`
    - cookie/session/token/redirect/form submission을 포함하는 multi-step replay contract를 representative lane에 도입한다
    - single payload replay와 state-transition replay가 summary / measured artifact에서 분리되게 정리한다
  - `TKT-007-B. Realism Rubric Integration`
    - browserful/stateful oracle richness를 `artifact_quality` qualitative tier와 연결한다
    - runnable success와 lab realism을 구분하는 rubric이 measured/support gate까지 이어지게 정리한다
  - `TKT-007-C. Realism Rubric Operationalization`
    - `exploit_path_diversity`, `statefulness`, `victim_realism`, `environment_fidelity`, `verifier_independence`, `cleanup_reproducibility` 같은 explicit rubric axis와 threshold를 정의한다
    - same rubric이 `artifact_quality`, `measured_gate`, `support_review`에서 서로 다른 해석을 쓰지 않도록 canonical quality contract로 승격한다
    - current directly verified `csrf-dynamic-name-only`를 sessionful single-flow comparator로 고정하고, browserful/state-transition proving ground와 구분해 rubric threshold를 설계한다

### TKT-008. Authoritative Measurement Gate Closure

- Priority: `P4`
- Phase mapping: `Phase 5B`
- Status: `ready`
- Problem:
  - matrix, repeatability, quality tier, summary consistency는 많이 좋아졌지만 아직 authoritative regression gate는 아니다.
- Scope:
  - snippet/evidence reuse와 representative perf comparison을 measured artifact에 연결한다.
  - CI-level matrix/perf gate를 강화한다.
  - `planning_only`/pre-generation lane과 multi-bundle convenience projection의 summary consistency residual을 더 줄인다.
  - quality tier and oracle parity distinction을 gate condition으로 명시한다.
  - `live` / `fixture` / `stub` / `degraded` generation path를 measured gate의 explicit axis로 승격한다.
- Out of scope:
  - external benchmark leaderboard
  - generalized capability claim automation
- Exit criteria:
  - representative measured lane가 stable quality/perf buckets로 비교된다.
  - gate가 `oracle_execution_parity=high`와 `artifact_quality.band=high`를 계속 분리한다.
  - remaining summary drift가 known documented exception 수준으로 줄어든다.
  - measured artifact가 `LLM-shaped positive`, `true live-positive`, `degraded fallback positive`를 같은 bucket으로 섞지 않는다.
- Minimum validation:
  - matrix/repeatability/pack regression
  - representative rerun of executed lane and planning-only lane
- Current bounded closure already achieved:
  - representative executed single-bundle lane의 core verdict sync
  - `planning_only`, `bounded_sidecar_parity_success`, `thin_fallback_demo` quality tier 구분
  - top-level runtime fact/provenance flattening
  - multi-bundle top-level `bundle_verdict_rollup` convenience projection
  - same rollup의 `by_stage_ceiling` / `by_terminal_failure_class` breakdown
  - uniform multi-bundle `run_passed` / `verify_pass` / `stage_ceiling` / `terminal_failure_class` / `oracle_execution_*` top-level projection
  - mixed multi-bundle `run_passed_rollup` / `verify_pass_rollup` / `stage_ceiling_rollup` / `terminal_failure_class_rollup` / `oracle_execution_*_rollup` token surface
  - top-level `verdict_authority` surface로 convenience projection과 nested bundle truth precedence explicit화
  - repeatability/matrix artifact의 `verdict_authority` observation surface
  - support candidate/review index의 `verdict_authority` handoff surface
  - support candidate external blocker로 `verdict_authority:missing/inconsistent` 도입
  - support review index의 `authority_ready_bundle_count` / `authority_blocked_bundle_count` / `by_authority_blocker` aggregate
  - support registry update preview의 authority aggregate / authority-mode breakdown preservation
  - `run_case` / `repeat_case` output-dir/attempt 기반 SID isolation으로 same-case concurrent artifact contention 완화
  - `repeatability_report.json` / `matrix_report.json`의 `measured_gate` preview와 support external blocker 연결
  - support review index / registry update preview의 `measured_gate_ready_bundle_count` / `measured_gate_blocked_bundle_count` / `by_measured_gate_blocker` aggregate
  - `summarize_repeat_attempt(...)` helper backward-compat 복구로 direct helper/test call shape와 actual repeat gate path를 다시 정렬
  - `_write_plan(..., sid_salt=...)` 도입 이후 older stub/test double path를 깨지 않도록 compatibility seam 복구
  - `repeatability_report.json` top-level `case`와 `case_name`를 함께 남겨 operator-facing report key parity 복구
  - undeclared case repeatability fallback도 `matrix_unavailable_reason`와 support gate의 `matrix_gate:unavailable`로 `not_covered`와 구분되게 정렬
  - latest direct verification 기준 representative sidecar lane도 `measured_gate:cache_reuse_inconsistent`와 curated-lower-bound/open-world blockers 때문에 support reviewable path로는 승격되지 않음을 확인
  - support candidate / review index / registry update preview에 `mechanically_healthy` vs `promotion_policy_ready` blocker split surface 도입
  - same support workflow에 `support_status` / `by_support_status` token surface 도입
  - same `support_review_index.json`에 `by_case_status` / `case_statuses[]` case-level aggregate 추가
  - same `support_registry_update.json` preview와 `support_decide.py` CLI output도 `by_case_status`를 보존
  - same preview CLI output도 `all_reviewable_cases` / `mixed_cases` / `all_blocked_cases` explicit case list를 노출
  - representative sidecar support rerun 기준 `support_review_index.json`가 `by_support_status={"blocked_mixed":1}`와 separated `by_mechanical_blocker` / `by_promotion_policy_blocker`를 남기는 것까지 direct verification
  - planning-only pair direct verification(`foobar-name-only-negative`, `open-redirect-strict-dynamic-no-remote`)에서도 `authority_ready_bundle_count=2`, `measured_gate_blocked_bundle_count=2`, `reviewable_bundle_count=0`, `by_support_status={"blocked_mixed":2}`로 authority handoff와 measured/promotion gate split이 계속 분리된다는 것까지 direct verification
- Active subtask decomposition:
  - `TKT-008-A. Authoritative Measured Gate`
    - snippet/evidence reuse와 representative perf comparison을 measured gate에 연결
    - CI-level matrix/perf gate를 explicit regression policy로 승격
    - representative high-quality lane의 `cache_reuse_inconsistent` 같은 blocker를 줄이거나, 어떤 blocker가 “promotion-blocking but mechanically healthy”인지 gate policy를 더 선명하게 분리
    - `TKT-008-A1. Blocker Policy Split`
      - representative high-quality lane가 `strict_curated_lower_bound` / `catalog_resolved_lower_bound` / `cache_reuse_inconsistent` 때문에 support reviewable path로 떨어질 때, 어떤 blocker가 capability truth이고 어떤 blocker가 promotion policy인지 gate surface를 더 선명하게 분리
      - measured gate preview가 “mechanically healthy but intentionally non-promotable” 상태를 명시적으로 표현하게 정리
      - same split을 `support_candidate.json` / `support_review_index.json` / `support_registry_update.json` aggregate까지 이어서 operator가 blocker class를 top-level에서 직접 읽을 수 있게 정리
      - `reviewable`, `mechanically_blocked`, `mechanically_healthy_policy_blocked`, `blocked_mixed` 같은 status token으로 current promotion state를 더 직접 노출
      - `support_review_index.json`의 `by_case_status` / `case_statuses[]`를 통해 bundle-level status를 case-level reviewability state로도 읽을 수 있게 정리
      - same case-level aggregate를 `support_registry_update.json` preview와 decision CLI output까지 이어서 review 단계에서도 유지
      - same preview CLI output도 explicit case list를 같이 노출해 operator가 preview JSON을 열지 않고도 case-level 상태를 읽게 정리
      - representative direct rerun에서 actual `blocked_mixed` lane를 지속적으로 재검증
      - low-cost no-Docker planning-only pair(`foobar-name-only-negative`, `open-redirect-strict-dynamic-no-remote`)를 authority-ready-but-measured-blocked regression pair로 고정해, `verdict_authority_ready=true`가 곧 reviewable/promotable candidate를 뜻하지 않는다는 current policy를 계속 확인
    - `TKT-008-A2. Authoritative CI / Measured Gate`
      - current preview/enforcement bridge를 CI-level authoritative measured gate로 승격
      - `snippet/evidence reuse`, representative perf comparison, blocker precedence를 explicit regression policy로 연결
    - `TKT-008-A3. Generation-Path Axis And Live-Positive Measurement`
      - matrix / repeatability / measured gate가 `live`, `fixture`, `stub`, `degraded` generation path를 explicit axis와 blocker vocabulary로 읽게 정리
      - same axis가 representative positive lane에서 `LLM-shaped`, `live LLM-positive`, `fallback demo`를 separate acceptance rule로 다루게 만든다
      - existing comparator lane(`trusted-dynamic-sqli`, `open-redirect-dynamic-name-only`)와 future live-name-only proving ground를 같은 measured vocabulary로 비교 가능하게 정리한다
      - latest bounded closure로 `summary.json -> repeatability_report.json -> matrix_report.json -> support_review_index.json` chain도 `generation_path_class`, `generation_path_observations`, `generation_path_gate`, `by_generation_path_class`, `by_generation_positive_bucket`, `live_positive_ready_bundle_count`를 surface하기 시작했다
      - latest measured closure로 same chain은 `generation_non_live_reason`, `observed_generation_non_live_reasons`, `primary_non_live_reason`, `by_non_live_reason`, `by_primary_non_live_reason`도 같이 보존한다. 따라서 comparator pair의 why-not-live subtype(`trusted-dynamic-sqli -> fixture_backed`, `open-redirect-dynamic-name-only -> provider_disabled`)이 repeatability/matrix 단계에서도 support workflow와 같은 vocabulary로 읽힌다
      - latest Docker-enabled rerun 기준 same comparator pair는 now explicit하게 `trusted-dynamic-sqli -> fixture_backed_positive`, `open-redirect-dynamic-name-only -> degraded_fallback_positive`로 다시 읽히고, 둘 다 `measured_gate:generation_path_not_live_positive`와 `live_positive_ready=false`로 support review에서 blocked된다. 따라서 same ticket의 remaining residual은 instrumentation 부재가 아니라 actual live-positive proving-ground lane 부재다
  - `TKT-008-B. Residual Summary Consistency`
    - mixed multi-bundle aggregate/top-level projection consistency 정리
    - convenience projection과 authoritative measured gate 사이의 remaining drift 축소
    - `TKT-008-B1. Mixed Multi-Bundle Projection Consistency`
      - mixed multi-bundle lane에서 top-level convenience projection이 어떤 verdict/failure truth까지 직접 싣고 어떤 것은 rollup으로만 남길지 정리
      - `bundle_verdict_rollup`와 top-level `run_passed/verify_pass/stage_ceiling/terminal_failure_class`의 precedence를 명시
    - `TKT-008-B2. Authoritative Gate Handoff`
      - top-level convenience summary와 nested bundle truth 중 무엇이 measured gate의 canonical input인지 명시
      - convenience projection residual을 measured gate/CI policy와 분리해, operator summary drift가 곧 gate drift로 읽히지 않게 정리
      - `verdict_authority` 같은 explicit precedence surface를 operator summary와 measured artifact에 연결
    - `TKT-008-B3. Repeatability Surface Contract Stabilization`
      - `summarize_repeat_attempt(case_name, matrix_axes)` helper contract와 existing test/helper call shape를 다시 정렬
      - `_write_plan(..., sid_salt=...)` 도입 이후 older stub/test double contract를 깨지 않도록 compatibility seam을 정리
      - `repeatability_report.json` top-level `case` vs `case_name` drift를 정리해 operator-facing report key를 self-consistent하게 만든다
      - `2026-03-19` workspace-local direct verification에서 no-Docker repeatability CLI path는 still working했지만, same helper/report contract drift 때문에 unit slice가 red라는 점을 기준으로 close 여부를 판단한다
      - `TKT-008-B3-A. Repeat Helper Backward-Compat Arguments`
        - `summarize_repeat_attempt(...)`에 새 필드가 추가돼도 기존 helper/test call shape가 hard-fail하지 않도록 defaulting 또는 compatibility wrapper를 정리
        - direct helper call과 actual `execute_repeat_gate(...)` call path가 같은 report truth를 만들도록 맞춘다
      - `TKT-008-B3-B. Plan Writer SID-Salt Compatibility Seam`
        - `_write_plan(..., sid_salt=...)` 도입 이후 older stub/test double이 깨지지 않도록 call seam을 정리
        - same seam이 실제 output-dir/attempt 기반 SID isolation을 유지하면서도 unit/mock path를 깨지 않도록 regression으로 고정
      - `TKT-008-B3-C. Repeatability Report Top-Level Case Key Parity`
        - `aggregate_repeat_results(...)`의 top-level `case` / `case_name` projection을 하나의 operator-facing contract로 정리
        - produced `repeatability_report.json`와 downstream consumer/support extraction expectation이 같은 key를 읽도록 정렬

### TKT-009. Curated Registry Write / Merge Closure

- Priority: `P5`
- Phase mapping: `Phase 6B`
- Status: `ready`
- Problem:
  - measured/manual review surface는 있지만 actual curated registry write/merge workflow는 없다.
- Scope:
  - accepted candidate를 registry schema로 write/merge한다.
  - review decision, provenance, update history를 기록한다.
  - manual preview artifact를 reusable support workflow로 승격한다.
- Out of scope:
  - auto-accept promotion
  - registry-backed generalized support claim widening
- Exit criteria:
  - accept/reject 결과가 registry에 materialize된다.
  - provenance/history가 registry item과 같이 남는다.
  - repeatability-measured lane에서 manual preview가 actual update workflow로 이어진다.
- Minimum validation:
  - support workflow regression
  - representative measured case end-to-end update rehearsal
- Current bounded closure already achieved:
  - `support_registry_update.json` preview를 actual `curated_support_registry.json` local write/merge로 적용하는 최소 workflow
  - accepted entry upsert와 reject decision history persistence
  - existing registry item에 대한 reject decision도 item-level history / `last_decision` / `rejected_count`로 반영
  - prior rejected item이 later accept될 때도 `rejected_count`와 full history를 잃지 않도록 preserve
  - sparse accepted/rejected update가 prior `source_artifacts`는 유지하면서 current support-status split은 reviewable semantics로 채움
  - sparse older registry item도 `history`와 last event를 읽어 `accepted_count` / `rejected_count` / `review_status` / `support_status` / `last_decision` / `source_artifacts`를 current schema로 backfill
  - local registry item의 current `review_status`와 top-level `by_review_status` aggregate
  - local registry item의 latest `source_artifacts`와 top-level `items_with_source_artifacts_count`
  - local registry top-level `schema_upgraded_item_count`, `by_schema_upgrade_reason`와 item-level `schema_upgrade_applied`, `schema_upgrade_reasons`
  - sparse older `update_history` entry도 current update schema로 normalize되고, top-level `schema_upgraded_update_count`, `by_update_schema_upgrade_reason`로 same lifecycle upgrade를 추적
  - sparse older `decision_history` event도 current decision schema로 normalize되고, top-level `schema_upgraded_decision_event_count`, `by_decision_schema_upgrade_reason`로 same lifecycle upgrade를 추적
  - local registry top-level `schema_status` token으로 `normalized` vs `legacy_*_present` 상태를 바로 읽을 수 있고, item/update/decision record도 `schema_status=normalized|legacy_upgraded`를 직접 가짐
  - local registry item의 `support_status`, `mechanically_healthy`, `promotion_policy_ready`와 top-level `by_support_status` / item-level mechanical-policy aggregate
  - local registry top-level current state도 `by_case_review_status` / `case_review_statuses[]`를 보존
  - same `support_apply.py` CLI output도 `all_accepted_cases` / `mixed_review_status_cases` / `all_rejected_cases` explicit case list를 노출
  - local registry `last_update` / `update_history`도 same support-status split과 mechanical-policy aggregate를 보존
  - local registry `last_update`도 `reviewable_case_count` / `blocked_case_count` / `by_case_status` / `case_statuses[]` case-level aggregate를 보존
  - same `last_update`도 explicit case count/list(`all_reviewable_case_count`, `mixed_case_count`, `all_blocked_case_count`, `all_reviewable_cases`, `mixed_cases`, `all_blocked_cases`)를 보존
  - `support_registry_update.json` preview와 local registry `last_update`가 `accepted/rejected/pending_by_support_status`도 보존
  - legacy decision-only registry에서도 direct API와 final written artifact가 `schema_status` / `last_update.schema_status` truth를 같이 보이도록 정렬
  - same legacy decision-only case에서 `build_curated_support_registry(...)` direct return과 `write_curated_support_registry(...)` file output parity를 regression으로 고정
  - `verdict_authority_ready` / `measured_gate_ready`가 false인 accepted entry reject
  - local registry의 `update_history`, `by_decision`, `by_reviewer` persistence
  - same case/slug에 대한 obvious `selected_family/selected_stack_id/topology/vuln_id` merge conflict reject
  - empty decision / blocked review queue 기준 local apply chain이 false promotion 없이 `registry_item_count=0` no-op로 끝나는 것까지 direct verification
  - same no-op path에서 `accepted/rejected/pending_by_support_status={}`와 empty local registry `by_support_status={}`로 끝나는 것까지 direct verification
  - `support_review -> support_decide -> support_apply` synthetic CLI chain에서 reviewable accept path와 blocked no-op path를 둘 다 regression으로 고정
  - planning-only pair output을 입력으로 한 blocked/no-op support chain이 `authority_ready_bundle_count=2`, `measured_gate_blocked_bundle_count=2`, `reviewable_bundle_count=0` 상태에서도 false promotion 없이 empty local registry로 끝나는 것까지 direct verification
- Active subtask decomposition:
  - `TKT-009-A. Local Registry Materialization`
    - measured/manual preview artifact를 reusable local registry JSON workflow로 연결
    - accepted item upsert와 decision history append semantics를 고정
    - blocked/no-op path뿐 아니라 representative reviewable accept path를 실제 direct workflow로 재검증
    - `TKT-009-A1. Reviewable Accept Path Verification`
      - representative reviewable measured lane를 실제 `support_review -> support_decide -> support_apply` chain으로 끝까지 검증
      - local registry가 non-empty accepted item을 materialize하는 representative direct workflow를 확보
      - current bounded closure로는 synthetic reviewable CLI workflow regression이 추가됐고, remaining residual은 actual measured lane accept path direct verification
      - `TKT-009-A1-A. First Reviewable LLM-Shaped Positive Lane`
        - `trusted-dynamic-sqli`를 first proving-ground lane로 고정해 `llm_fixture/llm_manifest/thin_or_incomplete/oracle_execution_parity_missing` residual을 reviewable accept-path 관점에서 실제로 줄인다
        - same lane가 support review에서 non-empty accepted local registry item으로 이어지는 minimal representative closure를 만든다
        - current known blocker set(`measured_gate:cache_reuse_inconsistent`, `measured_gate:artifact_quality_band_not_high`, `measured_gate:oracle_execution_parity_not_high`, `name_only_outcome:not_applicable`)을 direct burn-down target으로 유지한다
      - `TKT-009-A1-B. First Reviewable Dynamic Name-Only Positive Lane`
        - `open-redirect-dynamic-name-only`를 first dynamic name-only proving-ground lane로 고정해 `deterministic_fallback/partial/thin_fallback_demo` residual을 reviewable accept-path 관점에서 실제로 줄인다
        - same lane가 measured gate와 support review를 통과해 “runnable but not promotable”에서 최소 1개의 reviewable candidate로 넘어가는 direct workflow를 만든다
        - current known blocker set(`strict_open_world:strict_minimal_dynamic_fallback`, `open_world:semantic_guided_minimal_dynamic`, `artifact_quality:medium`, `name_only_outcome:partial`, `measured_gate:artifact_quality_band_not_high`)을 direct burn-down target으로 유지한다
      - `TKT-009-A1-C. First Reviewable Live-LLM Name-Only Positive Lane`
        - `live LLM response + open-world name-only + dynamic Docker materialization` 교집합 proving-ground lane를 explicit accept-path target으로 고정한다
        - same lane를 `trusted-dynamic-sqli` fixture comparator와 `open-redirect-dynamic-name-only` degraded comparator와 분리해서 measured/support workflow로 끝까지 검증한다
        - current direct burn-down target은 교집합 lane 부재, `TKT-006-D` live materialization contract, `TKT-006-E/F` build-ready/safety contract, `TKT-008-A3` generation-path axis를 하나의 accept-path로 연결하는 것이다
        - minimum direct acceptance token은 `llm_execution.path_class=live`, `provider_attempted=true`, `provider_succeeded=true`, `fixture_used=false`, `stub_fallback=false`, name-only lane의 non-fallback materialization, 그리고 support review에서 `reviewable_bundle_count >= 1`이다
    - `TKT-009-A2. Blocked / No-Op Path Preservation`
      - blocked queue, empty decision, authority/measured gate blocker가 false promotion 없이 `registry_item_count=0` no-op로 끝나는 current safety behavior를 regression으로 고정
      - planning-only pair(`foobar-name-only-negative`, `open-redirect-strict-dynamic-no-remote`) 기반 support review index가 `by_case_status={all_blocked:2}`, `by_support_status={blocked_mixed:2}`를 유지한 채 same empty-decision apply chain으로 이어지게 고정
      - same blocked/no-op chain에서 final local registry가 `schema_status=normalized`, `registry_item_count=0`, empty `by_review_status` / `by_support_status` / `by_case_review_status`로 끝나는 것을 low-cost no-Docker regression으로 계속 재검증
      - high-quality bounded comparator `sqli-sidecar-compiler-custom-env`도 `strict_curated_lower_bound` / `catalog_resolved_lower_bound` / `family_evidence:candidate_unbacked` / `measured_gate:cache_reuse_inconsistent` 때문에 still blocked라는 truth를 유지해, “high quality bounded artifact != first promotable open-world lane” 경계를 regression으로 고정한다
  - `TKT-009-B. Registry Provenance / Merge Policy Hardening`
    - merge conflict policy, history compaction, registry schema evolution을 정리
    - local JSON workflow를 reusable operator workflow로 더 단단하게 만들기
    - `TKT-009-B1. Item Provenance / Status Surface`
      - item-level `review_status`, `source_artifacts`, `last_decision`, top-level `by_review_status`, `items_with_source_artifacts_count` 같은 current-state surface를 더 정교하게 정리
      - operator가 local registry만 보고 current accepted/rejected/provenance 상태를 빠르게 읽을 수 있게 정리
      - support workflow의 `support_status` / mechanical-policy split을 local registry item과 top-level item aggregate까지 일관되게 이어 붙이기
      - local registry top-level current state도 `by_case_review_status` / `case_review_statuses[]`로 case 단위 accepted/rejected 상태를 바로 읽을 수 있게 정리
      - same current-state aggregate를 `support_apply.py` CLI stdout에도 explicit case list로 노출해 operator-facing readability를 높이기
      - same `last_update` context도 explicit case count/list를 같이 보존해 latest apply context를 preview/current-state와 같은 vocabulary로 읽게 정리
    - `TKT-009-B2. Merge Policy / History Lifecycle`
      - obvious merge conflict reject를 넘는 merge policy, history compaction, schema evolution, long-lived registry maintenance policy를 정리
      - sparse legacy registry item을 current lifecycle/status/provenance schema로 normalize하는 bounded upgrade path를 유지
      - same schema upgrade가 어떤 field/reason으로 발생했는지 item/top-level/update-history surface까지 남김
      - same schema evolution을 local registry item뿐 아니라 historical update entry에도 적용
      - same schema evolution을 top-level historical decision event에도 적용
      - same lifecycle maintenance 상태를 single `schema_status` token으로도 요약
    - `TKT-009-B3. Registry API / Artifact Schema-Status Parity`
      - `build_curated_support_registry(...)` direct return과 `support_apply.py`가 write한 final artifact가 `schema_status` / `last_update.schema_status` / `registry_schema_status`에서 같은 truth를 보이도록 정리
      - legacy item/update/decision normalization count와 `by_*_schema_upgrade_reason` 집계가 file roundtrip 없이도 direct API surface에서 일관되게 읽히게 만든다
      - `2026-03-19` workspace-local direct verification에서는 blocked/no-op CLI path는 정상 동작했지만 internal API contract regression이 남아 있었으므로, same parity를 regression close 조건으로 둔다
      - `TKT-009-B3-A. Legacy Decision-Only Schema-Status Parity`
        - decision-history만 있는 sparse legacy registry에서도 top-level과 `last_update`가 같은 maintenance truth를 보이도록 정리
        - `schema_upgraded_decision_event_count` / `by_decision_schema_upgrade_reason`가 nested summary에서도 같은 상태를 가리키게 맞춘다
      - `TKT-009-B3-B. Direct API vs Written Artifact Parity`
        - `build_curated_support_registry(...)` direct return과 `write_curated_support_registry(...)` file roundtrip 결과가 동일한 `schema_status` / `registry_schema_status` / aggregate를 보이도록 정리
        - operator CLI path와 unit/API path가 서로 다른 truth를 보이지 않도록 regression으로 고정

### TKT-010. Expansion After Runtime / Oracle Closure

- Priority: `P6`
- Phase mapping: `Phase 7`
- Status: `deferred`
- Problem:
  - family/stack 수를 늘리기 전에 runtime/oracle closure가 충분히 닫혀야 한다.
- Scope:
  - runtime class, dependency class, topology class, oracle class 확장을 family/stack expansion보다 먼저 설계한다.
  - expansion gate를 current measurement rubric에 연결한다.
- Out of scope:
  - immediate family-count scaling
  - unsupported runtime ecosystem expansion
- Exit criteria:
  - expansion 후보가 runtime/oracle/eval closure 기준을 통과해야만 backlog 상향이 가능하다.
- Minimum validation:
  - roadmap and measurement gate review
- Active subtask decomposition:
  - `TKT-010-A. Open-Vocabulary Family Induction`
    - runtime/oracle closure 이후 known-family bounded induction을 넘어서는 open-vocabulary family induction path를 설계
    - current fixed family hint universe 바깥 표현을 어떻게 provisional family로 세울지 측정 기준과 함께 정리
  - `TKT-010-B. Stack / Runtime-Class Expansion`
    - 현재 `python/flask`, `python/fastapi` narrow pool을 넘는 stack/runtime class expansion을 설계
    - non-Python 또는 broader multi-runtime expansion을 existing measurement rigor 안에서만 backlog 상향 가능하게 정리
  - `TKT-010-C. Expansion Unlock Contract`
    - expansion backlog를 올리기 전 충족해야 할 prerequisite bundle을 explicit하게 정의한다
    - 최소한 `live-LLM positive proving ground`, `non-SQLi primitive-first proving ground`, `browserful/stateful oracle proving ground`, `topology class beyond single-primary bounded lane` 같은 unlock set을 measurement/support gate와 함께 묶어 둔다
    - same unlock set은 currently direct verification된 comparator lane(`trusted-dynamic-sqli`, `open-redirect-dynamic-name-only`, `csrf-dynamic-name-only`, `sqli-sidecar-compiler-custom-env`)과 future proving-ground lane를 구분해 읽게 만든다

## Sequencing Rule

기본 실행 순서는 아래를 유지한다.

1. `TKT-001`
2. `TKT-002` ~ `TKT-005`
3. `TKT-006`
4. `TKT-007`
5. `TKT-008`
6. `TKT-009`
7. `TKT-010`

예외:

- `TKT-006`은 `TKT-001`과 일부 병행될 수 있지만, generalized runtime closure보다 앞서 support workflow를 올리지는 않는다.
- `TKT-009`는 `TKT-002` ~ `TKT-005`보다 앞서지 않는다.

## How To Update This Document

- current truth가 바뀌어 ticket priority나 scope가 달라질 때만 갱신한다.
- representative rerun evidence 자체는 [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)에 남긴다.
- non-claim과 operational constraint는 [docs/constraints.md](constraints.md)에 남긴다.
- phase ordering이 바뀌면 [docs/final_solution.md](final_solution.md)를 먼저 바꾸고 여기의 phase mapping을 따라 수정한다.
- ticket owner가 보는 primary code path나 representative validation surface가 달라지면 `Implementation Entry Points And Validation Surface`도 같이 갱신한다.
- validation harness 진입 문서나 첫 검증 순서가 바뀌면 `Validation Routing`도 같이 갱신한다.
- validation 문서 전체의 권장 reading order가 바뀌면 `Validation Reading Order`와 README/handbook/code/e2e 문서의 대응 섹션도 같이 갱신한다.
- validation companion 관계가 바뀌면 README/handbook/code/e2e 문서의 같은 섹션도 같이 갱신한다.
- validation question routing이 바뀌면 README/handbook/code/e2e 문서의 대응 링크도 같이 갱신한다.
- completion companion set이 바뀌면 README/handbook/code/e2e 문서와 canonical 문서의 completion companion 섹션도 같이 갱신한다.
- residual question routing이 바뀌면 README/handbook/code/e2e 문서와 canonical companion 링크도 같이 갱신한다.
- review mode matrix가 바뀌면 README/handbook/code/e2e 문서의 mode entry 섹션도 같이 갱신한다.
- residual companion set이 바뀌면 README/handbook/code/e2e와 canonical 문서의 residual companion 섹션도 같이 갱신한다.
- success criteria 5축과 backlog owner의 대응이 바뀌면 `Open-World Completion Axis Map`도 같이 갱신한다.
- success criteria 5축의 완료판정 질문이나 최소 근거가 바뀌면 `Open-World Completion Checklist`도 같이 갱신한다.
- 완료판정 canonical review order가 바뀌면 `Open-World Completion Review Flow`와 관련 companion 링크도 같이 갱신한다.
- 완료판정 canonical reading order가 바뀌면 `Open-World Completion Reading Order`와 README/handbook/code/e2e 문서의 대응 섹션도 같이 갱신한다.
- latest confirmed residual을 축별 ticket bundle로 다시 쪼개는 방식이 바뀌면 `Open-World Residual Ticket Breakdown`도 같이 갱신한다.
- residual implementation review의 canonical 순서가 바뀌면 `Open-World Residual Review Flow`와 관련 companion/entry 링크도 같이 갱신한다.
- residual 문서 reading order가 바뀌면 `Open-World Residual Reading Order`와 README/handbook/code/e2e 문서의 대응 섹션도 같이 갱신한다.
- queue-facing 정성/정량 shorthand가 바뀌면 `Current Capability Scorecard`와 companion 문서의 priority/turn-estimate entry도 같이 갱신한다.
- 평가 내용을 ticket-form으로 재분해하는 규칙이 바뀌면 `Evaluation-To-Ticket Breakdown`과 companion 문서의 priority reading order도 같이 갱신한다.
- turn envelope 추산이 바뀌면 `Estimated Turn Envelope`와 README/handbook/code/e2e/roadmap 문서의 priority routing도 같이 갱신한다.
- `Turn Estimate Entry`의 reading order가 바뀌면 README/handbook/code/e2e entry 문서의 same shortcut도 같이 갱신한다.
- LLM-response stricter reading의 ticket overlay가 바뀌면 companion 문서의 same routing/update section도 같이 갱신한다.
- latest positive representative pair의 ticket-form 해석이 바뀌면 companion 문서의 same routing/update section과 `Assessment-To-Ticket Interpretation` reference도 같이 갱신한다.
- `Priority Review Entry`의 reading order가 바뀌면 README/handbook/code/e2e와 archive/support companion 문서의 같은 entry도 같이 갱신한다.
- `LLM-Response Capability Overlay`의 reading order나 해석 규칙이 바뀌면 related companion 문서의 `Priority Companions` / `Priority Review Entry` / `How To Update`도 같이 갱신한다.
- review mode matrix나 mode entry shortcuts가 바뀌면 README/handbook/code/e2e 문서의 대응 섹션도 같이 갱신한다.
