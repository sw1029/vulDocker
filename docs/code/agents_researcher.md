# agents/researcher 디렉토리

Status: support
Audience: implementation
Source of truth for: researcher query/evidence/guard generation entrypoints
Not the source of truth for: generalized evidence policy or high-level roadmap
Last validated against: current repo layout on 2026-03-14

Relevant canonical docs:
- [현재 상태](../current_state_gap_analysis.md)
- [제약조건](../constraints.md)
- [로드맵](../final_solution.md)

## 핵심 파일

- `agents/researcher/main.py`: researcher CLI entry
- `agents/researcher/service.py`: query plan, search, evidence graph, guard spec, researcher report 생성

## 현재 구현상 포인트

- family hypothesis와 stack candidates는 retrieval evidence를 바탕으로 enrich되지만 아직 closed-vocabulary 경향이 강합니다.
- evidence graph와 source authority는 operator-facing summary를 개선하지만, causal proof나 full control-plane을 뜻하지는 않습니다.
- researcher output은 generator와 pack surface에 크게 영향을 주므로 `request_ir`, `family_hypothesis_summary`, `tech_stack_candidates`, `evidence_graph`를 함께 봐야 합니다.
