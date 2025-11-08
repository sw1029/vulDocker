# 단일 SID에서 다중 취약 생성 설계·구현안

본 문서는 하나의 시나리오 ID(SID) 안에서 여러 취약 유형(CWE/CVE 등)을 동시에 생성·검증·패키징하기 위한 구체적인 구현 방안을 제시한다. 현재 단일 취약 전제를 유지하는 구성과의 호환을 유지하면서 단계적으로 확장하는 것을 목표로 한다.

## 0. 추진 범위·연관 맵
- 다중 취약 시나리오 지원이 입력 스펙부터 메타스토어, 에이전트 계약, 실행·검증 파이프라인까지 전 구간에 영향을 주므로 기존 문서들과의 정합성을 먼저 점검한다.
- 아래 표는 주요 구성 요소와 실제 코드/문서 위치를 연결해 구현 시 누락을 방지하기 위한 체크리스트다.

| 구성 요소 | 영향 모듈/파일 | 연관 문서 | 비고 |
| --- | --- | --- | --- |
| 입력 스펙/템플릿 | `inputs/*.yml`, `common/schema/requirement.py` | `docs/requirements/goal_and_outputs.md` | 복수 취약 ID 허용 규칙 명시 |
| SID/메타스토어 | `metadata/sid.py`, `metadata/<SID>/plan.json` | `docs/variability_repro/design.md`, `docs/architecture/metastore_and_artifacts.md` | `vuln_ids_digest` 추가 및 캐시 키 영향 |
| Researcher/Generator 계약 | `agents/*`, `common/prompts/templates.py` | `docs/architecture/agents_contracts.md`, `docs/milestones/todo_13-15_code_plan.md` | 번들 단위 보고서/manifest 확장 |
| Executor/Eval/로그 | `executor/runtime/*`, `evals/*`, `artifacts/<SID>/` | `docs/executor/security_policies.md`, `docs/evals/specs.md`, `docs/ops/observability.md` | 취약별 로그/트레이스 디렉토리 표준화 |
| Packaging/CLI/CI | `orchestrator/plan.py`, `ops/ci/run_case.sh` | `docs/architecture/orchestration_and_tracing.md`, `docs/architecture/project_structure.md` | 단일 SID 내 번들 집계 및 플래그 제어 |

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

### 2.1 입력 검증 및 템플릿 반영
- `docs/requirements/goal_and_outputs.md`에서 이미 “복수 지정 가능”이라 명시된 규칙을 실제 템플릿(`inputs/base_requirement.yml`)과 요구 스키마(`common/schema/requirement.py`)에 반영한다.
- 스키마는 `vuln_ids?: list[str]` 타입과 `multi_vuln?: bool` 플래그를 추가하고, `docs/milestones/todo_13-15_code_plan.md`의 PLAN 작업 목록에 맞춰 Validation 에러 메시지를 구체화한다.
- 샘플 요구 파일(`inputs/examples/*.yml`)에는 단일/다중 케이스 두 가지를 모두 제공해 회귀 테스트에 활용한다.

### 2.2 CLI 파라미터 및 옵트인 정책
- `orchestrator/plan.py --multi-vuln` 또는 입력 YAML의 `multi_vuln: true` 중 하나라도 설정되면 배열 검증 로직을 강제 적용한다.
- 옵트인을 하지 않은 경우에는 `vuln_ids`가 입력에 있어도 경고 후 무시하거나 실패 여부를 정책으로 결정한다(초기에는 경고 + 단일 모드 강제).
- PLAN 단계에서 확정된 취약 배열은 Trace/메타데이터와 함께 저장되어 `docs/architecture/orchestration_and_tracing.md`에서 정의한 상태 전이 간 공유된다.

