# evals 디렉토리

핵심 파일
- evals/poc_verifier/main.py:1 — 번들별 run.log를 수집해 플러그인으로 평가하고 `reports/evals.json` 작성.
- evals/poc_verifier/registry.py:1 — 검증기 레지스트리. 사용자 정의 함수 등록 + rule 기반 폴백/LLM 보조를 담당.
- evals/poc_verifier/rule_based.py:1 — `docs/evals/rules/*.yaml` 스키마를 읽어 공통 검증을 수행(성공 시그니처/flag_token 매칭, JSON 출력 판정 등).
  - run_summary/summary.json을 우선 사용하고, 정책 `plan.policy.verifier.require_exit_code_zero`를 인식합니다.
- evals/poc_verifier/mvp_sqli.py:1 — SQLi 전용 검증기(필요 시 rule 기반 이전 단계에서 실행).
- evals/poc_verifier/csrf.py:1 — CSRF 전용 검증기(존재 시, rule 기반 이전 단계에서 실행).

데이터 계약
- 입력: run/index.json(번들별 실행 기록), run.log(로그), requirement(plan에서 scope).
- 출력: `artifacts/<SID>/reports/evals.json` (overall_pass, results[] 포함).

플러그인 계약
- 함수 시그니처: `def verifier(log_path: Path) -> dict`.
- 결과 권장 필드: verify_pass(bool), evidence(str), status(str: evaluated|unsupported 등), log_path(str).
- 미지원/실패 시 LLM 보조 검증(정책 허용 시)으로 보완.
- 정책 필드 예시: `verifier.require_exit_code_zero`, `verifier.llm_assist`, `verifier.log_excerpt_chars`.
