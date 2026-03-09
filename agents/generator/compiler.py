"""Deterministic scaffold/fragment compiler for compiler-covered families."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.generator.flask_fragment_registry import FLASK_FRAGMENT_REGISTRY
from agents.generator.scaffold_registry import load_scaffold_spec
from common.runtime_surface import derive_service_env

SUPPORTED_COMPILER_STRATEGIES = frozenset(FLASK_FRAGMENT_REGISTRY)
ASSETS_ROOT = Path(__file__).resolve().parent / "assets"
COMPILER_TARGETS_PATH = ASSETS_ROOT / "compiler-targets.json"


@dataclass
class CompilerResult:
    strategy: str
    manifest: Dict[str, Any]
    notes: str = ""


def supported_compiler_strategies() -> set[str]:
    return set(SUPPORTED_COMPILER_STRATEGIES)


def _default_compiler_targets() -> Dict[str, Dict[str, str]]:
    payload = json.loads(COMPILER_TARGETS_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}
    normalized: Dict[str, Dict[str, str]] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        name = str(value.get("name") or "").strip()
        vuln_id = str(value.get("vuln_id") or "").strip()
        if not name or not vuln_id:
            continue
        normalized[key.strip()] = {"name": name, "vuln_id": vuln_id}
    return normalized


def compile_manifest(
    *,
    sid: str,
    requirement: Dict[str, Any],
    semantic_profile: Dict[str, Any],
) -> Optional[CompilerResult]:
    strategy = str(semantic_profile.get("compiler_strategy") or "").strip()
    fragment = FLASK_FRAGMENT_REGISTRY.get(strategy)
    defaults = _default_compiler_targets().get(strategy)
    if fragment is None or defaults is None:
        return None
    return CompilerResult(
        strategy=strategy,
        manifest=_compile_registered_flask_fragment_manifest(
            sid=sid,
            requirement=requirement,
            semantic_profile=semantic_profile,
            strategy=strategy,
            default_name=defaults["name"],
            default_vuln_id=defaults["vuln_id"],
        ),
        notes=f"python/flask scaffold + registry fragment({fragment.family})",
    )


def _compile_registered_flask_fragment_manifest(
    *,
    sid: str,
    requirement: Dict[str, Any],
    semantic_profile: Dict[str, Any],
    strategy: str,
    default_name: str,
    default_vuln_id: str,
) -> Dict[str, Any]:
    fragment = FLASK_FRAGMENT_REGISTRY[strategy]
    port = _service_port(semantic_profile)
    stack = _stack_name(semantic_profile)
    scaffold = load_scaffold_spec(stack)
    if scaffold is None:
        return None
    service_path = scaffold.service_entry
    requested_name = str(
        semantic_profile.get("requested_name") or requirement.get("vuln_name") or default_name
    ).strip()
    vuln_id = str(
        semantic_profile.get("normalized_vuln_id") or requirement.get("vuln_id") or default_vuln_id
    ).strip()
    poc_payload = fragment.poc_builder(port)
    import_block = fragment.import_block.replace("{{port}}", str(port))
    app_setup_block = fragment.app_setup_block.replace("{{port}}", str(port)).strip()
    route_block = fragment.route_block.replace("{{port}}", str(port)).strip()
    startup_block = fragment.startup_block.replace("{{port}}", str(port))
    app_content = (
        import_block
        + "\n\n"
        + "app = Flask(__name__)\n\n"
        + (app_setup_block + "\n\n" if app_setup_block else "")
        + scaffold.render_health_route()
        + "\n"
        + route_block
        + "\n"
        + "if __name__ == '__main__':\n"
        + startup_block
        + f"    app.run(host={scaffold.service_host!r}, port={port})\n"
    )
    run_env = derive_service_env(
        compiler_strategy=strategy,
        requirement=requirement,
        service_port=port,
    )
    return _compiler_manifest_from_parts(
        sid=sid,
        requested_name=requested_name,
        vuln_id=vuln_id,
        stack=stack,
        port=port,
        service_path=service_path,
        requirements_content=fragment.requirements_content,
        app_content=app_content,
        poc_content=str(poc_payload.get("poc_content") or ""),
        success_signature=str(poc_payload.get("success_signature") or "Exploit SUCCESS"),
        flag_token=str(poc_payload.get("flag_token") or ""),
        compiler_strategy=strategy,
        compiler_family=fragment.family,
        pattern_tags=list(fragment.pattern_tags),
        notes=fragment.notes,
        service_description=fragment.service_description,
        poc_description=fragment.poc_description,
        dockerfile_content=scaffold.render_dockerfile(service_path=service_path, port=port),
        stack_scaffold_id=scaffold.scaffold_id,
        stack_scaffold_version=scaffold.version,
        fragment_id=fragment.fragment_id,
        compose_mode="registry",
        run_env=run_env,
        requires_external_db=fragment.requires_external_db,
        extra_files=[dict(item) for item in fragment.extra_files],
    )


def _compiler_manifest_from_parts(
    *,
    sid: str,
    requested_name: str,
    vuln_id: str,
    stack: str,
    port: int,
    service_path: str,
    requirements_content: str,
    app_content: str,
    poc_content: str,
    success_signature: str,
    compiler_strategy: str,
    compiler_family: str,
    pattern_tags: List[str],
    notes: str,
    dockerfile_content: str,
    flag_token: str = "",
    service_description: str = "",
    poc_description: str = "",
    stack_scaffold_id: str = "",
    stack_scaffold_version: str = "",
    fragment_id: str = "",
    compose_mode: str = "",
    run_env: Optional[Dict[str, str]] = None,
    requires_external_db: bool = False,
    extra_files: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    files = [
        {
            "path": "Dockerfile",
            "role": "helper",
            "description": "Build Python image for compiler-generated bundle.",
            "content": dockerfile_content,
        },
        {
            "path": "requirements.txt",
            "role": "helper",
            "description": "Pinned deps for compiler-generated bundle.",
            "content": requirements_content,
        },
        {
            "path": service_path,
            "role": "service_main",
            "description": service_description or f"{stack} compiler-generated service.",
            "content": app_content,
        },
        {
            "path": "poc.py",
            "role": "poc_entry",
            "description": poc_description or "Compiler-generated PoC.",
            "content": poc_content,
        },
        {
            "path": "README.md",
            "role": "helper",
            "description": "Quickstart instructions.",
            "content": (
                f"# {requested_name} compiler bundle\n"
                "```bash\n"
                "docker build -t compiler-bundle .\n"
                f"docker run -p {port}:{port} compiler-bundle\n"
                f"python poc.py --base-url http://127.0.0.1:{port}\n"
                "```\n"
            ),
        },
    ]
    if extra_files:
        files.extend(extra_files)
    deps = [line.strip() for line in requirements_content.splitlines() if line.strip()]
    poc_payload: Dict[str, Any] = {
        "cmd": "python poc.py --base-url {{base_url}}",
        "success_signature": success_signature,
    }
    if flag_token:
        poc_payload["flag_token"] = flag_token
    payload = {
        "intent": f"{requested_name} compiler synthesis",
        "pattern_tags": pattern_tags,
        "files": files,
        "deps": deps,
        "build": {"command": "pip install --no-cache-dir -r requirements.txt"},
        "run": {"command": f"python {service_path}", "port": port},
        "poc": poc_payload,
        "notes": notes,
        "metadata": {
            "sid": sid,
            "stack": stack,
            "cwe": vuln_id,
            "generation_origin": "compiler_generated",
            "compiler_strategy": compiler_strategy,
            "compiler_family": compiler_family,
        },
    }
    if isinstance(run_env, dict) and run_env:
        payload["run"]["env"] = {str(key): str(value) for key, value in run_env.items() if str(key).strip()}
    metadata = payload["metadata"]
    if stack_scaffold_id:
        metadata["stack_scaffold_id"] = stack_scaffold_id
    if stack_scaffold_version:
        metadata["stack_scaffold_version"] = stack_scaffold_version
    if fragment_id:
        metadata["fragment_id"] = fragment_id
    if compose_mode:
        metadata["compose_mode"] = compose_mode
    if requires_external_db:
        payload["requires_external_db"] = True
        metadata["requires_external_db"] = True
    return payload
def _service_port(semantic_profile: Dict[str, Any]) -> int:
    scenario_shape = semantic_profile.get("scenario_shape") if isinstance(semantic_profile, dict) else {}
    if isinstance(scenario_shape, dict):
        try:
            value = int(scenario_shape.get("service_port") or 5000)
        except Exception:
            value = 5000
        if value > 0:
            return value
    return 5000


def _stack_name(semantic_profile: Dict[str, Any]) -> str:
    stack_profile = semantic_profile.get("stack_profile") if isinstance(semantic_profile, dict) else {}
    if not isinstance(stack_profile, dict):
        return "python/flask"
    language = str(stack_profile.get("language") or "python").strip().lower()
    framework = str(stack_profile.get("framework") or "flask").strip().lower()
    return f"{language}/{framework}"
