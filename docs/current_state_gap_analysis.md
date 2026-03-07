# 동적 취약 Docker 생성 현재 상태 및 통합 실행 계획

본 문서는 2026-03-07 KST 기준으로 다음 세 가지를 함께 반영한 단일 마스터 계획 문서다.

- current workspace 직접 rerun 결과
- 기존 healthy-provider 세션에서 확보된 verified baseline
- 현재 코드 구조에 대한 템플릿/하드코딩 의존 감사

이 문서는 더 이상 단순 회고 문서가 아니다.
현재 상태를 과대평가하지 않도록 verified fact와 계획을 명확히 분리하고,
이후 구현 우선순위를 `신뢰성 최소 차단선 선행 -> failure-path truth/provenance 고정 -> degraded-mode resilience 확보 -> 성능 전면화 -> 템플릿/하드코딩 의존 축소 -> free-form generalization` 순으로 고정하는 실행 문서다.

## 1. 문서 목적과 판정 원칙

### 1.1 목적

이 문서의 목적은 여섯 가지다.

1. 현재 레포가 실제로 어디까지 닫혀 있는지 verified baseline을 고정한다.
2. healthy-provider success와 current-workspace degraded failure를 동시에 기록해 운영 하한선을 숨기지 않는다.
3. 현재 구현의 생성 경로를 `LLM 동적 생성`, `템플릿 복사`, `family-specific deterministic override`, `fallback`으로 분해한다.
4. 템플릿 의존과 family-specific 하드코딩 의존을 공식적으로 문서화한다.
5. 다음 구현 단계를 decision-complete한 phase 계획으로 재정렬한다.
6. 이후 문서 갱신이 “pass rate 증가”만이 아니라 “artifact trust 증가”를 반영하게 만든다.

### 1.2 판정 원칙

이 문서 이후 상태 판정은 아래 원칙을 따른다.

- `pass`는 반드시 provider condition을 함께 적는다.
- `python -m pytest -q tests` 통과와 Docker E2E 통과는 같은 완성도 근거로 취급하지 않는다.
- `dynamic`이라는 단어는 provenance가 `llm_manifest` 중심일 때만 쓴다.
- built-in template copy, runtime template clone, scaffold overwrite, deterministic fallback은 별도 분류로 적는다.
- healthy-provider success와 degraded-provider failure가 공존하면, 운영 완성도는 더 낮은 쪽을 기준으로 쓴다.
- `vuln_name only` 방향성은 유지하되, `CWE-9999` 같은 explicit synthetic id를 free-form name-only 성공의 증거로 쓰지 않는다.

## 2. Verified Current State

### 2.1 테스트 스위트 truth

- 실행: `python -m pytest -q tests`
- 결과: `147 passed, 11 skipped`

단, 이 수치는 기본 테스트 스위트 truth일 뿐이다.
현재 E2E 테스트는 `tests/e2e/test_cases.py`에서 `VULD_RUN_E2E=1`이 없으면 skip되므로,
이 문서에서는 “기본 pytest pass”를 “Docker E2E 완성도”와 동일시하지 않는다.

### 2.2 healthy-provider baseline

아래 표는 healthy-provider 세션에서 확인된 verified baseline이다.
이 표는 “특정 provider health session에서 확인된 상한선”이지,
current workspace의 운영 하한선이 아니다.

| lane | 입력 형태 | 결과 | loop | 총 소요 | 비고 |
| --- | --- | --- | --- | --- | --- |
| SQLi | `sqli-name-only` | pass | 2 | 약 52s | loop 1 guard miss 후 loop 2 성공 |
| CSRF | `csrf-name-only` | pass | 1 | 약 35s | known static lane |
| SSRF | `ssrf-name-only` | pass | 1 | 약 22s | known static lane |
| Path Traversal | `vuln_name: Path Traversal` | pass | 1 | 약 58s | researcher-backed runtime rule lane |
| Template Injection | `vuln_name: Template Injection` | pass | 1 | 약 68~73s | official E2E case, fresh rerun 기준 loop 1 pass 확인 |
| Reflected XSS | `vuln_name: Reflected XSS` | pass | 1 | 약 59s | official E2E case expectations satisfied 확인 |
| Insecure Deserialization | `vuln_name: Insecure Deserialization` | pass | 2 | 약 106s | official E2E case expectations satisfied 확인 |

주의:

- 위 baseline은 current workspace degraded 상태의 하한선을 대변하지 않는다.
- unknown live lane은 이번 healthy-provider 재검증 대상으로 재실행하지 않았으므로, 이 문서에서 success evidence로 집계하지 않는다.

### 2.3 current-workspace degraded baseline

2026-03-07 KST current workspace 직접 rerun에서는 OpenAI provider가 quota exhausted 상태였다.
같은 세션에서 Tavily remote search는 정상 동작했다.
아래 표는 이 degraded 상태에서 직접 확인한 운영 하한선이다.

| lane | SID | 결과 | loop | 총 소요 | 실패 stage | fingerprint / 비고 |
| --- | --- | --- | --- | --- | --- | --- |
| SQLi | `sid-3325b4630aa4` | fail | 3 | 21.461s | GENERATOR | `23365ba0 -> 10f8dd23`; fallback manifest가 SQLi semantic/guard를 통과하지 못함 |
| Template Injection | `sid-60ae4e071b9f` | fail | 3 | 28.115s | GENERATOR | `f40a3ab4`; Tavily remote search 성공 후에도 deterministic family fallback 부족으로 fail |
| unknown (`CWE-9999`) | `sid-d2ff12df4e6d` | fail | 3 | 30.366s | GENERATOR | `88cb5626`; remote search configured=true, `remote_result_count=9`, 이후 semantic guard fail |

