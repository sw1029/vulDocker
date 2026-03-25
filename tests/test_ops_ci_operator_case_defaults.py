from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_operator_case_defaults_resolve_pair_defaults_and_overrides(
    tmp_path: Path,
) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_operator_case_defaults.sh")!r}
operator_resolve_pair_case_defaults VULD_TEST_CASE_A alpha-default CASE_A VULD_TEST_CASE_B beta-default CASE_B
export CASE_A CASE_B
DEFAULTS="$(python - <<'PY'
import json
import os
print(json.dumps({{
  "case_a": os.environ["CASE_A"],
  "case_b": os.environ["CASE_B"],
}}))
PY
)"
export DEFAULTS
export VULD_TEST_CASE_A=alpha-override
unset VULD_TEST_CASE_B || true
operator_resolve_pair_case_defaults VULD_TEST_CASE_A alpha-default CASE_A VULD_TEST_CASE_B beta-default CASE_B
export CASE_A CASE_B
OVERRIDES="$(python - <<'PY'
import json
import os
print(json.dumps({{
  "case_a": os.environ["CASE_A"],
  "case_b": os.environ["CASE_B"],
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
            "case_a": "alpha-default",
            "case_b": "beta-default",
        },
        "overrides": {
            "case_a": "alpha-override",
            "case_b": "beta-default",
        },
    }


def test_operator_case_defaults_support_batch_resolution(
    tmp_path: Path,
) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_operator_case_defaults.sh")!r}
operator_resolve_case_defaults \
  VULD_TEST_CASE_A alpha-default CASE_A \
  VULD_TEST_CASE_B beta-default CASE_B \
  VULD_TEST_CASE_C gamma-default CASE_C
export CASE_A CASE_B CASE_C
DEFAULTS="$(python - <<'PY'
import json
import os
print(json.dumps({{
  "case_a": os.environ["CASE_A"],
  "case_b": os.environ["CASE_B"],
  "case_c": os.environ["CASE_C"],
}}))
PY
)"
export DEFAULTS
export VULD_TEST_CASE_A=alpha-override
unset VULD_TEST_CASE_B || true
export VULD_TEST_CASE_C=gamma-override
operator_resolve_case_defaults \
  VULD_TEST_CASE_A alpha-default CASE_A \
  VULD_TEST_CASE_B beta-default CASE_B \
  VULD_TEST_CASE_C gamma-default CASE_C
export CASE_A CASE_B CASE_C
OVERRIDES="$(python - <<'PY'
import json
import os
print(json.dumps({{
  "case_a": os.environ["CASE_A"],
  "case_b": os.environ["CASE_B"],
  "case_c": os.environ["CASE_C"],
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
            "case_a": "alpha-default",
            "case_b": "beta-default",
            "case_c": "gamma-default",
        },
        "overrides": {
            "case_a": "alpha-override",
            "case_b": "beta-default",
            "case_c": "gamma-override",
        },
    }


def test_operator_case_defaults_resolve_triple_defaults_and_overrides(
    tmp_path: Path,
) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_operator_case_defaults.sh")!r}
operator_resolve_triple_case_defaults VULD_TEST_CASE_A alpha-default CASE_A VULD_TEST_CASE_B beta-default CASE_B VULD_TEST_CASE_C gamma-default CASE_C
export CASE_A CASE_B CASE_C
DEFAULTS="$(python - <<'PY'
import json
import os
print(json.dumps({{
  "case_a": os.environ["CASE_A"],
  "case_b": os.environ["CASE_B"],
  "case_c": os.environ["CASE_C"],
}}))
PY
)"
export DEFAULTS
unset VULD_TEST_CASE_A || true
export VULD_TEST_CASE_B=beta-override
export VULD_TEST_CASE_C=gamma-override
operator_resolve_triple_case_defaults VULD_TEST_CASE_A alpha-default CASE_A VULD_TEST_CASE_B beta-default CASE_B VULD_TEST_CASE_C gamma-default CASE_C
export CASE_A CASE_B CASE_C
OVERRIDES="$(python - <<'PY'
import json
import os
print(json.dumps({{
  "case_a": os.environ["CASE_A"],
  "case_b": os.environ["CASE_B"],
  "case_c": os.environ["CASE_C"],
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
            "case_a": "alpha-default",
            "case_b": "beta-default",
            "case_c": "gamma-default",
        },
        "overrides": {
            "case_a": "alpha-default",
            "case_b": "beta-override",
            "case_c": "gamma-override",
        },
    }


def test_operator_case_defaults_requires_triplets(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_operator_case_defaults.sh")!r}
operator_resolve_case_defaults VULD_TEST_CASE_A alpha-default
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr.strip() == "case default triplets are required"
