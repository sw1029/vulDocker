from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_operator_matrix_baseline_defaults_resolve_defaults_and_partial_overrides(
    tmp_path: Path,
) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_operator_matrix_baseline_defaults.sh")!r}
operator_resolve_matrix_baseline_surface VULD_TEST {str(REPO_ROOT / "ops/ci")!r}
export OPERATOR_MATRIX_SEQUENCE_HELPER OPERATOR_MATRIX_PRESET_HELPER OPERATOR_MATRIX_NAMED_MATRIX_HELPER OPERATOR_MATRIX_HELPER
export OPERATOR_MATRIX_CASE_ARGS_JSON="$(printf '%s\\n' "${{OPERATOR_MATRIX_CASE_ARGS[@]}}")"
DEFAULTS="$(python - <<'PY'
import json
import os
print(json.dumps({{
  "sequence": os.environ["OPERATOR_MATRIX_SEQUENCE_HELPER"],
  "preset": os.environ["OPERATOR_MATRIX_PRESET_HELPER"],
  "named_matrix": os.environ["OPERATOR_MATRIX_NAMED_MATRIX_HELPER"],
  "matrix": os.environ["OPERATOR_MATRIX_HELPER"],
  "case_args": os.environ["OPERATOR_MATRIX_CASE_ARGS_JSON"].splitlines(),
}}))
PY
)"
export DEFAULTS
export VULD_TEST_SEQUENCE_HELPER=/tmp/custom-sequence
export VULD_TEST_PRESET_HELPER=/tmp/custom-preset
export VULD_TEST_NAMED_MATRIX_HELPER=/tmp/custom-named-matrix
export VULD_TEST_MATRIX_HELPER=/tmp/custom-matrix
export VULD_TEST_MATRIX_CASE_A=alpha-case
unset VULD_TEST_MATRIX_CASE_B || true
operator_resolve_matrix_baseline_surface VULD_TEST {str(REPO_ROOT / "ops/ci")!r}
export OPERATOR_MATRIX_SEQUENCE_HELPER OPERATOR_MATRIX_PRESET_HELPER OPERATOR_MATRIX_NAMED_MATRIX_HELPER OPERATOR_MATRIX_HELPER
export OPERATOR_MATRIX_CASE_ARGS_JSON="$(printf '%s\\n' "${{OPERATOR_MATRIX_CASE_ARGS[@]}}")"
OVERRIDES="$(python - <<'PY'
import json
import os
print(json.dumps({{
  "sequence": os.environ["OPERATOR_MATRIX_SEQUENCE_HELPER"],
  "preset": os.environ["OPERATOR_MATRIX_PRESET_HELPER"],
  "named_matrix": os.environ["OPERATOR_MATRIX_NAMED_MATRIX_HELPER"],
  "matrix": os.environ["OPERATOR_MATRIX_HELPER"],
  "case_args": os.environ["OPERATOR_MATRIX_CASE_ARGS_JSON"].splitlines(),
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
    payload = json.loads(capture.read_text(encoding="utf-8"))
    assert payload == {
        "defaults": {
            "sequence": str(REPO_ROOT / "ops/ci/run_helper_sequence.sh"),
            "preset": str(REPO_ROOT / "ops/ci/run_named_preset_case_set.sh"),
            "named_matrix": str(REPO_ROOT / "ops/ci/run_named_matrix_case_set.sh"),
            "matrix": str(REPO_ROOT / "ops/ci/run_repeatability_matrix_check.sh"),
            "case_args": [
                "foobar-name-only-negative",
                "open-redirect-strict-dynamic-no-remote",
            ],
        },
        "overrides": {
            "sequence": "/tmp/custom-sequence",
            "preset": "/tmp/custom-preset",
            "named_matrix": "/tmp/custom-named-matrix",
            "matrix": "/tmp/custom-matrix",
            "case_args": [
                "alpha-case",
                "open-redirect-strict-dynamic-no-remote",
            ],
        },
    }
