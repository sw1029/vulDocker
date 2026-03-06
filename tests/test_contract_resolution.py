from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.contracts import build_generator_contract, load_generator_contract, write_generator_contract


def test_contract_uses_rule_defined_success_markers(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="CWE-89",
        metadata_dir=tmp_path,
        workspace_dir=tmp_path,
        generator_mode="synthesis",
        bundle_slug="cwe-89",
    )

    assert payload["success_signature"] == "SQLi SUCCESS"
    assert payload["flag_token"] == "FLAG-sqli-demo-token"
    assert payload["output_mode"] == "auto"
    assert payload["schema_version"] == "resolved_contract@1.0"


def test_write_generator_contract_mirrors_resolved_and_legacy_files(tmp_path: Path) -> None:
    payload = {
        "schema_version": "resolved_contract@1.0",
        "sid": "sid-contract",
        "slug": "cwe-89",
        "vuln_id": "CWE-89",
        "success_signature": "SQLi SUCCESS",
        "flag_token": "FLAG-sqli-demo-token",
        "service_entry": "app.py",
        "poc_entry": "poc.py",
        "service_port": 5000,
        "base_url": "http://127.0.0.1:5000",
        "output_mode": "auto",
    }

    written = write_generator_contract(tmp_path, payload)

    assert written.name == "resolved_contract.json"
    assert (tmp_path / "resolved_contract.json").exists()
    assert (tmp_path / "generator_contract.json").exists()
    loaded = load_generator_contract(tmp_path)
    assert loaded is not None
    assert loaded["success_signature"] == "SQLi SUCCESS"
    assert json.loads((tmp_path / "generator_contract.json").read_text(encoding="utf-8"))["slug"] == "cwe-89"