## 3. SID 정책
- 기존 SID 구성 요소에 `vuln_ids_digest = sha256(join(sorted(vuln_ids)))`를 추가해 다중 취약 조합을 유일하게 반영한다.
- 단일 `vuln_id`만 있을 때는 기존 해시 규칙 유지(호환성 보장).
- `docs/variability_repro/design.md`와 `docs/architecture/metastore_and_artifacts.md`에 정의된 SID 공식은 그대로 두되, `metadata/sid.py` 계산 시 `multi_vuln` 플래그가 참일 경우 추가 필드를 연결하는 방식으로 후방 호환한다.
- `plan.json`과 `metadata/<SID>/metadata.json`에는 `vuln_ids`와 함께 `vuln_ids_digest`를 기록해 캐시 키 충돌을 방지하고, Pack 단계에서 검증할 수 있는 근거를 남긴다.

## 4. PLAN/Orchestrator 변경
- `orchestrator/plan.py`
  - `requirement["vuln_ids"]`를 정규화하여 `plan.json`에 저장.
  - `vuln_ids_digest`를 SID 계산에 반영(옵트인 플래그가 꺼져 있으면 현행 유지 가능).
- 옵트인 플래그 제안: `multi_vuln: true`(기본 false) — 롤아웃 초기 충돌 최소화.

### 4.1 plan.json 구조 확장
- `plan["run_matrix"]` 내에 `vuln_bundles` 배열을 추가하고, 각 항목에 `vuln_id`, `pattern_id`, `deps`, `executor_policy`를 포함시켜 이후 단계에서 동일 정보를 반복 계산하지 않도록 한다.
- PLAN 산출물은 `docs/architecture/project_structure.md`의 규약에 따라 `metadata/<SID>/plan.json`에 기록되며, 다중 취약 여부는 `plan["features"]["multi_vuln"]` 플래그로 코드에서 손쉽게 분기한다.
- 구현: `common/run_matrix.py`가 `plan.run_matrix.vuln_bundles[]`를 dataclass(`VulnBundle`)로 노출하고, 각 서비스는 동일 모듈의 `workspace_dir_for_bundle`, `metadata_dir_for_bundle`, `artifacts_dir_for_bundle`를 호출해 `workspaces/<SID>/app/<slug>`, `metadata/<SID>/bundles/<slug>`, `artifacts/<SID>/run/<slug>` 계산을 공유한다. 루트 경로에는 인덱스 JSON(`metadata/<SID>/researcher_reports.json`, `generator_runs.json`, `artifacts/<SID>/run/index.json`)을 생성해 번들→파일 매핑을 추적한다.

### 4.2 상태 기계 영향
- 상태 정의(`docs/architecture/orchestration_and_tracing.md`)는 그대로 유지하되, `RUN` 상태에서 취약 번들 수만큼 내부 sub-step을 순회하도록 `orchestrator/state_machine/handlers/run.py`를 확장한다.
- Trace Span 네이밍은 `run.executor/<vuln_id>` 형태로 세분화해 `ops/observability` 대시보드에서 취약별 성공/실패를 바로 확인하도록 한다.

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
- 구현 상태:
  - `agents/researcher/main.py`가 `load_plan` + `common.run_matrix.load_vuln_bundles()`를 읽어 번들을 순회하고, 각 번들마다 `ResearcherService(..., bundle=bundle)`를 실행해 `metadata/<SID>/bundles/<slug>/researcher_report.json`을 생성한다.
  - 루트 `metadata/<SID>/researcher_reports.json` 인덱스는 취약별 `report_path`를 기록하고, Generator/Reviewer가 동일 슬러그로 참조한다.

### 5.1 계약/프롬프트 정합성
- `docs/architecture/agents_contracts.md`의 Researcher 섹션에 새로운 `reports[]` 배열 필드를 명시하고, Reviewer/Generator가 동일 키(`vuln_id`)를 기준으로 데이터를 참조할 수 있도록 한다.
- 프롬프트 템플릿은 `multi_vuln_context` 블록을 추가해 LLM이 “공유 인프라(언어/프레임워크/런타임)는 단일 SID로 묶인다”는 제약을 이해하도록 안내한다.
- Retrieval Snapshot은 취약별로도 동일 값을 사용하므로, 응답 객체에 `retrieval_snapshot_id`를 최상위/취약별 모두에 기록해 `docs/milestones/todo_13-15_code_plan.md`의 추적 요건을 충족한다.

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
- `workspaces/<SID>/app/<vuln_id_slug>/...` 하위에 취약별 코드/PoC 파일을 분리 저장. 단일 취약 시에는 기존 경로(`workspaces/<SID>/app`)를 그대로 사용한다.
- 루트 `requirements.txt`는 취약별 deps의 합집합(가드/충돌 시 로그 보고).
- 구현 상태: `agents/generator/main.py`가 번들마다 `GeneratorService(..., bundle=bundle)`를 호출하며, 서비스는 `workspace_dir_for_bundle`을 통해 슬러그 디렉터리를 보장하고 `metadata/<SID>/bundles/<slug>/generator_template.json`, `generator_candidates.json`, `user_deps.json`을 번들별로 기록한다. 루트 `metadata/<SID>/generator_runs.json`은 취약별 workspace 경로를 요약한다.

