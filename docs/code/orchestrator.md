# orchestrator 디렉토리

핵심 파일
- orchestrator/plan.py:1 — 요구 입력 정규화 → SID 계산 → `metadata/<SID>/plan.json` 작성. 경로 생성(`workspaces/`, `artifacts/`, `metadata/`).
- orchestrator/pack.py:1 — 실행 산출물 취합/스냅샷/`manifest.json` 생성. REVIEW 게이트 정책(`--allow-intentional-vuln`) 반영.

데이터 계약
- 입력: `inputs/*.yml` (요구 스펙). 필수/선택 필드는 `plan.build_plan()`에서 정규화.
- 출력(PLAN): `metadata/<SID>/plan.json` (paths/variation_key/policy/run_matrix 등 포함).
- 출력(PACK): `metadata/<SID>/manifest.json`, `artifacts/<SID>/build/source_snapshot/`.

프로젝트 내 역할
- 파이프라인의 시작/끝 단계 담당. 이후 단계(agents/executor/evals/reviewer)가 참조할 경로/정책/변이키를 결정.

주요 의존
- common.scripts: `common/sid.py:1`, `common/paths.py:1`, `common/plan.py:1`, `common/run_matrix.py:1`.
- 리뷰 게이트: `metadata/<SID>/loop_state.json`을 기준으로 차단/통과 여부 판정.

