from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.contracts import write_generator_contract
from common.rules import list_rules, load_rule
from evals.poc_verifier.registry import evaluate_with_vuln
from evals.poc_verifier.rule_based import verify_with_rule


def test_unknown_rule_based_verifier_uses_resolved_contract_semantic_contract(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path
    metadata_dir = repo_root / "metadata" / "sid-semantic"
    workspace_dir = repo_root / "workspaces" / "sid-semantic" / "app"
    run_dir = repo_root / "artifacts" / "sid-semantic" / "run"
    metadata_dir.mkdir(parents=True)
    workspace_dir.mkdir(parents=True)
    run_dir.mkdir(parents=True)

    app_text = (
        "from flask import Flask, request\n"
        "import sqlite3\n"
        "app = Flask(__name__)\n"
        "@app.get('/users')\n"
        "def users():\n"
        "    user_id = request.args.get('id', '1')\n"
        "    query = 'SELECT * FROM users WHERE id=' + user_id\n"
        "    conn = sqlite3.connect('/tmp/app.db')\n"
        "    conn.execute(query)\n"
        "    return 'ok'\n"
    )
    (workspace_dir / "app.py").write_text(app_text, encoding="utf-8")
    (workspace_dir / "poc.py").write_text("print('Exploit SUCCESS')\n", encoding="utf-8")
    (run_dir / "run.log").write_text("Exploit SUCCESS\n", encoding="utf-8")

    manifest = {
        "manifest": {
            "files": [
                {"path": "app.py", "role": "service_main", "content": app_text},
                {"path": "poc.py", "role": "poc_entry", "content": "print('Exploit SUCCESS')\n"},
            ],
            "poc": {"success_signature": "Exploit SUCCESS"},
        },
    }
    (metadata_dir / "generator_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    write_generator_contract(
        metadata_dir,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": "sid-semantic",
            "slug": "cwe-9999",
            "vuln_id": "CWE-9999",
            "success_signature": "Exploit SUCCESS",
            "service_entry": "app.py",
            "poc_entry": "poc.py",
            "service_port": 5000,
            "base_url": "http://127.0.0.1:5000",
            "output_mode": "auto",
            "semantic_contract": {
                "semantic_signature": {
                    "input_vector": ["user-controlled request parameter"],
                    "sink": ["SQL query execution"],
                    "exploit_precondition": ["input concatenated/interpolated into SQL sink"],
                },
                "semantic_signature_source": ["contract"],
            },
        },
    )

    monkeypatch.setattr("evals.poc_verifier.rule_based.REPO_ROOT", repo_root)
    monkeypatch.setattr("evals.poc_verifier.rule_based.WORKSPACES_ROOT", repo_root / "workspaces")

    result = verify_with_rule(
        "CWE-9999",
        run_dir / "run.log",
        run_summary={"sid": "sid-semantic", "slug": "cwe-9999", "exit_code": 0},
        policy={"require_exit_code_zero": True},
    )

    assert result["verify_pass"] is True
    assert result["semantic_consistency"]["supported"] is True
    assert result["semantic_consistency"]["semantic_match"] is True
    assert result["semantic_consistency"]["source"] == "resolved_contract.semantic_contract"
    assert result["verification_rule_source"] == "generator_manifest_fallback"
    assert result["verification_trust"] == "low"


