# executor/runtime 디렉토리

Status: support
Audience: implementation
Source of truth for: executor entrypoint and runtime evidence surfaces
Not the source of truth for: topology constraints or roadmap priority
Last validated against: current repo layout, bundle-scoped execution surface wiring, bounded contract-stage runtime parity hardening, and active ticket decomposition on 2026-03-19

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

- `executor/runtime/docker_local.py`: Docker build/run, readiness, sidecar/network handling, run summary 생성

## 데이터 계약

- 입력: workspace, `plan.json`, `policy.executor`, resolved contract surface
- 출력: `build.log`, `run.log`, `summary.json`, `run/index.json`, `oracle_execution.json`

## 현재 구현상 포인트

- executor는 여전히 일부 fallback 재해석을 남기지만, 이제 bundle-scoped execution surface를 한 번 계산한 뒤 그 값을 network/sidecar/readiness에 재사용합니다.
- `service_plus_sidecar`는 현재 generator invention보다 policy-coupled lane에 가깝습니다.
- `executor_plan`은 존재하지만 아직 full runtime control-plane은 아닙니다.
- 현재 slice에서는 `base_url`, `service_env`, `requires_external_db` 판단이 `executor_plan`/`runtime_recipe`를 더 우선하도록 보강됐습니다.
- 현재 slice에서는 bundle별 `effective executor policy`가 도입돼, 비어 있는 `sidecars/network_mode/allow_network`가 `executor_plan`/`runtime_recipe`로 보완됩니다.
- 현재 slice에서는 `executor_plan.sidecars`가 global policy default보다 우선되고, bundle별 sidecar alias가 있으면 executor network도 bundle-scoped named network로 승격됩니다.
- 현재 slice에서는 `executor_plan.healthchecks`가 `health_path`보다 앞서는 readiness probe 후보가 되고, HTTP healthcheck 뒤에 TCP fallback이 유지됩니다.
- 현재 slice에서는 sidecar env/aliases/ready_probe도 resolved `executor_plan.sidecars`를 우선 읽습니다.
- 현재 slice에서는 executor가 `executor_plan/runtime_recipe`의 `db`, `db_source`, `topology_source`, `runtime_dependency_hypotheses`도 읽기 시작했고, external DB 판단에 이를 보조 근거로 사용합니다.
- 현재 slice에서는 `generator_manifest.metadata.target_db/target_sidecars`도 fallback runtime hint로 읽기 시작했고, external DB 판단과 sidecar-empty error context에 이를 반영합니다.
- 현재 slice에서는 `generator_manifest.metadata.target_topology`도 fallback runtime hint로 읽기 시작했고, execution surface의 topology/network 판단에 이를 반영합니다.
- 현재 slice에서는 explicit sidecar plan이 비어 있어도 `generator_manifest.metadata.target_sidecars/target_db`가 `mysql/mariadb/postgres/postgresql`를 가리키면 bounded default sidecar plan을 합성할 수 있습니다.
- latest slice에서는 일부 mysql/postgres lane에서 이 bounded sidecar plan이 executor 이전 contract 단계(`runtime_recipe`/`executor_plan`)에서 이미 합성되기 시작했습니다. executor는 여전히 fallback synthesis를 남기지만, raw manifest metadata를 직접 재해석해야 하는 폭은 조금 줄었습니다.
- same bounded lane에서는 contract가 합성한 `sidecars_source`/`service_env_source` provenance도 executor execution surface까지 유지되기 시작했습니다. 즉 summary에서 합성 출처가 `executor_plan.sidecars` 같은 generic label로 뭉개지는 경우가 줄었습니다.
- latest slice에서는 same bounded lane의 `network_enabled/network_mode`와 그 provenance도 contract 단계에서 먼저 정렬되기 시작했습니다. executor는 explicit policy cap을 계속 우선하지만, contract가 요구하는 bridge network와 cap provenance가 더 일관되게 보입니다.
- same bounded lane에서는 executor execution surface와 bundle summary도 이제 `allow_network_source`/`network_mode_source`를 같이 남기기 시작했습니다. 즉 contract-stage network synthesis와 policy cap provenance가 operator-facing surface에서 더 직접 읽힙니다.
- latest slice에서는 `sidecar_start_order`도 executor execution surface와 bundle summary까지 내려오고, `_start_sidecars()`는 explicit order를 따르며 `_stop_sidecars()`는 reverse order로 정리합니다.
- latest slice에서는 `seed_strategy`도 executor execution surface와 bundle summary까지 내려오고, sqlite/service-init validation과 sidecar SQL apply helper가 이 전략을 우선 읽기 시작했습니다.
- same `seed_strategy`는 이제 run 전 contract validation에도 일부 연결돼, `sqlite_service_init`의 non-sqlite/sidecar 모순과 `sidecar_sql_apply`의 external-db 또는 `.sql` seed file 부재를 early failure로 막기 시작했습니다.
- latest slice에서는 same `seed_strategy=sidecar_sql_apply`가 SQL-capable sidecar target 없이 선언되거나 mysql/postgres family가 동시에 걸려 actual apply target이 모호한 경우도 early failure로 막기 시작했습니다.
- latest slice에서는 same `sidecar_sql_apply`가 DB family hint만 있고 actual SQL-capable sidecar entry가 없는 경우도 early failure로 막기 시작했습니다.
- latest slice에서는 actual seed apply 결과도 bundle summary까지 올라오기 시작했습니다. 즉 `seed_apply_attempted`, `seed_apply_completed`, `seed_files_applied_total`로 bounded sidecar SQL apply가 실제로 일어났는지 operator가 바로 읽을 수 있습니다.
- 같은 bounded hint에서 executor는 `DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME/APP_PORT` service env defaults도 보수적으로 채울 수 있습니다.
- 현재 slice에서는 `executor_plan.seed_files`도 execution surface와 run summary까지 내려오고, declared seed file이 workspace에 없으면 run 전에 early validation으로 실패시킵니다.
- 현재 slice에서는 sqlite lane에 한해 declared `seed_files`가 있을 때 `service_entry` 안의 최소 runtime init 신호(`init_db`, `executescript`, `schema.sql` 참조 등)도 run 전에 검증합니다.
- 현재 slice에서는 external mysql/postgres 계열 sidecar가 있고 declared `.sql` seed file이 있으면, executor가 workspace를 read-only로 mount한 뒤 sidecar readiness 이후 listed SQL seed를 bounded하게 실제 적용합니다.
- latest direct rerun 기준으로 compiler-generated MySQL sidecar lane도 이제 `schema.sql`/`seed_strategy=sidecar_sql_apply` surface를 갖게 되어, same bounded actual seed apply path를 타기 시작했습니다.
- latest direct rerun 기준으로 same compiler-generated MySQL sidecar lane은 payload-driven negative/metamorphic replay도 정상 수행해 `oracle_execution_parity = high`까지 올릴 수 있게 됐습니다. 다만 deterministic fallback lane까지 일반화된 것은 아닙니다.
- latest direct rerun 기준으로 representative stateless/body-structured/sessionful minimal_dynamic fallback(`open_redirect`, `template_injection`, `path_traversal`, `ssrf`, `deserialization`, `xxe`, `csrf`)도 payload-aware `poc.cmd`를 통해 negative/metamorphic replay를 정상 수행해 `oracle_execution_parity = high`까지 올릴 수 있게 됐습니다. 다만 이것 역시 fallback lane 일부의 bounded closure입니다.
- 현재 slice에서는 `executor_plan.env_contract`도 execution surface와 run summary까지 내려오고, declared service env key/value가 resolved `service_env`와 어긋나면 run 전에 early validation으로 실패시킵니다.
- same `env_contract`는 이제 `sidecar:<name>` scope도 bounded하게 읽기 시작해서, declared sidecar env target이 없거나 key/value가 drift하면 run 전에 early validation으로 실패시킵니다.
- latest slice에서는 same `env_contract`가 같은 `scope+name`에 서로 다른 expected value를 중복 선언해 contract 자체가 모호한 경우도 executor가 run 전에 early validation으로 실패시킵니다.
- latest slice에서는 same `env_contract`가 `service`와 `sidecar:*` 외 unsupported scope를 포함하면 executor가 run 전에 early validation으로 실패시킵니다.
- latest slice에서는 same bounded seed lane의 `volume_contract`도 execution surface와 bundle summary까지 내려오고, executor가 declared workspace seed mount intent를 validation하고 실제 sidecar mount 판단에도 우선 반영하기 시작했습니다. custom absolute target도 허용되므로 mount path와 seed apply path가 declared target을 따릅니다.
- latest slice에서는 same `volume_contract`가 `sidecar:*` 외 unsupported scope를 포함하면 executor가 run 전에 early validation으로 실패시킵니다.
- latest slice에서는 same `volume_contract`가 `workspace/runtime` 외 unsupported `source` 값을 포함하면 executor가 run 전에 early validation으로 실패시킵니다.
- latest slice에서는 same `volume_contract`가 같은 `scope+target`에 서로 다른 `source/mode`를 중복 선언해 mount definition 자체가 충돌하는 경우도 executor가 run 전에 early validation으로 실패시킵니다.
- latest slice에서는 same bounded seed lane의 `volume_contract`가 같은 sidecar에 여러 workspace read-only seed mount target을 선언해 apply target이 모호해지는 경우도 executor가 run 전에 early failure로 막기 시작했습니다.
- latest slice에서는 same actual seed mount target도 `seed_mount_targets`로 bundle summary까지 노출되기 시작했습니다.
- same bounded sidecar lane에서는 `network_contract`도 execution surface와 bundle summary까지 내려오고, executor가 service `DB_HOST`와 sidecar alias drift, missing sidecar target, network-disabled 모순을 early validation으로 막기 시작했습니다.
- latest slice에서는 same `network_contract`가 `service`와 `sidecar:*` 외 unsupported scope를 포함하면 executor가 run 전에 early validation으로 실패시킵니다.
- latest slice에서는 same `network_contract`가 validation뿐 아니라 alias materialization에도 일부 쓰이기 시작했습니다. 즉 sidecar entry alias가 비어 있어도 declared contract가 있으면 execution surface가 alias를 보강하고 그 결과가 `docker run --network-alias`까지 이어집니다.
- latest slice에서는 same `network_contract`가 service env binding에도 일부 쓰이기 시작했습니다. 즉 `service` scope `{name, alias}`가 있고 해당 env key가 비어 있으면 execution surface가 이를 bounded fallback으로 채워 `service_env_source=*+network_contract_aliases`로 surface합니다.
- latest slice에서는 same `network_contract`가 같은 service env key에 서로 다른 alias를 중복 선언해 contract 자체가 모호한 경우도 executor가 run 전에 early validation으로 실패시킵니다.
- latest slice에서는 same `network_contract`가 service scope alias를 선언했는데 sidecar alias catalog 자체가 없어 target을 전혀 해석할 수 없는 경우도 executor가 run 전에 early validation으로 실패시킵니다.
- latest slice에서는 same `service_env_source` provenance도 더 길게 보존돼, 이후 runtime sidecar defaults가 추가로 채워져도 `*+network_contract_aliases+runtime_hint_sidecar_defaults`처럼 합성 source를 읽을 수 있습니다.
- latest slice에서는 explicit sidecar plan/order가 비어 있을 때 `runtime_graph.nodes`의 sidecar node와 `startup_order_index`를 bounded fallback source로 읽기 시작했습니다. same bounded lane에서는 `startup_order_index`가 없어도 `runtime_graph.edges[*].startup_after`를 bounded sidecar order fallback source로 읽기 시작했습니다. same `runtime_graph.nodes`는 sidecar `env`/`ready_probe` reconstruction에도 일부 연결되고, latest slice에서는 `runtime_graph.env_contract`도 service env fallback source를 넘어서 sidecar env backfill source로 읽히기 시작했습니다. `runtime_graph.network.enabled/mode`는 `allow_network/network_mode` fallback source로, `runtime_graph.exploit_path`와 service node는 `service_port`/`service_entry`/`base_url` fallback source로도 읽힙니다. latest slice에서는 declared `healthchecks.port`뿐 아니라 `runtime_recipe.healthchecks`도 actual readiness candidate fallback으로 읽히기 시작했고, `health_path_source`와 `healthchecks_source`도 same healthchecks declaration을 더 직접 반영하기 시작했습니다. 즉 same bounded lane에서는 graph와 declared healthchecks가 sidecar/env/order/network/service reconstruction의 실제 입력으로도 부분 연결됩니다.
- latest slice에서는 same `service_entry`도 actual run 전 workspace existence validation으로 연결돼, declared entry file drift를 executor가 early failure로 막기 시작했습니다.
- latest slice에서는 same local `base_url`도 `service_port`와 어긋나면 actual run 전 early failure로 막기 시작했습니다. 즉 localhost/127.0.0.1 target의 endpoint contract drift를 더 일찍 드러냅니다.
- latest slice에서는 same `runtime_graph.edges[*].startup_after` fallback도 이제 malformed reference, unknown sidecar dependency, cyclic dependency를 executor run 전에 early failure로 막기 시작했습니다. 즉 bounded graph-derived ordering이 obviously invalid dependency graph를 조용히 삼키지는 않습니다.
- latest slice에서는 `poc_entry`도 이제 `executor_plan/runtime_recipe/resolved_contract/runtime_graph.exploit_path` 순서로 execution surface에 올라오고, executor가 run 전 workspace existence/self-consistency validation까지 수행합니다. 즉 PoC script path가 더 이상 executor 내부의 별도 metadata 재해석만으로 결정되지 않고, bundle-scoped execution contract와 summary surface를 함께 탑니다.
- latest slice에서는 `poc_cmd`도 이제 execution surface에 올라와 main PoC execution과 oracle replay가 같은 resolved command를 재사용하기 시작했습니다. 즉 executor가 PoC command template를 metadata에서 다시 따로 해석하는 폭이 줄고, `poc_cmd_source`도 summary/aggregate에 남습니다.
- latest slice에서는 same `poc_cmd`도 bounded self-consistency validation에 일부 연결돼, declared local script reference가 resolved `poc_entry`와 명백히 어긋나면 executor가 run 전에 early failure로 막기 시작했습니다. placeholder(`{{poc_path}}`)나 inline command는 계속 허용합니다.
- latest slice에서는 same service `healthchecks`도 bounded self-consistency validation에 일부 연결돼, unsupported transport, HTTP(S) probe without path, TCP probe with path, non-service node declaration을 executor가 run 전에 early failure로 막기 시작했습니다.
- latest slice에서는 same service `healthchecks`가 서로 다른 explicit port를 가리키거나 resolved `service_port`와 명백히 어긋나도 executor가 run 전에 early failure로 막기 시작했습니다.
- latest slice에서는 same service HTTP(S) healthcheck path가 사실상 하나로 정해져 있는데 resolved `health_path`가 다른 값을 가리키면, 그 obvious path drift도 executor가 run 전에 early failure로 막기 시작했습니다.
- latest slice에서는 same `service_env` 안의 `APP_PORT`/`PORT`가 resolved `service_port`와 명백히 어긋나도 executor가 run 전에 early failure로 막기 시작했습니다.
- latest slice에서는 same bounded external-DB lane의 `DB_PORT`도 resolved mysql/postgres runtime kind와 명백히 어긋나면 executor가 run 전에 early failure로 막기 시작했습니다.
- latest slice에서는 same workspace path contract도 조금 더 조여져, `service_entry`, `poc_entry`, declared `seed_files`의 absolute path나 `..` traversal이 있으면 executor가 run 전에 early failure로 막기 시작했습니다.
- latest slice에서는 same bounded external-DB lane의 `DB_HOST`도 actual sidecar alias/name과 명백히 어긋나면 executor가 run 전에 early failure로 막기 시작했습니다.
- latest slice에서는 same bounded external-DB lane의 `DB_NAME/DB_USER/DB_PASSWORD`도 service env와 actual sidecar env가 둘 다 선언돼 있는데 서로 다르면 executor가 run 전에 early failure로 막기 시작했습니다.
- latest slice에서는 same bounded sidecar lane의 `ready_probe.type`도 actual mysql/postgres runtime kind와 명백히 어긋나면 executor가 run 전에 early failure로 막기 시작했습니다.
- latest slice에서는 same bounded sidecar lane의 `name`/`aliases`도 network identity contract로 읽혀, duplicate sidecar name이나 alias collision, alias-vs-other-name collision이 있으면 executor가 run 전에 early failure로 막기 시작했습니다.
- latest slice에서는 same bounded external-DB lane의 `DB_NAME/DB_USER/DB_PASSWORD`도 service env와 actual sidecar env가 둘 다 선언돼 있는데 서로 다르면 executor가 run 전에 early failure로 막기 시작했습니다.
- same service-level provenance(`service_port_source`, `service_entry_source`, `base_url_source`, `health_path_source`)도 이제 run summary, E2E summary, PACK aggregate까지 노출되므로 operator가 “어디서 복구됐는지”를 더 직접 읽을 수 있습니다.
- 현재 slice에서는 executor가 live container 상태에서 payload-driven negative/metamorphic oracle replay를 수행하고 `oracle_execution.json`을 남깁니다.
- 여전히 dependency order, generalized seed/init DSL, richer volume/env contract semantics, 일부 network lifecycle은 policy/runtime fallback에 남아 있으므로 full executor parity까지는 갭이 있습니다.

