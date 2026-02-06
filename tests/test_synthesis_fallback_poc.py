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
    engine._requirement = {}  # type: ignore[attr-defined]
    return engine


def test_default_poc_template_includes_base_url_placeholder(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    template = engine._normalize_poc_template(None)
    assert "--base-url" in template["cmd"]
    assert "{{base_url}}" in template["cmd"]


def test_fallback_endpoint_prefers_reflect(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    manifest = {
        "files": [
            {
                "path": "app.py",
                "role": "service_main",
                "content": (
                    "from flask import Flask, request\n"
                    "app = Flask(__name__)\n"
                    "@app.get('/reflect')\n"
                    "def reflect():\n"
                    "    value = request.args.get('q', '')\n"
                    "    return f\"<p>{value}</p>\"\n"
                ),
            }
        ]
    }
    endpoint = engine._infer_fallback_endpoint(manifest)
    assert endpoint["path"] == "/reflect"
    assert endpoint["method"] == "get"
    assert endpoint["expect_reflection"] is True

    poc = engine._build_fallback_poc_content(manifest, "Exploit SUCCESS", "")
    assert "import requests" not in poc
    assert "from urllib.request import Request, urlopen" in poc
    assert "PATH = '/reflect'" in poc
    assert "EXPECT_REFLECTION = True" in poc


def test_fallback_endpoint_detects_post_route(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    manifest = {
        "files": [
            {
                "path": "app.py",
                "role": "service_main",
                "content": (
                    "from flask import Flask, request\n"
                    "app = Flask(__name__)\n"
                    "@app.post('/transfer')\n"
                    "def transfer():\n"
                    "    amount = request.form.get('amount', '0')\n"
                    "    return amount\n"
                ),
            }
        ]
    }
    endpoint = engine._infer_fallback_endpoint(manifest)
    assert endpoint["path"] == "/transfer"
    assert endpoint["method"] == "post"

    poc = engine._build_fallback_poc_content(manifest, "Exploit SUCCESS", "")
    assert "METHOD = 'post'" in poc
    assert "PATH = '/transfer'" in poc
    assert "DEFAULT_PAYLOAD = '250'" in poc


def test_ensure_fallback_poc_skips_when_poc_entry_present(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    manifest = {
        "files": [
            {
                "path": "app.py",
                "role": "service_main",
                "content": "from flask import Flask\napp = Flask(__name__)\n",
            },
            {
                "path": "poc.sh",
                "role": "poc_entry",
                "content": "#!/bin/sh\necho OK\n",
            },
        ]
    }
    template = engine._normalize_poc_template(None)
    before = len(manifest["files"])
    updated = engine._ensure_fallback_poc(manifest, template)
    assert len(updated["files"]) == before
