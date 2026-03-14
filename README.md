# LLM+RAG 기반 동적 취약 테스트베드 (vulDocker)

Status: support
Audience: mixed
Source of truth for: repository entrypoint, quickstart, document map
Not the source of truth for: current-state assessment, constraints, implementation roadmap
Last validated against: `python -m pytest -q tests` and representative E2E reruns on 2026-03-14

`vulDocker`는 LLM+RAG를 활용해 취약 환경을 자동 합성/보강하고, Docker에서 실행·검증·리뷰·패키징까지 이어지는 실험용 테스트베드입니다. 현재 시스템은 정직한 bounded regression platform과 일부 supported family에 대한 degraded dynamic generation을 제공하며, generalized open-world generator로는 아직 발전 중입니다.

## Read This First

문서를 읽는 권장 순서는 아래와 같습니다.

1. [문제 정의](docs/problem.md)
2. [현재 상태 / 갭 분석](docs/current_state_gap_analysis.md)
3. [제약조건](docs/constraints.md)
4. [구현 로드맵](docs/final_solution.md)
5. [핸드북](docs/handbook.md)
6. [코드 인덱스](docs/code/README.md)

## Quickstart

사전 요구
- Docker (rootless 권장)
- Python 3.11+
- git
- 선택: Syft 설치 시 SBOM 자동 생성

설치
- `python -m venv .venv && source .venv/bin/activate`
- `pip install -r requirements.txt`

대표 실행
1. PLAN: `python orchestrator/plan.py --input inputs/mvp_sqli.yml`
2. E2E 루프: `python orchestrator/run_pipeline.py --sid <SID> --mode deterministic`
3. 단계별 실행이 필요하면 [핸드북](docs/handbook.md)의 quickstart를 따릅니다.

기본 검증
- 단위 테스트: `python -m pytest -q tests`
- 대표 E2E: `python tests/e2e/run_case.py --case tests/e2e/cases/open-redirect-dynamic-name-only --mode deterministic`

## Document Map

- `docs/problem.md`: 프로젝트가 풀고자 하는 문제와 success criteria
- `docs/current_state_gap_analysis.md`: 현재 truth, rerun 결과, 구조적 미비점
- `docs/constraints.md`: 현재 시스템의 기술·운영·평가 제약과 금지 claim
- `docs/final_solution.md`: 구현 우선순위와 phase-based roadmap
- `docs/handbook.md`: 운영/온보딩/명령/아티팩트 해석
- `docs/guardrails_dynamic.md`: GuardSpec subsystem guide
- `docs/code/README.md`: 구현 엔지니어용 코드 탐색 인덱스

## Safety

- PoC와 취약 환경은 로컬 격리 Docker에서만 사용합니다.
- 기본 네트워크는 `none`이며, 외부 연결을 허용하는 경우 정책과 이유를 명시해야 합니다.
- `promotion_eligible`와 generalized support claim을 같은 의미로 읽지 않습니다. 관련 제약은 [docs/constraints.md](docs/constraints.md)에 정리합니다.
