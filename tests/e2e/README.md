# E2E 회귀 하니스

Status: support
Audience: implementation, operator
Source of truth for: case layout, direct E2E harness usage, repeatability/support workflow commands
Not the source of truth for: backlog priority, current-state assessment, policy claims
Last validated against: current E2E harness scripts, `python -m pytest -q tests/test_ops_ci_*.py`, and measured/support workflow on 2026-04-02

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
- latest residual을 concise ticket-form으로 먼저 보려면 같은 [docs/work_tickets.md](../docs/work_tickets.md)의 `Current Remaining Ticket Form`을 본다.
- current completion priority order를 바로 보려면 같은 [docs/work_tickets.md](../docs/work_tickets.md)의 `Confirmed Completion Priority Order`를 본다.
- 잔여 작업량/turn envelope를 바로 보려면 같은 [docs/work_tickets.md](../docs/work_tickets.md)의 `Estimated Turn Envelope`를 본다.
- representative rerun evidence와 같이 turn estimate를 읽으려면 같은 [docs/work_tickets.md](../docs/work_tickets.md)의 `Turn Estimate Entry`와 이 문서의 `Positive Pair Promotion Check`를 같이 본다.
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

## Current Operator Baseline

current no-Docker baseline, measured gate baseline, support baseline, Docker-positive baseline, ops helper regression을 한 번에 보고 싶으면 아래 helper를 사용한다.

```bash
ops/ci/run_current_operator_baseline.sh
```

- helper override seam:
  - `VULD_CURRENT_BASELINE_SEQUENCE_HELPER`
  - `VULD_CURRENT_BASELINE_NO_DOCKER_HELPER`
  - `VULD_CURRENT_BASELINE_MEASURED_HELPER`
  - `VULD_CURRENT_BASELINE_SUPPORT_HELPER`
  - `VULD_CURRENT_BASELINE_DOCKER_POSITIVE_HELPER`
  - `VULD_CURRENT_BASELINE_HELPER_REGRESSION`
  - `VULD_CURRENT_BASELINE_PERMISSION_SUMMARY_NAME`
- helper는 generic bundle executor `ops/ci/run_helper_sequence.sh`를 재사용한다.

## No-Docker Operator Baseline

focused preflight, low-cost validation lanes, repeatability matrix preview, blocked/no-op rehearsal을 한 번에 보려면 아래 helper를 사용한다.

```bash
ops/ci/run_no_docker_operator_baseline.sh
```

- helper override seam:
  - `VULD_NO_DOCKER_BASELINE_SEQUENCE_HELPER`
  - `VULD_NO_DOCKER_BASELINE_FOCUSED_HELPER`
  - `VULD_NO_DOCKER_BASELINE_LOW_COST_HELPER`
  - `VULD_NO_DOCKER_BASELINE_PRESET_HELPER`
  - `VULD_NO_DOCKER_BASELINE_MATRIX_HELPER`
  - `VULD_NO_DOCKER_BASELINE_BLOCKED_HELPER`
  - `VULD_NO_DOCKER_BASELINE_PERMISSION_SUMMARY_NAME`
- helper는 generic bundle executor `ops/ci/run_helper_sequence.sh`를 재사용한다.

## Low-Cost No-Docker Validation Lanes

Docker runtime 없이도 current name-only policy / measured-support workflow 일부를 직접 검증할 수 있다.

```bash
ops/ci/run_low_cost_no_docker_validation.sh
ops/ci/run_direct_validation_chain.sh open-redirect-strict-dynamic-no-remote open-redirect-strict-dynamic-stub foobar-name-only-negative

# 또는 underlying direct rerun chain
python tests/e2e/run_case.py --case tests/e2e/cases/open-redirect-strict-dynamic-no-remote --mode deterministic --no-snapshot --output-dir /tmp/vuld_strict_no_remote
python tests/e2e/run_case.py --case tests/e2e/cases/open-redirect-strict-dynamic-stub --mode deterministic --no-snapshot --output-dir /tmp/vuld_strict_stub
python tests/e2e/run_case.py --case tests/e2e/cases/foobar-name-only-negative --mode deterministic --no-snapshot --output-dir /tmp/vuld_negative
```

- helper override seam:
  - `VULD_LOW_COST_PYTHON_BIN`
  - `VULD_LOW_COST_CASES_ROOT`
  - `VULD_LOW_COST_OUTPUT_ROOT`
  - `VULD_LOW_COST_MODE`
  - `VULD_LOW_COST_NO_SNAPSHOT`
  - `VULD_LOW_COST_NAMED_DIRECT_HELPER`
  - `VULD_LOW_COST_DIRECT_HELPER`
- `open-redirect-strict-dynamic-no-remote`: strict fail-closed가 remote-research capability precheck에서 닫히는지 확인하는 low-cost lane
- `open-redirect-strict-dynamic-stub`: strict fail-closed가 live-LLM capability precheck에서 닫히는지 확인하는 low-cost lane
- `foobar-name-only-negative`: unsupported free-form name이 success-like closure가 아니라 `abstain`으로 남는지 확인하는 low-cost lane
- positive LLM-shaped lane(`trusted-dynamic-sqli`)과 representative dynamic lane(`open-redirect-dynamic-name-only`)는 no-Docker lane이 아니다. 둘은 실제 Docker build/run이 필요하며, latest Docker-enabled rerun에서는 둘 다 expectation을 통과했다. 다만 Docker가 막힌 환경에서는 여전히 `docker daemon is not reachable`에서 멈출 수 있다.
- helper는 latest slice에서 generic `ops/ci/run_named_direct_case_set.sh`를 통해 case alias set을 구성한 뒤 `ops/ci/run_direct_validation_chain.sh`를 재사용한다.

## Generic Direct Validation Chain

임의 case slug 집합에 대해 generic `run_case.py` direct rerun 흐름을 재현하려면 아래 helper를 사용한다.

```bash
ops/ci/run_direct_validation_chain.sh open-redirect-strict-dynamic-no-remote open-redirect-strict-dynamic-stub foobar-name-only-negative
ops/ci/run_direct_validation_chain.sh trusted-dynamic-sqli open-redirect-dynamic-name-only
```

- helper override seam:
  - `VULD_DIRECT_CHAIN_PYTHON_BIN`
  - `VULD_DIRECT_CHAIN_CASES_ROOT`
  - `VULD_DIRECT_CHAIN_OUTPUT_ROOT`
  - `VULD_DIRECT_CHAIN_MODE`
  - `VULD_DIRECT_CHAIN_NO_SNAPSHOT`
- `expectations.json`가 케이스 폴더에 있으면 helper가 자동으로 `--expectations`를 붙인다.
- 기본값은 `--no-snapshot` 활성화이며, `VULD_DIRECT_CHAIN_NO_SNAPSHOT=0`이면 snapshot을 유지한다.

## Positive Direct Validation

Docker-enabled representative positive direct rerun은 아래 helper로 묶어 실행할 수 있다.

```bash
ops/ci/run_positive_direct_validation.sh
ops/ci/run_direct_validation_chain.sh trusted-dynamic-sqli open-redirect-dynamic-name-only

# 또는 underlying direct rerun chain
python tests/e2e/run_case.py --case tests/e2e/cases/trusted-dynamic-sqli --expectations tests/e2e/cases/trusted-dynamic-sqli/expectations.json --mode deterministic --no-snapshot --output-dir /tmp/vuld_trusted_dynamic
python tests/e2e/run_case.py --case tests/e2e/cases/open-redirect-dynamic-name-only --expectations tests/e2e/cases/open-redirect-dynamic-name-only/expectations.json --mode deterministic --no-snapshot --output-dir /tmp/vuld_open_redirect_dynamic
```

- helper override seam:
  - `VULD_POSITIVE_DIRECT_PRESET_HELPER`
  - `VULD_POSITIVE_DIRECT_PYTHON_BIN`
  - `VULD_POSITIVE_DIRECT_CASES_ROOT`
  - `VULD_POSITIVE_DIRECT_OUTPUT_ROOT`
  - `VULD_POSITIVE_DIRECT_MODE`
  - `VULD_POSITIVE_DIRECT_NO_SNAPSHOT`
  - `VULD_POSITIVE_DIRECT_NAMED_HELPER`
  - `VULD_POSITIVE_DIRECT_HELPER`
- helper는 latest slice에서 generic `ops/ci/run_named_preset_case_set.sh`, `ops/ci/run_named_direct_case_set.sh`를 통해 alias output path를 유지한 채 `ops/ci/run_direct_validation_chain.sh`를 재사용한다.

