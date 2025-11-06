# 사용 및 컴플라이언스 정책

prompt.md 15장 운영 정책과 TODO 19를 충족하기 위해 사용 제한, SBOM 서명, 윤리 규범을 정의한다. 모든 작업은 `conda`의 `vul` 환경에서 수행한다.

## 1. 허용/비허용 사용
- 내부 샌드박스 환경에서만 취약 테스트베드 생성/실행.
- 외부 타깃 공격, 실서비스 스캔 금지.
- 3rd-party PoC 실행 금지, 반드시 자체 생성된 스크립트만 사용.

## 2. 접근 제어
- 사용자/서비스 계정 RBAC, MFA.
- 모든 명령/실험은 TraceId와 함께 감사 로그 기록.

## 3. SBOM 및 서명 정책
- 모든 이미지/아티팩트는 SBOM 생성(SPDX/CycloneDX).
- cosign 서명 필수, 메타스토어에 `sbom_ref`와 서명 증명 저장.

## 4. 데이터 보호
- 로그에서 PII 자동 마스킹.
- 외부 공유 시 재현 리포트만 제공, 내부 경로/비밀 제외.

## 5. 컴플라이언스
- 내부 보안 가이드, OSS 라이선스 준수 확인.
- 정책 위반 시 접근 제한, Incident 보고 필수.

## 6. 정합성 체크
- [x] prompt.md 15장 정책 항목 반영.
- [x] docs/executor/security_policies.md, docs/ops/security_gates.md와 일관.

## 연관 문서
- `docs/ops/security_gates.md`
- `docs/executor/security_policies.md`
- `docs/risks/register.md`
