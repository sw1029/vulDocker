# Legacy Docs Archive

Status: archived
Audience: mixed
Source of truth for: none
Not the source of truth for: current problem statement, constraints, roadmap
Last validated against: document taxonomy rewrite on 2026-03-14

이 디렉토리는 historical reference용 문서를 보관합니다.

- active canonical docs는 상위 `docs/` 아래 문서를 따릅니다.
- archived 문서는 현재 상태나 우선순위를 설명하는 데 사용하지 않습니다.
- current completion priority order는 상위 canonical backlog 문서 [docs/work_tickets.md](../../work_tickets.md)의 `Confirmed Completion Priority Order`를 우선합니다.
- 잔여 작업량/turn envelope 해석도 상위 canonical backlog 문서 [docs/work_tickets.md](../../work_tickets.md)의 `Estimated Turn Envelope`를 우선합니다.

## Priority Companions

archive 문서 기준으로도 current priority source는 아래만 따른다.

- current completion priority order: [docs/work_tickets.md](../../work_tickets.md)의 `Confirmed Completion Priority Order`
- 잔여 작업량과 practical turn envelope: [docs/work_tickets.md](../../work_tickets.md)의 `Estimated Turn Envelope`
- representative evidence와 함께 보는 turn estimate shortcut: [docs/work_tickets.md](../../work_tickets.md)의 `Turn Estimate Entry`
- priority companion set / reading order: [docs/work_tickets.md](../../work_tickets.md)의 `Priority Companions`, `Priority Reading Order`
- latest positive representative pair의 ticket-form reading: [docs/work_tickets.md](../../work_tickets.md)의 `Assessment-To-Ticket Interpretation`
- LLM-response 기준 residual/priority 해석: [docs/work_tickets.md](../../work_tickets.md)의 `LLM-Response Capability Overlay`
- canonical roadmap / current truth / current non-claim: [docs/final_solution.md](../../final_solution.md), [docs/current_state_gap_analysis.md](../../current_state_gap_analysis.md), [docs/constraints.md](../../constraints.md)

## Priority Review Entry

archive entry에서 priority를 확인해야 한다면 아래 순서를 따른다.

1. 이 문서의 `Priority Companions`
2. [docs/work_tickets.md](../../work_tickets.md)의 `Confirmed Completion Priority Order`, `Estimated Turn Envelope`
3. [docs/work_tickets.md](../../work_tickets.md)의 `LLM-Response Capability Overlay`, `Assessment-To-Ticket Interpretation`
4. [docs/final_solution.md](../../final_solution.md), [docs/current_state_gap_analysis.md](../../current_state_gap_analysis.md), [docs/constraints.md](../../constraints.md)

turn estimate shortcut은 [docs/work_tickets.md](../../work_tickets.md)의 `Turn Estimate Entry`를 따른다.

## How To Update This Document

- archive taxonomy나 redirect target이 바뀔 때만 갱신합니다.
- current truth, current priority, current residual은 여기로 옮겨 적지 않습니다. 각각 [docs/current_state_gap_analysis.md](../../current_state_gap_analysis.md), [docs/work_tickets.md](../../work_tickets.md), [docs/final_solution.md](../../final_solution.md)를 우선합니다.
- priority companion 관계나 priority reading order가 바뀌면 [docs/work_tickets.md](../../work_tickets.md), [README.md](../../../README.md)와 같이 맞춥니다.
- LLM-response stricter reading의 archive redirect target이 바뀌면 [docs/work_tickets.md](../../work_tickets.md)의 `LLM-Response Capability Overlay`와 같이 맞춥니다.
- latest positive representative pair의 ticket-form redirect target이 바뀌면 [docs/work_tickets.md](../../work_tickets.md)의 `Assessment-To-Ticket Interpretation`와 같이 맞춥니다.
- 잔여 작업량/turn envelope redirect target이 바뀌면 [docs/work_tickets.md](../../work_tickets.md)의 `Estimated Turn Envelope`와 같이 맞춥니다.
- [docs/work_tickets.md](../../work_tickets.md)의 `Turn Estimate Entry` redirect target이 바뀌면 same shortcut도 같이 맞춥니다.
