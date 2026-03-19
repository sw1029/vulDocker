# vulDocker 작업 티켓

Status: canonical
Audience: implementation
Source of truth for: actionable ticket decomposition, current backlog slicing, phase-to-ticket mapping
Not the source of truth for: rerun evidence, active constraints, operator quickstart
Last validated against: roadmap/current-state/constraints and workspace-local direct execution on 2026-03-19, with 2026-03-15 representative reruns retained as residual grounding

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

- implementation owner, subtask decomposition, backlog priority를 보려면 이 문서를 본다.
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

## Review Mode Matrix

문서를 어떤 목적에서 열고 있는지에 따라 canonical 시작점은 아래처럼 고른다.

| Review mode | Start here | First routing surface | Canonical reading order | Primary outcome |
| --- | --- | --- | --- | --- |
| 검증 | `Validation Companions` | `Validation Question Routing` | `Validation Reading Order` | representative rerun / measured-support harness와 code/artifact를 연결한다 |
| 완료판정 | `Completion Companions`, `Open-World Completion Axis Map` | `Validation Question Routing` | `Open-World Completion Reading Order` | success criteria 5축이 실제로 닫혔는지 판단한다 |
| 잔여 검토 | `Residual Companions`, `Open-World Residual Ticket Breakdown` | `Residual Question Routing` | `Open-World Residual Reading Order` | latest confirmed residual이 어느 ticket bundle에 남았는지와 다음 확인 경로를 정한다 |

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
- “이 residual의 코드는 어디부터 읽어야 하나?”
  - [docs/code/README.md](code/README.md)
  - subsystem docs의 `Ticket-First Entry` / `Residual Review Focus`
- “이 residual의 artifact는 어디서 읽나?”
  - [docs/handbook.md](handbook.md)의 `Open-World Axis Reading Hints`
  - [docs/code/workspaces.md](code/workspaces.md)의 `Open-World Axis Artifact Hints`
- “왜 아직 residual이 닫혔다고 말하면 안 되나?”
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
| `TKT-002-A` | `TKT-002` | ready | graph-first service/sidecar/env/network execution |
| `TKT-002-B` | `TKT-002` | ready | graph-first health/poc/runtime surface consumption |
| `TKT-002-C` | `TKT-002` | ready | runtime_graph authoritative executor consumption |
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
| `TKT-007-A` | `TKT-007` | ready | browserful/sessionful multi-step replay |
| `TKT-007-B` | `TKT-007` | ready | realism rubric integration |
| `TKT-008-A` | `TKT-008` | ready | authoritative measured gate and CI comparison |
| `TKT-008-B` | `TKT-008` | ready | planning-only and multi-bundle summary consistency residual |
| `TKT-008-B1` | `TKT-008-B` | ready | mixed multi-bundle top-level verdict/failure projection consistency |
| `TKT-008-B2` | `TKT-008-B` | ready | authoritative measured-gate handoff and top-level/nested precedence |
| `TKT-008-B3` | `TKT-008-B` | ready | repeatability surface contract stabilization |
| `TKT-008-B3-A` | `TKT-008-B3` | ready | repeat helper backward-compat arguments |
| `TKT-008-B3-B` | `TKT-008-B3` | ready | plan writer sid-salt compatibility seam |
| `TKT-008-B3-C` | `TKT-008-B3` | ready | repeatability report top-level case key parity |
| `TKT-008-A1` | `TKT-008-A` | ready | measured-gate blocker policy split for mechanically healthy lanes |
| `TKT-008-A2` | `TKT-008-A` | ready | authoritative CI/measured gate consumption policy |
| `TKT-009-A` | `TKT-009` | ready | registry write/merge workflow |
| `TKT-009-B` | `TKT-009` | ready | provenance/history persistence |
| `TKT-009-A1` | `TKT-009-A` | ready | representative reviewable accept-path direct workflow verification |
| `TKT-009-A2` | `TKT-009-A` | ready | blocked/no-op path regression preservation |
| `TKT-009-B1` | `TKT-009-B` | ready | registry item provenance/status surface hardening |
| `TKT-009-B2` | `TKT-009-B` | ready | merge policy, history compaction, schema evolution |
| `TKT-009-B3` | `TKT-009-B` | ready | registry API / artifact schema-status parity |
| `TKT-009-B3-A` | `TKT-009-B3` | ready | legacy decision-only schema-status parity |
| `TKT-009-B3-B` | `TKT-009-B3` | ready | direct API vs written artifact parity |
| `TKT-010-A` | `TKT-010` | deferred | open-vocabulary family induction after runtime/oracle closure |
| `TKT-010-B` | `TKT-010` | deferred | stack/runtime-class expansion beyond Python narrow pool |

