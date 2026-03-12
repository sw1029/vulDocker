# 동적 취약 Docker 생성 Current State / Gap Analysis

본 문서는 2026-03-12 KST 기준 current workspace를 다시 실행·검토한 뒤,
현재 구현의 truth, 특히 `name-only` / open-world 관점의 현 상태와 다음 단계 계획을
단일 기준으로 정리한 문서다.

이 문서는 append-only 메모가 아니다.
현재 truth, 현재 한계, 이번 iteration의 보완 범위, 이후 staged refactor 입력을
한 문서 안에서 연결해 두는 authoritative source다.

## 1. Truth Protocol

- current workspace rerun과 현재 코드만 현재 상태의 1차 근거로 사용한다.
- `compiler-first`, `template-assisted`, `trusted dynamic`, `deterministic fallback dependent`,
  `research_short_circuit`는 현재 manifest taxonomy 그대로 사용한다.
- legacy `generalization_*`는 하위 호환 surface로만 보고, open-world 평가는
  `open_world_*`, `strict_open_world_*`, `intent_satisfaction_*`, `template_dependence_*`를 우선한다.
- `name-only`는 더 이상 단순 alias normalization 문제가 아니다.
  input intent, closure path, verifier independence, degraded path를 함께 본다.
- 이 문서의 목표는 과장된 capability claim을 줄이고,
  향후 staged refactor를 위한 decision-complete input을 남기는 것이다.

## 2. Current Truth Baseline

### 2.1 실행 기준선

2026-03-13 local rerun:

| command | result | 해석 |
| --- | --- | --- |
| `python -m pytest -q tests` | `523 passed, 53 skipped in 2.12s` | unit/integration baseline 유지 |
| `VULD_RUN_E2E=1 python -m pytest -q tests/e2e/test_cases.py -rs` | `51 passed, 2 skipped in 483.54s` | 공식 Docker E2E baseline 유지 |

즉 현재 구현은 regression platform 관점에서는 여전히 닫혀 있다.
다만 E2E wall-clock은 이전 문서 수치보다 다소 늘었다.

이번 round에서는 `open_redirect`, `xss`, `path_traversal`, `ssrf`, `deserialization`, `sqli`, `csrf`, `template_injection`,
`command_injection`, `code_injection`, `ldap_injection`, `xxe`의 dynamic name-only lane을
manual rerun만이 아니라 official E2E contract에도 추가했다.
즉 current supported semantic family 전체의 degraded dynamic lane이
이제 문서상의 관찰치가 아니라 repo-tracked regression target이다.

추가로 `strict_dynamic` posture에 대해서도
`Open Redirect + forced stub`, `Open Redirect + no remote provider` fail-closed lane을 official E2E contract에 올렸다.
즉 strict lane은 여전히 positive baseline이 아니라 negative/fail-closed baseline이지만,
적어도 "strict precondition이 깨진 경우 어디서 어떻게 멈추는가"는 이제 repo-tracked target이다.

또한 `exploit_oracle`는 이제 success signature뿐 아니라
`flag_token` assertion까지 deterministic하게 포함하도록 보강됐다.
즉 current oracle surface는 아직 `oracle_contract@1` 수준은 아니지만,
summary-grade에서 한 단계 더 structured한 contract로 이동했다.

이번 round의 추가 코드 보완은 아래 두 축이 핵심이었다.

- `request_ir.name_driven` + high-confidence catalog family를 synthesis 내부에서도 실제 anchor로 읽도록 보강
  - family hypothesis가 noisy/ambiguous해도 ranked support가 충분하면 semantic-guided minimal dynamic recovery를 계속 시도
- guard semantic-signature alias 확장
  - `code parameter -> eval(code)` flow
  - `LDAP filter construction / wildcard-or-OR bypass` 표현을 actual minimal-dynamic artifact에서 abstract하게 인정
- `CWE-502` declared verifier rule 추가
  - deserialization minimal-dynamic lane도 `declared_rule/high/independent` verification으로 승격
- XSS minimal-dynamic builder 정렬
  - Flask minimal-dynamic XSS artifact가 `render_template_string` + request-bound `name` + explicit template variable 흐름을 사용하도록 보정
- `request_ir` execution gating 정렬
  - generator / researcher / run_pipeline / synthesis prompt가 이제 `request_ir.name_driven`을 직접 읽는다
  - canonicalized `CWE-*`나 token-match lane에서도 name-only dynamic/strict_dynamic intent가 덜 손실된다
- `strict_dynamic` live-LLM gate 추가
  - RESEARCH 단계가 stub/fixture/degraded live-LLM path로 닫히면 GENERATOR 전에 `NAME_ONLY_GATE`에서 fail-closed
  - strict lane에서는 이후 subprocess circuit breaker가 stub를 강제하지 않도록 정렬
- `strict_dynamic` capability precheck 추가
  - forced stub / fixture env / missing key / missing litellm뿐 아니라,
    `remote_required`인데 remote search provider가 local configuration 수준에서 성립하지 않는 경우도
    `CAPABILITY_CHECK`에서 RESEARCH 전에 fail-closed
  - official strict negative E2E는 이제 이 precheck surface를 기준으로 고정된다
- `request_ir` primaryization 추가 보강
  - requirement normalization의 researcher/pipeline policy default도 이제 `request_ir.name_driven`을 직접 읽는다
  - canonicalized `CWE-*` + name-driven lane이 planning/skip-policy 단계에서 `NAME-*` prefix 유무 때문에 덜 흔들린다
- `request_ir` contract/reviewer 정렬
  - canonicalized `CWE-*` + `request_ir.name_driven` lane도 semantic contract에서 free-form fragment signature를 사용할 수 있다
  - reviewer도 이런 lane을 static-rule-known-family로 건너뛰지 않고 low-confidence semantic issue를 계속 surface할 수 있다
- `runtime_graph@0.1` shadow surface 도입
  - `runtime_recipe`에서 derived graph를 만들어 resolved contract / PACK manifest / E2E summary에 같이 노출
  - node / edge / env_contract / exploit_path 수준의 topology preview가 생겼지만, 아직 authoritative control plane은 아니다
- stack boundedness surface 추가
  - `stack_dependence_summary` / bundle-level `stack_dependence`를 manifest와 E2E summary에 노출
  - template dependence와 stack dependence를 같은 숫자로 뭉개지 않고 분리해서 본다
- name-only generation spec boundedness 보강
  - `family_candidate_summary`, `stack_candidate_summary`를 generator contract와 prompt에 추가
  - generator prompt가 이제 working family/stack뿐 아니라 candidate count, ambiguity, source/confidence까지 직접 읽는다
- ambiguous stack candidate override 완화
  - contract/runtime_recipe와 semantic-guided fallback은 이제 unambiguous + medium/high confidence researcher stack candidate만 직접 채택
  - ambiguous researcher stack 후보는 repo prior(`profile_prior`/`available_skeleton`)보다 우선하지 않게 정렬
- semantic-guided family overcommit 완화
  - semantic-guided fallback이 이제 첫 매칭 family를 바로 고르지 않고 semantic candidate set을 만든 뒤 disambiguation을 시도
  - multi-match일 때는 `request_resolution` / strong researcher family signal이 없으면 abstain하고 generic fallback으로 되돌림
  - 선택되더라도 `semantic_guided_selection_source`, `semantic_guided_ambiguous`, `semantic_guided_abstain_reason`가 metadata/provenance에 남는다
