# 동적 취약 Docker 생성 개선 계획

본 문서는 2026-03-07 KST 기준의 검토 결과와 fresh rerun 결과를 토대로 작성한 실행계획 문서다.
이 문서는 더 이상 "현재 상태 회고" 중심 문서가 아니라, 다음 구현 단계를 구체적으로 정의하는 계획 문서다.

핵심 대전제는 유지한다.

- 사용자 입력은 최종적으로 `취약점 이름만` 제공하는 형태까지 허용해야 한다.
- 시스템은 LLM/RAG/Guard/Verifier를 사용해 취약점을 동적으로 삽입한 Docker 환경을 생성해야 한다.
- 방향성을 "정적 템플릿 카탈로그만 고르는 시스템"으로 후퇴시키지 않는다.
- 다만 "생성 성공"과 "검증/승격 신뢰성"은 별개의 축으로 평가해야 한다.

## 1. 문서 목적

이 문서의 목적은 네 가지다.

1. 현재 구현이 실제로 어디까지 닫혀 있는지 verified baseline을 고정한다.
2. 이번 검토에서 확인된 구조적 결함을 우선순위 순으로 정리한다.
3. `vuln_name -> dynamic vulnerable Docker synthesis`라는 초기 방향을 유지한 채, 다음 구현 단계를 단계적으로 정의한다.
4. 이후 구현이 "pass rate 증가"에만 치우치지 않고 "artifact trust 증가"까지 달성하도록 acceptance 기준을 명확히 한다.

## 2. 비가역 원칙

이 문서 이후의 구현은 아래 원칙을 깨지 않아야 한다.

### 2.1 입력 원칙

- `vuln_id`가 명시된 입력은 계속 지원한다.
- `vuln_name`만 주어진 minimal input도 1급 입력으로 지원한다.
- `NAME-*` synthetic identifier는 free-form 취약점명을 plan 단계에 태우기 위한 공식 메커니즘으로 유지한다.

### 2.2 생성 원칙

- Docker 환경은 실행 가능한 취약 서비스 + PoC + 빌드/실행 메타데이터까지 동적으로 생성해야 한다.
- researcher/guard/verifier는 생성된 환경이 "실제로 그 취약점인지"를 확인하는 장치여야 하며, 생성 자체를 카탈로그 선택 문제로 축소해서는 안 된다.
- 템플릿은 fast path 또는 fallback으로 활용할 수 있지만, system capability의 정의는 "템플릿 유무와 무관하게 동적 합성 가능"이어야 한다.

### 2.3 검증 원칙

- `exploit succeeds`는 필요조건이지 충분조건이 아니다.
- `verify_pass`, `review_pass`, `promotion_eligible`는 모두 semantic/guard/contract 정합성을 반영해야 한다.
- nested failure를 evidence 문자열에만 남기고 top-level 성공으로 승격시키는 동작은 제거한다.

## 3. 2026-03-07 기준 verified baseline

이번 검토에서 직접 확인한 항목은 아래와 같다.

### 3.1 테스트 스위트

- `python -m pytest -q tests`
- 결과: `132 passed, 10 skipped`

### 3.2 직접 rerun한 lane

| lane | 입력 형태 | 결과 | loop | 총 소요 | 비고 |
| --- | --- | --- | --- | --- | --- |
| SQLi | `sqli-name-only` | pass | 2 | 약 52s | loop 1에서 guard miss 발생 후 loop 2 성공 |
| CSRF | `csrf-name-only` | pass | 1 | 약 35s | known static lane |
| SSRF | `ssrf-name-only` | pass | 1 | 약 22s | known static lane |
| Path Traversal | `vuln_name: Path Traversal` | pass | 1 | 약 58s | researcher-backed runtime rule lane |
| Template Injection | `vuln_name: Template Injection` | pass | 1 | 약 68~73s | official E2E case 추가, fresh rerun 기준 loop 1 pass 확인 |
| Reflected XSS | `vuln_name: Reflected XSS` | pass | 1 | 약 59s | official E2E case 추가 및 expectations satisfied 확인 |

이번 검토에서는 `unknown live rerun`은 재실행하지 않았다.
따라서 unknown noisy evidence lane의 상태는 이전 artifact와 코드 구조를 참고하되, 이번 문서에서는 우선순위만 정의하고 상태를 과도하게 단정하지 않는다.

### 3.3 착수 직후 반영된 작업

이번 계획 문서 작성 직후 아래 작업을 실제로 반영했다.

