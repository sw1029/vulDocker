# vulDocker 하드코딩 및 분기 구조 개선 방안

vulDocker 프로젝트의 현재 코드는 취약점 검증, PoC 성공 판정, 템플릿 선택 등 여러 부분에서 하드코딩된 상수나 단순 분기 구조를 사용하고 있습니다. 이를 **LLM 기반의 완전 자동화 취약 이미지 생성**을 지원하고, **범용성과 확장성**을 높이는 방향으로 재구성하기 위해 아래와 같은 개선을 제안합니다. 각 항목에서는 기존의 하드코딩/분기 패턴을 지적하고, 새로운 **논리 구조**를 설명한 후, **Python 의사코드**로 예시를 제공합니다.

## 취약점별 검증 규칙의 데이터 드리븐 전환

**개선 전 패턴:** 각 취약점의 **검증 로직**이 코드에 직접 하드코딩되어 있습니다. 예를 들어 CSRF 취약점 검증기는 run.log 파일에서 "CSRF SUCCESS" 문자열과 "FLAG" 토큰을 찾는 방식으로 성공 여부를 판단합니다[\[1\]](https://github.com/sw1029/vulDocker/blob/2ec2581cadb78efe20041b605fe40b8f8684840b/README.md#L54-L56)[\[2\]](https://github.com/sw1029/vulDocker/blob/2ec2581cadb78efe20041b605fe40b8f8684840b/evals/poc_verifier/csrf.py#L12-L19). 이러한 문자열 패턴은 코드에 고정되어 있어 새로운 취약점을 추가하거나 기준을 변경할 때 코드 수정이 필요합니다.

**개선 구조:** 취약점별 **검증 규칙을 YAML 등 외부 규칙 파일**로 분리하여 **데이터 기반**으로 관리합니다. 각 취약점에 대한 성공 시그니처나 필요한 토큰을 rules.yaml과 같은 파일에 정의하고 자동 로드합니다. 검증 로직은 **일반화된 함수** 하나로 구현하여, 주어진 vuln_id에 해당하는 규칙 데이터를 불러와서 검증합니다. 이렇게 하면 **규칙 파일을 추가/수정**하는 것만으로 검증 기준을 변경할 수 있어 유연성이 높아집니다[\[3\]](https://github.com/sw1029/vulDocker/blob/2ec2581cadb78efe20041b605fe40b8f8684840b/docs/evals/rules/cwe-89.yaml#L2-L4). 예를 들어 CWE-89(SQLi)의 규칙 파일에 성공 문자열과 플래그 토큰을 정의해 두고, 코드에서는 이를 읽어 검사하도록 합니다.

**예시 의사코드:**

\# YAML 규칙 로더 (예: rules/cwe-89.yaml에 정의된 내용 로드)  
rule = load_rule(vuln_id) # vuln_id에 대응하는 YAML 규칙을 dict로 로드  
<br/>log_text = log_path.read_text(encoding="utf-8")  
success_sig = rule.get("success_signature") # 예: "SQLi SUCCESS"  
flag_token = rule.get("flag_token") # 예: "FLAG-sqli-demo-token"  
<br/>\# 규칙에 정의된 모든 패턴을 검사하여 성공 여부 판단  
if success_sig and flag_token:  
verify_pass = (success_sig in log_text) and (flag_token in log_text)  
else:  
\# success_signature 또는 flag_token이 정의되지 않은 경우 대비  
verify_pass = False  
<br/>evidence = \[\]  
if success_sig in log_text:  
evidence.append(f"Found signature: {success_sig}")  
if flag_token in log_text:  
evidence.append(f"Found flag token: {flag_token}")  
<br/>result = {  
"verify_pass": verify_pass,  
"evidence": ", ".join(evidence) if evidence else "No signature",  
"log_path": str(log_path),  
"status": "evaluated"  
}  
return result

위 의사코드에서는 **규칙 파일에 정의된 문자열**들을 기반으로 검증하며, 새 취약점에 대한 규칙 파일만 추가하면 동일한 로직으로 자동 처리됩니다.

## 검증기 (register_verifier) 구조의 일반화

**개선 전 패턴:** 현재 각 취약점별로 별도 모듈을 만들어 일일이 register_verifier(\[...\], func)를 호출해 검증 함수를 등록하고 있습니다. 예를 들어 CSRF의 경우 register_verifier(\["CWE-352", "csrf"\], \_evaluate_csrf_log)와 같이 해당 함수와 취약점 ID를 수동으로 연결합니다[\[4\]](https://github.com/sw1029/vulDocker/blob/2ec2581cadb78efe20041b605fe40b8f8684840b/evals/poc_verifier/csrf.py#L28-L29). 새로운 취약점을 지원하려면 새로운 파일을 만들고 비슷한 패턴으로 등록해야 하는 등 **반복적 수작업**이 필요합니다.

**개선 구조:** 검증기 레지스트리를 **동적으로 구성**하여 **일반화**합니다. 전체 취약점에 대한 검증 함수를 한 곳에서 관리하고, **자동 등록 메커니즘**을 도입합니다. 두 가지 방향을 고려할 수 있습니다:

- _데이터 드리븐 등록:_ 앞서 언급한 **규칙 파일 목록을 스캔**하여, 각 취약점 ID에 대해 **공통 검증 함수**(예: 앞 절의 verify_with_rule)를 **자동 등록**합니다. 코드가 실행될 때 docs/evals/rules/ 디렉토리의 YAML 파일들을 훑어서, 존재하는 모든 vuln_id에 대해 하나의 검증 함수를 레지스트리에 추가하는 방식입니다. 이렇게 하면 새로운 규칙 파일 추가 시 코드 수정 없이도 검증이 등록됩니다.
- _플러그인 자동 로드:_ 혹은 evals/poc_verifier/ 폴더의 Python 파일들을 동적으로 import하여, 각 파일 내의 register_verifier 호출이 자동 실행되게 할 수 있습니다. 이를 위해 pkgutil.iter_modules나 importlib을 이용해 해당 디렉토리의 모든 모듈을 가져오면, 모듈 내에서 정의된 검증기가 자동으로 레지스트리에 포함됩니다. 이 방식은 **폴더 스캔**을 통해 플러그인을 등록하므로, 신규 취약점 모듈을 추가하면 코드를 손대지 않아도 가져올 수 있습니다.

**예시 의사코드 (규칙 기반 등록):**

\# 규칙 디렉토리를 스캔하여 검증기 자동 등록  
for rule_file in Path("docs/evals/rules").glob("\*.yaml"):  
vuln_id = parse_vuln_id_from_filename(rule_file.name) # e.g., "cwe-89.yaml" -> "CWE-89"  
def verifier_func(log_path: Path, vid=vuln_id):  
\# vid를 클로저로 캡쳐하여 해당 취약점에 대한 검증 수행  
return evaluate_log_with_rule(vid, log_path)  
register_verifier(\[vuln_id\], verifier_func)  
<br/>\# 혹은 플러그인 모듈 자동 로드 방식:  
import importlib, pkgutil  
for \_, module_name, _in pkgutil.iter_modules(\["evals/poc_verifier"\]):  
if module_name != "registry": # 레지스트리 자체는 제외  
importlib.import_module(f"evals.poc_verifier.{module_name}")

위 방법들을 통해 **검증기 추가/확장**이 용이해지며, **중복 코드를 줄이고** 구조를 유연하게 바꿀 수 있습니다. 예컨대 새로운 CWE 규칙 파일을 추가하면 자동으로 해당 검증이 등록되고, 별도 코딩 없이 LLM 보조 검증까지 활용할 수 있게 됩니다.

## PoC 성공 판정 방식의 유연화 (JSON 또는 플래그 기반)

**개선 전 패턴:** PoC 실행 성공 여부는 주로 **로그의 특정 문자열** 존재로만 판단합니다. 예를 들어 SQLi나 CSRF의 경우 run.log에 "SUCCESS" 키워드와 "FLAG" 문자열이 모두 포함되면 성공으로 간주하는 방식입니다[\[1\]](https://github.com/sw1029/vulDocker/blob/2ec2581cadb78efe20041b605fe40b8f8684840b/README.md#L54-L56). 이러한 접근은 출력 형식이 **고정적(Text 기반)**이라는 전제가 있습니다.

**개선 구조:** PoC 결과 **출력 형식의 다양성**을 고려하여 **유연한 성공 판정 로직**을 도입합니다. **JSON 출력**이나 특정 **플래그 파일/토큰** 기반의 확인도 지원해야 합니다. 이를 위해 다음과 같은 방안을 적용합니다:

- **JSON 기반 판정:** 만약 PoC가 JSON 형식으로 결과를 출력하도록 구현되었다면(run.log가 JSON이거나 별도 JSON 결과 파일 존재), 해당 내용을 파싱하여 {"success": true} 혹은 {"flag": "FLAG{...}"} 등의 키를 검사합니다. 예를 들어 결과 JSON에 success 필드가 있다면 그 값이 True인지 확인하거나, flag 필드에 값이 존재하면 성공으로 처리합니다. 이처럼 **구조적 출력**을 해석하여 성공 여부를 유도합니다.
- **텍스트 기반 판정:** 기존처럼 일반 텍스트 로그의 경우 **규칙 파일에 정의된 성공 시그니처/토큰**을 검사합니다. 각 CWE별 YAML에 success_signature나 flag_token이 정의되어 있다면 이를 기준으로 문자열 포함 여부를 확인합니다[\[3\]](https://github.com/sw1029/vulDocker/blob/2ec2581cadb78efe20041b605fe40b8f8684840b/docs/evals/rules/cwe-89.yaml#L2-L4). 플래그 문자열 패턴(예: "FLAG" 또는 특정 prefix의 토큰)이 발견되면 성공으로 간주할 수 있습니다.
- **포괄 로직:** 코드 구현 시 우선 출력이 JSON인지 시도해보고, 아니라면 텍스트로 처리하는 **이중 절차**를 둡니다. 또한 필요에 따라 **추가 정책**을 적용할 수 있습니다 (예: 프로세스 **exit code**나 특정 파일 생성 여부 등을 확인) - 이런 정책 역시 데이터로 정의 가능하게 합니다.

**예시 의사코드:**

log_content = log_path.read_text(encoding="utf-8")  
<br/>\# 우선 JSON 포맷 시도  
try:  
result_data = json.loads(log_content)  
\# JSON에 success나 flag 키가 있는지 확인  
if result_data.get("success") is True:  
verify_pass = True  
elif result_data.get("flag"):  
verify_pass = True  
else:  
verify_pass = False  
evidence = f"JSON output: {result_data}"  
except ValueError:  
\# JSON 파싱이 안 되면 일반 텍스트로 처리  
rule = load_rule(vuln_id)  
sig = rule.get("success_signature")  
token = rule.get("flag_token")  
verify_pass = False  
evidence_list = \[\]  
if sig and sig in log_content:  
evidence_list.append(f"Found signature: {sig}")  
if token and token in log_content:  
evidence_list.append(f"Found flag: {token}")  
if evidence_list and sig and token:  
verify_pass = True # 시그니처와 플래그 모두 발견 시 성공  
evidence = ", ".join(evidence_list) if evidence_list else "No success markers"  
<br/>result = {  
"verify_pass": verify_pass,  
"evidence": evidence,  
"log_path": str(log_path),  
"status": "evaluated"  
}

위 의사코드는 **JSON 출력**을 우선 탐지하여 처리하고, 실패하면 **텍스트 기반** 검사로 넘어갑니다. 이처럼 로직을 확장함으로써 PoC가 어떤 형식으로 결과를 내놓든 유연하게 대응할 수 있습니다. 규칙 파일에도 출력 형식이나 키워드에 대한 정보를 추가해 두면 (예: output_format: json, success_key: success 등) 더욱 **데이터 주도적인 판정**이 가능할 것입니다.

## 템플릿 재사용 구조의 일반화 및 LLM 결과의 보완 처리

**개선 전 패턴:** 현재 Generator 단계에서는 **LLM을 통해 코드를 합성**하고, 일부 경우 **정적 템플릿**을 조합하여 사용하는 **하이브리드 접근**을 취합니다[\[5\]](https://github.com/sw1029/vulDocker/blob/2ec2581cadb78efe20041b605fe40b8f8684840b/docs/handbook.md#L36-L40). 그러나 템플릿 활용이 체계화되어 있지 않거나, LLM이 생성한 코드와 템플릿 간 결합이 수동적으로 이뤄질 수 있습니다. 또한 LLM이 생성한 결과물에 **검증용 시그니처**나 **필수 구성요소**(예: 플래그 출력 코드)가 누락될 가능성이 있습니다.

**개선 구조:** **템플릿 재사용을 일반화**하고 **LLM 결과를 보완**하는 파이프라인을 확립합니다. 주요 아이디어는 다음과 같습니다.

- **템플릿 디스커버리/메타데이터:** 템플릿들을 일일이 지정하지 않고, **폴더 구조와 메타데이터를 활용한 탐색**을 수행합니다. 예를 들어 workspaces/templates/&lt;vuln&gt;/&lt;variant&gt;/template.json 등의 메타파일을 두고, 이를 **스캔하여 사용 가능한 템플릿 목록**을 구성합니다. 이미 TemplateRegistry가 template.json을 rglob하여 템플릿을 모으는 방식이 사용되고 있는데[\[6\]](https://github.com/sw1029/vulDocker/blob/2ec2581cadb78efe20041b605fe40b8f8684840b/agents/generator/service.py#L131-L139), 이러한 구조를 강화해 **새 템플릿 추가 시 자동 인식**되도록 합니다. TemplateSpec 등에 CWE ID, 패턴 ID, 사용 기술(stack) 등이 메타데이터로 포함되어 템플릿 선택에 활용됩니다.
- **LLM+템플릿 결합:** Generator에서는 우선 **해당 취약점에 적합한 템플릿**이 있는지 확인합니다. 템플릿이 있으면 이를 **기본 뼈대**로 사용하고, 세부 취약 코드를 **LLM 출력으로 채웁니다**. 예를 들어 Flask 기반 SQLi 템플릿이 있다면, 데이터베이스 초기화나 기본 라우팅 코드는 템플릿을 쓰고, 실제 취약한 쿼리 부분은 LLM에게 생성시키되 템플릿에 미리 표시된 **플레이스홀더** 위치에 삽입합니다. 템플릿이 없거나 템플릿이 특정 부분을 커버하지 못하면, **LLM 합성으로 대체**하되, 템플릿에서 재사용 가능한 부분(예: 공통 Dockerfile, 공통 import 등)은 가져옵니다.
- **LLM 결과 보완 처리:** LLM이 생성한 코드가 **검증 요구사항**을 만족하는지 검사하고 부족한 부분을 채웁니다. 예컨데 검증 플러그인이 요구하는 "SUCCESS" 문자열 출력이 누락되었다면, 결과 코드에 print("...SUCCESS...") 구문을 추가하거나, 프롬프트 단계에서 이러한 요소를 포함하도록 지시할 수 있습니다. 또한 템플릿에 미리 정의된 **플래그 토큰**이나 **실패 처리 로직** 등이 있다면, LLM 코드와 합칠 때 충돌 없이 포함되도록 합니다. 이러한 보완 작업은 **자동화된 후처리** 단계로 두어, LLM 산출물을 검증 규칙과 대조하며 수행합니다 (예: 규칙에 flag_token이 정의되어 있고 LLM 생성 코드에 해당 문자열이 없다면 추가).

**예시 의사코드:**

\# 1. 템플릿 선택 단계  
template_registry = TemplateRegistry() # 템플릿 폴더 스캔하여 목록 구축  
template = template_registry.find(vuln_id=vuln_id, framework=req.framework, pattern=req.pattern_id)  
\# (find 함수는 vuln_id 및 기타 요구사항에 맞는 템플릿을 검색한다고 가정)  
<br/>\# 2. 템플릿 기반 코드 생성을 시도  
if template:  
base_code_files = template.load() # 템플릿의 기본 코드 (dict: 파일명->내용)  
\# 예: app.py, Dockerfile 등 미리 준비된 코드 골격 불러오기  
snippet_prompt = build_vuln_snippet_prompt(vuln_id, template.metadata)  
vuln_snippet = llm.generate(snippet_prompt) # LLM으로 취약 부분 코드 생성  
\# 플레이스홀더 치환: 예를 들어 템플릿의 app.py에 "{{payload_code}}" 자리에 vuln_snippet 삽입  
integrated_code = merge_into_template(base_code_files\["app.py"\], vuln_snippet)  
base_code_files\["app.py"\] = integrated_code  
else:  
\# 템플릿이 없으면 LLM 합성에 의존  
full_app_code = llm.generate(full_app_prompt(vuln_id, req))  
base_code_files = {"app.py": full_app_code, "Dockerfile": default_dockerfile_for(req), ...}  
<br/>\# 3. LLM 결과 보완 처리 단계  
rule = load_rule(vuln_id)  
sig = rule.get("success_signature")  
flag = rule.get("flag_token")  
app_code = base_code_files\["app.py"\]  
\# 검증 시그니처 출력문 보강  
if sig and sig not in app_code:  
app_code += f'\\nprint("{sig}") # Ensure success signature present\\n'  
\# 플래그 토큰 보강 (예: 실행 중 노출용 출력)  
if flag and flag not in app_code:  
app_code = app_code.replace("SENSITIVE_DATA", flag)  
base_code_files\["app.py"\] = app_code  
<br/>\# 4. 완성된 코드 워크스페이스에 기록  
for fname, content in base_code_files.items():  
write_file(workspace_path / fname, content)

위 의사코드에서는 **템플릿 탐색** → **LLM 코드 생성** → **병합** → **보완 처리**의 논리 단위로 구성됩니다. 템플릿이 존재하면 활용하고, LLM은 부족한 부분만 채우도록 하며, 마지막에 검증 기준에 맞게 결과물을 보정합니다. 이로써 LLM의 창의성과 템플릿의 안정성이 결합되고, 새로운 패턴에도 **범용적으로 대응**할 수 있습니다.

## enum-like 하드 분기 구조의 동적 구성

**개선 전 패턴:** 시스템 전반에서 **열거형 상수나 리스트에 기반한 분기**가 존재하는 경우, 새로운 값 추가 시 코드 변경이 필요했습니다. 예를 들어 지원하는 취약점 ID, 취약 패턴, 데이터베이스 종류 등이 코드에 **하드코딩된 열거**나 if-elif **분기문 형태**로 구현되었다면, 이는 확장 시 매번 수정과 재배포가 필요합니다. (가령, 'supported_vulns = \["CWE-89","CWE-352",...\]' 식으로 나열하거나, "if vuln_id == 'CWE-89': ... elif vuln_id == 'CWE-352': ..." 같은 분기 구조 등이 해당합니다.)

**개선 구조:** **동적 스캔**을 통해 분기 구조를 **자동 구성**함으로써, enum-like 하드코딩을 제거합니다. 즉, 코드가 실행 시점에 **파일 시스템이나 설정을 조회하여** 가능한 옵션들을 수집하고 그에 따라 동적으로 동작하도록 합니다. 이 접근은 앞서 제시한 몇 가지 개선과 맥락을 같이합니다:

- **폴더 스캔으로 열거 대체:** 예를 들어 템플릿의 종류나 취약점 지원 목록을 얻기 위해 workspaces/templates 하위에 존재하는 디렉토리를 나열하거나, docs/evals/rules 폴더의 파일명을 조사하여 **지원 CWE 리스트**를 산출할 수 있습니다. 이렇게 얻은 목록으로 UI나 파이프라인을 구동하면, 새로운 폴더/파일 추가만으로 지원 항목이 자동 반영됩니다.
- **규칙/메타데이터 스캔:** enum 대신 **메타데이터 필드**를 활용하는 방법입니다. 예를 들어 TemplateSpec에 requires_external_db 같은 필드를 두고, 코드에서 데이터베이스 종류별 분기를 하드코딩하는 대신 템플릿 메타정보를 참고하여 결정합니다. 나아가, 특정 기능 활성화 여부도 plan이나 requirement의 필드로 일반화해 (features: {...} 섹션 등) 분기문을 줄입니다.
- **플러그인 구조 활용:** 지원 기능별로 클래스를 플러그인화하고, 실행 시점에 등록된 플러그인들을 순회하며 처리하는 구조로 바꾸면 일일이 분기문을 작성하지 않아도 됩니다. Python의 경우 앞서 언급한 방식으로 동적으로 import된 모듈이나 등록된 함수들을 기준으로 동작하게 할 수 있습니다. 예를 들어, 여러 종류의 데이터베이스 초기화 스크립트를 지원하는 코드를 DATABASE_PLUGINS 딕셔너리에 등록해 두고, 실제 실행 시 db_type 키로 찾아 실행하도록 하면 if-elif 없이 확장 가능합니다.

**예시 의사코드:**

\# (1) 규칙 파일 스캔을 통한 vuln_id 열거 자동화  
supported_vulns = \[\]  
for rule_file in Path("docs/evals/rules").glob("\*.yaml"):  
vid = parse_vuln_id_from_filename(rule_file.name) # "cwe-89.yaml" -> "CWE-89"  
supported_vulns.append(vid)  
\# 이제 supported_vulns 리스트가 코드 하드코딩 없이 동적으로 구성되었음  
<br/>\# (2) 템플릿 디렉토리 스캔을 통한 패턴 열거 자동화  
template_root = Path("workspaces/templates")  
available_patterns = \[tpl_dir.name for tpl_dir in template_root.iterdir() if tpl_dir.is_dir()\]  
\# templates 하위의 모든 폴더명을 취약 패턴으로 간주 (예: "flask_sqlite_raw", "flask_mysql_union" 등)  
<br/>\# (3) 플러그인 맵을 통한 분기 대체  
DATABASE_INIT_HANDLERS = {} # 빈 딕셔너리로 두고, 각 모듈에서 자동 등록  
\# 예: mysql_init.py 모듈 내에서 DATABASE_INIT_HANDLERS\["mysql"\] = init_mysql 함수를 등록  
for db_name, init_func in DATABASE_INIT_HANDLERS.items():  
if requirement.db_type == db_name:  
init_func() # 해당 DB 초기화 수행

위 의사코드는 세 가지 예시를 보여줍니다. **규칙 파일 스캔**으로 지원 취약점 ID 목록을 자동 생성하고, **템플릿 폴더 스캔**으로 사용 가능한 취약 패턴을 열거하며, **플러그인 맵**으로 데이터베이스 종류별 초기화를 처리하는 구조입니다. 공통적으로 새로운 항목을 추가하려면 **파일이나 메타데이터만 추가**하면 되고, 코드를 수정하지 않아도 로직에 반영됩니다. 이러한 **동적 구성** 덕분에 enum-like 상수나 분기문을 줄이고, 시스템의 **범용성**과 **확장성**을 크게 높일 수 있습니다.

&lt;hr/&gt;

정리하면, 위 개선 방안들은 **전체 시스템에 대한 구조 개편**을 목표로 합니다. 하드코딩된 상수와 분기를 **데이터 드리븐**하고 **플러그인화**된 구조로 대체함으로써, LLM을 통한 자동화된 취약 환경 생성에 유연하게 대응할 수 있습니다. 또한 새로운 취약점 유형이나 패턴, 환경이 생겨도 **코드 수정 없이 추가**될 수 있는 기반을 마련하여, 유지보수성과 확장성을 확보할 수 있습니다. 각 제안은 현재 vulDocker의 동작을 해치지 않는 선에서, **의사코드 수준으로 단순화**하여 보여준 것이며, 실제 적용 시에는 현 구조에 맞춰 세부 조정을 거쳐 구현하게 될 것입니다. [\[1\]](https://github.com/sw1029/vulDocker/blob/2ec2581cadb78efe20041b605fe40b8f8684840b/README.md#L54-L56)[\[5\]](https://github.com/sw1029/vulDocker/blob/2ec2581cadb78efe20041b605fe40b8f8684840b/docs/handbook.md#L36-L40)

[\[1\]](https://github.com/sw1029/vulDocker/blob/2ec2581cadb78efe20041b605fe40b8f8684840b/README.md#L54-L56) README.md

<https://github.com/sw1029/vulDocker/blob/2ec2581cadb78efe20041b605fe40b8f8684840b/README.md>

[\[2\]](https://github.com/sw1029/vulDocker/blob/2ec2581cadb78efe20041b605fe40b8f8684840b/evals/poc_verifier/csrf.py#L12-L19) [\[4\]](https://github.com/sw1029/vulDocker/blob/2ec2581cadb78efe20041b605fe40b8f8684840b/evals/poc_verifier/csrf.py#L28-L29) csrf.py

<https://github.com/sw1029/vulDocker/blob/2ec2581cadb78efe20041b605fe40b8f8684840b/evals/poc_verifier/csrf.py>

[\[3\]](https://github.com/sw1029/vulDocker/blob/2ec2581cadb78efe20041b605fe40b8f8684840b/docs/evals/rules/cwe-89.yaml#L2-L4) cwe-89.yaml

<https://github.com/sw1029/vulDocker/blob/2ec2581cadb78efe20041b605fe40b8f8684840b/docs/evals/rules/cwe-89.yaml>

[\[5\]](https://github.com/sw1029/vulDocker/blob/2ec2581cadb78efe20041b605fe40b8f8684840b/docs/handbook.md#L36-L40) handbook.md

<https://github.com/sw1029/vulDocker/blob/2ec2581cadb78efe20041b605fe40b8f8684840b/docs/handbook.md>

[\[6\]](https://github.com/sw1029/vulDocker/blob/2ec2581cadb78efe20041b605fe40b8f8684840b/agents/generator/service.py#L131-L139) service.py

<https://github.com/sw1029/vulDocker/blob/2ec2581cadb78efe20041b605fe40b8f8684840b/agents/generator/service.py>