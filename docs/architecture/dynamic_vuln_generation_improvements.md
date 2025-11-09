# 동적 취약 Docker 생성 개선안

본 문서는 `inputs/base_requirement.yml` 기반 시나리오 실행에서 확인된 미흡점을 해소하고, 자연어 요구 ↔ 동적 취약 Docker 생성 파이프라인의 범용성을 높이기 위한 구체적인 구현안을 정리한다. 핵심 개선 항목은 템플릿 선택 정확도, LLM 합성 폴백, PoC 검증 강도, 실행기 메타데이터 정합성, 연구(Researcher) 정보 활용, 및 장기 확장 로드맵으로 구성된다.

참고: LLM+RAG을 이용한 “동적 취약 삽입”에 초점을 맞춘 상세 설계와 단계별 구현안은 별도 문서에 정리되어 있다. docs/architecture/llm_rag_dynamic_vuln_insertion.md
또한, 범용화 및 오류 해소 관점의 구체적 구현 계획(한국어)은 다음 문서에 정리되어 있다. docs/architecture/dynamic_vuln_generalization_impl_plan_ko.md

## 1. 현행 과제 요약
- **CWE 라벨링 및 스택 불일치**: CWE-352 번들도 SQLi 템플릿으로 생성되어 취약군 정확도가 떨어짐.
- **연구↔생성 간 단절**: Researcher 보고서의 환경/전제 정보를 Generator가 적극 활용하지 않아 잘못된 템플릿이 선택됨.
- **PoC 검증 약함**: SQLi 성공 문자열만 확인하여 데이터 노출 증거가 부족.
- **Executor 결과 오기록**: build/run을 별도 호출하면 run index가 최근 호출 기준으로 덮여 `build_passed=false`로 남음.
- **차원/다양성 고정**: SQLi 템플릿 2종에만 의존하여 다양성 지표가 0에 수렴.

## 2. 즉시 적용된 수정
| 구분 | 구현 내용 | 파일 |
| --- | --- | --- |
| 템플릿 선택 | `vuln_id` 태그와 `runtime.db`가 모두 일치하는 템플릿만 사용, 부적합 시 LLM 합성/하이브리드 폴백 | `agents/generator/service.py` |
| Generator 모드 | 기본 `generator_mode`를 `hybrid`로 설정하여 합성→템플릿 보강 흐름을 기본값으로 사용 | `agents/generator/service.py`, `inputs/*.yml` 권장 |
| 실행기 인덱스 | 기존 인덱스를 병합하여 build/run 상태 보존 | `executor/runtime/docker_local.py` |
| Executor 요약 | `summary.json`에 `invocation`을 기록하고 build/run 성공 여부를 기존 기록과 OR 병합 | `executor/runtime/docker_local.py` |
| SQLi 검증 | “SQLi SUCCESS” + FLAG 유출 증거를 동시 요구 | `evals/poc_verifier/mvp_sqli.py` |
| SQLite 템플릿 | SQLite 템플릿/PoC가 FLAG 토큰을 포함하도록 스키마·payload 갱신 | `workspaces/templates/sqli/flask_sqlite_raw/app/*` |
| Reviewer 연동 | CI 파이프라인에 Reviewer 단계를 포함하여 Reflexion/loop를 자동 실행 | `ops/ci/run_case.sh` |
| CSRF 템플릿/검증 | CSRF(CWE-352) 템플릿 및 검증 플러그인을 추가해 다중 취약군을 지원 | `workspaces/templates/csrf/flask_sqlite_csrf/*`, `evals/poc_verifier/csrf.py`, `evals/poc_verifier/main.py` |
| 템플릿 검색 범위 | 템플릿 레지스트리 기본 루트를 `workspaces/templates/`로 확장, 패턴 가중치 반영 | `agents/generator/service.py` |
| 사이드카 조건부·프로브 | external DB 요구시만 sidecar 기동, mysql readiness 프로브 도입 | `executor/runtime/docker_local.py` |
| PACK 정책 처리 | `allow_intentional_vuln` 설정 시 CI에서 PACK 우회 플래그를 자동 적용 | `ops/ci/run_case.sh` |
| LLM 보조 검증 | 플러그인 부재/실패 시 LLM이 assertion 프로그램을 제안하고 로컬에서 검증 | `evals/poc_verifier/llm_assisted.py`, `evals/assertions.py`, `common/prompts/templates.py` |

## 3. 세부 구현안

### 3.1 템플릿 매칭 & 합성 폴백
1. **템플릿 메타 태그 정규화**
   - `workspaces/templates/**/template.json`에 `tags`로 CWE, DB, 프레임워크 태그를 유지.
   - `TemplateSpec.tags`/`TemplateSpec.db` accessor를 통해 Generator가 비교.
