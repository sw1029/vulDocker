# 단일 SID에서 다중 취약 생성 설계·구현안

본 문서는 하나의 시나리오 ID(SID) 안에서 여러 취약 유형(CWE/CVE 등)을 동시에 생성·검증·패키징하기 위한 구체적인 구현 방안을 제시한다. 현재 단일 취약 전제를 유지하는 구성과의 호환을 유지하면서 단계적으로 확장하는 것을 목표로 한다.

## 1. 목표와 범위
- 하나의 입력에서 `vuln_ids: ["CWE-89", "CWE-352", ...]`처럼 다중 취약을 지정.
- 단일 SID로 Build(1회) → Run/PoC(취약별 다중) → Eval(취약별 + 집계) → Pack(번들화)까지 처리.
- 기존 단일 취약 플로우와 완전 호환(옵트인 방식).

## 2. 입력 스펙 확장
- `vuln_id: string`(기존)과 함께 `vuln_ids: string[]`(신규)를 허용한다.
  - 규칙: `vuln_ids`가 유효 배열이면 이를 우선 사용, `vuln_id`는 fallback.
  - 배열 전처리: 공백/중복 제거, 대문자/정규화, 비어 있으면 에러.
- 예시(YAML)
```yaml
requirement_id: MULTI-EXAMPLE-0001
vuln_ids: ["CWE-89", "CWE-352"]
language: python
framework: flask
seed: 123
runtime:
  base_image: python:3.11-slim
  package_manager: pip
  allow_external_db: false
variation_key:
  mode: deterministic
```

## 3. SID 정책
- 기존 SID 구성 요소에 `vuln_ids_digest = sha256(join(sorted(vuln_ids)))`를 추가해 다중 취약 조합을 유일하게 반영한다.
- 단일 `vuln_id`만 있을 때는 기존 해시 규칙 유지(호환성 보장).

## 4. PLAN/Orchestrator 변경
- `orchestrator/plan.py`
  - `requirement["vuln_ids"]`를 정규화하여 `plan.json`에 저장.
  - `vuln_ids_digest`를 SID 계산에 반영(옵트인 플래그가 꺼져 있으면 현행 유지 가능).
- 옵트인 플래그 제안: `multi_vuln: true`(기본 false) — 롤아웃 초기 충돌 최소화.

## 5. Researcher 확장
- 쿼리 생성: `vuln_ids` 배열을 순회해 취약별 ReAct 쿼리를 생성하고 검색 결과를 취약별로 그룹화.
- 출력 스키마(요약):
```json
{
  "sid": "sid-...",
  "vuln_ids": ["CWE-89", "CWE-352"],
  "reports": [
    {"vuln_id": "CWE-89",  "tech_stack_candidates": ["Flask"], "pocs": [...], "deps": ["requests"], ...},
    {"vuln_id": "CWE-352", "tech_stack_candidates": ["Flask"], "pocs": [...], "deps": ["itsdangerous"], ...}
  ],
  "retrieval_snapshot_id": "rag-snap-..."
}
```
- 프롬프트(`common/prompts/templates.py`)는 다중 취약 컨텍스트를 포함.

## 6. Generator 확장
### 6.1 Manifest 스키마 확장
- 현재 단일 구조에 아래를 추가한다.
```json
{
  "vuln_bundles": [
    {
      "vuln_id": "CWE-89",
      "files": [{"path": "cwe-89/app.py", "content": "..."}, ...],
      "deps": ["requests"],
      "build": {"command": "pip install -r requirements.txt"},
      "run": {"command": "python cwe-89/app.py"},
      "poc": {"cmd": "python cwe-89/poc.py", "success_signature": "SQLi SUCCESS"},
      "notes": "...",
      "pattern_tags": ["sqli-string-concat"]
    },
    {"vuln_id": "CWE-352", "files": [...], "deps": [...], "poc": {...}}
  ]
}
```
- 단일 모드(기존)는 `vuln_bundles`가 비어 있거나 생략.

### 6.2 워크스페이스 구조
- `workspaces/<SID>/app/<vuln_id_slug>/...` 하위에 취약별 코드/PoC 파일을 분리 저장.
- 루트 `requirements.txt`는 취약별 deps의 합집합(가드/충돌 시 로그 보고).

### 6.3 Guard/Deps
- 정적 의존성 감지/가드는 취약별로 수행하고, 누락 deps는 번들별로 보고.
- `dep_guard.auto_patch`가 활성화되면 번들 deps와 루트 requirements 동기화.

## 7. Executor & Eval
### 7.1 Executor
- Docker 이미지 빌드는 1회.
- Run 단계: `vuln_bundles[*].poc`를 순차 실행.
  - 로그 경로: `artifacts/<SID>/run/<vuln_id>/run.log`
  - 실패 시에도 다음 번들을 계속 시도할지 정책화(옵션: `stop_on_first_failure`).

### 7.2 Eval
- 출력(요약):
```json
{
  "overall_pass": true,
  "details": [
    {"vuln_id": "CWE-89",  "verify_pass": true,  "evidence": "SQLi SUCCESS"},
    {"vuln_id": "CWE-352", "verify_pass": false, "evidence": "Signature missing"}
  ]
}
```
- `overall_pass`는 정책에 따라 AND/비율 기반 선택.

## 8. Diversity Metrics 확장
- 취약별 엔트로피/거리 산출 후, 집계 지표를 함께 기록.
```json
{
  "metrics": {
    "overall": {"shannon_entropy": 0.83, ...},
    "by_vuln": {
      "CWE-89": {"shannon_entropy": 0.5, ...},
      "CWE-352": {"shannon_entropy": 0.3, ...}
    }
  }
}
```

## 9. Packaging / Manifest
- `metadata/<SID>/manifest.json`에 `vuln_ids`와 `bundles[]`(취약별 pattern_id, paths, deps_digest 등)를 저장.
- Pack 결과는 동일 SID 아래에 소스 스냅샷을 취약별로 포함.

## 10. CLI/CI 연동
- `orchestrator/plan.py`에 `--multi-vuln`(기본 off) 추가 또는 `requirement.multi_vuln: true`로 동작 제어.
- `ops/ci/run_case.sh` 요약 출력에 취약별 결과를 포함.

## 11. 마이그레이션/롤아웃
- 기본은 기존 단일 취약 모드 유지. 다중 취약은 옵트인(`multi_vuln: true`).
- 단계적 도입: Researcher/manifest → Executor/Eval → Diversity 순으로 확장.

## 12. 리스크/완화
- 복잡도 증가: 스키마/경로/로그가 늘어남 → 스키마 검증/테스트 강화.
- 실패 전파: 번들 하나 실패가 전체 실패로 기록될 수 있음 → `stop_on_first_failure`/`overall_pass` 정책 분리.
- 의존성 충돌: 번들 합집합 requirements 충돌 가능 → guard에서 취약별/루트 충돌 감지 및 권고 로그.

## 13. 테스트 계획
- 단일 vuln_id 케이스 회귀(동등 동작 보장).
- 다중 vuln_ids 2~3개 케이스: 각 번들 PoC 통과/실패 조합을 시뮬레이션해 Eval/overall_pass 정책 검증.
- SBOM/Pack 산출에 취약별 파일/메타가 포함되는지 확인.

## 14. 연관 문서
- `docs/requirements/goal_and_outputs.md` — 입력 규격 및 메타데이터 정의 확장.
- `docs/milestones/todo_13-15_code_plan.md` — TODO 15 고도화 항목과 연계.
- `docs/architecture/agents_contracts.md` — Researcher/Generator/Executor 계약 확장 포인트.

