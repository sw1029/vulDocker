# vulDocker 최종 개선 설계서 (final_solution)

본 문서는 docs/problem.md와 docs/solution.md의 타당한 개선 제안을 바탕으로, 현 코드베이스에 적용 가능한 구체적·단계적 구현 방안을 정리합니다. 각 항목은 현재 구현 대비 변경점, 구현 포인트(파일·함수 기준), 이행(마이그레이션)과 리스크를 포함합니다.

## 목표
- 규칙(YAML) 주도 검증으로 확장성 확보 (새 CWE 추가 시 코드 수정 최소화)
- PoC 성공 판정의 유연화(JSON/토큰/파일/exit code 등)
- 템플릿+LLM 결합(보강) 파이프라인 도입으로 안정성+표현력 동시 확보
- enum-like 상수/분기를 데이터 스캔 기반으로 치환

---

## 1) 규칙(YAML) 기반 일반 검증기 도입

**상태:** 구현 완료 (`evals/poc_verifier/rule_based.py`, `evals/poc_verifier/registry.py`, `common/rules/__init__.py`).

현황
- 전용 검증기만 존재: `evals/poc_verifier/mvp_sqli.py`, `evals/poc_verifier/csrf.py`
- 등록 방식: `evals/poc_verifier/main.py`에서 모듈 직접 import로 등록
- 문제: 새 CWE마다 모듈·import 추가가 필요, flag 토큰은 `'FLAG'` 부분 문자열만 확인

개선안(타당함)
- 모든 CWE에 공통 적용 가능한 “규칙 주도 검증기”를 추가해, 규칙 파일만으로 동작 가능하게 함
- success_signature 및 flag_token을 규칙에서 읽어 엄격히 일치 비교(옵션화 가능)하도록 개선
- 등록 자동화: 규칙 디렉토리 스캔으로 vuln_id를 열거해 공통 검증기를 자동 등록하거나, 미등록 vuln에 대해 rule 기반 검증으로 폴백

구현 포인트
- 신규: `evals/poc_verifier/rule_based.py`
  - `verify_with_rule(vuln_id: str, log_path: Path, *, requirement=None, run_summary=None, policy=None) -> dict`
  - 동작 순서:
    1) `common/rules.load_rule(vuln_id)`로 규칙 로드(없으면 unsupported 반환)
    2) 아티팩트에서 구조화 로그 우선 확인: `artifacts/<SID>/run/summary.json` 또는 정책에서 지정한 경로
    3) JSON 성공 판정(예: `success_key`, `flag_key`, `success_value`) → 실패 시 텍스트 기반 판정
    4) 텍스트 판정: `success_signature`와 `flag_token`(옵션) 포함 여부 검사
    5) `patterns`(file_contains/poc_contains 등) 추가 단서도 evidence에 반영(있는 경우) → 실행 로그 경로로부터 `workspaces/<SID>/<slug>/...` 디렉터리를 추론해 `app.py`, `poc.py` 등 워크스페이스 파일을 직접 스캔하고 일치 여부를 evidence로 기록
- 변경: `evals/poc_verifier/registry.py`
  - `get_verifier()` 결과가 None인 경우, `verify_with_rule`을 호출하는 폴백 경로 추가
  - 또는 초기화 시 규칙 디렉토리(예: `docs/evals/rules/*.yaml`)를 스캔하여 각 vuln_id에 대해 공통 검증기를 자동 등록
- 변경: `evals/poc_verifier/main.py`
  - 빌트인 모듈 직접 import(현행 유지 가능) + 규칙 스캔 기반 자동 등록 훅 호출

YAML 확장(선택·권장)
```yaml
# 예: docs/evals/rules/cwe-89.yaml (확장 예)
cwe: CWE-89
success_signature: SQLi SUCCESS
flag_token: FLAG-sqli-demo-token
output:
  format: auto   # auto|json|text
  json:
    success_key: success
    success_value: true
    flag_key: flag
strict_flag: true  # true면 정확히 flag_token 일치 검사, false면 FLAG 부분 문자열 허용
```

호환성/영향
- 기존 전용 검증기는 그대로 유지 가능(특화 로직 필요 시 우선 사용)
- 규칙 미존재 CWE는 기존과 동일하게 `unsupported` 또는 LLM 보조로 처리
- strict_flag 도입 시 과거 로그가 정확한 토큰을 출력하지 않으면 FAIL로 전환될 수 있음(정책으로 완화 가능)
- 패턴 스캔은 `artifacts/<SID>/run/(slug)/run.log` 구조를 기반으로 워크스페이스 경로를 추론하므로, 커스텀 디렉터리 구조에서는 evidence가 생략될 수 있음(기본 레이아웃 유지 또는 slug 정보를 제공하면 정상 동작)

---

## 2) PoC 성공 판정 유연화(JSON/텍스트/파일/exit code)

