# orchestrator 디렉토리

Status: support
Audience: implementation
Source of truth for: orchestrator entrypoints and output surfaces
Not the source of truth for: project goals, constraints, roadmap
Last validated against: current repo layout, staged recovery/operator summary surfaces, build-ready/support workflow wiring, and local registry workflow hardening on 2026-04-02

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

## 핵심 파일

- `orchestrator/plan.py`: requirement 정규화, SID 계산, `plan.json` 작성
- `orchestrator/run_pipeline.py`: RESEARCH → GENERATE → EXECUTE → VERIFY → REVIEW → PACK loop 실행
- `orchestrator/pack.py`: summary/manifest rollup, readiness/promotion surfaces 생성
- `orchestrator/support_extract.py`: measured support candidate/review index/update preview extraction helper

## 구현상 중요 포인트

- `plan.json`은 경로, policy, variation, run matrix의 시작점입니다.
- `run_pipeline.py`는 stage timing과 capability gate를 surface합니다.
- `pack.py`는 `name_only_outcome`, `support_promotion`, `open_world_readiness`, `artifact_quality`의 최종 집계면입니다.
- latest slice에서는 same `pack.py`가 `staged_synthesis.file_manifest.build_ready` / `build_safety_policy`도 `support_promotion.reasons`와 `open_world_readiness.blockers` vocabulary로 읽기 시작했습니다. 따라서 buildable하지 않은 Docker bundle이 measured/support lane에서 silent positive처럼 남지 않게 됐습니다.
- latest slice에서는 same `artifact_quality`가 `band`만이 아니라 `qualitative_tier`, `qualitative_review`, `qualitative_signals`도 같이 surface하고, `artifact_quality_summary`도 `by_qualitative_tier`, `oracle_high_nonhigh_band_bundles`를 집계합니다. 즉 executed oracle closure와 실제 artifact quality tier를 분리해서 top-level aggregate에서 읽을 수 있습니다.
- latest slice에서는 single-bundle manifest도 `executed_sidecars`, `seed_mount_targets`, `seed_apply_*`, `network_mode`, `service_base_url` 같은 actual execution detail을 top-level로 직접 flatten하기 시작했습니다. latest slice에서는 same `executed_sidecars[*].type/aliases/seed_mount_target/seed_files_applied`뿐 아니라 actual `service_env_runtime`/`allow_network` 값, `poc_entry`, `poc_entry_source`, `poc_cmd`, `poc_cmd_source`도 top-level에서 읽을 수 있습니다.
- latest slice에서는 multi-bundle manifest도 `bundle_verdict_rollup`를 같이 싣기 시작했습니다. 즉 `run_passed/verify_pass` count, `oracle_execution_parity` 분포, `qualitative_tier` 분포뿐 아니라 `by_stage_ceiling`/`by_terminal_failure_class`도 `bundles[]`를 직접 열지 않고 top-level convenience projection에서 읽을 수 있습니다.
- latest slice에서는 same multi-bundle lane가 uniform planning-only/pre-generation verdict를 가질 때 `run_passed`, `verify_pass`, `stage_ceiling`, `terminal_failure_class`, `oracle_execution_parity`, `oracle_execution_attempted`도 top-level에서 직접 읽을 수 있습니다.
- latest slice에서는 same mixed multi-bundle lane도 `run_passed_rollup`, `verify_pass_rollup`, `stage_ceiling_rollup`, `terminal_failure_class_rollup`, `oracle_execution_parity_rollup`, `oracle_execution_attempted_rollup`를 같이 surface하므로, mixed 상태도 top-level convenience projection에서 더 직접 읽을 수 있습니다.
- latest slice에서는 same manifest가 `verdict_authority`도 같이 surface하므로, 각 verdict field가 top-level convenience projection인지 nested bundle truth canonical input인지 operator/measurement layer에서 더 직접 읽을 수 있습니다.
- latest slice에서는 same precedence signal이 `repeatability_report.json`와 `matrix_report.json`까지 이어져, measured gate 쪽에서도 verdict projection mode를 더 직접 읽을 수 있습니다.
- latest slice에서는 same `repeatability_report.json`가 `measured_gate = {ready, blockers}` preview를 담고, `matrix_report.json`도 `measured_gate_observations`를 집계하며, support extraction은 이를 `measured_gate:*` external blocker로 읽기 시작했습니다.
- latest slice에서는 same precedence signal이 `support_candidate.json`와 `support_review_index.json`까지 이어져, support review/workflow 쪽에서도 verdict projection mode를 더 직접 읽을 수 있습니다.
- latest slice에서는 same support workflow가 `verdict_authority:missing` / `verdict_authority:inconsistent`를 external blocker로도 읽기 시작해, measured precedence drift가 reviewable candidate로 바로 승격되지 않게 됐습니다.
- latest slice에서는 same `support_review_index.json`도 `authority_ready_bundle_count`, `authority_blocked_bundle_count`, `by_authority_blocker`를 함께 집계해, review queue 수준에서도 authority blocker 분포를 직접 읽을 수 있습니다.
- latest slice에서는 same `support_review_index.json`와 `support_registry_update.json` preview도 `measured_gate_ready_bundle_count`, `measured_gate_blocked_bundle_count`, `by_measured_gate_blocker`를 함께 집계해, measured gate blocker 분포도 review/update aggregate에서 직접 읽을 수 있습니다.
- latest slice에서는 same `support_registry_update.json` preview도 authority aggregate와 `accepted/rejected/pending_by_verdict_authority_mode`를 함께 보존해, registry update rehearsal 단계에서도 authority context를 직접 읽을 수 있습니다.
- latest slice에서는 same `support_registry_update.json` preview를 actual `curated_support_registry.json` local write/merge workflow로 적용할 수 있게 됐고, accepted item upsert와 reject decision history도 남길 수 있게 됐습니다.
- latest slice에서는 same local registry도 `update_history`, `by_decision`, `by_reviewer`를 보존하고 obvious merge conflict를 reject하기 시작해, provenance/history persistence와 최소 merge policy가 더 직접 생겼습니다.
- latest slice에서는 same existing registry item에 대한 reject decision도 item-level `history`, `last_decision`, `rejected_count`로 반영되기 시작해, local registry history가 accept-only append보다 더 실제 review trace에 가까워졌습니다.
- latest slice에서는 same previously rejected item이 later accept될 때도 `rejected_count`와 prior history를 preserve하기 시작해, local registry history lifecycle이 단순 overwrite보다 조금 더 안정화됐습니다.
- latest slice에서는 same sparse accepted/rejected update도 prior `source_artifacts`는 유지하면서 current support-status split은 reviewable semantics로 채우기 시작해, provenance retention과 current decision interpretation이 덜 충돌하게 됐습니다.
- latest slice에서는 same sparse older local registry item도 `history`와 last event를 읽어 `accepted_count` / `rejected_count` / `review_status` / `support_status` / `last_decision` / `source_artifacts`를 current schema로 normalize하기 시작했고, top-level `schema_upgraded_item_count`, `by_schema_upgrade_reason`, item-level `schema_upgrade_reasons`도 함께 surface에 오르기 시작했습니다.
- latest slice에서는 same sparse older `update_history` entry도 current update schema로 normalize하기 시작했고, top-level `schema_upgraded_update_count`와 `by_update_schema_upgrade_reason`도 함께 surface에 오르기 시작했습니다.
- latest slice에서는 same sparse older `decision_history` event도 current decision schema로 normalize하기 시작했고, top-level `schema_upgraded_decision_event_count`와 `by_decision_schema_upgrade_reason`도 함께 surface에 오르기 시작했습니다.
- latest slice에서는 same local registry maintenance 상태도 top-level `schema_status` token으로 바로 요약되기 시작했습니다.
- latest slice에서는 same item/update/decision record도 `schema_status=normalized|legacy_upgraded`를 직접 보존하기 시작했습니다.
- latest slice에서는 same local registry item도 `review_status`를 직접 갖고, top-level `by_review_status` aggregate도 생겨 현재 accepted/rejected state를 더 바로 읽을 수 있게 됐습니다.
- latest slice에서는 same local registry item도 latest `source_artifacts`를 직접 보존하고, top-level `items_with_source_artifacts_count`도 생겨 현재 상태가 어떤 artifact trace에서 왔는지 더 바로 읽을 수 있게 됐습니다.
- latest slice에서는 same support workflow도 blocker를 `mechanical` vs `promotion_policy` class로 나눠 surface하고, candidate `mechanically_healthy` / `promotion_policy_ready`, review/update aggregate `mechanically_*` / `promotion_policy_*` count, `by_mechanical_blocker` / `by_promotion_policy_blocker`도 같이 노출하기 시작했습니다.
- latest slice에서는 same support workflow도 `support_status` / `by_support_status`를 같이 노출해, current promotion state를 token으로 더 직접 읽을 수 있게 됐습니다.
- latest slice에서는 same `support_review_index.json`와 `support_registry_update.json` preview도 `by_case_status`, `case_statuses[]`, `all_reviewable_cases`, `mixed_cases`, `all_blocked_cases`를 같이 보존해, review/update preview가 bundle-level aggregate만이 아니라 case-level reviewability vocabulary도 유지하게 됐습니다.
- latest slice에서는 same `curated_support_registry.json` local registry도 item-level `support_status`, `mechanically_healthy`, `promotion_policy_ready`와 top-level `by_support_status`, `mechanically_*_item_count`, `promotion_policy_*_item_count`를 함께 보존해, support interpretation surface가 local registry 끝단까지 더 일관되게 이어지기 시작했습니다.
- latest slice에서는 same local registry current state도 `by_case_review_status`, `case_review_statuses[]`, `all_accepted_cases`, `mixed_review_status_cases`, `all_rejected_cases`를 같이 보존하고, `last_update`도 explicit case count/list와 `accepted/rejected/pending_by_support_status`를 같이 보존해 preview/current-state/apply-context가 같은 vocabulary를 유지하게 됐습니다.
- latest slice에서는 same local registry `last_update` / `update_history`도 support-status split과 mechanical-policy aggregate를 함께 보존해, latest apply context도 same interpretation surface로 읽을 수 있게 됐습니다.
- latest slice에서는 same `support_registry_update.json` preview와 local registry `last_update`도 `accepted/rejected/pending_by_support_status`를 함께 보존해, decision outcome breakdown도 same support-status token으로 읽을 수 있게 됐습니다.
- latest slice에서는 same `support_review.py -> support_decide.py -> support_apply.py` chain도 synthetic reviewable accept path와 blocked no-op path를 regression으로 고정해, local workflow CLI가 actual JSON artifact까지 일관되게 materialize되는 것을 자동 검증하기 시작했습니다.
- latest slice에서는 `tests/e2e/run_case.py` / `tests/e2e/repeat_case.py`도 output-dir/attempt 기반 SID isolation을 적용해, same-case concurrent direct run에서 metadata/artifact contention을 덜 만들게 됐습니다.
- latest slice에서는 same isolation trace도 `summary.json`의 `execution_salt`, `repeatability_report.json`의 `observed_execution_salts` / `distinct_sid_count`로 읽을 수 있습니다.
- `orchestrator/support_extract.py`는 packed manifest + matrix/repeatability artifacts에서 reviewable `support_candidate.json`을 뽑는 measured extraction helper입니다.
- latest slice에서는 same `support_candidate.json`도 `build_contract` payload를 같이 담아, review queue가 `build_ready/build_safety`와 generation-path/quality blocker를 같은 candidate surface에서 함께 읽을 수 있게 됐습니다.
- latest slice에서는 same `support_extract.py`가 stale/thin `support_promotion.reasons`만 복사하지 않고 `build_contract`에서 build blocker를 다시 구성하며, `selection_evidence` / `stack_selection` / `name_only_outcome` / `topology_clarity` 같은 open-world policy token도 `promotion_policy_blockers` aggregate로 남기기 시작했습니다.
- latest slice에서는 same `support_review_index.json` / `support_registry_update.json` preview도 `build_ready_bundle_count`, `build_not_ready_bundle_count`, `build_safety_safe_bundle_count`, `build_safety_blocked_bundle_count`, `by_build_ready_blocker`, `by_build_safety_blocker`를 같이 surface합니다. 즉 queue aggregate에서도 buildability와 promotability를 직접 분리해 읽을 수 있습니다.
- latest slice에서는 same local registry apply path도 explicit `generation_path_live_positive_ready=false` 또는 `generation_path_class!=live`, `mechanically_healthy=false`, `promotion_policy_ready=false`, `build_ready=false`, `build_safety_safe=false` accepted entry를 fail-closed 하므로, measured/support queue에서 막힌 candidate가 curated registry에 stale/manual drift로 들어가는 경로가 줄었습니다.
- `run_pipeline.py`의 `performance_summary.json`은 이제 search cache hit/miss, reuse ratio, planned/executed query count, early-stop 여부도 같이 surface합니다.
- `pack.py`의 `request_ir_summary`는 이제 ambiguity/evidence뿐 아니라 `provisional_family`, `primitive_hypotheses`, `runtime_dependency_hypotheses`, `topology_hypotheses`, `scenario_candidates` 집계도 담습니다.
- `pack.py`의 `selection_readiness_summary`는 이제 `scenario_selected_bundles`, `scenario_evidence_backed_bundles`, `by_scenario_topology` 같은 joint-candidate readiness truth도 담습니다.
- `pack.py`의 `runtime_surface_summary`도 이제 `by_seed_strategy`, `by_sidecars_source`, `by_service_env_source`, `by_network_mode_source`, `by_volume_contract_source`, `by_network_contract_source`, `by_poc_entry_source`, `by_poc_cmd_source`, `explicit_sidecar_order_bundles`를 함께 집계합니다. 즉 bounded runtime parity가 어느 source에서 왔는지 top-level aggregate에서도 읽을 수 있습니다.
- latest slice에서는 same `runtime_surface_summary`가 `seed_apply_attempted_bundles`, `seed_apply_completed_bundles`, `seed_files_applied_total`, `seed_mount_target_bundles`, `custom_seed_mount_target_bundles`, `by_seed_mount_target`, `executed_sidecar_bundles`, `executed_sidecar_count`, `by_executed_sidecar_type`도 같이 집계합니다. 또 `runtime_recipe`가 비어 있는 service-level source field뿐 아니라 `run_summary.sidecars/network_mode/sidecar_start_order`도 fallback으로 읽고, recipe-thin bundle의 topology도 actual execution shape에서 bounded fallback으로 복구해 aggregate source/count buckets가 actual execution에 더 가깝게 읽히기 시작했습니다.
- staged synthesis는 이제 generator 내부만의 정보가 아닙니다. `pack.py`는 `bundle.staged_synthesis`, `bundle.staged_recovery`, `staged_synthesis_summary`를 surface하고, single-bundle manifest에도 `staged_recovery_strategy`, `staged_failure_stage`, `staged_failure_stage_reason`를 복사합니다.
- loop/retry는 generator failure metadata의 `failure_stage`를 읽고, PACK 이후에도 같은 stage-aware 정보를 operator summary에서 추적할 수 있습니다.
- `tests/e2e/case_matrix.json`은 current E2E case collection을 eval matrix axes로 canonicalize합니다.
- `tests/e2e/run_case.py` summary는 `case_name`, `matrix_axes`, `search_cache_*`, planned/executed query count, `search_early_stop_triggered`를 같이 노출합니다.
- `tests/e2e/repeat_case.py`는 per-attempt cache observation과 `matrix_axes`를 repeatability report에 싣고, `tests/e2e/matrix_report.py`는 이를 axis별 `matrix_report.json`으로 rollup합니다.
- latest slice에서는 same repeatability/matrix artifacts가 `observed_artifact_quality_bands`, `observed_qualitative_tiers`, `quality_observations.by_qualitative_tier`까지 같이 남겨, measured lane에서도 `thin_fallback_demo`와 `bounded_sidecar_parity_success`를 구분해 읽을 수 있습니다.
- `tests/e2e/repeat_case.py`는 성공 summary가 있으면 `orchestrator/support_extract.py`를 통해 `support_candidate.json`도 함께 남깁니다. 이 artifact는 `support_promotion` internal gate와 external `matrix/repeatability` gate를 함께 기록합니다.
- `tests/e2e/support_review.py`는 여러 measured `support_candidate.json`을 모아 `support_review_index.json`을 만들고, reviewable vs blocked 후보를 blocker/family/topology 기준으로 집계합니다.
- `tests/e2e/support_decide.py`는 수동 reviewer decisions를 `support_review_index.json`에 적용해 `support_registry_update.json` preview를 만듭니다. 이 단계도 아직 measured/manual workflow이며 auto-promotion은 아닙니다.
- `tests/e2e/support_apply.py`는 `support_registry_update.json` preview를 받아 `curated_support_registry.json` local registry로 write/merge합니다. 이건 actual local workflow지만, 여전히 measured/manual apply이며 auto-promotion은 아닙니다.