### 6.3 Guard/Deps
- 정적 의존성 감지/가드는 취약별로 수행하고, 누락 deps는 번들별로 보고.
- `dep_guard.auto_patch`가 활성화되면 번들 deps와 루트 requirements 동기화.

### 6.4 Manifest 정합성
- `docs/architecture/project_structure.md`에 정의된 `workspaces/<SID>/app/` 규약을 그대로 사용하되, 취약별 디렉터리 이름은 `vuln_id`를 슬러그화(`cwe-089-sqli`)해 충돌을 방지한다.
- Manifest JSON은 `docs/requirements/goal_and_outputs.md`의 “취약 환경 아티팩트” 정의에 따라 SBOM/PoC 경로를 명시하고, Pack 단계에서 해당 경로가 모두 포함되어 있는지 자동 검증한다.

### 6.5 Reviewer
- Reviewer는 `plan.run_matrix.vuln_bundles[]`를 순회해 번들별로 실행 로그/워크스페이스를 분석하고, `metadata/<SID>/bundles/<slug>/reviewer_report.json`을 생성한다.
- 루트 `metadata/<SID>/reviewer_reports.json`에는 각 번들의 보고서 경로/차단 여부/이슈 수를 기록하고, `metadata/<SID>/reviewer_report.json` 요약에는 현재 루프 기준으로 차단된 번들 목록과 대표 이슈 샘플을 포함한다.
- LoopController는 번들 중 하나라도 차단 상태이면 전체 REVIEW 단계를 실패로 기록하며, 차단된 번들의 slug 목록을 reason/metadata로 남긴다.

## 7. Executor & Eval
### 7.1 Executor
- Docker 이미지는 번들별 workspace(`workspaces/<SID>/app/<slug>`) 기준으로 빌드하며, 빌드/Run 로그는 각각 `artifacts/<SID>/build/<slug>/build.log`, `artifacts/<SID>/run/<slug>/run.log`로 분리한다.
- `executor/runtime/docker_local.py`는 다중 취약 모드일 때 `image_tag = f"{sid}-{slug}"` 규칙을 사용하고, 루트 `artifacts/<SID>/run/index.json`에 취약별 로그/이미지 ID를 기록한다.
- 실패 시에도 다음 번들을 계속 시도하며, `policy.stop_on_first_failure`(`plan.policy.stop_on_first_failure`)가 `true`이면 첫 실패 직후 루프를 중단하고 실행기를 실패 상태로 종료한다. 각 번들의 실행 요약(`summary.json`)에는 `build_passed`, `run_passed`, `executed`, `error`, `failed_stage`를 기록하여 Eval/manifest가 상태를 판독할 수 있도록 한다.
- 외부 DB가 필요한 경우 `executor.allow_network: true`, `executor.network_mode: bridge`, `executor.sidecars[]` 입력을 통해 사이드카 컨테이너(MySQL 등)를 선언할 수 있으며, Executor는 번들마다 사이드카→메인 컨테이너 순으로 기동 후 `sidecars[]` 메타데이터를 run summary/manifest에 기록한다. 사이드카의 `ready_probe.wait_seconds` 값으로 단순 대기 시간을 제어한다.
- 사이드카에 `aliases[]`가 지정되면 Executor는 SID 기반 사용자 정의 네트워크(`sid-<hash>-net`)를 자동 생성해 alias를 부여하고, 메인 컨테이너 역시 해당 네트워크에서 실행한다. 커스텀 네트워크 이름을 직접 제어하려면 `executor.network_name`을 입력에 명시한다.

