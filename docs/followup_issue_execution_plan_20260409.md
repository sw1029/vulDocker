# Follow-up Issue Execution Plan

## 1. Scope

이 문서는 다음 후속 이슈 3개에 대한 현재 구현 상태, 남은 공백, branch/worktree 배정, 병렬 작업 순서를 정리한다.

- `#6 Add deterministic pipeline-harness audit and scorecard`
- `#8 Add observation ledger and failure-health reporting`
- `#9 Harden reviewer and verifier evidence contracts`

기준 시점:

- repo base commit: `064b54b`
- 현재 main workspace에는 governance foundation WIP가 존재한다.
- 새 worktree는 clean base commit에서 생성하고, foundation 변경이 commit되는 즉시 rebase/cherry-pick하는 것을 전제로 한다.

## 2. Current Status Snapshot

### 2.1 Issue #6: Harness Audit Scoring Rubric

현재 반영된 것:

- `ops/ci/harness_audit.py` 추가
- `manifest.json` / `failure_manifest.json` 기반 deterministic audit entrypoint 추가
- `action_trace_summary`, `stage_gate_summary`, `observation_summary`, `canonical_snapshot.json` 존재 여부를 읽는 최소 scorecard 구현
- `tests/test_harness_governance_artifacts.py`에서 audit smoke 검증 추가

현재 부족한 것:

- rubric이 binary `0/100` 위주라 quality gradient가 약함
- category 내부의 세부 check id / evidence path / severity가 없다
- `Selection Authority`, `Materialization Causality`, `Runtime Contract Parity`, `Oracle Execution Parity`, `Review Evidence Quality`, `Measured Gate Integrity`, `Cost And Retry Efficiency`를 full coverage로 분리하지 못했다
- repeatability/support workflow artifact와 교차 비교하지 않는다
- rerun lane recommendation이 고정 문자열 수준이다
- audit output이 아직 `pack`에 직접 summary surface로 연결되지는 않는다

판단:

- foundation은 완료
- deterministic presence-check 수준에서 `40~50%`
- 진짜 operator scorecard 수준으로 가려면 별도 helper module, weighted rubric, check registry가 필요하다

### 2.2 Issue #8: Observation Health Report

현재 반영된 것:

- `common/observations.py` 추가
- generator / executor / reviewer 경로에서 observation append 시작
- `pack.py`에서 `observation_summary` rollup 추가
- `canonical_snapshot.json`에 measured gate 관련 summary 포함

현재 부족한 것:

- `observation_health_report.json` 같은 파생 report artifact가 없다
- failure cluster / repair strategy success rate / promotion blocker rollup이 없다
- verifier stage, support workflow, repeatability/retry salvage 쪽 observation emit이 비어 있다
- `support_extract.py`, `tests/e2e/repeat_case.py`, support chain 쪽과 연결되지 않았다
- measured gate ready / artifact quality band가 실제로 계산되는 경로가 거의 없다

판단:

- ledger append foundation은 완료
- derived reporting과 support/repeatability integration이 빠져 있어 `35~45%`
- 이 이슈는 새 report module과 support pipeline wiring이 핵심이다

### 2.3 Issue #9: Reviewer / Verifier Evidence Contract

현재 반영된 것:

- reviewer 결과를 action/gate/observation surface에 연결
- existing reviewer/report pipeline는 유지
- verifier 결과는 여전히 `evals.json` 중심으로 남고, oracle parity field 일부는 manifest로 전달됨

현재 부족한 것:

- verifier output에 `verdict`, `checks`, `command`, `observed_output`, `result` triplet schema가 없다
- `PASS | FAIL | PARTIAL` 같은 machine-readable verdict contract가 표준화되어 있지 않다
- adversarial probe requirement가 formalized 되어 있지 않다
- reviewer report도 issue list는 있으나 evidence object schema가 약하다
- `evals/poc_verifier/main.py`, `evals/poc_verifier/llm_assisted.py`, rule-based verifier 결과 surface가 동일 schema를 공유하지 않는다

판단:

- 현재 상태는 reviewer side logging 강화 정도
- verifier contract hardening의 본론은 거의 시작 전이다
- 전체 목표 대비 `25~35%`

## 3. Write Scope Partition