## Current Residual Owners

- partial-lane / selection control-plane residual은 `TKT-001-*`, `TKT-006-*` owner와 직접 연결된다.
- strict capability-gate fail-closed subclass split(`strict_dynamic_remote_research_unavailable` vs `strict_dynamic_live_llm_unavailable`) 유지도 현재는 `TKT-001-E` residual reading에 포함된다.
- measured gate / summary consistency residual은 `TKT-008-A*`, `TKT-008-B*` owner다.
- curated registry / support workflow residual은 `TKT-009-A*`, `TKT-009-B*` owner다.
- orchestrator 문서는 many artifact surfaces를 설명할 수 있지만, 이것만으로 generalized control-plane closure나 auto-promotion completion을 claim하면 안 된다.

## Completion Review Focus

- `TKT-001`, `TKT-006` completion은 `plan.py` / `run_pipeline.py` / `pack.py`가 selection branch authority와 staged recovery truth를 실제 operator-facing summary까지 일관되게 남기는지부터 본다.
- `TKT-008`, `TKT-009` completion은 `support_extract.py`와 measured/support artifacts가 candidate -> review -> update -> registry current state까지 같은 vocabulary와 precedence를 유지하는지부터 본다.

## Priority Companions

이 문서를 우선순위 판단 관점으로 읽을 때는 아래 문서를 같이 본다.

