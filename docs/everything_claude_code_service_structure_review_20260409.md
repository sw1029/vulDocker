# Everything-Claude-Code Service Structure Review

작성일: 2026-04-09

## 1. 목적과 결론

이 문서는 레포 내 별도 구현인 `everything-claude-code`의 서비스 구조를 분석하고, 현재 레포의 `harness / runtime_graph / evidence_graph / staged_synthesis / measured gate` 관점에서 로직 적용 가능성을 검토한 보고서다.

핵심 결론은 다음이다.

- `everything-claude-code`는 단일 실행 서비스라기보다 `cross-harness performance system`이다.
- 이 레포의 중심은 앱 로직이 아니라 `install graph`, `hook graph`, `session adapter graph`, `deterministic audit`, `operator-facing control plane`이다.
- 현재 레포에 직접 도움이 되는 것은 대형 skill catalog 자체가 아니라:
  1. deterministic harness audit
  2. declarative hook/event gate
  3. canonical session/run snapshot normalization
  4. observation/state-store 기반 성능 보정
  5. verification/eval workflow formalization

반대로 우선순위가 낮거나 현재 레포와 맞지 않는 것은:

1. cross-harness install/profile packaging
2. 대규모 agent/skill/command 카탈로그
3. tmux 기반 operator workspace 전체
4. ECC2 TUI 자체의 도입

한 줄로 요약하면:

> `everything-claude-code`에서 가져와야 할 것은 “더 많은 프롬프트 자산”이 아니라, 하네스 성능을 별도 계층으로 다루는 방식, 즉 `audit/gate/recording/control-plane` 분리 구조다.

## 2. 이 저장소가 실제로 무엇인가

`everything-claude-code`는 일반 애플리케이션 코드베이스와 다르다.

`README.md` 기준 정체성:

- “The performance optimization system for AI agent harnesses”
- Claude Code, Codex, Cursor, OpenCode, Gemini 등 여러 하네스를 지원
- agents / skills / commands / hooks / rules / MCP configs / session infrastructure / ECC2 alpha control plane 포함

즉 이 레포는 특정 비즈니스 로직을 실행하는 서비스가 아니라:

- 하네스 실행 품질
- 세션 지속성
- 도구 사용 가드레일
- 검증 루프
- operator workflow

를 별도 제품 계층으로 구축한 시스템이다.

이 점이 현재 레포와의 가장 큰 차이다.

- 현재 레포는 취약 Docker 생성 파이프라인이 핵심이다.
- `everything-claude-code`는 “그런 파이프라인을 운영하는 하네스” 자체를 최적화하는 데 초점이 있다.

## 3. 서비스 구조 분해

### 3.1 Layer 1: 배포/설치 계층

핵심 파일:

- `package.json`
- `scripts/install-plan.js`
- `scripts/install-apply.js`
- `manifests/install-components.json`
- `manifests/install-modules.json`
- `manifests/install-profiles.json`

이 레이어는 명시적인 설치 그래프를 갖는다.

- `profile -> component -> module -> target` 구조
- 예:
  - `profile=developer`
  - `components=baseline:* + orchestration + workflow-quality + framework-language`
  - `modules=hooks-runtime, workflow-quality, orchestration ...`
  - `targets=claude, cursor, codex, opencode ...`

즉 단순 복사 스크립트가 아니라, `manifest-driven install graph`로 동작한다.

이 구조의 장점:

- 기능 묶음을 프로파일 단위로 선택 가능
- 대상 하네스별로 설치 surface 차등 적용
- “무엇이 설치되었는지”를 설치 상태로 추적 가능

현재 레포와 직접 맞닿는 부분은 크지 않지만, “control-plane artifact를 명시적 모듈 그래프로 다룬다”는 점은 참고할 가치가 있다.

### 3.2 Layer 2: 실행 표면 계층

이 레포의 사용자-facing surface는 네 가지다.

- `agents/`
- `skills/`
- `commands/`
- `hooks/`

여기서 진짜 실행력은 `commands + hooks + scripts/lib/*`에서 나온다.

`skills`와 `agents`는 대부분 지식/워크플로우 자산이고, `hooks`와 `scripts`가 이를 운영 가능한 시스템으로 만든다.

즉 구조적으로는:

- declarative surface:
  - markdown agents
  - markdown skills
  - markdown commands
- imperative substrate:
  - Node scripts
  - hook runner
  - session/state store
  - audit/scoring engine

### 3.3 Layer 3: Hook Graph

핵심 파일:

- `hooks/hooks.json`
- `scripts/hooks/run-with-flags.js`
- `scripts/lib/hook-flags.js`
- `scripts/hooks/quality-gate.js`
- `scripts/hooks/session-end.js`

이 레포에서 가장 중요한 “tool graph”에 가까운 것은 사실상 `hook event graph`다.

이벤트 축:

- `PreToolUse`
- `PreCompact`
- `SessionStart`
- `PostToolUse`
- `PostToolUseFailure`
- `Stop`

실행 특징:

- 각 hook는 `matcher + command + profile`로 선언된다.
- `ECC_HOOK_PROFILE=minimal|standard|strict`
- `ECC_DISABLED_HOOKS=...`
- `run-with-flags.js`가 실제 hook enable/disable과 direct require/spawn fallback을 처리

즉 이것은 단순한 pre-commit 훅 모음이 아니라:

- event-driven gate system
- runtime strictness switching
- 공통 runner를 통한 안정적 hook 실행

이다.

이 구조에서 중요한 포인트는 두 가지다.

1. gate가 선언적이다.
2. strictness를 환경 플래그로 조정할 수 있다.

현재 레포의 `strict_dynamic`, measured gate, support gate와 매우 잘 대응된다.

### 3.4 Layer 4: Deterministic Harness Audit

핵심 파일:

- `commands/harness-audit.md`
- `scripts/harness-audit.js`

이 레이어는 현재 repo와 비교했을 때 가장 직접적으로 응용 가치가 높다.

`harness-audit.js`는 고정된 7개 카테고리로 점수화한다.

- Tool Coverage
- Context Efficiency
- Quality Gates
- Memory Persistence
- Eval Coverage
- Security Guardrails
- Cost Efficiency

특징:

- 같은 커밋이면 재현 가능한 deterministic score
- file/rule 기반 check
- top actions를 자동 제시
- text/json output contract 존재

중요한 점은 이 점수체계가 “실제 task 성공률”을 직접 대체하지는 않지만, 하네스 품질을 별도 지표로 분리해서 다룬다는 것이다.

현재 레포에 매우 적합한 아이디어다.

### 3.5 Layer 5: Session Adapter / Canonical Snapshot

핵심 파일:

- `docs/ECC-2.0-SESSION-ADAPTER-DISCOVERY.md`
- `scripts/lib/orchestration-session.js`
- `scripts/lib/session-adapters/registry.js`
- `scripts/lib/session-adapters/canonical-session.js`
- `scripts/lib/session-adapters/dmux-tmux.js`
- `scripts/lib/session-adapters/claude-history.js`
- `scripts/session-inspect.js`
- `commands/sessions.md`
- `scripts/lib/session-manager.js`

여기서의 핵심은 “다른 세션 소스들을 공통 canonical snapshot으로 정규화한다”는 점이다.

정규화 대상:

- tmux/worktree orchestration session
- Claude local session history
- 이후 Codex/OpenCode 등 확장 가능

canonical snapshot schema:

- `schemaVersion`
- `adapterId`
- `session`
- `workers`
- `aggregates`

구조적 의미:

- runtime source가 달라도 operator는 같은 구조로 읽을 수 있다.
- raw session detail과 operator-facing read model을 분리한다.

현재 레포는 direct run, repeatability run, support review, bundle summary, pack manifest가 각각 다른 파일 surface를 갖는다. 이를 operator-facing canonical snapshot으로 다시 묶는 작업에 직접 참고할 수 있다.

### 3.6 Layer 6: Observation / State Store / Continuous Improvement

핵심 파일:

- `scripts/lib/state-store/*`
- `scripts/lib/skill-improvement/observations.js`
- `scripts/lib/skill-improvement/health.js`
- `scripts/lib/skill-improvement/amendify.js`
- `scripts/lib/skill-improvement/evaluate.js`
- `skills/eval-harness/SKILL.md`
- `skills/verification-loop/SKILL.md`

이 레이어는 “실행 결과를 남기고, health/evaluation/amendment proposal로 다시 읽는다”는 구조다.

상태 저장:

- SQLite-compatible local state store
- sessions
- skill_runs
- skill_versions
- decisions
- install_state
- governance_events

관찰 기반 보정:

- skill observation JSONL 수집
- repeated failure pattern 집계
- health report 생성
- amendment proposal 생성
- baseline vs amended 비교

이것은 현재 레포의 support promotion과는 다르지만, “반복 실패를 structured observation으로 바꾸고, 개선 후보를 별도 산출물로 만든다”는 면에서 강한 참고 가치가 있다.

