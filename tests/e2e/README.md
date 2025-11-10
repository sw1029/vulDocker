# E2E 회귀 하니스

`tests/e2e/` 폴더에는 전체 파이프라인(`plan → researcher → generator → executor → verifier → reviewer → pack`)
을 그대로 실행해 재현 가능한 회귀 시나리오를 담아둔다. 각 케이스는 `tests/e2e/cases/<slug>/`
하위에 위치하며 다음 파일을 포함한다.

- `requirement.yml`: 선언형 요구 정의. 전체 요구를 직접 작성하거나 `base_requirement.yml`을
  `base_requirement` + `overrides` 방식으로 참조할 수 있다.
- `expectations.json`: 실행 결과(Manifest/Reviewer)에 대한 검증 조건. 실제 값이 다르면 런너가 실패한다.
- `outputs/<sid>/`: (선택) 런너가 남긴 스냅샷. 로컬 반복 시 용량이 부담되면 `--no-snapshot`으로 생략 가능하다.

## 단일 케이스 실행 예시

```bash
python tests/e2e/run_case.py --case tests/e2e/cases/cwe-89-basic --mode deterministic
```

기본적으로 런너는 실패 분석을 돕기 위해 `metadata/<sid>`와 `artifacts/<sid>`를 케이스 폴더로 복사한다.
CI처럼 복사가 불필요한 환경에서는 `--no-snapshot` 플래그를 사용하면 된다.

## Pytest 연동

E2E 실행은 옵트인 방식이다. `VULD_RUN_E2E=1`을 설정하고 Docker 접근 권한을 확보하면
`pytest -m e2e`가 케이스를 실제로 실행한다. 환경 변수가 없으면 테스트가 자동으로 skip되어
기본 스위트 속도를 유지한다.

CI 엔트리 포인트 `ops/ci/run_e2e_tests.sh`는 각 케이스의 필수 파일을 확인한 뒤 `pytest -m e2e`를 호출한다.
