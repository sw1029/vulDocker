# LLM+RAG 기반 동적 취약 테스트베드 (vulDocker)

Status: support
Audience: mixed
Source of truth for: repository entrypoint, quickstart, document map
Not the source of truth for: current-state assessment, constraints, implementation roadmap
Last validated against: `python -m pytest -q tests`, targeted repeatability/support regressions, and representative no-Docker E2E direct checks on 2026-03-19

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
- 빠른 no-Docker direct check: `python tests/e2e/run_case.py --case tests/e2e/cases/open-redirect-strict-dynamic-no-remote --mode deterministic --no-snapshot --output-dir /tmp/vuld_strict_no_remote`
- unsupported negative check: `python tests/e2e/run_case.py --case tests/e2e/cases/foobar-name-only-negative --mode deterministic --no-snapshot --output-dir /tmp/vuld_negative`
- repeatability/support preview check: `python tests/e2e/repeat_case.py --case tests/e2e/cases/foobar-name-only-negative --attempts 2 --mode deterministic --output-dir /tmp/vuld_repeat_negative`
- Docker-enabled representative E2E: `python tests/e2e/run_case.py --case tests/e2e/cases/open-redirect-dynamic-name-only --mode deterministic`

## Document Map

- `docs/problem.md`: 프로젝트가 풀고자 하는 문제와 success criteria
- `docs/current_state_gap_analysis.md`: 현재 truth, rerun 결과, 구조적 미비점
- `docs/constraints.md`: 현재 시스템의 기술·운영·평가 제약과 금지 claim
- `docs/final_solution.md`: 구현 우선순위와 phase-based roadmap
- `docs/work_tickets.md`: actionable backlog, subtask decomposition, residual-to-ticket mapping
- `docs/handbook.md`: 운영/온보딩/명령/아티팩트 해석
- `docs/guardrails_dynamic.md`: GuardSpec subsystem guide
- `docs/code/README.md`: 구현 엔지니어용 코드 탐색 인덱스
- `tests/e2e/README.md`: 검증 하니스, case layout, repeatability/support workflow 진입점

문서가 충돌해 보이면 아래 우선순위를 따릅니다.

- 현재 truth / 실행 결과: `docs/current_state_gap_analysis.md`
- 금지 claim / 현재 한계: `docs/constraints.md`
- phase 우선순위: `docs/final_solution.md`
- 실제 작업 분해: `docs/work_tickets.md`
- 실행 절차 / 명령 / artifact path: `docs/handbook.md`

현재 구현 순서와 phase-owner 연결을 바로 보려면 아래를 함께 봅니다.

- phase-to-ticket map: [docs/final_solution.md](docs/final_solution.md)
- phase acceptance -> validation surface map: [docs/final_solution.md](docs/final_solution.md)
- current remaining snapshot / sequencing rule: [docs/work_tickets.md](docs/work_tickets.md)
- code entrypoints / validation surface by ticket: [docs/work_tickets.md](docs/work_tickets.md)
- validation harness by ticket: [tests/e2e/README.md](tests/e2e/README.md)

## Validation Companions

검증 관점에서 이 문서와 같이 봐야 할 companion은 아래와 같습니다.

- success criteria 5축과 backlog owner 대응: [docs/work_tickets.md](docs/work_tickets.md)
- completion companion set: [docs/work_tickets.md](docs/work_tickets.md)의 `Completion Companions`
- success criteria 5축의 완료판정 질문과 최소 근거: [docs/work_tickets.md](docs/work_tickets.md)의 `Open-World Completion Checklist`
- success criteria 5축의 canonical 완료 검토 순서: [docs/work_tickets.md](docs/work_tickets.md)의 `Open-World Completion Review Flow`
- success criteria 5축의 canonical 완료판정 reading order: [docs/work_tickets.md](docs/work_tickets.md)의 `Open-World Completion Reading Order`
- latest confirmed residual의 축별 ticket bundle 분해: [docs/work_tickets.md](docs/work_tickets.md)의 `Open-World Residual Ticket Breakdown`
- latest confirmed residual의 canonical 구현 검토 순서: [docs/work_tickets.md](docs/work_tickets.md)의 `Open-World Residual Review Flow`
- latest confirmed residual 검토 문서 순서: [docs/work_tickets.md](docs/work_tickets.md)의 `Open-World Residual Reading Order`
- residual companion set: [docs/work_tickets.md](docs/work_tickets.md)의 `Residual Companions`
- review mode별 canonical 시작점: [docs/work_tickets.md](docs/work_tickets.md)의 `Review Mode Matrix`
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
- axis map / close criteria / canonical review order: [docs/work_tickets.md](docs/work_tickets.md)의 `Open-World Completion Axis Map`, `Open-World Completion Checklist`, `Open-World Completion Review Flow`
- canonical completion reading order: [docs/work_tickets.md](docs/work_tickets.md)의 `Open-World Completion Reading Order`
- phase acceptance map: [docs/final_solution.md](docs/final_solution.md)의 `Acceptance-To-Validation Translation`
- harness entry: [tests/e2e/README.md](tests/e2e/README.md)
- code entrypoint: [docs/code/README.md](docs/code/README.md)
- artifact reading / troubleshooting: [docs/handbook.md](docs/handbook.md)
- current truth / non-claim: [docs/current_state_gap_analysis.md](docs/current_state_gap_analysis.md), [docs/constraints.md](docs/constraints.md)

