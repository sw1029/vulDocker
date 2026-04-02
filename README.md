# LLM+RAG 기반 동적 취약 테스트베드 (vulDocker)

Status: support
Audience: mixed
Source of truth for: repository entrypoint, quickstart, document map
Not the source of truth for: current-state assessment, constraints, implementation roadmap
Last validated against: `python -m pytest -q tests`, `python -m pytest -q tests/test_ops_ci_*.py`, targeted repeatability/support regressions, and representative direct/repeatability/support execution checks on 2026-04-02

`vulDocker`는 LLM+RAG를 활용해 취약 환경을 자동 합성/보강하고, Docker에서 실행·검증·리뷰·패키징까지 이어지는 실험용 테스트베드입니다. 현재 시스템은 정직한 bounded regression platform과 일부 supported family에 대한 degraded dynamic generation을 제공하며, generalized open-world generator로는 아직 발전 중입니다.

## Read This First

문서를 읽는 권장 순서는 아래와 같습니다.

1. [문제 정의](docs/problem.md)
2. [현재 상태 / 갭 분석](docs/current_state_gap_analysis.md)
3. [제약조건](docs/constraints.md)
4. [구현 로드맵](docs/final_solution.md)
5. [핸드북](docs/handbook.md)
6. [코드 인덱스](docs/code/README.md)
7. [검증 하니스](tests/e2e/README.md)

## Quickstart

사전 요구
- Docker (rootless 권장)
- Python 3.11+
- git
- 선택: Syft 설치 시 SBOM 자동 생성
- WSL 2 사용 시: Docker Desktop WSL integration을 켜고 `docker ps`가 현재 distro에서 성공하는지 먼저 확인

설치
- `python -m venv .venv && source .venv/bin/activate`
- `pip install -r requirements.txt`

대표 실행
1. PLAN: `python orchestrator/plan.py --input inputs/mvp_sqli.yml`
2. E2E 루프: `python orchestrator/run_pipeline.py --sid <SID> --mode deterministic`
3. 단계별 실행이 필요하면 [핸드북](docs/handbook.md)의 quickstart를 따릅니다.

기본 검증
- Docker precheck: `docker ps`
- 단위 테스트: `python -m pytest -q tests`
- ops/ci helper contract bundle: `python -m pytest -q tests/test_ops_ci_*.py`
- current operator baseline: `ops/ci/run_current_operator_baseline.sh`
- no-Docker operator baseline: `ops/ci/run_no_docker_operator_baseline.sh` (`focused -> low_cost -> matrix -> blocked`)
- measured gate operator baseline: `ops/ci/run_measured_gate_operator_baseline.sh`
- generic repeatability chain: `ops/ci/run_repeatability_chain.sh open-redirect-strict-dynamic-no-remote foobar-name-only-negative`
- generic named caseset helper: `ops/ci/run_named_case_set.sh alpha-case=alpha beta-case=beta`
- generic direct validation chain: `ops/ci/run_direct_validation_chain.sh open-redirect-strict-dynamic-no-remote open-redirect-strict-dynamic-stub foobar-name-only-negative`
- support workflow baseline: `ops/ci/run_support_workflow_operator_baseline.sh`
- repeatability matrix check: `ops/ci/run_repeatability_matrix_check.sh foobar-name-only-negative open-redirect-strict-dynamic-no-remote`
- Docker-positive operator baseline: `ops/ci/run_docker_positive_operator_baseline.sh`
- focused no-Docker regression slice: `python -m pytest -q tests/test_name_only_helpers.py tests/test_pack_promotion.py tests/test_repeatability_gate.py tests/test_support_extract.py tests/e2e/test_support_workflow.py tests/e2e/test_case_matrix_rollup.py`
- 빠른 no-Docker direct check: `python tests/e2e/run_case.py --case tests/e2e/cases/open-redirect-strict-dynamic-no-remote --mode deterministic --no-snapshot --output-dir /tmp/vuld_strict_no_remote`
- strict live-LLM capability gate check: `python tests/e2e/run_case.py --case tests/e2e/cases/open-redirect-strict-dynamic-stub --mode deterministic --no-snapshot --output-dir /tmp/vuld_strict_stub`
- unsupported negative check: `python tests/e2e/run_case.py --case tests/e2e/cases/foobar-name-only-negative --mode deterministic --no-snapshot --output-dir /tmp/vuld_negative`
- repeatability/support preview check: `python tests/e2e/repeat_case.py --case tests/e2e/cases/foobar-name-only-negative --attempts 2 --mode deterministic --output-dir /tmp/vuld_repeat_negative`
- Docker-enabled representative E2E: `python tests/e2e/run_case.py --case tests/e2e/cases/open-redirect-dynamic-name-only --mode deterministic`
- Docker-enabled fixture-backed positive LLM-shaped lane: `python tests/e2e/run_case.py --case tests/e2e/cases/trusted-dynamic-sqli --mode deterministic --no-snapshot --output-dir /tmp/vuld_trusted_dynamic`
  current truth는 `runnable but not promotable`다. representative positive pair support review에서도 `authority_ready_bundle_count=2`, `measured_gate_blocked_bundle_count=2`, `reviewable_bundle_count=0`, `by_generation_non_live_reason={fixture_backed:1, provider_disabled:1}`로 남는다.
