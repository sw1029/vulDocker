# Agent Prompt Pack

## Purpose

이 문서는 후속 이슈 `#6`, `#8`, `#9`를 병렬로 진행하기 위한 agent 작업지시용 prompt pack이다.

대상 이슈:

- `#6` `Add deterministic pipeline-harness audit and scorecard`
- `#8` `Add observation ledger and failure-health reporting`
- `#9` `Harden reviewer and verifier evidence contracts`

연관 계획 문서:

- [followup_issue_execution_plan_20260409.md](/home/ysw/vulDocker/docs/followup_issue_execution_plan_20260409.md)
- [cross_reference_improvement_program_20260409.md](/home/ysw/vulDocker/docs/cross_reference_improvement_program_20260409.md)

## Global Execution Rules

아래 규칙은 모든 agent prompt에 공통으로 적용한다.

- 현재 main workspace에는 governance foundation WIP가 존재한다.
- 각 worktree는 clean base `064b54b`에서 생성되어 있다.
- conductor가 foundation commit SHA를 확정해주기 전까지는 reference-only로 읽고, 본격 구현 전에는 반드시 foundation commit을 현재 branch에 rebase/cherry-pick해야 한다.
- 다른 track의 write scope를 침범하지 않는다.
- `orchestrator/pack.py`는 충돌 위험이 크므로 late integration window 이전에는 가능하면 수정하지 않는다.
- 기존 테스트/동작 semantics를 약화시키면 안 된다. 특히 fail-closed 성격을 약화시키면 안 된다.
- 작업 종료 시에는 아래 4가지를 반드시 남긴다.
  - 변경 파일 목록
  - 실행한 테스트
  - 남은 리스크
  - 다음 track 또는 conductor에게 넘길 handoff note

## Branch / Worktree Map

### Track A

- issue: `#6`
- branch: `issue-006-harness-audit-rubric`
- worktree: `/home/ysw/worktrees/vulDocker-issue-006`
- owner scope:
  - `ops/ci/harness_audit.py`
  - `common/harness_audit.py` 또는 동급 신규 helper
  - `tests/test_harness_governance_artifacts.py`

### Track B

- issue: `#8`
- branch: `issue-008-observation-health-report`
- worktree: `/home/ysw/worktrees/vulDocker-issue-008`
- owner scope:
  - `common/observations.py`
  - `common/observation_health.py`
  - `orchestrator/support_extract.py`
  - `tests/e2e/repeat_case.py`
  - support/repeatability 관련 테스트

### Track C

- issue: `#9`
- branch: `issue-009-reviewer-verifier-evidence-surface`
- worktree: `/home/ysw/worktrees/vulDocker-issue-009`
- owner scope:
  - `agents/reviewer/service.py`
  - `evals/poc_verifier/main.py`
  - `evals/poc_verifier/llm_assisted.py`
  - `evals/poc_verifier/registry.py`
  - reviewer/verifier 관련 테스트

## Parallel Execution Order

### Immediate Parallel Start

즉시 병렬 시작:

- Track A `#6`
- Track C `#9`

이유:

- 핵심 write scope가 거의 분리되어 있다.
- 둘 다 foundation artifact의 consumer/producer shape를 확장하는 작업이라 early parallelization이 가능하다.

### Delayed Parallel Start

Track B `#8`는 두 단계로 나눈다.

1. early parallel
   - `common/observation_health.py`
   - observation emit 확장
   - support/repeatability integration
2. late integration
   - `pack.py`
   - audit reflected summary
   - canonical snapshot reflected health sections

이유:

- Track B는 summary surface 충돌 가능성이 가장 높다.
- Track A rubric semantics와 Track C verifier evidence schema가 어느 정도 고정된 뒤 late integration하는 것이 낫다.

## Merge / Rebase Order

권장 순서:

1. governance foundation WIP commit/merge
2. Track A `#6`
3. Track C `#9`
4. Track B `#8`

근거:

- Track A가 audit vocabulary를 고정해야 Track B derived report가 measured gate scoring과 정합하게 연결된다.
- Track C가 stronger evidence producer schema를 제공해야 Track A의 `Review Evidence Quality` scoring이 의미를 가진다.
- Track B는 최종적으로 A/C 결과를 consume하므로 마지막에 정리하는 편이 충돌이 적다.

## Conductor Prompt

다음 prompt는 conductor agent가 각 track을 kickoff할 때 사용한다.