## Docker Positive Operator Baseline

direct rerun baseline과 promotion check를 한 번에 보려면 아래 helper를 사용한다.

```bash
ops/ci/run_docker_positive_operator_baseline.sh
```

- helper override seam:
  - `VULD_DOCKER_POSITIVE_BASELINE_SEQUENCE_HELPER`
  - `VULD_DOCKER_POSITIVE_BASELINE_DIRECT_HELPER`
  - `VULD_DOCKER_POSITIVE_BASELINE_PROMOTION_HELPER`
- helper는 generic bundle executor `ops/ci/run_helper_sequence.sh`를 재사용한다.

planning-only measured/support no-op chain은 아래 pair를 기본 regression pair로 사용한다.

```bash
ops/ci/run_blocked_noop_support_check.sh

# 또는 underlying command chain
python tests/e2e/repeat_case.py --case tests/e2e/cases/foobar-name-only-negative --attempts 2 --mode deterministic --output-dir /tmp/vuld_repeat_foobar
python tests/e2e/repeat_case.py --case tests/e2e/cases/open-redirect-strict-dynamic-no-remote --attempts 2 --mode deterministic --output-dir /tmp/vuld_repeat_strict
python tests/e2e/support_review.py /tmp/vuld_repeat_foobar /tmp/vuld_repeat_strict --output /tmp/vuld_support_review.json
python tests/e2e/support_decide.py --review-index /tmp/vuld_support_review.json --decisions /tmp/vuld_support_decisions.json --output /tmp/vuld_support_update.json
python tests/e2e/support_apply.py --registry-update /tmp/vuld_support_update.json --output /tmp/vuld_support_registry.json
```

- helper override seam:
  - `VULD_BLOCKED_NOOP_PYTHON_BIN`
  - `VULD_BLOCKED_NOOP_CASES_ROOT`
  - `VULD_BLOCKED_NOOP_OUTPUT_ROOT`
  - `VULD_BLOCKED_NOOP_MODE`
  - `VULD_BLOCKED_NOOP_ATTEMPTS`
  - `VULD_BLOCKED_NOOP_NO_SNAPSHOT`
  - `VULD_BLOCKED_NOOP_PERMISSION_ARTIFACT_NAME`
  - `VULD_BLOCKED_NOOP_PERMISSION_SUMMARY_NAME`
  - `VULD_BLOCKED_NOOP_DOCKER_RETRY_COUNT`
  - `VULD_BLOCKED_NOOP_DOCKER_RETRY_DELAY_SEC`
  - `VULD_BLOCKED_NOOP_PRESET_HELPER`
  - `VULD_BLOCKED_NOOP_NAMED_SUPPORT_HELPER`
  - `VULD_BLOCKED_NOOP_SUPPORT_HELPER`
- helper는 latest slice에서 generic `ops/ci/run_named_preset_case_set.sh`, `ops/ci/run_named_support_case_set.sh`를 통해 `foobar`, `strict` alias output path를 구성하고, 내부적으로 `ops/ci/run_support_workflow_chain.sh`와 `ops/ci/run_support_review_chain.sh`를 재사용한다.
- 이 pair는 current truth 기준 `authority_ready_bundle_count > 0`이더라도 `measured_gate_blocked_bundle_count > 0`, `reviewable_bundle_count = 0`, final `registry_item_count = 0` no-op로 끝나는지 확인하는 용도다

## Reviewable Accept Path Check

synthetic reviewable accept path를 직접 재현하고 싶으면 아래 helper를 사용한다.

```bash
ops/ci/run_reviewable_support_accept_check.sh
```

- helper override seam:
  - `VULD_REVIEWABLE_ACCEPT_PYTHON_BIN`
  - `VULD_REVIEWABLE_ACCEPT_OUTPUT_ROOT`
  - `VULD_REVIEWABLE_ACCEPT_CASE_NAME`
  - `VULD_REVIEWABLE_ACCEPT_SLUG`
  - `VULD_REVIEWABLE_ACCEPT_VULN_ID`
- `VULD_REVIEWABLE_ACCEPT_REVIEWER`
- `VULD_REVIEWABLE_ACCEPT_RATIONALE`
- `VULD_REVIEWABLE_ACCEPT_REVIEW_HELPER`
- 이 helper는 synthetic `support_candidate.json`과 accept decision을 materialize한 뒤 `support_review.py -> support_decide.py -> support_apply.py`를 실제 CLI 흐름으로 실행한다.

## Generic Support Workflow Chain

임의 case slug 집합에 대해 generic `repeat_case -> support_review -> support_decide -> support_apply` 흐름을 재현하려면 아래 helper를 사용한다.

```bash
ops/ci/run_support_workflow_chain.sh foobar-name-only-negative open-redirect-strict-dynamic-no-remote

# review-only preview만 보고 싶으면
VULD_SUPPORT_WORKFLOW_REVIEW_ONLY=1 ops/ci/run_support_workflow_chain.sh trusted-dynamic-sqli open-redirect-dynamic-name-only

# alias output path와 custom review filename이 필요하면
VULD_SUPPORT_WORKFLOW_REVIEW_ONLY=1 VULD_SUPPORT_WORKFLOW_REVIEW_OUTPUT_NAME=custom_review.json \
  ops/ci/run_support_workflow_chain.sh trusted-dynamic-sqli=trusted_dynamic open-redirect-dynamic-name-only=open_redirect_dynamic
```

- helper override seam:
  - `VULD_SUPPORT_WORKFLOW_PYTHON_BIN`
  - `VULD_SUPPORT_WORKFLOW_CASES_ROOT`
  - `VULD_SUPPORT_WORKFLOW_OUTPUT_ROOT`
  - `VULD_SUPPORT_WORKFLOW_MODE`
  - `VULD_SUPPORT_WORKFLOW_ATTEMPTS`
  - `VULD_SUPPORT_WORKFLOW_REVIEW_ONLY`
  - `VULD_SUPPORT_WORKFLOW_DECISIONS_FILE`
  - `VULD_SUPPORT_WORKFLOW_NO_SNAPSHOT`
  - `VULD_SUPPORT_WORKFLOW_ALLOW_REPEAT_FAILURE_WITH_REPORT`
  - `VULD_SUPPORT_WORKFLOW_PERMISSION_ARTIFACT_NAME`
  - `VULD_SUPPORT_WORKFLOW_PERMISSION_SUMMARY_NAME`
  - `VULD_SUPPORT_WORKFLOW_REVIEW_OUTPUT_NAME`
  - `VULD_SUPPORT_WORKFLOW_DECISIONS_OUTPUT_NAME`
  - `VULD_SUPPORT_WORKFLOW_UPDATE_OUTPUT_NAME`
  - `VULD_SUPPORT_WORKFLOW_REGISTRY_OUTPUT_NAME`
  - `VULD_SUPPORT_WORKFLOW_REPEAT_HELPER`
  - `VULD_SUPPORT_WORKFLOW_REVIEW_HELPER`
- `expectations.json`가 케이스 폴더에 있으면 helper가 자동으로 `--expectations`를 붙인다.
- `case-slug=alias` 형식을 쓰면 `repeat_<alias>` output path를 강제할 수 있다.
- explicit reviewer decisions file을 주지 않으면 empty decisions payload를 materialize해서 preview/apply까지 진행한다.
- `VULD_SUPPORT_WORKFLOW_REVIEW_ONLY=1`이면 `support_review.py`까지만 실행하고 `support_decide.py`, `support_apply.py`는 건너뛴다.
- helper는 latest slice에서 repeat 공통부를 `ops/ci/run_repeatability_chain.sh`, review/update/apply 공통부를 `ops/ci/run_support_review_chain.sh`로 위임한다.
- `VULD_SUPPORT_WORKFLOW_ALLOW_REPEAT_FAILURE_WITH_REPORT=1` 기본값에서는 `repeat_case.py`가 nonzero여도 `repeatability_report.json`이 생성되어 있으면 support review chain을 계속 진행한다.
- repeat output에 permission-artifact marker가 있으면 helper는 review 전에 note를 출력하고, same output을 sandbox artifact로 읽을 수 있게 해 준다.
- helper는 output root에 machine-readable `permission_artifact_summary.json`도 남기며, `VULD_SUPPORT_WORKFLOW_PERMISSION_SUMMARY_NAME`으로 filename을 바꿀 수 있다.

## Generic Support Review Chain