## Current Residual Owners

- `executor_plan` / `runtime_graph` authoritative consumption residual은 `TKT-002-A/B/C` owner다.
- dependency ordering/lifecycle residual은 `TKT-003-A/B` owner다.
- seed/init DSL residual은 `TKT-004-A/B` owner다.
- env/volume/network contract generalization residual은 `TKT-005-A/B/C` owner다.
- host Docker availability precondition은 backlog ticket이 아니라 operational prerequisite다. current cheapest no-Docker pair(`foobar-name-only-negative`, `open-redirect-strict-dynamic-no-remote`)는 executor truth 자체가 아니라 upstream policy/reporting sanity만 확인한다.
- 현재 executor 문서는 bounded contract-stage/runtime parity와 stronger early validation까지는 설명할 수 있지만, generalized runtime control-plane closure를 claim하면 안 된다.

## Residual Review Focus

- `TKT-002` residual은 `docker_local.py`가 `runtime_graph` / `executor_plan`을 실제 execution precedence로 쓰는지부터 본다.
- `TKT-003`~`TKT-005` residual은 ordering, seed/init, env-volume-network가 early validation을 넘어 actual runtime materialization까지 이어지는지부터 본다.

## Completion Review Focus

- `TKT-002` completion은 `docker_local.py`가 `runtime_graph` / `executor_plan`을 fallback hint가 아니라 actual materialization precedence로 소비하는지부터 본다.
- `TKT-003`~`TKT-005` completion은 lifecycle ordering, seed/init result surface, env-volume-network contract semantics가 실제 run summary와 oracle replay surface까지 일관되게 남는지부터 본다.

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

