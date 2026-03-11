# 동적 취약 Docker 생성 Current State / Gap Analysis

본 문서는 2026-03-11 KST 기준 최신 워크스페이스 truth를 기준으로, 이번 라운드의 추가 구현, 재실행 결과, 일반화/템플릿 의존성 관점의 재평가, 그리고 남은 개선 우선순위를 하나로 정리한 최신 문서다.

이번 개정의 목적은 다음 네 가지다.

1. 현재 코드와 실제 재실행 결과를 기준으로 “지금 실제로 무엇이 닫혀 있는가”를 다시 고정한다.
2. 이름만 주는 입력으로 동적 Docker/app/PoC를 만든다는 주장 범위를 과장 없이 재정의한다.
3. 이번 턴에서 직접 반영한 코드 보완을 현재 구조와 연결해 설명한다.
4. 남은 미비점과 다음 우선순위를 문서/테스트/실행 결과가 서로 어긋나지 않게 최신화한다.

## 1. Truth Protocol

이 문서의 평가는 아래 규칙을 따른다.

- `current workspace rerun`만 현재 상태의 주 근거로 쓴다.
- `sid-*`는 immutable evidence가 아니라 deterministic workspace locator로만 취급한다.
- `trusted dynamic`은 `llm_manifest` provenance가 명시된 경우에만 쓴다.
- `compiler-first`는 curated family catalog + scaffold/fragment compiler 경로를 뜻한다.
- `template-assisted`는 built-in template 또는 runtime template clone 경로를 뜻한다.
- `pre-generation fail-closed`는 semantic / provider / research precheck에서 생성 자체가 중단된 경로를 뜻한다.
- unsupported free-form lane은 generic fallback success가 아니라 fail-closed negative regression으로 다룬다.
- `semantic_source`는 가능한 한 canonical taxonomy로 surface하고, machine-local absolute path는 top-level truth로 쓰지 않는다.

## 2. 이번 턴에서 추가된 구현

이번 턴에서는 이전 gap analysis와 실제 코드 리뷰에서 확인된 약점을 바탕으로 아래 보완을 직접 반영했다.

### 2.1 Stack-aware compiler runtime rule emission

- compiler runtime rule 생성이 더 이상 Flask registry에 고정되지 않는다.
- 생성된 manifest의 scaffold/stack metadata를 읽고 해당 stack registry에서 fragment token을 뽑아 runtime rule을 만든다.
- 따라서 FastAPI compiler lane에서도 runtime rule이 `RedirectResponse(...)`, `Query(...)`, FastAPI용 fragment token을 기준으로 surface된다.

효과:

- declared rule이 없는 경우나 compiler-derived runtime rule을 fallback evidence로 쓸 때, FastAPI bundle을 Flask token으로 검증하는 구조적 mismatch를 줄였다.
- “second scaffold는 service만 FastAPI인데 runtime rule은 Flask 편향”이라는 결함을 닫았다.

### 2.2 Canonical semantic_source surface

- verifier의 workspace semantic fallback은 더 이상 absolute workspace path를 `semantic_source`로 내지 않는다.
- 이제 canonical source value로 `workspace_scan`을 내고, 상세 경로는 internal detail로만 남긴다.

효과:

- manifest/eval semantic surface가 machine/SID/path에 덜 종속된다.
- template lane에서도 `semantic_source`가 enum-like taxonomy로 읽히므로 expectation과 summary 비교가 더 안정적이다.

### 2.3 Template runtime viability gating 보강

- template compatibility 판단이 더 이상 사실상 DB-only check에 머무르지 않는다.
- external DB template는 executor sidecar/network feasibility까지 configured여야 viable로 인정한다.
- 추가로 template metadata의 env contract key set이 runtime_surface로 유도되는 service env key set과 최소한 schema level에서 맞는지 확인한다.

효과:

- `allow_external_db=true`만 켜고 sidecar/network가 빠진 상태에서 external DB template가 viable처럼 보이는 경로를 더 보수적으로 차단한다.
- template selection / hybrid fallback / executor feasibility가 조금 더 같은 방향을 보게 되었다.

주의:

- 이 보완은 full runtime capability DSL이 아니라 partial alignment다.
- 현재는 `db + executor feasibility + env-key contract` 수준이며, alias/env value/health/network/seed-data까지 fully model하지는 않는다.

### 2.4 Compiler README human-facing surface 보강

- compiler-generated README가 scaffold/fragment/vuln_id/service entry만 적는 quickstart stub에서 한 단계 확장됐다.
- 이제 service behavior, exploit contract, runtime assumptions를 함께 surface한다.