기존 repeat run directories를 이미 가지고 있다면 generic `support_review -> support_decide -> support_apply` 흐름만 별도로 재현하려면 아래 helper를 사용한다.

```bash
ops/ci/run_support_review_chain.sh /tmp/vuld_repeat_a /tmp/vuld_repeat_b

# review-only preview만 보고 싶으면
VULD_SUPPORT_REVIEW_REVIEW_ONLY=1 ops/ci/run_support_review_chain.sh /tmp/vuld_repeat_a /tmp/vuld_repeat_b
```

- helper override seam:
  - `VULD_SUPPORT_REVIEW_PYTHON_BIN`
  - `VULD_SUPPORT_REVIEW_OUTPUT_ROOT`
  - `VULD_SUPPORT_REVIEW_REVIEW_ONLY`
  - `VULD_SUPPORT_REVIEW_DECISIONS_FILE`
  - `VULD_SUPPORT_REVIEW_REVIEW_OUTPUT_NAME`
  - `VULD_SUPPORT_REVIEW_DECISIONS_OUTPUT_NAME`
  - `VULD_SUPPORT_REVIEW_UPDATE_OUTPUT_NAME`
  - `VULD_SUPPORT_REVIEW_REGISTRY_OUTPUT_NAME`
- `run_support_workflow_chain.sh`와 `run_reviewable_support_accept_check.sh`는 latest slice에서 이 helper를 재사용한다.

## Support Workflow Operator Baseline

reviewable accept path와 blocked/no-op path를 함께 보려면 아래 helper를 사용한다.

```bash
ops/ci/run_support_workflow_operator_baseline.sh
```

- helper override seam:
  - `VULD_SUPPORT_BASELINE_SEQUENCE_HELPER`
  - `VULD_SUPPORT_BASELINE_REVIEWABLE_HELPER`
  - `VULD_SUPPORT_BASELINE_BLOCKED_HELPER`
- helper는 generic bundle executor `ops/ci/run_helper_sequence.sh`를 재사용한다.

## Positive Pair Promotion Check

positive Docker-enabled pair의 promotion 경계를 직접 재현하고 싶으면 아래 command chain을 사용한다.

```bash
ops/ci/run_positive_pair_promotion_check.sh

# 또는 underlying command chain
python tests/e2e/repeat_case.py --case tests/e2e/cases/trusted-dynamic-sqli --expectations tests/e2e/cases/trusted-dynamic-sqli/expectations.json --mode deterministic --no-snapshot --output-dir /tmp/vuld_repeat_trusted_dynamic
python tests/e2e/repeat_case.py --case tests/e2e/cases/open-redirect-dynamic-name-only --expectations tests/e2e/cases/open-redirect-dynamic-name-only/expectations.json --mode deterministic --no-snapshot --output-dir /tmp/vuld_repeat_open_redirect_dynamic
python tests/e2e/support_review.py /tmp/vuld_repeat_trusted_dynamic /tmp/vuld_repeat_open_redirect_dynamic --output /tmp/vuld_support_review_positive_pair.json
```

- helper override seam:
  - `VULD_POSITIVE_PAIR_PRESET_HELPER`
  - `VULD_POSITIVE_PAIR_PYTHON_BIN`
  - `VULD_POSITIVE_PAIR_CASES_ROOT`
  - `VULD_POSITIVE_PAIR_OUTPUT_ROOT`
  - `VULD_POSITIVE_PAIR_MODE`
  - `VULD_POSITIVE_PAIR_NO_SNAPSHOT`
  - `VULD_POSITIVE_PAIR_PERMISSION_ARTIFACT_NAME`
  - `VULD_POSITIVE_PAIR_PERMISSION_SUMMARY_NAME`
  - `VULD_POSITIVE_PAIR_DOCKER_RETRY_COUNT`
  - `VULD_POSITIVE_PAIR_DOCKER_RETRY_DELAY_SEC`
  - `VULD_POSITIVE_PAIR_NAMED_SUPPORT_HELPER`
  - `VULD_POSITIVE_PAIR_SUPPORT_HELPER`
- helper는 latest slice에서 generic `ops/ci/run_named_preset_case_set.sh`, `ops/ci/run_named_support_case_set.sh`를 통해 `trusted_dynamic`, `open_redirect_dynamic` alias output path를 구성하고, review-only `ops/ci/run_support_workflow_chain.sh`와 `support_review_positive_pair.json` filename contract를 재사용한다.
- latest current truth는 `authority_ready_bundle_count=2`, `measured_gate_blocked_bundle_count=2`, `reviewable_bundle_count=0`이며, 이 pair는 `runnable but not promotable` regression으로 읽는다.
- latest slice 이후 same helper는 first `repeat_case.py`가 nonzero여도 `repeatability_report.json`이 생성된 blocked lane에서는 support review까지 계속 진행한다. same `ops/ci/run_repeatability_chain.sh`에는 transient docker readiness retry seam(`VULD_REPEAT_CHAIN_DOCKER_RETRY_COUNT`, `VULD_REPEAT_CHAIN_DOCKER_RETRY_DELAY_SEC`)이 있고, sandbox helper run에서 `docker daemon permission denied`가 나오면 `docker_permission_artifact.txt` marker와 note를 남긴다. unrestricted Docker-enabled direct rerun에서는 same helper가 다시 `blocked_mixed` aggregate truth와 정렬된다. 아래 underlying manual chain은 계속 가장 직접적인 step-by-step reproduction path로 남는다.
- current workspace-local direct verification에서는 same sandbox helper output이 `support_candidate_file_count=2`, `authority_ready_bundle_count=0`, `measured_gate_blocked_bundle_count=0`, `reviewable_bundle_count=0`, `by_support_status={}` empty aggregate로 끝날 수도 다시 확인됐다. 이 경우 helper output을 runtime-equivalent truth로 읽지 말고, unrestricted helper rerun 또는 아래 manual chain을 우선한다.
- same workspace-local direct verification에서는 helper가 남긴 per-case `repeatability_report.json`도 `passed=false`와 blocker `case_failed`를 보일 수 있었고, latest audit2 rerun에서는 `quality_tier_inconsistent`, `verdict_authority_inconsistent`도 같이 남았다. 이는 core measured truth 변화가 아니라 permission-artifact environment output이며 계속 `TKT-008-B3`로만 읽는다.
- same output root의 `permission_artifact_summary.json`는 `runtime_equivalent_helper_truth_available=false`, `recommended_action=unrestricted_docker_rerun`를 남긴다. current operator interpretation에서도 이 JSON을 helper output caveat의 machine-readable source로 읽는다.

## Generic Repeatability Chain

임의 case slug 집합에 대해 generic `repeat_case.py` 반복 실행 흐름만 재현하려면 아래 helper를 사용한다.

```bash
ops/ci/run_repeatability_chain.sh foobar-name-only-negative open-redirect-strict-dynamic-no-remote

# alias output path와 blocked-lane continuation이 필요하면
VULD_REPEAT_CHAIN_ALLOW_FAILURE_WITH_REPORT=1 \
  ops/ci/run_repeatability_chain.sh trusted-dynamic-sqli=trusted_dynamic open-redirect-dynamic-name-only=open_redirect_dynamic
```

- helper override seam:
  - `VULD_REPEAT_CHAIN_PYTHON_BIN`
  - `VULD_REPEAT_CHAIN_CASES_ROOT`
  - `VULD_REPEAT_CHAIN_OUTPUT_ROOT`
  - `VULD_REPEAT_CHAIN_MODE`
  - `VULD_REPEAT_CHAIN_ATTEMPTS`
  - `VULD_REPEAT_CHAIN_NO_SNAPSHOT`
  - `VULD_REPEAT_CHAIN_ALLOW_FAILURE_WITH_REPORT`
  - `VULD_REPEAT_CHAIN_DOCKER_RETRY_COUNT`
  - `VULD_REPEAT_CHAIN_DOCKER_RETRY_DELAY_SEC`
  - `VULD_REPEAT_CHAIN_PERMISSION_ARTIFACT_NAME`
  - `VULD_REPEAT_CHAIN_RUN_DIRS_FILE`
  - `VULD_REPEAT_CHAIN_OUTPUT_PREFIX`
  - `VULD_REPEAT_CHAIN_LOG_PREFIX`
  - `VULD_REPEAT_CHAIN_REPORT_NAME`
