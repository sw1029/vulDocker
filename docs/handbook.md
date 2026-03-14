# vulDocker 핸드북

Status: support
Audience: operator
Source of truth for: quickstart, command map, artifact locations, troubleshooting entrypoints
Not the source of truth for: current-state assessment, constraints, roadmap
Last validated against: repository commands and representative reruns on 2026-03-14

이 문서는 운영/온보딩용 가이드입니다. 개념 정의와 현재 제약은 요약하지 않고, 어떤 문서를 어디서 읽어야 하는지와 실제 실행 절차만 제공합니다.

canonical 관계:
- 왜 이 프로젝트를 하는가: [docs/problem.md](problem.md)
- 현재 진단은 어디에 적는가: [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)
- 무엇을 주장하면 안 되는가: [docs/constraints.md](constraints.md)
- 무엇을 먼저 구현할 것인가: [docs/final_solution.md](final_solution.md)

## Read Order

1. 문제와 목표: [docs/problem.md](problem.md)
2. 현재 truth: [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)
3. 현재 제약: [docs/constraints.md](constraints.md)
4. 구현 계획: [docs/final_solution.md](final_solution.md)
5. 코드 탐색: [docs/code/README.md](code/README.md)

## Quickstart

사전 요구
- Docker
- Python 3.11+
- `pip install -r requirements.txt`

대표 흐름
1. PLAN: `python orchestrator/plan.py --input inputs/mvp_sqli.yml`
2. 전체 루프: `python orchestrator/run_pipeline.py --sid <SID> --mode deterministic`
3. 단계별 실행이 필요하면 아래 순서를 따릅니다.

단계별 명령
- RESEARCH: `python agents/researcher/main.py --sid <SID> --mode deterministic`
- GENERATE: `python agents/generator/main.py --sid <SID> --mode deterministic`
- EXECUTE: `python executor/runtime/docker_local.py --sid <SID> --build --run`
- VERIFY: `python evals/poc_verifier/main.py --sid <SID>`
- REVIEW: `python agents/reviewer/main.py --sid <SID> --mode deterministic`
- PACK: `python orchestrator/pack.py --sid <SID>`

## Artifact Map

- `metadata/<SID>/plan.json`: normalized requirement and policy
- `metadata/<SID>/researcher_report.json`: retrieval/evidence summary
- `metadata/<SID>/resolved_contract.json`: current resolved contract surface when present
- `metadata/<SID>/manifest.json`: pack summary
- `workspaces/<SID>/app/`: generated bundle
- `artifacts/<SID>/build/`: build log and SBOM
- `artifacts/<SID>/run/`: run log and run summary
- `artifacts/<SID>/reports/evals.json`: verifier result

## Common Checks

- `pytest -q tests`
- `pytest -q tests/test_pack_promotion.py tests/test_run_case_summary_surface.py`
- representative E2E:
  - `open-redirect-dynamic-name-only`
  - `open-redirect-strict-dynamic-no-remote`
  - `sqli-name-only`
  - `foobar-name-only-negative`

## Troubleshooting Entry Points

- researcher/evidence 문제: `metadata/<SID>/search_traces/`, `researcher_report.json`
- generator 문제: `metadata/<SID>/generator_manifest.json`, `generator_failures.jsonl`
- executor 문제: `artifacts/<SID>/build/build.log`, `artifacts/<SID>/run/run.log`
- verifier 문제: `artifacts/<SID>/reports/evals.json`, `docs/guardrails_dynamic.md`
- pack/summary 문제: `metadata/<SID>/manifest.json`

## Safety Notes

- `promotion_eligible`와 generalized support claim은 다릅니다. 판단 기준은 [docs/constraints.md](constraints.md)를 따릅니다.
- degraded deterministic fallback은 runnable일 수 있어도 open-world success로 주장하지 않습니다.
- 외부 네트워크나 sidecar 사용은 policy와 evidence가 정렬된 경우에만 허용합니다.
