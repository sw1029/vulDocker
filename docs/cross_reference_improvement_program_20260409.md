# Cross-Reference Improvement Program

작성일: 2026-04-09
상태: proposed
성격: implementation plan / issue decomposition source of truth

## 1. 목적

이 문서는 `claude-leak`, `everything-claude-code`, 그리고 현재 `vulDocker` 구현의 비교 분석을 바탕으로, 현재 레포의 로직 품질, 하네스, 측정/보정, operator-facing control-plane을 전반적으로 개선하기 위한 상세 구현계획이다.

이 문서의 목적은 다음 네 가지다.

1. 외부 참고 구현에서 실제로 가져올 구조적 요소를 명확히 고정한다.
2. 현재 레포의 어떤 코드 경로에 어떤 방식으로 적용할지 decision-complete 수준으로 매핑한다.
3. 구현 순서를 의존성 기준으로 분해한다.
4. 즉시 발급 가능한 GitHub issue 구조를 제공한다.

이 문서는 기존 canonical backlog를 대체하지 않는다.

- 기존 canonical backlog: [work_tickets.md](/home/ysw/vulDocker/docs/work_tickets.md)
- 기존 roadmap: [final_solution.md](/home/ysw/vulDocker/docs/final_solution.md)
- current truth: [current_state_gap_analysis.md](/home/ysw/vulDocker/docs/current_state_gap_analysis.md)
- current non-claim boundary: [constraints.md](/home/ysw/vulDocker/docs/constraints.md)

이번 프로그램은 기존 `TKT-*` 체계 바깥의 별도 implementation program으로 관리하되, 각 workstream과 issue에서 관련 `TKT-*`를 reference only로 명시한다.

## 2. 출발점과 핵심 판단

### 2.1 현재 레포의 구조적 강점

현재 레포는 이미 아래 control-plane을 갖고 있다.

- `orchestrator/run_pipeline.py`
  - `RESEARCH -> GENERATOR -> EXECUTOR -> VERIFY -> REVIEW -> PACK`
- `common/contracts.py`
  - `request_ir`
  - `selection_decision`
  - `scenario_candidates`
  - `runtime_recipe`
  - `runtime_graph`
  - `executor_plan`
  - `evidence_graph`
  - `staged_synthesis`
- `executor/runtime/docker_local.py`
  - `runtime_graph` / `executor_plan` 기반 runtime validation + execution surface synthesis
- `tests/e2e/README.md`
  - direct run / repeatability / support review / measured gate / operator baseline 하니스

즉 현재 레포는 도메인 실행 파이프라인과 executable runtime contract는 이미 강하다.

### 2.2 현재 레포의 구조적 약점

현재 레포의 약점은 “도구가 없다”가 아니라 다음이다.

1. 내부 action-level control-plane이 아직 거칠다.
2. `selection -> materialization -> execution -> verification`의 causality trace가 충분히 explicit하지 않다.
3. validation/gate logic가 여러 위치에 흩어져 있다.
4. raw artifact는 많지만 operator-facing canonical read model이 약하다.
5. 반복 실패를 structured observation으로 축적하고 health/report로 되돌리는 계층이 약하다.
6. reviewer/verifier의 evidence contract가 아직 충분히 공격적이지 않다.

### 2.3 외부 비교 구현에서 가져올 것과 가져오지 않을 것

#### `claude-leak`에서 가져올 것

- tool/action metadata 중심 execution contract
- concurrency-safe / read-only / interrupt behavior 같은 action semantics
- specialized verification contract
- streaming/abort/sibling-cancel에서의 failure attribution discipline

#### `claude-leak`에서 가져오지 않을 것

- Bridge / IDE / Chrome 연동
- plugin/marketplace ecosystem
- fail-open product service layer
- 범용 MCP platformization 자체

#### `everything-claude-code`에서 가져올 것

- deterministic harness audit
- declarative hook/event gate 철학
- canonical session/run snapshot adapter
- observation/state-store 기반 health/eval layer
- eval/verification workflow formalization

#### `everything-claude-code`에서 가져오지 않을 것

- massive skill/agent catalog
- cross-harness install system 전체
- tmux operator workspace 전체
- ECC2 TUI 그 자체

### 2.4 프로그램의 핵심 목표

이 프로그램의 목표는 아래 세 줄로 요약된다.

