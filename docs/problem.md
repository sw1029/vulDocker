# vulDocker 문제 정의

Status: canonical
Audience: mixed
Source of truth for: project problem statement, name-only/open-world target behavior, success criteria
Not the source of truth for: current baseline evidence, implementation roadmap, subsystem policy details
Last validated against: current success-criteria wording, roadmap alignment, and rerun-backed truth reflected on 2026-03-19

본 프로젝트의 핵심 문제는 "취약점 이름만 주어졌을 때도 사용자가 기대한 의도에 맞는 취약 Docker 환경을 생성·실행·검증할 수 있는가"입니다. 현재 레포는 일부 family에 대해 정직한 regression platform과 bounded dynamic generation을 제공하지만, generalized open-world generator로는 아직 부족합니다.

관련 문서:
- 현재 truth와 baseline: [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)
- 현재 제약과 금지 claim: [docs/constraints.md](constraints.md)
- 구현 우선순위: [docs/final_solution.md](final_solution.md)
- actionable ticket backlog: [docs/work_tickets.md](work_tickets.md)
- 운영 절차: [docs/handbook.md](handbook.md)
- representative validation harness: [tests/e2e/README.md](../tests/e2e/README.md)

## Reader Routing

- 목표/성공 기준을 확인하려면 이 문서를 본다.
- 지금 실제로 어디까지 되는지 확인하려면 [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)로 간다.
- 무엇을 주장하면 안 되는지 확인하려면 [docs/constraints.md](constraints.md)로 간다.
- 다음 구현 순서를 정하려면 [docs/final_solution.md](final_solution.md)와 [docs/work_tickets.md](work_tickets.md)로 간다.
- 실제 실행 절차와 artifact 해석은 [docs/handbook.md](handbook.md)를 본다.
- representative rerun command와 repeatability/support 검증 하니스는 [tests/e2e/README.md](../tests/e2e/README.md)를 본다.

## Validation Companions

이 문서의 success criteria를 실제 검증으로 내릴 때는 아래 문서를 같이 본다.

- “현재 실제로 충족됐는가”는 [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)
- “무엇을 충족으로 말하면 안 되는가”는 [docs/constraints.md](constraints.md)
- “성공 기준 5축이 어떤 backlog owner로 분해되는가”는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Axis Map`
- “완료판정 companion 문서 세트는 무엇인가”는 [docs/work_tickets.md](work_tickets.md)의 `Completion Companions`
- “각 축 완료를 무엇으로 판정하나”는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Checklist`
- “각 축 완료를 어떤 순서로 검토하나”는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Review Flow`
- “완료판정 문서를 어떤 순서로 열 것인가”는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Reading Order`
- “지금 확인된 open-world residual이 어떤 ticket bundle로 쪼개지는가”는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Residual Ticket Breakdown`
- “지금 residual을 어떤 순서로 구현 검토하나”는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Residual Review Flow`
- “residual 문서를 어떤 순서로 열 것인가”는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Residual Reading Order`
- “residual 검토 companion 문서 세트는 무엇인가”는 [docs/work_tickets.md](work_tickets.md)의 `Residual Companions`
- “지금 내가 검증/완료판정/잔여 검토 중 무엇을 하려는지에 따라 어디서 시작해야 하나”는 [docs/work_tickets.md](work_tickets.md)의 `Review Mode Matrix`
- “어떤 phase acceptance가 어떤 검증 surface로 이어지는가”는 [docs/final_solution.md](final_solution.md)의 `Acceptance-To-Validation Translation`
- “검증 문서를 어떤 순서로 열 것인가”는 [docs/work_tickets.md](work_tickets.md)의 `Validation Reading Order`
- “검증 질문별로 어느 문서를 먼저 봐야 하나”는 [docs/work_tickets.md](work_tickets.md)의 `Validation Question Routing`
- “residual 질문별로 어느 문서를 먼저 봐야 하나”는 [docs/work_tickets.md](work_tickets.md)의 `Residual Question Routing`
- “실제 rerun command는 무엇인가”는 [tests/e2e/README.md](../tests/e2e/README.md)

## Completion Companions

이 문서의 success criteria를 완료판정 관점으로 읽을 때는 아래 문서를 같이 본다.

- completion companion set은 [docs/work_tickets.md](work_tickets.md)의 `Completion Companions`
- axis map / close criteria / canonical review order는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Axis Map`, `Open-World Completion Checklist`, `Open-World Completion Review Flow`
- canonical completion reading order는 [docs/work_tickets.md](work_tickets.md)의 `Open-World Completion Reading Order`
- phase acceptance map은 [docs/final_solution.md](final_solution.md)의 `Acceptance-To-Validation Translation`
- current truth / non-claim은 [docs/current_state_gap_analysis.md](current_state_gap_analysis.md), [docs/constraints.md](constraints.md)

## Review Mode Entry

이 문서를 보고 있을 때도, 현재 목적은 아래 셋 중 하나로 다시 좁혀서 본다.

- 검증:
  - [docs/work_tickets.md](work_tickets.md)의 `Review Mode Matrix`
  - [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)
- 완료판정:
  - [docs/work_tickets.md](work_tickets.md)의 `Review Mode Matrix`
  - 이 문서의 `Completion Companions`
- 잔여 구현 검토:
  - [docs/work_tickets.md](work_tickets.md)의 `Review Mode Matrix`
  - [docs/work_tickets.md](work_tickets.md)의 `Residual Companions`

