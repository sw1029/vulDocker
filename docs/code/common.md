# common 디렉토리

Status: support
Audience: implementation
Source of truth for: shared helpers, contracts, prompt and policy utilities
Not the source of truth for: project roadmap or current constraints
Last validated against: current repo layout, scenario-selection/staged-synthesis surfaces, bounded runtime-contract hardening, and active ticket decomposition on 2026-04-02

Relevant canonical docs:
- [문제 정의](../problem.md)
- [현재 상태](../current_state_gap_analysis.md)
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

## 구성 요소

- `common/name_only.py`: name-only mode contract, closure path policy, intent classification helper
- `common/contracts.py`: `request_ir`, `runtime_recipe`, `executor_plan`, `exploit_oracle`, `name_only_generation_spec`, `staged_synthesis`, `selection_branch_trace` 생성
- `common/prompts/templates.py`: researcher/generator/reviewer prompt surface
- `common/paths.py`: 저장소 경로 규칙
- `common/sid.py`: SID 필드 해시
- `common/plan.py`: `plan.json` 로더
- `common/run_matrix.py`: 단일/다중 취약 번들 경로 헬퍼
- `common/config/*`: API 키와 decoding profile
- `common/llm/provider.py`: litellm/stub path
- `common/variability/manager.py`: variation key와 decoding profile 선택

## 구현상 중요 포인트

