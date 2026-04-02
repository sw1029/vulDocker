# vulDocker 구현 로드맵

Status: canonical
Audience: mixed
Source of truth for: implementation priority, phase ordering, acceptance gates
Not the source of truth for: current rerun evidence, active constraints, operator quickstart
Last validated against: current code structure, rerun-backed assessment, and active ticket decomposition on 2026-04-02

이 문서는 `name only` intent fidelity와 generalized open-world readiness를 높이기 위한 phase-based roadmap입니다. 현재 baseline을 재서술하지 않고, 어떤 순서로 무엇을 바꿀지와 각 phase의 완료 조건만 정의합니다.

관련 문서:
- 문제 정의와 success criteria: [docs/problem.md](problem.md)
- 현재 rerun-backed truth: [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)
- 현재 제약과 금지 claim: [docs/constraints.md](constraints.md)
- actionable ticket decomposition: [docs/work_tickets.md](work_tickets.md)
- 운영/명령/아티팩트: [docs/handbook.md](handbook.md)
- representative validation harness: [tests/e2e/README.md](../tests/e2e/README.md)

실제 구현 backlog를 작업 티켓 단위로 쪼갠 canonical 문서는 [docs/work_tickets.md](work_tickets.md)다. 이 문서는 phase ordering과 acceptance gate만 유지한다. latest bounded repeatability/support stabilization closure는 `TKT-008-B3`와 `TKT-009-B3` 아래에 흡수되며, latest slice에서는 `ops/ci/lib_case_chain_profile_target_forward.sh`와 `tests/test_ops_ci_case_chain_profile_target_forward.py`가 direct/repeatability profile wrapper family의 shared `profile target forward` surface까지 direct regression으로 닫았다. phase ordering 자체는 바꾸지 않는다.

## Reader Routing

- current truth나 rerun evidence를 확인하려면 이 문서가 아니라 [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)를 먼저 본다.
- 금지 claim과 current limit은 [docs/constraints.md](constraints.md)를 본다.
- 실제 구현 단위, subtask owner, 잔여 작업량/turn envelope는 [docs/work_tickets.md](work_tickets.md)를 본다.
- 이 문서는 phase ordering, acceptance gate, sequencing 판단에만 쓴다.
- concrete rerun command와 measured/support harness detail은 [tests/e2e/README.md](../tests/e2e/README.md)를 본다.

## Validation Companions

이 문서의 phase/acceptance gate를 실제 검증 흐름으로 내릴 때는 아래 문서를 같이 본다.

