from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.generator.synthesis import SynthesisEngine
from agents.researcher.service import ResearcherService
from common.contracts import build_generator_contract
from common.guardrails import GuardEngine, build_guard_spec
from common.roles import normalize_role, role_matches


def test_normalize_role_aliases() -> None:
    assert normalize_role("server") == "service_main"
    assert normalize_role("verifier") == "poc_entry"
    assert role_matches("server", "service_main") is True
    assert role_matches("verifier", "poc_entry") is True


def test_guard_engine_role_exists_accepts_alias_manifest_roles() -> None:
    spec = build_guard_spec(
        sid="sid-role",
        vuln_id="CWE-9999",
        slug="cwe-9999",
        semantic_signature={},
        generator_assertions=[
            {"op": "role_exists", "role": "service_main"},
            {"op": "role_exists", "role": "poc_entry"},
        ],
        verifier_assertions=[],
        source="contract",
    )
    engine = GuardEngine("CWE-9999", spec.to_dict())
    report = engine.evaluate_manifest(
        {
            "files": [
                {"path": "server.py", "role": "server", "content": "print('server')\n"},
                {"path": "exploit.py", "role": "verifier", "content": "print('exploit')\n"},
            ]
        }
    )

    assert report.passed is True
    assert report.violations == []


def test_researcher_normalizes_role_aliases_in_guard_payload() -> None:
    service = ResearcherService.__new__(ResearcherService)
    service.requirement = {  # type: ignore[attr-defined]
        "vuln_id": "CWE-9999",
        "language": "python",
        "runtime": {"python_version": "3.11"},
    }
    payload = {
        "generator_assertions": [
            {"op": "role_exists", "role": "server"},
            {"op": "role_exists", "role": "verifier"},
        ],
        "verifier_assertions": [],
    }

    normalized = service._normalize_guard_payload_ops(  # type: ignore[attr-defined]
        payload,
        unsupported_policy="normalize_retry",
        bundle=None,
        report={},
    )

    assert normalized is not None
    roles = [assertion.get("role") for assertion in normalized["generator_assertions"]]
    assert roles == ["service_main", "poc_entry"]


def test_build_generator_contract_resolves_alias_manifest_roles(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "generator_manifest.json").write_text(
        json.dumps(
            {
                "manifest": {
                    "files": [
                        {"path": "server.py", "role": "server", "content": "print('server')\n"},
                        {"path": "exploit.py", "role": "verifier", "content": "print('exploit')\n"},
                    ],
                    "poc": {"success_signature": "Exploit SUCCESS"},
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = build_generator_contract(
        sid="sid-role",
        vuln_id="CWE-9999",
        metadata_dir=metadata_dir,
    )

    assert payload["service_entry"] == "server.py"
    assert payload["poc_entry"] == "exploit.py"


def test_synthesis_parse_manifest_canonicalizes_alias_roles() -> None:
    engine = SynthesisEngine.__new__(SynthesisEngine)

    manifest = engine._parse_manifest(  # type: ignore[attr-defined]
        json.dumps(
            {
                "files": [
                    {"path": "server.py", "role": "server", "content": "print('server')\n"},
                    {"path": "exploit.py", "role": "verifier", "content": "print('exploit')\n"},
                ]
            }
        ),
        1,
    )

    roles = [entry.get("role") for entry in manifest["files"]]
    assert roles == ["service_main", "poc_entry"]
