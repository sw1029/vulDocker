# LLM+RAG 기반 동적 취약 삽입 – 범용화 및 오류 해소 구현 계획(한국어)

본 문서는 “LLM + RAG를 이용한 동적 취약점 삽입이 가능한 Docker 이미지”를 실무적으로 구현/운영하기 위한 단계별 계획을 정리한다. 기존 로그에서 확인된 PACK 차단(Reviewer blocking) 문제를 포함하여, 취약군(CWE) 확장, 검증 표준화, 실행기 보안/준비성, CI 일관성까지 아우르는 범용화 전략을 제시한다.

## 1. 배경과 문제 요약
- 취약군 정합성: 템플릿 스코프가 SQLi에 편향되어 CSRF(CWE-352)가 검증기 미등록(unsupported) → Reviewer가 blocking → PACK 실패.
- LLM+RAG 비활성: 템플릿 경로에서는 LLM 결과가 실제 산출물에 거의 반영되지 않아 동적 삽입의 의도가 약화.
- 실행/운영: 사이드카 무조건 기동, readiness 단순 대기, 보안 옵션 미적용 등 운영·보안 정합성 부족.
- 평가: SQLi는 FLAG 요구로 강화되었으나 메타모픽(다중 payload)의 표준화, CSRF 등 타 취약군 규칙 부재.

## 2. 목표
- 신규 CWE/스택에도 쉽게 확장되는 일반화 구조.
- RAG/Researcher 신호와 실패 맥락이 Generator 산출물(합성/보강)에 실질 반영.
- 검증 플러그인/증거 규칙을 선언적·플러그블하게 운영.
- 실행기 보안/준비성/요약 정합성 개선으로 재현성/관측성 강화.

## 3. 원칙
- 하이브리드 기본화: 합성(synthesis) 경로를 항상 활성, 템플릿은 일치할 때만 재사용 + 필요 시 보강(패치).
- 강 일치성: CWE 태그 ∧ DB ∧(가능 시) 패턴이 일치하지 않으면 합성으로 전환.
- 규칙 주도: 검증(증거/메타모픽)과 템플릿 보강 기준을 선언적 규칙으로 관리.
- 안전 경계: 패치/빌드/실행에 allowlist·용량·보안 정책 적용.

## 4. 단계별 구현(로드맵)

### P0 — 즉시 적용(로그 오류 해결 + 최소 범용화)
1) CSRF(CWE-352) 전 경로 구축
   - **템플릿**: `workspaces/templates/csrf/flask_sqlite_csrf/`
     - `template.json` – tags = `["cwe-352", "csrf", "flask", "sqlite"]`, `pattern_id=csrf-missing-token`, `requires_external_db=false`.
     - `app.py` – `/transfer` POST 요청이 토큰 검증 없이 `accounts.balance`를 감소시키며 `csrf_flags.token`을 JSON 응답에 포함.
     - `schema.sql` – `accounts`와 `csrf_flags` 테이블 생성, FLAG 값을 삽입.
     - `poc.py` – CSRF 토큰 없이 `/transfer` 호출 → “CSRF SUCCESS”와 FLAG 문자열 출력.
     - `Dockerfile`, `requirements.txt`, `README.md` 포함.
   - **검증기**: `evals/poc_verifier/csrf.py`
     - 구현: `has_marker = "CSRF SUCCESS" in log`, `has_flag = "FLAG" in log`, 두 조건 모두 충족 시 pass.
     - 레지스트리: `evals/poc_verifier/main.py`에서 `from evals.poc_verifier import csrf` 로드.
   - **Generator 확장**: `TemplateRegistry` 기본 root를 `workspaces/templates/`로 상향하여 `<cwe>/**/template.json`을 자동 탐색.

2) Reviewer/PACK 흐름 안정화
   - Reviewer는 동일 플러그인을 호출하므로 CSRF 번들을 `status=evaluated`로 판단, blocking 제거.
   - CI에서 `plan.policy.allow_intentional_vuln == true`일 경우 `python orchestrator/pack.py --sid ... --allow-intentional-vuln`로 호출해 정책과 일치.

3) 사이드카/준비성 개선(최소)
   - `_bundle_requires_external_db()` 함수로 템플릿/manifest/runtime을 확인해 external DB가 필요할 때만 `_start_sidecars()` 실행.
   - MySQL readiness는 `docker exec <sidecar> mysqladmin ping`을 재시도하며, 실패 시 `ExecutorError`로 중단. Web 서비스는 기존 wait_seconds를 유지(추후 HTTP 프로브 도입 예정).

