# RAG 스냅샷 정책

prompt.md 5장 스냅샷 요구와 TODO 8 항목을 충족한다. 모든 작업은 `conda`의 `vul` 환경에서 수행한다.

## 1. 스냅샷 정의
- 스냅샷 ID 형식: `rag-snap-YYYYMMDD-NN`.
- 구성 요소: 코퍼스 해시, 임베딩 모델 버전, 색인 파라미터, preprocessing 스크립트 해시.
- 저장 위치: `rag/index/<snapshot_id>/` (인덱스 파일 + metadata.json).

## 2. 생성 절차
1. Raw corpus 업데이트 후 정제.
2. 청킹/메타데이터 추가.
3. 임베딩 생성 → 인덱스 빌드.
4. `metadata.json`에 아래 필드 기록:
```json
{
  "snapshot_id": "rag-snap-20241106",
  "corpus_layers": ["public", "poc", "internal"],
  "corpus_hash": "sha256:abcd",
  "embedding_model": "text-embedding-3-large",
  "chunking_strategy": "code-function-1024",
  "retriever_commit": "abc123",
  "created_at": "2024-11-06T00:00:00Z"
}
```

## 3. 사용 규칙
- Researcher는 요청 시 snapshot ID를 명시하고, Packaging Metadata에 기록.
- 스냅샷 변경 시 SID 계산 요소(`corpus_snapshot`) 업데이트.
- 롤백: 문제 발생 시 이전 snapshot으로 전환하고 incident를 기록.

## 4. 정합성 체크
- [x] prompt.md 스냅샷 요구(리트리버 커밋 고정, 보고서에 snapshot ID 포함) 반영.
- [x] docs/requirements/goal_and_outputs.md, docs/architecture/metastore_and_artifacts.md에서 언급된 `retrieval_snapshot_id`와 일치.
- [x] docs/schemas/researcher_report.md 및 packaging_metadata.md에서 snapshot 필드를 사용하도록 연결.

## 연관 문서
- `docs/rag/design.md`
- `docs/architecture/metastore_and_artifacts.md`
- `docs/schemas/packaging_metadata.md`
