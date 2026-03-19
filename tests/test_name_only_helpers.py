from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.name_only import (
    build_name_only_contract,
    classify_name_only_intent,
    closure_source_allowed_by_contract,
    closure_source_satisfies_intent,
    is_name_driven_requirement,
    resolve_name_only_closure_source,
)


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


def test_resolve_name_only_closure_source_maps_strict_positive_llm_manifest() -> None:
    closure_source = resolve_name_only_closure_source(
        failure_stage="",
        generation_origin="llm_manifest",
        strict_counts_as_generalization=True,
    )

    assert closure_source == "strict_open_world_positive"


def test_name_only_contract_path_helpers_separate_execution_from_intent() -> None:
    requirement = {
        "vuln_id": "CWE-79",
        "request_ir": {
            "request_label": "Reflected XSS",
            "resolved_vuln_id": "CWE-79",
            "name_driven": True,
        },
        "policy": {"name_only_mode": "dynamic"},
    }

    contract = build_name_only_contract(requirement=requirement)

    assert closure_source_allowed_by_contract(contract, "degraded_deterministic_fallback") is True
    assert closure_source_satisfies_intent(contract, "degraded_deterministic_fallback") is False
    assert closure_source_satisfies_intent(contract, "trusted_dynamic") is True


def test_classify_name_only_intent_marks_dynamic_degraded_path_as_partial() -> None:
    requirement = {
        "vuln_id": "CWE-79",
        "request_ir": {
            "request_label": "Reflected XSS",
            "resolved_vuln_id": "CWE-79",
            "name_driven": True,
        },
        "policy": {"name_only_mode": "dynamic"},
    }
    contract = build_name_only_contract(requirement=requirement)

    verdict = classify_name_only_intent(
        mode="dynamic",
        contract=contract,
        closure_source="degraded_deterministic_fallback",
        dynamic_eval_status="degraded_success",
        open_world_class="semantic_guided_minimal_dynamic",
    )

    assert verdict["status"] == "degraded_dynamic_success"
    assert verdict["meets_intent"] is False
    assert verdict["partial"] is True
    assert verdict["allowed_by_execution_contract"] is True
    assert verdict["satisfies_intent_contract"] is False
