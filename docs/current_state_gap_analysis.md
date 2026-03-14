# 동적 취약 Docker 생성 Current State / Gap Analysis

본 문서는 2026-03-14 KST 기준 workspace 재검토, 실제 rerun, 그리고 이번 iteration에서 적용한
`name-only` / open-world honesty hardening을 반영한 최신 상태 문서다.

이번 갱신의 핵심은 아래 여덟 가지다.

- 현재 코드 기준으로 강하게 말할 수 있는 truth를 정리
- `promotion`과 generalized/open-world support claim을 분리
- `stack_defaulted`를 surface에 올려 hidden default boundedness를 드러냄
- `open_world_readiness` blocker를 `name_only_generation_spec` planning focus로 부분 연결
- raw family candidate와 material family candidate를 분리해 strong resolution lane의 과민한 ambiguity를 완화
- strong resolution lane에서 `request_ir.family_candidates` 자체를 low-confidence researcher background family로 과하게 오염시키지 않도록 upstream filtering을 추가
- `request_ir.negative_hypotheses`와 canonicalized name-driven authority를 researcher query/evidence 단계까지 연결
- `docs/current_state_gap_analysis.md` 내부의 오래된 성능/계획/서술을 정리하고 하나로 병합

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
- `promotion`은 regression/pack 관점이다.
- open-world/support claim은 이제 `support_promotion`을 같이 봐야 한다.
- `generalization_*`는 legacy/comparison surface로만 본다.
- pre-generation fail-closed / abstain lane은 실행기 성공이 아니라 capability/research contract 관점에서 읽는다.

## 2. Current Verified Baseline

### 2.1 2026-03-14 실제 실행 결과

| command | result | interpretation |
| --- | --- | --- |
| `python -m pytest -q tests` | `572 passed, 53 skipped, 1 warning in 2.31s` | current unit/integration baseline 정상 |
| `python -m pytest -q tests/test_react_loop_queries.py tests/test_researcher_search_artifacts.py` | `21 passed in 1.25s` | 이번 iteration의 researcher query/evidence patch surface 정상 |
| `python -m pytest -q tests/test_contract_resolution.py tests/test_synthesis_prompt_contract.py` | `53 passed in 0.32s` | contract/prompt surface 회귀 없음 |
| `VULD_RUN_E2E=1 python -m pytest -q tests/e2e/test_cases.py -rs` | `51 passed, 2 skipped in 525.71s` | official E2E baseline 정상 |
| `python - <<PY ... normalize_requirement({'vuln_name':'Cross Site Injection', ...}) ...` | multi-family candidates surfaced | broad free-form phrase가 `xss`/`csrf` 후보를 보존하고 query plan도 이를 사용 |
| `python - <<PY ... build_generator_contract(...) for 'Cross Site Injection' ...` | planning focus surfaced | broad free-form phrase에서 planning focus가 `family_disambiguation`으로 올라오고 `stack_defaulted`/`oracle_realism`까지 reason token으로 드러남 |
| `python - <<PY ... ReactLoop.query_plan_from_requirement(...) for canonicalized name-driven 'Reflected XSS' ...` | request_ir authority preserved | `family_hypotheses = [xss(catalog_resolution)]`, raw `CWE-79` query seed는 빠지고 `negative_family_hypotheses = [template_injection]`, `contradiction_check` query가 추가됨 |

주의:

- full official E2E baseline(`51 passed, 2 skipped`)은 same-day reference baseline으로 보되,
  이번 최신 slice 후에는 representative rerun 위주로 다시 확인했다.
- 아래 generalized/open-world 평가는 baseline 통과와 별개로 representative truth와 current code structure를 함께 본 정성 평가다.

### 2.2 Representative rerun truth

- `sqli-name-only`
  - `generation_origin = compiler_generated`
  - `name_only_outcome.decision = intent_met`
  - `open_world_class = catalog_resolved_lower_bound`
  - `promotion_eligible = true`
  - `support_promotion_eligible = false`
  - 즉 fully validated lower-bound regression success이지만 generalized/open-world support claim은 아니다

