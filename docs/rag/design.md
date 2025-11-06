# RAG 설계

prompt.md 5장과 TODO 8 요구를 충족하기 위해 RAG 파이프라인, 코퍼스 층위, 청킹 전략, Reflexion 기반 개선 루프를 정의한다. 모든 작업은 `conda`의 `vul` 환경에서 수행한다.

## 1. 코퍼스 층위
1. **공용 지식층**: CWE, OWASP, Juliet, 논문/블로그(라이선스 확인).
2. **최신 PoC 층**: CVE 링크, exploit 블로그, GitHub PoC(허용 범위 내).
3. **사내 지식층**: 누적된 실행 로그, 실패 사례, 패턴 메모.

각 층은 `rag/corpus/raw/<layer>/`에 저장하고, 전처리 후 `rag/corpus/processed/<snapshot_id>/`에 배치.

## 2. 전처리/청킹 전략
- 문서 유형별 청킹 길이: 함수/클래스 단위(코드), 256~512 토큰(서술형).
- 메타데이터: `vuln_id`, `framework`, `db`, `pattern_tag`, `source_url`.
- 민감 정보 필터링: 사내 데이터는 자동 마스킹.

## 3. 색인 및 검색
- 벡터 인덱스 + 키워드 인덱스 하이브리드.
- 임베딩 모델: Code 전용(예: text-embedding-3-large) + 일반 자연어.
- 검색 전략: top-k + reranker; Researcher는 ReAct 방식으로 검색→검증 루프.

## 4. Reflexion 기반 개선
- 실패 로그나 Reviewer 지시를 `failure_context`로 RAG 입력에 추가.
- 반복 시 Retrieval 쿼리 확장, snapshot 변경 없이 메모리만 추가.
- 실패 패턴 저장소(`rag/memories/`) 유지.

## 5. 안전/품질 가이드
- 라이선스/출처 기록 필수(`source_url`, `license`).
- 최신 PoC 수집 시 네트워크 허용 도메인만 접근.
- 민감 자료는 `docs/policies/usage_and_compliance.md` 기준 준수.

## 6. 정합성 체크
- [x] prompt.md RAG 설계(코퍼스 층위, 청킹, 스냅샷) 반영.
- [x] docs/architecture/agents_contracts.md Researcher 입력 요구와 일치.
- [x] docs/schemas/researcher_report.md의 필드와 연결.

## 연관 문서
- `docs/rag/snapshots.md`
- `docs/rag/corpus_guide.md`
- `docs/variability_repro/design.md`
