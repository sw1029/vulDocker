# docs/solution.md Deprecated

Status: deprecated
Audience: mixed
Source of truth for: none
Not the source of truth for: strategy, constraints, roadmap
Last validated against: document taxonomy rewrite and completion-review routing update on 2026-03-19

이 문서는 더 이상 canonical 문서가 아닙니다.

- 전략/문제 정의: [docs/problem.md](problem.md)
- 현재 상태/근거: [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)
- 제약조건: [docs/constraints.md](constraints.md)
- 구현 로드맵: [docs/final_solution.md](final_solution.md)
- 작업 티켓 backlog: [docs/work_tickets.md](work_tickets.md)
- success criteria 5축과 backlog owner 대응: [docs/work_tickets.md](work_tickets.md)
- completion companion set: [docs/work_tickets.md](work_tickets.md)의 `Completion Companions`
- priority companion set: [docs/work_tickets.md](work_tickets.md)의 `Priority Companions`
- success criteria 5축의 완료판정 질문과 최소 근거: [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Checklist`
- success criteria 5축의 canonical 완료 검토 순서: [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Review Flow`
- success criteria 5축의 canonical 완료판정 reading order: [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Reading Order`
- current completion priority order: [docs/work_tickets.md](work_tickets.md)의 `Confirmed Completion Priority Order`
- 잔여 작업량과 practical turn envelope: [docs/work_tickets.md](work_tickets.md)의 `Estimated Turn Envelope`
- residual companion set: [docs/work_tickets.md](work_tickets.md)의 `Residual Companions`
- review mode별 canonical 시작점: [docs/work_tickets.md](work_tickets.md)의 `Review Mode Matrix`
- ticket별 code entrypoint / validation surface: [docs/work_tickets.md](work_tickets.md)
- 운영 절차: [docs/handbook.md](handbook.md)
- representative validation harness: [tests/e2e/README.md](../tests/e2e/README.md)
- 코드 탐색 인덱스: [docs/code/README.md](code/README.md)
- 검증 문서 읽는 순서: `work_tickets -> tests/e2e/README -> code/README -> handbook`
- 완료판정 검토 순서: `work_tickets axis/checklist/review flow -> final_solution acceptance map -> tests/e2e/README -> code/README -> handbook`
- 잔여 구현 검토 문서 순서: `work_tickets residual breakdown/checklist/reading order -> tests/e2e/README -> code/README -> handbook`

## Priority Companions

deprecated 문서 기준으로도 current priority source는 아래만 따른다.

- current completion priority order: [docs/work_tickets.md](work_tickets.md)의 `Confirmed Completion Priority Order`
- 잔여 작업량과 practical turn envelope: [docs/work_tickets.md](work_tickets.md)의 `Estimated Turn Envelope`
- representative evidence와 함께 보는 turn estimate shortcut: [docs/work_tickets.md](work_tickets.md)의 `Turn Estimate Entry`
- priority companion set / reading order: [docs/work_tickets.md](work_tickets.md)의 `Priority Companions`, `Priority Reading Order`
- latest positive representative pair의 ticket-form reading: [docs/work_tickets.md](work_tickets.md)의 `Assessment-To-Ticket Interpretation`
- LLM-response 기준 residual/priority 해석: [docs/work_tickets.md](work_tickets.md)의 `LLM-Response Capability Overlay`

## Priority Review Entry

이 deprecated 문서에서 priority를 확인해야 한다면 아래만 따른다.

1. `docs/work_tickets.md`의 `Confirmed Completion Priority Order`, `Estimated Turn Envelope`
2. `docs/work_tickets.md`의 `Priority Reading Order`
3. `docs/work_tickets.md`의 `LLM-Response Capability Overlay`, `Assessment-To-Ticket Interpretation`
4. `docs/final_solution.md`, `docs/current_state_gap_analysis.md`, `docs/constraints.md`

turn estimate shortcut은 `docs/work_tickets.md`의 `Turn Estimate Entry`를 따른다.

## How To Update This Document

- historical snapshot나 redirect 역할이 바뀔 때만 갱신합니다.
- current truth, current priority, current residual은 여기 옮겨 적지 않습니다. 각각 [docs/current_state_gap_analysis.md](current_state_gap_analysis.md), [docs/work_tickets.md](work_tickets.md), [docs/final_solution.md](final_solution.md)를 우선합니다.
- priority companion 관계나 priority reading order가 바뀌면 [docs/work_tickets.md](work_tickets.md), [README.md](../README.md)와 같이 맞춥니다.
- LLM-response stricter reading의 deprecated redirect target이 바뀌면 [docs/work_tickets.md](work_tickets.md)의 `LLM-Response Capability Overlay`와 같이 맞춥니다.
- latest positive representative pair의 ticket-form 해석 redirect가 바뀌면 [docs/work_tickets.md](work_tickets.md)의 `Assessment-To-Ticket Interpretation`와 같이 맞춥니다.
- 잔여 작업량/turn envelope 해석 redirect가 바뀌면 [docs/work_tickets.md](work_tickets.md)의 `Estimated Turn Envelope`와 같이 맞춥니다.
- [docs/work_tickets.md](work_tickets.md)의 `Turn Estimate Entry` redirect가 바뀌면 same shortcut도 같이 맞춥니다.
- deprecated 문서 taxonomy나 canonical redirect target이 바뀌면 [README.md](../README.md), [docs/handbook.md](handbook.md), [docs/code/README.md](code/README.md)와 같이 맞춥니다.