### 3.7 Layer 7: Orchestration Substrate

핵심 파일:

- `scripts/lib/tmux-worktree-orchestrator.js`
- `scripts/orchestrate-worktrees.js`

이 레이어는:

- worker별 git worktree 생성
- task/handoff/status markdown artifact 생성
- tmux pane orchestration

을 수행한다.

즉 worker runtime coordination을 위한 lightweight substrate다.

현재 레포에 바로 필요한 것은 아니지만, 병렬 조사/검증/리뷰 lane을 운영할 때 operator substrate로 참고할 수 있다.

### 3.8 Layer 8: ECC2 Alpha Control Plane

핵심 파일:

- `ecc2/Cargo.toml`
- `ecc2/src/main.rs`
- `ecc2/src/session/*`
- `ecc2/src/worktree/mod.rs`
- `ecc2/src/observability/mod.rs`
- `ecc2/src/tui/*`

ECC2는 Rust 기반 TUI/control-plane 프로토타입이다.

기능 범위:

- session start/delegate/assign/drain inbox/auto dispatch
- coordination status
- worktree status / merge readiness / prune
- observability tool log
- SQLite state store

구조적으로는:

- 하네스 operator shell
- multi-session/team coordinator
- worktree lifecycle manager

이다.

현 시점의 현재 레포에겐 직접 이식 대상이라기보다 “장기 control-plane 분리”의 참고 사례다.

## 4. `everything-claude-code`의 tool graph는 무엇인가

이 레포에는 현재 레포의 `runtime_graph`처럼 하나의 explicit graph가 있는 것은 아니다.

대신 graph-like surface가 3개 있다.

### 4.1 Install Graph

- `profile -> component -> module -> target`

이 graph는 distribution/control-plane scope를 정의한다.

### 4.2 Hook/Event Graph

- `SessionStart -> PreToolUse -> PostToolUse -> PreCompact -> Stop`

각 이벤트에 여러 hook가 연결되고, strictness profile이 그 실행을 조절한다.

실질적으로 이게 가장 중요한 execution graph다.

### 4.3 Session Adapter Graph

- `target type -> adapter -> canonical snapshot -> recording/state store`

이 graph는 operator view를 통일한다.

현재 레포에 적용할 때도 “tool graph”를 그대로 가져오기보다, 아래처럼 번역하는 것이 맞다.

- `pipeline stage hooks`
- `artifact normalization adapters`
- `deterministic audit graph`

## 5. 현재 레포와의 비교

현재 레포의 강점:

- `runtime_graph`, `executor_plan`, `evidence_graph`가 실제 도메인 실행에 연결됨
- `staged_synthesis`가 generator retry와 failure stage를 설명함
- `tests/e2e`와 repeatability/support workflow가 실측 하니스로 존재함

현재 레포의 약점:

1. 하네스 품질 자체를 별도 scorecard로 관리하지 않음
2. stage-local gate가 코드에 흩어져 있고 선언적이지 않음
3. run artifacts가 많지만 canonical operator snapshot이 약함
4. 반복 실패를 “개선 후보”로 구조화하는 observation layer가 약함
5. verification discipline이 강한 출력 계약보다 서비스별 휴리스틱에 의존함

이 지점이 `everything-claude-code`와 맞닿는다.

## 6. 적용 가능한 요소

### 6.1 Deterministic Harness Audit

가장 직접적이고 우선순위가 높다.

현재 레포용 `pipeline-harness-audit` 또는 `control-plane-audit`를 만들면 좋다.

권장 카테고리:

1. Selection Authority
2. Materialization Causality
3. Runtime Contract Parity
4. Oracle Execution Parity
5. Measured Gate Integrity
6. Review Evidence Quality
7. Cost / Retry Efficiency

예시 check:

- `selection_decision`이 `ready_for_materialization`과 `open_world_evidence_ready`를 일관되게 남기는가
- `selection_branch_trace`가 selected vs materialized divergence를 설명하는가
- `runtime_graph`와 `executor_plan`이 executor에 실제 primary input으로 사용되는가
- `oracle_execution_parity`가 manifest/evals/support surface에 일관되게 반영되는가
- strict_dynamic fail-closed subclasses가 섞이지 않는가

효과:

- raw PASS/FAIL 외에 control-plane quality score를 별도로 가질 수 있다.
- 성공률 보정에서 “실제로 개선된 것”과 “우연히 통과한 것”을 분리하기 좋다.