- current completion priority order: [docs/work_tickets.md](../work_tickets.md)의 `Confirmed Completion Priority Order`
- 잔여 작업량과 practical turn envelope: [docs/work_tickets.md](../work_tickets.md)의 `Estimated Turn Envelope`
- representative evidence와 함께 보는 turn estimate shortcut: [docs/work_tickets.md](../work_tickets.md)의 `Turn Estimate Entry`
- priority companion set / reading order: [docs/work_tickets.md](../work_tickets.md)의 `Priority Companions`, `Priority Reading Order`
- latest positive representative pair의 ticket-form reading: [docs/work_tickets.md](../work_tickets.md)의 `Assessment-To-Ticket Interpretation`
- LLM-response 기준 residual/priority 해석: [docs/work_tickets.md](../work_tickets.md)의 `LLM-Response Capability Overlay`
- current truth / non-claim: [docs/current_state_gap_analysis.md](../current_state_gap_analysis.md), [docs/constraints.md](../constraints.md)
- code/artifact entry: [docs/code/README.md](README.md), [docs/handbook.md](../handbook.md)

## Priority Review Focus

- current completion priority order에서 orchestrator는 `TKT-001`, `TKT-006`, 그리고 후행 `TKT-008`, `TKT-009` handoff를 읽는 primary companion이다.
- 이 문서는 priority source가 아니라, 선택/summary/measured-support registry handoff가 실제 어디서 만들어지는지 좁히는 entrypoint로 읽는다.
- latest positive representative pair의 ticket-form reading도 orchestrator를 `selection -> synthesis -> measured/support handoff` translation layer로 다시 묶는다. canonical 해석은 [docs/work_tickets.md](../work_tickets.md)의 `Assessment-To-Ticket Interpretation`을 따른다.
- 잔여 작업량/turn envelope 해석도 [docs/work_tickets.md](../work_tickets.md)의 `Estimated Turn Envelope`를 같이 따른다.
- turn estimate shortcut도 [docs/work_tickets.md](../work_tickets.md)의 `Turn Estimate Entry`를 같이 따른다.
- LLM-response stricter reading에서도 orchestrator는 strict live-LLM honesty와 positive LLM-shaped handoff를 같은 `TKT-001 -> TKT-006 -> TKT-008/9` 흐름으로 분리해 읽게 만드는 companion이다.
- LLM-response 기준 상세 해석은 [docs/work_tickets.md](../work_tickets.md)의 `LLM-Response Capability Overlay`를 따른다.

