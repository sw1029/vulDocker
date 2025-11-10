# 프로젝트 핸드북(통합 문서)

본 문서는 `docs/`에 흩어져 있던 개별 문서의 핵심을 한 곳으로 통합한 단일 가이드입니다. 설계·운영·평가·실행 방법을 일관된 맥락으로 제공합니다. 규칙/스키마/세부 명세는 필수 내용만 요약하며, 예시는 간결히 유지합니다.

## 문서 원칙(요약)
- 비-TODO 기록(설계, 결정사항, 위험·완화, 실험 요약, 운영 정책)은 문서로 남깁니다.
- 코드 리뷰에는 구현 세부를, 문서에는 배경/선택 근거/대안/재현 절차를 기록합니다.
- 경로는 상대 경로를 사용하고, 식별자(SID/TraceId)는 그대로 기입합니다.

## 빠른 시작(실행 가이드)
1) PLAN: `python orchestrator/plan.py --input inputs/mvp_sqli.yml`
   - 산출: `metadata/<SID>/plan.json` (+ 기본 디렉토리)
2) DRAFT: `python agents/generator/main.py --sid <SID> --mode deterministic`
   - 산출: `workspaces/<SID>/app/`, `metadata/<SID>/generator_llm_plan.md`
3) BUILD: `python executor/runtime/docker_local.py --sid <SID> --build`
   - Docker build + SBOM(`artifacts/<SID>/build/`)
4) RUN: `python executor/runtime/docker_local.py --sid <SID> --run`
   - 컨테이너 내부 `python poc.py` 실행(`artifacts/<SID>/run/run.log`)
5) VERIFY: `python evals/poc_verifier/main.py --sid <SID>`
   - `docs/evals/rules/*.yaml`에 정의된 성공 시그니처/FLAG 토큰을 기준으로 자동 평가 → `artifacts/<SID>/reports/evals.json`
6) PACK: `python orchestrator/pack.py --sid <SID>`
   - 스냅샷/메타(`metadata/<SID>/manifest.json`)

LLM API 키, Docker(rootless 권장), Syft(SBOM)는 환경에 맞춰 설정합니다.

## 요구/출력/성공 기준
- 입력 스펙: 취약군(CWE), 스택, 변이키(temperature/top-p/k), RAG 스냅샷, 정책.
- 출력물: workspace, 이미지/SBOM, 로그/트레이스, 평가 결과, 패키징 메타.
- 성공 기준: `docs/evals/rules/*.yaml`에 정의된 성공 시그니처/FLAG 토큰 검출, 보안 위반 0, 재현율 목표 충족.

## 아키텍처(상태·에이전트·메타스토어)
- 상태 전이: PLAN → PACK, 단계별 Span(`plan`, `draft.generator`, `build.executor`, `run.executor`, `verify.pipeline`, `review.reviewer`, `pack.orchestrator`).
- 에이전트 계약: Researcher(검색/RAG 보고서) → Generator(합성/템플릿 보강) → Reviewer(증거/로그 기반 지시) → Executor(격리 실행/요약).
- 메타스토어 & SID: `SID = H(model_ver | prompt_hash | seed | retriever_commit | corpus_snapshot | pattern_id | deps_digest | base_image_digest)` (+옵션 vuln_ids_digest).

## 동적 취약 삽입(LLM+RAG)
- 기본 전략: 합성(synthesis) 우선 + 템플릿 보강(LLM 패치). CWE/DB/패턴 불일치 시 합성으로 전환.
- 증거 일관성: 검증 플러그인 요구(FLAG/서명)와 생성물/PoC 로그를 정렬.
- 실패 맥락: Reflexion 메모리를 다음 프롬프트에 주입하여 수렴.

## RAG 설계·스냅샷
- 코퍼스 층위: 공용(CWE/OWASP/Juliet) / 최신 PoC(CVE/PoC) / 사내(로그/메모).
- 전처리/청킹: 코드(함수/클래스), 서술형(256~512 토큰), 메타(`vuln_id`, `framework`, `db`, `pattern_tag`, `source_url`, `license`).
- 색인/검색: 벡터+키워드, top-k + reranker, Researcher는 ReAct/Reflexion 루프.
- 스냅샷: `rag/index/<snapshot_id>/metadata.json`에 해시/모델/파라미터 기록.

## 실행기 보안·SBOM
- 기본: read-only, `--security-opt no-new-privileges:true`, `--cap-drop=ALL`, `--tmpfs /tmp:rw,noexec,nosuid`.
- 네트워크: 기본 `--network none` + egress 화이트리스트.
- SBOM: Syft로 `sbom.spdx.json` 생성, 정책 게이트와 연계.

## 관측성·보안 게이트
- 트레이싱: OTEL Collector, Trace/Span 규칙 일관.
- 로깅: JSON Lines(`timestamp`, `level`, `trace_id`, `span_id`, `sid`, `component`, `message`).
- 메트릭/대시보드: PoC 성공률/루프 수/다양성/재현율/KPI 알람.

## 디코딩 전략·변이키
- 프로파일: deterministic vs diverse(temperature/top-p/k).
- Variation Key: `{mode, temperature, top_p, self_consistency_k, pattern_pool_seed, ...}` 정규화.

## 평가(Evals)
- PoC 판단/메타모픽 테스트/커버리지 규칙 요약.
- 규칙 파일: `docs/evals/rules/*.yaml` (유지).

## 스키마(요약)
- generator_manifest: `intent`, `pattern_tags[]`, `files[]`, `deps[]`, `build`, `run`, `poc{cmd, success_signature}`, `notes`, `metadata`.
- packaging_metadata: 단계 타임스탬프/버전/스냅샷/이미지/리포트 레퍼런스.
- researcher_report / reviewer_report / executor_result: 각 에이전트 출력 구조.

## 정책·윤리·리포팅·위험
- 정책/사용 제한: 허용 도메인, SBOM 서명/검증, 윤리 규범.
- 리포팅: 재현 리포트 필수 필드(스냅샷/지표/환경/명령/결과 요약).
- 위험 레지스터: 주요 리스크와 완화 액션, 재발 방지 절차.

## 템플릿 예시
- `workspaces/templates/sqli/flask_mysql_union/app/README.md`
- `workspaces/templates/sqli/flask_sqlite_raw/app/README.md`
- `workspaces/templates/csrf/flask_sqlite_csrf/app/README.md`

본 핸드북은 요지 중심으로 유지되며, 변경 시 PR 설명에 본 파일 경로를 명시해 추적 가능성을 확보합니다.

## 코드 디렉토리별 상세 설명
- 인덱스: `docs/code/README.md`
- orchestrator: `docs/code/orchestrator.md`
- common: `docs/code/common.md`
- agents (researcher/generator/reviewer): `docs/code/agents_researcher.md`, `docs/code/agents_generator.md`, `docs/code/agents_reviewer.md`
- executor: `docs/code/executor.md`
- evals: `docs/code/evals.md`
- rag: `docs/code/rag.md`
- ops: `docs/code/ops.md`
- workspaces/metadata/artifacts: `docs/code/workspaces.md`
