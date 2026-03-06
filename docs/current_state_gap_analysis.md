# CWE 일반화 중심 구현계획 및 현재 상태

본 문서는 더 이상 "현재 상태 분석 메모"에 머무르지 않는다. 목적은 다음 네 가지를 동시에 만족하는 실행 문서가 되는 것이다.

- 현재 구현 상태를 과장 없이 요약한다.
- CWE 일반화 가능성을 구조적으로 평가한다.
- 잔여 미비점과 우선순위를 명시한다.
- 다음 구현 단계와 완료 기준을 decision-complete 수준으로 제시한다.

기준 시점은 2026-03-06이며, 본 문서의 상태 판정은 가능한 한 현재 코드와 실제 실행 결과를 기준으로 한다.

## 1. 현재 상태 요약

현재 레포는 "동적 취약 Docker 생성"의 핵심 골격은 갖췄고, known CWE와 unknown CWE 모두에서 단발 end-to-end 성공 사례를 확보했다. 하지만 아직 반복 재현성, 초기 contract ownership, semantic generalization, 운영 자동화가 부족하므로 "안정적인 일반화 엔진"이라고 보기는 어렵다.

현재 코드에 이미 반영된 핵심 사항:

- `effective_vuln_ids_digest` 기반 SID 격리
- `resolved_contract.json` / `generator_contract.json` 계약 로더/미러링
- GuardSpec canonicalization / validation
- generator-facing Guard trust boundary 강화
- reviewer non-blocking quality issue 정책
- Python local module dependency false positive 제거
- `custom|tavily` 기준 search provider abstraction 1차 구현
- `search_health.json`, `search_traces/`, `search_degraded`, `search_health_path` 연동

현재 운영/일반화 측면의 핵심 잔여 문제:

- known `cwe-89-basic`은 1회 pass했지만 반복 안정화는 아직 미검증
- unknown `cwe-9999`는 live Tavily로 1회 pass했지만 운영 자동화와 regression gate는 없음
- `resolved_contract.json`은 여전히 generator 성공 후에야 확정된다
- semantic evaluator는 여전히 `CWE-89`, `CWE-352` 중심이다
- Tavily 키는 `config/api_keys.ini`에 있어도 아직 자동 로드되지 않는다
- `brave`, `searxng` adapter와 search filter surface는 아직 미구현이다

상태를 한 줄로 요약하면 다음이 가장 정확하다.

- "핵심 인프라는 더 갖춰졌지만, 반복 재현성과 운영 자동화, semantic generalization이 아직 부족한 프로토타입"

## 2. 현재 구현 상태의 사실 정리

### 2.1 known path: `cwe-89-basic`

현재 확인된 사실:

- Guard trust boundary 보정 이후 deterministic known case 1회 end-to-end pass 사례가 있다.
- 해당 실행에서는 Researcher, Generator, Executor, Verifier, Reviewer, Pack까지 완료되었다.
- `metadata/sid-b36ff41a638a` 아래에 다음 산출물이 존재한다.
  - `researcher_report.json`
  - `guard_spec.json`
  - `resolved_contract.json`
  - `manifest.json`

현재 해석:

- known path는 더 이상 "구조적으로 막힌 상태"는 아니다.
- 하지만 "안정화되었다"라고 쓰기에는 증거가 부족하다.
- 단발 성공은 재현성의 증거가 아니라 가능성의 증거다.

### 2.2 unknown path: `cwe-unknown-basic`

현재 확인된 사실:

- provider 미구성 상태에서는 `remote_required` 정책 때문에 RESEARCHER 단계에서 hard fail한다.
- live Tavily를 env로 주입하면 deterministic unknown case 1회 end-to-end pass 사례가 있다.
- `metadata/sid-d2ff12df4e6d` 아래에 다음 산출물이 존재한다.
  - `search_health.json`
  - `researcher_report.json`
  - `guard_spec.json`
  - `resolved_contract.json`
  - `manifest.json`

현재 해석:

- unknown path는 더 이상 "search provider가 없어서 설계상 불가능"한 상태가 아니다.
- 다만 "운영 가능한 기본 경로"라고 보기에는 자동 credential 로딩, live regression, 추가 provider, semantic validation이 부족하다.