- `open-redirect-dynamic-name-only`
  - `generation_origin = deterministic_fallback`
  - `open_world_class = semantic_guided_minimal_dynamic`
  - `strict_open_world_class = strict_minimal_dynamic_fallback`
  - `name_only_outcome.decision = partial`
  - `name_only_next_required_step = stack_or_runtime_design`
  - `name_only_primary_focus = stack_or_runtime_design`
  - `request_ir.family_candidates = [open_redirect]`
  - `promotion_eligible = true`
  - `support_promotion_eligible = false`
  - `support_promotion.reasons`에 아래가 직접 남는다
    - `strict_open_world:strict_minimal_dynamic_fallback`
    - `open_world:semantic_guided_minimal_dynamic`
    - `artifact_quality:medium`
    - `stack_selection:defaulted`
    - `name_only_outcome:partial`
  - `stack_dependence.stack_defaulted = true`
  - `open_world_readiness.blockers = [strict_open_world_gate, open_world_non_positive, artifact_quality_below_high, stack_defaulted, name_only_intent_not_met]`
  - `name_only_planning_focus.by_focus = {stack_or_runtime_design: [stack_defaulted, stack_ambiguous]}`
  - `artifact_quality.oracle_rigor = high`
  - `artifact_quality.metamorphic_present = true`
  - sample performance:
    - `RESEARCH ≈ 7.60s`
    - `GENERATOR ≈ 1.31s`
    - `EXECUTOR_BUILD ≈ 0.79s`
    - `EXECUTOR_RUN ≈ 1.55s`
    - `VERIFY ≈ 1.37s`
    - `REVIEW ≈ 1.27s`

- `open-redirect-strict-dynamic-no-remote`
  - `generation_origin = capability_gate_rejected`
  - `name_only_outcome.decision = fail_closed`
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

- `trusted-dynamic-sqli`
  - expectations는 통과했지만 `request_kind = other`
  - `strict_open_world_class = strict_fixture_backed_dynamic`
  - `support_promotion_eligible = false`
  - 즉 “dynamic으로 보이는 regression lane”과 “name-only intent-faithful open-world lane”을 구분해야 한다

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
- `support_promotion`이 추가되어 degraded dynamic/lower-bound lane이 support-like success처럼 보이는 문제를 줄였다.
- `stack_defaulted`가 추가되어 `profile_prior`/`default_stack_profile` 기반 boundedness가 top-level summary에서 직접 드러난다.
- fully validated된 `partial` dynamic lane도 이제 `next_required_step`가 남아,
  어디를 먼저 보완해야 하는지 summary에서 바로 읽을 수 있다.
- `boundedness_summary`와 `open_world_readiness_summary`가 추가되어
  repo-wide boundedness inventory와 per-lane blocker를 summary에서 바로 읽을 수 있다.
- `name_only_generation_spec.planning_focus_summary`가 추가되어
  blocker diagnosis가 synthesis prompt/contract에는 직접 연결된다.
- `material_candidate_count` / `material_ambiguous`가 추가되어
  high-confidence request resolution 위에 low-confidence background family hypothesis가 얹히는 경우를
  raw ambiguity와 구분해서 읽게 된다.
- `open_redirect` minimal dynamic fallback이 explicit `verification_spec`를 싣고,
  representative rerun에서 `metamorphic_missing` blocker가 제거됐다.
- strong resolution lane에서는 `request_ir.family_candidates`가 이제
  low-confidence researcher background family 없이 더 좁게 유지된다.
- broad free-form phrase에서도 `request_ir.family_candidates`와 researcher query seed가
  single resolved id보다 더 candidate-aware하게 동작한다.
- canonicalized name-driven lane에서도 researcher query plan이 raw `vuln_id` family basis와
  identifier-level query seed를 다시 주입하지 않고 `request_ir` candidate authority를 우선한다.
- `request_ir.negative_hypotheses`가 이제 `query_plan.negative_family_hypotheses`와
  `evidence_graph`의 contradiction edge로 이어져 branch-preserving 정도가 조금 올라갔다.
- current dynamic name-only lane은 여전히 자주 deterministic fallback으로 닫힌다.
- current dynamic name-only lane은 representative rerun에서 여전히 `partial`이지 `intent_met`가 아니다.

### 2.4 아직 강하게 말하면 안 되는 것

- arbitrary 취약점 이름만으로 generalized open-world positive를 안정적으로 만든다.
- unknown family / unknown stack / multi-service topology를 실제 control plane으로 materialize한다.
- `promotion_eligible = true`가 generalized support readiness를 뜻한다.
- `artifact_quality = medium`가 사람 기준 좋은 실습/lab artifact를 뜻한다.
- current dynamic lane의 `fully_validated`가 곧 intent-faithful open-world success를 뜻한다.

