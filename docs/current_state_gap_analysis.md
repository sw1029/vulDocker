# 동적 취약 Docker 생성 Current State / Gap Analysis

본 문서는 2026-03-11 KST 기준 current workspace를 다시 검토한 뒤, 기존의 "현 상태 요약" 문서를 계획 문서로 전면 재작성한 것이다.

이 문서의 목적은 세 가지다.

1. 현재 구현이 실제로 어디까지 닫혀 있는지 과장 없이 다시 고정한다.
2. "일반화된 open-world 동적 취약 Docker 생성기"로 가기 위한 현실적인 전환 경로를 정의한다.
3. 초기 설계인 `Researcher -> RAG -> LLM response -> 동적 Docker 생성`을 버리지 않고 살리는 방향으로 우선순위를 재정렬한다.

이 문서는 더 이상 단순한 current-state 기록이 아니다. 현재 truth를 바탕으로 한 "재설계/전환 계획 문서"다.

## 1. Truth Protocol

이 문서는 아래 원칙을 따른다.

- current workspace rerun만 현재 상태의 1차 근거로 쓴다.
- `sid-*`는 immutable evidence가 아니라 rerun locator로만 본다.
- `compiler-first`는 curated family catalog + scaffold/fragment compose 경로를 뜻한다.
- `template-assisted`는 built-in template 또는 runtime template clone 경로를 뜻한다.
- `trusted dynamic`은 `llm_manifest` provenance가 명시된 경우에만 쓴다.
- `research_short_circuit`는 semantic/research 단계에서 fail-closed로 생성 자체가 멈춘 경로를 뜻한다.
- unsupported free-form lane을 generic success처럼 해석하지 않는다.
- machine-local absolute path는 top-level truth가 아니라 내부 detail로만 다룬다.

## 2. Current Truth Baseline

### 2.1 테스트 기준선

2026-03-11 KST current workspace rerun:

| command | result | 해석 |
| --- | --- | --- |
| `python -m pytest -q tests` | `443 passed, 39 skipped in 2.01s` | unit/integration baseline 유지 |
| `VULD_RUN_E2E=1 python -m pytest -q tests/e2e/test_cases.py -rs` | `37 passed, 2 skipped in 340.16s` | 공식 Docker E2E baseline 유지 |

즉 현재 구현은 regression platform 관점에서는 충분히 닫혀 있다.

### 2.2 현재 공식 identity

현재 레포에 대해 강하게 말할 수 있는 것은 아래다.

- 지원 family에 대해서는 이름 기반 compiler-first lower bound가 있다.
- unsupported free-form name은 success처럼 보이게 하지 않고 fail-closed negative regression으로 다룬다.
- provenance, verification trust, semantic surface, promotion gating은 꽤 잘 surface된다.
- second scaffold는 `python/fastapi`까지 확장되었지만 partial coverage다.
- `trusted dynamic` official evidence는 여전히 fixture-backed lane에 머물러 있다.
- known family에 대해 optional `researcher.shadow_mode`가 추가되어,
  lower-bound lane을 깨지 않으면서 shadow researcher spec를 축적할 수 있는 운영 옵션이 생겼다.

반대로 아직 강하게 말하면 안 되는 것은 아래다.

- 임의의 free-form 취약점 이름에 대해 open-world하게 Docker/app/PoC를 안정적으로 생성한다.
- live remote LLM 기반 trusted-dynamic success가 acceptance baseline에 포함돼 있다.
- runtime/model/stack diversity가 충분하다.
- template dependence가 사라졌다.

정확한 현재 평가는 아래 한 문장으로 요약된다.

> 현재 vulDocker는 "지원 family에 대한 이름 기반 compiler-first regression platform"으로는 중상 수준이지만,
> "일반화된 open-world 동적 취약 Docker 생성기"로 보기에는 아직 이르다.

### 2.3 현재 inventory

current workspace 기준 inventory:

- catalog family entry: 12개
- compiler-covered fragment strategy: 13개
- built-in template root: 3개
- scaffold asset: 2개 (`python/flask`, `python/fastapi`)
- FastAPI positive family: 5개 (`Open Redirect`, `Path Traversal`, `Template Injection`, `XSS`, `SSRF`)

### 2.4 현재 generation class의 정확한 의미

| class | 현재 의미 | 현재 신뢰도 |
| --- | --- | --- |
| `compiler-first` | catalog-resolved family를 scaffold/fragment로 materialize | 중상 |
| `template-assisted` | built-in template 또는 runtime template clone | 중 |
| `trusted dynamic` | `llm_manifest` provenance. official lane은 fixture-backed only | 중 |
| `deterministic fallback dependent` | fallback manifest에 의존한 degraded path | 중하 |
| `research_short_circuit` | semantic/research precheck에서 fail-closed | 높음 |

### 2.5 후속 점검에서 이미 닫힌 correctness gap

이번 후속 코드 보완으로 아래 네 가지는 current workspace에서 더 이상 "현재 gap"으로 두면 안 된다.

- external DB template viability가 sidecar 존재만 보고 compatible하다고 오판하던 문제는 닫혔다.
  이제 compatible sidecar type이 없으면 viability가 거절되고, template `service_env` 값이 실제 runtime surface와 다르면 template path가 거절된다.
- template mode가 `runtime.db` 미지정 시 internal-db viable template를 못 찾던 문제는 닫혔다.
  즉 `runtime.db`가 비어 있어도 stack/vuln/runtime surface가 맞는 internal template는 viable하게 취급된다.
- explicit unsupported identifier가 genericized `pattern_id`를 가지더라도 incidental stack/evidence 키워드만으로
  SQLi/XSS류 known-family `semantic_signature`를 재주입받던 문제는 닫혔다.
  현재 unsupported unknown lane은 명시적 structured semantic contract가 없으면 `semantic_signature`가 기본적으로 empty로 남는다.
- legacy `generalization_*` 집계가 alias-resolved name-only compiler lane을 generalization처럼 보이게 만들던 해석 문제는
  compatibility surface와 open-world surface를 분리하는 방식으로 완화됐다.
  현재 manifest에는 `open_world_*` / `open_world_summary`가 추가되어 lower-bound dependent lane을 별도 분류한다.
- `resolved_contract`와 PACK manifest에 `runtime_recipe` surface가 추가됐다.
  현재는 full capability schema는 아니지만 `language`, `framework`, `transport`, `db`, `allow_external_db`,
  `requires_external_db`, `network_mode`, `network_enabled`, `sidecars`, `service_env`, `seed_files`, `topology`
  정도는 단일 payload로 볼 수 있다.
- synthesis prompt에도 `runtime_recipe` 요약 block과 `generation posture` block이 추가되었다.
  특히 `NAME-*` lane은 prompt 수준에서 open-world/name-driven posture를 명시하고,
  Guard Spec 또는 Researcher evidence가 없는 한 repo 내부 family demo prior를 직접 주입하지 않도록 완화되었다.
- opt-in `policy.dynamic_eval=true`가 추가되었다.
  현재는 evaluation lane 성격으로, RESEARCH skip과 synthesis mode의 compiler-first short-circuit를 우회해
  lower-bound path를 비교군으로 분리한 채 동적 생성 경로를 먼저 보게 만든다.
  필요 시 `policy.dynamic_eval_allow_lower_bound_fallback=true`로 합성 실패 뒤 compiler/template lower bound로 다시 수렴할 수 있다.
- synthesis prompt는 이제 가능할 때 `resolved_contract.runtime_recipe`를 requirement payload에 다시 hydrate해서 받는다.
  즉 prompt가 raw requirement만 보지 않고 plan/research/contract 단계에서 정리된 runtime recipe surface를 참고하게 되었다.
- Researcher query seed도 request label / pattern / runtime anchor를 우선하고,
  `E2E`, `회귀`, `검증` 같은 내부 regression intent noise는 기본적으로 검색어에서 배제하도록 보정되었다.
- 추가로 current workspace follow-up에서는 lightweight `query_plan` surface가 도입되었다.
  현재 report/history에는 `family_hypotheses`, `exploit_hypotheses`, query별 `evidence_type`(`advisory`, `writeup`,
  `reference_impl`, `oracle_hint`)가 남고, `evidence_type_summary`도 researcher report에 포함된다.
- 후속 보완으로 `family_hypothesis_summary`도 report에 추가되었다.
  현재는 evidence-backed `top_family`, `top_confidence`, `contradiction_count`, `contradictory_families`를 남기며,
  PACK의 bundle/top-level `researcher_summary`에서도 이 요약을 볼 수 있다.
- 가장 최근 follow-up에서는 family hypothesis confidence도 calibration된다.
  즉 lexical score만 높아도 contradiction가 많고 top margin이 약하면 `raw_top_confidence=high`라도
  `top_confidence=low`로 떨어질 수 있다.
- semantic-guided fallback도 이제 이 summary를 실제로 읽는다.
  `dynamic_eval` lane에서 top family가 low-confidence/ambiguous이거나 semantic family와 불일치하면
  repo family asset으로의 semantic-guided fallback을 차단한다.
- 후속 보완으로 `Open Redirect` / `XSS` / `Path Traversal` / `SSRF` / `Insecure Deserialization` 일부 family에는 asset copy 대신
  lightweight Flask scaffold + inline PoC를 조립하는 `minimal_dynamic` materializer가 들어갔다.
  즉 semantic-guided degraded path 안에서도 template dependence를 한 단계 더 줄이는 실험이 시작되었다.
- 가장 최근 follow-up에서는 dynamic_eval lane이 non-JSON stub response일 때뿐 아니라,
  JSON 형태지만 guard를 통과하지 못하는 low-quality candidate만 남아도 마지막으로
  `semantic_guided recovery candidate`를 한 번 더 시도한다.
  이 보정은 open-world upper bound를 올리기보다, degraded name-only lane이
  저품질 stub JSON 때문에 불필요하게 `GENERATOR` 단계에서 붕괴되는 경우를 줄이는 쪽에 가깝다.
- PACK researcher summary는 이제 skip report를 `report_present=true, ran=false`로 구분한다.
  또한 `artifact_quality`는 thin README를 더 강하게 감점해 fixture-style dynamic bundle의 사람 기준 설명력을 더 정직하게 반영한다.
- deterministic fallback도 `NAME-*` lane에서는 기본적으로 family-aware asset을 사용하지 않게 바뀌었다.
  현재는 `policy.allow_name_family_fallback=true`일 때만 name-only lane에서 family-aware fallback을 허용한다.
  즉 degraded path에서도 "이름만 맞으면 repo 내 family asset으로 수렴"하던 기본 경향이 한 단계 약화됐다.
