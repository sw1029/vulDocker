# MVP 실행 런북

TODO 13을 실제로 수행하기 위한 단계별 실행 절차. 단일 LLM + 정적 RAG + 로컬 Docker 실행기 기반.

## 1. 준비
- Conda `vul` 환경 활성화.
- 정적 요구 파일: `inputs/mvp_sqli.yml`
- RAG 스냅샷 고정: `rag/corpus/processed/mvp-sample`

## 2. 단계별 명령
1. **PLAN**
   - `python orchestrator/plan.py --input inputs/mvp_sqli.yml`
   - 출력: `metadata/sid-mvp-sqli-0001/plan.json`
2. **DRAFT**
   - `python agents/generator/main.py --sid sid-mvp-sqli-0001 --mode deterministic`
   - 산출물: `workspaces/sid-mvp-sqli-0001/app/`
3. **BUILD**
   - `docker build -f workspaces/sid-mvp-sqli-0001/app/Dockerfile -t sid-mvp-sqli-0001 .`
   - `syft packages docker: sid-mvp-sqli-0001 -o json > artifacts/sid-mvp-sqli-0001/build/sbom.spdx.json`
4. **RUN**
   - `docker run --rm --name sid-mvp-sqli-0001 --network none sid-mvp-sqli-0001`
5. **VERIFY**
   - `python evals/poc_verifier/mvp_sqli.py --sid sid-mvp-sqli-0001 --log artifacts/.../run.log`
6. **PACK**
   - `python orchestrator/pack.py --sid sid-mvp-sqli-0001`

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
