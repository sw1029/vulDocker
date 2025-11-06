# 모델 및 디코딩 전략

prompt.md 4장(모델·툴 선택 원칙)과 TODO 7 요구를 충족하기 위해 주/보조 모델 구성, 디코딩 모드, 파라미터 프로파일을 정의한다. 모든 작업은 `conda`의 `vul` 환경에서 수행한다.

## 1. 모델 포트폴리오
| 역할 | 후보 모델 | 선정 기준 |
| --- | --- | --- |
| Generator/Researcher | 코드/툴 사용에 강한 GPT-4.1, Claude Sonnet, Llama 3.1 Code | Tool reliability, context window, 비용 |
| Reviewer | 상위 정확도 모델(Claude Opus, GPT-4.1 Turbo) | 정밀 코드 리뷰, 체크리스트 수행 |
| Tooling(정적 분석 보조) | 전용 AST/정적 분석기 | LLM 부하 감소 |

- 보조 모델은 Reviewer, 정책 검증에 집중하여 hallucination 감소.
- 모델 버전과 파라미터는 Packaging Metadata(`docs/schemas/packaging_metadata.md`)에 기록.

## 2. 디코딩 모드
### 2.1 재현 모드 (Deterministic)
- Generator/Researcher/Reviewer 모두 `temperature=0`, `top_p=1`, greedy.
- Self-consistency 비활성화.
- Scenario ID만으로 동일 결과를 재현하도록 고정.

### 2.2 다변성 모드 (Diverse)
- Generator: `temperature=0.7`, `top_p=0.95`, nucleus sampling.
- Self-consistency: `k=5` 경로 샘플링 후 다수결.
- Variation Key 예시:
```json
{
  "mode": "diverse",
  "top_p": 0.95,
  "temperature": 0.7,
  "self_consistency_k": 5,
  "pattern_pool_seed": 1337
}
```
- Reviewer는 기본적으로 deterministic이나, 필요 시 `temperature=0.2`로 다양성 허용.

## 3. 추론 제약 및 가이드
- 최대 토큰: Generator 8k, Reviewer 4k(로그 회수 시 슬라이딩 윈도우 사용).
- 함수 호출/도구 사용: Researcher는 ReAct 패턴, Reflexion 메모리를 통해 실패 로그를 재활용.
- Guardrails: 모델 출력은 JSON 스키마(`docs/schemas/*.md`) 검증 필수.

## 4. 선택 기준 & 모니터링
- KPI: PoC 성공률, Reviewer false-negative 비율, 다변성 지표(샤논 엔트로피), 재현율.
- 성능 모니터링: SWE-bench 난이도 참고( prompt.md 4장 ).
- 롤백 전략: 모델 버전 교체 시 SID 계산에 영향 → prompt_hash/model_version 업데이트.

## 5. 정합성 체크
- [x] prompt.md 4장(LLM 조합, 디코딩 전략, self-consistency) 반영.
- [x] TODO 7 작업 항목 충족.
- [x] 출력 JSON 스키마 준수를 통해 docs/schemas/* 와 일치.
- [x] Packaging Metadata에 모델/디코딩 파라미터 기록 규칙 연계.

## 연관 문서
- `docs/variability_repro/design.md`
- `docs/schemas/packaging_metadata.md`
- `docs/architecture/agents_contracts.md`