- canonicalized name-driven family fallback loophole 정리
  - `allow_name_family_fallback`는 이제 `NAME-*` prefix lane뿐 아니라 canonicalized `CWE-*` + `request_ir.name_driven` lane에도 동일하게 적용
  - 즉 semantic-guided가 abstain한 뒤 known-family asset template로 silently 재진입하는 경로를 기본값에서 막고, explicit opt-in일 때만 허용
- family dependence surface 추가
  - bundle-level `family_dependence`와 manifest-level `family_dependence_summary`를 추가
  - template / stack / family boundedness를 서로 다른 축으로 분리해 current generalized capability를 더 정직하게 본다
- semantic-support-required 판정 정렬
  - canonicalized `CWE-*` + `request_ir.name_driven` lane도 `requires_semantic_support_for_requirement(...)`를 통해 free-form/name-only semantic gate 대상으로 본다
  - researcher preseed fail-closed / run_pipeline semantic-profile precheck / reviewer confidence surface가 이 판정을 공유한다
- `NAME-XXE` declared rule 보완
  - Flask `request.get_data()`와 FastAPI `await request.body()` 둘 다 현재 minimal-dynamic artifact로 인정하도록 widened

### 2.2 현재 공식 identity

현재 레포에 대해 강하게 말할 수 있는 것은 아래다.

- 지원 family에 대해서는 deterministic compiler-first lower bound가 안정적이다.
- built-in template lane은 소수지만 현실감 있는 baseline artifact를 제공한다.
- unsupported/low-trust/open-world 실패를 success처럼 보이게 하지 않는 fail-closed 철학이 강하다.
- provenance, verification trust, semantic surface, lower-bound/open-world separation은 꽤 정직하다.
- `name-only` lane도 이제 compatibility / dynamic / strict_dynamic intent를 구분해서 surface한다.

반대로 아직 강하게 말하면 안 되는 것은 아래다.

- arbitrary free-form 취약점 이름만으로 open-world하게 app/PoC/Docker를 안정적으로 생성한다.
- unknown family on unknown stack을 generalized하게 materialize한다.
- live provider 기반 trusted-dynamic success가 official acceptance baseline에 포함돼 있다.
- template dependence가 구조적으로 해소되었다.

정확한 현재 평가는 한 문장으로 요약된다.

> 현재 vulDocker는 "지원 family에 대한 regression platform"으로는 강하지만,
> "generalized open-world dynamic vulnerability Docker generator"로 보기에는 아직 이르다.

### 2.3 현재 inventory

current workspace 기준 inventory:

- catalog family entry: 12
- compiler strategy: 13
- scaffold asset: 2 (`python/flask`, `python/fastapi`)
- built-in template directory: 3 (`sqli` 2, `csrf` 1 / family root는 2)
- fallback asset template: 20
- semantic-guided `minimal_dynamic` coverage: 12
  - `open_redirect`, `xss`, `path_traversal`, `ssrf`, `deserialization`, `sqli`, `csrf`, `template_injection`
  - `command_injection`, `code_injection`, `ldap_injection`, `xxe`

중요한 점은 이것이 곧 open-world coverage를 뜻하지 않는다는 것이다.
실제 open-world 상한은 현재 skeleton pool, family hints, verifier independence, provider health에 더 크게 제한된다.

## 3. Current Name-Only Behavior Contract

### 3.1 현재 mode 의미

현재 구현은 `name_only_mode`를 아래처럼 해석한다.

| mode | 현재 의도 | 현재 truth |
| --- | --- | --- |
| `compatibility` | catalog/compiler/template closure 허용 | 구현되어 있고 가장 안정적 |
| `dynamic` | Researcher-first + synthesis-first, degraded closure는 partial success | 구현되어 있으나 아직 evaluation 성격이 강함 |
| `strict_dynamic` | live/non-degraded/non-self-derived만 허용 | fail-closed surface는 있으나 성공 상한이 낮음 |

추가로 `policy.dynamic_eval=true`는 default 운영을 바꾸는 것이 아니라
lower-bound shortcut을 우회해 upper bound를 관찰하는 evaluation hook에 가깝다.

### 3.2 representative rerun

#### A. `inputs/name_only_mode_dynamic.yml`

current rerun `sid-b57485510ab9`

- `pipeline_result=success`
- `generation_origin=deterministic_fallback`
- `dynamicness_verdict=deterministic fallback dependent`
- `open_world_class=semantic_guided_minimal_dynamic`
- `strict_open_world_class=strict_minimal_dynamic_fallback`
- `intent_satisfaction.status=degraded_dynamic_success`
- `intent_satisfaction.meets_intent=false`
- `artifact_quality.band=medium`
- `provider_health_state=llm_degraded`
- `llm_stub_used=true`
- `llm_failure_class=quota_exhausted`
- `total_duration_s=16.017`
- `semantic_guided_selection_source=semantic_signature`
- `family_dependence.class=semantic_signature_bounded`
- `family_dependence.selection_source=semantic_signature`
- `semantic_guided_ambiguous=false`
- `stack_dependence.class=repo_prior_bounded`
- `stack_dependence.stack_source=profile_prior`
- `stack_dependence.candidate_count=2`
- `stack_dependence.ambiguous=true`

즉 dynamic posture는 current workspace에서 runnable degraded recovery까지는 닫히지만,
open-world positive로 해석할 수는 없다.
또한 current surface는 template dependence만 줄여 보는 것이 아니라,
실제 stack choice가 ambiguous researcher candidate 때문에 과도하게 흔들리지 않고,
repo prior bounded state로 닫히는지도 함께 드러낸다.
동시에 family selection도 현재는 `semantic_signature` 단독 선택으로 닫혔고,
multi-match semantic overlap 시에는 이제 provenance에 selection/abstain 이유가 남는다.
즉 동일한 degraded dynamic artifact라도 현재는
`template_dependence=minimal_dynamic`, `stack_dependence=repo_prior_bounded`,
`family_dependence=semantic_signature_bounded`처럼 서로 다른 boundedness 층위를 따로 읽을 수 있다.

#### B. `inputs/name_only_mode_strict_dynamic.yml`

current rerun `sid-8c6918dbcc12`

- `pipeline_result=failure`
- `failure.stage=NAME_ONLY_GATE`
- `failure.terminal_failure_class=strict_dynamic_disallowed_llm_path`
- `provider_health_state=strict_dynamic_disallowed_llm_path`
- `open_world_class=name_driven_live_llm_gate_failed`
- `strict_open_world_class=strict_dynamic_live_llm_required`
- `generalization_class=real_free_form_precondition_failed`
- `intent_satisfaction.status=strict_dynamic_failed`
- `llm_stub_used=true`
- `total_duration_s=7.041`

즉 strict_dynamic posture는 현재 environment에서 여전히 fail-closed 되지만,
이제는 RESEARCH가 stub/quota/auth 경로로 닫힌 순간 GENERATOR 전에 바로 멈춘다.
이것은 이전보다 더 correct한 behavior에 가깝다.

추가로 official strict negative E2E인 `open-redirect-strict-dynamic-stub`는
forced stub env가 보이면 `CAPABILITY_CHECK`에서 더 일찍 멈춘다.
또 다른 strict negative E2E인 `open-redirect-strict-dynamic-no-remote`는
remote search provider가 local configuration 수준에서 비어 있으면
`CAPABILITY_CHECK`에서 바로 fail-closed 된다.