추가 사실:

- `sid-60ae4e071b9f`, `sid-d2ff12df4e6d`의 `search_health.json` 기준
  - `provider=tavily`
  - `configured=true`
  - `remote_result_count=9`
  - `last_status_code=200`
- 즉 current workspace degraded baseline의 핵심 병목은 search가 아니라 generator/LLM degraded path다.

### 2.3.1 이번 세션 fresh rerun 재검증

아래 rerun은 본 문서 갱신 과정에서 2026-03-07 KST에 새 SID로 직접 실행한 검증이다.
세 실행 모두 stderr에서 OpenAI `RateLimitError` 후 stub/fallback 경로로 전환된 것이 확인되었다.

| lane | SID | 결과 | loop | 총 소요 | 관찰 |
| --- | --- | --- | --- | --- | --- |
| SQLi | `sid-6247be018b41` | fail | 3 | 18.407s | search는 healthy였으나 generator가 fallback 후 semantic/guard mismatch로 종료 |
| Template Injection | `sid-02575fde190d` | fail | 3 | 29.729s | researcher/search는 정상, generator fail 후 review gate 때문에 PACK도 실패 |
| CSRF | `sid-db1e04270bf4` | fail | 3 | 17.088s | known static lane도 degraded 상태에서 fallback semantic mismatch로 종료 |

추가 사실:

- 세 rerun 모두 `search_health.json` 기준 `provider=tavily`, `configured=true`, `remote_result_count=9`, `degraded=false`, `last_status_code=200`이었다.
- `sid-6247be018b41`는 `allow_intentional_vuln=true`라 failure manifest가 남았지만,
  그 manifest는 `provider_health_state=healthy`, `llm_stub_used=false`, `bundle.provenance={}`로 surface되었다.
- `sid-02575fde190d`, `sid-db1e04270bf4`는 review/pack gate에 막혀 top-level `manifest.json`이 생성되지 않았다.
- 따라서 현 시점의 실운영 하한선은 “LLM degraded 시 known static lane도 의미 있게 닫히지 못하고,
  failure provenance/health truth도 완전하게 surface되지 않는다” 쪽에 더 가깝다.

### 2.3.2 이번 턴 구현 반영 후 post-fix rerun

아래 rerun은 본 문서의 개선안을 실제 반영한 뒤 같은 degraded 환경에서 다시 수행한 fresh rerun이다.
세 known lane 모두 stderr에서 OpenAI `RateLimitError` 후 stub/fallback으로 전환되었지만,
family-aware deterministic fallback을 통해 end-to-end를 닫는 것이 확인되었다.

| lane | SID | 결과 | loop | 총 소요 | 핵심 관찰 |
| --- | --- | --- | --- | --- | --- |
| SQLi | `sid-5a5277a8aeda` | pass | 1 | 13.611s | `provider_health_state=llm_degraded`, `llm_failure_class=quota_exhausted`, `generation_origin=deterministic_fallback` |
| CSRF | `sid-91c772b15bb1` | pass | 1 | 12.179s | degraded known static lane이 deterministic fallback으로 loop 1 pass |
| Template Injection | `sid-6210ffdbeb5b` | pass | 1 | 19.580s | deterministic fallback + family override로 verify/review/pack까지 pass |
| unknown (`CWE-9999`) | `sid-269fb6724565` | fail | 3 | 16.565s | RESEARCH low relevance로 종료, `failure_manifest.json` 생성 확인 |

추가 사실:

- `sid-5a5277a8aeda`, `sid-91c772b15bb1`, `sid-6210ffdbeb5b`
  - `status=success`
  - `performance.provider_health_state=llm_degraded`
  - `performance.llm_stub_used=true`
  - `performance.llm_failure_class=quota_exhausted`
  - bundle `provenance.generation_origin=deterministic_fallback`
  - bundle `dynamicness.verdict=deterministic fallback dependent`
- 즉 known/static lane 및 Template Injection은 degraded 상태에서 “동적 신뢰성”을 회복한 것이 아니라
  “family-aware deterministic fallback dependent success”를 확보한 상태로 보는 것이 정확하다.
- `sid-269fb6724565`는 generation 이전 RESEARCH stage에서 종료됐지만,
  `failure_manifest.json`이 생성되어 pack/review gate와 inspection summary emission이 분리된 것이 확인되었다.

### 2.4 현재 코드에 이미 반영된 개선

현재 코드에는 아래 개선이 이미 반영되어 있다.

- verifier/reviewer/pack truth repair 1차 구현
- `NAME-*` runtime rule filename normalization 1차 구현
- role canonicalization 1차 구현
- Template Injection deterministic PoC stabilization 1차 구현
- Tavily auto-selection 보강
- Template Injection / XSS / Insecure Deserialization official E2E case 추가
- stub researcher report의 canonical `vuln_id` normalization 1차 구현
- `generator_manifest.json` / `generator_template.json` / `resolved_contract.json` provenance 1차 구현
  - `generation_origin`
  - `fallback_used`
  - `family_override_applied`
  - `llm_stub_used`
- pack manifest provenance / generation summary surface 1차 구현
  - bundle-level `provenance`
  - top-level `generation_summary`
  - top-level `performance`
