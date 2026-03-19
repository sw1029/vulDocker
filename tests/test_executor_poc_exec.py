from __future__ import annotations

import json
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


def test_build_poc_exec_cmd_drops_payload_placeholder_when_payload_missing(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "generator_contract.json").write_text(
        json.dumps({"poc_cmd": "python poc.py --base-url {{base_url}} --payload {{payload}}"}),
        encoding="utf-8",
    )

    cmd = docker_local._build_poc_exec_cmd(
        "demo-container",
        metadata_dir,
        "/tmp/poc.py",
        "http://127.0.0.1:5000",
        payload=None,
    )

    assert cmd == [
        docker_local.DOCKER_BIN,
        "exec",
        "-w",
        "/app",
        "-e",
        "PYTHONPATH=/app",
        "demo-container",
        "python",
        "/tmp/poc.py",
        "--base-url",
        "http://127.0.0.1:5000",
    ]


def test_build_poc_exec_cmd_renders_payload_placeholder_when_payload_present(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "generator_contract.json").write_text(
        json.dumps({"poc_cmd": "python poc.py --base-url {{base_url}} --payload {{payload}}"}),
        encoding="utf-8",
    )

    cmd = docker_local._build_poc_exec_cmd(
        "demo-container",
        metadata_dir,
        "/tmp/poc.py",
        "http://127.0.0.1:5000",
        payload="/local",
    )

    assert cmd == [
        docker_local.DOCKER_BIN,
        "exec",
        "-w",
        "/app",
        "-e",
        "PYTHONPATH=/app",
        "demo-container",
        "python",
        "/tmp/poc.py",
        "--base-url",
        "http://127.0.0.1:5000",
        "--payload",
        "/local",
    ]


def test_build_poc_exec_cmd_prefers_passed_poc_cmd_over_metadata(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "generator_contract.json").write_text(
        json.dumps({"poc_cmd": "python poc.py --base-url {{base_url}}"}),
        encoding="utf-8",
    )

    cmd = docker_local._build_poc_exec_cmd(
        "demo-container",
        metadata_dir,
        "/tmp/poc.py",
        "http://127.0.0.1:5000",
        poc_cmd="python /tmp/poc.py --base-url {{base_url}} --payload {{payload}}",
        payload="/runtime",
    )

    assert cmd == [
        docker_local.DOCKER_BIN,
        "exec",
        "-w",
        "/app",
        "-e",
        "PYTHONPATH=/app",
        "demo-container",
        "python",
        "/tmp/poc.py",
        "--base-url",
        "http://127.0.0.1:5000",
        "--payload",
        "/runtime",
    ]


def test_start_sidecars_requires_declared_sidecar_policy(tmp_path: Path) -> None:
    bundle = VulnBundle(vuln_id="CWE-89", slug="cwe-89", workspace_subdir="app")

    with pytest.raises(docker_local.ExecutorError, match="resolved sidecar plan is empty"):
        docker_local._start_sidecars(
            "sid-demo",
            bundle,
            execution_surface={"sidecars": []},
            workspace=None,
            run_dir=tmp_path,
            network_alias=docker_local.NetworkHandle("bridge"),
        )