- positive pair promotion check: 자세한 command chain은 [tests/e2e/README.md](/home/ysw/vulDocker/tests/e2e/README.md)의 `Positive Pair Promotion Check`를 본다.
  latest helper semantics에서는 `repeat_case.py`가 nonzero여도 `repeatability_report.json`이 생성된 blocked lane이면 support review까지 계속 진행하고, transient docker readiness retry도 흡수한다. sandbox helper run에서 `docker daemon permission denied`가 나오면 marker와 note를 남기고, unrestricted Docker-enabled helper rerun에서는 same helper가 다시 manual truth와 같은 `blocked_mixed` aggregate로 정렬된다. 다만 current workspace-local direct verification에서는 same sandbox helper output이 `authority_ready_bundle_count=0`, `reviewable_bundle_count=0`, `by_support_status={}` empty aggregate로 끝날 수도 다시 확인됐고, per-case helper `repeatability_report.json`도 `passed=false`, `case_failed`, `quality_tier_inconsistent`, `verdict_authority_inconsistent`를 남길 수 있었다. same output root의 `permission_artifact_summary.json`가 `runtime_equivalent_helper_truth_available=false`, `recommended_action=unrestricted_docker_rerun`를 남기면 runtime-equivalent truth가 아니라 permission-artifact environment output으로 읽어야 한다. 이 distinction은 새 core residual이 아니라 계속 `TKT-008-B3`로만 읽는다. underlying manual chain은 여전히 가장 직접적인 step-by-step reproduction path로 유지된다.
- latest bounded `TKT-008-B3` slice에서는 [ops/ci/lib_case_chain_profile_target_forward.sh](/home/ysw/vulDocker/ops/ci/lib_case_chain_profile_target_forward.sh), [tests/test_ops_ci_case_chain_profile_target_forward.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_profile_target_forward.py), [ops/ci/lib_case_chain_profile_entrypoint.sh](/home/ysw/vulDocker/ops/ci/lib_case_chain_profile_entrypoint.sh), [ops/ci/lib_case_chain_main.sh](/home/ysw/vulDocker/ops/ci/lib_case_chain_main.sh), [ops/ci/lib_case_chain_main_script.sh](/home/ysw/vulDocker/ops/ci/lib_case_chain_main_script.sh) 가 direct/repeatability profile wrapper family의 shared `profile target forward` surface를 direct regression으로 공통화했다. current workspace-local helper contract bundle truth는 `python -m pytest -q tests/test_ops_ci_*.py -> 343 passed`이고, same slice는 core backlog priority를 바꾸지 않는다.
- current operator baseline helper와 세부 sub-baseline helper는 [tests/e2e/README.md](/home/ysw/vulDocker/tests/e2e/README.md)의 `Current Operator Baseline`, `No-Docker Operator Baseline`, `Measured Gate Operator Baseline`, `Generic Repeatability Chain`, `Generic Named Case Set`, `Generic Direct Validation Chain`, `Generic Support Workflow Chain`, `Repeatability Matrix Check`, `Support Workflow Operator Baseline`, `Docker Positive Operator Baseline`를 본다.