- provenance 기반 dynamicness classification 1차 구현
  - bundle-level `dynamicness`
  - top-level `generation_summary.by_dynamicness_verdict`
  - 분류값:
    - `trusted dynamic`
    - `template-assisted`
    - `deterministic fallback dependent`
- `performance_summary.json` metadata 확장 1차 구현
  - `retry_count`
  - `provider_health_state`
  - `llm_stub_used`
- failure-path truth / degraded provenance 1차 구현
  - `generator_failures.jsonl`에 `llm_stub_used`
  - `generator_failures.jsonl`에 `fallback_used`
  - `generator_failures.jsonl`에 `family_override_applied`
  - `generator_failures.jsonl`에 `llm_failure_class`
  - `performance_summary.json`에 `llm_failure_class`
  - pack block 시 `failure_manifest.json` emission
  - pack bundle provenance가 generator failure record를 fallback source로 읽도록 보강
- family-aware deterministic fallback 1차 구현
  - SQLi service/PoC skeleton
  - CSRF service/PoC skeleton
  - Template Injection service skeleton + deterministic PoC dependency sync
  - Path Traversal service/PoC skeleton
- dependency sync truth repair 1차 구현
  - declared `deps`의 explicit version을 requirements sync 시 보존
- 관련 targeted test 추가 후 full pytest 재실행
  - targeted: `45 passed`
  - full: `147 passed, 11 skipped`

이번 턴 기준으로 아래 blind spot은 실제로 닫혔다.

- known static / Template Injection degraded rerun에서 `provider_health_state=llm_degraded`가 실제로 surface된다.
- `generator_failures.jsonl`에 failure-path provenance가 기록된다.
- pack gate에 막혀도 `failure_manifest.json`은 남는다.

다만 아래 항목은 아직 “운영 완료”로 판정하지 않는다.

- `exploit_pass / semantic_pass / guard_pass / verify_pass` schema 최종 고정
- degraded-mode family-aware fallback synthesis의 unknown/free-form/general-purpose 확대
- official lane/CI summary에서 provenance 기반 dynamicness classification 사용
- free-form unknown-name official case

### 2.5 이번 세션에서 재검증되어 active defect 목록에서 내린 항목

- `researcher_report.vuln_id` canonicalization은 fresh rerun에서 정상으로 확인되었다.
  - `sid-6247be018b41` -> `CWE-89`
  - `sid-02575fde190d` -> `NAME-TEMPLATE-INJECTION`
  - `sid-db1e04270bf4` -> `CWE-352`
- 따라서 `vuln_id=UNKNOWN` 문제는 현 시점 active defect라기보다 regression watch 항목으로 내린다.

## 3. 현재 구현의 실제 생성 방식 분해

현재 레포의 “동적 생성”은 단일 경로가 아니다.
실제로는 아래 네 등급의 생성 경로가 공존한다.

### A. Explicit built-in template materialization

- `generator_mode=template|hybrid`에서 built-in template를 그대로 복사하는 경로
- researcher candidate template가 새 코드를 합성하는 것이 아니라 기존 template를 clone하는 경로도 포함

판정:

- SQLi/CSRF 계열에는 explicit built-in template dependence가 실재한다.
- 이는 valid fast path일 수 있지만 “pure dynamic synthesis”와 동일하게 집계하면 안 된다.

### B. Template-assisted synthesis

- synthesis 결과 이후 template metadata, marker scaffold, auto-generated PoC scaffold, contract priority로 보정되는 경로
- manifest가 존재해도 downstream contract가 template metadata를 주요 source로 쓰는 경우를 포함

판정:

- 일부 lane은 “LLM이 전부 생성”하는 것이 아니라 synthesis 후 template/contract/scaffold 보정에 상당히 의존한다.
- 이 경로는 동적 합성과 정적 자산 재사용의 혼합 형태로 분리 집계해야 한다.

### C. Family-specific deterministic synthesis override

- Template Injection deterministic PoC overwrite
- fallback PoC endpoint/payload heuristic
- family별 semantic signature, relevance term, guard fallback, known pattern heuristic

판정:

- Template Injection/XSS/Deserialization은 built-in template보다는 family-specific guard/semantic/PoC hardcoding 의존이 더 크다.
- 이 경로는 “LLM free synthesis”가 아니라 “family-aware deterministic assistance”에 가깝다.

### D. LLM-led manifest synthesis

- 실제 LLM JSON manifest를 기반으로 서비스/PoC/Dockerfile이 형성되는 경로
- 이 경로가 artifact의 중심 provenance일 때만 `dynamic`이라는 표현을 쓴다.

### 3.5 종합 판정

현재 시스템은 “pure dynamic synthesis”가 아니다.
보다 정확한 정의는 아래다.

- `LLM + static rules + semantic heuristics + optional templates + deterministic fallback`

즉, `취약점 이름만 제공 -> 동적 취약 Docker 생성` 방향성은 유지되고 있지만,
현재 성립하는 것은 “보조 정적 자산과 family heuristic이 강하게 개입하는 hybrid generation”이다.

## 4. 템플릿/하드코딩 의존 감사

아래 표는 lane별 의존 축을 공식 분류한 것이다.
이 표는 이후 official lane classification과 provenance schema의 기준이 된다.

