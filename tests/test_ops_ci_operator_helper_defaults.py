from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_operator_resolve_script_helper_default_supports_default_and_override(
    tmp_path: Path,
) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_operator_helper_defaults.sh")!r}
operator_resolve_script_helper_default VULD_TEST_HELPER {str(REPO_ROOT / "ops/ci")!r} default-helper.sh RESOLVED_HELPER
export RESOLVED_HELPER
DEFAULTS="$(python - <<'PY'
import json
import os
print(json.dumps({{"resolved": os.environ["RESOLVED_HELPER"]}}))
PY
)"
export DEFAULTS
export VULD_TEST_HELPER=/tmp/custom-helper
operator_resolve_script_helper_default VULD_TEST_HELPER {str(REPO_ROOT / "ops/ci")!r} default-helper.sh RESOLVED_HELPER
export RESOLVED_HELPER
OVERRIDES="$(python - <<'PY'
import json
import os
print(json.dumps({{"resolved": os.environ["RESOLVED_HELPER"]}}))
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
            "resolved": str(REPO_ROOT / "ops/ci/default-helper.sh"),
        },
        "overrides": {
            "resolved": "/tmp/custom-helper",
        },
    }


def test_operator_resolve_script_helper_defaults_supports_batch_resolution(
    tmp_path: Path,
) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_operator_helper_defaults.sh")!r}
operator_resolve_script_helper_defaults \
  {str(REPO_ROOT / "ops/ci")!r} \
  VULD_FIRST_HELPER first-default.sh RESOLVED_FIRST \
  VULD_SECOND_HELPER second-default.sh RESOLVED_SECOND
export RESOLVED_FIRST RESOLVED_SECOND
DEFAULTS="$(python - <<'PY'
import json
import os
print(json.dumps({{
  "first": os.environ["RESOLVED_FIRST"],
  "second": os.environ["RESOLVED_SECOND"],
}}))
PY
)"
export DEFAULTS
export VULD_FIRST_HELPER=/tmp/custom-first
unset VULD_SECOND_HELPER || true
operator_resolve_script_helper_defaults \
  {str(REPO_ROOT / "ops/ci")!r} \
  VULD_FIRST_HELPER first-default.sh RESOLVED_FIRST \
  VULD_SECOND_HELPER second-default.sh RESOLVED_SECOND
export RESOLVED_FIRST RESOLVED_SECOND
OVERRIDES="$(python - <<'PY'
import json
import os
print(json.dumps({{
  "first": os.environ["RESOLVED_FIRST"],
  "second": os.environ["RESOLVED_SECOND"],
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
            "first": str(REPO_ROOT / "ops/ci/first-default.sh"),
            "second": str(REPO_ROOT / "ops/ci/second-default.sh"),
        },
        "overrides": {
            "first": "/tmp/custom-first",
            "second": str(REPO_ROOT / "ops/ci/second-default.sh"),
        },
    }


def test_operator_resolve_script_helper_defaults_requires_triplets(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_operator_helper_defaults.sh")!r}
operator_resolve_script_helper_defaults {str(REPO_ROOT / "ops/ci")!r} VULD_ONLY missing-one
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr.strip() == "script helper default triplets are required"
