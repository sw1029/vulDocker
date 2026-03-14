# 동적 취약 Docker 생성 Current State / Gap Analysis

Status: canonical
Audience: mixed
Source of truth for: current rerun-backed truth, current completeness assessment, current structural gaps
Not the source of truth for: implementation priority, next slice, roadmap
Last validated against: `python -m pytest -q tests`, targeted regression slices, and representative E2E reruns on 2026-03-14

본 문서는 2026-03-14 KST 기준 workspace 재검토, 최신 코드 보완, representative rerun,
그리고 `name-only` 관점의 최신 control-plane truth를 하나로 병합한 **현상 진단 문서**다.

관련 문서:
- 문제 정의와 success criteria: [docs/problem.md](problem.md)
- 현재 제약과 금지 claim: [docs/constraints.md](constraints.md)
- 구현 우선순위와 계획: [docs/final_solution.md](final_solution.md)
- 운영 절차: [docs/handbook.md](handbook.md)

이번 갱신의 핵심은 아래 항목들이다.

- 현재 코드와 실제 rerun 기준으로 강하게 말할 수 있는 truth만 남김
- `promotion`과 generalized/open-world support claim을 계속 분리
- `stack_defaulted` / `support_promotion` / `open_world_readiness` surface를 current truth 기준으로 재정리
- `request_ir.family_candidates` / `negative_hypotheses`의 current 의미를 최신화
- stack 선택에서 repo prior를 자동 우선하던 bias를 일부 완화
- `stack_anchor_query`를 evidence가 아니라 low-weight hint로 강등
- evidence graph가 query seed만으로 support edge를 부여하던 coupling을 일부 제거
- representative dynamic lane에서 `stack_defaulted`가 실제로 제거된 truth를 반영
- `request_ir.selection_decision`과 minimal `executor_plan`을 contract/summary/prompt에 연결
- `selection_readiness_summary`와 resolved/unresolved ambiguity 집계를 추가
- selected family/stack의 support count / authority 분포를 contract/summary/prompt에 연결
- `ready_for_materialization`와 `open_world_evidence_ready`를 분리
- 오래된 수치/평가/계획을 하나로 병합하고 obsolete wording을 정리

## 1. Truth Protocol

- primary truth는 현재 workspace 코드와 이번 세션에서 직접 실행한 결과다.
- repo-tracked historical snapshot은 참고 자료일 뿐 current rerun보다 우선하지 않는다.
- `pipeline_result` 단독 해석은 금지한다.
- 현재 primary acceptance surface는 아래다.
  - `name_only_outcome`
  - `completion_state`
  - `intent_satisfaction`
  - `open_world_*`
  - `strict_open_world_*`
- `promotion`은 regression/pack surface다.
- generalized/open-world support claim은 `support_promotion`과 `open_world_readiness`를 같이 본다.
- `generalization_*`는 legacy/comparison surface로만 본다.
- pre-generation fail-closed / abstain lane은 실행기 성공이 아니라 capability/research contract 관점에서 읽는다.

## 2. Current Verified Baseline

### 2.1 2026-03-14 실제 실행 결과

| command | result | interpretation |
| --- | --- | --- |
| `python -m pytest -q tests` | `586 passed, 53 skipped, 1 warning in 2.88s` | current unit/integration baseline 정상 |
| `python -m pytest -q tests/test_pack_promotion.py tests/test_run_case_summary_surface.py tests/test_contract_resolution.py tests/test_executor_poc_exec.py tests/test_generator_template_planner.py tests/test_researcher_search_artifacts.py tests/test_synthesis_prompt_contract.py` | `205 passed, 1 warning in 2.20s` | selection/contract/researcher/generator/executor summary surface 회귀 없음 |
| `python tests/e2e/run_case.py --case tests/e2e/cases/open-redirect-dynamic-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld_after_open_redirect_dynamic` | expectations satisfied | representative dynamic name-only rerun 정상 |
| `python tests/e2e/run_case.py --case tests/e2e/cases/open-redirect-strict-dynamic-no-remote --mode deterministic --no-snapshot --output-dir /tmp/vuld_after_open_redirect_strict` | expectations satisfied | strict fail-closed representative rerun 정상 |
| `python tests/e2e/run_case.py --case tests/e2e/cases/sqli-name-only --expectations tests/e2e/cases/sqli-name-only/expectations.no-remote.json --mode deterministic --no-snapshot --output-dir /tmp/vuld_after_sqli_name_only` | expectations satisfied | lower-bound regression representative rerun 정상 |
| `python tests/e2e/run_case.py --case tests/e2e/cases/foobar-name-only-negative --mode deterministic --no-snapshot --output-dir /tmp/vuld_after_foobar_negative` | expectations satisfied | unsupported free-form negative representative rerun 정상 |

