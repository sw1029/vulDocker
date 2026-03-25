from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_operator_current_baseline_defaults_resolve_defaults_and_partial_overrides(
    tmp_path: Path,
) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_operator_current_baseline_defaults.sh")!r}
operator_resolve_current_baseline_surface VULD_TEST {str(REPO_ROOT / "ops/ci")!r}
export OPERATOR_CURRENT_SEQUENCE_HELPER OPERATOR_CURRENT_NO_DOCKER_HELPER OPERATOR_CURRENT_MEASURED_HELPER OPERATOR_CURRENT_SUPPORT_HELPER OPERATOR_CURRENT_DOCKER_POSITIVE_HELPER OPERATOR_CURRENT_HELPER_REGRESSION
DEFAULTS="$(python - <<'PY'
import json
import os
print(json.dumps({{
  "sequence": os.environ["OPERATOR_CURRENT_SEQUENCE_HELPER"],
  "no_docker": os.environ["OPERATOR_CURRENT_NO_DOCKER_HELPER"],
  "measured": os.environ["OPERATOR_CURRENT_MEASURED_HELPER"],
  "support": os.environ["OPERATOR_CURRENT_SUPPORT_HELPER"],
  "docker_positive": os.environ["OPERATOR_CURRENT_DOCKER_POSITIVE_HELPER"],
  "helper_regression": os.environ["OPERATOR_CURRENT_HELPER_REGRESSION"],
}}))
PY
)"
export DEFAULTS
export VULD_TEST_SEQUENCE_HELPER=/tmp/custom-sequence
export VULD_TEST_MEASURED_HELPER=/tmp/custom-measured
export VULD_TEST_HELPER_REGRESSION=/tmp/custom-helper-regression
operator_resolve_current_baseline_surface VULD_TEST {str(REPO_ROOT / "ops/ci")!r}
export OPERATOR_CURRENT_SEQUENCE_HELPER OPERATOR_CURRENT_NO_DOCKER_HELPER OPERATOR_CURRENT_MEASURED_HELPER OPERATOR_CURRENT_SUPPORT_HELPER OPERATOR_CURRENT_DOCKER_POSITIVE_HELPER OPERATOR_CURRENT_HELPER_REGRESSION
OVERRIDES="$(python - <<'PY'
import json
import os
print(json.dumps({{
  "sequence": os.environ["OPERATOR_CURRENT_SEQUENCE_HELPER"],
  "no_docker": os.environ["OPERATOR_CURRENT_NO_DOCKER_HELPER"],
  "measured": os.environ["OPERATOR_CURRENT_MEASURED_HELPER"],
  "support": os.environ["OPERATOR_CURRENT_SUPPORT_HELPER"],
  "docker_positive": os.environ["OPERATOR_CURRENT_DOCKER_POSITIVE_HELPER"],
  "helper_regression": os.environ["OPERATOR_CURRENT_HELPER_REGRESSION"],
}}))
PY
)"
export OVERRIDES
python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "defaults": json.loads(os.environ["DEFAULTS"]),
  "overrides": json.loads(os.environ["OVERRIDES"]),
}}))
PY
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(capture.read_text(encoding="utf-8")) == {
        "defaults": {
            "sequence": str(REPO_ROOT / "ops/ci/run_helper_sequence.sh"),
            "no_docker": str(REPO_ROOT / "ops/ci/run_no_docker_operator_baseline.sh"),
            "measured": str(REPO_ROOT / "ops/ci/run_measured_gate_operator_baseline.sh"),
            "support": str(REPO_ROOT / "ops/ci/run_support_workflow_operator_baseline.sh"),
            "docker_positive": str(REPO_ROOT / "ops/ci/run_docker_positive_operator_baseline.sh"),
            "helper_regression": str(REPO_ROOT / "ops/ci/run_ops_helper_contract_regression.sh"),
        },
        "overrides": {
            "sequence": "/tmp/custom-sequence",
            "no_docker": str(REPO_ROOT / "ops/ci/run_no_docker_operator_baseline.sh"),
            "measured": "/tmp/custom-measured",
            "support": str(REPO_ROOT / "ops/ci/run_support_workflow_operator_baseline.sh"),
            "docker_positive": str(REPO_ROOT / "ops/ci/run_docker_positive_operator_baseline.sh"),
            "helper_regression": "/tmp/custom-helper-regression",
        },
    }
