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


class _SequentialManifestLLM:
    def __init__(self, manifest: dict) -> None:
        self._manifest = json.dumps(manifest, ensure_ascii=False)
        self.prompts: list[str] = []
        self.fixture_used = False
        self.last_used_stub = False
        self.last_provider_attempted = False
        self.last_provider_succeeded = True
        self.last_error_class = ""
        self.last_error_message = ""

    def generate(self, messages, *, tools=None) -> str:
        self.prompts.append(messages[-1]["content"])
        return self._manifest


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
        "run": {
            "command": "python app.py",
            "port": 8000,
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
    assert "ap.add_argument('--base-url', default='http://127.0.0.1:5000')" not in poc_content
    assert "ap.add_argument('--base-url', default='http://127.0.0.1:8000')" in poc_content
    assert "ARITH_RE = re.compile" in poc_content
    assert "expected = _expected_marker(args.payload)" in poc_content
    assert "print(expected)" in poc_content
    assert updated["poc"]["success_signature"] == "OK: arithmetic marker present"
    assert updated["poc"]["flag_token"] == "SSTI_OK"
    assert any(dep.startswith("requests") for dep in (updated.get("deps") or []))
    req_entry = next(entry for entry in updated["files"] if entry.get("path") == "requirements.txt")
    assert "requests" in req_entry["content"]


def test_template_injection_stabilizer_keeps_payload_placeholder_when_verification_spec_has_payloads(
    tmp_path: Path,
) -> None:
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
                    "@app.get('/render')\n"
                    "def render():\n"
                    "    name = request.args.get('name', '')\n"
                    "    return render_template_string('<h1>Hello ' + name + '</h1>')\n"
                ),
            }
        ],
        "poc": {
            "cmd": "python poc.py --base-url {{base_url}}",
            "success_signature": "Exploit SUCCESS",
            "flag_token": "FLAG{SSTI_OK}",
        },
        "verification_spec": {
            "negative_controls": [{"name": "plain-name", "expect_success": False, "payload": "friend"}],
            "metamorphic": {"cases": [{"name": "alt-arith", "expect_success": True, "payload": "{{6*7}}"}]},
        },
    }

    updated = engine._stabilize_pattern_specific_artifacts(manifest, manifest["poc"])  # type: ignore[attr-defined]

    assert updated["poc"]["cmd"] == "python poc.py --base-url {{base_url}} --payload {{payload}}"