### 7.2 Eval
- 출력(요약):
- `evals/poc_verifier/mvp_sqli.py`는 각 번들의 `artifacts/<SID>/run/<slug>/run.log`를 평가하고, `artifacts/<SID>/reports/evals.json`에 아래 형태로 저장한다.
```json
{
  "sid": "sid-...",
  "overall_pass": true,
  "results": [
    {"vuln_id": "CWE-89",  "verify_pass": true,  "evidence": "SQLi SUCCESS"},
    {"vuln_id": "CWE-352", "verify_pass": false, "evidence": "Signature missing"}
  ]
}
```
- `overall_pass`는 기본 AND 정책(모든 번들 성공 시 true)이며, 정책 분기는 추후 `plan.policy` 단계에서 확장한다.
- Executor가 특정 번들을 건너뛰었거나 `stop_on_first_failure`로 중단되면 `results[].status`는 `skipped` 또는 `error`로 표기되어 manifest/CI에서 즉시 감지할 수 있다.

### 7.3 트레이싱/관측성
- `docs/ops/observability.md`와 일치하도록 Executor/Eval은 취약별 Span Attribute(`vuln_id`)와 로그 필드(`artifact_path`, `attempt`)를 필수 포함한다.
- `artifacts/<SID>/run/<vuln_id>/run.log` 경로는 OTEL 로그 수집 파이프라인의 파일 스크래이퍼 목록에 등록해, 번들별 실패 시 대시보드에서 즉시 확인하도록 한다.

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
- 지표 산식은 `docs/variability_repro/design.md` 4장의 기준을 재사용하되, `metrics.by_vuln`에 저장된 값은 Variation Key와 함께 메타스토어에 적재해 동일 SID 재실행 시 비교가 가능해야 한다.

## 9. Packaging / Manifest
- `metadata/<SID>/manifest.json`에는 `features`, `policy`, `vuln_ids`, `vuln_ids_digest`, `indices{researcher_reports,generator_runs,reviewer_report,reviewer_reports_index,run_index,evals,diversity}`가 포함되며, `bundles[]`는 아래 필드를 갖는다.
  - `vuln_id`, `slug`, `pattern_id`, `deps_digest`
  - `paths.workspace|metadata|build|run`
  - `artifacts.build_log`, `artifacts.sbom`, `artifacts.run_log`, `artifacts.run_summary`(build/run pass 여부, error, image_tag), `artifacts.eval_result`(`results[]` 중 일치 항목)
  - `researcher_report`, `generator_template`, `reviewer_report` 경로
- Pack 단계에서 루트 `reports`(evals/diversity JSON)도 manifest에 인라인으로 포함해 CI/Slack 후속 파이프라인이 단일 파일만 읽으면 되도록 한다.
- `ops/ci/run_case.sh`는 manifest를 읽어 번들별 실행/Eval 결과를 콘솔 요약으로 출력한다.

## 10. CLI/CI 연동
- `orchestrator/plan.py`에 `--multi-vuln`(기본 off) 추가 또는 `requirement.multi_vuln: true`로 동작 제어.
- `ops/ci/run_case.sh` 요약 출력에 취약별 결과를 포함.
- CI 단계에서는 `ops/ci/run_case.sh --summary multi` 실행 시 `artifacts/<SID>/reports/evals.json`의 `details[]`를 파싱해 표 형태로 콘솔에 출력하고, `docs/milestones/todo_13-15_code_plan.md`에서 요구한 KPI(성공률, 실패 유형)를 취약별로 분리해 Slack/웹훅에 전달한다.