병렬 작업 충돌을 줄이기 위해 write scope를 아래처럼 나눈다.

### Track A: Issue #6

주 write scope:

- `ops/ci/harness_audit.py`
- 신규 helper: `common/harness_audit.py` 또는 동급 모듈
- `tests/test_harness_governance_artifacts.py`
- 선택적 문서 surface

가급적 피할 파일:

- `orchestrator/pack.py`
- `common/observations.py`
- verifier/reviewer modules

### Track B: Issue #8

주 write scope:

- `common/observations.py`
- 신규 helper: `common/observation_health.py`
- `orchestrator/support_extract.py`
- `tests/e2e/repeat_case.py`
- support/repeatability 관련 테스트

조건부 write scope:

- `orchestrator/pack.py`
  - 가능하면 late integration window에서만 수정

### Track C: Issue #9

주 write scope:

- `agents/reviewer/service.py`
- `evals/poc_verifier/main.py`
- `evals/poc_verifier/llm_assisted.py`
- `evals/poc_verifier/registry.py`
- verifier/reviewer 관련 테스트

가급적 피할 파일:

- `orchestrator/pack.py`
- audit modules

## 4. Branch / Worktree Allocation

### Track A

- issue: `#6`
- branch: `issue-006-harness-audit-rubric`
- worktree: `/home/ysw/worktrees/vulDocker-issue-006`
- owner scope:
  - rubric registry
  - weighted scoring
  - evidence-backed check list
  - deterministic rerun recommendations

### Track B

- issue: `#8`
- branch: `issue-008-observation-health-report`
- worktree: `/home/ysw/worktrees/vulDocker-issue-008`
- owner scope:
  - derived health report
  - failure clustering
  - repair strategy rates
  - support/repeatability observation expansion

### Track C

- issue: `#9`
- branch: `issue-009-reviewer-verifier-evidence-surface`
- worktree: `/home/ysw/worktrees/vulDocker-issue-009`
- owner scope:
  - verifier result schema
  - reviewer evidence object schema
  - verdict normalization
  - adversarial probe formalization

## 5. Ordered Execution Plan

### 5.1 Immediate Parallel Start

병렬 시작 가능:

- Track A `#6`
- Track C `#9`

이유:

- 두 트랙은 core write scope가 거의 겹치지 않는다
- 둘 다 현재 foundation artifact를 read consumer 방향으로 확장하는 작업이라 mutual dependency가 약하다

### 5.2 Delayed Parallel Start

Track B `#8`는 두 단계로 나눈다.

1. 병렬 시작 가능 범위
   - `common/observation_health.py`
   - support/repeatability observation emit 추가
   - health aggregation tests
2. 늦게 합류할 범위
   - `pack.py` integration
   - audit scorecard reflected health summary

이유:

- Track B는 `pack.py`와 summary surface를 건드릴 가능성이 크다
- Track A가 audit rubric을 정리하는 동안 `pack` write 충돌을 피하는 것이 낫다

## 6. Merge / Rebase Order

권장 순서:

1. current governance foundation WIP commit/merge
2. `#6` merge
3. `#9` merge
4. `#8` final rebase and merge

근거:

- `#6`가 audit vocabulary와 score semantics를 고정해야 `#8` health report가 measured gate / rerun guidance와 정합하게 연결된다
- `#9`는 verifier evidence surface를 강화해 `#6` category 중 `Review Evidence Quality` scoring 기준을 채우는 공급자 역할을 한다
- `#8`는 최종적으로 audit/review outputs를 consume 하므로 마지막에 통합하는 편이 충돌이 적다

## 7. Detailed Step Order Per Issue

### 7.1 Issue #6

1. `harness_audit.py`를 registry/check model로 분해
2. category별 weighted rubric 도입
3. `checks[]` surface에 `check_id`, `passed`, `score_delta`, `evidence_paths`, `detail` 추가
4. rerun lane recommendation을 failure signature 기반으로 개선
5. representative fixture tests 추가

### 7.2 Issue #8

1. observation health aggregation helper 추가
2. generator/executor/reviewer 외 verifier/support/repeatability emit 확장
3. `failure_clusters`, `repair_strategies`, `promotion_blockers` derived report 생성
4. support workflow summary와 연결
5. late window에서 `pack` 및 canonical snapshot surface에 추가