- `common/name_only.py`는 mode별 allowed closure와 intent-satisfying path를 정의하는 Phase 0 진입점입니다.
- `common/contracts.py`는 summary surface가 아니라 실질적인 control-plane 후보를 만드는 곳이라, staged synthesis와 executor parity 작업의 중심입니다.
- `selection_decision`, `ready_for_materialization`, `open_world_evidence_ready`, `name_only_outcome` 사이 state machine은 더 정리됐지만 아직 single authoritative partial-lane controller는 아닙니다.
- `request_ir`에는 이제 `primitive_hypotheses`, `runtime_dependency_hypotheses`, `topology_hypotheses`, `scenario_candidates`, `provisional_family` 같은 Phase 1 초기 surface가 들어갑니다.
- `common/contracts.py`는 이제 researcher family hypothesis가 비거나 약할 때 `semantic_signature -> primitive_hypotheses -> primitive_signature family candidate -> provisional_family` 경로를 보수적으로 생성합니다. 이 candidate는 working hypothesis로는 쓰이지만 low-trust source만으로 자동 selection되지는 않습니다.
- 같은 primitive-guided lane에서 현재는 `sql_injection`류에 한해 low-confidence `db:sqlite` runtime dependency hint도 생성하고, 이 hint를 `scenario_candidates[].dependency_set`까지 내려 planning surface에 반영합니다.
- 같은 primitive-guided lane에서 selected known family에는 low-confidence `oracle_hypotheses`도 추가될 수 있고, 이 hint는 `scenario_candidates[].oracle_profile`, `name_only_generation_spec`, `staged_synthesis.oracle_contract`까지 내려갑니다.
- `selection_decision.scenario`, `scenario_candidate_summary`, `staged_synthesis.candidate_resolution`도 이제 `selected_oracle_mode`/`selected_oracle_source` 같은 scenario-level oracle selection truth를 같이 싣습니다.
- `staged_synthesis.design_brief`도 이제 `selected_topology`, `selected_oracle_mode`, `dependency_set`, derived `required_roles`를 같이 싣기 시작했습니다. generator는 이 surface를 통해 stateful oracle/sidecar/db 성격을 prompt에서 더 직접 읽습니다.
- 이 `design_brief.required_roles`는 이제 generator recovery dispatch에도 연결돼서, `design_brief` 실패가 나도 dependency-heavy brief는 `runtime_plan` repair로, oracle-heavy brief는 `oracle_contract` repair로 우선 보낼 수 있습니다.
- `runtime_plan` repair도 이제 thin `runtime_plan`만 남아 있을 때 `design_brief`의 `selected_topology`/`dependency_set`을 fallback target으로 읽어 `target_topology`, `target_db`, `target_sidecars` metadata를 채웁니다.
- latest slice에서 same `design_brief.required_roles`는 fresh candidate guard에도 연결돼, `dependency_db`/`dependency_sidecar`가 필요한 brief인데 manifest가 그 신호를 못 내면 조기 runtime violation이 추가됩니다.
- same `design_brief.required_roles`는 이제 semantic-guided fallback family resolution에도 제한적으로 들어가서, semantic candidate가 비어 있어도 `dependency_db + db target`이 분명한 brief는 bounded `sqli` fallback family를 선택할 수 있습니다.
- `staged_synthesis.runtime_plan`도 이제 이런 primitive-derived hint를 직접 읽습니다. 즉 runtime recipe가 비어 있을 때 `db`, `topology`와 그 `*_source`가 primitive/runtime hypothesis에서 보수적으로 채워질 수 있습니다.
- `runtime_graph.seed_files`는 이제 `executor_plan.seed_files`까지 내려가고, executor는 declared seed file이 workspace에 실제 존재하는지도 run 전 검증하기 시작했습니다.
- same `seed_files` surface는 이제 bounded external DB lane에도 일부 이어져, mysql/postgres 계열 sidecar가 있고 listed `.sql` seed file이 있으면 executor가 sidecar readiness 이후 해당 SQL seed를 실제 적용할 수 있습니다.
- `runtime_graph.env_contract`도 이제 `executor_plan.env_contract`까지 내려가고, executor는 declared service env key가 resolved `service_env`에 실제 존재하는지도 run 전 검증하기 시작했습니다.
- same `env_contract`는 이제 bounded sidecar lane의 env도 `sidecar:<name>` scope로 `runtime_graph/executor_plan`까지 싣기 시작했습니다. 즉 contract surface가 service env뿐 아니라 declared sidecar env drift도 일부 설명할 수 있습니다.
- generator recovery metadata의 `target_db`/`target_sidecars`도 이제 executor fallback hint로 읽히기 시작했습니다. 즉 generator 쪽 metadata-level target 정렬이 external DB 판단과 sidecar-empty error context까지는 내려옵니다.
- generator recovery metadata의 `target_topology`도 이제 executor fallback hint로 읽히기 시작했습니다. 즉 generator 쪽 metadata-level topology 정렬이 execution surface의 topology/network 판단까지는 내려옵니다.
- latest slice에서는 same hint가 `mysql/mariadb/postgres/postgresql` target에 한해 bounded default sidecar plan synthesis까지 이어지기 시작했습니다.
- 같은 bounded hint는 executor 쪽에서 `service_env` defaults 합성까지 이어지기 시작했습니다.
- `seed_files`도 executor 쪽에서 sqlite lane의 minimal seed/init signal validation까지 이어지기 시작했습니다.
- latest slice에서는 bounded SQLi external DB fallback이 `schema.sql`을 실제 manifest file로 내보내기 시작해, `common/contracts.py`의 `runtime_seed_files -> runtime_recipe.seed_files -> executor_plan.seed_files` 체인과 더 직접 연결됩니다.
- same bounded SQLi external DB fallback service code도 이제 `schema.sql`을 직접 읽는 방향으로 맞춰져, generated seed surface와 degraded runtime init path 사이의 drift가 조금 줄었습니다.
- latest slice에서는 compiler-generated MySQL sidecar lane도 `schema.sql`을 실제 manifest file로 내보내고 service code가 같은 file을 읽도록 맞춰지기 시작했습니다. 즉 compiler lane도 `runtime_seed_files -> sidecar_sql_apply` 체인에 더 직접 연결됩니다.
- latest slice에서는 `generator_manifest.metadata.target_db/target_sidecars/target_topology`와 `run.env`만 있어도 `common/contracts.py`가 bounded sidecar plan을 `runtime_recipe/runtime_graph/executor_plan`까지 합성하기 시작했습니다. 즉 일부 mysql/postgres lane에서는 executor가 raw manifest metadata를 다시 해석하기 전에 contract surface 자체가 sidecar graph를 더 직접 제공합니다.
- 같은 bounded contract-stage synthesis는 이제 `service_env`도 `DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME/APP_PORT` 수준까지 보수적으로 채우고, top-level `service_env`/`resolved.service_env`도 그 값으로 다시 정렬합니다.
- latest slice에서는 이 bounded synthesis provenance도 `runtime_graph`/`executor_plan`까지 같이 실리기 시작했습니다. 즉 `generator_manifest.metadata.target_sidecars`나 `runtime_hint_sidecar_defaults` 같은 source label이 executor-facing contract surface에서 덜 소실됩니다.
- latest slice에서는 same bounded mysql/postgres lane가 `network_enabled=true`, `network_mode=bridge`와 그 source까지 contract 단계에서 싣기 시작했습니다. explicit `executor.allow_network/network_mode`가 있으면 그 cap도 source와 함께 남습니다.
- latest slice에서는 same bounded sidecar lane의 start order도 `sidecar_start_order`로 `runtime_recipe/runtime_graph/executor_plan`까지 실리기 시작했습니다. 즉 dependency order가 sidecar list 순서의 암묵적 가정만으로 남지 않게 됐습니다.
- same bounded order는 이제 `runtime_graph` node/edge에도 `startup_order_index`와 `startup_after`로 실리기 시작했습니다. 즉 graph 자체가 sidecar startup ordering을 조금 더 설명하게 됐습니다.
- latest slice에서는 `seed_strategy`도 `runtime_recipe/runtime_graph/executor_plan`까지 실리기 시작했습니다. 즉 sqlite lane의 `sqlite_service_init`와 external DB lane의 `sidecar_sql_apply`가 `seed_files` 존재만으로 추론되는 대신 bounded contract surface로 더 명시됩니다.
- same `seed_strategy`는 이제 executor의 run 전 contract validation에도 일부 연결돼, explicit strategy가 self-contradictory한 경우를 sqlite/non-sqlite, sidecar/no-sidecar, sql-seed/no-sql-seed 수준에서 early failure로 막기 시작했습니다.
- same bounded external DB seed lane에서는 `volume_contract`도 `runtime_recipe/runtime_graph/executor_plan`까지 실리기 시작했습니다. 현재는 `sidecar:<name> -> /seed-input:ro` mount intent를 설명하는 좁은 surface지만, contract가 actual seed mount 의도를 더 직접 표현하기 시작한 셈입니다.
- same bounded sidecar lane에서는 `network_contract`도 `runtime_recipe/runtime_graph/executor_plan`까지 실리기 시작했습니다. 현재는 service `DB_HOST`와 sidecar alias의 정렬을 설명하는 좁은 surface지만, contract가 alias-level network intent를 더 직접 표현하기 시작한 셈입니다.
- latest slice에서는 same `network_contract`가 executor resolution에도 일부 연결돼, sidecar entry의 alias가 비어 있어도 declared contract가 있으면 execution surface가 그 alias를 보강할 수 있게 됐습니다.
- same network provenance는 이제 executor-facing surface까지 roundtrip되므로, contract-stage `runtime_topology_requires_network`와 policy cap source가 summary에서 덜 소실됩니다.
- `staged_synthesis.oracle_contract`도 explicit `exploit_oracle`이 약한 경우 `mode`, `negative_control_present`, `metamorphic_present`, `source`, `confidence` 같은 working oracle shape를 primitive-derived hint로 보강할 수 있습니다.
- 이 hint는 `runtime_recipe`, `runtime_graph`, `executor_plan`에도 다시 반영됩니다. 그래서 executor-facing contract surface도 primitive-derived `db/topology`와 provenance를 읽을 수는 있지만, 아직 executor가 이를 primary execution controller로 쓰는 단계는 아닙니다.
- `selection_decision`은 family/stack만이 아니라 `scenario` payload도 포함하며, `selected_scenario_id`, `selected_topology`, scenario-level evidence authority를 노출합니다.
- `staged_synthesis`는 이제 `candidate_resolution`, `design_brief`, `runtime_plan`, `executor_plan`, `oracle_contract`, `file_manifest`를 typed intermediate surface로 제공합니다. 즉 runtime/oracle뿐 아니라 executor-facing surface와 build-ready file set도 같은 staged contract 안에서 읽기 시작했습니다.
- latest slice에서는 same `file_manifest`가 `build_ready`, `build_ready_blockers`, `dockerfile_base_images`, `package_installers_detected`, `build_safety_policy(policy_version=docker_build_safety@0.1, blockers, warnings)`까지 같이 남기기 시작했습니다. 따라서 build-ready 여부와 build-time safety warning/blocker를 same staged contract에서 같이 읽을 수 있습니다.
- latest slice에서는 same `file_manifest` build signal이 `pack.py`의 `support_promotion/open_world_readiness`와 `support_extract.py`의 `build_contract` surface까지 연결돼, buildability와 promotability를 measured/support lane에서도 분리해서 읽게 됐습니다.
- latest slice에서는 same staged contract 위에 `selection_branch_trace`도 추가돼, `selection_decision.family/stack/scenario -> candidate_resolution/design_brief/runtime_plan/executor_plan/oracle_contract/file_manifest` alignment를 one-shot machine-readable payload로 읽을 수 있습니다.
- same trace는 `controller_ready`, `branch_aligned`, branch별 `selected_value/materialized_value/aligned`, rejected scenario sample, materialized file/runtime bundle까지 같이 남기므로 selection enrichment와 actual Docker branch causality를 덜 섞습니다.
- latest slice에서는 same contract/provenance 위에 `generation_materialization@0.1`도 정리돼, `generation_origin`, `materializer`, `path_class`, provider attempt/success, fixture/stub flag, provider/model/cache/prompt/retry/timeout/cost surface를 one-shot payload로 읽을 수 있습니다.
- same why-not-live subtype(`fixture_backed`, `provider_disabled` 등)는 `generation_materialization.non_live_reason`에서 시작해 support review/update/apply aggregate의 `by_generation_non_live_reason`로 이어지므로, direct summary와 support workflow가 서로 다른 failure vocabulary를 쓰지 않게 됩니다.
- generator는 이 `staged_synthesis` surface를 prompt에만 보여주는 것이 아니라, failure-stage classification, 기록, 그리고 다음 candidate retry narrowing에도 사용하기 시작했습니다.
- recovery path도 `staged_synthesis`를 읽기 시작했습니다. 현재는 `runtime_plan`과 `oracle_contract` 실패에서 stage-specific repair candidate를 우선 시도하고, 그 다음에 semantic-guided fallback으로 내려갑니다.
- pack/operator surface도 이제 이 흐름을 읽습니다. `staged_recovery`와 `staged_synthesis_summary`가 manifest에 노출되므로 generator 내부 stage-aware behavior를 PACK 이후에도 추적할 수 있습니다.
- latest slice에서는 same staged contract와 single-bundle PACK summary가 actual `image_tag`, `build_log`, `run_log`, `sbom_path` pointer를 다시 surface하기 시작했습니다. 따라서 operator가 build/run artifact 위치를 top-level manifest와 `summary.json`에서 직접 읽을 수 있습니다.
- executor 쪽도 첫 parity slice가 들어가서, `executor_plan.base_url`, `executor_plan.service_env`, `executor_plan.requires_external_db/topology`가 실행 판단에 더 직접 반영됩니다.
- executor는 이제 bundle별 `effective executor policy`를 만들어 `sidecars/network_mode/allow_network`도 `executor_plan`/`runtime_recipe`에서 보완합니다.
- `executor_plan.sidecars`는 이제 global policy defaults보다 더 우선되고, bundle별 sidecar aliases가 있으면 network selection도 bundle-scoped로 재계산됩니다.
- executor는 이제 bundle-scoped execution surface를 한 번 계산해 `run_container_with_poc`, `NetworkPool.acquire`, `_start_sidecars`에 내려보냅니다.
- `executor_plan.sidecars`는 env/ready_probe까지 함께 보존되기 시작했고, `executor_plan.healthchecks`는 `health_path`보다 앞서는 readiness probe 후보가 됩니다.
- prompt surface를 바꾸지 않으면 researcher/generator behavior는 쉽게 안 바뀌므로 `common/prompts/templates.py`를 항상 함께 봐야 합니다.