효과:

- provenance만 강하고 사람 기준 설명력이 약했던 compiler bundle 산출물이 inspection/handoff/debugging에 조금 더 유리해졌다.
- sidecar/compiler lane에서는 env contract 같은 runtime assumption이 README에서 드러난다.

### 2.5 회귀 테스트 보강

이번 턴에서 아래 회귀를 추가로 고정했다.

- FastAPI compiler runtime rule이 stack-aware token을 쓰는지 검증
- workspace semantic fallback이 `workspace_scan` taxonomy를 쓰는지 검증
- external DB template가 executor surface misconfiguration일 때 viable로 보이지 않는지 검증
- compiler README가 service/poc/runtime assumption line을 surface하는지 검증
- E2E expectation에서 built-in MySQL template lane의 `semantic_source=workspace_scan` 고정

### 2.6 Template stack metadata / scaffold-specific PoC asset 보강

- built-in template metadata가 이제 explicit `stack_id`, `language`, `framework`를 surface한다.
- template planner는 runtime/db/executor surface뿐 아니라 template stack identity도 함께 본다.
- 따라서 stack을 명시한 요청에서 built-in Flask template가 “metadata상으로는 맞는 것처럼 보이지만 실제 stack은 다른” 상태를 덜 허용한다.
- 추가로 FastAPI compiler fragment는 더 이상 `flask-pocs` asset을 재사용하지 않고 `fastapi-pocs` asset을 쓴다.

효과:

- template dependence reduction이 “service scaffold만 다름” 수준에서 한 단계 나아가 “exploit harness asset도 scaffold-specific”으로 조금 더 진전됐다.
- built-in template lane도 이제 stack contract를 metadata 레벨에서 명시하므로, template viability가 stack mismatch를 표현할 수 있게 됐다.

주의:

- 현재 explicit stack metadata는 built-in template에 우선 적용된 상태다.
- runtime template clone까지 동일 수준으로 강제하려면 template schema/evaluator를 더 넓혀야 한다.

### 2.7 Template selection diagnostics surface 보강

- template lane은 이제 `generator_template.json`에 `template_stack_id`, `requested_stack_id`, `template_stack_match`, `template_runtime_surface_status`, `template_runtime_diagnostics`를 남긴다.
- 같은 정보가 `resolved_contract.json`에도 mirror되므로, template lane contract/provenance를 pack 전에도 기계적으로 읽을 수 있다.
- researcher가 base template를 runtime template clone으로 복사할 때도 stack metadata를 normalize해서 쓰도록 맞췄다.

효과:

- “왜 이 template가 viable였는가 / 왜 fallback 대상이 아니었는가”를 문자열 추론 없이 읽을 수 있다.
- built-in template와 runtime template clone 사이의 metadata drift를 조금 줄였다.

### 2.8 second scaffold 확장: XSS / SSRF

- `python/fastapi` second scaffold에 `CWE-79 (XSS)`와 `CWE-918 (SSRF)` compiler fragment를 추가했다.
- FastAPI용 XSS/SSRF PoC asset도 별도로 추가해 second scaffold coverage를 더 넓혔다.
- 추가로 `docs/evals/rules/cwe-79.yaml`을 도입해 XSS lane도 declared-rule 기반 high-trust verification을 갖게 했다.
- semantic evaluator는 `HTMLResponse(...)` reflected sink를 XSS semantic surface로 읽을 수 있도록 보강했다.

효과:

- second scaffold의 positive lane이 Open Redirect / Path Traversal / Template Injection 중심에서 XSS / SSRF까지 확장되었다.
- XSS는 compiler-runtime fallback이 아니라 declared-rule/high-trust lane으로 올라왔다.
- 이름만 주는 입력의 known-family lower bound가 `python/fastapi`에서도 조금 더 넓어졌다.

## 3. Verified Current State

### 3.1 테스트 기준선

2026-03-11 KST current workspace rerun:

| command | result | 해석 |
| --- | --- | --- |
| `python -m pytest -q tests` | `341 passed, 39 skipped in 2.09s` | unit/integration baseline |
| `VULD_RUN_E2E=1 python -m pytest -q tests/e2e/test_cases.py -rs` | `37 passed, 2 skipped in 312.27s` | 공식 Docker E2E baseline |

즉 이번 코드 보완 이후에도 official E2E truth는 유지됐다.

### 3.2 대표 lane 재실행 관찰

