# 중앙 메타스토어 및 아티팩트 관리

본 문서는 `implement_plan/prompt.md`의 중앙 메타스토어·아티팩트 요구(2장, 7장, 10장)를 토대로 SID 키 체계, 버전 관리, 보존 정책을 정의한다. 모든 작업은 `conda`의 `vul` 환경에서 수행한다.

## 1. 메타스토어 개념
- **목적**: 모든 단계의 산출물을 내용 주소화하여 재현성(SID)과 다변성 관리(Variation Key)를 보장.
- **구현 옵션**: Git LFS + SQLite, 혹은 전용 KV 스토어(etcd, PostgreSQL). MVP는 Git LFS + JSON 인덱스 사용.
- **데이터 모델**
```
ScenarioEntry {
  sid: string,
  requirement_hash: string,
  seed: int,
  model_version: string,
  prompt_hash: string,
  retriever_commit: string,
  corpus_snapshot: string,
  pattern_id: string,
  deps_digest: string,
  base_image_digest: string,
  variation_key: json,
  trace_id: string,
  status: enum {pending, success, failed},
  artifacts_path: string,
  created_at, updated_at
}
```

## 2. Scenario ID(SID)
- 정의: `SID = H(model_version || prompt_hash || seed || retriever_commit || corpus_snapshot || pattern_id || deps_digest || base_image_digest [|| vuln_ids_digest])`.
  - `vuln_ids_digest = sha256(join(sorted(vuln_ids)))`는 다중 취약 모드(`plan.features.multi_vuln=true`)일 때만 접미한다.
- 해시 함수: SHA-256(기본), 필요 시 BLAKE3.
- Variation Key(예: `{top_p, temperature, self_consistency_k, pattern_pool_seed}`)는 SID 외부에 저장하며 다양성 요구 시 변경.

## 3. 아티팩트 디렉토리 규칙
- 구조: `artifacts/<SID>/`
  - `build/` : Dockerfile, 이미지 manifest, SBOM(`sbom.spdx.json` 또는 `.cdx`). 다중 취약일 경우 `build/<slug>/`에 취약별 빌드 로그·SBOM을 저장한다.
  - `run/` : PoC 실행 로그, 메트릭, traces dump. 다중 취약일 경우 `run/<slug>/run.log` + `summary.json`, 루트 `run/index.json`은 모든 번들의 로그 위치와 image_tag를 집계한다.
  - `reports/` : 재현 리포트, Reviewer 보고서, PoC 판정 결과. Eval 출력(`evals.json`)은 `results[]` 배열을 통해 취약별 판정을 병렬로 기록한다.
  - `metadata.json` : ScenarioEntry 정보 + Variation Key + KPI
- 다중 취약 모드에서는 `metadata/<SID>/bundles/<slug>/...`에 Researcher/Generator/Reviewer 산출물을 저장하고, 루트 인덱스(`metadata/<SID>/researcher_reports.json`, `metadata/<SID>/generator_runs.json`)로 번들별 경로를 취합한다.
- 압축 및 해시: 각 하위 폴더 tarball 생성 시 SHA-256 기록.
- PACK 단계에서 작성되는 `metadata/<SID>/manifest.json`은 아래 정보를 포함한다.
  - `features`, `policy`, `vuln_ids`, `vuln_ids_digest`
  - `indices`(`researcher_reports`, `generator_runs`, `reviewer_report`, `run/index.json`, `reports/evals.json`, `reports/diversity.json`)
  - `bundles[]`: `vuln_id`, `slug`, `pattern_id`, `deps_digest`, `paths.workspace|metadata|build|run`, `artifacts.build_log|sbom|run_log|run_summary|eval_result`, `researcher_report`, `generator_template`, `reviewer_report`, `artifacts.run_summary.network_mode`, `artifacts.run_summary.sidecars[]`
  - `reports.evals`(`overall_pass` + `results[]`) 및 `reports.diversity`
  - 향후 PACK 확장에서 `bundles[].artifact_hash`를 포함시켜 SBOM/이미지 무결성 검증을 단일 JSON에서 수행할 예정.

## 4. 버전 및 보존 정책
- **버전 태깅**: `sid` + `revision`(loop count) 조합으로 동일 SID 내 반복 수정 추적.
- **캐시**: `status=success`인 항목만 재사용, RUN 이후 실패 시 캐시 등록 금지.
- **보존 기간**: 성공 시 최소 90일, 실패 Trace는 30일 후 보관소로 이동.
- **SBOM & 이미지**: OCI Registry에 저장 시 다이제스트 고정, SBOM은 registry ref와 함께 메타스토어에 기록.

## 5. 접근 제어 및 감사
- 메타스토어 접근은 서비스 계정 + RBAC 사용.
- 아티팩트 다운로드에는 TraceId와 SID 검증 필요.
- Write 경로는 오케스트레이터만 허용, 에이전트는 읽기 전용.

## 6. 통합 흐름
1. PLAN 단계에서 SID 계산, 메타스토어에 `pending` 엔트리 생성.
2. 각 상태 완료 후 `metadata/<SID>/state_logs/`에 타임스탬프·해시 기록, 메타스토어 업데이트.
3. PACK 단계에서 아티팩트 디렉토리 완성, 해시 검증 후 `success`로 변경.
4. 동일 요구 재실행 시 SID 조회 → 캐시 hit면 생성 단계 스킵.

## 7. 정합성 체크리스트
- [x] prompt.md의 중앙 메타스토어, SID, SBOM 요구 반영.
- [x] TODO 5단계 항목(아티팩트 유형·버전·다이제스트, SID 스키마, 저장소/보존 정책) 충족.
- [x] `docs/architecture/project_structure.md`에서 정의한 `artifacts/`와 `metadata/` 경로 규칙과 일치.
- [x] `docs/requirements/goal_and_outputs.md`의 재현 리포트/메타데이터 정의와 조화.

## 연관 문서
- `docs/variability_repro/design.md`
- `docs/executor/sbom_guideline.md`
- `docs/reporting/reproducibility_report_template.md`