current rerun `sid-2d9076e23cbf`

- `pipeline_result=failure`
- `failure.stage=CAPABILITY_CHECK`
- `failure.terminal_failure_class=strict_dynamic_remote_research_unavailable`
- `provider_health_state=strict_dynamic_remote_research_unavailable`
- `dynamicness_verdict=pre-generation fail-closed`
- `open_world_class=name_driven_capability_gate_failed`
- `strict_open_world_class=strict_dynamic_capability_unavailable`
- `intent_satisfaction.status=strict_dynamic_failed`
- `total_duration_s=0.059`

즉 current strict lane에는 두 종류의 fail-closed surface가 생겼다.

- local capability만으로 즉시 판단 가능한 경우: `CAPABILITY_CHECK`
  - live LLM precondition 실패
  - remote-required researcher precondition 실패
- live call 후에야 관측되는 quota/auth/provider drift: `NAME_ONLY_GATE`

다만 이것이 곧 full capability preflight가 있다는 뜻은 아니다.
현재 구현은 아직도 quota/auth 같은 일부 failure를
"한 번의 RESEARCH 실행으로 live-LLM contract 파손을 관측한 뒤 fail-closed"하는 수준에 가깝다.

#### C. `Template Injection` / `name_only_mode=dynamic`

current rerun `sid-06190a82e83c`

- `pipeline_result=success`
- `generation_origin=deterministic_fallback`
- `open_world_class=semantic_guided_minimal_dynamic`
- `strict_open_world_class=strict_minimal_dynamic_fallback`
- `intent_satisfaction.status=degraded_dynamic_success`
- `intent_satisfaction.meets_intent=false`
- `template_dependence_summary.minimal_dynamic_bundles=1`
- `template_dependence_summary.name_only_lower_bound_bundles=1`
- `artifact_quality.band=medium`
- `provider_health_state=llm_degraded`
- `llm_stub_used=true`
- `llm_failure_class=quota_exhausted`
- `total_duration_s=18.461`

즉 `Template Injection`은 current pipeline에서도 semantic-guided minimal dynamic degraded closure까지는 닫힌다.
이것은 unit test 수준이 아니라 actual pipeline/runtime/pack까지 통과한 관측이다.

#### D. `SQL Injection` / `name_only_mode=dynamic`

current rerun `sid-fc154557c7f0`

- `pipeline_result=success`
- `generation_origin=deterministic_fallback`
- `open_world_class=semantic_guided_minimal_dynamic`
- `strict_open_world_class=strict_minimal_dynamic_fallback`
- `generalization_class=real_free_form_non_generalizing`
- `intent_satisfaction.status=degraded_dynamic_success`
- `intent_satisfaction.meets_intent=false`
- `template_dependence_summary.minimal_dynamic_bundles=1`
- `template_dependence_summary.name_only_lower_bound_bundles=1`
- `artifact_quality.band=medium`
- `provider_health_state=llm_degraded`
- `llm_stub_used=true`
- `llm_failure_class=quota_exhausted`
- `total_duration_s=19.215`

이번 보완 이후 primary open-world surface는 이 case를 더 이상 `known_family_regression`으로 접지 않는다.
즉 alias-resolved `name-only` 요청이 `CWE-*`로 canonicalize되어도,
`request_ir.name_driven`이면 PACK summary는 semantic-guided minimal dynamic degraded lane으로 유지된다.

추가로 dynamic name-only lane에 한해서는 legacy `generalization_class`도
`real_free_form_non_generalizing`으로 정렬됐다.
즉 deprecated compatibility surface가 완전히 해결된 것은 아니지만,
적어도 dynamic lane에서는 primary truth와의 충돌이 줄었다.

#### E. `Command Injection` / `name_only_mode=dynamic`

current rerun `sid-57de794eb81a`

- `pipeline_result=success`
- `generation_origin=deterministic_fallback`
- `open_world_class=semantic_guided_minimal_dynamic`
- `strict_open_world_class=strict_minimal_dynamic_fallback`
- `generalization_class=real_free_form_non_generalizing`
- `intent_satisfaction.status=degraded_dynamic_success`
- `intent_satisfaction.meets_intent=false`
- `template_dependence_summary.minimal_dynamic_bundles=1`
- `template_dependence_summary.name_only_lower_bound_bundles=1`
- `artifact_quality.band=medium`
- `verification_rule_source=declared_rule`
- `verification_independence=independent`
- `verification_trust=high`
- `provider_health_state=llm_degraded`
- `llm_stub_used=true`
- `total_duration_s=15.369`

즉 `Command Injection`도 current pipeline에서 semantic-guided minimal dynamic degraded closure까지는 닫힌다.
추가로 이번 iteration에서 `CWE-78` declared verifier rule을 보강한 뒤,
이 case는 `declared_rule/high/independent` verification으로 승격됐다.
즉 coverage 확장과 verifier quality 보강이 실제 같은 lane에서 동시에 반영된 첫 사례다.

#### F. `XML External Entity` / `name_only_mode=dynamic`

current rerun `sid-169859ea4371`

- `pipeline_result=success`
- `generation_origin=deterministic_fallback`
- `open_world_class=semantic_guided_minimal_dynamic`
- `strict_open_world_class=strict_minimal_dynamic_fallback`
- `generalization_class=real_free_form_non_generalizing`
- `intent_satisfaction.status=degraded_dynamic_success`
- `intent_satisfaction.meets_intent=false`
- `template_dependence_summary.minimal_dynamic_bundles=1`
- `template_dependence_summary.name_only_lower_bound_bundles=1`
- `artifact_quality.band=medium`
- `verification_independence=independent`
- `verification_trust=high`
- `provider_health_state=llm_degraded`
- `llm_stub_used=true`
- `total_duration_s=27.506`

즉 `XXE` 계열도 current pipeline에서 degraded minimal dynamic lane으로 닫힌다.
현재 supported semantic family 전반에 대해 semantic-guided minimal dynamic recovery가 실제 runtime까지 닫히는 근거가 늘어난 셈이다.

#### G. `Code Injection` / `name_only_mode=dynamic`

current rerun `sid-03b819602bc4`

- `pipeline_result=success`
- `generation_origin=deterministic_fallback`
- `open_world_class=semantic_guided_minimal_dynamic`
- `strict_open_world_class=strict_minimal_dynamic_fallback`
- `generalization_class=real_free_form_non_generalizing`
- `intent_satisfaction.status=degraded_dynamic_success`
- `intent_satisfaction.meets_intent=false`
- `template_dependence_summary.minimal_dynamic_bundles=1`
- `template_dependence_summary.name_only_lower_bound_bundles=1`
- `verification_rule_source=declared_rule`
- `verification_independence=independent`
- `verification_trust=high`
- `llm_stub_used=true`
- `total_duration_s=14.907`

이 case는 이번 round에서 실제로 닫힌 가장 중요한 gap 중 하나다.
이전에는 researcher family hypothesis가 `sqli`로 흔들리면서
semantic-guided recovery가 막혀 `name_driven_dynamic_failed`로 끝날 수 있었다.
지금은 `request_ir`의 high-confidence family anchor와 ranked family support를 같이 읽어서,
noisy family hypothesis가 있어도 `code_injection` minimal dynamic degraded lane으로 닫힌다.

#### H. `LDAP Injection` / `name_only_mode=dynamic`

current rerun `sid-b8bdc487fd08`