| lane | 입력 | primary generation path | template dependence | family hardcoding | degraded-mode survivability | trusted dynamicness verdict |
| --- | --- | --- | --- | --- | --- | --- |
| SQLi | `vuln_name -> CWE-89` | synthesis default + family-aware deterministic fallback pass | 중간 | 높음 | 중간 이상 | deterministic fallback dependent under degraded |
| CSRF | `vuln_name -> CWE-352` | known static lane + family-aware deterministic fallback pass | 중간 | 높음 | 중간 이상 | deterministic fallback dependent under degraded |
| SSRF | `vuln_name -> CWE-918` | known static synthesis/static-rule lane | 낮음 또는 불명 | 중간 | 불명확 | partial dynamic, degraded 미검증 |
| Path Traversal | `vuln_name -> CWE-22` | researcher runtime rule + heuristic semantic contract | 낮음 | 높음 | 불명확 | heuristic-assisted dynamic |
| Template Injection | `vuln_name -> NAME-*` | runtime rule + deterministic family-specific service/PoC fallback | 낮음 | 높음 | 중간 이상 | deterministic fallback dependent under degraded |
| Reflected XSS | `vuln_name -> CWE-79` | known-name mapping + semantic/relevance heuristic | 낮음 | 높음 | 불명확 | heuristic-assisted dynamic |
| Insecure Deserialization | `vuln_name -> CWE-502` | known-name mapping + semantic/relevance heuristic | 낮음 | 높음 | 불명확 | heuristic-assisted dynamic |
| unknown / `CWE-9999` | explicit synthetic id | remote evidence + runtime rule + degraded fallback fail | 없음 | 높음 | 낮음 | free-form name-only generalization 증거로 사용 금지 |

### 4.1 이 표의 결론

- “취약점 이름만 제공 -> 동적 생성”은 부분적으로 성립한다.
- 그러나 “템플릿 비의존, 하드코딩 비의존, provider degraded에서도 의미 있게 작동” 단계에는 아직 도달하지 못했다.
- 따라서 official success 집계는 반드시 provenance와 dependency class를 함께 적어야 한다.

## 5. 핵심 결함 및 위험도

### 5.1 P1: provider degraded recovery는 known lane 기준 부분 회복됐지만 여전히 deterministic fallback dependent다

이번 턴 전에는 provider degraded 시 generator가 사실상 닫히는 상태였다.
이번 턴 구현 후에는 SQLi / CSRF / Template Injection은 degraded provider에서도 loop 1 pass가 가능해졌다.

다만 현재 degraded success의 성격은 아래와 같다.

- `trusted dynamic` recovery가 아니다.
- `generation_origin=deterministic_fallback`
- `dynamicness=deterministic fallback dependent`
- unknown/free-form lane은 여전히 researcher evidence 또는 broader family fallback coverage에 막힌다.

즉 degraded resilience는 분명히 개선되었지만,
현재 문서/운영 메시지는 이를 “family-aware deterministic degraded recovery”로 써야 한다.

### 5.2 P0: pytest green과 Docker E2E truth 사이의 간극이 크다

- `147 passed, 11 skipped`는 유지되고 있지만,
- 느린 E2E는 env gate가 없으면 기본적으로 skip된다.
- 따라서 현재 기본 테스트 스위트는 live Docker pipeline의 완성도를 충분히 대표하지 못한다.

이 gap은 성능 계획보다 먼저 문서와 acceptance에서 바로잡아야 한다.

### 5.3 P1: failure-path provenance / provider health truth는 generator/pack failure 기준 1차 해소되었지만 RESEARCH-stage taxonomy는 아직 거칠다

이번 턴 구현으로 아래는 실제로 개선되었다.

- `generator_failures.jsonl`에 `llm_stub_used`, `fallback_used`, `family_override_applied`, `llm_failure_class`가 기록된다.
- `performance_summary.provider_health_state`가 degraded known lane rerun에서 `llm_degraded`로 surface된다.
- pack block이 있어도 `failure_manifest.json`이 남는다.
- failed bundle provenance는 generator failure record를 fallback source로 읽을 수 있다.

다만 RESEARCH-stage failure는 아직 아래처럼 거칠다.

- `loop_state.reason`이 `Researcher failed with exit code 1` 수준에 머무른다.
- unknown lane low relevance / remote evidence insufficiency / provider degraded를 분리한 top-level taxonomy가 없다.
- generation 이전에 종료된 bundle은 provenance가 `unclassified`로 남는 것이 자연스럽지만,
  운영 summary에는 “왜 generation까지 못 갔는지”가 더 구조적으로 surface될 필요가 있다.

### 5.4 P1: failure artifact availability가 policy-dependent하다

이 결함은 이번 턴에서 1차 해소되었다.

- `allow_intentional_vuln` 여부와 관계없이 pack block 시 `failure_manifest.json`이 남는다.
- 실제 확인:
  - `sid-83bf14999326`
  - `sid-cfb2af6ba8ef`
  - `sid-269fb6724565`

남은 일:

- CI / live acceptance summary가 `manifest.json`과 `failure_manifest.json`을 함께 집계하도록 연결
- failure summary를 reviewer/ops 대시보드에 노출

### 5.5 P1: official unknown lane이 free-form `vuln_name only` 증거가 아니다

현재 공식 unknown case는 `vuln_name only`가 아니라 explicit `CWE-9999` 기반이다.
따라서 이 케이스를 free-form generalization 성공 증거로 쓰면 안 된다.