1. `runtime_graph` 이전 단계의 `internal action graph`를 추가한다.
2. pipeline 전체의 gate/audit/snapshot/observation을 별도 control-plane으로 만든다.
3. raw success rate 대신 calibrated success rate를 설명할 수 있는 측정 surface를 추가한다.

## 3. 설계 원칙

### 3.1 기존 canonical surfaces는 유지한다

아래는 유지한다.

- `runtime_graph`
- `executor_plan`
- `evidence_graph`
- `staged_synthesis`
- `name_only_outcome`
- `support_promotion`
- `open_world_readiness`

새 구조는 이들을 대체하지 않고, 더 상위/주변 control-plane을 추가한다.

### 3.2 fail-open이 아니라 fail-attributed로 간다

이번 프로그램은 availability 최적화보다 attribution 최적화가 우선이다.

- 현재 strict/fail-closed semantics는 유지한다.
- 새 계층은 “더 많이 통과시키는” 것이 아니라 “왜 멈췄는지 더 잘 설명하는” 방향으로 설계한다.

### 3.3 새로운 산출물은 operator-readable여야 한다

새 artifact는 모두 다음 기준을 만족한다.

- machine-readable
- pack/repeatability/support workflow에서 재사용 가능
- top-level summary에 rollup 가능

### 3.4 하네스 품질과 task 품질을 분리한다

앞으로는 아래를 분리해서 본다.

- task outcome
- harness quality
- verification quality
- promotion readiness

즉 “PASS”와 “PROMOTABLE”과 “OPEN-WORLD READY”는 계속 분리한다.

## 4. 신규 산출물과 인터페이스

이번 프로그램에서 새로 도입하는 핵심 산출물은 아래 다섯 가지다.

### 4.1 `action_trace.jsonl`

목적:

- pipeline 내부 action-level causality trace

생성 위치:

- `metadata/<SID>/action_trace.jsonl`
- multi-bundle lane는 `metadata/<SID>/bundles/<slug>/action_trace.jsonl`

record schema 최소 집합:

- `trace_id`
- `bundle_slug`
- `stage`
- `action_id`
- `attempt`
- `input_contract`
- `output_contract`
- `source_authority`
- `concurrency_safe`
- `cacheable`
- `retryable`
- `status`
- `failure_class`
- `duration_ms`
- `emitted_artifacts`
- `selected_family`
- `selected_stack_id`
- `selected_scenario_id`
- `materialized_family`
- `materialized_topology`

### 4.2 `stage_gate_report.json`

목적:

- scattered gate logic의 declarative evaluation 결과를 묶음 보고서로 남김

생성 위치:

- `metadata/<SID>/stage_gate_report.json`

schema 최소 집합:

- `schema_version`
- `sid`
- `bundle_scoped`
- `gates`
  - `id`
  - `stage`
  - `blocking`
  - `result`
  - `failure_class`
  - `source`
  - `notes`
- `summary`
  - `blocking_gate_count`
  - `warning_gate_count`
  - `first_blocking_gate`

### 4.3 `harness_audit.json`

목적:

- deterministic harness quality scoring

생성 위치:

- `artifacts/<SID>/reports/harness_audit.json`
- direct repo-level command도 지원

category:

- `Selection Authority`
- `Materialization Causality`
- `Runtime Contract Parity`
- `Oracle Execution Parity`
- `Review Evidence Quality`
- `Measured Gate Integrity`
- `Cost And Retry Efficiency`

output 최소 집합:

- `overall_score`
- `max_score`
- `category_scores`
- `checks`
- `top_actions`

### 4.4 `canonical_snapshot.json`

목적:

- direct run / repeatability / support / packed bundle의 공통 read model

adapter:

- `direct_run`
- `repeatability`
- `support_review`
- `packed_bundle`

생성 위치:

- 각 output root 아래 canonical snapshot
- 필요 시 pack summary에서 aggregate rollup

top-level:

- `schema_version`
- `adapter_id`
- `session`
- `bundle`
- `selection`
- `materialization`
- `runtime`
- `verification`
- `review`
- `measured_gate`
- `artifacts`

### 4.5 `observation_ledger.jsonl`

목적:

- 반복 실패/수정/보정 결과를 구조화해 축적

생성 위치:

- `metadata/<SID>/observation_ledger.jsonl`
- multi-bundle lane는 bundle path에도 복사 가능

record 최소 집합:

