# rag 디렉토리

Status: support
Audience: implementation
Source of truth for: retrieval/memory helper paths and search adapter boundaries
Not the source of truth for: evidence authority policy, roadmap, support-promotion claims
Last validated against: current repo layout, researcher search adapter surface, and cache/reuse observability wiring on 2026-04-02

Relevant canonical docs:
- [제약조건](../constraints.md)
- [현재 상태](../current_state_gap_analysis.md)
- [로드맵](../final_solution.md)
- [작업 티켓](../work_tickets.md)
- success criteria 5축과 backlog owner 대응: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Completion Axis Map`
- completion companion set과 canonical reading order: [docs/work_tickets.md](../work_tickets.md)의 `Completion Companions`, `Open-World Completion Reading Order`
- priority companion set과 canonical priority routing: [docs/work_tickets.md](../work_tickets.md)의 `Priority Companions`, `Priority Reading Order`
- success criteria 5축의 완료판정 질문과 최소 근거: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Completion Checklist`
- success criteria 5축의 canonical 완료 검토 순서: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Completion Review Flow`
- latest confirmed residual의 축별 ticket bundle 분해: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Residual Ticket Breakdown`
- latest direct verification까지 반영한 current completion priority order와 잔여 작업량/turn envelope: [docs/work_tickets.md](../work_tickets.md)의 `Confirmed Completion Priority Order`, `Estimated Turn Envelope`
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
- remote search provider는 구조적으로 Tavily와 custom endpoint 둘 다 지원한다. 현재 canonical live unknown-CWE proving ground는 Tavily를 기준으로 유지되지만, researcher remote capability 자체가 Tavily-only인 것은 아니다.
- `remote_required`는 remote provider가 없으면 fail-closed하고, `remote_prefer`는 local corpus fallback이 가능하다. 따라서 Tavily necessity는 global prerequisite가 아니라 “current canonical live remote-research lane” prerequisite로 읽는 편이 맞다.
- ops/E2E entry에서도 same distinction을 유지한다. `VULD_E2E_REQUIRE_REMOTE_PROVIDER=1`는 generic remote capability gate이고, `VULD_E2E_REQUIRE_TAVILY=1`는 current canonical Tavily proving-ground gate다.

## Current Residual Owners

- evidence authority / contradiction policy residual은 `TKT-001-G` owner다.
- perf/cache reuse를 authoritative measured gate로 승격하는 residual은 `TKT-008-A1/A2` owner다.
- planning-only pair(`foobar-name-only-negative`, `open-redirect-strict-dynamic-no-remote`)는 cache/reuse observation이 measured gate blocker로 어떻게 남는지 확인하는 cheapest no-Docker pair다.
- RAG 문서는 retrieval helper와 cache surface를 설명할 수 있지만, generalized evidence reasoning closure를 claim하면 안 된다.

## Residual Review Focus

- `TKT-001-G` residual은 retrieval 결과가 authority threshold/contradiction policy를 실제로 얼마나 돕는지부터 본다.
- `TKT-008-A*` residual은 cache/reuse observation이 measured gate blocker와 어떻게 이어지는지부터 본다.
- cheapest no-Docker cache/reuse sanity는 planning-only pair의 `repeatability_report.json`에서 `cache_reuse_inconsistent`가 계속 blocker로 남는지부터 보는 것이다.

## Completion Review Focus

- `TKT-001-G` completion은 retrieval/memory helper가 authority threshold와 contradiction-aware selection을 돕되, evidence proof를 과장하지 않는 보조 surface로 남는지부터 본다.
- `TKT-008-A*` completion은 cache/reuse observation이 measured gate authoritative input으로 재사용되되, standalone success claim으로 오해되지 않는지부터 본다.

## Priority Companions

이 문서를 우선순위 판단 관점으로 읽을 때는 아래 문서를 같이 본다.

- current completion priority order: [docs/work_tickets.md](../work_tickets.md)의 `Confirmed Completion Priority Order`
- 잔여 작업량과 practical turn envelope: [docs/work_tickets.md](../work_tickets.md)의 `Estimated Turn Envelope`
- representative evidence와 함께 보는 turn estimate shortcut: [docs/work_tickets.md](../work_tickets.md)의 `Turn Estimate Entry`
- priority companion set / reading order: [docs/work_tickets.md](../work_tickets.md)의 `Priority Companions`, `Priority Reading Order`
- latest positive representative pair의 ticket-form reading: [docs/work_tickets.md](../work_tickets.md)의 `Assessment-To-Ticket Interpretation`
- LLM-response 기준 residual/priority 해석: [docs/work_tickets.md](../work_tickets.md)의 `LLM-Response Capability Overlay`
- current truth / non-claim: [docs/current_state_gap_analysis.md](../current_state_gap_analysis.md), [docs/constraints.md](../constraints.md)
- code/harness entry: [docs/code/README.md](README.md), [tests/e2e/README.md](../../tests/e2e/README.md)