## 11. 마이그레이션/롤아웃
- 기본은 기존 단일 취약 모드 유지. 다중 취약은 옵트인(`multi_vuln: true`).
- 단계적 도입: Researcher/manifest → Executor/Eval → Diversity 순으로 확장.
- 롤아웃 단계별로 `docs/architecture/orchestration_and_tracing.md`의 상태 전이 테스트를 재실행하고, `docs/ops/observability.md`에 명시된 대시보드 위젯(성공률, 평균 실행 시간)을 다중 취약 차원으로 분리해 KPI 변화를 추적한다.

## 12. 리스크/완화
- 복잡도 증가: 스키마/경로/로그가 늘어남 → 스키마 검증/테스트 강화.
- 실패 전파: 번들 하나 실패가 전체 실패로 기록될 수 있음 → `stop_on_first_failure`/`overall_pass` 정책 분리.
- 의존성 충돌: 번들 합집합 requirements 충돌 가능 → guard에서 취약별/루트 충돌 감지 및 권고 로그.

## 13. 테스트 계획
- 단일 vuln_id 케이스 회귀(동등 동작 보장).
- 다중 vuln_ids 2~3개 케이스: 각 번들 PoC 통과/실패 조합을 시뮬레이션해 Eval/overall_pass 정책 검증.
- SBOM/Pack 산출에 취약별 파일/메타가 포함되는지 확인.
- `docs/evals/specs.md`의 검증 케이스 포맷을 활용해 취약별 판정 근거를 JSON Schema로 검증하고, CI에서 `pytest tests/e2e/test_multi_vuln_sid.py`와 같은 통합 테스트를 추가한다.

## 14. 연관 문서
- `docs/requirements/goal_and_outputs.md` — 입력 규격 및 메타데이터 정의 확장.
- `docs/milestones/todo_13-15_code_plan.md` — TODO 15 고도화 항목과 연계.
- `docs/architecture/agents_contracts.md` — Researcher/Generator/Executor 계약 확장 포인트.

## 15. 진행 현황
- 2025-11-08: 입력 스펙~패키징 파이프라인 전 구간에 대한 다중 취약 설계 초안을 정리하고, 연관 문서 맵 및 컴포넌트별 구현 포인트(PLAN, Researcher, Generator, Executor, Eval, Observability, CI)를 구체화함.
- 2025-11-08(코드): `common/schema/requirement.py`로 입력 정규화/검증을 구현하고, `orchestrator/plan.py --multi-vuln` 플래그, `plan.run_matrix.vuln_bundles`, `vuln_ids_digest` 기반 SID 확장(`common/sid.py`)을 배포. `inputs/base_requirement.yml`, `inputs/multi_vuln_example.yml`, `docs/requirements/goal_and_outputs.md`, `docs/architecture/agents_contracts.md`를 함께 갱신해 문서 정합성을 확보함.
- 2025-11-08(코드2): `common/run_matrix.py`를 추가해 PLAN 산출물에서 번들을 반복 처리하고, Researcher/Generator/Executor/Eval CLI가 취약별 workspace/metadata/artifacts 경로를 생성하도록 구현. 루트 인덱스(`metadata/<SID>/researcher_reports.json`, `generator_runs.json`, `artifacts/<SID>/run/index.json`, `reports/evals.json`)와 번들 전용 디렉터리(`metadata/<SID>/bundles/<slug>/...`, `artifacts/<SID>/build|run/<slug>/...`)를 표준화했으며, 관련 문서(`docs/variability_repro/design.md`, `docs/architecture/metastore_and_artifacts.md`)도 동기화함.
- 2025-11-08(코드3): PACK 단계가 manifest에 번들별 패턴/경로/아티팩트/Eval 결과를 집계하고, Executor/Eval은 `policy.stop_on_first_failure`를 읽어 실행 루프를 제어한다. CI 스크립트(`ops/ci/run_case.sh`)는 manifest를 사용해 번들별 통과 여부를 출력하며, `docs/architecture/metastore_and_artifacts.md`, `docs/requirements/goal_and_outputs.md`에 정책/manifest 확장을 기록했다.
- 후속(예정): PACK/Manifest 단계에서 `bundles[].artifact_hash`를 계산하고, Reviewer/CI 파이프라인이 번들 인덱스를 사용해 취약별 KPI를 Slack/대시보드로 전송하도록 확장.
