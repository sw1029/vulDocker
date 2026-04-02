# vulDocker 핸드북

Status: support
Audience: operator
Source of truth for: quickstart, command map, artifact locations, troubleshooting entrypoints
Not the source of truth for: current-state assessment, constraints, roadmap
Last validated against: repository commands, `python -m pytest -q tests/test_ops_ci_*.py`, support/repeatability workflow, and representative reruns on 2026-04-02

이 문서는 운영/온보딩용 가이드입니다. 개념 정의와 현재 제약은 요약하지 않고, 어떤 문서를 어디서 읽어야 하는지와 실제 실행 절차만 제공합니다.

canonical 관계:
- 왜 이 프로젝트를 하는가: [docs/problem.md](problem.md)
- 현재 진단은 어디에 적는가: [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)
- 무엇을 주장하면 안 되는가: [docs/constraints.md](constraints.md)
- 무엇을 먼저 구현할 것인가: [docs/final_solution.md](final_solution.md)
- 그 계획을 어떤 작업 티켓으로 쪼갰는가: [docs/work_tickets.md](work_tickets.md)
- representative validation harness는 어디에 적는가: [tests/e2e/README.md](../tests/e2e/README.md)

문서 충돌 시 우선순위:
- current truth는 [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)를 우선
- current non-claim은 [docs/constraints.md](constraints.md)를 우선
- implementation order는 [docs/final_solution.md](final_solution.md)를 우선
- actionable subtask와 잔여 작업량/turn envelope는 [docs/work_tickets.md](work_tickets.md)를 우선
- 이 문서는 실행 절차와 artifact 해석만 담당

현재 실행 순서와 owner를 바로 확인하려면:
- phase-to-ticket translation: [docs/final_solution.md](final_solution.md)
- phase acceptance -> validation surface map: [docs/final_solution.md](final_solution.md)
- priority board / current remaining snapshot / confirmed completion priority order / estimated turn envelope / sequencing rule: [docs/work_tickets.md](work_tickets.md)
- turn estimate entry: [docs/work_tickets.md](work_tickets.md)의 `Turn Estimate Entry`
- code entrypoints / representative validation surface by ticket: [docs/work_tickets.md](work_tickets.md)
- validation harness / case layout / repeatability-support workflow details: [tests/e2e/README.md](../tests/e2e/README.md)
- CI/ops companion specs: [ops/ci/pipeline.md](../ops/ci/pipeline.md), [ops/observability/dashboard_spec.md](../ops/observability/dashboard_spec.md)

## Validation Companions

운영/검증 관점에서 이 문서와 같이 봐야 할 companion은 아래와 같다.

