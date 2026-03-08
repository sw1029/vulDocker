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


def test_python_flask_scaffold_renders_dockerfile_from_asset_template() -> None:
    spec = load_scaffold_spec("python/flask")
    assert spec is not None

    dockerfile = spec.render_dockerfile(service_path="app.py", port=5000)
    assert "FROM python:3.11-slim" in dockerfile
    assert "WORKDIR /app" in dockerfile
    assert "EXPOSE 5000" in dockerfile
    assert 'CMD ["python", "app.py"]' in dockerfile