- `pipeline_result=success`
- `generation_origin=deterministic_fallback`
- `open_world_class=semantic_guided_minimal_dynamic`
- `strict_open_world_class=strict_minimal_dynamic_fallback`
- `generalization_class=real_free_form_non_generalizing`
- `intent_satisfaction.status=degraded_dynamic_success`
- `intent_satisfaction.meets_intent=false`
- `template_dependence_summary.minimal_dynamic_bundles=1`
- `template_dependence_summary.name_only_lower_bound_bundles=1`
- `verification_rule_source=declared_rule`
- `verification_independence=independent`
- `verification_trust=high`
- `llm_stub_used=true`
- `total_duration_s=12.139`

이 case는 runtime closure 자체는 이전에도 됐지만,
workspace guard가 `exploit_precondition` 추상 표현을 artifact에서 못 읽어서 verify 단계에서 실패할 수 있었다.
지금은 LDAP filter construction, request-bound user input, wildcard/OR bypass를
semantic-signature alias로 읽도록 보강해서 current pipeline에서 `overall_pass=true`까지 닫힌다.

#### I. `Reflected XSS` / `name_only_mode=dynamic`

current rerun `sid-2ca183761869`

- `pipeline_result=success`
- `generation_origin=deterministic_fallback`
- `open_world_class=semantic_guided_minimal_dynamic`
- `strict_open_world_class=strict_minimal_dynamic_fallback`
- `generalization_class=real_free_form_non_generalizing`
- `intent_satisfaction.status=degraded_dynamic_success`
- `intent_satisfaction.meets_intent=false`
- `template_dependence_summary.minimal_dynamic_bundles=1`
- `template_dependence_summary.name_only_lower_bound_bundles=1`
- `verification_rule_source=declared_rule`
- `verification_independence=independent`
- `verification_trust=high`
- `request_ir.resolution_state=token_match`
- `llm_stub_used=true`
- `total_duration_s=14.228`

이 case는 이번 round에서 실제 코드 보완이 필요했던 family다.
기존 Flask minimal-dynamic builder가 `Response` 기반 반사 응답을 사용해
current built-in semantic/rule contract의 `render_template_string` 중심 XSS detector와 어긋났다.
지금은 builder를 detector가 이해하는 형태로 정렬해 dynamic degraded lane이 실제로 닫힌다.

#### J. 추가 official dynamic contract coverage

이번 round에서 representative rerun + official E2E contract로 추가 고정한 나머지 family는 아래다.

- `Open Redirect` / `sid-41704fcd225a`
  - `resolution_state=catalog_alias`
  - `open_world_class=semantic_guided_minimal_dynamic`
  - `verification_rule_source=declared_rule`
  - `verification_trust=high`
  - `verification_independence=independent`
  - `total_duration_s=16.834`
- `Path Traversal` / `sid-e8e86d83987f`
  - `resolution_state=catalog_alias`
  - `open_world_class=semantic_guided_minimal_dynamic`
  - `verification_rule_source=declared_rule`
  - `verification_trust=high`
  - `verification_independence=independent`
  - `total_duration_s=19.980`
- `SSRF` / `sid-b35adafab4fd`
  - `resolution_state=catalog_alias`
  - `open_world_class=semantic_guided_minimal_dynamic`
  - `verification_rule_source=declared_rule`
  - `verification_trust=high`
  - `verification_independence=independent`
  - `total_duration_s=19.620`
- `CSRF` / `sid-ef91f6673033`
  - `resolution_state=catalog_alias`
  - `open_world_class=semantic_guided_minimal_dynamic`
  - `verification_rule_source=declared_rule`
  - `verification_trust=high`
  - `verification_independence=independent`
  - `total_duration_s=24.009`
- `Insecure Deserialization` / `sid-342db185d4dd`
  - `resolution_state=catalog_alias`
  - `open_world_class=semantic_guided_minimal_dynamic`
  - `verification_rule_source=declared_rule`
  - `verification_trust=high`
  - `verification_independence=independent`
  - `total_duration_s=22.545`

즉 current supported semantic family 12개는
이제 모두 `semantic_guided minimal_dynamic degraded lane` 기준 official dynamic E2E contract에 올라가 있다.
이는 capability claim의 상향이 아니라,
현재 degraded coverage와 template-dependence 완화 범위를 repo 차원에서 회귀 관리하기 시작했다는 의미다.

### 3.3 현재 구현이 실제로 보장하는 것

- known family alias/name-only request는 compatibility lane에서 안정적으로 닫힌다.
- dynamic lane은 lower-bound bypass 관찰은 가능하지만, 실제로는 fallback/fail-closed로 자주 수렴한다.
- strict_dynamic은 “open-world positive가 아니면 실패하게 만들기” 쪽은 어느 정도 닫혔지만,
  지금은 live-LLM contract가 깨진 경우 GENERATOR 전에 더 일찍 fail-closed 된다.
- 반대로 “실제로 strict open-world positive를 만들기”는 아직 약하다.

### 3.4 현재 template dependence boundary

이번 보완 이후 semantic-guided minimal dynamic degraded lane은
현재 supported semantic family 전체로 사실상 확장됐다.

대상:

- `open_redirect`, `xss`, `path_traversal`, `ssrf`, `deserialization`, `sqli`, `csrf`, `template_injection`
- `command_injection`, `code_injection`, `ldap_injection`, `xxe`

이것이 의미하는 것은 아래다.

- degraded dynamic lane에서 family-aware asset template 의존은 더 줄었다.
- actual pipeline 기준으로도 current supported semantic family 12개 전부는 `minimal_dynamic_bundles=1`로 닫힌다.
- FastAPI-style `Query(...)` bound SQLi/command/code injection도 semantic guard가 현재 minimal dynamic 패턴을 이해한다.
- alias-resolved `name-only` request가 `CWE-*`로 canonicalize되더라도,
  primary open-world summary는 이제 `request_ir.name_driven` 기준으로 유지된다.
- summary뿐 아니라 generator/researcher/run_pipeline/prompt gating도 이제
  `request_ir.name_driven`을 직접 읽는다.
- contract/reviewer도 이제 canonicalized `CWE-*` + `request_ir.name_driven` lane을
  단순 known-family static-rule lane으로 보지 않고 더 name-only/open-world 쪽에 가깝게 해석한다.
- resolved contract / PACK / E2E summary에는 이제 `runtime_graph@0.1`이 같이 노출된다.
- semantic-support-required 판정도 이제 canonicalized `CWE-*` + `request_ir.name_driven` lane을
  static-rule-known-family로 바로 접지 않고 free-form/name-only semantic gate 대상으로 본다.
- dynamic `name-only` lane에 한해서는 deprecated `generalization_*`도
  `known_family_regression`보다는 `real_free_form_non_generalizing` 쪽으로 덜 misleading하게 정렬된다.
- 즉 current template dependence는 점점 “unsupported unknown family”와
  compatibility/template-assisted lane 쪽으로 밀리고 있다.
- `CWE-78`, `CWE-94` declared verifier rule 추가로,
  적어도 supported family 일부에서는 degraded minimal dynamic lane의 verifier quality도 같이 보강되기 시작했다.
- 이번 round의 `CWE-502` declared verifier rule 추가로,
  supported semantic family 전체가 dynamic degraded lane에서 `declared_rule/high/independent` verification inventory를 가지게 됐다.
