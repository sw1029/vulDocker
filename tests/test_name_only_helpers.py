from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.name_only import build_name_only_contract, is_name_driven_requirement


def test_is_name_driven_requirement_uses_request_ir_when_vuln_id_is_canonicalized() -> None:
    requirement = {
        "vuln_id": "CWE-79",
        "request_ir": {
            "request_label": "Reflected XSS",
            "resolved_vuln_id": "CWE-79",
            "name_driven": True,
            "resolution_state": "token_match",
        },
    }

    assert is_name_driven_requirement(requirement) is True


def test_build_name_only_contract_uses_request_ir_name_driven_signal() -> None:
    requirement = {
        "vuln_id": "CWE-79",
        "request_ir": {
            "request_label": "Reflected XSS",
            "resolved_vuln_id": "CWE-79",
            "name_driven": True,
            "resolution_state": "token_match",
        },
        "policy": {"name_only_mode": "dynamic"},
    }

    contract = build_name_only_contract(requirement=requirement)

    assert contract["enabled"] is True
    assert contract["effective_mode"] == "dynamic"
    assert contract["require_research"] is True
    assert contract["allow_degraded_fallback"] is True


def test_build_name_only_contract_separates_execution_paths_from_intent_paths() -> None:
    requirement = {
        "vuln_id": "CWE-79",
        "request_ir": {
            "request_label": "Reflected XSS",
            "resolved_vuln_id": "CWE-79",
            "name_driven": True,
            "resolution_state": "token_match",
        },
        "policy": {"name_only_mode": "dynamic"},
    }

    contract = build_name_only_contract(requirement=requirement)

    assert contract["allowed_execution_paths"] == [
        "trusted_dynamic",
        "strict_open_world_positive",
        "degraded_deterministic_fallback",
    ]
    assert contract["intent_satisfying_paths"] == [
        "trusted_dynamic",
        "strict_open_world_positive",
    ]
