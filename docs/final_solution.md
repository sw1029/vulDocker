# vulDocker 구현 로드맵

Status: canonical
Audience: mixed
Source of truth for: implementation priority, phase ordering, acceptance gates
Not the source of truth for: current rerun evidence, active constraints, operator quickstart
Last validated against: current code structure and rerun-backed assessment on 2026-03-14

이 문서는 `name only` intent fidelity와 generalized open-world readiness를 높이기 위한 phase-based roadmap입니다. 현재 baseline을 재서술하지 않고, 어떤 순서로 무엇을 바꿀지와 각 phase의 완료 조건만 정의합니다.

관련 문서:
- 문제 정의와 success criteria: [docs/problem.md](problem.md)
- 현재 rerun-backed truth: [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)
- 현재 제약과 금지 claim: [docs/constraints.md](constraints.md)
- 운영/명령/아티팩트: [docs/handbook.md](handbook.md)

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
4. runtime/topology generation + executor parity
5. oracle execution parity
6. eval matrix + performance reuse
7. support promotion extraction
8. family/runtime expansion

## Phase Plan

### Phase 0. Decision Policy Unification

목표: `intent_met / partial / abstain / fail_closed`를 single state machine으로 고정합니다.

- `name_only` mode별 success/partial/fail-closed 기준을 하나의 policy surface로 통합합니다.
- `planning_focus_summary`, `next_required_step`, `name_only_outcome`의 중복 판단을 줄입니다.
- `dynamic/strict_dynamic`에서 `stack_defaulted`, `selection_open_world_evidence_ready=false`, `oracle execution parity missing` 상태는 `intent_met`로 올리지 않습니다.

완료 조건:
- 같은 bundle에 대해 `pipeline_result=success`여도 `name_only_outcome=partial`가 왜 그런지 단일 policy로 설명됩니다.
- claim surface에서 `promotion`, `support_promotion`, `open_world_readiness`가 혼동되지 않습니다.

### Phase 1. Joint Scenario Candidate IR

목표: `family_candidates[]`, `stack_candidates[]`를 넘어서 조합 가능한 candidate control-plane을 만듭니다.

- `scenario_candidates[] = {family, stack, topology, dependency_set, oracle_profile, evidence_bundle}`를 도입합니다.
- `provisional_family`, `primitive_hypotheses`, `runtime_dependency_hypotheses`, `topology_hypotheses`를 허용합니다.
- researcher/query planner가 candidate branch를 끝까지 보존하도록 바꿉니다.
- family는 runtime/oracle design의 입력이기도 하지만, 장기적으로는 selected scenario를 설명하는 projection으로 밀어냅니다.

완료 조건:
- misleading stack evidence, family conflict, topology-required lane이 branch-preserved state로 남습니다.
- broad phrase와 unknown-but-inducible phrase가 bounded synthetic name 하나로 즉시 닫히지 않습니다.
- `selection_decision`이 단순한 top candidate 소비가 아니라 joint candidate 선택 결과가 됩니다.

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

완료 조건:
- synthesis failure가 어느 단계에서 났는지 명확히 기록됩니다.
- fallback은 stage-aware downgrade로만 허용되고, silent collapse가 줄어듭니다.

### Phase 3. Runtime/Topology Generation And Executor Parity

목표: runtime plan이 summary가 아니라 실제 실행 입력이 되게 만듭니다.

- generator가 먼저 `service + db` topology, dependency wiring, readiness order, env contract, seed/init contract를 설계합니다.
- 그 다음 executor가 별도 heuristic 재해석보다 `executor_plan`을 authoritative input으로 읽습니다.
- `service_plus_sidecar`는 operator policy 주입이 아니라 generator design 결과가 됩니다.

완료 조건:
- `runtime_plan`과 실제 container graph의 drift가 줄어듭니다.
- single-service 외의 대표 lane이 contract-driven으로 실행됩니다.

### Phase 4. Oracle Execution Parity

목표: quality와 intent fidelity를 metadata가 아니라 executed oracle로 평가합니다.

- verifier가 negative control, forbidden-success, metamorphic replay를 실제 실행합니다.
- `artifact_quality`는 oracle metadata richness가 아니라 executed oracle richness를 읽도록 바꿉니다.
- strict_dynamic은 independent verifier 요구를 명시적으로 검사합니다.

완료 조건:
- `negative_controls`와 `metamorphic`가 문서 속 필드가 아니라 실제 평가 경로가 됩니다.
- open-world readiness와 support claim이 더 보수적이고 설명 가능해집니다.

### Phase 5. Eval Matrix And Performance Reuse

목표: generalized capability를 체계적으로 측정하고 researcher 병목을 줄입니다.

필수 matrix 축:

- family known vs unknown
- alias/paraphrase vs broad phrase
- stack known vs conflicting evidence
- single-service vs multi-service required
- high-authority vs low-authority evidence
- low-conflict vs family-conflict evidence
- oracle-simple vs oracle-stateful difficulty
- strict no-remote lane

성능 작업:

- query cache
- evidence graph reuse
- snippet reuse
- early stop budget

완료 조건:
- open-world regression이 scenario collection이 아니라 matrix로 측정됩니다.
- representative dynamic lane의 RESEARCH 비용이 구조적으로 줄어듭니다.

### Phase 6. Support Promotion Extraction

목표: truly support-ready bundle만 curated support candidate로 승격합니다.

- `primitive_signature`, `runtime_contract`, `oracle_contract`, `unsafe_pattern` 추출 규칙을 정의합니다.
- support promotion은 executed oracle parity와 eval matrix 통과를 전제로 합니다.
- bounded fallback artifact는 runnable하더라도 promotion 대상에서 계속 배제합니다.

완료 조건:
- `support_promotion`이 honesty surface를 넘어 reviewable extraction path가 됩니다.

### Phase 7. Expansion

목표: family/stack 수를 늘리기 전에 runtime/oracle/eval parity가 확보된 토대 위에서 확장합니다.

- `family count`보다 `runtime class`, `dependency class`, `topology class`, `oracle class` 확장을 우선합니다.
- Python 밖으로 나가기 전, 현재 Python lane에서 intent fidelity와 executor parity를 먼저 안정화합니다.

완료 조건:
- 확장된 family/stack이 기존 claim surface와 동일한 rigor로 측정됩니다.

## Acceptance Gates

각 phase는 아래를 만족해야 다음 phase로 넘어갑니다.

- Phase 0: mode별 decision policy가 문서와 summary surface에서 일치함
- Phase 1: branch-preserved candidate IR이 summary와 downstream input에 roundtrip됨
- Phase 2: stage별 typed artifacts와 repair policy가 기록됨
- Phase 3: executor가 runtime/executor plan을 주 입력으로 사용함
- Phase 4: verifier가 negative/metamorphic를 실제 실행함
- Phase 5: eval matrix와 performance cache가 운영됨
- Phase 6: promotion package가 reviewable artifact로 추출됨

## Explicit Deferrals

아래는 상위 phase가 끝나기 전까지 우선순위를 올리지 않습니다.

- family 수만 늘리는 작업
- 새로운 stack 수만 늘리는 작업
- prettier artifact scoring
- generalized support claim 확대

## Default Assumptions

- `compatibility` mode는 regression value를 유지하기 위해 lower-bound closure를 계속 허용합니다.
- `dynamic`와 `strict_dynamic`는 lower-bound closure를 generalized success로 읽지 않습니다.
- current codebase의 단기 ROI는 expansion이 아니라 control-plane, runtime parity, oracle execution parity에 있습니다.