## 3. 이번 Iteration에서 실제 적용한 보완

### 3.1 `support_promotion` surface 분리

적용:

- `orchestrator/pack.py::_bundle_support_promotion_status(...)`
- `orchestrator/pack.py::_support_promotion_summary(...)`
- `tests/e2e/run_case.py::_load_manifest_summary(...)`

변경:

- 기존 `promotion`은 그대로 regression/pack surface로 둔다.
- generalized/open-world support claim은 이제 별도 `support_promotion`으로 본다.
- `support_promotion`은 아래를 동시에 요구한다.
  - base `promotion.eligible = true`
  - `strict_open_world.counts_as_generalization = true`
  - `open_world.counts_as_generalization = true`
  - `artifact_quality.band = high`
  - `oracle_clarity = high`
  - non-defaulted stack
  - evidence-backed family
  - `name_only_outcome = intent_met`

의미:

- `open-redirect-dynamic-name-only` 같은 degraded dynamic fallback lane은
  계속 runnable regression surface로는 남되,
  generalized support candidate처럼 읽히지는 않는다.

### 3.2 `stack_defaulted` surface 추가

적용:

- `common/contracts.py::_stack_profile(...)`
- `common/contracts.py::_build_runtime_recipe(...)`
- `orchestrator/pack.py::_bundle_stack_dependence(...)`
- `orchestrator/pack.py::_stack_dependence_summary(...)`

변경:

- stack 선택이 아래 source에서 왔으면 `stack_defaulted = true`를 남긴다.
  - `default_stack_profile`
  - `profile_prior`
  - `available_skeleton`
- summary에 `stack_defaulted_bundles`가 추가됐다.

의미:

- hidden default boundedness가 이제 top-level에서 바로 읽힌다.
- `open-redirect-dynamic-name-only` / `open-redirect-strict-dynamic-no-remote`는
  둘 다 `stack_defaulted = true`로 드러난다.

### 3.3 artifact quality note 보강

적용:

- `orchestrator/pack.py::_bundle_artifact_quality(...)`
- `orchestrator/pack.py::_artifact_quality_summary(...)`

변경:

- stack이 repo-prior/default로 선택됐으면 artifact note에 그 사실을 남긴다.
- `artifact_quality_summary`는 이제 `stack_defaulted_bundles`도 같이 센다.

의미:

- quality score 자체를 바꾸지는 않았지만,
  operator-facing reading에서는 “왜 medium/high가 아닌가”를 더 정직하게 설명한다.

### 3.4 regression coverage 보강

추가/통과:

- `tests/test_pack_promotion.py`
  - degraded dynamic bundle의 `support_promotion` reject
  - strict open-world positive bundle의 `support_promotion` accept
  - `stack_defaulted_bundles` rollup
- `tests/test_run_case_summary_surface.py`
  - `support_promotion`
  - `support_promotion_eligible`
  - `stack_defaulted`
  - `stack_defaulted_bundles`

### 3.5 partial lane `next_required_step` / prompt contract hardening

적용:

- `orchestrator/pack.py::_bundle_name_only_outcome(...)`
- `common/prompts/templates.py::_name_only_generation_spec_contract(...)`

변경:

- fully validated되었지만 `partial`인 dynamic lane도 이제 `next_required_step`를 남긴다.
- 현재 규칙:
  - `stack_defaulted`면 `stack_or_runtime_design`
  - family evidence/ambiguity가 약하면 `research`
  - degraded/lower-bound dynamic closure면 `open_world_generation`
- prompt contract도 이제 `stack_defaulted`를 직접 surface한다.
  - repo-prior/default stack은 evidence-backed가 아니라는 경고를 prompt에 남긴다.

현재 관찰:

- `open-redirect-dynamic-name-only`
  - `fully_validated = true`
  - `decision = partial`
  - `next_required_step = stack_or_runtime_design`

의미:

- “실행/검증은 끝났지만 왜 아직 intent-faithful open-world success가 아닌가”를
  summary와 prompt 모두에서 바로 읽을 수 있다.

### 3.6 `boundedness_summary` / `open_world_readiness_summary` 추가

적용:

- `orchestrator/pack.py::_boundedness_summary(...)`
- `orchestrator/pack.py::_bundle_open_world_readiness(...)`
- `orchestrator/pack.py::_open_world_readiness_summary(...)`
- `tests/e2e/run_case.py::_load_manifest_summary(...)`

