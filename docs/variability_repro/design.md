# 다변성·재현성 설계

prompt.md 7장과 TODO 10 요구를 충족하기 위해 시나리오 차원, 샘플링 전략, Scenario ID 관리, 지표 체계를 정의한다. 모든 작업은 `conda`의 `vul` 환경에서 수행한다.

## 1. 시나리오 차원 테이블
| 차원 | 예시 값 |
| --- | --- |
| 언어 | Python, PHP, Java, Go |
| 웹 프레임워크 | Flask, Express, Spring, Laravel |
| DB 타입 | MySQL, PostgreSQL, SQLite |
| ORM 유무 | ORM, Raw SQL |
| 인코딩/로케일 | UTF-8, EUC-KR, en_US, ko_KR |
| 배포 형태 | Docker, MicroVM |
| OS | Ubuntu 22.04, Debian 12 |
| 입력 채널 | REST, GraphQL, CLI |
| 인증 | 없음, JWT, 세션 |

차원별 메타데이터는 `metadata/dimensions.json`(추후)로 관리하고, LHS 샘플링 시 균형 있게 선택한다.

## 2. 샘플링 및 패턴 선택
- **LHS(Latin Hypercube Sampling)**: 각 차원의 구간을 고르게 커버하도록 조합 생성.
- **패턴 풀**: CWE별 템플릿 ID(예: `sqli-string-concat`, `sqli-raw-orm`).
- **선택기 로직**:
  1. 사용자 요구와 필수 제약 반영.
  2. 남은 차원은 LHS 기반 무작위 추출.
  3. 패턴 풀에서 Variation Key에 따라 시드 고정 후 선택.

## 3. Scenario ID 및 Variation Key
- SID 정의: `H(model_version || prompt_hash || seed || retriever_commit || corpus_snapshot || pattern_id || deps_digest || base_image_digest)`를 기본으로 하되, 다중 취약 모드에서는 `vuln_ids_digest = sha256(join(sorted(vuln_ids)))`를 보조 필드로 추가해 조합 전체를 해시에 반영한다.
- Variation Key 예시:
```json
{
  "top_p": 0.95,
  "temperature": 0.7,
  "self_consistency_k": 5,
  "pattern_pool_seed": 1337
}
```
- 재현 모드: Variation Key 고정, deterministic 파라미터 사용.
- 다변성 모드: Variation Key 일부 변경(top_p 등)으로 다양성 제어.
- `plan.run_matrix.vuln_bundles[]`에 취약별 slug·워크스페이스 상대 경로를 저장하고, Variation Manager는 동일 Variation Key를 공유하되 Executor/Eval 단계에서 slug별 경로(`workspaces/<SID>/app/<slug>`, `metadata/<SID>/bundles/<slug>`, `artifacts/<SID>/run/<slug>`)를 참조해 번들 단위 재현성을 확보한다.

## 4. 지표
- **다변성**: 
  - 샤논 엔트로피 H (패턴 선택 분포).
  - 시나리오 거리(차원별 해밍 거리 합 / 차원 수).
- **재현성**:
  - 동일 `(requirement, SID)` 재실행一致율.
  - deterministic 테스트 결과 비교(diff).

## 5. 워크플로
1. PLAN 단계에서 차원 테이블+LHS로 후보 생성.
2. Variation Key 계산 후 Scenario ID 확정.
3. 생성/검증/패키징 단계에서 SID/Variation Key를 모두 메타데이터·레포트에 기록.
4. 다변성 모드 요청 시 Variation Key 변경 후 동일 프로세스 반복.

## 6. 정합성 체크
- [x] prompt.md 7장(시나리오 차원, LHS, self-consistency, SID/variation) 반영.
- [x] docs/decoding/model_and_decoding_strategy.md와 Variation Key 정의 일치.
- [x] docs/architecture/metastore_and_artifacts.md의 SID/caching 규칙과 연결.

## 연관 문서
- `docs/decoding/model_and_decoding_strategy.md`
- `docs/requirements/goal_and_outputs.md`
- `docs/evals/specs.md`
