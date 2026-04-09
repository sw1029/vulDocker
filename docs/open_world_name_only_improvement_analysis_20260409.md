# Open-World Name-Only Dynamic Insertion 개선 분석

작성일: 2026-04-09

관련 검증 문서:

- [open_world_name_only_validation_20260409.md](/home/ysw/vulDocker/docs/open_world_name_only_validation_20260409.md)
- [open_world_name_only_validation_20260409_gpt54.md](/home/ysw/vulDocker/docs/open_world_name_only_validation_20260409_gpt54.md)

## 1. 목적

이 문서는 기존의 핵심 목표,

> `Researcher -> RAG -> LLM response`를 통해 open world의 `name-only` 입력으로부터 취약점을 동적으로 삽입한 학습용 Docker를 생성한다

를 기준으로 현재 구현에서 무엇이 부족한지, 그리고 어떤 순서로 개선되어야 하는지를 코드와 최근 실행 결과 기준으로 분석한다.

여기서 중요한 기준은 두 가지다.

1. 단순히 Docker artifact가 생성되는가
2. 그 artifact가 정말 `open-world / name-only / researcher-backed / live-LLM-shaped / dynamic insertion`이라고 부를 수 있는가

현재 구현은 1번은 부분적으로 만족하지만, 2번은 아직 아니다. 개선 포인트는 바로 이 간극을 줄이기 위한 것이다.

## 2. 현재 구현의 핵심 상태

요약하면 현재 시스템은 아래 상태에 있다.

- `name-only` 입력을 받되, 초기에 catalog/request IR 기반으로 강하게 정규화한다
- researcher는 dynamic lane에서는 유효하게 동작하지만, compiler/static supported lane에서는 skip될 수 있다
- generator는 `compiler_generated`, `llm_manifest`, `deterministic_fallback` 세 provenance를 섞어 사용한다
- representative dynamic name-only lane는 Docker build/run/verify까지 닫혀도 여전히 `deterministic_fallback`, `partial`로 남는다
- fixture-backed positive LLM-shaped lane는 실행되지만 `llm_fixture`, `thin_or_incomplete`, measured/support blocked 상태다

즉 현재 구현은 아래 문장에는 가깝다.

> bounded catalog/evidence contract를 통해 취약 family를 해석하고, lower-bound/fixture/fallback을 포함한 방식으로 vulnerable Docker artifact를 생성한다

반면 아래 문장에는 아직 못 미친다.

> researcher와 RAG를 통해 open-world `name-only` 입력을 이해하고, live LLM response가 주도하는 dynamic insertion으로 취약 Docker를 생성한다

## 3. 가장 큰 구조적 문제

현재 목표 대비 가장 큰 구조적 문제는 다음 한 줄로 요약된다.

> `selection/research`는 rich해졌지만, 실제 `materialization branch`는 아직 lower-bound, repo prior, deterministic fallback이 더 강하게 지배한다.

이 문제는 다섯 축으로 나뉜다.

1. 입력 해석이 너무 빨리 resolved/bounded surface로 굳는다
2. researcher가 항상 authoritative controller로 작동하지 않는다
3. generator가 selection 결과보다 fallback/registry/builder prior에 더 많이 기대고 있다
4. runtime/oracle은 일부 닫혔지만 generalized control-plane은 아직 아니다
5. measured/support acceptance가 여전히 non-live positive를 막고 있다

아래부터는 각 축을 세부적으로 본다.

## 4. 개선이 필요한 지점

### 4.1 입력 해석이 너무 빨리 closed-world로 수렴한다

현재 문제:

- `common/schema/requirement.py`는 `vuln_name`을 초기에 `catalog_alias`, `exact_identifier`, `synthetic_name` 같은 resolution 상태로 정리한다
- `request_ir`는 early stage에서 이미 `resolved_vuln_id`, `family_candidates`, `stack_candidates`, `scenario_candidates`를 가진다
- `common/contracts.py:4469` 이후는 high-confidence `catalog_alias`면 다시 catalog family를 working hypothesis로 고정한다

왜 문제인가:

- 목표가 `open world name-only`라면, 초반부터 resolved catalog family가 authoritative input이 되면 연구와 생성은 “탐색”보다 “확인”에 가깝게 변한다
- 현재 dynamic lane가 실제로 `Open Redirect -> catalog_alias -> open_redirect`로 닫히기 때문에, open-world family induction이 아니라 bounded alias resolution에 가깝다

