from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.schema import normalize_requirement
from orchestrator.plan import build_plan


def _requirement(vuln_id: str) -> dict:
    return {
        "vuln_id": vuln_id,
        "seed": 7,
        "model_version": "gpt-5.2",
        "corpus_snapshot": "snapshot-a",
        "pattern_id": "dynamic-demo",
        "deps_digest": "deps-a",
        "base_image_digest": "base-a",
    }


def test_single_vuln_sid_changes_with_vuln_id() -> None:
    plan_a = build_plan(normalize_requirement(_requirement("CWE-89")))
    plan_b = build_plan(normalize_requirement(_requirement("CWE-9999")))

    assert plan_a["sid"] != plan_b["sid"]
    assert plan_a["effective_vuln_ids_digest"] != plan_b["effective_vuln_ids_digest"]


def test_plan_records_sid_inputs_for_traceability() -> None:
    plan = build_plan(normalize_requirement(_requirement("CWE-89")))

    sid_inputs = plan["sid_inputs"]
    assert sid_inputs["effective_vuln_ids"] == ["CWE-89"]
    assert sid_inputs["components"]["effective_vuln_ids_digest"] == plan["effective_vuln_ids_digest"]


def test_sid_changes_when_generator_mode_or_runtime_surface_changes() -> None:
    base = _requirement("CWE-89")
    template_req = dict(base)
    template_req["generator_mode"] = "template"
    template_req["runtime"] = {"db": "mysql", "allow_external_db": True}
    template_req["executor"] = {
        "allow_network": True,
        "network_mode": "bridge",
        "sidecars": [{"name": "mysql", "type": "mysql", "image": "mysql:8.0", "aliases": ["sqli-db"]}],
    }

    synthesis_req = dict(template_req)
    synthesis_req["generator_mode"] = "synthesis"

    plan_template = build_plan(normalize_requirement(template_req))
    plan_synthesis = build_plan(normalize_requirement(synthesis_req))

    assert plan_template["sid"] != plan_synthesis["sid"]
    assert plan_template["sid_inputs"]["components"]["generator_mode"] == "template"
    assert plan_synthesis["sid_inputs"]["components"]["generator_mode"] == "synthesis"
    assert (
        plan_template["sid_inputs"]["components"]["runtime_surface_digest"]
        != plan_synthesis["sid_inputs"]["components"]["runtime_surface_digest"]
        or plan_template["sid"] != plan_synthesis["sid"]
    )


def test_sid_changes_when_framework_changes() -> None:
    flask_req = _requirement("NAME-OPEN-REDIRECT")
    flask_req["language"] = "python"
    flask_req["framework"] = "flask"

    fastapi_req = dict(flask_req)
    fastapi_req["framework"] = "fastapi"

    plan_flask = build_plan(normalize_requirement(flask_req))
    plan_fastapi = build_plan(normalize_requirement(fastapi_req))

    assert plan_flask["sid"] != plan_fastapi["sid"]
    assert (
        plan_flask["sid_inputs"]["components"]["runtime_surface_digest"]
        != plan_fastapi["sid_inputs"]["components"]["runtime_surface_digest"]
    )


def test_plan_promotes_dynamic_eval_policy_flags_to_top_level_policy() -> None:
    requirement = _requirement("NAME-OPEN-REDIRECT")
    requirement["policy"] = {
        "dynamic_eval": True,
        "dynamic_eval_allow_lower_bound_fallback": True,
        "open_world_strict": True,
    }

    plan = build_plan(normalize_requirement(requirement))

    assert plan["policy"]["dynamic_eval"] is True
    assert plan["policy"]["dynamic_eval_allow_lower_bound_fallback"] is True
    assert plan["policy"]["open_world_strict"] is True


def test_sid_changes_when_dynamic_eval_policy_changes() -> None:
    base = _requirement("NAME-OPEN-REDIRECT")
    plan_default = build_plan(normalize_requirement(dict(base)))

    dynamic_req = dict(base)
    dynamic_req["policy"] = {"dynamic_eval": True}
    plan_dynamic = build_plan(normalize_requirement(dynamic_req))

    assert plan_default["sid"] != plan_dynamic["sid"]
    assert plan_dynamic["sid_inputs"]["components"]["policy_eval_digest"]


def test_sid_changes_when_name_only_mode_changes() -> None:
    base = _requirement("NAME-OPEN-REDIRECT")
    plan_default = build_plan(normalize_requirement(dict(base)))

    dynamic_req = dict(base)
    dynamic_req["policy"] = {"name_only_mode": "dynamic"}
    plan_dynamic = build_plan(normalize_requirement(dynamic_req))

    assert plan_default["sid"] != plan_dynamic["sid"]
    assert plan_dynamic["sid_inputs"]["components"]["policy_eval_digest"]