def test_rule_based_verifier_fails_closed_when_unknown_contract_status_is_empty(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path
    sid = "sid-semantic-empty"
    slug = "cwe-9999"
    metadata_dir = repo_root / "metadata" / sid
    workspace_dir = repo_root / "workspaces" / sid / "app"
    run_dir = repo_root / "artifacts" / sid / "run"
    metadata_dir.mkdir(parents=True)
    workspace_dir.mkdir(parents=True)
    run_dir.mkdir(parents=True)

    app_text = (
        "from flask import Flask, request\n"
        "import sqlite3\n"
        "app = Flask(__name__)\n"
        "@app.get('/users')\n"
        "def users():\n"
        "    user_id = request.args.get('id', '1')\n"
        "    query = 'SELECT * FROM users WHERE id=' + user_id\n"
        "    conn = sqlite3.connect('/tmp/app.db')\n"
        "    conn.execute(query)\n"
        "    return 'ok'\n"
    )
    (workspace_dir / "app.py").write_text(app_text, encoding="utf-8")
    (workspace_dir / "poc.py").write_text("print('Exploit SUCCESS')\n", encoding="utf-8")
    (run_dir / "run.log").write_text("Exploit SUCCESS\n", encoding="utf-8")

    (metadata_dir / "generator_manifest.json").write_text(
        json.dumps(
            {
                "manifest": {
                    "files": [
                        {"path": "app.py", "role": "service_main", "content": app_text},
                        {"path": "poc.py", "role": "poc_entry", "content": "print('Exploit SUCCESS')\n"},
                    ],
                    "poc": {"success_signature": "Exploit SUCCESS"},
                },
            }
        ),
        encoding="utf-8",
    )
    write_generator_contract(
        metadata_dir,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": sid,
            "slug": slug,
            "vuln_id": "CWE-9999",
            "success_signature": "Exploit SUCCESS",
            "service_entry": "app.py",
            "poc_entry": "poc.py",
            "service_port": 5000,
            "base_url": "http://127.0.0.1:5000",
            "output_mode": "auto",
            "semantic_contract": {
                "semantic_signature": {
                    "input_vector": ["request.args"],
                    "sink": ["execute("],
                    "exploit_precondition": ["string concatenation"],
                },
                "semantic_signature_source": ["heuristic"],
                "status": "empty",
            },
        },
    )

    monkeypatch.setattr("evals.poc_verifier.rule_based.REPO_ROOT", repo_root)
    monkeypatch.setattr("evals.poc_verifier.rule_based.WORKSPACES_ROOT", repo_root / "workspaces")

    result = verify_with_rule(
        "CWE-9999",
        run_dir / "run.log",
        run_summary={"sid": sid, "slug": slug, "exit_code": 0},
        policy={"require_exit_code_zero": True},
    )

    assert result["exploit_pass"] is True
    assert result["semantic_supported"] is False
    assert result["semantic_status"] == "empty"
    assert result["verify_pass"] is False


def test_rule_based_verifier_can_fail_closed_on_low_trust_unknown_policy(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path
    metadata_dir = repo_root / "metadata" / "sid-low-trust-policy"
    workspace_dir = repo_root / "workspaces" / "sid-low-trust-policy" / "app"
    run_dir = repo_root / "artifacts" / "sid-low-trust-policy" / "run"
    metadata_dir.mkdir(parents=True)
    workspace_dir.mkdir(parents=True)
    run_dir.mkdir(parents=True)

    app_text = (
        "from flask import Flask, request\n"
        "import sqlite3\n"
        "app = Flask(__name__)\n"
        "@app.get('/users')\n"
        "def users():\n"
        "    user_id = request.args.get('id', '1')\n"
        "    query = 'SELECT * FROM users WHERE id=' + user_id\n"
        "    conn = sqlite3.connect('/tmp/app.db')\n"
        "    conn.execute(query)\n"
        "    return 'ok'\n"
    )
    (workspace_dir / "app.py").write_text(app_text, encoding="utf-8")
    (workspace_dir / "poc.py").write_text("print('Exploit SUCCESS')\n", encoding="utf-8")
    (run_dir / "run.log").write_text("Exploit SUCCESS\n", encoding="utf-8")
    (metadata_dir / "generator_manifest.json").write_text(
        json.dumps(
            {
                "manifest": {
                    "files": [
                        {"path": "app.py", "role": "service_main", "content": app_text},
                        {"path": "poc.py", "role": "poc_entry", "content": "print('Exploit SUCCESS')\n"},
                    ],
                    "poc": {"success_signature": "Exploit SUCCESS"},
                }
            }
        ),
        encoding="utf-8",
    )
    write_generator_contract(
        metadata_dir,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": "sid-low-trust-policy",
            "slug": "cwe-9999",
            "vuln_id": "CWE-9999",
            "success_signature": "Exploit SUCCESS",
            "service_entry": "app.py",
            "poc_entry": "poc.py",
            "service_port": 5000,
            "base_url": "http://127.0.0.1:5000",
            "output_mode": "auto",
            "semantic_contract": {
                "semantic_signature": {
                    "input_vector": ["user-controlled request parameter"],
                    "sink": ["SQL query execution"],
                    "exploit_precondition": ["input concatenated/interpolated into SQL sink"],
                },
                "semantic_signature_source": ["contract"],
                "status": "aligned",
            },
        },
    )

    monkeypatch.setattr("evals.poc_verifier.rule_based.REPO_ROOT", repo_root)
    monkeypatch.setattr("evals.poc_verifier.rule_based.WORKSPACES_ROOT", repo_root / "workspaces")

    result = verify_with_rule(
        "CWE-9999",
        run_dir / "run.log",
        run_summary={"sid": "sid-low-trust-policy", "slug": "cwe-9999", "exit_code": 0},
        policy={"require_exit_code_zero": True, "low_trust_unknown_policy": "fail_closed"},
    )

    assert result["exploit_pass"] is True
    assert result["semantic_supported"] is True
    assert result["verify_pass"] is False
    assert result["verification_rule_source"] == "generator_manifest_fallback"
    assert result["verification_trust"] == "low"
    assert result["verification_policy_blocked"] is True
    assert result["terminal_failure_class"] == "low_trust_verification"
    assert "low-trust verifier contract blocked by policy" in result["evidence"]


