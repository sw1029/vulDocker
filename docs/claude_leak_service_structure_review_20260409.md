# Claude-Leak Service Structure Review

작성일: 2026-04-09

## 1. 목적과 결론

이 문서는 레포 내 별도 구현인 `claude-leak/claude-code-source-code`의 서비스 구조를 분해하고, 현재 레포의 `harness / runtime_graph / evidence_graph / staged_synthesis` 중심 구조와 비교해 로직 적용 가능성을 검토한 보고서다.

결론부터 말하면:

- `claude-leak`은 범용 코딩 에이전트용 `tool-centric interactive runtime`으로 매우 강하다.
- 반면 현재 레포는 이미 `domain-specific generation pipeline + executable harness` 관점에서는 더 강한 control-plane을 갖고 있다.
- 따라서 `claude-leak`의 전체 구조를 가져오는 것은 비효율적이고, 아래 3가지만 선별적으로 흡수하는 것이 맞다.

1. `tool/action metadata` 중심의 세분화된 실행 제어
2. role-specialized agent와 강한 출력 계약
3. verification discipline와 failure attribution 강화

반대로 아래는 현재 시점에서 우선순위가 낮거나, 현재 레포의 fail-closed 철학과 충돌한다.

1. UI/Bridge/IDE 연동
2. plugin/marketplace/skill ecosystem
3. remote-managed settings / policy services의 fail-open 운영 모델
4. 범용 MCP server/platformization 자체

핵심 판단은 다음이다.

- 현재 레포의 부족한 점은 `generic tool runtime` 부재가 아니라, `selection -> materialization -> executor/verifier` 사이의 branch causality와 stage-local failure control이 아직 충분히 authoritative하지 않다는 점이다.
- `claude-leak`은 이 gap을 메우는 데 필요한 `fine-grained orchestration pattern`을 준다.
- 하지만 현재 레포의 `runtime_graph`, `executor_plan`, `staged_synthesis`, `tests/e2e` 하니스 자체를 대체할 정도의 domain closure는 제공하지 않는다.

## 2. 분석 대상과 읽은 근거

`claude-leak` 쪽 핵심 근거:

- `claude-leak/claude-code-source-code/docs/architecture.md`
- `claude-leak/claude-code-source-code/docs/subsystems.md`
- `claude-leak/claude-code-source-code/docs/tools.md`
- `claude-leak/claude-code-source-code/src/entrypoints/init.ts`
- `claude-leak/claude-code-source-code/src/Tool.ts`
- `claude-leak/claude-code-source-code/src/tools.ts`
- `claude-leak/claude-code-source-code/src/query.ts`
- `claude-leak/claude-code-source-code/src/services/tools/toolOrchestration.ts`
- `claude-leak/claude-code-source-code/src/services/tools/StreamingToolExecutor.ts`
- `claude-leak/claude-code-source-code/src/tools/AgentTool/AgentTool.tsx`
- `claude-leak/claude-code-source-code/src/tools/AgentTool/built-in/exploreAgent.ts`
- `claude-leak/claude-code-source-code/src/tools/AgentTool/built-in/planAgent.ts`
- `claude-leak/claude-code-source-code/src/tools/AgentTool/built-in/verificationAgent.ts`
- `claude-leak/claude-code-source-code/src/services/analytics/growthbook.ts`
- `claude-leak/claude-code-source-code/src/services/policyLimits/index.ts`
- `claude-leak/claude-code-source-code/src/services/remoteManagedSettings/index.ts`
- `claude-leak/claude-code-source-code/src/services/SessionMemory/sessionMemory.ts`
- `claude-leak/claude-code-source-code/src/services/api/bootstrap.ts`
- `claude-leak/claude-code-source-code/docs/bridge.md`
- `claude-leak/claude-code-source-code/mcp-server/README.md`

현재 레포 쪽 핵심 근거:

- `common/contracts.py`
- `agents/researcher/service.py`
- `agents/generator/service.py`
- `agents/generator/synthesis.py`
- `agents/reviewer/service.py`
- `orchestrator/run_pipeline.py`
- `orchestrator/loop_controller.py`
- `executor/runtime/docker_local.py`
- `orchestrator/pack.py`
- `docs/code/common.md`
- `docs/code/orchestrator.md`
- `docs/code/agents_researcher.md`
- `docs/code/agents_generator.md`
- `docs/code/agents_reviewer.md`
- `tests/e2e/README.md`
- `docs/open_world_name_only_improvement_analysis_20260409.md`

## 3. Claude-Leak 서비스 구조 요약

### 3.1 전체 아키텍처

`claude-leak`의 중심은 `single-binary CLI` 위에 올라간 범용 에이전트 런타임이다.

- 입력 흐름:
  `User Input -> CLI Parser -> Query Engine -> LLM API -> Tool Execution Loop -> Terminal UI`
- 런타임:
  Bun + TypeScript + React/Ink
- 핵심 제어점:
  `src/query.ts`, `src/Tool.ts`, `src/tools.ts`, `src/tools/AgentTool/*`

즉 이것은 특정 도메인 산출물을 만드는 파이프라인이 아니라, 다양한 도구를 모델이 반복적으로 호출하는 `general-purpose tool execution engine`이다.

### 3.2 서비스 계층

`src/entrypoints/init.ts` 기준 초기화는 다음 특징을 가진다.

- safe env, CA cert, proxy, mTLS, graceful shutdown을 먼저 건다.
- analytics/growthbook, OAuth account info, IDE detection, remote managed settings, policy limits loading promise를 비동기로 걸어 둔다.
- telemetry는 trust 이후 지연 초기화한다.
- upstream proxy, scratchpad, cleanup registry 같은 운영 서비스가 별도로 붙는다.

중요한 점은:

- 원격 서비스 실패 시 앱이 죽지 않도록 대부분 `fail-open` 또는 `background loading` 패턴을 쓴다.
- 이 구조는 end-user CLI reliability에는 좋지만, 현재 레포의 strict measurement/fail-closed 정책에는 그대로 이식하면 안 된다.

### 3.3 툴 시스템

`src/Tool.ts`의 `Tool` 인터페이스와 `buildTool()`가 핵심이다.

각 툴은 최소한 아래 메타데이터를 가진다.

- 입력 schema
- permission check
- `isConcurrencySafe`
- `isReadOnly`
- `interruptBehavior`
- UI renderer
- result mapping

그리고 `buildTool()`가 안전한 default를 채워준다.

- concurrency-safe 기본값은 `false`
- read-only 기본값은 `false`
- permissions 기본값은 일반 permission system에 위임

이 패턴의 장점은:

- 모든 action이 동일한 실행 계약을 가진다.
- scheduler가 action metadata를 믿고 병렬화/직렬화/중단 처리를 할 수 있다.
- failure attribution이 도구 단위로 남는다.

### 3.4 쿼리 및 툴 실행 루프

실제 제어 루프는 `src/query.ts`에 있다.

핵심 요소:

- stream 기반 assistant/tool loop
- microcompact / autocompact / reactive compact
- tool result budget
- fallback model retry
- max output token recovery
- streaming tool execution
- tool summary generation
- attachment/memory prefetch

그리고 `src/services/tools/toolOrchestration.ts`는 툴 실행을 아래처럼 나눈다.

- concurrency-safe tool batch는 병렬 실행
- non-concurrent tool batch는 직렬 실행
- max concurrency 제한 존재

`src/services/tools/StreamingToolExecutor.ts`는 도구가 스트리밍 중 도착해도 즉시 큐잉/실행/abort/sibling cancel을 관리한다.

즉 `claude-leak`의 강점은 단순히 툴이 많다는 점이 아니라, 툴 실행이 `metadata-driven scheduler`로 조직되어 있다는 점이다.

