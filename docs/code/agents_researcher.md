# agents/researcher 디렉토리

Status: support
Audience: implementation
Source of truth for: researcher query/evidence/guard generation entrypoints
Not the source of truth for: generalized evidence policy or high-level roadmap
Last validated against: current repo layout, evidence/selection surface expansion, and active ticket decomposition on 2026-03-19

Relevant canonical docs:
- [현재 상태](../current_state_gap_analysis.md)
- [제약조건](../constraints.md)
- [로드맵](../final_solution.md)
- [작업 티켓](../work_tickets.md)
- success criteria 5축과 backlog owner 대응: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Completion Axis Map`
- completion companion set과 canonical reading order: [docs/work_tickets.md](../work_tickets.md)의 `Completion Companions`, `Open-World Completion Reading Order`
- success criteria 5축의 완료판정 질문과 최소 근거: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Completion Checklist`
- success criteria 5축의 canonical 완료 검토 순서: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Completion Review Flow`
- latest confirmed residual의 축별 ticket bundle 분해: [docs/work_tickets.md](../work_tickets.md)의 `Open-World Residual Ticket Breakdown`
- [검증 하니스](../../tests/e2e/README.md)

## 핵심 파일

- `agents/researcher/main.py`: researcher CLI entry
- `agents/researcher/service.py`: query plan, search, evidence graph, guard spec, researcher report 생성

## 현재 구현상 포인트

- family hypothesis와 stack candidates는 retrieval evidence를 바탕으로 enrich되지만 아직 closed-vocabulary 경향이 강합니다.
- evidence graph와 source authority는 operator-facing summary를 개선하지만, causal proof나 full control-plane을 뜻하지는 않습니다.
- researcher output은 generator와 pack surface에 크게 영향을 주므로 `request_ir`, `family_hypothesis_summary`, `tech_stack_candidates`, `evidence_graph`를 함께 봐야 합니다.
- latest slice에서는 query cache / diminishing-return early stop / cache observation surface가 들어가 measured performance summary와 `repeatability_report.json`까지 이어집니다.
- same slice에서는 `primitive_hypotheses`, `provisional_family`, scenario-level evidence authority가 `selection_decision`과 `scenario_candidates`까지 더 직접 연결되기 시작했지만, 이것 역시 bounded known-family induction이지 open-vocabulary discovery는 아닙니다.
- researcher `top_family/high/non-ambiguous`는 semantic signature가 비어 있을 때 bounded fallback salvage source로도 쓰일 수 있지만, 이것을 primitive-first controller나 evidence-complete selection으로 읽으면 안 됩니다.

## Current Residual Owners

- evidence authority threshold / contradiction policy residual은 `TKT-001-G` owner다.
- closed-vocabulary family residual은 near-term `TKT-001-C`, long-term `TKT-010-A` owner다.
- performance reuse를 authoritative measured gate로 닫는 residual은 `TKT-008-A1/A2` owner다.

## Residual Review Focus

- selection/evidence residual은 `service.py`의 `primitive_hypotheses`, `provisional_family`, `scenario_candidates`, contradiction handling을 먼저 본다.
- measured reuse residual은 `performance_summary.json`과 repeatability/matrix artifacts의 search/cache observation이 실제 gate policy와 어떻게 이어지는지부터 본다.

## Completion Review Focus

- `TKT-001-G` completion은 researcher output이 evidence summary를 넘어서 authority threshold와 contradiction-aware selection input으로 실제 branchable surface를 남기는지부터 본다.
- `TKT-008-A*` completion은 `performance_summary.json`과 repeatability/matrix artifacts의 cache/reuse observation이 measured gate authoritative input으로 재사용되는지부터 본다.

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

- `TKT-001-C`, `TKT-001-G`를 먼저 볼 때:
  - `agents/researcher/service.py`
  - `request_ir.family_hypothesis_summary`
  - `primitive_hypotheses`, `provisional_family`, `scenario_candidates`
- `TKT-008-A1/A2`와 연결된 reuse/perf surface를 볼 때:
  - `agents/researcher/service.py`
  - `metadata/<SID>/performance_summary.json`
  - repeatability/matrix artifacts의 search/cache observation

## Representative Validation Surface

- researcher/evidence regression:
  - `tests/test_researcher_search_artifacts.py`
  - `tests/test_researcher_guard_normalization.py`
  - `tests/test_researcher_main_skip_policy.py`
  - `tests/test_researcher_multibundle_continue.py`
- measured reuse observation sanity:
  - `tests/test_repeatability_gate.py`
  - representative `repeat_case.py` rerun with search/cache observation enabled

## How To Update This Document

- researcher entrypoint, evidence surface, cache/reuse wiring이 바뀔 때만 갱신한다.
- current rerun-backed evidence behavior는 [docs/current_state_gap_analysis.md](../current_state_gap_analysis.md)에 남긴다.
- authority/non-claim은 [docs/constraints.md](../constraints.md)에 남긴다.
- backlog owner와 sequencing은 [docs/final_solution.md](../final_solution.md), [docs/work_tickets.md](../work_tickets.md)로 보낸다.
- ticket-first entrypoint나 representative validation surface가 바뀌면 이 문서의 해당 섹션도 같이 갱신한다.
- completion review focus가 바뀌면 같은 owner/ticket mapping에 맞춰 이 문서도 같이 갱신한다.
- residual review focus가 바뀌면 같은 owner/ticket mapping에 맞춰 이 문서도 같이 갱신한다.
- review mode entry shortcut이 바뀌면 [docs/code/README.md](README.md)와 같이 갱신한다.
- representative rerun/harness path가 바뀌면 [tests/e2e/README.md](../../tests/e2e/README.md)와 같이 갱신한다.
