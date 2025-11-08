# TODO 13~15 코드 구현안

본 문서는 `implement_plan/prompt.md`, `implement_plan/TODO.md`, `docs/milestones/mvp_runbook.md`, `docs/milestones/roadmap.md`를 기반으로 TODO 13~15 단계의 **코드 단위 구현 계획**을 정리한다. 기존 아키텍처·스키마·운영 문서(`docs/architecture/*`, `docs/variability_repro/design.md`, `docs/decoding/model_and_decoding_strategy.md`, `docs/executor/*`, `docs/evals/specs.md`, `docs/ops/*`)와의 정합성을 교차 검증하였다.

---

## 0. 공통 설계 원칙 및 참조
- 상태 기계/트레이싱: `docs/architecture/orchestration_and_tracing.md`
- 에이전트 계약: `docs/architecture/agents_contracts.md`
- 메타스토어·SID: `docs/architecture/metastore_and_artifacts.md`
- 모델·디코딩·Variation: `docs/decoding/model_and_decoding_strategy.md`, `docs/variability_repro/design.md`
- 보안/실행기/게이트: `docs/executor/security_policies.md`, `docs/executor/sbom_guideline.md`, `docs/ops/security_gates.md`
- 검증/평가/리포트: `docs/evals/specs.md`, `docs/reporting/reproducibility_report_template.md`
- KPI/관측성: `docs/ops/observability.md`, `ops/observability/dashboard_spec.md`

---

## 1. TODO 13 – MVP 구현(실제 LLM 적용)
목표: 단일 LLM + 정적 RAG + 로컬 Docker 실행기로 생성→검증→수정 루프 1회 성공 (`docs/milestones/mvp_runbook.md` 기준). LLM 호출은 실제 API(`litellm` → OpenAI GPT-4.1 mini 또는 동급)로 수행한다.

### 1.1 코드 작업 목록
| 경로 | 작업 내용 | 주요 의존 문서 |
| --- | --- | --- |
| `common/llm/provider.py` | `litellm` 래퍼 클래스 구현. `LLMClient(model_name, decoding_mode)`가 `docs/decoding/model_and_decoding_strategy.md`의 재현 모드 파라미터(`temperature=0`, `top_p=1`)를 자동 적용. API 키는 `VUL_LLM_API_KEY` 환경 변수, 호출 로그는 OTEL Span에 첨부. | decoding 전략, ops/observability |
| `common/prompts/templates.py` | Generator/Reviewer용 기본 프롬프트 템플릿과 시스템 규약 정의. prompt hash 계산 유틸 포함 → `metadata/sid.py`에서 사용. | requirements/goal_and_outputs, agents_contracts |
| `orchestrator/state_machine/mvp.py` | PLAN→PACK 최소 상태 전이 로직. `docs/architecture/orchestration_and_tracing.md`의 가드 조건을 코드화하고, OTEL TraceId 생성. | orchestration |
| `orchestrator/plan.py` | 요구 입력 파싱(`inputs/mvp_sqli.yml`), Scenario ID 계산(`docs/variability_repro/design.md` 공식). 결과를 `metadata/sid-mvp-sqli-0001/plan.json`에 저장. | metastore & variability |
| `agents/generator/main.py` | LLM 호출 → 코드/Dockerfile/PoC 파일 생성. RAG 정적 스냅샷(`rag/corpus/processed/mvp-sample`)을 메모리 로더(`rag/static_loader.py`)로 주입. self-consistency 비활성화. 출력은 `workspaces/<SID>/app/` 하위에 기록. | RAG 설계, agents_contracts |
| `agents/reviewer/main.py` | 1차 MVP에서는 Generator와 동일 모델을 사용하지만, Reviewer 스키마(JSON Lines) 생성해 로그/코드 검증. 실패 시 `orchestrator`로 LOOP 신호 반환. | agents_contracts, evals/specs |
| `executor/runtime/docker_local.py` | Docker rootless 실행, `docs/executor/security_policies.md`의 read-only, network none, SBOM 생성(syft) 절차 구현. | executor/security, sbom_guideline |
| `evals/poc_verifier/mvp_sqli.py` | 로그에서 `SQLi SUCCESS` 패턴 탐지 + 메타모픽 입력 1종 적용. 검증 결과를 `artifacts/<SID>/reports/evals.json`에 저장. | docs/evals/specs.md |
| `experiments/01_mvp_sqli_loop.ipynb` | 노트북에서 실제 LLM 호출 경로를 재현. Scenario ID, 모델 버전, prompt hash를 첫 셀에 기록(`docs/README.md` 규칙). | docs/experiments/ |