- Phase 0 `verdict truth repair` 1차 구현
  - verifier가 nested guard failure를 더 이상 evidence 문자열로만 남기지 않고 `verify_pass=false`로 반영
  - reviewer가 nested verifier guard failure를 blocking issue로 승격
  - pack promotion이 nested `guard_consistency` / `semantic_consistency` failure를 차단
- Phase 1 `NAME-* runtime rule filename normalization` 1차 구현
  - rule loader가 `NAME-*` synthetic identifier를 `name-*.yaml`로 직접 해석
  - researcher runtime rule writer가 loader와 같은 filename normalization을 사용
- Phase 2 `role canonicalization` 1차 구현
  - `server -> service_main`
  - `verifier -> poc_entry`
  alias를 researcher normalization / synthesis manifest parsing / contract resolution / guard engine / reviewer / verifier에 공통 반영
- dependency/semantic guard 안정화 1차 구현
  - guard engine `dep_declared`가 `requirements.txt` 선언도 읽도록 보강
  - template-injection exploit precondition을 semantic alias로 인정하도록 보강
- Template Injection low-loop stabilization 1차 구현
  - generated `poc.py`를 deterministic template-injection verifier 형태로 안정화
  - success 시 `49`, success signature, optional flag token을 함께 출력하도록 보강
- Phase 4 일부 착수
  - `tests/e2e/cases/template-injection-name-only/` official case 추가
  - `tests/e2e/cases/xss-name-only/` official case 추가
  - pytest e2e entry 추가
  - `Template Injection` repeatability gate pytest entry 추가
  - `ops/ci/run_repeatability_gate.sh`를 case path 인자 지원 형태로 일반화
- 관련 테스트 추가 후 전체 테스트 재실행
  - `132 passed, 8 skipped`
- 기존 false-positive artifact 재검증
  - 대상 SID: `sid-86dba9eb7da8` (`Template Injection`)
  - 수정 후 `VERIFY` 재실행 결과: `overall_pass=false`
  - 수정 후 `REVIEW` 재실행 결과: `blocking_bundles=["name-template-injection"]`
  - 수정 후 `PACK` 재실행 결과: `last_result=failure`로 차단
  - 추가 검증: 동일 SID에서 `VERIFY` 재실행 시 더 이상 `generator_manifest fallback rule` 경로로 판정되지 않음
- existing alias artifact recheck
  - 대상 SID: `sid-319953f83d00` (`Path Traversal`)
  - role alias가 들어간 기존 artifact에 대해 `VERIFY` 재실행 결과: `overall_pass=true`
- official Template Injection case 검증
  - `tests/e2e/cases/template-injection-name-only`
  - `run_case` 기준 expectations satisfied 확인
  - 추가 fresh rerun 기준 loop 1 pass 확인
  - `repeat_case` 3회 반복 실행 결과 `success_count=3`, `failure_count=0`
- official XSS case 검증
  - `tests/e2e/cases/xss-name-only`
  - `run_case` 기준 expectations satisfied 확인

즉, P0와 Phase 1, Phase 2 core normalization, 그리고 Phase 4의 `Template Injection/XSS officialization`, `Template Injection` 1차 low-loop stabilization, repeatability gate wiring까지는 코드 반영이 완료되었다.
다만 아직 full rerun 기준 free-form lane 전체 재검증과 CI regression officialization은 남아 있다.

## 4. 현재 상태 판정

현재 레포는 이전 문서가 기술하던 상태보다 기능적으로는 더 전진해 있다.
하지만 검증 신뢰성 관점에서는 여전히 치명적인 결함이 남아 있다.

### 4.1 구현 완성도

- known static name-only lane(SQLi/CSRF/SSRF): `중상`
- known-but-ruleless lane(Path Traversal/XSS): `중상에 근접`
- free-form `NAME-*` generation capability: `중간 이상`
- free-form `NAME-*` verification/promotion trust: `중하 -> 중간`
- open-world multi-stack generalization: `낮음`

### 4.2 성능 판정

- Docker build/run/verify 자체는 상대적으로 빠르다. 대체로 2~6초 안쪽이다.
- 병목은 `RESEARCH`와 `GENERATOR`다.
- researcher가 붙는 lane은 `RESEARCH`만 약 39초가 소요된다.
- known static lane도 generator retry가 한 번만 발생하면 총 시간이 바로 50초대로 상승한다.
- free-form official case(`Template Injection`)는 fresh rerun 기준 loop 1에서도 닫힌다.
- `Template Injection` repeatability gate 3회 반복 실행도 현재는 통과했다.