- current completion priority order에서 executor는 `TKT-002`~`TKT-005` generalized runtime closure의 primary companion이다.
- Docker prerequisite가 막힌 환경의 no-Docker pair는 executor completion 증명이 아니라, current order를 바꾸지 않는 fallback sanity라는 점도 여기서 같이 읽는다.
- latest positive representative pair는 executor가 실제 runtime path까지는 열 수 있음을 보여 주지만, same ticket-form reading은 여전히 generalized runtime closure 미완으로 귀결된다. canonical 해석은 [docs/work_tickets.md](../work_tickets.md)의 `Assessment-To-Ticket Interpretation`을 따른다.
- 잔여 작업량/turn envelope 해석도 [docs/work_tickets.md](../work_tickets.md)의 `Estimated Turn Envelope`를 같이 따른다.
- turn estimate shortcut도 [docs/work_tickets.md](../work_tickets.md)의 `Turn Estimate Entry`를 같이 따른다.
- LLM-response stricter reading에서도 positive LLM-shaped capability는 Docker/runtime closure가 열려야 의미가 있으므로, executor priority는 그대로 본체 bucket에 남는다.
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

- `TKT-002`를 먼저 볼 때:
  - `executor/runtime/docker_local.py`의 execution surface resolution
  - `runtime_graph`, `executor_plan`, `artifacts/<SID>/run/summary.json`
