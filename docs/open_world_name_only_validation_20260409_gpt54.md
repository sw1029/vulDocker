# GPT-5.4 기준 재검증 기록

작성일: 2026-04-09

관련 선행 문서:

- [open_world_name_only_validation_20260409.md](/home/ysw/vulDocker/docs/open_world_name_only_validation_20260409.md)

## 1. 이번 재검증의 목적

기존 검증을 `gpt-5.2` 기본값이 아니라 `gpt-5.4` 기본값으로 다시 확인한다.

검증 질문은 두 가지다.

1. 시스템 기본 LLM 모델이 실제로 `gpt-5.4`로 전환되었는가
2. 그렇게 바꿔도 기존 결론, 즉 현재 구현이 `open world + name-only + LLM-only` strict claim에는 아직 못 미친다는 판정이 유지되는가

## 2. 코드 변경

기본 모델 상수를 `common.llm.DEFAULT_LLM_MODEL = "gpt-5.4"`로 추가하고 다음 경로를 이 상수를 보도록 바꿨다.

- `orchestrator/plan.py`
- `agents/researcher/service.py`
- `agents/generator/service.py`
- `agents/reviewer/service.py`
- `evals/poc_verifier/llm_assisted.py`

함께 정렬한 테스트:

- `tests/test_llm_provider_fixture.py`
- `tests/test_plan_sid_isolation.py`
- `tests/test_researcher_search_artifacts.py`
- `tests/test_run_case_summary_surface.py`
- `tests/test_support_extract.py`

## 3. 회귀 결과

실행:

```bash
python -m pytest -q \
  tests/test_name_only_helpers.py \
  tests/test_pack_promotion.py \
  tests/test_contract_resolution.py \
  tests/test_support_extract.py \
  tests/test_llm_provider_fixture.py \
  tests/test_plan_sid_isolation.py \
  tests/test_researcher_search_artifacts.py \
  tests/test_run_case_summary_surface.py \
  tests/e2e/test_support_workflow.py \
  tests/e2e/test_case_matrix_rollup.py
```

결과:

- `260 passed in 2.41s`

해석:

- 기본 모델 전환으로 인한 control-plane regression은 보이지 않았다
- model surface를 직접 검증하는 summary/provider fixture test도 같이 통과했다

## 4. no-Docker representative 재검증

실행:

```bash
python tests/e2e/run_case.py --case tests/e2e/cases/open-redirect-strict-dynamic-no-remote --mode deterministic --no-snapshot --output-dir /tmp/vuld_gpt54_strict_no_remote
python tests/e2e/run_case.py --case tests/e2e/cases/open-redirect-strict-dynamic-stub --mode deterministic --no-snapshot --output-dir /tmp/vuld_gpt54_strict_stub
python tests/e2e/run_case.py --case tests/e2e/cases/foobar-name-only-negative --mode deterministic --no-snapshot --output-dir /tmp/vuld_gpt54_foobar_negative
```

결과:

- 세 케이스 모두 expectations satisfied

summary 핵심:

1. `open-redirect-strict-dynamic-no-remote`
- `terminal_failure_class = strict_dynamic_remote_research_unavailable`
- `generation_origin = capability_gate_rejected`
- `dynamicness_verdict = pre-generation fail-closed`
- `name_only_decision = fail_closed`

2. `open-redirect-strict-dynamic-stub`
- `terminal_failure_class = strict_dynamic_live_llm_unavailable`
- `generation_origin = capability_gate_rejected`
- `dynamicness_verdict = pre-generation fail-closed`
- `name_only_decision = fail_closed`

3. `foobar-name-only-negative`
- `terminal_failure_class = semantic_support_missing`
- `generation_origin = research_short_circuit`
- `dynamicness_verdict = pre-generation fail-closed`
- `name_only_decision = abstain`

해석:

- `gpt-5.4`로 바꿔도 strict fail-closed honesty와 unsupported negative abstain behavior는 그대로 유지된다

## 5. stage-by-stage 재검증

새 SID를 `gpt-5.4` 기준으로 다시 만들고 `RESEARCH -> GENERATOR`까지 재실행했다.

대상:

- `open-redirect-name-only`
- `open-redirect-dynamic-name-only`
- `trusted-dynamic-sqli`

### 5.1 compiler-first compatibility lane

SID:

- `sid-e9fd9c7ffd8d`

관찰:

- `plan.json.sid_inputs.components.model_version = gpt-5.4`
- `generation_origin = compiler_generated`
- `llm_execution.model = gpt-5.4`
- `llm_execution.path_class = not_executed`
- `compiler_strategy = open_redirect_reflect`

해석:

- compatibility lane는 여전히 compiler-first이며, live LLM generation lane로 바뀌지 않는다
- 모델 기본값만 바뀌었고 generation provenance 자체는 바뀌지 않았다

### 5.2 dynamic name-only lane

SID:

- `sid-19b5a3371c45`

관찰:

- `plan.json.sid_inputs.components.model_version = gpt-5.4`
- `generation_origin = deterministic_fallback`
- `llm_execution.model = gpt-5.4`
- `llm_execution.path_class = stub`
- `llm_execution.stub_fallback = true`
- `llm_execution.last_error_class = provider_disabled`
- `compiler_supported = true`
- `compiler_strategy = open_redirect_reflect`

해석:

- `gpt-5.4`로 바꿔도 representative dynamic lane는 여전히 `semantic_guided` degraded fallback lane이다
- 즉 "dynamic attempt"는 유지되지만 strict live-positive open-world lane로 상승하지 않는다

### 5.3 fixture-backed positive comparator lane

SID:

- `sid-6e7ee29c62e8`

관찰:

- `plan.json.sid_inputs.components.model_version = gpt-5.4`
- generator 로그에 `LiteLLM completion() model= gpt-5.4`
- `generation_origin = llm_manifest`
- `llm_execution.model = gpt-5.4`
- `llm_execution.path_class = fixture`
- `llm_execution.fixture_used = true`
- `llm_execution.last_error_class = quota_exhausted`
- `compiler_strategy = sqli_string_concat`

해석:

- 이 lane는 여전히 fixture-backed positive comparator다
- `gpt-5.4` live provider 경로가 일부 auxiliary call에서 시도되었지만 quota failure가 발생했고, selected candidate provenance는 fixture 기반으로 남았다
- 따라서 이 lane도 "live LLM + name-only + open-world positive" 증거는 아니다

## 6. Docker-enabled direct rerun

이번 추가 검증 시점에는 Docker가 실제로 활성화돼 있었다.

실제 확인:

```bash
docker info --format '{{json .ServerVersion}} {{json .OperatingSystem}}'
```

결과:

- `ServerVersion = 27.4.0`
- `OperatingSystem = Docker Desktop`

추가 direct rerun:

```bash
python tests/e2e/run_case.py --case tests/e2e/cases/open-redirect-name-only --expectations tests/e2e/cases/open-redirect-name-only/expectations.json --mode deterministic --no-snapshot --output-dir /tmp/vuld_gpt54_docker_open_redirect_name_only
python tests/e2e/run_case.py --case tests/e2e/cases/open-redirect-dynamic-name-only --expectations tests/e2e/cases/open-redirect-dynamic-name-only/expectations.json --mode deterministic --no-snapshot --output-dir /tmp/vuld_gpt54_docker_open_redirect_dynamic
python tests/e2e/run_case.py --case tests/e2e/cases/trusted-dynamic-sqli --expectations tests/e2e/cases/trusted-dynamic-sqli/expectations.json --mode deterministic --no-snapshot --output-dir /tmp/vuld_gpt54_docker_trusted_dynamic
```

결과:

- 세 케이스 모두 expectations satisfied

핵심 summary:

1. `open-redirect-name-only`
- `pipeline_result = success`
- `generation_origin = compiler_generated`
- `dynamicness_verdict = compiler-first`
- `run_passed = true`
- `verify_pass = true`
- `stage_ceiling = fully_validated`
- `oracle_execution_parity = high`
- `name_only_decision = intent_met`
- `open_world_class = catalog_resolved_lower_bound`
- `strict_open_world_class = strict_curated_lower_bound`
- `generation_materialization.model = gpt-5.4`

2. `open-redirect-dynamic-name-only`
- `pipeline_result = success`
- `generation_origin = deterministic_fallback`
- `dynamicness_verdict = deterministic fallback dependent`
- `provider_health_state = llm_degraded`
- `run_passed = true`
- `verify_pass = true`
- `stage_ceiling = fully_validated`
- `oracle_execution_parity = high`
- `name_only_decision = partial`
- `open_world_class = semantic_guided_minimal_dynamic`
- `strict_open_world_class = strict_minimal_dynamic_fallback`
- `generation_materialization.model = gpt-5.4`
- `generation_materialization.path_class = stub`

3. `trusted-dynamic-sqli`
- `pipeline_result = success`
- `generation_origin = llm_manifest`
- `dynamicness_verdict = trusted dynamic`
- `provider_health_state = llm_fixture`
- `run_passed = true`
- `verify_pass = true`
- `stage_ceiling = fully_validated`
- `oracle_execution_parity = missing`
- `name_only_decision = not_applicable`
- `open_world_class = known_family_regression`
- `strict_open_world_class = strict_fixture_backed_dynamic`
- `generation_materialization.model = gpt-5.4`
- `generation_materialization.path_class = fixture`

해석:

- Docker runtime이 실제로 열려도 compiler-first lane는 그대로 bounded lower-bound lane다
- representative dynamic name-only lane는 runtime/oracle까지 닫히지만 여전히 degraded fallback + `partial`이다
- fixture-backed comparator lane도 runtime/oracle 일부는 닫히지만 여전히 fixture-based strict exclusion 상태다

## 7. Docker-enabled repeatability/support workflow

