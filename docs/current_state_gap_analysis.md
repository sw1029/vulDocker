# CWE 일반화 중심 구현계획 및 현재 상태

본 문서는 2026-03-07 KST 기준의 실행 문서다. 목적은 세 가지다.

- 현재 구현 상태를 코드와 실제 실행 결과 기준으로 다시 정리한다.
- 이번 턴에서 실제로 보완한 항목과 그 효과를 기록한다.
- 잔여 구현계획의 우선순위를 현재 증거에 맞게 재배치한다.

주의:

- 본 문서의 “이번 실행”은 2026-03-07 KST 기준이다.
- 로그와 메타데이터 타임스탬프는 UTC라 일부 파일에는 2026-03-06으로 보인다.
- historical artifact와 이번 턴 post-patch artifact를 구분해서 쓴다.

## 1. 핵심 결론

현재 레포는 더 이상 `known path만 겨우 되는 프로토타입`은 아니다. `CWE-89` known path는 이번 턴 post-patch 재실행에서도 deterministic single-run pass를 유지했고, reviewer non-blocking semantic noise도 제거했다.

또한 `CWE-9999` unknown live path는 현재 워킹트리 기준으로 pass한다. 이번 턴 후속 패치에서는 unknown path에 대해 다음 세 가지가 추가로 개선됐다.

- wrapped `researcher_report`를 canonical top-level 스키마로 정규화
- unknown evidence relevance를 raw CWE token 매칭이 아니라 semantic anchor / stack / exploit term 중심으로 재계산
- `resolved_contract.json`에 `semantic_contract`를 승격하고, verifier의 `semantic_consistency`가 builtin rule 부재 시 이 계약을 직접 소비

그 결과 unknown run의 검증은 더 이상 generic `"Exploit SUCCESS"` 단일 문자열에만 기대지 않고, runtime rule과 verifier evidence가 researcher `verification_spec`에서 유도된 concrete marker/flag를 사용한다.

다만 이 성공을 곧바로 `취약점 이름만 제공` 수준의 일반화 달성으로 해석하면 안 된다. 현재 unknown success는 여전히 `pattern_id`, language/framework/runtime, runtime rule, self-authored verification contract에 강하게 의존한다. 즉, 현재 최상위 잔여 과제는 더 이상 `unknown live 1회 pass 재확보`가 아니라 다음 두 가지다.

1. unknown path의 semantic validity를 더 독립적으로 보장
2. `취약점 이름만 제공`에 가까운 minimal-input 일반화 lane 확보

## 2. 이번 턴에서 반영한 구현

이번 턴에서 실제로 반영한 보완은 다음 일곱 가지다.

### 2.1 unknown semantics source-of-truth 보강

- Researcher 단계에서 `semantic_signature`를 후처리한다.
- known CWE 기본 시그니처와 report payload를 그대로 쓰는 대신,
  - report가 가진 시그니처
  - pattern / verification_spec / preconditions / failure_context에서 추론한 heuristic 시그니처
  - known CWE default 시그니처
  를 merge한다.
- 결과적으로 unknown run에서도 `semantic_signature`가 empty로 남지 않도록 보강했다.
- `semantic_signature_source`를 researcher report에 남겨, default/heuristic/report 중 어디에서 채워졌는지 추적 가능하게 했다.

효과:

- `metadata/sid-d2ff12df4e6d/researcher_report.json`의 top-level `semantic_signature`가 더 이상 빈 값이 아니다.
- same run의 `guard_spec.json`도 concrete anchor를 가진 semantic contract를 소비한다.

### 2.2 semantic matcher 현실화

- Guard engine의 semantic token matcher에 alias / code-anchor 인식을 추가했다.
- 예:
  - `user-controlled request parameter` -> `request.args`, `request.form`, `request.json`, query/body parameter 흔적
  - `SQL query execution` -> `cursor.execute`, `execute(`, `executescript(`, `sqlite3.connect`
  - `input concatenated/interpolated into SQL sink` -> SQL string composition regex
- 이 보완으로 known `CWE-89` bundle에서 실제 취약 구현이 있는데도 reviewer가 semantic mismatch를 내는 false positive를 줄였다.

효과:

- post-patch known E2E에서 reviewer `issues_sample`이 0이 되었다.

### 2.3 executor PoC 실행 컨텍스트 보강

- executor가 컨테이너 안에서 `/tmp/poc.py`를 실행할 때 `-w /app -e PYTHONPATH=/app`를 함께 준다.
- 이 보완으로 generated PoC가 `from app import app` / Flask test_client 패턴을 사용해도 `/app/app.py`를 import할 수 있다.

효과:

- post-patch known run에서 한 번 드러난 `PoC import error: No module named 'app'` 유형의 flake를 즉시 해소했다.

### 2.4 repeatability report 왜곡 수정

- success attempt에서 `failure_stage`를 채우지 않도록 수정했다.
- subprocess error만 있고 `latest_failure`가 없는 경우에는 에러 문자열에서 stage를 추론하도록 보강했다.

효과:

- success report가 더 이상 `failure_stage=REVIEW`로 왜곡되지 않는다.

### 2.5 researcher_report schema normalization

- LLM이 `{"researcher_report": {...}}` 래퍼를 씌운 JSON을 반환해도 저장 직전 canonical top-level shape로 정규화한다.
- downstream helper(`_extract_verification_spec`, `build_generator_contract`)도 wrapped/legacy payload를 모두 읽을 수 있게 했다.

효과:

- unknown run에서 `researcher_report.json`의 핵심 필드(`verification_spec`, `semantic_signature`, `quality`, `evidence_relevance`)가 top-level에서 일관되게 보인다.
- runtime rule 생성이 더 이상 wrapped payload를 놓쳐 generic fallback contract로 떨어지지 않는다.

### 2.6 evidence relevance 점수식 1차 재설계

- unknown/known 공통으로 relevance 계산에서 `hit.query`를 제거했다. 이제 query 문자열만으로 관련성이 부풀려지지 않는다.
- 대신 다음 축을 사용한다.
  - vulnerability family term
  - stack affinity(language/framework/db)
  - exploit term
  - semantic anchor(`input_vector`, `sink`, `exploit_precondition`)
- hit별 score/matched category를 `researcher_report.json.evidence_relevance`와 `resolved_contract.json.semantic_contract.evidence_relevance`에 기록한다.

효과:

- unknown run에서도 어떤 remote evidence가 실제로 관련 있고 어떤 hit가 low-signal인지 산출물에서 바로 식별할 수 있다.
- query-only inflated relevance bug는 제거됐다.

### 2.7 semantic contract 승격 및 verifier 소비

- `resolved_contract.json`에 `semantic_contract`를 추가했다.
- payload에는 다음이 포함된다.
  - `semantic_signature`
  - `semantic_signature_source`
  - `quality`
  - `quality_reason`
  - `evidence_relevance`
  - `guard_confidence`(available 시)
- verifier의 `semantic_consistency`는 builtin semantics가 지원되지 않는 unknown CWE에서 `resolved_contract.semantic_contract`를 직접 사용하도록 보강했다.

효과:

- unknown eval 결과의 `semantic_consistency.supported`가 더 이상 `false`가 아니다.
- `semantic_consistency.source="resolved_contract.semantic_contract"`로, verifier가 공통 semantic contract를 명시적으로 소비했음을 artifact에서 확인할 수 있다.

## 3. 이번 턴 검증 결과

이번 턴에서 직접 확인한 항목:

- 전체 테스트
  - `pytest -q tests`
  - 결과: `80 passed, 4 skipped`
- known deterministic E2E 재실행 (post-patch)
  - `python tests/e2e/run_case.py --case tests/e2e/cases/cwe-89-basic --mode deterministic --no-snapshot --output-dir /tmp/vuld-postpatch2-cwe89`
  - 결과: pass
- unknown live E2E 재실행 (post-patch)
  - `env VUL_WEB_SEARCH_PROVIDER=tavily python tests/e2e/run_case.py --case tests/e2e/cases/cwe-unknown-basic --mode deterministic --no-snapshot --output-dir /tmp/vuld-postpatch3-unknown`
  - 결과: pass
- unknown artifact spot-check
  - `metadata/sid-d2ff12df4e6d/runtime_rules/cwe-9999.yaml`
  - 결과: success marker가 generic `Exploit SUCCESS`가 아니라 concrete `"count": 2`, `VULNERABLE_SQLI_CONFIRMED`
