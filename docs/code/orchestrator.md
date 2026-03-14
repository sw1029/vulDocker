# orchestrator 디렉토리

Status: support
Audience: implementation
Source of truth for: orchestrator entrypoints and output surfaces
Not the source of truth for: project goals, constraints, roadmap
Last validated against: current repo layout on 2026-03-14

Relevant canonical docs:
- [문제 정의](../problem.md)
- [현재 상태](../current_state_gap_analysis.md)
- [제약조건](../constraints.md)
- [로드맵](../final_solution.md)

## 핵심 파일

- `orchestrator/plan.py`: requirement 정규화, SID 계산, `plan.json` 작성
- `orchestrator/run_pipeline.py`: RESEARCH → GENERATE → EXECUTE → VERIFY → REVIEW → PACK loop 실행
- `orchestrator/pack.py`: summary/manifest rollup, readiness/promotion surfaces 생성

## 구현상 중요 포인트

- `plan.json`은 경로, policy, variation, run matrix의 시작점입니다.
- `run_pipeline.py`는 stage timing과 capability gate를 surface합니다.
- `pack.py`는 `name_only_outcome`, `support_promotion`, `open_world_readiness`, `artifact_quality`의 최종 집계면입니다.

## Name-Only/Open-World 작업 시 먼저 볼 것

- `plan.py`: 어떤 입력이 `request_ir`와 policy로 들어가는지
- `run_pipeline.py`: 어떤 stage가 fail-closed/partial을 결정하는지
- `pack.py`: 어떤 summary surface가 operator-facing truth가 되는지