## Residual Companions

잔여 구현 검토 관점에서 이 문서와 같이 봐야 할 companion은 아래와 같습니다.

- residual bucket / ticket bundle: [docs/work_tickets.md](docs/work_tickets.md)의 `Open-World Residual Ticket Breakdown`
- residual close criteria: [docs/work_tickets.md](docs/work_tickets.md)의 `Open-World Completion Checklist`
- residual review / reading order: [docs/work_tickets.md](docs/work_tickets.md)의 `Open-World Residual Review Flow`, `Open-World Residual Reading Order`
- phase acceptance map: [docs/final_solution.md](docs/final_solution.md)의 `Acceptance-To-Validation Translation`
- code entrypoint / residual focus: [docs/code/README.md](docs/code/README.md)
- artifact reading / troubleshooting: [docs/handbook.md](docs/handbook.md)
- current truth / non-claim: [docs/current_state_gap_analysis.md](docs/current_state_gap_analysis.md), [docs/constraints.md](docs/constraints.md)

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
5. [docs/handbook.md](docs/handbook.md)의 artifact reading hints / troubleshooting

이 흐름을 support 문서 기준으로 따라갈 때는 아래 대응을 본다.

1. [docs/work_tickets.md](docs/work_tickets.md)의 `Open-World Residual Reading Order`
2. [tests/e2e/README.md](tests/e2e/README.md)의 `Residual Review Entry`
3. [docs/code/README.md](docs/code/README.md)의 `Residual Review Entry`
4. [docs/handbook.md](docs/handbook.md)의 `Residual Review Entry`

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
- residual companion 관계가 바뀌면 같은 섹션을 [docs/handbook.md](docs/handbook.md), [docs/code/README.md](docs/code/README.md), [tests/e2e/README.md](tests/e2e/README.md)와 같이 맞춘다.
- residual question routing이 바뀌면 [docs/work_tickets.md](docs/work_tickets.md)와 같이 맞춘다.
- completion review 진입 순서가 바뀌면 [docs/work_tickets.md](docs/work_tickets.md), [docs/handbook.md](docs/handbook.md), [tests/e2e/README.md](tests/e2e/README.md), [docs/code/README.md](docs/code/README.md)와 같이 맞춘다.
- completion reading order가 바뀌면 [docs/work_tickets.md](docs/work_tickets.md), [docs/handbook.md](docs/handbook.md), [tests/e2e/README.md](tests/e2e/README.md), [docs/code/README.md](docs/code/README.md)와 같이 맞춘다.
- residual review 진입 순서가 바뀌면 [docs/work_tickets.md](docs/work_tickets.md), [docs/handbook.md](docs/handbook.md), [tests/e2e/README.md](tests/e2e/README.md), [docs/code/README.md](docs/code/README.md)와 같이 맞춘다.
- residual reading order가 바뀌면 [docs/work_tickets.md](docs/work_tickets.md), [docs/handbook.md](docs/handbook.md), [tests/e2e/README.md](tests/e2e/README.md), [docs/code/README.md](docs/code/README.md)와 같이 맞춘다.
- review mode entry shortcuts가 바뀌면 [docs/handbook.md](docs/handbook.md), [docs/code/README.md](docs/code/README.md), [tests/e2e/README.md](tests/e2e/README.md)와 같이 맞춘다.