- `case-slug=alias` 형식을 쓰면 `repeat_<alias>` output path를 강제할 수 있다.
- `expectations.json`가 케이스 폴더에 있으면 helper가 자동으로 `--expectations`를 붙인다.
- `VULD_REPEAT_CHAIN_ALLOW_FAILURE_WITH_REPORT=1`이면 `repeat_case.py`가 nonzero여도 `repeatability_report.json`이 생성된 lane은 계속 진행한다.
- `docker daemon permission denied`가 report에 남으면 helper는 retry 대신 permission-artifact marker(`docker_permission_artifact.txt` 기본값)를 남긴다.

## Generic Named Matrix Case Set

임의 case slug 집합을 named wrapper로 matrix helper에 넘기고 싶으면 아래 helper를 사용한다.

```bash
ops/ci/run_named_matrix_case_set.sh foobar-name-only-negative open-redirect-strict-dynamic-no-remote
```

- helper override seam:
  - `VULD_NAMED_MATRIX_HELPER`
  - `VULD_NAMED_MATRIX_PYTHON_BIN`
  - `VULD_NAMED_MATRIX_CASES_ROOT`
  - `VULD_NAMED_MATRIX_OUTPUT_ROOT`
  - `VULD_NAMED_MATRIX_MODE`
  - `VULD_NAMED_MATRIX_ATTEMPTS`
  - `VULD_NAMED_MATRIX_NO_SNAPSHOT`
  - `VULD_NAMED_MATRIX_ALLOW_REPEAT_FAILURE_WITH_REPORT`
  - `VULD_NAMED_MATRIX_PERMISSION_ARTIFACT_NAME`
  - `VULD_NAMED_MATRIX_PERMISSION_SUMMARY_NAME`
  - `VULD_NAMED_MATRIX_DOCKER_RETRY_COUNT`
  - `VULD_NAMED_MATRIX_DOCKER_RETRY_DELAY_SEC`
  - `VULD_NAMED_MATRIX_REPEAT_HELPER`
- helper는 latest slice에서 generic `ops/ci/run_repeatability_matrix_check.sh` forwarding contract를 공통화한다.

## Generic Named Case Set

named direct/support/matrix wrapper 3종이 공통으로 쓰는 generic caseset executor는 아래 helper다.

```bash
ops/ci/run_named_case_set.sh alpha-case=alpha beta-case=beta
```

- helper override seam:
  - `VULD_NAMED_CASE_TARGET_HELPER`
  - `VULD_NAMED_CASE_LOG_PREFIX`
- latest slice에서는 `run_named_direct_case_set.sh`, `run_named_support_case_set.sh`, `run_named_matrix_case_set.sh`가 이 helper를 공통 재사용한다.
- same wrapper env projection은 `ops/ci/lib_named_case_env.sh`, representative alias-set preset은 `ops/ci/lib_case_spec_presets.sh`로 공통화되며, direct regression은 각각 [tests/test_ops_ci_named_case_env.py](/home/ysw/vulDocker/tests/test_ops_ci_named_case_env.py), [tests/test_ops_ci_case_spec_presets.py](/home/ysw/vulDocker/tests/test_ops_ci_case_spec_presets.py)가 고정한다.

## Generic Named Preset Case Set

named pair/triple wrapper가 preset builder를 named wrapper로 넘길 때 공통으로 쓰는 helper는 아래와 같다.

```bash
ops/ci/run_named_preset_case_set.sh build_positive_pair_case_specs trusted-dynamic-sqli open-redirect-dynamic-name-only
ops/ci/run_named_preset_case_set.sh build_low_cost_case_specs open-redirect-strict-dynamic-no-remote open-redirect-strict-dynamic-stub foobar-name-only-negative
```

- helper override seam:
  - `VULD_NAMED_PRESET_TARGET_HELPER`
  - `VULD_NAMED_PRESET_LOG_PREFIX`
- direct regression은 [tests/test_ops_ci_named_preset_case_set.py](/home/ysw/vulDocker/tests/test_ops_ci_named_preset_case_set.py)가 고정한다.
- latest slice에서 `run_positive_pair_promotion_check.sh`, `run_blocked_noop_support_check.sh`, `run_positive_direct_validation.sh`, `run_low_cost_no_docker_validation.sh`는 same helper를 통해 preset-builder invocation까지 공통화한다.

## Repeatability Matrix Check

repeatability output을 axis rollup `matrix_report.json`까지 같이 재현하려면 아래 helper를 사용한다.

```bash
ops/ci/run_repeatability_matrix_check.sh foobar-name-only-negative open-redirect-strict-dynamic-no-remote
```

- helper override seam:
  - `VULD_REPEAT_MATRIX_PYTHON_BIN`
  - `VULD_REPEAT_MATRIX_CASES_ROOT`
  - `VULD_REPEAT_MATRIX_OUTPUT_ROOT`
  - `VULD_REPEAT_MATRIX_MODE`
  - `VULD_REPEAT_MATRIX_ATTEMPTS`
  - `VULD_REPEAT_MATRIX_NO_SNAPSHOT`
  - `VULD_REPEAT_MATRIX_ALLOW_REPEAT_FAILURE_WITH_REPORT`
  - `VULD_REPEAT_MATRIX_PERMISSION_ARTIFACT_NAME`
  - `VULD_REPEAT_MATRIX_PERMISSION_SUMMARY_NAME`
  - `VULD_REPEAT_MATRIX_DOCKER_RETRY_COUNT`
  - `VULD_REPEAT_MATRIX_DOCKER_RETRY_DELAY_SEC`
  - `VULD_REPEAT_MATRIX_REPEAT_HELPER`
- helper는 latest slice에서 generic `ops/ci/run_repeatability_chain.sh`를 재사용한 뒤, resulting run directories를 `tests/e2e/matrix_report.py`에 넘겨 `matrix_report.json`을 materialize한다.
- `expectations.json`가 케이스 폴더에 있으면 helper가 자동으로 `--expectations`를 붙인다.
- helper는 output root에 machine-readable `permission_artifact_summary.json`도 남기며, `VULD_REPEAT_MATRIX_PERMISSION_SUMMARY_NAME`으로 filename을 바꿀 수 있다.
- latest slice에서는 `summary.json`이 없는 repeatability-only run directory도 직접 rollup할 수 있어서, planning-only no-Docker pair의 real helper run도 `matrix_report.json`까지 끝까지 materialize한다.

## Measured Gate Operator Baseline

planning-only measured preview와 positive pair promotion check를 한 번에 보려면 아래 helper를 사용한다.

```bash
ops/ci/run_measured_gate_operator_baseline.sh
```

- helper override seam:
  - `VULD_MEASURED_BASELINE_PRESET_HELPER`
  - `VULD_MEASURED_BASELINE_NAMED_MATRIX_HELPER`
  - `VULD_MEASURED_BASELINE_SEQUENCE_HELPER`
  - `VULD_MEASURED_BASELINE_MATRIX_HELPER`
  - `VULD_MEASURED_BASELINE_PROMOTION_HELPER`
  - `VULD_MEASURED_BASELINE_MATRIX_CASE_A`
  - `VULD_MEASURED_BASELINE_MATRIX_CASE_B`
  - `VULD_MEASURED_BASELINE_PERMISSION_SUMMARY_NAME`
- helper는 latest slice에서 generic `ops/ci/run_named_preset_case_set.sh`, `ops/ci/run_named_matrix_case_set.sh`를 통해 planning-only matrix pair wiring을 공통화한다.
- current default는 planning-only pair matrix preview(`foobar-name-only-negative`, `open-redirect-strict-dynamic-no-remote`)와 positive pair promotion check를 순서대로 실행한다.
- helper는 generic bundle executor `ops/ci/run_helper_sequence.sh`를 재사용한다.

## Focused No-Docker Regression Slice

direct case rerun 전에 policy/honesty/measured-support surface만 빠르게 preflight하고 싶으면 아래 pytest slice를 먼저 돌린다.

```bash
ops/ci/run_focused_no_docker_regression.sh

# 또는 underlying pytest slice
python -m pytest -q tests/test_name_only_helpers.py tests/test_pack_promotion.py tests/test_repeatability_gate.py tests/test_support_extract.py tests/e2e/test_support_workflow.py tests/e2e/test_case_matrix_rollup.py
```

- helper override seam:
  - `VULD_FOCUSED_NO_DOCKER_PYTEST_BIN`
- 이 slice는 `TKT-001-E`, `TKT-008-A1`, `TKT-009-A2`에 가장 가까운 fastest no-Docker regression net이다.
- latest direct verification pass/fail truth는 [docs/current_state_gap_analysis.md](../docs/current_state_gap_analysis.md)의 latest rerun table에서 읽는다.

