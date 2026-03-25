# vulDocker 동적화 로드맵 (Legacy Reference)

> Archived reference. 이 문서는 historical snapshot이며 active source가 아니다.
>
> 현재 canonical 문서:
> - 문제 정의: `docs/problem.md`
> - 현재 상태: `docs/current_state_gap_analysis.md`
> - 제약조건: `docs/constraints.md`
> - 구현 로드맵: `docs/final_solution.md`
> - current completion priority order / 잔여 작업량·turn envelope: `docs/work_tickets.md`의 `Confirmed Completion Priority Order`, `Estimated Turn Envelope`

> 이 문서는 historical roadmap snapshot이다. 현재 구현 우선순위 판정에는 쓰지 않는다.

## Priority Companions

legacy roadmap 문서 기준으로도 current priority source는 아래만 따른다.

- current completion priority order: [docs/work_tickets.md](../../work_tickets.md)의 `Confirmed Completion Priority Order`
- 잔여 작업량과 practical turn envelope: [docs/work_tickets.md](../../work_tickets.md)의 `Estimated Turn Envelope`
- representative evidence와 함께 보는 turn estimate shortcut: [docs/work_tickets.md](../../work_tickets.md)의 `Turn Estimate Entry`
- priority companion set / reading order: [docs/work_tickets.md](../../work_tickets.md)의 `Priority Companions`, `Priority Reading Order`
- latest positive representative pair의 ticket-form reading: [docs/work_tickets.md](../../work_tickets.md)의 `Assessment-To-Ticket Interpretation`
- LLM-response 기준 residual/priority 해석: [docs/work_tickets.md](../../work_tickets.md)의 `LLM-Response Capability Overlay`
- canonical roadmap / current truth / current non-claim: [docs/final_solution.md](../../final_solution.md), [docs/current_state_gap_analysis.md](../../current_state_gap_analysis.md), [docs/constraints.md](../../constraints.md)

## Priority Review Entry

legacy roadmap에서 priority를 확인해야 한다면 아래 순서를 따른다.

1. 이 문서의 `Priority Companions`
2. [docs/work_tickets.md](../../work_tickets.md)의 `Confirmed Completion Priority Order`, `Estimated Turn Envelope`
3. [docs/work_tickets.md](../../work_tickets.md)의 `LLM-Response Capability Overlay`, `Assessment-To-Ticket Interpretation`
4. [docs/final_solution.md](../../final_solution.md), [docs/current_state_gap_analysis.md](../../current_state_gap_analysis.md), [docs/constraints.md](../../constraints.md)

turn estimate shortcut은 [docs/work_tickets.md](../../work_tickets.md)의 `Turn Estimate Entry`를 따른다.

## How To Update This Document

- historical roadmap snapshot 의미나 redirect target이 바뀔 때만 갱신합니다.
- current roadmap, current priority, current rerun truth는 여기로 옮겨 적지 않습니다. 각각 [docs/final_solution.md](../../final_solution.md), [docs/work_tickets.md](../../work_tickets.md), [docs/current_state_gap_analysis.md](../../current_state_gap_analysis.md)를 우선합니다.
- priority companion 관계나 priority reading order가 바뀌면 [docs/work_tickets.md](../../work_tickets.md), [README.md](../../../README.md)와 같이 맞춥니다.
- LLM-response stricter reading의 legacy roadmap redirect target이 바뀌면 [docs/work_tickets.md](../../work_tickets.md)의 `LLM-Response Capability Overlay`와 같이 맞춥니다.
- latest positive representative pair의 ticket-form redirect target이 바뀌면 [docs/work_tickets.md](../../work_tickets.md)의 `Assessment-To-Ticket Interpretation`와 같이 맞춥니다.
- 잔여 작업량/turn envelope redirect target이 바뀌면 [docs/work_tickets.md](../../work_tickets.md)의 `Estimated Turn Envelope`와 같이 맞춥니다.
- [docs/work_tickets.md](../../work_tickets.md)의 `Turn Estimate Entry` redirect target이 바뀌면 same shortcut도 같이 맞춥니다.

## MoSCoW TODO Checklist

> 표기: `[x]` 완료 / `[ ]` 미완료(Backlog)

## MUST (필수 — “새 CWE/스택”에도 end-to-end가 깨지지 않게)

### 1) Contract 단일화(ResolvedContract)
- [ ] `ResolvedContract`(해석된 계약) 스키마 정의 + per-bundle 저장(`metadata/<SID>/.../resolved_contract.json`)
- [ ] Generator/Executor/Verifier/Reviewer가 contract를 우선 소비하고, 없을 때만 기존 폴백 경로 사용(점진 도입)
- [ ] 우선순위 규칙을 코드/문서로 고정: `runtime rule` → `static rule` → `generator_template.json` → `generator_manifest.json` → `defaults`

