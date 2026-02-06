# Eval 검증 추상화/템플릿 독립화 구현안

## 1. 개요
- 목적: `evals/poc_verifier` 파이프라인이 현재 SQLi(CWE-89), CSRF(CWE-352) 템플릿에만 종속되어 있는 문제를 해소하고, 새로운 취약 템플릿을 추가할 때 규칙·가드·플러그인을 반복 구현하지 않아도 되도록 공통 추상화를 도입한다.
- 근거: 실제 산출물 `artifacts/sid-00cd2caed6d3/reports/evals.json`에서 확인되듯 검증 증거가 `app.py`, `poc.py` 고정 문자열(SELECT, "SQLi SUCCESS", "@app.route('/transfer")만을 확인한다. 또한 `agents/generator/synthesis.py:584-661`의 가드가 동일 문자열 존재 여부를 하드코딩해 합성단계에서 template 이탈을 금지한다.

## 2. 현황과 문제 요약

> 이 섹션은 **초기 리포 상태 기준 문제점 요약**이다. 이후 14~17절의 체크리스트/진행 상황 업데이트에서 어떤 부분이 실제 코드로 해소되었는지, 무엇이 여전히 남아 있는지 단계별로 기술한다.
1. **규칙/패턴 템플릿 종속**
   - `docs/evals/rules/*.yaml`은 `app.py`, `poc.py` 파일명과 특정 문자열을 직접 명시한다.
   - `common/rules/__init__.py`는 위 두 rule만 로드하므로 새로운 CWE rule을 작성하지 않는 한 전체 파이프라인이 “rule unavailable” 상태로 남는다.
2. **플러그인 고정**
   - `evals/poc_verifier/mvp_sqli.py`, `evals/poc_verifier/csrf.py` 두 함수만 `register_verifier`에 등록된다. 신규 취약점은 rule fallback만 사용하거나 아예 unsupported가 된다.
3. **Generator/Researcher와의 단단한 결합**
   - `agents/generator/synthesis.py`가 rule을 직접 읽어 `success_signature must include 'SQLi SUCCESS'` 같은 에러를 뱉는다.
   - `agents/researcher/service.py:220-244`는 runtime rule을 생성할 때 동일 문자열을 재사용한다.
4. **워크스페이스 구조 가정**
   - `evals/poc_verifier/rule_based.py:284-323`에서 `workspaces/<SID>/app[/<slug>]`만 검색해 패턴을 찾는다. 템플릿이 다른 파일명을 쓰면 eval이 실패한다.

## 3. 제안하는 추상화 구조
### 3.1 EvaluationContext
```python
@dataclass
class EvaluationContext:
    sid: str
    vuln_id: str
    slug: str
    log_path: Path
    workspace: Path
    requirement: dict
    run_summary: dict
    rule_spec: RuleSpec
```
- `rule_spec`은 rule YAML + template metadata를 결합한 객체로, 파일 엔트리/포맷/패턴 placeholder를 해석한 값만을 보유한다.

### 3.2 RuleSpec & placeholder
- YAML에 `service_entry`, `poc_entry`, `patterns` 등에서 `{{service_main}}`, `{{poc_main}}`를 허용하고, template metadata(예: `workspaces/templates/**/template.json`) 또는 requirement 입력으로 치환한다.
- `common/rules`가 RuleSpec을 구성하면서 placeholder를 resolve해 `BaseScenarioVerifier`와 generator 모두에게 전달하도록 한다.

### 3.3 BaseScenarioVerifier (추상 클래스)
```python
class BaseScenarioVerifier(ABC):
    def __init__(self, context: EvaluationContext) -> None: ...
    @abstractmethod
    def expected_signature(self) -> SignatureSpec: ...
    @abstractmethod
    def verify_log(self) -> Evidence: ...
    def verify_patterns(self) -> Evidence: ...
```
- 기본 설계 의도는 `verify_log`가 텍스트/JSON/FLAG 검사(`rule_based` 모듈 로직)를 재사용하고, 하위 클래스가 필요한 assertion 또는 메타모픽 조건만 오버라이드하는 것이다.
- **현재 구현 기준**으로는 `BaseScenarioVerifier.verify_log()`가 기본적으로 `verify()`에 위임하며, 실제 텍스트/JSON/FLAG 검사는 `RuleBasedScenario.verify()` 내부에서 `rule_based.verify_with_rule()`을 호출하는 방식으로 제공된다. 추후 시나리오 타입별로 `verify_log()`/`verify_patterns()`를 세분화할 수 있도록 인터페이스만 먼저 도입한 상태이다.
- `register_verifier`는 vuln ID → 시나리오 클래스를 등록하고 `evaluate_with_vuln`에서 인스턴스화한다.

### 3.4 시나리오 유형 예시
1. `SignatureOnlyScenario`: 기존 SQLi/CSRF처럼 문자열/FLAG 만 확인.
2. `HttpEffectScenario`: run.log의 request/response 또는 `summary.json` delta를 assertion으로 정의.
3. `FileMutationScenario`: workspace내 특정 파일·코드를 확인.
새로운 템플릿을 만들 때 template metadata에 “scenario_type: http_effect”만 지정하면 대응 클래스를 자동으로 생성할 수 있다.

## 4. 수정 대상 스크립트 및 방향성
| 파일/디렉토리 | 작업 범위 |
| --- | --- |
| `docs/evals/rules/*.yaml` | placeholder 스키마, `service_entry`·`poc_entry`·`scenario_type` 필드 추가 |
| `common/rules/__init__.py` | RuleSpec 생성, runtime template metadata를 merge, placeholder 치환 로직 |
| `evals/poc_verifier/rule_based.py` | 텍스트/JSON/패턴 평가 함수를 BaseScenarioVerifier에서 호출 가능한 형태로 분리 |
| `evals/poc_verifier/registry.py` | vuln ID → 시나리오 클래스 매핑, `EvaluationContext` 조립, rule fallback 로직 단순화 |
| `evals/poc_verifier/mvp_sqli.py`, `csrf.py` | BaseScenarioVerifier 하위 클래스로 재작성(또는 YAML 기반 파생 클래스 자동 생성) |
| `agents/generator/synthesis.py` | 가드에서 RuleSpec 기반 검증(placeholder 반영), 성공 시그니처·flag 강제 조건 제거 또는 일반화 |
| `agents/researcher/service.py` | runtime rule 생성 시 template metadata 기반 RuleSpec을 재사용(하드코딩 제거) |
| `workspaces/templates/**/template.json` | service/poc 엔트리, scenario_type, flag token 등 메타데이터 정의 |

