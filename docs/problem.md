# vulDocker 현행 문제 정의 (MoSCoW TODO)

> 문서 목적: 현재 코드베이스에서 “동적 취약 환경 생성/실행/검증”을 방해하는 **하드코딩/커버리지/계약 불일치**를 문제 관점에서 정리한다.
>
> 참고: 상세 로드맵/Backlog는 `docs/final_solution.md`가 단일 소스다. 이전 버전 분석은 `docs/problem_legacy.md`에 보관한다.

## MUST (즉시 해결하지 않으면 end-to-end가 깨짐)

- [x] **새 CWE 입력 시 검증이 `unsupported`로 끝날 수 있음**: 정적 룰이 없고 Researcher를 실행하지 않으면 `docs/evals/rules/*.yaml`에 매칭이 없어 평가 단계에서 종료될 수 있음 (`evals/poc_verifier/rule_based.py`)
- [x] **실행기 포트/URL 하드코딩**: `http://127.0.0.1:5000` 및 readiness `port=5000` 고정으로 스택/프레임워크 다양성이 깨짐 (`executor/runtime/docker_local.py`)
- [x] **룰 커버리지 메타데이터 캐시 고정**: registry가 rule availability를 import 시점에만 계산해(runtime rule 등록 이후에도) `rule_known` 신호가 부정확할 수 있음 (`evals/poc_verifier/registry.py`)
- [x] **Synthesis의 `flag_token` 강제 덮어쓰기**: runtime/rule이 없을 때 LLM이 생성한 `poc.flag_token`이 무시되어 manifest↔PoC↔검증 계약이 어긋날 수 있음 (`agents/generator/synthesis.py`)

## SHOULD (해결 시 커버리지/재현성/운영성이 크게 개선)

- [ ] **룰/템플릿/힌트 커버리지 편중 해소**: 정적 룰/템플릿/힌트가 CWE-89/352 중심으로 편중 (`docs/evals/rules/`, `workspaces/templates/`, `rag/hints/`)
- [ ] **stage 간 “성공 조건/엔트리포인트” 단일 계약화**: RuleSpec/runtime, generator manifest, template metadata의 우선순위/병합 규칙이 명확히 문서화/구현되어야 함 (`common/rules/__init__.py` 중심)
- [ ] **“레포에 없는 CWE” e2e 케이스 부재**: 동적 케이스(Researcher→Generator→Executor→Verifier) 회귀 테스트가 부족 (`tests/e2e/`)

## COULD (실험/고도화)

- [ ] rule 부재 케이스에서 LLM-assisted verifier를 정책 기반으로 안전하게 활용(오프라인 스텁 시 graceful skip 포함) (`evals/poc_verifier/llm_assisted.py`)
- [ ] 다중 컨테이너 스택(db/redis 등) 지원(docker compose 또는 sidecar) + 네트워크 정책 강화 (`executor/`)

## WON'T (이번 범위 제외)

- [ ] 파이프라인 단계/아키텍처 대규모 개편(분산 실행/새 오케스트레이터 등)
- [ ] 외부 인터넷에 노출되는 형태의 실행/배포 자동화
