# vulDocker 동적화 로드맵 (MoSCoW TODO)

> 문서 목적: **기존 아키텍처(PLAN → GENERATE → EXECUTE → VERIFY → REVIEW → PACK)를 유지**하면서, 남아 있는 하드코딩(실행/검증/분기/기본값/커버리지)을 제거해 **LLM 기반의 “동적 취약 환경 생성 + 동적 검증”**이 지속적으로 확장되도록 로드맵을 제공한다.
>
> 원칙: `docs/`는 참고용이며 **소스 오브 트루스는 코드**다. (특히 `agents/`, `executor/`, `evals/`, `common/`.)

## 범위/비범위

- 유지: 파이프라인 단계 및 메타 저장 구조(SID, `metadata/`, `workspaces/`, `artifacts/`)
- 목표: “레포에 없는 CWE/스택” 입력 시에도 **동적으로 생성/실행/검증까지** 이어지게 만들기
- 비범위(이번 단계): 단계 재명명/분산 실행/외부 배포 자동화/모든 CWE 정적 템플릿 구축

## 현재 상태(코드 기준 체크리스트)

### 동작 중(이미 구현)
- [x] Generator는 `generator_mode`로 `hybrid|synthesis|template`를 지원 (`agents/generator/service.py`)
- [x] Synthesis는 LLM manifest(JSON) → workspace를 동적으로 materialize (`agents/generator/synthesis.py`)
- [x] TemplateRegistry는 `workspaces/templates/` + `metadata/<SID>/runtime_templates/`를 스캔 (`agents/generator/service.py`)
- [x] Rule 기반 verifier 및 JSON/텍스트 혼합 판정 지원 (`evals/poc_verifier/rule_based.py`)
- [x] runtime rule 디렉터리(`VULD_RUNTIME_RULE_DIRS`) 지원 및 룰 스캔(`list_rules`) 지원 (`common/rules/__init__.py`)
- [x] Researcher가 `metadata/<SID>/runtime_rules/*.yaml`에 candidate rule 작성 (`agents/researcher/service.py`)
- [x] Generator/Reviewer/Verifier가 `metadata/<SID>/runtime_rules/`를 env에 자동 등록 (`agents/generator/service.py`, `agents/reviewer/service.py`, `evals/poc_verifier/main.py`)

### 남은 하드코딩/리스크(개선 필요)
- [x] Executor base-url/port 하드코딩 제거 및 동적 resolve (`executor/runtime/docker_local.py`)
- [x] 컨테이너 readiness probe의 Python **필수 의존 제거**(다중 `tcp/http/shell` probe 폴백; python은 선택 경로) (`executor/runtime/docker_local.py`)
- [x] PoC 엔트리 `.py` 고정 제거 + non-python 엔트리 대응(allowlist + 기본 인터프리터 폴백) (`executor/runtime/docker_local.py`)
- [x] sidecar alias 사용 시 ephemeral network 정리(`NetworkPool.release()`) (`executor/runtime/docker_local.py`)
- [x] rule 미존재 CWE에서도 VERIFY가 `unsupported`로 끝나지 않게 폴백 추가 (`evals/poc_verifier/rule_based.py`)
- [x] verifier registry의 rule coverage import-time 캐시 제거 (`evals/poc_verifier/registry.py`)
- [x] `load_rule()`이 정적 룰에 고정되던 문제를 수정해 runtime rule override + env 기반 캐시 무효화를 적용 (`common/rules/__init__.py`)
- [x] Synthesis의 `poc.flag_token` 강제 덮어쓰기 제거(룰/런타임 없으면 주입하지 않음) (`agents/generator/synthesis.py`)
- [x] LLM 호출 실패(네트워크/엔드포인트 장애) 시 stub로 graceful fallback(Researcher/Synthesis) (`common/llm/provider.py`)
- [x] Synthesis dep-guard가 stdlib import를 외부 deps로 오판하지 않도록 필터링 (`agents/generator/synthesis.py`)
- [x] Researcher candidate rule/template 생성의 CWE-89/352 하드코딩 제거(verification_spec/스캔 기반) (`agents/researcher/service.py`)
- [x] Template mode PoC scaffold의 CWE별 endpoint 하드코딩 제거(서비스 엔트리 스캔 기반 추론) (`agents/generator/service.py`)
- [ ] 기본 rule/template/hints 커버리지가 CWE-89/352 중심으로 편중 (`docs/evals/rules/`, `workspaces/templates/`, `rag/hints/`)

---

## MoSCoW TODO Checklist

> 표기: `[x]` 완료 / `[ ]` 미완료(Backlog)

### MUST (필수 — 새 CWE 입력에도 end-to-end가 깨지지 않게)