4) SQLi 증거 유지
   - `workspaces/templates/sqli/flask_sqlite_raw/`는 `audit_tokens` 테이블과 UNION 기반 PoC를 유지하여 로그에 FLAG가 항상 출력되도록 지속 관리.

### P1 — 일반화(LLM 보강 + 규칙/평가 표준화)
1) 템플릿 보강(Template Augmentation)
- 흐름: materialize → `docs/evals/rules/<cwe>.yaml` 로드 → 증거 조건 위반 시 augmentation 훅 호출.
- LLM이 패치 DSL(JSON)을 출력(파일 path, op, body). 예) `{ "op": "append", "path": "schema.sql", "body": "INSERT INTO audit_tokens..." }`.
- 허용 경로: Dockerfile, *.py, *.sql, poc.*, requirements*.txt. 크기 제한(예: 4 KB/patch) 적용.
- 패치 후 `detect_required_deps` 재실행 및 Docker build dry-run. 실패 시 deterministic fallback 패치 적용.

2) Evidence Rules 스키마화
- 스키마 필드: `signals[]`, `flag_patterns[]`, `metamorphic.policy`, `mandatory_rules`, `examples`.
- 로더(`evals/poc_verifier/loader.py`)는 각 YAML을 파싱해 플러그인/LLM 프롬프트에 주입.
- 규칙 ID/버전은 `artifacts/.../reports/evals.json`에 기록.

3) 메타모픽 표준화
- Executor는 이미 payload 배열을 순회 실행(`run_container_with_poc`). 검증기는 “# Payload n” 구간별로 증거를 확인.
- `evals/poc_verifier/main.py`는 집계 필드 `metamorphic.total|passed|policy`를 결과 JSON에 추가.
- 실패 시 evidence에 어떤 payload(지표)에서 탈락했는지 기록.

4) LLM 보조 검증기
- 1차 플러그인 결과가 `unsupported/failed`일 때만 LLM을 호출해 JSON 스키마(판단·근거·assertion program)를 생성.
- Assertion 실행기는 로컬에서 regex/contains/number_delta 등 단순 연산으로 제안의 진위를 검증하고 최종 pass/fail을 결정(`evals/assertions.py`, `evals/poc_verifier/llm_assisted.py`).
- 정책 토글: `requirement.policy.verifier.llm_assist`, `strict` 옵션(신뢰도 high 전용), mandatory rules.
- CI 로그와 Reviewer도 LLM 검증 결과/근거를 재사용해 일관된 loop 제어.
  - 프롬프트 빌더: `common/prompts/templates.py::build_llm_verifier_prompt()`.
  - LLM 응답(JSON) 필드: `verify_pass`, `confidence`, `rationale`, `proposed_assertions[]`, `extracted_evidence[]`, `metamorphic`.
  - Assertion 실행기는 실패/성공 근거를 로그 오프셋과 함께 반환 -> Reviewer/Pack 보고서에 첨부.

### P2 — 실행·보안·다언어 확장
1) 실행기 플러그블 프로브/보안 정책
- readiness: `type(http|tcp|mysqladmin)`, `target`, `timeout`, `retries` 선언으로 실행.
- 보안: 기본 `--read-only`, `--tmpfs /tmp:rw,noexec,nosuid`, `--security-opt no-new-privileges:true`, `--cap-drop=ALL` 적용.
- egress 화이트리스트: executor policy에서 네트워크 허용 목록 선언.
  - 구현: `executor/runtime/probes.py` (프로브 타입별 함수), `executor/runtime/security.py` (RunCommand wrapper가 옵션 주입).
  - 정책 경로: `plan.policy.executor.security`에 read_only/tmpfs/seccomp_profile/egress_allowlist 선언.

2) 템플릿 레지스트리 범용화
- 우선순위: `workspaces/templates/<cwe>/**` → `workspaces/templates/common/**` 폴백.
- 매칭 가중치에 언어/프레임워크/패턴 포함(설정화 가능).
  - TemplateSpec 메타필드 `language`, `framework`, `requires_external_db`를 JSON에 명시.
  - 가중치 계산식 예: vuln_tag +3, db +2, pattern +1, language/framework 매칭 +0.5씩.
  - VariationManager seed를 CWE별 offset으로 분기해 다양성 유지.

3) DepGuard 다언어
- Python/Node/Go/Rust 등 모듈 추가, SBOM↔requirements 교차검증 리포트화.
  - 공통 인터페이스: `detect_required(language_manifest) -> Dict[str, Set[str]]`, `extract_declared(...)`.
  - SBOM 비교 스크립트 `tools/sbom_compare.py` 작성 → PACK 시 리포트 첨부.