## Review Mode Entry

이 문서를 열 때는 아래 mode entry를 먼저 고른다.

- 검증:
  - 이 문서의 `Representative Validation Surface`
- 완료판정:
  - 이 문서의 `Completion Review Focus`
  - [docs/code/README.md](README.md)의 `Completion Review Entry`
- 잔여 구현 검토:
  - 이 문서의 `Current Residual Owners`
  - [docs/code/README.md](README.md)의 `Residual Review Entry`
- 우선순위 판단:
  - 이 문서의 `Priority Review Focus`
  - [docs/work_tickets.md](../work_tickets.md)의 `Priority Companions`
  - [docs/work_tickets.md](../work_tickets.md)의 `Assessment-To-Ticket Interpretation`

## Ticket-First Entry

- `TKT-001`, `TKT-006`을 먼저 볼 때:
  - `orchestrator/plan.py`
  - `orchestrator/run_pipeline.py`
  - `orchestrator/pack.py`
- `TKT-008`을 먼저 볼 때:
  - `orchestrator/pack.py`
  - `orchestrator/support_extract.py`
  - `tests/e2e/repeat_case.py`
  - `tests/e2e/matrix_report.py`
  - latest low-cost rehearsal pair: `foobar-name-only-negative`, `open-redirect-strict-dynamic-no-remote`