## Current Residual Owners

- partial-lane decision state-machine residual은 `TKT-001-E/F` owner다.
- strict capability-gate fail-closed subclass split(`strict_dynamic_remote_research_unavailable` vs `strict_dynamic_live_llm_unavailable`) 유지도 현재는 `TKT-001-E` residual reading에 포함된다.
- evidence authority / scenario selection threshold residual은 `TKT-001-G` owner다.
- primitive-first branch controller와 runtime control-plane residual은 `TKT-001-A/D`, `TKT-002-C`, `TKT-003-A`, `TKT-004-A`, `TKT-005-A`와 직접 연결된다.
- 현재 common surface는 strong prompt/contract candidate IR를 제공하지만, 이것만으로 primitive-first or generalized runtime closure를 claim하면 안 된다.

## Residual Review Focus

- `TKT-001` residual은 `common/name_only.py`의 mode/state machine과 `common/contracts.py`의 `selection_decision`, `scenario_candidates`, `staged_synthesis` handoff를 먼저 본다.
- `TKT-002`~`TKT-005` residual은 `common/contracts.py`의 `runtime_graph`, `executor_plan`, `env_contract`, `volume_contract`, `network_contract`가 actual executor input으로 충분한지부터 본다.

## Completion Review Focus

- `TKT-001` completion은 `selection_decision`, `scenario_candidates`, `ready_for_materialization`, `open_world_evidence_ready`가 summary helper가 아니라 authoritative branch input으로 충분한지부터 본다.
- `TKT-002`~`TKT-005` completion은 `runtime_graph`, `executor_plan`, `env_contract`, `volume_contract`, `network_contract`가 downstream fallback 없이도 canonical runtime input으로 읽히는지부터 본다.

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

