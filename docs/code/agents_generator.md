# agents/generator 디렉토리

Status: support
Audience: implementation
Source of truth for: generator modes, synthesis/template/compiler entrypoints
Not the source of truth for: project-level roadmap or current evidence baseline
Last validated against: current repo layout, stage-aware recovery dispatch, bounded fallback/runtime/oracle hardening, and active ticket decomposition on 2026-03-19

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

- `agents/generator/main.py`: generator CLI entry
- `agents/generator/service.py`: mode 선택, compiler/template/synthesis orchestration
- `agents/generator/synthesis.py`: manifest candidate 생성, guard, deterministic fallback

## 현재 구현상 포인트

- current synthesis는 one-shot manifest candidate와 deterministic fallback을 함께 사용합니다.
- dynamic lane의 boundedness는 family-aware/semantic-guided fallback builder에 크게 의존합니다.
- `request_ir`, `runtime_recipe`, `executor_plan`, `exploit_oracle`가 prompt/contract에 주입되지만, 아직 staged synthesis control-plane은 아닙니다.
- `selection_decision`, `design_brief.required_roles`, `selected_oracle_mode/source`는 prompt/retry/guard input으로는 많이 올라왔지만, 아직 primitive-first materialization branch controller는 아닙니다.
- `name_only_generation_spec`에는 이제 `scenario_candidate_summary`와 `selection_decision.scenario`가 들어가므로, generator는 family/stack만이 아니라 `family x stack x topology` alignment를 prompt에서 직접 볼 수 있습니다.
- `GeneratorService._requirement_for_synthesis()`는 이제 `staged_synthesis`도 주입하므로, synthesis prompt는 `candidate_resolution -> design_brief -> runtime_plan -> oracle_contract` 요약을 함께 봅니다.
- latest slice에서 `design_brief`도 `selected_topology`, `selected_oracle_mode`, `dependency_set`, `required_roles`를 싣기 시작했습니다. 즉 generator는 selected scenario의 oracle/dependency workload를 family label만이 아니라 staged brief에서도 직접 읽습니다.
- `SynthesisEngine`는 이제 candidate/manifest/failure log에 `failure_stage`와 `failure_stage_reason`를 남기며, `staged_synthesis` snapshot을 `generator_candidates.json`, `generator_manifest.json`, `generator_failures.jsonl`에 함께 기록합니다.
- `SynthesisEngine.run()`은 이제 직전 candidate의 `failure_stage`를 읽어 다음 candidate prompt에 `Stage-Aware Retry Hint`를 추가합니다. 즉, retry는 더 이상 generic failure_context만 보지 않고 `runtime_plan`/`design_brief`/`oracle_contract` 같은 단계별 contract를 기준으로 좁혀집니다.
- latest slice에서 `design_brief.required_roles`도 stage-aware recovery dispatch에 쓰이기 시작했습니다. `design_brief` 실패라도 dependency-heavy brief는 `runtime_plan` repair를, oracle-heavy brief는 `oracle_contract` repair를 먼저 시도합니다.
- latest slice에서 `runtime_plan` repair도 thin runtime plan일 때 `design_brief`의 `selected_topology`/`dependency_set`을 fallback target으로 읽어 `target_topology`, `target_db`, `target_sidecars` metadata를 복구할 수 있게 됐습니다.
- latest slice에서 `design_brief.required_roles`는 recovery dispatch뿐 아니라 fresh candidate guard에도 연결됐습니다. `dependency_db`/`dependency_sidecar`가 요구되는데 manifest에 그 신호가 없으면 early runtime violation으로 분류돼 stage-aware repair 쪽으로 더 빨리 흘러갑니다.
- latest slice에서 `design_brief.required_roles`는 semantic-guided fallback family selection에도 제한적으로 들어가기 시작했습니다. 현재는 `dependency_db`와 bounded DB target이 분명한 brief에서만 `sqli` minimal dynamic fallback을 우선 고를 수 있습니다.
- latest slice에서는 semantic signature가 비어 있어도 researcher `top_family/high/non-ambiguous`가 충분히 강하면 bounded minimal_dynamic fallback으로 salvage할 수 있는 경로도 생겼습니다. selection source는 `researcher_top_family_no_semantic_signature`로 남고, 이는 primitive-first control-plane이 아니라 bounded fallback salvage입니다.
- latest slice에서는 generic unsupported fallback과 semantic-guided fallback도 `design_brief`의 topology/dependency/oracle metadata를 보수적으로 함께 싣기 시작했습니다. 즉 fallback manifest가 `target_topology`, `target_db`, `target_sidecars`, `design_brief_oracle_mode/source`를 잃지 않고 executor-facing metadata로 넘길 수 있습니다.
- latest slice에서는 SQLi minimal dynamic fallback이 `design_brief`의 external DB target(`mysql/mariadb/postgres`)을 실제 service code, requirements, `run.env`까지 제한적으로 반영할 수 있게 됐습니다. 즉 bounded `sqli` lane에서는 fallback manifest 자체가 sqlite single-service만 고집하지 않게 됐습니다.
- 같은 bounded SQLi external DB fallback은 이제 `schema.sql`도 실제 산출물로 내보내기 시작했습니다. 따라서 `runtime_recipe.seed_files -> executor sidecar seed apply` 체인에 natural seed surface를 제공할 수 있습니다.
- same bounded SQLi external DB fallback service code도 이제 `schema.sql`을 직접 읽어 init하도록 맞춰지기 시작했습니다. 즉 degraded app init path와 executor seed surface가 완전히 따로 놀지는 않게 됐습니다.
- latest slice에서는 compiler-generated MySQL sidecar lane도 `schema.sql`을 실제 산출물로 내보내고 service code가 그 file을 직접 읽도록 맞춰지기 시작했습니다. 즉 external DB compiler lane도 bounded seed surface와 executor seed chain에 더 자연스럽게 접속합니다.
- same compiler lane은 latest slice에서 executable `verification_spec`도 같이 싣기 시작했습니다. 즉 compiler-generated MySQL/open-redirect lane도 runnable negative/metamorphic replay를 위한 oracle surface를 부분적으로 제공합니다.
- latest direct rerun 기준으로 same compiler-generated MySQL sidecar lane은 이 oracle surface를 통해 `oracle_execution_parity = high`까지 올릴 수 있게 됐습니다. 다만 이건 bounded compiler lane 성공이지 fallback/stateful lane 일반을 뜻하지는 않습니다.
- latest slice에서는 representative stateless/body-structured/sessionful minimal_dynamic fallback(`open_redirect`, `template_injection`, `path_traversal`, `ssrf`, `deserialization`, `xxe`, `csrf`)도 payload-bearing `verification_spec`와 payload-aware `poc.cmd`를 함께 싣기 시작했습니다. direct rerun 기준으로 same bounded fallback lanes는 runnable oracle replay를 통해 `oracle_execution_parity = high`까지 올릴 수 있습니다.
- 모든 candidate가 실패하면 `SynthesisEngine`은 이제 `runtime_plan` 실패에 대해 runtime-safe fallback recovery를, `oracle_contract` 실패에 대해 PoC/oracle realignment recovery를 먼저 시도한 뒤에만 기존 semantic-guided fallback으로 내려갑니다.
- 이 stage-aware 결과는 이제 PACK에서도 읽히므로, generator 내부 recovery가 manifest final summary와 run-case summary에 어떤 흔적을 남기는지 operator가 바로 확인할 수 있습니다.

