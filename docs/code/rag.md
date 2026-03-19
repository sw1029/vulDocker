# rag 디렉토리

Status: support
Audience: implementation
Source of truth for: retrieval/memory helper paths and search adapter boundaries
Not the source of truth for: evidence authority policy, roadmap, support-promotion claims
Last validated against: current repo layout, researcher search adapter surface, and cache/reuse observability wiring on 2026-03-19

Relevant canonical docs:
- [제약조건](../constraints.md)
- [현재 상태](../current_state_gap_analysis.md)
- [로드맵](../final_solution.md)
- [작업 티켓](../work_tickets.md)
- success criteria 5축과 backlog owner 대응: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Completion Axis Map`
- completion companion set과 canonical reading order: [docs/work_tickets.md](../work_tickets.md)의 `Completion Companions`, `Open-World Completion Reading Order`
- success criteria 5축의 완료판정 질문과 최소 근거: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Completion Checklist`
- success criteria 5축의 canonical 완료 검토 순서: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Completion Review Flow`
- latest confirmed residual의 축별 ticket bundle 분해: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Residual Ticket Breakdown`
- [검증 하니스](../../tests/e2e/README.md)

## 핵심 파일

- `rag/memories/__init__.py`: reflexion-style memory(JSONL) 저장/조회
- `rag/tools/web_search.py`: remote/local search adapter, provider abstraction

## 데이터 계약

- 입력:
  - generator failure history
  - researcher query / search request
  - local memory store
- 출력:
  - prompt-injectable recent failure context
  - search result/adaptation surface for researcher

## 현재 구현상 포인트

- RAG 계층은 researcher가 evidence를 모으는 데 도움을 주지만, evidence authority를 causal proof 수준으로 올려 주지는 않는다.
- latest slice에서는 query cache, diminishing-return early stop, cache observation surface가 measured performance summary와 `repeatability_report.json`까지 이어진다.
- repo-local cache/reuse가 생겨도 그것만으로 authoritative measured gate closure나 open-world support claim을 만들 수는 없다.
- reflexion memory는 synthesis/review loop를 돕는 보조 계층이며, primitive-first controller나 scenario selection policy의 primary owner는 아니다.

## Current Residual Owners

- evidence authority / contradiction policy residual은 `TKT-001-G` owner다.
- perf/cache reuse를 authoritative measured gate로 승격하는 residual은 `TKT-008-A1/A2` owner다.
- RAG 문서는 retrieval helper와 cache surface를 설명할 수 있지만, generalized evidence reasoning closure를 claim하면 안 된다.

## Residual Review Focus

- `TKT-001-G` residual은 retrieval 결과가 authority threshold/contradiction policy를 실제로 얼마나 돕는지부터 본다.
- `TKT-008-A*` residual은 cache/reuse observation이 measured gate blocker와 어떻게 이어지는지부터 본다.

## Completion Review Focus

- `TKT-001-G` completion은 retrieval/memory helper가 authority threshold와 contradiction-aware selection을 돕되, evidence proof를 과장하지 않는 보조 surface로 남는지부터 본다.
- `TKT-008-A*` completion은 cache/reuse observation이 measured gate authoritative input으로 재사용되되, standalone success claim으로 오해되지 않는지부터 본다.

## Review Mode Entry

이 문서를 열 때는 아래 mode entry를 먼저 고른다.

- 검증:
  - 이 문서의 `Representative Validation Surface`
- 완료판정:
  - 이 문서의 `Completion Review Focus`
  - [docs/code/README.md](README.md)의 `Completion Review Entry`
- 잔여 구현 검토:
  - 이 문서의 `Residual Review Focus`
  - [docs/code/README.md](README.md)의 `Residual Review Entry`

## Ticket-First Entry

- researcher retrieval adapter를 볼 때:
  - `rag/tools/web_search.py`
  - `agents/researcher/service.py`
- memory/retry helper를 볼 때:
  - `rag/memories/__init__.py`
  - synthesis/reviewer loop callers
- perf/cache reuse surface를 볼 때:
  - `rag/tools/web_search.py`
  - `metadata/<SID>/performance_summary.json`
  - repeatability artifacts의 search/cache observation

## Representative Validation Surface

- retrieval/cache adapter regression:
  - `tests/test_web_search_tool.py`
  - `tests/test_web_search_custom.py`
  - `tests/test_web_search_tavily.py`
- researcher/RAG handoff regression:
  - `tests/test_researcher_search_artifacts.py`
  - `tests/test_repeatability_gate.py`

## How To Update This Document

- retrieval adapter, memory helper, cache/reuse surface가 바뀔 때만 갱신한다.
- current measured perf truth는 [docs/current_state_gap_analysis.md](../current_state_gap_analysis.md)에 남긴다.
- current authority/non-claim은 [docs/constraints.md](../constraints.md)에 남긴다.
- backlog owner와 sequencing은 [docs/final_solution.md](../final_solution.md), [docs/work_tickets.md](../work_tickets.md)로 보낸다.
- ticket-first entrypoint나 representative validation surface가 바뀌면 이 문서의 해당 섹션도 같이 갱신한다.
- completion review focus가 바뀌면 same authority/perf owner mapping에 맞춰 이 문서도 같이 갱신한다.
- residual review focus가 바뀌면 same authority/perf owner mapping에 맞춰 이 문서도 같이 갱신한다.
- review mode entry shortcut이 바뀌면 [docs/code/README.md](README.md)와 같이 갱신한다.
- cache/reuse representative harness path가 바뀌면 [tests/e2e/README.md](../../tests/e2e/README.md)와 같이 갱신한다.