- unknown semantic contract spot-check
  - `metadata/sid-d2ff12df4e6d/resolved_contract.json`
  - 결과: `semantic_contract` 포함
- unknown verifier semantic consistency spot-check
  - `artifacts/sid-d2ff12df4e6d/reports/evals.json`
  - 결과: `semantic_consistency.supported=true`, `source=resolved_contract.semantic_contract`
- unknown regeneration hardness spot-check
  - same rerun에서 generator가 첫 시도 실패 후 loop 2에서 회복
  - 실패 이유: `poc missing '"count": 2'`

## 4. 현재 상태 판정

### 4.1 known path: `cwe-89-basic`

현재 사실:

- deterministic single-run은 post-patch 재실행에서도 pass.
- `/tmp/vuld-postpatch2-cwe89/summary.json` 기준:
  - `overall_pass=true`
  - `verify_pass=true`
  - `run_passed=true`
  - `exit_code=0`
- `metadata/sid-b36ff41a638a/reviewer_report.json` 기준 reviewer issues는 0.

해석:

- known baseline의 기능 경로는 현재도 유지된다.
- reviewer signal 품질은 이전보다 좋아졌다.
- 다만 이번 follow-up patch 이후의 full 3회 repeatability를 다시 장시간 재실행하지는 않았다. 따라서 현재 증거는 `single-run 건강성 유지`까지다.

### 4.2 unknown live path: `cwe-unknown-basic`

현재 사실:

- post-patch unknown live run은 pass.
- `/tmp/vuld-postpatch3-unknown/summary.json` 기준:
  - `overall_pass=true`
  - `verify_pass=true`
  - `run_passed=true`
  - `blocking_bundles=[]`
- same summary 기준 verify evidence:
  - `Found signature: "count": 2`
  - `Found flag token: VULNERABLE_SQLI_CONFIRMED`
  - `Semantic consistency check passed`
- `metadata/sid-d2ff12df4e6d/search_health.json` 기준:
  - `provider=tavily`
  - `configured=true`
  - `auth_present=true`
  - `policy=remote_required`
  - `remote_result_count=9`
  - `degraded=false`
- `metadata/sid-d2ff12df4e6d/researcher_report.json` 기준:
  - wrapped payload가 canonical top-level로 정규화됨
  - `semantic_signature` non-empty
  - `semantic_signature_source=["heuristic"]`
  - `evidence_relevance.score=0.661`
  - low-signal evidence도 hit-level score로 드러남(예: E2E tutorial hit `0.05`)
- `metadata/sid-d2ff12df4e6d/runtime_rules/cwe-9999.yaml` 기준:
  - `success_signature="count": 2`
  - `flag_token=VULNERABLE_SQLI_CONFIRMED`
  - `assertion_program`이 더 이상 free-form verifier code에서 첫 문자열 리터럴만 뽑은 약한 값으로 채워지지 않고, success marker / flag 기반 contains assertion으로 정규화됨
- `metadata/sid-d2ff12df4e6d/resolved_contract.json` 기준:
  - `semantic_contract` 존재
  - `quality=sufficient`
  - `evidence_relevance` 포함
- `artifacts/sid-d2ff12df4e6d/reports/evals.json` 기준:
  - `semantic_consistency.supported=true`
  - `semantic_consistency.source=resolved_contract.semantic_contract`
- `metadata/sid-d2ff12df4e6d/guard_spec.json`도 concrete anchor를 가진 semantic signature를 기록한다.

해석:

- unknown live path는 더 이상 `현재 유일한 hard failure`가 아니다.
- unknown path의 verifier contract는 이전보다 명확해졌다. 즉, `generic fallback success marker` 의존도는 줄었다.
- unknown path의 semantic validity는 여전히 완전히 독립적이지는 않지만, verifier가 shared `semantic_contract`를 소비하도록 보강되면서 `산출물 semantic 독립성`은 `낮음 -> 중하` 정도로 한 단계 개선됐다.
- unknown evidence relevance는 query inflation bug가 제거됐지만, 아직 mixed evidence set를 완전히 억제하지는 못한다. 즉, 현재 문제는 `availability`보다 `validity + confidence calibration`이다.
- follow-up rerun에서 stricter success marker 때문에 generator가 1회 재시도한 점은 남은 리스크다. 즉, quality bar는 올라갔지만 unknown lane의 deterministic margin은 아직 넉넉하지 않다.