## Priority Review Focus

- current completion priority order에서 RAG/retrieval은 `TKT-001-G`와 `TKT-008-A*` companion surface다.
- retrieval/cache 보강만으로 runtime/oracle/support bucket 우선순위를 앞지르는 것이 아니라, evidence authority와 measured reuse closure를 돕는 축으로 읽는다.
- latest positive representative pair의 ticket-form reading도 retrieval이 runtime materialization owner가 아니라 evidence/reuse support 축이라는 점을 유지한다. canonical 해석은 [docs/work_tickets.md](../work_tickets.md)의 `Assessment-To-Ticket Interpretation`을 따른다.
- 잔여 작업량/turn envelope 해석도 [docs/work_tickets.md](../work_tickets.md)의 `Estimated Turn Envelope`를 같이 따른다.
- turn estimate shortcut도 [docs/work_tickets.md](../work_tickets.md)의 `Turn Estimate Entry`를 같이 따른다.
- LLM-response stricter reading에서도 retrieval은 positive Docker materialization 자체보다 evidence authority와 reuse closure를 돕는 보조 축으로만 읽는다.
- LLM-response 기준 상세 해석은 [docs/work_tickets.md](../work_tickets.md)의 `LLM-Response Capability Overlay`를 따른다.

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
- 우선순위 판단:
  - 이 문서의 `Priority Review Focus`
  - [docs/work_tickets.md](../work_tickets.md)의 `Priority Companions`
  - [docs/work_tickets.md](../work_tickets.md)의 `Assessment-To-Ticket Interpretation`

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
  - latest cheapest no-Docker pair:
    - `foobar-name-only-negative`
    - `open-redirect-strict-dynamic-no-remote`

## Representative Validation Surface

- retrieval/cache adapter regression:
  - `tests/test_web_search_tool.py`
  - `tests/test_web_search_custom.py`
  - `tests/test_web_search_tavily.py`
- researcher/RAG handoff regression:
  - `tests/test_researcher_search_artifacts.py`
  - `tests/test_repeatability_gate.py`
  - low-cost no-Docker cache/matrix pair:
    - `foobar-name-only-negative`
    - `open-redirect-strict-dynamic-no-remote`

## How To Update This Document

- retrieval adapter, memory helper, cache/reuse surface가 바뀔 때만 갱신한다.
- current measured perf truth는 [docs/current_state_gap_analysis.md](../current_state_gap_analysis.md)에 남긴다.
- current authority/non-claim은 [docs/constraints.md](../constraints.md)에 남긴다.
- backlog owner와 sequencing은 [docs/final_solution.md](../final_solution.md), [docs/work_tickets.md](../work_tickets.md)로 보낸다.
- ticket-first entrypoint나 representative validation surface가 바뀌면 이 문서의 해당 섹션도 같이 갱신한다.
- completion review focus가 바뀌면 same authority/perf owner mapping에 맞춰 이 문서도 같이 갱신한다.
- residual review focus가 바뀌면 same authority/perf owner mapping에 맞춰 이 문서도 같이 갱신한다.
- priority review focus나 priority companion 해석이 바뀌면 [docs/code/README.md](README.md), [docs/work_tickets.md](../work_tickets.md)와 같이 갱신한다.
- LLM-response stricter reading의 retrieval-side 해석이 바뀌면 [docs/work_tickets.md](../work_tickets.md)의 `LLM-Response Capability Overlay`와 같이 갱신한다.
- latest positive representative pair의 ticket-form 해석이 바뀌면 [docs/work_tickets.md](../work_tickets.md)의 `Assessment-To-Ticket Interpretation`와 같이 갱신한다.
- 잔여 작업량/turn envelope 해석이 바뀌면 [docs/work_tickets.md](../work_tickets.md)의 `Estimated Turn Envelope`와 같이 갱신한다.
- [docs/work_tickets.md](../work_tickets.md)의 `Turn Estimate Entry`가 바뀌면 same shortcut도 같이 갱신한다.
- review mode entry shortcut이 바뀌면 [docs/code/README.md](README.md)와 같이 갱신한다.
- cache/reuse representative harness path가 바뀌면 [tests/e2e/README.md](../../tests/e2e/README.md)와 같이 갱신한다.
