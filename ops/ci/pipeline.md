# CI/CD 및 재현성 검증 파이프라인

TODO 20과 prompt.md 15장 정책 요구를 충족하기 위해 이미지 다이제스트 고정, SBOM 확인, deterministic 테스트 절차를 정의한다.

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
