# 관측성 및 감사 설계

prompt.md 9장과 TODO 12 요구를 충족하기 위해 트레이싱, 로깅, 대시보드, 감사 정책을 정의한다. 모든 작업은 `conda`의 `vul` 환경에서 수행한다.

## 1. 트레이싱
- OpenTelemetry Collector 구성(`ops/observability/otel-collector.yaml`).
- TraceId/SpanId는 오케스트레이터에서 생성, 상태별 Span(`plan`, `draft.generator`, `build.executor`, `run.executor`, `verify.pipeline`, `review.reviewer`, `pack.orchestrator`).
- Exporter: OTLP → Tempo/Jaeger + 로그 연동.

## 2. 로깅
- JSON Lines 포맷, 필수 필드: `timestamp`, `level`, `trace_id`, `span_id`, `sid`, `component`, `message`.
- 보존: 30일(성공), 90일(실패/보안 이벤트).
- 로그 수집기: Fluent Bit → Loki/Elastic.

## 3. 메트릭·대시보드
- KPI: PoC 성공률, 루프/수정 횟수, 다양성 지표(H), 재현율, 자원 사용량, 보안 게이트 통과율.
- Grafana 대시보드 템플릿: `ops/observability/dashboards/`에 JSON.
- 알람 조건: PoC 성공률 < 70%, 보안 게이트 위반 > 0, 재현율 < 95%.

## 4. 감사 로그
- 에이전트 도구 호출, 외부 네트워크 접근, 이미지 스캔 결과 등 감사 이벤트를 `metadata/audit/`에 기록.
- 사용자 요청/명령 추적을 위해 CLI/API 호출 시 인증 정보 로그화(PII 최소화).

## 5. 정합성 체크
- [x] prompt.md 9장(분산 트레이싱, 로그 표준화, 보안 게이트) 반영.
- [x] docs/architecture/orchestration_and_tracing.md와 Trace/Span 규칙 일치.
- [x] docs/requirements/goal_and_outputs.md KPI와 연동.

## 연관 문서
- `ops/observability/dashboard_spec.md`
- `docs/ops/security_gates.md`
- `docs/risks/register.md`
