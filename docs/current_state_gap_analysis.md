# 동적 취약 Docker 생성 현재 상태 및 통합 실행 계획

본 문서는 2026-03-09 KST 기준 current workspace truth, 직접 재실행 결과, 코드 구조 감사, 그리고 후속 구현 우선순위를 하나로 통합한 마스터 계획 문서다.

이 문서의 목표는 단순히 “무엇이 통과하는가”를 적는 것이 아니다.
현 시점의 레포가

- 어디까지 실제로 닫혀 있는지
- 어떤 경로가 `trusted dynamic`이 아니라 `template-assisted` 또는 `deterministic fallback dependent`인지
- 어떤 lane이 generalization success가 아니라 regression lane인지
- 어떤 false positive가 산출물 신뢰성을 무너뜨리는지

를 current workspace truth 기준으로 다시 고정하는 데 있다.

이 문서 이후의 기본 원칙은 다음과 같다.

- `python -m pytest -q tests` green과 Docker E2E truth는 동일한 근거로 취급하지 않는다.
- `pass`는 반드시 provider condition, provenance, dynamicness class를 함께 기록한다.
- raw `sid-*` 값은 deterministic SID reuse 구조상 immutable evidence가 아니다.
- historical snapshot과 current workspace rerun을 같은 baseline으로 섞지 않는다.
- synthetic unknown lane과 real free-form `vuln_name` lane을 혼동하지 않는다.
- unsupported free-form/unknown lane이 generic fallback으로 “성공처럼 보이는” 현상은 최상위 defect로 다룬다.

## 1. 문서 역할과 판정 규칙

### 1.1 문서 역할

이 문서는 다음 여섯 가지 역할을 동시에 수행한다.

1. current workspace 기준 verified current state를 고정한다.
2. historical claim과 current rerun truth를 분리한다.
3. 현재 생성 경로를 `llm_manifest`, `compiler_generated`, `built_in_template`, `runtime_template_clone`, `family-aware deterministic fallback`, `generic unsupported fallback`으로 분해한다.
4. unsupported free-form false positive를 포함한 active defect를 우선순위별로 고정한다.
5. verifier/reviewer/pack/failure artifact에 대한 normative logic spec을 문서 수준에서 먼저 고정한다.
6. 이후 구현자가 바로 작업할 수 있도록 decision-complete한 integrated execution plan을 제공한다.

### 1.2 상태 판정 규칙

이 문서 이후 모든 lane/표/summary는 아래 규칙을 따른다.

- `dynamic`이라는 표현은 provenance가 `llm_manifest` 중심일 때만 쓴다.
- `compiler_generated`, `built_in_template`, `runtime_template_clone`, `family_override`, `deterministic_fallback`, `generic_unsupported_family`는 별도 class로 표기한다.
- `trusted dynamic`, `compiler-first`, `template-assisted`, `deterministic fallback dependent`는 manifest의 dynamicness verdict와 동일 의미로 쓴다.
- free-form `vuln_name -> NAME-*`는 synthetic `CWE-9999`와 다른 증거 class다.
- unsupported semantic 상태에서 exploit marker만 맞는 경우는 `run_passed=true`일 수 있어도 `verify_pass=true`의 근거가 될 수 없다.
- reviewer/pack success는 exploit marker success만으로 집계하지 않는다.

### 1.3 증거 row format

이 문서의 모든 실행 row는 최소 다음 필드를 가진다.

| field | 의미 |
| --- | --- |
| `provider_condition` | `healthy`, `llm_degraded`, `search_degraded`, `search_and_llm_degraded`, 또는 더 세분화된 failure class |
| `generation_origin` | `llm_manifest`, `compiler_generated`, `built_in_template`, `runtime_template_clone`, `family_override`, `deterministic_fallback` |
| `dynamicness` | `trusted dynamic`, `compiler-first`, `template-assisted`, `deterministic fallback dependent`, `unclassified` |
| `evidence_class` | `current workspace rerun`, `historical snapshot`, `unit test`, `repo inspection` 중 하나 |
| `observed_at` | 절대 시각 또는 문서 갱신 날짜 |
| `command` | 실행 command 또는 harness |
| `sid` | scenario id. 단, immutable evidence key가 아니라 deterministic workspace locator로만 취급 |

### 1.4 Evidence Integrity 규칙

이 문서에서 `sid-*`는 단독으로 immutable evidence가 아니다.

근거:

- SID는 deterministic hash로 계산된다.
- 동일 requirement는 동일 SID를 재사용한다.
- E2E harness는 같은 SID의 `metadata/`, `artifacts/`, `workspaces/`를 먼저 지우고 다시 생성한다.

즉, 같은 SID를 문서에 적는 것만으로 과거 결과가 보존되지 않는다.
이번 턴 구현으로 `orchestrator/run_pipeline.py`는 rerun 시작 시 stale generated state를 정리하도록 보강되었으므로,
이전 success `manifest.json`이 다음 failure rerun에 남아 current truth를 오염시키는 문제는 1차 해소되었다.
다만 rerun overwrite 자체가 사라진 것은 아니므로, raw SID는 여전히 immutable evidence key가 아니다.

추가로 이번 갱신에서는 runtime asset freshness도 한 단계 더 보강되었다.

- official harness(`tests/e2e/run_case.py`)는 now-default로 빈 seed manifest라도 기록해 `runtime_rules/`, `runtime_templates/`를 rerun 전에 완전히 purge한 뒤 seeded asset만 restore한다.
- pipeline 자체도 generated runtime rule/template를 별도 manifest로 추적해, raw `run_pipeline.py --sid ...` rerun에서도 tracked generated asset은 시작 시 제거한다.
- 즉 official E2E evidence에서는 runtime asset carry-over가 훨씬 더 강하게 차단되며, direct raw runner는 여전히 conservative하지만 최소한 tracked generated asset 기준 stale rule/template 누적은 줄었다.
- 추가로 이번 후속 구현에서 SID 입력에 `generator_mode`와 `runtime_surface_digest`가 들어가면서, 같은 vuln family/pattern이라도 generation/runtime surface가 다르면 더 이상 같은 SID로 collapse되지 않는다.

따라서 이 문서에서는 evidence를 다음 두 class로 분리한다.

- `historical snapshot`: 과거 세션에서 확보되었으나 현재 workspace artifact와 1:1로 일치한다고 보장할 수 없는 기록
- `current workspace rerun`: 이번 문서 갱신 과정에서 실제로 재실행해 현재 workspace artifact로 확인한 기록

이후 문서 갱신에서는 historical row를 current baseline처럼 서술하지 않는다.

## 2. Verified Current State

### 2.1 기본 테스트 스위트 truth

- command: `python -m pytest -q tests`
- observed_at: 2026-03-09 KST
- evidence_class: `current workspace rerun`
- result: `295 passed, 32 skipped`

이 수치는 unit/integration truth다.
하지만 `tests/e2e/test_cases.py`는 `VULD_RUN_E2E=1` 없이는 skip되므로, 이 수치를 Docker E2E 완성도와 동일시하면 안 된다.
이번 갱신 이후 공식 E2E full rerun도 별도로 다시 확인했고, `VULD_RUN_E2E=1 python -m pytest -q tests/e2e/test_cases.py -rs`는 `30 passed, 2 skipped`였다.

### 2.1.1 테스트 완성도 재검토

현재 테스트 완성도는 “semantic/provenance/pack gating” 축에서는 중상, “runtime surface 전체” 축에서는 아직 중 수준이다.

이번 추가 구현으로 current source-of-truth는 아래까지 확장되었다.

- unit/integration baseline은 `295 passed, 32 skipped`로 상향되었다.
- official E2E baseline은 `30 passed, 2 skipped`로 상향되었다.
- 새 `multi-name-only-supported` official E2E가 추가되어, `Template Injection + Open Redirect` 두 free-form `vuln_ids`를 하나의 SID에서 compiler-first positive lane으로 함께 닫는 다중 취약 경로가 source-of-truth에 편입되었다.
- 새 `trusted-dynamic-sqli` official E2E가 추가되어, fixture-backed `llm_manifest` synthesis가 `generation_origin=llm_manifest`, `dynamicness_verdict=trusted dynamic`, `provider_health_state=llm_fixture`, `llm_fixture_used=true`로 실제 PACK artifact까지 닫히는 경로가 source-of-truth에 편입되었다.
- 추가로 `sqli-sidecar-template` official E2E가 추가되어, `built_in_template` + MySQL sidecar + `executor_feasibility_status=configured` 조합의 runtime-surface positive lane이 source-of-truth에 편입되었다.
- 추가로 `sqli-sidecar-compiler` official E2E가 추가되어, `compiler_generated` + MySQL sidecar + `executor_feasibility_status=configured` 조합의 compiler-first sidecar positive lane이 source-of-truth에 편입되었다.
- 추가로 `sqli-sidecar-compiler-custom-env` official E2E가 추가되어, custom alias/credential/db-name을 가진 MySQL sidecar SQLi도 `compiler_generated` + `service_env` contract 검증과 함께 source-of-truth에 편입되었다.
- 추가로 `foobar-name-only-negative` official E2E가 추가되어, single-token custom free-form name도 `NAME-*` canonicalization + `semantic_support_missing` fail-closed taxonomy와 함께 source-of-truth에 편입되었다.
- 추가로 `template-injection-paraphrase-name-only`, `open-redirect-paraphrase-name-only` official E2E가 추가되어, `Template rendering vulnerability`, `External redirect vulnerability` 같은 paraphrase 입력도 `name_resolution.source=alias`와 함께 compiler-first positive lane으로 닫히는 것이 source-of-truth에 편입되었다.
- 추가로 `vuln_ids` list 경로도 이제 catalog 미등록 free-form 이름을 synthetic `NAME-*`로 보존하고 `vuln_id_resolutions[]` trace를 남긴다. 즉 `Template Injection + Open Redirect` 같은 supported-positive multi-vuln lane뿐 아니라 `Custom Weird Vuln + Open Redirect` 같은 mixed free-form 입력도 더 이상 supported subset으로 조용히 collapse되지 않는다.
- 추가로 token fallback은 stopword를 제거한 exact-content-token match로 좁혀져, `unsafe template deserialization` 같은 ambiguous phrase가 `CWE-502`로 과잉 canonicalize되는 false positive가 regression test로 차단되었다. current truth에서 supported alias/reordered phrase는 계속 닫히되, mixed-semantic phrase는 synthetic `NAME-*`로 남는 쪽으로 보수화되었다.
- 추가로 `multi-name-mixed-partial` official E2E가 추가되어, unsupported/custom free-form bundle이 bundle 단위 preseeded semantic profile에 의해 `semantic_support_missing`으로 RESEARCH-stage fail-closed되더라도 supported compiler bundle은 same SID에서 partial-progress로 build/run/verify를 계속 수행하는 것이 source-of-truth에 편입되었다. latest rerun 기준 top-level `failure.stage=RESEARCH`, `generation_origin=mixed`, `dynamicness_verdict=mixed`, `verification_rule_source=mixed`, `verification_trust=mixed`, `partial_progress_summary.partial_success=true`가 함께 남는다.
- 추가로 `multi-name-only-supported` official E2E의 top-level manifest도 이제 bundle-level 공통 provenance/trust를 mirror해 `generation_origin=compiler_generated`, `dynamicness_verdict=compiler-first`, `verification_rule_source=compiler_runtime_rule`, `verification_trust=medium`까지 직접 surface한다.
- `Template Injection` repeatability gate는 이제 compiler-first lower bound와 정렬되어 remote provider/Tavily 없이도 `3/3 passed`로 검증된다.
- repeatability harness의 `pipeline_returncode` 전파 버그도 이번 턴에서 수정되어, gate 실패 원인이 실제 비결정성인지 harness 결함인지 더 명확히 분리할 수 있게 되었다.
- 추가로 `compiler.enabled=false` 또는 legacy `disable_compiler=true`가 있을 때 requirement normalization, researcher unknown classification, run_pipeline researcher skip이 더 이상 compiler lower bound를 계속 가정하지 않는 regression test가 source-of-truth에 편입되었다.
- 추가로 external DB requirement와 `policy.executor.sidecars` / 네트워크 정책 불일치는 `EXECUTOR_PRECHECK`와 executor direct path에서 fail-fast되는 regression test가 source-of-truth에 편입되었다.
- 추가로 free-form family mapping이 `common/assets/vuln-family-catalog.json` 기반 shared catalog로 이동해 requirement normalization, compiler routing, semantic support default가 같은 canonical family table을 보게 되었다.
- 추가로 `XML External Entity`는 current truth 기준 `NAME-XXE` + `pattern_id=xxe`로 canonicalize될 뿐 아니라 `semantic_profile -> xxe_xml_entity_resolve -> compiler_generated` path로 승격되었다. latest rerun에서는 `generation_origin=compiler_generated`, `dynamicness_verdict=compiler-first`, `verification_rule_source=compiler_runtime_rule`, `verification_trust=medium`, `generalization_class=real_free_form_positive`, `counts_as_generalization=true`, `total_duration_s≈6.636s`로 닫혔다.
- 추가로 SID는 이제 `generator_mode`와 runtime/executor surface digest까지 포함한다. 따라서 같은 vuln family라도 `template` vs `synthesis`, embedded vs sidecar runtime은 더 이상 같은 SID로 충돌하지 않는다.
- 추가로 sidecar-backed template/compiler lane은 이제 `service_env`를 contract/summary에서 explicit surface하고 executor가 이를 실제 `docker run -e ...`로 주입한다. 즉 MySQL lane success가 더 이상 fragment/template 기본 DB host 값에 우연히 맞아떨어지는 경로에 의존하지 않는다.

반면 아직 남은 테스트 공백도 분명하다.

- official E2E에는 이제 `sqli-sidecar-template` built-in MySQL sidecar positive lane과 `sqli-sidecar-compiler` compiler-first MySQL sidecar positive lane이 함께 있다. 다만 richer bridge/sidecar family 일반화는 아직 없다.
- official E2E에는 live remote-LLM 기반 `llm_manifest -> trusted dynamic` success lane이 없다. 현재는 fixture-backed trusted dynamic source-of-truth만 존재한다.
- performance는 현재 wall-clock budget regression보다 provenance/summary correctness를 더 강하게 본다.
- multi-vuln path는 이제 official positive lane과 mixed partial-progress lane이 함께 있다. 다만 mixed success/failure multi-vuln의 promotion/acceptance policy는 아직 충분히 고정되지 않았다.

### 2.2 현재 공식 E2E source-of-truth 범위

`tests/e2e/test_cases.py` 기준 현재 공식 E2E 케이스는 아래와 같다.

- `cwe-89-basic`
- `sqli-name-only`
- `sqli-sidecar-template`
- `sqli-sidecar-compiler`
- `sqli-sidecar-compiler-custom-env`
- `foobar-name-only-negative`
- `csrf-name-only`
- `ssrf-name-only`
- `command-injection-name-only`
- `code-injection-name-only`
- `code-injection-alias-name-only`
- `template-injection-name-only`
- `template-injection-alias-name-only`
- `template-injection-paraphrase-name-only`
- `template-injection-reordered-name-only`
- `path-traversal-name-only`
- `xss-name-only`
- `xxe-name-only`
- `deserialization-name-only`
- `open-redirect-name-only`
- `open-redirect-alias-name-only`
- `open-redirect-paraphrase-name-only`
- `open-redirect-reordered-name-only`
- `multi-name-only-supported`
- `multi-name-mixed-partial`
- `trusted-dynamic-sqli`
- `ldap-injection-negative`
- `unknown_cwe_synthesis_case`
- `unknown_cwe_live_tavily_case`
- `unknown_cwe_live_low_trust_fail_closed_case`

중요한 사실:

- Path Traversal dedicated official E2E는 이번 갱신에서 추가되었고, current workspace rerun 기준 `compiler-first` green이다.
- Command Injection dedicated official E2E도 이번 갱신에서 추가되었고, current workspace rerun 기준 `compiler-first` green이다.
- Code Injection dedicated official E2E도 이번 갱신에서 추가되었고, current workspace rerun 기준 `compiler-first` green이다.
- `Eval Injection` heuristic phrase도 `CWE-94`로 normalize되어 same compiler-first lane으로 닫힌다.
- unknown lane은 이제 negative synthesis case와 live Tavily case가 expectations 수준에서도 분리되어 존재한다.
- live unknown case는 explicit synthetic id `CWE-9999` 기반이지 real free-form `vuln_name only` case가 아니다.
- 이번 갱신으로 `Server Side Template Injection` 같은 known alias도 canonical `NAME-TEMPLATE-INJECTION`으로 normalize되어 official E2E positive lane에 편입되었다.
- 추가로 `Template rendering vulnerability`, `External redirect vulnerability` 같은 paraphrase도 shared vuln family catalog의 exact alias layer를 통해 canonical supported family로 normalize되어 official E2E positive lane에 편입되었다.
- 추가로 `Injection in Jinja template`, `Redirect open vulnerability` 같은 reordered/free-form phrase도 shared vuln family catalog의 token-match + fragment strategy fallback을 통해 canonical supported family로 normalize되어 official E2E positive lane에 편입되었다.
- 이번 구현으로 compiler-supported positive lane(SQLi/CSRF/SSRF/Command Injection/Code Injection/Template Injection/Path Traversal/XSS/Insecure Deserialization/Open Redirect/XXE)과 unsupported free-form negative lane(LDAP Injection)은 더 이상 Tavily availability를 전제하지 않는다.
- 새 `multi-name-only-supported` official E2E는 current workspace rerun 기준 `sid-fd38543fbbd2`, `bundle_count=2`, `positive_generalization_bundles=2`, `supported_bundles=2`, `total_duration_s≈8.773s`로 닫혔다. 즉 current source-of-truth에는 이제 “단일 free-form positive bundle”뿐 아니라 “단일 SID 안의 다중 free-form positive compiler-first bundle”도 포함된다.
- 새 `multi-name-mixed-partial` official E2E는 current workspace rerun 기준 same-SID mixed lane에서 `partial_progress_summary.partial_success=true`, `successful_bundles=1`, `research_blocked_bundles=1`을 남긴다. 즉 current source-of-truth에는 이제 “unsupported/custom free-form bundle은 fail-closed되지만 supported compiler bundle은 same SID에서 계속 실행하는” mixed partial-progress lane도 포함된다.
- fixture-backed `trusted-dynamic-sqli` official E2E는 current workspace rerun 기준 `sid-b36ff41a638a`, `generation_origin=llm_manifest`, `dynamicness_verdict=trusted dynamic`, `verification_rule_source=declared_rule`, `verification_trust=high`, `performance.provider_health_state=llm_fixture`, `performance.llm_fixture_used=true`, `total_duration_s≈8.665s`로 닫혔다. 다만 이것은 live remote provider evidence가 아니라 deterministic fixture-backed trusted-dynamic regression lane이다.
- 새 `sqli-sidecar-template` official E2E는 current workspace rerun 기준 `sid-fb69eab9a174`, `generation_origin=built_in_template`, `dynamicness_verdict=template-assisted`, `compiler_strategy=sqli_string_concat_mysql`, `verification_rule_source=declared_rule`, `verification_trust=high`, `executor_feasibility_status=configured`, `promotion.eligible=true`로 닫혔다. 이 lane은 now-explicit `service_env` contract를 executor가 주입해 닫히며, runtime-surface positive lane이지만 compiler-first가 아니라 template-assisted evidence다.
- 새 `sqli-sidecar-compiler` official E2E는 current workspace rerun 기준 `sid-e94b254bdff9`, `generation_origin=compiler_generated`, `dynamicness_verdict=compiler-first`, `compiler_strategy=sqli_string_concat_mysql`, `compiler_family=sql_injection`, `stack_scaffold_id=python/flask`, `fragment_id=mysql_login_query_concat_route`, `executor_feasibility_status=configured`, `verification_rule_source=declared_rule`, `verification_trust=high`, `promotion.eligible=true`로 닫혔다. 이 lane도 `service_env`를 requirement-aware contract에서 surface한 뒤 executor가 주입해 닫히므로, current source-of-truth에는 이제 compiler-first sidecar positive lane도 존재한다.
- current workspace rerun 기준 official E2E는 `30 passed, 2 skipped`로 green이고, skip 2개는 repeatability gate다.
- 이번 갱신으로 official E2E expectations도 `compiler_supported`/`compiler_strategy`만이 아니라 bundle-level `generation_origin`, `dynamicness_verdict`까지 직접 검증한다. 즉 current official acceptance는 “capability metadata상 compiler-covered”를 넘어서 “실제 run provenance가 compiler-generated/compiler-first인지”를 함께 본다.
- 추가로 representative official case(`cwe-89-basic`, `template-injection-name-only`, `open-redirect-name-only`)는 `compiler_family`, `stack_scaffold_id`, `stack_scaffold_version`, `fragment_id`, `compose_mode`까지 expectation에서 직접 검증한다. 즉 일부 핵심 lane은 “compiler-first”뿐 아니라 “registry-backed scaffold/fragment compose”도 source-of-truth에 포함된다.
- 추가로 paraphrase official case(`template-injection-paraphrase-name-only`, `open-redirect-paraphrase-name-only`)는 top-level `name_resolution.source=alias`, `name_resolution.resolved_vuln_id=*`까지 expectation으로 직접 고정한다. 즉 current official acceptance는 “이름만으로 성공했다”뿐 아니라 “어떤 canonical family catalog resolution을 거쳤는가”까지 기록한다.
- 이번 추가 갱신으로 static rule이 없는 compiler-generated family의 verifier provenance는 `compiler_runtime_rule/medium`으로 분리된다. 즉 current official acceptance는 compiler-first lane의 검증이 “declared independent static rule”인지 “compiler-derived runtime rule”인지도 artifact 수준에서 구분한다.
- Template Injection repeatability gate는 이번 턴부터 Tavily key를 요구하지 않는다. compiler-first/provider `not_probed` lower bound를 그대로 3회 반복 검증하는 gate로 재정렬되었다.
- 남은 공식 coverage hole은 이제 remote provider drift 자체보다 unknown/open-world compiler 부재, richer bridge/sidecar family 부재, 그리고 synthetic unknown lane 해석 쪽에 더 가깝다.

### 2.3 Provider 상태

이번 세션 current workspace에서 관찰한 provider 상태는 다음과 같다.

- Docker CLI 사용 가능
- Tavily API key 사용 가능
- OpenAI API key 감지됨
- 실제 OpenAI 호출은 `RateLimitError`로 quota exhausted 상태
- 따라서 current workspace의 live remote LLM health는 실질적으로 `llm_degraded`
- 다만 fixture-backed `trusted-dynamic-sqli` official lane은 remote quota와 별개로 `provider_health_state=llm_fixture`를 기록하며 trusted-dynamic contract surface를 고정 검증한다.
- 다만 이번 구현 이후 compiler-supported / static-supported family는 기본 minimal-input path에서 RESEARCH를 skip하므로, Tavily 상태는 더 이상 해당 lane의 operational lower bound를 좌우하지 않는다.
- latest rerun에서 remote-required로 남아 있는 대표 lane은 `CWE-9999` live unknown과 향후 compiler-unsupported/unknown family다.

즉 current workspace truth의 핵심 축은

- search provider 상태가 세션 중간에 바뀔 수 있으며, Tavily는 여전히 intermittent degraded일 수 있다
- live remote LLM은 degraded지만 fixture-backed trusted-dynamic lane은 `llm_fixture` provider state로 별도 검증할 수 있다
- 하지만 compiler-supported known/free-form lane은 이제 provider `not_probed` 상태에서도 compiler-first lower bound로 닫힌다

이라는 점이다.

### 2.4 Current workspace rerun 결과

#### 2.4.1 official live lane rerun

