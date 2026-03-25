# KPI 대시보드 스펙

Status: support
Audience: ops
Not the source of truth for: current completion priority, current rerun truth, canonical measured gate policy

prompt.md 13장(지표) 및 TODO 17 요구에 따라 KPI 수집 파이프라인과 대시보드 구성을 정의한다.
current implementation priority와 completion ordering, 잔여 작업량/turn envelope 해석은 [docs/work_tickets.md](../../docs/work_tickets.md)의 `Confirmed Completion Priority Order`, `Estimated Turn Envelope`를 우선한다.
current ops/observability boundary 해석은 [docs/code/ops.md](../../docs/code/ops.md), [docs/handbook.md](../../docs/handbook.md)를 우선한다.

## Priority Companions

이 문서를 우선순위 판단 관점으로 읽을 때는 아래 문서를 같이 본다.

- current completion priority order: [docs/work_tickets.md](../../docs/work_tickets.md)의 `Confirmed Completion Priority Order`
- 잔여 작업량과 practical turn envelope: [docs/work_tickets.md](../../docs/work_tickets.md)의 `Estimated Turn Envelope`
- representative evidence와 함께 보는 turn estimate shortcut: [docs/work_tickets.md](../../docs/work_tickets.md)의 `Turn Estimate Entry`
- priority companion set / reading order: [docs/work_tickets.md](../../docs/work_tickets.md)의 `Priority Companions`, `Priority Reading Order`
- latest positive representative pair의 ticket-form reading: [docs/work_tickets.md](../../docs/work_tickets.md)의 `Assessment-To-Ticket Interpretation`
- LLM-response 기준 residual/priority 해석: [docs/work_tickets.md](../../docs/work_tickets.md)의 `LLM-Response Capability Overlay`
- canonical ops boundary / current truth / current non-claim: [docs/code/ops.md](../../docs/code/ops.md), [docs/current_state_gap_analysis.md](../../docs/current_state_gap_analysis.md), [docs/constraints.md](../../docs/constraints.md)

## Priority Review Focus

- current completion priority order에서 이 문서는 `TKT-008-A2` observability / measured-gate operationalization companion으로 읽는다.
- dashboard metric proposal이 current measured gate나 promotion policy의 canonical acceptance source가 아님을 유지한다.
- latest positive representative pair의 ticket-form reading도 dashboard 문서를 post-run observability companion으로만 두고, 본체 residual source로 읽지 않게 만든다.
- LLM-response stricter reading에서도 positive LLM-shaped 지표는 Docker/runtime 이후에만 의미가 있으므로, observability 문서가 roadmap 본체 우선순위를 바꾸지 않는다는 점을 유지한다.
- latest positive representative pair의 ticket-form 해석도 [docs/work_tickets.md](../../docs/work_tickets.md)의 `Assessment-To-Ticket Interpretation`을 같이 따른다.
- 잔여 작업량/turn envelope 해석도 [docs/work_tickets.md](../../docs/work_tickets.md)의 `Estimated Turn Envelope`를 같이 따른다.
- LLM-response 기준 상세 해석은 [docs/work_tickets.md](../../docs/work_tickets.md)의 `LLM-Response Capability Overlay`를 따른다.
- turn estimate shortcut도 [docs/work_tickets.md](../../docs/work_tickets.md)의 `Turn Estimate Entry`를 같이 따른다.

## 1. 지표 목록
- PoC 성공률 (성공/전체 시나리오)
- 루프 수 / 수정 횟수 (평균)
- 시나리오 다양성 지표 (샤논 엔트로피 H)
- 재현율 (% 동일 결과 재현)
- 안전도 (보안 게이트 위반 0 여부)
- 자원 사용량(CPU, 메모리)

## 2. 데이터 파이프라인
1. Orchestrator가 각 시나리오 완료 시 메타스토어에 KPI 데이터 기록.
2. Collector가 5분 주기로 `metadata/kpi/*.json`을 수집해 Prometheus pushgateway에 전송.
3. Grafana 대시보드가 Prometheus/Tempo/Loki 데이터를 통합 조회.

## 3. 대시보드 패널
- Success Rate Gauge
- Loop Count Histogram
- Diversity Trend (entropy vs time)
- Reproducibility Gauge
- Security Gate Violations table
- Resource Usage time-series

## 4. 알람
- PoC 성공률 < 70%
- 재현율 < 95%
- 보안 위반 ≥ 1
- CPU 사용률 > 80% 지속 10분

## 5. 정합성 체크
- [x] prompt.md KPI 항목 반영.
- [x] docs/handbook.md(관측성)와 Collector/대시보드 설계 일치.

## How To Update This Document

- observability metric proposal이나 dashboard companion positioning이 바뀔 때만 갱신합니다.
- current priority, current rerun truth, current acceptance verdict는 여기로 옮겨 적지 않습니다. 각각 [docs/work_tickets.md](../../docs/work_tickets.md), [docs/current_state_gap_analysis.md](../../docs/current_state_gap_analysis.md), [docs/constraints.md](../../docs/constraints.md)를 우선합니다.
- priority companion 관계나 priority reading order가 바뀌면 [docs/work_tickets.md](../../docs/work_tickets.md), [README.md](../../README.md)와 같이 맞춥니다.
- LLM-response stricter reading의 observability-side 해석이 바뀌면 [docs/work_tickets.md](../../docs/work_tickets.md)의 `LLM-Response Capability Overlay`와 같이 맞춥니다.
- latest positive representative pair의 ticket-form 해석이 바뀌면 [docs/work_tickets.md](../../docs/work_tickets.md)의 `Assessment-To-Ticket Interpretation`와 같이 맞춥니다.
- 잔여 작업량/turn envelope 해석이 바뀌면 [docs/work_tickets.md](../../docs/work_tickets.md)의 `Estimated Turn Envelope`와 같이 맞춥니다.
- [docs/work_tickets.md](../../docs/work_tickets.md)의 `Turn Estimate Entry`가 바뀌면 same shortcut도 같이 맞춥니다.
- canonical ops boundary나 operator observability entrypoint가 바뀌면 [docs/code/ops.md](../../docs/code/ops.md), [docs/handbook.md](../../docs/handbook.md)와 같이 맞춥니다.
