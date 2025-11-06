# 보안 게이트 정책

prompt.md 9장 운용·보안 요구를 토대로 보안 게이트를 정의한다. 모든 작업은 `conda`의 `vul` 환경에서 수행한다.

## 1. 게이트 목록
1. **Payload Filter**: 위험 패턴(Bash reverse shell, rm -rf 등) 차단.
2. **Network Egress Control**: 허용 도메인 외 outbound 차단.
3. **Image Scanning**: SBOM 기반 CVE 검사(Trivy 등).
4. **3rd-party PoC Ban**: 외부 PoC 스크립트를 그대로 실행하는 요청 차단.
5. **Credential Leak Check**: 로그/산출물에 민감정보 없는지 검사.

## 2. 실행 시점
- PLAN: 입력 검증, 허용되지 않은 요구 차단.
- BUILD: 이미지 스캐닝, SBOM 확인, 정책 통과 시 RUN 허용.
- RUN: 네트워크/페이로드 실시간 모니터링.
- PACK: 산출물 내 민감 정보 검사.

## 3. 위반 처리
- 즉시 실행 중단, 상태 `failed-security` 기록.
- Incident 리포트 작성(`docs/risks/register.md`와 연동 예정).
- 반복 위반 시 사용자 액세스 제한.

## 4. 정합성 체크
- [x] prompt.md 9장 보안 게이트 항목 반영.
- [x] docs/executor/security_policies.md와 연계.
- [x] docs/requirements/goal_and_outputs.md 안전 지표 요구 충족.

## 연관 문서
- `docs/policies/usage_and_compliance.md`
- `docs/risks/register.md`
- `docs/executor/security_policies.md`