## Document Map

- `docs/problem.md`: 프로젝트가 풀고자 하는 문제와 success criteria
- `docs/current_state_gap_analysis.md`: 현재 truth, rerun 결과, 구조적 미비점
- `docs/constraints.md`: 현재 시스템의 기술·운영·평가 제약과 금지 claim
- `docs/final_solution.md`: 구현 우선순위와 phase-based roadmap
- `docs/work_tickets.md`: actionable backlog, subtask decomposition, residual-to-ticket mapping, turn estimate
- `docs/handbook.md`: 운영/온보딩/명령/아티팩트 해석
- `docs/guardrails_dynamic.md`: GuardSpec subsystem guide
- `docs/code/README.md`: 구현 엔지니어용 코드 탐색 인덱스
- `tests/e2e/README.md`: 검증 하니스, case layout, repeatability/support workflow 진입점

문서가 충돌해 보이면 아래 우선순위를 따릅니다.

- 현재 truth / 실행 결과: `docs/current_state_gap_analysis.md`
- 금지 claim / 현재 한계: `docs/constraints.md`
- phase 우선순위: `docs/final_solution.md`
- 실제 작업 분해 / 잔여 작업량 추산: `docs/work_tickets.md`
- 실행 절차 / 명령 / artifact path: `docs/handbook.md`

현재 구현 순서와 phase-owner 연결을 바로 보려면 아래를 함께 봅니다.

- phase-to-ticket map: [docs/final_solution.md](docs/final_solution.md)
- phase acceptance -> validation surface map: [docs/final_solution.md](docs/final_solution.md)
- current remaining snapshot / confirmed completion priority order / estimated turn envelope / sequencing rule: [docs/work_tickets.md](docs/work_tickets.md)
- current remaining shorthand routing: [docs/work_tickets.md](docs/work_tickets.md)의 `Current Remaining Ticket Routing`
- turn estimate entry: [docs/work_tickets.md](docs/work_tickets.md)의 `Turn Estimate Entry`
- code entrypoints / validation surface by ticket: [docs/work_tickets.md](docs/work_tickets.md)
- validation harness by ticket: [tests/e2e/README.md](tests/e2e/README.md)

## Validation Companions

검증 관점에서 이 문서와 같이 봐야 할 companion은 아래와 같습니다.