### 4.3 search/provider 상태

현재 사실:

- `custom|tavily` provider는 동작한다.
- Tavily 키는 `config/api_keys.ini` fallback으로 자동 인식된다.
- `researcher.search_filters`는 request layer까지 전달된다.
- `ops/ci/run_e2e_tests.sh`는 Tavily preflight와 repeatability gate opt-in을 이미 지원한다.

현재 한계:

- `brave`, `searxng` adapter는 아직 없다.
- provider 간 filter parity는 아직 완전하지 않다.
- heavy E2E/live gate는 여전히 opt-in 운영이 맞다.

해석:

- search/provider는 primary blocker가 아니다.
- 이 영역의 남은 과제는 기능 부재보다 운영 정책과 parity다.

### 4.4 “일반화 / 취약점 이름만 제공” 관점

현재 사실:

- unknown case는 여전히 base requirement에서 다음을 강하게 상속한다.
  - `pattern_id: sqli-string-concat`
  - `language: python`
  - `framework: flask`
  - `runtime.db: sqlite`
  - `base_image`
  - `user_deps`
- unknown researcher report도 실제로는 `CWE-89 유사 SQLi`를 재현하는 방향으로 bundle을 유도한다.
- runtime rule 또한 researcher verification spec에서 파생되어 unknown verifier contract를 강화한다.
- 현재 E2E case set은 여전히 `cwe-89-basic`, `cwe-unknown-basic` 두 개뿐이며, 별도 minimal-input lane은 없다.

해석:

- 현재 unknown success는 `vuln-name-only generalization`의 증거가 아니다.
- 더 정확한 표현은 다음이다.
  - `pattern-conditioned synthesis`
  - `runtime rule + verification-contract aware generation`
  - `semantic contract가 이전보다 나아졌고 verifier도 이를 소비하지만, 아직 input-minimal generalization은 아님`

즉, 남은 구조적 갭은 `unknown pass/fail`보다 `얼마나 적은 입력으로도 올바른 취약 종류를 고를 수 있느냐`다.

### 4.5 현재 등급 재판정

- unknown pattern-conditioned lane: `중간 -> 중상`
  - 이유: wrapped report normalization, concrete runtime verifier contract, semantic contract 소비까지 연결됐다.
- 산출물 semantic 독립성: `낮음 -> 중하`
  - 이유: builtin rule이 없는 unknown에서도 verifier가 shared semantic contract를 읽지만, 그 contract 자체는 아직 researcher-derived heuristic 비중이 높다.
- 취약점 이름만 제공 generalization: `낮음 유지`
  - 이유: minimal-input lane과 stack inference lane이 아직 없다.

## 5. 잔여 구현계획 타당성 재검토

### 5.1 그대로 유지할 가치가 높은 항목

- dynamic semantics 강화
  - 이번 턴에서 `resolved_contract.semantic_contract`와 verifier consumption까지 추가했지만, 아직 authoritative owner를 완전히 고정하지는 않았다.
- repeatability / live artifact 보존 및 CI gate 승격
  - 이번 턴에서 report 해석 품질을 고쳤으므로, 이제 artifact-driven gate 운영 가치가 더 높아졌다.
- provider parity
  - primary blocker는 아니지만, 운영 lane 다양화에는 여전히 필요하다.
- scaffold + vuln patch 아키텍처
  - 장기적으로 일반화 품질을 가장 크게 끌어올릴 수 있는 방향은 여전히 맞다.

### 5.2 우선순위를 낮춰야 하는 항목

- `unknown live 1회 pass 재확보`
  - 현재 워킹트리 기준 이미 달성됐다.
- `repeated-failure loop`를 immediate top priority로 두는 것
  - unknown fail baseline이 더 이상 현재의 대표 상태가 아니므로, 이 항목은 한 단계 내려가야 한다.

### 5.3 현재 기준 새 우선순위

#### 1순위: unknown semantic validity hardening