| lane | 결과 | provider_condition | generation_origin | dynamicness | evidence_class | observed_at | command | sid | 핵심 관찰 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SQLi `sqli-name-only` | pass | `not_probed` | `compiler_generated` | `compiler-first` | `current workspace rerun` | 2026-03-08 KST | `python tests/e2e/run_case.py --case tests/e2e/cases/sqli-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-stage2-reruns/sqli-name-only` | `sid-3325b4630aa4` | static-rule known family지만 generator가 seed `semantic_profile`를 만들고 `sqli_string_concat` compiler path를 선택한다. researcher/search probe를 건너뛴 compiler-only lane이면서, `metadata/sid-3325b4630aa4/generator_manifest.json` metadata에는 `stack_scaffold_id=python/flask`, `fragment_id=login_query_concat_route`, `compose_mode=registry`가 남는다. manifest는 `known_family_regression`, `promotion.eligible=true`다 |
| trusted dynamic SQLi `trusted-dynamic-sqli` | pass | `llm_fixture` | `llm_manifest` | `trusted dynamic` | `current workspace rerun` | 2026-03-09 KST | `python tests/e2e/run_case.py --case tests/e2e/cases/trusted-dynamic-sqli --mode deterministic --no-snapshot --output-dir /tmp/vuld-trusted-dynamic-sqli` | `sid-b36ff41a638a` | compiler를 명시적으로 끄고 fixture-backed generator manifest를 주입한 official lane이다. latest rerun 기준 `verification_rule_source=declared_rule`, `verification_trust=high`, `performance.provider_health_state=llm_fixture`, `performance.llm_fixture_used=true`, `promotion.eligible=true`, `generalization_class=known_family_regression`으로 닫혔다. trusted dynamic contract surface는 확보됐지만, 이것을 live remote LLM evidence와 동일시하면 안 된다 |
| CSRF `csrf-name-only` | pass | `not_probed` | `compiler_generated` | `compiler-first` | `current workspace rerun` | 2026-03-08 KST | `python tests/e2e/run_case.py --case tests/e2e/cases/csrf-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-stage2-reruns/csrf-name-only` | `sid-d914426746e5` | static-rule known family지만 generator가 seed `semantic_profile`를 만들고 `csrf_missing_token` compiler path를 선택한다. researcher/search probe를 건너뛴 compiler-only lane이면서, `metadata/sid-d914426746e5/generator_manifest.json` metadata에는 `stack_scaffold_id=python/flask`, `fragment_id=csrf_state_change_route`, `compose_mode=registry`가 남는다. manifest는 `known_family_regression`, `promotion.eligible=true`다 |
| Command Injection `command-injection-name-only` | pass | `not_probed` | `compiler_generated` | `compiler-first` | `current workspace rerun` | 2026-03-08 KST | `python tests/e2e/run_case.py --case tests/e2e/cases/command-injection-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-cmdi-review` | `sid-9310c416fc6d` | `semantic_profile.support_level=builtin_supported`와 `compiler_strategy=command_injection_shell`를 바탕으로 generator가 compiler path를 선택한다. latest rerun 기준 `verify_pass=true`, `promotion.eligible=true`, `semantic_supported=true`, `provider_health_state=not_probed`, `total_duration_s≈7.026s`였다 |
| Code Injection `code-injection-name-only` | pass | `not_probed` | `compiler_generated` | `compiler-first` | `current workspace rerun` | 2026-03-08 KST | `python tests/e2e/run_case.py --case tests/e2e/cases/code-injection-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-review-code-injection` | `sid-31aac9a4f61c` | `semantic_profile.support_level=builtin_supported`와 `compiler_strategy=code_injection_eval`를 바탕으로 generator가 compiler path를 선택한다. latest rerun 기준 `verify_pass=true`, `promotion.eligible=true`, `semantic_supported=true`, `provider_health_state=not_probed`, `total_duration_s≈6.675s`였고, `generator_manifest.json` metadata에는 `stack_scaffold_id=python/flask`, `fragment_id=eval_code_exec_route`, `compose_mode=registry`가 남는다 |
| Template Injection `template-injection-name-only` | pass | `not_probed` | `compiler_generated` | `compiler-first` | `current workspace rerun` | 2026-03-08 KST | `python tests/e2e/run_case.py --case tests/e2e/cases/template-injection-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-postfix/template-injection` | `sid-60ae4e071b9f` | `semantic_profile.support_level=compiler_supported`와 `compiler_strategy=template_injection_render`를 바탕으로 generator가 compiler path를 선택한다. 이번 갱신으로 compiler PoC도 explicit `flag_token`을 출력해 verifier fallback evidence가 `success_signature + flag_token + semantic check`까지 포함한다. latest rerun에서는 RESEARCH가 `0.0s skipped`로 기록된다 |
| Template Injection alias `template-injection-alias-name-only` | pass | `not_probed` | `compiler_generated` | `compiler-first` | `current workspace rerun` | 2026-03-08 KST | `python tests/e2e/run_case.py --case tests/e2e/cases/template-injection-alias-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-review/template-alias` | `sid-60ae4e071b9f` | `Server Side Template Injection`이 requirement normalization 단계에서 canonical `NAME-TEMPLATE-INJECTION`으로 collapse되므로 original case와 같은 SID를 재사용한다. 즉 이번 갱신은 exact phrase가 아니라 supported alias layer까지 free-form positive lane을 넓혔다 |
| Path Traversal `path-traversal-name-only` | pass | `not_probed` | `compiler_generated` | `compiler-first` | `current workspace rerun` | 2026-03-08 KST | `python tests/e2e/run_case.py --case tests/e2e/cases/path-traversal-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-postfix/path-traversal` | `sid-319953f83d00` | `semantic_profile.support_level=builtin_supported`와 `compiler_strategy=path_traversal_file_read`를 바탕으로 generator가 compiler path를 선택한다. read-only executor 제약을 만족하는 compiler bundle이며 latest rerun에서는 `researcher skipped: compiler/static supported path`가 `performance_summary`에 남는다 |
| XSS `xss-name-only` | pass | `not_probed` | `compiler_generated` | `compiler-first` | `current workspace rerun` | 2026-03-08 KST | `python tests/e2e/run_case.py --case tests/e2e/cases/xss-name-only --mode deterministic --no-snapshot --output-dir /tmp/pytest-of-ysw/pytest-233/test_xss_name_only_case0` | `sid-9ec37e553560` | `semantic_profile.support_level=builtin_supported`와 `compiler_strategy=xss_reflected`를 바탕으로 generator가 compiler path를 선택한다. built-in semantic evaluator가 XSS도 직접 판정하며 latest rerun에서는 provider `not_probed`, `compiler-first`, `promotion.eligible=true`로 닫힌다 |
| SSRF `ssrf-name-only` | pass | `not_probed` | `compiler_generated` | `compiler-first` | `current workspace rerun` | 2026-03-08 KST | `python tests/e2e/run_case.py --case tests/e2e/cases/ssrf-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-stage2-reruns/ssrf-name-only` | `sid-236f65069375` | static-rule known family지만 generator가 seed `semantic_profile`를 만들고 `ssrf_loopback_fetch` compiler path를 선택한다. researcher/search probe를 건너뛴 compiler-only lane이며, `metadata/sid-236f65069375/generator_manifest.json` metadata에는 `stack_scaffold_id=python/flask`, `fragment_id=loopback_fetch_route`, `compose_mode=registry`가 남는다. bundle provenance는 `compiler_generated`, dynamicness는 `compiler-first`, `promotion.eligible=true`다 |
| Insecure Deserialization `deserialization-name-only` | pass | `not_probed` | `compiler_generated` | `compiler-first` | `current workspace rerun` | 2026-03-08 KST | `python tests/e2e/run_case.py --case tests/e2e/cases/deserialization-name-only --mode deterministic --no-snapshot --output-dir /tmp/pytest-of-ysw/pytest-233/test_deserialization_name_only0` | `sid-0f4fee19236d` | `semantic_profile.compiler_strategy=deserialization_pickle_body`로 compiler path를 타며 `verify_pass=true`, `promotion.eligible=true`, `compiler-first`까지 닫혔다. latest rerun에서는 RESEARCH가 skip되고 built-in semantic evaluator가 `generator_manifest` 기반으로 정렬된다 |
| Open Redirect `open-redirect-name-only` | pass | `not_probed` | `compiler_generated` | `compiler-first` | `current workspace rerun` | 2026-03-08 KST | `python tests/e2e/run_case.py --case tests/e2e/cases/open-redirect-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-review/open-redirect-postfix2` | `sid-d94f0a58336c` | `semantic_profile.support_level=compiler_supported`를 바탕으로 generator가 `open_redirect_reflect` compiler path를 선택한다. 이번 갱신으로 compiler PoC가 `FLAG{OPEN_REDIRECT_OK}`를 explicit 출력해 verifier fallback evidence도 강화되었고, free-form positive `NAME-*` lane은 여전히 `compiler-first`, `promotion.eligible=true`, `counts_as_generalization=true`로 닫힌다 |
| Open Redirect alias `open-redirect-alias-name-only` | pass | `not_probed` | `compiler_generated` | `compiler-first` | `current workspace rerun` | 2026-03-08 KST | `python tests/e2e/run_case.py --case tests/e2e/cases/open-redirect-alias-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-review/open-redirect-alias-official` | `sid-d94f0a58336c` | `Unvalidated Redirect`도 requirement normalization 단계에서 canonical `NAME-OPEN-REDIRECT`로 collapse되므로 original Open Redirect case와 같은 SID를 재사용한다. 즉 free-form positive lane이 exact phrase뿐 아니라 supported redirect alias까지 확장되었다 |

#### 2.4.2 synthetic regression / negative regression validation

| lane | 결과 | provider_condition | generation_origin | dynamicness | evidence_class | observed_at | command | sid | 핵심 관찰 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| synthetic unknown live `cwe-unknown-basic` | pass | `llm_degraded` | `deterministic_fallback` | `deterministic fallback dependent` | `current workspace rerun` | 2026-03-08 KST | `python tests/e2e/run_case.py --case tests/e2e/cases/cwe-unknown-basic --mode deterministic --no-snapshot --output-dir /tmp/vuld-gap-unknown-live6` | `sid-d2ff12df4e6d` | `verify_pass=true`와 `run_passed=true`는 닫히지만 `promotion.eligible=false`이며 manifest에 `generalization_class=synthetic_regression`, `counts_as_generalization=false`가 남는다. latest rerun에서는 verifier가 `verification_rule_source=runtime_rule_candidate`, `verification_trust=low`를 surface하고 promotion reason `verify_contract:runtime_rule_candidate`, reviewer issue `Verifier contract trust is low (runtime_rule_candidate)`, manifest `verification_summary.by_trust.low=1`까지 함께 남는다. 즉 explicit synthetic id + inherited SQLi-like pattern 기반 regression lane이며, current success는 low-trust verification success다 |
| synthetic unknown live strict `cwe-unknown-low-trust-fail-closed` | fail-closed | `llm_degraded` | `deterministic_fallback` | `deterministic fallback dependent` | `current workspace rerun` | 2026-03-08 KST | `python tests/e2e/run_case.py --case tests/e2e/cases/cwe-unknown-low-trust-fail-closed --mode deterministic --no-snapshot --output-dir /tmp/vuld-gap-unknown-live-fail-closed` | `sid-d2ff12df4e6d` | `policy.verifier.low_trust_unknown_policy=fail_closed`를 주면 같은 unknown live lane도 `verify_pass=false`, `run_passed=true`, `terminal_failure_class=low_trust_verification`, `retry_count=0`으로 종료한다. verifier는 `verification_policy_blocked=true`와 evidence `low-trust verifier contract blocked by policy ...`를 남기고, registry는 이 결과를 다시 LLM fallback으로 덮어쓰지 않는다 |
| real free-form `vuln_name: LDAP Injection` | fail-closed | `not_probed` | `research_short_circuit` | `pre-generation fail-closed` | `current workspace rerun` | 2026-03-08 KST | `python tests/e2e/run_case.py --case tests/e2e/cases/ldap-injection-negative --mode deterministic --no-snapshot --output-dir /tmp/vuld-postfix/ldap-negative` | `sid-2a995570da6f` | 이번 갱신으로 preseeded `semantic_profile`가 unsupported free-form `NAME-*`를 RESEARCH 실행 전에 차단한다. latest rerun에서는 `failure_manifest.json`, `terminal_failure_class=semantic_support_missing`, `retry_count=0`, `total_duration_s≈0.052s`까지 내려갔다 |
| synthetic unknown no-remote `cwe-unknown-basic` | fail-closed | `remote_provider_unavailable` | `research_short_circuit` | `pre-generation fail-closed` | `current workspace rerun` | 2026-03-08 KST | `VUL_WEB_SEARCH_PROVIDER=none python tests/e2e/run_case.py --case tests/e2e/cases/cwe-unknown-basic --expectations tests/e2e/cases/cwe-unknown-basic/expectations.no-remote.json --mode deterministic --no-snapshot --output-dir /tmp/vuld-gap-unknown-none-final` | `sid-d2ff12df4e6d` | no-remote negative regression은 `terminal_failure_class=remote_provider_unavailable`, `provider_health_state=remote_provider_unavailable`, `retry_count=0`, `generation_origin=research_short_circuit`, `dynamicness=pre-generation fail-closed`까지 surface된다. additional rerun 기준 `resolved_contract.semantic_contract.status=empty`와 `semantic_profile.derived_assertions.semantic_status=empty`도 확인되어, insufficient heuristic semantics가 더 이상 `aligned`로 남지 않는다 |

추가 current workspace rerun:

- single-token custom free-form `vuln_name: Foobar`도 이번 보완 이후 canonical `NAME-FOOBAR`로 보존된다.
- representative rerun(`VUL_WEB_SEARCH_PROVIDER=none python orchestrator/run_pipeline.py --sid <Foobar-SID> --mode deterministic`)에서는 `pipeline_result=failure`, `failure.stage=RESEARCH`, `terminal_failure_class=semantic_support_missing`, `provider_health_state=not_probed`, `compiler_supported=false`, `compiler_reason=semantic family unsupported for compiler-backed generation`이 함께 남았다.
- 즉 unsupported/custom name-only negative lane이 whitespace가 있는 자연어 phrase뿐 아니라 bare single-token label에도 동일하게 적용된다.

#### 2.4.3 post-fix 성능 snapshot

이번 세션 compiler-supported researcher decoupling 이후 direct rerun 기준 `performance_summary.total_duration_s`는 다음과 같았다.

- SQLi official: `7.174s`
- trusted-dynamic SQLi official: `8.665s`
- CSRF official: `6.844s`
- Command Injection official: `7.026s`
- Code Injection official: `6.675s`
- Template Injection official: `7.118s`
- Template Injection rerun after fallback assetization sweep: `6.630s`
- Template Injection alias canonicalized rerun: `7.341s`
- Path Traversal official: `6.907s`
- XSS official: `6.987s`
- synthetic unknown live: `19.443s`
- SSRF official: `6.772s`
- SSRF rerun after fallback assetization sweep: `6.713s`
- Insecure Deserialization official: `6.721s`
- Open Redirect free-form positive: `7.403s`
- Open Redirect free-form positive rerun after fallback assetization: `6.545s`
- Open Redirect alias canonicalized rerun: `12.220s`
- LDAP Injection negative: `0.052s`
- synthetic unknown live strict fail-closed: `14.267s`

추가 관찰:

- latest alias-positive rerun(`Server Side Template Injection`)도 약 `7.34s`로 기존 compiler-first lower bound와 같은 범위에 머물렀다.
- latest Open Redirect cold rerun은 약 `12.661s`였고, 이는 compiler path 자체 변화보다 Docker build/run cache 상태 차이의 영향이 더 컸다.

해석:

- SQLi, CSRF, SSRF는 여전히 compiler-only lane이며 latest rerun 기준 researcher/search probe 없이 각각 약 7초, 7초, 7초 수준으로 닫힌다.
- fixture-backed trusted-dynamic SQLi lane은 compiler-first lower bound보다 약간 느리지만 같은 10초 미만 대역에서 닫힌다. 다만 이 수치는 remote LLM latency가 아니라 local fixture + Docker orchestration 비용에 가깝다.
- Template Injection, Open Redirect, XXE, Path Traversal, XSS, Insecure Deserialization도 이번 decoupling 이후 모두 provider `not_probed` 상태에서 대체로 약 6~7초 안팎으로 수렴했다. 즉 previous remote-required drift가 current lower bound를 더 이상 지배하지 않는다.
- synthetic unknown live lane은 여전히 `deterministic fallback dependent`다. latest rerun에서는 약 16초였고, current manifest 기준 `promotion.eligible=false`, `generalization_class=synthetic_regression`으로 집계된다.
- unsupported free-form negative lane은 preseeded `semantic_profile` 덕분에 RESEARCH 실행 전 terminal stop으로 더 내려갔다. latest rerun 기준 LDAP Injection은 `retry_count=0`, 약 `0.052s` 수준이며 `failure_manifest.failure.terminal_failure_class=semantic_support_missing`, bundle provenance `research_short_circuit`, `generalization_class=unsupported_free_form_negative`가 함께 surface된다.
- synthetic unknown no-remote negative lane도 이번 갱신으로 3-loop 재시도 대신 single-shot terminal failure로 내려갔다. representative rerun 기준 `CWE-9999` no-remote는 `retry_count=0`, 약 `1.650s`, `terminal_failure_class=remote_provider_unavailable`, `provider_health_state=remote_provider_unavailable`, `generation_origin=research_short_circuit`까지 surface된다.

#### 2.4.4 post-compiler-decoupling targeted rerun

compiler/static supported bundle을 remote-required researcher에서 분리한 뒤, representative lane을 다시 확인했다.

- command root: `/tmp/vuld-postfix/*`
- unit/integration precheck: `python -m pytest -q tests` -> `295 passed, 32 skipped`
- official E2E full rerun: `VULD_RUN_E2E=1 python -m pytest -q tests/e2e/test_cases.py -rs` -> `30 passed, 2 skipped`
- Path Traversal / Template Injection: latest targeted rerun에서 둘 다 `compiler-first`, provider `not_probed`, RESEARCH `0.0s skipped`, 약 `7s` 수준으로 닫혔다
- Template Injection alias(`Server Side Template Injection`)도 latest targeted rerun에서 `compiler-first`, provider `not_probed`, RESEARCH `0.0s skipped`, `real_free_form_positive`로 닫혔다
- Open Redirect alias(`Unvalidated Redirect`)도 latest targeted rerun에서 `compiler-first`, provider `not_probed`, `real_free_form_positive`로 닫혔다
- Template Injection paraphrase(`Template rendering vulnerability`)와 Open Redirect paraphrase(`External redirect vulnerability`)도 latest official rerun에서 각각 `name_resolution.source=alias`, `compiler-first`, `real_free_form_positive`로 닫혔다
- multi-name-only-supported official rerun은 current workspace에서 `sid-fd38543fbbd2`, `bundle_count=2`, `generation_summary.by_origin.compiler_generated=2`, `generalization_summary.positive_generalization_bundles=2`, `compiler_contract_summary.supported_bundles=2`, `verification_summary.by_trust.medium=2`, `total_duration_s≈8.773s`로 닫혔다
- trusted-dynamic-sqli official rerun은 current workspace에서 `sid-b36ff41a638a`, `generation_origin=llm_manifest`, `dynamicness_verdict=trusted dynamic`, `verification_rule_source=declared_rule`, `verification_trust=high`, `provider_health_state=llm_fixture`, `llm_fixture_used=true`, `total_duration_s≈8.665s`로 닫혔다
- sqli-sidecar-template official rerun은 current workspace에서 `sid-fb69eab9a174`, `generation_origin=built_in_template`, `dynamicness_verdict=template-assisted`, `compiler_strategy=sqli_string_concat_mysql`, `verification_rule_source=declared_rule`, `verification_trust=high`, `executor_feasibility_status=configured`로 닫혔다
- sqli-sidecar-compiler official rerun은 current workspace에서 `sid-e94b254bdff9`, `generation_origin=compiler_generated`, `dynamicness_verdict=compiler-first`, `compiler_strategy=sqli_string_concat_mysql`, `compiler_family=sql_injection`, `stack_scaffold_id=python/flask`, `fragment_id=mysql_login_query_concat_route`, `executor_feasibility_status=configured`, `verification_rule_source=declared_rule`, `verification_trust=high`로 닫혔다
- sqli-sidecar-compiler-custom-env official rerun은 current workspace에서 custom alias/credential/db-name이 들어간 MySQL sidecar requirement를 `generation_origin=compiler_generated`, `dynamicness_verdict=compiler-first`, `compiler_strategy=sqli_string_concat_mysql`, `executor_feasibility_status=configured`, top-level/bundle `service_env` mirror까지 포함해 닫혔다
- latest sidecar template/compiler rerun에서는 service code의 DB host/user/password/name 기본값을 intentionally invalid placeholder로 둔 상태에서도 success가 재현되었다. 즉 current truth의 sidecar 성공은 hardcoded default가 아니라 executor가 injected `service_env`를 실제로 전달한 결과다.
- 추가로 ad-hoc custom sidecar rerun(`alias=db-internal`, `MYSQL_USER=custom_user`, `MYSQL_PASSWORD=custom_pw`, `MYSQL_DATABASE=runtime_db_custom`)도 current workspace에서 `pipeline_result=success`, `generation_origin=compiler_generated`, `dynamicness_verdict=compiler-first`, `executor_feasibility_status=configured`, `promotion.eligible=true`로 닫혔다.
- same custom rerun에서는 final `manifest.json` top-level에도 `service_env={APP_PORT, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME}`가 직접 mirror되었고 값은 `db-internal/custom_user/custom_pw/runtime_db_custom`으로 surface되었다. 즉 runtime contract 관측성도 intermediate contract에만 머물지 않고 final manifest까지 올라온다.
- LDAP Injection negative: latest targeted rerun에서 `failure_manifest.json`, `pre-generation fail-closed`, 약 `0.052s`
- `CWE-9999` no-remote negative: `VUL_WEB_SEARCH_PROVIDER=none` + dedicated negative expectations로 fail-closed validation이 별도 고정되었고, representative rerun 기준 `remote_provider_unavailable`, `provider_health_state=remote_provider_unavailable`, `retry_count=0`, `~1.650s`
- `CWE-9999` live Tavily: 여전히 `synthetic_regression` + `deterministic fallback dependent` success lane이지만, latest rerun에서는 `verification_rule_source=runtime_rule_candidate`, `verification_trust=low`, promotion reason `verify_contract:runtime_rule_candidate`가 함께 surface된다
- `CWE-9999` live strict fail-closed: 같은 lane에 `policy.verifier.low_trust_unknown_policy=fail_closed`를 주면 latest rerun에서 `run_passed=true`, `verification_policy_blocked=true`, `terminal_failure_class=low_trust_verification`, `retry_count=0`으로 종료한다
- `VULD_RUN_E2E=1 VULD_RUN_E2E_REPEAT=1 python -m pytest -q tests/e2e/test_cases.py -k template_injection_name_only_repeatability_gate -rs`도 current workspace에서 `1 passed`였다. 즉 repeatability source-of-truth가 provider-independent compiler-first lane과 다시 정렬되었다
- direct sanity script latest rerun에서는 `vuln_name: Template Injection + compiler.enabled=false`가 `researcher.search_policy=remote_required`, `policy.require_researcher_evidence=true`, `_can_skip_researcher=false`로 정렬되었다. 즉 compiler-disabled request가 더 이상 non-remote lower bound처럼 과대표현되지 않는다
- same sanity script latest rerun에서는 external DB requirement(`runtime.db=mysql`) + empty sidecars / disabled network 조합이 `terminal_failure_class=executor_dependency_misconfigured` precheck로 표면화되었다. 즉 Docker build/run까지 내려가 늦게 실패하던 mismatch가 더 이른 단계에서 차단된다

### 2.5 Current truth 요약

현재 workspace truth를 한 문장으로 요약하면 다음과 같다.

현재 레포는 known lane(SQLi/CSRF/Command Injection/Code Injection/SSRF/Path Traversal/XSS/Insecure Deserialization), fixture-backed trusted dynamic SQLi, template-assisted/ compiler-first MySQL sidecar SQLi, 그리고 synthetic unknown live를 닫을 수 있고,
real free-form `vuln_name: Template Injection`, `vuln_name: Open Redirect`, `vuln_name: XML External Entity`뿐 아니라 supported alias `Server Side Template Injection`, `Unvalidated Redirect`도 name-only 입력만으로 remote search 없이 positive lane을 닫을 수 있다.
반면 compiler-first 경로는 SQLi, CSRF, Command Injection, Code Injection, Template Injection, Path Traversal, XSS, SSRF, Insecure Deserialization, Open Redirect, XXE 열한 family에 한정되어 있고,
unsupported free-form `NAME-*` lane은 LDAP Injection뿐 아니라 single-token custom name(`Foobar -> NAME-FOOBAR`)도 포함해 preseeded semantic profile로 거의 즉시 fail-closed된다.
추가로 current manifest와 E2E summary는 `generalization_summary` / `generalization_class` / `counts_as_generalization`뿐 아니라 `verification_rule_source` / `verification_trust`도 surface해 known-family regression, real free-form positive, synthetic regression, unsupported free-form negative를 더 명확히 구분한다. manifest top-level에도 `verification_summary`가 추가되어 `by_rule_source`, `by_trust`, `low_trust_bundles`를 집계한다. 이번 갱신으로 compiler-supported known/free-form family는 더 이상 default minimal-input path에서 Tavily availability에 묶이지 않고, supported free-form alias도 canonical `NAME-*` family로 정규화할 수 있게 되었다. 또한 static rule이 없는 compiler-generated family의 verifier provenance는 이제 `compiler_runtime_rule/medium`으로 분리되어, compiler-coupled verification이 `declared_rule/high`처럼 과대표현되지 않는다. fixture-backed trusted-dynamic official lane은 `llm_manifest` provenance와 `llm_fixture_used=true`를 실제 success artifact에서 증명하지만, 이것이 live remote LLM health를 증명하는 것은 아니다. compiler-supported free-form family의 `semantic_profile`과 `resolved_contract.semantic_contract`는 researcher를 skip하더라도 shared fragment registry 또는 baseline에서 canonical `semantic_signature`를 backfill해, contract/profile artifact가 더 이상 empty placeholder로만 남지 않는다. 추가로 compiler lower bound를 requirement가 명시적으로 끄면 planner/researcher/runner가 그 lane을 다시 remote-required/skip-disabled로 재분류하므로, “family lower bound”와 “effective requirement lower bound”의 drift도 줄었다. external DB requirement와 empty sidecar/network-none 조합은 이제 EXECUTOR 이전 precheck에서 차단되며, direct executor 호출도 같은 mismatch를 즉시 에러로 표면화한다. insufficient researcher evidence가 있는 unknown lane은 contract 단계에서 `semantic_contract.status=empty`로 정규화되며, synthetic unknown live lane은 verifier success가 나오더라도 `runtime_rule_candidate/low` trust와 reviewer low-trust issue가 함께 남아 promotion에서 차단된다. 이제 같은 lane에 `policy.verifier.low_trust_unknown_policy=fail_closed`를 주면 verifier가 `verification_policy_blocked=true`를 남기고 VERIFY stage terminal failure(`low_trust_verification`)로 종료한다. PACK 이후 manifest를 한 번 더 갱신해 `manifest.performance`와 `performance_summary.json` 사이 stale drift도 제거되었고, single-bundle manifest는 `llm_fixture_used` 같은 provenance boolean도 직접 mirror한다. 추가로 transient remote LLM error는 이제 해당 call만 stub으로 낮추고 프로세스 전체를 영구 stub mode로 고정하지 않는다.
따라서 현 시점 최상위 남은 과제는 “unknown/open-world compiler 부재”, “synthetic unknown lane에서 `warn`을 default로 둘지 `fail_closed`를 official acceptance로 끌어올릴지의 policy 고정”, “compiler-derived runtime rule 이후에도 남는 verifier 독립성 상한”, “fixture-backed trusted dynamic을 live remote evidence와 분리해 읽는 acceptance 정착”, “SQLi 외 richer bridge/sidecar family의 compiler-first source-of-truth 부재”, 그리고 “shared fragment registry의 외부 자산화와 template debt의 구조적 전환”까지 포함한다.

