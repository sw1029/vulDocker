# SBOM 가이드라인

prompt.md 6장 및 `docs/architecture/metastore_and_artifacts.md` 요구를 충족하기 위해 SBOM 생성 및 관리 절차를 정의한다. 모든 작업은 `conda`의 `vul` 환경에서 수행한다.

## 1. 표준 및 도구
- 기본 형식: SPDX 2.3 (`.spdx.json`), 필요 시 CycloneDX 1.5.
- 생성 도구: `syft`, `tern`, 혹은 자체 스크립트.
- 아티팩트 경로: `artifacts/<SID>/build/sbom.spdx.json`.

## 2. 생성 시점
1. BUILD 단계 완료 후 이미지가 확정된 직후.
2. 패키지 레지스트리에 푸시할 때 재검증.

## 3. 필수 필드
- 패키지 이름/버전, 라이선스, 공급망 참고(CVE 링크), 빌드 환경 정보.
- `externalRef`로 OCI 이미지 다이제스트 연결.

## 4. 서명 및 보존
- cosign 등으로 SBOM 서명.
- 메타스토어에 `sbom_ref` 저장, 최소 90일 보존.

## 5. 정합성 체크
- [x] prompt.md SBOM 요구(SPDX/CycloneDX) 반영.
- [x] docs/architecture/metastore_and_artifacts.md의 `sbom_ref`와 일치.

## 연관 문서
- `docs/executor/security_policies.md`
- `ops/ci/pipeline.md`
- `docs/policies/usage_and_compliance.md`
