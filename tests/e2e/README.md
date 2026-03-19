# E2E 회귀 하니스

Status: support
Audience: implementation, operator
Source of truth for: case layout, direct E2E harness usage, repeatability/support workflow commands
Not the source of truth for: backlog priority, current-state assessment, policy claims
Last validated against: current E2E harness scripts and measured/support workflow on 2026-03-19

canonical 관계:
- current truth와 latest rerun 해석: [docs/current_state_gap_analysis.md](../docs/current_state_gap_analysis.md)
- current non-claim과 운영 전제: [docs/constraints.md](../docs/constraints.md)
- phase ordering과 backlog owner: [docs/final_solution.md](../docs/final_solution.md), [docs/work_tickets.md](../docs/work_tickets.md)
- phase acceptance와 validation surface 대응: [docs/final_solution.md](../docs/final_solution.md)
- operator quickstart와 artifact map: [docs/handbook.md](../docs/handbook.md)
- subsystem code path 탐색: [docs/code/README.md](../docs/code/README.md)

## Reader Routing

- representative E2E/direct rerun command를 찾으려면 이 문서를 본다.
- ticket priority나 implementation owner를 보려면 [docs/work_tickets.md](../docs/work_tickets.md)를 먼저 본다.
- current rerun 결과 해석이나 current limitation은 [docs/current_state_gap_analysis.md](../docs/current_state_gap_analysis.md), [docs/constraints.md](../docs/constraints.md)를 먼저 본다.
- subsystem code entrypoint는 [docs/code/README.md](../docs/code/README.md)를 먼저 본다.
- operator quickstart, artifact map, troubleshooting은 [docs/handbook.md](../docs/handbook.md)를 먼저 본다.

`tests/e2e/` 폴더에는 전체 파이프라인(`plan → researcher → generator → executor → verifier → reviewer → pack`)
을 그대로 실행해 재현 가능한 회귀 시나리오를 담아둔다. 각 케이스는 `tests/e2e/cases/<slug>/`
하위에 위치하며 다음 파일을 포함한다.

- `requirement.yml`: 선언형 요구 정의. 전체 요구를 직접 작성하거나 `base_requirement.yml`을
  `base_requirement` + `overrides` 방식으로 참조할 수 있다.
- `expectations.json`: 실행 결과(Manifest/Reviewer)에 대한 검증 조건. `compiler_supported` 같은 capability metadata뿐 아니라 `generation_origin`, `dynamicness_verdict`, nested `generation_summary`/`verification_summary` 같은 provenance and quality rollup도 함께 검증할 수 있다.
- `outputs/<sid>/`: (선택) 런너가 남긴 스냅샷. 로컬 반복 시 용량이 부담되면 `--no-snapshot`으로 생략 가능하다.

## 단일 케이스 실행 예시

```bash
python tests/e2e/run_case.py --case tests/e2e/cases/cwe-89-basic --mode deterministic
```

기본적으로 런너는 실패 분석을 돕기 위해 `metadata/<sid>`와 `artifacts/<sid>`를 케이스 폴더로 복사한다.
CI처럼 복사가 불필요한 환경에서는 `--no-snapshot` 플래그를 사용하면 된다.

## Pytest 연동

E2E 실행은 옵트인 방식이다. `VULD_RUN_E2E=1`을 설정하고 Docker 접근 권한을 확보하면
`pytest -m e2e`가 케이스를 실제로 실행한다. 환경 변수가 없으면 테스트가 자동으로 skip되어
기본 스위트 속도를 유지한다.

CI 엔트리 포인트 `ops/ci/run_e2e_tests.sh`는 각 케이스의 필수 파일을 확인한 뒤 `pytest -m e2e`를 호출한다.

반복 재현성 게이트는 별도 opt-in이다.

- `VULD_RUN_E2E_REPEAT=1 pytest -m e2e -k cwe89_basic_repeatability_gate`
- 또는 `bash ops/ci/run_repeatability_gate.sh`
- CI 엔트리포인트에서 함께 돌리려면 `VULD_RUN_E2E=1 VULD_RUN_E2E_REPEAT=1 bash ops/ci/run_e2e_tests.sh`

