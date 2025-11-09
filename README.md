# LLM+RAG 기반 동적 취약 테스트베드 (vulDocker)

본 프로젝트는 LLM+RAG를 활용해 취약 환경을 자동 합성/보강하고, Docker에서 실행·검증·리뷰·패키징까지 파이프라인을 일관되게 수행하는 테스트베드입니다. 실습/연구/회귀 테스트 목적의 재현 가능한 루프를 제공합니다.

- 통합 핸드북: `docs/handbook.md` (설계·운영·평가 전반을 단일 문서로 요약)
- 규칙: `docs/evals/rules/*.yaml`
 - 코드 디렉토리별 상세 설명: `docs/code/README.md`

## 빠른 시작

사전 요구
- Docker (rootless 권장), Python 3.11+, git
- 선택: Syft(SBOM) 설치 시 SBOM 자동 생성

설치
- 가상환경 구성 후 의존성 설치
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -r requirements.txt`

API 키 설정(선택)
- 실제 LLM 호출을 원하면 다음 중 하나로 OpenAI 호환 키를 설정합니다. 미설정 시 결정적 스텁으로 동작합니다.
  - 파일: `config/api_keys.ini`
    ```ini
    [openai]
    api_key = sk-...
    ```
  - 또는 환경변수: `export OPENAI_API_KEY=sk-...` (또는 `VUL_LLM_API_KEY`)

샘플 실행 (SQLi)
1) PLAN
- `python orchestrator/plan.py --input inputs/mvp_sqli.yml`
- 로그에 `Scenario <SID> planned` 출력. `metadata/<SID>/plan.json` 생성.

2) GENERATE
- `python agents/generator/main.py --sid <SID> --mode deterministic`
- 산출: `workspaces/<SID>/app/` (코드/PoC/Dockerfile), `metadata/<SID>/generator_runs.json`

3) EXECUTE (BUILD+RUN)
- `python executor/runtime/docker_local.py --sid <SID> --build --run`
- 산출: `artifacts/<SID>/build/build.log`, `artifacts/<SID>/run/run.log`, SBOM(`sbom.spdx.json`, Syft 설치 시)

4) VERIFY (PoC 판정)
- `python evals/poc_verifier/main.py --sid <SID>`
- 산출: `artifacts/<SID>/reports/evals.json`

5) REVIEW (선택)
- `python agents/reviewer/main.py --sid <SID> --mode deterministic`
- 결과/이슈 요약: `metadata/<SID>/reviewer_reports.json`

6) PACK
- `python orchestrator/pack.py --sid <SID>` (의도된 취약 허용 시 `--allow-intentional-vuln`)
- 산출: `metadata/<SID>/manifest.json`, 소스 스냅샷

기본 점검
- `artifacts/<SID>/run/run.log` 내 `SQLi SUCCESS`와 `FLAG` 문구를 확인합니다.

## 파이프라인 구조(상태/흐름)
- PLAN → GENERATE → EXECUTE → VERIFY → REVIEW → PACK
- Span/로그/아티팩트는 SID 기준으로 분리 저장됩니다. 자세한 설명은 `docs/handbook.md` 참고.

## 코드 흐름(상세)
- 입력(요구): `inputs/*.yml` → PLAN(`orchestrator/plan.py`)
  - 출력: `metadata/<SID>/plan.json`(paths, variation_key, policy, run_matrix)
- Researcher(선택): `agents/researcher/main.py`
  - 출력: `metadata/<SID>/researcher_report.json`
- Generator: `agents/generator/main.py`
  - 입력: plan.json(+실패 맥락/RAG), 모드(deterministic|diverse)
  - 출력: `workspaces/<SID>/app/`(+ 다중 취약 시 서브디렉토리), `metadata/<SID>/generator_runs.json`
- Executor: `executor/runtime/docker_local.py`
  - 동작: Docker build → SBOM(Syft) → 컨테이너 run → PoC 실행
  - 출력: `artifacts/<SID>/build/build.log`, `artifacts/<SID>/build/sbom.spdx.json`, `artifacts/<SID>/run/run.log`, `artifacts/<SID>/run/summary.json`, `artifacts/<SID>/run/index.json`
- Evals: `evals/poc_verifier/main.py`
  - 입력: run/index.json, run.log
  - 출력: `artifacts/<SID>/reports/evals.json`
- Reviewer: `agents/reviewer/main.py`
  - 입력: run.log, plan.json, eval 결과
  - 출력: 번들 리포트(JSON), `metadata/<SID>/reviewer_reports.json`, `metadata/<SID>/loop_state.json`
- PACK: `orchestrator/pack.py`
  - 출력: `metadata/<SID>/manifest.json`, `artifacts/<SID>/build/source_snapshot/`

## 다이어그램
```mermaid
flowchart LR
  A[inputs/*.yml] --> B[PLAN\n(orchestrator/plan.py)\nmetadata/<SID>/plan.json]
  B --> C{Researcher?}
  C -->|report| C1[metadata/<SID>/researcher_report.json]
  B --> D[Generator\n(agents/generator)\nworkspaces/<SID>/..., generator_runs.json]
  D --> E[Executor\n(executor/docker_local.py)\nbuild.log, run.log, index/summary]
  E --> F[Evals\n(evals/poc_verifier)\nreports/evals.json]
  E --> G[Reviewer\n(agents/reviewer)\nreviewer_reports.json, loop_state.json]
  F --> H[PACK\n(orchestrator/pack.py)\nmanifest.json, source_snapshot]
  G --> H
```

ASCII (대안)
```
inputs/*.yml
  │
  ├─ PLAN (orchestrator/plan.py) → metadata/<SID>/plan.json
  │
  ├─(optional) Researcher → metadata/<SID>/researcher_report.json
  │
  ├─ Generator → workspaces/<SID>/** , metadata/<SID>/generator_runs.json
  │
  ├─ Executor (Docker build/run)
  │      └─ artifacts/<SID>/build/build.log, build/sbom.spdx.json
  │      └─ artifacts/<SID>/run/run.log, run/summary.json, run/index.json
  │
  ├─ Evals → artifacts/<SID>/reports/evals.json
  │
  ├─ Reviewer → metadata/<SID>/reviewer_reports.json , metadata/<SID>/loop_state.json
  │
  └─ PACK (orchestrator/pack.py) → metadata/<SID>/manifest.json , artifacts/<SID>/build/source_snapshot/
```

## 코드 논리 구조(핵심 모듈)
- 오케스트레이션
  - `orchestrator/plan.py:1` — 요구 입력을 정규화하여 SID 계산 후 `plan.json` 작성
  - `orchestrator/pack.py:1` — 실행 산출물 수집/스냅샷/`manifest.json` 생성
- 공용 유틸
  - `common/sid.py:1` — SID 필드 해시(`compute_sid`) 정의
  - `common/paths.py:1` — `metadata/`, `workspaces/`, `artifacts/` 경로 규칙
  - `common/run_matrix.py:1` — 단일/다중 취약 번들 처리(슬러그/서브디렉토리)
  - `common/plan.py:1` — `metadata/<SID>/plan.json` 로더
  - `common/variability/manager.py:1` — Variation Key 정규화/디코딩 프로파일
  - `common/config/api_keys.py:1` — `config/api_keys.ini`에서 API 키 로드
  - `common/llm/provider.py:1` — litellm 백엔드/스텁 자동 전환
- Researcher (선택)
  - `agents/researcher/main.py:1`, `agents/researcher/service.py:1` — 검색/RAG 보고서(JSON) 생성
- Generator
  - `agents/generator/main.py:1` — 번들 단위 실행 진입점
  - `agents/generator/service.py:1` — 템플릿 탐색/가용성 판정/합성(hybrid) 모드/가드레일 적용
  - `agents/generator/synthesis.py:1` — 매니페스트 기반 합성 엔진(파일/의존성/제약), 결정적 폴백
  - 템플릿 예시: `workspaces/templates/**/template.json`, `app/`
- Executor
  - `executor/runtime/docker_local.py:1` — Docker build/run, readiness, SBOM(Syft), 보안 옵션(read-only/no-new-privileges/cap-drop)
  - 산출: `build.log`, `run.log`, `summary.json`, `run/index.json`
- Evals/Reviewer
  - `evals/poc_verifier/main.py:1` — 플러그인 레지스트리 기반 검증 집계
  - `evals/poc_verifier/mvp_sqli.py:1` — SQLi 플러그인(서명+FLAG)
  - `agents/reviewer/service.py:1` — 로그/정적 이슈 분석, LLM 피드백, 루프 상태 기록

## CI/스모크 테스트
- 스크립트: `ops/ci/run_case.sh`, `ops/ci/smoke_regression.sh`
- 기본 순서: PLAN → (Researcher) → Generator → Executor → Evals → Reviewer → Pack

## 트러블슈팅
- LLM 키 없음: `OPENAI_API_KEY`/`config/api_keys.ini`가 없거나 litellm 미설치 시 자동 스텁 동작(결정적 출력). 실제 호출엔 키/패키지 설치 필요.
- Docker 권한: 사용자 그룹/소켓 접근 권한 확인. rootless 권장.
- Syft 경고: 미설치 시 SBOM 생략(경고 로그).

## 라이선스/보안
- PoC/취약 환경은 격리된 로컬 Docker에서만 사용하세요. 외부 네트워크 접근은 기본 비활성화(`--network none`).

자세한 내용은 통합 핸드북을 참고하세요: `docs/handbook.md`.
