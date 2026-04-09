# Open-World Name-Only Dynamic Docker 검증 기록

작성일: 2026-04-09

## 1. 검증 목적

다음 의도가 현재 구현 로직에 실제로 충분히 반영되어 있는지 검증했다.

> "open world에서 name-only 입력과 LLM 응답만으로 취약점을 동적으로 삽입한 모델 학습용 Docker를 생성한다"

이번 검증은 단순 문서 비교가 아니라 아래 두 축을 함께 본다.

- 코드 경로 검증: 입력 정규화, researcher, generator, executor, pack가 어떤 기준으로 분기하는지 확인
- 실제 실행 검증: 현재 워크스페이스에서 실행 가능한 representative case를 직접 돌려 결과를 확인

## 2. 최종 판정

결론부터 말하면, 현재 구현은 위 의도를 "정직하게 제한된 형태로" 반영하고 있으나, 그 문장을 그대로 만족한다고 보기에는 부족하다.

- `name-only` control-plane honesty와 fail-closed 정책 반영 수준: 높음
- bounded family/stack 안에서의 동적 생성 시도 및 Docker 산출물 생성 수준: 중간
- `open world`, `name-only`, `LLM response only`, `strict positive`를 동시에 만족하는 수준: 낮음

즉 현재 구현의 정확한 상태는 아래에 가깝다.

> "bounded catalog/known-family 기반의 name-only 입력을 해석하고, researcher/generator contract를 통해 동적 생성 또는 lower-bound/degraded fallback을 수행하며, Docker 산출물을 만들 수 있다. 다만 generalized open-world name-only + live-LLM only positive generation capability는 아직 아니다."

이 평가는 저장소의 현재 canonical 문서와도 일치한다.

- `README.md`는 현재 시스템을 "bounded regression platform"과 "degraded dynamic generation"으로 설명하고 generalized open-world generator는 아직 발전 중이라고 명시한다.
- `docs/constraints.md`는 degraded fallback이나 lower-bound closure를 generalized open-world success로 읽으면 안 된다고 명시한다.

## 3. 검증 환경

- 작업 디렉터리: `/home/ysw/vulDocker`
- 실행일: 2026-04-09
- Python: `/home/ysw/anaconda3/bin/python`
- Docker 바이너리 경로: `/mnt/c/Program Files/Docker/Docker/resources/bin/docker`
- 현재 세션의 Docker 상태: WSL 2 distro integration 미활성으로 실제 `docker build` 불가

실제 확인:

- `docker ps` 실행 시 "The command 'docker' could not be found in this WSL 2 distro." 반환
- 따라서 runtime build/run 검증은 현재 세션에서 완전하게 끝까지 닫을 수 없고, `PLAN -> RESEARCH -> GENERATOR` 및 no-Docker lane 중심으로 검증했다

## 4. 이번에 실제 실행한 검증

### 4.1 focused regression slice

실행:

```bash
python -m pytest -q \
  tests/test_name_only_helpers.py \
  tests/test_pack_promotion.py \
  tests/test_contract_resolution.py \
  tests/test_support_extract.py \
  tests/e2e/test_support_workflow.py \
  tests/e2e/test_case_matrix_rollup.py
```

결과:

- `222 passed in 0.61s`

의미:

- name-only decision policy
- pack/open-world classification
- contract resolution
- measured/support workflow surface

가 현재 워크스페이스에서 깨지지 않았음을 확인했다.

### 4.2 no-Docker representative lanes

실행:

```bash
python tests/e2e/run_case.py --case tests/e2e/cases/open-redirect-strict-dynamic-no-remote --mode deterministic --no-snapshot --output-dir /tmp/vuld_audit_strict_no_remote
python tests/e2e/run_case.py --case tests/e2e/cases/open-redirect-strict-dynamic-stub --mode deterministic --no-snapshot --output-dir /tmp/vuld_audit_strict_stub
python tests/e2e/run_case.py --case tests/e2e/cases/foobar-name-only-negative --mode deterministic --no-snapshot --output-dir /tmp/vuld_audit_foobar_negative
```

결과:

- 세 케이스 모두 expectations satisfied

