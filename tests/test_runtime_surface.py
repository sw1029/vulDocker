from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.runtime_surface import derive_service_env, diagnose_runtime_surface


def test_derive_service_env_uses_catalog_variant_defaults() -> None:
    env = derive_service_env(
        compiler_strategy="sqli_string_concat_mysql",
        requirement={
            "runtime": {"db": "mysql", "allow_external_db": True},
            "executor": {"sidecars": [{"name": "mysql", "type": "mysql", "aliases": ["sqli-db"]}]},
        },
        service_port=5000,
    )

    assert env == {
        "APP_PORT": "5000",
        "DB_HOST": "sqli-db",
        "DB_PORT": "3306",
        "DB_USER": "sqli",
        "DB_PASSWORD": "sqli_pw",
        "DB_NAME": "sqliapp",
    }


def test_derive_service_env_uses_catalog_variant_custom_sidecar_values() -> None:
    env = derive_service_env(
        compiler_strategy="sqli_string_concat_mysql",
        requirement={
            "runtime": {"db": "mysql", "allow_external_db": True, "db_name": "runtime_db"},
            "executor": {
                "sidecars": [
                    {
                        "name": "mysql-main",
                        "type": "mysql",
                        "aliases": ["db-internal"],
                        "env": {
                            "MYSQL_USER": "custom_user",
                            "MYSQL_PASSWORD": "custom_pw",
                            "MYSQL_DATABASE": "custom_db",
                        },
                    }
                ]
            },
        },
        service_port=5001,
    )

    assert env == {
        "APP_PORT": "5001",
        "DB_HOST": "db-internal",
        "DB_PORT": "3306",
        "DB_USER": "custom_user",
        "DB_PASSWORD": "custom_pw",
        "DB_NAME": "custom_db",
    }


def test_derive_service_env_returns_empty_for_strategy_without_runtime_surface_spec() -> None:
    env = derive_service_env(
        compiler_strategy="template_injection_render",
        requirement={"runtime": {"db": "sqlite"}},
        service_port=5000,
    )

    assert env == {}


def test_diagnose_runtime_surface_flags_missing_compatible_sidecar_target() -> None:
    diagnostics = diagnose_runtime_surface(
        compiler_strategy="sqli_string_concat_mysql",
        requirement={
            "runtime": {"db": "mysql", "allow_external_db": True},
            "executor": {
                "sidecars": [
                    {"name": "pg-main", "type": "postgres", "aliases": ["db-internal"]},
                ]
            },
        },
        service_port=5000,
    )

    assert diagnostics["service_env"]["DB_HOST"] == "sqli-db"
    assert diagnostics["missing_sidecar_targets"] == [{"sidecar_type": "mysql", "sidecar_name": ""}]
    assert sorted(diagnostics["defaulted_sidecar_keys"]) == ["DB_HOST", "DB_NAME", "DB_PASSWORD", "DB_USER"]


def test_diagnose_runtime_surface_flags_defaulted_sidecar_env_keys() -> None:
    diagnostics = diagnose_runtime_surface(
        compiler_strategy="sqli_string_concat_mysql",
        requirement={
            "runtime": {"db": "mysql", "allow_external_db": True},
            "executor": {
                "sidecars": [
                    {"name": "mysql", "type": "mysql", "aliases": ["sqli-db"]},
                ]
            },
        },
        service_port=5000,
    )

    assert diagnostics["missing_sidecar_targets"] == []
    assert sorted(diagnostics["defaulted_sidecar_keys"]) == ["DB_NAME", "DB_PASSWORD", "DB_USER"]