## Pytest 연동

E2E 실행은 옵트인 방식이다. `VULD_RUN_E2E=1`을 설정하고 Docker 접근 권한을 확보하면
`pytest -m e2e`가 케이스를 실제로 실행한다. 환경 변수가 없으면 테스트가 자동으로 skip되어
기본 스위트 속도를 유지한다.

CI 엔트리 포인트 `ops/ci/run_e2e_tests.sh`는 각 케이스의 필수 파일을 확인한 뒤 `pytest -m e2e`를 호출한다.

반복 재현성 게이트는 별도 opt-in이다.

- `VULD_RUN_E2E_REPEAT=1 pytest -m e2e -k cwe89_basic_repeatability_gate`
- 또는 `bash ops/ci/run_repeatability_gate.sh cwe-89-basic 3 deterministic /tmp/vuld_cwe89_repeatability`
- CI chaining까지 함께 돌리려면 `VULD_RUN_E2E=1 VULD_RUN_E2E_REPEAT=1 bash ops/ci/run_e2e_tests.sh`
- repeatability case를 바꾸려면 `VULD_E2E_REPEAT_CASE_DIR=open-redirect-strict-dynamic-no-remote`처럼 slug만 넘기거나, 기존처럼 `tests/e2e/cases/open-redirect-strict-dynamic-no-remote` path를 넘긴다.
- current canonical repeatability entry는 direct helper invocation과 `run_e2e_tests.sh` repeatability chaining 둘 다 지원한다.
- helper와 CI chaining 둘 다 `repeatability_report.json.passed=false`이면 nonzero로 실패한다.
- ops helper contract regression은 `ops/ci/run_ops_helper_contract_regression.sh`와 `tests/test_ops_ci_*.py` bundle을 본다. helper는 current `tests/test_ops_ci_*.py` glob set 전체를 실제로 forward하며, [tests/test_ops_ci_helper_contract_regression.py](/home/ysw/vulDocker/tests/test_ops_ci_helper_contract_regression.py) 가 그 contract를 고정한다. `VULD_OPS_HELPER_TEST_GLOB`로 custom bundle을, `VULD_OPS_HELPER_PRINT_BUNDLE=1`로 resolved file list 출력을 강제할 수 있다. current workspace-local result는 `343 passed`다.
- latest slice에서는 `ops/ci/lib_repeatability_chain_env.sh`와 [tests/test_ops_ci_repeatability_chain_env.py](/home/ysw/vulDocker/tests/test_ops_ci_repeatability_chain_env.py)가 support/matrix helper의 `VULD_REPEAT_CHAIN_*` export 공통 contract를 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_repeatability_helper_contract.sh`와 [tests/test_ops_ci_repeatability_helper_contract.py](/home/ysw/vulDocker/tests/test_ops_ci_repeatability_helper_contract.py)가 support/matrix helper의 repeat-helper executable gate contract를 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_named_case_helper_contract.sh`와 [tests/test_ops_ci_named_case_helper_contract.py](/home/ysw/vulDocker/tests/test_ops_ci_named_case_helper_contract.py)가 `run_named_case_set.sh` / `run_named_preset_case_set.sh`의 target-helper executable gate contract를 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_case_spec_preset_contract.sh`와 [tests/test_ops_ci_case_spec_preset_contract.py](/home/ysw/vulDocker/tests/test_ops_ci_case_spec_preset_contract.py)가 `run_named_preset_case_set.sh`의 preset-builder required/known gate contract를 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_named_case_env.sh`와 [tests/test_ops_ci_named_case_dispatch.py](/home/ysw/vulDocker/tests/test_ops_ci_named_case_dispatch.py)가 named direct/support/matrix wrapper의 common caseset dispatch contract도 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_operator_direct_named_preset.sh`와 [tests/test_ops_ci_operator_direct_named_preset.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_direct_named_preset.py)가 positive direct / low-cost direct wrapper의 validate -> env export -> preset helper invoke contract도 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_operator_direct_case_check.sh`와 [tests/test_ops_ci_operator_direct_case_check.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_direct_case_check.py)가 positive direct / low-cost direct wrapper의 shared direct case-check skeleton contract도 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_operator_pair_case_check.sh`와 [tests/test_ops_ci_operator_pair_case_check.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_pair_case_check.py)가 direct/support wrapper family의 shared pair case-check skeleton contract도 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_operator_cases_output_roots.sh`와 [tests/test_ops_ci_operator_cases_output_roots.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_cases_output_roots.py)가 direct/support pair wrapper family의 cases/output-root default resolution contract도 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_operator_support_named_preset.sh`와 [tests/test_ops_ci_operator_support_named_preset.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_support_named_preset.py)가 positive pair / blocked-noop support wrapper의 validate -> env export -> preset helper invoke contract도 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_operator_support_pair_check.sh`와 [tests/test_ops_ci_operator_support_pair_check.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_support_pair_check.py)가 positive pair / blocked-noop support wrapper의 shared named-preset pair skeleton contract도 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_operator_named_preset_runner.sh`와 [tests/test_ops_ci_operator_named_preset_runner.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_named_preset_runner.py)가 direct/support operator pair wrapper의 shared validate -> env export -> preset helper invoke skeleton contract도 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_operator_pair_named_preset.sh`와 [tests/test_ops_ci_operator_pair_named_preset.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_pair_named_preset.py)가 direct/support named-preset thin wrapper의 pair-runner primitive contract도 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_operator_pair_named_preset_defaults.sh`와 [tests/test_ops_ci_operator_pair_named_preset_defaults.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_pair_named_preset_defaults.py)가 direct/support named-preset wrapper의 named/preset/leaf helper default resolution contract도 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_operator_case_defaults.sh`와 [tests/test_ops_ci_operator_case_defaults.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_case_defaults.py)가 direct/support wrapper family의 single/pair/triple/batch case-slug default resolution contract도 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_operator_output_notes.sh`와 [tests/test_ops_ci_operator_output_notes.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_output_notes.py)가 direct/support wrapper family의 completion/output note primitive contract도 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_operator_output_root_notes.sh`와 [tests/test_ops_ci_operator_output_root_notes.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_output_root_notes.py)가 direct/support wrapper family의 output-root child note primitive contract도 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_case_expectations.sh`와 [tests/test_ops_ci_case_expectations.py](/home/ysw/vulDocker/tests/test_ops_ci_case_expectations.py)가 direct/repeatability helper family의 default `expectations.json` auto-discovery와 `--expectations` argv append contract도 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_case_command_surface.sh`, [tests/test_ops_ci_case_command_surface.py](/home/ysw/vulDocker/tests/test_ops_ci_case_command_surface.py), [tests/test_ops_ci_direct_validation_chain.py](/home/ysw/vulDocker/tests/test_ops_ci_direct_validation_chain.py), [tests/test_ops_ci_repeatability_chain.py](/home/ysw/vulDocker/tests/test_ops_ci_repeatability_chain.py)가 direct/repeatability helper family의 shared `run_case.py` / `repeat_case.py` argv assembly, expectations append, `--no-snapshot` contract도 direct regression으로 고정한다.
- same helper family에서는 `ops/ci/lib_case_chain_entry.sh`, [tests/test_ops_ci_case_chain_entry.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_entry.py), [tests/test_ops_ci_direct_validation_chain.py](/home/ysw/vulDocker/tests/test_ops_ci_direct_validation_chain.py), [tests/test_ops_ci_repeatability_chain.py](/home/ysw/vulDocker/tests/test_ops_ci_repeatability_chain.py)가 direct/repeatability helper family의 usage check, output-root prep, entry preflight contract도 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_case_chain_output_notes.sh`, [tests/test_ops_ci_case_chain_output_notes.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_output_notes.py), [tests/test_ops_ci_direct_validation_chain.py](/home/ysw/vulDocker/tests/test_ops_ci_direct_validation_chain.py), [tests/test_ops_ci_repeatability_chain.py](/home/ysw/vulDocker/tests/test_ops_ci_repeatability_chain.py)가 direct/repeatability helper family의 case-output log, run-dirs file write, completion note contract도 direct regression으로 고정한다.
- same helper family에서는 `ops/ci/lib_case_spec_resolution.sh`와 [tests/test_ops_ci_case_spec_resolution.py](/home/ysw/vulDocker/tests/test_ops_ci_case_spec_resolution.py)가 direct/repeatability helper family의 `case=alias` split, case-dir path resolution, alias/path safety validation뿐 아니라 case-context capture, resolved output-name/safe-slug helper, named output-context export contract도 direct regression으로 고정한다.
- same helper family에서는 `ops/ci/lib_repeatability_report_failures.sh`, [tests/test_ops_ci_repeatability_report_failures.py](/home/ysw/vulDocker/tests/test_ops_ci_repeatability_report_failures.py), [tests/test_ops_ci_repeatability_chain.py](/home/ysw/vulDocker/tests/test_ops_ci_repeatability_chain.py)가 direct/repeatability helper family의 repeatability report Docker failure classification, retry gate input, permission-marker writer contract도 direct regression으로 고정한다.
- same helper family에서는 `ops/ci/lib_repeatability_case_failure.sh`, [tests/test_ops_ci_repeatability_case_failure.py](/home/ysw/vulDocker/tests/test_ops_ci_repeatability_case_failure.py), [tests/test_ops_ci_repeatability_chain.py](/home/ysw/vulDocker/tests/test_ops_ci_repeatability_chain.py)가 direct/repeatability helper family의 repeatability case-failure action resolution, retry/continue/fail routing, permission-marker-aware continue contract도 direct regression으로 고정한다.
- same helper family에서는 `ops/ci/lib_repeatability_case_runtime.sh`, [tests/test_ops_ci_repeatability_case_runtime.py](/home/ysw/vulDocker/tests/test_ops_ci_repeatability_case_runtime.py), [tests/test_ops_ci_repeatability_chain.py](/home/ysw/vulDocker/tests/test_ops_ci_repeatability_chain.py)가 direct/repeatability helper family의 repeatability case context hydration, report-path resolution, run-dir append, `repeat_case.py` argv assembly contract도 direct regression으로 고정한다.
- same helper family에서는 `ops/ci/lib_direct_case_runtime.sh`, [tests/test_ops_ci_direct_case_runtime.py](/home/ysw/vulDocker/tests/test_ops_ci_direct_case_runtime.py), [tests/test_ops_ci_direct_validation_chain.py](/home/ysw/vulDocker/tests/test_ops_ci_direct_validation_chain.py)가 direct/repeatability helper family의 direct case context hydration, output-dir resolution, `run_case.py` argv assembly contract도 direct regression으로 고정한다.
- same helper family에서는 `ops/ci/lib_direct_case_runner.sh`, [tests/test_ops_ci_direct_case_runner.py](/home/ysw/vulDocker/tests/test_ops_ci_direct_case_runner.py), [tests/test_ops_ci_direct_validation_chain.py](/home/ysw/vulDocker/tests/test_ops_ci_direct_validation_chain.py)가 direct/repeatability helper family의 direct case runtime reuse, output note emission, `run_case.py` command invoke contract도 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_case_chain_profile_target_forward.sh`, [tests/test_ops_ci_case_chain_profile_target_forward.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_profile_target_forward.py), [tests/test_ops_ci_case_chain_profile_entrypoint.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_profile_entrypoint.py), [tests/test_ops_ci_case_chain_main.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_main.py), [tests/test_ops_ci_case_chain_main_script.py](/home/ysw/vulDocker/tests/test_ops_ci_case_chain_main_script.py), [tests/test_ops_ci_direct_validation_chain.py](/home/ysw/vulDocker/tests/test_ops_ci_direct_validation_chain.py), [tests/test_ops_ci_repeatability_chain.py](/home/ysw/vulDocker/tests/test_ops_ci_repeatability_chain.py)가 direct/repeatability profile wrapper family의 shared `profile target forward` contract를 direct regression으로 고정한다.
- same support/matrix helper family에서는 `ops/ci/lib_repeatability_chain_runner.sh`와 [tests/test_ops_ci_repeatability_chain_runner.py](/home/ysw/vulDocker/tests/test_ops_ci_repeatability_chain_runner.py)가 repeat-helper invoke, env export, run-dir postprocess skeleton contract도 direct regression으로 고정한다.
- same support workflow/reviewable accept helper family에서는 `ops/ci/lib_support_review_runner.sh`와 [tests/test_ops_ci_support_review_runner.py](/home/ysw/vulDocker/tests/test_ops_ci_support_review_runner.py)가 review-helper invoke, env export, run-dir preflight skeleton contract도 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_support_review_output_surface.sh`, [tests/test_ops_ci_support_review_output_surface.py](/home/ysw/vulDocker/tests/test_ops_ci_support_review_output_surface.py), [tests/test_ops_ci_support_workflow_chain.py](/home/ysw/vulDocker/tests/test_ops_ci_support_workflow_chain.py)가 support review helper family의 prefix-aware output-name default resolution + resolved output-path materialization contract를 direct regression으로 고정하고, `run_support_review_chain.sh`, `run_reviewable_support_accept_check.sh`, `run_support_workflow_chain.sh`가 same resolved output-surface contract를 재사용한다. latest slice에서는 generic `VULD_SUPPORT_REVIEW_RESOLVED_*`뿐 아니라 `${PREFIX}_RESOLVED_*` output surface도 같이 닫는다.
- latest slice에서는 `ops/ci/lib_operator_export_helper_contract.sh`와 [tests/test_ops_ci_operator_export_helper_contract.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_export_helper_contract.py)가 named-preset runner와 matrix baseline sequence family의 export-helper function gate + invocation primitive contract도 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_operator_runtime_sequence.sh`와 [tests/test_ops_ci_operator_runtime_sequence.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_runtime_sequence.py)가 measured/support/docker-positive baseline wrapper의 runtime-surface forwarding + sequence invocation contract도 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_operator_pair_runtime_baseline.sh`와 [tests/test_ops_ci_operator_pair_runtime_baseline.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_pair_runtime_baseline.py)가 support workflow/docker-positive baseline wrapper의 two-step runtime baseline contract도 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_operator_pair_runtime_baseline_defaults.sh`와 [tests/test_ops_ci_operator_pair_runtime_baseline_defaults.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_pair_runtime_baseline_defaults.py)가 support workflow/docker-positive baseline wrapper의 helper/default resolution contract도 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_operator_helper_defaults.sh`와 [tests/test_ops_ci_operator_helper_defaults.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_helper_defaults.py)가 pair/matrix/current defaults library가 공유하는 helper-default single/batch resolution primitive도 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_operator_matrix_case_pair.sh`와 [tests/test_ops_ci_operator_matrix_case_pair.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_matrix_case_pair.py)가 measured/no-docker baseline wrapper의 planning-only matrix pair default/partial-override contract도 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_operator_matrix_baseline_defaults.sh`와 [tests/test_ops_ci_operator_matrix_baseline_defaults.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_matrix_baseline_defaults.py)가 measured/no-docker baseline wrapper의 matrix helper/default resolution contract도 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_operator_matrix_baseline_sequence.sh`와 [tests/test_ops_ci_operator_matrix_baseline_sequence.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_matrix_baseline_sequence.py)가 measured/no-docker matrix baseline wrapper의 matrix env export + runtime-surface + sequence invocation contract도 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_operator_current_baseline_defaults.sh`와 [tests/test_ops_ci_operator_current_baseline_defaults.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_current_baseline_defaults.py)가 current baseline의 helper/default resolution contract도 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_operator_current_baseline_sequence.sh`와 [tests/test_ops_ci_operator_current_baseline_sequence.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_current_baseline_sequence.py)가 current baseline의 child-surface forwarding + sequence invocation contract도 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_operator_sequence_helper_contract.sh`와 [tests/test_ops_ci_operator_sequence_helper_contract.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_sequence_helper_contract.py)가 runtime/current/matrix baseline family의 sequence-helper executable gate + invocation primitive contract도 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_operator_retry_env.sh`와 [tests/test_ops_ci_operator_retry_env.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_retry_env.py)가 top-level operator baseline의 single-target runtime surface와 multi-target retry/permission forwarding contract도 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_repeatability_run_dirs.sh`와 [tests/test_ops_ci_repeatability_run_dirs.py](/home/ysw/vulDocker/tests/test_ops_ci_repeatability_run_dirs.py)가 support/matrix helper의 repeat-run-dir file load/validation contract를 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_repeatability_postprocess.sh`와 [tests/test_ops_ci_repeatability_postprocess.py](/home/ysw/vulDocker/tests/test_ops_ci_repeatability_postprocess.py)가 support/matrix helper의 repeat post-process(run-dir load + permission note + summary materialization) contract를 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_support_review_env.sh`, [tests/test_ops_ci_support_review_env.py](/home/ysw/vulDocker/tests/test_ops_ci_support_review_env.py), `ops/ci/lib_support_review_output_defaults.sh`, [tests/test_ops_ci_support_review_output_defaults.py](/home/ysw/vulDocker/tests/test_ops_ci_support_review_output_defaults.py), `ops/ci/lib_support_review_output_notes.sh`, [tests/test_ops_ci_support_review_output_notes.py](/home/ysw/vulDocker/tests/test_ops_ci_support_review_output_notes.py), `ops/ci/lib_support_review_outputs.sh`, [tests/test_ops_ci_support_review_outputs.py](/home/ysw/vulDocker/tests/test_ops_ci_support_review_outputs.py)가 support review helper family의 env/prefix-aware-output-name/output-note/output-path contract를 direct regression으로 고정하고, latest slice에서는 `support_review_emit_prefixed_*` helpers와 backward-compatible `support_review_emit_resolved_*` wrappers까지 same note family로 닫는다.
- latest slice에서는 `ops/ci/lib_support_review_helper_contract.sh`와 [tests/test_ops_ci_support_review_helper_contract.py](/home/ysw/vulDocker/tests/test_ops_ci_support_review_helper_contract.py)가 support review helper family의 review-helper executable gate와 decisions-file materialization contract도 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_support_review_run_dirs.sh`와 [tests/test_ops_ci_support_review_run_dirs.py](/home/ysw/vulDocker/tests/test_ops_ci_support_review_run_dirs.py)가 support review helper family의 run-directory validation contract도 direct regression으로 고정한다.
- latest slice에서는 `ops/ci/lib_permission_artifact_summary.sh`와 [tests/test_ops_ci_permission_artifact_summary.py](/home/ysw/vulDocker/tests/test_ops_ci_permission_artifact_summary.py) 가 machine-readable permission summary contract를 direct regression으로 고정하고, matrix helper family도 `VULD_REPEAT_MATRIX_PERMISSION_SUMMARY_NAME`, `VULD_NAMED_MATRIX_PERMISSION_SUMMARY_NAME`, `VULD_MEASURED_BASELINE_PERMISSION_SUMMARY_NAME`, `VULD_NO_DOCKER_BASELINE_PERMISSION_SUMMARY_NAME`으로 filename override를 공유한다.