주의:

- full official E2E baseline(`51 passed, 2 skipped`)은 same-day reference baseline으로 유지하되,
  이번 최신 slice 후에는 representative rerun 위주로 truth를 다시 확인했다.
- 아래 generalized/open-world 평가는 baseline 통과와 별개로 representative truth와 current code structure를 함께 본 정성 평가다.

### 2.2 Representative rerun truth

- `sqli-name-only`
  - `generation_origin = compiler_generated`
  - `name_only_outcome.decision = intent_met`
  - `name_only_primary_focus = generation_execution`
  - `open_world_class = catalog_resolved_lower_bound`
  - `promotion_eligible = true`
  - `support_promotion_eligible = false`
  - `request_ir.selection_decision.ready_for_materialization = true`
  - `request_ir.selection_decision.open_world_evidence_ready = false`
  - `selection_readiness_summary.open_world_evidence_ready_bundles = 0`
  - 즉 fully validated lower-bound regression success이지만 generalized/open-world support claim은 아니고, selected contract가 곧 evidence-backed dynamic readiness를 뜻하지도 않는다

- `open-redirect-dynamic-name-only`
  - `generation_origin = deterministic_fallback`
  - `open_world_class = semantic_guided_minimal_dynamic`
  - `strict_open_world_class = strict_minimal_dynamic_fallback`
  - `name_only_outcome.decision = partial`
  - `name_only_next_required_step = open_world_generation`
  - `name_only_primary_focus = open_world_generation`
  - `request_ir.family_candidates = [open_redirect]`
  - `request_ir.stack_candidates = [python/flask(researcher_candidate, selected), python/fastapi(available_skeleton)]`
  - `request_ir.selection_decision = {family:selected(open_redirect, support_count=10, authority={medium:8, low:2}), stack:selected(python/flask, support_count=3, authority={medium:2, low:1}), ready_for_materialization:true, open_world_evidence_ready:true}`
  - `semantic_guided_selection_source = request_ir_selection`
  - `open_world_selection_source = request_ir_selection`
  - `open_world_selection_evidence_ready = true`
  - `request_ir_summary = {selection_ready_bundles: 1, selected_family_bundles: 1, selected_stack_bundles: 1, ambiguous_stack_candidate_bundles: 1, resolved_ambiguous_stack_candidate_bundles: 1}`
  - `selection_readiness_summary = {ready_for_materialization_bundles: 1, open_world_evidence_ready_bundles: 1, family_selected_bundles: 1, stack_selected_bundles: 1, family_evidence_backed_bundles: 1, stack_evidence_backed_bundles: 1, resolved_ambiguous_stack_bundles: 1, by_stack_source:{researcher_candidate:1}, by_stack_basis:{researcher_top_candidate:1}}`
  - `runtime_recipe.stack_source = researcher_candidate`
  - `runtime_recipe.stack_defaulted = false`
  - `runtime_recipe.stack_selection = {selected_stack_id: python/flask, confidence: high, margin: 0.85, basis: researcher_top_candidate}`
  - `executor_plan = {service_port: 8000, health_path: /health, topology: single_service}`
  - `stack_dependence.class = researcher_inferred`
  - `name_only_outcome.selection_ready_for_materialization = true`
  - `name_only_outcome.selection_open_world_evidence_ready = true`
  - `promotion_eligible = true`
  - `support_promotion_eligible = false`
  - `support_promotion.reasons`에 아래가 직접 남는다
    - `strict_open_world:strict_minimal_dynamic_fallback`
    - `open_world:semantic_guided_minimal_dynamic`
    - `artifact_quality:medium`
    - `name_only_outcome:partial`
  - `open_world_readiness.blockers = [strict_open_world_gate, open_world_non_positive, artifact_quality_below_high, name_only_intent_not_met]`
  - `artifact_quality.notes`에서 `stack selection remained repo-prior/defaulted`가 제거된다
  - sample performance:
    - `RESEARCH ≈ 7.22s`
    - `GENERATOR ≈ 1.40s`
    - `EXECUTOR_BUILD ≈ 0.80s`
    - `EXECUTOR_RUN ≈ 1.56s`
    - `VERIFY ≈ 1.30s`
    - `REVIEW ≈ 1.31s`
    - `TOTAL ≈ 13.72s`