- success criteria 5축과 backlog owner 대응: [docs/work_tickets.md](docs/work_tickets.md)
- completion companion set: [docs/work_tickets.md](docs/work_tickets.md)의 `Completion Companions`
- priority companion set: [docs/work_tickets.md](docs/work_tickets.md)의 `Priority Companions`
- success criteria 5축의 완료판정 질문과 최소 근거: [docs/work_tickets.md](docs/work_tickets.md)의 `Open-World Completion Checklist`
- success criteria 5축의 canonical 완료 검토 순서: [docs/work_tickets.md](docs/work_tickets.md)의 `Open-World Completion Review Flow`
- success criteria 5축의 canonical 완료판정 reading order: [docs/work_tickets.md](docs/work_tickets.md)의 `Open-World Completion Reading Order`
- latest confirmed residual의 축별 ticket bundle 분해: [docs/work_tickets.md](docs/work_tickets.md)의 `Open-World Residual Ticket Breakdown`
- latest confirmed residual의 shorthand ticket routing: [docs/work_tickets.md](docs/work_tickets.md)의 `Current Remaining Ticket Routing`
- latest direct verification까지 반영한 current completion priority order: [docs/work_tickets.md](docs/work_tickets.md)의 `Confirmed Completion Priority Order`
- 잔여 작업량과 practical turn envelope: [docs/work_tickets.md](docs/work_tickets.md)의 `Estimated Turn Envelope`
- latest positive Docker-enabled rerun의 ticket-form 해석: [docs/work_tickets.md](docs/work_tickets.md)의 `Assessment-To-Ticket Interpretation`
- latest confirmed residual의 canonical 구현 검토 순서: [docs/work_tickets.md](docs/work_tickets.md)의 `Open-World Residual Review Flow`
- latest confirmed residual 검토 문서 순서: [docs/work_tickets.md](docs/work_tickets.md)의 `Open-World Residual Reading Order`
- residual companion set: [docs/work_tickets.md](docs/work_tickets.md)의 `Residual Companions`
- review mode별 canonical 시작점: [docs/work_tickets.md](docs/work_tickets.md)의 `Review Mode Matrix`
- 우선순위 판단 routing: [docs/work_tickets.md](docs/work_tickets.md)의 `Priority Question Routing`, `Priority Reading Order`, `Assessment-To-Ticket Interpretation`
- LLM-response 기준 residual/priority 해석: [docs/work_tickets.md](docs/work_tickets.md)의 `LLM-Response Capability Overlay`
- phase acceptance와 validation surface 대응: [docs/final_solution.md](docs/final_solution.md)
- ticket별 first harness와 reading order: [docs/work_tickets.md](docs/work_tickets.md)
- concrete rerun/support harness command: [tests/e2e/README.md](tests/e2e/README.md)
- code entrypoint와 subsystem owner: [docs/code/README.md](docs/code/README.md)
- artifact map / troubleshooting: [docs/handbook.md](docs/handbook.md)
- success criteria 5축별 artifact reading hints: [docs/handbook.md](docs/handbook.md), [docs/code/workspaces.md](docs/code/workspaces.md)
- 질문 기반 routing: [docs/work_tickets.md](docs/work_tickets.md)의 `Validation Question Routing`
- residual 질문 기반 routing: [docs/work_tickets.md](docs/work_tickets.md)의 `Residual Question Routing`

## Completion Companions

완료판정 관점에서 이 문서와 같이 봐야 할 companion은 아래와 같습니다.

- completion companion set: [docs/work_tickets.md](docs/work_tickets.md)의 `Completion Companions`
- priority companion set: [docs/work_tickets.md](docs/work_tickets.md)의 `Priority Companions`
- axis map / close criteria / canonical review order: [docs/work_tickets.md](docs/work_tickets.md)의 `Open-World Completion Axis Map`, `Open-World Completion Checklist`, `Open-World Completion Review Flow`
- canonical completion reading order: [docs/work_tickets.md](docs/work_tickets.md)의 `Open-World Completion Reading Order`
- current completion priority order: [docs/work_tickets.md](docs/work_tickets.md)의 `Confirmed Completion Priority Order`
- phase acceptance map: [docs/final_solution.md](docs/final_solution.md)의 `Acceptance-To-Validation Translation`
- harness entry: [tests/e2e/README.md](tests/e2e/README.md)
- code entrypoint: [docs/code/README.md](docs/code/README.md)
- artifact reading / troubleshooting: [docs/handbook.md](docs/handbook.md)
- current truth / non-claim: [docs/current_state_gap_analysis.md](docs/current_state_gap_analysis.md), [docs/constraints.md](docs/constraints.md)

## Residual Companions

잔여 구현 검토 관점에서 이 문서와 같이 봐야 할 companion은 아래와 같습니다.

