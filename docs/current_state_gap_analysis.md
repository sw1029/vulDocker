# 동적 취약 Docker 생성 Current State / Gap Analysis

Status: canonical
Audience: mixed
Source of truth for: current rerun-backed truth, current completeness assessment, current structural gaps
Not the source of truth for: implementation priority, next slice, roadmap
Last validated against: current workspace-local `python -m pytest -q tests`, targeted regression slices, and workspace-local direct execution / repeatability / support workflow checks on 2026-03-19, with 2026-03-15 representative reruns retained as historical comparison

본 문서는 2026-03-15 KST 기준 workspace 재검토, 최신 코드 보완, representative rerun,
그리고 `name-only` 관점의 최신 control-plane truth에 2026-03-19 KST workspace-local direct execution delta를 덧붙인 **현상 진단 문서**다.

관련 문서:
- 문제 정의와 success criteria: [docs/problem.md](problem.md)
- 현재 제약과 금지 claim: [docs/constraints.md](constraints.md)
- 구현 우선순위와 계획: [docs/final_solution.md](final_solution.md)
- 작업 티켓 분해: [docs/work_tickets.md](work_tickets.md)
- 운영 절차: [docs/handbook.md](handbook.md)
- representative validation harness: [tests/e2e/README.md](../tests/e2e/README.md)

## Reader Routing

- 현재 baseline, direct rerun truth, current completeness assessment를 보려면 이 문서를 본다.
- “왜 이게 문제인지 / 성공 기준이 무엇인지”는 [docs/problem.md](problem.md)를 본다.
- “지금 무엇을 주장하면 안 되는지”는 [docs/constraints.md](constraints.md)를 본다.
- “다음에 무엇을 먼저 구현할지”는 [docs/final_solution.md](final_solution.md)를 본다.
- implementation-sized subtask와 owner는 [docs/work_tickets.md](work_tickets.md)를 본다.
- 실행 절차와 artifact reading은 [docs/handbook.md](handbook.md)를 본다.
- rerun command, case layout, measured/support harness detail은 [tests/e2e/README.md](../tests/e2e/README.md)를 본다.

## Validation Companions

이 문서의 “observed truth”를 재검증하거나 후속 구현 판단으로 넘길 때는 아래 문서를 같이 본다.