### 7.3 Issue #9

1. verifier result schema 초안 작성
2. `evals/poc_verifier/main.py` output을 structured check list로 확장
3. `llm_assisted.py`에 structured assertion evidence 추가
4. reviewer report의 issue evidence object 강화
5. `PASS | FAIL | PARTIAL` verdict semantics 표준화
6. adversarial probe requirement와 regression tests 추가

## 8. Blocking Notes

- 현재 main workspace의 governance foundation 변경이 아직 commit되지 않았다.
- 새 worktree는 `064b54b`에서 생성되므로, follow-up track 착수 전 foundation commit을 merge-base로 rebase/cherry-pick해야 한다.
- Track B가 `pack.py`를 조기 수정하면 Track A와 충돌 위험이 커진다.
- Track C가 verifier schema를 바꾸면 Track A의 `Review Evidence Quality` scoring 기준도 같이 업데이트되어야 한다.

## 9. Expected GitHub Reflection

각 child issue에는 아래를 반영한다.

- current status
- done / remaining split
- branch
- worktree path
- ordered checklist
- parallelization note

epic `#1`에는 아래를 반영한다.

- three-track follow-up map
- merge order
- conflict avoidance rules
- note about current WIP base / rebase requirement

## 10. Cycle Status Log

### 2026-04-09T23:04:15+09:00

- authoritative docs:
  - `docs/agent_prompt_pack_20260409.md`
  - `docs/followup_issue_execution_plan_20260409.md`
  - `docs/cross_reference_improvement_program_20260409.md`
- foundation/base reconciliation:
  - `master` HEAD `7fc8e37` and issue branch HEAD `1b9ad46` are tree-equivalent
  - merge-base remains `064b54b`
  - no foundation rebase/cherry-pick is justified this cycle
- issue `#9` `issue-009-reviewer-verifier-evidence-surface`:
  - status: implemented and tested
  - completion: `92%`
  - tests: `pytest -q evals/poc_verifier/tests/test_contract.py evals/poc_verifier/tests/test_registry.py tests/test_llm_assisted_verifier.py tests/test_reviewer_blocking_policy.py` -> `18 passed`
  - write scope: conforms
  - live notes:
    - shared schema source exists in `evals/poc_verifier/contract.py`
    - normalized `PASS | FAIL | PARTIAL`, `checks`, `command`, `observed_output`, `result`, `evidence_paths`, and `adversarial_probe` are implemented
    - reviewer handles `PARTIAL` verifier verdicts
  - freeze decision: freeze-ready now; move to freeze/handoff/commit preparation
- issue `#6` `issue-006-harness-audit-rubric`:
  - status: implemented but provisional
  - completion: `78%`
  - tests: `pytest -q tests/test_harness_governance_artifacts.py` -> `5 passed`
  - write scope: conforms
  - live notes:
    - weighted rubric, structured `checks[]`, and rerun-lane derivation are implemented
    - still depends on provisional schema consumption via absolute-path/copy fallback in `common/harness_audit.py`
    - cannot freeze until `#9` contract is consumed from a real shared source on the branch, not from another worktree path
  - freeze decision: not freeze-ready; schema/vocabulary sync to finalized `#9` is still required
- issue `#8` `issue-008-observation-health-report`:
  - status: implemented but provisional
  - completion: `68%`
  - tests: `pytest -q tests/test_observation_health.py tests/test_repeatability_gate.py tests/test_support_extract.py tests/test_pack_promotion.py` -> `150 passed`
  - write scope: drift present via early `orchestrator/pack.py` integration
  - live notes:
    - derived health report, failure clustering, repair-strategy rates, and support/repeatability integration are implemented
    - `common/observation_health.py` currently hardcodes copied rubric/verdict/evidence vocabulary and marks dependency status as `stable`
    - `orchestrator/pack.py` and canonical snapshot surfaces were expanded before dependency freeze, so those edits remain provisional
  - freeze decision: not freeze-ready; late integration window remains closed
- safe parallel work now:
  - `#9`: freeze/handoff/commit preparation only
  - `#6`: bounded prep that does not finalize dependency consumption before `#9` lands
  - `#8`: early-phase/helper cleanup only; no further `pack.py` expansion
