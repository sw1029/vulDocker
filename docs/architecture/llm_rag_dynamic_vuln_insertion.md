# LLM + RAG 기반 동적 취약 삽입 설계 및 구현안

본 문서는 현재 코드베이스의 동작과 문서 의도를 교차 검토하여, 취약점의 동적 삽입을 LLM + RAG 중심으로 강화하기 위한 구체적인 구현 로드맵을 제시한다. 목표는 템플릿 기반 샘플을 넘어, 요구/리서치/힌트/실패 맥락을 근거로 LLM이 실제로 취약 코드를 생성·보강하고, 검증/리뷰/루프를 통해 수렴하도록 만드는 것이다.

## 1. 목표와 범위
- 목표
  - RAG + Researcher 보고서 → Generator가 LLM 합성/보강으로 취약을 “동적 삽입”
  - 합성 실패/검증 실패를 Reflexion 메모리로 축적 후 재시도하여 수렴
  - 취약군(CWE)·스택·패턴과 일치하는 증거(FLAG 등)가 로그에 남도록 일관화
- 범위
  - Researcher → Generator → Executor/Evals → Reviewer → Reflexion 루프
  - 템플릿/합성/하이브리드 경로, DepGuard, SBOM, 보안/네트워크, 메타모픽

## 2. 현행 과제 요약(정합성 관점)
- 템플릿 경로 우세: `generator_mode: template`가 기본이어서 합성(synthesis) 경로가 비활성.
- 템플릿 가용성 판정이 완화(OR)되어 CWE-352도 SQLi 템플릿으로 귀결.
- Researcher 보고서가 템플릿 선택에 약하게 반영(태그 가중치)되며 구조적 전환(DB/패턴) 유도가 미흡.
- Eval은 SQLi에서 FLAG 요구, SQLite 템플릿은 FLAG 미노출로 항상 실패.
- Reviewer/Reflexion 루프의 CI 연계가 약해 failure_context 축적 효과가 낮음.
- 보안/메타모픽/커버리지 등 문서 의도가 일부 미적용.

## 3. 설계 원칙
- 하이브리드 기본화: 템플릿 우선이 아니라 LLM 합성 우선+템플릿 폴백 또는 템플릿+보강(패치) 방식을 채택.
- 강한 일치성: vuln 태그 ∧ DB ∧ 패턴이 일치하지 않으면 합성으로 전환.
- RAG 우선: Researcher 보고서/힌트/실패 문맥은 Generator의 의사결정에 “강한 제약 또는 높은 가중치”로 반영.
- 증거 일관성: 취약군별 검증 플러그인의 증거 요구(예: SQLi FLAG)가 생성물/PoC와 일치하도록 템플릿과 합성 모두 정렬.
- 루프 중심: 실패는 Reflexion 메모리에 축적하여 다음 프롬프트에 주입.

## 4. 아키텍처 변경(요약)
- Template 가용성 판정 강화: vuln 태그 ∧ DB ∧(선택) pattern_id 일치일 때만 “viable”.
- Generator 기본 모드: `generator_mode: hybrid`.
- Template 보강 단계: 템플릿 materialize 후, RAG/검증 요구와 불일치(예: FLAG 미노출) 시 LLM 패치(또는 결정적 패치) 적용.
- Researcher 연계 강화: 보고서의 `tech_stack_candidates`/`deps`/`preconditions`를 강 제약으로 사용.
- Synthesis 프롬프트 강화: RAG 힌트/실패 맥락/메타모픽 조건/DepGuard 제약을 명시.
- Eval/PoC: 메타모픽 페이로드, 플러그인 확장(CSRF 등), 결과 집계 일관화.
- Executor: readiness 개선, 요약 필드 정합성, 사이드카 최적화, 네트워크 정책 강화.

## 5. 단계별 구현 계획(세부)

### 5.1 Researcher × RAG
- 변경점
  - 보고서 스키마 확장(비파괴): `stack_hard_constraints`, `db_preferences`, `poc_invariants` 필드 추가 제안.
  - 검색→로컬 RAG 스냅샷(`rag/static_loader.py`) 결합은 유지.
- 코드 연계
  - `agents/researcher/service.py:1` 구조는 유지, `build_researcher_prompt()`에 스키마 가이드를 명확히 포함(`common/prompts/templates.py:120`).
  - 보고서 저장: `metadata/<SID>/bundles/<slug>/researcher_report.json`.