### 6.2 Hook-Style Stage Gate 선언화

현재 레포는 capability gate, generator gate, executor precheck, verify gate가 `run_pipeline.py`와 executor validator에 흩어져 있다.

`everything-claude-code`에서 가져올 수 있는 것은 hook 철학이다.

권장 번역:

- `PreResearch`
- `PostResearch`
- `PreGenerate`
- `PostGenerate`
- `PreExecute`
- `PostExecute`
- `PreVerify`
- `PostVerify`
- `PrePack`

각 gate는 JSON/YAML 또는 Python registry로 선언 가능하다.

필드 예시:

- `id`
- `stage`
- `enabled_profiles`
- `blocking`
- `validator`
- `emits`
- `failure_class`

이렇게 되면 현재의 scattered validation을 operator-readable event graph로 승격할 수 있다.

### 6.3 Canonical Run/Session Snapshot

현재 레포는 다음 산출물이 분산돼 있다.

- `loop_state.json`
- `researcher_report.json`
- `generator_manifest.json`
- `generator_failures.jsonl`
- `run/summary.json`
- `reports/evals.json`
- `summary.json`
- `support_candidate.json`
- `support_review_index.json`

이걸 바로 하나로 합치자는 게 아니라, ECC식 adapter 레이어를 두는 게 좋다.

예시:

- `adapter=direct-run`
- `adapter=repeatability-run`
- `adapter=support-review`
- `adapter=packed-bundle`

그리고 canonical snapshot:

- `session`
- `bundle`
- `selection`
- `runtime`
- `verification`
- `review`
- `measured_gate`
- `artifacts`

효과:

- direct/repeatability/support/pack 간 비교가 쉬워진다.
- benchmark와 대시보드가 간단해진다.
- success-rate calibration에서 lane별 authority drift를 쉽게 집계할 수 있다.

### 6.4 Observation Store 기반 보정

ECC의 skill-improvement 계층은 “반복 실패를 구조화된 observation으로 저장하고 요약한다”는 점에서 유용하다.

현재 레포에 적용하면 좋은 대상:

- generator failure patterns
- verifier low-trust blocks
- support workflow blockers
- stage retry salvage outcomes

권장 저장 예:

- `observation_id`
- `bundle_slug`
- `mode`
- `selected_family`
- `selected_stack_id`
- `selected_scenario_id`
- `failure_stage`
- `failure_class`
- `repair_strategy`
- `success`
- `oracle_execution_parity`
- `measured_gate_ready`

이 데이터를 기반으로:

- recurring failure clusters
- repair strategy health report
- baseline vs amended policy comparison

을 자동 생성할 수 있다.

이건 현재 레포의 성공률 보정에 매우 직접적이다.

### 6.5 Eval / Verification Formalization

`skills/eval-harness`와 `skills/verification-loop`는 내용 자체는 단순하지만, 중요한 건 “verification을 first-class workflow로 분리한다”는 태도다.

현재 레포에 필요한 번역:

- capability eval
- regression eval
- pass@k / pass^k
- human review required lane

현재 레포는 이미 repeatability/support workflow를 갖고 있으므로, 이걸 더 공식적으로 문서/artifact contract로 올릴 수 있다.

예:

- `pass@1`: direct deterministic pass
- `pass@3`: loop retry 포함 성공
- `pass^3`: repeatability 안정성
- `promotable@k`: measured/support gate까지 포함한 실제 promotion 가능성

이 지표는 현재 레포에 매우 적합하다.

### 6.6 State Store 기반 운영 시야

ECC의 SQLite state store 전체를 가져올 필요는 없다. 하지만 “artifact들을 조회 가능한 local state로 재인덱싱한다”는 아이디어는 유효하다.

현재 레포에 유의미한 테이블 예:

- runs
- bundles
- stage_events
- failure_observations
- retry_attempts
- support_decisions
- audit_snapshots

이렇게 되면 반복 rerun과 support workflow를 SQL queryable surface로 읽을 수 있다.

## 7. 적용 가치가 낮은 요소

### 7.1 Massive Skills / Agents Catalog

현재 레포의 병목은 skill 수가 아니라 control-plane closure다.

- 수백 개 skill/agent를 가져와도 open-world name-only generation 품질이 바로 오르지 않는다.
- 오히려 operator surface가 복잡해질 위험이 크다.

### 7.2 Cross-Harness Install System

ECC의 selective install architecture는 훌륭하지만 현재 레포 목표와는 거리가 있다.

- 현재 레포는 cross-harness product가 아니다.
- install graph보다 pipeline graph 정교화가 우선이다.