**상태:** 구현 완료 (run_summary/summary.json 우선 판정 + executor summary/인덱스에 exit_code 기록, 정책 기반 게이트 적용).

현황
- 텍스트 로그에서 `... SUCCESS` + `FLAG` 부분 문자열만 확인

개선안(타당함)
- 구조적 출력(JSON)·텍스트 출력 모두 지원하는 이중 경로
- 추가 신호(파일 생성, exit code 등)도 규칙 또는 정책으로 켜고 끌 수 있도록 확장

구현 포인트
- `evals/poc_verifier/rule_based.py` 내 판정 순서 고정:
  1) `summary.json` 존재 시 JSON 규칙으로 우선 판정
  2) 실패하거나 JSON 미존재 시 텍스트 기반 판정으로 폴백
  3) 정책 `plan.policy.verifier.require_exit_code_zero` 설정 시 run_summary/summary.json의 `exit_code`를 검사해 비정상 종료 차단
- `executor/runtime/docker_local.py`: PoC 실행 컨테이너의 exit code를 수집하여 summary/index에 반영하고, 실패 시 `ExecutorError.returncode`로 전달
- 정책 결합: `plan.policy.verifier`에 `llm_assist`, `log_excerpt_chars`, `strict_flag` 등 포함 가능(기존 LLM 보조와 동일 패턴)

호환성/영향
- JSON 결과를 출력하는 PoC는 보다 안정적으로 검증 가능
- 텍스트만 출력하는 PoC는 기존과 동일 동작(단, strict 옵션 사용 시 더 엄격해질 수 있음)
- Reviewer 연계: `agents/reviewer/service.py`가 policy.require_exit_code_zero 활성 시 `run_summary.exit_code`를 체크해 비정상 종료를 blocking 이슈로 기록.

---

## 3) Generator 가드·PoC 템플릿의 규칙 연동 강화

**상태:** 구현 완료 (`agents/generator/synthesis.py`의 success_signature/flag_token 우선순위 및 strict_flag 가드 조정).

현황
- `agents/generator/synthesis.py`가 `DEFAULT_SUCCESS_SIGNATURES`/`DEFAULT_FLAG_TOKENS`(SQLi/CSRF 중심)를 내장해 사용
- Guard가 PoC `success_signature`에 CWE별 기본 문자열 포함을 강제, 규칙 파일의 값도 일부 반영함

개선안(타당함)
- 우선순위를 “규칙 → 기본값”으로 고정하고, 규칙이 있는 CWE는 내장 상수를 의존하지 않도록 개선
- Fallback PoC 생성 시에도 규칙의 `success_signature/flag_token`을 일관되게 주입
- 규칙에 `strict_flag`가 켜진 경우, PoC 템플릿 주입 노트를 갱신해 LLM이 정확한 토큰을 출력하도록 가이드

구현 포인트
- 변경: `agents/generator/synthesis.py`
  - `_normalize_poc_template()`: 규칙 값이 존재하면 무조건 규칙 우선 사용(현행도 rule 우선이나, 기본값 경로 정리)
  - `_ensure_fallback_poc()`: Fallback PoC 내 출력 문자열을 규칙에서 직접 주입(기본값은 규칙 없을 때만 사용)
  - `_guard_manifest()`: `expected_signature` 계산 시 규칙 우선, 규칙 없을 때에만 fallback("Exploit SUCCESS"). `flag_token` 관련 제약은 규칙의 `strict_flag` 여부에 따라 가드 메시지 강화

호환성/영향
- 규칙이 있는 CWE는 가드·템플릿 모두 동일한 기준 사용 → 일관성 개선
- 기존 SQLi/CSRF 시나리오에는 동작 변화 없음(규칙이 이미 존재)

---

## 4) 템플릿 보강(LLM 결합) 훅 구현

**상태:** 2차 구현 완료 (MARKERS.md/README 보강 + `poc.py` 미존재 시 자동 scaffold 생성).

현황
- `GeneratorService._augment_workspace_if_needed()`는 플레이스홀더(로그만 남김)
- 템플릿 모드에선 템플릿을 그대로 복사, LLM 산출과의 병합/보강 없음

개선안(타당함)
- 템플릿 기반 생성 시, 규칙을 기준으로 최소한의 보강을 자동화
- 보강 항목 예: PoC `success_signature/flag_token` 출력 보장, README/PoC 사용법 주입, 요구 패키지 동기화

