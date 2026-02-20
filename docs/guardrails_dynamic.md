# Dynamic GuardSpec 운영 가이드

## 개요
- 목적: Researcher evidence를 기반으로 bundle 단위 `guard_spec.json`을 생성하고, Generator/Verifier/Reviewer가 동일 규격으로 소비한다.
- 스키마 버전: `guard_spec@1.0`

## 정책 (`policy.guard`)
- `enforcement`: `block_both|block_unknown|warn_only`
- `failure_policy`: `closed_unknown|open_all|closed_all`
- `dynamic_scope`: `assertions_semantics|include_patterns|full`
- `call_budget.mode`: `bundle_once|per_candidate|verifier_only|bundle_ensemble`
- `call_budget.ensemble_runs`: 앙상블 호출 횟수(기본 3)
- `autofix.level`: `none|manifest|code`
- `autofix.max_attempts`: 자동 보정 최대 시도 횟수

## GuardSpec 필드
- `schema_version`, `sid`, `vuln_id`, `slug`, `source`
- `policy_snapshot`
- `evidence_refs[]`: `query/source/url/published/retrieved_at/snippet`
- `semantic_signature`: `input_vector/sink/exploit_precondition`
- `generator_assertions[]`
- `verifier_assertions[]`
- `autofix_hints[]`
- `confidence`, `created_at`

## 적용 지점
- Researcher: `metadata/<sid>/bundles/<slug>/guard_spec.json` 생성
- Generator: synthesis guard에 `generator_assertions + semantics` 병합, 필요 시 `autofix` 1회 재검증
- Verifier: rule pass 이후 `verifier_assertions`/workspace semantics 교차검증
- Reviewer: guard mismatch를 `critical + blocking`으로 보고

## known/unknown 처리
- known CWE: static rule 핵심 계약은 잠금 상태 유지, GuardSpec은 확장 검사로만 동작
- unknown CWE: `failure_policy=closed_unknown`이면 GuardSpec 부재/검증 실패 시 차단