2. **우선순위 점수**
   - `vuln_id` 태그 일치 +3, `runtime.db` 일치 +2, `stability`를 tie-breaker로 사용.
3. **폴백 정책**
   - 요구 조건과 맞는 템플릿이 없으면 자동으로 synthesis 루프 실행.
   - hybrid 모드 권장(템플릿 우선, 실패 시 합성).
4. **Researcher 정보 반영(추가 예정)**
   - `researcher_report.json`의 `preconditions`, `tech_stack_candidates`, `deps`를 `_select_template` 점수에 가산하여 자연어 요구/검색 결과를 활용.

### 3.2 PoC 검증 강화
1. **SQLi**
   - 로그에서 FLAG/토큰과 같은 민감 데이터 누출 여부를 확인.
   - 향후 `evals/metamorphic/sqli.py`를 추가해 공백/주석/대소문 변형 payload 자동 실행.
2. **플러그인 구조**
   - `evals/poc_verifier/__init__.py`에서 vuln_id별 검증기를 라우팅.
   - Reviewer도 동일 플러그인을 호출하여 로그 근거를 일치시키고, 증거 부재 시 LOOP를 강제.
3. **CSRF/XSS 등 확장**
   - 신규 템플릿과 함께 PoC 검증기를 추가해 취약군별 성공 조건을 명확히 문서화.

### 3.3 Executor & CI
1. **런 로그/인덱스 정합성**
   - `_write_index`가 이전 빌드 결과를 OR 병합해 `build_passed`가 거짓으로 남지 않도록 함.
2. **메타모픽 실행 루프**
   - 계획: `plan.requirement.poc_payloads` 입력을 허용하고 `run_container_with_poc`가 payload 배열을 순회 실행하도록 확장.
3. **보안 정책 적용**
   - rootless + read-only + seccomp/AppArmor 프로파일을 `executor/runtime/docker_local.py`에 적용.
   - 네트워크 egress 제어는 `NetworkPool` 단계에서 허용 도메인 화이트리스트를 확인.
4. **사이드카 준비 상태**
   - 현재 `wait_seconds` 대기 → `mysqladmin ping` 등 프로브 호출로 대체 예정.

### 3.4 다양성/차원 관리
1. **LHS 샘플러**
   - PLAN 단계에서 언어/프레임워크/DB/인코딩 차원에 대해 Latin Hypercube Sampling을 적용해 시나리오 다양성 확보.
2. **지표 산출**
   - `evals/diversity_metrics.py`가 실제 선택 분포 기반으로 샤논 엔트로피/시나리오 거리를 계산하도록 개선.

### 3.5 의존성 가드
1. **중복 드라이버 정리**
   - SQLi 템플릿에서 `pymysql` vs `mysql-connector-python` 중 하나만 사용하도록 정리.
2. **SBOM ↔ requirements 교차검증**
   - Syft SBOM 결과와 `requirements*.txt`를 비교해 누락/불필요 항목을 보고.
3. **DepGuard 확장**
   - `agents/generator/synthesis.py`의 `detect_python_required` 결과를 자동 패치하고, Stdlib/denylist 로깅을 강화.

### 3.6 추가 품질 개선(운영 권고)
- 사용자 의존성(user_deps) 조건부 삽입
  - 템플릿 메타(`db`, `requires_external_db`)와 `requirement.runtime.db`를 기준으로 DB 드라이버 등 불필요 deps 삽입을 방지.
  - 예: SQLite 템플릿에서는 `pymysql` 삽입 생략. 적용 위치: `agents/generator/service.py::_apply_user_deps_to_workspace()`.
- PACK 게이트 메시지 정제
  - Reviewer가 성공한 경우에는 “우회” 경고를 출력하지 않도록 억제하거나, 리뷰 실패시에만 `--allow-intentional-vuln` 우회 메시지를 출력.
  - 적용 위치: `orchestrator/pack.py::assert_review_passed()`.
- Evals 리포트 강화
  - 결과 JSON에 `metamorphic: { total, passed }` 필드를 포함(다중 payload 신뢰도 확인용).
  - Assertion 기반 검증(LLM 보조 포함)의 통과/실패 근거 요약과 해시를 포함하여 증거 무결성/축약성을 확보.
  - 적용 위치: `evals/poc_verifier/main.py`, `evals/poc_verifier/llm_assisted.py`.

