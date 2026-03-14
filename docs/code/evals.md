# evals 디렉토리

Status: support
Audience: implementation
Source of truth for: verifier entrypoints and result surfaces
Not the source of truth for: artifact-quality policy or project roadmap
Last validated against: current repo layout on 2026-03-14

Relevant canonical docs:
- [제약조건](../constraints.md)
- [로드맵](../final_solution.md)

## 핵심 파일

- `evals/poc_verifier/main.py`: verifier entrypoint
- `evals/poc_verifier/rule_based.py`: rule/contract/log based verification
- `evals/poc_verifier/registry.py`: verifier registry
- `evals/poc_verifier/llm_assisted.py`: optional LLM-assisted verifier path

## 현재 구현상 포인트

- verifier는 declared rule, runtime rule, contract-oracle fallback을 구분합니다.
- negative/metamorphic oracle metadata는 일부 surface에 반영되지만, full execution parity는 아직 제한적입니다.
- eval 결과는 `verify_pass` 외에도 trust, independence, semantic consistency를 같이 읽어야 합니다.

artifact quality나 support claim을 해석할 때는 반드시 [docs/constraints.md](../constraints.md)의 verifier/oracle constraints를 같이 참고합니다.