### 5.6 P1: official lane/CI summary가 아직 provenance 기반 dynamicness classification을 기본 집계로 쓰지 않는다

artifact에는 `generation_origin`, `dynamicness`, `provider_health_state`가 기록되지만,
official lane/CI summary는 아직 success/failure 중심으로 읽히는 경향이 강하다.

현재부터는 degraded success를 다음처럼 분리 집계해야 한다.

- `trusted dynamic`
- `template-assisted`
- `deterministic fallback dependent`

### 5.7 P2: broader family coverage와 free-form unknown-name evidence는 아직 부족하다

- SQLi / CSRF / Template Injection degraded recovery는 확보했지만,
  SSRF / XSS / Insecure Deserialization / broader unknown family까지 닫았다고 쓰면 안 된다.
- official unknown case도 여전히 explicit `CWE-9999`다.
- real free-form `vuln_name -> NAME-*` acceptance가 아직 없다.

### 5.8 P2: 현재 semantic/heuristic core는 Python/Flask 단일 스택 편향이 강하다

minimal input defaults, semantic signatures, relevance terms, fallback PoC heuristic이 모두 Python/Flask 단일 컨테이너 웹앱에 강하게 기울어 있다.
따라서 open-world multi-stack generalization은 현재 단계에서 후순위가 맞다.

### 5.9 P2: researcher `vuln_id` canonicalization은 active defect가 아니라 regression watch 항목이다

이번 세션 fresh rerun에서는 `researcher_report.json.vuln_id`가 모두 canonical value로 기록되었다.
따라서 이전 `UNKNOWN` 관찰은 현 시점 active defect로 유지하지 않고,
acceptance/pytest로 회귀 방지하는 항목으로 관리한다.

## 6. 통합 단계별 실행계획

### Phase 0. Reliability Floor

### 목표

- healthy/degraded 양쪽에서 truthfulness를 일치시키는 최소 차단선을 완성한다.
- success, verify, promotion의 의미를 다시 일치시킨다.

### 작업

1. verifier result schema를 공식 top-level verdict로 고정한다.
   - `exploit_pass`
   - `semantic_pass`
   - `guard_pass`
   - `verify_pass`
2. reviewer와 pack이 위 verdict를 직접 소비하도록 정리한다.
3. `researcher_report.vuln_id` canonicalization 1차 구현이 실제 rerun artifact에서도 유지되는지 재검증한다.
4. healthy-provider와 degraded-provider 양쪽 rerun에서 promotion truth가 일치하는지 재검증한다.
5. official lane 재검증 시 nested guard/semantic failure가 top-level success로 승격되지 않는지 다시 확인한다.

### 완료 기준

- healthy/degraded 공통으로 `verify_pass=true`이면 semantic/guard blocking failure가 없다.
- `promotion.eligible=true`인 artifact는 reviewer/guard/semantic contradiction이 없다.
- stub researcher report에도 canonical `vuln_id`가 기록되고 rerun artifact에서 유지된다.

### Phase 0.5. Failure-Path Truth & Degraded Provenance

### 목표

- 실패 run에서도 provider health, fallback provenance, dynamicness class를 inspection 가능한 형태로 남긴다.
- promotion gate와 failure summary emission을 분리해 postmortem truth를 보존한다.

### 작업

1. `generator_failures.jsonl`, `loop_state.history[].metadata`, `performance_summary.json`에 아래 필드를 직접 기록한다.
   - 이번 턴 1차 구현 완료:
     - `llm_stub_used`
     - `fallback_used`
     - `family_override_applied`
     - `llm_failure_class`
   - 남은 일:
     - RESEARCH-stage failure taxonomy까지 health/provenance 필드 전파
     - `provider_health_state`를 stage별 원인과 연결한 richer summary 보강
2. `generator_manifest.json`이 없는 실패 run도 provenance를 잃지 않도록 failure summary surface를 추가한다.
   - 이번 턴 1차 구현 완료:
     - `failure_manifest.json`
   - 남은 일:
     - `manifest.json`과 `failure_manifest.json`의 소비 지점을 CI/ops에서 통합
3. `PACK` gating과 inspection artifact emission을 분리한다.
   - 이번 턴 1차 구현 완료:
     - review block이어도 `failure_manifest.json`은 남김
   - 남은 일:
     - `failure_manifest.json`을 official summary와 reviewer/ops 대시보드까지 연결
4. quota/auth/network/provider-unavailable failure를 구분하는 regression test와 rerun harness를 추가한다.

### 완료 기준

- degraded rerun에서 `provider_health_state`가 실제 failure class와 어긋나지 않는다.
- failed bundle도 `provenance={}` / `dynamicness=unclassified` 대신 근거 있는 class를 가진다.
- review/pack block이 있어도 inspection 가능한 top-level summary artifact가 남는다.

### Phase 1. Performance Stabilization

이 phase는 문서의 첫 번째 전면 실행 트랙이다.
단, `Reliability Floor`와 `Phase 0.5` 완료 후 착수한다.

### 목표

- known static lane의 불필요한 synthesis retry를 줄인다.
- researcher-backed lane의 p95를 낮춘다.
- fail-fast와 structured repair를 통해 retry cost를 줄인다.

### 작업

1. known static lane fast path를 끌어올린다.
   - provider health가 불량할 때 known static lane이 synthesis에 과도하게 의존하지 않도록 경로를 재검토한다.
   - template/hybrid/verified skeleton을 쓸 경우 provenance를 함께 기록한다.