## 5. 구현 단계 제안
1. **스키마 확장**: rule YAML 및 template metadata에 placeholder/시나리오 타입 필드를 추가하고 샘플(SQLi/CSRF)을 변환한다.
2. **RuleSpec 로더**: `common/rules`에서 RuleSpec dataclass와 placeholder 해석 함수를 구현한다.
3. **평가 추상화 도입**: `evals/poc_verifier`에 `EvaluationContext`, `BaseScenarioVerifier`, `ScenarioRegistry`를 추가하고 기존 rule-based/플러그인 코드를 신규 구조로 이식한다.
4. **Generator/Researcher 연동**: RuleSpec을 generator 가드·runtime rule 생성에 재사용하여 이중 정의를 제거한다.
5. **회귀 테스트**: `python evals/poc_verifier/main.py --sid <SID>` 및 `ops/ci/run_base_example.sh`를 실행하고 `artifacts/<SID>/reports/evals.json` 비교, synthesis guard 에러 메시지 변화를 확인한다.

## 6. 추가 고려 사항
- **LLM fallback**: `llm_assisted_verify`는 context-aware evidence를 필요로 하므로 prompt에 RuleSpec 요약(필수 시그니처/패턴)을 주입한다.
- **워크스페이스 탐색 범위**: EvaluationContext에서 workspace 경로를 명시적으로 받아 placeholder 기반 상대 경로를 계산함으로써, 템플릿마다 디렉토리 구조가 달라도 패턴 검사가 가능해진다.
- **호환성**: 기존 docs/problem.md에서 언급한 “FLAG 출력 강제” 제약을 RuleSpec 설정만으로 완화할 수 있으므로, backward compatibility 확보를 위해 기본 placeholder 값을 기존 템플릿과 동일하게 설정한 뒤 점진적으로 확장한다.

## 7. 진행 상황 업데이트 (1차)
- **실제 코드 반영**
  - `evals/poc_verifier/scenarios.py`에 `EvaluationContext`, `RuleSpec`, `BaseScenarioVerifier`, `RuleBasedScenario`와 시나리오 레지스트리 헬퍼(`register_scenario`, `get_scenario`, `build_evaluation_context`)를 추가했다. 현재는 rule YAML을 그대로 감싸는 얇은 RuleSpec을 사용한다.
  - `evals/poc_verifier/mvp_sqli.py`, `evals/poc_verifier/csrf.py`를 시나리오 기반 구조로 리팩터링했다. 각각 `SqlInjectionScenario`, `CsrfScenario`가 `BaseScenarioVerifier`를 상속해 기존 문자열/FLAG 기반 판정 로직을 구현하고, 기존 `register_verifier` 엔트리는 `build_evaluation_context`로 context를 구성한 뒤 시나리오 인스턴스를 호출한다.
- **동작 범위**
  - 기존 verifier 플러그인 인터페이스(`register_verifier` → `func(log_path) -> dict`)는 그대로 유지되며, 내부 구현만 시나리오 추상화를 사용하도록 변경했다. rule-based 평가(`evals/poc_verifier/rule_based.py`)와 registry 로직(`evals/poc_verifier/registry.py`)의 외부 인터페이스는 변경하지 않아 현재 SQLi/CSRF 파이프라인 동작에는 영향을 주지 않는다.
- **미완료/향후 작업**
  - RuleSpec placeholder(`service_entry`, `poc_entry`, `scenario_type` 등)를 사용하는 YAML/템플릿 메타데이터 확장과, `common/rules`에서의 RuleSpec 로더 도입은 아직 적용하지 않았다.
  - `evals/poc_verifier/registry.py`를 시나리오 레지스트리 기반으로 단순화하고, Generator/Researcher에서 RuleSpec을 재사용하도록 연동하는 단계는 후속 변경으로 남아 있다.

## 8. 설계 원칙 및 전반 데이터 플로우

### 8.1 설계 원칙
- **YAML은 최소한의 정책만** 표현한다.
  - 취약점 타입(CWE), 시나리오 종류(scenario_type), 플래그 강제 여부, exit code 정책, LLM 보조 허용 여부 등 **이산적인 파라미터**만 유지한다.
  - `"SQLi SUCCESS"`, `"CSRF SUCCESS"`, `"@app.route('/transfer"` 같은 **구체 문자열/파일 경로는 YAML에서 제거**한다.
- **성공 시그니처·경로·플래그 값은 LLM이 설계**한다.
  - Generator/Researcher LLM 응답에서 `verification_spec` JSON을 받아 동적으로 code/PoC에 삽입하고, runtime rule로도 저장한다.
- **Template 디렉터리 구조/파일명에 대한 의존성 제거**
  - `app.py`, `poc.py` 등은 “role” 수준(`service_main`, `poc_entry`)으로만 인식하고, 실제 경로는 LLM manifest에서 읽는다.
- **기존 파이프라인과의 호환성 유지**
  - 초기 단계에서는 legacy YAML(`success_signature` 기반)을 RuleSpec으로 어댑트하여 SQLi/CSRF 케이스는 그대로 통과시키고, 점진적으로 v2 스키마와 runtime spec으로 이행한다.

### 8.2 전체 데이터 플로우 (요약)
1. **PLAN**: `orchestrator/plan.py`가 requirement(취약점 목록·정책)를 기반으로 `plan.json` 생성.
2. **RESEARCHER**(선택): `agents/researcher/service.py`가 LLM을 호출해
   - 취약 코드 아이디어,
   - **verification_spec**(성공 조건/FLAG/검증 assertion)을 함께 도출.
   - 결과를 `metadata/<SID>/bundles/<CWE>/researcher_report.json` 및 `metadata/<SID>/runtime_rules/<CWE>.yaml`에 저장.
3. **GENERATOR**: `agents/generator/main.py`가 LLM manifest를 받아
   - 코드/PoC 파일을 materialize 하고,
   - manifest 내부 또는 Researcher 출력에 포함된 `verification_spec`을 읽어 PoC 코드에 성공 메시지/FLAG를 삽입.
