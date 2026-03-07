from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.researcher.service import ResearcherService
from common.rules import load_rule, list_rules, rule_filename_for_vuln_id
from common.run_matrix import VulnBundle


def test_rule_filename_for_name_identifier_keeps_name_prefix() -> None:
    assert rule_filename_for_vuln_id("NAME-TEMPLATE-INJECTION") == "name-template-injection"
    assert rule_filename_for_vuln_id("CWE-89") == "cwe-89"


def test_load_rule_resolves_name_runtime_rule(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime_rules"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    rule_path = runtime_dir / "name-template-injection.yaml"
    rule_path.write_text(
        yaml.safe_dump(
            {
                "cwe": "NAME-TEMPLATE-INJECTION",
                "version": 2,
                "scenario_type": "web-poc",
                "verification": {"source": "runtime", "require_flag": False, "flag_mode": "none", "exit_code": "zero"},
                "output": {"mode": "auto"},
                "runtime": {"assertion_program": [{"op": "contains", "string": "OK: SSTI confirmed"}]},
                "success_signature": "Exploit SUCCESS",
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("VULD_RUNTIME_RULE_DIRS", str(runtime_dir))
    monkeypatch.setenv("VULD_ALLOW_RUNTIME_RULE_OVERRIDE_STATIC", "false")
    load_rule.cache_clear()  # type: ignore[attr-defined]
    list_rules.cache_clear()  # type: ignore[attr-defined]

    rule = load_rule("NAME-TEMPLATE-INJECTION")

    assert rule.get("cwe") == "NAME-TEMPLATE-INJECTION"
    assert rule.get("success_signature") == "Exploit SUCCESS"


def test_researcher_writer_uses_shared_rule_filename_normalization(tmp_path: Path) -> None:
    service = ResearcherService.__new__(ResearcherService)
    service.runtime_rules_dir = tmp_path  # type: ignore[attr-defined]
    bundle = VulnBundle(vuln_id="NAME-TEMPLATE-INJECTION", slug="name-template-injection", workspace_subdir="app")

    path = service._write_candidate_rule(bundle, {"cwe": "NAME-TEMPLATE-INJECTION"})  # type: ignore[attr-defined]

    assert path == tmp_path / "name-template-injection.yaml"
    assert path.exists()