- `open-redirect-strict-dynamic-no-remote`
  - `generation_origin = capability_gate_rejected`
  - `name_only_outcome.decision = fail_closed`
  - `selection_readiness_summary = {family_selected_bundles: 1, stack_selected_bundles: 0, ready_for_materialization_bundles: 0, open_world_evidence_ready_bundles: 0, unresolved_ambiguous_stack_bundles: 1}`
  - `request_ir.selection_decision.family.selected = true` 이더라도 `family_support_count = 0`, `open_world_evidence_ready = false`
  - `runtime_recipe_hypothetical = true`
  - `name_only_primary_focus = stack_or_runtime_design`
  - `support_promotion_eligible = false`
  - `stack_dependence.stack_defaulted = true`

- `foobar-name-only-negative`
  - `generation_origin = research_short_circuit`
  - `name_only_outcome.decision = abstain`
  - `open_world_class = unsupported_free_form_negative`
  - `name_only_primary_focus = family_disambiguation`
  - `support_promotion_eligible = false`

- broad free-form phrase sanity check: `Cross Site Injection`
  - `resolved_vuln_id = NAME-CROSS-SITE-INJECTION`
  - `resolution_state = synthetic_name`
  - `request_ir.family_candidates = [xss, csrf]`
  - `query_plan.family_hypotheses = [xss, csrf]`
  - 즉 canonical id가 없더라도 plan 단계에서 다중 family candidate를 보존하는 쪽으로 조금 더 이동했다

- canonicalized name-driven sanity check: `Reflected XSS`
  - `vuln_id = CWE-79`, `request_ir.name_driven = true`
  - `query_plan.family_hypotheses = [xss(catalog_resolution)]`
  - raw `CWE-79 weakness details ...` / `CWE-79 exploit analysis ...` query seed는 빠진다
  - `query_plan.negative_family_hypotheses = [template_injection(researcher_contradiction)]`
  - query plan에 `contradiction_check` evidence type이 추가되어 negative branch가 retrieval surface까지 유지된다

### 2.3 현재 세션에서 강하게 말할 수 있는 것