### 3.5 AgentTool과 specialized agent

`AgentTool`은 하위 에이전트를 로컬/워크트리/원격 모드로 띄울 수 있고, built-in specialized agent를 가진다.

대표 built-in agent:

- `Explore`: read-only search 특화
- `Plan`: read-only planning 특화
- `verification`: 변경 금지 + 명령/출력 기반 PASS/FAIL/PARTIAL 강제

특징:

- 각 agent는 `disallowedTools`가 명시적이다.
- system prompt가 역할과 금지사항을 강하게 고정한다.
- 특히 verification agent는 "코드를 읽고 PASS라고 하지 말고 반드시 명령/출력 증거를 남겨라"는 계약이 매우 강하다.

이는 현재 레포의 researcher/generator/reviewer 구분과 유사하지만, 역할 경계와 출력 계약이 더 빡빡하다.

### 3.6 부가 서브시스템

`claude-leak`에는 다음이 붙어 있다.

- Bridge: IDE/웹 UI 연동
- MCP client/server
- Plugin / Skill system
- Session Memory
- Task / background agent system
- remote managed settings / policy limits / bootstrap API

이들은 product-grade platform 기능이지, 현재 레포의 open-world name-only generation 성공률을 직접 올리는 핵심은 아니다.

## 4. 현재 레포 구조 요약

현재 레포의 중심은 범용 툴 런타임이 아니라 `vuln Docker generation + verification + measured support workflow`다.

주요 흐름:

- `orchestrator/run_pipeline.py`
  `RESEARCH -> GENERATOR -> EXECUTOR(build/run) -> VERIFY -> REVIEW -> PACK`
- `LoopController`
  stage-level retry와 failure memory 유지
- `common/contracts.py`
  `request_ir`, `selection_decision`, `scenario_candidates`, `runtime_recipe`, `runtime_graph`, `executor_plan`, `evidence_graph`, `staged_synthesis`
- `executor/runtime/docker_local.py`
  `executor_plan/runtime_graph`를 실제 실행 surface로 해석하고 계약 검증 수행
- `tests/e2e/README.md`
  direct/repeatability/support-review 하니스

즉 현재 레포는 이미 아래 면에서는 `claude-leak`보다 더 진전돼 있다.

1. `runtime_graph`와 `executor_plan`이 실제 executor input으로 내려간다.
2. `evidence_graph`와 `selection_decision`이 operator-facing summary와 measured artifacts에 연결된다.
3. `staged_synthesis`가 generator retry와 failure stage classification에 사용된다.
4. repeatability/support workflow가 별도 하니스로 존재한다.

반대로 약한 부분은 다음이다.

1. action/stage granularity가 여전히 거칠다.
2. `selection -> materialization` causality가 완전 authoritative하지 않다.
3. reviewer는 강한 adversarial verification contract보다 log/pattern 중심이다.
4. researcher/generator 내부 action이 metadata-driven scheduler보다는 service-local heuristic에 더 가깝다.

## 5. 비교 결과: 가져올 수 있는 것

### 5.1 가장 가치가 큰 요소: 내부 action/tool metadata 계층

가장 먼저 가져와야 할 것은 `claude-leak`의 UI가 아니라 `Tool` 패턴이다.

현재 레포는 `runtime_graph`와 `evidence_graph`는 있지만, `research/generation/verification internal action graph`는 약하다.

권장 방향:

- 현재 레포에 별도의 `action graph` 또는 `internal tool graph`를 도입한다.
- 이 그래프는 `runtime_graph`를 대체하는 것이 아니라, 그 이전 단계의 control-plane을 세분화한다.

예시 노드:

- `query_plan_emit`
- `search_query_execute`
- `evidence_dedup`
- `family_rank`
- `stack_rank`
- `scenario_select`
- `design_brief_validate`
- `runtime_plan_synthesize`
- `executor_plan_validate`
- `oracle_contract_validate`
- `file_manifest_validate`
- `executor_precheck`
- `oracle_replay`