| lane | 결과 | generation_origin | dynamicness | semantic | verification | 대표 관찰 |
| --- | --- | --- | --- | --- | --- | --- |
| `open-redirect-fastapi-name-only` | success | `compiler_generated` | `compiler-first` | `true / aligned / generator_manifest` | `declared_rule / high / independent` | FastAPI lane은 여전히 positive로 닫히고, runtime rule은 이제 `RedirectResponse(` / `Query(` token을 가지며 Flask `request.args.get('next'` token을 더 이상 쓰지 않는다. latest rerun 기준 `total_duration_s≈17.344s` |
| `template-injection-fastapi-name-only` | success | `compiler_generated` | `compiler-first` | `true / aligned / generator_manifest` | `declared_rule / high / independent` | second scaffold가 template sink family까지 계속 닫힌다. 추가로 generated `poc.py`도 FastAPI-specific asset을 사용한다. latest rerun 기준 `total_duration_s≈14.682s` |
| `path-traversal-fastapi-name-only` | success | `compiler_generated` | `compiler-first` | `true / aligned / generator_manifest` | `declared_rule / high / independent` | second scaffold path traversal lane도 유지되며 generated `poc.py`가 FastAPI-specific asset으로 분리됐다. latest rerun 기준 `total_duration_s≈15.671s` |
| `xss-fastapi-name-only` | success | `compiler_generated` | `compiler-first` | `true / aligned / generator_manifest` | `declared_rule / high / independent` | second scaffold가 reflected XSS family까지 확장됐다. latest rerun 기준 `total_duration_s≈15.638s` |
| `ssrf-fastapi-name-only` | success | `compiler_generated` | `compiler-first` | `true / aligned / generator_manifest` | `declared_rule / high / independent` | second scaffold가 SSRF family까지 확장됐다. latest rerun 기준 `total_duration_s≈14.249s` |
| `sqli-sidecar-template` | success | `built_in_template` | `template-assisted` | `true / aligned / workspace_scan` | `declared_rule / high / independent` | built-in external DB template lane은 여전히 성공하고, template lane semantic source는 canonical `workspace_scan`으로 정리됐다. built-in template metadata도 이제 explicit stack contract를 가진다. latest rerun 기준 `total_duration_s≈19.767s` |
| `trusted-dynamic-sqli` | success | `llm_manifest` | `trusted dynamic` | `true / aligned / generator_manifest` | `declared_rule / high / independent` | 여전히 fixture-backed trusted-dynamic regression lane이다. live remote provider acceptance lane은 아니다 |
| `foobar-name-only-negative` | fail-closed | `research_short_circuit` | `pre-generation fail-closed` | `false / unsupported / resolved_contract.semantic_contract` | verifier 미실행 | unsupported free-form name은 현재도 generic artifact가 아니라 RESEARCH-stage terminal negative regression으로 닫힌다. latest rerun 기준 `total_duration_s≈0.054s` |

성능 메모:

- compiler-first no-sidecar HTTP lane은 현재 cold-ish rerun 기준 약 15~17초대였고, Docker build cache 상태에 따라 체감 편차가 크다.
- external DB sidecar lane은 현재 약 20초 내외다.
- unsupported negative lane은 여전히 수십 ms대로 매우 빠르게 fail-closed된다.

### 3.3 현재 공식 source-of-truth 범위

현재 official E2E는 아래 축을 포함한다.

- compiler-first known lane
  - SQLi, CSRF, Command Injection, Code Injection, Path Traversal, XSS, SSRF, Insecure Deserialization
- compiler-first real free-form positive lane
  - Template Injection, Open Redirect, XXE, LDAP Injection
- alias / paraphrase / reordered positive lane
  - catalog alias layer와 token-match layer를 모두 포함
- multi-vuln lane
  - supported-only positive lane
  - mixed partial-progress lane
- sidecar-backed positive lane
  - built-in template MySQL SQLi
  - compiler-first MySQL SQLi
  - custom service_env SQLi
- second scaffold positive lane
  - `python/fastapi` + Open Redirect compiler-first
  - `python/fastapi` + Path Traversal compiler-first
  - `python/fastapi` + Template Injection compiler-first
  - `python/fastapi` + XSS compiler-first
  - `python/fastapi` + SSRF compiler-first
- trusted-dynamic lane
  - fixture-backed `llm_manifest`
- unsupported negative lane
  - `Foobar`

즉 “이름만 주는 입력”의 하한선은 꽤 좋아졌지만, strong positive evidence는 여전히 curated family catalog 안에서 나온다.

