"""Helpers for deriving runtime surface requirements from requirement+strategy."""
from __future__ import annotations

from typing import Any, Dict, Optional


def derive_service_env(
    *,
    compiler_strategy: str,
    requirement: Optional[Dict[str, Any]],
    service_port: Optional[int] = None,
) -> Dict[str, str]:
    req = requirement if isinstance(requirement, dict) else {}
    env: Dict[str, str] = {}
    if compiler_strategy == "sqli_string_concat_mysql":
        if service_port:
            env["APP_PORT"] = str(service_port)
        runtime = req.get("runtime") if isinstance(req.get("runtime"), dict) else {}
        executor = req.get("executor") if isinstance(req.get("executor"), dict) else {}
        runtime = runtime if isinstance(runtime, dict) else {}
        executor = executor if isinstance(executor, dict) else {}
        sidecars = executor.get("sidecars") if isinstance(executor.get("sidecars"), list) else []
        mysql_sidecar = None
        for entry in sidecars:
            if not isinstance(entry, dict):
                continue
            sidecar_type = str(entry.get("type") or "").strip().lower()
            name = str(entry.get("name") or "").strip().lower()
            if sidecar_type == "mysql" or name == "mysql":
                mysql_sidecar = entry
                break
        aliases = mysql_sidecar.get("aliases") if isinstance(mysql_sidecar, dict) and isinstance(mysql_sidecar.get("aliases"), list) else []
        if isinstance(aliases, list) and aliases:
            env["DB_HOST"] = str(aliases[0])
        elif isinstance(mysql_sidecar, dict) and str(mysql_sidecar.get("name") or "").strip():
            env["DB_HOST"] = str(mysql_sidecar.get("name"))
        else:
            env["DB_HOST"] = "sqli-db"
        env["DB_PORT"] = "3306"
        if isinstance(mysql_sidecar, dict):
            sidecar_env = mysql_sidecar.get("env") if isinstance(mysql_sidecar.get("env"), dict) else {}
        else:
            sidecar_env = {}
        env["DB_USER"] = str(sidecar_env.get("MYSQL_USER") or "sqli")
        env["DB_PASSWORD"] = str(sidecar_env.get("MYSQL_PASSWORD") or "sqli_pw")
        env["DB_NAME"] = str(sidecar_env.get("MYSQL_DATABASE") or runtime.get("db_name") or "sqliapp")
    return env


__all__ = ["derive_service_env"]
