# evals 디렉토리

Status: support
Audience: implementation
Source of truth for: verifier entrypoints and result surfaces
Not the source of truth for: artifact-quality policy or project roadmap
Last validated against: current repo layout, oracle execution parity hardening, and measured workflow wiring on 2026-03-19

Relevant canonical docs:
- [제약조건](../constraints.md)
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

- `evals/poc_verifier/main.py`: verifier entrypoint
- `evals/poc_verifier/rule_based.py`: rule/contract/log based verification
- `evals/poc_verifier/registry.py`: verifier registry
- `evals/poc_verifier/llm_assisted.py`: optional LLM-assisted verifier path

## 현재 구현상 포인트

- verifier는 declared rule, runtime rule, contract-oracle fallback을 구분합니다.
- executor가 남긴 `oracle_execution.json`을 읽어 negative/metamorphic replay 결과를 verifier surface에 올리기 시작했습니다.
- eval 결과는 `verify_pass` 외에도 trust, independence, semantic consistency, `oracle_execution_parity`를 같이 읽어야 합니다.
- higher-level measured gate는 verifier 하나만으로 닫히지 않습니다. 현재 workflow에서는 `artifacts/<SID>/reports/evals.json`과 direct-run `summary.json`이 `repeatability_report.json`, `matrix_report.json`, `support_candidate.json`으로 다시 집계됩니다.
- 따라서 verifier 결과를 해석할 때는 `verify_pass=true`와 `oracle_execution_parity=high`를 곧바로 `artifact_quality.band=high`나 support-ready claim으로 읽지 않습니다.
- broader browserful/stateful oracle residual은 여전히 roadmap의 Phase 4 / `TKT-007` owner입니다. current eval surface는 representative stateless/body-structured/sessionful replay hardening까지가 주 closure입니다.

## Current Residual Owners

- broader browserful/stateful oracle replay residual은 `TKT-007-A/B` owner다.
- measured gate / quality-tier policy residual은 `TKT-008-A*`, `TKT-008-B*` owner다.
- planning-only pair(`foobar-name-only-negative`, `open-redirect-strict-dynamic-no-remote`)에서 `authority_ready`와 `measured_gate_blocked`가 동시에 남는 cheapest no-Docker measured sanity는 현재 `TKT-008-A1` residual reading에 포함된다.
- positive LLM-shaped lane(`trusted-dynamic-sqli`)는 eval/oracle surface를 실제 Docker run 이후에 읽어야 하며, latest Docker-enabled rerun에서는 이 경로 자체는 다시 열렸다. 다만 current repeatability/support truth는 여전히 `measured_gate.ready=false`, `reviewable_bundle_count=0`이라 eval closure와 promotion closure를 분리해서 읽어야 한다.
- representative positive pair의 ticket-form 해석은 [docs/work_tickets.md](../work_tickets.md)의 `Assessment-To-Ticket Interpretation`을 따른다. eval 관점에서는 `trusted-dynamic-sqli`가 `TKT-008-A*`, `TKT-009-A1`, `open-redirect-dynamic-name-only`가 `TKT-008-A*`와 함께 `TKT-001`/`TKT-006` signal을 남긴다는 점이 중요하다.
- same positive pair의 current closure는 eval 관점에서도 `runnable but not promotable`이다. representative repeatability/support aggregate가 `authority_ready_bundle_count=2`, `reviewable_bundle_count=0`로 남기 때문이다.
- same positive pair의 canonical rerun/support command chain은 [tests/e2e/README.md](../../tests/e2e/README.md)의 `Positive Pair Promotion Check`를 따른다.
- measured/support wording이나 blocker projection만 바뀐 경우 fastest project-level preflight는 `Focused No-Docker Regression Slice`다. eval 관점에서는 특히 `tests/test_repeatability_gate.py`, `tests/test_support_extract.py`, `tests/e2e/test_case_matrix_rollup.py`, `tests/e2e/test_support_workflow.py`가 먼저 흔들린다.
- eval 문서는 executed oracle와 verifier surface를 설명할 수 있지만, 이것만으로 support-ready or high-quality artifact closure를 claim하면 안 된다.

## Residual Review Focus

- `TKT-007` residual은 `oracle_execution.json`과 `evals.json`이 single-step을 넘는 richer stateful replay를 얼마나 반영하는지부터 본다.
- `TKT-008` residual은 verifier truth가 measured gate / quality-tier policy로 어떻게 다시 집계되는지부터 본다.
- cheapest no-Docker measured gate sanity는 planning-only pair의 `repeatability_report.json -> support_candidate.json`에서 `measured_gate_blocked_bundle_count > 0`, `reviewable_bundle_count = 0`가 유지되는지부터 본다.

## Completion Review Focus

- `TKT-007` completion은 `oracle_execution.json`, `evals.json`, quality-tier surface가 richer browserful/stateful replay truth를 함께 반영하는지부터 본다.
- `TKT-008` completion은 verifier truth가 measured gate blocker/policy surface로 authoritative하게 재집계되는지부터 본다.

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

