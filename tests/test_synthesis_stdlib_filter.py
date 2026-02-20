from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.generator.synthesis import SynthesisEngine, SynthesisLimits


class _DummyLLM:
    def generate(self, messages, *, tools=None) -> str:  # pragma: no cover - not used
        return "{}"


def test_synthesis_dependency_detector_ignores_stdlib_imports(tmp_path: Path) -> None:
    engine = SynthesisEngine(
        sid="sid-test",
        llm=_DummyLLM(),
        limits=SynthesisLimits(),
        workspace=tmp_path / "workspace",
        metadata_dir=tmp_path / "metadata",
        mode="synthesis",
    )
    engine._requirement = {"language": "python", "runtime": {"language_version": "3.11"}}  # type: ignore[attr-defined]
    engine._load_stdlib_spec()

    manifest = {
        "files": [
            {
                "path": "app.py",
                "content": (
                    "import argparse\n"
                    "import sys\n"
                    "from urllib.parse import quote\n"
                    "from flask import Flask\n"
                ),
            }
        ]
    }
    required = engine._detect_required_dependencies(manifest)
    assert "flask" in required
    assert "argparse" not in required
    assert "sys" not in required
    assert "urllib" not in required


def test_synthesis_dependency_detector_treats_sqlite3_as_stdlib(tmp_path: Path) -> None:
    engine = SynthesisEngine(
        sid="sid-test",
        llm=_DummyLLM(),
        limits=SynthesisLimits(),
        workspace=tmp_path / "workspace",
        metadata_dir=tmp_path / "metadata",
        mode="synthesis",
    )
    engine._requirement = {"language": "python", "runtime": {"language_version": "3.11"}}  # type: ignore[attr-defined]
    engine._load_stdlib_spec()

    manifest = {
        "files": [
            {
                "path": "app.py",
                "content": (
                    "import sqlite3\n"
                    "from flask import Flask\n"
                    "app = Flask(__name__)\n"
                ),
            }
        ]
    }
    required = engine._detect_required_dependencies(manifest)
    assert "flask" in required
    assert "sqlite3" not in required
    assert "pysqlite3-binary" not in required


def test_inject_user_deps_skips_mysql_driver_for_sqlite_runtime(tmp_path: Path) -> None:
    engine = SynthesisEngine(
        sid="sid-test",
        llm=_DummyLLM(),
        limits=SynthesisLimits(),
        workspace=tmp_path / "workspace",
        metadata_dir=tmp_path / "metadata",
        mode="synthesis",
        user_deps=["pymysql", "requests==2.31.0"],
    )
    engine._requirement = {  # type: ignore[attr-defined]
        "language": "python",
        "runtime": {"language_version": "3.11", "db": "sqlite"},
    }
    engine._load_stdlib_spec()

    manifest = {"deps": ["Flask==3.0.0"], "files": []}
    patched = engine._inject_user_deps(manifest)
    deps = [str(item).lower() for item in (patched.get("deps") or [])]
    assert "pymysql" not in deps
    assert "requests==2.31.0" in deps