def test_start_sidecars_requires_enabled_network(tmp_path: Path) -> None:
    bundle = VulnBundle(vuln_id="CWE-89", slug="cwe-89", workspace_subdir="app")

    with pytest.raises(docker_local.ExecutorError, match="executor network is disabled"):
        docker_local._start_sidecars(
            "sid-demo",
            bundle,
            execution_surface={"sidecars": [{"name": "mysql", "image": "mysql:8.0"}]},
            workspace=None,
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


def test_resolve_healthchecks_prefers_executor_plan(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "executor_plan": {
                    "healthchecks": [
                        {"node": "service", "path": "/ready", "port": 8080, "transport": "http"}
                    ]
                },
                "runtime_recipe": {"health_path": "/health"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    healthchecks = docker_local._resolve_healthchecks(metadata_dir)

    assert healthchecks == [{"node": "service", "path": "/ready", "port": 8080, "transport": "http"}]


def test_resolve_health_path_can_use_executor_plan_healthchecks_when_explicit_path_missing(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "executor_plan": {
                    "healthchecks": [
                        {"node": "service", "path": "/ready", "port": 8080, "transport": "http"}
                    ]
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    path = docker_local._resolve_health_path(metadata_dir)

    assert path == "/ready"


def test_resolve_healthchecks_uses_runtime_recipe_when_plan_and_graph_missing(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "runtime_recipe": {
                    "healthchecks": [
                        {"node": "service", "path": "/runtime-ready", "port": 8090, "transport": "http"}
                    ]
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    healthchecks = docker_local._resolve_healthchecks(metadata_dir)

    assert healthchecks == [{"node": "service", "path": "/runtime-ready", "port": 8090, "transport": "http"}]


def test_resolve_health_path_uses_runtime_recipe_healthchecks_when_other_sources_missing(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "runtime_recipe": {
                    "healthchecks": [
                        {"node": "service", "path": "/runtime-ready", "port": 8090, "transport": "http"}
                    ]
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    path = docker_local._resolve_health_path(metadata_dir)

    assert path == "/runtime-ready"


def test_resolve_execution_surface_preserves_seed_files_from_executor_plan(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "executor_plan": {
                    "service_port": 8000,
                    "seed_files": ["schema.sql", "./seed_data.sql"],
                    "seed_strategy": "sqlite_service_init",
                    "seed_strategy_source": "runtime_recipe.seed_files+db",
                },
                "runtime_graph": {
                    "seed_files": ["schema.sql"],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    surface = docker_local._resolve_execution_surface(metadata_dir, tmp_path, {})

    assert surface["service_entry"] == "app.py"
    assert surface["seed_files"] == ["schema.sql", "seed_data.sql"]
    assert surface["seed_files_source"] == "executor_plan.seed_files"
    assert surface["seed_strategy"] == "sqlite_service_init"
    assert surface["seed_strategy_source"] == "runtime_recipe.seed_files+db"


def test_resolve_execution_surface_can_resolve_poc_entry_from_runtime_graph_exploit_path(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "executor_plan": {"service_port": 8000},
                "runtime_graph": {
                    "exploit_path": {
                        "entrypoint": "tools/poc_runtime.py",
                        "service_entry": "app.py",
                        "target_node": "service",
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    surface = docker_local._resolve_execution_surface(metadata_dir, tmp_path, {})

    assert surface["poc_entry"] == "tools/poc_runtime.py"
    assert surface["poc_entry_source"] == "runtime_graph.exploit_path.entrypoint"


def test_resolve_execution_surface_can_resolve_poc_cmd_from_resolved_contract(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "poc_cmd": "python poc.py --base-url {{base_url}} --payload {{payload}}",
                "executor_plan": {"service_port": 8000},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    surface = docker_local._resolve_execution_surface(metadata_dir, tmp_path, {})

    assert surface["poc_cmd"] == "python poc.py --base-url {{base_url}} --payload {{payload}}"
    assert surface["poc_cmd_source"] == "resolved_contract.poc_cmd"


def test_validate_service_entry_contract_rejects_missing_file(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(docker_local.ExecutorError, match="Declared service entry missing from workspace"):
        docker_local._validate_service_entry_contract(
            workspace,
            {
                "service_entry": "server.py",
                "service_entry_source": "runtime_graph.exploit_path.service_entry",
            },
        )


def test_validate_service_entry_contract_rejects_absolute_path(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(docker_local.ExecutorError, match="Invalid service entry path"):
        docker_local._validate_service_entry_contract(
            workspace,
            {
                "service_entry": "/tmp/app.py",
                "service_entry_source": "executor_plan.service_entry",
            },
        )


def test_validate_service_entry_contract_rejects_parent_traversal(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(docker_local.ExecutorError, match="Invalid service entry path"):
        docker_local._validate_service_entry_contract(
            workspace,
            {
                "service_entry": "../app.py",
                "service_entry_source": "executor_plan.service_entry",
            },
        )


def test_validate_service_entry_contract_accepts_existing_file(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "server.py").write_text("print('ok')\n", encoding="utf-8")

    docker_local._validate_service_entry_contract(
        workspace,
        {
            "service_entry": "server.py",
            "service_entry_source": "runtime_graph.exploit_path.service_entry",
        },
    )


def test_validate_poc_entry_contract_rejects_missing_file(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(docker_local.ExecutorError, match="Declared poc entry missing from workspace"):
        docker_local._validate_poc_entry_contract(
            workspace,
            {
                "poc_entry": "tools/poc_runtime.py",
                "poc_entry_source": "runtime_graph.exploit_path.entrypoint",
            },
        )


def test_validate_poc_entry_contract_rejects_absolute_path(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(docker_local.ExecutorError, match="Invalid poc entry path"):
        docker_local._validate_poc_entry_contract(
            workspace,
            {
                "poc_entry": "/tmp/poc.py",
                "poc_entry_source": "runtime_graph.exploit_path.entrypoint",
            },
        )


def test_validate_poc_entry_contract_rejects_parent_traversal(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(docker_local.ExecutorError, match="Invalid poc entry path"):
        docker_local._validate_poc_entry_contract(
            workspace,
            {
                "poc_entry": "../poc.py",
                "poc_entry_source": "runtime_graph.exploit_path.entrypoint",
            },
        )


def test_validate_poc_entry_contract_accepts_existing_file(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "tools").mkdir(parents=True)
    (workspace / "tools" / "poc_runtime.py").write_text("print('ok')\n", encoding="utf-8")

    docker_local._validate_poc_entry_contract(
        workspace,
        {
            "poc_entry": "tools/poc_runtime.py",
            "poc_entry_source": "runtime_graph.exploit_path.entrypoint",
        },
    )


def test_validate_poc_cmd_contract_accepts_matching_local_script_reference() -> None:
    docker_local._validate_poc_cmd_contract(
        {
            "poc_entry": "poc.py",
            "poc_entry_source": "executor_plan.poc_entry",
            "poc_cmd": "python poc.py --base-url {{base_url}}",
            "poc_cmd_source": "resolved_contract.poc_cmd",
        }
    )


def test_validate_poc_cmd_contract_accepts_placeholder_form() -> None:
    docker_local._validate_poc_cmd_contract(
        {
            "poc_entry": "tools/poc_runtime.py",
            "poc_entry_source": "runtime_graph.exploit_path.entrypoint",
            "poc_cmd": "python {{poc_path}} --base-url {{base_url}} --payload {{payload}}",
            "poc_cmd_source": "resolved_contract.poc_cmd",
        }
    )


def test_validate_poc_cmd_contract_accepts_inline_command_without_local_script_reference() -> None:
    docker_local._validate_poc_cmd_contract(
        {
            "poc_entry": "poc.py",
            "poc_entry_source": "executor_plan.poc_entry",
            "poc_cmd": "python -c \"print('ok')\"",
            "poc_cmd_source": "resolved_contract.poc_cmd",
        }
    )


def test_validate_poc_cmd_contract_rejects_mismatched_local_script_reference() -> None:
    with pytest.raises(docker_local.ExecutorError, match="Declared poc_cmd references a local script inconsistent with poc_entry"):
        docker_local._validate_poc_cmd_contract(
            {
                "poc_entry": "poc.py",
                "poc_entry_source": "executor_plan.poc_entry",
                "poc_cmd": "python exploit.py --base-url {{base_url}}",
                "poc_cmd_source": "resolved_contract.poc_cmd",
            }
        )


def test_validate_healthcheck_contract_accepts_service_http_and_tcp_probes() -> None:
    docker_local._validate_healthcheck_contract(
        {
            "healthchecks": [
                {"node": "service", "path": "/ready", "port": 8080, "transport": "http"},
                {"node": "service", "transport": "tcp", "port": 8080},
            ],
            "healthchecks_source": "executor_plan.healthchecks",
        }
    )


def test_validate_healthcheck_contract_rejects_unsupported_transport() -> None:
    with pytest.raises(docker_local.ExecutorError, match="malformed service probes"):
        docker_local._validate_healthcheck_contract(
            {
                "healthchecks": [
                    {"node": "service", "path": "/ready", "port": 8080, "transport": "grpc"},
                ],
                "healthchecks_source": "executor_plan.healthchecks",
            }
        )


def test_validate_healthcheck_contract_rejects_http_probe_without_path() -> None:
    with pytest.raises(docker_local.ExecutorError, match="malformed service probes"):
        docker_local._validate_healthcheck_contract(
            {
                "healthchecks": [
                    {"node": "service", "port": 8080, "transport": "http"},
                ],
                "healthchecks_source": "runtime_recipe.healthchecks",
            }
        )


def test_validate_healthcheck_contract_rejects_tcp_probe_with_path() -> None:
    with pytest.raises(docker_local.ExecutorError, match="malformed service probes"):
        docker_local._validate_healthcheck_contract(
            {
                "healthchecks": [
                    {"node": "service", "path": "/ready", "port": 8080, "transport": "tcp"},
                ],
                "healthchecks_source": "runtime_graph.healthchecks",
            }
        )


def test_validate_healthcheck_contract_rejects_non_service_nodes() -> None:
    with pytest.raises(docker_local.ExecutorError, match="unsupported non-service nodes"):
        docker_local._validate_healthcheck_contract(
            {
                "healthchecks": [
                    {"node": "sidecar:mysql-main", "path": "/ready", "port": 3306, "transport": "http"},
                ],
                "healthchecks_source": "executor_plan.healthchecks",
            }
        )


def test_validate_healthcheck_contract_accepts_matching_service_port() -> None:
    docker_local._validate_healthcheck_contract(
        {
            "service_port": 8080,
            "service_port_source": "executor_plan.service_port",
            "healthchecks": [
                {"node": "service", "path": "/ready", "port": 8080, "transport": "http"},
            ],
            "healthchecks_source": "executor_plan.healthchecks",
        }
    )


def test_validate_healthcheck_contract_rejects_conflicting_service_probe_ports() -> None:
    with pytest.raises(docker_local.ExecutorError, match="conflicting service probe ports"):
        docker_local._validate_healthcheck_contract(
            {
                "service_port": 8080,
                "service_port_source": "executor_plan.service_port",
                "healthchecks": [
                    {"node": "service", "path": "/ready", "port": 8080, "transport": "http"},
                    {"node": "service", "path": "/live", "port": 9090, "transport": "http"},
                ],
                "healthchecks_source": "executor_plan.healthchecks",
            }
        )


def test_validate_healthcheck_contract_rejects_service_port_mismatch() -> None:
    with pytest.raises(docker_local.ExecutorError, match="inconsistent with resolved service_port"):
        docker_local._validate_healthcheck_contract(
            {
                "service_port": 8080,
                "service_port_source": "executor_plan.service_port",
                "healthchecks": [
                    {"node": "service", "path": "/ready", "port": 9090, "transport": "http"},
                ],
                "healthchecks_source": "runtime_recipe.healthchecks",
            }
        )


def test_validate_healthcheck_contract_accepts_matching_health_path() -> None:
    docker_local._validate_healthcheck_contract(
        {
            "service_port": 8080,
            "service_port_source": "executor_plan.service_port",
            "health_path": "/ready",
            "health_path_source": "executor_plan.health_path",
            "healthchecks": [
                {"node": "service", "path": "/ready", "port": 8080, "transport": "http"},
            ],
            "healthchecks_source": "executor_plan.healthchecks",
        }
    )


def test_validate_healthcheck_contract_rejects_health_path_mismatch() -> None:
    with pytest.raises(docker_local.ExecutorError, match="inconsistent with resolved health_path"):
        docker_local._validate_healthcheck_contract(
            {
                "service_port": 8080,
                "service_port_source": "executor_plan.service_port",
                "health_path": "/healthz",
                "health_path_source": "executor_plan.health_path",
                "healthchecks": [
                    {"node": "service", "path": "/ready", "port": 8080, "transport": "http"},
                ],
                "healthchecks_source": "runtime_recipe.healthchecks",
            }
        )


def test_validate_service_endpoint_contract_rejects_local_base_url_port_mismatch() -> None:
    with pytest.raises(docker_local.ExecutorError, match="base_url is inconsistent with service_port"):
        docker_local._validate_service_endpoint_contract(
            {
                "service_port": 5000,
                "service_port_source": "executor_plan.service_port",
                "base_url": "http://127.0.0.1:9000",
                "base_url_source": "executor_plan.base_url",
            }
        )


def test_validate_service_endpoint_contract_accepts_matching_local_base_url() -> None:
    docker_local._validate_service_endpoint_contract(
        {
            "service_port": 5000,
            "service_port_source": "executor_plan.service_port",
            "base_url": "http://127.0.0.1:5000",
            "base_url_source": "executor_plan.base_url",
        }
    )


def test_validate_service_endpoint_contract_allows_remote_base_url_override() -> None:
    docker_local._validate_service_endpoint_contract(
        {
            "service_port": 5000,
            "service_port_source": "executor_plan.service_port",
            "base_url": "http://service.internal:9000",
            "base_url_source": "policy.executor.base_url",
        }
    )


def test_validate_sidecar_runtime_contract_accepts_same_family_hints() -> None:
    docker_local._validate_sidecar_runtime_contract(
        {
            "db": "mysql",
            "db_source": "executor_plan.db",
            "sidecars": [
                {
                    "name": "mysql-main",
                    "type": "mysql",
                    "image": "mariadb:11",
                }
            ],
            "sidecars_source": "executor_plan.sidecars",
        }
    )


def test_validate_sidecar_runtime_contract_rejects_conflicting_runtime_hints() -> None:
    with pytest.raises(docker_local.ExecutorError, match="sidecar runtime hints are inconsistent"):
        docker_local._validate_sidecar_runtime_contract(
            {
                "sidecars": [
                    {
                        "name": "db-main",
                        "type": "mysql",
                        "image": "postgres:16",
                    }
                ],
                "sidecars_source": "runtime_graph.nodes.sidecar",
            }
        )


def test_validate_sidecar_runtime_contract_rejects_conflicting_db_family() -> None:
    with pytest.raises(docker_local.ExecutorError, match="sidecar runtime is inconsistent with resolved db family"):
        docker_local._validate_sidecar_runtime_contract(
            {
                "db": "mysql",
                "db_source": "executor_plan.db",
                "sidecars": [
                    {
                        "name": "postgres-main",
                        "type": "postgres",
                        "image": "postgres:16",
                    }
                ],
                "sidecars_source": "generator_manifest.metadata.target_sidecars",
            }
        )


def test_validate_sidecar_identity_contract_accepts_unique_names_and_aliases() -> None:
    docker_local._validate_sidecar_identity_contract(
        {
            "sidecars": [
                {"name": "mysql-main", "type": "mysql", "aliases": ["db-internal"]},
                {"name": "redis-main", "type": "redis", "aliases": ["cache-internal"]},
            ],
            "sidecars_source": "executor_plan.sidecars",
        }
    )


def test_validate_sidecar_identity_contract_rejects_duplicate_sidecar_names() -> None:
    with pytest.raises(docker_local.ExecutorError, match="duplicate sidecar names"):
        docker_local._validate_sidecar_identity_contract(
            {
                "sidecars": [
                    {"name": "mysql-main", "type": "mysql", "aliases": ["db-internal"]},
                    {"name": "mysql-main", "type": "mysql", "aliases": ["db-secondary"]},
                ],
                "sidecars_source": "runtime_graph.nodes.sidecar",
            }
        )


def test_validate_sidecar_identity_contract_rejects_alias_collision_across_sidecars() -> None:
    with pytest.raises(docker_local.ExecutorError, match="aliases collide with other sidecar identities"):
        docker_local._validate_sidecar_identity_contract(
            {
                "sidecars": [
                    {"name": "mysql-main", "type": "mysql", "aliases": ["db-internal"]},
                    {"name": "postgres-main", "type": "postgres", "aliases": ["db-internal"]},
                ],
                "sidecars_source": "executor_plan.sidecars",
            }
        )


def test_validate_sidecar_identity_contract_rejects_alias_collision_with_other_sidecar_name() -> None:
    with pytest.raises(docker_local.ExecutorError, match="aliases collide with other sidecar identities"):
        docker_local._validate_sidecar_identity_contract(
            {
                "sidecars": [
                    {"name": "mysql-main", "type": "mysql", "aliases": ["postgres-main"]},
                    {"name": "postgres-main", "type": "postgres", "aliases": ["db-internal"]},
                ],
                "sidecars_source": "runtime_graph.nodes.sidecar",
            }
        )


def test_validate_service_runtime_binding_contract_accepts_matching_app_port() -> None:
    docker_local._validate_service_runtime_binding_contract(
        {
            "service_port": 5000,
            "service_port_source": "executor_plan.service_port",
            "service_env": {"APP_PORT": "5000", "DB_HOST": "db-internal"},
            "service_env_source": "executor_plan.service_env",
        }
    )


def test_validate_service_runtime_binding_contract_accepts_matching_port() -> None:
    docker_local._validate_service_runtime_binding_contract(
        {
            "service_port": 8080,
            "service_port_source": "runtime_recipe.healthchecks[service].port",
            "service_env": {"PORT": "8080"},
            "service_env_source": "runtime_graph.env_contract",
        }
    )


def test_validate_service_runtime_binding_contract_rejects_mismatched_app_port() -> None:
    with pytest.raises(docker_local.ExecutorError, match="service env port bindings are inconsistent with resolved service_port"):
        docker_local._validate_service_runtime_binding_contract(
            {
                "service_port": 5000,
                "service_port_source": "executor_plan.service_port",
                "service_env": {"APP_PORT": "9000", "DB_HOST": "db-internal"},
                "service_env_source": "executor_plan.service_env",
            }
        )


def test_validate_service_runtime_binding_contract_rejects_mismatched_port() -> None:
    with pytest.raises(docker_local.ExecutorError, match="service env port bindings are inconsistent with resolved service_port"):
        docker_local._validate_service_runtime_binding_contract(
            {
                "service_port": 5000,
                "service_port_source": "executor_plan.service_port",
                "service_env": {"PORT": "7000"},
                "service_env_source": "runtime_hint_sidecar_defaults",
            }
        )


def test_validate_service_runtime_binding_contract_accepts_matching_mysql_db_port() -> None:
    docker_local._validate_service_runtime_binding_contract(
        {
            "service_port": 5000,
            "service_port_source": "executor_plan.service_port",
            "service_env": {"APP_PORT": "5000", "DB_PORT": "3306"},
            "service_env_source": "runtime_hint_sidecar_defaults",
            "db": "mysql",
            "db_source": "executor_plan.db",
        }
    )


def test_validate_service_runtime_binding_contract_rejects_mismatched_mysql_db_port() -> None:
    with pytest.raises(docker_local.ExecutorError, match="DB_PORT is inconsistent with resolved database runtime"):
        docker_local._validate_service_runtime_binding_contract(
            {
                "service_port": 5000,
                "service_port_source": "executor_plan.service_port",
                "service_env": {"APP_PORT": "5000", "DB_PORT": "5432"},
                "service_env_source": "runtime_hint_sidecar_defaults",
                "db": "mysql",
                "db_source": "executor_plan.db",
            }
        )


def test_validate_service_runtime_binding_contract_rejects_mismatched_postgres_db_port_from_sidecar() -> None:
    with pytest.raises(docker_local.ExecutorError, match="DB_PORT is inconsistent with resolved database runtime"):
        docker_local._validate_service_runtime_binding_contract(
            {
                "service_port": 5000,
                "service_port_source": "executor_plan.service_port",
                "service_env": {"APP_PORT": "5000", "DB_PORT": "3306"},
                "service_env_source": "runtime_hint_sidecar_defaults",
                "sidecars": [{"name": "postgres-main", "type": "postgres", "image": "postgres:16"}],
            }
        )


def test_validate_service_runtime_binding_contract_accepts_matching_db_host_from_sidecar_alias() -> None:
    docker_local._validate_service_runtime_binding_contract(
        {
            "service_port": 5000,
            "service_port_source": "executor_plan.service_port",
            "service_env": {"APP_PORT": "5000", "DB_HOST": "db-internal", "DB_PORT": "3306"},
            "service_env_source": "runtime_hint_sidecar_defaults",
            "sidecars": [{"name": "mysql-main", "type": "mysql", "aliases": ["db-internal"]}],
            "sidecars_source": "generator_manifest.metadata.target_sidecars",
        }
    )


def test_validate_service_runtime_binding_contract_rejects_mismatched_db_host_from_sidecar_alias() -> None:
    with pytest.raises(docker_local.ExecutorError, match="DB_HOST is inconsistent with resolved sidecar aliases"):
        docker_local._validate_service_runtime_binding_contract(
            {
                "service_port": 5000,
                "service_port_source": "executor_plan.service_port",
                "service_env": {"APP_PORT": "5000", "DB_HOST": "db-runtime", "DB_PORT": "3306"},
                "service_env_source": "runtime_hint_sidecar_defaults",
                "sidecars": [{"name": "mysql-main", "type": "mysql", "aliases": ["db-internal"]}],
                "sidecars_source": "generator_manifest.metadata.target_sidecars",
            }
        )


def test_validate_service_runtime_binding_contract_accepts_matching_mysql_db_credentials() -> None:
    docker_local._validate_service_runtime_binding_contract(
        {
            "service_port": 5000,
            "service_port_source": "executor_plan.service_port",
            "service_env": {
                "APP_PORT": "5000",
                "DB_HOST": "db-internal",
                "DB_PORT": "3306",
                "DB_NAME": "appdb",
                "DB_USER": "appuser",
                "DB_PASSWORD": "apppw",
            },
            "service_env_source": "runtime_hint_sidecar_defaults",
            "sidecars": [
                {
                    "name": "mysql-main",
                    "type": "mysql",
                    "aliases": ["db-internal"],
                    "env": {
                        "MYSQL_DATABASE": "appdb",
                        "MYSQL_USER": "appuser",
                        "MYSQL_PASSWORD": "apppw",
                    },
                }
            ],
            "sidecars_source": "generator_manifest.metadata.target_sidecars",
        }
    )


def test_validate_service_runtime_binding_contract_rejects_mismatched_mysql_db_credentials() -> None:
    with pytest.raises(docker_local.ExecutorError, match="DB credentials are inconsistent with resolved sidecar env"):
        docker_local._validate_service_runtime_binding_contract(
            {
                "service_port": 5000,
                "service_port_source": "executor_plan.service_port",
                "service_env": {
                    "APP_PORT": "5000",
                    "DB_HOST": "db-internal",
                    "DB_PORT": "3306",
                    "DB_NAME": "runtime_db",
                    "DB_USER": "appuser",
                    "DB_PASSWORD": "apppw",
                },
                "service_env_source": "runtime_hint_sidecar_defaults",
                "sidecars": [
                    {
                        "name": "mysql-main",
                        "type": "mysql",
                        "aliases": ["db-internal"],
                        "env": {
                            "MYSQL_DATABASE": "appdb",
                            "MYSQL_USER": "appuser",
                            "MYSQL_PASSWORD": "apppw",
                        },
                    }
                ],
                "sidecars_source": "generator_manifest.metadata.target_sidecars",
            }
        )


def test_validate_service_runtime_binding_contract_accepts_matching_db_credentials_from_mysql_sidecar() -> None:
    docker_local._validate_service_runtime_binding_contract(
        {
            "service_port": 5000,
            "service_port_source": "executor_plan.service_port",
            "service_env": {
                "APP_PORT": "5000",
                "DB_HOST": "db-internal",
                "DB_PORT": "3306",
                "DB_NAME": "appdb",
                "DB_USER": "appuser",
                "DB_PASSWORD": "apppw",
            },
            "service_env_source": "runtime_hint_sidecar_defaults",
            "sidecars": [
                {
                    "name": "mysql-main",
                    "type": "mysql",
                    "aliases": ["db-internal"],
                    "env": {
                        "MYSQL_DATABASE": "appdb",
                        "MYSQL_USER": "appuser",
                        "MYSQL_PASSWORD": "apppw",
                    },
                }
            ],
            "sidecars_source": "generator_manifest.metadata.target_sidecars",
        }
    )


def test_validate_service_runtime_binding_contract_rejects_mismatched_db_credentials_from_mysql_sidecar() -> None:
    with pytest.raises(docker_local.ExecutorError, match="DB credentials are inconsistent with resolved sidecar env"):
        docker_local._validate_service_runtime_binding_contract(
            {
                "service_port": 5000,
                "service_port_source": "executor_plan.service_port",
                "service_env": {
                    "APP_PORT": "5000",
                    "DB_HOST": "db-internal",
                    "DB_PORT": "3306",
                    "DB_NAME": "runtime_db",
                    "DB_USER": "appuser",
                    "DB_PASSWORD": "apppw",
                },
                "service_env_source": "runtime_hint_sidecar_defaults",
                "sidecars": [
                    {
                        "name": "mysql-main",
                        "type": "mysql",
                        "aliases": ["db-internal"],
                        "env": {
                            "MYSQL_DATABASE": "appdb",
                            "MYSQL_USER": "appuser",
                            "MYSQL_PASSWORD": "apppw",
                        },
                    }
                ],
                "sidecars_source": "generator_manifest.metadata.target_sidecars",
            }
        )


def test_resolve_execution_surface_preserves_env_contract_from_executor_plan(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "executor_plan": {
                    "service_port": 8000,
                    "service_env": {"APP_PORT": "8000", "DB_HOST": "db-internal"},
                    "env_contract": [
                        {"scope": "service", "name": "APP_PORT", "value": "8000"},
                        {"scope": "service", "name": "DB_HOST", "value": "db-internal"},
                    ],
                    "network_contract": [
                        {"scope": "service", "name": "DB_HOST", "alias": "db-internal"},
                        {"scope": "sidecar:mysql-main", "alias": "db-internal"},
                    ],
                    "network_contract_source": "executor_plan.network_contract",
                    "volume_contract": [
                        {
                            "scope": "sidecar:mysql-main",
                            "source": "workspace",
                            "target": "/seed-input",
                            "mode": "ro",
                        }
                    ],
                    "volume_contract_source": "executor_plan.volume_contract",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    surface = docker_local._resolve_execution_surface(metadata_dir, tmp_path, {})

    assert surface["env_contract"] == [
        {"scope": "service", "name": "APP_PORT", "value": "8000"},
        {"scope": "service", "name": "DB_HOST", "value": "db-internal"},
    ]
    assert surface["env_contract_source"] == "executor_plan.env_contract"
    assert surface["network_contract"] == [
        {"scope": "service", "name": "DB_HOST", "alias": "db-internal"},
        {"scope": "sidecar:mysql-main", "alias": "db-internal"},
    ]
    assert surface["network_contract_source"] == "executor_plan.network_contract"
    assert surface["volume_contract"] == [
        {
            "scope": "sidecar:mysql-main",
            "source": "workspace",
            "target": "/seed-input",
            "mode": "ro",
        }
    ]
    assert surface["volume_contract_source"] == "executor_plan.volume_contract"


def test_resolve_execution_surface_can_reconstruct_sidecars_from_runtime_graph_nodes(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "executor_plan": {"service_port": 8000},
                "runtime_graph": {
                    "sidecars_source": "runtime_graph.nodes.sidecar",
                    "nodes": [
                        {"id": "service", "kind": "service"},
                        {
                            "id": "sidecar:postgres-main",
                            "kind": "sidecar",
                            "sidecar_type": "postgres",
                            "image": "postgres:16",
                            "aliases": ["db-internal"],
                            "env": {"POSTGRES_DB": "demo", "POSTGRES_USER": "demo_user"},
                            "ready_probe": {"type": "postgres", "retries": 4},
                            "startup_order_index": 1,
                        },
                    ],
                    "network_contract": [
                        {"scope": "service", "name": "DB_HOST", "alias": "db-internal"},
                        {"scope": "sidecar:postgres-main", "alias": "db-internal"},
                    ],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    surface = docker_local._resolve_execution_surface(metadata_dir, tmp_path, {})

    assert surface["sidecars"] == [
        {
            "name": "postgres-main",
            "type": "postgres",
            "image": "postgres:16",
            "aliases": ["db-internal"],
            "env": {"POSTGRES_DB": "demo", "POSTGRES_USER": "demo_user"},
            "ready_probe": {"type": "postgres", "retries": 4},
        }
    ]
    assert surface["sidecars_source"] == "runtime_graph.nodes.sidecar"
    assert surface["sidecar_start_order"] == ["postgres-main"]
    assert surface["sidecar_start_order_source"] == "runtime_graph.nodes.startup_order_index"


def test_resolve_execution_surface_can_reconstruct_sidecar_env_from_runtime_graph_env_contract(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "executor_plan": {"service_port": 8000},
                "runtime_graph": {
                    "nodes": [
                        {"id": "service", "kind": "service"},
                        {
                            "id": "sidecar:mysql-main",
                            "kind": "sidecar",
                            "sidecar_type": "mysql",
                            "image": "mysql:8.0",
                            "aliases": ["db-internal"],
                        },
                    ],
                    "env_contract": [
                        {"scope": "sidecar:mysql-main", "name": "MYSQL_DATABASE", "value": "graph_db"},
                        {"scope": "sidecar:mysql-main", "name": "MYSQL_USER", "value": "graph_user"},
                    ],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    surface = docker_local._resolve_execution_surface(metadata_dir, tmp_path, {})

    assert surface["sidecars"] == [
        {
            "name": "mysql-main",
            "type": "mysql",
            "image": "mysql:8.0",
            "aliases": ["db-internal"],
            "env": {"MYSQL_DATABASE": "graph_db", "MYSQL_USER": "graph_user"},
        }
    ]
    assert surface["sidecars_source"] == "runtime_graph.nodes+env_contract"


def test_resolve_execution_surface_can_derive_sidecar_start_order_from_runtime_graph_nodes(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "executor_plan": {
                    "service_port": 8000,
                    "sidecars": [
                        {"name": "mysql-main", "type": "mysql", "image": "mysql:8.0"},
                        {"name": "redis-main", "type": "redis", "image": "redis:7"},
                    ],
                },
                "runtime_graph": {
                    "nodes": [
                        {"id": "service", "kind": "service"},
                        {"id": "sidecar:redis-main", "kind": "sidecar", "startup_order_index": 2},
                        {"id": "sidecar:mysql-main", "kind": "sidecar", "startup_order_index": 1},
                    ]
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    surface = docker_local._resolve_execution_surface(metadata_dir, tmp_path, {})

    assert surface["sidecar_start_order"] == ["mysql-main", "redis-main"]
    assert surface["sidecar_start_order_source"] == "runtime_graph.nodes.startup_order_index"


def test_resolve_execution_surface_can_derive_sidecar_start_order_from_runtime_graph_edges(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "executor_plan": {
                    "service_port": 8000,
                    "sidecars": [
                        {"name": "mysql-main", "type": "mysql", "image": "mysql:8.0"},
                        {"name": "redis-main", "type": "redis", "image": "redis:7"},
                    ],
                },
                "runtime_graph": {
                    "nodes": [
                        {"id": "service", "kind": "service"},
                        {"id": "sidecar:mysql-main", "kind": "sidecar"},
                        {"id": "sidecar:redis-main", "kind": "sidecar"},
                    ],
                    "edges": [
                        {"from": "service", "to": "sidecar:mysql-main", "kind": "runtime_dependency"},
                        {
                            "from": "service",
                            "to": "sidecar:redis-main",
                            "kind": "runtime_dependency",
                            "startup_after": "sidecar:mysql-main",
                        },
                    ],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    surface = docker_local._resolve_execution_surface(metadata_dir, tmp_path, {})

    assert surface["sidecar_start_order"] == ["mysql-main", "redis-main"]
    assert surface["sidecar_start_order_source"] == "runtime_graph.edges.startup_after"


def test_resolve_execution_surface_can_reconstruct_service_env_from_runtime_graph_env_contract(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "executor_plan": {"service_port": 8000},
                "runtime_graph": {
                    "env_contract": [
                        {"scope": "service", "name": "APP_PORT", "value": "8000"},
                        {"scope": "service", "name": "DB_HOST", "value": "db-internal"},
                        {"scope": "sidecar:mysql-main", "name": "MYSQL_USER", "value": "app_user"},
                    ]
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    surface = docker_local._resolve_execution_surface(metadata_dir, tmp_path, {})

    assert surface["service_env"] == {"APP_PORT": "8000", "DB_HOST": "db-internal"}
    assert surface["service_env_source"] == "runtime_graph.env_contract"


def test_resolve_execution_surface_uses_generator_manifest_target_runtime_hints(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "executor_plan": {
                    "service_port": 8000,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (metadata_dir / "generator_manifest.json").write_text(
        json.dumps(
            {
                "manifest": {
                    "metadata": {
                        "target_db": "mysql",
                        "target_sidecars": ["mysql"],
                        "target_topology": "service_plus_sidecar",
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    surface = docker_local._resolve_execution_surface(metadata_dir, tmp_path, {})

    assert surface["db"] == "mysql"
    assert surface["db_source"] == "generator_manifest.metadata.target_db"
    assert surface["topology"] == "service_plus_sidecar"
    assert surface["topology_source"] == "generator_manifest.metadata.target_topology"
    assert surface["target_sidecars_hint"] == ["mysql"]
    assert surface["target_runtime_hint_source"] == "generator_manifest.metadata"
    assert surface["requires_external_db"] is True
    assert surface["allow_network"] is True
    assert surface["network_mode"] == "bridge"


def test_resolve_execution_surface_can_synthesize_mysql_sidecar_from_target_hints(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "executor_plan": {
                    "service_port": 8000,
                    "service_env": {
                        "DB_HOST": "db-internal",
                        "DB_NAME": "runtime_db",
                        "DB_USER": "runtime_user",
                        "DB_PASSWORD": "runtime_pw",
                    },
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (metadata_dir / "generator_manifest.json").write_text(
        json.dumps(
            {
                "manifest": {
                    "metadata": {
                        "target_db": "mysql",
                        "target_sidecars": ["mysql"],
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    surface = docker_local._resolve_execution_surface(metadata_dir, tmp_path, {})

    assert surface["sidecars_source"] == "generator_manifest.metadata.target_sidecars"
    assert surface["sidecars"] == [
        {
            "name": "mysql-main",
            "type": "mysql",
            "image": "mysql:8.0",
            "aliases": ["db-internal"],
            "env": {
                "MYSQL_ROOT_PASSWORD": "sqli_root_pw",
                "MYSQL_DATABASE": "runtime_db",
                "MYSQL_USER": "runtime_user",
                "MYSQL_PASSWORD": "runtime_pw",
            },
            "ready_probe": {"type": "mysql", "retries": 10},
        }
    ]
    assert surface["service_env"] == {
        "DB_HOST": "db-internal",
        "DB_NAME": "runtime_db",
        "DB_USER": "runtime_user",
        "DB_PASSWORD": "runtime_pw",
        "DB_PORT": "3306",
        "APP_PORT": "8000",
    }
    assert surface["service_env_source"] == "executor_plan.service_env+runtime_hint_sidecar_defaults"


def test_resolve_execution_surface_can_synthesize_postgres_sidecar_from_target_hints(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "executor_plan": {
                    "service_port": 8000,
                    "service_env": {
                        "DB_HOST": "db-internal",
                        "DB_NAME": "appdb",
                        "DB_USER": "appuser",
                        "DB_PASSWORD": "apppw",
                    },
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (metadata_dir / "generator_manifest.json").write_text(
        json.dumps(
            {
                "manifest": {
                    "metadata": {
                        "target_db": "postgres",
                        "target_sidecars": ["postgres"],
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    surface = docker_local._resolve_execution_surface(metadata_dir, tmp_path, {})

    assert surface["sidecars_source"] == "generator_manifest.metadata.target_sidecars"
    assert surface["sidecars"] == [
        {
            "name": "postgres-main",
            "type": "postgres",
            "image": "postgres:16",
            "aliases": ["db-internal"],
            "env": {
                "POSTGRES_DB": "appdb",
                "POSTGRES_USER": "appuser",
                "POSTGRES_PASSWORD": "apppw",
            },
            "ready_probe": {"type": "postgres", "retries": 10},
        }
    ]
    assert surface["service_env"] == {
        "DB_HOST": "db-internal",
        "DB_NAME": "appdb",
        "DB_USER": "appuser",
        "DB_PASSWORD": "apppw",
        "DB_PORT": "5432",
        "APP_PORT": "8000",
    }
    assert surface["service_env_source"] == "executor_plan.service_env+runtime_hint_sidecar_defaults"


def test_validate_seed_files_rejects_missing_declared_seed_files(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "schema.sql").write_text("create table demo(id integer);\n", encoding="utf-8")

    with pytest.raises(docker_local.ExecutorError, match="Declared seed files missing from workspace"):
        docker_local._validate_seed_files(
            workspace,
            {
                "seed_files": ["schema.sql", "seed_data.sql"],
                "seed_files_source": "executor_plan.seed_files",
            },
        )


def test_validate_seed_files_rejects_absolute_declared_seed_files(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(docker_local.ExecutorError, match="Invalid seed file path"):
        docker_local._validate_seed_files(
            workspace,
            {
                "seed_files": ["/tmp/schema.sql"],
                "seed_files_source": "executor_plan.seed_files",
            },
        )


def test_validate_seed_files_rejects_parent_traversal_declared_seed_files(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(docker_local.ExecutorError, match="Invalid seed file path"):
        docker_local._validate_seed_files(
            workspace,
            {
                "seed_files": ["../schema.sql"],
                "seed_files_source": "executor_plan.seed_files",
            },
        )


def test_validate_seed_strategy_contract_rejects_sqlite_strategy_for_non_sqlite_runtime() -> None:
    with pytest.raises(
        docker_local.ExecutorError,
        match="sqlite_service_init is incompatible with non-sqlite runtime",
    ):
        docker_local._validate_seed_strategy_contract(
            {
                "db": "mysql",
                "seed_strategy": "sqlite_service_init",
                "seed_strategy_source": "executor_plan.seed_strategy",
            }
        )


def test_validate_seed_strategy_contract_rejects_sidecar_strategy_without_external_db() -> None:
    with pytest.raises(
        docker_local.ExecutorError,
        match="sidecar_sql_apply requires external-db or sidecar runtime",
    ):
        docker_local._validate_seed_strategy_contract(
            {
                "db": "mysql",
                "seed_strategy": "sidecar_sql_apply",
                "seed_strategy_source": "executor_plan.seed_strategy",
                "seed_files": ["schema.sql"],
                "sidecars": [],
                "requires_external_db": False,
            }
        )


def test_validate_seed_strategy_contract_rejects_sidecar_strategy_without_sql_seed_files() -> None:
    with pytest.raises(
        docker_local.ExecutorError,
        match="sidecar_sql_apply requires at least one .sql seed file",
    ):
        docker_local._validate_seed_strategy_contract(
            {
                "db": "postgres",
                "seed_strategy": "sidecar_sql_apply",
                "seed_strategy_source": "executor_plan.seed_strategy",
                "seed_files": ["notes.txt"],
                "sidecars": [{"name": "postgres-main", "image": "postgres:16"}],
                "requires_external_db": True,
            }
        )


def test_validate_seed_strategy_contract_accepts_valid_sidecar_sql_apply() -> None:
    docker_local._validate_seed_strategy_contract(
        {
            "db": "postgres",
            "seed_strategy": "sidecar_sql_apply",
            "seed_strategy_source": "executor_plan.seed_strategy",
            "seed_files": ["schema.sql", "notes.txt"],
            "sidecars": [{"name": "postgres-main", "image": "postgres:16"}],
            "requires_external_db": True,
        }
    )


def test_validate_seed_strategy_contract_rejects_sidecar_sql_apply_without_sql_capable_sidecar() -> None:
    with pytest.raises(
        docker_local.ExecutorError,
        match="requires a SQL-capable sidecar target",
    ):
        docker_local._validate_seed_strategy_contract(
            {
                "seed_strategy": "sidecar_sql_apply",
                "seed_strategy_source": "executor_plan.seed_strategy",
                "seed_files": ["schema.sql"],
                "sidecars": [{"name": "redis-main", "image": "redis:7"}],
                "requires_external_db": True,
            }
        )


def test_validate_seed_strategy_contract_rejects_sidecar_sql_apply_with_only_db_hint() -> None:
    with pytest.raises(
        docker_local.ExecutorError,
        match="requires a SQL-capable sidecar target",
    ):
        docker_local._validate_seed_strategy_contract(
            {
                "db": "mysql",
                "seed_strategy": "sidecar_sql_apply",
                "seed_strategy_source": "executor_plan.seed_strategy",
                "seed_files": ["schema.sql"],
                "sidecars": [],
                "requires_external_db": True,
            }
        )


def test_validate_seed_strategy_contract_rejects_sidecar_sql_apply_with_multiple_sql_families() -> None:
    with pytest.raises(
        docker_local.ExecutorError,
        match="ambiguous across multiple SQL sidecar runtimes",
    ):
        docker_local._validate_seed_strategy_contract(
            {
                "seed_strategy": "sidecar_sql_apply",
                "seed_strategy_source": "executor_plan.seed_strategy",
                "seed_files": ["schema.sql"],
                "sidecars": [
                    {"name": "mysql-main", "image": "mysql:8.0"},
                    {"name": "postgres-main", "image": "postgres:16"},
                ],
                "requires_external_db": True,
            }
        )


def test_validate_env_contract_shape_rejects_unsupported_scopes() -> None:
    with pytest.raises(
        docker_local.ExecutorError,
        match="unsupported scopes",
    ):
        docker_local._validate_env_contract_shape(
            {
                "env_contract": [
                    {"scope": "service", "name": "APP_PORT", "value": "8000"},
                    {"scope": "cache", "name": "CACHE_URL", "value": "redis://cache"},
                    {"scope": "runtime", "name": "DEBUG", "value": "1"},
                ],
                "env_contract_source": "executor_plan.env_contract",
            }
        )


def test_validate_env_contract_shape_accepts_service_and_sidecar_scopes() -> None:
    docker_local._validate_env_contract_shape(
        {
            "env_contract": [
                {"scope": "service", "name": "APP_PORT", "value": "8000"},
                {"scope": "sidecar:mysql-main", "name": "MYSQL_DATABASE", "value": "appdb"},
            ],
            "env_contract_source": "executor_plan.env_contract",
        }
    )


def test_validate_seed_init_contract_rejects_missing_sqlite_init_signal(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "schema.sql").write_text("create table demo(id integer);\n", encoding="utf-8")
    (workspace / "app.py").write_text(
        "from flask import Flask\napp = Flask(__name__)\napp.run()\n",
        encoding="utf-8",
    )

    with pytest.raises(docker_local.ExecutorError, match="Declared seed files require sqlite runtime init signals"):
        docker_local._validate_seed_init_contract(
            workspace,
            {
                "db": "sqlite",
                "seed_strategy": "sqlite_service_init",
                "service_entry": "app.py",
                "seed_files": ["schema.sql"],
            },
        )


def test_validate_seed_init_contract_accepts_executescript_signal(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "schema.sql").write_text("create table demo(id integer);\n", encoding="utf-8")
    (workspace / "app.py").write_text(
        "import sqlite3\n"
        "def init_db():\n"
        "    conn = sqlite3.connect('/tmp/app.db')\n"
        "    conn.executescript(open('schema.sql').read())\n",
        encoding="utf-8",
    )

    docker_local._validate_seed_init_contract(
        workspace,
        {
            "db": "sqlite",
            "seed_strategy": "sqlite_service_init",
            "service_entry": "app.py",
            "seed_files": ["schema.sql"],
        },
    )


def test_validate_service_env_contract_rejects_missing_env_values() -> None:
    with pytest.raises(docker_local.ExecutorError, match="Declared env contract missing service env values"):
        docker_local._validate_service_env_contract(
            {
                "service_env": {"APP_PORT": "8000"},
                "env_contract": [
                    {"scope": "service", "name": "APP_PORT", "value": "8000"},
                    {"scope": "service", "name": "DB_HOST", "value": "db-internal"},
                ],
                "env_contract_source": "executor_plan.env_contract",
            }
        )


def test_validate_service_env_contract_rejects_mismatched_env_values() -> None:
    with pytest.raises(docker_local.ExecutorError, match="Declared env contract value mismatch"):
        docker_local._validate_service_env_contract(
            {
                "service_env": {"APP_PORT": "9000", "DB_HOST": "db-runtime"},
                "env_contract": [
                    {"scope": "service", "name": "APP_PORT", "value": "8000"},
                    {"scope": "service", "name": "DB_HOST", "value": "db-internal"},
                ],
                "env_contract_source": "executor_plan.env_contract",
            }
        )


def test_validate_service_env_contract_rejects_conflicting_declared_values() -> None:
    with pytest.raises(docker_local.ExecutorError, match="conflicting service values"):
        docker_local._validate_service_env_contract(
            {
                "service_env": {"APP_PORT": "8000", "DB_HOST": "db-internal"},
                "env_contract": [
                    {"scope": "service", "name": "DB_HOST", "value": "db-internal"},
                    {"scope": "service", "name": "DB_HOST", "value": "db-shadow"},
                ],
                "env_contract_source": "executor_plan.env_contract",
            }
        )


def test_validate_sidecar_env_contract_rejects_missing_sidecar_target() -> None:
    with pytest.raises(docker_local.ExecutorError, match="Declared env contract targets missing sidecar entries"):
        docker_local._validate_sidecar_env_contract(
            {
                "sidecars": [{"name": "mysql-main", "env": {"MYSQL_DATABASE": "appdb"}}],
                "env_contract": [
                    {"scope": "sidecar:postgres-main", "name": "POSTGRES_DB", "value": "appdb"},
                ],
                "env_contract_source": "executor_plan.env_contract",
            }
        )


def test_validate_sidecar_env_contract_rejects_missing_sidecar_env_values() -> None:
    with pytest.raises(docker_local.ExecutorError, match="Declared env contract missing sidecar env values"):
        docker_local._validate_sidecar_env_contract(
            {
                "sidecars": [{"name": "mysql-main", "env": {"MYSQL_DATABASE": "appdb"}}],
                "env_contract": [
                    {"scope": "sidecar:mysql-main", "name": "MYSQL_USER", "value": "appuser"},
                ],
                "env_contract_source": "executor_plan.env_contract",
            }
        )


def test_validate_sidecar_env_contract_rejects_mismatched_sidecar_env_values() -> None:
    with pytest.raises(docker_local.ExecutorError, match="Declared env contract sidecar value mismatch"):
        docker_local._validate_sidecar_env_contract(
            {
                "sidecars": [{"name": "mysql-main", "env": {"MYSQL_DATABASE": "runtime_db"}}],
                "env_contract": [
                    {"scope": "sidecar:mysql-main", "name": "MYSQL_DATABASE", "value": "contract_db"},
                ],
                "env_contract_source": "executor_plan.env_contract",
            }
        )


def test_validate_sidecar_env_contract_rejects_conflicting_declared_values() -> None:
    with pytest.raises(docker_local.ExecutorError, match="conflicting sidecar values"):
        docker_local._validate_sidecar_env_contract(
            {
                "sidecars": [{"name": "mysql-main", "env": {"MYSQL_DATABASE": "appdb"}}],
                "env_contract": [
                    {"scope": "sidecar:mysql-main", "name": "MYSQL_DATABASE", "value": "appdb"},
                    {"scope": "sidecar:mysql-main", "name": "MYSQL_DATABASE", "value": "shadowdb"},
                ],
                "env_contract_source": "runtime_graph.env_contract",
            }
        )


def test_validate_sidecar_env_contract_accepts_matching_sidecar_env_values() -> None:
    docker_local._validate_sidecar_env_contract(
        {
            "sidecars": [{"name": "mysql-main", "env": {"MYSQL_DATABASE": "appdb", "MYSQL_USER": "appuser"}}],
            "env_contract": [
                {"scope": "sidecar:mysql-main", "name": "MYSQL_DATABASE", "value": "appdb"},
                {"scope": "sidecar:mysql-main", "name": "MYSQL_USER", "value": "appuser"},
            ],
            "env_contract_source": "executor_plan.env_contract",
        }
    )


def test_validate_sidecar_probe_contract_accepts_matching_mysql_probe() -> None:
    docker_local._validate_sidecar_probe_contract(
        {
            "sidecars": [
                {
                    "name": "mysql-main",
                    "type": "mysql",
                    "ready_probe": {"type": "mysql", "retries": 3},
                }
            ],
            "sidecars_source": "executor_plan.sidecars",
        }
    )


def test_validate_sidecar_probe_contract_accepts_missing_probe_type() -> None:
    docker_local._validate_sidecar_probe_contract(
        {
            "sidecars": [
                {
                    "name": "mysql-main",
                    "type": "mysql",
                    "ready_probe": {"retries": 3},
                }
            ],
            "sidecars_source": "executor_plan.sidecars",
        }
    )


def test_validate_sidecar_probe_contract_rejects_mysql_probe_type_mismatch() -> None:
    with pytest.raises(docker_local.ExecutorError, match="ready_probe is inconsistent with resolved sidecar runtime"):
        docker_local._validate_sidecar_probe_contract(
            {
                "sidecars": [
                    {
                        "name": "mysql-main",
                        "type": "mysql",
                        "ready_probe": {"type": "postgres", "retries": 3},
                    }
                ],
                "sidecars_source": "executor_plan.sidecars",
            }
        )


def test_validate_sidecar_probe_contract_rejects_postgres_probe_type_mismatch() -> None:
    with pytest.raises(docker_local.ExecutorError, match="ready_probe is inconsistent with resolved sidecar runtime"):
        docker_local._validate_sidecar_probe_contract(
            {
                "sidecars": [
                    {
                        "name": "postgres-main",
                        "type": "postgres",
                        "ready_probe": {"type": "mysql", "retries": 3},
                    }
                ],
                "sidecars_source": "runtime_graph.nodes.sidecar",
            }
        )


def test_validate_volume_contract_rejects_missing_sidecar_target() -> None:
    with pytest.raises(docker_local.ExecutorError, match="Declared volume contract targets missing sidecar entries"):
        docker_local._validate_volume_contract(
            {
                "sidecars": [{"name": "mysql-main", "image": "mysql:8.0"}],
                "volume_contract": [
                    {
                        "scope": "sidecar:postgres-main",
                        "source": "workspace",
                        "target": "/seed-input",
                        "mode": "ro",
                    }
                ],
                "volume_contract_source": "executor_plan.volume_contract",
            }
        )


def test_validate_volume_contract_rejects_unsupported_scopes() -> None:
    with pytest.raises(docker_local.ExecutorError, match="unsupported scopes"):
        docker_local._validate_volume_contract(
            {
                "sidecars": [{"name": "mysql-main", "image": "mysql:8.0"}],
                "volume_contract": [
                    {
                        "scope": "service",
                        "source": "workspace",
                        "target": "/seed-input",
                        "mode": "ro",
                    }
                ],
                "volume_contract_source": "executor_plan.volume_contract",
            }
        )


def test_validate_volume_contract_rejects_unsupported_sources() -> None:
    with pytest.raises(docker_local.ExecutorError, match="unsupported mount sources"):
        docker_local._validate_volume_contract(
            {
                "sidecars": [{"name": "mysql-main", "image": "mysql:8.0"}],
                "volume_contract": [
                    {
                        "scope": "sidecar:mysql-main",
                        "source": "hostfs",
                        "target": "/seed-input",
                        "mode": "ro",
                    }
                ],
                "volume_contract_source": "executor_plan.volume_contract",
            }
        )


def test_validate_volume_contract_rejects_missing_seed_mount_for_sidecar_strategy() -> None:
    with pytest.raises(docker_local.ExecutorError, match="Declared volume contract missing workspace seed mount entries"):
        docker_local._validate_volume_contract(
            {
                "seed_strategy": "sidecar_sql_apply",
                "seed_files": ["schema.sql"],
                "sidecars": [{"name": "mysql-main", "type": "mysql", "image": "mysql:8.0"}],
                "volume_contract": [
                    {
                        "scope": "sidecar:mysql-main",
                        "source": "runtime",
                        "target": "/other-input",
                        "mode": "ro",
                    }
                ],
                "volume_contract_source": "executor_plan.volume_contract",
            }
        )


def test_validate_volume_contract_accepts_seed_input_mount_for_sidecar_strategy() -> None:
    docker_local._validate_volume_contract(
        {
            "seed_strategy": "sidecar_sql_apply",
            "seed_files": ["schema.sql"],
            "sidecars": [{"name": "mysql-main", "type": "mysql", "image": "mysql:8.0"}],
            "volume_contract": [
                {
                    "scope": "sidecar:mysql-main",
                    "source": "workspace",
                    "target": "/seed-input",
                    "mode": "ro",
                }
            ],
            "volume_contract_source": "executor_plan.volume_contract",
        }
    )


def test_validate_volume_contract_accepts_custom_seed_mount_for_sidecar_strategy() -> None:
    docker_local._validate_volume_contract(
        {
            "seed_strategy": "sidecar_sql_apply",
            "seed_files": ["schema.sql"],
            "sidecars": [{"name": "mysql-main", "type": "mysql", "image": "mysql:8.0"}],
            "volume_contract": [
                {
                    "scope": "sidecar:mysql-main",
                    "source": "workspace",
                    "target": "/imports",
                    "mode": "ro",
                }
            ],
            "volume_contract_source": "executor_plan.volume_contract",
        }
    )


def test_validate_volume_contract_rejects_conflicting_mount_definitions_for_same_target() -> None:
    with pytest.raises(docker_local.ExecutorError, match="conflicting sidecar mount definitions"):
        docker_local._validate_volume_contract(
            {
                "sidecars": [{"name": "mysql-main", "type": "mysql", "image": "mysql:8.0"}],
                "volume_contract": [
                    {
                        "scope": "sidecar:mysql-main",
                        "source": "workspace",
                        "target": "/seed-input",
                        "mode": "ro",
                    },
                    {
                        "scope": "sidecar:mysql-main",
                        "source": "runtime",
                        "target": "/seed-input",
                        "mode": "rw",
                    },
                ],
                "volume_contract_source": "executor_plan.volume_contract",
            }
        )


def test_validate_volume_contract_rejects_ambiguous_workspace_seed_mount_targets() -> None:
    with pytest.raises(docker_local.ExecutorError, match="ambiguous workspace seed mount targets"):
        docker_local._validate_volume_contract(
            {
                "seed_strategy": "sidecar_sql_apply",
                "seed_files": ["schema.sql"],
                "sidecars": [{"name": "mysql-main", "type": "mysql", "image": "mysql:8.0"}],
                "volume_contract": [
                    {
                        "scope": "sidecar:mysql-main",
                        "source": "workspace",
                        "target": "/seed-input",
                        "mode": "ro",
                    },
                    {
                        "scope": "sidecar:mysql-main",
                        "source": "workspace",
                        "target": "/imports",
                        "mode": "ro",
                    },
                ],
                "volume_contract_source": "executor_plan.volume_contract",
            }
        )


def test_validate_network_contract_rejects_missing_sidecar_target() -> None:
    with pytest.raises(docker_local.ExecutorError, match="Declared network contract targets missing sidecar entries"):
        docker_local._validate_network_contract(
            {
                "allow_network": True,
                "service_env": {"DB_HOST": "db-internal"},
                "sidecars": [{"name": "mysql-main", "aliases": ["db-internal"]}],
                "network_contract": [
                    {"scope": "service", "name": "DB_HOST", "alias": "db-internal"},
                    {"scope": "sidecar:postgres-main", "alias": "pg-internal"},
                ],
                "network_contract_source": "executor_plan.network_contract",
            }
        )


def test_validate_network_contract_rejects_unsupported_scopes() -> None:
    with pytest.raises(docker_local.ExecutorError, match="unsupported scopes"):
        docker_local._validate_network_contract(
            {
                "allow_network": True,
                "service_env": {"DB_HOST": "db-internal"},
                "sidecars": [{"name": "mysql-main", "aliases": ["db-internal"]}],
                "network_contract": [
                    {"scope": "service", "name": "DB_HOST", "alias": "db-internal"},
                    {"scope": "cache", "name": "CACHE_HOST", "alias": "cache-internal"},
                ],
                "network_contract_source": "executor_plan.network_contract",
            }
        )


def test_validate_network_contract_rejects_service_alias_mismatch() -> None:
    with pytest.raises(docker_local.ExecutorError, match="Declared network contract service alias mismatch"):
        docker_local._validate_network_contract(
            {
                "allow_network": True,
                "service_env": {"DB_HOST": "db-runtime"},
                "sidecars": [{"name": "mysql-main", "aliases": ["db-internal"]}],
                "network_contract": [
                    {"scope": "service", "name": "DB_HOST", "alias": "db-internal"},
                    {"scope": "sidecar:mysql-main", "alias": "db-internal"},
                ],
                "network_contract_source": "executor_plan.network_contract",
            }
        )


def test_validate_network_contract_rejects_conflicting_service_alias_values() -> None:
    with pytest.raises(docker_local.ExecutorError, match="conflicting service aliases"):
        docker_local._validate_network_contract(
            {
                "allow_network": True,
                "service_env": {"DB_HOST": "db-internal"},
                "sidecars": [{"name": "mysql-main", "aliases": ["db-internal", "db-shadow"]}],
                "network_contract": [
                    {"scope": "service", "name": "DB_HOST", "alias": "db-internal"},
                    {"scope": "service", "name": "DB_HOST", "alias": "db-shadow"},
                ],
                "network_contract_source": "executor_plan.network_contract",
            }
        )


def test_validate_network_contract_rejects_service_alias_without_any_sidecar_target() -> None:
    with pytest.raises(docker_local.ExecutorError, match="unresolved service aliases without sidecar targets"):
        docker_local._validate_network_contract(
            {
                "allow_network": True,
                "service_env": {},
                "sidecars": [],
                "network_contract": [
                    {"scope": "service", "name": "DB_HOST", "alias": "db-internal"},
                ],
                "network_contract_source": "executor_plan.network_contract",
            }
        )


def test_validate_network_contract_rejects_disabled_network_for_declared_alias_contract() -> None:
    with pytest.raises(docker_local.ExecutorError, match="Declared network contract requires enabled executor network"):
        docker_local._validate_network_contract(
            {
                "allow_network": False,
                "service_env": {"DB_HOST": "db-internal"},
                "sidecars": [{"name": "mysql-main", "aliases": ["db-internal"]}],
                "network_contract": [
                    {"scope": "service", "name": "DB_HOST", "alias": "db-internal"},
                    {"scope": "sidecar:mysql-main", "alias": "db-internal"},
                ],
                "network_contract_source": "executor_plan.network_contract",
            }
        )


def test_validate_network_contract_accepts_matching_sidecar_alias_contract() -> None:
    docker_local._validate_network_contract(
        {
            "allow_network": True,
            "service_env": {"DB_HOST": "db-internal"},
            "sidecars": [{"name": "mysql-main", "aliases": ["db-internal"]}],
            "network_contract": [
                {"scope": "service", "name": "DB_HOST", "alias": "db-internal"},
                {"scope": "sidecar:mysql-main", "alias": "db-internal"},
            ],
            "network_contract_source": "executor_plan.network_contract",
        }
    )


def test_validate_sidecar_dependency_contract_rejects_unknown_sidecar_in_start_order() -> None:
    with pytest.raises(docker_local.ExecutorError, match="references unknown sidecars"):
        docker_local._validate_sidecar_dependency_contract(
            {
                "sidecars": [{"name": "mysql-main", "image": "mysql:8.0"}],
                "sidecar_start_order": ["redis-main"],
                "sidecar_start_order_source": "executor_plan.sidecar_start_order",
            },
            {},
        )


def test_validate_sidecar_dependency_contract_rejects_unknown_runtime_graph_dependency() -> None:
    with pytest.raises(docker_local.ExecutorError, match="runtime_graph startup_after references malformed or unknown sidecars"):
        docker_local._validate_sidecar_dependency_contract(
            {
                "sidecars": [
                    {"name": "redis-main", "image": "redis:7"},
                ],
                "sidecar_start_order": ["redis-main"],
                "sidecar_start_order_source": "runtime_graph.edges.startup_after",
            },
            {
                "edges": [
                    {
                        "from": "service",
                        "to": "sidecar:redis-main",
                        "kind": "runtime_dependency",
                        "startup_after": "sidecar:mysql-main",
                    }
                ]
            },
        )


def test_validate_sidecar_dependency_contract_rejects_runtime_graph_cycle() -> None:
    with pytest.raises(docker_local.ExecutorError, match="cyclic sidecar dependency"):
        docker_local._validate_sidecar_dependency_contract(
            {
                "sidecars": [
                    {"name": "mysql-main", "image": "mysql:8.0"},
                    {"name": "redis-main", "image": "redis:7"},
                ],
                "sidecar_start_order": ["mysql-main", "redis-main"],
                "sidecar_start_order_source": "runtime_graph.edges.startup_after",
            },
            {
                "edges": [
                    {
                        "from": "service",
                        "to": "sidecar:mysql-main",
                        "kind": "runtime_dependency",
                        "startup_after": "sidecar:redis-main",
                    },
                    {
                        "from": "service",
                        "to": "sidecar:redis-main",
                        "kind": "runtime_dependency",
                        "startup_after": "sidecar:mysql-main",
                    },
                ]
            },
        )


def test_validate_sidecar_dependency_contract_accepts_runtime_graph_dependency_chain() -> None:
    docker_local._validate_sidecar_dependency_contract(
        {
            "sidecars": [
                {"name": "mysql-main", "image": "mysql:8.0"},
                {"name": "redis-main", "image": "redis:7"},
            ],
            "sidecar_start_order": ["mysql-main", "redis-main"],
            "sidecar_start_order_source": "runtime_graph.edges.startup_after",
        },
        {
            "edges": [
                {
                    "from": "service",
                    "to": "sidecar:mysql-main",
                    "kind": "runtime_dependency",
                },
                {
                    "from": "service",
                    "to": "sidecar:redis-main",
                    "kind": "runtime_dependency",
                    "startup_after": "sidecar:mysql-main",
                },
            ]
        },
    )


def test_should_mount_seed_input_prefers_declared_volume_contract(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    assert docker_local._should_mount_seed_input(
        {"name": "custom-db", "image": "vendor/custom-db:1.0"},
        {
            "volume_contract": [
                {
                    "scope": "sidecar:custom-db",
                    "source": "workspace",
                    "target": "/seed-input",
                    "mode": "ro",
                }
            ]
        },
        workspace,
    ) is True


def test_sidecar_seed_mount_target_prefers_declared_custom_volume_contract(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    assert docker_local._sidecar_seed_mount_target(
        {"name": "custom-db", "image": "vendor/custom-db:1.0"},
        {
            "volume_contract": [
                {
                    "scope": "sidecar:custom-db",
                    "source": "workspace",
                    "target": "/imports",
                    "mode": "ro",
                }
            ],
            "seed_strategy": "sidecar_sql_apply",
            "seed_files": ["schema.sql"],
        },
        workspace,
    ) == "/imports"


def test_start_sidecars_mentions_target_sidecar_hint_when_plan_missing(tmp_path: Path) -> None:
    bundle = VulnBundle(vuln_id="CWE-89", slug="cwe-89", workspace_subdir="app")

    with pytest.raises(docker_local.ExecutorError, match="target sidecars hint=mysql"):
        docker_local._start_sidecars(
            "sid-demo",
            bundle,
            execution_surface={"sidecars": [], "target_sidecars_hint": ["mysql"]},
            workspace=None,
            run_dir=tmp_path,
            network_alias=docker_local.NetworkHandle("bridge"),
        )


def test_resolve_base_url_prefers_executor_plan_before_port_default(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        '{"executor_plan":{"base_url":"http://127.0.0.1:9000"},"base_url":"http://127.0.0.1:8000"}',
        encoding="utf-8",
    )

    base_url = docker_local._resolve_base_url(metadata_dir, {}, 5000)

    assert base_url == "http://127.0.0.1:9000"


def test_resolve_base_url_keeps_executor_policy_override(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        '{"executor_plan":{"base_url":"http://127.0.0.1:9000"}}',
        encoding="utf-8",
    )

    base_url = docker_local._resolve_base_url(metadata_dir, {"base_url": "http://service:8080"}, 5000)

    assert base_url == "http://service:8080"


def test_resolve_service_env_prefers_executor_plan_service_env(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        '{"executor_plan":{"service_env":{"DB_HOST":"plan-db","APP_PORT":"9000"}},"service_env":{"DB_HOST":"contract-db","APP_PORT":"5000"}}',
        encoding="utf-8",
    )

    env = docker_local._resolve_service_env(metadata_dir)

    assert env == {"DB_HOST": "plan-db", "APP_PORT": "9000"}


def test_bundle_requires_external_db_prefers_executor_plan_topology(tmp_path: Path) -> None:
    sid = "sid-executor-plan-db"
    metadata_dir = tmp_path / "metadata" / sid
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "resolved_contract.json").write_text(
        '{"executor_plan":{"topology":"service_plus_sidecar","requires_external_db":true}}',
        encoding="utf-8",
    )
    plan = {
        "sid": sid,
        "paths": {"metadata": str(tmp_path / "metadata" / sid)},
        "requirement": {"vuln_id": "CWE-89", "runtime": {"db": "sqlite"}},
        "run_matrix": {"vuln_bundles": [{"vuln_id": "CWE-89", "slug": "cwe-89", "workspace_subdir": "app"}]},
    }
    bundle = VulnBundle(vuln_id="CWE-89", slug="cwe-89", workspace_subdir="app")

    assert docker_local._bundle_requires_external_db(plan, bundle) is True


def test_bundle_requires_external_db_accepts_executor_plan_db_hint(tmp_path: Path) -> None:
    sid = "sid-executor-plan-db-hint"
    metadata_dir = tmp_path / "metadata" / sid
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "executor_plan": {
                    "db": "mysql",
                    "db_source": "primitive_family_inference",
                    "topology": "single_service",
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    plan = {
        "sid": sid,
        "paths": {"metadata": str(tmp_path / "metadata" / sid)},
        "requirement": {"vuln_id": "CWE-89", "runtime": {"db": "sqlite"}},
        "run_matrix": {"vuln_bundles": [{"vuln_id": "CWE-89", "slug": "cwe-89", "workspace_subdir": "app"}]},
    }
    bundle = VulnBundle(vuln_id="CWE-89", slug="cwe-89", workspace_subdir="app")

    assert docker_local._bundle_requires_external_db(plan, bundle) is True


def test_bundle_requires_external_db_accepts_runtime_dependency_hint(tmp_path: Path) -> None:
    sid = "sid-executor-plan-dependency-hint"
    metadata_dir = tmp_path / "metadata" / sid
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "executor_plan": {
                    "runtime_dependency_hypotheses": [
                        {"kind": "db", "value": "postgres", "source": "primitive_family_inference", "confidence": "low"}
                    ]
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    plan = {
        "sid": sid,
        "paths": {"metadata": str(tmp_path / "metadata" / sid)},
        "requirement": {"vuln_id": "CWE-89", "runtime": {"db": "sqlite"}},
        "run_matrix": {"vuln_bundles": [{"vuln_id": "CWE-89", "slug": "cwe-89", "workspace_subdir": "app"}]},
    }
    bundle = VulnBundle(vuln_id="CWE-89", slug="cwe-89", workspace_subdir="app")

    assert docker_local._bundle_requires_external_db(plan, bundle) is True


def test_effective_executor_policy_uses_executor_plan_when_policy_missing(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "executor_plan": {
                    "network_enabled": True,
                    "network_mode": "bridge",
                    "sidecars": [{"name": "mysql-main", "image": "mysql:8.0", "aliases": ["db-internal"]}],
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    policy = docker_local._effective_executor_policy(metadata_dir, {})

    assert policy["allow_network"] is True
    assert policy["network_mode"] == "bridge"
    assert policy["sidecars"] == [{"name": "mysql-main", "image": "mysql:8.0", "aliases": ["db-internal"]}]


def test_effective_executor_policy_keeps_explicit_policy_override(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "executor_plan": {
                    "network_enabled": True,
                    "network_mode": "bridge",
                    "sidecars": [{"name": "mysql-main", "image": "mysql:8.0"}],
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    policy = docker_local._effective_executor_policy(
        metadata_dir,
        {"allow_network": False, "network_mode": "none", "sidecars": []},
    )

    assert policy["allow_network"] is False
    assert policy["network_mode"] == "none"
    assert policy["sidecars"] == [{"name": "mysql-main", "image": "mysql:8.0"}]


def test_effective_executor_policy_prefers_executor_plan_sidecars_over_global_defaults(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "executor_plan": {
                    "network_enabled": True,
                    "network_mode": "bridge",
                    "sidecars": [{"name": "mysql-main", "image": "mysql:8.0", "aliases": ["db-internal"]}],
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    policy = docker_local._effective_executor_policy(
        metadata_dir,
        {"allow_network": True, "network_mode": "bridge", "sidecars": [{"name": "redis", "image": "redis:7"}]},
    )

    assert policy["sidecars"] == [{"name": "mysql-main", "image": "mysql:8.0", "aliases": ["db-internal"]}]


def test_resolve_execution_surface_prefers_executor_plan_sidecars_and_healthchecks(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "executor_plan": {
                    "service_port": 9000,
                    "base_url": "http://127.0.0.1:9000",
                    "db": "sqlite",
                    "db_source": "primitive_family_inference",
                    "topology_source": "primitive_family_inference",
                    "network_enabled": True,
                    "network_mode": "bridge",
                    "healthchecks": [{"path": "/ready", "port": 9000, "transport": "http"}],
                    "sidecars": [
                        {
                            "name": "mysql-main",
                            "image": "mysql:8.0",
                            "aliases": ["db-internal"],
                            "env": {"MYSQL_ROOT_PASSWORD": "pw"},
                            "ready_probe": {"type": "mysql", "retries": 3},
                        }
                    ],
                },
                "runtime_recipe": {
                    "network_enabled": True,
                    "network_mode": "bridge",
                    "health_path": "/health",
                    "sidecars": [{"name": "fallback-db", "image": "mysql:5.7"}],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    surface = docker_local._resolve_execution_surface(
        metadata_dir,
        workspace=None,
        executor_policy={"sidecars": [{"name": "redis", "image": "redis:7"}]},
    )

    assert surface["service_port"] == 9000
    assert surface["base_url"] == "http://127.0.0.1:9000"
    assert surface["db"] == "sqlite"
    assert surface["db_source"] == "primitive_family_inference"
    assert surface["topology_source"] == "primitive_family_inference"
    assert surface["health_path"] == "/health"
    assert surface["healthchecks"] == [{"path": "/ready", "port": 9000, "transport": "http"}]
    assert surface["healthchecks_source"] == "executor_plan.healthchecks"
    assert surface["sidecars_source"] == "executor_plan.sidecars"
    assert surface["sidecars"] == [
        {
            "name": "mysql-main",
            "image": "mysql:8.0",
            "aliases": ["db-internal"],
            "env": {"MYSQL_ROOT_PASSWORD": "pw"},
            "ready_probe": {"type": "mysql", "retries": 3},
        }
    ]


def test_resolve_execution_surface_preserves_contract_synthesized_sidecar_and_env_sources(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "executor_plan": {
                    "service_port": 9000,
                    "network_enabled": True,
                    "network_enabled_source": "runtime_topology_requires_network",
                    "network_mode": "bridge",
                    "network_mode_source": "runtime_topology_requires_network",
                    "service_env": {
                        "DB_HOST": "db-internal",
                        "DB_NAME": "sqliapp",
                        "DB_USER": "sqli",
                        "DB_PASSWORD": "sqli_pw",
                        "DB_PORT": "3306",
                        "APP_PORT": "9000",
                    },
                    "service_env_source": "runtime_hint_sidecar_defaults",
                    "sidecars_source": "generator_manifest.metadata.target_sidecars",
                    "sidecar_start_order": ["mysql-main"],
                    "sidecar_start_order_source": "generator_manifest.metadata.target_sidecars",
                    "sidecars": [
                        {
                            "name": "mysql-main",
                            "type": "mysql",
                            "image": "mysql:8.0",
                            "aliases": ["db-internal"],
                            "env": {
                                "MYSQL_ROOT_PASSWORD": "sqli_root_pw",
                                "MYSQL_DATABASE": "sqliapp",
                                "MYSQL_USER": "sqli",
                                "MYSQL_PASSWORD": "sqli_pw",
                            },
                            "ready_probe": {"type": "mysql", "retries": 10},
                        }
                    ],
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    surface = docker_local._resolve_execution_surface(metadata_dir, tmp_path, {})

    assert surface["sidecars_source"] == "generator_manifest.metadata.target_sidecars"
    assert surface["sidecar_start_order"] == ["mysql-main"]
    assert surface["sidecar_start_order_source"] == "generator_manifest.metadata.target_sidecars"
    assert surface["service_env_source"] == "runtime_hint_sidecar_defaults"
    assert surface["allow_network"] is True
    assert surface["allow_network_source"] == "runtime_topology_requires_network"
    assert surface["network_mode"] == "bridge"
    assert surface["network_mode_source"] == "runtime_topology_requires_network"
    assert surface["service_env"] == {
        "DB_HOST": "db-internal",
        "DB_NAME": "sqliapp",
        "DB_USER": "sqli",
        "DB_PASSWORD": "sqli_pw",
        "DB_PORT": "3306",
        "APP_PORT": "9000",
    }


def test_resolve_execution_surface_can_use_runtime_graph_network_fields(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "executor_plan": {"service_port": 8000},
                "runtime_graph": {
                    "network": {"enabled": True, "mode": "bridge"},
                    "network_enabled_source": "runtime_graph.network.enabled",
                    "network_mode_source": "runtime_graph.network.mode",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    surface = docker_local._resolve_execution_surface(metadata_dir, tmp_path, {})

    assert surface["allow_network"] is True
    assert surface["allow_network_source"] == "runtime_graph.network.enabled"
    assert surface["network_mode"] == "bridge"
    assert surface["network_mode_source"] == "runtime_graph.network.mode"


def test_resolve_execution_surface_can_use_runtime_graph_service_fields(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "runtime_graph": {
                    "nodes": [
                        {
                            "id": "service",
                            "kind": "service",
                            "entry": "server.py",
                            "port": 8100,
                        }
                    ],
                    "exploit_path": {
                        "service_entry": "server.py",
                        "port": 8100,
                        "base_url": "http://127.0.0.1:8100",
                    },
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    surface = docker_local._resolve_execution_surface(metadata_dir, tmp_path, {})

    assert surface["service_port"] == 8100
    assert surface["service_port_source"] == "runtime_graph.exploit_path.port"
    assert surface["service_entry"] == "server.py"
    assert surface["service_entry_source"] == "runtime_graph.exploit_path.service_entry"
    assert surface["base_url"] == "http://127.0.0.1:8100"
    assert surface["base_url_source"] == "runtime_graph.exploit_path.base_url"


def test_resolve_execution_surface_can_use_executor_plan_healthcheck_port_for_service_port(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "executor_plan": {
                    "healthchecks": [
                        {"node": "service", "path": "/ready", "port": 8123, "transport": "http"}
                    ]
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    surface = docker_local._resolve_execution_surface(metadata_dir, tmp_path, {})

    assert surface["service_port"] == 8123
    assert surface["service_port_source"] == "executor_plan.healthchecks[service].port"
    assert surface["base_url"] == "http://127.0.0.1:8123"


def test_resolve_execution_surface_can_use_runtime_graph_healthcheck_port_for_service_port(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "runtime_graph": {
                    "healthchecks": [
                        {"node": "service", "path": "/ready", "port": 8124, "transport": "http"}
                    ]
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    surface = docker_local._resolve_execution_surface(metadata_dir, tmp_path, {})

    assert surface["service_port"] == 8124
    assert surface["service_port_source"] == "runtime_graph.healthchecks[service].port"
    assert surface["health_path"] == "/ready"
    assert surface["health_path_source"] == "runtime_graph.healthchecks[service]"
    assert surface["healthchecks_source"] == "runtime_graph.healthchecks"


def test_resolve_execution_surface_can_use_runtime_recipe_healthchecks_when_other_sources_missing(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "runtime_recipe": {
                    "healthchecks": [
                        {"node": "service", "path": "/runtime-ready", "port": 8125, "transport": "http"}
                    ]
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    surface = docker_local._resolve_execution_surface(metadata_dir, tmp_path, {})

    assert surface["service_port"] == 8125
    assert surface["service_port_source"] == "runtime_recipe.healthchecks[service].port"
    assert surface["health_path"] == "/runtime-ready"
    assert surface["health_path_source"] == "runtime_recipe.healthchecks[service]"
    assert surface["healthchecks"] == [{"node": "service", "path": "/runtime-ready", "port": 8125, "transport": "http"}]
    assert surface["healthchecks_source"] == "runtime_recipe.healthchecks"


def test_resolve_execution_surface_applies_network_contract_aliases_to_sidecars(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "executor_plan": {
                    "service_port": 9000,
                    "service_env": {"APP_PORT": "9000"},
                    "sidecars": [
                        {
                            "name": "mysql-main",
                            "type": "mysql",
                            "image": "mysql:8.0",
                            "env": {
                                "MYSQL_ROOT_PASSWORD": "sqli_root_pw",
                                "MYSQL_DATABASE": "sqliapp",
                                "MYSQL_USER": "sqli",
                                "MYSQL_PASSWORD": "sqli_pw",
                            },
                        }
                    ],
                    "network_contract": [
                        {"scope": "service", "name": "DB_HOST", "alias": "db-internal"},
                        {"scope": "sidecar:mysql-main", "alias": "db-internal"},
                    ],
                    "network_contract_source": "executor_plan.network_contract",
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    surface = docker_local._resolve_execution_surface(metadata_dir, tmp_path, {})

    assert surface["sidecars"][0]["aliases"] == ["db-internal"]
    assert surface["service_env"]["DB_HOST"] == "db-internal"
    assert surface["network_contract_source"] == "executor_plan.network_contract"


def test_resolve_execution_surface_can_apply_service_env_from_network_contract_aliases(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "executor_plan": {
                    "service_port": 9000,
                    "service_env": {"APP_PORT": "9000"},
                    "sidecars": [
                        {
                            "name": "redis-main",
                            "type": "redis",
                            "image": "redis:7",
                        }
                    ],
                    "network_contract": [
                        {"scope": "service", "name": "CACHE_HOST", "alias": "cache-internal"},
                        {"scope": "sidecar:redis-main", "alias": "cache-internal"},
                    ],
                    "network_contract_source": "executor_plan.network_contract",
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    surface = docker_local._resolve_execution_surface(metadata_dir, tmp_path, {})

    assert surface["service_env"]["CACHE_HOST"] == "cache-internal"
    assert surface["service_env_source"] == "executor_plan.service_env+network_contract_aliases"
    assert surface["sidecars"][0]["aliases"] == ["cache-internal"]


def test_resolve_execution_surface_keeps_allow_network_false_cap(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "executor_plan": {
                    "network_enabled": True,
                    "network_mode": "bridge",
                    "sidecars": [{"name": "mysql-main", "image": "mysql:8.0"}],
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    surface = docker_local._resolve_execution_surface(
        metadata_dir,
        workspace=None,
        executor_policy={"allow_network": False, "network_mode": "bridge"},
    )

    assert surface["allow_network"] is False
    assert surface["network_mode"] == "none"
    assert surface["allow_network_source"] == "policy.executor.allow_network"
    assert surface["network_mode_source"] == "allow_network=false"
    assert surface["sidecars"] == [{"name": "mysql-main", "image": "mysql:8.0"}]


def test_start_sidecars_uses_resolved_execution_surface_entries(tmp_path: Path, monkeypatch) -> None:
    bundle = VulnBundle(vuln_id="CWE-89", slug="cwe-89", workspace_subdir="app")
    observed: dict[str, object] = {}
    monkeypatch.setattr(docker_local, "DOCKER_BIN", "docker")

    def _fake_run_command(cmd, log_path, check=True, cwd=None):
        observed["cmd"] = cmd
        return None

    def _fake_wait_for_sidecar(entry, container_name, log_path):
        observed["entry"] = entry
        observed["container_name"] = container_name

    monkeypatch.setattr(docker_local, "run_command", _fake_run_command)
    monkeypatch.setattr(docker_local, "_wait_for_sidecar", _fake_wait_for_sidecar)

    records = docker_local._start_sidecars(
        "sid-demo",
        bundle,
        execution_surface={
            "sidecars": [
                {
                    "name": "mysql-main",
                    "image": "mysql:8.0",
                    "aliases": ["db-internal"],
                    "env": {"MYSQL_ROOT_PASSWORD": "pw"},
                    "ready_probe": {"type": "mysql", "retries": 3},
                }
            ]
        },
        workspace=None,
        run_dir=tmp_path,
        network_alias=docker_local.NetworkHandle("sid-demo-net"),
    )

    assert observed["entry"] == {
        "name": "mysql-main",
        "image": "mysql:8.0",
        "aliases": ["db-internal"],
        "env": {"MYSQL_ROOT_PASSWORD": "pw"},
        "ready_probe": {"type": "mysql", "retries": 3},
    }
    assert "--network-alias" in observed["cmd"]
    assert records == [
        {
            "name": "mysql-main",
            "type": None,
            "container": "sid-demo-cwe-89-mysql-main",
            "image": "mysql:8.0",
            "aliases": ["db-internal"],
            "start_order_index": 1,
            "seed_mount_target": None,
            "seed_files_applied": [],
        }
    ]


def test_start_sidecars_uses_aliases_materialized_from_network_contract(tmp_path: Path, monkeypatch) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    bundle = VulnBundle(vuln_id="CWE-89", slug="cwe-89", workspace_subdir="app")
    observed: dict[str, object] = {}
    monkeypatch.setattr(docker_local, "DOCKER_BIN", "docker")
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "executor_plan": {
                    "service_port": 9000,
                    "service_env": {"APP_PORT": "9000"},
                    "sidecars": [
                        {
                            "name": "mysql-main",
                            "type": "mysql",
                            "image": "mysql:8.0",
                            "env": {"MYSQL_ROOT_PASSWORD": "pw"},
                        }
                    ],
                    "network_contract": [
                        {"scope": "service", "name": "DB_HOST", "alias": "db-internal"},
                        {"scope": "sidecar:mysql-main", "alias": "db-internal"},
                    ],
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    def _fake_run_command(cmd, log_path, check=True, cwd=None):
        observed["cmd"] = cmd
        return None

    monkeypatch.setattr(docker_local, "run_command", _fake_run_command)
    monkeypatch.setattr(docker_local, "_wait_for_sidecar", lambda entry, container_name, log_path: None)

    surface = docker_local._resolve_execution_surface(metadata_dir, tmp_path, {})
    docker_local._start_sidecars(
        "sid-demo",
        bundle,
        execution_surface=surface,
        workspace=None,
        run_dir=tmp_path,
        network_alias=docker_local.NetworkHandle("sid-demo-net"),
    )

    assert "--network-alias" in observed["cmd"]
    assert "db-internal" in observed["cmd"]


def test_start_sidecars_honors_explicit_start_order(tmp_path: Path, monkeypatch) -> None:
    bundle = VulnBundle(vuln_id="CWE-89", slug="cwe-89", workspace_subdir="app")
    started: list[str] = []
    monkeypatch.setattr(docker_local, "DOCKER_BIN", "docker")
    monkeypatch.setattr(docker_local, "_wait_for_sidecar", lambda entry, container_name, log_path: None)

    def _fake_run_command(cmd, log_path, check=True, cwd=None):
        if len(cmd) >= 6 and cmd[0] == "docker" and cmd[1] == "run":
            started.append(cmd[5])
        return None

    monkeypatch.setattr(docker_local, "run_command", _fake_run_command)

    records = docker_local._start_sidecars(
        "sid-demo",
        bundle,
        execution_surface={
            "sidecars": [
                {"name": "postgres-main", "image": "postgres:16", "ready_probe": {"type": "postgres", "retries": 1}},
                {"name": "mysql-main", "image": "mysql:8.0", "ready_probe": {"type": "mysql", "retries": 1}},
            ],
            "sidecar_start_order": ["mysql-main", "postgres-main"],
        },
        workspace=None,
        run_dir=tmp_path,
        network_alias=docker_local.NetworkHandle("sid-demo-net"),
    )

    assert started == ["sid-demo-cwe-89-mysql-main", "sid-demo-cwe-89-postgres-main"]
    assert records[0]["name"] == "mysql-main"
    assert records[0]["start_order_index"] == 1
    assert records[1]["name"] == "postgres-main"
    assert records[1]["start_order_index"] == 2


def test_start_sidecars_applies_mysql_seed_sql_files(tmp_path: Path, monkeypatch) -> None:
    bundle = VulnBundle(vuln_id="CWE-89", slug="cwe-89", workspace_subdir="app")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "schema.sql").write_text("create table demo(id integer);\n", encoding="utf-8")
    (workspace / "notes.txt").write_text("ignored\n", encoding="utf-8")
    commands: list[list[str]] = []
    monkeypatch.setattr(docker_local, "DOCKER_BIN", "docker")
    monkeypatch.setattr(docker_local, "_wait_for_sidecar", lambda entry, container_name, log_path: None)

    def _fake_run_command(cmd, log_path, check=True, cwd=None):
        commands.append(cmd)
        return None

    monkeypatch.setattr(docker_local, "run_command", _fake_run_command)

    records = docker_local._start_sidecars(
        "sid-demo",
        bundle,
        execution_surface={
            "sidecars": [
                {
                    "name": "mysql-main",
                    "type": "mysql",
                    "image": "mysql:8.0",
                    "aliases": ["db-internal"],
                    "env": {
                        "MYSQL_DATABASE": "appdb",
                        "MYSQL_USER": "appuser",
                        "MYSQL_PASSWORD": "apppw",
                    },
                    "ready_probe": {"type": "mysql", "retries": 3},
                }
            ],
            "seed_strategy": "sidecar_sql_apply",
            "seed_files": ["schema.sql", "notes.txt"],
            "service_env": {"DB_NAME": "appdb", "DB_USER": "appuser", "DB_PASSWORD": "apppw"},
        },
        workspace=workspace,
        run_dir=tmp_path,
        network_alias=docker_local.NetworkHandle("sid-demo-net"),
    )

    assert commands[0][:7] == ["docker", "run", "-d", "--rm", "--name", "sid-demo-cwe-89-mysql-main", "--network"]
    assert "-v" in commands[0]
    assert f"{workspace.resolve()}:/seed-input:ro" in commands[0]
    assert commands[1][:4] == ["docker", "exec", "sid-demo-cwe-89-mysql-main", "sh"]
    assert "mysql " in commands[1][-1]
    assert "/seed-input/schema.sql" in commands[1][-1]
    assert "notes.txt" not in commands[1][-1]
    assert records == [
        {
            "name": "mysql-main",
            "type": "mysql",
            "container": "sid-demo-cwe-89-mysql-main",
            "image": "mysql:8.0",
            "aliases": ["db-internal"],
            "start_order_index": 1,
            "seed_mount_target": "/seed-input",
            "seed_files_applied": ["schema.sql"],
        }
    ]


def test_start_sidecars_applies_mysql_seed_sql_files_with_custom_mount_target(tmp_path: Path, monkeypatch) -> None:
    bundle = VulnBundle(vuln_id="CWE-89", slug="cwe-89", workspace_subdir="app")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "schema.sql").write_text("create table demo(id integer);\n", encoding="utf-8")
    commands: list[list[str]] = []
    monkeypatch.setattr(docker_local, "DOCKER_BIN", "docker")
    monkeypatch.setattr(docker_local, "_wait_for_sidecar", lambda entry, container_name, log_path: None)

    def _fake_run_command(cmd, log_path, check=True, cwd=None):
        commands.append(cmd)
        return None

    monkeypatch.setattr(docker_local, "run_command", _fake_run_command)

    records = docker_local._start_sidecars(
        "sid-demo",
        bundle,
        execution_surface={
            "sidecars": [
                {
                    "name": "mysql-main",
                    "type": "mysql",
                    "image": "mysql:8.0",
                    "aliases": ["db-internal"],
                    "env": {
                        "MYSQL_DATABASE": "appdb",
                        "MYSQL_USER": "appuser",
                        "MYSQL_PASSWORD": "apppw",
                    },
                    "ready_probe": {"type": "mysql", "retries": 3},
                }
            ],
            "seed_strategy": "sidecar_sql_apply",
            "seed_files": ["schema.sql"],
            "volume_contract": [
                {
                    "scope": "sidecar:mysql-main",
                    "source": "workspace",
                    "target": "/imports",
                    "mode": "ro",
                }
            ],
            "service_env": {"DB_NAME": "appdb", "DB_USER": "appuser", "DB_PASSWORD": "apppw"},
        },
        workspace=workspace,
        run_dir=tmp_path,
        network_alias=docker_local.NetworkHandle("sid-demo-net"),
    )

    assert f"{workspace.resolve()}:/imports:ro" in commands[0]
    assert "/imports/schema.sql" in commands[1][-1]
    assert records[0]["seed_files_applied"] == ["schema.sql"]
    assert records[0]["seed_mount_target"] == "/imports"


def test_start_sidecars_applies_postgres_seed_sql_files(tmp_path: Path, monkeypatch) -> None:
    bundle = VulnBundle(vuln_id="CWE-89", slug="cwe-89", workspace_subdir="app")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "schema.sql").write_text("create table demo(id integer);\n", encoding="utf-8")
    commands: list[list[str]] = []
    monkeypatch.setattr(docker_local, "DOCKER_BIN", "docker")
    monkeypatch.setattr(docker_local, "_wait_for_sidecar", lambda entry, container_name, log_path: None)

    def _fake_run_command(cmd, log_path, check=True, cwd=None):
        commands.append(cmd)
        return None

    monkeypatch.setattr(docker_local, "run_command", _fake_run_command)

    records = docker_local._start_sidecars(
        "sid-demo",
        bundle,
        execution_surface={
            "sidecars": [
                {
                    "name": "postgres-main",
                    "type": "postgres",
                    "image": "postgres:16",
                    "aliases": ["db-internal"],
                    "env": {
                        "POSTGRES_DB": "appdb",
                        "POSTGRES_USER": "appuser",
                        "POSTGRES_PASSWORD": "apppw",
                    },
                    "ready_probe": {"type": "postgres", "retries": 3},
                }
            ],
            "seed_strategy": "sidecar_sql_apply",
            "seed_files": ["schema.sql"],
            "service_env": {"DB_NAME": "appdb", "DB_USER": "appuser", "DB_PASSWORD": "apppw", "DB_PORT": "5432"},
        },
        workspace=workspace,
        run_dir=tmp_path,
        network_alias=docker_local.NetworkHandle("sid-demo-net"),
    )

    assert "-v" in commands[0]
    assert f"{workspace.resolve()}:/seed-input:ro" in commands[0]
    assert commands[1][:4] == ["docker", "exec", "sid-demo-cwe-89-postgres-main", "sh"]
    assert "psql " in commands[1][-1]
    assert "-f /seed-input/schema.sql" in commands[1][-1]
    assert records == [
        {
            "name": "postgres-main",
            "type": "postgres",
            "container": "sid-demo-cwe-89-postgres-main",
            "image": "postgres:16",
            "aliases": ["db-internal"],
            "start_order_index": 1,
            "seed_mount_target": "/seed-input",
            "seed_files_applied": ["schema.sql"],
        }
    ]


def test_start_sidecars_skips_sql_seed_apply_when_strategy_is_sqlite_service_init(tmp_path: Path, monkeypatch) -> None:
    bundle = VulnBundle(vuln_id="CWE-89", slug="cwe-89", workspace_subdir="app")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "schema.sql").write_text("create table demo(id integer);\n", encoding="utf-8")
    commands: list[list[str]] = []
    monkeypatch.setattr(docker_local, "DOCKER_BIN", "docker")
    monkeypatch.setattr(docker_local, "_wait_for_sidecar", lambda entry, container_name, log_path: None)

    def _fake_run_command(cmd, log_path, check=True, cwd=None):
        commands.append(cmd)
        return None

    monkeypatch.setattr(docker_local, "run_command", _fake_run_command)

    records = docker_local._start_sidecars(
        "sid-demo",
        bundle,
        execution_surface={
            "sidecars": [{"name": "mysql-main", "type": "mysql", "image": "mysql:8.0", "ready_probe": {"type": "mysql", "retries": 1}}],
            "seed_strategy": "sqlite_service_init",
            "seed_files": ["schema.sql"],
        },
        workspace=workspace,
        run_dir=tmp_path,
        network_alias=docker_local.NetworkHandle("sid-demo-net"),
    )

    assert len(commands) == 1
    assert commands[0][0:2] == ["docker", "run"]
    assert records[0]["seed_files_applied"] == []
    assert records[0]["seed_mount_target"] is None


def test_seed_apply_observation_marks_attempted_and_completed() -> None:
    observation = docker_local._seed_apply_observation(
        {
            "seed_strategy": "sidecar_sql_apply",
            "seed_files": ["schema.sql"],
        },
        [{"name": "mysql-main", "seed_files_applied": ["schema.sql"], "seed_mount_target": "/seed-input"}],
    )

    assert observation == {
        "seed_apply_attempted": True,
        "seed_apply_completed": True,
        "seed_files_applied_total": 1,
        "seed_mount_targets": ["/seed-input"],
    }


def test_stop_sidecars_uses_reverse_order(monkeypatch) -> None:
    stopped: list[str] = []

    def _fake_subprocess_run(cmd, **kwargs):
        stopped.append(cmd[-1])
        class _Proc:
            returncode = 0
        return _Proc()

    monkeypatch.setattr(docker_local.subprocess, "run", _fake_subprocess_run)

    docker_local._stop_sidecars(
        [
            {"container": "sidecar-a"},
            {"container": "sidecar-b"},
            {"container": "sidecar-c"},
        ]
    )

    assert stopped == ["sidecar-c", "sidecar-b", "sidecar-a"]


def test_wait_for_sidecar_dispatches_postgres_probe(tmp_path: Path, monkeypatch) -> None:
    observed: dict[str, object] = {}

    def _fake_probe(entry, container_name, log_path, probe):
        observed["entry"] = entry
        observed["container_name"] = container_name
        observed["probe"] = probe

    monkeypatch.setattr(docker_local, "_probe_postgres_sidecar", _fake_probe)

    entry = {
        "name": "postgres-main",
        "image": "postgres:16",
        "env": {"POSTGRES_DB": "appdb", "POSTGRES_USER": "appuser", "POSTGRES_PASSWORD": "apppw"},
        "ready_probe": {"type": "postgres", "retries": 4},
    }

    docker_local._wait_for_sidecar(entry, "sid-demo-cwe-89-postgres-main", tmp_path / "run.log")

    assert observed["container_name"] == "sid-demo-cwe-89-postgres-main"
    assert observed["probe"] == {"type": "postgres", "retries": 4}


def test_app_readiness_urls_prioritize_healthchecks_before_health_path() -> None:
    urls = docker_local._app_readiness_urls(
        port=5000,
        health_path="/health",
        healthchecks=[
            {"path": "/ready", "transport": "http"},
            {"path": "alive", "transport": "https", "port": 5443},
            {"path": "/ready", "transport": "http"},
            {"path": "/skip", "transport": "tcp"},
        ],
    )

    assert urls == [
        "http://127.0.0.1:5000/ready",
        "https://127.0.0.1:5443/alive",
        "http://127.0.0.1:5000/health",
        "http://127.0.0.1:5000/",
    ]


def test_oracle_positive_success_respects_signature_flag_and_forbidden_markers() -> None:
    analysis = docker_local._oracle_positive_success(
        "Exploit SUCCESS\nFLAG{OK}\n",
        0,
        {
            "success_signature": "Exploit SUCCESS",
            "flag_token": "FLAG{OK}",
            "forbidden_success_markers": ["false positive"],
            "assertion_program": [
                {"op": "contains", "string": "Exploit SUCCESS"},
                {"op": "contains", "string": "FLAG{OK}"},
            ],
        },
    )

    assert analysis["positive_hit"] is True
    assert analysis["success_signature_hit"] is True
    assert analysis["flag_token_hit"] is True
    assert analysis["assertion_program_pass"] is True
    assert analysis["matched_forbidden_markers"] == []


def test_execute_oracle_replays_writes_artifact_for_runnable_cases(tmp_path: Path, monkeypatch) -> None:
    metadata_dir = tmp_path / "metadata"
    run_dir = tmp_path / "run"
    metadata_dir.mkdir()
    run_dir.mkdir()
    (metadata_dir / "resolved_contract.json").write_text(
        json.dumps(
            {
                "exploit_oracle": {
                    "success_signature": "Exploit SUCCESS",
                    "flag_token": "FLAG{OK}",
                    "negative_controls": [
                        {"name": "benign", "payload": "safe", "expect_success": False},
                    ],
                    "metamorphic": {
                        "relation": "same-origin redirect remains non-exploit",
                        "cases": [
                            {"name": "same-origin", "payload": "/local", "expect_success": False},
                        ],
                    },
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    def _fake_case(**kwargs):
        return {
            "name": kwargs["name"],
            "payload": kwargs["payload"],
            "expect_success": kwargs["expect_success"],
            "passed": True,
            "exit_code": 0,
            "success_signature_hit": kwargs["expect_success"],
            "flag_token_hit": kwargs["expect_success"],
            "assertion_program_pass": True,
            "matched_negative_markers": [],
            "matched_forbidden_markers": [],
            "output_excerpt": "ok",
            "assertion_outcomes": [],
        }

    monkeypatch.setattr(docker_local, "_evaluate_oracle_case", _fake_case)

    payload = docker_local._execute_oracle_replays(
        container_name="demo-container",
        metadata_dir=metadata_dir,
        run_dir=run_dir,
        log_path=run_dir / "run.log",
        poc_path="/tmp/poc.py",
        base_url="http://127.0.0.1:5000",
        poc_cmd="python /tmp/poc.py --base-url {{base_url}} --payload {{payload}}",
        success_exit_code=0,
        success_payloads=["exploit"],
    )

    assert payload["parity"] == "high"
    assert payload["negative_controls"]["passed"] is True
    assert payload["metamorphic"]["passed"] is True
    assert (run_dir / docker_local.ORACLE_EXECUTION_FILENAME).exists()


def test_network_pool_acquire_uses_bundle_policy_override(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(docker_local.NetworkPool, "_ensure_network", lambda self, name: None)
    pool = docker_local.NetworkPool("sid-demo", {"allow_network": False, "network_mode": "none", "sidecars": []})

    handle = pool.acquire(
        VulnBundle(vuln_id="CWE-89", slug="cwe-89", workspace_subdir="app"),
        {"allow_network": True, "network_mode": "bridge", "sidecars": []},
    )

    assert handle.mode == "bridge"


def test_network_pool_acquire_uses_bundle_sidecar_aliases_for_named_network(monkeypatch) -> None:
    monkeypatch.setattr(docker_local.NetworkPool, "_ensure_network", lambda self, name: None)
    pool = docker_local.NetworkPool("sid-demo", {"allow_network": False, "network_mode": "none", "sidecars": []})

    handle = pool.acquire(
        VulnBundle(vuln_id="CWE-89", slug="cwe-89", workspace_subdir="app"),
        {
            "allow_network": True,
            "network_mode": "bridge",
            "sidecars": [{"name": "mysql-main", "image": "mysql:8.0", "aliases": ["db-internal"]}],
        },
    )

    assert handle.mode == "sid-demo-net"


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