### 1.2 LLM 적용 세부
```python
# common/llm/provider.py
from litellm import acompletion

class LLMClient:
    def __init__(self, model: str, decoding: dict, tracer):
        self.model = model
        self.decoding = decoding
        self.tracer = tracer

    async def generate(self, messages, tools=None):
        span = self.tracer.start_span("generator.llm")
        resp = await acompletion(
            model=self.model,
            messages=messages,
            temperature=self.decoding["temperature"],
            top_p=self.decoding["top_p"],
            extra_headers={"sid": messages[0]["content"]["sid"]},
            tools=tools,
        )
        span.set_attribute("usage_tokens", resp.usage.total_tokens)
        span.end()
        return resp.choices[0].message["content"]
```
- 모델/디코딩 파라미터는 `common/config/decoding.py`에 상수로 정의해 `docs/decoding/model_and_decoding_strategy.md`와 동기화.
- Generator 프롬프트는 `docs/architecture/agents_contracts.md`의 출력 JSON 요구를 준수하도록 시스템 메시지에 스키마 링크를 포함.

### 1.3 실행 플로우 (코드→런북 맵핑)
1. `python orchestrator/plan.py --input inputs/mvp_sqli.yml`
2. `python agents/generator/main.py --sid sid-mvp-sqli-0001 --mode deterministic`
3. `python executor/runtime/docker_local.py --sid sid-mvp-sqli-0001 --build`
4. `python evals/poc_verifier/mvp_sqli.py --sid sid-mvp-sqli-0001 --log artifacts/.../run.log`
5. `python orchestrator/pack.py --sid sid-mvp-sqli-0001`

각 단계는 `docs/milestones/mvp_runbook.md`와 동일한 명령 시퀀스를 사용하며, TraceId/SpanId는 `docs/ops/observability.md` 규약에 따라 수집한다.

### 1.4 산출물 및 검증
- `artifacts/sid-mvp-sqli-0001/` 구조는 `docs/architecture/metastore_and_artifacts.md`의 `build/`, `run/`, `reports/`, `metadata.json` 규칙을 따른다.
- 재현 리포트는 `docs/reporting/reproducibility_report_template.md` 필드를 채워 `reports/repro.md`로 저장.
- KPI(성공률 1건 확보, 재현 모드 성공)는 `ops/observability/dashboard_spec.md`에서 정의한 수집 파이프라인으로 push.

### 1.5 구현 상태 (2025-11-08)
- `orchestrator/plan.py`, `agents/generator/main.py`, `agents/reviewer/main.py`, `executor/runtime/docker_local.py`, `evals/poc_verifier/mvp_sqli.py`가 모두 커밋되었으며, `inputs/mvp_sqli.yml`·`rag/corpus/processed/mvp-sample/` 등 지원 데이터도 포함됨.
- 실제 LLM 호출은 `config/api_keys.ini`(템플릿: `config/api_keys.example.ini`)에 저장된 OpenAI 서비스 키를 `common/config/api_keys.py`에서 로드해 `common/llm/provider.py`가 `OPENAI_API_KEY`로 주입함으로써 활성화되었다. 키가 없으면 기존 fallback(환경 변수/스텁) 로직을 사용.
- Docker 실행기는 rootless + `--network none` 정책을 준수하며, 컨테이너 내부 `poc.py` 실행 로그는 `artifacts/<SID>/run/run.log`로 수집된다. Docker 그룹 권한을 부여한 뒤 BUILD/RUN이 완료되었고, PACK 단계까지 마쳐 `artifacts/sid-e1bd64a0bfb4/`와 `metadata/sid-e1bd64a0bfb4/`가 모두 채워졌다.
- 검증 결과(`artifacts/.../reports/evals.json`)와 Reviewer 보고서(`metadata/.../reviewer_report.json`)가 실 LLM 기반으로 생성되어 TODO 13의 “생성→검증→수정 루프 1회 성공” 조건을 충족했다. Syft 미설치로 SBOM은 건너뛰었으므로 추후 설치 후 재빌드 필요.

