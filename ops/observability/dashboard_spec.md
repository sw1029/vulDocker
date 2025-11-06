# KPI 대시보드 스펙

prompt.md 13장(지표) 및 TODO 17 요구에 따라 KPI 수집 파이프라인과 대시보드 구성을 정의한다.

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
- [x] docs/ops/observability.md와 Collector/대시보드 설계 일치.