#### Contract/데이터 흐름 정렬
- [x] **RuleSpec/runtime을 stage 간 공통 계약**으로 고정하고(Generator/Executor/Verifier가 동일 해석), “어디서 생성되든 동일하게 소비”되도록 우선순위 규칙을 명문화한다.
  - [x] 우선순위: `runtime rule` > `static rule` > `generator manifest` > `defaults` (`common/rules/__init__.py`, `evals/poc_verifier/rule_based.py`)
  - [x] 계약(시그니처/FLAG/출력): `success_signature/flag_token`, `output(json|text)`를 runtime rule로 override 가능하게 통일 (`common/rules/__init__.py`)
  - [x] 계약(엔트리/포트): `service_entry(base_url/port)`, `poc_entry(cmd)`의 “결정/저장/소비”를 1곳에서 결정하도록 추가 정리

#### VERIFY (취약점 검증의 동적화)
- [x] rule 미존재 시 `unsupported`로 끝나지 않게 폴백을 제공한다.
  - [x] 옵션 A: `generator_manifest.json`의 PoC 계약(`poc.success_signature/flag_token`)으로 임시 룰을 구성해 검증
  - [x] 옵션 B: verifier-side에서 runtime rule을 생성(또는 Researcher 트리거)한 뒤 재시도(루프 피드백 포함)
- [x] `evals/poc_verifier/registry.py`의 `_RULE_IDS` import-time 캐시를 제거/갱신해 runtime rule 등록 이후에도 `rule_known`이 정확하도록 한다.
- [x] unknown CWE의 “기본 토큰/시그니처”를 Generator/Researcher/Verifier 간에 일치시키고(예: `FLAG-auto-token` vs “미주입/미요구”), 소스가 다른 경우에도 1곳에서 결정되도록 한다.

#### EXECUTE (실행기 하드코딩 제거)
- [x] `executor/runtime/docker_local.py`의 base-url/port 하드코딩을 제거하고 아래 소스에서 동적으로 resolve한다.
  - [x] 템플릿 메타(`template.json`/`generator_template.json`) 또는 generator manifest(`generator_manifest.json`)에서 port를 읽어 base-url 구성
  - [x] multi-vuln(slug)도 번들별 포트/엔드포인트 지원
- [x] PoC 실행 진입점을 `poc_entry`/`poc.cmd` 기반으로 전환한다(Template/Synthesis 공통).
- [x] 컨테이너 readiness probe를 다중 전략(`tcp/http/shell`)으로 확장해 Python이 없는 이미지에서도 동작하게 한다.
- [x] sidecar alias 사용 시 생성되는 ephemeral network를 실행 종료 시 정리한다.
- [x] 컨테이너가 즉시 크래시해도 로그를 수집할 수 있게 main 컨테이너의 `--rm` 의존을 제거하고(수동 cleanup), 실패 시 `docker logs` 근거를 남긴다.

#### ORCHESTRATE (E2E 루프 — EXECUTE/VERIFY 실패의 자동 수렴)
- [x] GENERATE 이후 단계(EXECUTE/VERIFY/REVIEW)에서 실패해도 “즉시 중단”하지 않고, `LoopController` + Reflexion memory를 통해 **재합성 루프**로 수렴시킨다.
  - [x] `orchestrator/run_pipeline.py` 추가: RESEARCH → GENERATE → EXECUTE(build/run) → VERIFY → REVIEW → PACK를 loop로 실행
  - [x] EXECUTOR/VERIFY 실패 시 `LoopController.record_failure(stage=...)`로 실패 맥락을 저장하고 다음 synthesis 프롬프트에 주입되게 한다(`rag/memories/*`).
  - [x] CI 엔트리(`ops/ci/run_case.sh`)는 위 pipeline runner를 호출해 실패 시에도 PACK/요약 출력이 남게 한다.