---

## 2. TODO 14 – 핵심 안정화
목표: Generator/Reviewer 분리, Docker 격리 강화, DB 연동 SQLi 확대, 실패 케이스 분석·Reflexion 메모리 적용. (`docs/milestones/roadmap.md` 2단계)

### 2.0 진행 현황 (2024-11-06)
- `orchestrator/plan.py`가 Variation Key에 `self_consistency_k`, `pattern_pool_seed`를 자동 포함하고 `loop.max_loops`를 기록하도록 확장했다.
- `rag/memories/reflexion_store.jsonl` + `orchestrator/loop_controller.py` 조합으로 실패 루프 메모리를 JSONL로 적재하고, Reviewer가 차단 시 자동으로 Reflexion 레코드를 남긴다.
- `agents/generator/service.py`는 `workspaces/templates/sqli/*` 패턴 풀(Flask+SQLite, Flask+MySQL)에서 self-consistency 샘플링 후 다수결로 템플릿을 선택하고, 실패 컨텍스트(`rag.memories.latest_failure_context`)를 프롬프트에 주입한다.
- `agents/reviewer/service.py`는 실행 로그/정적 분석을 결합하여 `docs/schemas/reviewer_report.md` 스키마에 맞는 보고서를 생성하고, Loop Controller를 통해 성공/실패를 기록한다.
- `executor/runtime/docker_db.py`는 내부 Docker 네트워크에 DB 컨테이너(MySQL)와 취약 앱을 함께 배치하고, PoC 실행·SBOM 작성·로그 수집을 수행한다.
- SBOM 생성은 `syft packages docker:<image>` → 실패 시 구버전 CLI(`syft docker:<image> -o spdx-json`) 순으로 시도해 `docs/executor/sbom_guideline.md`와 정합성을 맞췄다. 실패 시 경고 후 패키징을 중단하지 않지만, 성공 시 SPDX JSON만 남도록 했다.
- `workspaces/templates/sqli/flask_mysql_union/app/Dockerfile`에서 DB 비밀번호 등 민감 ENV를 제거해 `docs/ops/security_gates.md`의 “SecretsUsedInArgOrEnv” 경고를 해소하고, 실행 시점(`docker run -e ...`) 주입 방식과 일치시켰다.
- `orchestrator/pack.py`는 `metadata/<SID>/loop_state.json`의 `last_result`가 `success`가 될 때까지 PACK을 차단해 `docs/architecture/orchestration_and_tracing.md`의 REVIEW 게이트 요구를 강제한다.
- 교육용(의도적 취약) 시나리오를 위해 `inputs/*.yml`에 `allow_intentional_vuln: true`를 지정하고, PACK 단계에서 `--allow-intentional-vuln` 옵션을 명시하면 Reviewer가 blocking이어도 예외적으로 패키징할 수 있도록 정책 완화 플래그를 추가했다. 해당 예외는 plan.metadata.policy에 기록되어 감사 가능하다.
- `ops/observability/failure_dashboard.json`과 `experiments/02_stabilization_reflexion.ipynb`로 실패율/KPI 시각화, Reflexion 실험 로그 수집 경로를 마련했다.