positive pair에 대해 repeatability/support review도 다시 실행했다.

실행:

```bash
python tests/e2e/repeat_case.py --case tests/e2e/cases/trusted-dynamic-sqli --expectations tests/e2e/cases/trusted-dynamic-sqli/expectations.json --mode deterministic --no-snapshot --output-dir /tmp/vuld_gpt54_repeat_trusted_dynamic
python tests/e2e/repeat_case.py --case tests/e2e/cases/open-redirect-dynamic-name-only --expectations tests/e2e/cases/open-redirect-dynamic-name-only/expectations.json --mode deterministic --no-snapshot --output-dir /tmp/vuld_gpt54_repeat_open_redirect_dynamic
python tests/e2e/support_review.py /tmp/vuld_gpt54_repeat_trusted_dynamic /tmp/vuld_gpt54_repeat_open_redirect_dynamic --output /tmp/vuld_gpt54_support_review_positive_pair.json
python tests/e2e/support_decide.py --review-index /tmp/vuld_gpt54_support_review_positive_pair.json --decisions /tmp/vuld_gpt54_support_decisions_empty.json --output /tmp/vuld_gpt54_support_update_positive_pair.json
python tests/e2e/support_apply.py --registry-update /tmp/vuld_gpt54_support_update_positive_pair.json --output /tmp/vuld_gpt54_support_registry_positive_pair.json
```

결과:

- 두 repeatability report 모두 `passed = true`
- support review는 여전히 positive pair를 `reviewable = 0`으로 판단
- apply preview도 `registry_item_count = 0`

핵심 summary:

1. `trusted-dynamic-sqli` repeatability
- `measured_gate.ready = false`
- blockers:
  - `cache_reuse_inconsistent`
  - `artifact_quality_band_not_high`
  - `oracle_execution_parity_not_high`
  - `generation_path_not_live_positive`

2. `open-redirect-dynamic-name-only` repeatability
- `measured_gate.ready = false`
- blockers:
  - `artifact_quality_band_not_high`
  - `generation_path_not_live_positive`

3. positive pair support review
- `support_candidate_file_count = 2`
- `authority_ready_bundle_count = 2`
- `measured_gate_blocked_bundle_count = 2`
- `reviewable_bundle_count = 0`
- `by_support_status = {blocked_mixed: 2}`
- `by_generation_path_class = {fixture: 1, stub: 1}`
- `by_generation_positive_bucket = {fixture_backed_positive: 1, degraded_fallback_positive: 1}`
- `by_generation_non_live_reason = {fixture_backed: 1, provider_disabled: 1}`
- `live_positive_ready_bundle_count = 0`
- `live_positive_blocked_bundle_count = 2`

4. registry apply preview
- `registry_item_count = 0`
- `schema_status = normalized`

해석:

- Docker runtime이 실제로 열려도 current measured/support policy 결론은 바뀌지 않는다
- positive pair는 둘 다 runnable/authority-ready지만 still not reviewable/not promotable이다
- current residual은 여전히 generation-path non-live, artifact-quality, oracle-parity 쪽이다

## 8. 이전 판정 대비 달라진 점

달라진 점:

- 기본 모델 표면이 실제로 `gpt-5.4`로 바뀌었다
- planner SID component와 generator `llm_execution.model`까지 `gpt-5.4`로 기록된다
- fixture comparator lane의 provider log도 `gpt-5.4`로 찍힌다
- Docker-enabled direct rerun 기준 `open-redirect-name-only`, `open-redirect-dynamic-name-only`, `trusted-dynamic-sqli`가 모두 actual build/run/verify까지 다시 닫혔다

달라지지 않은 점:

- compatibility lane는 compiler-first
- representative dynamic name-only lane는 degraded fallback
- strict capability 부족 lane는 fail-closed
- unsupported free-form lane는 abstain
- positive pair는 Docker runtime이 열려도 support review에서 여전히 `blocked_mixed`
- current session의 main blocker는 Docker availability가 아니라 live-positive/support-ready 부재

## 9. 최종 결론

`gpt-5.4`로 기본 모델을 바꿔 재검증해도 선행 문서의 핵심 결론은 유지된다.

즉 현재 구현은 여전히 아래에 가깝다.

> bounded catalog/evidence contract를 통해 name-only 입력을 해석하고, compiler path 또는 synthesis/fallback path로 취약 Docker artifact를 생성하는 시스템

아직 아래 수준은 아니다.

> open world에서 name-only 입력과 live LLM 응답만으로 취약점을 동적으로 삽입한 Docker를 안정적으로 생성하는 시스템

이번 재검증은 "모델 버전이 올라가면 기존 한계가 사라지는가"를 확인하는 의미가 있었고, 결과는 아니다.

- 기본 모델 표면은 바뀌었다
- Docker-enabled runtime truth는 다시 열렸다
- 그러나 open-world/generalization claim boundary와 support promotion 결론은 바뀌지 않았다