4. **EXECUTOR**: `executor/runtime/docker_local.py`가 Docker build/run과 PoC 실행을 수행하고, `run.log`/`summary.json` 생성.
5. **EVALS**: `evals/poc_verifier/main.py`가
   - `run/index.json`을 읽어 각 번들별 `run.log`를 찾고,
   - `registry.evaluate_with_vuln`을 호출.
   - 이때 `scenarios.build_evaluation_context`를 통해 EvaluationContext를 구성하고, 등록된 Scenario가 RuleSpec + runtime spec + log를 사용해 검증.
6. **LLM-Assisted**(필요 시): rule/시나리오 기반 검증이 실패하거나 불확실한 경우, `llm_assisted_verify`가 log + RuleSpec 요약을 기반으로 LLM에게 보조 평가를 요청.

이 플로우에서 규칙(YAML)과 템플릿은 **정책/메타데이터 레이어**로만 작동하고, 실제 문자열/경로/FLAG는 LLM 응답에 의해 동적으로 결정된다.

## 9. RuleSpec 및 YAML 스키마 v2 설계

### 9.1 RuleSpec 구조
- `common/rules`에 다음과 같은 RuleSpec dataclass를 도입한다.
```python
@dataclass
class RuleSpec:
    cwe: str
    version: int
    scenario_type: str            # 예: "web-poc", "cli-poc"
    verification_source: str      # "runtime" | "static" | "llm"
    require_flag: bool
    flag_required_mode: str       # "strict" | "loose" | "none"
    exit_code_policy: str         # "zero" | "ignore"
    output_mode: str              # "auto" | "text" | "json"
    json_success_key: str | None
    json_success_value: Any | None
    json_flag_key: str | None
    llm_assist_default: bool
    assertion_budget: int
    runtime: Dict[str, Any]       # LLM이 설계한 verification_spec (동적)
```
- 핵심: RuleSpec은 **“무엇을 검사할지”가 아니라 “어디에서/어떻게 검사식을 가져올지와 정책”**을 표현한다.
  - 실제 성공 문자열/플래그 토큰/JSON 키 등은 `runtime` 필드(LLM이 채운 verification_spec)와 Scenario에서 해석한다.

### 9.2 YAML v2 스키마 (사용자 설정 최소화)
- 예: `docs/evals/rules/cwe-89.yaml` v2
```yaml
cwe: CWE-89
version: 2
scenario_type: web-poc

verification:
  source: runtime          # runtime spec 우선, 없으면 static/llm로 fallback
  require_flag: true
  flag_mode: strict        # strict | loose | none
  exit_code: zero          # zero | ignore

output:
  mode: auto               # auto | text | json
  json_success_key: success
  json_success_value: true
  json_flag_key: flag

llm:
  assist_default: true
  assertion_budget: 8
```
- CSRF(`cwe-352.yaml`)도 동일 구조를 사용하며, **특정 문자열/파일명은 포함하지 않는다.**
- 사용자가 조정하는 범위는 위 이산 파라미터에 한정된다.

### 9.3 RuleSpec 로딩/호환 전략
- `common/rules/__init__.py`에서:
  - `load_rule(vuln_id)`는 기존처럼 원시 YAML dict를 반환.
  - 신규 `load_rulespec(vuln_id)`를 추가:
    - `raw = load_rule(vuln_id)`
    - `raw.get("version", 1)`이 1이면: 기존 `success_signature`, `flag_token`, `patterns`를 이용해 RuleSpec으로 어댑트(legacy 호환).
    - 2 이상이면: 위 스키마에 따라 RuleSpec을 직접 구성.
- runtime rule(Researcher/Generator가 저장하는 YAML)은 `docs/evals/rules`보다 높은 우선순위로 merge:
  - static YAML + runtime YAML을 합성한 뒤 RuleSpec을 만든다.

## 10. Scenario/Registry 레이어 설계 및 Data Flow

### 10.1 EvaluationContext
- 이미 구현된 `evals/poc_verifier/scenarios.py`의 EvaluationContext를 RuleSpec-aware로 확장:
  - 생성 시 `load_rulespec(vuln_id)`를 호출해 `context.rule_spec`에 주입.
  - `workspace_dirs`는 `rule_based._workspace_candidates` 결과를 사용하되, 향후 manifest 기반 탐색으로 대체 예정.

### 10.2 BaseScenarioVerifier 및 RuleBasedScenario
- `BaseScenarioVerifier.verify()`는 추상 메서드로 유지.
- `RuleBasedScenario.verify()`는 다음과 같은 순서:
  1. `context.rule_spec`을 가져온다.
  2. `rule_spec.runtime`에 `assertion_program`이 있으면:
     - `evals.assertions.run_assertions(log_text, assertion_program)`으로 검증.
  3. runtime spec이 없거나 실패하면:
     - 기존 `rule_based.verify_with_rule()` 로직(텍스트/JSON/패턴 기반)을 fallback으로 호출.

### 10.3 Scenario 레지스트리와 registry.evaluate_with_vuln
- `evals/poc_verifier/scenarios.py`의 `register_scenario`, `get_scenario`를 사용해:
  - SQLi: `register_scenario(["CWE-89", "sqli"], SqlInjectionScenario)`
  - CSRF: `register_scenario(["CWE-352", "csrf"], CsrfScenario)`
- `evals/poc_verifier/registry.py`의 `evaluate_with_vuln`는 다음 플로우로 단순화:
  1. `verifier_policy = _resolve_verifier_policy(requirement, plan_policy)`
  2. `ctx = build_evaluation_context(vuln_id, log_path, requirement=..., run_summary=..., policy=verifier_policy)`
  3. `scenario_cls = get_scenario(vuln_id) or RuleBasedScenario`
  4. `scenario = scenario_cls(ctx); result = scenario.verify()`
  5. `result`가 실패이고 LLM 허용 시 `llm_assisted_verify`로 보조 평가 수행.

## 11. Generator/Researcher 연동 및 LLM 기반 verification_spec

