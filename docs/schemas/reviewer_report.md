# Reviewer 버그 리포트 스키마

prompt.md 3.2 및 docs/architecture/agents_contracts.md에 정의된 Reviewer 산출물 스키마를 명시한다. 모든 작업은 `conda`의 `vul` 환경에서 수행한다.

## JSON Schema (요약)
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ReviewerReport",
  "type": "object",
  "required": [
    "file",
    "line",
    "issue",
    "fix_hint",
    "severity",
    "evidence_log_ids"
  ],
  "properties": {
    "sid": {"type": "string"},
    "trace_id": {"type": "string"},
    "loop_count": {"type": "integer", "minimum": 0},
    "file": {"type": "string"},
    "line": {"type": "integer", "minimum": 1},
    "column": {"type": "integer", "minimum": 1},
    "issue": {"type": "string"},
    "fix_hint": {"type": "string"},
    "test_change": {"type": "string"},
    "severity": {"type": "string", "enum": ["info", "low", "medium", "high", "critical"]},
    "evidence_log_ids": {
      "type": "array",
      "items": {"type": "string"}
    },
    "blocking": {"type": "boolean", "default": false},
    "created_at": {"type": "string", "format": "date-time"}
  }
}
```

## 예시
```json
{
  "sid": "sid-1234",
  "trace_id": "trace-review",
  "loop_count": 1,
  "file": "app/routes.py",
  "line": 120,
  "issue": "사용자 입력을 그대로 SQL에 삽입",
  "fix_hint": "parameterized query 적용",
  "test_change": "SQLi payload 테스트 케이스 추가",
  "severity": "high",
  "evidence_log_ids": ["run-log-20241106-001"],
  "blocking": true,
  "created_at": "2024-11-06T12:34:56Z"
}
```

## 정합성 체크
- prompt.md 3.2와 동일 필드 구성.
- docs/architecture/agents_contracts.md Reviewer 계약 요구와 일치.
- Severity/Blocking 필드는 오케스트레이터 LOOP 판단에 사용 가능.

## 연관 문서
- `docs/architecture/agents_contracts.md`
- `docs/evals/specs.md`
- `docs/reporting/reproducibility_report_template.md`
```
