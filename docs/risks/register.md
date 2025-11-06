# 위험 등록부

prompt.md 12장 위험 및 완화 요구와 TODO 16 항목을 반영한다. 모든 작업은 `conda`의 `vul` 환경에서 수행한다.

| ID | 위험 | 영향 | 발생 가능성 | 완화 전략 | 모니터링 지표 |
| --- | --- | --- | --- | --- | --- |
| R1 | 격리 실패(MicroVM 탈출 등) | 치명적 | 낮음 | Firecracker/Kata 패치 최신 유지, seccomp/AppArmor 강화, 보안 게이트 모니터링 | 보안 이벤트 수, 패치 버전 |
| R2 | 모델 환각/오분석 | 중간 | 중간 | Reviewer에 상위 모델 사용, Reflexion 메모리, 자동 검증(Evals) | Reviewer 블로킹 비율, 실패 루프 수 |
| R3 | 출력 단조로움(다변성 부족) | 중간 | 중간 | LHS + 패턴 풀 + self-consistency, 다양성 지표 H 모니터링 | H 지표, 시나리오 거리 |
| R4 | 재현 실패 | 높음 | 낮음 | SID/Variation 관리, 결과 캐시, deterministic 모드 테스트 | 재현율 %, 캐시 hit ratio |
| R5 | 외부 네트워크 남용 | 높음 | 낮음 | 네트워크 허용 도메인 제한, 로그 감사, payload filter | 정책 위반 수 |
| R6 | SBOM 누락/공급망 위험 | 중간 | 중간 | SBOM 자동 생성, 이미지 스캔, cosign 서명 | SBOM coverage %, CVE count |
| R7 | 리소스 초과/비용 폭증 | 중간 | 중간 | cgroup 리밋, autoscaling 알람, KPI 추적 | CPU/메모리 사용률 |

## 조사/대응 절차
1. 위험 발생 시 TraceId/SID 기반 포렌식.
2. Incident 보고서를 `docs/risks/incidents/`에 작성.
3. 재발 방지 액션을 TODO에 반영.

## 정합성 체크
- [x] prompt.md 12장 위험 및 완화 항목 반영.
- [x] docs/ops/security_gates.md, docs/variability_repro/design.md 등 관련 문서와 연결.

## 연관 문서
- `docs/ops/security_gates.md`
- `docs/policies/usage_and_compliance.md`
- `docs/requirements/goal_and_outputs.md`
