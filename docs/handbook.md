# vulDocker 핸드북

Status: support
Audience: operator
Source of truth for: quickstart, command map, artifact locations, troubleshooting entrypoints
Not the source of truth for: current-state assessment, constraints, roadmap
Last validated against: repository commands, support/repeatability workflow, and representative reruns on 2026-03-19

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
- actionable subtask는 [docs/work_tickets.md](work_tickets.md)를 우선
- 이 문서는 실행 절차와 artifact 해석만 담당

현재 실행 순서와 owner를 바로 확인하려면:
- phase-to-ticket translation: [docs/final_solution.md](final_solution.md)
- phase acceptance -> validation surface map: [docs/final_solution.md](final_solution.md)
- priority board / sequencing rule / current remaining snapshot: [docs/work_tickets.md](work_tickets.md)
- code entrypoints / representative validation surface by ticket: [docs/work_tickets.md](work_tickets.md)
- validation harness / case layout / repeatability-support workflow details: [tests/e2e/README.md](../tests/e2e/README.md)

## Validation Companions

운영/검증 관점에서 이 문서와 같이 봐야 할 companion은 아래와 같다.

- success criteria 5축과 backlog owner 대응: [docs/work_tickets.md](work_tickets.md)
- completion companion set: [docs/work_tickets.md](work_tickets.md)의 `Completion Companions`
- success criteria 5축의 완료판정 질문과 최소 근거: [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Checklist`
- success criteria 5축의 canonical 완료 검토 순서: [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Review Flow`
- success criteria 5축의 canonical 완료판정 reading order: [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Reading Order`
- latest confirmed residual의 축별 ticket bundle 분해: [docs/work_tickets.md](work_tickets.md)의 `Open-World Residual Ticket Breakdown`
- latest confirmed residual의 canonical 구현 검토 순서: [docs/work_tickets.md](work_tickets.md)의 `Open-World Residual Review Flow`
- latest confirmed residual 검토 문서 순서: [docs/work_tickets.md](work_tickets.md)의 `Open-World Residual Reading Order`
- residual companion set: [docs/work_tickets.md](work_tickets.md)의 `Residual Companions`
- review mode별 canonical 시작점: [docs/work_tickets.md](work_tickets.md)의 `Review Mode Matrix`
- phase acceptance와 validation surface 대응: [docs/final_solution.md](final_solution.md)
- ticket별 first harness와 reading order: [docs/work_tickets.md](work_tickets.md)
- concrete rerun/support harness command: [tests/e2e/README.md](../tests/e2e/README.md)
- code entrypoint와 subsystem owner: [docs/code/README.md](code/README.md)
- success criteria 5축별 artifact reading hints: 이 문서의 `Open-World Axis Reading Hints`, [docs/code/workspaces.md](code/workspaces.md)의 `Open-World Axis Artifact Hints`
- current truth와 observed rerun evidence: [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)
- 질문 기반 routing: [docs/work_tickets.md](work_tickets.md)의 `Validation Question Routing`
- residual 질문 기반 routing: [docs/work_tickets.md](work_tickets.md)의 `Residual Question Routing`

## Completion Companions

운영/완료판정 관점에서 이 문서와 같이 봐야 할 companion은 아래와 같다.

- completion companion set: [docs/work_tickets.md](work_tickets.md)의 `Completion Companions`
- axis map / close criteria / canonical review order: [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Axis Map`, `Open-World Completion Checklist`, `Open-World Completion Review Flow`
- canonical completion reading order: [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Reading Order`
- phase acceptance map: [docs/final_solution.md](final_solution.md)의 `Acceptance-To-Validation Translation`
- harness entry: [tests/e2e/README.md](../tests/e2e/README.md)
- code entrypoint: [docs/code/README.md](code/README.md)
- artifact reading / troubleshooting: 이 문서의 `Open-World Axis Reading Hints`
- current truth / non-claim: [docs/current_state_gap_analysis.md](current_state_gap_analysis.md), [docs/constraints.md](constraints.md)

## Residual Companions

운영/잔여 구현 검토 관점에서 이 문서와 같이 봐야 할 companion은 아래와 같다.

- residual bucket / ticket bundle: [docs/work_tickets.md](work_tickets.md)의 `Open-World Residual Ticket Breakdown`
- residual close criteria: [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Checklist`
- residual review / reading order: [docs/work_tickets.md](work_tickets.md)의 `Open-World Residual Review Flow`, `Open-World Residual Reading Order`
- phase acceptance map: [docs/final_solution.md](final_solution.md)의 `Acceptance-To-Validation Translation`
- code entrypoint / residual focus: [docs/code/README.md](code/README.md)
- current truth / non-claim: [docs/current_state_gap_analysis.md](current_state_gap_analysis.md), [docs/constraints.md](constraints.md)

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
- `metadata/<SID>/manifest.json` or `metadata/<SID>/failure_manifest.json`: pack summary / failure summary
- `metadata/<SID>/reviewer_reports.json`: reviewer report index
- `metadata/<SID>/loop_state.json`: loop / retry state
- `metadata/<SID>/performance_summary.json`: search/cache/perf observation summary
- `workspaces/<SID>/app/`: generated bundle
- `artifacts/<SID>/build/`: build log and SBOM
- `artifacts/<SID>/run/`: run log and run summary
- `artifacts/<SID>/run/oracle_execution.json`: payload replay / oracle execution trace when present
- `artifacts/<SID>/reports/evals.json`: verifier result
- `<OUT_DIR>/repeatability_report.json`: measured repeatability summary, `measured_gate`, `observed_execution_salts`
- `<OUT_DIR>/matrix_report.json`: case-matrix rollup, quality observations, measured-gate observations
- `<OUT_DIR>/support_candidate.json`: measured support candidate with blocker classes and support status
- `support_review_index.json`: review queue aggregate, `by_case_status`, explicit case lists
- `support_registry_update.json`: decision preview, `accepted/rejected/pending_by_support_status`, case-level aggregate
- `curated_support_registry.json`: local registry current state, `by_case_review_status`, `last_update`, schema/provenance history

## Open-World Axis Reading Hints

[docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Axis Map`을 실제 artifact에 대응시킬 때는 아래처럼 읽는다.

- 선택
  - `metadata/<SID>/plan.json`
  - `metadata/<SID>/researcher_report.json`
  - `summary.json`의 `request_ir`, `request_ir_summary`, `selection_decision`, `name_only_outcome`
  - family/stack/topology/oracle 선택이 evidence-backed인지, `ready_for_materialization`과 `open_world_evidence_ready`가 어디서 멈췄는지 본다.
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
- `python -m pytest -q tests/test_repeatability_gate.py tests/test_support_extract.py`
- `python -m pytest -q tests/e2e/test_support_workflow.py tests/e2e/test_case_matrix_rollup.py`
- representative E2E:
  - `open-redirect-dynamic-name-only`
  - `open-redirect-strict-dynamic-no-remote`
  - `sqli-name-only`
  - `foobar-name-only-negative`

## Validation Routing

- `TKT-001` ~ `TKT-007`
  - 먼저 [tests/e2e/README.md](../tests/e2e/README.md)의 case/rerun 흐름을 보고, 이후 [docs/work_tickets.md](work_tickets.md)의 entrypoint/validation 표와 subsystem code docs를 따라간다.
- `TKT-008`
  - 먼저 `repeat_case.py` / `matrix_report.py` 흐름과 [tests/e2e/README.md](../tests/e2e/README.md)의 measured artifact 설명을 본다.
- `TKT-009`
  - 먼저 `support_review.py -> support_decide.py -> support_apply.py` 흐름과 [tests/e2e/README.md](../tests/e2e/README.md)의 registry preview/apply 설명을 본다.
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

1. repeatability: `python tests/e2e/repeat_case.py --case <CASE_DIR> --attempts 2 --mode deterministic --output-dir <OUT_DIR>`
2. review index: `python tests/e2e/support_review.py <OUT_DIR>/support_candidate.json ... --output <REVIEW_INDEX_JSON>`
3. decisions preview: `python tests/e2e/support_decide.py --review-index <REVIEW_INDEX_JSON> --decisions <DECISIONS_JSON> --output <REGISTRY_UPDATE_JSON>`
4. local apply: `python tests/e2e/support_apply.py --registry-update <REGISTRY_UPDATE_JSON> --output <CURATED_REGISTRY_JSON>`

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
- researcher/evidence 문제: `metadata/<SID>/search_traces/`, `researcher_report.json`
- generator 문제: `metadata/<SID>/generator_manifest.json`, `generator_failures.jsonl`
- executor 문제: `artifacts/<SID>/build/build.log`, `artifacts/<SID>/run/run.log`
- verifier 문제: `artifacts/<SID>/reports/evals.json`, `docs/guardrails_dynamic.md`
- pack/summary 문제: `metadata/<SID>/manifest.json`

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
- residual companion 관계가 바뀌면 [README.md](../README.md), [docs/code/README.md](code/README.md), [tests/e2e/README.md](../tests/e2e/README.md)와 같이 갱신한다.
- residual question routing이 바뀌면 [docs/work_tickets.md](work_tickets.md)와 같이 갱신한다.
- completion review entrypoint가 바뀌면 [README.md](../README.md), [docs/code/README.md](code/README.md), [tests/e2e/README.md](../tests/e2e/README.md)와 같이 갱신한다.
- completion reading order가 바뀌면 [README.md](../README.md), [docs/code/README.md](code/README.md), [tests/e2e/README.md](../tests/e2e/README.md)와 같이 갱신한다.
- residual review entrypoint가 바뀌면 [README.md](../README.md), [docs/code/README.md](code/README.md), [tests/e2e/README.md](../tests/e2e/README.md)와 같이 갱신한다.
- residual reading order가 바뀌면 [README.md](../README.md), [docs/code/README.md](code/README.md), [tests/e2e/README.md](../tests/e2e/README.md)와 같이 갱신한다.
- review mode entry shortcuts가 바뀌면 [README.md](../README.md), [docs/code/README.md](code/README.md), [tests/e2e/README.md](../tests/e2e/README.md)와 같이 갱신한다.