- regression/unit surface는 안정적이다.
- fail-closed / abstain / partial / intent_met 구분은 representative rerun에서 다시 확인됐다.
- `promotion_eligible`와 generalized/open-world support claim을 더 이상 같은 의미로 읽으면 안 된다.
- degraded dynamic lane이 runnable regression surface라는 사실과 support-ready bundle이 아니라는 사실을 이제 더 분리해 읽을 수 있다.
- latest slice에서 stack 선택은 더 이상 항상 repo prior로 닫히지 않는다.
- latest slice에서 `stack_anchor_query`는 low-weight hint로만 남고, text-backed evidence가 있는 top candidate가 있을 때만 researcher stack이 selection에 실제 영향을 준다.
- latest slice에서 evidence graph는 query family/stack seed만으로 support edge를 만들지 않는다.
- representative `open-redirect-dynamic-name-only`는 현재 `stack_defaulted = false`, `stack_source = researcher_candidate`로 rerun truth가 바뀌었다.
- representative `open-redirect-dynamic-name-only`는 현재 `request_ir.stack_candidates`까지 selected researcher stack truth를 다시 싣는다.
- representative `open-redirect-dynamic-name-only`는 현재 `request_ir.selection_decision`과 `runtime_recipe.stack_selection`을 통해 selected family/stack truth를 contract-level에서 직접 surface한다.
- representative `open-redirect-dynamic-name-only`는 현재 `request_ir_summary`와 `selection_readiness_summary`를 통해 "candidate pool은 2개지만 selection은 resolved"라는 상태를 aggregate surface에서도 다시 읽을 수 있다.
- latest slice에서는 selected family/stack마다 `support_count` / `support_by_source_authority`가 같이 남아, "선택됨"과 "근거가 있는 선택"을 분리해서 읽을 수 있다.
- latest slice에서는 `ready_for_materialization`와 `open_world_evidence_ready`가 분리된다.
- latest slice에서는 generator preflight contract injection이 들어가서 semantic-guided fallback도 `request_ir_selection`을 직접 읽기 시작했다.
- latest slice에서는 open-world verdict도 `open_world_selection_source` / `open_world_selection_evidence_ready`를 직접 surface한다.
- 하지만 same lane은 여전히 `partial`이고 generalized/open-world positive는 아니다.
- `boundedness_summary`와 `open_world_readiness_summary`는 여전히 repo-wide boundedness inventory를 정직하게 보여 준다.
- `name_only_generation_spec.planning_focus_summary`는 prompt/summary surface로는 유용하다.

### 2.4 아직 강하게 말하면 안 되는 것

- arbitrary 취약점 이름만으로 generalized open-world positive를 안정적으로 만든다.
- unknown family / unknown stack / multi-service topology를 실제 control plane으로 materialize한다.
- `promotion_eligible = true`가 generalized support readiness를 뜻한다.
- `artifact_quality = medium`가 사람 기준 좋은 실습/lab artifact를 뜻한다.
- current dynamic lane의 `fully_validated`가 곧 intent-faithful open-world success를 뜻한다.
- current `request_ir`가 이미 generator/executor의 authoritative control plane이라고 말한다.

## 3. 이번 Iteration까지 실제 적용된 보완

### 3.1 누적 truth-surface hardening

이미 반영되어 current truth에 계속 남는 변화:

- `support_promotion` surface 분리
- `stack_defaulted` / `stack_dependence_summary` 추가
- `boundedness_summary` / `open_world_readiness_summary` 추가
- `planning_focus_summary` 추가
- `material_candidate_count` / `material_ambiguous` 도입
- `request_ir.family_candidates` enrichment
- `request_ir.negative_hypotheses`의 query/evidence graph 연결
- minimal dynamic open redirect fallback의 oracle realism 보강

의미:

- degraded dynamic/lower-bound lane을 success-like support claim으로 읽는 문제를 줄였다.
- current system의 boundedness를 top-level summary에서 더 정직하게 읽게 됐다.

### 3.2 이번 최신 slice: stack selection de-bias

적용:

- `agents/researcher/service.py::_infer_tech_stack_candidates(...)`
- `common/contracts.py::_researcher_stack_candidates(...)`
- `common/contracts.py::_preferred_researcher_stack_candidate(...)`
- `common/contracts.py::_stack_profile(...)`
- `tests/test_contract_resolution.py`
- `tests/test_researcher_search_artifacts.py`

변경:

- `stack_anchor_query`는 이제 per-hit strong evidence가 아니라 per-stack low-weight hint다.
- researcher stack candidate는 이제 `score`와 `sources`를 보존한다.
- runtime stack selection은 아래 조건을 만족하는 top researcher candidate를 선택할 수 있다.
  - `confidence >= medium`
  - text-backed evidence 존재 (`search_hit_text`)
  - second candidate 대비 충분한 margin

현재 관찰:

- representative `open-redirect-dynamic-name-only`
  - researcher report:
    - `python/flask = score 0.55 / medium / [profile_prior, search_hit_text, stack_anchor_query]`
    - `python/fastapi = score 0.20 / low / [available_skeleton, stack_anchor_query]`
  - runtime recipe:
    - `stack_source = researcher_candidate`
    - `stack_defaulted = false`
    - `stack_dependence.class = researcher_inferred`

의미:

- name-only dynamic lane에서 repo prior가 항상 자동 승리하던 bias를 일부 줄였다.
- stack ambiguity는 아직 남지만, 적어도 current lane이 silent default보다는 evidence-led selection에 조금 더 가까워졌다.

### 3.3 이번 최신 slice: evidence graph de-bias

적용:

- `agents/researcher/service.py::_build_evidence_graph(...)`
- `tests/test_researcher_search_artifacts.py`

변경:

- `supports_family_hypothesis`는 더 이상 query family seed만으로 붙지 않는다.
- `supports_negative_family_hypothesis`도 query negative flag만으로 붙지 않는다.
- `supports_stack_hypothesis`도 stack-anchor query만으로 붙지 않는다.
- 현재는 snippet/title/url/raw_content에 아래가 있어야 support edge가 붙는다.
  - matched alias
  - matched anchor
  - canonical family label
  - known framework marker

현재 관찰:

- query-only generic evidence는 더 이상 family/stack support edge를 자동으로 얻지 않는다.
- negative family branch(`template_injection`)는 canonical family label 기반으로 여전히 유지된다.

의미:

- evidence graph가 완전히 authority-aware해진 것은 아니지만,
  query plan이 자기 자신을 support하는 self-confirming 구조는 한 단계 줄었다.

### 3.4 최신 representative dynamic lane에서 실제로 바뀐 것

- `support_promotion.reasons`에서 `stack_selection:defaulted`가 사라졌다.
- `open_world_readiness.blockers`에서 `stack_defaulted`가 사라졌다.
- `artifact_quality.notes`에서 defaulted stack note가 사라졌다.
- `name_only_next_required_step`가 `stack_or_runtime_design`에서 `open_world_generation`으로 이동했다.
- `request_ir.stack_candidates`의 top candidate가 `researcher_candidate(selected)`로 바뀌었다.
- `name_only_primary_focus`가 `stack_or_runtime_design`에서 `open_world_generation`으로 이동했다.
- `runtime_recipe.stack_selection` / `stack_dependence.selection_*`가 추가되어 selection resolution이 summary/manifest에 직접 남는다.
- `request_ir.selection_decision`이 추가되어 family/stack selection truth가 request plane에도 다시 남는다.
- `request_ir_summary`가 raw candidate ambiguity와 resolved/unresolved ambiguity를 같이 보여 주기 시작했다.
- `selection_readiness_summary`가 family/stack selected, ready_for_materialization, selection source/basis를 top-level aggregate로 보여 준다.
- `selection_readiness_summary`는 이제 family/stack evidence-backed 여부, authority bucket, `open_world_evidence_ready_bundles`도 같이 보여 준다.
- `name_only_outcome`이 `selection_ready_for_materialization`, `selected_family`, `selected_stack_id`를 직접 싣는다.
- `name_only_outcome`은 이제 `selection_open_world_evidence_ready`, `family_support_count`, `stack_support_count`도 같이 싣는다.
- `executor_plan`이 추가되어 declared `health_path`와 service port/topology가 executor-facing contract로 surface된다.
- `support_promotion` / `open_world_readiness`는 이제 selection evidence gap이 있을 때 `selection_evidence` blocker로 그 차이를 직접 표현할 수 있다.
- `open_world` verdict도 이제 selection source / selection evidence readiness를 직접 싣는다.

의미:

- current lane의 bottleneck이 “silent default stack”에서 “bounded dynamic generation 자체”로 조금 더 명확히 이동했다.
- planning focus와 outcome next step이 representative lane에서는 같은 blocker model(`open_world_generation`)로 정렬됐다.
- executor도 이제 declared `health_path`가 있을 때 readiness probe에서 그 경로를 실제로 사용한다.
- representative dynamic lane은 현재 `selection_open_world_evidence_ready = true`라 새 selection-evidence blocker를 직접 밟지 않지만, dynamic partial lane 일반에서는 이 차이를 blocker로 표현할 수 있게 됐다.
- 다만 이 정렬과 executor-plan 연결은 아직 partial lane 전체에 일반화된 controller는 아니다.

