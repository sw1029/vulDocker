from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.e2e import run_case


def test_load_manifest_summary_surfaces_name_only_and_quality_fields(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-summary-surface"
    metadata_dir = tmp_path / "metadata" / sid
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "reviewer_report.json").write_text(
        json.dumps({"blocking_bundles": [], "issues_sample": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    (metadata_dir / "manifest.json").write_text(
        json.dumps(
            {
                "sid": sid,
                "pipeline_result": "success",
                "request_ir": {
                    "request_label": "Open Redirect",
                    "resolution_state": "catalog_alias",
                    "pattern_seed_state": "preserved",
                },
                "artifact_quality_summary": {"bundle_count": 1, "average_score": 8.0},
                "template_dependence_summary": {"bundle_count": 1, "minimal_dynamic_bundles": 1},
                "stack_dependence_summary": {"bundle_count": 1, "repo_prior_bounded_bundles": 1},
                "family_dependence_summary": {"bundle_count": 1, "by_class": {"semantic_signature_bounded": 1}},
                "intent_satisfaction_summary": {"bundle_count": 1, "by_status": {"degraded_dynamic_success": 1}},
                "dynamic_eval_summary": {"bundle_count": 1, "attempted_bundles": 1},
                "semantic_guided_selection_source": "request_resolution",
                "semantic_guided_ambiguous": True,
                "runtime_recipe": {"language": "python", "framework": "flask"},
                "runtime_graph": {"topology": "single_service", "nodes": [{"id": "service"}]},
                "artifact_quality": {"band": "medium"},
                "stack_dependence": {"class": "repo_prior_bounded", "stack_source": "profile_prior"},
                "family_dependence": {"class": "semantic_signature_bounded", "selection_source": "semantic_signature"},
                "dynamic_eval": {"enabled": True, "status": "degraded_success"},
                "intent_satisfaction": {"mode": "dynamic", "status": "degraded_dynamic_success"},
                "bundles": [
                    {
                        "slug": "name-open-redirect",
                        "vuln_id": "NAME-OPEN-REDIRECT",
                        "request_ir": {
                            "request_label": "Open Redirect",
                            "resolution_state": "catalog_alias",
                        },
                        "provenance": {
                            "semantic_guided_selection_source": "request_resolution",
                            "semantic_guided_ambiguous": True,
                        },
                        "runtime_recipe": {"language": "python", "framework": "flask"},
                        "runtime_graph": {"topology": "single_service", "nodes": [{"id": "service"}]},
                        "dynamic_eval": {"enabled": True, "status": "degraded_success"},
                        "artifact_quality": {"band": "medium"},
                        "stack_dependence": {"class": "repo_prior_bounded", "stack_source": "profile_prior"},
                        "family_dependence": {"class": "semantic_signature_bounded", "selection_source": "semantic_signature"},
                        "intent_satisfaction": {"mode": "dynamic", "status": "degraded_dynamic_success"},
                        "artifacts": {
                            "run_summary": {"run_passed": True, "exit_code": 0},
                            "eval_result": {"verify_pass": True},
                        },
                    }
                ],
                "reports": {"evals": {"overall_pass": True}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(run_case, "REPO_ROOT", tmp_path)

    summary = run_case._load_manifest_summary(sid, pipeline_returncode=0)

    assert summary["request_ir"]["resolution_state"] == "catalog_alias"
    assert summary["artifact_quality_summary"]["average_score"] == 8.0
    assert summary["template_dependence_summary"]["minimal_dynamic_bundles"] == 1
    assert summary["stack_dependence_summary"]["repo_prior_bounded_bundles"] == 1
    assert summary["family_dependence_summary"]["by_class"] == {"semantic_signature_bounded": 1}
    assert summary["intent_satisfaction_summary"]["by_status"] == {"degraded_dynamic_success": 1}
    assert summary["dynamic_eval_summary"]["attempted_bundles"] == 1
    assert summary["semantic_guided_selection_source"] == "request_resolution"
    assert summary["semantic_guided_ambiguous"] is True
    assert summary["runtime_recipe"]["framework"] == "flask"
    assert summary["runtime_graph"]["topology"] == "single_service"
    assert summary["artifact_quality"]["band"] == "medium"
    assert summary["stack_dependence"]["class"] == "repo_prior_bounded"
    assert summary["family_dependence"]["class"] == "semantic_signature_bounded"
    assert summary["dynamic_eval"]["status"] == "degraded_success"
    assert summary["intent_satisfaction"]["status"] == "degraded_dynamic_success"
    assert summary["bundles"][0]["request_ir"]["request_label"] == "Open Redirect"
    assert summary["bundles"][0]["semantic_guided_selection_source"] == "request_resolution"
    assert summary["bundles"][0]["semantic_guided_ambiguous"] is True
    assert summary["bundles"][0]["runtime_graph"]["topology"] == "single_service"
    assert summary["bundles"][0]["stack_dependence"]["stack_source"] == "profile_prior"
    assert summary["bundles"][0]["family_dependence"]["selection_source"] == "semantic_signature"
