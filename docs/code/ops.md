# ops 디렉토리

Status: support
Audience: implementation
Source of truth for: CI/ops entrypoints and operational automation boundaries
Not the source of truth for: roadmap, support-promotion policy, current rerun baseline tables
Last validated against: current repo layout and operational script surface on 2026-03-20

Relevant canonical docs:
- [핸드북](../handbook.md)
- [제약조건](../constraints.md)
- [현재 상태](../current_state_gap_analysis.md)
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

- `ops/ci/pipeline.md`: CI/CD 및 재현성 검증 support spec
- `ops/ci/lib_named_case_env.sh`: named direct/support/matrix wrapper env projection + caseset dispatch helper library
- `ops/ci/lib_named_case_helper_contract.sh`: named-case / preset-case target helper executable gate library
- `ops/ci/lib_case_spec_preset_contract.sh`: preset-builder required/known gate library
- `ops/ci/lib_operator_named_preset_runner.sh`: operator named-preset validate/export/run skeleton library
- `ops/ci/lib_operator_pair_named_preset.sh`: operator direct/support pair named-preset runner library
- `ops/ci/lib_operator_pair_named_preset_defaults.sh`: operator direct/support pair named-preset helper/default resolution library
- `ops/ci/lib_operator_case_defaults.sh`: operator case-slug single/pair/triple/batch default resolution library
- `ops/ci/lib_operator_output_notes.sh`: operator wrapper completion/output note primitive library
- `ops/ci/lib_operator_output_root_notes.sh`: operator wrapper output-root child note library
- `ops/ci/lib_cases_output_roots.sh`: helper chain cases/output-root default resolution library
- `ops/ci/lib_case_expectations.sh`: helper chain expectations auto-discovery library
- `ops/ci/lib_case_chain_entry.sh`: direct/repeatability helper chain entry preflight library
- `ops/ci/lib_case_chain_output_notes.sh`: direct/repeatability helper chain output note library
- `ops/ci/lib_case_command_surface.sh`: direct/repeatability helper chain command assembly library
- `ops/ci/lib_case_chain_paths.sh`: direct/repeatability chain wrapper path/entry helper library
- `ops/ci/lib_case_chain_runtime_env.sh`: direct/repeatability chain wrapper shared runtime-env library
- `ops/ci/lib_case_chain_wrapper_context.sh`: direct/repeatability chain wrapper context helper library
- `ops/ci/lib_case_chain_script_runner.sh`: direct/repeatability chain wrapper script-runner library
- `ops/ci/lib_case_chain_specs_surface.sh`: direct/repeatability spec-runner surface library
- `ops/ci/lib_case_chain_entrypoint.sh`: direct/repeatability chain entrypoint library
- `ops/ci/lib_case_chain_entrypoint_surface.sh`: direct/repeatability chain entrypoint dispatch library
- `ops/ci/lib_case_chain_entrypoint_profile.sh`: direct/repeatability chain entrypoint profile library
- `ops/ci/lib_case_chain_profiled_entrypoint.sh`: direct/repeatability chain profiled-entrypoint library
- `ops/ci/lib_case_chain_standard_entrypoint.sh`: direct/repeatability chain standard-entrypoint library
- `ops/ci/lib_case_chain_standard_entrypoint_dispatch.sh`: direct/repeatability chain standard-entrypoint dispatch library
- `ops/ci/lib_case_chain_profile_runner_dispatch.sh`: direct/repeatability chain profile-runner dispatch library
- `ops/ci/lib_case_chain_profile_forward.sh`: direct/repeatability chain profile-forward library
- `ops/ci/lib_case_chain_fixed_profile.sh`: direct/repeatability chain fixed-profile library
- `ops/ci/lib_case_chain_target_forward.sh`: direct/repeatability chain target-forward library
- `ops/ci/lib_case_chain_standard_script_main.sh`: direct/repeatability chain standard-script-main library
- `ops/ci/lib_case_chain_standard_script_entrypoint.sh`: direct/repeatability chain standard-script-entrypoint library
- `ops/ci/lib_case_chain_fixed_profile_shortcuts.sh`: direct/repeatability chain fixed-profile-shortcuts library
- `ops/ci/lib_case_chain_named_profile_shortcuts.sh`: direct/repeatability chain named-profile-shortcuts library
- `ops/ci/lib_case_chain_standard_profile_dispatch.sh`: direct/repeatability chain standard-profile-dispatch library
- `ops/ci/lib_case_chain_standard_profile_surface.sh`: direct/repeatability chain standard-profile-surface library
- `ops/ci/lib_case_chain_profile_target_forward.sh`: direct/repeatability chain profile-target-forward library
- `ops/ci/lib_case_chain_profile_entrypoint.sh`: direct/repeatability chain profile-entrypoint compatibility library
- `ops/ci/lib_case_chain_entrypoint_compat.sh`: direct/repeatability chain entrypoint compatibility library
- `ops/ci/lib_case_chain_main_script.sh`: direct/repeatability chain main-script dispatch library
- `ops/ci/lib_case_chain_script_entry_compat.sh`: direct/repeatability chain script-entry compatibility library
- `ops/ci/lib_case_chain_standard_script_entry.sh`: direct/repeatability chain standard script-entry dispatch library
- `ops/ci/lib_case_chain_standard_script_entry_dispatch.sh`: direct/repeatability chain standard script-entry dispatch helper
- `ops/ci/lib_repeatability_chain_runtime_env.sh`: repeatability chain wrapper runtime-env/default library
- `ops/ci/lib_case_spec_resolution.sh`: helper chain case-spec split/path/alias validation, case-context capture, output-name/safe-slug resolution, named output-context export library
- `ops/ci/lib_repeatability_report_failures.sh`: repeatability report Docker failure classification + permission-marker library
- `ops/ci/lib_repeatability_case_failure.sh`: repeatability case-failure action resolution library
- `ops/ci/lib_repeatability_case_runtime.sh`: repeatability case runtime/context library
- `ops/ci/lib_repeatability_case_runner.sh`: repeatability case runner library
- `ops/ci/lib_repeatability_specs_runner.sh`: repeatability specs runner library
- `ops/ci/lib_direct_case_runtime.sh`: direct case runtime/context library
- `ops/ci/lib_direct_case_runner.sh`: direct case runner library
- `ops/ci/lib_case_runtime_context.sh`: direct/repeatability case runtime context primitive library
- `ops/ci/lib_operator_cases_output_roots.sh`: operator pair wrapper cases/output-root default resolution library
- `ops/ci/lib_operator_direct_named_preset.sh`: direct operator named-preset validate/export/run library
- `ops/ci/lib_operator_direct_case_check.sh`: positive-direct / low-cost direct case-check skeleton library
- `ops/ci/lib_operator_pair_case_check.sh`: direct/support pair case-check skeleton library
- `ops/ci/lib_operator_support_named_preset.sh`: support operator named-preset validate/export/run library
- `ops/ci/lib_operator_support_pair_check.sh`: positive-pair / blocked-noop support pair-check skeleton library
- `ops/ci/lib_operator_runtime_sequence.sh`: baseline runtime-surface + sequence invocation library
- `ops/ci/lib_operator_pair_runtime_baseline.sh`: two-step runtime baseline wrapper library
- `ops/ci/lib_operator_pair_runtime_baseline_defaults.sh`: support/docker-positive pair baseline helper/default resolution library
- `ops/ci/lib_operator_helper_defaults.sh`: shared helper-default single/batch resolution primitive library
- `ops/ci/lib_operator_matrix_case_pair.sh`: planning-only matrix pair default/override argument library
- `ops/ci/lib_operator_matrix_baseline_defaults.sh`: measured/no-docker matrix helper/default resolution library
- `ops/ci/lib_operator_matrix_baseline_sequence.sh`: matrix baseline env export + runtime-surface + sequence invocation library
- `ops/ci/lib_operator_current_baseline_defaults.sh`: current baseline helper/default resolution library
- `ops/ci/lib_operator_current_baseline_sequence.sh`: current baseline child-surface forwarding + sequence invocation library
- `ops/ci/lib_operator_sequence_helper_contract.sh`: operator baseline sequence-helper gate + invocation library
- `ops/ci/lib_operator_export_helper_contract.sh`: operator export-helper function gate + invocation library
- `ops/ci/lib_operator_named_case_env.sh`: operator direct/support wrapper env projection helper library
- `ops/ci/lib_operator_named_preset_helpers.sh`: operator preset/named/leaf helper executable gate library
- `ops/ci/lib_operator_baseline_matrix_env.sh`: measured/no-docker matrix baseline env projection helper library
- `ops/ci/lib_operator_retry_env.sh`: top-level operator baseline retry + permission surface env projection helper library
- `ops/ci/lib_repeatability_chain_env.sh`: support/matrix helper repeat-chain env projection helper library
- `ops/ci/lib_repeatability_helper_contract.sh`: support/matrix helper repeat-helper executable gate library
- `ops/ci/lib_support_review_runner.sh`: support-review helper invoke/env/run-dir skeleton library
- `ops/ci/lib_support_review_env.sh`: support review helper env projection helper library
- `ops/ci/lib_support_review_output_surface.sh`: support review helper prefixed output-name + resolved path surface library
- `ops/ci/lib_support_review_output_defaults.sh`: support review helper prefix-aware output-name single/batch default resolution library
- `ops/ci/lib_support_review_helper_contract.sh`: support review helper executable gate / decisions-file materialization library
- `ops/ci/lib_support_review_output_notes.sh`: support review helper completion/output note library
- `ops/ci/lib_support_review_run_dirs.sh`: support review helper run-directory validation library
- `ops/ci/lib_support_review_outputs.sh`: support review helper single/batch output-path resolution library
- `ops/ci/lib_permission_artifact_summary.sh`: support/matrix helper family machine-readable permission summary writer library
- `ops/ci/lib_repeatability_permission_artifacts.sh`: support/matrix helper family permission-artifact scan/note helper library
- `ops/ci/lib_repeatability_postprocess.sh`: support/matrix helper family post-repeat run-dir load + permission note/summary helper library
- `ops/ci/lib_repeatability_chain_runner.sh`: support/matrix helper family repeat-helper run + postprocess skeleton library
- `ops/ci/lib_case_spec_presets.sh`: representative named pair/triple preset helper library
- `ops/ci/run_current_operator_baseline.sh`: no-docker baseline + measured baseline + support baseline + docker-positive baseline + helper regression bundle helper
- `ops/ci/run_helper_sequence.sh`: reusable ordered helper-bundle executor
- `ops/ci/run_ops_helper_contract_regression.sh`: current ops helper contract pytest bundle helper
- `ops/ci/run_support_review_chain.sh`: arbitrary support review/update/apply helper
- `ops/ci/run_repeatability_chain.sh`: arbitrary repeat_case helper
- `ops/ci/run_named_case_set.sh`: generic named-case wrapper executor
- `ops/ci/run_named_preset_case_set.sh`: preset-driven named-case wrapper helper
- `ops/ci/run_named_matrix_case_set.sh`: named matrix-case wrapper helper
- `ops/ci/run_named_support_case_set.sh`: named support-case wrapper helper
- `ops/ci/run_named_direct_case_set.sh`: named direct-case wrapper helper
- `ops/ci/run_support_workflow_chain.sh`: arbitrary repeat/review/decide/apply support workflow helper
- `ops/ci/run_repeatability_matrix_check.sh`: repeatability + matrix_report rollup helper
- `ops/ci/run_measured_gate_operator_baseline.sh`: planning-only matrix preview + positive pair promotion check bundle helper
- `ops/ci/run_no_docker_operator_baseline.sh`: focused preflight + low-cost direct lanes + repeatability matrix preview + blocked/no-op rehearsal bundle helper
- `ops/ci/run_direct_validation_chain.sh`: arbitrary run_case direct validation helper
- `ops/ci/run_support_workflow_operator_baseline.sh`: reviewable accept + blocked/no-op support workflow bundle helper
- `ops/ci/run_reviewable_support_accept_check.sh`: synthetic reviewable accept-path helper
- `ops/ci/run_docker_positive_operator_baseline.sh`: positive direct rerun + promotion-check bundle helper
- `ops/ci/run_case.sh`: PLAN -> optional RESEARCH -> GENERATE -> EXECUTE -> EVALS -> REVIEW -> PACK smoke pipeline
- `ops/ci/run_positive_direct_validation.sh`: Docker-enabled positive direct rerun helper
- `ops/ci/run_low_cost_no_docker_validation.sh`: strict/abstain no-Docker direct rerun helper
- `ops/ci/run_focused_no_docker_regression.sh`: fastest policy/honesty/measured-support pytest preflight helper
- `ops/ci/run_blocked_noop_support_check.sh`: planning-only blocked/no-op repeat/support review/apply helper
- `ops/ci/run_positive_pair_promotion_check.sh`: positive representative pair repeat/support review helper
- `ops/ci/run_base_example.sh`: base requirement smoke helper, optional mode/override seam 포함
- `ops/ci/run_base_examples.sh`: legacy plural alias, base helper forwarding wrapper
- `ops/ci/run_custom_vuln_example.sh`: custom vuln-id requirement synthesis + `run_case.sh` wrapper, base-requirement/runner override seam 포함
- `ops/ci/smoke_regression.sh`: 기본 회귀 실행 시나리오, fake docker/flow seam 포함
- `ops/observability/dashboard_spec.md`: KPI/observability dashboard spec