## 5. 파일/코드 변경 체크리스트
- 신규
  - `workspaces/templates/csrf/flask_sqlite_csrf/*`
  - `evals/poc_verifier/csrf.py`, `evals/poc_verifier/loader.py`
  - `docs/evals/rules/cwe-89.yaml`, `docs/evals/rules/cwe-352.yaml`
- 변경
  - `agents/generator/service.py`: 템플릿 루트 상향, `_select_template()` 가중치 보강, augmentation 훅 추가
  - `executor/runtime/docker_local.py`: 사이드카 조건부 기동, readiness 프로브, 보안 실행 옵션
  - `evals/poc_verifier/main.py`: 메타모픽 집계 필드 기록
  - `ops/ci/run_case.sh`: PACK 우회 플래그(정책 기반) 호출 로직

## 6. 수용 기준(현장 검증)
- Base 예제에서 SQLi/CSRF 모두 `status=evaluated` ∧ `verify_pass=true`.
- Reviewer blocking=false → PACK 통과(우회 없이). 정책 우회 시 명시적 로그 출력.
- Executor summary에 `invocation` 기록, build/run OR 병합 유지. readiness 프로브 로그 확인.
- Evals에 `metamorphic` 집계 및 Evidence Rules ID/버전 기록.

## 7. 운영/관측성
- 선택 점수/규칙 평가/패치 적용 diff/보안 옵션/프로브 결과를 구조화된 로그로 남김.
- KPI: 합성 성공률, 검증 통과율, 규칙 위반·보강 빈도, 실행 시간/비용.

## 8. 리스크/롤백
- 신규 검증 규칙으로 오탐 증가 가능 → 규칙 스키마에 `strict=false` 완화 옵션.
- 비용 증가(LLM 호출/메타모픽) → 하이브리드에서 “템플릿 보강만” 모드, payload 수 상한.
- 기능 토글: requirement에서 generator_mode/matching_policy/augmentation_on 을 제어.

## 9. 타임라인 제안
- P0(1~2일): CSRF 템플릿/검증기, 레지스트리 상향, 사이드카 조건부, 간단 프로브, PACK 정책 우회.
- P1(3~5일): 템플릿 보강/패치 DSL, Evidence Rules/로더, 메타모픽 집계.
- P2(>1주): 프로브/보안 플러그블, DepGuard 다언어, 템플릿 레지스트리 범용화, 비용 최적화.

## 10. 연관 문서
- `docs/architecture/llm_rag_dynamic_vuln_insertion.md`
- `docs/architecture/dynamic_vuln_generation_improvements.md`
- `docs/evals/specs.md`, `docs/executor/security_policies.md`

## 11. 진행 상황 (2025-11-09)
- CSRF(CWE-352) 템플릿과 검증 플러그인이 추가되어 다중 취약군을 지원(`workspaces/templates/csrf/*`, `evals/poc_verifier/csrf.py`).
- 템플릿 레지스트리가 전체 `workspaces/templates/`를 탐색하고 pattern_id 가중치를 반영(`agents/generator/service.py`).
- Executor가 외부 DB 요구 시에만 sidecar를 기동하고 mysql readiness 프로브/보안 옵션을 적용(`executor/runtime/docker_local.py`).
- CI 파이프라인이 `allow_intentional_vuln` 정책에 따라 PACK 단계 플래그를 자동 적용(`ops/ci/run_case.sh`).
- LLM 보조 검증기가 도입되어 플러그인 부재/실패 시에도 assertion 실행을 거쳐 평가(`evals/poc_verifier/llm_assisted.py`, `evals/assertions.py`, `common/prompts/templates.py`).

## 12. 추가 품질 개선(권고/범용성)
- user_deps 조건부 삽입: 템플릿 메타(`db`, `requires_external_db`)와 `runtime.db`를 비교해 불필요한 DB 드라이버 삽입을 방지 (`agents/generator/service.py`).
- PACK 게이트 메시지 억제: Reviewer 성공 시 우회 경고를 suppress하고, 리뷰 실패시에만 우회 로그를 표기 (`orchestrator/pack.py`).
- Evals 리포트 보강: `metamorphic.total|passed` 집계 및 assertion 근거의 해시/요약을 포함해 증거 무결성 강화를 권고 (`evals/poc_verifier/main.py`, `evals/poc_verifier/llm_assisted.py`).
