# rag 디렉토리

핵심 파일
- rag/memories/__init__.py:1 — Reflexion 메모리(JSONL) 저장/조회, 실패 맥락 요약 제공.
- rag/tools/web_search.py:1 — 원격/로컬 검색 어댑터. Researcher가 사용.

데이터 계약
- 입력: 실패 기록(generator_failures.jsonl), 메모리 스토어(rag/memories/reflexion_store.jsonl).
- 출력: 최근 실패 맥락(프롬프트 삽입용 문자열).

프로젝트 내 역할
- 실패 사례를 학습 컨텍스트로 재활용하여 다음 합성/리뷰 루프의 수렴을 돕는 메모리 계층.