- `observation_id`
- `bundle_slug`
- `mode`
- `selection_signature`
- `failure_stage`
- `failure_class`
- `repair_strategy`
- `result`
- `oracle_execution_parity`
- `measured_gate_ready`
- `artifact_quality_band`
- `created_at`

## 5. Workstream별 상세 구현 계획

### Workstream A. Internal Action Graph

목표:

- researcher/generator/executor/verify 내부 action을 coarse stage보다 세밀한 control-plane으로 분해한다.

관련 참고:

- `claude-leak` tool metadata
- current `staged_synthesis`

적용 경로:

- [common/contracts.py](/home/ysw/vulDocker/common/contracts.py)
- [agents/researcher/service.py](/home/ysw/vulDocker/agents/researcher/service.py)
- [agents/generator/synthesis.py](/home/ysw/vulDocker/agents/generator/synthesis.py)
- [executor/runtime/docker_local.py](/home/ysw/vulDocker/executor/runtime/docker_local.py)
- [orchestrator/run_pipeline.py](/home/ysw/vulDocker/orchestrator/run_pipeline.py)

구현 순서:

1. action node schema 정의
2. `common/contracts.py`에 selection/materialization 관련 action helper 추가
3. researcher에서 query/evidence/selection action emission
4. generator에서 `candidate_resolution`, `design_brief`, `runtime_plan`, `executor_plan`, `oracle_contract`, `file_manifest`별 action emission
5. executor에서 precheck / build / run / oracle replay action emission
6. verify/review summary를 action trace에 연결

초기 action set:

- `query_plan_emit`
- `search_execute`
- `evidence_graph_build`
- `family_rank`
- `stack_rank`
- `scenario_select`
- `candidate_resolution_validate`
- `design_brief_validate`
- `runtime_plan_validate`
- `executor_plan_validate`
- `oracle_contract_validate`
- `file_manifest_validate`
- `executor_precheck`
- `executor_build`
- `executor_run`
- `oracle_replay`
- `review_contract_check`

acceptance:

- first failure action이 기록된다.
- selected scenario와 materialized path 간 drift가 trace에서 보인다.
- pack summary가 `action_trace_summary`를 제공한다.

### Workstream B. Declarative Stage Gates

목표:

- current gate logic를 registry와 artifact로 정리한다.

적용 경로:

- [orchestrator/run_pipeline.py](/home/ysw/vulDocker/orchestrator/run_pipeline.py)
- [executor/runtime/docker_local.py](/home/ysw/vulDocker/executor/runtime/docker_local.py)
- [common/contracts.py](/home/ysw/vulDocker/common/contracts.py)
- [orchestrator/pack.py](/home/ysw/vulDocker/orchestrator/pack.py)

registry 설계:

- Python registry 또는 JSON-like declarative table
- runtime-evaluated validator function pointer

초기 gate set:

- `capability_precheck`
- `semantic_profile_terminal_block`
- `post_research_authority_gate`
- `post_generator_live_path_gate`
- `executor_dependency_gate`
- `executor_contract_gate`
- `post_verify_low_trust_gate`
- `pre_pack_promotion_integrity_gate`

적용 방식:

- `run_pipeline.py`의 직접 `if` 판단은 유지하되, 동일 판단을 gate registry helper로 감싼다.
- 각 gate는 evaluation 결과를 `stage_gate_report.json`에 기록한다.
- `pack.py`는 gate summary를 rollup한다.
- support workflow는 gate blocker vocabulary를 재사용한다.

acceptance:

- strict_dynamic failure subclass가 current truth와 동일하게 유지된다.
- pack/support surfaces가 same gate vocabulary를 쓴다.

### Workstream C. Deterministic Harness Audit

목표:

- 하네스 품질을 deterministic scorecard로 분리 측정한다.

적용 경로:

- 신규 script entrypoint
- 신규 docs command contract
- optional `ops/ci` helper integration

구현 순서:

1. audit rubric 고정
2. 각 category별 deterministic check 구현
3. text/json output contract 고정
4. optional `ops/ci/run_*` helper integration

초기 checks 예시:

- `selection_decision_present`
- `selection_ready_vs_materialized_trace_present`
- `runtime_graph_executor_plan_primary_input`
- `oracle_execution_parity_rollup_present`
- `support_review_measured_gate_split_present`
- `review_evidence_contract_present`
- `retry/failure_class surface present`

acceptance:

- 같은 commit에서 같은 score가 나온다.
- `top_actions`가 concrete rerun path와 연결된다.

