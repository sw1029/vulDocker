# 코드 디렉토리별 상세 설명 인덱스

Status: support
Audience: implementation
Source of truth for: code navigation entrypoint
Not the source of truth for: project goals, constraints, roadmap
Last validated against: repository layout on 2026-03-14

이 인덱스는 구현 엔지니어가 코드 구조를 빠르게 따라가기 위한 문서입니다. 프로젝트 목표는 [docs/problem.md](../problem.md), 현재 제약은 [docs/constraints.md](../constraints.md), 구현 로드맵은 [docs/final_solution.md](../final_solution.md)를 봅니다.

## Index

- orchestrator: `docs/code/orchestrator.md`
- common: `docs/code/common.md`
- researcher: `docs/code/agents_researcher.md`
- generator: `docs/code/agents_generator.md`
- reviewer: `docs/code/agents_reviewer.md`
- executor: `docs/code/executor.md`
- evals: `docs/code/evals.md`
- rag: `docs/code/rag.md`
- ops: `docs/code/ops.md`
- workspace/metadata/artifacts: `docs/code/workspaces.md`

## Reading Order For Name-Only/Open-World Work

1. orchestrator
2. researcher
3. generator
4. executor
5. evals
6. common

이 순서를 기준으로 `request_ir`, `selection_decision`, `runtime_recipe`, `executor_plan`, `name_only_outcome`, `support_promotion`이 어디서 만들어지고 소비되는지 따라가면 됩니다.