실제 증거:

- `common/schema/requirement.py:496` 이후 `_build_request_ir`
- `common/contracts.py:4406` 이후 `_build_name_only_generation_spec`
- `common/contracts.py:4469` 이후 `request_identity_family`를 catalog entry로 고정

개선 방향:

1. `request_ir`를 `resolved request surface`와 `primitive/open hypothesis surface`로 분리해야 한다
2. generator의 primary input은 `resolved_vuln_id`가 아니라 primitive IR와 hypothesis set이 되게 바꿔야 한다
3. `catalog_alias`는 hard resolution이 아니라 one candidate source로 강등해야 한다
4. `synthetic_name`도 “unsupported니까 종료”가 아니라 “연구/abstain 후보”와 “generation 후보”를 분리해야 한다

구체적 개선안:

- `request_ir`를 최소 2-layer로 나눈다
  - `request_ir.resolution_surface`
  - `request_ir.open_hypothesis_surface`
- `family_candidates`에 score/authority뿐 아니라 contradiction score, elimination reason, abstain threshold를 추가한다
- generator는 `selected_family`를 직접 받기보다 `candidate set + confidence/authority/contradiction`을 입력으로 받아 staged narrowing을 하게 한다

우선순위:

- 최상위

관련 ticket:

- `TKT-001-A`
- `TKT-001-D`
- `TKT-001-H`
- `TKT-001-I`

### 4.2 researcher가 open-world lane에서 항상 authoritative하지 않다

현재 문제:

- `agents/researcher/main.py:65` 이후 `_should_skip_bundle_research()` 때문에 compiler/static supported bundle은 researcher가 skip될 수 있다
- 실제 `open-redirect-name-only`, `trusted-dynamic-sqli`는 researcher skip 후 generator가 진행된다
- dynamic lane에서는 researcher가 동작하더라도, 그 결과가 materializer를 강제하지는 않는다

왜 문제인가:

- 목표가 `Researcher -> RAG -> LLM response` 중심이라면, researcher skip 자체가 strong lower-bound shortcut이다
- researcher가 optional이면 “research-backed open-world generation”이 아니라 “research present when needed” 수준에 머문다

실제 증거:

- `agents/researcher/main.py:65-93`
- `agents/researcher/main.py:139-156`
- direct run에서 `open-redirect-name-only`와 `trusted-dynamic-sqli`는 researcher skipped

개선 방향:

1. `dynamic`와 `strict_dynamic` 뿐 아니라 “open-world proving ground” lane에서는 researcher skip을 금지해야 한다
2. supported family라도 `name-only + open-world target`이면 researcher output이 branch authority에 실제로 쓰이게 해야 한다
3. researcher quality를 binary `skip/sufficient/insufficient`가 아니라 branch-driving contract로 승격해야 한다

구체적 개선안:

- `policy.researcher.force_run_for_name_only_open_world=true` 같은 강한 모드를 도입
- researcher 산출물에 아래를 추가
  - decisive evidence ids
  - contradiction set
  - selected family/stack/scenario의 causal justification
  - negative hypotheses consumption trace
- `selection_decision`이 researcher evidence 없이 selected되면 dynamic/open-world lane에서 fail-closed 하도록 강화

우선순위:

- 최상위

관련 ticket:

- `TKT-001-D`
- `TKT-001-E`
- `TKT-001-H`

### 4.3 selection_decision이 실제 materialization branch를 충분히 지배하지 못한다

현재 문제:

- `common/contracts.py:4194` 이후 `_request_ir_selection_decision()`은 family/stack/scenario를 선택하고 `open_world_evidence_ready`까지 계산한다
- 그런데 representative dynamic lane는 이 값이 `true`여도 최종적으로 `deterministic_fallback`으로 닫힌다
- 즉 selected branch와 materialized branch의 인과가 약하다

왜 문제인가:

- 목표는 “research/selection이 만든 understanding이 actual vulnerable app/Docker로 이어지는 것”인데, 현재는 selection surface와 build surface가 부분적으로만 연결된다
- selection이 풍부해도 fallback이 same-family minimal dynamic builder로 닫혀 버리면, 연구 기반 dynamic insertion이 아니라 bounded salvage path가 된다

실제 증거:

- `common/contracts.py:4267-4278`에서 `open_world_evidence_ready` 계산
- `open-redirect-dynamic-name-only` run에서 `selection_open_world_evidence_ready=true`
- 그런데 same run은 `generation_origin=deterministic_fallback`, `materializer=minimal_dynamic`, `name_only_decision=partial`