### 7.3 tmux Worktree Orchestrator 전체

이는 operator productivity에는 좋다.

하지만 현재 레포의 core blocker는:

- worker pane 부족
- worktree 부재

가 아니라:

- selection/materialization causality
- runtime/oracle parity
- measured/support promotion precision

이다.

즉 직접 효과는 제한적이다.

### 7.4 ECC2 TUI 자체

ECC2는 장기적으로 흥미롭지만 현재 레포에는 너무 크다.

- 도입 비용이 높다.
- 현재 레포의 문제를 바로 해결하지 않는다.

참고할 것은 TUI가 아니라 “session/worktree/observability를 separate control-plane으로 둔다”는 구조다.

## 8. 현재 레포용 구체 제안

### 8.1 P0: `pipeline-harness-audit` 추가

`scripts/harness-audit.js`와 같은 deterministic audit를 현재 레포에 맞게 만든다.

출력:

- overall score
- category scores
- failed checks
- top actions
- representative lanes to rerun

이 산출물은 `pack.py` summary와는 별도로 유지하는 것이 좋다.

### 8.2 P0: stage gate registry 추가

현재 scattered validation을 registry로 승격한다.

초기 대상:

- strict capability precheck
- post-research authority check
- post-generator live-path check
- executor precheck
- post-verify low-trust check
- pre-pack promotion integrity check

이렇게 하면 현재 레포의 `if` 체인 로직을 더 측정 가능하게 바꿀 수 있다.

### 8.3 P1: canonical snapshot adapters 추가

우선 3개면 충분하다.

- `direct-run adapter`
- `repeatability adapter`
- `support-review adapter`

그리고 canonical JSON으로 normalize한다.

이건 보고서/대시보드/benchmark 일관성을 크게 올린다.

### 8.4 P1: observation ledger 추가

현재 `generator_failures.jsonl`는 좋은 출발점이다.

여기에:

- verify failure
- support blocker
- repair result
- promotion outcome

까지 합쳐 observation ledger를 만든다.

이 레이어가 생기면 success rate 보정이 훨씬 쉬워진다.

### 8.5 P2: verification contract 강화

ECC의 verification-loop 자체보다, “verification을 별도 gate workflow로 강제한다”는 구조를 가져오는 게 맞다.

현재 reviewer/verifier 쪽 보완:

- command-backed evidence
- result schema
- regression/capability/pass@k 기준 고정

## 9. 성공률 보정 관점의 해석

`everything-claude-code`는 raw task success를 직접 올리는 시스템이 아니다.

대신 아래를 더 잘하게 만든다.

1. 하네스 품질의 분리 측정
2. 품질 gate의 선언화
3. 세션/런의 canonical recording
4. 반복 실패의 구조화
5. 평가 루프의 공식화

즉 현재 레포에서 이 구조를 쓰면:

- “왜 성공률이 올랐는가”를 더 잘 설명할 수 있고
- “어떤 성공은 promotion-quality success가 아닌가”를 더 잘 분리할 수 있다.

이건 단순 improvement가 아니라 calibration improvement다.

현재 레포 요청 관점에서는 이 점이 매우 중요하다.

## 10. 최종 판단

`everything-claude-code`는 현재 레포에 직접 포팅할 “서비스 구현”이 아니다.

더 정확한 해석은 다음이다.

- 현재 레포는 domain pipeline이 핵심이다.
- ECC는 harness performance/control-plane이 핵심이다.
- 둘은 경쟁 구조가 아니라 상보 구조다.

현재 레포에 실제로 가져올 만한 것은:

1. deterministic harness audit
2. hook-like stage gate registry
3. canonical snapshot adapters
4. observation/state store 기반 failure health report
5. eval/verification workflow formalization

가져오지 말아야 할 것은:

1. 대형 skill/agent 카탈로그 복제
2. cross-harness packaging 전체
3. tmux operator shell 전체
4. ECC2 TUI 직접 도입

실행 우선순위:

1. `pipeline-harness-audit`
2. stage gate registry
3. canonical snapshot adapters
4. observation ledger / health report
5. verifier/eval contract 강화

정리하면:

> `everything-claude-code`가 주는 가장 큰 교훈은 “좋은 agent system은 파이프라인만 잘 짜는 것이 아니라, 하네스 품질 자체를 별도 제어면으로 관리한다”는 점이다. 현재 레포가 가져와야 할 것도 바로 그 `audit + gate + snapshot + observation` 계층이다.