- residual bucket / ticket bundle: [docs/work_tickets.md](docs/work_tickets.md)의 `Open-World Residual Ticket Breakdown`
- current completion priority order: [docs/work_tickets.md](docs/work_tickets.md)의 `Confirmed Completion Priority Order`
- latest positive representative pair의 ticket-form reading: [docs/work_tickets.md](docs/work_tickets.md)의 `Assessment-To-Ticket Interpretation`
- residual close criteria: [docs/work_tickets.md](docs/work_tickets.md)의 `Open-World Completion Checklist`
- residual review / reading order: [docs/work_tickets.md](docs/work_tickets.md)의 `Open-World Residual Review Flow`, `Open-World Residual Reading Order`
- phase acceptance map: [docs/final_solution.md](docs/final_solution.md)의 `Acceptance-To-Validation Translation`
- code entrypoint / residual focus: [docs/code/README.md](docs/code/README.md)
- artifact reading / troubleshooting: [docs/handbook.md](docs/handbook.md)
- current truth / non-claim: [docs/current_state_gap_analysis.md](docs/current_state_gap_analysis.md), [docs/constraints.md](docs/constraints.md)

## Priority Companions

우선순위 판단 관점에서 이 문서와 같이 봐야 할 companion은 아래와 같습니다.

- current completion priority order: [docs/work_tickets.md](docs/work_tickets.md)의 `Confirmed Completion Priority Order`
- 잔여 작업량과 practical turn envelope: [docs/work_tickets.md](docs/work_tickets.md)의 `Estimated Turn Envelope`
- priority companion set / routing / reading order: [docs/work_tickets.md](docs/work_tickets.md)의 `Priority Companions`, `Priority Question Routing`, `Priority Reading Order`
- latest positive representative pair의 ticket-form reading: [docs/work_tickets.md](docs/work_tickets.md)의 `Assessment-To-Ticket Interpretation`
- LLM-response 기준 residual/priority 해석: [docs/work_tickets.md](docs/work_tickets.md)의 `LLM-Response Capability Overlay`
- phase ordering / sequencing guardrail: [docs/final_solution.md](docs/final_solution.md), [docs/work_tickets.md](docs/work_tickets.md)의 `Sequencing Rule`
- current truth / non-claim: [docs/current_state_gap_analysis.md](docs/current_state_gap_analysis.md), [docs/constraints.md](docs/constraints.md)
- harness / code / artifact entry: [tests/e2e/README.md](tests/e2e/README.md), [docs/code/README.md](docs/code/README.md), [docs/handbook.md](docs/handbook.md)

## Review Mode Entry

지금 무엇을 하려는지에 따라 아래 entry를 먼저 고릅니다.

- 검증:
  - [docs/work_tickets.md](docs/work_tickets.md)의 `Review Mode Matrix`
  - 이 문서의 `Validation Companions`
- 완료판정:
  - [docs/work_tickets.md](docs/work_tickets.md)의 `Review Mode Matrix`
  - 이 문서의 `Completion Companions`
- 잔여 구현 검토:
  - [docs/work_tickets.md](docs/work_tickets.md)의 `Review Mode Matrix`
  - 이 문서의 `잔여 구현 검토부터 시작할 때`
- 작업량 추산:
  - [docs/work_tickets.md](docs/work_tickets.md)의 `Review Mode Matrix`
  - [docs/work_tickets.md](docs/work_tickets.md)의 `Turn Estimate Entry`
- 우선순위 판단:
  - [docs/work_tickets.md](docs/work_tickets.md)의 `Review Mode Matrix`
  - 이 문서의 `Priority Companions`
  - [docs/work_tickets.md](docs/work_tickets.md)의 `Assessment-To-Ticket Interpretation`

검증부터 시작할 때는 아래 순서를 권장합니다.

이 순서는 [docs/work_tickets.md](docs/work_tickets.md)의 `Validation Reading Order`를 따릅니다.

