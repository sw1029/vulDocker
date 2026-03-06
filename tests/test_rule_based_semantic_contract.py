from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.contracts import write_generator_contract
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