### 2.3 search/provider 상태

현재 구현 완료 범위:

- `VUL_WEB_SEARCH_PROVIDER=custom|tavily`
- `VUL_WEB_SEARCH_API_KEY`
- `VUL_WEB_SEARCH_BASE_URL`
- `VUL_WEB_SEARCH_ENDPOINT`
- `search_health.json`
- `search_traces/*`
- `search_degraded`

현재 미완료 범위:

- `config/api_keys.ini`의 `[tavily]` 섹션 자동 로딩
- `brave`, `searxng` adapter
- live provider 기반 CI/regression
- `SearchRequest`의 고급 필터 필드 노출
- raw payload full snapshot 저장 여부 확정

### 2.4 현재 상태 판단 시 주의할 점

분석에는 시점이 다른 metadata가 섞여 있다. 따라서 다음 원칙을 따른다.

- 현재 상태의 1차 근거는 최신 실행이 반영된 `metadata/sid-b36ff41a638a`, `metadata/sid-d2ff12df4e6d`
- pre-fix artifact는 historical note로만 사용
- "현재 구현"과 "당시 실패 상태"를 문장 단위로 분리해 쓴다

## 3. CWE 일반화 가능성 평가

이 섹션은 "새 CWE를 레포에 추가하지 않고도 얼마나 일반화가 가능한가"를 구조적으로 평가한다.

### 3.1 Evidence Acquisition

현재 상태:

- search/provider는 이제 unknown path를 여는 enabler 역할까지는 확보했다.
- `custom|tavily` 기준으로 remote evidence 수집, health 기록, degraded fallback 기록이 가능하다.
- live Tavily 기준 unknown full pipeline 1회 성공도 확인했다.

잔여 문제:

- Tavily credential 자동 로딩이 없다.
- live provider regression이 자동화돼 있지 않다.
- `brave`, `searxng`가 없어 provider 다양성과 운영 선택지가 좁다.
- domain/time/language filter가 call-site에서 적극 활용되지 않는다.

평가:

- Evidence acquisition은 일반화의 primary blocker에서 내려왔다.
- 이제 이 영역은 "운영 자동화 부족" 문제에 가깝다.

### 3.2 Semantic Representation

현재 상태:

- builtin semantics는 `CWE-89`, `CWE-352`에 편중되어 있다.
- unknown CWE는 semantic_match가 사실상 bypass되며, contract/evidence 중심으로 판정되는 경향이 강하다.
- Researcher는 `semantic_signature`를 생성하지만, unknown CWE에서 이것이 verifier/reviewer/generator 전반의 강한 shared semantics로 작동한다고 보기는 어렵다.

잔여 문제:

- `vuln_semantics.json` 또는 동등한 structured schema가 없다.
- unknown CWE의 input/sink/unsafe-composition/effect를 stage 공통 언어로 고정할 수 없다.
- 그 결과 unknown path는 "exploit contract만 맞으면 pass"에 가까워질 위험이 있다.

평가:

- 일반화의 핵심 구조적 병목이다.
- search quality가 좋아져도 semantics가 비어 있으면 CWE 일반화 품질은 제한된다.

### 3.3 Contract Ownership

현재 상태:

- downstream consumer는 `resolved_contract.json`을 잘 읽는다.
- 그러나 authoritative contract는 generator 성공 후에야 확정된다.
- Researcher는 여전히 raw `verification_spec`와 자체 `flag_token`/success marker를 제안할 수 있다.

잔여 문제:

- pipeline 초반에는 stage들이 완전히 동일한 성공 계약을 공유하지 못한다.
- unknown CWE에서 provider가 열려도, success contract ownership이 늦게 확정되면 drift와 해석 차이가 다시 생긴다.

평가:

- 일반화 관점의 최상위 구조 병목이다.
- evidence와 semantics보다 먼저, "무엇을 성공으로 볼 것인가"가 초반에 고정돼야 한다.

### 3.4 Synthesis Strategy

현재 상태:

- full-app synthesis가 여전히 중심이다.
- known/unknown 모두 end-to-end 성공 사례는 생겼지만, variance가 높다.
- 앱 구조, Docker, state path, PoC, vuln pattern을 한 번에 맞추는 방식은 일반화 시 불안정성이 커진다.

잔여 문제:

- scaffold와 vuln insertion이 분리되어 있지 않다.
- "취약점 삽입"보다 "전체 앱 생성"이 더 큰 search space를 만든다.
- 일반화 대상 CWE가 늘수록 variance가 빠르게 커진다.

평가:

- 중장기 핵심 과제다.
- 일반화 품질을 근본적으로 끌어올리려면 scaffold + vuln patch 구조로 가야 한다.

### 3.5 Evaluation and Regression

현재 상태:

- known `cwe-89-basic` 1회 pass
- unknown `cwe-9999` live Tavily 1회 pass
- provider unit test / search artifact test는 존재

잔여 문제:

- known 반복 gate가 없다.
- live unknown regression이 자동화되지 않았다.
- CWE family별 smoke matrix가 없다.
- "1회 성공"을 "일반화 가능"과 혼동할 여지가 있다.

평가:

- 일반화의 증명은 아직 부족하다.
- 현재 수준은 "실험 가능"이지 "일반화 달성"이 아니다.

### 3.6 일반화 관점 최종 결론

현재 일반화 가능성은 다음처럼 표현하는 것이 맞다.

- "현재 일반화 가능성은 실험 가능 수준이다."
- "구조적 일반화의 핵심 병목은 provider 자체보다 contract/semantics/synthesis에 있다."

## 4. 핵심 병목 및 우선순위

현재 구현과 최근 실검증을 기준으로, 보완 우선순위는 다음 순서가 가장 합리적이다.

### 4.1 1순위: authoritative contract를 pipeline 초반에 고정

이유:

- `resolved_contract.json`이 generator 성공 후에만 확정되면 early-stage drift를 막기 어렵다.
- Researcher가 raw `verification_spec`를 제안하는 구조와 결합되면 generalization 시 success/flag ownership이 흔들린다.
- 일반화 관점에서 search/provider보다 더 직접적인 병목이다.

### 4.2 2순위: known/unknown 반복 회귀 게이트 추가

이유:

- known 1회 pass와 unknown 1회 pass는 가능성만 보여준다.
- 일반화 가능성을 주장하려면 최소한 known 반복 gate와 live unknown regression이 자동화되어야 한다.
- 기준선이 없으면 이후 개선 효과를 측정할 수 없다.

### 4.3 3순위: dynamic semantics 도입

이유:

- unknown CWE의 vuln-class alignment를 현재는 보장하지 못한다.
- 일반화의 quality bottleneck은 evidence보다 semantic representation이다.
- `vuln_semantics.json` 또는 동등 schema는 일반화의 핵심 토대가 된다.

### 4.4 4순위: Tavily credential 자동 로딩 + live provider 운영 자동화

이유:

- search/provider는 이미 1차 구현 완료 상태다.
- 남은 문제는 기능 부재가 아니라 운영 편의와 regression 자동화다.
- 이 영역을 보완하면 unknown path를 기본 운영 경로로 올릴 수 있다.

### 4.5 5순위: repeated-failure aware loop 제어

이유:

- 같은 failure fingerprint가 반복될 때 전략 전환이 늦다.
- 일반화 시도에서는 실패 양상이 다양해지므로 loop 효율이 더 중요해진다.

### 4.6 6순위: Brave/SearxNG + search filter surface

이유:

- provider 다양성과 filter surface는 가치가 있다.
- 그러나 지금은 primary blocker가 아니다.
- contract/semantics/automation이 먼저다.

### 4.7 7순위: scaffold + vuln patch 아키텍처

이유:

- 장기적으로는 가장 큰 품질 개선 포인트다.
- 다만 현재는 baseline automation과 contract/semantics 정렬이 먼저다.

## 5. Track 기반 개선 로드맵

Phase 단일 나열보다, 지금은 두 개의 독립 축으로 보는 편이 구현 우선순위를 더 명확하게 만든다.