반복 게이트는 `cwe-89-basic`을 3회 연속 실행하고, 각 시도의 `summary.json`, 마지막 `failure_fingerprint`,
`guard_error_code`, `loop_state` tail을 `repeatability_report.json`으로 집계한다. 현재 repeatability report는
`matrix_axes`, attempt별 `search_cache_*`/`search_executed_query_count`/`search_early_stop_triggered`,
`artifact_quality_band`/`artifact_quality_qualitative_tier`/`oracle_execution_parity`,
aggregate `cache_reuse_observed`, `cache_reuse_consistent`, `executed_query_reduction_observed`도 함께 담는다.

## Ticket Mapping

- `run_case.py`와 `pytest -m e2e` representative rerun은 주로 `TKT-001` ~ `TKT-007`의 direct workflow sanity를 확인한다.
- `repeat_case.py`, `matrix_report.py`, `support_review.py`, `support_decide.py`, `support_apply.py`는 주로 `TKT-008`, `TKT-009` measured/support workflow를 확인한다.
- 이 하니스는 current bounded closure를 regression으로 고정하는 용도이며, `TKT-010` expansion readiness를 단독으로 증명하지는 않는다.

## Validation Companions

하니스 관점에서 이 문서와 같이 봐야 할 companion은 아래와 같다.

- success criteria 5축과 backlog owner 대응: [docs/work_tickets.md](../docs/work_tickets.md)의 `Open-World Completion Axis Map`
- completion companion set: [docs/work_tickets.md](../docs/work_tickets.md)의 `Completion Companions`
- success criteria 5축의 완료판정 질문과 최소 근거: [docs/work_tickets.md](../docs/work_tickets.md)의 `Open-World Completion Checklist`
- success criteria 5축의 canonical 완료 검토 순서: [docs/work_tickets.md](../docs/work_tickets.md)의 `Open-World Completion Review Flow`
- success criteria 5축의 canonical 완료판정 reading order: [docs/work_tickets.md](../docs/work_tickets.md)의 `Open-World Completion Reading Order`
- latest confirmed residual의 축별 ticket bundle 분해: [docs/work_tickets.md](../docs/work_tickets.md)의 `Open-World Residual Ticket Breakdown`
- latest confirmed residual의 canonical 구현 검토 순서: [docs/work_tickets.md](../docs/work_tickets.md)의 `Open-World Residual Review Flow`
- latest confirmed residual 검토 문서 순서: [docs/work_tickets.md](../docs/work_tickets.md)의 `Open-World Residual Reading Order`
- residual companion set: [docs/work_tickets.md](../docs/work_tickets.md)의 `Residual Companions`
- review mode별 canonical 시작점: [docs/work_tickets.md](../docs/work_tickets.md)의 `Review Mode Matrix`
- phase acceptance와 validation surface 대응: [docs/final_solution.md](../docs/final_solution.md)
- ticket별 first harness와 reading order: [docs/work_tickets.md](../docs/work_tickets.md)
- code entrypoint와 subsystem owner: [docs/code/README.md](../docs/code/README.md)
- operator artifact map / troubleshooting: [docs/handbook.md](../docs/handbook.md)
- success criteria 5축별 artifact reading hints: [docs/handbook.md](../docs/handbook.md)의 `Open-World Axis Reading Hints`, [docs/code/workspaces.md](../docs/code/workspaces.md)의 `Open-World Axis Artifact Hints`
- current truth와 observed rerun evidence: [docs/current_state_gap_analysis.md](../docs/current_state_gap_analysis.md)
- 질문 기반 routing: [docs/work_tickets.md](../docs/work_tickets.md)의 `Validation Question Routing`
- residual 질문 기반 routing: [docs/work_tickets.md](../docs/work_tickets.md)의 `Residual Question Routing`

## Completion Companions

하니스/완료판정 관점에서 이 문서와 같이 봐야 할 companion은 아래와 같다.

