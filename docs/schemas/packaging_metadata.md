# 패키징 메타데이터 스키마

prompt.md 3.4 및 docs/architecture/metastore_and_artifacts.md/requirements 문서의 메타데이터 정의를 반영한다. 모든 작업은 `conda`의 `vul` 환경에서 수행한다.

## JSON Schema (요약)
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "PackagingMetadata",
  "type": "object",
  "required": [
    "scenario_id",
    "seed",
    "model_version",
    "prompt_hash",
    "retriever_commit",
    "base_image_digest",
    "sbom_ref",
    "safety_gates",
    "timestamps"
  ],
  "properties": {
    "scenario_id": {"type": "string"},
    "seed": {"type": "integer"},
    "model_version": {"type": "string"},
    "prompt_hash": {"type": "string"},
    "retriever_commit": {"type": "string"},
    "corpus_snapshot": {"type": "string"},
    "pattern_id": {"type": "string"},
    "deps_digest": {"type": "string"},
    "base_image_digest": {"type": "string"},
    "sbom_ref": {"type": "string"},
    "variation_key": {"type": "object"},
    "trace_id": {"type": "string"},
    "safety_gates": {
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
    },
    "timestamps": {
      "type": "object",
      "required": ["plan", "draft", "build", "run", "verify", "pack"],
      "properties": {
        "plan": {"type": "string", "format": "date-time"},
        "draft": {"type": "string", "format": "date-time"},
        "build": {"type": "string", "format": "date-time"},
        "run": {"type": "string", "format": "date-time"},
        "verify": {"type": "string", "format": "date-time"},
        "pack": {"type": "string", "format": "date-time"}
      }
    },
    "status": {"type": "string", "enum": ["pending", "success", "failed"]}
  }
}
```

## 예시
```json
{
  "scenario_id": "sid-1234",
  "seed": 42,
  "model_version": "gpt-x-2024-10",
  "prompt_hash": "sha256:abcd",
  "retriever_commit": "abc123",
  "corpus_snapshot": "rag-snap-20241106",
  "pattern_id": "sqli-raw-orm",
  "deps_digest": "sha256:def0",
  "base_image_digest": "sha256:1111",
  "sbom_ref": "oci://registry/sbom@sha256:9999",
  "variation_key": {"top_p": 0.95, "temperature": 0.7},
  "trace_id": "trace-main",
  "safety_gates": [{"name": "image-scan", "status": "pass"}],
  "timestamps": {
    "plan": "2024-11-06T10:00:00Z",
    "draft": "2024-11-06T10:05:00Z",
    "build": "2024-11-06T10:15:00Z",
    "run": "2024-11-06T10:20:00Z",
    "verify": "2024-11-06T10:25:00Z",
    "pack": "2024-11-06T10:30:00Z"
  },
  "status": "success"
}
```

## 정합성 체크
- prompt.md 3.4 필드와 docs/architecture/metastore_and_artifacts.md ScenarioEntry 모델에 대응.
- docs/requirements/goal_and_outputs.md에서 요구한 재현 리포트 메타데이터와 호환.

## 연관 문서
- `docs/variability_repro/design.md`
- `docs/architecture/metastore_and_artifacts.md`
- `docs/reporting/reproducibility_report_template.md`
```