## Direct Verification Slice

`2026-03-19` workspace-local direct execution에서 확인한 latest residual을 work ticket으로 매핑하면 아래와 같다.

| Observed issue | Ticket | Why this ticket |
| --- | --- | --- |
| `summarize_repeat_attempt(...)` helper call shape drift | `TKT-008-B3-A` | repeat helper backward-compat와 report contract 안정화 |
| `_write_plan(..., sid_salt=...)` 도입 이후 older stub/test double breakage | `TKT-008-B3-B` | SID isolation은 유지하되 unit/mock seam 복구 |
| `repeatability_report.json` top-level `case` vs `case_name` drift | `TKT-008-B3-C` | operator-facing measured artifact key parity 복구 |
| legacy decision-only registry에서 nested `last_update.schema_status` drift | `TKT-009-B3-A` | legacy decision normalization truth를 top-level/nested에서 동일하게 유지 |
| `build_curated_support_registry(...)` direct return vs final written artifact drift | `TKT-009-B3-B` | API path와 CLI/file path가 같은 support-registry truth를 보이게 정렬 |
| planning-only repeatability lanes가 둘 다 `measured_gate.ready=false`와 `cache_reuse_inconsistent`, `artifact_quality_band_not_high`, `oracle_execution_parity_not_high` blocker를 남김 | `TKT-008-A1`, `TKT-008-A2` | repeatability CLI는 정상인데 measured promotion gate가 의도대로 닫혀 있는 상태를 authoritative policy 관점에서 계속 정리해야 함 |
| blocked support workflow recheck가 `by_support_status={blocked_mixed:2}`, `by_case_status={all_blocked:2}`, final `registry_item_count=0` no-op로 끝남 | `TKT-009-A2` | blocked/no-op path가 false promotion 없이 유지되는 current safety behavior를 regression으로 계속 고정해야 함 |
| current WSL 2 distro에서 `docker ps` 자체가 불가하고 representative dynamic lane 재검증이 환경 단계에서 막힘 | `none (operational precondition)` | implementation backlog라기보다 README/handbook에 반영해야 할 local verification prerequisite |