- `TKT-003`를 먼저 볼 때:
  - `startup_order_index`, `startup_after`, `sidecar_start_order`
  - `_start_sidecars()` / `_stop_sidecars()` ordering path
- `TKT-004`, `TKT-005`를 먼저 볼 때:
  - `seed_strategy`, `seed_files`, `env_contract`, `volume_contract`, `network_contract`
  - early validation path와 actual runtime materialization path
- `TKT-007`과 맞닿는 executor-side oracle surface를 볼 때:
  - `poc_entry`, `poc_cmd`
  - `artifacts/<SID>/run/oracle_execution.json`

## Representative Validation Surface

- executor/runtime regression:
  - `tests/test_executor_poc_exec.py`
  - `tests/test_contract_resolution.py`
  - `tests/test_runtime_rules.py`
  - `tests/test_runtime_surface.py`
  - `tests/test_run_case_summary_surface.py`
- representative runtime rerun:
  - Docker-enabled `tests/e2e/test_cases.py`
  - representative direct `run_case.py` lane for single-service and sidecar topology
  - no-Docker pair (`foobar-name-only-negative`, `open-redirect-strict-dynamic-no-remote`)는 executor parity regression이 아니라 Docker prerequisite가 막힌 환경에서 policy/reporting boundary만 빠르게 확인하는 fallback rehearsal이다