- 이번 round의 `Code Injection`/`LDAP Injection` 보완으로,
  `request_ir` anchored recovery와 guard semantic alias 확장이 actual dynamic E2E closure에 직접 기여함이 확인됐다.
- 이번 round의 `XSS` 보완으로,
  builder 표현과 built-in semantic/rule contract가 어긋날 때 dynamic lane이 어떻게 실패하는지,
  그리고 그 mismatch를 정렬하면 actual E2E closure로 바로 이어지는지도 확인됐다.

하지만 이것이 의미하지 않는 것은 아래다.

- open-world positive coverage가 올라갔다.
- stack/template dependence가 구조적으로 해소되었다.
- early resolution bias가 사라졌다.

즉 현재 개선은 “template dependence 완화”에는 분명히 기여하지만,
여전히 Flask/FastAPI bounded stack 위의 degraded minimal dynamic recovery 확장에 가깝다.

## 4. Current Structural Gaps

### 4.0 strict_dynamic fail-fast는 이전보다 더 닫혔지만 아직 완전하지 않다

이번 보완으로 strict lane은 두 단계로 fail-fast 된다.

- local capability failure는 `CAPABILITY_CHECK`에서 RESEARCH 전에 차단
- post-RESEARCH live-LLM contract 파손은 `NAME_ONLY_GATE`에서 GENERATOR 전에 차단

이는 이전의 "stub로 계속 내려간 뒤 GENERATOR에서 의미 없는 실패"보다 낫다.

하지만 아직 완전한 capability preflight는 아니다.

- 지금의 `CAPABILITY_CHECK`는 local configuration 수준의
  live LLM/remote research precondition까지는 본다.
- quota/auth/provider drift는 여전히 한 번의 RESEARCH 호출 뒤에야 관측된다.
- 즉 strict lane의 wasted work는 줄었지만, 제거되지는 않았다.

### 4.1 request label이 너무 빨리 canonical id로 접힌다

현재 normalization은 free-form label을 비교적 이른 단계에서 `NAME-*`로 canonicalize한다.
`request_identity`와 `name_resolution`은 좋아졌지만,
raw label / unresolved hypothesis / final resolved id가 아직 충분히 분리되지 않는다.

이것은 아래 문제를 낳는다.

- catalog/token-match lower bound와 truly unresolved lane의 차이가 내부 IR에서 빨리 사라진다.
- query planning과 family hypothesis가 early resolution에 쉽게 끌린다.
- open-world lane이 사실상 “known family resolver”처럼 동작할 위험이 남는다.
- primary open-world summary는 이번 보완으로 교정됐고,
  dynamic `name-only` lane의 deprecated `generalization_*`도 일부 정렬됐다.
- generator/researcher/run_pipeline/prompt gating도 이제 `request_ir.name_driven`을 읽으므로
  execution path 쪽 early-resolution 손실은 조금 줄었다.
- requirement normalization과 researcher skip/fail-closed helper도 이제
  canonicalized `CWE-*` + `request_ir.name_driven` lane을 더 직접적으로 읽는다.
- semantic contract와 reviewer confidence surface도 같은 방향으로 조금 더 정렬됐다.
- 이번 round에서 deterministic family-aware fallback도 같은 기준으로 정렬돼,
  canonicalized `CWE-*` + `request_ir.name_driven` lane이 기본값에서 curated family asset으로 silently 재진입하지 않게 됐다.
- `runtime_graph@0.1` shadow surface가 생겨 topology preview는 더 나아졌지만,
  여전히 `runtime_recipe`에서 유도한 summary-grade graph이며 authoritative stage IR은 아니다.
- semantic-support-required 판정도 같은 방향으로 정렬됐지만,
  여전히 `request_ir`는 staged authoritative IR이 아니라 richer context payload다.
- 다만 compatibility lane과 기타 legacy surface에는 여전히 early-resolution 흔적이 남아 있다.
- 이번 round의 semantic-guided family candidate-set disambiguation은
  “첫 semantic match를 바로 채택하는 과신”을 줄였지만,
  여전히 candidate family 집합 자체는 current semantic registry와 heuristics에 bounded되어 있다.
- 그리고 `request_ir`는 아직 authoritative staged IR이 아니라,
  여러 component가 공유하는 richer context payload에 가깝다.

### 4.2 search space 자체가 아직 bounded다

current stack hypothesis pool은 사실상 `python/flask`, `python/fastapi` 두 축이다.
Researcher query planner도 finite family hints와 heuristic query seed 중심이다.

즉 현재 구조는 “arbitrary name -> arbitrary stack/topology”가 아니라,
“arbitrary-ish name -> 현재 repo가 이미 가진 Python web skeleton 위의 candidate”에 가깝다.

이번 round부터는 이 boundedness가 `template_dependence_summary`에 간접적으로만 남는 것이 아니라,
`stack_dependence_summary` / bundle-level `stack_dependence`로 직접 surface된다.
그리고 이번 round의 추가 보완으로 `family_dependence_summary` / bundle-level `family_dependence`도 생겼다.
즉 template dependence가 낮아 보여도 stack source가 `profile_prior`/`available_skeleton`/`researcher_candidate`
위에 묶여 있거나 family source가 `semantic_signature`/`request_resolution`/`researcher_family_hypothesis`
중 하나에 강하게 의존하면 generalized synthesis라고 과장하지 않게 됐다.

### 4.3 Researcher output이 아직 generator의 authoritative execution plan은 아니다

`runtime_recipe`, `exploit_oracle`, `name_only_generation_spec`는 이미 존재하지만,
generator는 여전히 one-shot synthesis prompt와 repo hints에 크게 의존한다.

current rerun에서도 `researcher_report.quality=sufficient`와 empty `guard_spec.json`이 공존했다.
즉 Researcher가 충분한 evidence를 모아도 generator를 강하게 구속하는 hard contract가 항상 생기지 않는다.

### 4.4 one-shot manifest가 여전히 main bottleneck이다

현재 synthesis는 final manifest JSON을 곧바로 요구한다.

- non-JSON이면 즉시 fallback
- guard violation이 남으면 전체 candidate fail
- repair loop도 final manifest abstraction 위에서 돈다

open-world에서 필요한 결정은
request interpretation / stack choice / topology / vuln patch / oracle / file layout인데,
현재는 이를 한 번에 맞춰야 한다.

### 4.5 runtime schema는 아직 summary-grade다

`runtime_recipe`는 useful하지만 아직 topology graph가 아니다.

현재 빠져 있는 것:

- multi-node service graph
- readiness/init ordering
- shared volumes/state lifecycle
- exploit path와 runtime dependency의 연결
- field-level provenance / confidence

즉 generalized Docker generation의 control plane으로는 아직 얕다.

### 4.6 verifier independence가 아직 약하다

rule이 없는 lane에서는 verifier가
`resolved_contract` oracle fallback,
`generator_manifest` fallback,
runtime rule synthesis에 기대는 경우가 있다.

현재 taxonomy는 이것을 low-trust/self-derived로 잘 분류하지만,
open-world positive의 의미를 강하게 만들지는 못한다.

current rerun에서도 이 차이는 여전히 드러난다.

- `sid-57de794eb81a` (`Command Injection`)는 이번 iteration에서 declared rule 보강 후
  `independent/high` verifier로 올라갔다.
- `sid-169859ea4371` (`XXE`)는 같은 degraded minimal dynamic lane에서도
  verifier가 `independent/high`다.