- current truth와 rerun evidence는 [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)
- constraint boundary와 forbidden claim은 [docs/constraints.md](constraints.md)
- success criteria 5축과 backlog owner 대응은 [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Axis Map`
- completion companion set은 [docs/work_tickets.md](work_tickets.md)의 `Completion Companions`
- priority companion set은 [docs/work_tickets.md](work_tickets.md)의 `Priority Companions`
- success criteria 5축의 완료판정 질문과 최소 근거는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Checklist`
- success criteria 5축의 canonical 완료 검토 순서는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Review Flow`
- success criteria 5축의 canonical 완료판정 reading order는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Reading Order`
- latest confirmed residual의 축별 ticket bundle 분해는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Residual Ticket Breakdown`
- latest residual의 concise ticket-form summary는 [docs/work_tickets.md](work_tickets.md)의 `Current Remaining Ticket Form`
- latest residual의 shorthand ticket routing은 [docs/work_tickets.md](work_tickets.md)의 `Current Remaining Ticket Routing`
- latest direct verification까지 반영한 current completion priority order는 [docs/work_tickets.md](work_tickets.md)의 `Confirmed Completion Priority Order`
- latest confirmed residual의 canonical 구현 검토 순서는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Residual Review Flow`
- latest confirmed residual 검토 문서 순서는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Residual Reading Order`
- residual companion set은 [docs/work_tickets.md](work_tickets.md)의 `Residual Companions`
- review mode별 canonical 시작점은 [docs/work_tickets.md](work_tickets.md)의 `Review Mode Matrix`
- 우선순위 판단 문서 routing은 [docs/work_tickets.md](work_tickets.md)의 `Priority Question Routing`, `Priority Reading Order`, `Assessment-To-Ticket Interpretation`
- ticket owner, first harness, validation reading order는 [docs/work_tickets.md](work_tickets.md)의 `Validation Routing` / `Validation Reading Order`
- 질문 기반 검증 문서 routing은 [docs/work_tickets.md](work_tickets.md)의 `Validation Question Routing`
- 질문 기반 residual 문서 routing은 [docs/work_tickets.md](work_tickets.md)의 `Residual Question Routing`
- concrete rerun/support harness command는 [tests/e2e/README.md](../tests/e2e/README.md)
- artifact map / troubleshooting은 [docs/handbook.md](handbook.md)

## Completion Companions

이 문서의 phase/acceptance gate를 완료판정 관점으로 읽을 때는 아래 문서를 같이 본다.

- completion companion set은 [docs/work_tickets.md](work_tickets.md)의 `Completion Companions`
- priority companion set은 [docs/work_tickets.md](work_tickets.md)의 `Priority Companions`
- axis map / close criteria / canonical review order는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Axis Map`, `Open-World Completion Checklist`, `Open-World Completion Review Flow`
- canonical completion reading order는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Reading Order`
- concrete rerun / support harness command는 [tests/e2e/README.md](../tests/e2e/README.md)
- current truth / non-claim은 [docs/current_state_gap_analysis.md](current_state_gap_analysis.md), [docs/constraints.md](constraints.md)

## Priority Companions

이 문서의 phase ordering/sequencing을 우선순위 판단 관점으로 읽을 때는 아래 문서를 같이 본다.

- current completion priority order와 해석 규칙은 [docs/work_tickets.md](work_tickets.md)의 `Confirmed Completion Priority Order`
- latest residual의 concise ticket-form summary는 [docs/work_tickets.md](work_tickets.md)의 `Current Remaining Ticket Form`
- 잔여 작업량과 practical turn envelope는 [docs/work_tickets.md](work_tickets.md)의 `Estimated Turn Envelope`
- queue-facing 정성/정량 shorthand는 [docs/work_tickets.md](work_tickets.md)의 `Current Capability Scorecard`
- 계획 구체성 보강이 필요한 residual은 [docs/work_tickets.md](work_tickets.md)의 `Planning Specificity Residual Overlay`
- representative evidence와 함께 보는 turn estimate shortcut은 [docs/work_tickets.md](work_tickets.md)의 `Turn Estimate Entry`
- priority companion set / routing / reading order는 [docs/work_tickets.md](work_tickets.md)의 `Priority Companions`, `Priority Question Routing`, `Priority Reading Order`
- latest positive representative pair의 ticket-form reading은 [docs/work_tickets.md](work_tickets.md)의 `Assessment-To-Ticket Interpretation`
- LLM-response 기준 residual/priority 해석은 [docs/work_tickets.md](work_tickets.md)의 `LLM-Response Capability Overlay`
- current truth / non-claim은 [docs/current_state_gap_analysis.md](current_state_gap_analysis.md), [docs/constraints.md](constraints.md)
- concrete rerun / support harness command은 [tests/e2e/README.md](../tests/e2e/README.md)

## Review Mode Entry

이 문서를 보고 있을 때도, 현재 목적은 아래 셋 중 하나로 다시 좁혀서 본다.

- 검증:
  - [docs/work_tickets.md](work_tickets.md)의 `Review Mode Matrix`
  - [docs/work_tickets.md](work_tickets.md)의 `Validation Routing`
- 완료판정:
  - [docs/work_tickets.md](work_tickets.md)의 `Review Mode Matrix`
  - 이 문서의 `Completion Companions`
- 잔여 구현 검토:
  - [docs/work_tickets.md](work_tickets.md)의 `Review Mode Matrix`
  - [docs/work_tickets.md](work_tickets.md)의 `Open-World Residual Review Flow`
- 작업량 추산:
  - [docs/work_tickets.md](work_tickets.md)의 `Review Mode Matrix`
  - [docs/work_tickets.md](work_tickets.md)의 `Turn Estimate Entry`
- 우선순위 판단:
  - [docs/work_tickets.md](work_tickets.md)의 `Review Mode Matrix`
  - 이 문서의 `Priority Companions`
  - [docs/work_tickets.md](work_tickets.md)의 `Assessment-To-Ticket Interpretation`

## Priority Review Entry

phase ordering/sequencing 관점에서 우선순위 판단을 시작할 때는 아래 순서를 권장한다.

1. 이 문서의 `Priority Companions`
2. [docs/work_tickets.md](work_tickets.md)의 `Current Remaining Snapshot`, `Confirmed Completion Priority Order`, `Estimated Turn Envelope`
3. [docs/work_tickets.md](work_tickets.md)의 `Current Capability Scorecard`, `Planning Specificity Residual Overlay`, `Evaluation-To-Ticket Breakdown`, `LLM-Response Capability Overlay`, `Assessment-To-Ticket Interpretation`
4. 이 문서의 `Phase-To-Ticket Translation`, `Acceptance Gates`
5. [docs/current_state_gap_analysis.md](current_state_gap_analysis.md), [docs/constraints.md](constraints.md)
6. [tests/e2e/README.md](../tests/e2e/README.md), [docs/code/README.md](code/README.md), [docs/handbook.md](handbook.md)

turn estimate shortcut은 [docs/work_tickets.md](work_tickets.md)의 `Turn Estimate Entry`를 따른다.

## Strategy Summary

우선순위는 기능 수 확장보다 먼저 control-plane과 claim surface를 정직하게 만드는 쪽입니다.

핵심 설계 원칙:

- family/stack 개수 확장보다 먼저 selection, runtime design, oracle execution parity를 올립니다.
- `family`는 최종 설명 라벨일 수 있어도, 장기적으로는 `primitive / dependency / topology / oracle`보다 앞선 primary controller가 아니어야 합니다.
- runtime/topology generation은 executor parity보다 먼저 성립해야 합니다.

고정 순서:

1. truth surface와 decision policy 통일
2. joint scenario candidate IR
3. typed staged synthesis
4. generator controller activation
5. runtime/topology generation + executor parity
6. oracle execution parity
7. eval matrix + performance reuse
8. support promotion extraction
9. family/runtime expansion

세부 closure는 아래 sub-phase로 쪼갭니다.

- `Phase 2.5`는 `Phase 2`와 `Phase 3` 사이의 controller activation 단계입니다.
- `Phase 3A / 3B / 3C`는 bounded contract-stage runtime synthesis, executor provenance parity, generalized runtime closure를 나눕니다.
- `Phase 5A / 5B`는 measurement surface 도입과 closure를 나눕니다.
- `Phase 6A / 6B`는 reviewable extraction과 curated registry closure를 나눕니다.

## Phase-To-Ticket Translation

현재 active backlog 관점에서 phase residual을 ticket으로 번역하면 아래와 같다.

구체적인 code entrypoint와 representative validation surface는 [docs/work_tickets.md](work_tickets.md)의 `Implementation Entry Points And Validation Surface`를 따른다.
actual validation harness 진입 순서는 같은 [docs/work_tickets.md](work_tickets.md)의 `Validation Routing`과 [tests/e2e/README.md](../tests/e2e/README.md)를 따른다.

| Phase | Current ticket owner(s) | Note |
| --- | --- | --- |
| `Phase 0` | `TKT-001-E`, `TKT-001-F` | decision policy / partial-lane state machine residual |
| `Phase 1` | `TKT-001-A`, `TKT-001-B`, `TKT-001-C`, `TKT-001-G`, `TKT-001-H` | joint scenario candidate IR, selection algebra, evidence authority residual |
| `Phase 2` | `TKT-006-A`, `TKT-006-B`, `TKT-006-C`, `TKT-006-E`, `TKT-006-F` | typed staged synthesis의 resumable / repair-first residual과 file-manifest/build/safety contract residual |
| `Phase 2.5` | `TKT-001-D`, `TKT-001-I`, `TKT-006-D` | selection decision authoritative control-plane residual, selection-to-materialization causality residual, live-positive materialization provenance residual |
| `Phase 3A` | `TKT-002-A`, `TKT-004-A`, `TKT-005-A/B/C` | bounded contract-stage runtime synthesis의 remaining normalization / promotion residual |
| `Phase 3B` | `TKT-002-B` | executor provenance-preserving parity residual |
| `Phase 3C` | `TKT-002-C/D`, `TKT-003-A/B`, `TKT-004-B`, `TKT-005-A/B/C` | generalized runtime closure 본체와 topology class ladder residual |
| `Phase 4` | `TKT-007-A`, `TKT-007-B`, `TKT-007-C` | browserful / multi-step stateful oracle residual과 realism rubric operationalization |
| `Phase 5A` | `TKT-008-A1`, `TKT-008-A2`, `TKT-008-A3` | measurement surface는 도입됐고 remaining closure는 authoritative gate와 generation-path axis 쪽 |
| `Phase 5B` | `TKT-008-A*`, `TKT-008-B*` | measured gate와 summary consistency residual |
| `Phase 6A` | `TKT-008-A1`, `TKT-008-A3`, `TKT-009-A1-A/B/C` | reviewable extraction policy, generation-path gate, first promotion/live-name-only proving-ground residual |
| `Phase 6B` | `TKT-009-A*`, `TKT-009-B*` | curated registry closure residual |
| `Phase 7` | `TKT-010-A`, `TKT-010-B`, `TKT-010-C` | expansion. 현재는 defer 유지하되 unlock contract를 먼저 정의 |

## Phase Plan

### Phase 0. Decision Policy Unification

목표: `intent_met / partial / abstain / fail_closed`를 single state machine으로 고정합니다.

- `name_only` mode별 success/partial/fail-closed 기준을 하나의 policy surface로 통합합니다.
- `planning_focus_summary`, `next_required_step`, `name_only_outcome`의 중복 판단을 줄입니다.
- `dynamic/strict_dynamic`에서 `stack_defaulted`, `selection_open_world_evidence_ready=false`, `oracle execution parity missing` 상태는 `intent_met`로 올리지 않습니다.
- strict capability-gate fail-closed가 `remote_research_unavailable`와 `live_llm_unavailable` 같은 subclass를 계속 분리해 남기도록 유지합니다.

완료 조건:
- 같은 bundle에 대해 `pipeline_result=success`여도 `name_only_outcome=partial`가 왜 그런지 단일 policy로 설명됩니다.
- claim surface에서 `promotion`, `support_promotion`, `open_world_readiness`가 혼동되지 않습니다.
- low-cost no-Docker pair(`open-redirect-strict-dynamic-no-remote`, `open-redirect-strict-dynamic-stub`, `foobar-name-only-negative`)가 각각 `fail_closed/fail_closed/abstain`과 올바른 next-step/failure subclass를 계속 유지합니다.

### Phase 1. Joint Scenario Candidate IR

목표: `family_candidates[]`, `stack_candidates[]`를 넘어서 조합 가능한 candidate control-plane을 만듭니다.

- `scenario_candidates[] = {family, stack, topology, dependency_set, oracle_profile, evidence_bundle}`를 도입합니다.
- `provisional_family`, `primitive_hypotheses`, `runtime_dependency_hypotheses`, `topology_hypotheses`를 허용합니다.
- researcher/query planner가 candidate branch를 끝까지 보존하도록 바꿉니다.
- family는 runtime/oracle design의 입력이기도 하지만, 장기적으로는 selected scenario를 설명하는 projection으로 밀어냅니다.
- `candidate_score`, `contradiction_score`, `evidence_sufficiency`, `selected_by`, `abstain_reason`를 가진 explicit selection algebra를 도입해, tie-break / abstain / fail-closed 규칙이 actual selection rule로 남게 만듭니다.
- `negative_hypotheses`와 contradiction signal이 same selection rule 안에서 family/stack/topology/oracle 선택에 실제 영향을 주게 만듭니다.

완료 조건:
- misleading stack evidence, family conflict, topology-required lane이 branch-preserved state로 남습니다.
- broad phrase와 unknown-but-inducible phrase가 bounded synthetic name 하나로 즉시 닫히지 않습니다.
- `selection_decision`이 단순한 top candidate 소비가 아니라 joint candidate 선택 결과가 됩니다.
- same `selection_decision`이 왜 selected/abstain/fail_closed가 됐는지를 contradiction/evidence sufficiency/abstain reason까지 포함해 설명합니다.

### Phase 2. Typed Staged Synthesis

목표: one-shot final manifest 의존을 줄이고 intermediate repair를 가능하게 만듭니다.

필수 단계:

1. `candidate_resolution`
2. `design_brief`
3. `runtime_plan`
4. `executor_plan`
5. `oracle_contract`
6. `file_manifest`

각 단계는 typed schema, validator, repair policy, abort policy를 가집니다.
- `file_manifest`는 workspace file set(`Dockerfile`, dependency manifest, service/PoC entry, seed/init assets)과 build context를 explicit contract로 다루고, build-stage failure를 runtime/oracle failure와 분리해 남겨야 합니다.

완료 조건:
- synthesis failure가 어느 단계에서 났는지 명확히 기록됩니다.
- fallback은 stage-aware downgrade로만 허용되고, silent collapse가 줄어듭니다.
- `file_manifest`가 build-ready contract와 build-safety policy를 함께 남겨, "manifest가 있었다"와 "actual Docker bundle로 닫혔다"가 다시 섞이지 않습니다.
- representative direct rerun에서 `staged_synthesis.stage_order`가 `executor_plan`, `file_manifest`까지 실제로 남고, produced build artifact pointer가 manifest/summary에서 비어 있지 않습니다.

### Phase 2.5. Generator Controller Activation

목표: staged surface가 summary/prompt text를 넘어서 generator의 실제 branch input이 되게 만듭니다.

- `selection_decision.scenario`, `selected_oracle_mode/source`, `design_brief.required_roles`, `dependency_set`를 generator control-plane으로 승격합니다.
- `selection_decision -> chosen materializer/file/runtime/oracle branch` 인과를 machine-readable trace로 남겨, selection enrichment와 actual materialization causality를 분리합니다.
- latest bounded closure로는 `selection_branch_trace@0.1`가 generator contract/manifest/direct summary/measured support artifact에 추가돼, branch별 `selected_value`, `materialized_value`, `aligned`, rejected scenario sample, materialized file/runtime bundle을 같은 vocabulary로 남기기 시작했습니다.
- latest direct rerun 기준 comparator pair는 same trace에서 `branch_aligned=true`를 보여도 generation path는 각각 `fixture` / `stub`로 남았습니다. 즉 selection causality closure는 now separated artifact로 읽히지만, same trace alone does not prove live-positive materialization.
- `design_brief` 실패가 generic fallback으로 바로 떨어지지 않도록 role-aware retry/recovery/guard 경로를 명시화합니다.
- `required_roles` 기반 role mismatch가 candidate validation에서 직접 드러나게 만듭니다.
- `live`, `fixture`, `stub`, `degraded` generation path가 서로 다른 provider/materialization contract를 쓰게 하고, provider/model/prompt/decoding/retry/cost/cache provenance를 summary와 measured gate에 같이 남깁니다.
- latest bounded closure로는 `researcher_report`, `generator_manifest`, `generator_template`, `resolved_contract`, `reviewer_report`가 공통 `llm_execution` surface를 공유하고 `provider_backend`, `model`, `decoding_profile`, `path_class`, `fixture_path`, `last_error_retryable`, actual `prompt_contracts/prompt_invocations`, `retry_budget`, `timeout_budget`, `cost_budget`, `cache_mode`까지는 already surfaced됩니다. same `retry_budget`도 now `controller_loop_current/max`와 stage-specific planned/actual run count를 함께 담기 시작했고, `cost_budget`도 configured budget + usage token + litellm cost-map-based conservative estimate를 담기 시작했습니다. direct/operator summary도 stage retry/timeout/cost budget surface를 top-level convenience field로 읽을 수 있게 됐습니다.
- latest bounded closure로 `generation_materialization@0.1`도 single-bundle manifest/direct summary/support artifact에 들어가기 시작했습니다. same payload는 `generation_origin`, `materializer`, `path_class`, provider attempt/success, fixture/stub flag, provider/model/cache, prompt contract, retry/timeout/cost budget을 one-shot contract로 남깁니다.
- latest bounded closure로 bundle-level `support_promotion` / `open_world_readiness`도 `generation_path:not_live_positive` / `generation_path_not_live_positive`를 direct blocker로 쓰기 시작했습니다. 즉 measured chain을 열지 않아도 direct summary만으로 “selection trace는 aligned지만 live-positive contract는 아니다”를 읽을 수 있습니다.
- latest direct rerun 기준 `open-redirect-dynamic-name-only`는 same direct policy surface에서 `generation_path:provider_disabled` / `generation_path_provider_disabled`까지 같이 남깁니다. 즉 “non-live” 일반론을 넘어서 why-not-live subclass도 top-level policy wording으로 읽을 수 있습니다.
- latest bounded closure로 same why-not-live subtype vocabulary는 `support_review_index.json -> support_registry_update.json -> curated_support_registry.json:last_update` chain에도 남습니다. 따라서 blocked no-op apply가 `registry_item_count=0`로 끝나더라도 `fixture_backed` / `provider_disabled` 같은 non-live reason aggregate는 apply context에서 계속 읽을 수 있습니다.
- remaining residual은 promotion-quality cost policy / pricing governance, default/provider-policy-aware timeout closure beyond configured values, fully unified retry budget closure, first true live-positive proving-ground lane, 그리고 `live LLM + name-only + dynamic Docker` 교집합 proving-ground lane입니다.

완료 조건:
- `design_brief`가 prompt surface뿐 아니라 retry/recovery/guard classification에 실제 사용됩니다.
- `selection_decision`이 어떤 branch/materializer/file set을 열었는지 causal trace가 남아, summary-level selection truth와 actual generation branch truth가 따로 놀지 않습니다.
- `selected scenario/oracle`이 summary field가 아니라 candidate validation과 repair 경로를 바꿉니다.
- dependency-heavy/oracle-heavy brief가 서로 다른 recovery path로 흐릅니다.
- strict stub honesty lane와 live-positive materialization lane가 서로 다른 acceptance surface를 쓰고, representative positive lane에서 fixture/stub/degraded와 live-positive가 혼동되지 않습니다.
- representative positive set 안에 `live LLM + name-only + dynamic Docker` 교집합 lane가 별도 accept-path target으로 남아, 기존 fixture comparator와 degraded comparator를 동시에 통과한 것만으로 stricter claim을 대신하지 않게 합니다.

### Phase 3. Runtime/Topology Generation And Executor Parity

목표: runtime plan이 summary가 아니라 실제 실행 입력이 되게 만듭니다.

- generator가 먼저 `service + db` topology, dependency wiring, readiness order, env contract, seed/init contract를 설계합니다.
- 그 다음 executor가 별도 heuristic 재해석보다 `executor_plan`을 authoritative input으로 읽습니다.
- `service_plus_sidecar`는 operator policy 주입이 아니라 generator design 결과가 됩니다.
- generalized runtime closure는 abstract goal이 아니라 `service_only -> service_plus_db -> service_plus_supporting_sidecar -> multi_primary_web_pair -> browserful_lab_topology` 같은 representative topology class ladder로 읽히게 만듭니다.
- same topology ladder는 generation path claim과도 분리해서 읽습니다. 즉 `fixture-backed`, `degraded fallback`, future `live name-only positive`가 같은 topology rung에 있어도 같은 capability claim으로 합치지 않습니다.

권장 closure 순서:

- `Phase 3A. Contract-Stage Bounded Runtime Synthesis`
  - bounded mysql/postgres lane에서 `target_db/target_sidecars/target_topology`, `seed_files`, `service_env` defaults, provenance를 `runtime_recipe/runtime_graph/executor_plan`까지 먼저 올립니다.
  - 목적은 raw manifest metadata를 executor가 다시 해석하기 전에 contract surface가 sidecar/env/seed graph를 더 직접 제공하게 만드는 것입니다.

- `Phase 3B. Executor Provenance-Preserving Parity`
  - executor가 contract가 이미 합성한 `sidecars`, `service_env`, `seed_files`, `sidecars_source`, `service_env_source`를 덜 덮어쓰고 그대로 execution surface에 유지하게 만듭니다.
  - 목적은 contract-stage bounded synthesis와 executor summary/execution 간 provenance drift를 줄이는 것입니다.

- `Phase 3C. Generalized Runtime Closure`
  - bounded mysql/postgres lane를 넘어서 `dependency order`, `generalized seed-init DSL`, `volume/env contract semantics`, `network lifecycle`, richer `runtime_graph` execution을 닫습니다.
  - 이 단계가 끝나야 `runtime_graph` 또는 richer `executor_plan`을 true executable control-plane이라고 볼 수 있습니다.

완료 조건:
- `runtime_plan`과 실제 container graph의 drift가 줄어듭니다.
- single-service 외의 대표 lane이 contract-driven으로 실행됩니다.
- `dependency order`, `seed/init`, `volume/env contract`, `network lifecycle`이 heuristic/policy fallback이 아니라 runtime/executor plan에서 설명됩니다.
- `runtime_graph` 또는 richer `executor_plan`이 executable control-plane 역할을 합니다.
- representative topology class ladder의 각 단계에 대해 first validation lane과 remaining blocker가 explicit하게 남습니다.

### Phase 4. Oracle Execution Parity

목표: quality와 intent fidelity를 metadata가 아니라 executed oracle로 평가합니다.

- verifier가 negative control, forbidden-success, metamorphic replay를 실제 실행합니다.
- `artifact_quality`는 oracle metadata richness가 아니라 executed oracle richness를 읽도록 바꿉니다.
- strict_dynamic은 independent verifier 요구를 명시적으로 검사합니다.
- representative compiler/native lane과 deterministic fallback lane에서도 `run_passed/verify_pass`와 `oracle_execution_parity` 사이의 gap을 줄입니다.
- representative stateless/body-structured/sessionful payload-replay lane이 닫힌 뒤 남는 residual은 broader multi-step/browser stateful oracle replay와 richer realism rubric입니다.
- current near-term residual은 now `csrf` single-flow demo를 넘는 broader browserful/sessionful state transition oracle closure입니다.
- `exploit_path_diversity`, `statefulness`, `victim_realism`, `environment_fidelity`, `verifier_independence`, `cleanup_reproducibility` 같은 explicit realism rubric axis를 정의하고 same rubric이 `artifact_quality`, measured gate, support review에서 같은 vocabulary를 쓰게 만듭니다.

완료 조건:
- `negative_controls`와 `metamorphic`가 문서 속 필드가 아니라 실제 평가 경로가 됩니다.
- open-world readiness와 support claim이 더 보수적이고 설명 가능해집니다.
- representative direct execution에서 `run_passed=true`, `verify_pass=true`인 lane이 `oracle_execution_parity=missing`으로 대량 잔존하지 않습니다.
- representative stateless/body-structured/sessionful fallback lane을 넘어서 broader multi-step/browser stateful oracle lane까지 execution parity를 확장할 다음 residual이 명확합니다.
- realism rubric axis와 threshold가 explicit하고, same threshold가 quality tier / measured gate / support promotion 해석에 같이 반영됩니다.

### Phase 5A. Eval Matrix And Performance Surface

목표: generalized capability를 체계적으로 측정하고 researcher 병목을 줄입니다.

필수 matrix 축:

- family known vs unknown
- alias/paraphrase vs broad phrase
- stack known vs conflicting evidence
- single-service vs multi-service required
- high-authority vs low-authority evidence
- low-conflict vs family-conflict evidence
- oracle-simple vs oracle-stateful difficulty
- generation path: `live` vs `fixture` vs `stub` vs `degraded`
- strict no-remote lane

성능 작업:

- query cache
- early stop budget

완료 조건:
- open-world regression이 scenario collection이 아니라 matrix로 측정됩니다.
- representative dynamic lane의 RESEARCH 비용이 구조적으로 줄어듭니다.

### Phase 5B. Measurement Closure

목표: 도입된 matrix/performance surface를 authoritative regression gate에 가깝게 닫습니다.

- snippet reuse를 추가합니다.
- evidence graph reuse를 추가합니다.
- representative lane별 perf comparison을 넣습니다.
- CI-level matrix/perf gate를 강화합니다.
- same measured surface가 `live` / `fixture` / `stub` / `degraded` generation path를 explicit axis로 읽게 만들어, LLM-shaped positive와 true live-positive를 gate에서 다시 섞지 않게 합니다.
- pipeline-level authoritative measurement gate와 harness-level measured artifact의 경계를 줄입니다.
- representative executed lane에 대한 qualitative artifact review/rubric을 넣어, runnable success와 thin fallback demo를 더 명시적으로 구분합니다.
- representative compiler/native bounded lane과 representative deterministic fallback lane의 quality tier를 명시적으로 분리합니다. 즉 `oracle_execution_parity=high`와 `artifact_quality.band=high`를 같은 축으로 취급하지 않습니다.
- `artifact_quality.qualitative_tier`, `artifact_quality.qualitative_review`, aggregate `by_qualitative_tier` 같은 explicit surface를 regression gate가 읽을 수 있게 만듭니다.
- strict fail-closed lane의 `planning_only` tier도 explicit category로 유지해, quality 부족과 generated artifact 부재를 같은 bucket으로 섞지 않게 합니다.
- representative bounded compiler/native lane에서 `name_only_outcome=intent_met`여도 `open_world_ready/support_promotion=false`가 유지될 수 있음을 gate에 명시해, intent satisfaction과 generalized support/open-world claim을 다시 섞지 않게 합니다.
- same measured/support preview workflow에서도 `mechanically_blocked` vs `mechanically_healthy_policy_blocked`와 case-level reviewability vocabulary가 유지되게 만들어, measured gate interpretation과 review workflow interpretation이 다른 token을 쓰지 않게 합니다.
- latest bounded closure로 `repeatability_report.json` / `matrix_report.json` / `support_review_index.json`도 `generation_path_observations`, `generation_path_gate`, `by_generation_path_class`, `by_generation_positive_bucket`, `live_positive_ready_bundle_count`를 surface하기 시작했습니다. 따라서 same preview chain은 now `fixture_backed_positive` / `degraded_fallback_positive` / future `live_positive`를 operator-facing aggregate에서도 분리해 읽습니다.
- latest measured closure로 same repeatability/matrix surface는 `observed_generation_non_live_reasons`, `primary_non_live_reason`, `by_non_live_reason`, `by_primary_non_live_reason`도 같이 보존합니다. 따라서 `fixture_backed`와 `provider_disabled` 같은 why-not-live subtype이 support review 전 단계에서도 그대로 읽힙니다.
- top-level summary projection과 nested truth surface(`terminal_failure_class`, stage ceiling, failure reason 등)의 residual drift를 줄여 operator-facing summary consistency를 높입니다. 이 residual은 now executed single-bundle lane의 core verdict sync나 uniform `planning_only`/pre-generation lane보다, broader multi-bundle convenience projection과 authoritative measured gate 쪽으로 더 좁혀집니다.
- capability-gate failure 같은 early-stop lane에서도 `search_*` performance fields를 `0/false` default로 정규화해 measured-case summary consistency를 높입니다.
- representative executed single-bundle lane의 `run_passed`, `verify_pass`, `oracle_execution_parity`, `oracle_execution_attempted` alignment를 유지하고, uniform `planning_only`/pre-generation lane의 core verdict projection도 유지하면서, 남은 summary consistency work는 mainly mixed multi-bundle convenience projection drift와 authoritative measured gate를 줄이는 쪽으로 좁힙니다.
- operational backlog 기준으로는 same residual을 `TKT-008-B1 mixed multi-bundle projection consistency`와 `TKT-008-B2 authoritative measured-gate handoff`로 나눠 추적합니다.
- latest bounded closure로 mixed multi-bundle lane도 top-level `*_rollup` token을 통해 verdict/failure 상태를 더 직접 읽을 수 있게 되었으므로, same residual은 now token surface 부재보다 precedence/authority 정리 쪽에 더 가깝습니다.
- latest bounded closure로 `verdict_authority`도 같이 surface되기 시작했으므로, same residual은 이제 top-level convenience projection과 nested bundle truth의 precedence를 measured gate에서 어떻게 소비할지 정리하는 문제에 더 가깝습니다.

완료 조건:
- matrix/tagging/rollup이 current case collection 기록을 넘어서 representative regression 판단에 직접 쓰입니다.
- cache/early-stop 효과가 one-off sample이 아니라 repeatable comparison으로 읽힙니다.
- representative direct execution artifact가 “native/compiler-quality”, “bounded sidecar parity success”, “thin deterministic fallback”, “planning-only fail-closed”로 최소 구분됩니다.
- same measured surface가 `live-positive`, `fixture-backed positive`, `degraded fallback positive`를 separate generation-path bucket으로 읽습니다.
- representative fallback lane이 `oracle_execution_parity=high`여도 quality tier가 자동 상승하지 않도록 rubric과 gate가 명시됩니다.
- representative bounded compiler/native lane이 `intent_met`여도 generalized open-world/support-ready로 자동 승격되지 않도록 summary와 gate가 유지됩니다.
- representative executed single-bundle summary는 runtime fact/provenance뿐 아니라 core execution/oracle verdict도 nested bundle truth와 좁게 정렬됩니다.
- remaining summary consistency residual은 mixed multi-bundle convenience projection과 stronger authoritative measurement gate에 더 집중되며, operationally는 `TKT-008-B1/B2`로 나뉩니다.
- planning-only no-Docker pair에서 `authority_ready_bundle_count > 0`이더라도 same measured lane가 `measured_gate_blocked_bundle_count > 0`, `reviewable_bundle_count = 0`로 남는 current policy가 계속 분리돼 읽힙니다.

### Phase 6A. Support Candidate Extraction

목표: truly support-ready bundle만 curated support candidate로 승격합니다.

- `primitive_signature`, `runtime_contract`, `oracle_contract`, `unsafe_pattern` 추출 규칙을 정의합니다.
- support promotion은 executed oracle parity와 eval matrix 통과를 전제로 합니다.
- bounded fallback artifact는 runnable하더라도 promotion 대상에서 계속 배제합니다.
- “first promotable proving ground”를 abstract lane이 아니라 representative positive lane 집합으로 고정합니다. 최소한 하나의 LLM-shaped lane와 하나의 dynamic name-only lane이 separate accept-path target으로 남아야 하고, stricter reading용 `live LLM + name-only + dynamic Docker` 교집합 lane도 explicit proving-ground target으로 남아야 합니다.

완료 조건:
- `support_promotion`이 honesty surface를 넘어 reviewable extraction path가 됩니다.
- representative positive proving-ground lane가 무엇인지와 왜 reviewable/non-reviewable인지가 current support workflow에서 직접 읽힙니다.

### Phase 6B. Curated Registry Closure

목표: extraction/review/update preview를 실제 curated support registry workflow로 닫습니다.

- accepted candidate를 registry schema에 write/merge합니다.
- review decision과 provenance/history를 남깁니다.
- measured/manual review surface를 reusable promotion workflow로 승격합니다.
- blocked/no-op apply path와 actual reviewable accept path를 모두 representative workflow로 검증합니다.
- representative high-quality lane가 promotion policy blocker 때문에 reviewable path에서 떨어지는 경우도 measured/support gate policy로 명확히 분리합니다.
- representative `blocked_mixed` lane와 blocked/no-op apply path도 same support-status vocabulary로 direct workflow에서 검증합니다.
- sparse older local registry item도 current lifecycle/status/provenance schema로 normalize할 수 있게 합니다.
- same schema upgrade가 어떤 field/reason으로 발생했는지도 local registry surface에서 직접 읽을 수 있게 합니다.
- same schema evolution을 item뿐 아니라 historical update context까지 유지합니다.
- same schema evolution을 top-level historical decision trace까지 유지합니다.
- same registry maintenance 상태를 single `schema_status` token으로도 읽을 수 있게 합니다.
- same maintenance 상태를 nested item/update/decision record에서도 직접 읽을 수 있게 합니다.
- same `support_review_index.json -> support_registry_update.json -> curated_support_registry.json` chain이 case-level aggregate와 explicit case list vocabulary를 잃지 않게 합니다.
- representative proving-ground lane 중 최소 하나는 non-empty accepted local registry item을 materialize하는 direct workflow로 닫고, remaining positive lane는 explicit blocker set과 함께 계속 measured gate에 남겨 둡니다.

완료 조건:
- preview artifact가 아니라 실제 curated registry update가 가능합니다.
- accept/reject history와 artifact provenance가 추적 가능합니다.
- review/update/current-state artifact가 같은 case-level vocabulary와 status split으로 읽힙니다.
- low-cost no-Docker blocked/no-op pair가 empty decision apply 후에도 `registry_item_count = 0`, `schema_status = normalized` empty local registry로 끝나며 false promotion을 만들지 않습니다.
- representative positive proving-ground lane가 “왜 아직 blocked인가 / 왜 이제 reviewable인가”를 same vocabulary로 설명합니다.

### Phase 7. Expansion

목표: family/stack 수를 늘리기 전에 runtime/oracle/eval parity가 확보된 토대 위에서 확장합니다.

- `family count`보다 `runtime class`, `dependency class`, `topology class`, `oracle class` 확장을 우선합니다.
- Python 밖으로 나가기 전, 현재 Python lane에서 intent fidelity와 executor parity를 먼저 안정화합니다.
- expansion을 열기 전 선행 prerequisite bundle을 explicit unlock contract로 정의합니다.

완료 조건:
- 확장된 family/stack이 기존 claim surface와 동일한 rigor로 측정됩니다.
- unlock contract 없이 family/stack/runtime-class count를 늘리지 않습니다.

## Acceptance Gates

각 phase는 아래를 만족해야 다음 phase로 넘어갑니다.

- Phase 0: mode별 decision policy가 문서와 summary surface에서 일치함
- Phase 0: low-cost no-Docker pair가 `fail_closed/fail_closed/abstain`과 correct capability/semantic boundary를 유지함
- Phase 0: strict live-LLM fail-closed honesty와 positive LLM-shaped Docker materialization claim을 서로 다른 acceptance question으로 계속 분리해 읽음
- Phase 1: branch-preserved candidate IR이 summary와 downstream input에 roundtrip됨
- Phase 1: scenario selection algebra가 tie-break / contradiction / abstain reason / negative hypothesis consumption까지 explicit하게 남음
- Phase 2: stage별 typed artifacts와 repair policy가 기록되고, `file_manifest`가 build-ready/built-safe contract로 따로 검증됨
- Phase 2.5: staged surface가 generator retry/recovery/guard path를 실제로 바꿈
- Phase 2.5: live/fixture/stub/degraded generation provenance가 분리되고 live-positive path가 별도 acceptance surface를 가짐
- Phase 2.5: `selection_decision -> materialization branch` causal trace가 summary와 generator artifact에 같이 남음
- Phase 3: executor가 runtime/executor plan을 주 입력으로 사용하고 dependency order/seed-init/volume-network residual이 주요 blocker가 아님
- Phase 3A: bounded mysql/postgres lane에서 contract surface가 `sidecars`, `service_env`, `seed_files`, `target_*`를 executor 전에 합성함
- Phase 3B: executor execution surface와 run summary가 contract-synthesized provenance(`sidecars_source`, `service_env_source`)를 보존함
- Phase 3C: dependency order/seed-init/volume-network residual이 bounded exception이 아니라 generalized runtime contract로 설명됨
- Phase 4: verifier가 negative/metamorphic를 실제 실행함
- Phase 4: realism rubric axis와 threshold가 explicit하고 measured/support gate vocabulary와 정렬됨
- Phase 5A: eval matrix, repeatability report, performance cache가 운영되고 generation-path axis가 explicit하게 측정됨
- Phase 5B: matrix/perf surface가 stronger regression gate로 읽힘
- Phase 5B: authority handoff와 measured/promotion gate split이 planning-only pair에서도 계속 분리돼 읽힘
- Phase 6A: promotion package가 reviewable artifact로 추출됨
- Phase 6A: `live LLM + name-only + dynamic Docker` 교집합 proving-ground lane가 existing comparator lane와 분리된 accept-path target으로 읽힘
- Phase 6B: review/update preview가 실제 registry workflow로 닫힘
- Phase 6B: blocked/no-op pair가 false promotion 없이 empty local registry로 닫힘
- Phase 6B: representative positive proving-ground lane 중 최소 하나가 accepted local registry item으로 닫힘
- Phase 7: expansion unlock contract가 explicit하게 충족되기 전까지 expansion backlog가 상향되지 않음

## Acceptance-To-Validation Translation

phase acceptance를 실제 검증 surface에 연결할 때는 아래 대응을 따른다.

| Phase | First validation surface | Representative check | Notes |
| --- | --- | --- | --- |
| `Phase 0` | `tests/test_name_only_helpers.py`, `tests/test_pack_promotion.py` | `open-redirect-strict-dynamic-no-remote`, `open-redirect-strict-dynamic-stub`, `foobar-name-only-negative` direct rerun | decision policy와 operator-facing outcome wording, fail-closed subclass split을 본다 |
| `Phase 1` | `tests/test_researcher_search_artifacts.py`, `tests/test_contract_resolution.py` | representative non-SQLi name-only direct rerun | branch-preserved candidate IR와 scenario/evidence authority surface를 본다 |
| `Phase 2` | `tests/test_synthesis_prompt_contract.py`, `tests/test_synthesis_semantic_guard.py`, `tests/test_synthesis_fallback_poc.py` | semantic-guided dynamic rerun, `trusted-dynamic-sqli` | staged artifact persistence, repair-first, downgrade journal, `file_manifest`/build contract, fixture-backed positive synthesis quality를 같이 본다 |
| `Phase 2.5` | `tests/test_generator_template_planner.py`, `tests/test_run_pipeline_failure_resolution.py` | non-SQLi bounded lane direct rerun, `trusted-dynamic-sqli` provenance check | staged surface가 generator branching/recovery를 실제로 바꾸는지, selection-to-materialization causal trace가 남는지, live/fixture/stub/degraded provenance가 분리되는지를 같이 본다 |
| `Phase 3A` / `3B` | `tests/test_contract_resolution.py`, `tests/test_executor_poc_exec.py`, `tests/test_run_case_summary_surface.py` | representative single-service / bounded sidecar rerun | contract-stage bounded runtime synthesis와 executor provenance parity를 본다 |
| `Phase 3C` | `tests/test_runtime_rules.py`, `tests/test_runtime_surface.py`, `tests/e2e/test_cases.py` | ordered dependency / sidecar / seed lane rerun, `open-redirect-dynamic-name-only`, `trusted-dynamic-sqli`, `sqli-sidecar-compiler-custom-env` | generalized runtime closure 본체다. latest representative lane는 Docker-enabled rerun으로 실제 runtime path를 보되, fallback/fixture truth와 bounded sidecar comparator를 generalized closure와 혼동하지 않는다 |
| `Phase 4` | `tests/test_rule_based_semantic_contract.py`, `tests/test_llm_assisted_verifier.py` | representative stateful / richer oracle rerun, `csrf-dynamic-name-only` | executed oracle parity와 realism rubric integration을 본다. `csrf-dynamic-name-only`는 sessionful single-flow comparator고, browserful proving ground와는 별도로 읽는다 |
| `Phase 5A` / `5B` | `tests/test_repeatability_gate.py`, `tests/e2e/test_case_matrix_rollup.py` | `repeat_case.py`, `matrix_report.py`, `ops/ci/run_repeatability_chain.sh`, `ops/ci/run_repeatability_matrix_check.sh`, `ops/ci/run_measured_gate_operator_baseline.sh`, latest planning-only pair(`foobar-name-only-negative`, `open-redirect-strict-dynamic-no-remote`), representative positive pair(`trusted-dynamic-sqli`, `open-redirect-dynamic-name-only`) | measured gate preview와 matrix/perf closure, authority-vs-measured split, generation-path axis 분리를 본다. positive lane가 실행돼도 measured gate blocked로 남고 current truth는 still `runnable but not promotable`일 수 있음을 같이 본다. concrete command chain은 [tests/e2e/README.md](../tests/e2e/README.md)의 `Generic Repeatability Chain`, `Repeatability Matrix Check`, `Measured Gate Operator Baseline`, `Positive Pair Promotion Check`를 따른다. blocked lane의 `repeat_case.py` nonzero-with-report는 helper에서도 review 단계까지 계속 진행되고 transient docker readiness retry도 유지된다. sandbox helper run에서 `docker daemon permission denied`가 보이면 permission-artifact note를 남기고, unrestricted Docker-enabled helper rerun에서는 same helper projection이 다시 manual truth와 정렬된다. 다만 current workspace-local direct verification에서는 same sandbox helper output이 empty aggregate(`authority_ready_bundle_count=0`, `reviewable_bundle_count=0`, `by_support_status={}`)로 끝날 수도 다시 확인됐고 helper per-case repeatability도 `case_failed`, `quality_tier_inconsistent`, `verdict_authority_inconsistent`까지 남길 수 있었으므로, same output은 runtime-equivalent truth가 아니라 permission-artifact environment output으로 읽고 unrestricted rerun 또는 manual chain을 우선한다. same latest finding은 새 core ticket이 아니라 `TKT-008-B3` companion slice로만 귀속한다 |
| `Phase 6A` / `6B` | `tests/test_support_extract.py`, `tests/e2e/test_support_workflow.py` | `support_review.py -> support_decide.py -> support_apply.py`, `ops/ci/run_support_review_chain.sh`, `ops/ci/run_support_workflow_chain.sh`, latest blocked/no-op pair(`foobar-name-only-negative`, `open-redirect-strict-dynamic-no-remote`), positive support review(`trusted-dynamic-sqli`, `open-redirect-dynamic-name-only`), bounded comparator review(`sqli-sidecar-compiler-custom-env`) | reviewable extraction과 curated registry workflow closure, blocked/no-op false-promotion safety를 본다. positive lane의 `authority_ready != reviewable`과 current `runnable but not promotable` truth도 같이 확인하고, `trusted-dynamic-sqli` / `open-redirect-dynamic-name-only`를 first promotion proving-ground comparator로, future `live LLM + name-only + dynamic Docker` lane를 stricter accept-path target으로, `sqli-sidecar-compiler-custom-env`를 high-quality bounded comparator로 읽는다. concrete command chain은 [tests/e2e/README.md](../tests/e2e/README.md)의 `Generic Support Workflow Chain`, `Generic Support Review Chain`, `Positive Pair Promotion Check`를 따른다. helper contract green과 review continuation semantics는 유지되며, unrestricted Docker-enabled helper rerun에서는 positive blocked-lane aggregate truth도 다시 manual chain과 정렬된다. 다만 current workspace-local direct verification에서는 same sandbox helper output이 empty aggregate(`authority_ready_bundle_count=0`, `reviewable_bundle_count=0`, `by_support_status={}`)로 끝날 수도 다시 확인됐고 helper per-case repeatability도 `case_failed`, `quality_tier_inconsistent`, `verdict_authority_inconsistent`까지 남길 수 있었으므로, same output은 runtime-equivalent truth가 아니라 permission-artifact environment output으로 읽고 unrestricted rerun 또는 manual chain을 우선한다. same latest finding은 새 core ticket이 아니라 `TKT-008-B3` companion residual로만 본다 |
| `Phase 7` | roadmap review, residual review, gate review | no direct harness first | expansion은 runtime/oracle/eval closure review 이후에만 올린다 |

구체적인 harness 진입 순서와 읽는 순서는 [docs/work_tickets.md](work_tickets.md)의 `Validation Routing` / `Validation Reading Order`, 그리고 [tests/e2e/README.md](../tests/e2e/README.md)를 따른다.

## Explicit Deferrals

아래는 상위 phase가 끝나기 전까지 우선순위를 올리지 않습니다.

- family 수만 늘리는 작업
- 새로운 stack 수만 늘리는 작업
- prettier artifact scoring
- generalized support claim 확대
- review/update preview를 generalized support pipeline으로 읽는 작업
- matrix rollup만으로 generalized capability proof를 주장하는 작업
- bounded mysql/postgres lane 개선을 generalized multi-service/runtime planner로 읽는 작업

## How To Update This Document

- phase ordering, acceptance gate, sequencing rule이 바뀔 때만 갱신한다.
- current rerun 결과나 workspace-local verification delta는 여기 적지 않고 [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)로 보낸다.
- implementation-sized subtask decomposition은 [docs/work_tickets.md](work_tickets.md)로 보낸다.
- current non-claim과 운영 전제는 [docs/constraints.md](constraints.md)로 보낸다.
- validation harness command family나 rerun entrypoint가 바뀌면 [tests/e2e/README.md](../tests/e2e/README.md), [docs/work_tickets.md](work_tickets.md)의 validation routing과 같이 맞춘다.
- phase acceptance와 validation surface의 대응이 바뀌면 `Acceptance-To-Validation Translation`도 같이 갱신한다.
- completion companion 관계나 completion reading order가 바뀌면 [docs/work_tickets.md](work_tickets.md), [README.md](../README.md)와 같이 맞춘다.
- priority companion 관계나 priority reading order가 바뀌면 [docs/work_tickets.md](work_tickets.md), [README.md](../README.md)와 같이 맞춘다.
- 잔여 작업량/turn envelope 해석이 바뀌면 [docs/work_tickets.md](work_tickets.md)의 `Estimated Turn Envelope`와 README/handbook/code/e2e companion의 priority routing도 같이 맞춘다.
- [docs/work_tickets.md](work_tickets.md)의 `Turn Estimate Entry`가 바뀌면 README/handbook/code/e2e companion의 same shortcut도 같이 맞춘다.
- LLM-response stricter reading의 roadmap/acceptance 해석이 바뀌면 [docs/work_tickets.md](work_tickets.md)의 `LLM-Response Capability Overlay`와 같이 맞춘다.
- latest positive representative pair의 ticket-form 해석이 바뀌면 [docs/work_tickets.md](work_tickets.md)의 `Assessment-To-Ticket Interpretation`와 같이 맞춘다.
- review mode entry shortcut이 바뀌면 [docs/work_tickets.md](work_tickets.md), [README.md](../README.md)와 같이 맞춘다.

## Default Assumptions

- `compatibility` mode는 regression value를 유지하기 위해 lower-bound closure를 계속 허용합니다.
- `dynamic`와 `strict_dynamic`는 lower-bound closure를 generalized success로 읽지 않습니다.
- current codebase의 단기 ROI는 expansion이 아니라 control-plane, runtime parity, oracle execution parity에 있습니다.
- measured/manual support workflow(`Phase 6B`)는 `Phase 3C` residual보다 앞서지 않습니다. runtime/oracle parity 잔여를 닫기 전 registry closure를 먼저 올리지 않습니다.