## Problem Statement

현재 시스템이 풀고자 하는 질문은 두 가지입니다.

1. 지원되는 family에 대해서는 재현 가능하고 검증 가능한 취약 환경을 안정적으로 생성할 수 있는가.
2. `name only` 입력에서도 lower-bound recovery와 open-world intent satisfaction을 구분하면서, 근거 기반으로 family/stack/topology/oracle을 선택할 수 있는가.

이 문서에서 말하는 성공은 "무언가 실행되었다"가 아니라 "요청 의도와 맞는 결과를, 현재 claim 가능한 수준 안에서 정직하게 냈다"입니다.

## Why Name-Only Is Hard

`name only`가 어려운 이유는 입력이 곧바로 구현 계획으로 연결되지 않기 때문입니다.

- family가 애매할 수 있습니다. 예: broad phrase, paraphrase, alias, synthetic name
- stack이 입력에 없을 수 있습니다.
- topology와 dependency가 내재돼 있을 수 있습니다.
- verifier/oracle이 성공 마커만으로는 의도 충족을 보장하지 못할 수 있습니다.
- lower-bound recovery와 evidence-backed dynamic success를 혼동하기 쉽습니다.

따라서 `name only`에서는 selection, runtime design, oracle design, claim surface를 함께 다뤄야 합니다.

장기적으로는 family를 먼저 고정하고 그에 맞는 materializer를 찾는 구조보다, `primitive / runtime dependency / topology / oracle`를 먼저 세우고 family는 그 결과를 설명하는 라벨로 밀어내는 방향이 더 적절합니다. 현재 시스템은 아직 그 단계에 도달하지 않았습니다.

## Target Behavior By Mode

### `compatibility`

- curated lower-bound나 compiler/template closure를 허용합니다.
- 목표는 broad compatibility와 regression utility입니다.
- `intent_met`는 "현재 release의 lower-bound contract 안에서 요청이 충족되었다"를 뜻합니다.

### `dynamic`

- degraded deterministic fallback은 runnable closure로 허용할 수 있지만, generalized open-world success로 주장하면 안 됩니다.
- `intent_met`는 evidence-backed selection과 runtime/oracle parity가 갖춰진 경우에만 허용해야 합니다.
- 그렇지 않으면 `partial` 또는 `abstain`이 맞습니다.

### `strict_dynamic`

- remote evidence와 stricter verifier independence가 필요합니다.
- capability가 없거나 evidence가 부족하면 `fail_closed` 또는 `abstain`이어야 합니다.
- lower-bound recovery는 success로 읽지 않습니다.

## Success Criteria

다음 조건을 만족해야 `name only`에서 "의도에 맞는 동작"이라고 부를 수 있습니다.

- 선택: family/stack/topology/oracle이 evidence-backed 또는 명시적 requirement 기반으로 결정됨
- 생성: 산출물이 runnable하고, silent default에 의존하지 않음
- 실행: runtime plan과 executor behavior가 일치함
- 검증: verifier가 성공뿐 아니라 negative/forbidden/metamorphic contract를 충분히 반영함
- 보고: `intent_met`, `partial`, `abstain`, `fail_closed`가 operator에게 혼동 없이 surface됨

반대로 아래는 성공으로 주장하면 안 됩니다.

- bounded lower-bound closure를 generalized open-world success처럼 설명하는 것
- repo-prior/defaulted stack을 evidence-led selection처럼 설명하는 것
- quality metadata만 풍부하고 verifier execution parity가 약한 결과를 high-quality artifact처럼 설명하는 것

## Non-Goals

이번 범위의 비목표는 아래와 같습니다.

- 모든 CWE/family에 대한 정적 템플릿 구축
- 외부 배포/인터넷 노출 실행 자동화
- 분산 오케스트레이션 또는 완전히 다른 pipeline으로 교체
- unknown family와 unknown stack을 무조건 성공적으로 materialize하는 것

## Relationship To Other Docs

- 현재 baseline과 rerun truth는 [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)에서 다룹니다.
- 현재 시스템이 할 수 있는 것/없는 것은 [docs/constraints.md](constraints.md)에서 정의합니다.
- 구현 우선순위와 phase plan은 [docs/final_solution.md](final_solution.md)가 단일 소스입니다.
- 실제 운영 절차와 명령은 [docs/handbook.md](handbook.md)를 봅니다.
- representative validation harness와 case layout은 [tests/e2e/README.md](../tests/e2e/README.md)를 봅니다.

## How To Update This Document

- success criteria나 target behavior wording이 바뀔 때만 갱신한다.
- current baseline 수치나 rerun 결과는 여기 적지 않고 [docs/current_state_gap_analysis.md](current_state_gap_analysis.md)로 보낸다.
- current non-claim이나 운영 전제는 [docs/constraints.md](constraints.md)로 보낸다.
- 우선순위나 phase ordering이 바뀌면 [docs/final_solution.md](final_solution.md)와 [docs/work_tickets.md](work_tickets.md)를 함께 갱신한다.
- representative validation harness entrypoint가 바뀌면 [tests/e2e/README.md](../tests/e2e/README.md)와 같이 맞춘다.
- completion companion 관계나 completion reading order가 바뀌면 [docs/work_tickets.md](work_tickets.md), [README.md](../README.md)와 같이 맞춘다.
- review mode entry shortcut이 바뀌면 [docs/work_tickets.md](work_tickets.md), [README.md](../README.md)와 같이 맞춘다.