2. researcher skip lane의 first-pass rate를 높인다.
   - prompt/hint를 더 deterministic하게 고정한다.
   - 반복적으로 같은 semantic miss가 나는 lane은 regression asset으로 박는다.
3. loop repair 전략을 바꾼다.
   - dependency, role, contract class 오류는 full regenerate보다 structured patch를 우선한다.
   - full regenerate는 semantic skeleton이 깨졌을 때만 수행한다.
4. LLM health failure를 fail-fast로 분류한다.
   - quota/auth/network/transient를 구분한다.
   - 재시도 가치가 없는 상태에서는 loop budget을 낭비하지 않는다.
5. 성능 측정 필드를 확장한다.
   - `retry_count`
   - `provider_health_state`
   - `llm_stub_used`

### 목표 지표

- known static deterministic lane: p95 30초 이내
- researcher-backed deterministic lane: p95 75초 이내
- known static first-loop success rate: 90% 이상
- runtime rule lane first-loop success rate: 80% 이상

### Phase 2. Degraded-Mode Resilience

### 목표

- provider degraded 시에도 파이프라인이 “의미 있게 전진하거나, 최소한 정확한 failure class를 남기는 상태”를 만든다.

### 작업

1. provider health class를 공식화한다.
   - quota exhausted
   - auth failure
   - network transient
   - provider unavailable
   - search success / llm degraded
2. same-process stub stickiness를 문제 정의에 포함한다.
   - self-consistency와 retry 의미가 사라지지 않도록 LLM health handling policy를 재설계한다.
3. family-aware deterministic fallback skeleton을 확장한다.
   - 이번 턴 1차 구현 완료:
     - SQLi
     - CSRF
     - Template Injection
     - Path Traversal
   - 남은 일:
     - SSRF / XSS / Insecure Deserialization 계열 fallback 여부 정리
     - unknown-sqli-like 및 broader unknown family fallback
     - non-web / multi-stack fallback 여부 검토
4. degraded known lane이 template safety net을 쓰는 경우 provenance를 반드시 남긴다.
5. degraded failure는 아래 둘을 분리 기록한다.
   - search unavailable
   - family-aware synthesis unavailable

### 완료 기준

- remote-required lane은 provider env footgun 없이 정상 설정된다.
- known/static lane 일부는 degraded provider 상태에서도 닫히거나, 닫히지 않으면 정확한 health class를 남긴다.
- degraded mode에서 self-consistency가 형식적 재시도가 아니라 실제 다른 경로를 의미한다.

### Phase 3. Template / Hardcode Dependency Reduction

### 목표

- 현재 시스템이 어떤 정적 도움에 의존하는지 provenance와 dynamicness budget으로 명시한다.
- template reuse와 family override를 dynamic success와 분리한다.

### 작업

1. artifact provenance 필드를 추가한다.
   - 현재 1차 구현 완료:
     - `generation_origin`
     - `family_override_applied`
     - `fallback_used`
     - `llm_stub_used`
     - pack bundle `provenance`
     - top-level `generation_summary`
     - bundle `dynamicness`
     - top-level `generation_summary.by_dynamicness_verdict`
   - 남은 일:
     - failure path (`generator_failures.jsonl`, `loop_state`, `performance_summary`, top-level failure summary)까지 동일 필드 전파
     - official lane summary 및 CI acceptance까지 동일 필드 전파
     - acceptance에서 provenance 기반 분류 사용
2. official lane별 dynamicness budget을 정의한다.
   - 어느 수준의 static aid까지 허용하는지 lane별로 문서화한다.
3. built-in template copy는 문서상 `dynamic synthesis success`로 집계하지 않는다.
4. runtime candidate template clone은 “new synthesis”가 아니라 “template reuse”로 표기한다.
5. contract와 manifest가 template metadata를 source로 쓸 경우 그 사실을 artifact에 남긴다.

### 완료 기준

- official artifact는 모두 provenance를 가진다.
- template-assisted success와 LLM-led dynamic success를 문서와 artifact 양쪽에서 구분할 수 있다.

### Phase 4. Official Lane Reclassification

### 목표

- 현재 official lane을 success 여부만이 아니라 dependency/provenance class로 다시 분류한다.

### 작업

1. official lane을 아래 세 등급으로 재분류한다.
   - `trusted dynamic`
   - `template-assisted`
   - `deterministic fallback dependent`
2. `cwe-unknown-basic`은 free-form `vuln_name only` 증거에서 제외한다.
3. 실제 free-form unknown-name case를 새 acceptance 대상으로 추가한다.
   - 예: 임의 취약점명 기반 `NAME-*` case 최소 1개
4. official lane 문서와 CI matrix를 healthy/degraded 축으로 분리한다.

### 완료 기준

- official lane 목록이 성공/실패만이 아니라 provenance class를 함께 가진다.
- free-form name-only 증거와 synthetic id 증거를 혼동하지 않는다.

### Phase 5. Open-World Generalization

### 목표

- 단일 Python/Flask 컨테이너 편향을 넘는 multi-stack generalization으로 확장한다.

### 작업

1. Node/Express, PHP, Java 최소 1개 lane 확보
2. 외부 DB sidecar 및 multi-container synthesis 정식화
3. non-web scenario type 확장 여부 검토

### 착수 조건

- 단일 스택 lane에서 provenance가 명확하다.
- degraded-mode behavior가 규정되어 있다.
- official lane 분류가 완료되었다.

