from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.guardrails import build_guard_spec, default_guard_policy_snapshot, parse_guard_spec


def test_guard_spec_roundtrip() -> None:
    spec = build_guard_spec(
        sid="sid-test",
        vuln_id="CWE-89",
        slug="cwe-89",
        policy_snapshot={"enforcement": "block_both"},
        evidence_refs=[{"index": 0, "query": "cwe-89 sql injection", "source": "remote", "url": "https://x"}],
        semantic_signature={
            "input_vector": ["request parameter"],
            "sink": ["sql execute"],
            "exploit_precondition": ["string concatenation"],
        },
        generator_assertions=[{"op": "file_exists", "path": "app.py"}],
        verifier_assertions=[{"op": "contains", "string": "Exploit SUCCESS"}],
        autofix_hints=[{"priority": 10, "instruction": "Keep PoC success signature aligned"}],
        confidence="high",
    )
    parsed = parse_guard_spec(spec.to_dict())
    assert parsed.sid == "sid-test"
    assert parsed.vuln_id == "CWE-89"
    assert parsed.confidence == "high"
    assert parsed.generator_assertions[0]["op"] == "file_exists"
    assert parsed.verifier_assertions_deferred == []
    assert parsed.normalization["mapped_ops"] == []


def test_guard_policy_defaults_normalize_invalid_values() -> None:
    policy = default_guard_policy_snapshot(
        {
            "enforcement": "invalid",
            "failure_policy": "invalid",
            "dynamic_scope": "invalid",
            "call_budget": {"mode": "invalid", "ensemble_runs": -10},
            "autofix": {"level": "invalid", "max_attempts": -1},
        }
    )
    assert policy["enforcement"] == "block_both"
    assert policy["failure_policy"] == "closed_unknown"
    assert policy["dynamic_scope"] == "assertions_semantics"
    assert policy["call_budget"]["mode"] == "bundle_once"
    assert policy["call_budget"]["ensemble_runs"] == 1
    assert policy["autofix"]["level"] == "code"
    assert policy["autofix"]["max_attempts"] == 0
    assert policy["unsupported_op_policy"] == "normalize_retry"
    assert policy["refresh_researcher_on_guard_dsl_error"] is True


def test_guard_spec_normalizes_assertion_metadata_fields() -> None:
    spec = build_guard_spec(
        sid="sid-test",
        vuln_id="CWE-89",
        slug="cwe-89",
        generator_assertions=[
            {
                "op": "file_contains",
                "path": "app.py",
                "needle": "request.args",
                "severity": "INVALID",
                "intent": "unknown",
                "stability": "unstable",
                "evidence_ids": ["0", 1, "x"],
            }
        ],
        verifier_assertions=[],
    )
    parsed = parse_guard_spec(spec.to_dict())
    assertion = parsed.generator_assertions[0]
    assert assertion["severity"] == "block"
    assert assertion["intent"] == "semantic_anchor"
    assert assertion["stability"] == "medium"
    assert assertion["evidence_ids"] == [0, 1]