반대로 아직 declared verifier rule이 충분히 정리되지 않은 lane은
여전히 `self_derived/low` 또는 `contract_coupled/low`로 남을 수 있다.

즉 family coverage 확장만으로는 충분하지 않고,
oracle/verifier independence가 계속 핵심 병목이다.

### 4.7 artifact quality는 regression-friendly지만 operator-facing realism은 아직 낮다

현재 산출물의 강점:

- 작고 deterministic
- provenance/debugging이 좋음
- regression에 적합

현재 약점:

- compiler bundle은 single-route demo 성격이 강함
- fallback README는 quickstart + markers 중심
- quality scoring은 heuristic이라 사람 기준 realism과 1:1 대응하지 않음

## 5. This Iteration: Metrics/Docs First Hardening

이번 iteration의 목표는 full staged refactor가 아니다.
대신 name-only/open-world truth surface를 코드와 문서에서 일치시키는 것이다.

### 5.1 코드 보완 범위

- `request_ir@1` 추가
  - raw request, resolution state, pattern seed state, family/stack candidates, name-only contract를 단일 payload로 남김
- `name_only_contract` surface 강화
  - allowed closure sources, allowed llm paths, intent success rule을 코드상에 명시
- PACK/E2E summary 확장
  - `request_ir`, `runtime_recipe`, `dynamic_eval`, `artifact_quality`, `intent_satisfaction`
  - top-level `dynamic_eval_summary`, `artifact_quality_summary`, `template_dependence_summary`, `intent_satisfaction_summary`
- representative expectation update
  - open-redirect name-only
  - trusted dynamic fixture
  - unknown fail-closed
- semantic-guided minimal dynamic coverage 확장
  - `sqli`, `csrf`, `template_injection`을 asset fallback 우선이 아니라 `minimal_dynamic` builder 우선으로 승격
  - `request_ir` / family hypothesis / semantic signature를 같이 써서 degraded dynamic lane의 template dependence를 완화
- semantic guard 보완
  - FastAPI `Query(...)` bound SQLi를 input source / input-to-sink flow로 인식
  - template injection semantic-guided detection이 descriptive guard spec phrasing도 읽도록 확장
- semantic-guided minimal dynamic coverage 추가 확장
  - `command_injection`, `code_injection`, `ldap_injection`, `xxe`까지 builder와 detection을 확장
  - actual pipeline 기준 representative rerun(`Command Injection`, `XXE`)으로 degraded closure를 재확인
- semantic guard 추가 보완
  - FastAPI `Query(...)` bound command/code injection을 input source로 인식
  - verifier independence 차이를 current-state evidence로 추가 surface
- synthesis anchor 보완
  - `request_ir.name_driven` + high-confidence family candidate를 synthesis 내부에서도 semantic-guided fallback anchor로 사용
  - ranked family support가 충분하면 noisy top-family hypothesis가 있어도 degraded dynamic recovery를 계속 시도
- guard semantic alias 확장
  - `code parameter -> eval(code)` 흐름을 abstract semantic signature로 인정
  - LDAP filter construction / wildcard-or-OR bypass / request-bound user input을 workspace semantic signature에서 추상적으로 매칭
- XSS minimal-dynamic contract 정렬
  - Flask minimal-dynamic XSS builder를 `render_template_string` + request-bound `name` + explicit template variable 조합으로 변경
- declared verifier rule 보강
  - `CWE-78`, `CWE-94` rule 추가로 command/code injection lane의 verifier를 `declared_rule`로 승격
  - representative rerun(`Command Injection`)으로 `verification_rule_source=declared_rule`, `verification_trust=high`를 재확인
  - `CWE-502` rule 추가로 deserialization lane도 같은 declared verifier inventory에 편입
- request_ir execution gating 보강
  - `common.name_only` helper가 `request_ir.name_driven`을 primary signal로 읽도록 확장
  - generator/researcher/run_pipeline/prompt contract가 같은 signal을 공유하도록 정렬
- strict_dynamic fail-fast 보강
  - `strict_dynamic` + name-driven lane은 RESEARCH 이후 live LLM contract를 다시 검사
  - stub/fixture/degraded provider path가 관측되면 `NAME_ONLY_GATE`에서 즉시 fail-closed
  - strict lane에서는 quota/auth circuit breaker가 이후 subprocess에 stub를 강제하지 않도록 정렬
- request_ir primaryization 추가 보강
  - requirement normalization의 researcher/pipeline default가 `effective_vuln_ids` prefix 대신 `request_ir.name_driven`을 직접 읽도록 정렬
  - researcher preseed fail-closed / skip helper / intent surface도 같은 signal을 더 일관되게 사용
- strict_dynamic capability precheck 보강
  - forced stub / fixture env / missing key / missing litellm뿐 아니라
    remote-required lane의 `provider=none` / missing endpoint / missing Tavily key도 `CAPABILITY_CHECK`에서 먼저 차단
  - failure summary가 `strict_dynamic_live_llm_unavailable`,
    `strict_dynamic_remote_research_unavailable`,
    `name_driven_capability_gate_failed`,
    `strict_dynamic_capability_unavailable`를 직접 surface
- misleading generalization surface 정렬
  - strict live-LLM precondition failure는 더 이상 `real_free_form_non_generalizing`로만 뭉개지지 않고
    `real_free_form_precondition_failed`로 구분된다
- request_ir contract/reviewer 보강
  - semantic contract가 canonicalized `CWE-*` + `request_ir.name_driven` lane에서 fragment-registry signature를 사용할 수 있도록 정렬
  - reviewer confidence issue가 같은 lane에서도 계속 surface되도록 정렬
- runtime_graph shadow surface 추가
  - resolved contract가 `runtime_recipe`와 함께 `runtime_graph@0.1`을 노출
  - name-only generation spec에도 `runtime_graph_summary`를 추가해 prompt/summary에서 topology preview를 읽을 수 있게 정렬
- stack dependence surface 추가
  - bundle-level `stack_dependence`와 manifest-level `stack_dependence_summary`를 추가
  - template dependence와 stack boundedness를 별도 acceptance surface로 분리
- family dependence surface 추가
  - bundle-level `family_dependence`와 manifest-level `family_dependence_summary`를 추가
  - semantic signature / request resolution / researcher family hypothesis / curated family asset dependence를 별도 surface로 분리
- name-only prompt boundedness 보강
  - `name_only_generation_spec`에 `family_candidate_summary`, `stack_candidate_summary`를 추가
  - prompt가 candidate ambiguity/source/confidence를 직접 읽고 unsupported stack 과잉추정을 줄이게 정렬
- ambiguous researcher stack override 완화
  - `runtime_recipe`와 semantic-guided fallback은 ambiguous researcher stack candidate를 direct stack 선택 근거로 쓰지 않음
  - unambiguous + medium/high confidence candidate만 직접 채택하고, 나머지는 repo prior로 되돌림
- semantic-guided family candidate-set disambiguation
  - semantic signature가 여러 family와 겹칠 때는 `request_resolution` 또는 strong researcher family signal이 없으면 abstain
  - semantic-guided path가 선택돼도 why/how를 `semantic_guided_selection_source` 등 provenance로 남김
- canonicalized name-driven family fallback gate 정렬
  - `allow_name_family_fallback=false` 기본값은 이제 canonicalized `CWE-*` + `request_ir.name_driven` lane에도 동일하게 적용
  - semantic-guided abstain 뒤에 family-aware asset template가 다시 family를 확정하는 loophole를 차단
