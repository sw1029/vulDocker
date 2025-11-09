# common 디렉토리

구성 요소
- common/paths.py:1 — 저장소 경로 규칙(get_metadata_dir/get_workspace_dir/get_artifacts_dir).
- common/sid.py:1 — SID 필드 해시(`compute_sid`).
- common/plan.py:1 — `metadata/<SID>/plan.json` 로더.
- common/run_matrix.py:1 — 단일/다중 취약 번들, 디렉토리(shard) 경로 헬퍼.
- common/config/api_keys.py:1 — `config/api_keys.ini`에서 OpenAI 키 로드.
- common/config/decoding.py:1 — LLM 디코딩 파라미터 프로파일.
- common/llm/provider.py:1 — litellm 백엔드/스텁 자동 전환(키/패키지 없을 때 스텁).
- common/prompts/templates.py:1 — Researcher/Generator/Reviewer 프롬프트 빌더.
- common/variability/manager.py:1 — Variation Key 정규화/프로파일 선택.

데이터 계약
- plan.json: PLAN 산출물. 모든 모듈이 참조.
- generator_runs.json / reviewer_reports.json / run/index.json: 단계별 인덱스 파일을 읽어 집계 또는 다음 단계에 전달.

프로젝트 내 역할
- 파이프라인 전반의 경로/식별자/디코딩/키/LLM/프롬프트 표준을 제공하는 기반 유틸 묶음.