- `TKT-009`를 먼저 볼 때:
  - `orchestrator/support_extract.py`
  - `tests/e2e/support_review.py`
  - `tests/e2e/support_decide.py`
  - `tests/e2e/support_apply.py`
  - latest blocked/no-op rehearsal pair: `foobar-name-only-negative`, `open-redirect-strict-dynamic-no-remote`

## Representative Validation Surface

- orchestrator/pack summary and failure-path regression:
  - `tests/test_pack_promotion.py`
  - `tests/test_run_pipeline_failure_resolution.py`
- measured/support extraction regression:
  - `tests/test_repeatability_gate.py`
  - `tests/test_support_extract.py`
  - `tests/e2e/test_case_matrix_rollup.py`
  - `tests/e2e/test_support_workflow.py`
- representative direct workflow:
  - `python tests/e2e/run_case.py --case <CASE_DIR> --mode deterministic`
  - `python tests/e2e/repeat_case.py --case <CASE_DIR> --attempts 2 --mode deterministic --output-dir <OUT_DIR>`
  - low-cost no-Docker policy lanes:
    - `open-redirect-strict-dynamic-no-remote`
    - `open-redirect-strict-dynamic-stub`
    - `foobar-name-only-negative`
  - low-cost measured/support blocked-no-op pair:
    - `foobar-name-only-negative`
    - `open-redirect-strict-dynamic-no-remote`