변경:

- manifest/run_case summary가 이제 repo-wide boundedness inventory를 직접 노출한다.
  - `catalog_entries`
  - `catalog_families`
  - `family_hint_families`
  - `template_count`
  - `scaffold_stack_pool`
  - `compiler_strategy_count`
  - `semantic_guided_family_builders`
  - `executor_topology_classes`
  - `executor_multi_primary_supported`
- bundle-level `open_world_readiness`와 top-level `open_world_readiness_summary`를 추가했다.
- 이 surface는 `support_promotion` reason을 blocker category로 정규화한다.
  - 예: `strict_open_world_gate`, `open_world_non_positive`, `stack_defaulted`, `family_candidate_evidence_missing`

현재 관찰:

- current repo boundedness inventory
  - `catalog_entries = 12`
  - `family_hint_families = 12`
  - `template_count = 3`
  - `scaffold_stack_pool = 2`
  - `compiler_strategy_count = 13`
  - `semantic_guided_family_builders = 12`
  - `executor_multi_primary_supported = false`
- `open-redirect-dynamic-name-only`
  - `open_world_readiness.ready = false`
  - `by_blocker = {strict_open_world_gate: 1, open_world_non_positive: 1, artifact_quality_below_high: 1, stack_defaulted: 1, name_only_intent_not_met: 1}`

의미:

- 기존에는 “지원 가능/불가”를 사람이 여러 summary를 합쳐 읽어야 했다.
- 이제는 generalized/open-world readiness 부족 사유가 blocker category로 직접 surface된다.

### 3.7 `request_ir.family_candidates` enrichment + candidate-aware query seeding

적용:

- `common/vuln_catalog.py::catalog_family_candidates_for_label(...)`
- `common/schema/requirement.py::_family_candidates_for_request_ir(...)`
- `orchestrator/plugins/react_loop.py::_infer_family_hypotheses(...)`

변경:

- plan 단계의 `request_ir.family_candidates`가 이제 resolved family 1개만 담지 않는다.
- free-form label이 broad phrase인 경우에도 catalog 전역 token/label overlap을 바탕으로
  다중 family 후보를 보존한다.
- researcher query plan도 이제 `request_ir.family_candidates`를 family hypothesis seed로 읽는다.

현재 관찰:

- `Cross Site Injection`
  - canonical resolution은 여전히 `NAME-CROSS-SITE-INJECTION`
  - 하지만 `request_ir.family_candidates = [xss, csrf]`
  - `query_plan.family_hypotheses = [xss, csrf]`
  - query seed에도 `cross-site scripting ...` / `csrf ...` 류 family-aware query가 포함된다

의미:

- current control plane이 아직 authoritative branching은 아니지만,
  적어도 plan/research 단계가 “synthetic_name -> no family candidates”로 너무 빨리 닫히는 문제는 일부 완화됐다.

### 3.8 `planning_focus_summary`로 blocker를 prompt/contract에 연결

적용:

- `common/contracts.py::_name_only_planning_focus_summary(...)`
- `common/contracts.py::_build_name_only_generation_spec(...)`
- `common/prompts/templates.py::_name_only_generation_spec_contract(...)`
- `orchestrator/pack.py::_name_only_planning_summary(...)`
- `tests/e2e/run_case.py::_load_manifest_summary(...)`

변경:

- `name_only_generation_spec`가 이제 `planning_focus_summary`를 포함한다.
- 이 payload는 현재 lane이 generalized/open-world 관점에서 무엇을 먼저 해결해야 하는지 정리한다.
  - `family_disambiguation`
  - `stack_or_runtime_design`
  - `evidence_authority`
  - `oracle_realism`
  - `independent_verification`
- top-level manifest/run_case summary는 `name_only_planning_summary`와 `name_only_primary_focus`를 같이 노출한다.
- synthesis prompt도 이제 planning focus 순서를 직접 본다.

현재 관찰:

- `open-redirect-dynamic-name-only`
  - `name_only_primary_focus = stack_or_runtime_design`
- `open-redirect-strict-dynamic-no-remote`
  - `name_only_primary_focus = stack_or_runtime_design`
  - `evidence_authority`, `oracle_realism`, `independent_verification`까지 같이 surface된다
