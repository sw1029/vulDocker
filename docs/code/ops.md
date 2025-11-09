# ops 디렉토리

구성 요소
- ops/ci/run_case.sh — PLAN → (Researcher) → Generator → Executor → Evals → Reviewer → Pack 스모크 파이프라인.
- ops/ci/smoke_regression.sh — 기본 회귀 실행 시나리오.
- ops/observability/dashboard_spec.md — KPI 대시보드 스펙.

데이터 계약/출력
- CI 스크립트는 각 단계의 표준 출력/산출물(`metadata/`, `artifacts/`)을 그대로 이용하며, 실패 시 종료 코드를 전파.

프로젝트 내 역할
- 수동 실행을 자동화하고 회귀/KPI를 관측 가능한 형태로 유지.