def test_write_records_persists_generation_provenance(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine._guard_spec_payload = {}  # type: ignore[attr-defined]
    engine._guard_engine = None  # type: ignore[attr-defined]
    engine._user_deps = []  # type: ignore[attr-defined]
    engine._requirement = {  # type: ignore[attr-defined]
        "staged_synthesis": {
            "schema_version": "staged_synthesis@0.1",
            "stage_order": ["candidate_resolution", "design_brief", "runtime_plan", "oracle_contract"],
            "runtime_plan": {"topology": "single_service"},
        }
    }
    engine._llm_prompt_invocations = {"synthesis_manifest": 1, "guard_autofix": 1}  # type: ignore[attr-defined]
    engine._retry_budget_context = {  # type: ignore[attr-defined]
        "controller_loop_current": 2,
        "controller_loop_max": 3,
        "single_attempt_mode": True,
        "planned_candidate_budget": 1,
    }
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
        failure_stage="runtime_plan",
        failure_stage_reason="runtime_plan_mismatch",
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
    assert manifest["llm_execution"]["path_class"] == "stub"
    assert manifest["llm_execution"]["stub_fallback"] is True
    assert manifest["llm_execution"]["cache_mode"] == "none"
    assert manifest["llm_execution"]["retry_budget"]["candidate_budget"] == 1
    assert manifest["llm_execution"]["retry_budget"]["guard_autofix_max_attempts"] == 0
    assert manifest["llm_execution"]["retry_budget"]["controller_loop_current"] == 2
    assert manifest["llm_execution"]["retry_budget"]["controller_loop_max"] == 3
    assert manifest["llm_execution"]["retry_budget"]["single_attempt_mode"] is True
    assert manifest["llm_execution"]["retry_budget"]["actual_candidate_runs"] == 1
    assert manifest["llm_execution"]["retry_budget"]["actual_guard_autofix_runs"] == 1
    assert manifest["llm_execution"]["prompt_contracts"][0]["name"] == "synthesis_manifest"
    assert manifest["llm_execution"]["prompt_contracts"][1]["name"] == "guard_autofix"
    assert manifest["provenance"]["generation_origin"] == "deterministic_fallback"
    assert manifest["provenance"]["llm_execution"]["path_class"] == "stub"
    assert manifest["failure_stage"] == "runtime_plan"
    assert manifest["failure_stage_reason"] == "runtime_plan_mismatch"
    assert manifest["staged_synthesis"]["runtime_plan"]["topology"] == "single_service"


def test_record_guard_failure_persists_failure_path_provenance(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine._requirement = {  # type: ignore[attr-defined]
        "vuln_id": "CWE-89",
        "staged_synthesis": {
            "schema_version": "staged_synthesis@0.1",
            "stage_order": ["candidate_resolution", "design_brief", "runtime_plan", "oracle_contract"],
            "runtime_plan": {"topology": "single_service"},
        },
    }
    engine._llm_prompt_invocations = {"synthesis_manifest": 1, "guard_autofix": 1}  # type: ignore[attr-defined]
    engine._retry_budget_context = {  # type: ignore[attr-defined]
        "controller_loop_current": 2,
        "controller_loop_max": 3,
        "single_attempt_mode": True,
    }
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
        failure_stage="design_brief",
        failure_stage_reason="design_brief_mismatch",
    )

    engine._record_guard_failure([report])  # type: ignore[attr-defined]

    failure_path = tmp_path / "metadata" / "generator_failures.jsonl"
    payload = json.loads(failure_path.read_text(encoding="utf-8").strip())
    assert payload["llm_stub_used"] is True
    assert payload["fallback_used"] is True
    assert payload["family_override_applied"] is False
    assert payload["llm_failure_class"] == "quota_exhausted"
    assert payload["llm_execution"]["path_class"] == "stub"
    assert payload["llm_execution"]["last_error_class"] == "quota_exhausted"
    assert payload["llm_execution"]["cache_mode"] == "none"
    assert payload["llm_execution"]["prompt_contracts"][0]["version"] == "build_synthesis_prompt@1"
    assert payload["llm_execution"]["prompt_invocations"]["guard_autofix"] == 1
    assert payload["failure_stage"] == "design_brief"
    assert payload["failure_stage_reason"] == "design_brief_mismatch"
    assert payload["staged_synthesis"]["runtime_plan"]["topology"] == "single_service"


def test_classify_staged_failure_prefers_runtime_plan_for_runtime_constraints(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine._requirement = {  # type: ignore[attr-defined]
        "staged_synthesis": {
            "schema_version": "staged_synthesis@0.1",
            "stage_order": ["candidate_resolution", "design_brief", "runtime_plan", "oracle_contract"],
            "runtime_plan": {"topology": "single_service", "db": "sqlite"},
        }
    }

    failure = engine._classify_staged_failure(  # type: ignore[attr-defined]
        ["executor constraint violation: read-only runtime requires sqlite db under /tmp"]
    )

    assert failure["failure_stage"] == "runtime_plan"
    assert failure["failure_stage_reason"] == "runtime_plan_mismatch"
    assert failure["stage_contract"]["topology"] == "single_service"


def test_guard_design_brief_alignment_requires_db_signal(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine._requirement = {  # type: ignore[attr-defined]
        "vuln_id": "NAME-CUSTOM-WEIRD-VULN",
        "staged_synthesis": {
            "schema_version": "staged_synthesis@0.1",
            "stage_order": ["candidate_resolution", "design_brief", "runtime_plan", "oracle_contract"],
            "design_brief": {
                "required_roles": ["service_main", "poc_entry", "dependency_db"],
            },
            "runtime_plan": {"topology": "single_service"},
        },
    }
    manifest = {
        "files": [
            {"path": "Dockerfile", "role": "helper", "content": "FROM python:3.11-slim\n"},
            {"path": "app.py", "role": "service_main", "content": "print('hello')\n"},
            {"path": "poc.py", "role": "poc_entry", "content": "print('Exploit SUCCESS')\n"},
        ],
        "deps": ["Flask==3.0.0"],
        "build": {"command": "pip install -r requirements.txt"},
        "poc": {"cmd": "python poc.py --base-url {{base_url}}", "success_signature": "Exploit SUCCESS"},
        "pattern_tags": ["custom"],
    }

    violations, _ = engine._guard_manifest_with_autofix(manifest)  # type: ignore[attr-defined]

    assert (
        "executor constraint violation: design_brief requires dependency_db but manifest lacks DB/runtime dependency signals"
        in violations
    )
    failure = engine._classify_staged_failure(violations)  # type: ignore[attr-defined]
    assert failure["failure_stage"] == "runtime_plan"


def test_guard_design_brief_alignment_accepts_sqlite_runtime_signal(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine._requirement = {  # type: ignore[attr-defined]
        "vuln_id": "NAME-CUSTOM-WEIRD-VULN",
        "staged_synthesis": {
            "schema_version": "staged_synthesis@0.1",
            "stage_order": ["candidate_resolution", "design_brief", "runtime_plan", "oracle_contract"],
            "design_brief": {
                "required_roles": ["service_main", "poc_entry", "dependency_db"],
            },
        },
    }
    manifest = {
        "files": [
            {"path": "Dockerfile", "role": "helper", "content": "FROM python:3.11-slim\n"},
            {
                "path": "app.py",
                "role": "service_main",
                "content": "import sqlite3\nconn = sqlite3.connect('/tmp/app.db')\nprint('hello')\n",
            },
            {"path": "poc.py", "role": "poc_entry", "content": "print('Exploit SUCCESS')\n"},
        ],
        "deps": ["Flask==3.0.0"],
        "build": {"command": "pip install -r requirements.txt"},
        "poc": {"cmd": "python poc.py --base-url {{base_url}}", "success_signature": "Exploit SUCCESS"},
        "pattern_tags": ["custom"],
    }

    violations, _ = engine._guard_manifest_with_autofix(manifest)  # type: ignore[attr-defined]

    assert not any("design_brief requires dependency_db" in item for item in violations)


def test_failure_context_for_candidate_appends_stage_aware_retry_hint(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine._requirement = {  # type: ignore[attr-defined]
        "staged_synthesis": {
            "schema_version": "staged_synthesis@0.1",
            "stage_order": ["candidate_resolution", "design_brief", "runtime_plan", "oracle_contract"],
            "runtime_plan": {"topology": "single_service", "db": "sqlite"},
        }
    }
    report = CandidateReport(
        index=1,
        manifest={},
        raw_response="{}",
        violations=["executor constraint violation: read-only runtime requires sqlite db under /tmp"],
        score=0.0,
        static_report={},
        failure_stage="runtime_plan",
        failure_stage_reason="runtime_plan_mismatch",
    )

    failure_context = engine._failure_context_for_candidate(  # type: ignore[attr-defined]
        base_failure_context="previous failure context",
        reports=[report],
    )

    assert "previous failure context" in failure_context
    assert "# Stage-Aware Retry Hint" in failure_context
    assert "Previous candidate failed at staged_synthesis `runtime_plan`." in failure_context
    assert "runtime_plan_mismatch" in failure_context
    assert '"topology": "single_service"' in failure_context


def test_run_uses_stage_aware_retry_context_on_later_candidates(tmp_path: Path) -> None:
    manifest = {
        "files": [
            {"path": "app.py", "role": "service_main", "content": "print('app')\n"},
            {"path": "poc.py", "role": "poc_entry", "content": "print('poc')\n"},
        ],
        "deps": [],
        "build": {"dockerfile": "FROM python:3.11-slim"},
        "run": {"command": "python app.py", "port": 8000},
        "poc": {"cmd": "python poc.py --base-url {{base_url}}", "success_signature": "Exploit SUCCESS"},
        "notes": "minimal manifest",
        "pattern_tags": [],
    }
    llm = _SequentialManifestLLM(manifest)
    engine = SynthesisEngine(
        sid="sid-test",
        llm=llm,
        limits=SynthesisLimits(),
        workspace=tmp_path / "workspace",
        metadata_dir=tmp_path / "metadata",
        mode="synthesis",
    )
    engine._materialize = lambda manifest: []  # type: ignore[attr-defined]
    engine._write_records = lambda *args, **kwargs: None  # type: ignore[attr-defined]
    engine._write_candidate_log = lambda reports: None  # type: ignore[attr-defined]
    engine._record_guard_failure = lambda reports: None  # type: ignore[attr-defined]
    engine._manifest_requires_external_db = lambda manifest: False  # type: ignore[attr-defined]
    call_state = {"count": 0}

    def _guard_manifest_with_autofix(manifest, precomputed_llm=None, auto_patch=None):
        call_state["count"] += 1
        if call_state["count"] == 1:
            return ["executor constraint violation: read-only runtime requires sqlite db under /tmp"], {}
        return [], {}

    engine._guard_manifest_with_autofix = _guard_manifest_with_autofix  # type: ignore[attr-defined]
    engine._analyze_static_signals = lambda manifest: {"score": 0.0}  # type: ignore[attr-defined]

    requirement = {
        "vuln_id": "NAME-OPEN-REDIRECT",
        "vuln_name": "Open Redirect",
        "language": "python",
        "runtime": {"python_version": "3.11"},
        "staged_synthesis": {
            "schema_version": "staged_synthesis@0.1",
            "stage_order": ["candidate_resolution", "design_brief", "runtime_plan", "oracle_contract"],
            "runtime_plan": {"topology": "single_service", "db": "sqlite"},
        },
    }

    engine.run(
        requirement=requirement,
        rag_context="",
        hints="",
        failure_context="base retry context",
        candidate_k=2,
        researcher_report="",
        guard_spec="",
        guard_spec_payload={},
    )

    assert len(llm.prompts) == 2
    assert "base retry context" in llm.prompts[0]
    assert "# Stage-Aware Retry Hint" not in llm.prompts[0]
    assert "base retry context" in llm.prompts[1]
    assert "# Stage-Aware Retry Hint" in llm.prompts[1]
    assert "Previous candidate failed at staged_synthesis `runtime_plan`." in llm.prompts[1]


def test_stage_aware_runtime_plan_recovery_uses_runtime_safe_fallback_first(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine._requirement = {  # type: ignore[attr-defined]
        "vuln_id": "NAME-OPEN-REDIRECT",
        "vuln_name": "Open Redirect",
        "policy": {"dynamic_eval": True},
        "staged_synthesis": {
            "schema_version": "staged_synthesis@0.1",
            "stage_order": ["candidate_resolution", "design_brief", "runtime_plan", "oracle_contract"],
            "runtime_plan": {"topology": "single_service", "service_port": 9001, "db": "sqlite"},
        },
    }
    report = CandidateReport(
        index=1,
        manifest={
            "files": [{"path": "app.py", "role": "service_main", "content": "print('bad runtime')\n"}],
            "poc": {"cmd": "python poc.py --base-url {{base_url}}", "success_signature": "Exploit SUCCESS"},
            "pattern_tags": [],
        },
        raw_response="{}",
        violations=["executor constraint violation: read-only runtime requires sqlite db under /tmp"],
        score=0.1,
        static_report={},
        failure_stage="runtime_plan",
        failure_stage_reason="runtime_plan_mismatch",
    )
    engine._guard_manifest_with_autofix = lambda manifest, precomputed_llm=None, auto_patch=None: ([], {})  # type: ignore[attr-defined]
    engine._analyze_static_signals = lambda manifest: {"score": 0.0}  # type: ignore[attr-defined]

    recovery = engine._stage_aware_recovery_candidate(  # type: ignore[attr-defined]
        reports=[report],
        poc_template=engine._normalize_poc_template(None),
    )

    assert recovery is not None
    assert recovery.raw_response == '{"recovery": "runtime_plan"}'
    assert recovery.manifest["run"]["port"] == 9001
    assert recovery.manifest["metadata"]["recovery_strategy"] == "runtime_plan"
    assert "runtime_plan_repair" in recovery.manifest["pattern_tags"]


def test_runtime_plan_recovery_can_fall_back_to_design_brief_dependency_targets(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine._requirement = {  # type: ignore[attr-defined]
        "vuln_id": "CWE-89",
        "vuln_name": "SQL Injection",
        "staged_synthesis": {
            "schema_version": "staged_synthesis@0.1",
            "stage_order": ["candidate_resolution", "design_brief", "runtime_plan", "oracle_contract"],
            "design_brief": {
                "selected_topology": "service_plus_sidecar",
                "dependency_set": ["service", "db:mysql"],
                "required_roles": ["service_main", "poc_entry", "dependency_db", "dependency_sidecar"],
            },
            "runtime_plan": {"service_port": 9001},
        },
    }
    report = CandidateReport(
        index=1,
        manifest={
            "files": [{"path": "app.py", "role": "service_main", "content": "print('bad runtime')\n"}],
            "poc": {"cmd": "python poc.py --base-url {{base_url}}", "success_signature": "Exploit SUCCESS"},
            "pattern_tags": [],
        },
        raw_response="{}",
        violations=["executor constraint violation: sidecar alignment missing"],
        score=0.1,
        static_report={},
        failure_stage="runtime_plan",
        failure_stage_reason="runtime_plan_mismatch",
    )
    engine._guard_manifest_with_autofix = lambda manifest, precomputed_llm=None, auto_patch=None: ([], {})  # type: ignore[attr-defined]
    engine._analyze_static_signals = lambda manifest: {"score": 0.0}  # type: ignore[attr-defined]

    recovery = engine._stage_aware_recovery_candidate(  # type: ignore[attr-defined]
        reports=[report],
        poc_template=engine._normalize_poc_template(None),
    )

    assert recovery is not None
    assert recovery.manifest["metadata"]["recovery_strategy"] == "runtime_plan"
    assert recovery.manifest["metadata"]["target_topology"] == "service_plus_sidecar"
    assert recovery.manifest["metadata"]["target_db"] == "mysql"
    assert recovery.manifest["metadata"]["target_sidecars"] == ["mysql"]


def test_stage_aware_oracle_contract_recovery_realigns_poc_markers(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine._requirement = {  # type: ignore[attr-defined]
        "vuln_id": "NAME-OPEN-REDIRECT",
        "vuln_name": "Open Redirect",
        "staged_synthesis": {
            "schema_version": "staged_synthesis@0.1",
            "stage_order": ["candidate_resolution", "design_brief", "runtime_plan", "oracle_contract"],
            "oracle_contract": {
                "success_signature": "Exploit SUCCESS",
                "flag_token": "FLAG{OPEN_REDIRECT_OK}",
                "output_mode": "auto",
                "source": "researcher_verification_spec",
            },
        },
        "exploit_oracle": {
            "success_signature": "Exploit SUCCESS",
            "flag_token": "FLAG{OPEN_REDIRECT_OK}",
            "output_mode": "auto",
        },
    }
    report = CandidateReport(
        index=1,
        manifest={
            "files": [
                {
                    "path": "app.py",
                    "role": "service_main",
                    "content": (
                        "from flask import Flask, request, redirect\n"
                        "app = Flask(__name__)\n"
                        "@app.get('/redirect')\n"
                        "def do_redirect():\n"
                        "    return redirect(request.args.get('next', '/'))\n"
                    ),
                },
                {
                    "path": "poc.py",
                    "role": "poc_entry",
                    "content": "print('WRONG')\n",
                },
            ],
            "run": {"port": 8000},
            "poc": {"cmd": "python poc.py --base-url {{base_url}}", "success_signature": "WRONG"},
            "pattern_tags": [],
        },
        raw_response="{}",
        violations=["success_signature must include 'Exploit SUCCESS'"],
        score=0.5,
        static_report={},
        failure_stage="oracle_contract",
        failure_stage_reason="oracle_contract_mismatch",
    )
    engine._guard_manifest_with_autofix = lambda manifest, precomputed_llm=None, auto_patch=None: ([], {})  # type: ignore[attr-defined]
    engine._analyze_static_signals = lambda manifest: {"score": 0.0}  # type: ignore[attr-defined]

    recovery = engine._stage_aware_recovery_candidate(  # type: ignore[attr-defined]
        reports=[report],
        poc_template=engine._normalize_poc_template(None),
    )

    assert recovery is not None
    assert recovery.raw_response == '{"recovery": "oracle_contract"}'
    assert recovery.manifest["metadata"]["recovery_strategy"] == "oracle_contract"
    assert recovery.manifest["poc"]["success_signature"] == "Exploit SUCCESS"
    assert recovery.manifest["poc"]["flag_token"] == "FLAG{OPEN_REDIRECT_OK}"
    poc_entry = next(entry for entry in recovery.manifest["files"] if entry.get("role") == "poc_entry")
    assert "Exploit SUCCESS" in poc_entry["content"]
    assert "FLAG{OPEN_REDIRECT_OK}" in poc_entry["content"]


def test_stage_aware_design_brief_dependency_recovery_prefers_runtime_plan(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine._requirement = {  # type: ignore[attr-defined]
        "vuln_id": "CWE-89",
        "vuln_name": "SQL Injection",
        "staged_synthesis": {
            "schema_version": "staged_synthesis@0.1",
            "stage_order": ["candidate_resolution", "design_brief", "runtime_plan", "oracle_contract"],
            "design_brief": {
                "selected_topology": "single_service",
                "selected_oracle_mode": "text_markers",
                "dependency_set": ["service", "db:sqlite"],
                "required_roles": ["service_main", "poc_entry", "dependency_db", "negative_control_cases"],
            },
            "runtime_plan": {"topology": "single_service", "service_port": 9001, "db": "sqlite"},
            "oracle_contract": {"success_signature": "Exploit SUCCESS"},
        },
    }
    report = CandidateReport(
        index=1,
        manifest={
            "files": [{"path": "app.py", "role": "service_main", "content": "print('bad runtime')\n"}],
            "poc": {"cmd": "python poc.py --base-url {{base_url}}", "success_signature": "Exploit SUCCESS"},
            "pattern_tags": [],
        },
        raw_response="{}",
        violations=["missing input-to-sql vulnerable flow"],
        score=0.1,
        static_report={},
        failure_stage="design_brief",
        failure_stage_reason="design_brief_mismatch",
    )
    engine._guard_manifest_with_autofix = lambda manifest, precomputed_llm=None, auto_patch=None: ([], {})  # type: ignore[attr-defined]
    engine._analyze_static_signals = lambda manifest: {"score": 0.0}  # type: ignore[attr-defined]

    recovery = engine._stage_aware_recovery_candidate(  # type: ignore[attr-defined]
        reports=[report],
        poc_template=engine._normalize_poc_template(None),
    )

    assert recovery is not None
    assert recovery.raw_response == '{"recovery": "runtime_plan"}'
    assert recovery.manifest["metadata"]["recovery_strategy"] == "runtime_plan"
    assert recovery.manifest["metadata"]["design_brief_required_roles"] == [
        "service_main",
        "poc_entry",
        "dependency_db",
        "negative_control_cases",
    ]
    assert recovery.manifest["metadata"]["design_brief_dependency_set"] == ["service", "db:sqlite"]


def test_stage_aware_design_brief_oracle_recovery_prefers_oracle_contract(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine._requirement = {  # type: ignore[attr-defined]
        "vuln_id": "NAME-OPEN-REDIRECT",
        "vuln_name": "Open Redirect",
        "staged_synthesis": {
            "schema_version": "staged_synthesis@0.1",
            "stage_order": ["candidate_resolution", "design_brief", "runtime_plan", "oracle_contract"],
            "design_brief": {
                "selected_topology": "single_service",
                "selected_oracle_mode": "stateful_text",
                "selected_oracle_source": "researcher_verification_spec",
                "dependency_set": ["service"],
                "required_roles": [
                    "service_main",
                    "poc_entry",
                    "oracle_state_checks",
                    "negative_control_cases",
                    "metamorphic_cases",
                ],
            },
            "oracle_contract": {
                "success_signature": "Exploit SUCCESS",
                "flag_token": "FLAG{OPEN_REDIRECT_OK}",
                "output_mode": "auto",
                "source": "researcher_verification_spec",
            },
        },
        "exploit_oracle": {
            "success_signature": "Exploit SUCCESS",
            "flag_token": "FLAG{OPEN_REDIRECT_OK}",
            "output_mode": "auto",
        },
    }
    report = CandidateReport(
        index=1,
        manifest={
            "files": [
                {"path": "app.py", "role": "service_main", "content": "print('app')\n"},
                {"path": "poc.py", "role": "poc_entry", "content": "print('WRONG')\n"},
            ],
            "poc": {"cmd": "python poc.py --base-url {{base_url}}", "success_signature": "WRONG"},
            "pattern_tags": [],
        },
        raw_response="{}",
        violations=["missing redirect sink and semantic mismatch"],
        score=0.1,
        static_report={},
        failure_stage="design_brief",
        failure_stage_reason="design_brief_mismatch",
    )
    engine._guard_manifest_with_autofix = lambda manifest, precomputed_llm=None, auto_patch=None: ([], {})  # type: ignore[attr-defined]
    engine._analyze_static_signals = lambda manifest: {"score": 0.0}  # type: ignore[attr-defined]

    recovery = engine._stage_aware_recovery_candidate(  # type: ignore[attr-defined]
        reports=[report],
        poc_template=engine._normalize_poc_template(None),
    )

    assert recovery is not None
    assert recovery.raw_response == '{"recovery": "oracle_contract"}'
    assert recovery.manifest["metadata"]["recovery_strategy"] == "oracle_contract"
    assert recovery.manifest["metadata"]["design_brief_oracle_mode"] == "stateful_text"
    assert recovery.manifest["metadata"]["design_brief_required_roles"] == [
        "service_main",
        "poc_entry",
        "oracle_state_checks",
        "negative_control_cases",
        "metamorphic_cases",
    ]


def test_run_prefers_stage_aware_recovery_before_semantic_guided(tmp_path: Path) -> None:
    manifest = {
        "files": [
            {"path": "app.py", "role": "service_main", "content": "print('app')\n"},
            {"path": "poc.py", "role": "poc_entry", "content": "print('poc')\n"},
        ],
        "deps": [],
        "build": {"dockerfile": "FROM python:3.11-slim"},
        "run": {"command": "python app.py", "port": 8000},
        "poc": {"cmd": "python poc.py --base-url {{base_url}}", "success_signature": "Exploit SUCCESS"},
        "notes": "minimal manifest",
        "pattern_tags": [],
    }
    llm = _SequentialManifestLLM(manifest)
    engine = SynthesisEngine(
        sid="sid-test",
        llm=llm,
        limits=SynthesisLimits(),
        workspace=tmp_path / "workspace",
        metadata_dir=tmp_path / "metadata",
        mode="synthesis",
    )
    engine._materialize = lambda manifest: []  # type: ignore[attr-defined]
    engine._write_records = lambda *args, **kwargs: None  # type: ignore[attr-defined]
    engine._write_candidate_log = lambda reports: None  # type: ignore[attr-defined]
    engine._record_guard_failure = lambda reports: None  # type: ignore[attr-defined]
    engine._manifest_requires_external_db = lambda manifest: False  # type: ignore[attr-defined]
    engine._guard_manifest_with_autofix = lambda manifest, precomputed_llm=None, auto_patch=None: (["success_signature must include 'Exploit SUCCESS'"], {})  # type: ignore[attr-defined]
    engine._analyze_static_signals = lambda manifest: {"score": 0.0}  # type: ignore[attr-defined]
    stage_recovery = CandidateReport(
        index=2,
        manifest=manifest,
        raw_response='{"recovery":"oracle_contract"}',
        violations=[],
        score=1.0,
        static_report={},
        fallback_used=True,
        fallback_class="oracle_contract",
    )
    semantic_called = {"value": False}
    engine._stage_aware_recovery_candidate = lambda reports, poc_template: stage_recovery  # type: ignore[attr-defined]
    engine._semantic_guided_recovery_candidate = lambda reports, poc_template: semantic_called.__setitem__("value", True) or None  # type: ignore[attr-defined]

    outcome = engine.run(
        requirement={
            "vuln_id": "NAME-OPEN-REDIRECT",
            "vuln_name": "Open Redirect",
            "language": "python",
            "runtime": {"python_version": "3.11"},
            "staged_synthesis": {
                "schema_version": "staged_synthesis@0.1",
                "stage_order": ["candidate_resolution", "design_brief", "runtime_plan", "oracle_contract"],
                "oracle_contract": {"success_signature": "Exploit SUCCESS"},
            },
        },
        rag_context="",
        hints="",
        failure_context="",
        candidate_k=1,
        researcher_report="",
        guard_spec="",
        guard_spec_payload={},
    )

    assert outcome.selected.raw_response == '{"recovery":"oracle_contract"}'
    assert semantic_called["value"] is False
