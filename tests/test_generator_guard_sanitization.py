from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.generator.service import GeneratorService


def test_generator_sanitizes_blocking_regex_guard_before_synthesis() -> None:
    payload = {
        "schema_version": "guard_spec@1.0",
        "sid": "sid-test",
        "vuln_id": "CWE-89",
        "slug": "cwe-89",
        "generator_assertions": [
            {
                "op": "file_regex_any",
                "globs": ["**/*.py"],
                "regex": "@app\\.(get|route)\\s*\\(\\s*['\\\"]/health['\\\"]",
                "severity": "block",
                "intent": "contract",
                "stability": "high",
            }
        ],
        "normalization": {"warnings": []},
    }

    sanitized = GeneratorService._sanitize_guard_spec_for_generation(payload)

    assertion = sanitized["generator_assertions"][0]
    assert assertion["severity"] == "warn"
    assert assertion["intent"] == "syntax_hint"
    assert assertion["stability"] == "low"
    warnings = sanitized["normalization"]["warnings"]
    assert any("regex assertion" in item for item in warnings)


def test_generator_keeps_structural_blocking_guard_assertions() -> None:
    payload = {
        "schema_version": "guard_spec@1.0",
        "sid": "sid-test",
        "vuln_id": "CWE-89",
        "slug": "cwe-89",
        "generator_assertions": [
            {
                "op": "role_exists",
                "role": "service_main",
                "severity": "block",
                "intent": "contract",
                "stability": "high",
            }
        ],
        "normalization": {"warnings": []},
    }

    sanitized = GeneratorService._sanitize_guard_spec_for_generation(payload)

    assertion = sanitized["generator_assertions"][0]
    assert assertion["severity"] == "block"
    assert sanitized["normalization"]["warnings"] == []