### 4.3 산출물 품질 판정

- semantic contract 생성 품질은 이전보다 좋아졌다.
- top-level `success/promotion`이 nested guard/verifier failure를 무시하던 P0 결함은 이번 턴에 1차 수정이 반영되었다.
- 다만 아직 full rerun/CI 기준으로 모든 lane에 대해 재검증이 끝난 상태는 아니다.
- 따라서 현재 상태를 "artifact trust까지 충분히 안정화되었다"고 해석하면 안 된다.

## 5. 이번 검토에서 확인된 핵심 구조 결함

### 5.1 P0 결함: guard/verifier failure가 top-level success를 막지 못한다

상태: `1차 수리 완료, 회귀 고정/전체 rerun 재검증 남음`

수정 전에는 다음과 같은 잘못된 성공 경로가 존재했다.

- verifier 내부에서 guard inconsistency가 발생해도
- evidence 문자열에만 경고가 남고
- `verify_pass=true`
- reviewer clean
- promotion eligible
로 끝날 수 있다.

실제 예:

- `Template Injection` rerun (`sid-86dba9eb7da8`)
- `guard_consistency.verifier.passed=false`
- `violations=["verifier assertion failed (contains): substring=missing: 49"]`
- 그럼에도 `overall_pass=true`, reviewer clean, promotion eligible

이 결함은 이번 턴에서 1차 수정이 반영되었고, 이제 남은 일은 regression 고정과 전체 lane 재검증이다.

### 5.2 P0 결함: `NAME-*` runtime rule이 실제 로드되지 않는다

상태: `1차 수리 완료, free-form lane 전체 재검증 남음`

free-form lane의 runtime rule writer와 loader가 같은 naming rule을 공유하지 않는다.

- writer는 `name-template-injection.yaml`처럼 기록한다.
- loader는 non-CWE id를 `cwe-name-template-injection.yaml`로 해석한다.

수정 전 결과:

- `NAME-*` family는 researcher가 runtime rule을 생성해도
- verify 단계에서 그 rule을 직접 쓰지 못하고
- generator manifest fallback rule에 의존하게 된다.

이번 턴에서 filename normalization을 1차 수정했으므로, 이제 남은 일은 free-form lane 전체 rerun과 regression case 고정이다.

### 5.3 P1 결함: role vocabulary가 stage마다 다르다

상태: `1차 수리 완료, 비정형 파일명/전체 lane rerun 재검증 남음`

현재 pipeline의 canonical role은 사실상 다음 둘이다.

- `service_main`
- `poc_entry`

하지만 실제 생성물과 guard spec은 다음 role을 쓰는 경우가 있다.

- `server`
- `verifier`

이 문제는 즉시 실패로 드러나지 않을 수 있다.
왜냐하면 일부 stage는 fallback으로 `app.py`/`poc.py`를 사용하기 때문이다.
하지만 파일명이 비정형으로 바뀌는 순간 contract resolution, rule placeholder resolution, reviewer scan이 서로 다른 파일을 보게 된다.

이번 턴에서 alias normalization의 1차 구현이 반영되었고, 이제 남은 일은 비정형 파일명 lane과 full rerun 기준 재검증이다.

### 5.4 P1 결함: runtime assertion success가 semantic/guard 검사를 shortcut한다

runtime rule에 assertion program이 있으면 verify가 조기 성공할 수 있다.
그 결과 일부 lane에서는 eval evidence가 사실상 substring pass에 가까워진다.

이 동작은 다음 문제를 만든다.

- semantic consistency가 항상 기록되지 않는다.
- guard consistency가 항상 top-level verdict에 반영되지 않는다.
- reviewer가 보완하더라도 exploit 성공 시 non-blocking으로 낮춰지는 경로가 남는다.

즉 현재 verify는 "exploit success detector"로는 동작하지만, 항상 "contract/trust gate"로 동작하지는 않는다.

### 5.5 P1 결함: free-form official lane의 low-loop repeatability가 아직 약하다

상태: `공식 case 추가 + 1차 low-loop 안정화 + repeatability gate 통과, 장기 안정성 관찰 남음`

현재 `Template Injection`은 official case로 승격되었지만, 다음 특성이 남아 있다.

- fresh rerun 기준 loop 1 pass를 확보했고, 3회 repeatability gate도 통과했다.
- free-form lane의 researcher-generated dependency assertions / semantic precondition assertions이 생성물 variability보다 더 타이트해질 가능성은 여전히 남아 있다.

