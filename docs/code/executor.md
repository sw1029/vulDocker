# executor/runtime 디렉토리

Status: support
Audience: implementation
Source of truth for: executor entrypoint and runtime evidence surfaces
Not the source of truth for: topology constraints or roadmap priority
Last validated against: current repo layout on 2026-03-14

Relevant canonical docs:
- [제약조건](../constraints.md)
- [로드맵](../final_solution.md)

## 핵심 파일

- `executor/runtime/docker_local.py`: Docker build/run, readiness, sidecar/network handling, run summary 생성

## 데이터 계약

- 입력: workspace, `plan.json`, `policy.executor`, resolved contract surface
- 출력: `build.log`, `run.log`, `summary.json`, `run/index.json`

## 현재 구현상 포인트

- executor는 `service_port`, `health_path`, env, sidecar를 일부 재해석합니다.
- `service_plus_sidecar`는 현재 generator invention보다 policy-coupled lane에 가깝습니다.
- `executor_plan`은 존재하지만 아직 full runtime control-plane은 아닙니다.

이 디렉토리를 볼 때는 [docs/constraints.md](../constraints.md)의 executor/runtime constraints를 먼저 같이 봐야 합니다.
