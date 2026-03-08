"""Registry of stack scaffolds used by compiler-backed generation."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict


ASSETS_ROOT = Path(__file__).resolve().parent / "assets"


@dataclass(frozen=True)
class ScaffoldSpec:
    scaffold_id: str
    version: str
    language: str
    framework: str
    base_image: str
    workdir: str
    requirements_path: str
    install_command: str
    service_entry: str
    service_host: str
    health_route_path: str
    health_route_response: str
    dockerfile_template: tuple[str, ...]

    def render_dockerfile(self, *, service_path: str, port: int) -> str:
        replacements = {
            "{{base_image}}": self.base_image,
            "{{workdir}}": self.workdir,
            "{{install_command}}": self.install_command,
            "{{port}}": str(port),
            "{{service_path}}": service_path,
        }
        lines = []
        for line in self.dockerfile_template:
            rendered = line
            for key, value in replacements.items():
                rendered = rendered.replace(key, value)
            lines.append(rendered)
        return "\n".join(lines) + "\n"

    def render_health_route(self) -> str:
        return (
            f"@app.get('{self.health_route_path}')\n"
            "def health():\n"
            f"    return {self.health_route_response}\n"
        )


def _load_scaffold_asset(path: Path) -> ScaffoldSpec:
    payload = json.loads(path.read_text(encoding="utf-8"))
    health = payload.get("health_route") if isinstance(payload.get("health_route"), dict) else {}
    template = payload.get("dockerfile_template") if isinstance(payload.get("dockerfile_template"), list) else []
    return ScaffoldSpec(
        scaffold_id=str(payload.get("scaffold_id") or "python/flask"),
        version=str(payload.get("version") or "1.0"),
        language=str(payload.get("language") or "python"),
        framework=str(payload.get("framework") or "flask"),
        base_image=str(payload.get("base_image") or "python:3.11-slim"),
        workdir=str(payload.get("workdir") or "/app"),
        requirements_path=str(payload.get("requirements_path") or "requirements.txt"),
        install_command=str(payload.get("install_command") or "pip install --no-cache-dir -r requirements.txt"),
        service_entry=str(payload.get("service_entry") or "app.py"),
        service_host=str(payload.get("service_host") or "0.0.0.0"),
        health_route_path=str(health.get("path") or "/health"),
        health_route_response=str(health.get("response") or "{'ok': True}"),
        dockerfile_template=tuple(str(item) for item in template if isinstance(item, str) and item.strip()),
    )


def _catalog() -> Dict[str, ScaffoldSpec]:
    flask_asset = ASSETS_ROOT / "python-flask-scaffold.json"
    spec = _load_scaffold_asset(flask_asset)
    return {
        spec.scaffold_id: spec,
        f"{spec.language}/{spec.framework}": spec,
    }


def load_scaffold_spec(stack_name: str) -> ScaffoldSpec | None:
    token = str(stack_name or "").strip().lower()
    if not token:
        token = "python/flask"
    return _catalog().get(token)


__all__ = ["ScaffoldSpec", "load_scaffold_spec"]