## 4. Current Completeness Assessment

### 4.1 regression platform 관점

강점:

- unit/integration baseline 안정적
- representative E2E rerun 정상
- summary surface honesty 개선

평가:

- `8.6/10`

### 4.2 name-only intent fidelity 관점

강점:

- `intent_met` / `partial` / `abstain` / `fail_closed` 구분이 실제로 유지된다
- degraded dynamic lane이 더 이상 support-like promotion으로 읽히지 않는다
- representative dynamic lane에서 stack이 silent default가 아니라 researcher-evidence-led selection으로 조금 이동했다
- researcher evidence graph의 query-seeded support가 일부 줄었다

약점:

- `request_ir`는 여전히 true control plane이 아니다
- selected stack truth가 current lane에서는 roundtrip되지만, generator/executor 전 구간의 authoritative branch controller는 아니다
- planning focus와 outcome next step이 representative lane에서는 정렬됐지만, 아직 모든 partial lane에 일반화되지는 않았다
- dynamic lane은 여전히 deterministic fallback-first 경향이 강하다
- negative branch는 researcher evidence graph까지 내려왔지만 generator/executor decision의 primary input은 아직 아니다

평가:

- `7.5/10`

### 4.3 generalized open-world dynamic vulnerability Docker generator 관점

강점:

- unsupported/ambiguous lane을 success처럼 포장하지 않는다
- degraded dynamic lane도 `support_promotion`에서 계속 배제된다
- stack 선택이 일부 evidence-led가 되었지만, 이건 fidelity 개선이지 generalized capability 확장은 아니다

약점:

- family discovery는 fixed family universe에 bounded
- catalog entries는 여전히 `12`
- scaffold stack pool은 여전히 `2`
  - `python/flask`
  - `python/fastapi`
- compiler registry는 여전히 `13`
- semantic-guided minimal_dynamic family coverage는 여전히 `12`
- executor는 여전히 single primary service + optional sidecar에 bounded

평가:

- `3.2/10`

### 4.4 operator-facing artifact quality 관점

강점:

- deterministic하고 provenance가 좋다
- SQLi/compiler lane은 regression fixture로 쓸 만하다
- degraded lane도 이전보다 더 정직하게 읽힌다

약점:

- fallback artifact는 여전히 single-route demo가 많다
- state/session/victim realism이 얕다
- `artifact_quality`는 아직 heuristic이고 lab realism을 과대평가할 수 있다

평가:

- regression fixture quality: `7/10`
- 실습/lab artifact quality: `4/10`

## 5. Generalization / Template Dependence Assessment

현재 truth는 아래에 가깝다.

- direct static template dependence는 일부 줄었다
- 하지만 generalized planning이 그 자리를 대체한 것은 아니다
- 현재 boundedness는 아래 레이어의 조합이다
  - family catalog boundedness
  - fixed family-hint boundedness
  - scaffold boundedness
  - compiler fragment boundedness
  - deterministic fallback boundedness
  - repo asset/runtime prior boundedness

현재 lower bound:

- catalog entries: `12`
- family hint families: `12`
- template count: `3`
- scaffold stack pool: `2`
- compiler strategies: `13`
- semantic-guided minimal_dynamic families: `12`

현재 representative truth:

- `sqli-name-only`
  - `compiler_generated`
  - `intent_met`
  - `name_only_primary_focus = generation_execution`
  - `support_promotion = false`
  - curated lower-bound regression success

- `open-redirect-dynamic-name-only`
  - `deterministic_fallback`
  - `open_world_class = semantic_guided_minimal_dynamic`
  - `name_only_outcome = partial`
  - `support_promotion = false`
  - `stack_source = researcher_candidate`
  - `stack_defaulted = false`
  - 그러나 여전히 `single_service` / semantic-guided bounded fallback lane이다