### 2) EXECUTE 하드코딩 제거(스택/언어 독립)
- [x] 서비스 포트/base-url 동적 resolve(`generator_template.json`/`generator_manifest.json`/Dockerfile 기반) (`executor/runtime/docker_local.py`)
- [x] 컨테이너 readiness probe의 Python **필수 의존 제거**(다중 `tcp/http/shell` probe 폴백; python은 선택 경로) (`executor/runtime/docker_local.py`)
- [x] PoC 엔트리/실행의 `.py` 제한 제거: `poc.cmd`/`poc_entry` 기반 실행 + suffix allowlist/정책 제어 (`executor/runtime/docker_local.py`)
- [ ] sidecar 요구(`requires_external_db`)와 정책 불일치 조기 감지 + 루프 피드백(Generator/Reviewer)
- [x] 네트워크/sidecar 네트워크 lifecycle 구현(`NetworkPool.release()`), 잔존 네트워크/컨테이너 누수 방지 (`executor/runtime/docker_local.py`)

### 3) GENERATE/RESEARCH 하드코딩 제거(취약점/룰/템플릿 커버리지)
- [ ] CWE-89/352 전용 기본값 제거:
  - [x] `agents/generator/synthesis.py`: CWE 전용 상수(`DEFAULT_*`, `FALLBACK_POC_ENDPOINTS`) 제거 + 서비스 엔트리 기반 fallback PoC endpoint 추론으로 일반화
  - [x] `agents/generator/service.py`: `DEFAULT_TEMPLATE_ENDPOINTS` 제거(서비스 엔트리 스캔 기반 endpoint 추론으로 대체)
  - [x] `agents/researcher/service.py`: candidate rule/template 생성의 CWE 하드코딩 제거(스캔/LLM 기반)
- [x] rule 미존재 CWE에서도 VERIFY가 `unsupported`로 끝나지 않게 폴백 제공(`generator_manifest.json` 기반 임시 룰) (`evals/poc_verifier/rule_based.py`)
- [x] RuleSpec + runtime assertion program 기반 시나리오 계층 (`evals/poc_verifier/scenarios.py`)
- [x] LLM stub fallback이 특정 CWE(SQLi)에 치우치지 않도록 일반 폴백 체인으로 교체 (`common/llm/provider.py`, `agents/generator/synthesis.py`)

### 4) VERIFY/REVIEW 계약 정렬(성공 조건/증거)
- [x] JSON/텍스트 혼합 판정 및 pattern placeholder 지원 (`evals/poc_verifier/rule_based.py`)
- [ ] `"FLAG"` 기본 마커 관례 의존 최소화(룰/계약이 없으면 flag “비요구” 또는 JSON-only 판정)
- [x] Reviewer 정적 스캔을 rule patterns 기반으로 일반화(취약점별 하드코딩 제거) (`agents/reviewer/service.py`)

### 5) 테스트/회귀(동적 케이스)
- [x] 단위 테스트: runtime rule 디렉터리 로드 경로 (`tests/test_runtime_rules.py`)
- [x] E2E 기본 케이스(옵트인): `tests/e2e/cases/cwe-89-basic`
- [ ] “레포에 없는 CWE” 입력 케이스 E2E 추가(Researcher → Generator → Executor → Verifier)
- [ ] 비-Python 컨테이너(ready probe/PoC 실행) 회귀 케이스 추가

## SHOULD (권장 — 커버리지/운영성/재현성 확대)

- [ ] Rule v2 스키마 확장(실행 계약 포함) + 문서/샘플 룰 업데이트(`docs/evals/rules/*.yaml`)
- [ ] 템플릿 커버리지 확장 + “성공한 synthesis 결과”의 템플릿 승격(promote) 경로 추가
- [ ] RAG 힌트/코퍼스 커버리지 확장(CWE/스택 다양화) 및 운영 정책 정리
- [ ] `executor/runtime/docker_db.py`의 역할 정리(미사용 유지 vs sidecar 실행기로 통합)

## COULD (선택 — 실험/고도화)

- [ ] LLM-assisted verifier 고도화(예산/근거 제한, stub graceful skip, metamorphic 옵션)
- [ ] 다중 컨테이너 스택 지원 확대(DB 외 redis 등) + 네트워크 정책 세분화
- [ ] 재현성 메타(`deps_digest`, `base_image_digest`, `retriever_commit`) 자동 산출/검증 파이프라인 도입(ops/ci와 연동)

## WON'T (이번 범위 제외)

- [ ] 파이프라인 단계/아키텍처 대규모 개편(분산 실행/새 오케스트레이터 등)
- [ ] 외부 인터넷에 노출되는 형태의 실행/배포 자동화

## Quick Map (수정 후보 파일)

- Contract: `common/rules/__init__.py`(또는 신규 `common/contract.py`), `metadata/<SID>/...`
- Generator: `agents/generator/service.py`, `agents/generator/synthesis.py`
- Researcher: `agents/researcher/service.py`
- Executor: `executor/runtime/docker_local.py`
- Verifier: `evals/poc_verifier/rule_based.py`, `evals/poc_verifier/scenarios.py`, `evals/poc_verifier/registry.py`
- Reviewer: `agents/reviewer/service.py`
- Rules/Templates/Hints: `docs/evals/rules/`, `workspaces/templates/`, `rag/hints/`
