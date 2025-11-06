# Executor 결과 스키마

prompt.md 3.3, docs/architecture/agents_contracts.md, docs/architecture/orchestration_and_tracing.md 요구에 따라 Executor가 반환하는 결과를 정의한다. 모든 작업은 `conda`의 `vul` 환경에서 수행한다.

## JSON Schema (요약)
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ExecutorResult",
  "type": "object",
  "required": [
    "build_log",
    "run_log",
    "verify_pass",
    "traces",
    "resource_usage"
  ],
  "properties": {
    "sid": {"type": "string"},
    "trace_id": {"type": "string"},
    "build_log": {"type": "string"},
    "run_log": {"type": "string"},
    "verify_pass": {"type": "boolean"},
    "traces": {
      "type": "array",
      "items": {"type": "string"}
    },
    "coverage": {
      "type": "object",
      "properties": {
        "line": {"type": "number", "minimum": 0, "maximum": 1},
        "branch": {"type": "number", "minimum": 0, "maximum": 1}
      }
    },
    "resource_usage": {
      "type": "object",
      "required": ["cpu", "memory"],
      "properties": {
        "cpu": {"type": "string"},
        "memory": {"type": "string"},
        "duration_ms": {"type": "integer", "minimum": 0}
      }
    },
    "sbom_ref": {"type": "string"},
    "image_digest": {"type": "string"},
    "security_gates": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "status"],
        "properties": {
          "name": {"type": "string"},
          "status": {"type": "string", "enum": ["pass", "fail"]},
          "details": {"type": "string"}
        }
      }
    }
  }
}
```

## 예시
```json
{
  "sid": "sid-1234",
  "trace_id": "trace-exec",
  "build_log": "...",
  "run_log": "...",
  "verify_pass": true,
  "traces": ["otel-trace-1"],
  "coverage": {"line": 0.82},
  "resource_usage": {"cpu": "600m", "memory": "1.2Gi", "duration_ms": 45000},
  "sbom_ref": "oci://registry/artifacts/sbom@sha256:abcd",
  "image_digest": "sha256:1234",
  "security_gates": [{"name": "network-egress", "status": "pass"}]
}
```

## 정합성 체크
- prompt.md 3.3 요구 필드 포함(build/run/verify/logs/traces/coverage/resource_usage).
- docs/architecture/metastore_and_artifacts.md와 연결되는 SBOM/image 필드 추가.
- 보안 게이트 결과를 포함해 정책 준수를 기록.

## 연관 문서
- `docs/architecture/agents_contracts.md`
- `docs/executor/security_policies.md`
- `docs/evals/specs.md`
```