- `open-redirect-strict-dynamic-no-remote`
  - `capability_gate_rejected`
  - `fail_closed`
  - `support_promotion = false`

즉 “템플릿 의존 완화”는 일부 사실이지만,
그 자리를 generalized open-world capability가 대체한 것은 아니다.

## 6. Residual Gaps

### 6.1 `request_ir` is still too resolved

- candidate field는 있지만 branch-preserving control plane은 아직 researcher 단계 일부에만 걸려 있다
- generator/executor decision은 여전히 `request_ir` primary가 아니다
- latest slice에서 `selection_decision`이 current lane에서 `request_ir`까지 다시 실리고, `selection_readiness_summary`가 resolved/unresolved ambiguity를 분리해서 보여 주지만, 이게 아직 executor/generator 전체의 authoritative input은 아니다
- `ready_for_materialization`와 `open_world_evidence_ready`를 분리했지만, downstream generator/executor가 이 둘을 실제 branching controller로 쓰지는 않는다
- unresolved -> abstain transition modeling이 약하다

### 6.2 planning focus와 outcome step이 아직 이중화돼 있다

- representative dynamic lane에서는
  - `name_only_primary_focus = open_world_generation`
  - `name_only_next_required_step = open_world_generation`
- 하지만 이 정렬 로직이 lane-general controller로 정규화된 것은 아니다
- compatibility/lower-bound lane의 기본 planning focus는 이제 `generation_execution`으로 정리됐지만, planning surface와 acceptance surface를 완전히 분리한 상태 머신은 아직 아니다
- 다른 partial lane에서도 같은 decision policy를 쓰도록 controller를 더 명시화해야 한다

### 6.3 family discovery is still closed-vocabulary

- researcher의 family hypothesis space가 fixed family hints에 bounded돼 있다
- unknown family를 provisional family로 세우는 induction path가 없다

### 6.4 evidence graph는 덜 noisy해졌지만 아직 causal authority graph는 아니다

- query-seeded support edge는 줄었지만,
  current support edge는 여전히 substring/marker match에 크게 의존한다
- snippet claim extraction / source authority weighting / contradiction weighting이 아직 약하다
- 지금의 `support_count`는 "선택된 후보를 지지하는 evidence node 수"이지 causal sufficiency를 보장하는 score는 아니다

### 6.5 stack selection은 개선됐지만 아직 narrow하다

- current stack pool 자체가 `python/flask`, `python/fastapi` 중심이다
- margin policy는 들어갔지만, multi-runtime / multi-service / non-Python lane까지 일반화되지는 않았다

### 6.6 executor plan은 생겼지만 parity는 아직 얕다

- `executor_plan@0.1`은 현재 `service_port` / `health_path` / topology / stack selection 정도만 싣는다
- executor는 declared `health_path`를 readiness probe에 쓰기 시작했지만,
  sidecar wiring / dependency order / seed/init / env/volume contract는 아직 policy/runtime recipe에 더 의존한다

### 6.7 one-shot synthesis is still the main bottleneck

- current synthesis는 여전히 final manifest JSON one-shot에 크게 의존한다
- non-JSON / malformed design -> immediate fallback이 너무 쉽다

### 6.8 `runtime_graph` is not yet the executor control plane

- graph는 summary surface다
- executor는 이 graph를 직접 읽지 않는다
- topology-sensitive family는 reasoning보다 executor model 상한에 더 빨리 막힌다

### 6.9 verifier independence / artifact realism is still limited

- marker-only success를 완전히 벗어나지 못했다
- negative control / forbidden-success / metamorphic coverage가 아직 얕다
- 사람 기준 lab realism rubric이 아직 약하다

### 6.10 performance roadmap is still thin

- representative rerun에서 RESEARCH가 여전히 가장 느리다
- latest rerun에서는 `RESEARCH ≈ 7.22s`, `TOTAL ≈ 13.72s`였지만, remote search latency variance가 커서 one-off sample을 구조 개선으로 단정하면 안 된다
- query dedup/cache/reuse/early stop 계획이 아직 약하다