```text
You are the conductor for the vulDocker follow-up program covering issues #6, #8, and #9.

Repository:
- repo root: /home/ysw/vulDocker
- planning doc: /home/ysw/vulDocker/docs/followup_issue_execution_plan_20260409.md
- prompt pack: /home/ysw/vulDocker/docs/agent_prompt_pack_20260409.md

Execution rules:
- The current main workspace contains governance-foundation WIP.
- All dedicated worktrees were created from clean base commit 064b54b.
- Before substantive implementation, rebase/cherry-pick the finalized foundation commit SHA onto the target branch/worktree.
- Do not let tracks overlap on write scope unless this prompt explicitly says so.
- Preserve fail-closed behavior and current test semantics.

Parallelization plan:
- Start Track A (#6) and Track C (#9) immediately in parallel.
- Start Track B (#8) only for early helper/emitter work in parallel.
- Delay Track B late integration work that touches pack/canonical summary surfaces until after Track A and Track C stabilize.

Required outputs from each track:
- changed files
- tests executed
- unresolved risks
- handoff note for conductor

When a track finishes, evaluate whether its outputs should update the integration plan for other tracks before proceeding.
```

## Track A Prompt

다음 prompt는 `#6` 전용 worker agent에 바로 전달한다.

```text
You are assigned to issue #6: deterministic pipeline-harness audit and scorecard.

Worktree / branch:
- worktree: /home/ysw/worktrees/vulDocker-issue-006
- branch: issue-006-harness-audit-rubric
- issue: https://github.com/sw1029/vulDocker/issues/6

Before coding:
- sync to the finalized governance-foundation commit SHA provided by the conductor
- read:
  - /home/ysw/vulDocker/docs/followup_issue_execution_plan_20260409.md
  - /home/ysw/vulDocker/docs/agent_prompt_pack_20260409.md
  - current audit entrypoint under ops/ci/harness_audit.py

Your write scope:
- ops/ci/harness_audit.py
- common/harness_audit.py or equivalent new helper
- tests/test_harness_governance_artifacts.py

Avoid unless conductor explicitly approves:
- orchestrator/pack.py
- common/observations.py
- reviewer/verifier modules

Current state:
- a minimal deterministic harness audit exists
- it mainly checks artifact presence and emits coarse category scores
- it does not yet provide weighted rubric, stable check registry, evidence-backed checks, or meaningful rerun recommendations

Your goals:
1. refactor audit logic into a deterministic category/check registry model
2. implement weighted rubric instead of binary 0/100 presence checks
3. emit machine-readable checks with at least:
   - check_id
   - category
   - passed
   - score_delta
   - severity
   - detail
   - evidence_paths
4. cover categories:
   - Selection Authority
   - Materialization Causality
   - Runtime Contract Parity
   - Oracle Execution Parity
   - Review Evidence Quality
   - Measured Gate Integrity
   - Cost And Retry Efficiency
5. derive rerun recommendations from failure signatures rather than fixed labels
6. keep the audit deterministic for the same artifact set

Validation requirements:
- add/update deterministic fixture tests
- run at least:
  - pytest -q tests/test_harness_governance_artifacts.py
- add more focused tests if you introduce a new helper module

Deliverables:
- improved harness audit implementation
- updated tests
- handoff note stating:
  - exact scoring model
  - any new vocabulary that Track B or Track C must consume
  - whether late pack integration is still needed
```

## Track B Early Prompt

다음 prompt는 `#8`의 early-phase worker agent에 전달한다.

```text
You are assigned to the early phase of issue #8: observation ledger and failure-health reporting.

Worktree / branch:
- worktree: /home/ysw/worktrees/vulDocker-issue-008
- branch: issue-008-observation-health-report
- issue: https://github.com/sw1029/vulDocker/issues/8

Before coding:
- sync to the finalized governance-foundation commit SHA provided by the conductor
- read:
  - /home/ysw/vulDocker/docs/followup_issue_execution_plan_20260409.md
  - /home/ysw/vulDocker/docs/agent_prompt_pack_20260409.md
  - common/observations.py

Your write scope for early phase:
- common/observations.py
- common/observation_health.py
- orchestrator/support_extract.py
- tests/e2e/repeat_case.py
- support/repeatability related tests

Avoid in early phase:
- orchestrator/pack.py
- audit modules
- reviewer/verifier producer schema

Current state:
- observation_ledger append helpers exist
- generator / executor / reviewer already emit some observations
- pack rolls up observation_summary
- derived health reporting does not exist yet

Your goals in this phase:
1. define and implement a derived health report artifact, e.g. observation_health_report.json
2. aggregate:
   - failure clusters by failure_class
   - repair strategy totals / success rates / salvage rates
   - promotion blocker clusters
3. extend observation emission into:
   - verifier stage
   - support workflow
   - repeatability / retry salvage paths
4. keep the ledger append-only and machine-readable
5. avoid changing top-level pack summary surfaces in this phase

Validation requirements:
- add/update unit tests for aggregation logic
- add/update support/repeatability path tests
- run focused tests relevant to your changed files

Deliverables:
- observation health helper/report implementation
- extended emitters outside the current generator/executor/reviewer subset
- handoff note stating:
  - report schema
  - any fields that Track A should score
  - what late integration remains for pack/canonical snapshot
```

## Track B Late Integration Prompt

다음 prompt는 `#8`의 late integration phase에 사용한다.