- `Cross Site Injection`
  - `family_candidates = [xss, csrf]`
  - `planning_focus_summary.primary_focus = family_disambiguation`
  - `reason_tokens = [family_unresolved, family_ambiguous, stack_defaulted, stack_ambiguous, family_candidate_evidence_missing, remote_research_evidence_missing, negative_control_missing, metamorphic_missing]`

의미:

- `open_world_readiness` blocker가 이제 사람이 summary를 읽는 용도를 넘어,
  generator prompt/contract에서 “무엇을 먼저 풀어야 하는지”를 직접 가리킨다.
- 다만 아직 orchestrator의 retry policy, researcher query budget, executor plan 우선순위를 바꾸는
  control-plane input은 아니다.

### 3.9 material family candidates로 과민한 ambiguity 완화

적용:

- `common/contracts.py::_material_family_candidates(...)`
- `common/contracts.py::_build_name_only_generation_spec(...)`
- `orchestrator/pack.py::_bundle_family_dependence(...)`
- `common/prompts/templates.py::_name_only_generation_spec_contract(...)`

변경:

- `family_candidate_summary`가 이제 아래를 같이 남긴다.
  - `candidate_count`
  - `material_candidate_count`
  - `material_ambiguous`
  - `deprioritized_candidate_count`
- high-confidence request/catalog resolution이 선행되는 lane에서는
  low-confidence researcher background families를 planning ambiguity 계산에서 제외한다.
- prompt에는 `material_count`와 deprioritized candidate count가 같이 드러난다.

현재 관찰:

- strong `Open Redirect` resolution + researcher background families
  - raw `candidate_count = 3`
  - `material_candidate_count = 1`
  - `material_ambiguous = false`
  - `deprioritized_candidate_count = 2`
  - `planning_focus_summary.primary_focus = stack_or_runtime_design`
- representative rerun `open-redirect-dynamic-name-only`
  - 기존 `family_disambiguation` primary focus에서
  - 현재 `stack_or_runtime_design` primary focus로 내려왔다

의미:

- current system이 여전히 closed-vocabulary / bounded인 것은 그대로지만,
  적어도 clear request resolution lane에서 researcher noise 때문에 planning focus가 과민하게 흔들리는 문제는 줄었다.
- 이는 generalized capability를 늘린 것은 아니고, name-only intent fidelity 진단의 precision을 높인 쪽에 가깝다.

### 3.10 minimal dynamic open redirect fallback의 oracle realism 보강

적용:

- `agents/generator/synthesis.py::_fallback_manifest_from_parts(...)`
- `agents/generator/synthesis.py::_minimal_dynamic_manifest_open_redirect(...)`

변경:

- `open_redirect` minimal dynamic fallback이 이제 explicit `verification_spec`를 포함한다.
- 현재 포함되는 oracle realism은 아래다.
  - `negative_controls = [missing-next]`
  - `metamorphic = {total: 1, passed: 1, rationale: relative same-origin redirect should not count as exploit}`
  - `negative_text_markers = ['Unexpected redirect response']`

현재 관찰:

- representative rerun `open-redirect-dynamic-name-only`
  - `artifact_quality.oracle_clarity = high`
  - `artifact_quality.oracle_rigor = high`
  - `negative_control_present = true`
  - `metamorphic_present = true`
  - `name_only_planning_focus.by_focus`에서 `oracle_realism`가 빠지고
    `stack_or_runtime_design`만 남는다

의미:

- 여전히 degraded deterministic fallback이고 generalized/open-world positive는 아니다.
- 다만 fallback artifact의 정성 품질과 oracle contract의 충실도는 이전보다 한 단계 나아졌다.
- template dependence를 줄인 것은 아니고, bounded fallback artifact의 realism을 조금 높인 쪽에 가깝다.

### 3.11 strong resolution lane의 `request_ir.family_candidates` upstream noise filtering

적용:

- `common/contracts.py::_merge_family_candidates(...)`
- `common/contracts.py::_build_name_only_generation_spec(...)`

변경:

- high-confidence request/catalog resolution이 선행되고 authoritative existing family candidate가 있으면,
  researcher background family hypothesis는 아래 경우만 `request_ir.family_candidates`에 다시 합친다.
  - request-resolution-like source
  - researcher confidence가 `high`
- 그 외 low/medium researcher background families는 `request_ir.family_candidates`에는 넣지 않는다.
- 대신 `family_candidate_summary`는 `candidate_count` / `deprioritized_candidate_count`로
  background family 존재를 계속 surface한다.

현재 관찰:

- representative rerun `open-redirect-dynamic-name-only`
  - 이전 `request_ir.family_candidates = [open_redirect, xss, ssrf, ...]`
  - 현재 `request_ir.family_candidates = [open_redirect]`
  - `name_only_primary_focus`는 그대로 `stack_or_runtime_design`
- broad phrase `Cross Site Injection` 같이 strong resolution이 없는 lane은
  이 filtering의 대상이 아니므로 multi-family candidate behavior를 유지한다.

의미:

- generalized capability를 넓힌 것은 아니다.
- 대신 strong resolution lane의 candidate control plane 자체가 덜 noisy해져,
  downstream prompt/summary/generator 판단이 더 안정적이 된다.

### 3.12 `request_ir` authority가 researcher query/evidence graph까지 내려가도록 보강

적용:

- `orchestrator/plugins/react_loop.py::_infer_family_hypotheses(...)`
- `orchestrator/plugins/react_loop.py::ReactLoop.query_plan_from_requirement(...)`
- `agents/researcher/service.py::_build_evidence_graph(...)`
- `tests/test_react_loop_queries.py`
- `tests/test_researcher_search_artifacts.py`

변경:

- canonicalized name-driven lane에서는 researcher query plan이 raw `vuln_id`를 다시 high-confidence family basis로 주입하지 않는다.
- 같은 lane에서 `CWE-*` advisory/writeup query seed도 기본적으로 다시 치지 않는다.
- 대신 `request_ir.family_candidates`가 family hypothesis의 primary source가 된다.
- `request_ir.negative_hypotheses`는 이제 아래 surface로 실제 전달된다.
  - `query_plan.negative_family_hypotheses`
  - `contradiction_check` evidence type query
  - `evidence_graph`의 `negative_family_hypothesis`
  - `evidence_graph`의 `supports_negative_family_hypothesis`

현재 관찰:

- canonicalized name-driven `Reflected XSS`
  - `family_hypotheses = [xss(catalog_resolution)]`
  - raw `CWE-79 weakness details ...` query seed는 빠진다
  - `negative_family_hypotheses = [template_injection(researcher_contradiction)]`
  - query plan에 `contradiction_check` query가 추가된다
- researcher evidence graph는 이제 negative family branch를 별도 edge kind로 유지한다

의미:

- `request_ir`가 여전히 executor/generator 전체의 authoritative control plane은 아니지만,
  적어도 researcher 단계에서는 branch 정보가 summary-only payload가 아니라 retrieval/evidence input으로 한 단계 내려왔다.
- generalized capability 자체가 늘어난 것은 아니고,
  canonicalized name-driven lane이 raw identifier heuristic으로 과하게 다시 닫히는 경향을 줄인 변화에 가깝다.

## 4. Current Completeness Assessment

### 4.1 regression platform 관점

강점:

- unit/integration baseline 안정적
- representative E2E rerun 정상
- summary surface honesty 개선

평가:

- `8.5/10`

### 4.2 name-only intent fidelity 관점

강점:

- `intent_met` / `partial` / `abstain` / `fail_closed` 구분이 실제로 유지된다
- degraded dynamic lane이 더 이상 support-like promotion으로 읽히지 않는다
- hidden stack default boundedness가 surface에 남는다
- canonicalized name-driven lane에서도 researcher가 raw `vuln_id`로 다시 과닫히지 않고 `request_ir`를 더 우선한다

약점:

- `request_ir`는 여전히 true control plane이 아니다
- dynamic lane은 여전히 deterministic fallback-first 경향이 강하다
- stack default는 이제 visible이지만 아직 제거되지는 않았다
- negative branch는 researcher evidence graph까지 내려왔지만 generator/executor decision의 primary input은 아직 아니다

평가:

- `6.8/10`

### 4.3 generalized open-world dynamic vulnerability Docker generator 관점

강점:

- unsupported/ambiguous lane을 success처럼 포장하지 않는다
- degraded dynamic lane도 이제 `support_promotion`에서 명시적으로 배제된다

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

- `3/10`

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
  - repo-prior/default stack boundedness

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
  - `support_promotion = false`
  - curated lower-bound regression success

- `open-redirect-dynamic-name-only`
  - `deterministic_fallback`
  - `open_world_class = semantic_guided_minimal_dynamic`
  - `name_only_outcome = partial`
  - `support_promotion = false`
  - `stack_defaulted = true`

