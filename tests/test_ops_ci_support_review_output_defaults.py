from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_support_review_output_defaults_support_batch_resolution(
    tmp_path: Path,
) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_support_review_output_defaults.sh")!r}
support_review_resolve_output_name_defaults \
  VULD_TEST_REVIEW_OUTPUT_NAME support_review.json REVIEW_OUTPUT_NAME \
  VULD_TEST_DECISIONS_OUTPUT_NAME support_decisions.json DECISIONS_OUTPUT_NAME \
  VULD_TEST_UPDATE_OUTPUT_NAME support_update.json UPDATE_OUTPUT_NAME \
  VULD_TEST_REGISTRY_OUTPUT_NAME support_registry.json REGISTRY_OUTPUT_NAME
export REVIEW_OUTPUT_NAME DECISIONS_OUTPUT_NAME UPDATE_OUTPUT_NAME REGISTRY_OUTPUT_NAME
DEFAULTS="$(python - <<'PY'
import json
import os
print(json.dumps({{
  "review_output_name": os.environ["REVIEW_OUTPUT_NAME"],
  "decisions_output_name": os.environ["DECISIONS_OUTPUT_NAME"],
  "update_output_name": os.environ["UPDATE_OUTPUT_NAME"],
  "registry_output_name": os.environ["REGISTRY_OUTPUT_NAME"],
}}))
PY
)"
export DEFAULTS
export VULD_TEST_REVIEW_OUTPUT_NAME=custom_review.json
unset VULD_TEST_DECISIONS_OUTPUT_NAME || true
export VULD_TEST_UPDATE_OUTPUT_NAME=custom_update.json
export VULD_TEST_REGISTRY_OUTPUT_NAME=custom_registry.json
support_review_resolve_output_name_defaults \
  VULD_TEST_REVIEW_OUTPUT_NAME support_review.json REVIEW_OUTPUT_NAME \
  VULD_TEST_DECISIONS_OUTPUT_NAME support_decisions.json DECISIONS_OUTPUT_NAME \
  VULD_TEST_UPDATE_OUTPUT_NAME support_update.json UPDATE_OUTPUT_NAME \
  VULD_TEST_REGISTRY_OUTPUT_NAME support_registry.json REGISTRY_OUTPUT_NAME
export REVIEW_OUTPUT_NAME DECISIONS_OUTPUT_NAME UPDATE_OUTPUT_NAME REGISTRY_OUTPUT_NAME
OVERRIDES="$(python - <<'PY'
import json
import os
print(json.dumps({{
  "review_output_name": os.environ["REVIEW_OUTPUT_NAME"],
  "decisions_output_name": os.environ["DECISIONS_OUTPUT_NAME"],
  "update_output_name": os.environ["UPDATE_OUTPUT_NAME"],
  "registry_output_name": os.environ["REGISTRY_OUTPUT_NAME"],
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
            "review_output_name": "support_review.json",
            "decisions_output_name": "support_decisions.json",
            "update_output_name": "support_update.json",
            "registry_output_name": "support_registry.json",
        },
        "overrides": {
            "review_output_name": "custom_review.json",
            "decisions_output_name": "support_decisions.json",
            "update_output_name": "custom_update.json",
            "registry_output_name": "custom_registry.json",
        },
    }


def test_support_review_output_defaults_require_triplets(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_support_review_output_defaults.sh")!r}
support_review_resolve_output_name_defaults \
  VULD_TEST_REVIEW_OUTPUT_NAME support_review.json
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr.strip() == "support review output default triplets are required"


def test_support_review_output_defaults_support_prefixed_batch_resolution(
    tmp_path: Path,
) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_support_review_output_defaults.sh")!r}
support_review_resolve_prefixed_output_name_defaults \
  VULD_TEST \
  support_review.json REVIEW_OUTPUT_NAME \
  support_decisions.json DECISIONS_OUTPUT_NAME \
  support_update.json UPDATE_OUTPUT_NAME \
  support_registry.json REGISTRY_OUTPUT_NAME
export REVIEW_OUTPUT_NAME DECISIONS_OUTPUT_NAME UPDATE_OUTPUT_NAME REGISTRY_OUTPUT_NAME
DEFAULTS="$(python - <<'PY'
import json
import os
print(json.dumps({{
  "review_output_name": os.environ["REVIEW_OUTPUT_NAME"],
  "decisions_output_name": os.environ["DECISIONS_OUTPUT_NAME"],
  "update_output_name": os.environ["UPDATE_OUTPUT_NAME"],
  "registry_output_name": os.environ["REGISTRY_OUTPUT_NAME"],
}}))
PY
)"
export DEFAULTS
export VULD_TEST_REVIEW_OUTPUT_NAME=custom_review.json
unset VULD_TEST_DECISIONS_OUTPUT_NAME || true
export VULD_TEST_UPDATE_OUTPUT_NAME=custom_update.json
export VULD_TEST_REGISTRY_OUTPUT_NAME=custom_registry.json
support_review_resolve_prefixed_output_name_defaults \
  VULD_TEST \
  support_review.json REVIEW_OUTPUT_NAME \
  support_decisions.json DECISIONS_OUTPUT_NAME \
  support_update.json UPDATE_OUTPUT_NAME \
  support_registry.json REGISTRY_OUTPUT_NAME
export REVIEW_OUTPUT_NAME DECISIONS_OUTPUT_NAME UPDATE_OUTPUT_NAME REGISTRY_OUTPUT_NAME
OVERRIDES="$(python - <<'PY'
import json
import os
print(json.dumps({{
  "review_output_name": os.environ["REVIEW_OUTPUT_NAME"],
  "decisions_output_name": os.environ["DECISIONS_OUTPUT_NAME"],
  "update_output_name": os.environ["UPDATE_OUTPUT_NAME"],
  "registry_output_name": os.environ["REGISTRY_OUTPUT_NAME"],
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
            "review_output_name": "support_review.json",
            "decisions_output_name": "support_decisions.json",
            "update_output_name": "support_update.json",
            "registry_output_name": "support_registry.json",
        },
        "overrides": {
            "review_output_name": "custom_review.json",
            "decisions_output_name": "support_decisions.json",
            "update_output_name": "custom_update.json",
            "registry_output_name": "custom_registry.json",
        },
    }