핵심 summary:

1. `open-redirect-strict-dynamic-no-remote`
- `pipeline_result='failure'`
- `terminal_failure_class='strict_dynamic_remote_research_unavailable'`
- `generation_origin='capability_gate_rejected'`
- `dynamicness_verdict='pre-generation fail-closed'`
- `open_world_class='name_driven_capability_gate_failed'`
- `name_only_decision='fail_closed'`

2. `open-redirect-strict-dynamic-stub`
- `pipeline_result='failure'`
- `terminal_failure_class='strict_dynamic_live_llm_unavailable'`
- `generation_origin='capability_gate_rejected'`
- `dynamicness_verdict='pre-generation fail-closed'`
- `open_world_class='name_driven_capability_gate_failed'`
- `name_only_decision='fail_closed'`

3. `foobar-name-only-negative`
- `pipeline_result='failure'`
- `terminal_failure_class='semantic_support_missing'`
- `generation_origin='research_short_circuit'`
- `dynamicness_verdict='pre-generation fail-closed'`
- `open_world_class='unsupported_free_form_negative'`
- `name_only_decision='abstain'`

의미:

- strict_dynamic은 실제로 live LLM / remote research capability가 없으면 fail-closed 한다
- unsupported free-form name은 억지 생성이 아니라 abstain으로 닫힌다
- 즉 "무엇을 못 하는지 정직하게 surface"하는 control-plane은 꽤 강하다

## 5. 코드 경로별 상세 검증

### 5.1 입력은 정말 "name-only" 그대로 들어가나

부분적으로만 그렇다.

`common/schema/requirement.py`에서 free-form 이름은 그대로 generator로 가지 않고 먼저 resolution/normalization을 거친다.

핵심 경로:

- `_name_resolution()`에서 `vuln_name`을 catalog alias 또는 synthetic name으로 변환
- `_build_request_ir()`에서 `request_ir.resolution_state`, `identifier_candidates`, `family_candidates`, `stack_candidates`, `scenario_candidates`를 구성

실제 코드 근거:

- `common/schema/requirement.py:619` 이후: `vuln_name`을 alias 또는 synthetic name으로 해석
- `common/schema/requirement.py:496` 이후: `request_ir` 생성
- `common/vuln_catalog.py:195` 이후: label overlap과 catalog resolution으로 family candidate 생성

실제 실행 근거:

- `open-redirect-name-only`
  - `request_ir.request_label = "Open Redirect"`
  - `request_ir.resolution_state = "catalog_alias"`
  - `request_ir.selection_decision.family.top_family = "open_redirect"`
- `open-redirect-dynamic-name-only`
  - 동일하게 `resolution_state = "catalog_alias"`

판정:

- "name-only 입력을 받는다"는 맞다
- 하지만 "raw open-world name을 아무 사전 지식 없이 바로 생성기로 넘긴다"는 아니다
- 현재 입력은 catalog-backed bounded normalization을 거친다

### 5.2 open world family induction이 실제로 열려 있는가

아니다. 현재는 bounded family vocabulary다.

코드 근거:

- `common/vuln_catalog.py`는 catalog 기반 alias, token set, strategy variant를 제공
- `docs/constraints.md`는 family hypothesis space가 closed-vocabulary라고 명시

실제 실행 근거:

- `Open Redirect`는 open-vocabulary discovery가 아니라 `catalog_alias -> open_redirect`로 닫힌다
- `Foobar`는 unknown family를 임의로 induction하지 않고 `NAME-FOOBAR` synthetic name 후 `semantic_support_missing`로 fail-closed 된다

판정:

- "open world"라는 표현을 엄격하게 읽으면 현재 구현과 맞지 않는다
- 현재는 "unknown text를 bounded known family로 매핑 가능한 경우에 한해 처리"에 가깝다

### 5.3 researcher가 실제로 open-world planning을 강화하는가

일부는 그렇지만, 여전히 bounded planner다.

코드 근거:

- `agents/researcher/service.py:118` 이후: query plan, search hit, evidence graph, family hypothesis, tech stack candidate, guard spec 생성
- `common/contracts.py:4194` 이후: `request_ir.selection_decision` 구성
- `common/contracts.py:4273`: `open_world_evidence_ready`는 family/stack/scenario evidence-backed 여부로 계산

실제 실행 근거: `open-redirect-dynamic-name-only`

- researcher는 실제로 실행되었고 다음 산출물을 기록했다
  - `metadata/sid-6d54d136cf12/researcher_report.json`
  - `metadata/sid-6d54d136cf12/guard_spec.json`
  - `metadata/sid-6d54d136cf12/runtime_rules/name-open-redirect.yaml`
- researcher 결과
  - `quality = sufficient`
  - `search_policy = remote_prefer`
  - `family_hypothesis_summary.top_family = open_redirect`
  - `tech_stack_candidates[0].stack_id = python/flask`
- `resolved_contract.json` 안의 `request_ir.selection_decision`
  - `family.selected = true`
  - `stack.selected = true`
  - `scenario.selected = true`
  - `open_world_evidence_ready = true`

중요한 해석:

- selection/evidence surface는 꽤 상세하다
- 그러나 이 selection은 catalog/evidence-backed top choice이지, arbitrary unknown family/scenario를 자유롭게 발견하는 open-world planner는 아니다

### 5.4 generator가 실제로 "LLM response only"로 동작하는가

그렇지 않다.

generator 이전과 중간에 이미 다음이 강하게 개입한다.

- catalog resolution
- compiler support / lower bound
- static/runtime rule
- guard spec
- request_ir / runtime_recipe / executor_plan / exploit_oracle / staged_synthesis contract

코드 근거:

- `common/contracts.py:319` 이후 `build_generator_contract()`가 resolved contract를 구성
- 같은 함수에서 `request_ir`, `runtime_recipe`, `executor_plan`, `name_only_generation_spec`, `staged_synthesis`, `semantic_profile`, `lower_bound`, `compiler_supported`를 generator에 주입
- `common/contracts.py:4469` 이후 high-confidence `catalog_alias` 또는 `exact_identifier`이면 catalog entry로 family working hypothesis를 다시 고정

실제 실행 근거:

1. `open-redirect-name-only`
- researcher skipped
- generator는 synthesis를 시도하지 않고 compiler path로 바로 종료
- `generation_origin = compiler_generated`
- `llm_execution.path_class = not_executed`
- `compiler_strategy = open_redirect_reflect`

즉 이 lane은 "LLM response only"와 가장 거리가 멀다.

2. `open-redirect-dynamic-name-only`
- generator는 synthesis mode로 실행
- 하지만 결과는
  - `generation_origin = deterministic_fallback`
  - `fallback_class = semantic_guided`
  - `materializer = minimal_dynamic`
  - `dynamic_eval.status = degraded_success`
  - `llm_execution.path_class = stub`
  - `last_error_class = provider_disabled`
- `resolved_contract.json`에는 동시에
  - `compiler_supported = true`
  - `compiler_strategy = open_redirect_reflect`

즉 이 lane은 dynamic planning surface를 쓰지만, 최종 artifact는 live LLM only generation이 아니라 semantic-guided deterministic fallback이다.

3. `trusted-dynamic-sqli`
- generator는 `generation_origin = llm_manifest`
- `llm_execution.path_class = fixture`
- `selected_candidate.llm_execution.fixture_path = tests/e2e/cases/trusted-dynamic-sqli/llm_generator_manifest.json`
- 동시에 `compiler_supported = true`, `compiler_strategy = sqli_string_concat`
- researcher는 skipped

즉 이 lane은 llm-shaped artifact를 쓰지만

- name-only lane가 아니고
- fixture-backed이며
- known-family lower-bound 정보가 같이 존재한다

판정:

- 현재 구현은 "LLM response를 활용할 수 있는 bounded generator"다
- 그러나 "name-only + LLM response only"만으로 동작하는 구조는 아니다

### 5.5 generator가 Docker 산출물을 실제로 만드는가

그렇다. 이 부분은 구현되어 있다.

실제 실행으로 생성된 workspace:

- `workspaces/sid-e1bd28588c98/app`
- `workspaces/sid-6d54d136cf12/app`
- `workspaces/sid-1f57335c6d9e/app`

세 케이스 모두 아래 파일을 실제로 생성했다.

- `Dockerfile`
- `README.md`
- `app.py`
- `poc.py`
- `requirements.txt`

실제 예시:

1. compiler-first `open-redirect-name-only`
- `app.py`는 `request.args.get('next')` 값을 그대로 `redirect()`로 전달
- 주석까지 "Registry-backed compiler fragment"라고 명시

2. degraded dynamic `open-redirect-dynamic-name-only`
- `app.py`는 `/redirect` route에서 `next` 파라미터를 그대로 `redirect()`에 전달
- `Dockerfile`은 `python:3.11-slim`, `pip install -r requirements.txt`, `EXPOSE 8000`, `CMD ["python", "app.py"]`

3. fixture-backed `trusted-dynamic-sqli`
- `app.py`는 sqlite DB를 초기화하고 `/login`에서 string concatenation SQL injection을 수행

판정:

- "학습용 취약 Docker 산출물 생성" 자체는 구현되어 있다
- 다만 그 생성 provenance가 open-world live-LLM-only는 아니다

### 5.6 staged synthesis와 executor plan은 실제로 존재하는가

존재한다. 다만 authoritative runtime control-plane으로 완전히 닫힌 상태는 아니다.

실제 실행 근거: `open-redirect-dynamic-name-only`의 `resolved_contract.json`

- `executor_plan`
  - `topology = single_service`
  - `service_port = 8000`
  - `service_entry = app.py`
  - `poc_entry = poc.py`
  - `health_path = /health`
  - `network_mode = none`
- `staged_synthesis.executor_plan`
  - `validator = executor_plan_contract`
  - `repair_policy = reuse_runtime_plan_and_runtime_graph`
- `staged_synthesis.runtime_plan`
  - `stack_id = python/flask`
  - `topology = single_service`
  - `db = none`
- `staged_synthesis.oracle_contract`
  - `success_signature = Exploit SUCCESS`
  - `flag_token = FLAG{OPEN_REDIRECT_OK}`
  - `negative_control_present = true`
  - `metamorphic_present = true`

판정:

- planner/control-plane surface는 생각보다 상세하게 들어와 있다
- 하지만 이것이 곧 open-world native generation proof는 아니다
- 실제 materialization은 여전히 compiler path 또는 semantic-guided fallback에 의해 크게 좌우된다

### 5.7 pack/open-world 판정 로직은 의도에 정직한가

그렇다. 오히려 현재 구현의 강점은 "과장하지 않는 판정"이다.

코드 근거:

- `common/name_only.py`
  - mode별 allowed closure / intent success rule을 분리
- `orchestrator/pack.py:2666` 이후
  - open-world verdict 계산
- `orchestrator/pack.py:2877` 이후
  - strict_open_world verdict 계산
- `orchestrator/pack.py:5530` 이후
  - intent satisfaction 계산
- `orchestrator/pack.py:5754` 이후
  - `intent_met`, `partial`, `abstain`, `fail_closed` 계산

실제 동작:

- compiler-first compatibility lane는 lower-bound success로만 읽음
- degraded dynamic lane는 `partial`로 읽음
- strict capability 부족은 `fail_closed`
- unsupported name은 `abstain`

실제 실행 근거:

- `open-redirect-name-only`
  - compiler-first
  - open-world positive로 계산되지 않음
- `open-redirect-dynamic-name-only`
  - `dynamic_eval.status = degraded_success`
  - repo expectation도 `strict_minimal_dynamic_fallback`, `partial`, `counts_as_generalization=false`
- `open-redirect-strict-dynamic-*`
  - 둘 다 fail-closed
- `foobar-name-only-negative`
  - abstain

판정:

- "현재는 아직 그 claim을 하면 안 된다"는 honesty surface는 구현 의도 이상으로 잘 반영되어 있다

## 6. end-to-end runtime 검증 결과

현재 세션에서는 Docker build/run을 끝까지 닫지 못했다.

실제 실행:

```bash
VUL_FORCE_LLM_STUB=1 VUL_FORCE_LLM_STUB_REASON=provider_disabled \
python orchestrator/run_pipeline.py --sid sid-6d54d136cf12 --mode deterministic
```

실행 흐름:

- RESEARCH 성공
- GENERATOR 성공
- EXECUTOR build 진입
- `docker build`에서 실패

실제 build log:

```text
The command 'docker' could not be found in this WSL 2 distro.
We recommend to activate the WSL integration in Docker Desktop settings.
```

의미:

- generator가 Dockerfile과 runtime plan을 만든 것까지는 실제 확인됨
- 하지만 현재 세션에서는 actual build/run/oracle replay를 끝까지 재검증할 수 없었음
- 따라서 "current workspace-local run on 2026-04-09" 기준 final runtime truth는 부분 검증으로 읽어야 한다

## 7. 의도 문장에 대한 항목별 판정

### 7.1 "open world에서"

판정: 아니오

근거:

- family resolution이 catalog alias / token match / synthetic name 기반 bounded space에 묶여 있음
- unknown family는 generalized discovery가 아니라 fail-closed 또는 abstain으로 닫힘
- repo 문서 자체도 generalized open-world capability를 현재 non-claim으로 둠

### 7.2 "name-only 입력"

판정: 예, 단 bounded normalization을 거친다는 조건부

근거:

- `vuln_name`만 받아 request identity / request_ir를 구성함
- 다만 raw string은 바로 generator로 가지 않고 catalog-backed resolution과 candidate IR로 변환됨

### 7.3 "LLM 응답만으로"

판정: 아니오

근거:

- catalog, compiler support, rule resolution, semantic profile, guard spec, request_ir, executor_plan이 모두 실질적으로 개입함
- compatibility lane는 실제로 LLM 미사용 compiler path
- dynamic lane는 실제로 deterministic fallback 가능
- positive LLM-shaped lane도 fixture-backed comparator

### 7.4 "취약점을 동적으로 삽입"

판정: 부분적으로 예

근거:

- dynamic synthesis lane와 staged synthesis surface는 존재
- 실제 `open-redirect-dynamic-name-only`는 generator가 synthesis 경로를 타며 Docker 산출물을 만듦
- 하지만 최종 provenance는 `deterministic_fallback + semantic_guided + minimal_dynamic`
- 즉 "dynamic insertion attempt"는 맞지만 "strong open-world native insertion"은 아니다

### 7.5 "모델 학습용 Docker를 생성"

판정: 예

근거:

- 실제로 Dockerfile/app/poc/requirements/README가 생성됨
- 다만 current session에서 Docker integration 문제로 build/run 완료까지는 확인하지 못함

## 8. 종합 결론

현재 구현은 다음 두 가지를 강하게 만족한다.

1. name-only lane를 과장하지 않고 정직하게 분류한다
2. bounded family 안에서는 vulnerable Docker artifact를 실제로 생성할 수 있다

하지만 다음은 아직 만족하지 못한다.

1. generalized open-world family induction
2. name-only + live LLM response only 기반 native generation
3. strict/open-world positive를 end-to-end로 입증하는 name-only proving ground

따라서 현재 구현을 설명할 때는 아래 표현이 정확하다.

> "name-only 입력을 bounded catalog/evidence contract로 해석하고, compiler path 또는 synthesis/fallback path를 통해 취약 Docker artifact를 생성하는 시스템"

아래 표현은 현재 구현과 맞지 않는다.

> "open world에서 name-only 입력과 LLM 응답만으로 취약점을 동적으로 삽입한 Docker를 생성하는 시스템"

## 9. 후속 권고

이 의도를 실제 claim 수준으로 끌어올리려면 최소한 아래가 더 필요하다.

1. live LLM + name-only + dynamic Docker positive lane를 별도 proving ground로 확보
2. catalog/lower-bound 의존 없이도 strict open-world positive로 닫히는 representative case 확보
3. measured/support workflow에서 `reviewable/promotable`까지 올라가는 name-only positive lane 확보
4. 현재 WSL 세션의 Docker integration 복구 후 actual build/run/oracle replay 재검증