- next assignment wave:
  1. freeze `#9`, capture handoff with changed files/tests/schema vocabulary, and surface the exact commit for downstream consumption
  2. sync `#6` to the landed `#9` shared contract, then remove absolute-path fallback and copied vocabulary fallback from `common/harness_audit.py`
  3. keep `#8` in early-phase mode; quarantine or intentionally revisit `pack.py`/canonical-summary edits only after `#9` and `#6` are frozen
- cross-track dependency update:
  - `#9` is ready to become the source-of-truth producer
  - `#6` is the current dependency consumer bottleneck
  - `#8` still must not claim stable dependency vocabulary or open late integration

### 2026-04-09T23:12:19+09:00

- authoritative docs:
  - `docs/agent_prompt_pack_20260409.md`
  - `docs/followup_issue_execution_plan_20260409.md`
  - `docs/cross_reference_improvement_program_20260409.md`
- foundation/base reconciliation:
  - `master` HEAD `7fc8e37` and issue-branch HEAD `1b9ad46` remain tree-equivalent; current divergence is uncommitted issue-local WIP, not missing foundation content
  - merge-base remains `064b54b`
  - no foundation rebase/cherry-pick is justified this cycle
- issue `#9` `issue-009-reviewer-verifier-evidence-surface`:
  - status: implemented and tested
  - completion: `94%`
  - tests: `pytest -q evals/poc_verifier/tests/test_contract.py evals/poc_verifier/tests/test_registry.py tests/test_llm_assisted_verifier.py tests/test_reviewer_blocking_policy.py` -> `18 passed`
  - blocked: unblocked
  - provisional/frozen: freeze-ready now
  - write scope: conforms
  - live notes:
    - real in-repo schema source exists in `evals/poc_verifier/contract.py`
    - registry and LLM-assisted verifier paths normalize into the shared contract
    - reviewer now surfaces `PARTIAL` verifier verdicts without weakening fail-closed behavior
  - freeze decision: yes; move to freeze/handoff/commit preparation
- issue `#6` `issue-006-harness-audit-rubric`:
  - status: implemented but provisional
  - completion: `77%`
  - tests: `pytest -q tests/test_harness_governance_artifacts.py` -> `5 passed`
  - blocked: blocked for final freeze on landed `#9` contract handoff
  - provisional/frozen: provisional
  - write scope: conforms
  - live notes:
    - weighted rubric, deterministic check registry, structured `checks[]`, and rerun-lane derivation are implemented
    - `common/harness_audit.py` still falls back to absolute-path import of the `#9` worktree and embedded copied contract defaults
    - final `Review Evidence Quality` scoring still needs real shared-source consumption from landed `#9`, not fallback duplication
  - freeze decision: no; shared-source schema/vocabulary sync is still required
- issue `#8` `issue-008-observation-health-report`:
  - status: implemented but provisional
  - completion: `65%`
  - tests: `pytest -q tests/test_observation_health.py tests/test_repeatability_gate.py tests/test_support_extract.py tests/test_pack_promotion.py` -> `150 passed`
  - blocked: early helper/report work unblocked; late integration blocked
  - provisional/frozen: provisional
  - write scope: drift present via early `orchestrator/pack.py` / canonical-snapshot integration
  - live notes:
    - derived observation-health report, failure clustering, repair-strategy rates, and support/repeatability wiring are implemented
    - `common/observation_health.py` still hardcodes copied rubric/verdict/evidence vocabulary and marks dependency status as `stable`
    - current `orchestrator/pack.py` observation-health rollups remain provisional overreach until `#6` and `#9` freeze
  - freeze decision: no; late integration window remains closed
- safe parallel work now:
  - `#9`: freeze/handoff/commit preparation only
  - `#8`: helper/report cleanup only, especially removing copied `stable` dependency claims; no additional `pack.py` expansion
  - `#6`: no safe finalization task until `#9` lands a consumable shared-contract commit
- next assignment wave:
  1. freeze `#9`, capture changed files/tests/schema handoff, and surface the exact commit SHA for downstream consumption
  2. sync `#6` to that landed `#9` contract and delete the absolute-path/copy fallback from `common/harness_audit.py`
  3. keep `#8` early-phase only; treat current `pack.py` / canonical-summary edits as provisional until dependency-freeze criteria are satisfied