즉 free-form lane은 이제 `Template Injection` 기준으로는 repeatability gate까지 통과했지만, 다른 free-form family까지 같은 수준이라고 일반화할 수는 없다.

## 6. 전략 목표

다음 단계의 목표는 단순하다.

### 6.1 North Star

`vuln_name only -> researcher/guard/synthesis -> runnable vulnerable Docker bundle -> exploit success + semantic/guard alignment + promotion truthfulness`

### 6.2 이번 계획의 핵심 전환

이전 문서는 다음을 상위 우선순위로 두었다.

- Path Traversal low-loop 안정화
- Template Injection dependency follow-through
- XSS/Deserialization live coverage 확보

이번 검토 결과, 우선순위는 다음처럼 바뀌어야 한다.

1. success/promotion truth repair
2. `NAME-*` runtime rule/contract normalization
3. role canonicalization
4. official lane codification(Template Injection/XSS/Deserialization)
5. then performance stabilization
6. then broader stack generalization

## 7. 단계별 개선 계획

### Phase 0. Verdict Truth Repair

### 목적

- nested verifier/guard/semantic failure가 있으면 top-level `verify_pass`, `review`, `promotion`이 반드시 실패하도록 만든다.

### 진행 현황

- `rule_based verifier -> reviewer -> pack` 핵심 전파는 1차 구현 완료
- nested guard failure에 대한 unit/regression test 추가 완료
- 남은 일은 full lane rerun 재검증, CI case 편입, 필요 시 verdict schema 추가 분리다

### 작업 항목

1. `evals/poc_verifier/rule_based.py`
   - `guard_consistency.verifier.blocking=true` 또는 workspace guard blocking이면 `verify_pass=false`로 강제한다.
   - semantic consistency mismatch가 blocking 수준이면 evidence 추가만 하지 말고 verify failure로 반영한다.
   - top-level 결과를 `exploit_pass`, `contract_pass`, `verify_pass`로 분리하는 리팩터링 여부를 결정한다.

2. `agents/reviewer/service.py`
   - `evaluate_with_vuln()`가 반환한 nested `guard_consistency`, `semantic_consistency`를 reviewer issue로 승격한다.
   - exploit 성공 여부와 무관하게 `severity=block`인 verifier guard failure는 reviewer blocking으로 처리한다.
   - 현재의 "exploit 성공 시 workspace semantic/guard mismatch는 non-blocking" 정책을 재검토하고, 최소한 guard failure는 blocking으로 상향한다.

3. `orchestrator/pack.py`
   - `eval_result.guard_consistency.verifier.passed=false`
   - `eval_result.guard_consistency.workspace.passed=false`
   - `eval_result.semantic_consistency.semantic_match=false`
   인 경우 promotion을 차단한다.

4. 테스트 추가
   - `Template Injection`과 같은 케이스에서 nested guard failure가 있을 때
     - `evals.overall_pass=false`
     - reviewer blocking
     - promotion.eligible=false
     를 강제하는 unit/e2e 테스트를 추가한다.

### 완료 기준

- `Template Injection` rerun이 현재처럼 false-positive success로 끝나지 않는다.
- nested guard failure가 있는 artifact는 reviewer 또는 pack 단계에서 반드시 차단된다.
- `success`와 `promotion eligible`의 의미가 다시 일치한다.

### Phase 1. `NAME-*` Runtime Rule Normalization

### 목적

- free-form vulnerability family도 researcher가 만든 runtime rule을 verify가 직접 소비하게 만든다.

### 작업 항목

1. `common/rules/__init__.py`
   - `_normalized_filename()`를 `NAME-*`와 기타 synthetic identifier에 맞게 확장한다.
   - `cwe-` prefix 전제 로직을 완화하거나, identifier class에 따라 filename normalization을 분기한다.

2. `agents/researcher/service.py`
   - `_write_candidate_rule()`가 rule loader와 동일한 filename normalization 함수를 쓰도록 바꾼다.
   - writer/loader가 서로 다른 naming policy를 가지지 않게 만든다.

3. `evals/poc_verifier/registry.py`
   - `rule_available` 판정이 실제 `load_rule()` 가능성과 일치하도록 정리한다.
   - "registry knows the id"와 "rule loader can actually resolve the file"를 분리 기록할지 결정한다.