- 추가로 `policy.dynamic_eval=true`인 경우에는 Guard Spec semantic signature와 builtin family semantics가 강하게 정렬될 때
  semantic-guided fallback이 먼저 적용된다.
  이 경로는 lower-bound compiler/template recovery와는 분리 기록되지만, provenance상 여전히 `deterministic_fallback` degraded lane이다.
- asset-backed fallback README도 quickstart-only 형태에서 runtime/verification card를 포함하도록 보강되었다.
  따라서 dynamic_eval degraded success도 operator-facing 설명력이 조금 더 좋아졌지만, 이것은 open-world capability 상승이 아니라
  degraded artifact quality 보정에 가깝다.

다만 이것은 open-world 상한을 올린 것이 아니라 current correctness를 강화한 것이다.

### 2.6 environment-sensitive truth에 대한 주의

unknown live lane은 machine/env에 따라 관측이 달라질 수 있다.

- remote search provider가 꺼져 있으면 `cwe-unknown-basic`은 research fail-closed negative lane으로 남는다.
- remote search provider가 켜져 있더라도 current workspace follow-up에서는 explicit unsupported identifier가
  pattern-derived relevance/semantic bias를 받지 않도록 정리되었고, evidence relevance가 낮으면 RESEARCH 단계에서 fail-closed 된다.
- 즉 이전처럼 live unknown lane이 low-trust fallback success나 generic fallback generation으로 쉽게 넘어가지 않는다.
- normalization 단계에서도 unsupported unknown family는 기본적으로 `pattern_id=generic-web-vuln`으로 강등된다.
  known-family pattern seed를 유지하려면 explicit opt-in이 필요하다.

중요한 점은 두 경우 모두 이것을 generalization success로 해석하면 안 된다는 것이다.
현재 구현은 promotion/gating에 더해 `open_world_*` surface로도 이를 분리하지만, open-world quality를 증명한 것은 아니다.

### 2.7 acceptance baseline의 open-world 해석

current rerun manifest 집계 기준으로 unique case baseline은 아래에 가깝다.

- `compiler-first`: 29
- `template-assisted`: 1
- `trusted dynamic`: 2
- `pre-generation fail-closed`: 3
- `mixed`: 1

그리고 새 `open_world_summary` 기준으로는 아래가 현재 truth다.

- `positive_open_world_bundles`: 0
- alias/name-only known-family success 다수는 `catalog_resolved_lower_bound`
- token-match free-form lane은 `catalog_token_match_lower_bound`
- built-in template lane은 `template_dependent_bundles`로 분리
- runtime/topology truth는 개별 file/summary에 흩어진 값만 보지 않고 `runtime_recipe` surface로 1차 해석 가능

추가로 현재 manifest에는 아래 evaluation surface가 새로 있다.

- `runtime_recipe`: runtime/topology/env/sidecar/network의 단일 요약 payload
- `artifact_quality` / `artifact_quality_summary`: README, topology clarity, oracle clarity 기반 정성 품질 surface
- `template_dependence_summary`: template-assisted / lower-bound dependent / name-only lower-bound 비중 surface
- `strict_open_world` / `strict_open_world_summary`: curated lower bound / template lane / fixture/stub-backed dynamic /
  degraded researcher / non-independent verifier를 별도 exclusion class로 분리하는 더 보수적인 open-world 해석 surface
- `memory_promotion`: pipeline success/promotion과 별도로, strict open-world positive + 높은 artifact quality를 만족할 때만
  future runtime memory/template/oracle로 승격 가능한지 보는 surface
- `request_identity` / `request_identity_summary`: raw request label, input mode, match class, confidence, synthetic/catalog/token-match 여부를
  `name_resolution`과 분리해 보여 주는 pre-research identity surface
- `policy.dynamic_eval`: lower-bound shortcut을 잠시 비활성화한 채 synthesis/research lane을 먼저 보게 하는 opt-in evaluation surface

즉 현재 acceptance는 여전히 curated lower bound 중심이며,
이번 follow-up은 그것을 더 정직하게 보이도록 만든 것이다.

### 2.8 strict open-world surface의 의미

이번 추가 구현으로 `PACK` manifest에는 `strict_open_world` / `strict_open_world_summary`가 더해졌다.

이 surface는 기존 `open_world_*`보다 더 보수적이다.

- `compiler-first` alias/name-only success는 `strict_curated_lower_bound`
- template lane은 `strict_template_dependent`
- fixture-backed `trusted dynamic` lane은 `strict_fixture_backed_dynamic`
- stub-backed lane은 `strict_stub_backed_dynamic`
- verifier independence가 낮으면 `strict_verifier_coupled`
- live dynamic + no lower bound + no template + no fixture/stub + non-degraded researcher + independent high-trust verifier일 때만
  `strict_open_world_positive`

즉 `strict_open_world_*`는 "현재 구현이 정말 open-world 동적 생성으로 어디까지 갔는가"를
promotion/compatibility surface보다 더 엄격하게 읽기 위한 보조 taxonomy다.

current rerun 기준 해석은 아래에 가깝다.

- `strict_open_world_summary.positive_strict_open_world_bundles`: 0
- compiler/name-only positive 다수는 `strict_curated_lower_bound`
- built-in template lane은 `strict_template_dependent`
- fixture-backed trusted-dynamic lane은 `strict_fixture_backed_dynamic`
- compiler/template/lower-bound success 상당수는 `promotion`은 가능해도 `memory_promotion`은 불가
- `request_identity`는 이제 bundle별로 raw label과 resolved canonical id를 함께 남기고,
  researcher report에도 lightweight `family_hypotheses` / `family_hypothesis_summary`가 별도 기록된다.
  다만 이것은 아직 authoritative staged IR는 아니고 query planning / report surface 수준이다.
- `resolved_contract.semantic_contract`에도 이제 `family_hypothesis_summary`가 함께 보존된다.
  또한 synthesis prompt에는 `# Researcher Family Hypothesis` block이 추가되어,
  low-ambiguity hypothesis는 working hypothesis로 활용하고 contradiction-heavy hypothesis는 과신하지 않도록 유도한다.
- current rerun `request_identity_summary`는 대략 `free_form_name 24 / explicit_identifier 2`,
  `catalog_alias 22 / token_match 4 / synthetic_name 1`에 가깝다

따라서 현재 workspace는 `open_world_*`와 `strict_open_world_*`를 함께 보아야 한다.
전자는 curated lower bound와의 관계를 정직하게 나누는 surface이고,
후자는 live strict open-world acceptance 상한을 더 보수적으로 잡는 surface다.

## 3. 현재 구조의 정확한 해석

### 3.1 지금 실제로 돌아가는 중심 구조

현재 minimal-input path는 사실상 아래 체인에 가깝다.

1. free-form label을 canonical `CWE-*` 또는 `NAME-*`로 정규화
2. shared vuln family catalog로 alias / identifier / pattern / token-match 수행
3. `semantic_profile`과 `compiler_supported` lower-bound verdict 생성
4. 지원 family면 researcher를 건너뛰거나 약하게 사용하고 compiler-first path로 이동
5. 미지원 free-form `NAME-*`면 research/semantic gate에서 fail-closed
6. synthesis/template/hybrid는 lower-bound path를 보조하거나 degraded lane을 채움

단, 현재는 여기서 작은 변화가 하나 생겼다.

- 기본 운영은 여전히 "지원 family면 researcher skip 가능"이지만,
  `researcher.shadow_mode=true`면 supported lower-bound lane에서도 non-blocking shadow researcher를 실행할 수 있다.

즉 현재 구조는 open-world semantic inference라기보다 아래에 가깝다.

- curated semantic-family routing
- deterministic lower bound
- fail-closed enforcement

이건 나쁜 것이 아니다. 다만 "초기 설계"와 "현재 운영 중심" 사이에 차이가 있다는 뜻이다.

### 3.2 초기 설계와 현재 구조의 차이

초기 설계의 핵심은 아래였다.

- Researcher가 외부/내부 지식을 모은다
- RAG와 함께 LLM이 동적으로 vuln spec을 만들고
- 그 결과로 Docker/app/PoC를 생성한다

현재 구현은 그 설계의 뼈대를 보존하고 있지만, 실제 운영의 중심은 아래로 이동했다.

- known family는 compiler/template가 주도
- Researcher는 optional 또는 skip되는 경우가 많음
- LLM synthesis는 존재하지만 non-JSON/오류 시 deterministic fallback으로 빠르게 수렴
- verifier도 declared rule 또는 compiler/runtime rule에 더 강하게 의존

따라서 앞으로의 목표는 "초기 설계를 버리고 새 구조를 만드는 것"이 아니라 아래다.

> Researcher/RAG/LLM을 다시 primary path로 승격하고,
> compiler/template/fallback 자산은 lower-bound materializer와 reusable memory로 재배치한다.

## 4. 무엇을 보존하고 무엇을 바꿔야 하는가

### 4.1 반드시 보존해야 하는 것

- 아키텍처 단계: `PLAN -> RESEARCH -> GENERATE -> EXECUTE -> VERIFY -> REVIEW -> PACK`
- fail-closed 철학: unsupported/low-trust/open-world 실패를 success처럼 보이게 하지 않는 것
- provenance surface: `generation_origin`, `verification_trust`, `semantic_source`, promotion gating
- deterministic lower bound: compiler/template/fallback이 regression baseline을 제공하는 구조
- GuardSpec / resolved_contract / metadata 중심의 재현성

### 4.2 반드시 바꿔야 하는 것

- Researcher를 known family에선 자주 skip하는 현재 운영 중심
- prompt에 남아 있는 CWE-specific semantic hardcoding
- one-shot JSON manifest 생성에 과도하게 의존하는 synthesis 구조
- runtime capability를 stage마다 다르게 해석하는 구조
- static rule이 없는 경우 낮은 독립성을 가진 verifier fallback
- template/fragment 자산을 "최종 truth"로 해석하는 운영 방식

## 5. Open-World로 가기 위해 현재 즉시 해결해야 할 구조적 gap

### 5.1 Researcher가 생성의 1급 입력이 아님

현재 open-world 상한을 가장 크게 막는 것은 이 점이다.

- supported family는 Researcher를 skip하는 경우가 많다.
- Researcher output은 generator가 참고는 하지만 주 계약이 아니다.
- known family와 unknown family의 생성 경로가 크게 분리되어 있다.

영향:

- 초기 설계의 핵심인 "researcher를 통해 얻은 정보 기반 동적 생성"이 주 경로가 되지 못한다.
- open-world lane에서 얻은 지식이 known-family lane으로 재주입되지 않는다.

필요한 변화:

- dynamic lane에서는 Researcher를 primary stage로 승격
- known family에서도 shadow mode로 Researcher를 계속 실행해 spec quality를 축적

### 5.2 Researcher output이 생성기 소비용 structured spec이 아님

현재 `researcher_report.json`은 정보량은 있지만 생성기 입력으로는 느슨하다.

부족한 점:

- semantic signature는 있으나 runtime topology spec이 약하다
- exploit oracle이 충분히 구조화돼 있지 않다
- file-role/build plan/seed data/service env/health contract가 생성기 주입력으로 강하지 않다

필요한 변화:

- `vuln_spec.json`
- `runtime_recipe.json`
- `exploit_oracle.json`
- `guard_spec.json`

같은 구조화 산출물로 분해/격상해야 한다.

### 5.3 Prompt가 여전히 rule/CWE 하드코딩에 많이 의존

현재 synthesis prompt는 예전보다 덜 경직돼 있지만, 아직 known-family rule prior가 남아 있다.

문제:

- known family에는 강하지만 unknown/open-world lane엔 여전히 상한이 낮다
- `NAME-*` lane은 이제 별도의 open-world generation posture와 `runtime_recipe` block을 받지만,
  이것은 prompt-layer de-hardcoding일 뿐 generator core의 spec-driven execution은 아니다
- known CWE prompt는 여전히 rule/CWE prior를 직접 포함하므로 Researcher-derived semantic/runtime contract가 primary authority가 아니다
- open-world lane에서 "연구 기반 동적 생성"이 아니라 "정적 knowledge fallback"으로 기울어지는 근본 구조는 그대로다

필요한 변화:

- prompt에서 CWE 하드코딩을 더 축소하고, known-family lane에서도 Researcher/Guard 기반 override가 더 강하게 먹히게 조정
- Researcher-derived semantic/runtime/oracle contract를 primary prompt block으로 승격
- static rule은 가능한 경우 verifier/compatibility baseline으로만 사용
- prompt de-hardcoding을 prompt-layer에만 두지 말고 staged IR/materializer contract까지 연결

### 5.4 One-shot manifest + 빠른 deterministic fallback 구조

현재 synthesis는 LLM이 곧바로 최종 manifest JSON을 내는 구조다.

문제:

- LLM 응답이 조금만 어긋나도 non-JSON -> fallback으로 급격히 무너진다
- repair loop가 있어도 추상도가 너무 높아 수정 비용이 크다
- open-world 상황에서 모델이 "모든 것"을 한 번에 맞춰야 한다
- name-only lane의 degraded path는 이전보다 정직해졌지만, generic fallback이나 fail-closed 쪽으로 더 자주 수렴할 수 있다
  즉 template/family asset dependence를 줄인 대가로 temporary acceptance headroom이 줄 수 있다

필요한 변화:

- one-shot final manifest 대신 staged synthesis
- `design plan -> patch/injection manifest -> file-role manifest -> code blocks -> repair`
- LLM은 단계별로 더 작은 결정을 하게 하고, materializer는 deterministic하게 유지
- generic fallback 자체도 "minimal topology + neutral oracle" 수준으로 더 분리해,
  known-family asset과 unsupported/name-only degraded lane 사이의 경계를 더 선명하게 해야 한다

### 5.5 Runtime capability schema가 계층마다 분절돼 있음

현재 가장 중요한 구조적 병목은 이 부분이다.

현재 runtime 관련 결정이 다음 계층에 흩어져 있다.

- template viability
- compiler feasibility
- derive_service_env
- executor sidecar/network handling
- verifier summary

문제:

- 같은 bundle을 계층마다 다른 기준으로 viable/compatible하다고 해석할 수 있다
- external DB/service topology 같은 경우 오탐 viable이 남을 수 있다
- open-world lane에서 LLM이 runtime topology를 제안해도 공통 schema가 없어서 소비가 어렵다

즉시 확인된 구체 리스크:

- 이번 후속 구현으로 external DB template viability의 sidecar type mismatch false-positive는 닫혔다
- 이번 후속 구현으로 `runtime.db` 미지정 시 internal-db viable template discovery gap도 닫혔다
- 이번 후속 구현으로 explicit unsupported identifier는 researcher relevance/semantic inference에서 `pattern_id`/stack keyword bias를 받지 않게 되었다
- 이번 후속 구현으로 normalization 단계에서 unsupported unknown family의 inherited `pattern_id`도 기본적으로 generic으로 강등된다
- 다만 capability 판단은 여전히 `template viability / derive_service_env / executor summary / verifier summary`에 분산되어 있다
- pack/perf summary 계층의 executor feasibility는 template viability만큼 세밀한 env-level contract까지는 아직 보지 못한다
- explicit unsupported identifier에 대해 family-aware fallback을 허용하던 path는 닫혔다
- 다만 unsupported open-world lane은 `pattern_id`가 opt-in 시 다시 known-family seed로 들어올 수 있고, metadata/generalization reason에도 일부 흔적이 남을 수 있다
- fallback guard는 일부 FastAPI lane에서도 Flask-biased assertion에 기대는 부분이 남아 있다
- legacy `generalization_*` surface는 하위 호환 때문에 남아 있고, open-world 해석은 새 `open_world_*` surface를 봐야 한다

필요한 변화:

- 공통 capability schema 도입
- 최소 필드: `framework`, `transport`, `db`, `sidecars`, `env`, `ports`, `health`, `network`, `seed_data`
- planner/template/compiler/executor/verifier가 동일 schema를 읽게 정렬

현재 상태 메모:

- 이번 follow-up으로 `runtime_recipe` surface가 추가되었지만 아직 summary-grade다.
- `ports`, `health`, `seed_data`는 일부만 채워지고 source provenance도 필드별로 분해되어 있지 않다.
- 즉 capability schema work는 시작됐지만 아직 완료된 것은 아니다.
- 이번 follow-up으로 `artifact_quality_summary` / `template_dependence_summary`도 추가되었지만,
  이것 역시 heuristic scoring/rollup 수준이며 아직 hard gate는 아니다.

### 5.6 Verifier independence가 open-world에서 충분히 높지 않음

static rule이 없는 family에서는 verifier가 resolved contract oracle fallback, generator_manifest fallback,
또는 runtime rule에 기대는 경우가 있다.

문제:

- generated artifact와 verifier contract가 서로 coupled될 수 있다
- open-world lane에서 "성공"의 의미가 약해진다

필요한 변화:

- Researcher가 `exploit_oracle`을 구조화해서 제공
- verifier는 rule이 없을 때 oracle + metamorphic/negative control을 사용
- 현재 workspace는 `exploit_oracle` preview fallback을 먼저 읽게 되었지만,
  이것도 아직 `contract_coupled` low-trust lane이므로 independent acceptance로 승격해선 안 된다

### 5.7 산출물 품질은 regression fixture 중심

현재 산출물의 강점은 명확하다.

- 작고 deterministic하다
- provenance와 debugging이 좋다
- regression에는 매우 적합하다

그러나 약점도 명확하다.

- compiler bundle은 대부분 single-route demo에 가깝다
- README는 개선됐지만 여전히 quickstart 중심이다
- trusted-dynamic fixture bundle은 사람 기준 설명력이 약하다

즉 현재 산출물 품질은 아래처럼 나뉜다.

- regression fixture 품질: 높음
- provenance/report 품질: 높음
- 실습 패키지 품질: 중
- 현실적인 취약 앱 샘플 품질: 중하

### 5.8 strict evaluation mode가 아직 partial이다

이번 follow-up으로 `strict_open_world_*` surface가 추가되었고,
추가로 opt-in `policy.open_world_strict=true`에서는 name-driven lane에서
Researcher skip을 막고 degraded/local-only research evidence를 insufficient로 처리하도록 보완되었다.
다만 이것이 아직 full strict mode는 아니다.

현재 남은 한계:

- `strict_open_world`의 핵심은 여전히 PACK-stage classification이다.
  다만 current workspace follow-up에서는 name-only `strict_dynamic` lane에 한해
  generator 산출이 이미 `deterministic_fallback`, `llm_stub_used`, `llm_fixture_used`,
  `degraded_success` 같은 disallowed posture를 드러내면 EXECUTOR 전에 조기 중단하는 gate가 추가되었다.
  즉 strict mode가 여전히 fully staged execution profile은 아니지만,
  적어도 "명백히 strict intent를 만족할 수 없는 generation posture"를 끝까지 실행한 뒤 PACK에서만 탈락시키는 비효율은 일부 줄었다.
- `policy.open_world_strict`는 현재 "name-driven lane에서 Researcher skip 금지 + degraded/local-only research evidence 차단" 정도만 다룬다.
  verifier fallback/fixture/stub/local search degradation을 execution 전반에서 일괄 차단하는 수준까지는 아니다.
- LLM provider failure 시 stub fallback, search failure 시 local fallback 같은 runtime degradation은 여전히 pipeline continuity를 위해 허용된다.
  `strict_open_world`는 이를 사후 분류할 뿐, 사전에 강제 차단하지는 않는다.
- legacy `generalization_*`와 새 `open_world_*` / `strict_open_world_*`를 동시에 보는 기간이 남아 있다.

필요한 변화:

- explicit `open_world_strict` execution/eval mode 도입
- strict mode에서는 fixture/stub/local-only fallback/self-derived verifier를 acceptance 집계에서 자동 제외
- dashboard/CI/test expectation도 `strict_open_world_*`를 primary로 보는 경로를 별도 마련

### 5.9 request label과 family hypothesis가 아직 충분히 분리되지 않는다

현재 requirement normalization은 비교적 이른 단계에서 free-form label을 `NAME-*` synthetic identifier로 canonicalize한다.

문제:

- unresolved user label
- evidence-backed family hypothesis
- 최종 canonical vuln id

가 하나의 흐름으로 빠르게 접힌다.

영향:

- open-world lane에서 조기 family 확신이 생기기 쉽다
- catalog/token-match lower bound와 truly unresolved lane의 차이를 내부 IR 수준에서 세밀하게 보존하기 어렵다

필요한 변화:

- `request_label`
- `family_hypothesis`
- `resolved_vuln_id`

를 분리한 staged IR 도입

현재 상태 메모:

- 이번 follow-up으로 `request_identity` / `request_identity_summary`가 추가되었다.
- 여기에는 `request_label`, `input_mode`, `match_class`, `confidence`, `synthetic_resolution`,
  `catalog_backed_resolution`, `token_match_resolution` 등이 들어간다.
- 즉 raw request label과 resolved canonical id가 같은 payload 안에 남기 시작했다.
- 다만 이것은 아직 pre-research surface다.
  Researcher evidence를 거친 `family_hypothesis`와 최종 `resolved_vuln_id`를 별도 stage IR로 가지는 수준까지는 아니다.

