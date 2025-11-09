# 에이전트 역할 및 계약서

본 문서는 `implement_plan/prompt.md` 2장(에이전트 + 실행기) 요구를 토대로 Researcher, Generator, Reviewer, Executor 각 역할의 입력/출력 계약과 도구 사용 범위를 정의한다. 모든 작업은 `conda`의 `vul` 환경에서 수행한다.

## 공통 원칙
- 모든 에이전트 호출은 TraceId, SID, Variation Key를 포함한 컨텍스트를 전달한다.
- 산출물은 JSON 스키마를 준수하며 `docs/schemas/` 문서와 동기화한다.
- 실패 시 Root Cause 메모리(Reflexion) 업데이트를 추적한다.

## 1. Researcher
- **목표**: 외부 지식 검색, 요약, RAG 리포트 제공(ReAct + Reflexion 패턴).
- **입력**:
  - 요구 정의(취약점 ID, 패턴 힌트, 환경 제약).
  - 현재 실패 로그(선택) → 쿼리 증강.
  - Retrieval snapshot ID, 모델 버전(재현용).
- **출력 활용 규칙**: Researcher 보고서의 `preconditions`, `tech_stack_candidates`, `deps`는 Generator 단계에서 템플릿/LLM 선택 점수에 가산되어 자연어 요구와 검색 결과가 실제 코드 스택 선정에 직접 영향을 준다.
- **출력 JSON 스키마** (`docs/schemas/researcher_report.md` 예정):
```
{
  "vuln_id": "CWE-89",
  "intent": "SQLi 테스트베드",
  "preconditions": ["MySQL 5.7", "PHP"],
  "tech_stack_candidates": [ ... ],
  "minimal_repro_steps": [ ... ],
  "references": [ {"title": "...", "url": "..."} ],
  "pocs": [ {"desc": "...", "link": "..."} ],
  "deps": ["mysqlclient>=2.1"],
  "risks": ["DoS 가능성"],
  "retrieval_snapshot_id": "rag-snap-20241106"
}
```
- 다중 취약 모드(`requirement.multi_vuln: true` 또는 PLAN `features.multi_vuln`)에서는 `requirement.vuln_ids[]` 순서대로 보고서를 작성하고, 각 보고서는 해당 `vuln_id`를 명시해야 한다.
- **도구 사용**: 검색 API, 사내 문헌, 코드 저장소. 외부 호출 시 안전 정책 준수(네트워크 허용 도메인 목록).

## 2. Generator
- **목표**: 소스 코드, Dockerfile, 설정, PoC 초안 생성.
- **입력**:
  - Researcher 보고서.
  - Scenario 차원 파라미터(언어/프레임워크/DB 등).
  - 패턴/템플릿 ID, Variation Key.
  - `poc_payloads[]` 등 메타모픽 PoC 입력.
- **출력**:
  - 파일 번들(코드, Dockerfile, 스크립트) + 메타JSON (`generated_artifacts.json`).
  - PoC 스크립트 초안.
  - 빌드/실행에 필요한 dependency manifest.
- **검증**:
  - self-consistency k 샘플 중 다수결 선택 결과 기록.
  - Reviewer에 전달할 근거(중요 결정, 가정 등) 포함.

## 3. Reviewer
- **목표**: 코드와 실행 로그를 분석하여 문제를 식별하고 수정 지시 생성.
- **입력**:
  - Generator 산출물.
  - Executor의 build/run/verify 로그.
- **출력 JSON 스키마** (`docs/schemas/reviewer_report.md` 예정):
```
{
  "file": "app/routes.py",
  "line": 120,
  "issue": "Unsanitized SQL query",
  "fix_hint": "Use parameterized query",
  "test_change": "Add SQLi payload case",
  "severity": "high",
  "evidence_log_ids": ["run-log-20241106-001"]
}
```
- **정책**:
  - 치명적 이슈(예: 빌드 실패, 보안 위반)는 즉시 LOOP 트리거.
  - Reviewer는 상위 성능 모델(품질 모드) 사용 권장.
  - PoC 판정은 `evals.poc_verifier.registry`에 등록된 취약점별 검증기를 호출해 수행하며, 미등록 취약점은 blocking 이슈로 보고한다.

## 4. Executor
- **목표**: 빌드, 실행, PoC 검증 및 자원 측정.
- **입력**:
  - Generator 산출물 + 컨테이너/VM 설정.
  - Policy 프로파일(seccomp, AppArmor, network).
- **출력 JSON 스키마** (`docs/schemas/executor_result.md` 예정):
```
{
  "build_log": "...",
  "run_log": "...",
  "verify_pass": true,
  "traces": ["trace-..."],
  "coverage": {"line": 0.85},
  "resource_usage": {"cpu": "500m", "memory": "1Gi"}
}
```
- **제약**:
  - rootless 실행, read-only FS, no-privilege.
  - 네트워크 기본 차단(허용 목록 외 불가).
  - PoC 실행 후 로그/트레이스/아티팩트 경로를 보고.

## 5. 상호작용 시퀀스 요약
1. PLAN 단계에서 Scenario ID, Variation Key 결정.
2. Researcher가 외부 자료를 수집, RAG 보고서를 제공.
3. Generator가 보고서 + 시나리오 파라미터로 산출물 초안을 생성.
4. Executor가 빌드/실행/검증을 수행하고 결과를 반환.
5. Reviewer가 결과를 검토하여 통과/수정 지시.
6. 필요 시 DRAFT 단계로 루프하여 반복.

## 6. 정합성 체크리스트
- [x] prompt.md 2.1 섹션(Researcher/Generator/Reviewer/Executor 역할) 반영.
- [x] TODO 4단계 항목(역할·계약, ReAct/Reflexion, 로그·코드 동시 분석, 격리 실행) 충족.
- [x] `docs/architecture/project_structure.md`의 `agents/` 디렉토리 정의와 정합.
- [x] `docs/requirements/goal_and_outputs.md`에서 정의한 출력물(보고서, 메타데이터)과 일치.

## 연관 문서
- `docs/schemas/researcher_report.md`
- `docs/schemas/reviewer_report.md`
- `docs/schemas/executor_result.md`