- success criteria 기준점은 [docs/problem.md](problem.md)
- 금지 claim과 current non-claim은 [docs/constraints.md](constraints.md)
- success criteria 5축과 backlog owner 대응은 [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Axis Map`
- completion companion set은 [docs/work_tickets.md](work_tickets.md)의 `Completion Companions`
- success criteria 5축의 완료판정 질문과 최소 근거는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Checklist`
- success criteria 5축의 canonical 완료 검토 순서는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Review Flow`
- success criteria 5축의 canonical 완료판정 reading order는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Reading Order`
- latest confirmed residual의 축별 ticket bundle 분해는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Residual Ticket Breakdown`
- latest confirmed residual의 canonical 구현 검토 순서는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Residual Review Flow`
- latest confirmed residual 검토 문서 순서는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Residual Reading Order`
- residual companion set은 [docs/work_tickets.md](work_tickets.md)의 `Residual Companions`
- review mode별 canonical 시작점은 [docs/work_tickets.md](work_tickets.md)의 `Review Mode Matrix`
- phase acceptance와 validation surface 대응은 [docs/final_solution.md](final_solution.md)의 `Acceptance-To-Validation Translation`
- implementation-sized owner와 검증 문서 읽는 순서는 [docs/work_tickets.md](work_tickets.md)의 `Validation Routing` / `Validation Reading Order`
- 질문 기반 검증 문서 routing은 [docs/work_tickets.md](work_tickets.md)의 `Validation Question Routing`
- 질문 기반 residual 문서 routing은 [docs/work_tickets.md](work_tickets.md)의 `Residual Question Routing`
- 실제 rerun/support harness command는 [tests/e2e/README.md](../tests/e2e/README.md)

## Completion Companions

이 문서의 observed truth를 완료판정 관점으로 넘길 때는 아래 문서를 같이 본다.

- completion companion set은 [docs/work_tickets.md](work_tickets.md)의 `Completion Companions`
- axis map / close criteria / canonical review order는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Axis Map`, `Open-World Completion Checklist`, `Open-World Completion Review Flow`
- canonical completion reading order는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Reading Order`
- phase acceptance map은 [docs/final_solution.md](final_solution.md)의 `Acceptance-To-Validation Translation`
- concrete rerun / support harness command는 [tests/e2e/README.md](../tests/e2e/README.md)
- current non-claim은 [docs/constraints.md](constraints.md)

## Review Mode Entry

이 문서를 보고 있을 때도, 현재 목적은 아래 셋 중 하나로 다시 좁혀서 본다.

- 검증:
  - [docs/work_tickets.md](work_tickets.md)의 `Review Mode Matrix`
  - 이 문서의 direct rerun delta / representative rerun truth
- 완료판정:
  - [docs/work_tickets.md](work_tickets.md)의 `Review Mode Matrix`
  - 이 문서의 `Completion Companions`
- 잔여 구현 검토:
  - [docs/work_tickets.md](work_tickets.md)의 `Review Mode Matrix`
  - [docs/work_tickets.md](work_tickets.md)의 `Residual Companions`

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
- workspace-local repeatability/support regressions와 no-Docker direct verification 한계를 추가 기록
- 오래된 수치/평가/계획을 하나로 병합하고 obsolete wording을 정리

## 1. Truth Protocol

- primary truth는 현재 workspace 코드와 이번 세션에서 직접 실행한 결과다.
- repo-tracked historical snapshot은 참고 자료일 뿐 current rerun보다 우선하지 않는다.
- current workspace-local head와 older canonical snapshot이 다르면 exact date와 exact baseline을 둘 다 적고, current truth 판정은 workspace-local direct verification을 우선한다.
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

### 2.1b 2026-03-19 workspace-local direct execution delta

이번 세션에서 다시 확인한 local delta는 아래와 같다.

| command | result | interpretation |
| --- | --- | --- |
| `python -m pytest -q tests` | `824 passed, 53 skipped, 1 warning in 3.57s` | current workspace-local head는 green baseline을 유지한다 |
| `python -m pytest -q tests/test_executor_poc_exec.py tests/test_contract_resolution.py` | `219 passed in 0.62s` | core contract/executor surface는 current workspace-local state에서도 안정적이다 |
| `python -m pytest -q tests/test_repeatability_gate.py tests/test_support_extract.py` | `28 passed in 0.21s` | repeatability/support helper/API regression slice와 matrix-unavailable handling까지 current workspace-local head에서 복구됐다 |
| `python -m pytest -q tests/e2e/test_support_workflow.py tests/e2e/test_case_matrix_rollup.py` | `7 passed in 0.19s` | support CLI regression과 matrix rollup surface 자체는 still runnable하다 |
| `python tests/e2e/run_case.py --case tests/e2e/cases/open-redirect-strict-dynamic-no-remote --mode deterministic --no-snapshot --output-dir /tmp/vuld_verify_strict_no_remote` | expectations satisfied | strict fail-closed honesty lane는 current workspace-local direct execution에서도 유지된다 |
| `python tests/e2e/run_case.py --case tests/e2e/cases/foobar-name-only-negative --mode deterministic --no-snapshot --output-dir /tmp/vuld_verify_foobar_negative` | expectations satisfied | unsupported free-form negative abstain lane도 current workspace-local direct execution에서 유지된다 |
| `python tests/e2e/repeat_case.py --case tests/e2e/cases/foobar-name-only-negative --attempts 2 --mode deterministic --output-dir /tmp/vuld_repeat_foobar_negative` | report written, `passed=true` | no-Docker planning-only lane의 repeatability CLI path는 current workspace-local state에서도 동작한다 |
| `python tests/e2e/repeat_case.py --case tests/e2e/cases/open-redirect-strict-dynamic-no-remote --attempts 2 --mode deterministic --output-dir /tmp/vuld_repeat_strict_no_remote` | report written, `passed=true` | strict no-remote planning-only lane의 repeatability CLI path도 current workspace-local state에서 동작한다 |
| `python tests/e2e/repeat_case.py --case tests/e2e/cases/foobar-name-only-negative --attempts 2 --mode deterministic --output-dir /tmp/vuld_repeat_foobar_negative_after_fix` | report written, `case`와 `case_name` 모두 populated | repeatability report top-level case key parity가 current workspace-local head에서 복구됐다 |
| `python tests/e2e/support_review.py ...`, `support_decide.py ...`, `support_apply.py ...` | blocked/no-op workflow completed | measured/manual support no-op chain은 current workspace-local state에서도 false promotion 없이 유지된다 |
| `python tests/e2e/support_apply.py --registry-update /tmp/vuld_empty_registry_update.json --registry /tmp/vuld_legacy_registry.json --output /tmp/vuld_legacy_registry_out_after_fix.json` | `schema_status = legacy_decisions_present` and `last_update.schema_status = legacy_decisions_present` | legacy decision-only registry의 direct API / written artifact parity가 current workspace-local head에서 정렬됐다 |
| `python tests/e2e/run_case.py --case tests/e2e/cases/open-redirect-dynamic-name-only --mode deterministic --no-snapshot --output-dir /tmp/vuld_verify_open_redirect_dynamic` | `docker daemon is not reachable` | 이번 세션 환경에서는 Docker-executed representative lane을 재검증할 수 없었고, runnable dynamic/runtime artifact에 대한 fresh direct claim은 제한된다 |
| `docker ps` | `docker` command not found in current WSL 2 distro | 이번 세션 환경에서는 Docker daemon reachability 이전에 WSL integration/binary availability 자체가 direct runtime verification blocker다 |

의미:

- current workspace-local state는 canonical 2026-03-15 snapshot보다 더 많은 테스트 자산을 포함하고, same workspace head는 now green baseline으로 다시 복구됐다.
- direct CLI path와 helper/API surface를 분리해서 읽어야 한다.
- fail-closed / abstain / blocked no-op support workflow는 직접 실행으로 다시 확인됐고, same session에서 repeatability/support helper/API contract drift도 current workspace-local head에서 복구됐다.
- latest recheck 기준 planning-only repeatability lane(`foobar-name-only-negative`, `open-redirect-strict-dynamic-no-remote`)는 둘 다 `measured_gate.ready=false`와 blocker `cache_reuse_inconsistent`, `artifact_quality_band_not_high`, `oracle_execution_parity_not_high`를 남겼다. 즉 repeatability CLI는 정상 동작하지만 measured promotion gate는 의도대로 닫혀 있다.
- same recheck 기준 strict no-remote lane는 `name_only_outcome.decision=fail_closed`, `open_world_class=name_driven_capability_gate_failed`, `qualitative_tier=planning_only`로 다시 확인됐다. unsupported negative lane는 `decision=abstain`, `open_world_class=unsupported_free_form_negative`, `qualitative_tier=planning_only`로 다시 확인됐다.
- same recheck 기준 blocked support workflow는 `support_review_index.json`에서 `by_support_status={\"blocked_mixed\":2}`, `by_case_status={\"all_blocked\":2}`를 남기고, final local registry는 `registry_item_count=0`, `schema_status=normalized`, `by_review_status={}`, `by_support_status={}`, `by_case_review_status={}` no-op로 끝났다.
- undeclared case의 repeatability fallback matrix report도 now `matrix_gate:unavailable` reason과 함께 정직하게 surface된다.
- same rererun slice는 기존 product residual을 재확인했을 뿐, `TKT-008-A*`, `TKT-009-A2` 밖의 새 implementation backlog item은 만들지 않았다. positive representative dynamic lane 미검증은 여전히 local Docker prerequisite 문제로 분리해 읽는다.

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

약점:

- `2026-03-19` workspace-local direct verification에서는 full `pytest` baseline은 회복됐지만, representative Docker-executed lane을 이번 세션에서 fresh rerun으로 다시 확인하지는 못했다
- 따라서 current workspace-local head를 regression-green이라고는 말할 수 있어도, same session에서 runtime-executed representative quality까지 모두 재검증했다고 과장하면 안 된다

평가:

- canonical rerun-backed baseline: `8.6/10`
- current workspace-local head: `8.6/10`

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
  - representative direct rerun 기준으로도 `open_world_ready = false`다
  - same lane은 `artifact_quality.band = high`, `artifact_quality.qualitative_tier = bounded_sidecar_parity_success`까지 올라갈 수 있다
  - 즉 current bounded compiler/native lane에서는 `intent_met`가 곧 generalized open-world/support readiness를 뜻하지는 않는다
  - curated lower-bound regression success

- `open-redirect-dynamic-name-only`
  - `deterministic_fallback`
  - `open_world_class = semantic_guided_minimal_dynamic`
  - `name_only_outcome = partial`
  - `support_promotion = false`
  - direct rerun에서도 `fully_validated = true`이지만 `open_world_ready = false`
  - `artifact_quality.band = medium`
  - latest direct rerun에서는 runnable negative/metamorphic replay가 붙어 `oracle_execution_parity = high`, `oracle_execution_attempted = true`까지 올라갔다
  - 실제 산출물은 여전히 thin single-route fallback demo에 가깝다
  - 그러나 여전히 `single_service` / semantic-guided bounded fallback lane이다

- representative stateless minimal_dynamic fallback reruns
  - `template-injection-dynamic-name-only`
  - `path-traversal-dynamic-name-only`
  - `ssrf-dynamic-name-only`
  - `deserialization-dynamic-name-only`
  - `xxe-dynamic-name-only`
  - `csrf-dynamic-name-only`
  - latest direct rerun 기준으로 여섯 lane 모두 `oracle_execution_parity = high`, `oracle_execution_attempted = true`까지 올라간다
  - 그래도 `name_only_outcome = partial`, `open_world_ready = false`, `artifact_quality.band = medium`은 그대로다
  - latest slice 후 same lane들은 `artifact_quality.qualitative_tier = thin_fallback_demo`로 surface되어, executed oracle closure와 thin fallback demo 성격이 분리되어 읽힌다
  - 정성평가로는 “재현성과 honesty는 좋지만, 구조적으로는 still thin demo artifact”에 가깝다
  - 즉 deterministic fallback lane 일부는 executed oracle closure를 달성할 수 있지만, 이것이 open-world success나 broader multi-step/browser stateful realism closure를 뜻하지는 않는다

- `csrf-dynamic-name-only`
  - `deterministic_fallback`
  - `run_passed = true`, `verify_pass = true`
  - latest direct rerun 기준으로도 `oracle_execution_parity = high`, `oracle_execution_attempted = true`까지 올라갔다
  - current generated lane는 cookie/session single-flow CSRF replay까지는 닫혔지만, 이것이 broader browserful stateful oracle closure를 뜻하지는 않는다
  - 산출물은 state-changing session flow를 보이지만 여전히 bounded fallback이라 quality band는 `medium`이다

- `open-redirect-strict-dynamic-no-remote`
  - `capability_gate_rejected`
  - `fail_closed`
  - `artifact_quality.qualitative_tier = planning_only`
  - direct rerun에서는 `stage_ceiling = pre_generation`
  - latest direct rerun에서는 top-level `run_passed = false`, `verify_pass = null`, `oracle_execution_parity = missing`, `oracle_execution_attempted = false`도 같이 정렬된다
  - `search_cache_hit_count = 0`, `search_cache_miss_count = 0`
  - `search_planned_query_count = 0`, `search_executed_query_count = 0`
  - `search_early_stop_triggered = false`
  - remote provider가 없으면 RESEARCH 이전 capability precheck에서 멈춘다
  - latest direct rerun에서는 top-level `terminal_failure_class`와 nested `name_only_outcome.terminal_failure_class`가 모두 `strict_dynamic_remote_research_unavailable`로 정렬된다
  - latest direct rerun에서는 same top-level `bundle_verdict_rollup`도 `by_stage_ceiling = {pre_generation: 1}`, `by_terminal_failure_class = {strict_dynamic_remote_research_unavailable: 1}`로 정렬된다
  - 즉 same lane은 runnable artifact quality tier가 아니라 planning-only honesty surface로 읽어야 한다
  - `support_promotion = false`

- `sqli-sidecar-compiler-custom-env`
  - `compiler_generated`
  - `service_plus_sidecar`
  - `run_passed = true`, `verify_pass = true`
  - `artifact_quality.band = high`
  - custom DB env와 sidecar alias는 representative direct run에서도 정렬된 채 유지된다
  - latest direct rerun 기준 top-level `runtime_service_env`도 `DB_USER = custom_user`, `DB_PASSWORD = custom_pw`, `DB_NAME = runtime_db_custom`를 그대로 유지해, 최근 bounded self-consistency hardening 이후에도 custom runtime binding이 깨지지 않았다
  - latest direct rerun에서는 `schema.sql`, `seed_files = ['schema.sql']`, `seed_strategy = sidecar_sql_apply`, `seed_apply_completed = true`까지 확인됐다
  - latest direct rerun에서는 executable compiler oracle replay가 정상 동작해 `oracle_execution_parity = high`, `oracle_execution_attempted = true`까지 올라갔다
  - latest slice 후 same lane은 `artifact_quality.qualitative_tier = bounded_sidecar_parity_success`로 surface되어, thin fallback demo보다 한 단계 높은 bounded sidecar/runtime artifact로 읽힌다
  - current representative direct execution 기준으로는 레포 내 가장 높은 품질의 bounded artifact class에 가깝다
  - 즉 compiler/native bounded lane은 thin fallback demo보다 한 단계 높은 실습 품질을 보인다
  - 다만 이것도 compiler/native bounded lane의 개선이지 generalized oracle closure를 뜻하지는 않는다

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
- strong semantic signature가 known family primitive와 맞을 때 `primitive_signature` source provisional family를 세우는 partial path는 생겼다
- 하지만 이것도 bounded known-family induction일 뿐, unknown family를 truly open-vocabulary로 세우는 path는 아직 없다

### 6.4 evidence graph는 덜 noisy해졌지만 아직 causal authority graph는 아니다

- query-seeded support edge는 줄었지만,
  current support edge는 여전히 substring/marker match에 크게 의존한다
- snippet claim extraction / source authority weighting / contradiction weighting이 아직 약하다
- 지금의 `support_count`는 "선택된 후보를 지지하는 evidence node 수"이지 causal sufficiency를 보장하는 score는 아니다

### 6.5 stack selection은 개선됐지만 아직 narrow하다

- current stack pool 자체가 `python/flask`, `python/fastapi` 중심이다
- margin policy는 들어갔지만, multi-runtime / multi-service / non-Python lane까지 일반화되지는 않았다

### 6.6 executor plan은 생겼지만 parity는 아직 얕다

- `executor_plan@0.1`은 이제 `service_port`, `base_url`, `service_env`, `healthchecks`, `sidecars`, `topology`, `requires_external_db`와 일부 primitive-derived runtime provenance까지 executor-facing surface에 싣기 시작했다
- executor는 declared `healthchecks`/`health_path`, resolved sidecar `env`/`aliases`/`ready_probe`, `db`/`runtime_dependency_hypotheses` 기반 external DB hint, `seed_files` 존재 여부, `env_contract` key/value drift, `generator_manifest.metadata.target_db/target_sidecars/target_topology` fallback hint를 실제 실행 판단에 일부 반영한다
- `mysql/mariadb/postgres/postgresql` target에 대해서는 metadata hint만으로 bounded default sidecar plan synthesis까지 들어오기 시작했다
- 같은 bounded hint에서 `service_env` defaults도 일부 합성되기 시작했고, sqlite lane에서는 minimal seed/init signal 검증도 들어왔다
- external mysql/postgres sidecar가 있고 declared `.sql` seed file이 있을 때는 executor가 workspace를 read-only mount해 readiness 이후 listed SQL seed를 bounded actual apply할 수도 있게 됐다
- 하지만 dependency order / generalized seed-init DSL / richer env-volume contract semantics / generalized sidecar-runtime surface synthesis / 일부 network lifecycle은 아직 policy/runtime recipe fallback에 더 의존한다

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

### 6.10 performance reuse는 생겼지만 measurement closure는 아직 partial이다

- representative rerun에서 RESEARCH가 여전히 가장 느린 구간인 건 맞다
- 다만 query dedup에 더해 repo-local search cache와 conservative early stop, repeatability/cache observation surface는 이미 들어왔다
- 아직 snippet/evidence graph reuse와 representative lane별 perf comparison, stronger CI-level performance gate는 부족하다

### 6.11 support promotion loop is still missing

- repeatability-aware measured case에서는 `support_candidate.json`, `support_review_index.json`, `support_registry_update.json` preview artifact를 추출할 수 있게 됐고, latest slice에서는 same preview를 `curated_support_registry.json` local write/merge workflow로 적용할 수도 있게 됐지만,
  이것은 아직 E2E harness 기반 measured/manual review surface다
- `support_promotion`은 PACK inside honesty surface로 남아 있고, dynamic success에서 extracted candidate를 curated support registry로 자동 반영하는 닫힌 승격 루프는 아직 없다

### 6.12 open-world eval matrix는 생겼지만 harness-scoped measurement에 머문다

- `tests/e2e/case_matrix.json`과 `matrix_report.json`으로 `paraphrase`, `broad phrase`, `unknown family`, `misleading stack evidence`, `multi-service required`, `negative family conflict` 같은 bucket을 태깅하고 rollup할 수 있게 됐다
- repeatability runner도 matrix axes와 cache observation을 같이 남긴다
- latest slice에서는 `repeatability_report.json`도 `observed_artifact_quality_bands`, `observed_qualitative_tiers`, `quality_tier_consistent`를 surface하고, `matrix_report.json`도 `quality_observations.by_band/by_qualitative_tier/oracle_high_nonhigh_band_cases`를 집계하기 시작했다
- 즉 representative measured artifacts에서도 `bounded_sidecar_parity_success`와 `thin_fallback_demo`가 구분돼 읽히기 시작했다
- 하지만 이 matrix는 아직 E2E harness layer의 measurement artifact이고, pipeline-level capability claim을 자동 승격하는 authoritative gate는 아니다

### 6.12b summary surface consistency still has residual scope

- representative `strict no-remote` direct rerun 기준 `terminal_failure_class` top-level sync 문제는 latest slice로 해결됐다
- same capability-gate lane의 `search_*` performance fields도 latest slice로 `0/false` default로 정렬됐다
- latest slice에서는 same single-bundle top-level summary가 `run_passed`, `verify_pass`, `oracle_execution_parity`, `oracle_execution_attempted`도 bundle truth를 fallback으로 읽기 시작해, representative direct run에서 convenience projection이 verdict를 비우는 known drift는 줄었다
- latest direct rerun 기준 representative executed single-bundle lane(`sqli-sidecar-compiler-custom-env`, `template-injection-dynamic-name-only`, `csrf-dynamic-name-only`)는 top-level과 bundle-level이 모두 `run_passed/verify_pass/oracle_execution_parity`에서 정렬된다
- latest slice에서는 same multi-bundle top-level manifest/summary도 `bundle_verdict_rollup`를 싣기 시작해, `run_passed/verify_pass/oracle_execution_parity/qualitative_tier` 분포뿐 아니라 `by_stage_ceiling`/`by_terminal_failure_class`도 `bundles[]`를 열지 않고 읽을 수 있게 됐다
- latest slice에서는 same multi-bundle lane가 uniform `planning_only`/pre-generation verdict를 가질 때 top-level도 `run_passed=false`, `verify_pass=null`, `stage_ceiling=pre_generation`, `terminal_failure_class`, `oracle_execution_parity=missing`, `oracle_execution_attempted=false`를 직접 싣기 시작했다
- latest slice에서는 same mixed multi-bundle lane도 top-level `run_passed_rollup`, `verify_pass_rollup`, `stage_ceiling_rollup`, `terminal_failure_class_rollup`, `oracle_execution_parity_rollup`, `oracle_execution_attempted_rollup`로 verdict/failure 상태를 직접 요약하기 시작했다
- latest slice에서는 same top-level `verdict_authority`도 들어와, `run_passed/verify_pass/stage_ceiling/terminal_failure_class/oracle_execution_*`가 convenience projection인지 bundle truth canonical input인지 explicit하게 읽을 수 있게 됐다
- latest slice에서는 same `repeatability_report.json`와 `matrix_report.json`도 `verdict_authority` observation을 담기 시작해, measured gate 쪽에서도 projection mode와 canonical precedence를 더 직접 읽을 수 있게 됐다
- latest slice에서는 same `repeatability_report.json`가 `measured_gate = {ready, blockers}` preview를 담기 시작했고, `matrix_report.json`도 `measured_gate_observations`를 집계하며, support extraction도 이를 `measured_gate:*` external blocker로 읽기 시작했다
- latest slice에서는 same `support_candidate.json`와 `support_review_index.json`도 `verdict_authority` handoff를 읽기 시작해, manual review/workflow 쪽에서도 measured precedence context를 더 직접 볼 수 있게 됐다
- latest slice에서는 same support workflow가 `verdict_authority:missing` / `verdict_authority:inconsistent`를 external blocker로도 읽기 시작해, measured precedence drift가 reviewable package에 그대로 섞이지 않게 됐다
- latest slice에서는 same `support_review_index.json`도 `authority_ready_bundle_count`, `authority_blocked_bundle_count`, `by_authority_blocker`를 집계하기 시작해, review queue 수준에서도 authority blocker 분포를 직접 볼 수 있게 됐다
- latest slice에서는 same `support_review_index.json`와 `support_registry_update.json` preview도 `measured_gate_ready_bundle_count`, `measured_gate_blocked_bundle_count`, `by_measured_gate_blocker`를 보존하기 시작해, measured gate blocker 분포도 review/update aggregate에서 직접 읽을 수 있게 됐다
- latest slice에서는 same `support_registry_update.json` preview도 authority aggregate와 authority-mode breakdown을 같이 보존하기 시작해, accept/reject/pending preview에서도 authority context가 덜 사라진다
- latest slice에서는 same `support_registry_update.json` preview를 actual `curated_support_registry.json` local write/merge workflow로 적용할 수 있게 됐고, accepted entry upsert와 reject decision history도 남기기 시작했다
- latest slice에서는 same local registry도 `update_history`, `by_decision`, `by_reviewer`를 보존하기 시작했고, same case/slug의 obvious family/stack/topology drift는 merge conflict로 reject하기 시작했다
- latest slice에서는 same existing registry item에 대한 reject decision도 item-level `history`, `last_decision`, `rejected_count`로 반영되기 시작해, accept-only history보다 실제 review history에 조금 더 가까워졌다
- latest slice에서는 same previously rejected item이 later accept될 때도 `rejected_count`와 prior history를 잃지 않도록 preserve되기 시작해, history lifecycle이 단순 overwrite보다 조금 더 안정화됐다
- latest slice에서는 same sparse accepted/rejected update도 prior `source_artifacts`는 유지하면서 current support-status split은 reviewable semantics로 채우기 시작해, provenance retention과 current decision interpretation이 덜 충돌하게 됐다
- latest slice에서는 same sparse older local registry item도 `history`와 last event를 읽어 `accepted_count` / `rejected_count` / `review_status` / `support_status` / `last_decision` / `source_artifacts`를 current schema로 backfill하기 시작했고, top-level `schema_upgraded_item_count`와 `by_schema_upgrade_reason`, item-level `schema_upgrade_reasons`로 same bounded schema evolution이 surface에 직접 드러나기 시작했다
- latest slice에서는 same sparse older `update_history` entry도 current update schema로 normalize되기 시작했고, top-level `schema_upgraded_update_count`와 `by_update_schema_upgrade_reason`로 same lifecycle upgrade가 local registry surface에 직접 드러나기 시작했다
- latest slice에서는 same sparse older `decision_history` event도 current decision schema로 normalize되기 시작했고, top-level `schema_upgraded_decision_event_count`와 `by_decision_schema_upgrade_reason`로 same lifecycle upgrade가 local registry surface에 직접 드러나기 시작했다
- latest slice에서는 same local registry maintenance 상태도 top-level `schema_status` token으로 `normalized`, `legacy_items_present`, `legacy_updates_present`, `legacy_decisions_present`, `legacy_mixed_present` 중 하나로 바로 읽을 수 있게 됐다
- latest slice에서는 same item/update/decision record 자체도 `schema_status=normalized|legacy_upgraded`를 직접 가지기 시작해, nested record를 열었을 때도 same maintenance 상태를 바로 읽을 수 있게 됐다
- latest slice에서는 same local registry item도 `review_status`를 직접 갖고, top-level `by_review_status` aggregate도 생겨 현재 accepted/rejected state를 더 바로 읽을 수 있게 됐다
- latest slice에서는 same local registry item도 latest `source_artifacts`를 직접 보존하고, top-level `items_with_source_artifacts_count`도 생겨 현재 상태가 어떤 artifact trace에서 왔는지 더 바로 읽을 수 있게 됐다
- latest direct verification에서는 representative `sqli-sidecar-compiler-custom-env` repeatability/support workflow도 실제로 확인했다. same lane의 `repeatability_report.json`는 `passed=true`였지만 `measured_gate.ready=false`와 blocker `cache_reuse_inconsistent`를 남겼고, resulting `support_candidate.json` / `support_review_index.json`도 `strict_open_world:strict_curated_lower_bound`, `open_world:catalog_resolved_lower_bound`, `oracle_clarity:medium`, `family_evidence:candidate_unbacked`, `measured_gate:cache_reuse_inconsistent` 때문에 reviewable로 승격되지 않았다
- same representative rerun에서는 `support_review_index.json`가 `by_support_status={"blocked_mixed":1}`를, `by_mechanical_blocker={"measured_gate:cache_reuse_inconsistent":1}`를, `by_promotion_policy_blocker={"strict_open_world:strict_curated_lower_bound":1,"open_world:catalog_resolved_lower_bound":1,"oracle_clarity:medium":1,"family_evidence:candidate_unbacked":1}`를 남겨, mixed mechanical/policy blocked state가 aggregate에서도 실제로 분리된다는 점을 확인했다
- latest slice에서는 same `support_review_index.json`가 `by_case_status`와 per-case `case_statuses[]`도 같이 남기기 시작해, operator가 case 단위로 `all_reviewable`, `mixed_reviewability`, `all_blocked` 상태와 support-status/blocker 분포를 한 화면에서 읽을 수 있게 됐다
- latest slice에서는 same `support_review.py` / `support_decide.py` CLI output도 `all_reviewable_cases` / `mixed_cases` / `all_blocked_cases`를 같이 노출하기 시작해, operator가 preview JSON을 열지 않아도 case list를 바로 읽을 수 있게 됐다
- same direct verification에서는 empty reviewer decision을 적용한 `support_registry_update.json -> curated_support_registry.json` local apply chain도 실제로 실행했고, false promotion 없이 `registry_item_count=0` no-op local registry로 끝나는 것을 확인했다
- same no-op apply chain에서는 `accepted/rejected/pending_by_support_status={}`와 empty local registry `by_support_status={}`도 함께 남아, false promotion 없이 empty status aggregate로 끝나는 것도 확인했다
- latest slice에서는 same `support_review.py -> support_decide.py -> support_apply.py` chain도 synthetic reviewable candidate와 blocked candidate로 regression이 생겼고, reviewable accept path는 non-empty local registry를, blocked no-op path는 empty local registry를 각각 materialize하는 것이 자동 검증되기 시작했다
- latest slice에서는 same support workflow도 blocker를 `mechanical_blockers`와 `promotion_policy_blockers`로 나눠 surface하기 시작했고, candidate-level `mechanically_healthy` / `promotion_policy_ready`와 review/update aggregate의 `mechanically_*` / `promotion_policy_*` count 및 `by_mechanical_blocker` / `by_promotion_policy_blocker`도 같이 읽을 수 있게 됐다
- latest slice에서는 same support workflow도 `support_status` / `by_support_status`를 같이 surface하기 시작해, `reviewable`, `mechanically_blocked`, `mechanically_healthy_policy_blocked`, `blocked_mixed` 같은 current promotion state를 더 직접 읽을 수 있게 됐다
- latest slice에서는 same support workflow가 case-level aggregate도 같이 surface해, bundle-level token만 보지 않고 case-level reviewability 상태까지 top-level에서 읽을 수 있게 됐다
- latest slice에서는 same `support_registry_update.json` preview와 `support_decide.py` CLI output도 `by_case_status`를 같이 보존하기 시작해, review decision preview에서도 case-level 상태 맥락이 사라지지 않게 됐다
- latest slice에서는 same local registry `last_update`도 review/update 단계의 `reviewable_case_count` / `blocked_case_count` / `by_case_status` / `case_statuses[]`를 같이 보존하기 시작해, latest apply context를 case-level 상태까지 포함해 읽을 수 있게 됐다
- latest slice에서는 same `curated_support_registry.json` local registry도 item-level `support_status`, `mechanically_healthy`, `promotion_policy_ready`와 top-level `by_support_status`, `mechanically_*_item_count`, `promotion_policy_*_item_count`를 보존하기 시작해, support interpretation surface가 local registry 끝단까지 더 일관되게 이어지기 시작했다
- latest slice에서는 same local registry top-level current state도 `by_case_review_status` / `case_review_statuses[]`를 같이 보존하기 시작해, stored accepted/rejected item set을 case 단위 `all_accepted`, `mixed_review_status`, `all_rejected` 상태로도 직접 읽을 수 있게 됐다
- latest slice에서는 same `support_apply.py` CLI output도 `all_accepted_cases` / `mixed_review_status_cases` / `all_rejected_cases`를 같이 노출하기 시작해, local registry current state를 CLI stdout만으로도 case 단위까지 읽기 쉬워졌다
- latest slice에서는 same `last_update`도 explicit case count/list(`all_reviewable_case_count`, `mixed_case_count`, `all_blocked_case_count`, `all_reviewable_cases`, `mixed_cases`, `all_blocked_cases`)를 같이 보존하기 시작해, latest apply context를 aggregate와 explicit case list 양쪽으로 읽을 수 있게 됐다
- latest slice에서는 same local registry `last_update` / `update_history`도 same support-status split과 mechanical-policy aggregate를 보존하기 시작해, current registry state뿐 아니라 latest apply context도 같은 해석 surface로 읽을 수 있게 됐다
- latest slice에서는 same `support_registry_update.json` preview와 local registry `last_update`도 `accepted/rejected/pending_by_support_status`를 같이 보존하기 시작해, decision outcome breakdown도 same support-status token으로 직접 읽을 수 있게 됐다
- operational backlog 기준으로 보면, same residual은 `TKT-008-A1`의 blocker policy split과 `TKT-009-A1`의 representative reviewable accept-path verification으로 나눠 추적하는 편이 현재 상태를 더 정확히 설명한다
- latest slice에서는 same `run_case` / `repeat_case`가 output-dir/attempt 기반 SID salt를 쓰기 시작해, same-case direct run을 병렬로 돌릴 때 artifact contention으로 인한 false regression을 덜 만들게 됐다
- latest slice에서는 same `summary.json`와 `repeatability_report.json`도 `execution_salt` / `observed_execution_salts` / `distinct_sid_count`를 노출하기 시작해, harness isolation이 실제로 어떤 SID 분리를 만들었는지 더 직접 읽을 수 있게 됐다
- current remaining residual은 uniform `planning_only`/pre-generation lane 자체라기보다, mixed multi-bundle convenience projection과 broader authoritative gate 부재가 nested truth 전체를 완전히 대체하지는 못한다는 점에 더 가깝다
- operational backlog 기준으로는 same residual을 `TKT-008-B1 mixed multi-bundle projection consistency`와 `TKT-008-B2 authoritative measured-gate handoff`로 나눠 추적하는 편이 현재 상태를 더 정확히 설명한다
- 다만 현재 summary surface는 여전히 operator-facing top-level projection과 nested truth surface가 항상 완전히 동기화된다고 가정하면 안 된다
- 즉 특정 known drift는 더 줄었지만, broader summary consistency는 여전히 Phase 5B measurement/observability closure에 포함되어야 하는 잔여다

### 6.12c latest workspace-local repeatability / support stabilization closure

- `2026-03-19` workspace-local direct verification 기준으로 확인됐던 repeatability/support helper/API drift는 current workspace-local head에서 복구됐다
- current verification 결과:
  - `python -m pytest -q tests/test_repeatability_gate.py tests/test_support_extract.py` -> `28 passed`
  - `python -m pytest -q tests/e2e/test_support_workflow.py tests/e2e/test_case_matrix_rollup.py` -> `7 passed`
  - `python -m pytest -q tests` -> `824 passed, 53 skipped`
- closed drift는 아래와 같다
  - `summarize_repeat_attempt(...)` helper call shape가 backward-compatible하게 다시 정렬됐다
  - `_write_plan(..., sid_salt=...)` 도입 이후 older stub/test double path도 compatibility seam으로 다시 정렬됐다
  - `aggregate_repeat_results(...)`가 top-level `case`와 `case_name`를 함께 남겨 repeatability report key parity가 복구됐다
  - undeclared case fallback matrix report는 now `matrix_unavailable_reason`와 support gate의 `matrix_gate:unavailable`를 통해 `not_covered`와 구분돼 읽힌다
  - `build_curated_support_registry(...)` direct return과 `support_apply.py`가 write한 final artifact가 legacy decision-only registry에서도 `schema_status` truth를 같이 보이도록 정렬됐다
- direct CLI path도 계속 정상이다
  - `repeat_case.py`는 no-Docker planning-only lane에서 `repeatability_report.json`를 정상 생성하고 `case_name`까지 같이 남긴다
  - `support_review.py -> support_decide.py -> support_apply.py` blocked/no-op chain도 false promotion 없이 정상 종료된다
- 따라서 same slice의 current residual은 helper/API contract drift 자체보다, broader authoritative measured gate와 actual measured accept-path closure가 아직 남아 있다는 쪽으로 다시 좁혀진다
- operational backlog 기준으로는 same closure를 아래 bounded stabilization 항목이 흡수했다
  - `TKT-008-B3-A` repeat helper backward-compat arguments
  - `TKT-008-B3-B` plan writer `sid_salt` compatibility seam
  - `TKT-008-B3-C` repeatability report top-level case key parity
  - `TKT-009-B3-A` legacy decision-only schema-status parity
  - `TKT-009-B3-B` direct API vs written artifact parity

### 6.13 primitive-level runtime design control plane이 아직 없다

- semantic signature와 family-aware fallback은 있지만,
  `primitive -> dependency -> topology -> oracle`를 먼저 세우는 controller는 아직 없다
- latest slice로 `semantic_signature -> primitive_hypotheses -> provisional_family`까지는 더 직접 연결됐지만,
  `sql_injection`류에는 low-confidence `db:sqlite` dependency hint가 scenario planning까지 이어지기 시작했다
- staged runtime plan도 이 hint를 `db/topology`와 source 형태로 읽기 시작했지만, 여전히 executor/runtime materialization의 primary input이 된 것은 아니다
- selected known family에는 low-confidence `oracle_hypotheses`도 추가돼 `scenario_candidates.oracle_profile`, `name_only_generation_spec`, `staged_synthesis.oracle_contract`까지 내려가지만, 이것은 working oracle shape를 보강하는 bounded hint일 뿐이다
- scenario selection과 candidate resolution도 이제 `selected_oracle_mode`/`selected_oracle_source`를 surface하지만, 이것이 oracle branch를 primary controller로 만들었다고 보긴 어렵다
- `design_brief`도 `selected_topology`, `selected_oracle_mode`, `dependency_set`, derived `required_roles`를 싣기 시작했지만, 아직 이것이 generator materialization branch를 fully rewire하는 수준은 아니다
- 다만 latest slice로 `design_brief.required_roles`가 recovery dispatch에는 연결돼, `design_brief` 실패에서도 dependency-heavy brief는 `runtime_plan`, oracle-heavy brief는 `oracle_contract` repair를 우선 시도할 수 있게 됐다
- `runtime_plan` repair도 thin runtime plan일 때 `design_brief`의 `selected_topology`/`dependency_set`을 fallback target으로 읽어 `target_topology`/`target_db`/`target_sidecars` metadata를 복구할 수 있게 됐지만, 이것 역시 metadata-level 정렬이지 executor control plane 재배선은 아니다
- latest slice에서 `design_brief.required_roles`는 fresh candidate guard에도 연결돼 `dependency_db`/`dependency_sidecar` 부재를 조기 runtime violation으로 올릴 수 있게 됐지만, 여전히 heuristic signal check이며 full runtime planner는 아니다
- same `design_brief.required_roles`는 semantic-guided fallback family selection에도 제한적으로 연결돼, semantic candidate가 비어 있어도 `dependency_db + db target`이 분명한 brief는 bounded `sqli` fallback으로 흘릴 수 있게 됐다
- latest slice에서는 semantic signature가 비어 있어도 researcher `top_family/high/non-ambiguous`가 충분히 강하면 bounded minimal_dynamic fallback으로 salvage할 수 있는 경로가 생겼다
- 다만 이것 역시 `researcher_top_family_no_semantic_signature` source의 bounded fallback salvage일 뿐, primitive-first materialization이나 open-vocabulary discovery를 뜻하지는 않는다
- latest slice에서는 generic unsupported fallback과 semantic-guided fallback도 `design_brief`의 `target_topology`/`target_db`/`target_sidecars`/`selected_oracle_mode` metadata를 같이 싣기 시작했지만, 이것 역시 fallback manifest metadata 정렬이지 materialization branch 자체를 primitive-first로 바꾼 것은 아니다
- latest slice에서는 bounded `sqli` minimal dynamic fallback이 `design_brief`의 `db:mysql/postgres` target을 실제 service code, requirements, `run.env`까지 반영할 수 있게 됐지만, 이것 역시 SQLi family에 한정된 bounded external DB variant일 뿐 generalized runtime synthesis는 아니다
- same bounded SQLi external DB fallback은 `schema.sql`도 실제로 내보내기 시작해서 contract/executor seed chain과 더 직접 연결되지만, 이것 역시 SQLi lane의 bounded seed surface일 뿐 generalized init planning은 아니다
- same bounded SQLi external DB fallback service code도 이제 그 `schema.sql`을 직접 읽어 init하도록 맞춰지기 시작했지만, 이 역시 bounded lane 내부의 drift 감소일 뿐 generalized init/runtime synthesis는 아니다
- latest slice로 일부 mysql/postgres lane에서는 `generator_manifest.metadata.target_db/target_sidecars/target_topology`와 `run.env`만으로도 contract 단계가 bounded sidecar plan을 `runtime_recipe/runtime_graph/executor_plan`까지 합성하기 시작했지만, 이것 역시 bounded target-hint synthesis일 뿐 generalized topology/runtime planner는 아니다
- same bounded contract-stage synthesis는 `service_env`도 `DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME/APP_PORT` 수준까지 채우고 top-level contract surface를 다시 정렬하기 시작했지만, 이것 역시 bounded env-default synthesis일 뿐 generalized runtime planner는 아니다
- latest slice에서는 same bounded synthesis provenance(`generator_manifest.metadata.target_sidecars`, `runtime_hint_sidecar_defaults`)도 executor-facing surface까지 유지되기 시작했지만, 이것 역시 provenance parity 개선일 뿐 generalized control-plane closure는 아니다
- latest slice에서는 same bounded mysql/postgres lane가 `network_enabled=true`, `network_mode=bridge`와 explicit network cap provenance까지 contract 단계에서 싣기 시작했지만, 이것 역시 bounded network requirement synthesis일 뿐 generalized network lifecycle closure는 아니다
- same bounded network provenance는 이제 executor execution surface와 bundle summary까지 roundtrip되기 시작했지만, 이것 역시 provenance parity 강화일 뿐 generalized network lifecycle closure는 아니다
- latest slice에서는 same bounded sidecar lane의 `sidecar_start_order`도 contract와 executor summary까지 roundtrip되기 시작했지만, 이것 역시 bounded ordering parity일 뿐 generalized dependency ordering closure는 아니다
- same bounded order는 now `runtime_graph` node/edge에도 `startup_order_index`와 `startup_after`로 실리기 시작했지만, 이것 역시 graph 설명력 개선일 뿐 generalized dependency ordering closure는 아니다
- latest slice에서는 executor도 explicit sidecar plan/order가 비어 있을 때 `runtime_graph.nodes`의 sidecar node와 `startup_order_index`를 bounded fallback source로 읽기 시작했다
- latest slice에서는 same bounded lane에서 `startup_order_index`가 없어도 `runtime_graph.edges[*].startup_after`를 bounded sidecar order fallback source로 읽기 시작했다
- latest slice에서는 same `runtime_graph.edges[*].startup_after` fallback도 이제 malformed reference, unknown sidecar reference, cyclic dependency를 executor run 전에 early failure로 막기 시작했다. 즉 graph-derived ordering이 더 이상 obviously invalid dependency graph를 조용히 삼키지는 않는다
- latest slice에서는 same `runtime_graph.nodes`가 sidecar `env`/`ready_probe` reconstruction에도 일부 연결되고, `runtime_graph.env_contract`는 service env fallback source를 넘어서 sidecar env backfill source로도 읽히기 시작했다
- latest slice에서는 same `runtime_graph.network.enabled/mode`도 executor의 `allow_network/network_mode` fallback source로 읽히기 시작했다
- latest slice에서는 same `runtime_graph.exploit_path`와 service node도 `service_port`/`service_entry`/`base_url` fallback source로 읽히기 시작했다
- latest slice에서는 same declared `healthchecks.port`도 `executor_plan`/`runtime_graph`/`runtime_recipe`에서 `service_port` fallback source로 읽히기 시작했다
- latest slice에서는 same readiness `healthchecks` 자체도 이제 `runtime_recipe.healthchecks`를 fallback으로 읽기 시작해, `service_port` derivation과 actual readiness probe candidate가 더 덜 어긋난다
- latest slice에서는 same `health_path_source`도 이제 executor/runtime-recipe healthchecks declaration을 더 직접 반영해, actual readiness probe candidate와 surface provenance가 더 덜 어긋난다
- latest slice에서는 same `healthchecks_source`도 execution surface, bundle summary, single-bundle top-level summary까지 노출되기 시작해, readiness candidate가 어디서 왔는지 operator가 더 직접 읽을 수 있게 됐다
- latest slice에서는 same service `healthchecks`도 unsupported transport, HTTP(S) probe without path, TCP probe with path, non-service node declaration뿐 아니라 conflicting explicit probe ports, resolved `service_port`와의 명백한 drift, 사실상 하나로 정해진 HTTP(S) healthcheck path와 resolved `health_path` 간 obvious mismatch도 executor가 run 전에 early failure로 막기 시작했다
- latest slice에서는 same `service_env`의 `APP_PORT`/`PORT`가 resolved `service_port`와 명백히 어긋나도 executor가 run 전에 early failure로 막기 시작했다
- latest slice에서는 same bounded external-DB lane의 `DB_PORT`도 resolved mysql/postgres runtime kind와 명백히 어긋나면 executor가 run 전에 early failure로 막기 시작했다
- latest slice에서는 same workspace path contract도 더 조여져, `service_entry`, `poc_entry`, declared `seed_files`의 absolute path나 `..` traversal을 executor가 run 전에 early failure로 막기 시작했다
- latest slice에서는 same bounded external-DB lane의 `DB_HOST`도 resolved sidecar alias/name과 명백히 어긋나면 executor가 run 전에 early failure로 막기 시작했다
- latest slice에서는 same bounded external-DB lane의 `DB_NAME/DB_USER/DB_PASSWORD`도 service env와 actual sidecar env가 둘 다 선언돼 있는데 명백히 어긋나면 executor가 run 전에 early failure로 막기 시작했다
- latest slice에서는 same bounded sidecar lane의 `ready_probe.type`도 actual mysql/postgres runtime kind와 명백히 어긋나면 executor가 run 전에 early failure로 막기 시작했다
- latest slice에서는 same bounded sidecar lane의 `name`/`aliases`도 network identity contract로 읽혀, duplicate sidecar name이나 alias collision, alias-vs-other-name collision이 있으면 executor가 run 전에 early failure로 막기 시작했다
- latest slice에서는 same bounded seed lane의 `volume_contract`가 한 sidecar에 multiple workspace read-only seed mount target을 선언해 actual apply target이 모호해지는 경우도 executor가 run 전에 early failure로 막기 시작했다
- latest slice에서는 same bounded external-DB lane의 `DB_NAME/DB_USER/DB_PASSWORD`도 service env와 actual sidecar env가 둘 다 선언돼 있는데 명백히 어긋나면 executor가 run 전에 early failure로 막기 시작했다
- latest slice에서는 same `service_entry`도 이제 actual run 전 workspace existence validation으로 연결돼, declared entry file drift를 executor가 early failure로 막기 시작했다
- latest slice에서는 same `poc_entry`도 `executor_plan/runtime_recipe/resolved_contract/runtime_graph.exploit_path`에서 execution surface로 복구되고, actual run 전 workspace existence validation까지 연결되기 시작했다
- latest slice에서는 same `poc_cmd`도 execution surface에 올라와 main PoC execution과 oracle replay가 같은 resolved command template를 재사용하기 시작했다
- latest slice에서는 same `poc_cmd`도 placeholder/inlined form은 허용하되 declared local script reference가 resolved `poc_entry`와 명백히 어긋나면 executor가 run 전에 early failure로 막기 시작했다
- latest slice에서는 same local `base_url`도 `service_port`와 어긋나면 executor run 전에 early failure로 막기 시작했다. 즉 localhost/127.0.0.1 target에 대한 endpoint contract drift를 더 일찍 드러낸다
- latest slice에서는 same `network_contract`가 alias validation/materialization을 넘어, service env가 비어 있을 때 `service` scope `{name, alias}`를 bounded binding source로도 쓰기 시작했다
- latest slice에서는 same `network_contract`가 같은 service env key에 서로 다른 alias를 중복 선언해 contract 자체가 모호한 경우도 executor가 run 전에 early failure로 막기 시작했다
- latest slice에서는 same `network_contract`가 service scope alias를 선언했는데 sidecar alias catalog 자체가 없어 target을 전혀 해석할 수 없는 경우도 executor가 run 전에 early failure로 막기 시작했다
- latest slice에서는 same service env 보강 provenance도 더 보존돼, `service_env_source`가 `executor_plan.service_env+network_contract_aliases+runtime_hint_sidecar_defaults`처럼 합성 source를 surface할 수 있게 됐다
- latest slice에서는 same service-level fallback provenance(`service_port_source`, `service_entry_source`, `base_url_source`, `health_path_source`)도 executor summary와 aggregate surface까지 노출되기 시작했다
- 즉 `runtime_graph`는 아직 true control-plane은 아니지만, same bounded lane에서는 sidecar/env/order/network/service fallback의 실제 입력으로 부분 연결되기 시작했다
- latest slice에서는 `seed_strategy`도 contract와 executor summary까지 roundtrip되기 시작했지만, 이것 역시 bounded seed/init parity 강화일 뿐 generalized seed-init DSL closure는 아니다
- same `seed_strategy`는 이제 executor의 run 전 contract validation에도 일부 연결돼, `sqlite_service_init`의 non-sqlite/sidecar 모순과 `sidecar_sql_apply`의 external-db 또는 `.sql` seed file 부재를 early failure로 막기 시작했지만, 이것 역시 bounded strategy self-consistency 강화일 뿐 generalized seed-init DSL closure는 아니다
- latest slice에서는 same `sidecar_sql_apply`가 SQL-capable sidecar target 없이 선언되거나 mysql/postgres family가 동시에 걸려 actual apply target이 모호한 경우도 executor가 run 전에 early failure로 막기 시작했다
- latest slice에서는 same `sidecar_sql_apply`가 DB family hint만 있고 actual SQL-capable sidecar entry가 없는 경우도 executor가 run 전에 early failure로 막기 시작했다
- same bounded mysql/postgres lane에서는 `env_contract`도 이제 service scope를 넘어 `sidecar:<name>` env를 일부 싣고 executor가 sidecar env drift까지 early validation으로 막기 시작했지만, 이것 역시 bounded env-contract parity 강화일 뿐 richer env-volume semantics closure는 아니다
- latest slice에서는 same `env_contract`가 같은 `scope+name`에 서로 다른 expected value를 중복 선언해 contract 자체가 모호한 경우도 executor가 run 전에 early failure로 막기 시작했다
- latest slice에서는 same `env_contract`가 `service`와 `sidecar:*` 외 unsupported scope를 포함하면 executor가 run 전에 early failure로 막기 시작했다
- same bounded seed lane에서는 `volume_contract`도 이제 contract와 executor summary까지 roundtrip되기 시작했고 executor가 `/seed-input:ro` mount intent와 missing/malformed seed mount contract를 early validation으로 막기 시작했지만, 이것 역시 bounded volume-contract parity 강화일 뿐 richer env-volume semantics closure는 아니다
- latest slice에서는 same `volume_contract`가 `sidecar:*` 외 unsupported scope를 포함하면 executor가 run 전에 early failure로 막기 시작했다
- latest slice에서는 same `volume_contract`가 `workspace/runtime` 외 unsupported `source` 값을 포함하면 executor가 run 전에 early failure로 막기 시작했다
- latest slice에서는 same `volume_contract`가 같은 `scope+target`에 서로 다른 `source/mode`를 중복 선언해 mount definition 자체가 충돌하는 경우도 executor가 run 전에 early failure로 막기 시작했다
- latest slice에서는 same `volume_contract`가 `/seed-input` 고정 가정을 넘어서 declared workspace mount target을 actual sidecar mount와 seed-apply path에도 일부 반영하기 시작했지만, 이것 역시 bounded custom mount-target materialization일 뿐 generalized volume semantics closure는 아니다
- latest slice에서는 same actual seed mount target도 `seed_mount_targets`로 bundle summary와 PACK aggregate에 노출되기 시작해, `/seed-input` default와 custom target이 측정 surface에서도 구분된다
- latest slice에서는 `runtime_surface_summary`도 `runtime_recipe`가 비어 있는 service-level source field를 `run_summary` provenance로 보완해, `service_port/base_url/health_path` source bucket이 actual execution 기준으로 더 덜 `missing`하게 집계되기 시작했다
- latest slice에서는 E2E bundle summary도 actual `executed_sidecars` record를 그대로 노출해, sidecar별 `seed_mount_target`, `seed_files_applied`, `start_order_index`를 직접 읽을 수 있게 됐다
- latest slice에서는 same `executed_sidecars` record가 `type`과 `aliases`도 같이 노출해, actual executed sidecar runtime kind와 alias wiring을 bundle summary에서 더 직접 읽을 수 있게 됐다
- latest slice에서는 same `runtime_surface_summary`도 recipe-thin bundle에서 `run_summary.sidecars/network_mode/sidecar_start_order`를 fallback으로 읽기 시작해, sidecar/network/order aggregate가 actual execution shape를 더 덜 놓치게 됐다
- latest slice에서는 same topology bucket도 recipe가 비어 있으면 `run_summary` execution shape에서 bounded fallback으로 복구돼, executed sidecar가 있는 bundle이 aggregate에서 `unknown` 대신 `service_plus_sidecar`로 더 자주 집계되기 시작했다
- latest slice에서는 single-bundle top-level manifest도 `executed_sidecars`, `seed_mount_targets`, `seed_apply_*`, `network_mode`, `service_base_url` 같은 actual execution detail을 직접 flatten하기 시작해, operator가 `bundles[0]`를 열지 않아도 핵심 runtime fact를 읽을 수 있게 됐다
- latest slice에서는 same top-level flattening이 `executed_sidecars[*].type/aliases/seed_mount_target/seed_files_applied`까지 포함하게 돼, sidecar runtime kind와 alias wiring도 `bundles[0]`를 열지 않고 읽을 수 있게 됐다
- latest slice에서는 same operator-facing summary/top-level manifest가 actual `service_env_runtime`와 `allow_network` 값도 직접 노출하기 시작해, source뿐 아니라 resolved runtime value 자체도 `bundles[0]`를 열지 않고 읽을 수 있게 됐다
- latest slice에서는 same top-level E2E summary도 `service_port`, `service_base_url`, `network_mode`, `executed_sidecars`, `seed_apply_*`, `seed_mount_targets`를 직접 노출하기 시작해, single-bundle representative direct run의 핵심 runtime fact를 한 화면에서 읽기 쉬워졌다
- latest slice에서는 same top-level E2E summary가 이 actual runtime value와 짝이 되는 `service_port_source`, `base_url_source`, `health_path_source`, `service_env_source`, `allow_network_source`, `network_mode_source`도 함께 노출하기 시작해, single-bundle summary만으로 value와 provenance를 같이 읽을 수 있게 됐다
- latest slice에서는 same top-level E2E summary가 `service_entry_source`, `poc_entry`, `poc_entry_source`, `poc_cmd`, `poc_cmd_source`, `sidecars_source`, `sidecar_start_order`, `sidecar_start_order_source`, `network_contract`, `network_contract_source`, `seed_strategy`, `seed_strategy_source`, `seed_files`, `seed_files_source`, `volume_contract`, `volume_contract_source`도 함께 노출하기 시작해, single-bundle representative direct run은 top-level summary만으로 runtime value, provenance, contract intent를 더 self-contained하게 읽을 수 있게 됐다
- latest slice에서는 same `runtime_surface_summary`도 `by_poc_entry_source`, `by_poc_cmd_source`를 함께 집계하기 시작해, actual PoC entry/command가 어느 contract/fallback source에서 왔는지 aggregate에서도 읽을 수 있게 됐다
- same bounded sidecar lane에서는 `network_contract`도 이제 contract와 executor summary까지 roundtrip되기 시작했고 executor가 service `DB_HOST`와 sidecar alias drift, missing sidecar target, network-disabled 모순을 early validation으로 막기 시작했지만, 이것 역시 bounded network-contract parity 강화일 뿐 generalized network lifecycle closure는 아니다
- latest slice에서는 same `network_contract`가 `service`와 `sidecar:*` 외 unsupported scope를 포함하면 executor가 run 전에 early failure로 막기 시작했다
- latest slice에서는 same `network_contract`가 alias materialization에도 일부 연결돼, sidecar entry alias가 비어 있어도 declared contract가 있으면 execution surface와 `docker run --network-alias`까지 보강되기 시작했지만, 이것 역시 bounded alias synthesis일 뿐 generalized network lifecycle closure는 아니다
- latest direct rerun 기준으로 representative open-redirect minimal_dynamic fallback도 이제 executable oracle replay를 통해 `oracle_execution_parity = high`까지 올릴 수 있게 됐지만, 이것 역시 bounded fallback lane의 oracle closure 개선일 뿐 generalized open-world closure를 뜻하지는 않는다
- latest direct rerun 기준으로 compiler-generated external DB lane도 이제 `schema.sql`과 `sidecar_sql_apply` seed surface를 실제로 내보내고 bounded actual seed apply까지 수행할 수 있게 됐지만, 이것 역시 compiler-backed narrow lane 개선일 뿐 generalized seed/runtime synthesis는 아니다
- latest direct rerun 기준으로 same compiler-generated external DB lane과 representative stateless/body-structured/sessionful minimal_dynamic fallback lane(`open_redirect`, `template_injection`, `path_traversal`, `ssrf`, `deserialization`, `xxe`, `csrf`)은 executable oracle replay까지 성공해서 bounded compiler/fallback lane에서는 `oracle_execution_parity = high`를 달성할 수 있게 됐지만, broader multi-step/browser stateful oracle lane과 generalized lane까지 일반화된 것은 아니다
- latest slice에서는 `runtime_surface_summary`도 `by_seed_strategy`, `by_sidecars_source`, `by_service_env_source`, `by_network_mode_source`, `explicit_sidecar_order_bundles`까지 집계하기 시작했지만, 이것 역시 bounded runtime provenance aggregate 강화일 뿐 generalized runtime closure는 아니다
- same aggregate는 now `by_volume_contract_source`도 같이 집계하기 시작했지만, 이것 역시 bounded runtime provenance aggregate 강화일 뿐 generalized runtime closure는 아니다
- same aggregate는 now `by_network_contract_source`도 같이 집계하기 시작했지만, 이것 역시 bounded runtime provenance aggregate 강화일 뿐 generalized runtime closure는 아니다
- latest slice에서는 same aggregate가 actual bounded seed apply 결과(`seed_apply_attempted_bundles`, `seed_apply_completed_bundles`, `seed_files_applied_total`)도 읽기 시작했지만, 이것 역시 execution observability 강화일 뿐 generalized seed-init closure는 아니다
- runtime recipe / executor plan surface도 이 hint provenance를 싣기 시작했지만, executor가 그것을 heuristic보다 우선하는 control plane이라고 보긴 아직 이르다
- 그래도 여전히 runtime/topology/oracle이 primitive-first planner의 결과로 materialize되지는 않는다
- current dynamic lane은 여전히 selected family와 bounded builder에 크게 의존한다
- 즉 primitive-informed behavior는 일부 있지만 primitive-first control plane은 아니다

### 6.14 residual-to-ticket map

current residual을 implementation backlog와 직접 연결하면 아래와 같다.

| Residual section | Primary ticket(s) | Why this is the active owner |
| --- | --- | --- |
| `6.1 request_ir is still too resolved` | `TKT-001-D`, `TKT-001-A` | resolved request surface를 summary가 아니라 actual branch input으로 내리는 작업 |
| `6.2 planning focus와 outcome step이 아직 이중화돼 있다` | `TKT-001-E`, `TKT-001-F` | partial-lane wording drift와 unresolved transition rule을 하나의 state machine으로 정리 |
| `6.3 family discovery is still closed-vocabulary` | `TKT-010-A`, `TKT-001-C` | current closure 밖의 open-vocabulary family induction과 family-as-label 축소를 나눠 추적 |
| `6.4 evidence graph는 아직 causal authority graph는 아니다` | `TKT-001-G` | scenario selection이 쓸 authority / contradiction threshold를 명시하는 축 |
| `6.5 stack selection은 개선됐지만 아직 narrow하다` | `TKT-010-B` | runtime/oracle closure 이후 stack/runtime-class expansion으로 미루는 축 |
| `6.6 executor plan은 생겼지만 parity는 아직 얕다` | `TKT-002-C`, `TKT-004-A`, `TKT-004-B`, `TKT-005-A`, `TKT-005-B`, `TKT-005-C` | executor plan, seed/init, env-volume-network semantics를 true control-plane으로 승격 |
| `6.7 one-shot synthesis is still the main bottleneck` | `TKT-006-A`, `TKT-006-B`, `TKT-006-C` | stage persistence, repair-first flow, downgrade journaling로 분해되는 residual |
| `6.8 runtime_graph is not yet the executor control plane` | `TKT-002-A`, `TKT-002-B`, `TKT-002-C`, `TKT-003-A`, `TKT-003-B` | graph-first execution과 ordering/lifecycle parity를 함께 닫아야 하는 축 |
| `6.9 verifier independence / artifact realism is still limited` | `TKT-007-A`, `TKT-007-B` | stateful/browserful replay와 realism rubric integration이 직접 owner |
| `6.10 performance reuse는 생겼지만 measurement closure는 아직 partial이다` | `TKT-008-A1`, `TKT-008-A2` | perf/cache reuse를 authoritative measured gate와 CI policy로 닫는 축 |
| `6.11 support promotion loop is still missing` | `TKT-009-A1`, `TKT-009-B1`, `TKT-009-B2` | actual accept-path verification과 long-lived registry merge/provenance hardening이 남은 축 |
| `6.12 open-world eval matrix는 harness-scoped measurement에 머문다` | `TKT-008-A1`, `TKT-008-A2` | measured preview를 pipeline-level authoritative gate로 승격하는 축 |
| `6.12b summary surface consistency still has residual scope` | `TKT-008-B1`, `TKT-008-B2` | mixed multi-bundle projection consistency와 measured-gate handoff residual |
| `6.12c latest workspace-local repeatability / support stabilization closure` | `TKT-008-B3-A`, `TKT-008-B3-B`, `TKT-008-B3-C`, `TKT-009-B3-A`, `TKT-009-B3-B` | latest direct verification에서 닫힌 bounded stabilization slice의 owner |
| `6.13 primitive-level runtime design control plane이 아직 없다` | `TKT-001-A`, `TKT-001-D`, `TKT-002-C`, `TKT-003-A`, `TKT-004-A`, `TKT-005-A` | primitive-first controller 부재가 runtime/runtime_graph/env/seed residual로 이어지는 핵심 축 |

주의:

- latest recheck에서 확인된 current WSL 2 Docker unavailability(`docker ps` unavailable, representative dynamic lane direct rerun blocked)는 implementation backlog ticket으로 올리지 않는다.
- same issue는 local verification prerequisite이므로 [README.md](../README.md)와 [docs/handbook.md](handbook.md)의 Docker precheck / WSL integration guidance로 관리한다.

## 7. How To Update This Document

- 이 문서는 direct rerun, stable code inspection, summary surface 변경이 있을 때만 갱신한다.
- TODO, priority, next slice는 쓰지 않는다. 그런 내용은 [docs/final_solution.md](final_solution.md)로 보낸다.
- representative sample performance는 observed sample로만 적고 generalized claim으로 승격하지 않는다.
- `promotion_eligible`와 generalized support claim을 같은 의미로 서술하지 않는다.
- direct verification harness entrypoint나 rerun command family가 바뀌면 [tests/e2e/README.md](../tests/e2e/README.md), [docs/handbook.md](handbook.md)와 같이 맞춘다.
- completion companion 관계나 completion reading order가 바뀌면 [docs/work_tickets.md](work_tickets.md), [README.md](../README.md)와 같이 맞춘다.
- review mode entry shortcut이 바뀌면 [docs/work_tickets.md](work_tickets.md), [README.md](../README.md)와 같이 맞춘다.

## 8. Evidence Sources

- workspace code inspection
- `python -m pytest -q tests`
- targeted regression slices
- representative E2E reruns
- workspace-local direct execution / repeatability / support workflow CLI checks
- repo-tracked historical snapshots for comparison only

## 9. Current Bottom Line

현재 vulDocker는 여전히 아래에 가깝다.

> "지원 family에 대한 정직한 regression platform, 그리고 일부 supported family에 대한 bounded dynamic degraded generator"

이번 latest slice로 실제로 좋아진 것은 다음이다.

- `2026-03-15` canonical rerun-backed snapshot의 `586 passed` baseline 위에, current workspace-local head는 `824 passed, 53 skipped` green baseline까지 다시 회복됐다
- same truth 위에 current workspace-local direct verification도 추가돼, strict fail-closed lane / unsupported negative abstain lane / blocked no-op support workflow가 이번 세션에서 다시 확인됐다
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

다만 current workspace-local head를 읽을 때는 아래 caveat를 같이 봐야 한다.

- `2026-03-19` workspace-local direct verification 이후 current head는 `python -m pytest -q tests -> 824 passed, 53 skipped`로 green baseline을 유지하고 있다
- same session에서 repeatability/support helper/API/report drift도 복구돼, no-Docker repeatability/support CLI chain과 targeted regression slice가 함께 다시 green이 됐다
- representative Docker-executed dynamic lane는 이번 세션 환경에서 `docker daemon is not reachable` 때문에 fresh direct rerun으로 다시 확인하지 못했다

하지만 가장 중요한 구조적 한계는 그대로다.

- early-resolved control plane
- closed-vocabulary family hypothesis
- 아직 얕은 evidence authority
- one-shot synthesis
- executor/runtime plan 불일치
- support promotion loop 부재
- multi-service / unknown-family / unknown-stack open-world 미지원

구현 우선순위와 phase roadmap은 [docs/final_solution.md](final_solution.md), actionable ticket backlog는 [docs/work_tickets.md](work_tickets.md)를 본다.
