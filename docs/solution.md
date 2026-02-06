# vulDocker 해결 전략 (MoSCoW TODO)

> 문서 목적: “룰/템플릿 기반”에 갇히지 않고 **LLM 기반으로 동적으로 취약 환경을 생성/실행/검증**하기 위한 해결 전략을 정리한다. 아키텍처(PLAN → GENERATE → EXECUTE → VERIFY → REVIEW → PACK)는 유지한다.
>
> 참고: 상세 Backlog/우선순위/검증 기준은 `docs/final_solution.md`가 단일 소스다. 이전 버전 초안은 `docs/solution_legacy.md`에 보관한다.

## 핵심 설계 원칙(요약)

- **RuleSpec/runtime 중심 계약**: 성공 조건(서명/FLAG/JSON 키), 서비스 엔트리(base_url/port), PoC 엔트리(cmd)를 “룰”이 소유하고 stage들이 이를 소비한다.
- **데이터 드리븐 우선**: CWE별 if/elif 분기보다 룰/템플릿 메타/매니페스트 스캔으로 동작을 결정한다.
- **폴백 체인 표준화**: `runtime rule` → `static rule` → `generator manifest` → `defaults` 순으로 동일한 결정 로직을 적용한다.
- **검증 가능한 산출물**: `metadata/<SID>/...`에 “결정된 계약/선택 근거/실행 요약”을 남겨 재현과 디버깅을 쉽게 한다.

## MUST (필수)

- [x] rule 미존재 CWE에서도 VERIFY가 `unsupported`로 끝나지 않게 폴백 제공(매니페스트 기반 임시 룰)
- [x] EXECUTE 단계의 base-url/port/PoC 엔트리 하드코딩 제거(룰/템플릿/매니페스트 기반 resolve)
- [x] GENERATE 단계의 `flag_token` 계약 불일치 완화(룰/런타임 없으면 강제 주입 제거)

## SHOULD (권장)

- [ ] “성공한 synthesis 결과”의 템플릿 승격(promote) 경로 추가로 커버리지 확장
- [ ] `docs/evals/rules`(정적)과 `metadata/<SID>/runtime_rules`(런타임)의 스키마/우선순위 통합 및 마이그레이션 계획 수립
- [ ] RAG 힌트/코퍼스의 CWE/스택 커버리지 확대 및 운영 정책 정립

## COULD (선택)

- [ ] LLM-assisted verifier를 안전하게 활용(정책 기반, 오프라인 스텁 시 graceful skip)
- [ ] 다중 컨테이너 스택 지원(docker compose/sidecar) 및 네트워크 정책 고도화

## WON'T (이번 범위 제외)

- [ ] 파이프라인 단계/아키텍처 대규모 개편(분산 실행/새 오케스트레이터 등)
- [ ] 외부 인터넷에 노출되는 형태의 실행/배포 자동화