## 4. Current Architecture Truth

### 4.1 이름만 주는 요청의 실제 resolution chain

현재 minimal-input path는 아래 순서를 따른다.

1. free-form label을 canonical `CWE-*` 또는 `NAME-*`로 정규화한다.
2. shared vuln family catalog에서 alias / identifier / pattern / token-match를 수행한다.
3. `semantic_profile`과 `compiler_supported` lower-bound verdict를 seed한다.
4. 지원 family면 researcher를 건너뛰고 compiler-first path로 내려갈 수 있다.
5. 미지원 free-form `NAME-*`면 RESEARCH 이전 또는 RESEARCH 직후 fail-closed한다.
6. template mode/hybrid fallback은 stack identity, runtime db, executor feasibility를 같이 보고 viable template를 판단한다.

중요한 점:

- 이 구조는 open-world semantic inference라기보다 curated semantic-family routing + fail-closed enforcement에 가깝다.
- 따라서 “동적 생성”의 의미를 과대해석하면 안 된다.

### 4.2 generation class 별 현재 의미

| class | 현재 의미 | current 신뢰도 |
| --- | --- | --- |
| `trusted dynamic` | `llm_manifest` provenance. 현재 official lane은 fixture-backed only | 중 |
| `compiler-first` | catalog-resolved family -> scaffold/fragment compose | 중상 |
| `template-assisted` | built-in template 또는 runtime template clone | 중 |
| `deterministic fallback dependent` | fallback manifest로 닫힌 degraded path | 중하 |
| `pre-generation fail-closed` | semantic / provider / research precheck에서 생성 중단 | 높음 (negative lane 관점) |

## 5. 완성도 평가

### 5.1 구현 완성도

| 관점 | 현재 판정 | 설명 |
| --- | --- | --- |
| 파이프라인 closure | 중상 | PLAN → GENERATE → EXECUTE → VERIFY → REVIEW → PACK가 current E2E 기준 닫혀 있다 |
| provenance / gating | 중상 | generation_origin, dynamicness, semantic surface, verification_trust, promotion gating이 정교하다 |
| 이름만 주는 입력의 positive generalization | 중상 | supported alias/paraphrase/reordered phrase는 compiler-first positive evidence를 가진다 |
| open-world 동적 생성 | 중하 | unknown/open-world family는 compiler 부재와 live trusted-dynamic acceptance 부재로 상한이 낮다 |
| 템플릿 의존성 완화 | 중상 | filesystem template 의존은 줄었고 두 scaffold가 실제 positive lane을 갖는다. 다만 dependency는 catalog + limited scaffold + partial runtime contract로 재배치된 상태다 |
| 성능 | 중상 | no-sidecar compiler lane은 수 초~수십 초 초반, unsupported negative lane은 수십 ms대 fail-closed |
| 산출물 기계친화성 | 높음에 가까운 중상 | manifest / summary / policy / provenance / semantic surface가 강하다 |
| 산출물 인간친화성 | 중하~중 | README와 app realism은 개선됐지만 여전히 regression fixture 중심이다 |

### 5.2 일반화 / 이름만 제공한 동적 Docker 생성의 정확한 평가

현재 강한 주장으로 말할 수 있는 범위:

- 지원 family catalog에 포함된 취약점 이름/alias/paraphrase/reordered phrase는 compiler-first lower bound로 자동 materialize 가능하다.
- unsupported custom name은 success처럼 보이게 하지 않고 fail-closed negative regression으로 처리한다.
- 일부 supported family는 동일 family를 서로 다른 scaffold로 materialize할 수 있다.
- token-match medium-confidence lane도 실제로 닫힐 수 있지만, promotion/generalization evidence로는 더 보수적으로 분리된다.

현재 강한 주장으로 말하면 안 되는 범위:

- 임의의 free-form 취약점 이름에 대해 truly dynamic한 Docker/app/PoC를 안정적으로 생성한다.
- live remote LLM 기반 trusted-dynamic success가 official acceptance에 포함돼 있다.
- runtime/model/stack diversity가 충분하다.
- template dependence가 “사라졌다”.

정확한 표현은 아래가 맞다.

> 현재 레포는 “지원되는 취약 family에 대해서는 이름 기반 compiler-first lower bound를 제공하는 regression platform”이며,
> “open-world 동적 취약 Docker 생성기”로 보기에는 아직 이르다.

## 6. 일반화 / 템플릿 의존성 완화 재평가

### 6.1 현재 inventory

current workspace 기준 inventory:

- catalog family entry: 12개
- compiler-covered fragment strategy: 13개
- built-in template root: 3개
- scaffold asset: 2개 (`python/flask`, `python/fastapi`)
- FastAPI positive family: 5개 (`Open Redirect`, `Path Traversal`, `Template Injection`, `XSS`, `SSRF`)
- FastAPI scaffold-specific PoC asset: 5개

### 6.2 실제로 달성된 부분

- 취약점별 full filesystem template 복사 비중이 줄었다.
- compiler-covered family는 scaffold + fragment compose로 이동했다.
- shared vuln family catalog가 name normalization과 compiler routing을 함께 담당한다.
- runtime rule generation도 stack-aware로 정렬되기 시작했다.
- template lane semantic surface가 canonical taxonomy로 정리됐다.
- external DB template viability가 executor surface와 부분적으로 정렬되었다.
- built-in template가 explicit stack metadata를 가지게 되었고, template viability가 stack mismatch를 표현할 수 있게 됐다.
- FastAPI compiler lane은 service뿐 아니라 PoC asset 계층까지 분리되기 시작했다.
- template lane selection 근거가 `generator_template.json` / `resolved_contract.json`에 직접 surface되기 시작했다.
- second scaffold의 official positive coverage가 XSS / SSRF까지 확장되었다.
- XSS도 이제 declared rule을 가지므로 verification independence/trust가 더 안정적이다.

### 6.3 아직 남은 template / hardcoding debt

현재 debt는 “없어졌다”가 아니라 “위치가 바뀌었다”에 가깝다.

- second scaffold coverage는 이제 5개 family까지 늘었지만, 전체 compiler-covered family 범위로 보면 여전히 partial이다.
- compiler family 확장은 쉬워졌지만, registry의 대부분은 여전히 Flask 쪽에 편중되어 있다.
- FastAPI positive 5개 family는 이제 `fastapi-pocs` asset을 쓰지만, 전체 compiler family 범위로 보면 scaffold-specific PoC 분리는 아직 partial이다.
- template viability는 `db + executor feasibility + env-key contract` 수준까지만 정렬됐고, full capability DSL은 아니다.
- runtime template clone이나 future custom template가 explicit stack metadata를 가지지 않으면 planner는 여전히 permissive할 수 있다.
- template selection diagnostics는 template lane에만 직접 surface되고 있으며, pack top-level summary까지는 아직 부분적으로만 반영된다.
- compiler 이후 refinement가 없어서 artifact 다양성이 낮다.
- trusted-dynamic lane은 여전히 fixture-backed manifest에 의존한다.

따라서 template dependence reduction의 현재 정확한 평가는 아래다.

- filesystem template dependence: 부분 달성
- registry hardcoding reduction: 추가 개선 달성
- single-scaffold 탈피: 부분 달성
- compiler-first dynamic generation: 부분 달성
- open-world generation: 미달성

## 7. 산출물 품질 정성평가

### 7.1 강점

- bundle이 작고 deterministic해서 regression debugging이 쉽다.
- provenance / promotion / failure reason / semantic surface가 잘 드러난다.
- unsupported lane도 빠르게 닫혀 “성공처럼 보이는 garbage artifact”를 줄인다.
- compiler-generated README는 이제 scaffold/fragment/vuln_id뿐 아니라 service behavior / exploit contract / runtime assumptions까지 조금 더 드러난다.

### 7.2 약점

- app realism이 낮다. 대부분 single-route demo에 가깝다.
- compiler bundle README는 여전히 quickstart 중심이며, 실습 문서/운영 문서로는 얇다.
- trusted-dynamic fixture bundle 같은 일부 산출물은 사람 기준 설명력이 여전히 얇다.
- protocol-rich family도 semantic coverage 대비 runtime realism은 낮다.

### 7.3 현재 산출물의 체감 품질

실제 산출물 샘플 기준:

- compiler bundle은 대체로 5 files / 70~90 LOC 수준이며 README는 약 14줄 내외다.
- built-in MySQL template lane은 7 files / 약 181 LOC 수준으로 compiler bundle보다 설명력과 realism이 조금 높다.

정성평가 요약:

- regression fixture 품질: 높음
- provenance/report 품질: 높음
- 실습 패키지 품질: 중
- 현실적인 취약 앱 샘플 품질: 중하

## 8. 현재 구현계획의 타당성 재평가

이전 계획의 큰 방향은 여전히 맞다. 특히 아래는 타당하다.