## 3. 현재 구현의 실제 생성 방식과 의존 구조

### 3.1 생성 경로 분해

현재 생성 경로는 단일하지 않다.
실제로는 아래 여섯 경로가 공존한다.

1. `llm_manifest`
   - LLM manifest가 artifact 중심 provenance인 경우
2. `compiler_generated`
   - stack scaffold + vuln fragment compiler가 생성한 경우
3. `built_in_template`
   - `workspaces/templates/**` 기반 정적 template materialization
4. `runtime_template_clone`
   - researcher가 static template를 runtime template로 clone한 경우
5. `family-aware deterministic fallback`
   - 특정 family를 위한 deterministic service/PoC skeleton
6. `generic unsupported fallback`
   - family-specific semantics가 없는 generic reflection fallback

current live truth 기준 공식 positive lane에서 자주 관측되는 것은 이제 2다.
반면 synthetic unknown lane은 5, unsupported free-form negative lane은 pre-generation short-circuit와 함께 6의 fail-closed taxonomy를 surface한다.

### 3.2 built-in template inventory

current repo inspection 기준 built-in template inventory는 아래가 전부다.

| family | template |
| --- | --- |
| SQLi | `workspaces/templates/sqli/flask_sqlite_raw` |
| SQLi | `workspaces/templates/sqli/flask_mysql_union` |
| CSRF | `workspaces/templates/csrf/flask_sqlite_csrf` |

즉 built-in template dependence는 실제로 SQLi/CSRF 중심이다.
Path Traversal, SSRF, XSS, Insecure Deserialization, Open Redirect에는 built-in template가 없다.

### 3.3 runtime candidate template의 한계

researcher의 runtime candidate template 생성은 current code 기준 matching `cwe-*` static template clone이다.
즉 다음 성격을 가진다.

- 새 synthesis가 아니다.
- static template를 runtime metadata 아래로 복사한 것이다.
- `NAME-*` free-form lane의 일반화를 해결하지 못한다.
- `cwe-*` tag가 없는 family에는 적용되지 않는다.

따라서 runtime candidate template는 template reuse path로만 집계해야 한다.

### 3.4 family-aware deterministic fallback coverage

current code 기준 family-aware deterministic fallback이 명시적으로 구현된 family는 아래다.

- SQLi
- CSRF
- SSRF
- Template Injection
- Path Traversal
- XSS
- Insecure Deserialization
- Open Redirect

반면 아래는 dedicated deterministic fallback이 없다.

- LDAP Injection
- 기타 real free-form `NAME-*`

### 3.5 official lane 분류

| lane | 입력 class | primary generation path | template dependence | family hardcoding | current verdict |
| --- | --- | --- | --- | --- | --- |
| SQLi | known-name -> `CWE-89` | `semantic_profile -> sqli_string_concat -> compiler_generated` | 없음 | 중간 | current workspace rerun에서 `compiler-first`, `compiler_supported=true`, `promotion.eligible=true`까지 닫힌다 |
| CSRF | known-name -> `CWE-352` | `semantic_profile -> csrf_missing_token -> compiler_generated` | 없음 | 중간 | current workspace rerun에서 `compiler-first`, `compiler_supported=true`, `promotion.eligible=true`까지 닫힌다 |
| Command Injection | known-name -> `CWE-78` | `semantic_profile -> command_injection_shell -> compiler_generated` | 없음 | 중간 | current workspace rerun에서 `compiler-first`, `compiler_supported=true`, `promotion.eligible=true`까지 닫힌다 |
| Code Injection | known-name -> `CWE-94` | `semantic_profile -> code_injection_eval -> compiler_generated` | 없음 | 중간 | current workspace rerun에서 `compiler-first`, `compiler_supported=true`, `promotion.eligible=true`까지 닫힌다 |
| Path Traversal | known-name -> `CWE-22` | `semantic_profile -> path_traversal_file_read -> compiler_generated` | 없음 | 중간 | current workspace rerun에서 `compiler-first`, `compiler_supported=true`, `promotion.eligible=true`까지 닫힌다 |
| SSRF | known-name -> `CWE-918` | `semantic_profile -> ssrf_loopback_fetch -> compiler_generated` | 없음 | 중간 | current workspace rerun에서 `compiler-first`, `compiler_supported=true`, `promotion.eligible=true`까지 닫힌다 |
| Template Injection | free-form name -> `NAME-*` | `semantic_profile -> template_injection_render -> compiler_generated` | 없음 | 중간 | current workspace rerun에서 `compiler-first`, `compiler_supported=true`, `promotion.eligible=true`까지 닫힌다 |
| XSS | known-name -> `CWE-79` | `semantic_profile -> xss_reflected -> compiler_generated` | 없음 | 중간 | current workspace rerun에서 `compiler-first`, `compiler_supported=true`, `promotion.eligible=true`까지 닫힌다 |
| Insecure Deserialization | known-name -> `CWE-502` | `semantic_profile -> deserialization_pickle_body -> compiler_generated` | 없음 | 중간 | current workspace rerun에서 `compiler-first`, `compiler_supported=true`, `promotion.eligible=true`까지 닫힌다 |
| SQLi sidecar template | known-name -> `CWE-89` + explicit template/runtime-db request | `built_in_template(flask_mysql_union)` + MySQL sidecar | 높음 | 낮음 | current workspace rerun에서 `template-assisted`, `executor_feasibility_status=configured`, `verification_trust=high`, `promotion.eligible=true`까지 닫힌다. 현재는 `service_env` contract를 executor가 주입해 닫히므로 runtime surface completeness evidence로는 유효하지만 compiler-first/generalization evidence는 아니다 |
| SQLi sidecar compiler | known-name -> `CWE-89` + explicit sidecar/runtime-db request | `semantic_profile -> sqli_string_concat_mysql -> compiler_generated` + MySQL sidecar | 없음 | 중간 | current workspace rerun에서 `compiler-first`, `executor_feasibility_status=configured`, `verification_trust=high`, `promotion.eligible=true`까지 닫힌다. `service_env`가 contract/manifest에 explicit surface되고 executor가 이를 주입하므로, current source-of-truth에 편입된 compiler-first sidecar positive lane이다 |
| synthetic unknown live | explicit `CWE-9999` | researcher/runtime rule candidate + inherited SQLi-like semantics + deterministic fallback | 없음 | 높음 | regression lane이지 generalization lane이 아니며, latest rerun에서는 `verification_trust=low`가 명시된다 |
| Open Redirect | free-form name -> `NAME-OPEN-REDIRECT` | `semantic_profile -> open_redirect_reflect -> compiler_generated` | 없음 | 중간 | current workspace rerun에서 `compiler-first`, `compiler_supported=true`, `promotion.eligible=true`까지 닫힌다 |
| XXE | free-form name -> `NAME-XXE` | `semantic_profile -> xxe_xml_entity_resolve -> compiler_generated` | 없음 | 중간 | current workspace rerun에서 `compiler-first`, `compiler_supported=true`, `promotion.eligible=true`까지 닫힌다 |
| real free-form unsupported | `vuln_name -> NAME-*` | generic unsupported fallback | 없음 | 낮음 | LDAP Injection 같은 lane은 현재 fail-closed negative regression으로 정렬됨 |

### 3.6 free-form `vuln_name only` lane의 실제 resolution chain

현재 free-form lane은 대부분 여전히 “이름 -> 의미 -> 코드” compiler path로 닫히지 않지만, overall compiler-covered family는 SQLi, CSRF, Command Injection, Code Injection, Template Injection, Path Traversal, XSS, SSRF, Insecure Deserialization, Open Redirect, XXE까지 넓어졌다. real free-form positive lane에서 이 경로가 실제로 닫힌 family도 Template Injection, Open Redirect, XXE 셋으로 늘었고, 이번 갱신으로 이 세 lane은 default minimal-input path에서 researcher/remote provider 없이도 닫힌다.
실제 current code 기준 resolution chain은 아래와 같다.

1. requirement normalization
   - `vuln_name`은 alias/heuristic에 걸리면 known `CWE-*`로 매핑되고, 아니면 `NAME-*`로 정규화된다.
   - 이때 whitespace가 있는 자연어 phrase뿐 아니라 bare single-token custom label도 `NAME-*`로 보존된다. 즉 `Foobar` 같은 입력이 bare identifier로 새지 않고 unsupported free-form lane으로 분류된다.
   - 동시에 `pattern_id`, `language`, `framework`, `generator_mode`, 기본 runtime profile이 자동 주입된다.
2. researcher normalization
   - evidence relevance, `semantic_signature`, `verification_spec`, `guard_spec`, `runtime_rule`, runtime template candidate를 만들 수 있다.
   - 즉 “semantic을 구조화하는 층”은 이미 존재한다.
   - 다만 현재는 compiler/static supported bundle이면 default path에서 RESEARCH를 skip할 수 있고, remote-required evidence는 compiler-unsupported/unknown family에 집중된다.
3. generator materialization
   - compiler-covered family는 `semantic_profile.compiler_strategy`를 보고 scaffold/fragment compiler를 우선 시도한다.
   - 현재 이 path가 실제로 연결된 family는 SQLi, CSRF, Command Injection, Code Injection, Template Injection, Path Traversal, XSS, SSRF, Insecure Deserialization, Open Redirect, XXE 열한 family다.
   - explicit `generator_mode=template`이고 viable template가 있으면 이제 compiler가 선점하지 않고 template path를 우선 사용한다. 따라서 MySQL sidecar SQLi 같은 runtime-surface lane은 `built_in_template` provenance로 분리해 읽을 수 있다.
   - 다만 unknown 계열은 여전히 LLM output 또는 deterministic fallback에 의존한다.
4. late gating
   - verifier / reviewer / pack이 semantic mismatch, unsupported semantic, generic fallback provenance를 뒤늦게 차단한다.

따라서 current truth에서 free-form lane은

- upstream semantic normalization은 존재하지만
- semantic-to-code compiler가 아직 unknown 계열에는 부재하고
- unsupported/weakly-supported family는 generic fallback 또는 late fail path로 흐른다.

즉 “이름만으로 동적 Docker 생성”은 semantic extraction 단계는 중상, 전체 compiler-first artifact generation은 열한 family까지 도달했고 real free-form positive generalization evidence도 Template Injection, Open Redirect, XXE 세 family까지 늘어났다. 다만 unknown 계열은 여전히 fallback 의존이 강하다.

### 3.7 구성 요소별 완성도 판정

| 계층 | current 상태 | 완성도 판정 | 근거 |
| --- | --- | --- | --- |
| name normalization | `vuln_name -> CWE-*` 또는 canonical `NAME-*` 정규화, `pattern_id`/stack profile 기본값 주입, supported alias(`Server Side Template Injection`, `Unvalidated Redirect`) canonicalization, `vuln_ids` list의 synthetic `NAME-*` preservation, bare single-token custom label의 synthetic `NAME-*` preservation, stopword-trimmed exact-content-token fallback | 중상 | free-form 입력을 canonical identifier와 기본 stack으로 내리는 경로는 안정적이고, 이번 갱신으로 일부 supported free-form alias도 exact phrase뿐 아니라 reordered token phrase(`Injection in Jinja template`, `Redirect open vulnerability`, `Injection in shell command`) 수준까지 canonical family로 정렬된다. 동시에 mixed-semantic phrase(`unsafe template deserialization`)는 더 이상 supported family로 과잉 canonicalize되지 않고 synthetic `NAME-*`로 남으며, `Foobar` 같은 single-token custom label도 bare identifier leakage 없이 same unsupported lane으로 유지된다. 다만 이것도 open-world semantic understanding이 아니라 supported family catalog robustness 강화 + fail-closed 보수화로 보는 편이 정확하다 |
| semantic inference | researcher가 `semantic_signature`, `evidence_relevance`, `verification_spec`, `guard_spec` 생성 | 중 | semantic basis는 만들 수 있으나 evidence quality와 compiler feasibility가 완전히 분리된 것은 아니다. 다만 compiler/static supported bundle은 default path에서 RESEARCH를 skip할 수 있게 되었다 |
| semantic_profile / compiler contract | `resolved_contract.json`와 별도 `semantic_profile.json`에 family/support_level/compiler_strategy/compiler_supported/compiler_reason가 surface됨. compiler-supported free-form family는 researcher를 skip해도 shared fragment registry/baseline에서 canonical `semantic_signature`를 backfill한다 | 중상 | semantic basis와 compiler feasibility를 artifact로 명시할 수 있게 되었고, 이제 unsupported early stop뿐 아니라 default search policy / RESEARCH skip도 이 verdict를 직접 소비한다. 현재는 `resolved_contract.semantic_contract`도 `aligned` + `semantic_signature_source=fragment_registry`까지 surface되지만, verifier의 최종 positive truth source는 여전히 `generator_manifest` service-side semantics가 우선이다 |
| runtime rule/guard derivation | runtime rule writer/loader, compiler-derived runtime rule, guard spec fallback, verifier semantic gate 존재 | 중상 | service-side semantic scope까지 반영되며 verifier trust는 개선되었다. built-in semantic evaluator support가 XSS/Insecure Deserialization/Open Redirect/Template Injection까지 확장되었고, compiler-generated `NAME-*` lane은 runtime rule을 generator가 직접 파생해 manifest fallback 의존을 일부 줄였다. 추가로 current workspace에서는 `verification_rule_source` / `verification_trust`를 surface해 unknown live lane의 self-derived runtime rule candidate를 low-trust로 구분한다 |
| semantic-to-code generation | SQLi/CSRF/Command Injection/Code Injection/Template Injection/Path Traversal/XSS/SSRF/Insecure Deserialization/Open Redirect/XXE에 `semantic_profile -> compiler_generated` path가 연결됨. 현재 compiler-covered 열한 family 모두 `python/flask` scaffold + family fragment metadata를 남긴다. unknown 계열은 여전히 fallback 중심 | 중상 | compiler-first coverage는 열한 family까지 넓어졌고, free-form generalization evidence도 Template Injection/Open Redirect/XXE의 exact/alias/reordered/paraphrase layer로 유지된다. XXE는 local-file entity model에 고정되지만 실제 positive compiler lane이 생겼다. 남은 주요 hole은 unknown/open-world lane이다 |
| template dependence reduction | built-in template 의존은 줄었고, compiler-covered 열한 family 모두 `stack_scaffold_id` + `fragment_id`를 남기는 shared registry-backed compose path로 이동했다. 이번 갱신으로 `python/flask` scaffold metadata와 Dockerfile template, compiler target 기본 매핑, fragment metadata 일부, Flask fragment code 일부, Flask PoC templates 일부, shared vuln family catalog, 그리고 MySQL sidecar SQLi의 runtime env derivation 규칙(`runtime_surface.service_env`)이 각각 asset으로 분리되었다 | 중상 | filesystem template dependence와 code-embedded alias drift는 모두 줄었고 compiler path 전반이 registry-backed provenance를 남기기 시작했다. 추가로 Path Traversal/XXE의 helper files도 이제 fragment asset DSL에서 직접 정의되어 compiler registry의 callback hardcoding이 한 단계 줄었다. MySQL sidecar SQLi의 runtime env derivation도 catalog-driven으로 옮겨져 `DB_HOST/USER/PASSWORD/NAME` 해석이 더 이상 strategy별 if-branch 하나에 고정되지 않는다. 다만 compose orchestration, sidecar selection resolver, single-scaffold assumption 등은 여전히 Python 모듈에 집중되어 있어 scaffold 외부화는 partial이고, 완전한 자산 분리까지는 도달하지 못했다 |
| unsupported lane early exit | real free-form `NAME-*` + `support_level=unsupported`는 preseeded semantic profile 기준으로 RESEARCH 실행 전 terminal failure로 종료됨 | 중상 | LDAP Injection이 약 `0.052s` / `retry_count=0`까지 내려갔다. 다만 `deferred` family와 broader unsupported taxonomy는 아직 더 세분화해야 한다 |

정리하면, 현재 레포의 강점은 “semantic을 구조화하고 나쁜 산출물을 막는 층”과 “여러 family를 non-template deterministic bundle로 닫는 운영 하한선”이다.
반면 약점은 “그 semantic을 compiler-first artifact로 안정적으로 생성하는 층”과 “증가한 family fallback code를 구조화된 scaffold/fragment 자산으로 승격하는 층”이다.

### 3.7.1 일반화 / 템플릿 의존성 완화 재평가

이번 구현 이후 current workspace 기준 positive non-template evidence는 아래와 같이 넓어졌다.

- official/known lane: SQLi, CSRF, Command Injection, Code Injection, Path Traversal, SSRF, XSS, Insecure Deserialization (`compiler-first`)
- real free-form positive lane: Template Injection, Open Redirect, XXE (`compiler-first`)
- real free-form positive multi-vuln lane: 단일 SID 안의 `Template Injection + Open Redirect` 2-bundle compiler-first success
- mixed free-form partial-progress lane: `Custom Weird Vuln + Open Redirect`처럼 unsupported/custom bundle이 fail-closed되어도 supported bundle은 same SID에서 compiler-first 실행을 계속 수행할 수 있음
- canonical alias-positive lane: `Server Side Template Injection -> NAME-TEMPLATE-INJECTION`, `Unvalidated Redirect -> NAME-OPEN-REDIRECT`
- unsupported negative lane: LDAP Injection, `Foobar -> NAME-FOOBAR` 등 `NAME-*`

이 변화는 분명한 개선이다.
특히 Template Injection, Path Traversal, Open Redirect, XSS, SSRF, Insecure Deserialization은 built-in filesystem template 없이 compiler-generated bundle로 승격되었다.
추가로 이번 갱신으로 Template Injection / Open Redirect 계열은 supported alias를 canonical family로 collapse할 수 있게 되어, previous exact-phrase brittleness도 1차 완화되었다.
이번 추가 갱신으로는 single-bundle free-form positive evidence를 넘어서, 하나의 run에서 둘 이상의 free-form family를 compiler-first bundle로 함께 닫는 multi-vuln source-of-truth도 확보했다.
추가로 이번 보완으로 `vuln_ids` list 자체도 catalog 미등록 free-form 이름을 synthetic `NAME-*` bundle로 보존하므로, multi-vuln minimal-input path가 supported family subset으로 조용히 축소되는 결함은 해소되었다.
또한 reordered phrase fallback은 이제 token subset이 아니라 stopword를 제거한 exact content token 기준으로만 허용되므로, 지원 family robustness와 ambiguous phrase fail-closed가 동시에 조금 더 정렬되었다.

다만 이것을 곧바로 “template dependence solved”로 해석하면 안 된다.
현재는 dependency shape가 아래처럼 바뀐 상태에 가깝다.

1. `workspaces/templates/**` 같은 filesystem template dependence는 일부 줄었다.
2. 현재 compiler-covered 열한 family(SQLi/CSRF/Command Injection/Code Injection/Path Traversal/SSRF/XSS/Insecure Deserialization/Open Redirect/Template Injection/XXE)는 모두 `python/flask` scaffold + registry fragment compose로 materialize되며 `stack_scaffold_id`, `stack_scaffold_version`, `fragment_id`, `compose_mode=registry`가 실제 manifest metadata에 남는다.
3. 이번 갱신으로 `python/flask` scaffold metadata와 Dockerfile template는 `agents/generator/assets/python-flask-scaffold.json`으로 분리되었고 compiler는 이를 registry 경유로 읽는다.
4. 이번 추가 갱신으로 scaffold registry는 단일 hardcoded path를 직접 고정하지 않고 `*-scaffold.json` asset catalog 전체를 스캔하며, asset에 선언된 alias(`python-flask`, `flask`)까지 함께 해석한다.
5. 이번 추가 갱신으로 free-form vuln family alias/identifier/pattern match도 `common/assets/vuln-family-catalog.json` 하나로 수렴했다. 즉 requirement normalization과 compiler fragment routing이 서로 다른 hardcoded synonym table을 들고 있지 않다.
4. 추가로 compiler target 기본 매핑도 `agents/generator/assets/compiler-targets.json`으로 분리되어, strategy -> default target 하드코딩 일부가 code path 밖 asset으로 이동했다.
5. 이번 턴 구현으로 fragment metadata(`family`, `fragment_id`, `pattern_tags`, `service_side_tokens`, `semantic_signature`, `requirements_content`)도 `agents/generator/assets/flask-fragments.json`으로 이동해, runtime rule/guard/evaluator가 소비하는 의미 계층 일부가 코드 밖 자산으로 분리되었다.
6. 추가로 Flask fragment의 `import_block`, `route_block`, `app_setup_block`, `startup_block`도 `agents/generator/assets/flask-fragment-code.json`으로 이동해 route/service 초기화 코드 하드코딩 일부까지 asset catalog로 밀어냈다.
7. 추가로 각 family의 PoC script template도 `agents/generator/assets/flask-pocs/*.py.tmpl`로 이동해, compiler registry 내부의 PoC 문자열 하드코딩도 크게 줄었다.
8. synthetic unknown 계열과 unsupported family는 여전히 `agents/generator/synthesis.py` fallback orchestration에 머물러 있고, compose orchestration과 sidecar selection resolver의 상당 부분은 아직 companion Python 모듈 안에 정의되어 있다. 다만 MySQL sidecar SQLi의 runtime env derivation 자체는 now `common/assets/vuln-family-catalog.json`의 `runtime_surface` asset으로 이동했다.
9. 이번 추가 구현으로 active synthetic unknown lane에 실제로 사용되는 SQLi family-aware fallback service/PoC도 `agents/generator/assets/fallbacks/sqli_family_aware_*.py.tmpl` asset으로 분리되어, 적어도 current hot path의 fallback hardcoding 일부는 Python 문자열에서 asset template로 이동했다.
10. 추가로 generic unsupported reflect fallback, CSRF, Open Redirect, Template Injection, XSS, SSRF, Insecure Deserialization, Path Traversal family-aware fallback service/PoC가 모두 `agents/generator/assets/fallbacks/*.py.tmpl` asset으로 분리되었다. Template Injection fallback에는 이번 라운드에서 PoC template도 추가되어 family-aware fallback bundle completeness가 조금 더 올라갔다.
11. 추가로 이번 라운드에서 fallback bundle의 공통 `Dockerfile`/`README`도 `agents/generator/assets/fallbacks/fallback_bundle_dockerfile.tmpl`, `agents/generator/assets/fallbacks/fallback_bundle_readme.md.tmpl`로 이동해, `synthesis.py` 안의 공통 compose string hardcoding도 한 단계 더 줄었다.
12. 즉 current debt는 더 이상 “개별 family fallback 문자열”보다 “Python module형 registry/compose logic + single-scaffold orchestration debt”에 더 가깝다. template debt가 사라진 것은 아니지만, 적어도 current family-aware fallback body와 fallback bundle 공통 compose artifact, 그리고 일부 representative extra file helper는 asset template/DSL로 이동했다.

이 구조의 장점:

- Docker/E2E operational coverage를 빠르게 넓힐 수 있다.
- LLM degraded 환경에서도 reproducible lower bound를 제공한다.
- free-form `vuln_name` lane 일부를 실제 positive evidence로 끌어올릴 수 있다.
- single-SID multi-vuln run에서도 provider `not_probed` / compiler-first lower bound를 유지할 수 있다.

이 구조의 한계:

- family가 늘수록 `synthesis.py`가 monolithic fallback registry로 비대해진다.
- stack scaffold와 vuln fragment가 분리되지 않아 재사용성이 낮다.
- generator/verifier/reviewer alignment가 function-level convention에 의존한다.
- alias robustness가 아직 open-world semantic inference가 아니라 curated alias/heuristic layer에 묶여 있다.
- non-compiler-covered lane의 provenance는 여전히 `deterministic fallback dependent`라서 generalization quality claim의 상한이 낮다.
- 새로운 family를 추가할 때 “semantic profile -> code compile”이 아니라 “새 hardcoded bundle 추가”로 흐르기 쉽다.

추가로 이번 턴에서 실제로 드러난 구조적 교훈은 “capability”를 단일 bool로 다루면 안 된다는 점이다.
최소한 아래 세 층을 분리해야 한다.

1. `family lower bound`
   - 현재 release가 해당 family에 compiler/static lower bound를 갖는가
2. `effective requirement lower bound`
   - 사용자가 `compiler.enabled=false` 등으로 그 lower bound를 실제 실행에서 끄지 않았는가
3. `executor feasibility`
   - 해당 bundle이 요구하는 external DB/network/sidecar/runtime contract가 current executor policy에서 실제로 충족되는가

이번 구현으로 1과 2의 drift, 2와 3의 drift는 일부 줄었지만, 장기적으로는 이 세 층을 plan artifact와 acceptance summary에 별도 field로 표준화하는 편이 더 맞다.

따라서 template dependence reduction의 현재 정확한 평가는 다음과 같다.

- `filesystem template dependence reduction`: 부분 달성
- `runtime template clone dependence reduction`: 부분 달성
- `family-specific hardcoding reduction`: 부분 달성
- `compiler-first dynamic generation`: 부분 달성

이후 개선안은 단순히 family를 더 추가하는 것보다, fallback bundle을 구조화된 compiler 자산으로 재편하는 데 초점을 둬야 한다.

### 3.7.2 family fallback -> compiler fragment migration matrix

