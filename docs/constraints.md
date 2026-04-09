# vulDocker 제약조건

Status: canonical
Audience: mixed
Source of truth for: current technical, operational, and evaluation constraints
Not the source of truth for: roadmap, rerun baseline tables, quickstart
Last validated against: code inspection, representative reruns, and workspace-local direct/support workflow verification on 2026-04-02

이 문서는 현재 시스템이 할 수 있는 것, 아직 못 하는 것, 그리고 무엇을 주장하면 안 되는지를 canonical하게 정리합니다. 미래 계획은 최소 링크로만 남기고, 여기에는 현재 사실만 기록합니다.

관련 문서:
- 문제 정의와 success criteria: [docs/problem.md](problem.md)
- 현재 rerun-backed truth: [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)
- 구현 우선순위: [docs/final_solution.md](final_solution.md)
- 작업 티켓 분해: [docs/work_tickets.md](work_tickets.md)
- 운영 절차: [docs/handbook.md](handbook.md)
- representative validation harness: [tests/e2e/README.md](../tests/e2e/README.md)

## Reader Routing

- 현재 시스템이 “무엇을 할 수 있는지 / 말하면 안 되는지”를 확인하려면 이 문서를 본다.
- 실제 rerun 결과나 current baseline은 [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)를 본다.
- phase 우선순위는 [docs/final_solution.md](final_solution.md), implementation-sized work item과 current completion priority order, 잔여 작업량/turn envelope는 [docs/work_tickets.md](work_tickets.md)를 본다.
- 실제 명령과 artifact location은 [docs/handbook.md](handbook.md)를 본다.
- case layout과 rerun/support harness command는 [tests/e2e/README.md](../tests/e2e/README.md)를 본다.

## Validation Companions

이 문서의 constraint를 실제 검증/운영 판단으로 연결할 때는 아래 문서를 같이 본다.