개선 방향:

1. selection result가 actual generator branching input으로 강제돼야 한다
2. selected scenario가 어떤 materializer, 어떤 file set, 어떤 runtime/oracle contract를 열었는지 one-shot causal trace를 남겨야 한다
3. selected branch를 충족하지 못하면 그냥 fallback success로 닫지 말고 “selection-to-materialization mismatch”로 surface해야 한다

구체적 개선안:

- `selection_decision`을 read-only summary가 아니라 generator branching contract로 승격
- `selection_branch_trace`는 이미 있지만, fail reason을 더 강하게 남겨야 한다
  - selected branch
  - attempted branch
  - why branch diverged
  - whether divergence was fallback, safety block, schema repair, or dependency failure
- `open_world_evidence_ready=true`인데 final branch가 fallback이면 promotion/measured gate 전에 generator 단계에서 별도 failure class를 부여

우선순위:

- 최상위

관련 ticket:

- `TKT-001-B`
- `TKT-001-D`
- `TKT-001-I`

### 4.4 generator가 여전히 one-shot manifest + fallback architecture에 묶여 있다

현재 문제:

- synthesis failure 시 `semantic_guided` 또는 family-aware fallback으로 빠지기 쉽다
- `agents/generator/synthesis.py`는 여러 family에 대해 `_minimal_dynamic_manifest_*`를 제공하고, 이게 degraded recovery의 주 경로가 된다
- `open-redirect-dynamic-name-only`는 실제로 `fallback_class=semantic_guided`, `materializer=minimal_dynamic`

왜 문제인가:

- 목표는 live LLM response가 dynamic insertion을 주도하는 것인데, 지금은 “LLM이 실패하면 bounded family fallback이 artifact를 보장하는” 구조가 더 강하다
- 이 구조는 runnable demo에는 유리하지만, open-world claim을 계속 약하게 만든다

실제 증거:

- `agents/generator/synthesis.py:2257` 이후 `_semantic_guided_fallback_resolution`
- `agents/generator/synthesis.py:2385` 이후 `_semantic_guided_fallback_manifest`
- `agents/generator/synthesis.py:2401-2412`의 family별 `_minimal_dynamic_manifest_*`
- `agents/generator/synthesis.py:2427-2438`의 `fallback_class=semantic_guided`, `materializer`

개선 방향:

1. fallback은 유지하되, positive proving-ground lane에서는 fallback이 success로 보이지 않게 해야 한다
2. live dynamic generation path를 one-shot이 아니라 staged iterative synthesis로 강화해야 한다
3. manifest validity만 통과하는 것이 아니라 design-brief/runtime-plan/oracle-contract/file-manifest까지 모두 충족해야 positive로 읽히게 해야 한다

구체적 개선안:

- `staged_synthesis.stage_order`를 실질 단계로 확장
  - candidate_resolution
  - design_brief
  - runtime_plan
  - oracle_contract
  - file_manifest
  - build_contract
  - run_contract
- fallback을 “delivery mechanism”이 아니라 “explicit degraded lane”로 강등
- live-positive lane에서는 `fallback_used=true`인 순간 generator success가 아니라 degraded classification으로 바로 종료
- one-shot JSON manifest 대신 stage-specific prompts와 stage-specific repair loops를 분리

우선순위:

- 매우 높음

관련 ticket:

- `TKT-006-A`
- `TKT-006-B`
- `TKT-006-C`
- `TKT-006-D`
- `TKT-006-E`

### 4.5 live LLM positive path contract가 아직 약하다

현재 문제:

- strict fail-closed는 강하지만, positive live path는 fixture/stub/degraded/live를 분리해 acceptance contract로 닫지 못했다
- `trusted-dynamic-sqli`는 `llm_manifest`지만 `fixture`
- `open-redirect-dynamic-name-only`는 runtime까지 닫혀도 `stub`

왜 문제인가:

- 현재는 “LLM-shaped artifact exists”와 “live LLM positive capability exists”가 섞여 읽힐 여지가 남아 있다
- 이것 때문에 비교 lane는 많아졌지만, 실제 proving-ground는 생기지 않는다

실제 증거:

- `docs/work_tickets.md:522-523`
- `docs/work_tickets.md:575-577`
- recent support review에서
  - `by_generation_path_class = {fixture:1, stub:1}`
  - `live_positive_ready_bundle_count = 0`