아래 표는 “현재 family 구현을 어떤 compiler 자산으로 분해해야 하는가”를 정리한 것이다.

| family | current implementation path | target compiler strategy | 필요한 scaffold/fragment 자산 | verifier/reviewer 파생 규칙 | 잔여 리스크 |
| --- | --- | --- | --- | --- | --- |
| Open Redirect | `compiler_generated` + registry-backed scaffold/fragment compose | `open_redirect_reflect` | `python/flask` scaffold asset + `redirect_next_route` fragment + allowlist/offsite toggle fragment | redirect sink assertion, external `Location` header assertion, compiler-derived runtime rule | 현재는 scaffold metadata가 asset화됐지만, allowlist/offsite toggle 등 deeper fragment 옵션은 아직 정식 registry field로 분리되지 않았다 |
| Template Injection | `compiler_generated` + registry-backed scaffold/fragment compose | `template_injection_render` | `python/flask` scaffold asset + `render_template_string` fragment + arithmetic probe PoC fragment | template sink assertion, user input to template source assertion, compiler-derived runtime rule | 현재는 Flask/Jinja2 string-render model에 고정되어 있어 다른 template engine family로의 일반화는 아직 없다 |
| Path Traversal | `compiler_generated` + registry-backed scaffold/fragment compose | `path_traversal_file_read` | `python/flask` scaffold + `file_read_download_route` fragment + traversal target fixture | file sink assertion, request-controlled path assertion, traversal indicator assertion | read-only runtime contract는 맞췄지만 payload class와 exfil target contract가 아직 단순 텍스트 파일 수준이다 |
| XSS | `compiler_generated` + registry-backed scaffold/fragment compose | `xss_reflected` | `python/flask` scaffold + `render_reflect_route` fragment + optional template mode fragment | reflected sink assertion, unescaped render assertion, PoC literal과 service-side sink 분리 | browser-context 취약점과의 경계가 여전히 거칠고 verifier가 text-reflection 중심이다 |
| SSRF | `compiler_generated` + registry-backed scaffold/fragment compose | `ssrf_loopback_fetch` | `python/flask` scaffold + `loopback_fetch_route` fragment + metadata helper fragment | outbound request sink assertion, internal helper route assertion, same-container metadata probe contract | 네트워크 model이 helper route에 고정되어 있어 sidecar/real remote target 확장성이 낮다 |
| Insecure Deserialization | `compiler_generated` + registry-backed scaffold/fragment compose | `deserialization_pickle_body` | `python/flask` scaffold + `unsafe_pickle_body_route` fragment + payload serializer helper | unsafe deserialization sink assertion, binary body contract, payload class marker derivation | Python/pickle에 편중돼 있어 다른 serialization family로 일반화되지 않는다 |
| SQLi | `compiler_generated` + registry-backed scaffold/fragment compose | `sqli_string_concat` | `python/flask` scaffold + `login_query_concat_route` fragment + sqlite init fragment | input-to-SQL string composition assertion, SQL sink assertion, runtime init contract | 현재는 SQLite login model에 고정돼 있어 broader ORM/DB flavor 일반화는 아직 없다 |
| CSRF | `compiler_generated` + registry-backed scaffold/fragment compose | `csrf_missing_token` | `python/flask` scaffold + `csrf_state_change_route` fragment + session bootstrap fragment | cookie-auth session assertion, state-changing route assertion, missing CSRF token contract | 현재는 단순 session + transfer model에 고정돼 있어 multi-step workflow/REST variation 일반화는 아직 없다 |
| LDAP Injection | generic unsupported fallback only | `deferred` 또는 `ldap_filter_concat` | sidecar LDAP target 또는 in-memory mock fragment가 필요 | filter concatenation assertion, bind/search response contract | 현재 stack 자산이 없어 P0 compiler family로 잡기 어렵다. 문서상 deferred가 타당하다 |

이 migration matrix의 목적은 두 가지다.

1. `synthesis.py` 내부의 in-code template를 “임시 구현”으로 명시하고, 최종 귀착점을 fragment registry로 못 박는다.
2. family 확장 때마다 full app bundle을 새로 하드코딩하는 대신, 공통 scaffold와 family fragment를 분리해 debt가 선형적으로만 증가하도록 한다.

권장 구조 전환:

- `stack_scaffold_registry`
  - 예: `python/flask`
  - 공통 Dockerfile, requirements baseline, app bootstrap, health route, init hook 담당
- `family_fragment_registry`
  - 예: `open_redirect_redirect_next`, `xss_render_template_string`, `ssrf_loopback_fetch`, `deserialization_pickle_body`
  - route/sink/helper endpoint/PoC/init snippet만 담당
- `semantic_profile -> compiler_strategy`
  - researcher가 semantic profile과 compiler strategy를 고정
  - generator는 bundle 전체를 새로 쓰는 대신 scaffold + fragment를 compose
- `derived verifier bundle`
  - runtime rule, guard spec, evaluator assertion을 same fragment metadata에서 파생

이렇게 바꾸면 얻는 효과는 다음과 같다.

- family 추가 비용이 “새 hardcoded app/poc bundle 추가”에서 “새 fragment 추가”로 줄어든다.
- template clone과 in-code template의 경계가 사라지고, compiler provenance를 별도 class로 surface할 수 있다.
- 동일 semantic basis로 generator/verifier/reviewer를 묶기 쉬워 drift가 줄어든다.
- unsupported family는 `compiler_supported=false`로 더 이른 단계에서 종료할 수 있다.

### 3.8 목표 아키텍처: compiler-first 동적 생성

템플릿 의존성을 낮추려면 목표 아키텍처를 아래처럼 바꿔야 한다.

`vuln_name -> semantic_profile -> compiler_supported? -> stack scaffold + vuln fragment compile -> derived runtime_rule/guard/evaluator -> optional LLM refinement`

핵심 원칙:

- 취약점별 full template를 복사하지 않는다.
- stack별 공통 scaffold는 소수만 유지한다. 예: `python/flask`
- 취약점 family별로는 route/sink/helper endpoint/PoC fragment만 유지한다.
- runtime rule, guard spec, evaluator는 동일 `semantic_profile`에서 파생한다.
- `compiler_supported=false`이면 generic success artifact를 만들지 않고 early fail-closed 또는 inspection-only path로 종료한다.

이 구조의 장점은 다음과 같다.

- synthesis mode에서도 template clone 없이 deterministic artifact를 만들 수 있다.
- same semantic basis로 generator/verifier/reviewer가 정렬되어 drift가 줄어든다.
- unsupported family는 early stop이 가능해 성능 낭비가 줄어든다.

### 3.9 family rollout 우선순위

compiler-first 전환의 현실적 우선순위는 family별 난이도와 남은 debt 형태에 따라 달라진다.

- Tier A: shared fragment registry hardening + scaffold/fragment compose 구조화
  - 이미 green인 SQLi/CSRF/Command Injection/Code Injection/Template Injection/Path Traversal/XSS/SSRF/Insecure Deserialization/Open Redirect를 유지하되, 현재 `flask_fragment_registry.py`에 들어간 registry를 runtime rule/guard/evaluator와 더 강하게 공통화하고 이후 외부 data asset으로 승격해야 한다.
- Tier B: second scaffold / richer runtime model
  - 현재 `python/flask` 단일 scaffold 편중이 가장 큰 구조적 한계이므로, 다음 확장은 family 수 증가보다 stack 다양화와 sidecar/helper model 일반화가 우선이다.
- Tier C: LDAP Injection
  - embedded target/sidecar 또는 더 많은 protocol scaffolding이 필요해 P0 대상으론 비효율적이다.

현재 구현 업데이트로 SQLi, CSRF, Command Injection, Code Injection, Template Injection, Path Traversal, Open Redirect, XSS, SSRF, Insecure Deserialization은 compiler-first evidence까지 확보되었다.
따라서 다음 우선순위는 compiler-covered family를 더 추가하기 전에 fragment registry 정리와 synthetic unknown/open-world lane의 compiler 부재를 먼저 다루는 쪽이다.
LDAP Injection은 계속 명시적 deferred/unsupported family로 관리하는 편이 맞다.

## 4. Active Defects 및 위험도

### 4.1 P0 resolved in this turn: unsupported free-form false positive 1차 해소

이 항목은 이번 턴 구현으로 1차 해소되었고, 이후에는 regression watch + official negative coverage 확장 항목으로 관리한다.
다만 현재 구현 업데이트로 `Open Redirect`는 더 이상 이 bucket에 속하지 않고, compiler-first positive lane으로 이동했다.

#### 증상

- 이전 구현에서는 `vuln_name: Open Redirect`와 `vuln_name: LDAP Injection`가 false-positive pass했다.
- 현재 workspace truth에서는 `LDAP Injection` 같은 unsupported family가 GENERATOR 이전 RESEARCH-stage에서 fail-closed된다.
- `Open Redirect`는 unsupported bucket이 아니라 supported deterministic lane으로 재분류되었다.
- `promotion.eligible=false`가 되고, `failure_manifest.json`만 남는다.
- `failure_manifest.json`에는 top-level `failure` summary와 bundle-level `failure` summary가 남는다.
- provenance에는 `generation_origin=research_short_circuit`와 `dynamicness=pre-generation fail-closed`가 기록된다.

#### 현재 root cause chain

1. minimal-input normalization이 real free-form name을 `NAME-*`로 정규화한다.
2. unsupported family에는 dedicated compiler path가 없고, semantic profile이 `support_level=unsupported`를 surface한다.
3. 따라서 이 lane을 generator/executor로 보내지 않고 어디서 끊을지가 핵심 gating 문제였다.
4. 현재는 run_pipeline이 RESEARCH 직후 `semantic_profile.support_level=unsupported && compiler_supported=false`를 terminal condition으로 소비한다.
5. pack은 이 early failure를 `failure_manifest.failure`, bundle failure summary, `research_short_circuit` provenance로 함께 surface한다.
6. rerun 시작 시 stale generated state를 정리해 이전 success manifest가 다음 failure run을 오염시키는 문제도 함께 차단했다.

#### 왜 P0인가

이 defect는 단순히 unknown lane이 fail하는 문제보다 더 위험했다.
실제 unsupported family가 “성공한 artifact”처럼 보였기 때문이다.
이번 턴의 핵심 구현은 바로 이 승격 오류를 차단하는 데 있었다.

#### required behavior

unsupported free-form/unknown lane은 inspection artifact를 남길 수는 있어도,
semantic support가 없는 상태에서는 성공 manifest 또는 promotion success로 승격되면 안 된다.
이 behavior는 이번 턴에서 1차 구현되었다.

#### P0 acceptance

- `LDAP Injection` regression에서 GENERATOR 이전 terminal fail-closed가 실제로 재현되었다.
- `promotion.eligible=false`가 surface되었다.
- `failure_manifest.json`만 남고 stale `manifest.json`은 rerun 시작 시 정리된다.
- top-level/bundle failure summary에 `terminal_failure_class=semantic_support_missing`가 surface된다.
- provenance에는 `generation_origin=research_short_circuit`, `dynamicness=pre-generation fail-closed`가 기록된다.

### 4.1.1 P0 resolved in this turn: compiler-supported name-only lane의 remote-required decoupling

이 항목은 이번 턴 구현으로 1차 해소되었다.

- 이전 구현에서는 static rule이 없는 compiler-supported family가 default minimal-input path에서 `remote_required` researcher에 묶였다.
- 현재는 requirement normalization / guard unknown 판정 / run_pipeline skip이 모두 compiler/static supported verdict를 직접 소비한다.
- 결과적으로 Path Traversal, XSS, Insecure Deserialization, Template Injection, Open Redirect, XXE 같은 lane이 Tavily availability 없이도 official E2E green이다.
- 다만 이것은 `trusted dynamic`이 아니라 `compiler-first lower bound` 개선이다.

### 4.1.2 P1 partially resolved in this turn: exact-phrase brittleness와 hybrid random template fallback

이 항목은 이번 턴 구현으로 한 단계 더 보수적으로 정렬되었지만, open-world semantic inference가 완성된 것은 아니다.

- previous issue 1: `Template Injection`은 닫히지만 semantically equivalent alias `Server Side Template Injection`은 unsupported `NAME-SERVER-SIDE-TEMPLATE-INJECTION`로 fail-closed되었다.
- current fix: requirement normalization이 supported free-form alias를 canonical `NAME-*` family로 collapse한다. current workspace rerun에서 `template-injection-alias-name-only`, `template-injection-paraphrase-name-only`는 `real_free_form_positive`, `compiler-first`, `promotion.eligible=true`로 닫히고, `Unvalidated Redirect`, `External redirect vulnerability`도 same Open Redirect compiler lane으로 닫힌다.
- previous issue 1-1: token subset fallback이 `unsafe template deserialization` 같은 mixed phrase를 supported family로 과잉 canonicalize할 수 있었다.
- current fix 1-1: token fallback을 stopword-trimmed exact-content-token match로 좁혀 ambiguous phrase는 synthetic `NAME-*`로 남기고, curated alias/reordered phrase만 compiler lane으로 승격되도록 보수화했다.
- previous issue 2: `hybrid` mode는 synthesis failure 후 compatible template가 없어도 random template sampler로 내려갈 수 있었다.
- current fix: generator는 이제 compatible template가 있을 때만 hybrid template fallback을 허용하고, 그렇지 않으면 synthesis failure를 그대로 유지한다.

남은 한계:

- alias robustness는 여전히 curated alias / heuristic layer에 한정된다.
- open-world free-form semantic paraphrase 전반을 compiler strategy로 일반화하는 구조는 아직 아니다.

### 4.1.3 P1 resolved in this turn: compiler-disabled lower-bound policy drift

이 항목은 이번 턴 구현으로 1차 해소되었다.

- previous issue: `compiler.enabled=false` 또는 legacy `disable_compiler=true`가 있어도 planner는 family-level compiler capability만 보고 `remote_prefer` / `require_researcher_evidence=false` / researcher skip 가능 lane으로 남겼다.
- root cause: `can_resolve_without_remote_research(vuln_id)`가 “family lower bound”인데도 requirement normalization, researcher unknown 판정, run_pipeline researcher skip이 이를 그대로 “effective requirement lower bound”처럼 사용했다.
- current fix: requirement-aware lower-bound helper를 추가해 normalization, researcher unknown classification, run_pipeline `_can_skip_researcher`가 compiler-disabled request를 다시 remote-required lane으로 분류한다.
- latest sanity rerun에서는 `Template Injection + compiler.enabled=false`가 `researcher.search_policy=remote_required`, `policy.require_researcher_evidence=true`, `_can_skip_researcher=false`로 정렬되었다.

남은 한계:

- `can_resolve_without_remote_research(vuln_id)`는 여전히 family catalog lower bound로 남아 있다.
- 따라서 문서/metric/ops에서 “family lower bound”와 “effective requirement lower bound”를 계속 구분해 읽어야 한다.

### 4.1.4 P1 resolved in this turn: external DB / sidecar mismatch fail-fast

이 항목은 이번 턴 구현으로 1차 해소되었다.

- previous issue: external DB requirement(`runtime.db=mysql|postgres...` 또는 generated `requires_external_db=true`)가 있어도 `policy.executor.sidecars`가 비어 있거나 네트워크가 꺼져 있으면 Docker build/run까지 내려가 늦게 실패했다.
- current fix: run_pipeline에 `EXECUTOR_PRECHECK`를 추가해 generated bundle/runtime requirement와 executor policy를 대조한 뒤 `terminal_failure_class=executor_dependency_misconfigured`로 fail-fast한다.
- direct executor path도 `_start_sidecars()`에서 empty sidecar policy / disabled network를 즉시 에러로 표면화한다.
- latest sanity rerun에서는 external DB requirement + disabled network 조합이 `executor_dependency_misconfigured`로 바로 차단되었다.

남은 한계:

- 이것은 기본적으로 negative/fail-fast hardening이지만, 이번 후속 갱신으로 별도의 built-in MySQL sidecar positive lane(`sqli-sidecar-template`)도 official source-of-truth에 편입되었다.
- 추가로 compiler-first MySQL sidecar positive lane(`sqli-sidecar-compiler`)도 official source-of-truth에 편입되었다.
- 다만 이는 SQLi + MySQL 조합 한정이며, richer bridge/sidecar family 일반화까지 확보된 것은 아니다.

### 4.1.5 P1 resolved in this turn: multi-vuln free-form `vuln_ids` silent drop

이 항목은 이번 턴 구현으로 1차 해소되었다.

- previous issue: `vuln_ids` list는 `vuln_name`과 달리 catalog에 없는 free-form 이름을 synthetic `NAME-*`로 보존하지 못해, `Custom Weird Vuln + Open Redirect` 같은 입력이 warning 없이 `NAME-OPEN-REDIRECT` 단일 bundle로 축소될 수 있었다.
- root cause: `_extract_vuln_ids()`가 list entry마다 `_coerce_identifier()`만 호출했고, 공백/자연어가 포함된 value는 빈 값으로 떨어져 조용히 버려졌다.
- current fix: normalization이 `vuln_ids`/`vuln_id` free-form 값을 synthetic `NAME-*`로 보존하고 `vuln_id_resolutions[]` trace를 남긴다.
- current fix 1-1: RESEARCH-stage terminal failure metadata도 `bundle_slug`/`vuln_id`를 함께 남기도록 보강해, mixed multi-vuln failure run에서 unsupported bundle의 failure/provenance가 supported bundle로 복제되지 않게 했다.
- latest sanity rerun에서는 `{'vuln_ids': ['Custom Weird Vuln', 'Open Redirect'], 'multi_vuln': true}`가 `['NAME-CUSTOM-WEIRD-VULN', 'NAME-OPEN-REDIRECT']` 두 bundle로 유지되고, top-level `name_resolution`도 `synthetic_name` source를 보존한다.
- 같은 latest rerun에서 whole run은 여전히 `evidence_low_relevance`로 fail-closed되지만, `NAME-OPEN-REDIRECT` bundle은 더 이상 `unsupported_free_form_negative`로 오염되지 않고 `real_free_form_non_generalizing` + empty failure로 남는다.

남은 한계:

- mixed success/failure multi-vuln lane은 이제 input preservation을 넘어서 partial-progress 실행까지 가능하지만, official source-of-truth와 promotion policy는 아직 충분히 고정되지 않았다.

### 4.1.6 P1 resolved in this turn: mixed multi-vuln unsupported free-form bundle의 unnecessary remote RESEARCH

이 항목은 이번 턴 구현으로 1차 해소되었다.

- previous issue: single unsupported `NAME-*` lane은 preseeded semantic profile 기준 `semantic_support_missing`으로 거의 즉시 fail-closed되는데, mixed multi-vuln request에서는 unsupported bundle도 researcher를 타면서 `remote_provider_unavailable` 또는 `evidence_low_relevance`로 분류될 수 있었다.
- root cause: `run_pipeline.py`의 pre-generation semantic stop은 “모든 relevant free-form bundle이 unsupported일 때”만 terminal이었고, `agents/researcher/main.py`는 bundle 단위 semantic profile을 보고 fail-closed하지 않았다.
- current fix: researcher entrypoint가 bundle별 `semantic_profile`을 먼저 읽고, `support_level=unsupported && compiler_supported=false`인 free-form bundle은 실제 search 호출 전에 `quality=insufficient`, `terminal_failure_class=semantic_support_missing` report를 직접 기록한다.
- latest `multi-name-mixed-partial` rerun에서는 `NAME-CUSTOM-WEIRD-VULN` bundle이 더 이상 remote provider failure로 분류되지 않고 `semantic_support_missing` + `generation_origin=research_short_circuit`로 닫혔다.
- same rerun에서 top-level failure stage도 `VERIFY`가 아니라 root cause에 맞춰 `RESEARCH`로 정렬되었다.

남은 한계:

- mixed request에서 unsupported bundle을 inspection-only artifact로 남길지, 더 강하게 input validation 단계에서 reject할지는 아직 정책 선택의 여지가 있다.

### 4.1.7 P1 resolved in this turn: bundle-aware provider health rollup 부재

이 항목은 이번 턴 구현으로 1차 해소되었다.

- previous issue: `performance_summary.provider_health_state`는 root `metadata/<sid>/search_health.json`만 읽고, bundle-level `search_health.json`이나 `failed_bundles[].terminal_failure_class`를 보지 않았다.
- 결과적으로 bundle-scoped RESEARCH failure가 있어도 top-level provider 상태가 `not_probed` 또는 generic `bundle_scoped_research_failure`처럼 부정확하게 surface될 수 있었다.
- current fix: provider health 계산이 bundle-level search health payload와 loop-state의 nested `failed_bundles[].terminal_failure_class`까지 집계한다. 단, `semantic_support_missing`처럼 provider 자체와 무관한 pre-generation fail-closed는 provider state로 승격하지 않는다.
- regression test는 `bundle_scoped_research_failure` 아래의 nested `remote_provider_unavailable`가 top-level `provider_health_state=remote_provider_unavailable`로 정렬되는 경로를 고정한다.

남은 한계:

- current provider health는 still single label이므로, mixed request 안에서 일부 bundle만 degraded/provider-missing인 상태를 lossless하게 표현하지는 못한다.

### 4.1.8 P1 partially resolved in this turn: multi-bundle top-level provenance/trust 요약 공백

이 항목은 이번 턴 구현으로 한 단계 개선되었다.

- previous issue: multi-bundle manifest는 bundle-level provenance/dynamicness/verification 정보를 충분히 갖고 있어도 top-level `generation_origin`, `dynamicness_verdict`, `verification_rule_source`, `verification_trust`가 비어 있었다.
- current fix: multi-bundle manifest도 bundle 값이 uniform하면 그 값을 top-level로 mirror하고, 다르면 `mixed` sentinel을 surface한다.
- latest `multi-name-only-supported` rerun에서는 top-level `generation_origin=compiler_generated`, `dynamicness_verdict=compiler-first`, `verification_rule_source=compiler_runtime_rule`, `verification_trust=medium`가 직접 남는다.
- latest `multi-name-mixed-partial` rerun에서는 위 네 필드가 모두 `mixed`로 남아 downstream consumer가 “bundle-level 상세를 더 봐야 한다”는 사실을 즉시 알 수 있다.

남은 한계:

- `mixed`는 pragmatic sentinel일 뿐 lossless schema는 아니다. 장기적으로는 top-level enum 하나보다 bundle-set summary object를 별도 표준화하는 편이 맞다.

### 4.1.9 P0 resolved in this turn: single-token free-form name의 bare identifier leakage

이 항목은 이번 보완으로 해소되었다.

- previous issue: `vuln_name: Foobar`, `vuln_id: Foobar`, `vuln_ids: [Foobar]` 같은 single-token custom 입력은 whitespace가 없다는 이유로 bare `FOOBAR` explicit identifier로 남을 수 있었다.
- root cause: requirement normalization의 `_coerce_vuln_reference()`가 `allow_synthetic_name=True`인 경로에서도 일반 영숫자 token을 synthetic `NAME-*`보다 먼저 explicit identifier로 승격했다.
- impact: same input이 `name_resolution.source=synthetic_name`처럼 보이더라도 실제 `vuln_id`는 `FOOBAR`로 남아, `run_pipeline`의 free-form unsupported fast-fail(`NAME-*` + `support_level=unsupported`)에서 빠질 수 있었다.
- current fix: `allow_synthetic_name=True` 경로에서는 mapped alias/CWE/CVE/이미 canonical identifier가 아닌 bare plaintext token도 synthetic `NAME-*`로 정규화한다.
- current rerun: `vuln_name: Foobar`는 now `NAME-FOOBAR`로 보존되며, `VUL_WEB_SEARCH_PROVIDER=none` rerun에서 `failure.stage=RESEARCH`, `terminal_failure_class=semantic_support_missing`, `provider_health_state=not_probed`, `compiler_supported=false`까지 surface된다.

왜 중요했는가:

- 이 leak는 unsupported negative lane의 taxonomy를 `semantic_support_missing`에서 `remote_provider_unavailable` 또는 generic unknown lane 쪽으로 밀어낼 수 있었다.
- 즉 unsupported free-form false positive를 막더라도 “unsupported/custom name-only input은 semantic fail-closed된다”는 문서 claim을 single-token label이 우회할 수 있었다.

현재 남은 한계:

- single-token custom name preservation은 해결되었지만, 이것이 open-world family understanding을 의미하지는 않는다.
- 현재는 unsupported/custom 입력을 더 정확히 fail-closed하는 보수화이며, compiler-supported family catalog 자체를 확장한 것은 아니다.

### 4.2 P1: 문서와 workspace truth의 정합성 드리프트

현재 문서에는 과거 failure record가 current baseline처럼 남아 있지만,
동일 SID rerun으로 artifact가 덮여쓰일 수 있다는 사실 자체는 여전히 유효하다.

대표 예:

- `sid-3325b4630aa4`
- `sid-60ae4e071b9f`
- `sid-d2ff12df4e6d`

이번 턴 구현으로 stale generated state carry-over는 1차 차단되었지만,
raw SID를 historical evidence locator로 쓰는 문서 방식은 여전히 부정확하다.

다만 official harness 관점에서는 이번 갱신으로 freshness가 더 강해졌다.

- `tests/e2e/run_case.py`는 runtime asset seed manifest를 남기고 rerun마다 `runtime_rules/`, `runtime_templates/`를 purge 후 restore한다.
- same harness는 summary/expectation validation에서 `generation_origin`, `dynamicness_verdict`까지 읽는다.
- 따라서 official acceptance evidence는 이전보다 raw runner artifact drift에 덜 취약하다.

### 4.3 P1: synthetic unknown lane과 real free-form lane의 혼선

현재 `cwe-unknown-basic` live lane은 다음 이유로 generalization 증거가 아니다.

