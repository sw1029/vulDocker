from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_support_review_output_surface_resolves_defaults_and_output_paths(tmp_path: Path) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_support_review_output_surface.sh")!r}
support_review_prepare_prefixed_output_surface TEST_PREFIX {str(tmp_path / "outputs")!r} review.json REVIEW_OUT_NAME decisions.json DECISIONS_OUT_NAME update.json UPDATE_OUT_NAME registry.json REGISTRY_OUT_NAME
python - <<'PY' "${{REVIEW_OUT_NAME}}" "${{DECISIONS_OUT_NAME}}" "${{UPDATE_OUT_NAME}}" "${{REGISTRY_OUT_NAME}}" "${{VULD_SUPPORT_REVIEW_RESOLVED_REVIEW_OUT}}" "${{VULD_SUPPORT_REVIEW_RESOLVED_DECISIONS_OUT}}" "${{VULD_SUPPORT_REVIEW_RESOLVED_UPDATE_OUT}}" "${{VULD_SUPPORT_REVIEW_RESOLVED_REGISTRY_OUT}}" > {str(capture)!r}
import json
import os
import sys
print(json.dumps({{
  "review_name": sys.argv[1],
  "decisions_name": sys.argv[2],
  "update_name": sys.argv[3],
  "registry_name": sys.argv[4],
  "review_out": sys.argv[5],
  "decisions_out": sys.argv[6],
  "update_out": sys.argv[7],
  "registry_out": sys.argv[8],
  "prefixed_review_out": os.environ["TEST_PREFIX_RESOLVED_REVIEW_OUT"],
  "prefixed_decisions_out": os.environ["TEST_PREFIX_RESOLVED_DECISIONS_OUT"],
  "prefixed_update_out": os.environ["TEST_PREFIX_RESOLVED_UPDATE_OUT"],
  "prefixed_registry_out": os.environ["TEST_PREFIX_RESOLVED_REGISTRY_OUT"],
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
        "review_name": "review.json",
        "decisions_name": "decisions.json",
        "update_name": "update.json",
        "registry_name": "registry.json",
        "review_out": str(tmp_path / "outputs" / "review.json"),
        "decisions_out": str(tmp_path / "outputs" / "decisions.json"),
        "update_out": str(tmp_path / "outputs" / "update.json"),
        "registry_out": str(tmp_path / "outputs" / "registry.json"),
        "prefixed_review_out": str(tmp_path / "outputs" / "review.json"),
        "prefixed_decisions_out": str(tmp_path / "outputs" / "decisions.json"),
        "prefixed_update_out": str(tmp_path / "outputs" / "update.json"),
        "prefixed_registry_out": str(tmp_path / "outputs" / "registry.json"),
    }


def test_support_review_output_surface_honors_prefixed_overrides(tmp_path: Path) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
export TEST_PREFIX_REVIEW_OUTPUT_NAME=custom_review.json
export TEST_PREFIX_DECISIONS_OUTPUT_NAME=custom_decisions.json
export TEST_PREFIX_UPDATE_OUTPUT_NAME=custom_update.json
export TEST_PREFIX_REGISTRY_OUTPUT_NAME=custom_registry.json
source {str(REPO_ROOT / "ops/ci/lib_support_review_output_surface.sh")!r}
support_review_prepare_prefixed_output_surface TEST_PREFIX {str(tmp_path / "outputs")!r} review.json REVIEW_OUT_NAME decisions.json DECISIONS_OUT_NAME update.json UPDATE_OUT_NAME registry.json REGISTRY_OUT_NAME
python - <<'PY' "${{REVIEW_OUT_NAME}}" "${{DECISIONS_OUT_NAME}}" "${{UPDATE_OUT_NAME}}" "${{REGISTRY_OUT_NAME}}" "${{VULD_SUPPORT_REVIEW_RESOLVED_REVIEW_OUT}}" "${{VULD_SUPPORT_REVIEW_RESOLVED_DECISIONS_OUT}}" "${{VULD_SUPPORT_REVIEW_RESOLVED_UPDATE_OUT}}" "${{VULD_SUPPORT_REVIEW_RESOLVED_REGISTRY_OUT}}" > {str(capture)!r}
import json
import os
import sys
print(json.dumps({{
  "review_name": sys.argv[1],
  "decisions_name": sys.argv[2],
  "update_name": sys.argv[3],
  "registry_name": sys.argv[4],
  "review_out": sys.argv[5],
  "decisions_out": sys.argv[6],
  "update_out": sys.argv[7],
  "registry_out": sys.argv[8],
  "prefixed_review_out": os.environ["TEST_PREFIX_RESOLVED_REVIEW_OUT"],
  "prefixed_decisions_out": os.environ["TEST_PREFIX_RESOLVED_DECISIONS_OUT"],
  "prefixed_update_out": os.environ["TEST_PREFIX_RESOLVED_UPDATE_OUT"],
  "prefixed_registry_out": os.environ["TEST_PREFIX_RESOLVED_REGISTRY_OUT"],
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
        "review_name": "custom_review.json",
        "decisions_name": "custom_decisions.json",
        "update_name": "custom_update.json",
        "registry_name": "custom_registry.json",
        "review_out": str(tmp_path / "outputs" / "custom_review.json"),
        "decisions_out": str(tmp_path / "outputs" / "custom_decisions.json"),
        "update_out": str(tmp_path / "outputs" / "custom_update.json"),
        "registry_out": str(tmp_path / "outputs" / "custom_registry.json"),
        "prefixed_review_out": str(tmp_path / "outputs" / "custom_review.json"),
        "prefixed_decisions_out": str(tmp_path / "outputs" / "custom_decisions.json"),
        "prefixed_update_out": str(tmp_path / "outputs" / "custom_update.json"),
        "prefixed_registry_out": str(tmp_path / "outputs" / "custom_registry.json"),
    }