## 6.1 계획에 포함할 인터페이스 / 스키마 변경

아래 스키마 변경은 위 phase와 별개로 cross-cutting deliverable로 취급한다.

### verifier result schema

- `exploit_pass`
- `semantic_pass`
- `guard_pass`
- `verify_pass`

위 네 필드를 공식 top-level verdict로 고정한다.

### researcher report normalization

- stub/LLM fallback이어도 `vuln_id`가 `UNKNOWN`으로 남지 않도록 canonicalize
- `quality`, `quality_reason`, `search_degraded`와 함께 artifact truth를 유지

### manifest / contract provenance

- `generation_origin`
- `template_id`
- `family_override_applied`
- `fallback_used`

위 필드를 `resolved_contract` 또는 manifest metadata에 기록한다.

### performance summary

기존 stage latency 외에 아래 필드를 공식화한다.

- `retry_count`
- `provider_health_state`
- `llm_stub_used`

현재 `performance_summary.json`에는 위 세 필드의 1차 구현이 반영되었다.
남은 일은 official report/CI summary에서 이를 기준으로 pass/fail 및 degraded classification을 집계하는 것이다.

## 6.2 연계 계획 문서 정합성

이 문서는 verifier/template 독립화 하위 실행 설계인 [eval_refactor_plan.md](/home/ysw/vulDocker/docs/evals/eval_refactor_plan.md)와 다음 관계를 가진다.

- 본 문서의 `Phase 0`, `Phase 0.5`, `Phase 3`는 `eval_refactor_plan.md`의 RuleSpec / EvaluationContext / runtime rule 재사용 방향을 전제로 한다.
- 특히 아래 항목은 두 문서가 같은 방향을 가리켜야 한다.
  - verifier verdict schema 고정
  - runtime rule / RuleSpec / generator guard의 단일 truth source화
  - template metadata와 placeholder 기반 검증으로의 이행
  - hardcoded success string / file path 의존 축소
- 따라서 `gap_analysis` 문서에서 말하는 template/hardcode dependency reduction은
  단순 provenance 표기만이 아니라 `eval_refactor_plan.md`의 RuleSpec 통합이 실제 코드로 닫히는지까지 포함해 판단한다.

## 7. Acceptance Matrix

아래 matrix를 모두 만족해야 이번 단계 완료로 본다.

| 구분 | 최소 acceptance |
| --- | --- |
| Unit tests | `python -m pytest -q tests` 기준 최소 `147 passed, 11 skipped` 유지 또는 상향 |
| E2E truth | 기본 pytest pass와 별개로 필수 live E2E set가 존재해야 함 |
| Verdict truth | nested guard/verifier/semantic failure가 있으면 top-level success 금지 |
| Failure-path provenance | generator failure artifact에도 `llm_stub_used`, `fallback_used`, `family_override_applied`, `provider_health_state`가 남아야 함 |
| Failure artifact availability | review/pack block이 있어도 inspection 가능한 top-level summary artifact가 남아야 함 |
| Researcher normalization | stub researcher report에도 canonical `vuln_id`가 기록되어야 함 |
| Free-form rule loading | `NAME-*` runtime rule writer/loader round-trip 성공 |
| Role normalization | generated manifest canonical role 100% |
| Provider health | remote-required lane이 provider env 누락만으로 실패하지 않아야 함 |
| Degraded mode | known/static lane 일부는 degraded provider 상태에서도 닫히거나, 정확한 failure class를 남겨야 함 |
| Generation provenance | official artifact는 `generation_origin`과 fallback/template usage를 기록해야 함 |
| Template dependency disclosure | template reuse lane은 문서상 dynamic success로 집계하지 않아야 함 |
| Official lanes | healthy-provider 기준 SQLi/CSRF/SSRF/Path Traversal/Template Injection/XSS/Deserialization rerun 보유 |
| Free-form evidence quality | unknown 공식 케이스는 `CWE-9999`가 아니라 실제 free-form `vuln_name` case 최소 1개 포함 |
| Performance | known static p95 <= 30s, researcher-backed p95 <= 75s, known static first-loop success rate >= 90% |

## 8. 이번 문서 갱신에 반영한 실측 검증

### 8.1 테스트

- `python -m pytest -q tests`
  - 결과: `147 passed, 11 skipped`
- targeted verification:
  - `python -m pytest -q tests/test_synthesis_fallback_poc.py tests/test_synthesis_semantic_guard.py tests/test_run_pipeline_failure_resolution.py tests/test_pack_promotion.py tests/test_contract_resolution.py tests/test_researcher_search_artifacts.py`
  - 결과: `45 passed`

### 8.2 fresh rerun

- pre-fix SQLi
  - 입력: fresh plan -> `sid-6247be018b41`
  - 실행: `python orchestrator/run_pipeline.py --sid sid-6247be018b41 --mode deterministic`
  - 결과: OpenAI quota exhausted -> stub/fallback -> GENERATOR 3회 실패 -> failure manifest 기록
  - 관찰: `performance_summary.provider_health_state=healthy`, `llm_stub_used=false`, bundle `provenance={}`로 surface
- pre-fix Template Injection
  - 입력: fresh plan -> `sid-02575fde190d`
  - 실행: `python orchestrator/run_pipeline.py --sid sid-02575fde190d --mode deterministic`
  - 결과: OpenAI quota exhausted -> stub/fallback -> semantic mismatch -> PACK gate failure
  - 관찰: top-level `manifest.json` 미생성