- explicit synthetic id `CWE-9999`
- base requirement에서 `pattern_id: sqli-string-concat`를 상속
- semantic contract가 SQLi-like signature로 정렬될 수 있음
- latest rerun 기준 verifier도 `verification_rule_source=runtime_rule_candidate`, `verification_trust=low`를 surface함
- 따라서 open-world free-form unknown이라기보다 synthetic regression lane

문서, CI summary, acceptance에서 이 lane을 “free-form name-only success evidence”로 쓰면 안 된다.

### 4.4 P1: official lane coverage와 acceptance mismatch

현재 acceptance와 current workspace rerun truth 사이의 드리프트는 이번 갱신으로 더 줄었다.

대표 mismatch는 아래와 같다.

- current green lane은 `compiler-first`, `deterministic fallback dependent`, fixture-backed `trusted dynamic`이 공존한다. 다만 마지막 항목도 아직 live remote LLM evidence와 동의어는 아니다.
- 남은 핵심 mismatch는 synthetic unknown lane을 negative no-remote regression과 live Tavily regression으로 분리해 읽어야 한다는 점이다.
- 이번 갱신으로 official E2E acceptance는 bundle-level `generation_origin=compiler_generated`, `dynamicness_verdict=compiler-first`, 또는 negative/fallback lane의 corresponding provenance까지 기대치로 고정하기 시작했다.
- 추가로 fixture-backed `trusted-dynamic-sqli` official lane이 들어오면서 `generation_origin=llm_manifest`, `dynamicness_verdict=trusted dynamic`, `llm_fixture_used=true` surface 자체는 current truth에 편입되었다.
- 추가로 이번 턴 구현으로 static rule이 없는 compiler-generated lane의 verifier provenance는 `compiler_runtime_rule/medium`으로 분리되어, compiler-coupled verification이 `declared_rule/high`처럼 보이던 mismatch도 1차 완화되었다.

즉 current acceptance에서 “mandatory official lane = 모두 operationally green”은 현재는 대체로 맞지만,
이를 곧바로 “동적 생성이 provenance 상으로 충분히 일반화되었다”와 동의어로 쓰면 안 된다.

따라서 official live lane을 “present in test suite”, “current degraded green”, “compiler-first green”으로 3분할해 집계하는 쪽이 더 자연스럽다.
Path Traversal/Template Injection/Open Redirect/XSS/Insecure Deserialization까지 now-default path에서 compiler-first green이고, `Server Side Template Injection` alias도 같은 positive lane으로 닫혔다. 남은 핵심 mismatch는 synthetic unknown lane 해석과 open-world alias coverage 쪽이다.

### 4.5 P1: manifest filename semantics drift

이 항목은 이번 추가 구현으로 대부분 해소되었다.

현재 code path에서는 PACK 단계가 `_pipeline_result`를 먼저 보고,

- success run이면 `manifest.json`
- failure run이면 `failure_manifest.json`

만 남기도록 정렬되었다.

추가로 `allow_intentional_vuln=true`인 실패 run에 대해서도 `failure_manifest.json`만 남는 것을 current workspace에서 재검증했다.

따라서 raw filename semantics drift는 1차 해소되었고,
이후에는 stale counterpart file이 재생성되지 않는지 regression watch로 관리하면 된다.

### 4.6 P1: degraded known lane success 메시지의 과대평가 위험

current known lane degraded success는 분명한 개선이다.
하지만 성격은 `trusted dynamic recovery`가 아니다.

정확한 서술은 다음이다.

- SQLi/CSRF/Path Traversal/XSS/SSRF/Insecure Deserialization known lane은 현재 `compiler-first success`
- Command Injection/Code Injection known lane도 현재 `compiler-first success`
- Template Injection/Open Redirect free-form positive lane은 현재 `compiler-first success`
- 즉 provider degraded에서도 artifact truth는 남기고 known lane 일부를 닫을 수 있음
- 하지만 pure dynamic synthesis recovery로 집계하면 안 됨
- synthetic unknown live도 latest rerun 기준 asset-backed SQLi family-aware fallback을 사용하지만, 여전히 `runtime_rule_candidate/low` verifier trust와 `synthetic_regression` class에 머문다

### 4.7 P1 partially resolved: RESEARCH-stage taxonomy surface는 개선됐지만 아직 coarse하다

현재 pre-generation 종료 taxonomy는 이전보다 개선되었고, insufficient evidence reason도 top-level failure에 더 직접 surface되기 시작했다. 이번 갱신으로 `remote_provider_unavailable`까지 terminal failure class로 분리되어 single-shot stop이 가능해졌고, latest `CWE-9999` no-remote rerun에서는 `performance_summary.provider_health_state`도 동일하게 `remote_provider_unavailable`로 정렬되었다. 추가로 이번 턴 구현으로 PACK 이후 manifest를 다시 기록하게 만들어, `manifest.performance`와 `performance_summary.json` 사이의 stale mismatch도 제거되었다.
다만 performance/ops surface가 모든 failure class를 equally rich하게 반영하는 수준까지는 아직 아니다.
후속 문서/구현에서는 최소 다음 taxonomy를 분리해야 한다.

- `remote_evidence_missing`
- `evidence_low_relevance`
- `provider_degraded`
- `semantic_support_missing`

### 4.7.1 P1 partially resolved in this turn: verifier self-certification은 더 잘 surface되지만 아직 독립 verifier가 아니다

이 항목은 이번 턴 구현으로 “숨겨진 문제”에서 “보이는 문제”로 이동했다.

- 이전에는 unknown/open-world lane이 `generator_manifest fallback` 또는 researcher/runtime rule candidate를 통해 self-derived verification을 해도 summary에서 구분이 약했다.
- 현재는 verifier result, manifest bundle summary, E2E summary에 `verification_rule_source`와 `verification_trust`가 surface된다.
- 추가로 static rule이 없는 compiler-generated lane도 `compiler_runtime_rule/medium`으로 분리되어, compiler-coupled verification과 declared independent rule을 artifact 수준에서 구분할 수 있게 되었다.
- 추가로 manifest top-level `verification_summary`와 reviewer issue sample에도 low-trust 상태가 남는다.
- latest `CWE-9999` live rerun에서는 `verification_rule_source=runtime_rule_candidate`, `verification_trust=low`, promotion reason `verify_contract:runtime_rule_candidate`, reviewer issue `Verifier contract trust is low (runtime_rule_candidate)`가 함께 남는다.
- latest Template Injection / Open Redirect rerun에서는 `verification_rule_source=compiler_runtime_rule`, `verification_trust=medium`이 직접 surface된다.

다만 이것이 verifier 독립성 문제를 해결한 것은 아니다.

- current synthetic unknown live는 여전히 low-trust verification success다.
- current compiler-first positive lane도 static rule이 없는 family에서는 medium-trust compiler-coupled verification이다.
- 즉 `verify_pass=true`가 곧 independent verification을 의미하지 않는다.
- 남은 과제는 unknown/open-world lane에서 researcher/runtime-rule candidate를 diagnostics 또는 inspection artifact로만 제한할지, 아니면 stronger external evidence/second verifier를 붙일지 policy를 고정하는 것이다.

### 4.7.2 P1 partially resolved in this turn: transient LLM failure의 process-wide stub latch는 완화됐지만 live remote evidence는 아직 약하다

이 항목은 이번 턴 구현으로 “retry 불가능한 숨은 저하”에서 “call-level degraded fallback”으로 한 단계 개선되었다.

- previous issue: remote LLM call이 한 번이라도 `429`/transient network/provider error로 실패하면 같은 process의 이후 호출도 전부 stub mode로 고정되었다.
- current fix: `LLMClient`는 이제 missing-key / missing-litellm 같은 configuration absence일 때만 persistent stub mode를 유지하고, runtime provider error는 해당 call만 stub fallback으로 처리한다.
- regression test는 첫 call `429` 후 둘째 call real provider success를 다시 허용하는 동작을 고정했다.

남은 한계:

- current official trusted-dynamic evidence는 여전히 fixture-backed lane뿐이다.
- 즉 “transient failure 후 재시도 가능”은 개선됐지만, live remote provider 기반 trusted-dynamic acceptance가 닫힌 것은 아니다.

### 4.8 P1: semantic-to-code compiler coverage가 일부 family에 한정된다

현재 시스템은 free-form 이름을 semantic basis로 정규화할 수 있고, 일부 family는 그 semantic basis를 deterministic code artifact로 compile할 수 있다.
하지만 coverage는 아직 일부 family에 한정되어 있고, real free-form positive generalization은 현재 Template Injection, Open Redirect, XXE 세 family가 대표 증거다.

대표 증상:

- `Open Redirect`는 이제 non-empty semantic signature + `open_redirect_reflect` compiler path로 positive lane이 닫히며, current truth에서는 `compiler-first`다.
- `Template Injection`도 이제 non-empty semantic signature + `template_injection_render` compiler path로 positive lane이 닫히며, current truth에서는 `compiler-first`다.
- `XML External Entity`도 이제 non-empty semantic signature + `xxe_xml_entity_resolve` compiler path로 positive lane이 닫히며, current truth에서는 `compiler-first`다.
- `SQLi`도 이제 `sqli_string_concat` compiler path로 승격되어 current truth에서는 `compiler-first`다.
- `CSRF`도 이제 `csrf_missing_token` compiler path로 승격되어 current truth에서는 `compiler-first`다.
- `Code Injection`도 이제 `code_injection_eval` compiler path로 승격되어 current truth에서는 `compiler-first`다.
- `Path Traversal`도 이제 `path_traversal_file_read` compiler path로 승격되어 current truth에서는 `compiler-first`다.
- XSS도 이제 `xss_reflected` compiler path로 승격되어 current truth에서는 `compiler-first`다.
- SSRF는 `ssrf_loopback_fetch` compiler path로 승격되었지만, same-container `/metadata` helper model에 고정되어 있다.
- Insecure Deserialization도 `deserialization_pickle_body` compiler path로 승격되었지만, Python/pickle 모델에 편중돼 있다.

이 defect는 단순히 “family coverage가 적다”는 의미보다 더 크다.
현재 구조에서는 free-form generalization이 upstream semantic normalization에는 성공해도,
Template Injection/Open Redirect 계열을 제외한 real free-form positive family는 아직 compiler-first artifact generation까지 연결되지 않는다.
또한 이번 턴으로 `Server Side Template Injection` alias는 same compiler lane으로 닫히지만, 이것은 alias-layer robustness 개선이지 open-world semantic compiler coverage 자체의 증거는 아니다.
즉 현재의 fail-closed는 안전하지만, 동적 생성 완성도와 일반화 폭 면에서는 여전히 미완성이다.

### 4.9 P1: template dependence reduction이 현재는 relocation 수준에 머문다

runtime candidate template는 current code 기준 static template clone이다.
또한 generator는 template/hybrid mode에서만 runtime template를 사용한다.

따라서 현재 상태를 “template dependence reduction”이라고 부르면 과장이다.
정확한 표현은 다음이다.

- filesystem template copy 의존은 줄었고, representative compiler-first acceptance는 이제 registry-backed scaffold/fragment provenance까지 본다.
- 그러나 runtime model 자체는 아직 `python/flask` 단일 scaffold에 강하게 편중되어 있다.
- 즉 current improvement는 “template -> compiler registry/scaffold” 전환이지, “stack/runtime 다양성까지 일반화된 동적 생성”은 아니다.

- static template dependence 일부를 runtime metadata 아래로 이동시켰다.
- 그와 별개로 SQLi/CSRF/Command Injection/Code Injection/Template Injection/Path Traversal/Open Redirect/XSS/SSRF/Insecure Deserialization은 filesystem template 없이 compiler-generated bundle로 닫히도록 개선되었다.
- 다만 취약점 family별 full workspace copy 대신 scaffold/fragment compile로 바뀌기 전까지는, 이것 역시 template debt reduction의 완결이 아니라 relocation + in-code hardcoding 증가로 보는 편이 정확하다.

## 5. Normative Logic Spec 및 구체적 로직 보완안

이 섹션은 문서 수준 규격이다.
후속 구현은 이 섹션을 기준으로 test-first로 수행한다.

### 5.1 verifier 결과 규격

verifier의 공식 top-level verdict는 다음 필드를 가진다.

| field | type | 의미 |
| --- | --- | --- |
| `exploit_pass` | `bool` | PoC marker/exit/assertion 기준 exploit 성공 여부 |
| `semantic_pass` | `bool` | semantic gate가 통과했는지 |
| `guard_pass` | `bool` | dynamic guard가 통과했는지 |
| `verify_pass` | `bool` | 최종 verdict |
| `semantic_supported` | `bool` | semantic verdict를 내릴 수 있는 유효 semantic basis가 있었는지 |
| `semantic_source` | `str \| null` | semantic basis source. 예: `resolved_contract.semantic_contract`, `builtin_semantics`, `runtime_rule.semantic_signature`, `null` |
| `semantic_status` | `aligned \| contradicted \| unsupported \| empty` | semantic contract의 상태 |
| `verification_rule_source` | `str` | `declared_rule`, `compiler_runtime_rule`, `runtime_rule_candidate`, `generator_manifest_fallback`, `verifier_runtime_rule_fallback` 등 verifier contract provenance |
| `verification_trust` | `str` | `high`, `medium`, `low` 등 verifier contract 신뢰도 |
| `verification_trust_reason` | `str` | trust 판정 이유 |
| `verification_policy_blocked` | `bool` | strict verifier policy가 low-trust unknown verdict를 fail-closed로 차단했는지 |

manifest/report 집계 필드:

| field | type | 의미 |
| --- | --- | --- |
| `verification_summary.by_rule_source` | `dict[str,int]` | 어떤 verifier contract provenance가 몇 번 쓰였는지 |
| `verification_summary.by_trust` | `dict[str,int]` | verifier trust 등급별 bundle 수 |
| `verification_summary.low_trust_bundles` | `int` | low-trust verifier bundle 수 |

### 5.2 `verify_pass` 판정식

후속 구현에서 `verify_pass`는 아래 식으로 고정한다.

`verify_pass = exploit_pass && guard_pass && semantic_gate_pass`

여기서 `semantic_gate_pass`는 다음 규칙을 따른다.

- known supported family:
  - `semantic_supported=true`
  - `semantic_status=aligned`
  - 이 둘을 만족해야 pass
- free-form `NAME-*` 또는 static rule이 없는 bundle:
  - `semantic_supported=true`
  - semantic signature가 non-empty
  - `semantic_status=aligned`
  - 위 세 조건을 모두 만족해야 pass
- `semantic_supported=false` 또는 `semantic_status in {unsupported, empty, contradicted}`이면 fail-closed

즉 unsupported semantic 상태에서는 exploit marker만 맞아도 최종 success가 될 수 없다.

추가 규칙:

- default policy(`policy.verifier.low_trust_unknown_policy=warn`)에서는 `verification_trust`를 `verify_pass` 계산식에 직접 곱하지 않는다.
- `verification_trust=high`는 declared static/runtime rule에 기반한 상대적으로 독립적인 verifier path를 뜻한다.
- `verification_trust=medium`는 compiler-generated bundle이 생성한 runtime rule을 verifier가 사용한 경우를 뜻한다. 이는 current lower-bound acceptance에는 쓸 수 있지만 independent verification과 동의어로 쓰면 안 된다.
- 이 기본 모드에서는 `verification_trust=low`가 reviewer/pack/promotion에서 non-promotable signal로 취급된다.
- optional strict policy(`policy.verifier.low_trust_unknown_policy=fail_closed`)에서는 unknown/open-world lane의 `verification_trust=low` verdict를 VERIFY 단계에서 즉시 fail-closed하고, `verification_policy_blocked=true`, `terminal_failure_class=low_trust_verification`를 남긴다.
- strict policy로 차단된 verdict는 registry가 다시 LLM fallback으로 덮어쓰지 않고 base verifier result를 그대로 유지한다.

### 5.3 `semantic_contract.status` 표준화

`semantic_contract.status`는 아래 enum으로 표준화한다.

| status | 의미 |
| --- | --- |
| `aligned` | semantic signature가 non-empty이고 requested family와 정렬됨 |
| `contradicted` | contradiction 또는 foreign-family semantic term이 검출됨 |
| `unsupported` | 요청 family를 검증할 신뢰 가능한 semantic basis가 없음 |
| `empty` | semantic_signature가 비어 있거나, 일부 heuristic term이 있어도 evidence quality가 insufficient라 support로 쓰기 부족한 상태 |

규칙:

- `empty`는 `aligned`가 아니다.
- `unsupported`는 “현재 시스템이 semantic truth를 만들지 못했다”는 의미다.
- `contradicted`는 reviewer/pack blocking 사유다.
- researcher evidence quality가 `insufficient`면 non-empty heuristic signature가 있어도 `aligned`로 승격하지 않고 `empty`로 정렬한다.

### 5.4 `semantic_supported` 판정 규칙

`semantic_supported=true`가 되려면 아래 둘 중 하나가 필요하다.

1. built-in semantic evaluator가 해당 family를 지원하고 실제 semantic verdict를 낼 수 있는 경우
2. runtime rule / resolved contract / semantic contract 중 하나가 non-empty semantic signature를 제공하고, 그 source가 실제로 verifier에 사용된 경우

아래 경우는 모두 `semantic_supported=false`다.

- generic unsupported fallback
- empty semantic signature
- marker-only runtime assertion만 있고 family semantics가 없는 경우
- source는 존재하지만 semantic buckets가 모두 비어 있는 경우
- source는 존재하지만 researcher evidence quality가 insufficient라 semantic support로 쓰기 어려운 경우

### 5.5 provenance 규격 추가: `fallback_class`

bundle provenance에 아래 필드를 추가한다.

| field | type | values |
| --- | --- | --- |
| `fallback_class` | `str \| null` | `family_aware`, `generic_unsupported_family`, `null` |

판정 규칙:

- SQLi/CSRF/Template Injection/Path Traversal 전용 fallback manifest면 `family_aware`
- generic reflection fallback 또는 semantic support 없는 generic fallback이면 `generic_unsupported_family`
- fallback 미사용이면 `null`

이 필드는 최소 아래 위치에 surface되어야 한다.

- `resolved_contract.provenance`
- `manifest.json` bundle provenance
- `failure_manifest.json` bundle provenance
- `generator_failures.jsonl`

추가 규칙:

- GENERATOR 이전 RESEARCH-stage terminal stop은 `generation_origin=research_short_circuit`로 surface한다.
- 이 경우 `dynamicness`는 `pre-generation fail-closed`로 분류하고, `failure.terminal_failure_class`와 함께 읽는다.

### 5.6 generic unsupported fallback 정책

generic unsupported fallback은 short-term에는 inspection-only로 유지하되,
mid-term 목표는 unsupported `NAME-*` lane의 default 경로에서 제거하는 것이다.

허용:

- workspace materialization
- Docker build/run
- PoC execution
- reviewer/ops가 inspection 가능한 `failure_manifest.json` 생성

불허:

- success `manifest.json` 생성
- `verify_pass=true`
- `promotion.eligible=true`
- official success lane 집계

추가 규칙:

- `compiler_supported=false`가 researcher/contract 단계에서 명확하면, 기본 동작은 generator 3-loop 이전의 early fail-closed여야 한다.
- generic fallback materialization은 `inspection_mode=true` 또는 equivalent debug policy가 있을 때만 허용하는 방향으로 수렴한다.
- generic fallback을 실제로 materialize하더라도, 이는 “semantic-to-code generation 성공”으로 집계하지 않는다.

이 경로의 top-level `failure_reason`은 최소 아래 둘 중 하나여야 한다.

- `semantic_support_missing`
- `generic_unsupported_fallback`

### 5.7 reviewer / pack 승격 규칙

`promotion.eligible`는 아래를 모두 만족해야 한다.

- `verify_pass=true`
- `semantic_supported=true`
- `semantic_status=aligned`
- `verification_trust != low`
- reviewer non-blocking
- semantic contradiction 없음
- `fallback_class != generic_unsupported_family`

아래 중 하나라도 참이면 `promotion.eligible=false`다.

- `semantic_supported=false`
- `semantic_status in {unsupported, empty, contradicted}`
- `verification_trust=low`
- `fallback_class=generic_unsupported_family`
- reviewer blocking
- guard mismatch

### 5.8 RESEARCH-stage taxonomy surface

pre-generation 종료 또는 degraded evidence insufficiency는 최소 다음 taxonomy를 가진다.

- `remote_evidence_missing`
- `evidence_low_relevance`
- `provider_degraded`
- `semantic_support_missing`

이 taxonomy는 최소 다음 artifact에 남아야 한다.

- `loop_state.history[].metadata`
- `performance_summary.json`
- `failure_manifest.json`

### 5.9 `semantic_profile` canonical schema

compiler-first 전환을 위해 `semantic_profile`을 researcher/generator/verifier 공통 1급 artifact로 승격한다.
현재 workspace에서는 `semantic_profile.json` artifact와 `compiler_supported`/`compiler_strategy`/`compiler_reason` mirror가 이미 추가되었고, unsupported early stop 및 Open Redirect/XSS compiler path selection이 이 verdict를 직접 소비하기 시작했다. 이번 추가 구현으로 compiler-supported free-form family의 `semantic_profile.semantic_signature`는 researcher semantic contract가 비어 있어도 shared fragment registry 또는 baseline에서 non-empty canonical signature를 backfill한다.

최소 필드는 아래와 같다.

| field | 의미 |
| --- | --- |
| `requested_name` | 사용자가 입력한 raw `vuln_name` |
| `normalized_vuln_id` | `CWE-*` 또는 `NAME-*` canonical id |
| `family` | compiler/evaluator가 공유하는 semantic family label |
| `support_level` | `builtin_supported`, `compiler_supported`, `unsupported`, `deferred` |
| `compiler_strategy` | 예: `open_redirect_reflect`, `xss_reflected`, `ssrf_loopback_fetch`, `deserialization_pickle_body` |
| `compiler_reason` | supported/unsupported/deferred의 이유 |
| `stack_profile` | language/framework/base_image/package_manager/runtime defaults |
| `scenario_shape` | route/helper endpoint/state/init 방식 |
| `semantic_signature` | `input_vector`, `sink`, `exploit_precondition` |
| `verification_contract` | success marker, flag token, output mode, assertion program |
| `derived_assertions` | runtime rule/guard/evaluator derivation에 필요한 canonical assertion set |
| `evidence_relevance` | researcher evidence relevance snapshot |

보관 규칙:

- primary artifact는 `metadata/<sid>/semantic_profile.json`
- 요약 필드는 `resolved_contract.json`, `failure_manifest.json`, `manifest.json`에도 mirror
- `NAME-*` 또는 static rule 부재 bundle에서는 `semantic_profile`이 없으면 promotion 불가
- compiler-supported family에서 researcher를 skip한 경우에도 `semantic_profile.semantic_signature`는 empty placeholder가 아니라 fragment registry 또는 baseline 기반 canonical signature여야 한다

### 5.10 `compiler_supported` 판정 규칙

`compiler_supported=true`가 되려면 아래를 모두 만족해야 한다.

1. `semantic_profile.support_level in {builtin_supported, compiler_supported}`
2. `compiler_strategy`가 비어 있지 않다.
3. `semantic_signature`가 non-empty다.
4. 선택된 stack scaffold가 존재한다.
5. runtime rule / guard / evaluator를 동일 family 기준으로 파생할 수 있다.

아래는 `compiler_supported=false` 또는 equivalent deferred 상태다.

- `semantic_supported=false`
- `compiler_strategy` 부재
- family는 식별됐지만 embedded target/sidecar가 없어 current stack에서 deterministic compile 불가
- evidence는 있으나 foreign-family contamination 때문에 compiler family를 고정할 수 없음

surface 규칙:

- `resolved_contract`, `manifest`, `failure_manifest`, `performance_summary`에 `compiler_supported`, `compiler_strategy`, `compiler_reason`를 남긴다.
- unsupported negative regression은 `semantic_supported`뿐 아니라 `compiler_supported`도 함께 surface한다.

### 5.11 compiler-first generation path

후속 구현에서 synthesis path의 기본 순서는 아래로 고정한다.

1. requirement normalization
2. researcher가 `semantic_profile`과 `verification_contract`를 생성
3. generator가 `compiler_supported`를 먼저 확인
4. supported면 stack scaffold + vuln fragment를 deterministic compile
5. compile 결과에서 runtime rule / guard / evaluator를 파생
6. 필요한 경우에만 LLM refinement를 optional step으로 사용

중요 규칙:

- LLM은 primary generator가 아니라 optional refiner다.
- template mode는 legacy/compatibility path로 남길 수 있지만, compiler-covered family의 기본 경로가 되어서는 안 된다.
- runtime template clone은 compiler-covered family에서는 success provenance로 집계하지 않는다.

### 5.12 scaffold / fragment 기반 materialization 규칙

template dependence reduction의 공식 구현 단위는 “family template”가 아니라 아래 두 레이어다.

- stack scaffold
  - 예: `python/flask` 공통 Dockerfile, requirements baseline, app bootstrap, health route, init hook
- vuln fragment
  - family별 route/sink/helper endpoint/PoC/init snippet

규칙:

- scaffold는 소수의 stack별 공통 자산만 유지한다.
- vuln fragment는 semantic family별 최소 코드 단위만 가진다.
- full vulnerable workspace copy는 regression fixture 또는 legacy template mode에 한정한다.
- researcher의 runtime template clone은 compiler fragment가 없는 family의 temporary compatibility path로만 인정한다.

### 5.13 runtime rule / guard / evaluator convergence 규칙

runtime rule, guard spec, built-in evaluator는 동일 `semantic_profile`에서 파생해야 한다.
marker-only runtime rule은 compiler-first family에서는 충분하지 않다.

최소 요구:

- runtime rule은 `poc_contains`만이 아니라 service-side semantic assertions를 포함한다.
- guard spec은 `semantic_signature`와 `compiler_strategy`를 반영해 generator assertions를 만든다.
- built-in evaluator support 범위는 compiler-supported family와 가능한 한 일치해야 한다.
- `verify_pass=true`와 `promotion.eligible=true`는 `fallback_class=null` 또는 `family_aware`인 경우만 generalization-positive evidence로 집계한다.

### 5.14 semantic evidence scope 규칙

semantic gate가 참조하는 positive evidence scope는 기본적으로 service-side artifact로 제한한다.

허용:

- `service_main` role 파일
- service route/helper/init 모듈 등 실제 서버 동작을 구성하는 service-side 코드
- compiler가 생성한 family-specific helper endpoint / sink / state init 코드

불허:

- `poc.py` 또는 기타 attacker-side exploit script
- `README.md`, 설명 문서, researcher prose
- failure context, hint payload, run log string 자체
- success marker나 payload literal이 우연히 포함된 helper text

규칙:

- semantic_supported / semantic_pass / semantic_status는 기본적으로 service-side artifact만으로 판정한다.
- PoC와 README는 exploit marker 검증이나 debugging evidence로는 사용할 수 있어도 semantic alignment의 positive 근거로 계산하지 않는다.
- built-in evaluator와 guard engine의 workspace scan은 service role / service path 중심으로 수렴해야 하며, `poc_entry`와 문서 파일은 기본 제외 대상이다.
- 이 규칙이 잠기기 전까지 compiler-first positive evidence는 보수적으로 해석한다. PoC payload나 README 문구가 semantic pass를 도와주는 상태는 generalization success로 집계하지 않는다.

## 6. 통합 실행 계획

### Phase 0. Current Truth & Evidence Integrity 고정

목표:

- current workspace truth와 historical snapshot을 분리한다.
- 문서가 raw SID에 과도하게 의존하지 않도록 evidence protocol을 고정한다.

작업:

1. 이 문서 구조를 current truth 기준으로 유지한다.
2. future update부터 각 row에 `evidence_class`, `observed_at`, `command`, `provider_condition`, `generation_origin`, `dynamicness`를 강제한다.
3. historical snapshot은 별도 class로만 기록한다.
4. same effective scenario surface -> same SID -> rerun overwrite 구조를 문서 운영 규칙으로 고정한다.

완료 기준:

- 문서의 baseline이 current rerun과 historical claim을 혼동하지 않는다.
- raw SID만으로 immutable evidence인 것처럼 서술하지 않는다.

### Phase 0.5. test-first P0 규격 잠금

목표:

- unsupported free-form false positive를 먼저 regression test로 고정한다.

작업:

1. unit/regression test를 먼저 추가한다.
2. 첫 failing regression은 아래 두 케이스로 고정한다.
   - `vuln_name: LDAP Injection`
   - 또 다른 unsupported `NAME-*` family fixture 1개
3. 기대값은 아래로 고정한다.
   - `run_passed`는 true일 수 있음
   - `semantic_supported=false`
   - `semantic_status in {unsupported, empty}`
   - `verify_pass=false`
   - `promotion.eligible=false`
   - `failure_manifest.json` 생성
   - `fallback_class=generic_unsupported_family`
4. official negative regression을 E2E로 편입하려면 `tests/e2e/run_case.py`가 non-zero pipeline exit와 `failure_manifest.json`을 읽을 수 있도록 먼저 보강해야 한다.
5. synthetic unknown regression도 재정의한다.
   - `CWE-9999`는 “pass 여부” 자체보다 semantic support 없는 상태에서 fail-closed되는지 검증하는 case로 재설계한다.

완료 기준:

- unsupported free-form lane false positive를 deterministic regression으로 재현할 수 있다.
- 구현 전에 기대 behavior가 테스트로 고정된다.

### Phase 1. unsupported semantic fail-closed 구현

목표:

- generic unsupported fallback이 inspection-only artifact는 만들되 success artifact로 승격되지 않도록 한다.

작업:

1. verifier result schema에 `semantic_supported`, `semantic_source`, `semantic_status`를 추가한다.
2. `verify_pass = exploit_pass && guard_pass && semantic_gate_pass`를 실제 코드에 반영한다.
3. free-form `NAME-*` 또는 static rule 부재 bundle에서는 non-empty aligned semantics 없으면 fail-closed한다.
4. `semantic_contract.status`를 `aligned|contradicted|unsupported|empty`로 표준화한다.
5. reviewer가 unsupported semantic을 blocking 또는 promotion-blocking issue로 surface하도록 정렬한다.
6. pack이 generic unsupported fallback success를 `manifest.json`으로 승격하지 못하도록 수정한다.
7. `allow_intentional_vuln=true`인 failure run이 `manifest.json`을 남기는 현재 동작도 정리한다. 최소 filename과 top-level status semantics가 일치해야 한다.

완료 기준:

- LDAP Injection 같은 unsupported free-form lane은 success manifest를 만들지 못한다.
- exploit marker-only success가 최종 verify/promotion success가 되지 않는다.

### Phase 2. degraded provenance와 failure-path truth 보강

목표:

- failure artifact가 provider health와 unsupported semantic 사유를 구조적으로 노출한다.

작업:

1. provenance에 `fallback_class`를 추가한다.
2. `failure_manifest.json`에 `failure_reason`, `semantic_supported`, `semantic_status`, `semantic_source`를 추가한다.
3. `generator_failures.jsonl`, `loop_state`, `performance_summary`에 RESEARCH-stage taxonomy를 전파한다.
4. `llm_failure_class`와 `provider_condition`을 pre-generation 종료 사유와 연결한다.
5. `manifest.json`과 `failure_manifest.json`의 filename semantics를 `pipeline_result`와 일치시키고, `allow_intentional_vuln`는 REVIEW bypass에만 한정한다.

완료 기준:

- failure run에서도 왜 generation/verification/promotion이 막혔는지 top-level에서 바로 읽힌다.
- generic unsupported fallback은 provenance와 failure reason 둘 다 남긴다.

### Phase 3. `semantic_profile` / compiler contract 고정

목표:

- free-form `vuln_name only` 요청을 semantic inference와 code generation 사이에서 잃지 않도록 canonical compiler contract를 고정한다.

current status:

- `semantic_profile.json` artifact는 1차 구현 완료
- `resolved_contract`, `manifest`, `failure_manifest`, `performance_summary`의 compiler verdict surface도 1차 구현 완료
- real free-form `NAME-*` + `support_level=unsupported`는 현재 RESEARCH-stage terminal stop까지 연결 완료
- 남은 핵심은 이 verdict를 compiler-first generator path와 acceptance gating에 더 넓게 연결하는 것이다

작업:

1. `semantic_profile.json` artifact를 추가한다.
2. 최소 필드는 `requested_name`, `normalized_vuln_id`, `family`, `support_level`, `compiler_strategy`, `compiler_reason`, `stack_profile`, `scenario_shape`, `semantic_signature`, `verification_contract`, `derived_assertions`로 고정한다.
3. researcher가 `semantic_supported`와 별개로 `compiler_supported` / `compiler_reason`를 계산하도록 한다.
4. `resolved_contract.json`, `manifest.json`, `failure_manifest.json`, `performance_summary.json`에 compiler contract 요약을 mirror한다.
5. acceptance와 lane 표는 `semantic_supported`만이 아니라 `compiler_supported`를 함께 기록하도록 바꾼다.
6. semantic evidence scope를 service-side artifact 기준으로 잠근다. verifier/guard의 positive semantic 판정에서 `poc.py`, README, run log 문자열은 제외한다.

완료 기준:

- 모든 `NAME-*` 또는 static rule 부재 bundle이 explicit `compiler_supported` verdict를 가진다.
- unsupported semantic과 unsupported compiler를 구분해 설명할 수 있다.
- semantic pass가 attacker-side payload나 documentation text에 의해 과대판정되지 않는다.

### Phase 4. compiler-first dynamic generation P0 구현

목표:

- synthesis 핵심 경로를 template clone이 아니라 scaffold + vuln fragment compile로 전환한다.

작업:

1. 기존 `agents/generator/compiler.py`와 추출된 stack scaffold registry(`agents/generator/flask_fragment_registry.py`)를 확장한다.
2. 첫 stack scaffold는 `python/flask`를 기준으로 설계한다.
3. Tier A family fragment를 먼저 구현한다.
   - `template_injection_render`
   - `path_traversal_file_read`
4. Tier B family fragment를 이어서 구현한다.
   - `sqli_string_concat`
   - `csrf_state_change`
5. Tier C family는 분리된 sub-phase로 구현하거나 deferred truth를 명시한다.
   - `command_injection_shell`
   - `code_injection_eval`
6. compiler-covered family의 synthesis mode 기본 경로는 `compiler -> optional LLM refinement`로 고정한다.
7. compiler-covered family에서는 runtime template clone을 success provenance로 집계하지 않는다.
8. built-in template는 regression fixture/legacy mode 자산으로만 유지한다.
9. compiler-first positive acceptance는 service-side semantic evidence 규칙이 먼저 적용된 lane에서만 집계한다.

완료 기준:

- 최소 1개의 real free-form positive family가 `compiler_supported=true`, `fallback_class=null`, `promotion.eligible=true`로 닫힌다.
- XSS/SSRF/Insecure Deserialization/Open Redirect는 generic unsupported fallback에 의존하지 않는 current truth를 확보한다.
- 완료: Template Injection과 Path Traversal 모두 compiler fragment로 current truth를 닫았다.

### Phase 5. runtime rule / evaluator convergence와 known lane 안정화

목표:

- compiler output, runtime rule, guard spec, evaluator가 같은 semantic basis를 보도록 정렬하고, late-fail cost를 줄인다.

작업:

1. runtime rule은 `semantic_profile.scenario_shape` 기반 service-side assertions를 자동 포함하도록 바꾼다.
2. built-in evaluator support 범위를 compiler-supported family와 최대한 일치시킨다.
3. XSS의 기존 `verify_pass=true` / `promotion.eligible=false` split은 해소되었으므로, 이후 family 확장에서도 compiler-covered lane과 legacy lane을 명확히 분리한다.
4. unsupported `NAME-*` lane은 default로 early fail-closed하여 3-loop 소모를 줄인다.
5. performance summary는 known degraded lane / compiler-first lane / unsupported negative lane을 separate metric으로 집계한다.

완료 기준:

- compiler-supported family는 marker-only rule이 아니라 service semantics까지 포함한 verify/promotion verdict를 가진다.
- unsupported negative lane은 기본적으로 pre-generation 또는 single-loop 수준에서 종료한다.

### Phase 6. official lane 재분류와 real free-form evidence 확장

목표:

- current truth, compiler coverage, acceptance를 하나의 표로 정렬하고, free-form positive evidence를 공식화한다.

작업:

1. official lane을 아래 class로 재분류한다.
   - `trusted dynamic`
   - `compiler-first`
   - `template-assisted`
   - `deterministic fallback dependent`
   - `synthetic regression`
   - `unsupported free-form negative regression`
2. 완료: `CWE-9999` live lane은 manifest/E2E summary에서 `synthetic regression`과 `counts_as_generalization=false`로 고정된다.
3. LDAP Injection negative regression과 Open Redirect positive free-form evidence를 공식 acceptance에 편입한다.
4. compiler-first positive free-form case 최소 1개를 official acceptance에 편입한다.
   - current workspace에서는 `Open Redirect`, `Template Injection`, 그리고 canonical alias `Server Side Template Injection`이 이 조건을 충족한다.
5. 완료: Path Traversal dedicated official E2E를 추가했고, current workspace rerun에서 compiler-first green을 확인했다.
6. broader family roadmap를 phase-out 기준으로 문서화한다.
   - Tier A: fragment registry / scaffold compose 구조화
   - Tier B: second scaffold / richer runtime model
  - Tier C: LDAP Injection

완료 기준:

- official lane 표가 current code truth와 compiler coverage를 동시에 반영한다.
- negative free-form regression과 positive free-form evidence가 분리된다.
- free-form generalization success 주장이 synthetic unknown lane 또는 template clone에 의존하지 않는다.

## 7. Acceptance Matrix

| 구분 | corrected acceptance |
| --- | --- |
| Unit tests | `python -m pytest -q tests` 기준 최소 `295 passed, 32 skipped` 유지 또는 상향 |
| E2E truth | 기본 pytest pass와 분리된 공식 live E2E set 유지 |
| Test completeness | official source-of-truth에는 최소 1개의 multi-vuln positive case, 최소 1개의 fixture-backed trusted dynamic case, 최소 1개의 sidecar-backed positive runtime case가 포함되어야 하며, compiler-first repeatability gate는 remote provider 없이도 재현 가능해야 한다 |
| Evidence integrity | lane 표는 `provider_condition`, `generation_origin`, `dynamicness`, `evidence_class`, `observed_at`, `command`, `sid`를 함께 기록한다. official harness는 runtime asset seed manifest를 통해 rerun마다 `runtime_rules/`, `runtime_templates/`를 purge/restore하고, expectation에서도 `generation_origin`, `dynamicness_verdict`를 함께 검증한다 |
| SID handling | raw SID를 immutable evidence처럼 서술하지 않음 |
| Verdict truth | `verify_pass = exploit_pass && guard_pass && semantic_gate_pass` |
| Semantic gating | static rule 부재 또는 free-form `NAME-*`에서 `semantic_supported=false`면 fail-closed |
| Semantic schema | `semantic_supported`, `semantic_source`, `semantic_status`가 surface됨 |
| Failure-path provenance | failure artifact에도 `llm_stub_used`, `fallback_used`, `fallback_class`, `family_override_applied`, `provider_health_state`, 그리고 필요한 경우 `generation_origin=research_short_circuit`가 남음 |
| Provider health rollup | `provider_health_state`는 bundle-level `search_health.json`과 nested `failed_bundles[].terminal_failure_class`까지 반영해야 하며, `semantic_support_missing` 같은 semantic fail-closed는 provider degradation으로 오인되면 안 됨 |
| Failure artifact availability | review/pack block이어도 inspection 가능한 `failure_manifest.json`이 남음 |
| Runtime asset freshness | official harness rerun은 seeded runtime asset만 restore하고 previous generated runtime rule/template carry-over를 허용하지 않아야 한다. raw runner는 최소 tracked generated runtime asset cleanup을 수행해야 한다 |
| Manifest semantics | success run은 `manifest.json`, failure run은 `failure_manifest.json`만 남도록 정렬되어야 한다. filename alone으로 끝내지 않고 `pipeline_result`와 `promotion.eligible`를 함께 본다 |
| Researcher normalization | stub researcher report에도 canonical `vuln_id` 기록 |
| Semantic profile | `NAME-*` 또는 static rule 부재 bundle에는 canonical `semantic_profile` artifact가 존재해야 함. compiler-supported free-form family는 researcher skip path에서도 non-empty `semantic_signature`를 가져야 함 |
| Compiler contract | `compiler_supported`, `compiler_strategy`, `compiler_reason`가 `resolved_contract`와 top-level manifest/failure artifact에 surface됨. requirement가 compiler를 명시적으로 끄면 planner/researcher/runner lower bound도 같이 remote-required 방향으로 내려가야 함 |
| Lower-bound surface | `family_non_remote_available`, `effective_non_remote_available`, `compiler_path_enabled` 또는 동등한 `lower_bound` summary가 contract/manifest/performance에서 읽혀야 함 |
| Executor feasibility | `executor_feasibility_status` 또는 동등한 summary가 manifest/performance에서 읽혀야 하고, external DB requirement mismatch는 success provenance보다 먼저 fail-fast되어야 함 |
| Runtime env surface | sidecar/external DB bundle은 `service_env` 또는 동등한 runtime env contract를 surface해야 하고, executor는 이를 실제 service container env로 주입해야 함 |
| Semantic evidence scope | verifier semantic pass는 service-side artifact 기준으로 계산하고 `poc.py`/README/run log 문자열은 positive semantic 근거로 쓰지 않음 |
| Free-form rule loading | `NAME-*` runtime rule writer/loader round-trip 성공 |
| Role normalization | generated manifest canonical role 100% |
| Generic unsupported fallback | unsupported free-form `NAME-*` negative lane에서는 promotion 금지와 `failure_manifest.json`이 current truth다. current workspace 기준 LDAP Injection이 대표 negative regression이다 |
| Compiler-first generation | compiler-covered family는 scaffold + vuln fragment path를 primary generation path로 사용하고, runtime template clone은 legacy/compatibility path로만 집계 |
| Compiler provenance detail | registry-backed compiler bundle은 가능한 경우 `stack_scaffold_id`, `fragment_id`, `compose_mode` 같은 scaffold/fragment provenance를 metadata에 남겨야 함 |
| Scaffold asset provenance | compiler scaffold는 가능하면 별도 asset catalog version(`stack_scaffold_version`)까지 metadata에 남겨야 함 |
| Representative registry acceptance | 최소 representative compiler-first lane에서는 official expectation이 `compiler_family`, `stack_scaffold_id`, `stack_scaffold_version`, `fragment_id`, `compose_mode`까지 직접 검증해야 함 |
| Multi-bundle top-level rollup | multi-bundle manifest도 top-level `generation_origin`, `dynamicness_verdict`, `verification_rule_source`, `verification_trust`를 비우지 않아야 하며, uniform하면 같은 값, diverged면 `mixed` sentinel 또는 동등한 rollup을 surface해야 함 |
| Template dependence reduction | compiler-covered family의 success claim은 full template copy 또는 runtime template clone에 의존하지 않아야 함 |
| Reviewer / Pack gating | `promotion.eligible`는 bundle 종류와 무관하게 evaluator가 explicit `semantic_supported=false` 또는 `semantic_status in {unsupported, empty, contradicted}`를 surface하면 차단되어야 함 |
| Official lanes | 코드상 official live set은 SQLi/SQLi sidecar template/SQLi sidecar compiler/SQLi sidecar compiler custom env/CSRF/Command Injection/Code Injection/Code Injection alias/SSRF/Template Injection/Template Injection alias/Template Injection paraphrase/Template Injection reordered/Open Redirect/Open Redirect alias/Open Redirect paraphrase/Open Redirect reordered/Path Traversal/XSS/Deserialization/XXE/multi-name-only-supported/multi-name-mixed-partial/trusted-dynamic-sqli/LDAP negative/Foobar negative + unknown synthesis/live + unknown live strict fail-closed다. current rerun 기준 official E2E는 `30 passed, 2 skipped`이며, skip 2개는 repeatability gate다. sidecar positive lane은 template-assisted와 compiler-first 두 provenance에 더해 custom runtime env compiler-first evidence까지 존재하고, unsupported negative lane도 whitespace-bearing phrase뿐 아니라 single-token custom name까지 source-of-truth에 편입되었다. 다만 SQLi 외 richer bridge/sidecar family compiler lane은 아직 없다 |
| Synthetic unknown handling | `CWE-9999`는 regression lane이지 generalization lane이 아니며, manifest/E2E summary에 `generalization_class=synthetic_regression`, `counts_as_generalization=false`가 surface된다 |
| Free-form negative regression | `LDAP Injection`과 다른 unsupported `NAME-*` lane은 degraded/stub path에서 false-positive pass가 재현되지 않아야 함 |
| Free-form positive evidence | compiler-first 또는 equivalent non-template path로 만든 real free-form positive case 최소 1개. 최소 조건은 `generation_origin=compiler_generated`, `dynamicness_verdict=compiler-first`, `fallback_class!=generic_unsupported_family`, `promotion.eligible=true`다. `compiler_supported=true`만으로는 충분하지 않다. representative lane에서는 registry-backed scaffold/fragment provenance까지 같이 보는 편이 더 안전하다 |
| Verifier trust semantics | static rule이 없는 compiler-generated lane은 current truth에서 `compiler_runtime_rule/medium`으로 표기되어야 하며, `declared_rule/high`와 혼동되면 안 된다 |
| Performance | known degraded lane, compiler-first lane, unsupported negative lane 수치를 provenance-aware 분류와 함께 보고, quality defect를 덮는 성공 지표로 사용하지 않음 |

## 8. 이번 문서 갱신의 실측 근거

### 8.1 실행한 command