1. [docs/work_tickets.md](docs/work_tickets.md)의 `Validation Routing`
2. [tests/e2e/README.md](tests/e2e/README.md)의 case layout / harness command
3. [docs/code/README.md](docs/code/README.md)의 subsystem entrypoint
4. [docs/handbook.md](docs/handbook.md)의 artifact map / troubleshooting

## Completion Reading Order

완료판정부터 시작할 때는 아래 순서를 권장합니다.

이 순서는 [docs/work_tickets.md](docs/work_tickets.md)의 `Open-World Completion Reading Order`를 따릅니다.

1. [docs/work_tickets.md](docs/work_tickets.md)의 `Completion Companions`
2. [docs/work_tickets.md](docs/work_tickets.md)의 `Open-World Completion Axis Map` / `Open-World Completion Checklist`
3. [docs/final_solution.md](docs/final_solution.md)의 `Acceptance-To-Validation Translation`
4. [tests/e2e/README.md](tests/e2e/README.md)의 harness command / case layout
5. [docs/code/README.md](docs/code/README.md)의 subsystem entrypoint
6. [docs/handbook.md](docs/handbook.md)의 artifact reading hints / troubleshooting
7. [docs/current_state_gap_analysis.md](docs/current_state_gap_analysis.md), [docs/constraints.md](docs/constraints.md)

잔여 구현 검토부터 시작할 때는 아래 순서를 권장합니다.

이 순서는 [docs/work_tickets.md](docs/work_tickets.md)의 `Open-World Residual Reading Order`를 따릅니다.

1. [docs/work_tickets.md](docs/work_tickets.md)의 `Open-World Residual Ticket Breakdown`
2. [docs/work_tickets.md](docs/work_tickets.md)의 `Open-World Completion Checklist`
3. [docs/final_solution.md](docs/final_solution.md)의 `Acceptance-To-Validation Translation`
4. [docs/code/README.md](docs/code/README.md)의 subsystem entrypoint

## Priority Review Entry

우선순위 판단부터 시작할 때는 아래 순서를 권장합니다.

이 순서는 [docs/work_tickets.md](docs/work_tickets.md)의 `Priority Reading Order`를 따릅니다.

1. 이 문서의 `Priority Companions`
2. [docs/work_tickets.md](docs/work_tickets.md)의 `Current Remaining Snapshot`, `Confirmed Completion Priority Order`, `Estimated Turn Envelope`
3. [docs/work_tickets.md](docs/work_tickets.md)의 `Assessment-To-Ticket Interpretation`, `LLM-Response Capability Overlay`
4. [docs/final_solution.md](docs/final_solution.md)의 `Phase-To-Ticket Translation`, `Acceptance Gates`
5. [docs/current_state_gap_analysis.md](docs/current_state_gap_analysis.md), [docs/constraints.md](docs/constraints.md)
6. [tests/e2e/README.md](tests/e2e/README.md), [docs/code/README.md](docs/code/README.md), [docs/handbook.md](docs/handbook.md)

잔여 작업량/turn estimate만 바로 보고 싶으면 [docs/work_tickets.md](docs/work_tickets.md)의 `Turn Estimate Entry`를 먼저 본다.

## Safety

- PoC와 취약 환경은 로컬 격리 Docker에서만 사용합니다.
- 기본 네트워크는 `none`이며, 외부 연결을 허용하는 경우 정책과 이유를 명시해야 합니다.
- `promotion_eligible`와 generalized support claim을 같은 의미로 읽지 않습니다. 관련 제약은 [docs/constraints.md](docs/constraints.md)에 정리합니다.

## How To Update This Document