### 5.2 Generator: 선택·합성·보강
- 템플릿 가용성(AND)
  - 현재: vuln 태그 OR DB 일치 시 viable(`agents/generator/service.py:493`).
  - 변경: vuln 태그 ∧ DB ∧(가능하면) pattern_id 일치가 기본. 일부 예외(CWE 범용 템플릿)는 가중치 하향.
- 기본 모드: hybrid
  - `inputs/*.yml` 기본값을 `generator_mode: hybrid`로 권장.
  - hybrid 흐름: 합성 우선 시도 → guard 실패 시 템플릿 materialize → LLM 보강 패치.
- 템플릿 보강 패치(Template Augmentation)
  - 목적: 검증기 요구를 충족(예: SQLite 템플릿에 FLAG 테이블/레코드 추가, 엔드포인트에서 노출).
  - 절차
    1) 보강 필요 탐지: CWE/검증기 증거 규칙과 템플릿 메타/코드를 비교.
    2) LLM 패치 생성: “파일 경로+삽입/치환 블록” JSON(미니 manifest)을 출력.
    3) 안전 필터: allowlist 경로만 허용(Dockerfile, *.py, *.sql, poc.*). 크기 제한 유지.
    4) 적용: workspace에 패치 반영, DepGuard/빌드 검증.
  - 실패 시: 결정적(D) 패치 라이브러리로 fallback(예: SQLi-SQLite FLAG 주입 표준 패치).
- 합성 경로(Synthesis)
  - 프롬프트에 포함: RAG 컨텍스트, CWE별 힌트(`rag/hints/cwe-xx/*.md`), failure_context, 메타모픽 조건, DepGuard 제약.
  - 가드레일: `agents/generator/synthesis.py`의 `_guard_manifest()`를 유지하고 SQLi 정적 시그널(`evals/static_signatures/sqli.py:1`)을 점수에 반영.
- Researcher 가중치 강화
  - `tech_stack_candidates`에 포함된 DB/프레임워크는 선택 점수에 강 가중치 또는 하드 제약.
  - `deps`는 DepGuard 초기 선언에 병합.
- 템플릿 레지스트리 확장
  - 스캔 경로: `workspaces/templates/<cwe>/**` 우선, 그 외는 공용(`sqli`) 폴더.
  - 메타(`template.json`)에 `cwe`, `requires_external_db`, `tags`, `ports` 유지.

### 5.3 Executor / CI / 보안
- readiness
  - Web: `/healthz` 또는 대상 라우트 200이 될 때까지 폴링.
  - DB: `mysqladmin ping` 등 프로브 도입. 현재 `wait_seconds` 고정보다 우선.
- 요약 일관성
  - `run/.../summary.json`에 `invocation: build|run` 명시.
  - 기록 시 기존 build/run 성공 상태를 OR 병합 후 저장(표면 혼동 방지). 인덱스 병합(`executor/runtime/docker_local.py:276-313`)은 유지.
- 사이드카 최적화
  - 템플릿/합성 결과가 외부 DB를 사용하지 않으면 sidecar 생략.
- 네트워크/보안 정책
  - 기본 rootless, read-only, seccomp/AppArmor 프로파일 적용(`docs/executor/security_policies.md`).
  - egress 화이트리스트와 사용자 지정 네트워크명 정책 반영.

### 5.4 Evals / Reviewer / 루프
- 플러그인
  - SQLi: FLAG 요구 유지. 템플릿/합성은 이를 충족.
  - CSRF: 신규 플러그인 추가(CSRF 토큰 부재로 상태 변경, Origin/Referer 검증 부재 등).
- 메타모픽
  - `requirement.poc_payloads[]`가 있으면 모든 payload 성공 시 pass.
- Reviewer × Reflexion
  - Reviewer가 `evaluate_with_vuln()`을 호출하여 미지원 취약군은 blocking으로 보고.
  - CI에서 Reviewer를 포함해 실패를 `rag/memories`에 축적 → 다음 합성 프롬프트의 `failure_context`에 자동 주입.

