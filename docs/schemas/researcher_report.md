# Researcher RAG 보고서 스키마

본 스키마는 Researcher 에이전트가 생성하는 RAG 보고서를 정의한다. prompt.md 3.1 및 docs/architecture/agents_contracts.md 요구와 정합성을 유지하며, 모든 작업은 `conda`의 `vul` 환경에서 수행한다.

## JSON Schema (요약)
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ResearcherReport",
  "type": "object",
  "required": [
    "vuln_id",
    "intent",
    "preconditions",
    "tech_stack_candidates",
    "minimal_repro_steps",
    "references",
    "pocs",
    "deps",
    "risks",
    "retrieval_snapshot_id"
  ],
  "properties": {
    "sid": {"type": "string", "description": "Scenario ID"},
    "trace_id": {"type": "string"},
    "vuln_id": {"type": "string"},
    "intent": {"type": "string"},
    "preconditions": {"type": "array", "items": {"type": "string"}},
    "tech_stack_candidates": {"type": "array", "items": {"type": "string"}},
    "minimal_repro_steps": {"type": "array", "items": {"type": "string"}},
    "references": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["title", "url"],
        "properties": {
          "title": {"type": "string"},
          "url": {"type": "string", "format": "uri"},
          "notes": {"type": "string"}
        }
      }
    },
    "pocs": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["desc"],
        "properties": {
          "desc": {"type": "string"},
          "link": {"type": "string", "format": "uri"}
        }
      }
    },
    "deps": {"type": "array", "items": {"type": "string"}},
    "risks": {"type": "array", "items": {"type": "string"}},
    "retrieval_snapshot_id": {"type": "string"},
    "failure_context": {"type": "string", "description": "Reflexion 메모"}
  }
}
```

## 예시
```json
{
  "sid": "sid-1234",
  "trace_id": "trace-abc",
  "vuln_id": "CWE-89",
  "intent": "SQLi 취약 테스트베드 생성",
  "preconditions": ["MySQL 5.7", "Ubuntu 22.04"],
  "tech_stack_candidates": ["Python Flask", "PHP Laravel"],
  "minimal_repro_steps": ["DB 초기화", "취약 엔드포인트 배포"],
  "references": [{"title": "SQLi Survey", "url": "https://example.com"}],
  "pocs": [{"desc": "UNION 기반 공격", "link": "https://poc.example"}],
  "deps": ["mysqlclient>=2.1"],
  "risks": ["데이터 파괴 위험"],
  "retrieval_snapshot_id": "rag-snap-20241106",
  "failure_context": "이전 시도에서 MySQL 버전 미일치"
}
```

## 정합성 체크
- prompt.md 3.1 스키마 요구 반영.
- docs/architecture/agents_contracts.md에서 정의한 Researcher 계약과 일치.
- Trace/SID 포함으로 docs/architecture/orchestration_and_tracing.md와 연동.

## 연관 문서
- `docs/rag/design.md`
- `docs/rag/snapshots.md`
- `docs/architecture/agents_contracts.md`
```
