from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.run_matrix import VulnBundle
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


def test_start_sidecars_requires_declared_sidecar_policy(tmp_path: Path) -> None:
    bundle = VulnBundle(vuln_id="CWE-89", slug="cwe-89", workspace_subdir="app")

    with pytest.raises(docker_local.ExecutorError, match="policy.executor.sidecars is empty"):
        docker_local._start_sidecars(
            "sid-demo",
            bundle,
            executor_policy={"sidecars": []},
            run_dir=tmp_path,
            network_alias=docker_local.NetworkHandle("bridge"),
        )


def test_start_sidecars_requires_enabled_network(tmp_path: Path) -> None:
    bundle = VulnBundle(vuln_id="CWE-89", slug="cwe-89", workspace_subdir="app")

    with pytest.raises(docker_local.ExecutorError, match="executor network is disabled"):
        docker_local._start_sidecars(
            "sid-demo",
            bundle,
            executor_policy={"sidecars": [{"name": "mysql", "image": "mysql:8.0"}]},
            run_dir=tmp_path,
            network_alias=docker_local.NetworkHandle("none"),
        )


def test_resolve_service_env_prefers_resolved_contract(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        '{"service_env":{"DB_HOST":"sqli-db","DB_NAME":"sqliapp","APP_PORT":"5000"}}',
        encoding="utf-8",
    )

    env = docker_local._resolve_service_env(metadata_dir)

    assert env == {"DB_HOST": "sqli-db", "DB_NAME": "sqliapp", "APP_PORT": "5000"}


def test_resolve_health_path_prefers_executor_plan(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        '{"executor_plan":{"health_path":"/healthz"},"runtime_recipe":{"health_path":"/health"}}',
        encoding="utf-8",
    )

    path = docker_local._resolve_health_path(metadata_dir)

    assert path == "/healthz"


def test_skipped_bundle_summary_marks_bundle_unexecuted(tmp_path: Path) -> None:
    bundle = VulnBundle(vuln_id="NAME-CUSTOM-WEIRD-VULN", slug="name-custom-weird-vuln", workspace_subdir="app/name-custom-weird-vuln")
    plan = {
        "sid": "sid-demo",
        "paths": {
            "artifacts": str(tmp_path / "artifacts" / "sid-demo"),
        },
        "requirement": {"multi_vuln": True},
        "features": {"multi_vuln": True},
    }

    summary = docker_local._skipped_bundle_summary(
        "sid-demo",
        bundle,
        plan,
        reason="research blocked bundle",
    )

    assert summary["slug"] == "name-custom-weird-vuln"
    assert summary["executed"] is False
    assert summary["invocation"] == "skipped"
    assert summary["failed_stage"] == "research_short_circuit"
    assert summary["error"] == "research blocked bundle"