## 4. 장기 로드맵
| 단계 | 목표 | 내용 |
| --- | --- | --- |
| P0 (완료) | 기본 정확도 개선 | 템플릿 매칭 + 합성 폴백, SQLi 검증 강화, build/run 인덱스 병합 |
| P1 | 취약군 확장 & 검증 플러그인화 | CSRF/XSS 템플릿 추가, 메타모픽 실행, Reviewer/Eval 플러그인 라우팅 |
| P2 | 보안/격리 준수 | rootless/rofs/seccomp/AppArmor, 네트워크 egress 필터, Incident 리포트 |
| P3 | 다양성/차원 자동화 | LHS 기반 차원 샘플링, Variation Key 자동 조정, 지표 기반 피드백 루프 |

## 5. 문서 업데이트 체크리스트
- `docs/requirements/goal_and_outputs.md`: `generator_mode: hybrid`, `poc_payloads[]`, 템플릿 매칭/폴백 규칙 추가.
- `docs/architecture/agents_contracts.md`: 검증 플러그인/증거 규칙/LLM 합성 폴백 계약 명시.
- `docs/executor/security_policies.md`, `docs/ops/security_gates.md`: 실제 적용 파라미터, seccomp/AppArmor 프로파일 경로, SBOM 게이트 결과 기록 절차 반영.
- `docs/evals/specs.md`: SQLi 증거 기준 및 메타모픽/FLAG 검증을 포함하도록 업데이트.

## 6. 적용 가이드
1. 요구서 작성 시 `runtime.db`, `generator_mode`, `user_deps`를 명확히 명시해 템플릿 매칭을 돕는다.
2. 새 CWE를 도입할 때는 템플릿 메타(`tags`, `db`, `requires_external_db`)와 검증기 플러그인을 동시에 추가한다.
3. Executor 호출은 가능하면 `--build --run`을 단일 실행으로 호출하고, 다중 payload 테스트는 `plan.requirement.poc_payloads`를 통해 관리한다.
4. LLM Researcher가 제공하는 전제/참조를 Generator가 읽을 수 있도록 메타데이터 경로(예: `metadata/<SID>/bundles/<slug>/researcher_report.json`)를 계약 문서에 명시하고 코드에서 로드한다.

위 개선안을 순차적으로 적용하면, 자연어 요구 조건을 근거로 다양한 취약 템플릿/합성 결과를 안정적으로 선택하고, PoC 증거·보안 정책·다양성 지표가 강화된 동적 취약 Docker 생성 파이프라인을 구축할 수 있다.

## 7. 진행 상황 (2025-11-09)
- Researcher 보고서 기반 템플릿 점수 반영 및 LLM 폴백 자동화 구현(`agents/generator/service.py`).
- 템플릿 가용성(태그 ∧ DB) 강화 및 기본 `generator_mode=hybrid` 적용으로 합성 경로가 기본값이 됨(`agents/generator/service.py`).
- SQLite 템플릿/PoC가 FLAG 증거를 포함하도록 보강되어 SQLi 검증 요구와 일치(`workspaces/templates/sqli/flask_sqlite_raw/app/*`).
- Executor 요약/인덱스가 build/run 상태를 OR 병합하고 `invocation`을 기록(`executor/runtime/docker_local.py`).
- PoC 검증 플러그인 레지스트리 + 공용 CLI 도입, Reviewer가 동일 플러그인을 사용하도록 변경(`evals/poc_verifier/*`, `agents/reviewer/service.py`, `ops/ci/run_case.sh`).
- CI 파이프라인이 Reviewer 단계를 포함하여 Reflexion/loop 자동 실행( `ops/ci/run_case.sh`).
- `poc_payloads[]` 입력을 통해 Executor가 다중 payload를 순차 실행하도록 확장(`executor/runtime/docker_local.py`).
- CSRF 템플릿/PoC/검증기가 추가되어 CWE-352도 자동 생성·검증(`workspaces/templates/csrf/*`, `evals/poc_verifier/csrf.py`).
- 템플릿 레지스트리가 전체 `workspaces/templates/`를 탐색하며 pattern_id 가중치를 반영(`agents/generator/service.py`).
- Executor가 외부 DB 필요 여부를 판별해 sidecar를 조건부 기동하고 mysql readiness 프로브를 수행(`executor/runtime/docker_local.py`).
- CI가 `allow_intentional_vuln` 정책을 감지해 PACK 시 플래그를 적용(`ops/ci/run_case.sh`).
- 플러그인이 없는 취약군에서도 LLM 보조 검증기로 로그/Assertion 검증을 수행(`evals/poc_verifier/llm_assisted.py`, `evals/assertions.py`).
