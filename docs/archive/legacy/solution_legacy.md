# vulDocker 동적화 설계안 (Legacy Reference)

> Archived reference. 이 문서는 historical snapshot이며 active source가 아니다.
>
> 현재 canonical 문서:
> - 문제 정의: `docs/problem.md`
> - 현재 상태: `docs/current_state_gap_analysis.md`
> - 제약조건: `docs/constraints.md`
> - 구현 로드맵: `docs/final_solution.md`

## 설계 요약(핵심 원칙)

- **RuleSpec/runtime 중심 계약**: 성공 조건(서명/FLAG/JSON 키), 서비스 포트/베이스 URL, PoC 엔트리/명령을 “룰/런타임 스펙”이 소유하고 stage들은 이를 소비한다.
- **단일 결정 지점**: 각 stage가 제각각 해석하지 않도록 `ResolvedContract`(해석된 계약)를 1회 산출해 메타에 저장하고 재사용한다.
- **JSON-first 검증**: 가능하면 PoC 출력/요약을 JSON 스키마로 표준화하여 문자열 하드코딩 의존을 줄인다(텍스트는 폴백).
- **폴백 체인 표준화**: `runtime rule` → `static rule` → `generator_template.json` → `generator_manifest.json` → `defaults` 순으로 동일한 결정 로직을 적용한다.

## 데이터 모델(초안)

- `RuleSpec`(v2, `common/rules/__init__.py`)
  - 현재: `scenario_type`, `output(json keys)`, `runtime(assertion_program, success_text_markers, flag_token 등)`까지 지원
  - 확장(계획): `service_port`, `base_url_mode`, `ready_probe`, `poc_cmd`, `sidecar_requirements` 등 “실행 계약” 필드 추가
- `generator_template.json` (템플릿 선택 요약, `agents/generator/service.py`)
- `generator_manifest.json` (합성 산출물, `agents/generator/synthesis.py`)
- `resolved_contract.json` (신규 계획)
  - 위 3개 + Dockerfile/정책을 입력으로 “최종 결정된 계약”을 저장하는 단일 산출물
  - per-bundle 저장: `metadata/<SID>/bundles/<slug>/resolved_contract.json`(multi-vuln) / `metadata/<SID>/resolved_contract.json`(single)

## MoSCoW TODO Checklist

> 표기: `[x]` 완료 / `[ ]` 미완료(Backlog)

## MUST

### ContractResolver 도입(단일 결정 지점)
- [ ] `ResolvedContract` 스키마 정의 + 저장(`resolved_contract.json`)
- [ ] Generator/Executor/Verifier/Reviewer가 contract를 우선 소비하고, 없으면 기존 폴백 유지(점진 도입)
- [ ] contract에 포함될 최소 필드: `service_port/base_url`, `service_entry`, `poc_entry/poc_cmd`, `output(json keys)`, `success 조건`, `ready_probe`, `requires_external_db/sidecars`

### EXECUTE의 스택/언어 독립성 확보
- [x] 컨테이너 readiness probe의 Python **필수 의존 제거**(다중 `tcp/http/shell` probe 폴백; python은 선택 경로)
- [x] `.py`/`python` 강제 제거: `poc.cmd`/`poc_entry` 기반 실행 + suffix allowlist/정책으로 제어
- [ ] sidecar 요구(`requires_external_db`)와 정책 불일치 조기 감지 + 자동 루프 피드백(Generator/Reviewer)

### GENERATE/RESEARCH의 CWE 하드코딩 제거
- [x] Researcher: candidate rule/template 생성에서 CWE-89/352 하드코딩 제거(LLM 기반 `verification_spec`/스캔 기반으로 전환)
- [x] Generator: CWE별 기본 엔드포인트/시그니처/flag 상수 제거(룰/템플릿/manifest/contract 기반으로 생성)
- [x] LLM stub fallback이 특정 CWE(SQLi)로 치우치지 않도록 일반 폴백 체인으로 교체 (`common/llm/provider.py`, `agents/generator/synthesis.py`)

### VERIFY/REVIEW의 계약 정렬
- [ ] `"FLAG"` 기본 마커 관례 의존 최소화(룰/계약이 없으면 flag “비요구” 또는 JSON-only 판정)
- [x] Reviewer 정적 스캔을 SQLi 패턴 하드코딩에서 rule patterns 기반으로 일반화 (`agents/reviewer/service.py`)

## SHOULD

- [ ] Rule v2 스키마 확장(“실행 계약” 포함) + 기존 `docs/evals/rules/*.yaml` 정합 유지(마이그레이션 가이드 포함)
- [ ] “성공한 synthesis 결과”를 템플릿으로 승격(promote)하는 운영 경로 추가(`runtime_templates` → `workspaces/templates`)
- [ ] “레포에 없는 CWE” E2E 케이스 추가 및 회귀 테스트 확장(`tests/e2e/cases/*`)
- [ ] sidecar/네트워크 정책을 템플릿 메타/룰과 연동해 자동 결정(불일치 시 정책 위반으로 fail-fast)

## COULD

- [ ] LLM-assisted verifier 고도화(예산/근거 제한, stub graceful skip, metamorphic 옵션)
- [ ] 다중 컨테이너 스택(예: redis) 지원 확대 + 네트워크 정책 세분화
- [ ] 재현성 메타(`deps_digest` 등) 자동 산출/검증(ops/ci와 연동)

## WON'T

- [ ] 파이프라인 단계/아키텍처 대규모 개편(분산 실행/새 오케스트레이터 등)
- [ ] 외부 인터넷에 노출되는 형태의 실행/배포 자동화

## 점진적 롤아웃(권장)

- [ ] Phase 0: `resolved_contract.json`만 기록(consumer는 기존 로직 사용)
- [ ] Phase 1: Executor/Verifier가 contract 우선 사용(없으면 폴백)
- [ ] Phase 2: Generator/Researcher가 contract/rule 기반으로 기본값을 제거(기존 상수는 deprecated)
- [ ] Phase 3: 상수/하드코딩 제거 및 정책 강화(테스트/회귀 포함)

## 완료 기준(예시)

- [ ] 템플릿/룰이 없는 신규 CWE 입력에서도 VERIFY가 `unsupported`가 아니라 `evaluated`로 종료되고, evidence가 남는다.
- [ ] Python이 없는 컨테이너에서도 readiness probe 및 PoC 실행이 가능하다(계약 기반).
