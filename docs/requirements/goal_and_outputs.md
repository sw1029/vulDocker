# 목표와 출력 정의

본 문서는 `implement_plan/prompt.md`에서 정의한 요구와 정합성을 유지하며 자율 AI 에이전트 기반 온디맨드 취약점 테스트베드의 입력/출력 및 성공 기준을 명확히 한다. 모든 작업은 `conda`의 `vul` 환경에서 수행한다.

## 1. 입력 규격
- **취약점 유형 ID**: CWE, CVE, 기타 표준 ID. 복수 지정 가능.
  - 입력 필드: `vuln_id: string`(기존), `vuln_ids: string[]`(신규). 배열은 공백/중복 제거, 대문자 정규화 규칙을 따른다.
  - `multi_vuln: true` 또는 CLI `orchestrator/plan.py --multi-vuln`로 옵트인하면 `vuln_ids` 전체를 단일 SID에서 처리한다. 미옵트인 시에는 첫 번째 항목만 사용하고 나머지는 경고 후 무시한다.
  - 다중 취약 조합은 `vuln_ids_digest = sha256(join(sorted(vuln_ids)))` 형태로 SID 계산과 메타스토어 키에 반영된다.
- **취약 패턴 서술**: 자연어 설명, 코드 스니펫, 설정 조건 등 자유 형식 추가 정보.
- **환경 제약**: 언어/프레임워크/DB/OS/로케일 등 요구 조건. 미지정 시 시나리오 차원 테이블과 LHS 샘플링으로 자동 선택.
- **외부 DB 허용 여부**: `runtime.allow_external_db`(기본값 `false`)로 명시. 실행기는 기본적으로 `--network none`으로 동작하므로, 외부 데이터베이스나 네트워크 서비스가 필요하면 `true`로 설정해 템플릿 선택 및 실행기 정책과 일치시켜야 한다.
- **사용자 의존성 주입**: `user_deps` 배열로 pip 패키지를 지정하면 Generator가 `manifest.deps`/`requirements*.txt`에 강제로 포함한다. stdlib(`sqlite3`) 등은 guard에서 경고 후 무시될 수 있으므로 최소한의 실제 외부 패키지만 명시하는 것을 권장한다.
- **다변성 모드 요청**: 기본(재현) 또는 다양성 강조 모드(top-p, self-consistency, variation key 지정).
- **검증 강도 옵션**: 메타모픽 테스트, 정적 분석, 커버리지 측정 등 옵션 선택.
- **실행 정책**: 
  - `policy.stop_on_first_failure`(기본 `false`)로 Executor가 첫 실패 번들에서 중단할지 여부를 지정할 수 있다.
  - `executor.allow_network`/`executor.network_mode`/`executor.network_name`으로 `docker run` 네트워크 모드를 제어한다. `allow_network=false`이면 `--network none`, `true`이면 bridge 또는 명시한 사용자 정의 네트워크를 사용한다. `executor.sidecars[].aliases[]`를 지정하면 Executor가 SID 기반의 사용자 정의 네트워크를 자동 생성해 alias를 붙인다.
  - `executor.sidecars[]` 배열을 사용하면 MySQL 등 외부 의존 서비스를 사이드카 컨테이너로 함께 기동할 수 있으며 `name`, `image`, `env`, `aliases`, `ready_probe`를 정의해 Executor가 health check 후 메인 컨테이너를 실행한다.

## 2. 핵심 출력물 4종
1. **취약 환경 아티팩트**
   - Docker 이미지 또는 MicroVM 이미지(Firecracker/Kata/gVisor). 
   - SBOM(SPDX/CycloneDX) 포함, 베이스 이미지 다이제스트 고정.
   - 빌드 로그, 패치 내역, 의존성 잠금 파일 동봉.
2. **PoC 검증 스크립트**
   - 자동으로 익스플로잇 성공 여부를 판정하고, 실패 시 로그·트레이스를 수집.
   - 메타모픽 변형 입력 세트와 연동 가능.
3. **재현 리포트**
   - 실행 로그, 환경 해시, 모델 버전, 프롬프트 해시, 시드, RAG 스냅샷 ID, Variation Key 기록.
   - Scenario ID(SID) 기반 링크 제공으로 재실행 경로 고정.
4. **메타데이터 패키지**
   - 취약점 메타 정보, 시나리오 파라미터, 선택된 패턴/템플릿, 평가 지표.
   - `scenario_id, seed, model_version, prompt_hash, retriever_commit, base_image_digest, sbom_ref, safety_gates[], timestamps` 필수 포함.

## 3. 성공 기준 (SLO)
- **PoC 성공률**: 생성된 PoC가 명시된 취약 동작을 재현하고 자동 판정에서 통과.
- **로그 및 트레이싱 완결성**: PLAN→PACK 전 단계의 TraceId/SpanId가 수집되고 OpenTelemetry/W3C Trace Context 규약 준수.
- **재현성**: 동일 입력과 SID, seed, 스냅샷으로 재실행 시 동일 아티팩트와 결과가 생성(정합성 허용 오차 없음).
- **다변성 커버리지**: 시나리오 차원 테이블 대비 라틴 하이퍼큐브 샘플링 커버 비율이 목표치 이상, 패턴 선택 분포의 샤논 엔트로피 지표가 기준 이상.
- **안전 게이트 준수**: 네트워크 차단 정책, 이미지 스캐닝, 의심 페이로드 차단, 3rd-party PoC 실행 금지 등 보안 정책 위반 0건.

## 4. 산출 및 추적 방식
- 문서 산출물: `docs/requirements/goal_and_outputs.md` (본 문서) 유지보수, 중요 변경 시 버전 태그.
- 아티팩트 저장소: `artifacts/<scenario_id>/`에 이미지/SBOM/로그/리포트/메타데이터 저장.
- 메타스토어: 중앙 DB 또는 Git LFS에 SID 키 기반으로 버전 관리, 결과 캐시 정책 문서화(`docs/architecture/metastore_and_artifacts.md`와 연동).
- 보고 체계: 재현 리포트는 `docs/reporting/reproducibility_report_template.md` 형식 준수, 주요 KPI는 `ops/observability/` 대시보드로 노출.

## 5. 정합성 체크리스트
- [x] prompt.md의 목표/출력 정의와 일치.
- [x] TODO 1단계 항목(입력 규격, 출력물 명세, 성공 기준, 산출 경로) 반영.
- [x] `docs/README.md`의 기록 원칙(비-TODO 문서화) 준수.
- [x] 실험·재현 정보는 추후 `experiments/` 노트북과 SID를 통해 연동.

## 연관 문서
- `docs/architecture/project_structure.md`
- `docs/architecture/metastore_and_artifacts.md`
- `docs/reporting/reproducibility_report_template.md`
