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
    assert payload["contract_stage"] == "synthesis"


def test_contract_uses_researcher_proposal_when_rule_is_missing(tmp_path: Path) -> None:
    payload = build_generator_contract(
        sid="sid-contract",
        vuln_id="CWE-9999",
        metadata_dir=tmp_path,
        workspace_dir=None,
        generator_mode="research_seed",
        bundle_slug="cwe-9999",
        researcher_report={
            "researcher_report": {
                "verification_spec": {
                    "success_text_markers": ["UNKNOWN SUCCESS"],
                    "flag_token": "FLAG-unknown",
                    "assertion_program": [{"op": "contains", "string": "UNKNOWN SUCCESS"}],
                },
                "semantic_signature": {
                    "input_vector": ["request.args"],
                    "sink": ["execute("],
                    "exploit_precondition": ["string concatenation"],
                },
                "semantic_signature_source": ["heuristic"],
                "quality": "sufficient",
                "quality_reason": "semantic anchors matched",
            }
        },
    )

    assert payload["success_signature"] == "UNKNOWN SUCCESS"
    assert payload["flag_token"] == "FLAG-unknown"
    assert payload["sources"]["success_signature"] == "researcher_report.verification_spec.success_text_markers[0]"
    assert payload["sources"]["flag_token"] == "researcher_report.verification_spec.flag_token"
    assert payload["proposed_verification_contract"]["success_signature"] == "UNKNOWN SUCCESS"
    assert payload["proposed_verification_contract"]["flag_token"] == "FLAG-unknown"
    assert payload["semantic_contract"]["semantic_signature"]["sink"] == ["execute("]
    assert payload["semantic_contract"]["semantic_signature_source"] == ["heuristic"]
    assert payload["semantic_contract"]["quality"] == "sufficient"
    assert payload["contract_stage"] == "research_seed"


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