- `python -m pytest -q tests`
- `VULD_RUN_E2E=1 python -m pytest -q tests/e2e/test_cases.py -rs`
- `python -m pytest -q tests/test_researcher_multibundle_continue.py tests/test_run_pipeline_failure_resolution.py tests/test_pack_promotion.py`
- `VULD_RUN_E2E=1 python -m pytest -q tests/e2e/test_cases.py -k 'multi_name_only_supported_case or multi_name_mixed_partial_case or ldap_injection_negative_case'`
- `VULD_RUN_E2E=1 python -m pytest -q tests/e2e/test_cases.py -k 'open_redirect_name_only_case or ldap_injection_negative_case or multi_name_only_supported_case' -rs`
- `python - <<'PY' ... normalize_requirement({'vuln_ids':['Custom Weird Vuln','Open Redirect'],'multi_vuln':True}, multi_vuln_opt_in=True) ... normalize_requirement({'vuln_name':'unsafe template deserialization'}) ... PY`
- `python orchestrator/run_pipeline.py --sid sid-14513fdcdee9 --mode deterministic`
- `python -m pytest -q tests/test_requirement_policy_defaults.py tests/test_flask_fragment_registry.py tests/test_compiler_registry.py tests/test_generator_template_planner.py`
- `python -m pytest -q tests/test_requirement_policy_defaults.py`
- `python -m pytest -q tests/test_repeatability_gate.py`
- `python -m pytest -q tests/test_llm_provider_fixture.py`
- `python -m pytest -q tests/test_requirement_policy_defaults.py tests/test_run_pipeline_failure_resolution.py tests/test_flask_fragment_registry.py tests/test_compiler_registry.py tests/test_generator_template_planner.py`
- `python -m pytest -q tests/test_scaffold_registry.py tests/test_compiler_registry.py tests/test_requirement_policy_defaults.py tests/test_run_pipeline_failure_resolution.py`
- `python -m pytest -q tests`
- `VULD_RUN_E2E=1 python -m pytest -q tests/e2e/test_cases.py -k 'multi_name_only_supported_case or template_injection_name_only_repeatability_gate' -rs`
- `VULD_RUN_E2E=1 VULD_RUN_E2E_REPEAT=1 python -m pytest -q tests/e2e/test_cases.py -k template_injection_name_only_repeatability_gate -rs`
- `python -m pytest -q tests/test_contract_resolution.py tests/test_pack_promotion.py tests/test_rule_based_semantic_contract.py`
- `python -m pytest -q tests/test_flask_fragment_registry.py tests/test_compiler_registry.py tests/test_vuln_semantics.py`
- `VULD_RUN_E2E=1 python -m pytest -q tests/e2e/test_cases.py -rs`
- `VULD_RUN_E2E=1 python -m pytest -q tests/e2e/test_cases.py -k trusted_dynamic_sqli_case -rs`
- `VULD_RUN_E2E=1 python -m pytest -q tests/e2e/test_cases.py -k command_injection_name_only_case -rs`
- `python tests/e2e/run_case.py --case tests/e2e/cases/command-injection-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-cmdi-review`
- `python tests/e2e/run_case.py --case tests/e2e/cases/template-injection-alias-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-review/template-alias`
- `python tests/e2e/run_case.py --case tests/e2e/cases/open-redirect-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-review/open-redirect-postfix2`
- `python tests/e2e/run_case.py --case tests/e2e/cases/open-redirect-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-review/open-redirect-scaffold-asset`
- `python tests/e2e/run_case.py --case /tmp/vuld-review/open-redirect-alias-case --mode deterministic --no-snapshot --output-dir /tmp/vuld-review/open-redirect-alias-out`
- `python tests/e2e/run_case.py --case tests/e2e/cases/open-redirect-alias-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-review/open-redirect-alias-official`
- `python tests/e2e/run_case.py --case tests/e2e/cases/code-injection-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-review-code-injection`
- `python tests/e2e/run_case.py --case tests/e2e/cases/code-injection-alias-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-review-code-injection-alias`
- `VUL_WEB_SEARCH_PROVIDER=none python tests/e2e/run_case.py --case tests/e2e/cases/cwe-unknown-basic --expectations tests/e2e/cases/cwe-unknown-basic/expectations.no-remote.json --mode deterministic --no-snapshot --output-dir /tmp/vuld-review/unknown-none-postfix`
- `python -m pytest -q tests`
- `python -m pytest -q tests/test_compiler_registry.py tests/test_vuln_semantics.py tests/test_contract_resolution.py tests/test_rule_based_semantic_contract.py tests/test_pack_promotion.py`
- `python -m pytest -q tests/test_vuln_semantics.py tests/test_contract_resolution.py tests/test_rule_based_semantic_contract.py tests/test_pack_promotion.py`
- `python -m pytest -q tests/test_contract_resolution.py tests/test_researcher_guard_normalization.py tests/test_synthesis_fallback_poc.py tests/test_pack_promotion.py tests/test_run_pipeline_failure_resolution.py`
- `python tests/e2e/run_case.py --case tests/e2e/cases/sqli-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-review-sqli-20260308-3`
- `python tests/e2e/run_case.py --case tests/e2e/cases/csrf-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-review-csrf-20260308-3`
- `python tests/e2e/run_case.py --case tests/e2e/cases/template-injection-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-review-template`
- `python tests/e2e/run_case.py --case tests/e2e/cases/template-injection-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-review-template-injection-20260308-4`
- `python tests/e2e/run_case.py --case tests/e2e/cases/path-traversal-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-review-path-traversal-20260308`
- `python tests/e2e/run_case.py --case tests/e2e/cases/xss-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-xss-e2e-compiler`
- `python tests/e2e/run_case.py --case tests/e2e/cases/ssrf-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-ssrf-e2e-compiler-4`
- `python tests/e2e/run_case.py --case tests/e2e/cases/deserialization-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-deser-e2e-compiler-4`
- `python tests/e2e/run_case.py --case tests/e2e/cases/open-redirect-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-open-redirect-e2e-compiler-keep`
- `python tests/e2e/run_case.py --case tests/e2e/cases/open-redirect-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-review-open-redirect-20260308-4`
- `python tests/e2e/run_case.py --case tests/e2e/cases/trusted-dynamic-sqli --mode deterministic --no-snapshot --output-dir /tmp/vuld-trusted-dynamic-sqli`
- `python -m pytest -q tests/test_run_pipeline_failure_resolution.py`
- `python -m pytest -q tests/test_pack_promotion.py tests/test_contract_resolution.py tests/test_runtime_rules.py`
- `python -m pytest -q tests/test_requirement_policy_defaults.py tests/test_pack_promotion.py tests/test_flask_fragment_registry.py`
- `VULD_RUN_E2E=1 python -m pytest -q tests/e2e/test_cases.py -k 'cwe89_basic_case or template_injection_name_only_case or ldap_injection_negative_case or unknown_cwe_synthesis_case' -rs`
- `VULD_RUN_E2E=1 python -m pytest -q tests/e2e/test_cases.py -k 'cwe89_basic_case or template_injection_name_only_case or open_redirect_name_only_case' -rs`
- `python tests/e2e/run_case.py --case tests/e2e/cases/template-injection-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-review-template-20260308`
- `python tests/e2e/run_case.py --case tests/e2e/cases/ldap-injection-negative --mode deterministic --no-snapshot --output-dir /tmp/vuld-review-ldap-20260308`
- `VUL_WEB_SEARCH_PROVIDER=none python tests/e2e/run_case.py --case tests/e2e/cases/cwe-unknown-basic --expectations tests/e2e/cases/cwe-unknown-basic/expectations.no-remote.json --mode deterministic --no-snapshot --output-dir /tmp/vuld-review-unknown-none-20260308`
- `python tests/e2e/run_case.py --case tests/e2e/cases/cwe-unknown-basic --mode deterministic --no-snapshot --output-dir /tmp/vuld-review-unknown-live-20260308`
- `python tests/e2e/run_case.py --case tests/e2e/cases/ldap-injection-negative --mode deterministic --no-snapshot --output-dir /tmp/vuld-review-ldap-negative-20260308-4`
- `python tests/e2e/run_case.py --case tests/e2e/cases/cwe-unknown-basic --mode deterministic --no-snapshot --output-dir /tmp/vuld-review-unknown-20260308-2`
- `python tests/e2e/run_case.py --case tests/e2e/cases/open-redirect-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-e2e-open-redirect-postfix`
- `python tests/e2e/run_case.py --case tests/e2e/cases/template-injection-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-e2e-template-injection-postfix`
- `python tests/e2e/run_case.py --case tests/e2e/cases/xss-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-e2e-xss-postfix`
- `python tests/e2e/run_case.py --case tests/e2e/cases/deserialization-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-e2e-deser-postfix`
- `python tests/e2e/run_case.py --case tests/e2e/cases/cwe-unknown-basic --mode deterministic --no-snapshot --output-dir /tmp/vuld-e2e-unknown-postfix`
- `python tests/e2e/run_case.py --case tests/e2e/cases/ldap-injection-negative --mode deterministic --no-snapshot --output-dir /tmp/vuld-e2e-ldap-negative-postfix`
- `python tests/e2e/run_case.py --case tests/e2e/cases/open-redirect-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-e2e-open-redirect-registry`
- `python tests/e2e/run_case.py --case tests/e2e/cases/template-injection-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-e2e-template-registry`
- `python tests/e2e/run_case.py --case tests/e2e/cases/xss-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-e2e-xss-registry`
- `python tests/e2e/run_case.py --case tests/e2e/cases/ldap-injection-negative --mode deterministic --no-snapshot --output-dir /tmp/vuld-e2e-ldap-registry`
- `python tests/e2e/run_case.py --case tests/e2e/cases/sqli-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-e2e-sqli-registry2`
- `python tests/e2e/run_case.py --case tests/e2e/cases/csrf-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-e2e-csrf-registry2`
- `python tests/e2e/run_case.py --case tests/e2e/cases/path-traversal-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-e2e-path-registry2`
- `python tests/e2e/run_case.py --case tests/e2e/cases/ssrf-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-e2e-ssrf-registry2`
- `python tests/e2e/run_case.py --case tests/e2e/cases/deserialization-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-e2e-deser-registry2`
- `python tests/e2e/run_case.py --case tests/e2e/cases/open-redirect-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-e2e-open-redirect-registry2`
- `python tests/e2e/run_case.py --case tests/e2e/cases/template-injection-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-e2e-template-registry2`
- `python tests/e2e/run_case.py --case tests/e2e/cases/xss-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld-e2e-xss-registry2`
- `python tests/e2e/run_case.py --case tests/e2e/cases/ldap-injection-negative --mode deterministic --no-snapshot --output-dir /tmp/vuld-e2e-ldap-registry2`
- `python -m pytest -q tests/test_llm_provider_fixture.py tests/test_requirement_policy_defaults.py tests/test_run_pipeline_failure_resolution.py tests/test_executor_poc_exec.py`
- `python tests/e2e/run_case.py --case /tmp/vuld-sidecar-case2 --mode deterministic --no-snapshot --output-dir /tmp/vuld-sidecar-out5`
- `python - <<'PY' ... normalize_requirement({'vuln_name':'Template Injection','compiler':{'enabled':False}}) ... _can_skip_researcher(...) ... _terminal_executor_precheck(...) ... PY`
- `python - <<'PY' ... normalize_requirement({'vuln_ids':['Foobar']}) ... normalize_requirement({'vuln_id':'Foobar'}) ... normalize_requirement({'vuln_name':'Foobar'}) ... PY`
- `VUL_WEB_SEARCH_PROVIDER=none python orchestrator/run_pipeline.py --sid <NAME-FOOBAR-SID> --mode deterministic`

### 8.2 이번 문서에서 current truth로 채택한 핵심 관찰

- 공식 E2E full rerun은 이번 추가 갱신 이후 `30 passed, 2 skipped`였고, 기존 `command-injection-name-only`, `code-injection-name-only`, `code-injection-alias-name-only`, `template-injection-alias-name-only`, `template-injection-reordered-name-only`, `open-redirect-alias-name-only`, `open-redirect-reordered-name-only`에 더해 새 `template-injection-paraphrase-name-only`, `open-redirect-paraphrase-name-only`, `xxe-name-only`, `multi-name-only-supported`, `multi-name-mixed-partial`, `trusted-dynamic-sqli`, `sqli-sidecar-template`, `sqli-sidecar-compiler`, `sqli-sidecar-compiler-custom-env`, `foobar-name-only-negative` case도 green이었다.
- 추가로 latest targeted E2E rerun에서는 `open_redirect_name_only_case`, `ldap_injection_negative_case`, `multi_name_only_supported_case`가 `3 passed, 25 deselected`로 재확인되었다.
- 기본 테스트 스위트는 latest rerun 기준 `295 passed, 32 skipped`까지 상향되었다.
- 새 official multi-vuln case는 `Template Injection + Open Redirect` 두 free-form `vuln_ids`를 한 SID에서 `compiler_generated`, `compiler-first`, `real_free_form_positive` 2-bundle success로 닫았다. current manifest는 `bundle_count=2`, `positive_generalization_bundles=2`, `supported_bundles=2`, `total_duration_s≈8.773s`였다.
- 새 fixture-backed trusted-dynamic case는 SQLi를 `generation_origin=llm_manifest`, `dynamicness_verdict=trusted dynamic`, `verification_rule_source=declared_rule`, `verification_trust=high`, `provider_health_state=llm_fixture`, `llm_fixture_used=true`로 닫았다. current manifest는 `sid-b36ff41a638a`, `promotion.eligible=true`, `total_duration_s≈8.665s`였다.
- 같은 latest rerun에서 static rule이 없는 compiler-generated family는 `verification_rule_source=compiler_runtime_rule`, `verification_trust=medium`으로 surface되었다. 즉 current official evidence는 compiler-coupled verification과 declared independent rule을 구분한다.
- Template Injection repeatability gate는 이번 수정으로 더 이상 Tavily key를 요구하지 않으며, latest rerun 기준 `3/3 passed`였다.
- repeatability harness는 이번 턴에서 `pipeline_returncode`를 summary/expectation validation에 전달하도록 수정되어, gate가 harness 누락 필드 때문에 false fail하지 않는다.
- `Server Side Template Injection`은 이제 canonical `NAME-TEMPLATE-INJECTION`으로 normalize되어 same compiler-first positive lane으로 닫힌다. 같은 canonical requirement로 collapse되므로 original Template Injection case와 SID(`sid-60ae4e071b9f`)도 공유한다.
- ad-hoc `Unvalidated Redirect` rerun과 official `open-redirect-alias-name-only` case도 canonical `NAME-OPEN-REDIRECT`로 collapse되어 same Open Redirect compiler-first lane으로 닫혔다.
- `Template rendering vulnerability`, `External redirect vulnerability`도 shared vuln family catalog의 exact alias layer를 통해 각각 canonical `NAME-TEMPLATE-INJECTION`, `NAME-OPEN-REDIRECT`로 normalize되어 official E2E positive lane으로 닫혔다. 즉 current source-of-truth에는 exact canonical phrase와 alias, reordered phrase뿐 아니라 catalog-backed paraphrase alias도 포함된다.
- single-token custom free-form label(`Foobar`)도 latest rerun에서 canonical `NAME-FOOBAR`로 normalize되었고, no-remote pipeline rerun 기준 `failure.stage=RESEARCH`, `terminal_failure_class=semantic_support_missing`, `provider_health_state=not_probed`로 닫혔다. 즉 unsupported negative lane taxonomy가 whitespace-bearing phrase에만 국한되지 않는다.
- 추가로 `foobar-name-only-negative` official E2E도 current workspace에서 green이며, `name_resolution.resolved_vuln_id=NAME-FOOBAR`, `pipeline_result=failure`, `failure.stage=RESEARCH`, `failure.terminal_failure_class=semantic_support_missing`, `generalization_class=unsupported_free_form_negative`를 직접 기대치로 고정한다.
- `XML External Entity`는 이번 추가 구현으로 `NAME-XXE` + `compiler_strategy=xxe_xml_entity_resolve`로 승격되었고, official `xxe-name-only` case는 latest rerun 기준 `generation_origin=compiler_generated`, `dynamicness_verdict=compiler-first`, `verification_rule_source=compiler_runtime_rule`, `verification_trust=medium`, `generalization_class=real_free_form_positive`, `counts_as_generalization=true`, `total_duration_s≈6.636s`로 닫혔다.
- latest targeted rerun 기준 `xxe_name_only_case`, `path_traversal_name_only_case`, `multi_name_only_supported_case`도 `3 passed, 27 deselected`로 재확인되었다.
- same change set에서 `Injection in Jinja template`, `Redirect open vulnerability`, `Injection in shell command`도 stopword-trimmed exact-content-token fallback을 통해 canonical supported family로 normalize된다. 즉 current robustness는 token subset first-fit가 아니라 curated exact-content-token layer까지로 보는 편이 맞다.
- latest normalization sanity rerun에서는 `Custom Weird Vuln + Open Redirect`가 더 이상 supported subset으로 collapse되지 않고 `NAME-CUSTOM-WEIRD-VULN`, `NAME-OPEN-REDIRECT` 두 bundle로 유지되며 `vuln_id_resolutions[]` trace까지 남는다.
- same sanity rerun에서 `unsafe template deserialization`은 더 이상 `CWE-502`로 과잉 canonicalize되지 않고 synthetic `NAME-UNSAFE-TEMPLATE-DESERIALIZATION` + `pattern_id=generic-web-vuln`로 남는다.
- same mixed multi-vuln rerun(`sid-14513fdcdee9`)은 현재 whole-run 기준 `failure_manifest.json`으로 종료되지만, 이번 보강 이후 `NAME-OPEN-REDIRECT` bundle은 실제로 compiler-generated build/run/verify까지 닫히고 `run_passed=true`, `verify_pass=true`를 남긴다. 반면 `NAME-CUSTOM-WEIRD-VULN`만 `unsupported_free_form_negative` + `evidence_low_relevance` fail-closed로 남는다. 즉 mixed success/failure multi-vuln은 이제 input preservation을 넘어 partial execution까지 가능하지만, promotion/acceptance semantics는 아직 미완성이다.
- 추가로 `multi-name-mixed-partial` official case는 `VUL_WEB_SEARCH_PROVIDER=none`에서도 같은 동작을 deterministic하게 재현한다. 즉 supported bundle per-bundle RESEARCH skip과 unsupported/custom bundle fail-closed가 함께 작동해, mixed lane도 remote provider availability에 덜 흔들리는 lower bound를 갖게 되었다.
- latest sanity rerun에서는 `Template Injection + compiler.enabled=false`가 `remote_required`, `require_researcher_evidence=true`, `_can_skip_researcher=false`로 재분류되었다. 즉 compiler-disabled request가 더 이상 compiler-first lower bound처럼 과대표현되지 않는다.
- latest sanity rerun에서는 external DB requirement와 empty sidecar / network-none policy mismatch가 `EXECUTOR_PRECHECK`에서 `terminal_failure_class=executor_dependency_misconfigured`로 차단되었다.
- latest unit regression은 transient LLM provider failure가 이후 call 전체를 permanent stub mode로 고정하지 않는다는 사실도 고정했다.
- latest manifest/performance surface는 `lower_bound`(`family_non_remote_available`, `effective_non_remote_available`, `compiler_path_enabled`)와 `executor_feasibility_status`까지 직접 노출한다. 즉 family capability, effective requirement capability, executor satisfiability를 artifact 수준에서 분리해 읽을 수 있다.
- latest sidecar-template rerun에서는 `generator_mode=template` + viable MySQL template가 실제로 `built_in_template`, `template-assisted`, `executor_feasibility_status=configured`, `verification_rule_source=declared_rule`, `verification_trust=high`로 닫혔다. 이는 current source-of-truth에 포함된 첫 sidecar-backed positive runtime lane이다.
- latest sidecar-compiler rerun에서는 `generator_mode=synthesis` + MySQL sidecar runtime가 실제로 `compiler_generated`, `compiler-first`, `compiler_strategy=sqli_string_concat_mysql`, `compiler_family=sql_injection`, `stack_scaffold_id=python/flask`, `fragment_id=mysql_login_query_concat_route`, `executor_feasibility_status=configured`, `verification_rule_source=declared_rule`, `verification_trust=high`로 닫혔다. 즉 current source-of-truth에는 compiler-first sidecar positive lane도 편입되었다.
- same change set에서 sidecar template/compiler service 코드는 invalid placeholder DB defaults를 갖도록 바뀌었고, current rerun은 explicit `service_env` contract가 executor를 통해 실제 전달되었기 때문에 계속 green이다. 즉 “default host가 우연히 맞아 성공”하는 숨은 template dependence는 줄었다.
- 추가로 custom alias/credential/db-name을 가진 ad-hoc MySQL sidecar rerun도 current workspace에서 `compiler_generated`, `compiler-first`, `executor_feasibility_status=configured`, `promotion.eligible=true`로 닫혔다. 즉 현재 runtime env contract는 단순 default echo가 아니라 실제 sidecar spec 변화까지 흡수한다.
- SQLi, CSRF, Command Injection, Code Injection, SSRF, Template Injection, XSS, Insecure Deserialization official lane은 current workspace에서 pass했다.
- SQLi는 `sqli_string_concat`, CSRF는 `csrf_missing_token` compiler path로 승격되었고, 둘 다 current rerun 기준 `compiler-first`, `promotion.eligible=true`까지 닫혔다.
- Path Traversal official lane은 이번 갱신에서 추가되었고, current workspace에서 `compiler_strategy=path_traversal_file_read`, `compiler-first`, `promotion.eligible=true`까지 닫혔다.
- XSS, SSRF, Insecure Deserialization은 이번 구현 업데이트로 compiler-first family로 승격되었다.
- Template Injection은 이번 추가 구현으로 `semantic_profile.support_level=compiler_supported` + `compiler_strategy=template_injection_render`를 바탕으로 `compiler-first` positive lane으로 승격되었다.
- Template Injection deterministic fallback PoC는 기본 `--base-url`이 실제 service port와 정렬되도록 수정되었고, 이후 compiler path가 same-route contract를 사용한다.
- Open Redirect/Template Injection/Path Traversal runtime rule에는 최소 service-side `file_contains` evidence가 추가되었다.
- 이번 추가 구현으로 compiler와 researcher가 `agents/generator/flask_fragment_registry.py`를 공통 참조하며, service-side `file_contains` token derivation도 shared fragment registry metadata를 소비하기 시작했다.
- 이번 추가 구현으로 fallback guard `generator_assertions`와 exact compiler-covered family의 default semantic signature도 shared fragment registry에서 직접 파생되기 시작했다.
- 이번 추가 구현으로 requirement normalization과 fragment routing은 `common/assets/vuln-family-catalog.json`을 함께 참조한다. 즉 `Template rendering vulnerability`, `External redirect vulnerability`, `XML External Entity`, `CWE89` 같은 alias/identifier/paraphrase는 더 이상 서로 다른 하드코딩 table에서 따로 해석되지 않는다.
- 이번 추가 구현으로 SID는 `generator_mode`와 runtime/executor surface digest까지 포함한다. 그래서 `sqli-sidecar-template`과 `sqli-sidecar-compiler`처럼 같은 vuln family/pattern이더라도 generation path나 sidecar surface가 다르면 서로 다른 SID(`sid-fb69eab9a174`, `sid-e94b254bdff9`)로 분리된다. raw parallel case run에서 sidecar container name이 충돌하던 문제도 이 변경으로 줄었다.
- 이번 추가 구현으로 resolved contract / generator template / compiler manifest는 sidecar bundle의 `service_env`를 함께 surface한다. executor는 이를 실제 `docker run -e ...` 인자로 사용하고, 따라서 compiler-first sidecar lane과 template-assisted sidecar lane 모두 explicit runtime contract를 통해 닫힌다.
- 이번 추가 보완으로 MySQL sidecar SQLi의 runtime env derivation 규칙은 `common/assets/vuln-family-catalog.json`의 `runtime_surface.service_env` asset으로 이동했고, final `manifest.json`의 single-bundle top-level과 bundle-level `compiler_contract`도 `service_env`를 mirror한다. 즉 sidecar lane runtime contract가 intermediate artifact에만 머물지 않고 final pack artifact에서도 직접 관찰된다.
- current manifest/E2E summary는 known-family lane을 `known_family_regression`, real free-form positive lane을 `real_free_form_positive`, synthetic unknown lane을 `synthetic_regression`, unsupported negative lane을 `unsupported_free_form_negative`로 구분한다.
- 이번 hardening으로 `normalize_vuln_id`가 `NAME-*`를 canonical하게 보존하고, `NAME-OPEN-REDIRECT` / `NAME-TEMPLATE-INJECTION`도 foreign-family semantic contradiction 검출을 수행한다. 즉 free-form positive lane에서 SQLi/SSTI/XSS term contamination을 자동 용인하지 않는다.
- 추가로 name normalization은 shared fragment strategy fallback을 사용해 일부 reordered token phrase도 canonical family로 정렬한다. latest unit rerun 기준 `Injection in shell command -> CWE-78`, `Injection in Jinja template -> NAME-TEMPLATE-INJECTION`, `Redirect open vulnerability -> NAME-OPEN-REDIRECT`가 기본 pattern/profile까지 함께 정렬된다.
- 이번 추가 구현으로 compiler-covered 열한 family(SQLi/CSRF/Command Injection/Code Injection/Path Traversal/SSRF/XSS/Insecure Deserialization/Open Redirect/Template Injection/XXE)는 모두 `python/flask` scaffold + registry fragment compose metadata를 남기기 시작했다. current rerun의 `metadata/<sid>/generator_manifest.json`에는 `stack_scaffold_id`, `fragment_id`, `compose_mode=registry`가 실제로 남는다.
- same change set에서 single-bundle `manifest.json`/E2E summary도 `compiler_family`, `stack_scaffold_id`, `stack_scaffold_version`, `fragment_id`, `compose_mode`를 mirror할 수 있게 되었고, representative official case는 이를 expectation으로 직접 검증한다.
- 추가로 plan requirement/manifest는 `name_resolution.input`, `name_resolution.resolved_vuln_id`, `name_resolution.source`를 surface한다. current free-form positive evidence는 이제 alias-based인지, heuristic인지, fragment-strategy fallback인지를 artifact 수준에서 구분할 수 있다.
- 추가로 multi-vuln minimal-input path는 `vuln_id_resolutions[]`를 함께 surface해, `vuln_ids` list에서 어떤 raw 입력이 어떤 canonical/synthetic bundle로 정규화되었는지를 bundle 수와 분리해서 추적할 수 있다.
- 이번 추가 구현으로 compiler target 기본 매핑도 `agents/generator/assets/compiler-targets.json`으로 분리되어, strategy -> default target 하드코딩 일부가 코드 밖 asset으로 이동했다.
- `cwe-unknown-basic` live lane도 current workspace에서는 pass했지만, 이는 explicit `CWE-9999` + inherited SQLi-like pattern 기반 synthetic regression이며 `promotion.eligible=false`, `counts_as_generalization=false`로 surface된다.
- `Open Redirect`는 real free-form `vuln_name only` case이며, 이번 구현 후 `semantic_profile.support_level=compiler_supported`와 `open_redirect_reflect` compiler path로 `verify_pass=true`, `promotion.eligible=true`, `compiler-first`까지 닫힌다.
- `Template Injection`도 real free-form `vuln_name only` case이며, 이번 구현 후 `semantic_profile.support_level=compiler_supported`와 `template_injection_render` compiler path로 `verify_pass=true`, `promotion.eligible=true`, `compiler-first`까지 닫힌다.
- 이번 추가 구현으로 Open Redirect / Template Injection / XSS compiler PoC도 explicit `flag_token`을 출력하고, verifier fallback evidence에는 `success_signature + flag_token + semantic consistency`가 함께 남는다.
- 이번 추가 구현으로 compiler-generated `NAME-*` lane은 generator가 runtime rule을 직접 파생한다. latest Open Redirect alias rerun에서는 `metadata/<sid>/runtime_rules/name-open-redirect.yaml`이 생성되었고, `artifacts/<sid>/reports/evals.json`의 `verifier_meta.rule_available=true` 및 evidence에서 manifest fallback 문구 제거까지 확인했다.
- 이번 추가 구현으로 compiler는 `python/flask` scaffold metadata를 `agents/generator/assets/python-flask-scaffold.json`에서 읽고, current rerun의 `generator_manifest.json` metadata에는 `stack_scaffold_version=1.0`까지 남는다. 즉 scaffold 자산화는 partial이나 실제 provenance surface까지 연결되기 시작했다.
- `XSS`도 이제 `semantic_profile.support_level=builtin_supported` + `compiler_strategy=xss_reflected`를 바탕으로 compiler path를 선택하며 `compiler-first`로 재분류된다.
- `Command Injection`도 이제 `semantic_profile.support_level=builtin_supported` + `compiler_strategy=command_injection_shell`를 바탕으로 compiler path를 선택하며 `compiler-first`로 재분류된다.
- `Code Injection`도 이제 `semantic_profile.support_level=builtin_supported` + `compiler_strategy=code_injection_eval`를 바탕으로 compiler path를 선택하며 `compiler-first`로 재분류된다.
- `Eval Injection` heuristic phrase도 `CWE-94`로 normalize되어 same `code_injection_eval` compiler lane과 동일 SID(`sid-31aac9a4f61c`)로 닫힌다. 즉 known-family heuristic layer가 exact phrase 밖으로 한 단계 넓어졌다.
- `SSRF`도 seed `semantic_profile` + `compiler_strategy=ssrf_loopback_fetch`를 바탕으로 compiler path를 선택하며 `compiler-first`로 재분류된다. static-rule compiler-only lane이므로 current rerun의 `provider_health_state`는 `not_probed`다.
- `Insecure Deserialization`도 `compiler_strategy=deserialization_pickle_body`를 바탕으로 compiler path를 선택하며 `compiler-first`로 재분류된다.
- `Path Traversal`도 `compiler_strategy=path_traversal_file_read`를 바탕으로 compiler path를 선택하며 `compiler-first`로 재분류된다.
- `LDAP Injection`은 여전히 unsupported free-form lane이지만, current truth는 RESEARCH 실행 전 preseeded semantic profile terminal stop까지 앞당겨졌다. `failure_manifest.json`만 남기고 `retry_count=0`, `total_duration_s≈0.052` 수준으로 종료한다.
- `CWE-9999` no-remote negative lane도 이제 `failure_manifest.json` + `terminal_failure_class=remote_provider_unavailable` + `generation_origin=research_short_circuit` + `retry_count=0`로 정리된다.
- latest `CWE-9999` no-remote rerun에서는 `performance_summary.provider_health_state=remote_provider_unavailable`까지 반영되어 RESEARCH terminal failure class와 perf summary surface가 1차 정렬되었다.
- `failure_manifest.json`과 E2E summary에는 현재 `failure.stage`, `failure.reason`, `terminal_failure_class=semantic_support_missing`, `generation_origin=research_short_circuit`, `dynamicness=pre-generation fail-closed`가 함께 surface된다.
- `semantic_profile.json`이 현재는 `resolved_contract`와 별도 artifact로 생성되고, `manifest`/`failure_manifest`/`performance_summary`에도 `compiler_supported`, `compiler_strategy`, `compiler_reason`가 mirror된다. Template Injection/Open Redirect는 `support_level=compiler_supported` + 각 compiler strategy, Path Traversal/XSS/SSRF/Insecure Deserialization은 `support_level=builtin_supported` + 각 compiler strategy, LDAP Injection은 `support_level=unsupported` + `compiler_reason=semantic family unsupported for compiler-backed generation`으로 구분된다.
- 이번 추가 구현으로 Open Redirect / Template Injection compiler-supported free-form lane의 `semantic_profile.semantic_signature`와 `resolved_contract.semantic_contract.semantic_signature`는 shared fragment registry에서 backfill되고 `semantic_signature_source=['fragment_registry']`, `status=aligned`가 남는다. 즉 researcher skip path에서도 contract/profile artifact 자체는 non-empty canonical semantic basis를 보존한다. 다만 current verifier truth source는 여전히 `resolved_contract.semantic_contract`보다 `generator_manifest` service-side semantics가 우선이다.
- SQLi/CSRF도 현재는 `support_level=builtin_supported` + `compiler_supported=true` + 각각 `sqli_string_concat`, `csrf_missing_token`으로 surface되며, 더 이상 primary path에서 deterministic fallback에 의존하지 않는다.
- 이번 hardening 이후 Open Redirect/Template Injection/XSS/Insecure Deserialization rerun에서 verifier `semantic_source=generator_manifest`가 직접 surface되었다. 즉 이 lane들은 resolved contract prose가 아니라 service-side manifest semantics까지 포함해 pass한다.
- 이번 추가 구현으로 reviewer/pack도 free-form lane에만 국한하지 않고, evaluator가 explicit `semantic_supported=false` 또는 `semantic_status=unsupported`를 보고한 known/compiler-supported family를 promotion 대상에서 제외할 수 있게 되었다.
- 같은 변경으로 XSS/Insecure Deserialization 같은 compiler-supported known family가 더 이상 manifest `unknown_regression`으로 떨어지지 않고 `known_family_regression`으로 정렬된다.
- generic unsupported fallback + empty `semantic_contract` 조합은 이제 built-in evaluator가 service code를 읽고도 semantic support를 되살리지 못하도록 fail-closed된다. 즉 unsupported free-form generic fallback이 supported family 코드처럼 보여 success로 복구되는 경로는 차단된다.
- latest rerun 기준 SQLi / CSRF / Command Injection / Code Injection / Path Traversal / SSRF / Insecure Deserialization / Open Redirect / Template Injection / XSS는 각각 약 `7.174s`, `6.844s`, `7.026s`, `6.675s`, `6.907s`, `6.772s`, `6.721s`, `7.403s`, `7.118s`, `6.987s`였다. synthetic unknown live는 `19.443s`, LDAP Injection negative는 `0.054s`였다. latest bottleneck은 compiler-supported lane 자체보다 unknown/live remote-required lane과 Docker orchestration 쪽에 더 가깝다.
- 이번 추가 구현으로 `manifest.performance`와 `performance_summary.json`은 PACK 이후에도 같은 `provider_health_state` / `total_duration_s`를 보존한다. latest `code-injection-name-only`/`code-injection-alias-name-only` shared SID rerun에서는 둘 다 `not_probed`, `6.675s`였고, latest `CWE-9999` no-remote rerun에서는 둘 다 `remote_provider_unavailable`, `1.650s`였다.
- single-bundle manifest는 이번 추가 구현으로 `llm_fixture_used` 같은 provenance boolean도 top-level에 mirror할 수 있게 되었고, trusted-dynamic fixture lane에서는 same field가 PACK artifact에 직접 남는다.
- 이번 추가 구현으로 fragment metadata도 `agents/generator/assets/flask-fragments.json`으로 이동해, scaffold/target뿐 아니라 semantic signature / service token / description 계층 일부도 코드 밖 asset으로 분리되었다.
- 추가로 Flask fragment의 route/import/setup/startup code도 `agents/generator/assets/flask-fragment-code.json`으로 이동해, compiler registry의 code-side 하드코딩 일부가 asset catalog로 이동했다.
- 추가로 각 family의 PoC script template도 `agents/generator/assets/flask-pocs/*.py.tmpl`로 이동해, compiler registry 내부의 PoC 문자열 하드코딩도 크게 줄었다.
- compiler-supported family는 이제 default minimal-input path에서 RESEARCH `0.0s skipped` + provider `not_probed`로 닫힌다. provider health가 operational completeness를 직접 흔드는 대표 lane은 현재 `CWE-9999` live unknown 쪽이다.
- same change set 기준 unknown no-remote failure는 더 이상 3-loop를 소모하지 않고 single-shot terminal failure로 종료한다.
- `allow_intentional_vuln=true`인 failure run에서도 현재는 `failure_manifest.json`만 남고 `manifest.json`은 남지 않도록 정렬되었다.
- same SID rerun에서도 이전 success `manifest.json`이 남지 않도록 fresh-run cleanup이 추가되었다.
- 이번 추가 구현으로 pipeline가 생성한 runtime rule/template는 `generated_runtime_assets.json`에 추적되며 raw `run_pipeline.py --sid ...` rerun 시작 시 제거된다.
- same change set에서 official harness(`tests/e2e/run_case.py`)는 빈 seed manifest라도 생성해 `runtime_rules/`/`runtime_templates/`를 rerun 전에 purge한 뒤 seeded asset만 restore한다. 따라서 official E2E evidence는 previous generated runtime asset carry-over에 훨씬 덜 취약하다.
- 추가로 official E2E expectation schema는 bundle-level `generation_origin`, `dynamicness_verdict`를 직접 검증하기 시작했다. 즉 current official acceptance는 `compiler_supported=true`라는 capability metadata만으로는 pass를 선언하지 않는다.