- latest slice에서는 operator pair/triple wrapper 공통부도 더 줄었다. `lib_operator_named_case_env.sh`, `lib_operator_baseline_matrix_env.sh`, `lib_operator_retry_env.sh`, `lib_operator_named_preset_helpers.sh`가 각각 env projection과 preset/named/leaf helper executable gate를 공통화하고, [test_ops_ci_operator_named_case_env.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_named_case_env.py), [test_ops_ci_operator_baseline_matrix_env.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_baseline_matrix_env.py), [test_ops_ci_operator_retry_env.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_retry_env.py), [test_ops_ci_operator_named_preset_helpers.py](/home/ysw/vulDocker/tests/test_ops_ci_operator_named_preset_helpers.py) 가 same contract를 direct regression으로 고정한다.

반복 게이트는 `cwe-89-basic`을 3회 연속 실행하고, 각 시도의 `summary.json`, 마지막 `failure_fingerprint`,
`guard_error_code`, `loop_state` tail을 `repeatability_report.json`으로 집계한다. 현재 repeatability report는
`matrix_axes`, attempt별 `search_cache_*`/`search_executed_query_count`/`search_early_stop_triggered`,
`artifact_quality_band`/`artifact_quality_qualitative_tier`/`oracle_execution_parity`,
aggregate `cache_reuse_observed`, `cache_reuse_consistent`, `executed_query_reduction_observed`도 함께 담는다.