def test_evaluate_with_vuln_does_not_invoke_llm_after_low_trust_policy_block(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path
    metadata_dir = repo_root / "metadata" / "sid-low-trust-registry"
    workspace_dir = repo_root / "workspaces" / "sid-low-trust-registry" / "app"
    run_dir = repo_root / "artifacts" / "sid-low-trust-registry" / "run"
    metadata_dir.mkdir(parents=True)
    workspace_dir.mkdir(parents=True)
    run_dir.mkdir(parents=True)

    app_text = (
        "from flask import Flask, request\n"
        "import sqlite3\n"
        "app = Flask(__name__)\n"
        "@app.get('/users')\n"
        "def users():\n"
        "    user_id = request.args.get('id', '1')\n"
        "    query = 'SELECT * FROM users WHERE id=' + user_id\n"
        "    conn = sqlite3.connect('/tmp/app.db')\n"
        "    conn.execute(query)\n"
        "    return 'ok'\n"
    )
    (workspace_dir / "app.py").write_text(app_text, encoding="utf-8")
    (workspace_dir / "poc.py").write_text("print('Exploit SUCCESS')\n", encoding="utf-8")
    (run_dir / "run.log").write_text("Exploit SUCCESS\n", encoding="utf-8")
    (metadata_dir / "generator_manifest.json").write_text(
        json.dumps(
            {
                "manifest": {
                    "files": [
                        {"path": "app.py", "role": "service_main", "content": app_text},
                        {"path": "poc.py", "role": "poc_entry", "content": "print('Exploit SUCCESS')\n"},
                    ],
                    "poc": {"success_signature": "Exploit SUCCESS"},
                }
            }
        ),
        encoding="utf-8",
    )
    write_generator_contract(
        metadata_dir,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": "sid-low-trust-registry",
            "slug": "cwe-9999",
            "vuln_id": "CWE-9999",
            "success_signature": "Exploit SUCCESS",
            "service_entry": "app.py",
            "poc_entry": "poc.py",
            "service_port": 5000,
            "base_url": "http://127.0.0.1:5000",
            "output_mode": "auto",
            "semantic_contract": {
                "semantic_signature": {
                    "input_vector": ["user-controlled request parameter"],
                    "sink": ["SQL query execution"],
                    "exploit_precondition": ["input concatenated/interpolated into SQL sink"],
                },
                "semantic_signature_source": ["contract"],
                "status": "aligned",
            },
        },
    )

    monkeypatch.setattr("evals.poc_verifier.rule_based.REPO_ROOT", repo_root)
    monkeypatch.setattr("evals.poc_verifier.rule_based.WORKSPACES_ROOT", repo_root / "workspaces")
    monkeypatch.setattr(
        "evals.poc_verifier.registry.llm_assisted_verify",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("llm_assisted_verify should not run")),
    )

    result = evaluate_with_vuln(
        "CWE-9999",
        run_dir / "run.log",
        run_summary={"sid": "sid-low-trust-registry", "slug": "cwe-9999", "exit_code": 0},
        plan_policy={"verifier": {"prefer_rule": True, "require_exit_code_zero": True, "low_trust_unknown_policy": "fail_closed"}},
    )

    assert result["verify_pass"] is False
    assert result["verification_policy_blocked"] is True
    assert result["verification_trust"] == "low"
    assert result["terminal_failure_class"] == "low_trust_verification"


