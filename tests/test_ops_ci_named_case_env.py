from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_named_case_env_exports_direct_matrix_support_defaults_and_overrides(tmp_path: Path) -> None:
    helper = tmp_path / "helper.sh"
    _write_executable(helper, "#!/usr/bin/env bash\nexit 0\n")
    capture = tmp_path / "capture.json"
    shell_probe = tmp_path / "probe.sh"

    _write_executable(
        shell_probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_named_case_env.sh")!r}
named_caseset_require_helper {str(helper)!r} TEST
export VULD_NAMED_SUPPORT_REPEAT_HELPER=/tmp/repeat_helper
export VULD_NAMED_SUPPORT_REVIEW_HELPER=/tmp/review_helper
export VULD_NAMED_MATRIX_REPEAT_HELPER=/tmp/matrix_repeat_helper
export VULD_NAMED_DIRECT_PYTHON_BIN=/tmp/direct_python
export VULD_NAMED_DIRECT_CASES_ROOT=/tmp/direct_cases
export VULD_NAMED_DIRECT_OUTPUT_ROOT=/tmp/direct_out
export VULD_NAMED_DIRECT_MODE=diverse
export VULD_NAMED_DIRECT_NO_SNAPSHOT=0
named_direct_export_env /unused/direct_cases /unused/direct_out
export DIRECT_JSON=$(python - <<'PY'
import json, os
print(json.dumps({{
  "python_bin": os.environ["VULD_DIRECT_CHAIN_PYTHON_BIN"],
  "cases_root": os.environ["VULD_DIRECT_CHAIN_CASES_ROOT"],
  "output_root": os.environ["VULD_DIRECT_CHAIN_OUTPUT_ROOT"],
  "mode": os.environ["VULD_DIRECT_CHAIN_MODE"],
  "no_snapshot": os.environ["VULD_DIRECT_CHAIN_NO_SNAPSHOT"],
}}))
PY
)
unset VULD_SUPPORT_WORKFLOW_REPEAT_HELPER || true
unset VULD_SUPPORT_WORKFLOW_REVIEW_HELPER || true
export VULD_NAMED_SUPPORT_PYTHON_BIN=/tmp/support_python
export VULD_NAMED_SUPPORT_CASES_ROOT=/tmp/support_cases
export VULD_NAMED_SUPPORT_OUTPUT_ROOT=/tmp/support_out
export VULD_NAMED_SUPPORT_MODE=deterministic
export VULD_NAMED_SUPPORT_ATTEMPTS=5
export VULD_NAMED_SUPPORT_REVIEW_ONLY=1
export VULD_NAMED_SUPPORT_DECISIONS_FILE=/tmp/decisions.json
export VULD_NAMED_SUPPORT_NO_SNAPSHOT=1
export VULD_NAMED_SUPPORT_ALLOW_REPEAT_FAILURE_WITH_REPORT=0
export VULD_NAMED_SUPPORT_REVIEW_OUTPUT_NAME=review.json
export VULD_NAMED_SUPPORT_DECISIONS_OUTPUT_NAME=decisions.json
export VULD_NAMED_SUPPORT_UPDATE_OUTPUT_NAME=update.json
export VULD_NAMED_SUPPORT_REGISTRY_OUTPUT_NAME=registry.json
named_support_export_env /unused/support_cases /unused/support_out
export SUPPORT_JSON=$(python - <<'PY'
import json, os
print(json.dumps({{
  "python_bin": os.environ["VULD_SUPPORT_WORKFLOW_PYTHON_BIN"],
  "cases_root": os.environ["VULD_SUPPORT_WORKFLOW_CASES_ROOT"],
  "output_root": os.environ["VULD_SUPPORT_WORKFLOW_OUTPUT_ROOT"],
  "mode": os.environ["VULD_SUPPORT_WORKFLOW_MODE"],
  "attempts": os.environ["VULD_SUPPORT_WORKFLOW_ATTEMPTS"],
  "review_only": os.environ["VULD_SUPPORT_WORKFLOW_REVIEW_ONLY"],
  "decisions_file": os.environ["VULD_SUPPORT_WORKFLOW_DECISIONS_FILE"],
  "no_snapshot": os.environ["VULD_SUPPORT_WORKFLOW_NO_SNAPSHOT"],
  "allow_repeat_failure_with_report": os.environ["VULD_SUPPORT_WORKFLOW_ALLOW_REPEAT_FAILURE_WITH_REPORT"],
  "review_output_name": os.environ["VULD_SUPPORT_WORKFLOW_REVIEW_OUTPUT_NAME"],
  "decisions_output_name": os.environ["VULD_SUPPORT_WORKFLOW_DECISIONS_OUTPUT_NAME"],
  "update_output_name": os.environ["VULD_SUPPORT_WORKFLOW_UPDATE_OUTPUT_NAME"],
  "registry_output_name": os.environ["VULD_SUPPORT_WORKFLOW_REGISTRY_OUTPUT_NAME"],
  "repeat_helper": os.environ.get("VULD_SUPPORT_WORKFLOW_REPEAT_HELPER"),
  "review_helper": os.environ.get("VULD_SUPPORT_WORKFLOW_REVIEW_HELPER"),
}}))
PY
)
export VULD_NAMED_MATRIX_PYTHON_BIN=/tmp/matrix_python
export VULD_NAMED_MATRIX_CASES_ROOT=/tmp/matrix_cases
export VULD_NAMED_MATRIX_OUTPUT_ROOT=/tmp/matrix_out
export VULD_NAMED_MATRIX_MODE=diverse
export VULD_NAMED_MATRIX_ATTEMPTS=4
export VULD_NAMED_MATRIX_NO_SNAPSHOT=1
export VULD_NAMED_MATRIX_ALLOW_REPEAT_FAILURE_WITH_REPORT=1
named_matrix_export_env /unused/matrix_cases /unused/matrix_out
export MATRIX_JSON=$(python - <<'PY'
import json, os
print(json.dumps({{
  "python_bin": os.environ["VULD_REPEAT_MATRIX_PYTHON_BIN"],
  "cases_root": os.environ["VULD_REPEAT_MATRIX_CASES_ROOT"],
  "output_root": os.environ["VULD_REPEAT_MATRIX_OUTPUT_ROOT"],
  "mode": os.environ["VULD_REPEAT_MATRIX_MODE"],
  "attempts": os.environ["VULD_REPEAT_MATRIX_ATTEMPTS"],
  "no_snapshot": os.environ["VULD_REPEAT_MATRIX_NO_SNAPSHOT"],
  "allow_repeat_failure_with_report": os.environ["VULD_REPEAT_MATRIX_ALLOW_REPEAT_FAILURE_WITH_REPORT"],
  "repeat_helper": os.environ["VULD_REPEAT_MATRIX_REPEAT_HELPER"],
}}))
PY
)
python - <<'PY' > {str(capture)!r}
import json, os
print(json.dumps({{
  "direct": json.loads(os.environ["DIRECT_JSON"]),
  "support": json.loads(os.environ["SUPPORT_JSON"]),
  "matrix": json.loads(os.environ["MATRIX_JSON"]),
}}))
PY
""",
    )

    completed = subprocess.run(
        ["bash", str(shell_probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(capture.read_text(encoding="utf-8"))
    assert payload["direct"] == {
        "python_bin": "/tmp/direct_python",
        "cases_root": "/tmp/direct_cases",
        "output_root": "/tmp/direct_out",
        "mode": "diverse",
        "no_snapshot": "0",
    }
    assert payload["support"] == {
        "python_bin": "/tmp/support_python",
        "cases_root": "/tmp/support_cases",
        "output_root": "/tmp/support_out",
        "mode": "deterministic",
        "attempts": "5",
        "review_only": "1",
        "decisions_file": "/tmp/decisions.json",
        "no_snapshot": "1",
        "allow_repeat_failure_with_report": "0",
        "review_output_name": "review.json",
        "decisions_output_name": "decisions.json",
        "update_output_name": "update.json",
        "registry_output_name": "registry.json",
        "repeat_helper": "/tmp/repeat_helper",
        "review_helper": "/tmp/review_helper",
    }
    assert payload["matrix"] == {
        "python_bin": "/tmp/matrix_python",
        "cases_root": "/tmp/matrix_cases",
        "output_root": "/tmp/matrix_out",
        "mode": "diverse",
        "attempts": "4",
        "no_snapshot": "1",
        "allow_repeat_failure_with_report": "1",
        "repeat_helper": "/tmp/matrix_repeat_helper",
    }


def test_named_case_env_require_helper_fails_for_missing_executable(tmp_path: Path) -> None:
    shell_probe = tmp_path / "probe.sh"
    _write_executable(
        shell_probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_named_case_env.sh")!r}
named_caseset_require_helper /tmp/definitely_missing_helper TEST
""",
    )

    completed = subprocess.run(
        ["bash", str(shell_probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "[TEST] caseset helper not found or not executable: /tmp/definitely_missing_helper" in completed.stderr