## Ticket Mapping

- `run_case.py`와 `pytest -m e2e` representative rerun은 주로 `TKT-001` ~ `TKT-007`의 direct workflow sanity를 확인한다.
- `repeat_case.py`, `matrix_report.py`, `support_review.py`, `support_decide.py`, `support_apply.py`는 주로 `TKT-008`, `TKT-009` measured/support workflow를 확인한다.
- `run_repeatability_chain.sh`는 `TKT-008` / `TKT-009` helper surface에서 generic repeatability pre-chain을 재현하는 baseline helper다.
- `run_repeatability_matrix_check.sh`는 `TKT-008` measured preview를 operator baseline 형태로 재현하는 대표 helper다.
- `run_support_workflow_chain.sh`는 `TKT-009` measured/manual review-update-apply 흐름을 arbitrary case set에 대해 재현하는 generic helper다.
- `Focused No-Docker Regression Slice`는 direct case rerun 전 `TKT-001-E`, `TKT-008-A1`, `TKT-009-A2` low-cost preflight에 가장 적합하다.
- latest low-cost no-Docker pair (`foobar-name-only-negative`, `open-redirect-strict-dynamic-no-remote`)는 `TKT-008-A1`, `TKT-009-A2` blocked/no-op policy regression의 기본 rehearsal pair다.
- `open-redirect-strict-dynamic-stub`는 `TKT-001-E` strict capability-gate fail-closed subclass regression의 기본 no-Docker lane이다.
- `trusted-dynamic-sqli`는 fixture-backed positive LLM-shaped lane으로, latest Docker-enabled rerun에서는 `llm_fixture` / `llm_manifest` positive materialization sanity를 확인하는 representative lane으로 읽는다. 다만 current measured/support gate 기준으로는 아직 promotable closure가 아니다.
- `open-redirect-dynamic-name-only`는 representative dynamic Docker-enabled lane으로, latest rerun에서는 `llm_degraded` / `deterministic_fallback` / `partial` current truth를 확인하는 대표 regression lane으로 읽는다. ticket 해석상 `TKT-001`, `TKT-006`, `TKT-008-A1/A2`에 가장 가깝다.
- latest positive Docker-enabled pair(`trusted-dynamic-sqli`, `open-redirect-dynamic-name-only`)는 새 ticket를 만드는 근거가 아니라 existing `TKT-001`, `TKT-006`, `TKT-008-A*`, `TKT-009-A1` residual을 recurring regression으로 재확인하는 pair다.
- same positive pair의 `repeat_case.py -> support_review.py`는 current truth 기준 `authority_ready_bundle_count=2`, `measured_gate_blocked_bundle_count=2`, `reviewable_bundle_count=0`를 다시 확인하는 representative promotion-closure regression이다.
- current workspace-local sandbox helper output이 same positive pair에서 `authority_ready_bundle_count=0`, `reviewable_bundle_count=0`, `by_support_status={}` empty aggregate로 끝나는 latest finding도 `TKT-008-B3` companion residual로 읽는다. same output은 runtime-equivalent truth가 아니라 permission-artifact environment output이며, underlying manual chain 또는 unrestricted helper rerun이 authoritative reproduction path다.
- same positive pair의 helper wrapper(`ops/ci/run_positive_pair_promotion_check.sh`)는 sandbox helper run에서 `docker daemon permission denied` permission artifact note와 marker를 남길 수 있다. unrestricted Docker-enabled rerun에서는 다시 same `blocked_mixed` aggregate current truth와 정렬되며, 이 bounded environment distinction을 `TKT-008-B3` companion/operator stabilization residual로 읽는다. 같은 섹션의 underlying manual chain은 계속 가장 직접적인 reproduction path다.
- 이 하니스는 current bounded closure를 regression으로 고정하는 용도이며, `TKT-010` expansion readiness를 단독으로 증명하지는 않는다.

## Validation Companions

하니스 관점에서 이 문서와 같이 봐야 할 companion은 아래와 같다.

