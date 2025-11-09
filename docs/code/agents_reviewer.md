# agents/reviewer 디렉토리

핵심 파일
- agents/reviewer/main.py:1 — CLI 엔트리. ReviewerService 실행.
- agents/reviewer/service.py:1 — 실행 로그(run.log) + 정적 패턴 분석 → 이슈/블로킹 여부 판단, LLM 피드백 수집.
- orchestrator/plugins/react_loop.py:1 — 루프/스팬 기록 유틸.

데이터 계약
- 입력: `artifacts/<SID>/run/run.log` (또는 다중 취약: `run/<slug>/run.log`), run/summary.json, plan.json.
- 출력: 번들 리포트(JSON), reviewer_reports.json(인덱스), loop_state.json(루프 결과).

프로젝트 내 역할
- 평가 결과와 정적 힌트를 결합해 수정 지시를 내리고, PACK 전에 블로킹 여부를 결정.

