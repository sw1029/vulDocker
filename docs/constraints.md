# vulDocker 제약조건

Status: canonical
Audience: mixed
Source of truth for: current technical, operational, and evaluation constraints
Not the source of truth for: roadmap, rerun baseline tables, quickstart
Last validated against: code inspection and representative reruns on 2026-03-14

이 문서는 현재 시스템이 할 수 있는 것, 아직 못 하는 것, 그리고 무엇을 주장하면 안 되는지를 canonical하게 정리합니다. 미래 계획은 최소 링크로만 남기고, 여기에는 현재 사실만 기록합니다.

관련 문서:
- 문제 정의와 success criteria: [docs/problem.md](problem.md)
- 현재 rerun-backed truth: [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)
- 구현 우선순위: [docs/final_solution.md](final_solution.md)
- 운영 절차: [docs/handbook.md](handbook.md)

## 1. Name-Only Mode Constraints

Constraint: `compatibility`, `dynamic`, `strict_dynamic`는 서로 다른 closure contract를 가집니다.

- Current enforcement surface: `common/name_only.py`, `orchestrator/pack.py`
- Allowed claim: compatibility mode의 lower-bound closure는 regression success로 설명할 수 있습니다.
- Forbidden claim: dynamic/strict_dynamic의 degraded fallback을 generalized open-world success처럼 설명하면 안 됩니다.
- Planned removal path: roadmap의 decision policy unification과 oracle execution parity 이후 재평가

Constraint: `intent_met`, `partial`, `abstain`, `fail_closed`는 pipeline success와 분리해서 읽어야 합니다.

- Current enforcement surface: `name_only_outcome`, `support_promotion`, `open_world_readiness`
- Allowed claim: `pipeline_result=success`이면서 `name_only_outcome=partial`일 수 있습니다.
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

## 3. Research / Evidence Authority Constraints

Constraint: evidence authority는 아직 lexical heuristic이 강합니다.

- Current enforcement surface: query plan, family ranking, evidence graph, source authority weighting
- Observable today: alias/anchor/marker match와 simple authority buckets가 큰 비중을 가집니다.
- Allowed claim: evidence-informed ranking
- Forbidden claim: causal or sufficient evidence reasoning

Constraint: open-vocabulary induction layer가 아직 없습니다.

- Current enforcement surface: catalog resolution, fixed hints, synthetic name handling
- Observable today: unknown phrase는 synthetic name이나 bounded family candidate로는 surface되지만, `provisional_family`나 primitive-led induction layer는 없습니다.
- Allowed claim: bounded family-inducible handling
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

- Current enforcement surface: semantic signature, family-aware fallback builders, manifest synthesis
- Observable today: primitive signal은 존재하지만 최종 materialization은 대부분 bounded family builder와 repo-supported runtime prior에 의존합니다.
- Allowed claim: primitive-informed bounded generation
- Forbidden claim: primitive-first runtime design synthesis

Constraint: deterministic fallback은 runnable quality를 보존하기 위한 degraded path입니다.

- Current enforcement surface: `generation_origin=deterministic_fallback`, `fallback_class=*`
- Allowed claim: bounded runnable recovery
- Forbidden claim: template-independent generalized generation

## 5. Executor / Runtime Constraints

Constraint: `executor_plan`은 아직 완전한 authoritative runtime control-plane이 아닙니다.

- Current enforcement surface: executor의 port/health/env/sidecar re-resolution
- Observable today: sidecar wiring, dependency order, seed/init, env/volume contract가 policy/runtime recipe에 더 의존합니다.
- Allowed claim: minimal executor plan surface
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
- Observable today: `negative_controls`와 `metamorphic`가 quality metadata에는 반영되지만 full execution parity는 제한적입니다.
- Allowed claim: oracle metadata is present
- Forbidden claim: all oracle realism fields are executed verifier checks

## 7. Promotion / Readiness Claim Constraints

Constraint: `promotion_eligible`와 `support_promotion`은 다른 의미입니다.

- Current enforcement surface: pack summary surfaces
- Allowed claim: pack/regression promotion 가능
- Forbidden claim: promotion 가능 = generalized support readiness

Constraint: `support_promotion`은 honesty surface이며 extraction loop가 아닙니다.

- Current enforcement surface: summary/reasons only
- Allowed claim: support claim gating
- Forbidden claim: reusable support extraction pipeline가 이미 존재한다고 말하는 것

## 8. Performance / Observability Constraints

Constraint: researcher latency variance가 여전히 큽니다.

- Current enforcement surface: performance summary, search traces
- Observable today: representative dynamic rerun에서 RESEARCH가 총 시간의 가장 큰 비중을 차지합니다.
- Allowed claim: measured sample performance
- Forbidden claim: one-off rerun improvement를 구조 개선으로 일반화

Constraint: observability surface는 좋아졌지만 controller parity를 대체하지는 않습니다.

- Current enforcement surface: `name_only_outcome`, `selection_readiness_summary`, `boundedness_summary`, `open_world_readiness`
- Allowed claim: current boundedness를 정직하게 보여 줌
- Forbidden claim: summary surface가 곧 control-plane 완성을 뜻함

## 9. Non-Claims

아래는 현재 강하게 말하면 안 되는 주장입니다.

- arbitrary 취약점 이름만으로 generalized open-world positive를 안정적으로 만든다
- unknown family / unknown stack / multi-service topology를 실제로 materialize한다
- `promotion_eligible=true`가 generalized support readiness를 뜻한다
- `artifact_quality=high`가 사람 기준 좋은 lab realism을 항상 보장한다
- 현재 `request_ir`가 이미 generator/executor의 authoritative control-plane이다

## 10. How To Update This Document

- direct rerun, current code inspection, or stable policy change가 있을 때만 갱신합니다.
- TODO, priority, next slice는 적지 않습니다. 그런 내용은 [docs/final_solution.md](final_solution.md)로 보냅니다.
- representative sample 수치는 “observed sample”로만 적고, generalized claim으로 올리지 않습니다.
