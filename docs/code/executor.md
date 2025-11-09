# executor/runtime 디렉토리

핵심 파일
- executor/runtime/docker_local.py:1 — Docker build/run, 보안 옵션 적용, SBOM(Syft) 생성, 네트워크/사이드카 관리.

데이터 계약
- 입력: `workspaces/<SID>/app/` (또는 번들 서브디렉토리), plan.json(policy.executor, poc_payloads).
- 출력: `artifacts/<SID>/build/build.log`, `artifacts/<SID>/build/sbom.spdx.json`, `artifacts/<SID>/run/run.log`, `summary.json`, `run/index.json`.

동작 개요
- build_image: Dockerfile로 이미지 생성, 이미지 ID 기록, Syft가 있으면 SBOM 생성.
- run_container_with_poc: 컨테이너 실행 → readiness → `/tmp/poc.py` 실행 → 로그 수집.
- NetworkPool: `policy.executor`에 따라 네트워크 none/bridge/커스텀 네트워크 설정. sidecars 선언 시 네트워크 생성.
- readiness: TCP 포트 체크, MySQL `mysqladmin ping` 프로브 지원.

프로젝트 내 역할
- 생성된 워크스페이스를 실제로 빌드/실행하여 평가/리뷰가 참고할 증거(run.log)와 요약 지표를 남김.