이유:

- unknown path는 pass하고 verifier도 shared semantic contract를 읽지만, 그 contract가 아직 researcher-derived heuristic에 가깝다.
- 지금 가장 중요한 질문은 “이 취약점이 정말 요청한 취약점인가”다.

핵심 작업:

- `semantic_signature`를 researcher / guard / verifier / contract 중 어디가 authoritative인지 명확히 고정
- 현재 추가된 `resolved_contract.semantic_contract`를 진짜 source-of-truth로 승격
- runtime rule / verification spec이 semantic contract와 모순되지 않는지 cross-check

완료 기준:

- unknown run에서 semantic contract가 empty가 아니고,
- same contract를 researcher / guard / verifier가 공통 소비하며,
- self-authored verifier contract만 맞추는 bundle이 semantic layer에서 차단된다.

#### 2순위: evidence relevance 강화

이유:

- 이번 턴에서 query inflation bug는 제거했지만, 현재 scoring은 여전히 `stack/sql/sqlite` hit 몇 개만으로 overall sufficient가 가능하다.
- mixed evidence set에서 off-topic remote hit를 더 강하게 감점하는 2차 보정이 필요하다.

핵심 작업:

- unknown relevance를 raw CWE token match보다
  - vulnerability family term
  - sink/input/precondition anchor
  - stack affinity
  - exploit effect
  중심으로 재계산
- off-topic / wrong-family evidence에 negative weighting 추가
- low-confidence unknown evidence에서는 runtime rule strength를 낮추거나 explicit fallback mode로 전환

완료 기준:

- unrelated evidence mix가 많은 unknown run은 quality가 낮게 판정되거나
- 최소한 semantic contract confidence가 낮다고 명시된다.

#### 3순위: minimal-input generalization lane 신설

이유:

- 현재 repo는 `pattern-conditioned` lane에서는 점점 좋아지고 있다.
- 하지만 사용자가 원하는 `취약점 이름만 제공` 수준은 아직 별도 검증 lane 자체가 없다.

핵심 작업:

- 새 E2E case를 추가해 다음을 최소화한다.
  - no explicit `pattern_id`
  - no explicit framework hint
  - no explicit DB hint
  - only vuln_id + safe runtime defaults
- 현재 lane과 분리해서 `pattern-conditioned lane` / `minimal-input lane`을 별도 지표로 관리

완료 기준:

- minimal-input lane에서 1회 이상 pass artifact 확보
- 실패 시에도 어떤 missing semantic / stack inference 때문에 실패했는지 metadata에 남음

#### 4순위: repeatability / CI gate 승격

이유:

- 이번 턴에서 repeatability report 왜곡이 수정됐다.
- 이제 artifact 해석 가능성이 높아졌으므로 CI 승격을 논할 수 있다.

핵심 작업:

- known repeatability gate를 CI 기본 lane으로 승격
- unknown live gate는 Tavily key가 있는 lane/nightly에서 required
- repeatability/live artifact를 long-lived artifact로 보존

완료 기준:

- success/failure stage, guard codes, report path가 CI artifact로 안정적으로 남음

#### 5순위: provider 확장과 filter parity

이유:

- 여전히 useful하지만 primary blocker는 아니다.

핵심 작업:

- `brave.py`, `searxng.py` adapter
- provider별 filter parity 정렬

## 6. 지금 바로 이어서 할 다음 구현 단계

현 시점에서 가장 타당한 다음 작업은 아래 순서다.

1. `semantic_contract` authority 고정 + runtime rule / verification spec contradiction check 추가
2. unknown evidence relevance 2차 보정(negative weighting / confidence downgrade)
3. minimal-input unknown E2E case 추가
4. known repeatability 3회 post-follow-up 재측정 및 CI lane 연결
5. provider parity 확장

## 7. 현재 상태를 한 문장으로 요약하면

2026-03-07 KST 기준 이 레포는 `known/unknown live path 모두 현재는 실제 pass 가능하고, follow-up patch에서 unknown verifier contract / evidence relevance / semantic contract 공유를 한 단계 강화했지만, 아직 “취약점 이름만 제공” 수준의 일반화 엔진으로 보기는 이르다`가 가장 정확하다.
