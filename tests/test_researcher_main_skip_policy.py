from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.researcher.main import _should_skip_bundle_research


def test_researcher_main_skip_helper_respects_dynamic_eval() -> None:
    bundle = SimpleNamespace(vuln_id="NAME-OPEN-REDIRECT")
    should_skip = _should_skip_bundle_research(
        plan={"policy": {"dynamic_eval": True}},
        requirement_view={"request_identity": {"name_driven": True}},
        bundle=bundle,
        force_run=False,
    )

    assert should_skip is False


def test_researcher_main_skip_helper_respects_open_world_strict_for_name_driven_lane() -> None:
    bundle = SimpleNamespace(vuln_id="NAME-OPEN-REDIRECT")
    should_skip = _should_skip_bundle_research(
        plan={"policy": {"open_world_strict": True}},
        requirement_view={"request_identity": {"name_driven": True}},
        bundle=bundle,
        force_run=False,
    )

    assert should_skip is False


def test_researcher_main_skip_helper_uses_request_ir_for_canonicalized_name_driven_lane() -> None:
    bundle = SimpleNamespace(vuln_id="CWE-79")
    should_skip = _should_skip_bundle_research(
        plan={"policy": {"name_only_mode": "dynamic"}},
        requirement_view={
            "vuln_id": "CWE-79",
            "request_ir": {
                "request_label": "Reflected XSS",
                "resolved_vuln_id": "CWE-79",
                "name_driven": True,
                "resolution_state": "token_match",
            },
        },
        bundle=bundle,
        force_run=False,
    )

    assert should_skip is False