- completion companion set: [docs/work_tickets.md](../docs/work_tickets.md)의 `Completion Companions`
- axis map / close criteria / canonical review order: [docs/work_tickets.md](../docs/work_tickets.md)의 `Open-World Completion Axis Map`, `Open-World Completion Checklist`, `Open-World Completion Review Flow`
- canonical completion reading order: [docs/work_tickets.md](../docs/work_tickets.md)의 `Open-World Completion Reading Order`
- phase acceptance map: [docs/final_solution.md](../docs/final_solution.md)의 `Acceptance-To-Validation Translation`
- code entrypoint: [docs/code/README.md](../docs/code/README.md)
- artifact reading / troubleshooting: [docs/handbook.md](../docs/handbook.md)
- current truth / non-claim: [docs/current_state_gap_analysis.md](../docs/current_state_gap_analysis.md), [docs/constraints.md](../docs/constraints.md)

## Residual Companions

하니스/잔여 구현 검토 관점에서 이 문서와 같이 봐야 할 companion은 아래와 같다.

- residual bucket / ticket bundle: [docs/work_tickets.md](../docs/work_tickets.md)의 `Open-World Residual Ticket Breakdown`
- residual close criteria: [docs/work_tickets.md](../docs/work_tickets.md)의 `Open-World Completion Checklist`
- residual review / reading order: [docs/work_tickets.md](../docs/work_tickets.md)의 `Open-World Residual Review Flow`, `Open-World Residual Reading Order`
- phase acceptance map: [docs/final_solution.md](../docs/final_solution.md)의 `Acceptance-To-Validation Translation`
- code entrypoint / residual focus: [docs/code/README.md](../docs/code/README.md)
- artifact reading / troubleshooting: [docs/handbook.md](../docs/handbook.md)
- current truth / non-claim: [docs/current_state_gap_analysis.md](../docs/current_state_gap_analysis.md), [docs/constraints.md](../docs/constraints.md)

## Review Mode Entry

하니스 문서를 열 때는 아래 mode entry를 먼저 고른다.

- 검증:
  - [docs/work_tickets.md](../docs/work_tickets.md)의 `Review Mode Matrix`
  - 이 문서의 `Validation Reading Order`
- 완료판정:
  - [docs/work_tickets.md](../docs/work_tickets.md)의 `Review Mode Matrix`
  - 이 문서의 `Completion Companions`
- 잔여 구현 검토:
  - [docs/work_tickets.md](../docs/work_tickets.md)의 `Review Mode Matrix`
  - 이 문서의 `Residual Review Entry`

## Validation Reading Order

이 순서는 [docs/work_tickets.md](../docs/work_tickets.md)의 `Validation Reading Order`를 따른다.

1. [docs/work_tickets.md](../docs/work_tickets.md)의 `Validation Routing`
2. 이 문서의 harness command / case layout / ticket mapping
3. [docs/code/README.md](../docs/code/README.md)와 subsystem docs의 code entrypoint
4. [docs/handbook.md](../docs/handbook.md)의 artifact map / troubleshooting

## Completion Review Entry

하니스 관점에서 완료판정을 검토할 때는 [docs/work_tickets.md](../docs/work_tickets.md)의 `Open-World Completion Review Flow`를 먼저 보고, 이 문서의 harness command / case layout / ticket mapping으로 representative rerun 경로를 고른 뒤 [docs/code/README.md](../docs/code/README.md)와 [docs/handbook.md](../docs/handbook.md)로 내려간다.

## Completion Reading Order

하니스 문서 기준 completion reading order는 아래와 같다.

이 순서는 [docs/work_tickets.md](../docs/work_tickets.md)의 `Open-World Completion Reading Order`를 따른다.

1. [docs/work_tickets.md](../docs/work_tickets.md)의 `Completion Companions`
2. 이 문서의 `Completion Review Entry`
3. [docs/code/README.md](../docs/code/README.md)의 `Completion Review Entry`
4. [docs/handbook.md](../docs/handbook.md)의 `Completion Review Entry`

## Residual Review Entry

하니스 관점에서 current residual을 먼저 검토할 때는 [docs/work_tickets.md](../docs/work_tickets.md)의 `Open-World Residual Ticket Breakdown`을 먼저 보고, 이 문서의 harness command / case layout / ticket mapping으로 representative rerun 경로를 고른 뒤 [docs/code/README.md](../docs/code/README.md)와 [docs/handbook.md](../docs/handbook.md)로 내려간다.
이 순서는 [docs/work_tickets.md](../docs/work_tickets.md)의 `Open-World Residual Reading Order`를 따른다.