4. 테스트 추가
   - `NAME-TEMPLATE-INJECTION` runtime rule writer/loader round-trip test
   - `NAME-*` rule이 있으면 generator_manifest fallback으로 내려가지 않는 verify path test

### 완료 기준

- `load_rule("NAME-TEMPLATE-INJECTION")`가 실제 runtime rule을 반환한다.
- free-form lane에서 runtime rule이 verify에 직접 사용된다.
- `rule_available` metadata가 실제 rule resolution과 어긋나지 않는다.

### Phase 2. Canonical Role Normalization

### 목적

- 생성물, guard, contract, verifier, reviewer가 같은 file role vocabulary를 사용하게 만든다.

### canonical role

- `service_main`
- `poc_entry`
- `helper`
- `schema`
- `seed_data`
- `docs`
- `container`
- `deps_lock`

### 작업 항목

1. researcher guard payload normalization
   - `server -> service_main`
   - `verifier -> poc_entry`
   alias를 정식 지원한다.

2. synthesis manifest validation
   - role alias가 들어오면 canonical role로 normalize해서 기록한다.
   - 원본 role은 optional metadata로만 남긴다.

3. contract resolution / reviewer / verifier
   - canonical role 우선 사용
   - alias는 backward compatibility layer로만 허용

4. docs/prompts
   - generator prompt와 handbook에 canonical role만 공식 스키마로 명시한다.

### 완료 기준

- 모든 generated manifest는 canonical role을 쓴다.
- contract/reviewer/verifier가 파일 경로 fallback 없이 같은 entry file을 본다.
- 비정형 파일명(`server.py`, `exploit.py`, `main_service.py`)에서도 stable하게 동작한다.

### Phase 3. Verify Model Refactor

### 목적

- verify를 "substring pass detector"가 아니라 "exploit + contract alignment verifier"로 만든다.

### 작업 항목

1. `evals/poc_verifier/scenarios.py`
   - assertion_program 성공 시에도 semantic/guard consistency 계산을 계속 수행하도록 수정한다.
   - 조기 return을 제거하거나, partial verdict를 합성하는 구조로 변경한다.

2. verify result schema 개선
   - `exploit_pass`
   - `semantic_pass`
   - `guard_pass`
   - `verify_pass`
   를 구분한다.

3. reviewer/pack 연동
   - reviewer는 `verify_pass`만 보지 않고 하위 verdict를 직접 읽는다.
   - pack은 `guard_pass=false` 또는 `semantic_pass=false`면 promotion 차단한다.

4. 테스트 추가
   - Path Traversal/XSS처럼 runtime assertion이 있는 lane에서도 semantic/guard report가 비지 않는지 검증한다.

### 완료 기준

- eval result에 semantic/guard verdict가 항상 기록된다.
- assertion_program이 성공해도 semantic mismatch가 있으면 전체 verify는 실패한다.
- reviewer/pack이 하위 verdict와 모순되지 않는다.

### Phase 4. Official Lane Codification

### 목적

- 지금 수동 rerun으로 확인된 lane을 공식 regression asset으로 승격한다.

### 작업 항목

1. E2E case 추가 또는 정리
   - `Path Traversal` name-only official case
   - `Template Injection` name-only official case
   - `XSS` name-only official case
   - `Insecure Deserialization` name-only case 설계/구현

2. 문서/룰 정리
   - static rule이 필요한 family와 runtime rule로 충분한 family를 구분한다.
   - free-form family는 runtime rule + semantic contract + guard spec을 공식 경로로 문서화한다.

3. CI 분리
   - deterministic local lane
   - researcher-backed remote lane
   - unknown live lane
   를 분리하고, 각각의 책임을 다르게 둔다.

### 완료 기준

- manual rerun이 아니라 repo의 official case로 Path Traversal/Template Injection/XSS를 재현 가능하다.
- `Insecure Deserialization` 최소 1개 live pass 확보 또는 blocker를 재현하는 failing case가 officialized 된다.

### Phase 5. Performance Stabilization

### 목적

- researcher-backed lane의 latency를 줄이고 known static lane의 retry를 줄인다.

### 우선 병목

- researcher latency 약 39초
- generator latency 14~24초
- known static lane도 generator retry 1회만으로 50초대

### 작업 항목

1. known static fast path
   - researcher skip lane에서 prompt/hint를 더 deterministic하게 줄여 generator first-pass rate를 높인다.
   - SQLi처럼 반복되는 guard miss를 재현 가능한 regression으로 고정한다.