## 9. 즉시 착수 work package

다음 구현 순서는 이 문서에서 고정한다.

1. E2E harness semantics 보강
   - 완료: `tests/e2e/run_case.py`가 expected-negative case에서 non-zero exit와 `failure_manifest.json`을 읽고 기대치를 검증할 수 있게 수정
   - 추가 완료: `tests/e2e/run_case.py`가 top-level `failure.stage` / `failure.terminal_failure_class`도 expectation으로 직접 검증할 수 있게 수정
   - 추가 완료: E2E summary/expectation validation이 bundle-level `generation_origin`, `dynamicness_verdict`까지 읽고 official acceptance에서 provenance를 직접 고정
   - 추가 완료: official harness가 runtime asset seed manifest를 작성하고 rerun마다 `runtime_rules/`, `runtime_templates/`를 purge 후 seeded asset만 restore
   - 추가 완료: representative compiler-first case는 `compiler_family`, `stack_scaffold_id`, `stack_scaffold_version`, `fragment_id`, `compose_mode`까지 expectation으로 직접 고정
   - 추가 완료: `multi-name-only-supported` official E2E를 추가해 single-SID multi-vuln compiler-first positive lane을 source-of-truth에 편입
   - 추가 완료: repeatability harness가 `pipeline_returncode`를 summary/expectation validation에 전달하도록 수정
   - 추가 완료: `template_injection_name_only_repeatability_gate`는 current compiler-first lower bound와 정렬되도록 Tavily 의존을 제거
2. manifest / failure_manifest semantics 정리
   - 완료: `allow_intentional_vuln=true`여도 failure run이 `failure_manifest.json`만 남기도록 정렬
3. unsupported negative lane retry 절감
   - 완료: real free-form `NAME-*` + `support_level=unsupported`는 RESEARCH-stage terminal failure로 종료
4. `semantic_profile` schema 및 artifact 추가
   - 부분 완료: `semantic_profile.json`, `compiler_supported`, `compiler_strategy`, `compiler_reason`를 `resolved_contract`/manifest/failure artifact 및 `performance_summary`에 surface
   - 부분 완료: real free-form `NAME-*` unsupported early stop과 SQLi/CSRF/Command Injection/Code Injection/Template Injection/Path Traversal/XSS/SSRF/Insecure Deserialization/Open Redirect compiler path selection이 이 verdict를 직접 소비하기 시작함
   - 부분 완료: top-level/bundle failure summary와 `research_short_circuit` provenance가 same semantic verdict를 surface
   - 추가 완료: `NAME-*` canonical normalization 보정, free-form foreign-family semantic contradiction detection, compiler-supported known family의 generalization class 정렬
   - 추가 완료: single-token free-form input(`Foobar`)도 bare explicit identifier로 새지 않고 synthetic `NAME-FOOBAR`로 고정되어 unsupported negative lane taxonomy와 early fail-closed가 다시 정렬됨
   - 추가 완료: default search policy / `require_researcher_evidence` / RESEARCH skip이 compiler/static supported verdict를 직접 소비
   - 추가 완료: requirement-aware lower-bound helper가 `compiler.enabled=false` / `disable_compiler=true`를 반영해 normalization, researcher unknown classification, run_pipeline researcher skip까지 함께 정렬
   - 추가 완료: `lower_bound` summary(`family_non_remote_available`, `effective_non_remote_available`, `compiler_path_enabled`)가 contract/profile/manifest/performance surface에 올라오기 시작했다
   - 추가 완료: single-bundle manifest/summary도 compiler scaffold/fragment provenance(`compiler_family`, `stack_scaffold_id`, `fragment_id`, `compose_mode`)를 mirror할 수 있게 정렬
   - 추가 완료: `vuln_ids`/`vuln_id` free-form 입력도 synthetic `NAME-*`와 `vuln_id_resolutions[]` trace로 보존되어 multi-vuln minimal-input path의 silent drop을 제거
   - 남은 일: broader compiler-first generator path / acceptance gating 확장
5. compiler skeleton 도입
   - 부분 완료: `agents/generator/compiler.py`와 shared registry module(`agents/generator/flask_fragment_registry.py`) 기반 `sqli_string_concat`, `csrf_missing_token`, `command_injection_shell`, `code_injection_eval`, `open_redirect_reflect`, `template_injection_render`, `path_traversal_file_read`, `xss_reflected`, `ssrf_loopback_fetch`, `deserialization_pickle_body`, `xxe_xml_entity_resolve` 구현
   - 추가 완료: compiler-covered 열한 family 전체를 `python/flask` scaffold + registry fragment compose metadata로 전환하고, `generator_manifest.json` metadata에 `stack_scaffold_id`, `fragment_id`, `compose_mode=registry`를 surface
   - 추가 완료: compiler target 기본 매핑을 `agents/generator/assets/compiler-targets.json` asset으로 분리
   - 추가 완료: fragment metadata(`family`, `fragment_id`, `pattern_tags`, `service_side_tokens`, `semantic_signature`, `requirements_content`)를 `agents/generator/assets/flask-fragments.json` asset으로 분리
   - 추가 완료: Flask fragment의 `import_block`, `route_block`, `app_setup_block`, `startup_block`를 `agents/generator/assets/flask-fragment-code.json` asset으로 분리
   - 추가 완료: Flask PoC script template를 `agents/generator/assets/flask-pocs/*.py.tmpl` asset으로 분리
   - 추가 완료: compiler가 더 이상 자체 fragment registry를 중복 보유하지 않고 shared registry module을 직접 소비
6. Tier A family fragment 구현
   - 완료: SQLi, CSRF, Template Injection, Open Redirect, Path Traversal, XSS는 compiler-first artifact로 승격 완료
7. Tier B family fragment 구현 또는 explicit defer 정렬
   - 완료: SSRF는 `ssrf_loopback_fetch` compiler path로 승격 완료
   - 추가 완료: Command Injection은 `command_injection_shell` compiler path와 official E2E까지 승격 완료
   - 추가 완료: Code Injection은 `code_injection_eval` compiler path와 official E2E, heuristic alias(`Eval Injection`)까지 승격 완료
   - 남은 일: same-container helper model 일반화와 second scaffold 도입
8. Tier C family fragment 구현 또는 explicit defer 정렬
   - 완료: Insecure Deserialization은 `deserialization_pickle_body` compiler path로 승격 완료
   - 추가 완료: XXE는 `xxe_xml_entity_resolve` compiler path와 official E2E까지 승격 완료
   - 남은 일: Python/pickle 편중 완화와 XXE의 local-file model beyond-local-target generalization
9. runtime rule / guard / evaluator convergence
   - 부분 완료: Open Redirect/Template Injection/Path Traversal runtime rule에 최소 service-side evidence 추가
   - 추가 완료: built-in semantic evaluator support를 Open Redirect/Template Injection/XSS/Insecure Deserialization/XXE까지 확장하고, representative rerun에서 `semantic_source=generator_manifest`를 재검증
   - 추가 완료: researcher service-side `file_contains` token derivation이 shared fragment registry metadata를 직접 소비
   - 추가 완료: fallback guard `generator_assertions`와 exact compiler-covered family의 default semantic signature가 shared fragment registry metadata를 직접 소비
   - 추가 완료: verifier result와 manifest/E2E summary에 `verification_rule_source` / `verification_trust` / `verification_trust_reason`를 surface하고, unknown live lane의 runtime rule candidate를 low-trust로 분류
   - 추가 완료: reviewer가 low-trust verifier contract를 non-blocking quality issue로 surface하고, manifest top-level `verification_summary`가 trust/rule-source 분포를 집계
   - 추가 완료: insufficient researcher semantics는 `semantic_contract.status=empty`로 정규화되어 no-remote unknown lane과 semantic taxonomy 충돌을 줄였다
   - 추가 완료: `policy.verifier.low_trust_unknown_policy`를 `warn|fail_closed`로 정규화하고, strict mode에서는 unknown low-trust verdict를 `verification_policy_blocked=true` + `terminal_failure_class=low_trust_verification`로 종료
   - 추가 완료: strict policy로 막힌 verifier result는 registry가 LLM fallback으로 덮어쓰지 않도록 short-circuit
   - 남은 일: registry metadata에서 runtime rule / guard / evaluator assertion을 더 완전하게 자동 파생하고, unknown lane으로 잘못 새지 않도록 strict/loose resolution policy를 더 세분화
10. 공식 negative / positive free-form acceptance 편입
   - 완료: LDAP Injection negative regression
   - 추가 완료: single-token custom name negative regression(`Foobar -> NAME-FOOBAR`)
   - 완료: Template Injection positive free-form evidence
   - 완료: Open Redirect positive free-form evidence
   - 완료: compiler-first positive free-form 최소 2개 (`Template Injection`, `Open Redirect`)
- 추가 완료: multi-vuln free-form positive official case(`Template Injection + Open Redirect`)를 단일 SID evidence로 편입
- 추가 완료: mixed success/failure multi-vuln은 partial-progress 실행이 가능해져, unsupported/custom bundle이 fail-closed되어도 supported compiler bundle은 same SID에서 generate/build/run/verify를 계속 수행할 수 있다
- 추가 완료: compiler/static supported bundle은 mixed request 안에서도 per-bundle RESEARCH skip이 가능해져, `multi-name-mixed-partial` lane이 `VUL_WEB_SEARCH_PROVIDER=none`에서도 deterministic하게 재현된다
11. synthetic unknown lane 재분류 및 official lane 표 갱신
   - 완료: `CWE-9999`를 `synthetic_regression` + `counts_as_generalization=false`로 surface하고, official lane 표와 E2E expectation에 반영
   - 추가 완료: no-remote negative regression과 live Tavily regression을 expectations 수준에서도 분리
12. template debt accounting 전환
   - 부분 완료: runtime template clone과 built-in template를 legacy/compatibility asset으로 재분류하고, compiler-covered family success claim에서 제외
   - 추가 완료: compiler-covered 열한 family 모두 registry-backed scaffold/fragment provenance를 남기기 시작했다
   - 추가 완료: registry asset 자체를 `compiler.py` 내부 문자열 중복에서 분리해 shared module(`agents/generator/flask_fragment_registry.py`)로 승격
   - 추가 완료: MySQL sidecar SQLi의 runtime env derivation 규칙(`runtime_surface.service_env`)을 `common/assets/vuln-family-catalog.json` asset으로 이동해 strategy별 hardcoded env branch를 줄였다
   - 추가 완료: Path Traversal/XXE의 helper extra files도 이제 fragment asset DSL(`agents/generator/assets/flask-fragments.json`)에서 직접 정의되어 compiler registry callback hardcoding을 한 단계 줄였다
   - 추가 완료: active synthetic unknown lane에 실제 사용되는 SQLi family-aware fallback service/PoC를 `agents/generator/assets/fallbacks/sqli_family_aware_*.py.tmpl` asset으로 분리
   - 추가 완료: generic unsupported reflect fallback과 CSRF family-aware fallback service/PoC도 각각 fallback asset template로 분리
   - 추가 완료: Open Redirect family-aware fallback service/PoC도 `agents/generator/assets/fallbacks/open_redirect_family_aware_*.py.tmpl` asset으로 분리
   - 추가 완료: Template Injection/XSS/SSRF/Insecure Deserialization/Path Traversal family-aware fallback service/PoC도 각각 fallback asset template로 분리
   - 추가 완료: fallback bundle의 공통 `Dockerfile`/`README`도 asset template로 분리
   - 남은 일: shared registry module을 외부 data asset/DSL 수준으로 더 분리하고, `synthesis.py` 안에 남은 build/run metadata, `poc.cmd`, single-scaffold assumption을 data-driven layer로 이동
13. next compiler-first expansion
   - 우선순위: shared registry의 외부 data asset화 + evaluator/guard auto-derive, 이후 second scaffold / richer sidecar-backed family 검토
14. name-only robustness hardening
   - 추가 완료: requirement normalization이 shared fragment strategy fallback을 통해 일부 reordered token phrase를 canonical supported family로 정렬
   - 추가 완료: token fallback을 stopword-trimmed exact-content-token match로 좁혀 ambiguous mixed phrase의 supported-family overcanonicalization을 차단
   - 추가 완료: single-token custom free-form label도 synthetic `NAME-*`로 유지되어 unsupported/custom negative lane이 bare identifier leakage 없이 same fail-closed taxonomy로 정렬
   - 남은 일: 이 robustness를 broader open-world semantic family discovery와 혼동하지 않도록 unsupported unknown lane과의 경계를 유지
15. PACK/performance surface consistency
   - 완료: PACK subprocess 이후 manifest를 재기록해 `manifest.performance`와 `performance_summary.json`의 `provider_health_state` / `total_duration_s` 드리프트를 제거
   - 추가 완료: single-bundle manifest/summary에도 `generation_origin`, `dynamicness_verdict`, `dynamicness_reason`를 mirror해 acceptance와 문서 표를 더 직접 정렬
   - 추가 완료: single-bundle manifest top-level에도 `fallback_used`, `family_override_applied`, `llm_stub_used`, `llm_fixture_used` provenance boolean을 mirror
   - 추가 완료: single-bundle final `manifest.json` top-level과 bundle-level `compiler_contract`도 `service_env`를 mirror해 runtime contract가 final pack artifact까지 직접 surface된다
   - 추가 완료: single-bundle manifest/summary와 `performance_summary`에 `executor_feasibility_status` 및 lower-bound summary가 surface되기 시작했다
   - 추가 완료: multi-bundle manifest도 이제 common provenance/trust를 top-level로 mirror하고, diverged bundle-set은 `generation_origin=dynamicness_verdict=verification_rule_source=verification_trust=\"mixed\"` sentinel로 surface한다
   - 추가 완료: transient remote LLM failure가 process-wide permanent stub mode로 굳지 않도록 provider fallback을 call-level로 완화
   - 추가 완료: `provider_health_state`가 root `search_health.json`만 보는 대신 bundle-level search health와 nested failed-bundle failure class까지 집계하게 되어, bundle-scoped remote failure와 semantic fail-closed를 더 정확히 분리한다
   - 남은 일: current 성능 검증은 summary/provenance correctness가 중심이므로, wall-clock budget regression gate는 별도 계층으로 추가해야 한다
16. test completeness hardening
   - 추가 완료: official multi-vuln positive lane(`multi-name-only-supported`)을 source-of-truth에 편입
   - 추가 완료: fixture-backed trusted-dynamic official lane(`trusted-dynamic-sqli`)을 source-of-truth에 편입
   - 추가 완료: template-assisted MySQL sidecar positive lane(`sqli-sidecar-template`)을 source-of-truth에 편입
   - 추가 완료: compiler-first MySQL sidecar positive lane(`sqli-sidecar-compiler`)을 source-of-truth에 편입
   - 추가 완료: custom alias/credential/db-name을 가진 compiler-first MySQL sidecar official lane(`sqli-sidecar-compiler-custom-env`)을 source-of-truth에 편입
   - 추가 완료: sidecar/external DB bundle의 `service_env` contract를 resolved contract / template summary / compiler manifest / executor path에 연결
   - 추가 완료: catalog-backed paraphrase official lane(`template-injection-paraphrase-name-only`, `open-redirect-paraphrase-name-only`)을 source-of-truth에 편입
   - 추가 완료: repeatability harness의 false-fail 원인이던 `pipeline_returncode` 누락을 수정
   - 추가 완료: Template Injection repeatability gate를 provider-independent compiler-first lane으로 정렬
   - 추가 완료: external DB requirement와 executor sidecar/network mismatch를 `EXECUTOR_PRECHECK` 및 direct executor path에서 fail-fast하는 regression을 추가
   - 남은 일: SQLi 외 richer bridge/sidecar positive lane, live remote-LLM-backed `llm_manifest -> trusted dynamic` lane, mixed success/failure multi-vuln lane의 official acceptance/promotion semantics를 더 정교하게 source-of-truth로 추가
16. research failure taxonomy hardening
   - 추가 완료: `remote_provider_unavailable`, `remote_evidence_missing`, `evidence_low_relevance`, `provider_degraded`를 RESEARCH terminal failure class 후보로 분리
   - 추가 완료: no-remote synthetic unknown regression은 same-run 3-loop 재시도 대신 single-shot fail-closed
   - 추가 완료: mixed multi-vuln request에서도 unsupported free-form `NAME-*` bundle은 bundle 단위 preseeded semantic profile에 의해 search 호출 전에 `semantic_support_missing`으로 fail-closed된다
   - 추가 완료: bundle-scoped RESEARCH failure가 VERIFY 단계에서 다시 top-level root cause로 오인되지 않도록 partial-progress rerun의 top-level `failure.stage`를 `RESEARCH`로 정렬
   - 남은 일: provider degraded와 low-relevance를 performance/provider surface까지 더 정교하게 반영
17. runtime generated asset tracking
   - 추가 완료: researcher/generator/verifier가 생성한 runtime rule/template를 `generated_runtime_assets.json`으로 추적
   - 추가 완료: raw `run_pipeline.py --sid ...` rerun 시작 시 tracked generated runtime asset을 정리
   - 남은 일: seed manifest 없이도 historical untracked runtime asset을 deterministic하게 판별/정리하는 정책을 더 정교하게 다듬을 수 있다

## 10. 한 문장 요약

현재 레포는 known lane(SQLi/CSRF/Command Injection/Code Injection/SSRF/Path Traversal/XSS/Insecure Deserialization)과 real free-form `Template Injection`, `Open Redirect`, `XML External Entity`, canonical alias `Server Side Template Injection`, 그리고 catalog-backed paraphrase `Template rendering vulnerability`, `External redirect vulnerability`까지 compiler-first path로 지원하고 이 compiler-supported family들은 default minimal-input path에서 remote search 없이도 닫히며, 추가로 MySQL sidecar SQLi lane도 이제 `template-assisted`와 `compiler-first` 두 provenance로 모두 source-of-truth에 편입되었고 shared vuln family catalog 및 runtime-aware compiler strategy 덕분에 requirement normalization과 fragment routing의 alias/runtime drift가 줄었으며 MySQL sidecar SQLi의 runtime env derivation도 `runtime_surface.service_env` asset으로 이동해 final manifest까지 surface되기 시작했고 `vuln_ids` free-form 입력도 silent drop 없이 synthetic `NAME-*` bundle로 보존되며 token fallback도 stopword-trimmed exact-content-token layer로 보수화되어 ambiguous mixed phrase의 supported-family overcanonicalization이 줄었고 single-token custom label(`Foobar`)도 bare explicit identifier로 새지 않고 `NAME-FOOBAR`로 정렬되며 mixed success/failure multi-vuln도 supported bundle partial execution과 per-bundle semantic fail-closed까지 가능해졌고 multi-bundle top-level manifest 역시 uniform provenance/trust는 직접 mirror하고 diverged bundle-set은 `mixed` sentinel로 surface하며 SID도 generation/runtime surface를 반영해 case isolation이 더 좋아졌으며 unsupported free-form `NAME-*` lane은 LDAP Injection뿐 아니라 single-token custom unsupported name도 preseeded semantic profile로 거의 즉시 fail-closed되지만,
free-form 이름 기반 동적 Docker 생성의 generalization 상한은 여전히 unknown/open-world compiler 부재와 `python/flask` 단일 scaffold 편중, low-trust runtime-rule candidate에 기대는 unknown verifier path, compiler-derived runtime rule 이후에도 남는 verifier 독립성 상한, live remote-LLM-backed trusted-dynamic acceptance 부재, 그리고 `synthesis.py` 안에 남아 있는 build/run metadata와 compose/orchestration hardcoding에 의해 제한되므로 이후 우선순위는 `shared registry module의 외부 data asset화`, `fallback compose layer의 DSL화`, `unknown/open-world lane의 verifier policy 재설계`, `SQLi 외 richer bridge/sidecar family compiler화`, 그리고 second scaffold / sidecar-backed richer family 쪽으로 이동한다. 다만 이번 턴으로 sidecar lane 자체도 explicit runtime env contract를 통해 닫히기 시작했기 때문에, 이후 확장은 template cloning보다 runtime contract DSL 일반화 쪽에 더 초점을 두는 편이 맞다.