각 노드는 아래 메타데이터를 가져야 한다.

- input surface
- output surface
- read-only / stateful
- concurrency-safe 여부
- cacheable 여부
- retryable 여부
- terminal failure class
- artifact emission path

기대 효과:

- 실패가 `GENERATOR failed`가 아니라 `design_brief_validate failed`처럼 좁아진다.
- success rate를 raw pass rate가 아니라 `node-level completion profile`로 보정할 수 있다.
- harness에서 어떤 노드가 안정적이고 어떤 노드가 흔들리는지 직접 본다.
- selection/materialization drift를 summary가 아니라 action trace로 잡을 수 있다.

이 항목은 현재 레포의 `TKT-001`, `TKT-006`, `TKT-002~005`와 가장 직접적으로 맞닿는다.

### 5.2 specialized role + disallowed capability 패턴

현재 레포도 researcher/generator/reviewer가 분리돼 있지만, `claude-leak`처럼 role별 capability contract가 강하지는 않다.

적용 가능 포인트:

- researcher:
  read-only, evidence-gathering-only contract 강화
- generator:
  write/repair 가능하지만 selected scenario contract 위반 시 downgrade가 아니라 explicit branch divergence 기록
- reviewer/verifier:
  "명령/출력 없는 PASS 금지" 같은 강한 evidence contract 추가

특히 reviewer는 `claude-leak` verification agent 패턴을 직접 참고할 가치가 있다.

현재 reviewer는:

- run summary
- verifier result
- static pattern
- semantic contract

를 종합하지만, 실제 공격적 재실행 계약은 상대적으로 약하다.

권장 보완:

- `agents/reviewer/service.py` 또는 별도 verifier prompt에 아래를 추가
  - check마다 실행 명령/관찰 출력/판정 근거 기록
  - adversarial probe 최소 1개 강제
  - PASS/PARTIAL/FAIL machine-readable verdict
  - unsupported 환경은 PARTIAL로만 올리게 제한

이건 nominal success rate를 잠깐 낮출 수 있다. 하지만 이는 악화가 아니라 `성공률 보정(calibration)`이다. 현재 요청 관점에서는 오히려 반드시 필요한 강화다.

### 5.3 concurrency-safe batching 패턴

`claude-leak`은 `isConcurrencySafe`를 기준으로 병렬 배치를 돌린다.

현재 레포에 바로 적용 가능한 곳:

- researcher의 local/static post-processing
  - evidence typing
  - family/stack support projection
  - graph edge construction
- generator의 pure validation batch
  - file manifest checks
  - dependency inference checks
  - stage-local guard calculation
- executor precheck의 read-only contract validation

주의점:

- remote search query 자체를 무조건 병렬화하는 것은 권장하지 않는다.
- 현재 researcher는 cache와 early stop을 이미 가지고 있고, provider rate limit과 provenance ordering이 중요하다.
- 따라서 병렬화는 `authoritative remote search`보다 `read-only local validation batch`에서 먼저 써야 한다.

즉 적용 범위는 `search provider layer`보다 `validation/projection layer`가 맞다.

### 5.4 interrupt / abort / sibling-cancel semantics

`claude-leak`은 한 도구가 실패하거나 fallback이 발생할 때 sibling tool execution을 정리하고 synthetic error를 남긴다.

현재 레포는 coarse stage retry는 있지만, same-stage subaction cancel semantics는 약하다.

적용 가능 포인트:

- generator stage에서 한 contract validator가 terminal이면 이후 동등 후보 evaluation을 즉시 중단
- executor precheck에서 hard contract mismatch가 발견되면 sidecar synthesis/fallback 추론을 더 하지 않고 fail-fast
- researcher에서 authoritative evidence 부족이 terminal이면 lower-quality follow-up query를 의미 없이 더 돌리지 않음

