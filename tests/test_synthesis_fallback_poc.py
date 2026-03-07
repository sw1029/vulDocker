from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.generator.synthesis import CandidateReport, SynthesisEngine, SynthesisLimits


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


def test_template_injection_stabilizer_rewrites_poc_deterministically(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine._requirement = {  # type: ignore[attr-defined]
        "vuln_id": "NAME-TEMPLATE-INJECTION",
        "pattern_id": "template-injection",
        "vuln_name": "Template Injection",
    }
    manifest = {
        "files": [
            {
                "path": "app.py",
                "role": "service_main",
                "content": (
                    "from flask import Flask, request, render_template_string\n"
                    "app = Flask(__name__)\n"
                    "@app.get('/greet')\n"
                    "def greet():\n"
                    "    name = request.args.get('name', '')\n"
                    "    template = f'<h1>Hello {name}</h1>'\n"
                    "    return render_template_string(template)\n"
                ),
            },
            {
                "path": "poc.py",
                "role": "poc_entry",
                "content": (
                    "FLAG_TOKEN='SSTI_OK'\n"
                    "default=f\"{FLAG_TOKEN} {{\\u007b\\u007b7*7\\u007d\\u007d}\"\n"
                ),
            },
        ],
        "poc": {
            "cmd": "python poc.py --base-url {{base_url}}",
            "success_signature": "OK: arithmetic marker present",
            "flag_token": "SSTI_OK",
        },
    }
    template = {
        "cmd": "python poc.py --base-url {{base_url}}",
        "success_signature": "OK: arithmetic marker present",
        "flag_token": "SSTI_OK",
    }

    updated = engine._stabilize_pattern_specific_artifacts(manifest, template)  # type: ignore[attr-defined]

    poc_entry = next(entry for entry in updated["files"] if entry.get("path") == "poc.py")
    poc_content = poc_entry["content"]
    ast.parse(poc_content)
    assert "DEFAULT_PAYLOAD = 'SSTI_OK {{7*7}}'" in poc_content
    assert "ROUTE_CANDIDATES = ['/greet', '/display_name', '/hello', '/']" in poc_content
    assert "print('49')" in poc_content
    assert updated["poc"]["success_signature"] == "OK: arithmetic marker present"
    assert updated["poc"]["flag_token"] == "SSTI_OK"
    assert any(dep.startswith("requests") for dep in (updated.get("deps") or []))
    req_entry = next(entry for entry in updated["files"] if entry.get("path") == "requirements.txt")
    assert "requests" in req_entry["content"]


def test_write_records_persists_generation_provenance(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine._guard_spec_payload = {}  # type: ignore[attr-defined]
    engine._guard_engine = None  # type: ignore[attr-defined]
    engine._user_deps = []  # type: ignore[attr-defined]
    selected = CandidateReport(
        index=1,
        manifest={
            "files": [
                {"path": "app.py", "role": "service_main", "content": "print('app')\n"},
                {"path": "poc.py", "role": "poc_entry", "content": "print('poc')\n"},
            ],
            "pattern_tags": ["fallback", "stub", "cwe-89"],
        },
        raw_response="[llm-stub-synthesis]",
        violations=[],
        score=1.0,
        static_report={},
        fallback_used=True,
        family_override_applied=False,
        llm_stub_used=True,
        llm_failure_class="quota_exhausted",
        llm_failure_message="rate limit",
    )

    engine._write_records(  # type: ignore[attr-defined]
        selected,
        [selected],
        hints="",
        rag_context="",
        failure_context="",
        requires_external_db=False,
    )

    manifest = json.loads((tmp_path / "metadata" / "generator_manifest.json").read_text(encoding="utf-8"))
    assert manifest["generation_origin"] == "deterministic_fallback"
    assert manifest["fallback_used"] is True
    assert manifest["family_override_applied"] is False
    assert manifest["llm_stub_used"] is True
    assert manifest["llm_failure_class"] == "quota_exhausted"
    assert manifest["provenance"]["generation_origin"] == "deterministic_fallback"


def test_record_guard_failure_persists_failure_path_provenance(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine._requirement = {"vuln_id": "CWE-89"}  # type: ignore[attr-defined]
    report = CandidateReport(
        index=1,
        manifest={"files": [{"path": "app.py", "role": "service_main", "content": "print('x')\n"}]},
        raw_response="[llm-stub-synthesis]",
        violations=["semantic mismatch"],
        score=0.0,
        static_report={},
        guard_report={"errors": ["semantic mismatch"]},
        fallback_used=True,
        family_override_applied=False,
        llm_stub_used=True,
        llm_failure_class="quota_exhausted",
        llm_failure_message="rate limit",
    )

    engine._record_guard_failure([report])  # type: ignore[attr-defined]

    failure_path = tmp_path / "metadata" / "generator_failures.jsonl"
    payload = json.loads(failure_path.read_text(encoding="utf-8").strip())
    assert payload["llm_stub_used"] is True
    assert payload["fallback_used"] is True
    assert payload["family_override_applied"] is False
    assert payload["llm_failure_class"] == "quota_exhausted"