def test_rule_based_verifier_fails_when_semantic_contract_has_contradictions(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path
    metadata_dir = repo_root / "metadata" / "sid-semantic-bad"
    workspace_dir = repo_root / "workspaces" / "sid-semantic-bad" / "app"
    run_dir = repo_root / "artifacts" / "sid-semantic-bad" / "run"
    metadata_dir.mkdir(parents=True)
    workspace_dir.mkdir(parents=True)
    run_dir.mkdir(parents=True)

    app_text = "from flask import Flask\napp = Flask(__name__)\n"
    (workspace_dir / "app.py").write_text(app_text, encoding="utf-8")
    (workspace_dir / "poc.py").write_text("print('SQLi SUCCESS')\nprint('FLAG-sqli-demo-token')\n", encoding="utf-8")
    (run_dir / "run.log").write_text("SQLi SUCCESS\nFLAG-sqli-demo-token\n", encoding="utf-8")

    write_generator_contract(
        metadata_dir,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": "sid-semantic-bad",
            "slug": "cwe-89",
            "vuln_id": "CWE-89",
            "success_signature": "SQLi SUCCESS",
            "flag_token": "FLAG-sqli-demo-token",
            "service_entry": "app.py",
            "poc_entry": "poc.py",
            "service_port": 5000,
            "base_url": "http://127.0.0.1:5000",
            "output_mode": "auto",
            "semantic_contract": {
                "semantic_signature": {
                    "input_vector": ["cross-site request"],
                    "sink": ["state-changing endpoint (POST/PUT/DELETE/PATCH)"],
                    "exploit_precondition": ["missing CSRF token validation"],
                },
                "contradictions": ["semantic_contract sink conflicts with baseline CWE-89 semantics"],
                "status": "contradicted",
            },
        },
    )

    monkeypatch.setattr("evals.poc_verifier.rule_based.REPO_ROOT", repo_root)
    monkeypatch.setattr("evals.poc_verifier.rule_based.WORKSPACES_ROOT", repo_root / "workspaces")

    result = verify_with_rule(
        "CWE-89",
        run_dir / "run.log",
        run_summary={"sid": "sid-semantic-bad", "slug": "cwe-89", "exit_code": 0},
        policy={"require_exit_code_zero": True},
    )

    assert result["verify_pass"] is False
    assert result["semantic_consistency"]["supported"] is True
    assert result["semantic_consistency"]["semantic_match"] is False
    assert any(
        "baseline" in item or "semantic_contract" in item
        for item in result["semantic_consistency"]["errors"]
    )