#### GENERATE (LLM 기반 동적 생성 일관성)
- [x] `agents/generator/synthesis.py`의 `_normalize_poc_template`를 수정해, rule/runtime이 없을 때는 `poc.flag_token`을 주입하지 않고(또는 사용자/룰 제공값만 사용) 계약 불일치를 줄인다.
- [x] synthesis 프롬프트에 Researcher report(JSON)를 주입해 “레포에 없는 CWE”도 템플릿 없이 합성할 수 있게 한다 (`common/prompts/templates.py`, `agents/generator/service.py`)
- [x] 정적 룰이 있는 CWE는 Researcher의 `verification_spec`이 기본 계약을 덮어쓰지 않게 차단하고(필요 시 `override_static=true`), runtime rule의 `patterns`로 템플릿-특정 제약을 제거한다 (`agents/researcher/service.py`)
- [x] RAG snapshot ID가 잘못되거나 누락된 경우 `mvp-sample`로 폴백해 빈 컨텍스트로 인한 합성 실패를 줄인다 (`rag/static_loader.py`)
- [x] success_signature/flag_token을 RuleSpec/manifest로 결정하고, PoC가 동일 값을 출력하도록 scaffold/가드를 강화한다.
- [x] Template mode PoC scaffold의 CWE별 endpoint 하드코딩(`DEFAULT_TEMPLATE_ENDPOINTS`)을 제거하고 서비스 엔트리 스캔 기반으로 일반화한다.
- [x] Synthesis fallback PoC의 CWE별 endpoint 하드코딩(`FALLBACK_POC_ENDPOINTS`)을 제거하고 서비스 엔트리 기반 추론으로 일반화한다.
- [x] SQLi 전용 static signal(후보 스코어링)을 vuln별 플러그인 구조로 확장한다.
- [x] 서비스 구조 템플릿에 의존하지 않되, 반복적인 런타임 보일러플레이트(DB init/경로/제약)를 stack-level 힌트로 제공해 합성 안정성을 높인다(`rag/boilerplate/*`, `rag/static_loader.py`, `agents/generator/service.py`).

#### TEST/REPRO (문서/테스트 정합)
- [x] “레포에 없는 CWE” 입력 케이스에 대한 e2e 테스트를 추가한다(Researcher → Generator → Executor → Verifier).
- [x] static rule이 존재해도 runtime rule이 override 되는지(캐시 포함) 회귀 테스트를 추가한다 (`tests/test_runtime_rules.py`)

### SHOULD (권장 — 커버리지/운영성/재현성 확대)
- [ ] runtime_rules v2 스키마를 기준으로 `docs/evals/rules/*.yaml`(legacy) 마이그레이션 플랜을 운영한다(호환 유지).
- [ ] 성공한 synthesis 결과를 재사용 가능한 템플릿으로 승격(promote)하는 경로를 추가한다(`runtime_templates` → `workspaces/templates` 승격 정책 포함).
- [ ] `rag/hints/` 커버리지를 CWE-89 중심에서 확장(CWE-352 + 우선순위 CWE)하고, stack별 힌트 분리를 도입한다.
- [ ] LLM provider 설정을 OpenAI 단일 섹션 의존에서 확장(stage별 모델/endpoint/키)하되, 비밀정보 노출 방지 정책을 포함한다.
- [x] metadata에 “해석된 RuleSpec/선택된 template/source(정적/런타임/매니페스트)”를 저장해 디버깅 비용을 낮춘다.

### COULD (선택 — 실험/고도화)
- [ ] rule 없는 케이스에서 LLM-assisted verifier를 정책 기반으로 default-on(오프라인 스텁 시 graceful skip 포함).
- [ ] 다중 컨테이너 스택(db/redis 등) 지원(docker compose 또는 sidecar + network whitelist + healthcheck).
- [ ] 자동 메타모픽 테스트(입력 변형, 회귀) 및 “부분 성공/불완전” 등급화.

### WON'T (이번 범위 제외)
- [ ] 파이프라인 단계/아키텍처 대규모 개편(새 스케줄러/분산 실행 등)
- [ ] 외부 인터넷에 노출되는 형태의 실행/배포 자동화
- [ ] 모든 CWE에 대한 정적 템플릿 사전 구축(LLM 없이)

---

## 수정 후보 파일(Quick Map)

- Generator: `agents/generator/service.py`, `agents/generator/synthesis.py`
- Researcher: `agents/researcher/service.py`
- Executor: `executor/runtime/docker_local.py`
- Verifier: `evals/poc_verifier/main.py`, `evals/poc_verifier/registry.py`, `evals/poc_verifier/rule_based.py`
- Rules/Templates/Hints: `docs/evals/rules/`, `workspaces/templates/`, `rag/hints/`
- Tests/E2E: `tests/test_runtime_rules.py`, `evals/poc_verifier/tests/test_rule_based.py`, `tests/e2e/*`

## 검증 방법(로컬)

> 실행 환경은 `conda`의 `vul` 환경을 권장(또는 동등한 Python 3.11 환경). Docker(rootless 권장)는 별도 필요.

1) PLAN: `python orchestrator/plan.py --input <requirement.yml>`
2) (권장) RESEARCH: `python agents/researcher/main.py --sid <SID> --mode deterministic`
3) GENERATE: `python agents/generator/main.py --sid <SID> --mode deterministic`
4) EXECUTE: `python executor/runtime/docker_local.py --sid <SID> --build --run`
5) VERIFY: `python evals/poc_verifier/main.py --sid <SID>`

**완료 기준(예시)**  
- “레포에 없는 CWE”에서도 `artifacts/<SID>/reports/evals.json`이 `unsupported`가 아닌 `evaluated`로 종료되고, evidence가 남는다.