- `open-redirect-strict-dynamic-no-remote`
  - `capability_gate_rejected`
  - `fail_closed`
  - `support_promotion = false`

즉 “템플릿 의존 완화”는 일부 사실이지만,
그 자리를 generalized open-world capability가 대체한 것은 아니다.

## 6. Residual Gaps

### 6.1 `request_ir` is still too resolved

- candidate field는 있지만 branch-preserving control plane은 아직 researcher 단계 일부에만 걸려 있다
- canonicalized name-driven lane의 query/evidence에서는 raw `vuln_id` 재주입을 줄였지만,
  generator/executor decision은 여전히 `request_ir` primary가 아니다
- unresolved -> abstain transition modeling이 약하다
- stack/family/oracle ambiguity가 authoritative branch로 유지되지 않는다

### 6.2 family discovery is still closed-vocabulary

- researcher의 family hypothesis space가 fixed family hints에 bounded돼 있다
- unknown family를 provisional family로 세우는 induction path가 없다

### 6.3 `evidence_graph` is still query-coupled

- support edge가 query target과 alias substring에 강하게 의존한다
- negative family branch edge는 추가됐지만 snippet-level causal evidence / source authority가 여전히 부족하다

### 6.4 one-shot synthesis is still the main bottleneck

- current synthesis는 여전히 final manifest JSON one-shot에 크게 의존한다
- non-JSON / malformed design -> immediate fallback이 너무 쉽다

### 6.5 `runtime_graph` is not yet the executor control plane

- graph는 summary surface다
- executor는 이 graph를 직접 읽지 않는다
- topology-sensitive family는 reasoning보다 executor model 상한에 더 빨리 막힌다

### 6.6 hidden default는 visible해졌지만 제거되지는 않았다

- `stack_defaulted`가 이제 드러나지만,
  unresolved stack이 아직 실제로 abstain/fail_closed로 닫히지는 않는다

### 6.7 verifier independence / oracle realism is still limited

- marker-only success를 완전히 벗어나지 못했다
- negative control / forbidden-success / metamorphic coverage가 아직 얕다

### 6.8 performance roadmap is still thin

- representative rerun에서 RESEARCH가 가장 느리다
- query dedup/cache/reuse/early stop 계획이 아직 약하다

### 6.9 support promotion loop is still missing

- `support_promotion`은 honesty surface일 뿐, 아직 승격 루프는 아니다
- dynamic success에서 reusable fragment/oracle/runtime contract를 추출해 curated support로 올리는 닫힌 루프가 없다

### 6.10 readiness summary is now prompt input, but not yet orchestrator control-plane input

- `open_world_readiness` / `stack_defaulted` / evidence/oracle gaps는 이제
  `name_only_generation_spec.planning_focus_summary`로 synthesis prompt에 들어간다
- 하지만 아직 orchestrator retry policy, researcher query expansion, executor branching priority를
  실제로 바꾸는 input은 아니다

## 7. Revised Priority Plan

### P0. truth surface stabilization

목표:

- acceptance truth와 regression promotion truth를 분리
- `promotion`과 `support_promotion`을 혼동하지 않게 한다

작업:

- dashboard/reviewer/operator surface에서 `support_promotion`를 primary support claim으로 승격
- `promotion_eligible`는 regression/pack surface로 명시

### P0.5. hidden default hardening

목표:

- unresolved stack/topology를 조용히 default로 닫지 않게 한다

작업:

- `stack_defaulted = true` lane을 dynamic/strict_dynamic에서 더 엄격히 다룸
- unresolved stack/topology는 `partial` 또는 `abstain` 규칙을 도입

### P0.75. readiness/blocker-driven planning

목표:

- 현재 prompt/contract level planning focus를 orchestrator/researcher/executor 우선순위와 연결

작업:

- `stack_defaulted` focus가 걸린 lane은 stack/runtime design retry slice 우선
- `family_disambiguation` / `evidence_authority` focus가 걸린 lane은 researcher query/evidence slice 우선
- `oracle_realism` focus가 걸린 lane은 oracle contract enrichment slice 우선
- `independent_verification` focus가 걸린 lane은 strict precondition/infra slice 우선

### P1. candidate IR controller

목표:

- single resolved id가 아니라 candidate-bearing control plane 확보

작업:

- `identifier_candidates[]`
- `family_candidates[]`
- `stack_candidates[]`
- `negative_hypotheses[]`
- candidate-level confidence/provenance/contradiction
- unresolved -> abstain / branch-preserved transition modeling

