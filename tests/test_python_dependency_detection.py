from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.generator.deps.python import detect_required


def test_detect_required_ignores_local_python_modules() -> None:
    manifest = {
        "files": [
            {
                "path": "app.py",
                "content": "from helper import build_query\nimport flask\n",
            },
            {
                "path": "helper.py",
                "content": "def build_query():\n    return 'SELECT 1'\n",
            },
        ]
    }

    required = detect_required(manifest, lambda entry: str(entry.get("content") or ""))

    assert "flask" in required
    assert "helper" not in required
    assert "app" not in required