### 5.10 retrieval/query planning quality가 여전히 약하다

open-world 상한을 실제로 막는 병목 중 하나는 Researcher query seed quality다.

문제:

- current query seed는 개선되었지만 여전히 heuristic 중심이다.
- unsupported explicit identifier lane에서는 remote hit가 있어도 무관한 Flask/E2E/DB 일반 문서로 흘러갈 수 있다.
- free-form label, pattern, stack, exploit hypothesis를 단계적으로 분해한 query planning이 없다.

필요한 변화:

- `query_plan` stage 도입
- `request_label -> stack/runtime anchor -> family hypothesis -> exploit hypothesis` 순으로 질의를 분해
- evidence type(`advisory`, `writeup`, `reference impl`, `oracle hint`)을 구분해서 retrieval quality를 계량

현재 상태 메모:

- 이번 follow-up으로 request label / pattern / runtime 기반 query가 앞쪽으로 정렬되고 regression intent noise는 줄었다.
- `query_plan` / `family_hypotheses` / `exploit_hypotheses` / `evidence_type_summary`가 report에 남기 시작했다.
- `family_hypothesis_summary`가 추가되어 top family와 contradiction count를 researcher report와 PACK bundle summary에서 읽을 수 있다.
- contradiction-aware confidence calibration도 추가되었다.
  따라서 unsupported unknown lane에서 lexical hit가 많아도 ambiguity가 크면 top family confidence는 낮아진다.
- semantic-guided fallback gate도 추가되었다.
  따라서 contradiction-heavy family hypothesis는 dynamic_eval degradation path의 family asset 선택에도 직접 영향을 준다.
- open redirect name-only rerun에서는 이 planner가 실제로 advisory/writeup/reference_impl을 분리해 높은 relevance로 수렴했다.
- 반대로 unknown synthetic lane은 stack-only remote hit가 있어도 semantic/family/exploit alignment가 없으면
  score가 threshold 아래로 cap되어 fail-closed를 유지한다.
- 그러나 이것만으로는 full retrieval planner가 된 것이 아니다.

### 5.11 open-world capability를 측정하는 execution lane이 기본 경로에 없다

현재 기본 운영은 lower-bound preservation에 맞춰져 있다.

문제:

- compiler/template shortcut이 기본이라 supported family의 dynamic upper bound를 평상시에는 관측하기 어렵다.
- `shadow_mode`는 observation hook이지 generation path inversion이 아니다.

필요한 변화:

- explicit `dynamic_eval` lane 유지
- 이 lane에서 researcher skip / compiler-first short-circuit / template auto-close를 끈 상태로 synthesis를 먼저 본다
- lower-bound는 성공 path가 아니라 comparison baseline으로 병렬 기록한다

현재 상태 메모:

- 이번 follow-up으로 opt-in `policy.dynamic_eval=true`가 추가되어 RESEARCH skip과 synthesis mode의 compiler-first short-circuit를 우회할 수 있다.
- 다만 이것은 아직 evaluation lane이다.
  default 운영이 바뀐 것은 아니고, hybrid/template mode까지 완전히 staged comparison runner로 재구성된 것도 아니다.

### 5.12 memory/promotion loop에는 contamination control이 필요하다

문제:

- dynamic 결과를 곧바로 future template/memory로 승격하면 잘못된 artifact가 lower bound를 오염시킬 수 있다.
- current `memory_promotion`은 분류 taxonomy일 뿐, quarantine/review/replay gate가 없다.

필요한 변화:

- `quarantine -> replay -> independent verify -> promote` 4단계 승격
- semantic/oracle/runtime contract digest 기반 dedup
- rollback/expiry policy

### 5.13 cost/latency budget이 아직 로드맵에 없다

문제:

- Researcher-first + staged synthesis + oracle verification은 호출 수와 wall-clock을 빠르게 키운다.
- current plan은 quality/open-world 지표는 많지만 비용/지연 SLO가 없다.

필요한 변화:

- phase별 `max remote queries`, `max llm calls`, `target wall-clock` budget 정의
- strict mode / dynamic_eval / default regression mode를 비용 profile로도 분리
- artifact quality uplift와 latency 증가 사이의 trade-off를 acceptance에 반영

현재 상태 메모:

- current representative rerun에서도 compiler-first 약 7~8s, fixture dynamic 약 9s, sidecar template 약 20s로 차이가 크다.
- staged open-world path를 넣으려면 latency budget 없이 운영하기 어렵다.

## 6. 현재까지 구현한 tmpl/template 자원에 대한 판단

결론부터 말하면 현재 자원을 버릴 필요는 없다.

버려야 하는 것은 자원 자체가 아니라 자원의 "역할 배치"다.

### 6.1 유지해야 하는 자원

| 자원 | 현재 가치 | 향후 역할 |
| --- | --- | --- |
| built-in templates | 가장 현실감 있는 baseline artifact | quality baseline / runtime exemplar / promotion target |
| scaffold assets | deterministic materializer | stack skeleton |
| fragment registries | known-family lower bound | reusable vuln patch atoms의 출발점 |
| PoC templates | 실행 안정성 확보 | exploit harness/oracle library |
| fallback assets | degraded lane 보존 | fail-closed/degraded mode asset |
| vuln family catalog / rules | known-family accelerator | baseline knowledge + verifier/trust anchor |

### 6.2 바꿔야 하는 사용 방식

현재 자원은 "복사형 최종 산출물"에서 아래 역할로 재배치되어야 한다.

- stack skeleton
- runtime recipe exemplar
- vuln patch exemplar
- exploit oracle exemplar
- seed/fixture exemplar
- promoted memory

즉 방향은 아래다.

- `template copy` 확장: 지양
- `template-informed synthesis`: 지향
- `scaffold + patch/injection manifest + oracle` 조합: 핵심

### 6.3 점진적으로 줄여야 하는 것

- family마다 full filesystem template를 계속 추가하는 방식
- compiler/template lane 성공을 dynamic generation success로 해석하는 관행
- framework-biased fallback guard/PoC 자산 결합

### 6.4 이름만 제공되는 lane과 template dependence에 대한 현재 판단

이 관점에서 current workspace를 더 정확히 해석하면 아래와 같다.

- compiler-covered alias/name-only lane은 꽤 강하다.
  하지만 이것은 open-world dynamic success라기보다 curated catalog + scaffold lower bound success다.
- `trusted dynamic` lane은 존재하지만 아직 fixture-backed evidence가 중심이다.
  즉 provenance는 dynamic이지만 diversity/generalization upper bound를 증명하지는 않는다.
- unsupported unknown lane은 remote evidence가 있어도 current workspace에서는 RESEARCH relevance gate에서 멈출 수 있다.
  이는 이전의 low-trust fallback success보다 fail-closed 성격이 강하지만, 아직 "연구 기반 동적 생성 성공"을 의미하지는 않는다.
- 즉 template dependence 완화 관점에서는 "unsupported 요청을 억지로 known-family fallback으로 materialize"하던 경향은 줄었지만,
  그 자리를 researcher-first open-world success가 채운 것은 아니다.
- 이번 후속 수정으로 template viability는 더 엄격해졌고 `runtime.db` omission 때문에 compiler/template로 불필요하게 밀리던 현상도 줄었다.
  이것은 template dependence를 "낮춘 것"이라기보다 template path의 오탐 사용을 줄인 것이다.
- 가장 최근 rerun에서는 `Open Redirect`, `Path Traversal`, `Insecure Deserialization` dynamic_eval lane이 더 이상 asset-backed family template가 아니라
  `semantic_guided_minimal_dynamic` class로 기록된다.
  즉 아직 open-world positive는 아니지만, degraded lower-bound path 내부에서도 template/asset 의존이 실제로 줄기 시작했다.

따라서 template dependence 완화의 다음 단계는 아래다.

- full template copy 대신 skeleton + patch/oracle atom 비중을 늘린다
- unsupported family에서는 inherited `pattern_id`를 metadata trace 이상으로 쓰지 않도록 lane을 더 분리한다
- unsupported family의 opt-in pattern seed는 "research hint only"와 "generator seed"를 분리해 더 세밀하게 통제한다
- known family라도 Researcher shadow spec를 계속 축적해서 template/compiler 자산이 primary intelligence가 되지 않게 만든다
- promotion은 verifier independence와 oracle quality를 동시에 만족한 dynamic lane에만 허용한다

현재 상태 메모:

- 이번 follow-up으로 `memory_promotion` surface가 추가되었다.
- 다만 이것은 아직 "어떤 산출물을 future memory로 승격해도 되는가"를 분류하는 PACK-stage taxonomy일 뿐,
  실제 promoted memory write-back loop는 아니다.

## 7. 목표 아키텍처: 초기 설계를 존중한 open-world 전환안

목표 구조는 아래다.

`Researcher -> structured vuln/build/oracle spec -> LLM planner/generator -> deterministic materializer -> verifier/reviewer`

즉 핵심은 "LLM을 없애는 것"이 아니라 "LLM이 무엇을 생성하게 할지 재설계하는 것"이다.

### 7.1 Researcher의 목표 산출물

Researcher는 단순 report를 넘어서 아래를 만들도록 바뀌어야 한다.

#### `vuln_spec@2`

- vuln label normalization
- semantic signature
- missing defense
- positive/negative examples
- confidence + evidence provenance

#### `runtime_recipe@1`

- language/framework hypothesis
- service topology
- db/sidecar/env/port/health/network assumptions
- startup/init/seed requirements

#### `exploit_oracle@1`

- success marker
- flag rule
- positive payload set
- negative control
- metamorphic assertions

#### `guard_spec@next`

- generated code가 만족해야 할 semantic/structural assertions
- verifier/reviewer가 공통으로 사용할 contract

### 7.2 Generator의 목표 역할

Generator는 "최종 코드를 한 번에 쓰는 agent"에서 아래 역할로 이동해야 한다.

1. Researcher spec를 읽는다
2. stack skeleton을 고른다
3. vuln patch/injection manifest를 만든다
4. code block 단위로 materialize한다
5. guard/repair loop를 돌린다
6. contract/provenance를 기록한다

### 7.3 Compiler/template의 새로운 역할

compiler/template는 없어지는 것이 아니라 역할이 바뀐다.

- known-family lower bound
- deterministic materializer
- runtime-safe fallback
- promoted dynamic result의 저장 형식
- LLM이 생성한 spec를 실행 가능한 bundle로 변환하는 backend

## 8. 단계별 전환 로드맵

### Phase 0. Current truth hardening

목표:

- 지금 구조에서 correctness gap을 먼저 닫는다

핵심 작업:

- runtime capability schema 초안 통합
- external DB viability에서 sidecar type/name/env mismatch까지 체크
- template mode가 `runtime.db` 미지정 시에도 internal-db viable template를 찾도록 개선
- fallback guard/assertion을 scaffold-aware로 정렬

종료 조건:

- template/compiler/executor/verifier가 같은 runtime capability payload를 읽는다
- 현재 알려진 false-positive viability path가 닫힌다

### Phase 1. Researcher-first shadow mode

목표:

- known family에서도 Researcher를 항상 돌려 dynamic spec를 축적한다

핵심 작업:

- supported family라도 optional skip 대신 shadow run 허용
- `researcher_report`를 `vuln_spec/runtime_recipe/exploit_oracle` 중심으로 확장
- 기존 compiler-first 결과와 Researcher spec를 비교하는 diff artifact 생성

종료 조건:

- known-family official lane에서 Researcher output quality를 측정할 수 있다
- dynamic spec와 lower-bound compiler path의 불일치를 계량적으로 볼 수 있다

### Phase 2. Spec-driven synthesis

목표:

- LLM synthesis가 repo hardcoded semantics보다 Researcher spec를 더 강하게 따르도록 전환

핵심 작업:

- synthesis prompt에서 CWE-specific semantic hardcoding 축소
- Researcher-derived semantic/runtime/oracle contract를 primary block으로 승격
- one-shot manifest 대신 staged synthesis 도입

종료 조건:

- unknown family도 fallback manifest 대신 staged spec synthesis를 시도
- non-JSON failure가 곧바로 final degraded mode로 떨어지지 않는다

### Phase 3. Skeleton + Patch + Oracle model

목표:

- full template copy 중심에서 stack skeleton + vuln patch model로 전환

핵심 작업:

- scaffold를 skeleton layer로 분리
- fragment/template를 더 작은 patch/oracle atom으로 분해
- LLM은 patch manifest를 만들고 materializer가 deterministic하게 코드를 조립

종료 조건:

- new family on known stack 시나리오를 full template 없이 materialize 가능
- template 수 증가가 아니라 patch/oracle memory 증가로 커버리지가 넓어진다

### Phase 4. Oracle-based verification

목표:

- static rule이 없는 open-world lane에서도 verifier independence를 높인다

핵심 작업:

- `exploit_oracle` 기반 verifier 경로 추가
- positive payload + negative control + metamorphic checks 도입
- generator_manifest fallback verifier는 degraded trust lane으로만 유지

종료 조건:

- rule 없는 family에서도 "self-derived low trust only"에 머물지 않는 lane이 생긴다

### Phase 5. Promotion / Memory loop

목표:

- 성공한 dynamic 결과를 다시 자산화한다

핵심 작업:

- successful dynamic result -> runtime template / oracle / hint / recipe로 승격
- promoted asset의 provenance와 trust level 기록
- `runtime_templates`와 memory store를 분리 운영

종료 조건:

- open-world success가 다음 generation의 lower bound를 높인다
- template dependence는 "정적 수작업 템플릿"이 아니라 "축적된 promoted memory"로 대체된다

### Phase 6. Live trusted-dynamic acceptance

목표:

- fixture-only trusted dynamic에서 live provider acceptance로 확장

핵심 작업:

- remote provider available 환경에서만 optional live lane 실행
- fixture lane과 live lane을 명확히 분리
- retry/timeout/quota/auth failure taxonomy를 acceptance 표에 반영

종료 조건:

- live remote LLM 성공이 official but optional acceptance lane으로 편입된다

## 9. 우선순위 재정렬

이전 문서의 큰 방향은 맞지만, 실제 우선순위는 아래가 더 맞다.

### Priority 0. Runtime capability schema 통합 + 현재 correctness gap 정리

가장 먼저 해야 한다.

이유:

- open-world 상한의 핵심 병목은 "지원 family 수 부족"보다 "runtime contract가 계층마다 분절된 구조"다.
- 이 단계 없이 scaffold 확장이나 live trusted-dynamic을 먼저 늘리면 coverage만 넓고 신뢰도는 낮아진다.
- 여기에 semantic purity / metric correction도 같이 포함되어야 한다.
  unsupported unknown lane의 semantic contamination이 다시 생기지 않도록 하고,
  open-world 평가는 legacy `generalization_*`가 아니라 `open_world_*` surface를 기준으로 봐야 한다.
  현재는 여기서 한 단계 더 나아가 `strict_open_world_*`도 같이 봐야 한다.
  즉 lower-bound/template/fixture/stub/self-derived verifier를 별도 exclusion class로 분리한 strict taxonomy가
  baseline metric에 포함되어야 한다.

### Priority 1. Researcher-first dynamic lane 복원

그 다음이 핵심이다.

이유:

- 초기 설계를 살리려면 Researcher가 다시 primary path가 되어야 한다.
- known family에서도 shadow mode로 Researcher를 계속 돌려야 open-world 전환이 가능하다.

현재 상태 메모:

- `researcher.shadow_mode` 옵션은 이미 들어갔다.
- 다만 이것은 "supported lane에서도 researcher를 non-blocking으로 돌릴 수 있다"는 운영 훅일 뿐,
  Researcher output이 아직 generator primary contract가 된 것은 아니다.
- synthesis prompt에는 `runtime_recipe` / `generation posture` block이 추가되어,
  name-only lane에서 repo demo prior를 줄이는 작업이 시작됐다.
- 하지만 이것은 spec accumulation과 staged synthesis로 이어지지 않으면 prompt-level 완화에 그친다.

### Priority 2. Spec-driven staged synthesis

이유:

- one-shot final manifest는 open-world에서 너무 불안정하다.
- LLM은 더 작은 spec과 patch를 생성하게 해야 한다.

### Priority 3. Oracle-based verifier

이유:

- open-world lane의 성공 판정이 generator-coupled contract에만 머물면 의미가 약하다.
- current workspace는 `resolved_contract.exploit_oracle -> generator_manifest -> runtime rule` 순의
  preview fallback을 가지지만, 아직 negative control / metamorphic / live replay가 없어
  verifier independence를 충분히 올렸다고 볼 수는 없다.

### Priority 4. Asset promotion / quality uplift

이유:

- 성공한 dynamic 결과를 재사용 가능한 자산으로 바꾸지 않으면 open-world cost가 매번 초기화된다.
- 산출물의 인간친화성도 이 단계에서 같이 끌어올릴 수 있다.

### Priority 5. Live trusted-dynamic acceptance

이유:

- 필요하지만 마지막 단계다.
- capability/schema/spec/oracle 정렬 이전에 live acceptance를 넓히면 노이즈가 커진다.

## 10. 수용 기준과 측정 지표

계획은 아래 지표로 검증해야 한다.

### 10.1 안정성 지표

- 기존 `tests` / `tests/e2e` baseline 유지
- compiler-first known lane regression 불변
- fail-closed negative lane 불변

### 10.2 open-world 지표

- `unknown family on known stack` 성공률
- rule 없는 lane에서 verifier independence 상승 비율
- Researcher evidence가 실제 generation contract에 반영된 비율
- deterministic fallback으로 떨어지는 비율 감소
- 이름만 제공된 supported lane 중 full template copy 없이 compiler/skeleton으로 닫히는 비율
- unsupported lane에서 inherited `pattern_id` 또는 family-aware fallback에 의해 semantic drift가 발생하는 비율
- `open_world_summary.positive_open_world_bundles` 비율
- `open_world_summary.lower_bound_dependent_bundles` 비율
- `open_world_summary.template_dependent_bundles` 비율
- `strict_open_world_summary.positive_strict_open_world_bundles` 비율
- `strict_open_world_summary.fixture_backed_bundles` / `stub_backed_bundles`
- `strict_open_world_summary.verifier_coupled_bundles`
- `memory_promotion.eligible_bundles`
- `request_identity_summary.by_input_mode` / `by_match_class` / `synthetic_resolution_bundles`
- `artifact_quality_summary.average_score` / `by_band`
- `template_dependence_summary.name_only_lower_bound_bundles`

### 10.3 품질 지표

- artifact realism score
- README completeness
- runtime topology clarity
- exploit oracle clarity
- reviewer/pack human summary completeness

## 11. 최종 판단

현재 vulDocker는 이미 꽤 강한 regression platform이다.

- curated family에 대한 deterministic compiler-first lower bound
- fail-closed 정책
- provenance / semantic surface / verification trust / promotion gating

그러나 open-world 동적 생성기로 가기 위해서는 해석을 바꿔야 한다.

- compiler/template를 "최종 생성 방식"으로 두지 말고 lower-bound materializer로 재배치
- Researcher/RAG/LLM을 다시 primary path로 승격
- 현재 자산을 버리지 말고 skeleton/patch/oracle/memory로 분해/재활용

이 문서의 최종 결론은 아래다.

> vulDocker의 다음 단계는 "더 많은 hardcoded family를 추가하는 것"이 아니라,
> "Researcher -> RAG -> structured spec -> staged LLM synthesis -> deterministic materialization"으로 중심축을 되돌리는 것이다.
> 현재까지 구현한 template/scaffold/compiler/fallback 자산은 폐기 대상이 아니라,
> open-world 전환을 위한 실행기반 asset으로 재배치되어야 한다.

## 12. 이번 추가 구현 이후의 보정 메모

이번 문서 업데이트와 함께 current workspace에는 아래 추가 구현이 반영되었다.

- opt-in `policy.dynamic_eval=true`
  - RESEARCH skip 비활성화
  - synthesis mode의 compiler-first short-circuit 비활성화
  - name-only / lower-bound lane의 dynamic upper bound를 별도 평가할 수 있는 evaluation 훅
- opt-in `policy.dynamic_eval_allow_lower_bound_fallback=true`
  - dynamic_eval에서 synthesis가 막힐 경우 compiler/template lower bound로 다시 수렴 가능
- `plan.policy` carry-through correction
  - `dynamic_eval`, `dynamic_eval_allow_lower_bound_fallback`, `open_world_strict`,
    `allow_name_family_fallback`, `allow_unknown_pattern_seed`가 이제 top-level plan policy에도 반영된다
- synthesis prompt runtime hydration
  - 가능할 때 `resolved_contract.runtime_recipe`를 requirement payload에 다시 주입
- Researcher query seed 개선
  - request label / pattern / runtime anchor 우선
  - regression/E2E intent noise 제거
