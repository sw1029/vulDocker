from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_operator_pair_runtime_baseline_defaults_resolve_defaults_and_overrides(
    tmp_path: Path,
) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_operator_pair_runtime_baseline_defaults.sh")!r}
operator_resolve_pair_runtime_baseline_surface VULD_TEST {str(REPO_ROOT / "ops/ci")!r} VULD_TEST_FIRST_HELPER first-default.sh VULD_TEST_SECOND_HELPER second-default.sh
export OPERATOR_PAIR_SEQUENCE_HELPER OPERATOR_PAIR_FIRST_HELPER OPERATOR_PAIR_SECOND_HELPER
DEFAULTS="$(python - <<'PY'
import json
import os
print(json.dumps({{
  "sequence": os.environ["OPERATOR_PAIR_SEQUENCE_HELPER"],
  "first": os.environ["OPERATOR_PAIR_FIRST_HELPER"],
  "second": os.environ["OPERATOR_PAIR_SECOND_HELPER"],
}}))
PY
)"
export DEFAULTS
export VULD_TEST_SEQUENCE_HELPER=/tmp/custom-sequence
export VULD_TEST_FIRST_HELPER=/tmp/custom-first
unset VULD_TEST_SECOND_HELPER || true
operator_resolve_pair_runtime_baseline_surface VULD_TEST {str(REPO_ROOT / "ops/ci")!r} VULD_TEST_FIRST_HELPER first-default.sh VULD_TEST_SECOND_HELPER second-default.sh
export OPERATOR_PAIR_SEQUENCE_HELPER OPERATOR_PAIR_FIRST_HELPER OPERATOR_PAIR_SECOND_HELPER
OVERRIDES="$(python - <<'PY'
import json
import os
print(json.dumps({{
  "sequence": os.environ["OPERATOR_PAIR_SEQUENCE_HELPER"],
  "first": os.environ["OPERATOR_PAIR_FIRST_HELPER"],
  "second": os.environ["OPERATOR_PAIR_SECOND_HELPER"],
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
            "first": str(REPO_ROOT / "ops/ci/first-default.sh"),
            "second": str(REPO_ROOT / "ops/ci/second-default.sh"),
        },
        "overrides": {
            "sequence": "/tmp/custom-sequence",
            "first": "/tmp/custom-first",
            "second": str(REPO_ROOT / "ops/ci/second-default.sh"),
        },
    }