def test_rule_based_verifier_fails_when_guard_consistency_blocks(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path
    metadata_dir = repo_root / "metadata" / "sid-guard-bad"
    workspace_dir = repo_root / "workspaces" / "sid-guard-bad" / "app"
    run_dir = repo_root / "artifacts" / "sid-guard-bad" / "run"
    metadata_dir.mkdir(parents=True)
    workspace_dir.mkdir(parents=True)
    run_dir.mkdir(parents=True)

    app_text = "from flask import Flask\napp = Flask(__name__)\n"
    (workspace_dir / "app.py").write_text(app_text, encoding="utf-8")
    (workspace_dir / "poc.py").write_text("print('Exploit SUCCESS')\n", encoding="utf-8")
    (run_dir / "run.log").write_text("Exploit SUCCESS\n", encoding="utf-8")

    manifest = {
        "manifest": {
            "files": [
                {"path": "app.py", "role": "service_main", "content": app_text},
                {"path": "poc.py", "role": "poc_entry", "content": "print('Exploit SUCCESS')\n"},
            ],
            "poc": {"success_signature": "Exploit SUCCESS"},
        },
    }
    (metadata_dir / "generator_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    monkeypatch.setattr("evals.poc_verifier.rule_based.REPO_ROOT", repo_root)
    monkeypatch.setattr("evals.poc_verifier.rule_based.WORKSPACES_ROOT", repo_root / "workspaces")
    monkeypatch.setattr(
        "evals.poc_verifier.rule_based._evaluate_guard_consistency",
        lambda **kwargs: {
            "available": True,
            "required_but_missing": False,
            "verifier": {
                "passed": False,
                "blocking": True,
                "violations": ["verifier assertion failed (contains): substring=missing: expected marker"],
            },
            "workspace": {"passed": True, "blocking": False, "violations": []},
        },
    )

    result = verify_with_rule(
        "CWE-9999",
        run_dir / "run.log",
        run_summary={"sid": "sid-guard-bad", "slug": "cwe-9999", "exit_code": 0},
        policy={"require_exit_code_zero": True},
    )

    assert result["verify_pass"] is False
    assert result["guard_pass"] is False
    assert "guard mismatch:" in result["evidence"]


def test_freeform_name_rule_based_verifier_fails_closed_when_semantic_support_is_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path
    sid = "sid-open-redirect"
    slug = "name-open-redirect"
    metadata_dir = repo_root / "metadata" / sid
    workspace_dir = repo_root / "workspaces" / sid / "app"
    run_dir = repo_root / "artifacts" / sid / "run"
    metadata_dir.mkdir(parents=True)
    workspace_dir.mkdir(parents=True)
    run_dir.mkdir(parents=True)

    app_text = (
        "from flask import Flask, request\n"
        "app = Flask(__name__)\n"
        "@app.get('/reflect')\n"
        "def reflect():\n"
        "    value = request.args.get('q', '')\n"
        "    return f'<p>{value}</p>'\n"
    )
    (workspace_dir / "app.py").write_text(app_text, encoding="utf-8")
    (workspace_dir / "poc.py").write_text("print('Exploit SUCCESS')\n", encoding="utf-8")
    (run_dir / "run.log").write_text("Exploit SUCCESS\n", encoding="utf-8")
    (metadata_dir / "generator_manifest.json").write_text(
        json.dumps(
            {
                "generation_origin": "deterministic_fallback",
                "fallback_used": True,
                "fallback_class": "generic_unsupported_family",
                "manifest": {
                    "files": [
                        {"path": "app.py", "role": "service_main", "content": app_text},
                        {"path": "poc.py", "role": "poc_entry", "content": "print('Exploit SUCCESS')\n"},
                    ],
                    "poc": {"success_signature": "Exploit SUCCESS"},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    write_generator_contract(
        metadata_dir,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": sid,
            "slug": slug,
            "vuln_id": "NAME-OPEN-REDIRECT",
            "success_signature": "Exploit SUCCESS",
            "service_entry": "app.py",
            "poc_entry": "poc.py",
            "service_port": 5000,
            "base_url": "http://127.0.0.1:5000",
            "output_mode": "auto",
            "fallback_used": True,
            "fallback_class": "generic_unsupported_family",
            "semantic_contract": {
                "semantic_signature": {
                    "input_vector": [],
                    "sink": [],
                    "exploit_precondition": [],
                },
                "semantic_signature_source": ["empty"],
                "status": "unsupported",
            },
        },
    )

    monkeypatch.setattr("evals.poc_verifier.rule_based.REPO_ROOT", repo_root)
    monkeypatch.setattr("evals.poc_verifier.rule_based.WORKSPACES_ROOT", repo_root / "workspaces")

    result = verify_with_rule(
        "NAME-OPEN-REDIRECT",
        run_dir / "run.log",
        run_summary={"sid": sid, "slug": slug, "exit_code": 0},
        policy={"require_exit_code_zero": True},
    )

    assert result["exploit_pass"] is True
    assert result["semantic_supported"] is False
    assert result["semantic_status"] == "unsupported"
    assert result["verify_pass"] is False
    assert "semantic support missing" in result["evidence"]


def test_evaluate_with_vuln_runtime_assertions_do_not_bypass_semantic_contract(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path
    sid = "sid-runtime-assert"
    vuln_id = "CWE-9998"
    slug = "cwe-9998"
    metadata_dir = repo_root / "metadata" / sid
    workspace_dir = repo_root / "workspaces" / sid / "app"
    run_dir = repo_root / "artifacts" / sid / "run"
    runtime_rules = metadata_dir / "runtime_rules"
    metadata_dir.mkdir(parents=True)
    workspace_dir.mkdir(parents=True)
    run_dir.mkdir(parents=True)
    runtime_rules.mkdir(parents=True)

    (runtime_rules / "cwe-9998.yaml").write_text(
        (
            "cwe: CWE-9998\n"
            "version: 2\n"
            "scenario_type: web-poc\n"
            "verification:\n"
            "  source: runtime\n"
            "  require_flag: false\n"
            "  flag_mode: none\n"
            "  exit_code: zero\n"
            "output:\n"
            "  mode: auto\n"
            "llm:\n"
            "  assist_default: false\n"
            "  assertion_budget: 4\n"
            "runtime:\n"
            "  success_mode: text\n"
            "  success_text_markers: [OK]\n"
            "  assertion_program:\n"
            "    - op: contains\n"
            "      string: OK\n"
        ),
        encoding="utf-8",
    )
    (workspace_dir / "app.py").write_text(
        "from flask import Flask\napp = Flask(__name__)\n@app.get('/')\ndef home():\n    return 'hello'\n",
        encoding="utf-8",
    )
    (run_dir / "run.log").write_text("OK\n", encoding="utf-8")

    write_generator_contract(
        metadata_dir,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": sid,
            "slug": slug,
            "vuln_id": vuln_id,
            "success_signature": "OK",
            "service_entry": "app.py",
            "poc_entry": "poc.py",
            "service_port": 5000,
            "base_url": "http://127.0.0.1:5000",
            "output_mode": "auto",
            "semantic_contract": {
                "semantic_signature": {
                    "input_vector": ["user-controlled request parameter"],
                    "sink": ["SQL query execution"],
                    "exploit_precondition": ["input concatenated/interpolated into SQL sink"],
                },
                "semantic_signature_source": ["contract"],
            },
        },
    )

    monkeypatch.setenv("VULD_RUNTIME_RULE_DIRS", str(runtime_rules))
    load_rule.cache_clear()
    list_rules.cache_clear()
    monkeypatch.setattr("evals.poc_verifier.rule_based.REPO_ROOT", repo_root)
    monkeypatch.setattr("evals.poc_verifier.rule_based.WORKSPACES_ROOT", repo_root / "workspaces")

    result = evaluate_with_vuln(
        vuln_id,
        run_dir / "run.log",
        run_summary={"sid": sid, "slug": slug, "exit_code": 0},
        plan_policy={"verifier": {"prefer_rule": True, "llm_assist": False, "require_exit_code_zero": True}},
    )

    assert result["exploit_pass"] is True
    assert result["verify_pass"] is False
    assert result["semantic_consistency"]["supported"] is True
    assert result["semantic_consistency"]["semantic_match"] is False
    assert result["verification_rule_source"] == "runtime_rule_candidate"
    assert result["verification_trust"] == "low"
    assert "semantic mismatch:" in result["evidence"]


def test_rule_based_verifier_ignores_poc_only_semantic_hits_for_unknown_contract(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path
    sid = "sid-scope"
    slug = "name-scope"
    metadata_dir = repo_root / "metadata" / sid
    workspace_dir = repo_root / "workspaces" / sid / "app"
    run_dir = repo_root / "artifacts" / sid / "run"
    metadata_dir.mkdir(parents=True)
    workspace_dir.mkdir(parents=True)
    run_dir.mkdir(parents=True)

    app_text = (
        "from flask import Flask\n"
        "app = Flask(__name__)\n"
        "@app.get('/')\n"
        "def home():\n"
        "    return 'safe response'\n"
    )
    poc_text = (
        "# request.args render_template_string template response <script> "
        "unescaped reflection cross-site scripting\n"
        "print('Exploit SUCCESS')\n"
    )
    (workspace_dir / "app.py").write_text(app_text, encoding="utf-8")
    (workspace_dir / "poc.py").write_text(poc_text, encoding="utf-8")
    (run_dir / "run.log").write_text("Exploit SUCCESS\n", encoding="utf-8")
    (metadata_dir / "generator_manifest.json").write_text(
        json.dumps(
            {
                "manifest": {
                    "files": [
                        {"path": "app.py", "role": "service_main", "content": app_text},
                        {"path": "poc.py", "role": "poc_entry", "content": poc_text},
                    ],
                    "poc": {"success_signature": "Exploit SUCCESS"},
                }
            }
        ),
        encoding="utf-8",
    )
    write_generator_contract(
        metadata_dir,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": sid,
            "slug": slug,
            "vuln_id": "NAME-SCOPE",
            "success_signature": "Exploit SUCCESS",
            "service_entry": "app.py",
            "poc_entry": "poc.py",
            "service_port": 5000,
            "base_url": "http://127.0.0.1:5000",
            "output_mode": "auto",
            "semantic_contract": {
                "semantic_signature": {
                    "input_vector": ["request.args", "query parameter"],
                    "sink": ["render_template_string", "template response"],
                    "exploit_precondition": ["<script>", "unescaped reflection", "cross-site scripting"],
                },
                "semantic_signature_source": ["contract"],
            },
        },
    )

    monkeypatch.setattr("evals.poc_verifier.rule_based.REPO_ROOT", repo_root)
    monkeypatch.setattr("evals.poc_verifier.rule_based.WORKSPACES_ROOT", repo_root / "workspaces")

    result = verify_with_rule(
        "NAME-SCOPE",
        run_dir / "run.log",
        run_summary={"sid": sid, "slug": slug, "exit_code": 0},
        policy={"require_exit_code_zero": True},
    )

    assert result["exploit_pass"] is True
    assert result["semantic_consistency"]["supported"] is True
    assert result["semantic_consistency"]["semantic_match"] is False
    assert result["verify_pass"] is False


def test_freeform_open_redirect_can_pass_when_semantics_and_service_match(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path
    sid = "sid-open-redirect-pass"
    slug = "name-open-redirect"
    metadata_dir = repo_root / "metadata" / sid
    workspace_dir = repo_root / "workspaces" / sid / "app"
    run_dir = repo_root / "artifacts" / sid / "run"
    metadata_dir.mkdir(parents=True)
    workspace_dir.mkdir(parents=True)
    run_dir.mkdir(parents=True)

    app_text = (
        "from flask import Flask, redirect, request\n"
        "app = Flask(__name__)\n"
        "@app.get('/go')\n"
        "def go():\n"
        "    # open redirect via unvalidated redirect target\n"
        "    next_url = request.args.get('next', 'https://example.com')\n"
        "    return redirect(next_url, code=302)\n"
    )
    poc_text = "print('Exploit SUCCESS')\n"
    (workspace_dir / "app.py").write_text(app_text, encoding="utf-8")
    (workspace_dir / "poc.py").write_text(poc_text, encoding="utf-8")
    (run_dir / "run.log").write_text("Exploit SUCCESS\n", encoding="utf-8")
    (metadata_dir / "generator_manifest.json").write_text(
        json.dumps(
            {
                "generation_origin": "deterministic_fallback",
                "fallback_used": True,
                "fallback_class": "family_aware",
                "manifest": {
                    "files": [
                        {"path": "app.py", "role": "service_main", "content": app_text},
                        {"path": "poc.py", "role": "poc_entry", "content": poc_text},
                    ],
                    "poc": {"success_signature": "Exploit SUCCESS"},
                },
            }
        ),
        encoding="utf-8",
    )
    write_generator_contract(
        metadata_dir,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": sid,
            "slug": slug,
            "vuln_id": "NAME-OPEN-REDIRECT",
            "success_signature": "Exploit SUCCESS",
            "service_entry": "app.py",
            "poc_entry": "poc.py",
            "service_port": 5000,
            "base_url": "http://127.0.0.1:5000",
            "output_mode": "auto",
            "fallback_used": True,
            "fallback_class": "family_aware",
            "semantic_contract": {
                "semantic_signature": {
                    "input_vector": ["request.args", "next parameter", "redirect target"],
                    "sink": ["redirect(", "location header", "http redirect sink"],
                    "exploit_precondition": ["open redirect", "unvalidated redirect target", "external redirect"],
                },
                "semantic_signature_source": ["pattern", "heuristic"],
                "status": "aligned",
            },
        },
    )

    monkeypatch.setattr("evals.poc_verifier.rule_based.REPO_ROOT", repo_root)
    monkeypatch.setattr("evals.poc_verifier.rule_based.WORKSPACES_ROOT", repo_root / "workspaces")

    result = verify_with_rule(
        "NAME-OPEN-REDIRECT",
        run_dir / "run.log",
        run_summary={"sid": sid, "slug": slug, "exit_code": 0},
        policy={"require_exit_code_zero": True},
    )

    assert result["verify_pass"] is True
    assert result["semantic_supported"] is True
    assert result["semantic_status"] == "aligned"
    assert result["semantic_consistency"]["source"] == "generator_manifest"
