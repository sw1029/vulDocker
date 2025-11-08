# Generator Manifest Schema

합성(템플릿 없는) Generator가 산출하는 JSON 매니페스트 규격이다. TODO 14.5 이후 모든 `generator_mode: synthesis|hybrid` 경로는 이 스키마를 따르고, 문서는 `docs/architecture/agents_contracts.md` 및 `docs/milestones/todo_13-15_code_plan.md`에 정의된 계약과 연동된다.

## 1. 최상위 필드

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `intent` | string | 시나리오 개요(예: `"CWE-89 / login bypass"`). |
| `pattern_tags` | string[] | 적용한 취약 패턴 태그. 최소 1개. |
| `files` | object[] | 생성할 파일 목록. 아래 **파일 엔트리** 참조. |
| `deps` | string[] | 고정 버전 의존성(예: `"Flask==2.3.3"`). SBOM 추적용. |
| `build` | object | `command`(필수), `env`(선택) 등의 빌드 지시. |
| `run` | object | `command`, `healthcheck`, `port` 등 실행 정보. |
| `poc` | object | `cmd`와 `success_signature`(필수), `notes`(선택). |
| `notes` | string | 교육/재현 메모. SBOM·정책 게이트 참고. |
| `metadata` | object | `seed`, `stack`, `cwe`, `sid` 등 추가 메타. |

## 2. 파일 엔트리

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `path` | string | ✅ | 허용 화이트리스트 경로만 사용(`Dockerfile`, `app.py`, `requirements.txt`, `schema.sql`, `seed_data.sql`, `poc.py`, `README.md` 등). Relative path, no `..`. |
| `description` | string | ✅ | 파일 목적. Reviewer/Manifest 감사 로그에서 활용. |
| `content` | string | ✅ | 파일 본문. 64KB 이하. |
| `encoding` | string | ❌ | 기본 `plain`. base64 필요 시 명시. |

## 3. 제약 조건

* `files` 길이는 PLAN 단계에서 주어진 `synthesis_limits.max_files` 이하.
* 각 파일은 `synthesis_limits.max_bytes_per_file` 이하.
* 경로는 allowlist(PLAN→`plan.json.requirement.synthesis_limits.allowlist`) 안에 있어야 하며, 디렉터리 traversal 금지.
* `poc.success_signature`는 `SQLi SUCCESS` 문자열을 반드시 포함하여 `evals/poc_verifier/mvp_sqli.py`와 호환.
* 모든 문자열은 UTF-8, ASCII 기본 권장.

## 4. 예시

```json
{
  "intent": "CWE-89 login bypass via Flask + SQLite",
  "pattern_tags": ["sqli", "string-concat"],
  "files": [
    {
      "path": "app.py",
      "description": "Flask app with unsafe login",
      "content": "from flask import Flask, request..."
    },
    {
      "path": "Dockerfile",
      "description": "Builds the vulnerable image",
      "content": "FROM python:3.11-slim\nCOPY . /app\n..."
    }
  ],
  "deps": ["Flask==2.3.3", "Jinja2==3.1.4"],
  "build": {"command": "pip install -r requirements.txt"},
  "run": {"command": "python app.py", "port": 8000},
  "poc": {"cmd": "python poc.py", "success_signature": "SQLi SUCCESS"},
  "notes": "Seed DB created via schema.sql on build stage.",
  "metadata": {"stack": "python-flask", "cwe": "CWE-89"}
}
```

## 5. 산출물 기록 위치

선택된 매니페스트는 `metadata/<SID>/generator_manifest.json`에 기록한다. 동시 생성된 후보 점수/가드는 `metadata/<SID>/generator_candidates.json`에 JSON 배열로 보존하여 `docs/variability_repro/design.md`에서 요구하는 재현성 트레이스를 유지한다.