## Current Residual Owners

- primitive-first generator controller 부재는 주로 `TKT-001-A/D/E/F/G` owner다.
- stage persistence / repair-first / downgrade journaling residual은 `TKT-006-A/B/C` owner다.
- 현재 generator 문서는 “primitive-informed bounded generation”까지는 설명할 수 있지만, primitive-first generalized synthesis를 claim하면 안 된다.

이 디렉토리 작업은 항상 [docs/final_solution.md](../final_solution.md)의 phased plan과 [docs/constraints.md](../constraints.md)의 generator constraints를 기준으로 해야 합니다.

## Residual Review Focus

- `TKT-001` residual은 `service.py`에서 selection/branch consumption, `synthesis.py`에서 scenario-dependent generation path가 실제로 갈리는지부터 본다.
- `TKT-006` residual은 `synthesis.py`와 `generator_manifest.json` / `generator_failures.jsonl` / `loop_state.json`에서 stage persistence와 repair-first retry가 남는지부터 본다.

## Completion Review Focus

- `TKT-001` completion은 `service.py`와 `synthesis.py`가 family label이 아니라 primitive/dependency/topology/oracle branch를 실제 materialization path에 반영하는지부터 본다.
- `TKT-006` completion은 `generator_manifest.json`, `generator_failures.jsonl`, `loop_state.json`가 stage persistence, repair-first retry, downgrade trace를 fallback 이전 canonical path로 남기는지부터 본다.

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

- `TKT-001`을 먼저 볼 때:
  - `agents/generator/service.py`
  - `agents/generator/synthesis.py`
  - `common/contracts.py`
- `TKT-006`을 먼저 볼 때:
  - `agents/generator/synthesis.py`
  - `metadata/<SID>/generator_manifest.json`
  - `metadata/<SID>/generator_failures.jsonl`
  - `metadata/<SID>/loop_state.json`
- `TKT-007`과 맞닿는 generator-side oracle surface를 볼 때:
  - generated `verification_spec`
  - generated `poc.py`
  - generated `poc.cmd`

## Representative Validation Surface

- generator/synthesis regression:
  - `tests/test_generator_template_planner.py`
  - `tests/test_name_only_helpers.py`
  - `tests/test_synthesis_prompt_contract.py`
  - `tests/test_synthesis_semantic_guard.py`
  - `tests/test_synthesis_fallback_poc.py`
  - `tests/test_synthesis_executor_constraints.py`
  - `tests/test_synthesis_stdlib_filter.py`
- representative direct rerun:
  - non-SQLi name-only lane for `TKT-001`
  - semantic-guided dynamic lane for `TKT-006`
  - payload-bearing dynamic lane for generator-side oracle surface sanity

## How To Update This Document

- generator entrypoint, synthesis path, staged recovery wiring이 바뀔 때만 갱신한다.
- current rerun truth나 representative lane behavior는 [docs/current_state_gap_analysis.md](../current_state_gap_analysis.md)에 남긴다.
- current non-claim과 boundedness는 [docs/constraints.md](../constraints.md)에 남긴다.
- phase ordering과 subtask owner는 [docs/final_solution.md](../final_solution.md), [docs/work_tickets.md](../work_tickets.md)로 보낸다.
- ticket-first entrypoint나 representative validation surface가 바뀌면 이 문서의 해당 섹션도 같이 갱신한다.
- completion review focus가 바뀌면 같은 owner/ticket mapping에 맞춰 이 문서도 같이 갱신한다.
- residual review focus가 바뀌면 같은 owner/ticket mapping에 맞춰 이 문서도 같이 갱신한다.
- review mode entry shortcut이 바뀌면 [docs/code/README.md](README.md)와 같이 갱신한다.
- direct rerun harness나 generator-related representative lane selection이 바뀌면 [tests/e2e/README.md](../../tests/e2e/README.md)와 같이 갱신한다.