### 11.1 verification_spec 설계 (LLM 응답 구조)
- Researcher/Generator LLM 프롬프트에 다음 JSON 블록을 포함하도록 요구:
```json
{
  "verification_spec": {
    "success_mode": "text",
    "success_text_markers": ["LOGIN BYPASSED"],
    "flag_token": "FLAG-sqli-demo-token-123",
    "flag_mode": "strict",
    "json_success_key": "success",
    "json_success_value": true,
    "json_flag_key": "flag",
    "assertion_program": [
      {"op": "contains", "string": "LOGIN BYPASSED"},
      {"op": "contains", "string": "FLAG-sqli-demo-token-123"}
    ]
  }
}
```
- 이 spec은:
  - Generator가 PoC 코드에 성공 메시지/FLAG를 삽입하는 데 사용되고,
  - Researcher 또는 Generator가 `metadata/<SID>/runtime_rules/<CWE>.yaml`로 저장하는 runtime rule의 `runtime` 블록으로 직렬화된다.

### 11.2 runtime rule와 RuleSpec 통합
- runtime rule YAML 예시:
```yaml
cwe: CWE-89
version: 2
scenario_type: web-poc
verification:
  source: runtime
  require_flag: true
  flag_mode: strict
  exit_code: zero

runtime:
  success_mode: text
  success_text_markers:
    - "LOGIN BYPASSED"
  flag_token: "FLAG-sqli-demo-token-123"
  assertion_program:
    - op: contains
      string: "LOGIN BYPASSED"
    - op: contains
      string: "FLAG-sqli-demo-token-123"
```
- `load_rulespec`은 static rule과 runtime rule을 병합하여 RuleSpec.runtime에 위 데이터를 채운다.
- Scenario/RuleBasedScenario는 RuleSpec.runtime을 우선 사용하고, 없을 때만 static fallback에 의존한다.

### 11.3 Generator 가드의 일반화
- `agents/generator/synthesis.py`에서:
  - 현재는 `DEFAULT_SUCCESS_SIGNATURES`, `DEFAULT_FLAG_TOKENS`, `rule_patterns`로 특정 문자열을 강제한다.
  - 변경 후:
    - RuleSpec.runtime의 `flag_token`이 있고 `flag_mode`가 `strict`인 경우:
      - manifest의 `files[*].content` 또는 PoC 엔트리 파일에 해당 토큰이 literal로 포함되어 있어야 한다는 **일반 규칙**만 적용.
    - 성공 문자열은 `verification_spec.success_text_markers`의 첫 요소를 사용해, PoC 엔트리 파일에 존재하는지만 확인.
  - 파일 경로는 LLM manifest의 `role` 필드로 식별:
    ```json
    "files": [
      {"path": "app.py", "role": "service_main"},
      {"path": "poc.py", "role": "poc_entry"}
    ]
    ```
    - 가드는 `role == "poc_entry"`인 파일만 검사한다.

## 12. LLM-Assisted Verifier 통합

### 12.1 runtime assertion 우선 사용
- `evals/poc_verifier/llm_assisted.py`를 다음과 같이 확장:
  - `load_rulespec(vuln_id)`를 읽고, `rulespec.runtime.assertion_program`이 존재하면:
    - `run_assertions(log_text, assertion_program)`으로 먼저 검사.
    - 성공 시 LLM 호출 없이 검증 PASS 및 evidence를 구성.
  - assertion이 없거나 실패했을 때만 기존 LLM 호출(현재 구현)을 실행.

### 12.2 LLM 호출 정책
- RuleSpec 및 requirement/plan policy에서:
  - `llm_assist_default`, `assertion_budget`을 사용해:
    - LLM이 생성할 assertion 개수 상한 관리,
    - 특정 취약점/케이스에서 LLM 보조를 아예 비활성화 가능.

## 13. 파일 역할 및 워크스페이스 처리

### 13.1 파일 역할(role) 기반 설계
- Generator LLM manifest에 각 파일의 `role` 필드를 강제:
  - 예: `service_main`, `poc_entry`, `helper`, `schema`, `seed_data` 등.
- eval/generator 가드는:
  - PoC 검증 시 `poc_entry` 파일만 사용,
  - 서비스 구조 검증 시 `service_main` 파일만 사용.
- YAML/코드에서는 더 이상 `app.py`, `poc.py`라는 파일명을 전제로 하지 않는다.

### 13.2 워크스페이스 탐색
- EvaluationContext 구성 시:
  - 현재는 `rule_based._workspace_candidates`가 **`metadata/<SID>/[bundles/<slug>/]generator_manifest.json`의 `workspace_root` 필드를 우선 사용**하고, 해당 정보가 없을 때에만 `workspaces/<SID>/app[/<slug>]` 디렉터리 패턴으로 폴백해 후보 workspace 디렉터리를 찾는다.
  - 향후에는:
    - manifest/template metadata에서 파일 목록/role을 읽어 workspace_dirs + 역할 정보를 조합하고, 디렉터리 패턴 의존성을 더 줄이는 방향으로 확장한다.
    - RuleSpec.runtime 또는 EvaluationContext에 manifest/metadata 경로를 명시적으로 포함시켜 완전히 선언적인 구성을 목표로 한다.

## 14. 구현 체크리스트 (필수 구현 항목 정리)

1. **RuleSpec/스키마**
   - [x] `common/rules`에 RuleSpec dataclass 및 `load_rulespec` 구현.
   - [x] `docs/evals/rules/*.yaml`을 v2 스키마로 이관(legacy 필드는 load_rule 호환을 위해 유지, patterns.path에는 placeholder 적용).
2. **Scenario/Registry**
   - [x] EvaluationContext에 RuleSpec 주입.
   - [x] `RuleBasedScenario.verify()`에서 RuleSpec.runtime 기반 assertion 우선 사용.
   - [x] `registry.evaluate_with_vuln`를 Scenario 우선 구조로 단순화.
3. **Generator/Researcher**
   - [x] LLM 프롬프트에 `verification_spec` 설계 요구 추가.
   - [x] `verification_spec`을 runtime rule(`metadata/<SID>/runtime_rules/<CWE>.yaml`)에 저장.
   - [x] synthesis 가드에서 하드코딩된 문자열/파일명을 제거하고 RuleSpec + role 기반 로직으로 대체.
4. **LLM-Assisted Verifier**
   - [x] `llm_assisted_verify`에서 RuleSpec.runtime.assertion_program 우선 사용.
   - [x] 실패 시에만 기존 LLM 호출로 보조 검증 수행.
