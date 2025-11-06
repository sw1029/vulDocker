# 재현 리포트 템플릿

TODO 21과 docs/requirements/goal_and_outputs.md 요구에 따라 재현 리포트 구조를 정의한다. 모든 작업은 `conda`의 `vul` 환경에서 수행한다.

## 1. 메타데이터
- Scenario ID (SID)
- Variation Key
- Seed / Model Version / Prompt Hash
- Retrieval Snapshot ID
- Base Image Digest / SBOM Ref
- TraceId

## 2. 환경 요약
- 언어/프레임워크/DB/OS/배포 형태
- 패턴 ID / 차원 선택 근거

## 3. 실행 결과
- 빌드/실행/검증 요약 (성공 여부, 주요 로그 링크)
- PoC 판정 결과 및 근거
- 메타모픽 테스트 결과 테이블
- 정적 분석/커버리지 요약

## 4. 다변성/재현성 지표
- 다양성 지표(H), 시나리오 거리
- 재현 테스트 결과(diff 여부)

## 5. 보안 및 SBOM
- 보안 게이트 상태
- SBOM 링크, 주요 CVE 요약

## 6. 참고 자료
- 사용된 연구/템플릿/패턴 출처
- 관련 Incident 또는 메모 링크

## 7. 서명
- Responsible engineer / Reviewer
- 작성일

## 연관 문서
- `docs/requirements/goal_and_outputs.md`
- `docs/evals/specs.md`
- `docs/architecture/metastore_and_artifacts.md`
