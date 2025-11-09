# agents/researcher 디렉토리

핵심 파일
- agents/researcher/main.py:1 — CLI 엔트리. 번들 반복 실행, 인덱스(researcher_reports.json) 기록.
- agents/researcher/service.py:1 — 검색/로컬 RAG/프롬프트 조립 → researcher_report.json 생성.
- rag/tools/web_search.py:1 — 원격 검색(있으면) 우선, 실패 시 로컬 코퍼스 검색으로 폴백.

데이터 계약
- 입력: `metadata/<SID>/plan.json` (requirement/variation_key).
- 출력: `metadata/<SID>/researcher_report.json` (또는 번들 범위 파일).
- report(요약): vuln_id, intent, preconditions, tech_stack_candidates, minimal_repro_steps, references, pocs, deps, risks, retrieval_snapshot_id.

프로젝트 내 역할
- Generator가 선택/합성 결정을 더 명료하게 내리도록 외부/내부 근거를 정리한 보고서를 제공.