### P1.25. family induction + evidence authority upgrade

목표:

- fixed family hint universe 밖에서도 provisional family를 다룰 수 있게 함

작업:

- snippet claim extraction
- contradiction edge / weight
- provisional family cluster
- source authority weighting

### P1.5. staged synthesis

이번 문서의 변경점:

- staged synthesis를 더 이상 late polish로 두지 않는다
- current main bottleneck이므로 실제 우선순위를 앞으로 당긴다

권장 flow:

1. `request_ir`
2. `evidence_graph`
3. `design_brief`
4. `runtime_plan`
5. `oracle_contract`
6. `file_manifest`
7. deterministic materialization

### P2. runtime_graph / executor parity

목표:

- `runtime_graph`가 summary가 아니라 executor input이 되게 한다

우선 slice:

- `service + db`
- healthcheck/order/env/volume/target verifier contract 포함

### P2.5. oracle realism / verifier independence

목표:

- marker-only success를 줄이고 intent-faithful exploit contract로 이동

작업:

- negative control runner
- forbidden-success replay
- metamorphic runner
- richer operator-facing oracle narrative

### P3. support promotion loop

목표:

- dynamic run 일부를 curated support로 승격하는 closed loop 확보

필요:

- `support_promotion`을 실제 extraction pipeline과 연결
- runtime/oracle/fragment extraction
- human review point
- quality gate

### P4. family / stack expansion

원칙:

- current Python topology / oracle / executor parity를 먼저 안정화한다
- 그 다음 family/stack 수를 늘린다

## 8. Recommended Next Implementation Slice

다음 iteration의 실제 적용 범위는 아래가 적절하다.

1. `support_promotion`를 dashboard/reviewer/operator truth로 반영
2. `stack_defaulted` lane에 대한 dynamic/strict_dynamic gating 도입
3. `planning_focus_summary`를 orchestrator retry policy / researcher query budget / generator retry order와 연결
4. `request_ir@1` candidate authority를 generator/executor primary input까지 확장
5. `design_brief -> runtime_plan -> oracle_contract -> file_manifest` staged synthesis 첫 slice
6. `executor_plan@1` for `service + db`
7. negative/metamorphic oracle runner
8. support candidate extraction path 추가
9. query dedup/cache/reuse를 포함한 research performance slice 추가

## 9. Current Bottom Line

현재 vulDocker는 여전히 아래에 가깝다.

> "지원 family에 대한 정직한 regression platform, 그리고 일부 supported family에 대한 bounded dynamic degraded generator"

이번 iteration으로 실제로 좋아진 것은 다음이다.

- current unit/integration baseline이 `572 passed`로 올라왔고 official E2E는 same-day reference baseline(`51 passed`)으로 유지된다
- `promotion`과 generalized/open-world support claim을 `support_promotion`으로 분리했다
- degraded dynamic / lower-bound lane이 더 이상 support-ready bundle처럼 보이지 않게 됐다
- `stack_defaulted`가 추가되어 repo-prior/default stack boundedness가 직접 surface된다
- `planning_focus_summary`가 추가되어 blocker diagnosis가 prompt/contract와 summary에 직접 연결된다
- material candidate logic이 추가되어 strong resolution lane의 과민한 family ambiguity를 줄였다
- `open_redirect` minimal dynamic fallback이 explicit oracle contract를 싣고 `metamorphic_missing` blocker를 제거했다
- strong resolution lane에서 `request_ir.family_candidates` 자체의 researcher background noise를 줄였다
- canonicalized name-driven lane에서 raw `vuln_id` 재주입을 줄이고 `negative_hypotheses`를 researcher query/evidence graph까지 연결했다
- 문서가 오래된 수치/중복 서술 대신 current rerun + current code truth 기준으로 다시 정렬됐다

하지만 가장 중요한 구조적 한계는 그대로다.

- early-resolved control plane
- closed-vocabulary family hypothesis
- query-coupled evidence graph
- one-shot synthesis
- executor/runtime graph 불일치
- hidden default dependence
- degraded fallback 중심 dynamic closure
- support promotion loop 부재

따라서 다음 우선순위는 stack expansion이 아니라 아래 순서가 맞다.

> `truth surface -> hidden default hardening -> candidate IR/evidence authority -> staged synthesis -> runtime/executor parity -> oracle realism -> support promotion loop`
