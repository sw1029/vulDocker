# MVP 실행 런북

TODO 13을 실제로 수행하기 위한 단계별 실행 절차. 단일 LLM + 정적 RAG + 로컬 Docker 실행기 기반.

## 1. 준비
- Conda `vul` 환경 활성화.
- 정적 요구 파일: `inputs/mvp_sqli.yml`
- RAG 스냅샷 고정: `rag/corpus/processed/mvp-sample`

## 2. 단계별 명령
1. **PLAN**
   - `python orchestrator/plan.py --input inputs/mvp_sqli.yml`
   - 출력: `metadata/<SID>/plan.json` (스크립트가 metadata/workspaces/artifacts 폴더를 자동 생성)
2. **DRAFT**
   - `python agents/generator/main.py --sid <SID> --mode deterministic`
   - 산출물: `workspaces/<SID>/app/` + `metadata/<SID>/generator_llm_plan.md`
3. **BUILD**
   - `python executor/runtime/docker_local.py --sid <SID> --build`
   - 기능: Docker build + 이미지 ID 기록 + syft SBOM(`artifacts/<SID>/build/`)
4. **RUN**
   - `python executor/runtime/docker_local.py --sid <SID> --run`
   - 기능: rootless 컨테이너 실행 후 내부에서 `python poc.py` 실행(`artifacts/<SID>/run/run.log`)
5. **VERIFY**
   - `python evals/poc_verifier/mvp_sqli.py --sid <SID>`
   - 기능: `run.log`에서 `SQLi SUCCESS` 시그니처 검사 → `artifacts/<SID>/reports/evals.json`
6. **PACK**
   - `python orchestrator/pack.py --sid <SID>`
   - 기능: Workspace 스냅샷 및 `metadata/<SID>/manifest.json` 생성

### LLM · Docker · Syft 설정
- **LLM**: `config/api_keys.ini`에 OpenAI API 키를 저장하면(`config/api_keys.example.ini` 참고) 런타임이 자동으로 `OPENAI_API_KEY`를 세팅하여 실제 LLM을 호출한다. 별도 파일이 없으면 기존처럼 `VUL_LLM_API_KEY`/환경변수 값을 확인한 뒤, 모두 없을 경우 deterministic stub으로 동작한다.
- **Docker**: rootless 모드 권장. `docker` 바이너리가 PATH에 있어야 하며 RUN 단계에서 `--network none` 컨테이너를 띄운 뒤 `docker exec`으로 PoC를 실행한다.
- **Syft**: 설치되어 있으면 BUILD 단계에서 자동으로 SBOM(`sbom.spdx.json`)을 생성한다. 없을 경우 경고 후 건너뛴다.

## 3. 산출물 확인
- `artifacts/<SID>/build/`: `build.log`, `image_id.txt`, `sbom.spdx.json`, `source_snapshot/app/*`
- `artifacts/<SID>/run/`: `run.log`, `summary.json`
- `artifacts/<SID>/reports/`: `evals.json`, 기타 리포트
- `metadata/<SID>/`: `plan.json`, `generator_llm_plan.md`, `reviewer_report.json`, `manifest.json`

## 4. 검증 포인트
- PoC 로그에 `SQLi SUCCESS` 문자열
- SBOM 파일 서명 여부
- 재현 리포트 템플릿(`docs/reporting/…`)에 필수 메타데이터 기재

## 5. 연관 문서
- `docs/milestones/roadmap.md`
- `docs/requirements/goal_and_outputs.md`
- `experiments/01_mvp_sqli_loop.ipynb`