- success criteria 5축과 backlog owner 대응: [docs/work_tickets.md](work_tickets.md)
- completion companion set: [docs/work_tickets.md](work_tickets.md)의 `Completion Companions`
- priority companion set: [docs/work_tickets.md](work_tickets.md)의 `Priority Companions`
- success criteria 5축의 완료판정 질문과 최소 근거: [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Checklist`
- success criteria 5축의 canonical 완료 검토 순서: [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Review Flow`
- success criteria 5축의 canonical 완료판정 reading order: [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Reading Order`
- latest confirmed residual의 축별 ticket bundle 분해: [docs/work_tickets.md](work_tickets.md)의 `Open-World Residual Ticket Breakdown`
- latest direct verification까지 반영한 current completion priority order: [docs/work_tickets.md](work_tickets.md)의 `Confirmed Completion Priority Order`
- latest confirmed residual의 canonical 구현 검토 순서: [docs/work_tickets.md](work_tickets.md)의 `Open-World Residual Review Flow`
- latest confirmed residual 검토 문서 순서: [docs/work_tickets.md](work_tickets.md)의 `Open-World Residual Reading Order`
- residual companion set: [docs/work_tickets.md](work_tickets.md)의 `Residual Companions`
- review mode별 canonical 시작점: [docs/work_tickets.md](work_tickets.md)의 `Review Mode Matrix`
- 우선순위 판단 routing: [docs/work_tickets.md](work_tickets.md)의 `Priority Question Routing`, `Priority Reading Order`, `Assessment-To-Ticket Interpretation`
- phase acceptance와 validation surface 대응: [docs/final_solution.md](final_solution.md)
- ticket별 first harness와 reading order: [docs/work_tickets.md](work_tickets.md)
- concrete rerun/support harness command: [tests/e2e/README.md](../tests/e2e/README.md)
- code entrypoint와 subsystem owner: [docs/code/README.md](code/README.md)
- CI/ops companion specs: [ops/ci/pipeline.md](../ops/ci/pipeline.md), [ops/observability/dashboard_spec.md](../ops/observability/dashboard_spec.md)
- success criteria 5축별 artifact reading hints: 이 문서의 `Open-World Axis Reading Hints`, [docs/code/workspaces.md](code/workspaces.md)의 `Open-World Axis Artifact Hints`
- current truth와 observed rerun evidence: [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)
- 질문 기반 routing: [docs/work_tickets.md](work_tickets.md)의 `Validation Question Routing`
- residual 질문 기반 routing: [docs/work_tickets.md](work_tickets.md)의 `Residual Question Routing`

## Completion Companions

운영/완료판정 관점에서 이 문서와 같이 봐야 할 companion은 아래와 같다.

- completion companion set: [docs/work_tickets.md](work_tickets.md)의 `Completion Companions`
- priority companion set: [docs/work_tickets.md](work_tickets.md)의 `Priority Companions`
- axis map / close criteria / canonical review order: [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Axis Map`, `Open-World Completion Checklist`, `Open-World Completion Review Flow`
- canonical completion reading order: [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Reading Order`
- current completion priority order: [docs/work_tickets.md](work_tickets.md)의 `Confirmed Completion Priority Order`
- phase acceptance map: [docs/final_solution.md](final_solution.md)의 `Acceptance-To-Validation Translation`
- harness entry: [tests/e2e/README.md](../tests/e2e/README.md)
- code entrypoint: [docs/code/README.md](code/README.md)
- artifact reading / troubleshooting: 이 문서의 `Open-World Axis Reading Hints`
- current truth / non-claim: [docs/current_state_gap_analysis.md](current_state_gap_analysis.md), [docs/constraints.md](constraints.md)

## Residual Companions

운영/잔여 구현 검토 관점에서 이 문서와 같이 봐야 할 companion은 아래와 같다.

- residual bucket / ticket bundle: [docs/work_tickets.md](work_tickets.md)의 `Open-World Residual Ticket Breakdown`
- current completion priority order: [docs/work_tickets.md](work_tickets.md)의 `Confirmed Completion Priority Order`
- residual close criteria: [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Checklist`
- residual review / reading order: [docs/work_tickets.md](work_tickets.md)의 `Open-World Residual Review Flow`, `Open-World Residual Reading Order`
- phase acceptance map: [docs/final_solution.md](final_solution.md)의 `Acceptance-To-Validation Translation`
- code entrypoint / residual focus: [docs/code/README.md](code/README.md)
- current truth / non-claim: [docs/current_state_gap_analysis.md](current_state_gap_analysis.md), [docs/constraints.md](constraints.md)

## Priority Companions

운영/우선순위 판단 관점에서 이 문서와 같이 봐야 할 companion은 아래와 같다.

- current completion priority order: [docs/work_tickets.md](work_tickets.md)의 `Confirmed Completion Priority Order`
- 잔여 작업량과 practical turn envelope: [docs/work_tickets.md](work_tickets.md)의 `Estimated Turn Envelope`
- priority companion set / routing / reading order: [docs/work_tickets.md](work_tickets.md)의 `Priority Companions`, `Priority Question Routing`, `Priority Reading Order`
- latest positive representative pair의 ticket-form reading: [docs/work_tickets.md](work_tickets.md)의 `Assessment-To-Ticket Interpretation`
- LLM-response 기준 residual/priority 해석: [docs/work_tickets.md](work_tickets.md)의 `LLM-Response Capability Overlay`
- phase ordering / sequencing guardrail: [docs/final_solution.md](final_solution.md), [docs/work_tickets.md](work_tickets.md)의 `Sequencing Rule`
- current truth / non-claim: [docs/current_state_gap_analysis.md](current_state_gap_analysis.md), [docs/constraints.md](constraints.md)
- harness / code entry: [tests/e2e/README.md](../tests/e2e/README.md), [docs/code/README.md](code/README.md)

## Review Mode Entry

운영/검증 문서를 열 때는 아래 mode entry를 먼저 고른다.

- 검증:
  - [docs/work_tickets.md](work_tickets.md)의 `Review Mode Matrix`
  - 이 문서의 `Validation Reading Order`
- 완료판정:
  - [docs/work_tickets.md](work_tickets.md)의 `Review Mode Matrix`
  - 이 문서의 `Completion Companions`
- 잔여 구현 검토:
  - [docs/work_tickets.md](work_tickets.md)의 `Review Mode Matrix`
  - 이 문서의 `Residual Review Entry`
- 작업량 추산:
  - [docs/work_tickets.md](work_tickets.md)의 `Review Mode Matrix`
  - [docs/work_tickets.md](work_tickets.md)의 `Turn Estimate Entry`
- 우선순위 판단:
  - [docs/work_tickets.md](work_tickets.md)의 `Review Mode Matrix`
  - 이 문서의 `Priority Companions`
  - [docs/work_tickets.md](work_tickets.md)의 `Assessment-To-Ticket Interpretation`

## Priority Review Entry

운영/실행 관점에서 우선순위 판단을 시작할 때는 아래 순서를 권장한다.

1. 이 문서의 `Priority Companions`
2. [docs/work_tickets.md](work_tickets.md)의 `Confirmed Completion Priority Order`, `Estimated Turn Envelope`, `Priority Reading Order`
3. [docs/work_tickets.md](work_tickets.md)의 `LLM-Response Capability Overlay`, `Assessment-To-Ticket Interpretation`
4. 이 문서의 low-cost no-Docker quick checks와 troubleshooting entrypoints
5. [tests/e2e/README.md](../tests/e2e/README.md), [docs/code/README.md](code/README.md)

잔여 작업량/turn estimate만 operator 관점에서 바로 보려면 [docs/work_tickets.md](work_tickets.md)의 `Turn Estimate Entry`를 먼저 본다.

## Read Order

1. 문제와 목표: [docs/problem.md](problem.md)
2. 현재 truth: [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)
3. 현재 제약: [docs/constraints.md](constraints.md)
4. 구현 계획: [docs/final_solution.md](final_solution.md)
5. 작업 티켓: [docs/work_tickets.md](work_tickets.md)
6. 코드 탐색: [docs/code/README.md](code/README.md)
7. 검증 하니스: [tests/e2e/README.md](../tests/e2e/README.md)

## Quickstart

사전 요구
- Docker
- Python 3.11+
- `pip install -r requirements.txt`
- WSL 2 사용 시 Docker Desktop WSL integration 활성화

대표 흐름
1. PLAN: `python orchestrator/plan.py --input inputs/mvp_sqli.yml`
2. 전체 루프: `python orchestrator/run_pipeline.py --sid <SID> --mode deterministic`
3. 단계별 실행이 필요하면 아래 순서를 따릅니다.

단계별 명령
- RESEARCH: `python agents/researcher/main.py --sid <SID> --mode deterministic`
- GENERATE: `python agents/generator/main.py --sid <SID> --mode deterministic`
- EXECUTE: `python executor/runtime/docker_local.py --sid <SID> --build --run`
- VERIFY: `python evals/poc_verifier/main.py --sid <SID>`
- REVIEW: `python agents/reviewer/main.py --sid <SID> --mode deterministic`
- PACK: `python orchestrator/pack.py --sid <SID>`

## Artifact Map

- `metadata/<SID>/plan.json`: normalized requirement and policy
- `metadata/<SID>/researcher_report.json`: retrieval/evidence summary
- `metadata/<SID>/generator_manifest.json`: generator materialization result / synthesis surface
- `metadata/<SID>/generator_runs.json`: generator run record index
- `metadata/<SID>/generator_failures.jsonl`: generator failure/retry trace
- `metadata/<SID>/resolved_contract.json`: current resolved contract surface when present
- `metadata/<SID>/manifest.json` or `metadata/<SID>/failure_manifest.json`: pack summary / failure summary. single-bundle lane에서는 `generation_materialization`과 `selection_branch_trace`도 direct convenience surface로 붙기 시작했습니다
- `metadata/<SID>/reviewer_reports.json`: reviewer report index
- `metadata/<SID>/loop_state.json`: loop / retry state
- `metadata/<SID>/performance_summary.json`: search/cache/perf observation summary
- `workspaces/<SID>/app/`: generated bundle
- `artifacts/<SID>/build/`: build log and SBOM
- `artifacts/<SID>/run/`: run log and run summary
- `artifacts/<SID>/run/oracle_execution.json`: payload replay / oracle execution trace when present
- `artifacts/<SID>/reports/evals.json`: verifier result
- `<OUT_DIR>/repeatability_report.json`: measured repeatability summary, `measured_gate`, `observed_execution_salts`, `generation_path_observations`, `generation_path_gate`, `observed_generation_non_live_reasons`
- `<OUT_DIR>/matrix_report.json`: case-matrix rollup, quality observations, measured-gate observations, generation-path observations, `by_primary_non_live_reason`
- `<OUT_DIR>/support_candidate.json`: measured support candidate with blocker classes and support status
- `support_review_index.json`: review queue aggregate, `by_case_status`, explicit case lists, `by_generation_path_class`, `by_generation_positive_bucket`, `by_generation_non_live_reason`
- `support_registry_update.json`: decision preview, `accepted/rejected/pending_by_support_status`, case-level aggregate, `by_generation_non_live_reason`
- `curated_support_registry.json`: local registry current state, `by_case_review_status`, `last_update`, schema/provenance history. blocked no-op apply에서도 `last_update.by_generation_non_live_reason`는 유지된다

## Open-World Axis Reading Hints

[docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Axis Map`을 실제 artifact에 대응시킬 때는 아래처럼 읽는다.

- 선택
  - `metadata/<SID>/plan.json`
  - `metadata/<SID>/researcher_report.json`
  - `summary.json`의 `request_ir`, `request_ir_summary`, `selection_decision`, `selection_branch_trace`, `name_only_outcome`
  - family/stack/topology/oracle 선택이 evidence-backed인지, `ready_for_materialization`과 `open_world_evidence_ready`가 어디서 멈췄는지 본다.
  - latest slice에서는 same `selection_branch_trace`의 `selected_value/materialized_value/aligned`와 `candidate_context.rejected_scenario_ids_sample`를 같이 읽어, selected scenario가 실제 runtime/oracle/file branch를 열었는지와 어떤 대안이 밀렸는지를 한 번에 본다.
- 생성
  - `metadata/<SID>/generator_manifest.json`
  - `metadata/<SID>/generator_runs.json`
  - `metadata/<SID>/generator_failures.jsonl`
  - `metadata/<SID>/loop_state.json`
  - `metadata/<SID>/manifest.json` 또는 `metadata/<SID>/failure_manifest.json`
  - staged synthesis가 어떤 branch/recovery로 materialize됐는지, 어디서 degrade/fail 되었는지 본다.
- 실행
  - `metadata/<SID>/manifest.json`의 `runtime_graph`, `executor_plan`
  - `artifacts/<SID>/run/summary.json`
  - representative E2E `summary.json`
  - `runtime_graph/executor_plan`과 actual executor behavior가 얼마나 일치하는지, topology/health/seed/run 결과가 어디서 어긋나는지 본다.
- 검증
  - `artifacts/<SID>/run/oracle_execution.json`
  - `artifacts/<SID>/reports/evals.json`
  - `<OUT_DIR>/repeatability_report.json`
  - `<OUT_DIR>/matrix_report.json`
  - oracle replay parity, quality tier, repeatability, measured gate blocker가 어떤 이유로 promotion을 막는지 본다.
  - same slice에서는 `generation_path_observations(primary_path_class, primary_positive_bucket, primary_non_live_reason)`와 `generation_path_gate(blockers)`를 같이 읽어, `fixture_backed_positive`나 `degraded_fallback_positive`를 `live_positive`와 분리하고, why-not-live subtype(`fixture_backed`, `provider_disabled`)도 함께 본다.
- 보고
  - representative E2E `summary.json`의 `name_only_outcome`
  - `<OUT_DIR>/support_candidate.json`
  - `support_review_index.json`
  - `support_registry_update.json`
  - `curated_support_registry.json`
  - `intent_met/partial/abstain/fail_closed`, `support_status`, `by_case_status`, `by_case_review_status`, `last_update`가 혼동 없이 이어지는지 본다.

## Common Checks

- `docker ps`
- `python -m pytest -q tests`
- `python -m pytest -q tests/test_ops_ci_*.py`
- `python -m pytest -q tests/test_ops_ci_script_permissions.py`
- `ops/ci/run_current_operator_baseline.sh`
- `ops/ci/run_ops_helper_contract_regression.sh`
- `ops/ci/run_no_docker_operator_baseline.sh`
- `ops/ci/run_repeatability_chain.sh foobar-name-only-negative open-redirect-strict-dynamic-no-remote`
- `ops/ci/run_docker_positive_operator_baseline.sh`
- focused no-Docker regression slice:
  - `ops/ci/run_focused_no_docker_regression.sh`
  - `python -m pytest -q tests/test_name_only_helpers.py tests/test_pack_promotion.py tests/test_repeatability_gate.py tests/test_support_extract.py tests/e2e/test_support_workflow.py tests/e2e/test_case_matrix_rollup.py`
- `python -m pytest -q tests/test_repeatability_gate.py tests/test_support_extract.py`
- `python -m pytest -q tests/test_ops_ci_e2e_entry_script.py tests/test_ops_ci_repeatability_scripts.py tests/test_ops_ci_custom_vuln_script.py tests/test_ops_ci_base_example_scripts.py tests/test_ops_ci_run_case_script.py tests/test_ops_ci_smoke_regression_script.py`
- `python -m pytest -q tests/test_ops_ci_focused_no_docker_regression.py tests/test_ops_ci_blocked_noop_support_check.py tests/test_ops_ci_positive_pair_promotion_check.py tests/test_ops_ci_e2e_entry_script.py tests/test_ops_ci_repeatability_scripts.py tests/test_ops_ci_custom_vuln_script.py tests/test_ops_ci_base_example_scripts.py tests/test_ops_ci_run_case_script.py tests/test_ops_ci_smoke_regression_script.py`
- `python -m pytest -q tests/e2e/test_support_workflow.py tests/e2e/test_case_matrix_rollup.py`
- repeatability helper / CI chaining은 `repeatability_report.json.passed=false`이면 nonzero로 실패한다.
- focused no-Docker regression helper는 `VULD_FOCUSED_NO_DOCKER_PYTEST_BIN` seam으로 fake pytest regression을 지원한다.
- ops helper contract bundle helper는 `VULD_OPS_HELPER_PYTEST_BIN`, `VULD_OPS_HELPER_TEST_GLOB`, `VULD_OPS_HELPER_PRINT_BUNDLE` seam으로 current `tests/test_ops_ci_*.py` bundle 전체나 custom bundle을 fake pytest regression으로 지원하고, [tests/test_ops_ci_helper_contract_regression.py](/home/ysw/vulDocker/tests/test_ops_ci_helper_contract_regression.py) 가 actual glob set forwarding과 no-match failure를 고정한다.
- ops shell helper들은 executable bit를 유지해야 하며, `tests/test_ops_ci_script_permissions.py`가 이를 regression으로 확인한다.
- current operator baseline helper는 `VULD_CURRENT_BASELINE_NO_DOCKER_HELPER`, `VULD_CURRENT_BASELINE_MEASURED_HELPER`, `VULD_CURRENT_BASELINE_SUPPORT_HELPER`, `VULD_CURRENT_BASELINE_DOCKER_POSITIVE_HELPER`, `VULD_CURRENT_BASELINE_HELPER_REGRESSION` seam으로 top-level helper bundle regression을 지원한다.
- generic repeatability helper는 `VULD_REPEAT_CHAIN_PYTHON_BIN`, `VULD_REPEAT_CHAIN_CASES_ROOT`, `VULD_REPEAT_CHAIN_OUTPUT_ROOT`, `VULD_REPEAT_CHAIN_MODE`, `VULD_REPEAT_CHAIN_ATTEMPTS`, `VULD_REPEAT_CHAIN_NO_SNAPSHOT`, `VULD_REPEAT_CHAIN_ALLOW_FAILURE_WITH_REPORT`, `VULD_REPEAT_CHAIN_DOCKER_RETRY_COUNT`, `VULD_REPEAT_CHAIN_DOCKER_RETRY_DELAY_SEC`, `VULD_REPEAT_CHAIN_RUN_DIRS_FILE`, `VULD_REPEAT_CHAIN_OUTPUT_PREFIX`, `VULD_REPEAT_CHAIN_LOG_PREFIX`, `VULD_REPEAT_CHAIN_REPORT_NAME` seam으로 arbitrary `repeat_case.py` chain regression을 지원한다.
- generic named caseset helper는 `VULD_NAMED_CASE_TARGET_HELPER`, `VULD_NAMED_CASE_LOG_PREFIX` seam으로 named wrapper 공통 argv forwarding regression을 지원한다.
- generic named preset helper는 `VULD_NAMED_PRESET_TARGET_HELPER`, `VULD_NAMED_PRESET_LOG_PREFIX` seam으로 preset-builder -> named wrapper forwarding regression을 지원한다.
- `ops/ci/lib_named_case_env.sh`는 named direct/support/matrix wrapper의 env projection 공통부를 제공하고, latest slice에서는 same library를 직접 검증하는 regression도 추가됐다.
- latest slice에서는 same `ops/ci/lib_named_case_env.sh`가 named direct/support/matrix wrapper의 common caseset dispatch(`named_caseset_dispatch(...)`)도 맡고, same contract는 direct regression으로 고정된다.
- `ops/ci/lib_operator_named_case_env.sh`는 operator pair/triple wrapper의 direct/support env projection 공통부를 제공하고, [tests/test_ops_ci_operator_named_case_env.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_named_case_env.py)가 same mapping을 직접 검증한다.
- `ops/ci/lib_operator_named_preset_helpers.sh`는 preset helper / named wrapper helper / leaf helper executable gate를 공통화하고, [tests/test_ops_ci_operator_named_preset_helpers.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_named_preset_helpers.py)가 preset override, named override, missing preset failure semantics를 직접 검증한다.
- latest slice에서는 `ops/ci/lib_operator_direct_named_preset.sh`가 positive direct / low-cost direct wrapper의 validate -> env export -> preset helper invoke 골격도 공통화하고, same contract는 direct regression으로 고정된다.
- latest slice에서는 `ops/ci/lib_operator_direct_case_check.sh`가 same positive direct / low-cost direct wrapper의 shared direct case-check skeleton도 공통화하고, same contract는 direct regression으로 고정된다.
- latest slice에서는 `ops/ci/lib_operator_pair_case_check.sh`가 same direct/support wrapper family의 shared pair case-check skeleton도 공통화하고, same contract는 direct regression으로 고정된다.
- latest slice에서는 `ops/ci/lib_cases_output_roots.sh`가 same direct/repeatability/support workflow helper family의 cases/output-root default resolution도 공통화하고, same contract는 direct regression으로 고정된다.
- latest slice에서는 `ops/ci/lib_case_expectations.sh`가 same direct/repeatability helper family의 default `expectations.json` auto-discovery와 `--expectations` argv append도 공통화하고, same contract는 direct regression으로 고정된다.
- same direct/repeatability helper family에서는 `ops/ci/lib_case_spec_resolution.sh`가 `case=alias` split, case-dir path resolution, alias/path safety validation뿐 아니라 case-context capture, resolved output-name/safe-slug helper, named output-context export surface도 공통화하고, same contract는 direct regression으로 고정된다.
- same direct/repeatability helper family에서는 `ops/ci/lib_case_command_surface.sh`가 shared `run_case.py` / `repeat_case.py` argv assembly, expectations append, `--no-snapshot` surface도 공통화하고, same contract는 direct regression으로 고정된다.
- same helper family에서는 `ops/ci/lib_case_chain_entry.sh`가 same direct/repeatability helper family의 usage check, output-root prep, entry preflight surface도 공통화하고, same contract는 direct regression으로 고정된다.
- same direct/repeatability helper family에서는 `ops/ci/lib_case_chain_output_notes.sh`가 case-output log, run-dirs file write, completion note surface도 공통화하고, same contract는 direct regression으로 고정된다.
- same direct/repeatability helper family에서는 `ops/ci/lib_repeatability_report_failures.sh`가 repeatability report Docker failure classification, retry gate input, permission-marker writer surface도 공통화하고, same contract는 direct regression으로 고정된다.
- same direct/repeatability helper family에서는 `ops/ci/lib_repeatability_case_failure.sh`가 repeatability case-failure action resolution, retry/continue/fail routing, permission-marker-aware continue surface도 공통화하고, same contract는 direct regression으로 고정된다.
- same direct/repeatability helper family에서는 `ops/ci/lib_repeatability_case_runtime.sh`가 repeatability case context hydration, report-path resolution, run-dir append, `repeat_case.py` argv assembly surface도 공통화하고, same contract는 direct regression으로 고정된다.
- same direct/repeatability helper family에서는 `ops/ci/lib_direct_case_runtime.sh`가 direct case context hydration, output-dir resolution, `run_case.py` argv assembly surface도 공통화하고, same contract는 direct regression으로 고정된다.
- same direct/repeatability helper family에서는 `ops/ci/lib_direct_case_runner.sh`가 direct case runtime reuse, output note emission, `run_case.py` command invoke surface도 공통화하고, same contract는 direct regression으로 고정된다.
- latest slice에서는 `ops/ci/lib_case_chain_profile_target_forward.sh`가 same direct/repeatability profile wrapper family의 shared `profile target forward` surface도 공통화하고, same contract는 direct regression으로 고정된다.
- same support/matrix helper family에서는 `ops/ci/lib_repeatability_chain_runner.sh`가 repeat-helper invoke, env export, run-dir postprocess skeleton도 공통화하고, same contract는 direct regression으로 고정된다.
- same support workflow/reviewable accept helper family에서는 `ops/ci/lib_support_review_runner.sh`가 review-helper invoke, env export, run-dir preflight skeleton도 공통화하고, same contract는 direct regression으로 고정된다.
- latest slice에서는 `ops/ci/lib_support_review_output_surface.sh`가 same support review helper family의 prefix-aware output-name default resolution과 resolved output-path materialization도 공통화하고, `run_support_review_chain.sh`, `run_reviewable_support_accept_check.sh`, `run_support_workflow_chain.sh`가 same resolved output-surface contract를 재사용한다. same contract는 direct regression으로 고정된다.
- latest slice에서는 `ops/ci/lib_operator_cases_output_roots.sh`가 same direct/support pair wrapper family의 cases/output-root default resolution도 공통화하고, same contract는 direct regression으로 고정된다.
- latest slice에서는 `ops/ci/lib_operator_support_named_preset.sh`가 positive pair / blocked-noop support wrapper의 validate -> env export -> preset helper invoke 골격도 공통화하고, same contract는 direct regression으로 고정된다.
- latest slice에서는 `ops/ci/lib_operator_support_pair_check.sh`가 same positive pair / blocked-noop support wrapper의 shared named-preset pair skeleton도 공통화하고, same contract는 direct regression으로 고정된다.
- latest slice에서는 `ops/ci/lib_operator_named_preset_runner.sh`가 same direct/support operator pair wrapper의 shared validate -> env export -> preset helper invoke skeleton도 공통화하고, same contract는 direct regression으로 고정된다.
- latest slice에서는 `ops/ci/lib_operator_pair_named_preset.sh`가 same direct/support named-preset thin wrapper의 pair-runner primitive도 공통화하고, same contract는 direct regression으로 고정된다.
- latest slice에서는 `ops/ci/lib_operator_pair_named_preset_defaults.sh`가 same direct/support named-preset wrapper의 named/preset/leaf helper default resolution도 공통화하고, same contract는 direct regression으로 고정된다.
- latest slice에서는 `ops/ci/lib_operator_case_defaults.sh`가 same direct/support wrapper family의 single/pair/triple/batch case-slug default resolution도 공통화하고, same contract는 direct regression으로 고정된다.
- latest slice에서는 `ops/ci/lib_operator_output_notes.sh`가 same direct/support wrapper family의 completion/output note primitive도 공통화하고, same contract는 direct regression으로 고정된다.
- latest slice에서는 `ops/ci/lib_operator_output_root_notes.sh`가 same direct/support wrapper family의 `output_root + child suffix -> completion note` primitive도 공통화하고, same contract는 direct regression으로 고정된다.
- latest slice에서는 `ops/ci/lib_operator_export_helper_contract.sh`가 same named-preset runner와 matrix baseline sequence family의 export-helper function gate와 invoke primitive도 공통화하고, same contract는 direct regression으로 고정된다.
- latest slice에서는 `ops/ci/lib_operator_runtime_sequence.sh`가 measured/support/docker-positive baseline wrapper의 runtime-surface forwarding + sequence invocation skeleton도 공통화하고, same contract는 direct regression으로 고정된다.
- latest slice에서는 `ops/ci/lib_operator_pair_runtime_baseline.sh`가 support workflow/docker-positive baseline wrapper의 two-step runtime baseline skeleton도 공통화하고, same contract는 direct regression으로 고정된다.
- latest slice에서는 `ops/ci/lib_operator_pair_runtime_baseline_defaults.sh`가 support workflow/docker-positive baseline wrapper의 helper/default resolution contract도 공통화하고, same contract는 direct regression으로 고정된다.
- latest slice에서는 `ops/ci/lib_operator_helper_defaults.sh`가 pair/matrix/current defaults library가 공유하는 helper-default single/batch resolution primitive도 공통화하고, same contract는 direct regression으로 고정된다.
- latest slice에서는 `ops/ci/lib_operator_matrix_case_pair.sh`가 measured/no-docker baseline wrapper의 planning-only matrix pair default/partial-override contract도 공통화하고, same contract는 direct regression으로 고정된다.
- latest slice에서는 `ops/ci/lib_operator_matrix_baseline_defaults.sh`가 measured/no-docker baseline wrapper의 matrix helper/default resolution contract도 공통화하고, same contract는 direct regression으로 고정된다.
- latest slice에서는 `ops/ci/lib_operator_matrix_baseline_sequence.sh`가 measured/no-docker matrix baseline wrapper의 matrix env export + runtime-surface + sequence invocation skeleton도 공통화하고, same contract는 direct regression으로 고정된다.
- latest slice에서는 `ops/ci/lib_operator_current_baseline_defaults.sh`가 current baseline의 helper/default resolution contract도 공통화하고, same contract는 direct regression으로 고정된다.
- latest slice에서는 `ops/ci/lib_operator_current_baseline_sequence.sh`가 current baseline의 child-surface forwarding + sequence invocation skeleton도 공통화하고, same contract는 direct regression으로 고정된다.
- latest slice에서는 `ops/ci/lib_operator_sequence_helper_contract.sh`가 runtime/current/matrix baseline family의 sequence-helper executable gate와 invoke primitive도 공통화하고, same contract는 direct regression으로 고정된다.
- `ops/ci/lib_case_spec_presets.sh`는 positive pair, blocked/noop pair, low-cost no-Docker triple, measured matrix pair alias-set preset을 공통화하고, [tests/test_ops_ci_case_spec_presets.py](/home/ysw/vulDocker/tests/test_ops_ci_case_spec_presets.py) 가 same preset payload를 직접 검증한다.
- `ops/ci/lib_operator_baseline_matrix_env.sh`는 measured/no-Docker matrix baseline의 `VULD_NAMED_MATRIX_*` export를 공통화하고, [tests/test_ops_ci_operator_baseline_matrix_env.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_baseline_matrix_env.py)가 same projection을 직접 검증한다.
- `ops/ci/lib_operator_retry_env.sh`는 top-level operator baseline의 single-target runtime surface와 multi-target retry/permission forwarding을 공통화하고, [tests/test_ops_ci_operator_retry_env.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_retry_env.py)가 same projection을 직접 검증한다.
- named matrix wrapper helper는 `VULD_NAMED_MATRIX_HELPER`, `VULD_NAMED_MATRIX_PYTHON_BIN`, `VULD_NAMED_MATRIX_CASES_ROOT`, `VULD_NAMED_MATRIX_OUTPUT_ROOT`, `VULD_NAMED_MATRIX_MODE`, `VULD_NAMED_MATRIX_ATTEMPTS`, `VULD_NAMED_MATRIX_NO_SNAPSHOT`, `VULD_NAMED_MATRIX_ALLOW_REPEAT_FAILURE_WITH_REPORT`, `VULD_NAMED_MATRIX_DOCKER_RETRY_COUNT`, `VULD_NAMED_MATRIX_DOCKER_RETRY_DELAY_SEC`, `VULD_NAMED_MATRIX_REPEAT_HELPER` seam으로 matrix pair forwarding regression을 지원한다.
- named support-case wrapper helper는 `VULD_NAMED_SUPPORT_HELPER`, `VULD_NAMED_SUPPORT_PYTHON_BIN`, `VULD_NAMED_SUPPORT_CASES_ROOT`, `VULD_NAMED_SUPPORT_OUTPUT_ROOT`, `VULD_NAMED_SUPPORT_MODE`, `VULD_NAMED_SUPPORT_ATTEMPTS`, `VULD_NAMED_SUPPORT_REVIEW_ONLY`, `VULD_NAMED_SUPPORT_DECISIONS_FILE`, `VULD_NAMED_SUPPORT_NO_SNAPSHOT`, `VULD_NAMED_SUPPORT_ALLOW_REPEAT_FAILURE_WITH_REPORT`, `VULD_NAMED_SUPPORT_DOCKER_RETRY_COUNT`, `VULD_NAMED_SUPPORT_DOCKER_RETRY_DELAY_SEC`, `VULD_NAMED_SUPPORT_REVIEW_OUTPUT_NAME`, `VULD_NAMED_SUPPORT_DECISIONS_OUTPUT_NAME`, `VULD_NAMED_SUPPORT_UPDATE_OUTPUT_NAME`, `VULD_NAMED_SUPPORT_REGISTRY_OUTPUT_NAME`, `VULD_NAMED_SUPPORT_REPEAT_HELPER`, `VULD_NAMED_SUPPORT_REVIEW_HELPER` seam으로 pair-wrapper forwarding regression을 지원한다.
- named direct-case wrapper helper는 `VULD_NAMED_DIRECT_HELPER`, `VULD_NAMED_DIRECT_PYTHON_BIN`, `VULD_NAMED_DIRECT_CASES_ROOT`, `VULD_NAMED_DIRECT_OUTPUT_ROOT`, `VULD_NAMED_DIRECT_MODE`, `VULD_NAMED_DIRECT_NO_SNAPSHOT` seam으로 pair-wrapper forwarding regression을 지원한다.
- generic direct validation helper는 `VULD_DIRECT_CHAIN_PYTHON_BIN`, `VULD_DIRECT_CHAIN_CASES_ROOT`, `VULD_DIRECT_CHAIN_OUTPUT_ROOT`, `VULD_DIRECT_CHAIN_MODE`, `VULD_DIRECT_CHAIN_NO_SNAPSHOT` seam으로 arbitrary `run_case.py` chain regression을 지원한다.
- generic support workflow helper는 `VULD_SUPPORT_WORKFLOW_PYTHON_BIN`, `VULD_SUPPORT_WORKFLOW_CASES_ROOT`, `VULD_SUPPORT_WORKFLOW_OUTPUT_ROOT`, `VULD_SUPPORT_WORKFLOW_MODE`, `VULD_SUPPORT_WORKFLOW_ATTEMPTS`, `VULD_SUPPORT_WORKFLOW_REVIEW_ONLY`, `VULD_SUPPORT_WORKFLOW_DECISIONS_FILE`, `VULD_SUPPORT_WORKFLOW_NO_SNAPSHOT`, `VULD_SUPPORT_WORKFLOW_ALLOW_REPEAT_FAILURE_WITH_REPORT`, `VULD_SUPPORT_WORKFLOW_DOCKER_RETRY_COUNT`, `VULD_SUPPORT_WORKFLOW_DOCKER_RETRY_DELAY_SEC`, `VULD_SUPPORT_WORKFLOW_REVIEW_OUTPUT_NAME`, `VULD_SUPPORT_WORKFLOW_DECISIONS_OUTPUT_NAME`, `VULD_SUPPORT_WORKFLOW_UPDATE_OUTPUT_NAME`, `VULD_SUPPORT_WORKFLOW_REGISTRY_OUTPUT_NAME`, `VULD_SUPPORT_WORKFLOW_REPEAT_HELPER`, `VULD_SUPPORT_WORKFLOW_REVIEW_HELPER` seam으로 arbitrary repeat/review/decide/apply chain regression을 지원한다.
- generic support review helper는 `VULD_SUPPORT_REVIEW_PYTHON_BIN`, `VULD_SUPPORT_REVIEW_OUTPUT_ROOT`, `VULD_SUPPORT_REVIEW_REVIEW_ONLY`, `VULD_SUPPORT_REVIEW_DECISIONS_FILE`, `VULD_SUPPORT_REVIEW_REVIEW_OUTPUT_NAME`, `VULD_SUPPORT_REVIEW_DECISIONS_OUTPUT_NAME`, `VULD_SUPPORT_REVIEW_UPDATE_OUTPUT_NAME`, `VULD_SUPPORT_REVIEW_REGISTRY_OUTPUT_NAME` seam으로 arbitrary review/update/apply chain regression을 지원한다.
- no-Docker operator baseline helper는 `VULD_NO_DOCKER_BASELINE_FOCUSED_HELPER`, `VULD_NO_DOCKER_BASELINE_LOW_COST_HELPER`, `VULD_NO_DOCKER_BASELINE_PRESET_HELPER`, `VULD_NO_DOCKER_BASELINE_MATRIX_HELPER`, `VULD_NO_DOCKER_BASELINE_BLOCKED_HELPER` seam으로 helper bundle regression을 지원한다.
- measured gate operator baseline helper는 `VULD_MEASURED_BASELINE_PRESET_HELPER`, `VULD_MEASURED_BASELINE_MATRIX_HELPER`, `VULD_MEASURED_BASELINE_PROMOTION_HELPER`, `VULD_MEASURED_BASELINE_MATRIX_CASE_A`, `VULD_MEASURED_BASELINE_MATRIX_CASE_B`, `VULD_MEASURED_BASELINE_DOCKER_RETRY_COUNT`, `VULD_MEASURED_BASELINE_DOCKER_RETRY_DELAY_SEC` seam으로 measured preview helper bundle regression을 지원한다.
- measured gate operator baseline helper는 latest slice에서 `VULD_MEASURED_BASELINE_SEQUENCE_HELPER`, `VULD_MEASURED_BASELINE_PRESET_HELPER`, `VULD_MEASURED_BASELINE_NAMED_MATRIX_HELPER` seam을 통해 generic `ops/ci/run_helper_sequence.sh`, `ops/ci/run_named_preset_case_set.sh`, `ops/ci/run_named_matrix_case_set.sh`도 재사용한다.
- support workflow operator baseline helper는 `VULD_SUPPORT_BASELINE_SEQUENCE_HELPER`, `VULD_SUPPORT_BASELINE_REVIEWABLE_HELPER`, `VULD_SUPPORT_BASELINE_BLOCKED_HELPER`, `VULD_SUPPORT_BASELINE_DOCKER_RETRY_COUNT`, `VULD_SUPPORT_BASELINE_DOCKER_RETRY_DELAY_SEC` seam으로 support helper bundle regression을 지원한다.
- reviewable accept-path helper는 `VULD_REVIEWABLE_ACCEPT_PYTHON_BIN`, `VULD_REVIEWABLE_ACCEPT_OUTPUT_ROOT`, `VULD_REVIEWABLE_ACCEPT_CASE_NAME`, `VULD_REVIEWABLE_ACCEPT_SLUG`, `VULD_REVIEWABLE_ACCEPT_VULN_ID`, `VULD_REVIEWABLE_ACCEPT_REVIEWER`, `VULD_REVIEWABLE_ACCEPT_RATIONALE`, `VULD_REVIEWABLE_ACCEPT_REVIEW_HELPER` seam으로 synthetic accept-path regression을 지원한다.
- Docker-enabled positive operator baseline helper는 `VULD_DOCKER_POSITIVE_BASELINE_SEQUENCE_HELPER`, `VULD_DOCKER_POSITIVE_BASELINE_DIRECT_HELPER`, `VULD_DOCKER_POSITIVE_BASELINE_PROMOTION_HELPER`, `VULD_DOCKER_POSITIVE_BASELINE_DOCKER_RETRY_COUNT`, `VULD_DOCKER_POSITIVE_BASELINE_DOCKER_RETRY_DELAY_SEC` seam으로 helper bundle regression을 지원한다.
- positive direct validation helper는 `VULD_POSITIVE_DIRECT_PRESET_HELPER`, `VULD_POSITIVE_DIRECT_PYTHON_BIN`, `VULD_POSITIVE_DIRECT_CASES_ROOT`, `VULD_POSITIVE_DIRECT_OUTPUT_ROOT`, `VULD_POSITIVE_DIRECT_MODE`, `VULD_POSITIVE_DIRECT_NO_SNAPSHOT`, `VULD_POSITIVE_DIRECT_HELPER` seam으로 fake python regression을 지원한다.
- positive direct validation helper는 latest slice에서 `ops/ci/run_named_preset_case_set.sh`, `ops/ci/run_named_direct_case_set.sh`, `ops/ci/lib_case_spec_presets.sh`를 통해 pair alias wiring을 공통화한다.
- repeatability matrix helper는 `VULD_REPEAT_MATRIX_PYTHON_BIN`, `VULD_REPEAT_MATRIX_CASES_ROOT`, `VULD_REPEAT_MATRIX_OUTPUT_ROOT`, `VULD_REPEAT_MATRIX_MODE`, `VULD_REPEAT_MATRIX_ATTEMPTS`, `VULD_REPEAT_MATRIX_NO_SNAPSHOT`, `VULD_REPEAT_MATRIX_ALLOW_REPEAT_FAILURE_WITH_REPORT`, `VULD_REPEAT_MATRIX_DOCKER_RETRY_COUNT`, `VULD_REPEAT_MATRIX_DOCKER_RETRY_DELAY_SEC`, `VULD_REPEAT_MATRIX_REPEAT_HELPER` seam으로 fake python regression을 지원하고, latest slice에서는 `ops/ci/run_repeatability_chain.sh`를 재사용한다.
- repeatability helper는 `VULD_REPEAT_PYTHON_BIN` seam으로 fake python regression도 지원한다.
- e2e entry helper는 `VULD_E2E_CASES_DIR`, `VULD_E2E_CONFIG_PATH`, `VULD_E2E_PYTHON_BIN`, `VULD_E2E_PYTEST_BIN`, `VULD_E2E_REPEAT_HELPER` seam으로 temp case dir/config/fake pytest/repeat helper regression을 지원한다.
- positive pair promotion helper는 `VULD_POSITIVE_PAIR_PRESET_HELPER`, `VULD_POSITIVE_PAIR_PYTHON_BIN`, `VULD_POSITIVE_PAIR_CASES_ROOT`, `VULD_POSITIVE_PAIR_OUTPUT_ROOT`, `VULD_POSITIVE_PAIR_MODE`, `VULD_POSITIVE_PAIR_NO_SNAPSHOT`, `VULD_POSITIVE_PAIR_DOCKER_RETRY_COUNT`, `VULD_POSITIVE_PAIR_DOCKER_RETRY_DELAY_SEC`, `VULD_POSITIVE_PAIR_SUPPORT_HELPER` seam으로 fake python regression을 지원하고, latest slice에서는 review-only `ops/ci/run_support_workflow_chain.sh`를 재사용한다.
- blocked/no-op support helper는 `VULD_BLOCKED_NOOP_PRESET_HELPER`, `VULD_BLOCKED_NOOP_PYTHON_BIN`, `VULD_BLOCKED_NOOP_CASES_ROOT`, `VULD_BLOCKED_NOOP_OUTPUT_ROOT`, `VULD_BLOCKED_NOOP_MODE`, `VULD_BLOCKED_NOOP_ATTEMPTS`, `VULD_BLOCKED_NOOP_NO_SNAPSHOT`, `VULD_BLOCKED_NOOP_DOCKER_RETRY_COUNT`, `VULD_BLOCKED_NOOP_DOCKER_RETRY_DELAY_SEC`, `VULD_BLOCKED_NOOP_SUPPORT_HELPER` seam으로 fake python regression을 지원하고, latest slice에서는 generic `ops/ci/run_support_workflow_chain.sh`를 `foobar`, `strict` alias output path로 재사용한다.
- positive pair promotion helper와 blocked/no-op helper는 latest slice에서 `ops/ci/run_named_preset_case_set.sh`, `ops/ci/run_named_support_case_set.sh`, `ops/ci/lib_case_spec_presets.sh`를 통해 pair alias wiring을 공통화한다.
- latest slice에서는 same pair/triple wrapper의 executable gate도 `ops/ci/lib_operator_named_preset_helpers.sh`로 공통화했고, positive-direct / low-cost / promotion / blocked wrapper는 `ops/ci/lib_operator_named_case_env.sh`를 함께 재사용한다.
- reviewable accept-path helper와 blocked/no-op helper는 latest slice에서 review/update/apply 공통부를 `ops/ci/run_support_review_chain.sh`로 정렬한다.
- synthetic reviewable accept path를 빠르게 재현하고 싶으면 `ops/ci/run_reviewable_support_accept_check.sh`를 사용한다.
- reviewable accept path와 blocked/no-op path를 함께 보려면 `ops/ci/run_support_workflow_operator_baseline.sh`를 먼저 쓴다.
- run-case helper는 `VULD_RUN_CASE_PYTHON_BIN`, `VULD_RUN_CASE_DOCKER_BIN` seam으로 fake python/docker regression을 지원하고 pipeline returncode를 그대로 전파한다.
- base example helper는 `VULD_BASE_REQUIREMENT_FILE`, `VULD_BASE_RUN_CASE_SCRIPT`, `VULD_BASE_EXAMPLE_SCRIPT` override seam으로 fake runner regression을 지원한다.
- custom vuln helper는 `VULD_CUSTOM_BASE_REQUIREMENT_FILE`, `VULD_CUSTOM_RUN_CASE_SCRIPT` override seam으로 temp requirement + fake runner regression을 지원한다.
- smoke regression helper는 `VULD_SMOKE_DOCKER_BIN`, `VULD_SMOKE_PYTHON_BIN`, `VULD_SMOKE_FLOW_SCRIPT`, `VULD_SMOKE_SNAPSHOT` seam으로 fake docker/flow regression을 지원한다.
- low-cost no-Docker direct lanes:
  - `ops/ci/run_direct_validation_chain.sh open-redirect-strict-dynamic-no-remote open-redirect-strict-dynamic-stub foobar-name-only-negative`
  - `ops/ci/run_low_cost_no_docker_validation.sh`
  - `python tests/e2e/run_case.py --case tests/e2e/cases/open-redirect-strict-dynamic-no-remote --mode deterministic --no-snapshot --output-dir /tmp/vuld_strict_no_remote`
  - `python tests/e2e/run_case.py --case tests/e2e/cases/open-redirect-strict-dynamic-stub --mode deterministic --no-snapshot --output-dir /tmp/vuld_strict_stub`
  - `python tests/e2e/run_case.py --case tests/e2e/cases/foobar-name-only-negative --mode deterministic --no-snapshot --output-dir /tmp/vuld_negative`
- Docker-enabled positive LLM-shaped lane:
  - `ops/ci/run_direct_validation_chain.sh trusted-dynamic-sqli open-redirect-dynamic-name-only`
  - `ops/ci/run_docker_positive_operator_baseline.sh`
  - `ops/ci/run_positive_direct_validation.sh`
  - `python tests/e2e/run_case.py --case tests/e2e/cases/trusted-dynamic-sqli --mode deterministic --no-snapshot --output-dir /tmp/vuld_trusted_dynamic`
- representative E2E:
  - `open-redirect-dynamic-name-only`
  - `open-redirect-strict-dynamic-no-remote`
  - `open-redirect-strict-dynamic-stub`
  - `trusted-dynamic-sqli`
  - `sqli-name-only`
  - `foobar-name-only-negative`

## Validation Routing

- `TKT-001` ~ `TKT-007`
  - 먼저 [tests/e2e/README.md](../tests/e2e/README.md)의 case/rerun 흐름을 보고, 이후 [docs/work_tickets.md](work_tickets.md)의 entrypoint/validation 표와 subsystem code docs를 따라간다.
- `TKT-008`
  - 먼저 `ops/ci/run_measured_gate_operator_baseline.sh`와 [tests/e2e/README.md](../tests/e2e/README.md)의 `Measured Gate Operator Baseline`, `Repeatability Matrix Check`, measured artifact 설명을 본다.
  - low-cost no-Docker rehearsal은 `foobar-name-only-negative` + `open-redirect-strict-dynamic-no-remote` pair를 우선 사용한다.
- `TKT-009`
  - 먼저 `ops/ci/run_support_workflow_chain.sh`와 [tests/e2e/README.md](../tests/e2e/README.md)의 `Generic Support Workflow Chain`, registry preview/apply 설명을 본다.
  - blocked/no-op rehearsal은 `foobar-name-only-negative` + `open-redirect-strict-dynamic-no-remote` pair output을 우선 사용한다.
- representative executed lane이 필요한 ticket는 Docker availability가 전제다.

## Validation Reading Order

이 순서는 [docs/work_tickets.md](work_tickets.md)의 `Validation Reading Order`를 따른다.

1. [docs/work_tickets.md](work_tickets.md)의 `Validation Routing`
2. [tests/e2e/README.md](../tests/e2e/README.md)의 harness command / case layout
3. [docs/code/README.md](code/README.md)와 subsystem docs의 code entrypoint
4. 이 문서의 artifact map / troubleshooting

## Completion Review Entry

운영/검증 관점에서 완료판정을 검토할 때는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Review Flow`를 먼저 보고, 이후 [tests/e2e/README.md](../tests/e2e/README.md)의 harness command, [docs/code/README.md](code/README.md)의 subsystem entrypoint, 이 문서의 `Open-World Axis Reading Hints`를 순서대로 따라간다.

## Completion Reading Order

support 문서 기준 completion reading order는 아래와 같다.

이 순서는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Reading Order`를 따른다.

1. [docs/work_tickets.md](work_tickets.md)의 `Completion Companions`
2. [tests/e2e/README.md](../tests/e2e/README.md)의 `Completion Review Entry`
3. [docs/code/README.md](code/README.md)의 `Completion Review Entry`
4. 이 문서의 `Completion Review Entry`

## Residual Review Entry

운영/검증 관점에서 current residual을 먼저 검토할 때는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Residual Ticket Breakdown`을 먼저 보고, 이후 same document의 `Open-World Completion Checklist`, [tests/e2e/README.md](../tests/e2e/README.md)의 harness command, 이 문서의 artifact reading hints를 순서대로 따라간다.
이 순서는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Residual Reading Order`를 따른다.

## Residual Reading Order

support 문서 기준 residual reading order는 아래와 같다.

1. [docs/work_tickets.md](work_tickets.md)의 `Open-World Residual Reading Order`
2. [tests/e2e/README.md](../tests/e2e/README.md)의 `Residual Review Entry`
3. [docs/code/README.md](code/README.md)의 `Residual Review Entry`
4. 이 문서의 `Residual Review Entry`

## Repeatability And Support Workflow

반복 실행과 measured support preview/local apply는 아래 순서로 본다.

1. generic helper: `ops/ci/run_support_workflow_chain.sh <CASE_SLUG_OR_DIR> [<CASE_SLUG_OR_DIR> ...]`
2. review-only preview가 필요하면: `VULD_SUPPORT_WORKFLOW_REVIEW_ONLY=1 ops/ci/run_support_workflow_chain.sh <CASE_SLUG_OR_DIR> ...`
3. explicit decisions payload를 쓰려면: `VULD_SUPPORT_WORKFLOW_DECISIONS_FILE=<DECISIONS_JSON> ops/ci/run_support_workflow_chain.sh <CASE_SLUG_OR_DIR> ...`
4. underlying command family:
   - repeatability: `python tests/e2e/repeat_case.py --case <CASE_DIR> --attempts 2 --mode deterministic --output-dir <OUT_DIR>`
   - review index: `python tests/e2e/support_review.py <OUT_DIR>/support_candidate.json ... --output <REVIEW_INDEX_JSON>`
   - decisions preview: `python tests/e2e/support_decide.py --review-index <REVIEW_INDEX_JSON> --decisions <DECISIONS_JSON> --output <REGISTRY_UPDATE_JSON>`
   - local apply: `python tests/e2e/support_apply.py --registry-update <REGISTRY_UPDATE_JSON> --output <CURATED_REGISTRY_JSON>`

latest low-cost no-Docker rehearsal pair는 아래다.

1. `python tests/e2e/repeat_case.py --case tests/e2e/cases/foobar-name-only-negative --attempts 2 --mode deterministic --output-dir /tmp/vuld_repeat_foobar`
2. `python tests/e2e/repeat_case.py --case tests/e2e/cases/open-redirect-strict-dynamic-no-remote --attempts 2 --mode deterministic --output-dir /tmp/vuld_repeat_strict`
3. `python tests/e2e/support_review.py /tmp/vuld_repeat_foobar /tmp/vuld_repeat_strict --output /tmp/vuld_support_review.json`
4. `python tests/e2e/support_decide.py --review-index /tmp/vuld_support_review.json --decisions /tmp/vuld_support_decisions.json --output /tmp/vuld_support_update.json`
5. `python tests/e2e/support_apply.py --registry-update /tmp/vuld_support_update.json --output /tmp/vuld_support_registry.json`

이 pair는 current truth 기준 `authority_ready_bundle_count > 0`이어도 `measured_gate_blocked_bundle_count > 0`, `reviewable_bundle_count = 0`, final `registry_item_count = 0` no-op로 끝나는 blocked/no-op policy regression용이다.
동일한 generic command family를 그대로 쓰고 싶으면 `ops/ci/run_support_workflow_chain.sh foobar-name-only-negative open-redirect-strict-dynamic-no-remote`를 먼저 본다.

현재 workflow가 보존하는 operator-facing vocabulary는 아래와 같다.

- `repeatability_report.json`: `measured_gate`, `observed_execution_salts`, `distinct_sid_count`
- `support_review_index.json`: `by_support_status`, `by_case_status`, `all_reviewable_cases`, `mixed_cases`, `all_blocked_cases`
- `support_registry_update.json`: `accepted/rejected/pending_by_support_status`, `by_case_status`, explicit case lists
- `curated_support_registry.json`: `by_review_status`, `by_support_status`, `by_case_review_status`, `all_accepted_cases`, `mixed_review_status_cases`, `all_rejected_cases`, `last_update`

## Status Cheatsheet

operator가 measured/support artifact를 읽을 때는 아래처럼 해석한다.

- `measured_gate.ready=false`
  - repeatability CLI가 고장났다는 뜻이 아니다
  - current lane이 promotion/measured policy를 아직 통과하지 못했다는 뜻이다
- `support_status=reviewable`
  - current measured/manual workflow 안에서 reviewer decision 대상으로 올릴 수 있다는 뜻이다
- `support_status=mechanically_blocked`
  - runtime/measured/authority blocker 때문에 review queue로 올리면 안 된다는 뜻이다
- `support_status=mechanically_healthy_policy_blocked`
  - artifact는 어느 정도 동작하지만 current promotion policy상 올리지 않는다는 뜻이다
- `support_status=blocked_mixed`
  - mechanical blocker와 policy blocker가 함께 섞여 있다는 뜻이다
- `support_status=blocked_unclassified`
  - 주로 legacy/default normalization에서 온 blocked state이며, current blocker class가 세밀하게 복원되지 않았다는 뜻이다
- `by_case_status.all_reviewable`
  - 그 case의 measured bundle들이 모두 reviewable이라는 뜻이다
- `by_case_status.mixed_reviewability`
  - 같은 case 안에 reviewable과 blocked bundle이 섞여 있다는 뜻이다
- `by_case_status.all_blocked`
  - 그 case는 current workflow에서 전부 blocked라는 뜻이다
- `by_case_review_status.all_accepted`
  - local registry current state에서 그 case의 stored item들이 모두 accepted라는 뜻이다
- `by_case_review_status.mixed_review_status`
  - local registry current state에서 accepted/rejected state가 섞여 있다는 뜻이다
- `by_case_review_status.all_rejected`
  - local registry current state에서 그 case는 rejected state만 남아 있다는 뜻이다

## Troubleshooting Entry Points

- Docker / WSL integration 문제: 먼저 `docker ps`를 실행한다. current WSL distro에서 `docker` command 자체가 없으면 Docker Desktop WSL integration을 켠 뒤 다시 확인한다.
- strict dynamic가 어디서 fail-closed 되었는지 빠르게 구분하고 싶으면:
  - remote-research capability 경계는 `open-redirect-strict-dynamic-no-remote`
  - live-LLM capability 경계는 `open-redirect-strict-dynamic-stub`
  - unsupported semantic abstain 경계는 `foobar-name-only-negative`
- positive LLM-shaped lane를 보고 싶으면 `trusted-dynamic-sqli`를 대표 lane로 본다. latest Docker-enabled rerun에서는 expectation을 통과했지만 `llm_fixture` / `llm_manifest`, `thin_or_incomplete`, measured-gate blocked로 남았다는 점을 같이 읽는다.
- positive dynamic representative lane `open-redirect-dynamic-name-only`는 actual runtime/oracle path를 다시 열었지만 `llm_degraded` / `deterministic_fallback` / `partial`로 남았다. operator 관점의 ticket 해석은 [docs/work_tickets.md](work_tickets.md)의 `Assessment-To-Ticket Interpretation`을 같이 본다.
- same direct rerun command family는 `ops/ci/run_positive_direct_validation.sh` helper로도 바로 실행할 수 있다.
- positive pair의 promotion 경계를 보고 싶으면 `trusted-dynamic-sqli` + `open-redirect-dynamic-name-only`를 `repeat_case -> support_review`로 같이 본다. latest fresh rerun 기준으로는 `authority_ready_bundle_count=2`, `measured_gate_blocked_bundle_count=2`, `reviewable_bundle_count=0`, `by_generation_non_live_reason={fixture_backed:1, provider_disabled:1}`로 남는다.
- direct rerun + promotion-check를 같이 보려면 `ops/ci/run_docker_positive_operator_baseline.sh`를 먼저 쓴다.
- same command family는 `ops/ci/run_positive_pair_promotion_check.sh` helper로도 바로 실행할 수 있다.
  - `python tests/e2e/repeat_case.py --case tests/e2e/cases/trusted-dynamic-sqli --expectations tests/e2e/cases/trusted-dynamic-sqli/expectations.json --mode deterministic --no-snapshot --output-dir /tmp/vuld_repeat_trusted_dynamic`
  - `python tests/e2e/repeat_case.py --case tests/e2e/cases/open-redirect-dynamic-name-only --expectations tests/e2e/cases/open-redirect-dynamic-name-only/expectations.json --mode deterministic --no-snapshot --output-dir /tmp/vuld_repeat_open_redirect_dynamic`
  - `python tests/e2e/support_review.py /tmp/vuld_repeat_trusted_dynamic /tmp/vuld_repeat_open_redirect_dynamic --output /tmp/vuld_support_review_positive_pair.json`
  - canonical command reference는 [tests/e2e/README.md](../tests/e2e/README.md)의 `Positive Pair Promotion Check`
- latest slice 이후에는 동일 command family를 review-only `ops/ci/run_support_workflow_chain.sh trusted-dynamic-sqli=trusted_dynamic open-redirect-dynamic-name-only=open_redirect_dynamic`로도 재현할 수 있다.
- latest helper semantics에서는 same two helpers가 `repeatability_report.json`이 남은 blocked lane의 `repeat_case.py` nonzero를 허용하고 support review까지 계속 진행한다. same repeat helper는 transient docker readiness failure도 retry seam으로 흡수하고, `docker daemon permission denied`는 permission-artifact note로 따로 surface한다. unrestricted Docker-enabled helper rerun에서는 positive-pair helper가 다시 `blocked_mixed` aggregate truth와 정렬된다. manual `repeat_case.py` + `support_review.py` chain은 계속 step-by-step authoritative reproduction path로 유효하다.
- current workspace-local direct verification에서는 same sandbox helper output이 empty aggregate(`authority_ready_bundle_count=0`, `reviewable_bundle_count=0`, `by_support_status={}`)로 끝날 수도 다시 확인됐다. operator는 이 경우 helper output을 runtime-equivalent truth로 보지 말고, unrestricted helper rerun 또는 manual `repeat_case.py + support_review.py` chain을 우선해야 한다.
- latest slice에서는 named support/matrix wrapper와 measured/no-docker baseline뿐 아니라 support baseline, docker-positive baseline, current baseline도 custom permission-artifact marker name(`VULD_NAMED_SUPPORT_PERMISSION_ARTIFACT_NAME`, `VULD_NAMED_MATRIX_PERMISSION_ARTIFACT_NAME`, `VULD_MEASURED_BASELINE_PERMISSION_ARTIFACT_NAME`, `VULD_NO_DOCKER_BASELINE_PERMISSION_ARTIFACT_NAME`, `VULD_SUPPORT_BASELINE_PERMISSION_ARTIFACT_NAME`, `VULD_DOCKER_POSITIVE_BASELINE_PERMISSION_ARTIFACT_NAME`, `VULD_CURRENT_BASELINE_PERMISSION_ARTIFACT_NAME`)을 하위 helper까지 그대로 forward한다.
- latest slice에서는 support workflow helper가 output root에 machine-readable `permission_artifact_summary.json`도 남기며, support-family wrapper는 `VULD_SUPPORT_WORKFLOW_PERMISSION_SUMMARY_NAME`, `VULD_NAMED_SUPPORT_PERMISSION_SUMMARY_NAME`, `VULD_POSITIVE_PAIR_PERMISSION_SUMMARY_NAME`, `VULD_BLOCKED_NOOP_PERMISSION_SUMMARY_NAME`으로 filename을 바꿀 수 있다.
- latest slice에서는 repeatability matrix helper family도 같은 summary contract를 가진다. `ops/ci/run_repeatability_matrix_check.sh`는 output root에 machine-readable `permission_artifact_summary.json`을 남기고, `VULD_REPEAT_MATRIX_PERMISSION_SUMMARY_NAME`, `VULD_NAMED_MATRIX_PERMISSION_SUMMARY_NAME`, `VULD_MEASURED_BASELINE_PERMISSION_SUMMARY_NAME`, `VULD_NO_DOCKER_BASELINE_PERMISSION_SUMMARY_NAME`으로 filename을 바꿀 수 있다.
- latest slice에서는 same helper가 `summary.json`이 없는 repeatability-only run directory도 직접 rollup하므로, planning-only no-Docker pair의 real helper run도 `matrix_report.json`까지 끝까지 만든다.
- latest slice에서는 support/matrix helper의 permission-artifact scan/note도 `ops/ci/lib_repeatability_permission_artifacts.sh`로 공통화됐고, same case-slug projection과 note formatting은 direct regression으로 고정된다.
- latest slice에서는 support/matrix helper의 repeat post-process(run-dir load + permission note + machine-readable summary materialization)도 `ops/ci/lib_repeatability_postprocess.sh`로 공통화됐고, same contract는 direct regression으로 고정된다.
- latest slice에서는 support/matrix helper의 repeat-helper executable gate도 `ops/ci/lib_repeatability_helper_contract.sh`로 공통화됐고, same contract는 direct regression으로 고정된다.
- latest slice에서는 `run_named_case_set.sh` / `run_named_preset_case_set.sh`의 target-helper executable gate도 `ops/ci/lib_named_case_helper_contract.sh`로 공통화됐고, same contract는 direct regression으로 고정된다.
- latest slice에서는 `run_named_preset_case_set.sh`의 preset-builder required/known gate도 `ops/ci/lib_case_spec_preset_contract.sh`로 공통화됐고, same contract는 direct regression으로 고정된다.
- latest slice에서는 support review helper family의 `VULD_SUPPORT_REVIEW_*` env, prefix-aware single/batch output-name defaults, review-helper executable gate, decisions-file materialization, run-directory validation, completion/output note, single/batch output path resolution도 `ops/ci/lib_support_review_env.sh`, `ops/ci/lib_support_review_output_defaults.sh`, `ops/ci/lib_support_review_helper_contract.sh`, `ops/ci/lib_support_review_output_notes.sh`, `ops/ci/lib_support_review_run_dirs.sh`, `ops/ci/lib_support_review_outputs.sh`로 공통화됐고, generic `VULD_SUPPORT_REVIEW_RESOLVED_*`뿐 아니라 `${PREFIX}_RESOLVED_*` output surface와 `support_review_emit_prefixed_*` / `support_review_emit_resolved_*` helpers까지 same note family로 닫혔다. same contract는 direct regression으로 고정된다.
- researcher/evidence 문제: `metadata/<SID>/search_traces/`, `researcher_report.json`
- generator 문제: `metadata/<SID>/generator_manifest.json`, `generator_failures.jsonl`
- executor 문제: `artifacts/<SID>/build/build.log`, `artifacts/<SID>/run/run.log`
- verifier 문제: `artifacts/<SID>/reports/evals.json`, `docs/guardrails_dynamic.md`
- pack/summary 문제: `metadata/<SID>/manifest.json`
- measured/support blocked-no-op policy를 빠르게 재현하고 싶으면 `foobar-name-only-negative` + `open-redirect-strict-dynamic-no-remote` pair의 `repeat_case -> support_review -> support_decide -> support_apply` chain을 먼저 본다.
- same command family는 `ops/ci/run_blocked_noop_support_check.sh` helper로도 바로 실행할 수 있다.
- arbitrary case 조합으로 같은 command family를 재현하려면 `ops/ci/run_support_workflow_chain.sh <CASE_SLUG_OR_DIR> ...`를 먼저 쓴다.
- low-cost policy/support 문서 보강 이후 regression만 빠르게 확인하고 싶으면 focused no-Docker regression slice를 먼저 본다. 이 slice는 current direct verification 기준 `TKT-001-E`, `TKT-008-A1`, `TKT-009-A2`와 가장 가깝다.

## Safety Notes

- `promotion_eligible`와 generalized support claim은 다릅니다. 판단 기준은 [docs/constraints.md](constraints.md)를 따릅니다.
- degraded deterministic fallback은 runnable일 수 있어도 open-world success로 주장하지 않습니다.
- 외부 네트워크나 sidecar 사용은 policy와 evidence가 정렬된 경우에만 허용합니다.
- local registry/apply workflow가 존재해도 이것을 자동 curated promotion loop completion으로 읽지 않습니다.

## How To Update This Document

- operator command, quickstart, artifact location, troubleshooting flow가 바뀔 때만 갱신한다.
- current rerun truth나 completeness 평가는 [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)에 남긴다.
- current non-claim, status interpretation 한계, Docker precondition은 [docs/constraints.md](constraints.md)에 남긴다.
- phase ordering과 actionable backlog는 [docs/final_solution.md](final_solution.md), [docs/work_tickets.md](work_tickets.md)로 보낸다.
- artifact path/token이 바뀌면 [docs/code/workspaces.md](code/workspaces.md)와 같이 맞춘다.
- success criteria 5축과 artifact 대응이 바뀌면 `Open-World Axis Reading Hints`도 같이 갱신한다.
- operator가 참조하는 ticket별 primary validation focus가 바뀌면 [docs/work_tickets.md](work_tickets.md)의 entrypoint/validation 표와 같이 갱신한다.
- validation harness entry flow가 바뀌면 [tests/e2e/README.md](../tests/e2e/README.md)와 같이 갱신한다.
- validation reading order가 바뀌면 [README.md](../README.md), [docs/code/README.md](code/README.md)와 같이 갱신한다.
- validation companion 관계가 바뀌면 [README.md](../README.md), [docs/code/README.md](code/README.md), [tests/e2e/README.md](../tests/e2e/README.md)와 같이 갱신한다.
- validation question routing이 바뀌면 [docs/work_tickets.md](work_tickets.md)와 같이 갱신한다.
- completion companion 관계가 바뀌면 [README.md](../README.md), [docs/code/README.md](code/README.md), [tests/e2e/README.md](../tests/e2e/README.md)와 같이 갱신한다.
- priority companion 관계나 priority review entry가 바뀌면 [README.md](../README.md), [docs/code/README.md](code/README.md), [tests/e2e/README.md](../tests/e2e/README.md)와 같이 갱신한다.
- LLM-response stricter reading의 operator-side routing이 바뀌면 [docs/work_tickets.md](work_tickets.md)의 `LLM-Response Capability Overlay`와 같이 갱신한다.
- latest positive representative pair의 ticket-form 해석이 바뀌면 [docs/work_tickets.md](work_tickets.md)의 `Assessment-To-Ticket Interpretation`와 같이 갱신한다.
- residual companion 관계가 바뀌면 [README.md](../README.md), [docs/code/README.md](code/README.md), [tests/e2e/README.md](../tests/e2e/README.md)와 같이 갱신한다.
- residual question routing이 바뀌면 [docs/work_tickets.md](work_tickets.md)와 같이 갱신한다.
- completion review entrypoint가 바뀌면 [README.md](../README.md), [docs/code/README.md](code/README.md), [tests/e2e/README.md](../tests/e2e/README.md)와 같이 갱신한다.
- completion reading order가 바뀌면 [README.md](../README.md), [docs/code/README.md](code/README.md), [tests/e2e/README.md](../tests/e2e/README.md)와 같이 갱신한다.
- residual review entrypoint가 바뀌면 [README.md](../README.md), [docs/code/README.md](code/README.md), [tests/e2e/README.md](../tests/e2e/README.md)와 같이 갱신한다.
- residual reading order가 바뀌면 [README.md](../README.md), [docs/code/README.md](code/README.md), [tests/e2e/README.md](../tests/e2e/README.md)와 같이 갱신한다.
- review mode entry shortcuts가 바뀌면 [README.md](../README.md), [docs/code/README.md](code/README.md), [tests/e2e/README.md](../tests/e2e/README.md)와 같이 갱신한다.
- 잔여 작업량/turn envelope 해석이 바뀌면 [docs/work_tickets.md](work_tickets.md)의 `Estimated Turn Envelope`와 README/code/e2e companion의 priority routing도 같이 갱신한다.
- [docs/work_tickets.md](work_tickets.md)의 `Turn Estimate Entry`가 바뀌면 README/code/e2e companion의 same shortcut도 같이 갱신한다.
- no-Docker operator baseline helper는 latest slice에서 `VULD_NO_DOCKER_BASELINE_SEQUENCE_HELPER` seam을 통해 generic `ops/ci/run_helper_sequence.sh`를 재사용한다.
- current operator baseline helper는 latest slice에서 `VULD_CURRENT_BASELINE_SEQUENCE_HELPER` seam을 통해 generic `ops/ci/run_helper_sequence.sh`를 재사용한다.
- low-cost direct validation helper는 `VULD_LOW_COST_NO_SNAPSHOT`, `VULD_LOW_COST_DIRECT_HELPER` seam으로 generic direct-chain reuse까지 regression 고정한다.
- generic helper bundle executor는 `ops/ci/run_helper_sequence.sh`이며 operator baseline wrappers의 ordered sub-helper execution contract를 공통화한다.
