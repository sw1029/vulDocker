# 자동 검증 및 평가 스펙

prompt.md 8장과 TODO 11 항목을 충족하기 위해 PoC 판정, 메타모픽 테스트, 정적 분석, 커버리지 측정을 정의한다. 모든 작업은 `conda`의 `vul` 환경에서 수행한다.

## 1. PoC 판정
- **명세**: 취약 동작의 기대 결과(예: SQLi면 FLAG 유출, CSRF면 토큰 없이 상태 변경)를 코드로 명시.
- **플러그인 구조**: `evals/poc_verifier/registry.py`에 vuln_id별 검증기를 등록하고, `evals/poc_verifier/main.py` CLI 및 Reviewer가 동일 플러그인을 호출한다.
- **LLM 보조 검증**: 플러그인이 없거나 실패할 때는 `requirement.policy.verifier.llm_assist=true`인 경우 LLM이 JSON 스키마(판단/근거/assertion program)를 생성하고, `evals/assertions.py`가 로컬에서 이를 검증하여 최종 pass/fail을 결정한다.
- **메타모픽 입력**: `requirement.poc_payloads[]`가 지정되면 Executor가 동일 컨테이너에서 payload를 순차 실행하고, 검증기는 모든 payload 결과를 통합 평가한다.
- **출력**: pass/fail, 근거 로그 ID, 검증 시간, status(`evaluated|skipped|unsupported`).

## 2. 메타모픽 테스트
- 테스트 템플릿: CWE별 변형 규칙 집합.
  - SQLi: 공백/주석/대소문 변형, 인코딩 변화.
  - XSS: HTML 엔티티, 이벤트 핸들러 변형.
- 실행 흐름: 기본 PoC 성공 후 변형 입력을 순차 적용, 동일 취약성이 재현되는지 확인.

## 3. 정적 분석
- 단순 룰 세트: 하드코딩 크리덴셜, 위험 API 호출, eval 사용 등.
- 도구: Semgrep/CodeQL 등 플러그형 분석기. 결과는 Reviewer에 제공.

## 4. 커버리지 측정
- 언어별 도구(pytest-cov, gcov, nyc 등) 통합.
- 최소 기준: 취약 경로(해당 파일/함수) line coverage > X%(기본 70).
- Executor 결과 스키마의 `coverage` 필드에 기록.

## 5. 리포트 통합
- 모든 평가 결과는 `artifacts/<SID>/reports/evals.json`에 저장.
- 재현 리포트 템플릿(`docs/reporting/reproducibility_report_template.md`, 추후)과 연동.

## 6. 정합성 체크
- [x] prompt.md 8장( PoC, 메타모픽, 정적 분석, 커버리지 ) 반영.
- [x] docs/schemas/executor_result.md coverage 필드와 일치.
- [x] docs/architecture/agents_contracts.md Reviewer 계약에서 언급한 증거 로그와 연동.

## 연관 문서
- `docs/variability_repro/design.md`
- `docs/reporting/reproducibility_report_template.md`
- `docs/ops/observability.md`
