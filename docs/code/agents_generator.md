# agents/generator 디렉토리

핵심 파일
- agents/generator/main.py:1 — 번들 슬러그별 실행 진입점, 결과 인덱스(generator_runs.json) 작성.
- agents/generator/service.py:1 — 템플릿 탐색/가용성 판정(태그/DB), hybrid 모드(합성 우선 + 템플릿 보강), LLM 호출.
- agents/generator/synthesis.py:1 — manifest(JSON) 기반 합성: 파일/의존성/경로 제약, 결정적 폴백.

데이터 계약
- 입력: `metadata/<SID>/plan.json` (requirement/variation_key/policy/run_matrix).
- 출력: `workspaces/<SID>/app/` (단일 취약) 또는 서브디렉토리 구조(다중 취약), `metadata/<SID>/generator_runs.json`.
- manifest 스키마(요약): intent, pattern_tags[], files[], deps[], build, run, poc{cmd,success_signature}, notes, metadata.

프로젝트 내 역할
- 요구+RAG 신호를 바탕으로 취약 환경을 “합성/보강”하여 실행 가능한 워크스페이스를 생성.

주요 상호작용
- common/prompts: 합성 프롬프트와 가드레일 지시 사용.
- rag/memories: 실패 맥락을 프롬프트에 주입 가능.
- executor: Dockerfile/app/poc가 실행기에 의해 빌드/실행됨.