latest rerun slice는 위 항목을 재확인했을 뿐, 새 product backlog ticket을 추가로 만들지는 않았다. current residual owner는 그대로 `TKT-008-A*`, `TKT-009-A2`, 그리고 operational Docker prerequisite 분리 해석을 유지한다.

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
| 선택 | family/stack/topology/oracle 선택이 primitive-first joint decision으로 materialization에 실제 영향을 주는가 | `summary.json`의 `request_ir` / `selection_decision` / `name_only_outcome`, `metadata/<SID>/researcher_report.json`, representative name-only rerun | evidence-enriched top choice는 보이지만 family-first bounded builder가 still primary path | `TKT-001-A/B/C/D/E/F/G` |
| 생성 | staged synthesis가 one-shot default가 아니라 intent-faithful branch/recovery로 산출물을 만든다는 것이 남는가 | `metadata/<SID>/generator_manifest.json`, `generator_runs.json`, `generator_failures.jsonl`, `loop_state.json`, `manifest.json` or `failure_manifest.json` | bounded/degraded generation은 가능하지만 stage-resumable repair와 branch split이 authoritative하지 않음 | `TKT-001`, `TKT-006` |
| 실행 | `runtime_graph` / `executor_plan`이 설명 surface가 아니라 actual executor truth를 지배하는가 | `manifest.json`의 `runtime_graph` / `executor_plan`, `artifacts/<SID>/run/summary.json`, representative E2E `summary.json` | single-service 및 bounded sidecar parity는 있으나 generalized lifecycle/seed/env-volume-network closure는 부족 | `TKT-002`, `TKT-003`, `TKT-004`, `TKT-005` |
| 검증 | oracle replay와 measured gate가 richer stateful truth를 반영하며 promotion gate로 authoritative하게 연결되는가 | `artifacts/<SID>/run/oracle_execution.json`, `reports/evals.json`, `repeatability_report.json`, `matrix_report.json` | stateless/sessionful 일부 closure와 preview gate만 있고 browserful/stateful replay와 CI/policy gate는 미완 | `TKT-007`, `TKT-008-A1`, `TKT-008-A2` |
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
| 선택 | primitive-first joint decision이 아직 authoritative controller가 아니고 family-first bounded builder가 여전히 primary path다 | `TKT-001-A`, `TKT-001-B`, `TKT-001-C`, `TKT-001-D`, `TKT-001-E`, `TKT-001-F`, `TKT-001-G` | representative non-SQLi name-only lane가 primitive/dependency/topology/oracle decision에서 실제로 materialize되고, summary가 branch authority를 직접 남긴다 |
| 생성 | one-shot manifest 의존이 여전히 크고 staged repair/resume가 deterministic fallback보다 앞서지 못한다 | `TKT-001-B`, `TKT-001-C`, `TKT-006-A`, `TKT-006-B`, `TKT-006-C` | stage artifact persistence와 repair-first retry가 representative dynamic lane에서 measurable하게 남고 generic fallback 진입이 줄어든다 |
| 실행 | `runtime_graph` / `executor_plan`이 아직 설명/provenance surface에 더 가깝고 generalized lifecycle/seed/env-volume/network semantics가 미완이다 | `TKT-002-A`, `TKT-002-B`, `TKT-002-C`, `TKT-003-A`, `TKT-003-B`, `TKT-004-A`, `TKT-004-B`, `TKT-005-A`, `TKT-005-B`, `TKT-005-C` | representative single-service / sidecar lane가 graph-first execution으로 돌고 lifecycle/seed/network provenance가 same contract surface로 남는다 |
| 검증 | browserful/stateful oracle replay가 부족하고 measured gate는 아직 preview/policy split 수준이다 | `TKT-007-A`, `TKT-007-B`, `TKT-008-A1`, `TKT-008-A2` | representative stateful lane에서 richer oracle replay가 quality tier에 반영되고 measured gate가 CI/policy authoritative surface로 승격된다 |
| 보고 | honesty surface와 blocked no-op path는 닫혔지만 actual reviewable accept-path와 long-lived registry provenance/merge lifecycle은 미완이다 | `TKT-009-A1`, `TKT-009-A2`, `TKT-009-B1`, `TKT-009-B2` | representative measured accept-path가 non-empty accepted registry item을 materialize하고, same registry가 provenance/history/merge policy를 일관되게 유지한다 |

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
| `TKT-008` | [tests/e2e/README.md](../tests/e2e/README.md), [docs/handbook.md](handbook.md) | `tests/e2e/repeat_case.py`, `tests/e2e/matrix_report.py`, `tests/test_repeatability_gate.py`, `tests/e2e/test_case_matrix_rollup.py` | planning-only lane만으로도 preview/measured gate sanity 일부 확인 가능 |
| `TKT-009` | [tests/e2e/README.md](../tests/e2e/README.md), [docs/handbook.md](handbook.md) | `tests/e2e/support_review.py`, `tests/e2e/support_decide.py`, `tests/e2e/support_apply.py`, `tests/test_support_extract.py`, `tests/e2e/test_support_workflow.py` | current local registry flow는 measured/manual workflow이지 auto-promotion path가 아니다 |
| `TKT-010` | [docs/final_solution.md](final_solution.md), [docs/current_state_gap_analysis.md](current_state_gap_analysis.md) | roadmap review, residual review, gate review only | implementation harness보다 readiness review가 먼저다 |