### 2.1 코드 작업 목록
| 경로 | 작업 내용 | 주요 의존 문서 |
| --- | --- | --- |
| `agents/generator/service.py` | Generator를 마이크로서비스화. 패턴 풀(`workspaces/templates/sqli/*`)을 불러 Variation Key에 따라 템플릿 선택. Self-consistency `k` 인자 추가. | variability_repro/design, decoding |
| `agents/reviewer/service.py` | Reviewer를 독립 프로세스. `docs/schemas/reviewer_report.md`(추가 예정) 준수, Semgrep/정적 분석 결과 병합. | agents_contracts, evals/specs |
| `orchestrator/loop_controller.py` | LOOP 횟수, Reflexion 적용, 실패 로그 축적. 실패 시 `rag/memories/reflexion_store.jsonl`에 기록. | orchestration, rag/design |
| `executor/runtime/docker_db.py` | DB 컨테이너(MySQL/PostgreSQL)와 취약 앱 컨테이너를 docker network로 묶는 실행기. 정책은 `docs/executor/security_policies.md`의 rootless + netpolicy 적용. | executor/security |
| `rag/memories/` | Reflexion 메모리 저장소. 실패 로그 → RAG 입력(`failure_context`)으로 재사용. | rag/design |
| `ops/observability/failure_dashboard.json` | 실패 케이스 시계열 + 개선율을 노출하는 Grafana 패널. | ops/observability |
| `experiments/02_stabilization_reflexion.ipynb` | Reflexion 적용 전/후 성공률 비교. 결과 요약은 `docs/experiments/`에 기록. | docs/README.md |

### 2.2 동작 흐름
1. PLAN 단계에서 Variation Key에 self-consistency 파라미터(`k`, `pattern_pool_seed`)를 포함.
2. Generator는 템플릿을 기반으로 `k`개의 후보를 생성 후 다수결(또는 Reviewer prior)로 선택.
3. Reviewer는 Executor 로그 + 정적 분석 결과를 결합하여 JSON 레포트를 생성, severity에 따라 LOOP 조건 판단.
4. 실패 시 Reflexion 메모리에 `{sid, failure_reason, remediation_hint}` 저장 → 다음 DRAFT에서 프롬프트에 삽입.
5. Executor는 DB 컨테이너 health-check, SBOM 자동 생성, security gate hook을 수행.

### 2.3 지표 및 보고
- PoC 성공률 ≥ 60%, 평균 루프 ≤ 3, 보안 위반 0 (`docs/milestones/roadmap.md` 지표).
- KPI는 `metadata/kpi/stabilization.jsonl`로 적재하여 Grafana에서 시각화.
- 성공률·루프 수 개선 리포트는 `docs/milestones/roadmap.md`에 링크되는 Markdown(`docs/milestones/stabilization_report.md`)으로 생성.

---

## 2.5. TODO 14.5 – 합성(LLM) 기반 ‘템플릿 없는’ 유동적 취약 Docker 생성
목표: 템플릿 파일 전개 없이 LLM이 코드/도커/PoC 번들을 직접 합성하여 교육용 취약 이미지를 생성. TODO 15(외부 RAG) 전 단계로 내부 힌트 기반으로 품질을 안정화.

