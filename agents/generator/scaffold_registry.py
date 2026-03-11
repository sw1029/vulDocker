"""Registry of stack scaffolds used by compiler-backed generation."""
from __future__ import annotations

import json
from functools import lru_cache
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
    run_command_template: str
    poc_command_template: str
    service_entry: str
    service_host: str
    health_route_path: str
    health_route_response: str
    service_template: tuple[str, ...]
    readme_template: tuple[str, ...]
    dockerfile_template: tuple[str, ...]
    aliases: tuple[str, ...] = ()

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

    def render_build_command(self) -> str:
        return self.install_command

    def render_run_command(self, *, service_path: str) -> str:
        return self.run_command_template.replace("{{service_path}}", service_path)

    def render_poc_command(self, *, poc_path: str) -> str:
        return self.poc_command_template.replace("{{poc_path}}", poc_path)

    def render_health_route(self) -> str:
        return (
            f"@app.get('{self.health_route_path}')\n"
            "def health():\n"
            f"    return {self.health_route_response}\n"
        )

    def render_service(
        self,
        *,
        import_block: str,
        app_setup_block: str,
        route_block: str,
        startup_block: str,
        port: int,
    ) -> str:
        replacements = {
            "{{import_block}}": import_block.strip(),
            "{{app_setup_block}}": app_setup_block.strip(),
            "{{health_route}}": self.render_health_route().strip(),
            "{{route_block}}": route_block.strip(),
            "{{startup_block}}": startup_block.rstrip(),
            "{{service_host_repr}}": repr(self.service_host),
            "{{port}}": str(port),
        }
        return self._render_multiline_template(self.service_template, replacements)

    def render_readme(
        self,
        *,
        requested_name: str,
        port: int,
        vuln_id: str = "",
        service_path: str = "",
        fragment_id: str = "",
        service_description: str = "",
        poc_description: str = "",
        runtime_assumptions: str = "",
    ) -> str:
        replacements = {
            "{{requested_name}}": requested_name.strip() or "Compiler bundle",
            "{{port}}": str(port),
            "{{vuln_id}}": vuln_id.strip() or "UNKNOWN",
            "{{service_path}}": service_path.strip() or self.service_entry,
            "{{fragment_id}}": fragment_id.strip() or "unknown-fragment",
            "{{scaffold_id}}": self.scaffold_id,
            "{{health_route_path}}": self.health_route_path,
            "{{service_description_line}}": (
                f"- Service behavior: {service_description.strip()}" if service_description.strip() else ""
            ),
            "{{poc_description_line}}": (
                f"- Exploit contract: {poc_description.strip()}" if poc_description.strip() else ""
            ),
            "{{runtime_assumptions_line}}": (
                f"- Runtime assumptions: {runtime_assumptions.strip()}" if runtime_assumptions.strip() else ""
            ),
        }
        return self._render_multiline_template(self.readme_template, replacements)

    @staticmethod
    def _render_multiline_template(
        template_lines: tuple[str, ...],
        replacements: dict[str, str],
    ) -> str:
        text = "\n".join(template_lines)
        for key, value in replacements.items():
            text = text.replace(key, value)
        lines = [line.rstrip() for line in text.splitlines()]
        compacted: list[str] = []
        blank_streak = 0
        for line in lines:
            if line.strip():
                blank_streak = 0
                compacted.append(line)
                continue
            blank_streak += 1
            if blank_streak <= 1:
                compacted.append("")
        return "\n".join(compacted).strip() + "\n"


def _load_scaffold_asset(path: Path) -> ScaffoldSpec:
    payload = json.loads(path.read_text(encoding="utf-8"))
    health = payload.get("health_route") if isinstance(payload.get("health_route"), dict) else {}
    template = payload.get("dockerfile_template") if isinstance(payload.get("dockerfile_template"), list) else []
    service_template = (
        payload.get("service_template")
        if isinstance(payload.get("service_template"), list)
        else []
    )
    readme_template = (
        payload.get("readme_template")
        if isinstance(payload.get("readme_template"), list)
        else []
    )
    aliases = payload.get("aliases") if isinstance(payload.get("aliases"), list) else []
    return ScaffoldSpec(
        scaffold_id=str(payload.get("scaffold_id") or "python/flask"),
        version=str(payload.get("version") or "1.0"),
        language=str(payload.get("language") or "python"),
        framework=str(payload.get("framework") or "flask"),
        base_image=str(payload.get("base_image") or "python:3.11-slim"),
        workdir=str(payload.get("workdir") or "/app"),
        requirements_path=str(payload.get("requirements_path") or "requirements.txt"),
        install_command=str(payload.get("install_command") or "pip install --no-cache-dir -r requirements.txt"),
        run_command_template=str(payload.get("run_command_template") or "python {{service_path}}"),
        poc_command_template=str(
            payload.get("poc_command_template") or "python {{poc_path}} --base-url {{base_url}}"
        ),
        service_entry=str(payload.get("service_entry") or "app.py"),
        service_host=str(payload.get("service_host") or "0.0.0.0"),
        health_route_path=str(health.get("path") or "/health"),
        health_route_response=str(health.get("response") or "{'ok': True}"),
        service_template=tuple(
            str(item) for item in service_template if isinstance(item, str)
        ),
        readme_template=tuple(
            str(item) for item in readme_template if isinstance(item, str)
        ),
        dockerfile_template=tuple(str(item) for item in template if isinstance(item, str) and item.strip()),
        aliases=tuple(str(item).strip().lower() for item in aliases if isinstance(item, str) and str(item).strip()),
    )


@lru_cache(maxsize=1)
def _catalog() -> Dict[str, ScaffoldSpec]:
    catalog: Dict[str, ScaffoldSpec] = {}
    for path in sorted(ASSETS_ROOT.glob("*-scaffold.json")):
        spec = _load_scaffold_asset(path)
        keys = {
            spec.scaffold_id.strip().lower(),
            f"{spec.language}/{spec.framework}".strip().lower(),
        }
        keys.update(spec.aliases)
        for key in keys:
            if key:
                catalog[key] = spec
    return catalog


def load_scaffold_spec(stack_name: str) -> ScaffoldSpec | None:
    token = str(stack_name or "").strip().lower()
    if not token:
        token = "python/flask"
    return _catalog().get(token)


__all__ = ["ScaffoldSpec", "load_scaffold_spec"]