## Validation Reading Order

검증부터 시작할 때의 canonical reading order는 아래와 같다.

1. [docs/work_tickets.md](work_tickets.md)의 `Validation Routing`
2. [tests/e2e/README.md](../tests/e2e/README.md)의 harness command / case layout / ticket mapping
3. [docs/code/README.md](code/README.md)와 subsystem docs의 code entrypoint
4. [docs/handbook.md](handbook.md)의 artifact map / troubleshooting

phase acceptance gate와 validation surface의 대응은 [docs/final_solution.md](final_solution.md)의 `Acceptance-To-Validation Translation`을 같이 본다.

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
- Out of scope:
  - arbitrary unknown family discovery
  - non-Python/general multi-runtime expansion
- Exit criteria:
  - representative bounded lane가 family-first builder가 아니라 primitive/dependency/topology decision에서 materialize된다.
  - summary/contract surface가 어떤 controller signal이 선택을 지배했는지 직접 남긴다.
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
  - `TKT-001-F. Unresolved-To-Abstain Transition Modeling`
    - ambiguity/evidence-thin/unresolved 상태가 언제 `partial`, `abstain`, `fail_closed`로 넘어가는지 explicit transition rule로 고정한다
    - same transition이 researcher/generator/executor handoff에서 달라지지 않게 한다
  - `TKT-001-G. Evidence Authority Thresholding`
    - lexical support count를 넘어서 scenario selection에 필요한 minimum authority / contradiction threshold를 explicit rule로 정리한다
    - evidence graph를 causal proof로 과장하지 않으면서도 branch controller가 쓸 수 있는 threshold surface를 마련한다

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
- Out of scope:
  - fully autonomous open-world self-repair
  - arbitrary external tool orchestration
- Exit criteria:
  - malformed intermediate가 곧장 final fallback으로 무너지지 않는다.
  - recovery path가 어떤 stage artifact를 어떻게 보정했는지 summary에 남는다.
  - representative dynamic lane에서 deterministic fallback 진입 전 typed repair가 measurable하게 늘어난다.
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
- Out of scope:
  - external benchmark leaderboard
  - generalized capability claim automation
- Exit criteria:
  - representative measured lane가 stable quality/perf buckets로 비교된다.
  - gate가 `oracle_execution_parity=high`와 `artifact_quality.band=high`를 계속 분리한다.
  - remaining summary drift가 known documented exception 수준으로 줄어든다.
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
    - `TKT-008-A2. Authoritative CI / Measured Gate`
      - current preview/enforcement bridge를 CI-level authoritative measured gate로 승격
      - `snippet/evidence reuse`, representative perf comparison, blocker precedence를 explicit regression policy로 연결
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
- Active subtask decomposition:
  - `TKT-009-A. Local Registry Materialization`
    - measured/manual preview artifact를 reusable local registry JSON workflow로 연결
    - accepted item upsert와 decision history append semantics를 고정
    - blocked/no-op path뿐 아니라 representative reviewable accept path를 실제 direct workflow로 재검증
    - `TKT-009-A1. Reviewable Accept Path Verification`
      - representative reviewable measured lane를 실제 `support_review -> support_decide -> support_apply` chain으로 끝까지 검증
      - local registry가 non-empty accepted item을 materialize하는 representative direct workflow를 확보
      - current bounded closure로는 synthetic reviewable CLI workflow regression이 추가됐고, remaining residual은 actual measured lane accept path direct verification
    - `TKT-009-A2. Blocked / No-Op Path Preservation`
      - blocked queue, empty decision, authority/measured gate blocker가 false promotion 없이 `registry_item_count=0` no-op로 끝나는 current safety behavior를 regression으로 고정
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
- review mode matrix나 mode entry shortcuts가 바뀌면 README/handbook/code/e2e 문서의 대응 섹션도 같이 갱신한다.