### Workstream D. Canonical Snapshot Adapters

목표:

- 분산 artifact를 operator-readable canonical snapshot으로 정리한다.

적용 경로:

- 신규 adapter module
- [orchestrator/pack.py](/home/ysw/vulDocker/orchestrator/pack.py)
- [orchestrator/support_extract.py](/home/ysw/vulDocker/orchestrator/support_extract.py)
- `tests/e2e` repeatability/support scripts

adapter 정의:

- `direct_run`
  - source: `run/summary.json`, `evals.json`, generator contract
- `repeatability`
  - source: `repeatability_report.json`
- `support_review`
  - source: `support_candidate.json`, `support_review_index.json`, `support_registry_update.json`
- `packed_bundle`
  - source: `summary.json` / manifest

canonical fields:

- `session`
- `bundle`
- `selection`
- `materialization`
- `runtime`
- `verification`
- `review`
- `measured_gate`
- `artifacts`

acceptance:

- positive pair / blocked pair 모두 canonical snapshot으로 비교 가능
- adapter별 schema drift test 존재

### Workstream E. Observation Ledger and Health Reports

목표:

- 반복 실패와 보정 결과를 structured observation으로 남긴다.

적용 경로:

- [agents/generator/synthesis.py](/home/ysw/vulDocker/agents/generator/synthesis.py)
- [orchestrator/run_pipeline.py](/home/ysw/vulDocker/orchestrator/run_pipeline.py)
- [orchestrator/support_extract.py](/home/ysw/vulDocker/orchestrator/support_extract.py)
- 신규 reporting helper

초기 observation source:

- generator failure
- executor precheck failure
- verify failure
- support blocker
- retry salvage success

추가 report:

- failure cluster report
- repair strategy health report
- baseline vs amended policy comparison scaffold

acceptance:

- same failure class의 반복 빈도를 집계 가능
- `repair_strategy`별 salvage rate를 계산 가능

### Workstream F. Reviewer / Verifier Contract Hardening

목표:

- verification을 command-backed evidence contract로 강화한다.

적용 경로:

- [agents/reviewer/service.py](/home/ysw/vulDocker/agents/reviewer/service.py)
- verifier prompt/report surface
- optional `evals/poc_verifier/*`

구현 포인트:

- 각 review check에 `command`, `observed_output`, `result` 기록
- adversarial probe 최소 1개
- `PASS|FAIL|PARTIAL` machine-readable verdict
- PARTIAL은 환경 제약에서만 허용

이 workstream은 새 generic verifier를 만드는 것이 아니라, current reviewer/verifier surface를 강화하는 방식으로 간다.

acceptance:

- report만 읽어도 실제 검증 행동이 추적 가능
- success report에 evidence completeness가 향상됨

## 6. 코드 매핑

### 6.1 `common/contracts.py`

적용 내용:

- action node schema helper 추가
- `selection_decision`, `runtime_graph`, `executor_plan`, `staged_synthesis`를 action trace summary와 연결
- canonical snapshot용 derived helper 추가

### 6.2 `agents/researcher/service.py`

적용 내용:

- search/evidence/selection action trace emission
- cache/early-stop/relevance 결과를 observation ledger 입력으로 변환

### 6.3 `agents/generator/synthesis.py`

적용 내용:

- stage-aware recovery를 observation ledger와 action trace로 연결
- `failure_stage`를 action-level failure class로 승격

### 6.4 `orchestrator/run_pipeline.py`

적용 내용:

- stage gate registry 실행점
- gate result artifact 생성
- stage failure와 action trace/observation ledger 연결

### 6.5 `executor/runtime/docker_local.py`

적용 내용:

- executor precheck validator 결과를 action trace와 gate report에 남김
- build/run/oracle replay를 action trace에 남김

### 6.6 `orchestrator/pack.py`

적용 내용:

- `action_trace_summary`
- `stage_gate_summary`
- `canonical_snapshot_summary`
- optional `harness_audit_summary`

### 6.7 `tests/e2e/*`

적용 내용:

- adapter/schema tests
- harness audit deterministic tests
- positive pair / blocked pair regression

## 7. 구현 순서

아래 순서로 구현한다.

1. new planning doc + issue decomposition
2. action trace schema와 artifact helper
3. declarative gate registry
4. canonical snapshot adapters
5. observation ledger and reports
6. harness audit
7. reviewer/verifier contract hardening
8. `pack` / support workflow integration