- current completion priority order에서 evals는 `TKT-007` 다음 `TKT-008`을 읽는 핵심 companion이다.
- 즉 oracle realism이 measured gate authoritative화보다 앞선다는 순서를 verifier/eval artifact 관점에서 확인할 때 이 문서를 먼저 본다.
- LLM-response stricter reading에서도 positive LLM-shaped eval closure는 Docker/runtime 이후 문제이므로, same `TKT-007 -> TKT-008` 순서를 유지하는 companion으로 읽는다.
- latest positive representative pair의 ticket-form 해석도 [docs/work_tickets.md](../work_tickets.md)의 `Assessment-To-Ticket Interpretation`을 같이 따른다.
- 잔여 작업량/turn envelope 해석도 [docs/work_tickets.md](../work_tickets.md)의 `Estimated Turn Envelope`를 같이 따른다.
- turn estimate shortcut도 [docs/work_tickets.md](../work_tickets.md)의 `Turn Estimate Entry`를 같이 따른다.
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

- `TKT-007`을 먼저 볼 때:
  - `evals/poc_verifier/main.py`
  - `evals/poc_verifier/rule_based.py`
  - `artifacts/<SID>/run/oracle_execution.json`
  - `artifacts/<SID>/reports/evals.json`
- `TKT-008`을 먼저 볼 때:
  - `artifacts/<SID>/reports/evals.json`
  - `repeatability_report.json`
  - `matrix_report.json`
  - `support_candidate.json`
  - fastest no-Docker pytest preflight:
    - `tests/test_repeatability_gate.py`
    - `tests/test_support_extract.py`
    - `tests/e2e/test_case_matrix_rollup.py`
    - `tests/e2e/test_support_workflow.py`
  - latest cheapest no-Docker pair:
    - `foobar-name-only-negative`
    - `open-redirect-strict-dynamic-no-remote`

## Representative Validation Surface

- verifier/eval regression:
  - `tests/test_rule_based_semantic_contract.py`
  - `tests/test_llm_assisted_verifier.py`
  - `tests/test_run_case_summary_surface.py`
- measured rollup sanity:
  - `tests/test_repeatability_gate.py`
  - `tests/e2e/test_case_matrix_rollup.py`
  - fastest project-level no-Docker preflight slice:
    - `tests/test_name_only_helpers.py`
    - `tests/test_pack_promotion.py`
    - `tests/test_repeatability_gate.py`
    - `tests/test_support_extract.py`
    - `tests/e2e/test_support_workflow.py`
    - `tests/e2e/test_case_matrix_rollup.py`
  - low-cost no-Docker measured/support pair:
    - `foobar-name-only-negative`
    - `open-redirect-strict-dynamic-no-remote`

artifact quality나 support claim을 해석할 때는 반드시 [docs/constraints.md](../constraints.md)의 verifier/oracle constraints를 같이 참고합니다.

## How To Update This Document

- verifier entrypoint, result surface, oracle replay integration이 바뀔 때만 갱신한다.
- current rerun truth와 representative oracle behavior는 [docs/current_state_gap_analysis.md](../current_state_gap_analysis.md)에 남긴다.
- trust/quality/support claim 한계는 [docs/constraints.md](../constraints.md)에 남긴다.
- owner와 sequencing은 [docs/final_solution.md](../final_solution.md), [docs/work_tickets.md](../work_tickets.md)로 보낸다.
- ticket-first entrypoint나 representative validation surface가 바뀌면 이 문서의 해당 섹션도 같이 갱신한다.
- completion review focus가 바뀌면 same oracle/measured owner mapping에 맞춰 이 문서도 같이 갱신한다.
- residual review focus가 바뀌면 same oracle/measured owner mapping에 맞춰 이 문서도 같이 갱신한다.
- priority review focus나 priority companion 해석이 바뀌면 [docs/code/README.md](README.md), [docs/work_tickets.md](../work_tickets.md)와 같이 갱신한다.
- LLM-response stricter reading의 eval-side 해석이 바뀌면 [docs/work_tickets.md](../work_tickets.md)의 `LLM-Response Capability Overlay`와 같이 갱신한다.
- latest positive representative pair의 ticket-form 해석이 바뀌면 [docs/work_tickets.md](../work_tickets.md)의 `Assessment-To-Ticket Interpretation`와 같이 갱신한다.
- 잔여 작업량/turn envelope 해석이 바뀌면 [docs/work_tickets.md](../work_tickets.md)의 `Estimated Turn Envelope`와 같이 갱신한다.
- [docs/work_tickets.md](../work_tickets.md)의 `Turn Estimate Entry`가 바뀌면 same shortcut도 같이 갱신한다.
- review mode entry shortcut이 바뀌면 [docs/code/README.md](README.md)와 같이 갱신한다.
- eval-related rerun/harness flow가 바뀌면 [tests/e2e/README.md](../../tests/e2e/README.md)와 같이 갱신한다.