- current completion priority order에서 common은 `TKT-001` 다음 `TKT-002`~`TKT-005` contract/control-plane closure를 읽는 핵심 companion이다.
- 따라서 common 문서는 expansion이나 support workflow보다 앞선 primitive/runtime contract closure가 왜 선행되어야 하는지 설명하는 code-level entry로 읽는다.
- latest positive representative pair의 ticket-form reading도 `visible blocker`보다 먼저 `structural root-cause`를 common contract/control-plane 쪽에서 읽게 만든다. canonical 해석은 [docs/work_tickets.md](../work_tickets.md)의 `Assessment-To-Ticket Interpretation`을 따른다.
- 잔여 작업량/turn envelope 해석도 [docs/work_tickets.md](../work_tickets.md)의 `Estimated Turn Envelope`를 같이 따른다.
- turn estimate shortcut도 [docs/work_tickets.md](../work_tickets.md)의 `Turn Estimate Entry`를 같이 따른다.
- LLM-response stricter reading에서도 positive LLM-shaped materialization claim은 결국 common contract/control-plane closure 위에서만 성립하므로, same priority order를 설명하는 핵심 companion으로 읽는다.
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

- `TKT-001`을 먼저 볼 때:
  - `common/name_only.py`
  - `common/contracts.py`
  - `common/prompts/templates.py`
