from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.generator.synthesis import SynthesisEngine


def test_schema_normalization_history_does_not_force_schema_error() -> None:
    notes = [
        "guard semantic mismatch: input_vector terms were not observed in generated artifacts",
        "semantic mismatch: missing input-to-SQL composition path for CWE-89",
    ]
    code = SynthesisEngine._guard_error_code(notes, unsupported_ops=[], schema_errors=[])
    assert code == "guard_semantic_mismatch"


def test_failure_fingerprint_varies_by_error_code_strategy() -> None:
    semantic_fp = SynthesisEngine._build_failure_fingerprint(
        guard_error_code="guard_semantic_mismatch",
        guard_error_subcode="cwe89_input_sql_path_missing",
        normalized_notes=["semantic mismatch: missing input-to-sql composition path for cwe-89"],
        guard_spec_digest="abc",
        unsupported_ops=[],
        schema_errors=[],
        missing_dependencies=[],
        semantic_missing_buckets=["sink"],
        builtin_semantic_errors=["semantic mismatch: missing input-to-sql composition path for cwe-89"],
        vuln_id="CWE-89",
    )
    schema_fp = SynthesisEngine._build_failure_fingerprint(
        guard_error_code="guard_assertion_schema_error",
        guard_error_subcode="dep_declared_dep_missing",
        normalized_notes=["dep_declared requires dep"],
        guard_spec_digest="abc",
        unsupported_ops=[],
        schema_errors=["dep_declared.dep missing"],
        missing_dependencies=[],
        semantic_missing_buckets=[],
        builtin_semantic_errors=[],
        vuln_id="CWE-89",
    )
    assert semantic_fp != schema_fp


def test_missing_dep_declaration_is_classified_as_dependency_failure() -> None:
    notes = [
        "guard assertion failed: missing dep declaration: flask",
    ]

    code = SynthesisEngine._guard_error_code(notes, unsupported_ops=[], schema_errors=[])
    subcode = SynthesisEngine._guard_error_subcode(notes, code)
    missing = SynthesisEngine._extract_missing_dependency_names(notes)

    assert code == "guard_dependency_missing"
    assert subcode == "dependency_decl_missing"
    assert missing == ["flask"]