### Track A: 운영 안정화

목표:

- known/unknown 경로를 현재보다 더 일관되게 재현하고, 실사용 가능한 기본 운영 경로를 만든다.

구성:

1. 문서 정합화
2. Tavily ini 자동 로딩
3. live unknown regression 자동화
4. known `cwe-89` 3회 gate

운영 안정화 완료 기준:

- Tavily 키가 env 수작업 없이 자동 인식된다.
- live unknown regression이 자동 통과한다.
- known `cwe-89-basic` 3회 연속 pass가 확보된다.

### Track B: 구조적 일반화

목표:

- unknown CWE를 "evidence만 맞는 번들"이 아니라 "의미적으로 일치하는 번들"로 끌어올린다.

구성:

1. early contract seed
2. `verification_spec -> proposed_verification_contract`로 의미 격하
3. `vuln_semantics.json` 도입
4. repeated-failure loop
5. scaffold + vuln patch 아키텍처

구조 일반화 완료 기준:

- unknown CWE에서 semantic layer가 no-op가 아니다.
- success/flag drift가 stage 간 0회다.
- 동일 failure fingerprint 반복 빈도가 감소한다.

## 6. 명시해야 할 인터페이스와 정책

이 문서는 구현자가 추가 판단 없이 작업할 수 있도록, 현재/다음 인터페이스를 고정해서 기술한다.

### 6.1 현재 구현 인터페이스

- `VUL_WEB_SEARCH_PROVIDER=custom|tavily`
- `VUL_WEB_SEARCH_API_KEY`
- `VUL_WEB_SEARCH_BASE_URL`
- `VUL_WEB_SEARCH_ENDPOINT`
- `search_health.json`
- `search_traces/*`
- `search_degraded`
- `search_health_path`

### 6.2 다음 구현 인터페이스

- `common/config/api_keys.py`에 Tavily key loader 추가
- `resolved_contract.json` early seed
- `proposed_verification_contract` 명명
- `vuln_semantics.json` 스키마

### 6.3 `vuln_semantics.json` 최소 필드

문서에서 이 최소 스키마를 고정한다.

- `input_sources`
- `sink_patterns`
- `unsafe_composition_patterns`
- `required_effect`

예시:

```json
{
  "input_sources": ["request.args", "request.form", "stdin", "query string"],
  "sink_patterns": ["cursor.execute", "subprocess.run", "open", "exec"],
  "unsafe_composition_patterns": ["string concat", "f-string", "shell=True", "unescaped path join"],
  "required_effect": ["multiple rows returned", "command output reflected", "file content disclosure"]
}
```

## 7. 구현 단계별 상세 계획

### 7.1 즉시 보완 1: Tavily credential 자동 로딩

문제:

- Tavily 키가 `config/api_keys.ini`에 있어도 자동 로드되지 않는다.

구현:

- `common/config/api_keys.py`에 `get_tavily_api_key()` 추가
- `rag/tools/web_search.py`에서 env에 `VUL_WEB_SEARCH_API_KEY`가 없으면 ini fallback 사용
- `ops/tools/enable_live_pipeline_env.sh`도 ini 기반 Tavily 기본값을 읽을 수 있게 정리

완료 기준:

- `config/api_keys.ini`의 `[tavily] api_key`만 있어도 `WebSearchTool(provider='tavily')`가 live 호출 가능

### 7.2 즉시 보완 2: live unknown regression 자동화

문제:

- unknown live pass는 수동 검증만 존재한다.

구현:

- `tests/e2e/`에 provider-aware unknown live smoke 추가
- Tavily key 없으면 skip, 있으면 실행
- summary에서 `verify_pass`, `run_passed`, `blocking_bundles`를 검증

완료 기준:

- live unknown regression이 pytest/CI에서 자동 검증 가능

### 7.3 즉시 보완 3: known 반복 재현성 gate

문제:

- known path는 pass 사례만 있고 반복 gate가 없다.

구현:

- `ops/ci/` 또는 `tests/e2e/`에 `cwe-89-basic` 3회 반복 스크립트/테스트 추가
- 실행마다 `failure stage`, `failure_fingerprint`, `guard mismatch`를 수집

완료 기준:

- known path 3회 연속 pass 또는 failure fingerprint가 명시적으로 집계됨

### 7.4 구조 보완 1: early contract seed

문제:

- 현재 성공 계약의 authoritative owner가 너무 늦게 정해진다.

구현:

- PLAN 또는 RESEARCH 직후 `resolved_contract.json` seed 생성
- 최소 필드:
  - `success_signature`
  - `flag_token`
  - `output_mode`
  - `service_entry`
  - `poc_entry`
  - `service_port`
  - `base_url`
- Researcher의 `verification_spec`는 authoritative field가 아니라 proposal로 격하

완료 기준:

- generator 실패 전 단계에서도 contract artifact가 존재
- stage 간 success/flag drift 축소

### 7.5 구조 보완 2: dynamic semantics

문제:

- unknown CWE는 semantic no-op에 가깝다.

구현:

- Researcher가 `vuln_semantics.json` 생성
- generator guard, verifier, reviewer가 동일 semantics payload를 사용
- known CWE는 builtin semantics 유지, unknown은 dynamic fallback 사용

완료 기준:

- unknown CWE의 semantic 판정이 exploit-contract-only가 아님

### 7.6 구조 보완 3: repeated-failure aware loop

문제:

- 동일 failure fingerprint 반복 시 전략 전환이 늦다.

구현:

- 최근 fingerprint window를 보고 same failure 반복 시:
  - guard relaxation
  - researcher refresh
  - fallback spec
  중 하나로 전환
- "autofix applied but same fingerprint repeated"를 metadata에 기록

완료 기준:

- 동일 fingerprint 3연속 반복 감소

### 7.7 확장 보완: Brave/SearxNG + filter surface

문제:

- provider 다양성과 search precision이 제한된다.

구현:

- `brave.py`, `searxng.py` adapter 추가
- `SearchRequest`의 `include_domains`, `exclude_domains`, `time_range`, `country`, `search_lang`를 Researcher query generation 또는 provider request build 쪽에 노출

완료 기준:

- provider 선택 폭 확대
- search precision 제어 가능

## 8. Test / Validation

### 8.1 이미 수행된 검증

- provider unit tests
- search artifact tests
- known `cwe-89-basic` 1회 pass
- unknown `cwe-9999` live Tavily 1회 pass

### 8.2 앞으로 필요한 검증

- known `cwe-89-basic` 3회 연속 pass
- live Tavily unknown regression CI
- early contract seed 적용 후 success/flag drift regression
- unknown CWE 3종 이상 family smoke

### 8.3 정량 기준

단기 기준:

- known `cwe-89-basic` 3회 연속 pass
- live unknown regression 1회 이상 자동 통과
- provider 미구성 시 health artifact 경로 포함 실패
- Tavily ini 자동 로딩 성공

중기 기준:

- unknown smoke 3종 이상
- semantic no-op 제거
- contract drift 0회
- 동일 failure fingerprint 반복 감소

## 9. 최종 정리

현재 구현은 CWE 일반화에 대해 다음 수준까지는 올라왔다.

- known/unknown 각각 단발 end-to-end 성공 사례 확보
- search/provider 1차 구현 완료
- unknown path를 설계상 불가능 상태에서 실험 가능 상태로 전환

하지만 아직 다음 수준에는 도달하지 못했다.

- 반복적으로 재현 가능한 일반화
- semantic alignment가 내장된 일반화
- 초기 contract ownership이 보장된 일반화
- 운영 자동화가 갖춰진 일반화

따라서 다음 구현은 search provider 자체를 더 붙이는 것보다, 아래 순서를 따르는 것이 합리적이다.

1. early contract seed
2. known/unknown 회귀 gate
3. dynamic semantics
4. Tavily 자동 로딩 및 운영 자동화
5. repeated-failure loop
6. Brave/SearxNG + filter surface
7. scaffold + vuln patch

이 문서는 이후 구현 작업의 기준 문서로 유지한다.