- lightweight retrieval planner
  - `query_plan` / `family_hypotheses` / `exploit_hypotheses` / query별 `evidence_type`
  - `evidence_type_summary`가 researcher report/history/search trace에 함께 기록
  - `family_hypothesis_summary`와 PACK `researcher_summary.by_top_family_hypothesis` / `contradiction_bundles` rollup 추가
  - contradiction-aware confidence calibration과 synthesis prompt `Researcher Family Hypothesis` block 추가
  - unknown lane에서는 stack-only remote hit가 threshold를 뚫지 못하도록 semantic alignment cap을 추가
- PACK metric correction
  - skip report는 `report_present=true`와 `ran=false`를 구분
  - thin README는 artifact quality에서 더 강하게 감점
- dynamic-eval manifest surface
  - `dynamic_eval` / `dynamic_eval_summary`가 추가되어
    `dynamic_failed`와 `lower_bound_recovered`를 bundle/manifest 수준에서 구분할 수 있다
  - `generation_summary`에도 `dynamic_eval_attempted_bundles`, `dynamic_eval_recovered_bundles`가 추가되었다
- SID separation for evaluation policy
  - `policy_eval_digest`가 SID input에 포함되어 `dynamic_eval` / `open_world_strict` 차이가 다른 SID로 분리된다

이 구현은 open-world capability를 "해결"한 것이 아니라,
아래 두 가지를 더 잘 관측하게 만든 것이다.

1. lower-bound shortcut을 우회했을 때 현재 synthesis lane이 실제로 어디까지 가는가
2. current artifact/report metric이 사람 기준 품질을 얼마나 과대평가하는가

### 12.1 새 평가용 example input

current workspace에는 아래 example input이 추가되었다.

- `inputs/name_only_dynamic_eval.yml`
- `inputs/name_only_dynamic_eval_with_fallback.yml`
- `inputs/name_only_mode_dynamic.yml`
- `inputs/name_only_mode_strict_dynamic.yml`

이 파일들은 name-only lane에서 dynamic evaluation과 lower-bound fallback comparison을 빠르게 재현하기 위한 샘플이다.

### 12.2 로드맵 보정

기존 roadmap은 방향은 맞지만 아래 세 항목을 명시적으로 추가해야 한다.

- `Phase 0.5 Dynamic Eval Lane`
  - lower-bound를 끈 상태에서 synthesis/research upper bound를 측정하는 opt-in runner
- `Phase 1.5 Retrieval Planner`
  - query plan / evidence typing / family hypothesis ranking
- `Phase 5.5 Memory Quarantine`
  - promoted memory 오염을 막는 replay/independent verify gate

### 12.3 현재 남은 핵심 한계

- dynamic_eval이 있어도 live trusted-dynamic success가 바로 늘어나는 것은 아니다.
  retrieval quality, staged IR, verifier independence가 아직 부족하다.
- `runtime_recipe`는 아직 authoritative control plane이 아니라 summary-grade contract에 가깝다.
- `generalization_*`는 아직 완전히 퇴역하지 않았다.
- default 운영은 여전히 regression/lower-bound 중심이며, dynamic_eval은 opt-in evaluation lane이다.
- dynamic_eval rerun은 하나의 중요한 현재 한계를 드러냈다.
  Researcher-generated guard spec가 `metadata.stack_scaffold_id`, `metadata.fragment_id`, `metadata.compose_mode`,
  `metadata.compiler_strategy` 같은 compiler-lower-bound metadata를 semantic anchor처럼 요구해
  name-only dynamic synthesis를 다시 curated lower-bound shape로 끌어당길 수 있다.
  즉 next step은 "skip을 없애는 것"뿐 아니라 "guard/oracle에서 lower-bound metadata prior를 분리하는 것"이다.
- compiler metadata contamination는 이번 follow-up으로 dynamic_eval fallback guard에서 제거되었다.
  current rerun에서 남는 failure reason은 주로 `semantic mismatch: missing redirect sink`처럼
  더 순수한 synthesis semantic gap으로 수렴한다.
- pure dynamic_eval과 lower-bound fallback recovery는 이제 같은 `compiler-first success`로 뭉개지지 않는다.
  current manifest에는 `dynamic_eval.status=dynamic_failed|lower_bound_recovered|degraded_success`가 남는다.
- semantic-guided fallback이 추가된 current rerun에서는 name-only `Open Redirect` dynamic_eval input이
  lower-bound compiler/template recovery 없이도 `dynamic_eval.status=degraded_success`로 끝날 수 있다.
  다만 manifest provenance는 `generation_origin=deterministic_fallback`, `fallback_class=semantic_guided`,
  `dynamicness_verdict=deterministic fallback dependent`로 남으므로 strict open-world positive로 해석하면 안 된다.
  또한 current workspace follow-up에서는 이 lane을 `open_world_summary`에서도
  `catalog_resolved_lower_bound`와 구분되는 `semantic_guided_degraded` 또는
  `semantic_guided_minimal_dynamic` class로 분리한다.
- retrieval planner는 이제 contradiction tracking도 일부 한다.
  다만 이것은 lightweight lexical ranking 수준이며, cross-query reranking과 stronger calibration 근거는 아직 없다.

### 12.4 이번 rerun으로 고정된 관측

2026-03-11 KST current rerun 기준:

- `python orchestrator/plan.py --input inputs/name_only_dynamic_eval.yml`
  -> `sid-fd8304a41d65`
- `python orchestrator/run_pipeline.py --sid sid-fd8304a41d65 --mode deterministic`
  - current workspace에서는 `dynamic_eval=true`인 name-driven lane도 이제 hard `language/framework` default를 바로 주입하지 않는다.
    즉 plan 단계부터 `stack_hypotheses=[python/flask, python/fastapi]`를 유지한다.
  - OpenAI quota로 LLM은 여전히 stub fallback되지만, generator는 `family_hypothesis_summary`를 실제로 읽는다.
    current rerun researcher report는 `top_family=open_redirect`, `top_confidence=high`, `top_margin=0.34`,
    `contradiction_count=1`, `ambiguous=false`를 남긴다.
  - follow-up 구현으로 semantic-guided fallback gate는 이제 mode-aware다.
    즉 `dynamic_eval`/`dynamic` posture에서는 top family가 high-confidence이고 margin이 충분히 크며 contradiction이 1건 이하일 때
    semantic-guided minimal dynamic recovery를 허용한다.
  - manifest 기준:
    - `dynamic_eval.status=degraded_success`
    - `lower_bound_fallback_used=false`
    - `generation_origin=deterministic_fallback`
    - `provenance.fallback_class=semantic_guided`
    - `provenance.materializer=minimal_dynamic`
    - `open_world_class=semantic_guided_minimal_dynamic`
    - `strict_open_world_class=strict_minimal_dynamic_fallback`
    - `intent_satisfaction.mode=dynamic_eval`
    - `intent_satisfaction.status=degraded_dynamic_success`
    - `intent_satisfaction.meets_intent=false`
    - `artifact_quality.band=medium`
    - `artifact_quality.score=8`
    - `artifact_quality.generation_authenticity=degraded_fallback`
    - `template_dependence_summary.minimal_dynamic_bundles=1`
    - `strict_open_world_summary.positive_strict_open_world_bundles=0`
    - `provider_health_state=llm_degraded`
    - `llm_stub_used=true`
    - `llm_failure_class=quota_exhausted`
    - `total_duration_s=13.849`
  - 또한 current workspace에는 now `intent_satisfaction` surface가 추가되어,
    name-only request가 compatibility/intended dynamic/strict intent를 실제로 얼마나 충족했는지 bundle/top-level manifest에서 바로 읽을 수 있다.
  - 즉 이전처럼 degraded bundle이 `high quality`로 과대평가되지 않고,
    "실행 가능한 degraded recovery"로 더 정직하게 surface된다.

- `python orchestrator/plan.py --input inputs/name_only_mode_dynamic.yml`
  -> current rerun `sid-b57485510ab9`
- `python orchestrator/run_pipeline.py --sid sid-b57485510ab9 --mode deterministic`
  - `name_only_mode=dynamic`도 동일하게 soft stack prior를 유지한 채 researcher-first로 진행된다.
  - current rerun researcher report는 `top_family=open_redirect`, `top_confidence=high`, `top_margin=0.46`,
    `contradiction_count=1`, `ambiguous=false`를 남긴다.
  - current rerun에서는 `dynamic_eval` example과 동일하게 semantic-guided minimal dynamic recovery로 닫힌다.
  - manifest 기준:
    - `pipeline_result=success`
    - `dynamic_eval.status=degraded_success`
    - `open_world_class=semantic_guided_minimal_dynamic`
    - `strict_open_world_class=strict_minimal_dynamic_fallback`
    - `intent_satisfaction.mode=dynamic`
    - `intent_satisfaction.status=degraded_dynamic_success`
    - `intent_satisfaction.meets_intent=false`
    - `artifact_quality.band=medium`
    - `artifact_quality.score=8`
    - `artifact_quality.generation_authenticity=degraded_fallback`

- `python orchestrator/plan.py --input inputs/name_only_mode_strict_dynamic.yml`
  -> current rerun `sid-8c6918dbcc12`
- `python orchestrator/run_pipeline.py --sid sid-8c6918dbcc12 --mode deterministic`
  - `strict_dynamic`는 같은 request label이라도 current rerun family summary가 `top_confidence=low`,
    `ambiguous=true`, `contradiction_count=3`로 calibration된다.
  - follow-up wiring fix 이후 generator는 이 summary를 실제로 읽기 때문에,
    semantic-guided family fallback이 더 이상 열리지 않는다.
  - 그 결과 fallback은 generic unsupported shape로 떨어지고, guard는 `missing redirect sink`로 이를 거절한다.
  - current rerun failure manifest 기준:
    - `pipeline_result=failure`
    - `terminal_failure_class=guard_semantic_mismatch`
    - `failure_stage=GENERATOR`
    - `failure_reason=guard semantic mismatch: missing redirect sink for open redirect scenario; semantic mismatch: missing redirect sink for open redirect scenario`
    - `dynamic_eval.status=dynamic_failed`
    - `open_world_class=name_driven_dynamic_failed`
    - `strict_open_world_class=strict_dynamic_generation_failed`
    - `provider_health_state=llm_degraded`
    - `llm_stub_used=true`
    - `llm_failure_class=quota_exhausted`
    - `intent_satisfaction.mode=strict_dynamic`
    - `intent_satisfaction.status=strict_dynamic_failed`
    - `intent_satisfaction.meets_intent=false`
    - `total_duration_s=16.795`
  - 중요한 점은 current strict lane이 더 이상 post-PACK strict gate에서만 실패하지 않는다는 것이다.
    현재는 generation 단계에서 실제 semantic mismatch failure로 더 이르게 fail-closed 된다.

