문서 기록 원칙

개요
- 본 프로젝트의 비-TODO 기록(설계, 결정사항, 위험·완화, 실험 결과 요약, 스냅샷 설명, 운영 정책)은 모두 `docs/` 하위에 저장한다.
- 상세 구현은 코드 리뷰와 함께 하지만, 배경과 선택 근거, 대안 비교, 파라미터 표준, 재현 절차는 문서로 남긴다.

권장 디렉토리 구조(가이드)
- docs/requirements/        : 목표, 출력 정의, 성공 기준
- docs/architecture/        : 오케스트레이션, 에이전트 계약, 메타스토어, 프로젝트 구조
- docs/schemas/             : JSON 스키마 정의 및 예시
- docs/decoding/            : 모델/디코딩 전략
- docs/rag/                 : RAG 설계, 스냅샷 정책
- docs/executor/            : 샌드박스/보안 정책, SBOM 가이드
- docs/variability_repro/   : 다변성·재현성 설계
- docs/evals/               : PoC 판정, 메타모픽 테스트 스펙
- docs/ops/                 : 관측성, 보안 게이트, CI
- docs/policies/            : 사용·컴플라이언스 정책
- docs/reporting/           : 재현 리포트 템플릿
- docs/experiments/         : 주요 실험 요약(노트북 결과 요약본)

작성 규칙
- 파일 머리말에 문서 버전, 날짜, 작성자, 관련 이슈/PR 링크를 포함한다.
- 도표·결정 근거는 인용(링크) 명시, 외부 자료의 요약은 출처 포함.
- 실험의 원자료는 `experiments/` 노트북으로, 요약과 결론은 `docs/experiments/`에 정리한다.

실험 노트북과의 연계
- 노트북은 `experiments/`에 생성하며, 시드·모델 버전·프롬프트 해시·리트리버 스냅샷 ID 등 재현 필수 정보를 맨 앞 셀에 기입한다.
- 중요 결과는 이미지(또는 표)로 추출하여 `docs/experiments/`에 요약문과 함께 첨부한다.

