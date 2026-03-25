from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_permission_artifact_summary_library_writes_expected_contract(tmp_path: Path) -> None:
    capture = tmp_path / "summary.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_permission_artifact_summary.sh")!r}
write_permission_artifact_summary {str(capture)!r} docker_permission_artifact.txt alpha-case beta-case
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
        "schema_version": "permission_artifact_summary@0.1",
        "permission_artifact_name": "docker_permission_artifact.txt",
        "permission_artifact_count": 2,
        "runtime_equivalent_helper_truth_available": False,
        "recommended_action": "unrestricted_docker_rerun",
        "permission_artifact_cases": ["alpha-case", "beta-case"],
    }