5. **파일 역할/워크스페이스**
   - [x] manifest/template metadata에 파일 `role`(또는 동등한 역할 정보) 필드 추가.
   - [ ] eval/generator/Researcher 코드에서 `role`/manifest 기반으로 파일을 찾도록 리팩터링(Generator/eval 대부분은 구현, Researcher 경로는 여전히 미구현).  
     - 4차 이후 추가 구현: eval 쪽에서는 `rule_based._evaluate_patterns()`가 generator_manifest와 RuleSpec의 service_entry/poc_entry 정보를 함께 사용해 placeholder를 해석하고, workspace 디렉터리가 비어 있어도 manifest 파일 내용만으로 패턴 검사를 수행할 수 있도록 확장되었다.  
     - 5차 이후 추가 구현: `agents/generator/synthesis.SynthesisEngine._write_records()`가 `generator_manifest.json`에 `workspace_root`(실제 materialized workspace 절대 경로)를 기록하고, `evals/poc_verifier/rule_based._load_generator_manifest()`와 `_workspace_candidates()`가 이를 우선 사용해 단일 workspace 디렉터리를 결정하도록 변경되었다. multi-vuln 실행 시에는 `metadata/<SID>/bundles/<slug>/generator_manifest.json`을 우선 탐색하고, 없을 때 `metadata/<SID>/generator_manifest.json`으로 폴백한다. 여전히 Researcher 경로는 role/manifest 정보를 활용하지 않으므로, 체크리스트 항목은 부분 완료 상태로 남겨 둔다.
     - 향후 구현 가이드(Researcher/정책 계층/완전 manifest 기반 탐색):
       - **Researcher 경로 정렬**: `agents/researcher/service.ResearcherService`가 `generator_template.json`/`generator_manifest.json`을 읽어,  
         - 리포트에 사용된 템플릿 ID/파일 role 정보를 포함하고,  
         - `verification_spec`를 생성할 때 RuleSpec.template_flag_token, service_entry/poc_entry와 일치하도록 검증/보정하는 로직을 추가한다.
       - **정책 계층 분리**: RuleSpec/requirement/plan의 정책 필드(예: llm_assist, assertion_budget, exit_code_policy)를 별도 모듈(예: `common/policy/verifier.py`)로 추출해,  
         - “전역 기본값 → RuleSpec → plan.requirement.policy → run별 override” 순서가 코드/문서로 명시되도록 정리한다.
       - **완전 manifest 기반 workspace 탐색**: `rule_based._workspace_candidates()`가 `workspace_root` 폴백에 더해,  
         - generator_manifest의 `files[].path`/`role` 목록만으로도 논리적 workspace 뷰를 구성하고,  
         - 실제 디스크 디렉터리가 일부 비어 있거나 변형된 경우에도 manifest-only 모드로 eval이 동작할 수 있도록 확장한다.

위 항목을 순차적으로 완료하면, 이 문서만으로 **템플릿/파일명/고정 문자열에 의존하지 않는, LLM 응답 기반 동적 eval 파이프라인** 구현이 가능하다.

## 15. 진행 상황 업데이트 (2차)

- **RuleSpec 및 로더**
  - `common/rules/__init__.py`에 `RuleSpec` dataclass와 `load_rulespec(vuln_id)`를 실제 구현했다.
    - `docs/evals/rules/*.yaml`과 runtime rule 디렉터리(`VULD_RUNTIME_RULE_DIRS`)를 모두 스캔해 동일 `cwe`에 해당하는 YAML을 병합하고, legacy(v1)/v2 스키마를 자동으로 구분해 RuleSpec으로 어댑트한다.
    - legacy rule의 경우 `success_signature`, `flag_token`, `strict_flag`, `output.format/json` 등을 기반으로 `require_flag`, `flag_required_mode`, `output_mode`, `json_success_key/value`, `json_flag_key` 등을 채우고, v2 스키마는 `verification`/`output`/`llm`/`runtime` 블록을 그대로 반영한다.
    - 4차 이후 추가 구현: `workspaces/templates/**/template.json`의 템플릿 메타데이터를 스캔해 `scenario_type`, `service_entry`, `poc_entry`, `flag_token`을 RuleSpec에 주입한다. 이때 `RuleSpec.runtime.flag_token`이 비어 있으면 템플릿의 `flag_token`으로 보완해, Generator/Verifier/Researcher가 동일한 기본 플래그 정책을 공유하도록 했다.
    - 기존 `load_rule`, `list_rules` API는 그대로 유지해 backward compatibility를 보장한다.

- **Scenario/EvaluationContext/Registry 통합**
  - `evals/poc_verifier/scenarios.py`:
    - `RuleSpec`를 `common.rules`에서 import하도록 변경하고, `build_evaluation_context()`가 항상 `load_rulespec(vuln_id)`를 호출해 `EvaluationContext.rule_spec`에 주입하도록 수정했다.
    - `RuleBasedScenario.verify()`는 먼저 `rule_spec.runtime.assertion_program`이 존재하면 `evals.assertions.run_assertions()`로 runtime assertion program을 실행하고, 성공 시 그 결과만으로 PASS 판정을 내린다. assertion program이 없거나 실패할 경우 기존 `rule_based.verify_with_rule()`을 그대로 fallback으로 호출한다.
    - 5차 이후 추가 구현: `build_evaluation_context()`가 `metadata/<SID>/[bundles/<slug>/]generator_template.json`을 찾아, 존재할 경우 해당 템플릿 메타데이터(`scenario_type`, `service_entry`, `poc_entry`, `flag_token`)를 RuleSpec에 오버레이하도록 확장되었다. 이를 통해 다중 템플릿 환경에서도 “이번 run에서 실제 사용된 템플릿” 기준으로 RuleSpec이 정렬되며, TemplateRegistry의 전역 인덱스는 기본값/폴백 역할로 남는다.
  - `evals/poc_verifier/registry.py`:
    - 기존 rule/plugin 분기 대신, 먼저 `build_evaluation_context()`로 `EvaluationContext`를 구성하고, `get_scenario(vuln_id) or RuleBasedScenario`를 통해 Scenario를 선택해 `_run_scenario()`를 실행하도록 변경했다.
    - `prefer_rule` 또는 verifier(plugin) 유무에 따라:
      - (a) Scenario 우선 → unsupported면 plugin으로 fallback,
      - (b) plugin 우선 → 실패 시 Scenario로 fallback 하는 기존 흐름을 유지하되, rule 기반 경로를 Scenario 레이어로 통합했다.
    - `verifier_meta.type`는 Scenario 경로에서도 `"rule"`로 설정해 기존 결과 구조(`rule_available` 등)와 최대한 호환되도록 구성했다.

