# vulDocker 문제 정의 (Legacy → Plan, MoSCoW TODO)

> 문서 목적: 구버전 분석 문서(`docs/problem_legacy.md`)를 “하드코딩/분기/기본값/커버리지” 관점의 **계획 문서(TODO checklist)** 로 재구성한다.
>
> 아키텍처(PLAN → GENERATE → EXECUTE → VERIFY → REVIEW → PACK)는 유지한다.
>
> 최신 단일 소스: `docs/problem.md`, `docs/final_solution.md` (본 문서는 “레거시 관찰 → 실행 가능한 TODO” 보조 인덱스).

## MoSCoW TODO Checklist

> 표기: `[x]` 완료 / `[ ]` 미완료(Backlog)

## MUST (새 CWE/스택 입력에도 end-to-end가 깨지지 않게)

### Contract/결정 로직 분산
- [ ] stage 공통 계약(예: `ResolvedContract`)을 정의하고, per-bundle(`metadata/<SID>/bundles/<slug>/...` 또는 단일 번들의 `metadata/<SID>/...`)에 “해석된 계약”을 저장한다.
  - [ ] 우선순위 규칙: `runtime rule` → `static rule` → `generator_template.json` → `generator_manifest.json` → `defaults`
  - [ ] 계약 필드: `service_port/base_url`, `service_entry`, `poc_entry/poc_cmd`, `success 조건(JSON/텍스트/flag)`, `ready_probe`, `requires_external_db/sidecars`
- [ ] “unknown CWE 기본 토큰/시그니처”를 **한 곳에서 결정**(Generator/Researcher/Verifier 정렬)하고, 기본값을 CWE별 하드코딩이 아니라 “공통 스키마 기본값”으로 축소한다.
- [x] rule 미존재 CWE에서도 VERIFY가 `unsupported`로 끝나지 않게 폴백 제공(`generator_manifest.json` 기반 임시 룰) (`evals/poc_verifier/rule_based.py`)

### EXECUTE 하드코딩/언어 종속
- [x] 서비스 포트/base-url 동적 resolve(템플릿 메타/매니페스트/Dockerfile 기반) (`executor/runtime/docker_local.py`)
- [x] 앱 readiness probe의 Python **필수 의존 제거**(다중 `tcp/http/shell` probe 폴백; python은 선택 경로) (`executor/runtime/docker_local.py`)
- [x] PoC 실행을 `.py`/`python` 고정에서 분리: `poc.cmd`/`poc_entry` 기반 실행 + suffix allowlist/정책 제어 (`executor/runtime/docker_local.py`)
- [ ] 외부 DB 요구(`requires_external_db`)와 `policy.executor.sidecars` 불일치를 조기 감지(PLAN 또는 GENERATE 단계에서 fail-fast + 가이드).
- [x] 네트워크/sidecar 네트워크 생성·해제 lifecycle 완성(`NetworkPool.release()` 구현) (`executor/runtime/docker_local.py`)

### GENERATE/RESEARCH 하드코딩(취약점/엔드포인트/기본값)
- [ ] CWE-89/352 전용 기본값 제거:
  - [x] `agents/generator/synthesis.py`: CWE 전용 상수(`DEFAULT_*`, `FALLBACK_POC_ENDPOINTS`) 제거 + 서비스 엔트리 기반 fallback PoC endpoint 추론으로 일반화
  - [x] `agents/generator/service.py`: `DEFAULT_TEMPLATE_ENDPOINTS` 제거(서비스 엔트리 스캔 기반 endpoint 추론으로 대체)
  - [x] `agents/researcher/service.py`: candidate rule/template 생성의 CWE 하드코딩 제거(스캔/verification_spec 기반)
- [x] LLM 미설정/네트워크 장애(stub) 시 SQLi 전용 fallback manifest 편중을 제거하고 **일반 폴백 번들**로 교체(offline에서도 end-to-end 유지) (`common/llm/provider.py`, `agents/generator/synthesis.py`)
- [x] rule/runtime 부재 시 `flag_token`을 강제 덮어쓰지 않도록 수정(계약 불일치 완화) (`agents/generator/synthesis.py`)

### VERIFY/REVIEW 커버리지 일반화
- [x] RuleSpec + runtime assertion program 기반 시나리오 계층 도입 (`evals/poc_verifier/scenarios.py`, `evals/poc_verifier/llm_assisted.py`)
- [ ] `"FLAG"` 기본 마커 관례 의존을 줄인다(룰/계약이 없을 때 flag를 “비요구”로 처리하거나 JSON success만으로 판정).
- [x] Reviewer의 정적 스캔을 SQLi 정규식 하드코딩에서 rule patterns 기반으로 일반화한다(`docs/evals/rules/*.yaml` + runtime rule). (`agents/reviewer/service.py`)

## SHOULD (해결 시 커버리지/재현성/운영성이 크게 개선)

- [ ] rule/template/hints 커버리지 확장(CWE-89/352 편중 완화) 및 운영 모델 정리.
- [ ] “레포에 없는 CWE” 입력 케이스 E2E 회귀 테스트 추가(`tests/e2e/cases/*` 확장).
- [ ] 성공한 synthesis 결과를 템플릿으로 승격(promote)하는 경로 추가(`runtime_templates` → `workspaces/templates`).
- [ ] `executor/runtime/docker_db.py`를 정리(미사용 유지 vs sidecar 실행기로 통합 결정).

## COULD (실험/고도화)

- [ ] LLM-assisted verifier 정책/안전장치 강화(오프라인 stub graceful skip, assertion budget/근거 제한).
- [ ] 다중 컨테이너 스택 지원 확대(DB 외 redis 등) + 네트워크 정책 고도화.
- [ ] 재현성 메타(`deps_digest`, `base_image_digest`, `retriever_commit`) 자동 산출/검증 파이프라인 도입.

## WON'T (이번 범위 제외)

- [ ] 파이프라인 단계/아키텍처 대규모 개편(분산 실행/새 오케스트레이터 등)
- [ ] 외부 인터넷에 노출되는 형태의 실행/배포 자동화

## Quick Map (수정 후보 파일)

- Generator: `agents/generator/service.py`, `agents/generator/synthesis.py`
- Researcher: `agents/researcher/service.py`
- Executor: `executor/runtime/docker_local.py`
- Verifier: `evals/poc_verifier/rule_based.py`, `evals/poc_verifier/scenarios.py`, `evals/poc_verifier/registry.py`
- Reviewer: `agents/reviewer/service.py`
- Rules/Templates/Hints: `docs/evals/rules/`, `workspaces/templates/`, `rag/hints/`
