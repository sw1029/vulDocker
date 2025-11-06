# 구현 로드맵 (MVP → 안정화 → 고도화)

prompt.md 11장(로드맵)을 기반으로 TODO 13~15 항목을 구체화한다. 모든 작업은 `conda`의 `vul` 환경에서 수행한다.

## 1. MVP 단계
목표: 단일 LLM, 정적 RAG 샘플 1종, 로컬 실행기로 생성→검증→수정 루프 1회 완주.
- 구성 요소
  - Orchestrator 최소 상태(PLAN→PACK) + 단일 Generator/Reviewer 통합 구현.
  - RAG: `rag/corpus/processed/mvp-sample` 고정 스냅샷.
  - 실행기: Docker 기반 rootless 컨테이너.
- 필수 작업
  1. 요구 입력 파서 + SID 계산 프로토타입.
  2. PoC 검증 스크립트 템플릿 1종(SQLi).
  3. 로그/Trace 수집 최소 구성(OTEL exporter → file).
- 완료 기준
  - PoC 성공률 ≥ 1건.
  - `artifacts/<SID>/`에 이미지·SBOM·로그·리포트 저장.
  - TODO 13 항목 충족 여부 체크.

## 2. 핵심 안정화 단계
목표: Generator/Reviewer 분리, Docker 격리, DB 연동형 취약점 확대, Reflexion 기반 개선 루프.
- 구성 요소
  - Multi-agent 오케스트레이션(Researcher 옵션, Generator, Reviewer, Executor).
  - DB/서비스 조합 추가(MySQL/PostgreSQL + ORM/Raw).
  - RAG 정규 파이프라인 & snapshot 관리.
- 필수 작업
  1. 실패 케이스 수집·분석 대시보드 구성.
  2. Reflexion 메모리 저장(`rag/memories/`).
  3. SBOM 자동 생성, 보안 게이트 통합.
- 지표
  - PoC 성공률 ≥ 60%.
  - 평균 루프 수 ≤ 3.
  - 보안 위반 0.
- TODO 14 항목과 연계.

## 3. 고도화 단계
목표: Researcher + 외부 검색(ReAct) 연동, 최신 CVE 기반 자가 생성, 다변성 모드(Self-consistency) 도입.
- 구성 요소
  - 외부 검색 도구 체인, 허용 도메인 관리.
  - Variation Key 기반 다변성 제어(temperature/top-p/self-consistency).
  - 시나리오 다양성/재현성 지표 측정 자동화.
- 필수 작업
  1. 최신 CVE ingestion 파이프라인.
  2. 다변성 지표 계산 서비스(Entropy, 시나리오 거리).
  3. 재현율 리포트 자동 생성.
- 완료 기준
  - 다양성 지표 H ≥ 목표값, 재현율 ≥ 95%.
  - 최신 CVE 요구에 대해 자동 테스트베드 생성 성공 사례 확보.
- TODO 15 항목과 연계.

## 4. 정합성 체크
- [x] prompt.md 11장(MVP→핵심 안정화→고도화) 반영.
- [x] 기존 문서(agents, metastore, decoding, variability, ops)와 단계별 의존 관계 일치.
- [x] TODO 13~15 요구(루프 성공, Generator/Reviewer 분리, Researcher/다변성 도입) 구체화.

## 연관 문서
- `docs/architecture/project_structure.md`
- `docs/variability_repro/design.md`
- `ops/ci/pipeline.md`