## Residual Reading Order

하니스 문서 기준 residual reading order는 아래와 같다.

1. [docs/work_tickets.md](../docs/work_tickets.md)의 `Open-World Residual Reading Order`
2. 이 문서의 `Residual Review Entry`
3. [docs/code/README.md](../docs/code/README.md)의 `Residual Review Entry`
4. [docs/handbook.md](../docs/handbook.md)의 `Residual Review Entry`

반복 게이트 output 디렉터리에는 `matrix_report.json`도 같이 생성된다.

- `matrix_report.json`: `tests/e2e/case_matrix.json`을 authority로 삼아 axis별 `case_count/pass_count/fail_count/repeatability_fail_count`를 집계한 canonical rollup
- latest slice에서는 same `matrix_report.json`이 `quality_observations.by_band/by_qualitative_tier/oracle_high_nonhigh_band_cases`도 같이 집계한다.
- `repeatability_report.json`: 개별 attempt 결과와 cache/repeatability 관찰치를 함께 담는 per-case aggregate
- latest slice에서는 same `repeatability_report.json`도 `observed_artifact_quality_bands`, `observed_qualitative_tiers`, `observed_oracle_execution_parities`, `quality_tier_consistent`를 함께 담는다.
- `summary.json`의 각 bundle entry는 최근 slice 기준으로 executor run summary의 bounded runtime provenance와 일부 oracle execution 결과도 노출한다. 예를 들어 `service_port_source`, `service_entry_source`, `poc_entry`, `poc_entry_source`, `poc_cmd`, `poc_cmd_source`, `base_url_source`, `health_path_source`, `healthchecks`, `healthchecks_source`, `runtime_service_env`, `service_env_source`, `executed_sidecars`, `sidecar_start_order`, `allow_network`, `allow_network_source`, `network_mode_source`, `network_contract`, `seed_strategy`, `seed_files`, `volume_contract`, `seed_apply_attempted`, `seed_apply_completed`, `seed_files_applied_total`, `seed_mount_targets`, `oracle_execution_parity`, `oracle_execution_attempted` 같은 필드를 그대로 읽을 수 있다. latest slice 후 `executed_sidecars`는 `type`, `aliases`, `seed_mount_target`, `seed_files_applied`까지 같이 담는다.
- single-bundle case에서는 top-level `summary.json`도 `service_port`, `service_base_url`, `runtime_service_env`, `allow_network`, `network_mode`, `executed_sidecars`, `seed_apply_*`, `seed_mount_targets`를 직접 노출하므로, 대표 direct run의 핵심 runtime fact를 bundle list를 열지 않고 읽을 수 있다.
- latest slice에서는 same top-level `summary.json`가 `service_port_source`, `base_url_source`, `health_path_source`, `service_env_source`, `allow_network_source`, `network_mode_source`도 함께 노출하므로, value와 provenance를 같은 level에서 읽을 수 있다.
- latest slice에서는 same top-level `summary.json`가 `service_entry_source`, `poc_entry`, `poc_entry_source`, `poc_cmd`, `poc_cmd_source`, `sidecars_source`, `sidecar_start_order`, `sidecar_start_order_source`, `network_contract`, `network_contract_source`, `seed_strategy`, `seed_strategy_source`, `seed_files`, `seed_files_source`, `volume_contract`, `volume_contract_source`도 함께 노출하므로, single-bundle run은 top-level만으로도 runtime value, provenance, contract intent를 더 self-contained하게 읽을 수 있다.
- latest slice에서는 same top-level `summary.json`가 `run_passed`, `verify_pass`, `oracle_execution_parity`, `oracle_execution_attempted`도 single-bundle bundle truth를 fallback으로 읽으므로, runtime fact뿐 아니라 핵심 execution/oracle verdict도 top-level에서 바로 볼 수 있다.
- latest slice에서는 multi-bundle case의 top-level `summary.json`도 `bundle_verdict_rollup`를 노출하므로, `run_passed/verify_pass` count와 `oracle_execution_parity`/`qualitative_tier` 분포뿐 아니라 `by_stage_ceiling`/`by_terminal_failure_class`도 `bundles[]`를 직접 열지 않고 읽을 수 있다.
- latest slice에서는 same multi-bundle case가 uniform planning-only/pre-generation verdict를 가질 때 `run_passed`, `verify_pass`, `stage_ceiling`, `terminal_failure_class`, `oracle_execution_parity`, `oracle_execution_attempted`도 top-level에서 직접 읽을 수 있다.
- latest slice에서는 same mixed multi-bundle case도 `run_passed_rollup`, `verify_pass_rollup`, `stage_ceiling_rollup`, `terminal_failure_class_rollup`, `oracle_execution_parity_rollup`, `oracle_execution_attempted_rollup`를 같이 노출하므로, mixed 상태도 `bundles[]`를 열지 않고 더 직접 읽을 수 있다.
- latest slice에서는 same top-level `summary.json`가 `verdict_authority`도 같이 노출하므로, 각 verdict field가 convenience projection인지 bundle truth canonical input인지도 같이 읽을 수 있다.
- latest slice에서는 same `repeatability_report.json`와 `matrix_report.json`도 `verdict_authority` observation을 담기 시작해, measured gate 쪽에서도 projection mode와 canonical precedence를 같이 읽을 수 있다.
- latest slice에서는 same `repeatability_report.json`가 `measured_gate = {ready, blockers}` preview를 담고, `matrix_report.json`도 `measured_gate_observations`를 집계하며, support extraction은 이를 `measured_gate:*` external blocker로 읽기 시작했다.
- latest slice에서는 same `support_candidate.json`와 `support_review_index.json`도 `verdict_authority` handoff를 담기 시작해, support review/workflow 쪽에서도 projection mode와 canonical precedence를 같이 읽을 수 있다.
- latest slice에서는 same `support_review_index.json`와 `support_registry_update.json` preview도 `measured_gate_ready_bundle_count`, `measured_gate_blocked_bundle_count`, `by_measured_gate_blocker`를 같이 담기 시작해, measured gate blocker 분포도 review/update aggregate에서 직접 읽을 수 있다.
- latest slice에서는 same `support_registry_update.json` preview도 authority aggregate와 `accepted/rejected/pending_by_verdict_authority_mode`를 같이 담기 시작해, registry update rehearsal 단계에서도 authority context를 같이 읽을 수 있다.
- latest slice에서는 same `support_registry_update.json` preview를 actual `curated_support_registry.json` local write/merge workflow로 적용할 수 있게 됐다.
- latest slice에서는 same local registry가 `update_history`, `by_decision`, `by_reviewer`를 보존하고 obvious merge conflict를 reject하기 시작했다.
- latest slice에서는 same existing registry item에 대한 reject decision도 item-level `history`, `last_decision`, `rejected_count`로 반영되기 시작했다.
- latest slice에서는 same previously rejected item이 later accept될 때도 `rejected_count`와 prior history를 preserve하기 시작했다.
- latest slice에서는 same sparse accepted/rejected update도 prior `source_artifacts`는 유지하면서 current support-status split은 reviewable semantics로 채우기 시작했다.
- latest slice에서는 same sparse older local registry item도 `history`와 last event를 읽어 current lifecycle/status/provenance schema로 normalize하기 시작했고, top-level `schema_upgraded_item_count`, `by_schema_upgrade_reason`, item-level `schema_upgrade_reasons`로 same bounded schema evolution도 바로 읽을 수 있게 됐다.
- latest slice에서는 same sparse older `update_history` entry도 current update schema로 normalize하기 시작했고, top-level `schema_upgraded_update_count`와 `by_update_schema_upgrade_reason`로 same lifecycle upgrade도 바로 읽을 수 있게 됐다.
- latest slice에서는 same sparse older `decision_history` event도 current decision schema로 normalize하기 시작했고, top-level `schema_upgraded_decision_event_count`와 `by_decision_schema_upgrade_reason`로 same lifecycle upgrade도 바로 읽을 수 있게 됐다.
- latest slice에서는 same local registry maintenance 상태도 top-level `schema_status` token으로 `normalized` vs `legacy_*_present` 상태를 바로 읽을 수 있게 됐다.
- latest slice에서는 same item/update/decision record도 `schema_status=normalized|legacy_upgraded`를 직접 가져, nested record를 열었을 때도 maintenance 상태를 바로 읽을 수 있게 됐다.
- latest slice에서는 same local registry item도 `review_status`를 직접 갖고, top-level `by_review_status` aggregate도 같이 담기 시작했다.
- latest slice에서는 same local registry item도 latest `source_artifacts`를 직접 보존하고, top-level `items_with_source_artifacts_count`도 같이 담기 시작했다.
- latest slice에서는 same support workflow도 blocker를 `mechanical` vs `promotion_policy` class로 나눠 surface하고, candidate `mechanically_healthy` / `promotion_policy_ready`, review/update aggregate `mechanically_*` / `promotion_policy_*` count, `by_mechanical_blocker` / `by_promotion_policy_blocker`도 같이 담기 시작했다.
- latest slice에서는 same support workflow도 `support_status` / `by_support_status`를 같이 담기 시작해, current promotion state를 token으로 더 직접 읽을 수 있게 됐다.
- latest slice에서는 same `curated_support_registry.json` local registry도 item-level `support_status`, `mechanically_healthy`, `promotion_policy_ready`와 top-level `by_support_status`, `mechanically_*_item_count`, `promotion_policy_*_item_count`를 같이 담기 시작했다.
- latest slice에서는 same local registry `last_update` / `update_history`도 support-status split과 mechanical-policy aggregate를 같이 담기 시작했다.
- latest slice에서는 same `support_registry_update.json` preview와 local registry `last_update`도 `accepted/rejected/pending_by_support_status`를 같이 담기 시작했다.
- latest slice에서는 `run_case.py`와 `repeat_case.py`가 output-dir/attempt 기반 SID salt를 쓰기 시작해, 같은 case를 병렬로 돌릴 때 metadata/artifact contention을 덜 만들게 됐다.
- latest slice에서는 same isolation trace도 `summary.json`의 `execution_salt`, `repeatability_report.json`의 `observed_execution_salts` / `distinct_sid_count`로 같이 읽을 수 있다.
- same `summary.json`의 `artifact_quality`와 `artifact_quality_summary`는 최근 slice 기준으로 `qualitative_tier`, `qualitative_review`, `by_qualitative_tier`, `oracle_high_nonhigh_band_bundles`도 함께 노출한다. 즉 executed oracle closure와 thin fallback demo/native-or-sidecar quality tier를 분리해서 읽을 수 있다.
- `support_candidate.json`: packed manifest와 `matrix_report`/`repeatability_report`를 결합해 만든 reviewable support candidate package. `support_promotion` internal gate와 external matrix/repeatability gate를 같이 기록한다.