## 현재 운영 경계

- `ops/ci/*`는 core pipeline의 표준 `metadata/<SID>` / `artifacts/<SID>` surface를 소비한다.
- `tests/e2e/repeat_case.py`, `support_review.py`, `support_decide.py`, `support_apply.py`는 현재 measured/manual workflow이며 `ops/ci/*`의 canonical auto-promotion path는 아니다.
- 따라서 local registry write/merge workflow가 존재해도 현재 운영 자동화는 `support_registry_update.json -> curated_support_registry.json` chain을 CI default path로 읽지 않는다.
- latest low-cost no-Docker rehearsal pair(`foobar-name-only-negative`, `open-redirect-strict-dynamic-no-remote`)는 current blocked/no-op policy regression을 확인하는 수동 operator workflow이며, CI default acceptance path가 아니다.

## 데이터 계약 / 출력

- CI 스크립트는 각 단계의 표준 출력과 산출물(`metadata/`, `artifacts/`)을 그대로 이용하며, 실패 시 종료 코드를 전파한다.
- `ops/ci/run_ops_helper_contract_regression.sh`는 `VULD_OPS_HELPER_PYTEST_BIN`, `VULD_OPS_HELPER_TEST_GLOB`, `VULD_OPS_HELPER_PRINT_BUNDLE` seam을 지원해 current `tests/test_ops_ci_*.py` helper regression bundle 전체나 custom bundle을 fake pytest로 검증할 수 있고, [tests/test_ops_ci_helper_contract_regression.py](/home/ysw/vulDocker/tests/test_ops_ci_helper_contract_regression.py) 가 actual glob set forwarding과 no-match failure를 고정한다.
- `ops/ci/run_current_operator_baseline.sh`는 `VULD_CURRENT_BASELINE_SEQUENCE_HELPER`, `VULD_CURRENT_BASELINE_NO_DOCKER_HELPER`, `VULD_CURRENT_BASELINE_MEASURED_HELPER`, `VULD_CURRENT_BASELINE_SUPPORT_HELPER`, `VULD_CURRENT_BASELINE_DOCKER_POSITIVE_HELPER`, `VULD_CURRENT_BASELINE_HELPER_REGRESSION` seam을 지원해 current operator baseline bundle을 fake helper로 검증할 수 있고, latest slice에서는 `run_helper_sequence.sh`를 재사용한다.
- `ops/ci/run_helper_sequence.sh`는 ordered helper-bundle contract를 제공하며, label + helper + optional args chain을 공통 실행하는 fake helper regression surface를 가진다.
- `ops/ci/run_*.sh`와 `ops/ci/smoke_regression.sh`는 executable bit를 유지해야 하며, `tests/test_ops_ci_script_permissions.py`가 이를 regression으로 고정한다.
- `ops/ci/run_repeatability_chain.sh`는 `VULD_REPEAT_CHAIN_PYTHON_BIN`, `VULD_REPEAT_CHAIN_CASES_ROOT`, `VULD_REPEAT_CHAIN_OUTPUT_ROOT`, `VULD_REPEAT_CHAIN_MODE`, `VULD_REPEAT_CHAIN_ATTEMPTS`, `VULD_REPEAT_CHAIN_NO_SNAPSHOT`, `VULD_REPEAT_CHAIN_ALLOW_FAILURE_WITH_REPORT`, `VULD_REPEAT_CHAIN_DOCKER_RETRY_COUNT`, `VULD_REPEAT_CHAIN_DOCKER_RETRY_DELAY_SEC`, `VULD_REPEAT_CHAIN_RUN_DIRS_FILE`, `VULD_REPEAT_CHAIN_OUTPUT_PREFIX`, `VULD_REPEAT_CHAIN_LOG_PREFIX`, `VULD_REPEAT_CHAIN_REPORT_NAME` seam을 지원해 arbitrary `repeat_case.py` command family를 fake python으로 검증할 수 있다.
- `ops/ci/lib_case_expectations.sh`는 direct/repeatability helper family가 공유하는 default `expectations.json` auto-discovery와 `--expectations` argv append를 공통화하고, [tests/test_ops_ci_case_expectations.py](/home/ysw/vulDocker/tests/test_ops_ci_case_expectations.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_chain_entry.sh`는 direct/repeatability helper family가 공유하는 usage check, output-root prep, entry preflight surface를 공통화하고, [tests/test_ops_ci_case_chain_entry.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_entry.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_chain_output_notes.sh`는 direct/repeatability helper family가 공유하는 case-output log, run-dirs file write, completion note surface를 공통화하고, [tests/test_ops_ci_case_chain_output_notes.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_output_notes.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_command_surface.sh`는 direct/repeatability helper family가 공유하는 `run_case.py` / `repeat_case.py` argv assembly, expectations append, `--no-snapshot` surface를 공통화하고, [tests/test_ops_ci_case_command_surface.py](/home/ysw/vulDocker/tests/test_ops_ci_case_command_surface.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_chain_paths.sh`는 direct/repeatability chain wrapper family가 공유하는 `cases/output-root resolve + usage/output-root prep` surface를 공통화하고, [tests/test_ops_ci_case_chain_paths.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_paths.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_chain_runtime_env.sh`는 direct/repeatability chain wrapper family가 공유하는 `PYTHON_BIN/MODE/NO_SNAPSHOT` runtime-env surface를 공통화하고, [tests/test_ops_ci_case_chain_runtime_env.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_runtime_env.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_chain_wrapper_context.sh`는 direct/repeatability chain wrapper family가 공유하는 `paths + runtime-env` wrapper-context surface를 공통화하고, [tests/test_ops_ci_case_chain_wrapper_context.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_wrapper_context.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_chain_script_runner.sh`는 direct/repeatability top-level wrapper family가 공유하는 `wrapper context 준비 + chain runner invoke` surface를 공통화하고, [tests/test_ops_ci_case_chain_script_runner.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_script_runner.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_chain_specs_surface.sh`는 direct/repeatability spec-runner family가 공유하는 `runner_prefix/runner_suffix + case_specs_run_with_contexts(...)` surface를 공통화하고, [tests/test_ops_ci_case_chain_specs_surface.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_specs_surface.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_chain_entrypoint.sh`는 direct/repeatability top-level script family가 공유하는 `entrypoint -> script runner` surface를 공통화하고, [tests/test_ops_ci_case_chain_entrypoint.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_entrypoint.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_chain_entrypoint_surface.sh`는 direct/repeatability top-level script family가 공유하는 `script_dir -> repo_root -> script runner dispatch` surface를 공통화하고, [tests/test_ops_ci_case_chain_entrypoint_surface.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_entrypoint_surface.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_chain_entrypoint_profile.sh`는 direct/repeatability top-level script family가 공유하는 `profile defaults -> entrypoint surface`를 공통화하고, [tests/test_ops_ci_case_chain_entrypoint_profile.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_entrypoint_profile.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_chain_profiled_entrypoint.sh`는 direct/repeatability top-level script family가 공유하는 `profile resolve -> entrypoint dispatch` surface를 공통화하고, [tests/test_ops_ci_case_chain_profiled_entrypoint.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_profiled_entrypoint.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_chain_standard_entrypoint.sh`는 direct/repeatability top-level script family가 공유하는 standard entrypoint dispatch surface를 공통화하고, [tests/test_ops_ci_case_chain_standard_entrypoint.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_standard_entrypoint.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_chain_standard_entrypoint_dispatch.sh`는 direct/repeatability top-level script family가 공유하는 `profile -> runner function` dispatch surface를 공통화하고, [tests/test_ops_ci_case_chain_standard_entrypoint_dispatch.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_standard_entrypoint_dispatch.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_chain_profile_runner_dispatch.sh`는 direct/repeatability top-level script family가 공유하는 shared `resolver -> runner invoke` surface를 공통화하고, [tests/test_ops_ci_case_chain_profile_runner_dispatch.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_profile_runner_dispatch.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_chain_profile_forward.sh`는 direct/repeatability top-level script family가 공유하는 shared `profile-name forward` surface를 공통화하고, [tests/test_ops_ci_case_chain_profile_forward.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_profile_forward.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_chain_fixed_profile.sh`는 direct/repeatability top-level script family가 공유하는 shared `fixed-profile` surface를 공통화하고, [tests/test_ops_ci_case_chain_fixed_profile.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_fixed_profile.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_chain_target_forward.sh`는 direct/repeatability top-level helper family가 공유하는 shared `target forward` surface를 공통화하고, [tests/test_ops_ci_case_chain_target_forward.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_target_forward.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_chain_standard_script_main.sh`는 direct/repeatability top-level script family가 공유하는 shared `standard script main` surface를 공통화하고, [tests/test_ops_ci_case_chain_standard_script_main.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_standard_script_main.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_chain_standard_script_entrypoint.sh`는 direct/repeatability top-level script family가 공유하는 shared `standard script entrypoint` surface를 공통화하고, [tests/test_ops_ci_case_chain_standard_script_entrypoint.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_standard_script_entrypoint.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_chain_fixed_profile_shortcuts.sh`는 direct/repeatability shortcut wrapper family가 공유하는 shared `fixed-profile shortcuts` surface를 공통화하고, [tests/test_ops_ci_case_chain_fixed_profile_shortcuts.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_fixed_profile_shortcuts.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_chain_named_profile_shortcuts.sh`는 direct/repeatability shortcut wrapper family가 공유하는 shared `named-profile shortcuts` surface를 공통화하고, [tests/test_ops_ci_case_chain_named_profile_shortcuts.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_named_profile_shortcuts.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_chain_standard_profile_dispatch.sh`는 direct/repeatability standard wrapper family가 공유하는 shared `standard profile dispatch` surface를 공통화하고, [tests/test_ops_ci_case_chain_standard_profile_dispatch.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_standard_profile_dispatch.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_chain_standard_profile_surface.sh`는 direct/repeatability standard wrapper family가 공유하는 shared `standard profile surface`를 공통화하고, [tests/test_ops_ci_case_chain_standard_profile_surface.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_standard_profile_surface.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_chain_profile_target_forward.sh`는 direct/repeatability profile wrapper family가 공유하는 shared `profile target forward` surface를 공통화하고, [tests/test_ops_ci_case_chain_profile_target_forward.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_profile_target_forward.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_chain_profile_entrypoint.sh`는 direct/repeatability top-level script family가 공유하는 `profile -> standard entrypoint` compatibility surface를 공통화하고, [tests/test_ops_ci_case_chain_profile_entrypoint.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_profile_entrypoint.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_chain_entrypoint_compat.sh`는 direct/repeatability top-level script family가 공유하는 `named/direct/repeatability entrypoint compatibility` surface를 공통화하고, [tests/test_ops_ci_case_chain_entrypoint_compat.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_entrypoint_compat.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_chain_main_script.sh`는 direct/repeatability top-level script family가 공유하는 `profile + script path -> main dispatch` surface를 공통화하고, [tests/test_ops_ci_case_chain_main_script.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_main_script.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_chain_script_entry_compat.sh`는 direct/repeatability top-level script family가 공유하는 `named/direct/repeatability script entry compatibility` surface를 공통화하고, [tests/test_ops_ci_case_chain_script_entry_compat.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_script_entry_compat.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_chain_standard_script_entry.sh`는 direct/repeatability top-level script family가 공유하는 `standard script-entry dispatch` surface를 공통화하고, [tests/test_ops_ci_case_chain_standard_script_entry.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_standard_script_entry.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_chain_standard_script_entry_dispatch.sh`는 direct/repeatability top-level script family가 공유하는 `profile -> script-entry runner function` dispatch surface를 공통화하고, [tests/test_ops_ci_case_chain_standard_script_entry_dispatch.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_standard_script_entry_dispatch.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_repeatability_chain_runtime_env.sh`는 repeatability chain wrapper가 공유하는 `ATTEMPTS/ALLOW_FAILURE_WITH_REPORT/RUN_DIRS_FILE/OUTPUT_PREFIX/LOG_PREFIX/REPORT_NAME/DOCKER_RETRY_* / PERMISSION_ARTIFACT_NAME` env-default surface를 공통화하고, [tests/test_ops_ci_repeatability_chain_runtime_env.py](/home/ysw/vulDocker/tests/test_ops_ci_repeatability_chain_runtime_env.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_spec_resolution.sh`는 direct/repeatability helper family가 공유하는 `case=alias` split, case-dir path resolution, alias/path safety validation, case-context capture, resolved output-name/safe-slug resolution, named output-context export surface를 공통화하고, [tests/test_ops_ci_case_spec_resolution.py](/home/ysw/vulDocker/tests/test_ops_ci_case_spec_resolution.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_repeatability_report_failures.sh`는 direct/repeatability helper family가 공유하는 repeatability report Docker failure classification, retry gate input, permission-marker writer surface를 공통화하고, [tests/test_ops_ci_repeatability_report_failures.py](/home/ysw/vulDocker/tests/test_ops_ci_repeatability_report_failures.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_repeatability_case_failure.sh`는 direct/repeatability helper family가 공유하는 repeatability case-failure action resolution, retry/continue/fail routing, permission-marker-aware continue surface를 공통화하고, [tests/test_ops_ci_repeatability_case_failure.py](/home/ysw/vulDocker/tests/test_ops_ci_repeatability_case_failure.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_repeatability_case_runtime.sh`는 direct/repeatability helper family가 공유하는 repeatability case context hydration, report-path resolution, run-dir append, `repeat_case.py` argv assembly surface를 공통화하고, [tests/test_ops_ci_repeatability_case_runtime.py](/home/ysw/vulDocker/tests/test_ops_ci_repeatability_case_runtime.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_repeatability_case_runner.sh`는 direct/repeatability helper family가 공유하는 repeatability per-case runtime reuse, retry/continue branching, output note emission surface를 공통화하고, [tests/test_ops_ci_repeatability_case_runner.py](/home/ysw/vulDocker/tests/test_ops_ci_repeatability_case_runner.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_repeatability_specs_runner.sh`는 direct/repeatability helper family가 공유하는 repeatability spec-loop runner, run-dirs file write, completion note surface를 공통화하고, [tests/test_ops_ci_repeatability_specs_runner.py](/home/ysw/vulDocker/tests/test_ops_ci_repeatability_specs_runner.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_runtime_context.sh`는 direct/repeatability helper family가 공유하는 resolved-output context capture와 repeat report-path append primitive를 공통화하고, [tests/test_ops_ci_case_runtime_context.py](/home/ysw/vulDocker/tests/test_ops_ci_case_runtime_context.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_direct_case_runtime.sh`는 direct/repeatability helper family가 공유하는 direct case context hydration, output-dir resolution, `run_case.py` argv assembly surface를 공통화하고, [tests/test_ops_ci_direct_case_runtime.py](/home/ysw/vulDocker/tests/test_ops_ci_direct_case_runtime.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_direct_case_runner.sh`는 direct/repeatability helper family가 공유하는 direct case runtime reuse, output note emission, `run_case.py` command invoke surface를 공통화하고, [tests/test_ops_ci_direct_case_runner.py](/home/ysw/vulDocker/tests/test_ops_ci_direct_case_runner.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_named_case_env.sh`는 named direct/support/matrix wrapper의 target-env projection과 `named_caseset_dispatch(...)` 공통부를 공통화한다.
- `ops/ci/lib_named_case_helper_contract.sh`는 `run_named_case_set.sh` / `run_named_preset_case_set.sh`의 target-helper executable gate를 공통화하고, [tests/test_ops_ci_named_case_helper_contract.py](/home/ysw/vulDocker/tests/test_ops_ci_named_case_helper_contract.py) 가 same helper contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_spec_preset_contract.sh`는 `run_named_preset_case_set.sh`의 preset-builder required/known gate를 공통화하고, [tests/test_ops_ci_case_spec_preset_contract.py](/home/ysw/vulDocker/tests/test_ops_ci_case_spec_preset_contract.py) 가 same helper contract를 direct regression으로 고정한다.
- `ops/ci/lib_operator_named_case_env.sh`는 positive direct / low-cost / promotion / blocked operator wrapper의 target-env projection을 공통화하고, [tests/test_ops_ci_operator_named_case_env.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_named_case_env.py) 가 same mapping을 direct regression으로 고정한다.
- `ops/ci/lib_operator_named_preset_helpers.sh`는 pair/triple operator wrapper의 preset helper, named wrapper helper, leaf helper executable gate를 공통화하고, [tests/test_ops_ci_operator_named_preset_helpers.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_named_preset_helpers.py) 가 preset override / named override / missing preset failure semantics를 direct regression으로 고정한다.
- `ops/ci/lib_operator_named_preset_runner.sh`는 direct/support operator pair wrapper의 validate -> env export -> preset helper invoke skeleton을 공통화하고, [tests/test_ops_ci_operator_named_preset_runner.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_named_preset_runner.py) 가 missing export-helper rejection과 preset invocation contract를 direct regression으로 고정한다.
- `ops/ci/lib_operator_pair_named_preset.sh`는 direct/support named-preset thin wrapper가 공유하는 pair-runner primitive를 공통화하고, [tests/test_ops_ci_operator_pair_named_preset.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_pair_named_preset.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_operator_pair_named_preset_defaults.sh`는 direct/support named-preset wrapper가 공유하는 named/preset/leaf helper default resolution을 공통화하고, [tests/test_ops_ci_operator_pair_named_preset_defaults.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_pair_named_preset_defaults.py) 가 same defaults contract를 direct regression으로 고정한다.
- `ops/ci/lib_operator_case_defaults.sh`는 direct/support wrapper family가 공유하는 single/pair/triple/batch case-slug default resolution을 공통화하고, [tests/test_ops_ci_operator_case_defaults.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_case_defaults.py) 가 same defaults contract를 direct regression으로 고정한다.
- `ops/ci/lib_operator_output_notes.sh`는 direct/support wrapper family가 공유하는 completion/output note primitive를 공통화하고, [tests/test_ops_ci_operator_output_notes.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_output_notes.py) 가 same output contract를 direct regression으로 고정한다.
- `ops/ci/lib_operator_output_root_notes.sh`는 direct/support wrapper family가 공유하는 `output_root + child suffix -> completion note` primitive를 공통화하고, [tests/test_ops_ci_operator_output_root_notes.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_output_root_notes.py) 가 same output-root contract를 direct regression으로 고정한다.
- `ops/ci/lib_operator_export_helper_contract.sh`는 named-preset runner와 matrix baseline sequence family가 공유하는 export-helper function gate와 invoke primitive를 공통화하고, [tests/test_ops_ci_operator_export_helper_contract.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_export_helper_contract.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_operator_direct_named_preset.sh`는 positive direct / low-cost direct wrapper의 validate -> env export -> preset helper invoke 골격을 공통화하고, [tests/test_ops_ci_operator_direct_named_preset.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_direct_named_preset.py) 가 same runner contract를 direct regression으로 고정한다.
- `ops/ci/lib_operator_direct_case_check.sh`는 positive direct / low-cost direct wrapper의 shared direct case-check skeleton을 공통화하고, [tests/test_ops_ci_operator_direct_case_check.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_direct_case_check.py) 가 pair/triple case default resolution, preset invocation, output-note contract를 direct regression으로 고정한다.
- `ops/ci/lib_operator_pair_case_check.sh`는 direct/support wrapper family가 공유하는 pair case-check skeleton을 공통화하고, [tests/test_ops_ci_operator_pair_case_check.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_pair_case_check.py) 가 pair case default resolution, runner invocation, output-note contract를 direct regression으로 고정한다.
- `ops/ci/lib_cases_output_roots.sh`는 direct/repeatability/support workflow helper family의 cases/output-root default resolution을 공통화하고, [tests/test_ops_ci_cases_output_roots.py](/home/ysw/vulDocker/tests/test_ops_ci_cases_output_roots.py) 가 same defaults contract를 direct regression으로 고정한다.
- `ops/ci/lib_operator_cases_output_roots.sh`는 direct/support pair wrapper family의 cases/output-root default resolution을 공통화하고, [tests/test_ops_ci_operator_cases_output_roots.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_cases_output_roots.py) 가 same defaults contract를 direct regression으로 고정한다.
- `ops/ci/lib_operator_support_named_preset.sh`는 positive pair / blocked-noop support wrapper의 validate -> env export -> preset helper invoke 골격을 공통화하고, [tests/test_ops_ci_operator_support_named_preset.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_support_named_preset.py) 가 same runner contract를 direct regression으로 고정한다.
- `ops/ci/lib_operator_support_pair_check.sh`는 positive pair / blocked-noop support wrapper의 shared named-preset pair skeleton을 공통화하고, [tests/test_ops_ci_operator_support_pair_check.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_support_pair_check.py) 가 case default resolution, preset invocation, output-note contract를 direct regression으로 고정한다.
- `ops/ci/lib_operator_runtime_sequence.sh`는 measured/support/docker-positive baseline wrapper의 runtime-surface forwarding + sequence invocation skeleton을 공통화하고, [tests/test_ops_ci_operator_runtime_sequence.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_runtime_sequence.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_operator_pair_runtime_baseline.sh`는 support workflow/docker-positive baseline wrapper의 two-step runtime baseline skeleton을 공통화하고, [tests/test_ops_ci_operator_pair_runtime_baseline.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_pair_runtime_baseline.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_operator_pair_runtime_baseline_defaults.sh`는 support workflow/docker-positive baseline wrapper의 helper/default resolution contract를 공통화하고, [tests/test_ops_ci_operator_pair_runtime_baseline_defaults.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_pair_runtime_baseline_defaults.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_operator_helper_defaults.sh`는 pair/matrix/current defaults library가 공유하는 helper-default single/batch resolution primitive를 공통화하고, [tests/test_ops_ci_operator_helper_defaults.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_helper_defaults.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_operator_matrix_case_pair.sh`는 measured/no-docker baseline wrapper가 공유하는 planning-only matrix pair default/partial-override argument contract를 공통화하고, [tests/test_ops_ci_operator_matrix_case_pair.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_matrix_case_pair.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_operator_matrix_baseline_defaults.sh`는 measured/no-docker baseline wrapper의 matrix helper/default resolution contract를 공통화하고, [tests/test_ops_ci_operator_matrix_baseline_defaults.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_matrix_baseline_defaults.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_operator_matrix_baseline_sequence.sh`는 measured/no-docker matrix baseline wrapper의 matrix env export + runtime-surface + sequence invocation skeleton을 공통화하고, [tests/test_ops_ci_operator_matrix_baseline_sequence.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_matrix_baseline_sequence.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_operator_current_baseline_defaults.sh`는 current baseline의 helper/default resolution contract를 공통화하고, [tests/test_ops_ci_operator_current_baseline_defaults.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_current_baseline_defaults.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_operator_current_baseline_sequence.sh`는 current baseline의 child-surface forwarding + sequence invocation skeleton을 공통화하고, [tests/test_ops_ci_operator_current_baseline_sequence.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_current_baseline_sequence.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_operator_sequence_helper_contract.sh`는 runtime/current/matrix baseline family가 공유하는 sequence-helper executable gate와 invoke primitive를 공통화하고, [tests/test_ops_ci_operator_sequence_helper_contract.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_sequence_helper_contract.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_operator_baseline_matrix_env.sh`는 measured/no-Docker matrix baseline의 `VULD_NAMED_MATRIX_*` export를 공통화하고, [tests/test_ops_ci_operator_baseline_matrix_env.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_baseline_matrix_env.py) 가 same env projection을 direct regression으로 고정한다.
- `ops/ci/lib_operator_retry_env.sh`는 top-level operator baseline의 single-target runtime surface(`operator_forward_runtime_surface(...)`)와 multi-target retry/permission forwarding(`operator_retry_forward_pair_many(...)`, `operator_forward_permission_surface_many(...)`)을 공통화하고, [tests/test_ops_ci_operator_retry_env.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_retry_env.py) 가 same retry/permission projection을 direct regression으로 고정한다.
- `ops/ci/lib_repeatability_chain_env.sh`는 support/matrix helper family의 `VULD_REPEAT_CHAIN_*` export를 공통화하고, [tests/test_ops_ci_repeatability_chain_env.py](/home/ysw/vulDocker/tests/test_ops_ci_repeatability_chain_env.py) 가 same env projection을 direct regression으로 고정한다.
- `ops/ci/lib_repeatability_helper_contract.sh`는 support/matrix helper family의 repeat-helper executable gate를 공통화하고, [tests/test_ops_ci_repeatability_helper_contract.py](/home/ysw/vulDocker/tests/test_ops_ci_repeatability_helper_contract.py) 가 same helper contract를 direct regression으로 고정한다.
- `ops/ci/lib_repeatability_chain_runner.sh`는 support/matrix helper family의 repeat-helper invoke, env export, run-dir postprocess를 하나의 skeleton으로 공통화하고, [tests/test_ops_ci_repeatability_chain_runner.py](/home/ysw/vulDocker/tests/test_ops_ci_repeatability_chain_runner.py) 가 same runner contract를 direct regression으로 고정한다.
- `ops/ci/lib_support_review_runner.sh`는 support workflow/reviewable accept helper family의 review-helper invoke, env export, run-dir preflight를 하나의 skeleton으로 공통화하고, [tests/test_ops_ci_support_review_runner.py](/home/ysw/vulDocker/tests/test_ops_ci_support_review_runner.py) 가 same runner contract를 direct regression으로 고정한다.
- `ops/ci/lib_support_review_env.sh`는 support review helper family의 `VULD_SUPPORT_REVIEW_*` export를 공통화하고, [tests/test_ops_ci_support_review_env.py](/home/ysw/vulDocker/tests/test_ops_ci_support_review_env.py) 가 same env projection을 direct regression으로 고정한다.
- `ops/ci/lib_support_review_output_surface.sh`는 support review helper family의 prefix-aware output-name default resolution과 resolved output-path materialization을 하나의 surface로 공통화하고, latest slice에서는 generic `VULD_SUPPORT_REVIEW_RESOLVED_*`뿐 아니라 `${PREFIX}_RESOLVED_*` output surface도 함께 export한다. `run_support_review_chain.sh`, `run_reviewable_support_accept_check.sh`, `run_support_workflow_chain.sh`가 same resolved output-surface contract를 재사용하고, [tests/test_ops_ci_support_review_output_surface.py](/home/ysw/vulDocker/tests/test_ops_ci_support_review_output_surface.py) 와 [tests/test_ops_ci_support_workflow_chain.py](/home/ysw/vulDocker/tests/test_ops_ci_support_workflow_chain.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_support_review_output_defaults.sh`는 support review helper family의 prefix-aware output-name single/batch default resolution을 공통화하고, [tests/test_ops_ci_support_review_output_defaults.py](/home/ysw/vulDocker/tests/test_ops_ci_support_review_output_defaults.py) 가 same defaults contract를 direct regression으로 고정한다.
- `ops/ci/lib_support_review_helper_contract.sh`는 support review helper family의 review-helper executable gate와 decisions-file materialization contract를 공통화하고, [tests/test_ops_ci_support_review_helper_contract.py](/home/ysw/vulDocker/tests/test_ops_ci_support_review_helper_contract.py) 가 same helper contract를 direct regression으로 고정한다.
- `ops/ci/lib_support_review_output_notes.sh`는 support review helper family의 completion/output note contract를 공통화하고, latest slice에서는 `support_review_emit_review_only_completion(...)`, `support_review_emit_standard_completion(...)`, `support_review_emit_reviewable_accept_completion(...)` 위에 `support_review_emit_prefixed_*`와 `support_review_emit_resolved_*` helpers까지 제공한다. [tests/test_ops_ci_support_review_output_notes.py](/home/ysw/vulDocker/tests/test_ops_ci_support_review_output_notes.py) 가 same note contract를 direct regression으로 고정한다.
- `ops/ci/lib_support_review_run_dirs.sh`는 support review helper family의 run-directory validation contract를 공통화하고, [tests/test_ops_ci_support_review_run_dirs.py](/home/ysw/vulDocker/tests/test_ops_ci_support_review_run_dirs.py) 가 same validation contract를 direct regression으로 고정한다.
- `ops/ci/lib_support_review_outputs.sh`는 support review helper family의 single/batch output path resolution을 공통화하고, [tests/test_ops_ci_support_review_outputs.py](/home/ysw/vulDocker/tests/test_ops_ci_support_review_outputs.py) 가 same output contract를 direct regression으로 고정한다.
- `ops/ci/lib_permission_artifact_summary.sh`는 support/matrix helper family의 machine-readable permission summary contract를 공통화하고, [tests/test_ops_ci_permission_artifact_summary.py](/home/ysw/vulDocker/tests/test_ops_ci_permission_artifact_summary.py) 가 same JSON contract를 direct regression으로 고정한다.
- `ops/ci/lib_repeatability_permission_artifacts.sh`는 support/matrix helper family의 permission-artifact scan/note contract를 공통화하고, [tests/test_ops_ci_repeatability_permission_artifacts.py](/home/ysw/vulDocker/tests/test_ops_ci_repeatability_permission_artifacts.py) 가 same case-slug projection과 note formatting을 direct regression으로 고정한다.
- `ops/ci/lib_repeatability_postprocess.sh`는 support/matrix helper family의 repeat post-process(run-dir load + permission note + summary materialization) contract를 공통화하고, [tests/test_ops_ci_repeatability_postprocess.py](/home/ysw/vulDocker/tests/test_ops_ci_repeatability_postprocess.py) 가 same contract를 direct regression으로 고정한다.
- `ops/ci/lib_case_spec_presets.sh`는 positive pair, blocked/no-op pair, low-cost no-Docker triple, measured matrix pair alias-set preset을 공통화하고, [tests/test_ops_ci_case_spec_presets.py](/home/ysw/vulDocker/tests/test_ops_ci_case_spec_presets.py)가 same preset payload를 direct regression으로 고정한다.
- `ops/ci/run_named_case_set.sh`는 `VULD_NAMED_CASE_TARGET_HELPER`, `VULD_NAMED_CASE_LOG_PREFIX` seam을 지원해 named wrapper 공통 argv forwarding contract를 fake helper로 검증할 수 있다.
- `ops/ci/run_named_preset_case_set.sh`는 `VULD_NAMED_PRESET_TARGET_HELPER`, `VULD_NAMED_PRESET_LOG_PREFIX` seam을 지원해 preset-builder -> named wrapper forwarding contract를 fake helper로 검증할 수 있다.
- `ops/ci/run_named_matrix_case_set.sh`는 `VULD_NAMED_MATRIX_HELPER`, `VULD_NAMED_MATRIX_PYTHON_BIN`, `VULD_NAMED_MATRIX_CASES_ROOT`, `VULD_NAMED_MATRIX_OUTPUT_ROOT`, `VULD_NAMED_MATRIX_MODE`, `VULD_NAMED_MATRIX_ATTEMPTS`, `VULD_NAMED_MATRIX_NO_SNAPSHOT`, `VULD_NAMED_MATRIX_ALLOW_REPEAT_FAILURE_WITH_REPORT`, `VULD_NAMED_MATRIX_PERMISSION_ARTIFACT_NAME`, `VULD_NAMED_MATRIX_PERMISSION_SUMMARY_NAME`, `VULD_NAMED_MATRIX_DOCKER_RETRY_COUNT`, `VULD_NAMED_MATRIX_DOCKER_RETRY_DELAY_SEC`, `VULD_NAMED_MATRIX_REPEAT_HELPER` seam을 지원해 named matrix-case set wrapper contract를 fake helper로 검증할 수 있다.
- `ops/ci/run_named_support_case_set.sh`는 `VULD_NAMED_SUPPORT_HELPER`, `VULD_NAMED_SUPPORT_PYTHON_BIN`, `VULD_NAMED_SUPPORT_CASES_ROOT`, `VULD_NAMED_SUPPORT_OUTPUT_ROOT`, `VULD_NAMED_SUPPORT_MODE`, `VULD_NAMED_SUPPORT_ATTEMPTS`, `VULD_NAMED_SUPPORT_REVIEW_ONLY`, `VULD_NAMED_SUPPORT_DECISIONS_FILE`, `VULD_NAMED_SUPPORT_NO_SNAPSHOT`, `VULD_NAMED_SUPPORT_ALLOW_REPEAT_FAILURE_WITH_REPORT`, `VULD_NAMED_SUPPORT_PERMISSION_ARTIFACT_NAME`, `VULD_NAMED_SUPPORT_PERMISSION_SUMMARY_NAME`, `VULD_NAMED_SUPPORT_DOCKER_RETRY_COUNT`, `VULD_NAMED_SUPPORT_DOCKER_RETRY_DELAY_SEC`, `VULD_NAMED_SUPPORT_REVIEW_OUTPUT_NAME`, `VULD_NAMED_SUPPORT_DECISIONS_OUTPUT_NAME`, `VULD_NAMED_SUPPORT_UPDATE_OUTPUT_NAME`, `VULD_NAMED_SUPPORT_REGISTRY_OUTPUT_NAME`, `VULD_NAMED_SUPPORT_REPEAT_HELPER`, `VULD_NAMED_SUPPORT_REVIEW_HELPER` seam을 지원해 named support-case set wrapper contract를 fake helper로 검증할 수 있다.
- `ops/ci/run_named_direct_case_set.sh`는 `VULD_NAMED_DIRECT_HELPER`, `VULD_NAMED_DIRECT_PYTHON_BIN`, `VULD_NAMED_DIRECT_CASES_ROOT`, `VULD_NAMED_DIRECT_OUTPUT_ROOT`, `VULD_NAMED_DIRECT_MODE`, `VULD_NAMED_DIRECT_NO_SNAPSHOT` seam을 지원해 named direct-case set wrapper contract를 fake helper로 검증할 수 있다.
- `ops/ci/run_support_workflow_chain.sh`는 `VULD_SUPPORT_WORKFLOW_PYTHON_BIN`, `VULD_SUPPORT_WORKFLOW_CASES_ROOT`, `VULD_SUPPORT_WORKFLOW_OUTPUT_ROOT`, `VULD_SUPPORT_WORKFLOW_MODE`, `VULD_SUPPORT_WORKFLOW_ATTEMPTS`, `VULD_SUPPORT_WORKFLOW_REVIEW_ONLY`, `VULD_SUPPORT_WORKFLOW_DECISIONS_FILE`, `VULD_SUPPORT_WORKFLOW_NO_SNAPSHOT`, `VULD_SUPPORT_WORKFLOW_ALLOW_REPEAT_FAILURE_WITH_REPORT`, `VULD_SUPPORT_WORKFLOW_PERMISSION_ARTIFACT_NAME`, `VULD_SUPPORT_WORKFLOW_PERMISSION_SUMMARY_NAME`, `VULD_SUPPORT_WORKFLOW_DOCKER_RETRY_COUNT`, `VULD_SUPPORT_WORKFLOW_DOCKER_RETRY_DELAY_SEC`, `VULD_SUPPORT_WORKFLOW_REVIEW_OUTPUT_NAME`, `VULD_SUPPORT_WORKFLOW_DECISIONS_OUTPUT_NAME`, `VULD_SUPPORT_WORKFLOW_UPDATE_OUTPUT_NAME`, `VULD_SUPPORT_WORKFLOW_REGISTRY_OUTPUT_NAME`, `VULD_SUPPORT_WORKFLOW_REPEAT_HELPER`, `VULD_SUPPORT_WORKFLOW_REVIEW_HELPER` seam을 지원해 arbitrary support workflow command family를 fake python으로 검증할 수 있고, latest slice에서는 `case=alias` output-path override, `run_repeatability_chain.sh`, `run_support_review_chain.sh`, `lib_repeatability_postprocess.sh` reuse와 machine-readable permission summary output도 지원한다.
- `ops/ci/run_support_review_chain.sh`는 `VULD_SUPPORT_REVIEW_PYTHON_BIN`, `VULD_SUPPORT_REVIEW_OUTPUT_ROOT`, `VULD_SUPPORT_REVIEW_REVIEW_ONLY`, `VULD_SUPPORT_REVIEW_DECISIONS_FILE`, `VULD_SUPPORT_REVIEW_REVIEW_OUTPUT_NAME`, `VULD_SUPPORT_REVIEW_DECISIONS_OUTPUT_NAME`, `VULD_SUPPORT_REVIEW_UPDATE_OUTPUT_NAME`, `VULD_SUPPORT_REVIEW_REGISTRY_OUTPUT_NAME` seam을 지원해 arbitrary support review/update/apply command family를 fake python으로 검증할 수 있다.
- `ops/ci/run_repeatability_matrix_check.sh`는 `VULD_REPEAT_MATRIX_PYTHON_BIN`, `VULD_REPEAT_MATRIX_CASES_ROOT`, `VULD_REPEAT_MATRIX_OUTPUT_ROOT`, `VULD_REPEAT_MATRIX_MODE`, `VULD_REPEAT_MATRIX_ATTEMPTS`, `VULD_REPEAT_MATRIX_NO_SNAPSHOT`, `VULD_REPEAT_MATRIX_ALLOW_REPEAT_FAILURE_WITH_REPORT`, `VULD_REPEAT_MATRIX_PERMISSION_ARTIFACT_NAME`, `VULD_REPEAT_MATRIX_PERMISSION_SUMMARY_NAME`, `VULD_REPEAT_MATRIX_DOCKER_RETRY_COUNT`, `VULD_REPEAT_MATRIX_DOCKER_RETRY_DELAY_SEC`, `VULD_REPEAT_MATRIX_REPEAT_HELPER` seam을 지원해 repeatability + matrix rollup command family를 fake python으로 검증할 수 있고, latest slice에서는 `run_repeatability_chain.sh`, `lib_repeatability_postprocess.sh` reuse, machine-readable permission summary output, repeatability-only run directory CLI rollup까지 regression으로 고정한다.
- `ops/ci/run_measured_gate_operator_baseline.sh`는 `VULD_MEASURED_BASELINE_SEQUENCE_HELPER`, `VULD_MEASURED_BASELINE_PRESET_HELPER`, `VULD_MEASURED_BASELINE_NAMED_MATRIX_HELPER`, `VULD_MEASURED_BASELINE_MATRIX_HELPER`, `VULD_MEASURED_BASELINE_PROMOTION_HELPER`, `VULD_MEASURED_BASELINE_MATRIX_CASE_A`, `VULD_MEASURED_BASELINE_MATRIX_CASE_B`, `VULD_MEASURED_BASELINE_PERMISSION_ARTIFACT_NAME`, `VULD_MEASURED_BASELINE_PERMISSION_SUMMARY_NAME`, `VULD_MEASURED_BASELINE_DOCKER_RETRY_COUNT`, `VULD_MEASURED_BASELINE_DOCKER_RETRY_DELAY_SEC` seam을 지원해 measured preview bundle을 fake helper로 검증할 수 있고, latest slice에서는 `run_helper_sequence.sh`, `run_named_preset_case_set.sh`, `run_named_matrix_case_set.sh`, `lib_case_spec_presets.sh`, `lib_permission_artifact_summary.sh`를 재사용한다.
- `ops/ci/run_no_docker_operator_baseline.sh`는 `VULD_NO_DOCKER_BASELINE_SEQUENCE_HELPER`, `VULD_NO_DOCKER_BASELINE_FOCUSED_HELPER`, `VULD_NO_DOCKER_BASELINE_LOW_COST_HELPER`, `VULD_NO_DOCKER_BASELINE_PRESET_HELPER`, `VULD_NO_DOCKER_BASELINE_NAMED_MATRIX_HELPER`, `VULD_NO_DOCKER_BASELINE_MATRIX_HELPER`, `VULD_NO_DOCKER_BASELINE_MATRIX_CASE_A`, `VULD_NO_DOCKER_BASELINE_MATRIX_CASE_B`, `VULD_NO_DOCKER_BASELINE_BLOCKED_HELPER`, `VULD_NO_DOCKER_BASELINE_PERMISSION_ARTIFACT_NAME`, `VULD_NO_DOCKER_BASELINE_PERMISSION_SUMMARY_NAME`, `VULD_NO_DOCKER_BASELINE_MATRIX_DOCKER_RETRY_COUNT`, `VULD_NO_DOCKER_BASELINE_MATRIX_DOCKER_RETRY_DELAY_SEC`, `VULD_NO_DOCKER_BASELINE_BLOCKED_DOCKER_RETRY_COUNT`, `VULD_NO_DOCKER_BASELINE_BLOCKED_DOCKER_RETRY_DELAY_SEC` seam을 지원해 no-Docker operator baseline bundle을 fake helper로 검증할 수 있고, latest slice에서는 `run_helper_sequence.sh`, `run_named_preset_case_set.sh`, `run_named_matrix_case_set.sh`, `lib_case_spec_presets.sh`, `lib_permission_artifact_summary.sh`를 재사용한다.
- `ops/ci/run_direct_validation_chain.sh`는 `VULD_DIRECT_CHAIN_PYTHON_BIN`, `VULD_DIRECT_CHAIN_CASES_ROOT`, `VULD_DIRECT_CHAIN_OUTPUT_ROOT`, `VULD_DIRECT_CHAIN_MODE`, `VULD_DIRECT_CHAIN_NO_SNAPSHOT` seam을 지원해 arbitrary direct rerun command family를 fake python으로 검증할 수 있다.
- `ops/ci/run_support_workflow_operator_baseline.sh`는 `VULD_SUPPORT_BASELINE_SEQUENCE_HELPER`, `VULD_SUPPORT_BASELINE_REVIEWABLE_HELPER`, `VULD_SUPPORT_BASELINE_BLOCKED_HELPER`, `VULD_SUPPORT_BASELINE_PERMISSION_ARTIFACT_NAME`, `VULD_SUPPORT_BASELINE_DOCKER_RETRY_COUNT`, `VULD_SUPPORT_BASELINE_DOCKER_RETRY_DELAY_SEC` seam을 지원해 support workflow operator baseline bundle을 fake helper로 검증할 수 있고, latest slice에서는 `run_helper_sequence.sh`를 재사용한다.
- `ops/ci/run_reviewable_support_accept_check.sh`는 `VULD_REVIEWABLE_ACCEPT_PYTHON_BIN`, `VULD_REVIEWABLE_ACCEPT_OUTPUT_ROOT`, `VULD_REVIEWABLE_ACCEPT_CASE_NAME`, `VULD_REVIEWABLE_ACCEPT_SLUG`, `VULD_REVIEWABLE_ACCEPT_VULN_ID`, `VULD_REVIEWABLE_ACCEPT_REVIEWER`, `VULD_REVIEWABLE_ACCEPT_RATIONALE`, `VULD_REVIEWABLE_ACCEPT_REVIEW_HELPER` seam을 지원해 synthetic reviewable accept-path command family를 fake python으로 검증할 수 있고, latest slice에서는 `run_support_review_chain.sh` reuse를 regression으로 고정한다.
- `ops/ci/run_docker_positive_operator_baseline.sh`는 `VULD_DOCKER_POSITIVE_BASELINE_SEQUENCE_HELPER`, `VULD_DOCKER_POSITIVE_BASELINE_DIRECT_HELPER`, `VULD_DOCKER_POSITIVE_BASELINE_PROMOTION_HELPER`, `VULD_DOCKER_POSITIVE_BASELINE_PERMISSION_ARTIFACT_NAME`, `VULD_DOCKER_POSITIVE_BASELINE_DOCKER_RETRY_COUNT`, `VULD_DOCKER_POSITIVE_BASELINE_DOCKER_RETRY_DELAY_SEC` seam을 지원해 positive operator baseline bundle을 fake helper로 검증할 수 있고, latest slice에서는 `run_helper_sequence.sh`를 재사용한다.
- `ops/ci/run_positive_direct_validation.sh`는 `VULD_POSITIVE_DIRECT_PRESET_HELPER`, `VULD_POSITIVE_DIRECT_NAMED_HELPER`, `VULD_POSITIVE_DIRECT_PYTHON_BIN`, `VULD_POSITIVE_DIRECT_CASES_ROOT`, `VULD_POSITIVE_DIRECT_OUTPUT_ROOT`, `VULD_POSITIVE_DIRECT_MODE`, `VULD_POSITIVE_DIRECT_NO_SNAPSHOT`, `VULD_POSITIVE_DIRECT_HELPER` seam을 지원해 Docker-enabled positive direct rerun command family를 fake python으로 검증할 수 있고, latest slice에서는 `run_named_preset_case_set.sh`, `run_named_direct_case_set.sh`, `run_direct_validation_chain.sh`, `lib_case_spec_presets.sh`, `lib_operator_named_case_env.sh`, `lib_operator_named_preset_helpers.sh`를 재사용한다.
- `ops/ci/run_repeatability_gate.sh`와 `ops/ci/run_e2e_tests.sh` repeatability chaining은 `repeatability_report.json.passed=false`도 nonzero gate failure로 전파한다.
- `ops/ci/run_low_cost_no_docker_validation.sh`는 `VULD_LOW_COST_PRESET_HELPER`, `VULD_LOW_COST_NAMED_DIRECT_HELPER`, `VULD_LOW_COST_PYTHON_BIN`, `VULD_LOW_COST_CASES_ROOT`, `VULD_LOW_COST_OUTPUT_ROOT`, `VULD_LOW_COST_MODE`, `VULD_LOW_COST_NO_SNAPSHOT`, `VULD_LOW_COST_DIRECT_HELPER` seam을 지원해 strict/abstain no-Docker direct rerun command family를 fake python으로 검증할 수 있고, latest slice에서는 `run_named_preset_case_set.sh`, `run_named_direct_case_set.sh`, `run_direct_validation_chain.sh`, `lib_case_spec_presets.sh`, `lib_operator_named_case_env.sh`, `lib_operator_named_preset_helpers.sh`를 재사용한다.
- `ops/ci/run_repeatability_gate.sh`는 `VULD_REPEAT_PYTHON_BIN` seam을 지원해 repeat helper/report contract를 fake python으로도 검증할 수 있다.
- `ops/ci/run_e2e_tests.sh`는 `VULD_E2E_CASES_DIR`, `VULD_E2E_CONFIG_PATH`, `VULD_E2E_PYTHON_BIN`, `VULD_E2E_PYTEST_BIN`, `VULD_E2E_REPEAT_HELPER` seam을 지원해 temp case dir/config/fake pytest/repeat helper로 CI entrypoint contract를 검증할 수 있다.
- `ops/ci/run_positive_pair_promotion_check.sh`는 `VULD_POSITIVE_PAIR_PRESET_HELPER`, `VULD_POSITIVE_PAIR_NAMED_SUPPORT_HELPER`, `VULD_POSITIVE_PAIR_PYTHON_BIN`, `VULD_POSITIVE_PAIR_CASES_ROOT`, `VULD_POSITIVE_PAIR_OUTPUT_ROOT`, `VULD_POSITIVE_PAIR_MODE`, `VULD_POSITIVE_PAIR_NO_SNAPSHOT`, `VULD_POSITIVE_PAIR_PERMISSION_ARTIFACT_NAME`, `VULD_POSITIVE_PAIR_PERMISSION_SUMMARY_NAME`, `VULD_POSITIVE_PAIR_DOCKER_RETRY_COUNT`, `VULD_POSITIVE_PAIR_DOCKER_RETRY_DELAY_SEC`, `VULD_POSITIVE_PAIR_SUPPORT_HELPER` seam을 지원해 positive pair promotion check command family를 fake python으로 검증할 수 있고, latest slice에서는 `run_named_preset_case_set.sh`, `run_named_support_case_set.sh`, review-only `run_support_workflow_chain.sh`, `lib_case_spec_presets.sh`, `lib_operator_named_case_env.sh`, `lib_operator_named_preset_helpers.sh` reuse를 regression으로 고정한다.
- `ops/ci/run_blocked_noop_support_check.sh`는 `VULD_BLOCKED_NOOP_PRESET_HELPER`, `VULD_BLOCKED_NOOP_NAMED_SUPPORT_HELPER`, `VULD_BLOCKED_NOOP_PYTHON_BIN`, `VULD_BLOCKED_NOOP_CASES_ROOT`, `VULD_BLOCKED_NOOP_OUTPUT_ROOT`, `VULD_BLOCKED_NOOP_MODE`, `VULD_BLOCKED_NOOP_ATTEMPTS`, `VULD_BLOCKED_NOOP_NO_SNAPSHOT`, `VULD_BLOCKED_NOOP_PERMISSION_ARTIFACT_NAME`, `VULD_BLOCKED_NOOP_PERMISSION_SUMMARY_NAME`, `VULD_BLOCKED_NOOP_DOCKER_RETRY_COUNT`, `VULD_BLOCKED_NOOP_DOCKER_RETRY_DELAY_SEC`, `VULD_BLOCKED_NOOP_SUPPORT_HELPER` seam을 지원해 blocked/no-op rehearsal command family를 fake python으로 검증할 수 있고, latest slice에서는 `run_named_preset_case_set.sh`, `run_named_support_case_set.sh`, generic `run_support_workflow_chain.sh`, `lib_case_spec_presets.sh`, `lib_operator_named_case_env.sh`, `lib_operator_named_preset_helpers.sh` reuse를 regression으로 고정한다.
- latest helper semantics에서는 `run_support_workflow_chain.sh` / `run_positive_pair_promotion_check.sh`가 actual blocked promotion lane의 `repeat_case.py` nonzero-with-report를 허용하고 support review까지 계속 진행한다. same repeat helper는 transient docker readiness failure도 retry seam으로 흡수하고, `docker daemon permission denied`는 separate permission artifact로 marker/note를 남긴다. unrestricted Docker-enabled helper rerun에서는 positive-pair helper projection이 다시 manual truth와 정렬되며, sandbox helper output은 environment artifact로 읽는 편이 맞다. remaining residual은 broader promotion closure와 bounded helper/operator projection consistency를 함께 본다.
- current workspace-local direct verification에서는 same sandbox helper output이 empty aggregate(`authority_ready_bundle_count=0`, `by_support_status={}`)로 끝날 수도 다시 확인됐다. same output도 runtime-equivalent truth가 아니라 permission-artifact environment output으로 읽는다.
- `ops/ci/run_focused_no_docker_regression.sh`는 `VULD_FOCUSED_NO_DOCKER_PYTEST_BIN` seam을 지원해 fastest no-Docker pytest preflight command family를 fake pytest로 검증할 수 있다.
- `ops/ci/run_case.sh`는 `VULD_RUN_CASE_PYTHON_BIN`, `VULD_RUN_CASE_DOCKER_BIN` seam을 지원해 wrapper contract와 pipeline returncode propagation을 fake python/docker로 검증할 수 있다.
- `ops/ci/run_base_example.sh`와 `ops/ci/run_base_examples.sh`는 runner override seam(`VULD_BASE_RUN_CASE_SCRIPT`, `VULD_BASE_EXAMPLE_SCRIPT`)과 requirement override(`VULD_BASE_REQUIREMENT_FILE`)를 지원해 workspace-local regression에서 fake runner로 contract를 검증할 수 있다.
- `ops/ci/run_custom_vuln_example.sh`도 `VULD_CUSTOM_BASE_REQUIREMENT_FILE`, `VULD_CUSTOM_RUN_CASE_SCRIPT` seam을 지원해 custom vuln helper contract를 workspace-local temp requirement로 고정할 수 있다.
- `ops/ci/smoke_regression.sh`도 `VULD_SMOKE_DOCKER_BIN`, `VULD_SMOKE_PYTHON_BIN`, `VULD_SMOKE_FLOW_SCRIPT`, `VULD_SMOKE_SNAPSHOT` seam을 지원해 smoke helper contract를 fake docker/flow로 검증할 수 있다.
- measured/support workflow는 operator-specified output directory에 `repeatability_report.json`, `matrix_report.json`, `support_candidate.json`, `support_review_index.json`, `support_registry_update.json`, `curated_support_registry.json`을 남길 수 있지만, 이것은 현재 수동 review/update rehearsal surface다.

## 프로젝트 내 역할

- 수동 실행을 자동화하고 회귀/KPI를 관측 가능한 형태로 유지한다.
- authoritative measured gate / CI policy closure는 roadmap상 `Phase 5B`, backlog상 `TKT-008-A2` owner다.
- curated registry closure는 backlog상 `TKT-009-A1/B*` owner이며, 현재 ops 문서는 그 workflow 존재와 경계만 설명한다.

## Residual Review Focus

- `TKT-008-A2` residual은 CI/automation boundary가 measured gate authoritative policy와 어디서 만나는지부터 본다.
- `TKT-009-*` residual은 ops가 local/manual workflow를 auto-promotion처럼 다루지 않는지 boundary를 먼저 본다.

## Completion Review Focus

- `TKT-008-A2` completion은 CI/automation path가 measured gate를 optional preview가 아니라 authoritative policy boundary로 실제 소비하는지부터 본다.
- `TKT-009-*` completion은 local/manual registry workflow와 auto-promotion boundary가 운영 문서와 스크립트 양쪽에서 계속 분리되는지부터 본다.

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

- current completion priority order에서 ops는 `TKT-008-A2`, `TKT-009-*` operationalization companion으로 읽는다.
- 선행 control-plane/runtime/oracle bucket이 닫히기 전에는 ops 문서가 auto-promotion이나 expansion 우선순위를 끌어올리는 source가 아님을 명시적으로 유지한다.
- latest positive representative pair의 ticket-form reading도 ops를 acceptance/promotion 후행 companion으로만 두고, 본체 residual source로 읽지 않게 만든다. canonical 해석은 [docs/work_tickets.md](../work_tickets.md)의 `Assessment-To-Ticket Interpretation`을 따른다.
- 잔여 작업량/turn envelope 해석도 [docs/work_tickets.md](../work_tickets.md)의 `Estimated Turn Envelope`를 같이 따른다.
- turn estimate shortcut도 [docs/work_tickets.md](../work_tickets.md)의 `Turn Estimate Entry`를 같이 따른다.
- LLM-response stricter reading에서도 host Docker prerequisite는 operational precondition으로만 읽고, product backlog 본체 우선순위를 앞당기는 근거로 쓰지 않는다.
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

- core CI / smoke path를 볼 때:
  - `ops/ci/run_case.sh`
  - `ops/ci/smoke_regression.sh`
- measured gate / CI policy와 맞닿는 경계를 볼 때:
  - `ops/ci/*`
  - `tests/e2e/repeat_case.py`
  - `tests/e2e/matrix_report.py`
  - latest cheapest no-Docker pair:
    - `foobar-name-only-negative`
    - `open-redirect-strict-dynamic-no-remote`
- support workflow automation boundary를 볼 때:
  - `ops/ci/run_support_workflow_chain.sh`
  - `tests/e2e/support_review.py`
  - `tests/e2e/support_decide.py`
  - `tests/e2e/support_apply.py`

## Representative Validation Surface

- ops/environment sanity:
  - `tests/test_ops_ci_script_permissions.py`
  - `tests/test_ops_ci_measured_gate_operator_baseline.py`
  - `tests/test_ops_ci_direct_validation_chain.py`
  - `tests/test_ops_ci_repeatability_matrix_check.py`
  - `tests/test_ops_ci_support_workflow_chain.py`
  - `tests/test_ops_ci_support_workflow_operator_baseline.py`
  - `tests/test_ops_ci_reviewable_accept_check.py`
  - `tests/test_ops_ci_current_operator_baseline.py`
  - `tests/test_ops_ci_docker_positive_operator_baseline.py`
  - `tests/test_ops_ci_positive_direct_validation.py`
  - `tests/test_ops_ci_no_docker_operator_baseline.py`
  - `tests/test_ops_ci_helper_contract_regression.py`
  - `tests/test_ops_ci_low_cost_no_docker_validation.py`
  - `tests/test_ops_ci_focused_no_docker_regression.py`
  - `tests/test_ops_ci_blocked_noop_support_check.py`
  - `tests/test_ops_ci_positive_pair_promotion_check.py`
  - `tests/test_ops_ci_e2e_entry_script.py`
  - `tests/test_ops_ci_smoke_regression_script.py`
  - `tests/test_ops_ci_run_case_script.py`
  - `tests/test_ops_ci_base_example_scripts.py`
  - `tests/test_ops_ci_custom_vuln_script.py`
  - `tests/test_e2e_env_checks.py`
  - `tests/test_plan_sid_isolation.py`
- CI boundary sanity:
  - `tests/e2e/test_cases.py`
  - `tests/e2e/test_case_matrix_rollup.py`
  - `tests/e2e/test_support_workflow.py`
  - manual blocked/no-op rehearsal pair:
    - `foobar-name-only-negative`
    - `open-redirect-strict-dynamic-no-remote`

## How To Update This Document

- CI/ops entrypoint, automation boundary, observability script surface가 바뀔 때만 갱신한다.
- current rerun truth나 local verification result는 [docs/current_state_gap_analysis.md](../current_state_gap_analysis.md)에 남긴다.
- current operational constraint와 auto-promotion non-claim은 [docs/constraints.md](../constraints.md)에 남긴다.
- owner와 sequencing은 [docs/final_solution.md](../final_solution.md), [docs/work_tickets.md](../work_tickets.md)로 보낸다.
- `ops/ci/pipeline.md`, `ops/observability/dashboard_spec.md`의 companion positioning이나 maintenance rule이 바뀌면 같이 갱신한다.
- ticket-first entrypoint나 representative validation surface가 바뀌면 이 문서의 해당 섹션도 같이 갱신한다.
- completion review focus가 바뀌면 same owner/ticket mapping에 맞춰 이 문서도 같이 갱신한다.
- residual review focus가 바뀌면 same ops boundary 기준으로 이 문서도 같이 갱신한다.
- priority review focus나 priority companion 해석이 바뀌면 [docs/code/README.md](README.md), [docs/work_tickets.md](../work_tickets.md)와 같이 갱신한다.
- LLM-response stricter reading의 ops-side prerequisite 해석이 바뀌면 [docs/work_tickets.md](../work_tickets.md)의 `LLM-Response Capability Overlay`와 같이 갱신한다.
- latest positive representative pair의 ticket-form 해석이 바뀌면 [docs/work_tickets.md](../work_tickets.md)의 `Assessment-To-Ticket Interpretation`와 같이 갱신한다.
- 잔여 작업량/turn envelope 해석이 바뀌면 [docs/work_tickets.md](../work_tickets.md)의 `Estimated Turn Envelope`와 같이 갱신한다.
- [docs/work_tickets.md](../work_tickets.md)의 `Turn Estimate Entry`가 바뀌면 same shortcut도 같이 갱신한다.
- review mode entry shortcut이 바뀌면 [docs/code/README.md](README.md)와 같이 갱신한다.
- CI boundary에 연결된 harness path가 바뀌면 [tests/e2e/README.md](../../tests/e2e/README.md)와 같이 갱신한다.
