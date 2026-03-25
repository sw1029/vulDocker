from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_case_chain_standard_entrypoint_dispatch_supports_direct_and_repeatability(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "probe.sh"
    capture = tmp_path / "capture.json"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_standard_entrypoint_dispatch.sh")!r}
case_chain_resolve_standard_entrypoint_runner direct DIRECT_RUNNER
case_chain_resolve_standard_entrypoint_runner repeatability REPEAT_RUNNER
export DIRECT_RUNNER REPEAT_RUNNER
python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "direct_runner": os.environ["DIRECT_RUNNER"],
  "repeat_runner": os.environ["REPEAT_RUNNER"],
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
        "direct_runner": "case_chain_run_direct_wrapper",
        "repeat_runner": "case_chain_run_repeatability_wrapper",
    }


def test_case_chain_standard_entrypoint_dispatch_rejects_unknown_profile(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_chain_standard_entrypoint_dispatch.sh")!r}
case_chain_resolve_standard_entrypoint_runner unknown RUNNER
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr == "unknown case-chain standard entrypoint profile: unknown\n"