여러 measured run의 support candidate를 review queue로 묶으려면:

```bash
python tests/e2e/support_review.py /tmp/run-a /tmp/run-b --output /tmp/support_review_index.json
```

- `support_review_index.json`: 여러 `support_candidate.json`을 모아 `review_queue`, `blocked_queue`, `by_blocker`, `by_family`, `by_topology`를 집계한 measured review index

review queue에 대해 수동 결정을 적용하려면:

```bash
python tests/e2e/support_decide.py \
  --review-index /tmp/support_review_index.json \
  --decisions /tmp/support_review_decisions.json \
  --output /tmp/support_registry_update.json

python tests/e2e/support_apply.py \
  --registry-update /tmp/support_registry_update.json \
  --output /tmp/curated_support_registry.json
```

- `support_registry_update.json`: reviewer decision(`accept|reject`)을 `support_review_index.json`에 적용한 measured registry update preview
- `curated_support_registry.json`: `support_registry_update.json` preview를 local registry JSON에 적용한 actual write/merge artifact
- representative sidecar support rerun 기준 `support_review_index.json`는 `by_support_status={"blocked_mixed":1}`와 separated `by_mechanical_blocker` / `by_promotion_policy_blocker`를 남기고, empty decision/apply chain은 `accepted/rejected/pending_by_support_status={}` 및 empty local registry `by_support_status={}`로 끝난다.
- latest slice에서는 same `support_review.py -> support_decide.py -> support_apply.py` chain도 synthetic reviewable accept path와 blocked no-op path를 regression으로 고정했고, CLI stdout도 `by_support_status`, `accepted/rejected/pending_by_support_status`, `by_review_status`, `schema_status`, `schema_upgraded_item_count`, `by_schema_upgrade_reason`, `schema_upgraded_update_count`, `by_update_schema_upgrade_reason`, `schema_upgraded_decision_event_count`, `by_decision_schema_upgrade_reason`까지 직접 노출하기 시작했다.
- 결정 파일은 `{"schema_version":"support_review_decisions@0.1","decisions":[...]}` 형식을 사용하며, 각 entry는 `case_name`, `slug`, `decision`, 선택적 `reviewer`, `rationale`를 가진다.