구현 포인트
- 변경: `agents/generator/service.py` → `_augment_workspace_if_needed()` 구현
  - 입력: `selection: TemplateSpec`, `self.requirement`, 규칙(`load_rule`)
  - 단계:
    1) 규칙 로드 후 `success_signature/flag_token/strict_flag` 확보
    2) 워크스페이스(`workspaces/<SID>/app/`) 내 `poc.py` 존재 여부 확인
       - 없으면 규칙 기반 scaffold(`urllib` 사용) 생성 → HTTP 2xx 응답 시 시그니처/토큰 출력
    3) README 보강: 규칙 기반 사용법/성공 시그니처 안내 추가
    4) 선택: 요구 패키지 파일(`requirements*.txt`)과 `deps[]` 필드 동기화(LMM guard 힌트 참고)

호환성/영향
- 템플릿 모드 결과물의 검증 안정성 향상
- 과도한 코드 변형을 피하기 위해 보강은 정책 플래그로 토글 가능(예: `requirement.augmentation.enabled`)

---

## 5) enum-like 상수/분기의 동적 구성으로 치환

**상태:** 구현 완료 (list_rules() 기반 rule coverage 추적 + verifier 메타데이터 기록).

현황
- 일부 상수(dict)로 지원 CWE/토큰/시그니처를 유지(확장 시 코드 변경 필요)
- 템플릿 발견은 이미 동적(rglob)이며, 지원 vuln 목록은 별도 enum 없음

개선안(타당함)
- 규칙 파일 스캔 결과를 통해 지원 CWE/기준을 런타임에 구성
- 내장 상수는 “규칙 미존재 시에만 사용하는 fallback”으로 축소

구현 포인트
- `common/rules/list_rules()` 유틸: 규칙 파일 열거 및 vuln_id 추출
- `evals/poc_verifier/registry.py`
  - `list_rules()` 결과를 이용해 rule coverage 여부를 추적하고, 결과 객체에 `verifier_meta`(type, rule_available) 추가
  - 룰이 존재하지 않을 때 워닝을 출력하여 모니터링 신호 확보
- `agents/generator/synthesis.py`
  - `DEFAULT_*` 상수는 규칙 부재시에만 사용, 규칙 존재 시 우선

호환성/영향
- 새 규칙 파일 추가만으로 지원 CWE가 자동 반영
- 과거 상수 의존 경로는 규칙 부재시에만 사용되어 안전한 축소

---

## 6) RAG/LLM 기반 규칙·템플릿 자동화

**상태:** 구현 완료 (Researcher가 runtime 규칙/템플릿을 생성하고, Generator·Verifier가 자동으로 소비하며 `researcher_report.json`에 후보 메타데이터를 함께 기록).

현황
- RAG/Researcher 단계는 취약점 힌트를 수집하지만, 규칙(YAML)이나 템플릿 메타데이터는 여전히 사람이 미리 정의해야 함.
- 규칙 추가 속도가 느려 Phase 3(규칙 우선 구조 전환)을 적용하기 어려운 상태.

개선안(타당함)
- Researcher 산출물에 `candidate_rules[]`, `candidate_templates[]` 섹션을 추가하여, RAG 결과에서 검증 포인트·파일 구조를 추출.
- 별도 “Rule Synthesizer” LLM 호출을 통해 YAML/JSON 스키마(성공 시그니처, FLAG, 패턴, 템플릿 메타)를 자동 생성.
- Generator/Verifier는 해당 후보를 우선 적용하고, 실패 시 루프 컨트롤러가 실패 맥락을 LLM에 되돌려 보정.

구현 포인트
- Researcher(`agents/researcher/service.py`): RAG 결과를 기반으로 `candidate_rules[]`/`candidate_templates[]`를 생성하고 `metadata/<SID>/runtime_rules/*.yaml`, `metadata/<SID>/runtime_templates/*`에 저장하며, 동일 내용을 `researcher_report.json`의 `candidate_rules[]`/`candidate_templates[]` 필드로 노출(성공 시그니처·flag 토큰·템플릿 ID 요약 포함).
- Runtime 규칙 검색: `common/rules/load_rule`이 `VULD_RUNTIME_RULE_DIRS` 환경변수를 통해 동적 디렉터리를 스캔하도록 확장, `list_rules()`도 동일.
- TemplateRegistry: `agents/generator/service.TemplateRegistry`가 runtime 템플릿 루트를 추가로 탐색하여 폴백 시 우선 사용.
- Env 등록: Generator/Verifier/Reviewer가 metadata의 runtime rule 디렉터리를 `VULD_RUNTIME_RULE_DIRS`에 자동 추가하여 동일 SID 내에서 공유.
- Failure Feedback: `evals/poc_verifier/main.py`가 검증 실패 시 `rag.memories`에 Reflexion 기록을 남겨, 향후 Generator LLM 프롬프트에 "Signature missing" 등 구체적인 실패 맥락이 포함되도록 함.
- Fallback: generator 로그에 runtime 템플릿 materialize, rule absence 시 자동 적용.