## Name-Only/Open-World 작업 시 먼저 볼 것

- `plan.py`: 어떤 입력이 `request_ir`와 policy로 들어가는지
- `run_pipeline.py`: 어떤 stage가 fail-closed/partial을 결정하는지
- `pack.py`: 어떤 summary surface가 operator-facing truth가 되는지

## How To Update This Document

- orchestrator entrypoint, output surface, measured/support workflow wiring이 바뀔 때만 갱신한다.
- current rerun truth나 representative verification 결과는 [docs/current_state_gap_analysis.md](../current_state_gap_analysis.md)에 남긴다.
- current non-claim과 운영 전제는 [docs/constraints.md](../constraints.md)에 남긴다.
- phase ordering과 backlog owner는 [docs/final_solution.md](../final_solution.md), [docs/work_tickets.md](../work_tickets.md)로 보낸다.
- ticket-first entrypoint나 representative validation surface가 바뀌면 이 문서의 해당 섹션도 같이 갱신한다.
- completion review focus가 바뀌면 same owner/ticket mapping에 맞춰 이 문서도 같이 갱신한다.
- priority review focus나 priority companion 해석이 바뀌면 [docs/code/README.md](README.md), [docs/work_tickets.md](../work_tickets.md)와 같이 갱신한다.
- LLM-response stricter reading의 orchestrator-side handoff 해석이 바뀌면 [docs/work_tickets.md](../work_tickets.md)의 `LLM-Response Capability Overlay`와 같이 갱신한다.
- latest positive representative pair의 ticket-form 해석이 바뀌면 [docs/work_tickets.md](../work_tickets.md)의 `Assessment-To-Ticket Interpretation`와 같이 갱신한다.
- 잔여 작업량/turn envelope 해석이 바뀌면 [docs/work_tickets.md](../work_tickets.md)의 `Estimated Turn Envelope`와 같이 갱신한다.
- [docs/work_tickets.md](../work_tickets.md)의 `Turn Estimate Entry`가 바뀌면 same shortcut도 같이 갱신한다.
- review mode entry shortcut이 바뀌면 [docs/code/README.md](README.md)와 같이 갱신한다.
- harness command family나 measured/support validation flow가 바뀌면 [tests/e2e/README.md](../../tests/e2e/README.md)와 같이 갱신한다.