### 5.5 DepGuard / SBOM
- 템플릿 경로에도 최소 DepGuard 적용
  - workspace에서 파이썬 임포트 추출 → requirements.txt와 교차 → 누락 자동 패치(옵트인) 후 빌드(
  - SBOM(syft) 결과와 requirements 교차검증 리포트화.

## 6. 스키마/설정 변경 제안
- Plan / Requirement
  - `generator_mode: hybrid`(기본), `poc_payloads: []`, `allow_external_db`, `network_name`(옵션)
  - `pattern_id`를 템플릿/합성 점수에 반영.
- Generator Manifest(합성)
  - 기존 스키마 유지 + 선택적 `patches[]`(파일·치환 블록) 허용(템플릿 보강 재사용 목적).
- Eval 결과
  - `metamorphic: { total, passed }` 보강.

## 7. 단계별 적용 로드맵
- P0(정합성 회복)
  - viable 판정 AND로 수정, 기본 hybrid 권장.
  - SQLite 템플릿에 FLAG 삽입(또는 검증기 완화 중 하나 선택).
  - Executor `summary.json`에 `invocation` 추가 및 OR 병합 저장.
  - Reviewer를 CI에 포함하여 Reflexion 연계.
- P1(동적 삽입 강화)
  - 템플릿 보강 LLM 패처 구현 + 결정적 패치 fallback.
  - CSRF 템플릿/검증기/힌트 추가.
  - 메타모픽 평가/집계 도입.
- P2(보안/운영)
  - rootless/rofs/seccomp/AppArmor 적용 + egress 화이트리스트.
  - SBOM↔requirements 교차검증 리포트화.

## 8. 테스트/수용 기준
- 합성 성공률: 가드 위반 0개 후보의 비율 ≥ X%.
- Eval 일치율: SQLi/CSRF 등 플러그인 요구와 템플릿/합성 산출물의 일치율 100%.
- 메타모픽 통과율: 지정된 변형 payload 모두 성공.
- 재현성: Variation Key 동일 시 동일 산출물/평가.

## 9. 코드 변경 포인터(참조)
- 템플릿 가용성/선택: agents/generator/service.py:452, 493
- 하이브리드 경로: agents/generator/service.py:301-319, 338-360
- 합성 가드/정적 점수: agents/generator/synthesis.py:229-260, 480-579, evals/static_signatures/sqli.py:1
- Researcher↔Generator 가중치: agents/generator/service.py:452-476
- Executor 인덱스 병합/요약: executor/runtime/docker_local.py:276-313, 224-272
- Evals 플러그인: evals/poc_verifier/*.py
- Reflexion 메모리: rag/memories/__init__.py:79-116

## 10. 부록: 예시 정책/패치
- SQLi(SQLite) 템플릿 보강(개념)
  - schema.sql에 `audit_tokens(token)` 테이블 + FLAG 삽입
  - `/profile`에서 UNION으로 `audit_tokens` 노출
  - PoC는 FLAG 문자열이 로그에 등장하도록 유지

본 설계대로 적용 시, 템플릿 기반 재현 데모에서 한 단계 더 나아가 RAG/LLM이 실제 취약 삽입의 “주체”가 되고, 증거·보안·루프·다양성이 함께 강화된다.

## 11. 진행 상황 업데이트 (2025-11-09)
- ✅ Template viable 판정이 vuln 태그 ∧ DB 일치 조건으로 강화되고, 기본 Generator 모드가 `hybrid`로 전환됨 (`agents/generator/service.py`).
- ✅ `flask_sqlite_raw` 템플릿에 FLAG 토큰 테이블이 추가되고 PoC 기본 payload가 UNION 기반으로 갱신되어 검증 요구와 일치함 (`workspaces/templates/sqli/flask_sqlite_raw/app/*`).
- ✅ Executor `summary.json`에 `invocation` 필드가 기록되고, build/run 성공 여부를 기존 기록과 OR 병합하도록 수정됨 (`executor/runtime/docker_local.py`).
- ✅ CI 파이프라인이 Reviewer 단계를 포함하여 Reflexion/loop 메커니즘과 연동됨 (`ops/ci/run_case.sh`).
- ✅ CSRF(CWE-352) 템플릿/검증 플러그인 추가 및 템플릿 레지스트리 범용화로 다중 취약군 지원이 확장됨 (`workspaces/templates/csrf/*`, `evals/poc_verifier/csrf.py`, `agents/generator/service.py`).
- ✅ Executor가 외부 DB 요구 시에만 sidecar를 기동하고 mysql readiness 프로브를 수행, PACK 단계는 정책 기반 우회 플래그를 지원함 (`executor/runtime/docker_local.py`, `ops/ci/run_case.sh`).
- ✅ LLM 보조 검증기가 도입되어 플러그인 부재/실패 시에도 assertion 실행을 통해 평가를 이어갈 수 있음 (`evals/poc_verifier/registry.py`, `evals/poc_verifier/llm_assisted.py`, `evals/assertions.py`).