- `TKT-002` ~ `TKT-005`를 먼저 볼 때:
  - `common/contracts.py`의 `runtime_recipe`, `runtime_graph`, `executor_plan`
  - `env_contract`, `volume_contract`, `network_contract`
- `TKT-006`을 먼저 볼 때:
  - `common/contracts.py`의 `staged_synthesis`, `design_brief`, `runtime_plan`, `oracle_contract`

## Representative Validation Surface

- policy / name-only / selection regression:
  - `tests/test_name_only_helpers.py`
  - `tests/test_requirement_policy_defaults.py`
  - `tests/test_role_canonicalization.py`
  - low-cost no-Docker capability-gate lanes:
    - `open-redirect-strict-dynamic-no-remote`
    - `open-redirect-strict-dynamic-stub`
  - unsupported negative abstain lane:
    - `foobar-name-only-negative`
- contract/runtime/oracle surface regression:
  - `tests/test_contract_resolution.py`
  - `tests/test_runtime_surface.py`
  - `tests/test_rule_based_semantic_contract.py`
- researcher/common handoff regression:
  - `tests/test_researcher_search_artifacts.py`
  - `tests/test_researcher_guard_normalization.py`

## How To Update This Document

- shared contract, prompt, policy utility의 구조나 responsibility가 바뀔 때만 갱신한다.
- current truth/coverage/evidence는 [docs/current_state_gap_analysis.md](../current_state_gap_analysis.md)에 남긴다.
- current limit과 forbidden claim은 [docs/constraints.md](../constraints.md)에 남긴다.
- priority와 owner decomposition은 [docs/final_solution.md](../final_solution.md), [docs/work_tickets.md](../work_tickets.md)로 보낸다.
- ticket-first entrypoint나 representative validation surface가 바뀌면 이 문서의 해당 섹션도 같이 갱신한다.
- completion review focus가 바뀌면 같은 owner/ticket mapping에 맞춰 이 문서도 같이 갱신한다.
- residual review focus가 바뀌면 같은 owner/ticket mapping에 맞춰 이 문서도 같이 갱신한다.
- priority review focus나 priority companion 해석이 바뀌면 [docs/code/README.md](README.md), [docs/work_tickets.md](../work_tickets.md)와 같이 갱신한다.
- LLM-response stricter reading의 common contract 해석이 바뀌면 [docs/work_tickets.md](../work_tickets.md)의 `LLM-Response Capability Overlay`와 같이 갱신한다.
- latest positive representative pair의 ticket-form 해석이 바뀌면 [docs/work_tickets.md](../work_tickets.md)의 `Assessment-To-Ticket Interpretation`와 같이 갱신한다.
- 잔여 작업량/turn envelope 해석이 바뀌면 [docs/work_tickets.md](../work_tickets.md)의 `Estimated Turn Envelope`와 같이 갱신한다.
- [docs/work_tickets.md](../work_tickets.md)의 `Turn Estimate Entry`가 바뀌면 same shortcut도 같이 갱신한다.
- review mode entry shortcut이 바뀌면 [docs/code/README.md](README.md)와 같이 갱신한다.
- contract-related representative rerun/harness entrypoint가 바뀌면 [tests/e2e/README.md](../../tests/e2e/README.md)와 같이 갱신한다.