- `python tests/e2e/run_case.py --case tests/e2e/cases/cwe-unknown-basic --mode deterministic --no-snapshot`
  - unsupported unknown case는 여전히 `research_short_circuit` / `pre-generation fail-closed`다.
  - current rerun researcher report는 `query_plan`, `evidence_type_summary`, `family_hypothesis_summary`를 남기지만,
    evidence relevance가 semantic/family/exploit alignment를 넘지 못하면 fail-closed를 유지한다.

이 관측이 의미하는 것은 명확하다.

- `dynamic_eval`/`dynamic` lane은 current workspace에서 "soft stack prior + researcher evidence + mode-aware semantic-guided degraded success"까지는 도달했다.
- 그러나 upper bound는 여전히 `trusted dynamic`가 아니라 `deterministic_fallback + minimal_dynamic`다.
- `strict_dynamic`는 이제 degraded recovery를 success처럼 끝내지 않고 generation 단계에서 더 일찍 fail-closed 된다.
- current researcher summary는 이제 실제 generator control plane에 더 가깝게 연결되었지만,
  strict positive를 열어 줄 정도로 staged IR/materializer/oracle independence가 확보된 것은 아니다.

### 12.5 name_only_mode / provenance honesty follow-up

이번 추가 follow-up에서 current workspace에는 아래 보완이 더 반영되었다.

- `dynamic_eval=true`인 name-driven lane도 이제 `name_only_mode=dynamic/strict_dynamic`와 같은 soft stack posture를 사용한다.
  즉 current workspace는 `dynamic_eval` example에서도 hard `language/framework` default를 바로 주입하지 않는다.
- generator가 synthesis로 넘기는 trimmed researcher payload는 이제 `family_hypothesis_summary`와 `evidence_relevance`를 보존한다.
  따라서 synthesis가 실제로 contradiction-aware family summary를 읽고 fallback posture를 조절할 수 있다.
- semantic-guided fallback gate는 이제 posture-sensitive다.
  - `strict_dynamic`: low confidence / ambiguity / contradiction을 그대로 block
  - `dynamic` / `dynamic_eval`: top family high-confidence + clear margin + contradiction <= 1 인 경우에만
    semantic-guided degraded recovery 허용
- PACK `artifact_quality`는 deterministic fallback bundle을 native dynamic/template artifact처럼 채점하지 않는다.
  current workspace는 `generation_authenticity=degraded_fallback`를 남기고 score/band를 상한 조정한다.
- top-level `manifest` / `failure_manifest`도 이제 가능한 경우 `failure_stage`, `failure_reason`, `failure_fix_hint`,
  `terminal_failure_class`, `retry_recommended`를 flatten해서 남긴다.
- `intent_satisfaction` / `intent_satisfaction_summary`도 추가되었다.
  현재는 name-only lane에 대해
  - `compatibility_lower_bound`
  - `degraded_dynamic_success`
  - `strict_dynamic_failed`
  같은 posture-aware status를 남긴다.
  추가 follow-up으로는 `closure_source`, `llm_path`, `research_quality`,
  `verification_independence`, `verification_trust`, `required_contract`도 함께 남긴다.
  따라서 current workspace는 이제 name-only intent miss가 "왜 miss였는가"를
  curated lower bound / template / deterministic fallback / fixture/stub / verifier coupling 관점에서 더 직접 읽을 수 있다.
- provider degradation handling도 한 단계 더 보완되었다.
  non-transient `quota_exhausted` / `auth_failure`가 한 stage에서 관측되면,
  같은 SID의 후속 subprocess는 `VUL_FORCE_LLM_STUB`를 받아 remote provider를 다시 치지 않는다.
  따라서 current rerun strict lane에서도 researcher 1회차만 real provider를 치고,
  이후 generator/researcher retry는 즉시 stub path로 들어간다.

이 보완이 의미하는 것은 아래다.

- name-only intent는 current workspace에서 더 이상 "dynamic_eval면 무조건 optimistic degraded success"가 아니다.
- `dynamic`와 `strict_dynamic`는 같은 name-driven lane이라도 실제로 다른 fallback policy를 가진다.
- current workspace는 now:
  - `dynamic_eval` / `dynamic`: limited degraded recovery 허용
  - `strict_dynamic`: contradiction-aware fail-closed
  로 읽는 편이 더 정확하다.
- 동시에 degraded bundle quality도 예전보다 덜 낙관적으로 보인다.
  current rerun minimal dynamic bundle은 `band=medium`, `score=8`로 기록되고,
  `deterministic fallback bundle` note도 함께 남는다.

### 12.6 이번 follow-up 이후에도 남는 현재 gap

- top-level `intent_satisfaction` surface는 now 추가되었지만,
  current workspace follow-up에서는 `closure_source`, `llm_path`, `research_quality`,
  `verification_*`, `required_contract`까지 surface되지만,
  여전히 novelty/cheatiness/pedagogical quality를 직접 재는 수준까지는 아니다.
  future work로는 `semantic_novelty`, `stack_novelty`, `topology_novelty`, `oracle_novelty`를 분리한
  richer intent satisfaction model이 필요하다.
- dynamic lane의 stack choice는 soft prior가 되었지만, current rerun top stack은 여전히 Flask다.
  즉 stack uncertainty를 더 정직하게 surface하기 시작했을 뿐, stack diversity upper bound가 올라간 것은 아니다.
- current positive는 여전히 semantic-guided minimal dynamic degraded success다.
  `strict_open_world_positive`는 current rerun에서 여전히 0이다.
- provider degradation 비용도 여전히 남지만, now 한 단계 줄었다.
  current rerun dynamic lane은 약 13.8초, strict lane은 약 16.8초로 내려왔다.
  이는 non-transient provider failure가 같은 SID의 후속 subprocess에서 즉시 stub path로 전환되기 때문이다.
  다만 first-stage probe 비용은 여전히 남으므로, next step은 "첫 실패 이후 다음 stage부터"가 아니라
  planner-level provider health cache / warm fail-fast로 더 앞당기는 것이다.

### 12.7 2026-03-12 추가 구현 반영

이번 추가 구현으로 current workspace에는 아래 보완이 더 들어갔다.

- normalized `name_only_contract` surface
  - `requirement.policy.name_only_contract`와 `plan.policy.name_only_contract`가 추가되었다.
  - 현재는 `enabled`, `effective_mode`, `require_research`, `require_remote_research`,
    `allow_degraded_fallback`, `allow_lower_bound_recovery`, `allow_curated_lower_bound_closure`,
    `require_strict_open_world`, `require_independent_verifier`, `require_live_llm`,
    `allow_stub_llm`, `allow_fixture_llm` 정도를 단일 payload로 본다.
  - 이것은 full staged control plane은 아니지만, name-only lane의 intent bar를
    scattered bool flag보다 더 직접적으로 표면화한다.
- strict_dynamic generator posture gate
  - current workspace는 now `strict_dynamic` lane에서 generator 산출이 이미
    `generation_origin != llm_manifest`, `deterministic_fallback`, `llm_stub_used`,
    `llm_fixture_used`, `dynamic_eval.status=degraded_success|lower_bound_recovered`
    같은 disallowed posture를 보이면 EXECUTOR 전에 pipeline을 중단한다.
  - 즉 strict lane은 이제 "PACK에서 taxonomy상 탈락"만이 아니라,
    "generation이 strict intent를 만족할 수 없는 것으로 확인되면 더 이른 단계에서 fail-closed" 되는 성격이 더 강해졌다.
- richer name-only intent surface
  - `intent_satisfaction`는 now `status` 외에도
    `closure_source`, `generation_origin`, `fallback_class`, `llm_path`,
    `research_quality`, `verification_independence`, `verification_trust`,
    `required_contract`를 함께 남긴다.
  - `intent_satisfaction_summary`도 `by_status` 외에
    `by_closure_source`, `by_llm_path`, `by_research_quality` rollup을 가진다.
  - 따라서 current workspace는 now name-only lane을
    "compatibility lower bound인지 / degraded deterministic fallback인지 /
    live dynamic인지 / fixture/stub-backed인지"를 별도 taxonomy 없이도 더 직접 읽을 수 있다.
- structured preview surfaces
  - current workspace follow-up에서는 `resolved_contract` / `manifest`에
    summary-grade `exploit_oracle`과 `name_only_generation_spec`도 추가되었다.
  - `exploit_oracle`는 success signature / flag token / success mode / assertion_program /
    base_url / poc_cmd 정도를 한 payload로 surface한다.
  - `name_only_generation_spec`는 request label / request_identity / name_resolution /
    required_contract / working family hypothesis / runtime recipe summary / stack hypotheses /
    exploit oracle summary를 함께 surface한다.
  - 이것은 아직 full staged IR나 authoritative planner output은 아니지만,
    current workspace가 이제 name-only lane에 대해 "request -> working family -> runtime -> oracle"을
    단일 contract surface로 남기기 시작했다는 의미다.
- oracle-aware verifier fallback preview
  - current workspace는 now static/runtime rule이 없을 때
    `resolved_contract.exploit_oracle` 또는 legacy top-level resolved contract fields를 먼저 읽고,
    그 다음에야 `generator_manifest` fallback으로 내려간다.
  - 새 verifier source는 `contract_oracle_fallback`으로 기록되고,
    independence도 기존 `self_derived` 대신 `contract_coupled`로 분리된다.
  - 다만 trust는 아직 `low`로 유지한다.
    즉 이것은 generator self-certification을 조금 더 정직하게 분리한 것이지,
    independent verifier를 달성한 것은 아니다.

이 구현이 의미하는 것은 아래다.

- current workspace는 name-only intent 평가에서
  "성공/실패"만 보지 않고 `intent contract`와 `actual closure path` 사이의 차이를 더 정직하게 남긴다.
- strict lane은 now `post-pack strict rejection`만이 아니라
  `pre-executor strict generator rejection`도 가진다.
- dynamic lane에서도 current workspace는 now
  degraded/local-only researcher가 low-confidence wrong-family hypothesis를 내더라도,
  request identity가 `catalog_alias`/`exact_identifier` 고신뢰이고 guard semantic signature가 같은 family를 지지하면
  그 family를 degraded working hypothesis로 재사용해 `semantic_guided minimal_dynamic` recovery를 열 수 있다.
  이는 open-world upper bound 상승이 아니라, degraded dynamic lane이 noisy local evidence에 의해
  불필요하게 `generic_unsupported_family`로 붕괴되는 현상을 줄이는 보정이다.