이 디렉토리를 볼 때는 [docs/constraints.md](../constraints.md)의 executor/runtime constraints를 먼저 같이 봐야 합니다.

## How To Update This Document

- executor entrypoint, runtime evidence surface, contract validation 범위가 바뀔 때만 갱신한다.
- representative runtime truth나 rerun 결과는 [docs/current_state_gap_analysis.md](../current_state_gap_analysis.md)에 남긴다.
- current runtime limit과 operational prerequisite는 [docs/constraints.md](../constraints.md)에 남긴다.
- priority와 residual owner는 [docs/final_solution.md](../final_solution.md), [docs/work_tickets.md](../work_tickets.md)로 보낸다.
- ticket-first entrypoint나 representative validation surface가 바뀌면 이 문서의 해당 섹션도 같이 갱신한다.
- completion review focus가 바뀌면 same runtime-control-plane mapping에 맞춰 이 문서도 같이 갱신한다.
- residual review focus가 바뀌면 same runtime-control-plane mapping에 맞춰 이 문서도 같이 갱신한다.
- priority review focus나 priority companion 해석이 바뀌면 [docs/code/README.md](README.md), [docs/work_tickets.md](../work_tickets.md)와 같이 갱신한다.
- LLM-response stricter reading의 executor/runtime 해석이 바뀌면 [docs/work_tickets.md](../work_tickets.md)의 `LLM-Response Capability Overlay`와 같이 갱신한다.
- latest positive representative pair의 ticket-form 해석이 바뀌면 [docs/work_tickets.md](../work_tickets.md)의 `Assessment-To-Ticket Interpretation`와 같이 갱신한다.
- 잔여 작업량/turn envelope 해석이 바뀌면 [docs/work_tickets.md](../work_tickets.md)의 `Estimated Turn Envelope`와 같이 갱신한다.
- [docs/work_tickets.md](../work_tickets.md)의 `Turn Estimate Entry`가 바뀌면 same shortcut도 같이 갱신한다.
- review mode entry shortcut이 바뀌면 [docs/code/README.md](README.md)와 같이 갱신한다.
- runtime representative harness나 Docker-gated rerun path가 바뀌면 [tests/e2e/README.md](../../tests/e2e/README.md)와 같이 갱신한다.