개선 방향:

1. `generation_materialization`을 acceptance contract의 핵심으로 승격해야 한다
2. positive lane는 최소한 아래를 만족해야 한다
  - `path_class = live`
  - `provider_attempted = true`
  - `provider_succeeded = true`
  - `fixture_used = false`
  - `stub_fallback = false`
3. 이 조건을 만족하는 name-only dynamic lane를 별도 proving-ground case로 고정해야 한다

구체적 개선안:

- `tests/e2e/cases/live-name-only-positive-*` 계열의 canonical lane 추가
- same lane에 대해 direct / repeat / support workflow까지 full chain을 canonical baseline으로 승격
- `fixture_backed_positive`, `degraded_fallback_positive`, `live_positive`를 matrix axis와 support policy vocabulary에서 명시 분리

우선순위:

- 매우 높음

관련 ticket:

- `TKT-006-D`
- `TKT-008-A3`
- `TKT-009-A1-C`

### 4.6 runtime control-plane은 improved 되었지만 generalized topology synthesis는 아직 아니다

현재 문제:

- runtime_recipe, executor_plan, staged_synthesis.executor_plan은 존재한다
- sidecar/network/env/seed surface도 많이 보강됐다
- 하지만 현재 topology class는 사실상 `single_service`, `service_plus_sidecar` 정도의 bounded ladder다

왜 문제인가:

- open-world dynamic insertion이 실제로 강해지려면 generator가 runtime topology, dependencies, env, seed, sidecars를 연구 결과에서 재구성해야 한다
- 현재는 repo prior와 bounded contract alignment가 강하다

실제 증거:

- `docs/work_tickets.md:527`
- `docs/constraints.md:221` 이후 executor/runtime constraint
- `open-redirect-dynamic-name-only`는 single_service, no sidecar, bounded Flask lane로 닫힘

개선 방향:

1. proving-ground topology ladder를 명시해야 한다
2. 현재는 `single_service -> service_plus_sidecar` 수준만 strong regression으로 읽고, 그 위를 explicit next target으로 올려야 한다
3. topology/runtime closure를 research-derived dependency planning과 직접 연결해야 한다

구체적 개선안:

- topology ladder를 문서/평가/CI에 고정
  - single_service
  - service_plus_db
  - service_plus_supporting_sidecar
  - multi_primary_web_pair
  - browserful_lab_topology
- runtime dependency hypothesis가 actual sidecar/env/seed materialization으로 이어지는 trace 추가

우선순위:

- 높음

관련 ticket:

- `TKT-002-A/B/C/D`
- `TKT-003-A/B`
- `TKT-004-A/B`
- `TKT-005-A/B/C`

### 4.7 oracle realism은 일부 실행되지만 proving-ground quality gate로는 아직 약하다

현재 문제:

- negative control, metamorphic surface가 생겼다
- 일부 lane는 `oracle_execution_parity=high`까지 간다
- 하지만 fixture-backed positive lane는 여전히 `oracle_execution_parity=missing`
- browserful/stateful realism은 아직 partial이다

왜 문제인가:

- 목표가 “학습용 취약 Docker”라면, runnable만으로는 부족하고 exploit oracle이 충분히 realistic해야 한다
- 지금은 oracle richness와 executed oracle closure가 lane별로 분리된다

실제 증거:

- `docs/constraints.md:251-256`
- Docker-enabled rerun에서
  - `open-redirect-dynamic-name-only`: `oracle_execution_parity=high`
  - `trusted-dynamic-sqli`: `oracle_execution_parity=missing`

개선 방향:

1. oracle richness와 execution parity를 same rubric 위에서 관리해야 한다
2. representative positive lane가 모두 negative control / metamorphic / stateful/sessionful execution을 포함하도록 올려야 한다

구체적 개선안:

- realism rubric axis 명시
  - exploit-path diversity
  - negative controls
  - metamorphic consistency
  - statefulness
  - verifier independence
  - cleanup reproducibility
- same rubric을 artifact_quality / measured_gate / support promotion에 직접 연결

우선순위:

- 중상

관련 ticket:

- `TKT-007-A`
- `TKT-007-B`
- `TKT-007-C`

### 4.8 “runnable but not promotable”를 깨는 accept-path proving ground가 없다

현재 문제:

- positive pair는 direct rerun에서 둘 다 실행되지만 support review에서는 계속 `blocked_mixed`
- 실제 추가 검증에서도
  - `authority_ready_bundle_count = 2`
  - `reviewable_bundle_count = 0`
  - `registry_item_count = 0`

왜 문제인가:

- 현재 시스템은 runnable artifact demo로는 유효하지만, “좋은 open-world artifact를 만들었다”는 acceptance path가 없다
- 결과적으로 연구/생성/실행이 다 있어도 final product signal이 약하다

실제 증거:

- `docs/work_tickets.md:452`
- `docs/work_tickets.md:484-485`
- recent Docker-enabled support review:
  - `by_generation_positive_bucket = {fixture_backed_positive:1, degraded_fallback_positive:1}`
  - `live_positive_ready_bundle_count = 0`

개선 방향:

1. first promotable proving ground를 명시적으로 정의해야 한다
2. comparator lane와 target lane를 분리해야 한다
3. support review가 empty registry no-op로만 끝나지 않도록 최소 하나의 live-positive accepted lane를 만들어야 한다

구체적 개선안:

- comparator lane
  - `trusted-dynamic-sqli`
  - `open-redirect-dynamic-name-only`
- target lane
  - live LLM + name-only + dynamic Docker + reviewable
- support_apply acceptance minimum
  - `generation_path_live_positive_ready = true`
  - `mechanically_healthy = true`
  - `promotion_policy_ready = true`
  - `build_ready = true`
  - `build_safety_safe = true`

우선순위:

- 매우 높음

관련 ticket:

- `TKT-009-A1`
- `TKT-009-A1-A`
- `TKT-009-A1-B`
- `TKT-009-A1-C`

## 5. 우선순위 제안

현재 목표를 가장 빠르게 진전시키는 개선 순서는 아래가 맞다.

1. `selection/controller authority`를 강화한다
- 이유: selection이 materialization을 못 지배하면 나머지 개선도 계속 fallback로 흘러간다

2. `live-positive materialization contract`를 명시한다
- 이유: fixture/stub/degraded/live를 acceptance level에서 분리해야 진짜 목표를 측정할 수 있다

3. `staged synthesis`를 one-shot manifest에서 multi-stage branch controller로 바꾼다
- 이유: 현재 visible blocker의 대부분이 여기서 나온다

4. `runtime/file_manifest/build contract`를 selection과 직접 연결한다
- 이유: “연구 기반 계획”과 “실제 Docker branch”를 같은 causal chain으로 묶어야 한다

5. `oracle realism rubric`을 measured/support gate에 직접 연결한다
- 이유: runnable demo와 promotable artifact를 가르는 마지막 질적 차이기 때문이다

6. 마지막으로 `first reviewable live name-only lane`를 고정한다
- 이유: 이게 생겨야 현재 목표에 대한 첫 실증이 된다

## 6. 최소 구현 목표

현재 목표를 “실제로 조금 전진했다”고 부를 수 있는 최소 기준은 아래다.

1. `name-only` dynamic lane에서 researcher가 skip되지 않는다
2. selected family/stack/scenario가 generator branch를 실제로 결정한다
3. final `generation_materialization.path_class = live`
4. final `generation_origin = llm_manifest`
5. `fallback_used = false`
6. Docker build/run/verify가 성공한다
7. support review에서 `reviewable_bundle_count >= 1`

이 일곱 개가 동시에 닫히지 않으면, 현재 목표는 여전히 partially met로 읽는 편이 정확하다.

## 7. 최종 결론

현재 구현은 실패를 정직하게 드러내고, bounded family 안에서 취약 Docker artifact를 생성하는 시스템으로서는 상당히 좋아졌다.

하지만 원래 목표를 기준으로 보면, 핵심 부족점은 명확하다.

- researcher가 항상 authoritative하지 않다
- request IR가 너무 빨리 resolved closed-world surface로 굳는다
- selection이 materialization branch를 충분히 지배하지 못한다
- generator가 live dynamic synthesis보다 fallback architecture에 더 많이 기대고 있다
- runtime/oracle이 닫혀도 support-ready/live-positive proving ground가 없다

따라서 앞으로의 개선은 “family 수를 늘리는 것”보다 아래에 집중하는 것이 맞다.

- controller authority
- live-positive contract
- staged synthesis
- selection-to-materialization causality
- first reviewable live name-only lane

현재 목표 대비 부족한 본질은 coverage가 아니라 authority와 provenance다.