- **LLM-Assisted Verifier와 RuleSpec 연계**
  - `evals/poc_verifier/llm_assisted.py`:
    - `load_rulespec(vuln_id)`를 사용해 RuleSpec을 불러오고, `rulespec.runtime.assertion_program`이 존재할 경우 LLM 호출 전에 `run_assertions(log_text, assertion_program)`을 실행하도록 확장했다.
    - assertion program이 모두 성공하면 LLM을 호출하지 않고, assertion 결과를 evidence로 사용해 `"status": "evaluated-llm"` 형태의 결과를 반환한다.
    - assertion program이 없거나 실패할 경우에만 기존 LLM 프롬프트/호출 경로를 그대로 실행한다.

- **현재 구현 상태 요약**
  - RuleSpec/Scenario/Registry/LLM 간 기본 data flow는 코드에 반영된 상태이다.
    - static + runtime YAML 병합 → RuleSpec
    - RuleSpec → EvaluationContext.rule_spec
    - Scenario(RuleBasedScenario) → runtime assertion program → rule-based fallback
    - registry.evaluate_with_vuln → Scenario + plugin + LLM fallback
  - Generator/Researcher 쪽 `verification_spec` 설계, runtime rule에 assertion_program을 실제로 기록하는 부분, 파일 role 기반 가드 개선은 (당시 기준으로) 미구현 상태였으며, 이후 3차 업데이트에서 Generator/role 기반 가드 일부를 도입했다(아래 16절 참조). 4차 업데이트에서 Researcher가 `verification_spec`을 runtime rule로 직렬화하는 경로와 템플릿 메타데이터의 scenario_type/entry/flag 정보를 보강했다.

## 16. 진행 상황 업데이트 (3차) — Generator/템플릿/role 리팩터링

- **LLM 프롬프트/verification_spec 힌트**
  - `common/prompts/templates.py`:
    - `build_synthesis_prompt()`에 `files[]` 각 항목의 `role` 필드 사용을 권장하는 문구를 추가했다. (`service_main`, `poc_entry`, `helper`, `schema`, `seed_data` 등의 예시를 제시)
    - PoC가 출력해야 하는 성공 시그니처는 여전히 “명확한 성공 문자열”로 요구하지만, 구체 문자열은 LLM이 자유롭게 선택할 수 있도록 완화했다(예: `{sig}`는 참고 예시일 뿐 강제값이 아님).
    - `build_researcher_prompt()`에는 필요 시 compact한 `verification_spec`(success_text_markers, flag_token, assertion_program)을 리포트에 포함할 수 있다는 선택적 가이드를 추가했다. 현재 코드는 이 필드를 아직 파싱하지 않지만, 후속 구현에서 runtime rule과 RuleSpec.runtime으로 연결할 수 있도록 설계 의도를 명시했다.

- **Generator → RuleSpec/runtime 연동**
  - `agents/generator/synthesis.py`:
    - `common.rules.load_rulespec`와 `RuleSpec`을 import하고, `SynthesisEngine`이 `run()` 시점에 `self._rulespec`에 RuleSpec을 로드하도록 변경했다. (`load_rule`는 legacy 호환을 위해 유지)
    - `_normalize_poc_template()`에서:
      - 우선순위: `RuleSpec.runtime.success_text_markers[0]` → legacy rule의 `success_signature` → `DEFAULT_SUCCESS_SIGNATURES` 순으로 성공 시그니처를 선택한다.
      - 플래그 토큰도 `RuleSpec.runtime.flag_token` → legacy rule의 `flag_token` → `DEFAULT_FLAG_TOKENS` 순으로 결정한다.
      - 이 값을 `DEFAULT_POC_TEMPLATE`에 주입하여, 이후 LLM manifest 보정/폴백 PoC 생성 시에도 RuleSpec 기반 시그니처/플래그를 일관되게 사용한다.

- **synthesis 가드의 RuleSpec + role 기반 일반화**
  - `_guard_manifest()`의 PoC 관련 검사 로직을 다음처럼 일반화했다.
    - **성공 시그니처(success_signature)**:
      - `self._rulespec.runtime.success_text_markers[0]`가 존재하면, 이를 “primary_marker”로 간주한다.
      - `poc.success_signature` 문자열 또는 `files[]` 중 `role == "poc_entry"`(또는 `path`가 `poc.py`)인 파일의 `content` 안에 primary_marker가 포함되어 있어야 한다. 그렇지 않으면 오류:  
        `poc.success_signature or PoC code should reference runtime marker '<marker>'`.
      - runtime marker가 없을 때만 기존 동작(legacy rule의 `success_signature` 또는 `DEFAULT_SUCCESS_SIGNATURES`가 `poc.success_signature`에 포함되는지 검사)을 유지한다.
    - **플래그 토큰(flag_token)**:
      - 기대 플래그 토큰: `RuleSpec.runtime.flag_token` → legacy rule의 `flag_token` → `DEFAULT_FLAG_TOKENS[vuln]` 순으로 결정.
      - strict 여부:
        - RuleSpec가 존재하면 `require_flag == True` 이면서 `flag_required_mode == "strict"`일 때 strict로 판단.
        - RuleSpec가 없을 경우 기존 legacy rule의 `strict_flag` 값을 사용.
      - strict 모드 && 플래그 토큰이 존재할 때는 manifest 어디에도 해당 literal이 없으면 오류:  
        `flag token '<TOKEN>' missing from manifest` (검사는 `poc` dict 및 `files[].content` 전체를 대상으로 수행).