- semantic-support-required helper 추가
  - `requires_semantic_support_for_requirement(...)`를 도입해 canonicalized name-driven lane도 semantic gate 대상으로 일관되게 취급
  - `NAME-XXE` declared rule을 widened 해 current FastAPI minimal-dynamic artifact와 rule contract를 다시 정렬
- official strict negative contract 추가
  - `open-redirect-strict-dynamic-stub` E2E case를 추가해 `CAPABILITY_CHECK` / `strict_dynamic_live_llm_unavailable` fail-closed를 고정
  - `open-redirect-strict-dynamic-no-remote` E2E case를 추가해
    `CAPABILITY_CHECK` / `strict_dynamic_remote_research_unavailable` fail-closed도 고정

### 5.2 이번 iteration에서 하지 않는 것

- full staged synthesis 본체
- runtime graph materializer
- oracle executor verifier 본체
- new stack skeleton 대확장

즉 이번 iteration은 “truth/metrics/docs first, refactor-ready”다.

## 6. Refactor-Ready Next Steps

### 6.1 authoritative IR

다음 단계에서는 새 파일을 늘리기보다
`resolved_contract` 아래에 staged sub-schema를 두는 편이 낫다.

권장 구조:

- `request_ir@1`
- `runtime_graph@1`
- `oracle_contract@1`
- `patch_plan@1`

각 필드는 `value`, `confidence`, `source`, `evidence_ids`를 가져야 한다.

구체화:

- 목표 상태
  - early normalization은 raw request를 보존하고, canonical vuln id는 staged resolution 결과로만 승격한다.
  - bundle-level truth는 `request_identity`가 아니라 `request_ir`를 primary로 읽는다.
  - `request_ir`는 planner/generator/verifier/pack가 공통으로 읽는 최초 control plane이 된다.
- 최소 필드
  - `raw_label`, `normalized_label`, `input_mode`
  - `identifier_candidates[]`
  - `family_candidates[]`
  - `stack_candidates[]`
  - `pattern_seed_state`
  - `resolution_state`
  - `resolved_vuln_id_candidate`
  - `abstain_reason`
  - `required_contract`
- 구현 작업
  - requirement normalization에서 `request_ir`를 canonical payload로 생성
  - multi-vuln bundle split 시 `vuln_request_irs[]`를 bundle별 `request_ir`로 carry-through
  - pack summary와 E2E summary는 `request_ir`를 top-level truth로 노출
  - downstream compatibility surface는 `request_identity` / `name_resolution`를 derived legacy view로만 사용
- 리스크
  - current tests와 E2E expectations가 `request_identity` 중심이라 compatibility break 위험이 있음
  - early resolver를 늦추면 일부 alias/compiler shortcut path의 latency가 늘 수 있음
- 종료 조건
  - bundle summary에 `request_ir`가 항상 존재
  - `request_identity`가 없어도 name-only intent/summary 계산 가능
  - docs와 tests가 `request_ir`를 primary surface로 사용

### 6.2 staged synthesis

target flow:

1. `request_ir`
2. `evidence_graph`
3. `runtime_graph`
4. `oracle_contract`
5. `patch_plan`
6. deterministic materialization
7. guard/repair

LLM은 final filesystem 전체가 아니라 patch/delta를 생성해야 한다.

구체화:

- 목표 상태
  - generator는 더 이상 final manifest JSON one-shot에 의존하지 않는다.
  - LLM은 high-entropy design task만 맡고, file layout과 materialization은 deterministic backend가 맡는다.
- 단계별 산출물
  - `design_brief@1`
    - working family, stack choice, topology choice, exploit hypothesis
  - `patch_plan@1`
    - route additions, sink insertion, seed/init strategy, oracle hook plan
  - `file_manifest@1`
    - touched files, file roles, patch target locations, required dependencies
  - `materialization_report@1`
    - applied skeleton, applied patches, guard failures, auto-fix trace
- 구현 작업
  - synthesis engine을 `generate_manifest()`에서 `generate_design_brief() -> generate_patch_plan()`으로 분해
  - compiler/template/fallback asset을 final artifact source가 아니라 skeleton/patch atom source로 재배치
  - guard는 final manifest만 검사하지 말고 design/patch 단계도 검사
  - `non-JSON -> immediate fallback`을 줄이기 위해 intermediate schema를 더 작게 쪼갬
- 리스크
  - candidate scoring과 loop repair가 기존보다 복잡해짐
  - patch target abstraction이 약하면 stack-specific brittle coupling이 생길 수 있음
- 종료 조건
  - LLM output의 대부분이 small JSON schema로 제한됨
  - non-JSON failure가 final degraded closure로 즉시 이어지지 않음
  - same family / same stack에서 skeleton reuse + patch variation이 가능해짐

### 6.3 stack coverage expansion

open-world 상한을 높이려면
patch model 이전에 skeleton inventory를 늘려야 한다.

현재 가장 필요한 것은:

- stack coverage matrix
- stack별 health/readiness contract
- stack별 init/seed patterns
- stack별 oracle harness template

구체화:

- 목표 상태
  - current `python/flask`, `python/fastapi` 외에도 “known stack on unknown family”를 시험할 수 있는 최소 skeleton pool을 확보한다.
  - stack discovery와 family discovery를 분리해,
    family uncertainty가 stack choice를 과도하게 좁히지 않게 한다.
- 우선 확장 순서
  - Tier 1
    - current Python web stacks의 topology variants
    - single service / service+db / service+internal-metadata
  - Tier 2
    - JS/TS web stack 1종
    - Java or Go web stack 1종
  - Tier 3
    - non-web transport 또는 worker-style topology
- 구현 작업
  - `stack_coverage_matrix` 문서화
  - stack별 `health`, `run`, `seed/init`, `oracle harness`, `dependency bootstrap` contract 정의
  - query planner는 `stack discovery` query를 family query와 별도 scoring bucket으로 분리
  - `runtime_graph`는 stack-specific defaults를 참조하되 family-specific semantics를 섞지 않음
- 리스크
  - skeleton 수만 늘리고 patch/oracle 모델이 뒤따르지 않으면 template sprawl이 재발할 수 있음
  - E2E 비용이 크게 늘 수 있음
- 종료 조건
  - “unknown family on current Python stack” 외에 “unknown family on one additional stack” 실험이 가능
  - stack hypothesis가 current available skeleton pool을 투명하게 반영
  - docs와 metrics가 stack coverage를 명시적으로 추적

### 6.4 oracle-based verifier

rule 없는 lane에서는 아래가 필요하다.

- positive payload
- negative control
- metamorphic check
- replayable oracle contract

현재 fallback verifier는 honest하지만 independent acceptance 기준으로는 충분하지 않다.

구체화:

- 목표 상태
  - verifier는 generated artifact가 스스로 제시한 markers만 읽는 것이 아니라,
    externalized oracle contract와 replayable checks를 기준으로 판정한다.
  - unknown family lane에서도 `self_derived`가 아닌 verifier path가 생긴다.
- 최소 oracle contract 필드
  - `positive_payloads[]`
  - `negative_controls[]`
  - `metamorphic_checks[]`
  - `success_condition`
  - `forbidden_success_condition`
  - `required_runtime_observations`