- success criteria 5축과 backlog owner 대응: [docs/work_tickets.md](../docs/work_tickets.md)의 `Open-World Completion Axis Map`
- completion companion set: [docs/work_tickets.md](../docs/work_tickets.md)의 `Completion Companions`
- priority companion set: [docs/work_tickets.md](../docs/work_tickets.md)의 `Priority Companions`
- success criteria 5축의 완료판정 질문과 최소 근거: [docs/work_tickets.md](../docs/work_tickets.md)의 `Open-World Completion Checklist`
- success criteria 5축의 canonical 완료 검토 순서: [docs/work_tickets.md](../docs/work_tickets.md)의 `Open-World Completion Review Flow`
- success criteria 5축의 canonical 완료판정 reading order: [docs/work_tickets.md](../docs/work_tickets.md)의 `Open-World Completion Reading Order`
- latest confirmed residual의 축별 ticket bundle 분해: [docs/work_tickets.md](../docs/work_tickets.md)의 `Open-World Residual Ticket Breakdown`
- latest residual의 concise ticket-form summary: [docs/work_tickets.md](../docs/work_tickets.md)의 `Current Remaining Ticket Form`
- latest residual의 shorthand ticket routing: [docs/work_tickets.md](../docs/work_tickets.md)의 `Current Remaining Ticket Routing`
- latest direct verification까지 반영한 current completion priority order: [docs/work_tickets.md](../docs/work_tickets.md)의 `Confirmed Completion Priority Order`
- 잔여 작업량과 practical turn envelope: [docs/work_tickets.md](../docs/work_tickets.md)의 `Estimated Turn Envelope`
- latest confirmed residual의 canonical 구현 검토 순서: [docs/work_tickets.md](../docs/work_tickets.md)의 `Open-World Residual Review Flow`
- latest confirmed residual 검토 문서 순서: [docs/work_tickets.md](../docs/work_tickets.md)의 `Open-World Residual Reading Order`
- residual companion set: [docs/work_tickets.md](../docs/work_tickets.md)의 `Residual Companions`
- review mode별 canonical 시작점: [docs/work_tickets.md](../docs/work_tickets.md)의 `Review Mode Matrix`
- 우선순위 판단 routing: [docs/work_tickets.md](../docs/work_tickets.md)의 `Priority Question Routing`, `Priority Reading Order`, `Assessment-To-Ticket Interpretation`
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
- priority companion set: [docs/work_tickets.md](../docs/work_tickets.md)의 `Priority Companions`
- axis map / close criteria / canonical review order: [docs/work_tickets.md](../docs/work_tickets.md)의 `Open-World Completion Axis Map`, `Open-World Completion Checklist`, `Open-World Completion Review Flow`
- canonical completion reading order: [docs/work_tickets.md](../docs/work_tickets.md)의 `Open-World Completion Reading Order`
- current completion priority order: [docs/work_tickets.md](../docs/work_tickets.md)의 `Confirmed Completion Priority Order`
- phase acceptance map: [docs/final_solution.md](../docs/final_solution.md)의 `Acceptance-To-Validation Translation`
- code entrypoint: [docs/code/README.md](../docs/code/README.md)
- artifact reading / troubleshooting: [docs/handbook.md](../docs/handbook.md)
- current truth / non-claim: [docs/current_state_gap_analysis.md](../docs/current_state_gap_analysis.md), [docs/constraints.md](../docs/constraints.md)

## Residual Companions

하니스/잔여 구현 검토 관점에서 이 문서와 같이 봐야 할 companion은 아래와 같다.

- residual bucket / ticket bundle: [docs/work_tickets.md](../docs/work_tickets.md)의 `Open-World Residual Ticket Breakdown`
- current completion priority order: [docs/work_tickets.md](../docs/work_tickets.md)의 `Confirmed Completion Priority Order`
- residual close criteria: [docs/work_tickets.md](../docs/work_tickets.md)의 `Open-World Completion Checklist`
- residual review / reading order: [docs/work_tickets.md](../docs/work_tickets.md)의 `Open-World Residual Review Flow`, `Open-World Residual Reading Order`
- phase acceptance map: [docs/final_solution.md](../docs/final_solution.md)의 `Acceptance-To-Validation Translation`
- code entrypoint / residual focus: [docs/code/README.md](../docs/code/README.md)
- artifact reading / troubleshooting: [docs/handbook.md](../docs/handbook.md)
- current truth / non-claim: [docs/current_state_gap_analysis.md](../docs/current_state_gap_analysis.md), [docs/constraints.md](../docs/constraints.md)

## Priority Companions

하니스/우선순위 판단 관점에서 이 문서와 같이 봐야 할 companion은 아래와 같다.

- current completion priority order: [docs/work_tickets.md](../docs/work_tickets.md)의 `Confirmed Completion Priority Order`
- 잔여 작업량과 practical turn envelope: [docs/work_tickets.md](../docs/work_tickets.md)의 `Estimated Turn Envelope`
- priority companion set / routing / reading order: [docs/work_tickets.md](../docs/work_tickets.md)의 `Priority Companions`, `Priority Question Routing`, `Priority Reading Order`
- latest positive representative pair의 ticket-form reading: [docs/work_tickets.md](../docs/work_tickets.md)의 `Assessment-To-Ticket Interpretation`
- LLM-response 기준 residual/priority 해석: [docs/work_tickets.md](../docs/work_tickets.md)의 `LLM-Response Capability Overlay`
- phase ordering / sequencing guardrail: [docs/final_solution.md](../docs/final_solution.md), [docs/work_tickets.md](../docs/work_tickets.md)의 `Sequencing Rule`
- current truth / non-claim: [docs/current_state_gap_analysis.md](../docs/current_state_gap_analysis.md), [docs/constraints.md](../docs/constraints.md)
- code entrypoint / artifact reading: [docs/code/README.md](../docs/code/README.md), [docs/handbook.md](../docs/handbook.md)

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
- 작업량 추산:
  - [docs/work_tickets.md](../docs/work_tickets.md)의 `Review Mode Matrix`
  - [docs/work_tickets.md](../docs/work_tickets.md)의 `Turn Estimate Entry`
- 우선순위 판단:
  - [docs/work_tickets.md](../docs/work_tickets.md)의 `Review Mode Matrix`
  - 이 문서의 `Priority Companions`
  - [docs/work_tickets.md](../docs/work_tickets.md)의 `Assessment-To-Ticket Interpretation`

## Priority Review Entry

하니스 관점에서 우선순위 판단을 시작할 때는 아래 순서를 권장한다.

1. 이 문서의 `Priority Companions`
2. [docs/work_tickets.md](../docs/work_tickets.md)의 `Confirmed Completion Priority Order`, `Estimated Turn Envelope`, `Priority Reading Order`
3. [docs/work_tickets.md](../docs/work_tickets.md)의 `LLM-Response Capability Overlay`, `Assessment-To-Ticket Interpretation`
4. 이 문서의 `Focused No-Docker Regression Slice`, `Low-Cost No-Docker Validation Lanes`
5. [docs/code/README.md](../docs/code/README.md), [docs/handbook.md](../docs/handbook.md)

turn estimate shortcut은 [docs/work_tickets.md](../docs/work_tickets.md)의 `Turn Estimate Entry`를 따른다.

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
- LLM-response stricter reading의 harness-side routing이 바뀌면 [docs/work_tickets.md](../docs/work_tickets.md)의 `LLM-Response Capability Overlay`와 같이 맞춘다.
- latest positive representative pair의 ticket-form 해석이 바뀌면 [docs/work_tickets.md](../docs/work_tickets.md)의 `Assessment-To-Ticket Interpretation`와 같이 맞춘다.
- residual companion 관계가 바뀌면 [README.md](../README.md), [docs/code/README.md](../docs/code/README.md), [docs/handbook.md](../docs/handbook.md)와 같이 맞춘다.
- residual question routing이 바뀌면 [docs/work_tickets.md](../docs/work_tickets.md)와 같이 맞춘다.
- completion review entrypoint가 바뀌면 [README.md](../README.md), [docs/code/README.md](../docs/code/README.md), [docs/handbook.md](../docs/handbook.md)와 같이 맞춘다.
- completion reading order가 바뀌면 [README.md](../README.md), [docs/code/README.md](../docs/code/README.md), [docs/handbook.md](../docs/handbook.md)와 같이 맞춘다.
- residual review entrypoint가 바뀌면 [README.md](../README.md), [docs/code/README.md](../docs/code/README.md), [docs/handbook.md](../docs/handbook.md)와 같이 맞춘다.
- residual reading order가 바뀌면 [README.md](../README.md), [docs/code/README.md](../docs/code/README.md), [docs/handbook.md](../docs/handbook.md)와 같이 맞춘다.
- review mode entry shortcuts가 바뀌면 [README.md](../README.md), [docs/code/README.md](../docs/code/README.md), [docs/handbook.md](../docs/handbook.md)와 같이 맞춘다.
- 잔여 작업량/turn envelope 해석이 바뀌면 [docs/work_tickets.md](../docs/work_tickets.md)의 `Estimated Turn Envelope`와 README/code/handbook companion의 priority routing도 같이 맞춘다.
- [docs/work_tickets.md](../docs/work_tickets.md)의 `Turn Estimate Entry`가 바뀌면 README/code/handbook companion의 same shortcut도 같이 맞춘다.