### 14.5.1 코드 작업 목록
| 경로 | 작업 내용 | 주요 의존 문서 |
| --- | --- | --- |
| `agents/generator/synthesis.py` (신규) | 합성 엔진 구현: LLM 출력(JSON 매니페스트) 검증·가드(경로/확장자/크기), 후보 k개 점수화/선택, 머티리얼라이즈, 메타 기록 | agents_contracts, variability_repro/design |
| `common/prompts/templates.py` | 합성 전용 프롬프트 `build_synthesis_prompt()` 추가(출력 스키마 엄수, 필수 파일/PoC/시グ니처 포함) | prompt.md, schemas |
| `agents/generator/service.py` | `generator_mode: synthesis|hybrid|template` 분기. synthesis/hybrid 결과를 `metadata/<SID>/generator_manifest.json`, `generator_candidates.json`으로 기록 | agents_contracts |
| `rag/static_loader.py` + `rag/hints/cwe-89/*.md` (신규) | 내부 힌트 로딩(`load_hints(CWE, stack)`), 합성 프롬프트에 주입(14.5 단계), 15에서 외부 RAG로 대체 | rag/design |
| `evals/static_signatures/sqli.py` (신규) | 합성 후보 정적 스크리닝(문자열 조합/UNION SELECT 등 시グ니처), Reviewer 보조 | evals/specs |
| `docs/schemas/generator_manifest.md` (신규) | 합성 출력 스키마 정의: files[], deps[], build/run, poc{cmd, success_signature}, notes/pattern_tags[] | schemas/* |

### 14.5.2 동작 흐름
1. PLAN: 요구에 `generator_mode: synthesis`, `synthesis_limits{max_files, max_bytes_per_file, allowlist[]}`, `allow_intentional_vuln`(교육용)을 명시 → `plan.json`에 반영.
2. DRAFT(합성): 합성 프롬프트에 Requirement+내부 힌트+Reflexion 실패맥락+Variation Key를 포함하여 k개 매니페스트 샘플 → 스키마/가드/정적 시그니처 검증 → 점수화 다수결 → 1개 채택 → 워크스페이스에 파일 기록.
3. BUILD/RUN: 기존 실행기(`executor/runtime/docker_db.py`)로 빌드, Anchore Syft 1.x로 SPDX SBOM 생성, 내부 네트워크에서 DB+앱 실행, 로그 수집.
4. VERIFY: `evals/poc_verifier/mvp_sqli.py`로 `SQLi SUCCESS` 시グ니처 판정.
5. REVIEW: 로그+정적 분석 병합, blocking이면 Reflexion 메모리(JSONL) 기록 → 다음 합성 루프에 `failure_context`로 주입.
6. PACK: 기본은 Reviewer 차단 시 금지. 교육용은 요구의 정책 플래그(true) + `--allow-intentional-vuln` CLI가 동시에 있을 때 예외 허용(감사 로그 남김).

### 14.5.3 가드/정책
- 허용 경로 화이트리스트(기본: `Dockerfile, app.py, requirements.txt, poc.py, schema.sql, README.md`), 확장자/바이트 상한(예: 12개/≤64KB) 적용.
- 금지 토큰 블록리스트(역쉘, `rm -rf`, 외부 네트워크 호출 등) 필터.
- 의존 고정(핀 버전), 내부 네트워크 격리, SBOM 필수 생성(`docs/executor/sbom_guideline.md`).
- 정책 게이트: Reviewer 차단 시 PACK 금지. 교육용 예외는 `plan.policy.allow_intentional_vuln=true`+`--allow-intentional-vuln` 동시 충족 시에만 허용.

### 14.5.4 지표/검증 및 수용 기준
- 합성만으로 빌드/실행/PoC 성공(템플릿 디렉토리 미사용) → `evals.json.verify_pass=true`.
- SPDX SBOM 생성 성공(`artifacts/<SID>/build/sbom.spdx.json`).
- Reviewer 보고서 존재 및 Reflexion 루프 동작. 재현 모드에서 동일 입력/시드로 동일 manifest hash/SID 산출.
- 템플릿 의존도 0% (합성 모드): 전개 파일이 모두 합성 매니페스트에서 기인함을 `generator_manifest.json`으로 증명.

### 14.5.5 정합성 체크
- `prompt.md`: 합성 지침/출력 스키마 엄수, 에이전트 계약 준수.
- `docs/variability_repro/design.md`: Variation Key/시드/self-consistency 반영.
- `docs/executor/security_policies.md`, `docs/executor/sbom_guideline.md`, `docs/ops/security_gates.md`: 실행 격리·SBOM·보안 게이트 일치.
- `docs/architecture/agents_contracts.md`: Generator/Reviewer/Executor 계약 항목 충족.

### 14.5.6 사용 예시(교육용 허용)
```
generator_mode: synthesis
allow_intentional_vuln: true
synthesis_limits:
  max_files: 12
  max_bytes_per_file: 64000
```
명령: PLAN → DRAFT(합성) → BUILD/RUN → VERIFY → REVIEW → PACK(`--allow-intentional-vuln`).

---

## 3. TODO 15 – 고도화
목표: Researcher 도입, 외부 검색+ReAct 연동, 최신 CVE 자가 생성, 다변성 모드(top-p/self-consistency) 도입 및 다양성·재현성 지표 자동 측정.

### 3.1 코드 작업 목록
| 경로 | 작업 내용 | 주요 의존 문서 |
| --- | --- | --- |
| `agents/researcher/main.py` | ReAct 스타일 툴 체인, 외부 검색 모듈(`rag/tools/web_search.py`)과 연동. 결과는 `docs/schemas/researcher_report.md` JSON 출력. | agents_contracts, rag/design |
| `rag/ingest/cve_feed.py` | NVD/CISA RSS → `rag/corpus/raw/poc/`로 수집, 스냅샷(`rag/index/rag-snap-YYYYMMDD`) 자동 갱신. | rag/snapshots, rag/corpus_guide |
| `orchestrator/plugins/react_loop.py` | Researcher→Generator→Reviewer→Executor 순환 중 Researcher가 Reflexion 메모리를 읽어 Query 증강. Trace span 이름은 `researcher.react`. | orchestration, ops/observability |
| `common/variability/manager.py` | Variation Key 기반 다변성/재현성 모드 스위치. `docs/variability_repro/design.md`의 SID/variation 정의 적용. | variability_repro/design |
| `evals/diversity_metrics.py` | 샤논 엔트로피, 시나리오 거리, 재현율 계산 후 `artifacts/<SID>/reports/diversity.json`에 저장. 대시보드에 push. | variability_repro/design, ops/observability |
| `experiments/03_diversity_repro_tradeoff.ipynb` | top-p/self-consistency 조합에 따른 품질-다양성 트레이드오프 측정. | docs/README.md |

### 3.2 동작 흐름
1. 신규 요구 수신 시 Researcher가 외부 검색(ReAct)으로 RAG 보고서를 생성, Snapshot ID를 `metadata`에 기록.
2. Variation Manager가 다변성 모드를 활성화하면 Generator/Reviewer의 디코딩 파라미터를 `docs/decoding/model_and_decoding_strategy.md`의 diverse 프로파일로 전환.
3. Scenario 다양성 측정: `evals/diversity_metrics.py`가 패턴 ID 분포, 차원별 해밍 거리, 재현율을 계산.
4. 최신 CVE ingest 후 자동 실행 시나리오를 `ops/ci` 파이프라인에 추가하여 자가 검증.

### 3.3 산출물
- 다양성 지표 리포트(H, 시나리오 거리) + 재현율 리포트는 `docs/milestones/diversity_report.md`로 집계.
- 최신 CVE 성공 사례는 `artifacts/sid-cve-<id>/`에 저장하고, `docs/reporting/reproducibility_report_template.md` 기반 리포트를 자동 생성.

---

## 4. 정합성 검토 요약
- **prompt.md**: 상태 기계, 에이전트 역할, RAG, 다변성/재현성 전략, SBOM·보안 요구 등을 그대로 반영.
- **docs/milestones/mvp_runbook.md & roadmap.md**: 명령 시퀀스·지표를 그대로 참조, 각 단계 산출물 위치 일치.
- **docs/architecture/\***: 오케스트레이션, 에이전트 계약, 메타스토어 규약에 따라 경로/스키마/Trace 규칙을 설계.
- **docs/variability_repro/design.md & docs/decoding/model_and_decoding_strategy.md**: Variation Key, LHS, 디코딩 파라미터 정의를 그대로 코드에 투영.
- **docs/executor/\*** & **docs/ops/security_gates.md**: 실행기 정책, SBOM, 보안 게이트 절차를 TODO 13~15 실행기에 통합.
- **docs/evals/specs.md** & **docs/reporting/reproducibility_report_template.md**: 검증·리포트 산출 형식을 준수하도록 모듈 경로를 명시.

---

## 5. 후속 액션 정리
1. **즉시(13번)**: `common/llm/provider.py`, `orchestrator/state_machine/mvp.py`, `agents/generator/main.py`, `executor/runtime/docker_local.py`, `evals/poc_verifier/mvp_sqli.py`를 구현하고 실 LLM 호출을 검증(노트북 + artifacts).
2. **단기(14번)**: Multi-agent 분리, DB 연동 실행기, Reflexion 메모리, 실패 대시보드를 구축하고 성공률 지표를 수집.
3. **중기(15번)**: Researcher + 외부 검색, Variation Manager, 다양성 지표 계산 파이프라인을 추가하고 최신 CVE 시나리오 실행을 자동화.

위 단계가 완료되면 TODO 13~15의 체크리스트를 코드 차원에서 충족하며, 모든 산출물은 SID 기반으로 `artifacts/`와 `docs/milestones/`에 기록한다.