- 구현 작업
  - `exploit_oracle@1`을 `oracle_contract@1` 수준으로 승격
  - verifier runner에 positive / negative / metamorphic execution lane 추가
  - current `contract_oracle_fallback`, `generator_manifest_fallback`, `runtime_rule_candidate`는 degraded trust lane으로 유지
  - pack summary는 oracle path provenance와 independence를 별도로 노출
- 리스크
  - oracle authoring 비용이 커질 수 있음
  - replay/negative control은 flaky 환경에서 false negative를 낼 수 있음
- 종료 조건
  - rule 없는 lane에서 verifier independence가 `contract_coupled/self_derived` 밖으로 올라가는 사례가 생김
  - strict open-world acceptance가 oracle executor lane을 primary로 사용

### 6.5 residual gap별 상세 진행안

현재 잔여 핵심 미비점은 아래 순서로 닫는 것이 맞다.

#### 6.5.1 Gap A. early resolution / bounded resolver bias

- 문제
  - `vuln_name -> NAME-*` early canonicalization이 open-world lane을 lower-bound friendly하게 만든다.
- 즉시 작업
  - `request_ir` 기반 resolution state tracking
  - summary/E2E/pack에서 `request_ir` 우선 사용
- 다음 단계 작업
  - planner/generator/verifier가 `resolved_vuln_id` 대신 `resolved_vuln_id_candidate`를 읽도록 점진 전환
- 성공 기준
  - alias-resolved lane과 truly unresolved lane이 metrics 상 명확히 구분됨

#### 6.5.2 Gap B. bounded stack space

- 문제
  - current open-world는 사실상 current Python web skeleton pool에 갇혀 있다.
- 즉시 작업
  - stack coverage matrix 문서화
  - stack discovery metric 추가
- 다음 단계 작업
  - topology variant skeleton 추가
  - one additional non-Python stack 추가
- 성공 기준
  - “known stack on unknown family” coverage가 actual inventory 기준으로 명시됨

#### 6.5.3 Gap C. Researcher contract weakness

- 문제
  - Researcher evidence가 sufficient여도 generator hard contract가 빈 경우가 있다.
- 즉시 작업
  - `request_ir` / `required_contract` / `family_candidates` surface 정렬
- 다음 단계 작업
  - `runtime_graph`, `oracle_contract`, `patch_plan`을 Researcher-first staged IR로 승격
- 성공 기준
  - generator prompt가 아니라 deterministic backend input이 Researcher output을 primary로 사용

#### 6.5.4 Gap D. one-shot synthesis brittleness

- 문제
  - final manifest JSON quality가 open-world capability 자체를 가린다.
- 즉시 작업
  - failure taxonomy와 hint payload를 staged refactor 입력으로 활용
- 다음 단계 작업
  - design/patch/file manifest 3-stage synthesis
- 성공 기준
  - `non-JSON -> fallback` 비율이 눈에 띄게 감소

#### 6.5.5 Gap E. runtime schema shallowness

- 문제
  - summary-grade `runtime_recipe`로는 generalized Docker generation이 어렵다.
- 즉시 작업
  - docs에서 `runtime_graph` target field 정의
- 다음 단계 작업
  - service graph / init ordering / exploit path modeling
- 성공 기준
  - planner/template/compiler/executor/verifier가 같은 topology graph를 읽음

#### 6.5.6 Gap F. verifier low independence

- 문제
  - fallback verifier path는 정직하지만 open-world positive 의미를 약하게 만든다.
- 즉시 작업
  - low-trust path taxonomy를 docs/metrics/E2E에서 더 강하게 드러냄
- 다음 단계 작업
  - oracle executor 도입
- 성공 기준
  - strict open-world positive가 self-derived verifier 없이 성립

#### 6.5.7 Gap G. artifact realism

- 문제
  - 현재 artifact quality는 heuristic이고 operator-facing realism은 여전히 낮다.
- 즉시 작업
  - README/runtime/oracle completeness metric을 공식 acceptance에 반영
- 다음 단계 작업
  - quality rubric을 `operator_readiness`, `runtime_explainability`, `exploit_explainability`, `training_value`로 세분화
- 성공 기준
  - template-assisted/native dynamic/degraded fallback 간 품질 차이가 summary와 human review 모두에서 일관되게 드러남

### 6.6 ordered execution roadmap

실행 순서는 아래가 맞다.

1. `request_ir` primary화
2. `strict_dynamic` capability gate (`CAPABILITY_CHECK`) 심화
3. acceptance wiring 강화
4. `runtime_graph@1` schema 도입
5. stack coverage matrix + skeleton variants
6. staged synthesis
7. oracle executor verifier
8. asset promotion / quarantine
9. live trusted-dynamic acceptance

이 순서를 바꾸면 아래 문제가 생긴다.

- skeleton만 늘리면 template sprawl 재발
- live acceptance를 먼저 열면 noise 증가
- staged synthesis 전에 verifier를 먼저 바꾸면 generator bottleneck이 그대로 남음

## 7. Acceptance and Metrics

### 7.1 stability

- `tests` baseline 유지
- `tests/e2e` baseline 유지
- compiler-first known lane regression 유지
- fail-closed negative lane 유지

### 7.2 name-only intent

- `intent_satisfaction.meets_intent`
- `intent_satisfaction.status`
- `closure_source`
- `llm_path`
- `strict_open_world_class`
- `failure.stage`
- `failure.terminal_failure_class`
- `performance.provider_health_state`

### 7.3 open-world

- `open_world_summary.positive_open_world_bundles`
- `strict_open_world_summary.positive_strict_open_world_bundles`
- `template_dependence_summary.lower_bound_dependent_bundles`
- `template_dependence_summary.minimal_dynamic_bundles`
- `stack_dependence_summary.repo_prior_bounded_bundles`
- `stack_dependence_summary.researcher_inferred_bundles`
- `stack_dependence_summary.ambiguous_bundles`
- `stack_dependence_summary.by_stack_source`
- `family_dependence_summary.family_bounded_bundles`
- `family_dependence_summary.ambiguous_bundles`
- `family_dependence_summary.by_class`
- `family_dependence_summary.by_selection_source`
- `family_dependence_summary.by_abstain_reason`
- `semantic_guided_selection_source`
- `semantic_guided_abstain_reason`
- `semantic_guided_ambiguous`
- `request_ir.resolution_state`
- unknown lane의 `pattern_seed_state`

### 7.4 quality

- `artifact_quality_summary.average_score`
- `artifact_quality.band`
- runtime topology clarity
- oracle clarity
- operator-facing README completeness

## 8. Final Judgment

현재 vulDocker는 이미 강한 regression platform이다.
하지만 generalized open-world dynamic Docker generator로 가기 위해 필요한 것은
“더 많은 hardcoded family 추가”가 아니라 아래다.

- raw request와 resolved id를 분리한 authoritative request IR
- summary-grade가 아닌 runtime graph / oracle contract
- one-shot manifest를 해체한 staged synthesis
- generator와 독립적인 oracle-based verifier
- 새 truth surface를 실제 E2E acceptance에 연결하는 것

이번 iteration의 역할은 이것이다.

이번 round의 추가 strict precheck 보강은
intent fidelity와 fail-closed honesty를 높였지만,
generalized materialization capability 자체를 넓힌 것은 아니다.

> name-only lane이 현재 무엇을 정확히 할 수 있는지,
> 무엇을 하지 못하는지,
> degraded path가 intent를 얼마나 만족하는지,
> template dependence가 실제로 얼마나 남아 있는지를
> 코드와 문서에서 같은 말로 고정한다.