호환성/영향
- 규칙/템플릿 수동 관리 부담을 줄이고, 신규 CWE 입력시 자동 확장 경로를 확보.
- LLM이 생성한 규칙을 바로 적용하므로, 안전장치(스키마 검증, optional human review)가 필요.
- 성공 여부를 telemetry에 남겨 Phase 3 적용 시점을 데이터 기반으로 판단 가능.
- 현재 후보 규칙/템플릿은 deterministic 시드 기반 제너레이터/휴리스틱으로 생성되므로, 별도 “Rule Synthesizer” LLM 검증 파이프라인은 추후 강화 과제로 남음(보고서에는 실제 생성 결과가 그대로 포함됨).

---

## 7) 테스트/검증 계획(요지)

**상태:** 단위 테스트 + 1차 통합 E2E 케이스 구현 완료 (`evals/poc_verifier/tests/test_rule_based.py`, `tests/test_runtime_rules.py`, `tests/e2e/run_case.py`, `tests/e2e/test_cases.py`, `ops/ci/run_e2e_tests.sh`). 추가 CWE 케이스 확대와 병렬 실행 튜닝은 추후 작업으로 남겨둠.
- 단위 테스트
  - `evals/poc_verifier/tests/test_rule_based.py`: JSON/exit-code/텍스트 시나리오 검증
  - `tests/test_runtime_rules.py`: runtime rule 디렉터리에서 동적으로 규칙을 읽어오는 경로 검증
- 통합 E2E 케이스(초기)
  - `tests/e2e/cases/cwe-89-basic`: `base_requirement.yml`을 단일 SQLi 번들로 축소하고, 기대 evidence/리뷰어 결과를 `expectations.json`에 선언
  - `tests/e2e/run_case.py`: 요구 블루프린트를 머지 → SID 계획 → 파이프라인 실행 → `metadata/<sid>`·`artifacts/<sid>` 스냅샷 → 기대치 검증까지 자동화. `--no-snapshot`/환경변수로 Docker 가용성 확인 및 대형 복사 제어.
  - `tests/e2e/README.md`: 케이스 작성 지침과 실행 방법 정리
- Pytest/CI 연동
  - `tests/e2e/test_cases.py`는 `VULD_RUN_E2E=1` + Docker 사용 가능 시에만 실제 파이프라인을 구동하고, 그렇지 않으면 자동 skip하여 기본 테스트 속도를 유지
  - `ops/ci/run_e2e_tests.sh`: 케이스 스키마(필수 파일 존재) 검증 후 `pytest -m e2e` 트리거. CI에서 `VULD_RUN_E2E`를 켜면 통합 회귀 테스트를 선택적으로 포함 가능
- 향후 확대 방향
  - 추가 CWE/CVE 케이스를 `tests/e2e/cases/<slug>/`로 증설해 다중 취약, 템플릿 폴백, 룰 미존재 시나리오 등을 포괄
  - 케이스 정의에 runtime rule/template 번들(`runtime_assets`)을 추가해 Researcher 산출물 시나리오를 재현
  - 실행 시간 단축을 위해 Docker 이미지 캐시 공유 및 병렬 케이스 실행(리소스 여건에 맞춰 batch 처리) 적용

---

## 8) 마이그레이션/롤아웃

**상태:** Phase 1 완료 + Phase 2(telemetry) 적용 + Phase 3 일부(정책 기반 strict_flag 기본값 상향, rule-first 옵션). 남은 Phase 3 항목은 룰 확대 시점에 맞춰 진행.
- Phase 1(비파괴): 공통 검증기 도입 + 규칙 스캔 등록(기존 전용 검증기 유지)
- Phase 2(정렬): Generator 가드/템플릿 보강에서 규칙 우선 경로 활성화(경고 로그로 모니터링)
- Phase 3(옵트인 강화):
  - `policy.verifier.strict_flag_default` → 룰에 strict_flag가 없을 때도 엄격 비교
  - `policy.verifier.prefer_rule` → 전용 검증기 호출 전 rule 기반 검증을 우선
  - 전용 검증기 축소 및 기타 항목은 룰 확대 시점에 맞춰 추가 적용

---

## 9) 요약: 현재 대비 주요 차이
- 검증 기준이 코드 하드코딩 → 규칙(YAML) 우선으로 전환
- PoC 성공 판정이 텍스트 고정 → JSON/텍스트/파일/exit code 혼합 판정 지원
- 템플릿 결과가 그대로 사용 → 규칙에 맞춘 자동 보강(옵션) 적용
- 상수 중심 확장 → 규칙/폴더 스캔 중심의 동적 확장
- 실패 피드백 → Generator/Verifier가 시그니처 누락 등 구체적인 실패 맥락을 LLM 프롬프트에 삽입하여 재시도 시 자동 보정

적용 시, SQLi/CSRF의 기존 동작은 유지하면서, 신규 CWE는 “규칙 파일만 추가”로 검증·가드·템플릿 보강까지 연계되는 경로를 확보합니다.