이 순서를 고정하는 이유:

- action trace와 gate registry가 먼저 있어야 later audit와 observation이 consistent해진다.
- canonical snapshot이 있어야 audit/support/operator 해석이 쉬워진다.
- reviewer hardening은 하네스 측정 surface가 먼저 정리된 뒤에 올리는 것이 calibration에 유리하다.

## 8. 테스트 계획

### 8.1 Unit / Integration

필수 추가 테스트:

- action trace schema serialization
- stage gate registry evaluation
- canonical snapshot adapter normalization
- observation ledger aggregation
- harness audit deterministic scoring
- reviewer evidence contract formatting

### 8.2 Representative lanes

No-Docker:

- `open-redirect-strict-dynamic-no-remote`
- `open-redirect-strict-dynamic-stub`
- `foobar-name-only-negative`

Docker-enabled direct:

- `trusted-dynamic-sqli`
- `open-redirect-dynamic-name-only`

Measured/support:

- blocked/no-op pair
- positive pair promotion check

### 8.3 Acceptance checks

- first failure node가 action trace에 남는다
- gate result가 pack/support surface까지 이어진다
- canonical snapshot으로 direct/repeatability/support 비교가 가능하다
- harness audit가 deterministic output을 낸다
- observation ledger에서 recurring failure cluster가 집계된다
- reviewer/verifier report가 command-backed evidence를 남긴다

## 9. GitHub Issue Program

상위 issue 구조:

- Epic 1개
- Child issue 8개

### Epic

제목:

- `Program: Harness Governance and Action-Trace Improvement`

body 핵심:

- why now
- source references
- workstream summary
- sequencing
- acceptance gates

### Child issues

1. `Design action-trace schema and artifact contract`
2. `Emit action traces from researcher, generator, executor, and verifier surfaces`
3. `Introduce declarative stage-gate registry and gate reports`
4. `Unify gate blocker vocabulary across pipeline, pack, and support surfaces`
5. `Add deterministic pipeline-harness audit and scorecard`
6. `Add canonical snapshot adapters for direct, repeatability, support, and pack artifacts`
7. `Add observation ledger and failure-health reporting`
8. `Harden reviewer and verifier evidence contracts`

각 issue body 공통 섹션:

- Summary
- Why
- Implementation scope
- Code mapping
- Output artifacts
- Representative tests
- Acceptance criteria
- Related existing backlog

## 10. Existing Backlog Cross-References

새 프로그램은 별도 issue 체계로 관리하지만, 기존 backlog와의 관련성은 아래처럼 명시한다.

- Workstream A/B
  - related: `TKT-001`, `TKT-002~005`, `TKT-006`
- Workstream C/D/E
  - related: `TKT-008`, `TKT-009`
- Workstream F
  - related: `TKT-007`, `TKT-008`, `TKT-009`

이 표기는 reference only다. canonical completion 판정은 여전히 기존 문서 체계를 따른다.

## 11. Program Success Criteria

이번 프로그램이 성공했다고 판단하는 기준은 아래다.

1. current pipeline의 first failure가 stage보다 더 세밀한 action-level로 드러난다.
2. gate logic가 artifact로 남아 operator가 후행 summary만 보고도 판단할 수 있다.
3. direct/repeatability/support/pack artifact가 하나의 canonical schema로 비교 가능하다.
4. 반복 실패와 repair 효과가 observation ledger로 집계 가능하다.
5. harness quality를 deterministic audit score로 별도 추적할 수 있다.
6. reviewer/verifier evidence contract가 더 엄격해져 success-rate calibration이 개선된다.

## 12. Issue Mapping

issue 발급 후 이 섹션에 issue 번호와 URL을 연결한다.

- Epic: `#1` https://github.com/sw1029/vulDocker/issues/1
- Child 1: `#2` https://github.com/sw1029/vulDocker/issues/2
- Child 2: `#3` https://github.com/sw1029/vulDocker/issues/3
- Child 3: `#4` https://github.com/sw1029/vulDocker/issues/4
- Child 4: `#5` https://github.com/sw1029/vulDocker/issues/5
- Child 5: `#6` https://github.com/sw1029/vulDocker/issues/6
- Child 6: `#7` https://github.com/sw1029/vulDocker/issues/7
- Child 7: `#8` https://github.com/sw1029/vulDocker/issues/8
- Child 8: `#9` https://github.com/sw1029/vulDocker/issues/9
