# 프로젝트 구조 스캐폴딩

본 문서는 `implement_plan/prompt.md` 10장(프로젝트 구성)과 TODO 2단계 요구를 충족하도록 폴더 구조, 책임 구분, 공용 유틸 규약을 정의한다. 모든 작업은 `conda`의 `vul` 환경에서 수행한다.

## 1. 최상위 디렉토리 개요

| 경로 | 책임 | 주요 산출물/비고 |
| --- | --- | --- |
| `orchestrator/` | 상태 기계, 큐(작업/재시도), Trace hooks | 상태 전이 정의, 실행 계획, retry 정책 |
| `agents/researcher/` | 외부 자료 조사, RAG 보고서 생성(ReAct+Reflexion) | 검색 툴 어댑터, 요약기, RAG JSON 스키마 준수 |
| `agents/generator/` | 코드/Dockerfile/PoC 초안 생성 | 템플릿, 패턴 풀, self-consistency 지원 |
| `agents/reviewer/` | 코드/로그 동시 분석, 수정 지시(JSON) | 규칙 기반 체크, 보조 LLM 래퍼 |
| `executor/runtime/` | Firecracker/Kata/gVisor 실행 어댑터 | build/run/verify 스크립트, 격리 제어 |
| `executor/policies/` | seccomp, AppArmor, 네트워크 정책 | SBOM 생성 훅, 안전 게이트 |
| `rag/corpus/` | CWE/OWASP/Juliet 등 지식 데이터 | 원본 자료 + 메타 데이터 |
| `rag/index/` | 벡터/색인 스냅샷, 커밋 | snapshot metadata, retriever version |
| `rag/retriever/` | 검색기, 랭커, 쿼리 증강 | Reflexion 기반 재질문 모듈 |
| `artifacts/` | 생성된 이미지, SBOM, 로그, 트레이스 | `artifacts/<scenario_id>/...` |
| `metadata/` | Scenario ID, LHS 시드, variation key | 중앙 메타스토어, 캐시 관리 |
| `evals/` | PoC 판정 템플릿, 메타모픽 테스트 세트 | 평가 스크립트, 커버리지 리포트 |
| `ops/ci/` | 이미지 고정, 재현성 체크 파이프라인 | CI 스크립트, 정책 검사 |
| `ops/observability/` | OTEL Collector 설정, 대시보드 | Trace/Metric/Log pipeline |
| `docs/` | 설계·정책·결정 기록 (`docs/README.md` 참조) | 요구/아키텍처/정책 문서 |
| `experiments/` | 프로토타입 및 재현 노트북 | `00_repro_template.ipynb`, 결과 요약 |

## 2. 하위 디렉토리 세부 설계

### 2.1 Orchestrator
- `state_machine/`: PLAN→PACK 전이 정의, 가드 조건, 재시도/백오프 로직.
- `queue/`: 작업 큐 추상화(Kafka/Redis 등 선택 가능), idempotency 키.
- `tracing/`: OpenTelemetry 설정, TraceId/SpanId propagation.
- `cli/` (선택): 운영자 인터페이스, 시나리오 실행 트리거.

### 2.2 Agents
- 공통 유틸: `agents/common/`에 프롬프트 템플릿, 모델 래퍼, 토큰 예산 관리.
- `researcher/tools/`: 웹/문헌 검색, RAG 호출, 증거 스냅샷.
- `generator/templates/`: CWE별 패턴 템플릿, 언어/프레임워크 매트릭스.
- `reviewer/rules/`: 정적 규칙, 로그 힌트 매핑, 반자동 수정 가이드.

### 2.3 Executor
- `runtime/firecracker/`, `runtime/kata/`, `runtime/gvisor/`: 실행기별 어댑터.
- `policies/seccomp/`, `policies/apparmor/`, `policies/network/`: 보안 프로파일.
- `sbom/`: SPDX/CycloneDX 생성 스크립트, 서명 워크플로.

### 2.4 RAG
- `corpus/raw/`: 원천 자료 보관, 라이선스/출처 메타 포함.
- `corpus/processed/`: 청킹·클렌징 후 데이터.
- `index/<snapshot_id>/`: 인덱스 파일, 파라미터, 생성 로그.
- `retriever/`: 검색기 코드, rerankers, Reflexion 기반 쿼리 증강 모듈.

### 2.5 Ops & Observability
- `ops/ci/scripts/`: 빌드/테스트 파이프라인, 재현성 체크, SBOM 검증.
- `ops/observability/dashboards/`: KPI, 다양성 지표, 재현율 시각화.
- `ops/security/`: 보안 게이트, 페이로드 차단 리스트.

## 3. 공용 유틸리티 규약
- `common/logging/`: OTEL 호환 로거, 단계·에이전트·SID 태깅.
- `common/hash/`: Scenario ID 계산(`SID = H(model_ver || prompt_hash || seed || retriever_commit || corpus_snapshot || pattern_id || deps_digest || base_image_digest)`).
- `common/paths/`: 아티팩트/로그/메타데이터 경로 생성기, `artifacts/<SID>/` 규칙 강제.
- `common/config/`: 모델/툴 파라미터, variation key 정의, `conda` `vul` 환경 설정 체크.

## 4. 산출 및 정합성
- 문서 위치: `docs/architecture/project_structure.md` (본 문서).
- prompt.md의 프로젝트 구성 섹션(10장)과 동일한 책임 구성을 유지하며, 추가로 `docs/README.md`에서 정의한 기록 규칙을 반영했다.
- TODO 2단계 요구(폴더 트리 + 공용 유틸 인터페이스 정의)를 충족한다.

## 5. 향후 작업 연결
- 오케스트레이션/상태 기계 상세 설계(`docs/architecture/orchestration_and_tracing.md`) 작성 시 본 구조를 참조.
- 메타스토어/아티팩트 관리(`docs/architecture/metastore_and_artifacts.md`) 문서에서 `metadata/`와 `artifacts/` 하위 규칙을 확장.
- 실험/문서 작성 시 `docs/`, `experiments/` 규칙을 재확인하여 비-TODO 기록이 코드와 분리되도록 유지.

## 연관 문서
- `docs/requirements/goal_and_outputs.md`
- `docs/architecture/orchestration_and_tracing.md`
- `docs/architecture/metastore_and_artifacts.md`
