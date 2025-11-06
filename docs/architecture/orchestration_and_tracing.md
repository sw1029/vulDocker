# 오케스트레이션 및 트레이싱 설계

본 문서는 `implement_plan/prompt.md` 2장(오케스트레이션)과 TODO 3단계 요구를 충족하기 위한 상태 기계, 재시도 전략, OTEL 트레이싱 규약을 정의한다. 모든 작업은 `conda`의 `vul` 환경에서 수행한다.

## 1. 상태 기계 개요
- 기본 파이프라인: `PLAN → DRAFT → BUILD → RUN → VERIFY → REVIEW → PACK` (+ 필요 시 LOOP로 DRAFT 복귀).
- 각 단계는 멱등성을 보장하며 Scenario ID(SID)와 TraceId를 통해 추적된다.
- 상태 전이 정의는 `orchestrator/state_machine/` 모듈에 JSON/DSL 형식으로 저장한다.

### 1.1 상태 설명
| 상태 | 책임 | 주요 산출물 |
| --- | --- | --- |
| PLAN | 요구/시나리오 파싱, 차원 테이블 매핑, LHS 샘플링 | 실행 계획, variation key |
| DRAFT | Generator가 초기 코드/Dockerfile/PoC 초안 생성 | 초안 아티팩트, 로그 |
| BUILD | Executor runtime에서 이미지/환경 빌드, SBOM 생성 | 빌드 로그, 이미지 digest |
| RUN | PoC 실행, 메타모픽 입력 적용 | run 로그, metrics |
| VERIFY | 자동 판정 + 정적 분석 + 커버리지 측정 | 판정 결과, coverage report |
| REVIEW | Reviewer가 실패 원인·수정 지시 생성 | bug report JSON |
| PACK | 패키징, 메타데이터 정리, 캐시 업데이트 | artifacts/<SID>/, metadata entries |

### 1.2 전이 조건
- PLAN→DRAFT: 입력 검증 통과, 자원 할당 확정.
- DRAFT→BUILD: 초안 생성 성공, 리뷰에서 치명적 오류 없음.
- BUILD→RUN: 이미지 빌드 및 SBOM 성공, 보안 게이트 PASS.
- RUN→VERIFY: PoC 실행 로그 수집 완료.
- VERIFY→REVIEW: 판정 실패 또는 오류 발생 시.
- REVIEW→DRAFT: 수정 필요 시 loop counter 증가, 최대 N회(기본 3) 후 실패로 종료.
- VERIFY→PACK: 모든 검증 통과.
- PACK→DONE: artifacts/metadata 저장 및 캐시 등록 성공.

## 2. 재시도 및 중단 기준
- **백오프 전략**: 지수 백오프 + Jitter, 단계별 최대 시도 수 설정(예: BUILD 2회, RUN 3회).
- **중단 기준**:
  - LOOP 횟수 초과.
  - 보안 게이트 위반(external network, payload blacklist) 발생.
  - 자원 한도 초과(CPU/RAM/디스크) 시 즉시 중단.
- 실패 시 포렌식: TraceId/SpanId, 상태, 입력 파라미터, 로그 경로를 `metadata/failures/`에 기록.

## 3. 트레이싱 및 로그 규약
- **OpenTelemetry + W3C Trace Context** 사용.
- 각 상태는 고유 Span으로 기록, Span attribute에는 `sid`, `state`, `agent`, `attempt`, `variation_key` 포함.
- 오케스트레이터는 TraceId를 생성하고 모든 에이전트/실행기에 전파한다.
- 로그 포맷: JSON Lines, 필수 필드 `timestamp`, `level`, `trace_id`, `span_id`, `sid`, `component`.

### 3.1 OTEL 네이밍 예시
- Trace name: `scenario/<SID>`
- Span names: `plan`, `draft.generator`, `build.executor`, `run.executor`, `verify.pipeline`, `review.reviewer`, `pack.orchestrator`.

### 3.2 트레이스 수집 파이프라인
- 에이전트/실행기에서 OTLP exporter로 Collector 전송.
- Collector는 `ops/observability/otel-collector.yaml`에 구성, 백엔드(Tempo/Jaeger 등)로 내보냄.
- Trace 보존 정책: 최소 30일, 실패 Trace는 별도 태그 `status=failure` 지정.

## 4. 메타스토어 연동
- 각 상태 완료 시 `metadata/`에 단계별 기록(시간, 해시, 로그 위치) 저장.
- TraceId는 Scenario ID와 함께 메타스토어에 기록하여 재현 리포트에 포함.
- 결과 캐시: `sid` 기준으로 `PACK` 단계 산출물을 아토믹하게 저장, 중복 실행 시 캐시 조회 후 스킵.

## 5. 정합성 체크리스트
- [x] prompt.md 2장(정해진 상태 기계, 중앙 메타스토어, OTEL 트레이싱) 요구 반영.
- [x] TODO 3단계 항목(상태 전이, 재시도/중단 기준, OTEL 규약) 충족.
- [x] `docs/architecture/project_structure.md`의 `orchestrator`/`ops/observability` 구조와 연결됨.
- [x] `docs/README.md`의 기록 원칙 및 `conda vul` 환경 명시 준수.

## 연관 문서
- `docs/architecture/project_structure.md`
- `docs/architecture/metastore_and_artifacts.md`
- `docs/ops/observability.md`
