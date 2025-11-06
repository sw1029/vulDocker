# MVP 실행 런북

TODO 13을 실제로 수행하기 위한 단계별 실행 절차. 단일 LLM + 정적 RAG + 로컬 Docker 실행기 기반.

## 1. 준비
- Conda `vul` 환경 활성화.
- 정적 요구 파일: `inputs/mvp_sqli.yml`
- RAG 스냅샷 고정: `rag/corpus/processed/mvp-sample`
- 자동화 스크립트: `python scripts/mvp_loop.py --input inputs/mvp_sqli.yml`

## 2. 단계별 명령
### 자동 실행 (권장)
```
python scripts/mvp_loop.py --input inputs/mvp_sqli.yml
```
위 스크립트가 PLAN→PACK 전 단계를 순차 실행한다.

### 수동 실행
1. **PLAN**: `python orchestrator/plan.py --input inputs/mvp_sqli.yml`
2. **DRAFT**: `python agents/generator/main.py --sid sid-mvp-sqli-0001`
3. **BUILD**: `python scripts/mvp_loop.py --input inputs/mvp_sqli.yml` 내부의 `build_stage` 함수 참고(또는 Docker 기반 구현).
4. **RUN**: `PYTHONPATH=workspaces/sid-mvp-sqli-0001/app python workspaces/sid-mvp-sqli-0001/poc/poc.py --log artifacts/sid-mvp-sqli-0001/run/poc_log.json`
5. **VERIFY**: `python evals/poc_verifier/mvp_sqli.py --log artifacts/sid-mvp-sqli-0001/run/poc_log.json`
6. **PACK**: `python scripts/mvp_loop.py --input inputs/mvp_sqli.yml` 내부 `pack_stage` 참고(보고서 생성).

## 3. 산출물 확인
- `artifacts/sid-mvp-sqli-0001/`
  - `build/` (이미지 manifest, SBOM)
  - `run/` (PoC 로그)
  - `reports/` (repro report 초안)

## 4. 검증 포인트
- PoC 로그에 `SQLi SUCCESS` 문자열
- SBOM 파일 서명 여부
- 재현 리포트 템플릿(`docs/reporting/…`)에 필수 메타데이터 기재

## 5. 연관 문서
- `docs/milestones/roadmap.md`
- `docs/requirements/goal_and_outputs.md`
- `experiments/01_mvp_sqli_loop.ipynb`