live unknown 게이트도 opt-in이며, Tavily 키를 필수로 강제할 수 있다.

- `VULD_RUN_E2E=1 VULD_E2E_REQUIRE_TAVILY=1 pytest -m e2e -k unknown_cwe_live_tavily_case`
- `ops/ci/run_e2e_tests.sh`는 `VULD_E2E_REQUIRE_TAVILY=1`일 때 env 또는 `config/api_keys.ini`에 Tavily 키가 없으면 바로 실패한다.

## How To Update This Document

- E2E harness command, case layout, measured/support CLI flow가 바뀔 때만 갱신한다.
- current rerun truth나 completeness 평가는 [docs/current_state_gap_analysis.md](../docs/current_state_gap_analysis.md)에 남긴다.
- claim 한계와 Docker/Tavily 같은 prerequisite는 [docs/constraints.md](../docs/constraints.md)에 남긴다.
- ticket owner와 priority는 [docs/work_tickets.md](../docs/work_tickets.md), [docs/final_solution.md](../docs/final_solution.md)로 보낸다.
- validation reading order가 바뀌면 [README.md](../README.md), [docs/code/README.md](../docs/code/README.md), [docs/handbook.md](../docs/handbook.md)와 같이 맞춘다.
- validation companion 관계가 바뀌면 [README.md](../README.md), [docs/code/README.md](../docs/code/README.md), [docs/handbook.md](../docs/handbook.md)와 같이 맞춘다.
- validation question routing이 바뀌면 [docs/work_tickets.md](../docs/work_tickets.md)와 같이 맞춘다.
- completion companion 관계가 바뀌면 [README.md](../README.md), [docs/code/README.md](../docs/code/README.md), [docs/handbook.md](../docs/handbook.md)와 같이 맞춘다.
- residual companion 관계가 바뀌면 [README.md](../README.md), [docs/code/README.md](../docs/code/README.md), [docs/handbook.md](../docs/handbook.md)와 같이 맞춘다.
- residual question routing이 바뀌면 [docs/work_tickets.md](../docs/work_tickets.md)와 같이 맞춘다.
- completion review entrypoint가 바뀌면 [README.md](../README.md), [docs/code/README.md](../docs/code/README.md), [docs/handbook.md](../docs/handbook.md)와 같이 맞춘다.
- completion reading order가 바뀌면 [README.md](../README.md), [docs/code/README.md](../docs/code/README.md), [docs/handbook.md](../docs/handbook.md)와 같이 맞춘다.
- residual review entrypoint가 바뀌면 [README.md](../README.md), [docs/code/README.md](../docs/code/README.md), [docs/handbook.md](../docs/handbook.md)와 같이 맞춘다.
- residual reading order가 바뀌면 [README.md](../README.md), [docs/code/README.md](../docs/code/README.md), [docs/handbook.md](../docs/handbook.md)와 같이 맞춘다.
- review mode entry shortcuts가 바뀌면 [README.md](../README.md), [docs/code/README.md](../docs/code/README.md), [docs/handbook.md](../docs/handbook.md)와 같이 맞춘다.
