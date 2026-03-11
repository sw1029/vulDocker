from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.generator.scaffold_registry import load_scaffold_spec


def test_python_flask_scaffold_is_loaded_from_asset_catalog() -> None:
    spec = load_scaffold_spec("python/flask")

    assert spec is not None
    assert spec.scaffold_id == "python/flask"
    assert spec.version == "1.0"
    assert spec.base_image == "python:3.11-slim"
    assert spec.health_route_path == "/health"
    assert spec.service_template
    assert spec.readme_template


def test_python_flask_scaffold_renders_dockerfile_from_asset_template() -> None:
    spec = load_scaffold_spec("python/flask")
    assert spec is not None

    dockerfile = spec.render_dockerfile(service_path="app.py", port=5000)
    assert "FROM python:3.11-slim" in dockerfile
    assert "WORKDIR /app" in dockerfile
    assert "EXPOSE 5000" in dockerfile
    assert 'CMD ["python", "app.py"]' in dockerfile


def test_python_flask_scaffold_aliases_resolve_from_asset_catalog() -> None:
    assert load_scaffold_spec("python-flask") is not None
    assert load_scaffold_spec("flask") is not None


def test_python_flask_scaffold_renders_service_from_asset_template() -> None:
    spec = load_scaffold_spec("python/flask")
    assert spec is not None

    service = spec.render_service(
        import_block="from flask import Flask",
        app_setup_block="VALUE = 1",
        route_block="@app.get('/demo')\ndef demo():\n    return {'ok': VALUE}",
        startup_block="    prepare()",
        port=5000,
    )

    assert "from flask import Flask" in service
    assert "app = Flask(__name__)" in service
    assert "@app.get('/health')" in service
    assert "@app.get('/demo')" in service
    assert "prepare()" in service
    assert "app.run(host='0.0.0.0', port=5000)" in service


def test_python_flask_scaffold_renders_readme_from_asset_template() -> None:
    spec = load_scaffold_spec("python/flask")
    assert spec is not None

    readme = spec.render_readme(
        requested_name="Template Injection",
        port=5000,
        service_description="Registry-backed template injection service.",
        poc_description="Registry-backed template injection PoC.",
        runtime_assumptions="service expects runtime env {APP_PORT}",
    )

    assert readme.startswith("# Template Injection compiler bundle")
    assert "docker build -t compiler-bundle ." in readme
    assert "python poc.py --base-url http://127.0.0.1:5000" in readme
    assert "Service behavior: Registry-backed template injection service." in readme
    assert "Exploit contract: Registry-backed template injection PoC." in readme
    assert "Runtime assumptions: service expects runtime env {APP_PORT}" in readme


def test_python_flask_scaffold_renders_runtime_commands_from_asset_template() -> None:
    spec = load_scaffold_spec("python/flask")
    assert spec is not None

    assert spec.render_build_command() == "pip install --no-cache-dir -r requirements.txt"
    assert spec.render_run_command(service_path="app.py") == "python app.py"
    assert spec.render_poc_command(poc_path="poc.py") == "python poc.py --base-url {{base_url}}"


def test_python_fastapi_scaffold_is_loaded_from_asset_catalog() -> None:
    spec = load_scaffold_spec("python/fastapi")

    assert spec is not None
    assert spec.scaffold_id == "python/fastapi"
    assert spec.version == "1.0"
    assert spec.base_image == "python:3.11-slim"
    assert spec.health_route_path == "/health"
    assert spec.service_template
    assert spec.readme_template


def test_python_fastapi_scaffold_aliases_resolve_from_asset_catalog() -> None:
    assert load_scaffold_spec("python-fastapi") is not None
    assert load_scaffold_spec("fastapi") is not None


def test_python_fastapi_scaffold_renders_service_from_asset_template() -> None:
    spec = load_scaffold_spec("python/fastapi")
    assert spec is not None

    service = spec.render_service(
        import_block="from fastapi import FastAPI",
        app_setup_block="VALUE = 1",
        route_block="@app.get('/demo')\ndef demo():\n    return {'ok': VALUE}",
        startup_block="",
        port=5000,
    )

    assert "from fastapi import FastAPI" in service
    assert "app = FastAPI()" in service
    assert "@app.get('/health')" in service
    assert "@app.get('/demo')" in service
    assert "uvicorn.run(app, host='0.0.0.0', port=5000)" in service
