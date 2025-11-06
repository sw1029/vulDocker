# 실행기 보안 정책

prompt.md 6장과 TODO 9 요구를 충족하기 위해 실행기(Firecracker/Kata/gVisor) 보안 정책을 정의한다. 모든 작업은 `conda`의 `vul` 환경에서 수행한다.

## 1. 격리 계층
| 우선순위 | 기술 | 특징 |
| --- | --- | --- |
| 1 | Firecracker MicroVM | 최고 격리, 부팅 속도 빠름, 네이티브 KVM 필요 |
| 2 | Kata Containers | MicroVM과 OCI 호환, 약간의 오버헤드 |
| 3 | gVisor | 사용자 공간 커널, 호환성 높음, 성능 비용 |

선택 기준: 취약 코드의 커널 영향 가능성, 호환 요구, 자원 상황.

## 2. 공통 실행 정책
- rootless 컨테이너/VM 실행.
- 파일 시스템 read-only, 필요 시 tmpfs에 한정된 read-write.
- seccomp/AppArmor 프로파일 적용: `docs/executor/policies/`에 저장.
- PID/NET/IPC 네임스페이스 격리, `no_new_privs` 활성화.
- cgroups로 CPU/메모리 제한.

## 3. 네트워크 정책
- 기본 outbound 차단, 허용 도메인 whitelist (RAG, 패키지 미러 등).
- inbound 포트는 필요 시 localhost 바인딩만 허용.
- PoC 실행 시 외부 타깃 접근 금지.

## 4. 로그/포렌식
- STDOUT/STDERR, syscalls, network events를 수집하여 `artifacts/<SID>/run/`에 저장.
- 보안 이벤트는 `metadata/<SID>/security/`에 요약.

## 5. 정책 위반 대응
- 실행 중 정책 위반 발견 시 즉시 중단, 상태 `failed-security` 기록.
- Incident 리포트: 위반 유형, 컨테이너/VM ID, TraceId.

## 6. 정합성 체크
- [x] prompt.md 6장(격리, 네트워크 차단, 이미지 다이제스트) 반영.
- [x] docs/architecture/orchestration_and_tracing.md, metastore_and_artifacts.md와 연계(SID, 로그 위치).

## 연관 문서
- `docs/executor/sbom_guideline.md`
- `docs/ops/security_gates.md`
- `ops/ci/pipeline.md`
