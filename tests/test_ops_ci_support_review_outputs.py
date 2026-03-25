from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_support_review_resolve_output_paths_exports_expected_paths(tmp_path: Path) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_support_review_outputs.sh")!r}
support_review_resolve_output_paths \
  /tmp/fake_output \
  custom_review.json \
  custom_decisions.json \
  custom_update.json \
  custom_registry.json
python - <<'PY' > {str(capture)!r}
import json, os
print(json.dumps({{
  "review_out": os.environ["VULD_SUPPORT_REVIEW_RESOLVED_REVIEW_OUT"],
  "decisions_out": os.environ["VULD_SUPPORT_REVIEW_RESOLVED_DECISIONS_OUT"],
  "update_out": os.environ["VULD_SUPPORT_REVIEW_RESOLVED_UPDATE_OUT"],
  "registry_out": os.environ["VULD_SUPPORT_REVIEW_RESOLVED_REGISTRY_OUT"],
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
        "review_out": "/tmp/fake_output/custom_review.json",
        "decisions_out": "/tmp/fake_output/custom_decisions.json",
        "update_out": "/tmp/fake_output/custom_update.json",
        "registry_out": "/tmp/fake_output/custom_registry.json",
    }


def test_support_review_resolve_output_path_pairs_support_batch_resolution(
    tmp_path: Path,
) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_support_review_outputs.sh")!r}
support_review_resolve_output_path_pairs \
  /tmp/fake_output \
  custom_review.json VULD_SUPPORT_REVIEW_RESOLVED_REVIEW_OUT \
  custom_decisions.json VULD_SUPPORT_REVIEW_RESOLVED_DECISIONS_OUT \
  custom_update.json VULD_SUPPORT_REVIEW_RESOLVED_UPDATE_OUT \
  custom_registry.json VULD_SUPPORT_REVIEW_RESOLVED_REGISTRY_OUT
python - <<'PY' > {str(capture)!r}
import json, os
print(json.dumps({{
  "review_out": os.environ["VULD_SUPPORT_REVIEW_RESOLVED_REVIEW_OUT"],
  "decisions_out": os.environ["VULD_SUPPORT_REVIEW_RESOLVED_DECISIONS_OUT"],
  "update_out": os.environ["VULD_SUPPORT_REVIEW_RESOLVED_UPDATE_OUT"],
  "registry_out": os.environ["VULD_SUPPORT_REVIEW_RESOLVED_REGISTRY_OUT"],
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
        "review_out": "/tmp/fake_output/custom_review.json",
        "decisions_out": "/tmp/fake_output/custom_decisions.json",
        "update_out": "/tmp/fake_output/custom_update.json",
        "registry_out": "/tmp/fake_output/custom_registry.json",
    }


def test_support_review_resolve_output_path_pairs_require_even_pairs(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_support_review_outputs.sh")!r}
support_review_resolve_output_path_pairs /tmp/fake_output custom_review.json
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr.strip() == "support review output path pairs are required"
