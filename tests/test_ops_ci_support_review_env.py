from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_export_support_review_env_exports_expected_values(tmp_path: Path) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_support_review_env.sh")!r}
export_support_review_env \
  /tmp/fake_python \
  /tmp/fake_output \
  1 \
  /tmp/fake_decisions.json \
  custom_review.json \
  custom_decisions.json \
  custom_update.json \
  custom_registry.json
python - <<'PY' > {str(capture)!r}
import json, os
print(json.dumps({{
  "python_bin": os.environ["VULD_SUPPORT_REVIEW_PYTHON_BIN"],
  "output_root": os.environ["VULD_SUPPORT_REVIEW_OUTPUT_ROOT"],
  "review_only": os.environ["VULD_SUPPORT_REVIEW_REVIEW_ONLY"],
  "decisions_file": os.environ["VULD_SUPPORT_REVIEW_DECISIONS_FILE"],
  "review_output_name": os.environ["VULD_SUPPORT_REVIEW_REVIEW_OUTPUT_NAME"],
  "decisions_output_name": os.environ["VULD_SUPPORT_REVIEW_DECISIONS_OUTPUT_NAME"],
  "update_output_name": os.environ["VULD_SUPPORT_REVIEW_UPDATE_OUTPUT_NAME"],
  "registry_output_name": os.environ["VULD_SUPPORT_REVIEW_REGISTRY_OUTPUT_NAME"],
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
        "python_bin": "/tmp/fake_python",
        "output_root": "/tmp/fake_output",
        "review_only": "1",
        "decisions_file": "/tmp/fake_decisions.json",
        "review_output_name": "custom_review.json",
        "decisions_output_name": "custom_decisions.json",
        "update_output_name": "custom_update.json",
        "registry_output_name": "custom_registry.json",
    }