2. researcher query budget 정리
   - query 수, provider latency, high-noise source penalty를 튜닝한다.
   - evidence relevance가 충분히 높으면 추가 검색을 조기 종료한다.

3. synthesis retry cost 절감
   - 이전 loop의 accepted semantic skeleton을 재사용한다.
   - dependency/role/contract class 오류는 full regenerate 대신 structured patch를 우선한다.

### 성능 목표

- known static deterministic lane: p95 30초 이내
- researcher-backed deterministic lane: p95 75초 이내
- known static first-loop success rate: 90% 이상
- runtime rule lane first-loop success rate: 80% 이상

### Phase 6. Open-World Generalization

### 목적

- 현재의 Python/Flask 단일 컨테이너 중심 capability를 넘어 multi-stack, multi-service까지 일반화한다.

### 현재 판단

- 이 단계는 중요하지만 P0/P1 이후다.
- 현재 가장 큰 문제는 coverage 부족이 아니라 trust mismatch다.

### 작업 항목

1. Node/Express, PHP, Java 최소 1개 family 확보
2. 외부 DB sidecar 및 multi-container synthesis 정식화
3. non-web scenario type 확장 여부 검토

### 완료 기준

- 단일 스택이 아닌 lane에서도 `vuln_name only -> runnable bundle -> trusted verify`가 성립한다.

## 8. 실행 순서

실제 구현 순서는 아래로 고정한다.

1. Phase 0 잔여 항목 완료
2. Phase 1 잔여 항목 완료
3. Phase 2 잔여 항목 완료
4. Phase 3 최소 버전 완료
5. Phase 4에서 Template Injection/XSS officialization
6. 그 다음 Path Traversal/Deserialization 정식화
7. 이후 Phase 5 성능 안정화
8. 마지막으로 Phase 6 stack generalization

즉, 다음 sprint의 핵심은 "새 family 추가"가 아니라 "현재 pass의 의미를 신뢰 가능하게 만드는 것"이다.

## 9. Acceptance Matrix

아래 matrix가 모두 만족되어야 이번 단계 완료로 본다.

| 구분 | 최소 acceptance |
| --- | --- |
| Unit tests | 기존 `114 passed, 7 skipped` 수준 유지 또는 상향 |
| Verdict truth | nested guard/verifier failure가 있으면 top-level success 금지 |
| Free-form rule loading | `NAME-*` runtime rule writer/loader round-trip 성공 |
| Role normalization | generated manifest canonical role 100% |
| Official lanes | SQLi/CSRF/SSRF/Path Traversal/Template Injection/XSS 공식 rerun 보유 |
| Promotion truth | `promotion.eligible=true`인 artifact는 guard/semantic blocking failure가 없어야 함 |
| Performance | known static p95 <= 30s, researcher-backed p95 <= 75s |

## 10. 문서 운영 규칙

이 문서는 이후부터 다음 규칙으로 유지한다.

- speculative statement를 쓰지 않는다.
- "pass", "stable", "eligible" 같은 표현은 fresh rerun 또는 CI artifact로만 갱신한다.
- 상태 서술과 계획 서술을 분리한다.
- 계획 변경 시에는 반드시 "왜 우선순위가 바뀌었는지"를 rerun 결과와 연결해 적는다.

## 11. 현재 즉시 착수할 구현 항목

지금 바로 시작할 work package는 아래 네 개다.

1. `Insecure Deserialization` official regression case 또는 failing case 공식화
2. `verifier/reviewer/pack truth repair` 잔여 full rerun 재검증
3. `NAME-*` runtime rule normalization 잔여 정리 및 free-form rerun 고정
4. role canonicalization 잔여 정리 및 비정형 파일명 rerun 고정
5. `Template Injection` repeatability gate를 CI/nightly 정책에 연결

이 네 항목이 닫히기 전까지는 "free-form `취약점 이름만 제공` 기반 동적 취약 Docker 생성이 신뢰 가능한 수준에 도달했다"고 판단하지 않는다.

## 12. 한 문장 요약

현재 레포는 `취약점 이름만 제공 -> 동적 취약 Docker 생성`이라는 초기 방향성 자체는 실제로 SQLi/CSRF/SSRF/Path Traversal/Template Injection/XSS까지 상당 부분 구현했지만, 다음 단계의 최우선 과제는 family 확장보다 먼저 `verify/review/promotion truthfulness`, `NAME-* runtime rule loading`, `role canonicalization`을 바로잡아 생성 성공과 산출물 신뢰성을 일치시키는 것이다.