- pre-fix CSRF
  - 입력: fresh plan -> `sid-db1e04270bf4`
  - 실행: `python orchestrator/run_pipeline.py --sid sid-db1e04270bf4 --mode deterministic`
  - 결과: OpenAI quota exhausted -> stub/fallback -> state-changing endpoint missing -> PACK gate failure
  - 관찰: known static lane도 degraded 시 low survivability로 재확인
- post-fix SQLi
  - 입력: fresh plan -> `sid-5a5277a8aeda`
  - 실행: `python orchestrator/run_pipeline.py --sid sid-5a5277a8aeda --mode deterministic`
  - 결과: OpenAI quota exhausted -> deterministic fallback -> build/run/verify/review/pack pass
  - 관찰: `status=success`, `provider_health_state=llm_degraded`, `llm_failure_class=quota_exhausted`
- post-fix CSRF
  - 입력: fresh plan -> `sid-91c772b15bb1`
  - 실행: `python orchestrator/run_pipeline.py --sid sid-91c772b15bb1 --mode deterministic`
  - 결과: OpenAI quota exhausted -> deterministic fallback -> build/run/verify/review/pack pass
  - 관찰: degraded known static lane이 loop 1에서 닫힘
- post-fix Template Injection
  - 입력: fresh plan -> `sid-6210ffdbeb5b`
  - 실행: `python orchestrator/run_pipeline.py --sid sid-6210ffdbeb5b --mode deterministic`
  - 결과: OpenAI quota exhausted -> deterministic fallback + family override -> build/run/verify/review/pack pass
  - 관찰: `dynamicness=deterministic fallback dependent`, reviewer blocking 없음
- failure-summary validation
  - 입력: fresh plan -> `sid-269fb6724565` (`CWE-9999`)
  - 실행: `python orchestrator/run_pipeline.py --sid sid-269fb6724565 --mode deterministic`
  - 결과: RESEARCH low relevance fail
  - 관찰: pack block 이후에도 `failure_manifest.json` 생성 확인

### 8.3 이번 세션에서 다시 확인한 positive fact

- `researcher_report.vuln_id` canonicalization은 세 fresh rerun에서 모두 유지되었다.
- `search_health.json`은 세 rerun 모두 Tavily remote success(`remote_result_count=9`, `last_status_code=200`)를 기록했다.
- post-fix rerun에서는 SQLi / CSRF / Template Injection이 모두 `llm_degraded` 상태에서 deterministic fallback path로 loop 1 pass했다.
- unknown synthetic lane은 여전히 실패했지만 `failure_manifest.json`이 남아 inspection summary emission이 개선된 것이 확인되었다.
- 즉 현 시점 핵심 병목은 “known degraded lane collapse”보다 “unknown/free-form evidence quality”, “official provenance-aware reporting”, “broader family coverage” 쪽으로 이동했다.

## 9. 문서 운영 규칙

이 문서는 이후 아래 규칙으로 유지한다.

- speculative statement를 쓰지 않는다.
- `pass`, `stable`, `eligible`, `dynamic` 같은 표현은 provider condition과 provenance를 함께 적는다.
- 상태 서술과 계획 서술을 분리한다.
- template clone, scaffold overwrite, deterministic fallback은 별도 표기한다.
- healthy-provider success와 degraded-provider failure가 공존하면 문서 요약문은 더 낮은 운영 완성도를 기준으로 쓴다.
- official unknown lane은 real free-form `vuln_name only` case가 생기기 전까지 generalization success 근거로 쓰지 않는다.

## 10. 즉시 착수 work package

지금 바로 시작할 work package는 아래 순서로 고정한다.

1. `Reliability Floor` 잔여 항목 완료
   - verifier/reviewer/pack truth rerun 재검증
   - stub researcher `vuln_id` normalization rerun 검증
   - `exploit_pass / semantic_pass / guard_pass / verify_pass` schema 고정
2. `Failure-Path Truth & Degraded Provenance` 완료
   - `generator_failures.jsonl` / `loop_state` / `performance_summary` 필드 확장
   - top-level failure summary artifact 도입
3. degraded-mode resilience 구현
   - provider health class
   - family-aware fallback skeleton 확장
   - degraded provenance 기록
4. known static lane 성능 개선 착수
   - fast path pull-up
   - 불필요한 synthesis retry 축소
   - fail-fast health classification 도입
5. template / hardcode provenance 도입
   - `generation_origin`
   - `family_override_applied`
   - `fallback_used`
   - `llm_stub_used`
   - pack surface / dynamicness verdict 확장 후 official lane/CI summary 연결
6. official lane reclassification
   - `trusted dynamic`
   - `template-assisted`
   - `deterministic fallback dependent`
7. free-form unknown-name case 추가
   - `CWE-9999`가 아닌 real `vuln_name -> NAME-*` case 확보
8. 그 다음 open-world generalization 착수

## 11. 한 문장 요약

현재 레포는 `취약점 이름만 제공 -> 취약 Docker 생성` 방향성 자체는 부분적으로 구현했지만,
현 시점의 핵심 과제는 family 확장보다 먼저 `healthy/degraded 운영 하한선 정직화`, `failure-path truth/provenance 고정`, `degraded-mode resilience 확보`, `template/하드코딩 의존 공개`, `Reliability Floor 완료`를 통해 생성 성공과 산출물 신뢰성을 다시 일치시키는 것이다.
