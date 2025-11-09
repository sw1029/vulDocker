# workspaces/metadata/artifacts 구조

워크스페이스
- 경로: `workspaces/<SID>/app/` (단일 취약), 다중 취약 시 `workspaces/<SID>/<bundle_subdir>/`.
- 파일: `app.py`, `Dockerfile`, `requirements.txt`, `poc.py`, 스키마/시드 스크립트 등.

메타데이터
- 경로: `metadata/<SID>/...`
- 핵심 파일: `plan.json`(PLAN), `generator_runs.json`(Generator), `researcher_report.json`(Researcher), `reviewer_reports*.json`(Reviewer), `manifest.json`(PACK).

아티팩트
- 경로: `artifacts/<SID>/build|run|reports/...`
- 핵심 파일: `build/build.log`, `build/sbom.spdx.json`, `run/run.log`, `run/summary.json`, `run/index.json`, `reports/evals.json`.

데이터 계약 요약
- 각 단계는 자신의 산출물을 표준 경로에 기록하며, 다음 단계는 이를 읽어 집계/판단.

