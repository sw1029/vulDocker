# Dynamic GuardSpec 운영 가이드

Status: support
Audience: implementation
Source of truth for: GuardSpec subsystem behavior and policy interpretation
Not the source of truth for: project-level constraints, roadmap, current baseline
Last validated against: `common/guardrails/*`, generator/verifier/reviewer integration on 2026-03-14

이 문서는 GuardSpec subsystem만 설명합니다. 프로젝트 전체의 제약은 [docs/constraints.md](constraints.md), 구현 우선순위는 [docs/final_solution.md](final_solution.md)를 봅니다.

## 개요

- 목적: Researcher evidence를 바탕으로 bundle 단위 `guard_spec.json`을 만들고 Generator/Verifier/Reviewer가 공통 소비합니다.
- 스키마 버전: `guard_spec@1.0`
- 위치: `metadata/<sid>/bundles/<slug>/guard_spec.json` 또는 단일 번들의 `metadata/<sid>/guard_spec.json`

## 정책 (`policy.guard`)

- `failure_policy`: `closed_unknown|open_all|closed_all`
- `dynamic_scope`: `assertions_semantics|include_patterns|full`
- `call_budget.mode`: `bundle_once|per_candidate|verifier_only|bundle_ensemble`
- `call_budget.ensemble_runs`: ensemble run count
- `autofix.level`: `none|manifest|code`
- `autofix.max_attempts`: 최대 자동 보정 시도 횟수

정책 제약과 claim 한계는 [docs/constraints.md](constraints.md)의 researcher/generator/verifier constraints를 따릅니다.

## GuardSpec 필드

- `schema_version`, `sid`, `vuln_id`, `slug`, `source`
- `policy_snapshot`
- `evidence_refs[]`
- `semantic_signature`
- `generator_assertions[]`
- `verifier_assertions[]`
- `autofix_hints[]`
- `confidence`, `created_at`

## 적용 지점

- Researcher: evidence와 verification spec을 바탕으로 GuardSpec 생성
- Generator: candidate manifest를 guard assertions와 semantic constraints로 검증
- Verifier: rule 기반 검증 이후 verifier assertions와 workspace semantics를 추가 교차검증
- Reviewer: guard mismatch를 blocking signal로 해석

## What GuardSpec Does Not Solve Yet

- family/stack/topology selection 자체를 authoritative control-plane으로 만들지는 않습니다.
- negative/metamorphic oracle를 실제 실행하는 verifier parity를 대신하지 않습니다.
- generalized open-world capability의 근거가 되지 않습니다.

이 한계는 [docs/constraints.md](constraints.md)에 canonical하게 적고, 이 문서에서는 subsystem behavior만 유지합니다.