- cross-track dependency update:
  - `#9` now owns a real in-repo schema source in `evals/poc_verifier/contract.py`
  - `#6` remains the dependency consumer bottleneck because it still consumes `#9` provisionally
  - `#8` still must not claim stable dependency vocabulary or open the late integration window

### 2026-04-09T23:13:12+09:00

- authoritative docs:
  - `docs/agent_prompt_pack_20260409.md`
  - `docs/followup_issue_execution_plan_20260409.md`
  - `docs/cross_reference_improvement_program_20260409.md`
  - no newer superseding coordination/status doc found under `docs/`
- foundation/base reconciliation:
  - `master` HEAD `7fc8e37` and all three issue worktree HEAD trees remain equivalent to the shared foundation content
  - issue branch HEAD commit remains `1b9ad46`; merge-base with `master` remains `064b54b`
  - no foundation rebase/cherry-pick is justified this cycle
- issue `#9` `issue-009-reviewer-verifier-evidence-surface`:
  - status: implemented and tested
  - completion: `94%`
  - tests: `pytest -q evals/poc_verifier/tests/test_contract.py evals/poc_verifier/tests/test_registry.py tests/test_llm_assisted_verifier.py tests/test_reviewer_blocking_policy.py` -> `18 passed`
  - write scope: conforms
  - live notes:
    - `evals/poc_verifier/contract.py` is the live schema source on the branch
    - registry + LLM-assisted verifier paths normalize into shared `PASS | FAIL | PARTIAL` contract with `checks`, `command`, `observed_output`, `result`, `evidence_paths`, and `adversarial_probe`
    - reviewer surfaces `PARTIAL` verifier verdicts as non-blocking medium-severity issues
  - freeze decision: freeze-ready now; move to freeze/handoff/commit preparation
- issue `#6` `issue-006-harness-audit-rubric`:
  - status: implemented but provisional
  - completion: `79%`
  - tests: `pytest -q tests/test_harness_governance_artifacts.py` -> `5 passed`
  - write scope: conforms
  - live notes:
    - weighted rubric, deterministic `checks[]`, evidence paths, and failure-signature rerun derivation are implemented
    - `common/harness_audit.py` still resolves verifier vocabulary through a normal import, then an absolute-path `#9` worktree fallback, then copied constants
    - dependency consumption is therefore still provisional and not safe for downstream freeze
  - freeze decision: not freeze-ready; schema/vocabulary sync to frozen `#9` source is still required
- issue `#8` `issue-008-observation-health-report`:
  - status: implemented but provisional
  - completion: `63%`
  - tests: `pytest -q tests/test_observation_health.py tests/test_repeatability_gate.py tests/test_support_extract.py tests/test_pack_promotion.py` -> `150 passed`
  - write scope: drift present via early `orchestrator/pack.py` integration
  - live notes:
    - derived observation health reporting, failure clustering, repair-strategy rates, and support/repeatability integration are implemented
    - `common/observation_health.py` hardcodes copied rubric/verdict/evidence vocabulary and marks dependency status as `stable`
    - `orchestrator/pack.py` and canonical snapshot observation-health surfaces were expanded before dependency freeze, so those late-surface edits remain provisional overreach
  - freeze decision: not freeze-ready; late integration window remains closed
- safe parallel work now:
  - `#9`: freeze/handoff/commit preparation
  - `#6`: no final dependency sync until frozen `#9` contract source is landed on the branch
  - `#8`: no new late-surface work; only bounded cleanup/quarantine of copied dependency markers if explicitly chosen
- next assignment wave:
  1. freeze `#9`, capture handoff with changed files/tests/schema vocabulary, and surface the exact commit for downstream consumption
  2. land the frozen `#9` contract source on `#6`, then remove absolute-path fallback and copied vocabulary fallback from `common/harness_audit.py`
  3. keep `#8` in early-phase mode and hold `orchestrator/pack.py` / canonical summary integration closed until `#9` and `#6` are both frozen
- cross-track dependency update:
  - `#9` is ready to serve as the real schema/vocabulary producer
  - `#6` remains the current consumer bottleneck because it still depends on provisional import/copy fallback behavior
  - `#8` must remain early-phase only because dependency vocabulary is not frozen and `orchestrator/pack.py` conflict risk is still live
