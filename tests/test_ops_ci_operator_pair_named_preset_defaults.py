from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_operator_pair_named_preset_defaults_resolve_direct_defaults_and_overrides(
    tmp_path: Path,
) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_operator_pair_named_preset_defaults.sh")!r}
operator_resolve_pair_named_preset_surface {str(REPO_ROOT / "ops/ci")!r} VULD_TEST_NAMED_DIRECT_HELPER run_named_direct_case_set.sh VULD_TEST_PRESET_HELPER run_named_preset_case_set.sh VULD_TEST_DIRECT_HELPER run_direct_validation_chain.sh
export OPERATOR_PAIR_NAMED_HELPER OPERATOR_PAIR_PRESET_HELPER OPERATOR_PAIR_LEAF_HELPER
DEFAULTS="$(python - <<'PY'
import json
import os
print(json.dumps({{
  "named": os.environ["OPERATOR_PAIR_NAMED_HELPER"],
  "preset": os.environ["OPERATOR_PAIR_PRESET_HELPER"],
  "leaf": os.environ["OPERATOR_PAIR_LEAF_HELPER"],
}}))
PY
)"
export DEFAULTS
export VULD_TEST_NAMED_DIRECT_HELPER=/tmp/custom-named
unset VULD_TEST_PRESET_HELPER || true
export VULD_TEST_DIRECT_HELPER=/tmp/custom-leaf
operator_resolve_pair_named_preset_surface {str(REPO_ROOT / "ops/ci")!r} VULD_TEST_NAMED_DIRECT_HELPER run_named_direct_case_set.sh VULD_TEST_PRESET_HELPER run_named_preset_case_set.sh VULD_TEST_DIRECT_HELPER run_direct_validation_chain.sh
export OPERATOR_PAIR_NAMED_HELPER OPERATOR_PAIR_PRESET_HELPER OPERATOR_PAIR_LEAF_HELPER
OVERRIDES="$(python - <<'PY'
import json
import os
print(json.dumps({{
  "named": os.environ["OPERATOR_PAIR_NAMED_HELPER"],
  "preset": os.environ["OPERATOR_PAIR_PRESET_HELPER"],
  "leaf": os.environ["OPERATOR_PAIR_LEAF_HELPER"],
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
            "named": str(REPO_ROOT / "ops/ci/run_named_direct_case_set.sh"),
            "preset": str(REPO_ROOT / "ops/ci/run_named_preset_case_set.sh"),
            "leaf": str(REPO_ROOT / "ops/ci/run_direct_validation_chain.sh"),
        },
        "overrides": {
            "named": "/tmp/custom-named",
            "preset": str(REPO_ROOT / "ops/ci/run_named_preset_case_set.sh"),
            "leaf": "/tmp/custom-leaf",
        },
    }


def test_operator_pair_named_preset_defaults_resolve_support_defaults_and_overrides(
    tmp_path: Path,
) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_operator_pair_named_preset_defaults.sh")!r}
operator_resolve_pair_named_preset_surface {str(REPO_ROOT / "ops/ci")!r} VULD_TEST_NAMED_SUPPORT_HELPER run_named_support_case_set.sh VULD_TEST_PRESET_HELPER run_named_preset_case_set.sh VULD_TEST_SUPPORT_HELPER run_support_workflow_chain.sh
export OPERATOR_PAIR_NAMED_HELPER OPERATOR_PAIR_PRESET_HELPER OPERATOR_PAIR_LEAF_HELPER
DEFAULTS="$(python - <<'PY'
import json
import os
print(json.dumps({{
  "named": os.environ["OPERATOR_PAIR_NAMED_HELPER"],
  "preset": os.environ["OPERATOR_PAIR_PRESET_HELPER"],
  "leaf": os.environ["OPERATOR_PAIR_LEAF_HELPER"],
}}))
PY
)"
export DEFAULTS
unset VULD_TEST_NAMED_SUPPORT_HELPER || true
export VULD_TEST_PRESET_HELPER=/tmp/custom-preset
export VULD_TEST_SUPPORT_HELPER=/tmp/custom-support
operator_resolve_pair_named_preset_surface {str(REPO_ROOT / "ops/ci")!r} VULD_TEST_NAMED_SUPPORT_HELPER run_named_support_case_set.sh VULD_TEST_PRESET_HELPER run_named_preset_case_set.sh VULD_TEST_SUPPORT_HELPER run_support_workflow_chain.sh
export OPERATOR_PAIR_NAMED_HELPER OPERATOR_PAIR_PRESET_HELPER OPERATOR_PAIR_LEAF_HELPER
OVERRIDES="$(python - <<'PY'
import json
import os
print(json.dumps({{
  "named": os.environ["OPERATOR_PAIR_NAMED_HELPER"],
  "preset": os.environ["OPERATOR_PAIR_PRESET_HELPER"],
  "leaf": os.environ["OPERATOR_PAIR_LEAF_HELPER"],
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
            "named": str(REPO_ROOT / "ops/ci/run_named_support_case_set.sh"),
            "preset": str(REPO_ROOT / "ops/ci/run_named_preset_case_set.sh"),
            "leaf": str(REPO_ROOT / "ops/ci/run_support_workflow_chain.sh"),
        },
        "overrides": {
            "named": str(REPO_ROOT / "ops/ci/run_named_support_case_set.sh"),
            "preset": "/tmp/custom-preset",
            "leaf": "/tmp/custom-support",
        },
    }
