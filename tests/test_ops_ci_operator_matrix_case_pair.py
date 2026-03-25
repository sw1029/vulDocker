from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_operator_matrix_case_pair_uses_defaults_and_partial_overrides(tmp_path: Path) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_operator_matrix_case_pair.sh")!r}
mapfile -t defaults < <(operator_emit_matrix_case_pair_args "" "")
mapfile -t partial < <(operator_emit_matrix_case_pair_args "alpha-case" "")
mapfile -t explicit < <(operator_emit_matrix_case_pair_args "alpha-case" "beta-case")
export DEFAULTS="$(printf '%s\\n' "${{defaults[@]}}")"
export PARTIAL="$(printf '%s\\n' "${{partial[@]}}")"
export EXPLICIT="$(printf '%s\\n' "${{explicit[@]}}")"
python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "defaults": os.environ["DEFAULTS"].splitlines(),
  "partial": os.environ["PARTIAL"].splitlines(),
  "explicit": os.environ["EXPLICIT"].splitlines(),
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
        "defaults": [
            "foobar-name-only-negative",
            "open-redirect-strict-dynamic-no-remote",
        ],
        "partial": [
            "alpha-case",
            "open-redirect-strict-dynamic-no-remote",
        ],
        "explicit": [
            "alpha-case",
            "beta-case",
        ],
    }
