from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from executor.runtime import docker_local


def test_build_poc_exec_cmd_sets_workdir_and_pythonpath(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()

    cmd = docker_local._build_poc_exec_cmd(
        "demo-container",
        metadata_dir,
        "/tmp/poc.py",
        "http://127.0.0.1:5000",
        payload=None,
    )

    assert cmd[0] == docker_local.DOCKER_BIN
    assert cmd[1:6] == ["exec", "-w", "/app", "-e", "PYTHONPATH=/app"]
    assert cmd[6] == "demo-container"
    assert cmd[7:10] == ["python", "/tmp/poc.py", "--base-url"]
