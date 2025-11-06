자율 AI 에이전트 기반 온디맨드 취약점 테스트베드 – 구현 TODO

※ 모든 작업은 `conda`의 `vul` 환경에서 수행한다.

본 TODO는 implement_plan/prompt.md의 내용을 단계별·체계적으로 실행하기 위한 작업 목록이다. 코드 구현 이전에 아키텍처·스키마·운영 전략을 명확히 하고, 다변성(variability)과 재현성(reproducibility)을 동시 확보하는 것을 목표로 한다.

비고(중요)
- [ ] 비-TODO 기록(설계 결정, 실험 로그, 회의 메모, 위험·완화 기록, 스냅샷 설명 등)은 `docs/` 디렉토리에 별도 문서로 작성한다.
- [ ] 실험·프로토타이핑은 `experiments/` 디렉토리의 Jupyter 노트북으로 관리한다. 기본 템플릿: `experiments/00_repro_template.ipynb`.

### [x] 1. 목표·출력 정의 정합화
- [x] 입력 규격 정의(CWE, CVE, 자연어 요구)와 검증 범위 문서화
- [x] 핵심 출력물 4종 명세서 작성: 취약 환경 아티팩트, PoC 검증 스크립트, 재현 리포트, 메타데이터
- [x] 성공 기준(SLO) 합의: PoC 성공·로그·재현성·커버리지 지표
- [x] 산출: `docs/requirements/goal_and_outputs.md`

### [x] 2. 프로젝트 구조 스캐폴딩
- [x] 폴더 트리 초안 생성(오케스트레이터/에이전트/실행기/RAG/아티팩트/메타데이터/평가/운영)
- [x] 공용 유틸(로그, 해시, 경로 규약) 인터페이스 정의
- [x] 산출: `docs/architecture/project_structure.md`

### [x] 3. 오케스트레이션/상태 기계 설계
- [x] 상태 전이 정의: PLAN → DRAFT → BUILD → RUN → VERIFY → REVIEW → PACK
- [x] 재시도/백오프/중단 기준 정의, 장애 시 포렌식 수집 포인트 지정
- [x] OTEL Trace/Span 네이밍 규약 수립(W3C Trace Context 호환)
- [x] 산출: `docs/architecture/orchestration_and_tracing.md`

### [x] 4. 에이전트 역할/계약서(Contracts)
- [x] Researcher: RAG 리포트 JSON 계약 정의 + 툴사용 가이드(ReAct/Reflexion)
- [x] Generator: 소스·Dockerfile·설정·PoC 초안 산출 계약 정의
- [x] Reviewer: 로그·코드 동시 분석 리포트 계약 정의
- [x] Executor: 격리 환경에서 build/run/verify 실행 결과 계약 정의
- [x] 산출: `docs/architecture/agents_contracts.md`

### [x] 5. 중앙 메타스토어/아티팩트 관리
- [x] 아티팩트 유형·버전·다이제스트 체계 설계(SBOM 레퍼런스 포함)
- [x] SID(Scenario ID) 키 스키마, 결과 캐시 전략 정의
- [x] 저장소 배치(로컬/원격) 및 보존정책 정의
- [x] 산출: `docs/architecture/metastore_and_artifacts.md`

### [x] 6. 데이터 스키마(초안 → 확정)
- [x] RAG 보고서(JSON) 스키마: `vuln_id, intent, preconditions, tech_stack_candidates[], minimal_repro_steps[], references[], pocs[], deps[], risks[], retrieval_snapshot_id`
- [x] Reviewer 버그리포트(JSON) 스키마: `file, line, issue, fix_hint, test_change, severity, evidence_log_ids[]`
- [x] Executor 결과(JSON) 스키마: `build_log, run_log, verify_pass, traces, coverage?, resource_usage`
- [x] 패키징 메타(JSON) 스키마: `scenario_id, seed, model_version, prompt_hash, retriever_commit, base_image_digest, sbom_ref, safety_gates[], timestamps`
- [x] 산출: `docs/schemas/*.md` + 예제 JSON

### [x] 7. 모델·툴 선정 및 디코딩 전략
- [x] 주 모델(코드/툴 강점)·보조 모델(리뷰/체크리스트) 후보 비교표 작성
- [x] 재현 모드(greedy/temperature=0), 다변성 모드(top-p, self-consistency k) 파라미터 범위 정의
- [x] 멀티에이전트 프레임워크 패턴(AutoGen류) 채택 여부 결정
- [x] 산출: `docs/decoding/model_and_decoding_strategy.md`

### [x] 8. RAG 설계·구현 계획
- [x] 코퍼스 층위 정의(공용 지식, 최신 PoC 검색) 및 수집·정제 파이프라인
- [x] 색인/청킹 전략(함수 단위 등)과 리트리버 스냅샷 정책 수립
- [x] 실패 로그 기반 쿼리 증강(Reflexion) 루프 설계
- [x] 산출: `docs/rag/design.md`, `docs/rag/snapshots.md`