- repository entrypoint, quickstart command, document map이 바뀔 때만 갱신한다.
- current rerun 결과나 completeness 평가는 [docs/current_state_gap_analysis.md](docs/current_state_gap_analysis.md)에 남긴다.
- current non-claim과 operational prerequisite는 [docs/constraints.md](docs/constraints.md)에 남긴다.
- phase ordering과 implementation priority는 [docs/final_solution.md](docs/final_solution.md), [docs/work_tickets.md](docs/work_tickets.md)로 보낸다.
- operator 절차와 artifact reading detail은 [docs/handbook.md](docs/handbook.md)와 같이 맞춘다.
- 구현 ticket별 primary code path나 representative validation focus가 달라지면 [docs/work_tickets.md](docs/work_tickets.md)의 해당 표와 같이 맞춘다.
- 검증 하니스 진입 순서가 바뀌면 [tests/e2e/README.md](tests/e2e/README.md), [docs/handbook.md](docs/handbook.md)와 같이 맞춘다.
- 검증 문서 읽는 순서가 바뀌면 [docs/code/README.md](docs/code/README.md)와도 같이 맞춘다.
- validation companion 관계가 바뀌면 같은 섹션을 [docs/handbook.md](docs/handbook.md), [docs/code/README.md](docs/code/README.md), [tests/e2e/README.md](tests/e2e/README.md)와 같이 맞춘다.
- validation question routing이 바뀌면 [docs/work_tickets.md](docs/work_tickets.md)와 같이 맞춘다.
- completion companion 관계가 바뀌면 같은 섹션을 [docs/handbook.md](docs/handbook.md), [docs/code/README.md](docs/code/README.md), [tests/e2e/README.md](tests/e2e/README.md)와 같이 맞춘다.
- LLM-response stricter reading의 repository entrypoint 해석이 바뀌면 [docs/work_tickets.md](docs/work_tickets.md)의 `LLM-Response Capability Overlay`와 같이 맞춘다.
- latest positive representative pair의 ticket-form 해석이 바뀌면 [docs/work_tickets.md](docs/work_tickets.md)의 `Assessment-To-Ticket Interpretation`와 같이 맞춘다.
- residual companion 관계가 바뀌면 같은 섹션을 [docs/handbook.md](docs/handbook.md), [docs/code/README.md](docs/code/README.md), [tests/e2e/README.md](tests/e2e/README.md)와 같이 맞춘다.
- residual question routing이 바뀌면 [docs/work_tickets.md](docs/work_tickets.md)와 같이 맞춘다.
- completion review 진입 순서가 바뀌면 [docs/work_tickets.md](docs/work_tickets.md), [docs/handbook.md](docs/handbook.md), [tests/e2e/README.md](tests/e2e/README.md), [docs/code/README.md](docs/code/README.md)와 같이 맞춘다.
- completion reading order가 바뀌면 [docs/work_tickets.md](docs/work_tickets.md), [docs/handbook.md](docs/handbook.md), [tests/e2e/README.md](tests/e2e/README.md), [docs/code/README.md](docs/code/README.md)와 같이 맞춘다.
- residual review 진입 순서가 바뀌면 [docs/work_tickets.md](docs/work_tickets.md), [docs/handbook.md](docs/handbook.md), [tests/e2e/README.md](tests/e2e/README.md), [docs/code/README.md](docs/code/README.md)와 같이 맞춘다.
- residual reading order가 바뀌면 [docs/work_tickets.md](docs/work_tickets.md), [docs/handbook.md](docs/handbook.md), [tests/e2e/README.md](tests/e2e/README.md), [docs/code/README.md](docs/code/README.md)와 같이 맞춘다.
- review mode entry shortcuts가 바뀌면 [docs/handbook.md](docs/handbook.md), [docs/code/README.md](docs/code/README.md), [tests/e2e/README.md](tests/e2e/README.md)와 같이 맞춘다.
- 잔여 작업량/turn envelope 해석이 바뀌면 [docs/work_tickets.md](docs/work_tickets.md)의 `Estimated Turn Envelope`와 handbook/code/e2e companion의 priority routing도 같이 맞춘다.
- [docs/work_tickets.md](docs/work_tickets.md)의 `Turn Estimate Entry`가 바뀌면 handbook/code/e2e companion의 same shortcut도 같이 맞춘다.
