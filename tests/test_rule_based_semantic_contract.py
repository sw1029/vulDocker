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
    (workspace_dir / "poc.py").write_text("print('Exploit SUCCESS')\nprint('FLAG{OPEN_REDIRECT_OK}')\n", encoding="utf-8")
    (run_dir / "run.log").write_text("Exploit SUCCESS\nFLAG{OPEN_REDIRECT_OK}\n", encoding="utf-8")

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
    assert result["verification_rule_source"] == "contract_oracle_fallback"
    assert result["verification_trust"] == "low"
    assert result["verification_independence"] == "contract_coupled"


def test_unknown_rule_based_verifier_can_use_contract_oracle_json_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path
    metadata_dir = repo_root / "metadata" / "sid-oracle-json"
    workspace_dir = repo_root / "workspaces" / "sid-oracle-json" / "app"
    run_dir = repo_root / "artifacts" / "sid-oracle-json" / "run"
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
    (workspace_dir / "poc.py").write_text("print('{\"success\": true, \"flag\": \"FLAG{JSON_OK}\"}')\n", encoding="utf-8")
    (run_dir / "run.log").write_text('{"success": true, "flag": "FLAG{JSON_OK}"}\n', encoding="utf-8")

    (metadata_dir / "generator_manifest.json").write_text(
        json.dumps(
            {
                "manifest": {
                    "files": [
                        {"path": "app.py", "role": "service_main", "content": app_text},
                        {"path": "poc.py", "role": "poc_entry", "content": "print('json')\n"},
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    write_generator_contract(
        metadata_dir,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": "sid-oracle-json",
            "slug": "cwe-9999",
            "vuln_id": "CWE-9999",
            "service_entry": "app.py",
            "poc_entry": "poc.py",
            "service_port": 5000,
            "base_url": "http://127.0.0.1:5000",
            "exploit_oracle": {
                "success_signature": "",
                "flag_token": "FLAG{JSON_OK}",
                "output_mode": "json",
                "json_success_key": "success",
                "json_success_value": True,
                "json_flag_key": "flag",
                "source": "researcher_verification_spec",
            },
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
        run_summary={"sid": "sid-oracle-json", "slug": "cwe-9999", "exit_code": 0},
        policy={"require_exit_code_zero": True},
    )

    assert result["verify_pass"] is True
    assert result["verification_rule_source"] == "contract_oracle_fallback"
    assert result["verification_trust"] == "low"
    assert result["verification_independence"] == "contract_coupled"
    assert "resolved_contract oracle contract" in result["evidence"]


def test_rule_based_verifier_surfaces_oracle_execution_parity_from_run_artifact(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path
    metadata_dir = repo_root / "metadata" / "sid-oracle-parity"
    workspace_dir = repo_root / "workspaces" / "sid-oracle-parity" / "app"
    run_dir = repo_root / "artifacts" / "sid-oracle-parity" / "run"
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
    (workspace_dir / "poc.py").write_text("print('Exploit SUCCESS')\nprint('FLAG{OK}')\n", encoding="utf-8")
    (run_dir / "run.log").write_text("Exploit SUCCESS\nFLAG{OK}\n", encoding="utf-8")
    (run_dir / "oracle_execution.json").write_text(
        json.dumps(
            {
                "schema_version": "oracle_execution@0.1",
                "parity": "high",
                "negative_controls": {"available": True, "attempted": True, "total": 1, "total_declared": 1, "passed": True},
                "metamorphic": {"available": True, "attempted": True, "total": 1, "total_declared": 1, "passed": True},
                "forbidden_success": {"markers": [], "passed": True},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    write_generator_contract(
        metadata_dir,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": "sid-oracle-parity",
            "slug": "cwe-9999",
            "vuln_id": "CWE-9999",
            "service_entry": "app.py",
            "poc_entry": "poc.py",
            "service_port": 5000,
            "base_url": "http://127.0.0.1:5000",
            "exploit_oracle": {
                "success_signature": "Exploit SUCCESS",
                "flag_token": "FLAG{OK}",
                "negative_controls": [{"name": "benign", "payload": "safe", "expect_success": False}],
                "metamorphic": {"cases": [{"name": "same-origin", "payload": "/local", "expect_success": False}]},
                "source": "researcher_verification_spec",
            },
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
        run_summary={"sid": "sid-oracle-parity", "slug": "cwe-9999", "exit_code": 0},
        policy={"require_exit_code_zero": True},
    )

    assert result["verify_pass"] is True
    assert result["oracle_execution_parity"] == "high"
    assert result["oracle_execution_attempted"] is True
    assert result["oracle_negative_controls_pass"] is True
    assert result["oracle_metamorphic_pass"] is True


def test_unknown_rule_based_verifier_uses_contract_oracle_assertion_program_with_negative_markers(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path
    metadata_dir = repo_root / "metadata" / "sid-oracle-assertions"
    workspace_dir = repo_root / "workspaces" / "sid-oracle-assertions" / "app"
    run_dir = repo_root / "artifacts" / "sid-oracle-assertions" / "run"
    metadata_dir.mkdir(parents=True)
    workspace_dir.mkdir(parents=True)
    run_dir.mkdir(parents=True)

    (workspace_dir / "app.py").write_text("print('service')\n", encoding="utf-8")
    (workspace_dir / "poc.py").write_text("print('Exploit SUCCESS')\n", encoding="utf-8")
    (run_dir / "run.log").write_text("Exploit SUCCESS\nExploit FAILED\n", encoding="utf-8")

    write_generator_contract(
        metadata_dir,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": "sid-oracle-assertions",
            "slug": "cwe-9999",
            "vuln_id": "CWE-9999",
            "service_entry": "app.py",
            "poc_entry": "poc.py",
            "service_port": 5000,
            "base_url": "http://127.0.0.1:5000",
            "exploit_oracle": {
                "success_signature": "Exploit SUCCESS",
                "negative_text_markers": ["Exploit FAILED"],
                "assertion_program": [
                    {"op": "contains", "string": "Exploit SUCCESS"},
                    {"op": "not_contains", "string": "Exploit FAILED"},
                ],
                "source": "researcher_verification_spec",
            },
        },
    )

    monkeypatch.setattr("evals.poc_verifier.rule_based.REPO_ROOT", repo_root)
    monkeypatch.setattr("evals.poc_verifier.rule_based.WORKSPACES_ROOT", repo_root / "workspaces")

    result = verify_with_rule(
        "CWE-9999",
        run_dir / "run.log",
        run_summary={"sid": "sid-oracle-assertions", "slug": "cwe-9999", "exit_code": 0},
        policy={"require_exit_code_zero": True},
    )

    assert result["verify_pass"] is False
    assert result["verification_rule_source"] == "contract_oracle_fallback"
    assert result["verification_independence"] == "contract_coupled"


def test_unknown_rule_based_verifier_converts_negative_markers_into_runtime_assertions(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path
    metadata_dir = repo_root / "metadata" / "sid-oracle-negative-markers"
    workspace_dir = repo_root / "workspaces" / "sid-oracle-negative-markers" / "app"
    run_dir = repo_root / "artifacts" / "sid-oracle-negative-markers" / "run"
    metadata_dir.mkdir(parents=True)
    workspace_dir.mkdir(parents=True)
    run_dir.mkdir(parents=True)

    (workspace_dir / "app.py").write_text("print('service')\n", encoding="utf-8")
    (workspace_dir / "poc.py").write_text("print('Exploit SUCCESS')\n", encoding="utf-8")
    (run_dir / "run.log").write_text("Exploit SUCCESS\nExploit FAILED\n", encoding="utf-8")

    write_generator_contract(
        metadata_dir,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": "sid-oracle-negative-markers",
            "slug": "cwe-9999",
            "vuln_id": "CWE-9999",
            "service_entry": "app.py",
            "poc_entry": "poc.py",
            "service_port": 5000,
            "base_url": "http://127.0.0.1:5000",
            "exploit_oracle": {
                "success_signature": "Exploit SUCCESS",
                "negative_text_markers": ["Exploit FAILED"],
                "source": "generator_manifest.poc_derived_verification_spec",
            },
        },
    )

    monkeypatch.setattr("evals.poc_verifier.rule_based.REPO_ROOT", repo_root)
    monkeypatch.setattr("evals.poc_verifier.rule_based.WORKSPACES_ROOT", repo_root / "workspaces")

    result = verify_with_rule(
        "CWE-9999",
        run_dir / "run.log",
        run_summary={"sid": "sid-oracle-negative-markers", "slug": "cwe-9999", "exit_code": 0},
        policy={"require_exit_code_zero": True},
    )

    assert result["verify_pass"] is False
    assert result["verification_rule_source"] == "contract_oracle_fallback"
    assert result["verification_independence"] == "contract_coupled"


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
    (run_dir / "run.log").write_text("Exploit SUCCESS\nFLAG{OPEN_REDIRECT_OK}\n", encoding="utf-8")

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
    (run_dir / "run.log").write_text("Exploit SUCCESS\nFLAG{OPEN_REDIRECT_OK}\n", encoding="utf-8")
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
    assert result["verification_rule_source"] == "contract_oracle_fallback"
    assert result["verification_trust"] == "low"
    assert result["verification_independence"] == "contract_coupled"
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
    (run_dir / "run.log").write_text("Exploit SUCCESS\nFLAG{OPEN_REDIRECT_OK}\n", encoding="utf-8")
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
    (workspace_dir / "poc.py").write_text("print('Exploit SUCCESS')\nprint('FLAG{OPEN_REDIRECT_OK}')\n", encoding="utf-8")
    (run_dir / "run.log").write_text("Exploit SUCCESS\nFLAG{OPEN_REDIRECT_OK}\n", encoding="utf-8")

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
    (run_dir / "run.log").write_text("Exploit SUCCESS\nFLAG{OPEN_REDIRECT_OK}\n", encoding="utf-8")
    (metadata_dir / "generator_manifest.json").write_text(
        json.dumps(
            {
                "generation_origin": "deterministic_fallback",
                "fallback_used": True,
                "fallback_class": "generic_unsupported_family",
                "manifest": {
                    "files": [
                        {"path": "app.py", "role": "service_main", "content": app_text},
                        {
                            "path": "poc.py",
                            "role": "poc_entry",
                            "content": "print('Exploit SUCCESS')\nprint('FLAG{OPEN_REDIRECT_OK}')\n",
                        },
                    ],
                    "poc": {"success_signature": "Exploit SUCCESS", "flag_token": "FLAG{OPEN_REDIRECT_OK}"},
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
            "flag_token": "FLAG{OPEN_REDIRECT_OK}",
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
    (run_dir / "run.log").write_text("Exploit SUCCESS\nFLAG{OPEN_REDIRECT_OK}\n", encoding="utf-8")
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
    poc_text = "print('Exploit SUCCESS')\nprint('FLAG{OPEN_REDIRECT_OK}')\n"
    (workspace_dir / "app.py").write_text(app_text, encoding="utf-8")
    (workspace_dir / "poc.py").write_text(poc_text, encoding="utf-8")
    (run_dir / "run.log").write_text("Exploit SUCCESS\nFLAG{OPEN_REDIRECT_OK}\n", encoding="utf-8")
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
                    "poc": {"success_signature": "Exploit SUCCESS", "flag_token": "FLAG{OPEN_REDIRECT_OK}"},
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
            "flag_token": "FLAG{OPEN_REDIRECT_OK}",
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


def test_declared_rule_preempts_runtime_rule_for_supported_name_family(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path
    sid = "sid-compiler-runtime-rule"
    slug = "name-open-redirect"
    metadata_dir = repo_root / "metadata" / sid
    runtime_rules = metadata_dir / "runtime_rules"
    workspace_dir = repo_root / "workspaces" / sid / "app"
    run_dir = repo_root / "artifacts" / sid / "run"
    metadata_dir.mkdir(parents=True)
    runtime_rules.mkdir(parents=True)
    workspace_dir.mkdir(parents=True)
    run_dir.mkdir(parents=True)

    app_text = (
        "from flask import Flask, redirect, request\n"
        "app = Flask(__name__)\n"
        "@app.get('/go')\n"
        "def go():\n"
        "    next_url = request.args.get('next', 'https://example.com')\n"
        "    return redirect(next_url, code=302)\n"
    )
    poc_text = "print('Exploit SUCCESS')\nprint('FLAG{OPEN_REDIRECT_OK}')\n"
    (workspace_dir / "app.py").write_text(app_text, encoding="utf-8")
    (workspace_dir / "poc.py").write_text(poc_text, encoding="utf-8")
    (run_dir / "run.log").write_text("Exploit SUCCESS\nFLAG{OPEN_REDIRECT_OK}\n", encoding="utf-8")
    (metadata_dir / "generator_manifest.json").write_text(
        json.dumps(
            {
                "generation_origin": "compiler_generated",
                "manifest": {
                    "metadata": {"cwe": "NAME-OPEN-REDIRECT"},
                    "files": [
                        {"path": "app.py", "role": "service_main", "content": app_text},
                        {"path": "poc.py", "role": "poc_entry", "content": poc_text},
                    ],
                    "poc": {
                        "success_signature": "Exploit SUCCESS",
                        "flag_token": "FLAG{OPEN_REDIRECT_OK}",
                    },
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
            "flag_token": "FLAG{OPEN_REDIRECT_OK}",
            "service_entry": "app.py",
            "poc_entry": "poc.py",
            "service_port": 5000,
            "base_url": "http://127.0.0.1:5000",
            "output_mode": "auto",
            "compiler_supported": True,
            "compiler_strategy": "open_redirect_reflect",
            "generation_origin": "compiler_generated",
            "provenance": {"generation_origin": "compiler_generated"},
            "semantic_contract": {
                "semantic_signature": {
                    "input_vector": ["request.args", "next parameter", "redirect target"],
                    "sink": ["redirect(", "location header", "http redirect sink"],
                    "exploit_precondition": ["open redirect", "unvalidated redirect target", "external redirect"],
                },
                "semantic_signature_source": ["fragment_registry"],
                "status": "aligned",
            },
        },
    )
    (runtime_rules / "name-open-redirect.yaml").write_text(
        "\n".join(
            [
                "cwe: NAME-OPEN-REDIRECT",
                "version: 2",
                "scenario_type: web-poc",
                "origin: runtime",
                "override_scope: none",
                "verification:",
                "  source: runtime",
                "  require_flag: true",
                "  flag_mode: strict",
                "  exit_code: zero",
                "output:",
                "  mode: auto",
                "  format: auto",
                "llm:",
                "  assist_default: false",
                "  assertion_budget: 8",
                "runtime:",
                "  success_mode: text",
                "  success_text_markers:",
                "    - Exploit SUCCESS",
                "  flag_token: FLAG{OPEN_REDIRECT_OK}",
                "success_signature: Exploit SUCCESS",
                "flag_token: FLAG{OPEN_REDIRECT_OK}",
                "strict_flag: true",
                "patterns:",
                "  - type: file_contains",
                "    path: app.py",
                "    contains: redirect(",
                "  - type: poc_contains",
                "    path: poc.py",
                "    contains: Exploit SUCCESS",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("VULD_RUNTIME_RULE_DIRS", str(runtime_rules))
    load_rule.cache_clear()
    list_rules.cache_clear()
    monkeypatch.setattr("evals.poc_verifier.rule_based.REPO_ROOT", repo_root)
    monkeypatch.setattr("evals.poc_verifier.rule_based.WORKSPACES_ROOT", repo_root / "workspaces")

    result = verify_with_rule(
        "NAME-OPEN-REDIRECT",
        run_dir / "run.log",
        run_summary={"sid": sid, "slug": slug, "exit_code": 0},
        policy={"require_exit_code_zero": True},
    )

    assert result["verify_pass"] is True
    assert result["verification_rule_source"] == "declared_rule"
    assert result["verification_trust"] == "high"
    assert result["verification_independence"] == "independent"
    assert "declared static/runtime rule contract" in result["verification_trust_reason"]


def test_declared_rule_supports_cwe78_minimal_dynamic_workspace(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path
    sid = "sid-cwe78-declared"
    slug = "cwe-78"
    metadata_dir = repo_root / "metadata" / sid
    workspace_dir = repo_root / "workspaces" / sid / slug
    run_dir = repo_root / "artifacts" / sid / "run"
    metadata_dir.mkdir(parents=True)
    workspace_dir.mkdir(parents=True)
    run_dir.mkdir(parents=True)

    app_text = (
        "import subprocess\n"
        "from flask import Flask, jsonify, request\n"
        "app = Flask(__name__)\n"
        "@app.get('/run')\n"
        "def run():\n"
        "    cmd = request.args.get('cmd', 'echo safe')\n"
        "    output = subprocess.check_output('echo start && ' + cmd, shell=True, text=True)\n"
        "    return jsonify({'success': True, 'output': output})\n"
    )
    poc_text = "print('Exploit SUCCESS')\nprint('FLAG-command-injection-demo-token')\n"
    (workspace_dir / "app.py").write_text(app_text, encoding="utf-8")
    (workspace_dir / "poc.py").write_text(poc_text, encoding="utf-8")
    (run_dir / "run.log").write_text("Exploit SUCCESS\nFLAG-command-injection-demo-token\n", encoding="utf-8")

    manifest = {
        "manifest": {
            "files": [
                {"path": "app.py", "role": "service_main", "content": app_text},
                {"path": "poc.py", "role": "poc_entry", "content": poc_text},
            ],
            "poc": {"success_signature": "Exploit SUCCESS", "flag_token": "FLAG-command-injection-demo-token"},
        },
    }
    (metadata_dir / "generator_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    write_generator_contract(
        metadata_dir,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": sid,
            "slug": slug,
            "vuln_id": "CWE-78",
            "service_entry": "app.py",
            "poc_entry": "poc.py",
            "success_signature": "Exploit SUCCESS",
            "flag_token": "FLAG-command-injection-demo-token",
        },
    )

    monkeypatch.setattr("evals.poc_verifier.rule_based.REPO_ROOT", repo_root)
    monkeypatch.setattr("evals.poc_verifier.rule_based.WORKSPACES_ROOT", repo_root / "workspaces")

    result = verify_with_rule(
        "CWE-78",
        run_dir / "run.log",
        run_summary={"sid": sid, "slug": slug, "exit_code": 0},
        policy={"require_exit_code_zero": True},
    )

    assert result["verify_pass"] is True
    assert result["verification_rule_source"] == "declared_rule"
    assert result["verification_trust"] == "high"
    assert result["verification_independence"] == "independent"


def test_declared_rule_supports_cwe94_minimal_dynamic_workspace(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path
    sid = "sid-cwe94-declared"
    slug = "cwe-94"
    metadata_dir = repo_root / "metadata" / sid
    workspace_dir = repo_root / "workspaces" / sid / slug
    run_dir = repo_root / "artifacts" / sid / "run"
    metadata_dir.mkdir(parents=True)
    workspace_dir.mkdir(parents=True)
    run_dir.mkdir(parents=True)

    app_text = (
        "from flask import Flask, jsonify, request\n"
        "app = Flask(__name__)\n"
        "FLAG_TOKEN = 'FLAG-code-injection-demo-token'\n"
        "@app.get('/eval')\n"
        "def evaluate():\n"
        "    expr = request.args.get('expr', '0')\n"
        "    result = eval(expr, {'FLAG_TOKEN': FLAG_TOKEN})\n"
        "    return jsonify({'success': True, 'result': str(result)})\n"
    )
    poc_text = "print('Exploit SUCCESS')\nprint('FLAG-code-injection-demo-token')\n"
    (workspace_dir / "app.py").write_text(app_text, encoding="utf-8")
    (workspace_dir / "poc.py").write_text(poc_text, encoding="utf-8")
    (run_dir / "run.log").write_text("Exploit SUCCESS\nFLAG-code-injection-demo-token\n", encoding="utf-8")

    manifest = {
        "manifest": {
            "files": [
                {"path": "app.py", "role": "service_main", "content": app_text},
                {"path": "poc.py", "role": "poc_entry", "content": poc_text},
            ],
            "poc": {"success_signature": "Exploit SUCCESS", "flag_token": "FLAG-code-injection-demo-token"},
        },
    }
    (metadata_dir / "generator_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    write_generator_contract(
        metadata_dir,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": sid,
            "slug": slug,
            "vuln_id": "CWE-94",
            "service_entry": "app.py",
            "poc_entry": "poc.py",
            "success_signature": "Exploit SUCCESS",
            "flag_token": "FLAG-code-injection-demo-token",
        },
    )

    monkeypatch.setattr("evals.poc_verifier.rule_based.REPO_ROOT", repo_root)
    monkeypatch.setattr("evals.poc_verifier.rule_based.WORKSPACES_ROOT", repo_root / "workspaces")

    result = verify_with_rule(
        "CWE-94",
        run_dir / "run.log",
        run_summary={"sid": sid, "slug": slug, "exit_code": 0},
        policy={"require_exit_code_zero": True},
    )

    assert result["verify_pass"] is True
    assert result["verification_rule_source"] == "declared_rule"
    assert result["verification_trust"] == "high"
    assert result["verification_independence"] == "independent"


def test_declared_rule_supports_cwe502_minimal_dynamic_workspace(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path
    sid = "sid-cwe502-declared"
    slug = "cwe-502"
    metadata_dir = repo_root / "metadata" / sid
    workspace_dir = repo_root / "workspaces" / sid / slug
    run_dir = repo_root / "artifacts" / sid / "run"
    metadata_dir.mkdir(parents=True)
    workspace_dir.mkdir(parents=True)
    run_dir.mkdir(parents=True)

    app_text = (
        "from pathlib import Path\n"
        "import pickle\n"
        "from flask import Flask, jsonify, request\n"
        "app = Flask(__name__)\n"
        "FLAG_PATH = Path('/tmp/deser-flag.txt')\n"
        "FLAG_VALUE = 'FLAG{DESER_OK}'\n"
        "@app.post('/deserialize')\n"
        "def deserialize_payload():\n"
        "    payload = request.get_data()\n"
        "    result = pickle.loads(payload)\n"
        "    return jsonify({'result': str(result)})\n"
    )
    poc_text = "print('Exploit SUCCESS')\nprint('FLAG{DESER_OK}')\n"
    (workspace_dir / "app.py").write_text(app_text, encoding="utf-8")
    (workspace_dir / "poc.py").write_text(poc_text, encoding="utf-8")
    (run_dir / "run.log").write_text("Exploit SUCCESS\nFLAG{DESER_OK}\n", encoding="utf-8")

    manifest = {
        "manifest": {
            "files": [
                {"path": "app.py", "role": "service_main", "content": app_text},
                {"path": "poc.py", "role": "poc_entry", "content": poc_text},
            ],
            "poc": {"success_signature": "Exploit SUCCESS", "flag_token": "FLAG{DESER_OK}"},
        },
    }
    (metadata_dir / "generator_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    write_generator_contract(
        metadata_dir,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": sid,
            "slug": slug,
            "vuln_id": "CWE-502",
            "service_entry": "app.py",
            "poc_entry": "poc.py",
            "success_signature": "Exploit SUCCESS",
            "flag_token": "FLAG{DESER_OK}",
        },
    )

    monkeypatch.setattr("evals.poc_verifier.rule_based.REPO_ROOT", repo_root)
    monkeypatch.setattr("evals.poc_verifier.rule_based.WORKSPACES_ROOT", repo_root / "workspaces")

    result = verify_with_rule(
        "CWE-502",
        run_dir / "run.log",
        run_summary={"sid": sid, "slug": slug, "exit_code": 0},
        policy={"require_exit_code_zero": True},
    )

    assert result["verify_pass"] is True
    assert result["verification_rule_source"] == "declared_rule"
    assert result["verification_trust"] == "high"
    assert result["verification_independence"] == "independent"


def test_declared_rule_supports_name_xxe_fastapi_minimal_dynamic_workspace(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path
    sid = "sid-name-xxe-declared"
    slug = "name-xxe"
    metadata_dir = repo_root / "metadata" / sid
    workspace_dir = repo_root / "workspaces" / sid / slug
    run_dir = repo_root / "artifacts" / sid / "run"
    metadata_dir.mkdir(parents=True)
    workspace_dir.mkdir(parents=True)
    run_dir.mkdir(parents=True)

    app_text = (
        "from pathlib import Path\n"
        "from lxml import etree\n"
        "from fastapi import FastAPI, Request\n"
        "app = FastAPI()\n"
        "FLAG_TOKEN = 'FLAG{XXE_OK}'\n"
        "SECRET_PATH = Path('/tmp/xxe-secret.txt')\n"
        "SECRET_PATH.write_text(FLAG_TOKEN, encoding='utf-8')\n"
        "@app.post('/parse')\n"
        "async def parse(request: Request):\n"
        "    xml_body = await request.body()\n"
        "    parser = etree.XMLParser(load_dtd=True, resolve_entities=True)\n"
        "    root = etree.fromstring(xml_body, parser=parser)\n"
        "    return {'text': ''.join(root.itertext())}\n"
    )
    poc_text = "print('Exploit SUCCESS')\nprint('FLAG{XXE_OK}')\n"
    (workspace_dir / "app.py").write_text(app_text, encoding="utf-8")
    (workspace_dir / "poc.py").write_text(poc_text, encoding="utf-8")
    (run_dir / "run.log").write_text("Exploit SUCCESS\nFLAG{XXE_OK}\n", encoding="utf-8")

    manifest = {
        "manifest": {
            "files": [
                {"path": "app.py", "role": "service_main", "content": app_text},
                {"path": "poc.py", "role": "poc_entry", "content": poc_text},
            ],
            "poc": {"success_signature": "Exploit SUCCESS", "flag_token": "FLAG{XXE_OK}"},
        },
    }
    (metadata_dir / "generator_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    write_generator_contract(
        metadata_dir,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": sid,
            "slug": slug,
            "vuln_id": "NAME-XXE",
            "service_entry": "app.py",
            "poc_entry": "poc.py",
            "success_signature": "Exploit SUCCESS",
            "flag_token": "FLAG{XXE_OK}",
        },
    )

    monkeypatch.setattr("evals.poc_verifier.rule_based.REPO_ROOT", repo_root)
    monkeypatch.setattr("evals.poc_verifier.rule_based.WORKSPACES_ROOT", repo_root / "workspaces")

    result = verify_with_rule(
        "NAME-XXE",
        run_dir / "run.log",
        run_summary={"sid": sid, "slug": slug, "exit_code": 0},
        policy={"require_exit_code_zero": True},
    )

    assert result["verify_pass"] is True
    assert result["verification_rule_source"] == "declared_rule"
    assert result["verification_trust"] == "high"
    assert result["verification_independence"] == "independent"
