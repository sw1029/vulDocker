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


def _engine(tmp_path: Path) -> SynthesisEngine:
    engine = SynthesisEngine(
        sid="sid-test",
        llm=_DummyLLM(),
        limits=SynthesisLimits(),
        workspace=tmp_path / "workspace",
        metadata_dir=tmp_path / "metadata",
        mode="synthesis",
    )
    engine._requirement = {"language": "python", "runtime": {"python_version": "3.11"}}  # type: ignore[attr-defined]
    engine._load_stdlib_spec()
    return engine


def test_guard_rejects_sqlite3_cli_runtime_and_non_tmp_db_on_writes(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    manifest = {
        "files": [
            {
                "path": "app.py",
                "role": "service_main",
                "content": (
                    "import os\n"
                    "import sqlite3\n"
                    "import subprocess\n"
                    "\n"
                    "DATABASE = '/app/users.db'\n"
                    "\n"
                    "def do_write():\n"
                    "    conn = sqlite3.connect(DATABASE)\n"
                    "    conn.execute(\"UPDATE users SET balance = balance - 1\")\n"
                    "    conn.commit()\n"
                    "\n"
                    "if __name__ == '__main__':\n"
                    "    subprocess.run(['sqlite3', DATABASE, '.read schema.sql'])\n"
                    "    do_write()\n"
                ),
            },
            {
                "path": "poc.py",
                "role": "poc_entry",
                "content": "print('Exploit SUCCESS')\n",
            },
        ],
        "deps": [],
        "poc": {"cmd": "python poc.py --base-url {{base_url}}", "success_signature": "Exploit SUCCESS"},
        "pattern_tags": ["test"],
    }
    errors, _ = engine._guard_manifest(manifest)
    joined = "\n".join(errors)
    assert "sqlite3 CLI" in joined
    assert "SQLite writes detected" in joined


def test_guard_allows_sqlite_writes_when_db_path_under_tmp(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    manifest = {
        "files": [
            {
                "path": "app.py",
                "role": "service_main",
                "content": (
                    "import os\n"
                    "import sqlite3\n"
                    "\n"
                    "APP_DB_PATH = os.environ.get('APP_DB_PATH', '/tmp/app.db')\n"
                    "\n"
                    "def init_db() -> None:\n"
                    "    conn = sqlite3.connect(APP_DB_PATH)\n"
                    "    conn.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, balance INTEGER)')\n"
                    "    conn.commit()\n"
                    "    conn.close()\n"
                    "\n"
                    "def do_write():\n"
                    "    conn = sqlite3.connect(APP_DB_PATH)\n"
                    "    conn.execute(\"UPDATE users SET balance = balance - 1\")\n"
                    "    conn.commit()\n"
                    "\n"
                    "if __name__ == '__main__':\n"
                    "    init_db()\n"
                    "    do_write()\n"
                ),
            },
            {
                "path": "poc.py",
                "role": "poc_entry",
                "content": "print('Exploit SUCCESS')\n",
            },
        ],
        "deps": [],
        "poc": {"cmd": "python poc.py --base-url {{base_url}}", "success_signature": "Exploit SUCCESS"},
        "pattern_tags": ["test"],
    }
    errors, _ = engine._guard_manifest(manifest)
    joined = "\n".join(errors)
    assert "executor constraint violation" not in joined


def test_guard_rejects_dockerfile_parse_hazard_unknown_instruction(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    manifest = {
        "files": [
            {
                "path": "Dockerfile",
                "role": "helper",
                "content": (
                    "FROM python:3.11-slim\n"
                    "WORKDIR /app\n"
                    "COPY . /app\n"
                    "RUN echo ok\n"
                    "if echo spilled\n"
                ),
            },
            {
                "path": "app.py",
                "role": "service_main",
                "content": "print('ok')\n",
            },
            {"path": "poc.py", "role": "poc_entry", "content": "print('Exploit SUCCESS')\n"},
        ],
        "deps": [],
        "poc": {"cmd": "python poc.py --base-url {{base_url}}", "success_signature": "Exploit SUCCESS"},
        "pattern_tags": ["test"],
    }
    errors, _ = engine._guard_manifest(manifest)
    joined = "\n".join(errors)
    assert "Dockerfile syntax risk" in joined
    assert "unknown instruction 'IF'" in joined


def test_guard_rejects_build_time_tmp_db_artifact_in_dockerfile(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    manifest = {
        "files": [
            {
                "path": "Dockerfile",
                "role": "helper",
                "content": (
                    "FROM python:3.11-slim\n"
                    "WORKDIR /app\n"
                    "COPY . /app\n"
                    "RUN python -c \"import sqlite3; sqlite3.connect('/tmp/app.db').close()\"\n"
                    "CMD [\"python\", \"app.py\"]\n"
                ),
            },
            {
                "path": "app.py",
                "role": "service_main",
                "content": "print('ok')\n",
            },
            {"path": "poc.py", "role": "poc_entry", "content": "print('Exploit SUCCESS')\n"},
        ],
        "deps": [],
        "poc": {"cmd": "python poc.py --base-url {{base_url}}", "success_signature": "Exploit SUCCESS"},
        "pattern_tags": ["test"],
    }
    errors, _ = engine._guard_manifest(manifest)
    joined = "\n".join(errors)
    assert "Dockerfile appears to create DB artifacts under /tmp" in joined