```text
You are performing the late integration phase of issue #8 after Track A and Track C have stabilized.

Worktree / branch:
- worktree: /home/ysw/worktrees/vulDocker-issue-008
- branch: issue-008-observation-health-report

Preconditions:
- governance foundation commit is already integrated
- Track A rubric vocabulary is stable
- Track C verifier/reviewer evidence schema is stable

Your write scope in this phase:
- orchestrator/pack.py
- canonical snapshot integration surfaces
- any observation health rollup helpers needed for final summary output

Goals:
1. integrate derived observation health report into pack/canonical snapshot surfaces
2. ensure measured gate / promotion blocker / repair-strategy summaries are visible at operator-facing top level
3. avoid renaming vocabulary already fixed by Track A and Track C
4. keep summary surfaces concise and machine-readable

Validation requirements:
- run pack-related regression tests
- run any newly added observation-health tests

Deliverables:
- final pack integration
- summary of conflicts avoided / remaining
```

## Track C Prompt

다음 prompt는 `#9` 전용 worker agent에 바로 전달한다.

```text
You are assigned to issue #9: reviewer/verifier evidence contract hardening.

Worktree / branch:
- worktree: /home/ysw/worktrees/vulDocker-issue-009
- branch: issue-009-reviewer-verifier-evidence-surface
- issue: https://github.com/sw1029/vulDocker/issues/9

Before coding:
- sync to the finalized governance-foundation commit SHA provided by the conductor
- read:
  - /home/ysw/vulDocker/docs/followup_issue_execution_plan_20260409.md
  - /home/ysw/vulDocker/docs/agent_prompt_pack_20260409.md
  - agents/reviewer/service.py
  - evals/poc_verifier/main.py
  - evals/poc_verifier/llm_assisted.py

Your write scope:
- agents/reviewer/service.py
- evals/poc_verifier/main.py
- evals/poc_verifier/llm_assisted.py
- evals/poc_verifier/registry.py
- related tests

Avoid unless conductor explicitly approves:
- orchestrator/pack.py
- audit modules
- observation health aggregation modules

Current state:
- reviewer is connected to action/gate/observation surfaces
- verifier still mainly emits `evals.json` with relatively weak structured evidence
- there is no standardized machine-readable reviewer/verifier contract yet

Your goals:
1. define a shared machine-readable result schema for reviewer/verifier outputs
2. include at least:
   - verdict
   - checks[]
   - command
   - observed_output
   - result
   - evidence_paths
3. normalize verdict semantics to:
   - PASS
   - FAIL
   - PARTIAL
4. make PARTIAL legal only for genuine environment limitations
5. extend rule-based and LLM-assisted verifier outputs to share the same structured surface
6. harden reviewer issue/evidence objects to consume the stronger evidence schema
7. formalize at least one adversarial probe requirement for substantive verification paths

Validation requirements:
- add/update reviewer/verifier regression tests
- run focused tests for changed verifier/reviewer paths

Deliverables:
- shared schema implemented in producer outputs
- stronger evidence objects
- handoff note stating:
  - final verdict/check schema
  - fields that Track A should treat as Review Evidence Quality inputs
  - any compatibility notes for Track B summary consumers
```

## Mid-Run Sync Prompt

다음 prompt는 conductor가 Track A/C/B 사이 동기화가 필요할 때 사용한다.

```text
Provide a synchronization update for your track.

Required structure:
1. Current completion percentage
2. Files changed so far
3. Vocabulary/schema you introduced that other tracks may need to consume
4. Any conflict risk with pack.py or shared summary surfaces
5. Recommended next step for your own track
6. Blocking dependency on another track, if any

Keep the update concise and concrete. Focus on coordination-relevant facts.
```

## Final Integration Prompt

다음 prompt는 conductor 또는 integrator agent가 마지막 정리 단계에서 사용한다.

```text
You are the final integrator for follow-up issues #6, #8, and #9.

Context:
- governance foundation is merged
- Track A, Track B, and Track C branches have completed their scoped changes
- your job is to integrate without regressing current semantics

Tasks:
1. inspect the final outputs of Track A, Track B, and Track C
2. resolve vocabulary mismatches across audit, observation health, and reviewer/verifier evidence surfaces
3. ensure pack/canonical snapshot/top-level manifests expose stable machine-readable summaries
4. run representative regression tests across:
   - audit
   - pack
   - run_pipeline failure handling
   - verifier/reviewer
   - support/repeatability if Track B touched those paths
5. prepare a final integration note listing:
   - merged components
   - unresolved follow-ups
   - any new operator-facing commands/artifacts

Constraints:
- preserve fail-closed behavior
- do not silently weaken verifier/reviewer standards
- do not collapse structured artifacts back into free-form text
```

## Handoff Template

각 worker는 작업 종료 시 아래 형식으로 handoff를 남긴다.

```text
Track:
Issue:
Branch:
Worktree:

Completed:
- ...

Changed files:
- ...

Tests run:
- ...

New schema / vocabulary:
- ...

Known risks:
- ...

Needs from other tracks:
- ...

Recommended next step:
- ...
```
