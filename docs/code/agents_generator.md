# agents/generator 디렉토리

Status: support
Audience: implementation
Source of truth for: generator modes, synthesis/template/compiler entrypoints
Not the source of truth for: project-level roadmap or current evidence baseline
Last validated against: current repo layout on 2026-03-14

Relevant canonical docs:
- [현재 상태](../current_state_gap_analysis.md)
- [제약조건](../constraints.md)
- [로드맵](../final_solution.md)

## 핵심 파일

- `agents/generator/main.py`: generator CLI entry
- `agents/generator/service.py`: mode 선택, compiler/template/synthesis orchestration
- `agents/generator/synthesis.py`: manifest candidate 생성, guard, deterministic fallback

## 현재 구현상 포인트

- current synthesis는 one-shot manifest candidate와 deterministic fallback을 함께 사용합니다.
- dynamic lane의 boundedness는 family-aware/semantic-guided fallback builder에 크게 의존합니다.
- `request_ir`, `runtime_recipe`, `executor_plan`, `exploit_oracle`가 prompt/contract에 주입되지만, 아직 staged synthesis control-plane은 아닙니다.

이 디렉토리 작업은 항상 [docs/final_solution.md](../final_solution.md)의 phased plan과 [docs/constraints.md](../constraints.md)의 generator constraints를 기준으로 해야 합니다.