- 다만 이것이 open-world upper bound를 올린 것은 아니다.
  현재 positive dynamic upper bound는 여전히 degraded deterministic fallback 중심이며,
  `strict_open_world_positive`를 늘리려면 staged IR / live provider / independent oracle verifier가 여전히 필요하다.
- verifier 측면에서도 current workspace는
  `generator_manifest_fallback`만 남기던 상태보다는 나아졌지만,
  아직 `contract_oracle_fallback(low, contract_coupled)`에 머문다.
  즉 name-only dynamic의 acceptance quality는 조금 좋아졌지만,
  strict acceptance quality가 올라간 것은 아니다.
- template dependence 완화 측면에서도 이번 follow-up은
  verifier/contract 정렬 + `minimal_dynamic` family coverage 확대 + guard-failing JSON candidate 뒤
  semantic-guided recovery candidate 재시도까지 들어간 수준이다.
  다만 실제 생성 upper bound는 여전히 staged synthesis 부재와 limited family coverage에 의해 제한된다.

### 12.8 2026-03-12 local rerun 메모

이번 추가 구현 뒤 current machine에서 다시 수행한 lightweight rerun은 아래처럼 관측되었다.

- `python -m pytest -q tests`
  - `458 passed, 39 skipped, 1 warning`
- `python -m pytest -q tests/test_synthesis_semantic_guard.py tests/test_pack_promotion.py tests/test_rule_based_semantic_contract.py tests/test_contract_resolution.py`
  - `137 passed, 1 warning`
  - `exploit_oracle` 기반 verifier fallback과 `contract_oracle_fallback` / `contract_coupled`
    taxonomy, 그리고 `Path Traversal` / `SSRF` / `Insecure Deserialization` minimal dynamic materializer를 직접 검증했다.
- `python orchestrator/plan.py --input inputs/name_only_mode_strict_dynamic.yml`
  - `sid-8c6918dbcc12`
- `python orchestrator/run_pipeline.py --sid sid-8c6918dbcc12 --mode deterministic`
  - current machine에서는 remote search provider DNS가 풀리지 않아
    Researcher가 `remote_required` strict contract를 만족하지 못하고 RESEARCH 단계에서 fail-closed 된다.
  - failure manifest 기준:
    - `pipeline_result=failure`
    - `failure_stage=RESEARCH`
    - `terminal_failure_class=remote_evidence_missing`
    - `intent_satisfaction.mode=strict_dynamic`
    - `intent_satisfaction.status=strict_dynamic_not_satisfied`
    - `intent_satisfaction.required_contract.require_remote_research=true`
    - `intent_satisfaction.required_contract.require_live_llm=true`
    - `intent_satisfaction.llm_path=not_used`
    - `intent_satisfaction.research_quality=insufficient`
  - 즉 current strict lane은 provider/search health가 없을 때
    compiler lower bound로 내려가기보다 더 빠르게 fail-closed 되는 쪽으로 해석하는 편이 맞다.

- `python orchestrator/plan.py --input inputs/name_only_mode_dynamic.yml`
  - `sid-b57485510ab9`
- `python orchestrator/run_pipeline.py --sid sid-b57485510ab9 --mode deterministic`
  - current machine에서는 Researcher가 local/degraded evidence로는 계속 진행된다.
  - 추가 follow-up으로 degraded/local-only researcher가 `sqli(low)` 같은 noisy top-family를 내더라도,
    request identity가 `Open Redirect -> catalog_alias/high`이고 guard semantic signature가 open redirect를 지지하면
    generator는 alias-guided degraded working hypothesis를 사용해 `semantic_guided minimal_dynamic` recovery를 다시 열 수 있다.
  - 따라서 current machine rerun에서는 dynamic lane이 더 이상 GENERATOR 단계에서 무너지지 않고,
    degraded dynamic bundle 생성까지는 성공한 뒤 Docker build failure에서 멈춘다.
  - current rerun `resolved_contract` / `failure_manifest`에는 now:
    - `exploit_oracle.success_signature=Exploit SUCCESS`
    - `exploit_oracle.flag_token=FLAG{OPEN_REDIRECT_OK}`
    - `exploit_oracle.source=researcher_verification_spec`
    - `name_only_generation_spec.request_label=Open Redirect`
    - `name_only_generation_spec.required_contract.effective_mode=dynamic`
    - `name_only_generation_spec.family_working_hypothesis=open_redirect`
    - `name_only_generation_spec.family_hypothesis_source=request_identity_fallback`
    - `name_only_generation_spec.researcher_family_hypothesis=sqli`
    - `name_only_generation_spec.runtime_recipe_summary.framework=flask`
    - `name_only_generation_spec.exploit_oracle_summary.success_signature=Exploit SUCCESS`
    가 함께 기록된다.
  - failure manifest 기준:
    - `pipeline_result=failure`
    - `failure_stage=EXECUTOR`
    - `intent_satisfaction.mode=dynamic`
    - `intent_satisfaction.status=degraded_dynamic_success`
    - `intent_satisfaction.partial=true`
    - `intent_satisfaction.closure_source=degraded_deterministic_fallback`
    - `intent_satisfaction.generation_origin=deterministic_fallback`
    - `intent_satisfaction.fallback_class=semantic_guided`
    - `intent_satisfaction.llm_path=stub`
    - `intent_satisfaction.research_quality=sufficient`
    - `intent_satisfaction.required_contract.require_research=true`
    - `intent_satisfaction.required_contract.allow_degraded_fallback=true`
    - `intent_satisfaction.required_contract.allow_lower_bound_recovery=false`
    - `generator_manifest.manifest.metadata.materializer=minimal_dynamic`
    - `generator_manifest.manifest.metadata.semantic_guided_family=open_redirect`
    - `intent_satisfaction_summary.by_llm_path.stub=1`
    - `performance.provider_health_state=search_and_llm_degraded`
  - current rerun researcher report는 degraded local evidence only 상황에서
    여전히 `family_hypothesis_summary.top_family=sqli`, `top_confidence=low`까지 drift할 수 있다.
    다만 current workspace는 now `name_only_generation_spec`에
    `researcher_family_hypothesis=sqli`와 별도로
    `family_working_hypothesis=open_redirect`, `family_hypothesis_source=request_identity_fallback`
    를 함께 남긴다.
    즉 current 보완은 이 drift를 제거한 것이 아니라,
    degraded local evidence에서의 noisy top-family와 실제 degraded working hypothesis를
    분리해서 기록하고, alias/high-confidence request identity + matching semantic signature가 있을 때만
    generic collapse를 피하도록 완화한 것이다.
  - 이번 verifier follow-up은 current machine rerun path에서는 직접 관측되지 않았다.
    dynamic lane이 current machine에서 Docker build 이전에 VERIFY 단계까지 도달하지 못하기 때문이다.
    따라서 oracle-aware verifier change의 실행 확인은 위 targeted unit/integration tests로 보완했다.

- `python orchestrator/plan.py --input inputs/name_only_mode_dynamic_path_traversal.yml`
  - `sid-0a27cf8c8625`
- `python orchestrator/run_pipeline.py --sid sid-0a27cf8c8625 --mode deterministic`
  - current machine에서는 Researcher가 remote evidence 없이 degraded local/stub path로 진행되지만,
    generator는 now `Path Traversal -> semantic_guided -> minimal_dynamic`까지 닫힌다.
  - current rerun `generator_manifest` / `failure_manifest`에는 now:
    - `generator_manifest.manifest.metadata.fallback_class=semantic_guided`
    - `generator_manifest.manifest.metadata.materializer=minimal_dynamic`
    - `generator_manifest.manifest.metadata.semantic_guided_family=path_traversal`
    - `artifact_quality.oracle_clarity=high`
    - `intent_satisfaction_status=degraded_dynamic_success`
  - 즉 current workspace는 now degraded name-only dynamic lane에서
    `Path Traversal`도 repo family template copy가 아니라 inline scaffold + inline PoC bundle로 닫을 수 있다.
  - 다만 current machine에서는 이것 역시 Docker WSL integration 부재 때문에 EXECUTOR build에서 멈춘다.
    따라서 `semantic_guided_minimal_dynamic` upper bound가 실제 컨테이너 success로 이어지는지는
    아직 fresh Docker E2E로 검증하지 못했다.

- `python orchestrator/plan.py --input inputs/name_only_mode_dynamic_deserialization.yml`
  - `sid-669b2a95c6e0`
- `python orchestrator/run_pipeline.py --sid sid-669b2a95c6e0 --mode deterministic`
  - current machine에서는 `Insecure Deserialization`도 remote evidence 없이 degraded local/stub path로 진행된다.
  - 이전 follow-up 전에는 low-quality JSON candidate가 먼저 guard mismatch로 막히면서
    GENERATOR 단계에서 반복 실패할 수 있었다.
  - current workspace는 now 이런 경우 `semantic_guided recovery candidate`를 마지막으로 한 번 더 시도하고,
    current rerun에서는 그 recovery candidate가 실제로 채택되어 generator가 계속 진행된다.
  - current rerun `generator_manifest` / `failure_manifest`에는 now:
    - `generator_manifest.manifest.metadata.fallback_class=semantic_guided`
    - `generator_manifest.manifest.metadata.materializer=minimal_dynamic`
    - `generator_manifest.manifest.metadata.semantic_guided_family=deserialization`
    - `artifact_quality.oracle_clarity=high`
    - `intent_satisfaction_status=degraded_dynamic_success`
  - 즉 current workspace는 now degraded name-only dynamic lane에서
    `Insecure Deserialization`도 repo family template copy가 아니라 inline scaffold + inline PoC bundle로 닫을 수 있다.
  - 다만 이것 역시 current machine에서는 Docker WSL integration 부재 때문에 EXECUTOR build에서 멈춘다.

이 local rerun이 의미하는 것은 아래다.

- 현재 name-only lane은 stored rerun artifact에서 보이던 degraded success보다
  machine/provider 상태에 더 민감하다.
- strict lane은 now contract mismatch를 더 정직하게 RESEARCH 단계에서 드러내며,
  dynamic lane은 RESEARCH가 sufficient여도 generator semantic mismatch로 쉽게 무너질 수 있다.
- 새 `intent_satisfaction` / `name_only_contract` surface는
  이런 실패가 "research contract miss인지 / generator semantic miss인지 / degraded provider path인지"를
  이전보다 더 직접적으로 읽게 해 주지만,
  그 자체가 robustness를 보장해 주지는 않는다.
- template dependence 완화는 now `Open Redirect` 중심 single proof가 아니라
  `Path Traversal`, `Insecure Deserialization`까지 확대된 degraded evidence를 갖는다.
  다만 coverage가 늘어난 것과 open-world trusted dynamic upper bound가 올라간 것은 별개다.