- **role 기반 파일 식별 (Generator 쪽)**
  - `SynthesisEngine._fallback_manifest()`:
    - fallback manifest의 `files[]` 항목에 역할(role)을 명시했다.
      - `Dockerfile` / `requirements.txt`: `role: "helper"`
      - `app.py`: `role: "service_main"`
      - `schema.sql`: `role: "schema"`
      - `seed_data.sql`: `role: "seed_data"`
      - `poc.py`: `role: "poc_entry"`
  - `_ensure_fallback_poc()`:
    - LLM manifest에 `poc.py`가 없을 때 자동으로 추가하는 PoC 파일에도 `role: "poc_entry"`를 부여한다.
  - `_poc_contains()`:
    - 기존에는 `manifest.poc` 및 `files[].path.endswith("poc.py")`만 확인했으나, 이제 우선 `files[].role == "poc_entry"`인 항목의 `content`를 검사하고, 없을 때에만 `poc.py` 후행 매칭으로 폴백한다.
    - 이를 통해 향후 manifest가 다양한 PoC 파일명을 사용할 때도 role만 맞추면 가드가 제대로 작동한다.

- **현재 Generator/템플릿/role 구현 상태 요약**
  - **완료된 부분 (체크리스트 기준)**:
    - 3-3: “synthesis 가드에서 하드코딩된 문자열/파일명을 제거하고 RuleSpec + role 기반 로직으로 대체”  
      - 성공 시그니처는 RuleSpec.runtime.success_text_markers 기준으로, 플래그 토큰은 RuleSpec 정책(require_flag, flag_required_mode) 기준으로 검사하도록 일반화했다.
      - `poc.py` 경로 전제는 완전히 제거되진 않았지만, `files[].role == "poc_entry"`가 우선되고, 경로 기반 검사는 호환성을 위한 폴백 역할만 한다.
    - 5-1 (부분): manifest 쪽 `files[].role` 필드 도입 및 fallback manifest/자동 생성 PoC에 역할 정의가 포함되었다.
  - **남은 작업/주의점 (후속 구현자가 참고할 사항)**:
    - 3-1, 3-2:
      - LLM이 실제로 `verification_spec` JSON을 생성하고, Researcher/Generator가 이를 파싱해 runtime rule(`runtime` 블록)을 구성하는 로직은 4차 업데이트에서 Researcher 경로를 통해 1차 구현되었다. 현재는 Researcher 리포트의 상위 `verification_spec` 또는 `verification_specs[CWE]` 블록을 읽어 v2 rule YAML(runtime 섹션 포함)로 직렬화하며, `agents/generator/service.py`와 Verifier는 `RuleSpec.runtime`을 통해 이를 재사용한다.
    - 5-1 (템플릿 메타데이터 측면):
      - `workspaces/templates/**/template.json`에는 4차 기준으로 `scenario_type`, `service_entry`, `poc_entry`, `flag_token` 등의 메타데이터가 추가되었으며, `TemplateRegistry`는 이를 `TemplateSpec.scenario_type` 등으로 노출한다. 아직 이 정보가 eval 쪽에서 직접 사용되지는 않지만, 템플릿 선택 및 runtime rule 설계 시 참고 가능한 기반은 마련된 상태이다.
    - 5-2:
      - 현재 role을 적극적으로 사용하는 곳은 Generator의 PoC 관련 가드 및 manifest 수준(`files[].role`)이며, Researcher 쪽에는 아직 role 기반 탐색/검증 로직이 들어가 있지 않다.
      - `evals/poc_verifier/rule_based._workspace_candidates`는 이제 `generator_manifest.json`의 `workspace_root` 필드를 우선 사용해 단일 workspace 디렉터리를 결정하고, 해당 정보가 없을 때에만 `workspaces/<SID>/app[/<slug>]` 구조로 폴백한다. manifest의 파일/role 목록만으로 workspace_dirs를 구성하는 완전한 role/manifest 기반 탐색은 여전히 후속 리팩터링 과제로 남아 있다.