- observed truth와 실제 rerun evidence는 [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)
- success criteria 5축과 backlog owner 대응은 [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Axis Map`
- completion companion set은 [docs/work_tickets.md](work_tickets.md)의 `Completion Companions`
- priority companion set은 [docs/work_tickets.md](work_tickets.md)의 `Priority Companions`
- success criteria 5축의 완료판정 질문과 최소 근거는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Checklist`
- success criteria 5축의 canonical 완료 검토 순서는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Review Flow`
- success criteria 5축의 canonical 완료판정 reading order는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Reading Order`
- latest confirmed residual의 축별 ticket bundle 분해는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Residual Ticket Breakdown`
- latest direct verification까지 반영한 current completion priority order는 [docs/work_tickets.md](work_tickets.md)의 `Confirmed Completion Priority Order`
- 잔여 작업량과 practical turn envelope는 [docs/work_tickets.md](work_tickets.md)의 `Estimated Turn Envelope`
- latest confirmed residual의 canonical 구현 검토 순서는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Residual Review Flow`
- latest confirmed residual 검토 문서 순서는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Residual Reading Order`
- residual companion set은 [docs/work_tickets.md](work_tickets.md)의 `Residual Companions`
- review mode별 canonical 시작점은 [docs/work_tickets.md](work_tickets.md)의 `Review Mode Matrix`
- 우선순위 판단 routing은 [docs/work_tickets.md](work_tickets.md)의 `Priority Question Routing`, `Priority Reading Order`, `Assessment-To-Ticket Interpretation`
- phase acceptance와 검증 surface 대응은 [docs/final_solution.md](final_solution.md)의 `Acceptance-To-Validation Translation`
- ticket별 first harness와 reading order는 [docs/work_tickets.md](work_tickets.md)의 `Validation Routing` / `Validation Reading Order`
- 질문 기반 검증 문서 routing은 [docs/work_tickets.md](work_tickets.md)의 `Validation Question Routing`
- 질문 기반 residual 문서 routing은 [docs/work_tickets.md](work_tickets.md)의 `Residual Question Routing`
- concrete rerun/support harness command는 [tests/e2e/README.md](../tests/e2e/README.md)
- operator artifact reading과 troubleshooting은 [docs/handbook.md](handbook.md)

## Completion Companions

이 문서의 constraint를 완료판정 관점으로 연결할 때는 아래 문서를 같이 본다.

- completion companion set은 [docs/work_tickets.md](work_tickets.md)의 `Completion Companions`
- priority companion set은 [docs/work_tickets.md](work_tickets.md)의 `Priority Companions`
- axis map / close criteria / canonical review order는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Axis Map`, `Open-World Completion Checklist`, `Open-World Completion Review Flow`
- canonical completion reading order는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Reading Order`
- current completion priority order는 [docs/work_tickets.md](work_tickets.md)의 `Confirmed Completion Priority Order`
- phase acceptance map은 [docs/final_solution.md](final_solution.md)의 `Acceptance-To-Validation Translation`
- observed truth는 [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)
- concrete rerun / support harness command는 [tests/e2e/README.md](../tests/e2e/README.md)

## Priority Companions

이 문서의 constraint를 우선순위 판단 관점으로 연결할 때는 아래 문서를 같이 본다.

- current completion priority order는 [docs/work_tickets.md](work_tickets.md)의 `Confirmed Completion Priority Order`
- 잔여 작업량과 practical turn envelope는 [docs/work_tickets.md](work_tickets.md)의 `Estimated Turn Envelope`
- representative evidence와 함께 보는 turn estimate shortcut은 [docs/work_tickets.md](work_tickets.md)의 `Turn Estimate Entry`
- priority companion set / routing / reading order는 [docs/work_tickets.md](work_tickets.md)의 `Priority Companions`, `Priority Question Routing`, `Priority Reading Order`
- latest positive representative pair의 ticket-form reading은 [docs/work_tickets.md](work_tickets.md)의 `Assessment-To-Ticket Interpretation`
- LLM-response 기준 residual/priority 해석은 [docs/work_tickets.md](work_tickets.md)의 `LLM-Response Capability Overlay`
- phase ordering / sequencing guardrail은 [docs/final_solution.md](final_solution.md), [docs/work_tickets.md](work_tickets.md)의 `Sequencing Rule`
- observed truth는 [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)
- concrete rerun / support harness command는 [tests/e2e/README.md](../tests/e2e/README.md)

## Review Mode Entry

이 문서를 보고 있을 때도, 현재 목적은 아래 셋 중 하나로 다시 좁혀서 본다.

- 검증:
  - [docs/work_tickets.md](work_tickets.md)의 `Review Mode Matrix`
  - representative observed truth는 [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)
- 완료판정:
  - [docs/work_tickets.md](work_tickets.md)의 `Review Mode Matrix`
  - 이 문서의 `Completion Companions`
- 잔여 구현 검토:
  - [docs/work_tickets.md](work_tickets.md)의 `Review Mode Matrix`
  - [docs/work_tickets.md](work_tickets.md)의 `Residual Companions`
- 작업량 추산:
  - [docs/work_tickets.md](work_tickets.md)의 `Review Mode Matrix`
  - [docs/work_tickets.md](work_tickets.md)의 `Turn Estimate Entry`
- 우선순위 판단:
  - [docs/work_tickets.md](work_tickets.md)의 `Review Mode Matrix`
  - 이 문서의 `Priority Companions`
  - [docs/work_tickets.md](work_tickets.md)의 `Assessment-To-Ticket Interpretation`

## Priority Review Entry

제약/금지 claim 관점에서 우선순위 판단을 시작할 때는 아래 순서를 권장한다.

1. 이 문서의 `Priority Companions`
2. [docs/work_tickets.md](work_tickets.md)의 `Confirmed Completion Priority Order`, `Estimated Turn Envelope`
3. [docs/work_tickets.md](work_tickets.md)의 `LLM-Response Capability Overlay`, `Assessment-To-Ticket Interpretation`
4. current forbidden claim과 operational prerequisite를 이 문서에서 먼저 확인
5. [docs/current_state_gap_analysis.md](current_state_gap_analysis.md), [docs/final_solution.md](final_solution.md)

turn estimate shortcut은 [docs/work_tickets.md](work_tickets.md)의 `Turn Estimate Entry`를 따른다.

## 1. Name-Only Mode Constraints

Constraint: `compatibility`, `dynamic`, `strict_dynamic`는 서로 다른 closure contract를 가집니다.

- Current enforcement surface: `common/name_only.py`, `orchestrator/pack.py`
- Allowed claim: compatibility mode의 lower-bound closure는 regression success로 설명할 수 있습니다.
- Forbidden claim: dynamic/strict_dynamic의 degraded fallback을 generalized open-world success처럼 설명하면 안 됩니다.
- Planned removal path: roadmap의 decision policy unification과 oracle execution parity 이후 재평가

Constraint: `intent_met`, `partial`, `abstain`, `fail_closed`는 pipeline success와 분리해서 읽어야 합니다.

- Current enforcement surface: `name_only_outcome`, `support_promotion`, `open_world_readiness`
- Allowed claim: `pipeline_result=success`이면서 `name_only_outcome=partial`일 수 있습니다.
- Observable today: representative bounded compiler/native lane은 `name_only_outcome=intent_met`와 `artifact_quality.band=high`를 달성해도 `open_world_ready=false`, `support_promotion=false`로 남을 수 있습니다.
- Forbidden claim: fully validated bundle을 곧바로 intent-faithful open-world success로 읽으면 안 됩니다.

Constraint: selection은 아직 joint scenario candidate 정책이 아닙니다.

- Current enforcement surface: `request_ir.family_candidates`, `request_ir.stack_candidates`, `selection_decision`
- Observable today: family와 stack selection은 enrich되어도 `family x stack x topology x oracle`를 함께 고르는 단일 candidate plane은 아닙니다.
- Allowed claim: enriched candidate surfaces and evidence-backed top-choice selection
- Forbidden claim: joint scenario planning이 이미 구현돼 있다고 설명하는 것

## 2. Family / Stack / Topology Boundedness

Constraint: family hypothesis space는 closed-vocabulary입니다.

- Current enforcement surface: catalog resolution, `_FAMILY_HINTS`, semantic-guided family builders
- Observable today: family 후보와 semantic-guided fallback coverage가 bounded family set 안에 머뭅니다.
- Allowed claim: unknown but family-inducible phrase에 대한 bounded dynamic handling
- Forbidden claim: arbitrary unknown family induction

Constraint: stack selection은 bounded stack pool에 묶여 있습니다.

- Current enforcement surface: researcher stack markers, runtime recipe stack profile
- Observable today: representative dynamic lane는 `python/flask`와 `python/fastapi` 중심입니다.
- Allowed claim: limited repo-supported stack selection
- Forbidden claim: multi-runtime, non-Python, generalized stack inference

Constraint: topology synthesis는 아직 policy-coupled입니다.

- Current enforcement surface: `policy.executor.sidecars`, executor network/sidecar policy
- Observable today: `service_plus_sidecar`는 generator invention보다 policy-provided infra에 가깝습니다.
- Allowed claim: single-service and policy-declared sidecar execution
- Forbidden claim: generalized multi-service runtime design

Constraint: topology candidate generation 자체가 아직 약합니다.

- Current enforcement surface: runtime recipe, executor policy, bounded sidecar handling
- Observable today: topology는 selected scenario의 결과라기보다 policy와 runtime feasibility에 의해 닫히는 경우가 많습니다.
- Allowed claim: bounded topology handling
- Forbidden claim: evidence-led topology synthesis

Constraint: primitive-guided runtime dependency inference는 아직 narrow하고 family-bounded입니다.

- Current enforcement surface: `primitive_hypotheses`, `provisional_family`, primitive-derived runtime dependency hints in `common/contracts.py`
- Observable today: strong primitive match에서 `sql_injection`류는 low-confidence `db:sqlite` hint를 얻고, staged runtime plan도 이 hint를 읽기 시작했습니다. selected known family에는 low-confidence `oracle_hypotheses`도 추가돼 `scenario_candidates`와 `staged_synthesis.oracle_contract`까지 내려가지만, 이 역시 bounded fallback-style planning hint일 뿐 generalized dependency/oracle synthesis는 아닙니다.
- Allowed claim: bounded primitive-guided dependency/oracle hinting for selected known families
- Forbidden claim: generalized primitive-first dependency planning

## 3. Research / Evidence Authority Constraints

Constraint: evidence authority는 아직 lexical heuristic이 강합니다.

- Current enforcement surface: query plan, family ranking, evidence graph, source authority weighting
- Observable today: alias/anchor/marker match와 simple authority buckets가 큰 비중을 가집니다.
- Allowed claim: evidence-informed ranking
- Forbidden claim: causal or sufficient evidence reasoning

Constraint: open-vocabulary induction layer는 아직 partial primitive-guided 단계입니다.

- Current enforcement surface: catalog resolution, fixed hints, synthetic name handling, `primitive_hypotheses -> primitive_signature family candidate`
- Observable today: semantic signature가 강하게 알려진 known family primitive와 맞을 때는 `provisional_family`와 primitive-led family candidate를 만들 수 있지만, 이것은 bounded known-family induction일 뿐 arbitrary unknown family discovery는 아닙니다.
- Allowed claim: bounded primitive-guided provisional family induction for known families
- Forbidden claim: open-vocabulary family discovery

Constraint: selection evidence와 materialization readiness는 분리되어야 합니다.

- Current enforcement surface: `ready_for_materialization`, `open_world_evidence_ready`
- Observable today: selected family/stack가 있어도 support-ready bundle은 아닐 수 있습니다.
- Allowed claim: selection-ready but not support-ready
- Forbidden claim: selected candidate equals generalized support

## 4. Generator / Synthesis Constraints

Constraint: current synthesis는 여전히 one-shot manifest 의존이 큽니다.

- Current enforcement surface: synthesis candidate loop and deterministic fallback
- Observable today: manifest parse/guard failure 시 fallback으로 빠지기 쉽습니다.
- Allowed claim: runnable degraded dynamic artifact
- Forbidden claim: robust staged open-world synthesis

Constraint: primitive-level reasoning이 아직 primary controller가 아닙니다.

- Current enforcement surface: semantic signature, scenario/oracle selection summaries, family-aware fallback builders, manifest synthesis
- Observable today: primitive signal은 존재하고 scenario-level oracle selection truth와 `design_brief.required_roles`도 일부 surface되며 recovery dispatch, thin runtime-plan fallback target 복구, fresh candidate guard, bounded `dependency_db -> sqli` fallback selection, fallback manifest의 `target_topology/target_db/target_sidecars/design_brief_oracle_mode` metadata 보존, bounded SQLi minimal dynamic fallback의 external DB variant(`mysql/postgres`) materialization과 `schema.sql` seed surface 제공, same schema source를 service init path가 읽는 정렬, compiler-generated MySQL sidecar lane의 `schema.sql`/`seed_files` surface 추가, 그리고 일부 mysql/postgres lane에서 `generator_manifest.metadata.target_*`로부터 bounded sidecar plan이 contract 단계에서 합성되는 정도까지는 들어왔지만, 최종 materialization은 대부분 bounded family builder와 repo-supported runtime prior에 의존합니다.
- Observable today: primitive signal은 존재하고 scenario-level oracle selection truth와 `design_brief.required_roles`도 일부 surface되며 recovery dispatch, thin runtime-plan fallback target 복구, fresh candidate guard, bounded `dependency_db -> sqli` fallback selection, semantic signature가 비어 있어도 strong/non-ambiguous researcher `top_family`를 bounded minimal_dynamic fallback salvage에 쓰는 경로, fallback manifest의 `target_topology/target_db/target_sidecars/design_brief_oracle_mode` metadata 보존, bounded SQLi minimal dynamic fallback의 external DB variant(`mysql/postgres`) materialization과 `schema.sql` seed surface 제공, same schema source를 service init path가 읽는 정렬, compiler-generated MySQL sidecar lane의 `schema.sql`/`seed_files` surface 추가, 그리고 일부 mysql/postgres lane에서 `generator_manifest.metadata.target_*`로부터 bounded sidecar plan이 contract 단계에서 합성되는 정도까지는 들어왔지만, 최종 materialization은 대부분 bounded family builder와 repo-supported runtime prior에 의존합니다.
- Allowed claim: primitive-informed bounded generation
- Forbidden claim: primitive-first runtime design synthesis

Constraint: deterministic fallback은 runnable quality를 보존하기 위한 degraded path입니다.

- Current enforcement surface: `generation_origin=deterministic_fallback`, `fallback_class=*`
- Allowed claim: bounded runnable recovery
- Forbidden claim: template-independent generalized generation

## 5. Executor / Runtime Constraints

Constraint: `executor_plan`은 아직 완전한 authoritative runtime control-plane이 아닙니다.

- Current enforcement surface: executor의 bundle-scoped execution surface와 port/health/env/sidecar/db re-resolution
- Observable today: executor는 `base_url`, `service_env`, `requires_external_db`, `sidecars`, `healthchecks`, sidecar `ready_probe`를 더 직접 읽고, `executor_plan`/`runtime_recipe`의 `db`, `db_source`, `topology_source`, `runtime_dependency_hypotheses`, `seed_files`, `seed_strategy`, `env_contract`, `volume_contract`, `network_contract`와 `generator_manifest.metadata.target_db/target_sidecars/target_topology` fallback hint도 execution surface와 early validation에 일부 반영하기 시작했습니다. `mysql/mariadb/postgres/postgresql` target에 대해서는 bounded default sidecar plan synthesis와 bounded `service_env` default synthesis가 가능하고, latest slice로 일부 mysql/postgres lane에서는 contract 단계가 이미 bounded sidecar plan, bounded `service_env` defaults, bounded `network_enabled/network_mode`, bounded `sidecar_start_order`, bounded `seed_strategy`, bounded `volume_contract`, bounded `network_contract`를 `runtime_recipe/executor_plan`까지 합성하며 그 provenance(`sidecars_source`, `service_env_source`, `network_*_source`, `sidecar_start_order_source`, `seed_strategy_source`, `volume_contract_source`, `network_contract_source`)도 executor execution surface와 bundle summary까지 유지합니다. latest slice에서는 same `service_env_source`가 `executor_plan.service_env+network_contract_aliases+runtime_hint_sidecar_defaults`처럼 합성 provenance도 유지하기 시작했습니다. `runtime_graph`도 same bounded order를 `startup_order_index/startup_after` 수준으로 설명하기 시작했고, latest slice에서는 explicit sidecar plan/order가 비어 있을 때 `runtime_graph.nodes`의 sidecar node와 `startup_order_index`를 bounded fallback source로 읽기 시작했습니다. same bounded lane에서는 `startup_order_index`가 없어도 `runtime_graph.edges[*].startup_after`를 sidecar order fallback source로 읽기 시작했고, latest slice에서는 same graph-derived order가 malformed reference, unknown sidecar dependency, cyclic dependency를 executor run 전에 early failure로 막기 시작했습니다. `runtime_graph.nodes`는 sidecar `env`/`ready_probe` reconstruction에도 일부 연결되며, latest slice에서는 `runtime_graph.env_contract`가 service env fallback source를 넘어서 sidecar env backfill source로도 읽히기 시작했습니다. latest slice에서는 same `runtime_graph.network.enabled/mode`도 executor의 `allow_network/network_mode` fallback source로, `runtime_graph.exploit_path`와 service node는 `service_port`/`service_entry`/`base_url` fallback source로, same `runtime_graph.exploit_path.entrypoint`는 `poc_entry` fallback source로, `resolved_contract.poc_cmd`는 main PoC execution/oracle replay command fallback source로, declared `healthchecks.port`는 `service_port` fallback source로도 읽히기 시작했습니다. latest slice에서는 same readiness `healthchecks` 자체도 `runtime_recipe.healthchecks`를 fallback으로 읽기 시작해, `service_port` derivation과 actual readiness probe candidate가 더 덜 어긋납니다. latest slice에서는 same `health_path_source`도 executor/runtime-recipe healthchecks declaration을 더 직접 반영하기 시작했고, `healthchecks_source`도 execution surface와 summary까지 노출되기 시작했습니다. latest slice에서는 same service `healthchecks`도 bounded self-consistency validation에 일부 연결돼, unsupported transport, HTTP(S) probe without path, TCP probe with path, non-service node declaration, conflicting explicit healthcheck ports, resolved `service_port`와의 명백한 port drift, 사실상 하나로 정해진 HTTP(S) healthcheck path와 resolved `health_path` 간 obvious mismatch를 executor가 run 전에 early failure로 막기 시작했습니다. latest slice에서는 same `service_env`의 `APP_PORT`/`PORT`가 resolved `service_port`와 명백히 어긋나도 executor가 run 전에 early failure로 막기 시작했고, same bounded external-DB lane에서는 `DB_PORT`, `DB_HOST`, `DB_NAME/DB_USER/DB_PASSWORD`도 service env와 actual sidecar/runtime truth가 둘 다 선언돼 있는데 명백히 어긋나면 early failure로 막기 시작했습니다. latest slice에서는 same bounded sidecar lane의 `ready_probe.type`도 actual mysql/postgres runtime kind와 명백히 어긋나면 executor가 run 전에 early failure로 막기 시작했고, same lane의 sidecar `name`/`aliases`가 서로 충돌해 runtime identity가 ambiguous한 경우도 early failure로 막기 시작했습니다. latest slice에서는 same workspace path contract도 더 조여져, `service_entry`, `poc_entry`, declared `seed_files`에 absolute path나 `..` traversal이 있으면 executor가 run 전에 early failure로 막기 시작했습니다. latest slice에서는 same `poc_cmd`도 placeholder 또는 inline command는 계속 허용하되, declared local script reference가 resolved `poc_entry`와 명백히 어긋나면 executor가 run 전에 early failure로 막기 시작했습니다. latest slice에서는 same local `base_url`도 `service_port`와 어긋나면 executor run 전에 early failure로 막기 시작했습니다. same bounded sidecar lane에서는 `network_contract`가 alias validation/materialization을 넘어, service env가 일부 비어 있을 때 `service` scope `{name, alias}`를 minimal binding source로도 쓰이기 시작했습니다. same service-level provenance(`service_port_source`, `service_entry_source`, `base_url_source`, `health_path_source`)는 executor summary와 aggregate surface까지도 노출되기 시작했고, latest slice에서는 same bundle/top-level summary가 `poc_entry`/`poc_entry_source`, `poc_cmd`/`poc_cmd_source`도 직접 노출하기 시작했습니다. same bounded lane에서는 `env_contract`도 service scope뿐 아니라 `sidecar:<name>` scope env를 일부 싣고 executor가 sidecar env drift까지 early validation으로 막기 시작했으며, 같은 `scope+name`에 서로 다른 expected value를 중복 선언해 contract 자체가 모호한 경우도 early failure로 막기 시작했습니다. same bounded seed lane에서는 `volume_contract`도 `/seed-input:ro` mount intent를 좁게 설명하고 executor가 declared seed-input mount 누락이나 malformed mount contract를 early validation으로 막기 시작했습니다. latest slice에서는 same `volume_contract`가 custom absolute workspace target도 허용해, actual sidecar mount와 seed-apply path가 declared target을 따르기 시작했고, 한 sidecar에 multiple workspace read-only seed mount target이 선언돼 actual apply target이 모호해지는 경우도 early failure로 막기 시작했습니다. same bounded sidecar lane에서는 `network_contract`도 service `DB_HOST`와 sidecar alias 정렬을 좁게 설명하고 executor가 alias drift, missing sidecar target, network-disabled 모순을 early validation으로 막기 시작했습니다. latest slice에서는 same `network_contract`가 actual alias materialization에도 일부 연결돼, sidecar entry alias가 비어 있어도 declared contract가 있으면 execution surface와 `docker run --network-alias`까지 이를 보강합니다. representative direct rerun 기준으로 compiler-generated MySQL sidecar lane도 이제 `schema.sql`, `seed_files=['schema.sql']`, `seed_strategy=sidecar_sql_apply`, actual seed apply completion까지 들어오기 시작했습니다. external mysql/postgres sidecar가 있을 때 listed `.sql` seed file은 readiness 이후 bounded actual apply까지 들어오기 시작했고, sqlite lane에서는 `sqlite_service_init` 전략과 minimal init signal 검증이 묶이기 시작했습니다. same `seed_strategy`도 이제 explicit contract validation에 일부 연결돼, `sqlite_service_init`의 non-sqlite/sidecar 모순과 `sidecar_sql_apply`의 external-db 또는 `.sql` seed file 부재를 run 전에 early failure로 막습니다. 다만 이는 여전히 narrow fallback이며 generalized dependency ordering, generalized seed/init execution, richer env-volume contract semantics, generalized sidecar/runtime/topology synthesis, 일부 network lifecycle은 아직 policy/runtime fallback에 남아 있습니다.
- Observable today: same bounded sidecar lane에서는 `network_contract`가 같은 service env key에 서로 다른 alias를 중복 선언해 contract 자체가 모호한 경우도 executor가 run 전에 early failure로 막기 시작했습니다.
- Observable today: same bounded sidecar lane에서는 `network_contract`가 service scope alias를 선언했는데 sidecar alias catalog 자체가 없어 target을 전혀 해석할 수 없는 경우도 executor가 run 전에 early failure로 막기 시작했습니다.
- Observable today: same bounded sidecar lane에서는 `network_contract`가 `service`와 `sidecar:*` 외 unsupported scope를 포함하면 executor가 run 전에 early failure로 막기 시작했습니다.
- Observable today: same bounded volume-contract lane에서는 `sidecar:*` 외 unsupported scope가 들어오면 executor가 run 전에 early failure로 막기 시작했습니다.
- Observable today: same bounded volume-contract lane에서는 `workspace/runtime` 외 unsupported `source` 값이 들어오면 executor가 run 전에 early failure로 막기 시작했습니다.
- Observable today: same bounded seed lane에서는 `volume_contract`가 같은 `scope+target`에 서로 다른 `source/mode`를 중복 선언해 mount definition 자체가 충돌하는 경우도 executor가 run 전에 early failure로 막기 시작했습니다.
- Observable today: same bounded seed lane에서는 `sidecar_sql_apply`가 SQL-capable sidecar target 없이 선언되거나 multiple SQL family가 동시에 걸려 actual apply target이 모호한 경우도 executor가 run 전에 early failure로 막기 시작했습니다.
- Observable today: same bounded seed lane에서는 `sidecar_sql_apply`가 DB family hint만 있고 actual SQL-capable sidecar entry가 없으면 executor가 run 전에 early failure로 막기 시작했습니다.
- Observable today: same bounded env-contract lane에서는 `service`와 `sidecar:*` 외 unsupported scope가 들어오면 executor가 run 전에 early failure로 막기 시작했습니다.
- Allowed claim: expanded executor plan surface for sidecars, readiness, and partial runtime provenance passthrough with seed/env validation
- Forbidden claim: full runtime/executor parity

Constraint: runtime security defaults는 의도적으로 restrictive합니다.

- Current enforcement surface: read-only rootfs, tmpfs `/tmp`, `--network none`, `cap-drop`
- Allowed claim: isolated local execution
- Forbidden claim: arbitrary external dependency runtime support without explicit policy

## 6. Verifier / Oracle / Trust Constraints

Constraint: verifier independence는 lane에 따라 다르고, low-trust fallback이 남아 있습니다.

- Current enforcement surface: static rule, runtime rule, contract-oracle fallback, verifier policy
- Allowed claim: declared-rule 기반 high-trust verification
- Forbidden claim: contract-coupled fallback verification을 동일 trust로 취급

Constraint: oracle richness와 oracle execution parity는 아직 다릅니다.

- Current enforcement surface: `exploit_oracle`, `artifact_quality`, verifier runtime assertions
- Observable today: payload-driven `negative_controls`와 `metamorphic.cases`는 executor replay와 verifier surface까지 이어지기 시작했지만, metadata-only oracle과 broader multi-step/browser stateful oracle은 여전히 full execution parity 밖에 남아 있습니다. representative direct run 기준으로 compiler/native sidecar lane과 several stateless/body-structured/sessionful minimal_dynamic fallback lanes(`open_redirect`, `template_injection`, `path_traversal`, `ssrf`, `deserialization`, `xxe`, `csrf`)는 latest slice 후 `oracle_execution_parity=high`까지 올라갈 수 있지만, 이건 bounded compiler/fallback lane 개선일 뿐 전체 lane에 일반화된 closure는 아닙니다. 따라서 현재 high-trust verification success와 executed oracle closure는 여전히 lane별로 분리해서 읽어야 합니다.
- Allowed claim: payload-driven oracle execution parity is partially implemented
- Forbidden claim: all oracle realism fields are executed verifier checks

Constraint: high oracle parity가 곧 high artifact quality를 뜻하지는 않습니다.

- Current enforcement surface: `artifact_quality.band`, `artifact_quality.oracle_rigor`, `artifact_quality.qualitative_tier`, `artifact_quality_summary.by_qualitative_tier`, representative direct runs
- Observable today: representative deterministic fallback lane은 `oracle_execution_parity=high`와 `oracle_rigor=high`를 달성해도 여전히 `artifact_quality.band=medium`, `artifact_quality.qualitative_tier=thin_fallback_demo`, `name_only_outcome=partial`, `open_world_ready=false`로 남습니다. 반대로 representative compiler/native sidecar lane은 same bounded scope 안에서 `artifact_quality.band=high`, `artifact_quality.qualitative_tier=bounded_sidecar_parity_success`까지 올라갑니다.
- Observable today: representative compiler/native sidecar lane은 latest direct rerun 기준 custom DB env(`DB_USER/DB_PASSWORD/DB_NAME`)를 유지한 채 same `bounded_sidecar_parity_success` tier와 `oracle_execution_parity=high`를 계속 만족합니다. 즉 최근 bounded self-consistency hardening이 same lane의 custom runtime binding을 깨뜨리지는 않았습니다.
- Observable today: representative strict no-remote fail-closed lane은 `artifact_quality.qualitative_tier=planning_only`로 남고, 이것은 quality 부족이라기보다 generated operator artifact가 없다는 뜻입니다.
- Allowed claim: executed oracle closure and qualitative artifact quality are related but distinct
- Forbidden claim: `oracle_execution_parity=high` alone proves artifact quality is high

## 7. Promotion / Readiness Claim Constraints

Constraint: `promotion_eligible`와 `support_promotion`은 다른 의미입니다.

- Current enforcement surface: pack summary surfaces
- Allowed claim: pack/regression promotion 가능
- Forbidden claim: promotion 가능 = generalized support readiness

Constraint: `support_promotion`은 여전히 PACK의 honesty surface이며, extraction/review/update preview는 measured repeatability lane에 한정됩니다.

- Current enforcement surface: pack summary/reasons, `orchestrator/support_extract.py`, `tests/e2e/repeat_case.py`, `tests/e2e/support_review.py`, `tests/e2e/support_decide.py`
- Observable today: repeatability-aware E2E output은 `support_candidate.json`, `support_review_index.json`, `support_registry_update.json` preview를 만들 수 있고, latest slice에서는 same preview를 `curated_support_registry.json` local write/merge workflow로 적용할 수도 있습니다. same local registry는 `update_history`, `by_decision`, `by_reviewer`, `by_review_status`, `items_with_source_artifacts_count`를 보존하고 obvious merge conflict를 reject하며, existing item에 대한 reject decision도 item-level history로 반영하기 시작했지만, 그래도 이것은 matrix/repeatability-measured case에 대한 수동 review/update surface일 뿐 자동 curated promotion loop는 아닙니다.
- Observable today: latest slice에서는 same local registry가 previously rejected item이 later accept될 때도 `rejected_count`와 prior history를 preserve하기 시작했지만, 그래도 이것은 local/manual workflow hardening이지 operational curated promotion loop completion은 아닙니다.
- Observable today: latest slice에서는 same sparse accepted/rejected update도 prior `source_artifacts`는 유지하면서 current support-status split은 reviewable semantics로 채우기 시작했지만, 그래도 이것은 local/manual workflow hardening이지 operational curated promotion loop completion은 아닙니다.
- Observable today: latest slice에서는 same sparse older local registry item도 `history`와 last event를 읽어 current lifecycle/status/provenance schema로 normalize되고, `schema_upgraded_item_count`, `by_schema_upgrade_reason`, item-level `schema_upgrade_reasons`로 same bounded schema evolution이 surface에 드러나기 시작했습니다. 그래도 이것 역시 local/manual workflow hardening이지 operational curated promotion loop completion은 아닙니다.
- Observable today: latest slice에서는 same sparse older `update_history` entry도 current update schema로 normalize되고, `schema_upgraded_update_count`와 `by_update_schema_upgrade_reason`로 same lifecycle upgrade가 surface에 드러나기 시작했습니다. 그래도 이것 역시 local/manual workflow hardening이지 operational curated promotion loop completion은 아닙니다.
- Observable today: latest slice에서는 same sparse older `decision_history` event도 current decision schema로 normalize되고, `schema_upgraded_decision_event_count`와 `by_decision_schema_upgrade_reason`로 same lifecycle upgrade가 surface에 드러나기 시작했습니다. 그래도 이것 역시 local/manual workflow hardening이지 operational curated promotion loop completion은 아닙니다.
- Observable today: latest slice에서는 same local registry maintenance 상태도 top-level `schema_status` token으로 `normalized` vs `legacy_*_present` 상태를 바로 읽을 수 있게 됐지만, 그래도 이것 역시 local/manual workflow hardening이지 operational curated promotion loop completion은 아닙니다.
- Observable today: latest slice에서는 same item/update/decision record도 `schema_status=normalized|legacy_upgraded`를 직접 가지기 시작했지만, 그래도 이것 역시 local/manual workflow hardening이지 operational curated promotion loop completion은 아닙니다.
- Observable today: latest direct verification 기준 representative `sqli-sidecar-compiler-custom-env` lane은 app/runtime/oracle quality는 높아도 support workflow에서는 still `strict_open_world:strict_curated_lower_bound`, `open_world:catalog_resolved_lower_bound`, `oracle_clarity:medium`, `family_evidence:candidate_unbacked`, `measured_gate:cache_reuse_inconsistent` 때문에 reviewable candidate가 되지 않습니다. same empty-decision local apply chain은 `curated_support_registry.json`을 false promotion 없이 `registry_item_count=0` no-op 상태로 끝냅니다.
- Observable today: same representative sidecar support rerun은 `support_review_index.json`에서 `by_support_status={"blocked_mixed":1}`와 separated `by_mechanical_blocker` / `by_promotion_policy_blocker`를 남기며, same no-op apply chain은 `accepted/rejected/pending_by_support_status={}`와 empty local registry `by_support_status={}`로 끝납니다.
- Observable today: latest planning-only pair direct verification(`foobar-name-only-negative`, `open-redirect-strict-dynamic-no-remote`)에서는 `support_review_index.json`가 `authority_ready_bundle_count=2`, `measured_gate_blocked_bundle_count=2`, `reviewable_bundle_count=0`, `by_support_status={"blocked_mixed":2}`를 남겼습니다. 즉 verdict-authority readiness alone still does not imply reviewable/promotable candidate입니다.
- Observable today: latest fresh positive pair direct verification(`trusted-dynamic-sqli`, `open-redirect-dynamic-name-only`)에서도 combined `support_review_index.json`가 `support_candidate_file_count=2`, `authority_ready_bundle_count=2`, `measured_gate_blocked_bundle_count=2`, `reviewable_bundle_count=0`, `by_support_status={"blocked_mixed":2}`를 남겼습니다. `2026-03-20` rerun에서도 same aggregate가 그대로 재확인됐습니다. 즉 actual Docker materialization이 열려도 current measured/support policy 기준으로는 still “runnable but not promotable”일 수 있습니다.
- Observable today: latest helper semantics에서는 same positive blocked lane를 helper wrapper로 재현할 때도 `ops/ci/run_support_workflow_chain.sh`와 `ops/ci/run_positive_pair_promotion_check.sh`가 `repeatability_report.json`이 남은 `repeat_case.py` nonzero를 허용하고 support review까지 계속 진행합니다. same `run_repeatability_chain.sh`에는 transient docker readiness retry seam(`VULD_REPEAT_CHAIN_DOCKER_RETRY_COUNT`, `VULD_REPEAT_CHAIN_DOCKER_RETRY_DELAY_SEC`)이 있고, `docker daemon permission denied`는 retry 대상이 아니라 separate permission artifact marker/note로 surface됩니다. unrestricted Docker-enabled helper rerun에서는 helper wrapper도 다시 `authority_ready_bundle_count=2`, `measured_gate_blocked_bundle_count=2`, `reviewable_bundle_count=0`, `by_support_status={"blocked_mixed":2}` current truth와 정렬됩니다. 따라서 helper contract green만으로 generalized support closure를 주장하면 안 되지만, runtime-equivalent helper truth는 unrestricted helper rerun 또는 manual repeatability/support chain으로 재현할 수 있습니다.
- Observable today: same bounded environment distinction은 sandbox helper output 자체에도 남습니다. current workspace-local direct verification에서는 `run_positive_pair_promotion_check.sh`가 permission-artifact note를 남기면서 `support_candidate_file_count=2`, `authority_ready_bundle_count=0`, `measured_gate_blocked_bundle_count=0`, `reviewable_bundle_count=0`, `by_support_status={}` empty aggregate로 끝날 수도 다시 확인됐습니다. same output은 runtime-equivalent measured/support truth가 아니라 permission-artifact environment output으로 읽어야 합니다.
- Observable today: same latest direct reverify는 `docker ps` / `docker ps -a`가 empty container list로 정상 응답한 세션에서 실행됐고, strict stub / `trusted-dynamic-sqli` / `open-redirect-dynamic-name-only` direct rerun도 다시 모두 성공했습니다. 따라서 same helper split은 host Docker availability 부재가 아니라 helper output이 permission-artifact environment output으로 갈라지는 bounded distinction으로 읽는 편이 맞습니다.
- Observable today: same `2026-03-20` latest liveaudit rerun에서도 direct `run_case.py` 3종과 manual `repeat_case.py -> support_review.py` chain은 다시 성공했지만, sandbox helper wrapper는 다시 permission-artifact note와 empty aggregate / `case_failed` repeatability output으로 갈라졌습니다. 따라서 current authoritative measured/support truth는 계속 manual chain 또는 unrestricted helper rerun 기준으로 읽어야 합니다.
- Observable today: same workspace-local helper rerun에서는 per-case `repeatability_report.json`도 `passed=false`와 blocker `case_failed`를 포함할 수 있었습니다. same failure는 current core measured/support truth 변화가 아니라 permission-artifact environment output 쪽 drift입니다.
- Observable today: same `2026-03-20` latest audit2 rerun에서도 `docker ps` / `docker ps -a`는 정상이고 `docker images`에 fresh `sid-*` image가 남았는데, sandbox helper wrapper는 again empty aggregate와 permission summary split으로 갈라졌습니다. therefore same split도 host Docker precondition 부재가 아니라 permission-artifact environment output distinction으로 읽는 편이 맞습니다.
- Observable today: same latest audit2 rerun에서 helper per-case `repeatability_report.json`는 둘 다 `passed=false`였고 blocker에 `case_failed`, `quality_tier_inconsistent`, `verdict_authority_inconsistent`가 같이 남았습니다. manual chain이 같은 세션에서 다시 `by_support_status={"blocked_mixed":2}`를 재현한 점을 같이 보면, same helper blockers도 current core truth 변화가 아니라 bounded helper projection drift입니다.
- Observable today: same helper output root의 `permission_artifact_summary.json`는 `runtime_equivalent_helper_truth_available=false`, `recommended_action=unrestricted_docker_rerun`를 남깁니다. therefore current workspace-local helper output은 machine-readable summary 기준으로도 runtime-equivalent helper truth가 아닙니다.
- Observable today: same `2026-03-21` direct rerun에서도 `docker ps` / `docker ps -a`는 again empty list로 정상이고 `docker images`에는 fresh `sid-*` image가 남았습니다. same session에서 strict stub / `trusted-dynamic-sqli` / `open-redirect-dynamic-name-only` direct rerun은 again 모두 성공했고, manual positive pair support review도 again `authority_ready_bundle_count=2`, `measured_gate_blocked_bundle_count=2`, `reviewable_bundle_count=0`, `by_support_status={"blocked_mixed":2}`를 남겼습니다.
- Observable today: same `2026-03-21` latest audit3 rerun에서는 summary-level classification도 다시 동일했습니다. strict stub은 `name_only_decision=fail_closed`, `stage_ceiling=pre_generation`, `generation_summary.by_dynamicness_verdict={pre-generation fail-closed:1}`였고, `trusted-dynamic-sqli`는 `provider_health_state=llm_fixture`, `generation_origin=llm_manifest`, `generation_summary.by_dynamicness_verdict={trusted dynamic:1}`였으며, `open-redirect-dynamic-name-only`는 `provider_health_state=llm_degraded`, `generation_origin=deterministic_fallback`, `name_only_decision=partial`, `generation_summary.by_dynamicness_verdict={deterministic fallback dependent:1}`였습니다.
- Observable today: same `2026-03-21` sandbox helper rerun은 again empty aggregate와 permission summary split으로 갈라졌고, helper per-case `repeatability_report.json`는 둘 다 `passed=false`였으며 blocker에 `case_failed`, `cache_reuse_inconsistent`, `artifact_quality_band_not_high`, `quality_tier_inconsistent`, `oracle_execution_parity_not_high`, `verdict_authority_inconsistent`가 같이 남았습니다. therefore latest rerun도 host Docker availability 부재가 아니라 permission-artifact environment output distinction을 재확인한 bounded helper projection drift입니다.
- Current command entry: same positive pair rerun/support chain은 [tests/e2e/README.md](../tests/e2e/README.md)의 `Positive Pair Promotion Check`를 entrypoint로 사용하되, sandbox helper output에 permission-artifact note가 보이면 unrestricted helper rerun 또는 같은 섹션의 underlying manual chain을 우선합니다.
- Observable today: latest slice에서는 same `support_review.py -> support_decide.py -> support_apply.py` chain의 synthetic reviewable accept path와 blocked no-op path가 regression으로 고정됐지만, 이것이 곧 representative actual measured lane accept path가 닫혔다는 뜻은 아닙니다.
- Observable today: latest slice에서는 same support workflow가 blocker를 `mechanical` vs `promotion_policy` class로 나눠 surface하고, candidate `mechanically_healthy` / `promotion_policy_ready`, review/update aggregate `mechanically_*` / `promotion_policy_*` count, `by_mechanical_blocker` / `by_promotion_policy_blocker`도 같이 노출하기 시작했습니다. 그래도 이것은 blocker interpretation surface 강화이지 auto-promotion policy completion은 아닙니다.
- Observable today: latest slice에서는 same support workflow가 `support_status` / `by_support_status`도 같이 노출하기 시작해, current promotion state를 token으로 더 직접 읽을 수 있습니다. 그래도 이것 역시 interpretation surface 강화이지 auto-promotion policy completion은 아닙니다.
- Observable today: legacy/default normalization 경로에서는 `support_status=blocked_unclassified`가 남을 수 있습니다. 이것은 current blocker class를 충분히 복원하지 못한 blocked state라는 뜻이지, reviewable candidate를 뜻하지는 않습니다.
- Observable today: latest slice에서는 same support workflow가 `by_case_status`, `case_statuses[]`, `all_reviewable_cases`, `mixed_cases`, `all_blocked_cases`를 review/update preview에 같이 보존하고, local registry current state도 `by_case_review_status`, `all_accepted_cases`, `mixed_review_status_cases`, `all_rejected_cases`, `last_update`를 함께 보존하기 시작했습니다. 그래도 이것 역시 local/manual workflow observability 강화이지 operational curated promotion loop completion은 아닙니다.
- Observable today: latest slice에서는 same `curated_support_registry.json` local registry도 item-level `support_status`, `mechanically_healthy`, `promotion_policy_ready`와 top-level `by_support_status`, `mechanically_*_item_count`, `promotion_policy_*_item_count`를 보존하기 시작했습니다. 그래도 이것 역시 local/manual workflow observability 강화이지 operational curated promotion loop completion은 아닙니다.
- Observable today: latest slice에서는 same local registry `last_update` / `update_history`도 support-status split과 mechanical-policy aggregate를 보존하기 시작했습니다. 그래도 이것 역시 local/manual workflow observability 강화이지 operational curated promotion loop completion은 아닙니다.
- Observable today: latest slice에서는 same `support_registry_update.json` preview와 local registry `last_update`도 `accepted/rejected/pending_by_support_status`를 보존하기 시작했습니다. 그래도 이것 역시 local/manual workflow observability 강화이지 operational curated promotion loop completion은 아닙니다.
- Operational interpretation: current support residual은 “workflow가 전혀 없음”이 아니라 `TKT-008-A1` blocker policy split과 `TKT-009-A1` representative accept-path verification이 아직 안 닫혔다는 쪽에 더 가깝습니다.
- Allowed claim: measured support candidate extraction, review index, and manual update preview exist for repeatability-measured cases
- Forbidden claim: reusable auto-promotion pipeline가 이미 존재한다고 말하는 것

## 8. Performance / Observability Constraints

Constraint: researcher latency variance가 여전히 큽니다.

- Current enforcement surface: performance summary, search traces
- Observable today: repo-local search cache와 diminishing-return early stop이 들어갔지만, representative dynamic rerun에서 RESEARCH는 여전히 가장 큰 비중을 차지하고 remote latency variance도 큽니다.
- Allowed claim: measured sample performance
- Forbidden claim: one-off rerun improvement를 구조 개선으로 일반화

Constraint: observability surface는 좋아졌지만 controller parity를 대체하지는 않습니다.

- Current enforcement surface: `name_only_outcome`, `selection_readiness_summary`, `boundedness_summary`, `open_world_readiness`
- Allowed claim: current boundedness를 정직하게 보여 줌
- Forbidden claim: summary surface가 곧 control-plane 완성을 뜻함

Constraint: runtime aggregate surface는 richer해졌지만 bounded lane 관측치입니다.

- Current enforcement surface: `runtime_surface_summary`, bundle-level `run_summary`, E2E `summary.json`
- Observable today: `runtime_surface_summary`는 topology만이 아니라 `seed_strategy`, `sidecars_source`, `service_env_source`, `network_mode_source`, `volume_contract_source`, `network_contract_source`, `by_poc_entry_source`, `by_poc_cmd_source`, explicit sidecar order bundle count, actual seed apply 결과(`seed_apply_attempted_bundles`, `seed_apply_completed_bundles`, `seed_files_applied_total`), actual seed mount target buckets(`seed_mount_target_bundles`, `custom_seed_mount_target_bundles`, `by_seed_mount_target`), actual executed sidecar buckets(`executed_sidecar_bundles`, `executed_sidecar_count`, `by_executed_sidecar_type`)까지 집계하기 시작했고, latest slice에서는 `runtime_recipe`가 비어 있는 service-level source field뿐 아니라 `run_summary.sidecars/network_mode/sidecar_start_order`와 bounded execution-shape topology fallback까지 읽어 aggregate가 actual execution shape를 더 직접 반영하기 시작했지만, 이것은 일부 bounded mysql/postgres/runtime lanes에서의 관측치를 더 잘 보여 주는 것이지 generalized runtime planner 완성을 의미하지는 않습니다.
- Allowed claim: bounded runtime provenance aggregate exists
- Forbidden claim: aggregate richness alone proves runtime/executor parity closure

Constraint: strict no-remote fail-closed는 capability precheck에서 early reject될 수 있습니다.

- Current enforcement surface: `name_only_outcome`, `terminal_failure_class`, E2E `summary.json`
- Observable today: representative `open-redirect-strict-dynamic-no-remote` direct rerun에서는 remote provider가 없으면 `strict_dynamic_remote_research_unavailable`로 `pre_generation` 단계에서 멈추고 `search_cache_* = 0`, `search_planned_query_count = 0`, `search_executed_query_count = 0`, `search_early_stop_triggered = false`로 남습니다. latest slice 후 same direct rerun에서는 top-level `terminal_failure_class`와 nested `name_only_outcome.terminal_failure_class`도 같이 정렬됩니다.
- Allowed claim: strict dynamic lane can fail closed before RESEARCH when remote capability is unavailable
- Forbidden claim: strict no-remote failure always reflects post-research semantic rejection

Constraint: Tavily는 current canonical live unknown-CWE proving-ground provider이지만 repository-wide mandatory dependency는 아닙니다.

- Current enforcement surface: `rag/tools/web_search.py`, `rag/tools/providers/tavily.py`, `rag/tools/providers/custom.py`, `tests/e2e/test_cases.py`, `ops/ci/run_e2e_tests.sh`
- Observable today: remote search abstraction은 `tavily`와 `custom endpoint`를 모두 지원하고, strict/dynamic researcher gate는 “어떤 remote provider도 configured되지 않았는가”를 먼저 본다. ops/E2E entry도 `VULD_E2E_REQUIRE_REMOTE_PROVIDER=1` generic gate와 `VULD_E2E_REQUIRE_TAVILY=1` canonical Tavily gate를 분리해 쓸 수 있다. 다만 current live unknown-CWE E2E proving ground는 여전히 Tavily key를 기준으로 opt-in되어 있다.
- Allowed claim: Tavily is the current canonical provider for the repository's live unknown-CWE gate, while custom endpoint remains a structural alternative for remote researcher capability
- Forbidden claim: Tavily is required for all open-world/bounded/dynamic validation lanes, or that researcher remote capability is Tavily-only by design

Constraint: strict dynamic live-LLM fail-closed도 capability precheck에서 early reject될 수 있습니다.

- Current enforcement surface: `orchestrator/run_pipeline.py`, `name_only_outcome`, `terminal_failure_class`, E2E `summary.json`
- Observable today: representative `open-redirect-strict-dynamic-stub` direct rerun에서는 live LLM path가 stub/fixture/disallowed 상태이면 `CAPABILITY_CHECK` 단계에서 `strict_dynamic_live_llm_unavailable`로 멈추고, `name_only_outcome.decision=fail_closed`, `name_only_next_required_step=capability_or_research`, `open_world_class=name_driven_capability_gate_failed`로 남습니다.
- Allowed claim: strict dynamic lane can fail closed before RESEARCH when a live LLM path is unavailable or disallowed
- Forbidden claim: strict dynamic fail-closed를 항상 remote researcher evidence 부재 하나로만 설명하는 것

Constraint: local direct runtime verification은 host Docker availability가 먼저 충족되어야 합니다.

- Current enforcement surface: local shell environment, `docker ps`, `tests/e2e/run_case.py`
- Observable today: host Docker integration은 여전히 선행 조건이지만, latest same-day rerun에서는 `docker ps`와 `docker ps -a`가 정상 응답했고 representative dynamic lane(`open-redirect-dynamic-name-only`)와 fixture-backed positive LLM-shaped lane(`trusted-dynamic-sqli`)도 둘 다 expectations를 통과했다. lingering container도 남지 않았으므로 local Docker precondition은 real prerequisite이지만, latest current-state blocker 자체는 아니다.
- Allowed claim: local direct runtime verification may be blocked by host Docker integration prerequisites
- Forbidden claim: 이런 local Docker precondition failure를 곧바로 product/runtime regression으로 읽는 것

Constraint: strict live-LLM fail-closed lane와 positive LLM-shaped lane는 같은 capability claim이 아닙니다.

- Current enforcement surface: `tests/e2e/cases/open-redirect-strict-dynamic-stub`, `tests/e2e/cases/trusted-dynamic-sqli`, `name_only_outcome`, local Docker/runtime prerequisite
- Observable today: `open-redirect-strict-dynamic-stub`는 no-Docker direct rerun만으로 `strict_dynamic_live_llm_unavailable` fail-closed honesty를 확인할 수 있다. 별도로 Docker-enabled rerun에서는 `trusted-dynamic-sqli`가 `provider_health_state=llm_fixture`, `generation_origin=llm_manifest`로 actual Docker materialization까지 갔고, `open-redirect-dynamic-name-only`는 `provider_health_state=llm_degraded`, `generation_origin=deterministic_fallback`, `name_only_outcome.decision=partial`로 actual runtime/oracle path를 다시 열었다. 따라서 strict fail-closed honesty, fixture-backed positive materialization, degraded fallback dynamic lane는 서로 다른 claim이다.
- Allowed claim: live-LLM capability gate honesty, fixture-backed positive materialization, degraded/fallback dynamic execution should be verified separately
- Forbidden claim: strict stub pass나 fixture-backed positive lane pass만으로 live LLM open-world positive generation capability 전체가 직접 검증됐다고 읽는 것

Constraint: summary surface는 richer해졌지만 top-level projection drift가 남아 있습니다.

- Current enforcement surface: top-level `summary.json`, nested `name_only_outcome`, bundle-level runtime/oracle summary
- Observable today: latest slice로 representative `strict no-remote` lane의 `terminal_failure_class` top-level drift와 capability-gate `search_*` null drift는 줄었고, single-bundle manifest도 `executed_sidecars`, `seed_mount_targets`, `seed_apply_*`, `network_mode`, `service_base_url`, `poc_entry`, `poc_entry_source`, `poc_cmd`, `poc_cmd_source` 같은 actual execution detail을 직접 flatten하기 시작했습니다. same top-level E2E summary도 `service_port`, `service_base_url`, `runtime_service_env`, `allow_network`, `network_mode`, `executed_sidecars`, `seed_apply_*`, `seed_mount_targets`와 대응 provenance(`service_port_source`, `service_entry_source`, `poc_entry_source`, `poc_cmd_source`, `base_url_source`, `health_path_source`, `service_env_source`, `sidecars_source`, `allow_network_source`, `network_mode_source`, `sidecar_start_order_source`, `network_contract_source`, `seed_strategy_source`, `seed_files_source`, `volume_contract_source`)까지 직접 노출하기 시작했습니다. latest representative strict direct rerun에서는 top-level `run_passed=false`, `verify_pass=null`, `oracle_execution_parity=missing`, `oracle_execution_attempted=false`, `terminal_failure_class=strict_dynamic_remote_research_unavailable`와 same `bundle_verdict_rollup.by_stage_ceiling/by_terminal_failure_class`도 정렬됩니다. multi-bundle top-level manifest/summary도 `bundle_verdict_rollup`를 통해 `run_passed`, `verify_pass`, `oracle_execution_parity`, `qualitative_tier` 분포와 `by_stage_ceiling`/`by_terminal_failure_class` breakdown을 바로 보여 주고, uniform planning-only/pre-generation lane에서는 core top-level verdict field도 직접 채워집니다. latest slice에서는 mixed multi-bundle lane도 `run_passed_rollup`, `verify_pass_rollup`, `stage_ceiling_rollup`, `terminal_failure_class_rollup`, `oracle_execution_*_rollup` token과 `verdict_authority`를 통해 top-level convenience projection을 더 직접 읽을 수 있게 됐고, same precedence signal은 `repeatability_report.json`/`matrix_report.json`뿐 아니라 `support_candidate.json`/`support_review_index.json`/`support_registry_update.json` preview까지 이어집니다. support workflow는 now `verdict_authority:missing` / `verdict_authority:inconsistent`를 external blocker로도 읽고, review index와 registry preview도 authority aggregate를 직접 보존합니다. latest harness slice에서는 `run_case` / `repeat_case`가 output-dir/attempt 기반 SID salt를 쓰기 시작해, same-case direct run을 병렬로 돌릴 때 artifact contention으로 생기던 false REVIEW failure도 덜 만들게 됐고, same isolation은 `summary.json`의 `execution_salt`, `repeatability_report.json`의 `observed_execution_salts` / `distinct_sid_count`로도 직접 읽을 수 있습니다. 그래도 broader top-level projection이 nested truth와 항상 완전히 동기화된다고 가정하면 안 되며, current residual은 operationally `TKT-008-B1/B2`로 분해하는 편이 더 정확합니다.
- Allowed claim: nested summary surfaces can be more authoritative than top-level convenience projections
- Forbidden claim: every top-level summary field is perfectly synchronized with nested truth fields

Constraint: eval matrix는 current E2E case set 기준으로만 부분 도입됐습니다.

- Current enforcement surface: `tests/e2e/case_matrix.json`, `tests/e2e/run_case.py`, `tests/e2e/repeat_case.py`, `tests/e2e/matrix_report.py`
- Observable today: current case collection은 axis-tagged matrix와 repeatability-aware rollup으로 정리되고, latest slice에서는 `repeatability_report.json`의 `observed_artifact_quality_bands/observed_qualitative_tiers`와 `matrix_report.json`의 `quality_observations.by_band/by_qualitative_tier/oracle_high_nonhigh_band_cases`도 함께 남기기 시작했지만, 그것이 곧 generalized capability coverage를 보장하는 것은 아닙니다.
- Observable today: latest slice에서는 same `repeatability_report.json`가 `measured_gate = {ready, blockers}` preview를 담고, `matrix_report.json`도 `measured_gate_observations`를 집계하며, support extraction도 이를 `measured_gate:*` external blocker로 읽기 시작했습니다. same `support_review_index.json` / `support_registry_update.json` preview도 `measured_gate_ready_bundle_count`, `measured_gate_blocked_bundle_count`, `by_measured_gate_blocker`를 보존하기 시작했지만, 이건 아직 authoritative regression gate의 final form이 아니라 preview/enforcement bridge에 가깝습니다.
- Allowed claim: current E2E cases are matrix-tagged and repeatability-aware rollup exists for measured cases
- Forbidden claim: matrix rollup alone proves generalized open-world support

## 9. Non-Claims

아래는 현재 강하게 말하면 안 되는 주장입니다.

- arbitrary 취약점 이름만으로 generalized open-world positive를 안정적으로 만든다
- unknown family / unknown stack / multi-service topology를 실제로 materialize한다
- `promotion_eligible=true`가 generalized support readiness를 뜻한다
- `artifact_quality=high`가 사람 기준 좋은 lab realism을 항상 보장한다
- 현재 `request_ir`가 이미 generator/executor의 authoritative control-plane이다

## How To Update This Document

- direct rerun, current code inspection, or stable policy change가 있을 때만 갱신합니다.
- TODO, priority, next slice는 적지 않습니다. phase roadmap은 [docs/final_solution.md](final_solution.md), actionable ticket backlog는 [docs/work_tickets.md](work_tickets.md)로 보냅니다.
- representative sample 수치는 “observed sample”로만 적고, generalized claim으로 올리지 않습니다.
- validation prerequisite나 harness command routing이 바뀌면 [docs/handbook.md](handbook.md), [tests/e2e/README.md](../tests/e2e/README.md)와 같이 맞춥니다.
- completion companion 관계나 completion reading order가 바뀌면 [docs/work_tickets.md](work_tickets.md), [README.md](../README.md)와 같이 맞춥니다.
- priority companion 관계나 priority reading order가 바뀌면 [docs/work_tickets.md](work_tickets.md), [README.md](../README.md)와 같이 맞춥니다.
- LLM-response stricter reading의 claim boundary가 바뀌면 [docs/work_tickets.md](work_tickets.md)의 `LLM-Response Capability Overlay`와 같이 맞춥니다.
- latest positive representative pair의 ticket-form 해석이 바뀌면 [docs/work_tickets.md](work_tickets.md)의 `Assessment-To-Ticket Interpretation`와 같이 맞춥니다.
- 잔여 작업량/turn envelope 해석이 바뀌면 [docs/work_tickets.md](work_tickets.md)의 `Estimated Turn Envelope`와 같이 맞춥니다.
- [docs/work_tickets.md](work_tickets.md)의 `Turn Estimate Entry`가 바뀌면 same shortcut도 같이 맞춥니다.
- review mode entry shortcut이 바뀌면 [docs/work_tickets.md](work_tickets.md), [README.md](../README.md)와 같이 맞춥니다.