이것 역시 raw throughput보다 `failure attribution quality`를 올리는 쪽이다.

### 5.5 progress/event surface

`claude-leak`의 query/tool loop는 progress와 event를 매우 잘 남긴다.

현재 레포도 `loop_state`, `generator_failures.jsonl`, `support_review_index.json` 등이 있지만, stage 내부 단위 이벤트는 상대적으로 얇다.

권장 보완:

- `metadata/<SID>/action_trace.jsonl` 같은 per-node trace 추가
- 각 event에 아래 포함
  - `node`
  - `input_hash`
  - `source_contract`
  - `result_class`
  - `failure_class`
  - `retry_count`
  - `duration_ms`
  - `cache_hit`

이 trace는 success rate 보정과 benchmark 해석에 매우 유용하다.

## 6. 비교 결과: 가져오면 안 되는 것 또는 우선순위가 낮은 것

### 6.1 Bridge / IDE / Chrome integration

`claude-leak`의 bridge subsystem은 product surface로서 흥미롭지만, 현재 레포의 성공률과 직접 관련이 없다.

- open-world generation quality를 올리지 않는다.
- harness reliability를 직접 올리지 않는다.
- 운영 복잡도만 늘린다.

따라서 현 시점 우선순위는 낮다.

### 6.2 remote managed settings / policy limits의 fail-open 운영 철학

`claude-leak`의 서비스층은 원격 API 실패 시 계속 동작하게 설계되어 있다.

이는 product CLI에는 맞지만 현재 레포에는 주의가 필요하다.

- 현재 레포는 `strict_dynamic`에서 capability/evidence 부족을 fail-closed로 남겨야 한다.
- measured/support workflow도 authority drift를 숨기면 안 된다.

따라서 가져올 수 있는 것은:

- 비핵심 telemetry/config 로딩의 graceful degradation

가져오면 안 되는 것은:

- researcher/generator/verifier authority path의 fail-open

### 6.3 Session Memory / Plugin / Marketplace / MCP platformization

이들은 장기적으로 operator tooling을 좋게 만들 수는 있다. 그러나 현재 backlog 기준으로는 핵심이 아니다.

- current bottleneck은 기억 유지가 아니라 branch authority와 materialization quality다.
- pluginization은 오히려 control-plane closure 이전에 확장 축으로 빠질 위험이 있다.

즉 `Phase 7` 성격이지 지금 priority는 아니다.

### 6.4 model fallback logic의 직접 이식

`claude-leak`은 interactive UX를 위해 fallback model retry를 적극 사용한다.

현재 레포에 이를 그대로 넣으면 문제가 생긴다.

- benchmark interpretation이 흐려질 수 있다.
- strict live-LLM honesty를 해칠 수 있다.
- promotion/measured gate에서 authority mode가 섞일 수 있다.

현재 레포에는 fallback 자체보다 `which branch used which authority mode`를 더 명시적으로 남기는 방식이 우선이다.

## 7. 현재 레포에 대한 구체 제안

### 7.1 P0: `action graph` 도입

가장 우선순위가 높다.

구현 방향:

- `common/contracts.py`의 `staged_synthesis`와 별도로 `action_graph` 또는 `materialization_trace` 추가
- `agents/researcher/service.py`, `agents/generator/synthesis.py`, `executor/runtime/docker_local.py`가 공통 event schema로 기록
- `orchestrator/pack.py`가 이를 summary로 rollup

우선 연결할 필드:

- `selection_decision`
- `selection_branch_trace`
- `staged_synthesis`
- `runtime_graph`
- `executor_plan`

효과:

- 현재의 coarse stage retry를 node-aware retry로 바꿀 준비가 된다.
- harness에서 per-node benchmark가 가능해진다.

### 7.2 P0: reviewer/verifier evidence contract 강화

두 번째 우선순위다.

구현 방향:

- current reviewer 또는 별도 verifier prompt contract를 `claude-leak` verification agent 수준으로 강화
- 각 verification step에 command/output/result를 요구
- 최소 adversarial probe 1개 강제
- `VERDICT: PASS|FAIL|PARTIAL` 같은 fixed token 출력 도입 가능

효과:

- false positive pass 감소
- support promotion precision 개선
- success rate calibration 개선

### 7.3 P1: stage-local validators를 first-class action으로 승격

현재 generator는 stage-aware retry를 이미 갖고 있다. 하지만 validator/repair action이 아직 heuristic 묶음에 가깝다.

권장 방향:

- `design_brief_validate`
- `runtime_plan_validate`
- `oracle_contract_validate`
- `file_manifest_validate`

를 명시적 action으로 쪼개고, 각 action에 repair strategy를 붙인다.

이는 `claude-leak`의 tool contract 철학을 현재 레포에 가장 자연스럽게 번역한 방식이다.

### 7.4 P1: bounded concurrency 적용

적용 범위:

- graph building
- contract validation
- static/semantic checks
- non-authoritative local analysis

적용 금지 또는 후순위:

- authoritative remote search
- fail-closed policy decision 직전의 non-deterministic path

### 7.5 P2: service initialization hardening

현재 레포가 장기 실행 operator service나 daemon 쪽으로 갈 경우에만 고려할 만하다.

가져올 만한 패턴:

- lazy init
- cleanup registry
- optional telemetry bootstrap
- degraded-mode logging

하지만 이는 현재 success criteria의 core blocker는 아니다.

## 8. 하네스/벤치마킹 관점 권장 측정 항목

`claude-leak` 참고 후 현재 레포에서 추가로 보는 것이 좋은 항목:

- `node_success_rate`
  - action graph node별 성공률
- `first_failure_node`
  - rerun마다 최초 실패 node
- `retry_salvage_rate`
  - same failure class가 몇 번의 retry 후 salvage되는지
- `selection_to_materialization_parity`
  - selected scenario와 materialized branch 일치율
- `runtime_contract_parity`
  - `runtime_graph/executor_plan`과 actual run summary 일치율
- `oracle_contract_parity`
  - staged oracle contract와 oracle replay 결과 일치율
- `reviewer_evidence_completeness`
  - reviewer verdict에 command/output evidence가 실제 충분한지

대표 benchmark lane:

- no-Docker fail-closed pair
  - `open-redirect-strict-dynamic-no-remote`
  - `open-redirect-strict-dynamic-stub`
- abstain negative
  - `foobar-name-only-negative`
- positive direct pair
  - `trusted-dynamic-sqli`
  - `open-redirect-dynamic-name-only`

해석 원칙:

- verification contract를 강화하면 raw PASS count는 떨어질 수 있다.
- 하지만 authority-consistent PASS가 늘면 그것이 성공률 보정 측면에서는 개선이다.

## 9. 최종 판단

`claude-leak`을 현재 레포의 대체 아키텍처로 보는 것은 맞지 않다.

더 정확한 해석은 다음이다.

- 현재 레포는 domain control-plane과 harness 면에서 더 진화해 있다.
- `claude-leak`은 범용 agent runtime과 tool/action scheduling 면에서 더 정교하다.
- 따라서 흡수 대상은 `platform feature`가 아니라 `execution discipline`이다.

실행 우선순위는 아래가 적절하다.

1. `action graph` + per-node trace
2. reviewer/verifier evidence contract 강화
3. stage-local validator/repair action 분해
4. bounded concurrency
5. optional service bootstrap hardening

한 줄로 정리하면:

> 현재 레포는 `runtime_graph`는 이미 강하지만 `internal action graph`가 아직 약하다. `claude-leak`에서 가져와야 할 것은 UI나 MCP가 아니라, 바로 그 `metadata-driven action orchestration`과 `verification contract discipline`이다.