- second scaffold 확장
- runtime surface DSL 정렬
- compiler 후 optional refinement
- live trusted-dynamic acceptance lane 확보
- human-facing output quality 개선
- template dependence reduction을 PoC / runtime contract / template schema / selection summary 계층까지 확장

다만 이번 턴 기준으로 우선순위는 조금 조정하는 편이 맞다.

### Priority 0. runtime surface / capability schema 통합

이번 턴 보완으로 template viability가 조금 나아졌지만, 아직 full capability DSL은 아니다.

다음 단계 권장:

- `runtime_surface`를 `framework`, `transport`, `db`, `sidecars`, `env`, `ports`, `health`, `network`, `seed_data` 단위로 분해
- template/scaffold/fragment가 자신이 만족하는 capability를 선언
- planner / template fallback / compiler feasibility / executor precheck / verifier summary가 같은 schema를 보도록 정렬

이유:

- 지금 가장 큰 상한은 “지원 family 수”보다 “runtime contract가 계층마다 부분적으로만 공유되는 구조”에서 온다.

### Priority 1. second scaffold 확장

권장:

- `python/fastapi`는 이제 XSS / SSRF까지 확장됐으므로, 다음은 LDAP Injection 같은 HTTP-centric family와 이후 non-HTTP family 일부를 검토
- 이후 typed Flask variation 또는 third scaffold 검토

이유:

- current generalization 상한의 큰 부분은 여전히 scaffold 다양성 부족에서 온다.

### Priority 2. scaffold-specific PoC / runtime rule 계층 분리

권장:

- FastAPI용 PoC asset 분리를 현재 3개 family에서 더 넓은 family coverage로 확장
- runtime rule generation과 PoC template layer가 같은 scaffold assumptions를 보도록 정렬
- stack-aware runtime rule regression을 더 많은 family로 확대

이유:

- 이번 턴에서 second scaffold는 exploit harness layer도 일부 분리됐지만, coverage는 아직 partial이다.

### Priority 2.5 template schema/capability hardening

권장:

- built-in template에 넣은 explicit `stack_id/language/framework`를 runtime template clone schema에도 일반화
- template metadata에 stack/runtime capability를 필수 또는 강권 필드로 승격
- planner가 “metadata 부족” 자체를 warning 또는 low-trust template signal로 다루게 정렬

이유:

- 현재 stack-aware template viability는 built-in template에는 유효하지만, template ecosystem 전체 기준으로는 아직 부분 적용이다.

### Priority 3. compiler 후 bounded refinement

권장:

- `compiler -> optional LLM refinement -> guard re-verify`
- route naming / helper layout / README / PoC robustness 정도만 bounded refinement 대상으로 제한
- AST/token diff budget과 provenance field를 같이 기록

이유:

- 지금의 compiler bundle은 안정적이지만 artifact 다양성과 realism이 낮다.

### Priority 4. live trusted-dynamic acceptance

현재 `trusted dynamic` official evidence는 fixture-backed only다.

권장:

- remote provider available 세션에서만 실행하는 optional live lane
- fixture lane과 live lane을 acceptance 표에서 명확히 분리

### Priority 5. human-facing output quality

권장:

- README schema를 bundle class별로 통일
- vulnerable endpoint / exploit contract / expected flag / runtime assumptions / sidecar contract를 자동 surface
- reviewer / pack summary에 human quick summary block 추가

## 9. Actionable Conclusion

현재 vulDocker는 다음 의미에서는 이미 꽤 완성돼 있다.

- curated 취약 family에 대한 deterministic compiler-first regression platform
- 이름만 주는 입력의 supported/unsupported 분기와 fail-closed 정책
- provenance / promotion / semantic surface / failure taxonomy 기반 artifact pipeline

그러나 다음 의미로는 아직 미완이다.

- open-world free-form 취약점 이름에 대한 truly dynamic Docker generation
- template dependence가 충분히 사라진 multi-stack generator
- live remote LLM까지 포함한 trusted-dynamic acceptance baseline

한 줄 요약:

> 현재 vulDocker는 “지원 family에 대한 이름 기반 compiler-first regression platform”으로는 중상 수준이며,
> 이번 턴에서 stack-aware runtime rule, canonical semantic source, stack-aware template viability, partial scaffold-specific PoC separation까지 반영됐다.
> 다만 “open-world 동적 취약 Docker 생성기”로 보기에는 limited multi-scaffold, no-refinement, fixture-only trusted-dynamic, partial runtime DSL, partial-only PoC/template schema hardening이라는 구조적 상한이 여전히 남아 있다.