이 4차 업데이트까지 적용된 상태에서는, **RuleSpec/runtime → Researcher runtime rule 직렬화 → Generator 가드 → Template/manifest 역할 힌트**까지의 데이터 흐름이 한 단계 더 정렬되었으며, 남은 일은 주로 (1) eval/researcher 쪽에서 role/manifest 정보를 적극 활용하는 부분, (2) docs/evals/rules/*.yaml v2 스키마로의 완전 이관을 마무리하는 것이다. 이 문서(특히 11·13·16절)를 기반으로 이후 단계 구현을 이어가면 된다.

## 17. 미구현/부분 구현 항목 정리 (현 시점 기준)

아래 항목들은 상기 1~16절에서 제시한 설계/계획 중 **아직 구현되지 않았거나 부분적으로만 구현된 부분**을 요약한 것이다. 후속 작업 시 “무엇을 더 손봐야 하는지”를 빠르게 파악하는 체크리스트로 사용한다.

1. **Scenario 유형/시나리오 타입(scenario_type) 활용**
   - BaseScenarioVerifier:
     - `expected_signature()`, `verify_log()`, `verify_patterns()`를 공통 인터페이스로 도입했다. 기본 구현은 RuleSpec.runtime 기반으로 성공 시그니처/FLAG 요약을 제공하고(`expected_signature()`), 별도 오버라이드가 없을 경우 `verify_log()`는 `verify()`에 위임해 기존 시나리오와의 호환성을 유지한다. 시나리오별 세분화된 로직은 하위 클래스에서 선택적으로 오버라이드할 수 있다.
   - 시나리오 유형:
     - SQLi/CSRF 플러그인은 `RuleBasedScenario`에 위임하는 `SqlInjectionScenario`/`CsrfScenario`로 등록되어 있으며, `scenario_type == "web-poc"`는 `_scenario_for_type()`을 통해 기본적으로 RuleBasedScenario를 선택한다.
     - `SignatureOnlyScenario`, `HttpEffectScenario`, `FileMutationScenario`를 `RuleBasedScenario`의 thin subclass로 정의하고, `_scenario_for_type()`에서 `scenario_type` 값(`signature_only`, `http_effect`, `file_mutation`)에 따라 자동으로 해당 클래스를 선택하도록 연결했다. 현재는 모두 rule 기반 검증 로직을 공유하며, HTTP 효과/파일 변이 전용 검증 로직은 후속 확장 여지가 있다.

2. **RuleSpec ↔ template metadata/manifest 통합**
   - Template 메타데이터:
     - `workspaces/templates/**/template.json`에 정의된 `scenario_type`, `service_entry`, `poc_entry`, `flag_token` 값은 이제 `common.rules.load_rulespec()`에서 스캔되어 RuleSpec.scenario_type / RuleSpec.service_entry / RuleSpec.poc_entry / RuleSpec.template_flag_token 및 `runtime.flag_token` 보강에 사용된다. 이를 통해 Generator/Verifier/Researcher가 템플릿 메타데이터를 공유하는 단일 정책 계층을 갖게 되었다.
	   - manifest/placeholder 연동(부분 구현에서 추가 진전):
     - Generator:
       - `agents/generator/synthesis.SynthesisEngine._guard_manifest()`에서 `patterns[].type == "file_contains"`의 `path: \"{{service_entry}}\"`를 `role == \"service_main\"` 파일(또는 `app.py` 폴백)로 해석하는 `_resolve_rule_path()`를 도입했다.
     - eval:
       - `evals/poc_verifier/rule_based._evaluate_patterns()`는 `metadata/<SID>/generator_manifest.json`을 읽어 `files[].role`을 기반으로 `{{service_entry}}`/`{{poc_entry}}` placeholder를 실제 경로(예: 서비스 엔트리, PoC 엔트리)로 치환한 뒤 workspace 내 파일을 검사한다.
       - workspace 디렉터리를 찾지 못하더라도, generator_manifest의 `manifest.files[].content`만으로 패턴 검사를 수행할 수 있도록 `_manifest_file_contains()` 경로를 추가해 workspace 구조에 대한 의존성을 줄였다. placeholder 해석 시에는 generator_manifest → RuleSpec.service_entry/poc_entry → 전통적인 `app.py`/`poc.py` 순으로 폴백한다.
	     - 남은 부분:
	       - 다중 템플릿 환경에서 “어떤 템플릿의 메타데이터를 RuleSpec에 매핑할지”는 `evals/poc_verifier/scenarios.build_evaluation_context()`가 `generator_template.json`(metadata/<SID>/[bundles/<slug>/])을 읽어 runtime 템플릿 메타데이터를 RuleSpec에 오버레이하는 경로로 1차 구현되었다. 다만 manifest/템플릿 경로를 RuleSpec/runtime 쪽으로 완전히 역주입해, 모든 컴포넌트가 동일한 declared source만을 참조하도록 만드는 작업은 여전히 후속 과제로 남아 있다.

	3. **role 기반 eval/researcher 리팩터링**
   - Generator:
     - `files[].role` 기반 PoC 식별(`_poc_contains()`), flag 토큰 강제, `{{service_entry}}` placeholder 해석 등은 Generator 가드 레벨에서 대부분 구현되었다.
	   - eval:
	     - `rule_based._workspace_candidates()`는 `generator_manifest.json`의 `workspace_root`(존재 시)를 우선 사용해 workspace 루트를 결정하고, 해당 정보가 없을 때에만 `workspaces/<SID>/app[/<slug>]` 디렉터리 패턴으로 폴백한다.
	     - `patterns[].type == \"poc_contains\"`/`\"file_contains\"`는 `{{poc_entry}}`/`{{service_entry}}` placeholder를 generator_manifest의 역할 정보(`role == \"poc_entry\"`/`\"service_main\"`)와 RuleSpec의 service_entry/poc_entry 메타데이터를 활용해 실제 경로(서비스 엔트리, PoC 엔트리 등)로 해석한 뒤 검사를 수행한다.
	     - workspace 디렉터리가 비어 있거나 접근 불가능한 경우에도, generator_manifest의 파일 내용만으로 패턴 검사를 수행하는 manifest-only 경로가 유지되며, 향후에는 manifest의 파일/role 목록만으로 workspace_dirs를 구성하는 완전한 role/manifest 기반 탐색을 도입할 여지가 있다.
   - Researcher:
     - ResearcherService는 template metadata의 role 정보를 활용하지 않고 있으며, 검증/분석 로직이 role/manifest 정보와 정렬되도록 리포트 스키마/후처리를 확장하는 작업이 남아 있다.

4. **RuleSpec 기반 LLM 정책·프롬프트 고도화**
   - 현재 상태:
     - `llm_assisted_verify()`는 RuleSpec.runtime.assertion_program을 LLM 호출 전에 항상 실행하고, assertion 성공 시 LLM 호출 없이 PASS를 반환한다.
     - `_effective_llm_config()` 헬퍼를 도입해 plan/requirement의 `policy.verifier.*`와 RuleSpec.llm_* 필드를 합성한 단일 config를 만든 뒤, 여기서 `llm_assist`, `assertion_budget`, `log_excerpt_chars` 등을 일관되게 해석한다. `llm_assist`가 명시되지 않으면 RuleSpec.llm_assist_default를, assertion_budget이 비어 있으면 RuleSpec.assertion_budget을 기본값으로 사용한다.
     - LLM이 제안한 assertion 목록은 합성된 config의 `assertion_budget`을 상한으로 잘라 `run_assertions()`에 전달하며, 메타데이터에 `assertions_checked`를 기록한다.
     - `registry.evaluate_with_vuln()`는 RuleSpec에서 요약한 정보를 `evidence_rules`로 구성해 `build_llm_verifier_prompt()`에 전달하며, 여기에는 verification/output/runtime/llm 정보뿐 아니라 템플릿 메타데이터에서 채운 service_entry/poc_entry/flag_token 요약도 포함된다.
   - 남은 부분:
     - vuln/케이스별 override, 전역 실험 플래그 등 “정책 레이어”를 별도 모듈로 분리하고, plan/requirement/Runspec 간 우선순위를 더 명확히 문서화하는 작업은 여전히 남아 있다.
     - evidence_rules에 포함되는 RuleSpec 요약 구조를 runtime assertion 요약, scenario_type별 힌트 등으로 더 정교화하는 것은 후속 개선 여지가 있다.

위 미구현/부분 구현 항목들은, 1~16절에서 정의한 추상화와 실제 코드 사이의 “마지막 간극”에 해당한다. 향후 작업자는 이 섹션을 기준으로 우선순위를 잡아, (1) RuleSpec/템플릿/manifest/role을 중심으로 한 단일 정책 계층을 완성하고, (2) eval/researcher/generator가 모두 이 계층을 일관되게 참조하도록 리팩터링을 진행하면 된다.