### [x] 9. 보안 샌드박스/실행기 정책
- [x] 격리 계층 선택(Firecracker/Kata/gVisor)과 트레이드오프 문서화
- [x] rootless, seccomp, read-only FS, no-privilege 기본 프로파일 정의
- [x] 네트워크 이그레스 차단/허용 도메인 리스트, 이미지 다이제스트 고정, SBOM 생성(SPDX/CycloneDX)
- [x] 산출: `docs/executor/security_policies.md`, `docs/executor/sbom_guideline.md`

### [x] 10. 다변성·재현성 동시 확보 설계
- [x] 시나리오 차원 테이블 설계(언어/프레임워크/DB/ORM/인코딩/배포/OS/로케일/입력채널 등)
- [x] LHS 샘플링 구현 계획과 시드 정책, 패턴 풀 정의 및 선택 로직
- [x] Scenario ID 정의와 고정 요소(모델/프롬프트/스냅샷/베이스 이미지/SBOM/LHS 시드) 결정
- [x] 산출: `docs/variability_repro/design.md`

### [x] 11. 자동 검증·평가 설계
- [x] PoC 판정 명세와 성공 조건 템플릿
- [x] 메타모픽 테스트 셋과 입력 변환 규칙(SQLi: 공백/주석/대소문 변형 등)
- [x] 정적 분석 신호(하드코딩 크리덴셜/위험 API) 및 커버리지 수집 방법
- [x] 산출: `docs/evals/specs.md`

### [x] 12. 운영·관측·감사
- [x] 분산 트레이싱 구성(collector/exporter), 대시보드 항목 설계
- [x] 표준 로그 스키마(단계/에이전트/시드/패턴/해시/자원 사용)
- [x] 보안 게이트(페이로드 차단, 외부 네트워크 제한, 이미지 스캔, 3rd-party PoC 금지)
- [x] 산출: `docs/ops/observability.md`, `docs/ops/security_gates.md`

### [x] 13. MVP 구현
- [x] 단일 LLM + 정적 RAG 샘플 1종 + 로컬 실행기로 최소 파이프라인 구현(런북 참조)
- [x] 생성→검증→수정 루프 1회 성공·로그·리포트 산출 확인(실험 노트북 기반)
- [x] 산출: `docs/milestones/mvp_runbook.md`, `experiments/01_mvp_sqli_loop.ipynb`, `artifacts/sid-mvp-sqli-0001/`

### [ ] 14. 핵심 안정화
- [ ] Generator/Reviewer 분리, Docker 격리 적용, DB 연동형 취약점(SQLi) 확대
- [ ] 실패 케이스 수집·분석, Reflexion 메모리 적용으로 개선율 측정
- [ ] 산출: 성공률/루프수 개선 리포트

### [ ] 15. 고도화
- [ ] Researcher 도입, 외부 검색+ReAct 연동, 최신 CVE로 자가 생성 검증
- [ ] 다변성 모드 도입(top-p, self-consistency) 및 품질-다양성 트레이드오프 측정
- [ ] 산출: 다양성 지표(H, 시나리오 거리) 및 재현율 리포트

### [x] 16. 위험·완화 계획 운영화
- [x] 격리 실패/환각·오분석/출력 단조로움/재현 실패 위험에 대한 모니터링 항목과 대응 절차 확정
- [x] 산출: `docs/risks/register.md`, 주기 점검 체크리스트(추가 예정)

### [x] 17. KPI 계측·대시보드
- [x] Exploit 성공률, 루프 수/수정 횟수, 시나리오 다양성, 재현율, 안전도 지표 수집 파이프라인
- [x] 산출: `ops/observability/dashboard_spec.md` (샘플 패널 정의)

### [x] 18. 도메인 지식 베이스 구축
- [x] SQLi 분류 서베이 기반 템플릿 규칙화, Juliet 1.3 도입 및 회귀 평가 설계
- [x] 산출: `docs/rag/corpus_guide.md` (구성 가이드, 인용·출처 포함)

### [x] 19. 운영 정책·컴플라이언스
- [x] 외부 타깃 공격 금지, 내부 샌드박스 범위, SBOM 생성·서명 정책 문서화
- [x] 산출: `docs/policies/usage_and_compliance.md`

### [x] 20. CI/CD 및 재현성 검증
- [x] 이미지 다이제스트 고정, SBOM 생성 확인, deterministic 모드 재현 테스트
- [x] 산출: `ops/ci/pipeline.md`

### [x] 21. 리포팅·산출물 표준화
- [x] 재현 리포트 템플릿(로그/해시/모델·프롬프트·시드/RAG 스냅샷 ID 포함)
- [x] 산출: `docs/reporting/reproducibility_report_template.md`

### [x] 22. 문서·기록 운영
- [x] 모든 설계·결정·실험 기록은 `docs/`에 저장(본 TODO에는 일정을 포함하되, 상세 내용은 `docs/`)
- [x] 실험 노트북은 `experiments/`에 생성·버전 관리, 주요 결과를 `docs/experiments/`에 요약 (문서화: `docs/README.md`, `experiments/README.md`)

### 참고: 작업 원칙
- 코드는 최소 변경·명확한 책임 분리·테스트 우선
- 모든 결과는 SID로 식별 가능하게 저장
- 외부 네트워크는 최소 허용, 베이스 이미지는 다이제스트로 고정, SBOM 필수 생성