### 6.11 support promotion loop is still missing

- `support_promotion`은 honesty surface일 뿐, 아직 승격 루프는 아니다
- dynamic success에서 reusable fragment/oracle/runtime contract를 추출해 curated support로 올리는 닫힌 루프가 없다

### 6.12 open-world eval matrix가 아직 없다

- 현재 문서는 capability plan은 있으나,
  어떤 케이스 bucket으로 generalized behavior를 검증할지 명확하지 않다
- `paraphrase`, `broad phrase`, `unknown family`, `misleading stack evidence`, `multi-service required`, `negative family conflict` 같은 eval matrix가 필요하다

### 6.13 primitive-level runtime design control plane이 아직 없다

- semantic signature와 family-aware fallback은 있지만,
  `primitive -> dependency -> topology -> oracle`를 먼저 세우는 controller는 아직 없다
- current dynamic lane은 여전히 selected family와 bounded builder에 크게 의존한다
- 즉 primitive-informed behavior는 일부 있지만 primitive-first control plane은 아니다

## 7. How To Update This Document

- 이 문서는 direct rerun, stable code inspection, summary surface 변경이 있을 때만 갱신한다.
- TODO, priority, next slice는 쓰지 않는다. 그런 내용은 [docs/final_solution.md](final_solution.md)로 보낸다.
- representative sample performance는 observed sample로만 적고 generalized claim으로 승격하지 않는다.
- `promotion_eligible`와 generalized support claim을 같은 의미로 서술하지 않는다.

## 8. Evidence Sources

- workspace code inspection
- `python -m pytest -q tests`
- targeted regression slices
- representative E2E reruns
- repo-tracked historical snapshots for comparison only

## 9. Current Bottom Line

현재 vulDocker는 여전히 아래에 가깝다.

> "지원 family에 대한 정직한 regression platform, 그리고 일부 supported family에 대한 bounded dynamic degraded generator"

이번 latest slice로 실제로 좋아진 것은 다음이다.

- current unit/integration baseline이 `586 passed`까지 올라왔다
- stack selection이 representative dynamic lane에서 실제로 repo prior를 벗어나 `researcher_candidate`로 이동했다
- selected stack truth가 `runtime_recipe -> request_ir -> manifest summary`까지 다시 실리기 시작했다
- raw candidate multiplicity와 resolved selection을 `request_ir_summary` / `selection_readiness_summary`에서 따로 읽을 수 있게 됐다
- selected family/stack마다 support count와 authority 분포를 같이 읽을 수 있게 됐다
- `ready_for_materialization`와 `open_world_evidence_ready`를 분리해서 lower-bound success와 evidence-backed dynamic readiness를 더 구분하게 됐다
- generator preflight contract injection으로 semantic-guided fallback이 current `request_ir.selection_decision`을 실제로 읽기 시작했다
- open-world verdict도 current selection truth를 직접 surface하기 시작했다
- `stack_defaulted` blocker가 same lane에서 제거됐다
- representative dynamic lane에서 `planning_focus`와 `next_required_step`이 둘 다 `open_world_generation`으로 정렬됐다
- minimal `executor_plan`이 추가되어 declared `health_path`를 executor readiness probe가 실제로 사용하기 시작했다
- `support_promotion` / `open_world_readiness`가 이 변화를 그대로 반영한다
- evidence graph가 query seed만으로 support edge를 붙이던 coupling이 일부 줄었다
- 문서가 오래된 수치/중복 서술 대신 current rerun + current code truth 기준으로 다시 정렬됐다

하지만 가장 중요한 구조적 한계는 그대로다.

- early-resolved control plane
- closed-vocabulary family hypothesis
- 아직 얕은 evidence authority
- one-shot synthesis
- executor/runtime plan 불일치
- support promotion loop 부재
- multi-service / unknown-family / unknown-stack open-world 미지원

구현 우선순위와 next slice는 [docs/final_solution.md](final_solution.md)를 본다.
