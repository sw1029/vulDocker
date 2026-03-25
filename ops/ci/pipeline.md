# CI/CD 및 재현성 검증 파이프라인

Status: support
Audience: ops
Not the source of truth for: current completion priority, current rerun truth, canonical CI acceptance policy

TODO 20과 prompt.md 15장 정책 요구를 충족하기 위해 이미지 다이제스트 고정, SBOM 확인, deterministic 테스트 절차를 정의한다.
current implementation priority와 completion ordering, 잔여 작업량/turn envelope 해석은 [docs/work_tickets.md](../../docs/work_tickets.md)의 `Confirmed Completion Priority Order`, `Estimated Turn Envelope`를 우선한다.
current CI/ops boundary와 automation 해석은 [docs/code/ops.md](../../docs/code/ops.md), [docs/handbook.md](../../docs/handbook.md)를 우선한다.

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

- current completion priority order에서 이 문서는 `TKT-008-A2`, `TKT-009-*` operational CI companion으로 읽는다.
- control-plane/runtime/oracle 본체가 닫히기 전에는 이 문서가 auto-promotion이나 expansion 우선순위를 끌어올리는 source가 아님을 유지한다.
- latest positive representative pair의 ticket-form reading도 CI 문서를 measured/promotion 후행 companion으로만 두고, 본체 residual source로 읽지 않게 만든다.
- LLM-response stricter reading에서도 positive LLM-shaped lane는 Docker-enabled CI concern으로, no-Docker honesty checks와 별개로 읽는 operational companion이다.
- latest positive representative pair의 ticket-form 해석도 [docs/work_tickets.md](../../docs/work_tickets.md)의 `Assessment-To-Ticket Interpretation`을 같이 따른다.
- LLM-response 기준 상세 해석은 [docs/work_tickets.md](../../docs/work_tickets.md)의 `LLM-Response Capability Overlay`를 따른다.
- 잔여 작업량/turn envelope 해석도 [docs/work_tickets.md](../../docs/work_tickets.md)의 `Estimated Turn Envelope`를 같이 따른다.
- turn estimate shortcut도 [docs/work_tickets.md](../../docs/work_tickets.md)의 `Turn Estimate Entry`를 같이 따른다.

## 1. 파이프라인 단계
1. **Lint & Schema Check**: 문서/JSON 스키마 검증.
2. **Unit Tests**: 공통 라이브러리 테스트.
3. **Build**: Docker/MicroVM 이미지 빌드, 다이제스트 기록.
4. **SBOM 생성 & 서명**: syft + cosign.
5. **Deterministic Run**: 재현 모드(temperature=0)로 시나리오 실행, 결과 비교.
6. **Security Gates**: 이미지 스캔, 정책 검사.
7. **Publish**: Artifacts/SBOM 업로드, 메타스토어 업데이트.

## 2. 재현성 체크
- 이전 실행의 SID 선택 → 동일 입력으로 실행 → 출력 diff.
- 실패 시 파이프라인 중단.

## 3. 구현 참고
- GitHub Actions or Jenkins pipeline yaml(`ops/ci/github-actions.yml`, 추후) 참고.
- Secrets: registry credentials, cosign keys.

## 4. 정합성 체크
- [x] TODO 20 요구 반영.
- [x] docs/handbook.md(실행기/다변성)와 연계.

## How To Update This Document

- CI stage proposal이나 reproducibility pipeline companion positioning이 바뀔 때만 갱신합니다.
- current priority, current rerun truth, current acceptance verdict는 여기로 옮겨 적지 않습니다. 각각 [docs/work_tickets.md](../../docs/work_tickets.md), [docs/current_state_gap_analysis.md](../../docs/current_state_gap_analysis.md), [docs/constraints.md](../../docs/constraints.md)를 우선합니다.
- priority companion 관계나 priority reading order가 바뀌면 [docs/work_tickets.md](../../docs/work_tickets.md), [README.md](../../README.md)와 같이 맞춥니다.
- LLM-response stricter reading의 ops/CI prerequisite 해석이 바뀌면 [docs/work_tickets.md](../../docs/work_tickets.md)의 `LLM-Response Capability Overlay`와 같이 맞춥니다.
- latest positive representative pair의 ticket-form 해석이 바뀌면 [docs/work_tickets.md](../../docs/work_tickets.md)의 `Assessment-To-Ticket Interpretation`와 같이 맞춥니다.
- 잔여 작업량/turn envelope 해석이 바뀌면 [docs/work_tickets.md](../../docs/work_tickets.md)의 `Estimated Turn Envelope`와 같이 맞춥니다.
- [docs/work_tickets.md](../../docs/work_tickets.md)의 `Turn Estimate Entry`가 바뀌면 same shortcut도 같이 맞춥니다.
- canonical ops boundary나 operator entrypoint가 바뀌면 [docs/code/ops.md](../../docs/code/ops.md), [docs/handbook.md](../../docs/handbook.md)와 같이 맞춥니다.
